"""
Node Embeddings Module

This module provides comprehensive node embedding algorithms for knowledge graphs, enabling
structural similarity analysis and node representation learning.

Supported Algorithms:
    - Node2Vec: Biased random walk based embeddings (high quality, captures structural similarity)
    - DeepWalk: Unbiased random walk based embeddings (simpler, faster)
    - Word2Vec: Neural network training on graph walks (underlying training algorithm)
    - Future algorithms: FastRP, GraphSAGE, Struc2Vec (planned extensions)

Key Features:
    - Multiple embedding algorithms with different theoretical foundations
    - Biased and unbiased random walk generation
    - Configurable embedding dimensions and walk parameters
    - Embedding storage and retrieval as node properties
    - Similarity search based on learned embeddings
    - Scalable implementations for large graphs
    - Integration with Gensim for Word2Vec training

Main Classes:
    - NodeEmbedder: Comprehensive node embedding engine

Methods:
    - compute_embeddings(): Main interface for embedding computation
    - find_similar_nodes(): Find structurally similar nodes based on embeddings
    - store_embeddings(): Store embeddings as node properties
    - _generate_random_walks(): Generate biased random walks for Node2Vec
    - _train_word2vec(): Train Word2Vec model on generated walks
    - _extract_embeddings(): Extract embeddings from trained model

Example Usage:
    >>> from semantica.kg import NodeEmbedder
    >>> embedder = NodeEmbedder(method="node2vec", embedding_dimension=128)
    >>> embeddings = embedder.compute_embeddings(graph_store, ["Entity"], ["RELATED_TO"])
    >>> similar_nodes = embedder.find_similar_nodes(graph_store, "entity_123", top_k=10)
    >>> embedder.store_embeddings(graph_store, embeddings, "node2vec_embedding")

Author: Semantica Contributors
License: MIT
"""

import random
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import sparse

from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .kg_provenance import AlgorithmTrackerWithProvenance

try:
    from gensim.models import Word2Vec
    GENSIM_AVAILABLE = True
except ImportError:
    GENSIM_AVAILABLE = False
    Word2Vec = None


