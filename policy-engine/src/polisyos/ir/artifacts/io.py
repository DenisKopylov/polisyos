"""High-level helpers for persisting and loading JSON artifacts through the IR CAS boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.ir.canon import CanonSpec, from_canonical_bytes

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
