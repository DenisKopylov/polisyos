"""Public uncertainty delta module API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from statistics import NormalDist

import jax
import jax.numpy as jnp

from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    ParametricFitCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    build_composition_provenance,
)

from .config import PropagationConfig
from .covariance import build_covariance_matrix, has_unknown_dependency
from .protocol import PropagationResult


class DeltaMethodPropagator:
    """Delta method propagator public type."""

    def __init__(self, config: PropagationConfig | None = None) -> None:
        self._config = config or PropagationConfig()

    @property
    def method(self) -> PropagationMethod:
        return PropagationMethod.DELTA_METHOD

    @staticmethod
    def is_applicable(input_envelopes: Mapping[str, UncertaintyEnvelope]) -> bool:
        return all(
            env.distribution_family == DistributionFamily.NORMAL
            and env.confidence_level is not None
            and not env.is_heuristic_ci
            for env in input_envelopes.values()
        )

    def propagate(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
    ) -> list[PropagationResult]:
        if not output_metric_ids:
            return []

        effective_nominal = dict(nominal_params)
        param_names = sorted(input_envelopes.keys())
        if has_unknown_dependency(input_envelopes):
            return _unknown_dependency_results(
                output_metric_ids,
                input_param_names=param_names,
                failure="unknown_dependency",
            )

        n_params = len(param_names)
        vector_nominal = jnp.asarray(
            [float(effective_nominal[name]) for name in param_names],
            dtype=jnp.float32,
        )

        nominal_result = simulation_fn(**effective_nominal)
        if not isinstance(nominal_result, Mapping):
            raise TypeError("simulation_fn must return a mapping of output metrics")

        available_metric_ids = [
            metric_id
            for metric_id in output_metric_ids
            if metric_id in nominal_result and nominal_result[metric_id] is not None
        ]
        missing_metric_ids = [
            metric_id for metric_id in output_metric_ids if metric_id not in available_metric_ids
        ]

        try:
            cov = build_covariance_matrix(
                param_names,
                input_envelopes,
                use_full_covariance=self._config.delta_use_full_covariance,
                jitter=self._config.delta_covariance_jitter,
            )
        except ValueError:
            return _unknown_dependency_results(
                output_metric_ids,
                input_param_names=param_names,
                failure="incompatible_dependency",
            )

        def _vectorized_fn(theta: jnp.ndarray) -> jnp.ndarray:
            params = dict(effective_nominal)
            params.update({name: theta[idx] for idx, name in enumerate(param_names)})
            result = simulation_fn(**params)
            values: list[jnp.ndarray] = []
            for metric_id in available_metric_ids:
                values.append(jnp.asarray(result[metric_id], dtype=jnp.float32))
            return jnp.stack(values)

        level = self._config.confidence_level
        z = NormalDist().inv_cdf((1.0 + level) / 2.0)

        if available_metric_ids:
            jacobian = jax.jacfwd(_vectorized_fn)(vector_nominal)
            output_cov = jacobian @ cov @ jacobian.T
            output_var = jnp.clip(jnp.diag(output_cov), a_min=0.0)
            output_std = jnp.sqrt(output_var)
            nominal_out = _vectorized_fn(vector_nominal)
        else:
            jacobian = jnp.empty((0, n_params), dtype=jnp.float32)
            output_var = jnp.empty((0,), dtype=jnp.float32)
            output_std = jnp.empty((0,), dtype=jnp.float32)
            nominal_out = jnp.empty((0,), dtype=jnp.float32)

        result_by_metric: dict[str, PropagationResult] = {}
        for idx, metric_id in enumerate(available_metric_ids):
            point = float(nominal_out[idx])
            std = float(output_std[idx])
            lo = point - z * std
            hi = point + z * std
            envelope = UncertaintyEnvelope(
                point_estimate=point,
                confidence_interval=(float(lo), float(hi)),
                confidence_level=level,
                distribution_family=DistributionFamily.NORMAL,
                distribution_payload=ParametricFitCarrier(
                    family=DistributionFamily.NORMAL,
                    parameters={"mean": float(point), "std": float(std)},
                ),
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.DELTA_METHOD,
                interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
                is_heuristic_ci=False,
                # Preserve the weakest input authority through push-forward.
                gate_eligible=all(
                    envelope.gate_eligible for envelope in input_envelopes.values()
                ),
                metadata={
                    "n_input_params": n_params,
                    "input_param_names": param_names,
                    "jacobian_row_norm": float(jnp.linalg.norm(jacobian[idx])),
                    "used_full_covariance": bool(self._config.delta_use_full_covariance),
                    "output_std": std,
                },
                composition_provenance=build_composition_provenance(
                    input_envelopes=tuple(input_envelopes.values()),
                    op="push_forward",
                    stage_name="foundry.delta.push_forward",
                    output_flavour=ComposedFlavour.DELTA,
                    exactness=ExactnessKind.APPROXIMATION,
                    certificate_kind=CertificateKind.TAYLOR_REMAINDER,
                    certificate_radius=std,
                    confidence_level=level,
                    scope=("expectation", "interval", "quantile", "cdf"),
                    map_name=metric_id,
                    variance_bound=float(output_var[idx]),
                    assumptions=("jax_jacobian_linearization",),
                    notes={
                        "used_full_covariance": bool(self._config.delta_use_full_covariance),
                    },
                ),
            )
            result_by_metric[metric_id] = PropagationResult(
                metric_id=metric_id,
                envelope=envelope,
                input_envelopes_used=param_names,
                method_used=PropagationMethod.DELTA_METHOD,
                diagnostics={
                    "jacobian_norm": float(jnp.linalg.norm(jacobian[idx])),
                    "output_variance": float(output_var[idx]),
                },
            )

        for metric_id in missing_metric_ids:
            result_by_metric[metric_id] = _missing_output_result(
                metric_id,
                input_param_names=param_names,
            )

        return [result_by_metric[metric_id] for metric_id in output_metric_ids]


def _missing_output_result(
    metric_id: str,
    *,
    input_param_names: list[str],
) -> PropagationResult:
    """Return a non-authoritative result for an output absent from the response."""

    return PropagationResult(
        metric_id=metric_id,
        envelope=UncertaintyEnvelope(
            point_estimate=0.0,
            confidence_interval=(-1.0, 1.0),
            confidence_level=None,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.DELTA_METHOD,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            is_heuristic_ci=True,
            gate_eligible=False,
            metadata={
                "failure": "missing_output",
                "missing_output": metric_id,
                "input_param_names": input_param_names,
            },
        ),
        input_envelopes_used=input_param_names,
        method_used=PropagationMethod.DELTA_METHOD,
        diagnostics={"missing_output": True},
    )


def _unknown_dependency_results(
    output_metric_ids: list[str],
    *,
    input_param_names: list[str],
    failure: str,
) -> list[PropagationResult]:
    """Return non-authoritative results when no joint input law is established."""
    return [
        PropagationResult(
            metric_id=metric_id,
            envelope=UncertaintyEnvelope(
                point_estimate=0.0,
                confidence_interval=(-1.0, 1.0),
                confidence_level=None,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.DELTA_METHOD,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                is_heuristic_ci=True,
                gate_eligible=False,
                metadata={
                    "failure": failure,
                    "input_param_names": input_param_names,
                },
            ),
            input_envelopes_used=input_param_names,
            method_used=PropagationMethod.DELTA_METHOD,
            diagnostics={failure: True},
        )
        for metric_id in output_metric_ids
    ]
