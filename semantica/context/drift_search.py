"""
DRIFT Search Engine Module.

Implements Directed Reasoning and Iterative Filtering Tree (DRIFT) hybrid
search combining global thematic community framing, directed facet reasoning,
local entity-hop graph retrieval, semantic drift pruning, and dual-attributed
executive synthesis.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from ..kg.community_hierarchy import CommunityHierarchy
from ..kg.community_summarizer import CommunityReport, estimate_tokens
from ..utils.logging import get_logger
from .context_retriever import RetrievedContext

logger = get_logger("drift_search")


@dataclass
class DriftFacet:
    """Targeted sub-query and seed entity target for directed reasoning."""

    sub_query: str
    target_entities: List[str] = field(default_factory=list)
    rationale: str = ""
    depth: int = 0
    relevance_score: float = 1.0

    def __post_init__(self) -> None:
        self.sub_query = str(self.sub_query).strip()
        self.rationale = str(self.rationale).strip()
        self.depth = max(0, int(self.depth))
        try:
            r_val = float(self.relevance_score)
            if math.isnan(r_val) or math.isinf(r_val):
                r_val = 1.0
        except (ValueError, TypeError):
            r_val = 1.0
        self.relevance_score = max(0.0, min(1.0, r_val))

        if self.target_entities:
            self.target_entities = sorted(
                set(str(e).strip() for e in self.target_entities if e)
            )
        else:
            self.target_entities = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert DriftFacet to dictionary."""
        return {
            "sub_query": self.sub_query,
            "target_entities": list(self.target_entities),
            "rationale": self.rationale,
            "depth": self.depth,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DriftFacet":
        """Reconstruct DriftFacet from dictionary."""
        depth_val = d.get("depth")
        score_val = d.get("relevance_score")
        if score_val is None:
            score_val = d.get("score")
        return cls(
            sub_query=str(d.get("sub_query") or ""),
            target_entities=list(d.get("target_entities") or []),
            rationale=str(d.get("rationale") or ""),
            depth=int(depth_val) if depth_val is not None else 0,
            relevance_score=float(score_val) if score_val is not None else 1.0,
        )


class DriftFacetSchema(BaseModel):
    """Pydantic schema for individual DRIFT facets."""

    model_config = ConfigDict(extra="ignore")

    sub_query: str = Field(description="Targeted follow-up question")
    target_entities: List[str] = Field(
        default_factory=list, description="Seed entities to explore"
    )
    rationale: str = Field(
        default="", description="Reasoning behind exploring this facet"
    )
    relevance_score: float = Field(
        default=1.0,
        validation_alias=AliasChoices("relevance_score", "score"),
        description="Priority score between 0.0 and 1.0",
    )

    @field_validator("target_entities", mode="before")
    @classmethod
    def normalize_entities(cls, v: Any) -> List[str]:
        """Normalize target entities to list of strings."""
        if isinstance(v, list):
            return [str(e).strip() for e in v if e]
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return []

    @field_validator("relevance_score", mode="before")
    @classmethod
    def clamp_score(cls, v: Any) -> float:
        """Clamp relevance score to 0.0 - 1.0."""
        try:
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                return 1.0
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 1.0


class DriftFacetsResponseSchema(BaseModel):
    """Pydantic v2 schema for LLM facet generation response."""

    model_config = ConfigDict(extra="ignore")

    facets: List[DriftFacetSchema] = Field(
        default_factory=list, description="Generated exploration facets"
    )

    @field_validator("facets", mode="before")
    @classmethod
    def normalize_facets(cls, v: Any) -> List[Any]:
        """Normalize flexible facet outputs into valid schema objects."""
        if not isinstance(v, list):
            if isinstance(v, (dict, str)):
                v = [v]
            else:
                return []

        normalized = []
        for item in v:
            if isinstance(item, DriftFacetSchema):
                normalized.append(item)
            elif isinstance(item, dict):
                sq = (
                    item.get("sub_query")
                    or item.get("query")
                    or item.get("question")
                    or ""
                )
                ents = (
                    item.get("target_entities")
                    or item.get("entities")
                    or item.get("seed_entities")
                    or []
                )
                rat = item.get("rationale") or item.get("explanation") or ""
                score = (
                    item.get("relevance_score")
                    if item.get("relevance_score") is not None
                    else item.get("score", 1.0)
                )
                normalized.append(
                    {
                        "sub_query": str(sq),
                        "target_entities": ents,
                        "rationale": str(rat),
                        "relevance_score": score,
                    }
                )
            elif isinstance(item, str):
                normalized.append(
                    {
                        "sub_query": item.strip(),
                        "target_entities": [],
                        "rationale": "",
                        "relevance_score": 1.0,
                    }
                )
        return normalized


@dataclass
class DriftSearchResult:
    """Result of DRIFT hybrid search."""

    query: str
    answer: str
    thematic_framing: str = ""
    global_reports_used: List[str] = field(default_factory=list)
    verified_local_contexts: List[Dict[str, Any]] = field(default_factory=list)
    facets_explored: List[DriftFacet] = field(default_factory=list)
    depth_reached: int = 0
    pruned_fact_count: int = 0
    citations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_retrieved_contexts(self) -> List[RetrievedContext]:
        """
        Convert DRIFT search result into standard RetrievedContext objects.

        Primary answer is placed first with score 1.0, followed by verified
        local graph contexts. Returns an empty list if no global reports or
        verified local contexts are present.
        """
        contexts: List[RetrievedContext] = []

        if not self.global_reports_used and not self.verified_local_contexts:
            return contexts

        # Primary executive answer
        contexts.append(
            RetrievedContext(
                content=self.answer,
                score=1.0,
                source="drift_search",
                metadata={
                    "query": self.query,
                    "thematic_framing": self.thematic_framing,
                    "depth_reached": self.depth_reached,
                    "pruned_fact_count": self.pruned_fact_count,
                    "citations": list(self.citations),
                    "metrics": dict(self.metrics),
                },
                related_entities=[],
                related_relationships=[],
            )
        )

        # Verified local graph contexts
        for fact in self.verified_local_contexts:
            src = str(fact.get("source", ""))
            tgt = str(fact.get("target", ""))
            src_name = str(fact.get("source_name") or src)
            tgt_name = str(fact.get("target_name") or tgt)
            rel = str(fact.get("relation", "RELATED_TO"))
            desc = str(fact.get("description", ""))

            content_text = f"({src_name}) -[{rel}]-> ({tgt_name})"
            if desc:
                content_text += f": {desc}"

            score_val = float(fact.get("alignment_score", fact.get("score", 0.8)))
            scaled_score = max(0.0, min(1.0, score_val))

            entities = [{"id": src, "name": src_name}]
            if tgt and tgt != src:
                entities.append({"id": tgt, "name": tgt_name})

            rel_data = {
                "source": src,
                "target": tgt,
                "type": rel,
                **dict(fact.get("attributes", {})),
            }

            contexts.append(
                RetrievedContext(
                    content=content_text,
                    score=scaled_score,
                    source=str(fact.get("source_id", "local_graph")),
                    metadata={
                        "source": src,
                        "target": tgt,
                        "source_name": src_name,
                        "target_name": tgt_name,
                        "relation": rel,
                        "canonical_id": fact.get("canonical_id", ""),
                        "edge_id": fact.get("edge_id", ""),
                        "depth": fact.get("depth", 0),
                        "alignment_score": score_val,
                        **dict(fact.get("attributes", {})),
                    },
                    related_entities=entities,
                    related_relationships=[rel_data],
                )
            )

        return contexts

    def to_dict(self) -> Dict[str, Any]:
        """Serialize DriftSearchResult to dictionary."""
        return {
            "query": self.query,
            "answer": self.answer,
            "thematic_framing": self.thematic_framing,
            "global_reports_used": list(self.global_reports_used),
            "verified_local_contexts": list(self.verified_local_contexts),
            "facets_explored": [f.to_dict() for f in self.facets_explored],
            "depth_reached": self.depth_reached,
            "pruned_fact_count": self.pruned_fact_count,
            "citations": list(self.citations),
            "metrics": dict(self.metrics),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DriftSearchResult":
        """Deserialize DriftSearchResult from dictionary."""
        raw_facets = d.get("facets_explored", [])
        facets = [
            DriftFacet.from_dict(f) if isinstance(f, dict) else f
            for f in raw_facets
        ]
        return cls(
            query=str(d.get("query", "")),
            answer=str(d.get("answer", "")),
            thematic_framing=str(d.get("thematic_framing", "")),
            global_reports_used=list(d.get("global_reports_used", [])),
            verified_local_contexts=list(d.get("verified_local_contexts", [])),
            facets_explored=facets,
            depth_reached=int(d.get("depth_reached", 0)),
            pruned_fact_count=int(d.get("pruned_fact_count", 0)),
            citations=list(d.get("citations", [])),
            metrics=dict(d.get("metrics", {})),
        )


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute cosine similarity between two numerical vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _extract_words(text: str) -> Set[str]:
    """Extract normalized lowercase alphanumeric word tokens from text."""
    if not text:
        return set()
    return set(re.findall(r"\b\w+\b", text.lower()))


def _truncate_to_tokens(
    text: str,
    max_tokens: int,
    token_counter: Optional[Callable[[str], int]] = None,
) -> str:
    """Truncate text to fit within max_tokens without breaking prematurely."""
    if not text or max_tokens <= 0:
        return ""
    if estimate_tokens(text, token_counter) <= max_tokens:
        return text
    low = 0
    high = len(text)
    best = 0
    while low <= high:
        mid = (low + high) // 2
        cand = text[:mid]
        if estimate_tokens(cand, token_counter) <= max_tokens:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return text[:best].rstrip()


def _first_non_none(
    d: Dict[str, Any], keys: Sequence[str], default: Any = None
) -> Any:
    """Return first value in d matching any key whose value is not None."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _first_attr_non_none(
    obj: Any, attrs: Sequence[str], default: Any = None
) -> Any:
    """Return first attribute on obj matching any attr name whose value is not None."""
    for a in attrs:
        if hasattr(obj, a):
            val = getattr(obj, a)
            if val is not None:
                return val
    return default


class DriftSearchEngine:
    """
    DRIFT Hybrid Search Engine for Hierarchical GraphRAG.

    Executes global thematic framing, directed reasoning facet generation,
    local entity-hop traversal with in-memory adjacency indexing, semantic
    drift filtering, iterative deepening, and dual-attributed synthesis.
    """

    def __init__(
        self,
        knowledge_graph: Optional[Any] = None,
        reports: Optional[
            Union[
                Sequence[Union[CommunityReport, Dict[str, Any]]],
                Dict[str, Any],
            ]
        ] = None,
        hierarchy: Optional[CommunityHierarchy] = None,
        llm: Optional[Any] = None,
        embedder: Optional[Callable[[str], List[float]]] = None,
        token_counter: Optional[Callable[[str], int]] = None,
        drift_threshold: float = 0.35,
        max_depth: int = 2,
        top_k_reports: int = 3,
        max_facets: int = 3,
        max_context_tokens: int = 4000,
        **kwargs: Any,
    ) -> None:
        self.logger = get_logger("drift_search")
        self.hierarchy = hierarchy
        self.llm = llm
        self.embedder = embedder
        self.token_counter = token_counter
        self.drift_threshold = max(0.0, min(1.0, float(drift_threshold)))
        self.max_depth = max(1, int(max_depth))
        self.top_k_reports = max(1, int(top_k_reports))
        self.max_facets = max(1, int(max_facets))
        self.max_context_tokens = max(1, int(max_context_tokens))
        self.response_token_budget = max(
            1, int(kwargs.get("response_token_budget", 500))
        )
        self.config = kwargs
        self._reports: List[CommunityReport] = []
        self._report_index: Dict[str, CommunityReport] = {}
        self._adjacency_index: Dict[str, List[Dict[str, Any]]] = {}
        self._node_meta: Dict[str, Dict[str, Any]] = {}
        self._alias_to_id: Dict[str, str] = {}

        if reports:
            self.set_reports(reports)
        if knowledge_graph is not None:
            self.set_knowledge_graph(knowledge_graph)

    def _resolve_node_id(self, entity_str: Any) -> str:
        """Resolve an entity name, alias, or ID to its canonical node ID."""
        if entity_str is None or str(entity_str).strip() == "":
            return ""
        s = str(entity_str).strip()
        if s in self._adjacency_index:
            return s
        lower = s.lower()
        if lower in self._alias_to_id:
            return self._alias_to_id[lower]
        return s

    def set_reports(
        self,
        reports: Union[
            Sequence[Union[CommunityReport, Dict[str, Any]]],
            Dict[str, Any],
        ],
    ) -> None:
        """Update active community reports collection."""
        loaded: List[CommunityReport] = []
        if isinstance(reports, dict):
            if "community_id" in reports and "summary" in reports:
                loaded.append(CommunityReport.from_dict(reports))
            else:
                for rep in reports.values():
                    if isinstance(rep, CommunityReport):
                        loaded.append(rep)
                    elif isinstance(rep, dict):
                        loaded.append(CommunityReport.from_dict(rep))
        elif isinstance(reports, Iterable) and not isinstance(reports, (str, bytes)):
            for rep in reports:
                if isinstance(rep, CommunityReport):
                    loaded.append(rep)
                elif isinstance(rep, dict):
                    loaded.append(CommunityReport.from_dict(rep))
        self._reports = loaded

    def set_knowledge_graph(self, graph: Any) -> None:
        """
        Build fast in-memory adjacency index from knowledge graph representation.

        Supports dictionary representations ('nodes'/'edges',
        'entities'/'relationships'), NetworkX graphs, and Semantica
        GraphStore/ContextGraph objects.
        """
        adj: Dict[str, List[Dict[str, Any]]] = {}
        nodes_info: Dict[str, Dict[str, Any]] = {}

        # 1. Extract nodes if present
        raw_nodes = None
        if isinstance(graph, dict):
            raw_nodes = graph.get("nodes") or graph.get("entities")
        else:
            nodes_attr = getattr(graph, "nodes", None)
            if isinstance(nodes_attr, dict):
                raw_nodes = nodes_attr
            elif (
                nodes_attr is not None
                and not isinstance(nodes_attr, (str, bytes))
                and hasattr(nodes_attr, "get")
                and callable(nodes_attr.get)
            ):
                if hasattr(graph, "get_nodes") and callable(graph.get_nodes):
                    try:
                        raw_nodes = graph.get_nodes(limit=10000)
                    except TypeError:
                        raw_nodes = graph.get_nodes()
                else:
                    try:
                        raw_nodes = nodes_attr.get(limit=10000)
                    except TypeError:
                        raw_nodes = nodes_attr.get()
            elif callable(nodes_attr):
                try:
                    raw_nodes = nodes_attr(data=True)
                except Exception:
                    raw_nodes = nodes_attr()
            elif nodes_attr is not None:
                raw_nodes = nodes_attr
            elif hasattr(graph, "get_nodes") and callable(graph.get_nodes):
                try:
                    raw_nodes = graph.get_nodes(limit=10000)
                except TypeError:
                    raw_nodes = graph.get_nodes()
            else:
                raw_nodes = getattr(graph, "entities", None)

        def _extract_node_entry(
            val: Any, fallback_id: Any = None
        ) -> tuple[str, Dict[str, Any]]:
            if isinstance(val, dict):
                raw_nid = _first_non_none(
                    val,
                    ("id", "name", "entity_id", "node_id"),
                    fallback_id,
                )
                nid = str(raw_nid).strip() if raw_nid is not None else ""
                d = dict(val)
                props = (
                    d.get("properties")
                    if isinstance(d.get("properties"), dict)
                    else (d.get("n") if isinstance(d.get("n"), dict) else {})
                )
                raw_name = _first_non_none(d, ("name", "label"), None)
                if raw_name is None and isinstance(props, dict):
                    raw_name = _first_non_none(props, ("name", "label"), None)
                if raw_name is None:
                    raw_name = nid
                d.setdefault("name", str(raw_name))
                d.setdefault("id", nid)
                return nid, d
            if hasattr(val, "to_dict") and callable(val.to_dict):
                d = dict(val.to_dict())
                raw_nid = _first_non_none(
                    d, ("id", "node_id", "name"), fallback_id
                )
                nid = str(raw_nid).strip() if raw_nid is not None else ""
                props = (
                    d.get("properties")
                    if isinstance(d.get("properties"), dict)
                    else {}
                )
                raw_name = _first_non_none(d, ("name", "label"), None)
                if raw_name is None and isinstance(props, dict):
                    raw_name = _first_non_none(props, ("name", "label"), None)
                if raw_name is None:
                    raw_name = nid
                d.setdefault("name", str(raw_name))
                d.setdefault("id", nid)
                return nid, d
            if hasattr(val, "node_id"):
                raw_nid = getattr(val, "node_id", None)
                if raw_nid is None:
                    raw_nid = fallback_id
                nid = str(raw_nid).strip() if raw_nid is not None else ""
                props = dict(getattr(val, "properties", {}) or {})
                meta = dict(getattr(val, "metadata", {}) or {})
                raw_name = _first_non_none(
                    props,
                    ("name", "label"),
                    _first_non_none(meta, ("label",), nid),
                )
                d = {
                    "id": nid,
                    "name": str(raw_name),
                    "type": str(getattr(val, "node_type", "")),
                    "content": str(getattr(val, "content", "")),
                    **props,
                    **meta,
                }
                return nid, d
            raw_nid = fallback_id if fallback_id is not None else val
            nid = str(raw_nid).strip() if raw_nid is not None else ""
            return nid, {"id": nid, "name": nid}

        if isinstance(raw_nodes, dict):
            for k, v in raw_nodes.items():
                nid, d = _extract_node_entry(v, k)
                if nid != "":
                    nodes_info[nid] = d
        elif isinstance(raw_nodes, Iterable) and not isinstance(
            raw_nodes, (str, bytes)
        ):
            for item in raw_nodes:
                if isinstance(item, tuple) and len(item) == 2:
                    nid = str(item[0]).strip() if item[0] is not None else ""
                    if isinstance(item[1], dict):
                        d = dict(item[1])
                        d.setdefault("id", nid)
                        props = (
                            d.get("properties")
                            if isinstance(d.get("properties"), dict)
                            else {}
                        )
                        raw_name = _first_non_none(
                            d,
                            ("name", "label"),
                            _first_non_none(props, ("name", "label"), nid),
                        )
                        d.setdefault("name", str(raw_name))
                        if nid != "":
                            nodes_info[nid] = d
                    else:
                        if nid != "":
                            nodes_info[nid] = {"id": nid, "name": nid}
                else:
                    nid, d = _extract_node_entry(item)
                    if nid != "":
                        nodes_info[nid] = d

        alias_map: Dict[str, str] = {}
        for nid, info in nodes_info.items():
            if nid != "":
                alias_map[nid.lower()] = nid
                name_val = info.get("name")
                if name_val is not None and str(name_val).strip():
                    alias_map[str(name_val).strip().lower()] = nid
                label_val = info.get("label")
                if label_val is not None and str(label_val).strip():
                    alias_map[str(label_val).strip().lower()] = nid
                aliases = info.get("aliases")
                if isinstance(aliases, (list, tuple, set)):
                    for a in aliases:
                        if a is not None and str(a).strip():
                            alias_map[str(a).strip().lower()] = nid
                props = info.get("properties")
                if isinstance(props, dict):
                    for prop_k in ("name", "label", "title"):
                        pv = props.get(prop_k)
                        if pv is not None and str(pv).strip():
                            alias_map[str(pv).strip().lower()] = nid

        # 2. Extract edges
        raw_edges = None
        if isinstance(graph, dict):
            raw_edges = graph.get("edges") or graph.get("relationships")
        else:
            rel_attr = getattr(graph, "relationships", None)
            if (
                rel_attr is not None
                and not isinstance(rel_attr, dict)
                and not isinstance(rel_attr, (str, bytes))
                and hasattr(rel_attr, "get")
                and callable(rel_attr.get)
            ):
                if hasattr(graph, "get_relationships") and callable(
                    graph.get_relationships
                ):
                    try:
                        raw_edges = graph.get_relationships(limit=10000)
                    except TypeError:
                        raw_edges = graph.get_relationships()
                else:
                    try:
                        raw_edges = rel_attr.get(limit=10000)
                    except TypeError:
                        raw_edges = rel_attr.get()
            else:
                raw_edges = getattr(graph, "edges", None)
                if callable(raw_edges):
                    try:
                        raw_edges = raw_edges(data=True)
                    except Exception:
                        raw_edges = raw_edges()
                elif raw_edges is None:
                    raw_edges = getattr(graph, "relationships", None)
                    if callable(raw_edges):
                        raw_edges = raw_edges()
                    elif raw_edges is None:
                        raw_edges = getattr(graph, "get_all_relationships", None)
                        if callable(raw_edges):
                            raw_edges = raw_edges()
                        elif hasattr(graph, "get_relationships") and callable(
                            graph.get_relationships
                        ):
                            try:
                                raw_edges = graph.get_relationships(limit=10000)
                            except TypeError:
                                raw_edges = graph.get_relationships()

        if raw_edges:
            edge_iterable = (
                raw_edges.values() if isinstance(raw_edges, dict) else raw_edges
            )
            for item in edge_iterable:
                src, tgt, rel, attrs, desc, edge_id = self._parse_edge_item(item)
                if src == "" or tgt == "":
                    continue

                if edge_id:
                    canonical_id = f"{src}->{rel}->{tgt}:{edge_id}"
                else:
                    payload = json.dumps(
                        {"rel": rel, "desc": desc, "attrs": attrs},
                        sort_keys=True,
                        default=str,
                    )
                    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
                    canonical_id = f"{src}->{rel}->{tgt}:{h}"

                edge_dict = {
                    "source": src,
                    "target": tgt,
                    "relation": rel,
                    "description": desc,
                    "attributes": attrs,
                    "canonical_id": canonical_id,
                }
                if edge_id:
                    edge_dict["edge_id"] = edge_id
                adj.setdefault(src, []).append(edge_dict)
                # For undirected retrieval traversal, allow bidirection lookup
                if src != tgt:
                    inv_dict = {
                        "source": tgt,
                        "target": src,
                        "relation": rel,
                        "description": desc,
                        "attributes": attrs,
                        "canonical_id": canonical_id,
                        "is_inverse": True,
                    }
                    if edge_id:
                        inv_dict["edge_id"] = edge_id
                    adj.setdefault(tgt, []).append(inv_dict)

                for ep in (src, tgt):
                    if ep not in nodes_info:
                        nodes_info[ep] = {"id": ep, "name": ep}
                    if ep.lower() not in alias_map:
                        alias_map[ep.lower()] = ep

        self._adjacency_index = adj
        self._node_meta = nodes_info
        self._alias_to_id = alias_map

    def _parse_edge_item(
        self, item: Any
    ) -> tuple[str, str, str, Dict[str, Any], str, str]:
        """Normalize raw edge into src, tgt, rel, attrs, desc, edge_id."""
        src_val = None
        tgt_val = None
        rel = "RELATED_TO"
        attrs: Dict[str, Any] = {}
        desc = ""
        edge_id = ""

        if isinstance(item, (tuple, list)):
            if len(item) >= 2:
                src_val = item[0]
                tgt_val = item[1]
            if len(item) >= 3:
                third = item[2]
                if isinstance(third, str):
                    rel = third
                elif isinstance(third, dict):
                    attrs = dict(third)
                    rel = str(
                        attrs.get("type")
                        or attrs.get("relation")
                        or attrs.get("rel")
                        or attrs.get("rel_type")
                        or attrs.get("edge_type")
                        or attrs.get("predicate")
                        or rel
                    )
                    desc = str(attrs.get("description") or attrs.get("desc") or "")
                    edge_id = str(
                        attrs.get("id")
                        or attrs.get("edge_id")
                        or attrs.get("rel_id")
                        or attrs.get("relationship_id")
                        or ""
                    )
            if len(item) >= 4 and isinstance(item[3], dict):
                fourth = dict(item[3])
                attrs.update(fourth)
                rel = str(
                    attrs.get("type")
                    or attrs.get("relation")
                    or attrs.get("rel")
                    or attrs.get("rel_type")
                    or attrs.get("edge_type")
                    or attrs.get("predicate")
                    or rel
                )
                if not desc:
                    desc = str(attrs.get("description") or attrs.get("desc") or "")
                if not edge_id:
                    edge_id = str(
                        attrs.get("id")
                        or attrs.get("edge_id")
                        or attrs.get("rel_id")
                        or attrs.get("relationship_id")
                        or ""
                    )
        elif isinstance(item, dict):
            src_val = _first_non_none(
                item,
                (
                    "source",
                    "source_id",
                    "start_node_id",
                    "start_id",
                    "start",
                    "from",
                    "subject",
                    "src",
                ),
                None,
            )
            tgt_val = _first_non_none(
                item,
                (
                    "target",
                    "target_id",
                    "end_node_id",
                    "end_id",
                    "end",
                    "to",
                    "object",
                    "dst",
                ),
                None,
            )
            rel = str(
                item.get("relation")
                or item.get("type")
                or item.get("rel_type")
                or item.get("predicate")
                or item.get("rel")
                or "RELATED_TO"
            )
            props = (
                item.get("properties")
                if isinstance(item.get("properties"), dict)
                else (item.get("r") if isinstance(item.get("r"), dict) else {})
            )
            desc = str(
                item.get("description")
                or item.get("desc")
                or props.get("description")
                or props.get("desc")
                or ""
            )
            raw_edge_id = _first_non_none(
                item,
                ("id", "edge_id", "rel_id", "relationship_id"),
                _first_non_none(
                    props,
                    ("id", "edge_id", "rel_id", "relationship_id"),
                    None,
                ),
            )
            edge_id = str(raw_edge_id).strip() if raw_edge_id is not None else ""
            attrs = dict(item.get("attributes") or {})
            if props and not attrs:
                attrs.update(props)
            for k, v in item.items():
                if k not in (
                    "source",
                    "source_id",
                    "start_node_id",
                    "start_id",
                    "start",
                    "target",
                    "target_id",
                    "end_node_id",
                    "end_id",
                    "end",
                    "from",
                    "to",
                    "subject",
                    "object",
                    "src",
                    "dst",
                    "relation",
                    "type",
                    "rel_type",
                    "predicate",
                    "description",
                    "desc",
                    "attributes",
                    "properties",
                    "r",
                    "id",
                    "edge_id",
                    "rel_id",
                    "relationship_id",
                ):
                    attrs[k] = v
        else:
            src_val = _first_attr_non_none(
                item,
                (
                    "source",
                    "source_id",
                    "start_node_id",
                    "start_id",
                    "start",
                    "from_node",
                    "from",
                    "subject",
                    "src",
                ),
                None,
            )
            tgt_val = _first_attr_non_none(
                item,
                (
                    "target",
                    "target_id",
                    "end_node_id",
                    "end_id",
                    "end",
                    "to_node",
                    "to",
                    "object",
                    "dst",
                ),
                None,
            )
            rel = str(
                getattr(item, "edge_type", None)
                or getattr(item, "type", None)
                or getattr(item, "rel_type", None)
                or getattr(item, "relation", None)
                or getattr(item, "predicate", None)
                or getattr(item, "rel", "RELATED_TO")
                or "RELATED_TO"
            )
            attrs_obj = (
                getattr(item, "attributes", None)
                or getattr(item, "metadata", None)
                or getattr(item, "properties", None)
                or {}
            )
            attrs = dict(attrs_obj) if isinstance(attrs_obj, dict) else {}
            raw_edge_id = _first_attr_non_none(
                item,
                ("id", "edge_id", "rel_id", "relationship_id"),
                _first_non_none(
                    attrs,
                    ("id", "edge_id", "rel_id", "relationship_id"),
                    None,
                ),
            )
            edge_id = str(raw_edge_id).strip() if raw_edge_id is not None else ""
            desc = str(
                getattr(item, "description", "")
                or getattr(item, "desc", "")
                or (attrs.get("description", "") if isinstance(attrs, dict) else "")
                or (attrs.get("desc", "") if isinstance(attrs, dict) else "")
                or ""
            )

        src = str(src_val).strip() if src_val is not None else ""
        tgt = str(tgt_val).strip() if tgt_val is not None else ""
        return (src, tgt, rel.strip(), attrs, desc.strip(), edge_id.strip())

    def _extract_thematic_framing(
        self, query: str, query_embedding: Optional[List[float]] = None
    ) -> tuple[str, List[str]]:
        """Stage 1: Extract top-K global community reports for thematic framing."""
        if not self._reports:
            return ("No global community reports provided.", [])

        scored: List[tuple[float, CommunityReport]] = []
        query_words = _extract_words(query)

        for rep in self._reports:
            score = 0.0
            if (
                query_embedding is not None
                and rep.embedding is not None
                and len(rep.embedding) == len(query_embedding)
            ):
                score = _cosine_similarity(query_embedding, rep.embedding)
            else:
                text = f"{rep.title} {rep.summary}"
                words = _extract_words(text)
                if query_words and words:
                    intersection = len(query_words & words)
                    union = len(query_words | words)
                    jaccard = intersection / float(union) if union > 0 else 0.0
                else:
                    jaccard = 0.0
                norm_rank = max(0.0, min(1.0, rep.rank))
                norm_impact = max(0.0, min(1.0, (rep.impact_rating - 1.0) / 9.0))
                score = (jaccard * 0.5) + (norm_rank * 0.3) + (norm_impact * 0.2)

            scored.append((score, rep))

        scored.sort(
            key=lambda item: (-item[0], -item[1].impact_rating, item[1].community_id)
        )

        selected = [item[1] for item in scored[: self.top_k_reports]]
        framing_parts: List[str] = []
        for r in selected:
            framing_parts.append(
                f"- [Community {r.community_id}] (Level {r.level}): "
                f"{r.title}. {r.summary}"
            )

        framing_text = "\n".join(framing_parts)
        report_ids = [r.community_id for r in selected]
        return (framing_text, report_ids)

    def _extract_json(self, text: str) -> Union[Dict[str, Any], List[Any]]:
        """Extract and parse JSON object from LLM response text."""
        cleaned = text.strip()
        try:
            val = json.loads(cleaned)
            if isinstance(val, (dict, list)):
                return val
        except Exception:
            pass

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.DOTALL)
        if match:
            block = match.group(1).strip()
            try:
                val = json.loads(block)
                if isinstance(val, (dict, list)):
                    return val
            except Exception:
                pass

        decoder = json.JSONDecoder()
        for i in range(len(cleaned)):
            if cleaned[i] in ("{", "["):
                try:
                    obj, _ = decoder.raw_decode(cleaned[i:])
                    if isinstance(obj, (dict, list)):
                        return obj
                except Exception:
                    pass

        raise ValueError(f"No valid JSON in response: {cleaned[:100]}...")

    def _coerce_facets_response(
        self, res: Any
    ) -> Optional[DriftFacetsResponseSchema]:
        """Coerce arbitrary response into DriftFacetsResponseSchema."""
        if isinstance(res, DriftFacetsResponseSchema):
            return res
        if isinstance(res, list):
            return DriftFacetsResponseSchema(facets=res)
        if isinstance(res, dict):
            if "facets" not in res and any(
                k in res
                for k in ("sub_query", "query", "question", "target_entities")
            ):
                return DriftFacetsResponseSchema(facets=[res])
            return DriftFacetsResponseSchema.model_validate(res)
        if hasattr(res, "model_dump") and callable(res.model_dump):
            return DriftFacetsResponseSchema.model_validate(res.model_dump())
        if hasattr(res, "__dict__"):
            try:
                return DriftFacetsResponseSchema.model_validate(vars(res))
            except Exception:
                pass
        if isinstance(res, str):
            try:
                parsed = self._extract_json(res)
                if isinstance(parsed, list):
                    return DriftFacetsResponseSchema(facets=parsed)
                elif isinstance(parsed, dict):
                    if "facets" not in parsed and any(
                        k in parsed
                        for k in (
                            "sub_query",
                            "query",
                            "question",
                            "target_entities",
                        )
                    ):
                        return DriftFacetsResponseSchema(facets=[parsed])
                    return DriftFacetsResponseSchema.model_validate(parsed)
            except Exception:
                pass
        return None

    def _generate_facets(
        self, query: str, thematic_framing: str
    ) -> List[DriftFacet]:
        """Stage 2: Directed reasoning to produce follow-up exploration facets."""
        llm = self.llm
        if llm is None:
            return self._extractive_facets_fallback(query)

        prompt_scaffold = (
            "You are a directed reasoning engine in a GraphRAG system.\n"
            "User Query: \n\n"
            "Global Thematic Framing:\n\n\n"
            "Instructions:\n"
            f"1. Generate up to {self.max_facets} targeted follow-up sub-queries "
            "to drill down into local knowledge graph relationships.\n"
            "2. For each sub-query, identify 1-3 seed target entities to inspect.\n"
            "3. Return the response in JSON with 'facets': list of "
            "{'sub_query', 'target_entities', 'rationale', 'relevance_score'}."
        )
        base_tokens = estimate_tokens(prompt_scaffold, self.token_counter)
        response_reserve = min(
            getattr(self, "response_token_budget", 500),
            max(10, self.max_context_tokens // 5),
        )
        available_content = max(
            0, self.max_context_tokens - base_tokens - response_reserve
        )
        query_budget = max(1, available_content // 2) if available_content > 0 else 0
        budgeted_query = (
            _truncate_to_tokens(query, query_budget, self.token_counter)
            if query_budget > 0
            else ""
        )
        query_tokens = (
            estimate_tokens(f"User Query: {budgeted_query}\n\n", self.token_counter)
            - estimate_tokens("User Query: \n\n", self.token_counter)
            if budgeted_query
            else 0
        )
        remaining_for_framing = max(
            0,
            self.max_context_tokens - base_tokens - query_tokens - response_reserve,
        )
        budgeted_framing = (
            _truncate_to_tokens(
                thematic_framing, remaining_for_framing, self.token_counter
            )
            if remaining_for_framing > 0
            else ""
        )

        prompt = (
            "You are a directed reasoning engine in a GraphRAG system.\n"
            f"User Query: {budgeted_query}\n\n"
            f"Global Thematic Framing:\n{budgeted_framing}\n\n"
            "Instructions:\n"
            f"1. Generate up to {self.max_facets} targeted follow-up sub-queries "
            "to drill down into local knowledge graph relationships.\n"
            "2. For each sub-query, identify 1-3 seed target entities to inspect.\n"
            "3. Return the response in JSON with 'facets': list of "
            "{'sub_query', 'target_entities', 'rationale', 'relevance_score'}."
        )

        facets_resp = None
        # Tier 1: generate_typed
        if hasattr(llm, "generate_typed") and callable(llm.generate_typed):
            try:
                try:
                    res = llm.generate_typed(
                        prompt, schema=DriftFacetsResponseSchema
                    )
                except TypeError:
                    res = llm.generate_typed(prompt)
                facets_resp = self._coerce_facets_response(res)
            except Exception as e:
                self.logger.warning(f"Drift Tier 1 generate_typed failed: {e}")

        # Tier 2: provider.generate_typed
        if (
            facets_resp is None
            and hasattr(llm, "provider")
            and hasattr(llm.provider, "generate_typed")
            and callable(llm.provider.generate_typed)
        ):
            try:
                try:
                    res = llm.provider.generate_typed(
                        prompt, schema=DriftFacetsResponseSchema
                    )
                except TypeError:
                    res = llm.provider.generate_typed(prompt)
                facets_resp = self._coerce_facets_response(res)
            except Exception as e:
                self.logger.warning(f"Drift Tier 2 failed: {e}")

        # Tier 3: generate_structured
        if facets_resp is None and hasattr(llm, "generate_structured"):
            try:
                res = llm.generate_structured(prompt)
                facets_resp = self._coerce_facets_response(res)
            except Exception as e:
                self.logger.warning(f"Drift Tier 3 failed: {e}")

        # Tier 4: generate + JSON parse
        if facets_resp is None and hasattr(llm, "generate"):
            try:
                res = llm.generate(prompt)
                facets_resp = self._coerce_facets_response(res)
            except Exception as e:
                self.logger.warning(f"Drift Tier 4 failed: {e}")

        # Tier 5: callable
        if facets_resp is None and callable(llm):
            try:
                res = llm(prompt)
                facets_resp = self._coerce_facets_response(res)
            except Exception as e:
                self.logger.warning(f"Drift Tier 5 failed: {e}")

        if facets_resp and facets_resp.facets:
            return [
                DriftFacet(
                    sub_query=f.sub_query,
                    target_entities=f.target_entities,
                    rationale=f.rationale,
                    depth=0,
                    relevance_score=f.relevance_score,
                )
                for f in facets_resp.facets[: self.max_facets]
            ]

        return self._extractive_facets_fallback(query)

    def _extractive_facets_fallback(self, query: str) -> List[DriftFacet]:
        """Deterministic extractive fallback for facet generation."""
        query_words = _extract_words(query)
        candidate_entities: List[str] = []

        # Find matching entities in active reports or graph index
        for rep in self._reports:
            for ent in rep.member_entities:
                if ent.lower() in query.lower() or _extract_words(ent) & query_words:
                    if ent not in candidate_entities:
                        candidate_entities.append(ent)

        for nid, meta in self._node_meta.items():
            name = str(meta.get("name") or "")
            label = str(meta.get("label") or "")
            aliases = (
                meta.get("aliases")
                if isinstance(meta.get("aliases"), list)
                else []
            )
            names_to_check = [nid, name, label] + list(aliases)
            matched = any(
                n and (
                    n.lower() in query.lower()
                    or bool(_extract_words(n) & query_words)
                )
                for n in names_to_check
            )
            if matched:
                cand = name if name else nid
                if cand not in candidate_entities:
                    candidate_entities.append(cand)

        for nid in self._adjacency_index.keys():
            if nid.lower() in query.lower() or _extract_words(nid) & query_words:
                cand = str(self._node_meta.get(nid, {}).get("name") or nid)
                if cand not in candidate_entities:
                    candidate_entities.append(cand)

        if not candidate_entities and self._adjacency_index:
            for nid in sorted(self._adjacency_index.keys())[:3]:
                cand = str(self._node_meta.get(nid, {}).get("name") or nid)
                if cand not in candidate_entities:
                    candidate_entities.append(cand)

        facets: List[DriftFacet] = []
        for ent in candidate_entities[: self.max_facets]:
            facets.append(
                DriftFacet(
                    sub_query=f"Explore connections for {ent} regarding {query}",
                    target_entities=[ent],
                    rationale=f"Direct seed match for query entity: {ent}",
                    depth=0,
                    relevance_score=1.0,
                )
            )

        if not facets:
            facets.append(
                DriftFacet(
                    sub_query=query,
                    target_entities=[],
                    rationale="General fallback facet",
                    depth=0,
                    relevance_score=1.0,
                )
            )

        return facets

    def _compute_alignment_score(
        self,
        fact_text: str,
        query_context: str,
        query_embedding: Optional[List[float]] = None,
    ) -> float:
        """Compute semantic alignment score for Stage 4 drift pruning."""
        if self.embedder is not None and query_embedding is not None:
            try:
                fact_emb = self.embedder(fact_text)
                return _cosine_similarity(query_embedding, fact_emb)
            except Exception as e:
                self.logger.debug(f"Fact embedding alignment failed: {e}")

        # Heuristic token overlap & substring alignment
        fact_words = _extract_words(fact_text)
        query_words = _extract_words(query_context)
        if not fact_words or not query_words:
            return 0.0

        overlap = len(fact_words & query_words)
        union = len(fact_words | query_words)
        jaccard = overlap / float(union) if union > 0 else 0.0

        # Substring bonus capped to prevent runaway scores
        bonus = 0.0
        for qw in query_words:
            if len(qw) > 3 and qw in fact_text.lower():
                bonus += 0.15
        bonus = min(0.3, bonus)

        return min(1.0, (jaccard * 1.5) + bonus)

    def _traverse_and_prune(
        self,
        facets: List[DriftFacet],
        query: str,
        thematic_framing: str,
        query_embedding: Optional[List[float]] = None,
        max_depth: Optional[int] = None,
        drift_threshold: Optional[float] = None,
    ) -> tuple[List[Dict[str, Any]], int, int]:
        """
        Stages 3, 4, and 5: Local entity-hop traversal, drift pruning, and deepening.
        """
        verified_facts: List[Dict[str, Any]] = []
        visited_entities: Set[str] = set()
        seen_edges: Set[str] = set()
        pruned_count = 0
        depth_reached = 0
        accumulated_tokens = 0
        budget_reached = False

        eff_max_depth = (
            self.max_depth if max_depth is None else max(1, int(max_depth))
        )
        eff_drift_thresh = (
            self.drift_threshold
            if drift_threshold is None
            else max(0.0, min(1.0, float(drift_threshold)))
        )

        query_context = f"{query} {thematic_framing}"

        # Scaffold tokens measurement for budget allocation
        hybrid_scaffold = (
            "You are an authoritative intelligence analyst synthesizing a hybrid "
            f"knowledge answer.\nQuery: {query}\n\n"
            f"Macro Thematic Context:\n{thematic_framing}\n\n"
            "Verified Local Graph Relationships:\n\n\n"
            "Instructions:\n"
            "1. Synthesize a comprehensive answer directly resolving the query.\n"
            "2. Dual Attribution: cite macro assertions with [Community <id>] "
            "and cite micro local relationships as (EntityA -[REL]-> EntityB).\n"
            "3. Ground all assertions strictly in the provided macro and micro "
            "evidence.\n"
            "4. Be concise, coherent, and executive-ready."
        )
        scaffold_tokens = estimate_tokens(hybrid_scaffold, self.token_counter)
        response_reserve = min(500, max(10, self.max_context_tokens // 5))
        facts_budget = max(
            min(50, self.max_context_tokens),
            self.max_context_tokens - scaffold_tokens - response_reserve,
        )

        # Collect initial seed entities from facets, resolving names through alias map
        current_frontier: Set[str] = set()
        for f in facets:
            for ent in f.target_entities:
                if not ent:
                    continue
                resolved_id = self._resolve_node_id(ent)
                if resolved_id and resolved_id in self._adjacency_index:
                    current_frontier.add(resolved_id)
                elif ent in self._adjacency_index:
                    current_frontier.add(ent)

        for depth in range(eff_max_depth):
            if not current_frontier or budget_reached:
                break
            depth_reached = depth + 1
            next_frontier: Set[str] = set()

            for entity in sorted(current_frontier):
                if entity in visited_entities or budget_reached:
                    continue
                visited_entities.add(entity)

                edges = self._adjacency_index.get(entity, [])
                for edge in edges:
                    if budget_reached:
                        break
                    src = edge["source"]
                    tgt = edge["target"]
                    canon_id = edge.get(
                        "canonical_id", f"{src}->{edge['relation']}->{tgt}"
                    )
                    if canon_id in seen_edges:
                        continue
                    seen_edges.add(canon_id)

                    src_name = str(
                        self._node_meta.get(src, {}).get("name") or src
                    )
                    tgt_name = str(
                        self._node_meta.get(tgt, {}).get("name") or tgt
                    )

                    if edge.get("is_inverse"):
                        fact_text = (
                            f"({tgt_name}) -[{edge['relation']}]-> ({src_name}): "
                            f"{edge.get('description', '')}"
                        )
                    else:
                        fact_text = (
                            f"({src_name}) -[{edge['relation']}]-> ({tgt_name}): "
                            f"{edge.get('description', '')}"
                        )

                    score = self._compute_alignment_score(
                        fact_text, query_context, query_embedding
                    )

                    if score >= eff_drift_thresh:
                        fact_cost = estimate_tokens(fact_text, self.token_counter)
                        if accumulated_tokens + fact_cost > facts_budget:
                            budget_reached = True
                            break
                        if edge.get("is_inverse"):
                            verified_edge = {
                                "source": tgt,
                                "target": src,
                                "source_name": tgt_name,
                                "target_name": src_name,
                                "relation": edge["relation"],
                                "description": edge.get("description", ""),
                                "attributes": dict(edge.get("attributes", {})),
                            }
                        else:
                            verified_edge = {
                                "source": src,
                                "target": tgt,
                                "source_name": src_name,
                                "target_name": tgt_name,
                                "relation": edge["relation"],
                                "description": edge.get("description", ""),
                                "attributes": dict(edge.get("attributes", {})),
                            }
                        verified_edge["canonical_id"] = canon_id
                        if edge.get("edge_id"):
                            verified_edge["edge_id"] = edge["edge_id"]
                        verified_edge["alignment_score"] = score
                        verified_edge["depth"] = depth_reached
                        verified_facts.append(verified_edge)
                        accumulated_tokens += fact_cost
                        if tgt != "" and tgt not in visited_entities:
                            next_frontier.add(tgt)
                    else:
                        pruned_count += 1

                if budget_reached:
                    break

            if budget_reached:
                break

            current_frontier = next_frontier

        return (verified_facts, depth_reached, pruned_count)

    def _synthesize_hybrid(
        self,
        query: str,
        thematic_framing: str,
        verified_facts: List[Dict[str, Any]],
    ) -> str:
        """Stage 6: Authoritative dual-attributed executive synthesis."""
        llm = self.llm
        sorted_facts = sorted(
            verified_facts,
            key=lambda f: (
                -float(f.get("alignment_score", 0.0)),
                str(f.get("source", "")),
                str(f.get("target", "")),
            ),
        )

        # Token budgeting to guarantee prompt does not exceed max_context_tokens
        prompt_scaffold = (
            "You are an authoritative intelligence analyst synthesizing a hybrid "
            "knowledge answer.\nQuery: \n\n"
            "Macro Thematic Context:\n\n\n"
            "Verified Local Graph Relationships:\nNone\n\n"
            "Instructions:\n"
            "1. Synthesize a comprehensive answer directly resolving the query.\n"
            "2. Dual Attribution: cite macro assertions with [Community <id>] "
            "and cite micro local relationships as (EntityA -[REL]-> EntityB).\n"
            "3. Ground all assertions strictly in the provided macro and micro "
            "evidence.\n"
            "4. Be concise, coherent, and executive-ready."
        )
        base_tokens = estimate_tokens(prompt_scaffold, self.token_counter)
        response_reserve = min(
            getattr(self, "response_token_budget", 500),
            max(10, self.max_context_tokens // 5),
        )
        available_content = max(
            0, self.max_context_tokens - base_tokens - response_reserve
        )
        query_budget = max(1, available_content // 3) if available_content > 0 else 0
        budgeted_query = (
            _truncate_to_tokens(query, query_budget, self.token_counter)
            if query_budget > 0
            else ""
        )
        query_tokens = (
            estimate_tokens(f"Query: {budgeted_query}\n\n", self.token_counter)
            - estimate_tokens("Query: \n\n", self.token_counter)
            if budgeted_query
            else 0
        )
        available_for_context = max(
            0, self.max_context_tokens - base_tokens - query_tokens - response_reserve
        )
        framing_target = (
            available_for_context // 2 if available_for_context > 0 else 0
        )
        budgeted_framing = (
            _truncate_to_tokens(
                thematic_framing, framing_target, self.token_counter
            )
            if framing_target > 0
            else ""
        )
        framing_tokens = (
            estimate_tokens(budgeted_framing, self.token_counter)
            if budgeted_framing
            else 0
        )
        facts_budget = max(0, available_for_context - framing_tokens)

        facts_preview: List[str] = []
        accumulated_fact_tokens = 0
        for fact in sorted_facts:
            src = fact.get("source_name") or fact["source"]
            tgt = fact.get("target_name") or fact["target"]
            rel = fact["relation"]
            desc = fact.get("description", "")
            line = f"- ({src}) -[{rel}]-> ({tgt})"
            if desc:
                line += f": {desc}"
            line_cost = estimate_tokens(line + "\n", self.token_counter)
            if accumulated_fact_tokens + line_cost <= facts_budget:
                facts_preview.append(line)
                accumulated_fact_tokens += line_cost
            else:
                break

        facts_text = "\n".join(facts_preview) if facts_preview else "None"

        if llm is None:
            # Deterministic synthesis
            display_query = budgeted_query if budgeted_query else query
            lines = [f"DRIFT Hybrid Response for: '{display_query}'\n"]
            if budgeted_framing:
                lines.append("Macro Context:")
                lines.append(budgeted_framing)
                lines.append("")
            if facts_preview:
                lines.append("Verified Local Graph Facts:")
                lines.extend(facts_preview)
            return "\n".join(lines)

        prompt = (
            "You are an authoritative intelligence analyst synthesizing a hybrid "
            f"knowledge answer.\nQuery: {budgeted_query}\n\n"
            f"Macro Thematic Context:\n{budgeted_framing}\n\n"
            f"Verified Local Graph Relationships:\n{facts_text}\n\n"
            "Instructions:\n"
            "1. Synthesize a comprehensive answer directly resolving the query.\n"
            "2. Dual Attribution: cite macro assertions with [Community <id>] "
            "and cite micro local relationships as (EntityA -[REL]-> EntityB).\n"
            "3. Ground all assertions strictly in the provided macro and micro "
            "evidence.\n"
            "4. Be concise, coherent, and executive-ready."
        )

        try:
            if hasattr(llm, "generate") and callable(llm.generate):
                res = llm.generate(prompt)
            elif callable(llm):
                res = llm(prompt)
            else:
                raise TypeError(f"Unsupported LLM type: {type(llm)}")
            if isinstance(res, dict):
                return str(
                    res.get("text")
                    or res.get("response")
                    or res.get("content")
                    or json.dumps(res)
                )
            return str(res).strip()
        except Exception as e:
            self.logger.warning(f"DRIFT synthesis LLM failed: {e}")
            return (
                f"DRIFT answer for '{query}':\n\n{budgeted_framing}\n\n"
                f"Verified Facts:\n{facts_text}"
            )

    def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        max_depth: Optional[int] = None,
        drift_threshold: Optional[float] = None,
        **kwargs: Any,
    ) -> DriftSearchResult:
        """
        Execute full DRIFT hybrid global-local search pipeline.

        Args:
            query: User query string.
            query_embedding: Optional precomputed query vector.
            max_depth: Depth limit for local entity-hop exploration.
            drift_threshold: Alignment score cutoff to prune graph drift.
            **kwargs: Additional runtime options.

        Returns:
            DriftSearchResult with answer, verified contexts, citations, and metrics.
        """
        start_time = time.time()
        eff_max_depth = (
            self.max_depth if max_depth is None else max(1, int(max_depth))
        )
        eff_drift_thresh = (
            self.drift_threshold
            if drift_threshold is None
            else max(0.0, min(1.0, float(drift_threshold)))
        )

        if query_embedding is None and self.embedder is not None:
            try:
                query_embedding = self.embedder(query)
            except Exception as e:
                self.logger.warning(f"Query embedding calculation failed: {e}")

        # Stage 1: Thematic framing
        thematic_framing, global_reports_used = self._extract_thematic_framing(
            query, query_embedding
        )

        # Stage 2: Directed reasoning and facet generation
        facets = self._generate_facets(query, thematic_framing)

        # Stages 3, 4, 5: Local traversal, drift pruning, deepening
        (
            verified_facts,
            depth_reached,
            pruned_count,
        ) = self._traverse_and_prune(
            facets,
            query,
            thematic_framing,
            query_embedding,
            max_depth=eff_max_depth,
            drift_threshold=eff_drift_thresh,
        )

        # Sort verified_facts descending by alignment_score
        verified_facts.sort(
            key=lambda f: (
                -float(f.get("alignment_score", 0.0)),
                str(f.get("source", "")),
                str(f.get("target", "")),
            )
        )

        # Stage 6: Authoritative dual-attributed synthesis
        answer = self._synthesize_hybrid(query, thematic_framing, verified_facts)

        # Citation extraction
        raw_comm_cits = re.findall(
            r"\[Community\s+([A-Za-z0-9_\-]+)\]", answer, re.IGNORECASE
        )
        raw_rel_cits = re.findall(
            r"\(([^()]+?)\s*-\s*\[([^\]]+)\]\s*->\s*([^()]+?)\)",
            answer,
        )

        valid_comm_ids = set(str(c) for c in global_reports_used)
        comm_cits = [
            f"[Community {c}]"
            for c in sorted(set(raw_comm_cits))
            if str(c) in valid_comm_ids
        ]

        valid_triples_map = {}
        for f in verified_facts:
            s_id = str(f.get("source", "")).strip()
            t_id = str(f.get("target", "")).strip()
            s_name = str(f.get("source_name") or s_id).strip()
            t_name = str(f.get("target_name") or t_id).strip()
            rel = str(f.get("relation", "")).strip()
            disp = (s_name, rel, t_name)
            valid_triples_map[(s_id.lower(), rel.lower(), t_id.lower())] = disp
            valid_triples_map[(s_name.lower(), rel.lower(), t_name.lower())] = disp
            valid_triples_map[(s_name.lower(), rel.lower(), t_id.lower())] = disp
            valid_triples_map[(s_id.lower(), rel.lower(), t_name.lower())] = disp

        rel_cits: List[str] = []
        seen_rel_cits: Set[str] = set()
        for src_raw, rel_raw, tgt_raw in raw_rel_cits:
            s_clean = src_raw.strip()
            r_clean = rel_raw.strip()
            t_clean = tgt_raw.strip()
            t_clean_cand = (
                t_clean.split(":", 1)[0].strip() if ":" in t_clean else t_clean
            )
            key = (s_clean.lower(), r_clean.lower(), t_clean.lower())
            key_cand = (s_clean.lower(), r_clean.lower(), t_clean_cand.lower())
            canonical_triple = valid_triples_map.get(key) or valid_triples_map.get(
                key_cand
            )
            if canonical_triple:
                s_canon, r_canon, t_canon = canonical_triple
                cit_str = f"({s_canon} -[{r_canon}]-> {t_canon})"
                if cit_str not in seen_rel_cits:
                    seen_rel_cits.add(cit_str)
                    rel_cits.append(cit_str)

        citations = comm_cits + rel_cits
        if not citations and global_reports_used:
            citations = [f"[Community {c}]" for c in global_reports_used]

        duration = time.time() - start_time
        metrics = {
            "time_taken": duration,
            "depth_reached": depth_reached,
            "facets_generated": len(facets),
            "verified_facts_count": len(verified_facts),
            "pruned_facts_count": pruned_count,
            "global_reports_count": len(global_reports_used),
            "citations_count": len(citations),
        }

        return DriftSearchResult(
            query=query,
            answer=answer,
            thematic_framing=thematic_framing,
            global_reports_used=global_reports_used,
            verified_local_contexts=verified_facts,
            facets_explored=facets,
            depth_reached=depth_reached,
            pruned_fact_count=pruned_count,
            citations=citations,
            metrics=metrics,
        )
