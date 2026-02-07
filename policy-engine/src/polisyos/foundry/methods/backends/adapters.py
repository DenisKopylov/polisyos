from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.foundry.methods.base import ComputeBackend


def to_numpy(tree: Any) -> Any:
    """
    Convert arrays in a pytree to host NumPy arrays.

    Uses JAX canonical helpers when available to avoid custom tree recursion.
    """
    try:
        import jax

        return jax.device_get(tree)
    except Exception:
        if hasattr(tree, "shape") and hasattr(tree, "dtype"):
            return np.asarray(tree)
        return tree


def to_jax(tree: Any) -> Any:
    """Convert arrays in a pytree to JAX device arrays."""
    import jax

    return jax.device_put(tree)


def adapt_state(
    state: Any,
    *,
    source_backend: ComputeBackend,
    target_backend: ComputeBackend,
) -> Any:
    if source_backend == target_backend:
        return state

    if source_backend is ComputeBackend.JAX and target_backend in (
        ComputeBackend.NUMPY,
        ComputeBackend.SOLVER,
    ):
        return to_numpy(state)

    if source_backend in (ComputeBackend.NUMPY, ComputeBackend.SOLVER) and target_backend is ComputeBackend.JAX:
        return to_jax(state)

    return state

