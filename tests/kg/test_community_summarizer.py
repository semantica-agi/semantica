"""
Unit and integration tests for Hierarchical Community Summarizer (PR #2).

Covers CommunityReport dataclass, CommunityReportLLMSchema validation,
centrality-based token budgeting, context packing, caching with atomic disk
persistence, multi-tier LLM unwrapping, and hierarchical bottom-up synthesis.
"""

import json
from pathlib import Path
import tempfile
import threading
from unittest.mock import MagicMock

import networkx as nx
import pytest

from semantica.kg import (
    CommunityHierarchy,
    CommunityReport,
    CommunitySummarizer,
    HierarchicalCommunity,
    estimate_tokens,
    summarize_community,
    summarize_hierarchy,
)
from semantica.kg.community_summarizer import CommunityReportLLMSchema
from semantica.kg.registry import algorithm_registry, method_registry


# ---------------------------------------------------------------------------
# Test CommunityReport Dataclass
# ---------------------------------------------------------------------------


class TestCommunityReport:
    """Unit tests for CommunityReport dataclass and serialization."""

    def test_init_defaults(self):
        rep = CommunityReport(
            community_id="c_0",
            level=0,
            title="Technology Cluster",
            summary="Entities focused on algorithms.",
        )
        assert rep.community_id == "c_0"
        assert rep.level == 0
        assert rep.title == "Technology Cluster"
        assert rep.summary == "Entities focused on algorithms."
        assert rep.findings == []
        assert rep.impact_rating == 5.0
        assert rep.rating_explanation == ""
        assert rep.member_entities == []
        assert rep.content_hash == ""
        assert rep.sub_communities == []
        assert rep.parent_id is None
        assert rep.rank == 0.0
        assert rep.embedding is None
        assert rep.metadata == {}

    def test_post_init_normalization(self):
        rep = CommunityReport(
            community_id="c_1",
            level=1,
            title="  Data Science Core  ",
            summary="  A central hub.  ",
            findings=[
                "Direct finding 1",
                {"summary": "Finding 2", "score": 9},
            ],
            impact_rating=15.0,  # Clamped to 10.0
            rating_explanation="  Critical importance.  ",
            member_entities=["node_b", "node_a", "node_b"],
            sub_communities=["sub_2", "sub_1"],
            parent_id=10,
            rank=4.5,
            embedding=[0.1, 0.2, 0.3],
        )
        assert rep.title == "Data Science Core"
        assert rep.summary == "A central hub."
        assert rep.impact_rating == 10.0
        assert rep.rating_explanation == "Critical importance."
        assert rep.member_entities == ["node_a", "node_b"]
        assert rep.sub_communities == ["sub_1", "sub_2"]
        assert rep.parent_id == "10"
        assert rep.embedding == [0.1, 0.2, 0.3]
        assert len(rep.findings) == 2
        assert rep.findings[0] == {
            "summary": "Direct finding 1",
            "explanation": "",
        }
        assert rep.findings[1] == {"summary": "Finding 2", "score": 9}

    def test_impact_rating_clamped_low(self):
        rep = CommunityReport(
            community_id="c_low",
            level=0,
            title="Low",
            summary="Low impact",
            impact_rating=-2.0,
        )
        assert rep.impact_rating == 1.0

    def test_to_dict_and_from_dict_roundtrip(self):
        rep1 = CommunityReport(
            community_id="c_roundtrip",
            level=2,
            title="Roundtrip Test",
            summary="Ensuring perfect serialization fidelity.",
            findings=[{"summary": "Finding A", "explanation": "Detail A"}],
            impact_rating=8.5,
            rating_explanation="High strategic importance.",
            member_entities=["e1", "e2", "e3"],
            content_hash="deadbeef" * 8,
            sub_communities=["child_0", "child_1"],
            parent_id="root_c",
            rank=12.34,
            embedding=[0.5, 0.25, 0.125],
            metadata={"source": "unit_test", "coarsening_step": 2},
        )
        d = rep1.to_dict()
        rep2 = CommunityReport.from_dict(d)

        assert rep1.community_id == rep2.community_id
        assert rep1.level == rep2.level
        assert rep1.title == rep2.title
        assert rep1.summary == rep2.summary
        assert rep1.findings == rep2.findings
        assert rep1.impact_rating == rep2.impact_rating
        assert rep1.rating_explanation == rep2.rating_explanation
        assert rep1.member_entities == rep2.member_entities
        assert rep1.content_hash == rep2.content_hash
        assert rep1.sub_communities == rep2.sub_communities
        assert rep1.parent_id == rep2.parent_id
        assert rep1.rank == rep2.rank
        assert rep1.embedding == rep2.embedding
        assert rep1.metadata == rep2.metadata

    def test_to_json_and_from_json_roundtrip(self):
        rep = CommunityReport(
            community_id="c_json",
            level=1,
            title="JSON Test",
            summary="Testing json string handling.",
            findings=[{"summary": "Finding J", "explanation": "Evidence J"}],
            impact_rating=7.0,
        )
        json_str = rep.to_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["community_id"] == "c_json"

        restored = CommunityReport.from_json(json_str)
        assert restored.title == "JSON Test"
        assert restored.impact_rating == 7.0

    def test_to_markdown_formatting(self):
        rep = CommunityReport(
            community_id="c_md",
            level=1,
            title="Executive Neural Network Cluster",
            summary="High degree interconnectivity between models.",
            findings=[
                {
                    "summary": "Fast convergence",
                    "explanation": "Residual connections accelerate learning.",
                },
                "Auxiliary finding without detail",
            ],
            impact_rating=8.0,
            rating_explanation="Dominates model performance.",
            member_entities=["ResNet", "Transformer", "MLP"],
        )
        md = rep.to_markdown()

        assert "# Executive Neural Network Cluster" in md
        assert "**Community ID:** c_md" in md
        assert "**Level:** 1" in md
        assert "**Impact Rating:** 8.0/10" in md
        assert "*Dominates model performance.*" in md
        assert "## Summary" in md
        assert "High degree interconnectivity between models." in md
        assert "## Key Findings" in md
        assert "- **Fast convergence**: Residual connections" in md
        assert "- **Auxiliary finding without detail**" in md
        assert "## Member Entities" in md
        assert "MLP, ResNet, Transformer" in md


# ---------------------------------------------------------------------------
# Test CommunityReportLLMSchema Validation
# ---------------------------------------------------------------------------


