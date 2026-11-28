"""Filtered hybrid search must fill top k from the whole offline corpus."""

import numpy as np
import pytest

from semantica.vector_store import HybridSearch, MetadataFilter, VectorStore


@pytest.fixture(params=["inmemory", "faiss", "sqlite", "qdrant"])
def hybrid_corpus(request, tmp_path, monkeypatch):
    backend = request.param
    if backend != "inmemory":
        pytest.importorskip(
            {"faiss": "faiss", "sqlite": "sqlite_vec", "qdrant": "qdrant_client"}[
                backend
            ]
        )
    monkeypatch.setattr(
        "semantica.vector_store.vector_store.EmbeddingGenerator", lambda: None
    )
    config = {"dimension": 2, "db_path": str(tmp_path / "vectors.db")}
    store = VectorStore(backend=backend, config=config)
    if backend == "qdrant":
        from qdrant_client import QdrantClient

        store._backend_store.client = QdrantClient(":memory:")

    angles = np.linspace(0.02, 1.4, 24)
    vectors = [np.array([np.cos(a), np.sin(a)], dtype=np.float32) for a in angles]
    metadata = [
        {
            "category": "kept" if i >= 20 else "other",
            "count": 0 if i >= 20 else 1,
            "entities": ["org", "chosen"] if i >= 20 else ["org"],
        }
        for i in range(len(vectors))
    ]
    ids = store.store_vectors(vectors, metadata)
    try:
        yield store, vectors, metadata, ids
    finally:
        if backend == "sqlite":
            store._backend_store.close()
        elif backend == "qdrant":
            store._backend_store.client.close()


@pytest.mark.parametrize("k", [1, 3, 50])
@pytest.mark.parametrize(
    "condition",
    [
        ("category", "eq", "kept"),
        ("count", "eq", 0),
        ("entities", "contains", "chosen"),
    ],
)
def test_filtered_hybrid_search_matches_full_corpus(hybrid_corpus, k, condition):
    store, vectors, metadata, ids = hybrid_corpus
    query = np.array([1.0, 0.0], dtype=np.float32)
    scores = np.array([np.dot(query, v) / np.linalg.norm(v) for v in vectors])
    expected = [ids[i] for i in np.argsort(-scores) if i >= 20][:k]

    results = HybridSearch(vector_store=store).search(
        query, k=k, metadata_filter=MetadataFilter().add_condition(*condition)
    )

    assert [r["id"] for r in results] == expected
    assert [r["score"] for r in results] == sorted(
        (r["score"] for r in results), reverse=True
    )
    assert [r["metadata"] for r in results] == [
        metadata[ids.index(i)] for i in expected
    ]


def test_filtered_hybrid_search_exhausts_corpus(hybrid_corpus):
    store, _, _, _ = hybrid_corpus
    results = HybridSearch(vector_store=store).search(
        np.array([1.0, 0.0], dtype=np.float32),
        k=1,
        metadata_filter=MetadataFilter().eq("category", "absent"),
    )

    assert results == []


class _FullWindowStore:
    """Backend stand-in that always fills the window with non-matching rows."""

    backend = "faiss"

    def __init__(self):
        self.requested = []

    def search_vectors(self, query_vector, k=10, **options):
        self.requested.append(k)
        return [
            {"id": f"v{i}", "score": 0.5, "metadata": {"category": "other"}}
            for i in range(k)
        ]


def test_filtered_hybrid_search_stops_widening_at_cap():
    store = _FullWindowStore()
    results = HybridSearch(vector_store=store).search(
        np.array([1.0, 0.0], dtype=np.float32),
        k=10,
        metadata_filter=MetadataFilter().eq("category", "kept"),
    )

    assert results == []
    assert store.requested[0] == 40
    assert store.requested[-1] == 10_000
    assert max(store.requested) == 10_000
