"""Public economics mechanisms module API."""

from __future__ import annotations

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.plugins.economics.state import EconomicState


class TaxationMechanism(eqx.Module):
    """Progressive taxation mechanism."""

    brackets: tuple[tuple[float, float], ...] = (
        (0.0, 0.10),
        (10000.0, 0.15),
        (40000.0, 0.22),
        (85000.0, 0.24),
        (160000.0, 0.32),
        (200000.0, 0.35),
        (500000.0, 0.37),
    )

    @property
    def name(self) -> str:
        return "taxation"

    def apply(self, state: EconomicState, **kwargs) -> EconomicState:
        del kwargs
        agents = state.agents
        income = agents.income
        active = agents.active.astype(jnp.float32)

        tax = jnp.zeros_like(income)
        thresholds = [t for t, _ in self.brackets]

        for i, (lower, rate) in enumerate(self.brackets):
            bracket_income = jnp.maximum(income - lower, 0.0)
            if i + 1 < len(thresholds):
                width = thresholds[i + 1] - lower
                bracket_income = jnp.minimum(bracket_income, width)
            tax = tax + bracket_income * rate * active

        tax = tax * (1.0 + state.policy.tax_rate - 0.25)

        new_wealth = agents.wealth - tax
        new_agents = agents.replace(wealth=new_wealth)
        return state.replace(agents=new_agents)


class TransferMechanism(eqx.Module):
    """Government transfers (welfare, UBI, etc.)."""

    means_tested: bool = True

    @property
    def name(self) -> str:
        return "transfers"

    def apply(self, state: EconomicState, **kwargs) -> EconomicState:
        del kwargs
        agents = state.agents
        policy = state.policy
        active = agents.active.astype(jnp.float32)

        transfer = policy.transfer_rate * state.aggregates.mean_income

        unemployed = (~agents.employed).astype(jnp.float32)
        transfer = transfer + unemployed * policy.unemployment_benefit

        if self.means_tested:
            wealth_factor = jnp.clip(1.0 - agents.wealth / 100000.0, 0.0, 1.0)
            transfer = transfer * wealth_factor

        new_wealth = agents.wealth + transfer * active
        new_agents = agents.replace(wealth=new_wealth)
        return state.replace(agents=new_agents)


class LaborMarketMechanism(eqx.Module):
    """Labor market dynamics: employment, wages, hours."""

    job_finding_rate: float = 0.3
    job_separation_rate: float = 0.02
    wage_growth_rate: float = 0.02

    @property
    def name(self) -> str:
        return "labor_market"

    def apply(
        self,
        state: EconomicState,
        rng_key: jax.Array | None = None,
        **kwargs,
    ) -> EconomicState:
        del kwargs
        if rng_key is None:
            rng_key = jax.random.PRNGKey(int(state.time_step))

        key1, key2, key3 = jax.random.split(rng_key, 3)
        agents = state.agents
        active = agents.active

        unemployed = ~agents.employed & active
        find_prob = jnp.clip(self.job_finding_rate * agents.skill_level, 0.0, 1.0)
        finds_job = jax.random.bernoulli(key1, find_prob) & unemployed

        employed = agents.employed & active
        sep_prob = jnp.clip(
            self.job_separation_rate * (1.0 - agents.skill_level * 0.5),
            0.0,
            1.0,
        )
        loses_job = jax.random.bernoulli(key2, sep_prob) & employed

        new_employed = (agents.employed | finds_job) & ~loses_job

        wage_shock = jax.random.normal(key3, agents.wage.shape) * 0.02
        new_wage = agents.wage * (1.0 + self.wage_growth_rate + wage_shock)
        min_wage = state.policy.minimum_wage * 2000.0
        new_wage = jnp.maximum(new_wage, min_wage)

        new_income = jnp.where(new_employed, new_wage, 0.0)

        new_agents = agents.replace(
            employed=new_employed,
            wage=new_wage,
            income=new_income,
            hours_worked=jnp.where(new_employed, 40.0, 0.0),
        )

        return state.replace(agents=new_agents)


class ConsumptionMechanism(eqx.Module):
    """Consumption decision based on wealth and income."""

    base_consumption_rate: float = 0.7
    wealth_effect: float = 0.02

    @property
    def name(self) -> str:
        return "consumption"

    def apply(self, state: EconomicState, **kwargs) -> EconomicState:
        del kwargs
        agents = state.agents
        active = agents.active.astype(jnp.float32)

        income_consumption = agents.income * agents.consumption_preference
        wealth_consumption = agents.wealth * self.wealth_effect

        consumption = (income_consumption + wealth_consumption) * active
        consumption = jnp.maximum(consumption, 0.0)

        max_consumption = agents.wealth + agents.income
        consumption = jnp.minimum(consumption, max_consumption)

        new_wealth = agents.wealth + agents.income - consumption

        new_agents = agents.replace(consumption=consumption, wealth=new_wealth)
        return state.replace(agents=new_agents)


class SavingsMechanism(eqx.Module):
    """Savings and interest accumulation."""

    @property
    def name(self) -> str:
        return "savings"

    def apply(self, state: EconomicState, **kwargs) -> EconomicState:
        del kwargs
        agents = state.agents
        policy = state.policy
        active = agents.active.astype(jnp.float32)

        savings = jnp.maximum(agents.wealth - agents.consumption, 0.0)
        interest = savings * policy.interest_rate / 12.0
        new_wealth = agents.wealth + interest * active

        new_agents = agents.replace(savings=savings, wealth=new_wealth)
        return state.replace(agents=new_agents)
