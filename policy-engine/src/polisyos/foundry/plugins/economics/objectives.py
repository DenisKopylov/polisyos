"""Public economics objectives module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import jax.numpy as jnp

from polisyos.foundry.plugins.economics.state import EconomicState
from polisyos.foundry.social_weights import (
    prepare_social_weight_schedule,
    social_weighted_resource,
)


class GDPObjective:
    """Maximize GDP."""

    @property
    def maximize(self) -> bool:
        return True

    def evaluate(self, state: EconomicState) -> jnp.ndarray:
        return state.aggregates.gdp


class GiniObjective:
    """Minimize Gini coefficient (inequality)."""

    @property
    def maximize(self) -> bool:
        return False

    def evaluate(self, state: EconomicState) -> jnp.ndarray:
        return state.distributions.gini_wealth


class UnemploymentObjective:
    """Minimize unemployment rate."""

    @property
    def maximize(self) -> bool:
        return False

    def evaluate(self, state: EconomicState) -> jnp.ndarray:
        return state.aggregates.unemployment_rate


class SocialWelfareObjective:
    """Composite social welfare function."""

    weights: dict[str, float]

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        *,
        social_weight_ref: str | None = None,
        social_weight_manifest: Mapping[str, Any] | None = None,
        social_weight_scale: float = 1.0,
    ):
        self.weights = (
            dict(weights)
            if weights is not None
            else {
                "gdp": 1.0,
                "neg_gini": 0.5,
                "neg_unemployment": 0.3,
            }
        )
        self.social_weight_schedule = prepare_social_weight_schedule(
            social_weight_ref=social_weight_ref,
            social_weight_manifest=social_weight_manifest,
        )
        self.social_weight_scale = float(social_weight_scale)

    @property
    def maximize(self) -> bool:
        return True

    def evaluate(self, state: EconomicState) -> jnp.ndarray:
        welfare = jnp.array(0.0)

        if "gdp" in self.weights:
            welfare = welfare + self.weights["gdp"] * state.aggregates.gdp / 1e9

        if "neg_gini" in self.weights:
            welfare = welfare - self.weights["neg_gini"] * state.distributions.gini_wealth

        if "neg_unemployment" in self.weights:
            welfare = welfare - (
                self.weights["neg_unemployment"] * state.aggregates.unemployment_rate
            )

        if "bottom_50_share" in self.weights:
            welfare = welfare + (
                self.weights["bottom_50_share"] * state.distributions.bottom_50_share
            )

        if self.social_weight_schedule is not None:
            welfare = welfare + (
                self.social_weight_scale
                * self.weights.get("social_weighted_consumption", 1.0)
                * social_weighted_resource(
                    state.agents.consumption,
                    state.agents.income,
                    state.agents.active,
                    self.social_weight_schedule,
                )
            )

        return welfare


class UtilitarianWelfare:
    """Sum of individual utilities (Benthamite)."""

    @property
    def maximize(self) -> bool:
        return True

    def evaluate(self, state: EconomicState) -> jnp.ndarray:
        agents = state.agents
        active = agents.active.astype(jnp.float32)
        utility = jnp.log(agents.consumption + 1.0) * active
        return jnp.sum(utility)


class RawlsianWelfare:
    """Maximize minimum utility (maximin)."""

    @property
    def maximize(self) -> bool:
        return True

    def evaluate(self, state: EconomicState) -> jnp.ndarray:
        agents = state.agents
        active = agents.active

        utility = jnp.log(agents.consumption + 1.0)
        utility = jnp.where(active, utility, jnp.inf)

        return jnp.min(utility)
