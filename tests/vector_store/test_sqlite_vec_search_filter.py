"""Regression tests for metadata filtering during sqlite-vec KNN search."""

import numpy as np
import pytest

from semantica.vector_store import VectorStore
from semantica.vector_store.sqlite_vec_store import SQLITE_VEC_AVAILABLE, SQLiteVecStore

pytestmark = pytest.mark.skipif(
    not SQLITE_VEC_AVAILABLE, reason="sqlite-vec not available"
)


@pytest.fixture(params=["cosine", "l2"])
def filtered_store(tmp_path, request):
    with SQLiteVecStore(
        str(tmp_path / "vectors.db"),
        "vectors",
        dimension=2,
        distance_metric=request.param,
    ) as store:
        store.add(
            [[1, 0], [1, 0.1], [1, 1], [0, 1], [1, 0.2]],
            ids=["excluded", "partial", "near", "far", "missing"],
            metadata=[
                {"category": "other", "active": False, "rank": 0},
                {"category": "team's", "active": False, "rank": 1},
                {"category": "team's", "active": True, "rank": 2},
                {"category": "team's", "active": True, "rank": 2},
                {},
            ],
        )
        yield store


@pytest.mark.parametrize("top_k", [1, 2, 10])
@pytest.mark.parametrize(
    "metadata_filter",
    [{"active": True}, {"rank": 2}, {"category": "team's", "active": True}],
)
def test_search_filters_candidates_before_top_k(filtered_store, top_k, metadata_filter):
    results = filtered_store.search(
        np.array([1.0, 0.0]), top_k=top_k, filter=metadata_filter
    )

    assert [result["id"] for result in results] == ["near", "far"][:top_k]
    assert all(result["metadata"]["active"] is True for result in results)
    scores = [result["score"] for result in results]
    assert scores == sorted(scores, reverse=True)


def test_facade_filtered_search_after_reopen(filtered_store):
    filtered_store.close()
    store = VectorStore(
        backend="sqlite",
        db_path=filtered_store.db_path,
        table_name=filtered_store.table_name,
        dimension=2,
        distance_metric=filtered_store.distance_metric,
        read_only=True,
    )
    try:
        results = store.search_vectors(
            np.array([1.0, 0.0]), k=2, filter={"active": True}
        )
        assert [result["id"] for result in results] == ["near", "far"]
    finally:
        store._backend_store.close()


def test_search_with_no_matching_candidates(filtered_store):
    assert (
        filtered_store.search(
            np.array([1.0, 0.0]), top_k=2, filter={"category": "absent"}
        )
        == []
    )
