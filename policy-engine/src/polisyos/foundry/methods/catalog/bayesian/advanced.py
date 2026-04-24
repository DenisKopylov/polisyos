"""Estimate hierarchical, HMC/NUTS, and mixture-model Bayesian methods."""

from __future__ import annotations

import hashlib
import platform
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    BackendRuntimeFingerprint,
    build_backend_route_key,
    safe_version,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.ml.protocols import PredictionResult
from polisyos.foundry.methods.catalog.ml.regression import (
    _build_prediction_result,
    _tabular_payload,
)
from polisyos.foundry.uncertainty.protocol import UncertaintyDecomposition
from polisyos.ir.canon import CanonSpec, content_hash, to_canonical_bytes

from .protocols import (
    PosteriorResult,
    augment_sampler_diagnostics,
    canonical_draws_artifact,
    extract_truthfulness_hints,
    flatten_chain_draws,
    metropolis_sample,
    relative_interval_shift_max,
    split_truthfulness_hints,
    summarize_posterior_samples,
)

_REFERENCE_SAMPLER_CONTRACT = "foundry.bayesian.reference_sampler.v1"
_REFERENCE_CONTRACT_SALT = 0x504F4C59
_THREAD_PIN_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)
_SAMPLER_CODE = {
    "hmc": 101,
    "nuts": 202,
}


@dataclass(frozen=True, slots=True)
class _SamplerTrace:
    posterior_by_chain: dict[str, np.ndarray]
    warmup_by_chain: dict[str, np.ndarray]
    diagnostics_per_chain: dict[str, dict[str, float]]
    diagnostics_summary: dict[str, float]


def _stable_entropy_token(value: str | int) -> int:
    if isinstance(value, int):
        return int(value) & 0xFFFFFFFF
    digest = hashlib.blake2b(str(value).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest[:4], "little", signed=False)


@dataclass(frozen=True, slots=True)
class _SamplerRngNamespace:
    root_seed: int
    sampler_kernel: str
    chain_id: int
    phase: str
    iteration: int

    def generator(self, purpose: str, *tokens: str | int) -> np.random.Generator:
        code = _SAMPLER_CODE.get(self.sampler_kernel, 0)
        entropy = [
            int(self.root_seed),
            int(code),
            _REFERENCE_CONTRACT_SALT,
            int(self.chain_id),
            _stable_entropy_token(self.phase),
            int(self.iteration),
            _stable_entropy_token(purpose),
        ]
        entropy.extend(_stable_entropy_token(token) for token in tokens)
        return np.random.default_rng(np.random.SeedSequence(entropy))


def _thread_configuration_snapshot() -> dict[str, str]:
    getenv = __import__("os").getenv
    snapshot: dict[str, str] = {}
    for key in _THREAD_PIN_ENV_VARS:
        value = getenv(key)
        if value is not None and value.strip():
            snapshot[key] = value.strip()
    return snapshot


def _thread_configuration_is_pinned_single_thread(snapshot: Mapping[str, str]) -> bool:
    return all(snapshot.get(key) == "1" for key in _THREAD_PIN_ENV_VARS)


def _numpy_runtime_config() -> dict[str, Any]:
    config = getattr(np.__config__, "CONFIG", {})
    if not isinstance(config, Mapping):
        return {}
    build = config.get("Build Dependencies")
    machine = config.get("Machine Information")
    blas = build.get("blas", {}) if isinstance(build, Mapping) else {}
    lapack = build.get("lapack", {}) if isinstance(build, Mapping) else {}
    host = machine.get("host", {}) if isinstance(machine, Mapping) else {}
    return {
        "blas_name": str(blas.get("name", "unknown")),
        "blas_version": str(blas.get("version", "unknown")),
        "lapack_name": str(lapack.get("name", "unknown")),
        "lapack_version": str(lapack.get("version", "unknown")),
        "host_cpu": str(host.get("cpu", "unknown")),
        "host_family": str(host.get("family", "unknown")),
        "host_system": str(host.get("system", "unknown")),
    }


def _bayesian_execution_device(backend_used: str) -> str:
    if backend_used == "numpy":
        return "cpu:bayesian"
    if backend_used == "numpyro":
        try:
            import jax

            backend = str(jax.default_backend()).strip().lower()
            if backend:
                return f"{backend}:bayesian"
        except Exception:
            pass
    return f"cpu:{backend_used or 'bayesian'}"


def _bayesian_runtime_versions(backend_used: str) -> dict[str, str]:
    versions = {"numpy": np.__version__}
    package_names = ("scipy", "arviz")
    if backend_used == "numpyro":
        package_names = (*package_names, "numpyro", "jax", "jaxlib")
    for package_name in package_names:
        if package_name in versions:
            continue
        version = safe_version(package_name)
        if version is not None:
            versions[package_name] = version
    return versions


def _bayesian_observed_tolerance_budget(
    *,
    backend_used: str,
    effective_tier: DeterminismTier,
    seed: int,
    notes: tuple[str, ...] = (),
) -> dict[str, Any]:
    execution_device = _bayesian_execution_device(backend_used)
    library_versions = _bayesian_runtime_versions(backend_used)
    runtime_stack = tuple(
        dict.fromkeys(
            item
            for item in (
                backend_used,
                "numpy",
                "scipy",
                "arviz",
                "jax" if backend_used == "numpyro" else None,
                "jaxlib" if backend_used == "numpyro" else None,
                "numpyro" if backend_used == "numpyro" else None,
            )
            if item
        )
    )
    route_key = build_backend_route_key(
        ComputeBackend.BAYESIAN,
        execution_device=execution_device,
        runtime_backend=backend_used,
        library_versions=library_versions,
        route_key_overrides={"backend_route": f"bayesian:{backend_used}"},
    )
    posture = BackendRuntimeFingerprint(
        backend=ComputeBackend.BAYESIAN,
        available=True,
        determinism_tier=effective_tier,
        execution_device=execution_device,
        runtime_stack=runtime_stack,
        library_versions=library_versions,
        runtime_backend=backend_used,
        seed=seed,
        notes=notes,
        route_key=route_key,
    )
    return posture.observed_tolerance_budget