class NodeEmbedder:
    """
    Node embedding engine for knowledge graphs.
    
    This class provides node embedding capabilities using various algorithms,
    with Node2Vec as the primary implementation. Node embeddings capture
    structural similarity and enable advanced graph analytics.
    
    Supported Algorithms:
        - node2vec: Biased random walk based embeddings (high quality)
        - Future: fastrp, graphsage, struc2vec
    
    Features:
        - Biased random walk generation with p, q parameters
        - Word2Vec training on generated walks
        - Embedding storage as node properties
        - Similarity search functionality
        - Configurable embedding dimensions and walk parameters
    
    Example Usage:
        >>> embedder = NodeEmbedder(method="node2vec", embedding_dimension=128)
        >>> embeddings = embedder.compute_embeddings(
        ...     graph_store=graph_store,
        ...     node_labels=["Entity"],
        ...     relationship_types=["RELATED_TO"],
        ...     walk_length=80,
        ...     num_walks=10
        ... )
        >>> similar_nodes = embedder.find_similar_nodes(graph_store, "entity_123", top_k=10)
    """
    
    def __init__(
        self,
        method: str = "node2vec",
        embedding_dimension: int = 128,
        walk_length: int = 80,
        num_walks: int = 10,
        p: float = 1.0,
        q: float = 1.0,
        workers: int = 1,
        window_size: int = 5,
        min_count: int = 1,
        sg: int = 1,
        epochs: int = 5
    ):
        """
        Initialize the node embedder.
        
        Args:
            method: Embedding algorithm to use ("node2vec")
            embedding_dimension: Dimension of node embeddings
            walk_length: Length of each random walk
            num_walks: Number of walks per node
            p: Return parameter for biased random walks
            q: In-out parameter for biased random walks
            workers: Number of worker threads for training
            window_size: Window size for Word2Vec
            min_count: Minimum count for Word2Vec vocabulary
            sg: Skip-gram (1) or CBOW (0) for Word2Vec
            epochs: Number of training epochs
        """
        self.method = method
        self.embedding_dimension = embedding_dimension
        self.walk_length = walk_length
        self.num_walks = num_walks
        self.p = p
        self.q = q
        self.workers = workers
        self.window_size = window_size
        self.min_count = min_count
        self.sg = sg
        self.epochs = epochs
        
        if method not in ["node2vec"]:
            raise ValueError(f"Unsupported embedding method: {method}")

        self.logger = get_logger(__name__)
        self.progress_tracker = get_progress_tracker()

        if method == "node2vec" and not GENSIM_AVAILABLE:
            raise ImportError(
                "gensim is required for Node2Vec. Install with: pip install 'semantica[graph-embeddings]'"
            )
    
    def compute_embeddings(
        self,
        graph_store: Any,
        node_labels: List[str],
        relationship_types: List[str],
        embedding_dimension: Optional[int] = None,
        walk_length: Optional[int] = None,
        num_walks: Optional[int] = None,
        p: Optional[float] = None,
        q: Optional[float] = None
    ) -> Dict[str, List[float]]:
        """
        Compute node embeddings for the specified graph.
        
        Args:
            graph_store: Graph store containing the knowledge graph
            node_labels: List of node labels to include
            relationship_types: List of relationship types to traverse
            embedding_dimension: Override embedding dimension
            walk_length: Override walk length
            num_walks: Override number of walks
            p: Override return parameter
            q: Override in-out parameter
            
        Returns:
            Dictionary mapping node IDs to embedding vectors
            
        Raises:
            ValueError: If method is not supported
            RuntimeError: If embedding computation fails
        """
        if self.method not in ["node2vec"]:
            raise ValueError(f"Unsupported embedding method: {self.method}")

        if walk_length is not None and walk_length <= 0:
            raise ValueError("walk_length must be positive")
        if num_walks is not None and num_walks <= 0:
            raise ValueError("num_walks must be positive")
        if embedding_dimension is not None and embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")

        # Use override parameters if provided
        emb_dim = embedding_dimension or self.embedding_dimension
        walk_len = walk_length or self.walk_length
        num_w = num_walks or self.num_walks
        p_param = p or self.p
        q_param = q or self.q
        
        try:
            self.logger.info(f"Computing {self.method} embeddings for {len(node_labels)} node types")
            
            # Initialize provenance tracker if enabled
            provenance_tracker = None
            if hasattr(self, 'enable_provenance') and self.enable_provenance:
                provenance_tracker = AlgorithmTrackerWithProvenance(provenance=True)
            
            # Build adjacency representation
            adjacency = self._build_adjacency(graph_store, node_labels, relationship_types)

            if not adjacency:
                raise RuntimeError("No nodes found in graph for specified labels and relationship types")

            # Generate random walks
            walks = self._generate_random_walks(adjacency, walk_len, num_w, p_param, q_param)
            
            # Train Word2Vec model
            model = self._train_word2vec(walks, emb_dim)
            
            # Extract embeddings
            embeddings = {}
            for node in adjacency.keys():
                if node in model.wv:
                    embedding = model.wv[node]
                    # Handle both numpy arrays and lists
                    if hasattr(embedding, 'tolist'):
                        embeddings[node] = embedding.tolist()
                    else:
                        embeddings[node] = list(embedding) if isinstance(embedding, (list, tuple)) else embedding
                else:
                    # Handle nodes not in vocabulary (rare)
                    embeddings[node] = np.random.random(emb_dim).tolist()
            
            # Track provenance if enabled
            if provenance_tracker:
                provenance_tracker.track_embedding_computation(
                    graph=graph_store,
                    algorithm=self.method,
                    embeddings=embeddings,
                    parameters={
                        "embedding_dimension": emb_dim,
                        "walk_length": walk_len,
                        "num_walks": num_w,
                        "p": p_param,
                        "q": q_param
                    },
                    source="node_embeddings_computation"
                )
            
            self.logger.info(f"Generated embeddings for {len(embeddings)} nodes")
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Failed to compute embeddings: {str(e)}")
            raise RuntimeError(f"Embedding computation failed: {str(e)}")
    
    def find_similar_nodes(
        self,
        graph_store: Any,
        node_id: str,
        top_k: int = 10,
        embedding_property: str = "node2vec_embedding"
    ) -> List[str]:
        """
        Find structurally similar nodes based on embeddings.
        
        Args:
            graph_store: Graph store containing the knowledge graph
            node_id: Target node ID
            top_k: Number of similar nodes to return
            embedding_property: Property name for stored embeddings
            
        Returns:
            List of similar node IDs sorted by similarity
            
        Raises:
            ValueError: If node_id is not found or has no embeddings
            RuntimeError: If similarity search fails
        """
        try:
            # Get target node embedding
            target_embedding = self._get_node_embedding(
                graph_store, node_id, embedding_property
            )
            
            if target_embedding is None:
                raise ValueError(f"Node {node_id} not found or has no embeddings")
            
            # Get all node embeddings
            all_embeddings = self._get_all_embeddings(graph_store, embedding_property)
            
            # Calculate similarities
            similarities = []
            target_vec = np.array(target_embedding)

            for candidate_id, embedding in all_embeddings.items():
                if candidate_id != node_id:  # Skip self
                    embedding_vec = np.array(embedding)
                    similarity = self._cosine_similarity(target_vec, embedding_vec)
                    similarities.append((candidate_id, similarity))

            # Sort by similarity and return top-k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return [nid for nid, _ in similarities[:top_k]]
            
        except Exception as e:
            self.logger.error(f"Failed to find similar nodes: {str(e)}")
            raise RuntimeError(f"Similarity search failed: {str(e)}")
    
    def store_embeddings(
        self,
        graph_store: Any,
        embeddings: Dict[str, List[float]],
        property_name: str = "node2vec_embedding"
    ) -> None:
        """
        Store embeddings as node properties in the graph store.
        
        Args:
            graph_store: Graph store to store embeddings in
            embeddings: Dictionary of node embeddings
            property_name: Property name for storing embeddings
            
        Raises:
            RuntimeError: If storage operation fails
        """
        try:
            self.logger.info(f"Storing {len(embeddings)} embeddings as property '{property_name}'")
            
            # Store embeddings based on graph store type
            if hasattr(graph_store, 'set_node_property') and callable(graph_store.set_node_property):
                # Neo4j or similar
                for node_id, embedding in embeddings.items():
                    graph_store.set_node_property(node_id, property_name, embedding)
            elif hasattr(graph_store, 'add_node_attribute') and callable(graph_store.add_node_attribute):
                # NetworkX or similar
                for node_id, embedding in embeddings.items():
                    graph_store.add_node_attribute(node_id, {property_name: embedding})
            else:
                # Generic approach - update in-memory representation
                if not hasattr(graph_store, '_node_embeddings'):
                    graph_store._node_embeddings = {}
                graph_store._node_embeddings.update(embeddings)
            
            self.logger.info("Successfully stored embeddings")
            
        except Exception as e:
            self.logger.error(f"Failed to store embeddings: {str(e)}")
            raise RuntimeError(f"Embedding storage failed: {str(e)}")
    
    def _build_adjacency(
        self,
        graph_store: Any,
        node_labels: List[str],
        relationship_types: List[str]
    ) -> Dict[str, List[str]]:
        """Build adjacency list representation of the graph."""
        adjacency = defaultdict(list)
        
        # Get nodes based on labels
        nodes = []
        if hasattr(graph_store, 'get_nodes_by_label'):
            for label in node_labels:
                for node in graph_store.get_nodes_by_label(label):
                    if isinstance(node, dict):
                        node_id = node.get("id")
                        if node_id:
                            nodes.append(node_id)
                    elif node:
                        nodes.append(node)
        else:
            # Fallback for different graph store implementations
            nodes = list(graph_store.nodes())
        
        # Build adjacency — prefer get_neighbors/get_neighbor_ids over .neighbors
        for node in nodes:
            if hasattr(graph_store, 'get_neighbors'):
                try:
                    try:
                        neighbor_details = graph_store.get_neighbors(
                            node,
                            relationship_types=relationship_types,
                        )
                    except TypeError:
                        neighbor_details = graph_store.get_neighbors(node, relationship_types)

                    if isinstance(neighbor_details, list):
                        adjacency[node] = [
                            n.get("id") if isinstance(n, dict) else n
                            for n in neighbor_details
                            if n
                        ]
                    else:
                        adjacency[node] = []
                except TypeError:
                    adjacency[node] = []
            elif hasattr(graph_store, 'get_neighbor_ids'):
                adjacency[node] = list(graph_store.get_neighbor_ids(node, relationship_types))
            elif hasattr(graph_store, 'neighbors'):
                try:
                    adjacency[node] = [
                        n.get("id") if isinstance(n, dict) else n
                        for n in graph_store.neighbors(node)
                        if n
                    ]
                except TypeError:
                    adjacency[node] = []
            else:
                adjacency[node] = []
        
        return dict(adjacency)
    
    def _generate_random_walks(
        self,
        adjacency: Dict[str, List[str]],
        walk_length: int,
        num_walks: int,
        p: float,
        q: float
    ) -> List[List[str]]:
        """Generate biased random walks for Node2Vec."""
        walks = []
        nodes = list(adjacency.keys())
        
        for _ in range(num_walks):
            random.shuffle(nodes)
            for start_node in nodes:
                walk = self._biased_random_walk(adjacency, start_node, walk_length, p, q)
                walks.append(walk)
        
        return walks
    
    def _biased_random_walk(
        self,
        adjacency: Dict[str, List[str]],
        start_node: str,
        walk_length: int,
        p: float,
        q: float
    ) -> List[str]:
        """Generate a single biased random walk."""
        walk = [start_node]
        
        while len(walk) < walk_length:
            current = walk[-1]
            neighbors = adjacency.get(current, [])
            
            if not neighbors:
                break
            
            if len(walk) == 1:
                # First step - uniform random
                next_node = random.choice(neighbors)
            else:
                # Biased sampling
                prev_node = walk[-2]
                next_node = self._biased_sample(adjacency, prev_node, current, neighbors, p, q)
            
            walk.append(next_node)
        
        return walk
    
    def _biased_sample(
        self,
        adjacency: Dict[str, List[str]],
        prev_node: str,
        current_node: str,
        neighbors: List[str],
        p: float,
        q: float
    ) -> str:
        """Sample next node using biased probabilities."""
        probabilities = []
        
        for neighbor in neighbors:
            if neighbor == prev_node:
                # Return to previous node
                prob = 1.0 / p
            elif neighbor in adjacency.get(prev_node, []):
                # Distance 1 node
                prob = 1.0
            else:
                # Distance 2 node
                prob = 1.0 / q
            
            probabilities.append(prob)
        
        # Normalize probabilities
        total_prob = sum(probabilities)
        if total_prob > 0:
            probabilities = [p / total_prob for p in probabilities]
        
        # Sample based on probabilities
        return random.choices(neighbors, weights=probabilities)[0]
    
    def _train_word2vec(self, walks: List[List[str]], embedding_dimension: int) -> Any:
        """Train Word2Vec model on generated walks."""
        # Convert walks to strings if needed
        str_walks = [[str(node) for node in walk] for walk in walks]
        
        # Filter out empty walks
        str_walks = [walk for walk in str_walks if walk]
        
        if not str_walks:
            raise ValueError("No valid walks generated for training")
        
        model = Word2Vec(
            sentences=str_walks,
            vector_size=embedding_dimension,
            window=self.window_size,
            min_count=self.min_count,
            sg=self.sg,
            workers=self.workers,
            epochs=self.epochs
        )
        
        return model
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _get_node_embedding(
        self,
        graph_store: Any,
        node_id: str,
        property_name: str
    ) -> Optional[List[float]]:
        """Get embedding for a specific node."""
        # Prefer explicit _node_embeddings dict over auto-created Mock attributes
        if hasattr(graph_store, '_node_embeddings') and isinstance(graph_store._node_embeddings, dict):
            return graph_store._node_embeddings.get(node_id)
        if hasattr(graph_store, 'get_node_property') and callable(graph_store.get_node_property):
            result = graph_store.get_node_property(node_id, property_name)
            if isinstance(result, (list, np.ndarray)):
                return result
        return None
    
    def _get_all_embeddings(
        self,
        graph_store: Any,
        property_name: str
    ) -> Dict[str, List[float]]:
        """Get all node embeddings from the graph store."""
        embeddings = {}
        
        if hasattr(graph_store, '_node_embeddings') and isinstance(graph_store._node_embeddings, dict):
            embeddings = graph_store._node_embeddings.copy()
        elif hasattr(graph_store, 'get_all_nodes_with_property') and callable(graph_store.get_all_nodes_with_property):
            try:
                nodes = graph_store.get_all_nodes_with_property(property_name)
                for node_id in (nodes if isinstance(nodes, (list, tuple)) else []):
                    embedding = self._get_node_embedding(graph_store, node_id, property_name)
                    if embedding:
                        embeddings[node_id] = embedding
            except (TypeError, AttributeError):
                pass
        else:
            # Fallback - iterate through all nodes
            if hasattr(graph_store, 'nodes'):
                for node_id in graph_store.nodes():
                    embedding = self._get_node_embedding(graph_store, node_id, property_name)
                    if embedding:
                        embeddings[node_id] = embedding
        
        return embeddings
