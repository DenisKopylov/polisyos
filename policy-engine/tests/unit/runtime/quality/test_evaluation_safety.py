"""Behavioral falsifiers for the attempted-evaluation safety owner."""

from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel

from polisyos.core import components as core_components
from polisyos.core.artifacts import ArtifactID as CoreArtifactID
from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
from polisyos.pdc import ArtifactRef

NOW = datetime(2026, 8, 27, 12, tzinfo=UTC)


def _digest(char: str) -> str:
    return f"sha256:{char * 64}"


def _ref(char: str, kind: str = "test", *, content_hash: str | None = None) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_digest(char),
        artifact_type=kind,
        content_hash=content_hash or _digest(char),
        schema_ref=f"schema://{kind}",
        uri=f"cas://{char}",
        version="1.0.0",
    )


def _core_ref(char: str, kind: str = "test") -> CoreArtifactRef:
    return CoreArtifactRef(
        artifact_id=CoreArtifactID.model_validate(_digest(char)),
        kind=kind,
        media_type="application/json",
    )


def _intake(
    *,
    mode: str = "field_pilot",
    input_class: str = "real_world",
    domain_pack_ref: ArtifactRef | None = None,
) -> object:
    from polisyos.runtime.quality import evaluation_safety as es
    from polisyos.runtime.quality.evaluation_modes import resolve_evaluation_mode

    return es.EvaluationAttemptIntake(
        attempt_id="attempt-transit-1",
        candidate_ref=_ref("6", "candidate"),
        world_model_record_ref=_ref("7", "wmr"),
        requested_mode_token=mode,
        mode_resolution=resolve_evaluation_mode(mode),
        domain_hint="never-seen-domain",
        domain_pack_ref=domain_pack_ref or _ref("8", "domain-pack"),
        target_population_scope_ref=_ref("9", "population"),
        evaluation_input_refs=(_ref("a", "input"),),
        evaluation_input_provenance=(
            es.EvaluationInputProvenance(
                input_ref=_ref("a", "input"),
                input_class=input_class,
                predicate_provenance=(
                    "not_established" if input_class == "not_established" else "recomputed"
                ),
            ),
        ),
        evidence_refs=(_ref("b", "evidence"), _ref("c", "evidence")),
        requested_at=NOW,
        intended_start_at=NOW + timedelta(hours=1),
        requested_rule_version="transit_lab.eval_safety@1.0.0",
        external_executor_identity_ref=None,
    )


def _request(
    intake: object,
    intake_ref: ArtifactRef,
    denominator_ref: ArtifactRef | None = None,
) -> object:
    from polisyos.runtime.quality import evaluation_safety as es

    assert intake.mode_resolution.canonical_mode is not None
    assert intake.domain_pack_ref is not None
    return es.EvaluationAttemptRequest(
        intake_ref=intake_ref,
        attempt_id=intake.attempt_id,
        candidate_ref=intake.candidate_ref,
        world_model_record_ref=intake.world_model_record_ref,
        evaluation_mode=intake.mode_resolution.canonical_mode,
        domain_pack_ref=intake.domain_pack_ref,
        semantic_facet_denominator_receipt_ref=(
            denominator_ref or _ref("2", "facet-denominator")
        ),
        target_population_scope_ref=intake.target_population_scope_ref,
        evidence_refs=intake.evidence_refs,
        requested_at=intake.requested_at,
        intended_start_at=intake.intended_start_at,
        rule_version="transit_lab.eval_safety@1.0.0",
        external_executor_identity_ref=None,
    )


def _requirement(
    *,
    registry_ref: ArtifactRef | None = None,
    denominator_ref: ArtifactRef | None = None,
    semantic_hash: str = _digest("4"),
    requirement_id: str = "transit_lab.crowding_guard@1.0.0",
    evidence_contract_id: str = "transit_lab.crowding_evidence@1.0.0",
) -> object:
    from polisyos.runtime.quality import evaluation_safety as es

    return es.EvalSafetyRequirement(
        requirement_id=requirement_id,
        evidence_contract_id=evidence_contract_id,
        authority_purpose="attempted_evaluation_safety",
        applicability_scope=(
            es.EvalSafetyAllApplicability()
            if registry_ref is None or denominator_ref is None
            else es.EvalSafetyFacetApplicability(
                semantic_facet_registry_ref=registry_ref,
                semantic_facet_denominator_receipt_ref=denominator_ref,
                all_of=(
                    es.EvalSafetyFacetValueRequirement(
                        facet_id="transit_lab.platform_type@1.0.0",
                        source_binding_ref=_ref("3", "source"),
                        expected_semantic_value_hash=semantic_hash,
                    ),
                ),
            )
        ),
        warning_expires_after=None,
    )


