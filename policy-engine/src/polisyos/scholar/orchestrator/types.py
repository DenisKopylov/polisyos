"""Define internal DTOs and artifact-reference collections for Scholar orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from polisyos.core.contracts.scholar import SourceSpec

if TYPE_CHECKING:
    from polisyos.fabric.docs import DocSourceSpec


@dataclass(frozen=True)
class AcquireResult:
    """Carry one fetched raw source plus normalized source metadata."""

    source: SourceSpec
    source_identity: str
    raw_bytes: bytes
    mime: str
    doc_source: DocSourceSpec


@dataclass(frozen=True)
class DocPipelineRefs:
    """Collect persisted document-processing artifact IDs for one source document."""

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
    """Collect claim extraction/normalization artifacts and quality report IDs."""

    claim_set_artifact_id: str
    normalized_claim_set_artifact_id: str
    claim_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    quality_report_ids: list[str] = field(default_factory=list)
    quality_report_artifact_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReconcileRefs:
    """Collect conflict resolution and trust assessment artifacts."""

    conflict_set_ids: list[str] = field(default_factory=list)
    conflict_set_artifact_ids: list[str] = field(default_factory=list)
    winner_by_conflict_set: dict[str, str] = field(default_factory=dict)
    conflict_resolution_artifact_ids: list[str] = field(default_factory=list)
    trust_assessment_ids: list[str] = field(default_factory=list)
    trust_assessment_artifact_ids_by_id: dict[str, str] = field(default_factory=dict)
    quality_report_ids: list[str] = field(default_factory=list)
    quality_report_artifact_ids: list[str] = field(default_factory=list)


__all__ = [
    "AcquireResult",
    "ClaimsPipelineRefs",
    "DocPipelineRefs",
    "ReconcileRefs",
    "SourceSpec",
]
