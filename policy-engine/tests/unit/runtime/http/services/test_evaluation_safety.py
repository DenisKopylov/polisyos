from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import components as core_components
from polisyos.core.artifacts import ArtifactID as CoreArtifactID
from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import content_hash as canonical_content_hash
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes
from polisyos.pdc import ArtifactRef, gy_content_hash
from polisyos.runtime.http.services.control import evaluation_safety as c02
from polisyos.runtime.http.services.control.evaluation_safety import (
    EvaluationSafetyAttemptAuthorities,
    EvaluationSafetyDecisionEvidence,
    EvaluationSafetyPersistenceContext,
    EvaluationSafetyPersistenceService,
    EvaluationSafetyReplayMaterial,
    evaluation_safety_metrics_projection_identity,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import evaluation_safety as es
from polisyos.runtime.quality import semantic_epoch
from polisyos.runtime.quality.authority import (
    GovernanceMetadata,
    SameInputClosure,
    authority_surface_decision,
)
from polisyos.runtime.quality.evaluation_modes import resolve_evaluation_mode
from polisyos.runtime.quality.evaluation_safety import (
    DomainEvalSafetyPack,
    EvalSafetyAllApplicability,
    EvalSafetyAppointmentResolution,
    EvalSafetyAuthorityResolution,
    EvalSafetyCertificate,
    EvalSafetyFacetApplicability,
    EvalSafetyFacetValueRequirement,
    EvalSafetyModeBasis,
    EvalSafetyModeProfile,
    EvalSafetyRequirement,
    EvaluationAttemptIntake,
    EvaluationInputProvenance,
    decide_evaluation_safety_core,
    evaluation_safety_core_bytes,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

_NOW = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)


def _ref(value: str, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=value,
        artifact_type=kind,
        content_hash=value,
        schema_ref=f"{kind}.v1",
        uri=f"cas://sha256/{value.removeprefix('sha256:')}",
        version="1.0",
    )


def _service(tmp_path) -> tuple[EvaluationSafetyPersistenceService, FileSystemCAS]:
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )
    return (
        EvaluationSafetyPersistenceService(
            artifact_store=artifact_store,
            event_log=event_log,
        ),
        artifact_store,
    )


def _context(source_ref: str) -> EvaluationSafetyPersistenceContext:
    return EvaluationSafetyPersistenceContext(
        tenant_id="tenant-1",
        cell_id="cell-a",
        run_id="run-eval-safety",
        job_id="job-eval-safety",
        trace_id="trace-eval-safety",
        span_id="span-eval-safety",
        parent_span_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        phase="evaluation_safety",
        generated_at=_NOW,
        as_of_time=_NOW,
        same_input_closure=SameInputClosure(
            closure_id="closure-eval-safety",
            status="closed",
            run_id="run-eval-safety",
            job_id="job-eval-safety",
            tenant_id="tenant-1",
            cell_id="cell-a",
            evidence_input_refs=(source_ref,),
            closure_sha256="1" * 64,
        ),
        effective_mode_ref="sha256:" + "2" * 64,
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
    )


@dataclass(frozen=True)
class _PassingFixture:
    service: EvaluationSafetyPersistenceService
    artifact_store: FileSystemCAS
    intake: EvaluationAttemptIntake
    authorities: EvaluationSafetyAttemptAuthorities
    persisted: object
    replay_material: EvaluationSafetyReplayMaterial
    execution_context: es.EvaluationExecutionContext
    authority_resolver: object
    appointment_resolver: object
    verifier_registry: object
    cause_bindings: dict[tuple[str, str], dict[str, object]]
    evaluated_at: datetime


def _core_ref(value: str, kind: str) -> CoreArtifactRef:
    return CoreArtifactRef(
        artifact_id=CoreArtifactID.model_validate(value),
        kind=kind,
        media_type="application/json",
    )


