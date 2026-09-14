"""Unit tests covering all 27 PR review fixes (Issues 1-11, Findings A-P)."""

import time
from unittest.mock import MagicMock, patch

from semantica.context.global_retriever import (
    GlobalGraphRetriever,
    GlobalSearchResult,
    MapPointSchema,
    MapKeyPoint,
)
from semantica.context.drift_search import (
    DriftSearchEngine,
    DriftFacetSchema,
    DriftFacet,
)
from semantica.context.context_retriever import ContextRetriever, RetrievedContext
from semantica.kg.community_summarizer import CommunityReport


# ---------------------------------------------------------------------------
# Issue 1: Concurrency & Timeout Safety in GlobalGraphRetriever
# ---------------------------------------------------------------------------
def test_issue_1_concurrency_timeout():
    """Verify ThreadPoolExecutor timeout cancels futures without blocking."""
    retriever = GlobalGraphRetriever(timeout=0.1, max_workers=2)

    def slow_worker(rep, query):
        time.sleep(2.0)
        return []

    reports = [
        CommunityReport(
            community_id=f"c_{i}",
            level=0,
            title=f"Report {i}",
            summary=f"Summary {i}",
            findings=[],
            member_entities=[f"Ent_{i}"],
        )
        for i in range(3)
    ]
    start_t = time.time()
    with patch.object(retriever, "_map_report", side_effect=slow_worker):
        results = retriever._execute_parallel_map(reports, "test query")
        elapsed = time.time() - start_t
        # Finished within timeout window without waiting for slow workers
        assert elapsed < 2.5
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Issue 2: Query forwarded to extractive fallback
# ---------------------------------------------------------------------------
def test_issue_2_query_forwarded_to_extractive_fallback():
    retriever = GlobalGraphRetriever()
    report = CommunityReport(
        community_id="c1",
        level=0,
        title="AI",
        summary="Deep learning",
        findings=[],
        member_entities=[],
    )
    with patch.object(
        retriever, "_extractive_map_fallback", return_value=MagicMock(points=[])
    ) as mock_fallback:
        retriever._call_map_llm("prompt text", report, query="machine learning")
        mock_fallback.assert_called_once()
        args, kwargs = mock_fallback.call_args
        assert args[1] == "machine learning"


# ---------------------------------------------------------------------------
# Issue 3 & Finding G: Tier 1 failure cascades to Tier 2
# ---------------------------------------------------------------------------
def test_issue_3_and_finding_g_tier1_failure_cascades_to_tier2():
    retriever = GlobalGraphRetriever()
    mock_llm = MagicMock()
    mock_provider = MagicMock()
    mock_llm.provider = mock_provider

    # Tier 1 generate_typed fails
    mock_llm.generate_typed.side_effect = RuntimeError("Tier 1 unavailable")
    # Tier 2 provider.generate_typed succeeds
    mock_provider.generate_typed.return_value = [
        MapPointSchema(
            point="Finding from tier 2",
            relevance_score=8.5,
            description="Evidence text",
        )
    ]
    retriever.llm = mock_llm
    report = CommunityReport(
        community_id="c1",
        level=0,
        title="T",
        summary="S",
        findings=[],
        member_entities=[],
    )

    schema = retriever._call_map_llm("prompt", report, query="query")
    assert len(schema.points) == 1
    assert schema.points[0].point == "Finding from tier 2"
    mock_provider.generate_typed.assert_called_once()


def test_issue_3_and_finding_g_drift_facet_tier1_to_tier2():
    drift = DriftSearchEngine()
    mock_llm = MagicMock()
    mock_provider = MagicMock()
    mock_llm.provider = mock_provider

    mock_llm.generate_typed.side_effect = RuntimeError("Tier 1 fail")
    mock_provider.generate_typed.return_value = [
        DriftFacetSchema(
            sub_query="Facet from tier 2",
            target_entities=["EntityA"],
            rationale="Rationale text",
            relevance_score=0.9,
        )
    ]
    drift.llm = mock_llm

    facets = drift._generate_facets("test query", "thematic framing")
    assert len(facets) == 1
    assert facets[0].sub_query == "Facet from tier 2"


