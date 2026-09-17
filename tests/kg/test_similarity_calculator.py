"""
Test suite for Similarity Calculator module.

This module tests the SimilarityCalculator class and its various
similarity metrics for node embeddings.
"""

import pytest
import numpy as np
from unittest.mock import Mock

from semantica.kg.similarity_calculator import SimilarityCalculator


class TestSimilarityCalculator:
    """Test cases for SimilarityCalculator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = SimilarityCalculator()
        
        # Test vectors
        self.vec1 = [1.0, 0.0, 0.0]
        self.vec2 = [0.0, 1.0, 0.0]
        self.vec3 = [1.0, 0.0, 0.0]  # Same as vec1
        self.vec4 = [0.5, 0.5, 0.0]
        
        # Test embeddings dictionary
        self.embeddings = {
            "node1": self.vec1,
            "node2": self.vec2,
            "node3": self.vec3,
            "node4": self.vec4
        }
    
    def test_init_default(self):
        """Test SimilarityCalculator initialization with default parameters."""
        calculator = SimilarityCalculator()
        
        assert calculator.method == "cosine"
        assert calculator.normalize is True
    
    def test_init_custom_parameters(self):
        """Test SimilarityCalculator initialization with custom parameters."""
        calculator = SimilarityCalculator(method="euclidean", normalize=False)
        
        assert calculator.method == "euclidean"
        assert calculator.normalize is False
    
    def test_init_invalid_method(self):
        """Test SimilarityCalculator initialization with invalid method."""
        with pytest.raises(ValueError, match="Unsupported similarity method"):
            SimilarityCalculator(method="invalid_method")
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        # Orthogonal vectors
        similarity = self.calculator.cosine_similarity(self.vec1, self.vec2)
        assert abs(similarity) < 1e-10  # Should be approximately 0
        
        # Identical vectors
        similarity = self.calculator.cosine_similarity(self.vec1, self.vec3)
        assert abs(similarity - 1.0) < 1e-10  # Should be approximately 1
        
        # Partial similarity
        similarity = self.calculator.cosine_similarity(self.vec1, self.vec4)
        expected = np.dot(self.vec1, self.vec4) / (np.linalg.norm(self.vec1) * np.linalg.norm(self.vec4))
        assert abs(similarity - expected) < 1e-10
    
    def test_cosine_similarity_dimension_mismatch(self):
        """Test cosine similarity with mismatched dimensions."""
        with pytest.raises(ValueError, match="Embedding vectors must have the same dimension"):
            self.calculator.cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])
    
    def test_euclidean_distance(self):
        """Test Euclidean distance calculation."""
        # Identical vectors
        distance = self.calculator.euclidean_distance(self.vec1, self.vec3)
        assert distance == 0.0
        
        # Orthogonal unit vectors
        distance = self.calculator.euclidean_distance(self.vec1, self.vec2)
        expected = np.sqrt(2.0)  # sqrt((1-0)^2 + (0-1)^2 + (0-0)^2)
        assert abs(distance - expected) < 1e-10
        
        # Different vectors
        distance = self.calculator.euclidean_distance(self.vec1, self.vec4)
        expected = np.sqrt((1-0.5)**2 + (0-0.5)**2 + (0-0)**2)
        assert abs(distance - expected) < 1e-10
    
    def test_manhattan_distance(self):
        """Test Manhattan distance calculation."""
        # Identical vectors
        distance = self.calculator.manhattan_distance(self.vec1, self.vec3)
        assert distance == 0.0
        
        # Orthogonal unit vectors
        distance = self.calculator.manhattan_distance(self.vec1, self.vec2)
        expected = 2.0  # |1-0| + |0-1| + |0-0|
        assert distance == expected
        
        # Different vectors
        distance = self.calculator.manhattan_distance(self.vec1, self.vec4)
        expected = abs(1-0.5) + abs(0-0.5) + abs(0-0)
        assert distance == expected
    
    def test_correlation_similarity(self):
        """Test Pearson correlation similarity calculation."""
        # Identical vectors
        similarity = self.calculator.correlation_similarity(self.vec1, self.vec3)
        assert abs(similarity - 1.0) < 1e-10  # Perfect correlation
        
        # Orthogonal vectors
        similarity = self.calculator.correlation_similarity(self.vec1, self.vec2)
        # For these specific vectors, correlation should be -1/2
        expected = -0.5
        assert abs(similarity - expected) < 1e-10
    
    def test_correlation_similarity_insufficient_length(self):
        """Test correlation similarity with insufficient vector length."""
        with pytest.raises(ValueError, match="Vectors must have at least 2 elements"):
            self.calculator.correlation_similarity([1.0], [2.0])
    
    def test_correlation_similarity_constant_vectors(self):
        """Test correlation similarity with constant vectors."""
        constant_vec1 = [1.0, 1.0, 1.0]
        constant_vec2 = [2.0, 2.0, 2.0]
        
        similarity = self.calculator.correlation_similarity(constant_vec1, constant_vec2)
        assert similarity == 0.0  # Should handle NaN case
    
    def test_batch_similarity_cosine(self):
        """Test batch similarity calculation with cosine method."""
        query_embedding = [1.0, 0.0, 0.0]
        
        similarities = self.calculator.batch_similarity(
            self.embeddings, 
            query_embedding, 
            method="cosine"
        )
        
        assert len(similarities) == 4
        assert "node1" in similarities
        assert "node2" in similarities
        assert "node3" in similarities
        assert "node4" in similarities
        
        # node1 and node3 should have highest similarity (identical to query)
        assert similarities["node1"] > similarities["node2"]
        assert similarities["node3"] > similarities["node2"]
    
    def test_batch_similarity_euclidean(self):
        """Test batch similarity calculation with Euclidean distance."""
        query_embedding = [1.0, 0.0, 0.0]
        
        similarities = self.calculator.batch_similarity(
            self.embeddings, 
            query_embedding, 
            method="euclidean"
        )
        
        assert len(similarities) == 4
        
        # Lower distance should result in higher similarity
        assert similarities["node1"] > similarities["node2"]
        assert similarities["node3"] > similarities["node2"]
    
    def test_batch_similarity_top_k(self):
        """Test batch similarity calculation with top-k filtering."""
        query_embedding = [1.0, 0.0, 0.0]
        
        similarities = self.calculator.batch_similarity(
            self.embeddings, 
            query_embedding, 
            top_k=2
        )
        
        assert len(similarities) == 2
        
        # Should return the 2 most similar nodes
        sorted_similarities = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        assert len(sorted_similarities) == 2
    
    def test_batch_similarity_empty_embeddings(self):
        """Test batch similarity with empty embeddings."""
        similarities = self.calculator.batch_similarity({}, [1.0, 0.0])
        assert similarities == {}
    
    def test_batch_similarity_dimension_mismatch(self):
        """Test batch similarity with dimension mismatch."""
        query_embedding = [1.0, 0.0]  # 2D
        embeddings_3d = {"node1": [1.0, 0.0, 0.0]}  # 3D
        
        with pytest.raises(ValueError, match="Query embedding dimension"):
            self.calculator.batch_similarity(embeddings_3d, query_embedding)
    
    def test_pairwise_similarity(self):
        """Test pairwise similarity calculation."""
        similarities = self.calculator.pairwise_similarity(self.embeddings, method="cosine")
        
        # Should return combinations of node pairs
        assert len(similarities) == 6  # 4 choose 2
        
        # Check specific pairs
        assert ("node1", "node3") in similarities  # Should be identical
        assert ("node1", "node2") in similarities  # Should be orthogonal
        
        # Identical vectors should have similarity 1
        assert abs(similarities[("node1", "node3")] - 1.0) < 1e-10
    
    def test_pairwise_similarity_empty(self):
        """Test pairwise similarity with single node."""
        single_embedding = {"node1": [1.0, 0.0]}
        similarities = self.calculator.pairwise_similarity(single_embedding)
        assert similarities == {}
    
    def test_find_most_similar(self):
        """Test finding most similar nodes."""
        query_embedding = [1.0, 0.0, 0.0]
        
        similar_nodes = self.calculator.find_most_similar(
            self.embeddings, 
            query_embedding, 
            top_k=3
        )
        
        assert len(similar_nodes) == 3
        assert isinstance(similar_nodes[0], tuple)
        assert len(similar_nodes[0]) == 2  # (node_id, similarity)
        
        # Should be sorted by similarity (descending)
        similarities = [similarity for _, similarity in similar_nodes]
        assert all(similarities[i] >= similarities[i+1] for i in range(len(similarities)-1))
    
    def test_find_most_similar_custom_method(self):
        """Test finding most similar nodes with custom method."""
        query_embedding = [1.0, 0.0, 0.0]
        
        similar_nodes = self.calculator.find_most_similar(
            self.embeddings, 
            query_embedding, 
            method="euclidean",
            top_k=2
        )
        
        assert len(similar_nodes) == 2
    
    def test_normalize_vector(self):
        """Test vector normalization."""
        calculator = SimilarityCalculator()
        
        # Unit vector
        unit_vec = np.array([1.0, 0.0])
        normalized = calculator._normalize_vector(unit_vec)
        assert np.allclose(normalized, unit_vec)
        
        # Non-unit vector
        vec = np.array([2.0, 0.0])
        normalized = calculator._normalize_vector(vec)
        expected = np.array([1.0, 0.0])
        assert np.allclose(normalized, expected)
        
        # Zero vector
        zero_vec = np.array([0.0, 0.0])
        normalized = calculator._normalize_vector(zero_vec)
        assert np.allclose(normalized, zero_vec)
    
    def test_batch_cosine_similarity(self):
        """Test batch cosine similarity computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        query_vec = np.array(self.vec1)
        
        similarities = calculator._batch_cosine_similarity(embedding_matrix, query_vec)
        
        assert len(similarities) == 3
        assert abs(similarities[0] - 1.0) < 1e-10  # vec1 identical to query
        assert abs(similarities[2] - 1.0) < 1e-10  # vec3 identical to query
        assert abs(similarities[1]) < 1e-10      # vec2 orthogonal to query
    
    def test_batch_euclidean_distance(self):
        """Test batch Euclidean distance computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        query_vec = np.array(self.vec1)
        
        distances = calculator._batch_euclidean_distance(embedding_matrix, query_vec)
        
        assert len(distances) == 3
        assert distances[0] == 0.0  # vec1 identical to query
        assert distances[2] == 0.0  # vec3 identical to query
        assert distances[1] > 0.0   # vec2 different from query
    
    def test_batch_manhattan_distance(self):
        """Test batch Manhattan distance computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        query_vec = np.array(self.vec1)
        
        distances = calculator._batch_manhattan_distance(embedding_matrix, query_vec)
        
        assert len(distances) == 3
        assert distances[0] == 0.0  # vec1 identical to query
        assert distances[2] == 0.0  # vec3 identical to query
        assert distances[1] > 0.0   # vec2 different from query
    
    def test_batch_correlation_similarity(self):
        """Test batch correlation similarity computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        query_vec = np.array(self.vec1)
        
        similarities = calculator._batch_correlation_similarity(embedding_matrix, query_vec)
        
        assert len(similarities) == 3
        assert abs(similarities[0] - 1.0) < 1e-10  # vec1 identical to query
        assert abs(similarities[2] - 1.0) < 1e-10  # vec3 identical to query
    
    def test_pairwise_cosine_similarity(self):
        """Test pairwise cosine similarity matrix computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        similarity_matrix = calculator._pairwise_cosine_similarity(embedding_matrix)
        
        assert similarity_matrix.shape == (3, 3)
        assert np.allclose(np.diag(similarity_matrix), 1.0)  # Diagonal should be 1
        assert abs(similarity_matrix[0, 2] - 1.0) < 1e-10  # vec1 and vec3 identical
        assert abs(similarity_matrix[0, 1]) < 1e-10      # vec1 and vec2 orthogonal
    
    def test_pairwise_euclidean_distance(self):
        """Test pairwise Euclidean distance matrix computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        distance_matrix = calculator._pairwise_euclidean_distance(embedding_matrix)
        
        assert distance_matrix.shape == (3, 3)
        assert np.allclose(np.diag(distance_matrix), 0.0)  # Diagonal should be 0
        assert distance_matrix[0, 2] == 0.0  # vec1 and vec3 identical
        assert distance_matrix[0, 1] > 0.0   # vec1 and vec2 different
    
    def test_pairwise_manhattan_distance(self):
        """Test pairwise Manhattan distance matrix computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        distance_matrix = calculator._pairwise_manhattan_distance(embedding_matrix)
        
        assert distance_matrix.shape == (3, 3)
        assert np.allclose(np.diag(distance_matrix), 0.0)  # Diagonal should be 0
        assert distance_matrix[0, 2] == 0.0  # vec1 and vec3 identical
        assert distance_matrix[0, 1] > 0.0   # vec1 and vec2 different
    
    def test_pairwise_correlation_similarity(self):
        """Test pairwise correlation similarity matrix computation."""
        calculator = SimilarityCalculator()
        
        embedding_matrix = np.array([self.vec1, self.vec2, self.vec3])
        similarity_matrix = calculator._pairwise_correlation_similarity(embedding_matrix)
        
        assert similarity_matrix.shape == (3, 3)
        assert np.allclose(np.diag(similarity_matrix), 1.0)  # Diagonal should be 1
        assert abs(similarity_matrix[0, 2] - 1.0) < 1e-10  # vec1 and vec3 identical


