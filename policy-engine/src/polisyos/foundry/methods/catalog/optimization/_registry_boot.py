from __future__ import annotations

from typing import Sequence

from .io_model import LeontiefInputOutput
from .lp import ResourceLP
from .milp import BudgetMILP


def register_optimization_methods() -> Sequence[type]:
    return (
        BudgetMILP,
        ResourceLP,
        LeontiefInputOutput,
    )


__all__ = ["register_optimization_methods"]
