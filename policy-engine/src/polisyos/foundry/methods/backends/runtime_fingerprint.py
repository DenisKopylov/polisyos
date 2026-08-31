"""Capture backend runtime posture for method availability and replay evidence."""

from __future__ import annotations

import json
import platform
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any

from polisyos.common.config import build_process_bootstrap_config
from polisyos.core.canon import truncated_hash
from polisyos.core.observability import DeterminismTier, get_determinism_tier
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
    route_key: Mapping[str, Any] = field(default_factory=dict)

    @property
    def replay_semantics(self) -> str:
        return replay_semantics_for_tier(self.determinism_tier)

    @property
    def tolerance_budget(self) -> dict[str, Any]:
        return tolerance_budget_for_tier(self.determinism_tier)

    @property
    def observed_tolerance_budget(self) -> dict[str, Any]:
        helper = globals().get("observed_tolerance_budget_for_fingerprint")
        if callable(helper):
            return helper(self)
        return {
            "budget_source": "seed_prior",
            "mode": (
                "distributional"
                if self.determinism_tier is DeterminismTier.STATISTICAL
                else "allclose"
            ),
            "route_key": dict(self.route_key),
            "reference_fingerprint": self.compute_hash(),
            "expected_budget": self.tolerance_budget,
            "validation_status": "unknown",
            "downgraded_from": None,
            "downgraded_to": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend.value,
            "available": self.available,
            "determinism_tier": None
            if self.determinism_tier is None
            else self.determinism_tier.value,
            "execution_device": self.execution_device,
            "runtime_stack": list(self.runtime_stack),
            "library_versions": dict(self.library_versions),
            "runtime_backend": self.runtime_backend,
            "seed": self.seed,
            "notes": list(self.notes),
            "route_key": dict(self.route_key),
            "replay_semantics": self.replay_semantics,
            "tolerance_budget": self.tolerance_budget,
            "observed_tolerance_budget": self.observed_tolerance_budget,
            "fingerprint": self.compute_hash(),
        }

    def compute_hash(self) -> str:
        payload = {
            "backend": self.backend.value,
            "available": self.available,
            "determinism_tier": None
            if self.determinism_tier is None
            else self.determinism_tier.value,
            "execution_device": self.execution_device,
            "runtime_stack": list(self.runtime_stack),
            "library_versions": dict(sorted(self.library_versions.items())),
            "runtime_backend": self.runtime_backend,
            "seed": self.seed,
            "notes": list(self.notes),
            "route_key": dict(self.route_key),
        }
        return truncated_hash(json.dumps(payload, sort_keys=True), length=16)


def safe_version(package_name: str) -> str | None:
    """Return the installed distribution version without failing missing packages."""
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _normalized_architecture(machine: str | None) -> str:
    normalized = str(machine or "").strip().lower()
    if normalized in {"amd64", "x86-64", "x64"}:
        return "x86_64"
    if normalized in {"arm64", "arm64e"}:
        return "aarch64"
    return normalized or "unknown"


def _infer_arch_family(execution_device: str | None) -> str:
    normalized = str(execution_device or "").strip().lower()
    if normalized.startswith("cpu"):
        return _normalized_architecture(platform.machine())
    if any(token in normalized for token in ("metal", "mps", "apple")):
        return "metal_apple_gpu"
    if normalized.startswith("gpu"):
        return "cuda_gpu"
    if normalized.startswith("tpu"):
        return "tpu"
    return _normalized_architecture(platform.machine())


def _infer_device_family(execution_device: str | None) -> str:
    normalized = str(execution_device or "").strip()
    lowered = normalized.lower()
    if not lowered:
        return "unknown"
    if lowered.startswith("cpu"):
        return "cpu"
    if any(token in lowered for token in ("metal", "mps", "apple")):
        return "metal"
    if lowered.startswith("gpu"):
        _, _, family = normalized.partition(":")
        family = family.strip().lower().replace(" ", "_")
        return family or "cuda"
    return lowered.replace(" ", "_")


def _detect_blas_vendor(library_versions: Mapping[str, str]) -> str:
    keys = {str(key).lower() for key in library_versions}
    if any("mkl" in key for key in keys):
        return "mkl"
    if any("openblas" in key for key in keys):
        return "openblas"
    if any("accelerate" in key or "veclib" in key for key in keys):
        return "accelerate"
    try:
        import numpy as np

        config = getattr(np, "__config__", None)
        get_info = getattr(config, "get_info", None)
        info = dict(get_info("blas_opt_info")) if callable(get_info) else {}
        libraries = " ".join(str(item) for item in info.get("libraries", ())).lower()
        if "mkl" in libraries:
            return "mkl"
        if "openblas" in libraries:
            return "openblas"
        if "accelerate" in libraries or "veclib" in libraries:
            return "accelerate"
    except Exception:
        pass
    return "unknown"


def _detect_thread_policy() -> str:
    keys = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    )
    environ = __import__("os").environ
    values = [f"{key}={environ[key]}" for key in keys if environ.get(key)]
    return "|".join(values) if values else "default"


def _dtype_mode_for_backend(
    backend: ComputeBackend,
    *,
    execution_device: str | None,
) -> str:
    if backend is not ComputeBackend.JAX:
        return "float64_capable"

    normalized = str(execution_device or "").lower()
    if any(token in normalized for token in ("metal", "mps", "apple")):
        return "float32_only_experimental"

    try:
        import jax

        x64_enabled = getattr(jax.config, "x64_enabled", False)
        if callable(x64_enabled):
            x64_enabled = x64_enabled()
        return "x64_enabled" if bool(x64_enabled) else "float32_default"
    except Exception:
        return "unknown"


def _jax_matmul_precision() -> str | None:
    try:
        import jax

        value = getattr(jax.config, "jax_default_matmul_precision", None)
        if value is None:
            return None
        rendered = str(value).strip().lower()
        return rendered or None
    except Exception:
        return None


def _xla_flags_hash() -> str | None:
    flags = tuple(
        str(item) for item in build_process_bootstrap_config().xla_flags if str(item).strip()
    )
    if not flags:
        return None
    return truncated_hash(json.dumps(sorted(flags)), length=12)


