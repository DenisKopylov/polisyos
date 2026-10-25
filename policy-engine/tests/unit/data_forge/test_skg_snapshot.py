from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    ProducerInfo,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.read_api.academic import (
    RetainedSKGSnapshot as RetainedSKGSnapshotModel,
)
from polisyos.data_forge.read_api.academic import (
    RetainedSKGSnapshotChunk,
    RetainedSKGSnapshotError,
    RetainedSKGSnapshotV11,
    load_retained_skg_snapshot,
    retained_skg_source_binding,
)
from polisyos.ir.artifacts import put_json_artifact

_KIND = "scientist.skg_source_snapshot"
_CHUNK_KIND = "scientist.skg_source_chunk"
_CHUNK_BYTES = 1024 * 1024


class _CoreStoreWithoutRawManifest(FileSystemCAS):
    """A Core store handle with its optional selected-profile sidecar read hidden."""

    def __getattribute__(self, name: str) -> object:
        if name == "get_raw_manifest_bytes":
            raise AttributeError(name)
        return super().__getattribute__(name)


class _SnapshotChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ref: ArtifactRef
    byte_size: int = Field(gt=0, le=_CHUNK_BYTES)


class RetainedSKGSnapshot(BaseModel):
    """Exact operational bytes and provenance; no scientific authenticity claim."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"]
    source_reference: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(gt=0)
    source_binding_schema_version: str = Field(min_length=1)
    query_version: str = Field(min_length=1)
    chunks: tuple[_SnapshotChunk, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_complete_length(self) -> RetainedSKGSnapshot:
        if sum(chunk.byte_size for chunk in self.chunks) != self.byte_size:
            raise ValueError("retained_skg_chunk_length_mismatch")
        if any(chunk.byte_size != _CHUNK_BYTES for chunk in self.chunks[:-1]):
            raise ValueError("retained_skg_chunk_boundary_mismatch")
        return self


def _descriptor(
    store: FileSystemCAS,
    *,
    version: str,
    payload: bytes = b"captured local SKG bytes",
    source_sha256: str | None = None,
    remove_version_id: bool = False,
    remove_fields: tuple[str, ...] = (),
) -> ArtifactRef:
    chunk_ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=_CHUNK_KIND,
            media_type="application/octet-stream",
            schema=SchemaInfo(name=_CHUNK_KIND, version="1.0"),
            producer=ProducerInfo(component="tests.skg_snapshot", version="1.0"),
        ),
        return_selected_profile=True,
    )
    chunk = RetainedSKGSnapshotChunk(ref=chunk_ref, byte_size=len(payload))
    values = {
        "schema_version": version,
        "source_reference": "duckdb://captured/source#v7",
        "source_sha256": source_sha256 or hashlib.sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "source_binding_schema_version": "academic.skg_source_binding.v2",
        "query_version": "skg-query-read.v3",
        "chunks": (chunk,),
    }
    if version == "1.1":
        values["source_version_id"] = 7
        values["version_identity_kind"] = "content_digest"
        model = RetainedSKGSnapshotV11(**values)
        serialized = model.model_dump(mode="json")
        if remove_version_id:
            serialized.pop("source_version_id")
    else:
        model = RetainedSKGSnapshotModel(**values)
        serialized = model.model_dump(mode="json")
    for field in remove_fields:
        serialized.pop(field, None)
    ir_store = ensure_ir_artifact_store(store)
    ref_payload = put_json_artifact(
        ir_store,
        serialized,
        kind=_KIND,
        schema_name=_KIND,
        schema_version=version,
        inputs=[input_ref_from_artifact_ref(chunk_ref, role="source_chunk:0")],
        return_selected_profile=True,
    )
    return ArtifactRef.model_validate(ref_payload)


def test_retained_skg_v11_binding_recomputes_exact_content_and_local_version(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ref = _descriptor(store, version="1.1")

    snapshot = load_retained_skg_snapshot(ensure_ir_artifact_store(store), ref)
    binding = retained_skg_source_binding(ensure_ir_artifact_store(store), ref)

    assert isinstance(snapshot, RetainedSKGSnapshotV11)
    assert snapshot.source_version_id == 7
    assert snapshot.version_identity_kind == "content_digest"
    assert binding.descriptor_ref == ref
    assert binding.source_sha256 == hashlib.sha256(b"captured local SKG bytes").hexdigest()
    assert binding.source_version_id == 7
    assert binding.version_identity_kind == "content_digest"


def test_retained_skg_source_binding_rejects_missing_profile_reader(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ref = _descriptor(store, version="1.1")
    incomplete_store = _CoreStoreWithoutRawManifest(tmp_path)

    with pytest.raises(RetainedSKGSnapshotError, match="descriptor_read_store_required"):
        retained_skg_source_binding(incomplete_store, ref)


def test_retained_skg_legacy_v10_remains_readable_but_cannot_bind_new_source(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ref = _descriptor(store, version="1.0")

    snapshot = load_retained_skg_snapshot(ensure_ir_artifact_store(store), ref)

    assert type(snapshot) is RetainedSKGSnapshotModel
    with pytest.raises(RetainedSKGSnapshotError, match="legacy_source_version_unbound"):
        retained_skg_source_binding(ensure_ir_artifact_store(store), ref)


def test_retained_skg_v11_rejects_digest_mutation_and_removed_version_field(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    bad_digest_ref = _descriptor(store, version="1.1", source_sha256="0" * 64)
    missing_version_ref = _descriptor(store, version="1.1", remove_version_id=True)

    with pytest.raises(RetainedSKGSnapshotError, match="retained_digest_mismatch"):
        load_retained_skg_snapshot(ensure_ir_artifact_store(store), bad_digest_ref)
    with pytest.raises((TypeError, ValueError)):
        load_retained_skg_snapshot(ensure_ir_artifact_store(store), missing_version_ref)


def test_retained_skg_v10_schema_matches_exact_slice_base_contract() -> None:
    current_schema = RetainedSKGSnapshotModel.model_json_schema()
    base_schema = RetainedSKGSnapshot.model_json_schema()

    assert current_schema == base_schema
    assert current_schema["title"] == "RetainedSKGSnapshot"
    assert current_schema["required"] == [
        "schema_version",
        "source_reference",
        "source_sha256",
        "byte_size",
        "source_binding_schema_version",
        "query_version",
        "chunks",
    ]
    assert "_SnapshotChunk" in current_schema["$defs"]
    assert "RetainedSKGSnapshotChunk" not in current_schema["$defs"]


def test_retained_skg_schema_versions_keep_literal_identity_and_wire_order() -> None:
    base_fields = (
        "schema_version",
        "source_reference",
        "source_sha256",
        "byte_size",
        "source_binding_schema_version",
        "query_version",
        "chunks",
    )
    current_fields = (*base_fields, "source_version_id", "version_identity_kind")
    assert tuple(RetainedSKGSnapshotModel.model_fields) == base_fields
    assert tuple(RetainedSKGSnapshotV11.model_fields) == current_fields
    assert RetainedSKGSnapshotModel.model_fields["schema_version"].annotation == Literal["1.0"]
    assert RetainedSKGSnapshotV11.model_fields["schema_version"].annotation == Literal["1.1"]

    base_schema = RetainedSKGSnapshotModel.model_json_schema()
    current_schema = RetainedSKGSnapshotV11.model_json_schema()
    assert tuple(base_schema["properties"]) == base_fields
    assert tuple(current_schema["properties"]) == current_fields
    assert base_schema["properties"]["schema_version"]["const"] == "1.0"
    assert current_schema["properties"]["schema_version"]["const"] == "1.1"
    assert base_schema["properties"]["chunks"]["items"]["$ref"].endswith("_SnapshotChunk")
    assert current_schema["properties"]["chunks"]["items"]["$ref"].endswith(
        "RetainedSKGSnapshotChunk"
    )


def test_retained_skg_descriptors_reject_omitted_wire_identity_fields(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    malformed_refs = (
        _descriptor(store, version="1.0", remove_fields=("schema_version",)),
        _descriptor(store, version="1.1", remove_fields=("schema_version",)),
        _descriptor(store, version="1.1", remove_fields=("version_identity_kind",)),
    )

    for ref in malformed_refs:
        with pytest.raises(ValueError):
            load_retained_skg_snapshot(ensure_ir_artifact_store(store), ref)

    legacy_schema = RetainedSKGSnapshotModel.model_json_schema()
    current_schema = RetainedSKGSnapshotV11.model_json_schema()
    assert "schema_version" in legacy_schema["required"]
    assert {"schema_version", "version_identity_kind"} <= set(current_schema["required"])
