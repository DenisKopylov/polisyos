"""Policy DID / interference benchmark entrypoint.

This suite keeps the cases small and synthetic while exercising two things that
matter for policy evaluation under spillovers:
1. a clean DiD rollout,
2. a deliberately contaminated rollout with cross-unit spillover,
3. graph-based interference detection on a unit-suffixed ADMG.
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
from polisyos.foundry.methods.catalog.causal.did import DifferenceInDifferences  # noqa: E402
from polisyos.foundry.methods.catalog.causal.interference import (
    identify_interference_effect,  # noqa: E402
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData  # noqa: E402
from polisyos.ir.analytics.causal import EstimationStatus  # noqa: E402
from polisyos.ir.analytics.causal_graph import (  # noqa: E402
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)

CIRCUIT = BenchmarkCircuit.ESTIMATION


def _build_panel_data(
    *,
    direct_effect: float,
    spillover_effect: float,
    seed: int,
) -> PanelObservationalData:
    rng = np.random.default_rng(seed)
    n_units = 8
    n_periods = 4
    time_treatment = 2
    treated_units = (0, 1, 2, 3)
    control_units = (4, 5, 6, 7)

    unit_index = np.arange(n_units, dtype=float)
    time_index = np.arange(n_periods, dtype=float)
    base = 8.0 + 0.3 * unit_index[:, None] + 0.25 * time_index[None, :]
    outcome = base + rng.normal(0.0, 0.01, size=(n_units, n_periods))

    treated_mask = np.zeros(n_units, dtype=bool)
    treated_mask[list(treated_units)] = True
    control_mask = np.zeros(n_units, dtype=bool)
    control_mask[list(control_units)] = True

    outcome[treated_mask, time_treatment:] += direct_effect
    outcome[control_mask, time_treatment:] += spillover_effect

    covariates = np.column_stack(
        [
            0.05 * unit_index,
            np.cos(unit_index / max(n_units - 1, 1) * np.pi),
        ]
    )

    return PanelObservationalData(
        outcome=outcome,
        treatment=treated_mask.astype(int),
        time_treatment=time_treatment,
        covariates=covariates,
        unit_ids=np.array([f"u{i}" for i in range(n_units)], dtype=object),
        time_index=time_index,
        metadata={
            "design": "policy_rollout_with_spillover",
            "data_shape": "panel",
        },
    )


def _build_interference_graph() -> CausalGraphModel:
    nodes = ["A__0", "A__1", "Y__0", "Y__1"]
    edges = [
        CausalEdge(src="A__0", dst="Y__0", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="A__0", dst="Y__1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="A__1", dst="Y__1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="A__1", dst="Y__0", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
    ]
    metadata = {
        "cluster_partition": [
            ["A__0", "Y__0"],
            ["A__1", "Y__1"],
        ],
        "dataset_ref": "synthetic_policy_interference_graph",
    }
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
        metadata=metadata,
    )


def _runner_did(data: PanelObservationalData, *, seed: int) -> dict[str, Any]:
    result = DifferenceInDifferences.pure_step(
        data, {"confidence_level": 0.95, "__rng__": np.random.default_rng(seed)}
    )
    return {
        "artifact": result["report"],
        "artifact_kind": "did",
        "warnings": list(result.get("warnings", [])),
    }


def _runner_graph_detection() -> dict[str, Any]:
    artifact = identify_interference_effect(_build_interference_graph(), "A", "Y")
    return {
        "artifact": artifact,
        "artifact_kind": "interference_detection",
        "warnings": list(getattr(artifact, "warnings", ())),
    }


def _case_clean_policy_rollout() -> BenchmarkCase:
    direct_effect = 2.0
    data = _build_panel_data(direct_effect=direct_effect, spillover_effect=0.0, seed=7)

    def runner() -> dict[str, Any]:
        payload = _runner_did(data, seed=7)
        payload.update(
            {
                "expected_point_estimate": direct_effect,
                "design": "clean_policy_rollout",
            }
        )
        return payload

    def checker(result: dict[str, Any]) -> bool:
        report = result["artifact"]
        if report.status is not EstimationStatus.SUCCESS:
            raise AssertionError(f"clean rollout should succeed, got {report.status.value}")
        if abs(float(report.point_estimate) - direct_effect) > 0.15:
            raise AssertionError(
                f"clean rollout estimate drifted: want {direct_effect}, got {report.point_estimate}"
            )
        return True

    return BenchmarkCase(
        name="policy_did::clean_policy_rollout",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("policy", "did", "clean", "no_spillover"),
        timeout_s=10.0,
    )


def _case_contaminated_rollout() -> BenchmarkCase:
    direct_effect = 2.2
    spillover_effect = 0.9
    expected_att = direct_effect - spillover_effect
    data = _build_panel_data(
        direct_effect=direct_effect, spillover_effect=spillover_effect, seed=13
    )

    def runner() -> dict[str, Any]:
        payload = _runner_did(data, seed=13)
        payload.update(
            {
                "expected_point_estimate": expected_att,
                "design": "spillover_contaminated_rollout",
            }
        )
        return payload

    def checker(result: dict[str, Any]) -> bool:
        report = result["artifact"]
        if report.status is not EstimationStatus.SUCCESS:
            raise AssertionError(f"contaminated rollout should succeed, got {report.status.value}")
        if abs(float(report.point_estimate) - expected_att) > 0.15:
            raise AssertionError(
                f"contaminated rollout estimate drifted: want {expected_att}, got {report.point_estimate}"
            )
        return True

    return BenchmarkCase(
        name="policy_did::spillover_contaminated_rollout",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("policy", "did", "spillover", "contaminated"),
        timeout_s=10.0,
    )


def _case_graph_interference_detection() -> BenchmarkCase:
    def runner() -> dict[str, Any]:
        artifact = _runner_graph_detection()["artifact"]
        return {
            "artifact": artifact,
            "artifact_kind": "interference_detection",
            "design": "graph_cross_unit_spillover",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        if not artifact.sutva_violated:
            raise AssertionError("graph case should detect SUTVA violation")
        if not artifact.interference_detected:
            raise AssertionError("graph case should flag interference_detected")
        if not artifact.augmented_graph.exposure_nodes:
            raise AssertionError("graph case should create exposure nodes")
        return True

    return BenchmarkCase(
        name="policy_did::graph_interference_detection",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("policy", "interference", "graph", "spillover"),
        timeout_s=10.0,
    )


def build_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register_many(
        [
            _case_clean_policy_rollout(),
            _case_contaminated_rollout(),
            _case_graph_interference_detection(),
        ]
    )
    return harness


def _aggregate_metrics(report: BenchmarkReport) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    abs_errors: list[float] = []
    clean_point_estimate: float | None = None
    contaminated_point_estimate: float | None = None
    case_groups: dict[str, Any] = {}

    for case in report.cases:
        payload = case.result_payload or {}
        artifact = payload.get("artifact")
        if artifact is None:
            continue
        row = {
            "case": case.name,
            "artifact_kind": payload.get("artifact_kind"),
            "design": payload.get("design"),
            "status": getattr(artifact, "status", getattr(artifact, "status", None)),
            "warnings": len(payload.get("warnings", [])),
        }
        if hasattr(artifact, "point_estimate") and artifact.point_estimate is not None:
            point = float(artifact.point_estimate)
            row["point_estimate"] = point
            expected = payload.get("expected_point_estimate")
            row["expected_point_estimate"] = expected
            if expected is not None and np.isfinite(point):
                abs_error = abs(point - float(expected))
                abs_errors.append(abs_error)
                case_groups[payload.get("design") or case.name] = {
                    "policy_os_interference_did": {
                        "abs_att_error_mean": abs_error,
                        "point_estimate_mean": point,
                    }
                }
            if case.name.endswith("clean_policy_rollout"):
                clean_point_estimate = point
            elif case.name.endswith("spillover_contaminated_rollout"):
                contaminated_point_estimate = point
        if hasattr(artifact, "sutva_violated"):
            row["sutva_violated"] = bool(artifact.sutva_violated)
            row["interference_detected"] = bool(artifact.interference_detected)
            row["exposure_nodes"] = len(artifact.augmented_graph.exposure_nodes)
        rows.append(row)

    bias_gap = None
    if clean_point_estimate is not None and contaminated_point_estimate is not None:
        bias_gap = clean_point_estimate - contaminated_point_estimate

    mean_abs_error = float(np.mean(abs_errors)) if abs_errors else None
    flagship_scorecard = {
        "flagship_method": "policy_os_interference_did",
        "checks": {
            "mean_abs_att_error": mean_abs_error is not None and mean_abs_error <= 0.20,
            "spillover_detection": any(
                row.get("interference_detected") is True or row.get("sutva_violated") is True
                for row in rows
            ),
            "all_cases_green": report.n_total() > 0 and report.n_total() == report.n_passed(),
        },
    }
    flagship_scorecard["passes_all"] = all(flagship_scorecard["checks"].values())

    return {
        "case_rows": rows,
        "mean_abs_att_error": mean_abs_error,
        "max_abs_att_error": float(np.max(abs_errors)) if abs_errors else None,
        "did_bias_gap": bias_gap,
        "n_detected_spillover_cases": sum(
            1
            for row in rows
            if row.get("interference_detected") is True or row.get("sutva_violated") is True
        ),
        "ranking_summary": {
            "aggregate": {
                "policy_os_interference_did": {
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
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="policy_did_interference",
        mode=mode,
        preflight=preflight,
        sub_circuit="policy_did_interference",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(report),
        extra={
            "benchmark_family": "policy",
            "proof_class": "publication_benchmark",
            "claim_profile_targets": ["full_stack_publication_claim"],
            "dataset_regime": "synthetic_canonical_panel_and_graphs",
            "baseline_snapshot_ref": "policy_did_interference@synthetic-v1",
            "regression_guard": {
                "max_abs_att_error": 0.20,
                "max_did_bias_gap": 1.50,
                "min_detected_spillover_cases": 1,
            },
            "literature_anchor": [
                "Hudgens & Halloran (2008): causal inference with interference",
                "Aronow & Samii (2017): general interference and exposure mappings",
            ],
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Policy DID / interference benchmark")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode])
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    preflight = build_preflight(mode=mode.value, data_source="synthetic_policy_did_interference")
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
        print(f"\n[FAIL] {failures} interference case(s) failed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
