"""
Tests for Decision Query and Precedent Search

This module tests the DecisionQuery class and its methods
for finding precedents, filtering, and multi-hop reasoning.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from semantica.context.decision_models import Decision, Policy, PolicyException
from semantica.context.decision_query import DecisionQuery
from semantica.context.decision_recorder import DecisionRecorder


class TestDecisionQuery:
    """Test DecisionQuery class."""
    
    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store for testing."""
        mock_store = Mock()
        mock_store.execute_query = Mock()
        return mock_store
    
    @pytest.fixture
    def mock_embedding_generator(self):
        """Mock embedding generator for testing."""
        mock_generator = Mock()
        mock_generator.generate = Mock(return_value=[0.1, 0.2, 0.3])
        return mock_generator
    
    @pytest.fixture
    def decision_query(self, mock_graph_store, mock_embedding_generator):
        """Create DecisionQuery instance with mocked dependencies."""
        return DecisionQuery(
            graph_store=mock_graph_store,
            embedding_generator=mock_embedding_generator
        )
    
    @pytest.fixture
    def sample_decisions(self):
        """Create sample decisions for testing."""
        base_time = datetime.now()
        return [
            Decision(
                decision_id="decision_001",
                category="credit_approval",
                scenario="Credit limit increase for premium customer",
                reasoning="Customer has excellent payment history and low utilization",
                outcome="approved",
                confidence=0.95,
                timestamp=base_time - timedelta(days=1),
                decision_maker="ai_agent_001"
            ),
            Decision(
                decision_id="decision_002",
                category="credit_approval",
                scenario="Credit limit increase for high-risk customer",
                reasoning="Customer has recent late payments but improving trend",
                outcome="rejected",
                confidence=0.75,
                timestamp=base_time - timedelta(days=2),
                decision_maker="ai_agent_002"
            ),
            Decision(
                decision_id="decision_003",
                category="fraud_detection",
                scenario="Suspicious transaction pattern detected",
                reasoning="Multiple high-value transactions from new device",
                outcome="flagged_for_review",
                confidence=0.88,
                timestamp=base_time - timedelta(days=3),
                decision_maker="ai_agent_001"
            )
        ]
    
    def test_decision_query_initialization(self, mock_graph_store):
        """Test DecisionQuery initialization."""
        query_engine = DecisionQuery(graph_store=mock_graph_store)
        
        assert query_engine.graph_store == mock_graph_store
        assert query_engine.embedding_generator is None
    
    def test_decision_query_with_embedding_generator(self, mock_graph_store, mock_embedding_generator):
        """Test DecisionQuery initialization with embedding generator."""
        query_engine = DecisionQuery(
            graph_store=mock_graph_store,
            embedding_generator=mock_embedding_generator
        )
        
        assert query_engine.graph_store == mock_graph_store
        assert query_engine.embedding_generator == mock_embedding_generator
    
    def test_find_precedents_hybrid_success(self, decision_query, sample_decisions, mock_graph_store):
        """Test successful hybrid precedent search."""
        scenario = "Credit limit increase request"
        category = "credit_approval"
        limit = 5
        
        # Mock graph query results
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "credit_approval",
                "scenario": "Credit limit increase for premium customer",
                "reasoning": "Customer has excellent payment history",
                "outcome": "approved",
                "confidence": 0.95,
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                "decision_maker": "ai_agent_001",
                "similarity_score": 0.85
            }
        ]
        
        precedents = decision_query.find_precedents_hybrid(scenario, category, limit)
        
        assert len(precedents) == 1
        assert precedents[0].decision_id == "decision_001"
        assert precedents[0].category == "credit_approval"
        
        # Verify graph query was called
        mock_graph_store.execute_query.assert_called()
    
    def test_find_precedents_hybrid_no_category(self, decision_query, mock_graph_store):
        """Test hybrid precedent search without category filter."""
        scenario = "Credit limit increase request"
        
        mock_graph_store.execute_query.return_value = []
        
        precedents = decision_query.find_precedents_hybrid(scenario, None, 10)
        
        assert isinstance(precedents, list)
        
        # Verify query was called without category filter
        call_args = mock_graph_store.execute_query.call_args
        query = call_args[0][0]
        assert "d.category" not in query or "d.category IS NOT NULL" in query
    
    def test_find_precedents_hybrid_no_embedding_generator(self, mock_graph_store):
        """Test hybrid precedent search without embedding generator."""
        query_engine = DecisionQuery(graph_store=mock_graph_store)
        
        mock_graph_store.execute_query.return_value = []
        
        precedents = query_engine.find_precedents_hybrid("test scenario", "test", 5)
        
        assert isinstance(precedents, list)
    
    def test_find_by_category_success(self, decision_query, sample_decisions, mock_graph_store):
        """Test finding decisions by category."""
        category = "credit_approval"
        limit = 10
        
        # Mock graph query results
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "credit_approval",
                "scenario": "Credit limit increase",
                "reasoning": "Good payment history",
                "outcome": "approved",
                "confidence": 0.95,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "ai_agent_001"
            },
            {
                "decision_id": "decision_002",
                "category": "credit_approval",
                "scenario": "Credit limit denied",
                "reasoning": "High risk profile",
                "outcome": "rejected",
                "confidence": 0.75,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "ai_agent_002"
            }
        ]
        
        decisions = decision_query.find_by_category(category, limit)
        
        assert len(decisions) == 2
        assert all(d.category == category for d in decisions)
        
        # Verify query was called
        mock_graph_store.execute_query.assert_called_once()
    
    def test_find_by_category_no_results(self, decision_query, mock_graph_store):
        """Test finding decisions by category with no results."""
        mock_graph_store.execute_query.return_value = []
        
        decisions = decision_query.find_by_category("nonexistent_category", 10)
        
        assert len(decisions) == 0
    
    def test_find_by_entity_success(self, decision_query, mock_graph_store):
        """Test finding decisions by entity."""
        entity_id = "customer:jessica_norris"
        limit = 10
        
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "credit_approval",
                "scenario": "Credit limit increase",
                "reasoning": "Good customer",
                "outcome": "approved",
                "confidence": 0.95,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "ai_agent_001"
            }
        ]
        
        decisions = decision_query.find_by_entity(entity_id, limit)
        
        assert len(decisions) == 1
        
        # Verify query was called with correct entity in params
        call_args = mock_graph_store.execute_query.call_args
        params = call_args[0][1]
        assert params["entity_id"] == entity_id
    
    def test_find_by_time_range_success(self, decision_query, mock_graph_store):
        """Test finding decisions by time range."""
        start_time = datetime.now() - timedelta(days=7)
        end_time = datetime.now()
        limit = 10
        
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "credit_approval",
                "scenario": "Credit limit increase",
                "reasoning": "Good customer",
                "outcome": "approved",
                "confidence": 0.95,
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
                "decision_maker": "ai_agent_001"
            }
        ]
        
        decisions = decision_query.find_by_time_range(start_time, end_time, limit)
        
        assert len(decisions) == 1
        
        # Verify query was called with time range
        call_args = mock_graph_store.execute_query.call_args
        query = call_args[0][0]
        assert "d.timestamp >= " in query
        assert "d.timestamp <= " in query
    
    def test_find_by_time_range_invalid_range(self, decision_query):
        """Test finding decisions with invalid time range."""
        start_time = datetime.now()
        end_time = datetime.now() - timedelta(days=1)  # End before start
        
        with pytest.raises(ValueError, match="End time must be after start time"):
            decision_query.find_by_time_range(start_time, end_time, 10)
    
    def test_multi_hop_reasoning_success(self, decision_query, mock_graph_store):
        """Test multi-hop reasoning."""
        start_entity = "customer:jessica_norris"
        query_context = "Find related credit decisions"
        max_hops = 3
        
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "decision_001",
                "category": "credit_approval",
                "scenario": "Credit limit increase",
                "reasoning": "Good customer",
                "outcome": "approved",
                "confidence": 0.95,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "ai_agent_001",
                "hop_distance": 2
            }
        ]
        
        decisions = decision_query.multi_hop_reasoning(start_entity, query_context, max_hops)
        
        assert len(decisions) == 1
        assert decisions[0].decision_id == "decision_001"
        
        # Verify query was called with max hops
        call_args = mock_graph_store.execute_query.call_args
        query = call_args[0][0]
        assert f"*1..{max_hops}" in query
    
    def test_multi_hop_reasoning_invalid_max_hops(self, decision_query):
        """Test multi-hop reasoning with invalid max hops."""
        with pytest.raises(ValueError, match="max_hops must be between 1 and 10"):
            decision_query.multi_hop_reasoning("entity", "query", 0)
        
        with pytest.raises(ValueError, match="max_hops must be between 1 and 10"):
            decision_query.multi_hop_reasoning("entity", "query", 11)
    
    def test_trace_decision_path_success(self, decision_query, mock_graph_store):
        """Test tracing decision paths."""
        decision_id = "decision_001"
        relationship_types = ["CAUSED", "INFLUENCED"]
        
        mock_graph_store.execute_query.return_value = [
            {
                "path_nodes": [{"decision_id": "d1", "scenario": "S1", "category": "C1"}],
                "path_rels": [{"from": "d1", "to": "d2", "type": "CAUSED"}],
                "path_length": 2
            },
            {
                "path_nodes": [{"decision_id": "d2", "scenario": "S2", "category": "C2"}],
                "path_rels": [],
                "path_length": 3
            }
        ]

        paths = decision_query.trace_decision_path(decision_id, relationship_types)

        assert len(paths) == 2
        assert paths[0]["path_length"] == 2
        assert isinstance(paths[0]["nodes"], list)
        assert isinstance(paths[0]["relationships"], list)
        assert paths[0]["nodes"][0]["scenario"] == "S1"
        assert paths[0]["relationships"][0]["type"] == "CAUSED"
        
        # Verify query was called with relationship types
        call_args = mock_graph_store.execute_query.call_args
        query = call_args[0][0]
        for rel_type in relationship_types:
            assert rel_type in query
    
    def test_find_similar_exceptions_success(self, decision_query, mock_graph_store):
        """Test finding similar exceptions."""
        exception_reason = "High-risk customer with special circumstances"
        limit = 10
        
        mock_graph_store.execute_query.return_value = [
            {
                "exception_id": "exception_001",
                "decision_id": "decision_001",
                "policy_id": "policy_001",
                "reason": "High-risk customer with VIP status",
                "approver": "manager_001",
                "approval_timestamp": datetime.now().isoformat(),
                "justification": "Long-term valuable customer",
                "similarity_score": 0.85
            }
        ]
        
        exceptions = decision_query.find_similar_exceptions(exception_reason, limit)
        
        assert len(exceptions) == 1
        assert exceptions[0].exception_id == "exception_001"
        assert exceptions[0].reason == "High-risk customer with VIP status"
    
    def test_find_similar_exceptions_no_embedding_generator(self, mock_graph_store):
        """Test finding similar exceptions without embedding generator."""
        query_engine = DecisionQuery(graph_store=mock_graph_store)
        
        mock_graph_store.execute_query.return_value = []
        
        exceptions = query_engine.find_similar_exceptions("test reason", 10)
        
        assert isinstance(exceptions, list)
    
    def test_calculate_semantic_similarity_success(self, decision_query):
        """Test semantic similarity calculation."""
        text1 = "Credit limit increase for premium customer"
        text2 = "Credit limit increase request for valued customer"
        
        # Mock embedding generator
        decision_query.embedding_generator = Mock()
        decision_query.embedding_generator.generate.side_effect = [
            [0.1, 0.2, 0.3, 0.4],
            [0.1, 0.2, 0.3, 0.5]
        ]
        
        similarity = decision_query._calculate_semantic_similarity(text1, text2)
        
        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
        assert similarity > 0.9  # Should be high similarity
    
    def test_calculate_semantic_similarity_no_generator(self, decision_query):
        """Test semantic similarity calculation without embedding generator."""
        decision_query.embedding_generator = None  # Simulate no generator
        similarity = decision_query._calculate_semantic_similarity("text1", "text2")

        assert similarity == 0.0  # Default when no generator
    
    def test_calculate_structural_similarity_success(self, decision_query):
        """Test structural (cosine) similarity calculation between two embeddings."""
        embedding1 = [0.1, 0.2, 0.3, 0.4]
        embedding2 = [0.1, 0.2, 0.3, 0.5]

        similarity = decision_query._cosine_similarity(embedding1, embedding2)

        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
        assert similarity > 0.9  # Should be high similarity

    def test_calculate_structural_similarity_empty_embeddings(self, decision_query):
        """Test cosine similarity with empty embeddings."""
        similarity = decision_query._cosine_similarity([], [])

        assert similarity == 0.0

    def test_calculate_structural_similarity_mismatched_lengths(self, decision_query):
        """Test cosine similarity with mismatched embedding lengths."""
        embedding1 = [0.1, 0.2, 0.3]
        embedding2 = [0.1, 0.2, 0.3, 0.4]

        similarity = decision_query._cosine_similarity(embedding1, embedding2)

        assert similarity == 0.0  # Should handle mismatch gracefully
    
    def test_hybrid_score_calculation(self, decision_query):
        """Test hybrid score calculation."""
        semantic_score = 0.8
        structural_score = 0.7
        
        # Test default weights
        hybrid_score = decision_query._calculate_hybrid_score(semantic_score, structural_score)
        assert hybrid_score == 0.75  # (0.8 + 0.7) / 2
        
        # Test custom weights
        hybrid_score = decision_query._calculate_hybrid_score(
            semantic_score, structural_score, semantic_weight=0.7, structural_weight=0.3
        )
        assert hybrid_score == 0.77  # 0.8 * 0.7 + 0.7 * 0.3
    
    def test_hybrid_score_calculation_invalid_weights(self, decision_query):
        """Test hybrid score calculation with invalid weights."""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            decision_query._calculate_hybrid_score(0.8, 0.7, 0.8, 0.3)  # Sum = 1.1
    
    def test_query_execution_error_handling(self, decision_query, mock_graph_store):
        """Test error handling during query execution."""
        mock_graph_store.execute_query.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            decision_query.find_by_category("test", 10)
    
    def test_empty_result_handling(self, decision_query, mock_graph_store):
        """Test handling of empty query results."""
        mock_graph_store.execute_query.return_value = []
        
        decisions = decision_query.find_by_category("test", 10)
        
        assert decisions == []
    
    def test_malformed_result_handling(self, decision_query, mock_graph_store):
        """Test handling of partial/malformed query results — should succeed with defaults."""
        mock_graph_store.execute_query.return_value = [
            {"decision_id": "test"}  # Missing optional fields — handled with defaults
        ]

        decisions = decision_query.find_by_category("test", 10)
        assert len(decisions) == 1
        assert decisions[0].decision_id == "test"
    
    def test_large_limit_handling(self, decision_query, mock_graph_store):
        """Test handling of large limit values."""
        mock_graph_store.execute_query.return_value = []
        
        # Should handle large limits gracefully
        decisions = decision_query.find_by_category("test", 10000)
        
        assert isinstance(decisions, list)
        
        # Verify limit was passed as a parameter
        call_args = mock_graph_store.execute_query.call_args
        params = call_args[0][1]
        assert params["limit"] == 10000
    
    def test_special_characters_in_search(self, decision_query, mock_graph_store):
        """Test handling of special characters in search strings."""
        mock_graph_store.execute_query.return_value = []
        
        # Test with special characters
        scenario = "Credit limit increase for customer with special chars: @#$%^&*()"
        decisions = decision_query.find_precedents_hybrid(scenario, "test", 5)
        
        assert isinstance(decisions, list)
    
    def test_null_and_empty_values_handling(self, decision_query, mock_graph_store):
        """Test handling of null and empty values."""
        # Mock result with null/empty values
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "test_001",
                "category": None,
                "scenario": "",
                "reasoning": "Test reasoning",
                "outcome": "approved",
                "confidence": 0.8,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": ""
            }
        ]
        
        decisions = decision_query.find_by_category("test", 10)
        
        assert len(decisions) == 1
        assert decisions[0].category is None
        assert decisions[0].scenario == ""
    
    def test_concurrent_query_execution(self, decision_query, mock_graph_store):
        """Test concurrent query execution."""
        import threading
        import time
        
        results = []
        errors = []
        
        def query_thread(category):
            try:
                mock_graph_store.execute_query.return_value = []
                decisions = decision_query.find_by_category(category, 10)
                results.append(len(decisions))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=query_thread, args=(f"category_{i}",))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0
        assert len(results) == 5
    
    def test_memory_efficiency_large_results(self, decision_query, mock_graph_store):
        """Test memory efficiency with large result sets."""
        # Mock large result set
        large_results = [
            {
                "decision_id": f"decision_{i}",
                "category": "test",
                "scenario": f"Scenario {i}",
                "reasoning": f"Reasoning {i}",
                "outcome": "approved",
                "confidence": 0.8,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "ai_agent"
            }
            for i in range(1000)
        ]
        
        mock_graph_store.execute_query.return_value = large_results
        
        decisions = decision_query.find_by_category("test", 1000)
        
        assert len(decisions) == 1000
        # Verify memory usage is reasonable (this is a basic check)
        assert len(str(decisions)) > 0  # Ensure decisions are properly created

    def test_dict_to_decision_deserializes_json_string_metadata(self, decision_query):
        """DecisionQuery._dict_to_decision must decode JSON string metadata to dict and support item assignment."""
        data = {
            "decision_id": "dec_json_001",
            "category": "risk_check",
            "scenario": "loan scenario",
            "reasoning": "low risk",
            "outcome": "approved",
            "confidence": 0.9,
            "timestamp": datetime.now().isoformat(),
            "decision_maker": "agent",
            "metadata": '{"tags": ["auto", "verified"], "score": 95}'
        }
        decision = decision_query._dict_to_decision(data)
        assert isinstance(decision.metadata, dict)
        assert decision.metadata["tags"] == ["auto", "verified"]
        assert decision.metadata["score"] == 95

        # Item assignment must work (preventing TypeError: 'str' object does not support item assignment)
        decision.metadata["similarity_score"] = 0.88
        assert decision.metadata["similarity_score"] == 0.88
        assert decision.metadata.get("similarity_score", 0) == 0.88

    def test_dict_to_decision_handles_malformed_and_native_metadata(self, decision_query):
        """DecisionQuery._dict_to_decision gracefully handles native dicts, malformed strings, and None."""
        base = {
            "decision_id": "dec_edge_001",
            "category": "test",
            "scenario": "test",
            "reasoning": "test",
            "outcome": "test",
            "confidence": 0.8,
            "timestamp": datetime.now().isoformat(),
            "decision_maker": "test"
        }

        # Native dict (in-memory ContextGraph)
        dec1 = decision_query._dict_to_decision({**base, "metadata": {"key": "val"}})
        assert dec1.metadata == {"key": "val"}

        # Malformed non-JSON string
        dec2 = decision_query._dict_to_decision({**base, "metadata": "not-valid-json"})
        assert dec2.metadata == {"raw": "not-valid-json"}

        # None / missing
        dec3 = decision_query._dict_to_decision({**base, "metadata": None})
        assert dec3.metadata == {}

    def test_dict_to_exception_deserializes_json_string_metadata(self, decision_query):
        """DecisionQuery._dict_to_exception decodes JSON string metadata to dict."""
        data = {
            "exception_id": "exc_json_001",
            "decision_id": "dec_json_001",
            "policy_id": "pol_001",
            "reason": "override",
            "approver": "supervisor",
            "approval_timestamp": datetime.now().isoformat(),
            "justification": "urgent",
            "metadata": '{"rule": "bypass", "approved": true}'
        }
        exc = decision_query._dict_to_exception(data)
        assert isinstance(exc.metadata, dict)
        assert exc.metadata["rule"] == "bypass"
        assert exc.metadata["approved"] is True

    def test_neo4j_record_and_query_roundtrip(self, mock_graph_store, mock_embedding_generator):
        """Round-trip: record decision through DecisionRecorder, decode through DecisionQuery."""
        recorder = DecisionRecorder(graph_store=mock_graph_store)
        query = DecisionQuery(graph_store=mock_graph_store, embedding_generator=mock_embedding_generator)

        original_metadata = {"source": "test_suite", "tags": ["neo4j", "roundtrip"], "version": 1}
        decision = Decision(
            decision_id="roundtrip_dec_001",
            category="finance",
            scenario="customer refund",
            reasoning="within policy bounds",
            outcome="approved",
            confidence=0.92,
            timestamp=datetime.now(),
            decision_maker="refund_agent",
            reasoning_embedding=[0.1, 0.2, 0.3],
            metadata=original_metadata
        )

        recorder._store_decision_node(decision)

        # Retrieve arguments passed to execute_query
        call_args = mock_graph_store.execute_query.call_args[0]
        params = call_args[1]

        # Verify property sent to graph store is a JSON string (Neo4j safe)
        assert isinstance(params["metadata"], str)
        assert not isinstance(params["metadata"], dict)

        # Feed the recorded parameters into DecisionQuery as returned by Neo4j
        reconstructed = query._dict_to_decision(params)

        assert reconstructed.decision_id == decision.decision_id
        assert reconstructed.metadata == original_metadata
        # Downstream mutations (similarity_score) succeed
        reconstructed.metadata["similarity_score"] = 0.99
        assert reconstructed.metadata["similarity_score"] == 0.99


class TestDecisionQueryEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store for testing."""
        mock_store = Mock()
        mock_store.execute_query = Mock()
        return mock_store

    @pytest.fixture
    def decision_query(self, mock_graph_store):
        """Create DecisionQuery with minimal dependencies."""
        return DecisionQuery(graph_store=mock_graph_store)
    
    def test_empty_string_search(self, decision_query, mock_graph_store):
        """Test searching with empty strings."""
        mock_graph_store.execute_query.return_value = []
        
        decisions = decision_query.find_precedents_hybrid("", "", 10)
        
        assert isinstance(decisions, list)
    
    def test_unicode_content_search(self, decision_query, mock_graph_store):
        """Test searching with unicode content."""
        mock_graph_store.execute_query.return_value = []
        
        scenario = "Crédit limit increase for customer café"
        decisions = decision_query.find_precedents_hybrid(scenario, "test", 5)
        
        assert isinstance(decisions, list)
    
    def test_extreme_confidence_values(self, decision_query, mock_graph_store):
        """Test handling of extreme confidence values."""
        # Mock result with extreme confidence values
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "test_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 1.0,  # Maximum
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test"
            },
            {
                "decision_id": "test_002",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.0,  # Minimum
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test"
            }
        ]
        
        decisions = decision_query.find_by_category("test", 10)
        
        assert len(decisions) == 2
        assert decisions[0].confidence == 1.0
        assert decisions[1].confidence == 0.0
    
    def test_future_timestamps(self, decision_query, mock_graph_store):
        """Test handling of future timestamps."""
        future_time = datetime.now() + timedelta(days=1)
        
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "test_001",
                "category": "test",
                "scenario": "test",
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": future_time.isoformat(),
                "decision_maker": "test"
            }
        ]
        
        decisions = decision_query.find_by_category("test", 10)
        
        assert len(decisions) == 1
        assert decisions[0].timestamp > datetime.now()
    
    def test_very_long_text_content(self, decision_query, mock_graph_store):
        """Test handling of very long text content."""
        long_scenario = "test " * 10000  # Very long scenario
        
        mock_graph_store.execute_query.return_value = [
            {
                "decision_id": "test_001",
                "category": "test",
                "scenario": long_scenario,
                "reasoning": "test",
                "outcome": "test",
                "confidence": 0.8,
                "timestamp": datetime.now().isoformat(),
                "decision_maker": "test"
            }
        ]
        
        decisions = decision_query.find_by_category("test", 10)
        
        assert len(decisions) == 1
        assert len(decisions[0].scenario) == len(long_scenario)


if __name__ == "__main__":
    pytest.main([__file__])