# ---------------------------------------------------------------------------
# Issue 4: Budget exhaustion and empty lines packing
# ---------------------------------------------------------------------------
def test_issue_4_budget_exhaustion_no_artificial_inflation():
    retriever = GlobalGraphRetriever(
        max_context_tokens=100,
        fixed_overhead=200,
        response_token_budget=100,
    )
    rep = CommunityReport(
        community_id="c1",
        level=0,
        title="Distributed Systems",
        summary="Summary of distributed systems",
        findings=[],
        member_entities=[],
    )
    retriever.set_reports([rep])
    res = retriever.search("consensus")
    assert "No sufficiently relevant community findings were available." in res.response
    assert res.metrics["citations_count"] == 0


def test_issue_4_empty_packed_lines_handling():
    retriever = GlobalGraphRetriever()
    lines, retained = retriever._pack_reduce_context([], budget=100)
    assert lines == ""
    assert retained == []


# ---------------------------------------------------------------------------
# Issue 5: Extracted citations intersected with valid_ids
# ---------------------------------------------------------------------------
def test_issue_5_citation_intersection():
    retriever = GlobalGraphRetriever()
    rep1 = CommunityReport(community_id="comm_1", level=0, title="T1", summary="S1")
    rep2 = CommunityReport(community_id="comm_2", level=0, title="T2", summary="S2")
    retriever.set_reports([rep1, rep2])

    points = [
        MapKeyPoint(
            community_id="comm_1",
            point="Point 1",
            relevance_score=8.0,
            description="Evidence 1",
        ),
        MapKeyPoint(
            community_id="comm_2",
            point="Point 2",
            relevance_score=7.0,
            description="Evidence 2",
        ),
    ]

    # LLM hallucinates comm_999 alongside comm_1
    with patch.object(
        retriever, "_execute_parallel_map", return_value=points
    ), patch.object(
        retriever,
        "_synthesize_reduce",
        return_value="Based on [Community comm_1] and [Community comm_999].",
    ):
        res = retriever.search("query")
        assert res.citations == ["comm_1"]

    # When no citations match, fallback to sorted valid_ids
    with patch.object(
        retriever, "_execute_parallel_map", return_value=points
    ), patch.object(
        retriever,
        "_synthesize_reduce",
        return_value="No citations here.",
    ):
        res = retriever.search("query")
        assert res.citations == ["comm_1", "comm_2"]


# ---------------------------------------------------------------------------
# Issue 6 & Finding H: Schema validation alias for 'score'
# ---------------------------------------------------------------------------
def test_issue_6_and_finding_h_schema_score_alias():
    # MapPointSchema
    p1 = MapPointSchema.model_validate(
        {"point": "Key fact", "score": 8.5, "description": "text"}
    )
    assert p1.relevance_score == 8.5

    p2 = MapPointSchema.model_validate(
        {"point": "Key fact", "relevance_score": 9.2, "description": "text"}
    )
    assert p2.relevance_score == 9.2

    # DriftFacetSchema
    f1 = DriftFacetSchema.model_validate(
        {
            "sub_query": "Query facet",
            "score": 0.8,
            "rationale": "text",
            "target_entities": ["E1"],
        }
    )
    assert f1.relevance_score == 0.8


# ---------------------------------------------------------------------------
# Issue 7: Drift Search traversal token budget capping
# ---------------------------------------------------------------------------
def test_issue_7_drift_search_token_budget_capping():
    drift = DriftSearchEngine(max_context_tokens=40)
    drift._adjacency_index = {
        "n1": [
            {
                "source": "n1",
                "target": "n2",
                "relation": "relates_to",
                "description": "very long description " * 20,
            },
            {
                "source": "n1",
                "target": "n3",
                "relation": "connects",
                "description": "another long description " * 20,
            },
            {
                "source": "n1",
                "target": "n4",
                "relation": "links",
                "description": "third long description " * 20,
            },
        ]
    }
    drift._node_meta = {
        "n1": {"id": "n1", "name": "n1"},
        "n2": {"id": "n2", "name": "n2"},
        "n3": {"id": "n3", "name": "n3"},
        "n4": {"id": "n4", "name": "n4"},
    }

    facets = [
        DriftFacet(
            sub_query="Explore n1",
            target_entities=["n1"],
            relevance_score=1.0,
        )
    ]
    verified, depth, pruned = drift._traverse_and_prune(
        facets, "test query n1 n2", "framing"
    )
    # Traversal should halt early before adding all edges due to 40 token limit
    assert len(verified) < 3


