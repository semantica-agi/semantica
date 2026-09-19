"""Unit tests covering all 10 Qodo review fixes.

Issues covered:
1. Global answers evidence links and member entity citations.
2. DRIFT prompts token budgeting and truncation.
3. Named graph nodes alias resolution and readable fact rendering.
4. Zero-valued nodes retaining edges and graph presence.
5. Parallel graph edges and inverse edge identity preservation.
6. AlgorithmRegistry lazy loading and instantiation of retrieval engines.
7. Hybrid retrieval filtering by min_relevance_score without double-weighting.
8. DriftSearchEngine search-level depth/threshold argument immutability.
9. ContextRetriever.retrieve_drift score normalization on 0-10 scale.
10. CommunityReport safe string coercion for findings in global retrieval.
"""

from unittest.mock import MagicMock, patch

from semantica.context.context_retriever import ContextRetriever, RetrievedContext
from semantica.context.drift_search import (
    DriftFacet,
    DriftSearchEngine,
    DriftSearchResult,
    estimate_tokens,
)
from semantica.context.global_retriever import (
    GlobalGraphRetriever,
    MapKeyPoint,
)
from semantica.kg.community_summarizer import CommunityReport
from semantica.kg.registry import AlgorithmRegistry, algorithm_registry


# ---------------------------------------------------------------------------
# Issue 1: Global answers omit evidence links
# ---------------------------------------------------------------------------
def test_global_retriever_evidence_links_appended_when_missing():
    retriever = GlobalGraphRetriever()
    key_points = [
        MapKeyPoint(
            community_id="c1",
            point="Consensus is required in distributed state machines.",
            description="PBFT and Raft ensure safety under partitions.",
            relevance_score=9.0,
            entities=["Raft", "PBFT"],
        ),
        MapKeyPoint(
            community_id="c2",
            point="Gossip protocols provide eventual consistency.",
            description="Dynamo-style rings use gossip for membership.",
            relevance_score=8.0,
            entities=["Dynamo"],
        ),
    ]

    raw_response = "Distributed systems require consensus algorithms."
    validated = retriever._ensure_evidence_citations(raw_response, key_points)

    assert "Sources / Evidence:" in validated
    assert "[Community c1]" in validated
    assert "[Community c2]" in validated
    assert "Raft" in validated
    assert "PBFT" in validated
    assert "Dynamo" in validated


def test_global_retriever_evidence_links_preserved_when_already_present():
    retriever = GlobalGraphRetriever()
    key_points = [
        MapKeyPoint(
            community_id="c1",
            point="Consensus ensures safety.",
            description="Desc",
            relevance_score=9.0,
            entities=["Raft"],
        )
    ]

    raw_response = "Safety in [Community c1] is achieved via consensus (Raft)."
    validated = retriever._ensure_evidence_citations(raw_response, key_points)
    assert "Sources / Evidence:" not in validated
    assert validated == raw_response


def test_global_retriever_deterministic_fallback_cites_entities_and_communities():
    retriever = GlobalGraphRetriever()
    key_points = [
        MapKeyPoint(
            community_id="comm_42",
            point="Primary point",
            description="Detailed evidence",
            relevance_score=9.5,
            entities=["EntityAlpha", "EntityBeta"],
        )
    ]

    fallback = retriever._synthesize_reduce("test query", "context", key_points)
    assert "[Community comm_42]" in fallback
    assert "Entities: EntityAlpha, EntityBeta" in fallback


