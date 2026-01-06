from abc import abstractmethod

import equinox as eqx
import jax

from src.domain.state import GlobalState
from src.foundry.types import FidelityLevel  # <--- Импорт


class Mechanism(eqx.Module):
    """
    Базовый класс механизма с поддержкой уровня точности.
    """
    # По умолчанию работаем в режиме потоков (самый быстрый и дифференцируемый)
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID

    @abstractmethod
    def __call__(self, state: GlobalState, key: jax.Array) -> GlobalState:
        """Применяет механику к состоянию."""
        pass

    def invariants(self, state: GlobalState) -> bool:
        """
        Проверка физической корректности (MUST по ТЗ).
        Должна возвращать True, если состояние валидно.
        Может использоваться в debug-режиме или Assert-нодах.
        """
        return True
