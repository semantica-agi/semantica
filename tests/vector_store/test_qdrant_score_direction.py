"""Metric-aware Qdrant scores against the real local backend."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from semantica.vector_store.qdrant_store import QdrantCollection, QdrantStore

qdrant = pytest.importorskip("qdrant_client")
models = pytest.importorskip("qdrant_client.models")


@pytest.mark.parametrize("reopen", [False, True])
@pytest.mark.parametrize(
    "metric,vectors,expected",
    [
        ("Euclidean", [[1.0, 0.0], [2.0, 0.0], [4.0, 0.0]], [1.0, 0.5, 0.25]),
        ("Cosine", [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]], [0.75, 0.5, 0.25]),
        ("Dot", [[50.0, 0.0], [2.0, 0.0], [-1.0, 0.0]], [101 / 102, 5 / 6, 0.25]),
    ],
)
def test_scores_follow_created_or_reopened_metric(
    tmp_path, metric, vectors, expected, reopen
):
    path = str(tmp_path / "qdrant")
    store = QdrantStore()
    store.client = qdrant.QdrantClient(path=path)
    try:
        store.create_collection("vectors", vector_size=2, distance=metric)
        store.insert_vectors(vectors, ids=[1, 2, 3])
        if reopen:
            store.client.close()
            store = QdrantStore()
            store.client = qdrant.QdrantClient(path=path)
            store.get_collection("vectors")

        results = store.search_vectors(np.array([1.0, 0.0]), limit=10)
        assert [result["id"] for result in results] == [1, 2, 3]
        scores = [result["score"] for result in results]
        assert scores == pytest.approx(expected)
        assert scores == sorted(scores, reverse=True)
    finally:
        store.client.close()


@pytest.mark.parametrize(
    "distance", [models.Distance.EUCLID, models.Distance.MANHATTAN]
)
@pytest.mark.parametrize("named", [False, True])
def test_direct_wrapper_reads_external_collection_metric(distance, named):
    client = qdrant.QdrantClient(":memory:")
    try:
        config = models.VectorParams(size=2, distance=distance)
        if named:
            config = {
                "distance": config,
                "dot": models.VectorParams(size=2, distance=models.Distance.DOT),
            }
        client.create_collection("external", vectors_config=config)
        points = []
        for i, dot in enumerate([50.0, 2.0, -1.0], start=1):
            vector = [float(i - 1), 0.0]
            if named:
                vector = {"distance": vector, "dot": [dot, 0.0]}
            points.append(models.PointStruct(id=i, vector=vector))
        client.upsert("external", points=points)
        collection = QdrantCollection(client, "external")
        options = {"using": "distance"} if named else {}
        results = collection.search_points(np.array([0.0, 0.0]), limit=3, **options)
        scores = [result["score"] for result in results]
        assert [result["id"] for result in results] == [1, 2, 3]
        assert scores == pytest.approx([1.0, 0.5, 1 / 3])
        assert scores == sorted(scores, reverse=True)
        if named:
            results = collection.search_points(np.array([1.0, 0.0]), using="dot")
            assert [result["id"] for result in results] == [1, 2, 3]
            assert [result["score"] for result in results] == pytest.approx(
                [101 / 102, 5 / 6, 0.25]
            )
    finally:
        client.close()


def test_unavailable_collection_metric_keeps_existing_scores():
    client = MagicMock()
    client.get_collection.side_effect = RuntimeError("description unavailable")
    client.query_points.return_value = SimpleNamespace(
        points=[SimpleNamespace(id=1, score=2.0, payload={})]
    )
    results = QdrantCollection(client, "vectors").search_points(np.array([1.0, 0.0]))
    assert results[0]["score"] == pytest.approx(5 / 6)
