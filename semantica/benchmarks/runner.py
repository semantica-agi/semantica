"""The benchmark driver: ``datasets x systems``, scored by ``semantica.evals``.

Two scopes, defined by the dataset (see :mod:`semantica.benchmarks.types`):

``per_case``
    Each case ships its own evidence. The system is reset and fed only that
    case's passages before it answers — SQuAD-style reading comprehension.

``corpus``
    The union of every case's passages is ingested once and every question then
    queries the same long-lived memory — the setting a *memory* benchmark
    (LoCoMo) actually cares about. When the dataset carries a ``group_by`` key,
    each group is ingested into its *own* memory and answered separately, so a
    multi-conversation suite is never flattened into one shared blob.

Scoring is deliberately not reimplemented here. Predictions are handed to
:func:`semantica.evals.evaluate`, so the harness and the repo's evaluator
library can never drift apart.
"""

import statistics
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..evals import evaluate, list_evaluators
from .datasets import load_dataset
from .systems import SystemUnavailable, get_system
from .types import (
    CORPUS,
    PER_CASE,
    BenchmarkCase,
    BenchmarkReport,
    Dataset,
    Prediction,
    SystemResult,
)

EXACT_MATCH = "normalized_exact_match"


def _check_metric(metric: str) -> None:
    """Fail fast on a typo'd metric instead of silently averaging to zero.

    A misspelled ``--metric`` used to be invisible: every case simply reported
    no score for that name and the run averaged to ``0.0``. Validating against
    the evaluator registry turns a silent wrong answer into a clear error.
    """
    available = list_evaluators()
    if metric not in available:
        raise ValueError(
            f"unknown primary_metric {metric!r}; registered evaluators: "
            f"{', '.join(available)}"
        )


def _case_texts(cases: Sequence[BenchmarkCase]) -> List[str]:
    """Order-preserving union of the given cases' passages."""
    return list(dict.fromkeys(str(p) for case in cases for p in case.context))


def _group_cases(dataset: Dataset) -> List[Tuple[str, List[BenchmarkCase]]]:
    """Split ``dataset`` into the independent memories the runner must keep apart.

    Without ``group_by`` the whole dataset is one group (a single shared memory,
    the historical ``corpus`` behaviour). With it — LoCoMo's ``sample_id`` — the
    cases of each distinct key become their own group, so every conversation gets
    a private memory and cannot retrieve another conversation's evidence.
    """
    if not dataset.group_by:
        return [(dataset.name, list(dataset.cases))]

    groups: Dict[str, List[BenchmarkCase]] = {}
    for case in dataset.cases:
        key = str(case.metadata.get(dataset.group_by, dataset.name))
        groups.setdefault(key, []).append(case)
    return list(groups.items())


def _prepare(system, texts: Sequence[str], case_id: str) -> Optional[str]:
    """Reset ``system`` and ingest ``texts``; return an error string, or ``None``.

    The memory set-up is wrapped exactly like ``answer`` is: a backend that
    raises while loading its memory is recorded as an errored case rather than
    aborting the whole run. ``texts`` is ingested only when non-empty, so a case
    with no evidence simply leaves the system freshly reset.
    """
    try:
        system.reset()
        if texts:
            system.ingest(list(texts), case_id=case_id)
    except Exception as exc:  # noqa: BLE001 - memory prep must not kill the run
        return f"{type(exc).__name__}: {exc}"
    return None


