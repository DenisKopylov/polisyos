from abc import abstractmethod

import equinox as eqx
import jax

from src.domain.state import GlobalState


class Mechanism(eqx.Module):
    """
    Базовый класс для всех политик и экономических механизмов.
    Наследуемся от eqx.Module, чтобы JAX видел наши параметры.
    """

    @abstractmethod
    def __call__(self, state: GlobalState, key: jax.Array) -> GlobalState:
        """
        Применяет механику к состоянию мира.
        state_t -> state_t (или state_{t+1})
        """
        pass
