#!/usr/bin/env python3
"""Lightweight benchmark for Phase 2 mobility frontier methods."""

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

from polisyos.foundry.methods.catalog.distributional.mobility import (
    AttritionAdjustedMobilityMatrixEstimator,
)

SUITE_ID = "phase2_mobility_frontier"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    origin = np.concatenate(
        (
            np.zeros(100, dtype=int),
            np.zeros(100, dtype=int),
            np.ones(100, dtype=int),
            np.ones(100, dtype=int),
        )
    )
    feature = np.concatenate(
        (
            np.zeros(100, dtype=float),
            np.ones(100, dtype=float),
            np.zeros(100, dtype=float),
            np.ones(100, dtype=float),
        )
    )
    destination_full = feature.astype(int)
    retained = np.concatenate(
        (
            np.r_[np.ones(90, dtype=int), np.zeros(10, dtype=int)],
            np.r_[np.ones(30, dtype=int), np.zeros(70, dtype=int)],
            np.r_[np.ones(90, dtype=int), np.zeros(10, dtype=int)],
            np.r_[np.ones(30, dtype=int), np.zeros(70, dtype=int)],
        )
    )
    destination = np.where(retained == 1, destination_full, -1)
    retention_probabilities = np.where(feature == 0.0, 0.9, 0.3)

    report = AttritionAdjustedMobilityMatrixEstimator.pure_step(
        {
            "origin_classes": origin,
            "destination_classes": destination,
            "retention_indicators": retained,
            "attrition_features": feature.reshape(-1, 1),
            "retention_probabilities": retention_probabilities,
        },
        {"n_classes": 2, "estimator": "ipcw", "compute_bounds": True},
    )["result"]

    transition_matrix = np.asarray(report.point_estimate.transition_matrix, dtype=float)
    payload = {
        "suite_id": SUITE_ID,
        "status": "pass",
        "metrics": {
            "row0_balance_error": float(abs(transition_matrix[0, 0] - 0.5)),
            "row1_balance_error": float(abs(transition_matrix[1, 0] - 0.5)),
            "bounds_present": 1.0 if report.bounds.bundle_ref is not None else 0.0,
        },
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    if not args.quiet:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
