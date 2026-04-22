#!/usr/bin/env python3
"""Lightweight benchmark for Phase 2 distributional frontier methods."""

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

from polisyos.foundry.methods.catalog.causal.distributional_bounds import (
    DistributionalFunctional,
    mtr_headcount_distributional_bounds,
    sd_headcount_distributional_bounds,
)
from polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis import (
    _run_ordinal_poverty_estimate,
)

SUITE_ID = "phase2_distributional_frontier"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    outcome = np.array([0.2, 0.3, 0.45, 0.7, 0.85, 0.1, 0.2, 0.35, 0.5, 0.7], dtype=float)
    treatment = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0], dtype=float)

    mtr_bundle, _ = mtr_headcount_distributional_bounds(
        outcome=outcome,
        treatment=treatment,
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis_values=(0.4,),
        target_potential_outcome="y1",
    )
    sd_bundle, _ = sd_headcount_distributional_bounds(
        outcome=outcome,
        treatment=treatment,
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis_values=(0.4,),
        target_potential_outcome="y1",
    )

    ordinal_config = {
        "category_orders": [[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3]],
        "deprivation_cutoffs": [2, 2, 1],
        "dimension_names": ["health", "education", "housing"],
        "poverty_cutoff_K": 2 / 3,
        "comparator_recodings": [
            {
                "name": "stretched",
                "category_orders": [[1, 2, 10, 100], [1, 4, 10, 100], [1, 9, 20]],
            }
        ],
    }
    baseline = _run_ordinal_poverty_estimate(
        ordinal_config,
        category_matrix=np.array(
            [
                [1, 1, 1],
                [2, 2, 2],
                [1, 3, 1],
                [3, 1, 2],
                [4, 2, 1],
            ],
            dtype=int,
        ),
        label="baseline",
    )
    counterfactual = _run_ordinal_poverty_estimate(
        ordinal_config,
        category_matrix=np.array(
            [
                [2, 2, 2],
                [3, 3, 2],
                [2, 3, 2],
                [3, 2, 2],
                [4, 3, 2],
            ],
            dtype=int,
        ),
        label="counterfactual",
    )

    payload = {
        "suite_id": SUITE_ID,
        "status": "pass",
        "metrics": {
            "mtr_lower_envelope": mtr_bundle.consensus_bounds.lower[0],
            "sd_upper_envelope": sd_bundle.consensus_bounds.upper[0],
            "ordinal_counterfactual_delta": (
                counterfactual.ordinal_adjusted_headcount_q - baseline.ordinal_adjusted_headcount_q
            ),
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
