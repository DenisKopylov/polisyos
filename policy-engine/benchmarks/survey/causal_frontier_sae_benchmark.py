"""Track 5.2 benchmark for causal-frontier small-area estimation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from benchmarks.harness import BenchmarkCase, BenchmarkCircuit, BenchmarkHarness
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
from benchmarks.runtime import resolve_mode, resolve_tier
from polisyos.foundry.methods.catalog.survey.causal_frontier import (
    CausalFrontierFayHerriotEstimator,
)

SUITE_ID = "survey_causal_frontier_sae"
BENCHMARK_FAMILY = "survey"
LITERATURE_ANCHOR = [
    "Track 5.2 — cross-area dependence with causal frontiers and boundary leakage diagnostics.",
    "Production baseline: constrained graph smoother with unrestricted leakage control.",
]


def _chain_weights(n_areas: int) -> list[list[float]]:
    weights = np.zeros((n_areas, n_areas), dtype=float)
    for idx in range(n_areas - 1):
        weights[idx, idx + 1] = 1.0
        weights[idx + 1, idx] = 1.0
    return weights.tolist()


def _base_state(
    *,
    n_areas: int,
    jump: float,
    spillover_gamma: float,
    include_spillover: bool,
    frontier_edges: list[tuple[str, str, bool]],
) -> tuple[dict[str, Any], dict[str, float]]:
    area_ids = [f"area_{idx}" for idx in range(n_areas)]
    policy = np.zeros(n_areas, dtype=float)
    policy[n_areas // 2 :] = 1.0
    exposure = np.array([0.0, 0.0, 0.2, 0.6, 1.0, 1.0, 0.6, 0.2, 0.0, 0.0], dtype=float)[:n_areas]
    baseline_mean = np.full(n_areas, 1.5, dtype=float)
    sampling_noise = np.array(
        [-0.06, -0.03, 0.00, 0.03, 0.06, -0.06, -0.03, 0.00, 0.03, 0.06],
        dtype=float,
    )[:n_areas]
    y_direct = baseline_mean + jump * policy + spillover_gamma * exposure + sampling_noise

    state: dict[str, Any] = {
        "area_ids": area_ids,
        "y_direct": y_direct,
        "X": np.ones((n_areas, 1), dtype=float),
        "sampling_var": np.full(n_areas, 0.18, dtype=float),
        "policy_indicator": policy,
        "graph": {
            "graph_id": "track52_chain",
            "family": "CAR",
            "W": _chain_weights(n_areas),
        },
        "frontier_edges": frontier_edges,
    }
    if include_spillover:
        state["spillover_exposure"] = exposure
    truth = {"tau": jump, "spillover_gamma": spillover_gamma}
    return state, truth


def _null_case() -> dict[str, Any]:
    state, truth = _base_state(
        n_areas=10,
        jump=0.0,
        spillover_gamma=0.0,
        include_spillover=False,
        frontier_edges=[("area_4", "area_5", True)],
    )
    result = CausalFrontierFayHerriotEstimator.pure_step(
        state,
        {"lambda_spatial": 14.0, "component_ridge": 1e-4},
    )["result"]
    return {
        "case": "null_piecewise_smooth",
        "truth": truth,
        "statistics": result.statistics,
    }


def _jump_case() -> dict[str, Any]:
    state, truth = _base_state(
        n_areas=10,
        jump=1.1,
        spillover_gamma=0.0,
        include_spillover=False,
        frontier_edges=[("area_4", "area_5", True)],
    )
    result = CausalFrontierFayHerriotEstimator.pure_step(
        state,
        {"lambda_spatial": 14.0, "component_ridge": 1e-4},
    )["result"]
    return {
        "case": "policy_jump",
        "truth": truth,
        "statistics": result.statistics,
    }


def _spillover_case() -> dict[str, Any]:
    state, truth = _base_state(
        n_areas=10,
        jump=0.9,
        spillover_gamma=0.45,
        include_spillover=True,
        frontier_edges=[("area_4", "area_5", True)],
    )
    result = CausalFrontierFayHerriotEstimator.pure_step(
        state,
        {"lambda_spatial": 12.0, "component_ridge": 1e-4},
    )["result"]
    return {
        "case": "spillover_exposure",
        "truth": truth,
        "statistics": result.statistics,
    }


def _small_component_stress_case() -> dict[str, Any]:
    state, truth = _base_state(
        n_areas=8,
        jump=0.8,
        spillover_gamma=0.0,
        include_spillover=False,
        frontier_edges=[
            ("area_0", "area_1", True),
            ("area_3", "area_4", True),
            ("area_6", "area_7", True),
        ],
    )
    result = CausalFrontierFayHerriotEstimator.pure_step(
        state,
        {"lambda_spatial": 16.0, "component_ridge": 1e-4},
    )["result"]
    return {
        "case": "small_component_stress",
        "truth": truth,
        "statistics": result.statistics,
    }


def _check_null_case(payload: dict[str, Any]) -> bool:
    diagnostics = payload["statistics"]["diagnostics"]
    if float(diagnostics["blr"]) >= 0.05:
        raise AssertionError("piecewise-smooth null should not trigger meaningful boundary leakage")
    return True


def _check_jump_case(payload: dict[str, Any]) -> bool:
    truth_tau = float(payload["truth"]["tau"])
    statistics = payload["statistics"]
    baseline = statistics["baseline_unrestricted"]
    tau_cut = float(statistics["tau"])
    tau_unc = float(baseline["tau"])
    diagnostics = statistics["diagnostics"]
    if abs(tau_cut - truth_tau) >= abs(tau_unc - truth_tau):
        raise AssertionError("constrained model should recover the policy jump at least as well as unrestricted smoothing")
    if float(diagnostics["blr"]) <= 0.05:
        raise AssertionError("policy jump case should surface positive leakage under unrestricted smoothing")
    return True


def _check_spillover_case(payload: dict[str, Any]) -> bool:
    truth_gamma = float(payload["truth"]["spillover_gamma"])
    statistics = payload["statistics"]
    gamma_hat = statistics["spillover_gamma"]
    if gamma_hat is None:
        raise AssertionError("spillover case should estimate a spillover coefficient")
    if abs(float(gamma_hat) - truth_gamma) > 0.35:
        raise AssertionError("spillover coefficient estimate is too far from the synthetic truth")
    return True


def _check_small_component_case(payload: dict[str, Any]) -> bool:
    diagnostics = payload["statistics"]["diagnostics"]
    if int(diagnostics["singletons_after_cut"]) < 2:
        raise AssertionError("stress case should create post-cut singleton areas")
    if float(diagnostics["variance_inflation_ratio"]) < 1.0:
        raise AssertionError("stress case should inflate variance after cutting frontier edges")
    return True


def _build_report(mode: str, *, quiet: bool) -> dict[str, Any]:
    harness = BenchmarkHarness()
    harness.register_many(
        [
            BenchmarkCase(
                name="survey::causal_frontier::null_piecewise_smooth",
                circuit=BenchmarkCircuit.ESTIMATION,
                runner=_null_case,
                checker=_check_null_case,
                tags=("survey", "causal_frontier", "null"),
                timeout_s=10.0,
            ),
            BenchmarkCase(
                name="survey::causal_frontier::policy_jump",
                circuit=BenchmarkCircuit.ESTIMATION,
                runner=_jump_case,
                checker=_check_jump_case,
                tags=("survey", "causal_frontier", "jump"),
                timeout_s=10.0,
            ),
            BenchmarkCase(
                name="survey::causal_frontier::spillover_exposure",
                circuit=BenchmarkCircuit.ESTIMATION,
                runner=_spillover_case,
                checker=_check_spillover_case,
                tags=("survey", "causal_frontier", "spillover"),
                timeout_s=10.0,
            ),
            BenchmarkCase(
                name="survey::causal_frontier::small_component_stress",
                circuit=BenchmarkCircuit.ESTIMATION,
                runner=_small_component_stress_case,
                checker=_check_small_component_case,
                tags=("survey", "causal_frontier", "stress"),
                timeout_s=10.0,
            ),
        ]
    )
    report = harness.run(circuit=BenchmarkCircuit.ESTIMATION)
    preflight = build_preflight(
        mode=mode,
        benchmark_tier=resolve_tier(mode=resolve_mode(mode)).value,
        data_source="synthetic_suite",
        dataset_family=BENCHMARK_FAMILY,
    )
    if not quiet:
        print_preflight(preflight)

    payloads = [
        case.result_payload for case in report.cases if isinstance(case.result_payload, dict)
    ]
    null_payload = next(payload for payload in payloads if payload["case"] == "null_piecewise_smooth")
    jump_payload = next(payload for payload in payloads if payload["case"] == "policy_jump")
    stress_payload = next(payload for payload in payloads if payload["case"] == "small_component_stress")
    jump_stats = jump_payload["statistics"]
    null_stats = null_payload["statistics"]
    stress_stats = stress_payload["statistics"]
    truth_tau = float(jump_payload["truth"]["tau"])
    tau_cut = float(jump_stats["tau"])
    tau_unc = float(jump_stats["baseline_unrestricted"]["tau"])

    aggregate_metrics = {
        "null_false_alert_rate": float(
            float(null_stats["diagnostics"]["alert_level"] != "green")
        ),
        "jump_detection_rate": float(
            float(float(jump_stats["diagnostics"]["blr"]) > 0.05)
        ),
        "mean_variance_inflation": float(
            np.mean(
                [
                    float(payload["statistics"]["diagnostics"]["variance_inflation_ratio"])
                    for payload in payloads
                ]
            )
        ),
        "mean_tau_abs_error_improvement": float(abs(tau_unc - truth_tau) - abs(tau_cut - truth_tau)),
        "stress_singletons_after_cut": float(stress_stats["diagnostics"]["singletons_after_cut"]),
    }

    return build_report_payload(
        report,
        suite_id=SUITE_ID,
        mode=mode,
        preflight=preflight,
        sub_circuit="survey",
        benchmark_family=BENCHMARK_FAMILY,
        proof_class="publication_benchmark",
        literature_anchor=LITERATURE_ANCHOR,
        aggregate_metrics=aggregate_metrics,
        case_details_builder=lambda case: case.result_payload if isinstance(case.result_payload, dict) else {},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track 5.2 causal-frontier SAE benchmark")
    parser.add_argument("--mode", default="smoke")
    parser.add_argument("--json", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    payload = _build_report(args.mode, quiet=args.quiet)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.json:
        Path(args.json).write_text(rendered + "\n", encoding="utf-8")
    if not args.quiet:
        print(rendered)
    return 0 if payload.get("overall_status") in {"passed", "over_budget", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