# ---------------------------------------------------------------------------
# Issue 8 & Finding M: Citation filtering and regex in Drift Search
# ---------------------------------------------------------------------------
def test_issue_8_and_finding_m_drift_citation_filtering():
    drift = DriftSearchEngine()
    rep = CommunityReport(
        community_id="comm_1",
        level=0,
        title="Title",
        summary="Summary",
        findings=[],
        member_entities=["Node.js", "API/v1"],
    )
    drift.set_reports([rep])
    drift._adjacency_index = {
        "Node.js": [
            {
                "source": "Node.js",
                "target": "API/v1",
                "relation": "exposes",
                "description": "Exposes API",
            }
        ]
    }
    drift._node_meta = {
        "Node.js": {"id": "Node.js", "name": "Node.js"},
        "API/v1": {"id": "API/v1", "name": "API/v1"},
    }

    mock_llm = MagicMock()
    mock_llm.generate.return_value = (
        "Found in [Community comm_1] and [Community comm_999]. "
        "Also (Node.js -[exposes]-> API/v1) and (Fake -[bad]-> Invalid)."
    )
    drift.llm = mock_llm

    result = drift.search("Node.js exposes API/v1")
    assert "[Community comm_1]" in result.citations
    assert "[Community comm_999]" not in result.citations
    assert "(Node.js -[exposes]-> API/v1)" in result.citations
    assert "(Fake -[bad]-> Invalid)" not in result.citations


# ---------------------------------------------------------------------------
# Issue 9 & Finding D: ContextRetriever threshold scaling & hybrid score preservation
# ---------------------------------------------------------------------------
def test_issue_9_and_finding_d_threshold_scaling():
    retriever = ContextRetriever()
    search_result = GlobalSearchResult(
        query="query",
        response="Answer",
        level=0,
        key_points=[
            MapKeyPoint(
                point="Point 1",
                relevance_score=8.0,
                description="Evidence",
                community_id="c1",
            ),
            MapKeyPoint(
                point="Point 2",
                relevance_score=3.0,
                description="Evidence",
                community_id="c2",
            ),
        ],
        community_reports_used=["c1"],
        citations=["c1"],
    )

    with patch.object(
        GlobalGraphRetriever, "search", return_value=search_result
    ):
        # min_relevance_score=6.0 scales to threshold 0.60
        # Result contains executive answer (score=1.0) and Point 1 (score=0.80)
        contexts = retriever.retrieve_global(
            "query", min_relevance_score=6.0, as_contexts=True
        )
        assert len(contexts) == 2
        assert any(c.score == 0.80 for c in contexts)
        assert all(c.score >= 0.60 for c in contexts)


def test_issue_9_and_finding_d_hybrid_preserves_weighted_scores():
    retriever = ContextRetriever(hybrid_alpha=0.5)

    c1 = RetrievedContext(
        content="Vector match",
        score=1.0,
        source="vector:1",
    )

    with patch.object(
        retriever, "_retrieve_from_vector", return_value=[c1]
    ), patch.object(
        retriever, "_retrieve_from_graph", return_value=[]
    ), patch.object(
        retriever, "retrieve_global", return_value=[]
    ):
        retriever.knowledge_graph = None
        # In mode="local", c1 score is weighted to 0.5 (>= 0.4).
        # In mode="hybrid", after second merge, score becomes 0.25 (< 0.4).
        # In the old code, a second filter purged it. Now it is preserved.
        results = retriever.retrieve(
            "test query",
            mode="hybrid",
            min_relevance_score=0.4,
            max_results=5,
        )
        assert len(results) == 1
        assert results[0].content == "Vector match"


