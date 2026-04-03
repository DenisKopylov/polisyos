"""World-graph predicate ids shared by claim, provenance, and relation exports."""
from __future__ import annotations

from polisyos.ir.world.abi import EdgeKind

WORLD_KIND = "world.kind"
WORLD_LABEL = "world.label"
WORLD_ARTIFACT_ID = "world.artifact_id"
WORLD_PROPS_REF = "world.props_ref"
WORLD_REL_PREFIX = "world.rel."


def rel(edge_kind: EdgeKind | str) -> str:
    """Return the canonical world predicate id for a given edge kind."""
    value = edge_kind.value if isinstance(edge_kind, EdgeKind) else str(edge_kind)
    return f"{WORLD_REL_PREFIX}{value}"


__all__ = [
    "WORLD_ARTIFACT_ID",
    "WORLD_KIND",
    "WORLD_LABEL",
    "WORLD_PROPS_REF",
    "WORLD_REL_PREFIX",
    "rel",
]
