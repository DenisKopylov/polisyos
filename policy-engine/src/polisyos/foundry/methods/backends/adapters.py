"""Public backends adapters module API."""

from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.exceptions import BackendAdaptationError

try:
    import jax
except ModuleNotFoundError:  # pragma: no cover - exercised in environments without JAX
    jax = None

_HOST_BACKENDS = {
    ComputeBackend.NUMPY,
    ComputeBackend.SOLVER,
    ComputeBackend.BAYESIAN,
}


def _tree_leaves(tree: Any) -> list[Any]:
    if jax is None:
        leaves: list[Any] = []
        if isinstance(tree, dict):
            for value in tree.values():
                leaves.extend(_tree_leaves(value))
            return leaves
        if isinstance(tree, (list, tuple)):
            for value in tree:
                leaves.extend(_tree_leaves(value))
            return leaves
        leaves.append(tree)
        return leaves
    try:
        return list(jax.tree_util.tree_leaves(tree))
    except (TypeError, ValueError, RuntimeError) as exc:
        raise BackendAdaptationError("tree", "tree", f"pytree flatten failed: {exc}") from exc


def _is_jax_array(value: Any) -> bool:
    return bool(jax is not None and isinstance(value, jax.Array))


def _validate_no_device_leaks(tree: Any) -> None:
    leaked: list[str] = []
    for leaf in _tree_leaves(tree):
        if _is_jax_array(leaf):
            leaked.append(type(leaf).__name__)
            continue
        if isinstance(leaf, np.ndarray) and leaf.dtype == object:
            for item in leaf.flat:
                if _is_jax_array(item):
                    leaked.append("object_array[jax.Array]")
                    break
    if leaked:
        raise BackendAdaptationError(
            "jax",
            "numpy",
            f"device-native leaves remained after conversion: {sorted(set(leaked))}",
        )


def _validate_host_to_jax_inputs(tree: Any) -> None:
    unsupported: list[str] = []
    for leaf in _tree_leaves(tree):
        if isinstance(leaf, np.ndarray) and leaf.dtype == object:
            unsupported.append("ndarray[object]")
    if unsupported:
        raise BackendAdaptationError(
            "numpy",
            "jax",
            f"unsupported host leaves for device adaptation: {sorted(set(unsupported))}",
        )


def to_numpy(tree: Any) -> Any:
    """
    Convert arrays in a pytree to host NumPy arrays.

    Uses JAX canonical helpers when available to avoid custom tree recursion.
    """
    if jax is None:
        raise BackendAdaptationError("jax", "numpy", "JAX runtime is not installed")
    try:
        converted = jax.device_get(tree)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise BackendAdaptationError("jax", "numpy", f"device_get failed: {exc}") from exc

    _validate_no_device_leaks(converted)
    return converted


def to_jax(tree: Any) -> Any:
    """Convert arrays in a pytree to JAX device arrays."""
    if jax is None:
        raise BackendAdaptationError("numpy", "jax", "JAX runtime is not installed")
    _validate_host_to_jax_inputs(tree)
    try:
        return jax.device_put(tree)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise BackendAdaptationError("numpy", "jax", f"device_put failed: {exc}") from exc


def adapt_state(
    state: Any,
    *,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
) -> Any:
    """Adapt state helper."""
    if source_backend == target_backend:
        return state

    if source_backend is ComputeBackend.JAX and target_backend in _HOST_BACKENDS:
        return to_numpy(state)

    if source_backend in _HOST_BACKENDS and target_backend is ComputeBackend.JAX:
        return to_jax(state)

    if source_backend in _HOST_BACKENDS and target_backend in _HOST_BACKENDS:
        return state

    raise BackendAdaptationError(
        source_backend.value,
        target_backend.value,
        "unsupported backend adaptation path",
    )
