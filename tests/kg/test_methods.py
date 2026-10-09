"""
Test suite for enhanced KG methods module.

This module tests the convenience functions for enhanced graph algorithms
in the methods module.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from semantica.kg.methods import (
    compute_node_embeddings,
    calculate_similarity,
    predict_links,
    find_shortest_path,
    calculate_pagerank,
    detect_communities_label_propagation,
    _get_node_embedding
)


class TestComputeNodeEmbeddings:
    """Test cases for compute_node_embeddings function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph_store = Mock()
        self.mock_graph_store.get_nodes_by_label.return_value = ["node1", "node2", "node3"]
    
    @patch('semantica.kg.methods.NodeEmbedder')
    def test_compute_node_embeddings_default(self, mock_embedder_class):
        """Test compute_node_embeddings with default parameters."""
        mock_embedder = Mock()
        mock_embedder.compute_embeddings.return_value = {"node1": [0.1, 0.2]}
        mock_embedder_class.return_value = mock_embedder
        
        result = compute_node_embeddings(self.mock_graph_store)
        
        mock_embedder_class.assert_called_once_with(method="node2vec")
        mock_embedder.compute_embeddings.assert_called_once()
        assert result == {"node1": [0.1, 0.2]}
    
    @patch('semantica.kg.methods.NodeEmbedder')
    def test_compute_node_embeddings_custom_params(self, mock_embedder_class):
        """Test compute_node_embeddings with custom parameters."""
        mock_embedder = Mock()
        mock_embedder.compute_embeddings.return_value = {"node1": [0.1, 0.2]}
        mock_embedder_class.return_value = mock_embedder
        
        result = compute_node_embeddings(
            self.mock_graph_store,
            method="node2vec",
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            embedding_dimension=64
        )
        
        mock_embedder_class.assert_called_once_with(method="node2vec", embedding_dimension=64)
        mock_embedder.compute_embeddings.assert_called_once_with(
            graph_store=self.mock_graph_store,
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            embedding_dimension=64
        )
        assert result == {"node1": [0.1, 0.2]}
    
    @patch('semantica.kg.methods.NodeEmbedder')
    def test_compute_node_embeddings_error(self, mock_embedder_class):
        """Test compute_node_embeddings error handling."""
        mock_embedder = Mock()
        mock_embedder.compute_embeddings.side_effect = Exception("Test error")
        mock_embedder_class.return_value = mock_embedder
        
        with pytest.raises(Exception, match="Test error"):
            compute_node_embeddings(self.mock_graph_store)


