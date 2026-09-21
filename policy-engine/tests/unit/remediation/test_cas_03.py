"""Test-first witnesses for CAS-03 snapshot and bounded batch semantics.

These tests deliberately describe the missing B152/B154/B155 behavior at the
public ``FileSystemCAS`` seams.  This branch owns no production remediation.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import _integrity_ops as integrity_ops
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


def _synthetic_ids(count: int) -> list[ArtifactID]:
    """Return deterministic valid IDs without creating CAS files."""
    return [ArtifactID.from_sha256_hex(f"{index:064x}") for index in range(1, count + 1)]


def _valid_result(artifact_id: ArtifactID) -> SignatureVerificationResult:
    """Build a valid result for a patched public callback."""
    return SignatureVerificationResult(
        status=SignatureVerificationStatus.VALID,
        artifact_id=str(artifact_id),
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
    original_content_hash = integrity_ops.content_hash

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
        return original_content_hash(data, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)
    monkeypatch.setattr(Path, "read_text", counted_read_text)
    monkeypatch.setattr(integrity_ops, "content_hash", counted_content_hash)

    result = store.verify_signature(ref.artifact_id, verifier)

    assert result.status == SignatureVerificationStatus.VALID
    assert reads == {"blob": 1, "manifest": 1}
    assert integrity_hashes == 1


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
    original_verify = store.verify

    def verify_with_preflight_error(artifact_id: ArtifactID | str):
        if str(artifact_id) == str(denied_id):
            raise PermissionError("shared preflight denied")
        return original_verify(artifact_id)

    monkeypatch.setattr(store, "verify", verify_with_preflight_error)

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
    yielded: list[ArtifactID] = []
    first_started = threading.Event()
    first_finished = threading.Event()
    release_first = threading.Event()
    overfed = threading.Event()

    def artifact_stream():
        for artifact_id in artifact_ids:
            if len(yielded) >= pending_window and not first_finished.is_set():
                overfed.set()
            yielded.append(artifact_id)
            yield artifact_id

    def fake_verify(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        if artifact_id == artifact_ids[0]:
            first_started.set()
            release_first.wait(timeout=2)
            first_finished.set()
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
    assert report.total == len(artifact_ids)
    assert report.valid < report.total
    assert report.errors >= 1
    assert any(
        item.status == SignatureVerificationStatus.ERROR
        and "cancel" in (item.message or "").lower()
        for item in report.details
    )
