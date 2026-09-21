"""Shared integrity verification helpers for artifact stores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ..canon import content_hash
from .manifest import ArtifactManifest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .ids import ArtifactID


class VerificationReport(BaseModel):
    """Report byte-level CAS integrity for one artifact/blob-manifest pair."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    artifact_id: str
    expected_sha256_hex: str
    actual_sha256_hex: str | None = None
    byte_size: int | None = None
    error: str | None = None


class ArtifactIntegrityError(ValueError):
    """Raised when a stored blob or manifest fails read-time integrity validation."""


@dataclass(frozen=True)
class VerifiedArtifactSnapshot:
    """Immutable bytes/manifest view produced by one filesystem read."""

    data: bytes
    manifest_bytes: bytes
    actual_sha256_hex: str
    byte_size: int


def validate_manifest_identity(
    artifact_id: ArtifactID,
    manifest: ArtifactManifest,
) -> None:
    """Fail closed when a manifest is not bound to the requested artifact."""
    if str(manifest.artifact_id) != str(artifact_id):
        raise ArtifactIntegrityError(
            f"Manifest artifact_id mismatch for {artifact_id}: {manifest.artifact_id}"
        )
    if manifest.integrity.sha256 != artifact_id.hex:
        raise ArtifactIntegrityError(
            f"Manifest integrity mismatch for {artifact_id}: {manifest.integrity.sha256}"
        )


def validate_read_integrity(
    artifact_id: ArtifactID,
    data: bytes,
    manifest: ArtifactManifest,
) -> None:
    """Verify manifest binding, blob digest, and byte-size agreement."""
    actual = content_hash(data)
    _validate_read_integrity_with_digest(
        artifact_id,
        data=data,
        manifest=manifest,
        actual_sha256_hex=actual,
    )


def _validate_read_integrity_with_digest(
    artifact_id: ArtifactID,
    *,
    data: bytes,
    manifest: ArtifactManifest,
    actual_sha256_hex: str,
) -> None:
    """Validate a loaded pair without recomputing a caller-independent digest."""
    validate_manifest_identity(artifact_id, manifest)
    if actual_sha256_hex != artifact_id.hex:
        raise ArtifactIntegrityError(
            f"Blob sha256 mismatch for {artifact_id}: {actual_sha256_hex}"
        )
    if manifest.byte_size != len(data):
        raise ArtifactIntegrityError(
            f"Manifest byte_size mismatch for {artifact_id}: "
            f"expected {manifest.byte_size}, got {len(data)}"
        )


def read_verified_blob(
    artifact_id: ArtifactID,
    blob_path: Path,
    *,
    load_manifest: Callable[[ArtifactID], ArtifactManifest],
    record_integrity_failure: Callable[..., None] | None = None,
) -> bytes:
    """Read one blob from disk and enforce mandatory integrity validation."""
    if not blob_path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_id.hex}")
    data = blob_path.read_bytes()
    manifest = load_manifest(artifact_id)
    try:
        validate_read_integrity(artifact_id, data, manifest)
    except ArtifactIntegrityError as exc:
        if record_integrity_failure is not None:
            record_integrity_failure(reason=type(exc).__name__)
        raise
    return data


def load_verified_artifact_snapshot(
    artifact_id: ArtifactID,
    *,
    blob_path: Path,
    manifest_path: Path,
    record_integrity_failure: Callable[..., None] | None = None,
) -> VerifiedArtifactSnapshot:
    """Read and validate one immutable blob/manifest snapshot.

    The raw manifest bytes are retained for signing so that the verifier sees
    exactly the bytes that were validated and not a re-serialized model.
    """
    if not blob_path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_id.hex}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {artifact_id.hex}")

    data = blob_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    manifest = ArtifactManifest.model_validate_json(manifest_bytes)
    actual = content_hash(data)
    try:
        _validate_read_integrity_with_digest(
            artifact_id,
            data=data,
            manifest=manifest,
            actual_sha256_hex=actual,
        )
    except ArtifactIntegrityError as exc:
        if record_integrity_failure is not None:
            record_integrity_failure(reason=type(exc).__name__)
        raise
    return VerifiedArtifactSnapshot(
        data=data,
        manifest_bytes=manifest_bytes,
        actual_sha256_hex=actual,
        byte_size=len(data),
    )


