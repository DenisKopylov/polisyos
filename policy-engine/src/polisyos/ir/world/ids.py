from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any

from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.citations import FragmentLocator
from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN

_ARTIFACT_RE = re.compile(ARTIFACT_ID_PATTERN)
_ID_RE = re.compile(ID_PATTERN)


def _validate_prefix(prefix: str) -> None:
    if _ID_RE.fullmatch(prefix) is None:
        raise ValueError(f"prefix '{prefix}' does not match {ID_PATTERN}")


def sha256_hex_from_artifact_id(artifact_id: str) -> str:
    if _ARTIFACT_RE.fullmatch(artifact_id) is None:
        raise ValueError(f"artifact_id '{artifact_id}' does not match {ARTIFACT_ID_PATTERN}")
    return artifact_id.split("sha256:", 1)[1]


def artifact_id_to_world_id(*, prefix: str, artifact_id: str) -> str:
    _validate_prefix(prefix)
    hex_digest = sha256_hex_from_artifact_id(artifact_id)
    return f"{prefix}.sha256_{hex_digest}"


def stable_world_id_from_canon(*, prefix: str, payload: dict[str, Any]) -> str:
    _validate_prefix(prefix)
    canonical = to_canonical_bytes(payload)
    digest = hashlib.sha256(canonical).hexdigest()
    return f"{prefix}.sha256_{digest}"


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _normalize_payload_value(value: Any) -> Any:
    value = _enum_value(value)
    if isinstance(value, dict):
        return {key: _normalize_payload_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_payload_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_payload_value(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _normalize_payload_value(model_dump())
    return value


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def doc_source_id(
    *,
    canonical_url: str | None,
    official_id: str | None,
    source_kind: str | None = None,
) -> str:
    if (canonical_url is None) == (official_id is None):
        raise ValueError("exactly one of canonical_url or official_id is required")
    payload: dict[str, Any] = {}
    if canonical_url is not None:
        payload["canonical_url"] = canonical_url
    if official_id is not None:
        payload["official_id"] = official_id
    if source_kind is not None:
        payload["source_kind"] = source_kind
    return stable_world_id_from_canon(prefix="doc", payload=payload)


def doc_version_id_from_raw_artifact(*, raw_artifact_id: str) -> str:
    return artifact_id_to_world_id(prefix="docv", artifact_id=raw_artifact_id)


def doc_fragment_id(
    *,
    doc_version_id: str,
    locator: FragmentLocator,
    text_artifact_id: str,
) -> str:
    payload = {
        "doc_version_id": doc_version_id,
        "locator": locator,
        "text_hash": text_artifact_id,
    }
    return stable_world_id_from_canon(prefix="frag", payload=payload)


def claim_id_from_payload(*, claim_payload: dict[str, Any]) -> str:
    source_kind = _enum_value(claim_payload.get("source_kind"))
    payload: dict[str, Any] = {}
    for key in (
        "predicate_id",
        "subject_id",
        "subject_text",
        "value_text",
        "value_decimal",
        "unit_id",
        "jurisdiction",
        "domain",
        "valid_from",
        "valid_to",
        "qualifiers",
    ):
        if key in claim_payload:
            payload[key] = _normalize_payload_value(claim_payload[key])
    if source_kind == "doc":
        if "citations" in claim_payload:
            payload["citations"] = _normalize_payload_value(claim_payload["citations"])
    else:
        if "source_artifacts" in claim_payload:
            payload["source_artifacts"] = _normalize_payload_value(
                claim_payload["source_artifacts"]
            )
    payload = _strip_none(payload)
    payload.setdefault("qualifiers", {})
    return stable_world_id_from_canon(prefix="claim", payload=payload)


def world_event_id_from_payload(*, event_payload: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    for key in (
        "event_kind",
        "agent",
        "activity",
        "inputs",
        "outputs",
        "evidence_ref",
        "provenance_ref",
    ):
        if key in event_payload:
            payload[key] = _normalize_payload_value(event_payload[key])
    if "event_kind" in payload:
        payload["event_kind"] = _enum_value(payload["event_kind"])
    payload = _strip_none(payload)
    payload.setdefault("inputs", [])
    payload.setdefault("outputs", [])
    return stable_world_id_from_canon(prefix="event", payload=payload)


__all__ = [
    "artifact_id_to_world_id",
    "claim_id_from_payload",
    "doc_fragment_id",
    "doc_source_id",
    "doc_version_id_from_raw_artifact",
    "sha256_hex_from_artifact_id",
    "stable_world_id_from_canon",
    "world_event_id_from_payload",
]
