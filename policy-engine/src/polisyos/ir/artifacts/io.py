"""High-level helpers for persisting and loading JSON artifacts through the IR CAS boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation, from_canonical_bytes

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
    """Return a strict, supported profile model from a persisted or supplied value."""
    if isinstance(value, Mapping):
        payload = dict(value)
        separators = payload.get("separators")
        if (
            type(separators) is list
            and len(separators) == 2
            and all(type(separator) is str for separator in separators)
        ):
            payload["separators"] = tuple(separators)
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
    """Read IR JSON only under a complete supported persisted canon profile."""
    normalized_id = ArtifactID.model_validate(str(artifact_id))
    canon = _manifest_canon(store, normalized_id)
    if canon is None:
        raise CanonViolation("unsupported_ir_canon_profile")
    profile = _validated_ir_canon_info(canon)
    return from_canonical_bytes(store.get_bytes(normalized_id), max_depth=profile.max_depth)


def normalize_input_sequence(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Reuse ``normalize_input_refs`` for callers that still pass generic input sequences."""
    return normalize_input_refs(inputs)


__all__ = [
    "get_json_artifact",
    "normalize_input_sequence",
    "put_json_artifact",
]
