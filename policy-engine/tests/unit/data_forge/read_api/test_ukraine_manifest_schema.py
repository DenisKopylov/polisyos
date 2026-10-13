"""Selected Ukraine snapshot schema metadata uses the Core manifest field."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.read_api.ukraine import (
    UkraineJSONSnapshotRead,
    UkraineJSONSnapshotRefusalError,
    read_ukraine_json_snapshot,
)


class _StatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    state_ids: list[str]


def _read_snapshot(
    store: FileSystemCAS,
    ref: ArtifactRef,
    payload: bytes,
    expected_schema: tuple[str, str],
) -> UkraineJSONSnapshotRead[_StatePayload]:
    digest = hashlib.sha256(payload).hexdigest()
    return read_ukraine_json_snapshot(
        store,
        ref,
        raw_payload_bytes=payload,
        expected_sha256=digest,
        expected_size_bytes=len(payload),
        expected_kind="data_forge.ukraine.stage_output_snapshot",
        consumer_contract="unit.ukraine.schema",
        model_type=_StatePayload,
        expected_schema=expected_schema,
    )


def test_core_artifact_schema_is_read_and_absence_or_mismatch_refuses(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload_value = {"state_ids": ["a", "b"]}
    schema = SchemaInfo(name="tests.ukraine.state-payload", version="1.0")
    ref = store.put_json(
        payload_value,
        PutOptions(
            kind="data_forge.ukraine.stage_output_snapshot",
            media_type="application/json",
            schema=schema,
        ),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    payload = store.get_bytes(ref)

    read = _read_snapshot(store, ref, payload, (schema.name, schema.version))

    assert read.provenance.schema_name == schema.name
    assert read.provenance.schema_version == schema.version
    assert read.value.state_ids == ["a", "b"]
    with pytest.raises(UkraineJSONSnapshotRefusalError, match="ukraine_snapshot_schema_mismatch"):
        _read_snapshot(store, ref, payload, (schema.name, "2.0"))

    absent_ref = store.put_json(
        payload_value,
        PutOptions(
            kind="data_forge.ukraine.stage_output_snapshot",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    with pytest.raises(UkraineJSONSnapshotRefusalError, match="ukraine_snapshot_schema_mismatch"):
        _read_snapshot(
            store,
            absent_ref,
            store.get_bytes(absent_ref),
            (schema.name, schema.version),
        )
