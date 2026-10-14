"""
End-to-End Context Integration Tests

This module contains comprehensive end-to-end tests for the enhanced context
retriever with decision tracking and KG algorithm integration.

Test Scenarios:
    - Multi-source context retrieval with decisions
    - KG algorithm integration in context expansion
    - Hybrid search with semantic + structural components
    - Multi-hop reasoning for decision context
    - Performance under realistic loads
    - Error handling and graceful degradation
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch
from typing import Dict, List, Any

from semantica.context import ContextRetriever, DecisionContext, RetrievedContext
from semantica.vector_store import VectorStore, HybridSimilarityCalculator
from semantica.kg.path_finder import PathFinder
from semantica.kg.centrality_calculator import CentralityCalculator
from semantica.kg.community_detector import CommunityDetector


class TestEndToEndContextIntegration:
    """End-to-end tests for context integration."""
    
    def setup_method(self):
        """Set up test environment with realistic data."""
        self.vector_store = VectorStore(backend="inmemory", dimension=384)
        self.mock_kg = Mock()
        
        # Mock KG methods
        self.mock_kg.get_neighbors.return_value = ["related_entity_1", "related_entity_2"]
        self.mock_kg.get_nodes_by_label.return_value = ["policy_1", "policy_2"]
        
        # Realistic context scenarios
        self.financial_context = [
            {
                "content": "Customer requested credit limit increase due to business expansion",
                "score": 0.85,
                "source": "customer_request",
                "metadata": {
                    "customer_id": "cust_123",
                    "request_type": "credit_increase",
                    "amount": 50000,
                    "business_type": "retail"
                }
            },
            {
                "content": "Credit policy guidelines for premium customers",
                "score": 0.92,
                "source": "policy_document",
                "metadata": {
                    "policy_type": "credit_guidelines",
                    "customer_segment": "premium",
                    "max_increase": 100000
                }
            },
            {
                "content": "Previous credit limit approval for similar business",
                "score": 0.78,
                "source": "historical_decision",
                "metadata": {
                    "decision_id": "dec_456",
                    "outcome": "approved",
                    "similar_business": True
                }
            }
        ]
        
        self.risk_context = [
            {
                "content": "Fraud detection alert for unusual transaction pattern",
                "score": 0.91,
                "source": "fraud_system",
                "metadata": {
                    "alert_type": "velocity_anomaly",
                    "risk_score": 0.85,
                    "transaction_count": 15
                }
            },
            {
                "content": "Risk assessment framework for high-value transactions",
                "score": 0.88,
                "source": "risk_policy",
                "metadata": {
                    "framework_type": "transaction_risk",
                    "threshold_amount": 25000
                }
            }
        ]
    
    def test_multi_source_context_retrieval(self):
        """Test context retrieval from multiple sources."""
        print("\n=== Testing Multi-Source Context Retrieval ===")
        
        # Initialize ContextRetriever
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg
        )
        print("[OK] ContextRetriever initialized with vector store and KG")
        
        # Store context data in vector store
        for context_item in self.financial_context + self.risk_context:
            # Convert to vector format
            vector = np.random.rand(384)
            self.vector_store.store_vectors([vector], [context_item])
        
        print(f"[OK] Stored {len(self.financial_context + self.risk_context)} context items")
        
        # Test comprehensive retrieval
        results = retriever.retrieve(
            query="Credit limit increase for business expansion",
            max_results=10,
            graph_expansion=True
        )
        print(f"[OK] Retrieved {len(results)} context items")
        
        # Verify result quality
        assert len(results) > 0, "Should retrieve context items"
        assert all(isinstance(r, RetrievedContext) for r in results), "All should be RetrievedContext"
        assert all(hasattr(r, 'content') for r in results), "All should have content"
        assert all(hasattr(r, 'score') for r in results), "All should have scores"
        
        # Verify score distribution
        scores = [r.score for r in results]
        assert all(0 <= s <= 1 for s in scores), "All scores should be valid"
        print(f"[OK] Score range: {min(scores):.2f} - {max(scores):.2f}")
        
        print("[OK] Multi-source context retrieval successful")
    
    def test_decision_context_integration(self):
        """Test decision context integration with context retriever."""
        print("\n=== Testing Decision Context Integration ===")
        
        # Initialize DecisionContext
        decision_context = DecisionContext(
            vector_store=self.vector_store,
            graph_store=self.mock_kg
        )
        
        # Record financial decisions
        financial_decisions = [
            {
                "scenario": "Credit limit increase for expanding business",
                "reasoning": "Strong revenue growth, excellent payment history",
                "outcome": "approved",
                "confidence": 0.89,
                "entities": ["cust_123", "business_retail", "credit_expansion"],
                "category": "credit_approval"
            },
            {
                "scenario": "High-value transaction fraud investigation",
                "reasoning": "Unusual pattern, multiple locations, short time window",
                "outcome": "blocked",
                "confidence": 0.94,
                "entities": ["transaction_789", "pattern_anomaly", "location_multiple"],
                "category": "fraud_detection"
            }
        ]
        
        decision_ids = []
        for decision in financial_decisions:
            decision_id = decision_context.record_decision(**decision)
            decision_ids.append(decision_id)
            print(f"[OK] Recorded decision: {decision['category']} - {decision['outcome']}")
        
        # Initialize ContextRetriever
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg
        )
        
        # Test decision precedent retrieval
        precedents = retriever.retrieve_decision_precedents(
            query="Credit limit increase for business",
            limit=5,
            use_hybrid_search=True,
            include_context=True
        )
        print(f"[OK] Retrieved {len(precedents)} decision precedents")
        
        # Verify precedent quality
        assert len(precedents) > 0, "Should find decision precedents"
        assert all(p.source == "decision_precedent" for p in precedents), "All should be precedents"
        assert all(hasattr(p, 'related_entities') for p in precedents), "Should have related entities"
        
        # Test decision context retrieval
        decision_context_info = retriever.get_decision_context(
            decision_ids[0],
            depth=2,
            include_entities=True,
            include_policies=True
        )
        print(f"[OK] Retrieved decision context")
        
        # Verify context completeness
        assert hasattr(decision_context_info, 'content'), "Should have content"
        assert hasattr(decision_context_info, 'related_entities'), "Should have entities"
        assert hasattr(decision_context_info, 'related_relationships'), "Should have relationships"
        
        print("[OK] Decision context integration successful")
    
    def test_kg_algorithm_integration(self):
        """Test KG algorithm integration in context expansion."""
        print("\n=== Testing KG Algorithm Integration ===")
        
        # Mock KG algorithms
        mock_path_finder = Mock()
        mock_path_finder.find_shortest_path.return_value = ["entity1", "entity2", "entity3"]
        
        mock_community_detector = Mock()
        mock_community_detector.detect_communities.return_value = {
            "communities": [["entity1", "entity2", "entity3"], ["entity4", "entity5"]],
            "node_assignments": {
                "entity1": 0, "entity2": 0, "entity3": 0,
                "entity4": 1, "entity5": 1,
            },
            "modularity": 0.5,
            "algorithm": "louvain",
        }
        
        mock_centrality_calculator = Mock()
        mock_centrality_calculator.calculate_degree_centrality.return_value = 0.8
        
        # Create retriever with mocked KG algorithms
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg
        )
        
        # Replace with mocks
        retriever.path_finder = mock_path_finder
        retriever.community_detector = mock_community_detector
        retriever.centrality_calculator = mock_centrality_calculator
        
        # Store test data
        vector = np.random.rand(384)
        self.vector_store.store_vectors([vector], [{"content": "Test context", "type": "test"}])
        
        # Test context expansion with KG algorithms
        entities = [{"name": "entity1", "type": "entity"}, {"name": "entity2", "type": "entity"}]
        expanded = retriever._expand_decision_context(entities, max_hops=2)

        print(f"[OK] Expanded context from {len(entities)} to {len(expanded)} entities")
        
        # Verify KG algorithm usage
        mock_path_finder.find_shortest_path.assert_called()
        mock_community_detector.detect_communities.assert_called()
        
        # Verify expansion quality
        assert len(expanded) > len(entities), "Should expand context"
        assert all("source" in e for e in expanded), "All should have source information"
        
        # Check for different expansion types
        expansion_sources = set(e["source"] for e in expanded)
        expected_sources = {"graph_expansion", "path_finder", "community_detector"}
        assert any(source in expansion_sources for source in expected_sources), "Should use multiple algorithms"
        
        print("[OK] KG algorithm integration successful")
    
    def test_hybrid_search_performance(self):
        """Test hybrid search performance with different configurations."""
        print("\n=== Testing Hybrid Search Performance ===")
        
        # Create retriever
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg
        )
        
        # Store test data
        test_data = []
        for i in range(50):
            vector = np.random.rand(384)
            metadata = {
                "content": f"Test document {i}",
                "category": f"category_{i % 5}",
                "importance": i % 3
            }
            test_data.append(metadata)
            self.vector_store.store_vectors([vector], [metadata])
        
        print(f"[OK] Stored {len(test_data)} test documents")
        
        # Test different search configurations
        search_configs = [
            {"graph_expansion": False, "max_results": 10},
            {"graph_expansion": True, "max_results": 10},
            {"graph_expansion": True, "max_results": 20},
            {"graph_expansion": False, "max_results": 20},
        ]
        
        search_times = []
        for i, config in enumerate(search_configs):
            start_time = time.time()

            results = retriever.retrieve(
                query="Test document search",
                **config
            )

            search_time = time.time() - start_time
            search_times.append(search_time)
            print(f"[OK] Config {i+1}: {len(results)} results in {search_time:.3f}s")

            # Verify results
            assert len(results) <= config["max_results"], "Should respect max_results"
            assert all(isinstance(r, RetrievedContext) for r in results), "Should be RetrievedContext"

        # Performance should be reasonable on development machines running real
        # sentence-transformers (384-dim); threshold is 5.0s per config on average
        avg_time = sum(search_times) / len(search_times)
        assert avg_time < 5.0, f"Average search time {avg_time:.3f}s should be under 5 seconds"
    
    def test_multi_hop_reasoning(self):
        """Test multi-hop reasoning capabilities."""
        print("\n=== Testing Multi-Hop Reasoning ===")
        
        # Mock multi-hop KG structure
        def mock_get_neighbors(entity):
            graph = {
                "customer_123": ["transaction_1", "account_1"],
                "transaction_1": ["merchant_1", "location_1"],
                "merchant_1": ["category_1"],
                "account_1": ["branch_1"],
                "branch_1": ["region_1"]
            }
            return graph.get(entity, [])
        
        self.mock_kg.get_neighbors.side_effect = mock_get_neighbors
        
        # Create retriever
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg,
            max_expansion_hops=3
        )
        
        # Store test decision
        decision_context = DecisionContext(
            vector_store=self.vector_store,
            graph_store=self.mock_kg
        )
        
        decision_id = decision_context.record_decision(
            scenario="Customer transaction review",
            reasoning="Review transaction pattern for fraud detection",
            outcome="approved",
            entities=["customer_123"],
            category="transaction_review"
        )
        
        # Test multi-hop context expansion
        entities = [{"name": "customer_123", "type": "customer"}]
        expanded = retriever._expand_decision_context(entities, max_hops=3)
        
        print(f"[OK] Multi-hop expansion: {len(entities)} → {len(expanded)} entities")
        
        # Verify multi-hop discovery
        entity_names = [e["name"] for e in expanded]
        expected_entities = ["transaction_1", "merchant_1", "location_1", "account_1", "branch_1"]
        
        # Should discover entities within 3 hops
        discovered_count = sum(1 for entity in expected_entities if entity in entity_names)
        assert discovered_count >= 3, f"Should discover at least 3 entities, found {discovered_count}"
        
        # Verify hop depth information
        path_entities = [e for e in expanded if e.get("source") == "path_finder"]
        if path_entities:
            assert all("path_length" in e for e in path_entities), "Path entities should have length info"
        
        print("[OK] Multi-hop reasoning successful")
    
    def test_error_handling_and_fallbacks(self):
        """Test error handling and graceful fallbacks."""
        print("\n=== Testing Error Handling and Fallbacks ===")
        
        # Test with None knowledge graph
        retriever_no_kg = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=None
        )
        
        # Store test data
        vector = np.random.rand(384)
        self.vector_store.store_vectors([vector], [{"content": "Test", "type": "test"}])
        
        # Should work without KG
        results = retriever_no_kg.retrieve("Test query", max_results=5)
        assert len(results) > 0, "Should work without KG"
        print("[OK] Works without knowledge graph")
        
        # Test with broken KG
        broken_kg = Mock()
        broken_kg.get_neighbors.side_effect = Exception("KG error")
        
        retriever_broken = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=broken_kg
        )
        
        # Should handle KG errors gracefully
        results = retriever_broken.retrieve("Test query", max_results=5, graph_expansion=True)
        assert len(results) > 0, "Should handle KG errors gracefully"
        print("[OK] Handles KG errors gracefully")
        
        # Test decision context errors
        decision_context = DecisionContext(
            vector_store=self.vector_store,
            graph_store=None
        )
        
        # Test explanation for non-existent decision
        try:
            decision_context.explain_decision("non_existent")
            assert False, "Should raise exception for non-existent decision"
        except ValueError:
            print("[OK] Properly handles non-existent decisions")
        
        # Test with invalid decision data
        try:
            decision_context.record_decision()  # Missing required fields
            assert False, "Should raise exception for missing fields"
        except (ValueError, TypeError):
            print("[OK] Properly handles invalid decision data")
    
    def test_performance_under_load(self):
        """Test performance under realistic load."""
        print("\n=== Testing Performance Under Load ===")
        
        # Create large dataset
        large_dataset = []
        for i in range(200):
            vector = np.random.rand(384)
            metadata = {
                "content": f"Document {i} with content about various topics",
                "category": f"category_{i % 10}",
                "importance": (i % 5) / 4.0,
                "timestamp": f"2024-01-{(i % 28) + 1:02d}"
            }
            large_dataset.append(metadata)
            self.vector_store.store_vectors([vector], [metadata])
        
        print(f"[OK] Created dataset with {len(large_dataset)} documents")
        
        # Create retriever
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg
        )
        
        # Test concurrent searches
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def worker(query):
            start_time = time.time()
            results = retriever.retrieve(query, max_results=10)
            end_time = time.time()
            results_queue.put((query, len(results), end_time - start_time))
        
        # Start multiple searches
        queries = [
            "Document about category_1",
            "Important documents",
            "Recent documents",
            "Documents with high importance",
            "Various content documents"
        ]
        
        threads = []
        start_time = time.time()
        
        for query in queries:
            thread = threading.Thread(target=worker, args=(query,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Collect results
        search_results = []
        while not results_queue.empty():
            search_results.append(results_queue.get())
        
        print(f"[OK] Completed {len(search_results)} concurrent searches in {total_time:.3f}s")
        print(f"[OK] Average time per search: {total_time/len(search_results):.3f}s")
        
        # Verify performance
        assert len(search_results) == len(queries), "All searches should complete"
        assert all(result[1] > 0 for result in search_results), "All should find results"
        assert total_time < 5.0, "Should complete quickly under load"
        
        # Performance should be reasonable
        avg_time = total_time / len(search_results)
        assert avg_time < 1.0, "Average search time should be reasonable"
        
        print("[OK] Performance under load acceptable")


class TestRealWorldContextScenarios:
    """Test real-world context scenarios."""
    
    def setup_method(self):
        """Set up real-world test environment."""
        self.vector_store = VectorStore(backend="inmemory", dimension=384)
        self.mock_kg = Mock()
        
        # Mock realistic KG structure
        def mock_get_neighbors(entity):
            knowledge_graph = {
                "customer_premium": ["account_gold", "relationship_manager"],
                "account_gold": ["branch_downtown", "products_premium"],
                "branch_downtown": ["region_northeast", "staff_advisors"],
                "relationship_manager": ["team_commercial", "expertise_wealth"],
                "fraud_alert": ["transaction_anomaly", "risk_high"],
                "transaction_anomaly": ["pattern_velocity", "location_unusual"],
                "pattern_velocity": ["threshold_exceeded", "alert_triggered"]
            }
            return knowledge_graph.get(entity, [])
        
        self.mock_kg.get_neighbors.side_effect = mock_get_neighbors
    
    def test_banking_customer_context(self):
        """Test banking customer context assembly."""
        print("\n=== Testing Banking Customer Context ===")
        
        # Create decision context
        decision_context = DecisionContext(
            vector_store=self.vector_store,
            graph_store=self.mock_kg
        )
        
        # Record banking decisions
        banking_decisions = [
            {
                "scenario": "Premium customer requests investment advisory services",
                "reasoning": "High net worth individual, long-term relationship, complex portfolio needs",
                "outcome": "approved",
                "confidence": 0.92,
                "entities": ["customer_premium", "services_investment"],
                "category": "service_request"
            },
            {
                "scenario": "Suspicious activity alert for premium customer account",
                "reasoning": "Unusual transaction patterns, large amounts, new payees",
                "outcome": "flagged_for_review",
                "confidence": 0.87,
                "entities": ["customer_premium", "fraud_alert"],
                "category": "fraud_detection"
            }
        ]
        
        decision_ids = []
        for decision in banking_decisions:
            decision_id = decision_context.record_decision(**decision)
            decision_ids.append(decision_id)
            print(f"[OK] Recorded: {decision['category']} - {decision['outcome']}")
        
        # Create context retriever
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg
        )
        
        # Test comprehensive context retrieval
        context_results = retriever.retrieve(
            query="Premium customer investment and fraud assessment",
            max_results=15,
            graph_expansion=True
        )
        
        print(f"[OK] Retrieved {len(context_results)} context items")
        
        # Test decision-specific context
        decision_context_info = retriever.get_decision_context(
            decision_ids[0],
            depth=3,
            include_entities=True,
            include_policies=True
        )
        
        print(f"[OK] Decision context with {len(decision_context_info.related_entities)} entities")
        
        # Verify context quality
        assert len(context_results) > 0, "Should find context"
        assert len(decision_context_info.related_entities) > 0, "Should have related entities"
        
        # Verify entity relationships
        entity_names = [e["name"] for e in decision_context_info.related_entities]
        expected_entities = ["customer_premium", "account_gold", "relationship_manager"]
        found_entities = sum(1 for entity in expected_entities if entity in entity_names)
        assert found_entities >= 2, f"Should find related entities, found {found_entities}"
    
    def test_fraud_investigation_context(self):
        """Test fraud investigation context assembly."""
        print("\n=== Testing Fraud Investigation Context ===")
        
        # Record fraud-related decisions
        decision_context = DecisionContext(
            vector_store=self.vector_store,
            graph_store=self.mock_kg
        )
        
        fraud_decisions = [
            {
                "scenario": "Multiple high-value transactions from new device",
                "reasoning": "Unusual login pattern, rapid succession, amounts exceed thresholds",
                "outcome": "blocked",
                "confidence": 0.94,
                "entities": ["fraud_alert", "transaction_anomaly"],
                "category": "fraud_detection"
            },
            {
                "scenario": "Customer reports unauthorized account access",
                "reasoning": "Customer confirms unauthorized access, IP address mismatch, timing anomaly",
                "outcome": "investigation_opened",
                "confidence": 0.89,
                "entities": ["customer_premium", "fraud_alert"],
                "category": "fraud_investigation"
            }
        ]
        
        for decision in fraud_decisions:
            decision_id = decision_context.record_decision(**decision)
            print(f"[OK] Recorded fraud decision: {decision['outcome']}")
        
        # Test fraud context retrieval
        retriever = ContextRetriever(
            vector_store=self.vector_store,
            knowledge_graph=self.mock_kg
        )
        
        fraud_context = retriever.retrieve_decision_precedents(
            query="Suspicious transaction patterns and fraud alerts",
            limit=10,
            use_hybrid_search=True,
            include_context=True
        )
        
        print(f"[OK] Found {len(fraud_context)} fraud precedents")
        
        # Test multi-hop fraud investigation
        entities = [{"name": "fraud_alert", "type": "alert"}]
        expanded_context = retriever._expand_decision_context(entities, max_hops=3)
        
        print(f"[OK] Expanded fraud context: {len(entities)} → {len(expanded_context)} entities")
        
        # Verify fraud context quality
        assert len(fraud_context) > 0, "Should find fraud precedents"
        assert len(expanded_context) > len(entities), "Should expand context"
        
        # Verify fraud-specific entities discovered
        entity_names = [e["name"] for e in expanded_context]
        fraud_entities = ["transaction_anomaly", "pattern_velocity", "threshold_exceeded"]
        found_fraud_entities = sum(1 for entity in fraud_entities if entity in entity_names)
        assert found_fraud_entities >= 2, f"Should find fraud entities, found {found_fraud_entities}"


if __name__ == "__main__":
    # Run end-to-end tests
    pytest.main([__file__, "-v", "-s"])
