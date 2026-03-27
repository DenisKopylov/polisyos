"""Phase C.5 hidden temporal stress benchmark suite."""

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
    benchmark_case_from_fixture,
    build_hidden_summary,
    build_temporal_suite_backtest,
    extract_temporal_evaluations,
    temporal_case_details,
)
from benchmarks.temporal.fixtures import hidden_fixtures

SUITE_ID = "temporal_hidden"


def _build_payload(mode: str, *, quiet: bool) -> dict[str, object]:
    harness = BenchmarkHarness()
    for fixture in hidden_fixtures():
        harness.register(
            benchmark_case_from_fixture(fixture, circuit=BenchmarkCircuit.ESTIMATION)
        )

    report = harness.run(circuit=BenchmarkCircuit.ESTIMATION)
    evaluations = extract_temporal_evaluations(report)
    hidden_summary = build_hidden_summary(evaluations)
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
        proof_class="stress_evidence",
        claim_profile_targets=[
            "frontier_frontier_claim",
            "full_stack_publication_claim",
        ],
        public_claim_eligible=False,
        baseline_snapshot_ref="temporal_hidden@synthetic-v1",
        regression_guard={
            "rule": "locked_temporal_hidden_snapshot",
            "requires_all_cases_pass": True,
        },
        aggregate_metrics={
            "hidden_temporal_summary": hidden_summary,
            "accuracy": {
                "n_total": hidden_summary["n_total"],
                "n_passed": hidden_summary["n_passed"],
                "pass_rate": hidden_summary["pass_rate"],
            },
        },
        case_details_builder=lambda case: temporal_case_details(
            case,
            include_scenario_metadata=False,
        ),
        extra={
            "temporal_backtest_report": build_temporal_suite_backtest(
                report_id=f"{SUITE_ID}-{mode}",
                evaluations=evaluations,
                suite_id=SUITE_ID,
            ),
            "method_profile": "temporal_hidden_stress",
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase C.5 temporal hidden benchmark suite")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
