"""Public analytics parameters module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.data_forge.read_api.academic import (
    RetainedSKGSourceBinding,
    retained_skg_source_binding,
)
from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation as _OwnedJSONRepresentation,
)
from polisyos.ir.analytics._owner_admission import (
    declared_payload_version as _declared_payload_version,
)
from polisyos.ir.analytics._owner_admission import project_owner_source as _project_owner_source
from polisyos.ir.analytics._owner_admission import (
    register_owner_representations as _register_owner_representations,
)
from polisyos.ir.analytics._owner_admission import validate_owner_payload as _validate_owner_payload
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.ir.artifacts import get_json_artifact as get_json_artifact
from polisyos.ir.artifacts import normalize_artifact_ref
from polisyos.ir.artifacts import put_json_artifact as put_json_artifact
from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration as _ArtifactOwnerDeclaration
from polisyos.ir.artifacts.contracts import ArtifactSelector as _ArtifactSelector
from polisyos.ir.artifacts.contracts import CanonInfo as _CanonInfo
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact_with_bytes,
    _put_owned_json_artifact,
)
from polisyos.ir.migrations.base import CompatibilityMode as _CompatibilityMode
from polisyos.ir.migrations.base import IRRepresentationKey as _IRRepresentationKey
from polisyos.ir.migrations.base import (
    IRRepresentationRegistration as _IRRepresentationRegistration,
)
from polisyos.ir.migrations.base import ResolvedSchemaAdmission as _ResolvedSchemaAdmission
from polisyos.ir.migrations.base import (
    get_ir_owner_registry_snapshot as _get_ir_owner_registry_snapshot,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    ContextAdaptiveParameterBundleRef,
    CrossGraphEvidenceProfileRef,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.literature import EvidenceParameter
    from polisyos.ir.artifacts import ArtifactStore
    from polisyos.ir.artifacts._lineage import InputRefLike
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


_PARAMETER_OWNER_ID = "ir.analytics.ir_context_adaptive_parameter_bundle.owner.v1"
_PARAMETER_DTO_ABI = "polisyos.ir.analytics.parameters.ContextAdaptiveParameterBundle.union.v1"
_PARAMETER_POLICY_1_0 = ("ir.analytics.context_adaptive_parameter_bundle.wire-law", "1.0")
_PARAMETER_POLICY_1_1 = ("ir.analytics.context_adaptive_parameter_bundle.wire-law", "1.1")
_PARAMETER_POLICY_1_2 = ("ir.analytics.context_adaptive_parameter_bundle.wire-law", "1.2")
_PARAMETER_POLICY_MODELS = {
    _PARAMETER_POLICY_1_0: ContextAdaptiveParameterBundle,
    _PARAMETER_POLICY_1_1: ContextAdaptiveParameterBundleV11,
    _PARAMETER_POLICY_1_2: ContextAdaptiveParameterBundleV12,
}
_PARAMETER_PROFILE_REFS = {
    _PARAMETER_POLICY_1_0: "ir.analytics.context_adaptive_parameter_bundle.canon.v1",
    _PARAMETER_POLICY_1_1: "ir.analytics.context_adaptive_parameter_bundle.canon.v1_1",
    _PARAMETER_POLICY_1_2: "ir.analytics.context_adaptive_parameter_bundle.canon.v1_2",
}
_PARAMETER_CANON_INFO = {
    _PARAMETER_POLICY_1_0: _CanonInfo.from_spec(CanonSpec(forbid_floats=False)),
    _PARAMETER_POLICY_1_1: _CanonInfo.from_spec(CanonSpec(forbid_floats=False, exclude_none=False)),
    _PARAMETER_POLICY_1_2: _CanonInfo.from_spec(CanonSpec(forbid_floats=False, exclude_none=False)),
}
_PARAMETER_COMPATIBILITY_NOTES = (
    "Exact owner-declared parameter bundle tuple; typed history is source-versioned.",
)
_PARAMETER_REPRESENTATIONS = (
    _OwnedJSONRepresentation(
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION,
        payload_version=_SCHEMA_VERSION,
        wire_policy_ref=_PARAMETER_POLICY_1_0[0],
        wire_policy_revision=_PARAMETER_POLICY_1_0[1],
        profile_ref=_PARAMETER_PROFILE_REFS[_PARAMETER_POLICY_1_0],
        compatibility=_CompatibilityMode.NONE,
        notes=_PARAMETER_COMPATIBILITY_NOTES,
        readable=True,
        writable=True,
        current=False,
        default_write=False,
        readable_from=(),
    ),
    _OwnedJSONRepresentation(
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION_V1_1,
        payload_version=_SCHEMA_VERSION_V1_1,
        wire_policy_ref=_PARAMETER_POLICY_1_1[0],
        wire_policy_revision=_PARAMETER_POLICY_1_1[1],
        profile_ref=_PARAMETER_PROFILE_REFS[_PARAMETER_POLICY_1_1],
        compatibility=_CompatibilityMode.NONE,
        notes=_PARAMETER_COMPATIBILITY_NOTES,
        readable=True,
        writable=True,
        current=False,
        default_write=False,
        readable_from=(),
    ),
    _OwnedJSONRepresentation(
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION_V1_2,
        payload_version=_SCHEMA_VERSION_V1_2,
        wire_policy_ref=_PARAMETER_POLICY_1_2[0],
        wire_policy_revision=_PARAMETER_POLICY_1_2[1],
        profile_ref=_PARAMETER_PROFILE_REFS[_PARAMETER_POLICY_1_2],
        compatibility=_CompatibilityMode.NONE,
        notes=_PARAMETER_COMPATIBILITY_NOTES,
        readable=True,
        writable=True,
        current=True,
        default_write=True,
        readable_from=(
            _IRRepresentationKey(_SCHEMA_NAME, _SCHEMA_VERSION, _SCHEMA_VERSION),
            _IRRepresentationKey(_SCHEMA_NAME, _SCHEMA_VERSION_V1_1, _SCHEMA_VERSION_V1_1),
        ),
    ),
)


def _parameter_payload_version(payload: object) -> str | None:
    return _declared_payload_version(payload, field_name="schema_version")


def _parameter_registration_policy(
    registration: _IRRepresentationRegistration,
) -> tuple[str, str]:
    policy = (registration.wire_policy_ref, registration.wire_policy_revision)
    if (
        registration.registry_key != _SCHEMA_NAME
        or registration.owner_ref != _PARAMETER_OWNER_ID
        or registration.dto_abi != _PARAMETER_DTO_ABI
        or registration.schema_name != _SCHEMA_NAME
        or policy not in _PARAMETER_POLICY_MODELS
        or registration.payload_version != policy[1]
        or registration.profile_ref != _PARAMETER_PROFILE_REFS[policy]
    ):
        raise ValueError("Parameter bundle tuple is outside the trusted owner grammar")
    return policy


def _validate_parameter_source(
    payload: object,
    admission: _ResolvedSchemaAdmission,
) -> (
    ContextAdaptiveParameterBundle
    | ContextAdaptiveParameterBundleV11
    | ContextAdaptiveParameterBundleV12
):
    if admission.migration_path:
        raise ValueError("Parameter bundle owner does not admit schema migrations")
    policy = _parameter_registration_policy(admission.source_registration)
    _parameter_registration_policy(admission.current_registration)
    model = _PARAMETER_POLICY_MODELS[policy]
    snapshot = _get_ir_owner_registry_snapshot()
    if snapshot.revision != admission.snapshot_revision:
        raise ValueError("Parameter bundle owner registry changed during admission")
    expected_rows = tuple(
        row
        for row in snapshot.representation_records
        if row.registry_key == _SCHEMA_NAME
        and row.owner_ref == _PARAMETER_OWNER_ID
        and row.dto_abi == _PARAMETER_DTO_ABI
    )
    return _validate_owner_payload(
        payload,
        admission,
        payload_version_field="schema_version",
        source_parser=model.model_validate,
        expected_rows=expected_rows,
        expected_types=(model,),
    )


def _project_parameter_source(
    source: ContextAdaptiveParameterBundle
    | ContextAdaptiveParameterBundleV11
    | ContextAdaptiveParameterBundleV12,
    admission: _ResolvedSchemaAdmission,
) -> (
    ContextAdaptiveParameterBundle
    | ContextAdaptiveParameterBundleV11
    | ContextAdaptiveParameterBundleV12
):
    policy = _parameter_registration_policy(admission.source_registration)
    return _project_owner_source((_PARAMETER_POLICY_MODELS[policy],), source)


def _validate_parameter_profile(
    profile: _CanonInfo,
    registration: _IRRepresentationRegistration,
) -> bool:
    try:
        policy = _parameter_registration_policy(registration)
    except (TypeError, ValueError):
        return False
    return (
        registration.profile_ref == _PARAMETER_PROFILE_REFS[policy]
        and profile == _PARAMETER_CANON_INFO[policy]
    )


_PARAMETER_OWNER: _ArtifactOwnerDeclaration[
    ContextAdaptiveParameterBundle
    | ContextAdaptiveParameterBundleV11
    | ContextAdaptiveParameterBundleV12,
    ContextAdaptiveParameterBundle
    | ContextAdaptiveParameterBundleV11
    | ContextAdaptiveParameterBundleV12,
] = _ArtifactOwnerDeclaration(
    contract_id=_PARAMETER_OWNER_ID,
    dto_fqn=_PARAMETER_DTO_ABI,
    abi_key="ir.analytics.context_adaptive_parameter_bundle.owner-abi.v1",
    registry_key=_SCHEMA_NAME,
    kind=_SCHEMA_NAME,
    media_type="application/json",
    purpose="Typed context-adaptive parameter bundle intake and preservation.",
    policy_revision="2026-10-23",
    accepted_wire_policies=tuple(_PARAMETER_POLICY_MODELS),
    payload_version_of=_parameter_payload_version,
    validate_source=_validate_parameter_source,
    project_for_consumer=_project_parameter_source,
    validate_profile=_validate_parameter_profile,
)
_register_owner_representations(_PARAMETER_OWNER, _PARAMETER_REPRESENTATIONS)


def persist_context_adaptive_parameter_bundle(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundle,
    *,
    inputs: Sequence[InputRefLike] | None = None,
    schema_name: str = _SCHEMA_NAME,
    schema_version: str = _SCHEMA_VERSION,
) -> ContextAdaptiveParameterBundleRef:
    """Persist a historical v1.0 context-adaptive bundle."""
    if bundle.schema_version != _SCHEMA_VERSION:
        raise ValueError("Use the v1.1 persistence helper for versioned lineage bundles")
    if schema_name != _SCHEMA_NAME or schema_version != _SCHEMA_VERSION:
        raise ValueError("The v1.0 persistence helper only writes its declared schema")
    ref = _put_owned_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        owner=_PARAMETER_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ContextAdaptiveParameterBundleRef.model_validate(ref)


def persist_context_adaptive_parameter_bundle_v1_1(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV11,
    *,
    inputs: Sequence[InputRefLike],
    schema_name: str = _SCHEMA_NAME,
    schema_version: str = _SCHEMA_VERSION_V1_1,
) -> ContextAdaptiveParameterBundleRef:
    """Persist a v1.1 bundle with its exact selected-profile lineage."""
    _validate_v1_1_input_lineage(store, bundle, inputs)
    ref = _put_owned_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        owner=_PARAMETER_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
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
    inputs: Sequence[InputRefLike],
    schema_name: str = _SCHEMA_NAME,
    schema_version: str = _SCHEMA_VERSION_V1_2,
) -> ContextAdaptiveParameterBundleRef:
    """Persist a v1.2 bundle with a fully verified retained source join."""
    _validate_v1_2_input_lineage(store, bundle, inputs)
    ref = _put_owned_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        owner=_PARAMETER_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return ContextAdaptiveParameterBundleRef.model_validate(ref)


def load_context_adaptive_parameter_bundle(
    store: ArtifactStore,
    ref: _ArtifactSelector,
) -> (
    ContextAdaptiveParameterBundle
    | ContextAdaptiveParameterBundleV11
    | ContextAdaptiveParameterBundleV12
):
    """Load an exact source representation through its code-declared DTO owner."""
    ref = ContextAdaptiveParameterBundleRef.model_validate(normalize_artifact_ref(ref))
    owned = _get_owned_json_artifact_with_bytes(store, ref, owner=_PARAMETER_OWNER)
    bundle = owned.value
    source_registration = owned.admission.source_registration
    if source_registration.schema_name != _SCHEMA_NAME:
        raise ValueError("Context-adaptive parameter bundle manifest is incompatible")
    if _parameter_registration_policy(source_registration) not in _PARAMETER_POLICY_MODELS:
        raise ValueError("Context-adaptive parameter bundle representation is unsupported")

    manifest_profile_sha256 = owned.manifest_profile_sha256
    manifest_reader = getattr(store, "get_manifest_by_profile", None)
    if not callable(manifest_reader) or manifest_profile_sha256 is None:
        raise ValueError("Context-adaptive parameter bundle selected manifest is unavailable")
    try:
        manifest = manifest_reader(ref.artifact_id, manifest_profile_sha256)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(
            "Context-adaptive parameter bundle selected manifest is unavailable"
        ) from exc
    schema = manifest.artifact_schema
    if (
        manifest.kind != _SCHEMA_NAME
        or schema is None
        or schema.name != _SCHEMA_NAME
        or schema.version != source_registration.schema_version
    ):
        raise ValueError("Context-adaptive parameter bundle manifest is incompatible")

    if type(bundle) is ContextAdaptiveParameterBundle:
        return bundle
    if type(bundle) is ContextAdaptiveParameterBundleV11:
        _validate_v1_1_manifest_lineage(store, bundle, manifest.inputs)
        return bundle
    if type(bundle) is ContextAdaptiveParameterBundleV12:
        _validate_v1_2_manifest_lineage(store, bundle, manifest.inputs)
        return bundle
    raise ValueError("Context-adaptive parameter bundle owner returned an undeclared DTO")


def _validate_v1_1_input_lineage(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV11,
    inputs: Sequence[InputRefLike],
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
    inputs: Sequence[InputRefLike],
) -> None:
    _validate_v1_1_input_lineage(store, bundle, inputs)


def _validate_v1_2_input_lineage(
    store: ArtifactStore,
    bundle: ContextAdaptiveParameterBundleV12,
    inputs: Sequence[InputRefLike],
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
    inputs: Sequence[InputRefLike],
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