class TestCalculateSimilarity:
    """Test cases for calculate_similarity function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph_store = Mock()
        self.mock_graph_store.get_node_property.return_value = [0.1, 0.2, 0.3]
    
    @patch('semantica.kg.methods.SimilarityCalculator')
    def test_calculate_similarity_cosine(self, mock_calculator_class):
        """Test calculate_similarity with cosine method."""
        mock_calculator = Mock()
        mock_calculator.cosine_similarity.return_value = 0.85
        mock_calculator_class.return_value = mock_calculator
        
        result = calculate_similarity(
            self.mock_graph_store,
            "node1",
            "node2",
            method="cosine"
        )
        
        mock_calculator_class.assert_called_once_with(method="cosine")
        mock_calculator.cosine_similarity.assert_called_once()
        assert result == 0.85
    
    @patch('semantica.kg.methods.SimilarityCalculator')
    def test_calculate_similarity_euclidean(self, mock_calculator_class):
        """Test calculate_similarity with euclidean method."""
        mock_calculator = Mock()
        mock_calculator.euclidean_distance.return_value = 0.15
        mock_calculator_class.return_value = mock_calculator
        
        result = calculate_similarity(
            self.mock_graph_store,
            "node1",
            "node2",
            method="euclidean"
        )
        
        mock_calculator.euclidean_distance.assert_called_once()
        assert result == 0.15
    
    @patch('semantica.kg.methods.SimilarityCalculator')
    def test_calculate_similarity_manhattan(self, mock_calculator_class):
        """Test calculate_similarity with manhattan method."""
        mock_calculator = Mock()
        mock_calculator.manhattan_distance.return_value = 0.3
        mock_calculator_class.return_value = mock_calculator
        
        result = calculate_similarity(
            self.mock_graph_store,
            "node1",
            "node2",
            method="manhattan"
        )
        
        mock_calculator.manhattan_distance.assert_called_once()
        assert result == 0.3
    
    @patch('semantica.kg.methods.SimilarityCalculator')
    def test_calculate_similarity_correlation(self, mock_calculator_class):
        """Test calculate_similarity with correlation method."""
        mock_calculator = Mock()
        mock_calculator.correlation_similarity.return_value = 0.92
        mock_calculator_class.return_value = mock_calculator
        
        result = calculate_similarity(
            self.mock_graph_store,
            "node1",
            "node2",
            method="correlation"
        )
        
        mock_calculator.correlation_similarity.assert_called_once()
        assert result == 0.92
    
    @patch('semantica.kg.methods.SimilarityCalculator')
    def test_calculate_similarity_invalid_method(self, mock_calculator_class):
        """Test calculate_similarity with invalid method."""
        mock_calculator = Mock()
        mock_calculator_class.return_value = mock_calculator
        
        with pytest.raises(ValueError, match="Unsupported similarity method"):
            calculate_similarity(
                self.mock_graph_store,
                "node1",
                "node2",
                method="invalid_method"
            )
    
    @patch('semantica.kg.methods.SimilarityCalculator')
    def test_calculate_similarity_missing_embeddings(self, mock_calculator_class):
        """Test calculate_similarity with missing embeddings."""
        mock_calculator = Mock()
        mock_calculator_class.return_value = mock_calculator
        
        # Mock missing embedding for node2
        def mock_get_embedding(graph_store, node_id, property_name):
            if node_id == "node1":
                return [0.1, 0.2]
            else:
                return None
        
        with patch('semantica.kg.methods._get_node_embedding', side_effect=mock_get_embedding):
            with pytest.raises(ValueError, match="One or both nodes not found"):
                calculate_similarity(self.mock_graph_store, "node1", "node2")


class TestPredictLinks:
    """Test cases for predict_links function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph_store = Mock()
        self.mock_graph_store.get_nodes_by_label.return_value = ["node1", "node2", "node3"]
    
    @patch('semantica.kg.methods.LinkPredictor')
    def test_predict_links_default(self, mock_predictor_class):
        """Test predict_links with default parameters."""
        mock_predictor = Mock()
        mock_predictor.predict_links.return_value = [("node1", "node2", 0.85)]
        mock_predictor_class.return_value = mock_predictor
        
        result = predict_links(self.mock_graph_store)
        
        mock_predictor_class.assert_called_once_with(method="preferential_attachment")
        mock_predictor.predict_links.assert_called_once()
        assert result == [("node1", "node2", 0.85)]
    
    @patch('semantica.kg.methods.LinkPredictor')
    def test_predict_links_custom_params(self, mock_predictor_class):
        """Test predict_links with custom parameters."""
        mock_predictor = Mock()
        mock_predictor.predict_links.return_value = [("node1", "node2", 0.85)]
        mock_predictor_class.return_value = mock_predictor
        
        result = predict_links(
            self.mock_graph_store,
            method="common_neighbors",
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            top_k=10
        )
        
        mock_predictor_class.assert_called_once_with(method="common_neighbors")
        mock_predictor.predict_links.assert_called_once_with(
            graph_store=self.mock_graph_store,
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            top_k=10
        )
        assert result == [("node1", "node2", 0.85)]
    
    @patch('semantica.kg.methods.LinkPredictor')
    def test_predict_links_error(self, mock_predictor_class):
        """Test predict_links error handling."""
        mock_predictor = Mock()
        mock_predictor.predict_links.side_effect = Exception("Test error")
        mock_predictor_class.return_value = mock_predictor
        
        with pytest.raises(Exception, match="Test error"):
            predict_links(self.mock_graph_store)


