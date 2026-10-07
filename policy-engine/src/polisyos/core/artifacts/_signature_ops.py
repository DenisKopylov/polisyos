"""Signature helper operations for `FileSystemCAS`."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Sized
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .manifest import ArtifactRef
from .signing import (
    ArtifactBatchAbortError,
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

    @property
    def data(self) -> bytes: ...

    @property
    def manifest_bytes(self) -> bytes: ...


def _pending_window(max_workers: int, requested: int | None) -> int:
    workers = max(1, int(max_workers))
    return max(1, int(requested)) if requested is not None else workers


def _source_length_hint(source: Iterable[object]) -> int | None:
    return len(source) if isinstance(source, Sized) else None


@dataclass(frozen=True)
class _BoundedRun[Result]:
    indexed: list[tuple[int, Result]]
    length_hint: int | None
    admitted: int
    exhausted: bool
    abort_reason: str | None


def check_batch_admission(
    cancel_event: threading.Event | None,
    deadline: float | None,
) -> None:
    """Check a logical stop boundary without claiming to preempt physical callbacks."""
    if cancel_event is not None and cancel_event.is_set():
        raise ArtifactBatchAbortError("cancelled")
    if deadline is not None and time.monotonic() >= deadline:
        raise ArtifactBatchAbortError("deadline")


def _run_bounded[Item, Result](
    artifact_ids: Iterable[Item],
    process: Callable[[Item], Result],
    *,
    max_workers: int,
    pending_window: int | None,
    cancel_event: threading.Event | None,
    deadline: float | None,
    cancelled_result: Callable[[Item], Result],
) -> _BoundedRun[Result]:
    """Bound iterator admission and futures; drain physical work after a logical abort.

    No new items are admitted after cancellation/deadline/global failure. Running
    callbacks retain ownership until completion; uncooperative I/O can outlive the
    logical deadline. BaseException is never converted to successful-looking rows.
    """
    if deadline is not None and not math.isfinite(deadline):
        raise ValueError("batch deadline must be a finite absolute monotonic time")
    iterator = iter(artifact_ids)
    pending: dict[Future[Result], tuple[int, Item]] = {}
    results: list[tuple[int, Result]] = []
    next_index = 0
    exhausted = False
    abort_reason: str | None = None
    window = _pending_window(max_workers, pending_window)
    length_hint = _source_length_hint(artifact_ids)

    def checkpoint() -> bool:
        nonlocal abort_reason
        if abort_reason is not None:
            return False
        try:
            check_batch_admission(cancel_event, deadline)
        except ArtifactBatchAbortError as exc:
            abort_reason = exc.reason
            return False
        return True

    def fill_window(executor: ThreadPoolExecutor) -> None:
        nonlocal exhausted, next_index, abort_reason
        while not exhausted and len(pending) < window and checkpoint():
            try:
                artifact_id = next(iterator)
            except StopIteration:
                exhausted = True
                return
            except ArtifactBatchAbortError as exc:
                abort_reason = exc.reason
                return
            except Exception:
                abort_reason = "inventory_failed"
                return
            if not checkpoint():
                return
            try:
                future = executor.submit(copy_context().run, process, artifact_id)
            except Exception:
                abort_reason = "executor_failed"
                return
            pending[future] = (next_index, artifact_id)
            next_index += 1

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        fill_window(executor)
        while pending:
            checkpoint()
            if abort_reason is not None:
                for future, (index, item) in tuple(pending.items()):
                    if future.cancel():
                        pending.pop(future)
                        results.append((index, cancelled_result(item)))
                if not pending:
                    break
            timeout = 0.05
            if abort_reason is None and deadline is not None:
                timeout = min(timeout, max(0.0, deadline - time.monotonic()))
            done, _ = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
            for future in done:
                index, item = pending.pop(future)
                try:
                    result = future.result()
                except ArtifactBatchAbortError as exc:
                    abort_reason = exc.reason
                    result = cancelled_result(item)
                # BaseException deliberately escapes. Executor failure preserves
                # all completed rows while declaring the common basis aborted.
                except Exception:
                    abort_reason = "executor_failed"
                    result = cancelled_result(item)
                results.append((index, result))
            checkpoint()
            fill_window(executor)
    return _BoundedRun(results, length_hint, next_index, exhausted, abort_reason)


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
        except ArtifactBatchAbortError:
            raise
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
        except ArtifactBatchAbortError:
            raise
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
    except ArtifactBatchAbortError:
        raise
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
        except ArtifactBatchAbortError:
            raise
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
    deadline: float | None = None,
    load_snapshot: Callable[[ArtifactID], VerifiedArtifactSnapshot] | None = None,
) -> BulkSigningReport:
    """Sign many artifacts concurrently and summarize the result set."""
    signer_lock = threading.Lock()

    def _sign_one(aid: ArtifactID) -> ArtifactSigningResult:
        try:
            check_batch_admission(cancel_event, deadline)
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
            check_batch_admission(cancel_event, deadline)
            write_signature(aid, signature)
            return ArtifactSigningResult(
                artifact_id=str(aid),
                status="signed",
                key_id=signature.key_id,
            )
        except ArtifactBatchAbortError:
            raise
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
        deadline=deadline,
        cancelled_result=lambda aid: ArtifactSigningResult(
            artifact_id=str(aid), status="error", message="Batch stopped before item completion"
        ),
    )
    details = [result for _index, result in sorted(run.indexed, key=lambda item: item[0])]
    if run.abort_reason is not None:
        details.append(
            ArtifactSigningResult(
                artifact_id="<batch>",
                status="error",
                message=(
                    "Batch inventory source failed; results are incomplete"
                    if run.abort_reason == "inventory_failed"
                    else f"Batch {run.abort_reason}; results are incomplete"
                ),
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
        abort_reason=run.abort_reason,
        admitted=run.admitted,
        finished=len(run.indexed),
        inventory_exhausted=run.exhausted,
    )


def verify_all_signatures(
    *,
    verifier: Ed25519Verifier,
    artifact_ids: Iterable[ArtifactID | ArtifactRef],
    max_workers: int,
    strict_identity: bool | None,
    verify_one: Callable[
        [ArtifactID | ArtifactRef, Ed25519Verifier, bool | None], SignatureVerificationResult
    ],
    pending_window: int | None = None,
    cancel_event: threading.Event | None = None,
    deadline: float | None = None,
) -> BulkVerificationReport:
    """Verify many detached signatures concurrently and summarize statuses."""

    def _verify_one(aid: ArtifactID | ArtifactRef) -> SignatureVerificationResult:
        try:
            return verify_one(aid, verifier, strict_identity)
        except ArtifactBatchAbortError:
            raise
        except Exception as exc:
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=str(aid.artifact_id) if isinstance(aid, ArtifactRef) else str(aid),
                artifact_ref=aid if isinstance(aid, ArtifactRef) else None,
                message=str(exc),
            )

    run = _run_bounded(
        artifact_ids,
        _verify_one,
        max_workers=max_workers,
        pending_window=pending_window,
        cancel_event=cancel_event,
        deadline=deadline,
        cancelled_result=lambda aid: SignatureVerificationResult(
            status=SignatureVerificationStatus.ERROR,
            artifact_id=str(aid.artifact_id) if isinstance(aid, ArtifactRef) else str(aid),
            artifact_ref=aid if isinstance(aid, ArtifactRef) else None,
            message="Batch stopped before item completion",
        ),
    )
    details = [result for _index, result in sorted(run.indexed, key=lambda item: item[0])]
    if run.abort_reason is not None:
        details.append(
            SignatureVerificationResult(
                artifact_id="<batch>",
                status=SignatureVerificationStatus.ERROR,
                message=(
                    "Batch inventory source failed; results are incomplete"
                    if run.abort_reason == "inventory_failed"
                    else f"Batch {run.abort_reason}; results are incomplete"
                ),
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
        abort_reason=run.abort_reason,
        admitted=run.admitted,
        finished=len(run.indexed),
        inventory_exhausted=run.exhausted,
    )
