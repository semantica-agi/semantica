"""
Unit and integration tests for GlobalGraphRetriever and Map-Reduce retrieval (PR #3).
"""

from unittest.mock import MagicMock

import pytest

from semantica.context.context_retriever import RetrievedContext
from semantica.context.global_retriever import (
    GlobalGraphRetriever,
    GlobalSearchResult,
    MapKeyPoint,
    MapPointSchema,
    MapResponseSchema,
    _cosine_similarity,
    _extract_words,
)
from semantica.kg.community_summarizer import CommunityReport


class TestMapKeyPoint:
    """Tests for MapKeyPoint dataclass and serialization."""

    def test_init_defaults_and_clamping(self):
        kp = MapKeyPoint(
            point="Quantum computing advances",
            description="Qubits scaling faster than predicted",
            relevance_score=15.0,  # exceeds 10.0
            community_id="c_1",
            level=1,
            entities=["IBM", "Google", "IBM"],  # duplicates
        )
        assert kp.point == "Quantum computing advances"
        assert kp.relevance_score == 10.0
        assert kp.entities == ["Google", "IBM"]
        assert kp.community_id == "c_1"
        assert kp.level == 1

        # Test lower clamp
        kp_low = MapKeyPoint(point="Low", relevance_score=-5.0)
        assert kp_low.relevance_score == 0.0

        # Test NaN / invalid clamp
        kp_nan = MapKeyPoint(point="NaN", relevance_score=float("nan"))
        assert kp_nan.relevance_score == 5.0

    def test_to_dict_and_from_dict(self):
        kp = MapKeyPoint(
            point="Graph algorithms",
            description="Leiden clustering",
            relevance_score=8.5,
            community_id="c_42",
            level=2,
            entities=["Graph", "Node"],
            metadata={"source": "test"},
        )
        d = kp.to_dict()
        assert d["point"] == "Graph algorithms"
        assert d["relevance_score"] == 8.5
        assert d["entities"] == ["Graph", "Node"]

        reconstructed = MapKeyPoint.from_dict(d)
        assert reconstructed.point == kp.point
        assert reconstructed.relevance_score == kp.relevance_score
        assert reconstructed.entities == kp.entities
        assert reconstructed.metadata == kp.metadata


class TestMapResponseSchema:
    """Tests for MapResponseSchema Pydantic validation and coercion."""

    def test_valid_points(self):
        schema = MapResponseSchema(
            points=[
                MapPointSchema(
                    point="AI scaling laws",
                    description="Compute dictates capability",
                    relevance_score=9.0,
                    entities=["GPU", "Compute"],
                )
            ],
            relevance_explanation="Directly answers query",
        )
        assert len(schema.points) == 1
        assert schema.points[0].point == "AI scaling laws"
        assert schema.points[0].relevance_score == 9.0

    def test_normalize_dict_and_string_points(self):
        raw = {
            "points": [
                {
                    "finding": "Dict-based finding",
                    "explanation": "Derived from summary",
                    "score": 7.5,
                    "member_entities": ["E1", "E2"],
                },
                "Simple string point",
            ],
            "relevance_explanation": "Normalized successfully",
        }
        schema = MapResponseSchema.model_validate(raw)
        assert len(schema.points) == 2
        assert schema.points[0].point == "Dict-based finding"
        assert schema.points[0].description == "Derived from summary"
        assert schema.points[0].relevance_score == 7.5
        assert schema.points[0].entities == ["E1", "E2"]
        assert schema.points[1].point == "Simple string point"
        assert schema.points[1].relevance_score == 5.0


