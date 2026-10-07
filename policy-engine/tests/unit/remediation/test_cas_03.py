"""Behavioral witnesses for CAS-03 snapshot and bounded batch semantics."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import _integrity_ops as integrity_ops
from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.signing import (
    ArtifactSigningResult,
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationResult,
    SignatureVerificationStatus,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.observability import get_metrics
from polisyos.core.security.tenant_context import tenant_scope


def _synthetic_ids(count: int) -> list[ArtifactID]:
    """Return deterministic valid IDs without creating CAS files."""
    return [ArtifactID.from_sha256_hex(f"{index:064x}") for index in range(1, count + 1)]


def _valid_result(artifact_id: ArtifactID) -> SignatureVerificationResult:
    """Build a valid result for a patched public callback."""
    return SignatureVerificationResult(
        status=SignatureVerificationStatus.VALID,
        artifact_id=str(artifact_id),
    )


def probe_default_inventory_cancellation_stops_member_name_walk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Removal probe: cancellation must stop an in-progress CAS name walk.

    This helper is called only by a separate scratch pytest leaf. It is not
    collected in the normal CAS-03 file cohort. It signals cancellation from
    the first actual CAS-root ``scandir`` call and then records any later scan
    calls; the standalone probe is expected to fail until the owner can
    interrupt its authenticated name census.
    """
    store = FileSystemCAS(tmp_path / "cas")
    cancel_event = threading.Event()
    visited_prefixes: set[str] = set()
    candidate_index = 0
    while len(visited_prefixes) < 3:
        ref = store.put_bytes(
            f"cas-03-cancelled-name-walk-{candidate_index}".encode(),
            PutOptions(kind="cas03.inventory", media_type="application/octet-stream"),
        )
        candidate_index += 1
        if ref.artifact_id.hex[:4] in visited_prefixes:
            continue
        visited_prefixes.add(ref.artifact_id.hex[:4])
    cas_root = store.base.resolve()
    visited_after_cancel: list[Path] = []
    cancellation_observed = False
    original_scandir = store_module.os.scandir

    def count_scandir(path: Any) -> Any:
        nonlocal cancellation_observed
        resolved = Path(path).resolve()
        if resolved == cas_root or cas_root in resolved.parents:
            if cancel_event.is_set():
                visited_after_cancel.append(resolved)
            result = original_scandir(path)
            if not cancellation_observed:
                cancellation_observed = True
                cancel_event.set()
            return result
        return original_scandir(path)

    monkeypatch.setattr(store_module.os, "scandir", count_scandir)
    report = store.verify_all_signatures(
        Ed25519Verifier(),
        max_workers=1,
        pending_window=1,
        cancel_event=cancel_event,
    )

    assert report.errors == 1
    assert report.details[-1].artifact_id == "<batch>"
    assert cancellation_observed
    assert cancel_event.is_set()
    assert not visited_after_cancel, (
        "CAS member-name traversal continued after cancellation; "
        f"observed {len(visited_after_cancel)} post-cancellation scandir calls"
    )


