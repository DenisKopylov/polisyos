from __future__ import annotations

from dataclasses import dataclass

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array

from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.population import (
    InheritanceConfig,
    PopulationConfig,
    batch_create_agents,
    batch_remove_agents,
    compute_death_mask,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


@dataclass(frozen=True)
class AgingMechanism(Mechanism):
    steps_per_year: int = 12
    retirement_age: int = 65
    fertility_start: int = 20
    fertility_end: int = 45
    peak_fertility: float = 0.03

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="aging",
            reads=frozenset({"agents.active", "agents.age", "agents.life_expectancy"}),
            writes=frozenset({"agents.age", "agents.fertility_rate", "agents.retired"}),
            parameters={"steps_per_year": int},
            stochastic=False,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del rng_key, fidelity
        agents = state.agents
        active = agents.active

        new_age = jnp.where(active, agents.age + 1, agents.age)
        age_years = new_age // self.steps_per_year

        in_fertile = (age_years >= self.fertility_start) & (age_years <= self.fertility_end)
        peak = jnp.float32(0.5 * (self.fertility_start + self.fertility_end))
        age_from_peak = jnp.abs(age_years.astype(jnp.float32) - peak)
        fertility_factor = jnp.exp(jnp.float32(-0.01) * age_from_peak**2)
        new_fertility = jnp.where(
            in_fertile & active,
            jnp.float32(self.peak_fertility) * fertility_factor,
            jnp.float32(0.0),
        )

        new_retired = (age_years >= self.retirement_age) & active
        new_employed = agents.employed & ~new_retired

        new_agents = agents.replace(
            age=new_age,
            fertility_rate=new_fertility,
            retired=new_retired,
            employed=new_employed,
        )

        active_f = active.astype(jnp.float32)
        active_count = jnp.maximum(jnp.sum(active_f), 1.0)
        metrics = {
            "mean_age": jnp.sum(new_age * active_f) / active_count / self.steps_per_year,
            "n_retired": jnp.sum(new_retired),
            "mean_fertility": jnp.sum(new_fertility * active_f) / active_count,
        }
        return state.replace(agents=new_agents), metrics


@dataclass(frozen=True)
class BirthMechanism(Mechanism):
    max_births_per_step: int = 100
    steps_per_year: int = 12
    config: PopulationConfig = PopulationConfig()

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="birth",
            reads=frozenset(
                {"agents.active", "agents.fertility_rate", "agents.wealth", "agents.risk_aversion"}
            ),
            writes=frozenset({"agents", "population_manager"}),
            parameters={"max_births_per_step": int},
            stochastic=True,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del fidelity
        agents = state.agents
        key1, key2 = jax.random.split(rng_key)

        birth_probs = agents.fertility_rate * agents.active.astype(jnp.float32)
        random_vals = jax.random.uniform(key1, shape=birth_probs.shape)
        gives_birth = random_vals < birth_probs

        n_births_raw = jnp.sum(gives_birth.astype(jnp.int32))
        max_births = min(self.max_births_per_step, agents.active.shape[0])
        n_births = jnp.minimum(n_births_raw, max_births)

        priority = jnp.where(
            gives_birth,
            jax.random.uniform(key2, shape=gives_birth.shape),
            -1.0,
        )
        _, parent_indices_all = jax.lax.top_k(priority, max_births)
        valid_mask = jnp.arange(max_births) < n_births
        parent_indices = jnp.where(valid_mask, parent_indices_all, -1)

        pad = self.max_births_per_step - max_births
        if pad > 0:
            parent_indices = jnp.pad(parent_indices, (0, pad), constant_values=-1)
        new_state = batch_create_agents(
            state,
            n_new=self.max_births_per_step,
            parent_indices=parent_indices,
            rng_key=jax.random.fold_in(key2, 1),
            config=self.config,
            n_requested=n_births,
            birth_step=state.time_step,
            steps_per_year=self.steps_per_year,
        )

        active_count = jnp.maximum(jnp.sum(agents.active), 1.0)
        metrics = {
            "n_births": n_births,
            "birth_rate": n_births / active_count,
            "n_potential_births": n_births_raw,
        }
        return new_state, metrics


@dataclass(frozen=True)
class DeathMechanism(Mechanism):
    base_mortality_rate: float = 0.001
    age_mortality_factor: float = 0.0001
    wealth_mortality_factor: float = -0.0001
    steps_per_year: int = 12

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="death",
            reads=frozenset({"agents.active", "agents.age", "agents.life_expectancy", "agents.wealth"}),
            writes=frozenset({"agents", "population_manager"}),
            parameters={"base_mortality_rate": float},
            stochastic=True,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del fidelity
        agents = state.agents
        death_mask = compute_death_mask(
            state,
            rng_key,
            base_mortality_rate=self.base_mortality_rate,
            age_mortality_factor=self.age_mortality_factor,
            wealth_mortality_factor=self.wealth_mortality_factor,
            steps_per_year=self.steps_per_year,
        )

        inheritance = jnp.sum(agents.wealth * death_mask.astype(jnp.float32))
        survivors = agents.active & ~death_mask
        n_survivors = jnp.sum(survivors)
        per_agent = inheritance / (n_survivors + 1e-8)
        new_wealth = agents.wealth + jnp.where(survivors, per_agent, 0.0)

        updated_state = state.replace(agents=agents.replace(wealth=new_wealth))
        updated_state = batch_remove_agents(updated_state, death_mask)

        n_deaths = jnp.sum(death_mask)
        metrics = {
            "n_deaths": n_deaths,
            "death_rate": n_deaths / (jnp.sum(agents.active) + 1e-8),
            "mean_death_age": jnp.sum(agents.age * death_mask) / (n_deaths + 1e-8)
            / self.steps_per_year,
            "inheritance_total": inheritance,
        }
        return updated_state, metrics


@dataclass(frozen=True)
class MigrationMechanism(Mechanism):
    immigration_rate: float = 0.001
    emigration_rate: float = 0.0005
    emigration_wealth_factor: float = -0.1
    steps_per_year: int = 12
    max_immigrants_per_step: int = 100
    config: PopulationConfig = PopulationConfig()

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="migration",
            reads=frozenset(
                {"agents.active", "agents.wealth", "agents.income", "agents.age", "agents.employed"}
            ),
            writes=frozenset({"agents", "population_manager"}),
            parameters={"immigration_rate": float, "emigration_rate": float},
            stochastic=True,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del fidelity
        key1, key2, key3 = jax.random.split(rng_key, 3)
        agents = state.agents
        n_active = jnp.sum(agents.active)

        wealth_factor = self.emigration_wealth_factor * jnp.log(agents.wealth + 1.0)
        unemployed_factor = 0.02 * (~agents.employed).astype(jnp.float32)
        emigration_prob = jnp.clip(
            self.emigration_rate + wealth_factor + unemployed_factor,
            0.0,
            0.1,
        )
        emigration_prob = jnp.where(agents.active, emigration_prob, 0.0)
        random_vals = jax.random.uniform(key1, shape=emigration_prob.shape)
        emigrates = random_vals < emigration_prob

        state_after_emigration = batch_remove_agents(state, emigrates)
        n_emigrants = jnp.sum(emigrates)

        n_immigrants = (n_active * self.immigration_rate).astype(jnp.int32)
        n_immigrants = jnp.minimum(n_immigrants, self.max_immigrants_per_step)

        parent_indices = jnp.full((self.max_immigrants_per_step,), -1, dtype=jnp.int32)
        immigrant_ages = jax.random.randint(
            key3,
            (self.max_immigrants_per_step,),
            minval=20 * self.steps_per_year,
            maxval=50 * self.steps_per_year,
        )

        state_after_immigration = batch_create_agents(
            state_after_emigration,
            n_new=self.max_immigrants_per_step,
            parent_indices=parent_indices,
            rng_key=key2,
            config=self.config,
            n_requested=n_immigrants,
            age_override=immigrant_ages,
            birth_step=state.time_step,
            steps_per_year=self.steps_per_year,
        )

        metrics = {
            "n_emigrants": n_emigrants,
            "n_immigrants": n_immigrants,
            "net_migration": n_immigrants - n_emigrants,
            "emigration_rate_actual": n_emigrants / (n_active + 1e-8),
        }
        return state_after_immigration, metrics


@dataclass(frozen=True)
class InheritanceMechanism:
    config: InheritanceConfig = InheritanceConfig()

    def apply(
        self,
        state: GlobalState,
        death_mask: jnp.ndarray,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del rng_key, fidelity
        agents = state.agents
        estate = agents.wealth * death_mask.astype(jnp.float32)
        tax = estate * self.config.inheritance_tax_rate
        estate_after_tax = estate - tax

        parent_slot = agents.parent_slot
        parent_slot_safe = jnp.clip(parent_slot, 0, agents.active.shape[0] - 1)
        parent_match = (parent_slot >= 0) & (
            agents.agent_id[parent_slot_safe] == agents.parent_id
        )
        is_heir = agents.active & parent_match & death_mask[parent_slot_safe]

        total_estate = jnp.sum(estate_after_tax)
        n_heirs = jnp.sum(is_heir)
        inheritance_per_heir = jnp.where(
            n_heirs > 0,
            total_estate * self.config.inheritance_to_children / n_heirs,
            0.0,
        )
        inheritance_per_heir = jnp.minimum(
            inheritance_per_heir, self.config.max_inheritance_per_heir
        )

        inheritance_received = jnp.where(is_heir, inheritance_per_heir, 0.0)
        new_wealth = agents.wealth + inheritance_received

        distributed = inheritance_per_heir * n_heirs
        unclaimed = total_estate * self.config.inheritance_to_children - distributed

        new_agents = agents.replace(wealth=new_wealth)
        metrics = {
            "total_inheritance": total_estate,
            "inheritance_tax_collected": jnp.sum(tax),
            "n_heirs": n_heirs,
            "mean_inheritance": inheritance_per_heir,
            "unclaimed_estate": unclaimed,
        }
        return state.replace(agents=new_agents), metrics


@dataclass(frozen=True)
class GiftTransferMechanism(Mechanism):
    transfer_probability: float = 0.01
    transfer_fraction: float = 0.05
    min_parent_age: int = 50 * 12
    min_wealth_for_transfer: float = 100.0

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="gift_transfer",
            reads=frozenset(
                {
                    "agents.active",
                    "agents.wealth",
                    "agents.age",
                    "agents.parent_id",
                    "agents.parent_slot",
                    "agents.agent_id",
                }
            ),
            writes=frozenset({"agents.wealth"}),
            parameters={"transfer_probability": float, "transfer_fraction": float},
            stochastic=True,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del fidelity
        agents = state.agents
        can_transfer = (
            agents.active
            & (agents.age >= self.min_parent_age)
            & (agents.wealth >= self.min_wealth_for_transfer)
        )
        random_vals = jax.random.uniform(rng_key, shape=can_transfer.shape)
        does_transfer = can_transfer & (random_vals < self.transfer_probability)

        transfer_amount = agents.wealth * self.transfer_fraction * does_transfer.astype(jnp.float32)
        parent_slot = agents.parent_slot
        parent_slot_safe = jnp.clip(parent_slot, 0, agents.active.shape[0] - 1)
        parent_match = (parent_slot >= 0) & (
            agents.agent_id[parent_slot_safe] == agents.parent_id
        )
        receives_transfer = agents.active & parent_match & does_transfer[parent_slot_safe]

        received = jnp.where(receives_transfer, transfer_amount[parent_slot_safe], 0.0)
        new_wealth = jnp.maximum(agents.wealth - transfer_amount + received, 0.0)
        new_agents = agents.replace(wealth=new_wealth)

        metrics = {
            "n_transfers": jnp.sum(does_transfer),
            "total_transferred": jnp.sum(transfer_amount),
            "mean_transfer": jnp.sum(transfer_amount) / (jnp.sum(does_transfer) + 1e-8),
        }
        return state.replace(agents=new_agents), metrics
