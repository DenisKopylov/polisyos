"""Calibration helpers for causal-frontier boundary-leakage diagnostics."""
from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.survey.causal_frontier import CausalFrontierFayHerriotEstimator


def calibrate_boundary_leakage_thresholds(
    state: dict[str, Any],
    *,
    lambda_spatial: float,
    component_ridge: float,
    contrast_eps: float,
    reps: int,
    seed: int = 0,
    warning_quantile: float = 0.95,
    blocker_quantile: float = 0.99,
) -> dict[str, Any]:
    """Approximate BLR null thresholds via permutation calibration."""
    if reps <= 0:
        raise ValueError("reps must be positive")
    if not 0.0 < warning_quantile <= blocker_quantile <= 1.0:
        raise ValueError("warning_quantile and blocker_quantile must satisfy 0 < q <= 1")

    policy_indicator = np.asarray(state["policy_indicator"], dtype=float)
    spillover_exposure = state.get("spillover_exposure")
    spillover_array = (
        None if spillover_exposure is None else np.asarray(spillover_exposure, dtype=float)
    )
    rng = np.random.default_rng(seed)

    base_state = dict(state)
    base_state.pop("artifact_store", None)
    blr_values: list[float] = []
    pli_values: list[float] = []
    for _ in range(reps):
        permutation = rng.permutation(policy_indicator.shape[0])
        permuted_state = dict(base_state)
        permuted_state["policy_indicator"] = policy_indicator[permutation]
        if spillover_array is not None:
            permuted_state["spillover_exposure"] = spillover_array[permutation]
        result = CausalFrontierFayHerriotEstimator.pure_step(
            permuted_state,
            {
                "lambda_spatial": lambda_spatial,
                "component_ridge": component_ridge,
                "contrast_eps": contrast_eps,
                "green_threshold": 0.05,
                "red_threshold": 0.15,
            },
        )["result"]
        diagnostics = result.statistics["diagnostics"]
        blr_values.append(float(diagnostics["blr"]))
        pli_values.append(float(diagnostics["pli"]))

    warning_threshold = float(np.quantile(blr_values, warning_quantile))
    blocker_threshold = max(
        warning_threshold,
        float(np.quantile(blr_values, blocker_quantile)),
    )
    return {
        "method": "permutation_null",
        "reps": reps,
        "seed": seed,
        "warning_threshold": warning_threshold,
        "blocker_threshold": blocker_threshold,
        "warning_quantile": warning_quantile,
        "blocker_quantile": blocker_quantile,
        "null_blr_mean": float(np.mean(blr_values)),
        "null_blr_max": float(np.max(blr_values)),
        "null_pli_mean": float(np.mean(pli_values)),
    }


__all__ = ["calibrate_boundary_leakage_thresholds"]
