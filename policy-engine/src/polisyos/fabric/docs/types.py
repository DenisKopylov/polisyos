"""Document pipeline contracts shared by Fabric ingestion, normalization, structure, and chunking.

These dataclasses define the boundary between raw source acquisition and downstream claim/legal
pipelines. Every result object carries both the latest ``DocMeta`` artifact id and the world-event
segment emitted by the stage so provenance remains attached to normalized text, anchors, and
chunks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from polisyos.ir.fact_log import FactSegmentManifest

from .errors import DocValidationError


@dataclass(frozen=True)
class DocSourceSpec:
    """Canonical source identity and metadata for one ingested document.

    Exactly one locator must be set among ``canonical_url``, ``official_id``, and
    ``source_locator``. ``license`` is required because persisted ``DocMeta`` records are reused
    by downstream legal and academic pipelines.
    """
    canonical_url: str | None = None
    official_id: str | None = None
    source_locator: str | None = None
    license: str | None = None
    retrieved_at: datetime | None = None
    jurisdiction: str | None = None
    language: str | None = None
    source_type: str | None = None
    title: str | None = None
    publisher: str | None = None

    def __post_init__(self) -> None:
        identity_fields = [
            self.canonical_url,
            self.official_id,
            self.source_locator,
        ]
        provided = [value for value in identity_fields if value]
        if len(provided) != 1:
            raise DocValidationError(
                "exactly one of canonical_url, official_id, or source_locator is required"
            )
        if not self.license:
            raise DocValidationError("license is required for DocSourceSpec")


@dataclass(frozen=True)
class DocIngestOptions:
    """Persistence and provenance options for raw document ingestion."""
    raw_kind: str = "fabric.doc.raw"
    enforce_max_bytes: int | None = None
    agent_id: str = "prov.agent.fabric_docs"
    activity_id: str = "prov.activity.fabric_docs.ingest"


@dataclass(frozen=True)
class DocNormalizeOptions:
    """Text extraction and whitespace normalization options for raw document payloads."""
    normalized_kind: str = "fabric.doc.normalized"
    encoding_order: list[str] = field(default_factory=lambda: ["utf-8", "utf-8-sig", "latin-1"])
    errors: str = "strict"
    normalize_newlines: bool = True
    strip_trailing_whitespace: bool = False
    collapse_blank_lines: bool = False
    html_extract_mode: Literal["visible_text_v1"] = "visible_text_v1"


@dataclass(frozen=True)
class DocStructureOptions:
    """Options for generic heading/section anchor extraction from normalized text."""
    structure_kind: str = "fabric.doc.structure"
    algorithm: Literal["anchors_v1"] = "anchors_v1"
    max_heading_len: int = 160
    min_section_chars: int = 200
    include_full_document_anchor: bool = True


@dataclass(frozen=True)
class DocChunkOptions:
    """Options for chunk generation over normalized text with optional paragraph boundaries."""
    chunks_kind: str = "fabric.doc.chunks"
    algorithm: Literal["char_chunks_v1"] = "char_chunks_v1"
    chunk_size_chars: int = 2000
    overlap_chars: int = 200
    min_chunk_chars: int = 200
    boundary: Literal["fixed", "paragraph"] = "fixed"


@dataclass(frozen=True)
class DocIngestResult:
    """Result contract for the raw ingest stage and its emitted provenance references."""
    doc_source_id: str
    doc_version_id: str
    raw_ref: str
    normalized_ref: str | None
    structure_ref: str | None
    chunks_ref: str | None
    doc_meta_artifact_id: str
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest


@dataclass(frozen=True)
class DocNormalizeResult:
    """Result contract for normalized text generation and updated ``DocMeta`` persistence."""
    doc_source_id: str
    doc_version_id: str
    raw_ref: str
    normalized_ref: str
    structure_ref: str | None
    chunks_ref: str | None
    doc_meta_artifact_id: str
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest


@dataclass(frozen=True)
class DocStructureResult:
    """Result contract for generated document anchors and fragment ids."""
    doc_source_id: str
    doc_version_id: str
    raw_ref: str
    normalized_ref: str
    structure_ref: str
    chunks_ref: str | None
    doc_meta_artifact_id: str
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest
    fragment_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocChunkResult:
    """Result contract for chunk artifacts and chunk-backed ``DocFragment`` ids."""
    doc_source_id: str
    doc_version_id: str
    raw_ref: str
    normalized_ref: str
    structure_ref: str | None
    chunks_ref: str
    doc_meta_artifact_id: str
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest
    chunk_fragment_ids: list[str] = field(default_factory=list)


__all__ = [
    "DocChunkOptions",
    "DocChunkResult",
    "DocIngestOptions",
    "DocIngestResult",
    "DocNormalizeOptions",
    "DocNormalizeResult",
    "DocSourceSpec",
    "DocStructureOptions",
    "DocStructureResult",
]
