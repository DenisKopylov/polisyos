"""Translate calibration Hessian diagnostics into governance-ready envelopes."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from statistics import NormalDist
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ensure_ir_artifact_store, resolve_manifest_by_profile
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.uncertainty.protocol import PropagationResult, UncertaintyDecomposition
from polisyos.ir.analytics.posterior_summary import (
    PosteriorPointRole,
    PosteriorSummaryRef,
    PosteriorSummaryV11,
    load_posterior_summary,
    persist_posterior_summary,
    summarize_posterior_draw_artifact,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel

if TYPE_CHECKING:
    from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator


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
    posterior_draw_context: BayesianCalibrationDrawContextCandidate | None = None
    parameter_envelope_limitations: dict[str, BayesianCalibrationEnvelopeLimitation] = field(
        default_factory=dict
    )
    credible_mass: float = 0.9
    persisted_candidate_ref: _BayesianCalibrationSummaryCandidateRef | None = None


class BayesianCalibrationEnvelopeLimitation(StrEnum):
    """Explain why a posterior summary cannot be represented by an envelope."""

    POINT_OUTSIDE_CREDIBLE_INTERVAL = "point_outside_credible_interval"


class BayesianCalibrationDrawContextCandidate(BaseModel):
    """Retain caller-provided posterior columns without asserting a joint sampling law.

    A row matrix is included when columns have equal lengths so the original positional
    arrangement remains inspectable. Equal lengths and positional order do not establish that
    the columns are jointly sampled or share a source identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_order: tuple[str, ...] = Field(min_length=1)
    samples_by_parameter: dict[str, PosteriorSamplesCarrier]
    input_shapes: dict[str, tuple[int, ...]]
    row_matrix: tuple[tuple[float, ...], ...] | None = None
    row_relation_status: Literal["not_established"] = "not_established"
    source_binding_status: Literal["caller_input_only"] = "caller_input_only"
    joint_sampling_eligible: Literal[False] = False

    @model_validator(mode="after")
    def _validate_positional_context(self) -> BayesianCalibrationDrawContextCandidate:
        if (
            self.parameter_order != tuple(self.samples_by_parameter)
            or self.parameter_order != tuple(self.input_shapes)
            or any(not name.strip() for name in self.parameter_order)
        ):
            raise ValueError("posterior draw context order must match its sample columns")
        if any(
            any(size < 0 for size in self.input_shapes[name])
            or math.prod(self.input_shapes[name]) != len(self.samples_by_parameter[name].samples)
            for name in self.parameter_order
        ):
            raise ValueError("posterior draw context shapes must match their sample columns")
        sample_counts = {len(carrier.samples) for carrier in self.samples_by_parameter.values()}
        if len(sample_counts) == 1:
            sample_count = next(iter(sample_counts))
            expected_rows = tuple(
                tuple(self.samples_by_parameter[name].samples[row] for name in self.parameter_order)
                for row in range(sample_count)
            )
            if self.row_matrix != expected_rows:
                raise ValueError("posterior draw context row matrix must match its columns")
        elif self.row_matrix is not None:
            raise ValueError("posterior draw context cannot align columns with unequal lengths")
        return self


