"""IR contracts for generative network diagnostics and causal block bridges."""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import CausalBlockBridgeRef


def _to_numpy(value: Any) -> Any:
    if value is None or isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


class BlockSupportReport(BaseModel):
    """Per-block support diagnostics for design-stage causal stratification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    block_id: int = Field(ge=0)
    n_units: int = Field(ge=1)
    n_treated: int = Field(ge=0)
    n_control: int = Field(ge=0)
    treated_share: float = Field(ge=0.0, le=1.0)
    positivity_passed: bool
    warnings: tuple[str, ...] = ()


class CausalBlockBridge(BaseModel):
    """Bridge from SBM-style block labels into the network causal API."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    cluster_id: Any
    node_to_block: dict[str, int]
    block_support: tuple[BlockSupportReport, ...] = ()
    positivity_passed: bool = True
    aggregate_exposures: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @field_validator("cluster_id", mode="before")
    @classmethod
    def _coerce_cluster_id(cls, value: Any) -> Any:
        return _to_numpy(value)

    @field_serializer("cluster_id", mode="plain", when_used="json")
    def _serialize_cluster_id(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


def persist_causal_block_bridge(
    store: ArtifactStore,
    bridge: CausalBlockBridge,
    *,
    inputs: list[InputRef] | None = None,
) -> CausalBlockBridgeRef:
    """Persist a design-stage block bridge as a content-addressed IR artifact."""
    ref = put_json_artifact(
        store,
        bridge.model_dump(mode="json"),
        kind="ir.causal_block_bridge",
        schema_name="ir.causal_block_bridge",
        schema_version="1.0",
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalBlockBridgeRef.model_validate(ref)


def load_causal_block_bridge(
    store: ArtifactStore,
    ref: CausalBlockBridgeRef,
) -> CausalBlockBridge:
    """Load and validate a persisted causal block bridge."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CausalBlockBridge.model_validate(payload)


__all__ = [
    "BlockSupportReport",
    "CausalBlockBridge",
    "load_causal_block_bridge",
    "persist_causal_block_bridge",
]