# ---------------------------------------------------------------------------
# Issue 10 & Finding K: Early return on no retained points & metrics citations_count
# ---------------------------------------------------------------------------
def test_issue_10_and_finding_k_no_retained_points_metrics():
    retriever = GlobalGraphRetriever()
    retriever.set_reports(
        [
            CommunityReport(
                community_id="c1",
                level=0,
                title="T",
                summary="S",
                findings=[],
                member_entities=[],
            )
        ]
    )

    with patch.object(
        retriever,
        "_execute_parallel_map",
        return_value=[
            MapKeyPoint(
                community_id="c1",
                point="Irrelevant",
                relevance_score=2.0,
                description="e",
            )
        ],
    ):
        result = retriever.search("query", min_relevance_score=8.0)
        assert "No sufficiently relevant community findings" in result.response
        assert result.citations == []
        assert result.community_reports_used == []
        assert result.metrics["citations_count"] == 0


def test_issue_10_and_finding_k_no_candidate_reports_metrics():
    retriever = GlobalGraphRetriever()
    retriever.set_reports([])
    result = retriever.search("query")
    assert result.metrics["citations_count"] == 0


# ---------------------------------------------------------------------------
# Issue 11 & Finding A: GraphStore / manager detection and flexible edge keys
# ---------------------------------------------------------------------------
def test_issue_11_and_finding_a_graph_store_detection_and_edge_keys():
    drift = DriftSearchEngine()

    class MockGraphStore:
        def __init__(self):
            self.relationships = MagicMock()
            self.relationships.get.return_value = [
                {
                    "start_node_id": "n1",
                    "end_node_id": "n2",
                    "type": "DEPENDS_ON",
                    "properties": {"description": "n1 depends on n2"},
                }
            ]
            self.nodes = MagicMock()
            self.nodes.get.return_value = [
                {"id": "n1", "properties": {"name": "Service A"}},
                {"id": "n2", "properties": {"name": "Service B"}},
            ]

    store = MockGraphStore()
    drift.set_knowledge_graph(store)
    assert "n1" in drift._adjacency_index
    edge = drift._adjacency_index["n1"][0]
    assert edge["source"] == "n1"
    assert edge["target"] == "n2"
    assert edge["relation"] == "DEPENDS_ON"
    assert edge["description"] == "n1 depends on n2"
    assert "n1" in drift._node_meta
    assert drift._node_meta["n1"]["name"] == "Service A"


# ---------------------------------------------------------------------------
# Finding B: Ingest graph iterables and NetworkX node tuples
# ---------------------------------------------------------------------------
def test_finding_b_ingest_graph_networkx_tuples():
    drift = DriftSearchEngine()

    class MockNetworkXGraph:
        def __init__(self):
            self.nodes = [
                ("node_alpha", {"properties": {"name": "Alpha Node"}}),
                ("node_beta", {"name": "Beta Node"}),
            ]
            self.edges = [("node_alpha", "node_beta", {"relation": "LINKS_TO"})]

    drift.set_knowledge_graph(MockNetworkXGraph())
    assert "node_alpha" in drift._node_meta
    assert drift._node_meta["node_alpha"]["name"] == "Alpha Node"
    assert "node_beta" in drift._node_meta
    assert drift._node_meta["node_beta"]["name"] == "Beta Node"


# ---------------------------------------------------------------------------
# Finding C: Rank and merge preserves global & drift graph sources
# ---------------------------------------------------------------------------
def test_finding_c_rank_and_merge_preserves_graph_sources():
    retriever = ContextRetriever(hybrid_alpha=0.8)

    contexts = [
        RetrievedContext(content="Global", score=1.0, source="global_search"),
        RetrievedContext(content="DRIFT", score=1.0, source="drift_search"),
        RetrievedContext(content="Comm", score=1.0, source="community_report"),
        RetrievedContext(content="Vector", score=1.0, source="vector:items"),
    ]

    merged = retriever._rank_and_merge(contexts, "query")
    sources = {c.source for c in merged}
    assert "global_search" in sources
    assert "drift_search" in sources
    assert "community_report" in sources


