"""Persist and reconcile attempted-evaluation safety authority artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon
from polisyos.pdc import ArtifactRef as EvalSafetyArtifactRef
from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.http.services.control.artifacts import (
    AuthorityArtifactIdentityContext,
    AuthorityArtifactWriteResult,
    verify_runtime_authority_artifact_identity,
    write_runtime_authority_artifact,
)
from polisyos.runtime.quality.authority import (
    EvidenceAuthorityEnvelope,
    GovernanceMetadata,
    SameInputClosure,
)
from polisyos.runtime.quality.authority_reconciliation import (
    AuthorityReconciliationError,
    reconcile_authority_ref,
)
from polisyos.runtime.quality.evaluation_safety import (
    EVALUATION_SAFETY_ARTIFACT_IDENTITIES,
    DomainEvalSafetyPack,
    EvalSafetyAdmissionChallenge,
    EvalSafetyAuthorityResolver,
    EvalSafetyAuthoritySurfacePacket,
    EvalSafetyCertificate,
    EvalSafetyCertificateRevision,
    EvalSafetyCertificateRevisionNode,
    EvalSafetyConsumerAdmissionReceipt,
    EvalSafetyMetricsProjection,
    EvalSafetyModeBasis,
    EvalSafetyNearMissClassificationOffer,
    EvalSafetyPackAdmissionReceipt,
    EvalSafetyRequirementResult,
    EvalSafetySurfaceDisposition,
    EvalSafetyVerifierAppointmentResolver,
    EvalSafetyVerifierRegistry,
    EvaluationAttemptIntake,
    EvaluationAttemptRequest,
    EvaluationExecutionContext,
    EvaluationSafetyArtifactIdentity,
    EvaluationSafetyDecisionCore,
    EvaluationSafetyDecisionEvent,
    EvaluationSafetyProjectionReadIdentity,
    VerifiedNearMissClassification,
    admit_domain_evaluation_safety_pack,
    build_evaluation_safety_certificate,
    build_evaluation_safety_decision_event,
    decide_evaluation_safety_core,
    evaluation_execution_context_hash,
    evaluation_safety_metrics_projection_identity,
    reconcile_evaluation_safety_revisions,
    replay_evaluation_safety_authority,
    verify_evaluation_safety_consumer_admission,
    verify_evaluation_safety_mode_basis,
    verify_evaluation_safety_requirements,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.semantic_epoch import (
        SemanticFacetDenominatorReceipt,
        SemanticFacetRegistry,
    )

_PRODUCER_COMPONENT = "polisyos.runtime.http.control.evaluation_safety"
_PRODUCER_VERSION = "1.0.0"


class EvaluationSafetyPersistenceContext(BaseModel):
    """Closed authority-writer context for one attempted-evaluation chain."""

    tenant_id: str
    cell_id: str | None
    run_id: str
    job_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    requested_execution_profile: str
    effective_execution_profile: str
    phase: str
    generated_at: datetime
    as_of_time: datetime
    same_input_closure: SameInputClosure
    effective_mode_ref: str
    governance: GovernanceMetadata

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class PersistedEvaluationSafetyDecision:
    """Actual CAS identities for one persisted decision."""

    decision_ref: EvalSafetyArtifactRef
    diagnostic_event_ref: EvalSafetyArtifactRef
    decision: EvaluationSafetyDecisionEvent


@dataclass(frozen=True, slots=True)
class EvaluationSafetyEvidenceBinding:
    """Exact evidence-contract binding supplied to appointed C01 verifiers."""

    evidence_contract_id: str
    evidence_ref: EvalSafetyArtifactRef


@dataclass(frozen=True, slots=True)
class EvaluationSafetyAttemptAuthorities:
    """Closed authority inputs needed to compose one attempted-evaluation decision."""

    mode_basis_ref: EvalSafetyArtifactRef | None
    mode_basis: EvalSafetyModeBasis | None
    pack_ref: EvalSafetyArtifactRef | None
    pack: DomainEvalSafetyPack | None
    semantic_facet_denominator_receipt_ref: EvalSafetyArtifactRef | None
    facet_registry: SemanticFacetRegistry | None
    facet_denominator: SemanticFacetDenominatorReceipt | None
    authority_resolver: EvalSafetyAuthorityResolver
    appointment_resolver: EvalSafetyVerifierAppointmentResolver
    verifier_registry: EvalSafetyVerifierRegistry
    evidence: tuple[EvaluationSafetyEvidenceBinding, ...]
    classification_offer: EvalSafetyNearMissClassificationOffer | None
    classification: VerifiedNearMissClassification | None
    certificate_issue_cause_ref: EvalSafetyArtifactRef | None


@dataclass(frozen=True, slots=True)
class PersistedEvaluationSafetyAttempt:
    """Actual durable identities written for one attempted-evaluation chain."""

    intake_ref: EvalSafetyArtifactRef
    request_ref: EvalSafetyArtifactRef | None
    pack_admission_ref: EvalSafetyArtifactRef | None
    classification_offer_ref: EvalSafetyArtifactRef | None
    decision_ref: EvalSafetyArtifactRef
    certificate_ref: EvalSafetyArtifactRef | None
    revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...]
    decision: EvaluationSafetyDecisionEvent
    owner_evidence: EvaluationSafetyDecisionEvidence


@dataclass(frozen=True, slots=True)
class EvaluationSafetyDecisionEvidence:
    """Owner-produced decision evidence used for post-CAS reconciliation."""

    decision_ref: EvalSafetyArtifactRef
    decision: EvaluationSafetyDecisionEvent
    classification: VerifiedNearMissClassification | None


@dataclass(frozen=True, slots=True)
class _EvaluationSafetyOwnerState:
    """One canonical C01 owner composition shared by write and replay."""

    admitted_basis: EvalSafetyModeBasis | None
    admitted_pack: EvalSafetyPackAdmissionReceipt | None
    requirement_results: tuple[EvalSafetyRequirementResult, ...]
    core: EvaluationSafetyDecisionCore


@dataclass(frozen=True, slots=True)
class EvaluationSafetyReplayMaterial:
    """Explicit raw authority inputs for canonical post-CAS owner replay."""

    intake_ref: EvalSafetyArtifactRef
    request_ref: EvalSafetyArtifactRef | None
    mode_basis_ref: EvalSafetyArtifactRef | None
    mode_basis: EvalSafetyModeBasis | None
    pack_ref: EvalSafetyArtifactRef | None
    pack: DomainEvalSafetyPack | None
    facet_registry: SemanticFacetRegistry | None
    facet_denominator: SemanticFacetDenominatorReceipt | None
    authority_resolver: EvalSafetyAuthorityResolver
    appointment_resolver: EvalSafetyVerifierAppointmentResolver
    verifier_registry: EvalSafetyVerifierRegistry
    evidence: tuple[EvaluationSafetyEvidenceBinding, ...]
    classification: VerifiedNearMissClassification | None
    decision_ref: EvalSafetyArtifactRef
    certificate_ref: EvalSafetyArtifactRef | None
    revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...]
    decision_evaluated_at: datetime
    revalidated_at: datetime


class EvaluationSafetyCurrentStateResolver(Protocol):
    """Resolve the current raw replay material for one immediate consumer call."""

    def resolve(
        self, context: EvaluationExecutionContext
    ) -> EvaluationSafetyReplayMaterial | None:
        """Return the current explicit authority material for ``context``."""


@dataclass(frozen=True, slots=True)
class EvaluationSafetyDecisionReduction:
    """Complete decision-artifact denominator and honest counter reduction."""

    selected_refs: tuple[EvalSafetyArtifactRef, ...]
    reconciled_refs: tuple[EvalSafetyArtifactRef, ...]
    unreconciled_refs: tuple[EvalSafetyArtifactRef, ...]
    conflicting_refs: tuple[EvalSafetyArtifactRef, ...]
    denominator_decision_ids: tuple[str, ...]
    unsafe_attempt_blocked_count: int
    near_miss_count: int
    near_miss_classification_status: Literal["complete", "partial", "not_established"]
    unclassified_blocked_decision_ids: tuple[str, ...]
    reconciliation_status: Literal["complete", "not_established"]
    source_event_refs: tuple[EvalSafetyArtifactRef, ...]


@dataclass(frozen=True, slots=True)
class PersistedEvaluationSafetyProjection:
    """Strict informational projection and its actual CAS identity."""

    projection_ref: EvalSafetyArtifactRef
    projection: EvalSafetyMetricsProjection


class EvaluationSafetyPersistenceService:
    """Control-owned persistence adapter with no evaluation execution capability."""

    def __init__(
        self,
        *,
        artifact_store: core_artifacts.ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
    ) -> None:
        self._artifact_store = artifact_store
        self._event_log = event_log

    def compose_and_persist_attempt(
        self,
        *,
        intake: EvaluationAttemptIntake,
        authorities: EvaluationSafetyAttemptAuthorities,
        context: EvaluationSafetyPersistenceContext,
        evaluated_at: datetime,
    ) -> PersistedEvaluationSafetyAttempt:
        """Run the C01 owners and persist one complete audit-safe attempt chain."""

        intake_write = self._write(
            key="intake",
            payload=intake.model_dump(mode="json"),
            context=context,
            input_refs=intake.evaluation_input_refs,
            validation_status=(
                "pass" if intake.mode_resolution.status == "accepted" else "blocked"
            ),
            blocking_status=(
                "non_blocking"
                if intake.mode_resolution.status == "accepted"
                else "blocking"
            ),
        )
        intake_ref = self._verified_eval_ref(
            intake_write.cas_ref.artifact_id,
            key="intake",
            semantic_hash=str(intake_write.cas_ref.artifact_id),
            expected_context=intake_write.identity_context,
        )

        request: EvaluationAttemptRequest | None = None
        request_ref: EvalSafetyArtifactRef | None = None
        accepted_mode = intake.mode_resolution.canonical_mode
        if (
            intake.mode_resolution.status == "accepted"
            and accepted_mode is not None
            and accepted_mode != "simulate_only"
            and intake.domain_pack_ref is not None
            and intake.requested_rule_version is not None
            and authorities.semantic_facet_denominator_receipt_ref is not None
        ):
            request = EvaluationAttemptRequest(
                intake_ref=intake_ref,
                attempt_id=intake.attempt_id,
                evaluator_owner_id=intake.evaluator_owner_id,
                candidate_ref=intake.candidate_ref,
                world_model_record_ref=intake.world_model_record_ref,
                evaluation_mode=accepted_mode,
                domain_pack_ref=intake.domain_pack_ref,
                semantic_facet_denominator_receipt_ref=(
                    authorities.semantic_facet_denominator_receipt_ref
                ),
                target_population_scope_ref=intake.target_population_scope_ref,
                evaluation_input_refs=intake.evaluation_input_refs,
                evaluation_input_provenance=intake.evaluation_input_provenance,
                evidence_refs=intake.evidence_refs,
                requested_at=intake.requested_at,
                intended_start_at=intake.intended_start_at,
                rule_version=intake.requested_rule_version,
                external_executor_identity_ref=intake.external_executor_identity_ref,
            )
            request_write = self._write(
                key="request",
                payload=request.model_dump(mode="json"),
                context=context,
                input_refs=(intake_ref,),
                validation_status="pass",
                blocking_status="non_blocking",
            )
            request_ref = self._verified_eval_ref(
                request_write.cas_ref.artifact_id,
                key="request",
                semantic_hash=str(request_write.cas_ref.artifact_id),
                expected_context=request_write.identity_context,
            )

        owner_state = self._compose_owner_state(
            intake=intake,
            intake_ref=intake_ref,
            request=request,
            request_ref=request_ref,
            mode_basis_ref=authorities.mode_basis_ref,
            mode_basis=authorities.mode_basis,
            pack_ref=authorities.pack_ref,
            pack=authorities.pack,
            facet_registry=authorities.facet_registry,
            facet_denominator=authorities.facet_denominator,
            authority_resolver=authorities.authority_resolver,
            appointment_resolver=authorities.appointment_resolver,
            verifier_registry=authorities.verifier_registry,
            evidence=authorities.evidence,
            authority_verified_at=evaluated_at,
            evaluated_at=evaluated_at,
        )
        admitted_pack = owner_state.admitted_pack
        pack_admission_ref: EvalSafetyArtifactRef | None = None
        if admitted_pack is not None:
            pack_write = self._write(
                key="pack_admission",
                payload=admitted_pack.model_dump(mode="json"),
                context=context,
                input_refs=(request_ref,),
                validation_status=(
                    "pass" if admitted_pack.status == "admitted" else "blocked"
                ),
                blocking_status=(
                    "non_blocking"
                    if admitted_pack.status == "admitted"
                    else "blocking"
                ),
            )
            pack_admission_ref = self._verified_eval_ref(
                pack_write.cas_ref.artifact_id,
                key="pack_admission",
                semantic_hash=admitted_pack.content_hash,
                expected_context=pack_write.identity_context,
            )
        core = owner_state.core

        classification_offer_ref: EvalSafetyArtifactRef | None = None
        classification = authorities.classification
        if authorities.classification_offer is not None:
            offer = authorities.classification_offer
            offer_write = self._write(
                key="classification_offer",
                payload=offer.model_dump(mode="json"),
                context=context,
                input_refs=(),
                validation_status="pass",
                blocking_status="non_blocking",
            )
            classification_offer_ref = self._verified_eval_ref(
                offer_write.cas_ref.artifact_id,
                key="classification_offer",
                semantic_hash=offer.content_hash,
                expected_context=offer_write.identity_context,
            )
            if classification is not None and (
                not isinstance(classification, VerifiedNearMissClassification)
                or classification.offer_ref != classification_offer_ref
            ):
                classification = None
        elif classification is not None:
            classification = None

        persisted_decision = self.persist_decision(
            core=core,
            classification=classification,
            context=context,
        )
        certificate_ref: EvalSafetyArtifactRef | None = None
        revision_nodes: tuple[EvalSafetyCertificateRevisionNode, ...] = ()
        if core.certificate_eligible:
            if (
                request is None
                or request_ref is None
                or authorities.certificate_issue_cause_ref is None
            ):
                raise ValueError("eval_safety_certificate_issue_inputs_missing")
            certificate = build_evaluation_safety_certificate(
                core=core,
                request=request,
                request_ref=request_ref,
                decision=persisted_decision.decision,
                decision_ref=persisted_decision.decision_ref,
            )
            certificate_write = self._write(
                key="certificate",
                payload=certificate.model_dump(mode="json"),
                context=context,
                input_refs=(request_ref, persisted_decision.decision_ref),
                validation_status="pass",
                blocking_status="non_blocking",
            )
            certificate_ref = self._verified_eval_ref(
                certificate_write.cas_ref.artifact_id,
                key="certificate",
                semantic_hash=certificate.content_hash,
                expected_context=certificate_write.identity_context,
            )
            revision = EvalSafetyCertificateRevision.issue(
                revision_lineage_id=certificate.revision_lineage_id,
                certificate_ref=certificate_ref,
                verified_cause_ref=authorities.certificate_issue_cause_ref,
                cause_resolver=authorities.authority_resolver,
                effective_at=evaluated_at,
            )
            revision_nodes = self.persist_revision_chain(
                revisions=(revision,),
                cause_resolver=authorities.authority_resolver,
                context=context,
            )
        return PersistedEvaluationSafetyAttempt(
            intake_ref=intake_ref,
            request_ref=request_ref,
            pack_admission_ref=pack_admission_ref,
            classification_offer_ref=classification_offer_ref,
            decision_ref=persisted_decision.decision_ref,
            certificate_ref=certificate_ref,
            revision_nodes=revision_nodes,
            decision=persisted_decision.decision,
            owner_evidence=EvaluationSafetyDecisionEvidence(
                decision_ref=persisted_decision.decision_ref,
                decision=persisted_decision.decision,
                classification=classification,
            ),
        )

    def _compose_owner_state(
        self,
        *,
        intake: EvaluationAttemptIntake,
        intake_ref: EvalSafetyArtifactRef,
        request: EvaluationAttemptRequest | None,
        request_ref: EvalSafetyArtifactRef | None,
        mode_basis_ref: EvalSafetyArtifactRef | None,
        mode_basis: EvalSafetyModeBasis | None,
        pack_ref: EvalSafetyArtifactRef | None,
        pack: DomainEvalSafetyPack | None,
        facet_registry: SemanticFacetRegistry | None,
        facet_denominator: SemanticFacetDenominatorReceipt | None,
        authority_resolver: EvalSafetyAuthorityResolver,
        appointment_resolver: EvalSafetyVerifierAppointmentResolver,
        verifier_registry: EvalSafetyVerifierRegistry,
        evidence: tuple[EvaluationSafetyEvidenceBinding, ...],
        authority_verified_at: datetime,
        evaluated_at: datetime,
    ) -> _EvaluationSafetyOwnerState:
        admitted_basis: EvalSafetyModeBasis | None = None
        admitted_pack: EvalSafetyPackAdmissionReceipt | None = None
        results: tuple[EvalSafetyRequirementResult, ...] = ()
        if (
            request is not None
            and request_ref is not None
            and mode_basis_ref is not None
            and pack_ref is not None
        ):
            if mode_basis is not None:
                admitted_basis = verify_evaluation_safety_mode_basis(
                    basis_ref=mode_basis_ref,
                    basis=mode_basis,
                    authority_resolver=authority_resolver,
                    verified_at=authority_verified_at,
                )
            admitted_pack = admit_domain_evaluation_safety_pack(
                pack_ref=pack_ref,
                pack=pack,
                request=request,
                mode_basis_ref=mode_basis_ref,
                mode_basis=admitted_basis,
                facet_registry=facet_registry,
                facet_denominator=facet_denominator,
                appointment_resolver=appointment_resolver,
                verifier_registry=verifier_registry,
                admitted_at=authority_verified_at,
            )
            results = verify_evaluation_safety_requirements(
                request=request,
                request_ref=request_ref,
                admitted_pack=admitted_pack,
                evidence_by_contract=_evidence_map(evidence),
                appointment_resolver=appointment_resolver,
                verifier_registry=verifier_registry,
                evaluated_at=evaluated_at,
            )
        core = decide_evaluation_safety_core(
            intake=intake,
            intake_ref=intake_ref,
            request=request,
            request_ref=request_ref,
            admitted_pack=admitted_pack,
            mode_basis=admitted_basis,
            requirement_results=results,
            evaluated_at=evaluated_at,
        )
        return _EvaluationSafetyOwnerState(
            admitted_basis=admitted_basis,
            admitted_pack=admitted_pack,
            requirement_results=results,
            core=core,
        )

    def persist_decision(
        self,
        *,
        core: EvaluationSafetyDecisionCore,
        classification: VerifiedNearMissClassification | None,
        context: EvaluationSafetyPersistenceContext,
    ) -> PersistedEvaluationSafetyDecision:
        """Persist one owner-composed immutable decision event."""

        event = build_evaluation_safety_decision_event(
            core=core,
            classification=classification,
        )
        written = self._write(
            key="decision",
            payload=event.model_dump(mode="json"),
            context=context,
            input_refs=(core.intake_ref, *((core.request_ref,) if core.request_ref else ())),
            validation_status="pass" if event.safety.status == "passed" else "blocked",
            blocking_status=(
                "non_blocking" if event.safety.status == "passed" else "blocking"
            ),
        )
        decision_ref = self._verified_eval_ref(
            written.cas_ref.artifact_id,
            key="decision",
            semantic_hash=event.content_hash,
            expected_context=written.identity_context,
        )
        event_ref = self._verified_eval_ref(
            written.diagnostic_event_ref.artifact_id,
            key="decision",
            semantic_hash=str(written.diagnostic_event_ref.artifact_id),
            artifact_type="runtime_quality.diagnostic_event",
            schema_ref="polisyos.runtime.quality.diagnostic_event",
        )
        return PersistedEvaluationSafetyDecision(
            decision_ref=decision_ref,
            diagnostic_event_ref=event_ref,
            decision=event,
        )

    def persist_revision_chain(
        self,
        *,
        revisions: tuple[EvalSafetyCertificateRevision, ...],
        cause_resolver: EvalSafetyAuthorityResolver,
        context: EvaluationSafetyPersistenceContext,
    ) -> tuple[EvalSafetyCertificateRevisionNode, ...]:
        """Re-admit and persist one exact issue/supersede/revoke lineage."""

        produced = reconcile_evaluation_safety_revisions(
            revisions=revisions,
            cause_resolver=cause_resolver,
        )
        if len(produced) != len(revisions):
            raise ValueError("eval_safety_revision_chain_unreconciled")
        nodes: list[EvalSafetyCertificateRevisionNode] = []
        for revision in produced:
            if revision.predecessor_ref is not None and all(
                node.revision_ref != revision.predecessor_ref for node in nodes
            ):
                raise ValueError("eval_safety_revision_predecessor_unresolved")
            inputs = (revision.certificate_ref,) + (
                (revision.predecessor_ref,)
                if revision.predecessor_ref is not None
                else ()
            )
            written = self._write(
                key="certificate_revision",
                payload=revision.model_dump(mode="json"),
                context=context,
                input_refs=inputs,
                validation_status="pass",
                blocking_status=(
                    "blocking" if revision.action == "revoke" else "non_blocking"
                ),
            )
            revision_ref = self._verified_eval_ref(
                written.cas_ref.artifact_id,
                key="certificate_revision",
                semantic_hash=revision.content_hash,
                expected_context=written.identity_context,
            )
            nodes.append(
                EvalSafetyCertificateRevisionNode(
                    revision_ref=revision_ref,
                    revision=revision,
                )
            )
        return tuple(nodes)

    def reduce_decisions(
        self,
        *,
        evidence: tuple[EvaluationSafetyDecisionEvidence, ...],
    ) -> EvaluationSafetyDecisionReduction:
        """Reduce the complete exact decision-kind/schema CAS denominator."""

        evidence_by_ref: dict[
            tuple[str, str], list[EvaluationSafetyDecisionEvidence]
        ] = {}
        for row in evidence:
            rows = evidence_by_ref.setdefault(
                (row.decision_ref.artifact_id, row.decision_ref.content_hash), []
            )
            if row not in rows:
                rows.append(row)
        identity = EVALUATION_SAFETY_ARTIFACT_IDENTITIES["decision"]
        selected: list[EvalSafetyArtifactRef] = []
        reconciled: list[tuple[EvalSafetyArtifactRef, EvaluationSafetyDecisionEvent]] = []
        event_refs: list[EvalSafetyArtifactRef] = []
        for artifact_id in self._artifact_store.iter_artifact_ids():
            typed_id = core_artifacts.ArtifactID.model_validate(artifact_id)
            try:
                manifest = self._artifact_store.get_manifest(typed_id)
            except (OSError, TypeError, ValueError) as exc:
                raise ValueError("eval_safety_selection_not_established") from exc
            schema = manifest.artifact_schema
            if (
                manifest.kind != identity.kind
                or schema is None
                or schema.name != identity.schema
                or schema.version != "1.0"
            ):
                continue
            selected_ref = _eval_ref(
                typed_id,
                identity=identity,
                semantic_hash=str(typed_id),
            )
            selected.append(selected_ref)
            try:
                if not self._authority_envelope_is_exact(
                    artifact_id=typed_id,
                    identity=identity,
                ):
                    raise ValueError("eval_safety_authority_envelope_mismatch")
                report = reconcile_authority_ref(
                    artifact_store=self._artifact_store,
                    event_log=self._event_log,
                    cas_ref=str(typed_id),
                )
                payload = self._artifact_store.get_bytes(typed_id)
                decision = EvaluationSafetyDecisionEvent.model_validate(
                    canon.from_canonical_bytes(payload)
                )
                selected_ref = selected_ref.model_copy(
                    update={"content_hash": decision.content_hash}
                )
                selected[-1] = selected_ref
                owner_rows = evidence_by_ref.get(
                    (selected_ref.artifact_id, selected_ref.content_hash), []
                )
                if len(owner_rows) != 1:
                    raise ValueError("eval_safety_owner_recomposition_missing")
                owner_row = owner_rows[0]
                rebuilt = build_evaluation_safety_decision_event(
                    core=owner_row.decision.safety,
                    classification=owner_row.classification,
                )
                if (
                    rebuilt.model_dump(mode="json")
                    != owner_row.decision.model_dump(mode="json")
                    or rebuilt.model_dump(mode="json")
                    != decision.model_dump(mode="json")
                    or owner_row.decision_ref != selected_ref
                ):
                    raise ValueError("eval_safety_owner_recomposition_mismatch")
                producer = manifest.producer
                if (
                    producer is None
                    or str(producer.component) != _PRODUCER_COMPONENT
                    or producer.version != _PRODUCER_VERSION
                ):
                    raise ValueError("eval_safety_decision_producer_mismatch")
                reconciled.append((selected_ref, rebuilt))
                event_manifest = self._artifact_store.get_manifest(
                    core_artifacts.ArtifactID.model_validate(
                        self._artifact_store.get_manifest(typed_id).authority.diagnostic_event_ref
                    )
                )
                event_refs.append(
                    EvalSafetyArtifactRef(
                        artifact_id=str(event_manifest.artifact_id),
                        artifact_type=event_manifest.kind,
                        content_hash=str(event_manifest.artifact_id),
                        schema_ref=event_manifest.artifact_schema.name,
                        uri=f"cas://sha256/{event_manifest.artifact_id.hex}",
                        version=event_manifest.artifact_schema.version,
                    )
                )
                if report.status != "pass":
                    raise ValueError("eval_safety_reconciliation_not_established")
            except (AttributeError, AuthorityReconciliationError, TypeError, ValueError):
                continue
        by_id: dict[str, list[tuple[EvalSafetyArtifactRef, EvaluationSafetyDecisionEvent]]] = {}
        for row in reconciled:
            by_id.setdefault(row[1].decision_id, []).append(row)
        conflicts = {
            decision_id
            for decision_id, rows in by_id.items()
            if len({row.content_hash for _, row in rows}) > 1
        }
        conflicting_refs = tuple(
            ref for decision_id in conflicts for ref, _ in by_id[decision_id]
        )
        denominator = {
            decision_id: rows[0][1]
            for decision_id, rows in by_id.items()
            if decision_id not in conflicts
        }
        blocked = {
            decision_id: event
            for decision_id, event in denominator.items()
            if event.safety.attempt_class == "non_simulation"
            and event.safety.status == "blocked"
        }
        unclassified = tuple(
            sorted(
                decision_id
                for decision_id, event in blocked.items()
                if event.promotion_safe_facet is None
            )
        )
        classified_count = len(blocked) - len(unclassified)
        coverage: Literal["complete", "partial", "not_established"]
        if not blocked:
            coverage = "complete"
        elif classified_count == 0:
            coverage = "not_established"
        elif unclassified:
            coverage = "partial"
        else:
            coverage = "complete"
        reconciled_refs = tuple(ref for ref, _ in reconciled)
        selected_identities = {(ref.artifact_id, ref.content_hash) for ref in selected}
        reconciled_identities = {(ref.artifact_id, ref.content_hash) for ref in reconciled_refs}
        unreconciled_refs = tuple(
            ref
            for ref in selected
            if (ref.artifact_id, ref.content_hash) not in reconciled_identities
        )
        if unreconciled_refs or conflicting_refs:
            coverage = "not_established"
        complete = selected_identities == reconciled_identities and not conflicting_refs
        return EvaluationSafetyDecisionReduction(
            selected_refs=tuple(sorted(selected, key=lambda ref: ref.artifact_id)),
            reconciled_refs=tuple(sorted(reconciled_refs, key=lambda ref: ref.artifact_id)),
            unreconciled_refs=tuple(sorted(unreconciled_refs, key=lambda ref: ref.artifact_id)),
            conflicting_refs=tuple(sorted(conflicting_refs, key=lambda ref: ref.artifact_id)),
            denominator_decision_ids=tuple(sorted(denominator)),
            unsafe_attempt_blocked_count=len(blocked),
            near_miss_count=sum(event.near_miss for event in blocked.values()),
            near_miss_classification_status=coverage,
            unclassified_blocked_decision_ids=unclassified,
            reconciliation_status="complete" if complete else "not_established",
            source_event_refs=tuple(sorted(event_refs, key=lambda ref: ref.artifact_id)),
        )

    def reconcile_persisted_attempt(
        self,
        *,
        material: EvaluationSafetyReplayMaterial,
    ) -> EvaluationSafetyDecisionEvidence | None:
        """Resolve CAS bytes and re-run C01 owners without restoring private markers."""

        try:
            intake = self._read_model(
                material.intake_ref,
                key="intake",
                model_type=EvaluationAttemptIntake,
            )
            decision = self._read_model(
                material.decision_ref,
                key="decision",
                model_type=EvaluationSafetyDecisionEvent,
            )
            request = (
                self._read_model(
                    material.request_ref,
                    key="request",
                    model_type=EvaluationAttemptRequest,
                )
                if material.request_ref is not None
                else None
            )
        except (OSError, AuthorityReconciliationError, TypeError, ValueError):
            return None

        owner_state = self._compose_owner_state(
            intake=intake,
            intake_ref=material.intake_ref,
            request=request,
            request_ref=material.request_ref,
            mode_basis_ref=material.mode_basis_ref,
            mode_basis=material.mode_basis,
            pack_ref=material.pack_ref,
            pack=material.pack,
            facet_registry=material.facet_registry,
            facet_denominator=material.facet_denominator,
            authority_resolver=material.authority_resolver,
            appointment_resolver=material.appointment_resolver,
            verifier_registry=material.verifier_registry,
            evidence=material.evidence,
            authority_verified_at=material.revalidated_at,
            evaluated_at=material.decision_evaluated_at,
        )
        core = owner_state.core
        rebuilt = build_evaluation_safety_decision_event(
            core=core,
            classification=material.classification,
        )
        if (
            rebuilt.model_dump(mode="json") != decision.model_dump(mode="json")
            or rebuilt.content_hash != material.decision_ref.content_hash
        ):
            return None

        if not core.certificate_eligible:
            if material.certificate_ref is not None or material.revision_nodes:
                return None
            return EvaluationSafetyDecisionEvidence(
                decision_ref=material.decision_ref,
                decision=rebuilt,
                classification=material.classification,
            )
        if (
            request is None
            or material.request_ref is None
            or material.mode_basis_ref is None
            or material.mode_basis is None
            or material.pack_ref is None
            or material.pack is None
            or material.facet_registry is None
            or material.facet_denominator is None
            or material.certificate_ref is None
        ):
            return None
        try:
            certificate = self._read_model(
                material.certificate_ref,
                key="certificate",
                model_type=EvalSafetyCertificate,
            )
            for node in material.revision_nodes:
                persisted_revision = self._read_model(
                    node.revision_ref,
                    key="certificate_revision",
                    model_type=EvalSafetyCertificateRevision,
                )
                if persisted_revision.model_dump(mode="json") != node.revision.model_dump(
                    mode="json"
                ):
                    return None
        except (OSError, AuthorityReconciliationError, TypeError, ValueError):
            return None
        replay = replay_evaluation_safety_authority(
            intake_ref=material.intake_ref,
            intake=intake,
            request_ref=material.request_ref,
            request=request,
            mode_basis_ref=material.mode_basis_ref,
            mode_basis=material.mode_basis,
            pack_ref=material.pack_ref,
            pack=material.pack,
            facet_registry=material.facet_registry,
            facet_denominator=material.facet_denominator,
            authority_resolver=material.authority_resolver,
            appointment_resolver=material.appointment_resolver,
            verifier_registry=material.verifier_registry,
            evidence_by_contract=_evidence_map(material.evidence),
            classification=material.classification,
            decision_ref=material.decision_ref,
            decision=decision,
            certificate_ref=material.certificate_ref,
            certificate=certificate,
            revision_nodes=material.revision_nodes,
            decision_evaluated_at=material.decision_evaluated_at,
            revalidated_at=material.revalidated_at,
        )
        if replay is None:
            return None
        return EvaluationSafetyDecisionEvidence(
            decision_ref=material.decision_ref,
            decision=replay.decision,
            classification=material.classification,
        )

    def persist_metrics_projection(
        self,
        *,
        reduction: EvaluationSafetyDecisionReduction,
        context: EvaluationSafetyPersistenceContext,
        generated_at: datetime,
    ) -> PersistedEvaluationSafetyProjection:
        """Persist a strict informational projection of one complete CAS reduction."""

        boundary = AuthorityBoundary(
            boundary_id="eval_safety_metrics_projection_v1",
            authoritative_for=["runtime_closeout_authority", "dashboard_display"],
            may_not_use_for=[
                "attempted_evaluation_admission",
                "promotion",
                "evaluation_execution",
            ],
            source_authority="deterministic_producer",
            posture="advisory",
            rule_version_refs=["policyos.runtime.eval_safety.metrics_projection.v1"],
            evidence_kind="derivation",
            decision_grade="descriptive_only",
            known_limits=["informational_projection_only"],
        )
        denied = (
            "attempted_evaluation_admission",
            "promotion",
            "evaluation_execution",
        )
        surfaces = {
            surface: EvalSafetySurfaceDisposition(
                surface=surface,
                purpose=(
                    "dashboard_display"
                    if surface == "dashboard"
                    else "runtime_closeout_authority"
                ),
                status="allow",
                authority_result="informational_projection_only",
                consumed_boundary_id=boundary.boundary_id,
                projection_scope="faithful_eval_safety_projection",
                may_not_use_for=denied,
            )
            for surface in ("run", "artifact", "lineage", "dashboard")
        }
        packet = EvalSafetyAuthoritySurfacePacket(
            schema_version="policyos.runtime.eval_safety_surface_packet.v1",
            boundary=boundary,
            surfaces=surfaces,
        )
        projection = EvalSafetyMetricsProjection(
            attempt_disposition=(
                "blocked" if reduction.unsafe_attempt_blocked_count else "passed"
            ),
            selected_decision_artifact_refs=reduction.selected_refs,
            reconciled_decision_artifact_refs=reduction.reconciled_refs,
            unreconciled_decision_artifact_refs=reduction.unreconciled_refs,
            conflicting_decision_artifact_refs=reduction.conflicting_refs,
            denominator_decision_ids=reduction.denominator_decision_ids,
            unsafe_attempt_blocked_count=reduction.unsafe_attempt_blocked_count,
            near_miss_count=reduction.near_miss_count,
            near_miss_classification_status=reduction.near_miss_classification_status,
            unclassified_blocked_decision_ids=(
                reduction.unclassified_blocked_decision_ids
            ),
            reconciliation_status=reduction.reconciliation_status,
            generated_at=generated_at,
            source_event_refs=reduction.source_event_refs,
            authority_boundary=boundary,
            authority_surface_packet=packet,
        )
        written = self._write(
            key="metrics_projection",
            payload=projection.model_dump(mode="json"),
            context=context,
            input_refs=reduction.selected_refs,
            validation_status=(
                "pass" if reduction.reconciliation_status == "complete" else "blocked"
            ),
            blocking_status="non_blocking",
        )
        projection_ref = self._verified_eval_ref(
            written.cas_ref.artifact_id,
            key="metrics_projection",
            semantic_hash=str(written.cas_ref.artifact_id),
            expected_context=written.identity_context,
        )
        return PersistedEvaluationSafetyProjection(
            projection_ref=projection_ref,
            projection=projection,
        )

    def _authority_envelope_is_exact(
        self,
        *,
        artifact_id: core_artifacts.ArtifactID,
        identity: EvaluationSafetyArtifactIdentity,
    ) -> bool:
        manifest = self._artifact_store.get_manifest(artifact_id)
        authority = manifest.authority
        if authority is None:
            return False
        try:
            envelope_id = core_artifacts.ArtifactID.model_validate(
                authority.authority_envelope_ref
            )
            verification = self._artifact_store.verify(envelope_id)
            if not verification.ok:
                return False
            envelope = EvidenceAuthorityEnvelope.model_validate(
                canon.from_canonical_bytes(self._artifact_store.get_bytes(envelope_id))
            )
        except (TypeError, ValueError):
            return False
        return bool(
            envelope.artifact_ref == str(artifact_id)
            and envelope.cas_ref == str(artifact_id)
            and envelope.artifact_kind == identity.kind
            and envelope.payload_sha256 == manifest.integrity.sha256
            and envelope.schema_name == identity.schema
            and envelope.schema_version == "1.0"
            and envelope.producer_component == _PRODUCER_COMPONENT
            and envelope.producer_version == _PRODUCER_VERSION
            and envelope.reader_contract == identity.reader_contract
            and envelope.reader_contract_version == "1.0"
            and envelope.evidence_class == identity.evidence_class
            and envelope.authority_role == identity.authority_role
            and envelope.runtime_event_ref == authority.diagnostic_event_ref
        )

    def _read_model[
        ModelT: BaseModel
    ](
        self,
        artifact_ref: EvalSafetyArtifactRef,
        *,
        key: str,
        model_type: type[ModelT],
    ) -> ModelT:
        artifact_id = core_artifacts.ArtifactID.model_validate(artifact_ref.artifact_id)
        identity = EVALUATION_SAFETY_ARTIFACT_IDENTITIES[key]
        verification = self._artifact_store.verify(artifact_id)
        if not verification.ok:
            raise ValueError("eval_safety_cas_readback_failed")
        manifest = self._artifact_store.get_manifest(artifact_id)
        schema = manifest.artifact_schema
        if (
            manifest.kind != identity.kind
            or schema is None
            or schema.name != identity.schema
            or schema.version != "1.0"
            or not self._authority_envelope_is_exact(
                artifact_id=artifact_id,
                identity=identity,
            )
        ):
            raise ValueError("eval_safety_cas_identity_mismatch")
        reconcile_authority_ref(
            artifact_store=self._artifact_store,
            event_log=self._event_log,
            cas_ref=str(artifact_id),
        )
        result = model_type.model_validate(
            canon.from_canonical_bytes(self._artifact_store.get_bytes(artifact_id))
        )
        embedded_hash = getattr(result, "content_hash", None)
        expected_hash = embedded_hash if isinstance(embedded_hash, str) else str(artifact_id)
        if artifact_ref != _eval_ref(
            artifact_id,
            identity=identity,
            semantic_hash=expected_hash,
        ):
            raise ValueError("eval_safety_cas_ref_binding_mismatch")
        return result

    def _write(
        self,
        *,
        key: str,
        payload: object,
        context: EvaluationSafetyPersistenceContext,
        input_refs: tuple[EvalSafetyArtifactRef, ...],
        validation_status: str,
        blocking_status: str,
    ) -> AuthorityArtifactWriteResult:
        identity = EVALUATION_SAFETY_ARTIFACT_IDENTITIES[key]
        return write_runtime_authority_artifact(
            self._artifact_store,
            self._event_log,
            payload,
            core_artifacts.ArtifactWriteOptions(
                kind=identity.kind,
                media_type="application/json",
                schema=core_artifacts.SchemaInfo(name=identity.schema, version="1.0"),
                producer=core_artifacts.ProducerInfo(
                    component=_PRODUCER_COMPONENT,
                    version=_PRODUCER_VERSION,
                ),
                inputs=[
                    core_artifacts.InputRef(
                        artifact_id=core_artifacts.ArtifactID.model_validate(ref.artifact_id),
                        role=key,
                    )
                    for ref in input_refs
                ],
            ),
            evidence_id=f"eval-safety-{key}",
            evidence_class=identity.evidence_class,
            authority_role=identity.authority_role,
            provenance_kind=(
                "runtime_projection"
                if key == "metrics_projection"
                else "runtime_emitted"
            ),
            owner="team-runtime",
            reader_contract=identity.reader_contract,
            reader_contract_version="1.0",
            tenant_id=context.tenant_id,
            cell_id=context.cell_id,
            run_id=context.run_id,
            job_id=context.job_id,
            trace_id=context.trace_id,
            span_id=context.span_id,
            parent_span_id=context.parent_span_id,
            requested_execution_profile=context.requested_execution_profile,
            effective_execution_profile=context.effective_execution_profile,
            phase=context.phase,
            generated_at=context.generated_at.isoformat(),
            as_of_time=context.as_of_time.isoformat(),
            same_input_closure=context.same_input_closure,
            input_refs=[ref.artifact_id for ref in input_refs],
            effective_mode_ref=context.effective_mode_ref,
            validation_status=validation_status,
            blocking_status=blocking_status,
            governance=context.governance,
        )

    def _verified_eval_ref(
        self,
        artifact_id: core_artifacts.ArtifactID,
        *,
        key: str,
        semantic_hash: str,
        expected_context: AuthorityArtifactIdentityContext | None = None,
        artifact_type: str | None = None,
        schema_ref: str | None = None,
    ) -> EvalSafetyArtifactRef:
        typed_id = core_artifacts.ArtifactID.model_validate(artifact_id)
        identity = EVALUATION_SAFETY_ARTIFACT_IDENTITIES[key]
        if artifact_type is not None or schema_ref is not None:
            verification = self._artifact_store.verify(typed_id)
            manifest = self._artifact_store.get_manifest(typed_id)
            manifest_schema = manifest.artifact_schema
            if (
                not verification.ok
                or manifest.kind != artifact_type
                or manifest_schema is None
                or manifest_schema.name != schema_ref
            ):
                raise ValueError("eval_safety_cas_readback_failed")
        else:
            if expected_context is None:
                raise ValueError("eval_safety_authority_identity_context_missing")
            verify_runtime_authority_artifact_identity(
                self._artifact_store,
                artifact_id=typed_id,
                opts=core_artifacts.ArtifactWriteOptions(
                    kind=identity.kind,
                    media_type="application/json",
                    schema=core_artifacts.SchemaInfo(
                        name=identity.schema,
                        version="1.0",
                    ),
                    producer=core_artifacts.ProducerInfo(
                        component=_PRODUCER_COMPONENT,
                        version=_PRODUCER_VERSION,
                    ),
                ),
                expected_context=expected_context,
            )
            model_types: dict[str, type[BaseModel]] = {
                "pack_admission": EvalSafetyPackAdmissionReceipt,
                "intake": EvaluationAttemptIntake,
                "request": EvaluationAttemptRequest,
                "classification_offer": EvalSafetyNearMissClassificationOffer,
                "decision": EvaluationSafetyDecisionEvent,
                "certificate": EvalSafetyCertificate,
                "certificate_revision": EvalSafetyCertificateRevision,
                "metrics_projection": EvalSafetyMetricsProjection,
            }
            parsed = model_types[key].model_validate(
                canon.from_canonical_bytes(self._artifact_store.get_bytes(typed_id))
            )
            embedded_hash = getattr(parsed, "content_hash", None)
            expected_semantic_hash = (
                embedded_hash if isinstance(embedded_hash, str) else str(typed_id)
            )
            if semantic_hash != expected_semantic_hash:
                raise ValueError("eval_safety_cas_semantic_hash_mismatch")
        return EvalSafetyArtifactRef(
            artifact_id=str(typed_id),
            artifact_type=artifact_type or identity.kind,
            content_hash=semantic_hash,
            schema_ref=schema_ref or identity.schema,
            uri=f"cas://sha256/{typed_id.hex}",
            version="1.0",
        )


class EvaluationSafetyAdmissionVerifier:
    """CAS-backed verification-only adapter for immediate evaluator admission."""

    def __init__(
        self,
        *,
        persistence_service: EvaluationSafetyPersistenceService,
        current_state_resolver: EvaluationSafetyCurrentStateResolver,
        authority_resolver: EvalSafetyAuthorityResolver,
        appointment_resolver: EvalSafetyVerifierAppointmentResolver,
        verifier_registry: EvalSafetyVerifierRegistry,
    ) -> None:
        self._persistence_service = persistence_service
        self._current_state_resolver = current_state_resolver
        self._authority_resolver = authority_resolver
        self._appointment_resolver = appointment_resolver
        self._verifier_registry = verifier_registry

    def require_admission(
        self,
        context: EvaluationExecutionContext,
        challenge: EvalSafetyAdmissionChallenge,
    ) -> EvalSafetyConsumerAdmissionReceipt:
        """Re-resolve CAS and C01 authority for this exact call and challenge."""

        verified_at = _utc_now()
        try:
            raw = self._current_state_resolver.resolve(context)
        except (OSError, AuthorityReconciliationError):
            return _blocked_consumer_receipt(
                context=context,
                challenge=challenge,
                verified_at=verified_at,
                blocker="polisyos.eval_safety.authority_replay_not_established@1.0.0",
            )
        if raw is None or context.eval_safety_certificate_ref is None:
            return _blocked_consumer_receipt(
                context=context,
                challenge=challenge,
                verified_at=verified_at,
                blocker="polisyos.eval_safety.authority_replay_not_established@1.0.0",
            )
        try:
            certificate = self._persistence_service._read_model(
                context.eval_safety_certificate_ref,
                key="certificate",
                model_type=EvalSafetyCertificate,
            )
            if (
                raw.intake_ref != context.intake_ref
                or raw.certificate_ref != context.eval_safety_certificate_ref
                or raw.request_ref != certificate.request_ref
                or raw.decision_ref != certificate.decision_ref
            ):
                raise ValueError("eval_safety_current_state_binding_mismatch")
            revision_nodes = self._complete_revision_nodes(certificate)
            material = replace(
                raw,
                authority_resolver=self._authority_resolver,
                appointment_resolver=self._appointment_resolver,
                verifier_registry=self._verifier_registry,
                revision_nodes=revision_nodes,
                decision_evaluated_at=self._decision_evaluated_at(
                    certificate.decision_ref
                ),
                revalidated_at=verified_at,
            )
            if material.request_ref is None:
                raise ValueError("eval_safety_authority_replay_not_established")
            intake = self._persistence_service._read_model(
                material.intake_ref,
                key="intake",
                model_type=EvaluationAttemptIntake,
            )
            request = self._persistence_service._read_model(
                material.request_ref,
                key="request",
                model_type=EvaluationAttemptRequest,
            )
        except (OSError, AuthorityReconciliationError, TypeError, ValueError):
            return _blocked_consumer_receipt(
                context=context,
                challenge=challenge,
                verified_at=verified_at,
                blocker="polisyos.eval_safety.authority_replay_not_established@1.0.0",
            )
        owner = self._persistence_service.reconcile_persisted_attempt(
            material=material
        )
        if owner is None:
            return _blocked_consumer_receipt(
                context=context,
                challenge=challenge,
                verified_at=verified_at,
                blocker="polisyos.eval_safety.authority_replay_not_established@1.0.0",
            )
        replay = replay_evaluation_safety_authority(
            intake_ref=material.intake_ref,
            intake=intake,
            request_ref=material.request_ref,
            request=request,
            mode_basis_ref=material.mode_basis_ref,  # type: ignore[arg-type]
            mode_basis=material.mode_basis,  # type: ignore[arg-type]
            pack_ref=material.pack_ref,  # type: ignore[arg-type]
            pack=material.pack,  # type: ignore[arg-type]
            facet_registry=material.facet_registry,  # type: ignore[arg-type]
            facet_denominator=material.facet_denominator,  # type: ignore[arg-type]
            authority_resolver=self._authority_resolver,
            appointment_resolver=self._appointment_resolver,
            verifier_registry=self._verifier_registry,
            evidence_by_contract=_evidence_map(material.evidence),
            classification=material.classification,
            decision_ref=material.decision_ref,
            decision=owner.decision,
            certificate_ref=context.eval_safety_certificate_ref,
            certificate=certificate,
            revision_nodes=revision_nodes,
            decision_evaluated_at=material.decision_evaluated_at,
            revalidated_at=verified_at,
        )
        if replay is None:
            return _blocked_consumer_receipt(
                context=context,
                challenge=challenge,
                verified_at=verified_at,
                blocker="polisyos.eval_safety.authority_replay_not_established@1.0.0",
            )
        return verify_evaluation_safety_consumer_admission(
            context=context,
            challenge=challenge,
            intake=intake,
            request=request,
            request_ref=material.request_ref,
            certificate_ref=context.eval_safety_certificate_ref,
            certificate=replay.certificate,
            decision_ref=material.decision_ref,
            decision=replay.decision,
            decision_core=replay.decision_core,
            revision_nodes=replay.revision_nodes,
            current_requirement_results=replay.current_requirement_results,
            verified_at=verified_at,
        )

    def _complete_revision_nodes(
        self, certificate: EvalSafetyCertificate
    ) -> tuple[EvalSafetyCertificateRevisionNode, ...]:
        identity = EVALUATION_SAFETY_ARTIFACT_IDENTITIES["certificate_revision"]
        nodes: list[EvalSafetyCertificateRevisionNode] = []
        for artifact_id in self._persistence_service._artifact_store.iter_artifact_ids():
            typed_id = core_artifacts.ArtifactID.model_validate(artifact_id)
            manifest = self._persistence_service._artifact_store.get_manifest(typed_id)
            schema = manifest.artifact_schema
            if (
                manifest.kind != identity.kind
                or schema is None
                or schema.name != identity.schema
                or schema.version != "1.0"
            ):
                continue
            raw = EvalSafetyCertificateRevision.model_validate(
                canon.from_canonical_bytes(
                    self._persistence_service._artifact_store.get_bytes(typed_id)
                )
            )
            if raw.revision_lineage_id != certificate.revision_lineage_id:
                continue
            revision_ref = _eval_ref(
                typed_id,
                identity=identity,
                semantic_hash=raw.content_hash,
            )
            persisted = self._persistence_service._read_model(
                revision_ref,
                key="certificate_revision",
                model_type=EvalSafetyCertificateRevision,
            )
            nodes.append(
                EvalSafetyCertificateRevisionNode(
                    revision_ref=revision_ref,
                    revision=persisted,
                )
            )
        return tuple(
            sorted(
                nodes,
                key=lambda node: (
                    node.revision.effective_at,
                    node.revision_ref.artifact_id,
                ),
            )
        )

    def _decision_evaluated_at(self, decision_ref: EvalSafetyArtifactRef) -> datetime:
        decision = self._persistence_service._read_model(
            decision_ref,
            key="decision",
            model_type=EvaluationSafetyDecisionEvent,
        )
        return decision.safety.evaluated_at


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _blocked_consumer_receipt(
    *,
    context: EvaluationExecutionContext,
    challenge: EvalSafetyAdmissionChallenge,
    verified_at: datetime,
    blocker: str,
) -> EvalSafetyConsumerAdmissionReceipt:
    return EvalSafetyConsumerAdmissionReceipt(
        status="blocked",
        intake_ref=context.intake_ref,
        certificate_ref=None,
        current_revision_head_ref=None,
        execution_context_hash=evaluation_execution_context_hash(context),
        challenge=challenge,
        blocker_codes=(blocker,),
        verified_at=verified_at,
    )


def _eval_ref(
    artifact_id: core_artifacts.ArtifactID,
    *,
    identity: EvaluationSafetyArtifactIdentity,
    semantic_hash: str,
) -> EvalSafetyArtifactRef:
    return EvalSafetyArtifactRef(
        artifact_id=str(artifact_id),
        artifact_type=identity.kind,
        content_hash=semantic_hash,
        schema_ref=identity.schema,
        uri=f"cas://sha256/{artifact_id.hex}",
        version="1.0",
    )


def _evidence_map(
    bindings: tuple[EvaluationSafetyEvidenceBinding, ...],
) -> dict[str, EvalSafetyArtifactRef]:
    """Build an exact evidence map, rejecting duplicate contract identities."""

    result: dict[str, EvalSafetyArtifactRef] = {}
    for binding in bindings:
        if binding.evidence_contract_id in result:
            raise ValueError("eval_safety_evidence_contract_duplicate")
        result[binding.evidence_contract_id] = binding.evidence_ref
    return result


__all__ = [
    "EVALUATION_SAFETY_ARTIFACT_IDENTITIES",
    "EvaluationSafetyAdmissionVerifier",
    "EvaluationSafetyArtifactIdentity",
    "EvaluationSafetyAttemptAuthorities",
    "EvaluationSafetyCurrentStateResolver",
    "EvaluationSafetyDecisionEvidence",
    "EvaluationSafetyDecisionReduction",
    "EvaluationSafetyEvidenceBinding",
    "EvaluationSafetyPersistenceContext",
    "EvaluationSafetyPersistenceService",
    "EvaluationSafetyProjectionReadIdentity",
    "EvaluationSafetyReplayMaterial",
    "PersistedEvaluationSafetyAttempt",
    "PersistedEvaluationSafetyDecision",
    "PersistedEvaluationSafetyProjection",
    "evaluation_safety_metrics_projection_identity",
]
