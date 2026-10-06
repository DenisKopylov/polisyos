"""High-level helpers for persisting and loading JSON artifacts through the IR CAS boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.ir.model_layer.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes

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
        canon=CanonInfo.from_spec(canon_spec),
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
    """Serialize once with IR's typed profile, then persist those exact bytes."""
    canonical_bytes = to_canonical_bytes(payload, canon_spec)
    put_bytes = getattr(store, "put_bytes", None)
    if not callable(put_bytes):
        raise TypeError("IR artifact store must implement put_bytes for profile-bound writes")
    return put_bytes(canonical_bytes, opts=options)


def get_json_artifact(store: ArtifactStore, artifact_id: ArtifactID) -> Any:
    """Return json artifact."""
    normalized_id = ArtifactID.model_validate(str(artifact_id))
    return from_canonical_bytes(store.get_bytes(normalized_id))


def normalize_input_sequence(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Reuse ``normalize_input_refs`` for callers that still pass generic input sequences."""
    return normalize_input_refs(inputs)


__all__ = [
    "get_json_artifact",
    "normalize_input_sequence",
    "put_json_artifact",
]
