"""Stable DTOs for Fabric query planning, evidence bundles, and materialized data views."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from ..artifacts.manifest import ArtifactRef, InputRef, WarningRecord
from .uncertainty import UncertaintyEnvelopeRef


class DataViewRequestRef(ArtifactRef):
    """Artifact reference for the original Fabric data-view request payload."""

    kind: str = "ir.data_view_request"
    media_type: str = "application/json"


class QueryPlanRef(ArtifactRef):
    """Artifact reference for the query plan emitted before Fabric data retrieval runs."""

    kind: str = "fabric.query_plan"
    media_type: str = "application/json"


class FabricResultRef(ArtifactRef):
    """Artifact reference for the top-level Fabric result bundle returned to callers."""

    kind: str = "fabric.result_bundle"
    media_type: str = "application/json"


class EvidenceBundleRef(ArtifactRef):
    """Artifact reference for the evidence bundle backing a Fabric result."""

    kind: str = "fabric.evidence_bundle"
    media_type: str = "application/json"


class UncertaintyBoundsRef(ArtifactRef):
    """Artifact reference for numeric uncertainty bounds attached to a Fabric result."""

    kind: str = "fabric.uncertainty_bounds"
    media_type: str = "application/json"


class WarningsRef(ArtifactRef):
    """Artifact reference for machine-readable warnings emitted during Fabric retrieval."""

    kind: str = "fabric.warnings"
    media_type: str = "application/json"


class DataSnapshotRef(ArtifactRef):
    """Artifact reference for a materialized snapshot of retrieved data and its metadata."""

    kind: str = "fabric.data_snapshot"
    media_type: str = "application/json"


class HistoricalSemanticDiffReportRef(ArtifactRef):
    """Historical semantic diff report ref data model."""

    kind: str = "fabric.historical_semantic_diff_report"
    media_type: str = "application/json"


class QueryPlanStep(BaseModel):
    """Query plan step public type."""

    model_config = ConfigDict(extra="forbid")

    op: str
    params: dict[str, str | int | bool] = Field(default_factory=dict)


class QueryPlan(BaseModel):
    """Ordered retrieval plan describing which engine steps should satisfy a data request."""

    model_config = ConfigDict(extra="forbid")

    request_ref: DataViewRequestRef
    engine: str
    steps: list[QueryPlanStep] = Field(default_factory=list)
    trust_policy_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class EvidenceStep(BaseModel):
    """Evidence step public type."""

    model_config = ConfigDict(extra="forbid")

    op: str
    details: dict[str, str | int | bool] = Field(default_factory=dict)


class ProvenanceCoreRefModel(BaseModel):
    """Pydantic model for ProvenanceCoreRef."""

    model_config = ConfigDict(extra="forbid")

    graph_id: str
    stable_id: str
    artifact_id: str


class EvidenceBundle(BaseModel):
    """Provenance bundle describing inputs, transforms, and trust metadata for retrieved data."""

    model_config = ConfigDict(extra="forbid")

    sources: list[ArtifactRef] = Field(default_factory=list)
    transforms: list[EvidenceStep] = Field(default_factory=list)
    trust_policy_id: str | None = None
    notes: list[str] = Field(default_factory=list)
    provenance_ref: ProvenanceCoreRefModel | None = None
    quality_indicators: dict[str, dict[str, Any]] | None = None


class UncertaintyBounds(BaseModel):
    """Uncertainty bounds public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    value: Decimal
    lower: Decimal
    upper: Decimal
    method: str = "two_pass_compare"


class WarningsBundle(BaseModel):
    """Collection of warning records emitted while planning or serving a Fabric request."""

    model_config = ConfigDict(extra="forbid")

    warnings: list[WarningRecord] = Field(default_factory=list)


class FabricResult(BaseModel):
    """Top-level Fabric output linking retrieved data to plans, evidence, and uncertainty."""

    model_config = ConfigDict(extra="forbid")

    request_ref: DataViewRequestRef
    plan_ref: QueryPlanRef
    data_ref: ArtifactRef
    data_schema_ref: ArtifactRef | None = None
    sources: list[ArtifactRef] = Field(default_factory=list)
    trust_policy_id: str | None = None
    evidence_ref: EvidenceBundleRef
    uncertainty_ref: UncertaintyBoundsRef | None = None
    uncertainty_envelope_ref: UncertaintyEnvelopeRef | None = None
    warnings_ref: WarningsRef | None = None
    stats: dict[str, int | str] = Field(default_factory=dict)


