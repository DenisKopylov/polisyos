"""Behavioral tests for exact-byte signed artifact evidence."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    Ed25519Signer,
    FileSystemCAS,
)


def test_generic_artifact_store_is_not_signed_evidence_repository() -> None:
    """Removing the exact-manifest port must keep receipt issuance unavailable."""
    from polisyos.core.artifacts.signed_evidence import supports_signed_evidence_repository

    class GenericStore:
        def get_bytes(self, artifact_id: object) -> bytes:
            return b""

        def get_manifest(self, artifact_id: object) -> object:
            return object()

    assert supports_signed_evidence_repository(GenericStore()) is False


def _ref(label: str) -> ArtifactRef:
    import hashlib

    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"
        ),
        kind="fixture",
        media_type="application/octet-stream",
    )


def test_filesystem_repository_round_trips_actual_signed_bytes(tmp_path: Path) -> None:
    """The exact persisted sidecar, not a reconstructed parsed twin, is returned."""
    from polisyos.core.artifacts.signed_evidence import (
        FileSystemSignedArtifactEvidenceRepository,
    )

    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSystemSignedArtifactEvidenceRepository(store)
    persisted = repository.persist_signed(
        blob_bytes=b"accepted-anchor-statement",
        write_options=ArtifactWriteOptions(
            kind="fixture.anchor",
            media_type="application/octet-stream",
        ),
        signer=Ed25519Signer(Ed25519PrivateKey.generate()),
        signing_profile_ref=_ref("signing-profile"),
        signer_provenance_ref=_ref("signer-provenance"),
    )
    evidence = repository.read_exact(evidence_record_ref=persisted.evidence_record_ref)
    assert evidence.blob_bytes == b"accepted-anchor-statement"
    assert evidence.detached_signature_bytes.startswith(b"{")
    assert evidence.persisted == persisted


def test_sidecar_byte_substitution_is_rejected(tmp_path: Path) -> None:
    """A valid parsed signature with changed exact bytes must not pass readback."""
    from polisyos.core.artifacts.signed_evidence import (
        FileSystemSignedArtifactEvidenceRepository,
    )

    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSystemSignedArtifactEvidenceRepository(store)
    persisted = repository.persist_signed(
        blob_bytes=b"statement",
        write_options=ArtifactWriteOptions(
            kind="fixture.anchor",
            media_type="application/octet-stream",
        ),
        signer=Ed25519Signer(Ed25519PrivateKey.generate()),
        signing_profile_ref=_ref("signing-profile"),
        signer_provenance_ref=_ref("signer-provenance"),
    )
    record = repository.read_exact(evidence_record_ref=persisted.evidence_record_ref)
    import json

    payload = json.loads(record.detached_signature_bytes)
    artifact_id = ArtifactID.model_validate(payload["artifact_id"])
    blob_path, _ = store.get_paths(artifact_id)
    signature_path = blob_path.with_suffix(".sig")
    signature_path.chmod(0o644)
    signature_path.write_bytes(record.detached_signature_bytes + b"\n")
    with pytest.raises(ValueError, match="sidecar differs"):
        repository.read_exact(evidence_record_ref=persisted.evidence_record_ref)
