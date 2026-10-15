"""Stable DTOs for Fabric query planning, evidence bundles, and materialized data views."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from ..artifacts.manifest import ArtifactRef, WarningRecord
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


class DataSnapshot(BaseModel):
    """Snapshot of retrieved data plus the artifact references needed to audit its quality."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.DataSnapshot"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "0.2.0"
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
    pii_scan_summary: dict[str, Any] | None = None
    stats: dict[str, int | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


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