class TestCommunityReportLLMSchema:
    """Unit tests for Pydantic v2 CommunityReportLLMSchema normalization."""

    def test_defaults(self):
        schema = CommunityReportLLMSchema()
        assert schema.title == "Community Summary"
        assert schema.summary == ""
        assert schema.findings == []
        assert schema.impact_rating == 5.0
        assert schema.rating_explanation == ""

    def test_normalize_title(self):
        s1 = CommunityReportLLMSchema(title=None)
        assert s1.title == "Community Summary"

        s2 = CommunityReportLLMSchema(title="   ")
        assert s2.title == "Community Summary"

        s3 = CommunityReportLLMSchema(title="  Custom Title  ")
        assert s3.title == "Custom Title"

    def test_normalize_summary(self):
        s1 = CommunityReportLLMSchema(summary=None)
        assert s1.summary == ""

        s2 = CommunityReportLLMSchema(summary="  Useful summary  ")
        assert s2.summary == "Useful summary"

        s3 = CommunityReportLLMSchema(summary={"overview": "dict summary"})
        assert '{"overview": "dict summary"}' in s3.summary

    def test_normalize_impact_rating_clamping(self):
        s1 = CommunityReportLLMSchema(impact_rating=-10.0)
        assert s1.impact_rating == 1.0

        s2 = CommunityReportLLMSchema(impact_rating=18.5)
        assert s2.impact_rating == 10.0

        s3 = CommunityReportLLMSchema(impact_rating=6.4)
        assert s3.impact_rating == 6.4

    def test_normalize_impact_rating_strings(self):
        s1 = CommunityReportLLMSchema(impact_rating="Rating is 8.5/10")
        assert s1.impact_rating == 8.5

        s2 = CommunityReportLLMSchema(impact_rating="9")
        assert s2.impact_rating == 9.0

        s3 = CommunityReportLLMSchema(impact_rating="No rating specified")
        assert s3.impact_rating == 5.0

        s4 = CommunityReportLLMSchema(impact_rating=None)
        assert s4.impact_rating == 5.0

    def test_normalize_findings(self):
        # List of dicts
        s1 = CommunityReportLLMSchema(
            findings=[{"summary": "A", "explanation": "B"}]
        )
        assert s1.findings == [{"summary": "A", "explanation": "B"}]

        # Single dict
        s2 = CommunityReportLLMSchema(
            findings={"summary": "Single", "explanation": "Wrapped"}
        )
        assert s2.findings == [{"summary": "Single", "explanation": "Wrapped"}]

        # List of strings
        s3 = CommunityReportLLMSchema(findings=["String 1", "String 2"])
        assert s3.findings == [
            {"summary": "String 1", "explanation": ""},
            {"summary": "String 2", "explanation": ""},
        ]

        # JSON encoded list
        s4 = CommunityReportLLMSchema(
            findings='[{"summary": "From JSON", "explanation": "Parsed"}]'
        )
        assert s4.findings == [
            {"summary": "From JSON", "explanation": "Parsed"}
        ]

        # Plain string
        s5 = CommunityReportLLMSchema(findings="Plain string finding")
        assert s5.findings == [
            {"summary": "Plain string finding", "explanation": ""}
        ]

        # None
        s6 = CommunityReportLLMSchema(findings=None)
        assert s6.findings == []


# ---------------------------------------------------------------------------
# Test Token Estimation and Centrality Budgeting
# ---------------------------------------------------------------------------


