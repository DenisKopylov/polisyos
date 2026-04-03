"""Public store ids module API."""
from __future__ import annotations

import re

from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN
from polisyos.ir.world.ids import (
    artifact_id_to_world_id,
    claim_id_from_payload,
    doc_fragment_id,
    doc_source_id,
    doc_version_id_from_raw_artifact,
    world_event_id_from_payload,
)

from .errors import WorldIDError

_ID_RE = re.compile(ID_PATTERN)
_ARTIFACT_RE = re.compile(ARTIFACT_ID_PATTERN)


def ensure_world_id(value: str, *, field: str = "id") -> str:
    """Ensure world ID helper."""
    if _ID_RE.fullmatch(value) is None:
        raise WorldIDError(f"{field} '{value}' does not match {ID_PATTERN}")
    return value


def ensure_artifact_id(value: str, *, field: str = "artifact_id") -> str:
    """Ensure artifact ID helper."""
    if _ARTIFACT_RE.fullmatch(value) is None:
        raise WorldIDError(f"{field} '{value}' does not match {ARTIFACT_ID_PATTERN}")
    return value


__all__ = [
    "artifact_id_to_world_id",
    "claim_id_from_payload",
    "doc_fragment_id",
    "doc_source_id",
    "doc_version_id_from_raw_artifact",
    "ensure_artifact_id",
    "ensure_world_id",
    "world_event_id_from_payload",
]
