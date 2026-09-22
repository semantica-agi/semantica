"""
Tests for ranking semantics (soft_floor) and node-embedding persistence.

Covers the two behaviors discussed in #1140:

1. Rank-first retrieval: the lexical content score of an exact-scenario
   match decays monotonically as ``reasoning`` grows (scenario, reasoning
   and entities share one bag of words, bounding the score by
   ``|S| / |S union R|``), so a fixed hard threshold loses well-documented
   decisions. ``soft_floor`` switches the search to top-k ranking with a
   low floor instead.

2. Node embeddings (e.g. node2vec) computed by
   ``NodeEmbedder.store_embeddings()`` live in the in-memory
   ``_node_embeddings`` dict for stores without property setters — they
   must survive ``save_to_file()`` / ``load_from_file()``.
"""

import pytest

from semantica.context.context_graph import ContextGraph


SCENARIO = "Choose a persistence layer for the agent decision log"
LONG_REASONING = (
    "Postgres is cheaper to operate at this scale than the managed "
    "alternative, and the team already runs it in production for two "
    "other services, so operational familiarity strongly favors it."
)


def _record_one(graph: ContextGraph) -> str:
    """Record one well-documented decision (exact scenario, long reasoning)."""
    return graph.record_decision(
        category="architecture",
        scenario=SCENARIO,
        reasoning=LONG_REASONING,
        outcome="postgres",
        confidence=0.9,
    )


class TestRankFirstSoftFloor:
    """soft_floor switches decision search to ranking semantics."""

    @pytest.fixture
    def graph(self):
        """One graph holding a single well-documented decision."""
        g = ContextGraph()
        _record_one(g)
        return g

    def test_diluted_decision_misses_hard_default(self, graph):
        """Without soft_floor, the long-reasoning decision stays unreachable
        through both documented entry points (the #1140 symptom)."""
        assert graph.find_precedents_by_scenario(SCENARIO) == []
        assert graph.find_similar_decisions(SCENARIO) == []

    def test_soft_floor_ranks_it_back(self, graph):
        """soft_floor=0.0 ranks every candidate; the decision comes back."""
        hits = graph.find_precedents_by_scenario(SCENARIO, soft_floor=0.0)
        assert len(hits) == 1
        assert hits[0]["decision"]["scenario"] == SCENARIO

        hits = graph.find_similar_decisions(SCENARIO, soft_floor=0.0)
        assert len(hits) == 1
        assert hits[0]["decision"]["scenario"] == SCENARIO

    def test_soft_floor_overrides_hard_threshold(self, graph):
        """A stale hard threshold must not apply when soft_floor is given."""
        hits = graph.find_precedents_by_scenario(
            SCENARIO, soft_floor=0.0, similarity_threshold=0.5
        )
        assert len(hits) == 1

    def test_soft_floor_still_floors_noise(self, graph):
        """A positive floor still removes total noise."""
        hits = graph.find_precedents_by_scenario(SCENARIO, soft_floor=0.99)
        assert hits == []

    def test_soft_floor_respects_limit_and_order(self, graph):
        """Ranking semantics returns at most ``limit``, best first."""
        for i in range(5):
            graph.record_decision(
                category="architecture",
                scenario=f"Decision number {i} about storage",
                reasoning="Short rationale with few shared words",
                outcome=f"outcome_{i}",
                confidence=0.8,
            )
        hits = graph.find_precedents_by_scenario(
            SCENARIO, soft_floor=0.0, limit=3
        )
        assert len(hits) == 3
        scores = [h["similarity"] for h in hits]
        assert scores == sorted(scores, reverse=True)


class TestNodeEmbeddingsPersistence:
    """_node_embeddings survives save_to_file/load_from_file."""

    def test_embeddings_round_trip(self, tmp_path):
        """Embeddings stored the way NodeEmbedder.store_embeddings() does
        (in-memory fallback dict) are written and restored."""
        source = ContextGraph()
        source.record_decision(
            category="architecture",
            scenario=SCENARIO,
            reasoning="Short rationale",
            outcome="postgres",
            confidence=0.9,
        )
        source._node_embeddings = {
            "node_a": [0.1, 0.2, 0.3],
            "node_b": [0.4, 0.5, 0.6],
        }

        path = tmp_path / "kg.json"
        source.save_to_file(path)

        loaded = ContextGraph()
        loaded.load_from_file(path)
        assert loaded._node_embeddings == {
            "node_a": [0.1, 0.2, 0.3],
            "node_b": [0.4, 0.5, 0.6],
        }

    def test_old_files_without_embeddings_still_load(self, tmp_path):
        """A file written before the key existed loads with empty embeddings
        and decision search keeps working (backward compatibility)."""
        source = ContextGraph()
        source.record_decision(
            category="architecture",
            scenario=SCENARIO,
            reasoning="Short rationale",
            outcome="postgres",
            confidence=0.9,
        )
        path = tmp_path / "kg_legacy.json"
        source.save_to_file(path)

        loaded = ContextGraph()
        loaded.load_from_file(path)
        assert loaded._node_embeddings == {}
        assert len(loaded.find_similar_decisions(SCENARIO, soft_floor=0.0)) == 1

    def test_load_replaces_stale_embeddings(self, tmp_path):
        """Loading a graph replaces (not merges with) in-memory embeddings."""
        stale = ContextGraph()
        stale._node_embeddings = {"ghost": [1.0, 1.0]}

        source = ContextGraph()
        source._node_embeddings = {"real": [0.5, 0.5]}
        path = tmp_path / "kg.json"
        source.save_to_file(path)

        stale.load_from_file(path)
        assert stale._node_embeddings == {"real": [0.5, 0.5]}