class TestGlobalSearchResult:
    """Tests for GlobalSearchResult dataclass and conversion to RetrievedContext."""

    def test_to_retrieved_contexts(self):
        result = GlobalSearchResult(
            query="What are the key tech trends?",
            response="Executive overview: [Community c_1] focuses on AI.",
            level=1,
            key_points=[
                MapKeyPoint(
                    point="Neural networks",
                    description="Transformer architecture dominates",
                    relevance_score=9.0,
                    community_id="c_1",
                    level=1,
                    entities=["Transformers", "Attention"],
                )
            ],
            community_reports_used=["c_1"],
            citations=["c_1"],
            metrics={"time_taken": 0.5},
        )

        contexts = result.to_retrieved_contexts()
        assert len(contexts) == 2

        # Primary executive answer context
        primary = contexts[0]
        assert isinstance(primary, RetrievedContext)
        assert primary.score == 1.0
        assert primary.source == "global_search"
        assert primary.content == result.response
        assert primary.metadata["query"] == result.query
        assert primary.metadata["level"] == 1

        # Key point context
        kp_ctx = contexts[1]
        assert isinstance(kp_ctx, RetrievedContext)
        assert kp_ctx.score == 0.9  # 9.0 / 10.0
        assert kp_ctx.source == "community_c_1"
        assert "Neural networks" in kp_ctx.content
        assert len(kp_ctx.related_entities) == 2
        assert kp_ctx.related_entities[0]["id"] == "Attention"

    def test_to_dict_and_from_dict(self):
        result = GlobalSearchResult(
            query="test",
            response="ans",
            level=0,
            key_points=[MapKeyPoint(point="pt", relevance_score=8.0)],
            community_reports_used=["c0"],
            citations=["c0"],
            metrics={"m": 1},
        )
        d = result.to_dict()
        reconstructed = GlobalSearchResult.from_dict(d)
        assert reconstructed.query == "test"
        assert reconstructed.response == "ans"
        assert len(reconstructed.key_points) == 1
        assert reconstructed.key_points[0].point == "pt"


class TestGlobalGraphRetrieverLevelSelection:
    """Tests for dynamic level selection and token budgeting."""

    def _create_sample_reports(self):
        # Level 0 reports: 4 reports of ~100 tokens each
        l0_reports = [
            CommunityReport(
                community_id=f"c_0_{i}",
                level=0,
                title=f"Sub-cluster {i} of Machine Learning",
                summary=(
                    "Detailed exploration of specific algorithms, gradient descent, "
                    "backpropagation, and loss functions in artificial intelligence."
                ),
                findings=[
                    {"summary": f"Finding {i}", "explanation": "Detailed analysis"}
                ],
                impact_rating=6.0 + i,
                rank=0.5,
                member_entities=[f"Entity_{i}_A", f"Entity_{i}_B"],
            )
            for i in range(4)
        ]

        # Level 1 reports: 1 coarser report
        l1_report = CommunityReport(
            community_id="c_1_0",
            level=1,
            title="Macro Machine Learning Community",
            summary="Executive synthesis covering all machine learning sub-clusters.",
            findings=[{"summary": "Macro Overview", "explanation": "Unified ML"}],
            impact_rating=8.5,
            rank=0.9,
            member_entities=["MachineLearning", "NeuralNetworks"],
        )

        return l0_reports + [l1_report]

    def test_auto_promote_level_when_budget_exceeded(self):
        reports = self._create_sample_reports()
        # Set max_context_tokens small enough so L0 reports exceed it,
        # but L1 report fits.
        retriever = GlobalGraphRetriever(
            reports=reports,
            max_context_tokens=150,  # L0 total is ~250 tokens; L1 is ~70 tokens
            auto_promote_level=True,
        )

        selected_level, selected_reports = retriever.select_level_and_budget(
            query="machine learning"
        )
        assert selected_level == 1
        assert len(selected_reports) == 1
        assert selected_reports[0].community_id == "c_1_0"

    def test_stay_at_level_when_within_budget(self):
        reports = self._create_sample_reports()
        retriever = GlobalGraphRetriever(
            reports=reports,
            max_context_tokens=5000,
            auto_promote_level=True,
        )

        selected_level, selected_reports = retriever.select_level_and_budget(
            query="machine learning", target_level=0
        )
        assert selected_level == 0
        assert len(selected_reports) == 4

    def test_pruning_fallback_when_auto_promote_disabled(self):
        reports = self._create_sample_reports()
        # With auto_promote_level=False, must prune L0 reports to fit budget
        retriever = GlobalGraphRetriever(
            reports=reports,
            max_context_tokens=120,
            auto_promote_level=False,
        )

        selected_level, selected_reports = retriever.select_level_and_budget(
            query="machine learning"
        )
        assert selected_level == 0
        # Should prune from 4 down to fitting number
        assert len(selected_reports) < 4
        assert len(selected_reports) >= 1

    def test_embedding_cosine_pruning(self):
        rep_a = CommunityReport(
            community_id="c_emb_a",
            level=0,
            title="Quantum Physics",
            summary="Study of particles and waves.",
            embedding=[1.0, 0.0, 0.0],
        )
        rep_b = CommunityReport(
            community_id="c_emb_b",
            level=0,
            title="Finance and Banking",
            summary="Investment banking and markets.",
            embedding=[0.0, 1.0, 0.0],
        )

        retriever = GlobalGraphRetriever(
            reports=[rep_a, rep_b],
            max_context_tokens=15,  # each report is ~12 tokens, so 15 allows only 1
            auto_promote_level=False,
        )

        # Query aligned with rep_a
        level, selected = retriever.select_level_and_budget(
            query="quantum entanglement",
            query_embedding=[0.9, 0.1, 0.0],
        )
        assert level == 0
        assert len(selected) == 1
        assert selected[0].community_id == "c_emb_a"


