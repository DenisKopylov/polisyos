"""IR contracts for generative network diagnostics and causal block bridges."""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation as _OwnedJSONRepresentation,
)
from polisyos.ir.analytics._owner_admission import (
    declare_model_owner as _declare_model_owner,
)
from polisyos.ir.analytics._owner_admission import (
    owner_profile_for_spec as _owner_profile_for_spec,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef  # noqa: TC001
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import CompatibilityMode as _CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalBlockBridgeRef


def _to_numpy(value: object | None) -> np.ndarray | None:
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
    def _coerce_cluster_id(cls, value: object) -> np.ndarray | None:
        return _to_numpy(value)

    @field_serializer("cluster_id", mode="plain", when_used="json")
    def _serialize_cluster_id(self, value: object) -> object:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value


_CAUSAL_BLOCK_BRIDGE_OWNER = _declare_model_owner(
    CausalBlockBridge,
    contract_id="ir.analytics.causal_block_bridge.owner.v1",
    dto_fqn="polisyos.ir.analytics.network_generative.CausalBlockBridge",
    abi_key="ir.analytics.causal_block_bridge.owner.v1.dto-abi.v1",
    registry_key="ir.causal_block_bridge",
    kind="ir.causal_block_bridge",
    media_type="application/json",
    purpose="causal_block_bridge",
    policy_revision="ir.analytics.causal_block_bridge.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.causal_block_bridge.wire-law", "1"),),
    payload_version_field=None,
    validate_profile=_owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        _OwnedJSONRepresentation(
            schema_name="ir.causal_block_bridge",
            schema_version="1.0",
            payload_version=None,
            wire_policy_ref="ir.analytics.causal_block_bridge.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=_CompatibilityMode.NONE,
            notes=("Exact versionless owner-bound causal block bridge tuple.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


def persist_causal_block_bridge(
    store: ArtifactStore,
    bridge: CausalBlockBridge,
    *,
    inputs: list[InputRef] | None = None,
) -> CausalBlockBridgeRef:
    """Persist a design-stage block bridge as a content-addressed IR artifact."""
    ref = _put_owned_json_artifact(
        store,
        bridge.model_dump(mode="json"),
        owner=_CAUSAL_BLOCK_BRIDGE_OWNER,
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
    return _get_owned_json_artifact(store, ref, owner=_CAUSAL_BLOCK_BRIDGE_OWNER)


__all__ = [
    "BlockSupportReport",
    "CausalBlockBridge",
    "load_causal_block_bridge",
    "persist_causal_block_bridge",
]
