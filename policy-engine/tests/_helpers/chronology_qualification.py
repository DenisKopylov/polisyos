"""Test-only native authority shapes for chronology protocol conformance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    Ed25519Signer,
    Ed25519Verifier,
    FileSystemCAS,
)
from polisyos.core.artifacts.signed_evidence import (
    FileSystemSignedArtifactEvidenceRepository,
)
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import chronology as contract
from polisyos.core.security.anchor_lineage import (
    InMemoryAnchorAcceptanceLineageRepository,
)
from polisyos.core.security.chronology_anchor import (
    ExactAnchorAcceptanceReceiptVerifier,
    ExactAnchorHolderReceiptVerifier,
    InMemoryAnchorReadbackChallengeRepository,
    build_retention_package,
    canonical_exact_mapping_bytes,
    canonical_statement_bytes,
    raw_content_hash,
    semantic_content_hash,
)
from polisyos.core.security.full_prefix import FullPrefixVerifier, build_full_prefix_bundle
from polisyos.runtime.quality import chronology_proof, chronology_qualification


def _digest(label: str) -> contract.Digest:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def build_anchor_acceptance_request(
    *,
    bundle_ref: ArtifactRef,
    native_reconciliation_ref: ArtifactRef,
    requested_query_context_ref: contract.Digest,
    authority_purpose: str = "publication",
    asserted_prior_acceptance_record_refs: tuple[ArtifactRef, ...] = (),
) -> contract.AnchorAcceptanceRequest:
    """Build a test-only opaque request without supplying owner conclusions."""

    return contract.AnchorAcceptanceRequest(
        bundle_ref=bundle_ref,
        expected_domain=contract.ChronologyProofDomain(
            format=contract.FULL_PREFIX_FORMAT,
            profile=contract.FULL_PREFIX_PROFILE,
            proof_domain="epoch",
            family="epoch",
            scope_ref=_digest("fixture-epoch-scope"),
            authority_purpose=authority_purpose,
        ),
        native_reconciliation_ref=native_reconciliation_ref,
        authority_purpose=authority_purpose,
        requested_query_context_ref=requested_query_context_ref,
        asserted_prior_acceptance_record_refs=asserted_prior_acceptance_record_refs,
    )


def _put_raw(store: FileSystemCAS, payload: bytes, *, kind: str) -> ArtifactRef:
    return store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/octet-stream",
        ),
    )


def _put_statement(
    store: FileSystemCAS,
    statement: object,
    *,
    kind: str,
) -> ArtifactRef:
    raw_mapping = contract._raw_model_mapping(statement)
    payload = contract._frame_record(contract._canonical_raw_bytes(raw_mapping))
    return _put_raw(store, payload, kind=kind)


def _fixture_ref(label: str, *, kind: str = "fixture.chronology") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(_digest(label)),
        kind=kind,
        media_type="application/octet-stream",
    )


@dataclass(slots=True)
class AppointedAnchorFixture:
    """Test-only independent acceptance/holder evidence graph and verifiers."""

    root: Path
    store: FileSystemCAS = field(init=False)
    evidence_repository: FileSystemSignedArtifactEvidenceRepository = field(init=False)
    signer: Ed25519Signer = field(init=False)
    verifier: Ed25519Verifier = field(init=False)
    signing_profile_ref: ArtifactRef = field(init=False)
    signer_provenance_ref: ArtifactRef = field(init=False)
    acceptance_appointment: contract.VerifiedAcceptanceVerifierAppointment = field(init=False)
    holder_appointment: contract.VerifiedHolderVerifierAppointment = field(init=False)
    lineage: InMemoryAnchorAcceptanceLineageRepository = field(init=False)
    challenge_repository: InMemoryAnchorReadbackChallengeRepository = field(init=False)
    qualification_cases: dict[contract.Digest, QualificationCase] = field(
        init=False, default_factory=dict
    )
    retained_package: contract.AnchorRetentionPackage | None = field(init=False, default=None)
    custody_receipt: contract.AnchorCustodyReceipt | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.store = FileSystemCAS(self.root / "cas")
        private_key = Ed25519PrivateKey.from_private_bytes(
            hashlib.sha256(b"gy-n12-c3-appointed-fixture-key-v1").digest()
        )
        self.signer = Ed25519Signer(private_key)
        self.verifier = Ed25519Verifier()
        self.verifier.add_trusted_key(private_key.public_key())
        self.evidence_repository = FileSystemSignedArtifactEvidenceRepository(self.store)
        self.lineage = InMemoryAnchorAcceptanceLineageRepository()
        self.challenge_repository = InMemoryAnchorReadbackChallengeRepository()
        self.signing_profile_ref = _fixture_ref("signing-profile")
        self.signer_provenance_ref = _fixture_ref("signer-provenance")
        self.acceptance_appointment = self._acceptance_appointment()
        self.holder_appointment = self._holder_appointment()

    def make_acceptance_request(
        self, *, query_label: str = "current"
    ) -> contract.AnchorAcceptanceRequest:
        """Persist the two opaque owner inputs and return their ref-only request."""

        query_ref = _digest(f"query-{query_label}")
        domain = contract.ChronologyProofDomain(
            format=contract.FULL_PREFIX_FORMAT,
            profile=contract.FULL_PREFIX_PROFILE,
            proof_domain="epoch",
            family="epoch",
            scope_ref=_digest("fixture-epoch-scope"),
            authority_purpose="publication",
        )
        case = make_qualification_case(
            self.root / "qualification" / query_label,
            shape="epoch",
            member_count=1,
            domain_override=domain,
            requested_query_context_ref=query_ref,
        )
        qualified = self._qualify_case(case)
        if not isinstance(qualified, contract.NativeProjectionCustodyGap):
            raise AssertionError("fixture native owner must reach the declared projection gap")
        reconciliation = qualified.reconciliation
        candidate = reconciliation.owner_context.owner_qualified_candidate.candidate
        built = build_full_prefix_bundle(
            contract.ChronologyBundleRequest(
                domain=domain,
                native_schema_profile=reconciliation.authoritative_native_schema_profile,
                declared_denominator_ref=candidate.declared_denominator_ref,
                requested_cutoff_ref=case.query.requested_cutoff_ref,
                requested_query_context_ref=query_ref,
                members=candidate.ordered_members,
            )
        )
        if not isinstance(built, contract.EncodedChronologyBundle):
            raise AssertionError("fixture bundle must fit the frozen full-prefix profile")
        if (
            built.bundle_content_hash != qualified.proof_result.bundle_content_hash
            or built.header != qualified.proof_result.parsed_header
        ):
            raise AssertionError("fixture native owner and bundle builder disagree")
        bundle_ref = _put_raw(
            self.store,
            built.bundle_bytes,
            kind="fixture.chronology.bundle",
        )
        reconciliation_bytes = canonical_statement_bytes(reconciliation)
        reconciliation_ref = _put_raw(
            self.store,
            reconciliation_bytes,
            kind="fixture.chronology.reconciliation",
        )
        self.qualification_cases[query_ref] = case
        lineage_state = self.lineage.resolve_lineage(
            key=contract.AnchorAcceptanceLineageKey(
                family="epoch",
                proof_domain=domain.proof_domain,
                scope_ref=domain.scope_ref,
                authority_purpose=domain.authority_purpose,
            )
        )
        lineage_statement = contract.AnchorAcceptanceLineageStateStatement.model_validate(
            from_canonical_bytes(contract._split_framed_records(lineage_state.statement_bytes)[0])
        )
        return build_anchor_acceptance_request(
            bundle_ref=bundle_ref,
            native_reconciliation_ref=reconciliation_ref,
            requested_query_context_ref=query_ref,
            asserted_prior_acceptance_record_refs=lineage_statement.current_record_refs,
        )

    @staticmethod
    def _qualify_case(case: QualificationCase) -> contract.NativeChronologyQualificationResult:
        registry = chronology_proof._PERSISTENCE_REGISTRY
        try:
            return case.appoint_consumer().qualify(adapter=case.adapter, request=case.query)
        finally:
            registry._clear_for_test()

    def _issue(self, payload: bytes, *, kind: str) -> contract.SignedArtifactEvidence:
        persisted = self.evidence_repository.persist_signed(
            blob_bytes=payload,
            write_options=ArtifactWriteOptions(
                kind=kind,
                media_type="application/octet-stream",
            ),
            signer=self.signer,
            signing_profile_ref=self.signing_profile_ref,
            signer_provenance_ref=self.signer_provenance_ref,
        )
        return self.evidence_repository.read_exact(
            evidence_record_ref=persisted.evidence_record_ref
        )

    def _acceptance_appointment(
        self,
    ) -> contract.VerifiedAcceptanceVerifierAppointment:
        trust_bytes = canonical_exact_mapping_bytes(
            {"role": "acceptance", "trusted_keys": self.verifier.trusted_key_ids}
        )
        trust_ref = self.store.put_bytes(
            trust_bytes,
            ArtifactWriteOptions(
                kind="fixture.acceptance_trust",
                media_type="application/octet-stream",
            ),
        )
        statement = contract.AcceptanceVerifierAppointmentStatement(
            schema_version="polisyos.chronology.acceptance-appointment.v1",
            family="epoch",
            proof_domain="epoch",
            authority_purpose="publication",
            accepting_owner_ref="fixture-epoch-owner",
            trust_config_ref=trust_ref,
            trust_config_content_hash=semantic_content_hash(
                "anchor-acceptance-trust-snapshot.v1", trust_bytes
            ),
            appointment_basis_ref=_fixture_ref("acceptance-basis"),
            verifier_provenance_ref=self.signer_provenance_ref,
        )
        statement_bytes = canonical_statement_bytes(statement)
        signed_statement = self._issue(statement_bytes, kind="fixture.acceptance_appointment")
        statement_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed_statement.persisted.record_bytes)[0])
        )
        appointment_ref = statement_record.artifact_ref
        appointment_hash = semantic_content_hash(
            "anchor-acceptance-appointment.v1", statement_bytes
        )
        verification = contract.AcceptanceAppointmentVerificationStatement(
            schema_version=("polisyos.chronology.acceptance-appointment-verification.v1"),
            appointment_ref=appointment_ref,
            appointment_content_hash=appointment_hash,
            trust_config_ref=trust_ref,
            trust_config_content_hash=statement.trust_config_content_hash,
            appointment_evidence_record_ref=(signed_statement.persisted.evidence_record_ref),
            appointment_evidence_record_content_hash=(
                signed_statement.persisted.evidence_record_content_hash
            ),
            verifier_provenance_ref=self.signer_provenance_ref,
            predicate_class="independently_reconciled",
        )
        verification_bytes = canonical_statement_bytes(verification)
        signed_verification = self._issue(
            verification_bytes,
            kind="fixture.acceptance_appointment_verification",
        )
        verification_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(
                contract._split_framed_records(signed_verification.persisted.record_bytes)[0]
            )
        )
        return contract.VerifiedAcceptanceVerifierAppointment(
            appointment_ref=appointment_ref,
            appointment_content_hash=appointment_hash,
            statement_bytes=statement_bytes,
            signed_appointment_evidence=signed_statement,
            trust_config_bytes=trust_bytes,
            verification_statement_bytes=verification_bytes,
            verification_receipt_ref=verification_record.artifact_ref,
            verification_receipt_content_hash=semantic_content_hash(
                "anchor-acceptance-appointment-verification.v1",
                verification_bytes,
            ),
            signed_verification_evidence=signed_verification,
        )

    def _holder_appointment(self) -> contract.VerifiedHolderVerifierAppointment:
        trust_bytes = canonical_exact_mapping_bytes(
            {"role": "holder", "trusted_keys": self.verifier.trusted_key_ids}
        )
        trust_ref = self.store.put_bytes(
            trust_bytes,
            ArtifactWriteOptions(
                kind="fixture.holder_trust",
                media_type="application/octet-stream",
            ),
        )
        statement = contract.HolderVerifierAppointmentStatement(
            schema_version="polisyos.chronology.holder-appointment.v1",
            family="epoch",
            proof_domain="epoch",
            authority_purpose="publication",
            holder_ref="fixture-independent-holder",
            trust_config_ref=trust_ref,
            trust_config_content_hash=semantic_content_hash(
                "anchor-holder-trust-snapshot.v1", trust_bytes
            ),
            custody_boundary_evidence_ref=_fixture_ref("custody-boundary"),
            verifier_provenance_ref=self.signer_provenance_ref,
        )
        statement_bytes = canonical_statement_bytes(statement)
        signed_statement = self._issue(statement_bytes, kind="fixture.holder_appointment")
        statement_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed_statement.persisted.record_bytes)[0])
        )
        appointment_ref = statement_record.artifact_ref
        appointment_hash = semantic_content_hash("anchor-holder-appointment.v1", statement_bytes)
        verification = contract.HolderAppointmentVerificationStatement(
            schema_version="polisyos.chronology.holder-appointment-verification.v1",
            appointment_ref=appointment_ref,
            appointment_content_hash=appointment_hash,
            trust_config_ref=trust_ref,
            trust_config_content_hash=statement.trust_config_content_hash,
            appointment_evidence_record_ref=(signed_statement.persisted.evidence_record_ref),
            appointment_evidence_record_content_hash=(
                signed_statement.persisted.evidence_record_content_hash
            ),
            verifier_provenance_ref=self.signer_provenance_ref,
            predicate_class="independently_reconciled",
        )
        verification_bytes = canonical_statement_bytes(verification)
        signed_verification = self._issue(
            verification_bytes,
            kind="fixture.holder_appointment_verification",
        )
        verification_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(
                contract._split_framed_records(signed_verification.persisted.record_bytes)[0]
            )
        )
        return contract.VerifiedHolderVerifierAppointment(
            appointment_ref=appointment_ref,
            appointment_content_hash=appointment_hash,
            statement_bytes=statement_bytes,
            signed_appointment_evidence=signed_statement,
            trust_config_bytes=trust_bytes,
            verification_statement_bytes=verification_bytes,
            verification_receipt_ref=verification_record.artifact_ref,
            verification_receipt_content_hash=semantic_content_hash(
                "anchor-holder-appointment-verification.v1", verification_bytes
            ),
            signed_verification_evidence=signed_verification,
        )

    def build_acceptance(
        self,
        *,
        query_label: str = "current",
        request: contract.AnchorAcceptanceRequest | None = None,
    ) -> tuple[
        contract.AnchorAcceptanceReceipt,
        contract.AnchorAcceptanceEvidenceBundle,
        InMemoryAnchorAcceptanceLineageRepository,
        contract.VerifiedAnchorAcceptance,
    ]:
        request = request or self.make_acceptance_request(query_label=query_label)
        query_ref = request.requested_query_context_ref
        lineage_key = contract.AnchorAcceptanceLineageKey(
            family="epoch",
            proof_domain=request.expected_domain.proof_domain,
            scope_ref=request.expected_domain.scope_ref,
            authority_purpose=request.authority_purpose,
        )
        prior_state = self.lineage.resolve_lineage(key=lineage_key)
        prior_state_statement = contract.AnchorAcceptanceLineageStateStatement.model_validate(
            from_canonical_bytes(contract._split_framed_records(prior_state.statement_bytes)[0])
        )
        prior_refs = prior_state_statement.current_record_refs
        if request.asserted_prior_acceptance_record_refs != prior_refs:
            raise ValueError("caller prior refs differ from owner current heads")
        try:
            bundle_report = self.store.verify(request.bundle_ref.artifact_id)
            reconciliation_report = self.store.verify(request.native_reconciliation_ref.artifact_id)
            bundle_bytes = self.store.get_bytes(request.bundle_ref.artifact_id)
            reconciliation_bytes = self.store.get_bytes(
                request.native_reconciliation_ref.artifact_id
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("acceptance input bytes are unavailable") from exc
        if not bundle_report.ok or not reconciliation_report.ok:
            raise ValueError("acceptance input bytes fail CAS verification")
        case = self.qualification_cases.get(query_ref)
        if case is None:
            raise ValueError("no owner-qualified native reconciliation exists for the query")
        qualified = self._qualify_case(case)
        if not isinstance(qualified, contract.NativeProjectionCustodyGap):
            raise ValueError("native owner did not produce the declared qualified result")
        reconciliation = qualified.reconciliation
        candidate = reconciliation.owner_context.owner_qualified_candidate.candidate
        expected_reconciliation_bytes = canonical_statement_bytes(reconciliation)
        expected_bundle = build_full_prefix_bundle(
            contract.ChronologyBundleRequest(
                domain=case.query.domain,
                native_schema_profile=reconciliation.authoritative_native_schema_profile,
                declared_denominator_ref=candidate.declared_denominator_ref,
                requested_cutoff_ref=case.query.requested_cutoff_ref,
                requested_query_context_ref=case.query.requested_query_context_ref,
                members=candidate.ordered_members,
            )
        )
        if not isinstance(expected_bundle, contract.EncodedChronologyBundle):
            raise ValueError("owner-qualified native bundle is not encodable")
        if (
            request.expected_domain != case.query.domain
            or request.native_reconciliation_ref.artifact_id
            != ArtifactID.from_sha256_hex(hashlib.sha256(expected_reconciliation_bytes).hexdigest())
            or reconciliation_bytes != expected_reconciliation_bytes
            or request.bundle_ref.artifact_id
            != ArtifactID.from_sha256_hex(hashlib.sha256(expected_bundle.bundle_bytes).hexdigest())
            or bundle_bytes != expected_bundle.bundle_bytes
            or qualified.proof_result.bundle_content_hash != expected_bundle.bundle_content_hash
        ):
            raise ValueError("request bytes differ from owner-qualified reconciliation")
        proof = FullPrefixVerifier().verify_bundle(
            bundle_bytes,
            expected_domain=request.expected_domain,
            expected_bundle_content_hash=contract.chronology_bundle_content_hash(bundle_bytes),
        )
        if not isinstance(proof, contract.FullPrefixVerified):
            raise ValueError("bundle failed full-prefix verification")
        header = proof.parsed_header
        if (
            header.requested_query_context_ref != query_ref
            or header.authority_purpose != request.authority_purpose
        ):
            raise ValueError("bundle header differs from the requested query")
        prior_by_ref = {
            str(item.acceptance_record_ref.artifact_id): item
            for item in prior_state_statement.records
        }
        derived_prior_prefixes: list[contract.OwnerDerivedAcceptedPrefix] = []
        seen_prefixes: set[tuple[int, contract.Digest]] = set()
        for prior_ref in prior_refs:
            prior_entry = prior_by_ref[str(prior_ref.artifact_id)]
            prior_evidence = self.evidence_repository.read_exact(
                evidence_record_ref=prior_entry.signed_statement_evidence_ref
            )
            prior_statement = contract.AnchorAcceptanceStatement.model_validate(
                from_canonical_bytes(contract._split_framed_records(prior_evidence.blob_bytes)[0])
            )
            expected_prefix = contract.ExpectedCommitmentPrefix(
                domain=contract.ChronologyProofDomain(
                    format=prior_statement.parsed_header.format,
                    profile=prior_statement.parsed_header.profile,
                    proof_domain=prior_statement.parsed_header.proof_domain,
                    family=prior_statement.parsed_header.family,
                    scope_ref=prior_statement.parsed_header.scope_ref,
                    authority_purpose=prior_statement.parsed_header.authority_purpose,
                ),
                member_count=prior_statement.parsed_header.member_count,
                commitment_head=prior_statement.parsed_header.commitment_head,
            )
            prior_proof = FullPrefixVerifier().verify_bundle(
                bundle_bytes,
                expected_domain=request.expected_domain,
                expected_prefix=expected_prefix,
                expected_bundle_content_hash=contract.chronology_bundle_content_hash(bundle_bytes),
            )
            if not isinstance(prior_proof, contract.FullPrefixVerified):
                raise ValueError("owner-derived accepted prefix is not a prefix of the bundle")
            prefix_key = (expected_prefix.member_count, expected_prefix.commitment_head)
            if prefix_key not in seen_prefixes:
                seen_prefixes.add(prefix_key)
                derived_prior_prefixes.append(
                    contract.OwnerDerivedAcceptedPrefix(
                        acceptance_record_ref=prior_ref,
                        acceptance_record_content_hash=(prior_entry.acceptance_record_content_hash),
                        statement_evidence_ref=prior_entry.signed_statement_evidence_ref,
                        expected_prefix=expected_prefix,
                    )
                )
        acceptance_statement = contract.AnchorAcceptanceStatement(
            accepting_owner_ref="fixture-epoch-owner",
            bundle_ref=request.bundle_ref,
            bundle_content_hash=contract.chronology_bundle_content_hash(bundle_bytes),
            parsed_header=header,
            native_reconciliation_ref=request.native_reconciliation_ref,
            authority_purpose=request.authority_purpose,
            requested_query_context_ref=query_ref,
            admission_cutoff_ref=header.requested_cutoff_ref,
            predicate_dispositions=(
                tuple(row.disposition for row in candidate.member_predicates)
                + tuple(row.disposition for row in candidate.query_predicates)
            ),
            prior_acceptance_record_refs=prior_refs,
            derived_prior_prefixes=tuple(derived_prior_prefixes),
            owner_lineage_state_content_hash=prior_state.state_content_hash,
            acceptance_appointment_ref=self.acceptance_appointment.appointment_ref,
            acceptance_appointment_content_hash=(
                self.acceptance_appointment.appointment_content_hash
            ),
            appointment_verification_receipt_ref=(
                self.acceptance_appointment.verification_receipt_ref
            ),
            appointment_verification_receipt_content_hash=(
                self.acceptance_appointment.verification_receipt_content_hash
            ),
            trust_snapshot_content_hash=semantic_content_hash(
                "anchor-acceptance-trust-snapshot.v1",
                self.acceptance_appointment.trust_config_bytes,
            ),
            verifier_provenance_ref=str(self.signer_provenance_ref.artifact_id),
        )
        statement_bytes = canonical_statement_bytes(acceptance_statement)
        signed_statement = self._issue(statement_bytes, kind="fixture.acceptance_statement")
        statement_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed_statement.persisted.record_bytes)[0])
        )
        acceptance_digest = semantic_content_hash("anchor-acceptance-statement.v1", statement_bytes)
        candidate = contract.AnchorAcceptanceRecord(
            acceptance_digest=acceptance_digest,
            statement_artifact_ref=statement_record.artifact_ref,
            statement_content_hash=acceptance_digest,
            signed_statement_evidence_ref=signed_statement.persisted.evidence_record_ref,
            prior_acceptance_record_refs=prior_refs,
        )
        candidate_bytes = canonical_statement_bytes(candidate)
        candidate_ref = self.store.put_bytes(
            candidate_bytes,
            ArtifactWriteOptions(
                kind="fixture.acceptance_candidate",
                media_type="application/octet-stream",
            ),
        )
        entry = contract.AcceptedAnchorRecordEntry(
            acceptance_record_ref=candidate_ref,
            acceptance_record_content_hash=semantic_content_hash(
                "anchor-acceptance-candidate.v1", candidate_bytes
            ),
            acceptance_digest=acceptance_digest,
            signed_statement_evidence_ref=signed_statement.persisted.evidence_record_ref,
            requested_query_context_ref=query_ref,
            admission_cutoff_ref=header.requested_cutoff_ref,
            predecessor_record_refs=prior_refs,
        )
        lineage = self.lineage
        append = lineage.append_if_current(
            key=lineage_key,
            expected_head_refs=prior_refs,
            record=entry,
        )
        if not isinstance(append, contract.PersistedAnchorAcceptanceAppendSuccess):
            raise AssertionError("fixture lineage append must succeed")
        receipt_statement = contract.AnchorAcceptanceReceiptStatement(
            acceptance_digest=acceptance_digest,
            acceptance_record_ref=candidate_ref,
            acceptance_record_content_hash=entry.acceptance_record_content_hash,
            signed_statement_evidence_ref=signed_statement.persisted.evidence_record_ref,
            lineage_append_receipt_ref=append.append_receipt_ref,
            lineage_append_receipt_content_hash=append.append_receipt_content_hash,
            lineage_key_ref=raw_content_hash(canonical_statement_bytes(lineage_key)),
            requested_query_context_ref=query_ref,
            admission_cutoff_ref=header.requested_cutoff_ref,
        )
        receipt_bytes = canonical_statement_bytes(receipt_statement)
        signed_receipt = self._issue(receipt_bytes, kind="fixture.acceptance_receipt")
        receipt_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed_receipt.persisted.record_bytes)[0])
        )
        receipt = contract.AnchorAcceptanceReceipt(
            receipt_record_ref=receipt_record.artifact_ref,
            receipt_record_content_hash=semantic_content_hash(
                "anchor-acceptance-receipt.v1", receipt_bytes
            ),
            statement_bytes=receipt_bytes,
            receipt_record_bytes=receipt_bytes,
            signed_receipt_evidence=signed_receipt,
        )
        evidence = contract.AnchorAcceptanceEvidenceBundle(
            acceptance_statement_evidence=signed_statement,
            acceptance_record_bytes=candidate_bytes,
            acceptance_receipt_bytes=receipt_bytes,
            acceptance_receipt_signed_evidence=signed_receipt,
            lineage_append_receipt_bytes=append.statement_bytes,
        )
        verified = ExactAnchorAcceptanceReceiptVerifier(self.verifier).verify(
            receipt=receipt,
            appointment=self.acceptance_appointment,
            evidence=evidence,
            lineage=lineage,
            requested_query_context_ref=query_ref,
        )
        if not isinstance(verified, contract.VerifiedAnchorAcceptance):
            raise AssertionError(f"fixture acceptance failed: {verified}")
        return receipt, evidence, lineage, verified

    def build_retention(
        self,
        *,
        query_label: str = "current",
    ) -> tuple[
        contract.AnchorCustodyReceipt,
        contract.AnchorReadbackReceipt,
        contract.PersistedAnchorReadbackChallenge,
        contract.VerifiedAnchorRetention,
    ]:
        request = self.make_acceptance_request(query_label=query_label)
        receipt, acceptance_evidence, _, accepted = self.build_acceptance(request=request)
        bundle_bytes = self.store.get_bytes(request.bundle_ref.artifact_id)
        reconciliation_bytes = self.store.get_bytes(request.native_reconciliation_ref.artifact_id)
        retention_statement = contract.AnchorRetentionStatement(
            family="epoch",
            proof_domain="epoch",
            authority_purpose="publication",
            requested_query_context_ref=accepted.requested_query_context_ref,
            admission_cutoff_ref=accepted.admission_cutoff_ref,
            bundle_ref=request.bundle_ref,
            bundle_content_hash=contract.chronology_bundle_content_hash(bundle_bytes),
            native_reconciliation_ref=request.native_reconciliation_ref,
            acceptance_receipt_ref=receipt.receipt_record_ref,
            acceptance_receipt_content_hash=receipt.receipt_record_content_hash,
            prior_acceptance_record_refs=accepted.prior_acceptance_record_refs,
            acceptance_appointment_ref=self.acceptance_appointment.appointment_ref,
            acceptance_appointment_content_hash=(
                self.acceptance_appointment.appointment_content_hash
            ),
            holder_appointment_ref=self.holder_appointment.appointment_ref,
            holder_appointment_content_hash=self.holder_appointment.appointment_content_hash,
        )
        graph = contract.AnchorRetentionObjectGraph(
            retention_statement_bytes=canonical_statement_bytes(retention_statement),
            bundle_bytes=bundle_bytes,
            native_reconciliation_bytes=reconciliation_bytes,
            acceptance_evidence=acceptance_evidence,
            acceptance_appointment=self.acceptance_appointment,
            holder_appointment=self.holder_appointment,
        )
        package = build_retention_package(graph)
        self.retained_package = package
        custody_statement = contract.AnchorCustodyReceiptStatement(
            family="epoch",
            proof_domain="epoch",
            authority_purpose="publication",
            holder_appointment_ref=self.holder_appointment.appointment_ref,
            holder_ref="fixture-independent-holder",
            package_ref=package.package_ref,
            package_content_hash=package.package_content_hash,
            object_version_ref="version-1",
            retention_policy_ref=_fixture_ref("retention-policy"),
            requested_query_context_ref=accepted.requested_query_context_ref,
        )
        custody_bytes = canonical_statement_bytes(custody_statement)
        signed_custody = self._issue(custody_bytes, kind="fixture.custody_receipt")
        custody_evidence_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed_custody.persisted.record_bytes)[0])
        )
        custody_record_bytes = canonical_statement_bytes(
            contract.AnchorCustodyReceiptRecord(
                statement_artifact_ref=custody_evidence_record.artifact_ref,
                statement_content_hash=semantic_content_hash(
                    "anchor-custody-receipt.v1", custody_bytes
                ),
                signed_statement_evidence_ref=(signed_custody.persisted.evidence_record_ref),
                signed_statement_evidence_content_hash=(
                    signed_custody.persisted.evidence_record_content_hash
                ),
            )
        )
        custody_record_ref = self.store.put_bytes(
            custody_record_bytes,
            ArtifactWriteOptions(
                kind="fixture.custody_receipt_record",
                media_type="application/octet-stream",
            ),
        )
        custody = contract.AnchorCustodyReceipt(
            receipt_record_ref=custody_record_ref,
            receipt_record_raw_bytes_hash=raw_content_hash(custody_record_bytes),
            receipt_record_bytes=custody_record_bytes,
            statement_bytes=custody_bytes,
            signed_statement_evidence=signed_custody,
        )
        self.custody_receipt = custody
        challenge_statement = contract.AnchorReadbackChallengeStatement(
            family="epoch",
            proof_domain="epoch",
            authority_purpose="publication",
            lineage_key=contract.AnchorAcceptanceLineageKey(
                family="epoch",
                proof_domain="epoch",
                scope_ref=_digest("fixture-epoch-scope"),
                authority_purpose="publication",
            ),
            holder_appointment_ref=self.holder_appointment.appointment_ref,
            package_ref=package.package_ref,
            expected_package_content_hash=package.package_content_hash,
            custody_receipt_record_ref=custody.receipt_record_ref,
            custody_receipt_record_raw_bytes_hash=(custody.receipt_record_raw_bytes_hash),
            expected_object_version_ref="version-1",
            requested_query_context_ref=accepted.requested_query_context_ref,
        )
        challenge = self.challenge_repository.persist(challenge_statement)
        readback_statement = contract.AnchorReadbackReceiptStatement(
            family="epoch",
            proof_domain="epoch",
            authority_purpose="publication",
            holder_ref="fixture-independent-holder",
            holder_appointment_ref=self.holder_appointment.appointment_ref,
            challenge_record_ref=challenge.challenge_record_ref,
            challenge_record_content_hash=challenge.challenge_record_content_hash,
            custody_receipt_record_ref=custody.receipt_record_ref,
            custody_receipt_record_raw_bytes_hash=(custody.receipt_record_raw_bytes_hash),
            package_ref=package.package_ref,
            package_content_hash=package.package_content_hash,
            object_version_ref="version-1",
            retention_policy_ref=custody_statement.retention_policy_ref,
            requested_query_context_ref=accepted.requested_query_context_ref,
        )
        readback_bytes = canonical_statement_bytes(readback_statement)
        signed_readback = self._issue(readback_bytes, kind="fixture.readback_receipt")
        readback_evidence_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed_readback.persisted.record_bytes)[0])
        )
        readback_record_bytes = canonical_statement_bytes(
            contract.AnchorReadbackReceiptRecord(
                statement_artifact_ref=readback_evidence_record.artifact_ref,
                statement_content_hash=semantic_content_hash(
                    "anchor-readback-receipt.v1", readback_bytes
                ),
                signed_statement_evidence_ref=(signed_readback.persisted.evidence_record_ref),
                signed_statement_evidence_content_hash=(
                    signed_readback.persisted.evidence_record_content_hash
                ),
            )
        )
        readback_record_ref = self.store.put_bytes(
            readback_record_bytes,
            ArtifactWriteOptions(
                kind="fixture.readback_receipt_record",
                media_type="application/octet-stream",
            ),
        )
        readback = contract.AnchorReadbackReceipt(
            receipt_record_ref=readback_record_ref,
            receipt_record_raw_bytes_hash=raw_content_hash(readback_record_bytes),
            receipt_record_bytes=readback_record_bytes,
            statement_bytes=readback_bytes,
            package_bytes=package.package_bytes,
            retention_receipt=custody,
            signed_statement_evidence=signed_readback,
        )
        verified = ExactAnchorHolderReceiptVerifier(self.verifier).verify_retention_and_readback(
            retention=custody,
            readback=readback,
            challenge=challenge,
            appointment=self.holder_appointment,
        )
        if not isinstance(verified, contract.VerifiedAnchorRetention):
            raise AssertionError(f"fixture retention failed: {verified}")
        return custody, readback, challenge, verified

    def retain_package(
        self, package: contract.AnchorRetentionPackage
    ) -> contract.AnchorCustodyReceipt:
        """Act as the test-only appointed holder for one exact package."""

        graph = contract.AnchorRetentionObjectGraph.model_validate(
            from_canonical_bytes(contract._split_framed_records(package.package_bytes)[0])
        )
        retention = contract.AnchorRetentionStatement.model_validate(
            from_canonical_bytes(contract._split_framed_records(graph.retention_statement_bytes)[0])
        )
        statement = contract.AnchorCustodyReceiptStatement(
            family="epoch",
            proof_domain=retention.proof_domain,
            authority_purpose=retention.authority_purpose,
            holder_appointment_ref=self.holder_appointment.appointment_ref,
            holder_ref="fixture-independent-holder",
            package_ref=package.package_ref,
            package_content_hash=package.package_content_hash,
            object_version_ref="version-1",
            retention_policy_ref=_fixture_ref("retention-policy"),
            requested_query_context_ref=retention.requested_query_context_ref,
        )
        statement_bytes = canonical_statement_bytes(statement)
        signed = self._issue(statement_bytes, kind="fixture.custody_receipt")
        evidence_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed.persisted.record_bytes)[0])
        )
        record_bytes = canonical_statement_bytes(
            contract.AnchorCustodyReceiptRecord(
                statement_artifact_ref=evidence_record.artifact_ref,
                statement_content_hash=semantic_content_hash(
                    "anchor-custody-receipt.v1", statement_bytes
                ),
                signed_statement_evidence_ref=signed.persisted.evidence_record_ref,
                signed_statement_evidence_content_hash=(
                    signed.persisted.evidence_record_content_hash
                ),
            )
        )
        record_ref = self.store.put_bytes(
            record_bytes,
            ArtifactWriteOptions(
                kind="fixture.custody_receipt_record",
                media_type="application/octet-stream",
            ),
        )
        receipt = contract.AnchorCustodyReceipt(
            receipt_record_ref=record_ref,
            receipt_record_raw_bytes_hash=raw_content_hash(record_bytes),
            receipt_record_bytes=record_bytes,
            statement_bytes=statement_bytes,
            signed_statement_evidence=signed,
        )
        self.retained_package = package
        self.custody_receipt = receipt
        return receipt

    def readback_challenge(
        self, challenge: contract.PersistedAnchorReadbackChallenge
    ) -> contract.AnchorReadbackReceipt:
        """Return only holder-kept bytes for the exact persisted challenge."""

        if self.retained_package is None or self.custody_receipt is None:
            raise RuntimeError("holder has no retained package")
        statement = contract.AnchorReadbackChallengeStatement.model_validate(
            from_canonical_bytes(contract._split_framed_records(challenge.statement_bytes)[0])
        )
        if (
            statement.package_ref != self.retained_package.package_ref
            or statement.custody_receipt_record_ref != self.custody_receipt.receipt_record_ref
        ):
            raise ValueError("challenge does not name the retained holder graph")
        custody_statement = contract.AnchorCustodyReceiptStatement.model_validate(
            from_canonical_bytes(
                contract._split_framed_records(self.custody_receipt.statement_bytes)[0]
            )
        )
        readback_statement = contract.AnchorReadbackReceiptStatement(
            family="epoch",
            proof_domain=statement.proof_domain,
            authority_purpose=statement.authority_purpose,
            holder_ref="fixture-independent-holder",
            holder_appointment_ref=self.holder_appointment.appointment_ref,
            challenge_record_ref=challenge.challenge_record_ref,
            challenge_record_content_hash=challenge.challenge_record_content_hash,
            custody_receipt_record_ref=self.custody_receipt.receipt_record_ref,
            custody_receipt_record_raw_bytes_hash=(
                self.custody_receipt.receipt_record_raw_bytes_hash
            ),
            package_ref=self.retained_package.package_ref,
            package_content_hash=self.retained_package.package_content_hash,
            object_version_ref=custody_statement.object_version_ref,
            retention_policy_ref=custody_statement.retention_policy_ref,
            requested_query_context_ref=statement.requested_query_context_ref,
        )
        statement_bytes = canonical_statement_bytes(readback_statement)
        signed = self._issue(statement_bytes, kind="fixture.readback_receipt")
        evidence_record = contract.SignedArtifactEvidenceRecord.model_validate(
            json.loads(contract._split_framed_records(signed.persisted.record_bytes)[0])
        )
        record_bytes = canonical_statement_bytes(
            contract.AnchorReadbackReceiptRecord(
                statement_artifact_ref=evidence_record.artifact_ref,
                statement_content_hash=semantic_content_hash(
                    "anchor-readback-receipt.v1", statement_bytes
                ),
                signed_statement_evidence_ref=signed.persisted.evidence_record_ref,
                signed_statement_evidence_content_hash=(
                    signed.persisted.evidence_record_content_hash
                ),
            )
        )
        record_ref = self.store.put_bytes(
            record_bytes,
            ArtifactWriteOptions(
                kind="fixture.readback_receipt_record",
                media_type="application/octet-stream",
            ),
        )
        return contract.AnchorReadbackReceipt(
            receipt_record_ref=record_ref,
            receipt_record_raw_bytes_hash=raw_content_hash(record_bytes),
            receipt_record_bytes=record_bytes,
            statement_bytes=statement_bytes,
            package_bytes=self.retained_package.package_bytes,
            retention_receipt=self.custody_receipt,
            signed_statement_evidence=signed,
        )


@dataclass(frozen=True, slots=True)
class _FixtureAcceptanceAuthority:
    fixture: AppointedAnchorFixture

    def recompute_and_accept(
        self, request: contract.AnchorAcceptanceRequest
    ) -> contract.AnchorAcceptanceReceipt | contract.AcceptanceNonReceipt:
        try:
            return self.fixture.build_acceptance(request=request)[0]
        except ValueError:
            return contract.AcceptanceRejectedNonReceipt(
                status="rejected",
                component="acceptance",
                code="anchor_query_or_lineage_mismatch",
                subject_artifact_ref=request.bundle_ref,
                requested_query_context_ref=request.requested_query_context_ref,
                appointment_ref=self.fixture.acceptance_appointment.appointment_ref,
                verifier_provenance_ref=self.fixture.signer_provenance_ref,
                decisive_evidence_refs=(
                    request.bundle_ref,
                    self.fixture.acceptance_appointment.signed_appointment_evidence.persisted.evidence_record_ref,
                ),
                predicate_class="independently_reconciled",
            )


@dataclass(frozen=True, slots=True)
class _FixtureHolder:
    fixture: AppointedAnchorFixture

    def retain(self, package: contract.AnchorRetentionPackage) -> contract.AnchorCustodyReceipt:
        return self.fixture.retain_package(package)

    def readback(
        self, challenge: contract.PersistedAnchorReadbackChallenge
    ) -> contract.AnchorReadbackReceipt:
        return self.fixture.readback_challenge(challenge)


@dataclass(frozen=True, slots=True)
class _FixtureAppointmentResolver:
    fixture: AppointedAnchorFixture
    acceptance: bool
    holder: bool

    def resolve_epoch_appointments(
        self, *, family: Literal["epoch"], proof_domain: str, authority_purpose: str
    ) -> contract.EpochAnchorAppointmentResolution:
        from polisyos.runtime.quality.chronology_custody import (
            NoEpochAnchorAppointmentResolver,
        )

        absent = NoEpochAnchorAppointmentResolver().resolve_epoch_appointments(
            family=family,
            proof_domain=proof_domain,
            authority_purpose=authority_purpose,
        )
        acceptance = (
            contract.EstablishedAcceptanceAppointment(
                status="established", appointment=self.fixture.acceptance_appointment
            )
            if self.acceptance
            else absent.acceptance
        )
        holder = (
            contract.EstablishedHolderAppointment(
                status="established", appointment=self.fixture.holder_appointment
            )
            if self.holder
            else absent.holder
        )
        return contract.EpochAnchorAppointmentResolution(
            acceptance=acceptance,
            holder=holder,
        )


@dataclass(frozen=True, slots=True)
class _FixtureAuthorityRegistry:
    fixture: AppointedAnchorFixture

    def resolve_acceptance_authority(
        self, *, appointment: contract.VerifiedAcceptanceVerifierAppointment
    ) -> _FixtureAcceptanceAuthority:
        if appointment != self.fixture.acceptance_appointment:
            raise ValueError("unexpected acceptance appointment")
        return _FixtureAcceptanceAuthority(self.fixture)

    def resolve_holder(
        self, *, appointment: contract.VerifiedHolderVerifierAppointment
    ) -> _FixtureHolder:
        if appointment != self.fixture.holder_appointment:
            raise ValueError("unexpected holder appointment")
        return _FixtureHolder(self.fixture)

    def resolve_acceptance_verifier(
        self, *, appointment: contract.VerifiedAcceptanceVerifierAppointment
    ) -> ExactAnchorAcceptanceReceiptVerifier:
        if appointment != self.fixture.acceptance_appointment:
            raise ValueError("unexpected acceptance appointment")
        return ExactAnchorAcceptanceReceiptVerifier(self.fixture.verifier)

    def resolve_acceptance_lineage(
        self, *, appointment: contract.VerifiedAcceptanceVerifierAppointment
    ) -> InMemoryAnchorAcceptanceLineageRepository:
        if appointment != self.fixture.acceptance_appointment:
            raise ValueError("unexpected acceptance appointment")
        return self.fixture.lineage

    def resolve_holder_verifier(
        self, *, appointment: contract.VerifiedHolderVerifierAppointment
    ) -> ExactAnchorHolderReceiptVerifier:
        if appointment != self.fixture.holder_appointment:
            raise ValueError("unexpected holder appointment")
        return ExactAnchorHolderReceiptVerifier(self.fixture.verifier)


def build_appointed_anchor_service(
    fixture: AppointedAnchorFixture,
    *,
    acceptance: bool = True,
    holder: bool = True,
) -> contract.EpochAnchorCustodyProvider:
    """Build a test-only service; production has no injection seam for it."""
    from polisyos.runtime.quality.chronology_custody import EpochAnchorCustodyService

    return EpochAnchorCustodyService(
        appointment_resolver=_FixtureAppointmentResolver(
            fixture=fixture,
            acceptance=acceptance,
            holder=holder,
        ),
        authority_registry=_FixtureAuthorityRegistry(fixture),
        issuance_evidence=fixture.evidence_repository,
        challenge_repository=fixture.challenge_repository,
    )


def _native_bytes(
    *,
    shape: Literal["epoch", "inventory"],
    ordinal: int,
    annotation_revision: int,
) -> bytes:
    if shape == "epoch":
        mapping: dict[str, object] = {
            "schema": "fixture.epoch-like-native.v1",
            "epoch_ref": f"semantic-version-{ordinal}",
            "valid_effect": [ordinal, ordinal + 1],
            "visibility_knowledge": [ordinal + 10, ordinal + 11],
            "branch": "a" if ordinal % 2 == 0 else "b",
            "annotation_revision": annotation_revision,
            "status": "historical" if ordinal == 0 else "current",
        }
    else:
        mapping = {
            "schema": "fixture.opaque-inventory.v1",
            "inventory_record_id": f"record-{ordinal}",
            "opaque_value": f"value-{ordinal}",
            "annotation_revision": annotation_revision,
            "terminal": ordinal > 0,
            "historical": ordinal == 0,
        }
    return contract._canonical_raw_bytes(mapping)


class _FixtureBytesModel(BaseModel):
    """Strict immutable schema for independently persisted fixture authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _OwnerEvidenceStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.owner-evidence.v1"]
    subject_kind: Literal["member", "query"]
    subject_ref: contract.Digest
    predicate_id: str
    predicate_class: contract.PredicateClass
    status: Literal["satisfied", "rejected", "not_established"]
    failure_code: str | None


