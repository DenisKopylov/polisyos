"""Protocols that define the DES/ABM coupling boundary."""

from __future__ import annotations

from typing import Any, Protocol

import jax

from polisyos.foundry.contracts.mechanism import PatchMap
from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
from polisyos.foundry.coupling.messages import CouplingMessage


class DESKernel(Protocol):
    """Discrete-event kernel boundary for queue/resource dynamics."""

    def next_event_time(self, state_q: QueueRuntimeState) -> float:
        """Return the next DES event timestamp."""
        ...

    def advance_to(
        self,
        state_q: QueueRuntimeState,
        t: float,
        inbox: list[CouplingMessage] | tuple[CouplingMessage, ...],
        rng: jax.Array,
    ) -> tuple[QueueRuntimeState, list[CouplingMessage], PatchMap, dict[str, Any]]:
        """Advance DES state to `t`, consuming ABM intent messages."""
        ...


class ABMKernel(Protocol):
    """Agent-behavior kernel boundary for adaptive micro dynamics."""

    def advance(
        self,
        state_a: GlobalState,
        dt: float,
        inbox: list[CouplingMessage] | tuple[CouplingMessage, ...],
        rng: jax.Array,
    ) -> tuple[GlobalState, list[CouplingMessage], PatchMap, dict[str, Any]]:
        """Advance ABM state over a sync interval, emitting intent messages."""
        ...


class Coupler(Protocol):
    """Deterministic projection and merge layer between DES and ABM kernels."""

    def project_a_to_q(
        self,
        state: GlobalState,
        state_q: QueueRuntimeState,
        msgs_a: list[CouplingMessage] | tuple[CouplingMessage, ...],
    ) -> list[CouplingMessage]:
        """Translate agent intent messages into DES inbox messages."""
        ...

    def project_q_to_a(
        self,
        state: GlobalState,
        state_q: QueueRuntimeState,
        msgs_q: list[CouplingMessage] | tuple[CouplingMessage, ...],
    ) -> list[CouplingMessage]:
        """Translate DES outcomes into ABM inbox messages."""
        ...

    def merge(
        self,
        state: GlobalState,
        *,
        patches_q: PatchMap | None = None,
        patches_a: PatchMap | None = None,
        msgs_q: list[CouplingMessage] | tuple[CouplingMessage, ...] = (),
        time: float,
    ) -> tuple[GlobalState, dict[str, Any]]:
        """Merge same-time patches and queue outcomes into canonical state."""
        ...


__all__ = ["ABMKernel", "Coupler", "DESKernel"]
