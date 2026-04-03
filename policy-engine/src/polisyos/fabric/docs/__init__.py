"""Public fabric docs package API."""
from __future__ import annotations

from .chunking import chunk_doc
from .errors import (
    DocNotReadyError,
    DocPipelineError,
    DocUnsupportedMimeError,
    DocValidationError,
)
from .ingestion import ingest_doc_bytes
from .normalize import normalize_doc
from .structure import structure_doc
from .types import (
    DocChunkOptions,
    DocChunkResult,
    DocIngestOptions,
    DocIngestResult,
    DocNormalizeOptions,
    DocNormalizeResult,
    DocSourceSpec,
    DocStructureOptions,
    DocStructureResult,
)

__all__ = [
    "DocChunkOptions",
    "DocChunkResult",
    "DocIngestOptions",
    "DocIngestResult",
    "DocNormalizeOptions",
    "DocNormalizeResult",
    "DocNotReadyError",
    "DocPipelineError",
    "DocSourceSpec",
    "DocStructureOptions",
    "DocStructureResult",
    "DocUnsupportedMimeError",
    "DocValidationError",
    "chunk_doc",
    "ingest_doc_bytes",
    "normalize_doc",
    "structure_doc",
]
