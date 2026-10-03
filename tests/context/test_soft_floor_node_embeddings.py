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


class TestNeighborhoodRetrieval:
    """include_neighbors attaches the thread around a matched decision.

    The fixtures below keep the main match above the default hard threshold
    (short reasoning) while its neighbors stay below it, so the neighbors
    attached by the option are exactly the decisions the search alone lost.
    """

    @pytest.fixture
    def graph(self):
        """A well-scoring decision plus two related-but-unreachable ones."""
        g = ContextGraph()
        main_id = g.record_decision(
            category="architecture",
            scenario=SCENARIO,
            reasoning="Cost",
            outcome="postgres",
            confidence=0.9,
            entities=["postgres", "storage"],
        )
        g.record_decision(
            category="architecture",
            scenario="Migrate the analytics jobs to the new warehouse",
            reasoning="Same storage stack, shared tooling and backup runbooks",
            outcome="migrate",
            confidence=0.8,
            entities=["postgres", "analytics"],
        )
        g.record_decision(
            category="branding",
            scenario="Pick a logo color for the landing page",
            reasoning="Marketing wants something calm",
            outcome="blue",
            confidence=0.7,
            entities=["marketing"],
        )
        return g, main_id

    def test_neighbors_attached_via_shared_entities(self, graph):
        """The unreachable decision sharing an entity comes back as neighbor."""
        g, _ = graph
        hits = g.find_precedents_by_scenario(SCENARIO, include_neighbors=3)
        assert len(hits) == 1
        neighbors = hits[0]["neighbors"]
        assert len(neighbors) == 1
        assert neighbors[0]["via"] == "shared_entities"
        assert "postgres" in neighbors[0]["shared_entities"]
        assert neighbors[0]["decision"]["entities"] == ["postgres", "analytics"]

    def test_neighbors_absent_by_default(self, graph):
        """Without the option the result shape is unchanged."""
        g, _ = graph
        hits = g.find_precedents_by_scenario(SCENARIO)
        assert all("neighbors" not in h for h in hits)

    def test_neighbors_capped_per_precedent(self, graph):
        """The count is honored exactly."""
        g, _ = graph
        hits = g.find_precedents_by_scenario(SCENARIO, include_neighbors=1)
        assert len(hits[0]["neighbors"]) == 1

    def test_causal_neighbor_comes_first(self, graph):
        """Explicit causal relationships outrank shared-entity adjacency."""
        g, main_id = graph
        all_ids = list(g._decisions.keys())
        other_id = next(d for d in all_ids if d != main_id)
        g.add_causal_relationship(main_id, other_id, "CAUSED")
        # Rank a third decision in below the threshold by sharing an entity.
        g.record_decision(
            category="ops",
            scenario="Rotate the database credentials quarterly",
            reasoning="postgres service accounts",
            outcome="rotate",
            confidence=0.8,
            entities=["postgres", "security"],
        )
        hits = g.find_precedents_by_scenario(SCENARIO, include_neighbors=2)
        neighbors = hits[0]["neighbors"]
        assert [n["via"] for n in neighbors] == ["causal", "shared_entities"]
        assert neighbors[0]["relationship"] == "CAUSED"
        assert neighbors[0]["decision"]["id"] == other_id

    def test_neighbors_through_wrapper(self, graph):
        """find_similar_decisions passes include_neighbors through."""
        g, _ = graph
        hits = g.find_similar_decisions(
            SCENARIO, min_similarity=0.5, include_neighbors=1
        )
        assert len(hits) == 1
        assert len(hits[0]["neighbors"]) == 1
