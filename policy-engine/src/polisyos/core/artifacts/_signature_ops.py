"""Signature helper operations for `FileSystemCAS`."""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TYPE_CHECKING, Protocol

from .signing import (
    ArtifactSigningResult,
    BulkSigningReport,
    BulkVerificationReport,
    DetachedSignature,
    Ed25519Signer,
    Ed25519Verifier,
    SignatureVerificationResult,
    SignatureVerificationStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from .ids import ArtifactID


class IntegrityVerificationReport(Protocol):
    """Minimal integrity report protocol used by signature helpers."""

    ok: bool
    error: str | None


class VerifiedArtifactSnapshot(Protocol):
    """Minimal immutable bytes/manifest view consumed by signing helpers."""

    data: bytes
    manifest_bytes: bytes


def _pending_window(max_workers: int, requested: int | None) -> int:
    workers = max(1, int(max_workers))
    return max(1, int(requested)) if requested is not None else workers


def _source_length_hint(source: Iterable[ArtifactID]) -> int | None:
    try:
        return len(source)  # type: ignore[arg-type]
    except TypeError:
        return None


def _run_bounded(
    artifact_ids: Iterable[ArtifactID],
    process: Callable[[ArtifactID], object],
    *,
    max_workers: int,
    pending_window: int | None,
    cancel_event: threading.Event | None,
) -> tuple[list[tuple[int, object]], int | None, bool]:
    """Run item callbacks with bounded inventory consumption and cancellation.

    Only ordinary per-item exceptions are converted by the callback supplied
    by each caller.  Future ``result()`` calls deliberately let
    ``BaseException`` escape so operator interrupts and executor-level aborts
    cannot become successful-looking rows.
    """
    iterator = iter(artifact_ids)
    pending: dict[Future[object], tuple[int, ArtifactID]] = {}
    results: list[tuple[int, object]] = []
    next_index = 0
    exhausted = False
    cancelled = False
    window = _pending_window(max_workers, pending_window)
    length_hint = _source_length_hint(artifact_ids)

    def fill_window(executor: ThreadPoolExecutor) -> None:
        nonlocal cancelled, exhausted, next_index
        while not exhausted and not cancelled and len(pending) < window:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                return
            try:
                artifact_id = next(iterator)
            except StopIteration:
                exhausted = True
                return
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                return
            future = executor.submit(process, artifact_id)
            pending[future] = (next_index, artifact_id)
            next_index += 1

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        fill_window(executor)
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index, _artifact_id = pending.pop(future)
                # Do not catch BaseException here.  Cancellation and operator
                # interruption must retain their control-flow semantics.
                results.append((index, future.result()))
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
            fill_window(executor)

    return results, length_hint, cancelled


def put_signature(
    *,
    artifact_id: ArtifactID,
    signature: DetachedSignature,
    sig_path_for_artifact: Callable[[ArtifactID], Path],
    atomic_write: Callable[[Path, bytes], None],
) -> Path:
    """Persist one detached signature sidecar after binding validation."""
    if signature.artifact_id != str(artifact_id):
        raise ValueError("signature artifact_id mismatch")
    path = sig_path_for_artifact(artifact_id)
    payload = signature.model_dump_json(
        by_alias=True,
        exclude_none=True,
        indent=2,
    ).encode("utf-8")
    atomic_write(path, payload)
    return path


def get_signature(
    *,
    artifact_id: ArtifactID,
    sig_path_for_artifact: Callable[[ArtifactID], Path],
) -> DetachedSignature | None:
    """Load one detached signature sidecar or return `None` if it is absent."""
    path = sig_path_for_artifact(artifact_id)
    if not path.exists():
        return None
    return DetachedSignature.model_validate_json(path.read_text("utf-8"))


def has_signature(
    *,
    artifact_id: ArtifactID,
    sig_path_for_artifact: Callable[[ArtifactID], Path],
) -> bool:
    """Return whether a detached signature sidecar exists for one artifact."""
    return sig_path_for_artifact(artifact_id).exists()


def sign_artifact(
    *,
    artifact_id: ArtifactID,
    signer: Ed25519Signer,
    signer_identity: str | None,
    read_blob: Callable[[ArtifactID], bytes],
    read_manifest_bytes: Callable[[ArtifactID], bytes],
    write_signature: Callable[[ArtifactID, DetachedSignature], Path],
    load_snapshot: Callable[[ArtifactID], VerifiedArtifactSnapshot] | None = None,
) -> DetachedSignature:
    """Sign one stored artifact and persist its sidecar."""
    if load_snapshot is not None:
        snapshot = load_snapshot(artifact_id)
        blob_data = snapshot.data
        manifest_data = snapshot.manifest_bytes
    else:
        blob_data = read_blob(artifact_id)
        manifest_data = read_manifest_bytes(artifact_id)
    signature = signer.sign(
        artifact_id,
        blob_data,
        manifest_data,
        signer_identity=signer_identity,
    )
    write_signature(artifact_id, signature)
    return signature


def verify_signature(
    *,
    artifact_id: ArtifactID,
    verifier: Ed25519Verifier,
    strict_identity: bool | None,
    verify_integrity: Callable[[ArtifactID], IntegrityVerificationReport] | None,
    load_signature: Callable[[ArtifactID], DetachedSignature | None],
    read_blob: Callable[[ArtifactID], bytes],
    read_manifest_bytes: Callable[[ArtifactID], bytes],
    load_snapshot: Callable[[ArtifactID], VerifiedArtifactSnapshot] | None = None,
) -> SignatureVerificationResult:
    """Verify content integrity plus one detached signature sidecar."""
    snapshot: VerifiedArtifactSnapshot | None = None
    if load_snapshot is not None:
        try:
            snapshot = load_snapshot(artifact_id)
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                message=f"Artifact integrity verification failed: {exc}",
            )
    else:
        if verify_integrity is None:
            raise TypeError("verify_integrity is required without load_snapshot")
        try:
            integrity = verify_integrity(artifact_id)
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                message=f"Artifact integrity verification failed: {exc}",
            )
        if not integrity.ok:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                message=f"Artifact integrity verification failed: {integrity.error}",
            )
    try:
        signature = load_signature(artifact_id)
    except Exception as exc:
        return SignatureVerificationResult(
            status=SignatureVerificationStatus.ERROR,
            artifact_id=str(artifact_id),
            message=f"Invalid signature sidecar format: {exc}",
        )
    if signature is None:
        return SignatureVerificationResult(
            status=SignatureVerificationStatus.UNSIGNED,
            artifact_id=str(artifact_id),
            message="No detached signature sidecar found",
        )
    if snapshot is not None:
        blob_data = snapshot.data
        manifest_data = snapshot.manifest_bytes
    else:
        try:
            blob_data = read_blob(artifact_id)
            manifest_data = read_manifest_bytes(artifact_id)
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(artifact_id),
                key_id=signature.key_id,
                signer_identity=signature.signer_identity,
                message=f"Artifact read error: {exc}",
            )
    return verifier.verify(
        artifact_id,
        blob_data,
        manifest_data,
        signature,
        strict_identity=strict_identity,
    )


