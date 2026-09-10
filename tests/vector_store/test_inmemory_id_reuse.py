"""Regression tests for issue #1029: VectorStore inmemory backend must not
reissue live vector IDs after a deletion.

Before the fix, `store_vectors()` derived new IDs as
``f"vec_{len(self.vectors) + i}"``.  After any deletion `len` decreases,
so the next insertion generates an ID that already belongs to a surviving
vector, silently overwriting its embedding and metadata.

Three test groups:

1. ``TestInmemoryIdNoReuseAfterDelete``  — direct VectorStore path
2. ``TestAgentMemoryIdNoReuseAfterDelete`` — AgentMemory path
3. ``TestInmemoryIdPersistence``           — save / load / delete / store cycle
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np


# ---------------------------------------------------------------------------
# Helper: build a lightweight VectorStore(backend="inmemory") without
# triggering the real EmbeddingGenerator or VectorIndexer.
# ---------------------------------------------------------------------------

def _make_store(dim: int = 4) -> "VectorStore":  # noqa: F821
    """Return an inmemory VectorStore with heavy components mocked out."""
    from semantica.vector_store.vector_store import VectorStore

    with patch("semantica.vector_store.vector_store.get_logger",
               return_value=MagicMock()), \
         patch("semantica.vector_store.vector_store.get_progress_tracker",
               return_value=MagicMock()), \
         patch("semantica.vector_store.vector_store.VectorIndexer"), \
         patch("semantica.vector_store.vector_store.VectorRetriever"), \
         patch("semantica.vector_store.vector_store.EmbeddingGenerator"):
        store = VectorStore(backend="inmemory", config={"dimension": dim})
    store.embedder = None
    return store


_RNG = np.random.default_rng(seed=1029)


def _vec(dim: int = 4) -> np.ndarray:
    return _RNG.random(dim).astype(np.float32)


# ---------------------------------------------------------------------------
# 1. Direct VectorStore path
# ---------------------------------------------------------------------------

class TestInmemoryIdNoReuseAfterDelete(unittest.TestCase):
    """Store A+B, delete A, store C — B and C must have distinct IDs and both
    survive with correct metadata."""

    def _store(self) -> "VectorStore":  # noqa: F821
        return _make_store()

    def test_b_and_c_have_different_ids(self):
        """Core regression: id_c must not equal id_b."""
        store = self._store()
        id_a, id_b = store.store_vectors(
            [_vec(), _vec()], [{"label": "A"}, {"label": "B"}]
        )
        store.delete_vectors([id_a])
        (id_c,) = store.store_vectors([_vec()], [{"label": "C"}])

        self.assertNotEqual(
            id_b, id_c,
            f"ID collision: both B and C got id={id_b!r}",
        )

    def test_both_vectors_remain_after_delete_reinsert(self):
        """B's entry must survive the deletion of A and the insertion of C."""
        store = self._store()
        id_a, id_b = store.store_vectors(
            [_vec(), _vec()], [{"label": "A"}, {"label": "B"}]
        )
        store.delete_vectors([id_a])
        (id_c,) = store.store_vectors([_vec()], [{"label": "C"}])

        self.assertIn(id_b, store.vectors, "B's vector was lost")
        self.assertIn(id_c, store.vectors, "C's vector was not stored")
        self.assertIn(id_b, store.metadata, "B's metadata was lost")
        self.assertIn(id_c, store.metadata, "C's metadata was not stored")

    def test_count_is_two_after_store_delete_store(self):
        """After storing 2, deleting 1, storing 1 the count must be 2."""
        store = self._store()
        id_a, _ = store.store_vectors(
            [_vec(), _vec()], [{}, {}]
        )
        store.delete_vectors([id_a])
        store.store_vectors([_vec()], [{}])

        self.assertEqual(len(store.vectors), 2)

    def test_b_metadata_not_overwritten_by_c(self):
        """B's metadata must be unchanged after C is stored."""
        store = self._store()
        id_a, id_b = store.store_vectors(
            [_vec(), _vec()],
            [{"label": "A"}, {"label": "B", "sentinel": True}],
        )
        store.delete_vectors([id_a])
        store.store_vectors([_vec()], [{"label": "C"}])

        self.assertEqual(
            store.metadata[id_b],
            {"label": "B", "sentinel": True},
            "B's metadata was silently overwritten",
        )

    def test_id_uniqueness_across_multiple_delete_reinsert_cycles(self):
        """Each cycle of delete-then-store must produce a fresh, unique ID."""
        store = self._store()
        seen_ids: set = set()

        # Initial batch
        batch = store.store_vectors([_vec() for _ in range(3)], [{} for _ in range(3)])
        seen_ids.update(batch)

        # Three delete-then-store cycles
        for current_id in list(batch):
            store.delete_vectors([current_id])
            (new_id,) = store.store_vectors([_vec()], [{}])
            self.assertNotIn(
                new_id, seen_ids,
                f"Generated ID {new_id!r} collides with a previously used ID",
            )
            seen_ids.add(new_id)

    def test_counter_skips_explicit_vec_n_ids(self):
        """The monotonic counter must skip over any explicit ``vec_N`` already
        present so it never collides with a manually supplied ID."""
        store = self._store()

        # Manually insert vec_1 so the counter must skip it
        store.vectors["vec_1"] = _vec()
        store.metadata["vec_1"] = {"explicit": True}

        # Ask for two auto-generated IDs; one would be vec_1 if the counter
        # did not skip it.
        ids = store.store_vectors([_vec(), _vec()], [{}, {}])

        self.assertNotIn("vec_1", ids, "Monotonic counter re-generated an explicit ID")
        # vec_1's explicit entry must be intact
        self.assertEqual(store.metadata["vec_1"], {"explicit": True})
        # Both new vectors must actually be in the store
        for new_id in ids:
            self.assertIn(new_id, store.vectors)

    def test_auto_generated_id_never_silently_overwrites_live_vector(self):
        """An automatically generated ID must never land on top of a live
        auto-generated vector, regardless of deletion history.

        This is the core of 'Never overwrite an existing live vector id
        silently' from issue #1029: after any sequence of stores and deletes
        every auto-generated ID must map to exactly one vector.
        """
        store = self._store()
        # Store 5 vectors — auto-ids vec_0..vec_4
        first_batch = store.store_vectors([_vec() for _ in range(5)], [{} for _ in range(5)])
        # Delete vec_0, vec_1, vec_2 — _next_id stays at 5, so the next
        # auto-id should be vec_5, vec_6 …  NOT vec_2/vec_3/vec_4.
        store.delete_vectors(first_batch[:3])
        surviving = set(store.vectors.keys())  # {vec_3, vec_4}

        second_batch = store.store_vectors([_vec(), _vec()], [{}, {}])

        # None of the new IDs must collide with surviving ones
        for new_id in second_batch:
            self.assertNotIn(
                new_id, surviving,
                f"Auto-generated ID {new_id!r} silently landed on a live vector",
            )
        # Both new vectors must be independently present
        for new_id in second_batch:
            self.assertIn(new_id, store.vectors)
            self.assertIn(new_id, store.metadata)
        # Total count: 2 surviving + 2 new
        self.assertEqual(len(store.vectors), 4)

    def test_collision_detection_no_silent_overwrite_even_with_corrupted_counter(self):
        """Even if _next_id is externally wound back (simulating a corrupt
        load), the generator must never silently overwrite a live vector.

        The while-loop guarantees this by skipping every occupied candidate
        until it finds a free slot.  The existing vector and its metadata
        must be completely unchanged after the call.
        """
        store = self._store()
        # Store vec_0 and vec_1 (_next_id advances to 2)
        ids = store.store_vectors([_vec(), _vec()], [{"orig": 0}, {"orig": 1}])
        id_b = ids[1]  # vec_1
        vec_b_before = store.vectors[id_b].copy()
        meta_b_before = dict(store.metadata[id_b])

        # Corrupt the counter: reset to 0 so candidates start at vec_0/vec_1
        store._next_id = 0

        # store_vectors must succeed without raising and without overwriting
        new_ids = store.store_vectors([_vec()], [{"new": True}])

        # The new ID must be some other slot — not vec_0 or vec_1
        self.assertNotIn(
            new_ids[0], {ids[0], ids[1]},
            f"New vector landed on a live ID {new_ids[0]!r} "
            "(no-silent-overwrite invariant violated)",
        )
        # vec_1 must be completely unchanged
        np.testing.assert_array_equal(
            store.vectors[id_b], vec_b_before,
            err_msg="Live vector vec_1 was overwritten by the post-corruption store call",
        )
        self.assertEqual(
            store.metadata[id_b], meta_b_before,
            "Live metadata for vec_1 was overwritten by the post-corruption store call",
        )
        # New vector must actually be in the store
        self.assertIn(new_ids[0], store.vectors)
        self.assertEqual(store.metadata[new_ids[0]], {"new": True})