class _NativeDenominatorMember(_FixtureBytesModel):
    member_ref: contract.Digest
    native_artifact_ref: ArtifactRef
    native_content_hash: contract.Digest
    native_schema_profile: str
    member_admission_basis_ref: contract.Digest
    member_admission_context_ref: contract.Digest
    predicate_evidence_refs: tuple[ArtifactRef, ...]


class _NativeDenominatorStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.native-denominator.v1"]
    family: str
    native_schema_profile: str
    native_authority_head_refs: tuple[contract.Digest, ...]
    members: tuple[_NativeDenominatorMember, ...]


class _OwnerQueryContextStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.owner-query-context.v1"]
    query: contract.NativeChronologyQuery
    exterior_limitation_code: str | None
    predicate_evidence_refs: tuple[ArtifactRef, ...]


class _OwnerRelationStatement(_FixtureBytesModel):
    schema_version: Literal["fixture.chronology.owner-relation.v1"]
    key: contract.PredicatePolicySelectionKey
    policy_ref: ArtifactRef
    native_denominator_artifact_ref: ArtifactRef
    query_context_artifact_ref: ArtifactRef


@dataclass(frozen=True, slots=True)
class _OwnerTruth:
    query: contract.NativeChronologyQuery
    native_schema_profile: str
    denominator_ref: contract.Digest
    denominator_artifact_ref: ArtifactRef
    denominator_content_hash: contract.Digest
    query_context_artifact_ref: ArtifactRef
    query_context_content_hash: contract.Digest
    member_identities: tuple[contract.VerifiedNativeMemberIdentity, ...]
    predicate_statements: tuple[_OwnerEvidenceStatement, ...]
    predicate_evidence: tuple[contract.VerifiedOwnerPredicateEvidence, ...]
    exterior_limitation_code: str | None
    native_authority_head_refs: tuple[contract.Digest, ...]