class TestTokenEstimationAndCentrality:
    """Unit tests for token estimation and centrality score extraction."""

    def test_estimate_tokens_default(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0
        assert estimate_tokens("abc") == 1
        assert estimate_tokens("a" * 16) == 4
        assert estimate_tokens("a" * 17) == 5

    def test_estimate_tokens_custom_counter(self):
        custom = lambda s: len(s.split())  # noqa: E731
        text = "Four words in text"
        assert estimate_tokens(text, custom_counter=custom) == 4

    def test_centrality_computation_networkx(self):
        g = nx.Graph()
        g.add_edges_from([("A", "B"), ("A", "C"), ("B", "C"), ("C", "D")])

        comm = HierarchicalCommunity(
            id="c_test",
            level=0,
            index=0,
            entity_ids=["A", "B", "C", "D"],
            edges=[
                {"source": "A", "target": "B"},
                {"source": "A", "target": "C"},
                {"source": "B", "target": "C"},
                {"source": "C", "target": "D"},
            ],
        )
        summarizer = CommunitySummarizer()
        scores = summarizer._compute_centrality(g, comm.entity_ids)

        assert "C" in scores
        # C has highest degree (3 connections)
        assert scores["C"] > scores["D"]
        assert all(isinstance(v, float) for v in scores.values())

    def test_centrality_computation_non_networkx_dict(self):
        graph_dict = {
            "entities": [{"id": "X"}, {"id": "Y"}, {"id": "Z"}],
            "relationships": [
                {"source": "X", "target": "Y"},
                {"source": "X", "target": "Z"},
            ],
        }
        summarizer = CommunitySummarizer()
        scores = summarizer._compute_centrality(graph_dict, ["X", "Y", "Z"])
        assert "X" in scores
        assert scores["X"] > scores["Y"]

    def test_centrality_missing_entity_fallback(self):
        g = nx.Graph()
        g.add_edge("M1", "M2")
        summarizer = CommunitySummarizer()
        # Entity M3 is not present in graph
        scores = summarizer._compute_centrality(g, ["M1", "M2", "M3"])
        assert scores["M3"] == 0.0


# ---------------------------------------------------------------------------
# Test Context Packing
# ---------------------------------------------------------------------------


class TestContextPacking:
    """Unit tests for context packing within max_tokens."""

    def test_pack_context_level_0(self):
        comm = HierarchicalCommunity(
            id="c_leaf",
            level=0,
            index=0,
            entity_ids=["E1", "E2", "E3"],
            edges=[
                {
                    "source": "E1",
                    "target": "E2",
                    "attributes": {"type": "LINK"},
                },
                {
                    "source": "E2",
                    "target": "E3",
                    "attributes": {"type": "LINK"},
                },
            ],
        )
        summarizer = CommunitySummarizer(max_tokens=2000)
        subgraph = summarizer._extract_subgraph(comm, None)
        ctx = summarizer._pack_context(comm, subgraph)

        assert "Community ID: c_leaf" in ctx
        assert "Level: 0" in ctx
        assert "Total Member Entities: 3" in ctx
        assert "Anchor Entities" in ctx
        assert "E2" in ctx

    def test_pack_context_level_1_child_reports_budget_and_sorting(self):
        child1 = CommunityReport(
            community_id="c_child_1",
            level=0,
            title="Low Priority Child",
            summary="Low impact findings.",
            impact_rating=3.0,
            member_entities=["A", "B"],
        )
        child2 = CommunityReport(
            community_id="c_child_2",
            level=0,
            title="High Priority Child",
            summary="Critical vulnerability identified.",
            impact_rating=9.5,
            member_entities=["C", "D"],
        )
        parent_comm = HierarchicalCommunity(
            id="c_parent",
            level=1,
            index=0,
            entity_ids=["A", "B", "C", "D"],
            child_ids=["c_child_1", "c_child_2"],
            edges=[
                {
                    "source": "B",
                    "target": "C",
                    "attributes": {"type": "BRIDGE"},
                },
                {
                    "source": "A",
                    "target": "B",
                    "attributes": {"type": "INTERNAL"},
                },
            ],
        )
        summarizer = CommunitySummarizer(max_tokens=3000)
        subgraph = summarizer._extract_subgraph(parent_comm, None)
        ctx = summarizer._pack_context(
            parent_comm,
            subgraph,
            child_reports=[child1, child2],
        )

        assert "Child Community Reports" in ctx
        # Child 2 (impact 9.5) must appear before Child 1 (impact 3.0)
        idx_child2 = ctx.find("Sub-Community c_child_2")
        idx_child1 = ctx.find("Sub-Community c_child_1")
        assert idx_child2 != -1
        assert idx_child1 != -1
        assert idx_child2 < idx_child1

        # Bridge edge between child communities must be present
        assert "BRIDGE" in ctx

    def test_pack_context_respects_token_budget(self):
        comm = HierarchicalCommunity(
            id="c_tight",
            level=0,
            index=0,
            entity_ids=[f"Node_{i}" for i in range(100)],
            edges=[
                {"source": f"Node_{i}", "target": f"Node_{i+1}"}
                for i in range(99)
            ],
        )
        # Small max_tokens budget
        summarizer = CommunitySummarizer(max_tokens=450)
        subgraph = summarizer._extract_subgraph(comm, None)
        ctx = summarizer._pack_context(comm, subgraph, max_tokens=450)

        # Must not crash and should produce a valid context
        assert "Community ID: c_tight" in ctx
        total_tokens = estimate_tokens(ctx)
        assert total_tokens < 600


# ---------------------------------------------------------------------------
# Test Caching and Persistence
# ---------------------------------------------------------------------------


class TestCachingAndPersistence:
    """Unit tests for SHA-256 caching and atomic disk persistence."""

    def test_in_memory_cache_hit(self):
        comm = HierarchicalCommunity(
            id="c_cached",
            level=0,
            index=0,
            entity_ids=["N1", "N2"],
        )
        mock_llm = MagicMock()
        mock_llm.generate_structured.return_value = {
            "title": "Generated Once",
            "summary": "Called only on cache miss.",
            "impact_rating": 7.0,
        }

        summarizer = CommunitySummarizer(llm=mock_llm, cache_enabled=True)

        rep1 = summarizer.summarize_community(comm)
        assert rep1.title == "Generated Once"
        assert mock_llm.generate_structured.call_count == 1

        # Second call must hit cache
        rep2 = summarizer.summarize_community(comm)
        assert rep2.title == "Generated Once"
        assert mock_llm.generate_structured.call_count == 1

    def test_disk_cache_atomic_write_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            comm = HierarchicalCommunity(
                id="c_disk",
                level=0,
                index=0,
                entity_ids=["D1", "D2"],
            )
            mock_llm = MagicMock()
            mock_llm.generate_structured.return_value = {
                "title": "Disk Persisted Report",
                "summary": "Should be saved to disk atomically.",
                "impact_rating": 8.0,
            }

            s1 = CommunitySummarizer(
                llm=mock_llm, cache_dir=tmpdir, cache_enabled=True
            )
            rep1 = s1.summarize_community(comm)
            assert rep1.title == "Disk Persisted Report"

            cache_file = Path(tmpdir) / f"{comm.content_hash}.json"
            assert cache_file.exists()

            with open(cache_file, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
            assert disk_data["community_id"] == "c_disk"
            assert disk_data["title"] == "Disk Persisted Report"

            # Create new summarizer with empty cache pointing to same dir
            mock_llm2 = MagicMock()
            s2 = CommunitySummarizer(
                llm=mock_llm2, cache_dir=tmpdir, cache_enabled=True
            )
            rep2 = s2.summarize_community(comm)

            assert rep2.title == "Disk Persisted Report"
            # mock_llm2 should not have been called due to disk cache hit
            assert mock_llm2.generate_structured.call_count == 0

    def test_cache_invalidation_and_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            comm = HierarchicalCommunity(
                id="c_inv",
                level=0,
                index=0,
                entity_ids=["I1"],
            )
            summarizer = CommunitySummarizer(
                cache_dir=tmpdir, cache_enabled=True
            )
            rep = summarizer.summarize_community(comm)
            h = comm.content_hash

            assert summarizer.get_cached_report(h) is not None
            assert (Path(tmpdir) / f"{h}.json").exists()

            # Invalidate
            assert summarizer.invalidate(h) is True
            assert summarizer.get_cached_report(h) is None
            assert not (Path(tmpdir) / f"{h}.json").exists()

            # Re-cache and clear_cache
            summarizer.cache_report(h, rep)
            assert summarizer.get_cached_report(h) is not None
            summarizer.clear_cache()
            assert summarizer.get_cached_report(h) is None

    def test_bypass_cache(self):
        comm = HierarchicalCommunity(
            id="c_bypass",
            level=0,
            index=0,
            entity_ids=["B1"],
        )
        mock_llm = MagicMock()
        mock_llm.generate_structured.side_effect = [
            {"title": "First"},
            {"title": "Second"},
        ]
        summarizer = CommunitySummarizer(llm=mock_llm, cache_enabled=True)

        rep1 = summarizer.summarize_community(comm)
        assert rep1.title == "First"

        rep2 = summarizer.summarize_community(comm, use_cache=False)
        assert rep2.title == "Second"
        assert mock_llm.generate_structured.call_count == 2

    def test_concurrent_caching_thread_safety(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            summarizer = CommunitySummarizer(
                cache_dir=tmpdir, cache_enabled=True
            )
            errors = []

            def worker(thread_idx):
                try:
                    for i in range(10):
                        comm = HierarchicalCommunity(
                            id=f"comm_{thread_idx}_{i}",
                            level=0,
                            index=i,
                            entity_ids=[f"node_{thread_idx}_{i}"],
                        )
                        rep = summarizer.summarize_community(comm)
                        assert rep.community_id == f"comm_{thread_idx}_{i}"
                except Exception as ex:
                    errors.append(ex)

            threads = [
                threading.Thread(target=worker, args=(t,)) for t in range(5)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == []


# ---------------------------------------------------------------------------
# Test Multi-Tier LLM Unwrapping
# ---------------------------------------------------------------------------


class TestMultiTierLLMUnwrap:
    """Unit tests verifying all tiers of LLM invocation."""

    @pytest.fixture
    def sample_community(self):
        return HierarchicalCommunity(
            id="c_tier",
            level=0,
            index=0,
            entity_ids=["N_A", "N_B"],
            edges=[{"source": "N_A", "target": "N_B"}],
        )

    def test_tier_1_generate_typed(self, sample_community):
        mock_llm = MagicMock()
        mock_llm.generate_typed.return_value = CommunityReportLLMSchema(
            title="Tier 1 Generated",
            summary="Generated via generate_typed.",
            impact_rating=9.0,
        )
        summarizer = CommunitySummarizer(llm=mock_llm)
        report = summarizer.summarize_community(sample_community)

        assert report.title == "Tier 1 Generated"
        assert report.impact_rating == 9.0
        assert mock_llm.generate_typed.called

    def test_tier_2_provider_generate_typed(self, sample_community):
        provider = MagicMock()
        provider.generate_typed.return_value = CommunityReportLLMSchema(
            title="Tier 2 Provider Generated",
            summary="Generated via provider.generate_typed.",
            impact_rating=8.0,
        )
        wrapper_llm = MagicMock(spec=["provider"])
        wrapper_llm.provider = provider

        summarizer = CommunitySummarizer(llm=wrapper_llm)
        report = summarizer.summarize_community(sample_community)

        assert report.title == "Tier 2 Provider Generated"
        assert provider.generate_typed.called

    def test_tier_3_generate_structured(self, sample_community):
        mock_llm = MagicMock(spec=["generate_structured"])
        mock_llm.generate_structured.return_value = {
            "title": "Tier 3 Structured",
            "summary": "Generated via generate_structured dict.",
            "findings": [{"summary": "Finding 3", "explanation": "Detail 3"}],
            "impact_rating": 7.5,
        }
        summarizer = CommunitySummarizer(llm=mock_llm)
        report = summarizer.summarize_community(sample_community)

        assert report.title == "Tier 3 Structured"
        assert report.impact_rating == 7.5
        assert len(report.findings) == 1

    def test_tier_4_generate_json_string(self, sample_community):
        mock_llm = MagicMock(spec=["generate"])
        mock_llm.generate.return_value = (
            "```json\n"
            "{\n"
            '  "title": "Tier 4 Regex JSON",\n'
            '  "summary": "Extracted from markdown code block.",\n'
            '  "findings": [{"summary": "Finding 4"}],\n'
            '  "impact_rating": "6.5"\n'
            "}\n"
            "```"
        )
        summarizer = CommunitySummarizer(llm=mock_llm)
        report = summarizer.summarize_community(sample_community)

        assert report.title == "Tier 4 Regex JSON"
        assert report.impact_rating == 6.5

    def test_tier_4_freeform_text_fallback(self, sample_community):
        mock_llm = MagicMock(spec=["generate"])
        mock_llm.generate.return_value = (
            "This community represents an interconnected group of nodes."
        )
        summarizer = CommunitySummarizer(llm=mock_llm)
        report = summarizer.summarize_community(sample_community)

        assert report.title == f"Community {sample_community.id} Summary"
        assert "interconnected group" in report.summary

    def test_tier_5_callable(self, sample_community):
        def callable_llm(prompt: str):
            return {
                "title": "Tier 5 Callable Result",
                "summary": "Returned directly from callable.",
                "impact_rating": 6.0,
            }

        summarizer = CommunitySummarizer(llm=callable_llm)
        report = summarizer.summarize_community(sample_community)

        assert report.title == "Tier 5 Callable Result"
        assert report.impact_rating == 6.0

    def test_extractive_fallback_when_no_llm(self, sample_community):
        summarizer = CommunitySummarizer(llm=None)
        report = summarizer.summarize_community(sample_community)

        assert f"Community {sample_community.id}" in report.title
        assert "contains 2 entities" in report.summary
        assert report.impact_rating == 5.0


# ---------------------------------------------------------------------------
# Test Subgraph Extraction Fallbacks
# ---------------------------------------------------------------------------


class TestSubgraphExtraction:
    """Unit tests for subgraph extraction fallbacks."""

    def test_fallback_when_graph_is_none(self):
        comm = HierarchicalCommunity(
            id="c_none",
            level=0,
            index=0,
            entity_ids=["X1", "X2"],
            edges=[
                {"source": "X1", "target": "X2", "attributes": {"weight": 1.5}}
            ],
        )
        summarizer = CommunitySummarizer()
        sub = summarizer._extract_subgraph(comm, graph=None)

        if isinstance(sub, nx.Graph):
            assert "X1" in sub.nodes
            assert "X2" in sub.nodes
            assert sub.has_edge("X1", "X2")
        else:
            assert len(sub["entities"]) == 2

    def test_subgraph_from_nx_graph(self):
        g = nx.Graph()
        g.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])

        comm = HierarchicalCommunity(
            id="c_nx",
            level=0,
            index=0,
            entity_ids=["A", "B"],
        )
        summarizer = CommunitySummarizer()
        sub = summarizer._extract_subgraph(comm, graph=g)

        assert isinstance(sub, nx.Graph)
        assert set(sub.nodes) == {"A", "B"}
        assert sub.has_edge("A", "B")
        assert not sub.has_node("D")

    def test_subgraph_from_community_hierarchy(self):
        comm = HierarchicalCommunity(
            id="c_h",
            level=0,
            index=0,
            entity_ids=["H1", "H2"],
            edges=[{"source": "H1", "target": "H2"}],
        )
        g = nx.Graph()
        g.add_edge("H1", "H2")
        hierarchy = CommunityHierarchy(communities=[comm], graph=g)

        summarizer = CommunitySummarizer()
        sub = summarizer._extract_subgraph(comm, graph=hierarchy)

        assert isinstance(sub, nx.Graph)
        assert set(sub.nodes) == {"H1", "H2"}


# ---------------------------------------------------------------------------
# Test Hierarchical Synthesis (Bottom-Up)
# ---------------------------------------------------------------------------


class TestHierarchicalSynthesis:
    """Unit tests for bottom-up multi-level hierarchy summarization."""

    @pytest.fixture
    def multi_level_hierarchy(self):
        # Level 0 communities
        comm_0_0 = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["A", "B"],
            parent_id="c_1_0",
            edges=[{"source": "A", "target": "B"}],
        )
        comm_0_1 = HierarchicalCommunity(
            id="c_0_1",
            level=0,
            index=1,
            entity_ids=["C", "D"],
            parent_id="c_1_0",
            edges=[{"source": "C", "target": "D"}],
        )
        # Level 1 community (parent of 0_0 and 0_1)
        comm_1_0 = HierarchicalCommunity(
            id="c_1_0",
            level=1,
            index=0,
            entity_ids=["A", "B", "C", "D"],
            child_ids=["c_0_0", "c_0_1"],
            edges=[
                {"source": "A", "target": "B"},
                {"source": "C", "target": "D"},
                {
                    "source": "B",
                    "target": "C",
                    "attributes": {"type": "BRIDGE"},
                },
            ],
        )
        g = nx.Graph()
        g.add_edges_from([("A", "B"), ("C", "D"), ("B", "C")])

        return CommunityHierarchy(
            communities=[comm_0_0, comm_0_1, comm_1_0], graph=g
        )

    def test_summarize_hierarchy_bottom_up(self, multi_level_hierarchy):
        generated_prompts = []

        def tracking_llm(prompt: str):
            generated_prompts.append(prompt)
            if "Community ID: c_0_0" in prompt:
                return {
                    "title": "Leaf Community 0",
                    "summary": "Summary for leaf 0.",
                    "impact_rating": 8.0,
                }
            if "Community ID: c_0_1" in prompt:
                return {
                    "title": "Leaf Community 1",
                    "summary": "Summary for leaf 1.",
                    "impact_rating": 6.0,
                }
            return {
                "title": "Synthesized Coarse Community",
                "summary": "Aggregated from children.",
                "impact_rating": 9.0,
            }

        summarizer = CommunitySummarizer(llm=tracking_llm)
        reports = summarizer.summarize_hierarchy(multi_level_hierarchy)

        assert len(reports) == 3
        assert "c_0_0" in reports
        assert "c_0_1" in reports
        assert "c_1_0" in reports

        # Level 0 reports
        assert reports["c_0_0"].title == "Leaf Community 0"
        assert reports["c_0_1"].title == "Leaf Community 1"

        # Level 1 report
        assert reports["c_1_0"].title == "Synthesized Coarse Community"
        assert reports["c_1_0"].sub_communities == ["c_0_0", "c_0_1"]

        # Verify that parent prompt received child reports
        parent_prompt = [p for p in generated_prompts if "c_1_0" in p][0]
        assert "Child Community Reports" in parent_prompt
        assert "Leaf Community 0" in parent_prompt
        assert "Leaf Community 1" in parent_prompt

    def test_summarize_empty_hierarchy(self):
        empty_hierarchy = CommunityHierarchy()
        summarizer = CommunitySummarizer()
        reports = summarizer.summarize_hierarchy(empty_hierarchy)
        assert reports == {}

    def test_summarize_hierarchy_levels_filter(self, multi_level_hierarchy):
        summarizer = CommunitySummarizer()
        reports = summarizer.summarize_hierarchy(
            multi_level_hierarchy, levels=[1]
        )
        assert len(reports) == 1
        assert "c_1_0" in reports
        assert "c_0_0" not in reports


# ---------------------------------------------------------------------------
# Test Functional Wrappers and Registry Wiring
# ---------------------------------------------------------------------------


class TestRegistryAndWrappers:
    """Unit tests for methods.py wrappers and registry bindings."""

    def test_functional_wrapper_summarize_community(self):
        comm = HierarchicalCommunity(
            id="c_fn",
            level=0,
            index=0,
            entity_ids=["F1", "F2"],
        )
        rep = summarize_community(comm)
        assert isinstance(rep, CommunityReport)
        assert rep.community_id == "c_fn"

    def test_functional_wrapper_summarize_hierarchy(self):
        comm = HierarchicalCommunity(
            id="c_h_fn",
            level=0,
            index=0,
            entity_ids=["H1"],
        )
        hierarchy = CommunityHierarchy(communities=[comm])
        reports = summarize_hierarchy(hierarchy)
        assert "c_h_fn" in reports
        assert isinstance(reports["c_h_fn"], CommunityReport)

    def test_method_registry_bindings(self):
        assert method_registry.get("community_summary", "default") is not None
        assert (
            method_registry.get("community_summary", "summarizer") is not None
        )
        assert method_registry.get("community_summary", "llm") is not None
        assert (
            method_registry.get("community_summary", "hierarchy") is not None
        )

    def test_algorithm_registry_bindings(self):
        algo_cls = algorithm_registry.get("community_summary", "default")
        assert algo_cls is CommunitySummarizer

        instance = algorithm_registry.create_instance(
            "community_summary", "default", max_tokens=1500
        )
        assert isinstance(instance, CommunitySummarizer)
        assert instance.max_tokens == 1500

    def test_embedder_integration(self):
        comm = HierarchicalCommunity(
            id="c_emb",
            level=0,
            index=0,
            entity_ids=["E1"],
        )
        fake_embedder = lambda s: [0.1, 0.2, 0.3]  # noqa: E731
        summarizer = CommunitySummarizer(embedder=fake_embedder)
        report = summarizer.summarize_community(comm)
        assert report.embedding == [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# Test Edge Cases and Bug Fixes
# ---------------------------------------------------------------------------


class TestEdgeCasesAndBugFixes:
    """Tests for edge cases, sanitization, deep copy, and robust fallbacks."""

    def test_edge_attributes_none_does_not_crash(self):
        comm = HierarchicalCommunity(
            id="c_edge_none",
            level=0,
            index=0,
            entity_ids=["A", "B"],
            edges=[{"source": "A", "target": "B", "attributes": None}],
        )
        summarizer = CommunitySummarizer()
        subgraph = summarizer._extract_subgraph(comm, None)
        ctx = summarizer._pack_context(comm, subgraph)
        assert "CONNECTED_TO" in ctx

    def test_bridge_edges_extracted_from_subgraph_when_edges_empty(self):
        comm = HierarchicalCommunity(
            id="c_no_edges",
            level=0,
            index=0,
            entity_ids=["N1", "N2"],
            edges=[],
        )
        g = nx.Graph()
        g.add_edge("N1", "N2", type="RELATION")

        summarizer = CommunitySummarizer()
        subgraph = summarizer._extract_subgraph(comm, graph=g)
        ctx = summarizer._pack_context(comm, subgraph)
        assert "RELATION" in ctx

    def test_summarize_hierarchy_propagates_graph(self):
        comm = HierarchicalCommunity(
            id="c_h_prop",
            level=0,
            index=0,
            entity_ids=["X1", "X2"],
            edges=[],
        )
        g = nx.Graph()
        g.add_edge("X1", "X2", type="PROPAGATED_EDGE")
        hierarchy = CommunityHierarchy(communities=[comm], graph=g)

        recorded_prompts = []

        def llm_check(prompt: str):
            recorded_prompts.append(prompt)
            return {"title": "Title", "summary": "Summary"}

        summarizer = CommunitySummarizer(llm=llm_check)
        reports = summarizer.summarize_hierarchy(hierarchy)
        assert "c_h_prop" in reports
        assert any("PROPAGATED_EDGE" in p for p in recorded_prompts)

    def test_llm_kwargs_forwarded_to_provider(self):
        comm = HierarchicalCommunity(
            id="c_kwargs",
            level=0,
            index=0,
            entity_ids=["E1"],
        )
        mock_llm = MagicMock()
        mock_llm.generate_typed.return_value = CommunityReportLLMSchema(
            title="Kwargs Passed",
            summary="Checked kwargs",
        )
        summarizer = CommunitySummarizer(llm=mock_llm)
        summarizer.summarize_community(
            comm, temperature=0.3, max_retries=5
        )
        mock_llm.generate_typed.assert_called_once()
        _, kwargs = mock_llm.generate_typed.call_args
        assert kwargs.get("temperature") == 0.3
        assert kwargs.get("max_retries") == 5

    def test_loose_dictionary_community_input(self):
        summarizer = CommunitySummarizer()
        rep = summarizer.summarize_community(
            {"id": "loose_comm", "entity_ids": ["L1", "L2"]}
        )
        assert rep.community_id == "loose_comm"
        assert rep.level == 0
        assert rep.member_entities == ["L1", "L2"]

    def test_custom_centrality_direct_dict_output(self):
        class DirectCalculator:
            def calculate_degree_centrality(self, g):
                return {"N1": 0.9, "N2": 0.1}

        summarizer = CommunitySummarizer(
            centrality_calculator=DirectCalculator()
        )
        scores = summarizer._compute_centrality(None, ["N1", "N2"])
        assert scores["N1"] == 0.9
        assert scores["N2"] == 0.1

    def test_cache_key_sanitization_and_traversal_prevention(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            summarizer = CommunitySummarizer(cache_dir=tmpdir)
            path = summarizer._cache_path("../../malicious:key")
            assert path is not None
            assert (
                Path(tmpdir).resolve() in path.resolve().parents
                or path.parent == Path(tmpdir)
            )
            assert ":" not in path.name
            assert ".." not in str(path)

    def test_to_dict_deep_copies_findings(self):
        rep = CommunityReport(
            community_id="c_copy",
            level=0,
            title="Copy Test",
            summary="Summary",
            findings=[{"summary": "Original", "explanation": "Detail"}],
        )
        d = rep.to_dict()
        d["findings"][0]["summary"] = "Mutated"
        assert rep.findings[0]["summary"] == "Original"

    def test_nan_and_inf_ratings_normalized(self):
        rep = CommunityReport(
            community_id="c_nan",
            level=0,
            title="NaN Test",
            summary="Summary",
            impact_rating=float("nan"),
            rank=float("inf"),
        )
        assert rep.impact_rating == 5.0
        assert rep.rank == 0.0

        schema = CommunityReportLLMSchema(impact_rating=float("nan"))
        assert schema.impact_rating == 5.0

    def test_sub_communities_populated_from_child_reports(self):
        comm = HierarchicalCommunity(
            id="c_parent_sub",
            level=1,
            index=0,
            entity_ids=["P1"],
            child_ids=[],
        )
        child_rep = CommunityReport(
            community_id="c_child_sub",
            level=0,
            title="Child",
            summary="Child summary",
        )
        summarizer = CommunitySummarizer()
        rep = summarizer.summarize_community(
            comm, child_reports=[child_rep]
        )
        assert rep.sub_communities == ["c_child_sub"]

    def test_raw_decode_json_extraction_with_surrounding_noise(self):
        summarizer = CommunitySummarizer()
        messy_output = (
            "Here is notes {and remarks}. The actual output:\n"
            '{"title": "Messy JSON", "summary": "Parsed correctly", '
            '"impact_rating": 8.0}\n'
            "Additional explanation text {more notes}."
        )
        parsed = summarizer._extract_json(messy_output)
        assert parsed["title"] == "Messy JSON"
        assert parsed["impact_rating"] == 8.0

    def test_estimate_tokens_counter_errors(self):
        def bad_counter(text):
            raise RuntimeError("Counter crashed")

        assert estimate_tokens("Sample text", custom_counter=bad_counter) > 0

        def negative_counter(text):
            return -5

        assert (
            estimate_tokens(
                "Sample text", custom_counter=negative_counter
            )
            == 0
        )


# ---------------------------------------------------------------------------
# Test Qodo Review Fixes (PR #1605 / Issue #1548)
# ---------------------------------------------------------------------------


class TestQodoReviewFixes:
    """Unit and regression tests for 8 Qodo review issues."""

    def test_substantive_attributes_and_source_evidence_packing(self):
        """Issue 1: Substantive entity/rel attributes & text chunks."""
        comm = HierarchicalCommunity(
            id="c_evidence",
            level=0,
            index=0,
            entity_ids=["ent_1", "ent_2"],
        )
        graph = {
            "entities": [
                {
                    "id": "ent_1",
                    "name": "Alpha Node",
                    "type": "Organization",
                    "description": "Primary research institute",
                    "provenance": "doc_alpha.pdf",
                },
                {
                    "id": "ent_2",
                    "name": "Beta Node",
                    "type": "Person",
                    "description": "Lead investigator",
                },
            ],
            "relationships": [
                {
                    "source": "ent_1",
                    "target": "ent_2",
                    "type": "employs",
                    "weight": 3.0,
                    "description": "Long-term employment relationship",
                    "evidence": "Contract signed 2020",
                }
            ],
        }
        text_chunks = [
            {
                "text": "Alpha Node was founded in 2010 to study AI.",
                "source": "history.txt",
            },
            "Supplementary raw excerpt detailing research outputs.",
        ]

        summarizer = CommunitySummarizer()
        context = summarizer._pack_context(
            comm,
            budget=2000,
            graph=graph,
            text_chunks=text_chunks,
        )

        # Entity substantive attributes
        assert "Alpha Node" in context
        assert "Organization" in context
        assert "Primary research institute" in context
        assert "doc_alpha.pdf" in context

        # Relationship attributes
        assert "employs" in context
        assert "Long-term employment relationship" in context
        assert "Contract signed 2020" in context

        # Source evidence text chunks
        assert "## Source Evidence / Text Excerpts" in context
        assert "Alpha Node was founded in 2010" in context
        assert "history.txt" in context
        assert "Supplementary raw excerpt" in context

    def test_strict_token_budget_tiny_limit(self):
        """Issue 2 & 8: Strict token limit bounding and no tiny floors."""
        # Check constructor does not clamp tiny limits to 100/200
        summarizer = CommunitySummarizer(max_tokens=35)
        assert summarizer.max_tokens == 35

        comm = HierarchicalCommunity(
            id="c_tiny",
            level=0,
            index=0,
            entity_ids=["e1", "e2", "e3", "e4", "e5"],
        )
        graph = nx.complete_graph(["e1", "e2", "e3", "e4", "e5"])

        captured_prompts = []

        def mock_llm(prompt, **kwargs):
            captured_prompts.append(prompt)
            return json.dumps({
                "title": "Tiny Comm",
                "summary": "Short",
                "impact_rating": 5.0,
            })

        rep = summarizer.summarize_community(
            comm,
            graph=graph,
            max_tokens=35,
            llm=mock_llm,
        )
        assert rep is not None
        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # Total prompt must strictly be within max_tokens
        token_count = estimate_tokens(prompt)
        assert token_count <= 35

    def test_strict_token_budget_with_large_scaffolding(self):
        """Issue 2: Large custom system prompt strictly bounded."""
        custom_prompt = "You are an expert analyst. " * 15  # ~60 tokens
        summarizer = CommunitySummarizer(
            system_prompt=custom_prompt,
            max_tokens=120,
        )
        comm = HierarchicalCommunity(
            id="c_scaffold",
            level=0,
            index=0,
            entity_ids=["n1", "n2", "n3"],
        )
        graph = nx.path_graph(["n1", "n2", "n3"])

        captured_prompts = []

        def mock_llm(prompt, **kwargs):
            captured_prompts.append(prompt)
            return json.dumps({
                "title": "Scaffold Comm",
                "summary": "Summary",
                "impact_rating": 6.0,
            })

        summarizer.summarize_community(
            comm,
            graph=graph,
            max_tokens=120,
            llm=mock_llm,
        )
        assert len(captured_prompts) == 1
        assert estimate_tokens(captured_prompts[0]) <= 120

    def test_dict_graph_nodes_and_edges_with_aliases(self):
        """Issue 3: Dict graph nodes/edges, dict values, and aliases."""
        comm = HierarchicalCommunity(
            id="c_dict",
            level=0,
            index=0,
            entity_ids=["N1", "N2"],
        )
        dict_graph = {
            "nodes": {
                "N1": {"name": "Node One", "role": "server"},
                "N2": {"name": "Node Two", "role": "client"},
                "N3": {"name": "Node Three", "role": "external"},
            },
            "edges": [
                {
                    "from": "N1",
                    "to": "N2",
                    "type": "connects_to",
                    "weight": 4.5,
                    "description": "Internal link",
                },
                {
                    "source_id": "N1",
                    "target_id": "N3",
                    "type": "uplink",
                    "weight": 1.0,
                },
            ],
        }

        summarizer = CommunitySummarizer()
        subgraph = summarizer._extract_subgraph(comm, dict_graph)

        # Internal node attributes preserved
        assert "N1" in subgraph["nodes"]
        assert "N2" in subgraph["nodes"]
        assert "N3" not in subgraph["nodes"]
        assert subgraph["nodes"]["N1"]["name"] == "Node One"

        # Internal edges preserved
        assert len(subgraph["edges"]) == 1
        assert subgraph["edges"][0]["from"] == "N1"
        assert subgraph["edges"][0]["to"] == "N2"
        assert subgraph["edges"][0]["description"] == "Internal link"

        # Key relationships / bridge edges from subgraph
        edges = summarizer._identify_bridge_edges(
            comm, subgraph=subgraph
        )
        assert len(edges) == 1
        assert edges[0]["source"] == "N1"
        assert edges[0]["target"] == "N2"
        assert edges[0].get("type") == "connects_to"
        assert edges[0].get("description") == "Internal link"

        # Bridge edges identified when child reports present
        cr1 = CommunityReport(
            community_id="c_sub1",
            level=0,
            title="Sub1",
            summary="S1",
            member_entities=["N1"],
        )
        cr2 = CommunityReport(
            community_id="c_sub2",
            level=0,
            title="Sub2",
            summary="S2",
            member_entities=["N2"],
        )
        bridges = summarizer._identify_bridge_edges(
            comm, child_reports=[cr1, cr2], subgraph=subgraph
        )
        assert len(bridges) == 1
        assert bridges[0]["source"] == "N1"
        assert bridges[0]["target"] == "N2"

    def test_pagerank_centrality_metric_invoked(self):
        """Issue 4: PageRank uses calculate_pagerank; invalid raises error."""
        comm = HierarchicalCommunity(
            id="c_pagerank",
            level=0,
            index=0,
            entity_ids=["A", "B", "C"],
        )
        g = nx.DiGraph()
        g.add_edges_from([("A", "B"), ("B", "C"), ("C", "A")])

        summarizer = CommunitySummarizer(centrality_metric="pagerank")
        scores = summarizer._compute_centrality(g, comm.entity_ids)
        assert len(scores) == 3
        assert all(isinstance(v, float) for v in scores.values())

        # Also works seamlessly on dict graphs via calculator._to_networkx
        dict_g = {
            "nodes": ["A", "B", "C"],
            "edges": [
                {"source": "A", "target": "B"},
                {"source": "B", "target": "C"},
                {"source": "C", "target": "A"},
            ],
        }
        dict_scores = summarizer._compute_centrality(dict_g, comm.entity_ids)
        assert len(dict_scores) == 3

        # Invalid metric rejected with ValueError
        with pytest.raises(ValueError, match="Unsupported centrality metric"):
            CommunitySummarizer(centrality_metric="nonexistent_metric")

    def test_cache_key_varies_with_all_inputs(self):
        """Issue 5: Cache key includes graph, chunks, tokens, settings."""
        comm = HierarchicalCommunity(
            id="c_cache",
            level=0,
            index=0,
            entity_ids=["X", "Y"],
        )
        summarizer = CommunitySummarizer()

        base_key = summarizer._compute_cache_key(comm)
        # Baseline returns content_hash for disk compatibility
        assert base_key == comm.content_hash

        # Varied graph produces different key
        g1 = nx.Graph([("X", "Y")])
        key_g1 = summarizer._compute_cache_key(comm, graph=g1)
        assert key_g1 != base_key

        # Varied text chunks produces different key
        chunks = ["Evidence 1"]
        key_chunks = summarizer._compute_cache_key(comm, text_chunks=chunks)
        assert key_chunks != base_key

        # Varied max_tokens produces different key
        key_tokens = summarizer._compute_cache_key(comm, max_tokens=500)
        assert key_tokens != base_key

        # Varied prompt produces different key
        key_prompt = summarizer._compute_cache_key(
            comm, prompt="Custom prompt text"
        )
        assert key_prompt != base_key

        # Varied rank produces different key
        key_rank = summarizer._compute_cache_key(comm, rank=7.5)
        assert key_rank != base_key

        # End-to-end caching test: report with text_chunks is not returned
        # when text_chunks change
        call_count = 0

        def counting_llm(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            return json.dumps({
                "title": f"Report Call {call_count}",
                "summary": "Summary",
                "impact_rating": 5.0,
            })

        rep1 = summarizer.summarize_community(
            comm, text_chunks=["Chunk A"], llm=counting_llm
        )
        assert call_count == 1
        assert rep1.title == "Report Call 1"

        # Calling again with identical inputs hits memory cache
        rep1_cached = summarizer.summarize_community(
            comm, text_chunks=["Chunk A"], llm=counting_llm
        )
        assert call_count == 1
        assert rep1_cached.title == "Report Call 1"

        # Calling with different chunks bypasses cache and generates report
        rep2 = summarizer.summarize_community(
            comm, text_chunks=["Chunk B"], llm=counting_llm
        )
        assert call_count == 2
        assert rep2.title == "Report Call 2"

    def test_summarize_hierarchy_level_filtering_skips_unneeded_levels(self):
        """Issue 6: Level filter only computes target levels & descendants."""
        c_l0_a = HierarchicalCommunity(
            id="c_0a", level=0, index=0, entity_ids=["e1"]
        )
        c_l0_b = HierarchicalCommunity(
            id="c_0b", level=0, index=1, entity_ids=["e2"]
        )
        c_l1 = HierarchicalCommunity(
            id="c_1",
            level=1,
            index=0,
            entity_ids=["e1", "e2"],
            child_ids=["c_0a", "c_0b"],
        )
        c_l2 = HierarchicalCommunity(
            id="c_2",
            level=2,
            index=0,
            entity_ids=["e1", "e2"],
            child_ids=["c_1"],
        )

        hierarchy = CommunityHierarchy(
            communities=[c_l0_a, c_l0_b, c_l1, c_l2]
        )

        def recording_llm(prompt, **kwargs):
            return json.dumps({
                "title": "Community Report",
                "summary": "Summary",
                "impact_rating": 5.0,
            })

        summarizer = CommunitySummarizer()

        # Target level 0 only: level 1 and 2 must NOT be processed
        reports_l0 = summarizer.summarize_hierarchy(
            hierarchy,
            levels=[0],
            llm=recording_llm,
        )
        assert set(reports_l0.keys()) == {"c_0a", "c_0b"}

        # Target level 1 only: level 0 is needed as dependency, but level 2
        # is skipped
        reports_l1 = summarizer.summarize_hierarchy(
            hierarchy,
            levels=[1],
            llm=recording_llm,
        )
        assert "c_1" in reports_l1
        # Returned dictionary only contains requested target level [1]
        assert set(reports_l1.keys()) == {"c_1"}
        # And level 2 was never processed (not in hierarchy result)
        assert "c_2" not in reports_l1

    def test_tier1_failure_skips_tier2_provider_retry(self):
        """Issue 7: Wrapper generate_typed failure skips Tier 2 retry."""
        comm = HierarchicalCommunity(
            id="c_tier",
            level=0,
            index=0,
            entity_ids=["t1", "t2"],
        )
        summarizer = CommunitySummarizer()

        mock_provider = MagicMock()
        mock_provider.generate_typed = MagicMock(
            return_value={
                "title": "Provider Tier 2",
                "summary": "P",
                "impact_rating": 5.0,
            }
        )

        mock_llm = MagicMock()
        mock_llm.provider = mock_provider
        # Tier 1 fails
        mock_llm.generate_typed = MagicMock(
            side_effect=RuntimeError("Tier 1 API timeout")
        )
        # Tier 3 succeeds as fallback
        mock_llm.generate_structured = MagicMock(
            return_value={
                "title": "Structured Tier 3",
                "summary": "S",
                "impact_rating": 6.0,
            }
        )

        summarizer.llm = mock_llm
        schema = summarizer._call_llm(comm, "Prompt")

        # Tier 1 was attempted
        assert mock_llm.generate_typed.called
        # Tier 2 provider.generate_typed must have been SKIPPED
        assert not mock_provider.generate_typed.called
        # Tier 3 was executed
        assert mock_llm.generate_structured.called
        assert schema.title == "Structured Tier 3"

        # Case B: LLM has provider.generate_typed but NO generate_typed
        mock_raw_wrapper = MagicMock(spec=["provider"])
        mock_raw_wrapper.provider = MagicMock()
        mock_raw_wrapper.provider.generate_typed = MagicMock(
            return_value={
                "title": "Direct Provider",
                "summary": "DP",
                "impact_rating": 7.0,
            }
        )
        summarizer.llm = mock_raw_wrapper
        schema2 = summarizer._call_llm(comm, "Prompt")
        assert mock_raw_wrapper.provider.generate_typed.called
        assert schema2.title == "Direct Provider"

    def test_methods_api_forwards_text_chunks(self):
        """Top-level summarize methods forward text_chunks."""
        comm = HierarchicalCommunity(
            id="c_top", level=0, index=0, entity_ids=["e1"]
        )
        rep = summarize_community(
            comm,
            text_chunks=["Top-level source evidence chunk"],
        )
        assert rep is not None
        assert rep.community_id == "c_top"

        hierarchy = CommunityHierarchy(communities=[comm])
        reports = summarize_hierarchy(
            hierarchy,
            text_chunks=["Top-level hierarchy source chunk"],
        )
        assert "c_top" in reports

    def test_zero_negative_and_tiny_token_limits_fallback(self):
        """Issue 2 & 8: Zero/negative token limits return fallback."""
        comm = HierarchicalCommunity(
            id="c_tiny",
            level=0,
            index=0,
            entity_ids=["T1", "T2"],
        )
        mock_llm = MagicMock()

        # max_tokens = 0
        s_zero = CommunitySummarizer(llm=mock_llm, max_tokens=0)
        rep_zero = s_zero.summarize_community(comm)
        assert rep_zero is not None
        assert rep_zero.community_id == "c_tiny"
        assert not mock_llm.called

        # max_tokens = -5
        s_neg = CommunitySummarizer(llm=mock_llm, max_tokens=-5)
        rep_neg = s_neg.summarize_community(comm)
        assert rep_neg is not None
        assert rep_neg.community_id == "c_tiny"
        assert not mock_llm.called

        # Non-positive override max_tokens = 0
        s_tiny = CommunitySummarizer(llm=mock_llm)
        rep_tiny = s_tiny.summarize_community(comm, max_tokens=0)
        assert rep_tiny is not None
        assert rep_tiny.community_id == "c_tiny"
        assert not mock_llm.called

    def test_context_first_prompt_truncation_preserves_instructions(self):
        """Issue 2: Over-budget prompt trims context before template."""
        comm = HierarchicalCommunity(
            id="c_trunc",
            level=0,
            index=0,
            entity_ids=[f"E_{i}" for i in range(50)],
        )

        recorded_prompts = []

        def recording_llm(prompt, **kwargs):
            recorded_prompts.append(prompt)
            return json.dumps({
                "title": "Truncated Report",
                "summary": "Summary",
                "impact_rating": 6.0,
            })

        # Budget of 110 tokens: context is trimmed, but instructions remain
        summarizer = CommunitySummarizer(llm=recording_llm, max_tokens=110)
        rep = summarizer.summarize_community(comm)
        assert rep.title == "Truncated Report"
        assert len(recorded_prompts) == 1
        prompt = recorded_prompts[0]
        assert "Return ONLY the structured JSON report." in prompt
        assert estimate_tokens(prompt) <= 110

    def test_cache_key_preserves_content_hash_when_community_has_edges(self):
        """Issue 5: Internal comm.edges preserves comm.content_hash."""
        comm = HierarchicalCommunity(
            id="c_edges",
            level=0,
            index=0,
            entity_ids=["X1", "X2"],
            edges=[{"source": "X1", "target": "X2", "weight": 2.0}],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            summarizer = CommunitySummarizer(
                cache_dir=tmpdir, cache_enabled=True
            )
            rep = summarizer.summarize_community(comm)
            h = comm.content_hash

            # Cache file on disk is named exactly by content_hash
            cache_file = Path(tmpdir) / f"{h}.json"
            assert cache_file.exists()

            # Retrieval by content_hash succeeds
            cached = summarizer.get_cached_report(h)
            assert cached is not None
            assert cached.title == rep.title

    def test_entity_objects_and_name_resolution_in_pack_context(self):
        """Issue 1: Subgraph with entity objects and name resolution."""
        class EntityNode:
            def __init__(self, eid, name, desc, prov):
                self.id = eid
                self.name = name
                self.description = desc
                self.provenance = prov
                self.type = "Scientist"

        comm = HierarchicalCommunity(
            id="c_obj",
            level=0,
            index=0,
            entity_ids=["Marie Curie"],  # Name as identifier
        )
        graph = {
            "entities": [
                EntityNode(
                    "P001",
                    "Marie Curie",
                    "Pioneering radiation physicist",
                    "nobel_prize.pdf",
                )
            ],
            "relationships": [
                {
                    "from": "Marie Curie",
                    "to": "Sorbonne",
                    "type": "AFFILIATED_WITH",
                }
            ],
        }

        summarizer = CommunitySummarizer()
        context = summarizer._pack_context(
            comm,
            subgraph=graph,
            budget=2000,
        )

        assert "Marie Curie" in context
        assert "Scientist" in context
        assert "Pioneering radiation physicist" in context
        assert "nobel_prize.pdf" in context

    def test_bridge_edges_prioritized_over_internal_edges(self):
        """Issue 1 & 3: Bridge edges across communities prioritized."""
        c_parent = HierarchicalCommunity(
            id="c_par",
            level=1,
            index=0,
            entity_ids=["A1", "A2", "B1", "B2"],
            child_ids=["c_ch1", "c_ch2"],
        )

        cr1 = CommunityReport(
            community_id="c_ch1",
            level=0,
            title="Child 1",
            summary="Sub 1",
            findings=[],
            impact_rating=5.0,
            rating_explanation="",
            member_entities=["A1", "A2"],
            content_hash="h1",
        )
        cr2 = CommunityReport(
            community_id="c_ch2",
            level=0,
            title="Child 2",
            summary="Sub 2",
            findings=[],
            impact_rating=5.0,
            rating_explanation="",
            member_entities=["B1", "B2"],
            content_hash="h2",
        )

        # Internal edge (A1 -> A2) and Bridge edge (A1 -> B1)
        subgraph = {
            "edges": [
                {"from": "A1", "to": "A2", "type": "INTERNAL_LINK"},
                {"from": "A1", "to": "B1", "type": "BRIDGE_LINK"},
            ]
        }

        summarizer = CommunitySummarizer()
        bridge_edges = summarizer._identify_bridge_edges(
            c_parent, child_reports=[cr1, cr2], subgraph=subgraph
        )
        assert len(bridge_edges) == 2
        # Bridge link must be prioritized first
        assert bridge_edges[0]["type"] == "BRIDGE_LINK"
        assert bridge_edges[0].get("_is_bridge") is True

        # Pack context with small edge budget: BRIDGE_LINK should be included
        context = summarizer._pack_context(
            c_parent,
            subgraph=subgraph,
            child_reports=[cr1, cr2],
            budget=200,
        )
        assert "BRIDGE_LINK" in context

    def test_summarize_hierarchy_bfs_skips_unrelated_communities(self):
        """Issue 6: Multi-branch hierarchy only computes target branch."""
        # Branch A:
        c0_a1 = HierarchicalCommunity(
            id="a1", level=0, index=0, entity_ids=["x1"]
        )
        c0_a2 = HierarchicalCommunity(
            id="a2", level=0, index=1, entity_ids=["x2"]
        )
        c1_a = HierarchicalCommunity(
            id="c1_a",
            level=1,
            index=0,
            entity_ids=["x1", "x2"],
            child_ids=["a1", "a2"],
        )
        c2_top = HierarchicalCommunity(
            id="top",
            level=2,
            index=0,
            entity_ids=["x1", "x2"],
            child_ids=["c1_a"],
        )

        # Branch B (unrelated to c2_top):
        c0_b1 = HierarchicalCommunity(
            id="b1", level=0, index=2, entity_ids=["y1"]
        )
        c1_b = HierarchicalCommunity(
            id="c1_b",
            level=1,
            index=1,
            entity_ids=["y1"],
            child_ids=["b1"],
        )

        hierarchy = CommunityHierarchy(
            communities=[c0_a1, c0_a2, c1_a, c2_top, c0_b1, c1_b]
        )

        processed_ids = []

        def recording_llm(prompt, **kwargs):
            return json.dumps({
                "title": "Report",
                "summary": "Summary",
                "impact_rating": 5.0,
            })

        summarizer = CommunitySummarizer()
        # Mock summarize_community to record which communities are processed
        orig_summarize = summarizer.summarize_community

        def tracking_summarize(community, **kwargs):
            processed_ids.append(str(community.id))
            return orig_summarize(community, llm=recording_llm, **kwargs)

        summarizer.summarize_community = tracking_summarize

        reports = summarizer.summarize_hierarchy(hierarchy, levels=[2])

        # Only c2_top returned in output
        assert set(reports.keys()) == {"top"}
        # And Branch B communities were NEVER processed
        assert "b1" not in processed_ids
        assert "c1_b" not in processed_ids
        # Branch A dependencies WERE processed
        assert "a1" in processed_ids
        assert "a2" in processed_ids
        assert "c1_a" in processed_ids
        assert "top" in processed_ids
