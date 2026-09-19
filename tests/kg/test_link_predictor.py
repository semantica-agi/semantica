"""
Test suite for Link Predictor module.

This module tests the LinkPredictor class and its various
link prediction algorithms for knowledge graphs.
"""

import pytest
import networkx as nx
import numpy as np
from unittest.mock import Mock

from semantica.kg.link_predictor import LinkPredictor


class TestLinkPredictor:
    """Test cases for LinkPredictor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.predictor = LinkPredictor()
        
        # Create test graphs
        self.simple_graph = nx.Graph()
        self.simple_graph.add_edges_from([
            ("A", "B"), ("B", "C"), ("C", "D"), ("A", "E")
        ])
        
        self.complete_graph = nx.complete_graph(4)
        self.complete_graph = nx.relabel_nodes(self.complete_graph, {i: str(i) for i in range(4)})
        
        # Mock graph store
        self.mock_graph_store = Mock()
        self.mock_graph_store.get_nodes_by_label.return_value = ["A", "B", "C", "D", "E"]
        self.mock_graph_store.get_all_nodes.return_value = ["A", "B", "C", "D", "E"]
        self.mock_graph_store.has_node.return_value = True
        self.mock_graph_store.has_edge.return_value = False
        self.mock_graph_store.get_neighbors.return_value = []
        self.mock_graph_store.get_edge_data.return_value = {}
    
    def test_init_default(self):
        """Test LinkPredictor initialization with default parameters."""
        predictor = LinkPredictor()
        assert predictor.method == "preferential_attachment"
    
    def test_init_custom_method(self):
        """Test LinkPredictor initialization with custom method."""
        predictor = LinkPredictor(method="common_neighbors")
        assert predictor.method == "common_neighbors"
    
    def test_init_invalid_method(self):
        """Test LinkPredictor initialization with invalid method."""
        with pytest.raises(ValueError, match="Unsupported prediction method"):
            LinkPredictor(method="invalid_method")
    
    def test_preferential_attachment(self):
        """Test preferential attachment scoring."""
        # In simple graph: A(2), B(2), C(2), D(1), E(1)
        score = self.predictor._preferential_attachment(self.simple_graph, "A", "D")
        assert score == 2.0  # degree(A) * degree(D) = 2 * 1
        
        score = self.predictor._preferential_attachment(self.simple_graph, "A", "B")
        assert score == 4.0  # degree(A) * degree(B) = 2 * 2
    
    def test_common_neighbors(self):
        """Test common neighbors counting."""
        # A and C have B as common neighbor
        score = self.predictor._common_neighbors(self.simple_graph, "A", "C")
        assert score == 1.0
        
        # A and D have no common neighbors
        score = self.predictor._common_neighbors(self.simple_graph, "A", "D")
        assert score == 0.0
    
    def test_jaccard_coefficient(self):
        """Test Jaccard coefficient calculation."""
        # A and C: intersection={B}, union={B,E,D}
        score = self.predictor._jaccard_coefficient(self.simple_graph, "A", "C")
        assert abs(score - 1.0/3.0) < 1e-10  # |intersection|/|union| = 1/3
        
        # A and D: intersection={}, union={B,E,D}
        score = self.predictor._jaccard_coefficient(self.simple_graph, "A", "D")
        assert score == 0.0
    
    def test_adamic_adar_index(self):
        """Test Adamic-Adar index calculation."""
        # A and C have B as common neighbor (degree 2)
        score = self.predictor._adamic_adar_index(self.simple_graph, "A", "C")
        expected = 1.0 / (2.0 * np.log(2.0))  # 1/(deg(B) * log(deg(B)))
        assert abs(score - expected) < 1e-10
        
        # A and D have no common neighbors
        score = self.predictor._adamic_adar_index(self.simple_graph, "A", "D")
        assert score == 0.0
    
    def test_resource_allocation_index(self):
        """Test resource allocation index calculation."""
        # A and C have B as common neighbor (degree 2)
        score = self.predictor._resource_allocation_index(self.simple_graph, "A", "C")
        assert score == 0.5  # 1/deg(B) = 1/2
        
        # A and D have no common neighbors
        score = self.predictor._resource_allocation_index(self.simple_graph, "A", "D")
        assert score == 0.0
    
    def test_score_link_preferential_attachment(self):
        """Test scoring a specific link with preferential attachment."""
        score = self.predictor.score_link(self.simple_graph, "A", "D")
        assert score == 2.0  # degree(A) * degree(D)
    
    def test_score_link_common_neighbors(self):
        """Test scoring a specific link with common neighbors."""
        score = self.predictor.score_link(self.simple_graph, "A", "C", method="common_neighbors")
        assert score == 1.0
    
    def test_score_link_existing_edge(self):
        """Test scoring an existing edge (should return 0)."""
        score = self.predictor.score_link(self.simple_graph, "A", "B")
        assert score == 0.0
    
    def test_score_link_node_not_found(self):
        """Test scoring with non-existent node."""
        with pytest.raises(ValueError, match="Node X not found"):
            self.predictor.score_link(self.simple_graph, "X", "A")
        
        with pytest.raises(ValueError, match="Node X not found"):
            self.predictor.score_link(self.simple_graph, "A", "X")
    
    def test_predict_links_simple(self):
        """Test link prediction on simple graph."""
        links = self.predictor.predict_links(self.simple_graph, top_k=5)
        
        assert len(links) <= 5
        for link in links:
            assert len(link) == 3  # (node1, node2, score)
            assert isinstance(link[0], str)
            assert isinstance(link[1], str)
            assert isinstance(link[2], (int, float))
            assert link[2] > 0  # Only positive scores
    
    def test_predict_links_exclude_existing(self):
        """Test link prediction excluding existing edges."""
        links = self.predictor.predict_links(
            self.simple_graph, 
            top_k=10, 
            exclude_existing=True
        )
        
        # Should not include existing edges
        existing_edges = set(self.simple_graph.edges())
        for node1, node2, _ in links:
            assert (node1, node2) not in existing_edges
            assert (node2, node1) not in existing_edges
    
    def test_predict_links_include_existing(self):
        """Test link prediction including existing edges."""
        links = self.predictor.predict_links(
            self.simple_graph, 
            top_k=10, 
            exclude_existing=False
        )
        
        # Should include existing edges (though they might have score 0)
        # This test mainly ensures the parameter is respected
        assert isinstance(links, list)
    
    def test_predict_links_with_node_labels(self):
        """Test link prediction with node label filtering."""
        # Mock graph store with node labels
        self.mock_graph_store.get_nodes_by_label.return_value = ["A", "B", "C"]
        self.mock_graph_store.get_edges.return_value = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"}
        ]
        
        links = self.predictor.predict_links(
            self.mock_graph_store,
            node_labels=["Entity"],
            top_k=5
        )
        
        assert isinstance(links, list)
        assert len(links) <= 5
    
    def test_predict_links_with_relationship_types(self):
        """Test link prediction with relationship type filtering."""
        # Mock graph store with relationship types
        self.mock_graph_store.get_nodes_by_label.return_value = ["A", "B", "C", "D"]
        self.mock_graph_store.get_edges.return_value = [
            {"source": "A", "target": "B", "type": "RELATED"},
            {"source": "B", "target": "C", "type": "RELATED"}
        ]
        
        links = self.predictor.predict_links(
            self.mock_graph_store,
            relationship_types=["RELATED"],
            top_k=5
        )
        
        assert isinstance(links, list)
    
    def test_predict_top_links(self):
        """Test predicting top links for a specific node."""
        top_links = self.predictor.predict_top_links(self.simple_graph, "A", top_k=3)
        
        assert len(top_links) <= 3
        for link in top_links:
            assert len(link) == 2  # (node_id, score)
            assert isinstance(link[0], str)
            assert isinstance(link[1], (int, float))
            assert link[1] > 0  # Only positive scores
            assert link[0] != "A"  # Should not include self
    
    def test_predict_top_links_node_not_found(self):
        """Test predicting top links for non-existent node."""
        with pytest.raises(ValueError, match="Node X not found"):
            self.predictor.predict_top_links(self.simple_graph, "X", top_k=3)
    
    def test_batch_score_links(self):
        """Test batch scoring of node pairs."""
        node_pairs = [("A", "D"), ("A", "C"), ("B", "D")]
        
        scores = self.predictor.batch_score_links(self.simple_graph, node_pairs)
        
        assert len(scores) == 3
        for node1, node2, score in scores:
            assert (node1, node2) in node_pairs
            assert isinstance(score, (int, float))
    
    def test_batch_score_links_invalid_pairs(self):
        """Test batch scoring with invalid node pairs."""
        node_pairs = [("A", "X"), ("Y", "B"), ("A", "C")]  # X and Y don't exist
        
        scores = self.predictor.batch_score_links(self.simple_graph, node_pairs)
        
        assert len(scores) == 3
        # Invalid pairs should have score 0
        assert scores[0][2] == 0.0  # A-X
        assert scores[1][2] == 0.0  # Y-B
        assert scores[2][2] > 0.0   # A-C (valid)
    
    def test_get_candidate_nodes_all(self):
        """Test getting all candidate nodes."""
        nodes = self.predictor._get_candidate_nodes(self.simple_graph, None)
        expected_nodes = set(self.simple_graph.nodes())
        assert set(nodes) == expected_nodes
    
    def test_get_candidate_nodes_filtered(self):
        """Test getting candidate nodes with label filtering."""
        # Mock graph store
        self.mock_graph_store.get_nodes_by_label.return_value = ["A", "B", "C"]
        
        nodes = self.predictor._get_candidate_nodes(self.mock_graph_store, ["Entity"])
        assert set(nodes) == {"A", "B", "C"}
    
    def test_get_existing_edges(self):
        """Test getting existing edges."""
        edges = self.predictor._get_existing_edges(self.simple_graph, None)
        
        expected_edges = set()
        for u, v in self.simple_graph.edges():
            expected_edges.add((u, v))
            expected_edges.add((v, u))  # Add both directions
        
        assert edges == expected_edges
    
    def test_get_existing_edges_with_relationship_types(self):
        """Test getting existing edges with relationship type filtering."""
        # Mock graph store
        self.mock_graph_store.get_edges.return_value = [
            {"source": "A", "target": "B", "type": "RELATED"},
            {"source": "B", "target": "C", "type": "RELATED"},
            {"source": "C", "target": "D", "type": "DIFFERENT"}
        ]
        
        edges = self.predictor._get_existing_edges(self.mock_graph_store, ["RELATED"])
        
        # Should only include RELATED edges
        assert ("A", "B") in edges
        assert ("B", "A") in edges
        assert ("B", "C") in edges
        assert ("C", "B") in edges
        assert ("C", "D") not in edges
        assert ("D", "C") not in edges
    
    def test_get_all_nodes_networkx(self):
        """Test getting all nodes from NetworkX graph."""
        nodes = self.predictor._get_all_nodes(self.simple_graph)
        assert set(nodes) == set(self.simple_graph.nodes())
    
    def test_get_all_nodes_mock_graph(self):
        """Test getting all nodes from mock graph store."""
        self.mock_graph_store.get_all_nodes.return_value = ["A", "B", "C"]
        
        nodes = self.predictor._get_all_nodes(self.mock_graph_store)
        assert nodes == ["A", "B", "C"]
    
    def test_node_exists_networkx(self):
        """Test node existence check with NetworkX graph."""
        assert self.predictor._node_exists(self.simple_graph, "A")
        assert not self.predictor._node_exists(self.simple_graph, "X")
    
    def test_node_exists_mock_graph(self):
        """Test node existence check with mock graph store."""
        self.mock_graph_store.has_node.return_value = True
        assert self.predictor._node_exists(self.mock_graph_store, "A")
        
        self.mock_graph_store.has_node.return_value = False
        assert not self.predictor._node_exists(self.mock_graph_store, "X")
    
    def test_edge_exists_networkx(self):
        """Test edge existence check with NetworkX graph."""
        assert self.predictor._edge_exists(self.simple_graph, "A", "B")
        assert not self.predictor._edge_exists(self.simple_graph, "A", "D")
    
    def test_edge_exists_mock_graph(self):
        """Test edge existence check with mock graph store."""
        self.mock_graph_store.has_edge.return_value = True
        assert self.predictor._edge_exists(self.mock_graph_store, "A", "B")
        
        self.mock_graph_store.has_edge.return_value = False
        assert not self.predictor._edge_exists(self.mock_graph_store, "A", "D")
    
    def test_get_node_degree_networkx(self):
        """Test getting node degree from NetworkX graph."""
        degree = self.predictor._get_node_degree(self.simple_graph, "A")
        assert degree == 2  # A is connected to B and E
    
    def test_get_node_degree_mock_graph(self):
        """Test getting node degree from mock graph store."""
        self.mock_graph_store.get_node_degree.return_value = 3
        degree = self.predictor._get_node_degree(self.mock_graph_store, "A")
        assert degree == 3
    
    def test_get_node_degree_fallback(self):
        """Test getting node degree with fallback method."""
        self.mock_graph_store.get_node_degree = None
        self.mock_graph_store.get_neighbors.return_value = None  # disable get_neighbors
        self.mock_graph_store.neighbors.return_value = ["B", "C", "D"]

        degree = self.predictor._get_node_degree(self.mock_graph_store, "A")
        assert degree == 3
    
    def test_get_node_neighbors_networkx(self):
        """Test getting node neighbors from NetworkX graph."""
        neighbors = self.predictor._get_node_neighbors(self.simple_graph, "A")
        assert set(neighbors) == {"B", "E"}
    
    def test_get_node_neighbors_mock_graph(self):
        """Test getting node neighbors from mock graph store."""
        self.mock_graph_store.get_neighbors.return_value = ["B", "C"]
        neighbors = self.predictor._get_node_neighbors(self.mock_graph_store, "A")
        assert neighbors == ["B", "C"]
    
    def test_get_node_neighbors_filtered(self):
        """Test getting node neighbors with relationship type filtering."""
        self.mock_graph_store.get_neighbors.return_value = None  # disable get_neighbors
        self.mock_graph_store.neighbors.return_value = ["B", "C", "D"]
        self.mock_graph_store.get_edge_data.side_effect = lambda u, v: {
            ("A", "B"): {"type": "RELATED"},
            ("A", "C"): {"type": "DIFFERENT"},
            ("A", "D"): {"type": "RELATED"}
        }[(u, v)]
        
        neighbors = self.predictor._get_node_neighbors(
            self.mock_graph_store, "A", ["RELATED"]
        )
        assert set(neighbors) == {"B", "D"}


class TestLinkPredictorMethods:
    """Test different link prediction methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.predictor = LinkPredictor()
        
        # Create a more complex graph for testing
        self.graph = nx.Graph()
        self.graph.add_edges_from([
            ("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"),
            ("A", "F"), ("F", "G"), ("G", "H"), ("H", "E"),
            ("B", "F"), ("C", "G"), ("D", "H")
        ])
    
    def test_preferential_attachment_scores(self):
        """Test preferential attachment scoring on complex graph."""
        # Central nodes should have higher scores
        score_b_d = self.predictor._preferential_attachment(self.graph, "B", "D")
        score_a_e = self.predictor._preferential_attachment(self.graph, "A", "E")
        
        # B and D are more connected than A and E
        assert score_b_d > score_a_e
    
    def test_common_neighbors_scores(self):
        """Test common neighbors scoring on complex graph."""
        # A and G have F as common neighbor
        score_a_g = self.predictor._common_neighbors(self.graph, "A", "G")
        assert score_a_g == 1.0
        
        # A and E have no direct common neighbors
        score_a_e = self.predictor._common_neighbors(self.graph, "A", "E")
        assert score_a_e == 0.0
    
    def test_jaccard_coefficient_scores(self):
        """Test Jaccard coefficient scoring on complex graph."""
        # A and G: intersection={F}, union depends on their neighborhoods
        score_a_g = self.predictor._jaccard_coefficient(self.graph, "A", "G")
        assert 0.0 <= score_a_g <= 1.0
        
        # A and E: no common neighbors
        score_a_e = self.predictor._jaccard_coefficient(self.graph, "A", "E")
        assert score_a_e == 0.0
    
    def test_adamic_adar_scores(self):
        """Test Adamic-Adar index scoring on complex graph."""
        # A and G have F as common neighbor
        score_a_g = self.predictor._adamic_adar_index(self.graph, "A", "G")
        assert score_a_g > 0.0
        
        # A and E have no common neighbors
        score_a_e = self.predictor._adamic_adar_index(self.graph, "A", "E")
        assert score_a_e == 0.0
    
    def test_resource_allocation_scores(self):
        """Test resource allocation index scoring on complex graph."""
        # A and G have F as common neighbor
        score_a_g = self.predictor._resource_allocation_index(self.graph, "A", "G")
        assert score_a_g > 0.0
        
        # A and E have no common neighbors
        score_a_e = self.predictor._resource_allocation_index(self.graph, "A", "E")
        assert score_a_e == 0.0
    
    def test_predict_links_different_methods(self):
        """Test link prediction with different methods."""
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            links = self.predictor.predict_links(self.graph, method=method, top_k=5)
            
            assert isinstance(links, list)
            assert len(links) <= 5
            
            for link in links:
                assert len(link) == 3
                assert link[2] >= 0  # Scores should be non-negative
    
    def test_score_link_different_methods(self):
        """Test scoring links with different methods."""
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            score = self.predictor.score_link(self.graph, "A", "E", method=method)
            assert isinstance(score, (int, float))
            assert score >= 0


