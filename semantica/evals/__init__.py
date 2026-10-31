"""Semantica Evals — evaluation layer for decision intelligence outputs.

Provides a small library of deterministic and model-backed evaluators plus a
runner for measuring decision records, audit trails, and reasoning output.
"""

from . import decision_evaluators  # noqa: F401 (registers decision_scores)
from . import evaluators  # noqa: F401 (registers the generic evaluators)
from . import qa_evaluators  # noqa: F401 (registers token_f1, normalized_exact_match)
from .qa_evaluators import normalize_answer
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

__version__ = "0.1.0"
__all__ = [
    "evaluate",
    "evaluate_repeated",
    "get_evaluator",
    "list_evaluators",
    "normalize_answer",
    "CaseResult",
    "EvalMetric",
    "EvalSummary",
    "RepeatedCaseResult",
    "RepeatedSummary",
    "SampleStats",
]
