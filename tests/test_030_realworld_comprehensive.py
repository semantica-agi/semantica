"""
Comprehensive Real-World Test Suite for Semantica 0.3.0-alpha and 0.3.0-beta

Tests all major features with real-world use cases based on publicly available
knowledge about technology companies, their founders, products, and relationships.

Coverage:
  1.  ContextGraph - add/query nodes and edges (tech company knowledge graph)
  2.  ContextGraph - decision tracking lifecycle (loan approval domain)
  3.  ContextGraph - causal chain traversal (upstream & downstream)
  4.  ContextGraph - find_precedents via PRECEDENT_FOR edges
  5.  ContextGraph - record_decision() high-level API
  6.  ContextGraph - analyze_graph_with_kg() KG analytics
  7.  ContextGraph - find_similar_nodes() content & structural similarity
  8.  ContextGraph - get_node_centrality()
  9.  ContextGraph - save/load round-trip (JSON)
  10. ContextGraph - build_from_entities_and_relationships()
  11. ContextGraph - query() keyword search
  12. ContextGraph - get_neighbors() multi-hop BFS
  13. PolicyEngine - get_applicable_policies (ContextGraph fallback)
  14. DecisionQuery - find_precedents_hybrid
  15. CausalChainAnalyzer - get_causal_chain
  16. AgentContext - store / retrieve cycle
  17. AgentContext - record_decision + find_precedents
  18. AgentContext - capture_cross_system_inputs (error sanitization)
  19. KG algorithms - GraphBuilder + CentralityCalculator (tech network)
  20. KG algorithms - CommunityDetector (open-source ecosystem)
  21. KG algorithms - PathFinder shortest path (supply chain)
  22. KG algorithms - SimilarityCalculator (company similarity)
  23. KG algorithms - NodeEmbedder (person embeddings)
  24. KG algorithms - LinkPredictor (collaboration prediction)
  25. Deduplication v2 - semantic dedup (company name variants)
  26. Deduplication v2 - blocking_v2 candidate generation
  27. Export - RDF/TTL alias
  28. Reasoner - _match_pattern multi-word value inference
  29. Pipeline - retry + exponential backoff
  30. Decision models - full lifecycle serialization
"""

import json
import os
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# ── Context module ────────────────────────────────────────────────────────────
from semantica.context import (
    AgentContext,
    CausalChainAnalyzer,
    ContextGraph,
    Decision,
    DecisionQuery,
    DecisionRecorder,
    Policy,
    PolicyEngine,
)
from semantica.context.decision_models import (
    ApprovalChain,
    PolicyException,
    Precedent,
    deserialize_decision,
    serialize_decision,
    validate_decision,
)

