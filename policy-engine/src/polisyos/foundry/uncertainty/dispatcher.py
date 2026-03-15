from __future__ import annotations

from typing import Callable, Mapping

import jax
import jax.numpy as jnp

from polisyos.common.logger import get_logger
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    PropagationMethod,
    UncertaintyEnvelope,
)

from .config import PropagationConfig
from .delta import DeltaMethodPropagator
from .monte_carlo import MonteCarloPropagator
from .protocol import PropagationResult

logger = get_logger(__name__)


class PropagationDispatcher:
    def __init__(self, config: PropagationConfig | None = None) -> None:
        self._config = config or PropagationConfig()
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
    ) -> list[PropagationResult]:
        if not input_envelopes or not output_metric_ids:
            return []

        method = self._resolve_method(
            simulation_fn,
            nominal_params,
            input_envelopes,
            output_metric_ids,
            is_jax_differentiable,
        )

        if method == PropagationMethod.DELTA_METHOD:
            try:
                return self._delta.propagate(
                    simulation_fn,
                    nominal_params,
                    input_envelopes,
                    output_metric_ids,
                )
            except Exception as exc:  # pragma: no cover - robustness fallback
                logger.warning("Delta propagation failed (%s). Falling back to Monte Carlo.", exc)
                return self._mc.propagate(
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

    def _resolve_method(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        nominal_params: Mapping[str, float],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        is_jax_differentiable: bool,
    ) -> PropagationMethod:
        preferred = (self._config.preferred_method or "auto").lower()
        if preferred == "delta":
            return PropagationMethod.DELTA_METHOD
        if preferred == "monte_carlo":
            return PropagationMethod.MONTE_CARLO
        if preferred == "analytical":
            return PropagationMethod.MONTE_CARLO

        all_normal = all(
            env.distribution_family == DistributionFamily.NORMAL for env in input_envelopes.values()
        )
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
        nominal = jnp.asarray(
            [float(nominal_params[name]) for name in param_names],
            dtype=jnp.float32,
        )

        def _vectorized(theta: jnp.ndarray) -> jnp.ndarray:
            params = {name: theta[idx] for idx, name in enumerate(param_names)}
            result = simulation_fn(**params)
            vals = [
                jnp.asarray(result.get(mid, 0.0), dtype=jnp.float32)
                for mid in output_metric_ids
            ]
            return jnp.stack(vals)

        try:
            jax.eval_shape(lambda x: jax.jacfwd(_vectorized)(x), nominal)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.info("Delta dry-run failed; fallback to Monte Carlo: %s", exc)
            return False
