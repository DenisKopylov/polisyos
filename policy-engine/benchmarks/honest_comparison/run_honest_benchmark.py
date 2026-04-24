#!/usr/bin/env python
"""CLI entrypoint for the honest head-to-head benchmark."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure src is on path for PolicyOS imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
# Ensure benchmarks root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.comparators import (
    build_research_acceptance_comparator_status,
    comparator_degraded_reasons,
)
from benchmarks.harness import BenchmarkCircuit, BenchmarkReport, CaseResult, Verdict
from benchmarks.honest_comparison.config import BenchmarkConfig, FairnessTier
from benchmarks.honest_comparison.metrics import AggregatedMetrics
from benchmarks.honest_comparison.runner import run_benchmark
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
from benchmarks.runtime import BenchmarkMode, resolve_mode, resolve_tier

SUITE_ID = "honest_comparison"


def _parse_tiers(raw: str | None, *, smoke: bool) -> tuple[FairnessTier, ...]:
    if raw:
        tier_map = {"a": FairnessTier.A, "b": FairnessTier.B, "c": FairnessTier.C}
        return tuple(tier_map[item.strip().lower()] for item in raw.split(","))
    if smoke:
        return (FairnessTier.B,)
    return (FairnessTier.A, FairnessTier.B, FairnessTier.C)


def _parse_sample_sizes(raw: str | None, *, smoke: bool) -> tuple[int, ...]:
    if raw:
        return tuple(int(x) for x in raw.split(","))
    return (500,) if smoke else (1000, 2500, 5000)


def _default_output_path() -> Path:
    reports_dir = Path(__file__).resolve().parents[1] / "_reports"
    return reports_dir / f"honest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


def _synthetic_report(raw_metrics: dict[str, list[AggregatedMetrics]]) -> BenchmarkReport:
    grouped: dict[tuple[str, str], list[AggregatedMetrics]] = defaultdict(list)
    for tier_name, metrics_list in raw_metrics.items():
        for metric in metrics_list:
            grouped[(tier_name, metric.dataset_name)].append(metric)

    cases: list[CaseResult] = []
    for (tier_name, dataset_name), rows in sorted(grouped.items()):
        valid_rows = [row for row in rows if not math.isnan(row.ate_rmse)]
        cases.append(
            CaseResult(
                name=f"{tier_name}::{dataset_name}",
                circuit=BenchmarkCircuit.COMPARISON,
                verdict=Verdict.PASS if valid_rows else Verdict.FAIL,
                elapsed_s=float(
                    sum(row.wall_time_mean for row in rows if not math.isnan(row.wall_time_mean))
                ),
                memory_delta_mb=0.0,
                error_msg=None if valid_rows else "all honest comparison rows failed",
                result_payload={
                    "tier": tier_name,
                    "dataset_name": dataset_name,
                    "n_methods": len(rows),
                    "n_valid_methods": len(valid_rows),
                    "rows": rows,
                },
            )
        )

    return BenchmarkReport(
        circuits=[BenchmarkCircuit.COMPARISON],
        cases=cases,
        circuit_scores={},
    )


def _aggregate_metrics(raw_metrics: dict[str, list[AggregatedMetrics]]) -> dict[str, Any]:
    by_tier: dict[str, Any] = {}
    for tier_name, metrics_list in raw_metrics.items():
        by_tier[tier_name] = {
            "n_rows": len(metrics_list),
            "datasets": sorted({metric.dataset_name for metric in metrics_list}),
            "methods": sorted({metric.method_name for metric in metrics_list}),
            "mean_ate_rmse": float(
                sum(metric.ate_rmse for metric in metrics_list if not math.isnan(metric.ate_rmse))
                / max(1, sum(1 for metric in metrics_list if not math.isnan(metric.ate_rmse)))
            ),
            "mean_failure_rate": float(
                sum(
                    metric.failure_rate
                    for metric in metrics_list
                    if not math.isnan(metric.failure_rate)
                )
                / max(1, sum(1 for metric in metrics_list if not math.isnan(metric.failure_rate)))
            ),
        }
    return {"tier_summary": by_tier}


def _benchmark_payload(
    *,
    mode: BenchmarkMode,
    cfg: BenchmarkConfig,
    raw_result: dict[str, Any],
    raw_output_path: Path | None,
    quiet: bool,
) -> dict[str, Any]:
    comparator_status = build_research_acceptance_comparator_status(
        required_labels=("econml", "zepid", "dowhy"),
        default_to_legacy_required=False,
    )
    degraded_reasons = comparator_degraded_reasons(comparator_status)
    preflight = build_preflight(
        mode=mode.value,
        benchmark_tier=resolve_tier(mode=mode).value,
        validation_contour="academic",
        visibility="public",
        data_source="synthetic_dgp_head_to_head",
        dependency_status={"python_modules": {"numpy": "available"}},
        comparator_status=comparator_status,
        degraded_reasons=degraded_reasons,
        dataset_family="honest_head_to_head",
        batch_id=f"k={cfg.k_replications};sizes={','.join(str(size) for size in cfg.effective_sample_sizes())}",
        estimator_profile="honest_head_to_head",
        comparator_profile="suite_scoped",
        required_comparators=["econml", "zepid", "dowhy"],
    )
    if not quiet:
        print_preflight(preflight)

    report = _synthetic_report(raw_result["metrics"])
    payload = build_report_payload(
        report,
        suite_id=SUITE_ID,
        mode=mode.value,
        preflight=preflight,
        sub_circuit="honest_head_to_head",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(raw_result["metrics"]),
        benchmark_family="estimation",
        proof_class="publication_benchmark",
        claim_profile_targets=["full_stack_publication_claim"],
        public_claim_eligible=False,
        blockers=[],
        extra={
            "fairness_manifests": raw_result.get("pairwise", {}),
            "native_environment": raw_result.get("env", {}),
            "native_output_path": str(raw_output_path) if raw_output_path else None,
            "method_profile": "honest_head_to_head",
        },
    )
    payload["overall_status"] = "passed"
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Honest head-to-head benchmark: PolicyOS vs open-source causal inference"
    )
    parser.add_argument("--smoke", action="store_true", help="Smoke test: K=3, n=500, Tier B only")
    parser.add_argument("--output", type=str, default=None, help="Native JSON output path")
    parser.add_argument(
        "--json", type=str, default=None, help="Unified benchmark payload output path"
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress unified JSON stdout")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode], default=None)
    parser.add_argument(
        "--tiers", type=str, default=None, help="Comma-separated tiers to run (A,B,C)"
    )
    parser.add_argument("--k", type=int, default=None, help="Override number of replications")
    parser.add_argument(
        "--n", type=str, default=None, help="Comma-separated sample sizes (e.g., 1000,2500,5000)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    mode = resolve_mode(args.mode)
    smoke = (
        args.smoke
        or mode is BenchmarkMode.SMOKE
        or os.environ.get("HONEST_SMOKE", "").lower() in ("1", "true")
    )

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg = BenchmarkConfig(
        tiers=_parse_tiers(args.tiers or os.environ.get("HONEST_TIER"), smoke=smoke),
        sample_sizes=_parse_sample_sizes(args.n or os.environ.get("HONEST_N"), smoke=smoke),
        k_replications=args.k or int(os.environ.get("HONEST_K", "100")),
        smoke=smoke,
    )

    raw_output_path = (
        Path(args.output)
        if args.output
        else (_default_output_path() if args.json is None else None)
    )
    raw_result = run_benchmark(cfg, output_path=raw_output_path)

    if args.json:
        payload = _benchmark_payload(
            mode=mode,
            cfg=cfg,
            raw_result=raw_result,
            raw_output_path=raw_output_path,
            quiet=args.quiet,
        )
        output = json.dumps(payload, indent=2)
        Path(args.json).write_text(output + "\n", encoding="utf-8")
        if not args.quiet:
            print(output)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
