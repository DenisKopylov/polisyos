"""Signature helper operations for `FileSystemCAS`."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
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
) -> DetachedSignature:
    """Sign one stored artifact and persist its sidecar."""
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
    verify_integrity: Callable[[ArtifactID], IntegrityVerificationReport],
    load_signature: Callable[[ArtifactID], DetachedSignature | None],
    read_blob: Callable[[ArtifactID], bytes],
    read_manifest_bytes: Callable[[ArtifactID], bytes],
) -> SignatureVerificationResult:
    """Verify content integrity plus one detached signature sidecar."""
    integrity = verify_integrity(artifact_id)
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
) -> BulkSigningReport:
    """Sign many artifacts concurrently and summarize the result set."""
    ids = list(artifact_ids)
    details: list[ArtifactSigningResult] = []
    signer_lock = threading.Lock()

    def _sign_one(aid: ArtifactID) -> ArtifactSigningResult:
        if only_unsigned and has_signature_for_artifact(aid):
            return ArtifactSigningResult(
                artifact_id=str(aid),
                status="skipped",
                message="already signed",
            )
        try:
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

    workers = max(1, int(max_workers))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(_sign_one, ids):
            details.append(result)

    signed = sum(1 for item in details if item.status == "signed")
    skipped = sum(1 for item in details if item.status == "skipped")
    errors = sum(1 for item in details if item.status == "error")
    return BulkSigningReport(
        total=len(ids),
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
) -> BulkVerificationReport:
    """Verify many detached signatures concurrently and summarize statuses."""
    ids = list(artifact_ids)
    details: list[SignatureVerificationResult] = []

    def _verify_one(aid: ArtifactID) -> SignatureVerificationResult:
        return verify_one(aid, verifier, strict_identity)

    workers = max(1, int(max_workers))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(_verify_one, ids):
            details.append(result)

    valid = sum(1 for item in details if item.status == SignatureVerificationStatus.VALID)
    unsigned = sum(1 for item in details if item.status == SignatureVerificationStatus.UNSIGNED)
    invalid = sum(1 for item in details if item.status == SignatureVerificationStatus.INVALID)
    untrusted = sum(1 for item in details if item.status == SignatureVerificationStatus.UNTRUSTED)
    revoked = sum(1 for item in details if item.status == SignatureVerificationStatus.REVOKED)
    errors = sum(1 for item in details if item.status == SignatureVerificationStatus.ERROR)
    return BulkVerificationReport(
        total=len(ids),
        valid=valid,
        unsigned=unsigned,
        invalid=invalid,
        untrusted=untrusted,
        revoked=revoked,
        errors=errors,
        details=details,
    )
