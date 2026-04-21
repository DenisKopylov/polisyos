"""Econometrics-oriented truth targets."""
from __future__ import annotations

from typing import Any

import numpy as np


def register_cross_sectional_econometrics_targets(
    *,
    treatment_effect: np.ndarray,
    structural_coefficients: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """Cross-sectional econometric targets."""
    return {
        "econometrics.treatment_effect": {"value": float(np.mean(treatment_effect))},
        "econometrics.structural_coefficients": {
            "coefficients": {str(key): float(value) for key, value in structural_coefficients.items()}
        },
    }


def register_panel_econometrics_targets(
    *,
    rho: float,
    treatment_effect: np.ndarray,
    unit_ids: np.ndarray,
    iv_late: float | None = None,
    complier_share: float | None = None,
    irf: np.ndarray | None = None,
    horizons: np.ndarray | None = None,
) -> dict[str, dict[str, Any]]:
    """Panel/dynamic econometric targets."""
    targets = {
        "econometrics.panel_fe": {
            "rho": float(rho),
            "treatment_effect": float(np.mean(treatment_effect)),
        },
        "econometrics.dynamic_multiplier": {
            "values": np.asarray(treatment_effect, dtype=float).tolist(),
            "coords": {"unit_id": np.asarray(unit_ids).tolist()},
        },
    }
    if iv_late is not None:
        targets["econometrics.iv_late"] = {
            "value": float(iv_late),
            "subpopulation": "compliers",
            "complier_share": float(complier_share if complier_share is not None else 0.0),
        }
    if irf is not None:
        irf_horizons = np.asarray(horizons if horizons is not None else np.arange(np.asarray(irf).shape[0]), dtype=int)
        targets["econometrics.irf"] = {
            "values": np.asarray(irf, dtype=float).tolist(),
            "coords": {"horizon": irf_horizons.tolist()},
        }
    return targets


def register_survey_econometrics_targets(
    *,
    wave_effects: np.ndarray,
    wave_ids: np.ndarray,
) -> dict[str, dict[str, Any]]:
    """Repeated-cross-section econometric targets."""
    return {
        "econometrics.wave_effects": {
            "values": np.asarray(wave_effects, dtype=float).tolist(),
            "coords": {"wave": np.asarray(wave_ids).tolist()},
        }
    }


__all__ = [
    "register_cross_sectional_econometrics_targets",
    "register_panel_econometrics_targets",
    "register_survey_econometrics_targets",
]
