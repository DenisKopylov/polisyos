"""Deployment-bound epoch evidence resolves independently of callers and signers."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import shutil
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from polisyos.core import artifacts, security
from polisyos.core import contracts as core_contracts
from polisyos.core.artifacts.signed_evidence import FileSystemSignedArtifactEvidenceRepository

contracts = core_contracts.chronology


def _module():
    name = "polisyos.runtime.quality.epoch_deployment"
    assert importlib.util.find_spec(name) is not None, "production epoch deployment loader missing"
    return importlib.import_module(name)


def _ref(label: str) -> artifacts.ArtifactRef:
    return artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate(security.raw_content_hash(label.encode())),
        kind="test.epoch",
        media_type="application/octet-stream",
    )


def _write(store, payload: bytes, kind: str):
    return store.put_bytes(
        payload, artifacts.ArtifactWriteOptions(kind=kind, media_type="application/octet-stream")
    )


def _profile_configuration(tmp_path: Path):
    module = _module()
    store = artifacts.FileSystemCAS(tmp_path / "evidence")
    signer_key = Ed25519PrivateKey.generate()
    signer = artifacts.Ed25519Signer(signer_key)
    public_path = tmp_path / "admission.pub"
    public_path.write_bytes(
        signer_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    profile = module.EpochTransitionSigningProfile(
        signer_key_ids=(signer.key_id,),
        authority_purpose="publication",
    )
    profile_ref = _write(
        store, security.canonical_statement_bytes(profile), "epoch.transition_signing_profile"
    )
    statement = module.EpochSigningProfileAdmissionStatement(
        signing_profile_ref=profile_ref,
        signing_profile_content_hash=str(profile_ref.artifact_id),
        authority_purpose="publication",
        requested_query_context_ref=str(_ref("query").artifact_id),
    )
    repository = FileSystemSignedArtifactEvidenceRepository(store)
    evidence = repository.persist_signed(
        blob_bytes=security.canonical_statement_bytes(statement),
        write_options=artifacts.ArtifactWriteOptions(
            kind="epoch.signing_profile_admission", media_type="application/octet-stream"
        ),
        signer=signer,
        signing_profile_ref=_ref("admission-signing-profile"),
        signer_provenance_ref=_ref("admission-issuer"),
    )
    config = module.EpochDeploymentConfig(
        evidence_cas_root=store.root,
        trusted_issuers=(
            module.EpochTrustedIssuerConfig(
                identity="test-admission-owner",
                public_key_path=public_path,
                roles=("signing_profile_admission", "transition_signature"),
            ),
        ),
        signing_profile_admission_refs=(evidence.evidence_record_ref,),
    )
    return config, store, profile_ref, statement, repository, signer


def test_empty_deployment_retains_real_qualification_and_custody_negatives() -> None:
    module = _module()
    owner = module.build_epoch_deployment(None)
    from polisyos.runtime.quality import chronology_custody, chronology_qualification
    from tests.unit.runtime.quality.test_chronology_qualification import _ExplodingAdapter, _query
    from tests.unit.runtime.quality.test_epoch_custody_audit import _request

    consumer = chronology_qualification.QualificationConsumer.from_deployment(owner)
    adapter = _ExplodingAdapter()
    result = consumer.qualify(adapter=adapter, request=_query())
    assert result.failure.code == "policy_admission_missing"
    assert adapter.calls == 0
    with owner.composition_scope():
        provider = chronology_custody.build_production_epoch_anchor_custody_provider()
    custody = provider.evaluate_acceptance_and_custody(request=_request())
    assert custody.status == "limited"
    assert custody.acceptance.non_receipts[0].code == "anchor_acceptance_owner_not_established"
    assert custody.retention.non_receipts[0].code == "anchor_holder_not_established"


def test_profile_admission_resolves_exact_signed_owner_bytes(tmp_path: Path) -> None:
    config, store, profile_ref, statement, repository, signer = _profile_configuration(tmp_path)
    owner = _module().build_epoch_deployment(config)
    admitted = owner.resolve_admitted_signing_profile(
        signing_profile_ref=profile_ref,
        authority_purpose=statement.authority_purpose,
        requested_query_context_ref=statement.requested_query_context_ref,
    )
    assert admitted.signing_profile_content_hash == str(profile_ref.artifact_id)
    assert store.get_bytes(
        admitted.admission_ref.artifact_id
    ) == security.canonical_statement_bytes(statement)
    transition = repository.persist_signed(
        blob_bytes=b"transition candidate",
        write_options=artifacts.ArtifactWriteOptions(
            kind="epoch.validity_transition", media_type="application/octet-stream"
        ),
        signer=signer,
        signing_profile_ref=profile_ref,
        signer_provenance_ref=_ref("transition-issuer"),
    )
    assert owner.verify_transition_signature(
        evidence=repository.read_exact(evidence_record_ref=transition.evidence_record_ref),
        signing_profile_ref=profile_ref,
        authority_purpose=statement.authority_purpose,
        requested_query_context_ref=statement.requested_query_context_ref,
    )


@pytest.mark.parametrize(
    "mutation",
    ["foreign_purpose", "foreign_query", "empty_trust", "wrong_role", "revoked", "deleted_profile"],
)
def test_profile_configuration_cannot_self_admit_or_cross_scope(
    tmp_path: Path, mutation: str
) -> None:
    config, store, profile_ref, statement, _, signer = _profile_configuration(tmp_path)
    purpose, query = statement.authority_purpose, statement.requested_query_context_ref
    if mutation == "empty_trust":
        config = config.model_copy(update={"trusted_issuers": ()})
    elif mutation == "wrong_role":
        issuer = config.trusted_issuers[0].model_copy(update={"roles": ("transition_signature",)})
        config = config.model_copy(update={"trusted_issuers": (issuer,)})
    elif mutation == "revoked":
        config = config.model_copy(update={"revoked_key_ids": (signer.key_id,)})
    elif mutation == "foreign_purpose":
        purpose = "another-purpose"
    elif mutation == "foreign_query":
        query = str(_ref("another-query").artifact_id)
    else:
        blob, _ = store.get_paths(profile_ref.artifact_id)
        blob.rename(blob.with_suffix(".unavailable"))
    owner = _module().build_epoch_deployment(config)
    with pytest.raises(ValueError):
        owner.resolve_admitted_signing_profile(
            signing_profile_ref=profile_ref,
            authority_purpose=purpose,
            requested_query_context_ref=query,
        )


def test_two_deployments_do_not_share_owner_configuration(tmp_path: Path) -> None:
    config, _, profile_ref, statement, _, _ = _profile_configuration(tmp_path)
    first = _module().build_epoch_deployment(config)
    second = _module().build_epoch_deployment(None)
    for owner, expected in ((first, True), (second, False), (first, True)):
        if expected:
            assert owner.resolve_admitted_signing_profile(
                signing_profile_ref=profile_ref,
                authority_purpose=statement.authority_purpose,
                requested_query_context_ref=statement.requested_query_context_ref,
            )
        else:
            with pytest.raises(ValueError):
                owner.resolve_admitted_signing_profile(
                    signing_profile_ref=profile_ref,
                    authority_purpose=statement.authority_purpose,
                    requested_query_context_ref=statement.requested_query_context_ref,
                )


def _appointment_config(tmp_path: Path, fixture):
    module = _module()
    key = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"gy-n12-c3-appointed-fixture-key-v1").digest()
    )
    public_path = tmp_path / "appointment.pub"
    public_path.write_bytes(
        key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )

    def appointment(value):
        return module.EpochAppointmentEvidenceConfig(
            appointment_evidence_ref=value.signed_appointment_evidence.persisted.evidence_record_ref,
            verification_evidence_ref=value.signed_verification_evidence.persisted.evidence_record_ref,
        )

    return module.EpochDeploymentConfig(
        evidence_cas_root=fixture.store.root,
        trusted_issuers=(
            module.EpochTrustedIssuerConfig(
                identity="fixture-appointment-issuer",
                public_key_path=public_path,
                roles=("acceptance_appointment", "holder_appointment"),
            ),
        ),
        acceptance_appointments=(appointment(fixture.acceptance_appointment),),
        holder_appointments=(appointment(fixture.holder_appointment),),
    )


def test_configured_appointments_reach_independent_verifiers(tmp_path: Path) -> None:
    from polisyos.runtime.quality.epoch_evidence_exchange import EpochEvidenceExchange
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path / "holder")
    owner = _module().build_epoch_deployment(_appointment_config(tmp_path, fixture))
    exchange = EpochEvidenceExchange(owner)
    resolved = exchange.resolve_epoch_appointments(
        family="epoch", proof_domain="epoch", authority_purpose="publication"
    )
    assert resolved.acceptance.status == resolved.holder.status == "established"
    assert resolved.acceptance.appointment == fixture.acceptance_appointment
    assert resolved.holder.appointment == fixture.holder_appointment
    assert isinstance(
        exchange.resolve_acceptance_verifier(appointment=resolved.acceptance.appointment),
        security.ExactAnchorAcceptanceReceiptVerifier,
    )
    assert isinstance(
        exchange.resolve_holder_verifier(appointment=resolved.holder.appointment),
        security.ExactAnchorHolderReceiptVerifier,
    )
    foreign = exchange.resolve_epoch_appointments(
        family="epoch", proof_domain="epoch", authority_purpose="another-purpose"
    )
    assert foreign.acceptance.status == foreign.holder.status == "not_established"


@pytest.mark.parametrize(
    "mutation", ["missing_verification", "ambiguous", "wrong_role", "revoked", "wrong_binding"]
)
def test_holder_appointment_configuration_fails_closed_independently(
    tmp_path: Path, mutation: str
) -> None:
    from polisyos.runtime.quality.epoch_evidence_exchange import EpochEvidenceExchange
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path / "holder")
    config = _appointment_config(tmp_path, fixture)
    if mutation == "missing_verification":
        row = config.holder_appointments[0].model_copy(
            update={"verification_evidence_ref": _ref("absent")}
        )
        config = config.model_copy(update={"holder_appointments": (row,)})
    elif mutation == "ambiguous":
        config = config.model_copy(update={"holder_appointments": config.holder_appointments * 2})
    elif mutation == "wrong_role":
        row = config.trusted_issuers[0].model_copy(update={"roles": ("acceptance_appointment",)})
        config = config.model_copy(update={"trusted_issuers": (row,)})
    elif mutation == "revoked":
        config = config.model_copy(update={"revoked_key_ids": (fixture.signer.key_id,)})
    else:
        verification = security.parse_canonical_statement(
            fixture.holder_appointment.verification_statement_bytes,
            contracts.HolderAppointmentVerificationStatement,
        ).model_copy(
            update={"trust_config_content_hash": str(_ref("wrong-trust-hash").artifact_id)}
        )
        signed = fixture._issue(
            security.canonical_statement_bytes(verification), kind="fixture.wrong_verification"
        )
        row = config.holder_appointments[0].model_copy(
            update={"verification_evidence_ref": signed.persisted.evidence_record_ref}
        )
        config = config.model_copy(update={"holder_appointments": (row,)})
    exchange = EpochEvidenceExchange(_module().build_epoch_deployment(config))
    resolved = exchange.resolve_epoch_appointments(
        family="epoch", proof_domain="epoch", authority_purpose="publication"
    )
    assert resolved.holder.status == "not_established"
    assert resolved.acceptance.status == (
        "not_established" if mutation == "revoked" else "established"
    )


def test_configured_holder_exchange_verifies_real_readback_and_rejects_package_mutation(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality.chronology_custody import (
        build_production_epoch_anchor_custody_provider,
    )
    from polisyos.runtime.quality.epoch_evidence_exchange import EpochReadbackChallengeRepository
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path / "holder")
    _, readback, challenge, expected = fixture.build_retention()
    readback_ref = _write(
        fixture.store, security.canonical_statement_bytes(readback), "exchange.readback"
    )
    config = _appointment_config(tmp_path, fixture).model_copy(
        update={"readback_receipt_refs": (readback_ref,)}
    )
    holder_root = tmp_path / "independent-holder-evidence"
    shutil.copytree(fixture.store.root, holder_root)
    fixture.store.root.rename(tmp_path / "writer-unavailable")
    holder_store = artifacts.FileSystemCAS(holder_root)
    config = config.model_copy(update={"evidence_cas_root": holder_root})
    owner = _module().build_epoch_deployment(config)
    persisted = EpochReadbackChallengeRepository(owner).persist(
        security.parse_canonical_statement(
            challenge.statement_bytes, contracts.AnchorReadbackChallengeStatement
        )
    )
    assert persisted == challenge
    with owner.composition_scope():
        provider = build_production_epoch_anchor_custody_provider()
    result = provider.evaluate_retained_challenge(
        challenge_record_ref=challenge.challenge_record_ref
    )
    assert result.retention.status == "verified"
    assert result.retention.value == expected
    assert result.acceptance.status == "not_established"
    changed = readback.model_copy(update={"package_bytes": b"wrong-package"})
    changed_ref = _write(
        holder_store, security.canonical_statement_bytes(changed), "exchange.readback"
    )
    changed_owner = _module().build_epoch_deployment(
        config.model_copy(update={"readback_receipt_refs": (changed_ref,)})
    )
    with changed_owner.composition_scope():
        changed_provider = build_production_epoch_anchor_custody_provider()
    rejected = changed_provider.evaluate_retained_challenge(
        challenge_record_ref=challenge.challenge_record_ref
    )
    assert rejected.retention.status == "rejected"
    assert rejected.status == "rejected"


def _policy_configuration(tmp_path: Path):
    from tests._helpers.chronology_qualification import make_qualification_case

    module = _module()
    case = make_qualification_case(tmp_path / "policy", shape="epoch", member_count=2)
    admission = security.parse_canonical_statement(
        case.store.get_bytes(case.admission_ref.artifact_id),
        contracts.PredicatePolicyAdmissionStatement,
    )
    verifier = case.owner_verifier
    receipt = verifier.verify_owner_relation(
        query=case.query,
        admission=admission,
        policy=case.policy,
        policy_owner_provenance_bytes=verifier.policy_owner_provenance_bytes,
        owner_relation_bytes=verifier.owner_relation_bytes,
        candidate=case.candidate,
    )
    assert isinstance(receipt, contracts.VerifiedPredicatePolicyOwnerRelation)
    signer_key = Ed25519PrivateKey.generate()
    signer = artifacts.Ed25519Signer(signer_key)
    key_path = tmp_path / "policy.pub"
    key_path.write_bytes(
        signer_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    repository = FileSystemSignedArtifactEvidenceRepository(case.store)

    def signed(value, kind):
        return repository.persist_signed(
            blob_bytes=security.canonical_statement_bytes(value),
            write_options=artifacts.ArtifactWriteOptions(
                kind=kind, media_type="application/octet-stream"
            ),
            signer=signer,
            signing_profile_ref=_ref("policy-profile"),
            signer_provenance_ref=receipt.owner_verifier_provenance_ref,
        ).evidence_record_ref

    config = module.EpochDeploymentConfig(
        evidence_cas_root=case.store.root,
        trusted_issuers=(
            module.EpochTrustedIssuerConfig(
                identity="policy-verifier",
                public_key_path=key_path,
                roles=("predicate_policy_admission", "predicate_owner_verification"),
            ),
        ),
        predicate_policy_admission_refs=(signed(admission, "policy.admission"),),
        predicate_owner_verification_refs=(signed(receipt, "policy.verification"),),
        native_candidate_refs=(
            _write(
                case.store, security.canonical_statement_bytes(case.candidate), "native.candidate"
            ),
        ),
    )
    return config, case


def test_configured_policy_exchange_reaches_native_verifier_limitation(tmp_path: Path) -> None:
    from polisyos.runtime.quality.chronology_qualification import QualificationConsumer
    from polisyos.runtime.quality.epoch_evidence_exchange import EpochEvidenceExchange

    module = _module()
    config, case = _policy_configuration(tmp_path)
    owner = module.build_epoch_deployment(config)
    stored_before = {str(value) for value in case.store.iter_artifact_ids()}
    result = QualificationConsumer.from_deployment(owner).qualify(
        adapter=EpochEvidenceExchange(owner), request=case.query
    )
    assert not isinstance(result, contracts.NativeChronologyQualified)
    assert result.failure.code == "policy_owner_relation_not_established"
    from polisyos.runtime.quality.semantic_epoch import SemanticEpochService

    service = SemanticEpochService.for_deployment_policy_query(
        artifact_store=case.store,
        deployment=owner,
    )
    assert (
        service.qualify_chronology_query(query=case.query).failure.code
        == "policy_owner_relation_not_established"
    )
    assert {str(value) for value in case.store.iter_artifact_ids()} == stored_before
    empty = module.build_epoch_deployment(
        config.model_copy(update={"predicate_owner_verification_refs": ()})
    )
    refused = QualificationConsumer.from_deployment(empty).qualify(
        adapter=EpochEvidenceExchange(empty), request=case.query
    )
    assert refused.failure.code == "policy_owner_relation_not_established"


def test_privileged_native_verifier_is_operational_and_deployment_local(tmp_path: Path) -> None:
    from polisyos.runtime.quality.chronology_qualification import QualificationConsumer
    from polisyos.runtime.quality.epoch_evidence_exchange import EpochEvidenceExchange
    from polisyos.runtime.quality.semantic_epoch import SemanticEpochService

    module = _module()
    config, case = _policy_configuration(tmp_path)
    # This implementation derives native member/evidence truth from its own
    # exact store and schema; the signed DTO transport cannot replace it.
    first = module.build_epoch_deployment(config, native_policy_verifier=case.owner_verifier)
    second = module.build_epoch_deployment(config)
    for owner, admitted in ((first, True), (second, False), (first, True)):
        result = QualificationConsumer.from_deployment(owner).qualify(
            adapter=EpochEvidenceExchange(owner), request=case.query
        )
        if admitted:
            assert isinstance(result, contracts.NativeChronologyQualified)
        else:
            assert result.failure.code == "policy_owner_relation_not_established"
    service = SemanticEpochService.for_deployment_policy_query(
        artifact_store=case.store, deployment=first
    )
    assert isinstance(
        service.qualify_chronology_query(query=case.query), contracts.NativeChronologyQualified
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(type(case.owner_verifier), "verify_owner_relation", lambda **kwargs: None)
        with pytest.raises(ValueError, match="operation changed after deployment"):
            first.attestation_state()


@pytest.mark.parametrize(
    ("property_name", "operation_name"),
    [
        ("epoch_certificate_issuance_input_resolver", "resolve_verified_inputs"),
        ("epoch_certificate_issuance_input_resolver", "resolve_admitted_execution_closure"),
        ("epoch_perturbation_adjudication_provider", "resolve_complete_owner_adjudications"),
        ("epoch_owner_disposition_evidence_reader", "resolve_admitted_owner_disposition"),
    ],
)
def test_privileged_source_ports_are_local_and_reject_operation_replacement(
    property_name: str,
    operation_name: str,
) -> None:
    from types import SimpleNamespace

    def resolve(**kwargs: object) -> object:
        del kwargs
        raise ValueError("source evidence is not admitted")

    operations = {operation_name: resolve}
    if property_name == "epoch_certificate_issuance_input_resolver":
        operations.update(
            resolve_verified_inputs=resolve,
            resolve_admitted_execution_closure=resolve,
        )
    component = SimpleNamespace(**operations)
    module = _module()
    first = module.build_epoch_deployment(None, **{property_name: component})
    empty = module.build_epoch_deployment(None)
    assert getattr(empty, property_name) is None
    for _ in range(2):
        owner_component = getattr(first, property_name)
        assert owner_component is component
        with pytest.raises(ValueError, match="source evidence is not admitted"):
            getattr(owner_component, operation_name)()
    setattr(component, operation_name, lambda **kwargs: None)
    with pytest.raises(ValueError, match="operation changed after deployment"):
        getattr(first, property_name)


def test_configured_exchange_consumes_acceptance_retention_and_readback(tmp_path: Path) -> None:
    from polisyos.runtime.quality.chronology_custody import (
        build_production_epoch_anchor_custody_provider,
    )
    from tests._helpers.chronology_qualification import AppointedAnchorFixture

    fixture = AppointedAnchorFixture(tmp_path / "writer")
    lineage_root = tmp_path / "acceptance-owner-lineage"
    fixture.lineage = security.FileAnchorAcceptanceLineageRepository(root=lineage_root)
    retention, readback, _, _ = fixture.build_retention()
    graph = security.parse_canonical_statement(
        fixture.retained_package.package_bytes, contracts.AnchorRetentionObjectGraph
    )
    signed = graph.acceptance_evidence.acceptance_receipt_signed_evidence
    record = security.parse_canonical_statement(
        signed.persisted.record_bytes, contracts.SignedArtifactEvidenceRecord
    )
    receipt = contracts.AnchorAcceptanceReceipt(
        receipt_record_ref=record.artifact_ref,
        receipt_record_content_hash=security.semantic_content_hash(
            "anchor-acceptance-receipt.v1", signed.blob_bytes
        ),
        statement_bytes=signed.blob_bytes,
        receipt_record_bytes=signed.blob_bytes,
        signed_receipt_evidence=signed,
    )
    statement = security.parse_canonical_statement(
        graph.acceptance_evidence.acceptance_statement_evidence.blob_bytes,
        contracts.AnchorAcceptanceStatement,
    )
    request = contracts.AnchorAcceptanceRequest(
        bundle_ref=statement.bundle_ref,
        expected_domain=contracts.ChronologyProofDomain.model_validate(
            {
                name: getattr(statement.parsed_header, name)
                for name in contracts.ChronologyProofDomain.model_fields
            }
        ),
        native_reconciliation_ref=statement.native_reconciliation_ref,
        authority_purpose=statement.authority_purpose,
        requested_query_context_ref=statement.requested_query_context_ref,
        asserted_prior_acceptance_record_refs=statement.prior_acceptance_record_refs,
    )
    config = _appointment_config(tmp_path, fixture).model_copy(
        update={
            "acceptance_lineage_root": lineage_root,
            "acceptance_receipt_refs": (
                _write(
                    fixture.store,
                    security.canonical_statement_bytes(receipt),
                    "exchange.acceptance",
                ),
            ),
            "retention_receipt_refs": (
                _write(
                    fixture.store,
                    security.canonical_statement_bytes(retention),
                    "exchange.retention",
                ),
            ),
            "readback_receipt_refs": (
                _write(
                    fixture.store, security.canonical_statement_bytes(readback), "exchange.readback"
                ),
            ),
        }
    )
    owner = _module().build_epoch_deployment(config)
    with owner.composition_scope():
        provider = build_production_epoch_anchor_custody_provider()
    verified = provider.evaluate_acceptance_and_custody(request=request)
    assert verified.status == "verified"
    assert verified.acceptance.status == verified.retention.status == "verified"
    wrong = provider.evaluate_acceptance_and_custody(
        request=request.model_copy(update={"bundle_ref": _ref("other-bundle-same-query")})
    )
    assert wrong.status == "limited"
    assert wrong.acceptance.status == "not_established"


def test_configured_transition_signature_exchange_requires_exact_bytes(tmp_path: Path) -> None:
    config, _, profile_ref, statement, repository, signer = _profile_configuration(tmp_path)
    persisted = repository.persist_signed(
        blob_bytes=b"exact-transition",
        write_options=artifacts.ArtifactWriteOptions(
            kind="epoch.validity_transition", media_type="application/octet-stream"
        ),
        signer=signer,
        signing_profile_ref=profile_ref,
        signer_provenance_ref=_ref("transition-issuer"),
    )
    owner = _module().build_epoch_deployment(
        config.model_copy(
            update={"transition_signed_evidence_refs": (persisted.evidence_record_ref,)}
        )
    )
    assert owner.has_transition_evidence_configuration
    evidence = owner.resolve_exact_signed_transition(
        transition_bytes=b"exact-transition",
        authority_purpose=statement.authority_purpose,
        requested_query_context_ref=statement.requested_query_context_ref,
    )
    assert evidence.persisted == persisted
    with pytest.raises(ValueError):
        owner.resolve_exact_signed_transition(
            transition_bytes=b"candidate-different",
            authority_purpose=statement.authority_purpose,
            requested_query_context_ref=statement.requested_query_context_ref,
        )