class TestFindShortestPath:
    """Test cases for find_shortest_path function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph = Mock()
        self.mock_graph.nodes.return_value = ["A", "B", "C", "D"]
        self.mock_graph.has_node.return_value = True
    
    @patch('semantica.kg.methods.PathFinder')
    def test_find_shortest_path_dijkstra(self, mock_finder_class):
        """Test find_shortest_path with dijkstra method."""
        mock_finder = Mock()
        mock_finder.dijkstra_shortest_path.return_value = ["A", "B", "C", "D"]
        mock_finder_class.return_value = mock_finder
        
        result = find_shortest_path(
            self.mock_graph,
            "A",
            "D",
            method="dijkstra"
        )
        
        mock_finder_class.assert_called_once()
        mock_finder.dijkstra_shortest_path.assert_called_once_with(
            self.mock_graph, "A", "D"
        )
        assert result == ["A", "B", "C", "D"]
    
    @patch('semantica.kg.methods.PathFinder')
    def test_find_shortest_path_astar(self, mock_finder_class):
        """Test find_shortest_path with astar method."""
        mock_finder = Mock()
        mock_finder.a_star_search.return_value = ["A", "C", "D"]
        mock_finder_class.return_value = mock_finder
        
        result = find_shortest_path(
            self.mock_graph,
            "A",
            "D",
            method="astar"
        )
        
        mock_finder.a_star_search.assert_called_once()
        assert result == ["A", "C", "D"]
    
    @patch('semantica.kg.methods.PathFinder')
    def test_find_shortest_path_bfs(self, mock_finder_class):
        """Test find_shortest_path with bfs method."""
        mock_finder = Mock()
        mock_finder.bfs_shortest_path.return_value = ["A", "D"]
        mock_finder_class.return_value = mock_finder
        
        result = find_shortest_path(
            self.mock_graph,
            "A",
            "D",
            method="bfs"
        )
        
        mock_finder.bfs_shortest_path.assert_called_once()
        assert result == ["A", "D"]
    
    @patch('semantica.kg.methods.PathFinder')
    def test_find_shortest_path_invalid_method(self, mock_finder_class):
        """Test find_shortest_path with invalid method."""
        mock_finder = Mock()
        mock_finder_class.return_value = mock_finder
        
        with pytest.raises(ValueError, match="Unsupported path finding method"):
            find_shortest_path(
                self.mock_graph,
                "A",
                "D",
                method="invalid_method"
            )
    
    @patch('semantica.kg.methods.PathFinder')
    def test_find_shortest_path_astar_default_heuristic(self, mock_finder_class):
        """Test find_shortest_path with astar and default heuristic."""
        mock_finder = Mock()
        mock_finder.a_star_search.return_value = ["A", "B", "D"]
        mock_finder_class.return_value = mock_finder
        
        result = find_shortest_path(
            self.mock_graph,
            "A",
            "D",
            method="astar"
        )
        
        # Should call a_star_search with some heuristic function
        mock_finder.a_star_search.assert_called_once()
        assert result == ["A", "B", "D"]


class TestCalculatePageRank:
    """Test cases for calculate_pagerank function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph = Mock()
        self.mock_graph.nodes.return_value = ["A", "B", "C", "D"]
    
    @patch('semantica.kg.methods.CentralityCalculator')
    def test_calculate_pagerank_default(self, mock_calculator_class):
        """Test calculate_pagerank with default parameters."""
        mock_calculator = Mock()
        mock_calculator.calculate_pagerank.return_value = {
            "centrality": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
            "rankings": [("A", 0.25), ("B", 0.25), ("C", 0.25), ("D", 0.25)],
        }
        mock_calculator_class.return_value = mock_calculator
        
        result = calculate_pagerank(self.mock_graph)
        
        mock_calculator_class.assert_called_once()
        mock_calculator.calculate_pagerank.assert_called_once()
        assert result == {
            "centrality": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
            "rankings": [("A", 0.25), ("B", 0.25), ("C", 0.25), ("D", 0.25)],
        }
    
    @patch('semantica.kg.methods.CentralityCalculator')
    def test_calculate_pagerank_custom_params(self, mock_calculator_class):
        """Test calculate_pagerank with custom parameters."""
        mock_calculator = Mock()
        mock_calculator.calculate_pagerank.return_value = {
            "centrality": {"A": 0.4, "B": 0.3, "C": 0.2, "D": 0.1},
            "rankings": [("A", 0.4), ("B", 0.3), ("C", 0.2), ("D", 0.1)],
        }
        mock_calculator_class.return_value = mock_calculator
        
        result = calculate_pagerank(
            self.mock_graph,
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            max_iterations=30,
            damping_factor=0.9
        )
        
        mock_calculator.calculate_pagerank.assert_called_once_with(
            graph=self.mock_graph,
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            max_iterations=30,
            damping_factor=0.9
        )
        assert result == {
            "centrality": {"A": 0.4, "B": 0.3, "C": 0.2, "D": 0.1},
            "rankings": [("A", 0.4), ("B", 0.3), ("C", 0.2), ("D", 0.1)],
        }
    
    @patch('semantica.kg.methods.CentralityCalculator')
    def test_calculate_pagerank_error(self, mock_calculator_class):
        """Test calculate_pagerank error handling."""
        mock_calculator = Mock()
        mock_calculator.calculate_pagerank.side_effect = Exception("Test error")
        mock_calculator_class.return_value = mock_calculator
        
        with pytest.raises(Exception, match="Test error"):
            calculate_pagerank(self.mock_graph)


