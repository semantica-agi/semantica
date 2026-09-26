"""Optional content screening before GraphBuilder text extraction.

Scanners accept a string and return an iterable of ``ScreeningFinding`` objects.
Register additional backends with ``method_registry.register("screen", name,
scanner)``. The built-in baseline is deliberately small: findings are heuristic
signals for review, not proof of an attack or a guarantee that text is safe.
This module neither changes text nor executes instructions found in it.
"""

import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Tuple

from .registry import method_registry


@dataclass(frozen=True)
class ScreeningFinding:
    """A detection with a rule ID, severity and half-open character span.

    ``span`` uses Python string offsets into the exact input, not byte offsets.
    Text excerpts are intentionally omitted so reports need not copy secrets.
    """

    id: str
    severity: str
    span: Tuple[int, int]

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-compatible annotation."""
        return {"id": self.id, "severity": self.severity, "span": list(self.span)}


Scanner = Callable[[str], Iterable[ScreeningFinding]]

_PATTERNS = (
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|forget)\s+(?:(?:all|the)\s+)?"
            r"(?:previous|prior|above|system)\s+instructions?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credential_disclosure",
        re.compile(
            r"\b(?:send|reveal|disclose|exfiltrate|upload)\b"
            r"[^\n.!?]{0,80}?\b(?:credentials?|passwords?|api[ _-]?keys?|"
            r"access[ _-]?tokens?|private[ _-]?keys?)\b",
            re.IGNORECASE,
        ),
    ),
)


def baseline_scan(text: str) -> List[ScreeningFinding]:
    """Flag common English overrides, disclosure requests and hidden payloads.

    Ordinary HTML comments are not flagged. A comment is reported only when
    it contains one of the baseline instruction patterns. Quoted examples and
    negated instructions may still match; no claim of malicious intent is made.
    """
    findings = [
        ScreeningFinding(rule_id, "high", match.span())
        for rule_id, pattern in _PATTERNS
        for match in pattern.finditer(text)
    ]
    # Advance past each comment once. A non-greedy regex can repeatedly scan
    # the remaining document for every unmatched opening delimiter.
    cursor = 0
    while True:
        start = text.find("<!--", cursor)
        if start < 0:
            break
        end = text.find("-->", start + 4)
        if end < 0:
            break
        cursor = end + 3
        if any(pattern.search(text, start, cursor) for _, pattern in _PATTERNS):
            findings.append(
                ScreeningFinding("hidden_html_instruction", "high", (start, cursor))
            )
    return sorted(findings, key=lambda finding: (*finding.span, finding.id))


def get_scanner(method: str) -> Scanner:
    """Resolve a registered scanner, or the dependency-free baseline.

    Configuration errors are explicit; they must not silently disable an
    intended scanner. Runtime scanner failures are handled by the caller.
    """
    if not isinstance(method, str) or not method:
        raise ValueError("screening_method must be a non-empty string")
    scanner = method_registry.get("screen", method)
    if scanner is None and method == "baseline":
        scanner = baseline_scan
    if not callable(scanner):
        raise ValueError(f"Unknown or non-callable screening method: {method!r}")
    return scanner


def validate_findings(
    findings: Iterable[ScreeningFinding], text: str
) -> List[ScreeningFinding]:
    """Validate backend output before logging or publishing annotations."""
    result = list(findings)
    for finding in result:
        if not isinstance(finding, ScreeningFinding):
            raise TypeError("Scanners must return ScreeningFinding objects")
        if not isinstance(finding.id, str) or not finding.id:
            raise ValueError("Finding IDs must be non-empty strings")
        if finding.severity not in ("info", "low", "medium", "high", "critical"):
            raise ValueError("Invalid finding severity")
        if (
            not isinstance(finding.span, tuple)
            or len(finding.span) != 2
            or any(type(offset) is not int for offset in finding.span)
            or not 0 <= finding.span[0] < finding.span[1] <= len(text)
        ):
            raise ValueError("Finding span must be within the input text")
    return result
