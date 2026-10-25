"""Public analytics causal capabilities module API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalCapabilityContractRef


class CausalBackendId(str, Enum):
    """Causal backend ID public type."""

    Y0 = "y0"
    R_CAUSALEFFECT = "r_causaleffect"
    SIMPLIFIED_LEGACY = "simplified_legacy"
    BOUNDS_ONLY = "bounds_only"


class CausalIdentificationFamily(str, Enum):
    """Causal identification family public type."""

    DIRECT = "direct"
    TRSO = "trso"
    FRONTDOOR = "frontdoor"
    DO_CALCULUS_RULE2 = "do_calculus_rule2"
    DO_CALCULUS_RULE3 = "do_calculus_rule3"
    C_COMPONENT_FACTORIZATION = "c_component_factorization"
    BOUNDS_MANSKI = "bounds_manski"


class CausalBackendCapability(BaseModel):
    """Causal backend capability public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: CausalBackendId
    available: bool = True
    disabled_reason: str | None = None
    supported_families: list[CausalIdentificationFamily] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CausalCapabilityContract(BaseModel):
    """Causal capability contract data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    dependency_fingerprint: str
    full_backend_order: list[CausalBackendId] = Field(default_factory=list)
    degradation_policy: str = "full_then_bounds_explicit_simplified"
    backends: list[CausalBackendCapability] = Field(default_factory=list)
    supported_families: list[CausalIdentificationFamily] = Field(default_factory=list)
    disabled_families: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    def backend(self, backend_id: CausalBackendId) -> CausalBackendCapability | None:
        for backend in self.backends:
            if backend.backend_id is backend_id:
                return backend
        return None

    def supports_family(self, family: CausalIdentificationFamily) -> bool:
        return family in self.supported_families


_CAUSAL_CAPABILITY_CONTRACT_OWNER = declare_model_owner(
    CausalCapabilityContract,
    contract_id="ir.analytics.ir_causal_capability_contract.owner.v1",
    dto_fqn="polisyos.ir.analytics.causal_capabilities.CausalCapabilityContract",
    abi_key="ir.analytics.ir_causal_capability_contract.owner.v1.dto-abi.v1",
    registry_key="ir.causal_capability_contract",
    kind="ir.causal_capability_contract",
    media_type="application/json",
    purpose="causal_capability_contract",
    policy_revision="ir.analytics.ir_causal_capability_contract.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.ir_causal_capability_contract.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        OwnedJSONRepresentation(
            schema_name="ir.causal_capability_contract",
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.ir_causal_capability_contract.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=CompatibilityMode.NONE,
            notes=("Exact owner-bound analytics tuple; unknown history remains opaque.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


def persist_causal_capability_contract(
    store: ArtifactStore,
    contract: CausalCapabilityContract,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_capability_contract",
    schema_version: str = "1.0",
) -> CausalCapabilityContractRef:
    """Persist a causal-capability contract through its exact typed owner."""
    ref = _put_owned_json_artifact(
        store,
        contract.model_dump(mode="json"),
        owner=_CAUSAL_CAPABILITY_CONTRACT_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalCapabilityContractRef.from_selected_write(ref)


def load_causal_capability_contract(
    store: ArtifactStore,
    ref: CausalCapabilityContractRef,
) -> CausalCapabilityContract:
    """Load a causal-capability contract after owner and profile admission."""
    return _get_owned_json_artifact(store, ref, owner=_CAUSAL_CAPABILITY_CONTRACT_OWNER)


__all__ = [
    "CausalBackendCapability",
    "CausalBackendId",
    "CausalCapabilityContract",
    "CausalIdentificationFamily",
    "load_causal_capability_contract",
    "persist_causal_capability_contract",
]
