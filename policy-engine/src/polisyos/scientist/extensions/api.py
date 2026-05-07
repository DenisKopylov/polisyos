"""Public contract markers for Scientist extension plugins."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from polisyos.core.components import (
    ENTRY_POINT_GROUP_SCIENTIST_GOVERNANCE_PASSES,
    ENTRY_POINT_GROUP_SCIENTIST_NODES,
)

SCIENTIST_GOVERNANCE_PASS_ABI = ">=1.0.0,<2.0.0"
SCIENTIST_NODE_ABI = ">=1.0.0,<2.0.0"
SCIENTIST_GOVERNANCE_PASSES_ENTRY_POINT_GROUP = ENTRY_POINT_GROUP_SCIENTIST_GOVERNANCE_PASSES
SCIENTIST_NODES_ENTRY_POINT_GROUP = ENTRY_POINT_GROUP_SCIENTIST_NODES


@runtime_checkable
class ScientistGovernancePassPlugin(Protocol):
    """Entry-point plugin that creates a Scientist governance pass."""

    def __call__(self) -> object:
        ...


@runtime_checkable
class ScientistNodePlugin(Protocol):
    """Component-style plugin that creates a Scientist DAG node."""

    @property
    def metadata(self) -> object:
        ...

    def create(self) -> object:
        ...


__all__ = [
    "SCIENTIST_GOVERNANCE_PASS_ABI",
    "SCIENTIST_GOVERNANCE_PASSES_ENTRY_POINT_GROUP",
    "SCIENTIST_NODE_ABI",
    "SCIENTIST_NODES_ENTRY_POINT_GROUP",
    "ScientistGovernancePassPlugin",
    "ScientistNodePlugin",
]