# ---------------------------------------------------------------------------
# Issue 2: Drift prompts exceed token limit
# ---------------------------------------------------------------------------
def test_drift_synthesize_hybrid_respects_token_budget():
    engine = DriftSearchEngine(max_context_tokens=300, response_token_budget=50)
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Synthesized response (NodeA -[rel]-> NodeB)"
    engine.llm = mock_llm

    huge_query = "What is the consensus algorithm? " * 50
    huge_framing = "Global framing overview: " + ("extensive context " * 100)
    huge_facts = [
        {
            "source": f"Node{i}",
            "target": f"Node{i + 1}",
            "relation": "connects_to",
            "description": f"Connection {i} " * 20,
            "alignment_score": 0.9,
        }
        for i in range(100)
    ]

    response = engine._synthesize_hybrid(
        query=huge_query,
        thematic_framing=huge_framing,
        verified_facts=huge_facts,
    )
    assert response == "Synthesized response (NodeA -[rel]-> NodeB)"
    assert mock_llm.generate.called
    prompt_used = mock_llm.generate.call_args[0][0]
    prompt_tokens = estimate_tokens(prompt_used, engine.token_counter)
    # Total prompt tokens must stay within max_context_tokens
    assert prompt_tokens <= 300


def test_drift_generate_facets_respects_token_budget():
    engine = DriftSearchEngine(max_context_tokens=250, response_token_budget=50)
    mock_llm = MagicMock()
    mock_llm.generate_typed.return_value = []
    engine.llm = mock_llm

    huge_query = "Explore consensus nodes " * 40
    huge_framing = "Thematic context: " + ("deep background " * 100)

    engine._generate_facets(huge_query, huge_framing)
    assert mock_llm.generate_typed.called
    prompt_used = mock_llm.generate_typed.call_args[0][0]
    prompt_tokens = estimate_tokens(prompt_used, engine.token_counter)
    assert prompt_tokens <= 250


# ---------------------------------------------------------------------------
# Issue 3: Named graph nodes return no facts
# ---------------------------------------------------------------------------
def test_drift_named_graph_nodes_alias_resolution_and_fact_retrieval():
    engine = DriftSearchEngine(drift_threshold=0.0)
    graph_dict = {
        "nodes": [
            {
                "id": "uuid-node-001",
                "name": "PostgreSQL",
                "aliases": ["postgres", "psql"],
            },
            {
                "id": "uuid-node-002",
                "name": "WAL Service",
                "label": "WAL",
            },
        ],
        "edges": [
            {
                "source": "uuid-node-001",
                "target": "uuid-node-002",
                "relation": "writes_to",
                "description": "PostgreSQL streams logs to WAL Service.",
            }
        ],
    }
    engine.set_knowledge_graph(graph_dict)

    assert engine._resolve_node_id("postgres") == "uuid-node-001"
    assert engine._resolve_node_id("psql") == "uuid-node-001"
    assert engine._resolve_node_id("PostgreSQL") == "uuid-node-001"
    assert engine._resolve_node_id("WAL") == "uuid-node-002"

    facets = [
        DriftFacet(
            sub_query="Inspect postgres replication",
            target_entities=["postgres"],
            relevance_score=1.0,
        )
    ]
    verified, depth, pruned = engine._traverse_and_prune(
        facets, "postgres replication", "framing"
    )
    assert len(verified) >= 1
    edge = verified[0]
    assert edge["source"] == "uuid-node-001"
    assert edge["target"] == "uuid-node-002"
    assert edge["source_name"] == "PostgreSQL"
    assert edge["target_name"] == "WAL Service"


def test_drift_search_result_to_retrieved_contexts_uses_readable_names():
    res = DriftSearchResult(
        query="test query",
        answer="Test answer",
        global_reports_used=["comm_1"],
        verified_local_contexts=[
            {
                "source": "id_1",
                "target": "id_2",
                "relation": "MANAGES",
                "source_name": "Manager Service",
                "target_name": "Worker Node",
                "description": "Manager assigns tasks to Worker Node",
                "alignment_score": 0.85,
            }
        ],
        facets_explored=[],
    )
    contexts = res.to_retrieved_contexts()
    assert len(contexts) == 2  # answer + verified context
    ctx = contexts[1]
    assert "Manager Service" in ctx.content
    assert "Worker Node" in ctx.content
    assert ctx.metadata["source"] == "id_1"
    assert ctx.metadata["target"] == "id_2"