def _passing_fixture(
    tmp_path,
    *,
    evaluated_at: datetime | None = None,
    design_problem_ref: str | None = None,
) -> _PassingFixture:
    service, artifact_store = _service(tmp_path)
    evaluated_at = evaluated_at or (datetime.now(UTC) - timedelta(minutes=1))
    design_problem_ref = design_problem_ref or ("sha256:" + "0" * 64)
    source = artifact_store.put_json(
        {"input": "real-world"},
        opts=PutOptions(kind="test.eval-input", media_type="application/json"),
    )
    source_ref = _ref(str(source.artifact_id), "test.eval-input")
    registry = semantic_epoch.build_facet_registry(
        (
            semantic_epoch.SemanticFacetRegistration(
                facet_id="novel_domain.platform_type@1.0.0",
                source_binding_ref="sha256:" + "3" * 64,
            ),
        )
    )
    query = semantic_epoch.EpochResolutionQuery(
        scope_identity=semantic_epoch.build_epoch_scope_identity(
            schema_profile="novel-domain",
            identity_bytes=b"novel-domain-scope",
        ),
        authority_purpose="attempted_evaluation_safety",
        valid_effect_coordinate_evidence_ref=_core_ref(
            "sha256:" + "a" * 64, "test.effect-coordinate"
        ),
        valid_effect_coordinate_ref="sha256:" + "a" * 64,
        visibility_knowledge_cutoff_evidence_ref=_core_ref(
            "sha256:" + "b" * 64, "test.knowledge-cutoff"
        ),
        visibility_knowledge_cutoff_ref="sha256:" + "b" * 64,
        purpose_admission_cutoff_evidence_ref=_core_ref(
            "sha256:" + "c" * 64, "test.admission-cutoff"
        ),
        purpose_admission_cutoff_ref="sha256:" + "c" * 64,
        requested_query_context_ref="sha256:" + "d" * 64,
    )
    facet_value = semantic_epoch.SemanticFacetValue(
        facet_id="novel_domain.platform_type@1.0.0",
        source_record_ref=_core_ref("sha256:" + "3" * 64, "test.source"),
        source_record_content_hash="sha256:" + "3" * 64,
        semantic_value_hash="sha256:" + "4" * 64,
        annotation_hash="sha256:" + "5" * 64,
        status="resolved",
        failure_code=None,
    )
    denominator_payload = {
        "query_semantics": {
            "scope_identity_ref": query.scope_identity.scope_identity_ref,
            "authority_purpose": query.authority_purpose,
            "valid_effect_coordinate_ref": query.valid_effect_coordinate_ref,
            "visibility_knowledge_cutoff_ref": query.visibility_knowledge_cutoff_ref,
            "purpose_admission_cutoff_ref": query.purpose_admission_cutoff_ref,
            "requested_query_context_ref": query.requested_query_context_ref,
        },
        "registry_content_hash": registry.registry_content_hash,
        "values": [
            {
                "facet_id": facet_value.facet_id,
                "semantic_value_hash": facet_value.semantic_value_hash,
                "status": facet_value.status,
                "failure_code": facet_value.failure_code,
            }
        ],
    }
    denominator = semantic_epoch.SemanticFacetDenominatorReceipt(
        query=query,
        facet_registry_content_hash=registry.registry_content_hash,
        values=(facet_value,),
        denominator_hash=semantic_epoch._model_hash(  # noqa: SLF001
            semantic_epoch._FACET_DENOMINATOR_PREFIX,  # noqa: SLF001
            denominator_payload,
        ),
        status="resolved",
        failure_codes=(),
        predicate_class="independently_reconciled",
    )
    registry_ref = _ref(
        "sha256:" + "1" * 64,
        "test.facet-registry",
    ).model_copy(update={"content_hash": registry.registry_content_hash})
    denominator_ref = _ref(
        "sha256:" + "2" * 64,
        "test.facet-denominator",
    ).model_copy(update={"content_hash": denominator.denominator_hash})
    basis_requirement = EvalSafetyRequirement(
        requirement_id="polisyos.eval_safety.universal_floor@1.0.0",
        evidence_contract_id="polisyos.eval_safety.universal_evidence@1.0.0",
        authority_purpose="attempted_evaluation_safety",
        applicability_scope=EvalSafetyAllApplicability(),
        warning_expires_after=None,
    )
    pack_requirement = EvalSafetyRequirement(
        requirement_id="novel_domain.platform_guard@1.0.0",
        evidence_contract_id="novel_domain.platform_evidence@1.0.0",
        authority_purpose="attempted_evaluation_safety",
        applicability_scope=EvalSafetyFacetApplicability(
            semantic_facet_registry_ref=registry_ref,
            semantic_facet_denominator_receipt_ref=denominator_ref,
            all_of=(
                EvalSafetyFacetValueRequirement(
                    facet_id=facet_value.facet_id,
                    source_binding_ref=_ref("sha256:" + "3" * 64, "test.source"),
                    expected_semantic_value_hash=facet_value.semantic_value_hash,
                ),
            ),
        ),
        warning_expires_after=None,
    )
    producer_ref = _ref("sha256:" + "b" * 64, "test.basis-producer")
    verifier_ref = _ref("sha256:" + "c" * 64, "test.basis-verifier")
    basis = EvalSafetyModeBasis.build(
        schema_version="polisyos.eval_safety.mode_basis.v1",
        rule_version="novel_domain.eval_safety@1.0.0",
        profiles=(EvalSafetyModeProfile(mode="field_pilot", all_of=(basis_requirement,)),),
        producer_authority_ref=producer_ref,
        verifier_receipt_ref=verifier_ref,
        valid_from=evaluated_at - timedelta(days=1),
        valid_until=evaluated_at + timedelta(days=1),
    )
    basis_ref = _ref("sha256:" + "f" * 64, "test.mode-basis").model_copy(
        update={"content_hash": basis.content_hash}
    )
    appointment_refs = (
        _ref("sha256:" + "6" * 64, "test.appointment"),
        _ref("sha256:" + "7" * 64, "test.appointment"),
    )
    pack = DomainEvalSafetyPack.build(
        schema_version="polisyos.eval_safety.domain_pack.v1",
        rule_version=basis.rule_version,
        pack_component_id=core_components.ComponentId(
            "novel_domain.safety_pack@1.0.0"
        ),
        source_pack_ref=_ref("sha256:" + "8" * 64, "test.domain-pack-source"),
        mode_basis_ref=basis_ref,
        semantic_facet_registry_ref=registry_ref,
        semantic_facet_denominator_receipt_ref=denominator_ref,
        verifier_appointment_refs=appointment_refs,
        profiles=(EvalSafetyModeProfile(mode="field_pilot", all_of=(pack_requirement,)),),
        valid_from=evaluated_at - timedelta(days=1),
        valid_until=evaluated_at + timedelta(days=1),
    )
    pack_ref = _ref("sha256:" + "9" * 64, "test.domain-pack").model_copy(
        update={"content_hash": pack.content_hash}
    )
    appointments = (
        es.EvalSafetyVerifierAppointment(
            appointment_id="polisyos.eval_safety.universal_appointment@1.0.0",
            evidence_contract_id=basis_requirement.evidence_contract_id,
            verifier_component_id=core_components.ComponentId(
                "polisyos.eval_safety.universal_verifier@1.0.0"
            ),
            component_discovery_manifest_ref=_ref(
                "sha256:" + "a" * 64, "test.component-manifest"
            ),
            appointing_authority_ref=_ref(
                "sha256:" + "b" * 64, "test.appointing-authority"
            ),
            appointment_verification_receipt_ref=_ref(
                "sha256:" + "c" * 64, "test.appointment-verification"
            ),
            valid_from=evaluated_at - timedelta(days=1),
            valid_until=evaluated_at + timedelta(days=1),
        ),
        es.EvalSafetyVerifierAppointment(
            appointment_id="novel_domain.platform_appointment@1.0.0",
            evidence_contract_id=pack_requirement.evidence_contract_id,
            verifier_component_id=core_components.ComponentId(
                "novel_domain.independent_verifier@1.0.0"
            ),
            component_discovery_manifest_ref=_ref(
                "sha256:" + "d" * 64, "test.component-manifest"
            ),
            appointing_authority_ref=_ref(
                "sha256:" + "e" * 64, "test.appointing-authority"
            ),
            appointment_verification_receipt_ref=_ref(
                "sha256:" + "f" * 64, "test.appointment-verification"
            ),
            valid_from=evaluated_at - timedelta(days=1),
            valid_until=evaluated_at + timedelta(days=1),
        ),
    )
    cause_bindings: dict[tuple[str, str], dict[str, object]] = {}

    class AuthorityResolver:
        def resolve(self, artifact_ref: ArtifactRef) -> es.EvalSafetyAuthorityResolution:
            if artifact_ref in (producer_ref, verifier_ref):
                producer = artifact_ref == producer_ref
                return es.EvalSafetyAuthorityResolution(
                    status="verified",
                    artifact_ref=artifact_ref,
                    blocker_codes=(),
                    predicate_provenance=("independently_reconciled",),
                    resolved_at=evaluated_at,
                    attestation_role=(
                        "producer_statement" if producer else "independent_verification"
                    ),
                    subject_refs=(basis_ref,),
                    subject_schema_version=basis.schema_version,
                    subject_rule_version=basis.rule_version,
                    subject_purpose="attempted_evaluation_mode_basis",
                    subject_effective_at=basis.valid_from,
                    subject_valid_until=basis.valid_until,
                    attesting_component_id=core_components.ComponentId(
                        "polisyos.eval_safety.basis_producer@1.0.0"
                        if producer
                        else "polisyos.eval_safety.basis_verifier@1.0.0"
                    ),
                )
            binding = cause_bindings.get(
                (artifact_ref.artifact_id, artifact_ref.content_hash)
            )
            if binding is None:
                for artifact_id in artifact_store.iter_artifact_ids():
                    manifest = artifact_store.get_manifest(artifact_id)
                    if manifest.kind != c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES[
                        "certificate"
                    ].kind:
                        continue
                    certificate = es.EvalSafetyCertificate.model_validate(
                        from_canonical_bytes(artifact_store.get_bytes(artifact_id))
                    )
                    binding = {
                        "subject_refs": (
                            _ref(str(artifact_id), "placeholder").model_copy(
                                update={
                                    "artifact_type": c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES[
                                        "certificate"
                                    ].kind,
                                    "schema_ref": c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES[
                                        "certificate"
                                    ].schema,
                                    "content_hash": certificate.content_hash,
                                }
                            ),
                        ),
                        "subject_purpose": "certificate_revision_issue",
                        "subject_effective_at": evaluated_at,
                    }
                    break
            if binding is None:
                return es.EvalSafetyAuthorityResolution(
                    status="blocked",
                    artifact_ref=artifact_ref,
                    blocker_codes=(
                        "polisyos.eval_safety.revision_cause_unresolved@1.0.0",
                    ),
                    predicate_provenance=(),
                    resolved_at=evaluated_at,
                )
            return es.EvalSafetyAuthorityResolution(
                status="verified",
                artifact_ref=artifact_ref,
                blocker_codes=(),
                predicate_provenance=("independently_reconciled",),
                resolved_at=evaluated_at - timedelta(minutes=1),
                attestation_role="independent_verification",
                subject_refs=binding["subject_refs"],
                subject_schema_version="polisyos.eval_safety.certificate_revision.v1",
                subject_rule_version=None,
                subject_purpose=binding["subject_purpose"],
                subject_effective_at=binding["subject_effective_at"],
                subject_valid_until=None,
                attesting_component_id=core_components.ComponentId(
                    "polisyos.eval_safety.revision_cause_verifier@1.0.0"
                ),
            )

    class AppointmentResolver:
        def resolve(self, ref: ArtifactRef) -> es.EvalSafetyAppointmentResolution:
            appointment = next(
                (
                    row
                    for candidate_ref, row in zip(
                        appointment_refs, appointments, strict=True
                    )
                    if candidate_ref == ref
                ),
                None,
            )
            return es.EvalSafetyAppointmentResolution(
                status="verified" if appointment is not None else "blocked",
                appointment_ref=ref,
                appointment=appointment,
                blocker_codes=(
                    ()
                    if appointment is not None
                    else ("polisyos.eval_safety.verifier_unappointed@1.0.0",)
                ),
                predicate_provenance=("independently_reconciled",),
                verified_at=evaluated_at,
            )

    class Verifier:
        def __init__(self, appointment: es.EvalSafetyVerifierAppointment) -> None:
            self.component_id = appointment.verifier_component_id

        def verify(
            self,
            *,
            requirement: EvalSafetyRequirement,
            request: es.EvaluationAttemptRequest,
            request_ref: ArtifactRef,
            evidence_ref: ArtifactRef,
            appointment: es.EvalSafetyVerifierAppointment,
            evaluated_at: datetime,
        ) -> es.EvalSafetyRequirementResult:
            return es.EvalSafetyRequirementResult.build(
                requirement_id=requirement.requirement_id,
                evidence_contract_id=requirement.evidence_contract_id,
                request_ref=request_ref,
                candidate_ref=request.candidate_ref,
                world_model_record_ref=request.world_model_record_ref,
                evaluation_mode=request.evaluation_mode,
                target_population_scope_ref=request.target_population_scope_ref,
                rule_version=request.rule_version,
                intended_start_at=request.intended_start_at,
                evidence_ref=evidence_ref,
                evidence_producer_component_id=core_components.ComponentId(
                    "novel_domain.sensor@1.0.0"
                ),
                verifier_component_id=appointment.verifier_component_id,
                verification_receipt_ref=_ref(
                    "sha256:" + "0" * 64, "test.verification-receipt"
                ),
                status="passed",
                blocker_codes=(),
                predicate_provenance=("independently_reconciled",),
                evaluated_at=evaluated_at,
                valid_until=evaluated_at + timedelta(hours=1),
            )

    class Registry:
        def resolve(self, evidence_contract_id: str) -> Verifier | None:
            appointment = next(
                (
                    row
                    for row in appointments
                    if row.evidence_contract_id == evidence_contract_id
                ),
                None,
            )
            return Verifier(appointment) if appointment is not None else None

    authority_resolver = AuthorityResolver()
    appointment_resolver = AppointmentResolver()
    verifier_registry = Registry()
    evidence_refs = (
        _ref("sha256:" + "1" * 64, "test.evidence"),
        _ref("sha256:" + "2" * 64, "test.evidence"),
    )
    intake = EvaluationAttemptIntake(
        attempt_id="attempt-c02-passing",
        evaluator_owner_id=core_components.ComponentId(
            "polisyos.runtime.quality.foundry_value_port@1.0.0"
        ),
        design_problem_ref=design_problem_ref,
        candidate_ref=_ref("sha256:" + "6" * 64, "test.candidate"),
        world_model_record_ref=_ref("sha256:" + "7" * 64, "test.wmr"),
        requested_mode_token="field_pilot",  # noqa: S106
        mode_resolution=resolve_evaluation_mode("field_pilot"),
        domain_hint="novel-domain",
        domain_pack_ref=pack_ref,
        target_population_scope_ref=_ref(
            "sha256:" + "8" * 64, "test.population"
        ),
        evaluation_input_refs=(source_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=source_ref,
                input_class="real_world",
                predicate_provenance="independently_reconciled",
            ),
        ),
        evidence_refs=evidence_refs,
        requested_at=evaluated_at,
        intended_start_at=evaluated_at,
        requested_rule_version=basis.rule_version,
        external_executor_identity_ref=None,
    )
    authorities = EvaluationSafetyAttemptAuthorities(
        mode_basis_ref=basis_ref,
        mode_basis=basis,
        pack_ref=pack_ref,
        pack=pack,
        semantic_facet_denominator_receipt_ref=denominator_ref,
        facet_registry=registry,
        facet_denominator=denominator,
        authority_resolver=authority_resolver,
        appointment_resolver=appointment_resolver,
        verifier_registry=verifier_registry,
        evidence=(
            c02.EvaluationSafetyEvidenceBinding(
                evidence_contract_id=basis_requirement.evidence_contract_id,
                evidence_ref=evidence_refs[0],
            ),
            c02.EvaluationSafetyEvidenceBinding(
                evidence_contract_id=pack_requirement.evidence_contract_id,
                evidence_ref=evidence_refs[1],
            ),
        ),
        classification_offer=None,
        classification=None,
        certificate_issue_cause_ref=_ref(
            "sha256:" + "5" * 64, "test.revision-cause"
        ),
    )
    persisted = service.compose_and_persist_attempt(
        intake=intake,
        authorities=authorities,
        context=_context(source_ref.artifact_id),
        evaluated_at=evaluated_at,
    )
    assert persisted.certificate_ref is not None
    assert persisted.request_ref is not None
    assert len(persisted.revision_nodes) == 1
    material = EvaluationSafetyReplayMaterial(
        intake_ref=persisted.intake_ref,
        request_ref=persisted.request_ref,
        mode_basis_ref=basis_ref,
        mode_basis=basis,
        pack_ref=pack_ref,
        pack=pack,
        facet_registry=registry,
        facet_denominator=denominator,
        authority_resolver=authority_resolver,
        appointment_resolver=appointment_resolver,
        verifier_registry=verifier_registry,
        evidence=authorities.evidence,
        classification=None,
        decision_ref=persisted.decision_ref,
        certificate_ref=persisted.certificate_ref,
        revision_nodes=persisted.revision_nodes,
        decision_evaluated_at=evaluated_at,
        revalidated_at=datetime.now(UTC),
    )
    head_ref = persisted.revision_nodes[0].revision_ref
    execution_context = es.EvaluationExecutionContext(
        intake_ref=persisted.intake_ref,
        evaluator_owner_id=intake.evaluator_owner_id,
        design_problem_ref=intake.design_problem_ref,
        evaluation_mode="field_pilot",
        candidate_ref=intake.candidate_ref,
        world_model_record_ref=intake.world_model_record_ref,
        target_population_scope_ref=intake.target_population_scope_ref,
        rule_version=basis.rule_version,
        intended_start_at=intake.intended_start_at,
        evaluation_input_refs=intake.evaluation_input_refs,
        evaluation_input_provenance=intake.evaluation_input_provenance,
        eval_safety_certificate_ref=persisted.certificate_ref,
        eval_safety_revision_head_ref=head_ref,
    )
    return _PassingFixture(
        service=service,
        artifact_store=artifact_store,
        intake=intake,
        authorities=authorities,
        persisted=persisted,
        replay_material=material,
        execution_context=execution_context,
        authority_resolver=authority_resolver,
        appointment_resolver=appointment_resolver,
        verifier_registry=verifier_registry,
        cause_bindings=cause_bindings,
        evaluated_at=evaluated_at,
    )


