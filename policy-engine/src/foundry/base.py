from abc import abstractmethod

import equinox as eqx
import jax

from src.domain.state import GlobalState
from src.foundry.types import FidelityLevel


class Mechanism(eqx.Module):
    """
    Базовый класс механизма с поддержкой уровня точности и debug-режима.
    """

    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID
    debug_mode: bool = False

    @abstractmethod
    def init_state(self, state: GlobalState, key: jax.Array) -> GlobalState:
        """Инициализирует состояние механизма (если нужно)."""
        raise NotImplementedError

    @abstractmethod
    def step(self, state: GlobalState, key: jax.Array) -> GlobalState:
        """Один шаг механизма."""
        raise NotImplementedError

    def __call__(self, state: GlobalState, key: jax.Array) -> GlobalState:
        if self.debug_mode:
            with jax.disable_jit():
                return self.step(state, key)
        return self.step(state, key)

    def invariants(self, state: GlobalState) -> bool:
        """
        Проверка физической корректности (MUST по ТЗ).
        Должна возвращать True, если состояние валидно.
        Может использоваться в debug-режиме или Assert-нодах.
        """
        return True