_DENOMINATOR_PREFIX = b"fixture.native-denominator.v1\0"
_QUERY_CONTEXT_PREFIX = b"fixture.query-context.v1\0"


def _model_bytes(model: BaseModel) -> bytes:
    return contract._canonical_raw_bytes(contract._raw_model_mapping(model))


def _load_typed_bytes(
    store: FileSystemCAS,
    ref: ArtifactRef,
    model: type[_FixtureBytesModel],
) -> tuple[_FixtureBytesModel, bytes]:
    report = store.verify(ref.artifact_id)
    payload = store.get_bytes(ref.artifact_id)
    if not report.ok or str(ref.artifact_id) != contract._sha256_digest(payload):
        raise ValueError("fixture authority bytes fail CAS verification")
    raw: Any = json.loads(payload)
    if not isinstance(raw, dict) or contract._canonical_raw_bytes(raw) != payload:
        raise ValueError("fixture authority bytes are not canonical")
    return model.model_validate(raw), payload


@dataclass(slots=True)
class EpochLikeQualificationAdapter:
    """Test-only epoch-like shape with sparse bitemporal and branch roles."""

    candidate: contract.NativeChronologyCandidate
    epoch_ref: str = "semantic-version-current"
    valid_effect_roles: tuple[str, str] = ("valid", "effect")
    visibility_knowledge_roles: tuple[str, str] = ("visibility", "knowledge")
    incomparable_native_branches: tuple[str, str] = ("a", "b")
    calls: int = 0

    def reconcile_candidate(
        self, request: contract.NativeChronologyQuery
    ) -> contract.NativeChronologyCandidate:
        self.calls += 1
        if request != self.candidate.query:
            return self.candidate.model_copy(update={"query": request})
        return self.candidate


