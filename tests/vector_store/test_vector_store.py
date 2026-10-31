import json
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from semantica.vector_store.vector_store import VectorStore

class TestVectorStore(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_tracker = MagicMock()
        
        self.logger_patcher = patch('semantica.vector_store.vector_store.get_logger', return_value=self.mock_logger)
        self.tracker_patcher = patch('semantica.vector_store.vector_store.get_progress_tracker', return_value=self.mock_tracker)
        self.indexer_patcher = patch('semantica.vector_store.vector_store.VectorIndexer')
        self.retriever_patcher = patch('semantica.vector_store.vector_store.VectorRetriever')
        
        self.logger_patcher.start()
        self.tracker_patcher.start()
        self.MockVectorIndexer = self.indexer_patcher.start()
        self.MockVectorRetriever = self.retriever_patcher.start()

    def tearDown(self):
        self.logger_patcher.stop()
        self.tracker_patcher.stop()
        self.indexer_patcher.stop()
        self.retriever_patcher.stop()

    def test_initialization(self):
        store = VectorStore(backend="inmemory", dimension=128)
        self.assertEqual(store.dimension, 128)
        self.MockVectorIndexer.assert_called_once()
        self.MockVectorRetriever.assert_called_once()

    def test_store_vectors(self):
        store = VectorStore(backend="inmemory")
        vectors = [np.array([0.1, 0.2]), np.array([0.3, 0.4])]
        metadata = [{"id": "1"}, {"id": "2"}]

        ids = store.store_vectors(vectors, metadata)

        self.assertEqual(len(ids), 2)
        self.assertEqual(len(store.vectors), 2)
        self.assertEqual(len(store.metadata), 2)
        store.indexer.create_index.assert_called_once()

    def test_search_vectors(self):
        store = VectorStore(backend="inmemory")
        # Pre-populate store (though search uses retriever which we mock)
        store.vectors = {"v1": np.array([0.1]), "v2": np.array([0.2])}

        query_vector = np.array([0.15])
        expected_results = [{"id": "v1", "score": 0.9}]
        store.retriever.search_similar.return_value = expected_results

        results = store.search_vectors(query_vector, k=5)

        self.assertEqual(results, expected_results)
        store.retriever.search_similar.assert_called_once()

    def test_update_vectors(self):
        store = VectorStore(backend="inmemory")
        store.vectors = {"v1": np.array([0.1])}

        new_vector = np.array([0.9])
        store.update_vectors(["v1"], [new_vector])

        np.testing.assert_array_equal(store.vectors["v1"], new_vector)
        store.indexer.create_index.assert_called()

    def test_delete_vectors(self):
        store = VectorStore(backend="inmemory")
        store.vectors = {"v1": np.array([0.1]), "v2": np.array([0.2])}
        store.metadata = {"v1": {}, "v2": {}}

        store.delete_vectors(["v1"])

        self.assertNotIn("v1", store.vectors)
        self.assertIn("v2", store.vectors)
        store.indexer.create_index.assert_called()

    def test_get_vector_and_metadata(self):
        store = VectorStore(backend="inmemory")
        vec = np.array([0.1])
        meta = {"info": "test"}
        store.vectors = {"v1": vec}
        store.metadata = {"v1": meta}
        
        self.assertTrue(np.array_equal(store.get_vector("v1"), vec))
        self.assertEqual(store.get_metadata("v1"), meta)
        self.assertIsNone(store.get_vector("nonexistent"))

    def test_store_vectors_metadata_forwarding(self):
        """Test that metadata is correctly forwarded to backends that support it."""
        store = VectorStore(backend="inmemory")
        
        class MockBackendWithMetadata:
            def __init__(self):
                self.received_metadata = None
                
            def add_vectors(self, vectors, ids=None, metadata=None, **options):
                self.received_metadata = metadata
                return ["vec1"]
                
        mock_backend = MockBackendWithMetadata()
        store._backend_store = mock_backend
        
        vectors = [np.array([0.1, 0.2])]
        metadata = [{"id": "1"}]
        
        store.store_vectors(vectors, metadata=metadata)
        
        self.assertEqual(mock_backend.received_metadata, metadata)

    def test_store_vectors_strict_backend(self):
        """Test that metadata is dropped for strict backends without TypeError."""
        store = VectorStore(backend="inmemory")
        
        class MockBackendStrict:
            def __init__(self):
                self.called = False
                
            def add_vectors(self, vectors):
                self.called = True
                return ["vec1"]
                
        mock_backend = MockBackendStrict()
        store._backend_store = mock_backend
        
        vectors = [np.array([0.1, 0.2])]
        metadata = [{"id": "1"}]
        
        # This should not raise TypeError since metadata is dropped
        store.store_vectors(vectors, metadata=metadata)
        
        self.assertTrue(mock_backend.called)

    def test_filter_by_metadata_inmemory(self):
        """Test _filter_by_metadata on inmemory backend."""
        store = VectorStore(backend="inmemory")
        store.metadata = {
            "v1": {"category": "finance", "amount": 100, "tags": ["a", "b"]},
            "v2": {"category": "finance", "amount": 500, "tags": ["b", "c"]},
            "v3": {"category": "tech", "amount": 200, "tags": ["c"]},
        }
        store.vectors = {
            "v1": np.array([0.1]),
            "v2": np.array([0.2]),
            "v3": np.array([0.3]),
        }

        # Exact filter
        results = store._filter_by_metadata({"category": "finance"}, limit=10)
        self.assertEqual(len(results), 2)
        res_ids = {r["id"] for r in results}
        self.assertEqual(res_ids, {"v1", "v2"})

        # Range filter
        results = store._filter_by_metadata({"amount": {"min": 150}}, limit=10)
        self.assertEqual(len(results), 2)
        res_ids = {r["id"] for r in results}
        self.assertEqual(res_ids, {"v2", "v3"})

        # List intersection filter
        results = store._filter_by_metadata({"tags": ["a"]}, limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "v1")

    def test_filter_by_metadata_persistent_backend_delegation(self):
        """Test that persistent backend delegates filter_by_metadata without AttributeError."""
        store = VectorStore(backend="inmemory")
        # Simulate persistent backend by deleting self.metadata attribute if any
        if hasattr(store, "metadata"):
            delattr(store, "metadata")

        mock_backend = MagicMock()
        mock_backend.filter_by_metadata.return_value = [
            {"id": "p1", "metadata": {"category": "test"}, "vector": np.array([0.5])}
        ]
        store._backend_store = mock_backend
        store.backend = "faiss"

        # Should NOT raise AttributeError: 'VectorStore' object has no attribute 'metadata'
        results = store._filter_by_metadata({"category": "test"}, limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "p1")
        mock_backend.filter_by_metadata.assert_called_once_with(filters={"category": "test"}, limit=5)

    def test_filter_by_metadata_backend_not_implemented(self):
        """Test that missing filter_by_metadata method raises NotImplementedError."""
        store = VectorStore(backend="inmemory")
        if hasattr(store, "metadata"):
            delattr(store, "metadata")

        store.backend = "unknown"
        store._backend_store = object()

        with self.assertRaises(NotImplementedError):
            store._filter_by_metadata({"key": "val"}, limit=10)

    def test_save_load_roundtrip_numpy_vectors(self):
        """save()/load() must handle numpy float32 vectors without raising.

        Regression test: json.dump() rejects numpy scalar types, so a naive
        `list(v)` conversion (which yields np.float32 elements, not native
        floats) raises TypeError. `v.tolist()` converts recursively to
        native Python floats and must be used instead.
        """
        store = VectorStore(backend="inmemory", dimension=3)
        store.vectors = {"v1": np.array([0.1, 0.2, 0.3], dtype=np.float32)}
        store.metadata = {"v1": {"id": "1"}}

        tmpdir = tempfile.mkdtemp()
        try:
            store.save(tmpdir)  # must not raise TypeError

            # The JSON file itself must be valid and free of numpy types.
            with open(f"{tmpdir}/store_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertTrue(all(isinstance(x, float) for x in data["vectors"]["v1"]))

            loaded = VectorStore(backend="inmemory", dimension=3)
            loaded.load(tmpdir)
            np.testing.assert_allclose(
                loaded.vectors["v1"], [0.1, 0.2, 0.3], rtol=1e-6
            )
            self.assertEqual(loaded.metadata["v1"], {"id": "1"})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_rejects_legacy_pickle(self):
        """load() must refuse legacy .pkl stores rather than deserializing them."""
        store = VectorStore(backend="inmemory", dimension=3)
        tmpdir = tempfile.mkdtemp()
        try:
            with open(f"{tmpdir}/store_data.pkl", "wb") as f:
                f.write(b"not a real pickle, just needs to exist")
            with self.assertRaises(RuntimeError):
                store.load(tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCreateIndexFunction(unittest.TestCase):
    """create_index() forwards vector_store_config's defaults into VectorIndexer,
    which already receives backend/dimension as explicit args. Regression for the
    'got multiple values for keyword argument dimension' crash on the default
    (unmocked) config, hit by e.g. `semantica embed index`."""

    def test_create_index_with_default_config(self):
        from semantica.vector_store.methods import create_index

        vectors = [np.array([0.1, 0.2, 0.3]), np.array([0.4, 0.5, 0.6])]
        index = create_index(vectors, ids=["a", "b"])
        self.assertIsNotNone(index)


if __name__ == '__main__':
    unittest.main()

def test_backend_mirroring_and_save(tmp_path):
    """
    Test that backend-backed vector stores maintain a synchronized in-memory mirror
    for serialization by save(). This covers #1698 regression.
    """
    pytest.importorskip("sqlite_vec")

    import numpy as np
    from semantica.vector_store import VectorStore
    import os

    # We use sqlite since it doesn't require an external service.
    # The stored vector is 2-d, so the backend table must be too.
    vs = VectorStore(
        backend="sqlite",
        config={"db_path": str(tmp_path / "test1.db"), "dimension": 2},
    )
    
    vecs = [np.array([0.1, 0.2], dtype=np.float32)]
    meta = [{"test": "true"}]
    
    # store_vectors should populate mirror
    ids = vs.store_vectors(vecs, metadata=meta)
    assert len(ids) == 1
    assert ids[0] in vs.vectors
    assert ids[0] in vs.metadata
    
    # save() should persist mirror
    save_dir = str(tmp_path / "vs_save")
    vs.save(save_dir)
    assert os.path.exists(os.path.join(save_dir, "store_data.json"))
    
    # load() should restore mirror
    vs2 = VectorStore(backend="sqlite", config={"db_path": str(tmp_path / "test2.db")})
    vs2.load(save_dir)
    assert ids[0] in vs2.vectors
    assert ids[0] in vs2.metadata
    assert np.array_equal(vs2.vectors[ids[0]], vecs[0])
    
    # delete_vectors should update mirror
    vs.delete_vectors(ids)
    assert ids[0] not in vs.vectors
    assert ids[0] not in vs.metadata


def test_update_vectors_syncs_backend_mirror_before_save(tmp_path):
    """update_vectors() on a backend store must refresh the facade mirror.

    save() serialises self.vectors / self.metadata, so a stale mirror makes it
    persist the pre-update values (#1833).
    """
    import os

    class FakeBackend:
        def add(self, vectors, metadata, **options):
            return [f"id{i}" for i in range(len(vectors))]

        def update(self, ids, vectors, metadata=None, **options):
            return True

    vs = VectorStore(backend="inmemory", dimension=2)
    vs._backend_store = FakeBackend()

    ids = vs.store_vectors(
        [np.array([0.1, 0.2], dtype=np.float32)], metadata=[{"label": "original"}]
    )

    new_vec = np.array([0.9, 0.9], dtype=np.float32)
    assert vs.update_vectors(ids, [new_vec], metadata=[{"label": "updated"}]) is True

    assert np.array_equal(vs.vectors[ids[0]], new_vec)
    assert vs.metadata[ids[0]] == {"label": "updated"}

    vs.save(str(tmp_path))
    with open(os.path.join(str(tmp_path), "store_data.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["vectors"][ids[0]] == pytest.approx([0.9, 0.9])
    assert saved["metadata"][ids[0]] == {"label": "updated"}


def test_update_vectors_leaves_mirror_when_backend_rejects(tmp_path):
    """If the backend update returns False, the mirror must keep the originals."""
    import os

    class RejectingBackend:
        def add(self, vectors, metadata, **options):
            return [f"id{i}" for i in range(len(vectors))]

        def update(self, ids, vectors, metadata=None, **options):
            return False

    vs = VectorStore(backend="inmemory", dimension=2)
    vs._backend_store = RejectingBackend()

    original = np.array([0.1, 0.2], dtype=np.float32)
    ids = vs.store_vectors([original], metadata=[{"label": "original"}])

    new_vec = np.array([0.9, 0.9], dtype=np.float32)
    assert vs.update_vectors(ids, [new_vec], metadata=[{"label": "updated"}]) is False

    assert np.array_equal(vs.vectors[ids[0]], original)
    assert vs.metadata[ids[0]] == {"label": "original"}

    vs.save(str(tmp_path))
    with open(os.path.join(str(tmp_path), "store_data.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["vectors"][ids[0]] == pytest.approx([0.1, 0.2])
    assert saved["metadata"][ids[0]] == {"label": "original"}


def test_update_vectors_does_not_mirror_unconfirmed_ids(tmp_path):
    """A zero-row backend update must not rewrite the facade mirror (#1909)."""
    import os

    class ReportingBackend:
        def add(self, vectors, metadata, **options):
            return [f"id{i}" for i in range(len(vectors))]

        def update(self, ids, vectors, metadata=None, **options):
            return []

    vs = VectorStore(backend="inmemory", dimension=2)
    vs._backend_store = ReportingBackend()

    original = np.array([0.1, 0.2], dtype=np.float32)
    ids = vs.store_vectors([original], metadata=[{"label": "original"}])
    new_vec = np.array([0.9, 0.9], dtype=np.float32)

    assert vs.update_vectors(ids, [new_vec], metadata=[{"label": "updated"}]) is True
    assert np.array_equal(vs.vectors[ids[0]], original)
    assert vs.metadata[ids[0]] == {"label": "original"}

    vs.save(str(tmp_path))
    with open(os.path.join(str(tmp_path), "store_data.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["vectors"][ids[0]] == pytest.approx([0.1, 0.2])
    assert saved["metadata"][ids[0]] == {"label": "original"}


def test_update_vectors_mirrors_only_confirmed_ids(tmp_path):
    """A mixed batch refreshes only the ids the backend confirmed."""
    import os

    class ReportingBackend:
        def add(self, vectors, metadata, **options):
            return [f"id{i}" for i in range(len(vectors))]

        def update(self, ids, vectors, metadata=None, **options):
            return [ids[0]]

    vs = VectorStore(backend="inmemory", dimension=2)
    vs._backend_store = ReportingBackend()

    original_kept = np.array([0.3, 0.4], dtype=np.float32)
    ids = vs.store_vectors(
        [np.array([0.1, 0.2], dtype=np.float32), original_kept],
        metadata=[{"label": "first"}, {"label": "second"}],
    )
    new_first = np.array([0.9, 0.9], dtype=np.float32)
    new_second = np.array([0.8, 0.8], dtype=np.float32)

    assert (
        vs.update_vectors(
            ids,
            [new_first, new_second],
            metadata=[{"label": "first-new"}, {"label": "second-new"}],
        )
        is True
    )
    assert np.array_equal(vs.vectors[ids[0]], new_first)
    assert vs.metadata[ids[0]] == {"label": "first-new"}
    assert np.array_equal(vs.vectors[ids[1]], original_kept)
    assert vs.metadata[ids[1]] == {"label": "second"}

    vs.save(str(tmp_path))
    with open(os.path.join(str(tmp_path), "store_data.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["vectors"][ids[0]] == pytest.approx([0.9, 0.9])
    assert saved["metadata"][ids[0]] == {"label": "first-new"}
    assert saved["vectors"][ids[1]] == pytest.approx([0.3, 0.4])
    assert saved["metadata"][ids[1]] == {"label": "second"}


def test_update_vectors_vector_only_respects_confirmed_ids():
    """A vector-only update still leaves unconfirmed metadata alone."""

    class ReportingBackend:
        def add(self, vectors, metadata, **options):
            return [f"id{i}" for i in range(len(vectors))]

        def update(self, ids, vectors, metadata=None, **options):
            return [ids[0]]

    vs = VectorStore(backend="inmemory", dimension=2)
    vs._backend_store = ReportingBackend()

    original_kept = np.array([0.3, 0.4], dtype=np.float32)
    ids = vs.store_vectors(
        [np.array([0.1, 0.2], dtype=np.float32), original_kept],
        metadata=[{"label": "first"}, {"label": "second"}],
    )
    new_first = np.array([0.9, 0.9], dtype=np.float32)

    assert (
        vs.update_vectors(
            ids,
            [new_first, np.array([0.8, 0.8], dtype=np.float32)],
        )
        is True
    )
    assert np.array_equal(vs.vectors[ids[0]], new_first)
    assert vs.metadata[ids[0]] == {"label": "first"}
    assert np.array_equal(vs.vectors[ids[1]], original_kept)
    assert vs.metadata[ids[1]] == {"label": "second"}


def test_sqlite_update_vectors_skips_row_deleted_in_the_backend(tmp_path):
    """An id removed in SQLite stays unchanged in the mirror and in save()."""
    pytest.importorskip("sqlite_vec")
    import os

    vs = VectorStore(
        backend="sqlite",
        config={"db_path": str(tmp_path / "vectors.db"), "dimension": 2},
    )
    original = np.array([0.1, 0.2], dtype=np.float32)
    kept = np.array([0.3, 0.4], dtype=np.float32)
    ids = vs.store_vectors(
        [original, kept],
        metadata=[{"label": "gone"}, {"label": "kept"}],
    )
    assert vs._backend_store.delete([ids[0]]) is True

    new_gone = np.array([0.9, 0.9], dtype=np.float32)
    new_kept = np.array([0.8, 0.8], dtype=np.float32)
    assert (
        vs.update_vectors(
            ids,
            [new_gone, new_kept],
            metadata=[{"label": "new-gone"}, {"label": "new-kept"}],
        )
        is True
    )

    assert np.array_equal(vs.vectors[ids[0]], original)
    assert vs.metadata[ids[0]] == {"label": "gone"}
    assert np.array_equal(vs.vectors[ids[1]], new_kept)
    assert vs.metadata[ids[1]] == {"label": "new-kept"}
    assert [row["id"] for row in vs._backend_store.get(ids)] == [ids[1]]

    save_dir = str(tmp_path / "saved")
    vs.save(save_dir)
    with open(os.path.join(save_dir, "store_data.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["vectors"][ids[0]] == pytest.approx([0.1, 0.2])
    assert saved["metadata"][ids[0]] == {"label": "gone"}
    assert saved["vectors"][ids[1]] == pytest.approx([0.8, 0.8])
    assert saved["metadata"][ids[1]] == {"label": "new-kept"}
