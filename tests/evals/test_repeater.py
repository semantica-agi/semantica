"""Tests for ``evaluate_repeated`` (repeated-sampling evaluation)."""

import math

import pytest

from semantica.evals import (
    RepeatedCaseResult,
    RepeatedSummary,
    SampleStats,
    evaluate_repeated,
)
from semantica.evals.registry import EVALUATORS, register
from semantica.evals.types import EvalMetric

CALLS = {"n": 0}


@pytest.fixture
def grade_linear():
    """Register a graded evaluator for the mean/stddev test, then remove it."""

    @register("_grade_linear")
    def _grade_linear(actual, expected=None, config=None, **kwargs):
        return EvalMetric(score=float(actual), passed=float(actual) >= 0.0)

    yield _grade_linear
    EVALUATORS.pop("_grade_linear", None)


def seq(*results):
    """Return a shared-counter target_fn that yields ``results``, repeating last."""

    def _fn(_case):
        CALLS["n"] += 1
        idx = min(CALLS["n"] - 1, len(results) - 1)
        return results[idx]

    return _fn


def make_seq(*results):
    """Independent-counter target_fn yielding ``results``, repeating the last."""
    state = {"i": 0}

    def _fn(_case):
        idx = min(state["i"], len(results) - 1)
        state["i"] += 1
        return results[idx]

    return _fn


def always(actual):
    return lambda _case: actual


def _reset():
    CALLS["n"] = 0


def test_exports():
    from semantica.evals import evaluate, evaluate_repeated

    assert callable(evaluate) and callable(evaluate_repeated)


def test_stable_pass_when_all_runs_pass():
    _reset()
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        target_fn=always("ok"),
        runs=5,
    )
    assert isinstance(summary, RepeatedSummary)
    assert summary.runs == 5
    assert summary.stable_pass == 1
    assert summary.flaky == 0
    assert summary.stable_fail == 0
    result = summary.cases[0]
    assert isinstance(result, RepeatedCaseResult)
    assert result.verdict == "stable_pass"
    stat = result.stats["exact_match"]
    assert isinstance(stat, SampleStats)
    assert stat.n == 5
    assert stat.passes == 5
    assert stat.pass_rate == 1.0
    assert stat.any_passed is True
    assert stat.all_passed is True
    assert stat.stddev == 0.0


def test_flaky_detection_mixed_results():
    _reset()
    # 4 pass, 1 fail -> flaky
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        target_fn=seq("ok", "ok", "bad", "ok", "ok"),
        runs=5,
    )
    assert summary.cases[0].verdict == "flaky"
    stat = summary.cases[0].stats["exact_match"]
    assert stat.passes == 4
    assert stat.pass_rate == pytest.approx(0.8)
    assert stat.any_passed is True
    assert stat.all_passed is False
    assert summary.flaky == 1


def test_stable_fail_when_no_run_passes():
    _reset()
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        target_fn=always("bad"),
        runs=5,
    )
    assert summary.cases[0].verdict == "stable_fail"
    stat = summary.cases[0].stats["exact_match"]
    assert stat.passes == 0
    assert stat.pass_rate == 0.0
    assert stat.any_passed is False
    assert stat.all_passed is False


def test_static_actual_with_runs_gt_1_raises():
    _reset()
    with pytest.raises(ValueError, match=r"static ``actual``"):
        evaluate_repeated(
            [{"id": "c1", "expected": "ok", "actual": "ok"}],
            ["exact_match"],
            runs=3,
        )


def test_static_actual_runs_1_is_allowed():
    _reset()
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok", "actual": "ok"}],
        ["exact_match"],
        runs=1,
    )
    assert summary.cases[0].verdict == "stable_pass"
    assert summary.cases[0].stats["exact_match"].n == 1


def test_runs_zero_raises():
    _reset()
    with pytest.raises(ValueError, match="runs must be >= 1"):
        evaluate_repeated([], ["exact_match"], runs=0)


def test_target_fn_exception_becomes_error_verdict():
    _reset()

    def boom(_case):
        raise RuntimeError("boom")

    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        target_fn=boom,
        runs=5,
    )
    result = summary.cases[0]
    assert result.verdict == "error"
    assert summary.errors == 1
    # every errored sample carries the target_fn failure message
    stat = result.stats["exact_match"]
    assert stat.errors == 5
    assert all(m.meta.get("error", "").startswith("target_fn:") for m in stat.samples)


def test_error_takes_precedence_over_flaky():
    _reset()

    def sometimes_boom(case, _state={"i": 0}):
        _state["i"] += 1
        if _state["i"] == 2:
            raise RuntimeError("boom")
        return "ok"

    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        target_fn=sometimes_boom,
        runs=5,
    )
    assert summary.cases[0].verdict == "error"


def test_objective_applies_per_run():
    # objective applies per run as in evaluate(); this test pins that the
    # maximize threshold still flips the per-run verdict for exact_match
    _reset()
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        config={
            "exact_match": {"objective": {"direction": "maximize", "threshold": 0.6}}
        },
        target_fn=seq("ok", "ok", "bad", "ok", "ok"),
        runs=5,
    )
    # exact_match scores 1.0/0.0; pass_rate aggregates the per-run passes
    stat = summary.cases[0].stats["exact_match"]
    assert stat.passes == 4
    # the same objective also gates the aggregate pass_rate (0.8 >= 0.6)
    assert stat.objective_passed is True