def _verified_classification(
    core: es.EvaluationSafetyDecisionCore,
    monkeypatch: pytest.MonkeyPatch,
    *,
    promotion_safe: bool,
) -> tuple[
    es.EvalSafetyNearMissClassificationOffer,
    ArtifactRef,
    es.VerifiedNearMissClassification,
]:
    from polisyos.runtime.quality import promotion_sequence

    def named_ref(value: str, kind: str, semantic_hash: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=value,
            artifact_type=kind,
            content_hash=semantic_hash,
            schema_ref=f"{kind}.v1",
            uri=f"cas://{value}",
            version="1.0",
        )

    projection_hash = "sha256:" + "1" * 64
    candidate_hash = "sha256:" + "2" * 64
    value_hash = "sha256:" + "3" * 64
    world_hash = "sha256:" + "4" * 64
    open_ref = named_ref(
        "sha256:" + "5" * 64, "test.open-world", "sha256:" + "5" * 64
    )
    epoch_ref = named_ref(
        "sha256:" + "6" * 64, "test.epoch", "sha256:" + "6" * 64
    )
    design_binding = SimpleNamespace(model_dump=lambda **_values: {"design": "bound"})
    owner_projection = SimpleNamespace(
        open_world_gate=SimpleNamespace(vector_artifact_ref=open_ref),
        epoch_validity_projection=SimpleNamespace(gate_receipt_ref=epoch_ref),
        design_problem_binding=design_binding,
        projection_hash=projection_hash,
    )
    receipt = SimpleNamespace(
        candidate_id="candidate-classified",
        owner_projection=owner_projection,
        schema_version="polisyos.promotion.canonical.v1",
        model_dump=lambda **_values: {"receipt": "canonical"},
    )
    monkeypatch.setattr(
        promotion_sequence,
        "CanonicalPromotionReceipt",
        SimpleNamespace(model_validate=lambda _payload: receipt),
    )
    monkeypatch.setattr(
        promotion_sequence,
        "validate_canonical_promotion_receipt",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        promotion_sequence,
        "promotion_receipt_allows_decision_front",
        lambda *_args, **_kwargs: promotion_safe,
    )
    promotion_receipt_ref = named_ref(
        "sha256:" + "7" * 64,
        "test.promotion-receipt",
        gy_content_hash(receipt.model_dump()),
    )
    canonical_input_ref = named_ref(
        "sha256:" + "8" * 64, "test.promotion-input", projection_hash
    )
    design_ref = named_ref(
        "sha256:" + "9" * 64,
        "test.design-binding",
        gy_content_hash(design_binding.model_dump()),
    )
    value_ref = named_ref("sha256:" + "a" * 64, "test.value", value_hash)
    candidate_ref = named_ref(
        "candidate-classified", "test.candidate", candidate_hash
    )
    world_ref = named_ref("wmr-classified", "test.wmr", world_hash)
    validation_ref = named_ref(
        "sha256:" + "b" * 64, "test.validation", projection_hash
    )
    offer_values = {
        "promotion_receipt_ref": promotion_receipt_ref,
        "canonical_promotion_input_ref": canonical_input_ref,
        "design_problem_binding_ref": design_ref,
        "value_receipt_ref": value_ref,
        "candidate_ref": candidate_ref,
        "world_model_record_ref": world_ref,
        "promotion_rule_version": receipt.schema_version,
        "open_world_resolver_basis_ref": open_ref,
        "epoch_resolver_basis_ref": epoch_ref,
        "safety_semantic_hash": core.safety_semantic_hash,
        "offered_at": core.evaluated_at,
    }
    offer = es.EvalSafetyNearMissClassificationOffer(
        **offer_values,
        content_hash=es._content_hash(offer_values),  # noqa: SLF001
    )
    offer_artifact_id = "sha256:" + canonical_content_hash(
        to_canonical_bytes(offer.model_dump(mode="json"))
    )
    offer_identity = c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES["classification_offer"]
    offer_ref = ArtifactRef(
        artifact_id=offer_artifact_id,
        artifact_type=offer_identity.kind,
        content_hash=offer.content_hash,
        schema_ref=offer_identity.schema,
        uri=f"cas://sha256/{offer_artifact_id.removeprefix('sha256:')}",
        version="1.0",
    )
    classification = es.verify_near_miss_classification(
        offer=offer,
        offer_ref=offer_ref,
        validation_basis_ref=validation_ref,
        canonical_promotion_input_ref=canonical_input_ref,
        design_problem_binding_ref=design_ref,
        value_receipt_ref=value_ref,
        candidate_ref=candidate_ref,
        world_model_record_ref=world_ref,
        promotion_rule_version=receipt.schema_version,
        current_open_world_resolver_basis_ref=open_ref,
        current_epoch_resolver_basis_ref=epoch_ref,
        promotion=SimpleNamespace(receipts=({"receipt": "canonical"},)),
        candidate_summary=SimpleNamespace(
            candidate_id="candidate-classified", content_hash=candidate_hash
        ),
        design_problem=SimpleNamespace(),
        value_receipt=SimpleNamespace(
            value_ref=value_hash,
            world_model_record_content_hash=world_hash,
        ),
        open_world_resolver=SimpleNamespace(),
        epoch_validity_resolver=SimpleNamespace(),
        core=core,
    )
    assert classification is not None
    return offer, offer_ref, classification


