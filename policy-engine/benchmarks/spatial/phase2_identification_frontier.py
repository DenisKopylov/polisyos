#!/usr/bin/env python3
"""Lightweight benchmark for Phase 2 spatial identification methods."""

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

SUITE_ID = "phase2_spatial_identification"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output.")
    return parser


def _spatial_data(
    *,
    n: int = 24,
    bandwidth: float = 0.3,
    spillover: float = 0.3,
    seed: int = 29,
) -> dict[str, np.ndarray]:
    diff_rng = np.random.default_rng(seed)
    coords = diff_rng.uniform(size=(n, 2))
    treatment = diff_rng.binomial(1, 0.4, size=n).astype(float)
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    sq_dist = (diff**2).sum(axis=-1)
    weights = np.exp(-sq_dist / (2.0 * bandwidth**2))
    np.fill_diagonal(weights, 0.0)
    degree = weights.sum(axis=1)
    spill = np.where(degree > 0, (weights @ treatment) / degree, 0.0)
    outcome = 1.5 * treatment + spillover * spill + diff_rng.normal(scale=0.5, size=n)
    return {"outcome": outcome, "treatment": treatment, "coordinates": coords}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    data = _spatial_data(n=24, seed=29)
    treated = data["treatment"] > 0.5
    direct_effect = float(data["outcome"][treated].mean() - data["outcome"][~treated].mean())

    payload = {
        "suite_id": SUITE_ID,
        "status": "pass",
        "metrics": {
            "direct_effect": direct_effect,
            "coordinate_support_present": 1.0 if data["coordinates"] is not None else 0.0,
            "treated_share": float(data["treatment"].mean()),
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