# ---------------------------------------------------------------------------
# Issue 4: Zero-valued nodes lose their edges
# ---------------------------------------------------------------------------
def test_drift_zero_valued_nodes_preserve_edges():
    engine = DriftSearchEngine(drift_threshold=0.0)
    graph_dict = {
        "nodes": [
            {"id": 0, "name": "Node Zero Int"},
            {"id": 1, "name": "Node One"},
        ],
        "edges": [
            {
                "source": 0,
                "target": 1,
                "relation": "CONNECTS_INT_ZERO",
                "description": "Int 0 to 1",
            },
        ],
    }
    engine.set_knowledge_graph(graph_dict)

    assert "0" in engine._adjacency_index
    assert engine._node_meta.get("0") is not None
    assert engine._resolve_node_id(0) == "0"
    assert engine._resolve_node_id("0") == "0"

    edges = engine._adjacency_index.get("0", [])
    assert len(edges) >= 1
    assert any(e["relation"] == "CONNECTS_INT_ZERO" for e in edges)


# ---------------------------------------------------------------------------
# Issue 5: Parallel graph facts disappear
# ---------------------------------------------------------------------------
def test_drift_parallel_edges_between_same_endpoints_preserved():
    engine = DriftSearchEngine(drift_threshold=0.0)
    graph_dict = {
        "nodes": [{"id": "svc_a"}, {"id": "svc_b"}],
        "edges": [
            {
                "id": "edge_auth",
                "source": "svc_a",
                "target": "svc_b",
                "relation": "AUTHENTICATES_WITH",
                "description": "Auth protocol",
            },
            {
                "id": "edge_telemetry",
                "source": "svc_a",
                "target": "svc_b",
                "relation": "STREAMS_METRICS_TO",
                "description": "Prometheus scrape",
            },
        ],
    }
    engine.set_knowledge_graph(graph_dict)

    svc_a_edges = [
        e for e in engine._adjacency_index.get("svc_a", [])
        if e.get("target") == "svc_b" and not e.get("is_inverse")
    ]
    assert len(svc_a_edges) == 2
    relations = {e["relation"] for e in svc_a_edges}
    assert relations == {"AUTHENTICATES_WITH", "STREAMS_METRICS_TO"}


def test_drift_inverse_edge_preserves_canonical_id():
    engine = DriftSearchEngine(drift_threshold=0.0)
    graph_dict = {
        "nodes": [{"id": "node_x"}, {"id": "node_y"}],
        "edges": [
            {
                "id": "unique_edge_123",
                "source": "node_x",
                "target": "node_y",
                "relation": "CALLS",
                "description": "RPC call",
            }
        ],
    }
    engine.set_knowledge_graph(graph_dict)

    fwd_edge = next(
        e for e in engine._adjacency_index["node_x"]
        if e.get("target") == "node_y" and not e.get("is_inverse")
    )
    inv_edge = next(
        e for e in engine._adjacency_index["node_y"]
        if e.get("target") == "node_x" and e.get("is_inverse")
    )

    assert "unique_edge_123" in fwd_edge["canonical_id"]
    assert fwd_edge["canonical_id"] == inv_edge["canonical_id"]


# ---------------------------------------------------------------------------
# Issue 6: Registered retrieval cannot be created
# ---------------------------------------------------------------------------
def test_algorithm_registry_global_retrieval_and_drift_search():
    reg = AlgorithmRegistry()
    global_cls = reg.get("global_retrieval")
    assert global_cls is GlobalGraphRetriever

    drift_cls = reg.get("drift_search")
    assert drift_cls is DriftSearchEngine

    global_inst = reg.create_instance("global_retrieval")
    assert isinstance(global_inst, GlobalGraphRetriever)

    drift_inst = reg.create_instance("drift_search")
    assert isinstance(drift_inst, DriftSearchEngine)

    # Test global singleton algorithm_registry instance
    assert algorithm_registry.get("global_retrieval") is GlobalGraphRetriever
    assert algorithm_registry.get("drift_search") is DriftSearchEngine