# ---------------------------------------------------------------------------

class TestAgentMemoryIdNoReuseAfterDelete(unittest.TestCase):
    """Exercise the ID-collision fix through AgentMemory.store() /
    delete_memory() rather than VectorStore directly."""

    def setUp(self):
        """Build a real VectorStore(inmemory) and bind it to AgentMemory.

        EmbeddingGenerator is mocked so the test doesn't need a model.
        """
        from semantica.context.agent_memory import AgentMemory
        from semantica.vector_store.vector_store import VectorStore

        self._embedding_patch = patch(
            "semantica.context.agent_memory.AgentMemory._generate_embedding",
            side_effect=lambda text: np.ones(8, dtype=np.float32),
        )
        self._embedding_patch.start()

        self.store = VectorStore(backend="inmemory", config={"dimension": 8})
        # Suppress real EmbeddingGenerator on the store itself
        self.store.embedder = None

        self.memory = AgentMemory(vector_store=self.store)

    def tearDown(self):
        self._embedding_patch.stop()

    def test_b_and_c_have_different_vector_ids(self):
        """After storing A+B, deleting A, storing C, B and C must have
        distinct vector IDs."""
        self.memory.store("content A", memory_id="mem_a", skip_graph=True)
        self.memory.store("content B", memory_id="mem_b", skip_graph=True)

        vid_b_before = self.memory.vector_ids_for("mem_b")

        self.memory.delete_memory("mem_a")
        self.memory.store("content C", memory_id="mem_c", skip_graph=True)

        vid_b = self.memory.vector_ids_for("mem_b")
        vid_c = self.memory.vector_ids_for("mem_c")

        # B's vector IDs must be unchanged — it was never touched.
        self.assertEqual(vid_b, vid_b_before, "mem_b's vector IDs changed unexpectedly")
        self.assertTrue(vid_b, "mem_b has no tracked vector IDs")
        self.assertTrue(vid_c, "mem_c has no tracked vector IDs")
        self.assertTrue(
            set(vid_b).isdisjoint(set(vid_c)),
            f"B and C share vector IDs: {set(vid_b) & set(vid_c)}",
        )

    def test_both_memories_remain_independently_retrievable(self):
        """mem_b and mem_c must both survive and report correct vector-store
        embeddings after the delete-reinsert cycle."""
        self.memory.store("content B", memory_id="mem_b", skip_graph=True)
        self.memory.store("content A", memory_id="mem_a", skip_graph=True)
        self.memory.delete_memory("mem_a")
        self.memory.store("content C", memory_id="mem_c", skip_graph=True)

        self.assertIn("mem_b", self.memory.memory_items)
        self.assertIn("mem_c", self.memory.memory_items)
        self.assertNotIn("mem_a", self.memory.memory_items)

        # Each surviving memory must have its own live vector in the store
        for mid in ("mem_b", "mem_c"):
            vids = self.memory.vector_ids_for(mid)
            for vid in vids:
                self.assertIn(
                    vid, self.store.vectors,
                    f"{mid!r} vector id {vid!r} is missing from the store",
                )

    def test_vector_store_count_is_correct(self):
        """After storing 2, deleting 1, storing 1 the vector count must be 2."""
        self.memory.store("content A", memory_id="mem_a", skip_graph=True)
        self.memory.store("content B", memory_id="mem_b", skip_graph=True)
        self.memory.delete_memory("mem_a")
        self.memory.store("content C", memory_id="mem_c", skip_graph=True)

        self.assertEqual(self.store.count(), 2)

    def test_b_embedding_not_overwritten(self):
        """mem_b's vector must be the original embedding, not C's."""
        # Give B a distinct embedding so we can detect overwriting
        call_order: list = []

        def _side_effect(text: str) -> np.ndarray:
            call_order.append(text)
            # Unique per-call vector based on call order length
            v = np.zeros(8, dtype=np.float32)
            v[len(call_order) % 8] = float(len(call_order))
            return v

        with patch(
            "semantica.context.agent_memory.AgentMemory._generate_embedding",
            side_effect=_side_effect,
        ):
            mem2 = __import__(
                "semantica.context.agent_memory", fromlist=["AgentMemory"]
            ).AgentMemory(vector_store=self.store)
            mem2.store("content A", memory_id="mem_a2", skip_graph=True)
            mem2.store("content B", memory_id="mem_b2", skip_graph=True)
            b_embedding = mem2.memory_items["mem_b2"].embedding

            mem2.delete_memory("mem_a2")
            mem2.store("content C", memory_id="mem_c2", skip_graph=True)

            vid_b = mem2.vector_ids_for("mem_b2")
            self.assertTrue(vid_b, "mem_b2 has no tracked vector ID")
            stored_b_vec = self.store.vectors.get(vid_b[0])
            self.assertIsNotNone(stored_b_vec)
            np.testing.assert_array_equal(
                stored_b_vec,
                b_embedding if hasattr(b_embedding, "__len__") else np.array(b_embedding),
                err_msg="B's stored vector was silently overwritten by C's embedding",
            )


