"""Public agent sim mechanism module API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

import chex
from jaxtyping import Array

from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


class MechanismSpec(NamedTuple):
    """Declare what a mechanism reads, writes, and samples inside executor scheduling."""

    name: str
    reads: frozenset[str]
    writes: frozenset[str]
    parameters: dict[str, type]
    stochastic: bool


class Mechanism(ABC):
    """Mechanism public type."""

    @property
    @abstractmethod
    def spec(self) -> MechanismSpec:
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey | None,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, Array]]:
        raise NotImplementedError
