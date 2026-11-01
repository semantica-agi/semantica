"""
Tests for KG Algorithm Integration

This module contains tests to verify that KG algorithms are properly
integrated and used in the enhanced vector store functionality.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from semantica.vector_store.decision_embedding_pipeline import DecisionEmbeddingPipeline
from semantica.context import ContextRetriever


class TestKGAlgorithmIntegration:
    """Test cases for KG algorithm integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock vector store
        self.mock_vector_store = Mock()
        self.mock_vector_store.embed.return_value = np.array([0.1, 0.2, 0.3, 0.4])
        
        # Mock graph store
        self.mock_graph_store = Mock()
        self.mock_graph_store.get_neighbors.return_value = ["neighbor1", "neighbor2"]
        
        # Sample decision data
        self.sample_decision = {
            "scenario": "Credit limit increase request",
            "reasoning": "Good payment history",
            "outcome": "approved",
            "confidence": 0.85,
            "entities": ["customer_123", "credit_card"],
            "category": "credit_approval"
        }
    
    def test_decision_pipeline_kg_algorithm_imports(self):
        """Test that KG algorithms are properly imported in DecisionEmbeddingPipeline."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=True
        )
        
        # Verify KG algorithm components are initialized
        assert hasattr(pipeline, 'similarity_calculator')
        assert hasattr(pipeline, 'path_finder')
        assert hasattr(pipeline, 'connectivity_analyzer')
        assert hasattr(pipeline, 'centrality_calculator')
        assert hasattr(pipeline, 'community_detector')
        
        # Verify they are not None when graph store is provided
        assert pipeline.similarity_calculator is not None
        assert pipeline.path_finder is not None
        assert pipeline.connectivity_analyzer is not None
        assert pipeline.centrality_calculator is not None
        assert pipeline.community_detector is not None
    
    def test_decision_pipeline_kg_algorithms_disabled_without_graph_store(self):
        """Test that KG algorithms are disabled without graph store."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=None,
            use_graph_features=True
        )
        
        # Verify KG algorithm components are None without graph store
        assert pipeline.similarity_calculator is None
        assert pipeline.path_finder is None
        assert pipeline.connectivity_analyzer is None
        assert pipeline.centrality_calculator is None
        assert pipeline.community_detector is None
    
    def test_decision_pipeline_kg_algorithms_can_be_disabled(self):
        """Test that KG algorithms can be explicitly disabled."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=False
        )
        
        # Verify KG algorithm components are None when disabled
        assert pipeline.similarity_calculator is None
        assert pipeline.path_finder is None
        assert pipeline.connectivity_analyzer is None
        assert pipeline.centrality_calculator is None
        assert pipeline.community_detector is None
    
    def test_context_retriever_kg_algorithm_imports(self):
        """Test that KG algorithms are properly imported in ContextRetriever."""
        retriever = ContextRetriever(
            vector_store=self.mock_vector_store,
            knowledge_graph=self.mock_graph_store
        )
        
        # Verify KG algorithm components are initialized
        assert hasattr(retriever, 'path_finder')
        assert hasattr(retriever, 'centrality_calculator')
        assert hasattr(retriever, 'community_detector')
        assert hasattr(retriever, 'similarity_calculator')
        
        # Verify they are not None when knowledge graph is provided
        assert retriever.path_finder is not None
        assert retriever.centrality_calculator is not None
        assert retriever.community_detector is not None
        assert retriever.similarity_calculator is not None
    
    def test_context_retriever_kg_algorithms_disabled_without_knowledge_graph(self):
        """Test that KG algorithms are disabled without knowledge graph."""
        retriever = ContextRetriever(
            vector_store=self.mock_vector_store,
            knowledge_graph=None
        )
        
        # Verify KG algorithm components are None without knowledge graph
        assert retriever.path_finder is None
        assert retriever.centrality_calculator is None
        assert retriever.community_detector is None
        assert retriever.similarity_calculator is None
    
    @patch('semantica.vector_store.decision_embedding_pipeline.NodeEmbedder')
    def test_structural_embedding_uses_kg_algorithms(self, mock_node_embedder):
        """Test that structural embedding generation uses KG algorithms."""
        # Mock NodeEmbedder
        mock_node_embedder.return_value.compute_embeddings.return_value = {
            "customer_123": [0.1, 0.2, 0.3],
            "credit_card": [0.4, 0.5, 0.6]
        }
        
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=True
        )
        
        # Mock vector store methods
        self.mock_vector_store.store_vectors.return_value = ["decision_123"]
        
        # Process decision to trigger structural embedding generation
        result = pipeline.process_decision(self.sample_decision)
        
        # Verify NodeEmbedder was used
        mock_node_embedder.return_value.compute_embeddings.assert_called()
        
        # Verify structural embedding was generated
        assert result["structural_embedding"] is not None
        assert isinstance(result["structural_embedding"], np.ndarray)
    
    @patch('semantica.context.context_retriever.PathFinder')
    @patch('semantica.context.context_retriever.CommunityDetector')
    @patch('semantica.context.context_retriever.CentralityCalculator')
    def test_context_expansion_uses_kg_algorithms(self, mock_centrality, mock_community, mock_path_finder):
        """Test that context expansion uses KG algorithms."""
        # Mock KG algorithms
        mock_path_finder.return_value.find_shortest_path.return_value = ["entity1", "entity2", "entity3"]
        mock_community.return_value.detect_communities.return_value = {
            "communities": [
                ["customer_123", "related_entity1", "related_entity2"],
                ["other_entity"],
            ],
            "node_assignments": {
                "customer_123": 0, "related_entity1": 0, "related_entity2": 0,
                "other_entity": 1,
            },
            "modularity": 0.5,
            "algorithm": "louvain",
        }
        mock_centrality.return_value.calculate_degree_centrality.return_value = 0.8
        
        retriever = ContextRetriever(
            vector_store=self.mock_vector_store,
            knowledge_graph=self.mock_graph_store
        )
        
        # Test context expansion with multiple entities so path_finder is invoked
        entities = [
            {"name": "customer_123", "type": "entity"},
            {"name": "related_entity1", "type": "entity"}
        ]
        expanded = retriever._expand_decision_context(entities, max_hops=2)

        # Verify KG algorithms were called
        mock_path_finder.return_value.find_shortest_path.assert_called()
        mock_community.return_value.detect_communities.assert_called()
        
        # Verify expanded entities contain KG algorithm information
        assert len(expanded) > 0
        
        # Check for path-based expansions
        path_entities = [e for e in expanded if e.get("source") == "path_finder"]
        assert len(path_entities) > 0
        
        # Check for community-based expansions
        community_entities = [e for e in expanded if e.get("source") == "community_detector"]
        assert len(community_entities) > 0
    
    def test_kg_algorithm_integration_in_decision_context(self):
        """Test KG algorithm integration in DecisionContext."""
        from semantica.context import DecisionContext
        
        # Mock decision pipeline to use KG algorithms
        with patch('semantica.context.decision_context.DecisionEmbeddingPipeline') as mock_pipeline:
            mock_pipeline.return_value.process_decision.return_value = {
                "vector_id": "decision_123",
                "semantic_embedding": np.array([0.1, 0.2, 0.3, 0.4]),
                "structural_embedding": np.array([0.5, 0.6, 0.7, 0.8])
            }
            
            context = DecisionContext(
                vector_store=self.mock_vector_store,
                graph_store=self.mock_graph_store,
                use_graph_features=True
            )
            
            # Verify decision pipeline was initialized with KG algorithms
            mock_pipeline.assert_called_once()
            call_args = mock_pipeline.call_args
            assert call_args[1]['use_graph_features'] == True
    
    def test_kg_algorithm_error_handling(self):
        """Test error handling in KG algorithm integration."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=True
        )

        # Mock the pipeline's node_embedder instance directly to raise exception
        mock_node_embedder = Mock()
        mock_node_embedder.compute_embeddings.side_effect = Exception("KG algorithm error")
        pipeline.node_embedder = mock_node_embedder

        # Mock vector store methods
        self.mock_vector_store.store_vectors.return_value = ["decision_123"]

        # Process decision should handle error gracefully
        result = pipeline.process_decision(self.sample_decision)

        # Should still return a result with fallback embedding
        assert result["vector_id"] == "decision_123"
        assert result["semantic_embedding"] is not None
        # Structural embedding should be fallback (random) due to error
        assert result["structural_embedding"] is not None


