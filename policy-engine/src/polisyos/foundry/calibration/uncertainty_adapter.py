"""Translate calibration Hessian diagnostics into governance-ready envelopes."""

from __future__ import annotations

import math
import numbers
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, SupportsFloat, SupportsIndex

import numpy as np

from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.uncertainty.protocol import UncertaintyDecomposition
from polisyos.foundry.uncertainty.sampling_admission import (
    admit_empirical_weights,
    joint_carrier_digest,
)
from polisyos.ir.analytics import (
    PosteriorSamplesCarrier,
    PosteriorSummaryContext,
    PosteriorSummaryProfileV2,
    posterior_carrier_content_hash,
    posterior_population_std_v2,
    posterior_summary_functionals_v2,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
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
    point = report.calibrated_params.get(param_name)
    if point is None:
        return None

    projection = report.coordinate_projection
    covariance_params: list[str]
    covariance_row: list[float] | None
    non_identifiable: bool
    if projection is not None:
        field_covariance = _projected_field_covariance(report)
        if field_covariance is None or param_name not in projection.field_order:
            return None
        idx = projection.field_order.index(param_name)
        variance = float(field_covariance[idx, idx])
        if not math.isfinite(variance) or variance < 0.0:
            return None
        std = math.sqrt(variance)
        covariance_row = [float(value) for value in field_covariance[idx]]
        covariance_params = list(projection.field_order)
        coordinate_indices = np.flatnonzero(np.asarray(projection.matrix[idx], dtype=float))
        non_identifiable = any(
            unc.params[coordinate_idx] in unc.non_identifiable
            for coordinate_idx in coordinate_indices
            if coordinate_idx < len(unc.params)
        )
    else:
        if report.schema_version != "1.0":
            return None
        if param_name not in unc.params:
            return None
        idx = unc.params.index(param_name)
        if idx >= len(unc.std):
            return None
        std = float(unc.std[idx])
        covariance_row = list(unc.covariance[idx]) if idx < len(unc.covariance) else None
        covariance_params = list(unc.params)
        non_identifiable = param_name in unc.non_identifiable

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
        "non_identifiable": non_identifiable,
        "covariance_row": covariance_row,
        "covariance_params": covariance_params,
        "covariance_source": "calibration_report_projection_v2"
        if projection is not None
        else "calibration_report_v1_identity_key",
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
        schema_version="1.1",
        point_estimate=float(point),
        confidence_interval=(ci_lower, ci_upper),
        confidence_level=None,
        distribution_family=DistributionFamily.NORMAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": float(point), "std": std},
        ),
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
    param_names = (
        report.coordinate_projection.field_order
        if report.coordinate_projection is not None
        else report.calibrated_params
    )
    for param_name in param_names:
        env = envelope_from_calibration_param(
            report,
            param_name,
            confidence_level=confidence_level,
        )
        if env is not None:
            result[param_name] = env
    return result


def _projected_field_covariance(report: CalibrationReport) -> np.ndarray | None:
    """Return ``J Σ Jᵀ`` only when the persisted coordinate basis is complete."""
    projection = report.coordinate_projection
    uncertainty = report.uncertainties
    if projection is None or uncertainty is None:
        return None
    if tuple(uncertainty.params) != projection.coordinate_order:
        return None
    covariance = np.asarray(uncertainty.covariance, dtype=np.float64)
    coordinate_count = len(projection.coordinate_order)
    if covariance.shape != (coordinate_count, coordinate_count):
        return None
    if not np.all(np.isfinite(covariance)):
        return None
    if not np.allclose(covariance, covariance.T, rtol=1e-7, atol=1e-10):
        return None
    jacobian = np.asarray(projection.matrix, dtype=np.float64)
    projected = jacobian @ covariance @ jacobian.T
    if not np.all(np.isfinite(projected)):
        return None
    return 0.5 * (projected + projected.T)


