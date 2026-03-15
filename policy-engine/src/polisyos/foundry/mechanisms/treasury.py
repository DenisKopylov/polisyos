from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.canon import content_hash
from polisyos.core.contracts.foundry import ProgramGraph


class TreasuryPlan(BaseModel):
    """Deterministic salt plan for compiled program execution streams.

    The plan is consumed by the trinity compiler to derive stable, per-node
    randomization streams. It is intentionally lightweight and serializable so
    it can be embedded into compile artifacts and replayed later.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    root_seed: int = 0
    node_salts: dict[str, int] = Field(default_factory=dict)
    stream_salts: dict[str, int] = Field(default_factory=lambda: {"default": 0})
    notes: list[str] = Field(default_factory=list)


def stable_hash(value: str) -> int:
    """Map a stable content hash into a reproducible integer salt."""
    digest_hex = content_hash(value)
    return int(digest_hex[:16], 16)


def build_treasury_plan(program: ProgramGraph, root_seed: int = 0) -> TreasuryPlan:
    """Build deterministic node and stream salts for a compiled program graph."""
    node_salts = {node.node_id: stable_hash(node.node_id) for node in program.nodes}
    stream_salts = {"default": stable_hash("default")}
    return TreasuryPlan(
        root_seed=root_seed,
        node_salts=node_salts,
        stream_salts=stream_salts,
        notes=[
            "Used by trinity compilation for reproducible execution streams.",
            "Node salts are derived from stable node identifiers.",
        ],
    )
