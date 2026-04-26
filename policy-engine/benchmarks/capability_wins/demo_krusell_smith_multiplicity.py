"""Capability demo: KS-lite fixed-point multiplicity report.

This benchmark is intentionally synthetic. It exercises the Foundry feedback
multiplicity layer on a low-dimensional Krusell-Smith-lite perceived-law map:
two locally attractive belief regimes are separated by a threshold, and the
report must preserve both equilibria plus basin estimates.

Usage
-----
    python benchmarks/capability_wins/demo_krusell_smith_multiplicity.py
    python benchmarks/capability_wins/demo_krusell_smith_multiplicity.py --json report.json
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
for _path in [str(_SRC), str(_BENCH_ROOT)]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from polisyos.core.contracts.foundry import (  # noqa: E402
    FeedbackConfig,
    FeedbackSolverConfig,
    FeedbackStateSnapshot,
    FeedbackVariableSpec,
)
from polisyos.foundry.feedback import (  # noqa: E402
    MapEvaluation,
    PreparedFeedbackConfig,
    discover_equilibria,
    prepare_feedback_config,
)


def _prepare_config() -> PreparedFeedbackConfig:
    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="lom_intercept",
                source_kind="metric",
                source_ref="aggregate_capital_next",
                target_kind="parameter_override",
                target_ref="ks_lite_households",
                target_param="belief_intercept",
                initial_value=0.8,
                lower_bound=0.0,
                upper_bound=1.5,
                scale=1.0,
            )
        ],
        solver=FeedbackSolverConfig(
            homotopy_grid=[0.0, 1.0],
            damping_init=1.0,
            max_iter=20,
            multi_start_values=[[1.25]],
            fixed_point_merge_tol=1.0e-6,
            detect_multiplicity=True,
            multiplicity_max_attempts=16,
            multiplicity_sobol_draws=14,
            basin_draws=64,
            basin_seed=7,
        ),
    )
    return prepare_feedback_config(
        config,
        initial_state=FeedbackStateSnapshot(
            variable_ids=["lom_intercept"],
            values=[0.8],
            scales=[1.0],
            lower_bounds=[0.0],
            upper_bounds=[1.5],
            weights=[1.0],
        ),
    )


def _ks_lite_two_regime_map(values: np.ndarray) -> MapEvaluation:
    belief = float(values[0])
    target = 0.45 if belief < 0.85 else 1.15
    return MapEvaluation(
        map_value=np.asarray([target], dtype=float),
        diagnostics={
            "model_class": "ks_lite_synthetic",
            "aggregate_shock_regime": "low" if belief < 0.85 else "high",
        },
    )


def run_demo() -> dict[str, Any]:
    prepared = _prepare_config()
    report = discover_equilibria(
        prepared=prepared,
        evaluate_map=_ks_lite_two_regime_map,
        model_id="ks_lite_synthetic_two_regime",
        parameter_hash="synthetic:two_regime_v1",
    )
    num_equilibria = report.global_diagnostics.num_equilibria
    basin_mass = sum(
        estimate.share_hat or 0.0
        for estimate in report.basin_estimates
    )
    passed = num_equilibria == 2 and abs(basin_mass - 1.0) <= 1.0e-9
    return {
        "benchmark_id": "demo_krusell_smith_multiplicity",
        "passed": passed,
        "metrics": {
            "num_equilibria": num_equilibria,
            "num_attempts": report.global_diagnostics.num_attempts,
            "basin_mass": basin_mass,
            "num_bifurcation_candidates": len(report.bifurcation_candidates),
        },
        "report": report.model_dump(mode="json", by_alias=True, exclude_none=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    payload = run_demo()
    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload["metrics"], indent=2, sort_keys=True))  # noqa: T201
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