class TestDetectCommunitiesLabelPropagation:
    """Test cases for detect_communities_label_propagation function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph = Mock()
        self.mock_graph.nodes.return_value = ["A", "B", "C", "D"]
    
    @patch('semantica.kg.methods.CommunityDetector')
    def test_detect_communities_default(self, mock_detector_class):
        """Test detect_communities_label_propagation with default parameters."""
        mock_detector = Mock()
        mock_detector.detect_communities_label_propagation.return_value = {
            "communities": [["A", "B"], ["C", "D"]],
            "node_assignments": {"A": 0, "B": 0, "C": 1, "D": 1},
            "algorithm": "label_propagation",
            "iterations": 15
        }
        mock_detector_class.return_value = mock_detector
        
        result = detect_communities_label_propagation(self.mock_graph)
        
        mock_detector_class.assert_called_once()
        mock_detector.detect_communities_label_propagation.assert_called_once()
        assert result["algorithm"] == "label_propagation"
        assert len(result["communities"]) == 2
    
    @patch('semantica.kg.methods.CommunityDetector')
    def test_detect_communities_custom_params(self, mock_detector_class):
        """Test detect_communities_label_propagation with custom parameters."""
        mock_detector = Mock()
        mock_detector.detect_communities_label_propagation.return_value = {
            "communities": [["A", "B", "C"], ["D"]],
            "node_assignments": {"A": 0, "B": 0, "C": 0, "D": 1},
            "algorithm": "label_propagation",
            "iterations": 25
        }
        mock_detector_class.return_value = mock_detector
        
        result = detect_communities_label_propagation(
            self.mock_graph,
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            max_iterations=50
        )
        
        mock_detector.detect_communities_label_propagation.assert_called_once_with(
            graph=self.mock_graph,
            node_labels=["Entity"],
            relationship_types=["RELATED_TO"],
            max_iterations=50
        )
        assert result["iterations"] == 25
    
    @patch('semantica.kg.methods.CommunityDetector')
    def test_detect_communities_error(self, mock_detector_class):
        """Test detect_communities_label_propagation error handling."""
        mock_detector = Mock()
        mock_detector.detect_communities_label_propagation.side_effect = Exception("Test error")
        mock_detector_class.return_value = mock_detector
        
        with pytest.raises(Exception, match="Test error"):
            detect_communities_label_propagation(self.mock_graph)


class TestGetNodeEmbedding:
    """Test cases for _get_node_embedding helper function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph_store = Mock()
    
    def test_get_node_embedding_with_get_node_property(self):
        """Test _get_node_embedding with get_node_property method."""
        self.mock_graph_store.get_node_property.return_value = [0.1, 0.2, 0.3]
        
        result = _get_node_embedding(self.mock_graph_store, "node1", "embedding")
        
        assert result == [0.1, 0.2, 0.3]
        self.mock_graph_store.get_node_property.assert_called_once_with("node1", "embedding")
    
    def test_get_node_embedding_with_get_node_attributes(self):
        """Test _get_node_embedding with get_node_attributes method."""
        self.mock_graph_store.get_node_property = None
        self.mock_graph_store.get_node_attributes.return_value = {
            "embedding": [0.1, 0.2, 0.3],
            "other": "value"
        }
        
        result = _get_node_embedding(self.mock_graph_store, "node1", "embedding")
        
        assert result == [0.1, 0.2, 0.3]
        self.mock_graph_store.get_node_attributes.assert_called_once_with("node1")
    
    def test_get_node_embedding_with_node_embeddings_attribute(self):
        """Test _get_node_embedding with _node_embeddings attribute."""
        self.mock_graph_store.get_node_property = None
        self.mock_graph_store.get_node_attributes = None
        self.mock_graph_store._node_embeddings = {
            "node1": [0.1, 0.2, 0.3],
            "node2": [0.4, 0.5, 0.6]
        }
        
        result = _get_node_embedding(self.mock_graph_store, "node1", "embedding")
        
        assert result == [0.1, 0.2, 0.3]
    
    def test_get_node_embedding_not_found(self):
        """Test _get_node_embedding when embedding is not found."""
        self.mock_graph_store.get_node_property = None
        self.mock_graph_store.get_node_attributes = None
        self.mock_graph_store._node_embeddings = {}
        
        result = _get_node_embedding(self.mock_graph_store, "node1", "embedding")
        
        assert result is None
    
    def test_get_node_embedding_missing_property(self):
        """Test _get_node_embedding when property is missing."""
        self.mock_graph_store.get_node_attributes.return_value = {
            "other": "value"
        }
        
        result = _get_node_embedding(self.mock_graph_store, "node1", "embedding")
        
        assert result is None