# ---------------------------------------------------------------------------
# Issue 7: Hybrid results bypass score floor
# ---------------------------------------------------------------------------
def test_hybrid_retrieval_enforces_min_relevance_score_after_weighting():
    retriever = ContextRetriever(hybrid_alpha=0.5)

    # c_high raw score = 1.0 -> weighted score = 0.50 (>= 0.40)
    c_high = RetrievedContext(
        content="High relevance context",
        score=1.0,
        source="vector:high",
    )
    # c_low raw score = 0.60 -> weighted score = 0.30 (< 0.40)
    c_low = RetrievedContext(
        content="Low relevance context",
        score=0.60,
        source="vector:low",
    )

    with patch.object(
        retriever, "_retrieve_from_vector", return_value=[c_high, c_low]
    ), patch.object(
        retriever, "_retrieve_from_graph", return_value=[]
    ), patch.object(
        retriever, "retrieve_global", return_value=[]
    ):
        retriever.knowledge_graph = None
        results = retriever.retrieve(
            "test query",
            mode="hybrid",
            min_relevance_score=0.40,
            max_results=5,
        )

        assert len(results) == 1
        assert results[0].content == "High relevance context"
        assert results[0].score >= 0.40


# ---------------------------------------------------------------------------
# Issue 8: Concurrent searches corrupt settings
# ---------------------------------------------------------------------------
def test_drift_search_does_not_mutate_engine_settings():
    engine = DriftSearchEngine(max_depth=2, drift_threshold=0.3)
    mock_llm = MagicMock()
    mock_llm.generate_typed.return_value = []
    mock_llm.generate.return_value = "Answer"
    engine.llm = mock_llm

    assert engine.max_depth == 2
    assert engine.drift_threshold == 0.3

    engine.search("query", max_depth=5, drift_threshold=0.85)

    assert engine.max_depth == 2
    assert engine.drift_threshold == 0.3


# ---------------------------------------------------------------------------
# Issue 9: Valid drift results are filtered out
# ---------------------------------------------------------------------------
def test_context_retriever_retrieve_drift_scales_score_floor():
    retriever = ContextRetriever()
    search_result = DriftSearchResult(
        query="query",
        answer="Answer",
        global_reports_used=["c1"],
        verified_local_contexts=[
            {
                "source": "s1",
                "target": "t1",
                "relation": "REL1",
                "description": "High score fact",
                "alignment_score": 0.80,
            },
            {
                "source": "s2",
                "target": "t2",
                "relation": "REL2",
                "description": "Low score fact",
                "alignment_score": 0.30,
            },
        ],
        facets_explored=[],
    )

    with patch.object(
        DriftSearchEngine, "search", return_value=search_result
    ):
        # min_relevance_score=6.0 should scale to 0.60
        contexts = retriever.retrieve_drift(
            "query", min_relevance_score=6.0, as_contexts=True
        )
        assert len(contexts) >= 1
        assert all(c.score >= 0.60 for c in contexts)
        assert any(c.score == 0.80 for c in contexts)
        assert not any(c.score == 0.30 for c in contexts)


# ---------------------------------------------------------------------------
# Issue 10: Report loading crashes global search
# ---------------------------------------------------------------------------
def test_community_report_none_and_non_string_findings_safe_handling():
    report = CommunityReport(
        community_id="c_err",
        level=0,
        title="Fault Tolerant",
        summary="Summary text",
        findings=[
            {"summary": None, "explanation": None, "weight": 5.0},
            {"summary": 12345, "explanation": {"detail": "nested"}, "weight": 7.0},
        ],
        member_entities=["NodeA"],
    )

    assert report.findings[0]["summary"] == ""
    assert report.findings[0]["explanation"] == ""
    assert report.findings[1]["summary"] == "12345"

    retriever = GlobalGraphRetriever()
    retriever.set_reports([report])

    tokens = retriever._estimate_report_tokens(report)
    assert tokens > 0

    points = retriever._map_report(report, "test query")
    assert isinstance(points, list)

    fallback_response = retriever._extractive_map_fallback(report, "test query")
    assert hasattr(fallback_response, "points")
    assert isinstance(fallback_response.points, list)


