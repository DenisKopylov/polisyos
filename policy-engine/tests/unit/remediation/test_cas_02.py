"""Test-first witnesses for verified CAS transfer and exact export inventories."""

from __future__ import annotations

import copy
import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


PAYLOAD_A = b"cas-02-generation-a"
PAYLOAD_B = b"cas-02-generation-b"


def _options() -> PutOptions:
    """Build one explicit manifest profile for all CAS-02 fixtures."""
    return PutOptions(
        kind="tests.cas02.transfer",
        media_type="application/octet-stream",
        schema=SchemaInfo(name="tests.cas02.transfer", version="1"),
        producer=ProducerInfo(component="tests.cas02", version="1"),
    )


def _artifact_member_paths(store: FileSystemCAS, artifact_id: ArtifactID) -> set[str]:
    """Return the persisted ABI members for one artifact, excluding export metadata."""
    blob_path, manifest_path = store.get_paths(artifact_id)
    return {
        path.relative_to(store.root).as_posix()
        for path in (blob_path, manifest_path, store._sig_path(artifact_id))
        if path.exists()
    }


def _disk_member_paths(root: Path) -> set[str]:
    """Return every regular member currently present in a directory export."""
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _blob_member(store: FileSystemCAS, artifact_id: ArtifactID) -> str:
    """Return the stable archive name of an artifact blob."""
    blob_path, _ = store.get_paths(artifact_id)
    return blob_path.relative_to(store.root).as_posix()


def _copy_artifact_members(
    source_store: FileSystemCAS,
    artifact_id: ArtifactID,
    export_root: Path,
) -> None:
    """Add an already valid artifact's members to an export directory."""
    blob_path, manifest_path = source_store.get_paths(artifact_id)
    for source_path in (blob_path, manifest_path):
        relative = source_path.relative_to(source_store.root)
        destination = export_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)


def _rewrite_tar(
    source: Path,
    destination: Path,
    *,
    replace_member: str | None = None,
    append_member: tuple[str, bytes] | None = None,
) -> None:
    """Rewrite a small test archive with one controlled mutation or extra member."""
    with (
        tarfile.open(source, "r:*") as input_tar,
        tarfile.open(destination, "w:gz") as output_tar,
    ):
        for member in input_tar.getmembers():
            if not member.isfile():
                output_tar.addfile(copy.copy(member))
                continue
            extracted = input_tar.extractfile(member)
            assert extracted is not None
            payload = extracted.read()
            if member.name == replace_member:
                payload = b"cas-02-corrupted-import"
            copied = copy.copy(member)
            copied.size = len(payload)
            output_tar.addfile(copied, io.BytesIO(payload))

        if append_member is not None:
            name, payload = append_member
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            info.mtime = 0
            output_tar.addfile(info, io.BytesIO(payload))


@pytest.mark.parametrize(
    ("compress", "label"),
    [(False, "directory"), (True, "tar")],
)
def test_import_verifies_before_publication_and_preserves_prior_generation(
    tmp_path: Path,
    compress: bool,
    label: str,
) -> None:
    """A bad directory or tar import cannot replace an already valid generation."""
    source = FileSystemCAS(tmp_path / f"source-{label}")
    target = FileSystemCAS(tmp_path / f"target-{label}")
    source_ref = source.put_bytes(PAYLOAD_A, _options())
    target_ref = target.put_bytes(PAYLOAD_A, _options())
    assert target_ref.artifact_id == source_ref.artifact_id
    prior_manifest = target.get_manifest_bytes(target_ref.artifact_id)

    requested = tmp_path / (
        f"incoming-{label}" if not compress else f"incoming-{label}.tar.gz"
    )
    export_report = source.export_subgraph(
        [source_ref.artifact_id],
        requested,
        compress=compress,
    )
    incoming = export_report.output_path
    blob_member = _blob_member(source, source_ref.artifact_id)
    if compress:
        corrupted = tmp_path / f"corrupted-{label}.tar.gz"
        _rewrite_tar(incoming, corrupted, replace_member=blob_member)
        incoming = corrupted
    else:
        (incoming / Path(*blob_member.split("/"))).write_bytes(b"cas-02-corrupted-import")

    report = target.import_subgraph(incoming, verify_integrity=True)

    assert str(source_ref.artifact_id) in report.verification_failed
    assert target.get_bytes(target_ref.artifact_id) == PAYLOAD_A
    assert target.get_manifest_bytes(target_ref.artifact_id) == prior_manifest
    assert target.verify(target_ref.artifact_id).ok


