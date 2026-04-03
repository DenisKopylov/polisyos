"""Public economics plugin module API."""
from __future__ import annotations

from typing import Callable, Sequence

import jax
import jax.numpy as jnp

from polisyos.foundry.plugins.core import (
    DomainConfig,
    DomainPlugin,
    MechanismProtocol,
    ObjectiveProtocol,
    PluginCapability,
    PluginMetadata,
    RewardProtocol,
)
from polisyos.foundry.plugins.economics.mechanisms import (
    ConsumptionMechanism,
    LaborMarketMechanism,
    SavingsMechanism,
    TaxationMechanism,
    TransferMechanism,
)
from polisyos.foundry.plugins.economics.objectives import (
    GDPObjective,
    GiniObjective,
    RawlsianWelfare,
    SocialWelfareObjective,
    UnemploymentObjective,
    UtilitarianWelfare,
)
from polisyos.foundry.plugins.economics.rewards import EconomicReward
from polisyos.foundry.plugins.economics.state import EconomicState


class EconomicsPlugin(DomainPlugin[EconomicState]):
    """Economics domain plugin."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="economics",
            version="1.0.0",
            description="Economic simulation domain with heterogeneous agents",
            author="PolisyOS Team",
            capabilities=(
                PluginCapability.AGENTS,
                PluginCapability.MECHANISMS,
                PluginCapability.REWARDS,
                PluginCapability.OBJECTIVES,
                PluginCapability.OBSERVATIONS,
                PluginCapability.VISUALIZATION,
            ),
            tags=("economics", "macro", "policy", "inequality"),
        )

    def __init__(self):
        self._custom_objectives: dict[str, ObjectiveProtocol] = {}

    def create_initial_state(
        self,
        config: DomainConfig,
        rng_key: jax.Array,
    ) -> EconomicState:
        errors = self.validate_config(config)
        if errors:
            raise ValueError(f"Invalid config: {errors}")

        seed = int(jax.random.randint(rng_key, (), 0, 2**31 - 1))
        state = EconomicState.empty(
            n_agents=config.n_agents,
            seed=seed,
            max_agents=config.max_agents,
        )

        if config.parameters:
            state = _apply_policy_params(state, config.parameters)

        return state

    def get_mechanisms(self) -> Sequence[MechanismProtocol[EconomicState]]:
        return [
            LaborMarketMechanism(),
            TaxationMechanism(),
            TransferMechanism(),
            ConsumptionMechanism(),
            SavingsMechanism(),
        ]

    def get_reward_function(self) -> RewardProtocol[EconomicState]:
        return EconomicReward()

    def get_objectives(self) -> dict[str, ObjectiveProtocol[EconomicState]]:
        objectives: dict[str, ObjectiveProtocol[EconomicState]] = {
            "gdp": GDPObjective(),
            "gini": GiniObjective(),
            "unemployment": UnemploymentObjective(),
            "social_welfare": SocialWelfareObjective(),
            "utilitarian": UtilitarianWelfare(),
            "rawlsian": RawlsianWelfare(),
        }
        objectives.update(self._custom_objectives)
        return objectives

    def get_observation_builder(self) -> Callable[[EconomicState], jnp.ndarray]:
        def build_obs(state: EconomicState) -> jnp.ndarray:
            return state.agents.get_observations()

        return build_obs

    def get_visualizations(self) -> dict[str, Callable]:
        return {
            "wealth_distribution": self._viz_wealth_distribution,
            "lorenz_curve": self._viz_lorenz_curve,
            "employment_by_skill": self._viz_employment_by_skill,
        }

    def validate_config(self, config: DomainConfig) -> list[str]:
        errors: list[str] = []

        if config.n_agents < 10:
            errors.append("n_agents must be at least 10 for meaningful statistics")

        params = config.parameters
        if "tax_rate" in params:
            if not 0.0 <= params["tax_rate"] <= 1.0:
                errors.append("tax_rate must be between 0 and 1")

        return errors

    def register_objective(self, name: str, objective: ObjectiveProtocol) -> None:
        self._custom_objectives[name] = objective

    def _viz_wealth_distribution(self, state: EconomicState, ax=None):
        import matplotlib.pyplot as plt

        if ax is None:
            _, ax = plt.subplots()

        wealth = state.agents.wealth[state.agents.active]
        ax.hist(wealth, bins=50, density=True, alpha=0.7)
        ax.set_xlabel("Wealth")
        ax.set_ylabel("Density")
        ax.set_title(
            f"Wealth Distribution (Gini: {float(state.distributions.gini_wealth):.3f})"
        )

        return ax

    def _viz_lorenz_curve(self, state: EconomicState, ax=None):
        import matplotlib.pyplot as plt
        import numpy as np

        if ax is None:
            _, ax = plt.subplots()

        wealth = np.array(state.agents.wealth[state.agents.active])
        sorted_wealth = np.sort(wealth)
        cumulative = np.cumsum(sorted_wealth) / np.sum(sorted_wealth)
        pop_share = np.arange(1, len(cumulative) + 1) / len(cumulative)

        ax.plot(pop_share, cumulative, "b-", label="Lorenz Curve")
        ax.plot([0, 1], [0, 1], "k--", label="Perfect Equality")
        ax.fill_between(pop_share, pop_share, cumulative, alpha=0.3)
        ax.set_xlabel("Cumulative Population Share")
        ax.set_ylabel("Cumulative Wealth Share")
        ax.legend()

        return ax

    def _viz_employment_by_skill(self, state: EconomicState, ax=None):
        import matplotlib.pyplot as plt
        import numpy as np

        if ax is None:
            _, ax = plt.subplots()

        agents = state.agents
        active = agents.active

        skill = np.array(agents.skill_level[active])
        employed = np.array(agents.employed[active])

        bins = np.linspace(0, 1, 11)
        bin_indices = np.digitize(skill, bins) - 1

        employment_rates = []
        for i in range(len(bins) - 1):
            mask = bin_indices == i
            if np.sum(mask) > 0:
                employment_rates.append(np.mean(employed[mask]))
            else:
                employment_rates.append(0.0)

        ax.bar(bins[:-1] + 0.05, employment_rates, width=0.08)
        ax.set_xlabel("Skill Level")
        ax.set_ylabel("Employment Rate")
        ax.set_title("Employment by Skill Level")

        return ax


def _apply_policy_params(state: EconomicState, params: dict[str, float]) -> EconomicState:
    if not hasattr(state, "policy"):
        return state

    policy = state.policy
    updates = {}
    for key, value in params.items():
        if hasattr(policy, key):
            updates[key] = jnp.array(value)

    if updates:
        policy = policy.replace(**updates)
        return state.replace(policy=policy)

    return state
