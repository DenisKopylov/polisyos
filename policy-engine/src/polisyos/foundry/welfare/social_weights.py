"""Runtime helpers for applying estimated social-weight schedules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import jax.numpy as jnp

from polisyos.foundry.methods.catalog.policy.welfare import (
    register_social_weight_manifest,
    resolve_social_weight_schedule,
)


def prepare_social_weight_schedule(
    *,
    social_weight_ref: str | None = None,
    social_weight_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve a `social_weight_ref` into JAX arrays usable inside objective code."""
    ref = social_weight_ref
    if social_weight_manifest is not None:
        manifest = register_social_weight_manifest(social_weight_manifest)
        if ref is not None and str(ref).strip() and manifest["ref"] != str(ref).strip():
            raise ValueError("social_weight_ref does not match the provided social_weight_manifest")
        ref = manifest["ref"]

    payload = resolve_social_weight_schedule(ref)
    if payload is None and ref is not None and str(ref).strip():
        raise ValueError("social_weight_ref could not be resolved; provide a registered manifest")
    if payload is None:
        return None

    return {
        "ref": payload["ref"],
        "income_grid": jnp.asarray(payload["income_grid"], dtype=jnp.float32),
        "weights_on_grid": jnp.asarray(payload["weights_on_grid"], dtype=jnp.float32),
    }


def social_weights_for_incomes(
    incomes: jnp.ndarray,
    schedule: Mapping[str, Any],
    *,
    active: jnp.ndarray | None = None,
) -> jnp.ndarray:
    """Interpolate a registered weight schedule onto agent incomes and normalize it."""
    grid = jnp.asarray(schedule["income_grid"], dtype=jnp.float32)
    values = jnp.asarray(schedule["weights_on_grid"], dtype=jnp.float32)
    incomes = jnp.asarray(incomes, dtype=jnp.float32)

    if grid.shape[0] == 1:
        weights = jnp.broadcast_to(values[0], incomes.shape)
    else:
        clipped = jnp.clip(incomes, grid[0], grid[-1])
        index = jnp.searchsorted(grid, clipped, side="right") - 1
        index = jnp.clip(index, 0, grid.shape[0] - 2)
        x0 = grid[index]
        x1 = grid[index + 1]
        y0 = values[index]
        y1 = values[index + 1]
        span = x1 - x0
        fraction = jnp.where(jnp.abs(span) > 1.0e-12, (clipped - x0) / span, 0.0)
        weights = y0 + fraction * (y1 - y0)

    weights = jnp.clip(weights, 0.0, None)
    if active is None:
        active = jnp.ones_like(incomes, dtype=jnp.bool_)
    active_f = active.astype(jnp.float32)
    active_count = jnp.maximum(jnp.sum(active_f), 1.0)
    active_mean = jnp.sum(weights * active_f) / active_count
    normalized = weights / jnp.maximum(active_mean, 1.0e-6)
    return jnp.where(active, normalized, 0.0)


def social_weighted_resource(
    resources: jnp.ndarray,
    incomes: jnp.ndarray,
    active: jnp.ndarray,
    schedule: Mapping[str, Any],
) -> jnp.ndarray:
    """Average resources after applying state-dependent social welfare weights."""
    weights = social_weights_for_incomes(incomes, schedule, active=active)
    active_f = active.astype(jnp.float32)
    active_count = jnp.maximum(jnp.sum(active_f), 1.0)
    return jnp.sum(weights * resources * active_f) / active_count


__all__ = [
    "prepare_social_weight_schedule",
    "social_weighted_resource",
    "social_weights_for_incomes",
]
