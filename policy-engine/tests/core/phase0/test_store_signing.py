from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
    SigningConfig,
    SigningError,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions

if TYPE_CHECKING:
    from pathlib import Path


def _make_signed_store(tmp_path: Path) -> tuple[FileSystemCAS, Ed25519Signer, Ed25519Verifier]:
    store = FileSystemCAS(tmp_path)
    keypair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(keypair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(keypair.public_key, key_id=keypair.key_id)
    return store, signer, verifier


def test_sign_artifact_writes_sidecar_file(tmp_path: Path) -> None:
    store, signer, _ = _make_signed_store(tmp_path)
    ref = store.put_bytes(
        b"artifact",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )

    signature = store.sign_artifact(ref.artifact_id, signer, signer_identity="dev")

    assert store.has_signature(ref.artifact_id)
    sig = store.get_signature(ref.artifact_id)
    assert sig is not None
    assert sig.signature_hex == signature.signature_hex


def test_verify_signature_unsigned_status(tmp_path: Path) -> None:
    store, _, verifier = _make_signed_store(tmp_path)
    ref = store.put_bytes(
        b"unsigned",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )

    result = store.verify_signature(ref.artifact_id, verifier)

    assert result.status == SignatureVerificationStatus.UNSIGNED


def test_verify_signature_invalid_sidecar_format(tmp_path: Path) -> None:
    store, _, verifier = _make_signed_store(tmp_path)
    ref = store.put_bytes(
        b"unsigned",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    sig_path = store._sig_path(ref.artifact_id)
    sig_path.write_text("{not valid json}", encoding="utf-8")

    result = store.verify_signature(ref.artifact_id, verifier)

    assert result.status == SignatureVerificationStatus.ERROR


def test_verify_signature_valid(tmp_path: Path) -> None:
    store, signer, verifier = _make_signed_store(tmp_path)
    ref = store.put_bytes(
        b"signed",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    store.sign_artifact(ref.artifact_id, signer, signer_identity="ci")

    result = store.verify_signature(ref.artifact_id, verifier)

    assert result.status == SignatureVerificationStatus.VALID
    assert result.ok


def test_export_import_preserves_signatures(tmp_path: Path) -> None:
    source = FileSystemCAS(tmp_path / "source")
    keypair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(keypair.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(keypair.public_key, key_id=keypair.key_id)

    leaf = source.put_json(
        {"leaf": True},
        PutOptions(kind="test.leaf", media_type="application/json"),
    )
    root = source.put_json(
        {"root": True},
        PutOptions(
            kind="test.root",
            media_type="application/json",
        ),
    )
    source.sign_artifact(leaf.artifact_id, signer)
    source.sign_artifact(root.artifact_id, signer)

    archive = tmp_path / "bundle.tar.gz"
    export = source.export_subgraph([leaf.artifact_id, root.artifact_id], archive)
    assert export.output_path.exists()

    target = FileSystemCAS(tmp_path / "target")
    target.import_subgraph(export.output_path, verify_integrity=True)

    leaf_result = target.verify_signature(leaf.artifact_id, verifier)
    root_result = target.verify_signature(root.artifact_id, verifier)
    assert leaf_result.status == SignatureVerificationStatus.VALID
    assert root_result.status == SignatureVerificationStatus.VALID


def test_sign_all_artifacts_only_unsigned(tmp_path: Path) -> None:
    store, signer, _ = _make_signed_store(tmp_path)
    a = store.put_bytes(b"a", PutOptions(kind="test.bytes", media_type="application/octet-stream"))
    b = store.put_bytes(b"b", PutOptions(kind="test.bytes", media_type="application/octet-stream"))

    store.sign_artifact(a.artifact_id, signer)
    report = store.sign_all_artifacts(signer, only_unsigned=True, max_workers=2)

    assert report.total == 2
    assert report.signed == 1
    assert report.skipped == 1
    assert report.errors == 0
    assert store.has_signature(a.artifact_id)
    assert store.has_signature(b.artifact_id)


def test_verify_all_signatures_counts_statuses(tmp_path: Path) -> None:
    store, signer, verifier = _make_signed_store(tmp_path)
    signed = store.put_bytes(
        b"signed",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    store.put_bytes(
        b"unsigned",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    store.sign_artifact(signed.artifact_id, signer)

    report = store.verify_all_signatures(verifier, max_workers=2)

    assert report.total == 2
    assert report.valid == 1
    assert report.unsigned == 1
    assert report.invalid == 0
    assert report.errors == 0


def test_sign_on_put_fail_policy_raises(tmp_path: Path) -> None:
    config = SigningConfig(
        enabled=True,
        sign_on_put=True,
        sign_on_put_policy="fail",
        private_key_env="POLISYOS_TEST_MISSING_SIGNING_KEY",
        private_key_file_env="POLISYOS_TEST_MISSING_SIGNING_KEY_FILE",
        private_key_file=tmp_path / "missing.pem",
    )
    store = FileSystemCAS(tmp_path, signing_config=config)

    with pytest.raises(SigningError):
        store.put_bytes(
            b"x",
            PutOptions(kind="test.bytes", media_type="application/octet-stream"),
        )


def test_sign_on_put_success_with_env_key(monkeypatch, tmp_path: Path) -> None:
    pair = KeyPair.generate()
    monkeypatch.setenv("POLISYOS_TEST_SIGNING_KEY", pair.private_pem().decode("utf-8"))

    config = SigningConfig(
        enabled=True,
        sign_on_put=True,
        sign_on_put_policy="fail",
        private_key_env="POLISYOS_TEST_SIGNING_KEY",
        private_key_file_env="POLISYOS_TEST_SIGNING_KEY_FILE",
        private_key_file=tmp_path / "unused.pem",
        default_identity="ci",
    )
    store = FileSystemCAS(tmp_path, signing_config=config)
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)

    ref = store.put_bytes(
        b"auto",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    assert store.has_signature(ref.artifact_id)

    result = store.verify_signature(ref.artifact_id, verifier)
    assert result.status == SignatureVerificationStatus.VALID


def test_artifact_id_extraction_supports_sig_suffix(tmp_path: Path) -> None:
    aid = ArtifactID.from_sha256_hex("a" * 64)
    path = f"artifacts/sha256/aa/aa/{aid.hex}.sig"

    parsed = FileSystemCAS._artifact_id_from_member(path)

    assert parsed is not None
    assert str(parsed) == str(aid)
