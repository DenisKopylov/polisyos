"""Public contracts fidelity module API."""
from enum import Enum


class FidelityLevel(str, Enum):
    """Fidelity level public type."""
    SURROGATE_FLUID = "fluid"      # Непрерывные потоки (уравнения)
    RELAXED_DISCRETE = "relaxed"   # Сглаженные события (Softmax/Sigmoid)
    HARD_DISCRETE = "hard"         # Честная дискретная симуляция (без градиента)
