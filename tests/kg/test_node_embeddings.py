"""
Test suite for Node Embeddings module.

This module tests the NodeEmbedder class and its Node2Vec implementation
for generating node embeddings in knowledge graphs.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from semantica.kg.node_embeddings import NodeEmbedder


@pytest.fixture(autouse=True)
def require_gensim(request):
    """Skip tests that need a working NodeEmbedder when gensim is absent.

    gensim is the optional ``graph-embeddings`` extra and
    ``NodeEmbedder.__init__`` raises ImportError without it, so these tests
    fail instead of skipping on a core install.

    Tests marked ``no_gensim`` keep running: one asserts that ImportError
    itself, and skipping it on exactly the install where it applies would
    remove the only coverage of the missing-dependency path. Same shape as
    ``require_adk`` in tests/integrations/google_adk/.
    """
    if request.node.get_closest_marker("no_gensim") is None:
        pytest.importorskip("gensim")


class TestNodeEmbedder:
    """Test cases for NodeEmbedder class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_graph_store = Mock()
        self.mock_graph_store.get_nodes_by_label.return_value = ["node1", "node2", "node3"]
        self.mock_graph_store.get_neighbors.return_value = ["node2", "node3"]
        
        # Create a simple adjacency structure
        self.adjacency = {
            "node1": ["node2", "node3"],
            "node2": ["node1", "node3"],
            "node3": ["node1", "node2"]
        }
    
    def test_init_default(self):
        """Test NodeEmbedder initialization with default parameters."""
        embedder = NodeEmbedder()
        
        assert embedder.method == "node2vec"
        assert embedder.embedding_dimension == 128
        assert embedder.walk_length == 80
        assert embedder.num_walks == 10
        assert embedder.p == 1.0
        assert embedder.q == 1.0
    
    def test_init_custom_parameters(self):
        """Test NodeEmbedder initialization with custom parameters."""
        embedder = NodeEmbedder(
            method="node2vec",
            embedding_dimension=64,
            walk_length=40,
            num_walks=5,
            p=2.0,
            q=0.5
        )
        
        assert embedder.embedding_dimension == 64
        assert embedder.walk_length == 40
        assert embedder.num_walks == 5
        assert embedder.p == 2.0
        assert embedder.q == 0.5
    
    @pytest.mark.no_gensim
    def test_init_invalid_method(self):
        """Test NodeEmbedder initialization with invalid method.

        The method check runs before the gensim check, so this needs no extra.
        """
        with pytest.raises(ValueError, match="Unsupported embedding method"):
            NodeEmbedder(method="invalid_method")
    
    @pytest.mark.no_gensim
    @patch('semantica.kg.node_embeddings.GENSIM_AVAILABLE', False)
    def test_init_gensim_unavailable(self):
        """Test NodeEmbedder initialization when gensim is unavailable."""
        with pytest.raises(ImportError, match="gensim is required for Node2Vec"):
            NodeEmbedder()
    
    def test_build_adjacency(self):
        """Test adjacency list building."""
        embedder = NodeEmbedder()
        
        # Mock graph store methods
        self.mock_graph_store.get_nodes_by_label.return_value = ["node1", "node2"]
        self.mock_graph_store.get_neighbors.side_effect = lambda node, rel_types: {
            "node1": ["node2"],
            "node2": ["node1"]
        }[node]
        
        adjacency = embedder._build_adjacency(
            self.mock_graph_store, 
            ["Entity"], 
            ["RELATED_TO"]
        )
        
        assert "node1" in adjacency
        assert "node2" in adjacency
        assert "node2" in adjacency["node1"]
        assert "node1" in adjacency["node2"]
    
    def test_generate_random_walks(self):
        """Test random walk generation."""
        embedder = NodeEmbedder(walk_length=3, num_walks=2)
        
        walks = embedder._generate_random_walks(
            self.adjacency, 
            walk_length=3, 
            num_walks=2, 
            p=1.0, 
            q=1.0
        )
        
        assert len(walks) == 6  # 3 nodes * 2 walks
        for walk in walks:
            assert len(walk) <= 3  # Walk length constraint
            assert all(node in self.adjacency for node in walk)
    
    def test_biased_random_walk(self):
        """Test biased random walk generation."""
        embedder = NodeEmbedder()
        
        walk = embedder._biased_random_walk(
            self.adjacency, 
            "node1", 
            walk_length=3, 
            p=1.0, 
            q=1.0
        )
        
        assert len(walk) <= 3
        assert walk[0] == "node1"
        assert all(node in self.adjacency for node in walk)
    
    def test_biased_sample(self):
        """Test biased sampling for next node."""
        embedder = NodeEmbedder()
        
        neighbors = ["node2", "node3"]
        probabilities = embedder._biased_sample(
            self.adjacency, 
            "node1", 
            "node1", 
            neighbors, 
            p=1.0, 
            q=1.0
        )
        
        assert probabilities in neighbors
    
    @patch('semantica.kg.node_embeddings.Word2Vec')
    def test_train_word2vec(self, mock_word2vec):
        """Test Word2Vec model training."""
        mock_model = Mock()
        mock_model.wv = {"node1": [0.1, 0.2], "node2": [0.3, 0.4]}
        mock_word2vec.return_value = mock_model
        
        embedder = NodeEmbedder()
        walks = [["node1", "node2"], ["node2", "node1"]]
        
        model = embedder._train_word2vec(walks, embedding_dimension=2)
        
        mock_word2vec.assert_called_once()
        assert model == mock_model
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        embedder = NodeEmbedder()
        
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        vec3 = np.array([1.0, 0.0])
        
        # Orthogonal vectors
        similarity = embedder._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 1e-10  # Should be approximately 0
        
        # Identical vectors
        similarity = embedder._cosine_similarity(vec1, vec3)
        assert abs(similarity - 1.0) < 1e-10  # Should be approximately 1
    
    @patch('semantica.kg.node_embeddings.Word2Vec')
    def test_compute_embeddings(self, mock_word2vec):
        """Test full embedding computation pipeline."""
        # Mock Word2Vec model
        mock_model = Mock()
        mock_model.wv = {
            "node1": [0.1, 0.2, 0.3],
            "node2": [0.4, 0.5, 0.6],
            "node3": [0.7, 0.8, 0.9]
        }
        mock_word2vec.return_value = mock_model
        
        # Mock graph store
        self.mock_graph_store.get_nodes_by_label.return_value = ["node1", "node2", "node3"]
        self.mock_graph_store.get_neighbors.side_effect = lambda node, rel_types: self.adjacency[node]
        
        embedder = NodeEmbedder(embedding_dimension=3, walk_length=2, num_walks=1)
        
        embeddings = embedder.compute_embeddings(
            self.mock_graph_store,
            ["Entity"],
            ["RELATED_TO"]
        )
        
        assert len(embeddings) == 3
        assert all(len(embed) == 3 for embed in embeddings.values())
        assert "node1" in embeddings
        assert "node2" in embeddings
        assert "node3" in embeddings
    
    def test_find_similar_nodes(self):
        """Test finding similar nodes based on embeddings."""
        embedder = NodeEmbedder()
        
        # Mock graph store with embeddings
        embeddings = {
            "node1": [1.0, 0.0, 0.0],
            "node2": [0.9, 0.1, 0.0],
            "node3": [0.0, 1.0, 0.0]
        }
        
        self.mock_graph_store._node_embeddings = embeddings
        
        similar_nodes = embedder.find_similar_nodes(
            self.mock_graph_store, 
            "node1", 
            top_k=2
        )
        
        assert len(similar_nodes) <= 2
        assert "node1" not in similar_nodes  # Should not include self
    
    def test_store_embeddings(self):
        """Test storing embeddings as node properties."""
        embedder = NodeEmbedder()
        
        embeddings = {
            "node1": [0.1, 0.2],
            "node2": [0.3, 0.4]
        }
        
        # Mock graph store with set_node_property method
        self.mock_graph_store.set_node_property = Mock()
        
        embedder.store_embeddings(
            self.mock_graph_store, 
            embeddings, 
            "test_embedding"
        )
        
        # Verify set_node_property was called for each node
        assert self.mock_graph_store.set_node_property.call_count == 2
        self.mock_graph_store.set_node_property.assert_any_call("node1", "test_embedding", [0.1, 0.2])
        self.mock_graph_store.set_node_property.assert_any_call("node2", "test_embedding", [0.3, 0.4])
    
    def test_store_embeddings_fallback(self):
        """Test storing embeddings with fallback method."""
        embedder = NodeEmbedder()
        
        embeddings = {
            "node1": [0.1, 0.2],
            "node2": [0.3, 0.4]
        }
        
        # Mock graph store without set_node_property but with add_node_attribute
        self.mock_graph_store.set_node_property = None
        self.mock_graph_store.add_node_attribute = Mock()
        
        embedder.store_embeddings(
            self.mock_graph_store, 
            embeddings, 
            "test_embedding"
        )
        
        # Verify add_node_attribute was called
        assert self.mock_graph_store.add_node_attribute.call_count == 2
    
    def test_get_node_embedding(self):
        """Test retrieving node embeddings."""
        embedder = NodeEmbedder()
        
        # Test with get_node_property method
        self.mock_graph_store.get_node_property.return_value = [0.1, 0.2]
        embedding = embedder._get_node_embedding(self.mock_graph_store, "node1", "embedding")
        assert embedding == [0.1, 0.2]
        
        # Test with _node_embeddings attribute
        self.mock_graph_store.get_node_property = None
        self.mock_graph_store._node_embeddings = {"node1": [0.3, 0.4]}
        embedding = embedder._get_node_embedding(self.mock_graph_store, "node1", "embedding")
        assert embedding == [0.3, 0.4]
        
        # Test with no embedding found
        self.mock_graph_store._node_embeddings = {}
        embedding = embedder._get_node_embedding(self.mock_graph_store, "node1", "embedding")
        assert embedding is None
    
    def test_get_all_embeddings(self):
        """Test retrieving all node embeddings."""
        embedder = NodeEmbedder()
        
        # Test with _node_embeddings attribute
        self.mock_graph_store._node_embeddings = {
            "node1": [0.1, 0.2],
            "node2": [0.3, 0.4]
        }
        embeddings = embedder._get_all_embeddings(self.mock_graph_store, "embedding")
        assert len(embeddings) == 2
        assert "node1" in embeddings
        assert "node2" in embeddings


