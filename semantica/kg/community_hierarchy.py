"""
Hierarchical Community Structure and Multi-Level Graph Coarsening.

This module provides data structures and algorithms for constructing,
indexing, and querying hierarchical community structures across
multiple levels of coarsening.
"""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import networkx as nx
import networkx.algorithms.community as nx_comm

from ..utils.logging import get_logger
from .knowledge_graph import KnowledgeGraph

logger = get_logger("community_hierarchy")


def compute_community_hash(
    level: int,
    index: int,
    entity_ids: List[str],
    child_ids: Optional[List[str]] = None,
) -> str:
    """Compute canonical deterministic SHA-256 hash for community content."""
    payload = {
        "level": level,
        "index": index,
        "entity_ids": sorted(set(str(e) for e in entity_ids)),
        "child_ids": sorted(set(str(c) for c in (child_ids or []))),
    }
    dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


@dataclass
class HierarchicalCommunity:
    """Hierarchical community representation within a clustered graph."""

    id: str
    level: int
    index: int
    entity_ids: List[str]
    child_ids: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    size: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if self.entity_ids:
            self.entity_ids = sorted(set(str(e) for e in self.entity_ids))
        else:
            self.entity_ids = []

        if self.child_ids:
            self.child_ids = sorted(set(str(c) for c in self.child_ids))
        else:
            self.child_ids = []

        if not self.size:
            self.size = len(self.entity_ids)

        if not self.content_hash:
            self.content_hash = compute_community_hash(
                self.level, self.index, self.entity_ids, self.child_ids
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize community to a dictionary."""
        return {
            "id": self.id,
            "level": self.level,
            "index": self.index,
            "entity_ids": list(self.entity_ids),
            "child_ids": list(self.child_ids),
            "parent_id": self.parent_id,
            "size": self.size,
            "metrics": dict(self.metrics),
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HierarchicalCommunity":
        """Instantiate a community from a dictionary."""
        raw_parent = data.get("parent_id")
        parent_id = str(raw_parent) if raw_parent is not None else None
        return cls(
            id=str(data["id"]),
            level=int(data["level"]),
            index=int(data["index"]),
            entity_ids=list(data.get("entity_ids", [])),
            child_ids=list(data.get("child_ids", [])),
            parent_id=parent_id,
            size=int(data.get("size", len(data.get("entity_ids", [])))),
            metrics=dict(data.get("metrics", {})),
            content_hash=str(data.get("content_hash", "")),
        )


class CommunityHierarchy:
    """Container for hierarchical community structures and traversal."""

    def __init__(
        self,
        communities: Optional[
            Union[
                Dict[str, HierarchicalCommunity],
                List[HierarchicalCommunity],
            ]
        ] = None,
        graph: Optional[Any] = None,
    ) -> None:
        self._graph = graph
        if communities is None:
            self._communities: Dict[str, HierarchicalCommunity] = {}
        elif isinstance(communities, (list, tuple, set)):
            self._communities = {c.id: c for c in communities}
        elif isinstance(communities, dict):
            self._communities = dict(communities)
        else:
            raise TypeError("communities must be a dict, list, or None")

        self._node_to_community: Dict[Tuple[str, int], str] = {}
        self._level_to_communities: Dict[int, List[str]] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._node_to_community.clear()
        self._level_to_communities.clear()

        for comm in self._communities.values():
            level = comm.level
            if level not in self._level_to_communities:
                self._level_to_communities[level] = []
            self._level_to_communities[level].append(comm.id)

            for node_id in comm.entity_ids:
                self._node_to_community[(str(node_id), level)] = comm.id

        for level in self._level_to_communities:
            self._level_to_communities[level].sort(
                key=lambda cid: self._communities[cid].index
            )

    @property
    def communities(self) -> Dict[str, HierarchicalCommunity]:
        """Dictionary of community ID to HierarchicalCommunity object."""
        return self._communities

    @property
    def levels(self) -> List[int]:
        """Sorted list of unique levels present in the hierarchy."""
        return sorted(self._level_to_communities.keys())

    @property
    def max_level(self) -> int:
        """Maximum hierarchy level index, or -1 if empty."""
        return max(self.levels) if self.levels else -1

    @property
    def is_empty(self) -> bool:
        """Return True if hierarchy contains no communities."""
        return len(self._communities) == 0

    @property
    def root_communities(self) -> List[HierarchicalCommunity]:
        """Communities with no parent (top of the hierarchy)."""
        roots = [c for c in self._communities.values() if c.parent_id is None]
        roots.sort(key=lambda c: (c.level, c.index))
        return roots

    @property
    def leaf_communities(self) -> List[HierarchicalCommunity]:
        """Communities with no children (finest level)."""
        leaves = [c for c in self._communities.values() if not c.child_ids]
        leaves.sort(key=lambda c: (c.level, c.index))
        return leaves

    def get_community(
        self, community_id: str
    ) -> Optional[HierarchicalCommunity]:
        """Retrieve community by ID."""
        return self._communities.get(str(community_id))

    def get_communities_at_level(
        self, level: int
    ) -> List[HierarchicalCommunity]:
        """Retrieve all communities at a specific hierarchy level."""
        cids = self._level_to_communities.get(level, [])
        return [self._communities[cid] for cid in cids]

    def get_children(
        self, community_or_id: Union[str, HierarchicalCommunity]
    ) -> List[HierarchicalCommunity]:
        """Retrieve child communities for a given community or ID."""
        if isinstance(community_or_id, HierarchicalCommunity):
            comm = community_or_id
        else:
            comm = self.get_community(str(community_or_id))

        if comm is None:
            return []
        return [
            self._communities[cid]
            for cid in comm.child_ids
            if cid in self._communities
        ]

    def get_parent(
        self, community_or_id: Union[str, HierarchicalCommunity]
    ) -> Optional[HierarchicalCommunity]:
        """Retrieve parent community for a given community or ID."""
        if isinstance(community_or_id, HierarchicalCommunity):
            comm = community_or_id
        else:
            comm = self.get_community(str(community_or_id))

        if comm is None or comm.parent_id is None:
            return None
        return self.get_community(comm.parent_id)

    def get_community_for_node(
        self, node_id: str, level: Optional[int] = None
    ) -> Optional[HierarchicalCommunity]:
        """
        Look up community containing a node at a given level in O(1) time.

        If level is None, defaults to the lowest level available (usually 0).
        """
        if self.is_empty:
            return None
        target_level = min(self.levels) if level is None else level
        comm_id = self._node_to_community.get((str(node_id), target_level))
        if comm_id is None:
            return None
        return self._communities.get(comm_id)

    def get_subgraph(
        self,
        community_or_id: Union[str, HierarchicalCommunity],
        graph: Optional[Any] = None,
    ) -> Any:
        """Extract the subgraph induced by community entities."""
        target_graph = graph if graph is not None else self._graph
        if target_graph is None:
            raise ValueError("A graph must be provided to extract a subgraph.")

        if isinstance(community_or_id, HierarchicalCommunity):
            comm = community_or_id
        else:
            comm = self.get_community(str(community_or_id))

        if comm is None:
            raise KeyError(
                f"Community '{community_or_id}' not found in hierarchy."
            )

        node_set = set(comm.entity_ids)

        if hasattr(target_graph, "subgraph"):
            matching_nodes = [
                n for n in target_graph.nodes
                if str(n) in node_set or n in node_set
            ]
            return target_graph.subgraph(matching_nodes).copy()

        if isinstance(target_graph, KnowledgeGraph):
            sub_entities = [
                e for e in target_graph.entities
                if (
                    str(e.get("id", "")) if isinstance(e, dict) else str(e)
                ) in node_set
            ]
            sub_relationships = [
                r for r in target_graph.relationships
                if (
                    str(r.get("source", r.get("source_id", "")))
                    if isinstance(r, dict)
                    else str(r[0])
                ) in node_set
                and (
                    str(r.get("target", r.get("target_id", "")))
                    if isinstance(r, dict)
                    else str(r[1])
                ) in node_set
            ]
            return KnowledgeGraph(
                entities=sub_entities,
                relationships=sub_relationships,
                metadata=dict(target_graph.metadata),
            )

        if isinstance(target_graph, dict):
            if "entities" in target_graph or "relationships" in target_graph:
                sub_entities = [
                    e for e in target_graph.get("entities", [])
                    if (
                        str(e.get("id", "")) if isinstance(e, dict) else str(e)
                    ) in node_set
                ]
                sub_relationships = [
                    r for r in target_graph.get("relationships", [])
                    if (
                        str(r.get("source", r.get("source_id", "")))
                        if isinstance(r, dict)
                        else str(r[0])
                    ) in node_set
                    and (
                        str(r.get("target", r.get("target_id", "")))
                        if isinstance(r, dict)
                        else str(r[1])
                    ) in node_set
                ]
                return {
                    "entities": sub_entities,
                    "relationships": sub_relationships,
                    "metadata": dict(target_graph.get("metadata", {})),
                }
            if "nodes" in target_graph or "edges" in target_graph:
                sub_nodes = [
                    n for n in target_graph.get("nodes", [])
                    if (
                        str(n.get("id", "")) if isinstance(n, dict) else str(n)
                    ) in node_set
                ]
                sub_edges = [
                    e for e in target_graph.get("edges", [])
                    if (
                        str(e.get("source", e.get("source_id", "")))
                        if isinstance(e, dict)
                        else str(e[0])
                    ) in node_set
                    and (
                        str(e.get("target", e.get("target_id", "")))
                        if isinstance(e, dict)
                        else str(e[1])
                    ) in node_set
                ]
                return {"nodes": sub_nodes, "edges": sub_edges}

            # Adjacency dict format: {node: [neighbors, ...]}
            sub_adj: Dict[str, Any] = {}
            for node, nbrs in target_graph.items():
                node_str = str(node)
                if node_str in node_set:
                    if isinstance(nbrs, (list, set, tuple)):
                        sub_adj[node_str] = [
                            str(nbr) for nbr in nbrs if str(nbr) in node_set
                        ]
                    else:
                        sub_adj[node_str] = nbrs
            return sub_adj

        raise TypeError(f"Unsupported graph type: {type(target_graph)}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize hierarchy to a dictionary."""
        sorted_comms = sorted(
            self._communities.items(),
            key=lambda kv: (kv[1].level, kv[1].index),
        )
        return {
            "communities": {cid: c.to_dict() for cid, c in sorted_comms},
            "levels": list(self.levels),
            "max_level": self.max_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommunityHierarchy":
        """Instantiate hierarchy from a dictionary."""
        raw_communities = data.get("communities", {})
        if isinstance(raw_communities, list):
            communities = {
                str(c_data["id"]): HierarchicalCommunity.from_dict(c_data)
                for c_data in raw_communities
            }
        else:
            communities = {
                cid: HierarchicalCommunity.from_dict(c_data)
                for cid, c_data in raw_communities.items()
            }
        return cls(communities=communities)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize hierarchy to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> "CommunityHierarchy":
        """Instantiate hierarchy from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    def __len__(self) -> int:
        return len(self._communities)

    def __iter__(self):
        return iter(self._communities.values())

    def __getitem__(self, community_id: str) -> HierarchicalCommunity:
        return self._communities[str(community_id)]

    def __contains__(self, community_id: str) -> bool:
        return str(community_id) in self._communities

    def __repr__(self) -> str:
        return (
            f"CommunityHierarchy(levels={self.levels}, "
            f"total_communities={len(self._communities)}, "
            f"max_level={self.max_level})"
        )


class CommunityHierarchyBuilder:
    """Multi-level hierarchy builder supporting Louvain and Leiden."""

    @staticmethod
    def _clean_weight(val: Any) -> float:
        """Sanitize edge weights to non-negative floats."""
        if val is None:
            return 1.0
        try:
            w = float(val)
            if w != w:
                return 1.0
            return max(0.0, w)
        except (ValueError, TypeError):
            return 1.0

    def __init__(
        self,
        algorithm: str = "louvain",
        resolution: Union[float, List[float]] = 1.0,
        seed: Optional[int] = 42,
        directed: Optional[bool] = None,
        weight: Optional[str] = "weight",
        threshold: float = 1e-7,
        max_levels: Optional[int] = None,
        id_prefix: str = "c_",
        **kwargs: Any,
    ) -> None:
        algo_norm = algorithm.lower().strip()
        if algo_norm in ("louvain", "default"):
            self.algorithm = "louvain"
        elif algo_norm == "leiden":
            self.algorithm = "leiden"
        else:
            raise ValueError(
                f"Unsupported algorithm '{algorithm}'. "
                f"Supported algorithms: 'louvain', 'leiden'"
            )

        if isinstance(resolution, (list, tuple)):
            if len(resolution) == 0:
                self.resolution: Union[float, List[float]] = [1.0]
            else:
                for r in resolution:
                    if float(r) <= 0:
                        raise ValueError(
                            "Resolution values must be positive (> 0)"
                        )
                self.resolution = [float(r) for r in resolution]
        else:
            if float(resolution) <= 0:
                raise ValueError("Resolution must be positive (> 0)")
            self.resolution = float(resolution)

        if max_levels is not None and max_levels <= 0:
            raise ValueError("max_levels must be a positive integer (> 0)")
        self.max_levels = max_levels

        self.seed = seed
        self.directed = directed
        self.weight = weight
        self.threshold = threshold
        self.id_prefix = id_prefix
        self.config = kwargs

    def build(self, graph: Any) -> CommunityHierarchy:
        """Build hierarchical community structure from graph input."""
        nx_graph = self._to_networkx(graph)

        if nx_graph.number_of_nodes() == 0:
            return CommunityHierarchy(communities={}, graph=nx_graph)

        if self.algorithm == "leiden":
            partitions = self._build_leiden_partitions(nx_graph)
        else:
            partitions = self._build_louvain_partitions(nx_graph)

        if self.max_levels is not None and self.max_levels > 0:
            partitions = partitions[:self.max_levels]

        return self._build_hierarchy_from_partitions(nx_graph, partitions)

    def _to_networkx(self, graph: Any) -> Union[nx.Graph, nx.DiGraph]:
        """Convert input graph into NetworkX Graph or DiGraph."""
        if isinstance(graph, (nx.Graph, nx.DiGraph)):
            is_directed = (
                self.directed
                if self.directed is not None
                else graph.is_directed()
            )
            out_graph = nx.DiGraph() if is_directed else nx.Graph()
            for n, data in graph.nodes(data=True):
                out_graph.add_node(str(n), **data)

            is_multi = getattr(graph, "is_multigraph", lambda: False)()
            for u, v, data in graph.edges(data=True):
                su, sv = str(u), str(v)
                edge_data = dict(data)
                w = self._clean_weight(edge_data.get("weight", 1.0))
                edge_data["weight"] = w
                if (
                    (is_multi or not is_directed)
                    and out_graph.has_edge(su, sv)
                ):
                    curr_w = self._clean_weight(
                        out_graph[su][sv].get("weight", 1.0)
                    )
                    out_graph[su][sv]["weight"] = curr_w + w
                else:
                    out_graph.add_edge(su, sv, **edge_data)
            return out_graph

        is_directed = self.directed if self.directed is not None else False
        out_graph = nx.DiGraph() if is_directed else nx.Graph()

        if isinstance(graph, KnowledgeGraph):
            for entity in graph.entities:
                if isinstance(entity, dict):
                    eid = str(entity.get("id", ""))
                    if eid:
                        out_graph.add_node(eid, **entity)
                else:
                    eid = str(entity)
                    if eid:
                        out_graph.add_node(eid)

            for rel in graph.relationships:
                if isinstance(rel, dict):
                    src = str(rel.get("source", rel.get("source_id", "")))
                    tgt = str(rel.get("target", rel.get("target_id", "")))
                    if src and tgt:
                        data = dict(rel)
                        w = self._clean_weight(data.get("weight", 1.0))
                        data["weight"] = w
                        if out_graph.has_edge(src, tgt):
                            curr_w = self._clean_weight(
                                out_graph[src][tgt].get("weight", 1.0)
                            )
                            out_graph[src][tgt]["weight"] = curr_w + w
                        else:
                            out_graph.add_edge(src, tgt, **data)
                elif isinstance(rel, (tuple, list)) and len(rel) >= 2:
                    src, tgt = str(rel[0]), str(rel[1])
                    if out_graph.has_edge(src, tgt):
                        curr_w = self._clean_weight(
                            out_graph[src][tgt].get("weight", 1.0)
                        )
                        out_graph[src][tgt]["weight"] = curr_w + 1.0
                    else:
                        out_graph.add_edge(src, tgt, weight=1.0)
            return out_graph

        if isinstance(graph, dict):
            if "entities" in graph or "relationships" in graph:
                for entity in graph.get("entities", []):
                    if isinstance(entity, dict):
                        eid = str(entity.get("id", ""))
                        if eid:
                            out_graph.add_node(eid, **entity)
                    else:
                        eid = str(entity)
                        if eid:
                            out_graph.add_node(eid)

                for rel in graph.get("relationships", []):
                    if isinstance(rel, dict):
                        src = str(rel.get("source", rel.get("source_id", "")))
                        tgt = str(rel.get("target", rel.get("target_id", "")))
                        if src and tgt:
                            data = dict(rel)
                            w = self._clean_weight(data.get("weight", 1.0))
                            data["weight"] = w
                            if out_graph.has_edge(src, tgt):
                                curr_w = self._clean_weight(
                                    out_graph[src][tgt].get("weight", 1.0)
                                )
                                out_graph[src][tgt]["weight"] = curr_w + w
                            else:
                                out_graph.add_edge(src, tgt, **data)
                    elif isinstance(rel, (tuple, list)) and len(rel) >= 2:
                        src, tgt = str(rel[0]), str(rel[1])
                        if out_graph.has_edge(src, tgt):
                            curr_w = self._clean_weight(
                                out_graph[src][tgt].get("weight", 1.0)
                            )
                            out_graph[src][tgt]["weight"] = curr_w + 1.0
                        else:
                            out_graph.add_edge(src, tgt, weight=1.0)
                return out_graph

            if "nodes" in graph or "edges" in graph:
                for n in graph.get("nodes", []):
                    if isinstance(n, dict):
                        nid = str(n.get("id", ""))
                        if nid:
                            out_graph.add_node(nid, **n)
                    else:
                        nid = str(n)
                        if nid:
                            out_graph.add_node(nid)

                for e in graph.get("edges", []):
                    if isinstance(e, dict):
                        src = str(e.get("source", e.get("source_id", "")))
                        tgt = str(e.get("target", e.get("target_id", "")))
                        if src and tgt:
                            data = dict(e)
                            w = self._clean_weight(data.get("weight", 1.0))
                            data["weight"] = w
                            if out_graph.has_edge(src, tgt):
                                curr_w = self._clean_weight(
                                    out_graph[src][tgt].get("weight", 1.0)
                                )
                                out_graph[src][tgt]["weight"] = curr_w + w
                            else:
                                out_graph.add_edge(src, tgt, **data)
                    elif isinstance(e, (tuple, list)) and len(e) >= 2:
                        src, tgt = str(e[0]), str(e[1])
                        if out_graph.has_edge(src, tgt):
                            curr_w = self._clean_weight(
                                out_graph[src][tgt].get("weight", 1.0)
                            )
                            out_graph[src][tgt]["weight"] = curr_w + 1.0
                        else:
                            out_graph.add_edge(src, tgt, weight=1.0)
                return out_graph

            for node, nbrs in graph.items():
                node_id = str(node)
                out_graph.add_node(node_id)
                if isinstance(nbrs, (list, set, tuple)):
                    for nbr in nbrs:
                        nbr_id = str(nbr)
                        if out_graph.has_edge(node_id, nbr_id):
                            curr_w = self._clean_weight(
                                out_graph[node_id][nbr_id].get(
                                    "weight", 1.0
                                )
                            )
                            out_graph[node_id][nbr_id]["weight"] = (
                                curr_w + 1.0
                            )
                        else:
                            out_graph.add_edge(node_id, nbr_id, weight=1.0)
            return out_graph

        raise TypeError(f"Unsupported graph input type: {type(graph)}")

    def _refine_partition(
        self, G: Union[nx.Graph, nx.DiGraph], partition: List[Set[Any]]
    ) -> List[Set[Any]]:
        """Refine partition into connected or weakly connected components."""
        refined: List[Set[Any]] = []
        is_directed = G.is_directed()

        for comm in partition:
            if not comm:
                continue
            sub = G.subgraph(comm)
            if is_directed:
                components = list(nx.weakly_connected_components(sub))
            else:
                components = list(nx.connected_components(sub))
            refined.extend(components)

        return refined

    def _build_louvain_partitions(
        self, G: Union[nx.Graph, nx.DiGraph]
    ) -> List[List[Set[Any]]]:
        """Generate multi-level coarsened partitions using Louvain."""
        if G.number_of_nodes() == 0:
            return []
        if G.number_of_nodes() == 1:
            return [[set(G.nodes())]]

        if isinstance(self.resolution, (list, tuple)):
            resolution = float(self.resolution[0]) if self.resolution else 1.0
        else:
            resolution = float(self.resolution)

        try:
            raw_partitions = list(
                nx_comm.louvain_partitions(
                    G,
                    weight=self.weight,
                    resolution=resolution,
                    threshold=self.threshold,
                    seed=self.seed,
                )
            )
        except Exception as e:
            logger.warning(
                f"Louvain partitioning failed: {e}. Using singleton fallback."
            )
            raw_partitions = [[{n} for n in G.nodes()]]

        if not raw_partitions:
            raw_partitions = [[{n} for n in G.nodes()]]

        refined_partitions = [
            self._refine_partition(G, p) for p in raw_partitions
        ]
        return refined_partitions

    def _build_leiden_partitions(
        self, G: Union[nx.Graph, nx.DiGraph]
    ) -> List[List[Set[Any]]]:
        """Generate multi-level coarsened partitions using Leiden."""
        if G.number_of_nodes() == 0:
            return []
        if G.number_of_nodes() == 1:
            return [[set(G.nodes())]]

        partitions: List[List[Set[Any]]] = []
        current_g = G.copy()
        for u, v in current_g.edges():
            current_g[u][v]["weight"] = self._clean_weight(
                current_g[u][v].get("weight", 1.0)
            )

        super_to_orig: Dict[Any, Set[Any]] = {n: {n} for n in G.nodes()}
        level = 0

        while True:
            if self.max_levels is not None and level >= self.max_levels:
                break

            if isinstance(self.resolution, (list, tuple)):
                curr_res = float(
                    self.resolution[min(level, len(self.resolution) - 1)]
                )
            else:
                curr_res = float(self.resolution)

            try:
                raw_comms = nx_comm.louvain_communities(
                    current_g,
                    weight=self.weight,
                    resolution=curr_res,
                    seed=self.seed,
                )
            except Exception:
                raw_comms = [{n} for n in current_g.nodes()]

            refined_orig_comms: List[Set[Any]] = []
            for c in raw_comms:
                orig_set: Set[Any] = set()
                for sn in c:
                    orig_set.update(super_to_orig[sn])
                sub = G.subgraph(orig_set)
                if G.is_directed():
                    comps = list(nx.weakly_connected_components(sub))
                else:
                    comps = list(nx.connected_components(sub))
                refined_orig_comms.extend(comps)

            if partitions and (
                set(frozenset(s) for s in refined_orig_comms)
                == set(frozenset(s) for s in partitions[-1])
                or len(refined_orig_comms) >= len(partitions[-1])
            ):
                break

            partitions.append(refined_orig_comms)
            level += 1

            if (
                len(refined_orig_comms) <= 1
                or current_g.number_of_edges() == 0
            ):
                break

            new_super_to_orig: Dict[int, Set[Any]] = {}
            node_to_new_super: Dict[Any, int] = {}
            for idx, comp in enumerate(refined_orig_comms):
                new_super_to_orig[idx] = comp
                for n in comp:
                    node_to_new_super[n] = idx

            next_g = nx.DiGraph() if G.is_directed() else nx.Graph()
            next_g.add_nodes_from(range(len(refined_orig_comms)))

            for u, v, data in G.edges(data=True):
                su = node_to_new_super[u]
                sv = node_to_new_super[v]
                if su == sv:
                    continue
                w = self._clean_weight(data.get("weight", 1.0))
                if next_g.has_edge(su, sv):
                    next_g[su][sv]["weight"] += w
                else:
                    next_g.add_edge(su, sv, weight=w)

            if next_g.number_of_edges() == 0:
                break

            current_g = next_g
            super_to_orig = new_super_to_orig

        return partitions

    def _build_hierarchy_from_partitions(
        self,
        G: Union[nx.Graph, nx.DiGraph],
        partitions: List[List[Set[Any]]],
    ) -> CommunityHierarchy:
        """Construct communities with O(|V|) parent-child resolution."""
        communities: Dict[str, HierarchicalCommunity] = {}
        level_communities: List[List[HierarchicalCommunity]] = []
        is_directed = G.is_directed()

        for level_idx, raw_level in enumerate(partitions):
            sorted_raw = [
                s
                for s in sorted(
                    raw_level, key=lambda nodes: sorted(str(n) for n in nodes)
                )
                if s
            ]
            current_level_comms: List[HierarchicalCommunity] = []

            for c_idx, node_set in enumerate(sorted_raw):
                comm_id = f"{self.id_prefix}{level_idx}_{c_idx}"
                entity_ids = sorted(str(n) for n in node_set)
                sub_size = len(entity_ids)

                sub = G.subgraph(node_set)
                internal_edges = sub.number_of_edges()

                if is_directed:
                    total_incident = sum(
                        G.in_degree(n) + G.out_degree(n) for n in sub.nodes
                    )
                    external_edges = total_incident - 2 * internal_edges
                else:
                    total_degree = sum(G.degree(n) for n in sub.nodes)
                    external_edges = total_degree - 2 * internal_edges

                density = float(nx.density(sub))
                denom = 2.0 * internal_edges + external_edges
                conductance = (external_edges / denom) if denom > 0 else 0.0

                metrics = {
                    "internal_edges": int(internal_edges),
                    "external_edges": max(0, int(external_edges)),
                    "density": float(density),
                    "conductance": float(conductance),
                }

                comm = HierarchicalCommunity(
                    id=comm_id,
                    level=level_idx,
                    index=c_idx,
                    entity_ids=entity_ids,
                    child_ids=[],
                    parent_id=None,
                    size=sub_size,
                    metrics=metrics,
                    content_hash="",
                )
                communities[comm_id] = comm
                current_level_comms.append(comm)

            level_communities.append(current_level_comms)

        # O(|V|) parent-child resolution per level transition
        for level_idx in range(len(level_communities) - 1):
            children = level_communities[level_idx]
            parents = level_communities[level_idx + 1]

            node_to_parent: Dict[str, str] = {}
            for p in parents:
                for node in p.entity_ids:
                    node_to_parent[node] = p.id

            for child in children:
                if child.entity_ids:
                    parent_votes = [
                        node_to_parent[node]
                        for node in child.entity_ids
                        if node in node_to_parent
                    ]
                    if parent_votes:
                        from collections import Counter
                        parent_id = Counter(parent_votes).most_common(1)[0][0]
                        child.parent_id = parent_id
                        if parent_id in communities:
                            communities[parent_id].child_ids.append(child.id)

        # Finalize child ordering and deterministic content hashes
        for comm in communities.values():
            comm.child_ids.sort()
            comm.content_hash = compute_community_hash(
                comm.level, comm.index, comm.entity_ids, comm.child_ids
            )

        return CommunityHierarchy(communities=communities, graph=G)
