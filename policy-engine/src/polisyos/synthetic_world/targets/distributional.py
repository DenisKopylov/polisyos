"""Distributional truth targets."""
from __future__ import annotations

from typing import Any

import numpy as np


def register_distributional_targets(
    *,
    sample: np.ndarray,
    subgroup_ids: np.ndarray | None = None,
    subgroup_name: str = "group",
) -> dict[str, dict[str, Any]]:
    """Register quantile, CDF, and subgroup distribution targets."""
    arr = np.asarray(sample, dtype=float)
    grid = np.quantile(arr, np.linspace(0.05, 0.95, 7))
    sorted_arr = np.sort(arr)
    empirical_cdf = np.searchsorted(sorted_arr, grid, side="right") / max(sorted_arr.shape[0], 1)
    density, density_edges = np.histogram(arr, bins=min(12, max(arr.shape[0] // 8, 4)), density=True)
    density_grid = 0.5 * (density_edges[:-1] + density_edges[1:])
    targets: dict[str, dict[str, Any]] = {
        "distributional.quantile.p10": {"value": float(np.quantile(arr, 0.10))},
        "distributional.quantile.p50": {"value": float(np.quantile(arr, 0.50))},
        "distributional.quantile.p90": {"value": float(np.quantile(arr, 0.90))},
        "distributional.cdf": {
            "grid": grid.tolist(),
            "values": empirical_cdf.tolist(),
        },
        "distributional.pdf": {
            "grid": density_grid.tolist(),
            "values": density.tolist(),
        },
        "distributional.tail_risk.cvar90": {
            "value": float(np.mean(arr[arr >= np.quantile(arr, 0.9)])),
        },
    }
    if subgroup_ids is not None:
        subgroup = np.asarray(subgroup_ids)
        subgroup_means: dict[str, float] = {}
        for key in np.unique(subgroup):
            subgroup_means[str(key)] = float(np.mean(arr[subgroup == key]))
        targets["distributional.subgroup_means"] = {
            "values": list(subgroup_means.values()),
            "coords": {subgroup_name: list(subgroup_means.keys())},
        }
    return targets


__all__ = ["register_distributional_targets"]
