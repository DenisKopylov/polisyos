from __future__ import annotations

from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.lex.corpus.ingest import ingest_legal_doc_bytes as _ingest_legal_doc_bytes
from polisyos.lex.corpus.structure import build_legal_structure as _build_legal_structure
from polisyos.lex.corpus.versioning import (
    build_version_index as _build_version_index,
)
from polisyos.lex.corpus.versioning import (
    resolve_active_version as _resolve_active_version,
)
from polisyos.lex.types import (
    ActiveVersionResult,
    ActiveVersionStrategy,
    LegalDocSource,
    LexIngestOptions,
    LexIngestResult,
    LexStructureOptions,
    LexStructureResult,
    LexVersionIndexOptions,
    LexVersionIndexResult,
)


def ingest_legal_doc_bytes(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    source: LegalDocSource,
    raw_bytes: bytes,
    mime: str,
    options: LexIngestOptions | None = None,
    segment_name: str | None = None,
) -> LexIngestResult:
    return _ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=fact_log_root,
        source=source,
        raw_bytes=raw_bytes,
        mime=mime,
        options=options,
        segment_name=segment_name,
    )


def build_legal_structure(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: LexStructureOptions | None = None,
    segment_name: str | None = None,
) -> LexStructureResult:
    return _build_legal_structure(
        cas=cas,
        fact_log_root=fact_log_root,
        doc_meta_artifact_id=doc_meta_artifact_id,
        options=options,
        segment_name=segment_name,
    )


def build_version_index(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_source_id: str,
    options: LexVersionIndexOptions | None = None,
    segment_name: str | None = None,
) -> LexVersionIndexResult:
    return _build_version_index(
        cas=cas,
        fact_log_root=fact_log_root,
        doc_source_id=doc_source_id,
        options=options,
        segment_name=segment_name,
    )


def resolve_active_version(
    *,
    cas: FileSystemCAS,
    doc_source_id: str,
    as_of_iso: str,
    strategy: ActiveVersionStrategy | None = None,
) -> ActiveVersionResult:
    return _resolve_active_version(
        cas=cas,
        doc_source_id=doc_source_id,
        as_of_iso=as_of_iso,
        strategy=strategy,
    )


__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "LegalDocSource",
    "LexIngestOptions",
    "LexIngestResult",
    "LexStructureOptions",
    "LexStructureResult",
    "LexVersionIndexOptions",
    "LexVersionIndexResult",
    "build_legal_structure",
    "build_version_index",
    "ingest_legal_doc_bytes",
    "resolve_active_version",
]
