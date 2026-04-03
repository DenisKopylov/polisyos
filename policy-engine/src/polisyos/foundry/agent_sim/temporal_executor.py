"""Public agent sim temporal executor module API."""
from __future__ import annotations

from typing import Iterable

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.mechanism import Mechanism
from polisyos.foundry.agent_sim.mechanisms import ConsumptionMechanism
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism


def create_temporal_executor(
    actor_critic: ActorCritic,
    *,
    horizon: int = 256,
    min_consumption: float = 0.01,
    include_expectations: bool = True,
    base_mechanisms: Iterable[Mechanism] | None = None,
    prng_config: dict[str, int] | None = None,
    aggregate_every: int | None = None,
    compute_gini: bool = False,
) -> PureExecutor:
    """Create temporal executor."""
    mechanisms = list(base_mechanisms) if base_mechanisms is not None else []
    replaced = False
    for idx, mech in enumerate(mechanisms):
        if isinstance(mech, (ConsumptionMechanism, TemporalConsumptionMechanism)):
            mechanisms[idx] = TemporalConsumptionMechanism(
                actor_critic=actor_critic,
                horizon=horizon,
                min_consumption=min_consumption,
                include_expectations=include_expectations,
            )
            replaced = True
    if not replaced:
        mechanisms.append(
            TemporalConsumptionMechanism(
                actor_critic=actor_critic,
                horizon=horizon,
                min_consumption=min_consumption,
                include_expectations=include_expectations,
            )
        )
    return PureExecutor(
        mechanisms,
        prng_config=prng_config,
        aggregate_every=aggregate_every,
        compute_gini=compute_gini,
    )
