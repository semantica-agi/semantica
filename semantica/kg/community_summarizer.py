"""
Hierarchical Community GraphRAG Summarizer Module.

Provides global summarization, centrality-based token budgeting,
multi-tier LLM unwrapping, thread-safe SHA-256 caching, and bottom-up
hierarchical synthesis for community reports.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..utils.logging import get_logger
from ._graph_view import _edge_endpoints, _first_value
from .centrality_calculator import CentralityCalculator
from .community_hierarchy import (
    CommunityHierarchy,
    HierarchicalCommunity,
    compute_community_hash,
)

logger = get_logger("community_summarizer")

SUPPORTED_CENTRALITY_METRICS: Dict[str, str] = {
    "degree": "calculate_degree_centrality",
    "betweenness": "calculate_betweenness_centrality",
    "closeness": "calculate_closeness_centrality",
    "eigenvector": "calculate_eigenvector_centrality",
    "pagerank": "calculate_pagerank",
}

ENDPOINT_KEYS: Set[str] = {
    "source",
    "target",
    "source_id",
    "target_id",
    "subject",
    "object",
    "start",
    "end",
    "start_id",
    "end_id",
    "from",
    "to",
    "from_id",
    "to_id",
    "src",
    "dst",
    "START_ID",
    "END_ID",
    ":START_ID",
    ":END_ID",
    "attributes",
}


def _item_to_entity_dict(item: Any) -> Dict[str, Any]:
    """Normalize dictionary or entity object into an entity dictionary."""
    if isinstance(item, dict):
        return dict(item)
    d: Dict[str, Any] = {}
    for attr in (
        "id",
        "entity_id",
        "name",
        "text",
        "type",
        "label",
        "entity_type",
        "description",
        "desc",
        "summary",
        "metadata",
        "confidence",
        "provenance",
        "evidence",
    ):
        val = getattr(item, attr, None)
        if val is not None:
            d[attr] = val
    if "id" not in d and hasattr(item, "text"):
        d["id"] = getattr(item, "text")
    if "name" not in d and hasattr(item, "text"):
        d["name"] = getattr(item, "text")
    return d


def _normalize_edge(edge: Any) -> Optional[Dict[str, Any]]:
    """Normalize raw edge tuple, dictionary, or object into standard dict."""
    endpoints = _edge_endpoints(edge)
    if endpoints is None:
        return None
    src, tgt = str(endpoints[0]), str(endpoints[1])
    if isinstance(edge, dict):
        rel = dict(edge)
        rel["source"] = src
        rel["target"] = tgt
        attrs = dict(rel.get("attributes") or {})
        for k, v in edge.items():
            if k not in ENDPOINT_KEYS:
                attrs.setdefault(k, v)
        rel["attributes"] = attrs
        rel.setdefault("type", str(attrs.get("type", "CONNECTED_TO")))
        return rel
    elif isinstance(edge, (tuple, list)):
        attrs = {}
        if len(edge) >= 3:
            if isinstance(edge[2], dict):
                attrs.update(edge[2])
            elif isinstance(edge[2], (int, float)):
                attrs["weight"] = float(edge[2])
            else:
                attrs["data"] = str(edge[2])
        return {
            "source": src,
            "target": tgt,
            "type": str(attrs.get("type", "CONNECTED_TO")),
            "attributes": attrs,
            **attrs,
        }
    else:
        rel_type = str(
            getattr(
                edge,
                "type",
                getattr(
                    edge,
                    "label",
                    getattr(edge, "predicate", "CONNECTED_TO"),
                ),
            )
        )
        attrs = getattr(edge, "attributes", {}) or {}
        attrs_dict = dict(attrs) if isinstance(attrs, dict) else {}
        for attr in (
            "weight",
            "confidence",
            "description",
            "evidence",
            "provenance",
        ):
            val = getattr(edge, attr, None)
            if val is not None:
                attrs_dict.setdefault(attr, val)
        return {
            "source": src,
            "target": tgt,
            "type": rel_type,
            "attributes": attrs_dict,
            **attrs_dict,
        }


def estimate_tokens(
    text: str,
    custom_counter: Optional[Callable[[str], int]] = None,
) -> int:
    """
    Estimate token count for a text string.

    Args:
        text: Input string to measure.
        custom_counter: Optional callable accepting string and returning int.

    Returns:
        Estimated number of tokens (0 if text is empty).
    """
    if not text:
        return 0
    if custom_counter is not None and callable(custom_counter):
        try:
            return max(0, int(custom_counter(text)))
        except Exception:
            pass
    return max(1, math.ceil(len(text) / 4.0))


@dataclass
class CommunityReport:
    """
    Structured summary report for a knowledge graph community.

    Represents an executive-level summary and detailed findings synthesized
    from member entities, internal relationships, and finer child communities.
    """

    community_id: str
    level: int
    title: str
    summary: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    impact_rating: float = 5.0
    rating_explanation: str = ""
    member_entities: List[str] = field(default_factory=list)
    content_hash: str = ""
    sub_communities: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    rank: float = 0.0
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.community_id = str(self.community_id)
        self.level = int(self.level)
        self.title = str(self.title).strip()
        if not self.title:
            self.title = f"Community {self.community_id}"
        self.summary = str(self.summary).strip()
        self.rating_explanation = str(self.rating_explanation).strip()

        try:
            r_val = float(self.impact_rating)
            if math.isnan(r_val) or math.isinf(r_val):
                r_val = 5.0
        except (ValueError, TypeError):
            r_val = 5.0
        self.impact_rating = max(1.0, min(10.0, r_val))

        try:
            rank_val = float(self.rank)
            if math.isnan(rank_val) or math.isinf(rank_val):
                rank_val = 0.0
        except (ValueError, TypeError):
            rank_val = 0.0
        self.rank = rank_val

        if self.member_entities:
            self.member_entities = sorted(
                set(str(e) for e in self.member_entities)
            )
        else:
            self.member_entities = []

        if self.sub_communities:
            self.sub_communities = sorted(
                set(str(c) for c in self.sub_communities)
            )
        else:
            self.sub_communities = []

        if self.parent_id is not None:
            self.parent_id = str(self.parent_id)

        if self.embedding is not None:
            self.embedding = [float(x) for x in self.embedding]

        if not isinstance(self.findings, list):
            self.findings = []
        else:
            norm_findings = []
            for item in self.findings:
                if isinstance(item, dict):
                    norm_findings.append(
                        {str(k): v for k, v in item.items()}
                    )
                else:
                    norm_findings.append(
                        {"summary": str(item), "explanation": ""}
                    )
            self.findings = norm_findings

        if not isinstance(self.metadata, dict):
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize community report to a dictionary."""
        return {
            "community_id": self.community_id,
            "level": self.level,
            "title": self.title,
            "summary": self.summary,
            "findings": [
                dict(item) if isinstance(item, dict) else item
                for item in self.findings
            ],
            "impact_rating": self.impact_rating,
            "rating_explanation": self.rating_explanation,
            "member_entities": list(self.member_entities),
            "content_hash": self.content_hash,
            "sub_communities": list(self.sub_communities),
            "parent_id": self.parent_id,
            "rank": self.rank,
            "embedding": (
                list(self.embedding) if self.embedding is not None else None
            ),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommunityReport":
        """Instantiate a community report from a dictionary."""
        raw_parent = data.get("parent_id")
        parent_id = str(raw_parent) if raw_parent is not None else None
        raw_embed = data.get("embedding")
        embedding = (
            [float(x) for x in raw_embed] if raw_embed is not None else None
        )
        findings = [
            dict(item) if isinstance(item, dict) else item
            for item in data.get("findings", [])
        ]
        return cls(
            community_id=str(data.get("community_id", "")),
            level=int(data.get("level", 0)),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            findings=findings,
            impact_rating=float(data.get("impact_rating", 5.0)),
            rating_explanation=str(data.get("rating_explanation", "")),
            member_entities=list(data.get("member_entities", [])),
            content_hash=str(data.get("content_hash", "")),
            sub_communities=list(data.get("sub_communities", [])),
            parent_id=parent_id,
            rank=float(data.get("rank", 0.0)),
            embedding=embedding,
            metadata=dict(data.get("metadata", {})),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize report to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "CommunityReport":
        """Instantiate report from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_markdown(self) -> str:
        """Format report into executive markdown presentation."""
        lines = [
            f"# {self.title}",
            "",
            f"**Community ID:** {self.community_id}  ",
            f"**Level:** {self.level}  ",
            f"**Impact Rating:** {self.impact_rating:.1f}/10  ",
        ]
        if self.rating_explanation:
            lines.append(f"*{self.rating_explanation}*")
        lines.extend([
            "",
            "## Summary",
            "",
            self.summary if self.summary else "No summary provided.",
            "",
            "## Key Findings",
            "",
        ])
        if self.findings:
            for idx, finding in enumerate(self.findings, 1):
                if isinstance(finding, dict):
                    heading = (
                        finding.get("summary")
                        or finding.get("title")
                        or finding.get("finding")
                        or finding.get("name")
                        or finding.get("claim")
                        or f"Finding {idx}"
                    )
                    explanation = (
                        finding.get("explanation")
                        or finding.get("description")
                        or finding.get("detail")
                        or finding.get("evidence")
                        or ""
                    )
                    if explanation:
                        lines.append(f"- **{heading}**: {explanation}")
                    else:
                        lines.append(f"- **{heading}**")
                else:
                    lines.append(f"- {finding}")
        else:
            lines.append("No specific findings reported.")

        if self.member_entities:
            lines.extend([
                "",
                "## Member Entities",
                "",
                ", ".join(self.member_entities),
            ])
        return "\n".join(lines)


class CommunityReportLLMSchema(BaseModel):
    """
    Pydantic schema for structured LLM community report generation.

    Includes resilient field validators to normalize model outputs,
    clamp numeric ratings, and coerce findings into lists of dictionaries.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str = Field(
        default="Community Summary",
        description="Concise theme title for the community.",
    )
    summary: str = Field(
        default="",
        description="Comprehensive summary of entities and dynamics.",
    )
    findings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured key findings and supporting context.",
    )
    impact_rating: float = Field(
        default=5.0,
        description="Impact severity rating clamped between 1.0 and 10.0.",
    )
    rating_explanation: str = Field(
        default="",
        description="Rationale justifying the assigned impact rating.",
    )

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, v: Any) -> str:
        if v is None:
            return "Community Summary"
        s = str(v).strip()
        return s if s else "Community Summary"

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, dict)):
            return json.dumps(v)
        return str(v).strip()

    @field_validator("impact_rating", mode="before")
    @classmethod
    def _normalize_impact_rating(cls, v: Any) -> float:
        if v is None:
            return 5.0
        val = 5.0
        if isinstance(v, (int, float)):
            val = float(v)
        elif isinstance(v, str):
            match = re.search(r"(\d+(?:\.\d+)?)", v)
            if match:
                try:
                    val = float(match.group(1))
                except ValueError:
                    val = 5.0
        else:
            try:
                val = float(v)
            except (ValueError, TypeError):
                val = 5.0
        if math.isnan(val) or math.isinf(val):
            val = 5.0
        return max(1.0, min(10.0, val))

    @field_validator("rating_explanation", mode="before")
    @classmethod
    def _normalize_rating_explanation(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("findings", mode="before")
    @classmethod
    def _normalize_findings(cls, v: Any) -> List[Dict[str, Any]]:
        if v is None:
            return []
        if isinstance(v, dict):
            v = [v]
        elif isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    v = parsed
                elif isinstance(parsed, dict):
                    v = [parsed]
                else:
                    v = [{"summary": v.strip(), "explanation": ""}]
            except Exception:
                # Check for bullet list in string
                stripped = v.strip()
                raw_lines = [
                    ln.strip().lstrip("-* \t").strip()
                    for ln in stripped.split("\n")
                    if ln.strip()
                ]
                if len(raw_lines) > 1:
                    v = [
                        {"summary": ln, "explanation": ""}
                        for ln in raw_lines
                    ]
                else:
                    v = [{"summary": stripped, "explanation": ""}]
        elif not isinstance(v, list):
            return []

        normalized = []
        for item in v:
            if isinstance(item, dict):
                d = {str(k): val for k, val in item.items()}
                if "summary" not in d:
                    d["summary"] = str(
                        d.get("title")
                        or d.get("finding")
                        or d.get("name")
                        or d.get("claim")
                        or "Key Finding"
                    )
                if "explanation" not in d:
                    d["explanation"] = str(
                        d.get("description")
                        or d.get("detail")
                        or d.get("evidence")
                        or ""
                    )
                normalized.append(d)
            elif isinstance(item, str):
                normalized.append({"summary": item.strip(), "explanation": ""})
            else:
                normalized.append({"summary": str(item), "explanation": ""})
        return normalized


class CommunitySummarizer:
    """
    Engine for generating executive community reports in GraphRAG pipelines.

    Features:
        - Multi-tier LLM unwrapping across SDK wrappers and callables
        - Centrality-based deterministic token budgeting and context packing
        - Thread-safe SHA-256 content caching with atomic disk persistence
        - Subgraph extraction fallback when raw graph instance is unavailable
        - Bottom-up hierarchical synthesis across coarsening levels
    """

    def __init__(
        self,
        llm: Optional[Any] = None,
        max_tokens: int = 4000,
        token_counter: Optional[Callable[[str], int]] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        centrality_calculator: Optional[CentralityCalculator] = None,
        centrality_metric: str = "degree",
        cache_enabled: bool = True,
        embedder: Optional[Callable[[str], List[float]]] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.logger = get_logger("community_summarizer")
        self.llm = llm
        self.max_tokens = max(0, int(max_tokens))
        self.token_counter = token_counter
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.centrality_calculator = centrality_calculator
        metric = str(centrality_metric).lower().strip()
        if metric not in SUPPORTED_CENTRALITY_METRICS:
            supp = sorted(SUPPORTED_CENTRALITY_METRICS.keys())
            raise ValueError(
                f"Unsupported centrality metric '{centrality_metric}'. "
                f"Supported metrics: {supp}"
            )
        self.centrality_metric = metric
        self.cache_enabled = bool(cache_enabled)
        self.embedder = embedder
        self.system_prompt = system_prompt
        self.config = kwargs

        self._memory_cache: Dict[str, CommunityReport] = {}
        self._lock = threading.Lock()

        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, cache_key: str) -> Optional[Path]:
        """Generate safe, traversal-proof cache file path."""
        if self.cache_dir is None or not cache_key:
            return None
        safe_key = re.sub(r"[^\w\-]", "_", str(cache_key))
        return self.cache_dir / f"{safe_key}.json"

    def get_cached_report(self, cache_key: str) -> Optional[CommunityReport]:
        """Retrieve a cached community report by SHA-256 content hash."""
        if not cache_key or not self.cache_enabled:
            return None

        with self._lock:
            if cache_key in self._memory_cache:
                return self._memory_cache[cache_key]

            cache_file = self._cache_path(cache_key)
            if cache_file is not None and cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    report = CommunityReport.from_dict(data)
                    self._memory_cache[cache_key] = report
                    return report
                except Exception as e:
                    self.logger.warning(
                        f"Failed to read cache file {cache_file}: {e}"
                    )
        return None

    def cache_report(self, cache_key: str, report: CommunityReport) -> None:
        """Store a community report in cache with atomic disk persistence."""
        if not cache_key or not self.cache_enabled:
            return

        with self._lock:
            self._memory_cache[cache_key] = report

            cache_file = self._cache_path(cache_key)
            if cache_file is not None and self.cache_dir is not None:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=str(self.cache_dir),
                        delete=False,
                        suffix=".tmp",
                    ) as tf:
                        json.dump(
                            report.to_dict(), tf, indent=2, default=str
                        )
                        temp_path = tf.name
                    os.replace(temp_path, cache_file)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to persist cache file {cache_file}: {e}"
                    )
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                        except OSError:
                            pass

    def invalidate(self, cache_key: str) -> bool:
        """Invalidate a specific cache entry from memory and disk."""
        found = False
        with self._lock:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                found = True

            cache_file = self._cache_path(cache_key)
            if cache_file is not None and cache_file.exists():
                try:
                    cache_file.unlink()
                    found = True
                except OSError as e:
                    self.logger.warning(
                        f"Failed to remove cache file {cache_file}: {e}"
                    )
        return found

    def clear_cache(self) -> None:
        """Clear all in-memory and disk cache entries."""
        with self._lock:
            self._memory_cache.clear()
            if self.cache_dir is not None and self.cache_dir.exists():
                for json_file in self.cache_dir.glob("*.json"):
                    try:
                        json_file.unlink()
                    except OSError:
                        pass

    def _compute_cache_key(
        self,
        comm: HierarchicalCommunity,
        subgraph: Any = None,
        child_reports: Optional[List[CommunityReport]] = None,
        effective_max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        text_chunks: Optional[List[Any]] = None,
        rank: Optional[float] = None,
        embedding: Optional[List[float]] = None,
        llm_kwargs: Optional[Dict[str, Any]] = None,
        **extra_kwargs: Any,
    ) -> str:
        """
        Build a deterministic cache key for all report-affecting inputs.

        Returns comm.content_hash for baseline invocations to maintain backward
        compatibility with canonical content-hash disk persistence, and a
        composite SHA-256 hash when non-default evidence, budgets, or
        generation options differ.
        """
        if subgraph is None and "graph" in extra_kwargs:
            subgraph = extra_kwargs["graph"]
        if effective_max_tokens is None and "max_tokens" in extra_kwargs:
            effective_max_tokens = extra_kwargs["max_tokens"]
        if system_prompt is None and "prompt" in extra_kwargs:
            system_prompt = extra_kwargs["prompt"]
        base_hash = comm.content_hash or compute_community_hash(
            comm.level,
            comm.index,
            comm.entity_ids,
            comm.child_ids,
            edges=comm.edges,
            directed=comm.directed,
        )

        has_child_reports = bool(child_reports)
        DEFAULT_MAX_TOKENS = 4000
        has_custom_tokens = (
            effective_max_tokens is not None
            and (
                effective_max_tokens != self.max_tokens
                or effective_max_tokens != DEFAULT_MAX_TOKENS
            )
        )
        has_custom_prompt = bool(system_prompt or self.system_prompt)
        has_custom_metric = self.centrality_metric != "degree"
        has_chunks = bool(text_chunks)
        has_rank = rank is not None
        has_embedding = embedding is not None
        has_llm_kwargs = bool(llm_kwargs)

        graph_evidence: List[Any] = []
        if subgraph is not None:
            if hasattr(subgraph, "nodes") and hasattr(subgraph, "edges"):
                n_data = [
                    (str(n), dict(subgraph.nodes[n]))
                    for n in sorted(subgraph.nodes, key=str)
                ]
                e_data = [
                    (str(u), str(v), dict(d))
                    for u, v, d in sorted(
                        subgraph.edges(data=True),
                        key=lambda x: (str(x[0]), str(x[1])),
                    )
                ]
                if n_data or e_data:
                    graph_evidence = [n_data, e_data]
            elif isinstance(subgraph, dict):
                ents = (
                    subgraph.get("entities")
                    or subgraph.get("nodes")
                    or []
                )
                rels = (
                    subgraph.get("relationships")
                    or subgraph.get("edges")
                    or []
                )
                if isinstance(ents, dict):
                    ents_norm = sorted([
                        (str(k), dict(v) if isinstance(v, dict) else str(v))
                        for k, v in ents.items()
                    ])
                else:
                    ents_norm = [
                        dict(e) if isinstance(e, dict) else str(e)
                        for e in ents
                    ]
                rels_norm = [
                    dict(r) if isinstance(r, dict) else str(r)
                    for r in rels
                ]
                if ents_norm or rels_norm:
                    graph_evidence = [ents_norm, rels_norm]

        has_graph_evidence = bool(graph_evidence)

        if not (
            has_child_reports
            or has_custom_tokens
            or has_custom_prompt
            or has_custom_metric
            or has_chunks
            or has_rank
            or has_embedding
            or has_llm_kwargs
            or has_graph_evidence
        ):
            return base_hash

        child_payload = []
        if child_reports:
            for cr in sorted(child_reports, key=lambda r: str(r.community_id)):
                child_payload.append(
                    {
                        "id": str(cr.community_id),
                        "level": cr.level,
                        "impact": cr.impact_rating,
                        "hash": cr.content_hash,
                        "title": cr.title,
                        "summary": cr.summary,
                    }
                )

        chunks_payload = []
        if text_chunks:
            for c in text_chunks:
                if isinstance(c, dict):
                    chunks_payload.append(
                        {str(k): str(v) for k, v in sorted(c.items())}
                    )
                else:
                    chunks_payload.append(str(c))

        payload = {
            "base": base_hash,
            "child_reports": child_payload,
            "chunks": chunks_payload,
            "tokens": effective_max_tokens,
            "system_prompt": system_prompt or self.system_prompt or "",
            "metric": self.centrality_metric,
            "graph": graph_evidence,
            "rank": rank,
            "embedding": embedding,
            "llm_kwargs": {
                str(k): str(v) for k, v in sorted((llm_kwargs or {}).items())
            },
        }
        dumped = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        )
        variant_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]
        return f"{base_hash}_{variant_hash}"

    def _filter_nodes_from_graph(
        self, graph: Any, node_set: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract and filter nodes from dictionary or graph object."""
        ents: List[Dict[str, Any]] = []
        found_ids: Set[str] = set()

        raw_nodes = None
        if isinstance(graph, dict):
            for k in ("entities", "nodes"):
                if k in graph and graph[k]:
                    raw_nodes = graph[k]
                    break
        else:
            raw_nodes = getattr(graph, "entities", None)
            if raw_nodes is None:
                raw_nodes = getattr(graph, "nodes", None)
                if callable(raw_nodes):
                    raw_nodes = raw_nodes()

        if isinstance(raw_nodes, dict):
            for k, v in raw_nodes.items():
                nid = str(k)
                if nid in node_set:
                    if isinstance(v, dict):
                        d = dict(v)
                        d.setdefault("id", nid)
                        ents.append(d)
                    else:
                        ents.append({"id": nid, "name": str(v)})
                    found_ids.add(nid)
        elif raw_nodes:
            for item in raw_nodes:
                d = _item_to_entity_dict(item)
                nid = str(
                    _first_value(
                        d,
                        "id",
                        "entity_id",
                        "node_id",
                        "key",
                        "name",
                        "text",
                    )
                    or ""
                )
                name = str(d.get("name") or "")
                if nid and nid in node_set:
                    ents.append(d)
                    found_ids.add(nid)
                elif name and name in node_set:
                    ents.append(d)
                    found_ids.add(name)
                elif not isinstance(item, dict):
                    item_str = str(item)
                    if item_str in node_set:
                        ents.append({"id": item_str, "name": item_str})
                        found_ids.add(item_str)

        for eid in sorted(node_set):
            if eid not in found_ids:
                ents.append({"id": eid, "name": eid})

        return ents

    def _filter_edges_from_graph(
        self, graph: Any, node_set: Set[str]
    ) -> List[Dict[str, Any]]:
        """Extract and filter edges from dictionary or graph object."""
        rels: List[Dict[str, Any]] = []

        raw_edges = None
        if isinstance(graph, dict):
            for k in ("relationships", "edges"):
                if k in graph and graph[k]:
                    raw_edges = graph[k]
                    break
        else:
            raw_edges = getattr(graph, "relationships", None)
            if raw_edges is None:
                raw_edges = getattr(graph, "edges", None)
                if callable(raw_edges):
                    raw_edges = raw_edges()

        if not raw_edges:
            return rels

        for edge in raw_edges:
            norm = _normalize_edge(edge)
            if norm is None:
                continue
            if norm["source"] in node_set and norm["target"] in node_set:
                rels.append(norm)

        return rels

    def _extract_subgraph(
        self,
        community: HierarchicalCommunity,
        graph: Optional[Any] = None,
    ) -> Any:
        """Extract community subgraph with fallback to entity_ids and edges."""
        node_set: Set[str] = set(str(e) for e in community.entity_ids)

        if graph is not None:
            if isinstance(graph, CommunityHierarchy):
                try:
                    return graph.get_subgraph(community)
                except Exception as e:
                    self.logger.debug(
                        f"CommunityHierarchy.get_subgraph failed: {e}"
                    )

            if hasattr(graph, "subgraph") and callable(graph.subgraph):
                try:
                    matching = [
                        n for n in graph.nodes
                        if str(n) in node_set or n in node_set
                    ]
                    return graph.subgraph(matching).copy()
                except Exception as e:
                    self.logger.debug(f"graph.subgraph failed: {e}")

            is_dict_graph = isinstance(graph, dict) and any(
                k in graph
                for k in ("entities", "nodes", "relationships", "edges")
            )
            is_obj_graph = (
                hasattr(graph, "entities") or hasattr(graph, "nodes")
            ) and (
                hasattr(graph, "relationships") or hasattr(graph, "edges")
            )

            if is_dict_graph or is_obj_graph:
                try:
                    ents = self._filter_nodes_from_graph(graph, node_set)
                    rels = self._filter_edges_from_graph(graph, node_set)
                    raw_nodes = (
                        graph.get("nodes") if isinstance(graph, dict) else None
                    )
                    nodes_repr = (
                        {e["id"]: e for e in ents}
                        if isinstance(raw_nodes, dict)
                        else ents
                    )
                    return {
                        "entities": ents,
                        "relationships": rels,
                        "nodes": nodes_repr,
                        "edges": rels,
                    }
                except Exception as e:
                    self.logger.debug(f"Graph records filtering failed: {e}")

        # Subgraph extraction fallback when graph is None or unhandled
        try:
            import networkx as nx

            nx_graph = nx.DiGraph() if community.directed else nx.Graph()
            nx_graph.add_nodes_from(community.entity_ids)
            for edge in community.edges:
                src = edge.get("source")
                tgt = edge.get("target")
                if src is not None and tgt is not None:
                    attrs = edge.get("attributes") or {}
                    nx_graph.add_edge(str(src), str(tgt), **attrs)
            return nx_graph
        except (ImportError, Exception):
            return {
                "entities": [
                    {"id": str(e), "name": str(e)}
                    for e in community.entity_ids
                ],
                "relationships": [
                    {
                        "source": str(edge.get("source", "")),
                        "target": str(edge.get("target", "")),
                        "type": str(
                            (edge.get("attributes") or {}).get(
                                "type", "CONNECTED_TO"
                            )
                        ),
                        **(edge.get("attributes") or {}),
                    }
                    for edge in community.edges
                ],
            }

    def _compute_centrality(
        self,
        subgraph: Any,
        entity_ids: List[str],
    ) -> Dict[str, float]:
        """Compute centrality scores, handling non-NetworkX subgraphs."""
        scores: Dict[str, float] = {}
        if not entity_ids:
            return scores

        metric = str(self.centrality_metric).lower().strip()
        if metric not in SUPPORTED_CENTRALITY_METRICS:
            supp = sorted(SUPPORTED_CENTRALITY_METRICS.keys())
            raise ValueError(
                f"Unsupported centrality metric '{self.centrality_metric}'. "
                f"Supported metrics: {supp}"
            )

        method_name = SUPPORTED_CENTRALITY_METRICS[metric]
        calculator = (
            self.centrality_calculator
            if self.centrality_calculator is not None
            else CentralityCalculator()
        )
        calc_func = getattr(calculator, method_name, None)
        if calc_func is None or not callable(calc_func):
            raise ValueError(
                f"Calculator does not implement method '{method_name}' "
                f"for metric '{metric}'"
            )

        if not hasattr(subgraph, "nodes") and hasattr(
            calculator, "_to_networkx"
        ):
            try:
                calc_graph = calculator._to_networkx(subgraph)
            except Exception:
                calc_graph = subgraph
        else:
            calc_graph = subgraph

        try:
            res = calc_func(calc_graph)
            if isinstance(res, dict):
                cent_dict = (
                    res["centrality"]
                    if (
                        "centrality" in res
                        and isinstance(res["centrality"], dict)
                    )
                    else res
                )
                if isinstance(cent_dict, dict):
                    for k, v in cent_dict.items():
                        try:
                            scores[str(k)] = float(v)
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            self.logger.debug(f"Centrality calculation error: {e}")

        for eid in entity_ids:
            if str(eid) not in scores:
                scores[str(eid)] = 0.0

        return scores

    def _identify_bridge_edges(
        self,
        community: HierarchicalCommunity,
        child_reports: Optional[List[CommunityReport]] = None,
        subgraph: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Identify bridge edges connecting different sub-communities."""
        raw_edges: List[Dict[str, Any]] = []
        if subgraph is not None:
            if hasattr(subgraph, "edges") and callable(subgraph.edges):
                try:
                    for u, v, d in subgraph.edges(data=True):
                        norm = _normalize_edge((u, v, d))
                        if norm:
                            raw_edges.append(norm)
                except Exception as e:
                    self.logger.debug(
                        f"Failed extracting edges from subgraph: {e}"
                    )
            elif isinstance(subgraph, dict):
                sub_edges = (
                    subgraph.get("relationships")
                    or subgraph.get("edges")
                    or []
                )
                for rel in sub_edges:
                    norm = _normalize_edge(rel)
                    if norm:
                        raw_edges.append(norm)
            elif hasattr(subgraph, "relationships"):
                for rel in subgraph.relationships:
                    norm = _normalize_edge(rel)
                    if norm:
                        raw_edges.append(norm)

        if not raw_edges and community.edges:
            for e in community.edges:
                norm = _normalize_edge(e)
                if norm:
                    raw_edges.append(norm)

        if not raw_edges or not child_reports:
            return raw_edges

        node_to_child: Dict[str, str] = {}
        for cr in child_reports:
            for ent in cr.member_entities:
                node_to_child[str(ent)] = str(cr.community_id)

        bridge_edges = []
        internal_edges = []
        for e in raw_edges:
            src = str(e.get("source", ""))
            tgt = str(e.get("target", ""))
            src_child = node_to_child.get(src)
            tgt_child = node_to_child.get(tgt)
            if src_child and tgt_child and src_child != tgt_child:
                e_bridge = dict(e)
                e_bridge["_is_bridge"] = True
                bridge_edges.append(e_bridge)
            else:
                internal_edges.append(e)

        if bridge_edges:
            return bridge_edges + internal_edges
        return internal_edges

    def _pack_context(
        self,
        community: HierarchicalCommunity,
        subgraph: Any = None,
        child_reports: Optional[List[CommunityReport]] = None,
        max_tokens: Optional[int] = None,
        text_chunks: Optional[List[Union[str, Dict[str, Any]]]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Pack community context within token budget using centrality and impact.

        Accounts for all section headings, substantive attributes, and
        source text chunks strictly within the allocated budget.
        """
        if subgraph is None and "graph" in kwargs:
            subgraph = kwargs["graph"]
        if max_tokens is None and "budget" in kwargs:
            max_tokens = kwargs["budget"]
        budget = max_tokens if max_tokens is not None else self.max_tokens
        if budget <= 0:
            return ""

        base_header = (
            f"Community ID: {community.id}\n"
            f"Level: {community.level}\n"
            f"Total Member Entities: {len(community.entity_ids)}"
        )
        base_tokens = estimate_tokens(base_header, self.token_counter)
        if budget < base_tokens:
            truncated = base_header
            while (
                truncated
                and estimate_tokens(truncated, self.token_counter) > budget
            ):
                lines = truncated.rsplit("\n", 1)
                if len(lines) > 1 and lines[0]:
                    truncated = lines[0]
                else:
                    truncated = truncated[:-4].rstrip()
            return truncated

        remaining_budget = budget - base_tokens

        entity_attr_map: Dict[str, Dict[str, Any]] = {}
        if subgraph is not None:
            if hasattr(subgraph, "nodes") and not isinstance(subgraph, dict):
                try:
                    for n in subgraph.nodes:
                        n_str = str(n)
                        node_data = (
                            dict(subgraph.nodes[n])
                            if subgraph.nodes[n]
                            else {}
                        )
                        entity_attr_map[n_str] = node_data
                        if "name" in node_data and node_data["name"]:
                            entity_attr_map[str(node_data["name"])] = node_data
                except Exception:
                    pass
            elif isinstance(subgraph, dict):
                sub_ents = (
                    subgraph.get("entities")
                    or subgraph.get("nodes")
                    or []
                )
                if isinstance(sub_ents, dict):
                    for k, v in sub_ents.items():
                        k_str = str(k)
                        d = (
                            dict(v)
                            if isinstance(v, dict)
                            else {"id": k_str, "name": str(v)}
                        )
                        d.setdefault("id", k_str)
                        entity_attr_map[k_str] = d
                        if "name" in d and d["name"]:
                            entity_attr_map[str(d["name"])] = d
                elif isinstance(sub_ents, list):
                    for item in sub_ents:
                        d = _item_to_entity_dict(item)
                        nid = str(
                            _first_value(
                                d,
                                "id",
                                "entity_id",
                                "node_id",
                                "key",
                                "name",
                                "text",
                            )
                            or ""
                        )
                        if nid:
                            entity_attr_map[nid] = d
                        if "name" in d and d["name"]:
                            entity_attr_map[str(d["name"])] = d
                        if "id" in d and d["id"]:
                            entity_attr_map[str(d["id"])] = d
            elif hasattr(subgraph, "entities") or hasattr(subgraph, "nodes"):
                items = getattr(subgraph, "entities", None)
                if items is None:
                    items = getattr(subgraph, "nodes", [])
                    if callable(items):
                        items = items()
                if isinstance(items, dict):
                    for k, v in items.items():
                        k_str = str(k)
                        d = (
                            dict(v)
                            if isinstance(v, dict)
                            else {"id": k_str, "name": str(v)}
                        )
                        entity_attr_map[k_str] = d
                        if "name" in d and d["name"]:
                            entity_attr_map[str(d["name"])] = d
                elif items:
                    for item in items:
                        d = _item_to_entity_dict(item)
                        nid = str(
                            _first_value(
                                d,
                                "id",
                                "entity_id",
                                "node_id",
                                "key",
                                "name",
                                "text",
                            )
                            or ""
                        )
                        if nid:
                            entity_attr_map[nid] = d
                        if "name" in d and d["name"]:
                            entity_attr_map[str(d["name"])] = d

        if text_chunks is None:
            text_chunks = (
                getattr(community, "text_chunks", None)
                or (
                    community.metrics.get("text_chunks")
                    if isinstance(community.metrics, dict)
                    else None
                )
                or (
                    community.metrics.get("chunks")
                    if isinstance(community.metrics, dict)
                    else None
                )
            )

        packed_child_sections: List[str] = []
        tokens_used_children = 0
        if community.level >= 1 and child_reports and remaining_budget > 0:
            child_reports_budget = min(
                int(remaining_budget * 0.45), remaining_budget
            )
            section_hdr = "## Child Community Reports\n"
            sec_tokens = estimate_tokens(section_hdr, self.token_counter)
            if child_reports_budget > sec_tokens:
                sub_budget = child_reports_budget - sec_tokens
                sorted_child_reports = sorted(
                    child_reports,
                    key=lambda r: (
                        -float(r.impact_rating),
                        str(r.community_id),
                    ),
                )
                for cr in sorted_child_reports:
                    rating_str = f"{cr.impact_rating:.1f}/10"
                    cr_hdr = (
                        f"### Sub-Community {cr.community_id} "
                        f"(Level {cr.level}, Impact: {rating_str}): "
                        f"{cr.title}\n"
                    )
                    cr_text = f"{cr_hdr}{cr.summary}\n"
                    if cr.findings:
                        bullets = []
                        for f in cr.findings[:3]:
                            if isinstance(f, dict):
                                s = (
                                    f.get("summary")
                                    or f.get("title")
                                    or f.get("finding")
                                    or f.get("name")
                                    or f.get("claim")
                                    or ""
                                )
                                e = (
                                    f.get("explanation")
                                    or f.get("description")
                                    or f.get("detail")
                                    or f.get("evidence")
                                    or ""
                                )
                                bullets.append(f"{s}: {e}".strip(": "))
                            else:
                                bullets.append(str(f))
                        if bullets:
                            cr_text += (
                                "Key Findings:\n- "
                                + "\n- ".join(bullets)
                                + "\n"
                            )
                    t_count = estimate_tokens(cr_text, self.token_counter)
                    if tokens_used_children + t_count <= sub_budget:
                        packed_child_sections.append(cr_text)
                        tokens_used_children += t_count
                    else:
                        break
                if packed_child_sections:
                    tokens_used_children += sec_tokens
                    remaining_budget -= tokens_used_children

        packed_chunks: List[str] = []
        tokens_used_chunks = 0
        if text_chunks and remaining_budget > 0:
            chunks_budget = min(
                int(remaining_budget * 0.35), remaining_budget
            )
            section_hdr = "## Source Evidence / Text Excerpts\n"
            sec_tokens = estimate_tokens(section_hdr, self.token_counter)
            if chunks_budget > sec_tokens:
                sub_budget = chunks_budget - sec_tokens
                for chunk in text_chunks:
                    if isinstance(chunk, dict):
                        cid = (
                            chunk.get("id")
                            or chunk.get("chunk_id")
                            or chunk.get("source")
                            or ""
                        )
                        ctext = (
                            chunk.get("text")
                            or chunk.get("content")
                            or chunk.get("excerpt")
                            or str(chunk)
                        )
                        cline = (
                            f"- [{cid}]: {ctext}\n"
                            if cid
                            else f"- {ctext}\n"
                        )
                    else:
                        cline = f"- {str(chunk)}\n"
                    t_count = estimate_tokens(cline, self.token_counter)
                    if tokens_used_chunks + t_count <= sub_budget:
                        packed_chunks.append(cline)
                        tokens_used_chunks += t_count
                    else:
                        break
                if packed_chunks:
                    tokens_used_chunks += sec_tokens
                    remaining_budget -= tokens_used_chunks

        bridge_edges = self._identify_bridge_edges(
            community, child_reports, subgraph=subgraph
        )
        bridge_edges.sort(
            key=lambda e: (
                0 if e.get("_is_bridge") else 1,
                min(str(e.get("source", "")), str(e.get("target", ""))),
                max(str(e.get("source", "")), str(e.get("target", ""))),
                json.dumps(
                    {
                        k: v for k, v in (e.get("attributes") or {}).items()
                        if k != "_is_bridge"
                    },
                    sort_keys=True,
                    default=str,
                ),
            )
        )

        packed_edges: List[str] = []
        tokens_used_edges = 0
        if bridge_edges and remaining_budget > 0:
            edge_budget = min(
                int(remaining_budget * 0.45), remaining_budget
            )
            section_hdr = "## Key Relationships / Bridge Edges\n"
            sec_tokens = estimate_tokens(section_hdr, self.token_counter)
            if edge_budget > sec_tokens:
                sub_budget = edge_budget - sec_tokens
                for edge in bridge_edges:
                    endpoints = _edge_endpoints(edge)
                    if endpoints is not None:
                        src, tgt = str(endpoints[0]), str(endpoints[1])
                    else:
                        src = str(edge.get("source", ""))
                        tgt = str(edge.get("target", ""))
                    if not src or not tgt:
                        continue
                    attrs = dict(edge.get("attributes") or {})
                    for k, v in edge.items():
                        if k not in ENDPOINT_KEYS and k != "_is_bridge":
                            attrs.setdefault(k, v)
                    rel_type = (
                        edge.get("type")
                        or attrs.get("type")
                        or "CONNECTED_TO"
                    )
                    meta_items = []
                    if "weight" in attrs:
                        try:
                            meta_items.append(
                                f"weight: {float(attrs['weight']):.2f}"
                            )
                        except (ValueError, TypeError):
                            meta_items.append(f"weight: {attrs['weight']}")
                    if (
                        "confidence" in attrs
                        and attrs["confidence"] is not None
                    ):
                        try:
                            meta_items.append(
                                f"conf: {float(attrs['confidence']):.2f}"
                            )
                        except (ValueError, TypeError):
                            meta_items.append(f"conf: {attrs['confidence']}")
                    desc = attrs.get("description") or attrs.get("desc")
                    if desc:
                        meta_items.append(f"desc: {desc}")
                    if "evidence" in attrs and attrs["evidence"]:
                        meta_items.append(f"evidence: {attrs['evidence']}")
                    prov = (
                        attrs.get("provenance")
                        or attrs.get("source_id")
                        or attrs.get("chunk_id")
                    )
                    if not prov and attrs.get("source") != src:
                        prov = attrs.get("source")
                    if prov:
                        meta_items.append(f"provenance: {prov}")

                    for ak, av in sorted(attrs.items()):
                        if ak not in (
                            "type",
                            "weight",
                            "confidence",
                            "description",
                            "desc",
                            "evidence",
                            "provenance",
                            "source",
                            "source_id",
                            "chunk_id",
                            "attributes",
                            "_is_bridge",
                        ):
                            av_str = str(av).strip()
                            if av_str and len(av_str) < 50:
                                meta_items.append(f"{ak}: {av_str}")

                    if meta_items:
                        edge_line = (
                            f"- ({src}) -[{rel_type} "
                            f"({', '.join(meta_items[:5])})]-> ({tgt})\n"
                        )
                    else:
                        edge_line = f"- ({src}) -[{rel_type}]-> ({tgt})\n"

                    t_count = estimate_tokens(edge_line, self.token_counter)
                    if tokens_used_edges + t_count <= sub_budget:
                        packed_edges.append(edge_line)
                        tokens_used_edges += t_count
                    else:
                        break
                if packed_edges:
                    tokens_used_edges += sec_tokens
                    remaining_budget -= tokens_used_edges

        scores = self._compute_centrality(subgraph, community.entity_ids)
        sorted_entities = sorted(
            community.entity_ids,
            key=lambda e: (-scores.get(str(e), 0.0), str(e)),
        )

        packed_entities: List[str] = []
        tokens_used_entities = 0
        if sorted_entities and remaining_budget > 0:
            section_hdr = "## Anchor Entities (ranked by centrality)\n"
            sec_tokens = estimate_tokens(section_hdr, self.token_counter)
            if remaining_budget > sec_tokens:
                sub_budget = remaining_budget - sec_tokens
                for ent in sorted_entities:
                    score = scores.get(str(ent), 0.0)
                    ent_str = str(ent)
                    ent_data = entity_attr_map.get(ent_str, {})
                    name = (
                        ent_data.get("name")
                        or ent_data.get("text")
                        or ent_str
                    )
                    ent_type = (
                        ent_data.get("type")
                        or ent_data.get("label")
                        or ent_data.get("entity_type")
                    )
                    desc = (
                        ent_data.get("description")
                        or ent_data.get("desc")
                        or ent_data.get("summary")
                    )
                    meta = ent_data.get("metadata") or {}
                    if not desc and isinstance(meta, dict):
                        desc = (
                            meta.get("description")
                            or meta.get("desc")
                            or meta.get("summary")
                        )

                    prov = (
                        ent_data.get("provenance")
                        or ent_data.get("source")
                        or ent_data.get("source_id")
                        or ent_data.get("chunk_id")
                    )
                    if not prov and isinstance(meta, dict):
                        prov = (
                            meta.get("provenance")
                            or meta.get("source")
                            or meta.get("chunk_id")
                        )

                    evid = ent_data.get("evidence")
                    if not evid and isinstance(meta, dict):
                        evid = meta.get("evidence")

                    relevant_meta = []
                    conf = ent_data.get("confidence")
                    if conf is None and isinstance(meta, dict):
                        conf = meta.get("confidence")
                    if conf is not None:
                        try:
                            relevant_meta.append(f"conf: {float(conf):.2f}")
                        except (ValueError, TypeError):
                            relevant_meta.append(f"conf: {conf}")

                    if isinstance(meta, dict):
                        for mk, mv in sorted(meta.items()):
                            if mk not in (
                                "provenance",
                                "source",
                                "source_id",
                                "chunk_id",
                                "evidence",
                                "description",
                                "desc",
                                "summary",
                                "confidence",
                            ):
                                mv_str = str(mv).strip()
                                if mv_str and len(mv_str) < 60:
                                    relevant_meta.append(f"{mk}: {mv_str}")

                    for ek, ev in sorted(ent_data.items()):
                        if ek not in (
                            "id",
                            "entity_id",
                            "node_id",
                            "key",
                            "name",
                            "text",
                            "type",
                            "label",
                            "entity_type",
                            "description",
                            "desc",
                            "summary",
                            "metadata",
                            "provenance",
                            "source",
                            "source_id",
                            "chunk_id",
                            "evidence",
                            "confidence",
                        ):
                            ev_str = str(ev).strip()
                            if ev_str and len(ev_str) < 60:
                                relevant_meta.append(f"{ek}: {ev_str}")

                    prefix = f"- {name}" if name != ent_str else f"- {ent_str}"
                    attrs_list = []
                    if name != ent_str:
                        attrs_list.append(f"id: {ent_str}")
                    if ent_type and str(ent_type).upper() not in (
                        "UNKNOWN",
                        "NONE",
                    ):
                        attrs_list.append(f"type: {ent_type}")
                    attrs_list.append(f"centrality: {score:.3f}")
                    if relevant_meta:
                        attrs_list.extend(relevant_meta[:4])

                    ent_line = f"{prefix} ({', '.join(attrs_list)})"
                    if desc:
                        ent_line += f": {desc}"

                    text_val = ent_data.get("text")
                    if (
                        text_val
                        and str(text_val) != name
                        and str(text_val) != desc
                    ):
                        ent_line += f' (text: "{str(text_val)[:120]}")'

                    tags = []
                    if evid:
                        tags.append(f"evidence: {evid}")
                    if prov:
                        tags.append(f"provenance: {prov}")
                    if tags:
                        ent_line += f" [{', '.join(tags)}]"
                    ent_line += "\n"

                    t_count = estimate_tokens(ent_line, self.token_counter)
                    if tokens_used_entities + t_count <= sub_budget:
                        packed_entities.append(ent_line)
                        tokens_used_entities += t_count
                    else:
                        break

        sections = [base_header]
        if packed_child_sections:
            sections.append(
                "## Child Community Reports\n"
                + "".join(packed_child_sections)
            )

        if packed_chunks:
            sections.append(
                "## Source Evidence / Text Excerpts\n"
                + "".join(packed_chunks)
            )

        if packed_edges:
            sections.append(
                "## Key Relationships / Bridge Edges\n"
                + "".join(packed_edges)
            )

        if packed_entities:
            sections.append(
                "## Anchor Entities (ranked by centrality)\n"
                + "".join(packed_entities)
            )

        context_text = "\n\n".join(sections)
        while (
            context_text
            and estimate_tokens(context_text, self.token_counter) > budget
        ):
            lines = context_text.rsplit("\n", 1)
            if len(lines) > 1 and lines[0]:
                context_text = lines[0]
            else:
                context_text = context_text[:-4].rstrip()

        return context_text

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON object from LLM response text."""
        cleaned = text.strip()
        try:
            val = json.loads(cleaned)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

        # Try markdown code fences ```json ... ```
        match = re.search(
            r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.DOTALL
        )
        if match:
            block = match.group(1).strip()
            try:
                val = json.loads(block)
                if isinstance(val, dict):
                    return val
            except Exception:
                decoder = json.JSONDecoder()
                for i in range(len(block)):
                    if block[i] == "{":
                        try:
                            obj, _ = decoder.raw_decode(block[i:])
                            if isinstance(obj, dict):
                                return obj
                        except Exception:
                            pass

        # Scan text for first valid JSON object using raw_decode
        decoder = json.JSONDecoder()
        for i in range(len(cleaned)):
            if cleaned[i] == "{":
                try:
                    obj, _ = decoder.raw_decode(cleaned[i:])
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    pass

        raise ValueError(
            f"No valid JSON found in LLM output: {cleaned[:120]}..."
        )

    def _schema_from_freeform_text(
        self, text: str, community: HierarchicalCommunity
    ) -> CommunityReportLLMSchema:
        """Create fallback schema when LLM returns plain freeform text."""
        cleaned = text.strip()
        title = f"Community {community.id} Summary"
        findings = [
            {
                "summary": f"Insights for community {community.id}",
                "explanation": cleaned[:250],
            }
        ]
        return CommunityReportLLMSchema(
            title=title,
            summary=cleaned if cleaned else "No summary available.",
            findings=findings,
            impact_rating=5.0,
            rating_explanation="Generated from freeform text response.",
        )

    def _extractive_fallback(
        self, community: HierarchicalCommunity
    ) -> CommunityReportLLMSchema:
        """Deterministic extractive baseline when no LLM is provided."""
        preview = ", ".join(sorted(str(e) for e in community.entity_ids)[:8])
        title = f"Community {community.id} (Level {community.level})"
        summary = (
            f"Community {community.id} contains "
            f"{len(community.entity_ids)} entities including: {preview}."
        )
        findings = [
            {
                "summary": f"Cluster of {len(community.entity_ids)} entities",
                "explanation": (
                    f"Entities in community {community.id} form an "
                    f"interconnected sub-network at level {community.level}."
                ),
            }
        ]
        return CommunityReportLLMSchema(
            title=title,
            summary=summary,
            findings=findings,
            impact_rating=5.0,
            rating_explanation="Extractive baseline report.",
        )

    def _coerce_to_schema(
        self,
        res: Any,
        community: HierarchicalCommunity,
    ) -> Optional[CommunityReportLLMSchema]:
        """Coerce arbitrary response into CommunityReportLLMSchema."""
        if isinstance(res, CommunityReportLLMSchema):
            return res
        if isinstance(res, dict):
            return CommunityReportLLMSchema.model_validate(res)
        if hasattr(res, "model_dump") and callable(res.model_dump):
            return CommunityReportLLMSchema.model_validate(res.model_dump())
        if hasattr(res, "__dict__"):
            try:
                return CommunityReportLLMSchema.model_validate(vars(res))
            except Exception:
                pass
        if isinstance(res, str):
            try:
                parsed = self._extract_json(res)
                return CommunityReportLLMSchema.model_validate(parsed)
            except Exception:
                return self._schema_from_freeform_text(res, community)
        return None

    def _call_llm(
        self,
        prompt: Any,
        community: Any,
        **kwargs: Any,
    ) -> CommunityReportLLMSchema:
        """Invoke LLM via multi-tier unwrap strategy."""
        if isinstance(prompt, HierarchicalCommunity) and isinstance(
            community, str
        ):
            prompt, community = community, prompt
        llm = kwargs.get("llm") or self.llm
        if llm is None:
            return self._extractive_fallback(community)

        # Tier 1: llm.generate_typed
        tier1_attempted = False
        if hasattr(llm, "generate_typed") and callable(llm.generate_typed):
            tier1_attempted = True
            try:
                try:
                    res = llm.generate_typed(
                        prompt, schema=CommunityReportLLMSchema, **kwargs
                    )
                except TypeError:
                    res = llm.generate_typed(
                        prompt, schema=CommunityReportLLMSchema
                    )
                schema = self._coerce_to_schema(res, community)
                if schema is not None:
                    return schema
            except Exception as e:
                self.logger.warning(f"Tier 1 generate_typed failed: {e}")

        # Tier 2: llm.provider.generate_typed (e.g. semantica.llms.OpenAI)
        # Skip Tier 2 if Tier 1 was already attempted, since repo wrappers
        # delegate generate_typed directly to provider.generate_typed.
        if (
            not tier1_attempted
            and hasattr(llm, "provider")
            and hasattr(llm.provider, "generate_typed")
            and callable(llm.provider.generate_typed)
        ):
            try:
                try:
                    res = llm.provider.generate_typed(
                        prompt, schema=CommunityReportLLMSchema, **kwargs
                    )
                except TypeError:
                    res = llm.provider.generate_typed(
                        prompt, schema=CommunityReportLLMSchema
                    )
                schema = self._coerce_to_schema(res, community)
                if schema is not None:
                    return schema
            except Exception as e:
                self.logger.warning(
                    f"Tier 2 provider.generate_typed failed: {e}"
                )

        # Tier 3: llm.generate_structured
        if hasattr(llm, "generate_structured") and callable(
            llm.generate_structured
        ):
            try:
                try:
                    res = llm.generate_structured(prompt, **kwargs)
                except TypeError:
                    res = llm.generate_structured(prompt)
                schema = self._coerce_to_schema(res, community)
                if schema is not None:
                    return schema
                if isinstance(res, list) and res and isinstance(res[0], dict):
                    return CommunityReportLLMSchema.model_validate(res[0])
            except Exception as e:
                self.logger.warning(f"Tier 3 generate_structured failed: {e}")

        # Tier 4: llm.generate with regex/JSON parsing
        if hasattr(llm, "generate") and callable(llm.generate):
            try:
                try:
                    text_res = llm.generate(prompt, **kwargs)
                except TypeError:
                    text_res = llm.generate(prompt)
                schema = self._coerce_to_schema(text_res, community)
                if schema is not None:
                    return schema
            except Exception as e:
                self.logger.warning(f"Tier 4 generate failed: {e}")

        # Tier 5: callable(llm)
        if callable(llm):
            try:
                try:
                    res = llm(prompt, **kwargs)
                except TypeError:
                    res = llm(prompt)
                schema = self._coerce_to_schema(res, community)
                if schema is not None:
                    return schema
            except Exception as e:
                self.logger.warning(f"Tier 5 callable failed: {e}")

        self.logger.warning(
            "All LLM tiers failed; returning extractive fallback."
        )
        return self._extractive_fallback(community)

    def summarize_community(
        self,
        community: Union[HierarchicalCommunity, Dict[str, Any]],
        graph: Optional[Any] = None,
        child_reports: Optional[List[CommunityReport]] = None,
        use_cache: bool = True,
        max_tokens: Optional[int] = None,
        text_chunks: Optional[List[Union[str, Dict[str, Any]]]] = None,
        **kwargs: Any,
    ) -> CommunityReport:
        """
        Generate a structured community report for a single community.

        Args:
            community: HierarchicalCommunity or dict representation.
            graph: Optional graph instance or CommunityHierarchy.
            child_reports: Sub-community reports for hierarchical synthesis.
            use_cache: If True, checks and updates cache.
            max_tokens: Override context token budget.
            text_chunks: Optional source text chunks or evidence.
            **kwargs: Extra parameters passed to LLM generation.

        Returns:
            CommunityReport object.
        """
        if isinstance(community, dict):
            comm_data = dict(community)
            if "id" not in comm_data:
                comm_data["id"] = str(
                    comm_data.get("community_id", "c_0")
                )
            if "level" not in comm_data:
                comm_data["level"] = 0
            if "index" not in comm_data:
                comm_data["index"] = 0
            comm = HierarchicalCommunity.from_dict(comm_data)
        elif isinstance(community, HierarchicalCommunity):
            comm = community
        else:
            raise TypeError(
                "community must be a HierarchicalCommunity or dict"
            )

        content_hash = comm.content_hash
        if not content_hash:
            content_hash = compute_community_hash(
                comm.level,
                comm.index,
                comm.entity_ids,
                comm.child_ids,
                edges=comm.edges,
                directed=comm.directed,
            )
            comm.content_hash = content_hash

        total_budget = (
            max_tokens if max_tokens is not None else self.max_tokens
        )
        subgraph = self._extract_subgraph(comm, graph)

        chunks = (
            text_chunks
            or kwargs.get("text_chunks")
            or kwargs.get("chunks")
            or getattr(comm, "text_chunks", None)
            or (
                comm.metrics.get("text_chunks")
                if isinstance(comm.metrics, dict)
                else None
            )
            or (
                comm.metrics.get("chunks")
                if isinstance(comm.metrics, dict)
                else None
            )
        )

        llm_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in (
                "rank",
                "embedding",
                "use_cache",
                "child_reports",
                "max_tokens",
                "text_chunks",
                "chunks",
            )
        }

        cache_key = self._compute_cache_key(
            comm=comm,
            subgraph=subgraph if graph is not None else None,
            child_reports=child_reports,
            effective_max_tokens=total_budget,
            system_prompt=self.system_prompt,
            text_chunks=chunks,
            rank=kwargs.get("rank"),
            embedding=kwargs.get("embedding"),
            llm_kwargs=llm_kwargs,
        )

        if use_cache and self.cache_enabled:
            cached = self.get_cached_report(cache_key)
            if cached is not None:
                return cached

        if total_budget <= 0:
            schema = self._extractive_fallback(comm)
        else:
            system_instruction = self.system_prompt or (
                "You are an AI intelligence assistant summarizing knowledge "
                "graph communities into structured GraphRAG reports. Produce "
                "a JSON object with 'title', 'summary', 'findings' "
                "(list of {summary, explanation}), "
                "'impact_rating' (float 1.0 to 10.0), and "
                "'rating_explanation'."
            )

            prompt_template_empty = (
                f"{system_instruction}\n\n"
                f"Context Information:\n\n\n"
                "Return ONLY the structured JSON report."
            )
            fixed_overhead = estimate_tokens(
                prompt_template_empty, self.token_counter
            )
            context_budget = max(0, total_budget - fixed_overhead)

            context_text = self._pack_context(
                comm,
                subgraph,
                child_reports=child_reports,
                max_tokens=context_budget,
                text_chunks=chunks,
            )

            if context_text.strip():
                full_prompt = (
                    f"{system_instruction}\n\n"
                    f"Context Information:\n{context_text}\n\n"
                    "Return ONLY the structured JSON report."
                )
            else:
                full_prompt = (
                    f"{system_instruction}\n\n"
                    "Return ONLY the structured JSON report."
                )

            # Context-first prompt truncation
            if context_text.strip() and estimate_tokens(
                full_prompt, self.token_counter
            ) > total_budget:
                ctx_lines = context_text.splitlines()
                while ctx_lines and estimate_tokens(
                    f"{system_instruction}\n\nContext Information:\n"
                    f"{chr(10).join(ctx_lines)}\n\n"
                    "Return ONLY the structured JSON report.",
                    self.token_counter,
                ) > total_budget:
                    ctx_lines.pop()
                context_text = "\n".join(ctx_lines).strip()
                if context_text:
                    full_prompt = (
                        f"{system_instruction}\n\n"
                        f"Context Information:\n{context_text}\n\n"
                        "Return ONLY the structured JSON report."
                    )
                else:
                    full_prompt = (
                        f"{system_instruction}\n\n"
                        "Return ONLY the structured JSON report."
                    )

            # Strict total_budget enforcement: trim if still over budget
            while (
                full_prompt
                and estimate_tokens(
                    full_prompt, self.token_counter
                ) > total_budget
            ):
                lines = full_prompt.rsplit("\n", 1)
                if len(lines) > 1 and lines[0]:
                    full_prompt = lines[0]
                else:
                    full_prompt = full_prompt[:-4].rstrip()

            if not full_prompt.strip():
                schema = self._extractive_fallback(comm)
            else:
                schema = self._call_llm(full_prompt, comm, **llm_kwargs)

        rank = kwargs.get("rank")
        if rank is None:
            size_weight = 1.0 + math.log10(max(1, len(comm.entity_ids)))
            rank = round(float(schema.impact_rating * size_weight), 3)
        else:
            rank = float(rank)

        embedding = kwargs.get("embedding")
        if embedding is None and self.embedder is not None:
            try:
                embedding = self.embedder(
                    f"{schema.title}\n\n{schema.summary}"
                )
            except Exception as e:
                self.logger.warning(f"Embedder failed: {e}")

        sub_comms = list(comm.child_ids)
        if not sub_comms and child_reports:
            sub_comms = [str(cr.community_id) for cr in child_reports]

        report = CommunityReport(
            community_id=str(comm.id),
            level=int(comm.level),
            title=schema.title,
            summary=schema.summary,
            findings=schema.findings,
            impact_rating=schema.impact_rating,
            rating_explanation=schema.rating_explanation,
            member_entities=list(comm.entity_ids),
            content_hash=content_hash,
            sub_communities=sub_comms,
            parent_id=comm.parent_id,
            rank=rank,
            embedding=embedding,
            metadata={
                "size": comm.size,
                "directed": comm.directed,
                **dict(comm.metrics),
            },
        )

        if use_cache and self.cache_enabled:
            self.cache_report(cache_key, report)

        return report

    def summarize_hierarchy(
        self,
        hierarchy: CommunityHierarchy,
        graph: Optional[Any] = None,
        levels: Optional[List[int]] = None,
        use_cache: bool = True,
        max_tokens: Optional[int] = None,
        text_chunks: Optional[List[Union[str, Dict[str, Any]]]] = None,
        **kwargs: Any,
    ) -> Dict[str, CommunityReport]:
        """
        Synthesize community reports bottom-up across a multi-level hierarchy.

        Args:
            hierarchy: CommunityHierarchy container.
            graph: Optional graph instance.
            levels: Optional subset of hierarchy levels to summarize.
            use_cache: If True, uses SHA-256 caching.
            max_tokens: Override context token budget.
            text_chunks: Optional source text chunks or evidence.
            **kwargs: Extra arguments passed to single community summarization.

        Returns:
            Dictionary mapping community IDs to CommunityReport objects.
        """
        if hierarchy.is_empty:
            return {}

        all_levels = sorted(hierarchy.levels)
        target_levels = (
            set(levels) if levels is not None else set(all_levels)
        )
        target_levels = target_levels & set(all_levels)
        if not target_levels:
            return {}

        max_target_level = max(target_levels)

        # Determine all community IDs required to produce target levels
        needed_ids: Set[str] = set()
        for lvl in target_levels:
            for comm in hierarchy.get_communities_at_level(lvl):
                needed_ids.add(str(comm.id))

        # Bottom-up descendant tracking using BFS
        queue = list(needed_ids)
        visited = set(needed_ids)
        while queue:
            curr_id = queue.pop(0)
            comm_obj = hierarchy.get_community(curr_id)
            if comm_obj:
                for cid in comm_obj.child_ids:
                    cid_str = str(cid)
                    if cid_str not in visited:
                        visited.add(cid_str)
                        needed_ids.add(cid_str)
                        queue.append(cid_str)

        reports: Dict[str, CommunityReport] = {}
        target_graph = (
            graph if graph is not None else getattr(hierarchy, "_graph", None)
        )

        comm_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("child_reports", "levels", "text_chunks", "chunks")
        }

        # Process only levels up to max_target_level
        levels_to_process = [
            lvl for lvl in all_levels if lvl <= max_target_level
        ]
        for lvl in levels_to_process:
            communities = hierarchy.get_communities_at_level(lvl)
            for comm in communities:
                if str(comm.id) not in needed_ids:
                    continue

                child_reps = [
                    reports[str(cid)]
                    for cid in comm.child_ids
                    if str(cid) in reports
                ]

                report = self.summarize_community(
                    community=comm,
                    graph=target_graph,
                    child_reports=child_reps,
                    use_cache=use_cache,
                    max_tokens=max_tokens,
                    text_chunks=text_chunks,
                    **comm_kwargs,
                )
                reports[str(comm.id)] = report

        if levels is not None:
            return {
                cid: rep
                for cid, rep in reports.items()
                if rep.level in target_levels
            }

        return reports
