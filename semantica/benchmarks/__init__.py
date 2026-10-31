"""Open benchmark harness: run memory systems over QA datasets, fairly.

Phase 1 delivers the plumbing, not the leaderboard: one case shape, one system
protocol, one scorer — so that adding a dataset or a backend is a small, local
change and every number in a report came from the same code path.

Typical use::

    from semantica.benchmarks import load_dataset, run_benchmark

    report = run_benchmark(
        [load_dataset("sample")],
        ["lexical", "semantica"],
    )
    print(report.to_markdown_table())

From the shell::

    python -m semantica.benchmarks list
    python -m semantica.benchmarks run --dataset sample --system lexical

Scoring reuses :mod:`semantica.evals` (``token_f1`` by default, plus
``normalized_exact_match`` as a secondary column), so the harness has no metric
code of its own to drift out of sync.
"""

from .datasets import list_datasets, load_dataset, register_dataset
from .runner import run_benchmark, run_from_spec, run_system
from .systems import (
    MemorySystem,
    SystemUnavailable,
    get_system,
    list_systems,
    register_system,
)
from .types import (
    CORPUS,
    PER_CASE,
    BenchmarkCase,
    BenchmarkReport,
    Dataset,
    Prediction,
    SystemResult,
)

__all__ = [
    "BenchmarkCase",
    "BenchmarkReport",
    "CORPUS",
    "Dataset",
    "MemorySystem",
    "PER_CASE",
    "Prediction",
    "SystemResult",
    "SystemUnavailable",
    "get_system",
    "list_datasets",
    "list_systems",
    "load_dataset",
    "register_dataset",
    "register_system",
    "run_benchmark",
    "run_from_spec",
    "run_system",
]