def test_verify_signature_reuses_one_loaded_blob_and_manifest_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Signature verification must not reread or rehash one immutable CAS pair."""
    store = FileSystemCAS(tmp_path / "cas")
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key_pair.public_key, key_id=key_pair.key_id)
    ref = store.put_bytes(
        b"cas-03-snapshot",
        PutOptions(kind="cas03.snapshot", media_type="application/octet-stream"),
    )
    store.sign_artifact(ref.artifact_id, signer, signer_identity="cas03")

    reads = {"blob": 0, "manifest": 0}
    integrity_hashes = 0
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    original_member_reader = store._read_cas_file_no_follow
    original_stream_read = store_module._VerifiedCASMemberStream.read
    original_store_content_hash = store_module.content_hash
    original_integrity_content_hash = integrity_ops.content_hash
    member_reads = {"blob": 0, "manifest": 0, "signature": 0}

    def counted_read_bytes(path: Path, *args: Any, **kwargs: Any) -> bytes:
        if path.name.endswith(".blob"):
            reads["blob"] += 1
        elif path.name.endswith(".manifest.json"):
            reads["manifest"] += 1
        return original_read_bytes(path, *args, **kwargs)

    def counted_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name.endswith(".manifest.json"):
            reads["manifest"] += 1
        return original_read_text(path, *args, **kwargs)

    def counted_content_hash(data: bytes, *args: Any, **kwargs: Any) -> str:
        nonlocal integrity_hashes
        integrity_hashes += 1
        return original_store_content_hash(data, *args, **kwargs)

    def counted_member_reader(
        path: Path,
        *,
        member: str,
        max_bytes: int | None = None,
    ) -> bytes:
        member_reads[member] += 1
        return original_member_reader(path, member=member, max_bytes=max_bytes)

    def counted_stream_read(stream: Any, size: int = -1) -> bytes:
        member_name = stream._member
        if member_name.endswith(".blob"):
            member_reads["blob"] += 1
        elif member_name.endswith(".manifest.json"):
            member_reads["manifest"] += 1
        elif member_name.endswith(".sig"):
            member_reads["signature"] += 1
        return original_stream_read(stream, size)

    def counted_integrity_hash(data: bytes, *args: Any, **kwargs: Any) -> str:
        nonlocal integrity_hashes
        integrity_hashes += 1
        return original_integrity_content_hash(data, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)
    monkeypatch.setattr(Path, "read_text", counted_read_text)
    monkeypatch.setattr(store, "_read_cas_file_no_follow", counted_member_reader)
    monkeypatch.setattr(
        store_module._VerifiedCASMemberStream,
        "read",
        counted_stream_read,
    )
    monkeypatch.setattr(store_module, "content_hash", counted_content_hash)
    monkeypatch.setattr(integrity_ops, "content_hash", counted_integrity_hash)

    result = store.verify_signature(ref.artifact_id, verifier)

    assert result.status == SignatureVerificationStatus.VALID
    assert member_reads == {"blob": 1, "manifest": 1, "signature": 1}
    assert reads == {"blob": 0, "manifest": 0}
    assert integrity_hashes == 1


def test_verify_signature_records_corrupt_manifest_and_preserves_valid_control(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manifest identity failures remain visible through metrics and valid reads."""
    metrics = get_metrics()
    integrity_failures: list[tuple[str, str]] = []
    record_integrity_failure = metrics.record_artifact_integrity_failure

    def record_integrity_failure_spy(*, backend: str, reason: str) -> None:
        integrity_failures.append((backend, reason))
        record_integrity_failure(backend=backend, reason=reason)

    monkeypatch.setattr(
        metrics,
        "record_artifact_integrity_failure",
        record_integrity_failure_spy,
    )
    store = FileSystemCAS(tmp_path / "cas", metrics=metrics)
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key_pair.public_key, key_id=key_pair.key_id)
    valid_ref = store.put_bytes(
        b"cas-03-valid-signature-control",
        PutOptions(kind="cas03.snapshot", media_type="application/octet-stream"),
    )
    corrupt_ref = store.put_bytes(
        b"cas-03-corrupt-manifest-negative",
        PutOptions(kind="cas03.snapshot", media_type="application/octet-stream"),
    )
    store.sign_artifact(valid_ref.artifact_id, signer, signer_identity="cas03")
    store.sign_artifact(corrupt_ref.artifact_id, signer, signer_identity="cas03")

    valid_result = store.verify_signature(valid_ref.artifact_id, verifier)

    assert valid_result.status == SignatureVerificationStatus.VALID
    assert integrity_failures == []

    manifest_path = store._manifest_path_for_ref(corrupt_ref.artifact_id, None)
    manifest_document = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_document["artifact_id"] = str(ArtifactID.from_sha256_hex("f" * 64))
    manifest_path.write_text(
        json.dumps(manifest_document),
        encoding="utf-8",
    )

    corrupt_result = store.verify_signature(corrupt_ref.artifact_id, verifier)

    assert corrupt_result.status == SignatureVerificationStatus.ERROR
    assert integrity_failures == [("filesystem", "ArtifactIntegrityError")]


