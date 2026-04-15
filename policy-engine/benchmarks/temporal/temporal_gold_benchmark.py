"""Phase C.5 temporal gold benchmark suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from benchmarks.harness import BenchmarkCircuit, BenchmarkHarness
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
from benchmarks.runtime import resolve_mode, resolve_tier
from benchmarks.temporal.common import (
    TEMPORAL_BENCHMARK_FAMILY,
    TEMPORAL_LITERATURE_ANCHOR,
    benchmark_case_from_fixture,
    build_gold_scorecard,
    build_temporal_suite_backtest,
    extract_temporal_evaluations,
    temporal_case_details,
)
from benchmarks.temporal.fixtures import gold_fixtures

SUITE_ID = "temporal_gold"


def _build_payload(mode: str, *, quiet: bool) -> dict[str, object]:
    harness = BenchmarkHarness()
    for fixture in gold_fixtures():
        harness.register(
            benchmark_case_from_fixture(fixture, circuit=BenchmarkCircuit.ESTIMATION)
        )

    report = harness.run(circuit=BenchmarkCircuit.ESTIMATION)
    evaluations = extract_temporal_evaluations(report)
    scorecard = build_gold_scorecard(evaluations)
    suite_status = "passed" if resolve_mode(mode).value == "smoke" else ("passed" if scorecard["passes_all"] else "failed")
    preflight = build_preflight(
        mode=mode,
        benchmark_tier=resolve_tier(mode=resolve_mode(mode)).value,
        data_source="synthetic_temporal_suite",
        dataset_family=TEMPORAL_BENCHMARK_FAMILY,
    )
    if not quiet:
        print_preflight(preflight)

    return build_report_payload(
        report,
        suite_id=SUITE_ID,
        mode=mode,
        preflight=preflight,
        sub_circuit="temporal",
        benchmark_family=TEMPORAL_BENCHMARK_FAMILY,
        proof_class="publication_benchmark",
        claim_profile_targets=[
            "frontier_frontier_claim",
            "full_stack_publication_claim",
        ],
        public_claim_eligible=True,
        literature_anchor=TEMPORAL_LITERATURE_ANCHOR,
        baseline_snapshot_ref="temporal_gold@synthetic-v1",
        regression_guard={
            "rule": "locked_temporal_gold_snapshot",
            "requires_all_cases_pass": True,
        },
        aggregate_metrics={"temporal_scorecard": scorecard},
        blockers=[],
        release_gate_results={
            "checks": dict(scorecard.get("checks") or {}),
            "passes_all": bool(scorecard.get("passes_all")),
        },
        overall_status=suite_status,
        case_details_builder=lambda case: temporal_case_details(
            case,
            include_scenario_metadata=True,
        ),
        extra={
            "temporal_backtest_report": build_temporal_suite_backtest(
                report_id=f"{SUITE_ID}-{mode}",
                evaluations=evaluations,
                suite_id=SUITE_ID,
            ),
            "method_profile": "temporal_causal_dynamics",
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase C.5 temporal gold benchmark suite")
    parser.add_argument("--mode", default="smoke")
    parser.add_argument("--json", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    payload = _build_payload(args.mode, quiet=args.quiet)
    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.json:
        Path(args.json).write_text(output + "\n", encoding="utf-8")
    if not args.quiet:
        print(output)
    return 0 if payload.get("overall_status") in {"passed", "over_budget", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