def run_system(
    system_name: str,
    dataset: Dataset,
    *,
    primary_metric: str = "token_f1",
    system_options: Optional[Dict[str, Any]] = None,
    progress=None,
) -> SystemResult:
    """Run one system over one dataset and score the predictions.

    A system that raises while answering is recorded as a prediction with an
    ``error`` rather than aborting the run: one flaky question should not throw
    away the other 199, and the error count is reported next to the score.
    """
    _check_metric(primary_metric)
    system = get_system(system_name, **(system_options or {}))
    predictions: List[Prediction] = []
    total = len(dataset.cases)
    done = 0

    started = time.perf_counter()
    for group_label, group_cases in _group_cases(dataset):
        # Corpus scope: one long-lived memory per group, ingested once up front.
        # Per-case scope: memory is reset and refilled for every question below.
        group_error = None
        if dataset.scope == CORPUS:
            group_error = _prepare(system, _case_texts(group_cases), group_label)

        for case in group_cases:
            if dataset.scope == PER_CASE:
                case_error = _prepare(system, case.context, case.case_id)
            else:
                case_error = group_error

            case_started = time.perf_counter()
            answer, error = "", case_error
            if error is None:
                try:
                    answer = system.answer(case.question, case_id=case.case_id)
                except Exception as exc:  # noqa: BLE001
                    # One bad question must not throw away the whole run.
                    error = f"{type(exc).__name__}: {exc}"
            predictions.append(
                Prediction(
                    case_id=case.case_id,
                    answer=answer if error is None else "",
                    retrieved=list(getattr(system, "last_retrieved", None) or []),
                    latency_s=time.perf_counter() - case_started,
                    error=error,
                )
            )
            done += 1
            if progress is not None:
                progress(system_name, dataset.name, done, total)
    wall_s = time.perf_counter() - started

    by_id = {case.case_id: case for case in dataset.cases}
    eval_cases = [
        {
            "id": prediction.case_id,
            "expected": by_id[prediction.case_id].answers,
            "actual": prediction.answer,
        }
        for prediction in predictions
    ]
    evaluators = list(dict.fromkeys([primary_metric, EXACT_MATCH]))
    summary = evaluate(eval_cases, evaluators)

    scores = [
        result.metrics[primary_metric].score
        for result in summary.cases
        if primary_metric in result.metrics
    ]
    exact = [
        result.metrics[EXACT_MATCH].score
        for result in summary.cases
        if EXACT_MATCH in result.metrics
    ]

    return SystemResult(
        system=system_name,
        dataset=dataset.name,
        n=len(predictions),
        mean_score=statistics.fmean(scores) if scores else 0.0,
        exact_match_rate=statistics.fmean(exact) if exact else 0.0,
        errors=sum(1 for prediction in predictions if prediction.error),
        wall_s=wall_s,
        primary_metric=primary_metric,
        summary=summary,
        predictions=predictions,
    )


def run_benchmark(
    datasets: Sequence[Dataset],
    systems: Sequence[str],
    *,
    primary_metric: str = "token_f1",
    system_options: Optional[Dict[str, Any]] = None,
    on_error: str = "skip",
    progress=None,
) -> BenchmarkReport:
    """Run every (system, dataset) pair and return one report.

    ``on_error`` controls what happens when a system cannot start (missing SDK
    or credential). ``"skip"`` records it in :attr:`BenchmarkReport.skipped` and
    continues, which is what you want for a laptop run where only one of the
    three hosted backends is configured; ``"raise"`` propagates the error.
    """
    if on_error not in {"skip", "raise"}:
        raise ValueError(f"on_error must be 'skip' or 'raise', got {on_error!r}")

    report = BenchmarkReport(
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        primary_metric=primary_metric,
        datasets=[dataset.name for dataset in datasets],
        systems=list(systems),
    )

    for system_name in systems:
        for dataset in datasets:
            try:
                result = run_system(
                    system_name,
                    dataset,
                    primary_metric=primary_metric,
                    system_options=(system_options or {}).get(system_name),
                    progress=progress,
                )
            except SystemUnavailable as exc:
                if on_error == "raise":
                    raise
                report.skipped.append(
                    {"system": system_name, "dataset": dataset.name, "reason": str(exc)}
                )
                continue
            report.results.append(result)
            report.scores[f"{system_name}/{dataset.name}"] = result.mean_score

    return report


def run_from_spec(
    dataset_specs: Sequence[Dict[str, Any]],
    systems: Sequence[str],
    **kwargs: Any,
) -> BenchmarkReport:
    """Convenience wrapper: load datasets from ``{"name": ..., **options}`` specs."""
    datasets = [
        load_dataset(spec["name"], **{k: v for k, v in spec.items() if k != "name"})
        for spec in dataset_specs
    ]
    return run_benchmark(datasets, systems, **kwargs)
