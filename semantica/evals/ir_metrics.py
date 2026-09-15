"""
IR Metrics Module (page-aggregated)

Pure-function retrieval evaluation metrics for document corpora where the
relevance unit is a *page* (book/document title + page number) rather than an
individual chunk. Ground truth is annotated at page level; chunk-level truth
is derived automatically by joining page truth with the chunk table.

Metric family:
    - recall_at_k:  page-aggregated recall (top-k hit pages / truth pages)
    - ndcg_at_k:   page-aggregated nDCG with binary relevance
    - citation_hit_rate: share of cited pages that fall in the truth set

All functions are side-effect free and dependency free (stdlib only), so they
can run in offline evaluation harnesses without model or store access.

Conventions:
    - A "page" is a (book, page) tuple; ``book`` is coerced to str, ``page``
      to int.
    - Retrieval results are dicts with at least ``id``, ``book`` and ``page``
      keys (Milvus metadata or a relational chunk-table projection).
    - Empty truth yields 0.0 and is meant to be excluded from averages by the
      caller (the bundled ``mean`` helper already skips nothing — filter first).

Example Usage:
    >>> from semantica.evals.ir_metrics import recall_at_k
    >>> retrieved = [{"id": "c1", "book": "atlas", "page": 12},
    ...              {"id": "c2", "book": "atlas", "page": 57}]
    >>> recall_at_k(retrieved, [("atlas", 12)], k=14)
    1.0

Author: Semantica Contributors
License: MIT
"""

from __future__ import annotations

import math
from typing import Dict, List, Set, Tuple

__all__ = [
    "derive_chunk_truth",
    "pages_of_retrieved",
    "recall_at_k",
    "ndcg_at_k",
    "citation_hit_rate",
    "mean",
]


def derive_chunk_truth(expected_pages: List[Tuple[str, int]],
                       chunks: List[Dict]) -> Set[str]:
    """Derive chunk-level ground truth from page-level truth.

    Args:
        expected_pages: annotated truth pages as (book, page) tuples
            (multiple pages allowed).
        chunks: chunk projection ``[{"id", "book", "page"}, ...]``.

    Returns:
        Set of chunk ids whose (book, page) falls in the truth set. Page-level
        annotation never requires chunk-level labeling — this join is the only
        place the derivation happens.
    """
    truth = {(str(b), int(p)) for b, p in expected_pages}
    return {c["id"] for c in chunks
            if (str(c.get("book", "")), int(c.get("page", 0))) in truth}


def pages_of_retrieved(retrieved: List[Dict]) -> List[Tuple[str, int]]:
    """Map an ordered retrieval result to its ordered, deduplicated page list.

    The ranking unit for nDCG is the page: consecutive chunks from the same
    page collapse to a single page occurrence at its first-seen position.
    """
    seen: List[Tuple[str, int]] = []
    for r in retrieved:
        pg = (str(r.get("book", "")), int(r.get("page", 0)))
        if pg not in seen:
            seen.append(pg)
    return seen


def recall_at_k(retrieved: List[Dict], expected_pages: List[Tuple[str, int]],
                k: int = 14) -> float:
    """Page-aggregated recall@k: hit pages in top-k / truth pages.

    Empty truth returns 0.0; callers should exclude such queries from
    averaged reports (0.0 is a sentinel, not a measurement).
    """
    if not expected_pages:
        return 0.0
    truth = {(str(b), int(p)) for b, p in expected_pages}
    hit = {(str(r.get("book", "")), int(r.get("page", 0))) for r in retrieved[:k]}
    return len(truth & hit) / len(truth)


def ndcg_at_k(retrieved: List[Dict], expected_pages: List[Tuple[str, int]],
              k: int = 14) -> float:
    """Page-aggregated nDCG@k with binary relevance (truth page hit = 1).

    Pages are the ranking unit; discounting follows the position of the page
    in the deduplicated page sequence, not the raw chunk rank.
    """
    if not expected_pages:
        return 0.0
    truth = {(str(b), int(p)) for b, p in expected_pages}
    pages = pages_of_retrieved(retrieved[:k])
    dcg = sum(1.0 / math.log2(i + 2)
              for i, pg in enumerate(pages) if pg in truth)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(truth), k)))
    return dcg / ideal if ideal > 0 else 0.0


def citation_hit_rate(cited_pages: List[Tuple[str, int]],
                      expected_pages: List[Tuple[str, int]]) -> float:
    """Share of cited pages that fall in the truth set (no citations -> 0).

    Measures whether a downstream consumer (e.g. an LLM composing an
    evidence-cited answer) actually cites the annotated ground-truth pages.
    """
    if not cited_pages:
        return 0.0
    truth = {(str(b), int(p)) for b, p in expected_pages}
    hit = sum(1 for b, p in cited_pages if (str(b), int(p)) in truth)
    return hit / len(cited_pages)


def mean(values: List[float]) -> float:
    """Arithmetic mean; empty list -> 0.0 (evaluation reports average only
    over queries with non-empty truth, so 0.0 never pollutes aggregates when
    callers filter first)."""
    return sum(values) / len(values) if values else 0.0
