"""Public agent sim distribution mechanisms module API."""

from __future__ import annotations

import chex
import jax.numpy as jnp
from jaxtyping import Array

from polisyos.foundry.agent_sim.distributions import compute_ranks_hard
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


class DistributionAwareTaxMechanism(Mechanism):
    """Distribution aware tax mechanism public type."""

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="distribution_aware_tax",
            reads=frozenset(
                {
                    "agents.income",
                    "agents.active",
                    "distributions.income_ranks",
                }
            ),
            writes=frozenset({"agents.income"}),
            parameters={"base_rate": float, "progressivity": float},
            stochastic=False,
        )

    def __init__(
        self,
        *,
        base_rate: float = 0.15,
        progressivity: float = 0.3,
        use_cached_ranks: bool = True,
    ):
        self.base_rate = base_rate
        self.progressivity = progressivity
        self.use_cached_ranks = use_cached_ranks

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del rng_key, fidelity
        agents = state.agents
        active = agents.active
        if self.use_cached_ranks:
            income_ranks = state.distributions.income_ranks
        else:
            income_ranks = compute_ranks_hard(agents.income, active)

        effective_rate = self.base_rate + self.progressivity * income_ranks
        effective_rate = jnp.clip(effective_rate, 0.0, 1.0)
        tax = agents.income * effective_rate
        post_tax_income = jnp.where(active, agents.income - tax, agents.income)

        new_agents = agents.replace(income=post_tax_income)

        active_count = jnp.sum(active)
        safe_count = jnp.maximum(active_count, 1.0)
        top_mask = (income_ranks >= 0.9) & active
        top_count = jnp.sum(top_mask)
        safe_top = jnp.maximum(top_count, 1.0)
        metrics = {
            "total_tax": jnp.sum(tax * active),
            "mean_effective_rate": jnp.sum(effective_rate * active) / safe_count,
            "top_10_rate": jnp.sum(effective_rate * top_mask) / safe_top,
        }

        return state.replace(agents=new_agents), metrics


class TargetedTransferMechanism(Mechanism):
    """Targeted transfer mechanism public type."""

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="targeted_transfer",
            reads=frozenset(
                {
                    "agents.income",
                    "agents.active",
                    "distributions.income_ranks",
                }
            ),
            writes=frozenset({"agents.income"}),
            parameters={"total_budget": float, "target_percentile": float},
            stochastic=False,
        )

    def __init__(
        self,
        *,
        total_budget: float = 1000.0,
        target_percentile: float = 0.3,
        transfer_formula: str = "uniform",
    ):
        self.total_budget = total_budget
        self.target_percentile = target_percentile
        self.transfer_formula = transfer_formula

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del rng_key, fidelity
        agents = state.agents
        active = agents.active
        income_ranks = state.distributions.income_ranks

        eligible = (income_ranks < self.target_percentile) & active
        n_eligible = jnp.sum(eligible)

        if self.transfer_formula == "uniform":
            transfer_per_agent = self.total_budget / (jnp.maximum(n_eligible, 1.0))
            transfers = jnp.where(eligible, transfer_per_agent, 0.0)
        elif self.transfer_formula == "inverse_rank":
            denom = jnp.maximum(self.target_percentile, 1e-6)
            inverse_rank = (self.target_percentile - income_ranks) / denom
            inverse_rank = jnp.where(eligible, inverse_rank, 0.0)
            total_weight = jnp.sum(inverse_rank)
            transfers = self.total_budget * inverse_rank / (total_weight + 1e-8)
        else:
            raise ValueError(f"Unknown transfer formula: {self.transfer_formula}")

        new_income = jnp.where(active, agents.income + transfers, agents.income)
        new_agents = agents.replace(income=new_income)

        safe_count = jnp.maximum(n_eligible, 1.0)
        metrics = {
            "n_recipients": n_eligible,
            "total_transferred": jnp.sum(transfers),
            "mean_transfer": jnp.sum(transfers) / safe_count,
        }

        return state.replace(agents=new_agents), metrics


class RelativeConsumptionMechanism(Mechanism):
    """Relative consumption mechanism public type."""

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="relative_consumption",
            reads=frozenset(
                {
                    "agents.consumption",
                    "agents.active",
                    "distributions.wealth_ranks",
                    "distributions.consumption_quantiles",
                }
            ),
            writes=frozenset({"agents.utility_adjustment"}),
            parameters={"comparison_intensity": float, "reference_type": str},
            stochastic=False,
        )

    def __init__(
        self,
        *,
        comparison_intensity: float = 0.2,
        reference_type: str = "local_quantile",
    ):
        self.comparison_intensity = comparison_intensity
        self.reference_type = reference_type

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        del rng_key, fidelity
        agents = state.agents
        active = agents.active
        consumption = agents.consumption
        quantiles = state.distributions.consumption_quantiles

        if self.reference_type == "mean":
            ref_value = jnp.sum(consumption * active) / jnp.maximum(jnp.sum(active), 1.0)
            reference = jnp.broadcast_to(ref_value, consumption.shape)
        elif self.reference_type == "median":
            median_idx = int(quantiles.shape[0] // 2)
            reference = jnp.broadcast_to(quantiles[median_idx], consumption.shape)
        elif self.reference_type == "local_quantile":
            n_quantiles = quantiles.shape[0]
            indices = jnp.clip(
                (state.distributions.wealth_ranks * n_quantiles).astype(jnp.int32),
                0,
                n_quantiles - 1,
            )
            reference = quantiles[indices]
        else:
            raise ValueError(f"Unknown reference type: {self.reference_type}")

        gap = jnp.maximum(reference - consumption, 0.0)
        utility_adjustment = -self.comparison_intensity * gap
        utility_adjustment = jnp.where(active, utility_adjustment, agents.utility_adjustment)
        new_agents = agents.replace(utility_adjustment=utility_adjustment)

        active_count = jnp.sum(active)
        safe_count = jnp.maximum(active_count, 1.0)
        metrics = {
            "mean_gap": jnp.sum(gap * active) / safe_count,
            "frac_below_reference": jnp.sum((consumption < reference) * active) / safe_count,
            "mean_utility_adjustment": jnp.sum(utility_adjustment * active) / safe_count,
        }

        return state.replace(agents=new_agents), metrics
