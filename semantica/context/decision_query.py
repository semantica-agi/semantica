"""
Decision Query Module

Advanced decision querying with precedent search, filtering, and hybrid search
operations using KG algorithms and vector store integration.

Core Features:
    - Precedent search with multiple similarity measures
    - Decision filtering by category, time, and entities
    - Hybrid search combining semantic and structural similarity
    - Multi-hop reasoning for complex decision relationships
    - Decision path tracing and causality analysis

Decision Tracking Integration:
    - Complete decision lifecycle management
    - Decision recording and querying with full context
    - Decision metadata and relationship tracking
    - Decision analytics and statistics
    - Decision influence and relationship analysis

KG Algorithm Integration:
    - Centrality Analysis: Degree, betweenness, closeness, eigenvector centrality
    - Community Detection: Modularity-based community identification
    - Node Embeddings: Node2Vec embeddings for similarity analysis
    - Path Finding: Shortest path and advanced path algorithms
    - Link Prediction: Relationship prediction between decisions
    - Similarity Calculation: Multi-type similarity measures

Vector Store Integration:
    - Hybrid Search: Semantic + structural similarity
    - Custom Similarity Weights: Configurable scoring
    - Advanced Precedent Search: KG-enhanced similarity
    - Multi-Embedding Support: Multiple embedding types
    - Metadata Filtering: Advanced filtering capabilities
    - Policy Engine: Policy enforcement and compliance checking

Enhanced Methods:
    - find_precedents_hybrid(): Hybrid search with KG and vector store
    - find_precedents_advanced(): Enhanced search with custom weights
    - analyze_decision_influence(): Analyze influence using KG algorithms
    - predict_decision_relationships(): Predict decision relationships
    - multi_hop_reasoning(): Multi-hop reasoning for complex relationships
    - trace_decision_path(): Trace decision paths and causality
    - find_similar_decisions(): Find similar decisions with advanced similarity
    - get_decision_statistics(): Get comprehensive decision analytics

Search Capabilities:
    - Semantic Search: Text-based similarity using embeddings
    - Structural Search: Graph structure-based similarity
    - Hybrid Search: Combined semantic and structural similarity
    - Temporal Search: Time-based decision filtering
    - Category Search: Decision category-based filtering
    - Entity Search: Entity-based decision filtering

Example Usage:
    >>> from semantica.context import DecisionQuery
    >>> query = DecisionQuery(graph_store=kg, vector_store=vs,
    ...                      advanced_analytics=True,
    ...                      centrality_analysis=True,
    ...                      community_detection=True,
    ...                      node_embeddings=True)
    >>> precedents = query.find_precedents_hybrid("Loan application",
    ...                                           category="approval",
    ...                                           limit=10)
    >>> influence = query.analyze_decision_influence(decision_id)
    >>> predictions = query.predict_decision_relationships(decision_id)
    >>> similar = query.find_similar_decisions("Credit decision",
    ...                                        similarity_weights={"semantic": 0.6,
    ...                                                          "structural": 0.4})

Production Use Cases:
    - Banking: Loan approval precedents, risk assessment decisions
    - Healthcare: Treatment decisions, diagnostic precedents
    - Legal: Case law analysis, legal precedent search
    - Insurance: Claim decisions, underwriting precedents
    - Government: Policy decisions, regulatory compliance
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import numpy as np

from ..embeddings import EmbeddingGenerator
from ..graph_store import GraphStore
from ..utils.logging import get_logger
from .context_graph import ContextGraph
from .decision_models import Decision, PolicyException


try:
    from ..kg import (
        CentralityCalculator, CommunityDetector, PathFinder, 
        NodeEmbedder, SimilarityCalculator, LinkPredictor
    )
    from ..vector_store import HybridSearch, HybridSimilarityCalculator
    KG_AVAILABLE = True
except ImportError:
    KG_AVAILABLE = False


class DecisionQuery:
    """
    Queries decisions with hybrid search capabilities.
    
    This class provides methods for finding precedents, filtering decisions,
    and performing multi-hop reasoning with hybrid search combining semantic
    and structural embeddings.
    """
    
    def __init__(
        self,
        graph_store: GraphStore,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        vector_store: Optional[Any] = None,
        advanced_analytics: bool = True,
        node_embeddings: bool = True,
        centrality_analysis: bool = True,
        community_detection: bool = True,
        link_prediction: bool = True
    ):
        """
        Initialize DecisionQuery with optional advanced features.
        
        Args:
            graph_store: Graph database instance
            embedding_generator: Optional embedding generator for semantic search
            vector_store: Optional vector store for hybrid search
            advanced_analytics: Enable advanced graph analytics (requires semantica.kg)
            node_embeddings: Enable Node2Vec embeddings (requires semantica.kg)
            centrality_analysis: Enable centrality measures (requires semantica.kg)
            community_detection: Enable community detection (requires semantica.kg)
            link_prediction: Enable link prediction (requires semantica.kg)
        """
        self.graph_store = graph_store
        self.embedding_generator = embedding_generator
        self.vector_store = vector_store
        self.logger = get_logger(__name__)
        
        # Initialize advanced components if available and enabled
        self.kg_components = {}
        self.vector_components = {}
        
        if KG_AVAILABLE and advanced_analytics:
            try:
                if centrality_analysis:
                    self.kg_components["centrality_calculator"] = CentralityCalculator()
                if community_detection:
                    self.kg_components["community_detector"] = CommunityDetector()
                if node_embeddings:
                    try:
                        self.kg_components["node_embedder"] = NodeEmbedder()
                    except ImportError as e:
                        self.logger.warning(f"Node2Vec embeddings disabled: {e}")
                self.kg_components["path_finder"] = PathFinder()
                self.kg_components["similarity_calculator"] = SimilarityCalculator()
                if link_prediction:
                    self.kg_components["link_predictor"] = LinkPredictor()
                
                self.logger.info("Advanced KG components initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize KG components: {e}")
                self.kg_components = {}
        
        # Initialize vector store components
        if vector_store:
            try:
                self.vector_components["hybrid_search"] = HybridSearch(vector_store)
                self.vector_components["hybrid_similarity"] = HybridSimilarityCalculator()
                self.logger.info("Vector store components initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize vector components: {e}")
                self.vector_components = {}
        
        # Cache for computed metrics
        self._cache = {}
    
    def find_precedents_hybrid(
        self,
        scenario: str,
        category: Optional[str] = None,
        limit: int = 10,
        use_advanced_features: bool = True,
        similarity_weights: Optional[Dict[str, float]] = None
    ) -> List[Decision]:
        """
        Find similar past decisions using hybrid search (semantic + structural).
        
        Args:
            scenario: Scenario description to find precedents for
            category: Optional category filter
            limit: Maximum number of results
            use_advanced_features: Use advanced KG and vector store features if available
            similarity_weights: Weights for different similarity components
            
        Returns:
            List of similar decisions
        """
        try:
            # Default similarity weights
            default_weights = {
                "semantic": 0.4,
                "structural": 0.3,
                "text": 0.2,
                "category": 0.1
            }
            weights = similarity_weights or default_weights
            
            # Method 1: Try vector store hybrid search first
            if use_advanced_features and "hybrid_search" in self.vector_components:
                try:
                    vector_results = self._find_precedents_vector_store(
                        scenario, category, limit, weights
                    )
                    if vector_results:
                        self.logger.info(f"Found {len(vector_results)} precedents using vector store")
                        return vector_results
                except Exception as e:
                    self.logger.warning(f"Vector store search failed, falling back to graph search: {e}")
            
            # Method 2: Enhanced graph search with KG algorithms
            if use_advanced_features and self.kg_components:
                try:
                    graph_results = self._find_precedents_enhanced_graph(
                        scenario, category, limit, weights
                    )
                    if graph_results:
                        self.logger.info(f"Found {len(graph_results)} precedents using enhanced graph search")
                        return graph_results
                except Exception as e:
                    self.logger.warning(f"Enhanced graph search failed, falling back to basic search: {e}")
            
            # Method 3: Basic graph search (backward compatible)
            return self._find_precedents_basic(scenario, category, limit)
            
        except Exception as e:
            self.logger.error(f"Failed to find precedents: {e}")
            raise
    
    def _find_precedents_vector_store(
        self, scenario: str, category: Optional[str], limit: int, weights: Dict[str, float]
    ) -> List[Decision]:
        """Find precedents using vector store hybrid search."""
        hybrid_search = self.vector_components["hybrid_search"]
        
        filters = {}
        if category:
            filters["category"] = category
        
        results = hybrid_search.search(
            query=scenario,
            filters=filters,
            limit=limit
        )
        
        decisions = []
        for result in results:
            decision = self._vector_result_to_decision(result)
            if decision:
                # Calculate combined similarity score
                similarity_score = self._calculate_combined_similarity(
                    scenario, decision, weights, result
                )
                decision.metadata["similarity_score"] = similarity_score
                decisions.append(decision)
        
        # Sort by similarity
        decisions.sort(key=lambda d: d.metadata.get("similarity_score", 0), reverse=True)
        return decisions
    
    def _find_precedents_enhanced_graph(
        self, scenario: str, category: Optional[str], limit: int, weights: Dict[str, float]
    ) -> List[Decision]:
        """Find precedents using enhanced graph search with KG algorithms."""
        # Get base decisions from graph
        decisions = self._find_precedents_basic(scenario, category, limit * 2)
        
        # Enhance with KG algorithms
        enhanced_decisions = []
        
        for decision in decisions:
            similarity_score = 0.0
            
            # Text similarity
            text_sim = self._calculate_text_similarity(decision.scenario, scenario)
            similarity_score += weights["text"] * text_sim
            
            # Category similarity
            category_sim = 1.0 if decision.category == category else 0.0
            similarity_score += weights["category"] * category_sim
            
            # Semantic similarity (if embeddings available)
            if self.embedding_generator:
                try:
                    query_embedding = self.embedding_generator.generate(scenario)
                    if decision.reasoning_embedding:
                        semantic_sim = self._cosine_similarity(query_embedding, decision.reasoning_embedding)
                        similarity_score += weights["semantic"] * semantic_sim
                except Exception:
                    pass  # Continue without semantic similarity
            
            # Structural similarity (if Node2Vec available)
            if "node_embedder" in self.kg_components:
                try:
                    structural_sim = self._calculate_structural_similarity(decision, scenario)
                    similarity_score += weights["structural"] * structural_sim
                except Exception:
                    pass  # Continue without structural similarity
            
            # Centrality boosting (if available)
            if "centrality_calculator" in self.kg_components:
                try:
                    centrality_boost = self._get_centrality_boost(decision.decision_id)
                    similarity_score *= (1.0 + centrality_boost)
                except Exception:
                    pass  # Continue without centrality boost
            
            decision.metadata["similarity_score"] = similarity_score
            enhanced_decisions.append(decision)
        
        # Sort by similarity and limit results
        enhanced_decisions.sort(key=lambda d: d.metadata.get("similarity_score", 0), reverse=True)
        return enhanced_decisions[:limit]
    
    def _find_precedents_basic(
        self, scenario: str, category: Optional[str], limit: int
    ) -> List[Decision]:
        """Basic precedent search (backward compatible)."""
        # Generate query embedding
        query_embedding = None
        if self.embedding_generator:
            query_embedding = self.embedding_generator.generate(scenario)
        
        # Native ContextGraph flow
        if type(self.graph_store) is ContextGraph:
            nodes = self.graph_store.find_nodes(node_type="Decision")
            decisions = []
            for node in nodes:
                metadata = node.get("metadata", {}).get("properties", node.get("metadata", {}))
                if category and metadata.get("category") != category:
                    continue
                
                # Format to conform to _dict_to_decision
                core_fields = {
                    "category", "scenario", "reasoning", "outcome", "confidence", 
                    "timestamp", "decision_maker", "reasoning_embedding", "node2vec_embedding"
                }
                custom_metadata = {k: v for k, v in metadata.items() if k not in core_fields}
                decision_data = {"id": node.get("id"), "metadata": custom_metadata}
                decision_data.update({k: v for k, v in metadata.items() if k in core_fields})
                
                try:
                    decision = self._dict_to_decision(decision_data)
                except KeyError:
                    continue
                
                if query_embedding and decision.reasoning_embedding:
                    similarity = self._cosine_similarity(
                        query_embedding, decision.reasoning_embedding
                    )
                    decision.metadata["similarity_score"] = similarity
                decisions.append(decision)
            
            if query_embedding:
                decisions.sort(
                    key=lambda d: d.metadata.get("similarity_score", 0),
                    reverse=True
                )
            
            self.logger.info(f"Found {min(len(decisions), limit)} precedents for scenario")
            return decisions[:limit]

        # Build base Cypher query
        query_parts = ["MATCH (d:Decision)"]
        where_conditions = []
        params = {"limit": limit}
        
        if category:
            where_conditions.append("d.category = $category")
            params["category"] = category
        
        if where_conditions:
            query_parts.append(f"WHERE {' AND '.join(where_conditions)}")
        
        query_parts.append("RETURN d")
        query_parts.append("LIMIT $limit")
        
        query = " ".join(query_parts)
        results = self._extract_records(self.graph_store.execute_query(query, params))

        decisions = []
        for record in results:
            decision_data = record.get("d") if isinstance(record, dict) else None
            if not isinstance(decision_data, dict):
                decision_data = record if isinstance(record, dict) else {}
            decision = self._dict_to_decision(decision_data)
            
            # Calculate similarity if embedding available
            if query_embedding and decision.reasoning_embedding:
                similarity = self._cosine_similarity(
                    query_embedding, decision.reasoning_embedding
                )
                # Store similarity in metadata for ranking
                decision.metadata["similarity_score"] = similarity
            
            decisions.append(decision)
        
        # Sort by similarity if available
        if query_embedding:
            decisions.sort(
                key=lambda d: d.metadata.get("similarity_score", 0),
                reverse=True
            )
        
        self.logger.info(f"Found {len(decisions)} precedents for scenario")
        return decisions[:limit]
    
    def find_by_category(self, category: str, limit: int = 100) -> List[Decision]:
        """
        Filter decisions by category.
        
        Args:
            category: Decision category
            limit: Maximum number of results
            
        Returns:
            List of decisions in the category
        """
        try:
            if type(self.graph_store) is ContextGraph:
                nodes = self.graph_store.find_nodes("Decision")
                decisions = []
                for node in nodes:
                    metadata = node.get("metadata", {}).get("properties", node.get("metadata", {}))
                    if metadata.get("category") == category:
                        core_fields = {
                            "category", "scenario", "reasoning", "outcome", "confidence", 
                            "timestamp", "decision_maker", "reasoning_embedding", "node2vec_embedding"
                        }
                        custom_metadata = {k: v for k, v in metadata.items() if k not in core_fields}
                        decision_data = {"id": node.get("id"), "metadata": custom_metadata}
                        decision_data.update({k: v for k, v in metadata.items() if k in core_fields})
                        
                        try:
                            decisions.append(self._dict_to_decision(decision_data))
                        except KeyError:
                            continue
                
                decisions.sort(key=lambda d: d.timestamp, reverse=True)
                self.logger.info(f"Found {min(len(decisions), limit)} decisions in category {category}")
                return decisions[:limit]

            query = """
            MATCH (d:Decision {category: $category})
            RETURN d
            ORDER BY d.timestamp DESC
            LIMIT $limit
            """
            results = self.graph_store.execute_query(query, {
                "category": category,
                "limit": limit
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("d") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decisions.append(self._dict_to_decision(decision_data))
            
            self.logger.info(f"Found {len(decisions)} decisions in category {category}")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to find decisions by category: {e}")
            raise
    
    def find_by_entity(self, entity_id: str, limit: int = 100) -> List[Decision]:
        """
        Find decisions about specific entities.
        
        Args:
            entity_id: Entity ID to search for
            limit: Maximum number of results
            
        Returns:
            List of decisions about the entity
        """
        try:
            if type(self.graph_store) is ContextGraph:
                edges = self.graph_store.find_edges(edge_type="ABOUT")
                decision_ids = {
                    e["source"] for e in edges 
                    if e["target"] == entity_id
                }
                
                decisions = []
                for d_id in decision_ids:
                    node = self.graph_store.find_node(d_id)
                    if node and node.get("type") == "Decision":
                        metadata = node.get("metadata", {}).get("properties", node.get("metadata", {}))
                        core_fields = {
                            "category", "scenario", "reasoning", "outcome", "confidence", 
                            "timestamp", "decision_maker", "reasoning_embedding", "node2vec_embedding"
                        }
                        custom_metadata = {k: v for k, v in metadata.items() if k not in core_fields}
                        decision_data = {"id": node.get("id"), "metadata": custom_metadata}
                        decision_data.update({k: v for k, v in metadata.items() if k in core_fields})
                        
                        try:
                            decisions.append(self._dict_to_decision(decision_data))
                        except KeyError:
                            continue
                
                decisions.sort(key=lambda d: d.timestamp, reverse=True)
                self.logger.info(f"Found {min(len(decisions), limit)} decisions about entity {entity_id}")
                return decisions[:limit]

            query = """
            MATCH (d:Decision)-[:ABOUT]->(e)
            WHERE e.id = $entity_id OR e.entity_id = $entity_id
            RETURN d
            ORDER BY d.timestamp DESC
            LIMIT $limit
            """
            results = self.graph_store.execute_query(query, {
                "entity_id": entity_id,
                "limit": limit
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("d") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decisions.append(self._dict_to_decision(decision_data))
            
            self.logger.info(f"Found {len(decisions)} decisions about entity {entity_id}")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to find decisions by entity: {e}")
            raise
    
    def find_by_time_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 100
    ) -> List[Decision]:
        """
        Temporal filtering of decisions.
        
        Args:
            start: Start datetime
            end: End datetime
            limit: Maximum number of results
            
        Returns:
            List of decisions in time range
        """
        if end <= start:
            raise ValueError("End time must be after start time")
        try:
            if type(self.graph_store) is ContextGraph:
                nodes = self.graph_store.find_nodes("Decision")
                decisions = []
                for node in nodes:
                    metadata = node.get("metadata", {}).get("properties", node.get("metadata", {}))
                    ts_val = metadata.get("timestamp")
                    if not ts_val:
                        continue
                    
                    if isinstance(ts_val, str):
                        try:
                            dt = datetime.fromisoformat(ts_val)
                        except ValueError:
                            continue
                    elif isinstance(ts_val, datetime):
                        dt = ts_val
                    else:
                        continue
                    
                    # Ensure dt is naive or both are aware
                    if start.tzinfo is not None and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=start.tzinfo)
                    elif start.tzinfo is None and dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)

                    if start <= dt <= end:
                        core_fields = {
                            "category", "scenario", "reasoning", "outcome", "confidence", 
                            "timestamp", "decision_maker", "reasoning_embedding", "node2vec_embedding"
                        }
                        custom_metadata = {k: v for k, v in metadata.items() if k not in core_fields}
                        decision_data = {"id": node.get("id"), "metadata": custom_metadata}
                        decision_data.update({k: v for k, v in metadata.items() if k in core_fields})
                        
                        try:
                            decisions.append(self._dict_to_decision(decision_data))
                        except KeyError:
                            continue
                            
                decisions.sort(key=lambda d: d.timestamp, reverse=True)
                self.logger.info(f"Found {min(len(decisions), limit)} decisions in time range")
                return decisions[:limit]

            query = """
            MATCH (d:Decision)
            WHERE d.timestamp >= $start AND d.timestamp <= $end
            RETURN d
            ORDER BY d.timestamp DESC
            LIMIT $limit
            """
            results = self.graph_store.execute_query(query, {
                "start": start,
                "end": end,
                "limit": limit
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("d") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decisions.append(self._dict_to_decision(decision_data))
            
            self.logger.info(f"Found {len(decisions)} decisions in time range")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to find decisions by time range: {e}")
            raise
    
    def multi_hop_reasoning(
        self,
        start_entity: str,
        query_context: str,
        max_hops: int = 3
    ) -> List[Decision]:
        """
        Multi-hop traversal for context assembly.
        
        Args:
            start_entity: Starting entity ID
            query_context: Context for the query
            max_hops: Maximum number of hops to traverse
            
        Returns:
            List of relevant decisions
        """
        if not (1 <= max_hops <= 10):
            raise ValueError("max_hops must be between 1 and 10")
        try:
            if type(self.graph_store) is ContextGraph:
                from collections import deque
                # Use BFS to find all Decisions within max_hops
                queue = deque([(start_entity, 0)])
                visited = {start_entity}
                decisions = []
                
                while queue:
                    current_node_id, current_hop = queue.popleft()
                    
                    if current_hop > 0:
                        node = self.graph_store.find_node(current_node_id)
                        if node and node.get("type") == "Decision":
                            metadata = node.get("metadata", {}).get("properties", node.get("metadata", {}))
                            core_fields = {
                                "category", "scenario", "reasoning", "outcome", "confidence", 
                                "timestamp", "decision_maker", "reasoning_embedding", "node2vec_embedding"
                            }
                            custom_metadata = {k: v for k, v in metadata.items() if k not in core_fields}
                            decision_data = {"id": node.get("id"), "metadata": custom_metadata}
                            decision_data.update({k: v for k, v in metadata.items() if k in core_fields})
                            
                            try:
                                decision = self._dict_to_decision(decision_data)
                                decision.metadata["hop_count"] = current_hop
                                decisions.append(decision)
                            except KeyError:
                                pass
                                
                    if current_hop < max_hops:
                        # Undirected traversal: Get both incoming and outgoing neighbors
                        neighbors = []
                        # Outgoing edges
                        for edge in self.graph_store._adjacency.get(current_node_id, []):
                            neighbors.append(edge.target_id)
                        # Incoming edges
                        for src_id, edges in self.graph_store._adjacency.items():
                            for edge in edges:
                                if edge.target_id == current_node_id:
                                    neighbors.append(src_id)
                                    
                        for n_id in neighbors:
                            if n_id not in visited:
                                visited.add(n_id)
                                queue.append((n_id, current_hop + 1))
                                
                # Sort by hop_count then timestamp desc
                decisions.sort(key=lambda d: (d.metadata.get("hop_count", 0), -d.timestamp.timestamp()))
                self.logger.info(f"Found {len(decisions)} decisions via multi-hop reasoning")
                return decisions

            # Build multi-hop query
            query = f"""
            MATCH (start {{id: $start_entity}})
            CALL {{
                WITH start
                MATCH path = (start)-[*1..{max_hops}]-(d:Decision)
                RETURN d, length(path) as hop_count
            }}
            RETURN d, hop_count
            ORDER BY hop_count, d.timestamp DESC
            """
            
            results = self.graph_store.execute_query(query, {
                "start_entity": start_entity
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("d") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["hop_count"] = record.get("hop_count", 0)
                decisions.append(decision)
            
            self.logger.info(f"Found {len(decisions)} decisions via multi-hop reasoning")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed multi-hop reasoning: {e}")
            raise
    
    def trace_decision_path(
        self,
        decision_id: str,
        relationship_types: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Trace relationship paths for explainability.
        
        Args:
            decision_id: Decision ID to trace from
            relationship_types: List of relationship types to follow
            
        Returns:
            List of path information
        """
        try:
            if type(self.graph_store) is ContextGraph:
                from collections import deque
                
                # Check root node
                root = self.graph_store.find_node(decision_id)
                if not root or root.get("type") != "Decision":
                    return []
                    
                paths = []
                # Queue stores (current_node_id, current_path_nodes, current_path_rels)
                root_meta = root.get("metadata", {}).get("properties", root.get("metadata", {}))
                root_info = {"decision_id": root.get("id"), "scenario": root_meta.get("scenario", ""), "category": root_meta.get("category", "")}
                queue = deque([(decision_id, [root_info], [])])
                
                # Simple BFS path tracing matching cypher `MATCH path = (d)-[:REL*]-(related)`
                # We limit depth to prevent infinite loops in cyclic graphs
                max_depth = 5

                # Fetch all relevant edges once before BFS to avoid O(nodes * edges) fetches
                all_edges = []
                for rel_type in relationship_types:
                    all_edges.extend(self.graph_store.find_edges(edge_type=rel_type))

                while queue:
                    curr_id, path_nodes, path_rels = queue.popleft()

                    if len(path_rels) > 0:
                        paths.append({
                            "path_length": len(path_rels),
                            "nodes": path_nodes,
                            "relationships": path_rels
                        })

                    if len(path_rels) >= max_depth:
                        continue
                        
                    for edge in all_edges:
                        if edge["source"] == curr_id or edge["target"] == curr_id:
                            next_id = edge["target"] if edge["source"] == curr_id else edge["source"]
                            
                            # Avoid simple cycles in individual paths
                            if any(n["decision_id"] == next_id for n in path_nodes):
                                continue
                                
                            next_node = self.graph_store.find_node(next_id)
                            if next_node:
                                next_meta = next_node.get("metadata", {}).get("properties", next_node.get("metadata", {}))
                                next_info = {"decision_id": next_node.get("id"), "scenario": next_meta.get("scenario", ""), "category": next_meta.get("category", "")}
                                rel_info = {"from": edge["source"], "to": edge["target"], "type": edge["type"]}
                                queue.append((next_id, path_nodes + [next_info], path_rels + [rel_info]))
                
                paths.sort(key=lambda x: x["path_length"])
                self.logger.info(f"Traced {len(paths)} paths from decision {decision_id}")
                return paths

            # Build relationship filter
            rel_filter = "|".join(relationship_types)
            
            query = f"""
            MATCH (d:Decision {{decision_id: $decision_id}})
            MATCH path = (d)-[:{rel_filter}*]-(related)
            RETURN [node in nodes(path) | {{decision_id: node.decision_id, scenario: node.scenario, category: node.category}}] as path_nodes,
                   [r in relationships(path) | {{from: startNode(r).decision_id, to: endNode(r).decision_id, type: type(r)}}] as path_rels,
                   length(path) as path_length
            ORDER BY path_length
            """

            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)

            paths = []
            for record in results:
                path_info = {
                    "path_length": record.get("path_length", 0),
                    "nodes": record.get("path_nodes", []),
                    "relationships": record.get("path_rels", []),
                }
                paths.append(path_info)
            
            self.logger.info(f"Traced {len(paths)} paths from decision {decision_id}")
            return paths
            
        except Exception as e:
            self.logger.error(f"Failed to trace decision path: {e}")
            raise
    
    def find_similar_exceptions(
        self,
        exception_reason: str,
        limit: int = 10
    ) -> List[PolicyException]:
        """
        Find similar exceptions for precedent.
        
        Args:
            exception_reason: Reason for exception to find similar ones
            limit: Maximum number of results
            
        Returns:
            List of similar exceptions
        """
        try:
            # Generate query embedding for similarity search
            query_embedding = None
            if self.embedding_generator:
                query_embedding = self.embedding_generator.generate(exception_reason)
            
            if type(self.graph_store) is ContextGraph:
                nodes = self.graph_store.find_nodes("Exception")
                exceptions = []
                for node in nodes:
                    metadata = node.get("metadata", {}).get("properties", node.get("metadata", {}))
                    core_fields = {
                        "decision_id", "policy_id", "reason", "approver", 
                        "approval_timestamp", "justification"
                    }
                    custom_metadata = {k: v for k, v in metadata.items() if k not in core_fields}
                    exception_data = {"id": node.get("id"), "metadata": custom_metadata}
                    exception_data.update({k: v for k, v in metadata.items() if k in core_fields})
                    
                    try:
                        exception = self._dict_to_exception(exception_data)
                    except KeyError:
                        continue
                        
                    if query_embedding:
                        reason_embedding = self.embedding_generator.generate(exception.reason)
                        similarity = self._cosine_similarity(query_embedding, reason_embedding)
                        exception.metadata["similarity_score"] = similarity
                        
                    exceptions.append(exception)
                    
                if query_embedding:
                    exceptions.sort(
                        key=lambda e: e.metadata.get("similarity_score", 0),
                        reverse=True
                    )
                
                self.logger.info(f"Found {min(len(exceptions), limit)} similar exceptions")
                return exceptions[:limit]

            # Find exceptions with similar reasons
            query = """
            MATCH (e:Exception)
            RETURN e
            LIMIT $limit
            """
            results = self.graph_store.execute_query(query, {"limit": limit})
            results = self._extract_records(results)
            
            exceptions = []
            for record in results:
                exception_data = record.get("e") if isinstance(record, dict) else None
                if not isinstance(exception_data, dict):
                    exception_data = record if isinstance(record, dict) else {}
                exception = self._dict_to_exception(exception_data)
                
                # Calculate similarity if embedding available
                if query_embedding:
                    reason_embedding = self.embedding_generator.generate(exception.reason)
                    similarity = self._cosine_similarity(query_embedding, reason_embedding)
                    exception.metadata["similarity_score"] = similarity
                
                exceptions.append(exception)
            
            # Sort by similarity if available
            if query_embedding:
                exceptions.sort(
                    key=lambda e: e.metadata.get("similarity_score", 0),
                    reverse=True
                )
            
            self.logger.info(f"Found {len(exceptions)} similar exceptions")
            return exceptions[:limit]
            
        except Exception as e:
            self.logger.error(f"Failed to find similar exceptions: {e}")
            raise
    
    @staticmethod
    def _deserialize_graph_metadata(metadata: Any) -> Dict[str, Any]:
        """Deserialize metadata from graph node properties to a dictionary.
        
        Property-graph stores (e.g. Neo4j) persist metadata as JSON strings.
        Decodes JSON strings back into Dict[str, Any] while gracefully handling
        non-JSON strings and retaining already-native dicts.
        """
        if isinstance(metadata, str):
            try:
                parsed = json.loads(metadata)
                return parsed if isinstance(parsed, dict) else {"raw": metadata}
            except (TypeError, ValueError):
                return {"raw": metadata} if metadata else {}
        elif isinstance(metadata, dict):
            return metadata
        return {}

    def _dict_to_decision(self, data: Dict[str, Any]) -> Decision:
        """Convert dictionary to Decision object."""
        # Handle timestamp conversion
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        decision_id = data.get("decision_id") or data.get("id")
        if not decision_id:
            raise KeyError("decision_id")

        return Decision(
            decision_id=decision_id,
            category=data.get("category", ""),
            scenario=data.get("scenario", ""),
            reasoning=data.get("reasoning", ""),
            outcome=data.get("outcome", ""),
            confidence=data.get("confidence", 0.0),
            timestamp=data.get("timestamp", datetime.now()),
            decision_maker=data.get("decision_maker", ""),
            reasoning_embedding=data.get("reasoning_embedding"),
            node2vec_embedding=data.get("node2vec_embedding"),
            metadata=self._deserialize_graph_metadata(data.get("metadata")),
        )
    
    def _dict_to_exception(self, data: Dict[str, Any]) -> PolicyException:
        """Convert dictionary to PolicyException object."""
        # Handle timestamp conversion
        if isinstance(data.get("approval_timestamp"), str):
            data["approval_timestamp"] = datetime.fromisoformat(data["approval_timestamp"])

        exception_id = data.get("exception_id") or data.get("id")
        decision_id = data.get("decision_id")
        policy_id = data.get("policy_id")
        if not exception_id or not decision_id or not policy_id:
            raise KeyError("exception_id/decision_id/policy_id")

        return PolicyException(
            exception_id=exception_id,
            decision_id=decision_id,
            policy_id=policy_id,
            reason=data.get("reason", ""),
            approver=data.get("approver", ""),
            approval_timestamp=data.get("approval_timestamp", datetime.now()),
            justification=data.get("justification", ""),
            metadata=self._deserialize_graph_metadata(data.get("metadata")),
        )
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts using embeddings."""
        if not self.embedding_generator:
            return 0.0
        try:
            emb1 = self.embedding_generator.generate(text1)
            emb2 = self.embedding_generator.generate(text2)
            return self._cosine_similarity(emb1, emb2)
        except Exception:
            return 0.0

    def _calculate_hybrid_score(
        self,
        semantic_score: float,
        structural_score: float,
        semantic_weight: float = 0.5,
        structural_weight: float = 0.5
    ) -> float:
        """Calculate hybrid score from semantic and structural components."""
        if abs(semantic_weight + structural_weight - 1.0) > 1e-6:
            raise ValueError("Weights must sum to 1.0")
        return round(semantic_weight * semantic_score + structural_weight * structural_score, 10)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            if v1.shape != v2.shape:
                return 0.0
            
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
            
        except Exception:
            return 0.0
    
    def _vector_result_to_decision(self, result: Dict[str, Any]) -> Optional[Decision]:
        """Convert vector store result to Decision object."""
        try:
            decision_data = {
                "decision_id": result.get("id", ""),
                "category": result.get("metadata", {}).get("category", ""),
                "scenario": result.get("text", ""),
                "reasoning": result.get("metadata", {}).get("reasoning", ""),
                "outcome": result.get("metadata", {}).get("outcome", ""),
                "confidence": result.get("metadata", {}).get("confidence", 0.0),
                "timestamp": result.get("metadata", {}).get("timestamp", datetime.now()),
                "decision_maker": result.get("metadata", {}).get("decision_maker", ""),
            }
            return self._dict_to_decision(decision_data)
        except Exception:
            return None
    
    def _calculate_combined_similarity(
        self, scenario: str, decision: Decision, weights: Dict[str, float], result: Dict[str, Any]
    ) -> float:
        """Calculate combined similarity score from multiple components."""
        similarity_score = 0.0
        
        # Vector similarity from result
        vector_sim = result.get("similarity", 0.0)
        similarity_score += weights["semantic"] * vector_sim
        
        # Text similarity
        text_sim = self._calculate_text_similarity(decision.scenario, scenario)
        similarity_score += weights["text"] * text_sim
        
        # Category similarity
        category_sim = 1.0 if decision.category == result.get("metadata", {}).get("category") else 0.0
        similarity_score += weights["category"] * category_sim
        
        # Structural similarity (if available)
        if "node_embedder" in self.kg_components:
            try:
                structural_sim = self._calculate_structural_similarity(decision, scenario)
                similarity_score += weights["structural"] * structural_sim
            except Exception:
                pass
        
        return similarity_score
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple overlap."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_structural_similarity(self, decision: Decision, scenario: str) -> float:
        """Calculate structural similarity using Node2Vec embeddings."""
        if "node_embedder" not in self.kg_components:
            return 0.0
        
        try:
            # Get decision subgraph
            subgraph = self._get_decision_subgraph(decision.decision_id, max_depth=2)
            
            # Generate embeddings
            embeddings = self.kg_components["node_embedder"].generate_embeddings(subgraph)
            
            if decision.decision_id in embeddings:
                # For now, use text similarity as proxy for structural similarity
                # In a full implementation, this would compare node embeddings
                return self._calculate_text_similarity(decision.scenario, scenario) * 0.8
            
        except Exception:
            pass
        
        return 0.0
    
    def _get_centrality_boost(self, decision_id: str) -> float:
        """Get centrality-based boost for decision ranking."""
        if "centrality_calculator" not in self.kg_components:
            return 0.0
        
        # Check cache first
        cache_key = f"centrality_{decision_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Get decision subgraph
            subgraph = self._get_decision_subgraph(decision_id, max_depth=2)
            
            # Calculate degree centrality
            centrality = self.kg_components["centrality_calculator"].calculate_degree_centrality(subgraph)
            boost = centrality.get('centrality', {}).get(decision_id, 0.0)
            
            # Cache the result
            self._cache[cache_key] = boost
            return boost
            
        except Exception:
            return 0.0
    
    def _get_decision_subgraph(self, decision_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """Get subgraph around a decision for analysis."""
        query = """
        MATCH (start:Decision {decision_id: $decision_id})
        MATCH path = (start)-[:CAUSED|:INFLUENCED|:PRECEDENT_FOR]-(connected:Decision)
        RETURN start, connected, relationships(path) as rel
        LIMIT 50
        """
        
        try:
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            return {"nodes": results, "max_depth": max_depth}
        except Exception:
            return {"nodes": [], "max_depth": max_depth}
    
    # Advanced methods for comprehensive context graphs
    def analyze_decision_influence(
        self, decision_id: str, max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Analyze decision influence using advanced graph algorithms.
        
        Args:
            decision_id: Decision ID to analyze
            max_depth: Maximum depth for influence analysis
            
        Returns:
            Comprehensive influence analysis
        """
        if not self.kg_components:
            self.logger.warning("Advanced KG components not available")
            return {"error": "Advanced features not available"}
        
        try:
            analysis = {
                "decision_id": decision_id,
                "influence_score": 0.0,
                "centrality_measures": {},
                "community_info": {},
                "downstream_decisions": [],
                "upstream_decisions": []
            }
            
            # Get causal chains
            downstream_query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)-[:CAUSED|INFLUENCED|PRECEDENT_FOR*1..{max_depth}]->(end:Decision)
            RETURN DISTINCT end, length(path) as distance
            ORDER BY distance
            """
            
            upstream_query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)<-[:CAUSED|INFLUENCED|PRECEDENT_FOR*1..{max_depth}]-(end:Decision)
            RETURN DISTINCT end, length(path) as distance
            ORDER BY distance
            """
            
            # Execute queries
            downstream_results = self.graph_store.execute_query(downstream_query, {
                "decision_id": decision_id
            })
            downstream_results = self._extract_records(downstream_results)
            
            upstream_results = self.graph_store.execute_query(upstream_query, {
                "decision_id": decision_id
            })
            upstream_results = self._extract_records(upstream_results)
            
            # Process results
            for record in downstream_results:
                decision_data = record.get("end", {})
                decision = self._dict_to_decision(decision_data)
                analysis["downstream_decisions"].append({
                    "decision": decision,
                    "distance": record.get("distance", 0)
                })
            
            for record in upstream_results:
                decision_data = record.get("end", {})
                decision = self._dict_to_decision(decision_data)
                analysis["upstream_decisions"].append({
                    "decision": decision,
                    "distance": record.get("distance", 0)
                })
            
            # Calculate centrality measures
            if "centrality_calculator" in self.kg_components:
                subgraph = self._get_decision_subgraph(decision_id, max_depth)
                centrality_results = self.kg_components["centrality_calculator"].calculate_all_centrality(subgraph)
                
                # Extract centrality measures for this decision from nested structure
                decision_measures = {}
                centrality_measures = centrality_results.get('centrality_measures', {})
                
                for measure_type, measure_data in centrality_measures.items():
                    if isinstance(measure_data, dict) and 'centrality' in measure_data:
                        val = measure_data['centrality'].get(decision_id, 0.0)
                        decision_measures[measure_type] = val if isinstance(val, (int, float)) else 0.0

                analysis["centrality_measures"] = decision_measures

                # Calculate overall influence score
                measures = analysis["centrality_measures"]
                analysis["influence_score"] = (
                    0.3 * measures.get("degree", 0.0) +
                    0.3 * measures.get("betweenness", 0.0) +
                    0.2 * measures.get("closeness", 0.0) +
                    0.2 * measures.get("eigenvector", 0.0)
                )
            
            # Community detection
            if "community_detector" in self.kg_components:
                subgraph = self._get_decision_subgraph(decision_id, max_depth)
                communities = self.kg_components["community_detector"].detect_communities(subgraph)
                
                for community_id, members in communities.items():
                    if decision_id in members:
                        analysis["community_info"] = {
                            "community_id": community_id,
                            "community_size": len(members),
                            "community_members": list(members)[:10]
                        }
                        break
            
            self.logger.info(f"Completed influence analysis for decision {decision_id}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze decision influence: {e}")
            return {"error": str(e)}
    
    def predict_decision_relationships(self, decision_id: str, top_k: int = 5) -> List[Dict]:
        """
        Predict potential relationships for a decision using link prediction.
        
        Args:
            decision_id: Decision ID
            top_k: Number of predictions to return
            
        Returns:
            List of predicted relationships
        """
        if "link_predictor" not in self.kg_components:
            self.logger.warning("Link predictor not available")
            return []
        
        try:
            subgraph = self._get_decision_subgraph(decision_id, max_depth=2)
            predictions = self.kg_components["link_predictor"].predict_links(subgraph, top_k=top_k)
            
            # Filter predictions involving our decision
            relevant_predictions = []
            for prediction in predictions:
                if prediction.get("source") == decision_id or prediction.get("target") == decision_id:
                    relevant_predictions.append(prediction)
            
            return relevant_predictions
            
        except Exception as e:
            self.logger.error(f"Failed to predict relationships: {e}")
            return []

    def _extract_records(self, results: Any) -> List[Dict[str, Any]]:
        """Normalize execute_query result shapes to a list of record maps."""
        if isinstance(results, dict):
            records = results.get("records", [])
            return records if isinstance(records, list) else []
        if isinstance(results, list):
            return results
        return []
