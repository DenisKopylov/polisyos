from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef, WarningRecord
from .uncertainty import UncertaintyEnvelopeRef


class DataViewRequestRef(ArtifactRef):
    kind: Literal["ir.data_view_request"] = "ir.data_view_request"
    media_type: Literal["application/json"] = "application/json"


class QueryPlanRef(ArtifactRef):
    kind: Literal["fabric.query_plan"] = "fabric.query_plan"
    media_type: Literal["application/json"] = "application/json"


class FabricResultRef(ArtifactRef):
    kind: Literal["fabric.result_bundle"] = "fabric.result_bundle"
    media_type: Literal["application/json"] = "application/json"


class EvidenceBundleRef(ArtifactRef):
    kind: Literal["fabric.evidence_bundle"] = "fabric.evidence_bundle"
    media_type: Literal["application/json"] = "application/json"


class UncertaintyBoundsRef(ArtifactRef):
    kind: Literal["fabric.uncertainty_bounds"] = "fabric.uncertainty_bounds"
    media_type: Literal["application/json"] = "application/json"


class WarningsRef(ArtifactRef):
    kind: Literal["fabric.warnings"] = "fabric.warnings"
    media_type: Literal["application/json"] = "application/json"


class DataSnapshotRef(ArtifactRef):
    kind: Literal["fabric.data_snapshot"] = "fabric.data_snapshot"
    media_type: Literal["application/json"] = "application/json"


class QueryPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: str
    params: dict[str, str | int | bool] = Field(default_factory=dict)


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_ref: DataViewRequestRef
    engine: str
    steps: list[QueryPlanStep] = Field(default_factory=list)
    trust_policy_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class EvidenceStep(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    sources: list[ArtifactRef] = Field(default_factory=list)
    transforms: list[EvidenceStep] = Field(default_factory=list)
    trust_policy_id: str | None = None
    notes: list[str] = Field(default_factory=list)
    provenance_ref: ProvenanceCoreRefModel | None = None
    quality_indicators: dict[str, dict] | None = None


class UncertaintyBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    value: Decimal
    lower: Decimal
    upper: Decimal
    method: str = "two_pass_compare"


class WarningsBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warnings: list[WarningRecord] = Field(default_factory=list)


class FabricResult(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    data_ref: ArtifactRef
    data_schema_ref: ArtifactRef | None = None
    evidence_ref: EvidenceBundleRef | None = None
    uncertainty_ref: UncertaintyBoundsRef | None = None
    uncertainty_envelope_ref: UncertaintyEnvelopeRef | None = None
    warnings_ref: WarningsRef | None = None
    pii_scan_summary: dict[str, Any] | None = None
    stats: dict[str, int | str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
