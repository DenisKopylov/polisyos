"""High-level helpers for persisting and loading JSON artifacts through the IR CAS boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass, replace
from typing import TYPE_CHECKING, Any

from polisyos.ir.model_layer.canon import (
    CanonSpec,
    CanonViolation,
    from_canonical_bytes,
    to_canonical_bytes,
)

from .contracts import (
    ArtifactID,
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

_HISTORICAL_CANON_MAX_DEPTH = 128


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
    """Persist IR-canonical JSON and return a normalized artifact reference."""
    ref = _put_json_artifact_ref(
        store,
        payload,
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=canon_spec,
    )
    return normalize_artifact_ref(ref)


def _put_json_artifact_ref(
    store: ArtifactStore,
    payload: Any,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: Sequence[Any] | None = None,
    canon_spec: CanonSpec | None = None,
) -> Any:
    """Persist IR-profile JSON and retain the backend's exact artifact reference."""
    canon_spec = canon_spec or CanonSpec()
    options = PutOptions(
        kind=kind,
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version=schema_version),
        inputs=normalize_input_refs(inputs),
    )
    return _put_canonical_json_bytes(
        store,
        payload,
        to_store_put_options(options),
        canon_spec,
    )


def _put_canonical_json_bytes(
    store: Any,
    payload: Any,
    options: Any,
    canon_spec: CanonSpec,
) -> Any:
    """Bind IR's declared profile, serialize once, and persist those exact bytes."""
    options = _bind_canon_profile(options, canon_spec)
    canonical_bytes = to_canonical_bytes(payload, canon_spec)
    put_bytes = getattr(store, "put_bytes", None)
    if not callable(put_bytes):
        raise TypeError("IR artifact store must implement put_bytes for profile-bound writes")
    return put_bytes(canonical_bytes, opts=options)


def _bind_canon_profile(options: Any, canon_spec: CanonSpec) -> Any:
    """Fail on conflicting metadata and bind the exact profile used for serialization."""
    expected = _canon_info_from_spec(canon_spec)
    supplied = getattr(options, "canon", None)
    if supplied is not None:
        actual = _validated_ir_canon_info(supplied)
        if actual != expected:
            raise ValueError("ir_canon_profile_mismatch")
        return options

    if not is_dataclass(options) or isinstance(options, type):
        raise TypeError("IR artifact write options must support canon profile binding")
    return replace(options, canon=expected.model_dump(mode="python"))


def _canon_info_from_spec(canon_spec: CanonSpec) -> CanonInfo:
    """Validate the supported IR canon profile before binding it to persisted bytes."""
    if not is_dataclass(canon_spec) or isinstance(canon_spec, type):
        raise TypeError("IR canon spec must be a dataclass profile")
    return _validated_ir_canon_info(asdict(canon_spec))


def _validated_ir_canon_info(value: Any) -> CanonInfo:
    """Return a strict, supported profile model from a persisted or supplied value."""
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            payload = model_dump(mode="python")
        elif is_dataclass(value) and not isinstance(value, type):
            payload = asdict(value)
        elif hasattr(value, "__dict__"):
            payload = dict(vars(value))
        else:
            payload = value

    if not isinstance(payload, Mapping) or set(CanonInfo.model_fields) - set(payload):
        raise CanonViolation("unsupported_ir_canon_profile")
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


def _manifest_canon(store: Any, artifact_id: ArtifactID) -> Any | None:
    """Read canon metadata through the artifact-store manifest contract."""
    get_manifest = getattr(store, "get_manifest", None)
    if not callable(get_manifest):
        raise TypeError("IR artifact store must implement get_manifest for profile-aware reads")
    manifest = get_manifest(artifact_id)
    if manifest is None:
        raise CanonViolation("ir_artifact_manifest_missing")

    if isinstance(manifest, Mapping):
        return manifest.get("canon")
    model_dump = getattr(manifest, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="python")
        if not isinstance(payload, Mapping):
            raise TypeError("IR artifact store returned an invalid manifest")
        return payload.get("canon")
    if is_dataclass(manifest) and not isinstance(manifest, type):
        return asdict(manifest).get("canon")
    if hasattr(manifest, "canon"):
        return manifest.canon
    raise TypeError("IR artifact store returned an unsupported manifest")


def get_json_artifact(store: ArtifactStore, artifact_id: ArtifactID) -> Any:
    """Read IR-canonical JSON using its persisted profile or the legacy default."""
    normalized_id = ArtifactID.model_validate(str(artifact_id))
    canon = _manifest_canon(store, normalized_id)
    max_depth = (
        _validated_ir_canon_info(canon).max_depth
        if canon is not None
        else _HISTORICAL_CANON_MAX_DEPTH
    )
    return from_canonical_bytes(store.get_bytes(normalized_id), max_depth=max_depth)


def normalize_input_sequence(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Reuse ``normalize_input_refs`` for callers that still pass generic input sequences."""
    return normalize_input_refs(inputs)


__all__ = [
    "get_json_artifact",
    "normalize_input_sequence",
    "put_json_artifact",
]
