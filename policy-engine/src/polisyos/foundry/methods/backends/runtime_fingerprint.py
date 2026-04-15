"""Public backends runtime fingerprint module API."""
from __future__ import annotations

import json
from importlib import metadata
from dataclasses import dataclass, field
from typing import Any, Mapping

from polisyos.common.config import build_process_bootstrap_config
from polisyos.core.canon import truncated_hash
from polisyos.core.observability.determinism import DeterminismTier, get_determinism_tier
from polisyos.foundry.methods.base import ComputeBackend

_PACKAGE_ALIASES = {
    "sklearn": "scikit-learn",
}

_SOLVER_PACKAGES = ("ortools", "pulp", "scipy", "cvxpy", "pymoo")
_NUMPY_PACKAGES = ("numpy", "scipy", "statsmodels", "pandas")
_JAX_PACKAGES = ("jax", "jaxlib")
_BAYESIAN_PACKAGES = ("numpy", "scipy", "arviz", "xarray")


@dataclass(frozen=True, slots=True)
class BackendRuntimeFingerprint:
    """Observed backend posture used for availability and replay reporting."""

    backend: ComputeBackend
    available: bool
    determinism_tier: DeterminismTier | None
    execution_device: str | None
    runtime_stack: tuple[str, ...]
    library_versions: Mapping[str, str] = field(default_factory=dict)
    runtime_backend: str | None = None
    seed: int | None = None
    notes: tuple[str, ...] = ()

    @property
    def replay_semantics(self) -> str:
        return replay_semantics_for_tier(self.determinism_tier)

    @property
    def tolerance_budget(self) -> dict[str, Any]:
        return tolerance_budget_for_tier(self.determinism_tier)

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend.value,
            "available": self.available,
            "determinism_tier": None if self.determinism_tier is None else self.determinism_tier.value,
            "execution_device": self.execution_device,
            "runtime_stack": list(self.runtime_stack),
            "library_versions": dict(self.library_versions),
            "runtime_backend": self.runtime_backend,
            "seed": self.seed,
            "notes": list(self.notes),
            "replay_semantics": self.replay_semantics,
            "tolerance_budget": self.tolerance_budget,
            "fingerprint": self.compute_hash(),
        }

    def compute_hash(self) -> str:
        payload = {
            "backend": self.backend.value,
            "available": self.available,
            "determinism_tier": None if self.determinism_tier is None else self.determinism_tier.value,
            "execution_device": self.execution_device,
            "runtime_stack": list(self.runtime_stack),
            "library_versions": dict(sorted(self.library_versions.items())),
            "runtime_backend": self.runtime_backend,
            "seed": self.seed,
            "notes": list(self.notes),
        }
        return truncated_hash(json.dumps(payload, sort_keys=True), length=16)


def safe_version(package_name: str) -> str | None:
    """Safe version helper."""
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def tolerance_budget_for_tier(tier: DeterminismTier | None) -> dict[str, Any]:
    """Describe replay tolerance budgets for one determinism tier."""
    if tier is DeterminismTier.STRICT_CPU:
        return {
            "same_architecture_abs_tol": 0.0,
            "same_architecture_rel_tol": 0.0,
            "cross_architecture_abs_tol": 1.0e-9,
            "cross_architecture_rel_tol": 1.0e-8,
            "semantic_mode": "bit_exact_same_isa",
        }
    if tier is DeterminismTier.LIBRARY_DETERMINISTIC:
        return {
            "same_architecture_abs_tol": 1.0e-12,
            "same_architecture_rel_tol": 1.0e-12,
            "cross_architecture_abs_tol": 1.0e-9,
            "cross_architecture_rel_tol": 1.0e-8,
            "semantic_mode": "library_exact_cpu",
        }
    if tier is DeterminismTier.BEST_EFFORT_GPU:
        return {
            "same_architecture_abs_tol": 1.0e-6,
            "same_architecture_rel_tol": 1.0e-5,
            "cross_architecture_abs_tol": 1.0e-4,
            "cross_architecture_rel_tol": 1.0e-3,
            "semantic_mode": "near_deterministic_gpu",
        }
    if tier is DeterminismTier.STATISTICAL:
        return {
            "same_architecture_abs_tol": None,
            "same_architecture_rel_tol": None,
            "cross_architecture_abs_tol": None,
            "cross_architecture_rel_tol": None,
            "semantic_mode": "distributional_replay",
        }
    return {
        "same_architecture_abs_tol": None,
        "same_architecture_rel_tol": None,
        "cross_architecture_abs_tol": None,
        "cross_architecture_rel_tol": None,
        "semantic_mode": "best_effort",
    }


def replay_semantics_for_tier(tier: DeterminismTier | None) -> str:
    """Human-readable replay contract for one determinism tier."""
    if tier is DeterminismTier.STRICT_CPU:
        return "Replay must be bit-exact on the same CPU ISA; x86_64 vs arm64 uses tolerance budget."
    if tier is DeterminismTier.LIBRARY_DETERMINISTIC:
        return "Replay must match exactly within the same CPU/library stack; cross-ISA uses tolerance budget."
    if tier is DeterminismTier.BEST_EFFORT_GPU:
        return "Replay should match within near-deterministic GPU tolerances on the same device family."
    if tier is DeterminismTier.STATISTICAL:
        return "Replay is seed-stable only up to statistical envelopes, not bitwise equality."
    return "Replay is best-effort only; exact equality is not guaranteed."


