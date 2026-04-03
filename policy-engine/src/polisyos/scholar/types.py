"""Public scholar types module API."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.scholar import (
    BudgetsV1,
    EnrichmentReportRef,
    FreshnessMetadata,
    KnowledgeBundleRef,
    SourceKind,
    SourceSpec,
    ThresholdsV1,
)
from polisyos.fabric.docs import DocSourceSpec


@dataclass(frozen=True)
class AcquireResult:
    """Acquire result data model."""
    source: SourceSpec
    source_identity: str
    raw_bytes: bytes
    mime: str
    doc_source: DocSourceSpec


@dataclass(frozen=True)
class DocPipelineRefs:
    """Doc pipeline refs public type."""
    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    normalized_ref: str | None
    structure_ref: str | None
    chunks_ref: str | None
    fragment_count: int = 0
    chunk_fragment_count: int = 0


@dataclass(frozen=True)
class ClaimsPipelineRefs:
    """Claims pipeline refs public type."""
    claim_set_artifact_id: str
    normalized_claim_set_artifact_id: str
    claim_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    quality_report_ids: list[str] = field(default_factory=list)
    quality_report_artifact_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReconcileRefs:
    """Reconcile refs public type."""
    conflict_set_ids: list[str] = field(default_factory=list)
    conflict_set_artifact_ids: list[str] = field(default_factory=list)
    winner_by_conflict_set: dict[str, str] = field(default_factory=dict)
    conflict_resolution_artifact_ids: list[str] = field(default_factory=list)
    trust_assessment_ids: list[str] = field(default_factory=list)
    trust_assessment_artifact_ids_by_id: dict[str, str] = field(default_factory=dict)
    quality_report_ids: list[str] = field(default_factory=list)
    quality_report_artifact_ids: list[str] = field(default_factory=list)


class KnowledgeBundlePayloadV1(BaseModel):
    """Knowledge bundle payload V 1 public type."""
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    bundle_id: str
    intent: dict[str, Any] = Field(default_factory=dict)

    doc_meta_artifact_ids: list[str] = Field(default_factory=list)
    doc_version_ids: list[str] = Field(default_factory=list)
    doc_source_ids: list[str] = Field(default_factory=list)

    claim_ids: list[str] = Field(default_factory=list)
    claim_set_artifact_ids: list[str] = Field(default_factory=list)

    conflict_set_ids: list[str] = Field(default_factory=list)
    conflict_set_artifact_ids: list[str] = Field(default_factory=list)
    conflict_resolution_artifact_ids: list[str] = Field(default_factory=list)

    trust_assessment_ids: list[str] = Field(default_factory=list)
    trust_assessment_artifact_ids_by_id: dict[str, str] = Field(default_factory=dict)

    quality_report_ids: list[str] = Field(default_factory=list)
    quality_report_artifact_ids: list[str] = Field(default_factory=list)

    policy_ids_used: dict[str, str] = Field(default_factory=dict)
    created_by: dict[str, str] = Field(default_factory=dict)
    summary: dict[str, int | str | bool] = Field(default_factory=dict)
    freshness: FreshnessMetadata = Field(default_factory=FreshnessMetadata)


class EnrichmentReportV1(BaseModel):
    """Enrichment report V 1 public type."""
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    bundle_artifact_id: str
    bundle_id: str

    docs: dict[str, Any] = Field(default_factory=dict)
    claims: dict[str, Any] = Field(default_factory=dict)
    conflicts: dict[str, Any] = Field(default_factory=dict)
    trust: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class EnrichResultV1:
    """Enrich result V 1 public type."""
    knowledge_bundle_ref: KnowledgeBundleRef
    bundle_id: str
    report: EnrichmentReportV1
    report_ref: EnrichmentReportRef | None = None


__all__ = [
    "AcquireResult",
    "BudgetsV1",
    "ClaimsPipelineRefs",
    "DocPipelineRefs",
    "EnrichResultV1",
    "EnrichmentReportV1",
    "KnowledgeBundlePayloadV1",
    "ReconcileRefs",
    "SourceKind",
    "SourceSpec",
    "ThresholdsV1",
]