def sign_all_artifacts(
    *,
    signer: Ed25519Signer,
    artifact_ids: Iterable[ArtifactID],
    signer_identity: str | None,
    only_unsigned: bool,
    max_workers: int,
    has_signature_for_artifact: Callable[[ArtifactID], bool],
    read_blob: Callable[[ArtifactID], bytes],
    read_manifest_bytes: Callable[[ArtifactID], bytes],
    write_signature: Callable[[ArtifactID, DetachedSignature], Path],
    pending_window: int | None = None,
    cancel_event: threading.Event | None = None,
    load_snapshot: Callable[[ArtifactID], VerifiedArtifactSnapshot] | None = None,
) -> BulkSigningReport:
    """Sign many artifacts concurrently and summarize the result set."""
    signer_lock = threading.Lock()

    def _sign_one(aid: ArtifactID) -> ArtifactSigningResult:
        try:
            if only_unsigned and has_signature_for_artifact(aid):
                return ArtifactSigningResult(
                    artifact_id=str(aid),
                    status="skipped",
                    message="already signed",
                )
            if load_snapshot is not None:
                snapshot = load_snapshot(aid)
                blob_data = snapshot.data
                manifest_data = snapshot.manifest_bytes
            else:
                blob_data = read_blob(aid)
                manifest_data = read_manifest_bytes(aid)
            with signer_lock:
                signature = signer.sign(
                    aid,
                    blob_data,
                    manifest_data,
                    signer_identity=signer_identity,
                )
            write_signature(aid, signature)
            return ArtifactSigningResult(
                artifact_id=str(aid),
                status="signed",
                key_id=signature.key_id,
            )
        except Exception as exc:
            return ArtifactSigningResult(
                artifact_id=str(aid),
                status="error",
                message=str(exc),
            )

    indexed, length_hint, cancelled = _run_bounded(
        artifact_ids,
        _sign_one,
        max_workers=max_workers,
        pending_window=pending_window,
        cancel_event=cancel_event,
    )
    details = [
        result
        for _index, result in sorted(indexed, key=lambda item: item[0])
    ]
    if cancelled:
        details.append(
            ArtifactSigningResult(
                artifact_id="<batch>",
                status="error",
                message="Batch cancelled; no new artifacts were submitted",
            )
        )

    signed = sum(1 for item in details if item.status == "signed")
    skipped = sum(1 for item in details if item.status == "skipped")
    errors = sum(1 for item in details if item.status == "error")
    return BulkSigningReport(
        total=length_hint if length_hint is not None else len(details),
        signed=signed,
        skipped=skipped,
        errors=errors,
        details=details,
    )


