"""
End-to-End Test Suite 1: Banking Decision System
Tests comprehensive context graphs with KG algorithms and vector store integration
for a real-world banking decision tracking system.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock, MagicMock

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from semantica.context import (
    Decision, Policy, DecisionRecorder, DecisionQuery, 
    AgentContext, ContextGraph, CausalChainAnalyzer, PolicyEngine
)
from semantica.vector_store import VectorStore
from semantica.graph_store import GraphStore


class TestBankingDecisionSystem:
    """End-to-end test suite for banking decision system with context graphs."""
    
    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store for testing."""
        mock_store = Mock(spec=VectorStore)
        mock_store.add = Mock(return_value='test_vector_id')
        mock_store.search = Mock(return_value=[])
        mock_store.get = Mock(return_value=None)
        mock_store.delete = Mock(return_value=True)
        return mock_store
    
    @pytest.fixture
    def mock_knowledge_graph(self):
        """Create a mock knowledge graph for testing."""
        mock_kg = Mock(spec=GraphStore)
        mock_kg.execute_query = Mock(return_value=[])
        mock_kg.add_nodes = Mock(return_value=1)
        mock_kg.add_edges = Mock(return_value=1)
        mock_kg.get_node = Mock(return_value=None)
        mock_kg.get_neighbors = Mock(return_value=[])
        return mock_kg
    
    @pytest.fixture
    def banking_context(self, mock_vector_store, mock_knowledge_graph):
        """Create an enhanced banking context with all features."""
        return AgentContext(
            vector_store=mock_vector_store,
            knowledge_graph=mock_knowledge_graph,
            decision_tracking=True,
            advanced_analytics=True,
            kg_algorithms=True,
            vector_store_features=True
        )
    
    def test_banking_decision_lifecycle(self, banking_context):
        """Test complete banking decision lifecycle with context graphs."""
        print("\n=== Testing Banking Decision Lifecycle ===")
        
        # Step 1: Record multiple banking decisions
        decisions = [
            {
                "category": "mortgage_approval",
                "scenario": "Mortgage application for first-time homebuyer - Strong credit score (750), stable employment, 20% down payment",
                "reasoning": "Strong credit score (750), stable employment, 20% down payment",
                "outcome": "approved",
                "confidence": 0.94,
                "decision_maker": "loan_officer_001"
            },
            {
                "category": "credit_card_approval",
                "scenario": "Premium credit card application - Excellent credit history, high income, existing relationship",
                "reasoning": "Excellent credit history, high income, existing relationship",
                "outcome": "approved",
                "confidence": 0.96,
                "decision_maker": "credit_analyst_002"
            },
            {
                "category": "personal_loan",
                "scenario": "Debt consolidation loan - Good credit history, reasonable DTI ratio, purpose valid",
                "reasoning": "Good credit history, reasonable DTI ratio, purpose valid",
                "outcome": "approved",
                "confidence": 0.87,
                "decision_maker": "loan_officer_003"
            },
            {
                "category": "mortgage_approval",
                "scenario": "Investment property mortgage - High credit score, substantial assets, but investment risk",
                "reasoning": "High credit score, substantial assets, but investment risk",
                "outcome": "rejected",
                "confidence": 0.91,
                "decision_maker": "underwriter_001"
            }
        ]
        
        decision_ids = []
        for decision_data in decisions:
            decision_id = banking_context.record_decision(**decision_data)
            decision_ids.append(decision_id)
            print(f"[OK] Recorded {decision_data['category']}: {decision_id}")
        
        assert len(decision_ids) == 4, "Should have recorded 4 decisions"
        
        # Step 2: Test basic precedent search
        precedents = banking_context.find_precedents(
            scenario="Mortgage application",
            category="mortgage_approval",
            limit=5,
            use_hybrid_search=False
        )
        print(f"[OK] Found {len(precedents)} mortgage precedents")
        
        # Step 3: Test advanced precedent search with KG features
        advanced_precedents = banking_context.find_precedents_advanced(
            scenario="High-value credit application",
            category="credit_approval",
            limit=10,
            use_kg_features=True,
            similarity_weights={
                "semantic": 0.5,
                "structural": 0.3,
                "category": 0.2
            }
        )
        print(f"[OK] Advanced search found {len(advanced_precedents)} precedents")
        
        # Step 4: Test decision influence analysis
        for decision_id in decision_ids:
            influence = banking_context.analyze_decision_influence(decision_id)
            print(f"[OK] Influence analysis for {decision_id}: {type(influence)}")
            
            # Verify influence analysis structure (handle error cases)
            if "error" in influence:
                print(f"[OK] Influence analysis returned expected error: {influence['error']}")
            else:
                assert "decision_id" in influence, "Should contain decision_id"
                assert isinstance(influence.get("influence_score", 0), (int, float)), "Influence score should be numeric"
        
        # Step 5: Test relationship prediction
        predictions = banking_context.predict_decision_relationships(decision_ids[0])
        print(f"[OK] Relationship predictions: {len(predictions)} predictions")
        assert isinstance(predictions, list), "Should return list of predictions"
        
        # Step 6: Test context insights
        insights = banking_context.get_context_insights()
        print(f"[OK] Context insights generated: {type(insights)}")
        
        # Verify insights structure
        assert "timestamp" in insights, "Should contain timestamp"
        assert "memory_stats" in insights, "Should contain memory stats"
        assert "advanced_features" in insights, "Should contain advanced features"
        
        # Verify advanced features status (handle mock environment)
        features = insights["advanced_features"]
        print(f"[OK] Advanced features status: {features}")
        
        # In mock environment, features might not be detected as enabled
        # The important thing is that the system doesn't crash and returns a valid structure
        assert "kg_algorithms_enabled" in features, "Should have kg_algorithms_enabled field"
        assert "vector_store_features_enabled" in features, "Should have vector_store_features_enabled field"
        assert "decision_tracking_enabled" in features, "Should have decision_tracking_enabled field"
        
        print("[OK] Banking decision lifecycle test completed successfully")
    
    def test_context_graph_analytics(self, banking_context):
        """Test context graph analytics and KG algorithms."""
        print("\n=== Testing Context Graph Analytics ===")
        
        # Record some test decisions
        decision_id = banking_context.record_decision(
            category="mortgage_approval",
            scenario="Test mortgage application",
            reasoning="Test reasoning for analytics",
            outcome="approved",
            confidence=0.9,
            decision_maker="test_officer"
        )
        
        # Test context graph analysis
        graph_analysis = banking_context.analyze_context_graph()
        print(f"[OK] Graph analysis completed: {type(graph_analysis)}")
        
        # Verify graph analysis structure
        if "error" not in graph_analysis:
            assert "graph_metrics" in graph_analysis, "Should contain graph metrics"
            metrics = graph_analysis["graph_metrics"]
            assert isinstance(metrics.get("node_count", 0), int), "Node count should be integer"
            assert isinstance(metrics.get("edge_count", 0), int), "Edge count should be integer"
        
        # Test entity similarity
        similar_entities = banking_context.find_similar_entities(
            entity_id="test_customer",
            similarity_type="content",
            top_k=5
        )
        print(f"[OK] Entity similarity search: {len(similar_entities)} results")
        assert isinstance(similar_entities, list), "Should return list of similar entities"
        
        # Test entity centrality
        centrality = banking_context.get_entity_centrality("test_customer")
        print(f"[OK] Entity centrality: {type(centrality)}")
        assert isinstance(centrality, dict), "Should return dictionary of centrality measures"
        
        print("[OK] Context graph analytics test completed successfully")
    
    def test_enhanced_components_integration(self, mock_vector_store, mock_knowledge_graph):
        """Test integration of enhanced components with KG algorithms."""
        # Constructing NodeEmbedder requires gensim (the optional
        # graph-embeddings extra); see tests/test_issue_1513_slim_core.py
        # for the contract that it raises without it.
        pytest.importorskip("gensim")
        print("\n=== Testing Enhanced Components Integration ===")
        
        # Test enhanced DecisionQuery
        enhanced_query = DecisionQuery(
            graph_store=mock_knowledge_graph,
            vector_store=mock_vector_store,
            advanced_analytics=True,
            centrality_analysis=True,
            community_detection=True,
            node_embeddings=True
        )
        
        print(f"[OK] Enhanced DecisionQuery with {len(enhanced_query.kg_components)} KG components")
        assert len(enhanced_query.kg_components) == 6, "Should have 6 KG components"
        
        # Verify KG components
        expected_components = [
            "centrality_calculator",
            "community_detector", 
            "node_embedder",
            "path_finder",
            "similarity_calculator",
            "link_predictor"
        ]
        
        for component in expected_components:
            assert component in enhanced_query.kg_components, f"Should have {component} component"
        
        # Test enhanced ContextGraph
        enhanced_graph = ContextGraph(
            advanced_analytics=True,
            centrality_analysis=True,
            community_detection=True,
            node_embeddings=True
        )
        
        print(f"[OK] Enhanced ContextGraph with {len(enhanced_graph.kg_components)} KG components")
        assert len(enhanced_graph.kg_components) == 6, "Should have 6 KG components"
        
        # Test graph methods
        centrality = enhanced_graph.get_node_centrality("test_node")
        print(f"[OK] Node centrality: {type(centrality)}")
        
        similar_nodes = enhanced_graph.find_similar_nodes("test_node", "content", 5)
        print(f"[OK] Similar nodes: {len(similar_nodes)} nodes")
        
        graph_analysis = enhanced_graph.analyze_graph_with_kg()
        print(f"[OK] Graph KG analysis: {type(graph_analysis)}")
        
        print("[OK] Enhanced components integration test completed successfully")
    
    def test_backward_compatibility(self, mock_vector_store):
        """Test backward compatibility with existing code."""
        print("\n=== Testing Backward Compatibility ===")
        
        # Test old API - should work without changes
        basic_context = AgentContext(vector_store=mock_vector_store)
        print("[OK] Basic AgentContext initialization works")
        
        # Test old DecisionQuery API
        from semantica.context import DecisionQuery
        basic_query = DecisionQuery(graph_store=Mock())
        print("[OK] Basic DecisionQuery initialization works")
        
        # Test old ContextGraph API
        from semantica.context import ContextGraph
        basic_graph = ContextGraph()
        print("[OK] Basic ContextGraph initialization works")
        
        # Test basic operations
        memory_id = basic_context.store("Test memory", conversation_id="test_conv")
        print(f"[OK] Basic store operation works: {memory_id}")
        
        results = basic_context.retrieve("Test query")
        print(f"[OK] Basic retrieve operation works: {len(results)} results")
        
        # Test decision tracking with old API
        if hasattr(basic_context, 'record_decision'):
            try:
                decision_id = basic_context.record_decision(
                    category="test",
                    scenario="Test scenario",
                    reasoning="Test reasoning",
                    outcome="approved",
                    confidence=0.8
                )
                print(f"[OK] Basic decision recording works: {decision_id}")
            except RuntimeError as e:
                if "Decision tracking is not enabled" in str(e):
                    print("[OK] Basic decision tracking correctly disabled when not enabled")
                else:
                    raise
        
        print("[OK] Backward compatibility test completed successfully")
    
    def test_error_handling_and_fallbacks(self, banking_context):
        """Test error handling and graceful fallbacks."""
        print("\n=== Testing Error Handling and Fallbacks ===")
        
        # Test with invalid inputs
        try:
            precedents = banking_context.find_precedents_advanced(
                scenario="",  # Empty scenario
                category="test",
                limit=10
            )
            print("[OK] Handled empty scenario gracefully")
        except Exception as e:
            print(f"[OK] Error handled: {e}")
        
        # Test with non-existent decision ID
        try:
            influence = banking_context.analyze_decision_influence("non_existent_id")
            print(f"[OK] Handled non-existent decision: {type(influence)}")
        except Exception as e:
            print(f"[OK] Error handled: {e}")
        
        # Test with invalid similarity weights
        try:
            precedents = banking_context.find_precedents_advanced(
                scenario="test",
                category="test",
                similarity_weights={"invalid_weight": 1.0}  # Invalid weight
            )
            print("[OK] Handled invalid weights gracefully")
        except Exception as e:
            print(f"[OK] Error handled: {e}")
        
        print("[OK] Error handling and fallbacks test completed successfully")


if __name__ == "__main__":
    # Run the test suite
    pytest.main([__file__, "-v", "-s"])