def _blocked_core(artifact_store: FileSystemCAS):
    source = artifact_store.put_json(
        {"input": "real-world"},
        opts=PutOptions(kind="test.eval-input", media_type="application/json"),
    )
    source_ref = _ref(str(source.artifact_id), "test.eval-input")
    candidate_ref = _ref("sha256:" + "3" * 64, "test.candidate")
    world_ref = _ref("sha256:" + "4" * 64, "test.world-model")
    population_ref = _ref("sha256:" + "5" * 64, "test.population")
    pack_ref = _ref("sha256:" + "6" * 64, "test.pack")
    intake_ref = _ref(str(source.artifact_id), "test.intake")
    intake = EvaluationAttemptIntake(
        attempt_id="attempt-c02-promotion",
        evaluator_owner_id=ProducerInfo(
            component="polisyos.runtime.test.evaluator@1.0.0",
            version="1.0.0",
        ).component,
        design_problem_ref="sha256:" + "0" * 64,
        candidate_ref=candidate_ref,
        world_model_record_ref=world_ref,
        requested_mode_token="field_pilot",  # noqa: S106 - evaluation mode, not a secret.
        mode_resolution=resolve_evaluation_mode("field_pilot"),
        domain_hint="never-seen-domain",
        domain_pack_ref=pack_ref,
        target_population_scope_ref=population_ref,
        evaluation_input_refs=(source_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=source_ref,
                input_class="real_world",
                predicate_provenance="independently_reconciled",
            ),
        ),
        evidence_refs=(),
        requested_at=_NOW,
        intended_start_at=_NOW,
        requested_rule_version="eval-safety-rule-v1",
        external_executor_identity_ref=None,
    )
    core = decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=None,
        request_ref=None,
        admitted_pack=None,
        mode_basis=None,
        requirement_results=(),
        evaluated_at=_NOW,
    )
    return core, source_ref


def _persisted_reduction(tmp_path, classification: object):
    service, artifact_store = _service(tmp_path)
    core, source_ref = _blocked_core(artifact_store)
    persisted = service.persist_decision(
        core=core,
        classification=classification,  # type: ignore[arg-type]
        context=_context(source_ref.artifact_id),
    )
    evidence = EvaluationSafetyDecisionEvidence(
        decision_ref=persisted.decision_ref,
        decision=persisted.decision,
        classification=None,
    )
    return core, persisted, service.reduce_decisions(evidence=(evidence,))


def test_cas_backed_admission_verifier_is_fresh_and_current(tmp_path) -> None:
    fixture = _passing_fixture(tmp_path)

    class ActionCapableResolver:
        def __init__(self, delegate: object) -> None:
            self.delegate = delegate
            self.action_calls = 0

        def resolve(self, value: object) -> object:
            return self.delegate.resolve(value)

        def execute(self) -> None:
            self.action_calls += 1

        def schedule(self) -> None:
            self.action_calls += 1

        def dispatch(self) -> None:
            self.action_calls += 1

        def transport(self) -> None:
            self.action_calls += 1

    authority_spy = ActionCapableResolver(fixture.authority_resolver)
    appointment_spy = ActionCapableResolver(fixture.appointment_resolver)
    registry_spy = ActionCapableResolver(fixture.verifier_registry)

    class CurrentStateResolver:
        def __init__(self, material: EvaluationSafetyReplayMaterial) -> None:
            self.material = material
            self.calls = 0

        def resolve(
            self, context: es.EvaluationExecutionContext
        ) -> EvaluationSafetyReplayMaterial:
            del context
            self.calls += 1
            return self.material

    resolver = CurrentStateResolver(fixture.replay_material)
    verifier_type = c02.EvaluationSafetyAdmissionVerifier
    verifier = verifier_type(
        persistence_service=fixture.service,
        current_state_resolver=resolver,
        authority_resolver=authority_spy,
        appointment_resolver=appointment_spy,
        verifier_registry=registry_spy,
    )
    context = fixture.execution_context
    first_challenge = es.EvalSafetyAdmissionChallenge.fresh(
        consumer_component_id=context.evaluator_owner_id
    )
    first = verifier.require_admission(context, first_challenge)
    assert es.evaluation_safety_consumer_admission_is_verified(
        first, context, first_challenge
    )

    changed_context = context.model_copy(
        update={"candidate_ref": _ref("sha256:" + "e" * 64, "test.candidate")}
    )
    second_challenge = es.EvalSafetyAdmissionChallenge.fresh(
        consumer_component_id=context.evaluator_owner_id
    )
    assert not es.evaluation_safety_consumer_admission_is_verified(
        first, changed_context, first_challenge
    )
    assert not es.evaluation_safety_consumer_admission_is_verified(
        first, context, second_challenge
    )
    second = verifier.require_admission(context, second_challenge)
    assert es.evaluation_safety_consumer_admission_is_verified(
        second, context, second_challenge
    )
    assert second is not first and resolver.calls == 2

    stale_context = context.model_copy(
        update={
            "eval_safety_revision_head_ref": _ref(
                "sha256:" + "f" * 64, "test.certificate-revision"
            )
        }
    )
    stale = verifier.require_admission(
        stale_context,
        es.EvalSafetyAdmissionChallenge.fresh(
            consumer_component_id=stale_context.evaluator_owner_id
        ),
    )
    assert stale.status == "blocked"
    assert resolver.calls == 3
    assert es.verifier_port_is_verification_only(verifier_type)
    assert (
        authority_spy.action_calls,
        appointment_spy.action_calls,
        registry_spy.action_calls,
    ) == (0, 0, 0)

    issue_node = fixture.persisted.revision_nodes[0]
    assert fixture.persisted.certificate_ref is not None
    fork_rows = []
    for char in ("a", "b"):
        cause_ref = _ref("sha256:" + char * 64, "test.revision-cause")
        effective_at = fixture.evaluated_at + timedelta(seconds=10)
        fixture.cause_bindings[(cause_ref.artifact_id, cause_ref.content_hash)] = {
            "subject_refs": (
                issue_node.revision_ref,
                fixture.persisted.certificate_ref,
            ),
            "subject_purpose": "certificate_revision_supersede",
            "subject_effective_at": effective_at,
        }
        fork_rows.append(
            es.EvalSafetyCertificateRevision.transition(
                revision_lineage_id=issue_node.revision.revision_lineage_id,
                predecessor_ref=issue_node.revision_ref,
                action="supersede",
                certificate_ref=fixture.persisted.certificate_ref,
                verified_cause_ref=cause_ref,
                cause_resolver=fixture.authority_resolver,
                effective_at=effective_at,
            )
        )
    fixture.service.persist_revision_chain(
        revisions=(issue_node.revision, *fork_rows),
        cause_resolver=fixture.authority_resolver,
        context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
    )
    forked = verifier.require_admission(
        context,
        es.EvalSafetyAdmissionChallenge.fresh(
            consumer_component_id=context.evaluator_owner_id
        ),
    )
    assert forked.status == "blocked"

    class MissingStateResolver:
        action_calls = 0

        def resolve(
            self, context: es.EvaluationExecutionContext
        ) -> EvaluationSafetyReplayMaterial | None:
            del context
            return None

        def execute(self) -> None:
            self.action_calls += 1

    missing_state = MissingStateResolver()
    blocked_verifier = verifier_type(
        persistence_service=fixture.service,
        current_state_resolver=missing_state,
        authority_resolver=authority_spy,
        appointment_resolver=appointment_spy,
        verifier_registry=registry_spy,
    )
    blocked = blocked_verifier.require_admission(
        context,
        es.EvalSafetyAdmissionChallenge.fresh(
            consumer_component_id=context.evaluator_owner_id
        ),
    )
    assert blocked.status == "blocked" and missing_state.action_calls == 0
    public_callables = {
        name
        for name, value in inspect.getmembers(verifier_type)
        if not name.startswith("_") and callable(value)
    }
    assert public_callables == {"require_admission"}
    signature = inspect.signature(verifier_type.require_admission)
    assert all(
        parameter.kind
        not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
        for parameter in signature.parameters.values()
    )


def test_consumer_admission_blocks_request_design_problem_mismatch(tmp_path) -> None:
    fixture = _passing_fixture(tmp_path)

    class CurrentStateResolver:
        def resolve(
            self,
            context: es.EvaluationExecutionContext,
        ) -> EvaluationSafetyReplayMaterial:
            del context
            return fixture.replay_material

    verifier = c02.EvaluationSafetyAdmissionVerifier(
        persistence_service=fixture.service,
        current_state_resolver=CurrentStateResolver(),
        authority_resolver=fixture.authority_resolver,
        appointment_resolver=fixture.appointment_resolver,
        verifier_registry=fixture.verifier_registry,
    )
    mismatched_context = fixture.execution_context.model_copy(
        update={"design_problem_ref": "sha256:" + "e" * 64}
    )
    challenge = es.EvalSafetyAdmissionChallenge.fresh(
        consumer_component_id=mismatched_context.evaluator_owner_id
    )

    admission = verifier.require_admission(mismatched_context, challenge)

    assert admission.status == "blocked"
    assert admission.blocker_codes == (
        "polisyos.eval_safety.certificate_binding_mismatch@1.0.0",
        "polisyos.eval_safety.execution_context_binding_mismatch@1.0.0",
    )
    assert not es.evaluation_safety_consumer_admission_is_verified(
        admission,
        mismatched_context,
        challenge,
    )