def _autotune_key(
    backend: ComputeBackend,
    *,
    execution_device: str | None,
) -> str | None:
    if backend is not ComputeBackend.JAX:
        return None
    normalized = str(execution_device or "").lower()
    if normalized.startswith("gpu") or any(
        token in normalized for token in ("metal", "mps", "apple")
    ):
        return _xla_flags_hash() or "transient_autotune"
    return "not_applicable"


def _default_backend_route(
    backend: ComputeBackend,
    *,
    runtime_backend: str | None,
) -> str:
    if backend is ComputeBackend.BAYESIAN and runtime_backend:
        return f"bayesian:{runtime_backend}"
    return backend.value


def _default_solver_name(
    backend: ComputeBackend,
    *,
    runtime_backend: str | None,
    library_versions: Mapping[str, str],
) -> str | None:
    if backend is ComputeBackend.SOLVER:
        for candidate in _SOLVER_PACKAGES:
            if candidate in library_versions:
                return candidate
        return "solver"
    if backend is ComputeBackend.BAYESIAN and runtime_backend:
        return runtime_backend
    return None


def build_backend_route_key(
    backend: ComputeBackend,
    *,
    execution_device: str | None,
    runtime_backend: str | None,
    library_versions: Mapping[str, str],
    route_key_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    route_key = {
        "backend_route": _default_backend_route(backend, runtime_backend=runtime_backend),
        "arch_family": _infer_arch_family(execution_device),
        "device_family": _infer_device_family(execution_device),
        "dtype_mode": _dtype_mode_for_backend(backend, execution_device=execution_device),
        "blas_vendor": _detect_blas_vendor(library_versions),
        "thread_policy": _detect_thread_policy(),
        "solver_name": _default_solver_name(
            backend,
            runtime_backend=runtime_backend,
            library_versions=library_versions,
        ),
        "solver_options_hash": None,
        "jax_matmul_precision": _jax_matmul_precision() if backend is ComputeBackend.JAX else None,
        "xla_flags_hash": _xla_flags_hash() if backend is ComputeBackend.JAX else None,
        "autotune_key": _autotune_key(backend, execution_device=execution_device),
    }
    if route_key_overrides:
        route_key.update({str(key): value for key, value in route_key_overrides.items()})
    return route_key


def resolve_route_determinism_tier(
    tier: DeterminismTier | None,
    route_key: Mapping[str, Any],
) -> DeterminismTier | None:
    if tier is None:
        return None

    backend_route = str(route_key.get("backend_route") or "").lower()
    arch_family = str(route_key.get("arch_family") or "").lower()
    observed = tier

    if "ray" in backend_route and observed is DeterminismTier.STRICT_CPU:
        observed = DeterminismTier.LIBRARY_DETERMINISTIC
    if arch_family == "metal_apple_gpu" and observed in {
        DeterminismTier.STRICT_CPU,
        DeterminismTier.LIBRARY_DETERMINISTIC,
    }:
        observed = DeterminismTier.BEST_EFFORT_GPU
    return observed


def _route_failure_reasons(
    declared_tier: DeterminismTier | None,
    observed_tier: DeterminismTier | None,
    route_key: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    backend_route = str(route_key.get("backend_route") or "").lower()
    arch_family = str(route_key.get("arch_family") or "").lower()
    if "ray" in backend_route:
        reasons.append("ray_serialization_boundary")
    if "fallback" in backend_route:
        reasons.append("fallback_route")
    if arch_family == "metal_apple_gpu":
        reasons.append("experimental_metal_backend")
    if (
        declared_tier is not None
        and observed_tier is not None
        and declared_tier is not observed_tier
    ):
        reasons.append("route_overlay_downgrade")
    return reasons


def _budget_template(semantic_mode: str) -> dict[str, Any]:
    return {
        "same_fingerprint_abs_tol": None,
        "same_fingerprint_rel_tol": None,
        "same_fingerprint_ks_tol": None,
        "same_fingerprint_q50_abs_tol": None,
        "same_fingerprint_q90_width_abs_tol": None,
        "same_architecture_abs_tol": None,
        "same_architecture_rel_tol": None,
        "same_architecture_ks_tol": None,
        "same_architecture_q50_abs_tol": None,
        "same_architecture_q90_width_abs_tol": None,
        "cross_architecture_abs_tol": None,
        "cross_architecture_rel_tol": None,
        "cross_architecture_ks_tol": None,
        "cross_architecture_q50_abs_tol": None,
        "cross_architecture_q90_width_abs_tol": None,
        "semantic_mode": semantic_mode,
    }


def _scope_from_expected_budget(expected_budget: Mapping[str, Any]) -> str:
    same_fingerprint_keys = (
        "same_fingerprint_abs_tol",
        "same_fingerprint_rel_tol",
        "same_fingerprint_ks_tol",
        "same_fingerprint_q50_abs_tol",
        "same_fingerprint_q90_width_abs_tol",
    )
    same_architecture_keys = (
        "same_architecture_abs_tol",
        "same_architecture_rel_tol",
        "same_architecture_ks_tol",
        "same_architecture_q50_abs_tol",
        "same_architecture_q90_width_abs_tol",
    )
    if any(expected_budget.get(key) is not None for key in same_fingerprint_keys):
        return "same_fingerprint"
    if any(expected_budget.get(key) is not None for key in same_architecture_keys):
        return "same_architecture"
    return "cross_architecture"


def _bootstrap_envelope_budget(
    tier: DeterminismTier | None,
    route_key: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = tolerance_budget_for_tier(tier)
    expected = _budget_template(str(baseline.get("semantic_mode") or "best_effort"))
    expected.update(
        {
            "same_architecture_abs_tol": baseline.get("same_architecture_abs_tol"),
            "same_architecture_rel_tol": baseline.get("same_architecture_rel_tol"),
            "same_architecture_ks_tol": baseline.get("same_architecture_ks_tol"),
            "same_architecture_q50_abs_tol": baseline.get("same_architecture_q50_abs_tol"),
            "same_architecture_q90_width_abs_tol": baseline.get(
                "same_architecture_q90_width_abs_tol"
            ),
            "cross_architecture_abs_tol": baseline.get("cross_architecture_abs_tol"),
            "cross_architecture_rel_tol": baseline.get("cross_architecture_rel_tol"),
            "cross_architecture_ks_tol": baseline.get("cross_architecture_ks_tol"),
            "cross_architecture_q50_abs_tol": baseline.get("cross_architecture_q50_abs_tol"),
            "cross_architecture_q90_width_abs_tol": baseline.get(
                "cross_architecture_q90_width_abs_tol"
            ),
        }
    )

    arch_family = str(route_key.get("arch_family") or "").lower()
    backend_route = str(route_key.get("backend_route") or "").lower()

    if tier is DeterminismTier.STRICT_CPU:
        expected.update(
            {
                "same_fingerprint_abs_tol": 0.0,
                "same_fingerprint_rel_tol": 0.0,
                "same_architecture_abs_tol": 0.0,
                "same_architecture_rel_tol": 0.0,
                "cross_architecture_abs_tol": 1.0e-9,
                "cross_architecture_rel_tol": 1.0e-8,
            }
        )
    elif tier is DeterminismTier.LIBRARY_DETERMINISTIC:
        expected.update(
            {
                "same_fingerprint_abs_tol": 0.0,
                "same_fingerprint_rel_tol": 0.0,
                "same_architecture_abs_tol": 1.0e-12,
                "same_architecture_rel_tol": 1.0e-12,
                "cross_architecture_abs_tol": 1.0e-9,
                "cross_architecture_rel_tol": 1.0e-8,
            }
        )
    elif tier is DeterminismTier.BEST_EFFORT_GPU:
        if arch_family == "metal_apple_gpu":
            expected.update(
                {
                    "same_fingerprint_abs_tol": 1.0e-6,
                    "same_fingerprint_rel_tol": 1.0e-5,
                    "same_architecture_abs_tol": 1.0e-5,
                    "same_architecture_rel_tol": 1.0e-4,
                    "cross_architecture_abs_tol": 1.0e-3,
                    "cross_architecture_rel_tol": 1.0e-2,
                    "semantic_mode": "near_deterministic_metal",
                }
            )
        else:
            expected.update(
                {
                    "same_fingerprint_abs_tol": 1.0e-7,
                    "same_fingerprint_rel_tol": 1.0e-6,
                    "same_architecture_abs_tol": 1.0e-6,
                    "same_architecture_rel_tol": 1.0e-5,
                    "cross_architecture_abs_tol": 1.0e-4,
                    "cross_architecture_rel_tol": 1.0e-3,
                }
            )
    elif tier is DeterminismTier.STATISTICAL:
        expected.update(
            {
                "same_fingerprint_ks_tol": 0.05,
                "same_fingerprint_q50_abs_tol": 0.02,
                "same_fingerprint_q90_width_abs_tol": 0.05,
                "same_architecture_ks_tol": baseline.get("same_architecture_ks_tol") or 0.08,
                "same_architecture_q50_abs_tol": baseline.get("same_architecture_q50_abs_tol")
                or 0.05,
                "same_architecture_q90_width_abs_tol": baseline.get(
                    "same_architecture_q90_width_abs_tol"
                )
                or 0.08,
                "cross_architecture_ks_tol": baseline.get("cross_architecture_ks_tol") or 0.12,
                "cross_architecture_q50_abs_tol": baseline.get("cross_architecture_q50_abs_tol")
                or 0.10,
                "cross_architecture_q90_width_abs_tol": baseline.get(
                    "cross_architecture_q90_width_abs_tol"
                )
                or 0.12,
                "semantic_mode": "distributional_replay",
            }
        )

    if "ray" in backend_route:
        for key in (
            "same_fingerprint_abs_tol",
            "same_fingerprint_rel_tol",
            "same_fingerprint_ks_tol",
            "same_fingerprint_q50_abs_tol",
            "same_fingerprint_q90_width_abs_tol",
            "same_architecture_abs_tol",
            "same_architecture_rel_tol",
            "same_architecture_ks_tol",
            "same_architecture_q50_abs_tol",
            "same_architecture_q90_width_abs_tol",
            "cross_architecture_abs_tol",
            "cross_architecture_rel_tol",
            "cross_architecture_ks_tol",
            "cross_architecture_q50_abs_tol",
            "cross_architecture_q90_width_abs_tol",
        ):
            value = expected.get(key)
            if value is not None:
                expected[key] = float(value) * 10.0
        expected["semantic_mode"] = f"{expected['semantic_mode']}_ray"

    if "fallback" in backend_route or "->" in backend_route:
        expected["semantic_mode"] = f"{expected['semantic_mode']}_fallback"

    return expected


def observed_tolerance_budget_for_fingerprint(
    posture: BackendRuntimeFingerprint,
) -> dict[str, Any]:
    route_key = dict(posture.route_key)
    observed_tier = resolve_route_determinism_tier(posture.determinism_tier, route_key)
    expected_budget = _bootstrap_envelope_budget(observed_tier, route_key)
    reasons = _route_failure_reasons(posture.determinism_tier, observed_tier, route_key)
    validation_status = "unknown"
    if posture.available:
        validation_status = "degraded" if reasons else "compatible"

    return {
        "budget_source": "seed_prior",
        "mode": ("distributional" if observed_tier is DeterminismTier.STATISTICAL else "allclose"),
        "scope": _scope_from_expected_budget(expected_budget),
        "route_key": route_key,
        "reference_fingerprint": posture.compute_hash(),
        "canary_suite_id": None,
        "sample_count": 0,
        "abs_tol_p50": None,
        "abs_tol_p95": None,
        "abs_tol_p99": None,
        "rel_tol_p50": None,
        "rel_tol_p95": None,
        "rel_tol_p99": None,
        "ulp_tol_p99": None,
        "distributional_metrics": {
            "ks_statistic": None,
            "q50_abs_error": None,
            "q90_width_abs_error": None,
        },
        "solver_residual_budget": {
            "primal": None,
            "dual": None,
            "gap": None,
            "optimality": None,
        },
        "expected_budget": expected_budget,
        "validation_status": validation_status,
        "downgraded_from": (
            None
            if posture.determinism_tier is None or posture.determinism_tier is observed_tier
            else posture.determinism_tier.value
        ),
        "downgraded_to": (
            None
            if observed_tier is None or posture.determinism_tier is observed_tier
            else observed_tier.value
        ),
        "failure_reasons": reasons,
    }


def augment_observed_tolerance_budget(
    budget: Mapping[str, Any] | None,
    *,
    route_key_updates: Mapping[str, Any] | None = None,
    solver_residual_budget: Mapping[str, Any] | None = None,
    budget_source: str | None = None,
    validation_status: str | None = None,
    downgraded_from: str | None = None,
    downgraded_to: str | None = None,
    failure_reasons: tuple[str, ...] = (),
    expected_budget_updates: Mapping[str, Any] | None = None,
    distributional_metrics_updates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(budget or {})
    route_key = dict(merged.get("route_key") or {})
    if route_key_updates:
        route_key.update({str(key): value for key, value in route_key_updates.items()})
    merged["route_key"] = route_key

    expected_budget = dict(merged.get("expected_budget") or {})
    if expected_budget_updates:
        expected_budget.update({str(key): value for key, value in expected_budget_updates.items()})
    merged["expected_budget"] = expected_budget

    solver_budget = dict(merged.get("solver_residual_budget") or {})
    if solver_residual_budget:
        solver_budget.update({str(key): value for key, value in solver_residual_budget.items()})
    merged["solver_residual_budget"] = solver_budget

    distributional_metrics = dict(merged.get("distributional_metrics") or {})
    if distributional_metrics_updates:
        distributional_metrics.update(
            {str(key): value for key, value in distributional_metrics_updates.items()}
        )
    merged["distributional_metrics"] = distributional_metrics

    if validation_status is not None:
        merged["validation_status"] = validation_status
    if budget_source is not None:
        merged["budget_source"] = budget_source
    if downgraded_from is not None:
        merged["downgraded_from"] = downgraded_from
    if downgraded_to is not None:
        merged["downgraded_to"] = downgraded_to

    existing_reasons = [str(item) for item in merged.get("failure_reasons") or []]
    merged["failure_reasons"] = list(dict.fromkeys([*existing_reasons, *failure_reasons]))
    return merged


_DETERMINISM_TIER_ORDER = {
    DeterminismTier.STRICT_CPU: 0,
    DeterminismTier.LIBRARY_DETERMINISTIC: 1,
    DeterminismTier.BEST_EFFORT_GPU: 2,
    DeterminismTier.STATISTICAL: 3,
    DeterminismTier.NONDETERMINISTIC: 4,
}

_OBSERVED_BUDGET_SOURCE_ORDER = {
    "runtime_measured": 0,
    "ci_measured": 1,
    "seed_prior": 2,
    "none": 3,
}


def meet_determinism_tiers(
    tiers: tuple[DeterminismTier | None, ...] | list[DeterminismTier | None],
) -> DeterminismTier | None:
    resolved = [tier for tier in tiers if tier is not None]
    if not resolved:
        return None
    return max(
        resolved,
        key=lambda tier: _DETERMINISM_TIER_ORDER.get(tier, len(_DETERMINISM_TIER_ORDER)),
    )


def compose_route_keys(
    route_keys: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    *,
    composition_kind: str = "serial",
) -> dict[str, Any]:
    if not route_keys:
        return {
            "backend_route": "unknown",
            "arch_family": "unknown",
            "device_family": "unknown",
            "dtype_mode": "unknown",
            "blas_vendor": "unknown",
            "thread_policy": "default",
            "solver_name": None,
            "solver_options_hash": None,
            "jax_matmul_precision": None,
            "xla_flags_hash": None,
            "autotune_key": None,
            "composition_kind": composition_kind,
            "stage_count": 0,
        }

    separator = {
        "serial": "->",
        "concat": "||",
        "parallel": "||",
        "reduce": "=>",
    }.get(composition_kind, "->")

    def _collapse(key: str) -> Any:
        values = [
            value
            for value in (route_key.get(key) for route_key in route_keys)
            if value not in (None, "", ())
        ]
        if not values:
            return None
        if key == "backend_route":
            return separator.join(str(value) for value in values)
        unique = list(dict.fromkeys(str(value) for value in values))
        return unique[0] if len(unique) == 1 else "mixed"

    return {
        "backend_route": _collapse("backend_route") or "unknown",
        "arch_family": _collapse("arch_family") or "unknown",
        "device_family": _collapse("device_family") or "unknown",
        "dtype_mode": _collapse("dtype_mode") or "unknown",
        "blas_vendor": _collapse("blas_vendor") or "unknown",
        "thread_policy": _collapse("thread_policy") or "default",
        "solver_name": _collapse("solver_name"),
        "solver_options_hash": _collapse("solver_options_hash"),
        "jax_matmul_precision": _collapse("jax_matmul_precision"),
        "xla_flags_hash": _collapse("xla_flags_hash"),
        "autotune_key": _collapse("autotune_key"),
        "composition_kind": composition_kind,
        "stage_count": len(route_keys),
    }


def _compose_abs_values(values: list[float | None], *, composition_kind: str) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    if composition_kind in {"concat", "parallel"}:
        return max(numeric)
    return sum(numeric)


def _compose_rel_values(values: list[float | None], *, composition_kind: str) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    if composition_kind in {"concat", "parallel"}:
        return max(numeric)
    total = 0.0
    for value in numeric:
        total = total + value + (total * value)
    return total


def _compose_budget_maps(
    expected_budgets: list[Mapping[str, Any]],
    *,
    composition_kind: str,
) -> dict[str, Any]:
    keys = sorted({str(key) for budget in expected_budgets for key in budget})
    composed: dict[str, Any] = {}
    for key in keys:
        values = [budget.get(key) for budget in expected_budgets]
        if key.endswith("rel_tol"):
            composed[key] = _compose_rel_values(values, composition_kind=composition_kind)
            continue
        if key.endswith("abs_tol") or key.endswith("ulp_tol") or key.endswith("ks_tol"):
            composed[key] = _compose_abs_values(values, composition_kind=composition_kind)
            continue
        if key == "semantic_mode":
            rendered = [str(value) for value in values if value]
            if not rendered:
                composed[key] = "best_effort"
            elif composition_kind in {"concat", "parallel"}:
                composed[key] = max(rendered)
            else:
                composed[key] = rendered[-1]
            continue
        first = next((value for value in values if value is not None), None)
        composed[key] = first
    return composed


def _compose_validation_status(statuses: list[str]) -> str:
    normalized = [str(status).strip().lower() for status in statuses if str(status).strip()]
    if not normalized:
        return "unknown"
    if any(status == "degraded" for status in normalized):
        return "degraded"
    if normalized and all(status == "validated" for status in normalized):
        return "validated"
    if any(status in {"validated", "compatible"} for status in normalized):
        return "compatible"
    return "unknown"


def _compose_budget_source(sources: list[str]) -> str:
    normalized = [str(source).strip().lower() for source in sources if str(source).strip()]
    if not normalized:
        return "none"
    return min(
        normalized,
        key=lambda source: _OBSERVED_BUDGET_SOURCE_ORDER.get(
            source,
            len(_OBSERVED_BUDGET_SOURCE_ORDER),
        ),
    )


def _compose_solver_residual_budget(budgets: list[Mapping[str, Any]]) -> dict[str, Any]:
    keys = ("primal", "dual", "gap", "optimality")
    composed: dict[str, Any] = {}
    for key in keys:
        values = [
            budget.get("solver_residual_budget", {}).get(key)
            for budget in budgets
            if isinstance(budget.get("solver_residual_budget"), Mapping)
        ]
        numeric = [float(value) for value in values if value is not None]
        composed[key] = max(numeric) if numeric else None
    return composed


def _compose_distributional_metrics(
    budgets: list[Mapping[str, Any]],
    *,
    composition_kind: str,
) -> dict[str, Any]:
    keys = ("ks_statistic", "q50_abs_error", "q90_width_abs_error")
    composed: dict[str, Any] = {}
    for key in keys:
        values = [
            budget.get("distributional_metrics", {}).get(key)
            for budget in budgets
            if isinstance(budget.get("distributional_metrics"), Mapping)
        ]
        composed[key] = _compose_abs_values(values, composition_kind=composition_kind)
    return composed


def compose_observed_tolerance_budgets(
    budgets: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    *,
    determinism_tiers: tuple[DeterminismTier | None, ...]
    | list[DeterminismTier | None]
    | None = None,
    composition_kind: str = "serial",
) -> dict[str, Any]:
    normalized = [dict(budget) for budget in budgets if budget]
    if not normalized:
        return {
            "budget_source": "none",
            "mode": "allclose",
            "scope": "cross_architecture",
            "route_key": compose_route_keys((), composition_kind=composition_kind),
            "reference_fingerprint": None,
            "canary_suite_id": None,
            "sample_count": 0,
            "abs_tol_p50": None,
            "abs_tol_p95": None,
            "abs_tol_p99": None,
            "rel_tol_p50": None,
            "rel_tol_p95": None,
            "rel_tol_p99": None,
            "ulp_tol_p99": None,
            "distributional_metrics": {
                "ks_statistic": None,
                "q50_abs_error": None,
                "q90_width_abs_error": None,
            },
            "solver_residual_budget": {
                "primal": None,
                "dual": None,
                "gap": None,
                "optimality": None,
            },
            "expected_budget": _budget_template("best_effort"),
            "validation_status": "unknown",
            "downgraded_from": None,
            "downgraded_to": None,
            "failure_reasons": [],
        }

    expected_budget = _compose_budget_maps(
        [dict(budget.get("expected_budget") or {}) for budget in normalized],
        composition_kind=composition_kind,
    )
    route_keys = [dict(budget.get("route_key") or {}) for budget in normalized]
    composed_route_key = compose_route_keys(route_keys, composition_kind=composition_kind)
    base_tier = meet_determinism_tiers(list(determinism_tiers or ()))
    observed_tier = resolve_route_determinism_tier(base_tier, composed_route_key)
    failure_reasons = [
        str(item) for budget in normalized for item in (budget.get("failure_reasons") or [])
    ]
    if (
        composed_route_key.get("arch_family") == "mixed"
        and observed_tier is DeterminismTier.STRICT_CPU
    ):
        observed_tier = DeterminismTier.LIBRARY_DETERMINISTIC
        failure_reasons.append("mixed_architecture_pipeline")
    if (
        composed_route_key.get("device_family") == "mixed"
        and observed_tier is DeterminismTier.STRICT_CPU
    ):
        observed_tier = DeterminismTier.LIBRARY_DETERMINISTIC
        failure_reasons.append("mixed_device_pipeline")
    if (
        composed_route_key.get("dtype_mode") == "mixed"
        and observed_tier is DeterminismTier.STRICT_CPU
    ):
        observed_tier = DeterminismTier.LIBRARY_DETERMINISTIC
        failure_reasons.append("mixed_dtype_pipeline")
    if observed_tier is DeterminismTier.STATISTICAL:
        expected_budget["semantic_mode"] = "distributional_replay"

    scope = _scope_from_expected_budget(expected_budget)

    validation_status = _compose_validation_status(
        [str(budget.get("validation_status") or "") for budget in normalized]
    )
    if failure_reasons and validation_status == "validated":
        validation_status = "compatible"
    if (
        base_tier is not None
        and observed_tier is not None
        and base_tier is not observed_tier
        and validation_status != "unknown"
    ):
        validation_status = "degraded"

    reference_fingerprint_values = [
        str(value)
        for value in (budget.get("reference_fingerprint") for budget in normalized)
        if value
    ]
    canary_values = [
        str(value) for value in (budget.get("canary_suite_id") for budget in normalized) if value
    ]
    unique_canaries = list(dict.fromkeys(canary_values))

    return {
        "budget_source": _compose_budget_source(
            [str(budget.get("budget_source") or "") for budget in normalized]
        ),
        "mode": (
            "distributional"
            if any(str(budget.get("mode") or "") == "distributional" for budget in normalized)
            else "allclose"
        ),
        "scope": scope,
        "route_key": composed_route_key,
        "reference_fingerprint": (
            truncated_hash("|".join(reference_fingerprint_values), length=16)
            if reference_fingerprint_values
            else None
        ),
        "canary_suite_id": unique_canaries[0] if len(unique_canaries) == 1 else None,
        "sample_count": sum(int(budget.get("sample_count") or 0) for budget in normalized),
        "abs_tol_p50": _compose_abs_values(
            [budget.get("abs_tol_p50") for budget in normalized],
            composition_kind=composition_kind,
        ),
        "abs_tol_p95": _compose_abs_values(
            [budget.get("abs_tol_p95") for budget in normalized],
            composition_kind=composition_kind,
        ),
        "abs_tol_p99": _compose_abs_values(
            [budget.get("abs_tol_p99") for budget in normalized],
            composition_kind=composition_kind,
        ),
        "rel_tol_p50": _compose_rel_values(
            [budget.get("rel_tol_p50") for budget in normalized],
            composition_kind=composition_kind,
        ),
        "rel_tol_p95": _compose_rel_values(
            [budget.get("rel_tol_p95") for budget in normalized],
            composition_kind=composition_kind,
        ),
        "rel_tol_p99": _compose_rel_values(
            [budget.get("rel_tol_p99") for budget in normalized],
            composition_kind=composition_kind,
        ),
        "ulp_tol_p99": _compose_abs_values(
            [budget.get("ulp_tol_p99") for budget in normalized],
            composition_kind=composition_kind,
        ),
        "distributional_metrics": _compose_distributional_metrics(
            normalized,
            composition_kind=composition_kind,
        ),
        "solver_residual_budget": _compose_solver_residual_budget(normalized),
        "expected_budget": expected_budget,
        "validation_status": validation_status,
        "downgraded_from": (
            None
            if base_tier is None or observed_tier is None or base_tier is observed_tier
            else base_tier.value
        ),
        "downgraded_to": (
            None
            if base_tier is None or observed_tier is None or base_tier is observed_tier
            else observed_tier.value
        ),
        "failure_reasons": list(dict.fromkeys(failure_reasons)),
    }


def validate_observed_tolerance_budget(
    *,
    reference: Any,
    candidate: Any,
    budget: Mapping[str, Any],
    current_tier: DeterminismTier | None,
) -> dict[str, Any]:
    if str(budget.get("mode") or "allclose") == "distributional":
        metrics = _distributional_drift_metrics(reference=reference, candidate=candidate)
    else:
        metrics = _numeric_drift_metrics(reference=reference, candidate=candidate)
    return validate_observed_tolerance_budget_metrics(
        metrics=metrics,
        budget=budget,
        current_tier=current_tier,
    )


def validate_observed_tolerance_budget_metrics(
    *,
    metrics: Mapping[str, float],
    budget: Mapping[str, Any],
    current_tier: DeterminismTier | None,
) -> dict[str, Any]:
    expected_budget = dict(budget.get("expected_budget") or {})
    route_key = dict(budget.get("route_key") or {})
    if str(budget.get("mode") or "allclose") == "distributional":
        exact_fit = _fits_distributional_budget(metrics, expected_budget, prefix="same_fingerprint")
        same_arch_fit = _fits_distributional_budget(
            metrics,
            expected_budget,
            prefix="same_architecture",
        )
        cross_arch_fit = _fits_distributional_budget(
            metrics,
            expected_budget,
            prefix="cross_architecture",
        )
        updated = augment_observed_tolerance_budget(
            budget,
            budget_source="runtime_measured",
            validation_status=(
                "validated"
                if exact_fit
                else "compatible"
                if same_arch_fit or cross_arch_fit
                else "unknown"
            ),
            distributional_metrics_updates={
                "ks_statistic": float(metrics.get("ks_statistic", 0.0)),
                "q50_abs_error": float(metrics.get("q50_abs_error", 0.0)),
                "q90_width_abs_error": float(metrics.get("q90_width_abs_error", 0.0)),
            },
        )
        updated["sample_count"] = int(updated.get("sample_count") or 0) + 1
        updated["scope"] = (
            "same_fingerprint"
            if exact_fit
            else "same_architecture"
            if same_arch_fit
            else "cross_architecture"
            if cross_arch_fit
            else str(updated.get("scope") or _scope_from_expected_budget(expected_budget))
        )
        if exact_fit or same_arch_fit or cross_arch_fit:
            return updated
        if current_tier is not None:
            current_order = _DETERMINISM_TIER_ORDER.get(
                current_tier,
                len(_DETERMINISM_TIER_ORDER),
            )
            weaker_tiers = [
                tier for tier, order in _DETERMINISM_TIER_ORDER.items() if order > current_order
            ]
            for weaker_tier in weaker_tiers:
                weaker_budget = _bootstrap_envelope_budget(weaker_tier, route_key)
                if (
                    _fits_distributional_budget(metrics, weaker_budget, prefix="same_fingerprint")
                    or _fits_distributional_budget(
                        metrics, weaker_budget, prefix="same_architecture"
                    )
                    or _fits_distributional_budget(
                        metrics, weaker_budget, prefix="cross_architecture"
                    )
                ):
                    return augment_observed_tolerance_budget(
                        updated,
                        budget_source="runtime_measured",
                        validation_status="degraded",
                        downgraded_from=current_tier.value,
                        downgraded_to=weaker_tier.value,
                        failure_reasons=("runtime_drift_exceeded_expected_budget",),
                        expected_budget_updates=weaker_budget,
                    )
        return augment_observed_tolerance_budget(
            updated,
            budget_source="runtime_measured",
            validation_status="unknown",
            failure_reasons=("runtime_drift_exceeded_expected_budget",),
        )

    exact_fit = _fits_budget(metrics, expected_budget, prefix="same_fingerprint")
    same_arch_fit = _fits_budget(metrics, expected_budget, prefix="same_architecture")
    cross_arch_fit = _fits_budget(metrics, expected_budget, prefix="cross_architecture")

    updated = augment_observed_tolerance_budget(
        budget,
        budget_source="runtime_measured",
        validation_status=(
            "validated"
            if exact_fit
            else "compatible"
            if same_arch_fit or cross_arch_fit
            else "unknown"
        ),
        expected_budget_updates={},
    )
    updated["sample_count"] = int(updated.get("sample_count") or 0) + 1
    updated["abs_tol_p99"] = metrics["max_abs_error"]
    updated["rel_tol_p99"] = metrics["max_rel_error"]
    updated["scope"] = (
        "same_fingerprint"
        if exact_fit
        else "same_architecture"
        if same_arch_fit
        else "cross_architecture"
        if cross_arch_fit
        else str(updated.get("scope") or "cross_architecture")
    )

    if exact_fit or same_arch_fit or cross_arch_fit:
        return updated

    if current_tier is not None:
        current_order = _DETERMINISM_TIER_ORDER.get(current_tier, len(_DETERMINISM_TIER_ORDER))
        weaker_tiers = [
            tier for tier, order in _DETERMINISM_TIER_ORDER.items() if order > current_order
        ]
        for weaker_tier in weaker_tiers:
            weaker_budget = _bootstrap_envelope_budget(weaker_tier, route_key)
            if (
                _fits_budget(metrics, weaker_budget, prefix="same_fingerprint")
                or _fits_budget(metrics, weaker_budget, prefix="same_architecture")
                or _fits_budget(metrics, weaker_budget, prefix="cross_architecture")
            ):
                return augment_observed_tolerance_budget(
                    updated,
                    budget_source="runtime_measured",
                    validation_status="degraded",
                    downgraded_from=current_tier.value,
                    downgraded_to=weaker_tier.value,
                    failure_reasons=("runtime_drift_exceeded_expected_budget",),
                    expected_budget_updates=weaker_budget,
                )

    return augment_observed_tolerance_budget(
        updated,
        budget_source="runtime_measured",
        validation_status="unknown",
        failure_reasons=("runtime_drift_exceeded_expected_budget",),
    )


def _fits_budget(
    metrics: Mapping[str, float],
    expected_budget: Mapping[str, Any],
    *,
    prefix: str,
) -> bool:
    atol = expected_budget.get(f"{prefix}_abs_tol")
    rtol = expected_budget.get(f"{prefix}_rel_tol")
    if atol is None or rtol is None:
        return False
    return float(metrics.get("max_abs_error", 0.0)) <= float(atol) and float(
        metrics.get("max_rel_error", 0.0)
    ) <= float(rtol)


def _fits_distributional_budget(
    metrics: Mapping[str, float],
    expected_budget: Mapping[str, Any],
    *,
    prefix: str,
) -> bool:
    ks_tol = expected_budget.get(f"{prefix}_ks_tol")
    q50_tol = expected_budget.get(f"{prefix}_q50_abs_tol")
    q90_tol = expected_budget.get(f"{prefix}_q90_width_abs_tol")
    if ks_tol is None or q50_tol is None or q90_tol is None:
        return False
    return (
        float(metrics.get("ks_statistic", 0.0)) <= float(ks_tol)
        and float(metrics.get("q50_abs_error", 0.0)) <= float(q50_tol)
        and float(metrics.get("q90_width_abs_error", 0.0)) <= float(q90_tol)
    )


def _numeric_drift_metrics(*, reference: Any, candidate: Any) -> dict[str, float]:
    import numpy as np

    ref = np.asarray(reference, dtype=np.float64)
    cand = np.asarray(candidate, dtype=np.float64)
    if ref.shape != cand.shape:
        raise ValueError(
            f"Cannot validate tolerance budget for mismatched shapes: {ref.shape!r} vs {cand.shape!r}"
        )
    abs_error = np.abs(ref - cand)
    scale = np.maximum(np.maximum(np.abs(ref), np.abs(cand)), 1.0e-12)
    rel_error = np.divide(
        abs_error,
        scale,
        out=np.zeros_like(abs_error),
        where=scale > 0,
    )
    return {
        "max_abs_error": float(np.max(abs_error)) if abs_error.size else 0.0,
        "max_rel_error": float(np.max(rel_error)) if rel_error.size else 0.0,
    }


def _distributional_drift_metrics(*, reference: Any, candidate: Any) -> dict[str, float]:
    import numpy as np

    ref = np.asarray(reference, dtype=np.float64)
    cand = np.asarray(candidate, dtype=np.float64)
    if ref.shape != cand.shape:
        raise ValueError(
            f"Cannot validate tolerance budget for mismatched shapes: {ref.shape!r} vs {cand.shape!r}"
        )

    if ref.ndim == 0:
        ref = ref.reshape(1, 1)
        cand = cand.reshape(1, 1)
    else:
        ref = ref.reshape(ref.shape[0], -1)
        cand = cand.reshape(cand.shape[0], -1)

    ks_stats: list[float] = []
    q50_errors: list[float] = []
    q90_width_errors: list[float] = []
    for column in range(ref.shape[1]):
        ref_column = ref[:, column]
        cand_column = cand[:, column]
        ks_stats.append(_two_sample_ks_statistic(ref_column, cand_column))
        q50_errors.append(abs(float(np.median(ref_column)) - float(np.median(cand_column))))
        ref_q05, ref_q95 = np.quantile(ref_column, [0.05, 0.95])
        cand_q05, cand_q95 = np.quantile(cand_column, [0.05, 0.95])
        q90_width_errors.append(abs(float(ref_q95 - ref_q05) - float(cand_q95 - cand_q05)))

    return {
        "ks_statistic": max(ks_stats) if ks_stats else 0.0,
        "q50_abs_error": max(q50_errors) if q50_errors else 0.0,
        "q90_width_abs_error": max(q90_width_errors) if q90_width_errors else 0.0,
    }


def _two_sample_ks_statistic(reference: Any, candidate: Any) -> float:
    import numpy as np

    ref = np.sort(np.asarray(reference, dtype=np.float64))
    cand = np.sort(np.asarray(candidate, dtype=np.float64))
    if ref.size == 0 or cand.size == 0:
        return 0.0
    support = np.concatenate([ref, cand])
    ref_cdf = np.searchsorted(ref, support, side="right") / ref.size
    cand_cdf = np.searchsorted(cand, support, side="right") / cand.size
    return float(np.max(np.abs(ref_cdf - cand_cdf)))


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
            "same_architecture_ks_tol": 0.08,
            "same_architecture_q50_abs_tol": 0.05,
            "same_architecture_q90_width_abs_tol": 0.08,
            "cross_architecture_abs_tol": None,
            "cross_architecture_rel_tol": None,
            "cross_architecture_ks_tol": 0.12,
            "cross_architecture_q50_abs_tol": 0.10,
            "cross_architecture_q90_width_abs_tol": 0.12,
            "semantic_mode": "distributional_replay",
        }
    return {
        "same_architecture_abs_tol": None,
        "same_architecture_rel_tol": None,
        "same_architecture_ks_tol": None,
        "same_architecture_q50_abs_tol": None,
        "same_architecture_q90_width_abs_tol": None,
        "cross_architecture_abs_tol": None,
        "cross_architecture_rel_tol": None,
        "cross_architecture_ks_tol": None,
        "cross_architecture_q50_abs_tol": None,
        "cross_architecture_q90_width_abs_tol": None,
        "semantic_mode": "best_effort",
    }


def replay_semantics_for_tier(tier: DeterminismTier | None) -> str:
    """Human-readable replay contract for one determinism tier."""
    if tier is DeterminismTier.STRICT_CPU:
        return (
            "Replay must be bit-exact on the same CPU ISA; x86_64 vs arm64 uses tolerance budget."
        )
    if tier is DeterminismTier.LIBRARY_DETERMINISTIC:
        return "Replay must match exactly within the same CPU/library stack; cross-ISA uses tolerance budget."
    if tier is DeterminismTier.BEST_EFFORT_GPU:
        return "Replay should match within near-deterministic GPU tolerances on the same device family."
    if tier is DeterminismTier.STATISTICAL:
        return "Replay is seed-stable only up to statistical envelopes, not bitwise equality."
    return "Replay is best-effort only; exact equality is not guaranteed."


def runtime_stack_for(method_class: type) -> tuple[str, ...]:
    """Normalize a method class runtime stack declaration into stable labels."""
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
    """Collect installed versions for backend base packages and runtime stack labels."""
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
        if any(token in normalized for token in ("metal", "mps", "apple")):
            return DeterminismTier.BEST_EFFORT_GPU
        deterministic_ops = (
            "--xla_gpu_deterministic_ops=true" in build_process_bootstrap_config().xla_flags
        )
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
    determinism_tier: DeterminismTier | None = None,
    runtime_backend: str | None = None,
    available: bool | None = None,
    extra_versions: Mapping[str, str] | None = None,
    notes: tuple[str, ...] = (),
    route_key_overrides: Mapping[str, Any] | None = None,
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

            versions.update(
                capture_versions(base_packages=_JAX_PACKAGES, runtime_stack=runtime_stack)
            )
            devices = jax.devices()
            if devices:
                first_device = devices[0]
                device = f"{first_device.platform}:{first_device.device_kind}"
            else:
                device = f"{jax.default_backend()}:unknown"
        else:
            versions.update(
                capture_versions(base_packages=_JAX_PACKAGES, runtime_stack=runtime_stack)
            )
        is_available = runtime_available if available is None else available
    elif backend is ComputeBackend.SOLVER:
        versions.update(
            capture_versions(base_packages=_SOLVER_PACKAGES, runtime_stack=runtime_stack)
        )
        device = "cpu:solver"
        runtime_available = any(package in versions for package in _SOLVER_PACKAGES)
        is_available = runtime_available if available is None else available
    elif backend is ComputeBackend.BAYESIAN:
        base_packages = tuple(
            dict.fromkeys(
                _BAYESIAN_PACKAGES + (() if runtime_backend is None else (runtime_backend,))
            )
        )
        versions.update(capture_versions(base_packages=base_packages, runtime_stack=runtime_stack))
        device = "cpu:bayesian"
        runtime_available = bool(versions)
        is_available = runtime_available if available is None else available
    else:
        versions.update(
            capture_versions(base_packages=_NUMPY_PACKAGES, runtime_stack=runtime_stack)
        )
        device = "cpu:numpy"
        runtime_available = safe_version("numpy") is not None
        is_available = runtime_available if available is None else available

    if extra_versions:
        versions.update({str(key): str(value) for key, value in extra_versions.items() if value})

    tier = (
        (
            determinism_tier
            if determinism_tier is not None
            else default_determinism_tier_for_backend(backend, device=device)
        )
        if is_available
        else None
    )
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
        route_key=build_backend_route_key(
            backend,
            execution_device=device,
            runtime_backend=runtime_backend,
            library_versions=dict(sorted(versions.items())),
            route_key_overrides=route_key_overrides,
        ),
    )


__all__ = [
    "BackendRuntimeFingerprint",
    "augment_observed_tolerance_budget",
    "build_backend_route_key",
    "capture_backend_runtime_fingerprint",
    "capture_versions",
    "compose_observed_tolerance_budgets",
    "compose_route_keys",
    "default_determinism_tier_for_backend",
    "meet_determinism_tiers",
    "observed_tolerance_budget_for_fingerprint",
    "replay_semantics_for_tier",
    "resolve_route_determinism_tier",
    "runtime_stack_for",
    "safe_version",
    "tolerance_budget_for_tier",
    "validate_observed_tolerance_budget",
    "validate_observed_tolerance_budget_metrics",
]
