"""Tests for FAISSIndex.delete_vectors and FAISSStore.delete_vectors (#1374)."""

import numpy as np
import pytest

from semantica.context.erasure import (
    STATUS_ERASED,
    STATUS_UNSUPPORTED,
    ErasureCoordinator,
)
from semantica.utils.exceptions import ProcessingError
from semantica.vector_store import VectorStore
from semantica.vector_store.faiss_store import FAISSIndex, FAISSStore


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _flat_index(dim: int = 3) -> "faiss.IndexFlatL2":  # noqa: F821
    faiss = pytest.importorskip("faiss")
    return faiss.IndexFlatL2(dim)


def _populated_store(
    dim: int = 3,
    ids=("a", "b", "c", "d", "e"),
    meta=None,
):
    """Return an FAISSStore with *ids* already inserted (random unit vectors)."""
    faiss = pytest.importorskip("faiss")
    store = FAISSStore(dimension=dim)
    n = len(ids)
    rng = np.random.default_rng(seed=42)
    vectors = rng.random((n, dim)).astype(np.float32)
    metadata = meta or [{} for _ in ids]
    store.add_vectors(vectors, ids=list(ids), metadata=metadata)
    return store


def _populated_index(dim: int = 3, ids=("a", "b", "c", "d", "e")):
    """Return a bare FAISSIndex with *ids* inserted (random unit vectors)."""
    faiss = pytest.importorskip("faiss")
    idx = FAISSIndex(faiss.IndexFlatL2(dim), dimension=dim)
    n = len(ids)
    rng = np.random.default_rng(seed=42)
    vectors = rng.random((n, dim)).astype(np.float32)
    idx.add_vectors(vectors, ids=list(ids))
    return idx


# ---------------------------------------------------------------------------
# FAISSIndex-level unit tests
# ---------------------------------------------------------------------------


