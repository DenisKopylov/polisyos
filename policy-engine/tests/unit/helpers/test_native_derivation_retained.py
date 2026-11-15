"""Retained institutional signatures remain bound to their exact CAS view."""

from pathlib import Path

import pytest

from polisyos.core import artifacts
from tests._helpers.native_derivation_retained import _verify_retained_selected_signature


def test_legacy_signature_recovers_only_the_original_selected_manifest(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    key = artifacts.KeyPair.generate()
    signer = artifacts.Ed25519Signer.from_pem(key.private_pem())
    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(key.public_key, key_id=key.key_id, identity="fixture-owner")
    original = store.put_bytes(
        b"one immutable signed body",
        artifacts.PutOptions(kind="test.native.original", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    store.sign_artifact(original.artifact_id, signer, signer_identity="fixture-owner")
    other_view = store.put_bytes(
        store.get_bytes(original),
        artifacts.PutOptions(kind="test.native.other", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    assert original.artifact_id == other_view.artifact_id
    assert original.manifest_profile_sha256 != other_view.manifest_profile_sha256
    assert store.get_signature(original) is None
    assert store.get_signature(other_view) is None
    assert store.get_manifest_bytes(original) == store.get_manifest_bytes(original.artifact_id)
    before = {str(path): path.read_bytes() for path in store.base.rglob("*") if path.is_file()}

    _verify_retained_selected_signature(store, original, verifier)
    with pytest.raises(ValueError, match="retained_native_continuation_mandate_signature_invalid"):
        _verify_retained_selected_signature(store, other_view, verifier)

    assert {
        str(path): path.read_bytes() for path in store.base.rglob("*") if path.is_file()
    } == before
