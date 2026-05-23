from __future__ import annotations

from collections.abc import Mapping
from typing import Any

EFFECTIVENESS_REPORT_SCHEMA = {
    "type": "object",
    "required": ("timestamp", "mode", "command", "exit_code", "summary"),
    "properties": {
        "timestamp": {"type": "string"},
        "mode": {"type": "string", "enum": ("offline", "optional", "real_llm", "all")},
        "command": {"type": "array", "items_type": "string"},
        "exit_code": {"type": "integer"},
        "summary": {
            "type": "object",
            "required": ("passed", "failed", "skipped", "deselected", "errors"),
            "properties": {
                "passed": {"type": "integer"},
                "failed": {"type": "integer"},
                "skipped": {"type": "integer"},
                "deselected": {"type": "integer"},
                "errors": {"type": "integer"},
            },
        },
    },
}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_effectiveness_report(report: Mapping[str, Any]) -> None:
    """Validate the runner-level effectiveness artifact.

    Raises:
        ValueError: if the report does not match the expected artifact shape.
        TypeError: if report is not mapping-like.
    """
    if not isinstance(report, Mapping):
        raise TypeError("effectiveness report must be a mapping")

    schema = EFFECTIVENESS_REPORT_SCHEMA
    errors: list[str] = []

    for field in schema["required"]:
        if field not in report:
            errors.append(f"missing required field: {field}")

    timestamp = report.get("timestamp")
    if "timestamp" in report and not isinstance(timestamp, str):
        errors.append("timestamp must be a string")

    mode = report.get("mode")
    if "mode" in report:
        allowed_modes = schema["properties"]["mode"]["enum"]
        if not isinstance(mode, str):
            errors.append("mode must be a string")
        elif mode not in allowed_modes:
            errors.append(
                "mode must be one of " + ", ".join(repr(item) for item in allowed_modes)
            )

    command = report.get("command")
    if "command" in report:
        if not _is_str_list(command):
            errors.append("command must be a list of strings")

    exit_code = report.get("exit_code")
    if "exit_code" in report and not _is_int(exit_code):
        errors.append("exit_code must be an integer")

    summary = report.get("summary")
    summary_schema = schema["properties"]["summary"]
    if "summary" in report:
        if not isinstance(summary, Mapping):
            errors.append("summary must be an object")
        else:
            for field in summary_schema["required"]:
                if field not in summary:
                    errors.append(f"summary missing required field: {field}")
            for field, field_schema in summary_schema["properties"].items():
                if field in summary and not _is_int(summary[field]):
                    errors.append(f"summary.{field} must be an integer")

    if errors:
        raise ValueError("; ".join(errors))
