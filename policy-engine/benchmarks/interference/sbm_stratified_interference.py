"""SBM-stratified interference benchmark entrypoint.

This suite checks the Phase 2 bridge from pre-treatment network strata into the
existing interference-aware causal estimators.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import adjusted_rand_score

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
from polisyos.foundry.methods.catalog.causal.interference import (  # noqa: E402
    PartialInterferenceEstimator,
    build_block_stratified_network_causal_data,
)
from polisyos.foundry.methods.catalog.network.protocols import NetworkData  # noqa: E402
from polisyos.foundry.methods.catalog.network.sbm import SBMStratificationEstimator  # noqa: E402

CIRCUIT = BenchmarkCircuit.ESTIMATION


def _fractional_exposure(treatment: np.ndarray, cluster_id: np.ndarray) -> np.ndarray:
    exposure = np.zeros_like(treatment, dtype=float)
    for cluster in np.unique(cluster_id):
        mask = cluster_id == cluster
        members = np.where(mask)[0]
        if members.size < 2:
            continue
        for idx in members:
            exposure[idx] = (float(np.sum(treatment[mask])) - float(treatment[idx])) / (
                members.size - 1
            )
    return exposure


def _build_graph_with_effects(
    *, seed: int
) -> tuple[NetworkData, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    truth = np.array([0] * 15 + [1] * 15, dtype=int)
    n = truth.shape[0]
    adjacency = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            prob = 0.78 if truth[i] == truth[j] else 0.06
            edge = float(rng.uniform() < prob)
            adjacency[i, j] = edge
            adjacency[j, i] = edge
    node_features = np.column_stack(
        [
            truth.astype(float) + rng.normal(scale=0.08, size=n),
            (truth == 0).astype(float) + rng.normal(scale=0.08, size=n),
        ]
    )
    treatment = rng.binomial(1, 0.5, size=n).astype(float)
    exposure = _fractional_exposure(treatment, truth)
    outcome = 1.0 * treatment + 0.6 * exposure + rng.normal(scale=0.25, size=n)
    return (
        NetworkData(
            adjacency=adjacency,
            node_features=node_features,
            node_ids=[f"u{i}" for i in range(n)],
        ),
        truth,
        treatment,
        outcome,
    )


def _case_sbm_recovery() -> BenchmarkCase:
    state, truth, _, _ = _build_graph_with_effects(seed=7)

    def runner() -> dict[str, Any]:
        artifact = SBMStratificationEstimator.pure_step(
            state,
            {
                "n_blocks": 2,
                "bootstrap_samples": 4,
                "covariate_scale": 0.6,
                "min_block_size": 4,
                "__seed__": 7,
            },
        )["result"]
        return {
            "artifact": artifact,
            "artifact_kind": "sbm_stratification",
            "truth_labels": truth,
            "design": "clear_two_block_pre_treatment_graph",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        ari = adjusted_rand_score(result["truth_labels"], np.asarray(artifact.labels, dtype=int))
        assert ari > 0.80
        assert artifact.stability["overall_stability"] > 0.50
        assert artifact.metadata["effective_blocks"] == 2
        return True

    return BenchmarkCase(
        name="sbm_interference::stratification_recovery",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("network", "sbm", "interference", "phase2"),
        timeout_s=10.0,
    )


def _case_block_bridged_partial_interference() -> BenchmarkCase:
    state, _, treatment, outcome = _build_graph_with_effects(seed=19)

    def runner() -> dict[str, Any]:
        stratification = SBMStratificationEstimator.pure_step(
            state,
            {
                "n_blocks": 2,
                "bootstrap_samples": 4,
                "covariate_scale": 0.6,
                "min_block_size": 4,
                "__seed__": 19,
            },
        )["result"]
        causal_data, bridge = build_block_stratified_network_causal_data(
            outcome=outcome,
            treatment=treatment,
            covariates=state.node_features,
            adjacency_matrix=state.adjacency,
            stratification=stratification,
        )
        report = PartialInterferenceEstimator.pure_step(
            causal_data,
            {"alpha_high": 0.5, "alpha_low": 0.0, "alpha_bandwidth": 0.2},
        )["result"]
        return {
            "artifact": report,
            "artifact_kind": "partial_interference",
            "bridge": bridge,
            "design": "sbm_to_cluster_id_bridge",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        bridge = result["bridge"]
        assert artifact.is_success
        assert artifact.direct_effect is not None
        assert abs(float(artifact.direct_effect) - 1.0) < 0.45
        assert bridge.positivity_passed
        return True

    return BenchmarkCase(
        name="sbm_interference::block_bridged_partial_interference",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("network", "sbm", "interference", "causal_bridge", "phase2"),
        timeout_s=10.0,
    )


def build_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register_many(
        [
            _case_sbm_recovery(),
            _case_block_bridged_partial_interference(),
        ]
    )
    return harness


def _aggregate_metrics(report: BenchmarkReport) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    direct_effects: list[float] = []
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
        if hasattr(artifact, "labels"):
            row["effective_blocks"] = int(len(np.unique(np.asarray(artifact.labels, dtype=int))))
            row["overall_stability"] = float(artifact.stability["overall_stability"])
        if hasattr(artifact, "direct_effect") and artifact.direct_effect is not None:
            row["direct_effect"] = float(artifact.direct_effect)
            direct_effects.append(float(artifact.direct_effect))
        rows.append(row)
    return {
        "case_rows": rows,
        "mean_direct_effect": float(np.mean(direct_effects)) if direct_effects else None,
        "all_cases_green": report.n_total() == report.n_passed(),
    }


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="sbm_stratified_interference",
        mode=mode,
        preflight=preflight,
        sub_circuit="sbm_stratified_interference",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(report),
        extra={
            "benchmark_family": "interference",
            "proof_class": "supplementary_benchmark",
            "dataset_regime": "synthetic_phase2_networks",
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SBM-stratified interference benchmark")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode])
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    preflight = build_preflight(
        mode=mode.value, data_source="synthetic_sbm_stratified_interference"
    )
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
