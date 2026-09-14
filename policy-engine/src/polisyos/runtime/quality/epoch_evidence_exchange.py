"""Exact evidence exchange adapters for configured chronology owner contracts.

These adapters read externally produced receipts.  They do not perform an
institutional act or create signatures.  Existing qualification and custody
consumers still reconcile the complete evidence before emitting authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from polisyos.core import artifacts, contracts, security

if TYPE_CHECKING:
    from polisyos.runtime.quality.chronology_custody import EmptyEpochAnchorAuthorityRegistry
    from polisyos.runtime.quality.epoch_deployment import (
        EpochAppointmentEvidenceConfig,
        EpochDeployment,
    )

contract = contracts.chronology
_READ_ERRORS = (KeyError, OSError, RuntimeError, TypeError, ValueError)


@dataclass(frozen=True, slots=True)
class EpochEvidenceExchange:
    """Resolve owner-configured exact policy evidence, never candidate selectors."""

    owner: EpochDeployment

    def enumerate_admission_refs(
        self,
        *,
        key: contract.PredicatePolicySelectionKey,
    ) -> tuple[artifacts.ArtifactRef, ...]:
        """Read every configured signed admission before selecting the exact key."""
        refs = []
        for ref in self.owner._state().config.predicate_policy_admission_refs:
            admission, record, _ = self.owner._signed_model(
                ref,
                contract.PredicatePolicyAdmissionStatement,
                "predicate_policy_admission",
            )
            if admission.key == key:
                refs.append(record.artifact_ref)
        return tuple(refs)

    def reconcile_candidate(
        self,
        request: contract.NativeChronologyQuery,
    ) -> contract.NativeChronologyCandidate:
        """Load a single query-bound candidate; its evidence is still unqualified."""
        candidates = [
            self.owner._read_model(ref, contract.NativeChronologyCandidate)
            for ref in self.owner._state().config.native_candidate_refs
        ]
        matches = [row for row in candidates if row.query == request]
        if len(matches) != 1:
            raise ValueError("native chronology candidate missing or ambiguous")
        return matches[0]

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
        """Resolve transport evidence and refuse absent native semantic verification.

        A signature establishes the receipt issuer. The shared DTO does not
        define the native denominator/query semantic hash domains or predicate
        evidence semantics. No production native verifier currently closes that
        link. A deployment may supply the actual native verifier implementation
        through its privileged typed slot; a signed receipt cannot fill it.
        """
        failure = contract.PolicyOwnerRelationNotEstablished(
            code="policy_owner_relation_not_established",
            status="not_established",
            key=admission.key,
            requested_query_context_ref=query.requested_query_context_ref,
            owner_relation_ref=admission.owner_relation_ref,
        )
        native_operation = self.owner._state().native_policy_operation
        if native_operation is not None:
            self.owner.attestation_state()
            return native_operation(
                query=query,
                admission=admission,
                policy=policy,
                policy_owner_provenance_bytes=policy_owner_provenance_bytes,
                owner_relation_bytes=owner_relation_bytes,
                candidate=candidate,
            )
        try:
            receipts = []
            for ref in self.owner._state().config.predicate_owner_verification_refs:
                receipt, record, _ = self.owner._signed_model(
                    ref,
                    contract.VerifiedPredicatePolicyOwnerRelation,
                    "predicate_owner_verification",
                )
                if (
                    receipt.query == query
                    and receipt.owner_relation_ref == admission.owner_relation_ref
                ):
                    if record.signer_provenance_ref != receipt.owner_verifier_provenance_ref:
                        return failure
                    receipts.append(receipt)
            if len(receipts) != 1:
                return failure
            receipt = receipts[0]
            repository = self.owner._repository()
            provenance = receipt.policy_owner_provenance
            if (
                receipt.owner_relation_content_hash != admission.owner_relation_content_hash
                or provenance.policy_ref != policy.policy_ref
                or provenance.policy_content_hash != policy.policy_content_hash
                or provenance.owner_provenance_ref != policy.statement.owner_provenance_ref
                or provenance.owner_provenance_content_hash
                != policy.statement.owner_provenance_content_hash
                or repository.read_raw(artifact_ref=admission.owner_relation_ref)
                != owner_relation_bytes
                or repository.read_raw(artifact_ref=provenance.owner_provenance_ref)
                != policy_owner_provenance_bytes
            ):
                return failure
            contract.OwnerQualifiedNativeCandidate(
                candidate=candidate,
                candidate_content_hash=receipt.candidate_content_hash,
                owner_relation_verification=receipt,
            )
            for identity in (receipt.denominator_identity, receipt.query_context_identity):
                payload = repository.read_raw(artifact_ref=identity.artifact_ref)
                if security.raw_content_hash(payload) != identity.raw_cas_hash:
                    return failure
            for member in candidate.ordered_members:
                if (
                    repository.read_raw(artifact_ref=member.native_artifact_ref)
                    != member.native_bytes
                ):
                    return failure
            # The signed verifier receipt names independently produced evidence.
            # Resolve all provenance/evidence bytes; missing material never admits.
            referenced = [
                receipt.owner_verifier_provenance_ref,
                receipt.verification_receipt_ref,
                provenance.trust_snapshot_ref,
                provenance.verification_receipt_ref,
                provenance.verifier_provenance_ref,
            ]
            for row in receipt.predicate_evidence:
                if row.evidence_ref is not None:
                    referenced.append(row.evidence_ref)
                if row.evidence_verifier_provenance_ref is not None:
                    referenced.append(row.evidence_verifier_provenance_ref)
            for ref in referenced:
                repository.read_raw(artifact_ref=ref)
            # These generic transport checks do not verify native predicates or
            # their semantic hash domains. Preserve the precise missing link;
            # neither the signature nor the DTO's class label can establish it.
            return failure
        except _READ_ERRORS:
            return failure

    def _appointment(
        self,
        configured: EpochAppointmentEvidenceConfig,
        role: Literal["acceptance", "holder"],
    ) -> (
        contract.VerifiedAcceptanceVerifierAppointment | contract.VerifiedHolderVerifierAppointment
    ):
        statement_type = (
            contract.AcceptanceVerifierAppointmentStatement
            if role == "acceptance"
            else contract.HolderVerifierAppointmentStatement
        )
        verification_type = (
            contract.AcceptanceAppointmentVerificationStatement
            if role == "acceptance"
            else contract.HolderAppointmentVerificationStatement
        )
        model_type = (
            contract.VerifiedAcceptanceVerifierAppointment
            if role == "acceptance"
            else contract.VerifiedHolderVerifierAppointment
        )
        trust_role = "acceptance_appointment" if role == "acceptance" else "holder_appointment"
        statement, record, evidence = self.owner._signed_model(
            configured.appointment_evidence_ref,
            statement_type,
            trust_role,
        )
        _, verification_record, verified_evidence = self.owner._signed_model(
            configured.verification_evidence_ref,
            verification_type,
            trust_role,
        )
        result = model_type(
            appointment_ref=record.artifact_ref,
            appointment_content_hash=security.semantic_content_hash(
                f"anchor-{role}-appointment.v1",
                evidence.blob_bytes,
            ),
            statement_bytes=evidence.blob_bytes,
            signed_appointment_evidence=evidence,
            trust_config_bytes=self.owner._repository().read_raw(
                artifact_ref=statement.trust_config_ref
            ),
            verification_statement_bytes=verified_evidence.blob_bytes,
            verification_receipt_ref=verification_record.artifact_ref,
            verification_receipt_content_hash=security.semantic_content_hash(
                f"anchor-{role}-appointment-verification.v1",
                verified_evidence.blob_bytes,
            ),
            signed_verification_evidence=verified_evidence,
        )
        verify = (
            security.verify_acceptance_appointment
            if role == "acceptance"
            else security.verify_holder_appointment
        )
        if not verify(result, verifier=self.owner._verifier(trust_role)):
            raise ValueError("configured epoch appointment verification failed")
        return result

    def resolve_epoch_appointments(
        self,
        *,
        family: Literal["epoch"],
        proof_domain: str,
        authority_purpose: str,
    ) -> contract.EpochAnchorAppointmentResolution:
        """Resolve each role independently, including absent and ambiguous evidence."""
        from polisyos.runtime.quality.chronology_custody import NoEpochAnchorAppointmentResolver

        empty = NoEpochAnchorAppointmentResolver().resolve_epoch_appointments(
            family=family,
            proof_domain=proof_domain,
            authority_purpose=authority_purpose,
        )
        values = {"acceptance": empty.acceptance, "holder": empty.holder}
        config = self.owner._state().config
        for role, rows in (
            ("acceptance", config.acceptance_appointments),
            ("holder", config.holder_appointments),
        ):
            try:
                matches = []
                for row in rows:
                    appointment = self._appointment(row, role)
                    model = (
                        contract.AcceptanceVerifierAppointmentStatement
                        if role == "acceptance"
                        else contract.HolderVerifierAppointmentStatement
                    )
                    statement = security.parse_canonical_statement(
                        appointment.statement_bytes, model
                    )
                    if (statement.family, statement.proof_domain, statement.authority_purpose) == (
                        family,
                        proof_domain,
                        authority_purpose,
                    ):
                        matches.append(appointment)
                if len(matches) == 1:
                    established = (
                        contract.EstablishedAcceptanceAppointment
                        if role == "acceptance"
                        else contract.EstablishedHolderAppointment
                    )
                    values[role] = established(status="established", appointment=matches[0])
            except _READ_ERRORS:
                pass
        return contract.EpochAnchorAppointmentResolution(**values)

    def _current(
        self,
        appointment: contract.VerifiedAcceptanceVerifierAppointment
        | contract.VerifiedHolderVerifierAppointment,
        role: Literal["acceptance", "holder"],
    ) -> bool:
        model = (
            contract.AcceptanceVerifierAppointmentStatement
            if role == "acceptance"
            else contract.HolderVerifierAppointmentStatement
        )
        try:
            statement = security.parse_canonical_statement(appointment.statement_bytes, model)
            resolved = self.resolve_epoch_appointments(
                family=statement.family,
                proof_domain=statement.proof_domain,
                authority_purpose=statement.authority_purpose,
            )
            value = getattr(resolved, role)
            return value.status == "established" and value.appointment == appointment
        except _READ_ERRORS:
            return False

    def resolve_acceptance_authority(
        self,
        *,
        appointment: contract.VerifiedAcceptanceVerifierAppointment,
    ) -> contract.ChronologyAcceptanceAuthority | contract.AcceptanceNonReceipt:
        """Provide the exact receipt exchange only for the resolved appointment."""
        if self._current(appointment, "acceptance"):
            return _AcceptanceExchange(self, appointment)
        return self._empty_registry().resolve_acceptance_authority(appointment=appointment)

    def resolve_holder(
        self,
        *,
        appointment: contract.VerifiedHolderVerifierAppointment,
    ) -> contract.AnchorHolder | contract.RetentionNonReceipt:
        """Provide the external holder receipt exchange for its resolved appointment."""
        if self._current(appointment, "holder"):
            return _HolderExchange(self, appointment)
        return self._empty_registry().resolve_holder(appointment=appointment)

    def resolve_acceptance_verifier(
        self,
        *,
        appointment: contract.VerifiedAcceptanceVerifierAppointment,
    ) -> contract.AnchorAcceptanceReceiptVerifier | contract.AcceptanceNonReceipt:
        """Reuse the complete acceptance verifier under pinned public trust."""
        if self._current(appointment, "acceptance"):
            return security.ExactAnchorAcceptanceReceiptVerifier(
                artifact_verifier=self.owner._verifier("acceptance_appointment"),
            )
        return self._empty_registry().resolve_acceptance_verifier(appointment=appointment)

    def resolve_holder_verifier(
        self,
        *,
        appointment: contract.VerifiedHolderVerifierAppointment,
    ) -> contract.AnchorHolderReceiptVerifier | contract.RetentionNonReceipt:
        """Reuse the complete holder verifier under pinned public trust."""
        if self._current(appointment, "holder"):
            return security.ExactAnchorHolderReceiptVerifier(
                artifact_verifier=self.owner._verifier("holder_appointment"),
            )
        return self._empty_registry().resolve_holder_verifier(appointment=appointment)

    def resolve_acceptance_lineage(
        self,
        *,
        appointment: contract.VerifiedAcceptanceVerifierAppointment,
    ) -> contract.AnchorAcceptanceLineageRepository | contract.AcceptanceNonReceipt:
        """Read the separately configured accepted lineage through its canonical owner."""
        root = self.owner._state().config.acceptance_lineage_root
        if self._current(appointment, "acceptance") and root is not None:
            return security.FileAnchorAcceptanceLineageRepository(root=root)
        return self._empty_registry().resolve_acceptance_lineage(appointment=appointment)

    @staticmethod
    def _empty_registry() -> EmptyEpochAnchorAuthorityRegistry:
        from polisyos.runtime.quality.chronology_custody import EmptyEpochAnchorAuthorityRegistry

        return EmptyEpochAnchorAuthorityRegistry()


@dataclass(frozen=True, slots=True)
class _AcceptanceExchange:
    exchange: EpochEvidenceExchange
    appointment: contract.VerifiedAcceptanceVerifierAppointment

    def recompute_and_accept(
        self,
        request: contract.AnchorAcceptanceRequest,
    ) -> contract.AnchorAcceptanceReceipt | contract.AcceptanceNonReceipt:
        try:
            matches = []
            for ref in self.exchange.owner._state().config.acceptance_receipt_refs:
                receipt = self.exchange.owner._read_model(ref, contract.AnchorAcceptanceReceipt)
                statement = security.parse_canonical_statement(
                    receipt.statement_bytes,
                    contract.AnchorAcceptanceReceiptStatement,
                )
                if statement.requested_query_context_ref == request.requested_query_context_ref:
                    evidence = self.exchange.owner._repository().read_exact(
                        evidence_record_ref=statement.signed_statement_evidence_ref,
                    )
                    acceptance = security.parse_canonical_statement(
                        evidence.blob_bytes,
                        contract.AnchorAcceptanceStatement,
                    )
                    header = acceptance.parsed_header
                    if (
                        acceptance.bundle_ref == request.bundle_ref
                        and acceptance.native_reconciliation_ref
                        == request.native_reconciliation_ref
                        and acceptance.authority_purpose == request.authority_purpose
                        and acceptance.prior_acceptance_record_refs
                        == request.asserted_prior_acceptance_record_refs
                        and all(
                            getattr(header, name) == getattr(request.expected_domain, name)
                            for name in type(request.expected_domain).model_fields
                        )
                    ):
                        matches.append(receipt)
            if len(matches) == 1:
                return matches[0]
        except _READ_ERRORS:
            pass
        return self.exchange._empty_registry().resolve_acceptance_authority(
            appointment=self.appointment
        )


@dataclass(frozen=True, slots=True)
class _HolderExchange:
    exchange: EpochEvidenceExchange
    appointment: contract.VerifiedHolderVerifierAppointment

    def retain(
        self, package: contract.AnchorRetentionPackage
    ) -> contract.AnchorCustodyReceipt | contract.RetentionNonReceipt:
        try:
            matches = []
            for ref in self.exchange.owner._state().config.retention_receipt_refs:
                receipt = self.exchange.owner._read_model(ref, contract.AnchorCustodyReceipt)
                statement = security.parse_canonical_statement(
                    receipt.statement_bytes, contract.AnchorCustodyReceiptStatement
                )
                if (
                    statement.package_ref == package.package_ref
                    and statement.package_content_hash == package.package_content_hash
                ):
                    matches.append(receipt)
            if len(matches) == 1:
                return matches[0]
        except _READ_ERRORS:
            pass
        return self.exchange._empty_registry().resolve_holder(appointment=self.appointment)

    def readback(
        self, challenge: contract.PersistedAnchorReadbackChallenge
    ) -> contract.AnchorReadbackReceipt | contract.RetentionNonReceipt:
        try:
            matches = []
            for ref in self.exchange.owner._state().config.readback_receipt_refs:
                receipt = self.exchange.owner._read_model(ref, contract.AnchorReadbackReceipt)
                statement = security.parse_canonical_statement(
                    receipt.statement_bytes, contract.AnchorReadbackReceiptStatement
                )
                if (
                    statement.challenge_record_ref == challenge.challenge_record_ref
                    and statement.challenge_record_content_hash
                    == challenge.challenge_record_content_hash
                ):
                    matches.append(receipt)
            if len(matches) == 1:
                return matches[0]
        except _READ_ERRORS:
            pass
        return self.exchange._empty_registry().resolve_holder(appointment=self.appointment)


@dataclass(frozen=True, slots=True)
class EpochReadbackChallengeRepository:
    """Persist and reload challenge statements through the configured exact CAS."""

    owner: EpochDeployment

    def persist(
        self, statement: contract.AnchorReadbackChallengeStatement
    ) -> contract.PersistedAnchorReadbackChallenge:
        store = self.owner._runtime_artifact_store()
        if store is None:
            raise ValueError("epoch challenge repository is unconfigured")
        challenge = security.InMemoryAnchorReadbackChallengeRepository().persist(statement)
        ref = store.put_bytes(
            challenge.statement_bytes,
            artifacts.ArtifactWriteOptions(
                kind=challenge.challenge_record_ref.kind,
                media_type=challenge.challenge_record_ref.media_type,
            ),
        )
        if ref != challenge.challenge_record_ref:
            raise ValueError("epoch readback challenge persistence mismatch")
        return self.resolve(challenge_record_ref=ref)

    def resolve(
        self, *, challenge_record_ref: artifacts.ArtifactRef
    ) -> contract.PersistedAnchorReadbackChallenge:
        raw = self.owner._runtime_repository().read_raw(artifact_ref=challenge_record_ref)
        security.parse_canonical_statement(raw, contract.AnchorReadbackChallengeStatement)
        return contract.PersistedAnchorReadbackChallenge(
            challenge_record_ref=challenge_record_ref,
            challenge_record_content_hash=security.semantic_content_hash(
                "anchor-readback-challenge.v1", raw
            ),
            statement_bytes=raw,
        )
