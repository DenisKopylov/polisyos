from __future__ import annotations

from pathlib import Path

from polisyos.core.contracts.scholar import SourceSpec
from polisyos.fabric.docs import DocSourceSpec

from polisyos.scholar.errors import ScholarAcquireError, ScholarValidationError
from polisyos.scholar.types import AcquireResult

_MIME_BY_SUFFIX = {
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
}


def _doc_source_from_source(
    source: SourceSpec,
    *,
    canonical_url: str | None,
    official_id: str | None,
    source_locator: str | None,
) -> DocSourceSpec:
    props = source.props
    return DocSourceSpec(
        canonical_url=canonical_url,
        official_id=official_id,
        source_locator=source_locator,
        license=source.license,
        jurisdiction=props.get("jurisdiction"),
        language=props.get("language"),
        source_type=props.get("source_type"),
        title=props.get("title"),
        publisher=props.get("publisher"),
    )


def read_local_file(source: SourceSpec, *, max_bytes: int | None) -> AcquireResult:
    if source.kind != "local_file":
        raise ScholarValidationError(
            "read_local_file expects kind=local_file",
            stage="acquire",
            source_identity=source.source_locator,
        )

    if source.path is None:
        raise ScholarValidationError(
            "local_file source requires path",
            stage="acquire",
            source_identity=source.source_locator,
        )

    path = Path(source.path)
    if not path.exists() or not path.is_file():
        raise ScholarAcquireError(
            f"local file not found: {path}",
            source_identity=source.source_locator,
            details={"path": str(path)},
        )

    raw_bytes = path.read_bytes()
    if max_bytes is not None and len(raw_bytes) > max_bytes:
        raise ScholarAcquireError(
            "local file exceeds max_bytes_per_doc",
            source_identity=source.source_locator,
            details={"bytes": len(raw_bytes), "max_bytes": max_bytes},
        )

    mime = _MIME_BY_SUFFIX.get(path.suffix.lower())
    if mime is None:
        if source.mime_hint:
            mime = source.mime_hint.strip()
        else:
            raise ScholarAcquireError(
                "unsupported local file extension; set mime_hint explicitly",
                source_identity=source.source_locator,
                details={"path": str(path), "suffix": path.suffix.lower()},
            )

    source_locator = source.source_locator or str(path.expanduser().resolve())
    doc_source = _doc_source_from_source(
        source,
        canonical_url=None,
        official_id=None,
        source_locator=source_locator,
    )
    return AcquireResult(
        source=source,
        source_identity=source_locator,
        raw_bytes=raw_bytes,
        mime=mime,
        doc_source=doc_source,
    )


__all__ = ["read_local_file"]
