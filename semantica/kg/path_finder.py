"""
Path Finder Module

This module provides comprehensive path finding algorithms for knowledge graphs, enabling
shortest path discovery, route analysis, and connectivity assessment.

Supported Algorithms:
    - Dijkstra's algorithm: Weighted shortest path finding
    - A* search: Heuristic-based path finding with custom heuristics
    - BFS shortest path: Unweighted shortest path finding
    - All shortest paths: Multiple path discovery between nodes
    - K-shortest paths: Find top-k alternative paths
    - Path length calculation: Compute total path distance

Key Features:
    - Weighted and unweighted graph support
    - Custom heuristic functions for A* search
    - Multiple path discovery and ranking
    - Efficient path reconstruction algorithms
    - Graph compatibility with NetworkX and custom formats
    - Error handling and validation for invalid paths

Main Classes:
    - PathFinder: Comprehensive path finding engine

Methods:
    - dijkstra_shortest_path(): Find shortest path using Dijkstra's algorithm
    - a_star_search(): Find path using A* search with heuristics
    - bfs_shortest_path(): Find unweighted shortest path using BFS
    - all_shortest_paths(): Find all shortest paths between nodes
    - find_k_shortest_paths(): Find top-k shortest alternative paths
    - path_length(): Calculate total length of a given path
    - find_connected_components(): Identify connected graph components

Example Usage:
    >>> from semantica.kg import PathFinder
    >>> finder = PathFinder()
    >>> path = finder.dijkstra_shortest_path(graph, "node_a", "node_b")
    >>> paths = finder.all_shortest_paths(graph, "source_node", "target_node")
    >>> k_paths = finder.find_k_shortest_paths(graph, "source", "target", k=3)

Author: Semantica Contributors
License: MIT
"""

