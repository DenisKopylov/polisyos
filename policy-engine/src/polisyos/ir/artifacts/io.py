"""Public artifacts io module API."""
from __future__ import annotations

from typing import Any, Sequence

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
    """Put json artifact helper."""
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
    return from_canonical_bytes(store.get_bytes(artifact_id))


def normalize_input_sequence(inputs: Sequence[Any] | None) -> list[InputRef]:
    """Normalize input sequence helper."""
    return normalize_input_refs(inputs)


__all__ = [
    "get_json_artifact",
    "normalize_input_sequence",
    "put_json_artifact",
]
