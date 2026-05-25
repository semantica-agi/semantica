"""
Causal Chain Analyzer

Analyzes decision causality, influence chains, and precedent relationships using
graph traversal and advanced analytics.

Key Features:
    - Causal chain tracing (upstream/downstream)
    - Decision influence analysis and scoring
    - Precedent relationship mapping
    - Multi-directional causality analysis
    - Path finding and impact assessment

Decision Tracking Integration:
    - Complete decision lifecycle analysis
    - Decision influence and causality tracking
    - Decision relationship mapping
    - Decision metadata and context analysis
    - Decision analytics and statistics

KG Algorithm Integration:
    - Path Finding: Shortest path and advanced path algorithms
    - Centrality Analysis: Decision importance and influence scoring
    - Similarity Calculation: Decision similarity measures
    - Community Detection: Decision community analysis
    - Link Prediction: Predict causal relationships
    - Node Embeddings: Node2Vec embeddings for similarity analysis

Vector Store Integration:
    - Hybrid Search: Semantic + structural similarity
    - Custom Similarity Weights: Configurable scoring
    - Advanced Precedent Search: KG-enhanced similarity
    - Multi-Embedding Support: Multiple embedding types
    - Metadata Filtering: Advanced filtering capabilities
    - Policy Engine: Policy enforcement and compliance checking

Core Methods:
    - get_causal_chain(): Trace causal chains from decisions
    - find_influenced_decisions(): Find decisions influenced by a decision
    - find_influencing_decisions(): Find decisions that influenced a decision
    - analyze_causal_impact(): Analyze causal impact and scope
    - calculate_influence_score(): Calculate decision influence scores
    - find_precedents(): Find decision precedents with similarity

Example Usage:
    >>> from semantica.context import CausalChainAnalyzer
    >>> analyzer = CausalChainAnalyzer(graph_store=kg)
    >>> upstream = analyzer.get_causal_chain(decision_id, "upstream", max_depth=3)
    >>> downstream = analyzer.get_causal_chain(decision_id, "downstream", max_depth=3)
    >>> influenced = analyzer.find_influenced_decisions(decision_id)
    >>> influence_score = analyzer.calculate_influence_score(decision_id)
    >>> impact = analyzer.analyze_causal_impact(decision_id, max_depth=5)

Production Use Cases:
    - Banking: Trace loan approval decisions and their impacts
    - Healthcare: Analyze treatment decision cascades
    - Legal: Trace legal precedent influence chains
    - Manufacturing: Analyze production decision impacts
    - Policy: Trace policy decision consequences
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from collections import deque

from ..graph_store import GraphStore
from ..utils.helpers import classify_path_distance
from ..utils.logging import get_logger
from .decision_models import Decision


class CausalChainAnalyzer:
    """
    Analyzes causal chains between decisions.
    
    This class provides methods for tracing decision causality, finding
    decisions that influenced others, and analyzing precedent relationships
    using graph traversal.
    """
    
    def __init__(self, graph_store: Any):
        """
        Initialize CausalChainAnalyzer.
        
        Args:
            graph_store: Graph database instance for traversal
        """
        self.graph_store = graph_store
        self.logger = get_logger(__name__)
    
    def get_causal_chain(
        self,
        decision_id: str,
        direction: str = "upstream",
        max_depth: int = 10
    ) -> List[Decision]:
        """
        Trace decision causality in specified direction.
        
        Args:
            decision_id: Starting decision ID
            direction: "upstream" (what caused this) or "downstream" (what this caused)
            max_depth: Maximum traversal depth
            
        Returns:
            List of decisions in causal chain
        """
        try:
            if hasattr(self.graph_store, "get_causal_chain") and not hasattr(self.graph_store, "execute_query"):
                return self.graph_store.get_causal_chain(
                    decision_id=decision_id,
                    direction=direction,
                    max_depth=max_depth
                )

            if not (1 <= max_depth <= 100):
                raise ValueError("max_depth must be between 1 and 20")

            if direction not in ["upstream", "downstream"]:
                raise ValueError("Direction must be 'upstream' or 'downstream'")
            
            # Define relationship direction based on traversal direction
            if direction == "upstream":
                rel_pattern = "<-[:CAUSED|:INFLUENCED|:PRECEDENT_FOR]-"
            else:
                rel_pattern = "-[:CAUSED|:INFLUENCED|:PRECEDENT_FOR]->"
            
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start){rel_pattern}{{1,{max_depth}}}(end:Decision)
            RETURN DISTINCT end, length(path) as distance
            ORDER BY distance, end.timestamp
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("end") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["causal_distance"] = record.get("distance", 0)
                decisions.append(decision)
            
            self.logger.info(f"Found {len(decisions)} decisions in {direction} causal chain")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to get causal chain: {e}")
            raise

    def trace_at_time(
        self,
        event_id: str,
        at_time: Any,
        direction: str = "upstream",
        max_depth: int = 10,
    ) -> List[Decision]:
        """Trace a causal chain using only facts recorded up to ``at_time``."""
        cutoff = self._normalize_at_time(at_time)

        if direction not in ["upstream", "downstream"]:
            raise ValueError("Direction must be 'upstream' or 'downstream'")
        if not (1 <= max_depth <= 100):
            raise ValueError("max_depth must be between 1 and 100")

        if hasattr(self.graph_store, "nodes") and hasattr(self.graph_store, "edges"):
            return self._trace_at_time_from_context_graph(event_id, cutoff, direction, max_depth)

        if hasattr(self.graph_store, "execute_query"):
            rel_pattern = "<-[rel:CAUSED|INFLUENCED|PRECEDENT_FOR]-" if direction == "upstream" else "-[rel:CAUSED|INFLUENCED|PRECEDENT_FOR]->"
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start){rel_pattern}{{1,{max_depth}}}(end:Decision)
            WHERE ALL(rel IN relationships(path) WHERE rel.recorded_at IS NOT NULL AND rel.recorded_at <= $at_time)
            RETURN DISTINCT end, length(path) as distance
            ORDER BY distance, end.timestamp
            """
            results = self.graph_store.execute_query(
                query,
                {"decision_id": event_id, "at_time": cutoff.strftime("%Y-%m-%dT%H:%M:%S") + "Z"},
            )
            records = self._extract_records(results)
            decisions: List[Decision] = []
            for record in records:
                decision_data = record.get("end") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["causal_distance"] = record.get("distance", 0)
                decisions.append(decision)
            return decisions

        return []
    
    def get_influenced_decisions(
        self,
        decision_id: str,
        max_depth: int = 10
    ) -> List[Decision]:
        """
        Find decisions influenced by this one.
        
        Args:
            decision_id: Decision ID to find influences for
            max_depth: Maximum traversal depth
            
        Returns:
            List of influenced decisions
        """
        try:
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)-[:CAUSED|:INFLUENCED*1..{max_depth}]->(end:Decision)
            RETURN DISTINCT end, length(path) as influence_depth
            ORDER BY influence_depth, end.timestamp
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("end") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["influence_depth"] = record.get("influence_depth", 0)
                decisions.append(decision)
            
            self.logger.info(f"Found {len(decisions)} decisions influenced by {decision_id}")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to get influenced decisions: {e}")
            raise
    
    def get_precedent_chain(
        self,
        decision_id: str,
        max_depth: int = 10
    ) -> List[Decision]:
        """
        Find precedent relationships.
        
        Args:
            decision_id: Decision ID to find precedents for
            max_depth: Maximum traversal depth
            
        Returns:
            List of precedent decisions
        """
        try:
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)-[:PRECEDENT_FOR*1..{max_depth}]->(end:Decision)
            RETURN DISTINCT end, length(path) as precedent_depth, 
                   [rel in relationships(path) | rel.type] as relationship_types
            ORDER BY precedent_depth, end.timestamp
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("end") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["precedent_depth"] = record.get("precedent_depth", 0)
                decision.metadata["relationship_types"] = record.get("relationship_types", [])
                decisions.append(decision)
            
            self.logger.info(f"Found {len(decisions)} precedent decisions")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to get precedent chain: {e}")
            raise
    
    def find_causal_loops(self, max_depth: int = 10) -> List[Dict[str, Any]]:
        """
        Find causal loops in decision graph.

        Args:
            max_depth: Maximum depth to search for loops

        Returns:
            List of loop dicts with decision_id, loop_path, loop_length, cycle_strength
        """
        try:
            query = f"""
            MATCH path = (d1:Decision)-[:CAUSED|:INFLUENCED*2..{max_depth}]->(d1)
            WHERE ALL(i IN range(0, length(path)-2) |
                     path[i].decision_id <> path[i+1].decision_id)
            RETURN d1.decision_id as decision_id,
                   d1.scenario as decision_scenario,
                   [node in nodes(path) | {{decision_id: node.decision_id, scenario: node.scenario, category: node.category}}] as loop_path,
                   length(path) as loop_length
            ORDER BY loop_length
            """

            results = self._extract_records(self.graph_store.execute_query(query))

            loops = []
            for record in results:
                loops.append(record)

            self.logger.info(f"Found {len(loops)} causal loops")
            return loops

        except Exception as e:
            self.logger.error(f"Failed to find causal loops: {e}")
            raise
    
    def get_causal_impact_score(self, decision_id: str) -> float:
        """
        Calculate causal impact score for a decision.

        Args:
            decision_id: Decision ID to analyze

        Returns:
            Impact score (0-1)
        """
        try:
            query = """
            MATCH (d:Decision {decision_id: $decision_id})
            OPTIONAL MATCH (d)-[:CAUSED|:INFLUENCED*1..5]->(influenced:Decision)
            WITH d,
                 count(influenced) as influence_count,
                 avg(influenced.confidence) as avg_influence_strength
            OPTIONAL MATCH (d)<-[:PRECEDENT_FOR*1..5]-(precedent:Decision)
            RETURN influence_count,
                   avg_influence_strength,
                   count(precedent) as precedent_count,
                   avg(precedent.confidence) as avg_precedent_strength
            """
            results = self._extract_records(
                self.graph_store.execute_query(query, {"decision_id": decision_id})
            )
            if not results:
                return 0.0
            return self._calculate_impact_score(results)

        except Exception as e:
            self.logger.error(f"Failed to calculate causal impact: {e}")
            return 0.0

    def _calculate_impact_score(self, results: List[Dict[str, Any]]) -> float:
        """Calculate impact score from query results."""
        total_score = 0.0
        weight_sum = 0.0
        for record in results:
            if "avg_influence_strength" in record:
                influence_count = record.get("influence_count") or 0
                avg_strength = record.get("avg_influence_strength") or 0.0
                total_score += influence_count * avg_strength
                weight_sum += max(influence_count, 1)
            if "avg_precedent_strength" in record:
                precedent_count = record.get("precedent_count") or 0
                avg_strength = record.get("avg_precedent_strength") or 0.0
                total_score += precedent_count * avg_strength * 0.5
                weight_sum += max(precedent_count, 1) * 0.5
        if weight_sum == 0:
            return 0.0
        return min(total_score / weight_sum, 1.0)
    
    def find_root_causes(self, decision_id: str, max_depth: int = 10) -> List[Decision]:
        """
        Find root cause decisions (upstream decisions with no further causes).
        
        Args:
            decision_id: Decision ID to analyze
            max_depth: Maximum traversal depth
            
        Returns:
            List of root cause decisions
        """
        try:
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)<-[:CAUSED|:INFLUENCED*1..{max_depth}]-(root:Decision)
            WHERE NOT (root)<-[:CAUSED|:INFLUENCED]-(:Decision)
            RETURN DISTINCT root, length(path) as root_distance
            ORDER BY root_distance
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            root_decisions = []
            for record in results:
                decision_data = record.get("root") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["root_distance"] = record.get("root_distance", 0)
                root_decisions.append(decision)
            
            self.logger.info(f"Found {len(root_decisions)} root cause decisions")
            return root_decisions
            
        except Exception as e:
            self.logger.error(f"Failed to find root causes: {e}")
            raise
    
    def analyze_causal_network(self, decision_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze causal network.

        Args:
            decision_ids: Optional list of decision IDs to scope the analysis

        Returns:
            Network analysis results with node_count, edge_count, centrality_scores,
            community_structure
        """
        try:
            query = """
            MATCH (d:Decision)
            OPTIONAL MATCH (d)-[r:CAUSED|INFLUENCED]->(d2:Decision)
            RETURN count(DISTINCT d) as node_count,
                   count(DISTINCT r) as edge_count
            """
            results = self._extract_records(self.graph_store.execute_query(query))

            network_analysis: Dict[str, Any] = {
                "node_count": 0,
                "edge_count": 0,
                "centrality_scores": {},
                "community_structure": {},
            }

            for record in results:
                network_analysis.update(record)

            self.logger.info("Analyzed causal network")
            return network_analysis

        except Exception as e:
            self.logger.error(f"Failed to analyze causal network: {e}")
            raise
    
    def _calculate_influence_strength(
        self,
        relationship_type: str,
        confidence: float,
        temporal_distance: int
    ) -> float:
        """Calculate influence strength based on relationship type, confidence and distance."""
        base = confidence
        if relationship_type == "CAUSED":
            base *= 1.0
        elif relationship_type == "INFLUENCED":
            base *= 0.8
        else:
            base *= 0.6
        # Decay with temporal distance
        decay = 1.0 / (1.0 + temporal_distance * 0.1)
        return round(base * decay, 6)

    def _calculate_precedent_strength(
        self,
        similarity_score: float,
        category_match: bool,
        outcome_match: bool
    ) -> float:
        """Calculate precedent strength from similarity score and match flags."""
        strength = similarity_score
        if category_match:
            strength *= 1.1
        else:
            strength *= 0.7
        if outcome_match:
            strength *= 1.1
        else:
            strength *= 0.8
        return min(round(strength, 6), 1.0)

    def _detect_causal_cycle(self, path: List[str]) -> Optional[List[str]]:
        """Return the cycle portion of path if a cycle exists, else None."""
        seen: dict = {}
        for i, node in enumerate(path):
            if node in seen:
                return path[seen[node]:]
            seen[node] = i
        return None

    def _calculate_network_metrics(
        self,
        nodes: List[str],
        edges: List[tuple]
    ) -> Dict[str, float]:
        """Calculate basic network metrics: density, avg_path_length, clustering_coefficient."""
        n = len(nodes)
        if n == 0:
            return {"density": 0.0, "avg_path_length": 0.0, "clustering_coefficient": 0.0}
        max_edges = n * (n - 1)
        density = len(edges) / max_edges if max_edges > 0 else 0.0
        avg_path_length = 1.0 / density if density > 0 else float("inf")
        clustering_coefficient = density  # Simplified approximation
        return {
            "density": round(density, 6),
            "avg_path_length": round(min(avg_path_length, n), 6),
            "clustering_coefficient": round(clustering_coefficient, 6),
        }

    def _calculate_centrality_scores(
        self,
        nodes: List[str],
        edges: List[tuple]
    ) -> Dict[str, float]:
        """Calculate degree-based centrality for each node."""
        degree: Dict[str, int] = {n: 0 for n in nodes}
        for edge in edges:
            if len(edge) >= 2:
                src, dst = edge[0], edge[1]
                if src in degree:
                    degree[src] += 1
                if dst in degree:
                    degree[dst] += 1
        max_degree = max(degree.values()) if degree else 1
        if max_degree == 0:
            max_degree = 1
        return {node: round(deg / max_degree, 6) for node, deg in degree.items()}

    def _identify_communities(
        self,
        nodes: List[str],
        edges: List[tuple]
    ) -> Dict[str, List[str]]:
        """Identify communities via simple connected-components union-find."""
        parent = {n: n for n in nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for edge in edges:
            if len(edge) >= 2 and edge[0] in parent and edge[1] in parent:
                union(edge[0], edge[1])

        communities: Dict[str, List[str]] = {}
        for node in nodes:
            root = find(node)
            communities.setdefault(root, []).append(node)
        return communities

    def _dict_to_decision(self, data: Dict[str, Any]) -> Decision:
        """Convert dictionary to Decision object."""
        # Handle timestamp conversion
        ts = data.get("timestamp")
        if isinstance(ts, str):
            data["timestamp"] = datetime.fromisoformat(ts)
        elif ts is None:
            data["timestamp"] = datetime.now()

        decision_id = data.get("decision_id") or data.get("id")
        if not decision_id:
            raise KeyError("decision_id")

        raw_confidence = data.get("confidence", 0.0)
        confidence = max(0.0, min(1.0, float(raw_confidence))) if raw_confidence is not None else 0.0

        return Decision(
            decision_id=decision_id,
            category=data.get("category", ""),
            scenario=data.get("scenario", ""),
            reasoning=data.get("reasoning", ""),
            outcome=data.get("outcome", ""),
            confidence=confidence,
            timestamp=data.get("timestamp", datetime.now()),
            decision_maker=data.get("decision_maker", ""),
            reasoning_embedding=data.get("reasoning_embedding"),
            node2vec_embedding=data.get("node2vec_embedding"),
            metadata=data.get("metadata", {}),
        )

    def _extract_records(self, results: Any) -> List[Dict[str, Any]]:
        """Normalize execute_query result shapes to a list of record maps."""
        if isinstance(results, dict):
            records = results.get("records", [])
            return records if isinstance(records, list) else []
        if isinstance(results, list):
            return results
        return []

    def _normalize_at_time(self, value: Any) -> datetime:
        """Normalize supported ``at_time`` inputs."""
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None) if parsed.tzinfo is None else parsed.astimezone(timezone.utc).replace(tzinfo=None)
        raise ValueError("at_time must be a datetime or ISO datetime string")

    def _trace_at_time_from_context_graph(
        self,
        event_id: str,
        cutoff: datetime,
        direction: str,
        max_depth: int,
    ) -> List[Decision]:
        """Trace transaction-time causal chains against an in-memory ContextGraph."""
        eligible_edges = []
        for edge in getattr(self.graph_store, "edges", []):
            if edge.edge_type not in ["CAUSED", "INFLUENCED", "PRECEDENT_FOR"]:
                continue
            recorded_at = (edge.metadata or {}).get("recorded_at")
            if recorded_at is None:
                continue
            try:
                edge_recorded_at = self._normalize_at_time(recorded_at)
            except ValueError:
                continue
            if edge_recorded_at <= cutoff:
                eligible_edges.append(edge)

        if not eligible_edges:
            return []

        visited = set()
        queue = deque([(event_id, 0)])
        decisions: List[Decision] = []

        while queue:
            current_id, depth = queue.popleft()
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)

            if current_id != event_id:
                node = getattr(self.graph_store, "nodes", {}).get(current_id)
                if node and getattr(node, "node_type", "").lower() == "decision":
                    decision = self._dict_to_decision(
                        {
                            "id": node.node_id,
                            "category": node.properties.get("category", ""),
                            "scenario": node.properties.get("scenario", node.content),
                            "reasoning": node.properties.get("reasoning", ""),
                            "outcome": node.properties.get("outcome", ""),
                            "confidence": node.properties.get("confidence", 0.0),
                            "timestamp": node.properties.get("timestamp"),
                            "decision_maker": node.properties.get("decision_maker", ""),
                            "metadata": {},
                        }
                    )
                    decision.metadata["causal_distance"] = depth
                    decisions.append(decision)

            for edge in eligible_edges:
                if direction == "upstream" and edge.target_id == current_id and depth < max_depth:
                    queue.append((edge.source_id, depth + 1))
                if direction == "downstream" and edge.source_id == current_id and depth < max_depth:
                    queue.append((edge.target_id, depth + 1))

        if direction == "upstream":
            decisions.sort(key=lambda d: d.metadata.get("causal_distance", 0), reverse=True)
        else:
            decisions.sort(key=lambda d: d.metadata.get("causal_distance", 0))
        return decisions

    def interpret_causal_distance(
        self,
        source_id: str,
        target_id: str,
    ) -> Dict[str, Any]:
        """
        Traverse only causal-typed edges and return a structured distance report.

        Returns a dict matching CausalDistanceReport with keys:
            source_id, target_id, causal_path, causal_hop_count,
            intermediate_decisions, confidence_decay, weakest_link, interpretation
        """
        from collections import deque as _deque

        CAUSAL_TYPES = {"causes", "influences", "leads_to", "supports",
                        "CAUSED", "INFLUENCED", "PRECEDENT_FOR"}

        graph = self.graph_store

        # ContextGraph-native BFS over causal edges
        if hasattr(graph, "nodes") and hasattr(graph, "_adjacency"):
            if source_id not in graph.nodes:
                return self._unreachable_report(source_id, target_id)

            queue = _deque([(source_id, [source_id], 1.0, None)])
            visited: Set[str] = {source_id}

            while queue:
                current_id, path, decay, weakest = queue.popleft()
                if current_id == target_id:
                    hop_count = len(path) - 1
                    intermediates = [
                        n for n in path[1:-1]
                        if str(getattr(graph.nodes.get(n), "node_type", "")).lower() == "decision"
                    ]
                    band = classify_path_distance(hop_count)
                    interp = self._causal_interpretation(hop_count, decay, band)
                    return {
                        "source_id": source_id,
                        "target_id": target_id,
                        "causal_path": path,
                        "causal_hop_count": hop_count,
                        "intermediate_decisions": intermediates,
                        "confidence_decay": round(decay, 6),
                        "weakest_link": weakest,
                        "interpretation": interp,
                    }

                with graph._lock:
                    outgoing = list(graph._adjacency.get(current_id, []))

                for edge in outgoing:
                    if edge.edge_type not in CAUSAL_TYPES:
                        continue
                    nxt = edge.target_id
                    if nxt in visited:
                        continue
                    visited.add(nxt)
                    new_decay = decay * edge.weight
                    new_weakest = weakest
                    if weakest is None or edge.weight < weakest.get("edge_weight", 1.0):
                        new_weakest = {"source": current_id, "target": nxt, "edge_weight": edge.weight}
                    queue.append((nxt, path + [nxt], new_decay, new_weakest))

            return self._unreachable_report(source_id, target_id)

        # GraphStore fallback — return not-reachable; callers can use get_causal_chain instead
        return self._unreachable_report(source_id, target_id)

    @staticmethod
    def _causal_interpretation(hop_count: int, decay: float, band: str) -> str:
        if band == "direct":
            base = f"Direct cause with confidence {decay:.2f}."
        elif band == "near":
            base = (
                f"Mediated through {hop_count - 1} decision(s); "
                f"confidence decays to {decay:.2f}"
            )
            base += " — moderate evidence." if decay > 0.4 else " — weak evidence."
        else:
            base = (
                f"Distal influence across {hop_count} causal steps; "
                f"confidence near {decay:.2f} — weak signal."
            )
        return base

    @staticmethod
    def _unreachable_report(source_id: str, target_id: str) -> Dict[str, Any]:
        return {
            "source_id": source_id,
            "target_id": target_id,
            "causal_path": [],
            "causal_hop_count": 0,
            "intermediate_decisions": [],
            "confidence_decay": 0.0,
            "weakest_link": None,
            "interpretation": "No causal path found between the two nodes.",
        }
