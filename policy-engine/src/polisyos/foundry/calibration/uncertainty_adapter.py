"""Translate calibration Hessian diagnostics into governance-ready envelopes."""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Mapping, Sequence

import numpy as np

from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.uncertainty.protocol import UncertaintyDecomposition
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _z_score(confidence_level: float) -> float:
    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be in (0, 1)")
    return NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)


@dataclass(frozen=True)
class BayesianCalibrationPosteriorSummary:
    """Summarize posterior-draw based calibration with optional emulator diagnostics."""

    posterior_means: dict[str, float]
    credible_intervals: dict[str, tuple[float, float]]
    parameter_envelopes: dict[str, UncertaintyEnvelope]
    diagnostics: dict[str, Any]
    emulator_diagnostics: dict[str, Any]
    uncertainty_decomposition: dict[str, dict[str, Any]]


def _credible_interval(samples: np.ndarray, *, credible_mass: float) -> tuple[float, float]:
    alpha = max(1e-6, 1.0 - float(credible_mass))
    lower, upper = np.quantile(np.asarray(samples, dtype=float), [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lower), float(upper)


def envelope_from_calibration_param(
    report: CalibrationReport,
    param_name: str,
    *,
    confidence_level: float = 0.95,
) -> UncertaintyEnvelope | None:
    """Build a normal-approximation uncertainty envelope for one calibrated parameter.

    Args:
        report: Calibration report containing point estimates and optional
            `CalibrationUncertainty` diagnostics.
        param_name: Parameter key in `report.calibrated_params`.
        confidence_level: Two-sided confidence level in `(0, 1)`.

    Returns:
        `UncertaintyEnvelope` for the requested parameter, or `None` when the
        report does not contain enough finite uncertainty information.

    Raises:
        ValueError: If `confidence_level` is outside `(0, 1)`.
    """
    if report.uncertainties is None:
        return None

    unc = report.uncertainties
    if param_name not in unc.params:
        return None
    idx = unc.params.index(param_name)
    if idx >= len(unc.std):
        return None

    point = report.calibrated_params.get(param_name)
    if point is None:
        return None

    std = float(unc.std[idx])
    if not math.isfinite(std) or std < 0.0:
        return None
    if not math.isfinite(point):
        return None

    z = _z_score(confidence_level)
    ci_lower = float(point) - z * std
    ci_upper = float(point) + z * std

    metadata: dict[str, object] = {
        "param_name": param_name,
        "std": std,
        "hessian_rank": unc.hessian_rank,
        "hessian_condition": unc.hessian_condition,
        "damping": unc.damping,
        "method": unc.method,
        "non_identifiable": param_name in unc.non_identifiable,
        "covariance_row": list(unc.covariance[idx]) if idx < len(unc.covariance) else None,
        "covariance_params": list(unc.params),
        "interval_basis": "local_gaussian_hessian_approximation",
        "requested_confidence_level": confidence_level,
    }

    if report.identifiability is not None:
        for p in report.identifiability.params:
            if p.name == param_name:
                metadata["identifiability_status"] = p.status.value
                metadata["identifiability_eigenvalue"] = p.eigenvalue
                break

    return UncertaintyEnvelope(
        point_estimate=float(point),
        confidence_interval=(ci_lower, ci_upper),
        confidence_level=None,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        sample_size=None,
        is_heuristic_ci=True,
        gate_eligible=False,
        metadata=metadata,
    )


def envelopes_from_calibration(
    report: CalibrationReport,
    *,
    confidence_level: float = 0.95,
) -> Mapping[str, UncertaintyEnvelope]:
    """Build uncertainty envelopes for every calibrated parameter with usable Hessian stats."""
    result: dict[str, UncertaintyEnvelope] = {}
    for param_name in report.calibrated_params:
        env = envelope_from_calibration_param(
            report,
            param_name,
            confidence_level=confidence_level,
        )
        if env is not None:
            result[param_name] = env
    return result


def summarize_bayesian_calibration_posterior(
    posterior_draws: Mapping[str, Sequence[float] | np.ndarray],
    *,
    credible_mass: float = 0.9,
    emulator_diagnostics: Mapping[str, Any] | None = None,
    posterior_diagnostics: Mapping[str, Any] | None = None,
) -> BayesianCalibrationPosteriorSummary:
    """Summarize posterior draws from Bayesian calibration or emulator-assisted inference."""

    if not (0.0 < credible_mass < 1.0):
        raise ValueError("credible_mass must be in (0, 1)")

    emulator_info = dict(emulator_diagnostics or {})
    diagnostics = dict(posterior_diagnostics or {})
    posterior_means: dict[str, float] = {}
    credible_intervals: dict[str, tuple[float, float]] = {}
    parameter_envelopes: dict[str, UncertaintyEnvelope] = {}
    decompositions: dict[str, dict[str, Any]] = {}

    noise_map = emulator_info.get("emulator_noise_std", {})
    for param_name, values in posterior_draws.items():
        draws = np.asarray(values, dtype=float).reshape(-1)
        if draws.size == 0:
            raise ValueError(f"posterior draws for {param_name!r} must be non-empty")
        if not np.all(np.isfinite(draws)):
            raise ValueError(f"posterior draws for {param_name!r} must be finite")
        point = float(np.mean(draws))
        interval = _credible_interval(draws, credible_mass=credible_mass)
        posterior_means[param_name] = point
        credible_intervals[param_name] = interval
        parameter_envelopes[param_name] = UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=interval,
            confidence_level=float(credible_mass),
            distribution_family=DistributionFamily.BAYESIAN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
            sample_size=int(draws.shape[0]),
            metadata={
                "param_name": param_name,
                "posterior_basis": "posterior_draws",
                "emulator_diagnostics": emulator_info,
                "posterior_diagnostics": diagnostics,
            },
        )
        epistemic_std = float(np.std(draws, ddof=1)) if draws.shape[0] > 1 else 0.0
        aleatoric_std = 0.0
        if isinstance(noise_map, Mapping) and param_name in noise_map:
            aleatoric_std = max(float(noise_map[param_name]), 0.0)
        elif np.isscalar(noise_map):
            aleatoric_std = max(float(noise_map), 0.0)
        decomposition = UncertaintyDecomposition.from_gaussian_components(
            metric_id=param_name,
            point_estimate=point,
            confidence_level=credible_mass,
            epistemic_std=epistemic_std,
            aleatoric_std=aleatoric_std,
            source=UncertaintySource.CALIBRATION,
            distribution_family=DistributionFamily.BAYESIAN,
            propagation_method=PropagationMethod.MONTE_CARLO,
            metadata={
                "calibration_mode": (
                    "bayesian_emulator" if emulator_info else "bayesian_direct"
                ),
            },
        )
        decompositions[param_name] = decomposition.as_dict()

    diagnostics.setdefault("credible_mass", float(credible_mass))
    diagnostics.setdefault("num_parameters", float(len(posterior_means)))
    diagnostics.setdefault(
        "calibration_mode",
        "bayesian_emulator" if emulator_info else "bayesian_direct",
    )

    return BayesianCalibrationPosteriorSummary(
        posterior_means=posterior_means,
        credible_intervals=credible_intervals,
        parameter_envelopes=parameter_envelopes,
        diagnostics=diagnostics,
        emulator_diagnostics=emulator_info,
        uncertainty_decomposition=decompositions,
    )


__all__ = [
    "BayesianCalibrationPosteriorSummary",
    "envelope_from_calibration_param",
    "envelopes_from_calibration",
    "summarize_bayesian_calibration_posterior",
]
