#!/usr/bin/env python3
"""
Performance regression checker for CI/CD.

Compares benchmark results between baseline (main) and current (PR) branches.
Fails if latency increases by >5% or throughput decreases by >5%.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__, include_src_root=False)


@dataclass
class BenchmarkResult:
    """Single benchmark measurement."""

    name: str
    mean: float
    stddev: float
    min: float
    max: float
    rounds: int


@dataclass
class Comparison:
    """Comparison between baseline and current benchmark."""

    name: str
    baseline_mean: float
    current_mean: float
    delta_percent: float
    passed: bool
    threshold: float


def load_pytest_benchmark(path: Path) -> dict[str, BenchmarkResult]:
    """Load pytest-benchmark JSON output."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid pytest-benchmark JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"pytest-benchmark payload must be a JSON object: {path}")
    benchmarks = data.get("benchmarks", [])
    if not isinstance(benchmarks, list):
        raise ValueError(f"pytest-benchmark payload 'benchmarks' must be a list: {path}")

    results: dict[str, BenchmarkResult] = {}
    for index, bench in enumerate(benchmarks):
        if not isinstance(bench, dict) or not isinstance(bench.get("stats"), dict):
            raise ValueError(f"benchmark entry {index} in {path} must contain a stats object")
        name = str(bench.get("name") or "")
        if not name:
            raise ValueError(f"benchmark entry {index} in {path} is missing name")
        stats = bench["stats"]
        required = ("mean", "stddev", "min", "max", "rounds")
        missing = [key for key in required if key not in stats]
        if missing:
            raise ValueError(f"benchmark {name!r} in {path} is missing stats: {', '.join(missing)}")
        mean = float(stats["mean"])
        stddev = float(stats["stddev"])
        min_value = float(stats["min"])
        max_value = float(stats["max"])
        rounds = int(stats["rounds"])
        if not all(math.isfinite(value) for value in (mean, stddev, min_value, max_value)):
            raise ValueError(f"benchmark {name!r} in {path} has non-finite timing stats")
        if rounds < 0:
            raise ValueError(f"benchmark {name!r} in {path} has invalid rounds")
        results[name] = BenchmarkResult(
            name=name,
            mean=mean,
            stddev=stddev,
            min=min_value,
            max=max_value,
            rounds=rounds,
        )
    return results


def compare_benchmarks(
    baseline: dict[str, BenchmarkResult],
    current: dict[str, BenchmarkResult],
    latency_threshold: float = 5.0,
    throughput_threshold: float = 5.0,
) -> tuple[list[Comparison], list[str]]:
    """Compare baseline and current benchmark results."""
    comparisons: list[Comparison] = []
    warnings: list[str] = []

    for name, baseline_result in baseline.items():
        if name not in current:
            warnings.append(f"Benchmark '{name}' missing in current run")
            continue

        current_result = current[name]

        # Calculate delta (positive = regression for latency tests)
        delta = current_result.mean - baseline_result.mean
        delta_percent = (delta / baseline_result.mean) * 100 if baseline_result.mean > 0 else 0

        # Determine threshold based on test type
        if "throughput" in name.lower() or "steps_per_second" in name.lower():
            # For throughput, regression is when current < baseline
            threshold = -throughput_threshold  # Negative because decrease is bad
            passed = delta_percent >= threshold
        else:
            # For latency/overhead, regression is when current > baseline
            threshold = latency_threshold
            passed = delta_percent <= threshold

        comparisons.append(
            Comparison(
                name=name,
                baseline_mean=baseline_result.mean,
                current_mean=current_result.mean,
                delta_percent=delta_percent,
                passed=passed,
                threshold=threshold,
            )
        )

    return comparisons, warnings


def format_github_output(comparisons: list[Comparison]) -> str:
    """Format comparison results for GitHub PR comment."""
    lines = [
        "## Performance Regression Report",
        "",
        "| Benchmark | Baseline | Current | Delta | Status |",
        "|-----------|----------|---------|-------|--------|",
    ]

    all_passed = True
    for comp in comparisons:
        status = "PASS" if comp.passed else "FAIL"
        if not comp.passed:
            all_passed = False

        # Format times nicely
        def fmt_time(t: float) -> str:
            if t < 0.001:
                return f"{t * 1e6:.1f}us"
            if t < 1:
                return f"{t * 1e3:.1f}ms"
            return f"{t:.2f}s"

        delta_str = (
            f"+{comp.delta_percent:.1f}%"
            if comp.delta_percent > 0
            else f"{comp.delta_percent:.1f}%"
        )

        lines.append(
            f"| {comp.name} | {fmt_time(comp.baseline_mean)} | "
            f"{fmt_time(comp.current_mean)} | {delta_str} | {status} |"
        )

    lines.append("")
    if all_passed:
        lines.append("### All benchmarks within acceptable thresholds")
    else:
        lines.append("### Performance regression detected!")
        lines.append("")
        lines.append("Please investigate the failing benchmarks before merging.")

    return "\n".join(lines)


