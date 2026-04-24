"""Canonicalize MethodResult payloads into stable field-path trees."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from polisyos.foundry.methods.backends.protocol import MethodResult


def canonicalize_method_result(result: MethodResult) -> dict[str, Any]:
    """Flatten a MethodResult into `{field_path: leaf_value}` form."""

    tree = {
        "output": result.output,
        "slot_outputs": dict(result.slot_outputs),
        "artifacts": dict(result.artifacts),
        "reproducibility": {
            "backend": result.reproducibility.backend.value,
            "determinism_tier": result.reproducibility.determinism_tier.value,
            "seed": result.reproducibility.seed,
            "library_versions": dict(result.reproducibility.library_versions),
            "solver_status": (
                None
                if result.reproducibility.solver_status is None
                else result.reproducibility.solver_status.value
            ),
            "solver_gap": result.reproducibility.solver_gap,
            "solver_iterations": result.reproducibility.solver_iterations,
            "fingerprint": result.reproducibility.fingerprint,
            "observed_tolerance_budget": dict(result.reproducibility.observed_tolerance_budget),
            "note": result.reproducibility.note,
        },
        "timing": {
            "wall_time_ms": result.timing.wall_time_ms,
            "cpu_time_ms": result.timing.cpu_time_ms,
            "compile_time_ms": result.timing.compile_time_ms,
        },
        "warnings": tuple(result.warnings),
        "cross_backend_equivalence_ref": result.cross_backend_equivalence_ref,
    }
    flattened: dict[str, Any] = {}
    for key, value in tree.items():
        _flatten_into(key, value, flattened)
    return flattened


def _flatten_into(prefix: str, value: Any, out: dict[str, Any]) -> None:
    branch = _as_branch(value)
    if branch is None:
        out[prefix] = value
        return
    if not branch:
        out[prefix] = {}
        return
    for key, item in branch.items():
        child = f"{prefix}.{key}" if prefix else str(key)
        _flatten_into(child, item, out)


def _as_branch(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in dataclasses.fields(value)}
    if hasattr(value, "model_dump") and callable(value.model_dump):
        dumped = value.model_dump(mode="python", exclude_none=False)
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    if hasattr(value, "_asdict") and callable(value._asdict):
        dumped = value._asdict()
        if isinstance(dumped, Mapping):
            return {str(key): item for key, item in dumped.items()}
    return None


__all__ = ["canonicalize_method_result"]
