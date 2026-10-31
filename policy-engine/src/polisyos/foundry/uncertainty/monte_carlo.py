"""Public uncertainty monte carlo module API."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from numbers import Real
from typing import Any, Literal

import jax
import jax.numpy as jnp
import jax.random as jrandom
import jaxlib
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.logger import get_logger
from polisyos.ir import (
    ArtifactRefModel,
    PosteriorPointRole,
    PosteriorSummaryV11,
    summarize_posterior_draw_artifact,
)
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    CompositionProvenance,
    CompositionStep,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    build_composition_provenance,
)

from .config import PropagationConfig
from .covariance import (
    _COVARIANCE_DIAGONAL_ATOL,
    _COVARIANCE_DIAGONAL_RTOL,
    _COVARIANCE_VALIDATION_DTYPE,
    _SINGULAR_PSD_SCALE_RTOL,
    _SINGULAR_SYMMETRY_ATOL,
    _SINGULAR_SYMMETRY_RTOL,
    _real_float64,
    build_covariance_matrix,
    extract_std,
    has_unknown_dependency,
    joint_dependency_assurance,
)
from .evaluation_failures import classify_evaluation_failure
from .protocol import PropagationResult, _validate_effective_inputs

logger = get_logger(__name__)

_MAX_EVALUATION_ATTEMPTS = 2
_QMC_GAUSSIAN_UNIFORM_CLIP = 1e-10


@dataclass
class _EvaluationAttempts:
    """Count physical evaluator calls separately from logical input draws."""

    simulation_attempt_count: int = 0
    retry_attempt_count: int = 0


def _evaluate_with_transient_retry(
    simulation_fn: Callable[..., Any],
    params: Mapping[str, Any],
    attempts: _EvaluationAttempts,
) -> Any:
    """Retry one unchanged evaluation input once after an explicit transient error."""
    for attempt_index in range(_MAX_EVALUATION_ATTEMPTS):
        attempts.simulation_attempt_count += 1
        try:
            return simulation_fn(**params)
        except Exception as exc:
            if (
                attempt_index + 1 < _MAX_EVALUATION_ATTEMPTS
                and classify_evaluation_failure(exc).scope == "transient"
            ):
                attempts.retry_attempt_count += 1
                continue
            raise
    raise AssertionError("bounded evaluation loop returned without a result or exception")


def _is_legacy_draw_local_runtime_error(
    exc: BaseException,
    chain_complete: bool,
    cycle_detected: bool,
) -> bool:
    """Keep direct RuntimeError solver refusals as candidate draw failures.

    This narrow legacy case is the only unknown failure treated as draw-local.
    Wrapped errors, incomplete exception graphs, and other exception types do
    not establish a sampled-input limitation and therefore fail closed.
    """
    return (
        type(exc) is RuntimeError
        and exc.__cause__ is None
        and exc.__context__ is None
        and chain_complete
        and not cycle_detected
    )


@dataclass(frozen=True)
class _SampleBuffers:
    values: dict[str, np.ndarray]
    input_samples: dict[str, np.ndarray]
    capacity: int


@dataclass(frozen=True)
class _QMCExecutionSummary:
    method: str
    scrambled: bool
    replicate_count: int


@dataclass(frozen=True)
class _GaussianJointSpec:
    """One numerically validated, producer-declared Gaussian joint law."""

    means: np.ndarray
    factor: np.ndarray
    covariance_storage_dtype: str


@dataclass
class _GaussianExecutionTrace:
    """Record actual numeric batches for the declared Gaussian transform."""

    batches: list[dict[str, Any]]


@dataclass(frozen=True)
class _EmpiricalJointSpec:
    """Describe an aligned empirical law shared by input carriers."""

    names: tuple[str, ...]
    sample_axis: str
    sample_count: int
    samples: Mapping[str, np.ndarray]
    probabilities: np.ndarray
    joint_sample_id: str | None


class _DrawOutcomeCode(StrEnum):
    """Typed outcome classes for a Monte Carlo draw/output pair."""

    SIMULATION_EXCEPTION = "simulation_exception"
    INVALID_RESPONSE = "invalid_response"
    MISSING_OUTPUT = "missing_output"
    NON_NUMERIC_OUTPUT = "non_numeric_output"
    NON_FINITE_OUTPUT = "non_finite_output"


class _DrawOutputOutcome(BaseModel):
    """Describe one unavailable output within a sampled draw."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    output_metric_id: str = Field(min_length=1)
    outcome_code: _DrawOutcomeCode
    error_type: str | None = None


class _DrawOutcomeRecord(BaseModel):
    """Bind all unavailable outputs for one draw to its sampled inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draw_index: int = Field(ge=0)
    sampled_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_outcomes: tuple[_DrawOutputOutcome, ...] = Field(min_length=1)


class PosteriorPushforwardOutcomeCode(StrEnum):
    """Typed reasons one posterior draw did not produce a finite metric."""

    SIMULATION_EXCEPTION = "simulation_exception"
    INVALID_RESPONSE = "invalid_response"
    MISSING_OUTPUT = "missing_output"
    NON_NUMERIC_OUTPUT = "non_numeric_output"
    NON_FINITE_OUTPUT = "non_finite_output"


def _posterior_joint_matrix_digest(
    *,
    source_draws_ref: str,
    source_draws_hash: str,
    point_role: PosteriorPointRole,
    chain_count: int,
    draws_per_chain: int,
    parameter_names: tuple[str, ...],
    draw_order: tuple[int, ...],
    rows: tuple[tuple[float, ...], ...],
) -> str:
    """Bind selected source rows and their interpretation into one digest."""
    payload = {
        "profile_version": "1.1",
        "source_draws_ref": source_draws_ref,
        "source_draws_hash": source_draws_hash,
        "point_role": point_role.value,
        "chain_count": chain_count,
        "draws_per_chain": draws_per_chain,
        "parameter_names": list(parameter_names),
        "draw_order": list(draw_order),
        "rows": [list(row) for row in rows],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _posterior_empirical_quantile(values: tuple[float, ...], level: float) -> float:
    """Return the left-continuous inverse empirical CDF at one probability."""
    ordered = np.sort(np.asarray(values, dtype=np.float64), kind="stable")
    cumulative = np.arange(1, len(ordered) + 1, dtype=np.float64) / len(ordered)
    index = min(int(np.searchsorted(cumulative, level, side="left")), len(ordered) - 1)
    return float(ordered[index])


class PosteriorJointInputMatrix(BaseModel):
    """Content-bind the exact selected parameter rows consumed by Monte Carlo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_version: Literal["1.1"] = "1.1"
    source_draws_ref: str = Field(min_length=1)
    source_draws_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    point_role: PosteriorPointRole
    chain_count: int = Field(ge=1)
    draws_per_chain: int = Field(ge=1)
    parameter_names: tuple[str, ...] = Field(min_length=1)
    draw_order: tuple[int, ...] = Field(min_length=1)
    rows: tuple[tuple[float, ...], ...] = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_matrix_binding(self) -> PosteriorJointInputMatrix:
        if (
            len(set(self.parameter_names)) != len(self.parameter_names)
            or self.draw_order != tuple(range(len(self.rows)))
            or self.chain_count * self.draws_per_chain != len(self.rows)
            or any(len(row) != len(self.parameter_names) for row in self.rows)
            or any(not math.isfinite(value) for row in self.rows for value in row)
        ):
            raise ValueError("posterior joint input matrix has inconsistent axes")
        expected = _posterior_joint_matrix_digest(
            source_draws_ref=self.source_draws_ref,
            source_draws_hash=self.source_draws_hash,
            point_role=self.point_role,
            chain_count=self.chain_count,
            draws_per_chain=self.draws_per_chain,
            parameter_names=self.parameter_names,
            draw_order=self.draw_order,
            rows=self.rows,
        )
        if self.content_sha256 != expected:
            raise ValueError("posterior joint input matrix digest does not match its rows")
        return self


class PosteriorPushforwardFailure(BaseModel):
    """Record an unavailable draw/output value without dropping its row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draw_index: int = Field(ge=0)
    outcome_code: PosteriorPushforwardOutcomeCode
    error_type: str | None = None


class PosteriorPushforwardOutputSummary(BaseModel):
    """Summarize one output over exact posterior source rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    output_metric_id: str = Field(min_length=1)
    selected_point_value: float | None = None
    selected_point_failure: PosteriorPushforwardOutcomeCode | None = None
    selected_point_error_type: str | None = None
    credible_mass: float = Field(gt=0.0, lt=1.0)
    draw_values: tuple[float | None, ...] = Field(min_length=1)
    posterior_mean: float | None = None
    posterior_median: float | None = None
    equal_tail_interval: tuple[float, float] | None = None
    successful_draw_count: int = Field(ge=0)
    failure_records: tuple[PosteriorPushforwardFailure, ...] = ()
    distribution_sample_semantics: Literal["successful_draws_only_conditional_on_execution"] = (
        "successful_draws_only_conditional_on_execution"
    )
    gate_eligible: Literal[False] = False

    @model_validator(mode="after")
    def _validate_output_summary(self) -> PosteriorPushforwardOutputSummary:
        if self.selected_point_value is not None and not math.isfinite(self.selected_point_value):
            raise ValueError("selected posterior output must be finite")
        if (self.selected_point_value is None) != (self.selected_point_failure is not None):
            raise ValueError("selected posterior output must retain its failure outcome")
        if any(value is not None and not math.isfinite(value) for value in self.draw_values):
            raise ValueError("posterior output draw values must be finite when present")
        failed_indices = tuple(record.draw_index for record in self.failure_records)
        missing_indices = tuple(
            index for index, value in enumerate(self.draw_values) if value is None
        )
        if (
            failed_indices != tuple(sorted(set(failed_indices)))
            or failed_indices != missing_indices
            or self.successful_draw_count != len(self.draw_values) - len(failed_indices)
        ):
            raise ValueError("posterior output values and per-draw outcomes do not align")
        statistics = (self.posterior_mean, self.posterior_median)
        if any(value is not None and not math.isfinite(value) for value in statistics):
            raise ValueError("posterior output statistics must be finite")
        if self.equal_tail_interval is not None and (
            not all(math.isfinite(value) for value in self.equal_tail_interval)
            or self.equal_tail_interval[0] > self.equal_tail_interval[1]
        ):
            raise ValueError("posterior output equal-tail interval must be finite and ordered")
        if self.successful_draw_count == 0 and any(
            value is not None for value in (*statistics, self.equal_tail_interval)
        ):
            raise ValueError("empty posterior output cannot carry summary statistics")
        observed = tuple(value for value in self.draw_values if value is not None)
        if observed:
            expected_mean = math.fsum(value / len(observed) for value in observed)
            alpha = (1.0 - self.credible_mass) / 2.0
            expected_median = _posterior_empirical_quantile(observed, 0.5)
            expected_interval = (
                _posterior_empirical_quantile(observed, alpha),
                _posterior_empirical_quantile(observed, 1.0 - alpha),
            )
            if (
                self.posterior_mean != expected_mean
                or self.posterior_median != expected_median
                or self.equal_tail_interval != expected_interval
            ):
                raise ValueError(
                    "posterior output summaries do not recompute from retained draw values"
                )
        return self