class _BayesianCalibrationSummaryCandidateV1(BaseModel):
    """Store legacy summary statistics and caller rows without asserting their source law."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    point_role: Literal["posterior_mean"] = "posterior_mean"
    interval_method: Literal["numpy_quantile_linear"] = "numpy_quantile_linear"
    credible_mass: float = Field(gt=0.0, lt=1.0)
    posterior_means: dict[str, float]
    credible_intervals: dict[str, tuple[float, float]]
    parameter_envelopes: dict[str, UncertaintyEnvelope]
    diagnostics: dict[str, Any]
    emulator_diagnostics: dict[str, Any]
    posterior_draw_context: BayesianCalibrationDrawContextCandidate
    parameter_envelope_limitations: dict[str, BayesianCalibrationEnvelopeLimitation]
    source_binding_status: Literal["caller_input_only"] = "caller_input_only"
    row_relation_status: Literal["not_established"] = "not_established"
    unit_binding_status: Literal["not_established"] = "not_established"
    gate_eligible: Literal[False] = False

    @model_validator(mode="after")
    def _validate_candidate_summary(self) -> _BayesianCalibrationSummaryCandidateV1:
        names = set(self.posterior_means)
        envelope_names = set(self.parameter_envelopes)
        limitation_names = set(self.parameter_envelope_limitations)
        if (
            not names
            or names != set(self.credible_intervals)
            or names != set(self.posterior_draw_context.parameter_order)
            or envelope_names | limitation_names != names
            or envelope_names & limitation_names
        ):
            raise ValueError("posterior candidate fields must cover the same parameters")
        for name, (lower, upper) in self.credible_intervals.items():
            point = self.posterior_means[name]
            if (
                not math.isfinite(point)
                or not math.isfinite(lower)
                or not math.isfinite(upper)
                or lower > upper
            ):
                raise ValueError("candidate summary statistics must be finite and ordered")
            if name in self.parameter_envelope_limitations:
                if lower <= point <= upper:
                    raise ValueError("envelope limitation requires a point outside its interval")
                continue
            envelope = self.parameter_envelopes[name]
            carrier = self.posterior_draw_context.samples_by_parameter[name]
            if (
                not lower <= point <= upper
                or envelope.point_estimate != point
                or envelope.confidence_interval != (lower, upper)
                or envelope.distribution_payload != carrier
                or envelope.sample_size != len(carrier.samples)
            ):
                raise ValueError("representable envelope must retain its exact summary and draws")
        if any(envelope.gate_eligible for envelope in self.parameter_envelopes.values()):
            raise ValueError("caller-input candidate cannot retain a gate-eligible envelope")
        return self


class _BayesianCalibrationSummaryCandidateRef(ArtifactRefModel):
    """Reference the internal caller-input-only legacy summary candidate artifact."""

    kind: Literal["foundry.calibration.bayesian_posterior_summary_candidate"] = (
        "foundry.calibration.bayesian_posterior_summary_candidate"
    )
    media_type: Literal["application/json"] = "application/json"


@dataclass(frozen=True)
class BayesianCalibrationCandidateConsumption:
    """Describe a limited or evaluated read of a persisted caller-input candidate."""

    candidate: _BayesianCalibrationSummaryCandidateV1
    status: Literal["evaluated", "consumer_refused", "limited"]
    results: tuple[PropagationResult, ...]
    refusal_reason: str | None = None


def _credible_interval(samples: np.ndarray, *, credible_mass: float) -> tuple[float, float]:
    alpha = max(1e-6, 1.0 - float(credible_mass))
    lower, upper = np.quantile(
        np.asarray(samples, dtype=float),
        [alpha / 2.0, 1.0 - alpha / 2.0],
        method="linear",
    )
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
    candidate_store: ArtifactStore | None = None,
) -> BayesianCalibrationPosteriorSummary:
    """Summarize Bayesian calibration draws and optionally persist their candidate context.

    ``candidate_store`` requests a caller-input-only CAS artifact for the complete summary. This
    retains legacy statistics and the positional draw context without asserting a joint sampling
    law or manufacturing an ``UncertaintyEnvelope`` for an unrepresentable parameter.
    """

    if not (0.0 < credible_mass < 1.0):
        raise ValueError("credible_mass must be in (0, 1)")

    emulator_info = dict(emulator_diagnostics or {})
    diagnostics = dict(posterior_diagnostics or {})
    posterior_means: dict[str, float] = {}
    credible_intervals: dict[str, tuple[float, float]] = {}
    parameter_envelopes: dict[str, UncertaintyEnvelope] = {}
    decompositions: dict[str, dict[str, Any]] = {}
    sample_carriers: dict[str, PosteriorSamplesCarrier] = {}
    input_shapes: dict[str, tuple[int, ...]] = {}
    envelope_limitations: dict[str, BayesianCalibrationEnvelopeLimitation] = {}

    noise_map = emulator_info.get("emulator_noise_std", {})
    for param_name, values in posterior_draws.items():
        source_draws = np.asarray(values, dtype=float)
        input_shapes[param_name] = tuple(int(size) for size in source_draws.shape)
        draws = source_draws.reshape(-1)
        if draws.size == 0:
            raise ValueError(f"posterior draws for {param_name!r} must be non-empty")
        if not np.all(np.isfinite(draws)):
            raise ValueError(f"posterior draws for {param_name!r} must be finite")
        point = float(np.mean(draws))
        interval = _credible_interval(draws, credible_mass=credible_mass)
        posterior_means[param_name] = point
        credible_intervals[param_name] = interval
        carrier = PosteriorSamplesCarrier(samples=tuple(float(value) for value in draws))
        sample_carriers[param_name] = carrier
        if interval[0] <= point <= interval[1]:
            parameter_envelopes[param_name] = UncertaintyEnvelope(
                numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
                point_estimate=point,
                confidence_interval=interval,
                confidence_level=float(credible_mass),
                distribution_family=DistributionFamily.BAYESIAN,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.MONTE_CARLO,
                interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
                distribution_payload=carrier,
                sample_size=int(draws.shape[0]),
                gate_eligible=False,
                metadata={
                    "param_name": param_name,
                    "posterior_basis": "posterior_draws",
                    "sample_binding_status": "caller_input_only",
                    "joint_sampling_eligible": False,
                    "emulator_diagnostics": emulator_info,
                    "posterior_diagnostics": diagnostics,
                },
            )
        else:
            envelope_limitations[param_name] = (
                BayesianCalibrationEnvelopeLimitation.POINT_OUTSIDE_CREDIBLE_INTERVAL
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
                "calibration_mode": ("bayesian_emulator" if emulator_info else "bayesian_direct"),
            },
        )
        decompositions[param_name] = decomposition.as_dict()

    diagnostics.setdefault("credible_mass", float(credible_mass))
    diagnostics.setdefault("num_parameters", float(len(posterior_means)))
    diagnostics.setdefault(
        "calibration_mode",
        "bayesian_emulator" if emulator_info else "bayesian_direct",
    )
    if envelope_limitations:
        diagnostics["parameter_envelope_limitations"] = {
            name: limitation.value for name, limitation in envelope_limitations.items()
        }

    draw_context = None
    if sample_carriers:
        sample_counts = {len(carrier.samples) for carrier in sample_carriers.values()}
        row_matrix = None
        if len(sample_counts) == 1:
            sample_count = next(iter(sample_counts))
            parameter_order = tuple(sample_carriers)
            row_matrix = tuple(
                tuple(sample_carriers[name].samples[row] for name in parameter_order)
                for row in range(sample_count)
            )
        else:
            parameter_order = tuple(sample_carriers)
        draw_context = BayesianCalibrationDrawContextCandidate(
            parameter_order=parameter_order,
            samples_by_parameter=sample_carriers,
            input_shapes=input_shapes,
            row_matrix=row_matrix,
        )

    summary = BayesianCalibrationPosteriorSummary(
        posterior_means=posterior_means,
        credible_intervals=credible_intervals,
        parameter_envelopes=parameter_envelopes,
        diagnostics=diagnostics,
        emulator_diagnostics=emulator_info,
        uncertainty_decomposition=decompositions,
        posterior_draw_context=draw_context,
        parameter_envelope_limitations=envelope_limitations,
        credible_mass=float(credible_mass),
    )
    if candidate_store is not None and draw_context is not None:
        summary = replace(
            summary,
            persisted_candidate_ref=_persist_bayesian_calibration_summary_candidate(
                candidate_store,
                summary,
            ),
        )
    return summary


def _bayesian_calibration_summary_candidate_payload(
    summary: BayesianCalibrationPosteriorSummary,
) -> _BayesianCalibrationSummaryCandidateV1:
    """Validate a legacy summary for caller-input-only candidate persistence."""
    if summary.posterior_draw_context is None:
        raise ValueError("posterior summary has no retained draw context")
    return _BayesianCalibrationSummaryCandidateV1.model_validate(
        {
            "credible_mass": summary.credible_mass,
            "point_role": "posterior_mean",
            "interval_method": "numpy_quantile_linear",
            "posterior_means": summary.posterior_means,
            "credible_intervals": summary.credible_intervals,
            "parameter_envelopes": summary.parameter_envelopes,
            "diagnostics": summary.diagnostics,
            "emulator_diagnostics": summary.emulator_diagnostics,
            "posterior_draw_context": summary.posterior_draw_context,
            "parameter_envelope_limitations": summary.parameter_envelope_limitations,
            "source_binding_status": "caller_input_only",
            "row_relation_status": "not_established",
            "unit_binding_status": "not_established",
            "gate_eligible": False,
        }
    )


def _persist_bayesian_calibration_summary_candidate(
    store: ArtifactStore,
    summary: BayesianCalibrationPosteriorSummary,
) -> _BayesianCalibrationSummaryCandidateRef:
    """Persist the exact legacy output and its caller-input draw context as a candidate.

    The artifact preserves the existing NumPy quantile, mean, and envelope-limitation
    semantics. It does not bind the caller arrays to a method execution or assert that
    equal-length columns are jointly sampled.
    """
    candidate = _bayesian_calibration_summary_candidate_payload(summary)
    ref = put_json_artifact(
        ensure_ir_artifact_store(store),
        candidate.model_dump(mode="python", round_trip=True),
        kind="foundry.calibration.bayesian_posterior_summary_candidate",
        schema_name="polisyos.foundry.calibration.BayesianCalibrationSummaryCandidate",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return _BayesianCalibrationSummaryCandidateRef.model_validate(ref)


def _load_bayesian_calibration_summary_candidate(
    store: ArtifactStore,
    ref: _BayesianCalibrationSummaryCandidateRef,
) -> _BayesianCalibrationSummaryCandidateV1:
    """Fresh-read and recompute a caller-input-only posterior summary candidate."""
    candidate = _BayesianCalibrationSummaryCandidateV1.model_validate(
        get_json_artifact(ensure_ir_artifact_store(store), ref)
    )
    context = candidate.posterior_draw_context
    draws_by_parameter = {
        name: np.asarray(context.samples_by_parameter[name].samples, dtype=float).reshape(
            context.input_shapes[name]
        )
        for name in context.parameter_order
    }
    recomputed = summarize_bayesian_calibration_posterior(
        draws_by_parameter,
        credible_mass=candidate.credible_mass,
        emulator_diagnostics=candidate.emulator_diagnostics,
        posterior_diagnostics=candidate.diagnostics,
    )
    if _bayesian_calibration_summary_candidate_payload(recomputed).model_dump(
        mode="json"
    ) != candidate.model_dump(mode="json"):
        raise ValueError("persisted summary does not match its retained draw context")
    return candidate


def consume_persisted_bayesian_calibration_candidate(
    store: ArtifactStore,
    ref: _BayesianCalibrationSummaryCandidateRef,
    *,
    simulation_fn: Callable[..., Mapping[str, float]],
    nominal_params: Mapping[str, float],
    output_metric_ids: list[str],
    propagator: MonteCarloPropagator | None = None,
) -> BayesianCalibrationCandidateConsumption:
    """Fresh-read a candidate and route representable envelopes to legacy Monte Carlo.

    Off-interval parameters return a typed limitation with the persisted mean, interval, and
    draws intact. Representable single-parameter candidates use their existing sample carrier.
    Multi-parameter candidates still pass through the ordinary consumer, which refuses the
    caller-declared row relation unless a source-bound joint law exists.
    """
    candidate = _load_bayesian_calibration_summary_candidate(store, ref)
    if candidate.parameter_envelope_limitations:
        return BayesianCalibrationCandidateConsumption(
            candidate=candidate,
            status="limited",
            results=(),
            refusal_reason="parameter_envelope_unavailable",
        )

    if propagator is None:
        from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator

        propagator = MonteCarloPropagator()
    results = tuple(
        propagator.propagate(
            simulation_fn,
            nominal_params,
            candidate.parameter_envelopes,
            output_metric_ids,
        )
    )
    refusal_reason = next(
        (
            str(result.envelope.metadata["failure"])
            for result in results
            if "failure" in result.envelope.metadata
        ),
        None,
    )
    return BayesianCalibrationCandidateConsumption(
        candidate=candidate,
        status="consumer_refused" if refusal_reason else "evaluated",
        results=results,
        refusal_reason=refusal_reason,
    )


def _posterior_draw_source_from_method_evidence(
    store: ArtifactStore,
    evidence_ref: ArtifactRef,
) -> tuple[Mapping[str, Any], str, str, float]:
    """Resolve the producer-selected result view and bind its native draws to evidence."""
    if (
        evidence_ref.kind != "scientist.method_evidence"
        or evidence_ref.media_type != "application/json"
    ):
        raise ValueError("posterior summary requires a scientist.method_evidence JSON artifact")
    ir_store = ensure_ir_artifact_store(store)
    evidence = get_json_artifact(ir_store, evidence_ref)
    if not isinstance(evidence, Mapping):
        raise ValueError("method evidence payload is malformed")
    denied_uses = evidence.get("may_not_use_for")
    if (
        evidence.get("authority_purpose") != "method_execution"
        or evidence.get("backend") != "bayesian"
        or not isinstance(denied_uses, list)
        or not {"governance_admissibility", "method_validity"}.issubset(denied_uses)
    ):
        raise ValueError("method evidence does not carry the expected non-authority boundary")

    result_id = evidence.get("result_ref")
    raw_result_ref = evidence.get("method_result_ref")
    if not isinstance(result_id, str) or not result_id:
        raise ValueError("method evidence has no method-result reference")
    if not isinstance(raw_result_ref, Mapping):
        raise ValueError("method evidence has no producer-issued method-result view")
    try:
        result_ref = ArtifactRef.model_validate(raw_result_ref)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "method evidence has an invalid producer-issued method-result view"
        ) from exc
    if str(result_ref.artifact_id) != result_id:
        raise ValueError("method evidence method-result ID does not match its producer-issued view")
    evidence_manifest = store.get_manifest(evidence_ref)
    result_edges = [
        edge
        for edge in evidence_manifest.inputs
        if edge.role == "method_result" and str(edge.artifact_id) == result_id
    ]
    if (
        len(result_edges) != 1
        or result_edges[0].manifest_profile_sha256 != result_ref.manifest_profile_sha256
    ):
        raise ValueError("method evidence does not bind the producer-issued method-result view")
    result = get_json_artifact(ir_store, result_ref)
    if not isinstance(result, Mapping) or not isinstance(result.get("result"), Mapping):
        raise ValueError("persisted method result has no posterior result record")
    posterior_result = result["result"]

    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("method evidence has no artifact map")
    draws = artifacts.get("posterior_draws")
    if not isinstance(draws, Mapping):
        raise ValueError("method evidence has no persisted posterior draw payload")
    artifact_ref = draws.get("artifact_ref")
    artifact_hash = draws.get("artifact_hash")
    artifact_payload = draws.get("payload")
    if (
        not isinstance(artifact_ref, str)
        or not isinstance(artifact_hash, str)
        or not isinstance(artifact_payload, Mapping)
    ):
        raise ValueError("persisted posterior draw source is incomplete")
    if (
        posterior_result.get("sampler_family") != "mcmc"
        or posterior_result.get("draws_ref") != artifact_ref
        or posterior_result.get("sampler_kernel") != artifact_payload.get("sampler_kernel")
        or posterior_result.get("method_name") != artifact_payload.get("method_name")
    ):
        raise ValueError("method result and posterior draw source do not match")
    diagnostics = posterior_result.get("diagnostics")
    credible_mass = diagnostics.get("credible_mass") if isinstance(diagnostics, Mapping) else None
    if (
        isinstance(credible_mass, bool)
        or not isinstance(credible_mass, (int, float))
        or not math.isfinite(float(credible_mass))
        or not 0.0 < float(credible_mass) < 1.0
    ):
        raise ValueError("persisted method result has no valid credible_mass diagnostic")
    return artifact_payload, artifact_ref, artifact_hash, float(credible_mass)


def persist_posterior_summary_from_method_evidence(
    store: ArtifactStore,
    evidence_ref: ArtifactRef,
    *,
    credible_mass: float | None = None,
    point_role: PosteriorPointRole,
) -> PosteriorSummaryRef:
    """Build and persist a candidate v1.1 summary from native stored MCMC evidence.

    The method-execution evidence identifies a data source and disclaims
    method-validity and governance authority. The resulting summary therefore
    stays gate-ineligible and retains any missing unit binding as unknown.
    """
    artifact_payload, artifact_ref, artifact_hash, source_credible_mass = (
        _posterior_draw_source_from_method_evidence(store, evidence_ref)
    )
    if credible_mass is not None and credible_mass != source_credible_mass:
        raise ValueError("credible_mass must match the persisted method result diagnostic")
    summary = summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=artifact_payload,
        artifact_hash=artifact_hash,
        credible_mass=source_credible_mass,
        point_role=point_role,
    )
    return persist_posterior_summary(
        ensure_ir_artifact_store(store),
        summary,
        source_method_evidence_ref=evidence_ref,
    )


def load_persisted_posterior_summary(
    store: ArtifactStore,
    summary_ref: PosteriorSummaryRef,
) -> PosteriorSummaryV11:
    """Fresh-read a summary and recompute it from its source method-evidence artifact."""
    ir_store = ensure_ir_artifact_store(store)
    summary = load_posterior_summary(ir_store, summary_ref)
    source_ref = ArtifactRef.model_validate(
        summary.source_method_evidence_ref.model_dump(mode="python")
        if summary.source_method_evidence_ref is not None
        else {}
    )
    artifact_payload, artifact_ref, artifact_hash, source_credible_mass = (
        _posterior_draw_source_from_method_evidence(store, source_ref)
    )
    recomputed = summarize_posterior_draw_artifact(
        artifact_ref=artifact_ref,
        artifact_payload=artifact_payload,
        artifact_hash=artifact_hash,
        credible_mass=source_credible_mass,
        point_role=summary.point_role,
        source_method_evidence_ref=summary.source_method_evidence_ref,
    )
    if recomputed != summary:
        raise ValueError("posterior summary does not match its persisted method-evidence source")

    if summary_ref.manifest_profile_sha256 is None:
        summary_manifest = store.get_manifest(summary_ref.artifact_id)
    else:
        summary_manifest = resolve_manifest_by_profile(
            ir_store,
            summary_ref.artifact_id,
            summary_ref.manifest_profile_sha256,
        )
    source_edges = [edge for edge in summary_manifest.inputs if edge.role == "method_evidence"]
    if (
        len(source_edges) != 1
        or str(source_edges[0].artifact_id) != str(source_ref.artifact_id)
        or source_edges[0].manifest_profile_sha256 != source_ref.manifest_profile_sha256
    ):
        raise ValueError(
            "posterior summary manifest does not bind the selected method-evidence view"
        )
    return summary


__all__ = [
    "BayesianCalibrationDrawContextCandidate",
    "BayesianCalibrationEnvelopeLimitation",
    "BayesianCalibrationPosteriorSummary",
    "envelope_from_calibration_param",
    "envelopes_from_calibration",
    "summarize_bayesian_calibration_posterior",
]
