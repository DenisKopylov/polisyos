"""Public uncertainty monte carlo module API."""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import jax
import jax.numpy as jnp
import jax.random as jrandom
import numpy as np

from polisyos.common.logger import get_logger
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
            qmc_summary=qmc_summary,
            sample_axis=(empirical_spec.sample_axis if empirical_spec is not None else "draw"),
            joint_sample_id=(empirical_spec.joint_sample_id if empirical_spec is not None else None),
            parametric_fit_names=_parametric_fit_names(input_envelopes),
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
                this_batch = min(batch_size, replicate_size - generated_this_replicate)
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
        empirical_spec: _EmpiricalJointSpec | None,
    ) -> tuple[int, int]:
        rng = jrandom.PRNGKey(self._config.mc_seed)
        generated = 0
        failed = 0

        while generated < n_samples:
            this_batch = min(batch_size, n_samples - generated)
            batch_samples: dict[str, jnp.ndarray] = {}
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
                    batch_samples[name] = jnp.asarray(
                        empirical_spec.samples[name],
                        dtype=jnp.float32,
                    )[shared_indices]
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
    ) -> bool:
        for name in param_names:
            sample_buffers.input_samples[name][sample_idx] = float(params[name])
        try:
            result = simulation_fn(**params)
            if not isinstance(result, Mapping):
                raise TypeError("simulation_fn must return a mapping of output metrics")
            for mid in output_metric_ids:
                if mid not in result or result[mid] is None:
                    missing_outputs[mid] += 1
                    sample_buffers.values[mid][sample_idx] = float("nan")
                    continue
                sample_buffers.values[mid][sample_idx] = float(result[mid])
            return True
        except Exception:
            for mid in output_metric_ids:
                sample_buffers.values[mid][sample_idx] = float("nan")
            return False

    # ------------------------------------------------------------------
    # Adaptive stopping
    # ------------------------------------------------------------------

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
        for metric_id in output_metric_ids:
            arr = jnp.asarray(values[metric_id][:actual_n_samples], dtype=jnp.float32)
            valid = arr[jnp.isfinite(arr)]
            n_valid = int(valid.shape[0])
            missing_count = int(missing_outputs.get(metric_id, 0))
            has_missing_output = missing_count > 0
            interval_semantics = IntervalSemantics.CONFIDENCE_INTERVAL
            confidence_level: float | None = level
            # Sampling cannot promote a non-gate-eligible input into a gate.
            gate_eligible = all(
                envelope.gate_eligible for envelope in input_envelopes.values()
            )
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
            if has_missing_output:
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
                        "missing_output"
                        if has_missing_output
                        else "insufficient_valid_samples"
                    ),
                    "mc_n_valid": n_valid,
                    "mc_n_samples": actual_n_samples,
                    "fallback_point_estimate_source": point_source,
                }
                if has_missing_output:
                    failure_metadata["missing_output_count"] = missing_count
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
                        "missing_output_count": missing_count,
                        "executor_failed_batches": failed,
                        "stopped_early": stopped_early,
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