class TestSimilarityCalculatorEdgeCases:
    """Edge case tests for SimilarityCalculator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = SimilarityCalculator()
    
    def test_empty_embeddings_batch(self):
        """Test batch similarity with empty embeddings."""
        query_embedding = [1.0, 0.0, 0.0]
        
        similarities = self.calculator.batch_similarity({}, query_embedding)
        assert similarities == {}
    
    def test_single_embedding_batch(self):
        """Test batch similarity with single embedding."""
        embeddings = {"node1": [1.0, 0.0, 0.0]}
        query_embedding = [1.0, 0.0, 0.0]
        
        similarities = self.calculator.batch_similarity(embeddings, query_embedding)
        assert len(similarities) == 1
        assert similarities["node1"] == 1.0
    
    def test_zero_vector_similarity(self):
        """Test similarity with zero vectors."""
        zero_vec = [0.0, 0.0, 0.0]
        normal_vec = [1.0, 0.0, 0.0]
        
        # Cosine similarity with zero vector
        similarity = self.calculator.cosine_similarity(zero_vec, normal_vec)
        assert similarity == 0.0
        
        # Euclidean distance with zero vector
        distance = self.calculator.euclidean_distance(zero_vec, normal_vec)
        assert distance == 1.0
    
    def test_inf_nan_values(self):
        """Test similarity with infinity and NaN values."""
        # Test with infinity
        inf_vec = [float('inf'), 0.0, 0.0]
        normal_vec = [1.0, 0.0, 0.0]
        
        # Should handle infinity gracefully
        with pytest.raises(ValueError):
            self.calculator.cosine_similarity(inf_vec, normal_vec)
        
        # Test with NaN
        nan_vec = [float('nan'), 0.0, 0.0]
        
        with pytest.raises(ValueError):
            self.calculator.cosine_similarity(nan_vec, normal_vec)
    
    def test_very_small_values(self):
        """Test similarity with very small values."""
        small_vec1 = [1e-10, 1e-10, 1e-10]
        small_vec2 = [2e-10, 2e-10, 2e-10]
        
        # Should handle very small values without precision issues
        similarity = self.calculator.cosine_similarity(small_vec1, small_vec2)
        assert abs(similarity - 1.0) < 1e-10
        
        distance = self.calculator.euclidean_distance(small_vec1, small_vec2)
        assert distance > 0.0
    
    def test_very_large_values(self):
        """Test similarity with very large values."""
        large_vec1 = [1e10, 1e10, 1e10]
        large_vec2 = [2e10, 2e10, 2e10]
        
        # Should handle very large values without overflow
        similarity = self.calculator.cosine_similarity(large_vec1, large_vec2)
        assert abs(similarity - 1.0) < 1e-10
        
        distance = self.calculator.euclidean_distance(large_vec1, large_vec2)
        assert distance > 0.0
    
    def test_mixed_scale_values(self):
        """Test similarity with mixed scale values."""
        mixed_vec1 = [1e-10, 1.0, 1e10]
        mixed_vec2 = [2e-10, 2.0, 2e10]
        
        # Should handle mixed scales
        similarity = self.calculator.cosine_similarity(mixed_vec1, mixed_vec2)
        assert abs(similarity - 1.0) < 1e-10
    
    def test_high_dimensional_vectors(self):
        """Test similarity with high dimensional vectors."""
        # Test with 1000 dimensions
        high_dim1 = [0.1] * 1000
        high_dim2 = [0.2] * 1000
        
        similarity = self.calculator.cosine_similarity(high_dim1, high_dim2)
        assert abs(similarity - 1.0) < 1e-10
        
        distance = self.calculator.euclidean_distance(high_dim1, high_dim2)
        expected = np.sqrt(1000 * (0.1)**2)  # sqrt(1000 * 0.01)
        assert abs(distance - expected) < 1e-10
    
    def test_single_dimension_vectors(self):
        """Test similarity with single dimension vectors."""
        vec1 = [1.0]
        vec2 = [2.0]
        vec3 = [-1.0]
        
        # Cosine similarity
        similarity = self.calculator.cosine_similarity(vec1, vec2)
        assert similarity == 1.0  # Same direction
        
        similarity = self.calculator.cosine_similarity(vec1, vec3)
        assert similarity == -1.0  # Opposite direction
        
        # Euclidean distance
        distance = self.calculator.euclidean_distance(vec1, vec2)
        assert distance == 1.0
        
        # Manhattan distance
        distance = self.calculator.manhattan_distance(vec1, vec2)
        assert distance == 1.0
    
    def test_negative_values_similarity(self):
        """Test similarity with negative values."""
        vec1 = [1.0, -1.0, 0.0]
        vec2 = [-1.0, 1.0, 0.0]
        vec3 = [-1.0, -1.0, 0.0]
        
        # Cosine similarity
        similarity = self.calculator.cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 1e-10  # Opposite direction
        
        similarity = self.calculator.cosine_similarity(vec1, vec3)
        assert abs(similarity - 0.0) < 1e-10  # Orthogonal
        
        similarity = self.calculator.cosine_similarity(vec2, vec3)
        # Calculate expected: dot([-1,1,0], [-1,-1,0]) = 0, so cos = 0 (orthogonal)
        assert abs(similarity - 0.0) < 1e-10
        
        # Euclidean distance
        distance = self.calculator.euclidean_distance(vec1, vec2)
        expected = np.sqrt((1-(-1))**2 + (-1-1)**2 + 0**2)
        assert abs(distance - expected) < 1e-10
    
    def test_identical_vectors_all_methods(self):
        """Test all similarity methods with identical vectors."""
        vec = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        # Cosine similarity should be 1
        similarity = self.calculator.cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-10
        
        # Euclidean distance should be 0
        distance = self.calculator.euclidean_distance(vec, vec)
        assert abs(distance - 0.0) < 1e-10
        
        # Manhattan distance should be 0
        distance = self.calculator.manhattan_distance(vec, vec)
        assert abs(distance - 0.0) < 1e-10
        
        # Correlation similarity should be 1 (if length > 1)
        similarity = self.calculator.correlation_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-10
    
    def test_orthogonal_vectors(self):
        """Test similarity with orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        vec3 = [0.0, 0.0, 1.0]
        
        # All pairs should be orthogonal
        pairs = [(vec1, vec2), (vec1, vec3), (vec2, vec3)]
        
        for v1, v2 in pairs:
            # Cosine similarity should be 0
            similarity = self.calculator.cosine_similarity(v1, v2)
            assert abs(similarity) < 1e-10
            
            # Euclidean distance should be sqrt(2)
            distance = self.calculator.euclidean_distance(v1, v2)
            assert abs(distance - np.sqrt(2)) < 1e-10
            
            # Manhattan distance should be 2
            distance = self.calculator.manhattan_distance(v1, v2)
            assert distance == 2.0
    
    def test_batch_similarity_with_top_k(self):
        """Test batch similarity with top_k filtering."""
        embeddings = {
            "node1": [1.0, 0.0, 0.0],  # Most similar
            "node2": [0.9, 0.1, 0.0],  # Second most similar
            "node3": [0.0, 1.0, 0.0],  # Least similar
            "node4": [0.8, 0.2, 0.0],  # Third most similar
        }
        query_embedding = [1.0, 0.0, 0.0]
        
        # Test with top_k=2
        similarities = self.calculator.batch_similarity(embeddings, query_embedding, top_k=2)
        
        assert len(similarities) == 2
        # Should contain the most similar nodes
        assert "node1" in similarities
        assert "node2" in similarities
        
        # Should be sorted by similarity
        sorted_sims = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        assert sorted_sims[0][0] == "node1"
        assert sorted_sims[1][0] == "node2"
    
    def test_batch_similarity_with_invalid_top_k(self):
        """Test batch similarity with invalid top_k values."""
        embeddings = {"node1": [1.0, 0.0], "node2": [0.0, 1.0]}
        query_embedding = [1.0, 0.0]
        
        # Test with top_k=0
        similarities = self.calculator.batch_similarity(embeddings, query_embedding, top_k=0)
        assert similarities == {}
        
        # Test with negative top_k
        similarities = self.calculator.batch_similarity(embeddings, query_embedding, top_k=-1)
        assert similarities == {}
        
        # Test with top_k larger than number of embeddings
        similarities = self.calculator.batch_similarity(embeddings, query_embedding, top_k=10)
        assert len(similarities) == 2
    
    def test_pairwise_similarity_empty(self):
        """Test pairwise similarity with empty embeddings."""
        similarities = self.calculator.pairwise_similarity({})
        assert similarities == {}
        
        # Test with single embedding
        single_embedding = {"node1": [1.0, 0.0]}
        similarities = self.calculator.pairwise_similarity(single_embedding)
        assert similarities == {}
    
    def test_pairwise_similarity_large_dataset(self):
        """Test pairwise similarity with large dataset."""
        # Create 100 embeddings
        embeddings = {}
        for i in range(100):
            embeddings[f"node{i}"] = [np.random.random() for _ in range(10)]
        
        # Should handle large dataset without issues
        similarities = self.calculator.pairwise_similarity(embeddings, method="cosine")
        
        # Should have C(100, 2) = 4950 pairs
        assert len(similarities) == 4950
        
        # All similarities should be valid
        for (node1, node2), similarity in similarities.items():
            assert -1.0 <= similarity <= 1.0
    
    def test_find_most_similar_empty_embeddings(self):
        """Test finding most similar nodes with empty embeddings."""
        query_embedding = [1.0, 0.0, 0.0]
        
        similar_nodes = self.calculator.find_most_similar({}, query_embedding, top_k=5)
        assert similar_nodes == []
    
    def test_find_most_similar_single_embedding(self):
        """Test finding most similar nodes with single embedding."""
        embeddings = {"node1": [1.0, 0.0, 0.0]}
        query_embedding = [1.0, 0.0, 0.0]
        
        similar_nodes = self.calculator.find_most_similar(embeddings, query_embedding, top_k=5)
        # Should include the single node with perfect similarity
        assert len(similar_nodes) == 1
        assert similar_nodes[0] == ("node1", 1.0)
    
    def test_find_most_similar_invalid_top_k(self):
        """Test finding most similar nodes with invalid top_k."""
        embeddings = {"node1": [1.0, 0.0], "node2": [0.0, 1.0]}
        query_embedding = [1.0, 0.0]
        
        # Test with top_k=0
        similar_nodes = self.calculator.find_most_similar(embeddings, query_embedding, top_k=0)
        assert similar_nodes == []
        
        # Test with negative top_k
        similar_nodes = self.calculator.find_most_similar(embeddings, query_embedding, top_k=-1)
        assert similar_nodes == []
    
    def test_correlation_with_constant_vectors(self):
        """Test correlation similarity with constant vectors."""
        constant_vec1 = [1.0, 1.0, 1.0]
        constant_vec2 = [2.0, 2.0, 2.0]
        varying_vec = [1.0, 2.0, 3.0]
        
        # Correlation between constant vectors should be 0 (undefined)
        similarity = self.calculator.correlation_similarity(constant_vec1, constant_vec2)
        assert similarity == 0.0
        
        # Correlation between constant and varying vector should be 0 (undefined)
        similarity = self.calculator.correlation_similarity(constant_vec1, varying_vec)
        assert similarity == 0.0
    
    def test_correlation_with_two_elements(self):
        """Test correlation similarity with exactly two elements."""
        vec1 = [1.0, 2.0]
        vec2 = [2.0, 4.0]  # Perfectly correlated
        vec3 = [2.0, 1.0]  # Perfectly anti-correlated
        
        # Perfect positive correlation
        similarity = self.calculator.correlation_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-10
        
        # Perfect negative correlation
        similarity = self.calculator.correlation_similarity(vec1, vec3)
        assert abs(similarity + 1.0) < 1e-10
    
    def test_normalize_vector_edge_cases(self):
        """Test vector normalization edge cases."""
        calculator = SimilarityCalculator()
        
        # Zero vector
        zero_vec = np.array([0.0, 0.0, 0.0])
        normalized = calculator._normalize_vector(zero_vec)
        assert np.allclose(normalized, zero_vec)
        
        # Single element vector
        single_vec = np.array([5.0])
        normalized = calculator._normalize_vector(single_vec)
        assert np.allclose(normalized, np.array([1.0]))
        
        # Negative vector
        neg_vec = np.array([-1.0, -2.0, -3.0])
        normalized = calculator._normalize_vector(neg_vec)
        norm = np.linalg.norm(normalized)
        assert abs(norm - 1.0) < 1e-10
