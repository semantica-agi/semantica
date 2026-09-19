"""
Canonical Anchor & Landing Protocol Module

Implements the three-layer graph model primitives (ADR-0015 companion):
a deterministic four-level landing protocol that maps any source string
to a stable canonical anchor node, plus the PendingTerm lifecycle that
turns un-landed raw spellings into first-class graph citizens awaiting
human adjudication.

Landing protocol (strictly deterministic, no LLM, no embedding-driven
auto-landing):

    Level 1  normalization table exact hit   -> canonical identity
    Level 2  canonical vocabulary hit        -> canonical identity
    Level 3a formula variant name pattern    -> lineage attachment (DERIVES_FROM)
    Level 4  PendingTerm                     -> adjudication queue

Level 3b (composition similarity) is deliberately a separate advisory
call: it produces *candidates* for the human adjudication queue and never
lands anything on its own.

Example Usage:
    >>> from semantica.kg.canonical import AnchorResolver
    >>> resolver = AnchorResolver(
    ...     alias_map={"herb": {"元胡": "延胡索"}},
    ...     vocab={"herb": {"延胡索", "黄芪"}},
    ...     formula_roster={"四物汤": {"当归", "川芎", "白芍", "熟地黄"}},
    ... )
    >>> resolver.land("元胡", "herb").anchor
    '延胡索'
    >>> resolver.land("四物汤加减", "formula").detail["base_formula"]
    '四物汤'
    >>> resolver.attach_by_composition("X方", {"当归", "川芎", "白芍", "熟地黄"})
    [{'formula': '四物汤', 'jaccard': 1.0}]

Author: Semantica Contributors
License: MIT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from ..utils.logging import get_logger

logger = get_logger("canonical")

# Landing provenance markers
VIA_NORMALIZATION = "normalization"
VIA_VOCABULARY = "vocabulary"
VIA_VARIANT_PATTERN = "variant_pattern"
VIA_PENDING = "pending"

# Identity landing keeps the term itself as the anchor; lineage attachment
# links the record-level entity to a classical formula anchor (DERIVES_FROM).
MODE_IDENTITY = "identity"
MODE_DERIVES = "derives"
MODE_PENDING = "pending"

# "半夏泻心汤加减" / "香砂六君子汤加味" / "柴胡疏肝散化裁" — base name is
# 2-12 chars so generic suffixes (自拟方, 经验方) never match.
VARIANT_NAME_PATTERN = re.compile(r"^(.{2,12}?)(加减|加味|化裁)$")

# PendingTerm sample cap: keep the raw term's exemplar records bounded so
# repeated bulk imports cannot grow the node unboundedly.
PENDING_SAMPLE_CAP = 5

TERM_TYPES = ("herb", "symptom", "syndrome", "formula", "therapy_method", "disease")


@dataclass
class AnchorResult:
    """Outcome of one ``AnchorResolver.land()`` call.

    ``anchor`` is the canonical name when landing succeeded; ``mode``
    distinguishes identity landing (levels 1-2) from lineage attachment
    (level 3a). Pending results carry ``anchor=None``.
    """

    term: str
    term_type: str
    anchor: Optional[str] = None
    via: str = VIA_PENDING
    mode: str = MODE_PENDING
    pending: bool = True
    detail: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Truthy when the term landed on an anchor (identity or derives)."""
        return self.anchor is not None