class TestGlobalGraphRetrieverMapReduce:
    """Tests for parallel Map execution, 6-tier LLM unwrap, and Reduce synthesis."""

    def test_parallel_map_with_error_isolation(self):
        rep_good = CommunityReport(
            community_id="c_good",
            level=0,
            title="Success Community",
            summary="Everything functions as expected.",
            member_entities=["Alice", "Bob"],
        )
        rep_fail = CommunityReport(
            community_id="c_fail",
            level=0,
            title="Failing Community",
            summary="Triggers worker exception.",
            member_entities=["ErrorNode"],
        )

        # Mock LLM that raises on rep_fail prompt
        mock_llm = MagicMock()

        def llm_side_effect(prompt, **kwargs):
            if "c_fail" in prompt:
                raise RuntimeError("Simulated worker error in LLM")
            return MapResponseSchema(
                points=[
                    MapPointSchema(
                        point="Good Point",
                        description="From good community",
                        relevance_score=8.0,
                    )
                ],
                relevance_explanation="Worked",
            )

        mock_llm.generate_typed.side_effect = llm_side_effect

        retriever = GlobalGraphRetriever(
            reports=[rep_good, rep_fail],
            llm=mock_llm,
            max_workers=2,
        )

        result = retriever.search(query="test query")
        assert result is not None
        # Both communities should produce points (c_fail via extractive fallback)
        comm_ids = {kp.community_id for kp in result.key_points}
        assert "c_good" in comm_ids
        assert "c_fail" in comm_ids
        assert result.metrics["reports_evaluated"] == 2

    def test_llm_tier_1_generate_typed(self):
        rep = CommunityReport(
            community_id="c_tier1",
            level=0,
            title="Tier 1 Report",
            summary="Tier 1 evaluation",
        )
        mock_llm = MagicMock()
        mock_llm.generate_typed.return_value = MapResponseSchema(
            points=[
                MapPointSchema(
                    point="Tier 1 Point",
                    description="Success",
                    relevance_score=9.5,
                )
            ]
        )

        retriever = GlobalGraphRetriever(reports=[rep], llm=mock_llm)
        points = retriever._map_report(rep, "query")
        assert len(points) == 1
        assert points[0].point == "Tier 1 Point"
        assert points[0].relevance_score == 9.5
        mock_llm.generate_typed.assert_called_once()

    def test_llm_tier_2_provider_generate_typed(self):
        rep = CommunityReport(
            community_id="c_tier2",
            level=0,
            title="Tier 2 Report",
            summary="Tier 2 evaluation",
        )
        mock_provider = MagicMock()
        mock_provider.generate_typed.return_value = {
            "points": [{"point": "Tier 2 Point", "relevance_score": 8.0}]
        }

        mock_llm = MagicMock(spec=["provider"])
        mock_llm.provider = mock_provider

        retriever = GlobalGraphRetriever(reports=[rep], llm=mock_llm)
        points = retriever._map_report(rep, "query")
        assert len(points) == 1
        assert points[0].point == "Tier 2 Point"
        assert points[0].relevance_score == 8.0

    def test_llm_tier_3_generate_structured(self):
        rep = CommunityReport(
            community_id="c_tier3",
            level=0,
            title="Tier 3 Report",
            summary="Tier 3 evaluation",
        )
        mock_llm = MagicMock(spec=["generate_structured"])
        mock_llm.generate_structured.return_value = {
            "points": [{"point": "Tier 3 Structured", "relevance_score": 7.0}]
        }

        retriever = GlobalGraphRetriever(reports=[rep], llm=mock_llm)
        points = retriever._map_report(rep, "query")
        assert len(points) == 1
        assert points[0].point == "Tier 3 Structured"

    def test_llm_tier_4_generate_with_json(self):
        rep = CommunityReport(
            community_id="c_tier4",
            level=0,
            title="Tier 4 Report",
            summary="Tier 4 evaluation",
        )
        mock_llm = MagicMock(spec=["generate"])
        mock_llm.generate.return_value = (
            "```json\n"
            '{"points": [{"point": "Tier 4 JSON", "relevance_score": 8.2}]}\n'
            "```"
        )

        retriever = GlobalGraphRetriever(reports=[rep], llm=mock_llm)
        points = retriever._map_report(rep, "query")
        assert len(points) == 1
        assert points[0].point == "Tier 4 JSON"
        assert points[0].relevance_score == 8.2

    def test_llm_tier_5_callable(self):
        rep = CommunityReport(
            community_id="c_tier5",
            level=0,
            title="Tier 5 Report",
            summary="Tier 5 evaluation",
        )

        def mock_callable(prompt, **kwargs):
            return '{"points": [{"point": "Tier 5 Callable", "relevance_score": 7.5}]}'

        retriever = GlobalGraphRetriever(reports=[rep], llm=mock_callable)
        points = retriever._map_report(rep, "query")
        assert len(points) == 1
        assert points[0].point == "Tier 5 Callable"

    def test_llm_tier_6_extractive_fallback(self):
        rep = CommunityReport(
            community_id="c_extractive",
            level=0,
            title="Deep Learning Breakthroughs",
            summary="Transformers revolutionized natural language processing.",
            findings=[
                {
                    "summary": "Attention Mechanisms",
                    "explanation": "Self-attention enables massive context.",
                }
            ],
            member_entities=["BERT", "GPT"],
        )

        retriever = GlobalGraphRetriever(reports=[rep], llm=None)
        points = retriever._map_report(rep, "attention transformers")
        assert len(points) >= 1
        pt_texts = [p.point for p in points]
        assert any("Deep Learning" in pt or "Attention" in pt for pt in pt_texts)

    def test_min_relevance_score_filtering(self):
        rep = CommunityReport(
            community_id="c_filter",
            level=0,
            title="Filtered Report",
            summary="Report testing cutoff",
        )

        mock_llm = MagicMock(spec=["generate_typed"])
        mock_llm.generate_typed.return_value = MapResponseSchema(
            points=[
                MapPointSchema(point="High Relevance", relevance_score=9.0),
                MapPointSchema(point="Low Relevance", relevance_score=2.0),
            ]
        )

        retriever = GlobalGraphRetriever(
            reports=[rep],
            llm=mock_llm,
            min_relevance_score=5.0,
        )

        result = retriever.search(query="test")
        retained = [kp.point for kp in result.key_points]
        assert "High Relevance" in retained
        assert "Low Relevance" not in retained

    def test_executive_synthesis_citations_extraction(self):
        rep = CommunityReport(
            community_id="c_cit",
            level=0,
            title="Citation Source",
            summary="Data for citation",
        )

        mock_llm = MagicMock()
        mock_llm.generate_typed.return_value = MapResponseSchema(
            points=[MapPointSchema(point="Key Finding", relevance_score=8.5)]
        )
        mock_llm.generate.return_value = (
            "According to [Community c_cit], the key finding is verified."
        )

        retriever = GlobalGraphRetriever(reports=[rep], llm=mock_llm)
        result = retriever.search(query="test")
        assert "c_cit" in result.citations
        assert "[Community c_cit]" in result.response

    def test_empty_reports_returns_graceful_result(self):
        retriever = GlobalGraphRetriever(reports=[])
        result = retriever.search(query="empty search")
        assert result.key_points == []
        assert "No community reports" in result.response
        assert result.metrics["reports_evaluated"] == 0
        # Verify to_retrieved_contexts returns empty list to prevent RAG pollution
        assert result.to_retrieved_contexts() == []

    def test_extract_json_multi_item_array_and_markdown(self):
        retriever = GlobalGraphRetriever()
        raw_json_arr = (
            "[\n"
            '  {"point": "Pt A", "description": "D1", "relevance_score": 9.0},\n'
            '  {"point": "Pt B", "description": "D2", "relevance_score": 8.0},\n'
            '  {"point": "Pt C", "description": "D3", "relevance_score": 7.0}\n'
            "]"
        )
        parsed = retriever._extract_json(raw_json_arr)
        assert isinstance(parsed, list)
        assert len(parsed) == 3

        # Test within markdown codeblock
        markdown_text = (
            f"Findings:\n```json\n{raw_json_arr}\n```\nDone."
        )
        parsed_md = retriever._extract_json(markdown_text)
        assert isinstance(parsed_md, list)
        assert len(parsed_md) == 3

        # Test coercion maintains all 3 points
        rep = CommunityReport(community_id="c_arr", level=0, title="T", summary="S")
        schema = retriever._coerce_map_response(parsed, rep)
        assert schema is not None
        assert len(schema.points) == 3
        pts = [p.point for p in schema.points]
        assert pts == ["Pt A", "Pt B", "Pt C"]

    def test_parallel_map_timeout_falls_back_without_failing_batch(self):
        import time

        rep1 = CommunityReport(
            community_id="c_fast",
            level=0,
            title="Fast Community",
            summary="Fast summary",
            findings=[{"summary": "Fast finding"}],
        )
        rep2 = CommunityReport(
            community_id="c_slow",
            level=0,
            title="Slow Community",
            summary="Slow summary",
            findings=[{"summary": "Slow finding"}],
        )

        def mock_llm_with_delay(prompt, **kwargs):
            if "Slow Community" in prompt:
                time.sleep(0.3)
            return (
                '{"points": [{"point": "Finding", "relevance_score": 8.0}]}'
            )

        # Set a short timeout (0.05s) so the slow report times out
        retriever = GlobalGraphRetriever(
            reports=[rep1, rep2],
            llm=mock_llm_with_delay,
            timeout=0.05,
            max_workers=2,
        )

        # Must NOT raise TimeoutError; must return points for both
        points = retriever._execute_parallel_map([rep1, rep2], query="test")
        comm_ids = {p.community_id for p in points}
        assert "c_fast" in comm_ids or "c_slow" in comm_ids
        assert len(points) >= 1

    def test_helper_utilities(self):
        # Cosine similarity
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
        assert _cosine_similarity([], [1.0]) == 0.0

        # Word extraction
        words = _extract_words("Hello, World! 123_test")
        assert "hello" in words
        assert "world" in words
