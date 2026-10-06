"""Use real CAS signature batches and the actual importer publication boundary."""

import os
import threading
import time

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, _signature_ops, _transfer_ops
from polisyos.core.artifacts import signing as signing_module
from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.signing import (
    BulkVerificationReport,
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
)


@pytest.fixture(autouse=True)
def property_removal(monkeypatch):
    mode = os.environ.get("E02_B_PROPERTY_REMOVAL")
    if mode == "cas-batch-completeness":
        monkeypatch.setattr(BulkVerificationReport, "require_complete_valid", lambda *args: None)
        monkeypatch.setattr(
            _transfer_ops.TransferVerificationBatch, "require_complete_valid", lambda *args: None
        )
    if mode == "cas-batch-stop":
        monkeypatch.setattr(_signature_ops, "check_batch_admission", lambda *args: None)
        monkeypatch.setattr(store_module, "check_batch_admission", lambda *args: None)
    if mode == "cas-batch-window":
        monkeypatch.setattr(_signature_ops, "_pending_window", lambda *args: 1000000)


def signed_store(tmp_path):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)
    refs = [
        store.put_bytes(
            f"actual batch {i}".encode(), PutOptions(kind="test", media_type="text/plain")
        )
        for i in range(3)
    ]
    for ref in refs:
        store.sign_artifact(ref, signer)
    return store, verifier, refs


def test_real_full_batch_all_confirmations_are_required(tmp_path):
    store, verifier, refs = signed_store(tmp_path)
    report = store.verify_all_signatures(verifier, artifact_ids=refs, max_workers=2)
    assert report.state == "complete" and report.admitted == report.finished == 3
    report.require_complete_valid(refs)
    damaged = report.model_copy(update={"details": report.details[:-1], "valid": 3})
    with pytest.raises(ValueError):
        damaged.require_complete_valid(refs)


def test_local_corruption_preserves_full_typed_results_and_refuses_admission(tmp_path):
    store, verifier, refs = signed_store(tmp_path)
    store._paths(refs[1].artifact_id)[0].write_bytes(b"corrupt")
    report = store.verify_all_signatures(verifier, artifact_ids=refs, max_workers=2)
    assert report.state == "complete" and report.admitted == report.finished == 3
    assert report.valid == 2 and report.errors == 1
    assert {str(row.artifact_id) for row in report.details} == {
        str(ref.artifact_id) for ref in refs
    }
    with pytest.raises(ValueError):
        report.require_complete_valid(refs)


def test_cancel_preserves_actual_finished_item_and_explicit_abort(tmp_path, monkeypatch):
    store, verifier, refs = signed_store(tmp_path)
    cancelled = threading.Event()
    actual = store.verify_signature

    def verify(ref, current, *, strict_identity=None):
        result = actual(ref, current, strict_identity=strict_identity)
        cancelled.set()
        return result

    monkeypatch.setattr(store, "verify_signature", verify)
    report = store.verify_all_signatures(
        verifier,
        artifact_ids=refs,
        max_workers=1,
        pending_window=1,
        cancel_event=cancelled,
    )
    assert report.state == "aborted" and report.abort_reason == "cancelled"
    assert report.finished == report.admitted == 1 and report.valid == 1
    with pytest.raises(ValueError):
        report.require_complete_valid(refs)


def test_deadline_stops_lazy_inventory_before_more_real_verification(tmp_path, monkeypatch):
    store, verifier, refs = signed_store(tmp_path)
    consumed = []
    actual = store.verify_signature

    def source():
        for ref in refs:
            consumed.append(ref)
            yield ref

    def slow(ref, current, *, strict_identity=None):
        time.sleep(0.04)
        return actual(ref, current, strict_identity=strict_identity)

    monkeypatch.setattr(store, "verify_signature", slow)
    report = store.verify_all_signatures(
        verifier,
        artifact_ids=source(),
        max_workers=1,
        pending_window=1,
        deadline=time.monotonic() + 0.01,
    )
    assert report.state == "aborted" and report.abort_reason == "deadline"
    assert len(consumed) == report.admitted == report.finished == 1
    with pytest.raises(ValueError):
        report.require_complete_valid(refs)


def test_actual_import_publisher_refuses_unbound_per_item_report(tmp_path, monkeypatch):
    source = FileSystemCAS(tmp_path / "source", ownership_enforced=False)
    target = FileSystemCAS(tmp_path / "target", ownership_enforced=False)
    refs = [
        source.put_bytes(f"transfer {i}".encode(), PutOptions(kind="test", media_type="text/plain"))
        for i in range(2)
    ]
    package = source.export_subgraph(refs, tmp_path / "package", compress=False).output_path
    actual = target._verify_staged_artifact

    def substituted_report(ref, stage):
        report = actual(ref, stage)
        assert report.ok
        return report.model_copy(update={"artifact_id": str(refs[0].artifact_id)})

    monkeypatch.setattr(target, "_verify_staged_artifact", substituted_report)
    report = target.import_subgraph(package, verify_integrity=True)
    assert report.imported_files == 0 and report.verification_failed
    assert all(not target._paths(ref.artifact_id)[0].exists() for ref in refs)


