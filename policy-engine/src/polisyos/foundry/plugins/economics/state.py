"""Public economics state module API."""

from __future__ import annotations

import chex
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import (
    compute_bottom_share,
    compute_gini_hard,
    compute_top_share,
)


@chex.dataclass(frozen=True)
class EconomicAgentState:
    """Economic state of individual agents."""

    active: jnp.ndarray
    age: jnp.ndarray
    skill_level: jnp.ndarray
    wealth: jnp.ndarray
    income: jnp.ndarray
    consumption: jnp.ndarray
    savings: jnp.ndarray
    employed: jnp.ndarray
    wage: jnp.ndarray
    hours_worked: jnp.ndarray
    discount_rate: jnp.ndarray
    risk_aversion: jnp.ndarray
    consumption_preference: jnp.ndarray

    @classmethod
    def empty(cls, n_agents: int, rng_key: jax.Array) -> EconomicAgentState:
        keys = jax.random.split(rng_key, 8)
        return cls(
            active=jnp.ones(n_agents, dtype=jnp.bool_),
            age=jax.random.randint(keys[0], (n_agents,), 18, 65, dtype=jnp.int32),
            skill_level=jax.random.uniform(keys[1], (n_agents,), minval=0.2, maxval=1.0),
            wealth=jax.random.exponential(keys[2], (n_agents,)) * 50000.0,
            income=jnp.zeros(n_agents, dtype=jnp.float32),
            consumption=jnp.zeros(n_agents, dtype=jnp.float32),
            savings=jnp.zeros(n_agents, dtype=jnp.float32),
            employed=jax.random.bernoulli(keys[3], 0.95, (n_agents,)),
            wage=jax.random.uniform(keys[4], (n_agents,), minval=20000.0, maxval=150000.0),
            hours_worked=jnp.zeros(n_agents, dtype=jnp.float32),
            discount_rate=jax.random.uniform(keys[5], (n_agents,), minval=0.9, maxval=0.99),
            risk_aversion=jax.random.uniform(keys[6], (n_agents,), minval=0.5, maxval=3.0),
            consumption_preference=jax.random.uniform(keys[7], (n_agents,), minval=0.6, maxval=0.9),
        )

    def get_observations(self) -> jnp.ndarray:
        return jnp.stack(
            [
                self.wealth / 100000.0,
                self.income / 50000.0,
                self.consumption / 50000.0,
                self.employed.astype(jnp.float32),
                self.skill_level,
                self.age.astype(jnp.float32) / 100.0,
            ],
            axis=-1,
        )


@chex.dataclass(frozen=True)
class EconomicPolicyState:
    """Government economic policy parameters."""

    tax_rate: jnp.ndarray
    transfer_rate: jnp.ndarray
    interest_rate: jnp.ndarray
    unemployment_benefit: jnp.ndarray
    minimum_wage: jnp.ndarray

    @classmethod
    def default(cls) -> EconomicPolicyState:
        return cls(
            tax_rate=jnp.array(0.25, dtype=jnp.float32),
            transfer_rate=jnp.array(0.1, dtype=jnp.float32),
            interest_rate=jnp.array(0.03, dtype=jnp.float32),
            unemployment_benefit=jnp.array(15000.0, dtype=jnp.float32),
            minimum_wage=jnp.array(15.0, dtype=jnp.float32),
        )


@chex.dataclass(frozen=True)
class EconomicDistributions:
    """Pre-computed distribution statistics."""

    gini_wealth: jnp.ndarray
    gini_income: jnp.ndarray
    top_10_share: jnp.ndarray
    bottom_50_share: jnp.ndarray
    median_wealth: jnp.ndarray
    median_income: jnp.ndarray


@chex.dataclass(frozen=True)
class EconomicAggregates:
    """Aggregate economic indicators."""

    gdp: jnp.ndarray
    total_consumption: jnp.ndarray
    total_investment: jnp.ndarray
    unemployment_rate: jnp.ndarray
    inflation_rate: jnp.ndarray
    mean_wealth: jnp.ndarray
    mean_income: jnp.ndarray