def summarize_bayesian_calibration_posterior(
    posterior_draws: Mapping[str, Sequence[float] | np.ndarray],
    *,
    credible_mass: float = 0.9,
    emulator_diagnostics: Mapping[str, Any] | None = None,
    posterior_diagnostics: Mapping[str, Any] | None = None,
    weights: Sequence[float] | np.ndarray | None = None,
    draw_ids: Sequence[str] | None = None,
    sample_axis: str = "draw",
    context: PosteriorSummaryContext | None = None,
) -> BayesianCalibrationPosteriorSummary:
    """Summarize posterior draws from Bayesian calibration or emulator-assisted inference."""

    if not (0.0 < credible_mass < 1.0):
        raise ValueError("credible_mass must be in (0, 1)")
    if not posterior_draws or not isinstance(sample_axis, str) or not sample_axis.strip():
        raise ValueError("posterior draws and sample axis must be non-empty")
    names = sorted(posterior_draws)
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("posterior parameter names must be non-empty strings")
    if len(names) > 1 and draw_ids is None:
        raise ValueError("posterior joint law requires explicit producer-supplied aligned draw IDs")
    admitted_draws: dict[str, np.ndarray] = {}
    for name in names:
        raw = np.asarray(posterior_draws[name], dtype=object)
        if (
            raw.ndim != 1
            or raw.size == 0
            or any(
                isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real)
                for value in raw
            )
        ):
            raise ValueError("posterior draws require one finite real non-bool row axis")
        draws = np.asarray(raw, dtype=np.float64)
        if not np.all(np.isfinite(draws)) or np.any((raw != 0) & (draws == 0)):
            raise ValueError("posterior draws exceed finite float64 representation")
        # Existing IR CAS canon uses positive zero. Admit that representation
        # before content hashes so fresh readers see the identical finite law.
        admitted_draws[name] = np.where(draws == 0, 0.0, draws)
    count = len(admitted_draws[names[0]])
    if any(len(draws) != count for draws in admitted_draws.values()):
        raise ValueError("posterior coordinates must share an aligned draw axis")
    raw_weights = np.ones(count) if weights is None else np.asarray(weights, dtype=object)
    if any(isinstance(value, (bool, np.bool_)) for value in raw_weights.flat):
        raise ValueError("posterior weights cannot be bool")
    probabilities = tuple(
        0.0 if value == 0 else float(value) for value in admit_empirical_weights(raw_weights, count)
    )
    ids = list(draw_ids) if draw_ids is not None else [f"draw:{i}" for i in range(count)]
    if (
        len(ids) != count
        or len(set(ids)) != count
        or any(not isinstance(value, str) or not value.strip() for value in ids)
    ):
        raise ValueError("posterior draw IDs must be unique aligned non-empty strings")
    if context is None:
        context = PosteriorSummaryContext()
    if set(context.parameters) - set(names):
        raise ValueError("posterior context contains an unmatched parameter binding")

    emulator_info = dict(emulator_diagnostics or {})
    diagnostics = dict(posterior_diagnostics or {})
    posterior_means: dict[str, float] = {}
    credible_intervals: dict[str, tuple[float, float]] = {}
    parameter_envelopes: dict[str, UncertaintyEnvelope] = {}
    decompositions: dict[str, dict[str, Any]] = {}

    noise_map = emulator_info.get("emulator_noise_std", {})
    for param_name in names:
        draws = admitted_draws[param_name]
        point, median, interval = posterior_summary_functionals_v2(
            tuple(float(value) for value in draws), probabilities, credible_mass
        )
        posterior_means[param_name] = point
        credible_intervals[param_name] = interval
        parameter_envelopes[param_name] = UncertaintyEnvelope(
            schema_version="1.1",
            point_estimate=median,
            confidence_interval=interval,
            confidence_level=float(credible_mass),
            distribution_family=DistributionFamily.BAYESIAN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
            sample_size=int(draws.shape[0]),
            gate_eligible=False,
            numeric_policy={"mode": "decimal_exact"},
            distribution_payload=PosteriorSamplesCarrier(
                samples=tuple(float(value) for value in draws),
                weights=probabilities,
                sample_axis=sample_axis,
            ),
            metadata={
                "param_name": param_name,
                "posterior_basis": "posterior_draws",
                "emulator_diagnostics": emulator_info,
                "posterior_diagnostics": diagnostics,
                "point_functional": "median",
                "interval_functional": "equal_tail_inverse_cdf",
            },
        )
        epistemic_std = posterior_population_std_v2(
            tuple(float(value) for value in draws), probabilities
        )
        aleatoric_std = 0.0
        if isinstance(noise_map, Mapping) and param_name in noise_map:
            aleatoric_std = max(float(noise_map[param_name]), 0.0)
        elif np.isscalar(noise_map):
            if not isinstance(noise_map, (str, bytes, SupportsFloat, SupportsIndex)):
                raise TypeError("scalar emulator noise requires a supported float conversion")
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
                "calibration_mode": ("bayesian_emulator" if emulator_info else "bayesian_direct"),
                "epistemic_std_basis": "weighted_finite_corpus_population_spread",
            },
        )
        diagnostic = decomposition.as_dict()
        for component in ("total", "epistemic", "aleatoric"):
            diagnostic[component].update(
                {
                    "gate_eligible": False,
                    "is_heuristic_ci": True,
                    "confidence_level": None,
                    "interval_semantics": IntervalSemantics.HEURISTIC_RANGE,
                    "metadata": {
                        **diagnostic[component]["metadata"],
                        "interval_basis": "gaussian_spread_diagnostic",
                        "requested_credible_mass": float(credible_mass),
                        "posterior_coverage_established": False,
                        "noise_law_established": False,
                    },
                }
            )
        decompositions[param_name] = diagnostic

    joint_digest = joint_carrier_digest(names, parameter_envelopes, ids)
    for name, envelope in parameter_envelopes.items():
        carrier = envelope.distribution_payload
        if not isinstance(carrier, PosteriorSamplesCarrier):
            raise ValueError("posterior summary requires its actual posterior samples carrier")
        profile = PosteriorSummaryProfileV2(
            parameter_name=name,
            parameter_order=tuple(names),
            draw_ids=tuple(ids),
            row_identity_basis="producer_input_order"
            if draw_ids is None
            else "producer_supplied_ids",
            sample_axis=sample_axis,
            probabilities=probabilities,
            posterior_mean=posterior_means[name],
            credible_mass=float(credible_mass),
            carrier_content_hash=posterior_carrier_content_hash(carrier),
            joint_law_sha256=joint_digest,
            binding=context.parameters.get(name),
            context=context,
            context_content_hash=context.content_hash,
        )
        parameter_envelopes[name] = envelope.model_copy(
            update={
                "metadata": {
                    **envelope.metadata,
                    "posterior_summary_profile_required": True,
                    "posterior_summary_profile_id": profile.profile_id,
                    "posterior_summary_profile_version": profile.profile_version,
                    "joint_sample_id": joint_digest,
                    "joint_draw_ids": ids,
                    "joint_parameter_order": names,
                    "joint_law_sha256": joint_digest,
                    "posterior_summary_profile": profile.model_dump(mode="json"),
                }
            }
        )

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
