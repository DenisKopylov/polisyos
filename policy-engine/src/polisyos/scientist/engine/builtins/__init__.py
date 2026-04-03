"""Public engine builtins package API."""
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
    """Builtin nodes helper."""
    return [NoopNode(), SetStateNode(), EmitArtifactNode()]