@chex.dataclass(frozen=True)
class EconomicState:
    """Complete economic domain state."""

    agents: EconomicAgentState
    policy: EconomicPolicyState
    distributions: EconomicDistributions
    aggregates: EconomicAggregates
    time_step: jnp.ndarray
    n_agents: int
    max_agents: int

    @classmethod
    def empty(
        cls,
        n_agents: int,
        seed: int,
        max_agents: int | None = None,
        **kwargs,
    ) -> EconomicState:
        del kwargs
        if max_agents is None:
            max_agents = n_agents

        rng = jax.random.PRNGKey(int(seed))
        agents = EconomicAgentState.empty(max_agents, rng)

        if n_agents < max_agents:
            active = jnp.arange(max_agents) < n_agents
            agents = agents.replace(active=active)

        distributions = cls._compute_distributions(agents)
        aggregates = cls._compute_aggregates(agents)

        return cls(
            agents=agents,
            policy=EconomicPolicyState.default(),
            distributions=distributions,
            aggregates=aggregates,
            time_step=jnp.array(0, dtype=jnp.int32),
            n_agents=int(n_agents),
            max_agents=int(max_agents),
        )

    @staticmethod
    def _median_active(values: jnp.ndarray, active: jnp.ndarray) -> jnp.ndarray:
        n_agents = values.shape[0]
        n_active = jnp.sum(active).astype(jnp.int32)

        def _no_active():
            return jnp.array(0.0, dtype=jnp.float32)

        def _with_active():
            masked = jnp.where(active, values, jnp.inf)
            sorted_vals = jnp.sort(masked)
            active_mask = jnp.arange(n_agents) < n_active
            sorted_vals = jnp.where(active_mask, sorted_vals, 0.0)
            mid = jnp.maximum(n_active - 1, 0) // 2
            return sorted_vals[mid]

        return jax.lax.cond(n_active > 0, _with_active, _no_active)

    @staticmethod
    def _compute_distributions(agents: EconomicAgentState) -> EconomicDistributions:
        active = agents.active
        gini_wealth = compute_gini_hard(agents.wealth, active)
        gini_income = compute_gini_hard(agents.income, active)
        top_10_share = compute_top_share(agents.wealth, active, top_fraction=0.10)
        bottom_50_share = compute_bottom_share(agents.wealth, active, bottom_fraction=0.50)
        median_wealth = EconomicState._median_active(agents.wealth, active)
        median_income = EconomicState._median_active(agents.income, active)

        return EconomicDistributions(
            gini_wealth=gini_wealth,
            gini_income=gini_income,
            top_10_share=top_10_share,
            bottom_50_share=bottom_50_share,
            median_wealth=median_wealth,
            median_income=median_income,
        )

    @staticmethod
    def _compute_aggregates(agents: EconomicAgentState) -> EconomicAggregates:
        active = agents.active.astype(jnp.float32)
        n_active = jnp.maximum(jnp.sum(active), 1.0)

        return EconomicAggregates(
            gdp=jnp.sum(agents.income * active),
            total_consumption=jnp.sum(agents.consumption * active),
            total_investment=jnp.sum(agents.savings * active),
            unemployment_rate=1.0
            - jnp.sum(agents.employed.astype(jnp.float32) * active) / n_active,
            inflation_rate=jnp.array(0.02, dtype=jnp.float32),
            mean_wealth=jnp.sum(agents.wealth * active) / n_active,
            mean_income=jnp.sum(agents.income * active) / n_active,
        )

    def validate(self) -> bool:
        has_negative = jnp.any(self.agents.wealth < 0)
        too_many_active = jnp.sum(self.agents.active) > self.max_agents
        return bool(~(has_negative | too_many_active))

    def update_aggregates(self) -> EconomicState:
        return self.replace(
            distributions=self._compute_distributions(self.agents),
            aggregates=self._compute_aggregates(self.agents),
        )