def test_verify_batch_records_local_element_errors_and_finishes_independent_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One item failure must remain an error row while other items complete."""
    store = FileSystemCAS(tmp_path / "cas")
    artifact_ids = _synthetic_ids(3)
    denied_id = artifact_ids[1]

    def fake_verify(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        if artifact_id == denied_id:
            raise PermissionError("local item access denied")
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", fake_verify)

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=artifact_ids,
        max_workers=3,
    )

    by_id = {item.artifact_id: item for item in report.details}
    assert report.total == 3
    assert report.valid == 2
    assert report.errors == 1
    assert set(by_id) == {str(item) for item in artifact_ids}
    assert by_id[str(denied_id)].status == SignatureVerificationStatus.ERROR
    assert "local item access denied" in (by_id[str(denied_id)].message or "")


def test_verify_batch_deduplicates_equivalent_typed_ids_from_generator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Equivalent typed IDs must be processed once at the public batch boundary."""
    store = FileSystemCAS(tmp_path / "cas")
    first = ArtifactID.from_sha256_hex("a" * 64)
    repeated = ArtifactID(str(first))
    verified: list[ArtifactID] = []

    def verify_once(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        verified.append(artifact_id)
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", verify_once)

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=(artifact_id for artifact_id in (first, repeated)),
        max_workers=1,
    )

    assert report.total == 1
    assert report.valid == 1
    assert verified == [first]


