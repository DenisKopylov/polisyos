"""Retain one actual failed read's measurements through report consumers."""

from __future__ import annotations

import hashlib

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    artifact_manifest_profile_sha256,
    build_cas_integrity_report,
)
from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
from polisyos.core.contracts import chronology as contract
from polisyos.runtime.quality.chronology_proof import ChronologyProofArtifactReader


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("corrupt", "sha256 mismatch"),
        ("same_size", "sha256 mismatch"),
        ("wrong_size", "byte_size mismatch"),
        ("wrong_profile", "Selected manifest profile mismatch"),
        ("invalid_manifest", "manifest invalid:"),
        ("wrong_integrity", "manifest integrity mismatch"),
        ("wrong_ref_type", "Artifact reference type"),
    ],
)
def test_failed_selected_snapshot_retains_actual_measurements_and_refusal(
    tmp_path, monkeypatch, damage, reason
):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    store.put_bytes(b"original", PutOptions(kind="default", media_type="text/plain"))
    ref = store.put_bytes(b"original", PutOptions(kind="selected", media_type="text/plain"))
    assert ref.manifest_profile_sha256 is not None
    blob, _ = store._paths(ref.artifact_id)
    manifest = store.get_manifest(ref)
    selected = store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
    if damage in {"corrupt", "same_size"}:
        blob.write_bytes(b"tampered!!!" if damage == "corrupt" else b"ORIGINAL")
    elif damage in {"wrong_size", "wrong_integrity"}:
        changes = {"byte_size": 100}
        if damage == "wrong_integrity":
            changes = {"integrity": manifest.integrity.model_copy(update={"sha256": "a" * 64})}
        manifest = manifest.model_copy(update=changes)
        profile = artifact_manifest_profile_sha256(manifest)
        ref = ref.model_copy(update={"manifest_profile_sha256": profile})
        selected = store._manifest_path_for_ref(ref.artifact_id, profile)
        selected.write_bytes(store._manifests.to_bytes(manifest))
    elif damage == "wrong_profile":
        selected.write_bytes(
            store._manifests.to_bytes(manifest.model_copy(update={"kind": "foreign-profile"}))
        )
    elif damage == "invalid_manifest":
        selected.write_bytes(b"{}")
    else:
        ref = ref.model_copy(update={"kind": "foreign-type"})
    actual_data = blob.read_bytes()
    manifest_bytes = selected.read_bytes()
    actual_read = store._read_cas_file_no_follow
    actual_hash = store_module.content_hash
    reads, hashes = [], []

    def read(path, *, member, max_bytes=None):
        reads.append(member)
        return actual_read(path, member=member, max_bytes=max_bytes)

    def hash_bytes(data):
        hashes.append(data)
        return actual_hash(data)

    monkeypatch.setattr(store, "_read_cas_file_no_follow", read)
    monkeypatch.setattr(store_module, "content_hash", hash_bytes)
    report = store.verify(ref)
    assert not report.ok
    assert report.actual_sha256_hex == hashlib.sha256(actual_data).hexdigest()
    assert report.byte_size == len(actual_data)
    assert report.manifest_sha256 == hashlib.sha256(manifest_bytes).hexdigest()
    assert reason in report.error
    assert sorted(reads) == ["blob", "manifest"]
    assert hashes == [actual_data]
    with pytest.raises(ValueError):
        store.get_bytes(ref)
    with pytest.raises(ValueError):
        build_cas_integrity_report(store, ref)


