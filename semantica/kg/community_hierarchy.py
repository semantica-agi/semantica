"""
Hierarchical Community Structure and Multi-Level Graph Coarsening.

This module provides data structures and algorithms for constructing,
indexing, and querying hierarchical community structures across
multiple levels of coarsening.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
import hashlib
import json
import math
import random
import traceback
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import networkx as nx
import networkx.algorithms.community as nx_comm

from ..utils.logging import get_logger
from .knowledge_graph import KnowledgeGraph

logger = get_logger("community_hierarchy")


def _clean_attr_val(val: Any) -> Any:
    """Clean and normalize attribute value for canonical deterministic hashing."""
    if isinstance(val, float):
        return None if math.isnan(val) else float(val)
    if isinstance(val, (int, str, bool)):
        return val
    if val is None:
        return None
    if isinstance(val, dict):
        return {
            str(k): _clean_attr_val(v)
            for k, v in sorted(val.items(), key=lambda x: str(x[0]))
        }
    if isinstance(val, (list, tuple)):
        return [_clean_attr_val(x) for x in val]
    return str(val)


def canonicalize_edges(
    edges: Any,
    directed: bool = False,
) -> List[Dict[str, Any]]:
    """Produce deterministic canonical representation of induced edges."""
    if not edges:
        return []

    if hasattr(edges, "edges"):
        is_dir = getattr(edges, "is_directed", lambda: directed)()
        raw_edges = edges.edges(data=True)
    elif isinstance(edges, (str, bytes)):
        return []
    elif isinstance(edges, Iterable):
        is_dir = directed
        raw_edges = edges
    else:
        return []

    canonical = []
    for item in raw_edges:
        if isinstance(item, dict):
            src = str(
                item.get("source", item.get("source_id", item.get("src", "")))
            )
            tgt = str(
                item.get("target", item.get("target_id", item.get("tgt", "")))
            )
            raw_attrs: Dict[str, Any] = {}
            if "attributes" in item and isinstance(item["attributes"], dict):
                raw_attrs.update(item["attributes"])
            for k, v in item.items():
                if k not in (
                    "source",
                    "source_id",
                    "src",
                    "target",
                    "target_id",
                    "tgt",
                    "attributes",
                ):
                    raw_attrs[k] = v
            attrs = raw_attrs
        elif isinstance(item, (tuple, list)):
            if len(item) == 2:
                src, tgt = str(item[0]), str(item[1])
                attrs = {}
            elif len(item) >= 3:
                src, tgt = str(item[0]), str(item[1])
                data = item[2]
                if isinstance(data, dict):
                    attrs = dict(data)
                elif isinstance(data, (int, float)):
                    attrs = {"weight": float(data)}
                else:
                    attrs = {"data": str(data)}
            else:
                continue
        else:
            continue

        if not is_dir and src > tgt:
            src, tgt = tgt, src

        clean_attrs: Dict[str, Any] = {
            str(k): _clean_attr_val(v)
            for k, v in sorted(attrs.items(), key=lambda x: str(x[0]))
        }

        canonical.append(
            {
                "attributes": clean_attrs,
                "source": src,
                "target": tgt,
            }
        )

    canonical.sort(
        key=lambda e: (
            e["source"],
            e["target"],
            json.dumps(e["attributes"], sort_keys=True, separators=(",", ":")),
        )
    )
    return canonical


def compute_community_hash(
    level: int,
    index: int,
    entity_ids: List[str],
    child_ids: Optional[List[str]] = None,
    edges: Optional[Any] = None,
    directed: bool = False,
) -> str:
    """Compute canonical deterministic SHA-256 hash for community content."""
    payload = {
        "level": level,
        "index": index,
        "entity_ids": sorted(set(str(e) for e in entity_ids)),
        "child_ids": sorted(set(str(c) for c in (child_ids or []))),
        "edges": canonicalize_edges(edges, directed=directed),
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
    edges: List[Dict[str, Any]] = field(default_factory=list)
    directed: bool = False

    def __post_init__(self) -> None:
        if self.entity_ids:
            self.entity_ids = sorted(set(str(e) for e in self.entity_ids))
        else:
            self.entity_ids = []

        if self.child_ids:
            self.child_ids = sorted(set(str(c) for c in self.child_ids))
        else:
            self.child_ids = []

        if self.edges:
            self.edges = canonicalize_edges(self.edges, directed=self.directed)
        else:
            self.edges = []

        if not self.size:
            self.size = len(self.entity_ids)

        if not self.content_hash:
            self.content_hash = compute_community_hash(
                self.level,
                self.index,
                self.entity_ids,
                self.child_ids,
                edges=self.edges,
                directed=self.directed,
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
            "edges": list(self.edges),
            "directed": self.directed,
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
            edges=list(data.get("edges", [])),
            directed=bool(data.get("directed", False)),
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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._graph = graph
        self.metadata: Dict[str, Any] = dict(metadata or {})
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
            "metadata": dict(self.metadata),
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
        return cls(
            communities=communities,
            metadata=dict(data.get("metadata", {})),
        )

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
            if math.isnan(w):
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
        self._fallback_used = False

    def build(self, graph: Any) -> CommunityHierarchy:
        """Build hierarchical community structure from graph input."""
        self._fallback_used = False
        nx_graph = self._to_networkx(graph)

        if nx_graph.number_of_nodes() == 0:
            return CommunityHierarchy(
                communities={},
                graph=nx_graph,
                metadata={"algorithm": self.algorithm, "fallback": False},
            )

        if self.algorithm == "leiden":
            partitions = self._build_leiden_partitions(nx_graph)
        else:
            partitions = self._build_louvain_partitions(nx_graph)

        if self.max_levels is not None and self.max_levels > 0:
            partitions = partitions[:self.max_levels]

        return self._build_hierarchy_from_partitions(nx_graph, partitions)

    def _to_networkx(self, graph: Any) -> Union[nx.Graph, nx.DiGraph]:
        """Convert input graph into NetworkX Graph or DiGraph."""
        node_map: Dict[str, Any] = {}

        def register_node(raw_id: Any) -> str:
            if raw_id is None:
                return ""
            sid = str(raw_id)
            if not sid:
                return ""
            if sid in node_map and node_map[sid] != raw_id:
                raise ValueError(
                    f"Node identifier collision detected: distinct original "
                    f"nodes {repr(node_map[sid])} "
                    f"({type(node_map[sid]).__name__}) and {repr(raw_id)} "
                    f"({type(raw_id).__name__}) both serialize to '{sid}'."
                )
            node_map[sid] = raw_id
            return sid

        weight_attr = self.weight or "weight"

        if isinstance(graph, (nx.Graph, nx.DiGraph)):
            is_directed = (
                self.directed
                if self.directed is not None
                else graph.is_directed()
            )
            out_graph = nx.DiGraph() if is_directed else nx.Graph()
            for n, data in graph.nodes(data=True):
                sn = register_node(n)
                if sn:
                    out_graph.add_node(sn, **data)

            is_multi = getattr(graph, "is_multigraph", lambda: False)()
            for u, v, data in graph.edges(data=True):
                su = register_node(u)
                sv = register_node(v)
                if not su or not sv:
                    continue
                edge_data = dict(data)
                w = self._clean_weight(edge_data.get(weight_attr, 1.0))
                edge_data[weight_attr] = w
                if (
                    (is_multi or not is_directed)
                    and out_graph.has_edge(su, sv)
                ):
                    curr_w = self._clean_weight(
                        out_graph[su][sv].get(weight_attr, 1.0)
                    )
                    out_graph[su][sv][weight_attr] = curr_w + w
                else:
                    out_graph.add_edge(su, sv, **edge_data)
            return out_graph

        is_directed = self.directed if self.directed is not None else False
        out_graph = nx.DiGraph() if is_directed else nx.Graph()

        if isinstance(graph, KnowledgeGraph):
            for entity in graph.entities:
                if isinstance(entity, dict):
                    raw_id = entity.get("id", "")
                    eid = register_node(raw_id)
                    if eid:
                        out_graph.add_node(eid, **entity)
                else:
                    eid = register_node(entity)
                    if eid:
                        out_graph.add_node(eid)

            for rel in graph.relationships:
                if isinstance(rel, dict):
                    src_raw = rel.get("source", rel.get("source_id", ""))
                    tgt_raw = rel.get("target", rel.get("target_id", ""))
                    src = register_node(src_raw)
                    tgt = register_node(tgt_raw)
                    if src and tgt:
                        data = dict(rel)
                        w = self._clean_weight(data.get(weight_attr, 1.0))
                        data[weight_attr] = w
                        if out_graph.has_edge(src, tgt):
                            curr_w = self._clean_weight(
                                out_graph[src][tgt].get(weight_attr, 1.0)
                            )
                            out_graph[src][tgt][weight_attr] = curr_w + w
                        else:
                            out_graph.add_edge(src, tgt, **data)
                elif isinstance(rel, (tuple, list)) and len(rel) >= 2:
                    src = register_node(rel[0])
                    tgt = register_node(rel[1])
                    if src and tgt:
                        w = self._clean_weight(
                            rel[2]
                            if len(rel) >= 3 and isinstance(rel[2], (int, float))
                            else 1.0
                        )
                        if out_graph.has_edge(src, tgt):
                            curr_w = self._clean_weight(
                                out_graph[src][tgt].get(weight_attr, 1.0)
                            )
                            out_graph[src][tgt][weight_attr] = curr_w + w
                        else:
                            out_graph.add_edge(src, tgt, **{weight_attr: w})
            return out_graph

        if isinstance(graph, dict):
            if "entities" in graph or "relationships" in graph:
                for entity in graph.get("entities", []):
                    if isinstance(entity, dict):
                        raw_id = entity.get("id", "")
                        eid = register_node(raw_id)
                        if eid:
                            out_graph.add_node(eid, **entity)
                    else:
                        eid = register_node(entity)
                        if eid:
                            out_graph.add_node(eid)

                for rel in graph.get("relationships", []):
                    if isinstance(rel, dict):
                        src_raw = rel.get("source", rel.get("source_id", ""))
                        tgt_raw = rel.get("target", rel.get("target_id", ""))
                        src = register_node(src_raw)
                        tgt = register_node(tgt_raw)
                        if src and tgt:
                            data = dict(rel)
                            w = self._clean_weight(data.get(weight_attr, 1.0))
                            data[weight_attr] = w
                            if out_graph.has_edge(src, tgt):
                                curr_w = self._clean_weight(
                                    out_graph[src][tgt].get(weight_attr, 1.0)
                                )
                                out_graph[src][tgt][weight_attr] = curr_w + w
                            else:
                                out_graph.add_edge(src, tgt, **data)
                    elif isinstance(rel, (tuple, list)) and len(rel) >= 2:
                        src = register_node(rel[0])
                        tgt = register_node(rel[1])
                        if src and tgt:
                            w = self._clean_weight(
                                rel[2]
                                if len(rel) >= 3 and isinstance(rel[2], (int, float))
                                else 1.0
                            )
                            if out_graph.has_edge(src, tgt):
                                curr_w = self._clean_weight(
                                    out_graph[src][tgt].get(weight_attr, 1.0)
                                )
                                out_graph[src][tgt][weight_attr] = curr_w + w
                            else:
                                out_graph.add_edge(src, tgt, **{weight_attr: w})
                return out_graph

            if "nodes" in graph or "edges" in graph:
                for n in graph.get("nodes", []):
                    if isinstance(n, dict):
                        raw_id = n.get("id", "")
                        nid = register_node(raw_id)
                        if nid:
                            out_graph.add_node(nid, **n)
                    else:
                        nid = register_node(n)
                        if nid:
                            out_graph.add_node(nid)

                for e in graph.get("edges", []):
                    if isinstance(e, dict):
                        src_raw = e.get("source", e.get("source_id", ""))
                        tgt_raw = e.get("target", e.get("target_id", ""))
                        src = register_node(src_raw)
                        tgt = register_node(tgt_raw)
                        if src and tgt:
                            data = dict(e)
                            w = self._clean_weight(data.get(weight_attr, 1.0))
                            data[weight_attr] = w
                            if out_graph.has_edge(src, tgt):
                                curr_w = self._clean_weight(
                                    out_graph[src][tgt].get(weight_attr, 1.0)
                                )
                                out_graph[src][tgt][weight_attr] = curr_w + w
                            else:
                                out_graph.add_edge(src, tgt, **data)
                    elif isinstance(e, (tuple, list)) and len(e) >= 2:
                        src = register_node(e[0])
                        tgt = register_node(e[1])
                        if src and tgt:
                            w = self._clean_weight(
                                e[2]
                                if len(e) >= 3 and isinstance(e[2], (int, float))
                                else 1.0
                            )
                            if out_graph.has_edge(src, tgt):
                                curr_w = self._clean_weight(
                                    out_graph[src][tgt].get(weight_attr, 1.0)
                                )
                                out_graph[src][tgt][weight_attr] = curr_w + w
                            else:
                                out_graph.add_edge(src, tgt, **{weight_attr: w})
                return out_graph

            for node, nbrs in graph.items():
                node_id = register_node(node)
                if not node_id:
                    continue
                out_graph.add_node(node_id)
                if isinstance(nbrs, (list, set, tuple)):
                    for nbr in nbrs:
                        nbr_id = register_node(nbr)
                        if not nbr_id:
                            continue
                        if out_graph.has_edge(node_id, nbr_id):
                            curr_w = self._clean_weight(
                                out_graph[node_id][nbr_id].get(
                                    weight_attr, 1.0
                                )
                            )
                            out_graph[node_id][nbr_id][weight_attr] = (
                                curr_w + 1.0
                            )
                        else:
                            out_graph.add_edge(
                                node_id, nbr_id, **{weight_attr: 1.0}
                            )
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

    def _leiden_communities_native(
        self,
        G: Union[nx.Graph, nx.DiGraph],
        resolution: float = 1.0,
        seed: Optional[int] = None,
        weight: Optional[str] = "weight",
        max_iter: int = 20,
    ) -> List[Set[Any]]:
        """Native Leiden community detection with local moving and refinement."""
        nodes = list(G.nodes())
        n_nodes = len(nodes)
        if n_nodes <= 1:
            return [set(nodes)]

        rng = random.Random(seed)
        strengths: Dict[Any, float] = {}
        total_weight = 0.0
        adj: Dict[Any, Dict[Any, float]] = {n: {} for n in nodes}

        for u in nodes:
            u_strength = 0.0
            nbrs = set(G.successors(u) if G.is_directed() else G.neighbors(u))
            if G.is_directed():
                nbrs.update(G.predecessors(u))
            for v in nbrs:
                w = 0.0
                if G.has_edge(u, v):
                    w += self._clean_weight(
                        G[u][v].get(weight or "weight", 1.0)
                    )
                if G.is_directed() and G.has_edge(v, u):
                    w += self._clean_weight(
                        G[v][u].get(weight or "weight", 1.0)
                    )
                adj[u][v] = w
                u_strength += w
            strengths[u] = u_strength
            total_weight += u_strength

        m2 = total_weight
        if m2 <= 0.0:
            return [{n} for n in nodes]

        node_to_comm: Dict[Any, int] = {n: i for i, n in enumerate(nodes)}
        comm_to_nodes: Dict[int, Set[Any]] = {
            i: {n} for i, n in enumerate(nodes)
        }
        comm_tot: Dict[int, float] = {
            i: strengths[n] for i, n in enumerate(nodes)
        }

        improved = True
        iteration = 0
        while improved and iteration < max_iter:
            improved = False
            iteration += 1
            shuffled = list(nodes)
            rng.shuffle(shuffled)

            for u in shuffled:
                curr_c = node_to_comm[u]
                k_u = strengths[u]

                comm_weights: Dict[int, float] = defaultdict(float)
                for v, w in adj[u].items():
                    comm_weights[node_to_comm[v]] += w

                k_u_curr = comm_weights.get(curr_c, 0.0)
                best_c = curr_c
                best_gain = 0.0

                for cand_c, k_u_cand in comm_weights.items():
                    if cand_c == curr_c:
                        continue
                    tot_cand = comm_tot[cand_c]
                    tot_curr = comm_tot[curr_c]
                    gain = (k_u_cand - k_u_curr) / m2 - (
                        resolution * k_u * (tot_cand - (tot_curr - k_u))
                    ) / (m2 * m2)
                    if gain > best_gain:
                        best_gain = gain
                        best_c = cand_c

                if best_c != curr_c and best_gain > 1e-8:
                    comm_to_nodes[curr_c].remove(u)
                    comm_tot[curr_c] -= k_u
                    if not comm_to_nodes[curr_c]:
                        del comm_to_nodes[curr_c]
                        del comm_tot[curr_c]

                    node_to_comm[u] = best_c
                    comm_to_nodes[best_c].add(u)
                    comm_tot[best_c] += k_u
                    improved = True

        refined_comms: List[Set[Any]] = []
        for c_id, c_nodes in comm_to_nodes.items():
            if len(c_nodes) <= 1:
                refined_comms.append(set(c_nodes))
                continue

            sub_c_to_nodes: Dict[int, Set[Any]] = {}
            sub_node_to_c: Dict[Any, int] = {}
            for idx, u in enumerate(c_nodes):
                sub_c_to_nodes[idx] = {u}
                sub_node_to_c[u] = idx

            for u in c_nodes:
                curr_sub = sub_node_to_c[u]
                k_u = strengths[u]

                sub_weights: Dict[int, float] = defaultdict(float)
                for v, w in adj[u].items():
                    if v in c_nodes:
                        sub_weights[sub_node_to_c[v]] += w

                best_sub = curr_sub
                best_sub_gain = 0.0
                for cand_sub, k_u_cand in sub_weights.items():
                    if cand_sub == curr_sub:
                        continue
                    tot_cand = sum(
                        strengths[x] for x in sub_c_to_nodes[cand_sub]
                    )
                    tot_curr = sum(
                        strengths[x] for x in sub_c_to_nodes[curr_sub]
                    )
                    gain = (
                        k_u_cand - sub_weights.get(curr_sub, 0.0)
                    ) / m2 - (
                        resolution * k_u * (tot_cand - (tot_curr - k_u))
                    ) / (m2 * m2)
                    if gain > best_sub_gain:
                        best_sub_gain = gain
                        best_sub = cand_sub

                if best_sub != curr_sub and best_sub_gain > 1e-8:
                    sub_c_to_nodes[curr_sub].remove(u)
                    if not sub_c_to_nodes[curr_sub]:
                        del sub_c_to_nodes[curr_sub]
                    sub_node_to_c[u] = best_sub
                    sub_c_to_nodes[best_sub].add(u)

            for s_nodes in sub_c_to_nodes.values():
                if s_nodes:
                    refined_comms.append(set(s_nodes))

        return refined_comms

    def _detect_leiden_communities(
        self,
        G: Union[nx.Graph, nx.DiGraph],
        resolution: float = 1.0,
        weight: Optional[str] = "weight",
    ) -> List[Set[Any]]:
        """Detect communities using Leiden with optional C library fallback."""
        weight_key = weight or "weight"
        try:
            import igraph as ig
            import leidenalg

            nodes = list(G.nodes())
            node_idx = {n: i for i, n in enumerate(nodes)}
            ig_graph = ig.Graph(directed=G.is_directed())
            ig_graph.add_vertices(len(nodes))
            edges = []
            weights = []
            for u, v, data in G.edges(data=True):
                edges.append((node_idx[u], node_idx[v]))
                weights.append(
                    self._clean_weight(data.get(weight_key, 1.0))
                )

            ig_graph.add_edges(edges)
            if weights and weight is not None:
                ig_graph.es["weight"] = weights

            partition = leidenalg.find_partition(
                ig_graph,
                leidenalg.RBConfigurationVertexPartition,
                weights="weight" if (weights and weight is not None) else None,
                resolution_parameter=resolution,
                seed=self.seed,
            )
            return [{nodes[idx] for idx in comm} for comm in partition]
        except (ImportError, Exception):
            pass

        try:
            from cdlib import algorithms

            cd_comms = algorithms.leiden(G, weights=weight)
            return [set(c) for c in cd_comms.communities]
        except (ImportError, Exception):
            pass

        return self._leiden_communities_native(
            G, resolution=resolution, seed=self.seed, weight=weight
        )

    def _build_louvain_partitions(
        self, G: Union[nx.Graph, nx.DiGraph]
    ) -> List[List[Set[Any]]]:
        """Generate multi-level coarsened partitions using Louvain."""
        if G.number_of_nodes() == 0:
            return []
        if G.number_of_nodes() == 1:
            return [[set(G.nodes())]]

        partitions: List[List[Set[Any]]] = []
        weight_attr = self.weight or "weight"
        current_g = G.copy()
        for u, v in current_g.edges():
            current_g[u][v][weight_attr] = self._clean_weight(
                current_g[u][v].get(weight_attr, 1.0)
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

            curr_weight = self.weight if level == 0 else weight_attr

            try:
                raw_comms = nx_comm.louvain_communities(
                    current_g,
                    weight=curr_weight,
                    resolution=curr_res,
                    threshold=self.threshold,
                    seed=self.seed,
                )
            except (
                ZeroDivisionError,
                FloatingPointError,
                RuntimeError,
                nx.NetworkXError,
            ) as e:
                logger.warning(
                    f"Louvain partitioning failed at level {level}: {e}. "
                    f"Using singleton fallback. Traceback:\n"
                    f"{traceback.format_exc()}"
                )
                self._fallback_used = True
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
                w = self._clean_weight(data.get(weight_attr, 1.0))
                if next_g.has_edge(su, sv):
                    next_g[su][sv][weight_attr] += w
                else:
                    next_g.add_edge(su, sv, **{weight_attr: w})

            if next_g.number_of_edges() == 0:
                break

            current_g = next_g
            super_to_orig = new_super_to_orig

        return partitions

    def _build_leiden_partitions(
        self, G: Union[nx.Graph, nx.DiGraph]
    ) -> List[List[Set[Any]]]:
        """Generate multi-level coarsened partitions using Leiden."""
        if G.number_of_nodes() == 0:
            return []
        if G.number_of_nodes() == 1:
            return [[set(G.nodes())]]

        partitions: List[List[Set[Any]]] = []
        weight_attr = self.weight or "weight"
        current_g = G.copy()
        for u, v in current_g.edges():
            current_g[u][v][weight_attr] = self._clean_weight(
                current_g[u][v].get(weight_attr, 1.0)
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

            curr_weight = self.weight if level == 0 else weight_attr

            try:
                raw_comms = self._detect_leiden_communities(
                    current_g, resolution=curr_res, weight=curr_weight
                )
            except (
                ZeroDivisionError,
                FloatingPointError,
                RuntimeError,
                nx.NetworkXError,
            ) as e:
                logger.warning(
                    f"Leiden community detection failed at level {level}: {e}. "
                    f"Using singleton fallback. Traceback:\n"
                    f"{traceback.format_exc()}"
                )
                self._fallback_used = True
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
                w = self._clean_weight(data.get(weight_attr, 1.0))
                if next_g.has_edge(su, sv):
                    next_g[su][sv][weight_attr] += w
                else:
                    next_g.add_edge(su, sv, **{weight_attr: w})

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
                canonical_edges = canonicalize_edges(
                    sub.edges(data=True), directed=is_directed
                )
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
                    edges=canonical_edges,
                    directed=is_directed,
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
                        parent_id = Counter(parent_votes).most_common(1)[0][0]
                        child.parent_id = parent_id
                        if parent_id in communities:
                            communities[parent_id].child_ids.append(child.id)

        # Finalize child ordering and deterministic content hashes
        for comm in communities.values():
            comm.child_ids.sort()
            comm.content_hash = compute_community_hash(
                comm.level,
                comm.index,
                comm.entity_ids,
                comm.child_ids,
                edges=comm.edges,
                directed=is_directed,
            )

        metadata = {
            "algorithm": self.algorithm,
            "fallback": self._fallback_used,
            "levels_count": len(partitions),
        }
        return CommunityHierarchy(
            communities=communities, graph=G, metadata=metadata
        )
