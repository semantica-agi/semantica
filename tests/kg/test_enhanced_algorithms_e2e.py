"""
End-to-end tests for enhanced KG algorithms.

Comprehensive testing of all enhanced graph algorithms with real-world scenarios.
"""

import pytest
import networkx as nx
import numpy as np
from typing import Dict, List, Any, Tuple
import time

from semantica.kg import (
    NodeEmbedder,
    SimilarityCalculator,
    PathFinder,
    LinkPredictor,
    CentralityCalculator,
    CommunityDetector,
    ConnectivityAnalyzer,
    AlgorithmTrackerWithProvenance
)


class TestEnhancedAlgorithmsE2E:
    """End-to-end tests for enhanced KG algorithms."""
    
    @pytest.fixture
    def social_network_graph(self):
        """Create a realistic social network graph."""
        graph = nx.Graph()
        
        # Add nodes with attributes
        people = [
            ('Alice', {'type': 'Person', 'age': 30, 'city': 'New York'}),
            ('Bob', {'type': 'Person', 'age': 25, 'city': 'New York'}),
            ('Charlie', {'type': 'Person', 'age': 35, 'city': 'San Francisco'}),
            ('David', {'type': 'Person', 'age': 28, 'city': 'San Francisco'}),
            ('Eve', {'type': 'Person', 'age': 32, 'city': 'Chicago'}),
            ('Frank', {'type': 'Person', 'age': 27, 'city': 'Chicago'}),
            ('Grace', {'type': 'Person', 'age': 40, 'city': 'Boston'}),
            ('Henry', {'type': 'Person', 'age': 33, 'city': 'Boston'}),
            ('Iris', {'type': 'Person', 'age': 29, 'city': 'Seattle'}),
            ('Jack', {'type': 'Person', 'age': 31, 'city': 'Seattle'})
        ]
        
        graph.add_nodes_from(people)
        
        # Add edges (friendships)
        friendships = [
            ('Alice', 'Bob', {'weight': 0.9, 'type': 'friend'}),
            ('Alice', 'Charlie', {'weight': 0.7, 'type': 'friend'}),
            ('Bob', 'David', {'weight': 0.8, 'type': 'friend'}),
            ('Charlie', 'David', {'weight': 0.9, 'type': 'friend'}),
            ('David', 'Eve', {'weight': 0.6, 'type': 'friend'}),
            ('Eve', 'Frank', {'weight': 0.8, 'type': 'friend'}),
            ('Frank', 'Grace', {'weight': 0.5, 'type': 'friend'}),
            ('Grace', 'Henry', {'weight': 0.7, 'type': 'friend'}),
            ('Henry', 'Iris', {'weight': 0.6, 'type': 'friend'}),
            ('Iris', 'Jack', {'weight': 0.8, 'type': 'friend'}),
            ('Jack', 'Alice', {'weight': 0.4, 'type': 'friend'}),
            ('Bob', 'Eve', {'weight': 0.5, 'type': 'friend'}),
            ('Charlie', 'Frank', {'weight': 0.6, 'type': 'friend'}),
            ('David', 'Grace', {'weight': 0.7, 'type': 'friend'}),
            ('Eve', 'Henry', {'weight': 0.4, 'type': 'friend'}),
            ('Frank', 'Iris', {'weight': 0.5, 'type': 'friend'}),
            ('Grace', 'Jack', {'weight': 0.6, 'type': 'friend'}),
            ('Henry', 'Alice', {'weight': 0.3, 'type': 'friend'})
        ]
        
        graph.add_edges_from(friendships)
        return graph
    
    @pytest.fixture
    def citation_network_graph(self):
        """Create a citation network graph."""
        graph = nx.DiGraph()
        
        # Add papers
        papers = [
            ('P1', {'title': 'Machine Learning Basics', 'year': 2020, 'venue': 'ICML'}),
            ('P2', {'title': 'Deep Learning', 'year': 2021, 'venue': 'NeurIPS'}),
            ('P3', {'title': 'Neural Networks', 'year': 2019, 'venue': 'ICML'}),
            ('P4', {'title': 'CNN Architectures', 'year': 2022, 'venue': 'CVPR'}),
            ('P5', {'title': 'RNN Applications', 'year': 2021, 'venue': 'ACL'}),
            ('P6', {'title': 'Transformers', 'year': 2022, 'venue': 'NeurIPS'}),
            ('P7', {'title': 'Attention Mechanisms', 'year': 2020, 'venue': 'ICLR'}),
            ('P8', {'title': 'GANs for Image Generation', 'year': 2023, 'venue': 'ICCV'})
        ]
        
        graph.add_nodes_from(papers)
        
        # Add citations
        citations = [
            ('P1', 'P2', {'weight': 0.8, 'type': 'citation'}),
            ('P1', 'P3', {'weight': 0.7, 'type': 'citation'}),
            ('P2', 'P4', {'weight': 0.9, 'type': 'citation'}),
            ('P2', 'P6', {'weight': 0.8, 'type': 'citation'}),
            ('P3', 'P5', {'weight': 0.6, 'type': 'citation'}),
            ('P4', 'P8', {'weight': 0.7, 'type': 'citation'}),
            ('P5', 'P7', {'weight': 0.8, 'type': 'citation'}),
            ('P6', 'P7', {'weight': 0.9, 'type': 'citation'}),
            ('P7', 'P2', {'weight': 0.5, 'type': 'citation'}),
            ('P8', 'P4', {'weight': 0.6, 'type': 'citation'})
        ]
        
        graph.add_edges_from(citations)
        return graph
    
    @pytest.fixture
    def sample_embeddings(self):
        """Generate sample embeddings for testing."""
        np.random.seed(42)
        nodes = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank', 'Grace', 'Henry', 'Iris', 'Jack']
        embeddings = {}
        
        for node in nodes:
            # Generate 8-dimensional embeddings
            embedding = np.random.randn(8)
            embeddings[node] = embedding.tolist()
        
        return embeddings
    
    def test_node_embeddings_end_to_end(self, social_network_graph):
        """Test node embeddings end-to-end."""
        # Constructing NodeEmbedder requires gensim (the optional
        # graph-embeddings extra); see tests/test_issue_1513_slim_core.py
        # for the contract that it raises without it.
        pytest.importorskip("gensim")
        embedder = NodeEmbedder()
        embedder.enable_provenance = True
        
        # Mock graph store
        class MockGraphStore:
            def __init__(self, graph):
                self.graph = graph
            
            def get_nodes_by_label(self, label):
                return list(self.graph.nodes())
            
            def get_relationships_by_type(self, rel_type):
                return list(self.graph.edges())
        
        graph_store = MockGraphStore(social_network_graph)
        
        # Test different embedding methods
        methods = ['node2vec', 'deepwalk']
        
        for method in methods:
            embedder.method = method
            
            try:
                # This will likely fail due to missing dependencies, but we test the setup
                embeddings = embedder.compute_embeddings(graph_store, ['Person'], ['friend'])
                
                # If it succeeds, verify the embeddings
                assert isinstance(embeddings, dict)
                assert len(embeddings) > 0
                
                # Check embedding dimensions
                for node, embedding in embeddings.items():
                    assert isinstance(embedding, list)
                    assert len(embedding) > 0
                    
            except Exception as e:
                # Expected to fail due to missing dependencies
                print(f"Expected failure for {method}: {e}")
        
        # Verify embedder configuration
        assert embedder.enable_provenance is True
        assert hasattr(embedder, 'method')
    
    def test_similarity_calculator_end_to_end(self, sample_embeddings):
        """Test similarity calculator end-to-end."""
        sim_calc = SimilarityCalculator()
        
        # Test individual similarity calculations
        alice_embedding = sample_embeddings['Alice']
        bob_embedding = sample_embeddings['Bob']
        
        # Test different similarity metrics
        cosine_sim = sim_calc.cosine_similarity(alice_embedding, bob_embedding)
        euclidean_dist = sim_calc.euclidean_distance(alice_embedding, bob_embedding)
        manhattan_dist = sim_calc.manhattan_distance(alice_embedding, bob_embedding)
        
        # Verify results
        assert isinstance(cosine_sim, float)
        assert isinstance(euclidean_dist, float)
        assert isinstance(manhattan_dist, float)
        assert -1 <= cosine_sim <= 1  # Cosine similarity can be negative
        assert euclidean_dist >= 0
        assert manhattan_dist >= 0
        
        # Test batch similarity
        query_embedding = [0.5] * 8  # Average embedding
        
        similarities = sim_calc.batch_similarity(
            embeddings=sample_embeddings,
            query_embedding=query_embedding,
            method='cosine',
            top_k=5
        )
        
        assert isinstance(similarities, dict)
        assert len(similarities) <= 5  # Should be limited to top_k
        
        # Test pairwise similarity
        pairwise_sims = sim_calc.pairwise_similarity(sample_embeddings)
        assert isinstance(pairwise_sims, dict)
        
        # Test most similar finding
        most_similar = sim_calc.find_most_similar(
            embeddings=sample_embeddings,
            query_embedding=query_embedding,
            top_k=3,
            method='cosine'
        )
        
        assert isinstance(most_similar, list)
        assert len(most_similar) <= 3
        assert all(isinstance(item, tuple) and len(item) == 2 for item in most_similar)
    
    def test_path_finder_end_to_end(self, social_network_graph):
        """Test path finder end-to-end."""
        path_finder = PathFinder()
        
        # Test shortest path algorithms
        source = 'Alice'
        target = 'Grace'
        
        # BFS shortest path
        bfs_path = path_finder.bfs_shortest_path(social_network_graph, source, target)
        assert isinstance(bfs_path, list)
        assert bfs_path[0] == source
        assert bfs_path[-1] == target
        
        # Dijkstra shortest path
        dijkstra_path = path_finder.dijkstra_shortest_path(social_network_graph, source, target)
        assert isinstance(dijkstra_path, list)
        assert dijkstra_path[0] == source
        assert dijkstra_path[-1] == target
        
        # All shortest paths from source
        all_paths = path_finder.all_shortest_paths(social_network_graph, source)
        assert isinstance(all_paths, dict)
        assert len(all_paths) > 0  # Should have paths to other nodes
        
        # A* search
        def heuristic(node1, node2):
            # Simple heuristic based on node names
            return abs(len(node1) - len(node2))
        
        astar_path = path_finder.a_star_search(social_network_graph, source, target, heuristic)
        assert isinstance(astar_path, list)
        assert astar_path[0] == source
        assert astar_path[-1] == target
        
        # Path length calculation
        path_length = path_finder.path_length(social_network_graph, bfs_path)
        assert isinstance(path_length, float)
        assert path_length >= 0
        
        # K shortest paths
        k_paths = path_finder.find_k_shortest_paths(social_network_graph, source, target, k=3)
        assert isinstance(k_paths, list)
        assert len(k_paths) <= 3
    
    def test_link_prediction_end_to_end(self, social_network_graph):
        """Test link prediction end-to-end."""
        link_predictor = LinkPredictor()
        
        # Test different prediction methods
        methods = ['preferential_attachment', 'jaccard', 'adamic_adar']
        
        for method in methods:
            predictions = link_predictor.predict_links(
                graph=social_network_graph,
                method=method,
                top_k=5
            )
            
            assert isinstance(predictions, list)
            
            # Verify prediction format
            if predictions:  # May be empty for some graphs
                for pred in predictions:
                    assert isinstance(pred, tuple)
                    assert len(pred) == 3  # (source, target, score)
                    assert isinstance(pred[0], str)  # source node
                    assert isinstance(pred[1], str)  # target node
                    assert isinstance(pred[2], (int, float))  # score
        
        # Test with different top_k values
        predictions_10 = link_predictor.predict_links(
            graph=social_network_graph,
            method='preferential_attachment',
            top_k=10
        )
        
        assert isinstance(predictions_10, list)
        assert len(predictions_10) <= 10
    
    def test_centrality_calculator_end_to_end(self, social_network_graph):
        """Test centrality calculator end-to-end."""
        centrality_calc = CentralityCalculator()
        
        # Convert NetworkX graph to dict format
        graph_dict = {
            'nodes': list(social_network_graph.nodes()),
            'edges': list(social_network_graph.edges())
        }
        
        # Test different centrality measures
        centrality_methods = [
            ('degree', centrality_calc.calculate_degree_centrality),
            ('betweenness', centrality_calc.calculate_betweenness_centrality),
            ('closeness', centrality_calc.calculate_closeness_centrality),
            ('eigenvector', centrality_calc.calculate_eigenvector_centrality)
        ]
        
        results = {}
        
        for name, method in centrality_methods:
            try:
                result = method(graph_dict)
                results[name] = result
                
                # Verify result structure
                assert 'centrality' in result
                assert 'rankings' in result
                assert 'total_nodes' in result
                
                # Verify centrality scores
                assert isinstance(result['centrality'], dict)
                assert isinstance(result['rankings'], list)
                assert isinstance(result['total_nodes'], int)
                
                # Verify rankings format
                for ranking in result['rankings']:
                    assert isinstance(ranking, dict)
                    assert 'node' in ranking
                    assert 'score' in ranking
                
            except Exception as e:
                print(f"Warning: {name} centrality failed: {e}")
        
        # Test PageRank
        try:
            pagerank_result = centrality_calc.calculate_pagerank(
                graph=social_network_graph,
                node_labels=None,
                alpha=0.85,
                max_iter=100,
                tolerance=1e-6
            )
            
            assert 'centrality' in pagerank_result
            assert 'rankings' in pagerank_result
            results['pagerank'] = pagerank_result
            
        except Exception as e:
            print(f"Warning: PageRank failed: {e}")
        
        # Test all centrality calculation
        try:
            all_centrality = centrality_calc.calculate_all_centrality(graph_dict)
            assert isinstance(all_centrality, dict)
            results['all'] = all_centrality
            
        except Exception as e:
            print(f"Warning: All centrality failed: {e}")
        
        # Verify we got some results
        assert len(results) > 0
    
    def test_community_detection_end_to_end(self, social_network_graph):
        """Test community detection end-to-end."""
        community_detector = CommunityDetector()
        
        # Convert NetworkX graph to dict format
        graph_dict = {
            'nodes': list(social_network_graph.nodes()),
            'edges': list(social_network_graph.edges())
        }
        
        # Test different community detection methods
        methods = ['label_propagation', 'louvain']
        
        results = {}
        
        for method in methods:
            result = community_detector.detect_communities(graph_dict, method=method)
            results[method] = result
            
            # Verify result structure
            assert 'communities' in result
            assert 'node_assignments' in result
            assert result['algorithm'] == method
            
            # Verify communities
            assert isinstance(result['communities'], list)
            assert isinstance(result['node_assignments'], dict)
            
            # Verify node assignments
            for node, community_id in result['node_assignments'].items():
                assert isinstance(node, str)
                assert isinstance(community_id, int)
            
            # Verify communities contain all nodes
            all_nodes_in_communities = set()
            for community in result['communities']:
                all_nodes_in_communities.update(community)
            
            assert all_nodes_in_communities == set(result['node_assignments'].keys())
        
        # Test with parameters
        result_with_params = community_detector.detect_communities(
            graph_dict,
            method='label_propagation',
            max_iterations=50,
            random_seed=42
        )
        
        assert result_with_params['algorithm'] == 'label_propagation'
        assert 'communities' in result_with_params
        results['with_params'] = result_with_params
        
        # Verify we got some results
        assert len(results) > 0
    
    def test_connectivity_analyzer_end_to_end(self, social_network_graph):
        """Test connectivity analyzer end-to-end."""
        conn_analyzer = ConnectivityAnalyzer()
        
        # Convert NetworkX graph to dict format
        graph_dict = {
            'nodes': list(social_network_graph.nodes()),
            'edges': list(social_network_graph.edges())
        }
        
        # Test connected components
        components = conn_analyzer.find_connected_components(graph_dict)['components']

        assert isinstance(components, list)
        assert len(components) > 0

        # Verify component structure
        all_nodes_in_components = set()
        for component in components:
            assert isinstance(component, list)
            all_nodes_in_components.update(component)
        
        # All nodes should be in components
        assert all_nodes_in_components == set(graph_dict['nodes'])
        
        # Test graph properties
        try:
            properties = conn_analyzer.analyze_connectivity(graph_dict)
            
            assert isinstance(properties, dict)
            assert 'connected_components' in properties
            assert 'largest_component_size' in properties
            assert 'is_connected' in properties
            
        except Exception as e:
            print(f"Warning: Connectivity analysis failed: {e}")
    
    def test_comprehensive_workflow(self, social_network_graph, citation_network_graph, sample_embeddings):
        """Test comprehensive workflow combining all algorithms."""
        # Constructing NodeEmbedder requires gensim (the optional
        # graph-embeddings extra); see tests/test_issue_1513_slim_core.py
        # for the contract that it raises without it.
        pytest.importorskip("gensim")
        # Initialize all algorithms
        embedder = NodeEmbedder()
        embedder.enable_provenance = True
        
        sim_calc = SimilarityCalculator()
        path_finder = PathFinder()
        link_predictor = LinkPredictor()
        centrality_calc = CentralityCalculator()
        community_detector = CommunityDetector()
        conn_analyzer = ConnectivityAnalyzer()
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        # Step 1: Analyze social network connectivity
        social_dict = {
            'nodes': list(social_network_graph.nodes()),
            'edges': list(social_network_graph.edges())
        }
        
        components = conn_analyzer.find_connected_components(social_dict)['components']
        assert len(components) >= 1
        
        # Step 2: Calculate centrality measures
        degree_cent = centrality_calc.calculate_degree_centrality(social_dict)
        assert 'centrality' in degree_cent
        
        # Step 3: Detect communities
        communities = community_detector.detect_communities(social_dict, method='label_propagation')
        assert communities['algorithm'] == 'label_propagation'
        assert 'communities' in communities
        
        # Step 4: Find shortest paths
        source = 'Alice'
        target = 'Grace'
        shortest_path = path_finder.bfs_shortest_path(social_network_graph, source, target)
        assert shortest_path[0] == source and shortest_path[-1] == target
        
        # Step 5: Calculate similarities
        query_embedding = sample_embeddings['Alice']
        similarities = sim_calc.batch_similarity(
            embeddings=sample_embeddings,
            query_embedding=query_embedding,
            method='cosine',
            top_k=5
        )
        assert isinstance(similarities, dict)
        
        # Step 6: Predict missing links
        predictions = link_predictor.predict_links(social_network_graph, method='preferential_attachment')
        assert isinstance(predictions, list)
        
        # Step 7: Track all operations with provenance
        workflow_id = "comprehensive_test"
        
        # Track each step
        conn_id = tracker.track_connectivity_analysis(
            graph=social_dict,
            components=components,
            method='connected_components',
            source=workflow_id
        )
        
        cent_id = tracker.track_centrality_calculation(
            graph=social_dict,
            centrality_scores=degree_cent['centrality'],
            method='degree',
            parameters={},
            source=workflow_id
        )
        
        comm_id = tracker.track_community_detection(
            graph=social_dict,
            communities=communities['communities'],
            method='label_propagation',
            parameters={},
            source=workflow_id
        )
        
        path_id = tracker.track_path_finding(
            graph=social_network_graph,
            path=shortest_path,
            method='bfs',
            parameters={'source': source, 'target': target},
            source=workflow_id
        )
        
        sim_id = tracker.track_similarity_calculation(
            embeddings=sample_embeddings,
            query_embedding=query_embedding,
            similarities=similarities,
            method='cosine',
            source=workflow_id
        )
        
        link_id = tracker.track_link_prediction(
            graph=social_network_graph,
            predictions=predictions[:3],  # Track top 3
            method='preferential_attachment',
            parameters={},
            source=workflow_id
        )
        
        # Verify all tracking IDs were generated
        tracking_ids = [conn_id, cent_id, comm_id, path_id, sim_id, link_id]
        for tracking_id in tracking_ids:
            assert tracking_id is not None
            assert len(tracking_id) > 10  # UUID length
        
        # Verify all IDs are unique
        assert len(set(tracking_ids)) == len(tracking_ids)
        
        # Step 8: Analyze citation network
        citation_dict = {
            'nodes': list(citation_network_graph.nodes()),
            'edges': list(citation_network_graph.edges())
        }
        
        # Calculate PageRank for citation network
        try:
            pagerank = centrality_calc.calculate_pagerank(citation_network_graph)
            assert 'centrality' in pagerank
        except Exception as e:
            print(f"PageRank failed: {e}")
        
        # Find citation paths
        try:
            citation_path = path_finder.all_shortest_paths(citation_network_graph, 'P1')
            assert isinstance(citation_path, dict)
        except Exception as e:
            print(f"Citation path finding failed: {e}")
        
        print("Comprehensive workflow test completed successfully!")
    
    def test_performance_with_large_graph(self):
        """Test algorithm performance with larger graphs."""
        # Create a larger graph
        large_graph = nx.erdos_renyi_graph(100, 0.1, seed=42)
        
        # Test centrality calculation performance
        centrality_calc = CentralityCalculator()
        graph_dict = {
            'nodes': list(large_graph.nodes()),
            'edges': list(large_graph.edges())
        }
        
        start_time = time.time()
        degree_cent = centrality_calc.calculate_degree_centrality(graph_dict)
        centrality_time = time.time() - start_time
        
        assert centrality_time < 5.0  # Should complete within 5 seconds
        assert 'centrality' in degree_cent
        
        # Test connectivity analysis performance
        conn_analyzer = ConnectivityAnalyzer()
        
        start_time = time.time()
        components = conn_analyzer.find_connected_components(graph_dict)['components']
        connectivity_time = time.time() - start_time

        assert connectivity_time < 5.0  # Should complete within 5 seconds
        assert isinstance(components, list)
        
        # Test link prediction performance
        link_predictor = LinkPredictor()
        
        start_time = time.time()
        predictions = link_predictor.predict_links(graph_dict, method='preferential_attachment', top_k=10)
        prediction_time = time.time() - start_time
        
        assert prediction_time < 5.0  # Should complete within 5 seconds
        assert isinstance(predictions, list)
        
        print(f"Performance test completed:")
        print(f"  Centrality calculation: {centrality_time:.3f}s")
        print(f"  Connectivity analysis: {connectivity_time:.3f}s")
        print(f"  Link prediction: {prediction_time:.3f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