def _scalar_parameter_series(samples_by_chain: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    series: dict[str, np.ndarray] = {}
    for name, value in sorted(samples_by_chain.items()):
        arr = np.asarray(value, dtype=float)
        if arr.ndim < 2:
            continue
        if arr.ndim == 2:
            series[name] = arr
            continue
        flat = arr.reshape(arr.shape[0], arr.shape[1], -1)
        for idx in range(flat.shape[2]):
            label = name if flat.shape[2] == 1 else f"{name}_{idx}"
            series[label] = flat[:, :, idx]
    return series


def _split_rhat(samples: np.ndarray) -> float:
    arr = np.asarray(samples, dtype=float)
    if arr.ndim != 2:
        raise ValueError("R-hat expects an array with shape (chains, draws)")
    chains, draws = arr.shape
    if chains < 2 or draws < 4:
        return -1.0
    usable = draws - (draws % 2)
    if usable < 4:
        return -1.0
    split = np.concatenate([arr[:, : usable // 2], arr[:, usable // 2 : usable]], axis=0)
    split_vars = np.var(split, axis=1, ddof=1)
    if np.any(~np.isfinite(split_vars)) or float(np.max(split_vars, initial=0.0)) <= 0.0:
        return -1.0
    n = split.shape[1]
    chain_means = np.mean(split, axis=1)
    between = n * float(np.var(chain_means, ddof=1))
    within = float(np.mean(split_vars))
    if within <= 0.0:
        return -1.0
    var_hat = ((n - 1.0) / n) * within + between / n
    return float(np.sqrt(max(var_hat / within, 0.0)))


def _ess_estimate(samples: np.ndarray) -> float:
    arr = np.asarray(samples, dtype=float)
    if arr.ndim != 2:
        raise ValueError("ESS expects an array with shape (chains, draws)")
    chains, draws = arr.shape
    if chains < 1 or draws < 4:
        return float(chains * draws)
    centered = arr - np.mean(arr, axis=1, keepdims=True)
    variance = np.var(centered, axis=1)
    if np.any(~np.isfinite(variance)) or float(np.max(variance, initial=0.0)) <= 0.0:
        return -1.0

    tau = 1.0
    previous_pair = None
    for lag in range(1, draws - 1, 2):
        pair_sum = 0.0
        for inner_lag in (lag, lag + 1):
            rho_values: list[float] = []
            for chain_idx in range(chains):
                chain = centered[chain_idx]
                denom = float(np.dot(chain, chain))
                if denom <= 0.0:
                    continue
                numerator = float(np.dot(chain[:-inner_lag], chain[inner_lag:]))
                rho_values.append(numerator / denom)
            if not rho_values:
                continue
            pair_sum += float(np.mean(rho_values))
        if previous_pair is not None and pair_sum > previous_pair:
            pair_sum = previous_pair
        if pair_sum <= 0.0:
            break
        tau += 2.0 * pair_sum
        previous_pair = pair_sum
    return float((chains * draws) / max(tau, 1.0))


def _tail_ess_estimate(samples: np.ndarray) -> float:
    pooled = np.asarray(samples, dtype=float).reshape(-1)
    if pooled.size < 8:
        return -1.0
    lower_q, upper_q = np.quantile(pooled, [0.05, 0.95])
    lower_indicator = (samples <= lower_q).astype(float)
    upper_indicator = (samples >= upper_q).astype(float)
    lower_ess = _ess_estimate(lower_indicator)
    upper_ess = _ess_estimate(upper_indicator)
    candidates = [value for value in (lower_ess, upper_ess) if value >= 0.0]
    return min(candidates) if candidates else -1.0


def _energy_bfmi(energy: np.ndarray) -> float:
    arr = np.asarray(energy, dtype=float).reshape(-1)
    if arr.size < 2:
        return -1.0
    variance = float(np.var(arr))
    if not np.isfinite(variance) or variance <= 0.0:
        return -1.0
    deltas = np.diff(arr)
    return float(np.mean(deltas * deltas) / variance)


def _sampler_diagnostic_bundle(
    *,
    sampler_kernel: str,
    samples_by_chain: Mapping[str, np.ndarray],
    diagnostics_per_chain: Mapping[str, Mapping[str, float]],
) -> tuple[dict[str, float], dict[str, bool], tuple[str, ...], str]:
    series = _scalar_parameter_series(samples_by_chain)
    rhat_measurements = {name: _split_rhat(item) for name, item in series.items()}
    bulk_ess_measurements = {name: _ess_estimate(item) for name, item in series.items()}
    tail_ess_measurements = {name: _tail_ess_estimate(item) for name, item in series.items()}

    def _is_valid_metric(value: float) -> bool:
        return bool(np.isfinite(value) and value >= 0.0)

    rhat_values = [value for value in rhat_measurements.values() if _is_valid_metric(value)]
    bulk_ess_values = [value for value in bulk_ess_measurements.values() if _is_valid_metric(value)]
    tail_ess_values = [value for value in tail_ess_measurements.values() if _is_valid_metric(value)]
    chain_count = len(diagnostics_per_chain)
    ess_gate_chain_count = max(chain_count, 1)
    min_required_ess = 100.0 * ess_gate_chain_count
    bfmi_measurements = {
        str(chain_id): float(metrics.get("bfmi", -1.0))
        for chain_id, metrics in diagnostics_per_chain.items()
    }
    bfmi_values = [value for value in bfmi_measurements.values() if _is_valid_metric(value)]
    divergence_total = float(
        sum(
            int(round(float(metrics.get("divergences", 0.0))))
            for metrics in diagnostics_per_chain.values()
        )
    )
    treedepth_total = float(
        sum(
            int(round(float(metrics.get("max_treedepth_hits", 0.0))))
            for metrics in diagnostics_per_chain.values()
        )
    )
    acceptance_values = [
        float(metrics.get("acceptance_rate", 0.0)) for metrics in diagnostics_per_chain.values()
    ]
    invalid_counts = {
        "rhat": int(len(rhat_measurements) - len(rhat_values)),
        "bulk_ess": int(len(bulk_ess_measurements) - len(bulk_ess_values)),
        "tail_ess": int(len(tail_ess_measurements) - len(tail_ess_values)),
        "bfmi": int(len(bfmi_measurements) - len(bfmi_values)),
    }
    has_invalid_rhat = bool(rhat_measurements) and invalid_counts["rhat"] > 0
    has_invalid_bulk_ess = bool(bulk_ess_measurements) and invalid_counts["bulk_ess"] > 0
    has_invalid_tail_ess = bool(tail_ess_measurements) and invalid_counts["tail_ess"] > 0
    has_invalid_bfmi = chain_count > 0 and invalid_counts["bfmi"] > 0

    diagnostics_summary = {
        "num_monitored_chains": float(chain_count),
        "max_rhat": max(rhat_values) if rhat_values else -1.0,
        "min_bulk_ess": min(bulk_ess_values) if bulk_ess_values else -1.0,
        "min_tail_ess": min(tail_ess_values) if tail_ess_values else -1.0,
        "min_bfmi": min(bfmi_values) if bfmi_values else -1.0,
        "divergences": divergence_total,
        "max_treedepth_hits": treedepth_total,
        "mean_acceptance_rate": float(np.mean(acceptance_values)) if acceptance_values else 0.0,
        "num_scalar_parameters_monitored": float(len(series)),
        "minimum_required_ess": float(min_required_ess),
        "invalid_rhat_count": float(invalid_counts["rhat"]),
        "invalid_bulk_ess_count": float(invalid_counts["bulk_ess"]),
        "invalid_tail_ess_count": float(invalid_counts["tail_ess"]),
        "invalid_bfmi_count": float(invalid_counts["bfmi"]),
    }
    diagnostic_gates = {
        "minimum_chains": chain_count >= 4,
        "rhat": (
            bool(rhat_measurements)
            and not has_invalid_rhat
            and 0.0 <= diagnostics_summary["max_rhat"] <= 1.01
        ),
        "bulk_ess": (
            bool(bulk_ess_measurements)
            and not has_invalid_bulk_ess
            and diagnostics_summary["min_bulk_ess"] >= min_required_ess
        ),
        "tail_ess": (
            bool(tail_ess_measurements)
            and not has_invalid_tail_ess
            and diagnostics_summary["min_tail_ess"] >= min_required_ess
        ),
        "bfmi": chain_count > 0
        and not has_invalid_bfmi
        and diagnostics_summary["min_bfmi"] >= 0.30,
        "divergences": divergence_total == 0.0,
        "max_treedepth_hits": True if sampler_kernel != "nuts" else treedepth_total == 0.0,
    }
    warnings = tuple(
        dict.fromkeys(
            [
                *(
                    f"diagnostic_metric_invalid:{name}"
                    for name, invalid in (
                        ("rhat", has_invalid_rhat),
                        ("bulk_ess", has_invalid_bulk_ess),
                        ("tail_ess", has_invalid_tail_ess),
                        ("bfmi", has_invalid_bfmi),
                    )
                    if invalid
                ),
                *(
                    f"diagnostic_gate_failed:{name}"
                    for name, passed in diagnostic_gates.items()
                    if not passed
                ),
            ]
        )
    )
    status = "ok" if all(diagnostic_gates.values()) else "diagnostics_failed"
    return diagnostics_summary, diagnostic_gates, warnings, status


def _reference_sampler_reproducibility(
    *,
    params: Mapping[str, Any],
    backend_used: str,
    sampler_kernel: str,
    posterior_hash: str,
    warmup_hash: str | None,
    draw_layout: Mapping[str, Any],
) -> tuple[DeterminismTier, dict[str, Any], tuple[str, ...], str | None]:
    requested_runtime = _requested_runtime_backend(params)
    thread_snapshot = _thread_configuration_snapshot()
    degradation_reasons: list[str] = []
    if backend_used != "numpy":
        degradation_reasons.append("runtime_backend_not_reference")
    if requested_runtime != "numpy":
        degradation_reasons.append(
            "runtime_backend_auto_not_allowed"
            if requested_runtime == "auto"
            else "requested_runtime_backend_mismatch"
        )
    if not _thread_configuration_is_pinned_single_thread(thread_snapshot):
        degradation_reasons.append("thread_configuration_not_pinned_single_thread")

    effective_tier = (
        DeterminismTier.LIBRARY_DETERMINISTIC
        if not degradation_reasons
        else DeterminismTier.STATISTICAL
    )
    envelope = {
        "contract_version": _REFERENCE_SAMPLER_CONTRACT,
        "requested_runtime_backend": requested_runtime,
        "effective_runtime_backend": backend_used,
        "sampler_kernel": sampler_kernel,
        "execution_device": "cpu:bayesian",
        "chain_execution": "sequential",
        "float_precision": "float64",
        "jit_enabled": False,
        "gpu_allowed": False,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "arch_family": platform.machine(),
        "libc": {
            "lib": platform.libc_ver()[0] or "unknown",
            "version": platform.libc_ver()[1] or "unknown",
        },
        "numpy_version": np.__version__,
        "numpy_runtime_config": _numpy_runtime_config(),
        "thread_configuration": {
            "required_variables": list(_THREAD_PIN_ENV_VARS),
            "observed": dict(sorted(thread_snapshot.items())),
            "single_thread_pinned": _thread_configuration_is_pinned_single_thread(thread_snapshot),
        },
        "rng_partitioning": {
            "scheme": "seedsequence_substreams",
            "components": [
                "root_seed",
                "sampler_code",
                "contract_salt",
                "chain_id",
                "phase",
                "iteration",
                "purpose",
                "stream_tokens",
            ],
        },
    }
    envelope_id = content_hash(
        to_canonical_bytes(envelope, spec=CanonSpec(forbid_floats=False)),
        prefix=True,
    )
    observed_budget = _bayesian_observed_tolerance_budget(
        backend_used=backend_used,
        effective_tier=effective_tier,
        seed=int(params.get("__seed__", 0)),
        notes=tuple(f"determinism_degraded:{reason}" for reason in degradation_reasons),
    )
    reproducibility = {
        "contract_version": _REFERENCE_SAMPLER_CONTRACT,
        "requested_determinism_tier": (
            DeterminismTier.LIBRARY_DETERMINISTIC.value
            if requested_runtime == "numpy"
            else DeterminismTier.STATISTICAL.value
        ),
        "effective_determinism_tier": effective_tier.value,
        "requested_runtime_backend": requested_runtime,
        "effective_runtime_backend": backend_used,
        "root_seed": int(params.get("__seed__", 0)),
        "chain_seed_derivation": (
            "SeedSequence([root_seed, sampler_code, contract_salt, chain_id, phase, iteration, purpose, stream_tokens...])"
        ),
        "envelope_id": envelope_id,
        "determinism_envelope": envelope,
        "degradation_reasons": list(degradation_reasons),
        "replay_output_hash": posterior_hash,
        "warmup_output_hash": warmup_hash,
        "draw_layout": dict(draw_layout),
        "route_key": dict(observed_budget.get("route_key") or {}),
        "observed_tolerance_budget": observed_budget,
    }
    warnings = tuple(f"determinism_degraded:{reason}" for reason in degradation_reasons)
    degradation_reason = degradation_reasons[0] if degradation_reasons else None
    return effective_tier, reproducibility, warnings, degradation_reason


def _reference_sampler_contract(
    *,
    method_name: str,
    sampler_kernel: str,
    params: Mapping[str, Any],
    backend_used: str,
    trace: _SamplerTrace,
) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...], DeterminismTier]:
    diagnostics_summary, diagnostic_gates, gate_warnings, status = _sampler_diagnostic_bundle(
        sampler_kernel=sampler_kernel,
        samples_by_chain=trace.posterior_by_chain,
        diagnostics_per_chain=trace.diagnostics_per_chain,
    )
    posterior_ref, posterior_artifact, posterior_hash, draw_layout = canonical_draws_artifact(
        trace.posterior_by_chain,
        method_name=method_name,
        sampler_kernel=sampler_kernel,
        stage="posterior",
    )
    warmup_ref, warmup_artifact, warmup_hash, _ = canonical_draws_artifact(
        trace.warmup_by_chain,
        method_name=method_name,
        sampler_kernel=sampler_kernel,
        stage="warmup",
    )
    determinism_tier, reproducibility, replay_warnings, degradation_reason = (
        _reference_sampler_reproducibility(
            params=params,
            backend_used=backend_used,
            sampler_kernel=sampler_kernel,
            posterior_hash=posterior_hash,
            warmup_hash=warmup_hash,
            draw_layout=draw_layout,
        )
    )
    warnings = tuple(dict.fromkeys([*gate_warnings, *replay_warnings]))
    posterior_fields = {
        "sampler_family": "mcmc",
        "sampler_kernel": sampler_kernel,
        "draws_ref": posterior_ref,
        "warmup_draws_ref": warmup_ref,
        "draw_layout": dict(draw_layout),
        "diagnostics_per_chain": {
            key: dict(value) for key, value in trace.diagnostics_per_chain.items()
        },
        "diagnostics_summary": {**trace.diagnostics_summary, **diagnostics_summary},
        "diagnostic_gates": diagnostic_gates,
        "reproducibility": reproducibility,
        "warnings": warnings,
        "status": status,
        "degradation_reason": degradation_reason,
    }
    artifacts = {
        "posterior_draws": {
            "artifact_ref": posterior_ref,
            "artifact_hash": posterior_hash,
            "payload": posterior_artifact,
        },
        "warmup_draws": {
            "artifact_ref": warmup_ref,
            "artifact_hash": warmup_hash,
            "payload": warmup_artifact,
        },
        "sampler_reproducibility": reproducibility,
        "sampler_status": status,
        "diagnostic_gates": diagnostic_gates,
    }
    return posterior_fields, artifacts, warnings, determinism_tier


def _prediction_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("posterior", "json"),
                contract_id=PosteriorResult.contract_id,
            ),
            SlotSpec(
                "prediction_result",
                SlotType.SCALAR,
                Unit("prediction", "json"),
                contract_id=PredictionResult.contract_id,
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _mixture_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("posterior", "json"),
                contract_id=PosteriorResult.contract_id,
            ),
            SlotSpec(
                "cluster_assignments",
                SlotType.VECTOR,
                Unit("cluster", "id"),
                shape=("n_obs",),
            ),
            SlotSpec(
                "cluster_probabilities",
                SlotType.MATRIX,
                Unit("probability", "value"),
                shape=("n_obs", "n_components"),
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _mapping_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, Mapping):
        return dict(state)
    return _tabular_payload(state)


def _feature_names_from_payload(payload: Mapping[str, Any], n_features: int) -> list[str]:
    raw_names = payload.get("feature_names")
    if isinstance(raw_names, (list, tuple)) and len(raw_names) == n_features:
        return [str(item) for item in raw_names]
    return [f"x{idx}" for idx in range(n_features)]


def _coerce_observations(value: Any) -> np.ndarray:
    observations = np.asarray(value, dtype=float)
    if observations.ndim == 1:
        observations = observations[:, None]
    if observations.ndim != 2:
        raise ValueError("observations must be a 1D or 2D numeric array")
    if observations.shape[0] < 4:
        raise ValueError("mixture models require at least 4 observations")
    return observations


def _requested_runtime_backend(params: Mapping[str, Any]) -> str:
    value = str(params.get("runtime_backend", "auto")).strip().lower()
    return value or "auto"


def _selected_runtime_backend(params: Mapping[str, Any], *, default: str = "numpy") -> str:
    value = str(params.get("__bayesian_runtime_backend__", default)).strip().lower()
    return value or default


def _runtime_backend_fallback_reason(params: Mapping[str, Any], *, backend_used: str) -> str | None:
    requested = _requested_runtime_backend(params)
    health = params.get("__bayesian_backend_health__")
    if requested == backend_used:
        return None
    if backend_used == "numpy":
        if isinstance(health, Mapping) and requested in {"auto", "numpyro"}:
            warnings = health.get("warnings")
            if (
                isinstance(warnings, list)
                and "numpyro_unavailable:using_numpy_fallback" in warnings
            ):
                return "numpyro_unavailable"
    return None


def _runtime_backend_metadata(params: Mapping[str, Any], *, backend_used: str) -> dict[str, Any]:
    health = params.get("__bayesian_backend_health__")
    metadata = {
        "runtime_backend_requested": _requested_runtime_backend(params),
        "runtime_backend_used": backend_used,
    }
    fallback_reason = _runtime_backend_fallback_reason(params, backend_used=backend_used)
    if fallback_reason is not None:
        metadata["runtime_backend_fallback_reason"] = fallback_reason
    if isinstance(health, Mapping):
        metadata["runtime_backend_health"] = dict(health)
    return metadata


def _predictive_uncertainty_decomposition(
    *,
    metric_id: str,
    predictive_mean_draws: np.ndarray,
    aleatoric_scale_draws: np.ndarray,
    confidence_level: float,
    metadata: Mapping[str, Any] | None = None,
) -> UncertaintyDecomposition:
    mean_draws = np.asarray(predictive_mean_draws, dtype=float).reshape(-1)
    noise_draws = np.asarray(aleatoric_scale_draws, dtype=float).reshape(-1)
    point_estimate = float(np.mean(mean_draws)) if mean_draws.size else 0.0
    epistemic_std = float(np.std(mean_draws, ddof=1)) if mean_draws.size > 1 else 0.0
    aleatoric_std = float(np.mean(np.maximum(noise_draws, 0.0))) if noise_draws.size else 0.0
    return UncertaintyDecomposition.from_gaussian_components(
        metric_id=metric_id,
        point_estimate=point_estimate,
        confidence_level=confidence_level,
        epistemic_std=epistemic_std,
        aleatoric_std=aleatoric_std,
        metadata=metadata,
    )


def _numpyro_linear_regression_samples(
    *,
    algorithm: str,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
    step_size: float,
    n_leapfrog: int,
    max_depth: int,
    target_accept: float,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
    seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    try:
        import jax.numpy as jnp
        import numpyro
        from jax import random
        from numpyro import distributions as dist
        from numpyro.infer import HMC, MCMC, NUTS
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("NumPyro runtime is unavailable for Bayesian sampling") from exc

    features = jnp.asarray(x, dtype=jnp.float32)
    target = jnp.asarray(y, dtype=jnp.float32)

    def model(features: Any, target: Any | None = None) -> None:
        intercept = numpyro.sample("intercept", dist.Normal(0.0, prior_scale))
        coefficients = numpyro.sample(
            "coefficients",
            dist.Normal(jnp.zeros(features.shape[1]), prior_scale * jnp.ones(features.shape[1])),
        )
        sigma = numpyro.sample("sigma", dist.HalfNormal(prior_scale))
        mean = intercept + jnp.dot(features, coefficients)
        numpyro.sample("obs", dist.Normal(mean, sigma), obs=target)

    if algorithm == "hmc":
        kernel = HMC(
            model,
            step_size=step_size,
            num_steps=max(1, int(n_leapfrog)),
        )
    else:
        kernel = NUTS(
            model,
            step_size=step_size,
            target_accept_prob=target_accept,
            max_tree_depth=max(1, int(max_depth)),
        )
    mcmc = MCMC(
        kernel,
        num_warmup=max(1, int(num_warmup)),
        num_samples=max(1, int(num_samples)),
        num_chains=max(1, int(num_chains)),
        progress_bar=False,
    )
    mcmc.run(random.PRNGKey(int(seed)), features=features, target=target)
    samples = {
        key: np.asarray(value) for key, value in mcmc.get_samples(group_by_chain=False).items()
    }
    extra_fields = mcmc.get_extra_fields()

    def _extra_field(*keys: str) -> np.ndarray:
        for key in keys:
            if key in extra_fields:
                return np.asarray(extra_fields[key], dtype=float)
        return np.asarray([], dtype=float)

    accept_prob = _extra_field("accept_prob", "acceptance_prob", "acceptance_probability")
    num_steps_arr = _extra_field("num_steps")
    divergences_raw = extra_fields.get("diverging")
    divergences = (
        int(np.asarray(divergences_raw, dtype=bool).sum()) if divergences_raw is not None else 0
    )
    diagnostics = {
        "acceptance_rate": float(np.mean(accept_prob)) if accept_prob.size else 0.0,
        "divergences": float(divergences),
        "mean_num_steps": float(np.mean(num_steps_arr)) if num_steps_arr.size else 0.0,
    }
    return samples, diagnostics


def _numpyro_hierarchical_regression_samples(
    *,
    x: np.ndarray,
    y: np.ndarray,
    group_index: np.ndarray,
    prior_scale: float,
    group_scale_prior: float,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
    seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    try:
        import jax.numpy as jnp
        import numpyro
        from jax import random
        from numpyro import distributions as dist
        from numpyro.infer import MCMC, NUTS
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("NumPyro runtime is unavailable for hierarchical sampling") from exc

    features = jnp.asarray(x, dtype=jnp.float32)
    target = jnp.asarray(y, dtype=jnp.float32)
    groups = jnp.asarray(group_index, dtype=jnp.int32)
    n_groups = int(np.max(np.asarray(group_index, dtype=int))) + 1

    def model(features: Any, target: Any | None = None, groups: Any | None = None) -> None:
        global_intercept = numpyro.sample("global_intercept", dist.Normal(0.0, prior_scale))
        coefficients = numpyro.sample(
            "coefficients",
            dist.Normal(jnp.zeros(features.shape[1]), prior_scale * jnp.ones(features.shape[1])),
        )
        group_scale = numpyro.sample("group_scale", dist.HalfNormal(group_scale_prior))
        group_effect = numpyro.sample(
            "group_effect",
            dist.Normal(jnp.zeros(n_groups), group_scale * jnp.ones(n_groups)),
        )
        sigma = numpyro.sample("sigma", dist.HalfNormal(prior_scale))
        mean = global_intercept + jnp.dot(features, coefficients) + group_effect[groups]
        numpyro.sample("obs", dist.Normal(mean, sigma), obs=target)

    kernel = NUTS(model, target_accept_prob=0.8)
    mcmc = MCMC(
        kernel,
        num_warmup=max(1, int(num_warmup)),
        num_samples=max(1, int(num_samples)),
        num_chains=max(1, int(num_chains)),
        progress_bar=False,
    )
    mcmc.run(random.PRNGKey(int(seed)), features=features, target=target, groups=groups)
    samples = {
        key: np.asarray(value) for key, value in mcmc.get_samples(group_by_chain=False).items()
    }
    extra_fields = mcmc.get_extra_fields()
    accept_prob = np.asarray(extra_fields.get("accept_prob", []), dtype=float)
    divergences = np.asarray(extra_fields.get("diverging", []), dtype=bool)
    diagnostics = {
        "acceptance_rate": float(np.mean(accept_prob)) if accept_prob.size else 0.0,
        "divergences": float(np.sum(divergences)) if divergences.size else 0.0,
    }
    return samples, diagnostics


def _linear_regression_log_density_and_grad(
    theta: np.ndarray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> tuple[float, np.ndarray]:
    intercept = float(theta[0])
    beta = np.asarray(theta[1:-1], dtype=float)
    log_sigma = float(theta[-1])
    sigma = float(np.exp(log_sigma))
    mean = intercept + x @ beta
    residual = y - mean
    inv_sigma_sq = 1.0 / max(sigma * sigma, 1e-9)
    log_likelihood = -float(y.shape[0]) * log_sigma - 0.5 * inv_sigma_sq * float(
        np.sum(residual**2)
    )
    log_prior = -0.5 * float(np.sum((theta / max(prior_scale, 1e-9)) ** 2))
    grad = np.zeros_like(theta, dtype=float)
    grad[0] = float(np.sum(residual) * inv_sigma_sq - intercept / (prior_scale**2))
    grad[1:-1] = (x.T @ residual) * inv_sigma_sq - beta / (prior_scale**2)
    grad[-1] = (
        -float(y.shape[0])
        + float(np.sum(residual**2) * inv_sigma_sq)
        - log_sigma / (prior_scale**2)
    )
    return log_likelihood + log_prior, grad


def _leapfrog(
    position: np.ndarray,
    momentum: np.ndarray,
    *,
    step_size: float,
    n_steps: int,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    current_position = np.asarray(position, dtype=float).copy()
    current_momentum = np.asarray(momentum, dtype=float).copy()
    log_density, gradient = _linear_regression_log_density_and_grad(
        current_position,
        x=x,
        y=y,
        prior_scale=prior_scale,
    )
    current_momentum = current_momentum + 0.5 * step_size * gradient
    for step_idx in range(max(1, int(n_steps))):
        current_position = current_position + step_size * current_momentum
        log_density, gradient = _linear_regression_log_density_and_grad(
            current_position,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        if step_idx != max(1, int(n_steps)) - 1:
            current_momentum = current_momentum + step_size * gradient
    current_momentum = current_momentum + 0.5 * step_size * gradient
    return current_position, -current_momentum, float(log_density), gradient


def _hmc_sample_linear_regression(
    *,
    x: np.ndarray,
    y: np.ndarray,
    initial_state: np.ndarray,
    prior_scale: float,
    step_size: float,
    n_leapfrog: int,
    rng: np.random.Generator,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
) -> tuple[np.ndarray, float]:
    draws: list[np.ndarray] = []
    accepted = 0
    attempted = 0
    for _ in range(max(1, int(num_chains))):
        current = np.asarray(initial_state, dtype=float) + rng.normal(
            scale=0.05, size=initial_state.shape
        )
        current_lp, _ = _linear_regression_log_density_and_grad(
            current,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        local_step = max(float(step_size), 1e-4)
        chain_draws: list[np.ndarray] = []
        for step_idx in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            momentum = rng.normal(size=current.shape)
            proposal, proposal_momentum, proposal_lp, _ = _leapfrog(
                current,
                momentum,
                step_size=local_step,
                n_steps=n_leapfrog,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            current_energy = -current_lp + 0.5 * float(np.dot(momentum, momentum))
            proposal_energy = -proposal_lp + 0.5 * float(
                np.dot(proposal_momentum, proposal_momentum)
            )
            accept_prob = min(1.0, float(np.exp(current_energy - proposal_energy)))
            if float(rng.uniform()) <= accept_prob:
                current = proposal
                current_lp = proposal_lp
                accepted += 1
            attempted += 1
            if step_idx < max(0, int(num_warmup)):
                if accept_prob < 0.6:
                    local_step *= 0.92
                elif accept_prob > 0.8:
                    local_step *= 1.04
                local_step = min(max(local_step, 1e-4), 0.25)
                continue
            chain_draws.append(current.copy())
        draws.append(np.asarray(chain_draws, dtype=float))
    return np.concatenate(draws, axis=0), accepted / max(attempted, 1)


def _joint_log_density_linear_regression(
    theta: np.ndarray,
    momentum: np.ndarray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
) -> float:
    log_density, _ = _linear_regression_log_density_and_grad(
        theta,
        x=x,
        y=y,
        prior_scale=prior_scale,
    )
    return float(log_density - 0.5 * np.dot(momentum, momentum))


def _nuts_stop_criterion(
    theta_minus: np.ndarray,
    theta_plus: np.ndarray,
    momentum_minus: np.ndarray,
    momentum_plus: np.ndarray,
) -> bool:
    delta = np.asarray(theta_plus, dtype=float) - np.asarray(theta_minus, dtype=float)
    return bool(np.dot(delta, momentum_minus) >= 0.0 and np.dot(delta, momentum_plus) >= 0.0)


def _build_nuts_tree(
    theta: np.ndarray,
    momentum: np.ndarray,
    *,
    log_slice: float,
    direction: int,
    depth: int,
    step_size: float,
    x: np.ndarray,
    y: np.ndarray,
    prior_scale: float,
    joint0: float,
    rng: np.random.Generator | None = None,
    rng_namespace: _SamplerRngNamespace | None = None,
    path: tuple[int, ...] = (),
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, bool, float, int]:
    if depth == 0:
        theta_prime, momentum_prime, _, _ = _leapfrog(
            theta,
            momentum,
            step_size=float(direction) * step_size,
            n_steps=1,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        joint = _joint_log_density_linear_regression(
            theta_prime,
            momentum_prime,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        n_prime = 1 if log_slice <= joint else 0
        s_prime = bool((log_slice - 1000.0) < joint)
        alpha = min(1.0, float(np.exp(min(0.0, joint - joint0))))
        return (
            theta_prime,
            momentum_prime,
            theta_prime,
            momentum_prime,
            theta_prime,
            n_prime,
            s_prime,
            alpha,
            1,
        )

    (
        theta_minus,
        momentum_minus,
        theta_plus,
        momentum_plus,
        theta_prime,
        n_prime,
        s_prime,
        alpha_sum,
        alpha_count,
    ) = _build_nuts_tree(
        theta,
        momentum,
        log_slice=log_slice,
        direction=direction,
        depth=depth - 1,
        step_size=step_size,
        x=x,
        y=y,
        prior_scale=prior_scale,
        joint0=joint0,
        rng=rng,
        rng_namespace=rng_namespace,
        path=(*path, 0),
    )
    if not s_prime:
        return (
            theta_minus,
            momentum_minus,
            theta_plus,
            momentum_plus,
            theta_prime,
            n_prime,
            s_prime,
            alpha_sum,
            alpha_count,
        )

    if direction < 0:
        (
            theta_minus_2,
            momentum_minus_2,
            _,
            _,
            theta_prime_2,
            n_prime_2,
            s_prime_2,
            alpha_2,
            alpha_count_2,
        ) = _build_nuts_tree(
            theta_minus,
            momentum_minus,
            log_slice=log_slice,
            direction=direction,
            depth=depth - 1,
            step_size=step_size,
            x=x,
            y=y,
            prior_scale=prior_scale,
            joint0=joint0,
            rng=rng,
            rng_namespace=rng_namespace,
            path=(*path, 1),
        )
        theta_minus = theta_minus_2
        momentum_minus = momentum_minus_2
    else:
        (
            _,
            _,
            theta_plus_2,
            momentum_plus_2,
            theta_prime_2,
            n_prime_2,
            s_prime_2,
            alpha_2,
            alpha_count_2,
        ) = _build_nuts_tree(
            theta_plus,
            momentum_plus,
            log_slice=log_slice,
            direction=direction,
            depth=depth - 1,
            step_size=step_size,
            x=x,
            y=y,
            prior_scale=prior_scale,
            joint0=joint0,
            rng=rng,
            rng_namespace=rng_namespace,
            path=(*path, 2),
        )
        theta_plus = theta_plus_2
        momentum_plus = momentum_plus_2

    if rng_namespace is not None:
        combine_rng = rng_namespace.generator("tree_combine", depth, direction, *path)
    elif rng is not None:
        combine_rng = rng
    else:  # pragma: no cover - defensive guard for malformed internal calls.
        raise ValueError("NUTS tree builder requires either rng or rng_namespace")

    if (n_prime + n_prime_2) > 0 and float(combine_rng.uniform()) < (
        n_prime_2 / max(n_prime + n_prime_2, 1)
    ):
        theta_prime = theta_prime_2
    n_prime += n_prime_2
    s_prime = bool(
        s_prime
        and s_prime_2
        and _nuts_stop_criterion(theta_minus, theta_plus, momentum_minus, momentum_plus)
    )
    return (
        theta_minus,
        momentum_minus,
        theta_plus,
        momentum_plus,
        theta_prime,
        n_prime,
        s_prime,
        alpha_sum + alpha_2,
        alpha_count + alpha_count_2,
    )


def _nuts_sample_linear_regression(
    *,
    x: np.ndarray,
    y: np.ndarray,
    initial_state: np.ndarray,
    prior_scale: float,
    step_size: float,
    max_depth: int,
    rng: np.random.Generator,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
    target_accept: float,
) -> tuple[np.ndarray, float]:
    draws: list[np.ndarray] = []
    accepted_weight = 0.0
    total_weight = 0
    for _ in range(max(1, int(num_chains))):
        current = np.asarray(initial_state, dtype=float) + rng.normal(
            scale=0.03, size=initial_state.shape
        )
        local_step = max(float(step_size), 1e-4)
        chain_draws: list[np.ndarray] = []
        for step_idx in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            momentum0 = rng.normal(size=current.shape)
            joint0 = _joint_log_density_linear_regression(
                current,
                momentum0,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            log_slice = joint0 - float(rng.exponential(1.0))
            theta_minus = current.copy()
            theta_plus = current.copy()
            momentum_minus = momentum0.copy()
            momentum_plus = momentum0.copy()
            theta_candidate = current.copy()
            depth = 0
            n = 1
            continue_tree = True
            alpha_sum = 0.0
            alpha_count = 0
            while continue_tree and depth < max(1, int(max_depth)):
                direction = -1 if float(rng.uniform()) < 0.5 else 1
                if direction < 0:
                    (
                        theta_minus,
                        momentum_minus,
                        _,
                        _,
                        theta_prime,
                        n_prime,
                        s_prime,
                        alpha_prime,
                        alpha_count_prime,
                    ) = _build_nuts_tree(
                        theta_minus,
                        momentum_minus,
                        log_slice=log_slice,
                        direction=direction,
                        depth=depth,
                        step_size=local_step,
                        x=x,
                        y=y,
                        prior_scale=prior_scale,
                        joint0=joint0,
                        rng=rng,
                    )
                else:
                    (
                        _,
                        _,
                        theta_plus,
                        momentum_plus,
                        theta_prime,
                        n_prime,
                        s_prime,
                        alpha_prime,
                        alpha_count_prime,
                    ) = _build_nuts_tree(
                        theta_plus,
                        momentum_plus,
                        log_slice=log_slice,
                        direction=direction,
                        depth=depth,
                        step_size=local_step,
                        x=x,
                        y=y,
                        prior_scale=prior_scale,
                        joint0=joint0,
                        rng=rng,
                    )
                if (
                    s_prime
                    and (n + n_prime) > 0
                    and float(rng.uniform()) < (n_prime / max(n + n_prime, 1))
                ):
                    theta_candidate = theta_prime.copy()
                n += n_prime
                continue_tree = bool(
                    s_prime
                    and _nuts_stop_criterion(theta_minus, theta_plus, momentum_minus, momentum_plus)
                )
                alpha_sum += alpha_prime
                alpha_count += alpha_count_prime
                depth += 1
            accept_rate = alpha_sum / max(alpha_count, 1)
            accepted_weight += accept_rate
            total_weight += 1
            current = theta_candidate
            if step_idx < max(0, int(num_warmup)):
                if accept_rate < target_accept:
                    local_step *= 0.9
                else:
                    local_step *= 1.03
                local_step = min(max(local_step, 1e-4), 0.25)
                continue
            chain_draws.append(current.copy())
        draws.append(np.asarray(chain_draws, dtype=float))
    return np.concatenate(draws, axis=0), accepted_weight / max(total_weight, 1)


def _hmc_reference_trace(
    *,
    x: np.ndarray,
    y: np.ndarray,
    initial_state: np.ndarray,
    prior_scale: float,
    step_size: float,
    n_leapfrog: int,
    root_seed: int,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
) -> _SamplerTrace:
    warmup_draws: list[np.ndarray] = []
    posterior_draws: list[np.ndarray] = []
    diagnostics_per_chain: dict[str, dict[str, float]] = {}
    for chain_id in range(max(1, int(num_chains))):
        init_rng = _SamplerRngNamespace(
            root_seed=int(root_seed),
            sampler_kernel="hmc",
            chain_id=chain_id,
            phase="initialization",
            iteration=0,
        ).generator("initial_state")
        current = np.asarray(initial_state, dtype=float) + init_rng.normal(
            scale=0.05, size=initial_state.shape
        )
        current_lp, _ = _linear_regression_log_density_and_grad(
            current,
            x=x,
            y=y,
            prior_scale=prior_scale,
        )
        local_step = max(float(step_size), 1e-4)
        chain_warmup: list[np.ndarray] = []
        chain_posterior: list[np.ndarray] = []
        energy_trace: list[float] = []
        accepted = 0
        attempted = 0
        divergences = 0
        for step_idx in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            phase = "warmup" if step_idx < max(0, int(num_warmup)) else "posterior"
            rng_namespace = _SamplerRngNamespace(
                root_seed=int(root_seed),
                sampler_kernel="hmc",
                chain_id=chain_id,
                phase=phase,
                iteration=step_idx,
            )
            momentum = rng_namespace.generator("momentum").normal(size=current.shape)
            proposal, proposal_momentum, proposal_lp, _ = _leapfrog(
                current,
                momentum,
                step_size=local_step,
                n_steps=n_leapfrog,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            current_energy = -current_lp + 0.5 * float(np.dot(momentum, momentum))
            proposal_energy = -proposal_lp + 0.5 * float(
                np.dot(proposal_momentum, proposal_momentum)
            )
            if (not np.isfinite(current_energy)) or (not np.isfinite(proposal_energy)):
                divergences += 1
                accept_prob = 0.0
            else:
                energy_error = abs(proposal_energy - current_energy)
                if energy_error > 100.0:
                    divergences += 1
                accept_prob = min(1.0, float(np.exp(min(current_energy - proposal_energy, 0.0))))
            if float(rng_namespace.generator("accept").uniform()) <= accept_prob:
                current = proposal
                current_lp = proposal_lp
                accepted += 1
                current_energy = proposal_energy
            attempted += 1
            if step_idx < max(0, int(num_warmup)):
                chain_warmup.append(current.copy())
                if accept_prob < 0.6:
                    local_step *= 0.92
                elif accept_prob > 0.8:
                    local_step *= 1.04
                local_step = min(max(local_step, 1e-4), 0.25)
                continue
            chain_posterior.append(current.copy())
            energy_trace.append(float(current_energy))
        acceptance_rate = accepted / max(attempted, 1)
        diagnostics_per_chain[str(chain_id)] = {
            "acceptance_rate": float(acceptance_rate),
            "divergences": float(divergences),
            "bfmi": float(_energy_bfmi(np.asarray(energy_trace, dtype=float))),
            "final_step_size": float(local_step),
            "max_treedepth_hits": 0.0,
        }
        warmup_draws.append(np.asarray(chain_warmup, dtype=float))
        posterior_draws.append(np.asarray(chain_posterior, dtype=float))

    warmup_arr = np.asarray(warmup_draws, dtype=float)
    posterior_arr = np.asarray(posterior_draws, dtype=float)
    diagnostics_summary = {
        "acceptance_rate": float(
            np.mean([metrics["acceptance_rate"] for metrics in diagnostics_per_chain.values()])
        ),
        "divergences": float(
            sum(metrics["divergences"] for metrics in diagnostics_per_chain.values())
        ),
        "bfmi": float(min(metrics["bfmi"] for metrics in diagnostics_per_chain.values())),
    }
    return _SamplerTrace(
        posterior_by_chain={
            "intercept": posterior_arr[:, :, 0],
            "coefficients": posterior_arr[:, :, 1:-1],
            "sigma": np.exp(posterior_arr[:, :, -1]),
        },
        warmup_by_chain={
            "intercept": warmup_arr[:, :, 0],
            "coefficients": warmup_arr[:, :, 1:-1],
            "sigma": np.exp(warmup_arr[:, :, -1]),
        },
        diagnostics_per_chain=diagnostics_per_chain,
        diagnostics_summary=diagnostics_summary,
    )


def _nuts_reference_trace(
    *,
    x: np.ndarray,
    y: np.ndarray,
    initial_state: np.ndarray,
    prior_scale: float,
    step_size: float,
    max_depth: int,
    root_seed: int,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
    target_accept: float,
) -> _SamplerTrace:
    warmup_draws: list[np.ndarray] = []
    posterior_draws: list[np.ndarray] = []
    diagnostics_per_chain: dict[str, dict[str, float]] = {}
    for chain_id in range(max(1, int(num_chains))):
        init_rng = _SamplerRngNamespace(
            root_seed=int(root_seed),
            sampler_kernel="nuts",
            chain_id=chain_id,
            phase="initialization",
            iteration=0,
        ).generator("initial_state")
        current = np.asarray(initial_state, dtype=float) + init_rng.normal(
            scale=0.03, size=initial_state.shape
        )
        local_step = max(float(step_size), 1e-4)
        chain_warmup: list[np.ndarray] = []
        chain_posterior: list[np.ndarray] = []
        energy_trace: list[float] = []
        max_depth_hits = 0
        accepted_weight = 0.0
        total_weight = 0
        divergences = 0
        for step_idx in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            phase = "warmup" if step_idx < max(0, int(num_warmup)) else "posterior"
            rng_namespace = _SamplerRngNamespace(
                root_seed=int(root_seed),
                sampler_kernel="nuts",
                chain_id=chain_id,
                phase=phase,
                iteration=step_idx,
            )
            momentum0 = rng_namespace.generator("momentum").normal(size=current.shape)
            joint0 = _joint_log_density_linear_regression(
                current,
                momentum0,
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            if not np.isfinite(joint0):
                divergences += 1
                continue
            log_slice = joint0 - float(rng_namespace.generator("slice").exponential(1.0))
            theta_minus = current.copy()
            theta_plus = current.copy()
            momentum_minus = momentum0.copy()
            momentum_plus = momentum0.copy()
            theta_candidate = current.copy()
            depth = 0
            n = 1
            continue_tree = True
            alpha_sum = 0.0
            alpha_count = 0
            while continue_tree and depth < max(1, int(max_depth)):
                direction = (
                    -1 if float(rng_namespace.generator("direction", depth).uniform()) < 0.5 else 1
                )
                if direction < 0:
                    (
                        theta_minus,
                        momentum_minus,
                        _,
                        _,
                        theta_prime,
                        n_prime,
                        s_prime,
                        alpha_prime,
                        alpha_count_prime,
                    ) = _build_nuts_tree(
                        theta_minus,
                        momentum_minus,
                        log_slice=log_slice,
                        direction=direction,
                        depth=depth,
                        step_size=local_step,
                        x=x,
                        y=y,
                        prior_scale=prior_scale,
                        joint0=joint0,
                        rng_namespace=rng_namespace,
                        path=(depth, 0),
                    )
                else:
                    (
                        _,
                        _,
                        theta_plus,
                        momentum_plus,
                        theta_prime,
                        n_prime,
                        s_prime,
                        alpha_prime,
                        alpha_count_prime,
                    ) = _build_nuts_tree(
                        theta_plus,
                        momentum_plus,
                        log_slice=log_slice,
                        direction=direction,
                        depth=depth,
                        step_size=local_step,
                        x=x,
                        y=y,
                        prior_scale=prior_scale,
                        joint0=joint0,
                        rng_namespace=rng_namespace,
                        path=(depth, 1),
                    )
                if (
                    s_prime
                    and (n + n_prime) > 0
                    and float(
                        rng_namespace.generator("candidate_accept", depth, direction).uniform()
                    )
                    < (n_prime / max(n + n_prime, 1))
                ):
                    theta_candidate = theta_prime.copy()
                n += n_prime
                continue_tree = bool(
                    s_prime
                    and _nuts_stop_criterion(theta_minus, theta_plus, momentum_minus, momentum_plus)
                )
                alpha_sum += alpha_prime
                alpha_count += alpha_count_prime
                depth += 1
            accept_rate = alpha_sum / max(alpha_count, 1)
            if depth >= max(1, int(max_depth)) and continue_tree:
                max_depth_hits += 1
            accepted_weight += accept_rate
            total_weight += 1
            current = theta_candidate
            posterior_energy = -_joint_log_density_linear_regression(
                current,
                np.zeros_like(current),
                x=x,
                y=y,
                prior_scale=prior_scale,
            )
            if step_idx < max(0, int(num_warmup)):
                chain_warmup.append(current.copy())
                if accept_rate < target_accept:
                    local_step *= 0.9
                else:
                    local_step *= 1.03
                local_step = min(max(local_step, 1e-4), 0.25)
                continue
            chain_posterior.append(current.copy())
            energy_trace.append(float(posterior_energy))
        diagnostics_per_chain[str(chain_id)] = {
            "acceptance_rate": float(accepted_weight / max(total_weight, 1)),
            "divergences": float(divergences),
            "bfmi": float(_energy_bfmi(np.asarray(energy_trace, dtype=float))),
            "final_step_size": float(local_step),
            "max_treedepth_hits": float(max_depth_hits),
        }
        warmup_draws.append(np.asarray(chain_warmup, dtype=float))
        posterior_draws.append(np.asarray(chain_posterior, dtype=float))

    warmup_arr = np.asarray(warmup_draws, dtype=float)
    posterior_arr = np.asarray(posterior_draws, dtype=float)
    diagnostics_summary = {
        "acceptance_rate": float(
            np.mean([metrics["acceptance_rate"] for metrics in diagnostics_per_chain.values()])
        ),
        "divergences": float(
            sum(metrics["divergences"] for metrics in diagnostics_per_chain.values())
        ),
        "bfmi": float(min(metrics["bfmi"] for metrics in diagnostics_per_chain.values())),
        "max_treedepth_hits": float(
            sum(metrics["max_treedepth_hits"] for metrics in diagnostics_per_chain.values())
        ),
    }
    return _SamplerTrace(
        posterior_by_chain={
            "intercept": posterior_arr[:, :, 0],
            "coefficients": posterior_arr[:, :, 1:-1],
            "sigma": np.exp(posterior_arr[:, :, -1]),
        },
        warmup_by_chain={
            "intercept": warmup_arr[:, :, 0],
            "coefficients": warmup_arr[:, :, 1:-1],
            "sigma": np.exp(warmup_arr[:, :, -1]),
        },
        diagnostics_per_chain=diagnostics_per_chain,
        diagnostics_summary=diagnostics_summary,
    )


def _diag_gaussian_log_prob(
    observations: np.ndarray,
    means: np.ndarray,
    variances: np.ndarray,
) -> np.ndarray:
    safe_variances = np.maximum(variances, 1e-6)
    diff = observations[:, None, :] - means[None, :, :]
    quadratic = np.sum((diff**2) / safe_variances[None, :, :], axis=2)
    norm = np.sum(np.log(2.0 * np.pi * safe_variances), axis=1)
    return -0.5 * (quadratic + norm[None, :])


def _fit_bayesian_gaussian_mixture(
    observations: np.ndarray,
    *,
    n_components: int,
    concentration: float,
    max_iter: int,
    seed: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    x = _coerce_observations(observations)
    n_obs, n_features = x.shape
    n_components = max(1, min(int(n_components), n_obs))

    base_var = np.var(x, axis=0, ddof=1) if n_obs > 1 else np.ones(n_features, dtype=float)
    base_var = np.maximum(base_var, 1e-3)
    init_idx = np.linspace(0, n_obs - 1, num=n_components, dtype=int)
    means = x[init_idx].copy() + rng.normal(scale=1e-3, size=(n_components, n_features))
    variances = np.broadcast_to(base_var, (n_components, n_features)).copy()
    weights = np.full(n_components, 1.0 / n_components, dtype=float)

    log_likelihood = float("-inf")
    for iteration in range(max(5, int(max_iter))):
        log_prob = _diag_gaussian_log_prob(x, means, variances) + np.log(weights + 1e-12)[None, :]
        max_log_prob = np.max(log_prob, axis=1, keepdims=True)
        stabilized = np.exp(log_prob - max_log_prob)
        normalizer = np.sum(stabilized, axis=1, keepdims=True)
        responsibilities = stabilized / np.maximum(normalizer, 1e-12)
        component_mass = np.sum(responsibilities, axis=0) + 1e-6
        weights = np.maximum(component_mass + float(concentration) - 1.0, 1e-6)
        weights = weights / np.sum(weights)
        means = (responsibilities.T @ x) / component_mass[:, None]
        diff = x[:, None, :] - means[None, :, :]
        variances = np.sum(responsibilities[:, :, None] * diff**2, axis=0) / component_mass[:, None]
        variances = np.maximum(variances, 1e-6)
        next_log_likelihood = float(
            np.sum(max_log_prob[:, 0] + np.log(np.maximum(normalizer[:, 0], 1e-12)))
        )
        if abs(next_log_likelihood - log_likelihood) < 1e-6:
            log_likelihood = next_log_likelihood
            break
        log_likelihood = next_log_likelihood

    assignments = np.argmax(responsibilities, axis=1).astype(float)
    entropy = float(
        -np.mean(np.sum(responsibilities * np.log(np.maximum(responsibilities, 1e-12)), axis=1))
    )
    return {
        "weights": weights,
        "means": means,
        "variances": variances,
        "responsibilities": responsibilities,
        "assignments": assignments,
        "component_mass": component_mass,
        "entropy": entropy,
        "log_likelihood": log_likelihood,
        "iterations": float(iteration + 1),
        "n_obs": float(n_obs),
    }


def _sorted_component_payload(fitted: Mapping[str, Any]) -> dict[str, np.ndarray]:
    weights = np.asarray(fitted["weights"], dtype=float)
    means = np.asarray(fitted["means"], dtype=float)
    variances = np.asarray(fitted["variances"], dtype=float)
    component_mass = np.asarray(fitted["component_mass"], dtype=float)
    sort_key = np.lexsort(
        (
            means[:, 0]
            if means.ndim == 2 and means.shape[1] > 0
            else np.zeros(weights.shape[0], dtype=float),
            -weights,
        )
    )
    return {
        "weights": weights[sort_key],
        "means": means[sort_key],
        "variances": variances[sort_key],
        "component_mass": component_mass[sort_key],
    }


def _prune_dp_fit(fitted: Mapping[str, Any], *, prune_threshold: float) -> dict[str, Any]:
    active = np.asarray(fitted["weights"], dtype=float) >= prune_threshold
    if not np.any(active):
        active[np.argmax(np.asarray(fitted["weights"], dtype=float))] = True
    responsibilities = np.asarray(fitted["responsibilities"], dtype=float)[:, active]
    responsibilities = responsibilities / np.maximum(
        np.sum(responsibilities, axis=1, keepdims=True),
        1e-12,
    )
    weights = np.asarray(fitted["weights"], dtype=float)[active]
    weights = weights / np.sum(weights)
    means = np.asarray(fitted["means"], dtype=float)[active]
    variances = np.asarray(fitted["variances"], dtype=float)[active]
    component_mass = np.sum(responsibilities, axis=0)
    return {
        "weights": weights,
        "means": means,
        "variances": variances,
        "responsibilities": responsibilities,
        "assignments": np.argmax(responsibilities, axis=1).astype(float),
        "component_mass": component_mass,
        "entropy": float(fitted["entropy"]),
        "log_likelihood": float(fitted["log_likelihood"]),
        "iterations": float(fitted["iterations"]),
        "n_obs": float(fitted["n_obs"]),
    }


def _mixture_posterior_result(
    *,
    method_name: str,
    fitted: Mapping[str, Any],
    concentration: float,
    diagnostics_extra: Mapping[str, Any] | None = None,
    metadata_extra: Mapping[str, Any] | None = None,
) -> PosteriorResult:
    weights = np.asarray(fitted["weights"], dtype=float)
    means = np.asarray(fitted["means"], dtype=float)
    variances = np.asarray(fitted["variances"], dtype=float)
    component_mass = np.asarray(fitted["component_mass"], dtype=float)
    n_obs = max(float(fitted.get("n_obs", means.shape[0])), 1.0)

    posterior_means: dict[str, float] = {}
    posterior_stds: dict[str, float] = {}
    credible_intervals: dict[str, tuple[float, float]] = {}
    for component_idx in range(weights.shape[0]):
        weight = float(weights[component_idx])
        weight_std = float(np.sqrt(max(weight * (1.0 - weight), 1e-9) / n_obs))
        posterior_means[f"weight_{component_idx}"] = weight
        posterior_stds[f"weight_{component_idx}"] = weight_std
        credible_intervals[f"weight_{component_idx}"] = (
            max(0.0, weight - 1.96 * weight_std),
            min(1.0, weight + 1.96 * weight_std),
        )
        for feature_idx in range(means.shape[1]):
            label = f"mean_{component_idx}_{feature_idx}"
            mean_value = float(means[component_idx, feature_idx])
            mean_std = float(
                np.sqrt(
                    max(variances[component_idx, feature_idx], 1e-9)
                    / max(component_mass[component_idx], 1.0)
                )
            )
            posterior_means[label] = mean_value
            posterior_stds[label] = mean_std
            credible_intervals[label] = (
                mean_value - 1.96 * mean_std,
                mean_value + 1.96 * mean_std,
            )
            variance_label = f"variance_{component_idx}_{feature_idx}"
            variance_value = float(variances[component_idx, feature_idx])
            variance_std = float(variance_value / np.sqrt(max(component_mass[component_idx], 1.0)))
            posterior_means[variance_label] = variance_value
            posterior_stds[variance_label] = variance_std
            credible_intervals[variance_label] = (
                max(1e-9, variance_value - 1.96 * variance_std),
                variance_value + 1.96 * variance_std,
            )

    return PosteriorResult(
        method_name=method_name,
        posterior_means=posterior_means,
        posterior_stds=posterior_stds,
        credible_intervals=credible_intervals,
        diagnostics={
            "n_components": float(weights.shape[0]),
            "log_likelihood": float(fitted["log_likelihood"]),
            "entropy": float(fitted["entropy"]),
            "iterations": float(fitted["iterations"]),
            "concentration": float(concentration),
            "num_samples": float(fitted["n_obs"]),
            **{
                str(key): float(value)
                for key, value in (diagnostics_extra or {}).items()
                if np.isfinite(float(value))
            },
        },
        metadata={
            "component_mass": component_mass.tolist(),
            "active_components": int(np.sum(weights > 1e-3)),
            **dict(metadata_extra or {}),
        },
    )


@foundry_method(
    namespace="bayesian.regression",
    version="1.0.0",
    tags={"bayesian", "hierarchical", "regression"},
)
class BayesianHierarchicalRegressionEstimator:
    """Estimate pooled and group-level coefficients with hierarchical shrinkage; avoid when group structure is absent or priors are arbitrary."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "numpyro", "jax", "jaxlib")
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz", "numpyro", "jax", "jaxlib")
    method_variant: ClassVar[str] = "hierarchical"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hierarchical",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
                SlotSpec("group_ids", SlotType.VECTOR, Unit("group", "id"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=1.5),
            ParameterSpec(name="group_scale_prior", default=1.0),
            ParameterSpec(name="num_warmup", default=128),
            ParameterSpec(name="num_samples", default=192),
            ParameterSpec(name="num_chains", default=1),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="proposal_scale", default=0.035),
            ParameterSpec(name="runtime_backend", default="auto"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Random-intercept Bayesian hierarchical regression with partial pooling across groups.",
        tags=frozenset({"bayesian", "hierarchical", "regression"}),
        when_to_use="Grouped data with partial pooling; schools, regions, time periods; partial pooling across groups",
        citations=(
            "Gelman, A. et al. (2013). Bayesian Data Analysis. 3rd ed. CRC Press.",
            "Gelman, A. & Hill, J. (2006). Data Analysis Using Regression and Multilevel/Hierarchical Models. Cambridge University Press.",
        ),
        when_not_to_use="No meaningful grouping structure; all groups have large equal samples",
        typical_min_obs=30,
        output_interpretation="Group-level estimates shrink toward grand mean. Shrinkage amount depends on group size and variance.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        x = np.asarray(payload["features"], dtype=float)
        y = np.asarray(payload["target"], dtype=float)
        group_ids = np.asarray(payload["group_ids"])
        if x.ndim != 2:
            raise ValueError("hierarchical regression expects a 2D feature matrix")
        if y.ndim != 1 or group_ids.ndim != 1:
            raise ValueError("target and group_ids must be 1D vectors")
        if x.shape[0] != y.shape[0] or group_ids.shape[0] != y.shape[0]:
            raise ValueError("features, target, and group_ids must have the same number of rows")

        _, group_index = np.unique(group_ids.astype(str), return_inverse=True)
        n_groups = int(np.max(group_index)) + 1
        prior_scale = max(1e-3, float(params.get("prior_scale", 1.5)))
        group_scale_prior = max(1e-3, float(params.get("group_scale_prior", 1.0)))
        num_warmup = max(32, int(params.get("num_warmup", 128)))
        num_samples = max(32, int(params.get("num_samples", 192)))
        num_chains = max(1, int(params.get("num_chains", 1)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        proposal_scale = max(1e-4, float(params.get("proposal_scale", 0.035)))
        backend_used = _selected_runtime_backend(params, default="numpy")

        if backend_used == "numpyro":
            posterior, runtime_diag = _numpyro_hierarchical_regression_samples(
                x=x,
                y=y,
                group_index=group_index,
                prior_scale=prior_scale,
                group_scale_prior=group_scale_prior,
                num_warmup=num_warmup,
                num_samples=num_samples,
                num_chains=num_chains,
                seed=int(params.get("__seed__", 0)),
            )
            accept_rate = float(runtime_diag.get("acceptance_rate", float("nan")))
        else:
            runtime_diag: dict[str, float] = {}
            ols_design = np.column_stack([np.ones(x.shape[0]), x])
            ols_coef = np.linalg.pinv(ols_design) @ y
            residuals = y - ols_design @ ols_coef
            sigma0 = max(float(np.std(residuals, ddof=max(ols_design.shape[1], 1))), 0.1)
            group_std = np.array(
                [np.mean(residuals[group_index == idx]) for idx in range(n_groups)],
                dtype=float,
            )
            tau0 = max(float(np.std(group_std, ddof=1)) if n_groups > 1 else 0.25, 0.1)
            initial = np.concatenate(
                [
                    np.array([ols_coef[0]], dtype=float),
                    np.asarray(ols_coef[1:], dtype=float),
                    np.zeros(n_groups, dtype=float),
                    np.array([np.log(sigma0), np.log(tau0)], dtype=float),
                ]
            )
            rng = np.random.default_rng(int(params.get("__seed__", 0)))

            def log_density(theta: np.ndarray) -> float:
                intercept = theta[0]
                beta = theta[1 : 1 + x.shape[1]]
                group_offsets = theta[1 + x.shape[1] : 1 + x.shape[1] + n_groups]
                log_sigma = theta[-2]
                log_tau = theta[-1]
                sigma = float(np.exp(log_sigma))
                tau = float(np.exp(log_tau))
                mean = intercept + x @ beta + group_offsets[group_index]
                residual = y - mean
                log_likelihood = -0.5 * np.sum(
                    (residual / sigma) ** 2 + 2.0 * log_sigma + np.log(2.0 * np.pi)
                )
                log_prior_global = -0.5 * (
                    (intercept / prior_scale) ** 2 + (log_tau / group_scale_prior) ** 2
                )
                log_prior_beta = -0.5 * np.sum((beta / prior_scale) ** 2)
                log_prior_offsets = -0.5 * np.sum(
                    (group_offsets / tau) ** 2 + 2.0 * log_tau + np.log(2.0 * np.pi)
                )
                log_prior_scale = -0.5 * (log_sigma / prior_scale) ** 2
                return float(
                    log_likelihood
                    + log_prior_global
                    + log_prior_beta
                    + log_prior_offsets
                    + log_prior_scale
                )

            draws, accept_rate = metropolis_sample(
                log_density=log_density,
                initial_state=initial,
                proposal_scale=np.full(initial.shape, proposal_scale, dtype=float),
                rng=rng,
                num_warmup=num_warmup,
                num_samples=num_samples,
                num_chains=num_chains,
            )
            posterior = {
                "global_intercept": draws[:, 0],
                "coefficients": draws[:, 1 : 1 + x.shape[1]],
                "group_effect": draws[:, 1 + x.shape[1] : 1 + x.shape[1] + n_groups],
                "sigma": np.exp(draws[:, -2]),
                "group_scale": np.exp(draws[:, -1]),
            }
        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        predictive_mean_draws = (
            np.asarray(posterior["global_intercept"], dtype=float)[:, None]
            + np.asarray(posterior["coefficients"], dtype=float) @ x.T
            + np.asarray(posterior["group_effect"], dtype=float)[:, group_index]
        ).mean(axis=1)
        decomposition = _predictive_uncertainty_decomposition(
            metric_id="hierarchical_prediction",
            predictive_mean_draws=predictive_mean_draws,
            aleatoric_scale_draws=np.asarray(posterior["sigma"], dtype=float),
            confidence_level=credible_mass,
            metadata={
                "runtime_backend_used": backend_used,
                "method_name": "bayesian_hierarchical_regression",
            },
        )
        fitted = (
            posterior_means["global_intercept"]
            + x
            @ np.asarray(
                [posterior_means.get(f"coefficients_{idx}", 0.0) for idx in range(x.shape[1])],
                dtype=float,
            )
            + np.asarray(
                [posterior_means.get(f"group_effect_{group}", 0.0) for group in group_index],
                dtype=float,
            )
        )
        prediction_output = _build_prediction_result(
            method_name="bayesian_hierarchical_regression",
            predictions=fitted,
            target=y,
            coefficients={
                "intercept": posterior_means["global_intercept"],
                **{
                    name: posterior_means.get(f"coefficients_{idx}", 0.0)
                    for idx, name in enumerate(_feature_names_from_payload(payload, x.shape[1]))
                },
            },
            model_info={"library": backend_used, "estimator": "BayesianHierarchicalRegressionMCMC"},
            metadata={
                "n_groups": n_groups,
                "num_samples": num_samples,
                **_runtime_backend_metadata(params, backend_used=backend_used),
            },
        )
        diagnostics = augment_sampler_diagnostics(
            posterior,
            diagnostics={
                "acceptance_rate": float(accept_rate),
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "n_groups": float(n_groups),
                "divergences": float(runtime_diag.get("divergences", 0.0)),
            },
            num_chains=num_chains,
            num_samples=num_samples,
            credible_mass=credible_mass,
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_hierarchical_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics=diagnostics,
            sampler_family="mcmc",
            sampler_kernel="metropolis" if backend_used == "numpy" else "nuts",
            metadata={
                "group_labels": [str(item) for item in np.unique(group_ids.astype(str))],
                "feature_names": _feature_names_from_payload(payload, x.shape[1]),
                "partial_pooling": True,
                "uncertainty_decomposition": decomposition.as_dict(),
                **_runtime_backend_metadata(params, backend_used=backend_used),
            },
        )
        return {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(
                param_name="group_scale"
            ),
        }


@foundry_method(
    namespace="bayesian.sampling",
    version="1.0.0",
    tags={"bayesian", "sampling", "hmc"},
)
class BayesianHMCRegressionEstimator:
    """Sample a Bayesian linear-regression posterior with HMC; avoid strongly multimodal or poorly scaled posteriors without reparameterization."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "numpyro", "jax", "jaxlib")
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz", "numpyro", "jax", "jaxlib")
    method_variant: ClassVar[str] = "hmc"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hmc",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=2.0),
            ParameterSpec(name="step_size", default=0.02),
            ParameterSpec(name="n_leapfrog", default=12),
            ParameterSpec(name="num_warmup", default=64),
            ParameterSpec(name="num_samples", default=128),
            ParameterSpec(name="num_chains", default=2),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="runtime_backend", default="auto"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Hamiltonian Monte Carlo sampler for Bayesian linear regression with adaptive warmup step size.",
        tags=frozenset({"bayesian", "sampling", "hmc"}),
        declared_truthfulness_tier="asymptotic",
        truthfulness_scope="posterior",
        when_to_use="Bayesian regression where Metropolis-Hastings mixes poorly; correlated posteriors; moderate sample sizes",
        citations=(
            "Neal, R. (2011). MCMC using Hamiltonian dynamics. In Handbook of Markov Chain Monte Carlo, CRC Press.",
            "Betancourt, M. (2017). A conceptual introduction to Hamiltonian Monte Carlo. arXiv:1701.02434.",
        ),
        when_not_to_use="Very high-dimensional parameter space; gradient computation is expensive",
        typical_min_obs=30,
        output_interpretation="Posterior samples over regression coefficients. Check acceptance rate (target 60–80%). HMC produces less correlated chains than Metropolis.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        x = np.asarray(payload["features"], dtype=float)
        y = np.asarray(payload["target"], dtype=float)
        if x.ndim != 2:
            raise ValueError("hmc regression expects a 2D feature matrix")
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")

        prior_scale = max(1e-3, float(params.get("prior_scale", 2.0)))
        step_size = max(1e-4, float(params.get("step_size", 0.02)))
        n_leapfrog = max(4, int(params.get("n_leapfrog", 12)))
        num_warmup = max(32, int(params.get("num_warmup", 64)))
        num_samples = max(32, int(params.get("num_samples", 128)))
        num_chains = max(1, int(params.get("num_chains", 2)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        backend_used = _selected_runtime_backend(params, default="numpy")

        if backend_used == "numpyro":
            posterior, runtime_diag = _numpyro_linear_regression_samples(
                algorithm="hmc",
                x=x,
                y=y,
                prior_scale=prior_scale,
                step_size=step_size,
                n_leapfrog=n_leapfrog,
                max_depth=5,
                target_accept=0.75,
                num_warmup=num_warmup,
                num_samples=num_samples,
                num_chains=num_chains,
                seed=int(params.get("__seed__", 0)),
            )
            accept_rate = float(runtime_diag.get("acceptance_rate", float("nan")))
            observed_budget = _bayesian_observed_tolerance_budget(
                backend_used=backend_used,
                effective_tier=DeterminismTier.STATISTICAL,
                seed=int(params.get("__seed__", 0)),
                notes=("determinism_degraded:accelerated_backend_statistical_only",),
            )
            contract_fields = {
                "sampler_family": "mcmc",
                "sampler_kernel": "hmc",
                "reproducibility": {
                    "contract_version": _REFERENCE_SAMPLER_CONTRACT,
                    "requested_determinism_tier": DeterminismTier.STATISTICAL.value,
                    "effective_determinism_tier": DeterminismTier.STATISTICAL.value,
                    "requested_runtime_backend": _requested_runtime_backend(params),
                    "effective_runtime_backend": backend_used,
                    "root_seed": int(params.get("__seed__", 0)),
                    "degradation_reasons": ["accelerated_backend_statistical_only"],
                    "route_key": dict(observed_budget.get("route_key") or {}),
                    "observed_tolerance_budget": observed_budget,
                },
                "warnings": ("determinism_degraded:accelerated_backend_statistical_only",),
                "status": "ok",
                "degradation_reason": "accelerated_backend_statistical_only",
            }
            contract_artifacts: dict[str, Any] = {}
            contract_warnings: tuple[str, ...] = contract_fields["warnings"]
            determinism_tier = DeterminismTier.STATISTICAL
        else:
            runtime_diag: dict[str, float] = {}
            ols_design = np.column_stack([np.ones(x.shape[0]), x])
            ols_coef = np.linalg.pinv(ols_design) @ y
            residual = y - ols_design @ ols_coef
            initial = np.concatenate(
                [
                    np.asarray(ols_coef, dtype=float),
                    np.array(
                        [
                            np.log(
                                max(float(np.std(residual, ddof=max(ols_design.shape[1], 1))), 0.1)
                            )
                        ],
                        dtype=float,
                    ),
                ]
            )
            trace = _hmc_reference_trace(
                x=x,
                y=y,
                initial_state=initial,
                prior_scale=prior_scale,
                step_size=step_size,
                n_leapfrog=n_leapfrog,
                root_seed=int(params.get("__seed__", 0)),
                num_warmup=num_warmup,
                num_samples=num_samples,
                num_chains=num_chains,
            )
            posterior = flatten_chain_draws(trace.posterior_by_chain)
            accept_rate = float(trace.diagnostics_summary.get("acceptance_rate", 0.0))
            contract_fields, contract_artifacts, contract_warnings, determinism_tier = (
                _reference_sampler_contract(
                    method_name="bayesian_hmc_regression",
                    sampler_kernel="hmc",
                    params=params,
                    backend_used=backend_used,
                    trace=trace,
                )
            )
        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        predictive_mean_draws = (
            np.asarray(posterior["intercept"], dtype=float)[:, None]
            + np.asarray(posterior["coefficients"], dtype=float) @ x.T
        ).mean(axis=1)
        decomposition = _predictive_uncertainty_decomposition(
            metric_id="linear_regression_prediction",
            predictive_mean_draws=predictive_mean_draws,
            aleatoric_scale_draws=np.asarray(posterior["sigma"], dtype=float),
            confidence_level=credible_mass,
            metadata={
                "runtime_backend_used": backend_used,
                "method_name": "bayesian_hmc_regression",
            },
        )
        coefficients = np.asarray(
            [posterior_means.get(f"coefficients_{idx}", 0.0) for idx in range(x.shape[1])],
            dtype=float,
        )
        predictions = posterior_means["intercept"] + x @ coefficients
        prediction_output = _build_prediction_result(
            method_name="bayesian_hmc_regression",
            predictions=predictions,
            target=y,
            coefficients={
                "intercept": posterior_means["intercept"],
                **{
                    name: posterior_means.get(f"coefficients_{idx}", 0.0)
                    for idx, name in enumerate(_feature_names_from_payload(payload, x.shape[1]))
                },
            },
            model_info={"library": backend_used, "estimator": "BayesianHMCRegression"},
            metadata={
                "num_samples": num_samples,
                "num_chains": num_chains,
                **_runtime_backend_metadata(params, backend_used=backend_used),
            },
        )
        diagnostics = augment_sampler_diagnostics(
            posterior,
            diagnostics={
                "acceptance_rate": float(accept_rate),
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "step_size": float(step_size),
                "n_leapfrog": float(n_leapfrog),
                "divergences": float(runtime_diag.get("divergences", 0.0)),
            },
            num_chains=num_chains,
            num_samples=num_samples,
            credible_mass=credible_mass,
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_hmc_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics=diagnostics,
            **contract_fields,
            metadata={
                "feature_names": _feature_names_from_payload(payload, x.shape[1]),
                "uncertainty_decomposition": decomposition.as_dict(),
                **_runtime_backend_metadata(params, backend_used=backend_used),
            },
        )
        result = {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(param_name="sigma"),
        }
        if contract_artifacts:
            result["__bayesian_artifacts__"] = contract_artifacts
        if contract_warnings:
            result["__bayesian_warnings__"] = contract_warnings
        result["__determinism_tier__"] = determinism_tier
        return result


@foundry_method(
    namespace="bayesian.sampling",
    version="1.0.0",
    tags={"bayesian", "sampling", "nuts"},
)
class BayesianNUTSRegressionEstimator:
    """Sample a Bayesian linear-regression posterior with NUTS-style path expansion; avoid expensive runs on very large design matrices."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "numpyro", "jax", "jaxlib")
    optional_deps: ClassVar[tuple[str, ...]] = ("arviz", "numpyro", "jax", "jaxlib")
    method_variant: ClassVar[str] = "nuts"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="nuts",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("target", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="prior_scale", default=2.0),
            ParameterSpec(name="step_size", default=0.018),
            ParameterSpec(name="max_depth", default=5),
            ParameterSpec(name="target_accept", default=0.75),
            ParameterSpec(name="num_warmup", default=64),
            ParameterSpec(name="num_samples", default=128),
            ParameterSpec(name="num_chains", default=2),
            ParameterSpec(name="credible_mass", default=0.9),
            ParameterSpec(name="runtime_backend", default="auto"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="No-U-Turn Sampler for Bayesian linear regression with dynamic trajectory expansion.",
        tags=frozenset({"bayesian", "sampling", "nuts"}),
        declared_truthfulness_tier="asymptotic",
        truthfulness_scope="posterior",
        when_to_use="Bayesian regression requiring efficient exploration of curved posteriors; preferred over HMC when step count is hard to tune",
        citations=(
            "Hoffman, M. & Gelman, A. (2014). The No-U-Turn sampler: Adaptively setting path lengths in Hamiltonian Monte Carlo. JMLR, 15, 1593-1623.",
        ),
        when_not_to_use="Very high-dimensional or non-differentiable posteriors; speed-critical contexts where VI suffices",
        typical_min_obs=30,
        output_interpretation="Posterior samples with dynamic trajectory length. NUTS typically achieves higher ESS per sample than Metropolis or fixed-step HMC.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        x = np.asarray(payload["features"], dtype=float)
        y = np.asarray(payload["target"], dtype=float)
        if x.ndim != 2:
            raise ValueError("nuts regression expects a 2D feature matrix")
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("target must be a 1D vector aligned with features")

        prior_scale = max(1e-3, float(params.get("prior_scale", 2.0)))
        step_size = max(1e-4, float(params.get("step_size", 0.018)))
        max_depth = max(3, int(params.get("max_depth", 5)))
        target_accept = min(max(float(params.get("target_accept", 0.75)), 0.5), 0.95)
        num_warmup = max(32, int(params.get("num_warmup", 64)))
        num_samples = max(32, int(params.get("num_samples", 128)))
        num_chains = max(1, int(params.get("num_chains", 2)))
        credible_mass = min(max(float(params.get("credible_mass", 0.9)), 0.5), 0.99)
        backend_used = _selected_runtime_backend(params, default="numpy")

        if backend_used == "numpyro":
            posterior, runtime_diag = _numpyro_linear_regression_samples(
                algorithm="nuts",
                x=x,
                y=y,
                prior_scale=prior_scale,
                step_size=step_size,
                n_leapfrog=8,
                max_depth=max_depth,
                target_accept=target_accept,
                num_warmup=num_warmup,
                num_samples=num_samples,
                num_chains=num_chains,
                seed=int(params.get("__seed__", 0)),
            )
            accept_rate = float(runtime_diag.get("acceptance_rate", float("nan")))
            observed_budget = _bayesian_observed_tolerance_budget(
                backend_used=backend_used,
                effective_tier=DeterminismTier.STATISTICAL,
                seed=int(params.get("__seed__", 0)),
                notes=("determinism_degraded:accelerated_backend_statistical_only",),
            )
            contract_fields = {
                "sampler_family": "mcmc",
                "sampler_kernel": "nuts",
                "reproducibility": {
                    "contract_version": _REFERENCE_SAMPLER_CONTRACT,
                    "requested_determinism_tier": DeterminismTier.STATISTICAL.value,
                    "effective_determinism_tier": DeterminismTier.STATISTICAL.value,
                    "requested_runtime_backend": _requested_runtime_backend(params),
                    "effective_runtime_backend": backend_used,
                    "root_seed": int(params.get("__seed__", 0)),
                    "degradation_reasons": ["accelerated_backend_statistical_only"],
                    "route_key": dict(observed_budget.get("route_key") or {}),
                    "observed_tolerance_budget": observed_budget,
                },
                "warnings": ("determinism_degraded:accelerated_backend_statistical_only",),
                "status": "ok",
                "degradation_reason": "accelerated_backend_statistical_only",
            }
            contract_artifacts: dict[str, Any] = {}
            contract_warnings: tuple[str, ...] = contract_fields["warnings"]
            determinism_tier = DeterminismTier.STATISTICAL
        else:
            runtime_diag: dict[str, float] = {}
            ols_design = np.column_stack([np.ones(x.shape[0]), x])
            ols_coef = np.linalg.pinv(ols_design) @ y
            residual = y - ols_design @ ols_coef
            initial = np.concatenate(
                [
                    np.asarray(ols_coef, dtype=float),
                    np.array(
                        [
                            np.log(
                                max(float(np.std(residual, ddof=max(ols_design.shape[1], 1))), 0.1)
                            )
                        ],
                        dtype=float,
                    ),
                ]
            )
            trace = _nuts_reference_trace(
                x=x,
                y=y,
                initial_state=initial,
                prior_scale=prior_scale,
                step_size=step_size,
                max_depth=max_depth,
                root_seed=int(params.get("__seed__", 0)),
                num_warmup=num_warmup,
                num_samples=num_samples,
                num_chains=num_chains,
                target_accept=target_accept,
            )
            posterior = flatten_chain_draws(trace.posterior_by_chain)
            accept_rate = float(trace.diagnostics_summary.get("acceptance_rate", 0.0))
            contract_fields, contract_artifacts, contract_warnings, determinism_tier = (
                _reference_sampler_contract(
                    method_name="bayesian_nuts_regression",
                    sampler_kernel="nuts",
                    params=params,
                    backend_used=backend_used,
                    trace=trace,
                )
            )
        posterior_means, posterior_stds, credible_intervals = summarize_posterior_samples(
            posterior,
            credible_mass=credible_mass,
        )
        predictive_mean_draws = (
            np.asarray(posterior["intercept"], dtype=float)[:, None]
            + np.asarray(posterior["coefficients"], dtype=float) @ x.T
        ).mean(axis=1)
        decomposition = _predictive_uncertainty_decomposition(
            metric_id="linear_regression_prediction",
            predictive_mean_draws=predictive_mean_draws,
            aleatoric_scale_draws=np.asarray(posterior["sigma"], dtype=float),
            confidence_level=credible_mass,
            metadata={
                "runtime_backend_used": backend_used,
                "method_name": "bayesian_nuts_regression",
            },
        )
        coefficients = np.asarray(
            [posterior_means.get(f"coefficients_{idx}", 0.0) for idx in range(x.shape[1])],
            dtype=float,
        )
        predictions = posterior_means["intercept"] + x @ coefficients
        prediction_output = _build_prediction_result(
            method_name="bayesian_nuts_regression",
            predictions=predictions,
            target=y,
            coefficients={
                "intercept": posterior_means["intercept"],
                **{
                    name: posterior_means.get(f"coefficients_{idx}", 0.0)
                    for idx, name in enumerate(_feature_names_from_payload(payload, x.shape[1]))
                },
            },
            model_info={"library": backend_used, "estimator": "BayesianNUTSRegression"},
            metadata={
                "num_samples": num_samples,
                "num_chains": num_chains,
                **_runtime_backend_metadata(params, backend_used=backend_used),
            },
        )
        diagnostics = augment_sampler_diagnostics(
            posterior,
            diagnostics={
                "acceptance_rate": float(accept_rate),
                "credible_mass": float(credible_mass),
                "num_warmup": float(num_warmup),
                "num_samples": float(num_samples),
                "num_chains": float(num_chains),
                "step_size": float(step_size),
                "max_depth": float(max_depth),
                "target_accept": float(target_accept),
                "divergences": float(runtime_diag.get("divergences", 0.0)),
            },
            num_chains=num_chains,
            num_samples=num_samples,
            credible_mass=credible_mass,
        )
        posterior_result = PosteriorResult(
            method_name="bayesian_nuts_regression",
            posterior_means=posterior_means,
            posterior_stds=posterior_stds,
            credible_intervals=credible_intervals,
            diagnostics=diagnostics,
            **contract_fields,
            metadata={
                "feature_names": _feature_names_from_payload(payload, x.shape[1]),
                "uncertainty_decomposition": decomposition.as_dict(),
                **_runtime_backend_metadata(params, backend_used=backend_used),
            },
        )
        result = {
            "result": posterior_result,
            "prediction_result": prediction_output["result"],
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(param_name="sigma"),
        }
        if contract_artifacts:
            result["__bayesian_artifacts__"] = contract_artifacts
        if contract_warnings:
            result["__bayesian_warnings__"] = contract_warnings
        result["__determinism_tier__"] = determinism_tier
        return result


@foundry_method(
    namespace="bayesian.nonparametric",
    version="1.0.0",
    tags={"bayesian", "mixture", "gaussian-mixture", "tabular", "estimation", "uncertainty"},
)
class BayesianGaussianMixtureEstimator:
    """Fit a finite Bayesian Gaussian mixture for soft clustering; avoid highly non-Gaussian clusters or too few observations."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "gaussian_mixture"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="gaussian_mixture",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "observations",
                    SlotType.MATRIX,
                    Unit("observation", "value"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=_mixture_output_slots(),
        parameters=(
            ParameterSpec(name="n_components", default=3),
            ParameterSpec(name="concentration", default=1.0),
            ParameterSpec(name="max_iter", default=64),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Finite Bayesian Gaussian mixture with diagonal covariance and Dirichlet-smoothed EM updates.",
        tags=frozenset({"bayesian", "mixture", "gaussian-mixture"}),
        when_to_use="Known number of latent clusters; density estimation with soft assignments; policy heterogeneity analysis",
        citations=(
            "Gelman, A. et al. (2013). Bayesian Data Analysis. 3rd ed. CRC Press.",
            "McLachlan, G. & Peel, D. (2000). Finite Mixture Models. Wiley.",
        ),
        when_not_to_use="Number of components is unknown (use Dirichlet Process); data has non-Gaussian cluster shapes",
        typical_min_obs=100,
        output_interpretation="Component means, weights, and soft cluster assignments per observation. Dirichlet smoothing prevents degenerate components.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        seed = int(params.get("__seed__", 0))
        n_components = int(params.get("n_components", 3))
        concentration = max(1e-3, float(params.get("concentration", 1.0)))
        max_iter = max(8, int(params.get("max_iter", 64)))
        fitted = _fit_bayesian_gaussian_mixture(
            payload["observations"],
            n_components=n_components,
            concentration=concentration,
            max_iter=max_iter,
            seed=seed,
        )
        baseline_result = _mixture_posterior_result(
            method_name="bayesian_gaussian_mixture",
            fitted=fitted,
            concentration=concentration,
        )
        baseline_sorted = _sorted_component_payload(fitted)
        interval_shifts: list[float] = []
        weight_shifts: list[float] = []
        mean_shifts: list[float] = []
        for offset in (1, 2):
            alt_fit = _fit_bayesian_gaussian_mixture(
                payload["observations"],
                n_components=n_components,
                concentration=concentration,
                max_iter=max_iter,
                seed=seed + offset,
            )
            alt_result = _mixture_posterior_result(
                method_name="bayesian_gaussian_mixture",
                fitted=alt_fit,
                concentration=concentration,
            )
            alt_sorted = _sorted_component_payload(alt_fit)
            interval_shifts.append(
                relative_interval_shift_max(
                    baseline_result.credible_intervals,
                    alt_result.credible_intervals,
                )
            )
            shared_components = min(
                baseline_sorted["weights"].shape[0],
                alt_sorted["weights"].shape[0],
            )
            if shared_components > 0:
                weight_shifts.append(
                    float(
                        np.max(
                            np.abs(
                                baseline_sorted["weights"][:shared_components]
                                - alt_sorted["weights"][:shared_components]
                            )
                        )
                    )
                )
                mean_shifts.append(
                    float(
                        np.max(
                            np.abs(
                                baseline_sorted["means"][:shared_components]
                                - alt_sorted["means"][:shared_components]
                            )
                        )
                    )
                )
        hint_diagnostics, hint_metadata = split_truthfulness_hints(
            extract_truthfulness_hints(payload, params)
        )
        posterior_result = _mixture_posterior_result(
            method_name="bayesian_gaussian_mixture",
            fitted=fitted,
            concentration=concentration,
            diagnostics_extra={
                "multistart_interval_shift_max": float(max(interval_shifts))
                if interval_shifts
                else 0.0,
                "multistart_weight_shift_max": float(max(weight_shifts)) if weight_shifts else 0.0,
                "multistart_mean_shift_max": float(max(mean_shifts)) if mean_shifts else 0.0,
                "component_collapse_fraction": float(
                    np.mean(np.asarray(fitted["component_mass"], dtype=float) < 1.0)
                ),
                **hint_diagnostics,
            },
            metadata_extra=hint_metadata,
        )
        return {
            "result": posterior_result,
            "cluster_assignments": np.asarray(fitted["assignments"], dtype=float),
            "cluster_probabilities": np.asarray(fitted["responsibilities"], dtype=float),
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(param_name="weight_0"),
        }


@foundry_method(
    namespace="bayesian.nonparametric",
    version="1.0.0",
    tags={"bayesian", "nonparametric", "dirichlet-process", "tabular", "estimation", "uncertainty"},
)
class DirichletProcessMixtureEstimator:
    """Approximate a DP mixture when cluster count is unknown; avoid very small datasets where nonparametric clustering is unstable."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_variant: ClassVar[str] = "dirichlet_process_mixture"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dirichlet_process_mixture",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "observations",
                    SlotType.MATRIX,
                    Unit("observation", "value"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=_mixture_output_slots(),
        parameters=(
            ParameterSpec(name="max_components", default=8),
            ParameterSpec(name="concentration", default=0.75),
            ParameterSpec(name="prune_threshold", default=0.05),
            ParameterSpec(name="max_iter", default=96),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Truncated Dirichlet-process Gaussian mixture with adaptive component pruning.",
        tags=frozenset({"bayesian", "nonparametric", "dirichlet-process"}),
        when_to_use="Unknown number of clusters; flexible density estimation; mixture models with unknown components",
        citations=(
            "Ferguson, T. (1973). A Bayesian analysis of some nonparametric problems. Annals of Statistics, 1(2), 209-230.",
            "Neal, R. (2000). Markov chain sampling methods for Dirichlet process mixture models. Journal of Computational and Graphical Statistics, 9(2), 249-265.",
        ),
        when_not_to_use="Number of components is known and fixed; small dataset where DP complexity is unwarranted",
        typical_min_obs=100,
        output_interpretation="Posterior distribution over number of clusters and cluster memberships. DP concentration α controls expected number of clusters.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _mapping_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        payload = _mapping_payload(state)
        seed = int(params.get("__seed__", 0))
        max_components = int(params.get("max_components", 8))
        concentration = max(1e-3, float(params.get("concentration", 0.75)))
        max_iter = max(16, int(params.get("max_iter", 96)))
        fitted = _fit_bayesian_gaussian_mixture(
            payload["observations"],
            n_components=max_components,
            concentration=concentration,
            max_iter=max_iter,
            seed=seed,
        )
        prune_threshold = min(max(float(params.get("prune_threshold", 0.05)), 0.0), 0.5)
        pruned = _prune_dp_fit(fitted, prune_threshold=prune_threshold)
        baseline_result = _mixture_posterior_result(
            method_name="dirichlet_process_mixture",
            fitted=pruned,
            concentration=concentration,
        )
        baseline_sorted = _sorted_component_payload(pruned)
        interval_shifts: list[float] = []
        weight_shifts: list[float] = []
        mean_shifts: list[float] = []
        active_component_counts = [baseline_sorted["weights"].shape[0]]
        for offset in (1, 2):
            alt_fit = _fit_bayesian_gaussian_mixture(
                payload["observations"],
                n_components=max_components,
                concentration=concentration,
                max_iter=max_iter,
                seed=seed + offset,
            )
            alt_pruned = _prune_dp_fit(alt_fit, prune_threshold=prune_threshold)
            alt_result = _mixture_posterior_result(
                method_name="dirichlet_process_mixture",
                fitted=alt_pruned,
                concentration=concentration,
            )
            alt_sorted = _sorted_component_payload(alt_pruned)
            active_component_counts.append(alt_sorted["weights"].shape[0])
            interval_shifts.append(
                relative_interval_shift_max(
                    baseline_result.credible_intervals,
                    alt_result.credible_intervals,
                )
            )
            shared_components = min(
                baseline_sorted["weights"].shape[0],
                alt_sorted["weights"].shape[0],
            )
            if shared_components > 0:
                weight_shifts.append(
                    float(
                        np.max(
                            np.abs(
                                baseline_sorted["weights"][:shared_components]
                                - alt_sorted["weights"][:shared_components]
                            )
                        )
                    )
                )
                mean_shifts.append(
                    float(
                        np.max(
                            np.abs(
                                baseline_sorted["means"][:shared_components]
                                - alt_sorted["means"][:shared_components]
                            )
                        )
                    )
                )
        hint_diagnostics, hint_metadata = split_truthfulness_hints(
            extract_truthfulness_hints(payload, params)
        )
        posterior_result = _mixture_posterior_result(
            method_name="dirichlet_process_mixture",
            fitted=pruned,
            concentration=concentration,
            diagnostics_extra={
                "multistart_interval_shift_max": float(max(interval_shifts))
                if interval_shifts
                else 0.0,
                "multistart_weight_shift_max": float(max(weight_shifts)) if weight_shifts else 0.0,
                "multistart_mean_shift_max": float(max(mean_shifts)) if mean_shifts else 0.0,
                "component_collapse_fraction": float(
                    np.mean(np.asarray(pruned["component_mass"], dtype=float) < 1.0)
                ),
                "active_component_count_std": float(np.std(active_component_counts, ddof=0)),
                **hint_diagnostics,
            },
            metadata_extra={
                "active_components": int(pruned["weights"].shape[0]),
                "prune_threshold": prune_threshold,
                **hint_metadata,
            },
        )
        return {
            "result": posterior_result,
            "cluster_assignments": np.asarray(pruned["assignments"], dtype=float),
            "cluster_probabilities": np.asarray(pruned["responsibilities"], dtype=float),
            "uncertainty_envelope": posterior_result.to_uncertainty_envelope(param_name="weight_0"),
        }


__all__ = [
    "BayesianGaussianMixtureEstimator",
    "BayesianHMCRegressionEstimator",
    "BayesianHierarchicalRegressionEstimator",
    "BayesianNUTSRegressionEstimator",
    "DirichletProcessMixtureEstimator",
]
