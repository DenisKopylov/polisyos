"""Signature helper operations for `FileSystemCAS`."""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, BrokenExecutor, Future, ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

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


type _BatchAbortReason = Literal["cancelled", "inventory_failed", "executor_failed"]
_BATCH_ABORT_MESSAGES: dict[_BatchAbortReason, str] = {
    "cancelled": "Batch cancelled; no new artifacts were submitted",
    "inventory_failed": "Batch inventory source failed; results are incomplete",
    "executor_failed": "Batch aborted (executor_failed); results are incomplete",
}


def _batch_abort_message(reason: _BatchAbortReason) -> str:
    """Return the established diagnostic for a typed batch abort reason."""
    return _BATCH_ABORT_MESSAGES[reason]


class IntegrityVerificationReport(Protocol):
    """Minimal integrity report protocol used by signature helpers."""

    ok: bool
    error: str | None


class VerifiedArtifactSnapshot(Protocol):
    """Minimal immutable bytes/manifest view consumed by signing helpers."""

    @property
    def data(self) -> bytes: ...

    @property
    def manifest_bytes(self) -> bytes: ...


def _pending_window(max_workers: int, requested: int | None) -> int:
    workers = max(1, int(max_workers))
    return max(1, int(requested)) if requested is not None else workers


def _source_length_hint(source: Iterable[ArtifactID]) -> int | None:
    try:
        return len(source)  # type: ignore[arg-type]
    except TypeError:
        return None


@dataclass(frozen=True)
class _BoundedRun:
    """Return actual finished rows and inventory/executor completion state."""

    indexed: list[tuple[int, object]]
    length_hint: int | None
    admitted: int
    inventory_exhausted: bool
    abort_reason: _BatchAbortReason | None

    @property
    def finished(self) -> int:
        """Count callback results retained by this run."""
        return len(self.indexed)


def _run_bounded(
    artifact_ids: Iterable[ArtifactID],
    process: Callable[[ArtifactID], object],
    *,
    max_workers: int,
    pending_window: int | None,
    cancel_event: threading.Event | None,
) -> _BoundedRun:
    """Run item callbacks with bounded inventory consumption and cancellation.

    Only ordinary per-item exceptions are converted by the callback supplied
    by each caller. Executor breakage stops further admission while preserving
    finished callback rows. ``BaseException`` deliberately retains its control
    flow meaning.
    """
    iterator = iter(artifact_ids)
    pending: dict[Future[object], tuple[int, ArtifactID]] = {}
    results: list[tuple[int, object]] = []
    next_index = 0
    exhausted = False
    abort_reason: _BatchAbortReason | None = None
    window = _pending_window(max_workers, pending_window)
    length_hint = _source_length_hint(artifact_ids)

    def fill_window(executor: ThreadPoolExecutor) -> None:
        nonlocal abort_reason, exhausted, next_index
        while not exhausted and abort_reason is None and len(pending) < window:
            if cancel_event is not None and cancel_event.is_set():
                abort_reason = "cancelled"
                return
            try:
                artifact_id = next(iterator)
            except StopIteration:
                exhausted = True
                return
            except Exception:
                # A failed inventory is not evidence that the source ended.
                abort_reason = "inventory_failed"
                return
            if cancel_event is not None and cancel_event.is_set():
                abort_reason = "cancelled"
                return
            task_context = copy_context()
            try:
                future = executor.submit(task_context.run, process, artifact_id)
            except (BrokenExecutor, RuntimeError):
                abort_reason = "executor_failed"
                return
            pending[future] = (next_index, artifact_id)
            next_index += 1

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        fill_window(executor)
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index, _artifact_id = pending.pop(future)
                try:
                    results.append((index, future.result()))
                except BrokenExecutor:
                    # The callback wrapper converts local Exception instances
                    # to item rows. A BrokenExecutor escaping Future.result()
                    # therefore identifies infrastructure failure, not an
                    # item disposition. Preserve every other finished row.
                    abort_reason = "executor_failed"
                if abort_reason is None and cancel_event is not None and cancel_event.is_set():
                    abort_reason = "cancelled"
            fill_window(executor)

    return _BoundedRun(
        indexed=results,
        length_hint=length_hint,
        admitted=next_index,
        inventory_exhausted=exhausted,
        abort_reason=abort_reason,
    )


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
    write_signature: Callable[[ArtifactID, DetachedSignature], None],
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
    write_signature: Callable[[ArtifactID, DetachedSignature], None],
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

    run = _run_bounded(
        artifact_ids,
        _sign_one,
        max_workers=max_workers,
        pending_window=pending_window,
        cancel_event=cancel_event,
    )
    details = [result for _index, result in sorted(run.indexed, key=lambda item: item[0])]
    if run.abort_reason is not None:
        details.append(
            ArtifactSigningResult(
                artifact_id="<batch>",
                status="error",
                message=_batch_abort_message(run.abort_reason),
            )
        )

    signed = sum(1 for item in details if item.status == "signed")
    skipped = sum(1 for item in details if item.status == "skipped")
    errors = sum(1 for item in details if item.status == "error")
    return BulkSigningReport(
        total=(
            run.length_hint
            if run.length_hint is not None and run.abort_reason != "inventory_failed"
            else len(details)
        ),
        signed=signed,
        skipped=skipped,
        errors=errors,
        details=details,
        state="aborted" if run.abort_reason is not None else "complete",
        admitted=run.admitted,
        finished=run.finished,
        inventory_exhausted=run.inventory_exhausted,
        abort_reason=run.abort_reason,
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

    run = _run_bounded(
        artifact_ids,
        _verify_one,
        max_workers=max_workers,
        pending_window=pending_window,
        cancel_event=cancel_event,
    )
    details = [result for _index, result in sorted(run.indexed, key=lambda item: item[0])]
    if run.abort_reason is not None:
        details.append(
            SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id="<batch>",
                message=_batch_abort_message(run.abort_reason),
            )
        )

    valid = sum(1 for item in details if item.status == SignatureVerificationStatus.VALID)
    unsigned = sum(1 for item in details if item.status == SignatureVerificationStatus.UNSIGNED)
    invalid = sum(1 for item in details if item.status == SignatureVerificationStatus.INVALID)
    untrusted = sum(1 for item in details if item.status == SignatureVerificationStatus.UNTRUSTED)
    revoked = sum(1 for item in details if item.status == SignatureVerificationStatus.REVOKED)
    errors = sum(1 for item in details if item.status == SignatureVerificationStatus.ERROR)
    return BulkVerificationReport(
        total=(
            run.length_hint
            if run.length_hint is not None and run.abort_reason != "inventory_failed"
            else len(details)
        ),
        valid=valid,
        unsigned=unsigned,
        invalid=invalid,
        untrusted=untrusted,
        revoked=revoked,
        errors=errors,
        details=details,
        state="aborted" if run.abort_reason is not None else "complete",
        admitted=run.admitted,
        finished=run.finished,
        inventory_exhausted=run.inventory_exhausted,
        abort_reason=run.abort_reason,
    )