@dataclass(slots=True)
class OpaqueInventoryQualificationAdapter:
    """Test-only non-epoch shape with no native clock, fork or authority head."""

    candidate: contract.NativeChronologyCandidate
    calls: int = 0

    def reconcile_candidate(
        self, request: contract.NativeChronologyQuery
    ) -> contract.NativeChronologyCandidate:
        self.calls += 1
        if request != self.candidate.query:
            return self.candidate.model_copy(update={"query": request})
        return self.candidate


@dataclass(slots=True)
class _SingleAdmissionIndex:
    key: contract.PredicatePolicySelectionKey
    refs: tuple[ArtifactRef, ...]
    calls: list[contract.PredicatePolicySelectionKey] = field(default_factory=list)

    def enumerate_admission_refs(
        self, *, key: contract.PredicatePolicySelectionKey
    ) -> tuple[ArtifactRef, ...]:
        self.calls.append(key)
        if key != self.key:
            return ()
        return self.refs


@dataclass(frozen=True, slots=True)
class _FixtureOwnerVerifier:
    store: FileSystemCAS
    key: contract.PredicatePolicySelectionKey
    policy: contract.PersistedPredicateAdmissionPolicy
    policy_owner_provenance_bytes: bytes
    owner_relation_bytes: bytes
    owner_relation_ref: ArtifactRef
    owner_relation_content_hash: contract.Digest
    owner_receipt_ref: ArtifactRef
    owner_verifier_ref: ArtifactRef
    policy_owner_provenance_ref: ArtifactRef
    trust_snapshot_ref: ArtifactRef
    policy_owner_receipt_ref: ArtifactRef
    evidence_verifier_ref: ArtifactRef
    failure_evidence_ref: ArtifactRef
    _calls: list[None] = field(default_factory=list)

    @property
    def calls(self) -> int:
        return len(self._calls)

    def _rejected(
        self, query: contract.NativeChronologyQuery
    ) -> contract.PolicyOwnerRelationRejected:
        return contract.PolicyOwnerRelationRejected(
            code="policy_owner_relation_rejected",
            status="rejected",
            key=self.key,
            requested_query_context_ref=query.requested_query_context_ref,
            owner_relation_ref=self.owner_relation_ref,
            evidence_ref=self.failure_evidence_ref,
        )

    def _stored_exact(self, ref: ArtifactRef, expected: bytes) -> bool:
        try:
            report = self.store.verify(ref.artifact_id)
            payload = self.store.get_bytes(ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False
        return (
            report.ok
            and payload == expected
            and str(ref.artifact_id) == (f"sha256:{hashlib.sha256(expected).hexdigest()}")
        )

    def _denominator_mismatch(
        self,
        *,
        query: contract.NativeChronologyQuery,
        expected: contract.Digest,
        observed: contract.Digest,
    ) -> contract.PolicyOwnerDenominatorMismatchFailure:
        return contract.PolicyOwnerDenominatorMismatchFailure(
            code="native_denominator_mismatch",
            status="rejected",
            key=self.key,
            requested_query_context_ref=query.requested_query_context_ref,
            expected_denominator_ref=expected,
            observed_denominator_ref=observed,
        )

    def _load_evidence(
        self,
        ref: ArtifactRef,
    ) -> tuple[_OwnerEvidenceStatement, contract.VerifiedOwnerPredicateEvidence]:
        loaded, payload = _load_typed_bytes(
            self.store,
            ref,
            _OwnerEvidenceStatement,
        )
        if not isinstance(loaded, _OwnerEvidenceStatement):
            raise TypeError("owner evidence decoder returned the wrong model")
        verified = contract.VerifiedOwnerPredicateEvidence(
            subject_kind=loaded.subject_kind,
            subject_ref=loaded.subject_ref,
            predicate_id=loaded.predicate_id,
            predicate_class=loaded.predicate_class,
            status=loaded.status,
            evidence_ref=ref,
            evidence_content_hash=contract._sha256_digest(payload),
            evidence_verifier_provenance_ref=self.evidence_verifier_ref,
        )
        return loaded, verified

    def _derive_owner_truth(self) -> _OwnerTruth:
        relation, stored_relation_bytes = _load_typed_bytes(
            self.store,
            self.owner_relation_ref,
            _OwnerRelationStatement,
        )
        if not isinstance(relation, _OwnerRelationStatement):
            raise TypeError("owner relation decoder returned the wrong model")
        if (
            stored_relation_bytes != self.owner_relation_bytes
            or relation.key != self.key
            or relation.policy_ref != self.policy.policy_ref
        ):
            raise ValueError("owner relation is not bound to the appointed policy")

        denominator, denominator_bytes = _load_typed_bytes(
            self.store,
            relation.native_denominator_artifact_ref,
            _NativeDenominatorStatement,
        )
        query_context, query_context_bytes = _load_typed_bytes(
            self.store,
            relation.query_context_artifact_ref,
            _OwnerQueryContextStatement,
        )
        if not isinstance(denominator, _NativeDenominatorStatement) or not isinstance(
            query_context, _OwnerQueryContextStatement
        ):
            raise TypeError("owner truth decoder returned the wrong model")
        if denominator.family != self.key.family:
            raise ValueError("owner denominator names a different family")
        if denominator.native_schema_profile != self.policy.statement.native_schema_profile:
            raise ValueError("owner denominator profile differs from owner policy")

        member_identities: list[contract.VerifiedNativeMemberIdentity] = []
        evidence_statements: list[_OwnerEvidenceStatement] = []
        predicate_evidence: list[contract.VerifiedOwnerPredicateEvidence] = []
        for member in denominator.members:
            report = self.store.verify(member.native_artifact_ref.artifact_id)
            native_bytes = self.store.get_bytes(member.native_artifact_ref.artifact_id)
            if (
                not report.ok
                or str(member.native_artifact_ref.artifact_id)
                != contract._sha256_digest(native_bytes)
                or member.native_content_hash != contract._native_content_hash(native_bytes)
            ):
                raise ValueError("owner member bytes fail independent verification")
            member_identities.append(
                contract.VerifiedNativeMemberIdentity(
                    member_ref=member.member_ref,
                    native_artifact_ref=member.native_artifact_ref,
                    native_content_hash=member.native_content_hash,
                    native_schema_profile=member.native_schema_profile,
                    member_admission_basis_ref=member.member_admission_basis_ref,
                    member_admission_context_ref=member.member_admission_context_ref,
                )
            )
            for evidence_ref in member.predicate_evidence_refs:
                statement, verified = self._load_evidence(evidence_ref)
                if statement.subject_kind != "member" or statement.subject_ref != member.member_ref:
                    raise ValueError("member evidence names the wrong owner subject")
                evidence_statements.append(statement)
                predicate_evidence.append(verified)

        for evidence_ref in query_context.predicate_evidence_refs:
            statement, verified = self._load_evidence(evidence_ref)
            if (
                statement.subject_kind != "query"
                or statement.subject_ref != query_context.query.requested_query_context_ref
            ):
                raise ValueError("query evidence names the wrong owner subject")
            evidence_statements.append(statement)
            predicate_evidence.append(verified)

        return _OwnerTruth(
            query=query_context.query,
            native_schema_profile=denominator.native_schema_profile,
            denominator_ref=contract._sha256_digest(
                _DENOMINATOR_PREFIX,
                denominator_bytes,
            ),
            denominator_artifact_ref=relation.native_denominator_artifact_ref,
            denominator_content_hash=contract._sha256_digest(
                _DENOMINATOR_PREFIX,
                denominator_bytes,
            ),
            query_context_artifact_ref=relation.query_context_artifact_ref,
            query_context_content_hash=contract._sha256_digest(
                _QUERY_CONTEXT_PREFIX,
                query_context_bytes,
            ),
            member_identities=tuple(member_identities),
            predicate_statements=tuple(evidence_statements),
            predicate_evidence=tuple(predicate_evidence),
            exterior_limitation_code=query_context.exterior_limitation_code,
            native_authority_head_refs=denominator.native_authority_head_refs,
        )

    def verify_owner_relation(
        self,
        *,
        query: contract.NativeChronologyQuery,
        admission: contract.PredicatePolicyAdmissionStatement,
        policy: contract.PersistedPredicateAdmissionPolicy,
        policy_owner_provenance_bytes: bytes,
        owner_relation_bytes: bytes,
        candidate: contract.NativeChronologyCandidate,
    ) -> (
        contract.VerifiedPredicatePolicyOwnerRelation | contract.PredicatePolicyOwnerRelationFailure
    ):
        self._calls.append(None)
        if (
            admission.key != self.key
            or policy != self.policy
            or policy_owner_provenance_bytes != self.policy_owner_provenance_bytes
            or owner_relation_bytes != self.owner_relation_bytes
            or not self._stored_exact(
                self.policy_owner_provenance_ref,
                self.policy_owner_provenance_bytes,
            )
            or not self._stored_exact(self.owner_relation_ref, self.owner_relation_bytes)
        ):
            return self._rejected(query)
        try:
            truth = self._derive_owner_truth()
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._rejected(query)

        try:
            _, candidate_denominator_bytes = _load_typed_bytes(
                self.store,
                candidate.native_denominator_artifact_ref,
                _NativeDenominatorStatement,
            )
            candidate_denominator_ref = contract._sha256_digest(
                _DENOMINATOR_PREFIX,
                candidate_denominator_bytes,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._rejected(query)
        if (
            candidate.declared_denominator_ref != candidate_denominator_ref
            or candidate.native_denominator_content_hash != candidate_denominator_ref
        ):
            return self._rejected(query)

        if truth.denominator_ref != candidate_denominator_ref:
            return self._denominator_mismatch(
                query=query,
                expected=truth.denominator_ref,
                observed=candidate_denominator_ref,
            )

        candidate_identities = tuple(
            contract.VerifiedNativeMemberIdentity(
                member_ref=member.member_ref,
                native_artifact_ref=member.native_artifact_ref,
                native_content_hash=member.native_content_hash,
                native_schema_profile=member.native_schema_profile,
                member_admission_basis_ref=member.member_admission_basis_ref,
                member_admission_context_ref=member.member_admission_context_ref,
            )
            for member in candidate.ordered_members
        )
        candidate_predicates = {
            ("member", row.member_ref, row.disposition.predicate_id): (
                row.disposition.predicate_class,
                row.disposition.status,
                row.disposition.failure_code,
                row.disposition.evidence_ref,
            )
            for row in candidate.member_predicates
        } | {
            (
                "query",
                row.requested_query_context_ref,
                row.disposition.predicate_id,
            ): (
                row.disposition.predicate_class,
                row.disposition.status,
                row.disposition.failure_code,
                row.disposition.evidence_ref,
            )
            for row in candidate.query_predicates
        }
        owner_predicates = {
            (statement.subject_kind, statement.subject_ref, statement.predicate_id): (
                statement.predicate_class,
                statement.status,
                statement.failure_code,
                verified.evidence_ref,
            )
            for statement, verified in zip(
                truth.predicate_statements,
                truth.predicate_evidence,
                strict=True,
            )
        }
        if (
            query != truth.query
            or candidate.query != truth.query
            or candidate.native_denominator_artifact_ref != truth.denominator_artifact_ref
            or candidate.native_denominator_content_hash != truth.denominator_content_hash
            or candidate.query_context_artifact_ref != truth.query_context_artifact_ref
            or candidate.query_context_content_hash != truth.query_context_content_hash
            or candidate_identities != truth.member_identities
            or candidate_predicates != owner_predicates
            or candidate.exterior_limitation_code != truth.exterior_limitation_code
            or candidate.native_authority_head_refs != truth.native_authority_head_refs
            or any(
                not self._stored_exact(member.native_artifact_ref, member.native_bytes)
                for member in candidate.ordered_members
            )
        ):
            return self._rejected(query)

        candidate_hash = contract._native_candidate_content_hash(candidate)

        return contract.VerifiedPredicatePolicyOwnerRelation(
            query=query,
            owner_relation_ref=self.owner_relation_ref,
            owner_relation_content_hash=self.owner_relation_content_hash,
            owner_verifier_provenance_ref=self.owner_verifier_ref,
            verification_receipt_ref=self.owner_receipt_ref,
            verification_receipt_content_hash=str(self.owner_receipt_ref.artifact_id),
            candidate_content_hash=candidate_hash,
            owner_declared_denominator_ref=truth.denominator_ref,
            candidate_declared_denominator_ref=candidate.declared_denominator_ref,
            owner_ordered_member_refs=tuple(
                member.member_ref for member in truth.member_identities
            ),
            candidate_ordered_member_refs=tuple(
                member.member_ref for member in candidate.ordered_members
            ),
            denominator_identity=contract.VerifiedNativeSubjectIdentity(
                subject_kind="denominator",
                subject_ref=truth.denominator_ref,
                artifact_ref=truth.denominator_artifact_ref,
                raw_cas_hash=str(truth.denominator_artifact_ref.artifact_id),
                semantic_content_hash=truth.denominator_content_hash,
                verifier_provenance_ref=self.owner_verifier_ref,
            ),
            query_context_identity=contract.VerifiedNativeSubjectIdentity(
                subject_kind="query_context",
                subject_ref=query.requested_query_context_ref,
                artifact_ref=truth.query_context_artifact_ref,
                raw_cas_hash=str(truth.query_context_artifact_ref.artifact_id),
                semantic_content_hash=truth.query_context_content_hash,
                verifier_provenance_ref=self.owner_verifier_ref,
            ),
            member_identities=truth.member_identities,
            predicate_evidence=truth.predicate_evidence,
            policy_owner_provenance=contract.VerifiedPolicyOwnerProvenance(
                policy_ref=policy.policy_ref,
                policy_content_hash=policy.policy_content_hash,
                owner_provenance_ref=self.policy_owner_provenance_ref,
                owner_provenance_content_hash=contract._sha256_digest(
                    self.policy_owner_provenance_bytes
                ),
                trust_snapshot_ref=self.trust_snapshot_ref,
                trust_snapshot_content_hash=str(self.trust_snapshot_ref.artifact_id),
                verification_receipt_ref=self.policy_owner_receipt_ref,
                verification_receipt_content_hash=str(self.policy_owner_receipt_ref.artifact_id),
                verifier_provenance_ref=self.owner_verifier_ref,
                predicate_class="independently_reconciled",
            ),
            predicate_class="independently_reconciled",
        )


@dataclass(slots=True)
class QualificationCase:
    store: FileSystemCAS
    query: contract.NativeChronologyQuery
    candidate: contract.NativeChronologyCandidate
    policy: contract.PersistedPredicateAdmissionPolicy
    admission_ref: ArtifactRef
    admission_index: _SingleAdmissionIndex
    owner_verifier: _FixtureOwnerVerifier
    adapter: EpochLikeQualificationAdapter | OpaqueInventoryQualificationAdapter
    owner_denominator_ref: contract.Digest

    def appoint_consumer(self) -> chronology_qualification.QualificationConsumer:
        registry = chronology_proof._PERSISTENCE_REGISTRY
        registry._appoint_for_test(
            store_factory=lambda: self.store,
            verifier_factory=FullPrefixVerifier,
            admission_index_factory=lambda: self.admission_index,
            owner_provenance_verifier_factory=lambda: self.owner_verifier,
        )
        return chronology_qualification.QualificationConsumer.from_current_owner_container()


def make_qualification_case(
    root: Path,
    *,
    shape: Literal["epoch", "inventory"],
    member_count: int,
    domain_override: contract.ChronologyProofDomain | None = None,
    requested_query_context_ref: contract.Digest | None = None,
    candidate_member_ordinals: tuple[int, ...] | None = None,
    required_native_head_role: str | None = None,
    native_authority_head_refs: tuple[contract.Digest, ...] | None = None,
    exterior_limitation_code: str | None = None,
    annotation_revision: int = 0,
    policy_profile: str | None = None,
    owner_native_profile: str | None = None,
    candidate_profile: str | None = None,
    predicate_class: contract.PredicateClass = "independently_reconciled",
    omit_query_predicate: bool = False,
    missing_owner_relation: bool = False,
    include_novel_candidate_member: bool = False,
) -> QualificationCase:
    store = FileSystemCAS(root)
    family = "epoch-like-fixture" if shape == "epoch" else "opaque-inventory-fixture"
    selected_profile = policy_profile or f"fixture.{shape}.native@1"
    authoritative_profile = owner_native_profile or selected_profile
    observed_profile = candidate_profile or authoritative_profile
    candidate_member_count = member_count + int(include_novel_candidate_member)
    candidate_ordinals = (
        tuple(range(candidate_member_count))
        if candidate_member_ordinals is None
        else candidate_member_ordinals
    )
    if len(candidate_ordinals) != len(set(candidate_ordinals)) or any(
        ordinal < 0 or ordinal >= candidate_member_count for ordinal in candidate_ordinals
    ):
        raise ValueError("candidate member ordinals must be unique available members")
    domain = domain_override or contract.ChronologyProofDomain(
        format=contract.FULL_PREFIX_FORMAT,
        profile=contract.FULL_PREFIX_PROFILE,
        proof_domain=f"{shape}-conformance",
        family=family,
        scope_ref=_digest(f"{shape}:scope"),
        authority_purpose="publication",
    )
    query = contract.NativeChronologyQuery(
        domain=domain,
        requested_cutoff_ref=_digest(f"{shape}:cutoff"),
        requested_query_context_ref=(
            requested_query_context_ref or _digest(f"{shape}:query-context")
        ),
    )
    key = contract.PredicatePolicySelectionKey(
        family=domain.family,
        proof_domain=domain.proof_domain,
        scope_ref=domain.scope_ref,
        authority_purpose=domain.authority_purpose,
        requested_cutoff_ref=query.requested_cutoff_ref,
    )
    member_rule = contract.PredicateAdmissionRule(
        predicate_id="owner_member_admitted",
        subject_kind="member",
        admitted_classes=("independently_reconciled",),
    )
    query_rule = contract.PredicateAdmissionRule(
        predicate_id="owner_denominator_complete",
        subject_kind="query",
        admitted_classes=("independently_reconciled",),
    )
    provenance_bytes = f"{shape}:owner-provenance:v1".encode()
    provenance_ref = _put_raw(
        store,
        provenance_bytes,
        kind="fixture.policy-owner-provenance",
    )
    policy_statement = contract.PredicateAdmissionPolicyStatement(
        schema_version="polisyos.chronology.predicate-policy.v1",
        key=key,
        native_schema_profile=selected_profile,
        required_native_head_role=required_native_head_role,
        rules=(member_rule, query_rule),
        owner_provenance_ref=provenance_ref,
        owner_provenance_content_hash=contract._sha256_digest(provenance_bytes),
    )
    policy_ref = _put_statement(
        store,
        policy_statement,
        kind="fixture.predicate-policy",
    )
    persisted_policy = contract.PersistedPredicateAdmissionPolicy(
        policy_ref=policy_ref,
        policy_content_hash=contract._predicate_policy_content_hash(policy_statement),
        statement=policy_statement,
    )

    owner_members: list[_NativeDenominatorMember] = []
    candidate_members: dict[int, contract.ChronologyMemberInput] = {}
    candidate_member_rows: dict[int, contract.MemberPredicateDisposition] = {}
    for ordinal in range(candidate_member_count):
        native_bytes = _native_bytes(
            shape=shape,
            ordinal=ordinal,
            annotation_revision=annotation_revision,
        )
        native_ref = _put_raw(store, native_bytes, kind=f"fixture.{shape}.member")
        member_ref = _digest(f"{shape}:member:{ordinal}")
        basis_ref = _digest(f"{shape}:basis:{ordinal}")
        context_ref = _digest(f"{shape}:context:{ordinal}")
        evidence_statement = _OwnerEvidenceStatement(
            schema_version="fixture.chronology.owner-evidence.v1",
            subject_kind="member",
            subject_ref=member_ref,
            predicate_id=member_rule.predicate_id,
            predicate_class=predicate_class,
            status="satisfied",
            failure_code=None,
        )
        evidence_ref = _put_raw(
            store,
            _model_bytes(evidence_statement),
            kind="fixture.owner-predicate-evidence",
        )
        if ordinal < member_count:
            owner_members.append(
                _NativeDenominatorMember(
                    member_ref=member_ref,
                    native_artifact_ref=native_ref,
                    native_content_hash=contract._native_content_hash(native_bytes),
                    native_schema_profile=authoritative_profile,
                    member_admission_basis_ref=basis_ref,
                    member_admission_context_ref=context_ref,
                    predicate_evidence_refs=(evidence_ref,),
                )
            )
        candidate_members[ordinal] = contract.ChronologyMemberInput(
            member_ref=member_ref,
            native_artifact_ref=native_ref,
            native_content_hash=contract._native_content_hash(native_bytes),
            native_schema_profile=observed_profile,
            native_bytes=native_bytes,
            member_admission_basis_ref=basis_ref,
            member_admission_context_ref=context_ref,
        )
        candidate_member_rows[ordinal] = contract.MemberPredicateDisposition(
            member_ref=member_ref,
            disposition=contract.PredicateDisposition(
                predicate_id=member_rule.predicate_id,
                predicate_class=predicate_class,
                status="satisfied",
                evidence_ref=evidence_ref,
                failure_code=None,
            ),
        )

    query_evidence_statement = _OwnerEvidenceStatement(
        schema_version="fixture.chronology.owner-evidence.v1",
        subject_kind="query",
        subject_ref=query.requested_query_context_ref,
        predicate_id=query_rule.predicate_id,
        predicate_class=predicate_class,
        status="satisfied",
        failure_code=None,
    )
    query_evidence_ref = _put_raw(
        store,
        _model_bytes(query_evidence_statement),
        kind="fixture.owner-predicate-evidence",
    )
    heads = native_authority_head_refs
    if heads is None:
        heads = (_digest("epoch:authority-head"),) if shape == "epoch" else ()

    owner_denominator = _NativeDenominatorStatement(
        schema_version="fixture.chronology.native-denominator.v1",
        family=domain.family,
        native_schema_profile=authoritative_profile,
        native_authority_head_refs=heads,
        members=tuple(owner_members),
    )
    owner_denominator_bytes = _model_bytes(owner_denominator)
    owner_denominator_artifact_ref = _put_raw(
        store,
        owner_denominator_bytes,
        kind="fixture.native-denominator",
    )
    owner_query_context = _OwnerQueryContextStatement(
        schema_version="fixture.chronology.owner-query-context.v1",
        query=query,
        exterior_limitation_code=exterior_limitation_code,
        predicate_evidence_refs=(query_evidence_ref,),
    )
    owner_query_context_bytes = _model_bytes(owner_query_context)
    owner_query_context_artifact_ref = _put_raw(
        store,
        owner_query_context_bytes,
        kind="fixture.native-query-context",
    )

    candidate_denominator_members = tuple(
        _NativeDenominatorMember(
            member_ref=candidate_members[ordinal].member_ref,
            native_artifact_ref=candidate_members[ordinal].native_artifact_ref,
            native_content_hash=candidate_members[ordinal].native_content_hash,
            native_schema_profile=candidate_members[ordinal].native_schema_profile,
            member_admission_basis_ref=(candidate_members[ordinal].member_admission_basis_ref),
            member_admission_context_ref=(candidate_members[ordinal].member_admission_context_ref),
            predicate_evidence_refs=(candidate_member_rows[ordinal].disposition.evidence_ref,),
        )
        for ordinal in candidate_ordinals
    )
    candidate_denominator = _NativeDenominatorStatement(
        schema_version="fixture.chronology.native-denominator.v1",
        family=domain.family,
        native_schema_profile=observed_profile,
        native_authority_head_refs=heads,
        members=candidate_denominator_members,
    )
    candidate_denominator_bytes = _model_bytes(candidate_denominator)
    candidate_denominator_artifact_ref = _put_raw(
        store,
        candidate_denominator_bytes,
        kind="fixture.native-denominator",
    )
    candidate_denominator_ref = contract._sha256_digest(
        _DENOMINATOR_PREFIX,
        candidate_denominator_bytes,
    )
    query_predicates = ()
    candidate_query_evidence_refs = ()
    if not omit_query_predicate:
        query_predicates = (
            contract.QueryPredicateDisposition(
                requested_query_context_ref=query.requested_query_context_ref,
                disposition=contract.PredicateDisposition(
                    predicate_id=query_rule.predicate_id,
                    predicate_class=predicate_class,
                    status="satisfied",
                    evidence_ref=query_evidence_ref,
                    failure_code=None,
                ),
            ),
        )
        candidate_query_evidence_refs = (query_evidence_ref,)
    candidate_query_context = _OwnerQueryContextStatement(
        schema_version="fixture.chronology.owner-query-context.v1",
        query=query,
        exterior_limitation_code=exterior_limitation_code,
        predicate_evidence_refs=candidate_query_evidence_refs,
    )
    candidate_query_context_bytes = _model_bytes(candidate_query_context)
    candidate_query_context_artifact_ref = _put_raw(
        store,
        candidate_query_context_bytes,
        kind="fixture.native-query-context",
    )

    candidate = contract.NativeChronologyCandidate(
        query=query,
        declared_denominator_ref=candidate_denominator_ref,
        native_denominator_artifact_ref=candidate_denominator_artifact_ref,
        native_denominator_content_hash=candidate_denominator_ref,
        query_context_artifact_ref=candidate_query_context_artifact_ref,
        query_context_content_hash=contract._sha256_digest(
            _QUERY_CONTEXT_PREFIX,
            candidate_query_context_bytes,
        ),
        ordered_members=tuple(candidate_members[ordinal] for ordinal in candidate_ordinals),
        member_predicates=tuple(candidate_member_rows[ordinal] for ordinal in candidate_ordinals),
        query_predicates=query_predicates,
        exterior_limitation_code=exterior_limitation_code,
        native_authority_head_refs=heads,
    )

    owner_relation = _OwnerRelationStatement(
        schema_version="fixture.chronology.owner-relation.v1",
        key=key,
        policy_ref=policy_ref,
        native_denominator_artifact_ref=owner_denominator_artifact_ref,
        query_context_artifact_ref=owner_query_context_artifact_ref,
    )
    owner_relation_bytes = _model_bytes(owner_relation)
    if missing_owner_relation:
        owner_relation_ref = ArtifactRef(
            artifact_id=ArtifactID.model_validate(_digest(f"{shape}:missing-relation")),
            kind="fixture.owner-relation",
            media_type="application/octet-stream",
        )
    else:
        owner_relation_ref = _put_raw(
            store,
            owner_relation_bytes,
            kind="fixture.owner-relation",
        )
    admission_statement = contract.PredicatePolicyAdmissionStatement(
        schema_version="polisyos.chronology.predicate-policy-admission.v1",
        key=key,
        requested_query_context_ref=query.requested_query_context_ref,
        native_schema_profile=selected_profile,
        policy_ref=policy_ref,
        policy_content_hash=persisted_policy.policy_content_hash,
        owner_relation_ref=owner_relation_ref,
        owner_relation_content_hash=contract._sha256_digest(owner_relation_bytes),
    )
    admission_ref = _put_statement(
        store,
        admission_statement,
        kind="fixture.predicate-policy-admission",
    )

    owner_receipt_bytes = f"{shape}:owner-verification-receipt".encode()
    owner_receipt_ref = _put_raw(
        store,
        owner_receipt_bytes,
        kind="fixture.owner-verification-receipt",
    )
    owner_verifier_ref = _put_raw(
        store,
        f"{shape}:owner-verifier".encode(),
        kind="fixture.owner-verifier-provenance",
    )
    trust_snapshot_ref = _put_raw(
        store,
        f"{shape}:trust-snapshot".encode(),
        kind="fixture.trust-snapshot",
    )
    policy_owner_receipt_ref = _put_raw(
        store,
        f"{shape}:policy-owner-receipt".encode(),
        kind="fixture.policy-owner-receipt",
    )
    evidence_verifier_ref = _put_raw(
        store,
        f"{shape}:evidence-verifier".encode(),
        kind="fixture.evidence-verifier",
    )
    failure_evidence_ref = _put_raw(
        store,
        f"{shape}:owner-rejection".encode(),
        kind="fixture.owner-rejection",
    )
    admission_index = _SingleAdmissionIndex(key=key, refs=(admission_ref,))
    owner_verifier = _FixtureOwnerVerifier(
        store=store,
        key=key,
        policy=persisted_policy,
        policy_owner_provenance_bytes=provenance_bytes,
        owner_relation_bytes=owner_relation_bytes,
        owner_relation_ref=owner_relation_ref,
        owner_relation_content_hash=contract._sha256_digest(owner_relation_bytes),
        owner_receipt_ref=owner_receipt_ref,
        owner_verifier_ref=owner_verifier_ref,
        policy_owner_provenance_ref=provenance_ref,
        trust_snapshot_ref=trust_snapshot_ref,
        policy_owner_receipt_ref=policy_owner_receipt_ref,
        evidence_verifier_ref=evidence_verifier_ref,
        failure_evidence_ref=failure_evidence_ref,
    )
    adapter: EpochLikeQualificationAdapter | OpaqueInventoryQualificationAdapter
    if shape == "epoch":
        adapter = EpochLikeQualificationAdapter(candidate=candidate)
    else:
        adapter = OpaqueInventoryQualificationAdapter(candidate=candidate)
    return QualificationCase(
        store=store,
        query=query,
        candidate=candidate,
        policy=persisted_policy,
        admission_ref=admission_ref,
        admission_index=admission_index,
        owner_verifier=owner_verifier,
        adapter=adapter,
        owner_denominator_ref=contract._sha256_digest(
            _DENOMINATOR_PREFIX,
            owner_denominator_bytes,
        ),
    )


__all__ = [
    "EpochLikeQualificationAdapter",
    "OpaqueInventoryQualificationAdapter",
    "QualificationCase",
    "make_qualification_case",
]
