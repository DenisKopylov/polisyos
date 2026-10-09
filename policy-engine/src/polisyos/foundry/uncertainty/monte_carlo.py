"""Public uncertainty monte carlo module API."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real
from typing import Any, Literal

import jax
import jax.numpy as jnp
import jax.random as jrandom
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.logger import get_logger
from polisyos.ir.analytics.posterior_summary import (
    PosteriorPointRole,
    PosteriorSummaryV11,
    summarize_posterior_draw_artifact,
)
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
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
from polisyos.ir.registry.refs import ArtifactRefModel

from .config import PropagationConfig
from .covariance import extract_std, has_unknown_dependency
from .protocol import PropagationResult

logger = get_logger(__name__)


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
    row_evaluation_semantics: Literal["one_evaluator_call_per_source_draw"] = (
        "one_evaluator_call_per_source_draw"
    )
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
        return self


def _evaluate_posterior_outputs(
    simulation_fn: Callable[..., Mapping[str, float]],
    nominal_params: Mapping[str, float],
    parameter_names: tuple[str, ...],
    parameter_values: tuple[float, ...],
    output_metric_ids: tuple[str, ...],
) -> tuple[
    dict[str, float | None],
    dict[str, tuple[PosteriorPushforwardOutcomeCode, str | None] | None],
]:
    """Evaluate one posterior row while retaining each requested output failure."""
    params = dict(nominal_params)
    params.update(dict(zip(parameter_names, parameter_values, strict=True)))
    try:
        response = simulation_fn(**params)
    except Exception as exc:  # An evaluator failure is one unavailable candidate row.
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
            failures[metric_id] = (PosteriorPushforwardOutcomeCode.NON_NUMERIC_OUTPUT, None)
            continue
        value = float(raw_value)
        if not math.isfinite(value):
            values[metric_id] = None
            failures[metric_id] = (PosteriorPushforwardOutcomeCode.NON_FINITE_OUTPUT, None)
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


def _envelope_content_digest(envelope: UncertaintyEnvelope) -> str | None:
    """Return a stable content binding, or None when the payload is not JSON-safe."""
    try:
        payload = json.dumps(
            envelope.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload).hexdigest()


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
    for carrier in carriers.values():
        if carrier.sample_axis.strip() != axis or len(carrier.samples) != sample_count:
            return None, "incompatible_joint_law"
        weights = (
            np.ones(sample_count, dtype=np.float64)
            if carrier.weights is None
            else np.asarray(carrier.weights, dtype=np.float64)
        )
        if (
            weights.shape != (sample_count,)
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
            samples={
                name: np.asarray(carrier.samples, dtype=np.float64)
                for name, carrier in carriers.items()
            },
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
        if not output_metric_ids:
            return []

        param_names = sorted(input_envelopes.keys())
        if has_unknown_dependency(input_envelopes):
            return _unknown_joint_results(
                output_metric_ids,
                input_param_names=param_names,
                failure="unknown_dependency",
            )
        empirical_spec, empirical_failure = _build_empirical_joint_spec(
            param_names,
            input_envelopes,
        )
        if empirical_failure is not None:
            return _unknown_joint_results(
                output_metric_ids,
                input_param_names=param_names,
                failure=empirical_failure,
            )
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
        failed = 0
        stopped_early = False
        actual_n_samples = 0
        nominal_outputs = self._safe_nominal_outputs(simulation_fn, nominal_params)
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
                empirical_spec,
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
                empirical_spec,
            )
            stopped_early = adaptive.enabled and actual_n_samples < n_samples

        return self._build_results(
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
            requested_n_samples=n_samples,
            qmc_summary=qmc_summary,
            sample_axis=(empirical_spec.sample_axis if empirical_spec is not None else "draw"),
            joint_sample_id=(
                empirical_spec.joint_sample_id if empirical_spec is not None else None
            ),
            parametric_fit_names=_parametric_fit_names(input_envelopes),
        )

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

        selected_values, selected_failures = _evaluate_posterior_outputs(
            simulation_fn,
            nominal_params,
            parameter_names,
            selected_input_point,
            output_metric_ids,
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
            row_evaluation_semantics="one_evaluator_call_per_source_draw",
            selected_input_point=selected_input_point,
            joint_input_matrix=joint_input_matrix,
            output_metric_ids=output_metric_ids,
            output_summaries=output_summaries,
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
        empirical_spec: _EmpiricalJointSpec | None,
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
                    dimension_names=qmc_dimension_names,
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
        empirical_spec: _EmpiricalJointSpec | None,
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
            result = simulation_fn(**params)
        except Exception as exc:
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
                failures[mid] = (_DrawOutcomeCode.NON_NUMERIC_OUTPUT, type(exc).__name__)
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
        requested_n_samples: int,
        qmc_summary: _QMCExecutionSummary | None,
        sample_axis: str = "draw",
        joint_sample_id: str | None = None,
        parametric_fit_names: tuple[str, ...] = (),
    ) -> list[PropagationResult]:
        from .sensitivity import compute_first_order_indices

        out: list[PropagationResult] = []
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
        input_envelope_digests = {
            name: _envelope_content_digest(envelope) for name, envelope in input_envelopes.items()
        }
        input_identity_complete = all(
            value is not None for value in input_envelope_digests.values()
        )
        metric_failure_draw_counts = dict.fromkeys(output_metric_ids, 0)
        for draw_outcome in draw_outcomes:
            for output_outcome in draw_outcome.output_outcomes:
                metric_failure_draw_counts[output_outcome.output_metric_id] += 1
        draw_outcome_provenance: dict[str, Any] = {
            "schema_version": "1.0",
            "requested_draw_count": requested_n_samples,
            "attempted_draw_count": actual_n_samples,
            "successful_draw_count": actual_n_samples - len(draw_outcomes),
            "unattempted_draw_count": requested_n_samples - actual_n_samples,
            "outcome_denominator_complete": not stopped_early,
            "sampling_recipe": {
                "config": self._config.model_dump(mode="json"),
                "input_param_names": param_names,
                "input_envelope_sha256": input_envelope_digests,
                "sample_axis": sample_axis,
                "joint_sample_id": joint_sample_id,
            },
            "input_identity_status": (
                "content_hashed" if input_identity_complete else "not_established"
            ),
            "implementation_identity_status": "not_established",
            "draw_identity_basis": "sampling_recipe+draw_index+sampled_input_sha256",
            "failure_records": [item.model_dump(mode="json") for item in draw_outcomes],
        }
        for metric_id in output_metric_ids:
            arr = jnp.asarray(values[metric_id][:actual_n_samples], dtype=jnp.float32)
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
                        assumptions=(
                            ("empirical_push_forward", "restricted_qmc_scope")
                            if qmc_method is not None and not qmc_has_full_certificate
                            else ("empirical_push_forward",)
                        ),
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
                    "mc_n_samples": actual_n_samples,
                    "mc_n_valid": n_valid,
                    "mc_n_failed": actual_n_samples - n_valid,
                    "mc_batch_size": self._config.mc_batch_size,
                    "mc_std": std,
                    "mc_seed": int(self._config.mc_seed),
                    "mc_sampling_method": self._config.mc_sampling_method,
                }
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
                notes = {"mc_sampling_method": self._config.mc_sampling_method}
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
    ) -> Mapping[str, float] | None:
        try:
            outputs = simulation_fn(**nominal_params)
        except Exception:
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
            return mean + max(std, 1e-12) * jrandom.normal(rng, shape=(n,))

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
        if dimension_names is None:
            dimension_names = _qmc_dimension_names(param_names, empirical_spec)
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
            lo, hi = float(env.confidence_interval[0]), float(env.confidence_interval[1])

            if env.distribution_family == DistributionFamily.NORMAL:
                fit = _normal_parametric_fit(env)
                if fit is None:
                    mean = point
                    std = extract_std(env)
                else:
                    mean, std = fit
                result[name] = sp_norm.ppf(u, loc=mean, scale=max(std, 1e-12))
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
        n_dims = int(state["n_dims"])

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
