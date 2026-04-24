"""Survey-design truth targets."""

from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.synthetic_world.operators.sampling import SamplingOutcome


def register_survey_targets(
    *,
    sampling: SamplingOutcome,
    outcome: np.ndarray,
    entity_ids: np.ndarray,
    coord_name: str,
    domain_codes: np.ndarray | None = None,
    domain_name: str = "domain",
    design_variance: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Survey truth for inclusion, response, weights, DEFF, and domain means."""
    ids = np.asarray(entity_ids).tolist()
    targets: dict[str, dict[str, Any]] = {
        "survey.inclusion_probabilities": {
            "values": np.asarray(sampling.inclusion_probability, dtype=float).tolist(),
            "coords": {coord_name: ids},
        },
        "survey.base_weights": {
            "values": np.asarray(sampling.base_weight, dtype=float).tolist(),
            "coords": {coord_name: ids},
        },
        "survey.population_mean": {"value": float(np.mean(np.asarray(outcome, dtype=float)))},
        "survey.population_total": {"value": float(np.sum(np.asarray(outcome, dtype=float)))},
    }
    if sampling.response_probability is not None:
        targets["survey.response_probabilities"] = {
            "values": np.asarray(sampling.response_probability, dtype=float).tolist(),
            "coords": {coord_name: ids},
        }
    if sampling.calibrated_weight is not None:
        targets["survey.calibrated_weights"] = {
            "values": np.asarray(sampling.calibrated_weight, dtype=float).tolist(),
            "coords": {coord_name: ids},
        }
    if sampling.design_effect is not None:
        targets["survey.design_effect"] = {"value": float(sampling.design_effect)}
    if design_variance is not None:
        targets["survey.design_variance"] = {"value": float(design_variance)}
    if domain_codes is not None:
        domains = np.asarray(domain_codes)
        domain_means: dict[str, float] = {}
        for domain in np.unique(domains):
            mask = domains == domain
            domain_means[str(domain)] = float(np.mean(np.asarray(outcome, dtype=float)[mask]))
        targets["survey.domain_means"] = {
            "values": list(domain_means.values()),
            "coords": {domain_name: list(domain_means.keys())},
        }
    return targets


__all__ = ["register_survey_targets"]
