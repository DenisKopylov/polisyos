from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import EvidenceParameter
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ContextAdaptiveParameterBundleRef

_SCHEMA_NAME = "ir.context_adaptive_parameter_bundle"
_SCHEMA_VERSION = "1.0"


class ParameterApplicability(BaseModel):
    """Applicability assessment for a parameter in a target context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_id: str
    target_context_id: str
    transport_status: TransportabilityStatus
    transport_mode: TransportMode = TransportMode.NONE
    transport_confidence: float = Field(ge=0.0, le=1.0)
    context_distance: float = Field(ge=0.0, le=1.0)
    is_applicable: bool
    adjustment_required: bool
    uncertainty_multiplier: float = Field(default=1.0, ge=1.0)
    recommended_value: float | None = None
    transport_notes: list[str] = Field(default_factory=list)


class ContextAdaptiveParameterBundle(BaseModel):
    """Parameters selected from SKG and adapted for a target simulation context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    target_context: ContextProfile
    simulation_domain: str
    parameters: dict[str, EvidenceParameter] = Field(default_factory=dict)
    applicability: dict[str, ParameterApplicability] = Field(default_factory=dict)
    unsupported_parameters: list[str] = Field(default_factory=list)
    skg_snapshot_ref: str = ""
    skg_version_id: int | None = None
    selection_timestamp: str = ""


def persist_context_adaptive_parameter_bundle(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _SCHEMA_NAME,
    schema_version: str = _SCHEMA_VERSION,
) -> ContextAdaptiveParameterBundleRef:
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ContextAdaptiveParameterBundleRef.model_validate(ref)


def load_context_adaptive_parameter_bundle(
    store: ArtifactStore,
    ref: ContextAdaptiveParameterBundleRef,
) -> ContextAdaptiveParameterBundle:
    payload = get_json_artifact(store, ref.artifact_id)
    return ContextAdaptiveParameterBundle.model_validate(payload)


__all__ = [
    "ParameterApplicability",
    "ContextAdaptiveParameterBundle",
    "persist_context_adaptive_parameter_bundle",
    "load_context_adaptive_parameter_bundle",
]
