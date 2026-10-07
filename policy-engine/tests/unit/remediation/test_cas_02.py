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
from polisyos.core.artifacts.manifest import (
    ArtifactTenantContextInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.ownership import ArtifactTransactionPendingError
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
    blob_path, manifest_path = store._paths(artifact_id)
    return {
        path.relative_to(store.root).as_posix()
        for path in (blob_path, manifest_path, store._sig_path(artifact_id))
        if path.exists()
    }


def _disk_member_paths(root: Path) -> set[str]:
    """Return every regular member currently present in a directory export."""
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def _blob_member(store: FileSystemCAS, artifact_id: ArtifactID) -> str:
    """Return the stable archive name of an artifact blob."""
    blob_path, _ = store._paths(artifact_id)
    return blob_path.relative_to(store.root).as_posix()


def _copy_artifact_members(
    source_store: FileSystemCAS,
    artifact_id: ArtifactID,
    export_root: Path,
) -> None:
    """Add an already valid artifact's members to an export directory."""
    blob_path, manifest_path = source_store._paths(artifact_id)
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
    replace_payload: tuple[str, bytes] | None = None,
    rename_member: tuple[str, str] | None = None,
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
            if replace_payload is not None and member.name == replace_payload[0]:
                payload = replace_payload[1]
            copied = copy.copy(member)
            if rename_member is not None and member.name == rename_member[0]:
                copied.name = rename_member[1]
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

    requested = tmp_path / (f"incoming-{label}" if not compress else f"incoming-{label}.tar.gz")
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


def test_failed_reused_directory_export_preserves_prior_complete_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed replacement leaves the previously published directory intact."""
    import polisyos.core.artifacts._transfer_ops as transfer_ops

    source = FileSystemCAS(tmp_path / "source")
    artifact_a = source.put_bytes(PAYLOAD_A, _options())
    artifact_b = source.put_bytes(PAYLOAD_B, _options())
    export_root = tmp_path / "reused-export"

    source.export_subgraph([artifact_a.artifact_id], export_root, compress=False)
    prior_members = {
        path.relative_to(export_root): path.read_bytes()
        for path in export_root.rglob("*")
        if path.is_file()
    }

    def fail_replacement_exchange(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected replacement exchange failure")

    monkeypatch.setattr(transfer_ops, "_exchange_directory_generation", fail_replacement_exchange)

    with pytest.raises(OSError, match="replacement exchange"):
        source.export_subgraph([artifact_b.artifact_id], export_root, compress=False)

    current_members = {
        path.relative_to(export_root): path.read_bytes()
        for path in export_root.rglob("*")
        if path.is_file()
    }
    assert current_members == prior_members
    reopened = FileSystemCAS(tmp_path / "reopened-export")
    report = reopened.import_subgraph(export_root, verify_integrity=True)
    assert not report.verification_failed
    assert reopened.get_bytes(artifact_a) == PAYLOAD_A
    assert reopened.verify(artifact_a).ok
    assert not reopened.has(artifact_b)


def test_reused_directory_export_preserves_unowned_non_file_entries(
    tmp_path: Path,
) -> None:
    """An owned export with an extra directory is rejected without data loss."""
    source = FileSystemCAS(tmp_path / "source")
    artifact_a = source.put_bytes(PAYLOAD_A, _options())
    artifact_b = source.put_bytes(PAYLOAD_B, _options())
    export_root = tmp_path / "reused-export"

    source.export_subgraph([artifact_a.artifact_id], export_root, compress=False)
    prior_members = {
        path.relative_to(export_root): path.read_bytes()
        for path in export_root.rglob("*")
        if path.is_file()
    }
    foreign_directory = export_root / "user-owned-directory"
    foreign_directory.mkdir()

    with pytest.raises(ValueError, match="unowned"):
        source.export_subgraph([artifact_b.artifact_id], export_root, compress=False)

    current_members = {
        path.relative_to(export_root): path.read_bytes()
        for path in export_root.rglob("*")
        if path.is_file()
    }
    assert current_members == prior_members
    assert foreign_directory.is_dir()


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


def test_import_preserves_distinct_manifest_profile_as_selected_view(tmp_path: Path) -> None:
    """Import keeps the local default and admits the incoming exact typed view."""
    source = FileSystemCAS(tmp_path / "source")
    target = FileSystemCAS(tmp_path / "target")
    source_ref = source.put_bytes(PAYLOAD_A, _options())
    target_opts = PutOptions(
        kind="tests.cas02.other-profile",
        media_type="application/octet-stream",
        schema=SchemaInfo(name="tests.cas02.transfer", version="1"),
        producer=ProducerInfo(component="tests.cas02", version="1"),
    )
    target_ref = target.put_bytes(PAYLOAD_A, target_opts)
    prior_manifest = target.get_manifest_bytes(target_ref.artifact_id)
    export = source.export_subgraph(
        [source_ref.artifact_id],
        tmp_path / "profile-conflict.tar.gz",
    )

    report = target.import_subgraph(export.output_path, verify_integrity=True)

    assert report.verification_failed == []
    imported_ref = next(ref for ref in report.imported_refs if ref.kind == "tests.cas02.transfer")
    assert imported_ref.manifest_profile_sha256 is not None
    assert target.get_manifest_bytes(target_ref.artifact_id) == prior_manifest
    assert target.get_bytes(target_ref.artifact_id) == PAYLOAD_A
    assert target.get_manifest(imported_ref).kind == "tests.cas02.transfer"
    assert target.get_manifest(target_ref).kind == "tests.cas02.other-profile"
    assert target.has(imported_ref)


def test_transfer_round_trip_preserves_each_selected_view_and_signature(
    tmp_path: Path,
) -> None:
    """Archive inventory preserves separate manifests and signatures for one blob."""
    source = FileSystemCAS(tmp_path / "source")
    target = FileSystemCAS(tmp_path / "target")
    first = source.put_bytes(PAYLOAD_A, _options())
    second = source.put_bytes(
        PAYLOAD_A,
        PutOptions(
            kind="tests.cas02.second-view",
            media_type="application/json",
            schema=SchemaInfo(name="tests.cas02.second-view", version="2"),
            producer=ProducerInfo(component="tests.cas02", version="2"),
        ),
    )
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key_pair.public_key, key_id=key_pair.key_id)
    source.sign_artifact(second, signer, signer_identity="cas02-second-view")

    export = source.export_subgraph(
        [first, second],
        tmp_path / "multi-view.tar.gz",
    )

    report = target.import_subgraph(export.output_path, verify_integrity=True)

    assert report.verification_failed == []
    assert first in report.imported_refs
    assert second in report.imported_refs
    assert target.get_manifest(first).kind == "tests.cas02.transfer"
    assert target.get_manifest(second).kind == "tests.cas02.second-view"
    assert target.get_manifest_bytes(second) == source.get_manifest_bytes(second)
    assert target.get_signature_bytes(second) == source.get_signature_bytes(second)
    assert target.verify_signature(second, verifier).ok


def test_import_enforces_existing_tenant_ownership(tmp_path: Path) -> None:
    """A tenant cannot import over an artifact owned by another tenant."""
    source = FileSystemCAS(tmp_path / "source")
    source_ref = source.put_bytes(PAYLOAD_A, _options())
    export = source.export_subgraph(
        [source_ref.artifact_id],
        tmp_path / "tenant.tar.gz",
    )

    shared_root = tmp_path / "shared"
    tenant_a = FileSystemCAS(shared_root, tenant_id="tenant-a")
    tenant_a.put_bytes(PAYLOAD_A, _options())
    tenant_b = FileSystemCAS(shared_root, tenant_id="tenant-b")

    with pytest.raises(PermissionError, match="not owned by tenant"):
        tenant_b.import_subgraph(export.output_path, verify_integrity=True)


def test_import_rejects_a_selected_view_bound_to_another_tenant(tmp_path: Path) -> None:
    """An archive cannot transfer authority-bound tenant metadata by byte possession."""
    source = FileSystemCAS(tmp_path / "source", tenant_id="tenant-a")
    source_ref = source.put_bytes(
        PAYLOAD_A,
        PutOptions(
            kind="tests.cas02.tenant-bound",
            media_type="application/octet-stream",
            tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a"),
        ),
    )
    export = source.export_subgraph(
        [source_ref],
        tmp_path / "tenant-bound-view.tar.gz",
    )
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-b")

    with pytest.raises(PermissionError, match="bound to a different tenant"):
        target.import_subgraph(export.output_path, verify_integrity=True)

    assert not target.has(source_ref)


def test_import_rejects_symlinked_parent_without_touching_external_target(
    tmp_path: Path,
) -> None:
    """A symlinked CAS parent is rejected before any external path is written."""
    source = FileSystemCAS(tmp_path / "source")
    source_ref = source.put_bytes(PAYLOAD_A, _options())
    export = source.export_subgraph(
        [source_ref.artifact_id],
        tmp_path / "symlink-parent.tar.gz",
    )
    target = FileSystemCAS(tmp_path / "target")
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    symlinked_parent = target.root / "artifacts" / "sha256" / source_ref.artifact_id.hex[:2]
    symlinked_parent.symlink_to(external, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        target.import_subgraph(export.output_path, verify_integrity=True)

    assert sentinel.read_text("utf-8") == "keep"
    assert not target.has(source_ref.artifact_id)


def test_import_rejects_symlinked_owned_member_without_unlinking_external_file(
    tmp_path: Path,
) -> None:
    """An owned member symlink is never replaced or unlinked by import."""
    source = FileSystemCAS(tmp_path / "source")
    source_ref = source.put_bytes(PAYLOAD_A, _options())
    export = source.export_subgraph(
        [source_ref.artifact_id],
        tmp_path / "symlink-member.tar.gz",
    )
    target = FileSystemCAS(tmp_path / "target")
    blob_path, _ = target._paths(source_ref.artifact_id)
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    external = tmp_path / "external-blob.txt"
    external.write_bytes(b"keep-external")
    blob_path.symlink_to(external)

    with pytest.raises(ValueError, match="symlink"):
        target.import_subgraph(export.output_path, verify_integrity=True)

    assert external.read_bytes() == b"keep-external"
    assert blob_path.is_symlink()


def test_import_accepts_canonicalized_tar_manifest_marker(tmp_path: Path) -> None:
    """Tar marker lookup canonicalizes ``./export_manifest.json`` before comparison."""
    source = FileSystemCAS(tmp_path / "source")
    source_ref = source.put_bytes(PAYLOAD_A, _options())
    export = source.export_subgraph(
        [source_ref.artifact_id],
        tmp_path / "canonical-marker.tar.gz",
    )
    canonicalized = tmp_path / "canonicalized.tar.gz"
    _rewrite_tar(
        export.output_path,
        canonicalized,
        rename_member=("export_manifest.json", "./export_manifest.json"),
    )

    target = FileSystemCAS(tmp_path / "target")
    report = target.import_subgraph(canonicalized, verify_integrity=True)

    assert report.verification_failed == []
    assert target.has(source_ref.artifact_id)


@pytest.mark.parametrize("mutation", ["malformed", "mismatched"])
def test_import_rejects_malformed_or_mismatched_signature(
    tmp_path: Path,
    mutation: str,
) -> None:
    """A detached signature must parse and bind before any CAS publication."""
    source = FileSystemCAS(tmp_path / "source")
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    artifact = source.put_bytes(PAYLOAD_A, _options())
    source.sign_artifact(artifact.artifact_id, signer, signer_identity="cas02-test")
    export = source.export_subgraph(
        [artifact.artifact_id],
        tmp_path / f"signature-{mutation}.tar.gz",
    )
    signature_member = next(
        member
        for member in _artifact_member_paths(source, artifact.artifact_id)
        if member.endswith(".sig")
    )
    if mutation == "malformed":
        replacement = b"not-json"
    else:
        signature = source.get_signature(artifact.artifact_id)
        assert signature is not None
        payload = signature.model_dump(mode="json")
        payload["statement"]["blob_sha256"] = "0" * 64
        replacement = json.dumps(payload, sort_keys=True).encode("utf-8")
    mutated = tmp_path / f"mutated-{mutation}.tar.gz"
    _rewrite_tar(
        export.output_path,
        mutated,
        replace_payload=(signature_member, replacement),
    )

    target = FileSystemCAS(tmp_path / f"target-{mutation}")
    with pytest.raises(ValueError, match="Invalid detached signature"):
        target.import_subgraph(mutated, verify_integrity=True)

    assert not target.has(artifact.artifact_id)


def test_import_refuses_pending_generation_and_recovers_exactly_after_publication_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actual partial publication remains deny-only until exact transaction recovery."""
    source = FileSystemCAS(tmp_path / "source")
    first = source.put_bytes(PAYLOAD_A, _options())
    second = source.put_bytes(PAYLOAD_B, _options())
    export = source.export_subgraph(
        [first.artifact_id, second.artifact_id],
        tmp_path / "mid-publication.tar.gz",
    )
    target = FileSystemCAS(tmp_path / "target")
    original_publish = target._publish_transaction_member
    writes = 0

    def fail_after_first_blob(
        stage_path: Path | None, final_path: Path, *, expected_sha256: str
    ) -> bool:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("injected mid-publication failure")
        return original_publish(stage_path, final_path, expected_sha256=expected_sha256)

    monkeypatch.setattr(target, "_publish_transaction_member", fail_after_first_blob)

    with pytest.raises(OSError, match="mid-publication"):
        target.import_subgraph(export.output_path, verify_integrity=True)

    interrupted, unprocessed = sorted([first, second], key=lambda ref: ref.artifact_id.hex)
    with pytest.raises(ArtifactTransactionPendingError):
        target.has(interrupted)
    with pytest.raises(ArtifactTransactionPendingError):
        FileSystemCAS(target.root).get_bytes(interrupted)
    assert not target.has(unprocessed)
    assert not target._ownership_index.has_any_tenant_claim(interrupted.artifact_id)

    monkeypatch.setattr(target, "_publish_transaction_member", original_publish)
    report = target.import_subgraph(export.output_path, verify_integrity=True)
    assert not report.verification_failed
    reopened = FileSystemCAS(target.root)
    for ref, payload in [(first, PAYLOAD_A), (second, PAYLOAD_B)]:
        assert reopened.get_bytes(ref) == payload
        assert reopened.get_manifest_bytes(ref) == source.get_manifest_bytes(ref)
        assert reopened.verify(ref).ok
