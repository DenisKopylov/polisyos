"""Public analytics causal capabilities module API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
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


def persist_causal_capability_contract(
    store: ArtifactStore,
    contract: CausalCapabilityContract,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_capability_contract",
    schema_version: str = "1.0",
) -> CausalCapabilityContractRef:
    """Persist causal capability contract helper."""
    ref = put_json_artifact(
        store,
        contract.model_dump(mode="json"),
        kind="ir.causal_capability_contract",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalCapabilityContractRef.model_validate(ref)


def load_causal_capability_contract(
    store: ArtifactStore,
    ref: CausalCapabilityContractRef,
) -> CausalCapabilityContract:
    """Load causal capability contract."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CausalCapabilityContract.model_validate(payload)


__all__ = [
    "CausalBackendCapability",
    "CausalBackendId",
    "CausalCapabilityContract",
    "CausalIdentificationFamily",
    "load_causal_capability_contract",
    "persist_causal_capability_contract",
]
