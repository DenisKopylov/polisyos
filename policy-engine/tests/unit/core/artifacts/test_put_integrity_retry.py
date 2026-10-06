"""Direct put retry witnesses for persisted CAS bytes and selected manifest views."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactIntegrityError, FileSystemCAS, PutOptions
from polisyos.core.artifacts._atomic_write import AtomicFileWriter
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo

PAYLOAD = b"a stable payload for a direct CAS retry"


def _options(kind: str) -> PutOptions:
    return PutOptions(
        kind=kind,
        media_type="application/octet-stream",
        schema=SchemaInfo(name=kind, version="1"),
        producer=ProducerInfo(component="tests.put_integrity_retry", version="1"),
    )


def _assert_reopened_readback(root: Path, ref: ArtifactRef) -> None:
    reader = FileSystemCAS(root)
    assert reader.get_bytes(ref) == PAYLOAD
    manifest = reader.get_manifest(ref)
    assert manifest.byte_size == len(PAYLOAD)
    assert manifest.kind == ref.kind
    assert manifest.media_type == ref.media_type
    assert manifest.integrity.sha256.removeprefix("sha256:") == hashlib.sha256(PAYLOAD).hexdigest()
    assert reader.verify(ref).ok


@pytest.mark.parametrize("damage", ["same_size_bytes", "short_bytes", "selected_manifest_size"])
def test_duplicate_put_refuses_damage_before_exact_repair_and_reopened_retry(
    tmp_path: Path, damage: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    default = store.put_bytes(PAYLOAD, _options("tests.retry_default"))
    selected_options = _options("tests.retry_selected")
    selected = store.put_bytes(PAYLOAD, selected_options)
    assert selected.artifact_id == default.artifact_id
    assert selected.manifest_profile_sha256 is not None
    blob, default_manifest = store._paths(selected.artifact_id)
    selected_manifest = store._layout.view_manifest_path(
        selected.artifact_id, selected.manifest_profile_sha256
    )
    default_bytes = default_manifest.read_bytes()
    selected_bytes = selected_manifest.read_bytes()

    if damage == "selected_manifest_size":
        damaged_path = selected_manifest
        repaired_bytes = selected_bytes
        malformed = json.loads(selected_bytes)
        malformed["byte_size"] = len(PAYLOAD) + 1
        damaged_bytes = json.dumps(malformed).encode()
        expected_error = "Manifest byte_size mismatch"
    else:
        damaged_path = blob
        repaired_bytes = PAYLOAD
        damaged_bytes = b"!" * len(PAYLOAD) if damage == "same_size_bytes" else b"short"
        expected_error = "Blob sha256 mismatch"
    damaged_path.write_bytes(damaged_bytes)

    with pytest.raises(ArtifactIntegrityError, match=expected_error):
        store.put_bytes(PAYLOAD, selected_options)
    assert damaged_path.read_bytes() == damaged_bytes
    assert default_manifest.read_bytes() == default_bytes
    if damaged_path != selected_manifest:
        assert selected_manifest.read_bytes() == selected_bytes

    # The operator supplies the exact previously retained bytes, preserving the
    # refused copy separately. The put path does not fabricate repair provenance.
    quarantine = tmp_path / "quarantine"
    quarantine.mkdir()
    preserved_fault = quarantine / damaged_path.name
    preserved_fault.write_bytes(damaged_bytes)
    AtomicFileWriter.write_atomic(damaged_path, repaired_bytes, durable_parent=True)
    retry = store.put_bytes(PAYLOAD, selected_options)
    assert retry == selected
    assert preserved_fault.read_bytes() == damaged_bytes
    assert default_manifest.read_bytes() == default_bytes
    _assert_reopened_readback(store.root, retry)


@pytest.mark.parametrize("sidecar", ["default", "selected"])
def test_duplicate_put_restores_a_missing_sidecar_and_reopens_its_exact_view(
    tmp_path: Path, sidecar: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    default_options = _options("tests.retry_default")
    selected_options = _options("tests.retry_selected")
    default = store.put_bytes(PAYLOAD, default_options)
    selected = store.put_bytes(PAYLOAD, selected_options)
    assert selected.manifest_profile_sha256 is not None
    blob, default_manifest = store._paths(default.artifact_id)
    selected_manifest = store._layout.view_manifest_path(
        selected.artifact_id, selected.manifest_profile_sha256
    )
    missing = default_manifest if sidecar == "default" else selected_manifest
    retained = selected_manifest if sidecar == "default" else default_manifest
    retained_bytes = retained.read_bytes()
    missing.unlink()

    retry = store.put_bytes(PAYLOAD, default_options if sidecar == "default" else selected_options)
    assert missing.is_file()
    assert retained.read_bytes() == retained_bytes
    assert blob.read_bytes() == PAYLOAD
    assert retry.artifact_id == default.artifact_id
    assert retry.manifest_profile_sha256 == (
        None if sidecar == "default" else selected.manifest_profile_sha256
    )
    _assert_reopened_readback(store.root, retry)
