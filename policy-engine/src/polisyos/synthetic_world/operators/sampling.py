"""Sampling-design operators for synthetic worlds."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from polisyos.synthetic_world.models import SamplingDesignKind


def _standardize(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    std = float(np.std(arr))
    if std <= 1.0e-9:
        return np.zeros_like(arr)
    return (arr - float(np.mean(arr))) / std


def _safe_logit(probability: float) -> float:
    clipped = float(np.clip(probability, 1.0e-6, 1.0 - 1.0e-6))
    return float(np.log(clipped / (1.0 - clipped)))


def _sigmoid(value: np.ndarray | float) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    return 1.0 / (1.0 + np.exp(-np.clip(array, -30.0, 30.0)))


@dataclass(frozen=True)
class SamplingOutcome:
    """Observed result of a sampling design."""

    inclusion_probability: np.ndarray
    sample_mask: np.ndarray
    base_weight: np.ndarray
    response_probability: np.ndarray | None = None
    respondent_mask: np.ndarray | None = None
    calibrated_weight: np.ndarray | None = None
    design_effect: float | None = None
    metadata: dict[str, Any] | None = None


def apply_entity_sampling(
    *,
    entity_signal: np.ndarray,
    design_kind: SamplingDesignKind,
    inclusion_rate: float,
    rng: np.random.Generator,
) -> SamplingOutcome:
    """Sample entities for cross-sectional, panel, and spatial worlds."""
    n_entities = int(np.asarray(entity_signal).shape[0])
    if design_kind is SamplingDesignKind.CENSUS:
        inclusion_probability = np.ones(n_entities, dtype=float)
        mask = np.ones(n_entities, dtype=bool)
    else:
        score = _standardize(np.asarray(entity_signal, dtype=float))
        inclusion_probability = np.clip(
            _sigmoid(_safe_logit(inclusion_rate) + 0.35 * score),
            0.05,
            1.0,
        )
        mask = rng.binomial(1, inclusion_probability, size=n_entities).astype(bool)
        if not mask.any():
            mask[int(np.argmax(inclusion_probability))] = True
    return SamplingOutcome(
        inclusion_probability=inclusion_probability,
        sample_mask=mask,
        base_weight=1.0 / inclusion_probability,
        metadata={"design_kind": design_kind.value},
    )


def apply_survey_sampling(
    *,
    size_signal: np.ndarray,
    inclusion_rate: float,
    response_rate: float,
    n_strata: int,
    n_clusters: int,
    calibrate_weights: bool,
    rng: np.random.Generator,
) -> SamplingOutcome:
    """Apply a finite-population survey design with response and weight calibration."""
    n_entities = int(np.asarray(size_signal).shape[0])
    score = _standardize(np.asarray(size_signal, dtype=float))
    strata = np.mod(np.arange(n_entities), max(1, n_strata))
    clusters = np.mod(np.arange(n_entities), max(1, n_clusters))

    inclusion_probability = np.clip(
        _sigmoid(_safe_logit(inclusion_rate) + 0.4 * score + 0.15 * _standardize(strata)),
        0.03,
        0.98,
    )
    sample_mask = rng.binomial(1, inclusion_probability, size=n_entities).astype(bool)
    if not sample_mask.any():
        sample_mask[int(np.argmax(inclusion_probability))] = True

    response_probability = np.clip(
        _sigmoid(_safe_logit(response_rate) - 0.25 * score + 0.2 * _standardize(clusters)),
        0.05,
        0.99,
    )
    respondent_mask = sample_mask & rng.binomial(1, response_probability, size=n_entities).astype(bool)
    if not respondent_mask.any():
        respondent_mask[int(np.argmax(response_probability * inclusion_probability))] = True

    base_weight = 1.0 / inclusion_probability
    response_adjusted = base_weight / np.clip(response_probability, 0.05, 1.0)
    if calibrate_weights:
        calibration_factor = float(n_entities / np.sum(response_adjusted[respondent_mask]))
        calibrated_weight = response_adjusted * calibration_factor
    else:
        calibrated_weight = response_adjusted
    design_effect = float(
        1.0
        + np.var(calibrated_weight[respondent_mask]) / max(np.mean(calibrated_weight[respondent_mask]) ** 2, 1.0e-9)
    )
    return SamplingOutcome(
        inclusion_probability=inclusion_probability,
        sample_mask=sample_mask,
        base_weight=base_weight,
        response_probability=response_probability,
        respondent_mask=respondent_mask,
        calibrated_weight=calibrated_weight,
        design_effect=design_effect,
        metadata={
            "n_strata": int(n_strata),
            "n_clusters": int(n_clusters),
            "strata": strata,
            "clusters": clusters,
        },
    )


__all__ = ["SamplingOutcome", "apply_entity_sampling", "apply_survey_sampling"]

