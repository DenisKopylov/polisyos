"""Claim extraction, normalization, and result contracts for Fabric document pipelines.

These dataclasses describe how extractors consume chunked text, how normalization rewrites claim
payloads into canonical ids/units/numeric forms, and how both stages expose artifact/world-event
references for conflict resolution and downstream NormPack assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from polisyos.ir.fact_log import FactSegmentManifest


@dataclass(frozen=True)
class ClaimExtractOptions:
    """Extraction controls for chunk-based claim parsers and generated evidence bundles."""

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
    """Canonicalization controls for predicates, units, numeric values, and invalid-claim handling."""

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
    quarantine_invalid: bool = True
    quarantine_retry_policy: dict[str, Any] = field(
        default_factory=lambda: {
            "mode": "deterministic_reprocess",
            "max_attempts": 1,
        }
    )


@dataclass(frozen=True)
class ClaimExtractResult:
    """Result contract for claim-set extraction and its associated world/evidence artifacts."""

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
    """Result contract for normalized claim sets and ``PROV_WAS_DERIVED_FROM`` edges."""

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
    quarantine_record_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkContext:
    """Read-only chunk slice passed to extractor backends with provenance-safe fragment ids."""

    fragment_id: str
    doc_version_id: str
    offset_start: int
    offset_end: int
    text_preview: str


@dataclass(frozen=True)
class ClaimCandidate:
    """Extractor-emitted claim candidate before canonical claim-id normalization."""

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
    "ChunkContext",
    "ClaimCandidate",
    "ClaimExtractOptions",
    "ClaimExtractResult",
    "ClaimNormalizeOptions",
    "ClaimNormalizeResult",
]