import heapq
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class PathFinder:
    """
    Path finding engine for knowledge graphs.
    
    This class provides various path finding algorithms for discovering routes
    and analyzing connectivity in knowledge graphs. It supports both weighted
    and unweighted graphs with efficient implementations.
    
    Supported Algorithms:
        - dijkstra: Dijkstra's algorithm for shortest paths (weighted)
        - astar: A* search with heuristic guidance (weighted)
        - bfs: Breadth-first search for unweighted shortest paths
        - all_pairs: All-pairs shortest paths
    
    Features:
        - Weighted and unweighted path finding
        - Multiple path finding algorithms
        - Efficient implementations with priority queues
        - Support for large graphs
        - Heuristic functions for A* search
        - Path length calculation
    
    Example Usage:
        >>> finder = PathFinder()
        >>> # Shortest path
        >>> path = finder.dijkstra_shortest_path(graph, "source", "target")
        >>> # A* search with heuristic
        >>> path = finder.a_star_search(graph, "source", "target", heuristic)
        >>> # All shortest paths from source
        >>> paths = finder.all_shortest_paths(graph, "source")
    """
    
    def __init__(self, default_algorithm: str = "dijkstra"):
        """
        Initialize the path finder.
        
        Args:
            default_algorithm: Default algorithm for path finding
        """
        self.default_algorithm = default_algorithm
        
        self.logger = get_logger(__name__)
        self.progress_tracker = get_progress_tracker()
        
        if default_algorithm not in ["dijkstra", "astar", "bfs"]:
            raise ValueError(f"Unsupported default algorithm: {default_algorithm}")
    
    def dijkstra_shortest_path(
        self,
        graph: Any,
        source: str,
        target: str,
        weight_attribute: str = "weight",
        default_weight: float = 1.0,
        directed: bool = True
    ) -> List[str]:
        """
        Find shortest path using Dijkstra's algorithm.
        
        Args:
            graph: Graph object (NetworkX or similar)
            source: Source node ID
            target: Target node ID
            weight_attribute: Edge attribute for weights
            default_weight: Default weight for unweighted edges
            
        Returns:
            List of node IDs representing the shortest path
            
        Raises:
            ValueError: If source or target not found
            RuntimeError: If path finding fails
        """
        try:
            self.logger.info(f"Finding Dijkstra shortest path from {source} to {target}")

            # Validate nodes exist
            if not self._node_exists(graph, source):
                raise ValueError(f"Source node {source} not found")
            if not self._node_exists(graph, target):
                raise ValueError(f"Target node {target} not found")

            traversal_graph = graph if directed else self._make_undirected_view(graph)

            # Dijkstra's algorithm
            distances = {source: 0.0}
            previous = {}
            priority_queue = [(0.0, source)]
            visited = set()

            while priority_queue:
                current_distance, current_node = heapq.heappop(priority_queue)

                if current_node in visited:
                    continue

                visited.add(current_node)

                if current_node == target:
                    break

                # Explore neighbors
                for neighbor, edge_data in self._get_neighbors(traversal_graph, current_node):
                    if neighbor in visited:
                        continue
                    
                    # Get edge weight
                    weight = self._get_edge_weight(edge_data, weight_attribute, default_weight)
                    distance = current_distance + weight
                    
                    if neighbor not in distances or distance < distances[neighbor]:
                        distances[neighbor] = distance
                        previous[neighbor] = current_node
                        heapq.heappush(priority_queue, (distance, neighbor))
            
            # Reconstruct path
            if target not in previous and source != target:
                return []  # No path found
            
            path = []
            current = target
            while current is not None:
                path.append(current)
                current = previous.get(current)
            
            path.reverse()
            
            self.logger.info(f"Found path of length {len(path)}")
            return path
            
        except ValueError:
            # Re-raise ValueError for invalid nodes
            raise
        except Exception as e:
            self.logger.error(f"Dijkstra path finding failed: {str(e)}")
            raise RuntimeError(f"Path finding failed: {str(e)}")
    
    def a_star_search(
        self,
        graph: Any,
        source: str,
        target: str,
        heuristic: Callable[[str, str], float],
        weight_attribute: str = "weight",
        default_weight: float = 1.0
    ) -> List[str]:
        """
        Find shortest path using A* search with heuristic.
        
        Args:
            graph: Graph object (NetworkX or similar)
            source: Source node ID
            target: Target node ID
            heuristic: Heuristic function estimating distance to target
            weight_attribute: Edge attribute for weights
            default_weight: Default weight for unweighted edges
            
        Returns:
            List of node IDs representing the shortest path
            
        Raises:
            ValueError: If source or target not found
            RuntimeError: If path finding fails
        """
        try:
            self.logger.info(f"Finding A* path from {source} to {target}")
            
            # Validate nodes exist
            if not self._node_exists(graph, source):
                raise ValueError(f"Source node {source} not found")
            if not self._node_exists(graph, target):
                raise ValueError(f"Target node {target} not found")
            
            # A* algorithm
            open_set = [(0.0, source)]
            came_from = {}
            g_score = {source: 0.0}
            f_score = {source: heuristic(source, target)}
            closed_set = set()
            
            while open_set:
                current_f, current = heapq.heappop(open_set)
                
                if current in closed_set:
                    continue
                
                if current == target:
                    # Reconstruct path
                    path = []
                    while current is not None:
                        path.append(current)
                        current = came_from.get(current)
                    path.reverse()
                    
                    self.logger.info(f"Found A* path of length {len(path)}")
                    return path
                
                closed_set.add(current)
                
                # Explore neighbors
                for neighbor, edge_data in self._get_neighbors(graph, current):
                    if neighbor in closed_set:
                        continue
                    
                    # Get edge weight
                    weight = self._get_edge_weight(edge_data, weight_attribute, default_weight)
                    tentative_g = g_score[current] + weight
                    
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f_score[neighbor] = tentative_g + heuristic(neighbor, target)
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
            
            return []  # No path found
            
        except ValueError:
            raise
        except Exception as e:
            self.logger.error(f"A* path finding failed: {str(e)}")
            raise RuntimeError(f"Path finding failed: {str(e)}")
    
    def all_shortest_paths(
        self,
        graph: Any,
        source: str,
        weight_attribute: str = "weight",
        default_weight: float = 1.0
    ) -> Dict[str, List[str]]:
        """
        Find shortest paths from source to all other nodes.
        
        Args:
            graph: Graph object (NetworkX or similar)
            source: Source node ID
            weight_attribute: Edge attribute for weights
            default_weight: Default weight for unweighted edges
            
        Returns:
            Dictionary mapping target nodes to shortest paths
            
        Raises:
            ValueError: If source not found
            RuntimeError: If path finding fails
        """
        try:
            self.logger.info(f"Finding all shortest paths from {source}")
            
            # Validate source exists
            if not self._node_exists(graph, source):
                raise ValueError(f"Source node {source} not found")
            
            # Dijkstra's algorithm for all nodes
            distances = {source: 0.0}
            previous = defaultdict(list)
            priority_queue = [(0.0, source)]
            visited = set()
            
            while priority_queue:
                current_distance, current_node = heapq.heappop(priority_queue)
                
                if current_node in visited:
                    continue
                
                visited.add(current_node)
                
                # Explore neighbors
                for neighbor, edge_data in self._get_neighbors(graph, current_node):
                    if neighbor in visited:
                        continue
                    
                    # Get edge weight
                    weight = self._get_edge_weight(edge_data, weight_attribute, default_weight)
                    distance = current_distance + weight
                    
                    if neighbor not in distances or distance < distances[neighbor]:
                        distances[neighbor] = distance
                        previous[neighbor] = [current_node]
                        heapq.heappush(priority_queue, (distance, neighbor))
                    elif distance == distances[neighbor]:
                        previous[neighbor].append(current_node)
            
            # Reconstruct all paths
            paths = {}
            for target in distances:
                if target != source:
                    paths[target] = self._reconstruct_all_paths(previous, source, target)
            
            self.logger.info(f"Found paths to {len(paths)} nodes")
            return paths
            
        except ValueError:
            # Re-raise ValueError for invalid nodes
            raise
        except Exception as e:
            self.logger.error(f"All shortest paths finding failed: {str(e)}")
            raise RuntimeError(f"Path finding failed: {str(e)}")
    
    def bfs_shortest_path(
        self,
        graph: Any,
        source: str,
        target: str,
        directed: bool = True
    ) -> List[str]:
        """
        Find shortest path using BFS (unweighted).

        Args:
            graph: Graph object (NetworkX or similar)
            source: Source node ID
            target: Target node ID
            directed: If False, treat the graph as undirected for traversal

        Returns:
            List of node IDs representing the shortest path

        Raises:
            ValueError: If source or target not found
        """
        try:
            self.logger.info(f"Finding BFS shortest path from {source} to {target}")

            # Validate nodes exist
            if not self._node_exists(graph, source):
                raise ValueError(f"Source node {source} not found")
            if not self._node_exists(graph, target):
                raise ValueError(f"Target node {target} not found")

            traversal_graph = graph if directed else self._make_undirected_view(graph)

            # BFS algorithm
            queue = deque([(source, [source])])
            visited = {source}

            while queue:
                current, path = queue.popleft()

                if current == target:
                    self.logger.info(f"Found BFS path of length {len(path)}")
                    return path

                # Explore neighbors
                for neighbor, _ in self._get_neighbors(traversal_graph, current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))
            
            return []  # No path found
            
        except ValueError:
            # Re-raise ValueError for invalid nodes
            raise
        except Exception as e:
            self.logger.error(f"BFS path finding failed: {str(e)}")
            raise RuntimeError(f"Path finding failed: {str(e)}")
    
    def path_length(
        self,
        graph: Any,
        path: List[str],
        weight_attribute: str = "weight",
        default_weight: float = 1.0
    ) -> float:
        """
        Calculate total length of a path.
        
        Args:
            graph: Graph object (NetworkX or similar)
            path: List of node IDs representing the path
            weight_attribute: Edge attribute for weights
            default_weight: Default weight for unweighted edges
            
        Returns:
            Total path length
            
        Raises:
            ValueError: If path is invalid
        """
        if len(path) < 2:
            return 0.0
        
        total_length = 0.0
        
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]
            
            # Check if edge exists
            edge_data = self._get_edge_data(graph, current, next_node)
            if edge_data is None:
                raise ValueError(f"No edge found between {current} and {next_node}")
            
            # Get edge weight
            weight = self._get_edge_weight(edge_data, weight_attribute, default_weight)
            total_length += weight
        
        return total_length
    
    def find_shortest_path(
        self,
        graph: Any,
        source: str,
        target: str,
        **kwargs
    ) -> Optional[List[str]]:
        """Find shortest path between source and target (alias for bfs_shortest_path)."""
        result = self.bfs_shortest_path(graph, source, target)
        if isinstance(result, dict):
            return result.get("path")
        return result

    def find_k_shortest_paths(
        self,
        graph: Any,
        source: str,
        target: str,
        k: int,
        weight_attribute: str = "weight",
        default_weight: float = 1.0
    ) -> List[List[str]]:
        """
        Find k shortest paths using Yen's algorithm.
        
        Args:
            graph: Graph object (NetworkX or similar)
            source: Source node ID
            target: Target node ID
            k: Number of shortest paths to find
            weight_attribute: Edge attribute for weights
            default_weight: Default weight for unweighted edges
            
        Returns:
            List of k shortest paths (ordered by length)
            
        Raises:
            ValueError: If parameters are invalid
        """
        if k <= 0:
            raise ValueError("k must be positive")
        
        # Find first shortest path
        first_path = self.dijkstra_shortest_path(graph, source, target, weight_attribute, default_weight)
        if not first_path:
            return []
        
        paths = [first_path]
        candidates = []
        
        for i in range(1, k):
            # Generate candidate paths
            for j in range(len(paths[-1]) - 1):
                spur_node = paths[-1][j]
                root_path = paths[-1][:j + 1]
                
                # Temporarily remove edges
                removed_edges = []
                for path in paths:
                    if len(path) > j and path[:j + 1] == root_path:
                        if j + 1 < len(path):
                            edge_data = self._get_edge_data(graph, path[j], path[j + 1])
                            if edge_data is not None:
                                removed_edges.append((path[j], path[j + 1], edge_data))
                                self._remove_edge(graph, path[j], path[j + 1])
                
                # Temporarily remove nodes (except spur node and nodes that don't exist)
                removed_nodes = []
                for node in root_path[:-1]:
                    if node != spur_node and node != source and self._node_exists(graph, node):
                        removed_nodes.append(node)
                        self._remove_node(graph, node)
                
                # Find spur path
                spur_path = self.dijkstra_shortest_path(graph, spur_node, target, weight_attribute, default_weight)
                
                # Restore graph
                for node in removed_nodes:
                    self._restore_node(graph, node)
                for u, v, data in removed_edges:
                    self._restore_edge(graph, u, v, data)
                
                # Combine root and spur paths
                if spur_path:
                    candidate_path = root_path[:-1] + spur_path
                    if candidate_path not in candidates and candidate_path not in paths:
                        candidates.append(candidate_path)
        
        # Calculate path lengths and sort
        candidates_with_lengths = []
        for path in candidates:
            try:
                length = self.path_length(graph, path, weight_attribute, default_weight)
                candidates_with_lengths.append((path, length))
            except ValueError:
                # Skip invalid paths
                continue
        
        candidates_with_lengths.sort(key=lambda x: x[1])
        
        # Add shortest unique paths
        for path, length in candidates_with_lengths:
            if len(paths) < k and path not in paths:
                paths.append(path)
        
        return paths
    
    def _node_exists(self, graph: Any, node: str) -> bool:
        """Check if node exists in graph."""
        if hasattr(graph, 'has_node'):
            return graph.has_node(node)
        elif hasattr(graph, '__contains__'):
            return node in graph
        elif hasattr(graph, 'nodes'):
            # Handle NetworkX graphs and similar
            try:
                return node in list(graph.nodes())
            except (TypeError, AttributeError):
                return False
        return False
    
    def _make_undirected_view(self, graph: Any) -> Any:
        """Return an undirected view of the graph for bidirectional traversal.

        For NetworkX directed graphs this calls ``to_undirected()``, which
        preserves all edge attributes.  For graph types that have no such
        method the original object is returned as a fallback — callers that
        already expose undirected neighbors will still work correctly.
        """
        if hasattr(graph, "to_undirected"):
            return graph.to_undirected()
        return graph

    def _get_neighbors(self, graph: Any, node: str) -> List[Tuple[str, Any]]:
        """Get neighbors of a node with edge data."""
        neighbors = []
        
        if hasattr(graph, 'neighbors'):
            for _raw in graph.neighbors(node):
                neighbor = _raw.get("id") if isinstance(_raw, dict) else _raw
                edge_data = self._get_edge_data(graph, node, neighbor)
                neighbors.append((neighbor, edge_data))
        elif hasattr(graph, 'get_neighbors'):
            neighbor_list = graph.get_neighbors(node)
            for neighbor in neighbor_list:
                edge_data = self._get_edge_data(graph, node, neighbor)
                neighbors.append((neighbor, edge_data))
        
        return neighbors
    
    def _get_edge_data(self, graph: Any, u: str, v: str) -> Any:
        """Get edge data between two nodes."""
        if hasattr(graph, 'get_edge_data'):
            return graph.get_edge_data(u, v)
        elif hasattr(graph, 'edges'):
            return graph.edges.get((u, v), {})
        return {}
    
    def _get_edge_weight(self, edge_data: Any, weight_attribute: str, default_weight: float) -> float:
        """Get edge weight from edge data."""
        if isinstance(edge_data, dict):
            return edge_data.get(weight_attribute, default_weight)
        return default_weight
    
    def _remove_edge(self, graph: Any, u: str, v: str) -> None:
        """Remove edge from graph."""
        if hasattr(graph, 'remove_edge'):
            graph.remove_edge(u, v)
    
    def _restore_edge(self, graph: Any, u: str, v: str, data: Any) -> None:
        """Restore edge to graph."""
        if hasattr(graph, 'add_edge'):
            graph.add_edge(u, v, **data)
    
    def _remove_node(self, graph: Any, node: str) -> None:
        """Remove node from graph."""
        if hasattr(graph, 'remove_node'):
            graph.remove_node(node)
    
    def _restore_node(self, graph: Any, node: str) -> None:
        """Restore node to graph (implementation depends on graph type)."""
        # This is a simplified implementation
        # In practice, you'd need to restore the node and its connections
        pass
    
    def _reconstruct_all_paths(
        self,
        previous: Dict[str, List[str]],
        source: str,
        target: str
    ) -> List[List[str]]:
        """Reconstruct all shortest paths from previous dictionary."""
        if target == source:
            return [[source]]
        
        if target not in previous:
            return []
        
        paths = []
        for prev_node in previous[target]:
            for path in self._reconstruct_all_paths(previous, source, prev_node):
                paths.append(path + [target])
        
        return paths
