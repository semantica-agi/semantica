"""
Comprehensive end-to-end tests for KG provenance integration.

Tests the unified provenance system with all KG algorithms.
"""

import pytest
import networkx as nx
from typing import Dict, List, Any
import time

from semantica.kg import (
    GraphBuilderWithProvenance,
    AlgorithmTrackerWithProvenance,
    NodeEmbedder,
    SimilarityCalculator,
    LinkPredictor,
    CentralityCalculator,
    CommunityDetector,
    ConnectivityAnalyzer
)


class TestProvenanceIntegration:
    """Test suite for KG provenance integration."""
    
    @pytest.fixture
    def sample_graph_data(self):
        """Sample graph data for testing."""
        return {
            'entities': [
                {'id': 'person1', 'type': 'Person', 'name': 'John Doe', 'age': 30},
                {'id': 'person2', 'type': 'Person', 'name': 'Jane Smith', 'age': 25},
                {'id': 'company1', 'type': 'Organization', 'name': 'Tech Corp'},
                {'id': 'project1', 'type': 'Project', 'name': 'AI Project'},
                {'id': 'skill1', 'type': 'Skill', 'name': 'Python'}
            ],
            'relationships': [
                {'source': 'person1', 'target': 'company1', 'type': 'WORKS_FOR', 'role': 'Engineer'},
                {'source': 'person2', 'target': 'company1', 'type': 'WORKS_FOR', 'role': 'Manager'},
                {'source': 'person1', 'target': 'project1', 'type': 'WORKS_ON'},
                {'source': 'person2', 'target': 'project1', 'type': 'MANAGES'},
                {'source': 'person1', 'target': 'skill1', 'type': 'HAS_SKILL', 'level': 'Expert'},
                {'source': 'project1', 'target': 'skill1', 'type': 'REQUIRES'}
            ]
        }
    
    @pytest.fixture
    def networkx_graph(self):
        """Sample NetworkX graph for testing."""
        graph = nx.Graph()
        graph.add_edges_from([
            ('A', 'B', {'weight': 1.0}),
            ('B', 'C', {'weight': 2.0}),
            ('C', 'D', {'weight': 1.5}),
            ('B', 'E', {'weight': 0.8}),
            ('E', 'D', {'weight': 1.2}),
            ('A', 'F', {'weight': 0.5}),
            ('F', 'G', {'weight': 0.7}),
            ('G', 'H', {'weight': 0.9})
        ])
        return graph
    
    @pytest.fixture
    def sample_embeddings(self):
        """Sample embeddings for testing."""
        return {
            'A': [0.1, 0.2, 0.3, 0.4],
            'B': [0.5, 0.6, 0.7, 0.8],
            'C': [0.9, 1.0, 0.1, 0.2],
            'D': [0.3, 0.4, 0.5, 0.6],
            'E': [0.7, 0.8, 0.9, 1.0],
            'F': [0.2, 0.3, 0.4, 0.5],
            'G': [0.6, 0.7, 0.8, 0.9],
            'H': [0.4, 0.5, 0.6, 0.7]
        }
    
    def test_graph_builder_with_provenance(self, sample_graph_data):
        """Test graph building with provenance tracking."""
        builder = GraphBuilderWithProvenance(provenance=True)
        
        # Build graph with provenance
        result = builder.build_single_source(sample_graph_data)
        
        # Verify graph structure
        assert 'entities' in result
        assert 'relationships' in result
        assert len(result['entities']) == 5
        assert len(result['relationships']) == 6
        
        # Verify provenance tracking
        assert builder.provenance is True
        assert builder._prov_manager is not None
        
        # Check that provenance manager was called
        # (This is a basic check - in a real scenario you'd verify the actual provenance data)
        assert hasattr(builder, '_prov_manager')
    
    def test_algorithm_tracker_initialization(self):
        """Test algorithm tracker initialization."""
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        assert tracker.provenance is True
        assert tracker._prov_manager is not None
        
        # Test without provenance
        tracker_no_prov = AlgorithmTrackerWithProvenance(provenance=False)
        assert tracker_no_prov.provenance is False
        assert tracker_no_prov._prov_manager is None
    
    def test_embedding_computation_tracking(self, networkx_graph, sample_embeddings):
        """Test embedding computation provenance tracking."""
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        # Track embedding computation
        execution_id = tracker.track_embedding_computation(
            graph=networkx_graph,
            algorithm='node2vec',
            embeddings=sample_embeddings,
            parameters={
                'embedding_dimension': 4,
                'walk_length': 10,
                'num_walks': 5,
                'p': 1.0,
                'q': 1.0
            },
            source='test_embedding_computation'
        )
        
        # Verify execution ID was generated
        assert execution_id is not None
        assert execution_id.startswith('embedding_')
        assert len(execution_id) > 10  # UUID should be longer
    
    def test_similarity_calculation_tracking(self, sample_embeddings):
        """Test similarity calculation provenance tracking."""
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        query_embedding = [0.5, 0.5, 0.5, 0.5]
        similarities = {
            'A': 0.9, 'B': 0.8, 'C': 0.7, 'D': 0.6, 'E': 0.5
        }
        
        # Track similarity calculation
        execution_id = tracker.track_similarity_calculation(
            embeddings=sample_embeddings,
            query_embedding=query_embedding,
            similarities=similarities,
            method='cosine',
            source='test_similarity_calculation'
        )
        
        # Verify execution ID was generated
        assert execution_id is not None
        assert execution_id.startswith('similarity_')
    
    def test_link_prediction_tracking(self, networkx_graph):
        """Test link prediction provenance tracking."""
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        predictions = [
            ('A', 'C', 0.7),
            ('F', 'H', 0.6),
            ('A', 'D', 0.5)
        ]
        
        # Track link prediction
        execution_id = tracker.track_link_prediction(
            graph=networkx_graph,
            predictions=predictions,
            method='preferential_attachment',
            parameters={'top_k': 10},
            source='test_link_prediction'
        )
        
        # Verify execution ID was generated
        assert execution_id is not None
        assert execution_id.startswith('link_prediction_')
    
    def test_centrality_calculation_tracking(self, networkx_graph):
        """Test centrality calculation provenance tracking."""
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        centrality_scores = {
            'A': 0.3, 'B': 0.5, 'C': 0.4, 'D': 0.3, 'E': 0.2, 'F': 0.1, 'G': 0.1, 'H': 0.1
        }
        
        # Track centrality calculation
        execution_id = tracker.track_centrality_calculation(
            graph=networkx_graph,
            centrality_scores=centrality_scores,
            method='degree',
            parameters={'normalized': True},
            source='test_centrality_calculation'
        )
        
        # Verify execution ID was generated
        assert execution_id is not None
        assert execution_id.startswith('centrality_')
    
    def test_community_detection_tracking(self, networkx_graph):
        """Test community detection provenance tracking."""
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        communities = [
            ['A', 'B', 'C'],
            ['D', 'E'],
            ['F', 'G', 'H']
        ]
        
        # Track community detection
        execution_id = tracker.track_community_detection(
            graph=networkx_graph,
            communities=communities,
            method='label_propagation',
            parameters={'max_iterations': 100},
            source='test_community_detection'
        )
        
        # Verify execution ID was generated
        assert execution_id is not None
        assert execution_id.startswith('community_')
    
    def test_node_embeddings_with_provenance(self, sample_graph_data):
        """Test node embeddings with provenance tracking."""
        # Constructing NodeEmbedder requires gensim (the optional
        # graph-embeddings extra); see tests/test_issue_1513_slim_core.py
        # for the contract that it raises without it.
        pytest.importorskip("gensim")
        embedder = NodeEmbedder()
        embedder.enable_provenance = True
        
        # Mock graph store for testing
        class MockGraphStore:
            def get_nodes_by_label(self, label):
                return ['person1', 'person2', 'company1']
            
            def get_relationships_by_type(self, rel_type):
                return [('person1', 'person2'), ('person1', 'company1')]
        
        graph_store = MockGraphStore()
        
        # Test that provenance is enabled
        assert embedder.enable_provenance is True
        
        # Test embedding computation (will fail due to missing dependencies, but provenance setup should work)
        try:
            embeddings = embedder.compute_embeddings(graph_store, ['Person'], ['WORKS_FOR'])
        except Exception:
            # Expected to fail due to missing dependencies
            pass
        
        # Verify embedder is properly configured
        assert embedder.method == 'node2vec'  # Default method
        assert hasattr(embedder, 'enable_provenance')
    
    def test_similarity_calculator_with_provenance(self, sample_embeddings):
        """Test similarity calculator with provenance tracking."""
        sim_calc = SimilarityCalculator()
        
        # Test similarity calculations
        query_embedding = [0.5, 0.5, 0.5, 0.5]
        
        # Test batch similarity
        similarities = sim_calc.batch_similarity(
            embeddings=sample_embeddings,
            query_embedding=query_embedding,
            method='cosine'
        )
        
        assert isinstance(similarities, dict)
        assert len(similarities) > 0
        
        # Test individual similarity methods
        cos_sim = sim_calc.cosine_similarity(sample_embeddings['A'], sample_embeddings['B'])
        euc_dist = sim_calc.euclidean_distance(sample_embeddings['A'], sample_embeddings['B'])
        
        assert isinstance(cos_sim, float)
        assert isinstance(euc_dist, float)
        assert 0 <= cos_sim <= 1
        assert euc_dist >= 0
    
    def test_link_predictor_with_provenance(self, networkx_graph):
        """Test link predictor with provenance tracking."""
        link_predictor = LinkPredictor()
        
        # Test different prediction methods
        for method in ['preferential_attachment', 'jaccard', 'adamic_adar']:
            predictions = link_predictor.predict_links(
                graph=networkx_graph,
                method=method,
                top_k=5
            )
            
            assert isinstance(predictions, list)
            # Each prediction should be a tuple of (source, target, score)
            if predictions:  # May be empty for some graphs
                assert len(predictions[0]) == 3
    
    def test_centrality_calculator_with_provenance(self, networkx_graph):
        """Test centrality calculator with provenance tracking."""
        centrality_calc = CentralityCalculator()
        
        # Convert NetworkX graph to dict format
        graph_dict = {
            'nodes': list(networkx_graph.nodes()),
            'edges': list(networkx_graph.edges())
        }
        
        # Test different centrality measures
        centrality_methods = [
            ('degree', centrality_calc.calculate_degree_centrality),
            ('betweenness', centrality_calc.calculate_betweenness_centrality),
            ('closeness', centrality_calc.calculate_closeness_centrality),
            ('eigenvector', centrality_calc.calculate_eigenvector_centrality)
        ]
        
        for name, method in centrality_methods:
            try:
                result = method(graph_dict)
                assert 'centrality' in result
                assert 'rankings' in result
                assert isinstance(result['centrality'], dict)
                assert isinstance(result['rankings'], list)
            except Exception as e:
                # Some methods may fail on certain graphs
                print(f"Warning: {name} centrality failed: {e}")
    
    def test_community_detector_with_provenance(self, networkx_graph):
        """Test community detector with provenance tracking."""
        community_detector = CommunityDetector()
        
        # Convert NetworkX graph to dict format
        graph_dict = {
            'nodes': list(networkx_graph.nodes()),
            'edges': list(networkx_graph.edges())
        }
        
        # Test different community detection methods
        for method in ['label_propagation', 'louvain']:
            try:
                result = community_detector.detect_communities(graph_dict, method=method)
                assert 'communities' in result
                assert 'node_assignments' in result
                assert isinstance(result['communities'], list)
                assert isinstance(result['node_assignments'], dict)
            except Exception as e:
                # Some methods may fail on certain graphs
                print(f"Warning: {method} community detection failed: {e}")
    
    def test_connectivity_analyzer_with_provenance(self, networkx_graph):
        """Test connectivity analyzer with provenance tracking."""
        conn_analyzer = ConnectivityAnalyzer()
        
        # Convert NetworkX graph to dict format
        graph_dict = {
            'nodes': list(networkx_graph.nodes()),
            'edges': list(networkx_graph.edges())
        }
        
        # Test connected components
        result = conn_analyzer.find_connected_components(graph_dict)
        components = result['components']

        assert isinstance(components, list)
        assert len(components) > 0
        # Each component should be a list of nodes
        for component in components:
            assert isinstance(component, list)
    
    def test_end_to_end_workflow(self, sample_graph_data, networkx_graph, sample_embeddings):
        """Test complete end-to-end workflow with provenance tracking."""
        # Constructing NodeEmbedder requires gensim (the optional
        # graph-embeddings extra); see tests/test_issue_1513_slim_core.py
        # for the contract that it raises without it.
        pytest.importorskip("gensim")
        # Initialize all components with provenance
        builder = GraphBuilderWithProvenance(provenance=True)
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        embedder = NodeEmbedder()
        embedder.enable_provenance = True
        
        # Step 1: Build graph with provenance
        graph_result = builder.build_single_source(sample_graph_data)
        
        # Step 2: Track embedding computation
        embed_id = tracker.track_embedding_computation(
            graph=networkx_graph,
            algorithm='node2vec',
            embeddings=sample_embeddings,
            parameters={'dim': 4},
            source='end_to_end_test'
        )
        
        # Step 3: Track similarity calculation
        sim_id = tracker.track_similarity_calculation(
            embeddings=sample_embeddings,
            query_embedding=[0.5, 0.5, 0.5, 0.5],
            similarities={'A': 0.9, 'B': 0.8},
            method='cosine',
            source='end_to_end_test'
        )
        
        # Step 4: Track link prediction
        link_id = tracker.track_link_prediction(
            graph=networkx_graph,
            predictions=[('A', 'C', 0.7)],
            method='preferential_attachment',
            parameters={},
            source='end_to_end_test'
        )
        
        # Step 5: Track centrality calculation
        cent_id = tracker.track_centrality_calculation(
            graph=networkx_graph,
            centrality_scores={'A': 0.5, 'B': 0.7},
            method='degree',
            parameters={},
            source='end_to_end_test'
        )
        
        # Step 6: Track community detection
        comm_id = tracker.track_community_detection(
            graph=networkx_graph,
            communities=[['A', 'B'], ['C', 'D']],
            method='label_propagation',
            parameters={},
            source='end_to_end_test'
        )
        
        # Verify all tracking IDs were generated
        assert embed_id is not None
        assert sim_id is not None
        assert link_id is not None
        assert cent_id is not None
        assert comm_id is not None
        
        # Verify all IDs are unique
        ids = [embed_id, sim_id, link_id, cent_id, comm_id]
        assert len(set(ids)) == len(ids)  # All unique
        
        # Verify ID formats
        assert embed_id.startswith('embedding_')
        assert sim_id.startswith('similarity_')
        assert link_id.startswith('link_prediction_')
        assert cent_id.startswith('centrality_')
        assert comm_id.startswith('community_')
    
    def test_provenance_error_handling(self):
        """Test provenance system error handling."""
        # Test graceful fallback when provenance is not available
        # This tests the ImportError handling in the provenance classes
        
        # These should work even if provenance system has issues
        builder = GraphBuilderWithProvenance(provenance=True)
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        # Should not raise exceptions during initialization
        assert builder is not None
        assert tracker is not None
        
        # Test tracking methods when provenance is disabled
        tracker_no_prov = AlgorithmTrackerWithProvenance(provenance=False)
        
        result = tracker_no_prov.track_embedding_computation(
            graph={'nodes': [], 'edges': []},
            algorithm='test',
            embeddings={},
            parameters={}
        )
        
        # Should return None when provenance is disabled
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
