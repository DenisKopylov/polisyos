from typing import List

import jax

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.base import Mechanism
from polisyos.foundry.registry import create_mechanism
from polisyos.ir.contract import PolicyRequestIR
from polisyos.common.logger import logger


class CompositePolicy(Mechanism):
    """
    Контейнер, который выполняет список механизмов последовательно.
    S_0 -> Mech_1 -> S_1 -> Mech_2 -> S_2
    """

    steps: List[Mechanism]

    def __init__(self, mechanisms: List[Mechanism]):
        self.steps = mechanisms

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        # Прогоняем состояние через цепочку мер
        # (JAX unroll'ит этот цикл при компиляции, если список фиксирован)
        current_state = state
        current_key = key
        for mech in self.steps:
            # Для простоты пока используем один ключ,
            # в будущем можно расщеплять key внутри цикла
            current_key, step_key = jax.random.split(current_key)
            current_state, current_key = mech(current_state, step_key)
        return current_state, current_key


def compile_policy(ir: PolicyRequestIR, n_agents: int, n_firms: int = 0) -> Mechanism:
    """
    Превращает JSON-контракт (IR) в дифференцируемый объект JAX (Mechanism).
    """
    logger.info(f"⚙️ Compiling policy: {ir.project_name.en} ({len(ir.interventions)} interventions)")

    compiled_steps = []

    for intervention in ir.interventions:
        try:
            instance = create_mechanism(intervention, n_agents=n_agents, n_firms=n_firms)
            compiled_steps.append(instance)
            logger.info(f"  ✅ Compiled '{intervention.id}' -> {instance.__class__.__name__}")

        except TypeError as e:
            logger.error(f"  ❌ Failed to compile '{intervention.id}': {e}")
            raise ValueError(f"Parameter mismatch for {intervention.mechanism_type}: {e}")

    return CompositePolicy(mechanisms=compiled_steps)
