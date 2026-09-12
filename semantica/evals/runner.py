"""Evaluation runner: orchestrates evaluators over a list of cases."""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .registry import get_evaluator
from .types import (
    CaseResult,
    EvalMetric,
    EvalSummary,
    RepeatedCaseResult,
    RepeatedSummary,
    SampleStats,
)

Case = Union[Dict[str, Any], Tuple[Any, Any]]


def _coerce_threshold(name, threshold):
    """Convert ``threshold`` to a finite float, raising ``ValueError`` otherwise.

    Accepts any value that ``float()`` accepts (int, float, bool, numeric
    strings) as long as the result is finite.  Raises ``ValueError`` — never
    ``TypeError`` — for non-convertible types, NaN, and infinity so that
    all invalid objective config produces the same exception type.
    """
    try:
        value = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"objective for '{name}': 'threshold' must be a finite number "
            f"(got {threshold!r})"
        ) from exc
    if not math.isfinite(value):
        raise ValueError(
            f"objective for '{name}': 'threshold' must be a finite number "
            f"(got {threshold!r})"
        )
    return value


def _parse_objective(name, eval_config):
    """Return the validated objective dict, or None when not configured.

    Raises ValueError for invalid configurations (programmer error).
    """
    objective = (eval_config or {}).get("objective")
    if objective is None:
        return None
    if not isinstance(objective, dict):
        raise ValueError(
            f"objective for '{name}': expected a dict, got {type(objective).__name__}"
        )
    direction = objective.get("direction")
    threshold = objective.get("threshold")
    expect = objective.get("expect")

    if expect is not None:
        if not isinstance(expect, bool):
            raise ValueError(
                f"objective for '{name}': 'expect' must be a bool (got {expect!r})"
            )
        if direction is not None or threshold is not None:
            raise ValueError(
                f"objective for '{name}': 'expect' cannot be combined with "
                "'direction' or 'threshold'"
            )
        return {"expect": expect}
    if direction == "minimize":
        if threshold is None:
            raise ValueError(
                f"objective for '{name}': 'minimize' requires a 'threshold'"
            )
        return {
            "direction": "minimize",
            "threshold": _coerce_threshold(name, threshold),
        }
    if direction == "maximize":
        if threshold is None:
            # no bar to re-decide against; treat as absent (evaluator default stands)
            return None
        return {
            "direction": "maximize",
            "threshold": _coerce_threshold(name, threshold),
        }
    raise ValueError(
        f"objective for '{name}': 'direction' must be 'maximize' or 'minimize' "
        f"(got {direction!r})"
    )


def _apply_objective(metric, objective):
    """Return the objective-adjusted pass verdict for a non-error metric."""
    if "expect" in objective:
        return bool(metric.score) == objective["expect"]
    if objective["direction"] == "minimize":
        return metric.score <= objective["threshold"]
    return metric.score >= objective["threshold"]


def _extract(case: Case, target_fn: Optional[Callable]):
    """Return (case_id, expected, actual, config, per_case_target_fn)."""
    if isinstance(case, tuple):
        expected, actual = case[0], (case[1] if len(case) > 1 else None)
        return str(id(case)), expected, actual, {}, None
    case_id = case.get("id") or f"case-{id(case)}"
    expected = case.get("expected")
    actual = case.get("actual")
    config = case.get("config") or {}
    per_fn = case.get("target_fn")
    return case_id, expected, actual, config, per_fn