class AnchorResolver:
    """Deterministic four-level anchor landing resolver (ADR-0015).

    The resolver is storage-agnostic by default: alias maps, vocabularies
    and the classical formula roster are plain in-memory structures so the
    protocol itself stays unit-testable without a graph. When a connected
    ``Neo4jStore`` is supplied, the PendingTerm lifecycle methods persist
    ``:PendingTerm`` nodes in the graph.
    """

    def __init__(
        self,
        alias_map: Optional[Dict[str, Dict[str, str]]] = None,
        vocab: Optional[Dict[str, Iterable[str]]] = None,
        formula_roster: Optional[Dict[str, Set[str]]] = None,
        graph: Any = None,
        derives_jaccard_threshold: float = 0.8,
    ):
        """Initialize the resolver.

        Args:
            alias_map: term_type -> {raw spelling -> canonical name} (level 1)
            vocab: term_type -> iterable of canonical names (level 2)
            formula_roster: classical formula name -> set of normalized herb
                names; used by level 3a (name pattern) and level 3b
                (composition similarity candidates)
            graph: connected ``Neo4jStore`` for PendingTerm persistence
                (optional; lifecycle methods raise without it)
            derives_jaccard_threshold: minimum normalized herb-set Jaccard
                similarity for level 3b candidates (default 0.8, aligned
                with the classical-formula add/subtract tolerance)
        """
        self.logger = get_logger("anchor_resolver")
        self.alias_map: Dict[str, Dict[str, str]] = {
            k: dict(v) for k, v in (alias_map or {}).items()
        }
        self.vocab: Dict[str, Set[str]] = {
            k: set(v) for k, v in (vocab or {}).items()
        }
        self.formula_roster: Dict[str, Set[str]] = {
            k: set(v) for k, v in (formula_roster or {}).items()
        }
        self.graph = graph
        self.derives_jaccard_threshold = float(derives_jaccard_threshold)

    # ---- Landing protocol ----

    def land(self, term: str, term_type: str) -> AnchorResult:
        """Resolve a raw term to an anchor via the four-level protocol.

        Pure lookup — no graph writes. PendingTerm recording is a separate
        explicit call (:meth:`record_pending`) so dry-run passes stay
        side-effect free.
        """
        term = (term or "").strip()
        if not term:
            return AnchorResult(term="", term_type=term_type)

        # Level 1: normalization table exact hit
        canonical = self.alias_map.get(term_type, {}).get(term)
        if canonical:
            return AnchorResult(
                term=term, term_type=term_type, anchor=canonical,
                via=VIA_NORMALIZATION, mode=MODE_IDENTITY, pending=False,
                detail={"raw": term, "canonical": canonical})

        # Level 2: canonical vocabulary hit
        if term in self.vocab.get(term_type, set()):
            return AnchorResult(
                term=term, term_type=term_type, anchor=term,
                via=VIA_VOCABULARY, mode=MODE_IDENTITY, pending=False)

        # Level 3a: formula variant name pattern -> lineage attachment.
        # Only fires when the base name is on the classical formula roster
        # (文献自声明); unknown bases fall through to pending.
        if term_type == "formula":
            m = VARIANT_NAME_PATTERN.match(term)
            if m:
                base, suffix = m.group(1), m.group(2)
                if base in self.formula_roster:
                    return AnchorResult(
                        term=term, term_type=term_type, anchor=base,
                        via=VIA_VARIANT_PATTERN, mode=MODE_DERIVES, pending=False,
                        detail={"base_formula": base, "variant_suffix": suffix})

        # Level 4: pending
        return AnchorResult(term=term, term_type=term_type)

    def attach_by_composition(
        self, name: str, herbs: Iterable[str], threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Level 3b: composition-similarity candidates for lineage attachment.

        Computes normalized herb-set Jaccard similarity between the given
        herb set and every classical formula in the roster, returning
        candidates at or above the threshold sorted by similarity desc.
        Purely advisory — callers must route candidates into the human
        adjudication queue, never auto-create graph edges from them.
        """
        threshold = self.derives_jaccard_threshold if threshold is None else float(threshold)
        herb_set = {h for h in (herbs or {}) if h}
        if not herb_set or not self.formula_roster:
            return []
        out: List[Dict[str, Any]] = []
        for formula, roster_herbs in self.formula_roster.items():
            if not roster_herbs:
                continue
            union = herb_set | roster_herbs
            jaccard = len(herb_set & roster_herbs) / len(union) if union else 0.0
            if jaccard >= threshold:
                out.append({
                    "formula": formula,
                    "jaccard": round(jaccard, 4),
                    "shared": sorted(herb_set & roster_herbs),
                    "missing_from_record": sorted(roster_herbs - herb_set),
                    "extra_in_record": sorted(herb_set - roster_herbs),
                })
        out.sort(key=lambda c: (-c["jaccard"], c["formula"]))
        return out

    # ---- PendingTerm lifecycle (graph-backed) ----

    def _require_graph(self) -> Any:
        if self.graph is None:
            raise RuntimeError("AnchorResolver 需要连接的 Neo4jStore 才能操作 PendingTerm")
        return self.graph

    def record_pending(self, raw: str, term_type: str,
                       sample: str = "", batch: str = "") -> Dict[str, Any]:
        """Upsert a ``:PendingTerm`` node: create or bump freq + samples.

        Idempotent per (raw, term_type); samples capped so bulk re-imports
        converge to a stable node state.
        """
        graph = self._require_graph()
        raw = (raw or "").strip()
        if not raw:
            return {"raw": "", "created": False}
        result = graph.execute_query(
            "MERGE (p:PendingTerm {raw: $raw, term_type: $tt}) "
            "ON CREATE SET p.freq = 1, p.samples = CASE WHEN $sample = '' THEN [] ELSE [$sample] END, "
            "               p.first_seen_batch = $batch, p.status = 'open', p.created_at = datetime() "
            "ON MATCH SET p.freq = coalesce(p.freq, 0) + 1, "
            "             p.samples = CASE WHEN $sample = '' OR $sample IN coalesce(p.samples, []) "
            "                              THEN coalesce(p.samples, []) "
            "                              ELSE coalesce(p.samples, []) + [$sample] END, "
            # 裁决终态粘滞（PRD-0021 R3）：promoted/rejected 不因重导入复活回 open；
            # freq/samples 照常累计（rejected 且 freq 增长 = 天然复审信号）。
            "             p.status = CASE WHEN coalesce(p.status, 'open') IN ['promoted', 'rejected'] "
            "                             THEN p.status ELSE 'open' END "
            "WITH p LIMIT 1 "
            "RETURN p.raw AS raw, p.freq AS freq, p.status AS status, "
            "       p.samples[..5] AS samples",
            {"raw": raw, "tt": term_type, "sample": sample or "", "batch": batch or ""})
        records = result.get("records") or []
        row = records[0] if records else {"raw": raw}
        # Cap samples at read time (PENDING_SAMPLE_CAP) — a bounded list per node
        if isinstance(row.get("samples"), list):
            row["samples"] = row["samples"][:PENDING_SAMPLE_CAP]
        return row

    def promote_pending(self, raw: str, term_type: str, canonical: str,
                        anchor_labels: Optional[List[str]] = None,
                        anchor_props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Promote a PendingTerm into a ``:Canonical`` anchor node.

        Marks the PendingTerm ``status='promoted'`` with
        ``promoted_to=canonical`` first, then creates/merges the anchor
        (labelled e.g. ``Herb``+``Canonical``) — a non-existent pending term
        leaves no orphan anchor behind. Edge re-hooking is the caller's job:
        re-running the importer (or a backfill script) through ``land()``
        will now hit level 1/2 and rebuild edges onto the anchor.
        """
        graph = self._require_graph()
        canonical = (canonical or "").strip()
        if not canonical:
            raise ValueError("promote_pending 需要 canonical 正名")
        label = _label_for_term_type(term_type)
        labels = anchor_labels or [label, "Canonical"]
        result = graph.execute_query(
            "MATCH (p:PendingTerm {raw: $raw, term_type: $tt}) "
            "SET p.status = 'promoted', p.promoted_to = $canonical, "
            "    p.resolved_at = datetime() "
            "RETURN p.raw AS raw, p.status AS status, p.promoted_to AS promoted_to",
            {"raw": raw, "tt": term_type, "canonical": canonical})
        records = result.get("records") or []
        if not records:
            return {"raw": raw, "status": "not_found"}
        graph.merge_anchor(
            labels=labels, name=canonical,
            extra_props={"term_type": term_type, **(anchor_props or {})})
        return records[0]

    def reject_pending(self, raw: str, term_type: str, reason: str = "") -> Dict[str, Any]:
        """Reject a PendingTerm (keep node + reason for audit; never delete)."""
        graph = self._require_graph()
        result = graph.execute_query(
            "MATCH (p:PendingTerm {raw: $raw, term_type: $tt}) "
            "SET p.status = 'rejected', p.reject_reason = $reason, p.resolved_at = datetime() "
            "RETURN p.raw AS raw, p.status AS status",
            {"raw": raw, "tt": term_type, "reason": reason or ""})
        records = result.get("records") or []
        return records[0] if records else {"raw": raw, "status": "not_found"}

    # ---- Alias registry (PRD-0021 R3: generalised beyond herb/symptom) ----

    def register_alias(self, term_type: str, alias: str, canonical: str) -> bool:
        """Register one in-memory alias mapping (level-1 landing source).

        Registry is generalised to every TERM_TYPES entry (previously only
        herb/symptom were populated by callers); alias == canonical or empty
        values are ignored so promote-identity never pollutes L1.
        """
        alias, canonical = (alias or "").strip(), (canonical or "").strip()
        if term_type not in TERM_TYPES or not alias or not canonical or alias == canonical:
            return False
        self.alias_map.setdefault(term_type, {})[alias] = canonical
        return True

    def load_aliases_from_graph(self, term_types: Optional[Iterable[str]] = None) -> int:
        """Hydrate the alias registry from anchor ``aliases`` properties.

        Source of truth for merged/adjudicated aliases (PRD-0021 R3): both
        normative direct landing (GB/T 别名列) and merge adjudication write
        ``aliases`` onto :Canonical anchors; importers reconstruct resolvers
        from the graph so a merged spelling hits level 1 on re-import.
        Existing entries win (setdefault semantics) — curated seed tables
        are never overwritten by graph state.
        """
        graph = self._require_graph()
        wanted = set(term_types) if term_types else set(TERM_TYPES)
        result = graph.execute_query(
            "MATCH (a:Canonical) WHERE a.aliases IS NOT NULL AND a.term_type IS NOT NULL "
            "RETURN a.term_type AS tt, a.name AS name, a.aliases AS aliases",
            {})
        registered = 0
        for row in result.get("records") or []:
            tt = row.get("tt")
            name = (row.get("name") or "").strip()
            if tt not in wanted or not name:
                continue
            bucket = self.alias_map.setdefault(tt, {})
            for alias in row.get("aliases") or []:
                alias = (alias or "").strip()
                if alias and alias != name and alias not in bucket:
                    bucket[alias] = name
                    registered += 1
        if registered:
            self.logger.info("锚点别名注册表水合：%d 条（graph → L1）", registered)
        return registered

    def merge_pending(self, raw: str, term_type: str, canonical: str) -> Dict[str, Any]:
        """Merge a PendingTerm into an existing anchor + alias write-back.

        Adjudication merge (PRD-0021 R3): flips the pending row to
        ``status='promoted', promoted_to=canonical`` *and* appends the raw
        spelling to the anchor's ``aliases`` list — unlike promote_pending
        (which creates/merges the anchor), the target anchor must already
        exist; a missing anchor aborts without flipping the pending row so
        no decision is lost. Re-running is idempotent (alias dedup + same
        terminal status).
        """
        graph = self._require_graph()
        canonical = (canonical or "").strip()
        if not canonical:
            raise ValueError("merge_pending 需要 canonical 正名")
        result = graph.execute_query(
            "MATCH (a:Canonical {name: $canonical}) "
            "MATCH (p:PendingTerm {raw: $raw, term_type: $tt}) "
            "SET p.status = 'promoted', p.promoted_to = $canonical, p.resolved_at = datetime(), "
            "    a.aliases = CASE WHEN $raw IN coalesce(a.aliases, []) OR $raw = a.name "
            "                     THEN coalesce(a.aliases, []) "
            "                     ELSE coalesce(a.aliases, []) + [$raw] END "
            "RETURN p.raw AS raw, p.status AS status, p.promoted_to AS promoted_to, "
            "       a.name AS anchor",
            {"raw": raw, "tt": term_type, "canonical": canonical})
        records = result.get("records") or []
        if not records:
            # 目标锚点不存在或 pending 行不存在：不翻状态（决策不丢失），
            # 由调用方决定是否先建锚点（promote 路径）或报告错误。
            return {"raw": raw, "status": "not_found", "canonical": canonical}
        return records[0]

    def list_pending(self, term_type: Optional[str] = None, min_freq: int = 1,
                     status: str = "open", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List pending terms (freq desc) for adjudication queue rendering.

        ``limit`` overrides the 500-row queue-rendering default (full-batch
        adjudication passes a larger cap; PRD-0021 R2 全量跑批).
        """
        graph = self._require_graph()
        where = ["p.freq >= $minFreq", "coalesce(p.status, 'open') = $status"]
        params: Dict[str, Any] = {
            "minFreq": int(min_freq), "status": status, "lim": int(limit or 500)
        }
        if term_type:
            where.append("p.term_type = $tt")
            params["tt"] = term_type
        result = graph.execute_query(
            f"MATCH (p:PendingTerm) WHERE {' AND '.join(where)} "
            "RETURN p.raw AS raw, p.term_type AS term_type, p.freq AS freq, "
            "       p.samples AS samples, p.first_seen_batch AS first_seen_batch, "
            "       p.status AS status, p.promoted_to AS promoted_to "
            "ORDER BY p.freq DESC, p.raw LIMIT $lim",
            params)
        return result.get("records") or []


def _label_for_term_type(term_type: str) -> str:
    """Map a term_type to its primary node label."""
    return {
        "herb": "Herb",
        "symptom": "Symptom",
        "syndrome": "Syndrome",
        "formula": "Formula",
        "therapy_method": "TherapyMethod",
        "disease": "Disease",
    }.get(term_type, "Term")
