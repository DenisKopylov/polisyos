"""Public agent sim executor module API."""

from __future__ import annotations

from collections.abc import Iterable
from functools import partial
from typing import Any

import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.mechanism import Mechanism
from polisyos.foundry.agent_sim.prng import get_mechanism_key
from polisyos.foundry.agent_sim.state import GlobalState, compute_aggregates
from polisyos.foundry.contracts.fidelity import FidelityLevel


class MechanismOrder:
    """Deterministic topological ordering of mechanisms based on reads/writes."""

    def __init__(self, mechanisms: Iterable[Mechanism]):
        self.mechanisms = list(mechanisms)
        self.order = self._topological_sort()

    def _topological_sort(self) -> list[int]:
        n = len(self.mechanisms)
        deps = [set() for _ in range(n)]

        for i, mech_i in enumerate(self.mechanisms):
            for j, mech_j in enumerate(self.mechanisms):
                if i == j:
                    continue
                if mech_j.spec.writes & mech_i.spec.reads:
                    deps[i].add(j)

        result: list[int] = []
        remaining = set(range(n))
        while remaining:
            ready = [idx for idx in remaining if not (deps[idx] & remaining)]
            if not ready:
                raise ValueError("Circular dependency detected in mechanism graph")
            next_idx = min(ready)
            result.append(next_idx)
            remaining.remove(next_idx)
        return result


class PureExecutor:
    """Runs a pure JAX-compatible multi-agent step and scan."""

    def __init__(
        self,
        mechanisms: list[Mechanism],
        prng_config: dict[str, int] | None = None,
        *,
        aggregate_every: int | None = None,
        compute_gini: bool = False,
    ):
        self.mechanisms = list(mechanisms)
        self.order = MechanismOrder(self.mechanisms)
        if prng_config is None:
            prng_config = {mech.spec.name: idx for idx, mech in enumerate(self.mechanisms)}
        self.prng_config = dict(prng_config)
        self.aggregate_every = aggregate_every
        self.compute_gini = compute_gini

    def step(
        self,
        state: GlobalState,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, Any]]:
        all_metrics: dict[str, Any] = {}

        for idx in self.order.order:
            mechanism = self.mechanisms[idx]
            if mechanism.spec.stochastic:
                salt = self.prng_config.get(mechanism.spec.name, idx)
                mech_key = get_mechanism_key(state.rng_key, state.time_step, salt)
            else:
                mech_key = None

            state, metrics = mechanism.apply(state, mech_key, fidelity)
            for key, value in metrics.items():
                all_metrics[f"{mechanism.spec.name}/{key}"] = value

        if self.aggregate_every is not None:
            state = self._maybe_update_aggregates(state)

        state = state.replace(time_step=state.time_step + 1)
        return state, all_metrics

    @partial(jax.jit, static_argnums=(0, 2, 3))
    def run(
        self,
        initial_state: GlobalState,
        n_steps: int,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, jnp.ndarray]]:
        def scan_fn(state, _):
            new_state, metrics = self.step(state, fidelity)
            return new_state, metrics

        final_state, all_metrics = jax.lax.scan(
            scan_fn,
            initial_state,
            None,
            length=int(n_steps),
        )
        return final_state, all_metrics

    def _maybe_update_aggregates(self, state: GlobalState) -> GlobalState:
        if self.aggregate_every is None:
            return state

        def _update(s: GlobalState) -> GlobalState:
            aggregates = compute_aggregates(s.agents, compute_gini=self.compute_gini)
            return s.replace(aggregates=aggregates)

        should_update = (state.time_step % self.aggregate_every) == 0
        return jax.lax.cond(should_update, _update, lambda s: s, state)
