"""Data model for the open benchmark harness.

A benchmark run is ``datasets x systems``. This module defines the small,
dependency-free types that flow through it:

- :class:`BenchmarkCase` / :class:`Dataset` — the evaluation inputs, normalized
  to a single shape regardless of which upstream dataset they came from.
- :class:`Prediction` / :class:`SystemResult` / :class:`BenchmarkReport` — the
  outputs, aggregated per (system, dataset) pair.

Keeping the case shape fixed is what lets one harness drive HotPotQA, MuSiQue
and LoCoMo the same way, and score every system with the same evaluators.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Dataset scopes -----------------------------------------------------------------
# ``per_case``: each question ships its own evidence bundle; memory is reset
# between cases (SQuAD-style reading comprehension, HotPotQA, MuSiQue).
# ``corpus``: one long-lived context is ingested once and every question queries
# the shared memory (long-conversation suites, LoCoMo).
PER_CASE = "per_case"
CORPUS = "corpus"
SCOPES = (PER_CASE, CORPUS)


@dataclass(frozen=True)
class BenchmarkCase:
    """One question plus everything needed to answer and score it."""

    case_id: str
    question: str
    answers: List[str]
    context: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.answers:
            raise ValueError(f"case {self.case_id!r} has no gold answers")


@dataclass(frozen=True)
class Dataset:
    """A named, licensed collection of cases at a fixed scope.

    ``group_by`` names an optional :attr:`BenchmarkCase.metadata` key that splits
    a ``corpus`` dataset into **independent** memories. LoCoMo sets it to
    ``"sample_id"`` because each sample is a separate conversation: without it the
    runner would merge every conversation into one blob and let one sample's
    evidence leak into another's answers. Left empty, a corpus dataset is a single
    shared memory (the whole thing is ingested once).
    """

    name: str
    license: str
    scope: str
    cases: List[BenchmarkCase]
    version: str = ""
    source: str = ""
    notes: str = ""
    group_by: str = ""

    def __post_init__(self):
        if self.scope not in SCOPES:
            raise ValueError(f"unknown scope {self.scope!r}; expected one of {SCOPES}")

    def __len__(self) -> int:
        return len(self.cases)

    def limit(self, n: Optional[int]) -> "Dataset":
        """Return a copy truncated to the first ``n`` cases (``None`` = all)."""
        if n is None or n >= len(self.cases):
            return self
        return Dataset(
            name=self.name,
            license=self.license,
            scope=self.scope,
            cases=list(self.cases[:n]),
            version=self.version,
            source=self.source,
            notes=self.notes,
            group_by=self.group_by,
        )


@dataclass
class Prediction:
    """A system's answer to one case, with timing and retrieved evidence."""

    case_id: str
    answer: str
    retrieved: List[str] = field(default_factory=list)
    latency_s: float = 0.0
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "answer": self.answer,
            "retrieved": list(self.retrieved),
            "latency_s": round(self.latency_s, 6),
            "error": self.error,
        }


@dataclass
class SystemResult:
    """Scored outcome of one (system, dataset) pair."""

    system: str
    dataset: str
    n: int
    mean_score: float
    exact_match_rate: float
    errors: int
    wall_s: float
    primary_metric: str
    summary: Any = None  # semantica.evals EvalSummary
    predictions: List[Prediction] = field(default_factory=list)

    def as_dict(self, include_predictions: bool = False) -> Dict[str, Any]:
        out = {
            "system": self.system,
            "dataset": self.dataset,
            "n": self.n,
            "primary_metric": self.primary_metric,
            "mean_score": round(self.mean_score, 6),
            "exact_match_rate": round(self.exact_match_rate, 6),
            "errors": self.errors,
            "wall_s": round(self.wall_s, 3),
        }
        if include_predictions:
            out["predictions"] = [p.as_dict() for p in self.predictions]
        return out


@dataclass
class BenchmarkReport:
    """A full run: every (system, dataset) cell plus the run metadata."""

    created_at: str
    primary_metric: str
    datasets: List[str] = field(default_factory=list)
    systems: List[str] = field(default_factory=list)
    results: List[SystemResult] = field(default_factory=list)
    scores: Dict[str, Any] = field(default_factory=dict)
    skipped: List[Dict[str, str]] = field(default_factory=list)

    def as_dict(self, include_predictions: bool = False) -> Dict[str, Any]:
        return {
            "created_at": self.created_at,
            "primary_metric": self.primary_metric,
            "datasets": list(self.datasets),
            "systems": list(self.systems),
            "results": [r.as_dict(include_predictions) for r in self.results],
            "skipped": list(self.skipped),
        }

    def to_markdown_table(self) -> str:
        """Render a system x dataset matrix of the primary metric.

        Cells are mean scores; systems that were not run on a dataset render as
        an em dash so the table can be pasted into a README unchanged.
        """
        header = ["system"] + list(self.datasets)
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * len(header)) + " |",
        ]
        for system in self.systems:
            row = [system]
            for dataset in self.datasets:
                cell = next(
                    (
                        r
                        for r in self.results
                        if r.system == system and r.dataset == dataset
                    ),
                    None,
                )
                row.append(f"{cell.mean_score:.4f}" if cell else "—")
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)
