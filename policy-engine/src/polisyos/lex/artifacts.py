"""Public lex artifacts module API."""
from __future__ import annotations

from typing import TypeVar

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.world import validate_doc_meta_ids
from polisyos.ir.world.doc import DocMeta
from polisyos.lex.errors import LexValidationError

_E = TypeVar("_E", bound=Exception)

__all__ = ["load_doc_meta_artifact", "load_json_artifact"]


def load_json_artifact(
    cas: FileSystemCAS,
    artifact_id: str,
    *,
    error_cls: type[_E] = LexValidationError,
    payload_label: str = "artifact",
    wrap_read_errors: bool = False,
    read_error_prefix: str | None = None,
) -> dict:
    """Load json artifact."""
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
    error_cls: type[_E] = LexValidationError,
    payload_label: str = "artifact",
    wrap_read_errors: bool = False,
    read_error_prefix: str | None = None,
    validate_ids: bool = False,
) -> DocMeta:
    """Load doc meta artifact."""
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
