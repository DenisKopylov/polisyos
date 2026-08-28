"""Behavioral falsifiers for the attempted-evaluation safety owner."""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import pytest
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from polisyos.core import components as core_components
from polisyos.core.artifacts import ArtifactID as CoreArtifactID
from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
from polisyos.pdc import ArtifactRef

NOW = datetime(2026, 8, 27, 12, tzinfo=UTC)


def _digest(char: str) -> str:
    return f"sha256:{char * 64}"


def _copy_with_recomputed_hash(
    value: BaseModel,
    *,
    hash_field: str,
    updates: dict[str, object],
) -> BaseModel:
    payload = value.model_dump(mode="python", exclude={hash_field})
    payload.update(updates)
    content_hash = _content_hash_values(payload)
    return value.model_copy(
        update={**updates, hash_field: content_hash}
    )


def _content_hash_values(values: dict[str, object]) -> str:
    encoded = json.dumps(
        to_jsonable_python(values), sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


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
        evaluator_owner_id=core_components.ComponentId(
            "polisyos.runtime.quality.foundry_value_port@1.0.0"
        ),
        design_problem_ref=_digest("4"),
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
        evaluator_owner_id=intake.evaluator_owner_id,
        design_problem_ref=intake.design_problem_ref,
        candidate_ref=intake.candidate_ref,
        world_model_record_ref=intake.world_model_record_ref,
        evaluation_mode=intake.mode_resolution.canonical_mode,
        domain_pack_ref=intake.domain_pack_ref,
        semantic_facet_denominator_receipt_ref=(
            denominator_ref or _ref("2", "facet-denominator")
        ),
        target_population_scope_ref=intake.target_population_scope_ref,
        evaluation_input_refs=intake.evaluation_input_refs,
        evaluation_input_provenance=intake.evaluation_input_provenance,
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

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality import evaluation_safety as es
    from polisyos.runtime.quality import promotion_sequence

    classification_producer = es.verify_near_miss_classification

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

    def named_ref(artifact_id: str, kind: str, content_hash: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=artifact_id,
            artifact_type=kind,
            content_hash=content_hash,
            schema_ref=f"schema://{kind}",
            uri=f"cas://{artifact_id}",
            version="1.0.0",
        )

    projection_hash = _digest("1")
    candidate_hash = _digest("2")
    value_hash = _digest("3")
    world_hash = _digest("4")
    open_ref = named_ref("open-world", "open-world", _digest("5"))
    epoch_ref = named_ref("epoch", "epoch", _digest("6"))
    design_binding = SimpleNamespace(
        model_dump=lambda **_kwargs: {"design": "bound"}
    )
    owner_projection = SimpleNamespace(
        open_world_gate=SimpleNamespace(vector_artifact_ref=open_ref),
        epoch_validity_projection=SimpleNamespace(gate_receipt_ref=epoch_ref),
        design_problem_binding=design_binding,
        projection_hash=projection_hash,
    )
    fake_receipt = SimpleNamespace(
        candidate_id="candidate-classified",
        owner_projection=owner_projection,
        schema_version="polisyos.promotion.canonical.v1",
        model_dump=lambda **_kwargs: {"receipt": "canonical"},
    )
    monkeypatch.setattr(
        promotion_sequence,
        "CanonicalPromotionReceipt",
        SimpleNamespace(model_validate=lambda _payload: fake_receipt),
    )
    monkeypatch.setattr(
        promotion_sequence,
        "validate_canonical_promotion_receipt",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        promotion_sequence,
        "promotion_receipt_allows_decision_front",
        lambda *_args, **_kwargs: True,
    )
    receipt_ref = named_ref(
        "promotion-receipt",
        "promotion-receipt",
        gy_content_hash(fake_receipt.model_dump()),
    )
    canonical_input_ref = named_ref(
        "promotion-input", "promotion-input", projection_hash
    )
    design_ref = named_ref(
        "design-binding",
        "design-binding",
        gy_content_hash(design_binding.model_dump()),
    )
    value_ref = named_ref("value", "value", value_hash)
    candidate_ref = named_ref("candidate-classified", "candidate", candidate_hash)
    world_ref = named_ref("wmr", "wmr", world_hash)
    validation_ref = named_ref("validation", "validation", projection_hash)
    offer_values = {
        "promotion_receipt_ref": receipt_ref,
        "canonical_promotion_input_ref": canonical_input_ref,
        "design_problem_binding_ref": design_ref,
        "value_receipt_ref": value_ref,
        "candidate_ref": candidate_ref,
        "world_model_record_ref": world_ref,
        "promotion_rule_version": fake_receipt.schema_version,
        "open_world_resolver_basis_ref": open_ref,
        "epoch_resolver_basis_ref": epoch_ref,
        "safety_semantic_hash": core.safety_semantic_hash,
        "offered_at": NOW,
    }
    offer = es.EvalSafetyNearMissClassificationOffer(
        **offer_values,
        content_hash=_content_hash_values(offer_values),
    )
    classification = classification_producer(
        offer=offer,
        offer_ref=named_ref("offer", "classification-offer", offer.content_hash),
        validation_basis_ref=validation_ref,
        canonical_promotion_input_ref=canonical_input_ref,
        design_problem_binding_ref=design_ref,
        value_receipt_ref=value_ref,
        candidate_ref=candidate_ref,
        world_model_record_ref=world_ref,
        promotion_rule_version=fake_receipt.schema_version,
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
    classified_event = es.build_evaluation_safety_decision_event(
        core=core,
        classification=classification,
    )
    sibling_core = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=_request(intake, intake_ref),
        request_ref=request_ref,
        admitted_pack=None,
        mode_basis=None,
        requirement_results=(),
        evaluated_at=NOW + timedelta(seconds=1),
    )
    sibling_event = es.build_evaluation_safety_decision_event(
        core=sibling_core,
        classification=classification,
    )
    assert classified_event.promotion_safe_facet is True
    assert sibling_event.promotion_safe_facet is None and not sibling_event.near_miss
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
    cause_bindings: dict[tuple[str, str], dict[str, object]] = {}

    class EchoOnlyAuthorityResolver:
        def resolve(self, artifact_ref: ArtifactRef) -> es.EvalSafetyAuthorityResolution:
            return es.EvalSafetyAuthorityResolution.model_construct(
                status="verified",
                artifact_ref=artifact_ref,
                blocker_codes=(),
                predicate_provenance=("independently_reconciled",),
                resolved_at=NOW,
            )

    class AuthorityResolver:
        def resolve(self, artifact_ref: ArtifactRef) -> es.EvalSafetyAuthorityResolution:
            if artifact_ref in (
                basis.producer_authority_ref,
                basis.verifier_receipt_ref,
            ):
                producer = artifact_ref == basis.producer_authority_ref
                return es.EvalSafetyAuthorityResolution(
                    status="verified",
                    artifact_ref=artifact_ref,
                    blocker_codes=(),
                    predicate_provenance=("independently_reconciled",),
                    resolved_at=NOW,
                    attestation_role=(
                        "producer_statement" if producer else "independent_verification"
                    ),
                    subject_refs=(mode_basis_ref,),
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
                return es.EvalSafetyAuthorityResolution(
                    status="blocked",
                    artifact_ref=artifact_ref,
                    blocker_codes=(
                        "polisyos.eval_safety.revision_cause_unresolved@1.0.0",
                    ),
                    predicate_provenance=(),
                    resolved_at=NOW,
                )
            return es.EvalSafetyAuthorityResolution(
                status="verified",
                artifact_ref=artifact_ref,
                blocker_codes=(),
                predicate_provenance=("independently_reconciled",),
                resolved_at=binding.get(
                    "resolved_at", NOW - timedelta(days=2)
                ),
                attestation_role="independent_verification",
                subject_refs=binding["subject_refs"],
                subject_schema_version=(
                    "polisyos.eval_safety.certificate_revision.v1"
                ),
                subject_rule_version=None,
                subject_purpose=binding["subject_purpose"],
                subject_effective_at=binding["subject_effective_at"],
                subject_valid_until=None,
                attesting_component_id=core_components.ComponentId(
                    "polisyos.eval_safety.revision_cause_verifier@1.0.0"
                ),
            )

    assert (
        es.verify_evaluation_safety_mode_basis(
            basis_ref=mode_basis_ref,
            basis=basis,
            authority_resolver=EchoOnlyAuthorityResolver(),
            verified_at=NOW,
        )
        is None
    )

    verified_basis = es.verify_evaluation_safety_mode_basis(
        basis_ref=mode_basis_ref,
        basis=basis,
        authority_resolver=AuthorityResolver(),
        verified_at=NOW,
    )
    assert verified_basis is not None

    class SelfAttestedBasisResolver(AuthorityResolver):
        def resolve(self, artifact_ref: ArtifactRef) -> es.EvalSafetyAuthorityResolution:
            resolved = super().resolve(artifact_ref)
            if artifact_ref == basis.verifier_receipt_ref:
                return resolved.model_copy(
                    update={
                        "attesting_component_id": core_components.ComponentId(
                            "polisyos.eval_safety.basis_producer@1.0.0"
                        )
                    }
                )
            return resolved

    assert (
        es.verify_evaluation_safety_mode_basis(
            basis_ref=mode_basis_ref,
            basis=basis,
            authority_resolver=SelfAttestedBasisResolver(),
            verified_at=NOW,
        )
        is None
    )
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

    def register_cause(
        cause_ref: ArtifactRef,
        *,
        subject_refs: tuple[ArtifactRef, ...],
        subject_purpose: str,
        subject_effective_at: datetime,
    ) -> ArtifactRef:
        cause_bindings[(cause_ref.artifact_id, cause_ref.content_hash)] = {
            "subject_refs": subject_refs,
            "subject_purpose": subject_purpose,
            "subject_effective_at": subject_effective_at,
            "resolved_at": NOW - timedelta(days=2),
        }
        return cause_ref

    revision = es.EvalSafetyCertificateRevision.issue(
        revision_lineage_id=certificate.revision_lineage_id,
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("3", "cause"),
            subject_refs=(certificate_ref,),
            subject_purpose="certificate_revision_issue",
            subject_effective_at=NOW,
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW,
    )
    with pytest.raises(ValueError, match="revision_cause_unverified"):
        es.EvalSafetyCertificateRevision.issue(
            revision_lineage_id=certificate.revision_lineage_id,
            certificate_ref=certificate_ref,
            verified_cause_ref=register_cause(
                _ref("e", "cause"),
                subject_refs=(certificate_ref,),
                subject_purpose="certificate_revision_issue",
                subject_effective_at=NOW,
            ),
            cause_resolver=AuthorityResolver(),
            effective_at=NOW + timedelta(minutes=1),
        )
    issue_ref = _ref("4", "certificate-revision", content_hash=revision.content_hash)
    issue_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=issue_ref,
        revision=revision,
    )
    context = es.EvaluationExecutionContext(
        intake_ref=intake_ref,
        evaluator_owner_id=core_components.ComponentId(
            "polisyos.runtime.quality.foundry_value_port@1.0.0"
        ),
        design_problem_ref=request.design_problem_ref,
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
    challenge = es.EvalSafetyAdmissionChallenge.fresh(
        consumer_component_id=context.evaluator_owner_id
    )
    consumer = es.verify_evaluation_safety_consumer_admission(
        context=context,
        challenge=challenge,
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
    changed_replay_context = context.model_copy(
        update={"evaluation_mode": "deployment"}
    )
    fresh_call_challenge = es.EvalSafetyAdmissionChallenge.fresh(
        consumer_component_id=context.evaluator_owner_id
    )
    fresh_consumer = es.verify_evaluation_safety_consumer_admission(
        context=context,
        challenge=fresh_call_challenge,
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
    assert es.evaluation_safety_consumer_admission_is_verified(
        consumer, context, challenge
    )
    replay_observed = (
        es.evaluation_safety_consumer_admission_is_verified(
            consumer, changed_replay_context, challenge
        ),
        es.evaluation_safety_consumer_admission_is_verified(
            consumer, context, fresh_call_challenge
        ),
    )
    assert replay_observed == (False, False)
    assert es.evaluation_safety_consumer_admission_is_verified(
        fresh_consumer, context, fresh_call_challenge
    )

    sibling_owner_admission = es.verify_evaluation_safety_consumer_admission(
        context=context.model_copy(
            update={
                "evaluator_owner_id": core_components.ComponentId(
                    "polisyos.runtime.quality.sibling_value_port@1.0.0"
                )
            }
        ),
        challenge=challenge,
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
    substituted_input_ref = _ref("e", "input")
    substituted_input_provenance = (
        es.EvaluationInputProvenance(
            input_ref=substituted_input_ref,
            input_class="real_world",
            predicate_provenance="recomputed",
        ),
    )
    substituted_input_admission = es.verify_evaluation_safety_consumer_admission(
        context=context.model_copy(
            update={
                "evaluation_input_refs": (substituted_input_ref,),
                "evaluation_input_provenance": substituted_input_provenance,
            }
        ),
        challenge=challenge,
        intake=intake.model_copy(
            update={
                "evaluation_input_refs": (substituted_input_ref,),
                "evaluation_input_provenance": substituted_input_provenance,
            }
        ),
        request=request.model_copy(
            update={
                "evaluation_input_refs": (substituted_input_ref,),
                "evaluation_input_provenance": substituted_input_provenance,
            }
        ),
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
    assert sibling_owner_admission.status == "blocked"
    assert substituted_input_admission.status == "blocked"

    weakened_basis = verified_basis.model_copy(
        update={
            "profiles": (
                es.EvalSafetyModeProfile(mode="field_pilot", all_of=()),
            )
        }
    )
    weakened_basis_admission = es.admit_domain_evaluation_safety_pack(
        **{**admission_args, "mode_basis": weakened_basis},
        pack=pack,
        appointment_resolver=Resolver(),
    )
    copied_pack_admission = admitted.model_copy(
        update={"resolved_appointment_refs": ()}
    )
    copied_pack_core = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=request,
        request_ref=request_ref,
        admitted_pack=copied_pack_admission,
        mode_basis=verified_basis,
        requirement_results=results,
        evaluated_at=NOW,
    )
    copied_result = _copy_with_recomputed_hash(
        results[0],
        hash_field="content_hash",
        updates={"valid_until": NOW + timedelta(days=365)},
    )
    copied_result_core = es.decide_evaluation_safety_core(
        intake=intake,
        intake_ref=intake_ref,
        request=request,
        request_ref=request_ref,
        admitted_pack=admitted,
        mode_basis=verified_basis,
        requirement_results=(
            copied_result,
            results[1],
        ),
        evaluated_at=NOW,
    )
    copied_core = _copy_with_recomputed_hash(
        core,
        hash_field="safety_semantic_hash",
        updates={"valid_until": NOW + timedelta(days=365)},
    )
    with pytest.raises(ValueError, match="decision_core_unreconciled"):
        es.build_evaluation_safety_decision_event(
            core=copied_core,
            classification=None,
        )
    copied_certificate_admission = es.verify_evaluation_safety_consumer_admission(
        context=context,
        challenge=challenge,
        intake=intake,
        request=request,
        request_ref=request_ref,
        certificate_ref=certificate_ref,
        certificate=certificate.model_copy(
            update={"valid_until": NOW + timedelta(days=365)}
        ),
        decision_ref=decision_ref,
        decision=decision,
        decision_core=core,
        revision_nodes=(issue_node,),
        current_requirement_results=results,
        verified_at=NOW,
    )
    copied_revision = _copy_with_recomputed_hash(
        revision,
        hash_field="content_hash",
        updates={"verified_cause_ref": _ref("f", "cause")},
    )
    copied_revision_ref = _ref(
        "f", "certificate-revision", content_hash=copied_revision.content_hash
    )
    copied_revision_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=copied_revision_ref,
        revision=copied_revision,
    )
    copied_revision_admission = es.verify_evaluation_safety_consumer_admission(
        context=context.model_copy(
            update={"eval_safety_revision_head_ref": copied_revision_ref}
        ),
        challenge=challenge,
        intake=intake,
        request=request,
        request_ref=request_ref,
        certificate_ref=certificate_ref,
        certificate=certificate,
        decision_ref=decision_ref,
        decision=decision,
        decision_core=core,
        revision_nodes=(copied_revision_node,),
        current_requirement_results=results,
        verified_at=NOW,
    )
    assert weakened_basis_admission.status == "refused"
    assert copied_pack_core.status == copied_result_core.status == "blocked"
    assert copied_certificate_admission.status == "blocked"
    assert copied_revision_admission.status == "blocked"

    missing_basis_pack = es.DomainEvalSafetyPack.build(
        **pack.model_dump(
            mode="python",
            exclude={"content_hash", "verifier_appointment_refs", "source_pack_ref"},
        ),
        source_pack_ref=_ref("8", "domain-pack-source"),
        verifier_appointment_refs=(appointment_refs[1],),
    )
    missing_basis_pack_ref = _ref(
        "e", "domain-pack", content_hash=missing_basis_pack.content_hash
    )
    missing_basis_intake = intake.model_copy(
        update={"domain_pack_ref": missing_basis_pack_ref}
    )
    missing_basis_request = request.model_copy(
        update={"domain_pack_ref": missing_basis_pack_ref}
    )
    missing_basis_appointment = es.admit_domain_evaluation_safety_pack(
        **{
            **admission_args,
            "pack_ref": missing_basis_pack_ref,
            "request": missing_basis_request,
        },
        pack=missing_basis_pack,
        appointment_resolver=Resolver(),
    )
    assert missing_basis_intake.domain_pack_ref == missing_basis_pack_ref
    assert missing_basis_appointment.status == "refused"
    assert (
        "polisyos.eval_safety.verifier_unappointed@1.0.0"
        in missing_basis_appointment.blocker_codes
    )
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
        challenge=challenge,
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
        verified_cause_ref=register_cause(
                _ref("5", "cause"),
                subject_refs=(issue_ref, certificate_ref),
                subject_purpose="certificate_revision_revoke",
                subject_effective_at=NOW,
            ),
            cause_resolver=AuthorityResolver(),
            effective_at=NOW,
        )
    fork_a = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("6", "cause"),
            subject_refs=(issue_ref, certificate_ref),
            subject_purpose="certificate_revision_supersede",
            subject_effective_at=NOW + timedelta(minutes=1),
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=1),
    )
    fork_b = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("7", "cause"),
            subject_refs=(issue_ref, certificate_ref),
            subject_purpose="certificate_revision_supersede",
            subject_effective_at=NOW + timedelta(minutes=2),
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=2),
    )
    cycle_tail = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=revision_ref(fork_a, "8"),
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("8", "cause"),
            subject_refs=(revision_ref(fork_a, "8"), certificate_ref),
            subject_purpose="certificate_revision_supersede",
            subject_effective_at=NOW + timedelta(minutes=2),
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=2),
    )
    future_revoke = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="revoke",
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("a", "cause"),
            subject_refs=(issue_ref, certificate_ref),
            subject_purpose="certificate_revision_revoke",
            subject_effective_at=NOW + timedelta(minutes=10),
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=10),
    )
    future_supersede = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("b", "cause"),
            subject_refs=(issue_ref, certificate_ref),
            subject_purpose="certificate_revision_supersede",
            subject_effective_at=NOW + timedelta(minutes=10),
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=10),
    )
    nonmonotone_supersede = es.EvalSafetyCertificateRevision.transition(
        revision_lineage_id=certificate.revision_lineage_id,
        predecessor_ref=issue_ref,
        action="supersede",
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("c", "cause"),
            subject_refs=(issue_ref, certificate_ref),
            subject_purpose="certificate_revision_supersede",
            subject_effective_at=NOW - timedelta(minutes=1),
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW - timedelta(minutes=1),
    )
    future_issue = es.EvalSafetyCertificateRevision.issue(
        revision_lineage_id=certificate.revision_lineage_id,
        certificate_ref=certificate_ref,
        verified_cause_ref=register_cause(
            _ref("d", "cause"),
            subject_refs=(certificate_ref,),
            subject_purpose="certificate_revision_issue",
            subject_effective_at=NOW + timedelta(minutes=10),
        ),
        cause_resolver=AuthorityResolver(),
        effective_at=NOW + timedelta(minutes=10),
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
        at: datetime = NOW,
    ) -> str:
        return es.verify_evaluation_safety_consumer_admission(
            context=bound_context,
            challenge=es.EvalSafetyAdmissionChallenge.fresh(
                consumer_component_id=bound_context.evaluator_owner_id
            ),
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
            verified_at=at,
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
    assert consumer_status(
        (issue_node, revision_node(future_revoke, "a"))
    ) == "verified"
    assert consumer_status(
        (issue_node, revision_node(future_supersede, "b"))
    ) == "verified"
    nonmonotone_node = revision_node(nonmonotone_supersede, "c")
    assert consumer_status(
        (issue_node, nonmonotone_node),
        bound_context=context.model_copy(
            update={"eval_safety_revision_head_ref": nonmonotone_node.revision_ref}
        ),
    ) == "blocked"
    future_issue_node = revision_node(future_issue, "d")
    assert consumer_status(
        (future_issue_node,),
        bound_context=context.model_copy(
            update={"eval_safety_revision_head_ref": future_issue_node.revision_ref}
        ),
    ) == "blocked"
    fork_a_node = revision_node(fork_a, "6")
    fork_a_context = context.model_copy(
        update={"eval_safety_revision_head_ref": fork_a_node.revision_ref}
    )
    assert consumer_status(
        (issue_node, fork_a_node),
        bound_context=fork_a_context,
        at=NOW + timedelta(minutes=1),
    ) == "verified"
    aliased_issue_node = es.EvalSafetyCertificateRevisionNode(
        revision_ref=_ref(
            "b", "certificate-revision", content_hash=revision.content_hash
        ),
        revision=revision,
    )
    assert consumer_status(
        (aliased_issue_node, fork_a_node),
        bound_context=fork_a_context,
        at=NOW + timedelta(minutes=1),
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
        challenge=es.EvalSafetyAdmissionChallenge.fresh(
            consumer_component_id=context.evaluator_owner_id
        ),
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
