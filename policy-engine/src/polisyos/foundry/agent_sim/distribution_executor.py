from __future__ import annotations

from typing import Any, Iterable

from polisyos.foundry.agent_sim.distributions import (
    DistributionConfig,
    maybe_update_distributions,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.mechanism import Mechanism
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.types import FidelityLevel


class DistributionAwareExecutor(PureExecutor):
    def __init__(
        self,
        mechanisms: Iterable[Mechanism],
        *,
        distribution_config: DistributionConfig,
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

    def step(
        self,
        state: GlobalState,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
    ) -> tuple[GlobalState, dict[str, Any]]:
        state = maybe_update_distributions(state, self.distribution_config)
        state, metrics = super().step(state, fidelity)
        metrics.update(
            {
                "gini_wealth": state.distributions.gini_wealth,
                "gini_income": state.distributions.gini_income,
                "top_10_share": state.distributions.top_10_share,
                "bottom_50_share": state.distributions.bottom_50_share,
            }
        )
        return state, metrics


def create_distribution_aware_executor(
    mechanisms: Iterable[Mechanism],
    distribution_config: DistributionConfig,
    *,
    prng_config: dict[str, int] | None = None,
    aggregate_every: int | None = None,
    compute_gini: bool = False,
) -> DistributionAwareExecutor:
    return DistributionAwareExecutor(
        mechanisms,
        distribution_config=distribution_config,
        prng_config=prng_config,
        aggregate_every=aggregate_every,
        compute_gini=compute_gini,
    )