def test_unseen_domain_composition_is_data_driven_and_refuses_exact_gaps(
    tmp_path,
) -> None:
    engine_digest = Path(c02.__file__).read_bytes()
    fixture = _passing_fixture(tmp_path)
    assert fixture.persisted.decision.safety.status == "passed"
    assert fixture.persisted.certificate_ref is not None
    assert tuple(
        row.requirement_id
        for row in fixture.persisted.decision.safety.requirement_results
    ) == (
        "polisyos.eval_safety.universal_floor@1.0.0",
        "novel_domain.platform_guard@1.0.0",
    )

    class ActionCapableResolver:
        def __init__(self, delegate: object) -> None:
            self.delegate = delegate
            self.action_calls = 0

        def resolve(self, value: object) -> object:
            return self.delegate.resolve(value)

        def execute(self) -> None:
            self.action_calls += 1

        def schedule(self) -> None:
            self.action_calls += 1

        def dispatch(self) -> None:
            self.action_calls += 1

        def transport(self) -> None:
            self.action_calls += 1

    class ActionCapableVerifier:
        def __init__(self, delegate: object) -> None:
            self.delegate = delegate
            self.component_id = delegate.component_id
            self.action_calls = 0

        def verify(self, **values: object) -> object:
            return self.delegate.verify(**values)

        def execute(self) -> None:
            self.action_calls += 1

        def schedule(self) -> None:
            self.action_calls += 1

    class ActionCapableRegistry(ActionCapableResolver):
        def __init__(self, delegate: object) -> None:
            super().__init__(delegate)
            self.verifiers: list[ActionCapableVerifier] = []

        def resolve(self, value: object) -> ActionCapableVerifier | None:
            verifier = self.delegate.resolve(value)
            if verifier is None:
                return None
            wrapped = ActionCapableVerifier(verifier)
            self.verifiers.append(wrapped)
            return wrapped

    authority_spy = ActionCapableResolver(fixture.authority_resolver)
    appointment_spy = ActionCapableResolver(fixture.appointment_resolver)
    registry_spy = ActionCapableRegistry(fixture.verifier_registry)
    spied_authorities = replace(
        fixture.authorities,
        authority_resolver=authority_spy,
        appointment_resolver=appointment_spy,
        verifier_registry=registry_spy,
    )
    spied_passed = fixture.service.compose_and_persist_attempt(
        intake=fixture.intake,
        authorities=spied_authorities,
        context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=fixture.evaluated_at,
    )
    assert spied_passed.decision.safety.status == "passed"

    missing_facet = fixture.service.compose_and_persist_attempt(
        intake=fixture.intake,
        authorities=replace(spied_authorities, facet_denominator=None),
        context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=fixture.evaluated_at,
    )
    assert "polisyos.eval_safety.semantic_facet_denominator_missing@1.0.0" in (
        missing_facet.decision.safety.blocker_codes
    )

    class MissingAppointmentResolver:
        def resolve(self, ref: ArtifactRef) -> es.EvalSafetyAppointmentResolution:
            resolved = fixture.appointment_resolver.resolve(ref)
            if resolved.appointment is None or not resolved.appointment.evidence_contract_id.startswith(
                "novel_domain."
            ):
                return resolved
            return es.EvalSafetyAppointmentResolution(
                status="blocked",
                appointment_ref=ref,
                appointment=None,
                blocker_codes=(
                    "polisyos.eval_safety.verifier_unappointed@1.0.0",
                ),
                predicate_provenance=("not_established",),
                verified_at=fixture.evaluated_at,
            )

    missing_appointment = fixture.service.compose_and_persist_attempt(
        intake=fixture.intake,
        authorities=replace(
            fixture.authorities,
            appointment_resolver=MissingAppointmentResolver(),
        ),
        context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=fixture.evaluated_at,
    )
    assert "polisyos.eval_safety.verifier_unappointed@1.0.0" in (
        missing_appointment.decision.safety.blocker_codes
    )
    assert (
        authority_spy.action_calls,
        appointment_spy.action_calls,
        registry_spy.action_calls,
        *(verifier.action_calls for verifier in registry_spy.verifiers),
    ) == (0,) * (3 + len(registry_spy.verifiers))
    assert Path(c02.__file__).read_bytes() == engine_digest
    assert "novel_domain" not in inspect.getsource(c02.EvaluationSafetyPersistenceService)


def test_accepted_request_persists_when_domain_pack_is_unresolved(tmp_path) -> None:
    fixture = _passing_fixture(tmp_path)
    persisted = fixture.service.compose_and_persist_attempt(
        intake=fixture.intake,
        authorities=replace(fixture.authorities, pack=None),
        context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=fixture.evaluated_at,
    )

    assert persisted.request_ref is not None
    assert "polisyos.eval_safety.domain_pack_missing@1.0.0" in (
        persisted.decision.safety.blocker_codes
    )


def test_compose_and_replay_share_the_complete_authority_absence_lattice(
    tmp_path,
) -> None:
    fixture = _passing_fixture(tmp_path)

    class MissingAppointmentResolver:
        def resolve(self, ref: ArtifactRef) -> es.EvalSafetyAppointmentResolution:
            return es.EvalSafetyAppointmentResolution(
                status="blocked",
                appointment_ref=ref,
                appointment=None,
                blocker_codes=(
                    "polisyos.eval_safety.verifier_unappointed@1.0.0",
                ),
                predicate_provenance=("not_established",),
                verified_at=fixture.evaluated_at,
            )

    cases = (
        replace(fixture.authorities, mode_basis_ref=None),
        replace(fixture.authorities, mode_basis=None),
        replace(fixture.authorities, pack_ref=None),
        replace(fixture.authorities, pack=None),
        replace(fixture.authorities, facet_registry=None),
        replace(fixture.authorities, facet_denominator=None),
        replace(
            fixture.authorities,
            semantic_facet_denominator_receipt_ref=None,
        ),
        replace(
            fixture.authorities,
            appointment_resolver=MissingAppointmentResolver(),
        ),
        replace(fixture.authorities, evidence=()),
    )
    for index, authorities in enumerate(cases):
        persisted = fixture.service.compose_and_persist_attempt(
            intake=fixture.intake,
            authorities=authorities,
            context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
            evaluated_at=fixture.evaluated_at,
        )
        assert persisted.decision.safety.status == "blocked", index
        replayed = fixture.service.reconcile_persisted_attempt(
            material=replace(
                fixture.replay_material,
                request_ref=persisted.request_ref,
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
                decision_ref=persisted.decision_ref,
                certificate_ref=persisted.certificate_ref,
                revision_nodes=persisted.revision_nodes,
                classification=None,
                decision_evaluated_at=fixture.evaluated_at,
                revalidated_at=fixture.evaluated_at,
            )
        )
        assert replayed is not None, index
        assert replayed.decision == persisted.decision, index


def test_admission_io_and_ownership_failures_return_typed_blocked_receipts(
    tmp_path,
) -> None:
    fixture = _passing_fixture(tmp_path)

    class RaisingResolver:
        def resolve(
            self, context: es.EvaluationExecutionContext
        ) -> EvaluationSafetyReplayMaterial:
            del context
            raise OSError("current-state CAS unavailable")

    verifier = c02.EvaluationSafetyAdmissionVerifier(
        persistence_service=fixture.service,
        current_state_resolver=RaisingResolver(),
        authority_resolver=fixture.authority_resolver,
        appointment_resolver=fixture.appointment_resolver,
        verifier_registry=fixture.verifier_registry,
    )
    challenge = es.EvalSafetyAdmissionChallenge.fresh(
        consumer_component_id=fixture.execution_context.evaluator_owner_id
    )
    resolver_blocked = verifier.require_admission(fixture.execution_context, challenge)
    assert resolver_blocked.status == "blocked"
    assert resolver_blocked.blocker_codes == (
        "polisyos.eval_safety.authority_replay_not_established@1.0.0",
    )

    class ProgrammerFaultResolver:
        def resolve(
            self, context: es.EvaluationExecutionContext
        ) -> EvaluationSafetyReplayMaterial:
            del context
            raise ValueError("resolver programmer fault")

    programmer_fault = c02.EvaluationSafetyAdmissionVerifier(
        persistence_service=fixture.service,
        current_state_resolver=ProgrammerFaultResolver(),
        authority_resolver=fixture.authority_resolver,
        appointment_resolver=fixture.appointment_resolver,
        verifier_registry=fixture.verifier_registry,
    )
    with pytest.raises(ValueError, match="resolver programmer fault"):
        programmer_fault.require_admission(fixture.execution_context, challenge)

    class CurrentStateResolver:
        def resolve(
            self, context: es.EvaluationExecutionContext
        ) -> EvaluationSafetyReplayMaterial:
            del context
            return fixture.replay_material

    class BrokenVerifier:
        def __init__(self, component_id: core_components.ComponentId) -> None:
            self.component_id = component_id

        def verify(
            self,
            *,
            requirement: EvalSafetyRequirement,
            request: es.EvaluationAttemptRequest,
            request_ref: ArtifactRef,
            evidence_ref: ArtifactRef,
            appointment: es.EvalSafetyVerifierAppointment,
            evaluated_at: datetime,
        ) -> es.EvalSafetyRequirementResult:
            del requirement, request, request_ref, evidence_ref, appointment, evaluated_at
            raise ValueError("appointed verifier programmer fault")

    class BrokenVerifierRegistry:
        def resolve(self, evidence_contract_id: str) -> BrokenVerifier | None:
            verifier = fixture.verifier_registry.resolve(evidence_contract_id)
            if verifier is None:
                return None
            return BrokenVerifier(verifier.component_id)

    broken_verifier = c02.EvaluationSafetyAdmissionVerifier(
        persistence_service=fixture.service,
        current_state_resolver=CurrentStateResolver(),
        authority_resolver=fixture.authority_resolver,
        appointment_resolver=fixture.appointment_resolver,
        verifier_registry=BrokenVerifierRegistry(),
    )
    with pytest.raises(ValueError, match="appointed verifier programmer fault"):
        broken_verifier.require_admission(fixture.execution_context, challenge)

    inaccessible_ref = _ref(
        "sha256:" + "0" * 64,
        c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES["certificate"].kind,
    ).model_copy(
        update={
            "schema_ref": c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES[
                "certificate"
            ].schema
        }
    )
    inaccessible_context = fixture.execution_context.model_copy(
        update={"eval_safety_certificate_ref": inaccessible_ref}
    )

    class InaccessibleStateResolver:
        def resolve(
            self, context: es.EvaluationExecutionContext
        ) -> EvaluationSafetyReplayMaterial:
            del context
            return replace(fixture.replay_material, certificate_ref=inaccessible_ref)

    inaccessible = c02.EvaluationSafetyAdmissionVerifier(
        persistence_service=fixture.service,
        current_state_resolver=InaccessibleStateResolver(),
        authority_resolver=fixture.authority_resolver,
        appointment_resolver=fixture.appointment_resolver,
        verifier_registry=fixture.verifier_registry,
    ).require_admission(inaccessible_context, challenge)
    assert inaccessible.status == "blocked"
    assert inaccessible.blocker_codes == (
        "polisyos.eval_safety.authority_replay_not_established@1.0.0",
    )


