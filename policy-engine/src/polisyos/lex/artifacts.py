"""Lex-owned readers for runtime legal artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.world import validate_doc_meta_ids
from polisyos.ir.world.doc import DocMeta
from polisyos.lex.errors import LexValidationError

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS

def load_json_artifact(
    cas: FileSystemCAS,
    artifact_id: str,
    *,
    error_cls: type[Exception] = LexValidationError,
    payload_label: str = "artifact",
    wrap_read_errors: bool = False,
    read_error_prefix: str | None = None,
) -> dict:
    """Load a JSON-object artifact with Lex caller-selected error semantics."""
    try:
        aid = ArtifactID.model_validate(artifact_id)
        payload = from_canonical_bytes(cas.get_bytes(aid))
    except Exception as exc:
        if not wrap_read_errors:
            raise
        prefix = read_error_prefix or f"failed to read {payload_label}"
        raise error_cls(f"{prefix} {artifact_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise error_cls(f"{payload_label} {artifact_id} payload must be a JSON object")
    return payload


def load_doc_meta_artifact(
    cas: FileSystemCAS,
    artifact_id: str,
    *,
    error_cls: type[Exception] = LexValidationError,
    payload_label: str = "artifact",
    wrap_read_errors: bool = False,
    read_error_prefix: str | None = None,
    validate_ids: bool = False,
) -> DocMeta:
    """Load a document metadata artifact with optional identity validation."""
    payload = load_json_artifact(
        cas,
        artifact_id,
        error_cls=error_cls,
        payload_label=payload_label,
        wrap_read_errors=wrap_read_errors,
        read_error_prefix=read_error_prefix,
    )
    meta = DocMeta.model_validate(payload)
    if validate_ids:
        validate_doc_meta_ids(meta)
    return meta


__all__ = ["load_doc_meta_artifact", "load_json_artifact"]
