"""Public claims types module API."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from polisyos.ir.fact_log import FactSegmentManifest


@dataclass(frozen=True)
class ClaimExtractOptions:
    """Claim extract options data model."""
    require_chunks: bool = True
    max_chunks: int | None = None
    extract_mode: Literal["chunks_only", "structure_then_chunks"] = "chunks_only"
    agent_id: str = "prov.agent.fabric_claims"
    activity_id: str = "prov.activity.fabric_claims.extract"
    build_evidence: bool = True
    evidence_schema_name: str = "fabric.evidence.claim_extract_v1"
    evidence_schema_version: str = "1.0"
    claim_set_kind: str = "fabric.claims.claim_set"
    claim_set_schema_name: str = "fabric.claims.claim_set"
    claim_set_schema_version: str = "1.0"
    max_claims_total: int | None = None
    max_claims_per_chunk: int | None = None


@dataclass(frozen=True)
class ClaimNormalizeOptions:
    """Claim normalize options data model."""
    normalize_units: bool = True
    normalize_predicates: bool = True
    parse_numeric: bool = True
    canonicalize_numeric_value_text: bool = True
    drop_invalid: bool = True
    agent_id: str = "prov.agent.fabric_claims"
    activity_id: str = "prov.activity.fabric_claims.normalize"
    build_evidence: bool = True
    evidence_schema_name: str = "fabric.evidence.claim_normalize_v1"
    evidence_schema_version: str = "1.0"
    claim_set_kind: str = "fabric.claims.claim_set"
    claim_set_schema_name: str = "fabric.claims.claim_set"
    claim_set_schema_version: str = "1.0"


@dataclass(frozen=True)
class ClaimExtractResult:
    """Claim extract result data model."""
    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    normalized_ref: str
    chunks_ref: str
    claim_set_artifact_id: str
    claim_ids: list[str]
    world_event_id: str
    world_event_artifact_id: str
    evidence_ref: str | None
    world_segment_manifest: FactSegmentManifest


@dataclass(frozen=True)
class ClaimNormalizeResult:
    """Claim normalize result data model."""
    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    normalized_ref: str
    chunks_ref: str
    input_claim_set_artifact_id: str
    claim_set_artifact_id: str
    claim_ids: list[str]
    world_event_id: str
    world_event_artifact_id: str
    evidence_ref: str | None
    world_segment_manifest: FactSegmentManifest
    derived_edges: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkContext:
    """Chunk context public type."""
    fragment_id: str
    doc_version_id: str
    offset_start: int
    offset_end: int
    text_preview: str


@dataclass(frozen=True)
class ClaimCandidate:
    """Claim candidate public type."""
    predicate_id: str
    value_text: str
    citation_fragment_id: str
    subject_id: str | None = None
    subject_text: str | None = None
    value_decimal: Decimal | None = None
    unit_id: str | None = None
    confidence: Decimal | None = None
    qualifiers: dict[str, str | int | bool] = field(default_factory=dict)
    props: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ClaimCandidate",
    "ClaimExtractOptions",
    "ClaimExtractResult",
    "ClaimNormalizeOptions",
    "ClaimNormalizeResult",
    "ChunkContext",
]
