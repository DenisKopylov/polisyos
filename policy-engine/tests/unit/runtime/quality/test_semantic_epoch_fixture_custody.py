from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from tests._helpers import acquisition_chain, semantic_epoch_native


def test_native_epoch_fixture_custody_reuses_only_the_exact_signed_context(
    tmp_path: Path,
) -> None:
    custodian_type = getattr(semantic_epoch_native, "NativeEpochFixtureCustodian", None)
    assert custodian_type is not None, (
        "native epoch fixture custodian must preserve exact envelopes"
    )

    scenario = semantic_epoch_native._real_epoch_scenario(tmp_path / "scenario")
    custodian = custodian_type.create(scenario.store, tmp_path / "custodian")
    first = semantic_epoch_native.sign_native_epoch_scenario(
        scenario,
        tmp_path / "policy-first",
        custodian=custodian,
    )
    original_signature_bytes = scenario.store.get_signature_bytes(first.signed.artifact_ref)
    original_evidence = semantic_epoch_native.FileSystemSignedArtifactEvidenceRepository(
        scenario.store
    ).read_exact(evidence_record_ref=first.signed.evidence.evidence_record_ref)

    repeated = semantic_epoch_native.sign_native_epoch_scenario(
        scenario,
        tmp_path / "policy-repeat",
        custodian=custodian,
    )
    repeated_evidence = semantic_epoch_native.FileSystemSignedArtifactEvidenceRepository(
        scenario.store
    ).read_exact(evidence_record_ref=repeated.signed.evidence.evidence_record_ref)

    assert repeated.signed.artifact_ref == first.signed.artifact_ref
    assert repeated.signed.evidence.evidence_record_ref == first.signed.evidence.evidence_record_ref
    assert repeated_evidence.persisted.record_bytes == original_evidence.persisted.record_bytes
    assert repeated_evidence.detached_signature_bytes == original_signature_bytes
    first_signature = artifacts.DetachedSignature.model_validate_json(original_signature_bytes)
    repeated_signature = artifacts.DetachedSignature.model_validate_json(
        repeated_evidence.detached_signature_bytes
    )
    assert repeated_signature.key_id == first_signature.key_id == custodian.signer.key_id
    assert repeated_signature.signed_at == first_signature.signed_at

    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    trusted_key_id = verifier.load_trusted_key_file(
        custodian.public_key_path,
        identity=custodian.issuer_identity,
    )
    assert trusted_key_id == custodian.signer.key_id
    assert (
        scenario.store.verify_signature(
            first.signed.artifact_ref,
            verifier,
            strict_identity=True,
        ).status
        is artifacts.SignatureVerificationStatus.VALID
    )
    trusted_issuer = repeated.config.trusted_issuers[0]
    assert trusted_issuer.identity == custodian.issuer_identity
    assert trusted_issuer.roles == custodian.issuer_roles
    assert trusted_issuer.public_key_path == custodian.public_key_path

    changed_scenario = SimpleNamespace(**vars(scenario))
    changed_scenario.query = scenario.query.model_copy(
        update={
            "requested_query_context_ref": (
                f"sha256:{hashlib.sha256(b'changed native query context').hexdigest()}"
            )
        }
    )
    changed_query = semantic_epoch_native.sign_native_epoch_scenario(
        changed_scenario,
        tmp_path / "policy-changed-query",
        custodian=custodian,
    )
    assert changed_query.signed.artifact_ref.artifact_id != first.signed.artifact_ref.artifact_id
    assert (
        scenario.store.verify_signature(
            changed_query.signed.artifact_ref,
            verifier,
            strict_identity=True,
        ).status
        is artifacts.SignatureVerificationStatus.VALID
    )

    changed_provenance_ref = scenario.store.put_bytes(
        b"different fixture provenance context",
        ArtifactWriteOptions(
            kind="fixture.epoch.other_provenance",
            media_type="application/octet-stream",
        ),
    )
    with pytest.raises(ValueError, match="context"):
        custodian.persist_or_reuse(
            blob_bytes=semantic_epoch_native.security.canonical_statement_bytes(first.admission),
            signing_profile_ref=custodian.owner_ref,
            signer_provenance_ref=changed_provenance_ref,
        )
    assert scenario.store.get_signature_bytes(first.signed.artifact_ref) == original_signature_bytes

    first_public_key_bytes = custodian.public_key_path.read_bytes()
    wrong_key_custodian = custodian_type.create(scenario.store, tmp_path / "custodian")
    assert wrong_key_custodian.owner_ref == custodian.owner_ref
    assert wrong_key_custodian.public_key_path != custodian.public_key_path
    assert custodian.public_key_path.read_bytes() == first_public_key_bytes

    reused_after_collision = semantic_epoch_native.sign_native_epoch_scenario(
        scenario,
        tmp_path / "policy-after-collision",
        custodian=custodian,
    )
    assert reused_after_collision.signed.artifact_ref == first.signed.artifact_ref
    assert (
        reused_after_collision.signed.evidence.evidence_record_ref
        == first.signed.evidence.evidence_record_ref
    )
    assert scenario.store.get_signature_bytes(first.signed.artifact_ref) == original_signature_bytes
    assert (
        scenario.store.verify_signature(
            first.signed.artifact_ref,
            verifier,
            strict_identity=True,
        ).status
        is artifacts.SignatureVerificationStatus.VALID
    )

    with pytest.raises(ValueError, match="existing signature"):
        wrong_key_custodian.persist_or_reuse(
            blob_bytes=semantic_epoch_native.security.canonical_statement_bytes(first.admission),
            signing_profile_ref=wrong_key_custodian.owner_ref,
            signer_provenance_ref=wrong_key_custodian.owner_ref,
        )
    wrong_verifier = artifacts.Ed25519Verifier(strict_identity=True)
    wrong_verifier.load_trusted_key_file(
        wrong_key_custodian.public_key_path,
        identity=wrong_key_custodian.issuer_identity,
    )
    assert (
        scenario.store.verify_signature(
            first.signed.artifact_ref,
            wrong_verifier,
            strict_identity=True,
        ).status
        is artifacts.SignatureVerificationStatus.UNTRUSTED
    )
    assert scenario.store.get_signature_bytes(first.signed.artifact_ref) == original_signature_bytes


def test_retained_native_epoch_custodian_requires_the_same_cas_context(
    tmp_path: Path,
) -> None:
    scenario = semantic_epoch_native._real_epoch_scenario(tmp_path / "scenario")
    custodian = semantic_epoch_native.NativeEpochFixtureCustodian.create(
        scenario.store,
        tmp_path / "custodian",
    )
    appointment = SimpleNamespace(custodian=custodian)

    assert (
        acquisition_chain._retained_native_epoch_custodian(
            [appointment],
            store=scenario.store,
        )
        is custodian
    )

    reopened_same_root = FileSystemCAS(scenario.store.root)
    assert reopened_same_root.root == scenario.store.root
    assert (
        acquisition_chain._retained_native_epoch_custodian(
            [appointment],
            store=reopened_same_root,
        )
        is None
    )
    assert (
        acquisition_chain._retained_native_epoch_custodian(
            [SimpleNamespace()],
            store=scenario.store,
        )
        is None
    )
