"""Semantica Evals — evaluation layer for decision intelligence outputs.

Provides a small library of deterministic and model-backed evaluators plus a
runner for measuring decision records, audit trails, and reasoning output.
Also home to page-aggregated IR metrics (recall@k / nDCG@k / citation hit
rate) for document corpora; additional evaluation harnesses may land here
over time.
"""

from . import decision_evaluators  # noqa: F401 (registers decision_scores)
from . import evaluators  # noqa: F401 (registers the generic evaluators)
from .ir_metrics import (
    citation_hit_rate,
    derive_chunk_truth,
    mean,
    ndcg_at_k,
    pages_of_retrieved,
    recall_at_k,
)
from .registry import get_evaluator, list_evaluators
from .runner import evaluate, evaluate_repeated
from .types import (
    CaseResult,
    EvalMetric,
    EvalSummary,
    RepeatedCaseResult,
    RepeatedSummary,
    SampleStats,
)

__version__ = "0.1.1"
__status__ = "stable"
__all__ = [
    "evaluate",
    "evaluate_repeated",
    "get_evaluator",
    "list_evaluators",
    "CaseResult",
    "EvalMetric",
    "EvalSummary",
    "RepeatedCaseResult",
    "RepeatedSummary",
    "SampleStats",
    "citation_hit_rate",
    "derive_chunk_truth",
    "mean",
    "ndcg_at_k",
    "pages_of_retrieved",
    "recall_at_k",
]
