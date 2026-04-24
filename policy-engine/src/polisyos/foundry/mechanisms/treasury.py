"""Public mechanisms treasury module API."""

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


def _seeded_salt(label: str, *, root_seed: int) -> int:
    """Derive a salt while preserving historical semantics for the zero-seed case."""
    if root_seed == 0:
        return stable_hash(label)
    return stable_hash(f"{root_seed}:{label}")


def build_treasury_plan(program: ProgramGraph, root_seed: int = 0) -> TreasuryPlan:
    """Build deterministic node and stream salts for a compiled program graph."""
    node_salts = {
        node.node_id: _seeded_salt(f"node:{node.node_id}", root_seed=root_seed)
        for node in program.nodes
    }
    stream_salts = {"default": _seeded_salt("stream:default", root_seed=root_seed)}
    return TreasuryPlan(
        root_seed=root_seed,
        node_salts=node_salts,
        stream_salts=stream_salts,
        notes=[
            "Used by trinity compilation for reproducible execution streams.",
            "Node salts are derived from stable node identifiers and the treasury root seed.",
        ],
    )
