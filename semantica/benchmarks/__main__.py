"""Command line entry point: ``python -m semantica.benchmarks``.

    list                       show the registered datasets and systems
    run --dataset D --system S run and print a system x dataset table

Datasets that ship no data (``hotpotqa``, ``musique``, ``locomo``) take their
file via ``--data NAME=PATH``. Nothing is downloaded.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from ..evals import list_evaluators
from .datasets import list_datasets, load_dataset
from .runner import run_benchmark
from .systems import list_systems
from .types import BenchmarkReport

# Datasets whose loader needs a local file, and the licence we must surface.
_FILE_DATASETS = {
    "hotpotqa": "CC BY-SA 4.0",
    "musique": "CC BY 4.0",
    "locomo": "CC BY-NC 4.0 (NON-COMMERCIAL)",
}


def _cmd_list(_args) -> int:
    print("datasets:")
    for name in list_datasets():
        licence = _FILE_DATASETS.get(name, "bundled / in-repo")
        print(f"  {name:<12} {licence}")
    print("systems:")
    for name in list_systems():
        print(f"  {name}")
    return 0


def _parse_data(pairs: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--data expects NAME=PATH, got {pair!r}")
        name, path = pair.split("=", 1)
        out[name.strip()] = path.strip()
    return out


def _load(specs: List[str], data: Dict[str, str], limit):
    datasets = []
    for name in specs:
        options = {}
        if name in _FILE_DATASETS:
            if name not in data:
                raise SystemExit(
                    f"--dataset {name} needs --data {name}=/path/to/file "
                    f"(licence: {_FILE_DATASETS[name]}; the file is not bundled)"
                )
            options["path"] = data[name]
        if limit is not None:
            options["limit"] = limit
        datasets.append(load_dataset(name, **options))
    return datasets


def _cmd_run(args) -> int:
    if args.metric not in list_evaluators():
        # A typo'd --metric used to average silently to 0.0; surface it instead.
        raise SystemExit(
            f"unknown --metric {args.metric!r}; registered evaluators: "
            f"{', '.join(list_evaluators())}"
        )
    if args.system in (["all"],):
        systems = list_systems()
    else:
        systems = args.system
    datasets = _load(args.dataset, _parse_data(args.data), args.limit)

    for dataset in datasets:
        scope = dataset.scope
        licence = dataset.license
        print(
            f"# {dataset.name}: {len(dataset)} cases, "
            f"scope={scope}, licence={licence}"
        )

    def progress(system, dataset, done, total):
        if args.quiet:
            return
        sys.stderr.write(f"\r  {system} on {dataset}: {done}/{total}")
        sys.stderr.flush()
        if done == total:
            sys.stderr.write("\n")

    report = run_benchmark(
        datasets,
        systems,
        primary_metric=args.metric,
        on_error="raise" if args.strict else "skip",
        progress=None if args.quiet else progress,
    )

    print()
    print(f"primary metric: {report.primary_metric}")
    print(report.to_markdown_table())
    if report.skipped:
        print("\nskipped (backend unavailable):")
        for entry in report.skipped:
            print(f"  {entry['system']} / {entry['dataset']}: {entry['reason']}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(report.as_dict(include_predictions=args.predictions), indent=2),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")
    if args.markdown:
        Path(args.markdown).write_text(
            _markdown(report), encoding="utf-8"
        )
        print(f"wrote {args.markdown}")
    return 0


def _markdown(report: BenchmarkReport) -> str:
    lines = [
        "# semantica benchmark report",
        "",
        f"- created: {report.created_at}",
        f"- primary metric: `{report.primary_metric}`",
        "",
        report.to_markdown_table(),
        "",
    ]
    if report.skipped:
        lines += ["## Skipped", ""]
        lines += [
            f"- `{e['system']}` on `{e['dataset']}`: {e['reason']}"
            for e in report.skipped
        ]
        lines.append("")
    lines += [
        "## Per system x dataset",
        "",
        "| system | dataset | n | mean | exact match | errors | wall (s) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in report.results:
        lines.append(
            f"| {result.system} | {result.dataset} | {result.n} | "
            f"{result.mean_score:.4f} | {result.exact_match_rate:.4f} | "
            f"{result.errors} | {result.wall_s:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m semantica.benchmarks",
        description=(
            "Run memory systems over QA benchmarks and score them with "
            "semantica.evals."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show registered datasets and systems")

    run = sub.add_parser("run", help="run benchmarks and print a table")
    run.add_argument(
        "--dataset",
        action="append",
        required=True,
        help=(
            "dataset name; repeat for several "
            "(e.g. --dataset sample --dataset musique)"
        ),
    )
    run.add_argument(
        "--system",
        action="append",
        required=True,
        help="system name, or 'all' for every registered system",
    )
    run.add_argument(
        "--data",
        action="append",
        default=[],
        help="NAME=PATH for datasets that are not bundled (hotpotqa, musique, locomo)",
    )
    run.add_argument("--limit", type=int, default=None, help="cap cases per dataset")
    run.add_argument(
        "--metric",
        default="token_f1",
        help="primary evaluator from semantica.evals (default: token_f1)",
    )
    run.add_argument("--json", default=None, help="write the full report as JSON")
    run.add_argument("--markdown", default=None, help="write the report as Markdown")
    run.add_argument(
        "--predictions",
        action="store_true",
        help="include per-case predictions in the JSON output",
    )
    run.add_argument("--quiet", action="store_true", help="suppress progress output")
    run.add_argument(
        "--strict",
        action="store_true",
        help="fail instead of skipping a system whose backend is unavailable",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list":
        return _cmd_list(args)
    return _cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
