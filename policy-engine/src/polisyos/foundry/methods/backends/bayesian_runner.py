"""Public backends bayesian runner module API."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from polisyos.core.canon import truncated_hash
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    capture_backend_runtime_fingerprint,
    capture_versions,
    runtime_stack_for,
    safe_version,
)
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.io import dematerialize_method_output

_ENGINE_PACKAGES = {
    "numpy": "numpy",
    "numpyro": "numpyro",
    "jax": "jax",
    "jaxlib": "jaxlib",
    "arviz": "arviz",
    "sbi": "sbi",
    "torch": "torch",
    "pymc": "pymc",
    "pymc_bart": "pymc-bart",
}
_FIRST_CLASS_ENGINE = {
    "hmc": "numpyro",
    "nuts": "numpyro",
    "hierarchical": "numpyro",
    "npe": "sbi",
    "nle": "sbi",
    "nre": "sbi",
    "bart": "pymc_bart",
}
_RUNTIME_OPTIONS = {
    "hmc": frozenset({"auto", "numpy", "numpyro"}),
    "nuts": frozenset({"auto", "numpy", "numpyro"}),
    "hierarchical": frozenset({"auto", "numpy", "numpyro"}),
    "npe": frozenset({"auto", "sbi"}),
    "nle": frozenset({"auto", "sbi"}),
    "nre": frozenset({"auto", "sbi"}),
    "bart": frozenset({"auto", "pymc_bart"}),
}


def _resolve_params(signature: MethodSignature, params: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    known = {p.name for p in signature.parameters}
    unknown = set(params.keys()) - known
    if unknown:
        raise ValueError(f"Unknown parameters for {signature.fqn}: {sorted(unknown)}")
    for param in signature.parameters:
        result[param.name] = params.get(param.name, param.default)
    return result


@dataclass(frozen=True, slots=True)
class BayesianEngineStatus:
    """Describe one optional Bayesian runtime engine."""

    engine: str
    available: bool
    version: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "available": self.available,
            "version": self.version,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class BayesianBackendHealth:
    """Summarize which Bayesian execution engines are actually installed."""

    method_variant: str | None
    preferred_engine: str
    default_runtime: str
    engines: tuple[BayesianEngineStatus, ...]
    warnings: tuple[str, ...] = ()

    @property
    def is_available(self) -> bool:
        availability = {status.engine: status.available for status in self.engines}
        variant = self.method_variant or ""
        if variant in {"npe", "nle", "nre"}:
            return bool(availability.get("sbi")) and bool(availability.get("torch"))
        if variant == "bart":
            return bool(availability.get("pymc")) and bool(availability.get("pymc_bart"))
        return bool(availability.get("numpy"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "method_variant": self.method_variant,
            "preferred_engine": self.preferred_engine,
            "default_runtime": self.default_runtime,
            "available": self.is_available,
            "warnings": list(self.warnings),
            "engines": [status.as_dict() for status in self.engines],
        }


class BayesianBackendUnavailableError(RuntimeError):
    """Signal that the requested Bayesian runtime backend is unavailable."""

    def __init__(
        self,
        *,
        requested_runtime: str,
        method_variant: str | None,
        health: BayesianBackendHealth,
    ) -> None:
        self.requested_runtime = requested_runtime
        self.method_variant = method_variant
        self.health = health
        super().__init__(self.__str__())

    def __str__(self) -> str:
        variant = self.method_variant or "generic"
        return (
            f"Bayesian runtime backend '{self.requested_runtime}' is unavailable for "
            f"variant '{variant}'. Installed engines: "
            f"{', '.join(f'{item.engine}={item.available}' for item in self.health.engines)}"
        )


def _variant_for(method_class: type | None) -> str | None:
    if method_class is None:
        return None
    raw = getattr(method_class, "method_variant", None)
    if raw is None:
        return None
    value = str(raw).strip().lower()
    return value or None


def bayesian_backend_health(method_class: type | None = None) -> BayesianBackendHealth:
    """Report installed Bayesian engines and the runtime selected for one method."""

    variant = _variant_for(method_class)
    preferred_engine = _FIRST_CLASS_ENGINE.get(variant or "", "numpy")
    engine_statuses = tuple(
        BayesianEngineStatus(
            engine=engine,
            available=(version := safe_version(package_name)) is not None,
            version=version,
            detail=None if version is not None else f"missing_dependency:{package_name}",
        )
        for engine, package_name in _ENGINE_PACKAGES.items()
    )
    availability = {status.engine: status.available for status in engine_statuses}

    if variant in {"npe", "nle", "nre"}:
        default_runtime = "sbi" if availability.get("sbi") and availability.get("torch") else "unavailable"
    elif variant == "bart":
        default_runtime = (
            "pymc_bart"
            if availability.get("pymc") and availability.get("pymc_bart")
            else "unavailable"
        )
    elif preferred_engine == "numpyro":
        default_runtime = "numpyro" if availability.get("numpyro") else "numpy"
    else:
        default_runtime = "numpy"

    warnings: list[str] = []
    if preferred_engine == "numpyro" and default_runtime == "numpy":
        warnings.append("numpyro_unavailable:using_numpy_fallback")
    if variant in {"npe", "nle", "nre"} and default_runtime == "unavailable":
        warnings.append("sbi_stack_unavailable")
    if variant == "bart" and default_runtime == "unavailable":
        warnings.append("pymc_bart_stack_unavailable")

    return BayesianBackendHealth(
        method_variant=variant,
        preferred_engine=preferred_engine,
        default_runtime=default_runtime,
        engines=engine_statuses,
        warnings=tuple(warnings),
    )


def _resolve_runtime_backend(
    *,
    method_class: type,
    params: Mapping[str, Any],
    health: BayesianBackendHealth,
) -> tuple[str, tuple[str, ...]]:
    variant = _variant_for(method_class)
    allowed = _RUNTIME_OPTIONS.get(variant or "", frozenset({"auto", "numpy"}))
    requested = str(params.get("runtime_backend", "auto")).strip().lower() or "auto"
    if requested not in allowed:
        raise ValueError(
            f"Unsupported runtime_backend={requested!r} for variant "
            f"{variant or 'generic'}; expected one of {sorted(allowed)}"
        )
    if requested == "auto":
        if health.default_runtime == "unavailable":
            raise BayesianBackendUnavailableError(
                requested_runtime=requested,
                method_variant=variant,
                health=health,
            )
        return health.default_runtime, health.warnings

    availability = {status.engine: status.available for status in health.engines}
    if requested == "numpyro" and not availability.get("numpyro", False):
        raise BayesianBackendUnavailableError(
            requested_runtime=requested,
            method_variant=variant,
            health=health,
        )
    if requested == "sbi" and not (availability.get("sbi", False) and availability.get("torch", False)):
        raise BayesianBackendUnavailableError(
            requested_runtime=requested,
            method_variant=variant,
            health=health,
        )
    if requested == "pymc_bart" and not (
        availability.get("pymc", False) and availability.get("pymc_bart", False)
    ):
        raise BayesianBackendUnavailableError(
            requested_runtime=requested,
            method_variant=variant,
            health=health,
        )
    if requested == "numpy" and not availability.get("numpy", False):
        raise BayesianBackendUnavailableError(
            requested_runtime=requested,
            method_variant=variant,
            health=health,
        )
    return requested, ()


def _version_packages_for_runtime(runtime_backend: str) -> tuple[str, ...]:
    if runtime_backend == "numpyro":
        return ("numpy", "arviz", "numpyro", "jax", "jaxlib", "scipy", "xarray")
    if runtime_backend == "sbi":
        return ("numpy", "sbi", "torch", "scipy")
    if runtime_backend == "pymc_bart":
        return ("numpy", "pymc", "pymc-bart", "arviz", "scipy")
    return ("numpy", "arviz", "scipy", "xarray")


class BayesianRunner(MethodRunner):
    """Bayesian runner public type."""
    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({ComputeBackend.BAYESIAN})

    def is_available(self) -> bool:
        return bayesian_backend_health().is_available

    def execute(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        health = bayesian_backend_health(method_class)
        if not health.is_available:
            raise BayesianBackendUnavailableError(
                requested_runtime="auto",
                method_variant=_variant_for(method_class),
                health=health,
            )
        runtime_backend, runtime_warnings = _resolve_runtime_backend(
            method_class=method_class,
            params=params,
            health=health,
        )
        resolved = _resolve_params(signature, params)
        resolved["__rng__"] = np.random.default_rng(seed)
        resolved["__seed__"] = seed
        resolved["__bayesian_runtime_backend__"] = runtime_backend
        resolved["__bayesian_backend_health__"] = health.as_dict()

        started = time.perf_counter()
        output = method_class.pure_step(state, resolved)
        wall_ms = (time.perf_counter() - started) * 1000

        determinism_tier = DeterminismTier.STATISTICAL
        artifacts: dict[str, Any] = {
            "bayesian_backend_health": health.as_dict(),
            "bayesian_runtime_backend": runtime_backend,
        }
        warnings = list(runtime_warnings)
        class_tier = getattr(method_class, "determinism_tier", None)
        if isinstance(class_tier, DeterminismTier):
            determinism_tier = class_tier
        if isinstance(output, dict):
            maybe_tier = output.get("__determinism_tier__")
            if isinstance(maybe_tier, DeterminismTier):
                determinism_tier = maybe_tier
                output = dict(output)
                output.pop("__determinism_tier__", None)
            maybe_artifacts = output.get("__bayesian_artifacts__")
            if isinstance(maybe_artifacts, Mapping):
                output = dict(output)
                output.pop("__bayesian_artifacts__", None)
                artifacts.update({str(key): value for key, value in maybe_artifacts.items()})
            maybe_warnings = output.get("__bayesian_warnings__")
            if isinstance(maybe_warnings, (list, tuple, set, frozenset)):
                output = dict(output)
                output.pop("__bayesian_warnings__", None)
                warnings.extend(str(item) for item in maybe_warnings)

        runtime_stack = runtime_stack_for(method_class)
        versions = capture_versions(
            base_packages=_version_packages_for_runtime(runtime_backend),
            runtime_stack=runtime_stack,
        )
        posture = capture_backend_runtime_fingerprint(
            ComputeBackend.BAYESIAN,
            method_class=method_class,
            seed=seed,
            runtime_backend=runtime_backend,
            available=health.is_available,
            extra_versions=versions,
            notes=tuple(str(item) for item in warnings),
        )
        fp_payload = {
            "backend": ComputeBackend.BAYESIAN.value,
            "runtime_backend": runtime_backend,
            "seed": seed,
            "versions": versions,
            "runtime_stack": runtime_stack,
        }
        fingerprint = truncated_hash(json.dumps(fp_payload, sort_keys=True), length=16)
        slot_outputs = dematerialize_method_output(
            method_class=method_class,
            signature=signature,
            output=output,
        )

        return MethodResult(
            output=output,
            timing=MethodTiming(wall_time_ms=wall_ms),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.BAYESIAN,
                determinism_tier=determinism_tier,
                seed=seed,
                library_versions=versions,
                fingerprint=fingerprint,
                note=posture.replay_semantics,
            ),
            slot_outputs=slot_outputs,
            artifacts={**artifacts, "backend_runtime_fingerprint": posture.as_dict()},
            warnings=tuple(dict.fromkeys(warnings)),
        )


__all__ = [
    "BayesianBackendHealth",
    "BayesianBackendUnavailableError",
    "BayesianEngineStatus",
    "BayesianRunner",
    "bayesian_backend_health",
]
