"""
Link Predictor Module

This module provides comprehensive link prediction algorithms for knowledge graphs, enabling
the discovery of potential connections and missing relationships.

Supported Algorithms:
    - Preferential attachment: Degree product scoring (effective for scale-free networks)
    - Common neighbors: Count of shared neighbors between nodes
    - Jaccard coefficient: Jaccard similarity of neighbor sets
    - Adamic-Adar index: Weighted neighbor count based on degree logarithm
    - Resource allocation index: Resource transfer probability between nodes

Key Features:
    - Multiple link prediction algorithms with different theoretical foundations
    - Scalable implementations for large graphs
    - Batch processing for multiple link predictions
    - Top-k link prediction for targeted analysis
    - Configurable scoring methods and parameters
    - Graph compatibility with NetworkX and custom formats

Main Classes:
    - LinkPredictor: Comprehensive link prediction engine

Methods:
    - predict_links(): Predict potential links across the entire graph
    - score_link(): Calculate link prediction score for specific node pair
    - predict_top_links(): Find top-k links for a specific node
    - batch_score_links(): Batch scoring for multiple node pairs
    - _preferential_attachment(): Degree product scoring
    - _common_neighbors(): Shared neighbor counting
    - _jaccard_coefficient(): Jaccard similarity calculation
    - _adamic_adar_index(): Adamic-Adar index computation
    - _resource_allocation_index(): Resource allocation calculation

Example Usage:
    >>> from semantica.kg import LinkPredictor
    >>> predictor = LinkPredictor(method="preferential_attachment")
    >>> links = predictor.predict_links(graph, top_k=20)
    >>> score = predictor.score_link(graph, "node_a", "node_b")
    >>> node_links = predictor.predict_top_links(graph, "node_a", top_k=10)
    >>> batch_scores = predictor.batch_score_links(graph, node_pairs)

Author: Semantica Contributors
License: MIT
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class LinkPredictor:
    """
    Link prediction engine for knowledge graphs.
    
    This class provides various link prediction algorithms for identifying
    potential connections and missing relationships in knowledge graphs.
    It supports multiple scoring methods and efficient computation for large graphs.
    
    Supported Algorithms:
        - preferential_attachment: Degree product scoring (simple, effective for scale-free networks)
        - common_neighbors: Count of shared neighbors
        - jaccard_coefficient: Jaccard similarity of neighbor sets
        - adamic_adar: Weighted neighbor count based on degree
        - resource_allocation: Resource allocation index
    
    Features:
        - Multiple link prediction algorithms
        - Efficient neighbor counting
        - Similarity-based predictions
        - Scalable implementations
        - Batch prediction capabilities
        - Configurable scoring methods
    
    Example Usage:
        >>> predictor = LinkPredictor(method="preferential_attachment")
        >>> # Predict top links
        >>> links = predictor.predict_links(graph, top_k=20)
        >>> # Score specific link
        >>> score = predictor.score_link(graph, "node_a", "node_b")
        >>> # Predict links for specific node
        >>> node_links = predictor.predict_top_links(graph, "node_a", top_k=10)
    """
    
    def __init__(self, method: str = "preferential_attachment"):
        """
        Initialize the link predictor.
        
        Args:
            method: Default prediction method
        """
        self.method = method
        
        self.logger = get_logger(__name__)
        self.progress_tracker = get_progress_tracker()
        
        supported_methods = [
            "preferential_attachment", "common_neighbors", 
            "jaccard_coefficient", "adamic_adar", "resource_allocation"
        ]
        
        if method not in supported_methods:
            raise ValueError(f"Unsupported prediction method: {method}")
    
    def predict_links(
        self,
        graph_store: Any = None,
        node_labels: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        top_k: int = 20,
        method: Optional[str] = None,
        exclude_existing: bool = True,
        chunk_size: int = 1000,
        graph: Any = None,
        directed: Optional[bool] = None
    ) -> List[Tuple[str, str, float]]:
        """
        Predict likely links between nodes.
        
        Args:
            graph_store: Graph store containing the knowledge graph
            node_labels: List of node labels to consider (None for all)
            relationship_types: List of relationship types to consider (None for all)
            top_k: Number of top predictions to return
            method: Prediction method to use (overrides default)
            exclude_existing: Whether to exclude existing links
            chunk_size: Process candidates in chunks for memory efficiency
            directed: Score each ordered pair, excluding only an edge in the
                same direction. None keeps the undirected behaviour (one
                candidate per node pair, dropped when either direction already
                has an edge), which is what an undirected graph wants; a
                directed graph needs True, otherwise a missing reverse edge is
                never considered (#1941 review).
            
        Returns:
            List of (node1, node2, score) tuples sorted by score
            
        Raises:
            ValueError: If method is not supported
            RuntimeError: If prediction fails
        """
        try:
            # Support 'graph' as alias for 'graph_store'
            if graph_store is None and graph is not None:
                graph_store = graph
            method = method or self.method
            # Support method aliases
            _method_aliases = {"jaccard": "jaccard_coefficient"}
            method = _method_aliases.get(method, method)
            self.logger.info(f"Predicting links using {method} method")

            # Get candidate nodes
            nodes = self._get_candidate_nodes(graph_store, node_labels)
            
            # Get existing edges if excluding
            existing_edges = set()
            if exclude_existing:
                existing_edges = self._get_existing_edges(graph_store, relationship_types)
            
            if directed:
                # Ordered pairs: with the undirected candidate set below, an
                # existing A->B hides a missing B->A, and which direction gets
                # scored depends on node order (#1941 review). The set from
                # _get_existing_edges() records both directions of every edge,
                # so it cannot tell those apart; read the directed edges from
                # the graph itself when it can expose them.
                directed_edges = existing_edges
                edges_attr = getattr(graph_store, "edges", None)
                if callable(edges_attr):
                    directed_edges = {(u, v) for u, v, *_ in edges_attr()}
                scores = []

                def _score_ordered(source: Any, target: Any) -> None:
                    if source == target:
                        return
                    if exclude_existing and (source, target) in directed_edges:
                        return
                    score = self.score_link(graph_store, source, target, method)
                    if score > 0:
                        scores.append((source, target, score))

                # Chunked like the undirected path below: chunking is about
                # memory, and without it this loop holds every ordered pair it
                # scores. Both directions of each unordered pair are scored, so
                # the chunked traversal still covers all n*(n-1) ordered pairs.
                for i in range(0, len(nodes), chunk_size):
                    chunk_nodes = nodes[i:i + chunk_size]
                    for j, node1 in enumerate(chunk_nodes):
                        for node2 in chunk_nodes[j + 1:]:
                            _score_ordered(node1, node2)
                            _score_ordered(node2, node1)
                        for prev_start in range(0, i, chunk_size):
                            prev_chunk = nodes[prev_start:prev_start + chunk_size]
                            for node2 in prev_chunk:
                                _score_ordered(node1, node2)
                                _score_ordered(node2, node1)
            # For large graphs, use efficient candidate generation
            elif len(nodes) > chunk_size:
                scores = []
                
                # Process nodes in chunks to manage memory
                for i in range(0, len(nodes), chunk_size):
                    chunk_nodes = nodes[i:i + chunk_size]
                    
                    # Generate pairs within chunk and with previous chunks
                    for j, node1 in enumerate(chunk_nodes):
                        # Pairs within current chunk
                        for node2 in chunk_nodes[j + 1:]:
                            if exclude_existing and ((node1, node2) in existing_edges or (node2, node1) in existing_edges):
                                continue
                            score = self.score_link(graph_store, node1, node2, method)
                            if score > 0:
                                scores.append((node1, node2, score))
                        
                        # Pairs with previous chunks
                        for prev_chunk_start in range(0, i, chunk_size):
                            prev_chunk_end = min(prev_chunk_start + chunk_size, i)
                            prev_chunk = nodes[prev_chunk_start:prev_chunk_end]
                            for node2 in prev_chunk:
                                if exclude_existing and ((node1, node2) in existing_edges or (node2, node1) in existing_edges):
                                    continue
                                score = self.score_link(graph_store, node1, node2, method)
                                if score > 0:
                                    scores.append((node1, node2, score))
            else:
                # For smaller graphs, use existing method
                candidate_pairs = []
                for i, node1 in enumerate(nodes):
                    for node2 in nodes[i + 1:]:
                        if exclude_existing and ((node1, node2) in existing_edges or (node2, node1) in existing_edges):
                            continue
                        candidate_pairs.append((node1, node2))
                
                # Score all pairs
                scores = []
                for node1, node2 in candidate_pairs:
                    score = self.score_link(graph_store, node1, node2, method)
                    if score > 0:  # Only include positive scores
                        scores.append((node1, node2, score))
            
            # Sort by score and return top-k
            scores.sort(key=lambda x: x[2], reverse=True)
            top_predictions = scores[:top_k]
            
            self.logger.info(f"Generated {len(top_predictions)} link predictions")
            return top_predictions
            
        except Exception as e:
            self.logger.error(f"Link prediction failed: {str(e)}")
            raise RuntimeError(f"Link prediction failed: {str(e)}")
    
    def score_link(
        self,
        graph_store: Any,
        node_id1: str,
        node_id2: str,
        method: Optional[str] = None
    ) -> float:
        """
        Score a potential link between two nodes.
        
        Args:
            graph_store: Graph store containing the knowledge graph
            node_id1: First node ID
            node_id2: Second node ID
            method: Prediction method to use (overrides default)
            
        Returns:
            Link prediction score (higher indicates more likely)
            
        Raises:
            ValueError: If method is not supported or nodes not found
        """
        method = method or self.method

        # Self-links are not meaningful
        if node_id1 == node_id2:
            return 0.0

        # Validate nodes exist
        if not self._node_exists(graph_store, node_id1):
            raise ValueError(f"Node {node_id1} not found")
        if not self._node_exists(graph_store, node_id2):
            raise ValueError(f"Node {node_id2} not found")

        # Check if link already exists
        if self._edge_exists(graph_store, node_id1, node_id2):
            return 0.0  # Already connected
        
        # Calculate score based on method
        if method == "preferential_attachment":
            return self._preferential_attachment(graph_store, node_id1, node_id2)
        elif method == "common_neighbors":
            return self._common_neighbors(graph_store, node_id1, node_id2)
        elif method == "jaccard_coefficient":
            return self._jaccard_coefficient(graph_store, node_id1, node_id2)
        elif method == "adamic_adar":
            return self._adamic_adar_index(graph_store, node_id1, node_id2)
        elif method == "resource_allocation":
            return self._resource_allocation_index(graph_store, node_id1, node_id2)
        else:
            raise ValueError(f"Unsupported prediction method: {method}")
    
    def predict_top_links(
        self,
        graph_store: Any,
        node_id: str,
        top_k: int = 10,
        method: Optional[str] = None
    ) -> List[Tuple[str, float]]:
        """
        Predict top-k likely links for a specific node.
        
        Args:
            graph_store: Graph store containing the knowledge graph
            node_id: Target node ID
            top_k: Number of predictions to return
            method: Prediction method to use (overrides default)
            
        Returns:
            List of (node_id, score) tuples sorted by score
            
        Raises:
            ValueError: If node not found
        """
        if not self._node_exists(graph_store, node_id):
            raise ValueError(f"Node {node_id} not found")
        
        # Get all other nodes
        all_nodes = self._get_all_nodes(graph_store)
        other_nodes = [node for node in all_nodes if node != node_id]
        
        # Score all potential links
        scores = []
        for other_node in other_nodes:
            if not self._edge_exists(graph_store, node_id, other_node):
                score = self.score_link(graph_store, node_id, other_node, method)
                if score > 0:
                    scores.append((other_node, score))
        
        # Sort by score and return top-k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def batch_score_links(
        self,
        graph_store: Any,
        node_pairs: List[Tuple[str, str]],
        method: Optional[str] = None
    ) -> List[Tuple[str, str, float]]:
        """
        Score multiple node pairs efficiently.
        
        Args:
            graph_store: Graph store containing the knowledge graph
            node_pairs: List of (node1, node2) tuples
            method: Prediction method to use (overrides default)
            
        Returns:
            List of (node1, node2, score) tuples
        """
        method = method or self.method
        scores = []
        
        for node1, node2 in node_pairs:
            try:
                score = self.score_link(graph_store, node1, node2, method)
                scores.append((node1, node2, score))
            except ValueError:
                # Skip invalid pairs
                scores.append((node1, node2, 0.0))
        
        return scores
    
    def _preferential_attachment(self, graph_store: Any, node_id1: str, node_id2: str) -> float:
        """Calculate preferential attachment score."""
        degree1 = self._get_node_degree(graph_store, node_id1)
        degree2 = self._get_node_degree(graph_store, node_id2)
        return float(degree1 * degree2)
    
    def _common_neighbors(self, graph_store: Any, node_id1: str, node_id2: str) -> float:
        """Count common neighbors between two nodes."""
        neighbors1 = set(self._get_node_neighbors(graph_store, node_id1))
        neighbors2 = set(self._get_node_neighbors(graph_store, node_id2))
        return float(len(neighbors1.intersection(neighbors2)))
    
    def _jaccard_coefficient(self, graph_store: Any, node_id1: str, node_id2: str) -> float:
        """Calculate Jaccard coefficient of neighbor sets."""
        neighbors1 = set(self._get_node_neighbors(graph_store, node_id1))
        neighbors2 = set(self._get_node_neighbors(graph_store, node_id2))
        
        intersection = neighbors1.intersection(neighbors2)
        union = neighbors1.union(neighbors2)
        
        if len(union) == 0:
            return 0.0
        
        return float(len(intersection) / len(union))
    
    def _adamic_adar_index(self, graph_store: Any, node_id1: str, node_id2: str) -> float:
        """Calculate Adamic-Adar index."""
        neighbors1 = set(self._get_node_neighbors(graph_store, node_id1))
        neighbors2 = set(self._get_node_neighbors(graph_store, node_id2))
        
        common_neighbors = neighbors1.intersection(neighbors2)
        score = 0.0
        
        for neighbor in common_neighbors:
            degree = self._get_node_degree(graph_store, neighbor)
            if degree > 1:
                score += 1.0 / (degree * np.log(degree))
        
        return score
    
    def _resource_allocation_index(self, graph_store: Any, node_id1: str, node_id2: str) -> float:
        """Calculate resource allocation index."""
        neighbors1 = set(self._get_node_neighbors(graph_store, node_id1))
        neighbors2 = set(self._get_node_neighbors(graph_store, node_id2))
        
        common_neighbors = neighbors1.intersection(neighbors2)
        score = 0.0
        
        for neighbor in common_neighbors:
            degree = self._get_node_degree(graph_store, neighbor)
            if degree > 0:
                score += 1.0 / degree
        
        return score
    
    def _get_candidate_nodes(self, graph_store: Any, node_labels: Optional[List[str]]) -> List[str]:
        """Get candidate nodes based on labels."""
        if node_labels is None:
            return self._get_all_nodes(graph_store)
        
        nodes = []
        for label in node_labels:
            if hasattr(graph_store, 'get_nodes_by_label') and callable(graph_store.get_nodes_by_label):
                result = graph_store.get_nodes_by_label(label)
                if isinstance(result, list):
                    nodes.extend(
                        item.get("id") if isinstance(item, dict) else item
                        for item in result
                        if item and (not isinstance(item, dict) or item.get("id"))
                    )
            else:
                # Fallback - get all nodes and filter by label if possible
                all_nodes = self._get_all_nodes(graph_store)
                for node in all_nodes:
                    if hasattr(graph_store, 'get_node_label'):
                        if graph_store.get_node_label(node) in node_labels:
                            nodes.append(node)
        
        return list(set(nodes))  # Remove duplicates
    
    def _get_existing_edges(self, graph_store: Any, relationship_types: Optional[List[str]]) -> set:
        """Get existing edges to exclude from predictions."""
        edges = set()

        if hasattr(graph_store, 'get_edges') and callable(graph_store.get_edges):
            all_edges = graph_store.get_edges(relationship_types)
            if isinstance(all_edges, list):
                for edge in all_edges:
                    if relationship_types and edge.get('type') not in relationship_types:
                        continue
                    edges.add((edge['source'], edge['target']))
                    edges.add((edge['target'], edge['source']))
        elif hasattr(graph_store, 'edges') and callable(graph_store.edges):
            for u, v in graph_store.edges():
                edges.add((u, v))
                edges.add((v, u))

        return edges

    def _get_all_nodes(self, graph_store: Any) -> List[str]:
        """Get all nodes from the graph store."""
        if hasattr(graph_store, 'get_all_nodes') and callable(graph_store.get_all_nodes):
            result = graph_store.get_all_nodes()
            if isinstance(result, list):
                return result
        if hasattr(graph_store, 'nodes') and callable(graph_store.nodes):
            try:
                return list(graph_store.nodes())
            except TypeError:
                pass
        return []
    
    def _node_exists(self, graph_store: Any, node_id: str) -> bool:
        """Check if node exists in the graph store."""
        if hasattr(graph_store, 'has_node'):
            return graph_store.has_node(node_id)
        elif hasattr(graph_store, '__contains__'):
            return node_id in graph_store
        else:
            all_nodes = self._get_all_nodes(graph_store)
            return node_id in all_nodes
    
    def _edge_exists(self, graph_store: Any, node_id1: str, node_id2: str) -> bool:
        """Check if edge exists between two nodes."""
        if hasattr(graph_store, 'has_edge'):
            return graph_store.has_edge(node_id1, node_id2)
        elif hasattr(graph_store, 'get_edge'):
            return graph_store.get_edge(node_id1, node_id2) is not None
        else:
            return False
    
    def _get_node_degree(self, graph_store: Any, node_id: str) -> int:
        """Get degree of a node."""
        if hasattr(graph_store, 'get_node_degree') and callable(graph_store.get_node_degree):
            result = graph_store.get_node_degree(node_id)
            if isinstance(result, int):
                return result
        if hasattr(graph_store, 'degree') and callable(graph_store.degree):
            result = graph_store.degree(node_id)
            if isinstance(result, int):
                return result
        # Fallback - count neighbors
        return len(self._get_node_neighbors(graph_store, node_id))

    def _get_node_neighbors(
        self,
        graph_store: Any,
        node_id: str,
        relationship_types: Optional[List[str]] = None
    ) -> List[str]:
        """Get neighbors of a node."""
        if hasattr(graph_store, 'get_neighbors') and callable(graph_store.get_neighbors):
            raw = graph_store.get_neighbors(node_id)
            if isinstance(raw, list):
                neighbors = [
                    n.get("id") if isinstance(n, dict) else n
                    for n in raw if n
                ]
                if relationship_types and hasattr(graph_store, 'get_edge_data') and callable(graph_store.get_edge_data):
                    filtered = []
                    for nb in neighbors:
                        try:
                            edge_data = graph_store.get_edge_data(node_id, nb)
                            if isinstance(edge_data, dict) and edge_data.get('type') in relationship_types:
                                filtered.append(nb)
                        except Exception:
                            pass
                    return filtered
                return neighbors
        if hasattr(graph_store, 'neighbors') and callable(graph_store.neighbors):
            try:
                raw = [n.get("id") if isinstance(n, dict) else n for n in graph_store.neighbors(node_id)]
                if not isinstance(raw, list):
                    return []
                if relationship_types and hasattr(graph_store, 'get_edge_data') and callable(graph_store.get_edge_data):
                    filtered = []
                    for nb in raw:
                        try:
                            edge_data = graph_store.get_edge_data(node_id, nb)
                            if isinstance(edge_data, dict) and edge_data.get('type') in relationship_types:
                                filtered.append(nb)
                        except Exception:
                            pass
                    return filtered
                return raw
            except TypeError:
                pass
        return []