def test_verify_batch_records_preflight_error_without_marking_it_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An integrity/preflight exception becomes one explicit error result."""
    store = FileSystemCAS(tmp_path / "cas")
    refs = [
        store.put_bytes(
            f"cas-03-preflight-{index}".encode(),
            PutOptions(kind="cas03.preflight", media_type="application/octet-stream"),
        )
        for index in range(3)
    ]
    artifact_ids = [ref.artifact_id for ref in refs]
    denied_id = artifact_ids[1]
    original_snapshot_loader = store._load_verified_snapshot

    def snapshot_with_preflight_error(artifact_id: ArtifactID):
        if str(artifact_id) == str(denied_id):
            raise PermissionError("shared preflight denied")
        return original_snapshot_loader(artifact_id)

    monkeypatch.setattr(store, "_load_verified_snapshot", snapshot_with_preflight_error)

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=artifact_ids,
        max_workers=3,
    )

    by_id = {item.artifact_id: item for item in report.details}
    assert report.total == 3
    assert report.unsigned == 2
    assert report.errors == 1
    assert by_id[str(denied_id)].status == SignatureVerificationStatus.ERROR
    assert "shared preflight denied" in (by_id[str(denied_id)].message or "")


def test_verify_batch_does_not_swallow_base_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cancellation/cleanup boundaries must not turn ``KeyboardInterrupt`` into a row."""
    store = FileSystemCAS(tmp_path / "cas")
    artifact_id = _synthetic_ids(1)[0]

    def interrupted_verify(
        _artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        raise KeyboardInterrupt("operator interrupted batch")

    monkeypatch.setattr(store, "verify_signature", interrupted_verify)

    with pytest.raises(KeyboardInterrupt, match="operator interrupted batch"):
        store.verify_all_signatures(
            Ed25519Verifier(),
            artifact_ids=[artifact_id],
            max_workers=1,
        )


def test_sign_batch_records_signature_presence_preflight_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A ``has_signature`` access error must not discard other signing results."""
    store = FileSystemCAS(tmp_path / "cas")
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    refs = [
        store.put_bytes(
            f"cas-03-sign-preflight-{index}".encode(),
            PutOptions(kind="cas03.sign-preflight", media_type="application/octet-stream"),
        )
        for index in range(3)
    ]
    artifact_ids = [ref.artifact_id for ref in refs]
    denied_id = artifact_ids[1]
    original_has_signature = store.has_signature

    def has_signature_with_preflight_error(artifact_id: ArtifactID | str) -> bool:
        if str(artifact_id) == str(denied_id):
            raise PermissionError("signature presence denied")
        return original_has_signature(artifact_id)

    monkeypatch.setattr(store, "has_signature", has_signature_with_preflight_error)

    report = store.sign_all_artifacts(
        signer,
        artifact_ids=artifact_ids,
        only_unsigned=True,
        max_workers=3,
    )

    by_id = {item.artifact_id: item for item in report.details}
    assert report.total == 3
    assert report.signed == 2
    assert report.skipped == 0
    assert report.errors == 1
    assert by_id[str(denied_id)].status == "error"
    assert "signature presence denied" in (by_id[str(denied_id)].message or "")
    assert all(isinstance(item, ArtifactSigningResult) for item in report.details)


def test_verify_batch_keeps_pending_window_bounded_for_large_iterable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Only the configured pending window may be submitted before progress resumes."""
    store = FileSystemCAS(tmp_path / "cas")
    artifact_ids = _synthetic_ids(40)
    pending_window = 4
    submitted: list[ArtifactID] = []
    completed = 0
    state_lock = threading.Lock()
    first_started = threading.Event()
    release_first = threading.Event()
    overfed = threading.Event()

    def artifact_stream():
        for artifact_id in artifact_ids:
            with state_lock:
                if len(submitted) - completed >= pending_window:
                    overfed.set()
                submitted.append(artifact_id)
            yield artifact_id

    def fake_verify(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        nonlocal completed
        del strict_identity
        if artifact_id == artifact_ids[0]:
            first_started.set()
        release_first.wait(timeout=2)
        with state_lock:
            completed += 1
        return _valid_result(artifact_id)

    def release_after_observation() -> None:
        first_started.wait(timeout=2)
        overfed.wait(timeout=1)
        release_first.set()

    monkeypatch.setattr(store, "verify_signature", fake_verify)
    release_thread = threading.Thread(target=release_after_observation, daemon=True)
    release_thread.start()
    try:
        report = store.verify_all_signatures(
            Ed25519Verifier(),
            artifact_ids=artifact_stream(),
            max_workers=2,
            pending_window=pending_window,
        )
    finally:
        release_first.set()
        release_thread.join(timeout=2)

    assert not release_thread.is_alive()
    assert not overfed.is_set()
    assert report.total == len(artifact_ids)
    assert report.valid == len(artifact_ids)


def test_verify_batch_cancellation_stops_new_submissions_and_is_reported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cancellation must stop inventory consumption and remain visible as non-success."""
    store = FileSystemCAS(tmp_path / "cas")
    artifact_ids = _synthetic_ids(24)
    cancel_event = threading.Event()
    yielded: list[ArtifactID] = []

    def artifact_stream():
        for artifact_id in artifact_ids:
            yielded.append(artifact_id)
            yield artifact_id

    def fake_verify(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        cancel_event.set()
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", fake_verify)

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=artifact_stream(),
        max_workers=2,
        pending_window=2,
        cancel_event=cancel_event,
    )

    assert len(yielded) < len(artifact_ids)
    assert report.total == len(report.details)
    assert report.valid < report.total
    assert report.errors >= 1
    assert any(
        item.status == SignatureVerificationStatus.ERROR
        and "cancel" in (item.message or "").lower()
        for item in report.details
    )


def test_default_batch_path_stops_lazy_inventory_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The public default inventory path must not list every manifest first."""
    store = FileSystemCAS(tmp_path / "cas")
    refs = [
        store.put_bytes(
            f"cas-03-default-inventory-{index}".encode(),
            PutOptions(kind="cas03.default-inventory", media_type="application/octet-stream"),
        )
        for index in range(12)
    ]
    cancel_event = threading.Event()
    yielded: list[ArtifactID] = []
    reads_before_first_worker = {"blob": 0, "manifest": 0}
    original_path_read_bytes = Path.read_bytes
    original_stream_read = store_module._VerifiedCASMemberStream.read

    def counted_path_read_bytes(path: Path, *args: Any, **kwargs: Any) -> bytes:
        if path.name.endswith(".blob"):
            reads_before_first_worker["blob"] += 1
        elif path.name.endswith(".manifest.json"):
            reads_before_first_worker["manifest"] += 1
        return original_path_read_bytes(path, *args, **kwargs)

    def counted_stream_read(stream: Any, size: int = -1) -> bytes:
        if stream._member.endswith(".blob"):
            reads_before_first_worker["blob"] += 1
        elif stream._member.endswith(".manifest.json"):
            reads_before_first_worker["manifest"] += 1
        return original_stream_read(stream, size)

    monkeypatch.setattr(Path, "read_bytes", counted_path_read_bytes)
    monkeypatch.setattr(
        store_module._VerifiedCASMemberStream,
        "read",
        counted_stream_read,
    )
    original_inventory = store._iter_artifact_ids_lazy

    def lazy_inventory(*, cancel_event=None, deadline=None):
        for artifact_id in original_inventory(cancel_event=cancel_event, deadline=deadline):
            yielded.append(artifact_id)
            yield artifact_id

    def fake_verify(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        assert reads_before_first_worker == {"blob": 0, "manifest": 0}
        cancel_event.set()
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "_iter_artifact_ids_lazy", lazy_inventory)
    monkeypatch.setattr(store, "verify_signature", fake_verify)

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        max_workers=1,
        pending_window=2,
        cancel_event=cancel_event,
    )

    assert 0 < len(yielded) < len(refs)
    assert report.valid < report.total
    assert report.errors >= 1
    assert any(
        item.status == SignatureVerificationStatus.ERROR
        and "cancel" in (item.message or "").lower()
        for item in report.details
    )


def test_verify_batch_preserves_partial_rows_when_inventory_source_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An inventory exception after work starts cannot erase rows or imply completion."""
    store = FileSystemCAS(tmp_path / "cas")
    artifact_id = _synthetic_ids(1)[0]

    def broken_source():
        yield artifact_id
        raise OSError("synthetic inventory read failure")

    def fake_verify(
        current_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        return _valid_result(current_id)

    monkeypatch.setattr(store, "verify_signature", fake_verify)

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=broken_source(),
        max_workers=1,
    )

    assert report.total == 2
    assert report.valid == 1
    assert report.errors == 1
    assert report.details[0].artifact_id == str(artifact_id)
    assert report.details[-1].artifact_id == "<batch>"
    assert "source failed" in (report.details[-1].message or "")


def test_default_batch_inventory_change_is_a_partial_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A cooperating writer during work cannot make a default scan look complete."""
    store = FileSystemCAS(tmp_path / "cas")
    initial_ref = store.put_bytes(
        b"cas-03-inventory-before",
        PutOptions(kind="cas03.inventory", media_type="application/octet-stream"),
    )
    inserted: list[ArtifactID] = []

    def write_during_worker(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        if not inserted:
            new_ref = store.put_bytes(
                b"cas-03-inventory-during-scan",
                PutOptions(kind="cas03.inventory", media_type="application/octet-stream"),
            )
            inserted.append(new_ref.artifact_id)
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", write_during_worker)

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        max_workers=1,
        pending_window=1,
    )

    assert inserted
    assert report.valid == 1
    assert report.errors == 1
    assert report.total == 2
    assert report.details[0].artifact_id == str(initial_ref.artifact_id)
    assert report.details[-1].artifact_id == "<batch>"
    assert "source failed" in (report.details[-1].message or "")


def test_default_batch_tolerates_hidden_tenant_and_signature_only_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unrelated shared-CAS churn must preserve a complete tenant batch."""
    store = FileSystemCAS(
        tmp_path / "cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key_pair.public_key, key_id=key_pair.key_id)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        current_ref = store.put_bytes(
            b"cas-03-tenant-a-default",
            PutOptions(kind="cas03.tenant", media_type="application/octet-stream"),
        )

    foreign_refs: list[ArtifactID] = []
    original_verify = store.verify_signature

    def write_during_verify(
        artifact_id: ArtifactID,
        current_verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            store.sign_artifact(artifact_id, signer, signer_identity="tenant-a")
        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
            foreign_ref = store.put_bytes(
                b"cas-03-tenant-b-added-during-scan",
                PutOptions(
                    kind="cas03.tenant",
                    media_type="application/octet-stream",
                ),
            )
            foreign_refs.append(foreign_ref.artifact_id)
        return original_verify(
            artifact_id,
            current_verifier,
            strict_identity=strict_identity,
        )

    monkeypatch.setattr(store, "verify_signature", write_during_verify)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        report = store.verify_all_signatures(
            verifier,
            max_workers=1,
            pending_window=1,
        )
        assert store.has_signature(current_ref.artifact_id)

    assert foreign_refs
    assert report.total == 1
    assert report.valid == 1
    assert report.errors == 0
    assert [item.artifact_id for item in report.details] == [str(current_ref.artifact_id)]


def test_bulk_sign_worker_inherits_the_callers_tenant_scope(
    tmp_path: Path,
) -> None:
    """CAS workers must retain the caller's tenant-bound owner context."""
    store = FileSystemCAS(
        tmp_path / "cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())

    with tenant_scope(None, tenant_id="tenant-cas03", cell_id="cell-cas03"):
        ref = store.put_bytes(
            b"cas-03-tenant-bound-worker",
            PutOptions(kind="cas03.tenant", media_type="application/octet-stream"),
        )
        report = store.sign_all_artifacts(
            signer,
            artifact_ids=(artifact_id for artifact_id in (ref.artifact_id,)),
            only_unsigned=True,
            max_workers=1,
            pending_window=1,
        )

    assert report.total == 1
    assert report.signed == 1
    assert report.errors == 0


def test_default_bulk_signing_uses_unique_default_views(
    tmp_path: Path,
) -> None:
    """Default bulk signing sees one sorted blob ID per default view only."""
    store = FileSystemCAS(tmp_path / "cas")
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    default_view = store.put_bytes(
        b"cas-03-default-and-selected-view",
        PutOptions(kind="cas03.default", media_type="text/plain"),
    )
    selected_view = store.put_bytes(
        b"cas-03-default-and-selected-view",
        PutOptions(kind="cas03.selected", media_type="application/json"),
    )
    other_blob = store.put_bytes(
        b"cas-03-second-default-blob",
        PutOptions(kind="cas03.other", media_type="text/plain"),
    )

    report = store.sign_all_artifacts(
        signer,
        only_unsigned=True,
        max_workers=2,
        pending_window=2,
    )

    expected_ids = {str(default_view.artifact_id), str(other_blob.artifact_id)}
    assert report.total == 2
    assert report.signed == 2
    assert report.errors == 0
    assert {item.artifact_id for item in report.details} == expected_ids
    assert store.has_signature(default_view.artifact_id)
    assert not store.has_signature(selected_view)


def test_default_and_explicit_bulk_reads_keep_foreign_tenant_bytes_unread(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default inventory omits foreign IDs, and an explicit foreign ID denies before bytes."""
    store = FileSystemCAS(
        tmp_path / "cas",
        ownership_enforced=True,
        ownership_requires_scope=True,
    )
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key_pair.public_key, key_id=key_pair.key_id)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        tenant_a_ref = store.put_bytes(
            b"cas-03-tenant-a",
            PutOptions(kind="cas03.tenant", media_type="application/octet-stream"),
        )
        store.sign_artifact(tenant_a_ref.artifact_id, signer, signer_identity="tenant-a")
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        tenant_b_ref = store.put_bytes(
            b"cas-03-tenant-b",
            PutOptions(kind="cas03.tenant", media_type="application/octet-stream"),
        )
        store.sign_artifact(tenant_b_ref.artifact_id, signer, signer_identity="tenant-b")

    blob_reads = 0
    original_member_reader = store._read_cas_file_no_follow

    def count_blob_reads(
        path: Path,
        *,
        member: str,
        max_bytes: int | None = None,
    ) -> bytes:
        nonlocal blob_reads
        if member == "blob":
            blob_reads += 1
        return original_member_reader(path, member=member, max_bytes=max_bytes)

    monkeypatch.setattr(store, "_read_cas_file_no_follow", count_blob_reads)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        default_report = store.verify_all_signatures(
            verifier,
            max_workers=1,
            pending_window=1,
        )

    assert default_report.total == 1
    assert default_report.valid == 1
    assert [item.artifact_id for item in default_report.details] == [str(tenant_a_ref.artifact_id)]
    assert blob_reads == 1

    blob_reads = 0
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        explicit_report = store.verify_all_signatures(
            verifier,
            artifact_ids=(tenant_b_ref.artifact_id,),
            max_workers=1,
        )

    assert explicit_report.total == 1
    assert explicit_report.errors == 1
    assert explicit_report.details[0].artifact_id == str(tenant_b_ref.artifact_id)
    assert blob_reads == 0