class PosteriorPushforwardResult(BaseModel):
    """Non-gating output from the v1.1 source-row posterior consumer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_version: Literal["1.1"] = "1.1"
    source_draws_ref: str = Field(min_length=1)
    source_draws_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_method_evidence_ref: ArtifactRefModel | None = None
    point_role: PosteriorPointRole
    chain_count: int = Field(ge=1)
    draws_per_chain: int = Field(ge=1)
    source_weight_status: Literal["not_supplied_by_source"] = "not_supplied_by_source"
    row_evaluation_semantics: Literal[
        "one_evaluator_call_per_source_draw",
        "one_logical_result_per_source_draw_with_one_bounded_typed_transient_retry",
    ] = "one_evaluator_call_per_source_draw"
    simulation_attempt_count: int = Field(ge=1)
    retry_attempt_count: int = Field(ge=0)
    selected_input_point: tuple[float, ...] = Field(min_length=1)
    joint_input_matrix: PosteriorJointInputMatrix
    output_metric_ids: tuple[str, ...] = Field(min_length=1)
    output_summaries: dict[str, PosteriorPushforwardOutputSummary]
    gate_eligible: Literal[False] = False
    unit_binding_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _validate_result_binding(self) -> PosteriorPushforwardResult:
        if (
            self.source_draws_ref != self.joint_input_matrix.source_draws_ref
            or self.source_draws_hash != self.joint_input_matrix.source_draws_hash
            or self.point_role is not self.joint_input_matrix.point_role
            or self.chain_count != self.joint_input_matrix.chain_count
            or self.draws_per_chain != self.joint_input_matrix.draws_per_chain
            or len(self.selected_input_point) != len(self.joint_input_matrix.parameter_names)
            or any(not math.isfinite(value) for value in self.selected_input_point)
            or len(set(self.output_metric_ids)) != len(self.output_metric_ids)
            or tuple(self.output_summaries) != self.output_metric_ids
            or any(
                item.output_metric_id != metric_id
                or len(item.draw_values) != len(self.joint_input_matrix.rows)
                for metric_id, item in self.output_summaries.items()
            )
        ):
            raise ValueError("posterior pushforward result does not match its selected matrix")

        logical_evaluation_count = 1 + len(self.joint_input_matrix.rows)
        retry_semantics = (
            "one_logical_result_per_source_draw_with_one_bounded_typed_transient_retry"
        )
        if self.retry_attempt_count > logical_evaluation_count:
            raise ValueError("posterior retry count exceeds logical evaluation count")
        if self.retry_attempt_count == 0 and self.row_evaluation_semantics != (
            "one_evaluator_call_per_source_draw"
        ):
            raise ValueError("posterior retry semantics do not match retry attempt count")
        if self.retry_attempt_count > 0 and self.row_evaluation_semantics != retry_semantics:
            raise ValueError("posterior retry semantics do not match retry attempt count")
        if self.simulation_attempt_count != logical_evaluation_count + self.retry_attempt_count:
            raise ValueError(
                "posterior physical attempt counts do not match logical evaluations and retries"
            )
        return self


def _evaluate_posterior_outputs(
    simulation_fn: Callable[..., Mapping[str, float]],
    nominal_params: Mapping[str, float],
    parameter_names: tuple[str, ...],
    parameter_values: tuple[float, ...],
    output_metric_ids: tuple[str, ...],
    attempts: _EvaluationAttempts,
) -> tuple[
    dict[str, float | None],
    dict[str, tuple[PosteriorPushforwardOutcomeCode, str | None] | None],
]:
    """Evaluate one posterior row while retaining each requested output failure."""
    params = dict(nominal_params)
    params.update(dict(zip(parameter_names, parameter_values, strict=True)))
    try:
        response = _evaluate_with_transient_retry(simulation_fn, params, attempts)
    except Exception as exc:
        failure = classify_evaluation_failure(exc)
        if failure.scope != "unknown" or not _is_legacy_draw_local_runtime_error(
            exc, failure.chain_complete, failure.cycle_detected
        ):
            raise
        return (
            dict.fromkeys(output_metric_ids),
            {
                metric_id: (
                    PosteriorPushforwardOutcomeCode.SIMULATION_EXCEPTION,
                    type(exc).__name__,
                )
                for metric_id in output_metric_ids
            },
        )
    if not isinstance(response, Mapping):
        return (
            dict.fromkeys(output_metric_ids),
            dict.fromkeys(
                output_metric_ids,
                (PosteriorPushforwardOutcomeCode.INVALID_RESPONSE, None),
            ),
        )

    values: dict[str, float | None] = {}
    failures: dict[str, tuple[PosteriorPushforwardOutcomeCode, str | None] | None] = {}
    for metric_id in output_metric_ids:
        if metric_id not in response:
            values[metric_id] = None
            failures[metric_id] = (PosteriorPushforwardOutcomeCode.MISSING_OUTPUT, None)
            continue
        raw_value = response[metric_id]
        if isinstance(raw_value, (bool, np.bool_)) or not isinstance(raw_value, Real):
            values[metric_id] = None
            failures[metric_id] = (
                PosteriorPushforwardOutcomeCode.NON_NUMERIC_OUTPUT,
                None,
            )
            continue
        value = float(raw_value)
        if not math.isfinite(value):
            values[metric_id] = None
            failures[metric_id] = (
                PosteriorPushforwardOutcomeCode.NON_FINITE_OUTPUT,
                None,
            )
            continue
        values[metric_id] = value
        failures[metric_id] = None
    return values, failures


def _sampled_input_digest(params: Mapping[str, Any]) -> str:
    """Hash all exact numeric inputs for one attempted draw."""
    digest = hashlib.sha256()
    for name in sorted(params):
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(struct.pack(">d", float(params[name])))
    return digest.hexdigest()


def _envelope_identity_and_context_wires(
    envelope: UncertaintyEnvelope,
) -> tuple[str | None, str | None, str | None]:
    """Capture the digest and context wires from the same serialization."""
    try:
        payload = json.dumps(
            envelope.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None, None, None
    digest = hashlib.sha256(payload).hexdigest()
    try:
        # Read context from those exact bytes, not by serializing behavioral
        # caller objects for a second time.
        decoded = json.loads(payload)
        provenance_wire = json.dumps(
            decoded["composition_provenance"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        metadata_wire = json.dumps(
            decoded["metadata"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, KeyError):
        return digest, None, None
    return digest, provenance_wire, metadata_wire


def _envelope_content_digest(envelope: UncertaintyEnvelope) -> str | None:
    """Return the existing content binding, or None when it is not JSON-safe."""
    return _envelope_identity_and_context_wires(envelope)[0]


def _normal_parametric_fit(env: UncertaintyEnvelope) -> tuple[float, float] | None:
    """Return the typed normal law, rejecting payloads this backend cannot honor."""
    payload = env.distribution_payload
    if not isinstance(payload, ParametricFitCarrier):
        return None
    if env.distribution_family is not DistributionFamily.NORMAL:
        raise ValueError("parametric fit family does not match envelope family")
    if payload.family is not DistributionFamily.NORMAL:
        raise ValueError("normal envelope carries a non-normal parametric fit")
    if payload.support is not None:
        raise ValueError("bounded normal parametric fit support is unsupported")

    raw_mean = payload.parameters.get("mean", payload.parameters.get("mu"))
    raw_std = payload.parameters.get("std", payload.parameters.get("sigma"))
    if raw_mean is None or raw_std is None:
        raise ValueError("normal parametric fit requires mean/mu and std/sigma")
    mean = float(raw_mean)
    std = float(raw_std)
    if not math.isfinite(mean) or not math.isfinite(std) or std < 0.0:
        raise ValueError("normal parametric fit parameters must be finite and non-negative")
    return mean, std


def _parametric_fit_names(
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[str, ...]:
    """Return inputs whose sampling law came from a typed fit carrier."""
    return tuple(
        name
        for name, envelope in input_envelopes.items()
        if isinstance(envelope.distribution_payload, ParametricFitCarrier)
    )


def _build_gaussian_joint_spec(
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    *,
    covariance_jitter: float = 0.0,
) -> tuple[_GaussianJointSpec | None, str | None]:
    """Bind all declared covariance rows or refuse unsupported joint inputs.

    A covariance declaration describes a Gaussian joint law only when every
    input is a compatible Gaussian marginal. Numeric validation cannot certify
    the origin or units of the declared covariance.
    """
    declared = any(
        "covariance_row" in input_envelopes[name].metadata
        or "covariance_params" in input_envelopes[name].metadata
        for name in param_names
    )
    if not declared:
        return None, None
    if any(
        input_envelopes[name].distribution_family is not DistributionFamily.NORMAL
        or isinstance(input_envelopes[name].distribution_payload, PosteriorSamplesCarrier)
        for name in param_names
    ):
        return None, "unsupported_joint_covariance"
    try:
        stored_covariance = build_covariance_matrix(
            param_names,
            input_envelopes,
            use_full_covariance=True,
            jitter=covariance_jitter,
            preserve_singular=True,
        )
        covariance = np.asarray(stored_covariance, dtype=np.float64)
        means = np.asarray(
            [
                (
                    _normal_parametric_fit(input_envelopes[name])
                    or (float(input_envelopes[name].point_estimate), 0.0)
                )[0]
                for name in param_names
            ],
            dtype=np.float64,
        )
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    except (TypeError, ValueError, np.linalg.LinAlgError):
        return None, "incompatible_dependency"
    factor = eigenvectors * np.sqrt(np.clip(eigenvalues, 0.0, None))
    return _GaussianJointSpec(
        means=means, factor=factor, covariance_storage_dtype=str(stored_covariance.dtype)
    ), None


def _build_empirical_joint_spec(
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[_EmpiricalJointSpec | None, str | None]:
    """Validate carrier alignment before treating rows as one joint law."""
    carriers: dict[str, PosteriorSamplesCarrier] = {}
    for name in param_names:
        envelope = input_envelopes[name]
        payload = envelope.distribution_payload
        if isinstance(payload, PosteriorSamplesCarrier):
            carriers[name] = payload
            continue
        if isinstance(payload, ParametricFitCarrier):
            try:
                _normal_parametric_fit(envelope)
            except (TypeError, ValueError):
                return None, "unsupported_parametric_fit"
            continue
        if payload is not None:
            return None, "unsupported_distribution_payload"
        if envelope.distribution_family not in {
            DistributionFamily.NORMAL,
            DistributionFamily.UNIFORM,
            DistributionFamily.TRIANGULAR,
        }:
            return None, "unsupported_distribution_family"

    if not carriers:
        return None, None
    if len(carriers) != len(param_names):
        return None, "incompatible_joint_law"

    joint_sample_id: str | None = None
    if len(carriers) > 1:
        declared_ids: list[str] = []
        for name in carriers:
            raw_id = input_envelopes[name].metadata.get("joint_sample_id")
            if not isinstance(raw_id, str) or not raw_id.strip():
                return None, "unestablished_joint_law"
            declared_ids.append(raw_id.strip())
        if len(set(declared_ids)) != 1:
            return None, "incompatible_joint_law"
        joint_sample_id = declared_ids[0]

    first = next(iter(carriers.values()))
    axis = first.sample_axis.strip()
    if not axis:
        return None, "incompatible_joint_law"
    sample_count = len(first.samples)
    if sample_count < 1:
        return None, "incompatible_joint_law"

    normalized_weights: list[np.ndarray] = []
    samples: dict[str, np.ndarray] = {}
    for name, carrier in carriers.items():
        if carrier.sample_axis.strip() != axis or len(carrier.samples) != sample_count:
            return None, "incompatible_joint_law"
        try:
            samples[name] = _real_float64(carrier.samples)
            weights = (
                np.ones(sample_count, dtype=np.float64)
                if carrier.weights is None
                else _real_float64(carrier.weights)
            )
        except (TypeError, ValueError, OverflowError):
            return None, "incompatible_joint_law"
        if (
            samples[name].shape != (sample_count,)
            or weights.shape != (sample_count,)
            or not np.all(np.isfinite(weights))
            or np.any(weights < 0.0)
        ):
            return None, "incompatible_joint_law"
        total = float(np.sum(weights))
        if not math.isfinite(total) or total <= 0.0:
            return None, "incompatible_joint_law"
        normalized_weights.append(weights / total)

    probabilities = normalized_weights[0]
    if any(
        not np.allclose(probabilities, weights, rtol=0.0, atol=1e-12)
        for weights in normalized_weights[1:]
    ):
        return None, "incompatible_joint_law"

    return (
        _EmpiricalJointSpec(
            names=tuple(carriers),
            sample_axis=axis,
            sample_count=sample_count,
            samples=samples,
            probabilities=probabilities,
            joint_sample_id=joint_sample_id,
        ),
        None,
    )


def _unknown_joint_results(
    output_metric_ids: list[str],
    *,
    input_param_names: list[str],
    failure: str,
) -> list[PropagationResult]:
    """Return non-authoritative results when sampling law is not established."""
    return [
        PropagationResult(
            metric_id=metric_id,
            envelope=UncertaintyEnvelope(
                point_estimate=0.0,
                confidence_interval=(-1.0, 1.0),
                confidence_level=None,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.MONTE_CARLO,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                is_heuristic_ci=True,
                gate_eligible=False,
                metadata={
                    "failure": failure,
                    "input_param_names": input_param_names,
                },
            ),
            input_envelopes_used=input_param_names,
            method_used=PropagationMethod.MONTE_CARLO,
            diagnostics={failure: True},
        )
        for metric_id in output_metric_ids
    ]


def _qmc_dimension_names(
    param_names: list[str],
    empirical_spec: _EmpiricalJointSpec | None,
) -> tuple[str, ...]:
    """Return one QMC dimension per independent sampling coordinate."""
    if empirical_spec is None:
        return tuple(param_names)
    first_empirical = True
    dimensions: list[str] = []
    for name in param_names:
        if name in empirical_spec.names:
            if first_empirical:
                dimensions.append(name)
                first_empirical = False
            continue
        dimensions.append(name)
    return tuple(dimensions)


def _empirical_indices_from_uniform(
    uniform_samples: np.ndarray,
    probabilities: np.ndarray,
) -> np.ndarray:
    """Map one QMC coordinate to aligned empirical row indices."""
    clipped = np.clip(np.asarray(uniform_samples, dtype=np.float64), 1e-10, 1.0 - 1e-10)
    cumulative = np.cumsum(np.asarray(probabilities, dtype=np.float64))
    indices = np.searchsorted(cumulative, clipped, side="right")
    return np.minimum(indices, len(probabilities) - 1)


_NATIVE_NUMPY_SCALAR_TYPES = frozenset(np.sctypeDict.values())


@dataclass(frozen=True)
class _PreparedPropagationInputs:
    """One invocation's owned numerical interpretation and original wire identity.

    This is not a generic Python graph snapshot. Fixed scalar objects keep
    their callback-visible types; callable defaults/closures and opaque inert
    sidecars remain outside the numerical-data ownership claim.
    """

    nominal_params: dict[str, float]
    input_envelopes: dict[str, UncertaintyEnvelope]
    output_metric_ids: list[str]
    input_envelope_digests: dict[str, str | None]
    weights: dict[str, float] | None
    unknown_dependency: bool
    empirical_spec: _EmpiricalJointSpec | None = None
    empirical_failure: str | None = None
    gaussian_spec: _GaussianJointSpec | None = None
    gaussian_failure: str | None = None
    execution_context_prepared: bool = False
    context_error: Exception | None = None
    fixed_scalar_values_owned: bool = True
    analytical_weight_error: Exception | None = None
    covariance_context_error: Exception | None = None
    input_provenance_wires: dict[str, str | None] | None = None
    provenance_context_owned: bool = True
    metadata_context_owned: bool = True


def _fixed_scalar_value_is_owned(value: Any) -> bool:
    """Qualify immutable scalar value semantics, not an arbitrary object graph.

    Other fixed objects keep their legacy borrowed callback behavior, with
    identity not established and no gate. They are not newly refused.
    """
    if any(type(value) is scalar for scalar in (bool, int, float, complex, Decimal, Fraction)):
        return True
    return (
        isinstance(value, np.generic)
        and any(type(value) is scalar for scalar in _NATIVE_NUMPY_SCALAR_TYPES)
        and value.dtype.kind in "biufc"
        and value.dtype.metadata is None
        and value.dtype.fields is None
        and value.dtype.subdtype is None
    )


def _check_legacy_posterior_profile(
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> None:
    if isinstance(input_envelopes, PosteriorSummaryV11):
        raise ValueError(
            "legacy propagate cannot consume a v1.1 posterior summary; "
            "use propagate_posterior_summary"
        )
    if any(
        envelope.metadata.get("profile_id")
        == "urn:policyos:ir:bayesian-posterior-summary-profile:1"
        and envelope.metadata.get("profile_version") == "1.1"
        for envelope in input_envelopes.values()
    ):
        raise ValueError(
            "legacy propagate cannot consume a v1.1 posterior summary profile; "
            "use propagate_posterior_summary"
        )


def _own_json_metadata(value: Any, active: set[int]) -> tuple[Any, bool]:
    """Copy the exact JSON metadata domain; mark all other values borrowed.

    This is a qualification for the existing metadata owner, not a generic
    object codec. It deliberately excludes tuples, subclasses, Enum members,
    datetime and custom objects even when they happen to serialize as JSON.
    """
    kind = type(value)
    if value is None or kind in (bool, int, float, str):
        return value, True
    if kind not in (dict, list):
        return value, False
    identity = id(value)
    if identity in active:
        return value, False
    active.add(identity)
    try:
        if kind is dict:
            copied = {key: _own_json_metadata(item, active) for key, item in value.items()}
            return (
                {key: item[0] for key, item in copied.items()},
                all(type(key) is str and item[1] for key, item in copied.items()),
            )
        copied_values = [_own_json_metadata(item, active) for item in value]
        return [item[0] for item in copied_values], all(item[1] for item in copied_values)
    finally:
        active.remove(identity)


def _metadata_wire_matches(metadata: Any, original_wire: str | None) -> bool:
    """Compare owned metadata to the exact original digest's JSON metadata."""
    if original_wire is None:
        return False
    try:
        return (
            json.dumps(
                metadata,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            == original_wire
        )
    except (TypeError, ValueError):
        return False


def _prepare_propagation_inputs(
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    output_metric_ids: list[str],
    *,
    covariance_jitter: float,
    weights: Mapping[str, float] | None = None,
) -> _PreparedPropagationInputs:
    """Resolve existing law owners before an evaluator can change their inputs.

    Metadata strings are resolved by the same consuming interpretation, not
    by an Enum's wire value. Original content identity is independently kept
    as the existing digest or None. Unsupported/incompatible laws need no
    unrelated provenance conversion or evaluator binding.
    """
    _check_legacy_posterior_profile(input_envelopes)
    nominal = dict(nominal_params)
    source = dict(input_envelopes)
    metrics = list(output_metric_ids)
    route_weights = None if weights is None else dict(weights)
    identities = {name: _envelope_identity_and_context_wires(env) for name, env in source.items()}
    digests = {name: identity[0] for name, identity in identities.items()}
    provenance_wires = {name: identity[1] for name, identity in identities.items()}
    metadata_wires = {name: identity[2] for name, identity in identities.items()}
    metadata_snapshots: dict[str, tuple[Any, bool]] = {}
    for name, envelope in source.items():
        try:
            metadata_snapshots[name] = _own_json_metadata(envelope.metadata, set())
        except RecursionError:
            metadata_snapshots[name] = (envelope.metadata, False)
    metadata_owned = all(
        type(snapshot[0]) is dict
        and snapshot[1]
        and _metadata_wire_matches(snapshot[0], metadata_wires[name])
        for name, snapshot in metadata_snapshots.items()
    )
    envelopes = dict(source)
    for name, envelope in source.items():
        # Unsupported entries stay available to legacy candidate computation,
        # but the common finalizer never promotes their identity to a gate.
        metadata = dict(metadata_snapshots[name][0])
        dependency_key = "dependency"
        raw = metadata.get(dependency_key)
        if raw is None:
            dependency_key = "dependence"
            raw = metadata.get(dependency_key)
        if raw is not None:
            # Resolve the actual owner's entire consumed predicate once.
            # Keep its primitive meaning, never a behavioral string alias.
            unknown = has_unknown_dependency(
                {name: envelope.model_copy(update={"metadata": metadata})}
            )
            metadata[dependency_key] = "unknown" if unknown else "known"
        else:
            unknown = False
        envelopes[name] = envelope.model_copy(update={"metadata": metadata})
        if unknown:
            return _PreparedPropagationInputs(
                nominal,
                envelopes,
                metrics,
                digests,
                route_weights,
                True,
                metadata_context_owned=metadata_owned,
            )
    names = sorted(envelopes)
    empirical, empirical_failure = _build_empirical_joint_spec(names, envelopes)
    gaussian: _GaussianJointSpec | None = None
    gaussian_failure: str | None = None
    if empirical_failure is None:
        gaussian, gaussian_failure = _build_gaussian_joint_spec(
            names, envelopes, covariance_jitter=covariance_jitter
        )
    return _PreparedPropagationInputs(
        nominal,
        envelopes,
        metrics,
        digests,
        route_weights,
        False,
        empirical,
        empirical_failure,
        gaussian,
        gaussian_failure,
        fixed_scalar_values_owned=all(_fixed_scalar_value_is_owned(v) for v in nominal.values()),
        input_provenance_wires=provenance_wires,
        metadata_context_owned=metadata_owned,
    )


def _own_provenance_value(value: Any, active: set[int]) -> tuple[Any, bool]:
    """Own the closed, type-preserving provenance data domain; cap the rest.

    This is not a general object copier. Exact builtin containers are copied
    recursively; exact scalar values and the IR's declared enum types are
    stable. Aware datetimes retain their wire offset without retaining the
    caller's timezone object. Other values, subclasses, cycles and behaviors
    are retained as borrowed, with the enclosing context unqualified.
    """
    kind = type(value)
    if value is None or kind in (bool, int, float, str, bytes):
        return value, True
    if kind in (ComposedFlavour, ExactnessKind, CertificateKind):
        return value, type(value.value) is str
    if kind is datetime:
        try:
            if value.tzinfo is None:
                return value, True
            offset = value.utcoffset()
            if offset is not None:
                return value.replace(tzinfo=timezone(offset)), True
        except (TypeError, ValueError, OverflowError):
            pass
        return value, False
    if kind not in (dict, list, tuple, CompositionStep, CompositionProvenance):
        return value, False
    identity = id(value)
    if identity in active:
        return value, False
    active.add(identity)
    try:
        if kind in (CompositionStep, CompositionProvenance):
            copied_fields = {
                name: _own_provenance_value(getattr(value, name), active)
                for name in kind.model_fields
            }
            return (
                value.model_copy(update={name: item[0] for name, item in copied_fields.items()}),
                all(item[1] for item in copied_fields.values()),
            )
        if kind is dict:
            copied_items = {key: _own_provenance_value(item, active) for key, item in value.items()}
            return (
                {key: item[0] for key, item in copied_items.items()},
                all(type(key) is str and item[1] for key, item in copied_items.items()),
            )
        copied_values = [_own_provenance_value(item, active) for item in value]
        result = [item[0] for item in copied_values]
        return (tuple(result) if kind is tuple else result, all(item[1] for item in copied_values))
    finally:
        active.remove(identity)


def _provenance_wire_matches(envelope: UncertaintyEnvelope, original_wire: str | None) -> bool:
    """Bind the prepared history to the provenance in the original envelope digest."""
    if original_wire is None:
        return False
    try:
        provenance = envelope.composition_provenance
        wire = json.dumps(
            None if provenance is None else provenance.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return False
    return wire == original_wire


def _finalize_prepared_results(
    results: list[PropagationResult], prepared: _PreparedPropagationInputs
) -> list[PropagationResult]:
    """Apply the shared invocation and context qualification to every route."""
    fixed_names = set(prepared.nominal_params) - set(prepared.input_envelopes)
    identity_established = (
        not fixed_names
        and prepared.fixed_scalar_values_owned
        and prepared.provenance_context_owned
        and prepared.metadata_context_owned
        and all(value is not None for value in prepared.input_envelope_digests.values())
    )
    if identity_established:
        return results
    finalized: list[PropagationResult] = []
    for result in results:
        metadata = dict(result.envelope.metadata)
        metadata["invocation_identity_status"] = "not_established"
        diagnostics = dict(result.diagnostics)
        diagnostics["input_identity_status"] = "not_established"
        provenance = result.envelope.composition_provenance
        if not prepared.provenance_context_owned:
            metadata["provenance_context_status"] = "not_established"
            diagnostics["provenance_context_status"] = "not_established"
            if provenance is not None:
                # Keep the producer's own last step, but do not serialize
                # borrowed history or origin IDs as if they were an owned wire.
                history = provenance.operator_history
                if history:
                    own_step = history[-1]
                    own_step = own_step.model_copy(
                        update={
                            "notes": {
                                **own_step.notes,
                                "input_provenance_history": "withheld_unowned",
                            }
                        }
                    )
                    history = (own_step,)
                provenance = provenance.model_copy(
                    update={"operator_history": history, "origin_envelope_ids": ()}
                )
                metadata["input_provenance_history"] = "withheld_unowned"
                diagnostics["input_provenance_history"] = "withheld_unowned"
        if not prepared.metadata_context_owned:
            metadata["metadata_context_status"] = "not_established"
            diagnostics["metadata_context_status"] = "not_established"
        finalized.append(
            replace(
                result,
                envelope=result.envelope.model_copy(
                    update={
                        "gate_eligible": False,
                        "metadata": metadata,
                        "composition_provenance": provenance,
                    }
                ),
                diagnostics=diagnostics,
            )
        )
    return finalized


def _prepare_execution_envelope(
    envelope: UncertaintyEnvelope, *, prepare_covariance: bool
) -> tuple[UncertaintyEnvelope, Exception | None, bool]:
    """Own the typed sampling/provenance data actually read after binding.

    An unsupported metadata sidecar is retained as borrowed candidate data;
    it is neither graph-copied nor newly rejected. The earlier metadata-domain
    qualification independently caps the result even when its original digest
    exists. No later consumer may use the sidecar as verified authority evidence.
    """
    data = envelope.model_dump(
        mode="python", exclude={"metadata", "composition_provenance", "distribution_payload"}
    )
    metadata = dict(envelope.metadata)
    covariance_error: Exception | None = None
    if prepare_covariance:
        try:
            # Covariance's declared lists retain their original admission shape.
            row = metadata.get("covariance_row")
            if isinstance(row, list):
                metadata["covariance_row"] = [
                    float(value)
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                    else value
                    for value in row
                ]
            columns = metadata.get("covariance_params")
            if isinstance(columns, list):
                metadata["covariance_params"] = [
                    str.__str__(value) if isinstance(value, str) else value for value in columns
                ]
            declared_std = metadata.get("std")
            if isinstance(declared_std, (int, float)):
                metadata["std"] = float(declared_std)
        except Exception as exc:
            # Only a consumer of the moment covariance sees this error.
            # An MC fallback that ignores std keeps its existing behavior.
            covariance_error = exc

    provenance = envelope.composition_provenance
    if provenance is None:
        # These are the existing IR provenance owner's consumed meanings.
        # Keep wire identity separate; no new metadata encoding is invented.
        for key in ("envelope_id", "artifact_id", "ref_id"):
            raw_id = metadata.get(key)
            if isinstance(raw_id, str):
                metadata[key] = str.__str__(raw_id) if raw_id else None
        is_qmc_source = str(metadata.get("mc_sampling_method", "")).lower() in {"sobol", "halton"}
        # The existing provenance owner consumes the QMC category, not the
        # original spelling or a behavioral string object. Wire identity is
        # retained separately and still distinguishes sobol from halton.
        sampling_method = "sobol" if is_qmc_source else ""
        metadata["mc_sampling_method"] = sampling_method
        if sampling_method.lower() in {"sobol", "halton"} and envelope.sample_size is not None:
            metadata["qmc_replicates"] = float(metadata.get("qmc_replicates", 1))
        if envelope.propagation_method is PropagationMethod.DELTA_METHOD:
            for key in ("taylor_remainder", "output_std"):
                raw_radius = metadata.get(key)
                if isinstance(raw_radius, (int, float)):
                    metadata[key] = float(raw_radius)
    else:
        try:
            provenance, provenance_owned = _own_provenance_value(provenance, set())
        except RecursionError:
            # Excessively deep or cyclic objects do not acquire authority.
            provenance_owned = False
    if provenance is None:
        provenance_owned = True

    payload = envelope.distribution_payload
    if isinstance(payload, PosteriorSamplesCarrier):
        payload = PosteriorSamplesCarrier.model_validate(payload.model_dump(mode="python"))
    elif isinstance(payload, ParametricFitCarrier):
        payload = ParametricFitCarrier.model_validate(payload.model_dump(mode="python"))
    data.update(metadata=metadata, composition_provenance=provenance, distribution_payload=payload)
    return UncertaintyEnvelope.model_validate(data), covariance_error, provenance_owned


def _prepare_execution_inputs(
    prepared: _PreparedPropagationInputs,
    *,
    prepare_weights: bool = False,
    prepare_covariance: bool = False,
) -> _PreparedPropagationInputs:
    """Finish one shared preparation without changing supported fixed scalars."""
    if prepared.execution_context_prepared:
        return prepared
    try:
        snapshots = {
            name: _prepare_execution_envelope(envelope, prepare_covariance=prepare_covariance)
            for name, envelope in prepared.input_envelopes.items()
        }
        envelopes = {name: snapshot[0] for name, snapshot in snapshots.items()}
        covariance_error = next(
            (snapshot[1] for snapshot in snapshots.values() if snapshot[1] is not None), None
        )
        original_wires = prepared.input_provenance_wires or {}
        provenance_owned = all(
            snapshot[2]
            and (
                snapshot[0].composition_provenance is None
                or _provenance_wire_matches(snapshot[0], original_wires.get(name))
            )
            for name, snapshot in snapshots.items()
        )
    except Exception as exc:
        # Preserve binding-error precedence for an otherwise executable law.
        # No evaluator is run with a context that could not be prepared.
        return replace(prepared, execution_context_prepared=True, context_error=exc)
    weights = prepared.weights
    weight_error: Exception | None = None
    if prepare_weights and weights:
        # Analytical's existing consuming interpretation is float(weight).
        # Resolve it before signature effects; retain its existing fallback
        # on invalid weights, after complete evaluator binding.
        converted: dict[str, float] = {}
        for name, weight in weights.items():
            try:
                converted[name] = float(weight)
            except Exception as exc:
                converted[name] = 0.0
                if weight_error is None:
                    weight_error = exc
        weights = converted
    return replace(
        prepared,
        input_envelopes=envelopes,
        weights=weights,
        execution_context_prepared=True,
        analytical_weight_error=weight_error,
        covariance_context_error=covariance_error,
        provenance_context_owned=provenance_owned,
    )


class MonteCarloPropagator:
    """Monte carlo propagator public type."""

    def __init__(self, config: PropagationConfig | None = None) -> None:
        self._config = config or PropagationConfig()

    @property
    def method(self) -> PropagationMethod:
        return PropagationMethod.MONTE_CARLO

    def propagate(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
    ) -> list[PropagationResult]:
        if not output_metric_ids:
            _check_legacy_posterior_profile(input_envelopes)
            return []
        prepared = _prepare_propagation_inputs(
            nominal_params,
            input_envelopes,
            output_metric_ids,
            covariance_jitter=self._config.delta_covariance_jitter,
        )
        return self._propagate_prepared(simulation_fn, prepared)

    def _propagate_prepared(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        prepared: _PreparedPropagationInputs,
    ) -> list[PropagationResult]:
        """Consume the same prepared law from direct and dispatched execution."""
        param_names = sorted(prepared.input_envelopes)
        failure = (
            "unknown_dependency"
            if prepared.unknown_dependency
            else prepared.empirical_failure or prepared.gaussian_failure
        )
        if failure is not None:
            return _finalize_prepared_results(
                _unknown_joint_results(
                    prepared.output_metric_ids, input_param_names=param_names, failure=failure
                ),
                prepared,
            )
        prepared = _prepare_execution_inputs(prepared)
        nominal_params = prepared.nominal_params
        input_envelopes = prepared.input_envelopes
        output_metric_ids = prepared.output_metric_ids
        _validate_effective_inputs(simulation_fn, nominal_params, param_names)
        if prepared.context_error is not None:
            raise prepared.context_error
        empirical_spec = prepared.empirical_spec
        gaussian_spec = prepared.gaussian_spec
        gaussian_trace = _GaussianExecutionTrace(batches=[]) if gaussian_spec is not None else None
        level = self._config.confidence_level
        alpha = 1.0 - level

        adaptive = self._config.adaptive_stopping
        if adaptive.enabled:
            n_samples = adaptive.max_samples
        else:
            n_samples = self._config.mc_n_samples

        batch_size = min(self._config.mc_batch_size, n_samples)

        sample_buffers = self._create_sample_buffers(
            param_names=param_names,
            output_metric_ids=output_metric_ids,
            n_samples=n_samples,
        )
        missing_outputs = dict.fromkeys(output_metric_ids, 0)
        draw_outcomes: list[_DrawOutcomeRecord] = []
        evaluation_attempts = _EvaluationAttempts()
        failed = 0
        stopped_early = False
        actual_n_samples = 0
        nominal_outputs = self._safe_nominal_outputs(
            simulation_fn, nominal_params, evaluation_attempts=evaluation_attempts
        )
        qmc_summary: _QMCExecutionSummary | None = None

        use_qmc = self._config.mc_sampling_method != "random"

        if use_qmc:
            actual_n_samples, failed, qmc_summary = self._run_qmc_loop(
                simulation_fn,
                nominal_params,
                param_names,
                input_envelopes,
                output_metric_ids,
                n_samples,
                sample_buffers,
                adaptive,
                alpha,
                missing_outputs,
                draw_outcomes,
                evaluation_attempts,
                empirical_spec,
                gaussian_spec,
                gaussian_trace,
            )
            stopped_early = adaptive.enabled and actual_n_samples < n_samples
        else:
            actual_n_samples, failed = self._run_random_loop(
                simulation_fn,
                nominal_params,
                param_names,
                input_envelopes,
                output_metric_ids,
                n_samples,
                batch_size,
                sample_buffers,
                adaptive,
                alpha,
                missing_outputs,
                draw_outcomes,
                evaluation_attempts,
                empirical_spec,
                gaussian_spec,
                gaussian_trace,
            )
            stopped_early = adaptive.enabled and actual_n_samples < n_samples

        results = self._build_results(
            sample_buffers.values,
            sample_buffers.input_samples,
            input_envelopes,
            param_names,
            output_metric_ids,
            nominal_params,
            nominal_outputs,
            actual_n_samples,
            failed,
            stopped_early,
            level,
            alpha,
            missing_outputs=missing_outputs,
            draw_outcomes=draw_outcomes,
            evaluation_attempts=evaluation_attempts,
            requested_n_samples=n_samples,
            qmc_summary=qmc_summary,
            input_envelope_digests=prepared.input_envelope_digests,
            fixed_scalar_values_owned=prepared.fixed_scalar_values_owned,
            provenance_context_owned=prepared.provenance_context_owned,
            metadata_context_owned=prepared.metadata_context_owned,
            sample_axis=(empirical_spec.sample_axis if empirical_spec is not None else "draw"),
            joint_sample_id=(
                empirical_spec.joint_sample_id if empirical_spec is not None else None
            ),
            parametric_fit_names=_parametric_fit_names(input_envelopes),
            declared_gaussian_joint=gaussian_spec is not None,
            gaussian_spec=gaussian_spec,
            gaussian_trace=gaussian_trace,
            unestablished_independence=(
                len(param_names) > 1 and empirical_spec is None and gaussian_spec is None
            ),
        )
        return _finalize_prepared_results(results, prepared)

    def propagate_posterior_summary(
        self,
        summary: PosteriorSummaryV11,
        *,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        parameter_names: tuple[str, ...],
        output_metric_ids: tuple[str, ...],
        point_role: PosteriorPointRole,
    ) -> PosteriorPushforwardResult:
        """Push one named posterior functional and its exact rows through an evaluator.

        This versioned path preserves each aligned source row and reports the selected
        point, posterior output functionals, and equal-tail bounds as distinct values.
        It never coerces those values into an ``UncertaintyEnvelope``.

        Args:
            summary: Recomputed v1.1 candidate summary from a persisted posterior artifact.
            simulation_fn: The actual evaluator applied to the selected point and each source row.
            nominal_params: Additional fixed evaluator inputs.
            parameter_names: Ordered scalar parameter coordinates selected from the source rows.
            output_metric_ids: Ordered outputs to retain from each evaluator result.
            point_role: Explicit point functional selected by this consumer.

        Returns:
            A non-gating result that retains the content-bound joint input matrix and every
            output row in source order.

        Raises:
            ValueError: If the source summary, selected point role, or requested axes cannot be
                recomputed and matched before running the evaluator.
        """
        if point_role is not summary.point_role:
            raise ValueError("point_role must match the named functional in the selected summary")
        if not parameter_names or len(set(parameter_names)) != len(parameter_names):
            raise ValueError("parameter_names must be non-empty and distinct")
        if not output_metric_ids or len(set(output_metric_ids)) != len(output_metric_ids):
            raise ValueError("output_metric_ids must be non-empty and distinct")
        if any(not name for name in (*parameter_names, *output_metric_ids)):
            raise ValueError("parameter and output names must be non-empty")
        for name, raw_value in nominal_params.items():
            if isinstance(raw_value, (bool, np.bool_)) or not isinstance(raw_value, Real):
                raise ValueError(f"nominal parameter {name!r} must be a finite real number")
            if not math.isfinite(float(raw_value)):
                raise ValueError(f"nominal parameter {name!r} must be a finite real number")

        recomputed = summarize_posterior_draw_artifact(
            artifact_ref=summary.source_draws_ref,
            artifact_payload=summary.source_draws_payload,
            artifact_hash=summary.source_draws_hash,
            credible_mass=summary.credible_mass,
            point_role=summary.point_role,
            source_method_evidence_ref=summary.source_method_evidence_ref,
        )
        if recomputed != summary:
            raise ValueError("selected posterior summary does not match its source draw payload")

        # Execute only the detached source-derived projection. A shallowly
        # frozen caller DTO can have equal-valued mutable substitutions; its
        # equality with the source is not permission to consume those values.
        summary = recomputed
        rows = summary.joint_row_values(parameter_names)
        selected_input_point = tuple(
            summary.parameters[name].selected_point for name in parameter_names
        )
        draw_order = summary.draw_order
        matrix_digest = _posterior_joint_matrix_digest(
            source_draws_ref=summary.source_draws_ref,
            source_draws_hash=summary.source_draws_hash,
            point_role=point_role,
            chain_count=summary.chain_count,
            draws_per_chain=summary.draws_per_chain,
            parameter_names=parameter_names,
            draw_order=draw_order,
            rows=rows,
        )
        joint_input_matrix = PosteriorJointInputMatrix(
            source_draws_ref=summary.source_draws_ref,
            source_draws_hash=summary.source_draws_hash,
            point_role=point_role,
            chain_count=summary.chain_count,
            draws_per_chain=summary.draws_per_chain,
            parameter_names=parameter_names,
            draw_order=draw_order,
            rows=rows,
            content_sha256=matrix_digest,
        )

        evaluation_attempts = _EvaluationAttempts()
        selected_values, selected_failures = _evaluate_posterior_outputs(
            simulation_fn,
            nominal_params,
            parameter_names,
            selected_input_point,
            output_metric_ids,
            evaluation_attempts,
        )
        values_by_metric = {metric_id: [] for metric_id in output_metric_ids}
        failures_by_metric: dict[str, list[PosteriorPushforwardFailure]] = {
            metric_id: [] for metric_id in output_metric_ids
        }
        for draw_index, row in enumerate(rows):
            row_values, row_failures = _evaluate_posterior_outputs(
                simulation_fn,
                nominal_params,
                parameter_names,
                row,
                output_metric_ids,
                evaluation_attempts,
            )
            for metric_id in output_metric_ids:
                values_by_metric[metric_id].append(row_values[metric_id])
                failure = row_failures[metric_id]
                if failure is not None:
                    failures_by_metric[metric_id].append(
                        PosteriorPushforwardFailure(
                            draw_index=draw_index,
                            outcome_code=failure[0],
                            error_type=failure[1],
                        )
                    )

        alpha = (1.0 - summary.credible_mass) / 2.0
        output_summaries: dict[str, PosteriorPushforwardOutputSummary] = {}
        for metric_id in output_metric_ids:
            draw_values = tuple(values_by_metric[metric_id])
            observed = tuple(value for value in draw_values if value is not None)
            if observed:
                mean = math.fsum(value / len(observed) for value in observed)
                median = _posterior_empirical_quantile(observed, 0.5)
                interval = (
                    _posterior_empirical_quantile(observed, alpha),
                    _posterior_empirical_quantile(observed, 1.0 - alpha),
                )
            else:
                mean = median = None
                interval = None
            selected_failure = selected_failures[metric_id]
            output_summaries[metric_id] = PosteriorPushforwardOutputSummary(
                output_metric_id=metric_id,
                selected_point_value=selected_values[metric_id],
                selected_point_failure=(selected_failure[0] if selected_failure else None),
                selected_point_error_type=(selected_failure[1] if selected_failure else None),
                credible_mass=summary.credible_mass,
                draw_values=draw_values,
                posterior_mean=mean,
                posterior_median=median,
                equal_tail_interval=interval,
                successful_draw_count=len(observed),
                failure_records=tuple(failures_by_metric[metric_id]),
            )

        return PosteriorPushforwardResult(
            source_draws_ref=summary.source_draws_ref,
            source_draws_hash=summary.source_draws_hash,
            source_method_evidence_ref=summary.source_method_evidence_ref,
            point_role=point_role,
            chain_count=summary.chain_count,
            draws_per_chain=summary.draws_per_chain,
            source_weight_status=summary.weight_status,
            selected_input_point=selected_input_point,
            joint_input_matrix=joint_input_matrix,
            output_metric_ids=output_metric_ids,
            output_summaries=output_summaries,
            row_evaluation_semantics=(
                "one_evaluator_call_per_source_draw"
                if evaluation_attempts.retry_attempt_count == 0
                else "one_logical_result_per_source_draw_with_one_bounded_typed_transient_retry"
            ),
            simulation_attempt_count=evaluation_attempts.simulation_attempt_count,
            retry_attempt_count=evaluation_attempts.retry_attempt_count,
            gate_eligible=False,
            unit_binding_status="not_established",
        )

    # ------------------------------------------------------------------
    # Sampling loops
    # ------------------------------------------------------------------

    def _run_qmc_loop(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        param_names: list[str],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        n_samples: int,
        sample_buffers: _SampleBuffers,
        adaptive: Any,
        alpha: float,
        missing_outputs: dict[str, int],
        draw_outcomes: list[_DrawOutcomeRecord],
        evaluation_attempts: _EvaluationAttempts,
        empirical_spec: _EmpiricalJointSpec | None,
        gaussian_spec: _GaussianJointSpec | None,
        gaussian_trace: _GaussianExecutionTrace | None,
    ) -> tuple[int, int, _QMCExecutionSummary]:
        batch_size = min(self._config.mc_batch_size, n_samples)
        failed = 0
        generated = 0
        qmc_method = self._config.mc_sampling_method
        scrambled = bool(self._config.mc_qmc_scramble)
        requested_replicates = self._config.mc_qmc_replicates if scrambled else 1
        replicate_sizes = _split_evenly(n_samples, requested_replicates)
        actual_replicates = 0
        qmc_dimension_names = _qmc_dimension_names(param_names, empirical_spec)

        for replicate_idx, replicate_size in enumerate(replicate_sizes):
            if replicate_size <= 0:
                continue
            sampler_state = self._create_qmc_sampler_state_with_seed(
                len(qmc_dimension_names),
                seed=self._config.mc_seed + replicate_idx,
            )
            generated_this_replicate = 0
            actual_replicates += 1

            while generated_this_replicate < replicate_size:
                this_batch = self._adaptive_batch_size(
                    generated=generated,
                    batch_size=batch_size,
                    remaining=replicate_size - generated_this_replicate,
                    adaptive=adaptive,
                )
                uniform_samples, sampler_state = self._next_qmc_uniform_chunk(
                    sampler_state,
                    this_batch,
                )
                if uniform_samples.shape[0] > this_batch:
                    uniform_samples = uniform_samples[:this_batch]
                qmc_transformed = self._transform_qmc_samples(
                    uniform_samples,
                    param_names,
                    input_envelopes,
                    empirical_spec=empirical_spec,
                    gaussian_spec=gaussian_spec,
                    dimension_names=qmc_dimension_names,
                )
                if gaussian_spec is not None and gaussian_trace is not None:
                    gaussian_trace.batches.append(
                        {
                            "first_draw": generated,
                            "draw_count": int(uniform_samples.shape[0]),
                            "source_dtype": str(uniform_samples.dtype),
                            "factor_dtype": str(gaussian_spec.factor.dtype),
                            "mean_dtype": str(gaussian_spec.means.dtype),
                            "joint_dtype": str(qmc_transformed[param_names[0]].dtype),
                            "device": "cpu",
                            "prng_implementation": None,
                            "replicate_index": replicate_idx,
                            "replicate_seed": self._config.mc_seed + replicate_idx,
                        }
                    )

                for row_idx in range(uniform_samples.shape[0]):
                    params = dict(nominal_params)
                    params.update(
                        {name: float(qmc_transformed[name][row_idx]) for name in param_names}
                    )
                    sample_idx = generated + row_idx
                    ok = self._eval_and_record(
                        simulation_fn,
                        params,
                        param_names,
                        output_metric_ids,
                        sample_buffers,
                        sample_idx=sample_idx,
                        missing_outputs=missing_outputs,
                        draw_outcomes=draw_outcomes,
                        evaluation_attempts=evaluation_attempts,
                    )
                    if not ok:
                        failed += 1

                generated_batch = int(uniform_samples.shape[0])
                generated += generated_batch
                generated_this_replicate += generated_batch

                if adaptive.enabled and self._check_adaptive_stop(
                    generated,
                    adaptive,
                    sample_buffers.values,
                    output_metric_ids,
                    alpha,
                ):
                    return (
                        generated,
                        failed,
                        _QMCExecutionSummary(
                            method=qmc_method,
                            scrambled=scrambled,
                            replicate_count=actual_replicates,
                        ),
                    )

        return (
            generated,
            failed,
            _QMCExecutionSummary(
                method=qmc_method,
                scrambled=scrambled,
                replicate_count=actual_replicates,
            ),
        )

    def _run_random_loop(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        param_names: list[str],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        n_samples: int,
        batch_size: int,
        sample_buffers: _SampleBuffers,
        adaptive: Any,
        alpha: float,
        missing_outputs: dict[str, int],
        draw_outcomes: list[_DrawOutcomeRecord],
        evaluation_attempts: _EvaluationAttempts,
        empirical_spec: _EmpiricalJointSpec | None,
        gaussian_spec: _GaussianJointSpec | None,
        gaussian_trace: _GaussianExecutionTrace | None,
    ) -> tuple[int, int]:
        rng = jrandom.PRNGKey(self._config.mc_seed)
        generated = 0
        failed = 0

        while generated < n_samples:
            this_batch = self._adaptive_batch_size(
                generated=generated,
                batch_size=batch_size,
                remaining=n_samples - generated,
                adaptive=adaptive,
            )
            batch_samples: dict[str, np.ndarray | jnp.ndarray] = {}
            if gaussian_spec is not None:
                rng, joint_key = jrandom.split(rng)
                standard = jrandom.normal(joint_key, shape=(this_batch, len(param_names)))
                factor = jnp.asarray(gaussian_spec.factor.T)
                means = jnp.asarray(gaussian_spec.means)
                joint = standard @ factor + means
                if gaussian_trace is not None:
                    gaussian_trace.batches.append(
                        {
                            "first_draw": generated,
                            "draw_count": this_batch,
                            "source_dtype": str(standard.dtype),
                            "factor_dtype": str(factor.dtype),
                            "mean_dtype": str(means.dtype),
                            "joint_dtype": str(joint.dtype),
                            "device": str(joint.device.platform),
                            "prng_implementation": str(jrandom.key_impl(joint_key)),
                            "replicate_index": None,
                            "replicate_seed": None,
                        }
                    )
                batch_samples.update({name: joint[:, i] for i, name in enumerate(param_names)})
            shared_indices: jnp.ndarray | None = None
            if empirical_spec is not None:
                rng, shared_key = jrandom.split(rng)
                shared_indices = jrandom.choice(
                    shared_key,
                    empirical_spec.sample_count,
                    shape=(this_batch,),
                    p=jnp.asarray(empirical_spec.probabilities, dtype=jnp.float32),
                )
            for name in param_names:
                if gaussian_spec is not None:
                    continue
                env = input_envelopes[name]
                if empirical_spec is not None and name in empirical_spec.names:
                    assert shared_indices is not None
                    selected_indices = np.asarray(shared_indices, dtype=np.intp)
                    batch_samples[name] = empirical_spec.samples[name][selected_indices]
                    continue
                rng, subkey = jrandom.split(rng)
                batch_samples[name] = self._sample_from_envelope(subkey, env, this_batch)

            for i in range(this_batch):
                params = dict(nominal_params)
                params.update({name: batch_samples[name][i] for name in param_names})
                sample_idx = generated + i
                ok = self._eval_and_record(
                    simulation_fn,
                    params,
                    param_names,
                    output_metric_ids,
                    sample_buffers,
                    sample_idx=sample_idx,
                    missing_outputs=missing_outputs,
                    draw_outcomes=draw_outcomes,
                    evaluation_attempts=evaluation_attempts,
                )
                if not ok:
                    failed += 1

            generated += this_batch

            if adaptive.enabled and self._check_adaptive_stop(
                generated,
                adaptive,
                sample_buffers.values,
                output_metric_ids,
                alpha,
            ):
                return generated, failed

        return n_samples, failed

    def _eval_and_record(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        params: dict[str, Any],
        param_names: list[str],
        output_metric_ids: list[str],
        sample_buffers: _SampleBuffers,
        *,
        sample_idx: int,
        missing_outputs: dict[str, int],
        draw_outcomes: list[_DrawOutcomeRecord],
        evaluation_attempts: _EvaluationAttempts,
    ) -> bool:
        sampled_inputs = {name: float(params[name]) for name in param_names}
        for name, value in sampled_inputs.items():
            sample_buffers.input_samples[name][sample_idx] = value
        sampled_input_sha256: str | None = None

        def input_digest() -> str:
            nonlocal sampled_input_sha256
            if sampled_input_sha256 is None:
                sampled_input_sha256 = _sampled_input_digest(params)
            return sampled_input_sha256

        def record_failures(
            failures: Mapping[str, tuple[_DrawOutcomeCode, str | None]],
        ) -> None:
            if not failures:
                return
            draw_outcomes.append(
                _DrawOutcomeRecord(
                    draw_index=sample_idx,
                    sampled_input_sha256=input_digest(),
                    output_outcomes=tuple(
                        _DrawOutputOutcome(
                            output_metric_id=metric_id,
                            outcome_code=outcome_code,
                            error_type=error_type,
                        )
                        for metric_id, (outcome_code, error_type) in sorted(failures.items())
                    ),
                )
            )

        try:
            result = _evaluate_with_transient_retry(simulation_fn, params, evaluation_attempts)
        except Exception as exc:
            failure = classify_evaluation_failure(exc)
            if failure.scope != "unknown" or not _is_legacy_draw_local_runtime_error(
                exc, failure.chain_complete, failure.cycle_detected
            ):
                raise
            for mid in output_metric_ids:
                sample_buffers.values[mid][sample_idx] = float("nan")
            record_failures(
                dict.fromkeys(
                    output_metric_ids,
                    (_DrawOutcomeCode.SIMULATION_EXCEPTION, type(exc).__name__),
                )
            )
            return False

        if not isinstance(result, Mapping):
            for mid in output_metric_ids:
                sample_buffers.values[mid][sample_idx] = float("nan")
            record_failures(
                dict.fromkeys(
                    output_metric_ids,
                    (_DrawOutcomeCode.INVALID_RESPONSE, type(result).__name__),
                )
            )
            return False

        parsed_values: dict[str, float] = {}
        failures: dict[str, tuple[_DrawOutcomeCode, str | None]] = {}
        for mid in output_metric_ids:
            if mid not in result or result[mid] is None:
                parsed_values[mid] = float("nan")
                failures[mid] = (_DrawOutcomeCode.MISSING_OUTPUT, None)
                continue
            try:
                value = float(result[mid])
            except (TypeError, ValueError, OverflowError) as exc:
                parsed_values[mid] = float("nan")
                failures[mid] = (
                    _DrawOutcomeCode.NON_NUMERIC_OUTPUT,
                    type(exc).__name__,
                )
                continue
            if not math.isfinite(value):
                parsed_values[mid] = float("nan")
                failures[mid] = (_DrawOutcomeCode.NON_FINITE_OUTPUT, None)
                continue
            parsed_values[mid] = value

        for mid, value in parsed_values.items():
            sample_buffers.values[mid][sample_idx] = value
        for mid, (outcome_code, _error_type) in failures.items():
            if outcome_code is _DrawOutcomeCode.MISSING_OUTPUT:
                missing_outputs[mid] += 1
        record_failures(failures)
        return True

    # ------------------------------------------------------------------
    # Adaptive stopping
    # ------------------------------------------------------------------

    @staticmethod
    def _adaptive_batch_size(
        *,
        generated: int,
        batch_size: int,
        remaining: int,
        adaptive: Any,
    ) -> int:
        """Split a batch at the next adaptive stopping checkpoint.

        Adaptive evaluation is defined at generated-sample boundaries.  A
        batch may cross such a boundary, so cap it before sampling instead of
        silently skipping the checkpoint when the batch and interval differ.
        """
        this_batch = min(batch_size, remaining)
        if not adaptive.enabled:
            return this_batch

        interval = adaptive.check_interval
        next_boundary = ((generated // interval) + 1) * interval
        return min(this_batch, next_boundary - generated)

    def _check_adaptive_stop(
        self,
        n_generated: int,
        adaptive: Any,
        values: dict[str, np.ndarray],
        output_metric_ids: list[str],
        alpha: float,
    ) -> bool:
        if n_generated < adaptive.min_samples:
            return False
        if n_generated % adaptive.check_interval != 0:
            return False

        for mid in output_metric_ids:
            arr = values[mid][:n_generated]
            valid = arr[np.isfinite(arr)]
            if len(valid) < adaptive.min_samples:
                return False
            point = float(np.mean(valid))
            lo = float(np.percentile(valid, 100.0 * alpha / 2.0))
            hi = float(np.percentile(valid, 100.0 * (1.0 - alpha / 2.0)))
            half_width = (hi - lo) / max(abs(point), 1e-12)
            if half_width > adaptive.ci_half_width_target:
                return False

        logger.info("Adaptive MC stopping: converged after %d samples.", n_generated)
        return True

    @staticmethod
    def _create_sample_buffers(
        *,
        param_names: list[str],
        output_metric_ids: list[str],
        n_samples: int,
    ) -> _SampleBuffers:
        return _SampleBuffers(
            values={
                metric_id: np.full((n_samples,), np.nan, dtype=np.float64)
                for metric_id in output_metric_ids
            },
            input_samples={name: np.empty((n_samples,), dtype=np.float64) for name in param_names},
            capacity=n_samples,
        )

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    def _build_results(
        self,
        values: dict[str, np.ndarray],
        input_samples: dict[str, np.ndarray],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        param_names: list[str],
        output_metric_ids: list[str],
        nominal_params: Mapping[str, float],
        nominal_outputs: Mapping[str, float] | None,
        actual_n_samples: int,
        failed: int,
        stopped_early: bool,
        level: float,
        alpha: float,
        *,
        missing_outputs: Mapping[str, int],
        draw_outcomes: list[_DrawOutcomeRecord],
        evaluation_attempts: _EvaluationAttempts,
        requested_n_samples: int,
        qmc_summary: _QMCExecutionSummary | None,
        sample_axis: str = "draw",
        joint_sample_id: str | None = None,
        parametric_fit_names: tuple[str, ...] = (),
        declared_gaussian_joint: bool = False,
        gaussian_spec: _GaussianJointSpec | None = None,
        gaussian_trace: _GaussianExecutionTrace | None = None,
        input_envelope_digests: Mapping[str, str | None] | None = None,
        fixed_scalar_values_owned: bool = True,
        provenance_context_owned: bool = True,
        metadata_context_owned: bool = True,
        unestablished_independence: bool = False,
    ) -> list[PropagationResult]:
        from .sensitivity import compute_first_order_indices

        out: list[PropagationResult] = []
        dependency_assurance = joint_dependency_assurance(input_envelopes)
        qmc_method = None if qmc_summary is None else qmc_summary.method
        qmc_scrambled = False if qmc_summary is None else qmc_summary.scrambled
        qmc_replicates = 0 if qmc_summary is None else qmc_summary.replicate_count
        output_flavour = (
            ComposedFlavour.QUASI_MONTE_CARLO
            if qmc_method is not None
            else ComposedFlavour.MONTE_CARLO
        )
        certificate_kind = (
            CertificateKind.RQMC_REPLICATES
            if qmc_method is not None and qmc_scrambled and qmc_replicates >= 2
            else (
                CertificateKind.QMC_VARIATION
                if qmc_method is not None
                else CertificateKind.KOLMOGOROV
            )
        )
        qmc_has_full_certificate = qmc_method is not None and qmc_scrambled and qmc_replicates >= 2
        if input_envelope_digests is None:
            input_envelope_digests = {
                name: _envelope_content_digest(envelope)
                for name, envelope in input_envelopes.items()
            }
        # Recipe 1.0 binds envelopes/configuration, not fixed invocation
        # values.  Never describe an invocation with unbound fixed inputs as
        # content hashed, even when those values are immutable scalars.
        has_unbound_fixed_inputs = bool(set(nominal_params) - set(param_names))
        input_identity_complete = (
            fixed_scalar_values_owned
            and provenance_context_owned
            and metadata_context_owned
            and not has_unbound_fixed_inputs
            and all(value is not None for value in input_envelope_digests.values())
        )
        metric_failure_draw_counts = dict.fromkeys(output_metric_ids, 0)
        for draw_outcome in draw_outcomes:
            for output_outcome in draw_outcome.output_outcomes:
                metric_failure_draw_counts[output_outcome.output_metric_id] += 1
        sampling_recipe: dict[str, Any] = {
            "config": self._config.model_dump(mode="json"),
            "input_param_names": param_names,
            "input_envelope_sha256": input_envelope_digests,
            "sample_axis": sample_axis,
            "joint_sample_id": joint_sample_id,
        }
        summary_dtypes: list[str] = []
        if declared_gaussian_joint:
            if gaussian_spec is None or gaussian_trace is None:
                raise ValueError("Gaussian recipe requires the executed transform and trace")
            scipy_version = None
            if qmc_summary is not None:
                import scipy

                scipy_version = scipy.__version__
            sampling_recipe.update(
                {
                    "gaussian_joint_names": list(param_names),
                    "gaussian_joint_assumption": "multivariate_normal_with_declared_covariance",
                    "gaussian_numeric_profile": {
                        "backend": "scipy_qmc" if qmc_summary is not None else "jax_random",
                        "jax_version": jax.__version__,
                        "jaxlib_version": jaxlib.__version__,
                        "numpy_version": np.__version__,
                        "scipy_version": scipy_version,
                        "covariance_validation_dtype": str(_COVARIANCE_VALIDATION_DTYPE),
                        "covariance_storage_dtype": gaussian_spec.covariance_storage_dtype,
                        "factor_dtype": str(gaussian_spec.factor.dtype),
                        "means": gaussian_spec.means.tolist(),
                        "factor_rows": gaussian_spec.factor.tolist(),
                        "draw_batches": gaussian_trace.batches,
                        "summary_dtypes": summary_dtypes,
                        "validation_tolerances": {
                            "diagonal_rtol": _COVARIANCE_DIAGONAL_RTOL,
                            "diagonal_atol": _COVARIANCE_DIAGONAL_ATOL,
                            "symmetry_rtol": _SINGULAR_SYMMETRY_RTOL,
                            "symmetry_atol": _SINGULAR_SYMMETRY_ATOL,
                            "negative_eigenvalue_scale_rtol": _SINGULAR_PSD_SCALE_RTOL,
                        },
                        "qmc_uniform_clip": (
                            [_QMC_GAUSSIAN_UNIFORM_CLIP, 1.0 - _QMC_GAUSSIAN_UNIFORM_CLIP]
                            if qmc_summary is not None
                            else None
                        ),
                    },
                }
            )
        draw_outcome_provenance: dict[str, Any] = {
            "schema_version": "1.1" if declared_gaussian_joint else "1.0",
            "requested_draw_count": requested_n_samples,
            "attempted_draw_count": actual_n_samples,
            "simulation_attempt_count": evaluation_attempts.simulation_attempt_count,
            "retry_attempt_count": evaluation_attempts.retry_attempt_count,
            "successful_draw_count": actual_n_samples - len(draw_outcomes),
            "unattempted_draw_count": requested_n_samples - actual_n_samples,
            "outcome_denominator_complete": not stopped_early,
            "sampling_recipe": sampling_recipe,
            "input_identity_status": (
                "content_hashed" if input_identity_complete else "not_established"
            ),
            "implementation_identity_status": "not_established",
            "draw_identity_basis": "sampling_recipe+draw_index+sampled_input_sha256",
            "failure_records": [item.model_dump(mode="json") for item in draw_outcomes],
        }
        for metric_id in output_metric_ids:
            arr = jnp.asarray(values[metric_id][:actual_n_samples], dtype=jnp.float32)
            if declared_gaussian_joint and str(arr.dtype) not in summary_dtypes:
                summary_dtypes.append(str(arr.dtype))
            valid = arr[jnp.isfinite(arr)]
            n_valid = int(valid.shape[0])
            missing_count = int(missing_outputs.get(metric_id, 0))
            has_missing_output = missing_count > 0
            metric_failure_draw_count = metric_failure_draw_counts[metric_id]
            has_incomplete_draws = (
                metric_failure_draw_count > 0 or stopped_early or not input_identity_complete
            )
            interval_semantics = IntervalSemantics.CONFIDENCE_INTERVAL
            confidence_level: float | None = level
            # Sampling cannot promote a non-gate-eligible input into a gate.
            gate_eligible = all(envelope.gate_eligible for envelope in input_envelopes.values())
            exactness = ExactnessKind.APPROXIMATION
            scope = ("expectation", "interval", "quantile", "cdf")
            sample_size_value: int | None = n_valid
            distribution_payload = None
            notes: dict[str, Any] = {}

            if qmc_method is not None and not qmc_has_full_certificate:
                interval_semantics = IntervalSemantics.HEURISTIC_RANGE
                confidence_level = None
                gate_eligible = False
                exactness = ExactnessKind.CONSTRAINT_ONLY
                scope = ("expectation_bv",)
            if qmc_method is None and actual_n_samples <= 0:
                scope = ("expectation", "bounds")
            if has_incomplete_draws:
                interval_semantics = IntervalSemantics.HEURISTIC_RANGE
                confidence_level = None
                gate_eligible = False
                exactness = ExactnessKind.CONSTRAINT_ONLY
                scope = ("expectation_bv",)
            if dependency_assurance != "not_applicable":
                # Numeric sampling does not prove the joint law or its units.
                gate_eligible = False
            if joint_sample_id is not None:
                # The producer-supplied ID is a declaration, not an
                # independently reconciled row-identity proof.
                gate_eligible = False

            if n_valid < self._config.mc_min_valid_samples:
                if has_missing_output:
                    point = 0.0
                    point_source = "missing_output_unavailable"
                    confidence_interval = (-1.0, 1.0)
                else:
                    point, point_source = self._fallback_point_estimate(
                        metric_id,
                        nominal_params=nominal_params,
                        nominal_outputs=nominal_outputs,
                    )
                    confidence_interval = (point, point)
                failure_metadata = {
                    "failure": (
                        "missing_output" if has_missing_output else "insufficient_valid_samples"
                    ),
                    "mc_n_valid": n_valid,
                    "mc_n_samples": actual_n_samples,
                    "fallback_point_estimate_source": point_source,
                }
                if declared_gaussian_joint:
                    failure_metadata["joint_gaussian_basis"] = "declared_non_authoritative"
                    failure_metadata["parameter_unit_binding"] = "not_established"
                if unestablished_independence:
                    failure_metadata["joint_dependency"] = "independence_assumption_not_established"
                    failure_metadata["parameter_unit_binding"] = "not_established"
                if has_missing_output:
                    failure_metadata["missing_output_count"] = missing_count
                if has_incomplete_draws:
                    failure_metadata.update(
                        {
                            "draw_outcome_status": (
                                "adaptively_stopped" if stopped_early else "incomplete"
                            ),
                            "draw_requested_count": requested_n_samples,
                            "draw_attempted_count": actual_n_samples,
                            "draw_successful_count": n_valid,
                            "draw_failure_count": metric_failure_draw_count,
                            "draw_unattempted_count": requested_n_samples - actual_n_samples,
                            "distribution_sample_semantics": (
                                "successful_draws_only_conditional_on_execution"
                            ),
                            "candidate_only": True,
                        }
                    )
                if qmc_method is not None:
                    failure_metadata["qmc_scrambled"] = qmc_scrambled
                    failure_metadata["qmc_replicates"] = qmc_replicates
                failure_assumptions = ["empirical_push_forward"]
                if qmc_method is not None and not qmc_has_full_certificate:
                    failure_assumptions.append("restricted_qmc_scope")
                if declared_gaussian_joint:
                    failure_assumptions.append("declared_gaussian_joint")
                if unestablished_independence:
                    failure_assumptions.append("unestablished_independence")
                if sample_axis != "draw":
                    failure_assumptions.append("source_axis_preserved")
                if joint_sample_id is not None:
                    failure_assumptions.append("declared_shared_sample_identity")
                if parametric_fit_names:
                    failure_assumptions.append("typed_parametric_fit")
                envelope = UncertaintyEnvelope(
                    point_estimate=point,
                    confidence_interval=confidence_interval,
                    confidence_level=None,
                    distribution_family=DistributionFamily.UNKNOWN,
                    source=UncertaintySource.ENSEMBLE,
                    propagation_method=PropagationMethod.MONTE_CARLO,
                    interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                    sample_size=n_valid if n_valid > 0 else None,
                    is_heuristic_ci=True,
                    gate_eligible=False,
                    metadata=failure_metadata,
                    composition_provenance=build_composition_provenance(
                        input_envelopes=tuple(input_envelopes[name] for name in param_names),
                        op="push_forward",
                        stage_name="foundry.monte_carlo.push_forward",
                        output_flavour=output_flavour,
                        exactness=exactness,
                        certificate_kind=certificate_kind,
                        certificate_radius=(
                            {
                                "sample_size": float(n_valid),
                                "replicate_count": 1.0,
                            }
                            if qmc_method is not None and n_valid > 0
                            else None
                        ),
                        confidence_level=None,
                        scope=scope,
                        map_name=metric_id,
                        sample_size=n_valid if n_valid > 0 else None,
                        replicate_count=qmc_replicates if qmc_method is not None else None,
                        qmc_method=qmc_method,
                        scrambled=qmc_scrambled if qmc_method is not None else None,
                        assumptions=tuple(failure_assumptions),
                        notes=failure_metadata,
                    ),
                )
            else:
                point = float(jnp.mean(valid))
                distribution_payload = PosteriorSamplesCarrier(
                    samples=tuple(float(value) for value in np.asarray(valid, dtype=np.float64)),
                    sample_axis=sample_axis,
                )
                if qmc_method is not None and not qmc_has_full_certificate:
                    lo = float(jnp.min(valid))
                    hi = float(jnp.max(valid))
                else:
                    lo = float(jnp.percentile(valid, 100.0 * alpha / 2.0))
                    hi = float(jnp.percentile(valid, 100.0 * (1.0 - alpha / 2.0)))
                if lo > point:
                    lo = point
                if hi < point:
                    hi = point
                std = float(jnp.std(valid))

                metadata: dict[str, Any] = {
                    "joint_dependency_assurance": dependency_assurance,
                    "covariance_jitter_requested": self._config.delta_covariance_jitter,
                    "covariance_jitter_applied_to_input_law": False,
                    "mc_n_samples": actual_n_samples,
                    "mc_n_valid": n_valid,
                    "mc_n_failed": actual_n_samples - n_valid,
                    "mc_batch_size": self._config.mc_batch_size,
                    "mc_std": std,
                    "mc_seed": int(self._config.mc_seed),
                    "mc_sampling_method": self._config.mc_sampling_method,
                }
                if declared_gaussian_joint:
                    metadata["joint_gaussian_basis"] = "declared_non_authoritative"
                    metadata["parameter_unit_binding"] = "not_established"
                if unestablished_independence:
                    metadata["joint_dependency"] = "independence_assumption_not_established"
                    metadata["parameter_unit_binding"] = "not_established"
                if has_missing_output:
                    metadata["missing_output"] = metric_id
                    metadata["missing_output_count"] = missing_count
                if has_incomplete_draws:
                    metadata.update(
                        {
                            "failure": "incomplete_simulation_draws",
                            "draw_outcome_status": (
                                "adaptively_stopped" if stopped_early else "incomplete"
                            ),
                            "draw_requested_count": requested_n_samples,
                            "draw_attempted_count": actual_n_samples,
                            "draw_successful_count": n_valid,
                            "draw_failure_count": metric_failure_draw_count,
                            "draw_unattempted_count": requested_n_samples - actual_n_samples,
                            "distribution_sample_semantics": (
                                "successful_draws_only_conditional_on_execution"
                            ),
                            "candidate_only": True,
                        }
                    )
                if qmc_method is not None:
                    metadata["qmc_scrambled"] = qmc_scrambled
                    metadata["qmc_replicates"] = qmc_replicates
                if sample_axis != "draw":
                    metadata["input_sample_axis"] = sample_axis
                    metadata["empirical_source_weights_applied"] = True
                if joint_sample_id is not None:
                    metadata["empirical_joint_law"] = (
                        "explicit_shared_sample_id+axis_length_weight_compatible"
                    )
                    metadata["empirical_joint_id"] = joint_sample_id
                    metadata["empirical_joint_identity_status"] = "declared_non_authoritative"
                if parametric_fit_names:
                    metadata["parametric_fit_payload_used"] = True
                    metadata["parametric_fit_inputs"] = list(parametric_fit_names)

                if stopped_early:
                    metadata["adaptive_stopped_early"] = True

                # Tail-risk metrics
                if n_valid > 100:
                    q05 = float(jnp.percentile(valid, 5.0))
                    tail_mask = valid <= q05
                    cvar_05 = float(jnp.mean(valid[tail_mask])) if jnp.any(tail_mask) else q05
                    metadata["tail_risk"] = {
                        "cvar_05": cvar_05,
                        "quantile_01": float(jnp.percentile(valid, 1.0)),
                        "quantile_99": float(jnp.percentile(valid, 99.0)),
                    }

                # Sensitivity indices
                if (
                    self._config.compute_sensitivity
                    and n_valid >= self._config.mc_min_valid_samples
                    and len(param_names) >= 2
                ):
                    try:
                        valid_mask = np.isfinite(values[metric_id][:actual_n_samples])
                        filtered_inputs = {
                            name: input_samples[name][:actual_n_samples][valid_mask]
                            for name in param_names
                        }
                        valid_outputs = values[metric_id][:actual_n_samples][valid_mask]
                        indices = compute_first_order_indices(
                            filtered_inputs,
                            valid_outputs,
                            param_names,
                        )
                        metadata["sensitivity_indices"] = indices
                        metadata["sensitivity_method"] = "regression_first_order_proxy"
                    except Exception as exc:
                        logger.debug("Sensitivity computation failed: %s", exc)

                certificate_radius: float | dict[str, float] | None
                if qmc_method is not None and qmc_has_full_certificate:
                    certificate_radius = {
                        "sample_size": float(n_valid),
                        "replicate_count": float(qmc_replicates),
                    }
                elif qmc_method is not None:
                    certificate_radius = None
                else:
                    certificate_radius = math.sqrt(
                        math.log(2.0 / max(1.0 - level, 1e-12)) / (2.0 * max(n_valid, 1))
                    )
                notes = {
                    "mc_sampling_method": self._config.mc_sampling_method,
                    "covariance_jitter_requested": self._config.delta_covariance_jitter,
                    "covariance_jitter_applied_to_input_law": False,
                }
                if declared_gaussian_joint:
                    notes["joint_gaussian_basis"] = "declared_non_authoritative"
                    notes["parameter_unit_binding"] = "not_established"
                if unestablished_independence:
                    notes["joint_dependency"] = "independence_assumption_not_established"
                if has_missing_output:
                    notes["missing_output_count"] = missing_count
                if qmc_method is not None and not qmc_has_full_certificate:
                    notes["restricted_scope"] = "expectation_bv"
                if sample_axis != "draw":
                    notes["input_sample_axis"] = sample_axis
                    notes["empirical_source_weights_applied"] = True
                if joint_sample_id is not None:
                    notes["empirical_joint_law"] = (
                        "explicit_shared_sample_id+axis_length_weight_compatible"
                    )
                    notes["empirical_joint_id"] = joint_sample_id
                    notes["empirical_joint_identity_status"] = "declared_non_authoritative"
                assumptions = ["empirical_push_forward"]
                if declared_gaussian_joint:
                    assumptions.append("declared_gaussian_joint")
                if unestablished_independence:
                    assumptions.append("unestablished_independence")
                if sample_axis != "draw":
                    assumptions.append("source_axis_preserved")
                if joint_sample_id is not None:
                    assumptions.append("declared_shared_sample_identity")
                if parametric_fit_names:
                    assumptions.append("typed_parametric_fit")
                if qmc_has_full_certificate:
                    assumptions.append("rqmc_replicates")
                elif qmc_method is not None:
                    assumptions.append("restricted_qmc_scope")
                envelope = UncertaintyEnvelope(
                    point_estimate=point,
                    confidence_interval=(lo, hi),
                    confidence_level=confidence_level,
                    distribution_family=DistributionFamily.BOOTSTRAP,
                    source=UncertaintySource.ENSEMBLE,
                    propagation_method=PropagationMethod.MONTE_CARLO,
                    interval_semantics=interval_semantics,
                    distribution_payload=distribution_payload,
                    sample_size=sample_size_value,
                    is_heuristic_ci=interval_semantics is IntervalSemantics.HEURISTIC_RANGE,
                    gate_eligible=gate_eligible,
                    metadata=metadata,
                    composition_provenance=build_composition_provenance(
                        input_envelopes=tuple(input_envelopes[name] for name in param_names),
                        op="push_forward",
                        stage_name="foundry.monte_carlo.push_forward",
                        output_flavour=output_flavour,
                        exactness=exactness,
                        certificate_kind=certificate_kind,
                        certificate_radius=certificate_radius,
                        confidence_level=confidence_level,
                        scope=scope,
                        map_name=metric_id,
                        variance_bound=std * std,
                        sample_size=n_valid,
                        replicate_count=qmc_replicates if qmc_method is not None else None,
                        qmc_method=qmc_method,
                        scrambled=qmc_scrambled if qmc_method is not None else None,
                        assumptions=tuple(assumptions),
                        notes=notes,
                    ),
                )

            out.append(
                PropagationResult(
                    metric_id=metric_id,
                    envelope=envelope,
                    input_envelopes_used=param_names,
                    method_used=PropagationMethod.MONTE_CARLO,
                    diagnostics={
                        "n_samples": actual_n_samples,
                        "n_valid": n_valid,
                        "n_failed": actual_n_samples - n_valid,
                        "missing_output": has_missing_output,
                        "missing_output_count": missing_count,
                        "draw_outcome_provenance": draw_outcome_provenance,
                        "executor_failed_batches": failed,
                        "stopped_early": stopped_early,
                        "output_coverage_complete": not has_incomplete_draws,
                        "qmc_method": qmc_method,
                        "qmc_scrambled": qmc_scrambled if qmc_method is not None else None,
                        "qmc_replicates": qmc_replicates if qmc_method is not None else None,
                    },
                )
            )

        return out

    def _safe_nominal_outputs(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        *,
        evaluation_attempts: _EvaluationAttempts,
    ) -> Mapping[str, float] | None:
        try:
            outputs = _evaluate_with_transient_retry(
                simulation_fn, nominal_params, evaluation_attempts
            )
        except Exception as exc:
            failure = classify_evaluation_failure(exc)
            if failure.scope != "unknown" or not _is_legacy_draw_local_runtime_error(
                exc, failure.chain_complete, failure.cycle_detected
            ):
                raise
            return None
        if not isinstance(outputs, Mapping):
            return None
        safe_outputs: dict[str, float] = {}
        for key, value in outputs.items():
            try:
                safe_outputs[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return safe_outputs

    def _fallback_point_estimate(
        self,
        metric_id: str,
        *,
        nominal_params: Mapping[str, float],
        nominal_outputs: Mapping[str, float] | None,
    ) -> tuple[float, str]:
        _ = nominal_params
        if nominal_outputs is not None and metric_id in nominal_outputs:
            return float(nominal_outputs[metric_id]), "nominal_evaluation"
        return 0.0, "default_zero_nominal_unavailable"

    # ------------------------------------------------------------------
    # Sampling helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_from_envelope(rng: jax.Array, env: UncertaintyEnvelope, n: int) -> jnp.ndarray:
        point = float(env.point_estimate)
        lo, hi = env.confidence_interval
        lo = float(lo)
        hi = float(hi)

        if env.distribution_family == DistributionFamily.NORMAL:
            fit = _normal_parametric_fit(env)
            if fit is None:
                mean = point
                std = extract_std(env)
            else:
                mean, std = fit
            if std == 0.0:
                return jnp.full((n,), mean)
            return mean + std * jrandom.normal(rng, shape=(n,))

        if env.distribution_family == DistributionFamily.UNIFORM:
            return jrandom.uniform(rng, shape=(n,), minval=lo, maxval=hi)

        if env.distribution_family == DistributionFamily.TRIANGULAR:
            if hi <= lo:
                return jnp.full((n,), point)
            mode = min(max(point, lo), hi)
            u = jrandom.uniform(rng, shape=(n,))
            frac = (mode - lo) / (hi - lo)
            left = lo + jnp.sqrt(u * (hi - lo) * (mode - lo))
            right = hi - jnp.sqrt((1.0 - u) * (hi - lo) * (hi - mode))
            return jnp.where(u < frac, left, right)

        raise ValueError(f"unsupported distribution family: {env.distribution_family}")

    @staticmethod
    def _transform_qmc_samples(
        uniform_samples: np.ndarray,
        param_names: list[str],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        *,
        empirical_spec: _EmpiricalJointSpec | None = None,
        gaussian_spec: _GaussianJointSpec | None = None,
        dimension_names: tuple[str, ...] | None = None,
    ) -> dict[str, np.ndarray]:
        """Inverse CDF transform of uniform QMC samples per envelope distribution."""
        from scipy.stats import norm as sp_norm

        result: dict[str, np.ndarray] = {}
        if empirical_spec is None:
            empirical_spec, failure = _build_empirical_joint_spec(
                param_names,
                input_envelopes,
            )
            if failure is not None:
                raise ValueError(failure)
        if gaussian_spec is None:
            gaussian_spec, failure = _build_gaussian_joint_spec(param_names, input_envelopes)
            if failure is not None:
                raise ValueError(failure)
        if dimension_names is None:
            dimension_names = _qmc_dimension_names(param_names, empirical_spec)
        if gaussian_spec is not None:
            indices = [dimension_names.index(name) for name in param_names]
            uniforms = np.clip(
                uniform_samples[:, indices],
                _QMC_GAUSSIAN_UNIFORM_CLIP,
                1.0 - _QMC_GAUSSIAN_UNIFORM_CLIP,
            )
            joint = sp_norm.ppf(uniforms) @ gaussian_spec.factor.T + gaussian_spec.means
            return {name: joint[:, i] for i, name in enumerate(param_names)}
        if empirical_spec is not None:
            empirical_anchor_idx = dimension_names.index(empirical_spec.names[0])
            shared_indices = _empirical_indices_from_uniform(
                uniform_samples[:, empirical_anchor_idx],
                empirical_spec.probabilities,
            )
        else:
            shared_indices = None

        for name in param_names:
            if empirical_spec is not None and name in empirical_spec.names:
                assert shared_indices is not None
                result[name] = empirical_spec.samples[name][shared_indices]
                continue
            u = uniform_samples[:, dimension_names.index(name)]
            # Clip to avoid infinities at 0 and 1
            u = np.clip(u, 1e-10, 1.0 - 1e-10)
            env = input_envelopes[name]
            point = float(env.point_estimate)
            lo, hi = (
                float(env.confidence_interval[0]),
                float(env.confidence_interval[1]),
            )

            if env.distribution_family == DistributionFamily.NORMAL:
                fit = _normal_parametric_fit(env)
                if fit is None:
                    mean = point
                    std = extract_std(env)
                else:
                    mean, std = fit
                result[name] = (
                    np.full(u.shape, mean, dtype=np.float64)
                    if std == 0.0
                    else sp_norm.ppf(u, loc=mean, scale=std)
                )
            elif env.distribution_family == DistributionFamily.UNIFORM:
                result[name] = lo + u * (hi - lo)
            elif env.distribution_family == DistributionFamily.TRIANGULAR:
                if hi <= lo:
                    result[name] = np.full_like(u, point)
                else:
                    c = min(max((point - lo) / (hi - lo), 0.0), 1.0)
                    from scipy.stats import triang

                    result[name] = triang.ppf(u, c, loc=lo, scale=hi - lo)
            else:
                raise ValueError(f"unsupported distribution family: {env.distribution_family}")
        return result

    def _create_qmc_sampler_state(self, n_dims: int) -> dict[str, Any]:
        return self._create_qmc_sampler_state_with_seed(n_dims, seed=self._config.mc_seed)

    def _create_qmc_sampler_state_with_seed(self, n_dims: int, *, seed: int) -> dict[str, Any]:
        if self._config.mc_sampling_method == "halton":
            from scipy.stats.qmc import Halton

            return {
                "method": "halton",
                "n_dims": n_dims,
                "generated": 0,
                "sampler": Halton(
                    d=n_dims,
                    scramble=self._config.mc_qmc_scramble,
                    seed=seed,
                ),
            }

        from scipy.stats.qmc import Sobol

        return {
            "method": "sobol",
            "n_dims": n_dims,
            "generated": 0,
            "sampler": Sobol(
                d=n_dims,
                scramble=self._config.mc_qmc_scramble,
                seed=seed,
            ),
            "buffer": np.empty((0, n_dims), dtype=np.float64),
        }

    def _next_qmc_uniform_chunk(
        self,
        state: dict[str, Any],
        chunk_size: int,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        method = state["method"]
        generated = int(state["generated"])

        if method == "halton":
            sampler = state["sampler"]
            samples = sampler.random(chunk_size)
            return samples, {**state, "generated": generated + chunk_size}

        sampler = state["sampler"]
        buffered = state["buffer"]
        if buffered.shape[0] >= chunk_size:
            return (
                buffered[:chunk_size],
                {
                    **state,
                    "generated": generated + chunk_size,
                    "buffer": buffered[chunk_size:],
                },
            )

        needed = max(chunk_size - buffered.shape[0], 1)
        block_size = _next_power_of_two(needed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            new_block = sampler.random(block_size)

        available = (
            new_block if buffered.shape[0] == 0 else np.concatenate((buffered, new_block), axis=0)
        )
        samples = available[:chunk_size]
        return (
            samples,
            {
                **state,
                "generated": generated + chunk_size,
                "buffer": available[chunk_size:],
            },
        )


def _next_power_of_two(value: int) -> int:
    value = max(1, int(value))
    return 1 << (value - 1).bit_length()


def _split_evenly(total: int, parts: int) -> list[int]:
    total = max(int(total), 0)
    parts = max(int(parts), 1)
    base = total // parts
    remainder = total % parts
    return [base + (1 if idx < remainder else 0) for idx in range(parts)]