def test_aggregate_objective_gates_pass_rate():
    # a nudge below the threshold flips objective_passed without changing the
    # distribution verdict: 3/5 passes gives pass_rate 0.6 < 0.8
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        config={
            "exact_match": {"objective": {"direction": "maximize", "threshold": 0.8}}
        },
        target_fn=make_seq("ok", "ok", "bad", "ok", "bad"),
        runs=5,
    )
    stat = summary.cases[0].stats["exact_match"]
    assert stat.passes == 3
    assert stat.pass_rate == pytest.approx(0.6)
    assert stat.objective_passed is False
    # verdict still reflects distribution, not the aggregate threshold
    assert summary.cases[0].verdict == "flaky"


def test_mean_and_stddev_reflect_scores(grade_linear):
    # _grade_linear scores mirror the numeric actual, so 1..5 -> mean 3, stddev sqrt(2)
    summary = evaluate_repeated(
        [{"id": "c1"}],
        ["_grade_linear"],
        target_fn=make_seq(1.0, 2.0, 3.0, 4.0, 5.0),
        runs=5,
    )
    stat = summary.cases[0].stats["_grade_linear"]
    assert stat.mean_score == pytest.approx(3.0)
    assert stat.stddev == pytest.approx(math.sqrt(2.0))
    assert stat.any_passed is True
    assert stat.all_passed is True


def test_multiple_cases_aggregation():
    # each case owns an independent target_fn, so verdicts are deterministic
    summary = evaluate_repeated(
        [
            {"id": "a", "expected": "ok", "target_fn": make_seq("ok", "ok", "ok")},
            {"id": "b", "expected": "ok", "target_fn": make_seq("ok", "bad", "ok")},
            {"id": "c", "expected": "ok", "target_fn": make_seq("bad", "bad", "bad")},
        ],
        ["exact_match"],
        runs=3,
    )
    assert summary.total == 3
    verdicts = {r.case_id: r.verdict for r in summary.cases}
    assert verdicts["a"] == "stable_pass"
    assert verdicts["b"] == "flaky"
    assert verdicts["c"] == "stable_fail"


def test_missing_target_fn_is_error():
    _reset()
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        runs=3,
    )
    assert summary.cases[0].verdict == "error"
    assert summary.errors == 1


def test_multi_evaluator_flaky_when_verdicts_diverge():
    # exact_match (checks "ok") passes every run; keyword_check (requires "k")
    # fails every run -> pooled across evaluators the case is flaky.
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match", "keyword_check"],
        config={"keyword_check": {"required": ["k"]}},
        target_fn=always("ok"),
        runs=4,
    )
    result = summary.cases[0]
    assert result.verdict == "flaky"
    assert result.stats["exact_match"].all_passed is True
    assert result.stats["keyword_check"].all_passed is False


def test_minimize_objective_applies_per_run():
    # exact_match scores 1.0 on a match; a minimize threshold of 0.0 flips that
    # pass to a fail -> every run fails -> stable_fail.
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        config={
            "exact_match": {"objective": {"direction": "minimize", "threshold": 0.0}}
        },
        target_fn=always("ok"),
        runs=3,
    )
    result = summary.cases[0]
    assert result.verdict == "stable_fail"
    assert result.stats["exact_match"].passes == 0
    # aggregate gate mirrors the per-run direction: pass_rate 0.0 <= 0.0
    assert result.stats["exact_match"].objective_passed is True


def test_empty_evaluators_rejected():
    with pytest.raises(ValueError, match="at least one evaluator"):
        evaluate_repeated([{"id": "c1"}], [], runs=3)


def test_duplicate_evaluators_rejected():
    with pytest.raises(ValueError, match="must be unique"):
        evaluate_repeated(
            [{"id": "c1", "expected": "ok"}],
            ["exact_match", "exact_match"],
            target_fn=always("ok"),
            runs=3,
        )


def test_missing_target_errors_all_runs():
    # no static actual and no resolver: every requested run records an error, so
    # SampleStats.n matches runs rather than stopping after the first.
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["exact_match"],
        runs=4,
    )
    result = summary.cases[0]
    assert result.verdict == "error"
    stat = result.stats["exact_match"]
    assert stat.n == 4
    assert stat.errors == 4
    assert summary.runs == 4


def test_tuple_case_form_is_rejected_for_sampling():
    # (expected, actual) tuple form always carries a static actual, so with
    # runs > 1 it is rejected up front, consistent with static-actual cases.
    with pytest.raises(ValueError, match="static ``actual``"):
        evaluate_repeated(
            [("ok", "ok")],
            ["exact_match"],
            target_fn=seq("ok", "bad", "ok"),
            runs=3,
        )


def test_unknown_evaluator_surfaces_as_error_verdict():
    # An unknown evaluator raising from get_evaluator is caught per-run and the
    # case becomes an error verdict, consistent with the single-run evaluate().
    _reset()
    summary = evaluate_repeated(
        [{"id": "c1", "expected": "ok"}],
        ["nope"],
        target_fn=always("ok"),
        runs=2,
    )
    assert summary.cases[0].verdict == "error"
    assert summary.errors == 1
    # the per-run error carries the unknown-evaluator message
    assert summary.cases[0].stats["nope"].samples[0].meta["error"]