def _comparison_messages(
    comparisons: list[Comparison], warnings: list[str]
) -> tuple[ToolMessage, ...]:
    messages: list[ToolMessage] = []
    for warning in warnings:
        messages.append(ToolMessage(level="warning", message=warning, rule_id="PERF_MISSING"))
    for comp in comparisons:
        status = "error" if not comp.passed else "info"
        benchmark_type = "throughput" if comp.threshold < 0 else "latency"
        messages.append(
            ToolMessage(
                level=status,
                message=(
                    f"{comp.name}: delta={comp.delta_percent:+.1f}% "
                    f"(threshold={comp.threshold:+.1f}%, type={benchmark_type})"
                ),
                rule_id="PERF_REGRESSION" if not comp.passed else "PERF_OBSERVED",
            )
        )
    return tuple(messages)


def _comparison_payload(
    comparisons: list[Comparison],
    warnings: list[str],
    *,
    latency_threshold: float,
    throughput_threshold: float,
) -> dict[str, object]:
    return {
        "latency_threshold": latency_threshold,
        "throughput_threshold": throughput_threshold,
        "warnings": warnings,
        "comparisons": [
            {
                "name": comp.name,
                "baseline_mean": comp.baseline_mean,
                "current_mean": comp.current_mean,
                "delta_percent": comp.delta_percent,
                "passed": comp.passed,
                "threshold": comp.threshold,
            }
            for comp in comparisons
        ],
    }


def _structured_result(
    comparisons: list[Comparison],
    warnings: list[str],
    *,
    latency_threshold: float,
    throughput_threshold: float,
) -> ToolResult:
    payload = _comparison_payload(
        comparisons,
        warnings,
        latency_threshold=latency_threshold,
        throughput_threshold=throughput_threshold,
    )
    if not comparisons:
        return ToolResult(
            tool="diagnostics.check-perf-regression",
            status="skipped",
            summary="No comparable benchmarks found",
            exit_code=0,
            messages=(
                ToolMessage(
                    level="skipped",
                    message="No overlapping benchmark names were found",
                    rule_id="PERF_SKIPPED",
                ),
            )
            + tuple(
                ToolMessage(level="warning", message=warning, rule_id="PERF_MISSING")
                for warning in warnings
            ),
            data=payload,
        )

    failures = [comp for comp in comparisons if not comp.passed]
    status = "failed" if failures else "ok"
    summary = (
        "Performance regression detected"
        if failures
        else "All benchmarks within acceptable thresholds"
    )
    return ToolResult(
        tool="diagnostics.check-perf-regression",
        status=status,
        summary=summary,
        exit_code=1 if failures else 0,
        messages=_comparison_messages(comparisons, warnings),
        data=payload,
    )


def _text_output(comparisons: list[Comparison], warnings: list[str]) -> str:
    lines = [f"[WARN] {warning}" for warning in warnings]
    if not comparisons:
        lines.append("[SKIPPED] No comparable benchmarks found")
        return "\n".join(lines) + "\n"
    for comp in comparisons:
        status = "PASS" if comp.passed else "FAIL"
        lines.append(f"[{status}] {comp.name}: {comp.delta_percent:+.1f}%")
    return "\n".join(lines) + "\n"


def _emit(content: str, *, output: Path | None) -> None:
    if output is not None:
        atomic_write_text(output, content if content.endswith("\n") else content + "\n")
        return
    sys.stdout.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check performance regression")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--latency-threshold", type=float, default=5.0)
    parser.add_argument("--throughput-threshold", type=float, default=5.0)
    parser.add_argument(
        "--output-format", choices=["github", "text", "json", "junit"], default="text"
    )
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)
    if args.latency_threshold < 0 or not math.isfinite(args.latency_threshold):
        print("--latency-threshold must be a finite non-negative number", file=sys.stderr)
        return 2
    if args.throughput_threshold < 0 or not math.isfinite(args.throughput_threshold):
        print("--throughput-threshold must be a finite non-negative number", file=sys.stderr)
        return 2

    try:
        baseline = load_pytest_benchmark(args.baseline)
        current = load_pytest_benchmark(args.current)
    except ValueError as exc:
        result = ToolResult.failed(
            "diagnostics.check-perf-regression",
            str(exc),
            exit_code=2,
        )
        structured_format = (
            args.output_format if args.output_format in {"json", "junit"} else "text"
        )
        _emit(format_tool_result(result, output_format=structured_format), output=args.output)
        return 2

    comparisons, warnings = compare_benchmarks(
        baseline,
        current,
        latency_threshold=args.latency_threshold,
        throughput_threshold=args.throughput_threshold,
    )

    if args.output_format == "github":
        report = format_github_output(comparisons)
        target = args.output or Path("comparison_report.md")
        atomic_write_text(target, report + "\n")
        print(report)
        return 1 if any(not c.passed for c in comparisons) else 0

    if args.output_format == "text":
        _emit(_text_output(comparisons, warnings), output=args.output)
    else:
        result = _structured_result(
            comparisons,
            warnings,
            latency_threshold=args.latency_threshold,
            throughput_threshold=args.throughput_threshold,
        )
        _emit(format_tool_result(result, output_format=args.output_format), output=args.output)

    # Exit with error if any benchmark failed
    if comparisons and not all(c.passed for c in comparisons):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
