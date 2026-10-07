"""Exercise one loaded byte/manifest view through verification and audit consumers."""

import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, build_cas_integrity_report
from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.manifest import CanonInfo


def test_selected_verify_uses_one_manifest_snapshot(tmp_path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    store.put_bytes(b"same blob", PutOptions(kind="default", media_type="text/plain"))
    selected = store.put_bytes(b"same blob", PutOptions(kind="selected", media_type="text/plain"))
    actual_read = store._read_cas_file_no_follow
    actual_bytes, actual_text = Path.read_bytes, Path.read_text
    counts = {"blob": 0, "manifest": 0}

    def read(path, *, member, max_bytes=None):
        counts[member] += 1
        return actual_read(path, member=member, max_bytes=max_bytes)

    def count_path(path):
        if path.name.endswith(".blob"):
            counts["blob"] += 1
        elif path.name.endswith(".manifest.json"):
            counts["manifest"] += 1

    def read_bytes(path, *args, **kwargs):
        count_path(path)
        return actual_bytes(path, *args, **kwargs)

    def read_text(path, *args, **kwargs):
        count_path(path)
        return actual_text(path, *args, **kwargs)

    monkeypatch.setattr(store, "_read_cas_file_no_follow", read)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "read_text", read_text)
    report = store.verify(selected)
    assert report.ok and report.byte_size == len(b"same blob")
    assert counts == {"blob": 1, "manifest": 1}


def test_integrity_report_cannot_project_an_unverified_second_manifest(tmp_path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    ref = store.put_bytes(b"audit bytes", PutOptions(kind="audit", media_type="text/plain"))
    original = store.get_manifest(ref)
    manifest_path = store._manifest_path_for_ref(ref.artifact_id, None)
    actual_verify = store.verify
    actual_read = store._read_cas_file_no_follow

    def replace_manifest():
        replacement = original.model_copy(update={"canon": CanonInfo(name="foreign", version="99")})
        manifest_path.write_bytes(store._manifests.to_bytes(replacement))

    def verify_then_replace(selected):
        result = actual_verify(selected)
        replace_manifest()
        return result

    def read_then_replace(path, *, member, max_bytes=None):
        data = actual_read(path, member=member, max_bytes=max_bytes)
        if member == "manifest":
            replace_manifest()
        return data

    monkeypatch.setattr(store, "verify", verify_then_replace)
    monkeypatch.setattr(store, "_read_cas_file_no_follow", read_then_replace)
    report = build_cas_integrity_report(store, ref.artifact_id)
    assert report.canonicalization_rule_ref == "raw-bytes"
    assert store.get_manifest(ref).canon.name == "foreign"


def test_staged_verification_cannot_mix_digest_with_later_size(tmp_path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    ref = store.put_bytes(b"original", PutOptions(kind="stage", media_type="text/plain"))
    blob, manifest = store._paths(ref.artifact_id)
    stage = store.root / ".probe-stage"
    staged_blob = stage / blob.relative_to(store.root)
    staged_manifest = stage / manifest.relative_to(store.root)
    staged_blob.parent.mkdir(parents=True)
    staged_blob.write_bytes(b"original")
    staged_manifest.write_bytes(
        store._manifests.to_bytes(
            store.get_manifest(ref).model_copy(update={"byte_size": len(b"different longer bytes")})
        )
    )
    actual_hash = store_module._file_content_hash

    def hash_then_replace(path):
        digest = actual_hash(path)
        if path == staged_blob:
            staged_blob.write_bytes(b"different longer bytes")
        return digest

    monkeypatch.setattr(store_module, "_file_content_hash", hash_then_replace)
    report = store._verify_staged_artifact(ref, stage)
    assert not report.ok


@pytest.mark.parametrize("damage", ["same_size", "wrong_size"])
def test_actual_snapshot_refuses_damaged_blob_or_selected_size(tmp_path, damage):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    store.put_bytes(b"snapshot", PutOptions(kind="default", media_type="text/plain"))
    ref = store.put_bytes(b"snapshot", PutOptions(kind="selected", media_type="text/plain"))
    blob, _ = store._paths(ref.artifact_id)
    if damage == "same_size":
        blob.write_bytes(b"SNAPSHOT")
    else:
        selected = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
        manifest = store.get_manifest(ref).model_copy(update={"byte_size": 100})
        selected.write_bytes(store._manifests.to_bytes(manifest))
    report = store.verify(ref)
    assert not report.ok
    with pytest.raises(ValueError):
        build_cas_integrity_report(store, ref)


@pytest.mark.parametrize("kind", ["symlink", "dangling", "fifo", "socket"])
def test_actual_nonregular_read_is_a_finite_child_refusal(tmp_path, kind):
    worker = Path(__file__).with_name("snapshot_special_path_worker.py")
    child = subprocess.run(
        [sys.executable, str(worker), str(tmp_path / "cas"), kind],
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert "PASS:" in child.stdout
