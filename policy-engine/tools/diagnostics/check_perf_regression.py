#!/usr/bin/env python3
"""
Performance regression checker for CI/CD.

Compares benchmark results between baseline (main) and current (PR) branches.
Fails if latency increases by >5% or throughput decreases by >5%.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


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
    with open(path) as f:
        data = json.load(f)

    results: dict[str, BenchmarkResult] = {}
    for bench in data.get("benchmarks", []):
        name = bench["name"]
        stats = bench["stats"]
        results[name] = BenchmarkResult(
            name=name,
            mean=stats["mean"],
            stddev=stats["stddev"],
            min=stats["min"],
            max=stats["max"],
            rounds=stats["rounds"],
        )
    return results


def compare_benchmarks(
    baseline: dict[str, BenchmarkResult],
    current: dict[str, BenchmarkResult],
    latency_threshold: float = 5.0,
    throughput_threshold: float = 5.0,
) -> list[Comparison]:
    """Compare baseline and current benchmark results."""
    comparisons: list[Comparison] = []

    for name, baseline_result in baseline.items():
        if name not in current:
            print(f"Warning: Benchmark '{name}' missing in current run", file=sys.stderr)
            continue

        current_result = current[name]

        # Calculate delta (positive = regression for latency tests)
        delta = current_result.mean - baseline_result.mean
        delta_percent = (
            (delta / baseline_result.mean) * 100 if baseline_result.mean > 0 else 0
        )

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

    return comparisons


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
                return f"{t*1e6:.1f}us"
            if t < 1:
                return f"{t*1e3:.1f}ms"
            return f"{t:.2f}s"

        delta_str = (
            f"+{comp.delta_percent:.1f}%" if comp.delta_percent > 0 else f"{comp.delta_percent:.1f}%"
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Check performance regression")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--latency-threshold", type=float, default=5.0)
    parser.add_argument("--throughput-threshold", type=float, default=5.0)
    parser.add_argument("--output-format", choices=["github", "text"], default="text")
    args = parser.parse_args()

    baseline = load_pytest_benchmark(args.baseline)
    current = load_pytest_benchmark(args.current)

    comparisons = compare_benchmarks(
        baseline,
        current,
        latency_threshold=args.latency_threshold,
        throughput_threshold=args.throughput_threshold,
    )

    if args.output_format == "github":
        report = format_github_output(comparisons)
        Path("comparison_report.md").write_text(report)
        print(report)
    else:
        for comp in comparisons:
            status = "PASS" if comp.passed else "FAIL"
            print(f"[{status}] {comp.name}: {comp.delta_percent:+.1f}%")

    # Exit with error if any benchmark failed
    if not all(c.passed for c in comparisons):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