# ---------------------------------------------------------------------------
# Finding E: Inverse edge canonical direction in traversal
# ---------------------------------------------------------------------------
def test_finding_e_inverse_edge_canonical_direction():
    drift = DriftSearchEngine(drift_threshold=0.0)
    drift.set_knowledge_graph(
        {
            "nodes": [{"id": "client"}, {"id": "server"}],
            "edges": [
                {
                    "source": "client",
                    "target": "server",
                    "relation": "CONNECTS_TO",
                    "description": "Client establishes connection to Server",
                }
            ],
        }
    )

    # Query facet matching "server", traversing backward to "client"
    facets = [
        DriftFacet(
            sub_query="Explore server",
            target_entities=["server"],
            relevance_score=1.0,
        )
    ]
    verified, depth, pruned = drift._traverse_and_prune(
        facets, "server client connects", "framing"
    )
    assert len(verified) == 1
    # Fact text should retain canonical (client) -[CONNECTS_TO]-> (server)
    assert verified[0]["source"] == "client"
    assert verified[0]["target"] == "server"


# ---------------------------------------------------------------------------
# Finding F: Verified facts sorted descending by alignment score
# ---------------------------------------------------------------------------
def test_finding_f_verified_facts_sorted_descending():
    drift = DriftSearchEngine(drift_threshold=0.1)
    rep = CommunityReport(
        community_id="c1",
        level=0,
        title="Title",
        summary="Summary",
        findings=[],
        member_entities=["a", "b", "c"],
    )
    drift.set_reports([rep])
    drift._adjacency_index = {
        "a": [
            {
                "source": "a",
                "target": "b",
                "relation": "r1",
                "description": "fact low",
            },
            {
                "source": "a",
                "target": "c",
                "relation": "r2",
                "description": "fact high",
            },
        ]
    }
    drift._node_meta = {
        "a": {"id": "a", "name": "a"},
        "b": {"id": "b", "name": "b"},
        "c": {"id": "c", "name": "c"},
    }

    with patch.object(
        drift, "_compute_alignment_score", side_effect=[0.3, 0.9]
    ), patch.object(
        drift,
        "_generate_facets",
        return_value=[
            DriftFacet(
                sub_query="Explore a",
                target_entities=["a"],
                relevance_score=1.0,
            )
        ],
    ):
        result = drift.search("a query")
        contexts = result.verified_local_contexts
        assert len(contexts) == 2
        assert contexts[0]["alignment_score"] >= contexts[1]["alignment_score"]
        assert contexts[0]["alignment_score"] == 0.9


# ---------------------------------------------------------------------------
# Finding I: Guard against None in numeric fields in from_dict
# ---------------------------------------------------------------------------
def test_finding_i_guard_none_in_from_dict():
    # CommunityReport
    cs = CommunityReport.from_dict(
        {
            "community_id": "comm_1",
            "title": "Title",
            "summary": "Summary",
            "level": None,
            "impact_rating": None,
            "rank": None,
        }
    )
    assert cs.level == 0
    assert cs.impact_rating == 5.0
    assert cs.rank == 0.0

    # MapKeyPoint
    kp = MapKeyPoint.from_dict(
        {
            "community_id": "c1",
            "point": "P",
            "relevance_score": None,
            "level": None,
        }
    )
    assert kp.relevance_score == 5.0
    assert kp.level == 0

    # DriftFacet
    df = DriftFacet.from_dict(
        {
            "sub_query": "F",
            "relevance_score": None,
        }
    )
    assert df.relevance_score == 1.0


# ---------------------------------------------------------------------------
# Finding J: _estimate_report_tokens handles string findings
# ---------------------------------------------------------------------------
def test_finding_j_estimate_report_tokens_string_findings():
    retriever = GlobalGraphRetriever()
    report = CommunityReport(
        community_id="c1",
        level=0,
        title="Report",
        summary="Summary",
        findings=[
            "Simple string finding 1",
            "Simple string finding 2",
        ],
        member_entities=[],
    )
    tokens = retriever._estimate_report_tokens(report)
    assert tokens > 0


# ---------------------------------------------------------------------------
# Finding N: Unsupported LLM raises TypeError to trigger deterministic fallback
# ---------------------------------------------------------------------------
def test_finding_n_unsupported_llm_raises_typeerror():
    retriever = GlobalGraphRetriever()
    retriever.llm = "unsupported_string_llm"
    rep = CommunityReport(
        community_id="c1",
        level=0,
        title="t",
        summary="sample text",
        findings=[],
        member_entities=[],
    )
    res = retriever._call_map_llm("prompt", rep, query="sample")
    assert isinstance(res.points, list)

    drift = DriftSearchEngine()
    drift.llm = 12345  # unsupported int
    facets = drift._generate_facets("query", "framing")
    assert isinstance(facets, list)


