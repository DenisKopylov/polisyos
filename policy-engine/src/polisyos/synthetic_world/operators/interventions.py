"""Intervention assignment helpers."""

from __future__ import annotations

import numpy as np


def _sigmoid(value: np.ndarray | float) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    return 1.0 / (1.0 + np.exp(-np.clip(array, -30.0, 30.0)))


def static_treatment_assignments(
    *,
    features: np.ndarray,
    latent_driver: np.ndarray,
    confounding_strength: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign cross-sectional treatments and return `(treatment, propensity)`."""
    logits = (
        0.2
        + features[:, 0]
        - 0.35 * features[:, min(1, features.shape[1] - 1)]
        + confounding_strength * latent_driver
    )
    propensity = _sigmoid(logits)
    treatment = rng.binomial(1, propensity, size=features.shape[0]).astype(int)
    return treatment, propensity


def dynamic_treatment_assignments(
    *,
    lagged_state: np.ndarray,
    features: np.ndarray,
    latent_driver: np.ndarray,
    confounding_strength: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign dynamic treatments at one time step and return `(treatment, propensity)`."""
    logits = (
        -0.1 + 0.45 * lagged_state + 0.25 * features[:, 0] + confounding_strength * latent_driver
    )
    propensity = _sigmoid(logits)
    treatment = rng.binomial(1, propensity).astype(int)
    return treatment, propensity


def spatial_intervention_assignments(
    *,
    n_regions: int,
    period: int,
    treatment_start_period: int,
) -> np.ndarray:
    """Assign spatial interventions after a shared regime start."""
    treated = np.arange(n_regions) >= n_regions // 2
    return (treated & (period >= treatment_start_period)).astype(int)


def survey_wave_treatment_assignments(
    *,
    wave_index: np.ndarray,
    treatment_share: float,
) -> np.ndarray:
    """Assign wave-level treatment markers for repeated cross-sections."""
    threshold = max(1, int(round(1.0 / max(treatment_share, 1.0e-6))))
    return ((wave_index % threshold) == 0).astype(int)


__all__ = [
    "dynamic_treatment_assignments",
    "spatial_intervention_assignments",
    "static_treatment_assignments",
    "survey_wave_treatment_assignments",
]
