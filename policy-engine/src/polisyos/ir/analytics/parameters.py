"""Public analytics parameters module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.data_forge.read_api.academic import (
    RetainedSKGSourceBinding,
    retained_skg_source_binding,
)
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.ir.artifacts import (
    ArtifactStore,
    InputRef,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    ContextAdaptiveParameterBundleRef,
    CrossGraphEvidenceProfileRef,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.literature import EvidenceParameter
else:
    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.literature import EvidenceParameter

_SCHEMA_NAME = "ir.context_adaptive_parameter_bundle"
_SCHEMA_VERSION = "1.0"
_SCHEMA_VERSION_V1_1 = "1.1"
_SCHEMA_VERSION_V1_2 = "1.2"
_SKG_SOURCE_SNAPSHOT_ROLE = "skg_source_snapshot"
_SKG_SOURCE_SNAPSHOT_KIND = "scientist.skg_source_snapshot"
_SKG_SOURCE_SNAPSHOT_MEDIA_TYPE = "application/json"
_SKG_SOURCE_SNAPSHOT_SCHEMA_VERSION = "1.0"


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


class ContextAdaptiveParameterBundleV11(ContextAdaptiveParameterBundle):
    """Versioned bundle that records the selected optional profile, including absence."""

    schema_version: Literal["1.1"] = "1.1"
    selected_cross_graph_profile_ref: CrossGraphEvidenceProfileRef | None


class ContextAdaptiveParameterBundleV12(ContextAdaptiveParameterBundleV11):
    """Source-bound bundle requiring an exact retained SKG descriptor."""

    schema_version: Literal["1.2"] = "1.2"
    selected_skg_source: RetainedSKGSourceBinding


def persist_context_adaptive_parameter_bundle(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _SCHEMA_NAME,
    schema_version: str = _SCHEMA_VERSION,
) -> ContextAdaptiveParameterBundleRef:
    """Persist a historical v1.0 context-adaptive bundle."""
    if bundle.schema_version != _SCHEMA_VERSION:
        raise ValueError("Use the v1.1 persistence helper for versioned lineage bundles")
    if schema_name != _SCHEMA_NAME or schema_version != _SCHEMA_VERSION:
        raise ValueError("The v1.0 persistence helper only writes its declared schema")
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ContextAdaptiveParameterBundleRef.model_validate(ref)


def persist_context_adaptive_parameter_bundle_v1_1(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV11,
    *,
    inputs: list[InputRef],
) -> ContextAdaptiveParameterBundleRef:
    """Persist a v1.1 bundle with its exact selected-profile lineage."""
    _validate_v1_1_input_lineage(store, bundle, inputs)
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION_V1_1,
        inputs=inputs,
        # The required nullable field distinguishes verified absence from an
        # older record that never captured the selection.
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return ContextAdaptiveParameterBundleRef.model_validate(ref)


def persist_context_adaptive_parameter_bundle_v1_2(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV12,
    *,
    inputs: list[InputRef],
) -> ContextAdaptiveParameterBundleRef:
    """Persist a v1.2 bundle with a fully verified retained source join."""
    _validate_v1_2_input_lineage(store, bundle, inputs)
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION_V1_2,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return ContextAdaptiveParameterBundleRef.model_validate(ref)


def load_context_adaptive_parameter_bundle(
    store: ArtifactStore,
    ref: ContextAdaptiveParameterBundleRef,
) -> (
    ContextAdaptiveParameterBundle
    | ContextAdaptiveParameterBundleV11
    | ContextAdaptiveParameterBundleV12
):
    """Load only known bundle versions through their distinct typed decoders."""
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if manifest.kind != _SCHEMA_NAME or schema is None or schema.name != _SCHEMA_NAME:
        raise ValueError("Context-adaptive parameter bundle manifest is incompatible")

    payload = get_json_artifact(store, ref)
    if schema.version == _SCHEMA_VERSION:
        bundle = ContextAdaptiveParameterBundle.model_validate(payload)
        if bundle.schema_version != _SCHEMA_VERSION:
            raise ValueError("Context-adaptive parameter bundle payload version is incompatible")
        return bundle
    if schema.version == _SCHEMA_VERSION_V1_1:
        bundle = ContextAdaptiveParameterBundleV11.model_validate(payload)
        if bundle.schema_version != _SCHEMA_VERSION_V1_1:
            raise ValueError("Context-adaptive parameter bundle payload version is incompatible")
        _validate_v1_1_manifest_lineage(store, bundle, manifest.inputs)
        return bundle
    if schema.version == _SCHEMA_VERSION_V1_2:
        bundle = ContextAdaptiveParameterBundleV12.model_validate(payload)
        if bundle.schema_version != _SCHEMA_VERSION_V1_2:
            raise ValueError("Context-adaptive parameter bundle payload version is incompatible")
        _validate_v1_2_manifest_lineage(store, bundle, manifest.inputs)
        return bundle
    raise ValueError(f"Unsupported context-adaptive parameter bundle version: {schema.version}")


def _validate_v1_1_input_lineage(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV11,
    inputs: list[InputRef],
) -> None:
    allowed_roles = {
        "causal_graph",
        "cross_graph_evidence_profile",
        _SKG_SOURCE_SNAPSHOT_ROLE,
    }
    if any(item.role not in allowed_roles for item in inputs):
        raise ValueError("A v1.1 bundle contains an unsupported input role")
    graph_inputs = [item for item in inputs if item.role == "causal_graph"]
    if len(graph_inputs) != 1:
        raise ValueError("A v1.1 bundle requires exactly one causal graph input")
    profile_inputs = [item for item in inputs if item.role == "cross_graph_evidence_profile"]
    selected = bundle.selected_cross_graph_profile_ref
    if selected is None:
        if profile_inputs:
            raise ValueError("A profileless v1.1 bundle cannot carry a profile input")
    else:
        if len(profile_inputs) != 1:
            raise ValueError("A selected profile requires exactly one profile input")
        profile_input = profile_inputs[0]
        if (
            str(profile_input.artifact_id) != str(selected.artifact_id)
            or profile_input.manifest_profile_sha256 != selected.manifest_profile_sha256
        ):
            raise ValueError("Bundle profile content and manifest input lineage disagree")

    source_inputs = [item for item in inputs if item.role == _SKG_SOURCE_SNAPSHOT_ROLE]
    if len(source_inputs) > 1:
        raise ValueError("A v1.1 bundle accepts at most one selected SKG source input")
    if not source_inputs:
        return
    source_input = source_inputs[0]
    source_profile = source_input.manifest_profile_sha256
    if source_profile is None:
        raise ValueError("A selected SKG source requires its exact manifest profile")
    manifest_reader = getattr(store, "get_manifest_by_profile", None)
    if not callable(manifest_reader):
        raise ValueError("Selected SKG source profile could not be resolved")
    try:
        manifest = manifest_reader(source_input.artifact_id, source_profile)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("Selected SKG source profile could not be resolved") from exc
    if (
        str(manifest.artifact_id) != str(source_input.artifact_id)
        or manifest.kind != _SKG_SOURCE_SNAPSHOT_KIND
        or manifest.media_type != _SKG_SOURCE_SNAPSHOT_MEDIA_TYPE
    ):
        raise ValueError("Selected SKG source input has an incompatible manifest")
    selected_source_ref = ArtifactRefModel(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=source_profile,
    )
    try:
        store.get_bytes(selected_source_ref)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("Selected SKG source profile could not be resolved") from exc
    schema = manifest.artifact_schema
    if (
        manifest.kind != _SKG_SOURCE_SNAPSHOT_KIND
        or manifest.media_type != _SKG_SOURCE_SNAPSHOT_MEDIA_TYPE
        or schema is None
        or schema.name != _SKG_SOURCE_SNAPSHOT_KIND
        or schema.version
        != (
            "1.1"
            if isinstance(bundle, ContextAdaptiveParameterBundleV12)
            else _SKG_SOURCE_SNAPSHOT_SCHEMA_VERSION
        )
    ):
        raise ValueError("Selected SKG source input has an incompatible manifest")


def _validate_v1_1_manifest_lineage(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV11,
    inputs: list[InputRef],
) -> None:
    _validate_v1_1_input_lineage(store, bundle, inputs)


def _validate_v1_2_input_lineage(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV12,
    inputs: list[InputRef],
) -> None:
    """Require the bundle to bind one exact, fully reconciled source descriptor."""
    _validate_v1_1_input_lineage(store, bundle, inputs)
    source_inputs = [item for item in inputs if item.role == _SKG_SOURCE_SNAPSHOT_ROLE]
    if len(source_inputs) != 1:
        raise ValueError("A v1.2 bundle requires exactly one selected SKG source input")
    selected = bundle.selected_skg_source
    source_input = source_inputs[0]
    selected_ref = selected.descriptor_ref
    if (
        selected_ref.kind != _SKG_SOURCE_SNAPSHOT_KIND
        or selected_ref.media_type != _SKG_SOURCE_SNAPSHOT_MEDIA_TYPE
        or selected_ref.manifest_profile_sha256 is None
        or str(source_input.artifact_id) != str(selected_ref.artifact_id)
        or source_input.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    ):
        raise ValueError("Bundle source content and manifest input lineage disagree")
    try:
        resolved = retained_skg_source_binding(store, selected_ref)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("Selected SKG source descriptor could not be resolved") from exc
    if (
        resolved != selected
        or bundle.skg_snapshot_ref != resolved.source_reference
        or bundle.skg_version_id != resolved.source_version_id
        or selected.version_identity_kind != "content_digest"
    ):
        raise ValueError("Bundle source content and observed version disagree")


def _validate_v1_2_manifest_lineage(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV12,
    inputs: list[InputRef],
) -> None:
    _validate_v1_2_input_lineage(store, bundle, inputs)


__all__ = [
    "ContextAdaptiveParameterBundle",
    "ContextAdaptiveParameterBundleV11",
    "ContextAdaptiveParameterBundleV12",
    "ParameterApplicability",
    "load_context_adaptive_parameter_bundle",
    "persist_context_adaptive_parameter_bundle",
    "persist_context_adaptive_parameter_bundle_v1_1",
    "persist_context_adaptive_parameter_bundle_v1_2",
]
