"""Bayesian truth targets."""
from __future__ import annotations

from typing import Any

import numpy as np


def register_prior_targets(
    *,
    parameter_names: list[str],
    prior_mean: np.ndarray,
    prior_covariance: np.ndarray,
    predictive_mean: np.ndarray | None = None,
    predictive_std: np.ndarray | None = None,
    coord_name: str | None = None,
    entity_ids: np.ndarray | None = None,
) -> dict[str, dict[str, Any]]:
    """Bayesian prior and prior-predictive targets."""
    mean = np.asarray(prior_mean, dtype=float)
    covariance = np.asarray(prior_covariance, dtype=float)
    targets: dict[str, dict[str, Any]] = {
        "bayesian.prior_params": {
            "prior_mean": {name: float(mean[idx]) for idx, name in enumerate(parameter_names)},
            "prior_covariance": covariance.tolist(),
        }
    }
    if predictive_mean is not None:
        predictive_payload: dict[str, Any] = {
            "mean": np.asarray(predictive_mean, dtype=float).tolist(),
            "std": (
                np.asarray(predictive_std, dtype=float).tolist()
                if predictive_std is not None
                else np.zeros_like(np.asarray(predictive_mean, dtype=float)).tolist()
            ),
        }
        if coord_name is not None and entity_ids is not None:
            predictive_payload["coords"] = {coord_name: np.asarray(entity_ids).tolist()}
        targets["bayesian.prior_predictive"] = predictive_payload
    return targets


def exact_linear_regression_posterior(
    *,
    design: np.ndarray,
    outcome: np.ndarray,
    noise_scale: float,
    coefficient_names: list[str],
    prior_scale: float = 5.0,
) -> dict[str, Any]:
    """Closed-form Gaussian posterior for a linear regression truth target."""
    x = np.asarray(design, dtype=float)
    y = np.asarray(outcome, dtype=float)
    sigma2 = float(noise_scale) ** 2
    prior_precision = np.eye(x.shape[1], dtype=float) / (prior_scale**2)
    posterior_precision = prior_precision + (x.T @ x) / sigma2
    posterior_covariance = np.linalg.inv(posterior_precision)
    posterior_mean = posterior_covariance @ (x.T @ y / sigma2)
    return {
        "policy": "exact_posterior",
        "posterior_mean": {
            name: float(posterior_mean[idx]) for idx, name in enumerate(coefficient_names)
        },
        "posterior_covariance": posterior_covariance.tolist(),
        "noise_scale": float(noise_scale),
        "prior_scale": float(prior_scale),
    }


def reference_posterior_summary(
    *,
    parameter_names: list[str],
    point_estimates: np.ndarray,
    covariance: np.ndarray,
    predictive_mean: np.ndarray | None = None,
    predictive_std: np.ndarray | None = None,
) -> dict[str, Any]:
    """Reference-posterior summary for realistic nonconjugate or dynamic worlds."""
    mean = np.asarray(point_estimates, dtype=float)
    cov = np.asarray(covariance, dtype=float)
    payload: dict[str, Any] = {
        "policy": "reference_posterior",
        "posterior_mean": {
            name: float(mean[idx]) for idx, name in enumerate(parameter_names)
        },
        "posterior_covariance": cov.tolist(),
    }
    if predictive_mean is not None:
        payload["posterior_predictive_mean"] = np.asarray(predictive_mean, dtype=float).tolist()
    if predictive_std is not None:
        payload["posterior_predictive_std"] = np.asarray(predictive_std, dtype=float).tolist()
    return payload


def register_reference_posterior_targets(
    *,
    parameter_names: list[str],
    point_estimates: np.ndarray,
    covariance: np.ndarray,
    predictive_mean: np.ndarray | None = None,
    predictive_std: np.ndarray | None = None,
    coord_name: str | None = None,
    entity_ids: np.ndarray | None = None,
    log_evidence: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Canonical reference-posterior targets with backward-compatible aliases."""
    summary = reference_posterior_summary(
        parameter_names=parameter_names,
        point_estimates=point_estimates,
        covariance=covariance,
        predictive_mean=predictive_mean,
        predictive_std=predictive_std,
    )
    targets: dict[str, dict[str, Any]] = {
        "bayesian.reference_posterior": summary,
        "bayesian.posterior_reference": dict(summary),
    }
    if predictive_mean is not None:
        predictive_payload: dict[str, Any] = {
            "mean": np.asarray(predictive_mean, dtype=float).tolist(),
            "std": (
                np.asarray(predictive_std, dtype=float).tolist()
                if predictive_std is not None
                else np.zeros_like(np.asarray(predictive_mean, dtype=float)).tolist()
            ),
        }
        if coord_name is not None and entity_ids is not None:
            predictive_payload["coords"] = {coord_name: np.asarray(entity_ids).tolist()}
        targets["bayesian.posterior_predictive_reference"] = predictive_payload
    if log_evidence is not None:
        targets["bayesian.log_evidence_reference"] = {"value": float(log_evidence)}
    return targets


def register_latent_state_targets(
    *,
    state_values: np.ndarray,
    coord_name: str,
    entity_ids: np.ndarray,
    extras: dict[str, list[Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Expose latent states to truth-aware Bayesian workflows."""
    coords: dict[str, Any] = {coord_name: np.asarray(entity_ids).tolist()}
    if extras:
        coords.update({str(key): list(value) for key, value in extras.items()})
    return {
        "bayesian.latent_states_true": {
            "values": np.asarray(state_values, dtype=float).tolist(),
            "coords": coords,
        }
    }


__all__ = [
    "exact_linear_regression_posterior",
    "reference_posterior_summary",
    "register_latent_state_targets",
    "register_prior_targets",
    "register_reference_posterior_targets",
]
