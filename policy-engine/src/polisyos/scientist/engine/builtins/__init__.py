"""Always-available engine builtins for no-op, state mutation, and artifact emission."""

from __future__ import annotations

from polisyos.scientist.engine.builtins.emit_artifact import EmitArtifactNode
from polisyos.scientist.engine.builtins.noop import NoopNode
from polisyos.scientist.engine.builtins.set_state import SetStateNode
from polisyos.scientist.engine.protocol import Node

__all__ = [
    "EmitArtifactNode",
    "NoopNode",
    "SetStateNode",
    "builtin_nodes",
]


def builtin_nodes() -> list[Node]:
    """Return the engine-level builtin nodes used to bootstrap a minimal registry."""
    return [NoopNode(), SetStateNode(), EmitArtifactNode()]