class _DataSnapshotOwnerLineage(BaseModel):
    """Strict base for owner-specific direct-input witnesses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.core.DataSnapshotOwnerLineage.v1"] = (
        "polisyos.core.DataSnapshotOwnerLineage.v1"
    )


class MeasurementRootDataSnapshotLineage(_DataSnapshotOwnerLineage):
    """Typed references emitted by the replay-verified measurement-root owner."""

    owner: Literal["measurement_root"] = "measurement_root"
    measurement_root_ref: ArtifactRef
    fetch_receipt_ref: ArtifactRef
    catalog_binding_ref: ArtifactRef


class FabricBridgeDataSnapshotLineage(_DataSnapshotOwnerLineage):
    """Typed request relation emitted by DefaultFabricPort."""

    owner: Literal["fabric_bridge"] = "fabric_bridge"
    data_view_request_ref: DataViewRequestRef


class AcquiredObservationDataSnapshotLineage(_DataSnapshotOwnerLineage):
    """Typed source refs emitted by the activated-observation overlay owner."""

    owner: Literal["acquired_observation_overlay"] = "acquired_observation_overlay"
    base_data_snapshot_ref: ArtifactRef
    overlay_admission_receipt_ref: ArtifactRef
    passport_ref: ArtifactRef


DataSnapshotOwnerLineage = Annotated[
    MeasurementRootDataSnapshotLineage
    | FabricBridgeDataSnapshotLineage
    | AcquiredObservationDataSnapshotLineage,
    Field(discriminator="owner"),
]


DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION = "0.3.0"


class DataSnapshot(BaseModel):
    """Snapshot of retrieved data plus typed references needed to audit its quality.

    Version 0.2.0 remains readable with its exact typed-field/role contract.
    Recognized owner families must pass the same fresh producer verification
    under either schema; version 0.3.0 carries those owner refs explicitly.
    """

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.DataSnapshot"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "0.2.0"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = (
        "0.2.0",
        DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
    )
    ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION: ClassVar[dict[str, tuple[str, ...]]] = {
        DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION: ("source_lineage",),
    }
    ARTIFACT_KIND: ClassVar[Literal["fabric.data_snapshot"]] = "fabric.data_snapshot"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid")

    data_ref: ArtifactRef
    data_schema_ref: ArtifactRef | None = None
    evidence_ref: EvidenceBundleRef | None = None
    quality_report_ref: ArtifactRef | None = None
    uncertainty_ref: UncertaintyBoundsRef | None = None
    uncertainty_envelope_ref: UncertaintyEnvelopeRef | None = None
    warnings_ref: WarningsRef | None = None
    input_bindings_ref: ArtifactRef | None = None
    source_lineage: DataSnapshotOwnerLineage | None = None
    pii_scan_summary: dict[str, Any] | None = None
    stats: dict[str, int | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class DataSnapshotOwnerBound(DataSnapshot):
    """Schema 0.3.0 writer DTO requiring a typed owner-lineage variant."""

    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = (DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,)
    ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION: ClassVar[dict[str, tuple[str, ...]]] = {
        DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION: ("source_lineage",),
    }

    source_lineage: DataSnapshotOwnerLineage


_DATA_SNAPSHOT_REFERENCE_INPUT_ROLES: dict[str, frozenset[str]] = {
    "data_ref": frozenset(
        {
            "data_ref",
            "retrieval_payload",
            "production_data_payload",
            "payload.real_l4",
            "payload.acquired_observation_candidate",
            "fetched_payload",
            "masked_data",
        }
    ),
    "data_schema_ref": frozenset({"data_schema_ref"}),
    "evidence_ref": frozenset({"evidence_ref"}),
    "quality_report_ref": frozenset({"quality_report", "quality_report_ref"}),
    # No current DataSnapshot producer supplies these optional nested views.
    # An authority-selected parent with one present therefore remains unbound.
    "uncertainty_ref": frozenset(),
    "uncertainty_envelope_ref": frozenset(),
    "warnings_ref": frozenset({"warnings_ref"}),
    "input_bindings_ref": frozenset(),
}


def data_snapshot_reference_fields() -> tuple[str, ...]:
    """Return DataSnapshot fields whose values are typed artifact references.

    The field set is derived from the model annotations so a newly added
    reference field cannot silently evade parent-manifest lineage validation.
    """
    names: list[str] = []
    for name, field in DataSnapshot.model_fields.items():
        candidates = (field.annotation, *get_args(field.annotation))
        if any(
            isinstance(candidate, type)
            and issubclass(candidate, BaseModel)
            and {"artifact_id", "kind", "media_type"}.issubset(
                getattr(candidate, "model_fields", {})
            )
            for candidate in candidates
        ):
            names.append(name)
    return tuple(names)


def data_snapshot_reference_input_roles(field_name: str) -> frozenset[str]:
    """Return the producer roles observed for one DataSnapshot reference field.

    Roles are pinned to current source producers. An optional field with no
    producer role has an empty set and cannot be admitted in a selected parent
    view until a source producer and its lineage edge are implemented.
    """
    if field_name not in _DATA_SNAPSHOT_REFERENCE_INPUT_ROLES:
        raise ValueError(f"unknown DataSnapshot artifact-reference field: {field_name}")
    return _DATA_SNAPSHOT_REFERENCE_INPUT_ROLES[field_name]


def data_snapshot_owner_input_requirements(
    snapshot: DataSnapshot,
) -> tuple[tuple[ArtifactRef, str], ...]:
    """Derive exact direct refs and roles for a schema-0.3 owner snapshot.

    This is a typed transport contract, not by itself proof of completeness.
    Runtime consumers must reconcile these refs with the owning source artifact
    or its persisted owner binding before using them for a protected claim.
    """
    validated_snapshot = DataSnapshot.model_validate(snapshot.model_dump(mode="python"))
    lineage = validated_snapshot.source_lineage
    if lineage is None:
        raise ValueError("data_snapshot_owner_lineage_missing")

    field_roles: dict[str, str]
    optional_fields: frozenset[str] = frozenset()
    extra_refs: tuple[tuple[ArtifactRef, str], ...]
    if isinstance(lineage, MeasurementRootDataSnapshotLineage):
        field_roles = {"data_ref": "fetched_payload"}
        extra_refs = (
            (lineage.measurement_root_ref, "measurement_root"),
            (lineage.fetch_receipt_ref, "fabric_fetch"),
            (lineage.catalog_binding_ref, "catalog_binding"),
        )
    elif isinstance(lineage, FabricBridgeDataSnapshotLineage):
        field_roles = {
            "data_ref": "data_ref",
            "data_schema_ref": "data_schema_ref",
            "evidence_ref": "evidence_ref",
            "quality_report_ref": "quality_report_ref",
            "warnings_ref": "warnings_ref",
        }
        optional_fields = frozenset({"evidence_ref", "warnings_ref"})
        extra_refs = ((lineage.data_view_request_ref, "data_view_request_ref"),)
    elif isinstance(lineage, AcquiredObservationDataSnapshotLineage):
        field_roles = {"data_ref": "payload.acquired_observation_candidate"}
        extra_refs = (
            (lineage.base_data_snapshot_ref, "input.base_data_snapshot"),
            (lineage.overlay_admission_receipt_ref, "evidence.overlay_admission_receipt"),
            (lineage.passport_ref, "evidence.acquisition_passport"),
        )
    else:  # pragma: no cover - Pydantic's discriminated union owns this boundary.
        raise ValueError("data_snapshot_owner_lineage_unsupported")

    actual_refs = {
        name: getattr(validated_snapshot, name)
        for name in data_snapshot_reference_fields()
        if getattr(validated_snapshot, name) is not None
    }
    actual_fields = set(actual_refs)
    required_fields = set(field_roles) - optional_fields
    if not required_fields <= actual_fields or actual_fields - set(field_roles):
        raise ValueError("data_snapshot_owner_fields_do_not_match_lineage")
    requirements = [(ref, field_roles[field_name]) for field_name, ref in actual_refs.items()]
    requirements.extend(extra_refs)
    identities = [(ref.artifact_id, role) for ref, role in requirements]
    if len(identities) != len(set(identities)):
        raise ValueError("data_snapshot_owner_inputs_not_unique")
    return tuple(requirements)


def data_snapshot_manifest_inputs_match(
    snapshot: DataSnapshot,
    manifest_inputs: object,
    *,
    schema_version: str | None,
) -> bool:
    """Reconcile selected DataSnapshot parent edges to its typed source fields.

    Schema 0.2 uses the established field-to-role contract. Schema 0.3 uses
    the owner-specific typed edge set. The runtime owner verifier must still
    bind an owner-family snapshot to its producer payload; this predicate only
    checks the manifest's direct edges against the declared typed transport.
    """
    if not isinstance(manifest_inputs, list):
        return False
    if schema_version == DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION:
        if snapshot.source_lineage is None:
            return False
        try:
            requirements = data_snapshot_owner_input_requirements(snapshot)
        except (TypeError, ValueError):
            return False
        expected = [
            InputRef(
                artifact_id=ref.artifact_id,
                role=role,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for ref, role in requirements
        ]
        try:
            actual_keys = Counter(
                (row.role, str(row.artifact_id), row.manifest_profile_sha256)
                for row in manifest_inputs
            )
            expected_keys = Counter(
                (row.role, str(row.artifact_id), row.manifest_profile_sha256) for row in expected
            )
            return actual_keys == expected_keys
        except AttributeError:
            return False
    if (
        schema_version != DataSnapshot.ARTIFACT_SCHEMA_VERSION
        or snapshot.source_lineage is not None
    ):
        return False

    expected_fields = [
        (field_name, getattr(snapshot, field_name))
        for field_name in data_snapshot_reference_fields()
        if getattr(snapshot, field_name) is not None
    ]
    if len(manifest_inputs) != len(expected_fields):
        return False
    unmatched = set(range(len(manifest_inputs)))
    for field_name, ref in expected_fields:
        roles = data_snapshot_reference_input_roles(field_name)
        if not roles:
            return False
        matches = [
            index
            for index in unmatched
            if getattr(manifest_inputs[index], "artifact_id", None) == ref.artifact_id
            and getattr(manifest_inputs[index], "manifest_profile_sha256", None)
            == ref.manifest_profile_sha256
            and getattr(manifest_inputs[index], "role", None) in roles
        ]
        if len(matches) != 1:
            return False
        unmatched.remove(matches[0])

    # Historical 0.2 owner snapshots place some independently verifiable owner
    # edges directly in the manifest because the DTO did not yet carry a lineage
    # field. Recognize only those producer-declared role sets here; the Runtime
    # owner verifier must recover the refs from owner bytes and bind their IDs.
    extra_roles_by_payload_kind = {
        "fabric.fetch_payload": {"measurement_root", "fabric_fetch", "catalog_binding"},
        "fabric.tabular_payload": {"data_view_request_ref"},
        "fabric.production_data_state_payload": {
            "input.base_data_snapshot",
            "evidence.overlay_admission_receipt",
            "evidence.acquisition_passport",
        },
    }
    actual_extra_roles = [getattr(manifest_inputs[index], "role", None) for index in unmatched]
    expected_extra_roles = extra_roles_by_payload_kind.get(snapshot.data_ref.kind, set())
    if snapshot.data_ref.kind == "fabric.production_data_state_payload" and not actual_extra_roles:
        # The same artifact kind also serves ordinary L4 DataState payloads.
        # An acquired-overlay payload proves that owner family from its content;
        # the Runtime verifier refuses a marker-bearing payload with stripped edges.
        expected_extra_roles = set()
    return sorted(actual_extra_roles) == sorted(expected_extra_roles)


class RetrievalSummary(BaseModel):
    """Observed retrieval inputs without claiming that their quality was assessed."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.fabric.RetrievalSummary"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_KIND: ClassVar[Literal["fabric.retrieval_summary"]] = "fabric.retrieval_summary"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", strict=True)

    assessment_status: Literal["not_assessed"]
    source: StrictStr
    source_refs: list[ArtifactRef] = Field(min_length=1)
    observed_counts: dict[StrictStr, StrictInt] = Field(default_factory=dict)
    notes: list[StrictStr] = Field(default_factory=list)

    @field_validator("observed_counts")
    @classmethod
    def _require_nonnegative_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("retrieval summary counts must be nonnegative")
        return value
