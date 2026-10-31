"""
Tests for ranking semantics (soft_floor) and node-embedding persistence.

1. Rank-first retrieval: ``soft_floor`` switches decision search from a
   hard threshold to top-k ranking with a low floor. Since #1716 main
   scores a decision's own scenario first, the surviving cases are the
   default-threshold divergence between the two entry points (0.5 vs 0.3)
   and the reasoning-only match discounted below the 0.3 default — both
   overrideable with ``soft_floor`` (#1713 review).

2. Node embeddings (e.g. node2vec) stored through
   ``NodeEmbedder.store_embeddings()`` must stay readable through the
   public path — an empty in-memory ``_node_embeddings`` dict must not
   shadow property-backed vectors — and survive
   ``save_to_file()`` / ``load_from_file()``.
"""

import pytest

from semantica.context.context_graph import ContextGraph
from semantica.kg.node_embeddings import NodeEmbedder


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

    def test_exact_scenario_found_by_default_both_entry_points(self, graph):
        """Since #1716 main scores a decision's own scenario first: the
        exact-scenario match comes back through both entry points at their
        defaults — the old #1140 headline symptom no longer reproduces on
        main (the case this suite originally pinned)."""
        hits = graph.find_precedents_by_scenario(SCENARIO)
        assert len(hits) == 1
        assert hits[0]["decision"]["scenario"] == SCENARIO

        hits = graph.find_similar_decisions(SCENARIO)
        assert len(hits) == 1
        assert hits[0]["decision"]["scenario"] == SCENARIO

    def test_threshold_divergence_between_entry_points(self):
        """The two entry points disagree on their default hard threshold
        (find_precedents_by_scenario 0.5, find_similar_decisions 0.3 — both
        named by #1716 without being changed): the same match passes one and
        not the other, and soft_floor levels both to ranking semantics
        (#1713 review). Measured combined score for this fixture: 0.350."""
        g = ContextGraph()
        g.record_decision(
            category="architecture",
            scenario=SCENARIO
            + " across multiple regions and environments with strict "
            "compliance requirements",
            reasoning="Short rationale",
            outcome="postgres",
            confidence=0.9,
        )

        assert g.find_precedents_by_scenario(SCENARIO) == []
        assert len(g.find_similar_decisions(SCENARIO)) == 1

        hits = g.find_precedents_by_scenario(SCENARIO, soft_floor=0.0)
        assert len(hits) == 1
        hits = g.find_similar_decisions(SCENARIO, soft_floor=0.0)
        assert len(hits) == 1

    def test_reasoning_only_match_below_default_returns_with_soft_floor(self):
        """A query overlapping the reasoning but not the scenario falls
        below the 0.3 default (the 0.8x full-text discount of #1716) and is
        excluded by default — exactly the kind of threshold a caller should
        be able to override with soft_floor (#1713 review). Measured
        combined score for this fixture: 0.124."""
        g = ContextGraph()
        g.record_decision(
            category="architecture",
            scenario="Pick a deployment region for the customer API",
            reasoning="Operational familiarity with postgres favors the "
            "region the team already runs in production",
            outcome="eu-west",
            confidence=0.8,
        )
        query = "operational familiarity with postgres"

        assert g.find_similar_decisions(query) == []

        hits = g.find_similar_decisions(query, soft_floor=0.0)
        assert len(hits) == 1
        assert "postgres" in hits[0]["decision"]["reasoning"]

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
    """Embeddings survive save_to_file/load_from_file — both the in-memory
    dict path (stores without property setters) and the public
    ``NodeEmbedder.store_embeddings()`` path (property-backed stores)."""

    def test_embeddings_round_trip(self, tmp_path):
        """The in-memory _node_embeddings dict (the fallback path of
        store_embeddings() for stores without property setters) is written
        and restored."""
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

    def test_from_dict_resets_stale_embeddings(self):
        """clear()/from_dict() reset the in-memory embeddings with the
        graph: no ghost vectors for ids that no longer exist."""
        stale = ContextGraph()
        stale._node_embeddings = {"ghost": [1.0, 1.0, 1.0]}

        stale.from_dict({"nodes": [], "edges": []})
        assert stale._node_embeddings == {}

    def test_store_embeddings_public_path_reads_back(self):
        """store_embeddings() through the public path must be readable back:
        the always-present empty _node_embeddings dict must not shadow the
        vectors stored as node properties (#1713 review)."""
        graph = ContextGraph()
        node_a = graph.record_decision(
            category="architecture",
            scenario=SCENARIO,
            reasoning="Short rationale",
            outcome="postgres",
            confidence=0.9,
        )
        node_b = graph.record_decision(
            category="architecture",
            scenario="A second decision for the similarity search",
            reasoning="Short rationale",
            outcome="sqlite",
            confidence=0.8,
        )

        NodeEmbedder().store_embeddings(
            graph,
            {node_a: [1.0, 0.0, 0.0], node_b: [0.9, 0.1, 0.0]},
        )

        embedder = NodeEmbedder()
        assert embedder._get_node_embedding(
            graph, node_a, "node2vec_embedding"
        ) == [1.0, 0.0, 0.0]
        assert embedder._get_node_embedding(
            graph, node_b, "node2vec_embedding"
        ) == [0.9, 0.1, 0.0]

    def test_public_path_survives_round_trip(self, tmp_path):
        """store_embeddings() + save_to_file() + load_from_file(): the
        embeddings must still be readable, including through
        find_similar_nodes (persistence takes effect through the public
        path — #1713 review)."""
        source = ContextGraph()
        node_a = source.record_decision(
            category="architecture",
            scenario=SCENARIO,
            reasoning="Short rationale",
            outcome="postgres",
            confidence=0.9,
        )
        node_b = source.record_decision(
            category="architecture",
            scenario="A second decision for the similarity search",
            reasoning="Short rationale",
            outcome="sqlite",
            confidence=0.8,
        )
        NodeEmbedder().store_embeddings(
            source,
            {node_a: [1.0, 0.0, 0.0], node_b: [0.9, 0.1, 0.0]},
        )

        path = tmp_path / "kg_public_path.json"
        source.save_to_file(path)
        loaded = ContextGraph()
        loaded.load_from_file(path)

        embedder = NodeEmbedder()
        assert embedder._get_node_embedding(
            loaded, node_a, "node2vec_embedding"
        ) == [1.0, 0.0, 0.0]
        assert embedder.find_similar_nodes(loaded, node_a) == [node_b]


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

    def test_neighbors_respect_temporal_filter(self):
        """A decision whose valid_until is past is filtered out of the
        primary results AND out of the neighbors (same predicate — #1713
        review), and comes back with include_superseded=True."""
        g = ContextGraph()
        main_id = g.record_decision(
            category="architecture",
            scenario=SCENARIO,
            reasoning="Cost",
            outcome="postgres",
            confidence=0.9,
        )
        expired_id = g.record_decision(
            category="architecture",
            scenario="Retire the legacy reporting warehouse",
            reasoning="postgres service accounts and shared tooling",
            outcome="retire",
            confidence=0.8,
            valid_until="2020-01-01T00:00:00",
        )
        g.add_causal_relationship(main_id, expired_id, "CAUSED")

        hits = g.find_precedents_by_scenario(SCENARIO, include_neighbors=3)
        assert len(hits) == 1
        assert all(
            n["decision"]["id"] != expired_id
            for n in hits[0].get("neighbors", [])
        )

        revisited = g.find_precedents_by_scenario(
            SCENARIO, include_neighbors=3, include_superseded=True
        )
        assert any(
            n["decision"]["id"] == expired_id
            for n in revisited[0].get("neighbors", [])
        )
