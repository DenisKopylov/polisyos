"""Typed, optional observations of the actual ProgramGraph execution seam.

An observer is diagnostic input to one explicitly selected execution. Foundry
retains the callable and invokes it itself; an observer neither supplies a
patch nor establishes source, execution, or publication authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from polisyos.core.artifacts import ArtifactRef


@dataclass(frozen=True, slots=True)
class PreparedProgramGraphMethodCall:
    """Expose the exact bounded inputs and held providers of a method call.

    Preparation alone is not an execution witness. An actual observer receives
    this same content immediately before the held backend call is invoked.
    """

    plan_index: int
    node_id: str
    step: int
    method_fqn: str
    method_version: str
    method_abi_digest: str
    input_slot_sources: Mapping[str, str]
    input_values: Mapping[str, Any]
    resolved_parameters: Mapping[str, Any]
    root_seed: int
    seed: int
    key_words: tuple[int, ...]
    rng_state: Mapping[str, Any]
    selected_call: Callable[..., Any]
    provider_callables: Mapping[str, Callable[..., Any]]


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


class ProgramGraphMethodExecutionObserver(ProgramGraphExecutionObserver, Protocol):
    """Opt into method observations without changing the legacy observer ABI."""

    def method_started(
        self,
        *,
        step: int,
        plan_index: int,
        node_id: str,
        prepared_call: PreparedProgramGraphMethodCall,
    ) -> None:
        """Observe actual held NumPy call inputs before their sole invocation."""
        ...

    def method_finished(
        self, *, step: int, plan_index: int, node_id: str, status: Literal["returned", "raised"]
    ) -> None:
        """Observe whether the held method call returned or raised."""
        ...