def test_eval_safety_identity_table_pins_all_roles() -> None:
    rows = c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES
    assert {key: row.authority_role for key, row in rows.items()} == {
        "pack_admission": "producer_authority",
        "intake": "not_authoritative",
        "request": "not_authoritative",
        "classification_offer": "not_authoritative",
        "decision": "producer_authority",
        "certificate": "producer_authority",
        "certificate_revision": "producer_authority",
        "metrics_projection": "projection_only",
    }


def test_promotion_state_injection_cannot_change_persisted_safety_or_unsafe_count(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated_at = _NOW
    absent_fixture = _passing_fixture(
        tmp_path / "absent", evaluated_at=evaluated_at
    )
    absent = absent_fixture.service.compose_and_persist_attempt(
        intake=absent_fixture.intake,
        authorities=replace(absent_fixture.authorities, facet_denominator=None),
        context=_context(absent_fixture.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=evaluated_at,
    )
    core = absent.decision.safety
    offer, _offer_ref, genuine = _verified_classification(
        core, monkeypatch, promotion_safe=True
    )
    public_copy = object.__new__(es.VerifiedNearMissClassification)
    for name in (
        "offer_ref",
        "validation_basis_ref",
        "promotion_safe_facet",
        "safety_semantic_hash",
    ):
        object.__setattr__(public_copy, name, getattr(genuine, name))
    object.__setattr__(public_copy, "_producer_token", None)
    object.__setattr__(public_copy, "_producer_fingerprint", None)
    forged = {
        "offer_ref": genuine.offer_ref,
        "validation_basis_ref": genuine.validation_basis_ref,
        "promotion_safe_facet": True,
        "safety_semantic_hash": core.safety_semantic_hash,
    }
    persisted_by_case = {"absent": (absent_fixture, absent)}
    for name, classification in (
        ("public_copy", public_copy),
        ("forged", forged),
        ("genuine", genuine),
    ):
        fixture = _passing_fixture(tmp_path / name, evaluated_at=evaluated_at)
        persisted_by_case[name] = (
            fixture,
            fixture.service.compose_and_persist_attempt(
                intake=fixture.intake,
                authorities=replace(
                    fixture.authorities,
                    facet_denominator=None,
                    classification_offer=offer,
                    classification=classification,  # type: ignore[arg-type]
                ),
                context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
                evaluated_at=evaluated_at,
            ),
        )

    observables = []
    for name, (fixture, persisted) in persisted_by_case.items():
        reduction = fixture.service.reduce_decisions(
            evidence=(persisted.owner_evidence,)
        )
        observables.append(
            (
                persisted.decision.safety.status,
                persisted.decision.safety.blocker_codes,
                evaluation_safety_core_bytes(persisted.decision.safety),
                persisted.decision.safety.safety_semantic_hash,
                persisted.decision.decision_id,
                persisted.decision.safety.certificate_eligible,
                reduction.unsafe_attempt_blocked_count,
            )
        )
        if name != "genuine":
            assert persisted.decision.promotion_safe_facet is None
            assert not persisted.decision.near_miss
            assert reduction.near_miss_count == 0
            assert persisted.decision.decision_id in (
                reduction.unclassified_blocked_decision_ids
            )
        else:
            assert persisted.decision.promotion_safe_facet is True
            assert persisted.decision.near_miss
            assert reduction.near_miss_count == 1
            assert reduction.unclassified_blocked_decision_ids == ()

    assert len(set(observables)) == 1


def test_counter_reducer_reports_near_miss_and_unclassified_coverage_honestly(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated_at = _NOW
    seed = _passing_fixture(tmp_path / "seed", evaluated_at=evaluated_at)
    seed_blocked = seed.service.compose_and_persist_attempt(
        intake=seed.intake,
        authorities=replace(seed.authorities, facet_denominator=None),
        context=_context(seed.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=evaluated_at,
    )
    offer, _offer_ref, classified_true = _verified_classification(
        seed_blocked.decision.safety,
        monkeypatch,
        promotion_safe=True,
    )
    _offer, _offer_ref, classified_false = _verified_classification(
        seed_blocked.decision.safety,
        monkeypatch,
        promotion_safe=False,
    )

    def classified_attempt(path: str, classification: object):
        fixture = _passing_fixture(tmp_path / path, evaluated_at=evaluated_at)
        persisted = fixture.service.compose_and_persist_attempt(
            intake=fixture.intake,
            authorities=replace(
                fixture.authorities,
                facet_denominator=None,
                classification_offer=offer,
                classification=classification,  # type: ignore[arg-type]
            ),
            context=_context(fixture.intake.evaluation_input_refs[0].artifact_id),
            evaluated_at=evaluated_at,
        )
        return fixture, persisted

    true_fixture, classified_true_attempt = classified_attempt(
        "classified-true", classified_true
    )
    retry_authorities = replace(
        true_fixture.authorities,
        facet_denominator=None,
        classification_offer=offer,
        classification=classified_true,
    )
    persisted_retry = true_fixture.service.compose_and_persist_attempt(
        intake=true_fixture.intake,
        authorities=retry_authorities,
        context=_context(true_fixture.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=evaluated_at,
    )
    assert persisted_retry.decision_ref == classified_true_attempt.decision_ref
    retry_manifest = true_fixture.artifact_store.get_manifest(
        CoreArtifactID.model_validate(persisted_retry.decision_ref.artifact_id)
    )
    retry_event = from_canonical_bytes(
        true_fixture.artifact_store.get_bytes(
            CoreArtifactID.model_validate(
                retry_manifest.authority.diagnostic_event_ref
            )
        )
    )
    assert len(
        true_fixture.service._event_log.list_events(  # noqa: SLF001
            event_id=retry_event["event_id"],
            limit=2,
        )
    ) == 1
    retry = true_fixture.service.reduce_decisions(
        evidence=(
            true_fixture.persisted.owner_evidence,
            classified_true_attempt.owner_evidence,
            persisted_retry.owner_evidence,
        )
    )
    decision_identity = c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES["decision"]
    selected_from_cas: set[str] = set()
    expected_decision_ids: set[str] = set()
    for artifact_id in true_fixture.artifact_store.iter_artifact_ids():
        manifest = true_fixture.artifact_store.get_manifest(artifact_id)
        schema = manifest.artifact_schema
        if (
            manifest.kind != decision_identity.kind
            or schema is None
            or schema.name != decision_identity.schema
            or schema.version != "1.0"
        ):
            continue
        selected_from_cas.add(str(artifact_id))
        expected_decision_ids.add(
            es.EvaluationSafetyDecisionEvent.model_validate(
                from_canonical_bytes(
                    true_fixture.artifact_store.get_bytes(artifact_id)
                )
            ).decision_id
        )
    assert {ref.artifact_id for ref in retry.selected_refs} == selected_from_cas
    assert {ref.artifact_id for ref in retry.reconciled_refs} == selected_from_cas
    assert set(retry.denominator_decision_ids) == expected_decision_ids
    assert true_fixture.persisted.decision_ref in retry.selected_refs
    assert true_fixture.persisted.decision_ref in retry.reconciled_refs
    assert (
        true_fixture.persisted.decision.decision_id
        in retry.denominator_decision_ids
    )
    assert retry.unsafe_attempt_blocked_count == 1
    assert retry.near_miss_count == 1
    assert retry.near_miss_classification_status == "complete"

    false_fixture, classified_false_attempt = classified_attempt(
        "classified-false", classified_false
    )
    classified_false_reduction = false_fixture.service.reduce_decisions(
        evidence=(
            false_fixture.persisted.owner_evidence,
            classified_false_attempt.owner_evidence,
        )
    )
    assert classified_false_reduction.unsafe_attempt_blocked_count == 1
    assert classified_false_reduction.near_miss_count == 0
    assert classified_false_reduction.near_miss_classification_status == "complete"

    identity = c02.EVALUATION_SAFETY_ARTIFACT_IDENTITIES["decision"]
    malformed_ref = true_fixture.artifact_store.put_json(
        {"decision_id": classified_true_attempt.decision.decision_id},
        opts=PutOptions(
            kind=identity.kind,
            media_type="application/json",
            schema=SchemaInfo(name=identity.schema, version="1.0"),
        ),
    )
    mixed = true_fixture.service.reduce_decisions(
        evidence=(
            true_fixture.persisted.owner_evidence,
            classified_true_attempt.owner_evidence,
        )
    )
    assert len(mixed.unreconciled_refs) == 1
    assert mixed.unreconciled_refs[0].artifact_id == str(malformed_ref.artifact_id)
    assert mixed.reconciliation_status == "not_established"
    assert mixed.near_miss_classification_status == "not_established"

    original_log = false_fixture.service._event_log  # noqa: SLF001

    class MutatedEventLog:
        def list_events(self, **values: object) -> list[object]:
            rows = original_log.list_events(**values)
            return [
                replace(
                    row,
                    event=row.event.model_copy(
                        update={"trace_id": "trace-event-substituted"}
                    ),
                )
                if row.event.payload_ref == classified_false_attempt.decision_ref.artifact_id
                else row
                for row in rows
            ]

    mutated_service = EvaluationSafetyPersistenceService(
        artifact_store=false_fixture.artifact_store,
        event_log=MutatedEventLog(),
    )
    event_mutated = mutated_service.reduce_decisions(
        evidence=(
            false_fixture.persisted.owner_evidence,
            classified_false_attempt.owner_evidence,
        )
    )
    assert tuple(ref.artifact_id for ref in event_mutated.unreconciled_refs) == (
        classified_false_attempt.decision_ref.artifact_id,
    )
    assert event_mutated.near_miss_classification_status == "not_established"

    conflict_fixture, conflict_true = classified_attempt("conflict", classified_true)
    conflict_false = conflict_fixture.service.compose_and_persist_attempt(
        intake=conflict_fixture.intake,
        authorities=replace(
            conflict_fixture.authorities,
            facet_denominator=None,
            classification_offer=offer,
            classification=classified_false,
        ),
        context=_context(conflict_fixture.intake.evaluation_input_refs[0].artifact_id),
        evaluated_at=evaluated_at,
    )
    conflict = conflict_fixture.service.reduce_decisions(
        evidence=(
            conflict_fixture.persisted.owner_evidence,
            conflict_true.owner_evidence,
            conflict_false.owner_evidence,
        )
    )
    assert set(conflict.conflicting_refs) == {
        conflict_true.decision_ref,
        conflict_false.decision_ref,
    }
    assert conflict.reconciliation_status == "not_established"
    assert conflict.near_miss_classification_status == "not_established"
    assert conflict_true.decision.decision_id not in conflict.denominator_decision_ids


class _UnusedAuthorityResolver:
    def resolve(self, artifact_ref):
        raise AssertionError(f"unexpected authority resolution: {artifact_ref}")


class _UnusedAppointmentResolver:
    def resolve(self, appointment_ref):
        raise AssertionError(f"unexpected appointment resolution: {appointment_ref}")


class _EmptyVerifierRegistry:
    def resolve(self, evidence_contract_id: str):
        del evidence_contract_id
        return None


class _BlockedAuthorityResolver:
    def resolve(self, artifact_ref):
        return EvalSafetyAuthorityResolution(
            status="blocked",
            artifact_ref=artifact_ref,
            blocker_codes=("polisyos.eval_safety.authority_unresolved@1.0.0",),
            predicate_provenance=("not_established",),
            resolved_at=_NOW,
        )


class _BlockedAppointmentResolver:
    def resolve(self, appointment_ref):
        return EvalSafetyAppointmentResolution(
            status="blocked",
            appointment_ref=appointment_ref,
            appointment=None,
            blocker_codes=("polisyos.eval_safety.verifier_unappointed@1.0.0",),
            predicate_provenance=("not_established",),
            verified_at=_NOW,
        )


def test_blocked_non_simulation_persists_ordered_chain_without_certificate(tmp_path) -> None:
    service, artifact_store = _service(tmp_path)
    source = artifact_store.put_json(
        {"input": "real-world"},
        opts=PutOptions(kind="test.eval-input", media_type="application/json"),
    )
    source_ref = _ref(str(source.artifact_id), "test.eval-input")
    basis_ref_seed = _ref("sha256:" + "a" * 64, "test.mode-basis")
    producer_ref = _ref("sha256:" + "b" * 64, "test.basis-producer")
    verifier_ref = _ref("sha256:" + "c" * 64, "test.basis-verifier")
    basis_requirement = EvalSafetyRequirement(
        requirement_id="unseen.minimum@1.0.0",
        evidence_contract_id="unseen.minimum.evidence@1.0.0",
        authority_purpose="attempted_evaluation_safety",
        applicability_scope=EvalSafetyAllApplicability(),
        warning_expires_after=None,
    )
    basis = EvalSafetyModeBasis.build(
        schema_version="policyos.eval-safety.mode-basis.v1",
        rule_version="eval-safety-rule-v1",
        profiles=(
            EvalSafetyModeProfile(mode="field_pilot", all_of=(basis_requirement,)),
        ),
        producer_authority_ref=producer_ref,
        verifier_receipt_ref=verifier_ref,
        valid_from=_NOW,
        valid_until=None,
    )
    basis_ref = basis_ref_seed.model_copy(update={"content_hash": basis.content_hash})
    registry_ref = _ref("sha256:" + "d" * 64, "test.facet-registry")
    denominator_ref = _ref("sha256:" + "e" * 64, "test.facet-denominator")
    facet_source_ref = _ref("sha256:" + "f" * 64, "test.facet-source")
    pack_requirement = EvalSafetyRequirement(
        requirement_id="unseen.domain.guard@1.0.0",
        evidence_contract_id="unseen.domain.guard.evidence@1.0.0",
        authority_purpose="attempted_evaluation_safety",
        applicability_scope=EvalSafetyFacetApplicability(
            semantic_facet_registry_ref=registry_ref,
            semantic_facet_denominator_receipt_ref=denominator_ref,
            all_of=(
                EvalSafetyFacetValueRequirement(
                    facet_id="unseen.domain.facet@1.0.0",
                    source_binding_ref=facet_source_ref,
                    expected_semantic_value_hash="sha256:" + "1" * 64,
                ),
            ),
        ),
        warning_expires_after=None,
    )
    pack = DomainEvalSafetyPack.build(
        schema_version="policyos.eval-safety.domain-pack.v1",
        rule_version="eval-safety-rule-v1",
        pack_component_id=ProducerInfo(
            component="unseen.domain.pack@1.0.0",
            version="1.0.0",
        ).component,
        source_pack_ref=_ref("sha256:" + "2" * 64, "test.source-pack"),
        mode_basis_ref=basis_ref,
        semantic_facet_registry_ref=registry_ref,
        semantic_facet_denominator_receipt_ref=denominator_ref,
        verifier_appointment_refs=(
            _ref("sha256:" + "7" * 64, "test.verifier-appointment"),
        ),
        profiles=(EvalSafetyModeProfile(mode="field_pilot", all_of=(pack_requirement,)),),
        valid_from=_NOW,
        valid_until=None,
    )
    pack_ref = _ref("sha256:" + "6" * 64, "test.domain-pack").model_copy(
        update={"content_hash": pack.content_hash}
    )
    intake = EvaluationAttemptIntake(
        attempt_id="attempt-c02-blocked-chain",
        evaluator_owner_id=ProducerInfo(
            component="polisyos.runtime.test.evaluator@1.0.0",
            version="1.0.0",
        ).component,
        design_problem_ref="sha256:" + "0" * 64,
        candidate_ref=_ref("sha256:" + "3" * 64, "test.candidate"),
        world_model_record_ref=_ref("sha256:" + "4" * 64, "test.world-model"),
        requested_mode_token="field_pilot",  # noqa: S106 - evaluation mode, not a secret.
        mode_resolution=resolve_evaluation_mode("field_pilot"),
        domain_hint="unseen-domain",
        domain_pack_ref=pack_ref,
        target_population_scope_ref=_ref("sha256:" + "5" * 64, "test.population"),
        evaluation_input_refs=(source_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=source_ref,
                input_class="real_world",
                predicate_provenance="independently_reconciled",
            ),
        ),
        evidence_refs=(),
        requested_at=_NOW,
        intended_start_at=_NOW,
        requested_rule_version="eval-safety-rule-v1",
        external_executor_identity_ref=None,
    )
    authorities = EvaluationSafetyAttemptAuthorities(
        mode_basis_ref=basis_ref,
        mode_basis=basis,
        pack_ref=pack_ref,
        pack=pack,
        semantic_facet_denominator_receipt_ref=(
            pack.semantic_facet_denominator_receipt_ref
        ),
        facet_registry=None,
        facet_denominator=None,
        authority_resolver=_BlockedAuthorityResolver(),
        appointment_resolver=_BlockedAppointmentResolver(),
        verifier_registry=_EmptyVerifierRegistry(),
        evidence=(),
        classification_offer=None,
        classification=None,
        certificate_issue_cause_ref=None,
    )
    persisted = service.compose_and_persist_attempt(
        intake=intake,
        authorities=authorities,
        context=_context(source_ref.artifact_id),
        evaluated_at=_NOW,
    )

    assert persisted.request_ref is not None
    assert persisted.pack_admission_ref is not None
    assert persisted.decision.safety.status == "blocked"
    assert persisted.certificate_ref is None
    assert persisted.revision_nodes == ()
    replayed = service.reconcile_persisted_attempt(
        material=EvaluationSafetyReplayMaterial(
            intake_ref=persisted.intake_ref,
            request_ref=persisted.request_ref,
            mode_basis_ref=basis_ref,
            mode_basis=basis,
            pack_ref=pack_ref,
            pack=pack,
            facet_registry=None,
            facet_denominator=None,
            authority_resolver=authorities.authority_resolver,
            appointment_resolver=authorities.appointment_resolver,
            verifier_registry=authorities.verifier_registry,
            evidence=(),
            classification=None,
            decision_ref=persisted.decision_ref,
            certificate_ref=None,
            revision_nodes=(),
            decision_evaluated_at=_NOW,
            revalidated_at=_NOW,
        )
    )
    assert replayed is not None
    assert replayed.decision == persisted.decision


def test_invalid_mode_persists_intake_and_typed_block_without_request(tmp_path) -> None:
    service, artifact_store = _service(tmp_path)
    source = artifact_store.put_json(
        {"input": "real-world"},
        opts=PutOptions(kind="test.eval-input", media_type="application/json"),
    )
    source_ref = _ref(str(source.artifact_id), "test.eval-input")
    intake = EvaluationAttemptIntake(
        attempt_id="attempt-c02-invalid-mode",
        evaluator_owner_id=ProducerInfo(
            component="polisyos.runtime.test.evaluator@1.0.0",
            version="1.0.0",
        ).component,
        design_problem_ref="sha256:" + "0" * 64,
        candidate_ref=_ref("sha256:" + "3" * 64, "test.candidate"),
        world_model_record_ref=_ref("sha256:" + "4" * 64, "test.world-model"),
        requested_mode_token=None,
        mode_resolution=resolve_evaluation_mode(None),
        domain_hint="unseen-domain",
        domain_pack_ref=None,
        target_population_scope_ref=_ref("sha256:" + "5" * 64, "test.population"),
        evaluation_input_refs=(source_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=source_ref,
                input_class="real_world",
                predicate_provenance="independently_reconciled",
            ),
        ),
        evidence_refs=(),
        requested_at=_NOW,
        intended_start_at=_NOW,
        requested_rule_version=None,
        external_executor_identity_ref=None,
    )
    persisted = service.compose_and_persist_attempt(
        intake=intake,
        authorities=EvaluationSafetyAttemptAuthorities(
            mode_basis_ref=None,
            mode_basis=None,
            pack_ref=None,
            pack=None,
            semantic_facet_denominator_receipt_ref=None,
            facet_registry=None,
            facet_denominator=None,
            authority_resolver=_UnusedAuthorityResolver(),
            appointment_resolver=_UnusedAppointmentResolver(),
            verifier_registry=_EmptyVerifierRegistry(),
            evidence=(),
            classification_offer=None,
            classification=None,
            certificate_issue_cause_ref=None,
        ),
        context=_context(source_ref.artifact_id),
        evaluated_at=_NOW,
    )

    assert persisted.request_ref is None
    assert persisted.certificate_ref is None
    assert persisted.revision_nodes == ()
    assert persisted.decision.safety.status == "blocked"
    assert "polisyos.eval_safety.evaluation_mode_missing@1.0.0" in (
        persisted.decision.safety.blocker_codes
    )

    material = EvaluationSafetyReplayMaterial(
        intake_ref=persisted.intake_ref,
        request_ref=None,
        mode_basis_ref=None,
        mode_basis=None,
        pack_ref=None,
        pack=None,
        facet_registry=None,
        facet_denominator=None,
        authority_resolver=_UnusedAuthorityResolver(),
        appointment_resolver=_UnusedAppointmentResolver(),
        verifier_registry=_EmptyVerifierRegistry(),
        evidence=(),
        classification=None,
        decision_ref=persisted.decision_ref,
        certificate_ref=None,
        revision_nodes=(),
        decision_evaluated_at=_NOW,
        revalidated_at=_NOW,
    )
    replayed = service.reconcile_persisted_attempt(material=material)
    assert replayed is not None
    assert replayed.decision == persisted.decision


def test_cas_replay_rejects_swapped_intake_request_and_decision_refs(tmp_path) -> None:
    service, artifact_store = _service(tmp_path)
    source = artifact_store.put_json(
        {"input": "real-world"},
        opts=PutOptions(kind="test.eval-input", media_type="application/json"),
    )
    source_ref = _ref(str(source.artifact_id), "test.eval-input")
    intake = EvaluationAttemptIntake(
        attempt_id="attempt-c02-swapped-ref",
        evaluator_owner_id=ProducerInfo(
            component="polisyos.runtime.test.evaluator@1.0.0",
            version="1.0.0",
        ).component,
        design_problem_ref="sha256:" + "0" * 64,
        candidate_ref=_ref("sha256:" + "3" * 64, "test.candidate"),
        world_model_record_ref=_ref("sha256:" + "4" * 64, "test.world-model"),
        requested_mode_token="unknown-mode",  # noqa: S106 - evaluation mode, not a secret.
        mode_resolution=resolve_evaluation_mode("unknown-mode"),
        domain_hint="unseen-domain",
        domain_pack_ref=None,
        target_population_scope_ref=_ref("sha256:" + "5" * 64, "test.population"),
        evaluation_input_refs=(source_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=source_ref,
                input_class="real_world",
                predicate_provenance="independently_reconciled",
            ),
        ),
        evidence_refs=(),
        requested_at=_NOW,
        intended_start_at=_NOW,
        requested_rule_version=None,
        external_executor_identity_ref=None,
    )
    authorities = EvaluationSafetyAttemptAuthorities(
        mode_basis_ref=None,
        mode_basis=None,
        pack_ref=None,
        pack=None,
        semantic_facet_denominator_receipt_ref=None,
        facet_registry=None,
        facet_denominator=None,
        authority_resolver=_UnusedAuthorityResolver(),
        appointment_resolver=_UnusedAppointmentResolver(),
        verifier_registry=_EmptyVerifierRegistry(),
        evidence=(),
        classification_offer=None,
        classification=None,
        certificate_issue_cause_ref=None,
    )
    persisted = service.compose_and_persist_attempt(
        intake=intake,
        authorities=authorities,
        context=_context(source_ref.artifact_id),
        evaluated_at=_NOW,
    )
    material = EvaluationSafetyReplayMaterial(
        intake_ref=persisted.intake_ref,
        request_ref=None,
        mode_basis_ref=None,
        mode_basis=None,
        pack_ref=None,
        pack=None,
        facet_registry=None,
        facet_denominator=None,
        authority_resolver=authorities.authority_resolver,
        appointment_resolver=authorities.appointment_resolver,
        verifier_registry=authorities.verifier_registry,
        evidence=(),
        classification=None,
        decision_ref=persisted.decision_ref,
        certificate_ref=None,
        revision_nodes=(),
        decision_evaluated_at=_NOW,
        revalidated_at=_NOW,
    )

    assert service.reconcile_persisted_attempt(material=material) is not None
    assert (
        service.reconcile_persisted_attempt(
            material=replace(material, intake_ref=persisted.decision_ref)
        )
        is None
    )
    assert (
        service.reconcile_persisted_attempt(
            material=replace(material, decision_ref=persisted.intake_ref)
        )
        is None
    )


def test_eval_safety_projection_packet_is_strict_and_informational_only(tmp_path) -> None:
    _core, persisted, reduction = _persisted_reduction(tmp_path, None)
    service, _artifact_store = _service(tmp_path)
    written = service.persist_metrics_projection(
        reduction=reduction,
        context=_context(persisted.decision.safety.intake_ref.artifact_id),
        generated_at=_NOW,
    )
    projection = written.projection

    assert set(projection.authority_surface_packet.surfaces) == {
        "run",
        "artifact",
        "lineage",
        "dashboard",
    }
    assert evaluation_safety_metrics_projection_identity("artifact").purpose == (
        "runtime_closeout_authority"
    )
    assert evaluation_safety_metrics_projection_identity("dashboard").purpose == (
        "dashboard_display"
    )
    decision = authority_surface_decision(
        projection.model_dump(mode="json"),
        surface="artifact",
        purpose="runtime_closeout_authority",
    )
    assert not decision.blocking
    denied_payload = projection.model_dump(mode="json")
    denied_payload["authority_boundary"]["authoritative_for"] = ["dashboard_display"]
    denied_payload["authority_surface_packet"]["boundary"]["authoritative_for"] = [
        "dashboard_display"
    ]
    blocked = authority_surface_decision(
        denied_payload,
        surface="artifact",
        purpose="runtime_closeout_authority",
    )
    assert blocked.status != "allowed"
    with pytest.raises(ValueError):
        EvalSafetyCertificate.model_validate(projection.model_dump(mode="json"))


def test_service_signature_has_no_executor_callback_or_kwargs() -> None:
    forbidden = {"executor", "callback", "action", "transport", "scheduler"}
    public_callables = {
        name: value
        for name, value in inspect.getmembers(EvaluationSafetyPersistenceService)
        if not name.startswith("_") and callable(value)
    }
    assert public_callables
    for method in public_callables.values():
        signature = inspect.signature(method)
        parameter_text = " ".join(
            f"{parameter.name}:{parameter.annotation!s}".lower()
            for parameter in signature.parameters.values()
        )
        assert not any(name in parameter_text for name in forbidden)
        assert not forbidden.intersection(signature.parameters)
        assert all(
            parameter.kind
            not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
            for parameter in signature.parameters.values()
        )