def test_global_basis_loss_preserves_finished_row_and_aborts(tmp_path, monkeypatch):
    store, verifier, refs = signed_store(tmp_path)
    actual = store._load_verified_snapshot

    def lose_basis(ref):
        if ref.artifact_id == refs[1].artifact_id:
            raise signing_module.ArtifactBatchAbortError("authorization_lost")
        return actual(ref)

    monkeypatch.setattr(store, "_load_verified_snapshot", lose_basis)
    report = store.verify_all_signatures(
        verifier, artifact_ids=refs, max_workers=1, pending_window=1
    )
    assert report.state == "aborted" and report.abort_reason == "authorization_lost"
    assert report.admitted == report.finished == 2 and report.valid == 1
    with pytest.raises(ValueError):
        report.require_complete_valid(refs)


def test_cancel_interrupts_actual_default_name_census(tmp_path, monkeypatch):
    store, verifier, refs = signed_store(tmp_path)
    cancelled = threading.Event()
    actual = store_module.os.scandir
    after = []

    def scan(path):
        if cancelled.is_set():
            after.append(path)
        stream = actual(path)
        cancelled.set()
        return stream

    monkeypatch.setattr(store_module.os, "scandir", scan)
    report = store.verify_all_signatures(verifier, cancel_event=cancelled, max_workers=1)
    assert report.state == "aborted" and report.abort_reason == "cancelled"
    assert report.admitted == report.finished == 0 and not after
    with pytest.raises(ValueError):
        report.require_complete_valid(refs)


def test_selected_and_default_same_blob_remain_two_exact_confirmations(tmp_path):
    store, verifier, refs = signed_store(tmp_path)
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)
    selected = store.put_bytes(
        store.get_bytes(refs[0]), PutOptions(kind="selected", media_type="text/plain")
    )
    store.sign_artifact(selected, signer)
    required = (refs[0], selected)
    report = store.verify_all_signatures(verifier, artifact_ids=required, max_workers=1)
    assert report.state == "complete" and report.valid == report.admitted == report.finished == 2
    report.require_complete_valid(required)
    with pytest.raises(ValueError):
        report.require_complete_valid((refs[0], refs[0]))


def test_cryptographically_valid_wrong_size_manifest_still_refuses(tmp_path):
    store, _verifier, refs = signed_store(tmp_path)
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)
    ref = refs[0]
    data = store.get_bytes(ref)
    bad = store.get_manifest(ref).model_copy(update={"byte_size": len(data) + 1})
    manifest_bytes = store._manifests.to_bytes(bad)
    signature = signer.sign(ref.artifact_id, data, manifest_bytes)
    assert verifier.verify(ref.artifact_id, data, manifest_bytes, signature).ok
    store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256).write_bytes(
        manifest_bytes
    )
    store._sig_path(ref.artifact_id, ref.manifest_profile_sha256).write_text(
        signature.model_dump_json()
    )
    result = store.verify_signature(ref, verifier)
    assert not result.ok and result.status.value == "error" and "byte_size" in result.message


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_deadline_refuses_before_inventory(tmp_path, deadline):
    store, verifier, refs = signed_store(tmp_path)
    consumed = []

    def source():
        consumed.append(True)
        yield from refs

    with pytest.raises(ValueError, match="finite"):
        store.verify_all_signatures(verifier, artifact_ids=source(), deadline=deadline)
    assert not consumed


def test_real_forty_item_source_waits_for_a_bounded_pending_window(tmp_path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    refs = [
        store.put_bytes(f"window {i}".encode(), PutOptions(kind="test", media_type="text/plain"))
        for i in range(40)
    ]
    actual = store.verify_signature
    release, fourth, fifth = threading.Event(), threading.Event(), threading.Event()
    consumed, outcome = [], []

    def source():
        for ref in refs:
            consumed.append(ref)
            if len(consumed) == 4:
                fourth.set()
            if len(consumed) == 5:
                fifth.set()
            yield ref

    def held(ref, verifier, *, strict_identity=None):
        assert release.wait(5)
        return actual(ref, verifier, strict_identity=strict_identity)

    monkeypatch.setattr(store, "verify_signature", held)
    worker = threading.Thread(
        target=lambda: outcome.append(
            store.verify_all_signatures(
                Ed25519Verifier(),
                artifact_ids=source(),
                max_workers=2,
                pending_window=4,
            )
        )
    )
    worker.start()
    try:
        assert fourth.wait(2)
        assert not fifth.wait(0.1), (
            "inventory advanced beyond four before any callback could finish"
        )
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive() and len(outcome) == 1
    report = outcome[0]
    assert report.state == "complete" and report.admitted == report.finished == 40
    assert report.unsigned == 40 and len(consumed) == 40


def test_late_real_signer_cannot_start_signature_publication(tmp_path, monkeypatch):
    store, _verifier, _refs = signed_store(tmp_path)
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    actual = signer.sign
    unsigned = store.put_bytes(
        b"deadline signature", PutOptions(kind="test", media_type="text/plain")
    )

    def slow(*args, **kwargs):
        time.sleep(0.04)
        return actual(*args, **kwargs)

    monkeypatch.setattr(signer, "sign", slow)
    report = store.sign_all_artifacts(
        signer,
        artifact_ids=(unsigned.artifact_id,),
        max_workers=1,
        deadline=time.monotonic() + 0.01,
    )
    assert report.state == "aborted" and report.abort_reason == "deadline"
    assert report.admitted == report.finished == 1 and report.signed == 0
    assert not store._sig_path(unsigned.artifact_id).exists()