class TestNodeEmbedderIntegration:
    """Integration tests for NodeEmbedder."""
    
    def test_end_to_end_embedding_pipeline(self):
        """Test complete embedding pipeline with mocked dependencies."""
        # This test would require actual Word2Vec or extensive mocking
        # For now, we'll test the structure and flow
        pass
    
    def test_error_handling(self):
        """Test error handling in embedding computation."""
        embedder = NodeEmbedder()
        
        # Test with empty graph
        mock_empty_graph = Mock()
        mock_empty_graph.get_nodes_by_label.return_value = []
        
        with pytest.raises(RuntimeError):
            embedder.compute_embeddings(mock_empty_graph, ["Entity"], ["RELATED_TO"])
    
    def test_parameter_validation(self):
        """Test parameter validation in embedding methods."""
        embedder = NodeEmbedder()
        
        # Test invalid walk parameters
        with pytest.raises(ValueError):
            embedder.compute_embeddings(
                Mock(), 
                [], 
                [], 
                embedding_dimension=-1
            )


class TestNodeEmbedderEdgeCases:
    """Edge case tests for NodeEmbedder."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = NodeEmbedder()
    
    def test_empty_graph_embeddings(self):
        """Test embedding computation on empty graph."""
        mock_empty_graph = Mock()
        mock_empty_graph.get_nodes_by_label.return_value = []
        
        with pytest.raises(RuntimeError, match="No nodes found|Embedding computation failed"):
            self.embedder.compute_embeddings(mock_empty_graph, ["Entity"], ["RELATED_TO"])
    
    def test_single_node_graph_embeddings(self):
        """Test embedding computation on single node graph."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1"]
        mock_graph.get_neighbors.return_value = []
        
        # Should handle single node gracefully
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            mock_adj.return_value = {"node1": []}
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["node1"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"node1": [0.1, 0.2]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    assert len(embeddings) == 1
                    assert "node1" in embeddings
    
    def test_disconnected_graph_embeddings(self):
        """Test embedding computation on disconnected graph."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1", "node2", "node3"]
        
        # Create disconnected adjacency
        adjacency = {"node1": [], "node2": [], "node3": []}
        
        with patch.object(self.embedder, '_build_adjacency', return_value=adjacency):
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                # Should generate walks even for disconnected nodes
                mock_walks.return_value = [["node1"], ["node2"], ["node3"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"node1": [0.1, 0.2], "node2": [0.3, 0.4], "node3": [0.5, 0.6]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    assert len(embeddings) == 3
    
    def test_very_small_embedding_dimension(self):
        """Test embedding computation with very small dimensions."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1", "node2"]
        
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            mock_adj.return_value = {"node1": ["node2"], "node2": ["node1"]}
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["node1", "node2"], ["node2", "node1"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"node1": [0.1], "node2": [0.2]}  # 1D embeddings
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(
                        mock_graph, ["Entity"], ["RELATED_TO"], embedding_dimension=1
                    )
                    assert len(embeddings) == 2
                    assert all(len(embed) == 1 for embed in embeddings.values())
    
    def test_very_large_embedding_dimension(self):
        """Test embedding computation with very large dimensions."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1"]
        
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            mock_adj.return_value = {"node1": []}
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["node1"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    # Test large dimension (1000)
                    large_embedding = [0.1] * 1000
                    mock_model = Mock()
                    mock_model.wv = {"node1": large_embedding}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(
                        mock_graph, ["Entity"], ["RELATED_TO"], embedding_dimension=1000
                    )
                    assert len(embeddings["node1"]) == 1000
    
    def test_zero_walk_length(self):
        """Test embedding computation with zero walk length."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1", "node2"]
        
        with pytest.raises(ValueError, match="walk_length must be positive"):
            self.embedder.compute_embeddings(
                mock_graph, ["Entity"], ["RELATED_TO"], walk_length=0
            )
    
    def test_zero_num_walks(self):
        """Test embedding computation with zero number of walks."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1", "node2"]
        
        with pytest.raises(ValueError, match="num_walks must be positive"):
            self.embedder.compute_embeddings(
                mock_graph, ["Entity"], ["RELATED_TO"], num_walks=0
            )
    
    def test_extreme_p_q_parameters(self):
        """Test embedding computation with extreme p and q parameters."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1", "node2"]
        
        # Test very high p and q values
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            mock_adj.return_value = {"node1": ["node2"], "node2": ["node1"]}
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["node1", "node2"], ["node2", "node1"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"node1": [0.1, 0.2], "node2": [0.3, 0.4]}
                    mock_train.return_value = mock_model
                    
                    # Test extreme values
                    embeddings = self.embedder.compute_embeddings(
                        mock_graph, ["Entity"], ["RELATED_TO"], p=1000.0, q=0.001
                    )
                    assert len(embeddings) == 2
    
    def test_node_with_very_high_degree(self):
        """Test embedding computation with node having very high degree."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["hub", "leaf1", "leaf2", "leaf3"]
        
        # Create star-like adjacency where hub connects to all leaves
        adjacency = {
            "hub": ["leaf1", "leaf2", "leaf3"],
            "leaf1": ["hub"],
            "leaf2": ["hub"],
            "leaf3": ["hub"]
        }
        
        with patch.object(self.embedder, '_build_adjacency', return_value=adjacency):
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["hub", "leaf1"], ["hub", "leaf2"], ["hub", "leaf3"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"hub": [0.1, 0.2], "leaf1": [0.3, 0.4], "leaf2": [0.5, 0.6], "leaf3": [0.7, 0.8]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    assert len(embeddings) == 4
    
    def test_duplicate_node_names(self):
        """Test embedding computation with duplicate node names."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1", "node1"]  # Duplicate
        
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            # Should handle duplicates by creating unique keys
            mock_adj.return_value = {"node1": [], "node1_1": []}
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["node1"], ["node1_1"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"node1": [0.1, 0.2], "node1_1": [0.3, 0.4]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    # Should handle duplicates gracefully
                    assert len(embeddings) >= 1
    
    def test_special_characters_in_node_names(self):
        """Test embedding computation with special characters in node names."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node-1", "node_2", "node.3", "node@4"]
        
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            adjacency = {"node-1": ["node_2"], "node_2": ["node-1"], "node.3": ["node@4"], "node@4": ["node.3"]}
            mock_adj.return_value = adjacency
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["node-1", "node_2"], ["node.3", "node@4"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"node-1": [0.1, 0.2], "node_2": [0.3, 0.4], "node.3": [0.5, 0.6], "node@4": [0.7, 0.8]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    assert len(embeddings) == 4
                    # Special characters should be preserved
                    assert "node-1" in embeddings
                    assert "node@4" in embeddings
    
    def test_very_long_node_names(self):
        """Test embedding computation with very long node names."""
        long_name = "node_" + "a" * 1000  # Very long name
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = [long_name, "short"]
        
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            adjacency = {long_name: ["short"], "short": [long_name]}
            mock_adj.return_value = adjacency
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [[long_name, "short"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {long_name: [0.1, 0.2], "short": [0.3, 0.4]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    assert len(embeddings) == 2
                    assert long_name in embeddings
    
    def test_numeric_node_names(self):
        """Test embedding computation with numeric node names."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = [1, 2, 3]  # Numeric nodes
        
        with patch.object(self.embedder, '_build_adjacency') as mock_adj:
            adjacency = {1: [2], 2: [1, 3], 3: [2]}
            mock_adj.return_value = adjacency
            
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                mock_walks.return_value = [["1", "2"], ["2", "3"]]  # Converted to strings
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"1": [0.1, 0.2], "2": [0.3, 0.4], "3": [0.5, 0.6]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    assert len(embeddings) == 3
    
    def test_self_loops_in_graph(self):
        """Test embedding computation with self-loops in graph."""
        mock_graph = Mock()
        mock_graph.get_nodes_by_label.return_value = ["node1", "node2"]
        
        # Create adjacency with self-loops
        adjacency = {"node1": ["node1", "node2"], "node2": ["node2", "node1"]}
        
        with patch.object(self.embedder, '_build_adjacency', return_value=adjacency):
            with patch.object(self.embedder, '_generate_random_walks') as mock_walks:
                # Should handle self-loops in walks
                mock_walks.return_value = [["node1", "node1", "node2"], ["node2", "node2", "node1"]]
                
                with patch.object(self.embedder, '_train_word2vec') as mock_train:
                    mock_model = Mock()
                    mock_model.wv = {"node1": [0.1, 0.2], "node2": [0.3, 0.4]}
                    mock_train.return_value = mock_model
                    
                    embeddings = self.embedder.compute_embeddings(mock_graph, ["Entity"], ["RELATED_TO"])
                    assert len(embeddings) == 2