# ---------------------------------------------------------------------------
# 3. Persistence: save → load → delete → store must not collide
# ---------------------------------------------------------------------------

class TestInmemoryIdPersistence(unittest.TestCase):
    """The _next_id counter must survive save/load so that inserting after a
    delete-and-reload cycle cannot generate an ID already held by a surviving
    vector."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _fresh_store(self, dim: int = 4):
        return _make_store(dim=dim)

    def test_next_id_is_persisted_in_json(self):
        """save() must write ``next_id`` into store_data.json."""
        store = self._fresh_store()
        store.store_vectors([_vec(), _vec(), _vec()], [{}, {}, {}])
        store.save(self.tmpdir)

        with open(f"{self.tmpdir}/store_data.json", encoding="utf-8") as fh:
            data = json.load(fh)

        self.assertIn("next_id", data, "save() did not write 'next_id' to JSON")
        self.assertGreaterEqual(data["next_id"], 3)

    def test_load_restores_next_id(self):
        """load() must restore _next_id so the counter does not restart at 0."""
        store = self._fresh_store()
        store.store_vectors([_vec(), _vec(), _vec()], [{}, {}, {}])
        store.save(self.tmpdir)

        loaded = self._fresh_store()
        loaded.load(self.tmpdir)

        self.assertGreaterEqual(
            loaded._next_id, 3,
            f"load() set _next_id={loaded._next_id}, expected >= 3",
        )

    def test_no_collision_after_save_load_delete_store(self):
        """Full lifecycle: save → load → delete one → store one new vector.
        The new ID must not collide with any surviving vector."""
        store = self._fresh_store()
        # Store vec_0, vec_1, vec_2
        ids = store.store_vectors([_vec() for _ in range(3)], [{} for _ in range(3)])
        store.save(self.tmpdir)

        # Load fresh instance
        loaded = self._fresh_store()
        loaded.load(self.tmpdir)

        # Delete vec_0 (ntotal drops to 2; without the fix, next id = vec_2)
        loaded.delete_vectors([ids[0]])
        surviving = set(loaded.vectors.keys())

        # Store a new vector — must not reuse any surviving ID
        (new_id,) = loaded.store_vectors([_vec()], [{"new": True}])

        self.assertNotIn(
            new_id, surviving,
            f"Generated ID {new_id!r} collides with a surviving ID "
            f"(surviving={sorted(surviving)})",
        )
        self.assertEqual(len(loaded.vectors), 3)

    def test_stale_next_id_in_json_is_clamped(self):
        """load() must clamp a stale persisted next_id to at least
        max(vec_N suffix)+1, guarding against corrupted saves."""
        store = self._fresh_store()
        # Stores vec_0, vec_1, vec_2
        store.store_vectors([_vec() for _ in range(3)], [{}, {}, {}])
        store.save(self.tmpdir)

        # Corrupt the JSON: set next_id to 1 (below vec_2's suffix+1 = 3)
        json_path = f"{self.tmpdir}/store_data.json"
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["next_id"] = 1
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

        loaded = self._fresh_store()
        loaded.load(self.tmpdir)

        self.assertGreaterEqual(
            loaded._next_id, 3,
            f"Stale next_id=1 was not clamped; got {loaded._next_id} (expected >= 3)",
        )

    def test_missing_next_id_in_old_json_inferred_from_vec_suffixes(self):
        """Older store files without 'next_id' must have the counter inferred
        from the highest ``vec_N`` suffix so that loading them is safe."""
        store = self._fresh_store()
        store.store_vectors([_vec() for _ in range(4)], [{} for _ in range(4)])
        store.save(self.tmpdir)

        # Remove next_id to simulate an older save file
        json_path = f"{self.tmpdir}/store_data.json"
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        data.pop("next_id", None)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

        loaded = self._fresh_store()
        loaded.load(self.tmpdir)

        # _next_id must be at least 4 (vec_0..vec_3 → max suffix+1 = 4)
        self.assertGreaterEqual(
            loaded._next_id, 4,
            f"Missing next_id not inferred correctly; got {loaded._next_id}",
        )

        # And a subsequent insert must not collide
        surviving = set(loaded.vectors.keys())
        (new_id,) = loaded.store_vectors([_vec()], [{}])
        self.assertNotIn(
            new_id, surviving,
            f"Post-load insert collided: {new_id!r} already in {sorted(surviving)}",
        )


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# 4. Concurrency: concurrent store_vectors calls must not produce duplicate IDs
# ---------------------------------------------------------------------------

class TestInmemoryIdConcurrency(unittest.TestCase):
    """Concurrent store_vectors calls on the same VectorStore must each get
    unique IDs and all vectors must survive (no silent overwrites)."""

    def test_concurrent_store_vectors_produce_unique_ids(self):
        """Two threads storing vectors simultaneously must not collide."""
        import threading as _threading

        store = _make_store(dim=4)
        results: list = []
        errors: list = []

        def _store_batch(n: int) -> None:
            try:
                ids = store.store_vectors(
                    [_vec() for _ in range(n)],
                    [{"batch": n, "idx": i} for i in range(n)],
                )
                results.extend(ids)
            except Exception as exc:
                errors.append(exc)

        threads = [_threading.Thread(target=_store_batch, args=(5,)) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(errors, f"Threads raised: {errors}")
        total = 6 * 5
        self.assertEqual(len(results), total, "Some store calls lost vectors")
        # All returned IDs must be unique — no two threads got the same ID
        self.assertEqual(
            len(set(results)), total,
            f"Duplicate IDs produced under concurrency: "
            f"{[x for x in results if results.count(x) > 1]}",
        )
        # Every returned ID must be present in the store
        for vid in results:
            self.assertIn(vid, store.vectors, f"ID {vid!r} not in store after concurrent insert")

    def test_concurrent_delete_and_store_no_phantom_ids(self):
        """A thread deleting while another is storing must not leave the store
        with stale index entries or inconsistent counts."""
        import threading as _threading

        store = _make_store(dim=4)
        initial = store.store_vectors([_vec() for _ in range(4)], [{} for _ in range(4)])
        errors: list = []

        def _deleter():
            try:
                store.delete_vectors(initial[:2])
            except Exception as exc:
                errors.append(exc)

        def _storer():
            try:
                store.store_vectors([_vec(), _vec()], [{}, {}])
            except Exception as exc:
                errors.append(exc)

        t1 = _threading.Thread(target=_deleter)
        t2 = _threading.Thread(target=_storer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertFalse(errors, f"Threads raised: {errors}")
        # After the dust settles the vectors dict and metadata must agree
        self.assertEqual(
            set(store.vectors.keys()), set(store.metadata.keys()),
            "vectors and metadata dicts are out of sync after concurrent delete+store",
        )

    def test_concurrent_search_and_delete_no_runtime_error(self):
        """search_vectors() must not raise RuntimeError when a concurrent
        delete_vectors() modifies the store during iteration.

        Uses threading.Barrier to make the race deterministic: the search
        thread announces it is ready just before calling search_similar, and
        the delete thread fires only after that signal has been received.
        Without the lock-protected snapshot in search_vectors(), the delete
        would mutate self.vectors while list() is iterating it, reliably
        causing 'RuntimeError: dictionary changed size during iteration'.
        """
        import threading as _threading

        store = _make_store(dim=4)
        vecs = store.store_vectors([_vec() for _ in range(8)], [{} for _ in range(8)])
        query = _vec()
        errors: list = []

        # Barrier with 2 parties: searcher + deleter.
        barrier = _threading.Barrier(2)

        original_search_similar = store.retriever.search_similar

        def _patched_search_similar(q, vectors, keys, k, **kw):
            # Signal the deleter that iteration is about to begin, then wait
            # for it to be ready too.  Both threads proceed together.
            barrier.wait(timeout=5)
            return original_search_similar(q, vectors, keys, k, **kw)

        store.retriever.search_similar = _patched_search_similar

        def _searcher():
            try:
                store.search_vectors(query, k=4)
            except Exception as exc:
                errors.append(exc)

        def _deleter():
            barrier.wait(timeout=5)   # wait until searcher is mid-search
            try:
                store.delete_vectors(vecs[:4])
            except Exception as exc:
                errors.append(exc)

        t1 = _threading.Thread(target=_searcher)
        t2 = _threading.Thread(target=_deleter)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertFalse(
            errors,
            f"Concurrent search+delete raised: {errors}",
        )