def verify_filesystem_artifact(
    artifact_id: ArtifactID,
    *,
    blob_path: Path,
    manifest_path: Path,
) -> VerificationReport:
    """Build a verification report for a filesystem-backed artifact pair."""
    try:
        if not blob_path.exists():
            return VerificationReport(
                ok=False,
                artifact_id=str(artifact_id),
                expected_sha256_hex=artifact_id.hex,
                error="blob missing",
            )
        if not manifest_path.exists():
            return VerificationReport(
                ok=False,
                artifact_id=str(artifact_id),
                expected_sha256_hex=artifact_id.hex,
                error="manifest missing",
            )

        data = blob_path.read_bytes()
        actual = content_hash(data)
        if actual != artifact_id.hex:
            return VerificationReport(
                ok=False,
                artifact_id=str(artifact_id),
                expected_sha256_hex=artifact_id.hex,
                actual_sha256_hex=actual,
                byte_size=len(data),
                error="sha256 mismatch",
            )

        try:
            manifest = ArtifactManifest.model_validate_json(manifest_path.read_text("utf-8"))
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return VerificationReport(
                ok=False,
                artifact_id=str(artifact_id),
                expected_sha256_hex=artifact_id.hex,
                actual_sha256_hex=actual,
                byte_size=len(data),
                error=f"manifest invalid: {exc}",
            )

        return _verification_report_from_loaded_artifact_with_digest(
            artifact_id,
            data=data,
            manifest=manifest,
            actual_sha256_hex=actual,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return VerificationReport(
            ok=False,
            artifact_id=str(artifact_id),
            expected_sha256_hex=artifact_id.hex,
            error=str(exc),
        )


def verify_loaded_artifact(
    artifact_id: ArtifactID,
    *,
    load_bytes: Callable[[ArtifactID], bytes],
    load_manifest: Callable[[ArtifactID], ArtifactManifest],
) -> VerificationReport:
    """Build a verification report for a backend that loads bytes/manifests via callables."""
    try:
        data = load_bytes(artifact_id)
        manifest = load_manifest(artifact_id)
    except (AttributeError, FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return VerificationReport(
            ok=False,
            artifact_id=str(artifact_id),
            expected_sha256_hex=artifact_id.hex,
            error=str(exc),
        )
    return verification_report_from_loaded_artifact(
        artifact_id,
        data=data,
        manifest=manifest,
    )


def verification_report_from_loaded_artifact(
    artifact_id: ArtifactID,
    *,
    data: bytes,
    manifest: ArtifactManifest,
) -> VerificationReport:
    """Convert already-loaded bytes/manifest data into a stable integrity report."""
    return _verification_report_from_loaded_artifact_with_digest(
        artifact_id,
        data=data,
        manifest=manifest,
        actual_sha256_hex=content_hash(data),
    )


def _verification_report_from_loaded_artifact_with_digest(
    artifact_id: ArtifactID,
    *,
    data: bytes,
    manifest: ArtifactManifest,
    actual_sha256_hex: str,
) -> VerificationReport:
    """Build a report from a digest computed by this module's local reader."""
    actual = actual_sha256_hex
    try:
        _validate_read_integrity_with_digest(
            artifact_id,
            data=data,
            manifest=manifest,
            actual_sha256_hex=actual,
        )
    except ArtifactIntegrityError as exc:
        return VerificationReport(
            ok=False,
            artifact_id=str(artifact_id),
            expected_sha256_hex=artifact_id.hex,
            actual_sha256_hex=actual,
            byte_size=len(data),
            error=_normalize_verification_error(str(exc)),
        )
    return VerificationReport(
        ok=True,
        artifact_id=str(artifact_id),
        expected_sha256_hex=artifact_id.hex,
        actual_sha256_hex=actual,
        byte_size=len(data),
    )


def _normalize_verification_error(detail: str) -> str:
    if "Blob sha256 mismatch" in detail:
        return "sha256 mismatch"
    if "byte_size mismatch" in detail:
        return "byte_size mismatch"
    if "Manifest " in detail:
        return "manifest integrity mismatch"
    return detail


__all__ = [
    "ArtifactIntegrityError",
    "VerificationReport",
    "VerifiedArtifactSnapshot",
    "load_verified_artifact_snapshot",
    "read_verified_blob",
    "validate_manifest_identity",
    "validate_read_integrity",
    "verification_report_from_loaded_artifact",
    "verify_filesystem_artifact",
    "verify_loaded_artifact",
]