# ---------------------------------------------------------------------------
# Finding O: set_reports accepts general Iterable
# ---------------------------------------------------------------------------
def test_finding_o_set_reports_accepts_iterable():
    retriever = GlobalGraphRetriever()
    reports_dict = {
        "c1": {"community_id": "c1", "summary": "s1"},
        "c2": {"community_id": "c2", "summary": "s2"},
    }
    # Pass dict_values view
    retriever.set_reports(reports_dict.values())
    assert len(retriever._reports) == 2

    drift = DriftSearchEngine()
    # Pass generator of CommunityReport objects
    rep_objs = (
        CommunityReport(
            community_id=k,
            level=0,
            title=k,
            summary=v["summary"],
            findings=[],
            member_entities=[],
        )
        for k, v in reports_dict.items()
    )
    drift.set_reports(rep_objs)
    assert len(drift._reports) == 2


# ---------------------------------------------------------------------------
# Finding P: MapPointSchema exported in semantica.context
# ---------------------------------------------------------------------------
def test_finding_p_map_point_schema_exported():
    import semantica.context as ctx
    assert hasattr(ctx, "MapPointSchema")
    assert "MapPointSchema" in ctx.__all__


# ---------------------------------------------------------------------------
# Deep Verification: Robustness & Edge Cases
# ---------------------------------------------------------------------------
def test_issue_1_duplicate_community_ids_on_timeout():
    """Verify duplicate community IDs do not suppress fallback for timed-out futures."""
    retriever = GlobalGraphRetriever(timeout=0.05, max_workers=2)

    def slow_worker(rep, query):
        time.sleep(2.0)
        return []

    # Both reports share the same community_id
    reports = [
        CommunityReport(
            community_id="shared_comm",
            level=0,
            title="Report 1",
            summary="Summary 1",
            findings=[],
            member_entities=["E1"],
        ),
        CommunityReport(
            community_id="shared_comm",
            level=0,
            title="Report 2",
            summary="Summary 2",
            findings=[],
            member_entities=["E2"],
        ),
    ]
    with patch.object(retriever, "_map_report", side_effect=slow_worker):
        results = retriever._execute_parallel_map(reports, "test query")
        # Both reports produce fallback points despite shared community ID
        assert len(results) == 2


def test_issue_1_subsecond_timeout_respected():
    retriever = GlobalGraphRetriever(timeout=0.05)
    assert retriever.timeout == 0.05


def test_issue_4_pack_reduce_context_skips_oversized_points():
    retriever = GlobalGraphRetriever()
    # Create 3 points: kp1 (fits), kp2 (huge, exceeds remaining), kp3 (small, fits)
    kp1 = MapKeyPoint(
        point="Short 1",
        description="d1",
        relevance_score=9.0,
        community_id="c1",
    )
    kp2 = MapKeyPoint(
        point="Huge 2",
        description="long description " * 100,
        relevance_score=8.5,
        community_id="c2",
    )
    kp3 = MapKeyPoint(
        point="Short 3",
        description="d3",
        relevance_score=8.0,
        community_id="c3",
    )

    _, retained = retriever._pack_reduce_context([kp1, kp2, kp3], budget=60)
    assert kp1 in retained
    assert kp2 not in retained
    assert kp3 in retained


def test_issue_5_integer_and_zero_community_id_citations():
    retriever = GlobalGraphRetriever()
    rep0 = CommunityReport(community_id=0, level=0, title="T0", summary="S0")
    rep1 = CommunityReport(community_id=1, level=0, title="T1", summary="S1")
    retriever.set_reports([rep0, rep1])

    points = [
        MapKeyPoint(
            community_id=0,
            point="Fact 0",
            relevance_score=9.0,
            description="e0",
        ),
        MapKeyPoint(
            community_id=1,
            point="Fact 1",
            relevance_score=8.0,
            description="e1",
        ),
    ]

    with patch.object(
        retriever, "_execute_parallel_map", return_value=points
    ), patch.object(
        retriever,
        "_synthesize_reduce",
        return_value="Assert [Community 0] and [Community 1].",
    ):
        res = retriever.search("query")
        assert "0" in res.citations
        assert "1" in res.citations


