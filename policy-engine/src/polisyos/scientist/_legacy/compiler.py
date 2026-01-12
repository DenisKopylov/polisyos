from __future__ import annotations

import warnings
from typing import List

import jax

from polisyos.common.logger import logger
from polisyos.foundry.base import Mechanism
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.registry import create_mechanism
from polisyos.ir.contract import PolicyRequestIR
from polisyos.scientist import deprecated_import

deprecated_import(
    "polisyos.scientist.orchestrator.compiler (PolicyRequestIR) is deprecated; use Surface IR."
)


class CompositePolicy(Mechanism):
    steps: List[Mechanism]

    def __init__(self, mechanisms: List[Mechanism]):
        self.steps = mechanisms

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        current_state = state
        current_key = key
        for mech in self.steps:
            current_key, step_key = jax.random.split(current_key)
            current_state, current_key = mech(current_state, step_key)
        return current_state, current_key


def compile_policy(ir: PolicyRequestIR, n_agents: int, n_firms: int = 0) -> Mechanism:
    warnings.warn(
        "compile_policy(PolicyRequestIR) is legacy; migrate to PolicySurfaceIR and new compiler.",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.info(f"⚙️ Compiling policy: {ir.project_name.en} ({len(ir.interventions)} interventions)")
    compiled_steps = []
    for intervention in ir.interventions:
        try:
            instance = create_mechanism(intervention, n_agents=n_agents, n_firms=n_firms)
            compiled_steps.append(instance)
            logger.info(f"  ✅ Compiled '{intervention.id}' -> {instance.__class__.__name__}")
        except TypeError as exc:
            logger.error(f"  ❌ Failed to compile '{intervention.id}': {exc}")
            raise ValueError(f"Parameter mismatch for {intervention.mechanism_type}: {exc}")
    return CompositePolicy(mechanisms=compiled_steps)
