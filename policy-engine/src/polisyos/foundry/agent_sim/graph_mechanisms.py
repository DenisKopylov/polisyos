from __future__ import annotations

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array

from polisyos.foundry.agent_sim.graphs import aggregate_messages
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


class SocialInfluenceMechanism(Mechanism):
    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="social_influence",
            reads=frozenset({"agents.consumption", "agents.active", "graph.edges"}),
            writes=frozenset({"agents.consumption_target"}),
            parameters={"influence_strength": float, "aggregation": str},
            stochastic=False,
        )

    def __init__(self, *, influence_strength: float = 0.3, aggregation: str = "mean"):
        self.influence_strength = influence_strength
        self.aggregation = aggregation

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del rng_key, fidelity
        agents = state.agents
        edges = state.graph.edges
        active = agents.active

        neighbor_consumption = aggregate_messages(
            agents.consumption[:, None],
            edges,
            aggregation=self.aggregation,
            active=active,
        ).squeeze(-1)

        consumption_target = (
            (1.0 - self.influence_strength) * agents.consumption
            + self.influence_strength * neighbor_consumption
        )
        consumption_target = jnp.where(active, consumption_target, agents.consumption_target)
        new_agents = agents.replace(consumption_target=consumption_target)

        active_f = active.astype(jnp.float32)
        count = jnp.maximum(jnp.sum(active_f), 1.0)
        mean_neighbor = jnp.sum(neighbor_consumption * active_f) / count
        mean_self = jnp.sum(agents.consumption * active_f) / count
        cov = jnp.sum(
            (agents.consumption - mean_self)
            * (neighbor_consumption - mean_neighbor)
            * active_f
        ) / count
        var_self = jnp.sum((agents.consumption - mean_self) ** 2 * active_f) / count
        var_neighbor = (
            jnp.sum((neighbor_consumption - mean_neighbor) ** 2 * active_f) / count
        )
        corr = cov / (jnp.sqrt(var_self * var_neighbor) + 1e-8)

        metrics = {
            "mean_neighbor_consumption": mean_neighbor,
            "consumption_correlation": corr,
        }
        return state.replace(agents=new_agents), metrics


class InformationDiffusionMechanism(Mechanism):
    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="information_diffusion",
            reads=frozenset({"agents.information_level", "agents.active", "graph.edges"}),
            writes=frozenset({"agents.information_level"}),
            parameters={"diffusion_rate": float, "decay_rate": float},
            stochastic=True,
        )

    def __init__(self, *, diffusion_rate: float = 0.2, decay_rate: float = 0.05):
        self.diffusion_rate = diffusion_rate
        self.decay_rate = decay_rate

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del fidelity
        agents = state.agents
        edges = state.graph.edges
        active = agents.active

        current_info = agents.information_level
        neighbor_max = aggregate_messages(
            current_info[:, None],
            edges,
            aggregation="max",
            active=active,
        ).squeeze(-1)
        info_gain = self.diffusion_rate * jnp.maximum(neighbor_max - current_info, 0.0)
        info_decay = self.decay_rate * current_info
        noise = 0.01 * jax.random.normal(rng_key, shape=current_info.shape)
        new_info = jnp.clip(current_info + info_gain - info_decay + noise, 0.0, 1.0)
        new_info = jnp.where(active, new_info, current_info)
        new_agents = agents.replace(information_level=new_info)

        metrics = {
            "mean_info_level": jnp.sum(new_info * active) / jnp.maximum(jnp.sum(active), 1.0),
            "info_spread": jnp.std(jnp.where(active, new_info, 0.0)),
            "fully_informed_frac": jnp.mean((new_info > 0.9) & active),
        }
        return state.replace(agents=new_agents), metrics


class NetworkLendingMechanism(Mechanism):
    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="network_lending",
            reads=frozenset(
                {"agents.wealth", "agents.income", "agents.active", "graph.edges"}
            ),
            writes=frozenset({"agents.wealth", "agents.debt"}),
            parameters={"max_loan_fraction": float, "interest_rate": float},
            stochastic=True,
        )

    def __init__(self, *, max_loan_fraction: float = 0.1, interest_rate: float = 0.05):
        self.max_loan_fraction = max_loan_fraction
        self.interest_rate = interest_rate

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del rng_key, fidelity
        agents = state.agents
        edges = state.graph.edges
        active = agents.active

        wants_to_borrow = (agents.wealth < agents.income * 2.0) & active
        can_lend = (agents.wealth > agents.income * 10.0) & active
        lender_wealth = jnp.where(can_lend, agents.wealth, 0.0)

        max_neighbor_wealth = aggregate_messages(
            lender_wealth[:, None],
            edges,
            aggregation="max",
            active=active,
        ).squeeze(-1)

        loan_amount = self.max_loan_fraction * max_neighbor_wealth
        loan_amount = jnp.where(wants_to_borrow, loan_amount, 0.0)

        new_wealth = agents.wealth + loan_amount
        new_debt = agents.debt + loan_amount * (1.0 + self.interest_rate)
        new_wealth = jnp.where(active, new_wealth, agents.wealth)
        new_debt = jnp.where(active, new_debt, agents.debt)
        new_agents = agents.replace(wealth=new_wealth, debt=new_debt)

        borrowers = loan_amount > 0
        borrower_count = jnp.sum(borrowers)
        metrics = {
            "total_loans": jnp.sum(loan_amount),
            "n_borrowers": borrower_count,
            "mean_loan_size": jnp.sum(loan_amount) / (borrower_count + 1e-8),
        }
        return state.replace(agents=new_agents), metrics


class LaborNetworkMechanism(Mechanism):
    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="labor_network",
            reads=frozenset(
                {"agents.employed", "agents.income", "agents.active", "graph.edges"}
            ),
            writes=frozenset({"agents.employed", "agents.income"}),
            parameters={"referral_probability": float},
            stochastic=True,
        )

    def __init__(self, *, referral_probability: float = 0.1):
        self.referral_probability = referral_probability

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del fidelity
        agents = state.agents
        edges = state.graph.edges
        active = agents.active

        unemployed = (~agents.employed) & active
        employed_neighbors = aggregate_messages(
            agents.employed.astype(jnp.float32)[:, None],
            edges,
            aggregation="mean",
            active=active,
        ).squeeze(-1)
        referral_prob = self.referral_probability * employed_neighbors
        random_vals = jax.random.uniform(rng_key, shape=agents.employed.shape)
        gets_job = unemployed & (random_vals < referral_prob)

        new_employed = agents.employed | gets_job
        neighbor_income = aggregate_messages(
            (agents.income * agents.employed.astype(jnp.float32))[:, None],
            edges,
            aggregation="mean",
            active=active,
        ).squeeze(-1)
        new_income = jnp.where(gets_job, neighbor_income, agents.income)
        new_employed = jnp.where(active, new_employed, agents.employed)
        new_income = jnp.where(active, new_income, agents.income)

        new_agents = agents.replace(employed=new_employed, income=new_income)
        metrics = {
            "new_jobs": jnp.sum(gets_job),
            "unemployment_rate": 1.0
            - jnp.sum(new_employed.astype(jnp.float32) * active)
            / jnp.maximum(jnp.sum(active), 1.0),
        }
        return state.replace(agents=new_agents), metrics