class TestFAISSIndexDeleteVectors:
    def test_delete_single_existing_id(self):
        idx = _populated_index()
        result = idx.delete_vectors(["b"])
        assert result == {"delete_count": 1}
        assert "b" not in idx.vector_ids
        assert idx.index.ntotal == len(idx.vector_ids) == 4

    def test_delete_multiple_existing_ids(self):
        idx = _populated_index()
        result = idx.delete_vectors(["b", "d"])
        assert result == {"delete_count": 2}
        assert "b" not in idx.vector_ids
        assert "d" not in idx.vector_ids
        assert sorted(idx.vector_ids) == ["a", "c", "e"]
        assert idx.index.ntotal == 3

    def test_delete_nonexistent_id_is_noop(self):
        idx = _populated_index()
        result = idx.delete_vectors(["z"])
        assert result == {"delete_count": 0}
        assert len(idx.vector_ids) == 5
        assert idx.index.ntotal == 5

    def test_delete_empty_list_is_noop(self):
        idx = _populated_index()
        result = idx.delete_vectors([])
        assert result == {"delete_count": 0}
        assert len(idx.vector_ids) == 5

    def test_delete_duplicate_ids_in_request_only_removes_once(self):
        idx = _populated_index()
        result = idx.delete_vectors(["b", "b", "b"])
        assert result == {"delete_count": 1}
        assert "b" not in idx.vector_ids
        assert len(idx.vector_ids) == 4

    def test_delete_count_reflects_actual_removal(self):
        idx = _populated_index()
        # "z" doesn't exist; only "a" and "c" do
        result = idx.delete_vectors(["a", "c", "z"])
        assert result == {"delete_count": 2}

    def test_metadata_removed_for_deleted_id(self):
        faiss = pytest.importorskip("faiss")
        idx = FAISSIndex(faiss.IndexFlatL2(3), dimension=3)
        vectors = np.eye(3, dtype=np.float32)[:2]
        idx.add_vectors(vectors, ids=["x", "y"])
        idx.metadata = {"x": {"val": 1}, "y": {"val": 2}}
        idx.delete_vectors(["x"])
        assert "x" not in idx.metadata
        assert "y" in idx.metadata

    def test_vector_ids_list_stays_parallel_to_faiss_ntotal(self):
        idx = _populated_index(ids=["a", "b", "c"])
        idx.delete_vectors(["b"])
        assert len(idx.vector_ids) == idx.index.ntotal == 2

    def test_search_does_not_return_deleted_id(self):
        """After deletion, similarity search must not return the deleted ID."""
        faiss = pytest.importorskip("faiss")
        idx = FAISSIndex(faiss.IndexFlatL2(3), dimension=3)
        vectors = np.array(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
        )
        idx.add_vectors(vectors, ids=["a", "b", "c"])
        idx.delete_vectors(["b"])

        query = np.array([[0.0, 1.0, 0.0]], dtype=np.float32)
        distances, indices = idx.search(query, k=3)
        # Filter both negative sentinels (-1) and out-of-range indices.
        returned_ids = [
            idx.vector_ids[i]
            for i in indices[0]
            if 0 <= i < len(idx.vector_ids)
        ]
        assert "b" not in returned_ids

    def test_get_vector_returns_none_after_deletion(self):
        faiss = pytest.importorskip("faiss")
        idx = FAISSIndex(faiss.IndexFlatL2(3), dimension=3)
        vectors = np.eye(3, dtype=np.float32)
        idx.add_vectors(vectors, ids=["a", "b", "c"])
        idx.delete_vectors(["b"])
        assert idx.get_vector("b") is None

    def test_get_metadata_returns_none_after_deletion(self):
        faiss = pytest.importorskip("faiss")
        idx = FAISSIndex(faiss.IndexFlatL2(3), dimension=3)
        idx.add_vectors(np.eye(3, dtype=np.float32)[:2], ids=["a", "b"])
        idx.metadata = {"a": {"k": 1}, "b": {"k": 2}}
        idx.delete_vectors(["b"])
        assert idx.get_metadata("b") is None

    def test_add_vectors_after_deletion_works(self):
        """Inserting new vectors after deletion maintains correct position mapping."""
        idx = _populated_index(ids=["a", "b", "c"])
        idx.delete_vectors(["b"])
        new_vecs = np.array([[0.5, 0.5, 0.0]], dtype=np.float32)
        idx.add_vectors(new_vecs, ids=["new"])
        assert "new" in idx.vector_ids
        assert len(idx.vector_ids) == idx.index.ntotal == 3

    def test_save_load_after_deletion_preserves_state(self, tmp_path):
        """Deletion persists correctly through save/load round-trip."""
        _ = pytest.importorskip("faiss")
        idx = _populated_index(ids=["a", "b", "c"])
        idx.delete_vectors(["b"])

        path = tmp_path / "idx.faiss"
        idx.save(path)
        loaded = FAISSIndex.load(path, dimension=3)

        assert "b" not in loaded.vector_ids
        assert sorted(loaded.vector_ids) == ["a", "c"]
        assert loaded.index.ntotal == 2

    def test_hnsw_delete_raises_not_implemented(self):
        """HNSW does not support remove_ids; must raise NotImplementedError."""
        faiss = pytest.importorskip("faiss")
        hnsw = FAISSIndex(faiss.IndexHNSWFlat(4, 16), dimension=4)
        vecs = np.random.rand(5, 4).astype(np.float32)
        hnsw.add_vectors(vecs, ids=["a", "b", "c", "d", "e"])
        with pytest.raises(NotImplementedError):
            hnsw.delete_vectors(["a"])
        # Python-side state must be untouched
        assert len(hnsw.vector_ids) == 5

    def test_ivf_delete_raises_not_implemented(self):
        """IVF does not compact labels after remove_ids; raise NotImplementedError.

        IVF surviving labels stay sparse (0,2,4 not 0,1,2), so the list-compact
        approach used by Flat would desynchronize search labels from vector_ids.
        """
        faiss = pytest.importorskip("faiss")
        dim = 4
        train = np.random.rand(80, dim).astype(np.float32)
        q = faiss.IndexFlatL2(dim)
        ivf = faiss.IndexIVFFlat(q, dim, 2)
        ivf.train(train)
        idx = FAISSIndex(ivf, dimension=dim)
        vecs = np.random.rand(5, dim).astype(np.float32)
        idx.add_vectors(vecs, ids=["a", "b", "c", "d", "e"])
        with pytest.raises(NotImplementedError):
            idx.delete_vectors(["b"])
        # Python-side state must be completely untouched
        assert idx.vector_ids == ["a", "b", "c", "d", "e"]


# ---------------------------------------------------------------------------
# FAISSStore-level unit tests
# ---------------------------------------------------------------------------


