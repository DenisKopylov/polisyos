"""High-level helpers for persisting and loading JSON artifacts through the IR CAS boundary."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.ir.model_layer.canon import (
    CanonSpec,
    CanonViolation,
    from_canonical_bytes,
    to_canonical_bytes,
)

from .contracts import (
    ArtifactID,
    ArtifactSelector,
    ArtifactStore,
    CanonInfo,
    InputRef,
    PutOptions,
    SchemaInfo,
    normalize_artifact_ref,
    normalize_input_refs,
    to_store_put_options,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


_PROFILE_SELECTOR_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def put_json_artifact(
    store: ArtifactStore,
    payload: Any,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: Sequence[Any] | None = None,
    canon_spec: CanonSpec | None = None,
) -> dict[str, str]:
    """Persist JSON plus schema/canonical metadata and return a normalized artifact reference."""
    canon_spec = canon_spec or CanonSpec()
    options = PutOptions(
        kind=kind,
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version=schema_version),
        inputs=normalize_input_refs(inputs),
        canon=CanonInfo.from_spec(canon_spec),
    )
    ref = store.put_json(
        payload,
        opts=to_store_put_options(options),
        canon_spec=canon_spec,
    )
    return normalize_artifact_ref(ref)


def _validated_ir_canon_info(value: Any) -> CanonInfo:
    """Validate a complete profile mapping parsed from the raw persisted sidecar."""
    if not isinstance(value, Mapping):
        raise CanonViolation("unsupported_ir_canon_profile")
    payload = dict(value)
    if set(CanonInfo.model_fields) - set(payload):
        raise CanonViolation("unsupported_ir_canon_profile")
    separators = payload.get("separators")
    if (
        type(separators) is list
        and len(separators) == 2
        and all(type(separator) is str for separator in separators)
    ):
        payload["separators"] = tuple(separators)
    try:
        profile = CanonInfo.model_validate(payload, strict=True)
    except (TypeError, ValueError) as exc:
        raise CanonViolation("unsupported_ir_canon_profile") from exc

    supported = CanonInfo()
    if (
        profile.name != supported.name
        or profile.version != supported.version
        or profile.max_depth < 0
    ):
        raise CanonViolation("unsupported_ir_canon_profile")
    return profile


def _duplicate_key_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object and refuse ambiguous duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    """Reject non-JSON numeric constants accepted by Python's permissive decoder."""
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _artifact_selector(value: ArtifactSelector) -> ArtifactSelector:
    """Validate an artifact ID or typed selected-view ref without dropping its selector."""
    if isinstance(value, (ArtifactID, str)) or isinstance(getattr(value, "root", None), str):
        return ArtifactID.model_validate(str(value))

    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        payload = {
            field_name: getattr(value, field_name, None)
            for field_name in (
                "artifact_id",
                "kind",
                "media_type",
                "manifest_profile_sha256",
            )
            if hasattr(value, field_name)
        }
    allowed_fields = {
        "artifact_id",
        "kind",
        "media_type",
        "manifest_profile_sha256",
    }
    if (
        not {"artifact_id", "kind", "media_type"} <= set(payload)
        or set(payload) - allowed_fields
        or not isinstance(payload.get("kind"), str)
        or not isinstance(payload.get("media_type"), str)
    ):
        raise CanonViolation("ir_artifact_view_selector_invalid")
    try:
        ArtifactID.model_validate(str(payload["artifact_id"]))
    except (TypeError, ValueError) as exc:
        raise CanonViolation("ir_artifact_view_selector_invalid") from exc
    profile_selector = payload.get("manifest_profile_sha256")
    if profile_selector is not None and (
        not isinstance(profile_selector, str)
        or _PROFILE_SELECTOR_RE.fullmatch(profile_selector) is None
    ):
        raise CanonViolation("ir_artifact_view_selector_invalid")
    if isinstance(value, Mapping):
        return payload
    return value


def _raw_manifest_canon(store: Any, selector: ArtifactSelector) -> Any:
    """Parse canon metadata directly from the exact selected raw manifest sidecar."""
    get_manifest_bytes = getattr(store, "get_manifest_bytes", None)
    if not callable(get_manifest_bytes):
        raise CanonViolation("ir_artifact_raw_manifest_unavailable")
    try:
        manifest_bytes = get_manifest_bytes(selector)
    except ValidationError as exc:
        raise CanonViolation("unsupported_ir_canon_profile") from exc
    if not isinstance(manifest_bytes, bytes):
        raise CanonViolation("ir_artifact_raw_manifest_invalid")
    try:
        manifest = json.loads(
            manifest_bytes,
            object_pairs_hook=_duplicate_key_rejector,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise CanonViolation("ir_artifact_raw_manifest_invalid") from exc
    if not isinstance(manifest, Mapping) or "canon" not in manifest:
        raise CanonViolation("unsupported_ir_canon_profile")
    return manifest["canon"]


def get_json_artifact(store: ArtifactStore, artifact_id: ArtifactSelector) -> Any:
    """Read JSON after raw profile completeness and byte conformance checks.

    The stored profile is a declaration used to select the IR decoder and encoder
    settings. A successful round-trip proves those settings reproduce the stored
    bytes; it does not identify or attest the producer.
    """
    selector = _artifact_selector(artifact_id)
    canon = _raw_manifest_canon(store, selector)
    if canon is None:
        raise CanonViolation("unsupported_ir_canon_profile")
    profile = _validated_ir_canon_info(canon)
    raw_bytes = store.get_bytes(selector)
    if not isinstance(raw_bytes, bytes):
        raise CanonViolation("ir_artifact_payload_bytes_invalid")
    value = from_canonical_bytes(raw_bytes, max_depth=profile.max_depth)
    spec = CanonSpec(
        name=profile.name,
        version=profile.version,
        forbid_floats=profile.forbid_floats,
        forbid_nan_inf=profile.forbid_nan_inf,
        exclude_none=profile.exclude_none,
        max_depth=profile.max_depth,
        sort_keys=profile.sort_keys,
        separators=profile.separators,
        ensure_ascii=profile.ensure_ascii,
    )
    try:
        expected_bytes = to_canonical_bytes(value, spec)
    except CanonViolation as exc:
        raise CanonViolation("ir_artifact_bytes_do_not_conform_to_persisted_canon_profile") from exc
    if raw_bytes != expected_bytes:
        raise CanonViolation("ir_artifact_bytes_do_not_conform_to_persisted_canon_profile")
    return value


def normalize_input_sequence(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Reuse ``normalize_input_refs`` for callers that still pass generic input sequences."""
    return normalize_input_refs(inputs)


__all__ = [
    "get_json_artifact",
    "normalize_input_sequence",
    "put_json_artifact",
]
