"""Local semantic ranking for the MCP server.

``find_precedents`` in :class:`ContextGraph` scores decisions lexically (Jaccard over words and
bigrams) plus graph structure, so a paraphrased query ("which lakehouse storage layer should the
analytics store use") misses a decision worded differently ("StarRocks native tables vs Apache
Iceberg"). This module adds dense-embedding similarity with FastEmbed, which runs locally (ONNX,
no network after the one-off model download) and is installed by the ``embeddings-local`` extra.

Everything degrades gracefully: if FastEmbed is not importable or the model cannot load, the
helpers return ``None`` and callers keep the lexical behaviour.

Environment:
    SEMANTICA_SEMANTIC_SEARCH   "false" disables embeddings (default: enabled when available)
    SEMANTICA_EMBED_MODEL       FastEmbed model name (default: BAAI/bge-small-en-v1.5)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger("semantica-mcp")

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_SKIP_TYPES = {"category", "decision_maker"}
_TEXT_KEYS = (
    "label",
    "title",
    "scenario",
    "reasoning",
    "outcome",
    "summary",
    "detail",
    "evidence",
    "points",
    "key_terms",
    "path",
    "repo",
    "url",
)

_lock = threading.Lock()
_model = None
_model_failed = False
_cache: Dict[str, Any] = {}  # sha1(text) -> unit vector (numpy)


def enabled() -> bool:
    return os.environ.get("SEMANTICA_SEMANTIC_SEARCH", "true").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _get_model():
    global _model, _model_failed
    if _model is not None or _model_failed or not enabled():
        return _model
    with _lock:
        if _model is None and not _model_failed:
            try:
                from fastembed import TextEmbedding  # type: ignore

                _model = TextEmbedding(
                    model_name=os.environ.get("SEMANTICA_EMBED_MODEL", DEFAULT_MODEL)
                )
            except (
                Exception
            ) as exc:  # missing extra, no network for first download, etc.
                _model_failed = True
                log.warning(
                    "Semantic search disabled (%s); falling back to lexical matching",
                    exc,
                )
    return _model


def _embed(texts: Sequence[str]):
    """Return unit vectors for texts (cached), or None when embeddings are unavailable."""
    model = _get_model()
    if model is None:
        return None
    import numpy as np

    keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
    missing = [(k, t) for k, t in zip(keys, texts) if k not in _cache]
    if missing:
        vecs = list(model.embed([t for _, t in missing]))
        for (k, _), v in zip(missing, vecs):
            v = np.asarray(v, dtype="float32")
            n = float(np.linalg.norm(v)) or 1.0
            _cache[k] = v / n
    return [_cache[k] for k in keys]


def similarities(query: str, texts: Sequence[str]) -> Optional[List[float]]:
    """Cosine similarity of query against each text, mapped to [0, 1]. None if unavailable."""
    if not texts:
        return []
    vecs = _embed([query, *texts])
    if vecs is None:
        return None
    q = vecs[0]
    return [max(0.0, float(q @ v)) for v in vecs[1:]]


def _flatten(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value)
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    return str(value) if value is not None else ""


def node_text(node: Dict[str, Any]) -> str:
    """Searchable text for a graph node: type, content and the descriptive metadata fields."""
    meta = node.get("metadata") or {}
    inner = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
    parts = [str(node.get("type") or ""), str(node.get("content") or "")]
    for src in (meta, inner):
        for key in _TEXT_KEYS:
            if src.get(key):
                parts.append(_flatten(src[key]))
    return " ".join(p for p in parts if p).strip()[:2000]


def decision_text(decision: Dict[str, Any]) -> str:
    return " ".join(
        str(decision.get(k) or "")
        for k in ("category", "scenario", "reasoning", "outcome")
    ).strip()


def rerank_precedents(
    scenario: str,
    precedents: List[Dict[str, Any]],
    limit: int,
    semantic_weight: float = 0.65,
) -> List[Dict[str, Any]]:
    """Blend semantic similarity into lexical/structural precedents and re-sort."""
    sims = similarities(
        scenario, [decision_text(p.get("decision") or {}) for p in precedents]
    )
    if sims is None:
        return precedents[:limit]
    for p, s in zip(precedents, sims):
        lexical = float(p.get("similarity") or 0.0)
        p["lexical_similarity"] = lexical
        p["semantic_similarity"] = round(s, 4)
        p["similarity"] = round(
            semantic_weight * s + (1 - semantic_weight) * lexical, 4
        )
    precedents.sort(key=lambda p: p["similarity"], reverse=True)
    return precedents[:limit]


def search_nodes(
    query: str,
    nodes: Iterable[Dict[str, Any]],
    node_types: Optional[Sequence[str]] = None,
    limit: int = 10,
) -> Tuple[List[Dict[str, Any]], str]:
    """Rank nodes by semantic similarity (lexical containment fallback). Returns (hits, method)."""
    wanted = {t for t in (node_types or []) if t}
    pool = [
        n
        for n in nodes
        if n.get("type") not in _SKIP_TYPES
        and (not wanted or n.get("type") in wanted)
        and (n.get("metadata") or {}).get("status") != "archived"
    ]
    texts = [node_text(n) for n in pool]
    sims = similarities(query, texts)
    method = "semantic"
    if sims is None:
        method = "lexical"
        words = {w for w in query.lower().split() if len(w) > 2}
        sims = [len(words & set(t.lower().split())) / (len(words) or 1) for t in texts]
    ranked = sorted(zip(pool, texts, sims), key=lambda x: x[2], reverse=True)[
        : max(0, limit)
    ]
    hits = []
    for n, text, score in ranked:
        meta = n.get("metadata") or {}
        hits.append(
            {
                "id": n.get("id"),
                "type": n.get("type"),
                "score": round(score, 4),
                "label": meta.get("label") or n.get("content"),
                "text": text[:400],
            }
        )
    return hits, method


def describe() -> Dict[str, Any]:
    model = _get_model()
    return {
        "semantic": model is not None,
        "model": (
            os.environ.get("SEMANTICA_EMBED_MODEL", DEFAULT_MODEL)
            if model is not None
            else None
        ),
    }


if (
    __name__ == "__main__"
):  # quick manual check: python -m semantica.mcp_server.semantic "query" text...
    import sys

    print(json.dumps(similarities(sys.argv[1], sys.argv[2:]), indent=1))
