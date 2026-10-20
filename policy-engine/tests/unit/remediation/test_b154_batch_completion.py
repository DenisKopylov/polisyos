"""Real CAS falsifiers for B154's bounded batch executor boundary."""

from __future__ import annotations

import json
import threading
from concurrent.futures import BrokenExecutor, Future
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    BatchAuthorizationLossSignal,
    _signature_ops,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.signing import (
    BulkSigningReport,
    BulkVerificationReport,
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationResult,
    SignatureVerificationStatus,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.exceptions import AuthorizationDeniedError


def _signed_store(
    tmp_path: Path,
) -> tuple[FileSystemCAS, Ed25519Signer, Ed25519Verifier, list[Any]]:
    store = FileSystemCAS(tmp_path / "cas")
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key_pair.public_key, key_id=key_pair.key_id)
    refs = [
        store.put_bytes(
            b"b154-executor-first",
            PutOptions(kind="cas03.b154-executor", media_type="application/octet-stream"),
        ),
        store.put_bytes(
            b"b154-executor-second",
            PutOptions(kind="cas03.b154-executor", media_type="application/octet-stream"),
        ),
    ]
    for ref in refs:
        store.sign_artifact(ref.artifact_id, signer, signer_identity="b154-test")
    return store, signer, verifier, refs


