"""Public uncertainty dispatcher module API."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import jax
import jax.numpy as jnp

from polisyos.common.logger import get_logger
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .analytical import AnalyticalPropagator
from .config import PropagationConfig
from .covariance import build_covariance_matrix, has_unknown_dependency
from .delta import DeltaMethodPropagator
from .monte_carlo import MonteCarloPropagator
from .protocol import PropagationResult
from .sampling_admission import admit_covariance_sampling_family, admit_sampling_support

logger = get_logger(__name__)


class PropagationDispatcher:
    """Propagation dispatcher public type."""

    def __init__(self, config: PropagationConfig | None = None) -> None:
        self._config = config or PropagationConfig()
        self._analytical = AnalyticalPropagator()
        self._delta = DeltaMethodPropagator(self._config)
        self._mc = MonteCarloPropagator(self._config)

    def propagate(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        *,
        is_jax_differentiable: bool = True,
        weights: Mapping[str, float] | None = None,
    ) -> list[PropagationResult]:
        if not input_envelopes or not output_metric_ids:
            return []

        param_names = sorted(input_envelopes)
        try:
            admit_sampling_support(input_envelopes)
        except (TypeError, ValueError, OverflowError):
            return _blocked_dependency_results(
                output_metric_ids,
                input_param_names=param_names,
                failure="unsupported_sampling_range_or_covariance",
            )
        if has_unknown_dependency(input_envelopes):
            return _blocked_dependency_results(
                output_metric_ids,
                input_param_names=param_names,
                failure="unknown_dependency",
            )

        try:
            admit_covariance_sampling_family(input_envelopes)
        except ValueError:
            return _blocked_dependency_results(
                output_metric_ids,
                input_param_names=param_names,
                failure="unsupported_joint_sampling_law",
            )

        if self._config.bounded_iid_mean is not None:
            return self._mc.propagate(
                simulation_fn,
                nominal_params,
                input_envelopes,
                output_metric_ids,
            )

        if _requires_monte_carlo_sampling(input_envelopes):
            return self._mc.propagate(
                simulation_fn,
                nominal_params,
                input_envelopes,
                output_metric_ids,
            )

        if (
            self._config.delta_use_full_covariance
            and all(
                env.distribution_family == DistributionFamily.NORMAL
                for env in input_envelopes.values()
            )
            and any(
                "covariance_row" in env.metadata or "covariance_params" in env.metadata
                for env in input_envelopes.values()
            )
        ):
            try:
                build_covariance_matrix(
                    param_names,
                    input_envelopes,
                    use_full_covariance=True,
                    jitter=self._config.delta_covariance_jitter,
                )
            except ValueError:
                return _blocked_dependency_results(
                    output_metric_ids,
                    input_param_names=param_names,
                    failure="incompatible_dependency",
                )

        method = self._resolve_method(
            simulation_fn,
            nominal_params,
            input_envelopes,
            output_metric_ids,
            is_jax_differentiable,
            weights=weights,
        )

        if method == PropagationMethod.ANALYTICAL:
            if weights and AnalyticalPropagator.is_applicable(input_envelopes):
                try:
                    param_names = sorted(input_envelopes)
                    covariance = build_covariance_matrix(
                        param_names,
                        input_envelopes,
                        use_full_covariance=self._config.delta_use_full_covariance,
                        jitter=self._config.delta_covariance_jitter,
                    )
                    return [
                        self._analytical.propagate_linear_combination(
                            weights=weights,
                            input_envelopes=input_envelopes,
                            output_metric_id=mid,
                            confidence_level=self._config.confidence_level,
                            covariance=covariance,
                            use_full_covariance=self._config.delta_use_full_covariance,
                        )
                        for mid in output_metric_ids
                    ]
                except Exception as exc:
                    logger.warning(
                        "Analytical propagation failed (%s). Falling back to delta method.",
                        exc,
                    )
            # Fallback: try delta, then MC
            return self._propagate_delta_with_mc_fallback(
                simulation_fn,
                nominal_params,
                input_envelopes,
                output_metric_ids,
            )

        if method == PropagationMethod.DELTA_METHOD:
            return self._propagate_delta_with_mc_fallback(
                simulation_fn,
                nominal_params,
                input_envelopes,
                output_metric_ids,
            )

        return self._mc.propagate(
            simulation_fn,
            nominal_params,
            input_envelopes,
            output_metric_ids,
        )

    def _propagate_delta_with_mc_fallback(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
    ) -> list[PropagationResult]:
        try:
            return self._delta.propagate(
                simulation_fn,
                nominal_params,
                input_envelopes,
                output_metric_ids,
            )
        except Exception as exc:
            logger.warning("Delta propagation failed (%s). Falling back to Monte Carlo.", exc)
            return self._mc.propagate(
                simulation_fn,
                nominal_params,
                input_envelopes,
                output_metric_ids,
            )

    def _resolve_method(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        is_jax_differentiable: bool,
        *,
        weights: Mapping[str, float] | None = None,
    ) -> PropagationMethod:
        preferred = (self._config.preferred_method or "auto").lower()
        if preferred == "delta":
            return PropagationMethod.DELTA_METHOD
        if preferred == "monte_carlo":
            return PropagationMethod.MONTE_CARLO
        if preferred == "analytical":
            return PropagationMethod.ANALYTICAL

        all_normal = all(
            env.distribution_family == DistributionFamily.NORMAL for env in input_envelopes.values()
        )

        # Auto-select: prefer analytical when weights are provided and all inputs are normal
        if weights and all_normal and AnalyticalPropagator.is_applicable(input_envelopes):
            return PropagationMethod.ANALYTICAL

        if not all_normal:
            return PropagationMethod.MONTE_CARLO

        if not is_jax_differentiable:
            return PropagationMethod.MONTE_CARLO

        if self._can_use_delta(simulation_fn, nominal_params, input_envelopes, output_metric_ids):
            return PropagationMethod.DELTA_METHOD
        return PropagationMethod.MONTE_CARLO

    def _can_use_delta(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
    ) -> bool:
        param_names = sorted(input_envelopes.keys())
        effective_nominal = dict(nominal_params)
        nominal = jnp.asarray(
            [float(effective_nominal[name]) for name in param_names],
            dtype=jnp.float32,
        )

        def _vectorized(theta: jnp.ndarray) -> jnp.ndarray:
            params = dict(effective_nominal)
            params.update({name: theta[idx] for idx, name in enumerate(param_names)})
            result = simulation_fn(**params)
            if not isinstance(result, Mapping):
                raise TypeError("simulation_fn must return a mapping of output metrics")
            vals = [jnp.asarray(result[mid], dtype=jnp.float32) for mid in output_metric_ids]
            return jnp.stack(vals)

        try:
            nominal_result = simulation_fn(**effective_nominal)
            if not isinstance(nominal_result, Mapping):
                return False
            if any(
                mid not in nominal_result or nominal_result[mid] is None
                for mid in output_metric_ids
            ):
                # Delta can emit a typed, non-authoritative missing-output result without
                # launching a large Monte Carlo fallback for a structural response gap.
                return True
            jax.eval_shape(lambda x: jax.jacfwd(_vectorized)(x), nominal)
            return True
        except Exception as exc:
            logger.info("Delta dry-run failed; fallback to Monte Carlo: %s", exc)
            return False


def _requires_monte_carlo_sampling(
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> bool:
    """Route empirical/unsupported families away from analytical or delta paths."""
    for envelope in input_envelopes.values():
        payload = envelope.distribution_payload
        if isinstance(payload, PosteriorSamplesCarrier):
            return True
        if isinstance(payload, ParametricFitCarrier):
            # The MC adapter is the only path that consumes the typed fit
            # parameters.  Do not let analytical/delta silently substitute
            # envelope point/CI moments for a declared law.
            return True
        if payload is not None:
            return True
        if envelope.distribution_family in {
            DistributionFamily.BOOTSTRAP,
            DistributionFamily.BAYESIAN,
            DistributionFamily.UNKNOWN,
        }:
            return True
    return False


def _blocked_dependency_results(
    output_metric_ids: list[str],
    *,
    input_param_names: list[str],
    failure: str,
) -> list[PropagationResult]:
    """Return a typed limitation without entering any propagation backend."""
    return [
        PropagationResult(
            metric_id=metric_id,
            envelope=UncertaintyEnvelope(
                point_estimate=0.0,
                confidence_interval=(-1.0, 1.0),
                confidence_level=None,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                is_heuristic_ci=True,
                gate_eligible=False,
                metadata={
                    "failure": failure,
                    "input_param_names": input_param_names,
                },
            ),
            input_envelopes_used=input_param_names,
            method_used=PropagationMethod.NONE,
            diagnostics={failure: True},
        )
        for metric_id in output_metric_ids
    ]
