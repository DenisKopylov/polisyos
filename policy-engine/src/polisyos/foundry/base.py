from abc import abstractmethod
from typing import Any

import equinox as eqx
import jax

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.types import FidelityLevel


PatchRecord = dict[str, Any]
PatchMap = dict[str, list[PatchRecord]]


class Mechanism(eqx.Module):
    """
    Базовый класс механизма с поддержкой уровня точности и debug-режима.
    """

    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID
    debug_mode: bool = False

    @abstractmethod
    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        """Инициализирует состояние механизма (если нужно) и возвращает новый ключ."""
        raise NotImplementedError

    @abstractmethod
    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ) -> tuple[PatchMap, jax.Array]:
        """
        Patch-first path. Must return per-slot patch records (delta/value/new_value, etc.).
        """
        raise NotImplementedError

    def invariants(self, state: GlobalState) -> bool:
        """
        Проверка физической корректности (MUST по ТЗ).
        Должна возвращать True, если состояние валидно.
        Может использоваться в debug-режиме или Assert-нодах.
        """
        return True


class ComplexMechanism(Mechanism):
    """
    Marker for mechanisms that run complex computations but still emit patches only.
    """