def _result(
    request: object,
    request_ref: ArtifactRef,
    requirement: object,
    *,
    evidence_ref: ArtifactRef,
    verifier_component_id: core_components.ComponentId,
) -> object:
    from polisyos.runtime.quality import evaluation_safety as es

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
            "transit_lab.sensor@1.0.0"
        ),
        verifier_component_id=verifier_component_id,
        verification_receipt_ref=_ref("c", "verification"),
        status="passed",
        blocker_codes=(),
        predicate_provenance=("independently_reconciled",),
        evaluated_at=NOW,
        valid_until=NOW + timedelta(days=1),
    )


def _facet_basis() -> tuple[object, object, ArtifactRef, ArtifactRef]:
    from polisyos.runtime.quality import semantic_epoch

    registry = semantic_epoch.build_facet_registry(
        (
            semantic_epoch.SemanticFacetRegistration(
                facet_id="transit_lab.platform_type@1.0.0",
                source_binding_ref=_digest("3"),
            ),
        )
    )
    query = semantic_epoch.EpochResolutionQuery(
        scope_identity=semantic_epoch.build_epoch_scope_identity(
            schema_profile="transit-lab", identity_bytes=b"never-seen-domain"
        ),
        authority_purpose="attempted_evaluation_safety",
        valid_effect_coordinate_evidence_ref=_core_ref("a"),
        valid_effect_coordinate_ref=_digest("a"),
        visibility_knowledge_cutoff_evidence_ref=_core_ref("b"),
        visibility_knowledge_cutoff_ref=_digest("b"),
        purpose_admission_cutoff_evidence_ref=_core_ref("c"),
        purpose_admission_cutoff_ref=_digest("c"),
        requested_query_context_ref=_digest("d"),
    )
    value = semantic_epoch.SemanticFacetValue(
        facet_id="transit_lab.platform_type@1.0.0",
        source_record_ref=_core_ref("3", "source"),
        source_record_content_hash=_digest("3"),
        semantic_value_hash=_digest("4"),
        annotation_hash=_digest("5"),
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
                "facet_id": value.facet_id,
                "semantic_value_hash": value.semantic_value_hash,
                "status": value.status,
                "failure_code": value.failure_code,
            }
        ],
    }
    denominator = semantic_epoch.SemanticFacetDenominatorReceipt(
        query=query,
        facet_registry_content_hash=registry.registry_content_hash,
        values=(value,),
        denominator_hash=semantic_epoch._model_hash(  # noqa: SLF001
            semantic_epoch._FACET_DENOMINATOR_PREFIX, denominator_payload  # noqa: SLF001
        ),
        status="resolved",
        failure_codes=(),
        predicate_class="independently_reconciled",
    )
    return (
        registry,
        denominator,
        _ref("1", "facet-registry", content_hash=registry.registry_content_hash),
        _ref("2", "facet-denominator", content_hash=denominator.denominator_hash),
    )


def test_strict_mode_resolution_never_defaults_to_simulation() -> None:
    from polisyos.runtime.quality.evaluation_modes import resolve_evaluation_mode

    observed = tuple(resolve_evaluation_mode(token) for token in (None, "unknown", "simulation_only"))
    assert tuple(row.status for row in observed) == ("missing", "invalid", "invalid")
    assert all(row.canonical_mode is None for row in observed)
    assert tuple(row.blocker_code for row in observed) == (
        "polisyos.eval_safety.evaluation_mode_missing@1.0.0",
        "polisyos.eval_safety.evaluation_mode_unknown@1.0.0",
        "polisyos.eval_safety.evaluation_mode_unknown@1.0.0",
    )
    explicit = resolve_evaluation_mode("simulate_only")
    assert (explicit.status, explicit.canonical_mode, explicit.blocker_code) == (
        "accepted",
        "simulate_only",
        None,
    )


