"""Tests for QdrantCollection.search_points and QdrantStore.get_stats.

These cover the qdrant-client >=1.16.0 compatibility fixes:

1. search_points() must call client.query_points() (not the removed .search()),
   read ScoredPoints from response.points, and map them to the documented
   Semantica result shape.

2. get_stats() must not access vectors_count unconditionally; when the field
   is absent (qdrant-client >=1.16), it falls back to points_count for
   single-vector collections, and to None for named/multi-vector collections
   where the per-point vector count is unknown.

All tests drive the real implementation against a MagicMock client, following
the established pattern in test_qdrant_store.py.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantica.utils.exceptions import ProcessingError
from semantica.vector_store.qdrant_store import QdrantCollection, QdrantStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scored_point(point_id, score, payload=None):
    """Build a stand-in for a qdrant_client ScoredPoint."""
    sp = MagicMock()
    sp.id = point_id
    sp.score = score
    sp.payload = payload
    return sp


def _query_response(*scored_points):
    """Build a stand-in for a qdrant_client QueryResponse."""
    qr = MagicMock()
    qr.points = list(scored_points)
    return qr


def _collection_with_query_response(*scored_points):
    """QdrantCollection whose client.query_points() returns the given points."""
    client = MagicMock()
    client.query_points.return_value = _query_response(*scored_points)
    return QdrantCollection(client, "test_collection")


# ---------------------------------------------------------------------------
# QdrantCollection.search_points — API call
# ---------------------------------------------------------------------------

@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_calls_query_points_not_search():
    """search_points() must call .query_points(), NOT the removed .search()."""
    collection = _collection_with_query_response()
    query = np.array([0.1, 0.2, 0.3, 0.4])

    collection.search_points(query, limit=5)

    collection.client.query_points.assert_called_once()
    collection.client.search.assert_not_called()


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_passes_correct_arguments():
    """query_points() must receive collection_name, query list, limit, and payload flag."""
    collection = _collection_with_query_response()
    query = np.array([0.1, 0.2, 0.3, 0.4])

    collection.search_points(query, limit=7)

    _, kwargs = collection.client.query_points.call_args
    assert kwargs["collection_name"] == "test_collection"
    assert kwargs["query"] == [0.1, 0.2, 0.3, 0.4]
    assert kwargs["limit"] == 7
    assert kwargs["with_payload"] is True
    assert kwargs["with_vectors"] is False


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_passes_query_filter_through():
    """The query_filter argument must be forwarded verbatim to query_points()."""
    collection = _collection_with_query_response()
    mock_filter = MagicMock()
    query = np.array([0.5, 0.6])

    collection.search_points(query, limit=3, query_filter=mock_filter)

    _, kwargs = collection.client.query_points.call_args
    assert kwargs["query_filter"] is mock_filter


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_passes_none_filter_when_unfiltered():
    """query_filter=None must be passed through (not omitted) so the server
    returns all matching vectors rather than raising a missing-argument error."""
    collection = _collection_with_query_response()
    query = np.array([0.1, 0.2])

    collection.search_points(query, limit=5, query_filter=None)

    _, kwargs = collection.client.query_points.call_args
    assert kwargs["query_filter"] is None


# ---------------------------------------------------------------------------
# QdrantCollection.search_points — result shape
# ---------------------------------------------------------------------------

@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_result_shape():
    """Each result dict must contain id, score, metadata, vector, distance."""
    sp = _scored_point(42, 0.8, payload={"tag": "ml"})
    collection = _collection_with_query_response(sp)
    query = np.array([0.1, 0.2, 0.3])

    results = collection.search_points(query, limit=1)

    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == {"id", "score", "metadata", "vector", "distance"}


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_maps_id_and_payload():
    """id and metadata must come from ScoredPoint.id and ScoredPoint.payload."""
    sp = _scored_point(99, 0.5, payload={"source": "wiki", "year": 2024})
    collection = _collection_with_query_response(sp)

    results = collection.search_points(np.array([0.1, 0.2]), limit=1)

    assert results[0]["id"] == 99
    assert results[0]["metadata"] == {"source": "wiki", "year": 2024}


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_null_payload_becomes_empty_dict():
    """A ScoredPoint with payload=None must produce metadata={}."""
    sp = _scored_point(7, 0.9, payload=None)
    collection = _collection_with_query_response(sp)

    results = collection.search_points(np.array([0.1, 0.2]), limit=1)

    assert results[0]["metadata"] == {}


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_vector_and_distance_are_none():
    """vector and distance fields must always be None (vectors are not fetched)."""
    sp = _scored_point(1, 0.7, payload={})
    collection = _collection_with_query_response(sp)

    results = collection.search_points(np.array([0.1, 0.2]), limit=1)

    assert results[0]["vector"] is None
    assert results[0]["distance"] is None


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_score_normalization_midrange():
    """Score=0 must map to exactly 0.5 under the normalization formula."""
    sp = _scored_point(1, 0.0)
    collection = _collection_with_query_response(sp)

    results = collection.search_points(np.array([0.1, 0.2]), limit=1)

    assert results[0]["score"] == pytest.approx(0.5)


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_score_normalization_positive():
    """Positive raw scores must map to (0.5, 1.0) under the normalization formula."""
    sp = _scored_point(1, 1.0)
    collection = _collection_with_query_response(sp)

    results = collection.search_points(np.array([0.1, 0.2]), limit=1)

    # (1.0/(1+1.0) + 1.0) / 2.0 = (0.5 + 1.0) / 2.0 = 0.75
    assert results[0]["score"] == pytest.approx(0.75)


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_score_normalization_negative():
    """Negative raw scores must map to (0.0, 0.5) under the normalization formula."""
    sp = _scored_point(1, -1.0)
    collection = _collection_with_query_response(sp)

    results = collection.search_points(np.array([0.1, 0.2]), limit=1)

    # (-1.0/(1+1.0) + 1.0) / 2.0 = (−0.5 + 1.0) / 2.0 = 0.25
    assert results[0]["score"] == pytest.approx(0.25)


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_multiple_results_preserve_order():
    """All ScoredPoints in response.points must appear in the output, in order."""
    points = [_scored_point(i, 1.0 - i * 0.1) for i in range(5)]
    collection = _collection_with_query_response(*points)

    results = collection.search_points(np.array([0.1, 0.2]), limit=5)

    assert len(results) == 5
    assert [r["id"] for r in results] == [0, 1, 2, 3, 4]


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_empty_response():
    """An empty response.points list must produce an empty result list."""
    collection = _collection_with_query_response()  # zero points

    results = collection.search_points(np.array([0.1, 0.2]), limit=10)

    assert results == []


# ---------------------------------------------------------------------------
# QdrantCollection.search_points — error handling
# ---------------------------------------------------------------------------

@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", False)
def test_search_points_raises_when_qdrant_unavailable():
    client = MagicMock()
    collection = QdrantCollection(client, "test_collection")

    with pytest.raises(ProcessingError):
        collection.search_points(np.array([0.1, 0.2]), limit=5)


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_search_points_wraps_client_errors_as_processing_error():
    client = MagicMock()
    client.query_points.side_effect = RuntimeError("network failure")
    collection = QdrantCollection(client, "test_collection")

    with pytest.raises(ProcessingError, match="network failure"):
        collection.search_points(np.array([0.1, 0.2]), limit=5)


# ---------------------------------------------------------------------------
# QdrantStore.get_stats — vectors_count compatibility
# ---------------------------------------------------------------------------

def _store_with_collection_info(**info_attrs):
    """QdrantStore with a mocked client.get_collection() response."""
    store = QdrantStore()
    store.client = MagicMock()
    store.collection = MagicMock()
    store.collection.collection_name = "test_coll"

    info = MagicMock(spec=list(info_attrs.keys()))
    for attr, val in info_attrs.items():
        setattr(info, attr, val)
    store.client.get_collection.return_value = info
    return store


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_get_stats_uses_vectors_count_when_present():
    """On qdrant-client <1.16, vectors_count exists and must be returned."""
    store = _store_with_collection_info(
        points_count=10, vectors_count=10, status="green"
    )

    stats = store.get_stats()

    assert stats["points_count"] == 10
    assert stats["vectors_count"] == 10


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_get_stats_uses_points_count_when_vectors_count_absent():
    """On qdrant-client >=1.16, vectors_count is absent.
    For a single unnamed-vector collection (config.params.vectors is a
    VectorParams instance), points_count is the correct substitute.
    indexed_vectors_count must NOT be used: it counts only vectors
    in optimised segments and is 0 for freshly-inserted data."""
    from qdrant_client.models import VectorParams, Distance
    store = QdrantStore()
    store.client = MagicMock()
    store.collection = MagicMock()
    store.collection.collection_name = "test_coll"

    info = MagicMock(spec=["points_count", "indexed_vectors_count", "config", "status"])
    info.points_count = 5
    info.indexed_vectors_count = 0  # typical for freshly-inserted, unoptimised data
    info.config.params.vectors = VectorParams(size=4, distance=Distance.COSINE)
    info.status = "green"
    store.client.get_collection.return_value = info

    stats = store.get_stats()

    assert stats["points_count"] == 5
    # Must equal points_count (5), NOT indexed_vectors_count (0)
    assert stats["vectors_count"] == 5
    assert stats["vectors_count"] != info.indexed_vectors_count
    assert stats["status"] == "green"


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_get_stats_vectors_count_equals_points_count_when_vectors_count_absent():
    """On qdrant-client >=1.16, vectors_count is absent.  For a single unnamed-
    vector collection the fallback is points_count, so both keys are equal.
    indexed_vectors_count is intentionally absent from this mock to confirm
    it is not required by the fallback path."""
    from qdrant_client.models import VectorParams, Distance
    store = QdrantStore()
    store.client = MagicMock()
    store.collection = MagicMock()
    store.collection.collection_name = "test_coll"

    info = MagicMock(spec=["points_count", "config", "status"])
    info.points_count = 7
    info.config.params.vectors = VectorParams(size=8, distance=Distance.COSINE)
    info.status = "green"
    store.client.get_collection.return_value = info

    stats = store.get_stats()

    assert stats["points_count"] == 7
    assert stats["vectors_count"] == 7


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_get_stats_vectors_count_is_none_for_named_multi_vector_collection():
    """When vectors_count is absent and the collection uses named/multi vectors
    (config.params.vectors is a dict), the total cannot be inferred and
    vectors_count must be None rather than a misleading points_count value."""
    from qdrant_client.models import VectorParams, Distance
    store = QdrantStore()
    store.client = MagicMock()
    store.collection = MagicMock()
    store.collection.collection_name = "test_coll"

    info = MagicMock(spec=["points_count", "config", "status"])
    info.points_count = 4
    # Named multi-vector: qdrant-client returns a dict of VectorParams
    info.config.params.vectors = {
        "text": VectorParams(size=4, distance=Distance.COSINE),
        "image": VectorParams(size=8, distance=Distance.DOT),
    }
    info.status = "green"
    store.client.get_collection.return_value = info

    stats = store.get_stats()

    assert stats["points_count"] == 4
    # vectors_count must be None: total vectors = points * num_named_vectors,
    # and that multiplier is unknown to the caller.
    assert stats["vectors_count"] is None


@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_get_stats_vectors_count_is_none_when_config_inaccessible():
    """If the collection config cannot be read (e.g. an older schema or
    unexpected server response), vectors_count must fall back to None safely
    without raising."""
    store = QdrantStore()
    store.client = MagicMock()
    store.collection = MagicMock()
    store.collection.collection_name = "test_coll"

    # Simulate a CollectionInfo that has no config attribute at all
    info = MagicMock(spec=["points_count", "status"])
    info.points_count = 3
    info.status = "green"
    store.client.get_collection.return_value = info

    stats = store.get_stats()

    assert stats["points_count"] == 3
    assert stats["vectors_count"] is None
