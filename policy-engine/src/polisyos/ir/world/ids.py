"""Deterministic ID builders for world documents, claims, events, trust, and quality objects."""
from __future__ import annotations

import re
from enum import Enum
from typing import Any

from polisyos.ir.canon import CanonViolation, content_hash, to_canonical_bytes
from polisyos.ir.citations import FragmentLocator
from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN

_ARTIFACT_RE = re.compile(ARTIFACT_ID_PATTERN)
_ID_RE = re.compile(ID_PATTERN)
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_WORLD_ID_PAYLOAD_DEPTH = 128


def _validate_prefix(prefix: str) -> None:
    if _ID_RE.fullmatch(prefix) is None:
        raise ValueError(f"prefix '{prefix}' does not match {ID_PATTERN}")


def sha256_hex_from_artifact_id(artifact_id: str) -> str:
    """Extract the raw SHA-256 hex digest from a validated CAS artifact id."""
    if _ARTIFACT_RE.fullmatch(artifact_id) is None:
        raise ValueError(f"artifact_id '{artifact_id}' does not match {ARTIFACT_ID_PATTERN}")
    return artifact_id.split("sha256:", 1)[1]


def artifact_id_to_world_id(*, prefix: str, artifact_id: str) -> str:
    """Project a CAS artifact id into a deterministic world-id namespace prefix."""
    _validate_prefix(prefix)
    hex_digest = sha256_hex_from_artifact_id(artifact_id)
    return f"{prefix}.sha256_{hex_digest}"


def conflict_set_id_from_key(*, conflict_key: str) -> str:
    """Wrap a precomputed conflict digest in the stable ``cset.*`` world-id namespace."""
    if _SHA256_HEX_RE.fullmatch(conflict_key) is None:
        raise ValueError("conflict_key must be a 64-char lowercase hex sha256 digest")
    return f"cset.sha256_{conflict_key}"


def stable_world_id_from_canon(*, prefix: str, payload: dict[str, Any]) -> str:
    """Hash canonical payload bytes into a stable world id once the payload is finalized."""
    _validate_prefix(prefix)
    canonical = to_canonical_bytes(payload)
    digest = content_hash(canonical)
    return f"{prefix}.sha256_{digest}"


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _normalize_payload_value(
    value: Any,
    *,
    max_depth: int = _MAX_WORLD_ID_PAYLOAD_DEPTH,
    _depth: int = 0,
) -> Any:
    if _depth > max_depth:
        raise CanonViolation(f"World ID payload depth exceeds max_depth={max_depth}")
    value = _enum_value(value)
    if isinstance(value, dict):
        return {
            key: _normalize_payload_value(item, max_depth=max_depth, _depth=_depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _normalize_payload_value(item, max_depth=max_depth, _depth=_depth + 1)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _normalize_payload_value(item, max_depth=max_depth, _depth=_depth + 1)
            for item in value
        ]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _normalize_payload_value(
            model_dump(),
            max_depth=max_depth,
            _depth=_depth + 1,
        )
    return value


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def doc_source_id(
    *,
    canonical_url: str | None,
    official_id: str | None,
    source_kind: str | None = None,
) -> str:
    """Derive the stable world id for a document source from its canonical URL or official id."""
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
    """Derive the stable world id for a raw document artifact version."""
    return artifact_id_to_world_id(prefix="docv", artifact_id=raw_artifact_id)


def doc_fragment_id(
    *,
    doc_version_id: str,
    locator: FragmentLocator,
    text_artifact_id: str,
) -> str:
    """Hash a locator plus text artifact into the stable id for a document fragment."""
    payload = {
        "doc_version_id": doc_version_id,
        "locator": locator,
        "text_hash": text_artifact_id,
    }
    return stable_world_id_from_canon(prefix="frag", payload=payload)


def claim_id_from_payload(*, claim_payload: dict[str, Any]) -> str:
    """Derive a deterministic claim id from the canonicalized claim boundary payload."""
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
    """Derive the stable id for a world provenance event from its persisted payload."""
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


def trust_assessment_id_from_payload(*, payload: dict[str, Any]) -> str:
    """Derive the stable id for a trust assessment once its scoring inputs are fixed."""
    clean_payload: dict[str, Any] = {}
    for key in (
        "policy_id",
        "algorithm_version",
        "target_world_id",
        "score",
        "tier",
        "features",
        "rationale",
        "props",
    ):
        if key in payload:
            clean_payload[key] = _normalize_payload_value(payload[key])
    clean_payload = _strip_none(clean_payload)
    clean_payload.setdefault("features", {})
    clean_payload.setdefault("rationale", {})
    clean_payload.setdefault("props", {})
    return stable_world_id_from_canon(prefix="trust", payload=clean_payload)


def quality_report_id_from_payload(*, payload: dict[str, Any]) -> str:
    """Derive the stable id for a quality report once metrics, issues, and props are fixed."""
    clean_payload: dict[str, Any] = {}
    for key in (
        "scope",
        "run_event_id",
        "policy_id",
        "algorithm_version",
        "metrics",
        "issues",
        "props",
    ):
        if key in payload:
            clean_payload[key] = _normalize_payload_value(payload[key])
    clean_payload = _strip_none(clean_payload)
    clean_payload.setdefault("metrics", {})
    clean_payload.setdefault("issues", [])
    clean_payload.setdefault("props", {})
    return stable_world_id_from_canon(prefix="quality", payload=clean_payload)


__all__ = [
    "artifact_id_to_world_id",
    "claim_id_from_payload",
    "conflict_set_id_from_key",
    "doc_fragment_id",
    "doc_source_id",
    "doc_version_id_from_raw_artifact",
    "quality_report_id_from_payload",
    "sha256_hex_from_artifact_id",
    "stable_world_id_from_canon",
    "trust_assessment_id_from_payload",
    "world_event_id_from_payload",
]
