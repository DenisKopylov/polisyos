from __future__ import annotations

from pydantic import BaseModel, Field

from polisyos.core.canon import content_hash
from polisyos.core.contracts.foundry import ProgramGraph


class TreasuryPlan(BaseModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    root_seed: int = 0
    node_salts: dict[str, int] = Field(default_factory=dict)
    stream_salts: dict[str, int] = Field(default_factory=lambda: {"default": 0})
    notes: list[str] = Field(default_factory=list)


def stable_hash(value: str) -> int:
    digest_hex = content_hash(value)
    return int(digest_hex[:16], 16)


def build_treasury_plan(program: ProgramGraph, root_seed: int = 0) -> TreasuryPlan:
    node_salts = {node.node_id: stable_hash(node.node_id) for node in program.nodes}
    stream_salts = {"default": stable_hash("default")}
    return TreasuryPlan(root_seed=root_seed, node_salts=node_salts, stream_salts=stream_salts)
