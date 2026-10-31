"""
Reproduction and regression tests for evaluator execution on ContextGraph decision recording.
"""

from datetime import datetime
from unittest.mock import Mock
import pytest

from semantica.context.agent_context import AgentContext
from semantica.context.context_graph import ContextGraph
from semantica.context.decision_models import Decision
from semantica.context.decision_recorder import DecisionRecorder


class TestContextGraphDecisionEvaluatorsRepro:
    @pytest.fixture
    def mock_vector_store(self):
        store = Mock()
        store.add = Mock()
        store.search = Mock(return_value=[])
        return store

    def test_record_decision_with_evaluators_attaches_metadata(self, mock_vector_store):
        """ContextGraph decision recording must run evaluators and attach eval metadata."""
        graph = ContextGraph()
        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
            evaluators=["decision_scores"],
            eval_config={
                "decision_scores": {
                    "expected_outcome": "approved",
                    "min_confidence": 0.8,
                }
            },
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history and low debt",
            outcome="approved",
            confidence=0.9,
            decision_maker="ai_agent_001",
            cross_system_context={"salesforce": {"tier": "gold"}},
            metadata={"provenance": {"source": "unit_test", "decision_maker": "ai_agent_001"}},
        )

        assert decision_id is not None
        assert decision_id in graph.nodes
        node = graph.nodes[decision_id]

        assert "eval_score" in node.properties, f"eval_score missing from node properties: {node.properties}"
        assert node.properties["eval_score"] == 1.0
        assert "eval_passed" in node.properties, f"eval_passed missing from node properties: {node.properties}"
        assert node.properties["eval_passed"] is True
        assert "eval_details" in node.properties, f"eval_details missing from node properties: {node.properties}"
        assert "cross_system_context" in node.properties
        assert node.properties["provenance"] == {"source": "unit_test", "decision_maker": "ai_agent_001"}

    def test_decision_scores_without_provenance_fails(self, mock_vector_store):
        """Evaluators check real provenance only; without it, decision_scores fails provenance check."""
        graph = ContextGraph()
        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
            evaluators=["decision_scores"],
            eval_config={
                "decision_scores": {
                    "expected_outcome": "approved",
                    "min_confidence": 0.8,
                }
            },
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history and low debt",
            outcome="approved",
            confidence=0.9,
            decision_maker="ai_agent_001",
        )

        assert decision_id in graph.nodes
        node = graph.nodes[decision_id]
        assert node.properties["eval_passed"] is False
        assert "provenance" not in node.properties
        eval_details = node.properties["eval_details"]
        assert eval_details["decision_scores"]["provenance"] is False
        assert "provenance" in eval_details["decision_scores"]["reasons"]

    def test_record_decision_partial_eval_metadata_triggers_full_eval(self, mock_vector_store):
        """Partial eval metadata does not bypass evaluation; missing fields are computed and merged."""
        graph = ContextGraph()
        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
            evaluators=["decision_scores"],
            eval_config={
                "decision_scores": {
                    "expected_outcome": "approved",
                    "min_confidence": 0.8,
                }
            },
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history and low debt",
            outcome="approved",
            confidence=0.9,
            decision_maker="ai_agent_001",
            metadata={"eval_score": 0.1, "provenance": {"source": "unit_test"}},
        )

        assert decision_id in graph.nodes
        node = graph.nodes[decision_id]
        # Should have executed evaluators and overwritten eval_score with full evaluation results
        assert node.properties["eval_score"] == 1.0
        assert node.properties["eval_passed"] is True
        assert "eval_details" in node.properties

    def test_evaluator_with_required_expected_arg(self, mock_vector_store):
        """Registered evaluators requiring an expected parameter receive it from config."""
        graph = ContextGraph()
        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
            evaluators=["exact_match"],
            eval_config={
                "exact_match": {
                    "expected": "approved",
                }
            },
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history and low debt",
            outcome="approved",
            confidence=0.9,
            decision_maker="ai_agent_001",
        )

        assert decision_id in graph.nodes
        node = graph.nodes[decision_id]
        assert node.properties["eval_passed"] is True
        assert node.properties["eval_score"] == 1.0

    def test_direct_decision_recorder_with_provenance_manager(self):
        """Direct DecisionRecorder call attaches provenance record before running evaluators."""
        mock_graph_store = Mock()
        mock_graph_store.execute_query = Mock()

        mock_prov_manager = Mock()
        mock_prov_manager.track_entity = Mock(return_value={"entity_id": "dec_1"})
        mock_prov_manager.track_activity = Mock(return_value={"activity_id": "act_1"})

        recorder = DecisionRecorder(
            graph_store=mock_graph_store,
            provenance_manager=mock_prov_manager,
            evaluators=["decision_scores"],
            eval_config={
                "decision_scores": {
                    "expected_outcome": "approved",
                    "min_confidence": 0.8,
                }
            },
        )

        decision = Decision(
            decision_id="decision_uuid_100",
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history and low debt",
            outcome="approved",
            confidence=0.9,
            timestamp=datetime.now(),
            decision_maker="ai_agent_001",
        )

        dec_id = recorder.record_decision(
            decision,
            entities=["customer_1"],
            source_documents=["doc_1"],
        )

        assert dec_id == "decision_uuid_100"
        assert "provenance" in decision.metadata
        assert decision.metadata["provenance"]["entity_id"] == "decision_uuid_100"
        assert decision.metadata["eval_passed"] is True
        assert decision.metadata["eval_score"] == 1.0

    def test_context_graph_reused_metadata_dict_not_mutated(self):
        """ContextGraph.record_decision must not mutate caller-owned metadata dict."""
        graph = ContextGraph(
            evaluators=["exact_match"],
            eval_config={"exact_match": {"expected": "approved"}},
        )

        shared_metadata = {"caller_key": "caller_value"}

        # Decision 1: outcome matches expected
        dec_id_1 = graph.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request 1",
            reasoning="Customer has excellent payment history",
            outcome="approved",
            confidence=0.9,
            metadata=shared_metadata,
        )

        # Assert caller dictionary was NOT mutated
        assert "eval_score" not in shared_metadata
        assert "eval_passed" not in shared_metadata
        assert "eval_details" not in shared_metadata
        assert shared_metadata == {"caller_key": "caller_value"}
        assert graph.nodes[dec_id_1].properties["eval_passed"] is True

        # Decision 2: reusing the exact same shared_metadata dict with outcome="rejected"
        dec_id_2 = graph.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request 2",
            reasoning="Customer has high debt",
            outcome="rejected",
            confidence=0.9,
            metadata=shared_metadata,
        )

        # Reused dictionary should still not be mutated and decision 2 evaluated independently
        assert "eval_score" not in shared_metadata
        assert graph.nodes[dec_id_2].properties["eval_passed"] is False

    def test_evaluated_decision_id_matches_context_graph_node_id(self, mock_vector_store):
        """Decision passed to evaluators must have the same decision_id as the ContextGraph node."""
        graph = ContextGraph()
        captured_ids = []

        def capture_evaluator(decision, **kwargs):
            captured_ids.append(decision.decision_id)
            return True

        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
            evaluators=[capture_evaluator],
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history",
            outcome="approved",
            confidence=0.9,
        )

        assert decision_id in graph.nodes
        assert len(captured_ids) == 1
        assert captured_ids[0] == decision_id

    def test_evaluator_type_error_invoked_only_once(self, mock_vector_store):
        """Evaluator raising internal TypeError must not be retried with stripped arguments."""
        graph = ContextGraph()
        call_count = 0

        def failing_with_type_error(decision, config=None):
            nonlocal call_count
            call_count += 1
            raise TypeError("internal type error within evaluator body")

        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
            evaluators=[failing_with_type_error],
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history",
            outcome="approved",
            confidence=0.9,
        )

        assert call_count == 1
        assert decision_id in graph.nodes
        node = graph.nodes[decision_id]
        assert node.properties["eval_passed"] is False

    def test_caller_large_eval_details_rejected_by_size_check(self):
        """Caller-supplied eval_details is subject to length check without exemption."""
        graph = ContextGraph()

        with pytest.raises(ValueError, match="Metadata values must be 1000 characters or less"):
            graph.record_decision(
                category="credit_approval",
                scenario="Credit limit increase request",
                reasoning="Customer has excellent payment history",
                outcome="approved",
                confidence=0.9,
                metadata={"eval_details": "x" * 1001},
            )

        with pytest.raises(ValueError, match="Additional field values must be 1000 characters or less"):
            graph.record_decision(
                category="credit_approval",
                scenario="Credit limit increase request",
                reasoning="Customer has excellent payment history",
                outcome="approved",
                confidence=0.9,
                eval_details="x" * 1001,
            )

    def test_record_decision_evaluator_failure_non_blocking(self, mock_vector_store, caplog):
        """Failing evaluator must not prevent decision persistence."""
        graph = ContextGraph()

        def broken_evaluator(decision, **kwargs):
            raise RuntimeError("Evaluator execution crash")

        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
            evaluators=[broken_evaluator],
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history",
            outcome="approved",
            confidence=0.9,
        )

        assert decision_id is not None
        assert decision_id in graph.nodes
        node = graph.nodes[decision_id]
        assert "eval_score" in node.properties
        assert node.properties["eval_passed"] is False
        assert "Evaluator execution crash" in caplog.text

    def test_record_decision_without_evaluators_unchanged(self, mock_vector_store):
        """Omission of evaluators preserves existing behavior."""
        graph = ContextGraph()
        context = AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=graph,
            decision_tracking=True,
        )

        decision_id = context.record_decision(
            category="credit_approval",
            scenario="Credit limit increase request",
            reasoning="Customer has excellent payment history",
            outcome="approved",
            confidence=0.9,
        )

        assert decision_id is not None
        assert decision_id in graph.nodes
        node = graph.nodes[decision_id]
        assert "eval_score" not in node.properties
        assert "eval_passed" not in node.properties
        assert "eval_details" not in node.properties