@pytest.mark.parametrize("staged", [False, True])
def test_failed_report_cannot_reread_operator_repaired_bytes(tmp_path, monkeypatch, staged):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    ref = store.put_bytes(b"original", PutOptions(kind="snapshot", media_type="text/plain"))
    blob, manifest = store._paths(ref.artifact_id)
    root = store.root
    if staged:
        root = store.root / ".probe-stage"
        staged_blob = root / blob.relative_to(store.root)
        staged_manifest = root / manifest.relative_to(store.root)
        staged_blob.parent.mkdir(parents=True)
        staged_blob.write_bytes(blob.read_bytes())
        staged_manifest.write_bytes(manifest.read_bytes())
        blob = staged_blob
    damaged = b"old damaged snapshot"
    blob.write_bytes(damaged)
    actual_read = store._read_cas_file_no_follow
    actual_hash = store_module.content_hash
    reads, hashes = [], []

    def read_then_repair(path, *, member, max_bytes=None):
        data = actual_read(path, member=member, max_bytes=max_bytes)
        reads.append(member)
        if member == "blob":
            blob.write_bytes(b"original")
        return data

    def hash_bytes(data):
        hashes.append(data)
        return actual_hash(data)

    monkeypatch.setattr(store, "_read_cas_file_no_follow", read_then_repair)
    monkeypatch.setattr(store_module, "content_hash", hash_bytes)
    report = store._verify_staged_artifact(ref, root) if staged else store.verify(ref)
    assert not report.ok and report.error == "sha256 mismatch"
    assert report.actual_sha256_hex == hashlib.sha256(damaged).hexdigest()
    assert report.byte_size == len(damaged)
    assert sorted(reads) == ["blob", "manifest"]
    assert hashes == [damaged]
    assert blob.read_bytes() == b"original"


def test_pre_read_failure_cannot_invent_blob_measurements(tmp_path):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    ref = store.put_bytes(b"original", PutOptions(kind="snapshot", media_type="text/plain"))
    blob, _ = store._paths(ref.artifact_id)
    blob.unlink()
    report = store.verify(ref)
    assert not report.ok and report.error == "blob missing"
    assert report.actual_sha256_hex is None and report.byte_size is None


def test_valid_signature_cannot_admit_a_wrong_size_selected_snapshot(tmp_path):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    data = b"signed original"
    ref = store.put_bytes(data, PutOptions(kind="signed", media_type="text/plain"))
    manifest = store.get_manifest(ref).model_copy(update={"byte_size": len(data) + 1})
    profile = artifact_manifest_profile_sha256(manifest)
    ref = ref.model_copy(update={"manifest_profile_sha256": profile})
    manifest_bytes = store._manifests.to_bytes(manifest)
    store._manifest_path_for_ref(ref.artifact_id, profile).write_bytes(manifest_bytes)
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)
    signature = signer.sign(ref.artifact_id, data, manifest_bytes)
    assert verifier.verify(ref.artifact_id, data, manifest_bytes, signature).ok
    store._sig_path(ref.artifact_id, profile).write_text(signature.model_dump_json())
    result = store.verify_signature(ref, verifier)
    assert not result.ok and result.status.value == "error"
    report = store.verify(ref)
    assert not report.ok and report.error == "byte_size mismatch"
    assert report.actual_sha256_hex == hashlib.sha256(data).hexdigest()
    assert report.byte_size == len(data)


def test_actual_chronology_reader_classifies_observed_corruption_as_rejected(tmp_path):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    ref = store.put_bytes(
        b"original proof bytes",
        PutOptions(
            kind="core.chronology.full_prefix.bundle", media_type="application/octet-stream"
        ),
    )
    damaged = b"damaged proof bytes"
    store._paths(ref.artifact_id)[0].write_bytes(damaged)
    digest = "sha256:" + hashlib.sha256(b"scope").hexdigest()
    domain = contract.ChronologyProofDomain(
        format=contract.FULL_PREFIX_FORMAT,
        profile=contract.FULL_PREFIX_PROFILE,
        proof_domain="conformance",
        family="snapshot-fixture",
        scope_ref=digest,
        authority_purpose="publication",
    )
    query = contract.NativeChronologyQuery(
        domain=domain, requested_cutoff_ref=digest, requested_query_context_ref=digest
    )
    result = ChronologyProofArtifactReader(store=store).load_and_verify(
        query=query,
        bundle_ref=ref,
        expected_domain=domain,
        expected_prefix=None,
        expected_bundle_content_hash=str(ref.artifact_id),
    )
    assert isinstance(result, contract.ChronologyPersistenceStoreIntegrityMismatch)
    assert result.disposition == "rejected"
    assert result.observed_raw_cas_hash == "sha256:" + hashlib.sha256(damaged).hexdigest()