def _merge_config(
    default_config: Dict[str, Any], case_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Deep-merge per-case config over the global config (two levels deep).

    Level 1 (top-level keys, e.g. evaluator names): merged key-by-key so a
    per-case override of one evaluator's settings does not erase the whole
    global evaluator entry.

    Level 2 (evaluator config keys, e.g. ``"objective"``): also merged
    key-by-key so a per-case override that specifies only some objective fields
    (e.g. just ``"threshold"``) inherits the rest from the global objective
    (e.g. ``"direction"``).  Per-case values always take precedence.

    Depth-3+ values are replaced wholesale, consistent with the previous
    single-level behaviour (no evaluator config currently nests beyond two
    levels).  Neither the caller's global config nor the case config is
    mutated.
    """
    merged = dict(default_config)
    for key, value in (case_config or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            # Merge level-1 dict (evaluator config) key-by-key.
            current = dict(merged[key])
            for k, v in value.items():
                if isinstance(v, dict) and isinstance(current.get(k), dict):
                    # Merge level-2 dict (e.g. objective sub-dict) key-by-key.
                    inner = dict(current[k])
                    inner.update(v)
                    current[k] = inner
                else:
                    current[k] = v
            merged[key] = current
        else:
            merged[key] = value
    return merged


def evaluate(
    cases: List[Case],
    evaluators: List[str],
    config: Optional[Dict[str, Any]] = None,
    target_fn: Optional[Callable] = None,
) -> EvalSummary:
    """Run named evaluators over each case and aggregate metrics.

    A per-case or top-level ``target_fn`` produces ``actual`` when the case
    does not already carry one. Evaluator failures become ``error`` results.
    """
    default_config = config or {}
    case_results: List[CaseResult] = []

    # Validate objective config for every case up front so an invalid objective
    # rejects the run before any target_fn or evaluator executes (fail-fast),
    # regardless of which case carries it.
    pre_resolved = []
    for case in cases:
        _, _, _, case_config, _ = _extract(case, target_fn)
        merged = _merge_config(default_config, case_config)
        pre_resolved.append(
            {
                name: _parse_objective(name, merged.get(name) or {})
                for name in evaluators
            }
        )

    for case, objective_by_name in zip(cases, pre_resolved):
        case_id, expected, actual, case_config, per_fn = _extract(case, target_fn)
        merged = _merge_config(default_config, case_config)
        if expected is None:
            expected = merged.get("expected")
        resolver = per_fn or target_fn
        if actual is None and resolver is not None:
            try:
                actual = resolver(case)
            except Exception as exc:  # noqa: BLE001
                case_results.append(
                    CaseResult(case_id, "error", {}, {"target_fn": str(exc)})
                )
                continue
        metrics: Dict[str, EvalMetric] = {}
        details: Dict[str, Any] = {}
        failed, errored = False, False
        for name in evaluators:
            eval_config = merged.get(name) or {}
            try:
                metric = get_evaluator(name)(actual, expected, config=eval_config)
                objective = objective_by_name.get(name)
                if objective is not None and "error" not in metric.meta:
                    metric = EvalMetric(
                        metric.score, _apply_objective(metric, objective), metric.meta
                    )
                metrics[name] = metric
                if "error" in metric.meta:
                    errored = True
                    details[name] = metric.meta
                elif not metric.passed:
                    failed = True
                    details[name] = metric.meta
            except Exception as exc:  # noqa: BLE001
                errored = True
                metrics[name] = EvalMetric(0.0, False, {"error": str(exc)})
                details[name] = {"error": str(exc)}
        status = "error" if errored else ("fail" if failed else "pass")
        case_results.append(CaseResult(case_id, status, metrics, details))

    total = len(case_results)
    passed = sum(1 for c in case_results if c.status == "pass")
    failed = sum(1 for c in case_results if c.status == "fail")
    errors = sum(1 for c in case_results if c.status == "error")
    pass_rate = (passed / total) if total else 1.0
    return EvalSummary(
        total,
        passed,
        failed,
        errors,
        pass_rate,
        cases=case_results,
    )


def _stddev(values: List[float]) -> float:
    """Population standard deviation over ``values`` (0.0 for <2 samples)."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def evaluate_repeated(
    cases: List[Case],
    evaluators: List[str],
    config: Optional[Dict[str, Any]] = None,
    target_fn: Optional[Callable] = None,
    runs: int = 10,
) -> RepeatedSummary:
    """Rerun ``target_fn`` per case ``runs`` times and aggregate statistics.

    Non-determinism in an evaluation lives in ``target_fn`` (an LLM call, a
    sampling-based pipeline), not in the evaluators, which are pure functions
    over a given ``actual``. So ``evaluate_repeated`` re-invokes ``target_fn``
    on each run to draw a fresh ``actual``, then scores it with the named
    evaluators. Aggregating those scores across runs surfaces distribution-level
    evidence (pass rate, mean/stddev) and a per-case verdict:

    - ``stable_pass``: every run passed every evaluator
    - ``flaky``: at least one pass and one fail across runs/evaluators
    - ``stable_fail``: no run passed any evaluator
    - ``error``: a run errored

    Verdict for a multi-evaluator case pools samples across all evaluators: it
    is ``stable_pass`` only when every sample of every evaluator passed, and
    ``flaky`` when the pool mixes passes and fails (e.g. one evaluator passing
    every run while another passes none).

    A case that carries a non-null static ``actual`` (rather than a ``target_fn``)
    has nothing to sample, so with ``runs > 1`` it raises ``ValueError``, matching
    the fail-fast style of invalid objective config. An ``actual`` of ``None`` is
    treated as absent, exactly as in ``evaluate()``: it falls back to the
    resolver. ``evaluate()`` is untouched; this is an additive entry point over
    the same helpers.
    """
    if runs < 1:
        raise ValueError(f"runs must be >= 1 (got {runs!r})")
    if not evaluators:
        raise ValueError("evaluate_repeated requires at least one evaluator")
    if len(evaluators) != len(set(evaluators)):
        raise ValueError(
            f"evaluators must be unique (got duplicates: "
            f"{sorted({n for n in evaluators if evaluators.count(n) > 1})})"
        )
    default_config = config or {}
    repeated_results: List[RepeatedCaseResult] = []

    # Validate object config and sampling prerequisites for every case up front
    # so an invalid objective or an unsamplable static ``actual`` rejects the
    # run before any target_fn or evaluator executes (fail-fast), regardless of
    # which case carries it.
    pre_resolved = []
    for case in cases:
        case_id, _, static_actual, case_config, _ = _extract(case, target_fn)
        if static_actual is not None and runs > 1:
            raise ValueError(
                f"case '{case_id}': repeated sampling requires a streaming "
                f"``target_fn``; a static ``actual`` can only be run once "
                f"(runs={runs!r})"
            )
        merged = _merge_config(default_config, case_config)
        pre_resolved.append(
            {
                name: _parse_objective(name, merged.get(name) or {})
                for name in evaluators
            }
        )

    for case, objective_by_name in zip(cases, pre_resolved):
        case_id, expected, static_actual, case_config, per_fn = _extract(
            case, target_fn
        )
        merged = _merge_config(default_config, case_config)
        if expected is None:
            expected = merged.get("expected")
        resolver = per_fn or target_fn
        has_actual = static_actual is not None

        # All samples for this case, per evaluator.
        per_eval: Dict[str, List[EvalMetric]] = {name: [] for name in evaluators}
        errored_any = False
        for _ in range(runs):
            if not has_actual and resolver is None:
                for name in evaluators:
                    per_eval[name].append(
                        EvalMetric(0.0, False, {"error": "no target_fn to sample"})
                    )
                errored_any = True
                continue
            try:
                actual = static_actual if has_actual else resolver(case)
            except Exception as exc:  # noqa: BLE001
                errored_any = True
                for name in evaluators:
                    per_eval[name].append(
                        EvalMetric(0.0, False, {"error": f"target_fn: {exc}"})
                    )
                continue
            for name in evaluators:
                eval_config = merged.get(name) or {}
                objective = objective_by_name.get(name)
                try:
                    metric = get_evaluator(name)(actual, expected, config=eval_config)
                    if objective is not None and "error" not in metric.meta:
                        metric = EvalMetric(
                            metric.score,
                            _apply_objective(metric, objective),
                            metric.meta,
                        )
                except Exception as exc:  # noqa: BLE001
                    metric = EvalMetric(0.0, False, {"error": str(exc)})
                if "error" in metric.meta:
                    errored_any = True
                per_eval[name].append(metric)

        # Aggregate per-evaluator stats.
        stats: Dict[str, SampleStats] = {}
        verdict = "error" if errored_any else None
        for name in evaluators:
            samples = per_eval[name]
            n = len(samples)
            passes = sum(1 for m in samples if m.passed and "error" not in m.meta)
            errors = sum(1 for m in samples if "error" in m.meta)
            scores = [m.score for m in samples if "error" not in m.meta]
            pass_rate = passes / n if n else 0.0
            mean_score = sum(scores) / len(scores) if scores else 0.0
            objective = objective_by_name.get(name)
            objective_passed = None
            if objective is not None and "direction" in objective:
                objective_passed = _apply_objective(
                    EvalMetric(pass_rate, True), objective
                )
            stats[name] = SampleStats(
                n=n,
                passes=passes,
                errors=errors,
                pass_rate=pass_rate,
                mean_score=mean_score,
                stddev=_stddev(scores),
                any_passed=passes > 0,
                all_passed=passes == n and n > 0 and errors == 0,
                objective_passed=objective_passed,
                samples=samples,
            )
        if verdict is None:
            # Verdict across all evaluators: flaky if any mixed, else uniform.
            passes_total = sum(stats[name].passes for name in evaluators)
            n_total = sum(stats[name].n for name in evaluators)
            if passes_total == 0:
                verdict = "stable_fail"
            elif passes_total == n_total:
                verdict = "stable_pass"
            else:
                verdict = "flaky"
        repeated_results.append(
            RepeatedCaseResult(case_id=case_id, verdict=verdict, stats=stats)
        )

    stable_pass = sum(1 for r in repeated_results if r.verdict == "stable_pass")
    flaky = sum(1 for r in repeated_results if r.verdict == "flaky")
    stable_fail = sum(1 for r in repeated_results if r.verdict == "stable_fail")
    errors = sum(1 for r in repeated_results if r.verdict == "error")
    return RepeatedSummary(
        runs=runs,
        stable_pass=stable_pass,
        flaky=flaky,
        stable_fail=stable_fail,
        errors=errors,
        cases=repeated_results,
    )
