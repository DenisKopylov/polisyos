"""Exact selected Core-to-IR reads without a writer-capable adapter."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import RawManifestBytesReader
from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    ensure_ir_artifact_store,
    matches_artifact_store_protocol,
)
from polisyos.core.artifacts.manifest import CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.artifacts.io import get_json_artifact
from polisyos.ir.model_layer.canon import CanonViolation


def test_fresh_read_only_ir_reader_preserves_exact_profile_and_rejects_foreign_selector(tmp_path):
    root = tmp_path / "selected-json"
    writer = FileSystemCAS(root)
    default = writer.put_bytes(
        b'{"value":1}',
        ArtifactWriteOptions(kind="test.default", media_type="application/json", canon=CanonInfo()),
    )
    selected = writer.put_bytes(
        b'{"value":1}',
        ArtifactWriteOptions(
            kind="test.selected", media_type="application/json", canon=CanonInfo()
        ),
        return_selected_profile=True,
    )
    assert selected.artifact_id == default.artifact_id
    raw = writer.get_raw_manifest_bytes(selected)
    fresh = FileSystemCAS.open_existing_read_only(root)
    reader = ensure_ir_artifact_store(fresh)
    assert not isinstance(reader, CoreToIRArtifactStoreAdapter)
    assert ensure_ir_artifact_store(reader) is reader
    assert matches_artifact_store_protocol(reader, RawManifestBytesReader)
    assert isinstance(reader, RawManifestBytesReader)
    assert not hasattr(reader, "put_bytes")
    assert not hasattr(reader, "put_json")
    assert reader.get_manifest_bytes(selected.model_dump(mode="python")) == raw
    assert get_json_artifact(reader, selected.model_dump(mode="python")) == {"value": 1}
    wrong_kind = selected.model_copy(update={"kind": "test.foreign"})
    with pytest.raises(CanonViolation, match="ir_artifact_selected_manifest_mismatch"):
        get_json_artifact(reader, wrong_kind.model_dump(mode="python"))
    missing_profile = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    with pytest.raises(FileNotFoundError):
        reader.get_manifest_bytes(missing_profile)
    assert get_json_artifact(reader, selected.model_dump(mode="python")) == {"value": 1}


def test_read_only_ir_adapter_does_not_invent_absent_raw_manifest_capability(tmp_path):
    owner = FileSystemCAS(tmp_path / "missing-raw")
    owner.put_bytes(
        b'{"value":1}',
        ArtifactWriteOptions(
            kind="test.raw-absent", media_type="application/json", canon=CanonInfo()
        ),
    )
    fresh = FileSystemCAS.open_existing_read_only(tmp_path / "missing-raw")

    class NoRawReader:
        def has(self, selector):
            return fresh.has(selector)

        def get_bytes(self, selector):
            return fresh.get_bytes(selector)

        def get_manifest(self, selector):
            return fresh.get_manifest(selector)

        def verify(self, selector):
            return fresh.verify(selector)

    source = NoRawReader()
    assert not isinstance(source, RawManifestBytesReader)
    with pytest.raises(TypeError, match="requires get_raw_manifest_bytes"):
        ensure_ir_artifact_store(source)
