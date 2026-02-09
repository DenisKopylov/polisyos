from __future__ import annotations

import hashlib
import json
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
    SigningConfig,
    build_verifier_from_config,
    compute_key_id,
)


def _artifact_payload() -> tuple[ArtifactID, bytes, bytes]:
    blob_data = b"policy-os-signing-test"
    artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(blob_data).hexdigest())
    manifest_data = json.dumps(
        {
            "artifact_id": str(artifact_id),
            "integrity": {"sha256": artifact_id.hex},
            "kind": "test.kind",
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return artifact_id, blob_data, manifest_data


def test_keypair_generation_and_key_id_stable() -> None:
    pair = KeyPair.generate()
    key_id_1 = pair.key_id
    key_id_2 = compute_key_id(pair.public_key)

    assert key_id_1 == key_id_2
    assert key_id_1.startswith("sha256:")
    assert len(key_id_1) == len("sha256:") + 64


def test_private_public_pem_roundtrip() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())

    assert signer.key_id == pair.key_id



def test_sign_verify_roundtrip_valid() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)

    artifact_id, blob_data, manifest_data = _artifact_payload()
    signature = signer.sign(
        artifact_id,
        blob_data,
        manifest_data,
        signer_identity="ci-prod",
    )
    result = verifier.verify(artifact_id, blob_data, manifest_data, signature)

    assert result.status == SignatureVerificationStatus.VALID
    assert result.ok


def test_verify_rejects_tampered_blob() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)

    artifact_id, blob_data, manifest_data = _artifact_payload()
    signature = signer.sign(artifact_id, blob_data, manifest_data)
    result = verifier.verify(artifact_id, blob_data + b"!", manifest_data, signature)

    assert result.status == SignatureVerificationStatus.INVALID
    assert not result.ok


def test_verify_rejects_tampered_manifest() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)

    artifact_id, blob_data, manifest_data = _artifact_payload()
    signature = signer.sign(artifact_id, blob_data, manifest_data)
    result = verifier.verify(artifact_id, blob_data, manifest_data + b" ", signature)

    assert result.status == SignatureVerificationStatus.INVALID


def test_verify_rejects_untrusted_key() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()

    artifact_id, blob_data, manifest_data = _artifact_payload()
    signature = signer.sign(artifact_id, blob_data, manifest_data)
    result = verifier.verify(artifact_id, blob_data, manifest_data, signature)

    assert result.status == SignatureVerificationStatus.UNTRUSTED


def test_verify_rejects_revoked_key() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)
    verifier.add_revoked_key_id(pair.key_id)

    artifact_id, blob_data, manifest_data = _artifact_payload()
    signature = signer.sign(artifact_id, blob_data, manifest_data)
    result = verifier.verify(artifact_id, blob_data, manifest_data, signature)

    assert result.status == SignatureVerificationStatus.REVOKED


def test_identity_mismatch_strict_mode_fails() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id, identity="ci-prod")

    artifact_id, blob_data, manifest_data = _artifact_payload()
    signature = signer.sign(
        artifact_id,
        blob_data,
        manifest_data,
        signer_identity="spoofed-name",
    )
    result = verifier.verify(artifact_id, blob_data, manifest_data, signature)

    assert result.status == SignatureVerificationStatus.INVALID


def test_identity_mismatch_non_strict_mode_warns() -> None:
    pair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(pair.private_pem())
    verifier = Ed25519Verifier(strict_identity=False)
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id, identity="ci-prod")

    artifact_id, blob_data, manifest_data = _artifact_payload()
    signature = signer.sign(
        artifact_id,
        blob_data,
        manifest_data,
        signer_identity="spoofed-name",
    )
    result = verifier.verify(artifact_id, blob_data, manifest_data, signature)

    assert result.status == SignatureVerificationStatus.VALID
    assert result.message is not None


def test_signer_from_env_or_file_prefers_env(monkeypatch, tmp_path: Path) -> None:
    pair = KeyPair.generate()
    key_path = tmp_path / "signing.pem"
    key_path.write_bytes(pair.private_pem())

    env_pair = KeyPair.generate()
    monkeypatch.setenv("POLISYOS_SIGNING_KEY", env_pair.private_pem().decode("utf-8"))
    monkeypatch.setenv("POLISYOS_SIGNING_KEY_FILE", str(key_path))

    signer = Ed25519Signer.from_env_or_file()
    assert signer.key_id == env_pair.key_id


def test_build_verifier_from_config_loads_trust_revoked_identity(tmp_path: Path) -> None:
    trusted_dir = tmp_path / "trusted"
    revoked_dir = tmp_path / "revoked"
    identities_path = tmp_path / "identities.json"
    trusted_dir.mkdir(parents=True)
    revoked_dir.mkdir(parents=True)

    trusted_pair = KeyPair.generate()
    revoked_pair = KeyPair.generate()

    (trusted_dir / "trusted.pub").write_bytes(trusted_pair.public_pem())
    (revoked_dir / "revoked.pub").write_bytes(revoked_pair.public_pem())
    identities_path.write_text(
        json.dumps(
            {
                trusted_pair.key_id: "ci-prod",
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    verifier = build_verifier_from_config(
        SigningConfig(
            trust_dir=trusted_dir,
            revoked_dir=revoked_dir,
            identities_path=identities_path,
        )
    )

    assert trusted_pair.key_id in verifier.trusted_key_ids
    assert revoked_pair.key_id in verifier.revoked_key_ids
    assert verifier.expected_identity(trusted_pair.key_id) == "ci-prod"
