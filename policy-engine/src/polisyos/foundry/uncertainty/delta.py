from __future__ import annotations

from statistics import NormalDist
from typing import Callable, Mapping

import jax
import jax.numpy as jnp

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .config import PropagationConfig
from .covariance import build_covariance_matrix
from .protocol import PropagationResult


class DeltaMethodPropagator:
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

        param_names = sorted(input_envelopes.keys())
        n_params = len(param_names)
        vector_nominal = jnp.asarray(
            [float(nominal_params[name]) for name in param_names],
            dtype=jnp.float32,
        )

        cov = build_covariance_matrix(
            param_names,
            input_envelopes,
            use_full_covariance=self._config.delta_use_full_covariance,
            jitter=self._config.delta_covariance_jitter,
        )

        def _vectorized_fn(theta: jnp.ndarray) -> jnp.ndarray:
            params = {name: theta[idx] for idx, name in enumerate(param_names)}
            result = simulation_fn(**params)
            values: list[jnp.ndarray] = []
            for metric_id in output_metric_ids:
                raw = result.get(metric_id, jnp.asarray(0.0, dtype=jnp.float32))
                values.append(jnp.asarray(raw, dtype=jnp.float32))
            return jnp.stack(values)

        jacobian = jax.jacfwd(_vectorized_fn)(vector_nominal)
        output_cov = jacobian @ cov @ jacobian.T
        output_var = jnp.clip(jnp.diag(output_cov), a_min=0.0)
        output_std = jnp.sqrt(output_var)
        nominal_out = _vectorized_fn(vector_nominal)

        level = self._config.confidence_level
        z = NormalDist().inv_cdf((1.0 + level) / 2.0)

        out: list[PropagationResult] = []
        for idx, metric_id in enumerate(output_metric_ids):
            point = float(nominal_out[idx])
            std = float(output_std[idx])
            lo = point - z * std
            hi = point + z * std
            envelope = UncertaintyEnvelope(
                point_estimate=point,
                confidence_interval=(float(lo), float(hi)),
                confidence_level=level,
                distribution_family=DistributionFamily.NORMAL,
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.DELTA_METHOD,
                interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
                is_heuristic_ci=False,
                gate_eligible=True,
                metadata={
                    "n_input_params": n_params,
                    "input_param_names": param_names,
                    "jacobian_row_norm": float(jnp.linalg.norm(jacobian[idx])),
                    "used_full_covariance": bool(self._config.delta_use_full_covariance),
                    "output_std": std,
                },
            )
            out.append(
                PropagationResult(
                    metric_id=metric_id,
                    envelope=envelope,
                    input_envelopes_used=param_names,
                    method_used=PropagationMethod.DELTA_METHOD,
                    diagnostics={
                        "jacobian_norm": float(jnp.linalg.norm(jacobian[idx])),
                        "output_variance": float(output_var[idx]),
                    },
                )
            )

        return out
