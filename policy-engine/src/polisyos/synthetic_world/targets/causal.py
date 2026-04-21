"""Causal truth targets."""
from __future__ import annotations

from typing import Any

import numpy as np


def register_cross_sectional_causal_targets(
    *,
    y0: np.ndarray,
    y1: np.ndarray,
    treatment: np.ndarray,
    unit_ids: np.ndarray,
    propensity: np.ndarray,
    mediator: np.ndarray | None = None,
) -> dict[str, dict[str, Any]]:
    """ATE/ATT/CATE/ITE truth for cross-sectional worlds."""
    ite = np.asarray(y1, dtype=float) - np.asarray(y0, dtype=float)
    targets: dict[str, dict[str, Any]] = {
        "causal.ate": {"value": float(np.mean(ite))},
        "causal.att": {"value": float(np.mean(ite[np.asarray(treatment, dtype=int) == 1]))},
        "causal.atc": {"value": float(np.mean(ite[np.asarray(treatment, dtype=int) == 0]))},
        "causal.cate": {
            "values": ite.tolist(),
            "coords": {"unit_id": np.asarray(unit_ids).tolist()},
        },
        "causal.ite": {
            "values": ite.tolist(),
            "coords": {"unit_id": np.asarray(unit_ids).tolist()},
        },
        "causal.propensity": {
            "values": np.asarray(propensity, dtype=float).tolist(),
            "coords": {"unit_id": np.asarray(unit_ids).tolist()},
        },
    }
    if mediator is not None:
        mediator_arr = np.asarray(mediator, dtype=float)
        direct = ite - 0.2 * mediator_arr
        indirect = ite - direct
        targets["causal.mediation.direct_effect"] = {"value": float(np.mean(direct))}
        targets["causal.mediation.indirect_effect"] = {"value": float(np.mean(indirect))}
    return targets


def register_dynamic_causal_targets(
    *,
    treatment_effect: np.ndarray,
    unit_ids: np.ndarray,
    regime_value: float | None = None,
    path_treated: np.ndarray | None = None,
    path_untreated: np.ndarray | None = None,
    horizon_ids: np.ndarray | None = None,
) -> dict[str, dict[str, Any]]:
    """Dynamic-treatment truth targets."""
    effect = np.asarray(treatment_effect, dtype=float)
    targets = {
        "causal.dynamic_ate": {"value": float(np.mean(effect))},
        "causal.dynamic_ite": {
            "values": effect.tolist(),
            "coords": {"unit_id": np.asarray(unit_ids).tolist()},
        },
    }
    if regime_value is not None:
        targets["causal.dynamic_regime_value"] = {"value": float(regime_value)}
    if path_treated is not None and path_untreated is not None:
        horizons = np.asarray(horizon_ids if horizon_ids is not None else np.arange(np.asarray(path_treated).shape[0]), dtype=int)
        targets["causal.path_specific_outcomes"] = {
            "treated_path": np.asarray(path_treated, dtype=float).tolist(),
            "untreated_path": np.asarray(path_untreated, dtype=float).tolist(),
            "coords": {"horizon": horizons.tolist()},
        }
    return targets


def register_spatial_causal_targets(
    *,
    treatment_effect: np.ndarray,
    region_ids: np.ndarray,
) -> dict[str, dict[str, Any]]:
    """Spatial treatment-effect truth targets."""
    effect = np.asarray(treatment_effect, dtype=float)
    return {
        "causal.spatial_ate": {"value": float(np.mean(effect))},
        "causal.spatial_ite": {
            "values": effect.tolist(),
            "coords": {"region_id": np.asarray(region_ids).tolist()},
        },
    }


__all__ = [
    "register_cross_sectional_causal_targets",
    "register_dynamic_causal_targets",
    "register_spatial_causal_targets",
]