def _break_second_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    original_submit = _signature_ops.ThreadPoolExecutor.submit
    calls = 0

    def fail_second(
        executor: Any,
        fn: Any,
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise BrokenExecutor("injected after first worker result")
        return original_submit(executor, fn, *args, **kwargs)

    monkeypatch.setattr(_signature_ops.ThreadPoolExecutor, "submit", fail_second)


def _synthetic_ids(count: int) -> list[ArtifactID]:
    return [ArtifactID.from_sha256_hex(f"{index:064x}") for index in range(1, count + 1)]


def _valid_result(artifact_id: ArtifactID) -> SignatureVerificationResult:
    return SignatureVerificationResult(
        status=SignatureVerificationStatus.VALID,
        artifact_id=str(artifact_id),
    )


def test_b154_verification_retains_real_completed_result_after_executor_break(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, _signer, verifier, refs = _signed_store(tmp_path)
    _break_second_submit(monkeypatch)

    report = store.verify_all_signatures(
        verifier,
        artifact_ids=[ref.artifact_id for ref in refs],
        max_workers=1,
        pending_window=1,
    )

    valid_rows = [
        detail for detail in report.details if detail.status == SignatureVerificationStatus.VALID
    ]
    batch_rows = [detail for detail in report.details if detail.artifact_id == "<batch>"]
    assert len(valid_rows) == 1
    assert valid_rows[0].artifact_id == str(refs[0].artifact_id)
    assert len(batch_rows) == 1
    assert batch_rows[0].status == SignatureVerificationStatus.ERROR
    assert report.state == "aborted"
    assert report.admitted == 1
    assert report.finished == 1
    assert report.inventory_exhausted is False
    assert report.abort_reason == "executor_failed"
    assert report.ok is False


def test_b154_verification_retains_real_completed_result_after_future_break(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, _signer, verifier, refs = _signed_store(tmp_path)
    original_submit = _signature_ops.ThreadPoolExecutor.submit
    calls = 0

    def fail_second_result(
        executor: Any,
        fn: Any,
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future[Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            first = original_submit(executor, fn, *args, **kwargs)
            # Establish that the retained positive row is a finished callback
            # result before injecting the second Future's executor failure.
            first.result(timeout=5)
            return first
        failed: Future[Any] = Future()
        failed.set_exception(BrokenExecutor("injected from Future.result"))
        return failed

    monkeypatch.setattr(_signature_ops.ThreadPoolExecutor, "submit", fail_second_result)

    report = store.verify_all_signatures(
        verifier,
        artifact_ids=[ref.artifact_id for ref in refs],
        max_workers=1,
        pending_window=2,
    )

    valid_rows = [
        detail for detail in report.details if detail.status == SignatureVerificationStatus.VALID
    ]
    assert len(valid_rows) == 1
    assert valid_rows[0].artifact_id == str(refs[0].artifact_id)
    assert report.state == "aborted"
    assert report.admitted == 2
    assert report.finished == 1
    assert report.inventory_exhausted is False
    assert report.abort_reason == "executor_failed"


def test_b154_verification_preserves_base_exception_control_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    artifact_id = _synthetic_ids(1)[0]

    def interrupt(
        _artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        raise KeyboardInterrupt

    monkeypatch.setattr(store, "verify_signature", interrupt)
    with pytest.raises(KeyboardInterrupt):
        store.verify_all_signatures(Ed25519Verifier(), artifact_ids=[artifact_id], max_workers=1)


def test_b154_verification_reports_complete_all_valid_inventory(
    tmp_path: Path,
) -> None:
    store, _signer, verifier, refs = _signed_store(tmp_path)
    report = store.verify_all_signatures(
        verifier,
        artifact_ids=[ref.artifact_id for ref in refs],
        max_workers=1,
        pending_window=1,
    )

    assert report.valid == report.finished == report.admitted == 2
    assert report.total == 2
    assert report.state == "complete"
    assert report.inventory_exhausted is True
    assert report.abort_reason is None
    assert report.ok is True


def test_b154_legacy_report_payload_does_not_claim_runtime_completion() -> None:
    verification = BulkVerificationReport.model_validate(
        {
            "total": 1,
            "valid": 1,
            "unsigned": 0,
            "invalid": 0,
            "untrusted": 0,
            "revoked": 0,
            "errors": 0,
        }
    )
    signing = BulkSigningReport.model_validate({"total": 1, "signed": 1, "skipped": 0, "errors": 0})
    assert verification.ok is True  # Legacy outcome-only meaning is unchanged.

    for report in (verification, signing):
        payload = json.loads(report.model_dump_json())
        assert report.state is None
        assert report.admitted is None
        assert report.finished is None
        assert report.inventory_exhausted is None
        assert report.abort_reason is None
        assert payload["state"] is None
        assert payload["admitted"] is None
        assert payload["finished"] is None
        assert payload["inventory_exhausted"] is None
        assert payload["abort_reason"] is None


def test_b154_local_item_error_keeps_other_results_and_is_a_complete_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ids = _synthetic_ids(3)
    local_failure = ids[1]

    def verify_one(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        if artifact_id == local_failure:
            raise PermissionError("local item access denied")
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", verify_one)
    report = store.verify_all_signatures(Ed25519Verifier(), artifact_ids=ids, max_workers=1)

    assert report.state == "complete"
    assert report.admitted == report.finished == 3
    assert report.inventory_exhausted is True
    assert report.abort_reason is None
    assert report.valid == 2
    assert report.errors == 1


def test_b154_inventory_failure_retains_rows_and_marks_aborted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    artifact_id = _synthetic_ids(1)[0]

    def broken_source():
        yield artifact_id
        raise OSError("synthetic inventory failure")

    def verify_one(
        current_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        return _valid_result(current_id)

    monkeypatch.setattr(store, "verify_signature", verify_one)
    report = store.verify_all_signatures(
        Ed25519Verifier(), artifact_ids=broken_source(), max_workers=1, pending_window=1
    )

    assert report.state == "aborted"
    assert report.admitted == report.finished == 1
    assert report.inventory_exhausted is False
    assert report.abort_reason == "inventory_failed"
    assert report.valid == 1
    assert report.errors == 1


def test_b154_cancellation_retains_rows_and_marks_aborted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ids = _synthetic_ids(4)
    yielded: list[ArtifactID] = []
    cancel_event = threading.Event()

    def inventory():
        for artifact_id in ids:
            yielded.append(artifact_id)
            yield artifact_id

    def verify_one(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        cancel_event.set()
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", verify_one)
    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=inventory(),
        max_workers=1,
        pending_window=1,
        cancel_event=cancel_event,
    )

    assert len(yielded) == report.admitted == report.finished == 1
    assert report.state == "aborted"
    assert report.inventory_exhausted is False
    assert report.abort_reason == "cancelled"
    assert report.valid == 1
    assert report.errors == 1


def test_b154_signing_retains_real_completed_item_after_executor_break(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    key_pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key_pair.private_pem())
    refs = [
        store.put_bytes(
            b"b154-sign-first",
            PutOptions(kind="cas03.b154-sign", media_type="application/octet-stream"),
        ),
        store.put_bytes(
            b"b154-sign-second",
            PutOptions(kind="cas03.b154-sign", media_type="application/octet-stream"),
        ),
    ]
    _break_second_submit(monkeypatch)

    report = store.sign_all_artifacts(
        signer,
        artifact_ids=[ref.artifact_id for ref in refs],
        only_unsigned=True,
        max_workers=1,
        pending_window=1,
    )

    signed_rows = [detail for detail in report.details if detail.status == "signed"]
    batch_rows = [detail for detail in report.details if detail.artifact_id == "<batch>"]
    assert len(signed_rows) == 1
    assert signed_rows[0].artifact_id == str(refs[0].artifact_id)
    assert len(batch_rows) == 1
    assert batch_rows[0].status == "error"
    assert report.signed == 1
    assert report.errors == 1
    assert report.state == "aborted"
    assert report.admitted == report.finished == 1
    assert report.inventory_exhausted is False
    assert report.abort_reason == "executor_failed"


def test_b154_authorization_loss_stops_new_admissions_and_retains_completed_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, _signer, verifier, refs = _signed_store(tmp_path)
    ids = [ref.artifact_id for ref in refs]
    yielded: list[ArtifactID] = []
    signal = BatchAuthorizationLossSignal()
    verify_signature = store.verify_signature

    def inventory():
        for artifact_id in ids:
            yielded.append(artifact_id)
            yield artifact_id

    def verify_one(
        artifact_id: ArtifactID,
        selected_verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        result = verify_signature(
            artifact_id,
            selected_verifier,
            strict_identity=strict_identity,
        )
        signal.request()
        return result

    monkeypatch.setattr(store, "verify_signature", verify_one)
    report = store.verify_all_signatures(
        verifier,
        artifact_ids=inventory(),
        max_workers=1,
        pending_window=1,
        authorization_loss_signal=signal,
    )

    item_rows = [detail for detail in report.details if detail.artifact_id != "<batch>"]
    batch_rows = [detail for detail in report.details if detail.artifact_id == "<batch>"]
    assert len(yielded) == report.admitted == report.finished == 1
    assert len(item_rows) == 1 and item_rows[0].artifact_id == str(ids[0])
    assert item_rows[0].status == SignatureVerificationStatus.VALID
    assert len(batch_rows) == 1 and batch_rows[0].status == SignatureVerificationStatus.ERROR
    assert report.state == "aborted"
    assert report.inventory_exhausted is False
    assert report.abort_reason == "authorization_lost"  # noqa: S101
    assert report.errors == 1 and report.ok is False
    assert report.model_dump(mode="json")["abort_reason"] == "authorization_lost"


def test_b154_authorization_loss_before_admission_leaves_inventory_unconsumed(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ids = _synthetic_ids(3)
    yielded: list[ArtifactID] = []
    signal = BatchAuthorizationLossSignal()
    signal.request()

    def inventory():
        for artifact_id in ids:
            yielded.append(artifact_id)
            yield artifact_id

    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=inventory(),
        max_workers=1,
        pending_window=1,
        authorization_loss_signal=signal,
    )

    assert yielded == []
    assert report.admitted == report.finished == 0
    assert report.inventory_exhausted is False
    assert report.state == "aborted"
    assert report.abort_reason == "authorization_lost"  # noqa: S101
    assert report.errors == 1


def test_b154_item_denials_do_not_become_request_wide_authorization_loss(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ids = _synthetic_ids(3)
    signal = BatchAuthorizationLossSignal()

    def verify_one(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        if artifact_id == ids[0]:
            raise ArtifactOwnershipError("artifact belongs to another tenant")
        if artifact_id == ids[1]:
            raise AuthorizationDeniedError("item authorization refused")
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", verify_one)
    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=ids,
        max_workers=1,
        pending_window=1,
        authorization_loss_signal=signal,
    )

    assert report.state == "complete"
    assert report.inventory_exhausted is True
    assert report.abort_reason is None
    assert report.valid == 1 and report.errors == 2
    assert not any(detail.artifact_id == "<batch>" for detail in report.details)


def test_b154_authorization_loss_drains_already_admitted_callbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ids = _synthetic_ids(4)
    yielded: list[ArtifactID] = []
    signal = BatchAuthorizationLossSignal()
    second_started = threading.Event()
    first_started = threading.Event()
    second_finished_after_loss = threading.Event()

    def inventory():
        for artifact_id in ids:
            yielded.append(artifact_id)
            yield artifact_id

    def verify_one(
        artifact_id: ArtifactID,
        _verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        del strict_identity
        if artifact_id == ids[0]:
            assert second_started.wait(timeout=5)
            signal.request()
            first_started.set()
        else:
            second_started.set()
            assert first_started.wait(timeout=5)
            assert signal.is_set()
            second_finished_after_loss.set()
        return _valid_result(artifact_id)

    monkeypatch.setattr(store, "verify_signature", verify_one)
    report = store.verify_all_signatures(
        Ed25519Verifier(),
        artifact_ids=inventory(),
        max_workers=2,
        pending_window=2,
        authorization_loss_signal=signal,
    )

    item_rows = [detail for detail in report.details if detail.artifact_id != "<batch>"]
    assert len(yielded) == report.admitted == report.finished == 2
    assert len(item_rows) == 2
    assert second_finished_after_loss.is_set()
    assert report.valid == 2
    assert report.state == "aborted"
    assert report.inventory_exhausted is False
    assert report.abort_reason == "authorization_lost"  # noqa: S101


def test_b154_verification_only_abort_reason_is_rejected_by_signing_report() -> None:
    with pytest.raises(ValidationError):
        BulkSigningReport(
            total=1,
            signed=0,
            skipped=0,
            errors=1,
            state="aborted",
            abort_reason="authorization_lost",
        )

    report = BulkVerificationReport(
        total=1,
        valid=0,
        unsigned=0,
        invalid=0,
        untrusted=0,
        revoked=0,
        errors=1,
        state="aborted",
        abort_reason="authorization_lost",
    )
    assert report.abort_reason == "authorization_lost"  # noqa: S101
