from __future__ import annotations

from typing import Callable, Mapping

import jax
import jax.numpy as jnp
import jax.random as jrandom

from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .config import PropagationConfig
from .covariance import extract_std
from .protocol import PropagationResult


class MonteCarloPropagator:
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
        n_samples = self._config.mc_n_samples
        batch_size = min(self._config.mc_batch_size, n_samples)
        level = self._config.confidence_level
        alpha = 1.0 - level

        values: dict[str, list[float]] = {metric_id: [] for metric_id in output_metric_ids}
        failed = 0
        rng = jrandom.PRNGKey(self._config.mc_seed)

        generated = 0
        while generated < n_samples:
            this_batch = min(batch_size, n_samples - generated)
            batch_samples: dict[str, jnp.ndarray] = {}
            for name in param_names:
                rng, subkey = jrandom.split(rng)
                env = input_envelopes[name]
                batch_samples[name] = self._sample_from_envelope(subkey, env, this_batch)

            for i in range(this_batch):
                params = {name: batch_samples[name][i] for name in param_names}
                try:
                    result = simulation_fn(**params)
                    for metric_id in output_metric_ids:
                        raw = result.get(metric_id)
                        if raw is None:
                            values[metric_id].append(float("nan"))
                        else:
                            values[metric_id].append(float(raw))
                except Exception:  # pragma: no cover - defensive fallback
                    failed += 1
                    for metric_id in output_metric_ids:
                        values[metric_id].append(float("nan"))
            generated += this_batch

        out: list[PropagationResult] = []
        for metric_id in output_metric_ids:
            arr = jnp.asarray(values[metric_id], dtype=jnp.float32)
            valid = arr[jnp.isfinite(arr)]
            n_valid = int(valid.shape[0])

            if n_valid < self._config.mc_min_valid_samples:
                point = float(nominal_params.get(metric_id, 0.0))
                envelope = UncertaintyEnvelope(
                    point_estimate=point,
                    confidence_interval=(point, point),
                    confidence_level=None,
                    distribution_family=DistributionFamily.UNKNOWN,
                    source=UncertaintySource.ENSEMBLE,
                    propagation_method=PropagationMethod.MONTE_CARLO,
                    interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                    sample_size=n_valid if n_valid > 0 else None,
                    is_heuristic_ci=True,
                    gate_eligible=False,
                    metadata={
                        "failure": "insufficient_valid_samples",
                        "mc_n_valid": n_valid,
                        "mc_n_samples": n_samples,
                    },
                )
            else:
                point = float(jnp.mean(valid))
                lo = float(jnp.percentile(valid, 100.0 * alpha / 2.0))
                hi = float(jnp.percentile(valid, 100.0 * (1.0 - alpha / 2.0)))
                if lo > point:
                    lo = point
                if hi < point:
                    hi = point
                std = float(jnp.std(valid))
                envelope = UncertaintyEnvelope(
                    point_estimate=point,
                    confidence_interval=(lo, hi),
                    confidence_level=level,
                    distribution_family=DistributionFamily.BOOTSTRAP,
                    source=UncertaintySource.ENSEMBLE,
                    propagation_method=PropagationMethod.MONTE_CARLO,
                    interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
                    sample_size=n_valid,
                    is_heuristic_ci=False,
                    gate_eligible=True,
                    metadata={
                        "mc_n_samples": n_samples,
                        "mc_n_valid": n_valid,
                        "mc_n_failed": n_samples - n_valid,
                        "mc_batch_size": batch_size,
                        "mc_std": std,
                        "mc_seed": int(self._config.mc_seed),
                    },
                )

            out.append(
                PropagationResult(
                    metric_id=metric_id,
                    envelope=envelope,
                    input_envelopes_used=param_names,
                    method_used=PropagationMethod.MONTE_CARLO,
                    diagnostics={
                        "n_samples": n_samples,
                        "n_valid": n_valid,
                        "n_failed": n_samples - n_valid,
                        "executor_failed_batches": failed,
                    },
                )
            )

        return out

    @staticmethod
    def _sample_from_envelope(rng: jax.Array, env: UncertaintyEnvelope, n: int) -> jnp.ndarray:
        point = float(env.point_estimate)
        lo, hi = env.confidence_interval
        lo = float(lo)
        hi = float(hi)

        if env.distribution_family == DistributionFamily.NORMAL:
            std = max(extract_std(env), 1e-12)
            return point + std * jrandom.normal(rng, shape=(n,))

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

        std = max((hi - lo) / 4.0, 1e-12)
        return point + std * jrandom.normal(rng, shape=(n,))
