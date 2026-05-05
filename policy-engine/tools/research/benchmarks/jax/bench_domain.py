#!/usr/bin/env python3
"""Manual Foundry domain benchmarks for release-gate method families."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from typing import Any

from tools.lib.imports import ensure_repo_import_roots, repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

REPO_ROOT, SRC_ROOT = ensure_repo_import_roots(__file__)

import jax_bootstrap  # noqa: F401
import numpy as np
from polisyos.foundry.methods.catalog.bayesian.regression import BayesianLinearRegressionEstimator
from polisyos.foundry.methods.catalog.ml.protocols import TabularData
from polisyos.foundry.methods.catalog.optimization.lp import ResourceLP
from polisyos.foundry.methods.catalog.optimization.protocols import (
    AllocationItem,
    OptimizationProblem,
    ResourceConstraint,
)
from polisyos.foundry.methods.catalog.survey.estimation import FayHerriotEstimator


def _benchmark(
    fn: Callable[[], Any],
    *,
    warmup: int,
    repeat: int,
) -> dict[str, float]:
    for _ in range(max(warmup, 0)):
        fn()

    samples_ms: list[float] = []
    for _ in range(max(repeat, 1)):
        start = time.perf_counter()
        fn()
        samples_ms.append((time.perf_counter() - start) * 1000.0)

    arr = np.asarray(samples_ms, dtype=float)
    return {
        "mean_ms": float(np.mean(arr)),
        "median_ms": float(np.median(arr)),
        "p95_ms": float(np.percentile(arr, 95.0)),
        "min_ms": float(np.min(arr)),
        "max_ms": float(np.max(arr)),
        "rounds": float(arr.shape[0]),
    }


def _bayesian_state() -> TabularData:
    features = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
            [2.0, 1.0],
            [2.0, 2.0],
            [3.0, 1.0],
            [3.0, 2.0],
        ],
        dtype=float,
    )
    target = np.array([1.0, 2.7, 0.5, 2.2, 4.0, 3.5, 5.8, 5.0], dtype=float)
    return TabularData(features=features, target=target, feature_names=["x0", "x1"])


def _optimization_problem() -> OptimizationProblem:
    return OptimizationProblem(
        problem_id="bench_domain_lp",
        budget=8.0,
        items=(
            AllocationItem(
                item_id="clinics",
                cost=2.0,
                benefit=5.0,
                max_units=4,
                is_integer=False,
            ),
            AllocationItem(
                item_id="schools",
                cost=1.0,
                benefit=2.0,
                max_units=6,
                is_integer=False,
            ),
        ),
        constraints=(
            ResourceConstraint(
                constraint_id="staffing",
                coefficients={"clinics": 1.0, "schools": 1.0},
                bound=6.0,
                sense="<=",
            ),
        ),
    )


def _survey_state() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(42)
    n_areas = 12
    return {
        "y_direct": rng.normal(50, 5, size=n_areas),
        "X": rng.normal(0, 1, size=(n_areas, 2)),
        "sampling_var": np.abs(rng.normal(1, 0.3, size=n_areas)) + 0.1,
    }


def run_benchmarks(*, warmup: int, repeat: int) -> dict[str, dict[str, Any]]:
    bayesian_state = _bayesian_state()
    optimization_problem = _optimization_problem()
    survey_state = _survey_state()

    def _run_bayesian() -> dict[str, Any]:
        result = BayesianLinearRegressionEstimator.pure_step(
            bayesian_state,
            {
                "num_warmup": 32,
                "num_samples": 32,
                "num_chains": 1,
                "proposal_scale": 0.025,
            },
        )
        assert result["result"].method_name == "bayesian_linear_regression"
        return result

    def _run_optimization() -> tuple[dict[str, Any], dict[str, Any]]:
        payload, solver_info = ResourceLP.pure_step(
            optimization_problem,
            {"prefer_ortools": False},
        )
        assert payload["status"] in {"optimal", "feasible", "error"}
        return payload, solver_info

    def _run_survey() -> dict[str, Any]:
        result = FayHerriotEstimator.pure_step(survey_state, {"max_iter": 40})
        assert result["result"]["n_areas"] == survey_state["y_direct"].shape[0]
        return result

    return {
        "bayesian": {
            "benchmark": _benchmark(_run_bayesian, warmup=warmup, repeat=repeat),
            "method": "bayesian.regression.linear_regression@1.0.0",
        },
        "optimization": {
            "benchmark": _benchmark(_run_optimization, warmup=warmup, repeat=repeat),
            "method": "optimization.linear.resource_lp@1.0.0",
        },
        "survey": {
            "benchmark": _benchmark(_run_survey, warmup=warmup, repeat=repeat),
            "method": "survey.estimation.fay_herriot@1.0.0",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Foundry release-gate domains")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup iterations per domain")
    parser.add_argument("--repeat", type=int, default=5, help="Measured iterations per domain")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text summary",
    )
    args = parser.parse_args()

    results = run_benchmarks(warmup=args.warmup, repeat=args.repeat)
    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
        return 0

    print("Foundry domain benchmark summary")
    for domain, payload in results.items():
        stats = payload["benchmark"]
        print(
            f"- {domain}: mean={stats['mean_ms']:.2f}ms "
            f"median={stats['median_ms']:.2f}ms p95={stats['p95_ms']:.2f}ms "
            f"rounds={int(stats['rounds'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