def test_global_retriever_evidence_word_boundary_and_none_id():
    retriever = GlobalGraphRetriever()
    kp = [
        MapKeyPoint(
            community_id="c1",
            point="",
            description="Algorithm description",
            relevance_score=8.0,
            entities=["Go"],
        ),
        MapKeyPoint(
            community_id=None,
            point="Anonymous point",
            relevance_score=7.0,
            entities=["NodeX"],
        ),
    ]

    resp = "This algorithm executes in linear time."
    validated = retriever._ensure_evidence_citations(resp, kp)
    assert "[Community None]" not in validated
    assert "Sources / Evidence:" in validated
    assert "- [Community c1] (Entities: Go): Algorithm description" in validated


def test_drift_budgeting_tight_limit_with_huge_query():
    # Facets prompt budgeting
    engine = DriftSearchEngine(max_context_tokens=150, response_token_budget=20)
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Answer"
    mock_llm.generate_typed.return_value = []
    engine.llm = mock_llm

    huge_query = "What is the consensus algorithm in a distributed system? " * 10
    huge_framing = "Global framing: " * 20

    engine._generate_facets(huge_query, huge_framing)
    prompt = mock_llm.generate_typed.call_args[0][0]
    prompt_tokens = estimate_tokens(prompt, engine.token_counter)
    assert prompt_tokens <= 150

    # Synthesis prompt budgeting
    engine2 = DriftSearchEngine(max_context_tokens=180, response_token_budget=20)
    engine2.llm = mock_llm
    huge_facts = [
        {
            "source": "A",
            "target": "B",
            "relation": "C",
            "description": "D" * 50,
        }
    ]
    engine2._synthesize_hybrid(huge_query, huge_framing, huge_facts)
    prompt2 = mock_llm.generate.call_args[0][0]
    prompt2_tokens = estimate_tokens(prompt2, engine2.token_counter)
    assert prompt2_tokens <= 180


def test_drift_edge_id_zero_preservation():
    engine = DriftSearchEngine()
    graph = {
        "nodes": [{"id": 0, "name": "ZeroNode"}, {"id": 1, "name": "OneNode"}],
        "edges": [
            {
                "id": 0,
                "source": 0,
                "target": 1,
                "relation": "ZERO_EDGE",
                "description": "Edge 0",
            }
        ],
    }
    engine.set_knowledge_graph(graph)
    edge = engine._adjacency_index["0"][0]
    assert ":0" in edge["canonical_id"]
    assert edge.get("edge_id") == "0"


def test_algorithm_registry_aliases_and_listing():
    reg = AlgorithmRegistry()
    for name in ("default", "global", "map_reduce"):
        assert reg.get("global_retrieval", name) is GlobalGraphRetriever
        inst = reg.create_instance("global_retrieval", name)
        assert isinstance(inst, GlobalGraphRetriever)

    for name in ("default", "drift", "hybrid"):
        assert reg.get("drift_search", name) is DriftSearchEngine
        inst = reg.create_instance("drift_search", name)
        assert isinstance(inst, DriftSearchEngine)

    global_names = algorithm_registry.list_category("global_retrieval")
    assert "default" in global_names
    assert "global" in global_names
    assert "map_reduce" in global_names

    drift_names = algorithm_registry.list_category("drift_search")
    assert "default" in drift_names
    assert "drift" in drift_names
    assert "hybrid" in drift_names


def test_local_retrieval_scales_min_relevance_score():
    retriever = ContextRetriever()
    c1 = RetrievedContext(
        content="Context 1",
        score=0.8,
        source="vector:1",
    )
    c2 = RetrievedContext(
        content="Context 2",
        score=0.4,
        source="vector:2",
    )
    with patch.object(
        retriever, "_retrieve_from_vector", return_value=[c1, c2]
    ), patch.object(
        retriever, "_retrieve_from_graph", return_value=[]
    ):
        retriever.knowledge_graph = None
        # min_relevance_score=4.0 should scale to 0.40
        res = retriever.retrieve(
            "query", mode="local", min_relevance_score=4.0, max_results=5
        )
        assert len(res) == 1
        assert res[0].content == "Context 1"
        assert res[0].score >= 0.40