def runtime_stack_for(method_class: type) -> tuple[str, ...]:
    """Runtime stack for helper."""
    runtime_stack = getattr(method_class, "runtime_stack", ())
    if isinstance(runtime_stack, str):
        runtime_stack = (runtime_stack,)
    if isinstance(runtime_stack, (list, tuple, set, frozenset)):
        values = [str(item).strip() for item in runtime_stack if str(item).strip()]
        return tuple(dict.fromkeys(values))
    return ()


def capture_versions(
    *,
    base_packages: tuple[str, ...],
    runtime_stack: tuple[str, ...],
) -> dict[str, str]:
    """Capture versions helper."""
    versions: dict[str, str] = {}
    packages = list(base_packages)
    for item in runtime_stack:
        packages.append(_PACKAGE_ALIASES.get(item, item))
    for package_name in dict.fromkeys(packages):
        version = safe_version(package_name)
        if version:
            versions[package_name] = version
    return versions


def default_determinism_tier_for_backend(
    backend: ComputeBackend,
    *,
    device: str | None = None,
) -> DeterminismTier | None:
    """Infer the backend determinism tier from the observed runtime posture."""
    configured = get_determinism_tier()
    if configured is not None:
        return configured
    if backend is ComputeBackend.JAX:
        normalized = (device or "").lower()
        if normalized.startswith("cpu"):
            return DeterminismTier.STRICT_CPU
        deterministic_ops = "--xla_gpu_deterministic_ops=true" in build_process_bootstrap_config().xla_flags
        if normalized.startswith("gpu") and deterministic_ops:
            return DeterminismTier.BEST_EFFORT_GPU
        return DeterminismTier.NONDETERMINISTIC
    if backend in {ComputeBackend.NUMPY, ComputeBackend.SOLVER}:
        return DeterminismTier.LIBRARY_DETERMINISTIC
    if backend is ComputeBackend.BAYESIAN:
        return DeterminismTier.STATISTICAL
    return None


def capture_backend_runtime_fingerprint(
    backend: ComputeBackend,
    *,
    method_class: type | None = None,
    seed: int | None = None,
    runtime_backend: str | None = None,
    available: bool | None = None,
    extra_versions: Mapping[str, str] | None = None,
    notes: tuple[str, ...] = (),
) -> BackendRuntimeFingerprint:
    """Capture an execution-ready backend posture for methods and catalog snapshots."""
    runtime_stack = runtime_stack_for(method_class) if method_class is not None else ()
    versions: dict[str, str] = {}
    device: str | None = None

    if backend is ComputeBackend.JAX:
        jax_version = safe_version("jax")
        jaxlib_version = safe_version("jaxlib")
        runtime_available = jax_version is not None and jaxlib_version is not None
        if runtime_available:
            import jax

            versions.update(capture_versions(base_packages=_JAX_PACKAGES, runtime_stack=runtime_stack))
            devices = jax.devices()
            if devices:
                first_device = devices[0]
                device = f"{first_device.platform}:{first_device.device_kind}"
            else:
                device = f"{jax.default_backend()}:unknown"
        else:
            versions.update(capture_versions(base_packages=_JAX_PACKAGES, runtime_stack=runtime_stack))
        is_available = runtime_available if available is None else available
    elif backend is ComputeBackend.SOLVER:
        versions.update(capture_versions(base_packages=_SOLVER_PACKAGES, runtime_stack=runtime_stack))
        device = "cpu:solver"
        runtime_available = any(package in versions for package in _SOLVER_PACKAGES)
        is_available = runtime_available if available is None else available
    elif backend is ComputeBackend.BAYESIAN:
        base_packages = tuple(dict.fromkeys(_BAYESIAN_PACKAGES + (() if runtime_backend is None else (runtime_backend,))))
        versions.update(capture_versions(base_packages=base_packages, runtime_stack=runtime_stack))
        device = "cpu:bayesian"
        runtime_available = bool(versions)
        is_available = runtime_available if available is None else available
    else:
        versions.update(capture_versions(base_packages=_NUMPY_PACKAGES, runtime_stack=runtime_stack))
        device = "cpu:numpy"
        runtime_available = safe_version("numpy") is not None
        is_available = runtime_available if available is None else available

    if extra_versions:
        versions.update({str(key): str(value) for key, value in extra_versions.items() if value})

    tier = default_determinism_tier_for_backend(backend, device=device) if is_available else None
    return BackendRuntimeFingerprint(
        backend=backend,
        available=is_available,
        determinism_tier=tier,
        execution_device=device,
        runtime_stack=runtime_stack,
        runtime_backend=runtime_backend,
        library_versions=dict(sorted(versions.items())),
        seed=seed,
        notes=notes,
    )


__all__ = [
    "BackendRuntimeFingerprint",
    "capture_backend_runtime_fingerprint",
    "capture_versions",
    "default_determinism_tier_for_backend",
    "replay_semantics_for_tier",
    "runtime_stack_for",
    "safe_version",
    "tolerance_budget_for_tier",
]
