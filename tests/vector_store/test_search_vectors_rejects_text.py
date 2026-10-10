"""``VectorStore.search_vectors`` must reject text with a message that names the
method, instead of failing deep inside NumPy (#1791)."""

import numpy as np
import pytest

from semantica.utils.exceptions import ValidationError
from semantica.vector_store import VectorStore


def _store_with_vectors() -> VectorStore:
    store = VectorStore(backend="inmemory")
    vectors = [np.random.rand(16).astype(np.float32) for _ in range(2)]
    store.store_vectors(vectors, metadata=[{"t": "a"}, {"t": "b"}])
    return store


def test_search_vectors_rejects_a_string():
    store = _store_with_vectors()
    with pytest.raises(ValidationError) as exc:
        store.search_vectors("a string, not a vector")
    message = str(exc.value)
    assert "search_vectors" in message
    assert "search(" in message


def test_search_vectors_still_accepts_a_vector():
    store = _store_with_vectors()
    results = store.search_vectors(np.random.rand(16).astype(np.float32))
    assert isinstance(results, list)
