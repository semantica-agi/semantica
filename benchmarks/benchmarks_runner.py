import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.context_graph_effectiveness.report_schema import (
    validate_effectiveness_report,
)


def _effectiveness_marker_expr(mode: str) -> str:
    if mode == "offline":
        return "not real_llm and not effectiveness_optional"
    if mode == "optional":
        return "effectiveness_optional and not real_llm"
    if mode == "real_llm":
        return "real_llm"
    if mode == "all":
        return ""
    raise ValueError(f"Unsupported effectiveness mode: {mode}")


def _parse_pytest_summary(output: str) -> dict[str, int]:
    summary = {"passed": 0, "failed": 0, "skipped": 0, "deselected": 0, "errors": 0}
    for key in summary:
        match = re.search(rf"(\d+)\s+{key}", output)
        if match:
            summary[key] = int(match.group(1))
    return summary


def run_effectiveness_suite(
    strict: bool = False,
    mode: str = "offline",
    report_json: str | None = None,
) -> int:
    """
    Run the Context Graph Effectiveness benchmark suite (pytest-based, no
    pytest-benchmark fixture).  Uses pytest directly — does NOT use
    --benchmark-only which would skip these tests entirely.

    Args:
        strict: If True, exit(1) on any threshold failure.
        mode: Which marker subset to run.
        report_json: Optional output path for machine-readable summary.

    Returns:
        pytest exit code (0 = all passed/skipped, non-zero = failures).
    """
    print("\n" + "=" * 60)
    print("  Context Graph Effectiveness Suite")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "pytest",
        "benchmarks/context_graph_effectiveness/",
        "-p", "no:typeguard",
        "-p", "no:langsmith",
        "-v", "--tb=short",
        "--no-header",
    ]
    marker_expr = _effectiveness_marker_expr(mode)
    if marker_expr:
        cmd.extend(["-m", marker_expr])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")

    if report_json:
        report_dir = os.path.dirname(report_json)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "command": cmd,
            "exit_code": result.returncode,
            "summary": _parse_pytest_summary(f"{result.stdout}\n{result.stderr}"),
        }
        validate_effectiveness_report(report)
        with open(report_json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    if result.returncode != 0:
        print("\n[EFFECTIVENESS] One or more effectiveness tests FAILED.")
        if strict:
            sys.exit(result.returncode)
    else:
        print("\n[EFFECTIVENESS] All effectiveness tests PASSED.")
    return result.returncode


def run_benchmarks():
    """
    Master Runner for Semantica Benchmarks.
    """
    parser = argparse.ArgumentParser(description="Run Semantica Benchmarks")
    parser.add_argument(
        "--strict", action="store_true", help="Fail script if performance regresses"
    )
    parser.add_argument(
        "--effectiveness", action="store_true",
        help="Run the Context Graph Effectiveness suite (pytest-based metrics)"
    )
    parser.add_argument(
        "--effectiveness-mode",
        choices=["offline", "optional", "real_llm", "all"],
        default="offline",
        help="Select which effectiveness subset to run",
    )
    parser.add_argument(
        "--effectiveness-report-json",
        default=None,
        help="Optional path for machine-readable effectiveness summary JSON",
    )
    args = parser.parse_args()

    # Run effectiveness suite first if requested
    if args.effectiveness:
        run_effectiveness_suite(
            strict=args.strict,
            mode=args.effectiveness_mode,
            report_json=args.effectiveness_report_json,
        )
        return

    print("Starting Semantica Benchmark Suite...")

    timestamp = datetime.now().strftime("%Y%m%d_%H_%M_%S")
    os.makedirs("benchmarks/results", exist_ok=True)

    current_json = f"benchmarks/results/run_{timestamp}.json"
    baseline_json = "benchmarks/results/baseline.json"

    # Run Benchmarks
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "benchmarks/",
        "-p",
        "no:typeguard",
        "-p",
        "no:langsmith",
        "--benchmark-only",
        f"--benchmark-json={current_json}",
        "--benchmark-columns=min,mean,stddev,ops",
        "--benchmark-sort=mean",
    ]

    print(f"Executing benchmarks... (saving to {current_json})")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("Benchmarks failed to execute (runtime errors).")
        sys.exit(result.returncode)

    print("Benchmarks completed execution.")

    # Compare against Baseline
    if os.path.exists(baseline_json):
        print(f"Comparing against Baseline ({baseline_json})...")

        if os.path.exists("benchmarks/infrastructure/compare.py"):
            compare_cmd = [
                sys.executable,
                "benchmarks/infrastructure/compare.py",
                baseline_json,
                current_json,
            ]

            compare_result = subprocess.run(compare_cmd)

            if compare_result.returncode != 0:
                print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                print("   PERFORMANCE REGRESSION DETECTED")
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
                if args.strict:
                    sys.exit(1)
            else:
                print("Performance is within acceptable limits.")
        else:
            print(
                "Comparison script not found (benchmarks/infrastructure/compare.py). Skipping comparison."
            )
    else:
        print("No baseline found. This run effectively sets the new baseline.")

    print(f"\n[Action] To update baseline: cp {current_json} {baseline_json}")


if __name__ == "__main__":
    run_benchmarks()
