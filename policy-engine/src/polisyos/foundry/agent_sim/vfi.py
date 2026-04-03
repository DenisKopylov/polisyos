"""Public agent sim vfi module API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import jax
import jax.numpy as jnp


@dataclass
class OfflineVFI:
    """Offline VFI public type."""
    state_grid: dict[str, jnp.ndarray]
    action_grid: jnp.ndarray
    transition_fn: Callable[[dict[str, float], jnp.ndarray], dict[str, float]]
    reward_fn: Callable[[dict[str, float], jnp.ndarray], float]
    discount_factor: float = 0.99
    tolerance: float = 1e-6
    max_iterations: int = 1000

    def solve(self) -> tuple[jnp.ndarray, jnp.ndarray]:
        grid_axes = list(self.state_grid.keys())
        grid_values = [self.state_grid[name] for name in grid_axes]
        grid_shape = tuple(len(v) for v in grid_values)
        v_table = jnp.zeros(grid_shape, dtype=jnp.float32)

        for _ in range(int(self.max_iterations)):
            v_new = jnp.zeros_like(v_table)
            for idx in _iter_indices(grid_shape):
                state = {name: float(grid_values[i][idx[i]]) for i, name in enumerate(grid_axes)}
                best_value = -jnp.inf
                for action in self.action_grid:
                    reward = self.reward_fn(state, action)
                    next_state = self.transition_fn(state, action)
                    next_value = self._interpolate(v_table, next_state)
                    q_value = reward + self.discount_factor * next_value
                    best_value = jnp.maximum(best_value, q_value)
                v_new = v_new.at[idx].set(best_value)
            if float(jnp.max(jnp.abs(v_new - v_table))) < float(self.tolerance):
                v_table = v_new
                break
            v_table = v_new

        policy_table = self._extract_policy(v_table)
        return v_table, policy_table

    def _interpolate(self, v_table: jnp.ndarray, state: dict[str, float]) -> float:
        idx = []
        for name, grid in self.state_grid.items():
            value = float(state[name])
            idx.append(int(jnp.argmin(jnp.abs(grid - value))))
        return float(v_table[tuple(idx)])

    def _extract_policy(self, v_table: jnp.ndarray) -> jnp.ndarray:
        grid_axes = list(self.state_grid.keys())
        grid_values = [self.state_grid[name] for name in grid_axes]
        grid_shape = tuple(len(v) for v in grid_values)
        action_dim = int(self.action_grid.shape[1]) if self.action_grid.ndim > 1 else 1
        policy_table = jnp.zeros(grid_shape + (action_dim,), dtype=jnp.float32)
        for idx in _iter_indices(grid_shape):
            state = {name: float(grid_values[i][idx[i]]) for i, name in enumerate(grid_axes)}
            best_value = -jnp.inf
            best_action = None
            for action in self.action_grid:
                reward = self.reward_fn(state, action)
                next_state = self.transition_fn(state, action)
                next_value = self._interpolate(v_table, next_state)
                q_value = reward + self.discount_factor * next_value
                if q_value > best_value:
                    best_value = q_value
                    best_action = action
            if best_action is None:
                best_action = jnp.zeros((action_dim,), dtype=jnp.float32)
            policy_table = policy_table.at[idx].set(best_action)
        return policy_table


@dataclass
class VFILookupTable:
    """VFI lookup table public type."""
    value_table: jnp.ndarray
    policy_table: jnp.ndarray
    state_grid: dict[str, jnp.ndarray]

    def get_value(self, states: dict[str, jnp.ndarray]) -> jnp.ndarray:
        names = list(self.state_grid.keys())
        grids = [self.state_grid[name] for name in names]

        def _lookup(*vals):
            idx = tuple(jnp.argmin(jnp.abs(grid - val)) for grid, val in zip(grids, vals))
            return self.value_table[idx]

        return jax.vmap(_lookup)(*([states[name] for name in names]))

    def get_action(self, states: dict[str, jnp.ndarray]) -> jnp.ndarray:
        names = list(self.state_grid.keys())
        grids = [self.state_grid[name] for name in names]

        def _lookup(*vals):
            idx = tuple(jnp.argmin(jnp.abs(grid - val)) for grid, val in zip(grids, vals))
            return self.policy_table[idx]

        return jax.vmap(_lookup)(*([states[name] for name in names]))

    def _interpolate_value(self, state: dict[str, float]) -> float:
        idx = []
        for name, grid in self.state_grid.items():
            value = float(state[name])
            idx.append(int(jnp.argmin(jnp.abs(grid - value))))
        return float(self.value_table[tuple(idx)])

    def _interpolate_policy(self, state: dict[str, float]) -> jnp.ndarray:
        idx = []
        for name, grid in self.state_grid.items():
            value = float(state[name])
            idx.append(int(jnp.argmin(jnp.abs(grid - value))))
        return self.policy_table[tuple(idx)]


def _iter_indices(shape: tuple[int, ...]):
    if not shape:
        yield ()
        return
    stacks = [range(dim) for dim in shape]
    def _recurse(prefix, dims):
        if not dims:
            yield tuple(prefix)
            return
        for idx in dims[0]:
            prefix.append(idx)
            yield from _recurse(prefix, dims[1:])
            prefix.pop()
    yield from _recurse([], stacks)