class TestKGAlgorithmSpecificFeatures:
    """Test specific KG algorithm features."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_vector_store = Mock()
        self.mock_graph_store = Mock()
    
    def test_path_based_similarity_enhancement(self):
        """Test path-based similarity enhancement in embeddings."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=True
        )
        
        # Mock path finder
        with patch.object(pipeline.path_finder, 'find_shortest_path') as mock_path_finder:
            mock_path_finder.return_value = ["entity1", "entity2", "entity3"]
            
            # Test path similarity calculation
            entities = ["entity1", "entity2"]
            path_similarities = pipeline._calculate_path_similarities(entities)
            
            # Verify path finder was called
            assert mock_path_finder.call_count >= 1
            
            # Verify similarity scores are calculated
            assert "entity1" in path_similarities
            assert "entity2" in path_similarities
            assert all(isinstance(sim, dict) for sim in path_similarities.values())
    
    def test_community_detection_integration(self):
        """Test community detection integration."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=True
        )
        
        # Mock community detector
        with patch.object(pipeline.community_detector, 'detect_communities') as mock_community:
            mock_community.return_value = {
                "communities": [
                    ["entity1", "entity2", "entity3"],
                    ["entity4", "entity5"],
                ],
                "node_assignments": {
                    "entity1": 0, "entity2": 0, "entity3": 0,
                    "entity4": 1, "entity5": 1,
                },
                "modularity": 0.5,
                "algorithm": "louvain",
            }
            
            # Test community detection
            entities = ["entity1", "entity4"]
            communities = pipeline._get_entity_communities(entities)
            
            # Verify community detector was called
            mock_community.assert_called_once_with(self.mock_graph_store)
            
            # Verify community assignments
            assert communities["entity1"] == 0
            assert communities["entity4"] == 1
    
    def test_centrality_weighted_aggregation(self):
        """Test centrality-weighted aggregation of embeddings."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=True
        )
        
        # Test centrality-based aggregation
        entities = ["entity1", "entity2"]
        entity_embeddings = [np.array([0.1, 0.2]), np.array([0.3, 0.4])]
        all_embeddings = {"entity1": [0.1, 0.2], "entity2": [0.3, 0.4]}
        
        weighted_embedding = pipeline._weighted_aggregation(
            entities, entity_embeddings, all_embeddings
        )
        
        # Verify result is a numpy array
        assert isinstance(weighted_embedding, np.ndarray)
        assert len(weighted_embedding) == 2  # Same dimension as input embeddings
    
    def test_connectivity_analysis(self):
        """Test connectivity analysis for entities."""
        pipeline = DecisionEmbeddingPipeline(
            vector_store=self.mock_vector_store,
            graph_store=self.mock_graph_store,
            use_graph_features=True
        )
        
        # Mock graph store neighbors
        self.mock_graph_store.get_neighbors.side_effect = lambda x: ["n1", "n2", "n3"] if x == "entity1" else ["n1"]
        
        entities = ["entity1", "entity2"]
        connectivity_scores = pipeline._calculate_connectivity_scores(entities)
        
        # Verify connectivity scores are calculated
        assert "entity1" in connectivity_scores
        assert "entity2" in connectivity_scores
        assert connectivity_scores["entity1"] > connectivity_scores["entity2"]  # More neighbors


if __name__ == "__main__":
    pytest.main([__file__])
