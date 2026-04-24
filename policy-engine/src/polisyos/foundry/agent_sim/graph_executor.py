"""Public agent sim graph executor module API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import (
    DistributionConfig,
    maybe_update_distributions,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.graphs import DynamicGraphUpdater, compute_graph_metrics
from polisyos.foundry.agent_sim.mechanism import Mechanism
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


class GraphAwareExecutor(PureExecutor):
    """Augment execution with scheduled graph rewiring and graph-level diagnostics."""

    def __init__(
        self,
        mechanisms: Iterable[Mechanism],
        *,
        distribution_config: DistributionConfig,
        graph_update_frequency: int = 16,
        graph_update_salt: int = 991,
        graph_updater: DynamicGraphUpdater | None = None,
        prng_config: dict[str, int] | None = None,
        aggregate_every: int | None = None,
        compute_gini: bool = False,
    ):
        super().__init__(
            list(mechanisms),
            prng_config=prng_config,
            aggregate_every=aggregate_every,
            compute_gini=compute_gini,
        )
        self.distribution_config = distribution_config
        self.graph_update_frequency = graph_update_frequency
        self.graph_update_salt = graph_update_salt
        self.graph_updater = graph_updater or DynamicGraphUpdater()

    def step(
        self,
        state: GlobalState,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, Any]]:
        state = maybe_update_distributions(state, self.distribution_config)
        state = self._maybe_update_graph(state)
        state, metrics = super().step(state, fidelity)
        metrics.update(compute_graph_metrics(state.graph.edges, state.agents.active))
        return state, metrics

    def _maybe_update_graph(self, state: GlobalState) -> GlobalState:
        if self.graph_update_frequency <= 0:
            return state

        should_update = (state.time_step % self.graph_update_frequency) == 0

        def _update(s: GlobalState) -> GlobalState:
            key = jax.random.fold_in(
                s.rng_key, jnp.asarray(self.graph_update_salt, dtype=jnp.uint32)
            )
            key = jax.random.fold_in(key, jnp.asarray(s.time_step, dtype=jnp.uint32))
            graph = s.graph
            if hasattr(s.graph.edges, "active"):
                graph = self.graph_updater.update_graph(s.graph, s.agents, key)
            graph = graph.replace(last_structure_update=s.time_step)
            return s.replace(graph=graph)

        return jax.lax.cond(should_update, _update, lambda s: s, state)


def create_graph_aware_executor(
    mechanisms: Iterable[Mechanism],
    distribution_config: DistributionConfig,
    *,
    graph_update_frequency: int = 16,
    graph_update_salt: int = 991,
    graph_updater: DynamicGraphUpdater | None = None,
    prng_config: dict[str, int] | None = None,
    aggregate_every: int | None = None,
    compute_gini: bool = False,
) -> GraphAwareExecutor:
    """Create graph aware executor."""
    return GraphAwareExecutor(
        mechanisms,
        distribution_config=distribution_config,
        graph_update_frequency=graph_update_frequency,
        graph_update_salt=graph_update_salt,
        graph_updater=graph_updater,
        prng_config=prng_config,
        aggregate_every=aggregate_every,
        compute_gini=compute_gini,
    )