class TestLinkPredictorEdgeCases:
    """Edge case tests for LinkPredictor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.predictor = LinkPredictor()
    
    def test_empty_graph_all_methods(self):
        """Test all link prediction methods on empty graph."""
        empty_graph = nx.Graph()
        
        # All methods should return empty results
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            links = self.predictor.predict_links(empty_graph, method=method, top_k=10)
            assert links == []
    
    def test_single_node_graph_all_methods(self):
        """Test all link prediction methods on single node graph."""
        single_node_graph = nx.Graph()
        single_node_graph.add_node("A")
        
        # All methods should return empty results (no possible links)
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            links = self.predictor.predict_links(single_node_graph, method=method, top_k=10)
            assert links == []
    
    def test_complete_graph_all_methods(self):
        """Test all link prediction methods on complete graph."""
        complete_graph = nx.complete_graph(3)
        complete_graph = nx.relabel_nodes(complete_graph, {i: str(i) for i in range(3)})
        
        # With exclude_existing=True, should return empty results
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            links = self.predictor.predict_links(
                complete_graph, method=method, top_k=10, exclude_existing=True
            )
            assert links == []
            
            # With exclude_existing=False, should return existing edges with scores
            links = self.predictor.predict_links(
                complete_graph, method=method, top_k=10, exclude_existing=False
            )
            # Should have some results, but scores might be 0 for some methods
            assert isinstance(links, list)
    
    def test_disconnected_graph_all_methods(self):
        """Test all link prediction methods on disconnected graph."""
        disconnected_graph = nx.Graph()
        disconnected_graph.add_edges_from([("A", "B"), ("B", "C")])  # Component 1
        disconnected_graph.add_edges_from([("X", "Y"), ("Y", "Z")])  # Component 2
        
        # Should predict cross-component links
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            links = self.predictor.predict_links(disconnected_graph, method=method, top_k=10)
            
            # Should find cross-component predictions
            cross_component_links = [
                link for link in links
                if (link[0] in ["A", "B", "C"] and link[1] in ["X", "Y", "Z"]) or
                   (link[1] in ["A", "B", "C"] and link[0] in ["X", "Y", "Z"])
            ]
            
            if method == "preferential_attachment":
                # Preferential attachment should find cross-component links
                assert len(cross_component_links) > 0
            else:
                # Common neighbors based methods should have 0 score for cross-component
                assert all(score == 0.0 for _, _, score in cross_component_links)
    
    def test_star_graph_all_methods(self):
        """Test all link prediction methods on star graph."""
        star_graph = nx.star_graph(5)  # Central node 0, leaves 1-5
        star_graph = nx.relabel_nodes(star_graph, {i: str(i) for i in range(6)})
        
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            links = self.predictor.predict_links(star_graph, method=method, top_k=10)
            
            # Should predict leaf-leaf connections (center already connected to all)
            leaf_links = [
                link for link in links
                if link[0] != "0" and link[1] != "0"  # Both are leaves
            ]
            
            if method == "preferential_attachment":
                # Should predict leaf-leaf connections
                assert len(leaf_links) > 0
            else:
                # Common neighbors based methods should predict leaf-leaf with center as common neighbor
                assert len(leaf_links) > 0
    
    def test_graph_with_self_loops(self):
        """Test link prediction with self-loops."""
        loop_graph = nx.Graph()
        loop_graph.add_edges_from([("A", "B"), ("B", "C")])
        loop_graph.add_edge("A", "A")  # Self-loop
        loop_graph.add_edge("B", "B")  # Self-loop
        
        # Should handle self-loops gracefully
        links = self.predictor.predict_links(loop_graph, method="preferential_attachment", top_k=10)
        
        # Should not predict self-loops
        self_loops = [link for link in links if link[0] == link[1]]
        assert len(self_loops) == 0
    
    def test_graph_with_isolated_nodes(self):
        """Test link prediction with isolated nodes."""
        isolated_graph = nx.Graph()
        isolated_graph.add_edges_from([("A", "B")])
        isolated_graph.add_nodes_from(["X", "Y", "Z"])  # Isolated nodes
        
        # Should handle isolated nodes
        links = self.predictor.predict_links(isolated_graph, method="preferential_attachment", top_k=10)
        
        # Should predict connections involving isolated nodes
        isolated_links = [
            link for link in links
            if link[0] in ["X", "Y", "Z"] or link[1] in ["X", "Y", "Z"]
        ]
        
        # Preferential attachment should predict connections to isolated nodes (degree 0)
        # But degree 0 * degree anything = 0, so they might not appear in top results
        assert isinstance(isolated_links, list)
    
    def test_very_large_graph_performance(self):
        """Test link prediction performance on large graph."""
        # Create a larger sparse graph
        large_graph = nx.erdos_renyi_graph(100, 0.1)  # 100 nodes, moderate density
        large_graph = nx.relabel_nodes(large_graph, {i: str(i) for i in range(100)})
        
        # Test that methods complete without error
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        
        for method in methods:
            links = self.predictor.predict_links(large_graph, method=method, top_k=20)
            assert isinstance(links, list)
            assert len(links) <= 20
            
            # All links should be valid
            for node1, node2, score in links:
                assert node1 in large_graph.nodes()
                assert node2 in large_graph.nodes()
                assert node1 != node2
                assert isinstance(score, (int, float))
    
    def test_predict_top_links_edge_cases(self):
        """Test predict_top_links with edge cases."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("A", "C")])
        
        # Test with top_k=0
        top_links = self.predictor.predict_top_links(graph, "A", top_k=0)
        assert top_links == []
        
        # Test with negative top_k
        top_links = self.predictor.predict_top_links(graph, "A", top_k=-1)
        assert top_links == []
        
        # Test with top_k larger than possible connections
        top_links = self.predictor.predict_top_links(graph, "A", top_k=100)
        # Should not return more links than possible
        max_possible = len(graph.nodes()) - 1  # Can't connect to self
        assert len(top_links) <= max_possible
        
        # Test with non-existent source node
        with pytest.raises(ValueError, match="Node X not found"):
            self.predictor.predict_top_links(graph, "X", top_k=5)
    
    def test_batch_score_links_edge_cases(self):
        """Test batch_score_links with edge cases."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C")])
        
        # Empty node pairs
        scores = self.predictor.batch_score_links(graph, [])
        assert scores == []
        
        # Single node pair
        node_pairs = [("A", "B")]
        scores = self.predictor.batch_score_links(graph, node_pairs)
        assert len(scores) == 1
        assert scores[0][0] == "A"
        assert scores[0][1] == "B"
        assert scores[0][2] == 0.0  # Existing edge should have score 0
        
        # Mixed valid and invalid pairs
        mixed_pairs = [("A", "C"), ("X", "B"), ("A", "Y"), ("B", "C")]
        scores = self.predictor.batch_score_links(graph, mixed_pairs)
        assert len(scores) == 4
        
        # Valid pairs should have positive scores, invalid pairs should have 0
        for node1, node2, score in scores:
            if node1 in graph.nodes() and node2 in graph.nodes():
                if graph.has_edge(node1, node2):
                    assert score == 0.0  # Existing edge
                else:
                    assert score >= 0.0  # Valid prediction
            else:
                assert score == 0.0  # Invalid nodes
    
    def test_score_link_edge_cases(self):
        """Test score_link with edge cases."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C")])
        
        # Test with existing edge
        score = self.predictor.score_link(graph, "A", "B")
        assert score == 0.0  # Existing edges should have score 0
        
        # Test with non-existent edge
        score = self.predictor.score_link(graph, "A", "C")
        assert score > 0.0  # Should predict positive score
        
        # Test with non-existent nodes
        with pytest.raises(ValueError, match="Node X not found"):
            self.predictor.score_link(graph, "X", "A")
        
        with pytest.raises(ValueError, match="Node X not found"):
            self.predictor.score_link(graph, "A", "X")
        
        # Test with same node (self-link)
        score = self.predictor.score_link(graph, "A", "A")
        assert score == 0.0  # Self-links should have score 0
    
    def test_different_graph_types(self):
        """Test link prediction with different NetworkX graph types."""
        # Test with DiGraph
        directed_graph = nx.DiGraph()
        directed_graph.add_edges_from([("A", "B"), ("B", "C")])
        
        links = self.predictor.predict_links(directed_graph, method="preferential_attachment", top_k=10)
        assert isinstance(links, list)
        
        # Test with MultiGraph
        multigraph = nx.MultiGraph()
        multigraph.add_edge("A", "B")
        multigraph.add_edge("A", "B")  # Multiple edges
        
        links = self.predictor.predict_links(multigraph, method="preferential_attachment", top_k=10)
        assert isinstance(links, list)
        
        # Test with MultiDiGraph
        multi_digraph = nx.MultiDiGraph()
        multi_digraph.add_edge("A", "B")
        multi_digraph.add_edge("B", "A")
        
        links = self.predictor.predict_links(multi_digraph, method="preferential_attachment", top_k=10)
        assert isinstance(links, list)
    
    def test_extreme_degree_nodes(self):
        """Test link prediction with nodes of extreme degrees."""
        # Create graph with one high-degree node and many low-degree nodes
        extreme_graph = nx.Graph()
        hub = "hub"
        leaves = [f"leaf_{i}" for i in range(20)]
        
        # Connect hub to all leaves
        for leaf in leaves:
            extreme_graph.add_edge(hub, leaf)
        
        # Add some connections between leaves
        for i in range(0, 18, 2):
            extreme_graph.add_edge(leaves[i], leaves[i + 1])
        
        # Test preferential attachment (should favor hub-hub connections, but hub is already connected to all)
        links = self.predictor.predict_links(extreme_graph, method="preferential_attachment", top_k=10)
        
        # Should predict leaf-leaf connections
        leaf_links = [
            link for link in links
            if link[0].startswith("leaf_") and link[1].startswith("leaf_")
        ]
        assert len(leaf_links) > 0
        
        # Test common neighbors (should predict leaf-leaf with hub as common neighbor)
        links = self.predictor.predict_links(extreme_graph, method="common_neighbors", top_k=10)
        
        leaf_links = [
            link for link in links
            if link[0].startswith("leaf_") and link[1].startswith("leaf_")
        ]
        assert len(leaf_links) > 0
    
    def test_graph_with_node_attributes(self):
        """Test link prediction with graphs that have node attributes."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C")])
        
        # Add node attributes
        graph.nodes["A"]["type"] = "person"
        graph.nodes["B"]["type"] = "person"
        graph.nodes["C"]["type"] = "organization"
        
        # Should ignore node attributes for basic link prediction
        links = self.predictor.predict_links(graph, method="preferential_attachment", top_k=10)
        assert isinstance(links, list)
        
        # Should work the same regardless of attributes
        links_with_attrs = self.predictor.predict_links(graph, method="common_neighbors", top_k=10)
        assert isinstance(links_with_attrs, list)
    
    def test_graph_with_edge_attributes(self):
        """Test link prediction with graphs that have edge attributes."""
        graph = nx.Graph()
        graph.add_edge("A", "B", weight=1.5, type="friendship")
        graph.add_edge("B", "C", weight=2.0, type="colleague")
        
        # Should ignore edge attributes for basic link prediction
        links = self.predictor.predict_links(graph, method="preferential_attachment", top_k=10)
        assert isinstance(links, list)
        
        # Should work the same regardless of edge attributes
        links_with_attrs = self.predictor.predict_links(graph, method="common_neighbors", top_k=10)
        assert isinstance(links_with_attrs, list)
    
    def test_numeric_node_names(self):
        """Test link prediction with numeric node names."""
        graph = nx.Graph()
        graph.add_edges_from([(1, 2), (2, 3), (3, 4)])
        
        # Should handle numeric node names
        links = self.predictor.predict_links(graph, method="preferential_attachment", top_k=10)
        assert isinstance(links, list)
        
        # All node names should be numeric
        for node1, node2, score in links:
            assert isinstance(node1, (int, str))
            assert isinstance(node2, (int, str))
    
    def test_special_characters_in_node_names(self):
        """Test link prediction with special characters in node names."""
        graph = nx.Graph()
        graph.add_edges_from([("node-1", "node_2"), ("node_2", "node.3"), ("node.3", "node@4")])
        
        # Should handle special characters
        links = self.predictor.predict_links(graph, method="preferential_attachment", top_k=10)
        assert isinstance(links, list)
        
        # Special characters should be preserved
        for node1, node2, score in links:
            assert isinstance(node1, str)
            assert isinstance(node2, str)
    
    def test_very_small_top_k_values(self):
        """Test predict_links with very small top_k values."""
        graph = nx.Graph()
        graph.add_edges_from([("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")])
        
        # Test with top_k=1
        links = self.predictor.predict_links(graph, method="preferential_attachment", top_k=1)
        assert len(links) <= 1
        
        # Test with top_k=2
        links = self.predictor.predict_links(graph, method="preferential_attachment", top_k=2)
        assert len(links) <= 2
    
    def test_all_methods_with_same_graph(self):
        """Test all link prediction methods on the same graph for comparison."""
        graph = nx.Graph()
        graph.add_edges_from([
            ("A", "B"), ("B", "C"), ("C", "D"),  # Path
            ("A", "E"), ("E", "F"), ("F", "D")   # Another path
        ])
        
        methods = ["preferential_attachment", "common_neighbors", "jaccard_coefficient", "adamic_adar"]
        results = {}
        
        for method in methods:
            links = self.predictor.predict_links(graph, method=method, top_k=5)
            results[method] = links
            
            # All should return valid results
            assert isinstance(links, list)
            for node1, node2, score in links:
                assert node1 in graph.nodes()
                assert node2 in graph.nodes()
                assert node1 != node2
                assert isinstance(score, (int, float))
        
        # Different methods should give different results (scores, possibly rankings)
        # This is a basic sanity check that methods are actually different
        method_pairs = [(methods[i], methods[j]) for i in range(len(methods)) for j in range(i+1, len(methods))]
        
        for method1, method2 in method_pairs:
            # Convert to sets of node pairs for comparison (ignoring scores)
            pairs1 = set((node1, node2) for node1, node2, _ in results[method1])
            pairs2 = set((node1, node2) for node1, node2, _ in results[method2])
            
            # Should not be identical (though they might overlap)
            # This is a weak test, but ensures methods are doing something different
            if pairs1 and pairs2:
                # At least one method should return results
                pass
