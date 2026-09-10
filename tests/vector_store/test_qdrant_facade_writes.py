"""Regression tests for the Qdrant write path behind the VectorStore facade.

Qodo review of #1508 found three bugs in the newly wired qdrant dispatch:
stored IDs were swallowed (the upsert status dict was returned instead),
mismatched ids/vectors silently truncated the write via zip(), and lazy
collection init ignored the documented ``collection_name`` option. These
tests pin all three.

qdrant-client is not installed in this environment, so QDRANT_AVAILABLE is
patched and PointStruct is replaced with a plain stand-in, following the
pattern in test_vector_store_deepdive.py and test_qdrant_store.py.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantica.utils.exceptions import ValidationError
from semantica.vector_store import VectorStore
from semantica.vector_store.qdrant_store import QdrantStore

VECTORS = [np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])]
METADATA = [{"type": "a"}, {"type": "b"}]


class _Point:
    """Stand-in for qdrant_client PointStruct that keeps the point id."""

    def __init__(self, id, vector=None, payload=None):
        self.id = id
        self.vector = vector
        self.payload = payload


def _qdrant_facade(**config):
    """VectorStore built through the real qdrant init path, with the network
    client and an attached collection replaced by mocks."""
    store = VectorStore(backend="qdrant", config={"dimension": 3, **config})
    backend = store._backend_store
    backend.client = MagicMock()
    backend.collection = MagicMock()
    return store


@patch("semantica.vector_store.qdrant_store.PointStruct", _Point)
@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_facade_returns_generated_ids_not_upsert_status():
    """store_vectors() promises callers the stored vector IDs; the qdrant
    branch used to leak insert_vectors()' upsert status dict instead."""
    store = _qdrant_facade()

    ids = store.store_vectors(VECTORS, METADATA)

    assert isinstance(ids, list)
    assert len(ids) == len(VECTORS)
    assert all(isinstance(i, str) and i for i in ids)
    upserted = store._backend_store.collection.upsert_points.call_args[0][0]
    assert [p.id for p in upserted] == ids


@patch("semantica.vector_store.qdrant_store.PointStruct", _Point)
@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_facade_returns_caller_supplied_ids_verbatim():
    store = _qdrant_facade()

    ids = store.store_vectors(VECTORS, METADATA, ids=["doc-a", "doc-b"])

    assert ids == ["doc-a", "doc-b"]


@pytest.mark.parametrize("ids", [["doc-a"], ["doc-a", "doc-b", "doc-c"]])
@patch("semantica.vector_store.qdrant_store.PointStruct", _Point)
@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_facade_rejects_ids_count_mismatch(ids):
    """insert_vectors() pairs points with zip(vectors, ids); a mismatched
    batch must fail loudly instead of silently dropping vectors."""
    store = _qdrant_facade()

    with pytest.raises(ValidationError, match="must match number of vectors"):
        store.store_vectors(VECTORS, METADATA, ids=ids)
    store._backend_store.collection.upsert_points.assert_not_called()


@patch("semantica.vector_store.qdrant_store.PointStruct", _Point)
@patch("semantica.vector_store.qdrant_store.QDRANT_AVAILABLE", True)
def test_backend_insert_vectors_rejects_count_mismatch():
    """Direct QdrantStore callers get the same guard as facade callers."""
    store = QdrantStore()
    store.client = MagicMock()
    store.collection = MagicMock()

    with pytest.raises(ValidationError, match="must match number of vectors"):
        store.insert_vectors(VECTORS, ["only-one"])
    store.collection.upsert_points.assert_not_called()


def _lazy_collection_name(store):
    """Drive _ensure_default_collection and report the name it selected."""
    store.client = MagicMock()
    with (
        patch.object(store, "create_collection") as create,
        patch.object(store, "get_collection"),
    ):
        store._ensure_default_collection(3)
    return create.call_args[0][0]


def test_lazy_collection_uses_documented_collection_name():
    """The docs and facade configure qdrant with collection_name=...; lazy
    init used to look up 'collection' and always fall back to the default."""
    store = QdrantStore(collection_name="semantica")

    assert _lazy_collection_name(store) == "semantica"


def test_lazy_collection_accepts_legacy_collection_alias():
    store = QdrantStore(collection="legacy_name")

    assert _lazy_collection_name(store) == "legacy_name"


def test_lazy_collection_defaults_without_config():
    store = QdrantStore()

    assert _lazy_collection_name(store) == "semantica_default"
