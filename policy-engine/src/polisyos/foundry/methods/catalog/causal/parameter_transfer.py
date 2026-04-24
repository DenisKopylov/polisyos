"""Public causal parameter transfer module API."""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Any, ClassVar

import numpy as np

from polisyos.common.logger import get_logger
from polisyos.core.observability.determinism import DeterminismTier
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
from polisyos.foundry.methods.catalog.causal.protocols import ParameterTransferData

logger = get_logger(__name__)


@foundry_method(
    namespace="causal.structural",
    version="1.0.0",
    tags={"causal", "structural", "parameters", "bridge"},
)
class ParameterTransfer:
    """Bridge context-adaptive parameter bundles to JAX-ready payloads."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="parameter_transfer",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="parameter_transfer_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("request", "json"),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="parameter_transfer_payload",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="runtime_backend", default="auto"),
            ParameterSpec(name="runtime_draws", default=256),
            ParameterSpec(name="runtime_seed", default=0),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.JAX,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Convert ContextAdaptiveParameterBundle into deterministic parameter payload "
            "for JAX/NumPyro structural methods."
        ),
        assumptions={
            "prior_shape": (
                "Output literature_priors follows SCMFitData shape: "
                "{target: {'__intercept__': {'mean': x, 'std': y}}}"
            ),
        },
        tags=frozenset({"causal", "structural", "parameters", "bridge"}),
        when_to_use="Transfer external validity / parameter estimates to a new context; incorporate prior parameter knowledge into structural estimation",
        when_not_to_use="No prior parameter bundle available; parameters are not transferable across contexts",
        output_interpretation="Parameter values with uncertainty multipliers. Literature priors formatted for JAX/NumPyro. Runtime intervals show Monte Carlo uncertainty around transferred parameters.",
    )

    @staticmethod
    def pure_step(
        state: ParameterTransferData | Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = (
            state
            if isinstance(state, ParameterTransferData)
            else ParameterTransferData.model_validate(state)
        )
        bundle = payload.parameter_bundle

        parameter_values: dict[str, float] = {}
        uncertainty_multipliers: dict[str, float] = {}
        literature_priors: dict[str, dict[str, dict[str, float]]] = {}
        warnings: list[str] = []

        for parameter_name, parameter in sorted(bundle.parameters.items()):
            if parameter.value is None:
                warnings.append(f"parameter '{parameter_name}' has no scalar value and was skipped")
                continue

            try:
                mean_value = float(parameter.value)
            except (TypeError, ValueError):
                warnings.append(
                    f"parameter '{parameter_name}' value is non-numeric and was skipped"
                )
                continue

            applicability = bundle.applicability.get(parameter_name)
            multiplier = 1.0
            if applicability is not None:
                multiplier = float(applicability.uncertainty_multiplier)
            multiplier = max(1.0, multiplier)

            base_std = _estimate_std(parameter)
            std_value = max(base_std * multiplier, 1.0e-6)

            parameter_values[parameter_name] = mean_value
            uncertainty_multipliers[parameter_name] = multiplier
            literature_priors[parameter_name] = {
                "__intercept__": {"mean": mean_value, "std": std_value}
            }

        if bundle.unsupported_parameters:
            warnings.append(
                "unsupported parameters: " + ", ".join(sorted(bundle.unsupported_parameters))
            )

        runtime_requested = _normalize_runtime_backend(params.get("runtime_backend"))
        runtime_draws = max(32, int(params.get("runtime_draws", 256) or 256))
        runtime_seed = int(params.get("runtime_seed", 0) or 0)
        backend_used, fallback_reason = _resolve_runtime_backend(runtime_requested)
        runtime_intervals, runtime_warning = _runtime_intervals_from_priors(
            literature_priors=literature_priors,
            backend=backend_used,
            draws=runtime_draws,
            seed=runtime_seed,
        )
        if runtime_warning:
            warnings.append(runtime_warning)

        return {
            "parameter_values": parameter_values,
            "uncertainty_multipliers": uncertainty_multipliers,
            "literature_priors": literature_priors,
            "unsupported_parameters": list(bundle.unsupported_parameters),
            "warnings": warnings,
            "skg_snapshot_ref": bundle.skg_snapshot_ref,
            "skg_version_id": bundle.skg_version_id,
            "runtime_backend_requested": runtime_requested,
            "runtime_backend_used": backend_used,
            "runtime_backend_fallback_reason": fallback_reason,
            "runtime_draws": runtime_draws,
            "runtime_seed": runtime_seed,
            "runtime_parameter_intervals": runtime_intervals,
            "runtime_ready": bool(runtime_intervals),
            "runtime_engine_versions": _runtime_engine_versions(backend_used),
        }


def _estimate_std(parameter: Any) -> float:
    confidence_interval = getattr(parameter, "confidence_interval", None)
    if isinstance(confidence_interval, tuple) and len(confidence_interval) == 2:
        try:
            lo = float(confidence_interval[0])
            hi = float(confidence_interval[1])
        except (TypeError, ValueError) as exc:
            logger.debug(
                "Failed to parse confidence_interval for parameter std estimation: %s",
                exc,
            )
            lo, hi = 0.0, 0.0
        width = max(0.0, hi - lo)
        if width > 0.0:
            # Approximate 95% CI width for normal uncertainty.
            return max(width / 3.92, 1.0e-6)

    std_error = getattr(parameter, "std_error", None)
    if std_error is not None:
        try:
            parsed = float(std_error)
        except (TypeError, ValueError) as exc:
            logger.debug(
                "Failed to parse std_error for parameter std estimation: %s",
                exc,
            )
            parsed = 0.0
        if parsed > 0.0:
            return parsed

    mean = getattr(parameter, "value", None)
    if mean is not None:
        try:
            return max(abs(float(mean)) * 0.1, 1.0e-6)
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)
    return 0.1


def _normalize_runtime_backend(raw: Any) -> str:
    token = str(raw or "auto").strip().lower()
    if token not in {"auto", "numpyro", "jax", "numpy"}:
        return "auto"
    return token


def _resolve_runtime_backend(requested: str) -> tuple[str, str | None]:
    numpyro_available = _module_available("numpyro")
    jax_available = _module_available("jax")
    if requested == "numpyro":
        if numpyro_available:
            return "numpyro", None
        return "jax" if jax_available else "numpy", "numpyro_unavailable"
    if requested == "jax":
        if jax_available:
            return "jax", None
        return "numpy", "jax_unavailable"
    if requested == "numpy":
        return "numpy", None
    # auto
    if numpyro_available:
        return "numpyro", None
    if jax_available:
        return "jax", "auto_selected_jax:numpyro_unavailable"
    return "numpy", "auto_selected_numpy:numpyro_and_jax_unavailable"


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _runtime_intervals_from_priors(
    *,
    literature_priors: dict[str, dict[str, dict[str, float]]],
    backend: str,
    draws: int,
    seed: int,
) -> tuple[dict[str, dict[str, float]], str | None]:
    if not literature_priors:
        return {}, None

    if backend == "numpyro":
        try:
            return _runtime_intervals_numpyro(
                literature_priors=literature_priors,
                draws=draws,
                seed=seed,
            ), None
        except Exception as exc:
            fallback = "jax" if _module_available("jax") else "numpy"
            intervals, _ = _runtime_intervals_from_priors(
                literature_priors=literature_priors,
                backend=fallback,
                draws=draws,
                seed=seed,
            )
            return intervals, f"numpyro_runtime_failed:{type(exc).__name__}:{exc}"
    if backend == "jax":
        return _runtime_intervals_jax(
            literature_priors=literature_priors,
            draws=draws,
            seed=seed,
        ), None
    return _runtime_intervals_numpy(
        literature_priors=literature_priors,
        draws=draws,
        seed=seed,
    ), None


def _runtime_intervals_numpyro(
    *,
    literature_priors: dict[str, dict[str, dict[str, float]]],
    draws: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    jnp = import_module("jax.numpy")
    jrandom = import_module("jax.random")
    dist = import_module("numpyro.distributions")

    key = jrandom.PRNGKey(seed)
    output: dict[str, dict[str, float]] = {}
    for parameter_name in sorted(literature_priors):
        prior = literature_priors[parameter_name].get("__intercept__", {})
        mean = float(prior.get("mean", 0.0))
        std = max(1.0e-6, float(prior.get("std", 0.1)))
        key, subkey = jrandom.split(key)
        samples = dist.Normal(loc=mean, scale=std).sample(subkey, sample_shape=(draws,))
        output[parameter_name] = {
            "mean": float(jnp.mean(samples)),
            "std": float(jnp.std(samples)),
            "ci_low": float(jnp.quantile(samples, 0.025)),
            "ci_high": float(jnp.quantile(samples, 0.975)),
            "draws": float(draws),
        }
    return output


def _runtime_intervals_jax(
    *,
    literature_priors: dict[str, dict[str, dict[str, float]]],
    draws: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    jnp = import_module("jax.numpy")
    jrandom = import_module("jax.random")

    key = jrandom.PRNGKey(seed)
    output: dict[str, dict[str, float]] = {}
    for parameter_name in sorted(literature_priors):
        prior = literature_priors[parameter_name].get("__intercept__", {})
        mean = float(prior.get("mean", 0.0))
        std = max(1.0e-6, float(prior.get("std", 0.1)))
        key, subkey = jrandom.split(key)
        samples = mean + std * jrandom.normal(subkey, shape=(draws,))
        output[parameter_name] = {
            "mean": float(jnp.mean(samples)),
            "std": float(jnp.std(samples)),
            "ci_low": float(jnp.quantile(samples, 0.025)),
            "ci_high": float(jnp.quantile(samples, 0.975)),
            "draws": float(draws),
        }
    return output


def _runtime_intervals_numpy(
    *,
    literature_priors: dict[str, dict[str, dict[str, float]]],
    draws: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(seed)
    output: dict[str, dict[str, float]] = {}
    for parameter_name in sorted(literature_priors):
        prior = literature_priors[parameter_name].get("__intercept__", {})
        mean = float(prior.get("mean", 0.0))
        std = max(1.0e-6, float(prior.get("std", 0.1)))
        samples = rng.normal(loc=mean, scale=std, size=draws)
        output[parameter_name] = {
            "mean": float(np.mean(samples)),
            "std": float(np.std(samples)),
            "ci_low": float(np.quantile(samples, 0.025)),
            "ci_high": float(np.quantile(samples, 0.975)),
            "draws": float(draws),
        }
    return output


def _runtime_engine_versions(backend: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    if backend in {"jax", "numpyro"}:
        jax_ver = _safe_version("jax")
        if jax_ver:
            versions["jax"] = jax_ver
    if backend == "numpyro":
        numpyro_ver = _safe_version("numpyro")
        if numpyro_ver:
            versions["numpyro"] = numpyro_ver
    return versions


def _safe_version(name: str) -> str | None:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return None


__all__ = ["ParameterTransfer"]
