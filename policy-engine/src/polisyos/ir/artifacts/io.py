"""High-level helpers for persisting and loading JSON artifacts through the IR CAS boundary."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, NoReturn, Protocol

from pydantic import ValidationError

from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    _manifest_profile_sha256,
    _normalize_canonical_profile_mapping,
    decode_profiled_canonical_bytes,
    parse_canonical_profile,
)
from polisyos.ir.model_layer.canon import (
    IR_TAG_POLICY_ID,
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
    _is_string_root_model,
    _normalize_scalar_artifact_id,
    normalize_artifact_ref,
    normalize_input_refs,
    to_store_put_options,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def _duplicate_key_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one raw JSON object and reject ambiguous duplicate fields."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    """Reject non-JSON numeric constants in a persisted sidecar."""
    raise ValueError(f"invalid JSON numeric constant: {value}")


class _ProfiledJSONReader(Protocol):
    """Minimal raw selected-view reader required by semantic JSON intake."""

    def get_bytes(self, artifact_id: ArtifactSelector) -> bytes: ...

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes: ...


def put_json_artifact(
    store: ArtifactStore,
    payload: object,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: Sequence[Any] | None = None,
    canon_spec: CanonSpec | None = None,
    return_selected_profile: bool = False,
) -> dict[str, str]:
    """Persist JSON and optionally return the exact profile selected by this write.

    Stores without this write-result capability refuse the request. This helper never
    synthesizes a producer profile from a later default-manifest read.
    """
    if type(return_selected_profile) is not bool:
        raise TypeError("return_selected_profile must be a bool")
    canon_spec = canon_spec or CanonSpec()
    options = PutOptions(
        kind=kind,
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version=schema_version),
        inputs=normalize_input_refs(inputs),
        canon=CanonInfo.from_spec(canon_spec),
    )
    put_json = store.put_json
    if return_selected_profile:
        try:
            signature = inspect.signature(put_json)
        except (TypeError, ValueError) as exc:
            raise NotImplementedError("artifact_store_return_selected_profile_unsupported") from exc
        parameter = signature.parameters.get("return_selected_profile")
        if parameter is None or parameter.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise NotImplementedError("artifact_store_return_selected_profile_unsupported")
        ref = put_json(
            payload,
            opts=to_store_put_options(options),
            canon_spec=canon_spec,
            return_selected_profile=True,
        )
    else:
        ref = put_json(
            payload,
            opts=to_store_put_options(options),
            canon_spec=canon_spec,
        )
    normalized = normalize_artifact_ref(ref)
    if return_selected_profile and not normalized.get("manifest_profile_sha256"):
        raise ValueError("artifact_write_selected_profile_missing")
    return normalized


def _validated_ir_canon_info(value: object) -> CanonInfo:
    """Validate a complete profile mapping parsed from the raw persisted sidecar."""
    if not isinstance(value, Mapping):
        raise CanonViolation("unsupported_ir_canon_profile")
    payload = dict(value)
    if set(CanonInfo.model_fields) - set(payload):
        raise CanonViolation("unsupported_ir_canon_profile")
    payload = _normalize_canonical_profile_mapping(payload)
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


def _make_ir_canon_spec(profile: object) -> CanonSpec:
    """Build IR's typed encoder spec from the selected, validated IR profile."""
    if not isinstance(profile, CanonInfo):
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    return CanonSpec(
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


def _encode_ir_profiled_value(value: object, spec: object) -> bytes:
    """Encode with IR's public codec after checking the shared callback result type."""
    if not isinstance(spec, CanonSpec):
        raise CanonicalProfileRefusalError("canon_profile_invalid")
    return to_canonical_bytes(value, spec)


def _artifact_selector(value: ArtifactSelector) -> ArtifactSelector:
    """Validate an artifact ID or typed selected-view ref without dropping its selector."""
    if isinstance(value, (ArtifactID, str)) or _is_string_root_model(value):
        try:
            return _normalize_scalar_artifact_id(value)
        except (TypeError, ValueError) as exc:
            raise CanonViolation("ir_artifact_view_selector_invalid") from exc
    try:
        return normalize_artifact_ref(value)
    except (TypeError, ValueError) as exc:
        raise CanonViolation("ir_artifact_view_selector_invalid") from exc


def _get_json_artifact_with_bytes(
    store: _ProfiledJSONReader, artifact_id: ArtifactSelector
) -> tuple[Any, bytes]:
    """Read JSON after raw profile completeness and byte conformance checks.

    The stored profile is a declaration used to select the IR decoder and encoder
    settings. A successful round-trip proves those settings reproduce the stored
    bytes; it does not identify or attest the producer.
    """
    selector = _artifact_selector(artifact_id)
    get_manifest_bytes = getattr(store, "get_manifest_bytes", None)
    if not callable(get_manifest_bytes):
        raise CanonViolation("ir_artifact_raw_manifest_unavailable")
    try:
        raw_manifest_bytes = get_manifest_bytes(selector)
    except ValidationError as exc:
        raise CanonViolation("unsupported_ir_canon_profile") from exc
    try:
        declaration = parse_canonical_profile(
            raw_manifest_bytes,
            profile_model=CanonInfo,
            allow_profile_absent=False,
        )
    except CanonicalProfileRefusalError as exc:
        code = {
            "canon_profile_raw_manifest_invalid": "ir_artifact_raw_manifest_invalid",
        }.get(exc.code, "unsupported_ir_canon_profile")
        raise CanonViolation(code) from exc
    try:
        raw_manifest = json.loads(
            raw_manifest_bytes,
            object_pairs_hook=_duplicate_key_rejector,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise CanonViolation("ir_artifact_raw_manifest_invalid") from exc
    if not isinstance(raw_manifest, Mapping):
        raise CanonViolation("ir_artifact_raw_manifest_invalid")
    profile = declaration.profile
    if not isinstance(profile, CanonInfo):
        raise CanonViolation("unsupported_ir_canon_profile")
    profile = _validated_ir_canon_info(profile.model_dump(mode="python"))
    selected_id = selector.get("artifact_id") if isinstance(selector, Mapping) else selector
    manifest_id = raw_manifest.get("artifact_id")
    if manifest_id is None or str(manifest_id) != str(selected_id):
        raise CanonViolation("ir_artifact_selected_manifest_mismatch")
    selected_profile = (
        selector.get("manifest_profile_sha256") if isinstance(selector, Mapping) else None
    )
    if isinstance(selector, Mapping):
        for field in ("kind", "media_type"):
            expected = selector.get(field)
            if expected is not None and str(expected) != str(raw_manifest.get(field)):
                raise CanonViolation("ir_artifact_selected_manifest_mismatch")
    manifest_reader = getattr(store, "get_manifest", None)
    manifest = None
    if callable(manifest_reader):
        manifest = manifest_reader(selector)
        typed_dump = getattr(manifest, "model_dump", None)
        if callable(typed_dump):
            typed_manifest = typed_dump(mode="json", by_alias=True, exclude_none=True)
        elif isinstance(manifest, Mapping):
            typed_manifest = dict(manifest)
        else:
            raise CanonViolation("ir_artifact_selected_manifest_invalid")
        if dict(raw_manifest) != typed_manifest:
            raise CanonViolation("ir_artifact_selected_manifest_changed")
        typed_id = (
            manifest.get("artifact_id")
            if isinstance(manifest, Mapping)
            else getattr(manifest, "artifact_id", None)
        )
        if typed_id is None or str(typed_id) != str(selected_id):
            raise CanonViolation("ir_artifact_selected_manifest_mismatch")
        typed_canon = (
            manifest.get("canon")
            if isinstance(manifest, Mapping)
            else getattr(manifest, "canon", None)
        )
        typed_canon_dump = getattr(typed_canon, "model_dump", None)
        if callable(typed_canon_dump):
            typed_canon = typed_canon_dump(mode="python")
        if _validated_ir_canon_info(typed_canon) != profile:
            raise CanonViolation("ir_artifact_selected_profile_mismatch")
        if selected_profile is not None:
            try:
                actual_profile = _manifest_profile_sha256(typed_manifest)
            except CanonicalProfileRefusalError as exc:
                raise CanonViolation("ir_artifact_selected_manifest_invalid") from exc
            except (TypeError, ValueError) as exc:
                raise CanonViolation("ir_artifact_selected_manifest_invalid") from exc
            if actual_profile != selected_profile:
                raise CanonViolation("ir_artifact_selected_profile_mismatch")
    elif selected_profile is not None:
        # A raw-only reader can prove ID-selected bytes, but cannot resolve a
        # profile-bearing view without an exact typed selector capability.
        raise CanonViolation("ir_artifact_selected_manifest_unavailable")
    raw_bytes = store.get_bytes(selector)
    if not isinstance(raw_bytes, bytes):
        raise CanonViolation("ir_artifact_payload_bytes_invalid")
    expected_hex = str(selected_id).removeprefix("sha256:")
    if hashlib.sha256(raw_bytes).hexdigest() != expected_hex:
        raise CanonViolation("ir_artifact_payload_identity_mismatch")
    try:
        result = decode_profiled_canonical_bytes(
            raw_bytes,
            declaration,
            profile_model=CanonInfo,
            make_spec=_make_ir_canon_spec,
            decode=lambda raw, max_depth: from_canonical_bytes(raw, max_depth=max_depth),
            encode=_encode_ir_profiled_value,
            reader_policy_id=IR_TAG_POLICY_ID,
        )
    except CanonicalProfileRefusalError as exc:
        code = {
            "canon_profile_raw_manifest_invalid": "ir_artifact_raw_manifest_invalid",
            "canon_profile_payload_bytes_invalid": "ir_artifact_payload_bytes_invalid",
            "canon_profile_payload_nonconformant": (
                "ir_artifact_bytes_do_not_conform_to_persisted_canon_profile"
            ),
        }.get(exc.code, "unsupported_ir_canon_profile")
        cause = exc.__cause__
        if (
            exc.code == "canon_profile_payload_nonconformant"
            and isinstance(cause, CanonViolation)
            and str(cause).startswith("Unknown canonical _type")
        ):
            code = str(cause)
        raise CanonViolation(code) from exc
    return result.value, raw_bytes


get_json_artifact_with_bytes = _get_json_artifact_with_bytes


def get_json_artifact(store: ArtifactStore, artifact_id: ArtifactSelector) -> object:
    """Read and return JSON after selected-profile and same-byte conformance checks."""
    value, _raw_bytes = _get_json_artifact_with_bytes(store, artifact_id)
    return value


def normalize_input_sequence(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Reuse ``normalize_input_refs`` for callers that still pass generic input sequences."""
    return normalize_input_refs(inputs)


__all__ = [
    "get_json_artifact",
    "get_json_artifact_with_bytes",
    "normalize_input_sequence",
    "put_json_artifact",
]
