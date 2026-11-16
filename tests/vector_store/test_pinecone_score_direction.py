"""Metric-aware Pinecone scores using the existing fake-client pattern."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from semantica.vector_store.pinecone_store import (
    PineconeClient,
    PineconeIndex,
    PineconeStore,
)


@pytest.fixture(autouse=True)
def pinecone_available(monkeypatch):
    monkeypatch.setattr(
        "semantica.vector_store.pinecone_store.PINECONE_AVAILABLE", True
    )


@pytest.mark.parametrize("create", [False, True])
@pytest.mark.parametrize("description_type", [dict, SimpleNamespace])
@pytest.mark.parametrize(
    "metric,native_metric,raw_scores,expected",
    [
        ("euclidean", "euclidean", [0.0, 1.0, 3.0], [1.0, 0.5, 0.25]),
        ("cosine", "cosine", [1.0, 0.0, -1.0], [0.75, 0.5, 0.25]),
        ("dot", "dotproduct", [50.0, 2.0, -1.0], [101 / 102, 5 / 6, 0.25]),
    ],
)
def test_scores_follow_created_or_attached_metric(
    create, description_type, metric, native_metric, raw_scores, expected
):
    client = MagicMock()
    index = client.Index.return_value
    client.describe_index.return_value = description_type(metric=native_metric)
    index.query.return_value = SimpleNamespace(
        matches=[
            SimpleNamespace(id=str(i), score=score, metadata={})
            for i, score in enumerate(raw_scores)
        ]
    )
    store = PineconeStore(api_key="test-key", dimension=2)
    store.client = PineconeClient(client)
    if create:
        store.create_index("vectors", dimension=2, metric=metric)
    else:
        store.get_index("vectors")

    results = store.search_vectors(np.array([1.0, 0.0]), k=3)
    scores = [result["score"] for result in results]
    assert [result["id"] for result in results] == ["0", "1", "2"]
    assert scores == pytest.approx(expected)
    assert scores == sorted(scores, reverse=True)
    if create:
        assert client.create_index.call_args.kwargs["metric"] == native_metric


def test_unavailable_metric_keeps_existing_scores():
    client = MagicMock()
    client.describe_index.side_effect = RuntimeError("description unavailable")
    index = client.Index.return_value
    index.query.return_value = SimpleNamespace(
        matches=[SimpleNamespace(id="a", score=2.0, metadata={})]
    )
    store = PineconeStore(api_key="test-key", dimension=2)
    store.client = PineconeClient(client)
    store.get_index("vectors")

    results = store.search_vectors(np.array([1.0, 0.0]))
    assert results[0]["score"] == pytest.approx(5 / 6)


def test_direct_index_without_metric_keeps_existing_scores():
    index = MagicMock()
    index.query.return_value = SimpleNamespace(
        matches=[SimpleNamespace(id="a", score=2.0, metadata={})]
    )
    results = PineconeIndex(index).search_vectors([1.0, 0.0])
    assert results[0]["score"] == pytest.approx(5 / 6)
