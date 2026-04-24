"""Public agent sim population executor module API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import chex
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import DistributionConfig
from polisyos.foundry.agent_sim.graph_executor import GraphAwareExecutor
from polisyos.foundry.agent_sim.graphs import DynamicGraphUpdater
from polisyos.foundry.agent_sim.mechanism import Mechanism
from polisyos.foundry.agent_sim.population import (
    GraphSyncConfig,
    LifecycleConfig,
    batch_remove_agents,
    compute_death_mask,
    sync_graph_with_population,
)
from polisyos.foundry.agent_sim.population_mechanisms import (
    AgingMechanism,
    BirthMechanism,
    GiftTransferMechanism,
    InheritanceMechanism,
    MigrationMechanism,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


def lifecycle_step(
    state: GlobalState,
    rng_key: chex.PRNGKey,
    config: LifecycleConfig,
    *,
    aging_mech: AgingMechanism,
    birth_mech: BirthMechanism,
    migration_mech: MigrationMechanism,
    inheritance_mech: InheritanceMechanism,
    gift_mech: GiftTransferMechanism | None,
    fidelity: FidelityLevel,
) -> tuple[GlobalState, dict[str, jnp.ndarray], jnp.ndarray]:
    """Run aging, death, birth, migration, and transfer mechanics for one lifecycle tick."""
    keys = jax.random.split(rng_key, 5)
    all_metrics: dict[str, jnp.ndarray] = {}

    state, metrics = aging_mech.apply(state, None, fidelity)
    all_metrics.update({f"aging/{k}": v for k, v in metrics.items()})

    death_mask = compute_death_mask(
        state,
        keys[0],
        base_mortality_rate=config.base_mortality_rate,
        age_mortality_factor=config.age_mortality_factor,
        wealth_mortality_factor=config.wealth_mortality_factor,
        steps_per_year=config.steps_per_year,
    )

    state, metrics = inheritance_mech.apply(state, death_mask, None, fidelity)
    all_metrics.update({f"inheritance/{k}": v for k, v in metrics.items()})

    state = batch_remove_agents(state, death_mask)
    all_metrics["death/n_deaths"] = jnp.sum(death_mask)
    active_after_deaths = state.agents.active

    state, metrics = birth_mech.apply(state, keys[1], fidelity)
    all_metrics.update({f"birth/{k}": v for k, v in metrics.items()})

    state, metrics = migration_mech.apply(state, keys[2], fidelity)
    all_metrics.update({f"migration/{k}": v for k, v in metrics.items()})

    if config.enable_gift_transfers and gift_mech is not None:
        state, metrics = gift_mech.apply(state, keys[3], fidelity)
        all_metrics.update({f"gifts/{k}": v for k, v in metrics.items()})

    all_metrics["population/n_active"] = state.population_manager.n_active
    births = all_metrics.get("birth/n_births", jnp.array(0.0))
    deaths = all_metrics.get("death/n_deaths", jnp.array(0.0))
    all_metrics["population/birth_death_ratio"] = births / (deaths + 1e-8)

    births_mask = state.agents.active & ~active_after_deaths
    return state, all_metrics, births_mask


class PopulationAwareExecutor(GraphAwareExecutor):
    """Wrap the base executor with lifecycle, graph, and distribution updates."""

    def __init__(
        self,
        mechanisms: Iterable[Mechanism],
        *,
        lifecycle_config: LifecycleConfig,
        distribution_config: DistributionConfig | None = None,
        lifecycle_frequency: int = 1,
        graph_sync_config: GraphSyncConfig | None = None,
        graph_update_frequency: int = 16,
        graph_update_salt: int = 991,
        graph_updater: DynamicGraphUpdater | None = None,
        prng_config: dict[str, int] | None = None,
        aggregate_every: int | None = None,
        compute_gini: bool = False,
    ):
        if distribution_config is None:
            distribution_config = DistributionConfig()
        super().__init__(
            list(mechanisms),
            distribution_config=distribution_config,
            graph_update_frequency=graph_update_frequency,
            graph_update_salt=graph_update_salt,
            graph_updater=graph_updater,
            prng_config=prng_config,
            aggregate_every=aggregate_every,
            compute_gini=compute_gini,
        )
        self.lifecycle_config = lifecycle_config
        self.lifecycle_frequency = lifecycle_frequency
        self.graph_sync_config = graph_sync_config

        pop_cfg = lifecycle_config.population_config
        self.aging_mech = AgingMechanism(
            steps_per_year=lifecycle_config.steps_per_year,
            retirement_age=pop_cfg.retirement_age,
            fertility_start=pop_cfg.fertility_start_age,
            fertility_end=pop_cfg.fertility_end_age,
            peak_fertility=pop_cfg.base_fertility_rate,
        )
        self.birth_mech = BirthMechanism(
            max_births_per_step=lifecycle_config.max_births_per_step,
            steps_per_year=lifecycle_config.steps_per_year,
            config=pop_cfg,
        )
        self.migration_mech = MigrationMechanism(
            max_immigrants_per_step=lifecycle_config.max_immigrants_per_step,
            steps_per_year=lifecycle_config.steps_per_year,
            config=pop_cfg,
        )
        self.inheritance_mech = InheritanceMechanism()
        self.gift_mech = GiftTransferMechanism() if lifecycle_config.enable_gift_transfers else None

    def step(
        self,
        state: GlobalState,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, Any]]:
        key, lifecycle_key = jax.random.split(state.rng_key)
        state = state.replace(rng_key=key)

        lifecycle_metrics: dict[str, jnp.ndarray] = {}
        old_active = state.agents.active
        births_mask = jnp.zeros_like(old_active, dtype=jnp.bool_)

        if self.lifecycle_frequency > 0:
            should_run_lifecycle = (state.time_step % self.lifecycle_frequency) == 0
            next_state, next_metrics, next_births_mask = lifecycle_step(
                state,
                lifecycle_key,
                self.lifecycle_config,
                aging_mech=self.aging_mech,
                birth_mech=self.birth_mech,
                migration_mech=self.migration_mech,
                inheritance_mech=self.inheritance_mech,
                gift_mech=self.gift_mech,
                fidelity=fidelity,
            )
            state = jax.tree_util.tree_map(
                lambda updated, current: jnp.where(should_run_lifecycle, updated, current),
                next_state,
                state,
            )
            lifecycle_metrics = {
                key: jnp.where(should_run_lifecycle, value, jnp.zeros_like(value))
                for key, value in next_metrics.items()
            }
            births_mask = jnp.where(
                should_run_lifecycle,
                next_births_mask,
                births_mask,
            )

        if self.graph_sync_config is not None:
            new_active = state.agents.active
            state = state.replace(
                graph=sync_graph_with_population(
                    state.graph,
                    old_active,
                    new_active,
                    births_mask,
                    lifecycle_key,
                    self.graph_sync_config,
                    parent_slots=state.agents.parent_slot,
                )
            )

        state, metrics = super().step(state, fidelity)
        metrics.update(lifecycle_metrics)
        return state, metrics
