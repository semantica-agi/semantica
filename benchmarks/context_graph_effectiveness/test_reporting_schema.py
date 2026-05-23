from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.context_graph_effectiveness.report_schema import validate_effectiveness_report


FIXTURE_PATH = Path(__file__).parent / ".." / "results" / "effectiveness_offline.json"


def _load_fixture_report() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_current_effectiveness_offline_report_validates():
    validate_effectiveness_report(_load_fixture_report())


def test_minimal_valid_effectiveness_report_validates():
    report = {
        "timestamp": "2026-04-04T13:37:18.641331",
        "mode": "offline",
        "command": ["python", "-m", "pytest"],
        "exit_code": 0,
        "summary": {
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "deselected": 0,
            "errors": 0,
        },
    }
    validate_effectiveness_report(report)


@pytest.mark.parametrize(
    "mutator, expected_message",
    [
        (lambda report: report.pop("summary"), "missing required field: summary"),
        (lambda report: report.__setitem__("mode", "invalid"), "mode must be one of"),
        (lambda report: report.__setitem__("command", "pytest"), "command must be a list of strings"),
        (lambda report: report.__setitem__("exit_code", "0"), "exit_code must be an integer"),
    ],
)
def test_malformed_effectiveness_report_fails(mutator, expected_message):
    report = _load_fixture_report()
    mutator(report)

    with pytest.raises(ValueError, match=expected_message):
        validate_effectiveness_report(report)
