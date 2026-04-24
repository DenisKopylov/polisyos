"""ERGM null-lite diffusion benchmark entrypoint.

This suite exercises the structural-null layer introduced for Phase 2:
1. null-lite ERGM fit with GOF-style diagnostics,
2. diffusion-null calibration on a synthetic pre-treatment network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

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
from polisyos.foundry.methods.catalog.network.ergm import (  # noqa: E402
    DiffusionNullTestEstimator,
    ERGMNullModelEstimator,
)
from polisyos.foundry.methods.catalog.network.protocols import NetworkData  # noqa: E402

CIRCUIT = BenchmarkCircuit.ESTIMATION


def _build_state(*, seed: int, bridge_boost: float = 0.0) -> NetworkData:
    rng = np.random.default_rng(seed)
    labels = np.array([0] * 10 + [1] * 10, dtype=int)
    n = labels.shape[0]
    adjacency = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            prob = 0.60 if labels[i] == labels[j] else 0.08 + bridge_boost
            edge = float(rng.uniform() < min(prob, 0.95))
            adjacency[i, j] = edge
            adjacency[j, i] = edge
    node_features = np.column_stack(
        [
            labels.astype(float),
            rng.normal(scale=0.15, size=n),
        ]
    )
    node_states = np.zeros(n, dtype=float)
    node_states[:4] = 1.0
    return NetworkData(
        adjacency=adjacency,
        node_features=node_features,
        node_states=node_states,
        metadata={"ergm_group_labels": labels.tolist()},
    )


def _case_ergm_null_fit() -> BenchmarkCase:
    state = _build_state(seed=17)

    def runner() -> dict[str, Any]:
        artifact = ERGMNullModelEstimator.pure_step(
            state,
            {"n_simulations": 16, "save_graphs": 4, "__seed__": 17},
        )["result"]
        return {
            "artifact": artifact,
            "artifact_kind": "ergm_null",
            "design": "clustered_pre_treatment_graph",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        assert artifact.fit_status == "null_lite"
        assert "gwdegree" in artifact.coefficients
        assert "gwesp" in artifact.coefficients
        assert artifact.metadata["n_simulations"] == 16
        assert (
            artifact.gof_checks["edge_density"]["q05"] <= artifact.gof_checks["edge_density"]["q95"]
        )
        return True

    return BenchmarkCase(
        name="ergm_null::fit_null_lite",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("network", "ergm", "null_model", "phase2"),
        timeout_s=10.0,
    )


def _case_diffusion_null_summary() -> BenchmarkCase:
    state = _build_state(seed=29, bridge_boost=0.05)

    def runner() -> dict[str, Any]:
        artifact = DiffusionNullTestEstimator.pure_step(
            state,
            {
                "n_simulations": 16,
                "n_steps": 8,
                "diffusion_rate": 0.35,
                "decay": 0.04,
                "__seed__": 29,
            },
        )["result"]
        return {
            "artifact": artifact,
            "artifact_kind": "diffusion_null",
            "design": "deGroot_against_structural_null",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        assert 0.0 <= artifact.p_value <= 1.0
        assert artifact.null_std >= 0.0
        assert artifact.envelope["q05"] <= artifact.envelope["q50"] <= artifact.envelope["q95"]
        assert len(artifact.simulated_metrics) == 16
        return True

    return BenchmarkCase(
        name="ergm_null::diffusion_null_summary",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("network", "ergm", "diffusion", "phase2"),
        timeout_s=10.0,
    )


def build_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register_many(
        [
            _case_ergm_null_fit(),
            _case_diffusion_null_summary(),
        ]
    )
    return harness


def _aggregate_metrics(report: BenchmarkReport) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    p_values: list[float] = []
    alarms = 0
    for case in report.cases:
        payload = case.result_payload or {}
        artifact = payload.get("artifact")
        if artifact is None:
            continue
        row = {
            "case": case.name,
            "artifact_kind": payload.get("artifact_kind"),
            "design": payload.get("design"),
        }
        if hasattr(artifact, "degeneracy_alarm"):
            row["degeneracy_alarm"] = bool(artifact.degeneracy_alarm)
            alarms += int(bool(artifact.degeneracy_alarm))
        if hasattr(artifact, "p_value"):
            row["p_value"] = float(artifact.p_value)
            p_values.append(float(artifact.p_value))
        rows.append(row)
    return {
        "case_rows": rows,
        "degeneracy_alarm_count": alarms,
        "mean_p_value": float(np.mean(p_values)) if p_values else None,
        "all_cases_green": report.n_total() == report.n_passed(),
    }


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="ergm_null_diffusion",
        mode=mode,
        preflight=preflight,
        sub_circuit="ergm_null_diffusion",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(report),
        extra={
            "benchmark_family": "network",
            "proof_class": "supplementary_benchmark",
            "dataset_regime": "synthetic_phase2_networks",
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ERGM null-lite diffusion benchmark")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode])
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    preflight = build_preflight(mode=mode.value, data_source="synthetic_ergm_null_diffusion")
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
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