def verify_all_signatures(
    *,
    verifier: Ed25519Verifier,
    artifact_ids: Iterable[ArtifactID],
    max_workers: int,
    strict_identity: bool | None,
    verify_one: Callable[[ArtifactID, Ed25519Verifier, bool | None], SignatureVerificationResult],
    pending_window: int | None = None,
    cancel_event: threading.Event | None = None,
) -> BulkVerificationReport:
    """Verify many detached signatures concurrently and summarize statuses."""

    def _verify_one(aid: ArtifactID) -> SignatureVerificationResult:
        try:
            return verify_one(aid, verifier, strict_identity)
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(aid),
                message=str(exc),
            )

    indexed, length_hint, cancelled = _run_bounded(
        artifact_ids,
        _verify_one,
        max_workers=max_workers,
        pending_window=pending_window,
        cancel_event=cancel_event,
    )
    details = [
        result
        for _index, result in sorted(indexed, key=lambda item: item[0])
    ]
    if cancelled:
        details.append(
            SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id="<batch>",
                message="Batch cancelled; no new artifacts were submitted",
            )
        )

    valid = sum(1 for item in details if item.status == SignatureVerificationStatus.VALID)
    unsigned = sum(1 for item in details if item.status == SignatureVerificationStatus.UNSIGNED)
    invalid = sum(1 for item in details if item.status == SignatureVerificationStatus.INVALID)
    untrusted = sum(1 for item in details if item.status == SignatureVerificationStatus.UNTRUSTED)
    revoked = sum(1 for item in details if item.status == SignatureVerificationStatus.REVOKED)
    errors = sum(1 for item in details if item.status == SignatureVerificationStatus.ERROR)
    return BulkVerificationReport(
        total=length_hint if length_hint is not None else len(details),
        valid=valid,
        unsigned=unsigned,
        invalid=invalid,
        untrusted=untrusted,
        revoked=revoked,
        errors=errors,
        details=details,
    )
