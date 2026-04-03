"""Public uncertainty monte carlo module API."""
from __future__ import annotations

from typing import Any, Callable, Mapping

import jax
import jax.numpy as jnp
import jax.random as jrandom
import numpy as np

from polisyos.common.logger import get_logger
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .config import PropagationConfig
from .covariance import extract_std
from .protocol import PropagationResult
from .quasi_mc import QuasiMCSampler

logger = get_logger(__name__)


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
        level = self._config.confidence_level
        alpha = 1.0 - level

        adaptive = self._config.adaptive_stopping
        if adaptive.enabled:
            n_samples = adaptive.max_samples
        else:
            n_samples = self._config.mc_n_samples

        batch_size = min(self._config.mc_batch_size, n_samples)

        values: dict[str, list[float]] = {mid: [] for mid in output_metric_ids}
        input_samples: dict[str, list[float]] = {name: [] for name in param_names}
        failed = 0
        stopped_early = False
        actual_n_samples = 0

        use_qmc = self._config.mc_sampling_method != "random"

        if use_qmc:
            actual_n_samples, failed = self._run_qmc_loop(
                simulation_fn, param_names, input_envelopes, output_metric_ids,
                n_samples, values, input_samples, adaptive, alpha,
            )
            stopped_early = adaptive.enabled and actual_n_samples < n_samples
        else:
            actual_n_samples, failed = self._run_random_loop(
                simulation_fn, param_names, input_envelopes, output_metric_ids,
                n_samples, batch_size, values, input_samples, adaptive, alpha,
            )
            stopped_early = adaptive.enabled and actual_n_samples < n_samples

        return self._build_results(
            values, input_samples, param_names, output_metric_ids,
            nominal_params, actual_n_samples, failed, stopped_early,
            level, alpha,
        )

    # ------------------------------------------------------------------
    # Sampling loops
    # ------------------------------------------------------------------

    def _run_qmc_loop(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        param_names: list[str],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        n_samples: int,
        values: dict[str, list[float]],
        input_samples: dict[str, list[float]],
        adaptive: Any,
        alpha: float,
    ) -> tuple[int, int]:
        qmc_sampler = QuasiMCSampler(
            method=self._config.mc_sampling_method,
            seed=self._config.mc_seed,
        )
        uniform_samples = qmc_sampler.sample(n_samples, len(param_names))
        qmc_transformed = self._transform_qmc_samples(
            uniform_samples, param_names, input_envelopes,
        )

        failed = 0
        for i in range(n_samples):
            params = {name: float(qmc_transformed[name][i]) for name in param_names}
            self._eval_and_record(
                simulation_fn, params, param_names, output_metric_ids,
                values, input_samples,
            )

            if adaptive.enabled and self._check_adaptive_stop(
                i + 1, adaptive, values, output_metric_ids, alpha,
            ):
                return i + 1, failed

        return n_samples, failed

    def _run_random_loop(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        param_names: list[str],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        n_samples: int,
        batch_size: int,
        values: dict[str, list[float]],
        input_samples: dict[str, list[float]],
        adaptive: Any,
        alpha: float,
    ) -> tuple[int, int]:
        rng = jrandom.PRNGKey(self._config.mc_seed)
        generated = 0
        failed = 0

        while generated < n_samples:
            this_batch = min(batch_size, n_samples - generated)
            batch_samples: dict[str, jnp.ndarray] = {}
            for name in param_names:
                rng, subkey = jrandom.split(rng)
                env = input_envelopes[name]
                batch_samples[name] = self._sample_from_envelope(subkey, env, this_batch)

            for i in range(this_batch):
                params = {name: batch_samples[name][i] for name in param_names}
                ok = self._eval_and_record(
                    simulation_fn, params, param_names, output_metric_ids,
                    values, input_samples,
                )
                if not ok:
                    failed += 1

            generated += this_batch

            if adaptive.enabled and self._check_adaptive_stop(
                generated, adaptive, values, output_metric_ids, alpha,
            ):
                return generated, failed

        return n_samples, failed

    def _eval_and_record(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        params: dict[str, Any],
        param_names: list[str],
        output_metric_ids: list[str],
        values: dict[str, list[float]],
        input_samples: dict[str, list[float]],
    ) -> bool:
        for name in param_names:
            input_samples[name].append(float(params[name]))
        try:
            result = simulation_fn(**params)
            for mid in output_metric_ids:
                raw = result.get(mid)
                values[mid].append(float("nan") if raw is None else float(raw))
            return True
        except Exception:
            for mid in output_metric_ids:
                values[mid].append(float("nan"))
            return False

    # ------------------------------------------------------------------
    # Adaptive stopping
    # ------------------------------------------------------------------

    def _check_adaptive_stop(
        self,
        n_generated: int,
        adaptive: Any,
        values: dict[str, list[float]],
        output_metric_ids: list[str],
        alpha: float,
    ) -> bool:
        if n_generated < adaptive.min_samples:
            return False
        if n_generated % adaptive.check_interval != 0:
            return False

        for mid in output_metric_ids:
            arr = np.array(values[mid], dtype=np.float64)
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

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    def _build_results(
        self,
        values: dict[str, list[float]],
        input_samples: dict[str, list[float]],
        param_names: list[str],
        output_metric_ids: list[str],
        nominal_params: Mapping[str, float],
        actual_n_samples: int,
        failed: int,
        stopped_early: bool,
        level: float,
        alpha: float,
    ) -> list[PropagationResult]:
        from .sensitivity import compute_first_order_indices

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
                        "mc_n_samples": actual_n_samples,
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

                metadata: dict[str, Any] = {
                    "mc_n_samples": actual_n_samples,
                    "mc_n_valid": n_valid,
                    "mc_n_failed": actual_n_samples - n_valid,
                    "mc_batch_size": self._config.mc_batch_size,
                    "mc_std": std,
                    "mc_seed": int(self._config.mc_seed),
                    "mc_sampling_method": self._config.mc_sampling_method,
                }

                if stopped_early:
                    metadata["adaptive_stopped_early"] = True

                # Tail-risk metrics
                if n_valid > 100:
                    q05 = float(jnp.percentile(valid, 5.0))
                    tail_mask = valid <= q05
                    cvar_05 = (
                        float(jnp.mean(valid[tail_mask]))
                        if jnp.any(tail_mask)
                        else q05
                    )
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
                        valid_mask = np.isfinite(
                            np.array(values[metric_id], dtype=np.float64),
                        )
                        filtered_inputs = {
                            name: np.array(input_samples[name], dtype=np.float64)[valid_mask]
                            for name in param_names
                        }
                        valid_outputs = np.array(values[metric_id], dtype=np.float64)[valid_mask]
                        indices = compute_first_order_indices(
                            filtered_inputs, valid_outputs, param_names,
                        )
                        metadata["sensitivity_indices"] = indices
                        metadata["sensitivity_method"] = "regression_first_order_proxy"
                    except Exception as exc:
                        logger.debug("Sensitivity computation failed: %s", exc)

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
                    metadata=metadata,
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
                        "executor_failed_batches": failed,
                        "stopped_early": stopped_early,
                    },
                )
            )

        return out

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

    @staticmethod
    def _transform_qmc_samples(
        uniform_samples: np.ndarray,
        param_names: list[str],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
    ) -> dict[str, np.ndarray]:
        """Inverse CDF transform of uniform QMC samples per envelope distribution."""
        from scipy.stats import norm as sp_norm

        result: dict[str, np.ndarray] = {}
        for dim_idx, name in enumerate(param_names):
            u = uniform_samples[:, dim_idx]
            # Clip to avoid infinities at 0 and 1
            u = np.clip(u, 1e-10, 1.0 - 1e-10)
            env = input_envelopes[name]
            point = float(env.point_estimate)
            lo, hi = float(env.confidence_interval[0]), float(env.confidence_interval[1])

            if env.distribution_family == DistributionFamily.NORMAL:
                std = max(extract_std(env), 1e-12)
                result[name] = sp_norm.ppf(u, loc=point, scale=std)
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
                # Fallback: normal approximation
                std = max((hi - lo) / 4.0, 1e-12)
                result[name] = sp_norm.ppf(u, loc=point, scale=std)
        return result
