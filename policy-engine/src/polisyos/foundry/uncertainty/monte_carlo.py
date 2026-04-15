"""Public uncertainty monte carlo module API."""
from __future__ import annotations

import warnings
from dataclasses import dataclass
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

logger = get_logger(__name__)


@dataclass(frozen=True)
class _SampleBuffers:
    values: dict[str, np.ndarray]
    input_samples: dict[str, np.ndarray]
    capacity: int


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

        sample_buffers = self._create_sample_buffers(
            param_names=param_names,
            output_metric_ids=output_metric_ids,
            n_samples=n_samples,
        )
        failed = 0
        stopped_early = False
        actual_n_samples = 0
        nominal_outputs = self._safe_nominal_outputs(simulation_fn, nominal_params)

        use_qmc = self._config.mc_sampling_method != "random"

        if use_qmc:
            actual_n_samples, failed = self._run_qmc_loop(
                simulation_fn, param_names, input_envelopes, output_metric_ids,
                n_samples, sample_buffers, adaptive, alpha,
            )
            stopped_early = adaptive.enabled and actual_n_samples < n_samples
        else:
            actual_n_samples, failed = self._run_random_loop(
                simulation_fn, param_names, input_envelopes, output_metric_ids,
                n_samples, batch_size, sample_buffers, adaptive, alpha,
            )
            stopped_early = adaptive.enabled and actual_n_samples < n_samples

        return self._build_results(
            sample_buffers.values,
            sample_buffers.input_samples,
            param_names,
            output_metric_ids,
            nominal_params, nominal_outputs, actual_n_samples, failed, stopped_early,
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
        sample_buffers: _SampleBuffers,
        adaptive: Any,
        alpha: float,
    ) -> tuple[int, int]:
        batch_size = min(self._config.mc_batch_size, n_samples)
        failed = 0
        generated = 0
        sampler_state = self._create_qmc_sampler_state(len(param_names))

        while generated < n_samples:
            this_batch = min(batch_size, n_samples - generated)
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
            )

            for row_idx in range(uniform_samples.shape[0]):
                params = {
                    name: float(qmc_transformed[name][row_idx])
                    for name in param_names
                }
                sample_idx = generated + row_idx
                ok = self._eval_and_record(
                    simulation_fn,
                    params,
                    param_names,
                    output_metric_ids,
                    sample_buffers,
                    sample_idx=sample_idx,
                )
                if not ok:
                    failed += 1

            generated += int(uniform_samples.shape[0])

            if adaptive.enabled and self._check_adaptive_stop(
                generated, adaptive, sample_buffers.values, output_metric_ids, alpha,
            ):
                return generated, failed

        return generated, failed

    def _run_random_loop(
        self,
        simulation_fn: Callable[..., Mapping[str, float]],
        param_names: list[str],
        input_envelopes: Mapping[str, UncertaintyEnvelope],
        output_metric_ids: list[str],
        n_samples: int,
        batch_size: int,
        sample_buffers: _SampleBuffers,
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
                sample_idx = generated + i
                ok = self._eval_and_record(
                    simulation_fn, params, param_names, output_metric_ids,
                    sample_buffers, sample_idx=sample_idx,
                )
                if not ok:
                    failed += 1

            generated += this_batch

            if adaptive.enabled and self._check_adaptive_stop(
                generated, adaptive, sample_buffers.values, output_metric_ids, alpha,
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
    ) -> bool:
        for name in param_names:
            sample_buffers.input_samples[name][sample_idx] = float(params[name])
        try:
            result = simulation_fn(**params)
            for mid in output_metric_ids:
                raw = result.get(mid)
                sample_buffers.values[mid][sample_idx] = (
                    float("nan") if raw is None else float(raw)
                )
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
            input_samples={
                name: np.empty((n_samples,), dtype=np.float64)
                for name in param_names
            },
            capacity=n_samples,
        )

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    def _build_results(
        self,
        values: dict[str, np.ndarray],
        input_samples: dict[str, np.ndarray],
        param_names: list[str],
        output_metric_ids: list[str],
        nominal_params: Mapping[str, float],
        nominal_outputs: Mapping[str, float] | None,
        actual_n_samples: int,
        failed: int,
        stopped_early: bool,
        level: float,
        alpha: float,
    ) -> list[PropagationResult]:
        from .sensitivity import compute_first_order_indices

        out: list[PropagationResult] = []
        for metric_id in output_metric_ids:
            arr = jnp.asarray(values[metric_id][:actual_n_samples], dtype=jnp.float32)
            valid = arr[jnp.isfinite(arr)]
            n_valid = int(valid.shape[0])

            if n_valid < self._config.mc_min_valid_samples:
                point, point_source = self._fallback_point_estimate(
                    metric_id,
                    nominal_params=nominal_params,
                    nominal_outputs=nominal_outputs,
                )
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
                        "fallback_point_estimate_source": point_source,
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
                        valid_mask = np.isfinite(values[metric_id][:actual_n_samples])
                        filtered_inputs = {
                            name: input_samples[name][:actual_n_samples][valid_mask]
                            for name in param_names
                        }
                        valid_outputs = values[metric_id][:actual_n_samples][valid_mask]
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

    def _create_qmc_sampler_state(self, n_dims: int) -> dict[str, Any]:
        if self._config.mc_sampling_method == "halton":
            from scipy.stats.qmc import Halton

            return {
                "method": "halton",
                "n_dims": n_dims,
                "generated": 0,
                "sampler": Halton(
                    d=n_dims,
                    scramble=True,
                    seed=self._config.mc_seed,
                ),
            }

        from scipy.stats.qmc import Sobol

        return {
            "method": "sobol",
            "n_dims": n_dims,
            "generated": 0,
            "sampler": Sobol(
                d=n_dims,
                scramble=True,
                seed=self._config.mc_seed,
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
            new_block
            if buffered.shape[0] == 0
            else np.concatenate((buffered, new_block), axis=0)
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
