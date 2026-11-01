"""Required cryptographic transfer admission before any owner publication."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    ImportSignatureVerificationError,
    PutOptions,
)
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
)


@pytest.fixture(autouse=True)
def _required_signature_removal(monkeypatch):
    if os.environ.get("E02_CAS02_REMOVAL") != "required-signature":
        return
    original = FileSystemCAS.import_subgraph

    def remove_policy(store, *args, **kwargs):
        kwargs.pop("signature_verifier", None)
        return original(store, *args, **kwargs)

    monkeypatch.setattr(FileSystemCAS, "import_subgraph", remove_policy)


def _store(root: Path) -> FileSystemCAS:
    return FileSystemCAS(root, tenant_id="signature-tenant", cell_id="signature-cell")


def _views(store, signer, *, signed=True, payload=b"same blob with distinct signed views"):
    refs = [
        store.put_bytes(
            payload,
            PutOptions(kind=kind, media_type="application/octet-stream"),
            return_selected_profile=True,
        )
        for kind in ("tests.signature.a", "tests.signature.b")
    ]
    if signed:
        store.sign_artifact(refs[0].artifact_id, signer, signer_identity="transfer-owner")
        store.sign_artifact(refs[1], signer, signer_identity="transfer-owner")
    return refs


def _snapshot(store):
    return (
        {
            str(p.relative_to(store.base)): p.read_bytes()
            for p in store.base.rglob("*")
            if p.is_file()
        },
        store._owner_generation_token(),
    )


def _ref_keys(refs):
    return sorted(
        (str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256)
        for ref in refs
    )


def _keyring():
    key = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key.private_pem())
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(key.public_key, key_id=key.key_id, identity="transfer-owner")
    return key, signer, verifier


@pytest.mark.parametrize("compress", [False, True])
def test_required_all_views_survive_fresh_reader_and_exact_noop(compress, tmp_path, monkeypatch):
    key, signer, verifier = _keyring()
    source = _store(tmp_path / "source")
    refs = _views(source, signer)
    package = tmp_path / ("package.tar.gz" if compress else "package")
    source.export_subgraph([refs[0].artifact_id, refs[1]], package, compress=compress)
    receiver = _store(tmp_path / "receiver")
    report = receiver.import_subgraph(package, signature_verifier=verifier)
    assert report.signature_verification_requested is True
    assert _ref_keys(report.signature_verified_refs) == _ref_keys(refs)
    assert len(report.published_refs) == 2
    fresh = _store(receiver.root)
    for ref in refs:
        assert fresh.get_manifest_bytes(ref) == source.get_manifest_bytes(ref)
        assert fresh.verify_signature(ref, verifier).status == SignatureVerificationStatus.VALID
    # The native CAS03 consumer reads this transferred default view. Selected
    # views remain verified above through their exact public references.
    batch = fresh.verify_all_signatures(
        verifier, artifact_ids=[refs[0].artifact_id], max_workers=1, pending_window=1
    )
    assert batch.state == "complete"
    assert batch.admitted == batch.finished == batch.valid == 1
    assert batch.errors == batch.revoked == batch.unsigned == 0
    before = _snapshot(fresh)
    calls = []
    original = fresh._ownership_index.write_transaction_intent

    def observe_intent(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(fresh._ownership_index, "write_transaction_intent", observe_intent)
    reused = fresh.import_subgraph(package, signature_verifier=verifier)
    assert reused.published_refs == ()
    assert reused.imported_files == 0
    assert reused.disposition_basis == "exact_owned_view_admission"
    assert report.disposition_basis == "durable_owner_manifest_stage_intent"
    assert _ref_keys(reused.signature_verified_refs) == _ref_keys(refs)
    assert _snapshot(fresh) == before
    assert calls == []
    verifier.add_revoked_key_id(key.key_id)
    revoked_batch = fresh.verify_all_signatures(
        verifier, artifact_ids=[refs[0].artifact_id], max_workers=1, pending_window=1
    )
    assert revoked_batch.state == "complete"
    assert revoked_batch.admitted == revoked_batch.finished == revoked_batch.revoked == 1
    assert revoked_batch.errors == revoked_batch.valid == 0
    with pytest.raises(ImportSignatureVerificationError) as refusal:
        fresh.import_subgraph(package, signature_verifier=verifier)
    assert refusal.value.result.status == SignatureVerificationStatus.REVOKED
    assert _snapshot(fresh) == before
    assert calls == []


@pytest.mark.parametrize("compress", [False, True])
@pytest.mark.parametrize("failure", ["unsigned", "revoked", "untrusted", "wrong_crypto"])
def test_required_signature_refuses_before_any_owner_intent(
    compress, failure, tmp_path, monkeypatch
):
    key, signer, verifier = _keyring()
    source = _store(tmp_path / "source")
    refs = _views(source, signer, signed=failure != "unsigned")
    package = tmp_path / ("package.tar.gz" if compress else "package")
    source.export_subgraph([refs[0].artifact_id, refs[1]], package, compress=compress)
    receiver = _store(tmp_path / "receiver")
    receiver.put_bytes(
        b"unrelated valid old artifact", PutOptions(kind="control", media_type="text/plain")
    )
    before = _snapshot(receiver)
    calls = []
    original = receiver._ownership_index.write_transaction_intent

    def observe_intent(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(receiver._ownership_index, "write_transaction_intent", observe_intent)
    if failure == "revoked":
        verifier.add_revoked_key_id(key.key_id)
    elif failure == "untrusted":
        verifier = Ed25519Verifier()
    elif failure == "wrong_crypto":
        # Real Ed25519 must reject unrelated key material under the claimed key ID.
        verifier = Ed25519Verifier()
        verifier.add_trusted_key(KeyPair.generate().public_key, key_id=key.key_id)
    expected = {
        "unsigned": SignatureVerificationStatus.UNSIGNED,
        "revoked": SignatureVerificationStatus.REVOKED,
        "untrusted": SignatureVerificationStatus.UNTRUSTED,
        "wrong_crypto": SignatureVerificationStatus.INVALID,
    }[failure]
    if os.environ.get("E02_CAS02_REMOVAL") == "required-signature":
        published = receiver.import_subgraph(package, signature_verifier=verifier)
        fresh = _store(receiver.root)
        actual = fresh.verify_signature(refs[0], verifier)
        assert len(published.published_refs) == 2
        assert calls
        assert actual.status == expected
        pytest.fail(
            f"REMOVAL_ACTUAL_PUBLISHED: {len(published.published_refs)} views; "
            f"owner_intent_writes={len(calls)}; fresh_current_signature={actual.status.value}",
            pytrace=False,
        )
    with pytest.raises(ImportSignatureVerificationError) as refusal:
        receiver.import_subgraph(package, signature_verifier=verifier)
    assert refusal.value.result.status == expected
    assert calls == [], "policy refusal happened after owner publication began"
    assert _snapshot(receiver) == before
    # The same bytes remain admissible under the explicit legacy unsigned profile.
    accepted = receiver.import_subgraph(package)
    assert accepted.signature_verification_requested is False
    assert accepted.signature_verified_refs == ()
    assert not accepted.verification_failed


@pytest.mark.parametrize("compress", [False, True])
def test_mixed_exact_noop_revocation_refuses_all_new_views(compress, tmp_path, monkeypatch):
    key, signer, verifier = _keyring()
    source = _store(tmp_path / "source")
    old = _views(source, signer, payload=b"existing noop")
    new = _views(source, signer, payload=b"new pending")
    old_package = tmp_path / ("old.tar.gz" if compress else "old")
    source.export_subgraph([old[0].artifact_id, old[1]], old_package, compress=compress)
    receiver = _store(tmp_path / "receiver")
    receiver.import_subgraph(old_package, signature_verifier=verifier)
    before = _snapshot(receiver)
    combined = tmp_path / ("mixed.tar.gz" if compress else "mixed")
    source.export_subgraph(
        [old[0].artifact_id, old[1], new[0].artifact_id, new[1]], combined, compress=compress
    )
    verifier.add_revoked_key_id(key.key_id)
    calls = []
    original = receiver._ownership_index.write_transaction_intent

    def observe_intent(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(receiver._ownership_index, "write_transaction_intent", observe_intent)
    with pytest.raises(ImportSignatureVerificationError):
        receiver.import_subgraph(combined, signature_verifier=verifier)
    assert calls == []
    assert _snapshot(receiver) == before
    assert not receiver._paths(new[0].artifact_id)[0].exists()


@pytest.mark.parametrize("compress", [False, True])
def test_mixed_required_policy_verifies_noops_but_only_publishes_pending(compress, tmp_path):
    _key, signer, verifier = _keyring()
    source = _store(tmp_path / "source")
    old = _views(source, signer, payload=b"old exact views")
    new = _views(source, signer, payload=b"new pending views")
    receiver = _store(tmp_path / "receiver")
    first_package = tmp_path / ("old.tar.gz" if compress else "old")
    source.export_subgraph([old[0].artifact_id, old[1]], first_package, compress=compress)
    receiver.import_subgraph(first_package, signature_verifier=verifier)
    old_bytes = [receiver.get_manifest_bytes(ref) for ref in old]
    combined = tmp_path / ("combined.tar.gz" if compress else "combined")
    source.export_subgraph(
        [old[0].artifact_id, old[1], new[0].artifact_id, new[1]], combined, compress=compress
    )
    result = receiver.import_subgraph(combined, signature_verifier=verifier)
    assert _ref_keys(result.signature_verified_refs) == _ref_keys(old + new)
    assert _ref_keys(result.published_refs) == _ref_keys(new)
    assert _ref_keys(result.reused_refs) == _ref_keys(old)
    assert result.imported_files == 5  # One blob, two manifests and two signatures for NEW.
    assert result.disposition_basis == "durable_owner_manifest_stage_intent"
    fresh = _store(receiver.root)
    assert [fresh.get_manifest_bytes(ref) for ref in old] == old_bytes
    for ref in old + new:
        assert fresh.verify_signature(ref, verifier).status == SignatureVerificationStatus.VALID


def test_validity_marker_is_not_a_configured_crypto_verifier(tmp_path):
    source = _store(tmp_path / "source")
    _key, signer, _verifier = _keyring()
    refs = _views(source, signer)
    package = tmp_path / "package"
    source.export_subgraph([refs[0].artifact_id, refs[1]], package, compress=False)
    receiver = _store(tmp_path / "receiver")

    class Marker:
        def verify(self, *args, **kwargs):
            pytest.fail("arbitrary validity marker was invoked as a crypto authority")

    with pytest.raises(TypeError, match="configured Ed25519Verifier"):
        receiver.import_subgraph(package, signature_verifier=Marker())
    assert _snapshot(receiver)[0] == {}


@pytest.mark.parametrize("compress", [False, True])
def test_unscoped_exact_repeat_also_reports_no_transaction(compress, tmp_path, monkeypatch):
    _key, signer, verifier = _keyring()
    source = FileSystemCAS(tmp_path / "source")
    refs = _views(source, signer)
    package = tmp_path / ("package.tar.gz" if compress else "package")
    source.export_subgraph([refs[0].artifact_id, refs[1]], package, compress=compress)
    receiver = FileSystemCAS(tmp_path / "receiver")
    first = receiver.import_subgraph(package, signature_verifier=verifier)
    assert first.imported_files == 5
    calls = []
    original = receiver._ownership_index.write_transaction_intent

    def observe(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(receiver._ownership_index, "write_transaction_intent", observe)
    before = _snapshot(receiver)
    repeated = receiver.import_subgraph(package, signature_verifier=verifier)
    assert repeated.imported_files == 0
    assert repeated.published_refs == ()
    assert repeated.disposition_basis == "exact_owned_view_admission"
    assert _ref_keys(repeated.signature_verified_refs) == _ref_keys(refs)
    assert _snapshot(receiver) == before
    assert calls == []


@pytest.mark.parametrize("compress", [False, True])
def test_default_and_explicit_selected_alias_preserve_distinct_valid_signatures(compress, tmp_path):
    _key, signer, verifier = _keyring()
    source = _store(tmp_path / "source")
    refs = _views(source, signer)
    alias_key = KeyPair.generate()
    alias_signer = Ed25519Signer.from_pem(alias_key.private_pem())
    verifier.add_trusted_key(alias_key.public_key, key_id=alias_key.key_id, identity="alias-owner")
    source.sign_artifact(refs[0], alias_signer, signer_identity="alias-owner")
    assert source.get_signature_bytes(refs[0].artifact_id) != source.get_signature_bytes(refs[0])
    package = tmp_path / ("all-selectors.tar.gz" if compress else "all-selectors")
    requests = [refs[0].artifact_id, refs[0], refs[1]]
    for request in requests:
        assert (
            source.verify_signature(request, verifier).status == SignatureVerificationStatus.VALID
        )
    source.export_subgraph(requests, package, compress=compress)
    receiver = _store(tmp_path / "receiver")
    result = receiver.import_subgraph(package, signature_verifier=verifier)
    assert not result.verification_failed
    fresh = _store(receiver.root)
    for request in requests:
        assert fresh.get_signature_bytes(request) == source.get_signature_bytes(request)
        assert fresh.verify_signature(request, verifier).status == SignatureVerificationStatus.VALID


@pytest.mark.parametrize("compress", [False, True])
def test_explicit_unsigned_alias_is_not_promoted_by_default_signature(compress, tmp_path):
    _key, signer, verifier = _keyring()
    source = _store(tmp_path / "source")
    refs = _views(source, signer)
    requests = [refs[0].artifact_id, refs[0], refs[1]]
    assert source.verify_signature(refs[0], verifier).status == SignatureVerificationStatus.UNSIGNED
    package = tmp_path / ("unsigned-alias.tar.gz" if compress else "unsigned-alias")
    source.export_subgraph(requests, package, compress=compress)
    receiver = _store(tmp_path / "receiver")
    report = receiver.import_subgraph(package)
    assert not report.verification_failed
    fresh = _store(receiver.root)
    assert fresh.verify_signature(refs[0], verifier).status == SignatureVerificationStatus.UNSIGNED
    for request in (refs[0].artifact_id, refs[1]):
        assert fresh.get_signature_bytes(request) == source.get_signature_bytes(request)
        assert fresh.verify_signature(request, verifier).status == SignatureVerificationStatus.VALID
    required = _store(tmp_path / "required")
    with pytest.raises(ImportSignatureVerificationError) as refusal:
        required.import_subgraph(package, signature_verifier=verifier)
    assert refusal.value.result.status == SignatureVerificationStatus.UNSIGNED
    assert _snapshot(required)[0] == {}


@pytest.mark.parametrize("compress", [False, True])
def test_explicit_alias_wins_when_incoming_default_cannot_replace_existing_default(
    compress, tmp_path
):
    _key, signer, verifier = _keyring()
    payload = b"one blob, differing default manifest profiles"
    source = FileSystemCAS(tmp_path / "source")
    incoming = source.put_bytes(
        payload,
        PutOptions(kind="incoming.b", media_type="text/plain"),
        return_selected_profile=True,
    )
    alias_key = KeyPair.generate()
    verifier.add_trusted_key(alias_key.public_key, key_id=alias_key.key_id, identity="alias-owner")
    source.sign_artifact(incoming.artifact_id, signer, signer_identity="transfer-owner")
    source.sign_artifact(
        incoming, Ed25519Signer.from_pem(alias_key.private_pem()), signer_identity="alias-owner"
    )
    requests = [incoming.artifact_id, incoming]
    for request in requests:
        assert (
            source.verify_signature(request, verifier).status == SignatureVerificationStatus.VALID
        )
    package = tmp_path / ("incoming.tar.gz" if compress else "incoming")
    source.export_subgraph(requests, package, compress=compress)
    receiver = FileSystemCAS(tmp_path / "receiver")
    existing = receiver.put_bytes(
        payload,
        PutOptions(kind="existing.a", media_type="text/plain"),
        return_selected_profile=True,
    )
    receiver.sign_artifact(existing.artifact_id, signer, signer_identity="transfer-owner")
    old_manifest = receiver.get_manifest_bytes(existing.artifact_id)
    old_signature = receiver.get_signature_bytes(existing.artifact_id)
    result = receiver.import_subgraph(package, signature_verifier=verifier)
    assert not result.verification_failed
    fresh = FileSystemCAS(receiver.root)
    assert fresh.get_manifest_bytes(existing.artifact_id) == old_manifest
    assert fresh.get_signature_bytes(existing.artifact_id) == old_signature
    assert fresh.get_manifest_bytes(incoming) == source.get_manifest_bytes(incoming)
    assert fresh.get_signature_bytes(incoming) == source.get_signature_bytes(incoming)
    assert fresh.verify_signature(incoming, verifier).status == SignatureVerificationStatus.VALID
