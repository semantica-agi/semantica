"""Evals result data models.

Defines the metric and result shapes produced by the evals module.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, NamedTuple, Optional


@dataclass(frozen=True)
class EvalMetric:
    """One evaluator's numeric score plus pass/fail verdict."""

    score: float
    passed: bool
    meta: Dict[str, Any] = field(default_factory=dict)


class CaseResult(NamedTuple):
    """Evaluation output for a single case."""

    case_id: str
    status: str
    metrics: Dict[str, EvalMetric]
    details: Dict[str, Any]


@dataclass
class EvalSummary:
    """Aggregate evaluation output across cases."""

    total: int
    passed: int
    failed: int
    errors: int
    pass_rate: float
    cases: List[CaseResult] = field(default_factory=list)


@dataclass(frozen=True)
class SampleStats:
    """Per-evaluator statistics over repeated runs of one case.

    ``n`` is the number of runs, ``passes`` the number that passed, and the
    rest are derived views over those runs. ``samples`` keeps the raw metrics.
    ``objective_passed`` is None unless a ``direction`` objective is configured,
    in which case it gates the aggregate ``pass_rate`` with the same threshold.
    """

    n: int
    passes: int
    errors: int
    pass_rate: float
    mean_score: float
    stddev: float
    any_passed: bool
    all_passed: bool
    objective_passed: Optional[bool] = None
    samples: List[EvalMetric] = field(default_factory=list)


@dataclass(frozen=True)
class RepeatedCaseResult:
    """Per-case outcome after repeated sampling.

    ``verdict`` classifies the case across runs:
    ``stable_pass`` (all runs passed), ``flaky`` (mixed), ``stable_fail``
    (none passed), or ``error`` (a run errored). ``stats`` holds per-evaluator
    ``SampleStats``.
    """

    case_id: str
    verdict: str
    stats: Dict[str, SampleStats]


@dataclass
class RepeatedSummary:
    """Aggregate outcome across cases from repeated sampling."""

    runs: int
    stable_pass: int
    flaky: int
    stable_fail: int
    errors: int
    cases: List[RepeatedCaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)