def test_reused_directory_export_publishes_exact_new_inventory_without_a_to_b_leakage(
    tmp_path: Path,
) -> None:
    """A reused directory is a new generation, not an append of the prior request."""
    source = FileSystemCAS(tmp_path / "source")
    artifact_a = source.put_bytes(PAYLOAD_A, _options())
    artifact_b = source.put_bytes(PAYLOAD_B, _options())
    export_root = tmp_path / "reused-export"

    source.export_subgraph([artifact_a.artifact_id], export_root, compress=False)
    source.export_subgraph([artifact_b.artifact_id], export_root, compress=False)

    expected_members = _artifact_member_paths(source, artifact_b.artifact_id)
    assert _disk_member_paths(export_root) == expected_members | {"export_manifest.json"}
    assert _blob_member(source, artifact_a.artifact_id) not in _disk_member_paths(export_root)
    manifest = json.loads((export_root / "export_manifest.json").read_text("utf-8"))
    assert manifest["exported_artifacts"] == 1
    assert manifest["requested_artifacts"] == 1
    assert manifest["members"] == sorted(expected_members)


def test_import_rejects_valid_but_unlisted_member_from_export_inventory(
    tmp_path: Path,
) -> None:
    """A valid CAS member not listed by the generation inventory is not published."""
    source = FileSystemCAS(tmp_path / "source")
    artifact_a = source.put_bytes(PAYLOAD_A, _options())
    artifact_b = source.put_bytes(PAYLOAD_B, _options())
    export_root = tmp_path / "export"
    source.export_subgraph([artifact_a.artifact_id], export_root, compress=False)

    manifest_path = export_root / "export_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["members"] = sorted(_artifact_member_paths(source, artifact_a.artifact_id))
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    _copy_artifact_members(source, artifact_b.artifact_id, export_root)

    target = FileSystemCAS(tmp_path / "target")
    report = target.import_subgraph(export_root, verify_integrity=True)
    unlisted_members = _artifact_member_paths(source, artifact_b.artifact_id)

    assert unlisted_members.issubset(set(report.skipped_entries))
    assert target.has(artifact_a.artifact_id)
    assert not target.has(artifact_b.artifact_id)


def test_invalid_tar_member_is_reported_without_path_escape_or_user_directory_deletion(
    tmp_path: Path,
) -> None:
    """Path safety rejects traversal while leaving unrelated user data untouched."""
    source = FileSystemCAS(tmp_path / "source")
    artifact = source.put_bytes(PAYLOAD_A, _options())
    export = source.export_subgraph(
        [artifact.artifact_id],
        tmp_path / "safe.tar.gz",
        compress=True,
    )
    malicious = tmp_path / "malicious.tar.gz"
    _rewrite_tar(
        export.output_path,
        malicious,
        append_member=("../cas-02-escape.txt", b"must-not-escape"),
    )
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    sentinel = user_data / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    target = FileSystemCAS(tmp_path / "target")
    report = target.import_subgraph(malicious, verify_integrity=True)

    assert "../cas-02-escape.txt" in report.skipped_entries
    assert not (tmp_path / "cas-02-escape.txt").exists()
    assert sentinel.read_text("utf-8") == "keep"


def test_signed_export_round_trip_preserves_signature_binding(tmp_path: Path) -> None:
    """A transfer keeps the signature sidecar bound to the imported blob and manifest."""
    source = FileSystemCAS(tmp_path / "source")
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key_pair.public_key, key_id=key_pair.key_id)
    artifact = source.put_bytes(PAYLOAD_A, _options())
    source.sign_artifact(artifact.artifact_id, signer, signer_identity="cas02-test")

    export = source.export_subgraph(
        [artifact.artifact_id],
        tmp_path / "signed.tar.gz",
        compress=True,
    )
    signature_member = next(
        member
        for member in _artifact_member_paths(source, artifact.artifact_id)
        if member.endswith(".sig")
    )
    with tarfile.open(export.output_path, "r:*") as archive:
        assert signature_member in archive.getnames()

    target = FileSystemCAS(tmp_path / "target")
    report = target.import_subgraph(export.output_path, verify_integrity=True)
    result = target.verify_signature(artifact.artifact_id, verifier)

    assert report.verification_failed == []
    assert result.status == SignatureVerificationStatus.VALID
    assert result.ok
