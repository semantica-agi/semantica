"""
Tests for the Decision Evaluation Hook

This module tests the opt-in evaluators/eval_config wiring between
semantica.evals and DecisionRecorder / AgentContext.
"""

import logging
from datetime import datetime
from unittest.mock import Mock

import pytest

from semantica.context.agent_context import AgentContext
from semantica.context.decision_models import Decision
from semantica.context.decision_recorder import DecisionRecorder
from semantica.evals.types import CaseResult, EvalMetric, EvalSummary


def _decision(**overrides):
    """Build a Decision that passes every decision_scores check by default."""
    base = dict(
        decision_id="eval-hook-d1",
        category="loan",
        scenario="mortgage application",
        reasoning="strong credit history",
        outcome="approved",
        confidence=0.95,
        timestamp=datetime(2026, 1, 1),
        decision_maker="loan_officer",
        metadata={"provenance": {"prov_record": "rid-1"}},
    )
    base.update(overrides)
    return Decision(**base)


class TestDecisionRecorderEvalHook:
    """Test the opt-in evaluation hook on DecisionRecorder.record_decision()."""

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store for testing."""
        mock_store = Mock()
        mock_store.execute_query = Mock()
        return mock_store

    def test_no_evaluators_configured_is_unchanged(self, mock_graph_store):
        """Backward compat: omitting evaluators= adds no eval_* metadata."""
        recorder = DecisionRecorder(graph_store=mock_graph_store)
        decision = _decision()

        decision_id = recorder.record_decision(decision, [], [])

        assert decision_id == decision.decision_id
        assert "eval_score" not in decision.metadata
        assert "eval_passed" not in decision.metadata
        assert "eval_details" not in decision.metadata

    def test_full_pass_enriches_metadata(self, mock_graph_store):
        """All decision_scores checks pass -> eval_score 1.0, eval_passed True."""
        recorder = DecisionRecorder(
            graph_store=mock_graph_store,
            evaluators=["decision_scores"],
            eval_config={"decision_scores": {"expected_outcome": "approved"}},
        )
        decision = _decision()

        recorder.record_decision(decision, [], [])

        assert decision.metadata["eval_score"] == 1.0
        assert decision.metadata["eval_passed"] is True
        assert list(decision.metadata["eval_details"].keys()) == ["decision_scores"]

    def test_failing_check_surfaces_in_metadata(self, mock_graph_store):
        """Empty reasoning fails a field check -> eval_passed False, named in details."""
        recorder = DecisionRecorder(
            graph_store=mock_graph_store,
            evaluators=["decision_scores"],
        )
        decision = _decision(reasoning="")

        recorder.record_decision(decision, [], [])

        assert decision.metadata["eval_passed"] is False
        assert decision.metadata["eval_score"] < 1.0
        assert (
            decision.metadata["eval_details"]["decision_scores"]["meta"]["reasoning"]
            is False
        )

    def test_none_metadata_does_not_crash_recording(self, mock_graph_store):
        """Decision(metadata=None) -> hook normalizes it instead of crashing."""
        recorder = DecisionRecorder(
            graph_store=mock_graph_store,
            evaluators=["decision_scores"],
        )
        decision = _decision(metadata=None)

        decision_id = recorder.record_decision(decision, [], [])

        assert decision_id == decision.decision_id
        assert decision.metadata["eval_passed"] is False  # provenance check fails
        assert mock_graph_store.execute_query.called

    def test_policy_mismatch_surfaces_in_metadata(self, mock_graph_store):
        """PolicyEngine.check_compliance() False -> failing 'policy' check surfaced."""

        class FakePolicyEngine:
            def check_compliance(self, decision, policy_id):
                return False

        recorder = DecisionRecorder(
            graph_store=mock_graph_store,
            evaluators=["decision_scores"],
            eval_config={
                "decision_scores": {
                    "policy_engine": FakePolicyEngine(),
                    "policy_id": "p1",
                }
            },
        )
        decision = _decision()

        recorder.record_decision(decision, [], [])

        assert decision.metadata["eval_passed"] is False
        assert (
            decision.metadata["eval_details"]["decision_scores"]["meta"]["policy"]
            is False
        )

    def test_evaluator_failure_does_not_block_recording(
        self, mock_graph_store, monkeypatch, caplog
    ):
        """evaluate() itself raising -> decision still recorded, no eval_* keys."""
        monkeypatch.setattr(
            "semantica.evals.evaluate",
            Mock(side_effect=RuntimeError("boom")),
        )
        recorder = DecisionRecorder(
            graph_store=mock_graph_store,
            evaluators=["decision_scores"],
        )
        decision = _decision()

        with caplog.at_level(logging.WARNING):
            decision_id = recorder.record_decision(decision, [], [])

        assert decision_id == decision.decision_id
        assert "eval_score" not in decision.metadata
        assert "eval_passed" not in decision.metadata
        assert mock_graph_store.execute_query.called
        # The traceback must survive the log call, not just the message string.
        record = next(r for r in caplog.records if "Decision evaluation failed" in r.message)
        assert record.exc_info is not None

    def test_evaluator_error_status_is_logged(
        self, mock_graph_store, monkeypatch, caplog
    ):
        """A named evaluator erroring (unknown name, internal raise) -> logged,
        not just buried in eval_details on the stored decision."""
        error_summary = EvalSummary(
            total=1,
            passed=0,
            failed=0,
            errors=1,
            pass_rate=0.0,
            cases=[
                CaseResult(
                    case_id="eval-hook-d1",
                    status="error",
                    metrics={"decision_scores": EvalMetric(0.0, False, {"error": "boom"})},
                    details={"decision_scores": {"error": "boom"}},
                )
            ],
        )
        monkeypatch.setattr(
            "semantica.evals.evaluate", Mock(return_value=error_summary)
        )
        recorder = DecisionRecorder(
            graph_store=mock_graph_store,
            evaluators=["decision_scores"],
        )
        decision = _decision()

        with caplog.at_level(logging.WARNING):
            recorder.record_decision(decision, [], [])

        assert decision.metadata["eval_passed"] is False
        assert any(
            "evaluator(s) errored" in r.message for r in caplog.records
        )


class TestAgentContextEvalHookWiring:
    """Test that AgentContext threads evaluators/eval_config into DecisionRecorder."""

    @pytest.fixture(autouse=True)
    def _stub_node_embedder(self, monkeypatch):
        """AgentContext(vector_store=..., knowledge_graph=...) constructs a real
        ContextRetriever, which eagerly builds a DecisionEmbeddingPipeline and a
        DecisionQuery, both of which construct NodeEmbedder(method="node2vec").
        NodeEmbedder raises ImportError when the optional `gensim` dependency
        (semantica[graph-embeddings]) isn't installed. These tests only check
        that evaluators/eval_config land on the DecisionRecorder, so stub
        NodeEmbedder out at both import sites rather than requiring gensim.
        """
        monkeypatch.setattr(
            "semantica.vector_store.decision_embedding_pipeline.NodeEmbedder", Mock()
        )
        monkeypatch.setattr("semantica.context.decision_query.NodeEmbedder", Mock())

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing."""
        mock_store = Mock()
        mock_store.add = Mock()
        mock_store.search = Mock(return_value=[])
        return mock_store

    @pytest.fixture
    def mock_knowledge_graph(self):
        """Mock knowledge graph for testing."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])
        return mock_graph

    def test_evaluators_threaded_into_decision_recorder(
        self, mock_vector_store, mock_knowledge_graph
    ):
        """Constructor-level evaluators/eval_config land on the recorder."""
        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            decision_tracking=True,
            evaluators=["decision_scores"],
            eval_config={"decision_scores": {"expected_outcome": "approved"}},
        )

        assert context._decision_recorder.evaluators == ["decision_scores"]
        assert context._decision_recorder.eval_config == {
            "decision_scores": {"expected_outcome": "approved"}
        }

    def test_evaluators_threaded_on_exception_fallback_path(
        self, mock_vector_store, mock_knowledge_graph, monkeypatch
    ):
        """Same wiring survives the DecisionQuery/-Analyzer init failure fallback."""
        # The success path constructs DecisionQuery once; on failure the
        # except block constructs it again as part of the fallback. Only
        # the first call should fail, so the fallback branch itself succeeds.
        monkeypatch.setattr(
            "semantica.context.agent_context.DecisionQuery",
            Mock(side_effect=[RuntimeError("boom"), Mock()]),
        )

        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            decision_tracking=True,
            evaluators=["decision_scores"],
            eval_config={"x": 1},
        )

        assert context._decision_recorder.evaluators == ["decision_scores"]
        assert context._decision_recorder.eval_config == {"x": 1}

    def test_no_evaluators_default_is_none(
        self, mock_vector_store, mock_knowledge_graph
    ):
        """Backward compat at the AgentContext layer: default is untouched."""
        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            decision_tracking=True,
        )

        assert context._decision_recorder.evaluators is None
        assert context._decision_recorder.eval_config == {}