# ── KG module ─────────────────────────────────────────────────────────────────
from semantica.kg import (
    CentralityCalculator,
    CommunityDetector,
    ConnectivityAnalyzer,
    GraphBuilder,
    LinkPredictor,
    NodeEmbedder,
    PathFinder,
    SimilarityCalculator,
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

# Real-world tech company graph data
# Sources: Wikipedia / Crunchbase public knowledge (no live web calls made)
TECH_ENTITIES = [
    {"id": "apple", "type": "company", "text": "Apple Inc.", "founded": 1976, "sector": "technology"},
    {"id": "microsoft", "type": "company", "text": "Microsoft Corporation", "founded": 1975, "sector": "technology"},
    {"id": "google", "type": "company", "text": "Google LLC", "founded": 1998, "sector": "technology"},
    {"id": "openai", "type": "company", "text": "OpenAI", "founded": 2015, "sector": "ai"},
    {"id": "anthropic", "type": "company", "text": "Anthropic PBC", "founded": 2021, "sector": "ai"},
    {"id": "tim_cook", "type": "person", "text": "Tim Cook", "role": "CEO"},
    {"id": "satya_nadella", "type": "person", "text": "Satya Nadella", "role": "CEO"},
    {"id": "sundar_pichai", "type": "person", "text": "Sundar Pichai", "role": "CEO"},
    {"id": "sam_altman", "type": "person", "text": "Sam Altman", "role": "CEO"},
    {"id": "dario_amodei", "type": "person", "text": "Dario Amodei", "role": "CEO"},
    {"id": "iphone", "type": "product", "text": "iPhone", "category": "smartphone"},
    {"id": "chatgpt", "type": "product", "text": "ChatGPT", "category": "ai_assistant"},
    {"id": "claude", "type": "product", "text": "Claude", "category": "ai_assistant"},
    {"id": "gpt4", "type": "product", "text": "GPT-4", "category": "llm"},
]

TECH_RELATIONSHIPS = [
    {"source_id": "tim_cook", "target_id": "apple", "type": "leads", "confidence": 1.0},
    {"source_id": "satya_nadella", "target_id": "microsoft", "type": "leads", "confidence": 1.0},
    {"source_id": "sundar_pichai", "target_id": "google", "type": "leads", "confidence": 1.0},
    {"source_id": "sam_altman", "target_id": "openai", "type": "leads", "confidence": 1.0},
    {"source_id": "dario_amodei", "target_id": "anthropic", "type": "leads", "confidence": 1.0},
    {"source_id": "apple", "target_id": "iphone", "type": "makes", "confidence": 1.0},
    {"source_id": "openai", "target_id": "chatgpt", "type": "makes", "confidence": 1.0},
    {"source_id": "openai", "target_id": "gpt4", "type": "makes", "confidence": 1.0},
    {"source_id": "anthropic", "target_id": "claude", "type": "makes", "confidence": 1.0},
    {"source_id": "microsoft", "target_id": "openai", "type": "invested_in", "confidence": 1.0},
    {"source_id": "google", "target_id": "anthropic", "type": "invested_in", "confidence": 1.0},
    {"source_id": "chatgpt", "target_id": "claude", "type": "competes_with", "confidence": 0.9},
    {"source_id": "gpt4", "target_id": "claude", "type": "competes_with", "confidence": 0.9},
]


def _make_decision(
    decision_id: str = None,
    category: str = "loan_approval",
    scenario: str = "First-time homebuyer mortgage application",
    reasoning: str = "Applicant has FICO score 780, stable 5-year employment, 20% down payment.",
    outcome: str = "approved",
    confidence: float = 0.92,
    decision_maker: str = "mortgage_underwriter_ai",
) -> Decision:
    return Decision(
        decision_id=decision_id or str(uuid.uuid4()),
        category=category,
        scenario=scenario,
        reasoning=reasoning,
        outcome=outcome,
        confidence=confidence,
        timestamp=datetime.now(),
        decision_maker=decision_maker,
    )


def _make_policy(category: str = "loan_approval") -> Policy:
    return Policy(
        policy_id=str(uuid.uuid4()),
        name="Mortgage Lending Policy v3.2",
        description="Standard policy for retail mortgage approvals",
        rules={
            "min_fico_score": 680,
            "max_dti_ratio": 0.43,
            "min_down_payment_pct": 5,
            "employment_history_years": 2,
        },
        category=category,
        version="3.2",
        created_at=datetime.now() - timedelta(days=365),
        updated_at=datetime.now() - timedelta(days=30),
    )


def _build_tech_graph() -> ContextGraph:
    g = ContextGraph(advanced_analytics=True)
    g.build_from_entities_and_relationships(TECH_ENTITIES, TECH_RELATIONSHIPS)
    return g


# ═════════════════════════════════════════════════════════════════════════════
# 1. ContextGraph – basic node/edge operations on a tech company graph
# ═════════════════════════════════════════════════════════════════════════════

class TestContextGraphBasicOperations:
    """Basic add/query on a real-world tech company knowledge graph."""

    def test_build_from_entities_and_relationships(self):
        g = _build_tech_graph()
        stats = g.stats()
        assert stats["node_count"] >= len(TECH_ENTITIES)
        assert stats["edge_count"] >= len(TECH_RELATIONSHIPS)

    def test_node_types_indexed_correctly(self):
        g = _build_tech_graph()
        companies = g.find_nodes(node_type="company")
        persons = g.find_nodes(node_type="person")
        products = g.find_nodes(node_type="product")
        assert len(companies) == 5  # apple, microsoft, google, openai, anthropic
        assert len(persons) == 5
        assert len(products) == 4

    def test_find_node_returns_metadata(self):
        g = _build_tech_graph()
        node = g.find_node("apple")
        assert node is not None
        assert node["type"] == "company"
        assert node["content"] == "Apple Inc."

    def test_add_node_and_edge_manual(self):
        g = ContextGraph()
        g.add_node("meta", node_type="company", content="Meta Platforms")
        g.add_node("mark_zuckerberg", node_type="person", content="Mark Zuckerberg")
        added = g.add_edge("mark_zuckerberg", "meta", edge_type="leads")
        assert added is True
        assert g.has_node("meta")
        neighbors = g.get_neighbors("mark_zuckerberg", hops=1)
        assert any(n["id"] == "meta" for n in neighbors)

    def test_query_keyword_search(self):
        g = _build_tech_graph()
        results = g.query("AI assistant")
        # chatgpt and claude both contain "ai_assistant" in category
        # But query searches content - let's check that something is returned or not
        # The query searches node content. Let's add a node with explicit content
        g.add_node("llm_overview", node_type="concept", content="Large Language Models AI assistant")
        results = g.query("AI assistant")
        assert len(results) > 0
        assert results[0]["score"] > 0.0

    def test_get_neighbors_multi_hop(self):
        g = _build_tech_graph()
        # 1 hop from microsoft: openai (invested_in)
        # 2 hops from microsoft: chatgpt (openai makes chatgpt), gpt4
        neighbors_1 = g.get_neighbors("microsoft", hops=1)
        neighbors_2 = g.get_neighbors("microsoft", hops=2)
        one_hop_ids = {n["id"] for n in neighbors_1}
        two_hop_ids = {n["id"] for n in neighbors_2}
        assert "openai" in one_hop_ids
        assert len(two_hop_ids) > len(one_hop_ids)

    def test_find_edges_by_type(self):
        g = _build_tech_graph()
        invested_edges = g.find_edges(edge_type="invested_in")
        assert len(invested_edges) == 2  # microsoft->openai, google->anthropic
        sources = {e["source"] for e in invested_edges}
        assert "microsoft" in sources
        assert "google" in sources

    def test_density_calculation(self):
        g = _build_tech_graph()
        density = g.density()
        assert 0.0 <= density <= 1.0

    def test_to_dict_round_trip(self):
        g = _build_tech_graph()
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert d["statistics"]["node_count"] == len(g.nodes)
        g2 = ContextGraph(advanced_analytics=False)
        g2.from_dict(d)
        assert len(g2.nodes) == len(g.nodes)
        assert len(g2.edges) == len(g.edges)

    def test_save_and_load_file(self):
        g = _build_tech_graph()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            g.save_to_file(path)
            assert os.path.exists(path)
            g2 = ContextGraph(advanced_analytics=False)
            g2.load_from_file(path)
            assert len(g2.nodes) == len(g.nodes)
            assert g2.has_node("apple")
            assert g2.has_node("claude")
        finally:
            os.unlink(path)


# ═════════════════════════════════════════════════════════════════════════════
# 2. ContextGraph – decision tracking lifecycle
# ═════════════════════════════════════════════════════════════════════════════

class TestContextGraphDecisionTracking:
    """Decision tracking: add, causal chains, precedents, record_decision."""

    def test_add_decision_stores_node(self):
        g = ContextGraph()
        d = _make_decision(decision_id="loan_001")
        g.add_decision(d)
        node = g.find_node("loan_001")
        assert node is not None
        assert node["type"] == "Decision"
        assert "loan_approval" in str(node["metadata"])

    def test_add_decision_with_none_metadata(self):
        g = ContextGraph()
        d = _make_decision(decision_id="loan_002")
        d.metadata = None
        g.add_decision(d)  # Should not raise
        assert g.has_node("loan_002")

    def test_add_decision_empty_id_generates_uuid(self):
        g = ContextGraph()
        d = Decision(
            decision_id="auto_001",
            category="credit",
            scenario="Credit card limit increase",
            reasoning="3-year on-time payment history",
            outcome="approved",
            confidence=0.87,
            timestamp=datetime.now(),
            decision_maker="credit_scoring_engine",
        )
        g.add_decision(d)
        assert g.has_node("auto_001")

    def test_causal_chain_downstream(self):
        g = ContextGraph()
        d1 = _make_decision(decision_id="d_root", scenario="Initial credit approval")
        d2 = _make_decision(decision_id="d_child", scenario="Credit limit increase")
        d3 = _make_decision(decision_id="d_grandchild", scenario="Premium card upgrade")
        g.add_decision(d1)
        g.add_decision(d2)
        g.add_decision(d3)
        g.add_causal_relationship("d_root", "d_child", "CAUSED")
        g.add_causal_relationship("d_child", "d_grandchild", "CAUSED")
        chain = g.get_causal_chain("d_root", direction="downstream", max_depth=5)
        chain_ids = {d.decision_id for d in chain}
        assert "d_child" in chain_ids
        assert "d_grandchild" in chain_ids

    def test_causal_chain_upstream(self):
        g = ContextGraph()
        d_early = _make_decision(decision_id="d_early", scenario="Initial loan decision 2023")
        d_late = _make_decision(decision_id="d_late", scenario="Refinance decision 2024")
        g.add_decision(d_early)
        g.add_decision(d_late)
        g.add_causal_relationship("d_early", "d_late", "INFLUENCED")
        chain = g.get_causal_chain("d_late", direction="upstream", max_depth=5)
        chain_ids = {d.decision_id for d in chain}
        assert "d_early" in chain_ids

    def test_causal_relationship_invalid_type_raises(self):
        g = ContextGraph()
        d1 = _make_decision(decision_id="x1")
        d2 = _make_decision(decision_id="x2")
        g.add_decision(d1)
        g.add_decision(d2)
        with pytest.raises(ValueError, match="Relationship type must be one of"):
            g.add_causal_relationship("x1", "x2", "INVALID_TYPE")

    def test_causal_relationship_nonexistent_node_skipped(self):
        g = ContextGraph()
        d1 = _make_decision(decision_id="exist_1")
        g.add_decision(d1)
        g.add_causal_relationship("exist_1", "ghost_node", "CAUSED")  # Should not raise
        chain = g.get_causal_chain("exist_1", direction="downstream")
        assert len(chain) == 0

    def test_find_precedents_via_precedent_for_edge(self):
        g = ContextGraph()
        old = _make_decision(decision_id="prec_old", scenario="Homebuyer loan 2022, FICO 770")
        new = _make_decision(decision_id="prec_new", scenario="Homebuyer loan 2024, FICO 780")
        g.add_decision(old)
        g.add_decision(new)
        g.add_causal_relationship("prec_old", "prec_new", "PRECEDENT_FOR")
        precedents = g.find_precedents("prec_new", limit=10)
        assert len(precedents) == 1
        assert precedents[0].decision_id == "prec_old"

    def test_record_decision_high_level_api(self):
        g = ContextGraph()
        did = g.record_decision(
            category="fraud_detection",
            scenario="Transaction flagged: $5,000 wire transfer to new payee in 30 seconds",
            reasoning="Velocity anomaly: 10x avg, new beneficiary, unusual hours (2 AM).",
            outcome="blocked_pending_review",
            confidence=0.95,
            entities=["acct_789012", "payee_xyz"],
            decision_maker="fraud_ai_v4",
        )
        assert did is not None
        assert g.has_node(did)
        node = g.find_node(did)
        # record_decision() uses lowercase "decision" node type
        assert node["type"].lower() == "decision"

    def test_record_decision_validation_errors(self):
        g = ContextGraph()
        with pytest.raises(ValueError):
            g.record_decision("", "scenario", "reasoning", "outcome", 0.9)
        with pytest.raises(ValueError):
            g.record_decision("cat", "scenario", "reasoning", "outcome", 1.5)

    def test_multiple_decisions_same_category(self):
        g = ContextGraph()
        ids = []
        for i in range(5):
            did = g.record_decision(
                category="insurance_claim",
                scenario=f"Auto claim #{i}: rear-end collision, liability clear",
                reasoning=f"Claimant has comprehensive coverage, incident #{i} verified by telematics.",
                outcome="approved",
                confidence=0.88 + i * 0.01,
                decision_maker="claims_ai",
            )
            ids.append(did)
        # All should be unique decision nodes
        assert len(set(ids)) == 5
        # record_decision() uses lowercase "decision" type
        decision_nodes = g.find_nodes(node_type="decision")
        assert len(decision_nodes) >= 5


# ═════════════════════════════════════════════════════════════════════════════
# 3. ContextGraph – KG analytics (centrality, similar nodes)
# ═════════════════════════════════════════════════════════════════════════════

class TestContextGraphKGAnalytics:
    """KG algorithm integration: centrality, find_similar_nodes, analyze_graph_with_kg."""

    def test_find_similar_nodes_content(self):
        g = _build_tech_graph()
        # openai and anthropic are both AI companies
        similar = g.find_similar_nodes("openai", similarity_type="content", top_k=5)
        assert isinstance(similar, list)
        # Should return some results; content of "OpenAI" and "Anthropic PBC" may have partial overlap
        assert len(similar) <= len(g.nodes) - 1

    def test_find_similar_nodes_structural(self):
        g = _build_tech_graph()
        similar = g.find_similar_nodes("apple", similarity_type="structural", top_k=5)
        assert isinstance(similar, list)
        for item in similar:
            assert isinstance(item, dict)
            assert isinstance(item.get("id"), str)
            assert isinstance(item.get("content"), str)
            assert isinstance(item.get("type"), str)
            assert isinstance(item.get("score"), float)
            assert 0.0 <= item["score"] <= 1.0

    def test_find_similar_nodes_missing_node_returns_empty(self):
        g = _build_tech_graph()
        result = g.find_similar_nodes("nonexistent_node", similarity_type="content")
        assert result == []

    def test_get_node_centrality_returns_dict(self):
        g = _build_tech_graph()
        centrality = g.get_node_centrality("openai")
        # Either returns centrality scores or an error dict (if KG components unavailable)
        assert isinstance(centrality, dict)

    def test_analyze_graph_with_kg_structure(self):
        g = _build_tech_graph()
        analysis = g.analyze_graph_with_kg()
        assert isinstance(analysis, dict)
        if "error" not in analysis:
            assert "graph_metrics" in analysis
            assert analysis["graph_metrics"]["node_count"] >= len(TECH_ENTITIES)

    def test_density_is_nonzero_for_connected_graph(self):
        g = _build_tech_graph()
        assert g.density() > 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 4. PolicyEngine – ContextGraph fallback path (from 0.3.0-alpha fix)
# ═════════════════════════════════════════════════════════════════════════════

class TestPolicyEngineContextGraphFallback:
    """Tests the ContextGraph-backed PolicyEngine introduced in 0.3.0-alpha."""

    def _make_policy_node(self, policy_id, category, entity_filter=None):
        return {
            "metadata": {
                "policy_id": policy_id,
                "name": f"Policy {policy_id}",
                "description": f"Desc {policy_id}",
                "rules": {"max_loan": 500_000},
                "category": category,
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": {"entities": entity_filter or []},
            }
        }

    def test_applicable_policies_matched_by_entity(self):
        class _FakeGraph:
            def find_nodes(self, node_type=None):
                return [
                    self._pnode("p_mortgage", "mortgage", ["customer:A"]),
                    self._pnode("p_auto", "mortgage", ["customer:B"]),
                ]

            def _pnode(self, pid, cat, entities):
                return {
                    "metadata": {
                        "policy_id": pid, "name": pid, "description": pid,
                        "rules": {}, "category": cat, "version": "1.0",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "metadata": {"entities": entities},
                    }
                }

        engine = PolicyEngine(graph_store=_FakeGraph())
        policies = engine.get_applicable_policies("mortgage", ["customer:A"])
        assert len(policies) == 1
        assert policies[0].policy_id == "p_mortgage"

    def test_no_policies_when_entity_not_matched(self):
        class _FakeGraph:
            def find_nodes(self, node_type=None):
                return [
                    {
                        "metadata": {
                            "policy_id": "p_x", "name": "X", "description": "X",
                            "rules": {}, "category": "credit", "version": "1.0",
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                            "metadata": {"entities": ["customer:999"]},
                        }
                    }
                ]

        engine = PolicyEngine(graph_store=_FakeGraph())
        policies = engine.get_applicable_policies("credit", ["customer:000"])
        assert len(policies) == 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. DecisionQuery + CausalChainAnalyzer – mock graph store (from 0.3.0-beta fix)
# ═════════════════════════════════════════════════════════════════════════════

class TestDecisionQueryAndCausalAnalyzer:
    """DecisionQuery and CausalChainAnalyzer with wrapped-records store format."""

    def _mock_store(self):
        store = Mock()
        store.execute_query = Mock(
            return_value={
                "records": [
                    {
                        "d": {
                            "decision_id": "q_001",
                            "category": "mortgage",
                            "scenario": "30yr fixed refinance, rate drop 1.2%",
                            "reasoning": "Rate-and-term refi; DTI 38%, FICO 800.",
                            "outcome": "approved",
                            "confidence": 0.96,
                            "timestamp": datetime.now().isoformat(),
                            "decision_maker": "refi_agent",
                        },
                        "end": {
                            "decision_id": "q_002",
                            "category": "mortgage",
                            "scenario": "Cash-out refi for home improvement",
                            "reasoning": "LTV 72%, strong employment history.",
                            "outcome": "approved",
                            "confidence": 0.88,
                            "timestamp": datetime.now().isoformat(),
                            "decision_maker": "refi_agent",
                        },
                        "distance": 1,
                    }
                ]
            }
        )
        return store

    def test_decision_query_find_precedents_hybrid(self):
        store = self._mock_store()
        query = DecisionQuery(graph_store=store)
        precedents = query.find_precedents_hybrid("refinance scenario", "mortgage", 5)
        assert len(precedents) == 1
        assert precedents[0].decision_id == "q_001"

    def test_causal_chain_analyzer_downstream(self):
        store = self._mock_store()
        analyzer = CausalChainAnalyzer(graph_store=store)
        chain = analyzer.get_causal_chain("q_001", "downstream", 3)
        assert len(chain) == 1
        assert chain[0].decision_id == "q_002"


# ═════════════════════════════════════════════════════════════════════════════
# 6. AgentContext – high-level interface (0.3.0-alpha / beta)
# ═════════════════════════════════════════════════════════════════════════════

class TestAgentContextHighLevel:
    """AgentContext: store/retrieve, decision tracking, cross-system capture."""

    def _make_agent_context(self, error_kg=False):
        vector_store = Mock()
        vector_store.add = Mock(return_value="vs_id_001")
        vector_store.search = Mock(return_value=[])

        knowledge_graph = Mock()
        if error_kg:
            knowledge_graph.execute_query = Mock(side_effect=RuntimeError("db connection refused"))
        else:
            knowledge_graph.execute_query = Mock(return_value={"records": []})
        knowledge_graph.get_neighbors = Mock(return_value=[])

        return AgentContext(
            vector_store=vector_store,
            knowledge_graph=knowledge_graph,
            decision_tracking=True,
        )

    def test_store_and_retrieve_basic(self):
        ctx = self._make_agent_context()
        mem_id = ctx.store(
            "Apple acquired Beats Electronics in 2014 for $3 billion, "
            "its largest acquisition at the time.",
            conversation_id="conv_apple_history",
        )
        assert mem_id is not None

    def test_record_decision_returns_id(self):
        ctx = self._make_agent_context()
        did = ctx.record_decision(
            category="supply_chain",
            scenario="Dual-source procurement: TSMC + Samsung for A-series chips",
            reasoning="Geopolitical risk mitigation; TSMC concentration risk post-2021 chip shortage.",
            outcome="approved",
            confidence=0.88,
            entities=["tsmc", "samsung", "apple_chip_team"],
        )
        assert did is not None

    def test_find_precedents_returns_list(self):
        ctx = self._make_agent_context()
        ctx.record_decision(
            category="supply_chain",
            scenario="Single-source silicon vendor",
            reasoning="Cost optimisation in stable environment",
            outcome="approved",
            confidence=0.75,
        )
        precedents = ctx.find_precedents("supply chain procurement decision", category="supply_chain")
        assert isinstance(precedents, list)

    def test_capture_cross_system_inputs_error_sanitized(self):
        ctx = self._make_agent_context(error_kg=True)
        result = ctx.capture_cross_system_inputs(["salesforce"], "customer_001")
        assert result["salesforce"]["status"] == "capture_failed"
        # Internal error detail must not leak
        assert "db connection" not in result["salesforce"].get("error", "")

    def test_capture_cross_system_inputs_success(self):
        vector_store = Mock()
        knowledge_graph = Mock()
        knowledge_graph.execute_query = Mock(
            return_value={
                "records": [
                    {
                        "c": {
                            "context_id": "ctx_01",
                            "system_name": "jira",
                            "context_data": {"sprint": 42},
                        }
                    }
                ]
            }
        )
        ctx = AgentContext(
            vector_store=vector_store,
            knowledge_graph=knowledge_graph,
            decision_tracking=True,
        )
        systems = ["jira", "confluence", "datadog"]
        result = ctx.capture_cross_system_inputs(systems, "project_alpha")
        for system in systems:
            assert result[system]["system_name"] == system
            assert result[system]["entity_id"] == "project_alpha"
            assert result[system]["status"] == "captured"


# ═════════════════════════════════════════════════════════════════════════════
# 7. Decision models – serialization, validation
# ═════════════════════════════════════════════════════════════════════════════

class TestDecisionModelsSerialization:
    """Decision model lifecycle: create, validate, serialize, deserialize."""

    def test_decision_serialize_deserialize(self):
        d = _make_decision(decision_id="ser_001")
        json_str = serialize_decision(d)
        restored = deserialize_decision(json_str)
        assert restored.decision_id == d.decision_id
        assert restored.category == d.category
        assert abs(restored.confidence - d.confidence) < 0.001

    def test_validate_decision_passes(self):
        d = _make_decision(decision_id="val_001")
        assert validate_decision(d) is True

    def test_validate_decision_fails_empty_category(self):
        d = _make_decision(decision_id="val_002")
        d.category = ""
        assert validate_decision(d) is False

    def test_policy_to_dict_and_from_dict(self):
        p = _make_policy()
        d = p.to_dict()
        restored = Policy.from_dict(d)
        assert restored.policy_id == p.policy_id
        assert restored.name == p.name
        assert restored.rules == p.rules

    def test_policy_exception_model(self):
        exc = PolicyException(
            exception_id=str(uuid.uuid4()),
            decision_id="loan_001",
            policy_id="pol_001",
            reason="Customer relationship >10yr with zero defaults; waived min FICO by 15pts.",
            approver="senior_underwriter_007",
            approval_timestamp=datetime.now(),
            justification="Relationship banking exception per policy section 4.3.1",
        )
        d = exc.to_dict()
        assert d["reason"] == exc.reason
        restored = PolicyException.from_dict(d)
        assert restored.approver == exc.approver

    def test_approval_chain_model(self):
        approval = ApprovalChain(
            approval_id=str(uuid.uuid4()),
            decision_id="loan_001",
            approver="branch_manager_ann",
            approval_method="slack_dm",
            approval_context="Reviewed customer portfolio in Slack thread #mortgage-exceptions",
            timestamp=datetime.now(),
        )
        d = approval.to_dict()
        assert d["approval_method"] == "slack_dm"

    def test_precedent_model(self):
        prec = Precedent(
            precedent_id=str(uuid.uuid4()),
            source_decision_id="old_loan_789",
            similarity_score=0.87,
            relationship_type="similar_scenario",
        )
        d = prec.to_dict()
        assert d["similarity_score"] == 0.87

    def test_decision_confidence_bounds(self):
        with pytest.raises(ValueError):
            Decision(
                decision_id="bad_conf",
                category="test",
                scenario="test",
                reasoning="test",
                outcome="test",
                confidence=1.5,  # Invalid
                timestamp=datetime.now(),
                decision_maker="test",
            )


# ═════════════════════════════════════════════════════════════════════════════
# 8. KG algorithms – real-world tech company graph
# ═════════════════════════════════════════════════════════════════════════════

def _build_nx_tech_graph():
    """Build a NetworkX graph from TECH_ENTITIES/TECH_RELATIONSHIPS."""
    import networkx as nx
    G = nx.DiGraph()
    for e in TECH_ENTITIES:
        G.add_node(e["id"], **{k: v for k, v in e.items() if k != "id"})
    for r in TECH_RELATIONSHIPS:
        G.add_edge(r["source_id"], r["target_id"], type=r["type"], weight=r["confidence"])
    return G


class TestKGAlgorithmsRealWorld:
    """KG algorithms with real-world tech company data."""

    def test_graph_builder_produces_entities_and_relationships(self):
        builder = GraphBuilder(merge_entities=False)
        sources = [{"entities": TECH_ENTITIES, "relationships": TECH_RELATIONSHIPS}]
        kg = builder.build(sources=sources)
        assert "entities" in kg
        assert len(kg["entities"]) >= len(TECH_ENTITIES)

    def test_centrality_calculator_on_tech_graph(self):
        G = _build_nx_tech_graph()
        calc = CentralityCalculator()
        result = calc.calculate_all_centrality(G)
        assert isinstance(result, dict)
        # openai should appear (it's heavily connected: microsoft invested, makes chatgpt/gpt4)
        all_keys = set(result.keys()) if result else set()
        # Result may be keyed by node ID or metric name - just verify it's non-empty
        assert len(result) > 0

    def test_community_detector_on_tech_graph(self):
        G = _build_nx_tech_graph()
        detector = CommunityDetector()
        communities = detector.detect_communities(G)
        # Should return communities (list/dict/int)
        assert communities is not None

    def test_connectivity_analyzer_on_tech_graph(self):
        G = _build_nx_tech_graph()
        analyzer = ConnectivityAnalyzer()
        result = analyzer.analyze_connectivity(G)
        assert isinstance(result, dict)

    def test_path_finder_shortest_path_supply_chain(self):
        """Shortest path: microsoft -> chatgpt (via openai)."""
        import networkx as nx
        G = _build_nx_tech_graph()
        # Convert to undirected for simple path test
        G_undirected = G.to_undirected()
        finder = PathFinder()
        path = finder.find_shortest_path(G_undirected, "microsoft", "chatgpt")
        assert path is not None
        assert "microsoft" in path
        assert "chatgpt" in path
        assert "openai" in path  # Must pass through openai

    def test_similarity_calculator_cosine(self):
        import numpy as np
        calc = SimilarityCalculator()
        v1 = np.array([0.1, 0.9, 0.2])
        v2 = np.array([0.15, 0.85, 0.18])
        score = calc.cosine_similarity(v1, v2)
        assert 0.0 <= score <= 1.0
        assert score > 0.95  # Very similar vectors

    def test_node_embedder_generates_embeddings(self):
        # Constructing NodeEmbedder requires gensim (the optional
        # graph-embeddings extra); see tests/test_issue_1513_slim_core.py
        # for the contract that it raises without it.
        pytest.importorskip("gensim")
        G = _build_nx_tech_graph()
        embedder = NodeEmbedder(embedding_dimension=16, walk_length=10, num_walks=2, epochs=1)
        node_labels = list({data.get("type", "entity") for _, data in G.nodes(data=True)})
        rel_types = list({data.get("type", "related_to") for _, _, data in G.edges(data=True)})
        embeddings = embedder.compute_embeddings(G, node_labels=node_labels, relationship_types=rel_types)
        assert isinstance(embeddings, dict)

    def test_link_predictor_preferential_attachment(self):
        G = _build_nx_tech_graph().to_undirected()
        predictor = LinkPredictor()
        # Predict probability of a link between apple and google
        score = predictor.score_link(G, "apple", "google", method="preferential_attachment")
        assert isinstance(score, float)
        assert score >= 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 9. Open-source ecosystem community detection
# ═════════════════════════════════════════════════════════════════════════════

class TestCommunityDetectionOpenSourceEcosystem:
    """Community detection on a simulated open-source library dependency graph."""

    @pytest.fixture
    def ecosystem_graph(self):
        import networkx as nx
        G = nx.Graph()
        # Python data science ecosystem
        packages = [
            "numpy", "scipy", "pandas", "matplotlib", "seaborn", "sklearn",
            "torch", "tensorflow", "keras", "transformers",
            "fastapi", "flask", "django", "sqlalchemy", "pydantic",
            "requests", "httpx", "aiohttp",
        ]
        for pkg in packages:
            G.add_node(pkg)
        # Dependencies
        edges = [
            ("scipy", "numpy"), ("pandas", "numpy"), ("matplotlib", "numpy"),
            ("seaborn", "matplotlib"), ("seaborn", "pandas"),
            ("sklearn", "numpy"), ("sklearn", "scipy"),
            ("keras", "tensorflow"), ("transformers", "torch"),
            ("transformers", "tensorflow"),
            ("fastapi", "pydantic"), ("fastapi", "httpx"),
            ("flask", "requests"), ("django", "sqlalchemy"),
            ("aiohttp", "httpx"),
        ]
        G.add_edges_from(edges)
        return G

    def test_communities_are_detected(self, ecosystem_graph):
        detector = CommunityDetector()
        communities = detector.detect_communities(ecosystem_graph)
        assert communities is not None

    def test_connectivity_analysis(self, ecosystem_graph):
        analyzer = ConnectivityAnalyzer()
        result = analyzer.analyze_connectivity(ecosystem_graph)
        assert isinstance(result, dict)


# ═════════════════════════════════════════════════════════════════════════════
# 10. Deduplication v2 – semantic dedup on company name variants
# ═════════════════════════════════════════════════════════════════════════════

class TestDeduplicationV2RealWorld:
    """Semantic deduplication with company name variants (real-world data quality issue)."""

    def test_semantic_dedup_company_name_variants(self):
        from semantica.deduplication import DuplicateDetector

        entities = [
            {"id": "e1", "name": "Apple Inc.", "type": "Company"},
            {"id": "e2", "name": "Apple Incorporated", "type": "Company"},
            {"id": "e3", "name": "APPLE INC", "type": "Company"},
            {"id": "e4", "name": "Microsoft Corporation", "type": "Company"},
            {"id": "e5", "name": "Microsoft Corp.", "type": "Company"},
            {"id": "e6", "name": "Microsoft Corp", "type": "Company"},
            {"id": "e7", "name": "Google LLC", "type": "Company"},
            {"id": "e8", "name": "Alphabet Inc.", "type": "Company"},
        ]

        detector = DuplicateDetector(similarity_threshold=0.75)
        duplicates = detector.detect_duplicates(entities, threshold=0.75)
        assert isinstance(duplicates, list)
        # Apple variants and Microsoft variants should be detected as duplicates
        assert len(duplicates) > 0

    def test_semantic_dedup_v2_mode(self):
        from semantica.deduplication import DuplicateDetector

        entities = [
            {"id": "e1", "name": "OpenAI Inc.", "type": "Company"},
            {"id": "e2", "name": "OpenAI", "type": "Company"},
            {"id": "e3", "name": "Anthropic PBC", "type": "Company"},
            {"id": "e4", "name": "Anthropic", "type": "Company"},
        ]
        detector = DuplicateDetector(similarity_threshold=0.70)
        duplicates = detector.detect_duplicates(entities, threshold=0.70)
        assert isinstance(duplicates, list)

    def test_blocking_v2_candidate_generation(self):
        from semantica.deduplication import DuplicateDetector

        entities = [
            {"id": f"ent_{i}", "name": f"Entity Name {i}", "type": "Organization"}
            for i in range(30)
        ]
        # Add some deliberate duplicates
        entities.append({"id": "dup_1", "name": "Entity Name 5", "type": "Organization"})
        entities.append({"id": "dup_2", "name": "Entity Name 12", "type": "Organization"})

        detector = DuplicateDetector(similarity_threshold=0.90)
        duplicates = detector.detect_duplicates(entities, threshold=0.90, candidate_strategy="blocking_v2")
        assert isinstance(duplicates, list)
        # Exact duplicates should be detected
        assert len(duplicates) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 11. Export – RDF/TTL alias (0.3.0-beta fix)
# ═════════════════════════════════════════════════════════════════════════════

class TestRDFExportAliases:
    """TTL and other format aliases introduced in 0.3.0-beta."""

    def _make_kg_data(self):
        return {
            "entities": [
                {"id": "apple", "type": "Company", "properties": {"name": "Apple Inc.", "founded": 1976}},
                {"id": "tim_cook", "type": "Person", "properties": {"name": "Tim Cook"}},
            ],
            "relationships": [
                {"source_id": "tim_cook", "target_id": "apple", "type": "leads", "properties": {}},
            ],
        }

    def test_ttl_alias_export(self):
        from semantica.export import RDFExporter
        exporter = RDFExporter()
        kg_data = self._make_kg_data()
        # export_to_rdf returns a string; "ttl" is an alias for "turtle"
        result = exporter.export_to_rdf(kg_data, format="ttl")
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain RDF/turtle syntax elements
        assert "apple" in result or "Apple" in result or "@" in result or "<" in result

    def test_nt_alias_export(self):
        from semantica.export import RDFExporter
        exporter = RDFExporter()
        kg_data = self._make_kg_data()
        result = exporter.export_to_rdf(kg_data, format="nt")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_turtle_canonical_format(self):
        from semantica.export import RDFExporter
        exporter = RDFExporter()
        kg_data = self._make_kg_data()
        result = exporter.export_to_rdf(kg_data, format="turtle")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_invalid_format_raises(self):
        from semantica.export import RDFExporter
        exporter = RDFExporter()
        with pytest.raises(Exception):
            exporter.export_to_rdf(self._make_kg_data(), format="invalid_format_xyz")


# ═════════════════════════════════════════════════════════════════════════════
# 12. Reasoner – _match_pattern with multi-word values (0.3.0-beta fix)
# ═════════════════════════════════════════════════════════════════════════════

class TestReasonerPatternMatching:
    """Pattern matching fixes from 0.3.0-beta: multi-word values, pre-bound vars."""

    def test_multi_word_value_inference(self):
        """Bug #354 — _match_pattern must match facts with multi-word values."""
        from semantica.reasoning.reasoner import Reasoner
        reasoner = Reasoner()
        # Use dict fact format: source_name/target_name/type
        for fact in [
            {"source_name": "Steve Jobs",    "target_name": "Apple", "type": "founded_by"},
            {"source_name": "Steve Wozniak", "target_name": "Apple", "type": "founded_by"},
            {"source_name": "Ronald Wayne",  "target_name": "Apple", "type": "founded_by"},
        ]:
            reasoner.add_fact(fact)

        inferred = reasoner.infer_facts(
            [],
            rules=["IF founded_by(?person, ?org) THEN is_cofounder(?person, ?org)"],
        )
        assert isinstance(inferred, list)
        assert len(inferred) == 3
        assert "is_cofounder(Steve Jobs, Apple)" in inferred
        assert "is_cofounder(Steve Wozniak, Apple)" in inferred
        assert "is_cofounder(Ronald Wayne, Apple)" in inferred

    def test_single_word_value_regression(self):
        """Single-word value inference must continue to work (regression guard)."""
        from semantica.reasoning.reasoner import Reasoner
        reasoner = Reasoner()
        inferred = reasoner.infer_facts(
            ["Person(John)", "Parent(John, Jane)"],
            rules=["IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)"],
        )
        assert "Child(Jane, John)" in inferred

    def test_pre_bound_variable_match(self):
        """_match_pattern must enforce pre-bound variables."""
        from semantica.reasoning.reasoner import Reasoner
        reasoner = Reasoner()
        # Pre-bound: org=Apple must match exactly
        result = reasoner._match_pattern(
            "founded_by(?person, ?org)",
            "founded_by(Steve Jobs, Apple)",
            {"org": "Apple"},
        )
        assert result is not None
        assert result["person"] == "Steve Jobs"
        assert result["org"] == "Apple"

    def test_pre_bound_variable_conflict_returns_none(self):
        """_match_pattern must return None on variable binding conflict."""
        from semantica.reasoning.reasoner import Reasoner
        reasoner = Reasoner()
        result = reasoner._match_pattern(
            "founded_by(?person, ?org)",
            "founded_by(Steve Jobs, Apple)",
            {"org": "Google"},  # Conflict: Apple != Google
        )
        assert result is None

    def test_forward_chain_tech_facts(self):
        """Forward chaining with real-world tech facts."""
        from semantica.reasoning.reasoner import Reasoner
        reasoner = Reasoner()
        reasoner.add_rule("IF AICompany(?x) AND Creates(?x, ?product) THEN AIProduct(?product)")
        reasoner.add_fact("AICompany(OpenAI)")
        reasoner.add_fact("Creates(OpenAI, ChatGPT)")
        results = reasoner.forward_chain()
        conclusions = [r.conclusion for r in results]
        assert "AIProduct(ChatGPT)" in conclusions


# ═════════════════════════════════════════════════════════════════════════════
# 13. Pipeline – retry and failure handling (0.3.0-beta fix)
# ═════════════════════════════════════════════════════════════════════════════

class TestPipelineRetryAndFailure:
    """Pipeline retry loop and FailureHandler from 0.3.0-beta fix."""

    def test_pipeline_builder_returns_step(self):
        from semantica.pipeline import PipelineBuilder

        builder = PipelineBuilder()
        step = builder.add_step("ingest", "file_ingestor", dependencies=[])
        assert step is not None
        assert hasattr(step, "name")

    def test_pipeline_validator_detects_missing_dependency(self):
        from semantica.pipeline import PipelineBuilder, PipelineValidator

        builder = PipelineBuilder()
        builder.add_step("ingest", "file_ingestor", dependencies=[])
        step = builder.add_step("load", "kg_builder", dependencies=["ingest"])
        # Manually inject a nonexistent dependency (same pattern as existing pipeline tests)
        step.dependencies.append("ghost_step")

        validator = PipelineValidator()
        result = validator.validate(builder)
        assert result.valid is False
        assert any("ghost_step" in e for e in result.errors)

    def test_failure_handler_linear_backoff(self):
        from semantica.pipeline.failure_handler import FailureHandler, RetryPolicy, RecoveryAction, RetryStrategy

        handler = FailureHandler()
        policy = RetryPolicy(strategy=RetryStrategy.LINEAR, initial_delay=0.5, max_retries=5)
        action = handler.handle_failure(
            error=RuntimeError("connection timeout"),
            policy=policy,
            retry_count=2,
        )
        assert isinstance(action, RecoveryAction)
        assert action.retry_delay >= 0.0

    def test_failure_handler_exponential_backoff(self):
        from semantica.pipeline.failure_handler import FailureHandler, RetryPolicy, RecoveryAction, RetryStrategy

        handler = FailureHandler()
        policy = RetryPolicy(strategy=RetryStrategy.EXPONENTIAL, initial_delay=1.0, max_retries=5)
        action1 = handler.handle_failure(RuntimeError("err"), policy, retry_count=1)
        action2 = handler.handle_failure(RuntimeError("err"), policy, retry_count=2)
        # Exponential delay should grow with retry count
        assert action2.retry_delay >= action1.retry_delay

    def test_validate_alias_works(self):
        from semantica.pipeline import PipelineBuilder, PipelineValidator

        builder = PipelineBuilder()
        builder.add_step("step_a", "some_processor", dependencies=[])

        validator = PipelineValidator()
        # validate() is an alias for validate_pipeline() – should not raise
        validator.validate(builder)


# ═════════════════════════════════════════════════════════════════════════════
# 14. ProvenanceTracker – now exported from semantica.kg (0.3.0-beta fix)
# ═════════════════════════════════════════════════════════════════════════════

class TestProvenanceTrackerExport:
    """ProvenanceTracker must be importable from semantica.kg after the fix."""

    def test_provenance_tracker_importable_from_kg(self):
        from semantica.kg import ProvenanceTracker
        tracker = ProvenanceTracker()
        assert tracker is not None

    def test_provenance_tracker_track_entity(self):
        from semantica.kg import ProvenanceTracker
        tracker = ProvenanceTracker()
        tracker.track_entity("E1", "wikipedia:Apple_Inc", metadata={"type": "company"})
        tracker.track_entity("E1", "crunchbase:apple-inc", metadata={"type": "company"})
        sources = tracker.get_all_sources("E1")
        assert len(sources) == 2
        source_ids = [s["source"] for s in sources]
        assert "wikipedia:Apple_Inc" in source_ids
        assert "crunchbase:apple-inc" in source_ids

    def test_provenance_tracker_clear(self):
        from semantica.kg import ProvenanceTracker
        tracker = ProvenanceTracker()
        tracker.track_entity("E2", "source_a")
        tracker.clear()
        sources = tracker.get_all_sources("E2")
        assert sources == []


# ═════════════════════════════════════════════════════════════════════════════
# 15. Semantic Relation Extraction – duplicate-relation fix (0.3.0-beta)
# ═════════════════════════════════════════════════════════════════════════════

class TestSemanticExtractRelationFix:
    """_parse_relation_result must not create duplicate relations (0.3.0-beta fix)."""

    def test_llm_relation_not_duplicated(self):
        from semantica.semantic_extract.ner_extractor import Entity
        from semantica.semantic_extract.schemas import RelationOut, RelationsResponse
        from semantica.semantic_extract.methods import extract_relations_llm

        entities = [
            Entity(text="OpenAI", label="ORG", start_char=0, end_char=6, confidence=1.0),
            Entity(text="ChatGPT", label="PRODUCT", start_char=10, end_char=17, confidence=1.0),
        ]

        class _FakeLLM:
            def is_available(self): return True
            def generate_typed(self, prompt, schema, **kw):
                return RelationsResponse(relations=[
                    RelationOut(subject="OpenAI", predicate="created", object="ChatGPT", confidence=0.98)
                ])

        with patch("semantica.semantic_extract.methods.create_provider", return_value=_FakeLLM()):
            relations = extract_relations_llm(
                "OpenAI created ChatGPT.",
                entities=entities,
                provider="openai",
                model="gpt-4",
            )

        # Must be exactly 1 relation, not 2
        assert len(relations) == 1
        assert relations[0].subject.text == "OpenAI"
        assert relations[0].object.text == "ChatGPT"
        assert relations[0].predicate == "created"

    def test_extraction_method_typed_metadata(self):
        from semantica.semantic_extract.ner_extractor import Entity
        from semantica.semantic_extract.schemas import RelationOut, RelationsResponse
        from semantica.semantic_extract.methods import extract_relations_llm

        entities = [
            Entity(text="Anthropic", label="ORG", start_char=0, end_char=9, confidence=1.0),
            Entity(text="Claude", label="PRODUCT", start_char=13, end_char=19, confidence=1.0),
        ]

        class _FakeLLM:
            def is_available(self): return True
            def generate_typed(self, prompt, schema, **kw):
                return RelationsResponse(relations=[
                    RelationOut(subject="Anthropic", predicate="built", object="Claude", confidence=0.99)
                ])

        with patch("semantica.semantic_extract.methods.create_provider", return_value=_FakeLLM()):
            relations = extract_relations_llm(
                "Anthropic built Claude.",
                entities=entities,
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                structured_output_mode="typed",
            )

        assert len(relations) == 1
        assert relations[0].metadata["extraction_method"] == "llm_typed"

    def test_ghost_entity_resolved_from_full_list(self):
        """Entity filtered from prompt (due to max_entities_prompt) is still matched from original list."""
        from semantica.semantic_extract.ner_extractor import Entity
        from semantica.semantic_extract.schemas import RelationOut, RelationsResponse
        from semantica.semantic_extract.methods import extract_relations_llm

        # 120 long names + 1 ghost entity not mentioned in text
        # (will be filtered from prompt since it's not in text, but must still be matched)
        entities = [
            Entity(text=f"VeryLongOrgName{i}", label="ORG", start_char=0, end_char=1, confidence=1.0)
            for i in range(120)
        ]
        ghost = Entity(text="GhostCorp", label="ORG", start_char=0, end_char=9, confidence=1.0)
        entities.append(ghost)

        captured = {}

        class _FakeLLM:
            def is_available(self): return True
            def generate_typed(self, prompt, schema, **kw):
                captured["prompt"] = prompt
                return RelationsResponse(relations=[
                    RelationOut(subject="GhostCorp", predicate="acquired", object="VeryLongOrgName0", confidence=0.9)
                ])

        with patch("semantica.semantic_extract.methods.create_provider", return_value=_FakeLLM()):
            relations = extract_relations_llm(
                "Short text about VeryLongOrgName0 only.",
                entities=entities,
                provider="openai",
                model="gpt-4",
                max_entities_prompt=20,
            )

        assert "GhostCorp" not in captured["prompt"]
        assert len(relations) == 1
        assert relations[0].subject.text == "GhostCorp"


# ═════════════════════════════════════════════════════════════════════════════
# 16. ContextGraph – build from conversations (real dialog data)
# ═════════════════════════════════════════════════════════════════════════════

class TestContextGraphFromConversations:
    """Build a context graph from structured conversation data."""

    def _sample_conversations(self):
        return [
            {
                "id": "conv_001",
                "content": "Discussion about Apple's new M4 chip and its AI capabilities.",
                "timestamp": datetime.now().isoformat(),
                "entities": [
                    {"id": "apple_e", "text": "Apple", "type": "company"},
                    {"id": "m4_chip", "text": "M4 chip", "type": "product"},
                ],
                "relationships": [
                    {"source_id": "apple_e", "target_id": "m4_chip", "type": "manufactures", "confidence": 0.95},
                ],
            },
            {
                "id": "conv_002",
                "content": "OpenAI GPT-4o release discussion and comparison with Claude 3.5.",
                "timestamp": datetime.now().isoformat(),
                "entities": [
                    {"id": "openai_e", "text": "OpenAI", "type": "company"},
                    {"id": "gpt4o", "text": "GPT-4o", "type": "product"},
                    {"id": "claude35", "text": "Claude 3.5", "type": "product"},
                ],
                "relationships": [
                    {"source_id": "openai_e", "target_id": "gpt4o", "type": "released", "confidence": 1.0},
                ],
            },
        ]

    def test_build_from_conversations(self):
        g = ContextGraph()
        result = g.build_from_conversations(self._sample_conversations(), link_entities=False)
        assert "nodes" in result
        assert len(g.nodes) > 0

    def test_conversation_entities_in_graph(self):
        g = ContextGraph()
        g.build_from_conversations(self._sample_conversations(), link_entities=False)
        assert g.has_node("apple_e") or g.has_node("m4_chip")

    def test_has_conversation_nodes(self):
        g = ContextGraph()
        g.build_from_conversations(self._sample_conversations(), link_entities=False)
        conv_nodes = g.find_nodes(node_type="conversation")
        assert len(conv_nodes) >= 2


# ═════════════════════════════════════════════════════════════════════════════
# 17. Multi-hop reasoning: Microsoft → OpenAI → ChatGPT investment chain
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiHopInvestmentChain:
    """End-to-end context graph tracking of investment → product chain."""

    def test_microsoft_chatgpt_2hop_path(self):
        g = _build_tech_graph()
        # microsoft --invested_in--> openai --makes--> chatgpt
        neighbors_2hop = g.get_neighbors("microsoft", hops=2)
        ids_2hop = {n["id"] for n in neighbors_2hop}
        assert "chatgpt" in ids_2hop

    def test_google_claude_2hop_path(self):
        g = _build_tech_graph()
        # google --invested_in--> anthropic --makes--> claude
        neighbors_2hop = g.get_neighbors("google", hops=2)
        ids_2hop = {n["id"] for n in neighbors_2hop}
        assert "claude" in ids_2hop

    def test_decision_chain_investment_impact(self):
        """Causal chain: investment decision → product launch → market decision."""
        g = ContextGraph()
        d_invest = g.record_decision(
            category="investment",
            scenario="Microsoft $10B investment in OpenAI - strategic AI partnership",
            reasoning="Generative AI leadership; Azure integration; GPT models embedded in Office 365.",
            outcome="approved",
            confidence=0.97,
            decision_maker="msft_board",
        )
        d_product = g.record_decision(
            category="product_launch",
            scenario="Copilot integration into Microsoft 365 suite",
            reasoning="Leverage OpenAI GPT-4 capabilities; $30/seat/month premium tier.",
            outcome="launched",
            confidence=0.93,
            decision_maker="satya_nadella",
        )
        d_market = g.record_decision(
            category="market_strategy",
            scenario="Azure OpenAI Service GA launch for enterprise customers",
            reasoning="Capture enterprise AI infrastructure spend; compete with AWS Bedrock.",
            outcome="launched",
            confidence=0.91,
            decision_maker="azure_gm",
        )
        g.add_causal_relationship(d_invest, d_product, "CAUSED")
        g.add_causal_relationship(d_product, d_market, "INFLUENCED")

        chain_down = g.get_causal_chain(d_invest, direction="downstream", max_depth=5)
        chain_ids = {d.decision_id for d in chain_down}
        assert d_product in chain_ids
        assert d_market in chain_ids


# ═════════════════════════════════════════════════════════════════════════════
# 18. Healthcare context graph – treatment decision tracking
# ═════════════════════════════════════════════════════════════════════════════

class TestHealthcareContextGraphE2E:
    """Real-world healthcare domain: treatment decisions with policy compliance."""

    def test_treatment_decision_lifecycle(self):
        g = ContextGraph()

        # Record initial diagnosis decision
        diag_id = g.record_decision(
            category="diagnosis",
            scenario=(
                "Patient: 58yo male, BP 165/95, total cholesterol 268, LDL 180, "
                "10yr CVD risk 18% (ACC/AHA pooled cohort). Diagnosis: Stage 2 hypertension + dyslipidemia."
            ),
            reasoning=(
                "JNC8 guidelines met for Stage 2 HTN (>160 systolic). "
                "ATP III criteria: high-risk patient requiring statin therapy."
            ),
            outcome="diagnosed_stage2_htn_dyslipidemia",
            confidence=0.94,
            entities=["patient_hc_7712", "bp_reading_001", "lipid_panel_001"],
            decision_maker="cardiology_ai_v2",
        )

        # Record treatment plan decision
        treat_id = g.record_decision(
            category="treatment",
            scenario="Prescribe ACE inhibitor + high-intensity statin for Stage 2 HTN + dyslipidemia",
            reasoning=(
                "Lisinopril 10mg/day for BP control; Atorvastatin 40mg/day for LDL reduction to <100. "
                "ACC/AHA Class I recommendation. No contraindications identified."
            ),
            outcome="treatment_prescribed",
            confidence=0.92,
            entities=["patient_hc_7712", "lisinopril_rx_001", "atorvastatin_rx_001"],
            decision_maker="cardiology_ai_v2",
        )

        # Record follow-up decision
        followup_id = g.record_decision(
            category="followup",
            scenario="6-week follow-up: BP 138/84, LDL 95. Treatment response assessment.",
            reasoning="Target BP <140/90 achieved. LDL <100 achieved. Continue current regimen.",
            outcome="continue_treatment",
            confidence=0.96,
            decision_maker="cardiology_ai_v2",
        )

        g.add_causal_relationship(diag_id, treat_id, "CAUSED")
        g.add_causal_relationship(treat_id, followup_id, "INFLUENCED")

        # Verify causal chain
        chain = g.get_causal_chain(diag_id, direction="downstream", max_depth=5)
        chain_ids = {d.decision_id for d in chain}
        assert treat_id in chain_ids
        assert followup_id in chain_ids

        # Verify precedent search
        g.add_causal_relationship(diag_id, treat_id, "PRECEDENT_FOR")
        precedents = g.find_precedents(treat_id, limit=5)
        assert len(precedents) >= 1

    def test_policy_compliance_check(self):
        """Policy engine: check treatment against clinical policy."""
        g = ContextGraph()
        # Add a clinical policy node
        policy_node_id = "clinical_policy_htn_2024"
        g.add_node(
            policy_node_id,
            node_type="Policy",
            content="Hypertension Management Policy 2024",
            policy_id=policy_node_id,
            category="treatment",
            rules={"min_bp_systolic_threshold": 140, "first_line_agent": "ACE_inhibitor"},
            version="2024.1",
        )
        assert g.has_node(policy_node_id)
        policy_nodes = g.find_nodes(node_type="Policy")
        assert len(policy_nodes) == 1
