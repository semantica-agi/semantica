"""
Regression tests for Context Explainability Output Fixes.

Covers:
- Readable decision text preservation in ContextGraph nodes and reconstruction paths
- Enriched causal/path outputs (from_scenario, to_scenario, scenario/outcome/category dicts)
- PolicyEngine.get_affected_decisions() consistent metadata across Cypher and fallback branches
- EntityLinker similarity flows return full enriched payloads
- KG consumer compatibility (node_embeddings, link_predictor, centrality_calculator, path_finder)
  when ContextGraph is used as the graph store and get_neighbors returns enriched dicts
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Any, Dict, List

from semantica.context.context_graph import ContextGraph
from semantica.context.decision_models import Decision
from semantica.context.entity_linker import EntityLinker
from semantica.context.policy_engine import PolicyEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_decision(decision_id: str, scenario: str, reasoning: str,
                   category: str = "test", outcome: str = "approved",
                   confidence: float = 0.9, decision_maker: str = "agent_1") -> Decision:
    return Decision(
        decision_id=decision_id,
        category=category,
        scenario=scenario,
        reasoning=reasoning,
        outcome=outcome,
        confidence=confidence,
        timestamp=datetime.now(),
        decision_maker=decision_maker,
    )


# ===========================================================================
# Group 1 – Readable Decision Text Preservation
# ===========================================================================

class TestReadableDecisionTextPreservation:
    """Decision-node storage preserves full human-readable text, not IDs."""

    def test_add_decision_scenario_stored_as_content(self):
        """scenario is stored as node.content, not as an opaque ID."""
        g = ContextGraph()
        d = _make_decision(
            "d1",
            scenario="Loan application for first-time buyer: $300k, FICO 720",
            reasoning="Strong credit profile with stable income"
        )
        g.add_decision(d)

        node = g.nodes["d1"]
        assert node.content == d.scenario, (
            "node.content must equal the full human-readable scenario string"
        )
        assert node.content != "d1", "node.content must NOT be the node ID"

    def test_add_decision_reasoning_preserved_in_properties(self):
        """Full reasoning text is stored in node.properties, not truncated."""
        g = ContextGraph()
        long_reasoning = (
            "Customer has 8-year payment history, zero delinquencies, debt-to-income "
            "ratio of 28%, salary verified at $95k/year via W-2. Risk score: LOW."
        )
        d = _make_decision("d2", "Credit card limit review", long_reasoning)
        g.add_decision(d)

        node = g.nodes["d2"]
        assert node.properties["reasoning"] == long_reasoning
        assert len(node.properties["reasoning"]) > 50

    def test_find_precedents_returns_decision_with_readable_scenario(self):
        """find_precedents() returns Decision objects whose .scenario is readable text."""
        g = ContextGraph()
        cause = _make_decision(
            "cause_1",
            scenario="Overdraft protection request – account in good standing 5 yrs",
            reasoning="Long account history, low overdraft frequency"
        )
        effect = _make_decision(
            "effect_1",
            scenario="Fee waiver granted due to precedent overdraft approval",
            reasoning="Follows precedent cause_1"
        )
        g.add_decision(cause)
        g.add_decision(effect)
        g.add_causal_relationship("cause_1", "effect_1", "PRECEDENT_FOR")

        precedents = g.find_precedents("effect_1")
        assert len(precedents) >= 1, "Should return at least one precedent"

        p = precedents[0]
        assert isinstance(p, Decision)
        assert p.scenario, "Returned Decision.scenario must not be empty"
        assert "overdraft" in p.scenario.lower() or "Overdraft" in p.scenario, (
            f"scenario should contain human-readable text, got: {p.scenario!r}"
        )
        assert p.scenario != "cause_1", "scenario must NOT be the raw node ID"

    def test_get_causal_chain_returns_readable_text(self):
        """get_causal_chain() returns Decision objects with scenario text from node.content."""
        g = ContextGraph()
        for did, scenario in [
            ("root", "Initial fraud alert triggered on account #7734"),
            ("mid",  "Temporary hold placed pending fraud investigation"),
            ("leaf", "Card blocked; customer notified via SMS"),
        ]:
            g.add_decision(_make_decision(did, scenario, f"reasoning for {did}"))

        g.add_causal_relationship("root", "mid", "CAUSED")
        g.add_causal_relationship("mid", "leaf", "CAUSED")

        chain = g.get_causal_chain("leaf", direction="upstream")
        assert len(chain) >= 1

        for dec in chain:
            assert isinstance(dec, Decision)
            assert dec.scenario, "Each chained Decision must have non-empty scenario"
            assert dec.scenario != dec.decision_id, (
                f"scenario '{dec.scenario}' must not equal the decision_id"
            )


# ===========================================================================
# Group 2 – Enriched Causal / Path Outputs
# ===========================================================================

class TestEnrichedCausalOutputs:
    """trace_decision_causality and analyze_decision_influence return readable dicts."""

    def _graph_with_decisions(self):
        g = ContextGraph()
        alpha_id = g.record_decision(
            category="mortgage",
            scenario="Approve mortgage for tech employee earning $180k",
            reasoning="Strong credit profile and stable income verified",
            outcome="approved",
            confidence=0.92,
            entities=["tech_employee", "mortgage_dept"],
        )
        beta_id = g.record_decision(
            category="auto_loan",
            scenario="Approve auto-loan backed by employer letter",
            reasoning="Employer verification provided, income above threshold",
            outcome="approved",
            confidence=0.85,
            entities=["tech_employee", "auto_dept"],
        )
        return g, alpha_id, beta_id

    def test_trace_decision_causality_hops_have_scenario_fields(self):
        """Each causal hop includes from_scenario and to_scenario with readable text."""
        g, alpha_id, beta_id = self._graph_with_decisions()
        chains = g.trace_decision_causality(beta_id, max_depth=3)

        # At least one hop should exist (shared entity creates causal link)
        if chains:
            for hop_list in chains:
                for hop in hop_list:
                    assert "from" in hop, "hop must have 'from' key"
                    assert "to" in hop, "hop must have 'to' key"
                    assert "from_scenario" in hop, (
                        f"hop must have 'from_scenario' key, got keys: {list(hop.keys())}"
                    )
                    assert "to_scenario" in hop, (
                        f"hop must have 'to_scenario' key, got keys: {list(hop.keys())}"
                    )
                    # Scenarios must be strings, not empty IDs
                    assert isinstance(hop["from_scenario"], str)
                    assert isinstance(hop["to_scenario"], str)

    def test_analyze_decision_influence_direct_influence_is_enriched_dicts(self):
        """direct_influence list contains dicts with decision_id, scenario, outcome, category."""
        g, alpha_id, beta_id = self._graph_with_decisions()
        result = g.analyze_decision_influence(alpha_id)

        assert "direct_influence" in result
        assert isinstance(result["direct_influence"], list)

        for item in result["direct_influence"]:
            assert isinstance(item, dict), (
                f"direct_influence items must be dicts, got {type(item)}"
            )
            for field in ("decision_id", "scenario", "outcome", "category"):
                assert field in item, (
                    f"influence item missing field '{field}', keys: {list(item.keys())}"
                )

    def test_analyze_decision_influence_scores_contain_readable_fields(self):
        """influence_scores entries include scenario/outcome/category alongside score."""
        g, alpha_id, beta_id = self._graph_with_decisions()
        result = g.analyze_decision_influence(alpha_id)

        assert "influence_scores" in result
        for item in result["influence_scores"]:
            assert "score" in item
            assert "decision_id" in item
            assert "scenario" in item
            assert "category" in item
            assert "outcome" in item


# ===========================================================================
# Group 3 – PolicyEngine Consistent Decision Metadata
# ===========================================================================

class TestPolicyEngineAffectedDecisions:
    """get_affected_decisions() returns enriched metadata from both branches."""

    def _mock_store_with_query(self, records):
        store = MagicMock()
        store.execute_query.return_value = records
        return store

    def test_cypher_branch_returns_scenario_category_outcome_confidence(self):
        """Cypher results include scenario/category/outcome/confidence with actual values."""
        records = [
            {
                "decision_id": "dec_abc",
                "scenario": "Increase credit limit for platinum member",
                "category": "credit",
                "outcome": "approved",
                "confidence": 0.88,
            }
        ]
        store = self._mock_store_with_query(records)
        pe = PolicyEngine(graph_store=store)

        affected = pe.get_affected_decisions("policy_1", "v1", "v2")

        assert len(affected) == 1
        d = affected[0]
        assert d["scenario"] == "Increase credit limit for platinum member", (
            f"scenario must be readable text, got: {d['scenario']!r}"
        )
        assert d["category"] == "credit"
        assert d["outcome"] == "approved"
        assert d["confidence"] == pytest.approx(0.88, abs=1e-6)

    def test_fallback_branch_enriches_from_context_graph_nodes(self):
        """Fallback branch reads scenario/category/outcome/confidence from ContextGraph nodes."""
        g = ContextGraph()
        d = _make_decision(
            "dec_xyz",
            scenario="Block account after 3 failed PIN attempts",
            reasoning="Security policy v1 requires lockout",
            category="security",
            outcome="blocked",
            confidence=0.99,
        )
        g.add_decision(d)
        # Add a policy node and the APPLIED_POLICY edge
        g.add_node("policy_2:v1", "Policy", {"policy_id": "policy_2", "version": "v1"})
        g.add_edge("dec_xyz", "policy_2:v1", "APPLIED_POLICY")

        pe = PolicyEngine(graph_store=g)

        affected = pe.get_affected_decisions("policy_2", "v1", "v2")

        assert len(affected) == 1
        d_out = affected[0]
        assert d_out["decision_id"] == "dec_xyz"
        # scenario must come from node.content, not be empty or the raw ID
        assert d_out["scenario"], "scenario must not be empty"
        assert d_out["scenario"] != "dec_xyz", (
            f"scenario should be readable text not the node ID, got: {d_out['scenario']!r}"
        )
        assert "PIN" in d_out["scenario"] or "Block" in d_out["scenario"], (
            f"scenario should reflect stored decision text, got: {d_out['scenario']!r}"
        )

    def test_both_branches_return_same_key_shape(self):
        """Both Cypher and fallback branches return dicts with identical required keys."""
        required_keys = {"decision_id", "scenario", "category", "outcome", "confidence"}

        # Cypher branch
        store_cypher = self._mock_store_with_query([{
            "decision_id": "d1",
            "scenario": "some scenario",
            "category": "cat",
            "outcome": "out",
            "confidence": 0.5,
        }])
        pe_c = PolicyEngine(graph_store=store_cypher)
        cypher_result = pe_c.get_affected_decisions("p", "v1", "v2")
        assert len(cypher_result) == 1
        assert required_keys.issubset(cypher_result[0].keys()), (
            f"Cypher branch missing keys: {required_keys - cypher_result[0].keys()}"
        )

        # Fallback branch
        g = ContextGraph()
        g.add_decision(_make_decision("d2", "fallback scenario", "fallback reason"))
        g.add_node("p2:v1", "Policy", {})
        g.add_edge("d2", "p2:v1", "APPLIED_POLICY")
        pe_f = PolicyEngine(graph_store=g)
        fallback_result = pe_f.get_affected_decisions("p2", "v1", "v2")
        assert len(fallback_result) == 1
        assert required_keys.issubset(fallback_result[0].keys()), (
            f"Fallback branch missing keys: {required_keys - fallback_result[0].keys()}"
        )


# ===========================================================================
# Group 4 – EntityLinker Similarity Payloads
# ===========================================================================

class TestEntityLinkerSimilarityPayloads:
    """EntityLinker similarity flows return enriched dicts, not bare IDs."""

    def _linker(self):
        return EntityLinker(
            knowledge_graph={
                "entities": [
                    {
                        "id": "ent_python",
                        "text": "Python programming language",
                        "type": "Technology",
                    },
                    {
                        "id": "ent_java",
                        "text": "Java programming language",
                        "type": "Technology",
                    },
                    {
                        "id": "ent_sql",
                        "text": "SQL database query language",
                        "type": "Language",
                    },
                ]
            }
        )

    def test_find_similar_entities_returns_full_payload_keys(self):
        """find_similar_entities() returns dicts with entity_id, text, type, uri, similarity."""
        linker = self._linker()
        results = linker.find_similar_entities("Python language", threshold=0.1)

        assert isinstance(results, list)
        assert len(results) >= 1, "Should find at least one similar entity"

        for item in results:
            assert isinstance(item, dict)
            for field in ("entity_id", "text", "type", "similarity"):
                assert field in item, (
                    f"find_similar_entities result missing field '{field}', got: {list(item.keys())}"
                )
            # entity_id must be the stored ID, not empty
            assert item["entity_id"], "entity_id must not be empty"
            # similarity must be a non-negative float
            assert isinstance(item["similarity"], (int, float))
            assert item["similarity"] >= 0.0

    def test_find_similar_entities_text_field_is_human_readable(self):
        """text field in similarity results is human-readable entity text, not an ID."""
        linker = self._linker()
        results = linker.find_similar_entities("Python language", threshold=0.1)

        assert len(results) >= 1
        for item in results:
            assert item["text"] != item["entity_id"], (
                f"text should be human-readable, not the entity ID: {item['text']!r}"
            )
            assert len(item["text"]) > 2

    def test_find_similar_entities_sorted_by_similarity_descending(self):
        """Results are sorted by similarity in descending order."""
        linker = self._linker()
        results = linker.find_similar_entities("Python language", threshold=0.0)

        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i]["similarity"] >= results[i + 1]["similarity"], (
                    "Results must be sorted by similarity descending"
                )

    def test_find_similar_public_alias_returns_full_payload(self):
        """find_similar() public alias delegates to find_similar_entities and returns full dicts."""
        linker = self._linker()
        results = linker.find_similar("Python language", threshold=0.1)

        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, dict)
            assert "entity_id" in item
            assert "text" in item
            assert "similarity" in item

    def test_find_similar_with_entity_dict_input(self):
        """find_similar() accepts an EntityDict as input and returns full dicts."""
        linker = self._linker()
        entity_dict = {"text": "Java language", "type": "Technology"}
        results = linker.find_similar(entity_dict, threshold=0.1)

        assert isinstance(results, list)
        for item in results:
            assert "entity_id" in item
            assert "similarity" in item

    def test_find_linked_entities_creates_entity_links_with_ids(self):
        """_find_linked_entities creates EntityLink objects with valid target entity IDs."""
        linker = self._linker()
        linker.assign_uri("ent_python", "Python programming language", "Technology")

        links = linker._find_linked_entities(
            entity_id="my_entity",
            entity_text="Python language",
            entity_type="Technology",
            all_entities=[],
            context=None,
        )

        assert isinstance(links, list)
        for link in links:
            # target_entity_id must be a stored entity ID, not empty or equal to text
            assert link.target_entity_id, "target_entity_id must not be empty"
            assert link.target_entity_id.startswith("ent_"), (
                f"target_entity_id should be a stored entity ID, got: {link.target_entity_id!r}"
            )
            assert link.confidence >= 0.0


# ===========================================================================
# Group 5 – KG Consumer Compatibility
# ===========================================================================

class TestKGConsumerCompatibility:
    """KG algorithms normalize enriched neighbor/node dicts from ContextGraph correctly."""

    def _graph_with_nodes(self, pairs):
        """Build a ContextGraph with given (id, label) pairs connected in a chain."""
        g = ContextGraph()
        for nid, label in pairs:
            g.add_node(nid, label, {"name": nid})
        # Connect in order
        ids = [nid for nid, _ in pairs]
        for i in range(len(ids) - 1):
            g.add_edge(ids[i], ids[i + 1], "RELATED_TO")
        return g

    def test_node_embedder_build_adjacency_normalizes_enriched_dicts(self):
        """NodeEmbedder._build_adjacency strips enriched dicts to node IDs (no crash, no None)."""
        from semantica.kg.node_embeddings import NodeEmbedder

        g = self._graph_with_nodes([("A", "Person"), ("B", "Person"), ("C", "Person")])
        embedder = NodeEmbedder()

        # Verify get_neighbors on ContextGraph returns dicts (enriched)
        raw = g.get_neighbors("A")
        assert isinstance(raw[0], dict), "ContextGraph.get_neighbors should return dicts"
        assert "id" in raw[0]

        adjacency = embedder._build_adjacency(g, ["Person", "Person"], ["RELATED_TO"])
        # Each node maps to a list of plain string IDs
        for node_id, neighbors in adjacency.items():
            assert isinstance(node_id, str)
            for nb in neighbors:
                assert isinstance(nb, str), (
                    f"adjacency neighbor must be a string ID, got {type(nb)}: {nb!r}"
                )
                assert nb is not None

    def test_link_predictor_get_node_neighbors_normalizes_enriched_dicts(self):
        """LinkPredictor._get_node_neighbors strips enriched dicts to plain IDs."""
        from semantica.kg.link_predictor import LinkPredictor

        g = self._graph_with_nodes([("X", "Item"), ("Y", "Item"), ("Z", "Item")])
        predictor = LinkPredictor()

        neighbors = predictor._get_node_neighbors(g, "X")
        assert isinstance(neighbors, list)
        for nb in neighbors:
            assert isinstance(nb, str), (
                f"neighbor must be a plain string ID, got {type(nb)}: {nb!r}"
            )
            assert nb is not None

    def test_link_predictor_score_link_works_with_context_graph(self):
        """score_link() runs without error when given a ContextGraph store."""
        from semantica.kg.link_predictor import LinkPredictor

        g = self._graph_with_nodes([
            ("n1", "Entity"), ("n2", "Entity"), ("n3", "Entity")
        ])
        predictor = LinkPredictor()

        score = predictor.score_link(g, "n1", "n3", method="common_neighbors")
        assert isinstance(score, (int, float))
        assert score >= 0.0

    def test_centrality_calculator_get_filtered_neighbors_normalizes_dicts(self):
        """CentralityCalculator._get_filtered_neighbors strips enriched dicts to IDs."""
        from semantica.kg.centrality_calculator import CentralityCalculator

        g = self._graph_with_nodes([("c1", "Node"), ("c2", "Node"), ("c3", "Node")])
        calc = CentralityCalculator()

        neighbors = calc._get_filtered_neighbors(g, "c1", relationship_types=None)
        assert isinstance(neighbors, list)
        for nb in neighbors:
            assert isinstance(nb, str), (
                f"filtered neighbor must be a plain string ID, got {type(nb)}: {nb!r}"
            )

    def test_centrality_calculator_degree_centrality_works_with_context_graph(self):
        """calculate_degree_centrality() works with ContextGraph as the graph store."""
        from semantica.kg.centrality_calculator import CentralityCalculator

        g = self._graph_with_nodes([
            ("hub", "Node"), ("spoke1", "Node"), ("spoke2", "Node")
        ])
        g.add_edge("hub", "spoke2", "RELATED_TO")  # hub has extra edge
        calc = CentralityCalculator()

        result = calc.calculate_degree_centrality(g)
        assert isinstance(result, dict)
        # result has keys: centrality, rankings, max_degree, total_nodes
        assert "centrality" in result
        centrality = result["centrality"]
        assert isinstance(centrality, dict)
        assert len(centrality) > 0
        for node_id, score in centrality.items():
            assert isinstance(node_id, str)
            assert isinstance(score, (int, float))
            assert score >= 0.0

    def test_path_finder_get_neighbors_normalizes_enriched_dicts(self):
        """PathFinder._get_neighbors strips enriched dicts to (id, edge_data) tuples."""
        from semantica.kg.path_finder import PathFinder

        g = self._graph_with_nodes([("p1", "Stop"), ("p2", "Stop"), ("p3", "Stop")])
        finder = PathFinder()

        neighbors = finder._get_neighbors(g, "p1")
        assert isinstance(neighbors, list)
        for item in neighbors:
            node_id, edge_data = item
            assert isinstance(node_id, str), (
                f"neighbor node_id must be a plain string, got {type(node_id)}: {node_id!r}"
            )
            assert node_id is not None

    def test_path_finder_dijkstra_works_with_context_graph(self):
        """dijkstra_shortest_path() runs without error on ContextGraph."""
        from semantica.kg.path_finder import PathFinder

        g = self._graph_with_nodes([
            ("start", "Node"), ("mid", "Node"), ("end", "Node")
        ])
        finder = PathFinder()

        result = finder.dijkstra_shortest_path(g, "start", "end")
        assert result is not None
        assert isinstance(result, list)
        assert "start" in result
        assert "end" in result
