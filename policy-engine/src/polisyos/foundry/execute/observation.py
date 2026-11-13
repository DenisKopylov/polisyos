"""Typed, optional observations of the actual ProgramGraph execution seam.

An observer is diagnostic input to one explicitly selected execution. Foundry
retains the callable and invokes it itself; an observer neither supplies a
patch nor establishes source, execution, or publication authority.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol

from polisyos.core.artifacts import ArtifactRef


class ProgramGraphExecutionObserver(Protocol):
    """Observe one graph step and its actual mechanism calls without replacing them."""

    def graph_started(
        self,
        *,
        step: int,
        seed: int,
        base_state_ref: ArtifactRef | None,
        nodes: tuple[tuple[str, str, str | None], ...],
    ) -> None:
        """Observe the selected plan's ordered node denominator."""
        ...

    def mechanism_started(
        self,
        *,
        step: int,
        plan_index: int,
        node_id: str,
        selected_call: Callable[..., object],
        state: object,
        key: object,
        target_mask: object,
    ) -> None:
        """Observe the exact bound callable and arguments before its invocation."""
        ...

    def mechanism_finished(
        self, *, step: int, plan_index: int, node_id: str, status: Literal["returned", "raised"]
    ) -> None:
        """Observe whether that actual invocation returned or raised."""
        ...

    def node_finished(
        self,
        *,
        step: int,
        plan_index: int,
        node_id: str,
        status: Literal["succeeded", "skipped", "failed"],
    ) -> None:
        """Observe the terminal state of one selected plan node."""
        ...

    def graph_finished(self, *, step: int, seed: int) -> None:
        """Observe the graph owner's completion of its selected step."""
        ...