class TestMethodsIntegration:
    """Integration tests for enhanced KG methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph_store = Mock()
        self.mock_graph = Mock()
    
    @patch('semantica.kg.methods.NodeEmbedder')
    @patch('semantica.kg.methods.SimilarityCalculator')
    def test_embedding_similarity_pipeline(self, mock_calculator_class, mock_embedder_class):
        """Test complete embedding to similarity pipeline."""
        # Mock embedding computation
        mock_embedder = Mock()
        mock_embedder.compute_embeddings.return_value = {
            "node1": [1.0, 0.0],
            "node2": [0.0, 1.0]
        }
        mock_embedder_class.return_value = mock_embedder
        
        # Mock similarity calculation
        mock_calculator = Mock()
        mock_calculator.cosine_similarity.return_value = 0.0
        mock_calculator_class.return_value = mock_calculator
        
        # Mock graph store to return embeddings
        self.mock_graph_store._node_embeddings = {
            "node1": [1.0, 0.0],
            "node2": [0.0, 1.0]
        }
        
        # Compute embeddings
        embeddings = compute_node_embeddings(self.mock_graph_store)
        assert len(embeddings) == 2
        
        # Calculate similarity
        similarity = calculate_similarity(self.mock_graph_store, "node1", "node2")
        assert similarity == 0.0
    
    @patch('semantica.kg.methods.LinkPredictor')
    @patch('semantica.kg.methods.PathFinder')
    def test_link_prediction_path_finding_pipeline(self, mock_finder_class, mock_predictor_class):
        """Test link prediction to path finding pipeline."""
        # Mock link prediction
        mock_predictor = Mock()
        mock_predictor.predict_links.return_value = [("A", "C", 0.8)]
        mock_predictor_class.return_value = mock_predictor
        
        # Mock path finding
        mock_finder = Mock()
        mock_finder.dijkstra_shortest_path.return_value = ["A", "B", "C"]
        mock_finder_class.return_value = mock_finder
        
        # Predict links
        links = predict_links(self.mock_graph_store, top_k=5)
        assert len(links) == 1
        
        # Find path for predicted link
        if links:
            source, target, score = links[0]
            path = find_shortest_path(self.mock_graph, source, target)
            assert path == ["A", "B", "C"]
    
    @patch('semantica.kg.methods.CentralityCalculator')
    @patch('semantica.kg.methods.CommunityDetector')
    def test_centrality_community_pipeline(self, mock_detector_class, mock_calculator_class):
        """Test centrality to community detection pipeline."""
        # Mock PageRank calculation
        mock_calculator = Mock()
        mock_calculator.calculate_pagerank.return_value = {
            "centrality": {"A": 0.4, "B": 0.3, "C": 0.2, "D": 0.1},
            "rankings": [("A", 0.4), ("B", 0.3), ("C", 0.2), ("D", 0.1)],
        }
        mock_calculator_class.return_value = mock_calculator
        
        # Mock community detection
        mock_detector = Mock()
        mock_detector.detect_communities_label_propagation.return_value = {
            "communities": [["A", "B"], ["C", "D"]],
            "node_assignments": {"A": 0, "B": 0, "C": 1, "D": 1}
        }
        mock_detector_class.return_value = mock_detector
        
        # Calculate PageRank
        pagerank_result = calculate_pagerank(self.mock_graph)
        assert len(pagerank_result["centrality"]) == 4
        
        # Detect communities
        communities = detect_communities_label_propagation(self.mock_graph)
        assert len(communities["communities"]) == 2


if __name__ == "__main__":
    pytest.main([__file__])