def test_promotion_state_injection_cannot_change_safety_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O0-PROMOTION-INDEPENDENCE-C01: post-core offers cannot alter safety."""

    from polisyos.runtime.quality import evaluation_safety as es

    def annotation_names(annotation: object, seen: set[object] | None = None) -> set[str]:
        visited = seen or set()
        if annotation in visited:
            return set()
        visited.add(annotation)
        names = {getattr(annotation, "__name__", str(annotation)).lower()}
        for argument in get_args(annotation):
            names |= annotation_names(argument, visited)
        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            for field in annotation.model_fields.values():
                names |= annotation_names(field.annotation, visited)
        return names

    signature = inspect.signature(es.decide_evaluation_safety_core, eval_str=True)
    assert "promotion" not in " ".join(signature.parameters)
    assert all(
        parameter.kind is not inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    nested_names = {
        name
        for parameter in signature.parameters.values()
        for name in annotation_names(parameter.annotation)
    }
    assert not any(
        token in name
        for name in nested_names
        for token in ("promotion", "near_miss", "classification")
    )
    external_calls = 0

    def external_spy(**_values: object) -> None:
        nonlocal external_calls
        external_calls += 1

    monkeypatch.setattr(es, "verify_near_miss_classification", external_spy)
    intake = _intake()
    intake_ref = _ref("5", "intake")
    request_ref = _ref("d", "request")
    core = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=_request(intake, intake_ref),
        request_ref=request_ref,
        admitted_pack=None,
        mode_basis=None,
        requirement_results=(),
        evaluated_at=NOW,
    )
    events = tuple(
        es.build_evaluation_safety_decision_event(core=core, classification=offer)
        for offer in (
            None,
            {"promoted": True, "consumer_promotable": True},
            {"forged": "passing"},
        )
    )
    observables = tuple(
        (
            event.safety.status,
            event.safety.blocker_codes,
            event.safety.certificate_eligible,
            external_calls,
            es.evaluation_safety_core_bytes(event.safety),
            event.decision_id,
            event.safety.safety_semantic_hash,
        )
        for event in events
    )
    assert core.status == "blocked" and not core.certificate_eligible
    assert len(set(observables)) == 1
    assert external_calls == 0
    assert all(event.promotion_safe_facet is None and not event.near_miss for event in events)
    forged = object.__new__(es.VerifiedNearMissClassification)
    object.__setattr__(forged, "offer_ref", _ref("a", "classification-offer"))
    object.__setattr__(forged, "validation_basis_ref", _ref("b", "validation-basis"))
    object.__setattr__(forged, "promotion_safe_facet", True)
    forged_event = es.build_evaluation_safety_decision_event(
        core=core,
        classification=forged,
    )
    assert forged_event.promotion_safe_facet is None and not forged_event.near_miss
    public_core = es.EvaluationSafetyDecisionCore.model_validate(
        core.model_dump(mode="python")
    )
    with pytest.raises(ValueError, match="decision_core_unreconciled"):
        es.build_evaluation_safety_decision_event(
            core=public_core,
            classification=None,
        )


def test_unseen_domain_pack_resolves_or_refuses_without_engine_conditional() -> None:
    """An unseen namespaced pack passes or refuses from data, never fixture names."""

    from polisyos.runtime.quality import evaluation_safety as es

    registry, denominator, registry_ref, denominator_ref = _facet_basis()
    basis_requirement = _requirement(
        requirement_id="polisyos.eval_safety.ratified_harm_floor@1.0.0",
        evidence_contract_id="polisyos.eval_safety.ratified_harm_evidence@1.0.0",
    )
    pack_requirement = _requirement(
        registry_ref=registry_ref,
        denominator_ref=denominator_ref,
    )
    with pytest.raises(ValueError, match="basis_applicability_not_universal"):
        es.EvalSafetyModeBasis.build(
            schema_version="polisyos.eval_safety.mode_basis.v1",
            rule_version="transit_lab.eval_safety@1.0.0",
            profiles=(
                es.EvalSafetyModeProfile(mode="field_pilot", all_of=(pack_requirement,)),
            ),
            producer_authority_ref=_ref("d", "authority"),
            verifier_receipt_ref=_ref("e", "verification"),
            valid_from=NOW - timedelta(days=1),
            valid_until=NOW + timedelta(days=1),
        )
    basis = es.EvalSafetyModeBasis.build(
        schema_version="polisyos.eval_safety.mode_basis.v1",
        rule_version="transit_lab.eval_safety@1.0.0",
        profiles=(
            es.EvalSafetyModeProfile(mode="field_pilot", all_of=(basis_requirement,)),
        ),
        producer_authority_ref=_ref("d", "authority"),
        verifier_receipt_ref=_ref("e", "verification"),
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
    )
    mode_basis_ref = _ref("f", "mode-basis", content_hash=basis.content_hash)

    class AuthorityResolver:
        def resolve(self, artifact_ref: ArtifactRef) -> es.EvalSafetyAuthorityResolution:
            return es.EvalSafetyAuthorityResolution(
                status="verified",
                artifact_ref=artifact_ref,
                blocker_codes=(),
                predicate_provenance=("independently_reconciled",),
                resolved_at=NOW,
            )

    verified_basis = es.verify_evaluation_safety_mode_basis(
        basis_ref=mode_basis_ref,
        basis=basis,
        authority_resolver=AuthorityResolver(),
        verified_at=NOW,
    )
    assert verified_basis is not None
    appointment_refs = (_ref("0", "appointment"), _ref("1", "appointment"))
    pack = es.DomainEvalSafetyPack.build(
        schema_version="polisyos.eval_safety.domain_pack.v1",
        rule_version="transit_lab.eval_safety@1.0.0",
        pack_component_id=core_components.ComponentId(
            "transit_lab.platform_crowding_guard@1.0.0"
        ),
        source_pack_ref=_ref("8", "domain-pack-source"),
        mode_basis_ref=mode_basis_ref,
        semantic_facet_registry_ref=registry_ref,
        semantic_facet_denominator_receipt_ref=denominator_ref,
        verifier_appointment_refs=appointment_refs,
        profiles=(
            es.EvalSafetyModeProfile(mode="field_pilot", all_of=(pack_requirement,)),
        ),
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
    )
    pack_ref = _ref("8", "domain-pack", content_hash=pack.content_hash)
    intake = _intake(domain_pack_ref=pack_ref)
    intake_ref = _ref("5", "intake")
    request_ref = _ref("d", "request")
    request = _request(intake, intake_ref, denominator_ref)
    appointments = (
        es.EvalSafetyVerifierAppointment(
            appointment_id="polisyos.eval_safety.ratified_harm_appointment@1.0.0",
            evidence_contract_id=basis_requirement.evidence_contract_id,
            verifier_component_id=core_components.ComponentId(
                "polisyos.eval_safety.ratified_harm_verifier@1.0.0"
            ),
            component_discovery_manifest_ref=_ref("a", "component-manifest"),
            appointing_authority_ref=_ref("b", "authority"),
            appointment_verification_receipt_ref=_ref("c", "verification"),
            valid_from=NOW - timedelta(days=1),
            valid_until=NOW + timedelta(days=1),
        ),
        es.EvalSafetyVerifierAppointment(
            appointment_id="transit_lab.crowding_verifier_appointment@1.0.0",
            evidence_contract_id=pack_requirement.evidence_contract_id,
            verifier_component_id=core_components.ComponentId(
                "transit_lab.independent_verifier@1.0.0"
            ),
            component_discovery_manifest_ref=_ref("d", "component-manifest"),
            appointing_authority_ref=_ref("e", "authority"),
            appointment_verification_receipt_ref=_ref("f", "verification"),
            valid_from=NOW - timedelta(days=1),
            valid_until=NOW + timedelta(days=1),
        ),
    )

    class Resolver:
        def __init__(self, present: bool = True) -> None:
            self.present = present

        def resolve(self, ref: ArtifactRef) -> es.EvalSafetyAppointmentResolution:
            appointment = next(
                (
                    row
                    for candidate_ref, row in zip(appointment_refs, appointments, strict=True)
                    if candidate_ref == ref
                ),
                None,
            )
            present = self.present and appointment is not None
            return es.EvalSafetyAppointmentResolution(
                status="verified" if present else "blocked",
                appointment_ref=ref,
                appointment=appointment if present else None,
                blocker_codes=() if present else (
                    "polisyos.eval_safety.verifier_unappointed@1.0.0",
                ),
                predicate_provenance=("independently_reconciled",),
                verified_at=NOW,
            )

    verifier_calls: list[str] = []

    class Verifier:
        def __init__(self, appointment: object) -> None:
            self.appointment = appointment
            self.component_id = appointment.verifier_component_id

        def verify(self, **values: object) -> object:
            requirement = values["requirement"]
            evidence_ref = values["evidence_ref"]
            verifier_calls.append(requirement.requirement_id)
            return _result(
                request,
                request_ref,
                requirement,
                evidence_ref=evidence_ref,
                verifier_component_id=self.component_id,
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

    self_verifying_appointment = appointments[1].model_copy(
        update={"verifier_component_id": pack.pack_component_id}
    )
    aliased_authority_appointment = appointments[1].model_copy(
        update={"appointing_authority_ref": appointment_refs[1]}
    )

    class AlteredResolver(Resolver):
        def __init__(self, replacement: object) -> None:
            super().__init__()
            self.replacement = replacement

        def resolve(self, ref: ArtifactRef) -> es.EvalSafetyAppointmentResolution:
            resolved = super().resolve(ref)
            if ref != appointment_refs[1]:
                return resolved
            return resolved.model_copy(update={"appointment": self.replacement})

    class AlteredRegistry(Registry):
        def __init__(self, replacement: object) -> None:
            self.replacement = replacement

        def resolve(self, evidence_contract_id: str) -> Verifier | None:
            if evidence_contract_id == pack_requirement.evidence_contract_id:
                return Verifier(self.replacement)
            return super().resolve(evidence_contract_id)

    engine_digest = hashlib.sha256(Path(es.__file__).read_bytes()).hexdigest()
    admission_args = {
        "pack_ref": request.domain_pack_ref,
        "mode_basis_ref": mode_basis_ref,
        "mode_basis": verified_basis,
        "facet_registry": registry,
        "facet_denominator": denominator,
        "verifier_registry": Registry(),
        "request": request,
        "admitted_at": NOW,
    }
    admitted = es.admit_domain_evaluation_safety_pack(
        **admission_args, pack=pack, appointment_resolver=Resolver()
    )
    results = es.verify_evaluation_safety_requirements(
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted,
        evidence_by_contract={
            basis_requirement.evidence_contract_id: request.evidence_refs[0],
            pack_requirement.evidence_contract_id: request.evidence_refs[1],
        },
        appointment_resolver=Resolver(),
        verifier_registry=Registry(),
        evaluated_at=NOW,
    )
    core = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted,
        mode_basis=verified_basis,
        requirement_results=results,
        evaluated_at=NOW,
    )
    decision = es.build_evaluation_safety_decision_event(core=core, classification=None)
    decision_ref = _ref("1", "decision", content_hash=decision.content_hash)
    certificate = es.build_evaluation_safety_certificate(
        core=core,
        request=request,
        request_ref=request_ref,
        decision=decision,
        decision_ref=decision_ref,
    )
    certificate_ref = _ref("2", "certificate", content_hash=certificate.content_hash)
    revision = es.EvalSafetyCertificateRevision.issue(
        revision_lineage_id=certificate.revision_lineage_id,
        certificate_ref=certificate_ref,
        verified_cause_ref=_ref("3", "cause"),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW,
    )
    issue_ref = _ref("4", "certificate-revision", content_hash=revision.content_hash)
    issue_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=issue_ref,
        revision=revision,
    )
    context = es.EvaluationExecutionContext(
        intake_ref=intake_ref,
        evaluator_owner_id=core_components.ComponentId(
            "polisyos.foundry.value_port@1.0.0"
        ),
        evaluation_mode=request.evaluation_mode,
        candidate_ref=request.candidate_ref,
        world_model_record_ref=request.world_model_record_ref,
        target_population_scope_ref=request.target_population_scope_ref,
        rule_version=request.rule_version,
        intended_start_at=request.intended_start_at,
        evaluation_input_refs=intake.evaluation_input_refs,
        evaluation_input_provenance=intake.evaluation_input_provenance,
        eval_safety_certificate_ref=certificate_ref,
        eval_safety_revision_head_ref=issue_ref,
    )
    consumer = es.verify_evaluation_safety_consumer_admission(
        context=context,
        intake=intake,
        request=request,
        request_ref=request_ref,
        certificate_ref=certificate_ref,
        certificate=certificate,
        decision_ref=decision_ref,
        decision=decision,
        decision_core=core,
        revision_nodes=(issue_node,),
        current_requirement_results=results,
        verified_at=NOW,
    )
    assert admitted.status == "admitted"
    assert tuple(row.requirement_id for row in admitted.effective_profile.all_of) == (
        basis_requirement.requirement_id,
        pack_requirement.requirement_id,
    )
    assert verifier_calls == [
        basis_requirement.requirement_id,
        pack_requirement.requirement_id,
    ]
    assert core.status == "passed" and core.certificate_eligible
    assert certificate.evaluation_mode == "field_pilot"
    assert revision.action == "issue" and consumer.status == "verified"
    changed_intake = intake.model_copy(
        update={
            "evaluation_input_provenance": (
                es.EvaluationInputProvenance(
                    input_ref=intake.evaluation_input_refs[0],
                    input_class="not_established",
                    predicate_provenance="not_established",
                ),
            )
        }
    )
    replayed = es.verify_evaluation_safety_consumer_admission(
        context=context,
        intake=changed_intake,
        request=request,
        request_ref=request_ref,
        certificate_ref=certificate_ref,
        certificate=certificate,
        decision_ref=decision_ref,
        decision=decision,
        decision_core=core,
        revision_nodes=(issue_node,),
        current_requirement_results=results,
        verified_at=NOW,
    )
    assert replayed.status == "blocked" and replayed.blocker_codes

    def revision_ref(row: object, char: str) -> ArtifactRef:
        return _ref(char, "certificate-revision", content_hash=row.content_hash)

    revoke = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="revoke",
        certificate_ref=certificate_ref,
        verified_cause_ref=_ref("5", "cause"),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=1),
    )
    fork_a = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=_ref("6", "cause"),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=1),
    )
    fork_b = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=_ref("7", "cause"),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=2),
    )
    cycle_tail = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=revision_ref(fork_a, "8"),
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=_ref("8", "cause"),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=2),
    )
    cyclic_head = fork_a.model_copy(
        update={"predecessor_ref": revision_ref(cycle_tail, "9")}
    )

    def revision_node(row: object, char: str) -> object:
        return es.EvalSafetyCertificateRevisionNode(
            revision_ref=revision_ref(row, char),
            revision=row,
        )

    def consumer_status(
        revision_nodes: tuple[object, ...],
        current_results: tuple[object, ...] = results,
        bound_decision_ref: ArtifactRef = decision_ref,
        bound_context: object = context,
    ) -> str:
        return es.verify_evaluation_safety_consumer_admission(
            context=bound_context,
            intake=intake,
            request=request,
            request_ref=request_ref,
            certificate_ref=certificate_ref,
            certificate=certificate,
            decision_ref=bound_decision_ref,
            decision=decision,
            decision_core=core,
            revision_nodes=revision_nodes,
            current_requirement_results=current_results,
            verified_at=NOW,
        ).status

    assert consumer_status((issue_node, revision_node(revoke, "5"))) == "blocked"
    assert consumer_status(
        (issue_node, revision_node(fork_a, "6"), revision_node(fork_b, "7"))
    ) == "blocked"
    assert consumer_status(
        (
            issue_node,
            es.EvalSafetyCertificateRevisionNode.model_construct(
                revision_ref=revision_ref(cyclic_head, "8"),
                revision=cyclic_head,
            ),
            revision_node(cycle_tail, "9"),
        )
    ) == "blocked"
    assert consumer_status((issue_node,), ()) == "blocked"
    parsed_revision = es.EvalSafetyCertificateRevision.model_validate(
        revision.model_dump(mode="python")
    )
    parsed_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=issue_ref,
        revision=parsed_revision,
    )
    assert consumer_status((parsed_node,)) == "blocked"
    replayed_revisions = es.reconcile_evaluation_safety_revisions(
        revisions=(parsed_revision,),
        cause_resolver=AuthorityResolver(),
    )
    replayed_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=issue_ref,
        revision=replayed_revisions[0],
    )
    assert consumer_status((replayed_node,)) == "verified"
    fork_a_node = revision_node(fork_a, "6")
    fork_a_context = context.model_copy(
        update={"eval_safety_revision_head_ref": fork_a_node.revision_ref}
    )
    assert consumer_status(
        (issue_node, fork_a_node), bound_context=fork_a_context
    ) == "verified"
    aliased_issue_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=_ref(
            "b", "certificate-revision", content_hash=revision.content_hash
        ),
        revision=revision,
    )
    assert consumer_status(
        (aliased_issue_node, fork_a_node), bound_context=fork_a_context
    ) == "blocked"
    replay_inputs = {
        "intake_ref": intake_ref,
        "intake": intake,
        "request_ref": request_ref,
        "request": request,
        "mode_basis_ref": mode_basis_ref,
        "mode_basis": es.EvalSafetyModeBasis.model_validate(
            verified_basis.model_dump(mode="python")
        ),
        "pack_ref": pack_ref,
        "pack": es.DomainEvalSafetyPack.model_validate(pack.model_dump(mode="python")),
        "facet_registry": registry,
        "facet_denominator": denominator,
        "authority_resolver": AuthorityResolver(),
        "appointment_resolver": Resolver(),
        "verifier_registry": Registry(),
        "evidence_by_contract": {
            basis_requirement.evidence_contract_id: request.evidence_refs[0],
            pack_requirement.evidence_contract_id: request.evidence_refs[1],
        },
        "classification": None,
        "decision_ref": decision_ref,
        "decision": es.EvaluationSafetyDecisionEvent.model_validate(
            decision.model_dump(mode="python")
        ),
        "certificate_ref": certificate_ref,
        "certificate": es.EvalSafetyCertificate.model_validate(
            certificate.model_dump(mode="python")
        ),
        "revision_nodes": (
            es.EvalSafetyCertificateRevisionNode(
                revision_ref=issue_ref,
                revision=parsed_revision,
            ),
        ),
    }
    replay = es.replay_evaluation_safety_authority(
        **replay_inputs,
        decision_evaluated_at=NOW,
        revalidated_at=NOW,
    )
    assert replay is not None
    replay_consumer = es.verify_evaluation_safety_consumer_admission(
        context=context,
        intake=intake,
        request=request,
        request_ref=request_ref,
        certificate_ref=certificate_ref,
        certificate=replay.certificate,
        decision_ref=decision_ref,
        decision=replay.decision,
        decision_core=replay.decision_core,
        revision_nodes=replay.revision_nodes,
        current_requirement_results=replay.current_requirement_results,
        verified_at=NOW,
    )
    assert replay_consumer.status == "verified"
    assert "intake_ref" not in intake.model_dump(mode="json")
    assert request.intake_ref == intake_ref
    assert all(
        row.request_ref == request_ref
        for row in replay.decision_requirement_results
    )
    assert replay.decision_core.request_ref == request_ref
    assert replay.certificate.request_ref == request_ref
    later_replay = es.replay_evaluation_safety_authority(
        **replay_inputs,
        decision_evaluated_at=NOW,
        revalidated_at=NOW + timedelta(minutes=5),
    )
    wrong_decision_time = es.replay_evaluation_safety_authority(
        **replay_inputs,
        decision_evaluated_at=NOW + timedelta(minutes=5),
        revalidated_at=NOW + timedelta(minutes=5),
    )
    assert later_replay is not None
    assert later_replay.decision.content_hash == decision.content_hash
    assert wrong_decision_time is None
    substituted_revision_ref = _ref(
        "a", "certificate-revision", content_hash=revision.content_hash
    )
    substituted_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=substituted_revision_ref,
        revision=revision,
    )
    assert consumer_status((substituted_node,)) == "blocked"
    substituted_decision_ref = _ref(
        "a", "decision", content_hash=decision.content_hash
    )
    assert consumer_status(
        (issue_node,), bound_decision_ref=substituted_decision_ref
    ) == "blocked"
    assert hashlib.sha256(Path(es.__file__).read_bytes()).hexdigest() == engine_digest
    assert b"transit_lab" not in Path(es.__file__).read_bytes()

    missing_domain_result = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted,
        mode_basis=verified_basis,
        requirement_results=results[:1],
        evaluated_at=NOW,
    )
    public_result = es.EvalSafetyRequirementResult.model_validate(
        results[0].model_dump(mode="python")
    )
    marker_only_result = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted,
        mode_basis=verified_basis,
        requirement_results=(public_result, results[1]),
        evaluated_at=NOW,
    )
    public_admission = es.EvalSafetyPackAdmissionReceipt.model_validate(
        admitted.model_dump(mode="python")
    )
    marker_only_admission = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=request,
        request_ref=request_ref,
        admitted_pack=public_admission,
        mode_basis=verified_basis,
        requirement_results=results,
        evaluated_at=NOW,
    )
    assert all(
        row.status == "blocked" and row.blocker_codes
        for row in (missing_domain_result, marker_only_result, marker_only_admission)
    )

    wrong_facet_requirement = _requirement(
        registry_ref=registry_ref,
        denominator_ref=denominator_ref,
        semantic_hash=_digest("e"),
    )
    wrong_facet_pack = es.DomainEvalSafetyPack.build(
        **pack.model_dump(
            mode="python", exclude={"content_hash", "profiles", "source_pack_ref"}
        ),
        source_pack_ref=_ref("8", "domain-pack-source"),
        profiles=(
            es.EvalSafetyModeProfile(
                mode="field_pilot", all_of=(wrong_facet_requirement,)
            ),
        ),
    )
    basis_override_pack = es.DomainEvalSafetyPack.build(
        **pack.model_dump(
            mode="python", exclude={"content_hash", "profiles", "source_pack_ref"}
        ),
        source_pack_ref=_ref("8", "domain-pack-source"),
        profiles=(
            es.EvalSafetyModeProfile(
                mode="field_pilot",
                all_of=(
                    _requirement(
                        registry_ref=registry_ref,
                        denominator_ref=denominator_ref,
                        requirement_id=basis_requirement.requirement_id,
                        evidence_contract_id=basis_requirement.evidence_contract_id,
                    ),
                ),
            ),
        ),
    )
    changed_contract_override_pack = es.DomainEvalSafetyPack.build(
        **pack.model_dump(
            mode="python", exclude={"content_hash", "profiles", "source_pack_ref"}
        ),
        source_pack_ref=_ref("8", "domain-pack-source"),
        profiles=(
            es.EvalSafetyModeProfile(
                mode="field_pilot",
                all_of=(
                    _requirement(
                        registry_ref=registry_ref,
                        denominator_ref=denominator_ref,
                        requirement_id=basis_requirement.requirement_id,
                        evidence_contract_id=(
                            "transit_lab.changed_basis_contract@1.0.0"
                        ),
                    ),
                ),
            ),
        ),
    )
    changed_contract_override = es.admit_domain_evaluation_safety_pack(
        **{
            **admission_args,
            "pack_ref": _ref(
                "8",
                "domain-pack",
                content_hash=changed_contract_override_pack.content_hash,
            ),
        },
        pack=changed_contract_override_pack,
        appointment_resolver=Resolver(),
    )
    self_verifying = es.admit_domain_evaluation_safety_pack(
        **{
            **admission_args,
            "verifier_registry": AlteredRegistry(self_verifying_appointment),
        },
        pack=pack,
        appointment_resolver=AlteredResolver(self_verifying_appointment),
    )
    aliased_authority = es.admit_domain_evaluation_safety_pack(
        **{
            **admission_args,
            "verifier_registry": AlteredRegistry(aliased_authority_appointment),
        },
        pack=pack,
        appointment_resolver=AlteredResolver(aliased_authority_appointment),
    )
    refusals = (
        es.admit_domain_evaluation_safety_pack(
            **admission_args, pack=None, appointment_resolver=Resolver()
        ),
        es.admit_domain_evaluation_safety_pack(
            **admission_args, pack=pack, appointment_resolver=Resolver(False)
        ),
        es.admit_domain_evaluation_safety_pack(
            **{**admission_args, "mode_basis": basis},
            pack=pack,
            appointment_resolver=Resolver(),
        ),
        es.admit_domain_evaluation_safety_pack(
            **{
                **admission_args,
                "pack_ref": _ref(
                    "8", "domain-pack", content_hash=wrong_facet_pack.content_hash
                ),
            },
            pack=wrong_facet_pack,
            appointment_resolver=Resolver(),
        ),
        es.admit_domain_evaluation_safety_pack(
            **{
                **admission_args,
                "pack_ref": _ref(
                    "8", "domain-pack", content_hash=basis_override_pack.content_hash
                ),
            },
            pack=basis_override_pack,
            appointment_resolver=Resolver(),
        ),
    )
    assert all(row.status == "refused" and row.blocker_codes for row in refusals)
    assert (
        "polisyos.eval_safety.profile_basis_invalid@1.0.0"
        in changed_contract_override.blocker_codes
    )
    assert all(
        "polisyos.eval_safety.verifier_independence_invalid@1.0.0"
        in row.blocker_codes
        for row in (self_verifying, aliased_authority)
    )
