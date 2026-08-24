"""Compose epoch anchor acceptance and custody without appointing an owner.

The production composition root is deliberately no-argument.  It installs no
acceptance authority and no holder; therefore it can preserve evidence for
both predicates while returning ``not_established`` for each one.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from polisyos.core import artifacts as core_artifacts
from polisyos.core import contracts as contract
from polisyos.core import security as chronology_security

ArtifactID = core_artifacts.ArtifactID
ArtifactRef = core_artifacts.ArtifactRef
InMemoryAnchorReadbackChallengeRepository = (
    chronology_security.InMemoryAnchorReadbackChallengeRepository
)
build_retention_package = chronology_security.build_retention_package
canonical_statement_bytes = chronology_security.canonical_statement_bytes
parse_canonical_statement = chronology_security.parse_canonical_statement
raw_content_hash = chronology_security.raw_content_hash
semantic_content_hash = chronology_security.semantic_content_hash

_MEDIA_TYPE = "application/octet-stream"


def _digest(label: str) -> contract.Digest:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _ref(label: str, *, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(_digest(label)),
        kind=kind,
        media_type=_MEDIA_TYPE,
    )


def _appointment_key(*, family: str, proof_domain: str, authority_purpose: str) -> contract.Digest:
    return _digest(f"epoch-anchor-appointment-key-v1:{family}:{proof_domain}:{authority_purpose}")


@dataclass(frozen=True, slots=True)
class NoEpochAnchorAppointmentResolver:
    """Production resolver whose result names both absent institutional roles."""

    resolver_provenance_ref: ArtifactRef = field(
        default_factory=lambda: _ref(
            "production-no-epoch-anchor-appointment-resolver-v1",
            kind="chronology.anchor_appointment_resolver",
        )
    )

    def resolve_epoch_appointments(
        self,
        *,
        family: Literal["epoch"],
        proof_domain: str,
        authority_purpose: str,
    ) -> contract.EpochAnchorAppointmentResolution:
        key = _appointment_key(
            family=family,
            proof_domain=proof_domain,
            authority_purpose=authority_purpose,
        )
        subject = _ref(
            f"epoch-anchor-appointment:{proof_domain}:{authority_purpose}",
            kind="chronology.anchor_appointment_key",
        )
        return contract.EpochAnchorAppointmentResolution(
            acceptance=contract.UnavailableAcceptanceAppointment(
                status="not_established",
                non_receipt=contract.AcceptanceUnavailableNonReceipt(
                    status="not_established",
                    component="acceptance",
                    code="anchor_acceptance_owner_not_established",
                    subject_artifact_ref=subject,
                    requested_query_context_ref=key,
                    appointment_key_ref=key,
                    resolved_appointment_ref=None,
                    appointment_evidence_ref=None,
                    resolver_provenance_ref=self.resolver_provenance_ref,
                    predicate_class="not_established",
                ),
            ),
            holder=contract.UnavailableHolderAppointment(
                status="not_established",
                non_receipt=contract.RetentionUnavailableNonReceipt(
                    status="not_established",
                    component="retention",
                    code="anchor_holder_not_established",
                    subject_artifact_ref=subject,
                    requested_query_context_ref=key,
                    appointment_key_ref=key,
                    resolved_appointment_ref=None,
                    appointment_evidence_ref=None,
                    resolver_provenance_ref=self.resolver_provenance_ref,
                    predicate_class="not_established",
                ),
            ),
        )


class EmptyEpochAnchorAuthorityRegistry:
    """Production registry with no acceptance/holder/verifier appointments."""

    _provenance = _ref(
        "production-empty-epoch-anchor-authority-registry-v1",
        kind="chronology.anchor_authority_registry",
    )

    @staticmethod
    def _query_ref(payload: bytes) -> contract.Digest:
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    def _acceptance_unavailable(
        self, appointment: contract.VerifiedAcceptanceVerifierAppointment
    ) -> contract.AcceptanceUnavailableNonReceipt:
        return contract.AcceptanceUnavailableNonReceipt(
            status="not_established",
            component="acceptance",
            code="anchor_acceptance_trust_not_established",
            subject_artifact_ref=appointment.appointment_ref,
            requested_query_context_ref=self._query_ref(appointment.statement_bytes),
            appointment_key_ref=self._query_ref(appointment.trust_config_bytes),
            resolved_appointment_ref=appointment.appointment_ref,
            appointment_evidence_ref=(
                appointment.signed_appointment_evidence.persisted.evidence_record_ref
            ),
            resolver_provenance_ref=self._provenance,
            predicate_class="not_established",
        )

    def _retention_unavailable(
        self, appointment: contract.VerifiedHolderVerifierAppointment
    ) -> contract.RetentionUnavailableNonReceipt:
        return contract.RetentionUnavailableNonReceipt(
            status="not_established",
            component="retention",
            code="anchor_holder_trust_not_established",
            subject_artifact_ref=appointment.appointment_ref,
            requested_query_context_ref=self._query_ref(appointment.statement_bytes),
            appointment_key_ref=self._query_ref(appointment.trust_config_bytes),
            resolved_appointment_ref=appointment.appointment_ref,
            appointment_evidence_ref=(
                appointment.signed_appointment_evidence.persisted.evidence_record_ref
            ),
            resolver_provenance_ref=self._provenance,
            predicate_class="not_established",
        )

    def resolve_acceptance_authority(
        self, *, appointment: contract.VerifiedAcceptanceVerifierAppointment
    ) -> contract.AcceptanceNonReceipt:
        return self._acceptance_unavailable(appointment)

    def resolve_holder(
        self, *, appointment: contract.VerifiedHolderVerifierAppointment
    ) -> contract.RetentionNonReceipt:
        return self._retention_unavailable(appointment)

    def resolve_acceptance_verifier(
        self, *, appointment: contract.VerifiedAcceptanceVerifierAppointment
    ) -> contract.AcceptanceNonReceipt:
        return self._acceptance_unavailable(appointment)

    def resolve_acceptance_lineage(
        self, *, appointment: contract.VerifiedAcceptanceVerifierAppointment
    ) -> contract.AcceptanceNonReceipt:
        return self._acceptance_unavailable(appointment)

    def resolve_holder_verifier(
        self, *, appointment: contract.VerifiedHolderVerifierAppointment
    ) -> contract.RetentionNonReceipt:
        return self._retention_unavailable(appointment)


class UnavailableSignedArtifactEvidenceRepository:
    """Deny-all issuance port used while no acceptance authority is appointed."""

    def persist_signed(self, **_: object) -> contract.PersistedSignedArtifactEvidence:
        raise RuntimeError("anchor_acceptance_owner_not_established")

    def read_exact(self, *, evidence_record_ref: ArtifactRef) -> contract.SignedArtifactEvidence:
        raise FileNotFoundError(str(evidence_record_ref.artifact_id))

    def read_raw(self, *, artifact_ref: ArtifactRef) -> bytes:
        raise FileNotFoundError(str(artifact_ref.artifact_id))


@dataclass(slots=True)
class EpochAnchorCustodyService:
    """Internal consumer that keeps acceptance and retention outcomes separate."""

    appointment_resolver: contract.EpochAnchorAppointmentResolver
    authority_registry: contract.EpochAnchorAuthorityRegistry
    issuance_evidence: contract.SignedArtifactEvidenceRepository
    challenge_repository: contract.AnchorReadbackChallengeRepository

    @staticmethod
    def _product(
        *,
        acceptance: contract.AcceptanceOutcome,
        retention: contract.RetentionOutcome,
    ) -> contract.AnchorCustodyVerification:
        pair = (acceptance.status, retention.status)
        status: Literal["verified", "limited", "rejected"] = (
            "rejected"
            if "rejected" in pair
            else "verified"
            if pair == ("verified", "verified")
            else "limited"
        )
        return contract.AnchorCustodyVerification(
            status=status,
            acceptance=acceptance,
            retention=retention,
        )

    def _unavailable_product(
        self,
        *,
        resolution: contract.EpochAnchorAppointmentResolution,
        requested_query_context_ref: contract.Digest,
        subject_artifact_ref: ArtifactRef,
    ) -> contract.AnchorCustodyVerification:
        if resolution.acceptance.status == "established":
            acceptance_nr = contract.AcceptanceUnavailableNonReceipt(
                status="not_established",
                component="acceptance",
                code="anchor_acceptance_trust_not_established",
                subject_artifact_ref=subject_artifact_ref,
                requested_query_context_ref=requested_query_context_ref,
                appointment_key_ref=_digest("unorchestrated-acceptance-appointment"),
                resolved_appointment_ref=resolution.acceptance.appointment.appointment_ref,
                appointment_evidence_ref=(
                    resolution.acceptance.appointment.signed_appointment_evidence.persisted.evidence_record_ref
                ),
                resolver_provenance_ref=_ref(
                    "production-epoch-custody-provider-v1",
                    kind="chronology.custody_provider",
                ),
                predicate_class="not_established",
            )
        else:
            acceptance_nr = resolution.acceptance.non_receipt.model_copy(
                update={
                    "subject_artifact_ref": subject_artifact_ref,
                    "requested_query_context_ref": requested_query_context_ref,
                }
            )
        if resolution.holder.status == "established":
            retention_nr = contract.RetentionUnavailableNonReceipt(
                status="not_established",
                component="retention",
                code="anchor_retention_not_established",
                subject_artifact_ref=subject_artifact_ref,
                requested_query_context_ref=requested_query_context_ref,
                appointment_key_ref=_digest("unorchestrated-holder-appointment"),
                resolved_appointment_ref=resolution.holder.appointment.appointment_ref,
                appointment_evidence_ref=(
                    resolution.holder.appointment.signed_appointment_evidence.persisted.evidence_record_ref
                ),
                resolver_provenance_ref=_ref(
                    "production-epoch-custody-provider-v1",
                    kind="chronology.custody_provider",
                ),
                predicate_class="not_established",
            )
        else:
            retention_nr = resolution.holder.non_receipt.model_copy(
                update={
                    "subject_artifact_ref": subject_artifact_ref,
                    "requested_query_context_ref": requested_query_context_ref,
                }
            )
        return self._product(
            acceptance=contract.UnavailableAcceptanceOutcome(
                status="not_established", non_receipts=(acceptance_nr,)
            ),
            retention=contract.UnavailableRetentionOutcome(
                status="not_established", non_receipts=(retention_nr,)
            ),
        )

    @staticmethod
    def _acceptance_outcome(
        value: contract.VerifiedAnchorAcceptance | contract.AcceptanceNonReceipt,
    ) -> contract.AcceptanceOutcome:
        if isinstance(value, contract.VerifiedAnchorAcceptance):
            return contract.VerifiedAcceptanceOutcome(status="verified", value=value)
        if isinstance(value, contract.AcceptanceUnavailableNonReceipt):
            return contract.UnavailableAcceptanceOutcome(
                status="not_established", non_receipts=(value,)
            )
        return contract.RejectedAcceptanceOutcome(status="rejected", rejections=(value,))

    @staticmethod
    def _retention_outcome(
        value: contract.VerifiedAnchorRetention | contract.RetentionNonReceipt,
    ) -> contract.RetentionOutcome:
        if isinstance(value, contract.VerifiedAnchorRetention):
            return contract.VerifiedRetentionOutcome(status="verified", value=value)
        if isinstance(value, contract.RetentionUnavailableNonReceipt):
            return contract.UnavailableRetentionOutcome(
                status="not_established", non_receipts=(value,)
            )
        return contract.RejectedRetentionOutcome(status="rejected", rejections=(value,))

    @staticmethod
    def _is_acceptance_non_receipt(value: object) -> bool:
        return isinstance(
            value,
            contract.AcceptanceUnavailableNonReceipt | contract.AcceptanceRejectedNonReceipt,
        )

    @staticmethod
    def _is_retention_non_receipt(value: object) -> bool:
        return isinstance(
            value,
            contract.RetentionUnavailableNonReceipt | contract.RetentionRejectedNonReceipt,
        )

    def _rebuild_acceptance_evidence(
        self,
        *,
        receipt: contract.AnchorAcceptanceReceipt,
        lineage: contract.AnchorAcceptanceLineageRepository,
    ) -> contract.AnchorAcceptanceEvidenceBundle:
        receipt_statement = parse_canonical_statement(
            receipt.statement_bytes, contract.AnchorAcceptanceReceiptStatement
        )
        candidate_bytes = self.issuance_evidence.read_raw(
            artifact_ref=receipt_statement.acceptance_record_ref
        )
        candidate = parse_canonical_statement(candidate_bytes, contract.AnchorAcceptanceRecord)
        statement_evidence = self.issuance_evidence.read_exact(
            evidence_record_ref=candidate.signed_statement_evidence_ref
        )
        statement = parse_canonical_statement(
            statement_evidence.blob_bytes, contract.AnchorAcceptanceStatement
        )
        key = contract.AnchorAcceptanceLineageKey(
            family="epoch",
            proof_domain=statement.parsed_header.proof_domain,
            scope_ref=statement.parsed_header.scope_ref,
            authority_purpose=statement.authority_purpose,
        )
        state = lineage.resolve_lineage(key=key)
        state_statement = parse_canonical_statement(
            state.statement_bytes, contract.AnchorAcceptanceLineageStateStatement
        )
        append_bytes: bytes | None = None
        for status in ("appended", "idempotent"):
            append_statement = contract.AnchorAcceptanceAppendSuccessStatement(
                status=status,
                key=key,
                expected_head_refs=candidate.prior_acceptance_record_refs,
                previous_head_refs=candidate.prior_acceptance_record_refs,
                resulting_head_refs=state_statement.current_record_refs,
                acceptance_record_ref=receipt_statement.acceptance_record_ref,
                resulting_state_content_hash=state.state_content_hash,
            )
            candidate_append_bytes = canonical_statement_bytes(append_statement)
            if str(receipt_statement.lineage_append_receipt_ref.artifact_id) == raw_content_hash(
                candidate_append_bytes
            ) and receipt_statement.lineage_append_receipt_content_hash == semantic_content_hash(
                "anchor-lineage-append.v1", candidate_append_bytes
            ):
                append_bytes = candidate_append_bytes
                break
        if append_bytes is None:
            raise ValueError("lineage append receipt cannot be rebuilt from owner state")
        return contract.AnchorAcceptanceEvidenceBundle(
            acceptance_statement_evidence=statement_evidence,
            acceptance_record_bytes=candidate_bytes,
            acceptance_receipt_bytes=receipt.statement_bytes,
            acceptance_receipt_signed_evidence=receipt.signed_receipt_evidence,
            lineage_append_receipt_bytes=append_bytes,
        )

    def _acceptance_failure(
        self,
        *,
        request: contract.AnchorAcceptanceRequest,
        appointment: contract.VerifiedAcceptanceVerifierAppointment,
    ) -> contract.AcceptanceRejectedNonReceipt:
        return contract.AcceptanceRejectedNonReceipt(
            status="rejected",
            component="acceptance",
            code="anchor_query_or_lineage_mismatch",
            subject_artifact_ref=request.bundle_ref,
            requested_query_context_ref=request.requested_query_context_ref,
            appointment_ref=appointment.appointment_ref,
            verifier_provenance_ref=_ref(
                "epoch-acceptance-evidence-rebuilder-v1",
                kind="chronology.acceptance_verifier",
            ),
            decisive_evidence_refs=(
                appointment.signed_appointment_evidence.persisted.evidence_record_ref,
            ),
            predicate_class="independently_reconciled",
        )

    def _verify_acceptance(
        self,
        *,
        request: contract.AnchorAcceptanceRequest,
        appointment: contract.VerifiedAcceptanceVerifierAppointment,
    ) -> tuple[
        contract.AcceptanceOutcome,
        contract.AnchorAcceptanceReceipt | None,
        contract.AnchorAcceptanceEvidenceBundle | None,
    ]:
        authority = self.authority_registry.resolve_acceptance_authority(appointment=appointment)
        verifier = self.authority_registry.resolve_acceptance_verifier(appointment=appointment)
        lineage = self.authority_registry.resolve_acceptance_lineage(appointment=appointment)
        for component in (authority, verifier, lineage):
            if self._is_acceptance_non_receipt(component):
                return self._acceptance_outcome(component), None, None
        receipt = authority.recompute_and_accept(request)
        if self._is_acceptance_non_receipt(receipt):
            return self._acceptance_outcome(receipt), None, None
        try:
            evidence = self._rebuild_acceptance_evidence(
                receipt=receipt,
                lineage=lineage,
            )
        except (FileNotFoundError, KeyError, OSError, TypeError, ValueError):
            failure = self._acceptance_failure(request=request, appointment=appointment)
            return self._acceptance_outcome(failure), None, None
        verified = verifier.verify(
            receipt=receipt,
            appointment=appointment,
            evidence=evidence,
            lineage=lineage,
            requested_query_context_ref=request.requested_query_context_ref,
        )
        return self._acceptance_outcome(verified), receipt, evidence

    def _missing_retention(
        self,
        *,
        appointment: contract.VerifiedHolderVerifierAppointment,
        request: contract.AnchorAcceptanceRequest,
    ) -> contract.RetentionUnavailableNonReceipt:
        return contract.RetentionUnavailableNonReceipt(
            status="not_established",
            component="retention",
            code="anchor_retention_not_established",
            subject_artifact_ref=request.bundle_ref,
            requested_query_context_ref=request.requested_query_context_ref,
            appointment_key_ref=_digest("accepted-anchor-required-before-retention"),
            resolved_appointment_ref=appointment.appointment_ref,
            appointment_evidence_ref=(
                appointment.signed_appointment_evidence.persisted.evidence_record_ref
            ),
            resolver_provenance_ref=_ref(
                "epoch-anchor-custody-service-v1", kind="chronology.custody_provider"
            ),
            predicate_class="not_established",
        )

    def _retain_verified_acceptance(
        self,
        *,
        request: contract.AnchorAcceptanceRequest,
        acceptance: contract.VerifiedAnchorAcceptance,
        receipt: contract.AnchorAcceptanceReceipt,
        evidence: contract.AnchorAcceptanceEvidenceBundle,
        acceptance_appointment: contract.VerifiedAcceptanceVerifierAppointment,
        holder_appointment: contract.VerifiedHolderVerifierAppointment,
    ) -> contract.RetentionOutcome:
        holder = self.authority_registry.resolve_holder(appointment=holder_appointment)
        verifier = self.authority_registry.resolve_holder_verifier(appointment=holder_appointment)
        for component in (holder, verifier):
            if self._is_retention_non_receipt(component):
                return self._retention_outcome(component)
        try:
            bundle_bytes = self.issuance_evidence.read_raw(artifact_ref=request.bundle_ref)
            reconciliation_bytes = self.issuance_evidence.read_raw(
                artifact_ref=request.native_reconciliation_ref
            )
        except (FileNotFoundError, KeyError, OSError, TypeError, ValueError):
            return self._retention_outcome(
                self._missing_retention(appointment=holder_appointment, request=request)
            )
        retention_statement = contract.AnchorRetentionStatement(
            family="epoch",
            proof_domain=request.expected_domain.proof_domain,
            authority_purpose=request.authority_purpose,
            requested_query_context_ref=request.requested_query_context_ref,
            admission_cutoff_ref=acceptance.admission_cutoff_ref,
            bundle_ref=request.bundle_ref,
            bundle_content_hash=contract.chronology_bundle_content_hash(bundle_bytes),
            native_reconciliation_ref=request.native_reconciliation_ref,
            acceptance_receipt_ref=receipt.receipt_record_ref,
            acceptance_receipt_content_hash=receipt.receipt_record_content_hash,
            prior_acceptance_record_refs=acceptance.prior_acceptance_record_refs,
            acceptance_appointment_ref=acceptance_appointment.appointment_ref,
            acceptance_appointment_content_hash=(acceptance_appointment.appointment_content_hash),
            holder_appointment_ref=holder_appointment.appointment_ref,
            holder_appointment_content_hash=holder_appointment.appointment_content_hash,
        )
        package = build_retention_package(
            contract.AnchorRetentionObjectGraph(
                retention_statement_bytes=canonical_statement_bytes(retention_statement),
                bundle_bytes=bundle_bytes,
                native_reconciliation_bytes=reconciliation_bytes,
                acceptance_evidence=evidence,
                acceptance_appointment=acceptance_appointment,
                holder_appointment=holder_appointment,
            )
        )
        retained = holder.retain(package)
        if self._is_retention_non_receipt(retained):
            return self._retention_outcome(retained)
        challenge = self.challenge_repository.persist(
            contract.AnchorReadbackChallengeStatement(
                family="epoch",
                proof_domain=request.expected_domain.proof_domain,
                authority_purpose=request.authority_purpose,
                lineage_key=contract.AnchorAcceptanceLineageKey(
                    family="epoch",
                    proof_domain=request.expected_domain.proof_domain,
                    scope_ref=request.expected_domain.scope_ref,
                    authority_purpose=request.authority_purpose,
                ),
                holder_appointment_ref=holder_appointment.appointment_ref,
                package_ref=package.package_ref,
                expected_package_content_hash=package.package_content_hash,
                custody_receipt_record_ref=retained.receipt_record_ref,
                custody_receipt_record_raw_bytes_hash=(retained.receipt_record_raw_bytes_hash),
                expected_object_version_ref=parse_canonical_statement(
                    retained.statement_bytes, contract.AnchorCustodyReceiptStatement
                ).object_version_ref,
                requested_query_context_ref=request.requested_query_context_ref,
            )
        )
        readback = holder.readback(challenge)
        if self._is_retention_non_receipt(readback):
            return self._retention_outcome(readback)
        verified = verifier.verify_retention_and_readback(
            retention=retained,
            readback=readback,
            challenge=challenge,
            appointment=holder_appointment,
        )
        return self._retention_outcome(verified)

    def accept_retain_and_verify(
        self, *, request: contract.AnchorAcceptanceRequest
    ) -> contract.AnchorCustodyVerification:
        """Resolve both roles and verify every positive from independently loaded bytes."""

        resolution = self.appointment_resolver.resolve_epoch_appointments(
            family="epoch",
            proof_domain=request.expected_domain.proof_domain,
            authority_purpose=request.authority_purpose,
        )
        if resolution.acceptance.status == "not_established":
            acceptance = contract.UnavailableAcceptanceOutcome(
                status="not_established",
                non_receipts=(
                    resolution.acceptance.non_receipt.model_copy(
                        update={
                            "subject_artifact_ref": request.bundle_ref,
                            "requested_query_context_ref": (request.requested_query_context_ref),
                        }
                    ),
                ),
            )
            receipt = None
            evidence = None
        else:
            acceptance, receipt, evidence = self._verify_acceptance(
                request=request,
                appointment=resolution.acceptance.appointment,
            )
        if resolution.holder.status == "not_established":
            retention = contract.UnavailableRetentionOutcome(
                status="not_established",
                non_receipts=(
                    resolution.holder.non_receipt.model_copy(
                        update={
                            "subject_artifact_ref": request.bundle_ref,
                            "requested_query_context_ref": (request.requested_query_context_ref),
                        }
                    ),
                ),
            )
        elif (
            acceptance.status != "verified"
            or receipt is None
            or evidence is None
            or resolution.acceptance.status != "established"
        ):
            retention = self._retention_outcome(
                self._missing_retention(
                    appointment=resolution.holder.appointment,
                    request=request,
                )
            )
        else:
            retention = self._retain_verified_acceptance(
                request=request,
                acceptance=acceptance.value,
                receipt=receipt,
                evidence=evidence,
                acceptance_appointment=resolution.acceptance.appointment,
                holder_appointment=resolution.holder.appointment,
            )
        return self._product(acceptance=acceptance, retention=retention)

    def verify_retained_challenge(
        self, *, challenge_record_ref: ArtifactRef
    ) -> contract.AnchorCustodyVerification:
        """Reload a persisted challenge before resolving either appointment."""

        try:
            challenge = self.challenge_repository.resolve(challenge_record_ref=challenge_record_ref)
            statement = parse_canonical_statement(
                challenge.statement_bytes, contract.AnchorReadbackChallengeStatement
            )
            proof_domain = statement.proof_domain
            purpose = statement.authority_purpose
            query_ref = statement.requested_query_context_ref
        except (FileNotFoundError, IndexError, ValueError):
            proof_domain = "unresolved"
            purpose = "unresolved"
            query_ref = _digest(f"challenge:{challenge_record_ref.artifact_id}")
            challenge = None
        resolution = self.appointment_resolver.resolve_epoch_appointments(
            family="epoch",
            proof_domain=proof_domain,
            authority_purpose=purpose,
        )
        if challenge is None or resolution.holder.status == "not_established":
            return self._unavailable_product(
                resolution=resolution,
                requested_query_context_ref=query_ref,
                subject_artifact_ref=challenge_record_ref,
            )
        holder = self.authority_registry.resolve_holder(appointment=resolution.holder.appointment)
        verifier = self.authority_registry.resolve_holder_verifier(
            appointment=resolution.holder.appointment
        )
        for component in (holder, verifier):
            if self._is_retention_non_receipt(component):
                retention = self._retention_outcome(component)
                break
        else:
            readback = holder.readback(challenge)
            if self._is_retention_non_receipt(readback):
                retention = self._retention_outcome(readback)
            else:
                retention = self._retention_outcome(
                    verifier.verify_retention_and_readback(
                        retention=readback.retention_receipt,
                        readback=readback,
                        challenge=challenge,
                        appointment=resolution.holder.appointment,
                    )
                )
        if resolution.acceptance.status == "not_established":
            acceptance = contract.UnavailableAcceptanceOutcome(
                status="not_established",
                non_receipts=(resolution.acceptance.non_receipt,),
            )
        else:
            acceptance = contract.UnavailableAcceptanceOutcome(
                status="not_established",
                non_receipts=(
                    contract.AcceptanceUnavailableNonReceipt(
                        status="not_established",
                        component="acceptance",
                        code="anchor_acceptance_trust_not_established",
                        subject_artifact_ref=challenge_record_ref,
                        requested_query_context_ref=query_ref,
                        appointment_key_ref=_digest(
                            "retained-challenge-acceptance-replay-unavailable"
                        ),
                        resolved_appointment_ref=(
                            resolution.acceptance.appointment.appointment_ref
                        ),
                        appointment_evidence_ref=(
                            resolution.acceptance.appointment.signed_appointment_evidence.persisted.evidence_record_ref
                        ),
                        resolver_provenance_ref=_ref(
                            "epoch-anchor-custody-service-v1",
                            kind="chronology.custody_provider",
                        ),
                        predicate_class="not_established",
                    ),
                ),
            )
        return self._product(acceptance=acceptance, retention=retention)

    def evaluate_acceptance_and_custody(
        self, *, request: contract.AnchorAcceptanceRequest
    ) -> contract.AnchorCustodyVerification:
        return self.accept_retain_and_verify(request=request)

    def evaluate_retained_challenge(
        self, *, challenge_record_ref: ArtifactRef
    ) -> contract.AnchorCustodyVerification:
        return self.verify_retained_challenge(challenge_record_ref=challenge_record_ref)


def build_production_epoch_anchor_custody_provider() -> contract.EpochAnchorCustodyProvider:
    """Build the sole production provider with both institutional roles absent."""

    return EpochAnchorCustodyService(
        appointment_resolver=NoEpochAnchorAppointmentResolver(),
        authority_registry=EmptyEpochAnchorAuthorityRegistry(),
        issuance_evidence=UnavailableSignedArtifactEvidenceRepository(),
        challenge_repository=InMemoryAnchorReadbackChallengeRepository(),
    )


__all__ = ["build_production_epoch_anchor_custody_provider"]
