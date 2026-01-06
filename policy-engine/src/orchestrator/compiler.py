from typing import List

import jax

from src.domain.state import GlobalState
from src.foundry.base import Mechanism
from src.orchestrator.registry import get_mechanism_class
from src.policy_ir.contract import PolicyRequestIR
from src.utils.logger import logger


class CompositePolicy(Mechanism):
    """
    Контейнер, который выполняет список механизмов последовательно.
    S_0 -> Mech_1 -> S_1 -> Mech_2 -> S_2
    """

    steps: List[Mechanism]

    def __init__(self, mechanisms: List[Mechanism]):
        self.steps = mechanisms

    def __call__(self, state: GlobalState, key: jax.Array) -> GlobalState:
        # Прогоняем состояние через цепочку мер
        # (JAX unroll'ит этот цикл при компиляции, если список фиксирован)
        current_state = state
        for mech in self.steps:
            # Для простоты пока используем один ключ,
            # в будущем можно расщеплять key внутри цикла
            current_state = mech(current_state, key)
        return current_state


def compile_policy(ir: PolicyRequestIR, n_agents: int, n_firms: int = 0) -> Mechanism:
    """
    Превращает JSON-контракт (IR) в дифференцируемый объект JAX (Mechanism).
    """
    logger.info(f"⚙️ Compiling policy: {ir.project_name.en} ({len(ir.interventions)} interventions)")

    compiled_steps = []

    for intervention in ir.interventions:
        mech_cls = get_mechanism_class(intervention.mechanism_type)
        params = intervention.parameters

        try:
            # Магия: инициализируем класс параметрами из JSON
            # Важно: класс должен принимать именованные аргументы, совпадающие с JSON
            # Добавляем n_agents и n_firms для инициализации механизмов
            instance = mech_cls(n_agents=n_agents, n_firms=n_firms, **params)
            compiled_steps.append(instance)
            logger.info(f"  ✅ Compiled '{intervention.id}' -> {mech_cls.__name__}")

        except TypeError as e:
            logger.error(f"  ❌ Failed to compile '{intervention.id}': {e}")
            raise ValueError(f"Parameter mismatch for {intervention.mechanism_type}: {e}")

    return CompositePolicy(mechanisms=compiled_steps)
