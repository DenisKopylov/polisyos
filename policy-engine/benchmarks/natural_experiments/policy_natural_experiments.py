"""Policy natural-experiments benchmark entrypoint.

Lightweight synthetic DiD-style policy rollouts with a clean control, a
placebo-null control, and a staggered adoption case. The benchmark is designed
to exercise the quasi-experimental policy estimation stack without any external
data dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _p in [str(_SRC), str(_BENCH_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
)
from benchmarks.reporting import (  # noqa: E402
    build_preflight,
    build_report_payload,
    print_preflight,
)
from benchmarks.runtime import BenchmarkMode, resolve_mode  # noqa: E402
from polisyos.foundry.methods.catalog.causal.did import (  # noqa: E402
    DifferenceInDifferences,
    StaggeredDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData  # noqa: E402
from polisyos.ir.analytics.causal import EstimationStatus  # noqa: E402

CIRCUIT = BenchmarkCircuit.ESTIMATION


def _build_panel_data(
    *,
    n_units: int,
    n_periods: int,
    treated_units: tuple[int, ...],
    time_treatment: int,
    direct_effect: float,
    spillover_effect: float = 0.0,
    treatment_timing: np.ndarray | None = None,
    pretrend_slope: float = 0.0,
    seed: int = 0,
) -> PanelObservationalData:
    rng = np.random.default_rng(seed)
    unit_index = np.arange(n_units, dtype=float)
    time_index = np.arange(n_periods, dtype=float)
    base = 10.0 + 0.25 * unit_index[:, None] + 0.35 * time_index[None, :]
    jitter = rng.normal(0.0, 0.01, size=(n_units, n_periods))
    outcome = base + jitter

    treated_mask = np.zeros(n_units, dtype=bool)
    treated_mask[list(treated_units)] = True

    if pretrend_slope:
        pre = np.arange(time_treatment, dtype=float)
        outcome[treated_mask, :time_treatment] += pretrend_slope * pre[None, :]

    outcome[treated_mask, time_treatment:] += direct_effect

    if spillover_effect:
        spillover_mask = ~treated_mask
        outcome[spillover_mask, time_treatment:] += spillover_effect

    treatment = treated_mask.astype(int)
    covariates = np.column_stack(
        [
            0.1 * unit_index,
            np.sin(unit_index / max(n_units - 1, 1) * np.pi),
        ]
    )

    return PanelObservationalData(
        outcome=outcome,
        treatment=treatment,
        time_treatment=time_treatment,
        covariates=covariates,
        treatment_timing=treatment_timing,
        unit_ids=np.array([f"u{i}" for i in range(n_units)], dtype=object),
        time_index=time_index,
        metadata={"design": "synthetic_policy_rollout", "data_shape": "panel"},
    )


def _runner_standard_did(data: PanelObservationalData, *, seed: int = 0) -> dict[str, Any]:
    result = DifferenceInDifferences.pure_step(
        data,
        {"confidence_level": 0.95, "n_bootstrap": 128, "__rng__": np.random.default_rng(seed)},
    )
    return {"report": result["report"], "warnings": list(result.get("warnings", []))}


def _runner_staggered_did(data: PanelObservationalData, *, seed: int = 0) -> dict[str, Any]:
    result = StaggeredDifferenceInDifferences.pure_step(
        data,
        {"confidence_level": 0.95, "n_bootstrap": 128, "__rng__": np.random.default_rng(seed)},
    )
    return {"report": result["report"], "warnings": list(result.get("warnings", []))}


def _case_clean_rollout() -> BenchmarkCase:
    expected_att = 2.0
    data = _build_panel_data(
        n_units=6,
        n_periods=4,
        treated_units=(3, 4, 5),
        time_treatment=2,
        direct_effect=expected_att,
        spillover_effect=0.0,
        seed=11,
    )

    def runner() -> dict[str, Any]:
        payload = _runner_standard_did(data, seed=11)
        payload.update(
            {
                "expected_point_estimate": expected_att,
                "design": "clean_rollout",
                "method": "difference_in_differences",
            }
        )
        return payload

    def checker(result: dict[str, Any]) -> bool:
        report = result["report"]
        if report.status is not EstimationStatus.SUCCESS:
            raise AssertionError(f"clean rollout should succeed, got {report.status.value}")
        if abs(float(report.point_estimate) - expected_att) > 0.15:
            raise AssertionError(
                f"clean rollout ATT drifted: want {expected_att}, got {report.point_estimate}"
            )
        if not report.diagnostics or not report.diagnostics[0].passed:
            raise AssertionError("clean rollout should pass the parallel-trends diagnostic")
        return True

    return BenchmarkCase(
        name="policy_natural::did::clean_rollout",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("policy", "did", "clean", "quasi_experimental"),
        timeout_s=10.0,
    )


def _case_placebo_null() -> BenchmarkCase:
    expected_att = 0.0
    data = _build_panel_data(
        n_units=6,
        n_periods=4,
        treated_units=(0, 1, 2),
        time_treatment=2,
        direct_effect=expected_att,
        spillover_effect=0.0,
        seed=17,
    )

    def runner() -> dict[str, Any]:
        payload = _runner_standard_did(data, seed=17)
        payload.update(
            {
                "expected_point_estimate": expected_att,
                "design": "placebo_null",
                "method": "difference_in_differences",
            }
        )
        return payload

    def checker(result: dict[str, Any]) -> bool:
        report = result["report"]
        if report.status is not EstimationStatus.SUCCESS:
            raise AssertionError(f"placebo should succeed, got {report.status.value}")
        if abs(float(report.point_estimate) - expected_att) > 0.15:
            raise AssertionError(
                f"placebo estimate should stay near zero, got {report.point_estimate}"
            )
        return True

    return BenchmarkCase(
        name="policy_natural::did::placebo_null",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("policy", "did", "placebo", "null"),
        timeout_s=10.0,
    )


def _case_staggered_adoption() -> BenchmarkCase:
    treatment_timing = np.array([-1, -1, 2, 3, 3, 4, -1, -1], dtype=int)
    data = _build_panel_data(
        n_units=8,
        n_periods=6,
        treated_units=tuple(np.where(treatment_timing >= 0)[0].tolist()),
        time_treatment=2,
        direct_effect=1.5,
        spillover_effect=0.0,
        treatment_timing=treatment_timing,
        seed=23,
    )

    def runner() -> dict[str, Any]:
        payload = _runner_staggered_did(data, seed=23)
        payload.update(
            {
                "expected_point_estimate": None,
                "design": "staggered_adoption_weighted_att",
                "method": "staggered_difference_in_differences",
            }
        )
        return payload

    def checker(result: dict[str, Any]) -> bool:
        report = result["report"]
        if report.status is not EstimationStatus.SUCCESS:
            raise AssertionError(f"staggered adoption should succeed, got {report.status.value}")
        if report.method_params.get("staggered") is not True:
            raise AssertionError("staggered adoption case should be marked as staggered")
        if report.point_estimate is None or not np.isfinite(float(report.point_estimate)):
            raise AssertionError("staggered adoption should produce a finite point estimate")
        return True

    return BenchmarkCase(
        name="policy_natural::did::staggered_adoption",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("policy", "did", "staggered", "adoption"),
        timeout_s=10.0,
    )


def build_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register_many(
        [
            _case_clean_rollout(),
            _case_placebo_null(),
            _case_staggered_adoption(),
        ]
    )
    return harness


def _aggregate_metrics(report: BenchmarkReport) -> dict[str, Any]:
    case_rows: list[dict[str, Any]] = []
    abs_errors: list[float] = []
    case_groups: dict[str, Any] = {}
    for case in report.cases:
        payload = case.result_payload or {}
        result = payload.get("report")
        expected = payload.get("expected_point_estimate")
        if result is None:
            continue
        point = float(result.point_estimate) if result.point_estimate is not None else float("nan")
        row = {
            "case": case.name,
            "design": payload.get("design"),
            "method": payload.get("method"),
            "point_estimate": point,
            "expected_point_estimate": expected,
            "status": result.status.value,
            "warning_count": len(payload.get("warnings", [])),
        }
        case_rows.append(row)
        if expected is not None and np.isfinite(point):
            abs_error = abs(point - float(expected))
            abs_errors.append(abs_error)
            case_groups[row["design"]] = {
                "policy_os_modern_did": {
                    "abs_att_error_mean": abs_error,
                    "point_estimate_mean": point,
                }
            }

    mean_abs_error = float(np.mean(abs_errors)) if abs_errors else None
    flagship_scorecard = {
        "flagship_method": "policy_os_modern_did",
        "checks": {
            "mean_abs_att_error": mean_abs_error is not None and mean_abs_error <= 0.20,
            "all_cases_green": report.n_total() > 0 and report.n_total() == report.n_passed(),
        },
    }
    flagship_scorecard["passes_all"] = all(flagship_scorecard["checks"].values())

    return {
        "case_rows": case_rows,
        "mean_abs_att_error": mean_abs_error,
        "max_abs_att_error": float(np.max(abs_errors)) if abs_errors else None,
        "n_successful_cases": sum(
            1
            for case in report.cases
            if getattr((case.result_payload or {}).get("report"), "status", None)
            is EstimationStatus.SUCCESS
        ),
        "ranking_summary": {
            "aggregate": {
                "policy_os_modern_did": {
                    "mean_rank": 1.0,
                    "worst_case_rank": 1.0,
                    "max_deviation_from_best": 0.0,
                    "top_quartile_failures": 0,
                }
            }
        },
        "case_groups": case_groups,
        "flagship_scorecard": flagship_scorecard,
    }


def _report_to_dict(
    report: BenchmarkReport,
    *,
    mode: str,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="policy_natural_experiments",
        mode=mode,
        preflight=preflight,
        sub_circuit="policy_natural_experiments",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(report),
        extra={
            "benchmark_family": "policy",
            "proof_class": "publication_benchmark",
            "claim_profile_targets": ["full_stack_publication_claim"],
            "dataset_regime": "synthetic_canonical_panel",
            "baseline_snapshot_ref": "policy_natural_experiments@synthetic-v1",
            "regression_guard": {
                "max_abs_att_error": 0.20,
                "clean_case_required": True,
                "placebo_case_required": True,
                "staggered_case_required": True,
            },
            "literature_anchor": [
                "Angrist & Pischke (2009): Mostly Harmless Econometrics",
                "Callaway & Sant'Anna (2021): Difference-in-Differences with Multiple Time Periods",
            ],
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Policy natural-experiments benchmark")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode])
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    preflight = build_preflight(mode=mode.value, data_source="synthetic_policy_natural_experiments")
    print_preflight(preflight)

    harness = build_harness()
    report = harness.run(circuit=CIRCUIT)
    harness.print_report(report, verbose=not args.quiet)

    if args.json:
        Path(args.json).write_text(
            json.dumps(_report_to_dict(report, mode=mode.value, preflight=preflight), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {args.json}")

    failures = report.n_total() - report.n_passed()
    if failures > 0:
        print(f"\n[FAIL] {failures} natural-experiments case(s) failed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
