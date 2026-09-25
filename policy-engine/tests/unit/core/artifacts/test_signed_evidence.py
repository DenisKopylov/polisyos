"""Behavioral tests for exact-byte signed artifact evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    Ed25519Signer,
    Ed25519Verifier,
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

    framed_length = int.from_bytes(record.persisted.record_bytes[:8], "big")
    record_payload = json.loads(record.persisted.record_bytes[8 : 8 + framed_length])
    from polisyos.core.contracts.chronology import SignedArtifactEvidenceRecord

    signed_ref = SignedArtifactEvidenceRecord.model_validate(record_payload).artifact_ref
    assert signed_ref.manifest_profile_sha256 is not None
    signature_path = store._layout.view_sig_path(
        signed_ref.artifact_id,
        signed_ref.manifest_profile_sha256,
    )
    signature_path.chmod(0o644)
    signature_path.write_bytes(record.detached_signature_bytes + b"\n")
    with pytest.raises(ValueError, match="sidecar differs"):
        repository.read_exact(evidence_record_ref=persisted.evidence_record_ref)


def test_signed_evidence_keeps_the_exact_selected_manifest_view(tmp_path: Path) -> None:
    """A repeated blob with another profile is signed and replayed as that view."""
    from polisyos.core.artifacts.signed_evidence import (
        FileSystemSignedArtifactEvidenceRepository,
    )
    from polisyos.core.contracts.chronology import SignedArtifactEvidenceRecord

    store = FileSystemCAS(tmp_path / "cas")
    repository = FileSystemSignedArtifactEvidenceRepository(store)
    key = Ed25519PrivateKey.generate()
    signer = Ed25519Signer(key)
    payload = b"identical bytes with distinct manifest views"
    store.put_bytes(
        payload,
        ArtifactWriteOptions(kind="prior.view", media_type="application/octet-stream"),
    )
    persisted = repository.persist_signed(
        blob_bytes=payload,
        write_options=ArtifactWriteOptions(
            kind="signed.view",
            media_type="application/octet-stream",
        ),
        signer=signer,
        signing_profile_ref=_ref("signing-profile"),
        signer_provenance_ref=_ref("signer-provenance"),
    )

    evidence = repository.read_exact(evidence_record_ref=persisted.evidence_record_ref)
    framed_length = int.from_bytes(persisted.record_bytes[:8], "big")
    record_payload = json.loads(persisted.record_bytes[8 : 8 + framed_length])
    record = SignedArtifactEvidenceRecord.model_validate(record_payload)

    assert record.artifact_ref.manifest_profile_sha256 is not None
    assert evidence.exact_manifest_bytes == store.get_manifest_bytes(record.artifact_ref)
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key.public_key())
    assert store.verify_signature(record.artifact_ref, verifier).ok is True