class TestFAISSStoreDeleteVectors:
    def test_delete_uninitialized_index_raises_processing_error(self):
        store = FAISSStore(dimension=3)
        with pytest.raises(ProcessingError, match="Index not initialized"):
            store.delete_vectors(["a"])

    def test_delete_existing_id_returns_dict(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b", "c"])
        result = store.delete_vectors(["b"])
        assert result == {"delete_count": 1}

    def test_delete_reduces_count(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b", "c"])
        assert store.count() == 3
        store.delete_vectors(["b"])
        assert store.count() == 2

    def test_delete_multiple_ids(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b", "c", "d"])
        result = store.delete_vectors(["a", "c"])
        assert result == {"delete_count": 2}
        assert store.count() == 2

    def test_delete_empty_input_is_noop(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b"])
        result = store.delete_vectors([])
        assert result == {"delete_count": 0}
        assert store.count() == 2

    def test_delete_nonexistent_id_is_zero(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b"])
        result = store.delete_vectors(["z"])
        assert result == {"delete_count": 0}
        assert store.count() == 2

    def test_duplicate_ids_in_request(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b"])
        result = store.delete_vectors(["a", "a"])
        assert result == {"delete_count": 1}
        assert store.count() == 1

    def test_metadata_cleaned_up(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(
            ids=["a", "b"],
            meta=[{"owner": "alice"}, {"owner": "bob"}],
        )
        store.delete_vectors(["a"])
        assert store.get_metadata("a") is None
        assert store.get_metadata("b") == {"owner": "bob"}

    def test_get_vector_returns_none_after_deletion(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b"])
        store.delete_vectors(["a"])
        assert store.get_vector("a") is None

    def test_search_excludes_deleted_vector(self):
        """search_similar must not return a deleted vector's ID."""
        faiss = pytest.importorskip("faiss")
        store = FAISSStore(dimension=3)
        vectors = np.array(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
        )
        store.add_vectors(vectors, ids=["a", "b", "c"])
        store.delete_vectors(["b"])
        query = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        results = store.search_similar(query, k=3)
        returned_ids = [r["id"] for r in results]
        assert "b" not in returned_ids

    def test_add_vectors_after_deletion(self):
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b", "c"])
        store.delete_vectors(["b"])
        vecs = np.array([[0.5, 0.5, 0.0]], dtype=np.float32)
        store.add_vectors(vecs, ids=["new"])
        assert store.count() == 3
        assert store.get_vector("new") is not None

    def test_save_load_after_deletion(self, tmp_path):
        """Deleted vectors do not reappear after save/load."""
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b", "c"])
        store.delete_vectors(["b"])

        path = tmp_path / "store.faiss"
        store.save_index(path)

        fresh = FAISSStore(dimension=3)
        fresh.load_index(path)

        assert fresh.count() == 2
        assert "b" not in fresh.index.vector_ids
        assert fresh.get_vector("b") is None

    def test_options_kwarg_is_accepted_and_ignored(self):
        """delete_vectors(**options) must not crash even with extra kwargs."""
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a"])
        result = store.delete_vectors(["a"], unused_option=True)
        assert result["delete_count"] == 1

    def test_hnsw_raises_not_implemented(self):
        """FAISSStore.delete_vectors on HNSW must propagate NotImplementedError."""
        faiss = pytest.importorskip("faiss")
        store = FAISSStore(dimension=4)
        store.create_index(index_type="hnsw", metric="L2")
        vecs = np.random.rand(5, 4).astype(np.float32)
        store.add_vectors(vecs, ids=["a", "b", "c", "d", "e"])
        with pytest.raises(NotImplementedError):
            store.delete_vectors(["a"])
        # Count must be unchanged
        assert store.count() == 5

    def test_ivf_raises_not_implemented(self):
        """FAISSStore.delete_vectors on IVF must raise NotImplementedError.

        IVF remove_ids preserves original labels rather than compacting them,
        which would desynchronize search labels from vector_ids.
        """
        faiss = pytest.importorskip("faiss")
        store = FAISSStore(dimension=4)
        # nlist=2 so we only need >= 2*39 = 78 training points
        store.create_index(index_type="ivf", metric="L2", nlist=2)
        train = np.random.rand(80, 4).astype(np.float32)
        store.index.index.train(train)
        store.add_vectors(train[:5], ids=["a", "b", "c", "d", "e"])
        with pytest.raises(NotImplementedError):
            store.delete_vectors(["a"])
        # State must be completely unchanged
        assert store.count() == 5

    def test_delete_with_loaded_index_auto_saves(self, tmp_path):
        """Deletion on a store loaded from disk auto-saves without explicit save_index."""
        _ = pytest.importorskip("faiss")
        # Create, populate, save
        store = _populated_store(ids=["a", "b", "c"])
        path = tmp_path / "store.faiss"
        store.save_index(path)

        # Load into a fresh store and delete
        loaded = FAISSStore(dimension=3)
        loaded.load_index(path)
        loaded.delete_vectors(["b"])

        # Reload without any additional save call — deletion must have persisted
        reloaded = FAISSStore(dimension=3)
        reloaded.load_index(path)
        assert reloaded.count() == 2
        assert "b" not in reloaded.index.vector_ids

    def test_default_id_no_collision_after_deletion(self):
        """Default vec_N IDs must not reuse a surviving ID after deletion."""
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["vec_0", "vec_1", "vec_2"])
        # Delete the middle one; len(vector_ids) drops to 2
        store.delete_vectors(["vec_1"])
        assert store.count() == 2

        # Add a new vector — without the monotonic counter, the default ID
        # would be vec_2 which already exists and would be silently skipped.
        new_vecs = np.random.rand(1, 3).astype(np.float32)
        returned_ids = store.add_vectors(new_vecs)
        # The returned ID must not be an existing one
        assert returned_ids[0] not in {"vec_0", "vec_2"}, (
            f"Default ID {returned_ids[0]} collides with a surviving ID"
        )
        # And the vector must actually have been inserted
        assert store.count() == 3

    def test_default_id_skip_past_explicit_id(self):
        """Blocker: default IDs must skip over explicit IDs already in the store.

        If a user inserts an explicit ``"vec_N"`` and then adds two vectors
        without IDs, the generator must skip ``"vec_N"`` rather than
        producing it and losing the second vector silently.
        """
        _ = pytest.importorskip("faiss")
        store = FAISSStore(dimension=3)

        # Explicit vec_1 first
        store.add_vectors(np.ones((1, 3), dtype=np.float32), ids=["vec_1"])

        # 2 default vectors — one would collide with vec_1 if not skipped
        store.add_vectors(np.ones((2, 3), dtype=np.float32))

        # 1 more default vector — must get a fresh ID, not re-generate a used one
        original_meta = {vid: {"original": vid} for vid in store.index.vector_ids}
        for vid, m in original_meta.items():
            store.index.metadata[vid] = m
        count_before = store.count()

        ret = store.add_vectors(
            np.ones((1, 3), dtype=np.float32), metadata=[{"new": True}]
        )
        new_id = ret[0]

        assert store.count() == count_before + 1, (
            f"Vector was silently skipped; count stayed {store.count()}"
        )
        assert new_id not in original_meta, (
            f"Generated ID {new_id!r} collides with an already-existing ID"
        )
        # Surviving IDs' metadata must not be overwritten
        for vid, m in original_meta.items():
            assert store.index.metadata.get(vid) == m, (
                f"Metadata for surviving {vid!r} was overwritten"
            )

    def test_stale_persisted_next_id_is_clamped_to_inferred_minimum(self, tmp_path):
        """Regression: a stale ``next_id`` in the sidecar must be clamped to
        at least ``max(vec_N)+1`` so that auto-save after deletion cannot
        propagate the stale value and cause future ID collisions.
        """
        import json as _json
        _ = pytest.importorskip("faiss")
        rng = np.random.default_rng(seed=3)
        store = FAISSStore(dimension=3)
        store.add_vectors(rng.random((5, 3)).astype(np.float32))
        # IDs are vec_0..vec_4, next_id=5
        path = tmp_path / "s.faiss"
        store.save_index(path)

        # Corrupt the sidecar: set next_id to a stale low value
        meta = _json.loads((tmp_path / "s.faiss.meta.json").read_text())
        meta["next_id"] = 2  # stale — vec_2, vec_3, vec_4 still exist
        (tmp_path / "s.faiss.meta.json").write_text(_json.dumps(meta))

        # Load and immediately delete one vector (auto-save fires)
        s2 = FAISSStore(dimension=3)
        s2.load_index(path)
        assert s2._next_id == 5, f"Stale next_id should be clamped to 5, got {s2._next_id}"
        s2.delete_vectors(["vec_3"])  # triggers auto-save

        # The sidecar must not carry the stale value forward
        persisted = _json.loads((tmp_path / "s.faiss.meta.json").read_text())
        assert persisted["next_id"] >= 5, (
            f"Auto-save propagated stale next_id={persisted['next_id']} (expected >= 5)"
        )

    def test_search_does_not_return_phantom_id_when_k_exceeds_ntotal(self):
        """Regression: when k > ntotal, FAISS returns -1 sentinel values.
        ``-1 < len(vector_ids)`` is always True in Python, so without an
        explicit non-negative guard ``-1`` maps to ``vector_ids[-1]``,
        making the last vector appear as a spurious extra result.
        """
        faiss = pytest.importorskip("faiss")
        store = FAISSStore(dimension=3)
        vecs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
        store.add_vectors(vecs, ids=["only_a", "only_b"])

        # Ask for 10 neighbors but only 2 exist
        results = store.search_similar(
            np.array([0.0, 1.0, 0.0], dtype=np.float32), k=10
        )
        returned_ids = [r["id"] for r in results]
        assert len(results) == 2, (
            f"Expected exactly 2 results, got {len(results)}: {returned_ids}"
        )
        assert returned_ids.count("only_b") == 1, (
            f"only_b appears {returned_ids.count('only_b')} time(s) — "
            "sentinel -1 is mapping to vector_ids[-1]"
        )

    def test_next_id_persisted_across_delete_save_reload(self, tmp_path):
        """Regression test for critical bug: delete → auto-save → reload → add.

        Without persisting ``next_id`` in the sidecar, ``load_index`` would
        set ``_next_id = ntotal`` (4 after one deletion from 5 vectors), which
        would generate ``"vec_4"`` as the next default ID.  That ID is still
        present in the surviving vector list, so the insertion would be
        silently skipped, the count would not increase, and the old vector's
        metadata would be overwritten by the new metadata.

        This test pins the full lifecycle so any regression is caught
        immediately.
        """
        _ = pytest.importorskip("faiss")
        rng = np.random.default_rng(seed=7)
        dim = 4

        # Step 1: create vec_0 .. vec_4, record their embeddings
        store1 = FAISSStore(dimension=dim)
        vecs = rng.random((5, dim)).astype(np.float32)
        store1.add_vectors(vecs)
        for vid in store1.index.vector_ids:
            store1.index.metadata[vid] = {"original": vid}
        path = tmp_path / "idx.faiss"
        store1.save_index(path)

        # Step 2: reload → delete vec_2 (auto-saves) → reload again
        store2 = FAISSStore(dimension=dim)
        store2.load_index(path)
        store2.delete_vectors(["vec_2"])   # ntotal drops to 4; auto-save triggered

        store3 = FAISSStore(dimension=dim)
        store3.load_index(path)

        # Step 3: add a new vector without an explicit ID
        new_vec = rng.random((1, dim)).astype(np.float32)
        count_before = store3.count()
        returned_ids = store3.add_vectors(new_vec, metadata=[{"new": True}])

        # The generated ID must not collide with any surviving ID
        surviving = set(store3.index.vector_ids[:count_before])
        new_id = returned_ids[0]
        assert new_id not in surviving, (
            f"Generated ID {new_id!r} collides with surviving ID "
            f"(surviving={sorted(surviving)})"
        )

        # The new vector must actually have been inserted
        assert store3.count() == count_before + 1, (
            f"Count did not increase: was {count_before}, still {store3.count()}"
        )

        # The new vector must be retrievable
        assert store3.get_vector(new_id) is not None, (
            f"New vector with ID {new_id!r} is not retrievable"
        )

        # The surviving vec_4's embedding must be unchanged
        original_vec4 = vecs[4]
        loaded_vec4 = store3.get_vector("vec_4")
        assert loaded_vec4 is not None
        np.testing.assert_allclose(loaded_vec4, original_vec4, atol=1e-5,
            err_msg="vec_4 embedding was corrupted by the new add")

        # The surviving vec_4's metadata must be unchanged
        assert store3.index.metadata.get("vec_4") == {"original": "vec_4"}, (
            f"vec_4 metadata was overwritten: {store3.index.metadata.get('vec_4')}"
        )

        # The new vector's metadata must be the new value
        assert store3.index.metadata.get(new_id) == {"new": True}

    def test_no_op_delete_does_not_rewrite_disk(self, tmp_path):
        """A deletion of only nonexistent IDs must not call FAISSIndex.save().

        Uses a spy on ``FAISSIndex.save`` rather than filesystem mtime so the
        assertion is deterministic regardless of filesystem timestamp resolution.
        """
        from unittest.mock import patch
        _ = pytest.importorskip("faiss")
        store = _populated_store(ids=["a", "b", "c"])
        path = tmp_path / "idx.faiss"
        store.save_index(path)

        loaded = FAISSStore(dimension=3)
        loaded.load_index(path)

        with patch.object(loaded.index, "save", wraps=loaded.index.save) as mock_save:
            loaded.delete_vectors(["z"])  # nonexistent → delete_count 0
            loaded.delete_vectors([])     # empty list  → delete_count 0
            assert mock_save.call_count == 0, (
                f"save() called {mock_save.call_count} time(s) for a no-op deletion"
            )

            # A real deletion must still trigger save()
            loaded.delete_vectors(["b"])
            assert mock_save.call_count == 1, (
                f"save() was not called after a real deletion (calls={mock_save.call_count})"
            )


# ---------------------------------------------------------------------------
# Facade delegation test
# ---------------------------------------------------------------------------


class TestFAISSFacadeDelegation:
    def test_vector_store_facade_delegates_to_faiss_store(self):
        """VectorStore(backend='faiss').delete_vectors() must call FAISSStore."""
        _ = pytest.importorskip("faiss")
        vs = VectorStore(backend="faiss", config={"dimension": 3})
        vecs = np.eye(3, dtype=np.float32)
        vs.store_vectors(list(vecs), metadata=[{}, {}, {}])
        # Count before
        assert vs._backend_store.count() == 3

        result = vs.delete_vectors(["vec_0"])

        assert result == {"delete_count": 1}
        assert vs._backend_store.count() == 2


# ---------------------------------------------------------------------------
# ErasureCoordinator integration tests
# ---------------------------------------------------------------------------


class TestFAISSErasureCoordinator:
    def _faiss_vector_store(self, dim: int = 3) -> VectorStore:
        _ = pytest.importorskip("faiss")
        vs = VectorStore(backend="faiss", config={"dimension": dim})
        vecs = np.eye(dim, dtype=np.float32)
        vs.store_vectors(list(vecs), metadata=[{}, {}, {}])
        return vs

    def test_erasure_reports_status_erased(self):
        vs = self._faiss_vector_store()
        # store_vectors assigns ids "vec_0", "vec_1", "vec_2"
        vector_ids = vs._backend_store.index.vector_ids
        coord = ErasureCoordinator(vector_store=vs)
        receipt = coord.erase_entity(vector_ids[0], vector_ids=[vector_ids[0]])
        assert receipt.stores["vectors"]["status"] == STATUS_ERASED

    def test_erasure_backend_name_is_faiss(self):
        vs = self._faiss_vector_store()
        coord = ErasureCoordinator(vector_store=vs)
        receipt = coord.erase_entity("vec_0", vector_ids=["vec_0"])
        assert receipt.stores["vectors"]["backend"] == "faiss"

    def test_erasure_receipt_is_complete_after_deletion(self):
        vs = self._faiss_vector_store()
        coord = ErasureCoordinator(vector_store=vs)
        receipt = coord.erase_entity("vec_0", vector_ids=["vec_0"])
        assert receipt.complete

    def test_erasure_hnsw_reports_unsupported(self):
        """HNSW deletion raises NotImplementedError; coordinator must report unsupported."""
        faiss = pytest.importorskip("faiss")
        vs = VectorStore(backend="faiss", config={"dimension": 4})
        vs._backend_store.create_index(index_type="hnsw", metric="L2")
        vecs = np.random.rand(5, 4).astype(np.float32)
        vs._backend_store.add_vectors(vecs, ids=["a", "b", "c", "d", "e"])
        coord = ErasureCoordinator(vector_store=vs)
        receipt = coord.erase_entity("a", vector_ids=["a"])
        assert receipt.stores["vectors"]["status"] == STATUS_UNSUPPORTED
        assert not receipt.complete

    def test_erasure_ivf_reports_unsupported(self):
        """IVF deletion raises NotImplementedError; coordinator must report unsupported."""
        faiss = pytest.importorskip("faiss")
        dim = 4
        vs = VectorStore(backend="faiss", config={"dimension": dim})
        vs._backend_store.create_index(index_type="ivf", metric="L2", nlist=2)
        train = np.random.rand(80, dim).astype(np.float32)
        vs._backend_store.index.index.train(train)
        vs._backend_store.add_vectors(train[:5], ids=["a", "b", "c", "d", "e"])
        coord = ErasureCoordinator(vector_store=vs)
        receipt = coord.erase_entity("a", vector_ids=["a"])
        assert receipt.stores["vectors"]["status"] == STATUS_UNSUPPORTED
        assert not receipt.complete
