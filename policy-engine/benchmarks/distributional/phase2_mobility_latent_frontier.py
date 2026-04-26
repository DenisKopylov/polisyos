#!/usr/bin/env python3
"""Lightweight benchmark for latent-heterogeneous long-horizon mobility."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from polisyos.foundry.methods.catalog.econometrics.mobility_latent import (  # noqa: E402
    LatentMobilityEstimator,
)

SUITE_ID = "phase2_mobility_latent_frontier"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output.")
    return parser


def _simulate_panel(*, n_entities: int = 64, seed: int = 41) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    n_periods = 8
    means = np.where(np.arange(n_entities) < n_entities // 2, -1.0, 1.0)
    rhos = np.full(n_entities, 0.2, dtype=float)
    p = np.zeros((n_entities, n_periods), dtype=float)
    y = np.zeros_like(p)
    for entity in range(n_entities):
        p[entity, 0] = rng.normal(scale=0.08)
        for time_idx in range(1, n_periods):
            p[entity, time_idx] = rhos[entity] * p[entity, time_idx - 1] + rng.normal(scale=0.08)
        y[entity] = means[entity] + p[entity] + rng.normal(scale=0.03, size=n_periods)

    return {
        "dependent": y.reshape(-1),
        "exog": np.zeros((n_entities * n_periods, 1), dtype=float),
        "entity_ids": np.repeat(np.arange(n_entities), n_periods),
        "time_ids": np.tile(np.arange(n_periods), n_entities),
        "feature_names": ["zero"],
    }


def run_latent_mobility_benchmark(*, n_entities: int = 64, seed: int = 41) -> dict[str, object]:
    result = LatentMobilityEstimator.pure_step(
        _simulate_panel(n_entities=n_entities, seed=seed),
        {
            "n_types": 2,
            "profile_order": 0,
            "n_starts": 1,
            "max_iter": 45,
            "horizons": (1, 5),
            "n_income_classes": 4,
            "random_seed": seed,
        },
    )
    econometric = result["result"]
    transition = np.asarray(result["transition_tensor"], dtype=float)
    max_row_sum_error = float(np.max(np.abs(transition.sum(axis=2) - 1.0)))
    max_latent_rho = float(max(econometric.diagnostics["rho"]))
    pooled_ar1 = float(econometric.diagnostics["pooled_ar1"])
    report = result["mobility_report"]

    return {
        "suite_id": SUITE_ID,
        "status": "pass",
        "metrics": {
            "pooled_minus_latent_rho": float(pooled_ar1 - max_latent_rho),
            "transition_row_sum_error": max_row_sum_error,
            "selected_k": float(econometric.diagnostics["selected_k"]),
            "mobility_report_ok": 1.0
            if report.analysis_type == "latent_mobility_transition_matrix"
            else 0.0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_latent_mobility_benchmark()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    if not args.quiet:
        print(rendered, end="")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
