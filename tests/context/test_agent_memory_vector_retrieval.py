"""AgentMemory.retrieve returns the memories a VectorStore finds (#1724)."""

import pytest

from semantica.context import AgentMemory
from semantica.vector_store import VectorStore

REACTOR = "The reactor coolant pump tripped on Tuesday"
REVENUE = "Quarterly revenue grew by twelve percent"
QUERY = "nuclear plant outage"


@pytest.fixture
def vector_store():
    return VectorStore(backend="inmemory")


@pytest.fixture
def memory(vector_store):
    memory = AgentMemory(vector_store=vector_store)
    memory.store(REACTOR)
    memory.store(REVENUE)
    return memory


def test_retrieve_returns_vector_hits_without_keyword_overlap(memory):
    results = memory.retrieve(QUERY)

    assert REACTOR in {r["content"] for r in results}
    assert {r["memory_id"] for r in results} <= set(memory.memory_items)


def test_retrieve_skips_vectors_that_are_not_memories(vector_store, memory):
    vector_store.store_vectors(
        vectors=[vector_store.embed("nuclear plant outage report")],
        metadata=[{"type": "decision"}],
    )

    results = memory.retrieve(QUERY)

    assert results
    assert {r["memory_id"] for r in results} <= set(memory.memory_items)


class _IntIdStore:
    def __init__(self):
        self.vectors = []

    def embed(self, text):
        return [1.0, 1.0]

    def store_vectors(self, vectors, metadata):
        self.vectors.extend(vectors)
        return [len(self.vectors) - 1]

    def search_vectors(self, query_vector, k):
        return [{"id": i, "score": 1.0} for i in range(len(self.vectors))][:k]


def test_retrieve_maps_integer_vector_ids():
    memory = AgentMemory(vector_store=_IntIdStore())
    memory.store(REACTOR)

    results = memory.retrieve(QUERY)

    assert [r["content"] for r in results] == [REACTOR]