def test_issue_7_unverified_edges_do_not_exhaust_traversal_budget():
    drift = DriftSearchEngine(max_context_tokens=40, drift_threshold=0.5)
    drift._adjacency_index = {
        "n1": [
            # Edge 1: huge description, irrelevant (alignment score = 0.01)
            {
                "source": "n1",
                "target": "n2",
                "relation": "irrelevant_rel",
                "description": "very long irrelevant text " * 50,
            },
            # Edge 2: small, highly relevant (alignment score = 0.99)
            {
                "source": "n1",
                "target": "n3",
                "relation": "relevant_rel",
                "description": "short relevant text",
            },
        ]
    }
    drift._node_meta = {
        "n1": {"id": "n1", "name": "n1"},
        "n2": {"id": "n2", "name": "n2"},
        "n3": {"id": "n3", "name": "n3"},
    }

    facets = [
        DriftFacet(
            sub_query="Explore n1",
            target_entities=["n1"],
            relevance_score=1.0,
        )
    ]

    with patch.object(
        drift, "_compute_alignment_score", side_effect=[0.01, 0.99]
    ):
        verified, depth, pruned = drift._traverse_and_prune(
            facets, "test query", "framing"
        )
        assert pruned == 1
        assert len(verified) == 1
        assert verified[0]["target"] == "n3"


def test_issue_8_relationship_citation_whitespace_case_and_colon():
    drift = DriftSearchEngine()
    rep = CommunityReport(
        community_id="comm_1",
        level=0,
        title="Title",
        summary="Summary",
        findings=[],
        member_entities=["Node.js", "API/v1"],
    )
    drift.set_reports([rep])
    drift._adjacency_index = {
        "Node.js": [
            {
                "source": "Node.js",
                "target": "API/v1",
                "relation": "exposes",
                "description": "Exposes REST API",
            }
        ]
    }
    drift._node_meta = {
        "Node.js": {"id": "Node.js", "name": "Node.js"},
        "API/v1": {"id": "API/v1", "name": "API/v1"},
    }

    # LLM outputs space around brackets, uppercase relation, and trailing colon
    mock_llm = MagicMock()
    mock_llm.generate.return_value = (
        "Evidence from (Node.js - [EXPOSES] -> API/v1: REST endpoints)."
    )
    drift.llm = mock_llm

    result = drift.search("Node.js exposes API/v1")
    assert "(Node.js -[exposes]-> API/v1)" in result.citations


def test_issue_11_dict_of_edges_and_neo4j_node_props():
    drift = DriftSearchEngine()
    graph_dict = {
        "nodes": [
            {"id": "n1", "n": {"name": "Neo4j Service A"}},
            {"id": "n2", "properties": {"name": "Service B"}},
        ],
        "edges": {
            "e1": {
                "source": "n1",
                "target": "n2",
                "relation": "CALLS",
                "description": "Service A calls Service B",
            }
        },
    }
    drift.set_knowledge_graph(graph_dict)
    assert "n1" in drift._adjacency_index
    assert drift._adjacency_index["n1"][0]["relation"] == "CALLS"
    assert drift._node_meta["n1"]["name"] == "Neo4j Service A"


def test_issue_11_networkx_multigraph_4tuple():
    drift = DriftSearchEngine()

    class MockMultiGraph:
        def __init__(self):
            self.nodes = [
                ("srv1", {"name": "Server 1"}),
                ("srv2", {"name": "Server 2"}),
            ]
            self.edges = [
                (
                    "srv1",
                    "srv2",
                    0,
                    {"relation": "REPLICATES_TO", "description": "Replication"},
                )
            ]

    drift.set_knowledge_graph(MockMultiGraph())
    assert "srv1" in drift._adjacency_index
    edge = drift._adjacency_index["srv1"][0]
    assert edge["relation"] == "REPLICATES_TO"
    assert edge["description"] == "Replication"
