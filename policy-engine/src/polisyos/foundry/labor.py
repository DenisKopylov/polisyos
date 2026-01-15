from __future__ import annotations

from typing import Any

import jax
import jax.numpy as jnp

from polisyos.foundry.base import ComplexMechanism, PatchMap
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.types import FidelityLevel


class LaborMarketMechanism(ComplexMechanism):
    employment_threshold: jnp.ndarray

    def __init__(
        self,
        *,
        employment_threshold: float = 0.5,
        fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID,
        debug_mode: bool = False,
        **kwargs: Any,
    ):
        self.employment_threshold = jnp.array(employment_threshold)
        self.fidelity = fidelity
        self.debug_mode = debug_mode

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ) -> tuple[PatchMap, jax.Array]:
        agents = state.agents
        firms = state.firms
        n_agents = agents.size
        n_firms = firms.size

        employment_probs = jax.random.uniform(key, shape=(n_agents,))
        new_is_employed = employment_probs < self.employment_threshold
        firm_choices = jax.random.randint(key, shape=(n_agents,), minval=0, maxval=n_firms)
        new_employer_ids = jnp.where(new_is_employed, firm_choices, -1)

        employed_firm_ids = jnp.where(new_is_employed, new_employer_ids, 0)
        labor_counts = jax.ops.segment_sum(jnp.ones_like(employed_firm_ids), employed_firm_ids, n_firms)

        employed_firm_ids_safe = jnp.where(new_is_employed, new_employer_ids, 0)
        safe_firm_ids = jnp.clip(employed_firm_ids_safe, 0, n_firms - 1)
        wage_rates = firms.wage_offer[safe_firm_ids] * agents.skill_level
        new_income = jnp.where(new_is_employed, wage_rates, 0.0)

        if target_mask is not None:
            if target_mask.shape[0] != n_agents:
                raise ValueError("LaborMarketMechanism target_mask must match agent count")
            new_is_employed = jnp.where(target_mask, new_is_employed, agents.is_employed)
            new_employer_ids = jnp.where(target_mask, new_employer_ids, agents.employer_id)
            new_income = jnp.where(target_mask, new_income, agents.income)
            employed_firm_ids = jnp.where(new_is_employed, new_employer_ids, 0)
            labor_counts = jax.ops.segment_sum(
                jnp.ones_like(employed_firm_ids), employed_firm_ids, n_firms
            )

        if self.debug_mode:
            employed_rate = jnp.mean(new_is_employed)
            jax.debug.print("LaborMarket employed_rate={r}", r=employed_rate)

        income_delta = new_income - agents.income
        return (
            {
                "agents.employer_id": [{"value": new_employer_ids}],
                "agents.is_employed": [{"value": new_is_employed}],
                "agents.income": [{"delta": income_delta}],
                "firms.labor_count": [{"value": labor_counts}],
            },
            key,
        )
