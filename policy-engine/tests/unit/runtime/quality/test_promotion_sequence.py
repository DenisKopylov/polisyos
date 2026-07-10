from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    AuthorityDerivationTrace,
    PromotionObligationClass,
    PromotionObligationRecord,
    PromotionObligationStatus,
    PromotionRiskSpendRecord,
    gy_content_hash,
)
from polisyos.pdc._impl.layer2_design_search import (
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateSummary,
    ValueCalibrationReceipt,
    ValueGateReceipt,
    ValueTransportReceipt,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingBindGate,
    GroundingDecisionCertificate,
    recompute_grounding_decision_content_hash,
)
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalPromotionInput,
    LegacyPromotionStrangleReceipt,
    _gate_outcome_hash,
    recompute_authority_trace_hash,
    run_canonical_promotion_sequence,
    validate_canonical_promotion_receipt,
)


def test_fully_grounded_contract_lane_promotes_with_trace_and_spend() -> None:
    receipt = run_canonical_promotion_sequence(_promotion_input())

    assert receipt.promoted is True
    assert receipt.status == "grounded_partial_admissible"
    assert receipt.promotion_lane == "contract_testing"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "non_production_anchor_scope"
    assert receipt.authority_derivation_trace is not None
    assert receipt.risk_spend.total_declared_delta == pytest.approx(0.001)
    assert receipt.risk_spend.within_budget is True
    assert _obligation(receipt, PromotionObligationClass.EFFECT).status == (
        PromotionObligationStatus.SCOPE_INSUFFICIENT
    )
    assert _obligation(receipt, PromotionObligationClass.MEASUREMENT).status == (
        PromotionObligationStatus.SCOPE_INSUFFICIENT
    )
    assert validate_canonical_promotion_receipt(receipt) == ()


def test_ungrounded_candidate_stays_shadow_by_real_grounding_owner() -> None:
    receipt = run_canonical_promotion_sequence(
        _promotion_input(
            summary=_summary(current_valid=False, grounding_status="grounded_shadow"),
        )
    )

    assert receipt.promoted is False
    assert "identification:single_obligation_fail" in receipt.refusal_reasons


def test_uncalibrated_candidate_stays_shadow() -> None:
    value = _value_receipt(calibration_status="blocked")
    receipt = run_canonical_promotion_sequence(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert "calibration:single_obligation_fail" in receipt.refusal_reasons


def test_untransportable_candidate_stays_shadow() -> None:
    value = _value_receipt(transport_status="blocked")
    receipt = run_canonical_promotion_sequence(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert "slot:single_obligation_fail" in receipt.refusal_reasons


def test_timeout_unknown_never_promotes_or_fabricates_block() -> None:
    receipt = run_canonical_promotion_sequence(_promotion_input(force_proof_timeout=True))

    assert receipt.promoted is False
    assert receipt.status == "shadow"
    effect = _obligation(receipt, PromotionObligationClass.EFFECT)
    assert effect.status == PromotionObligationStatus.UNKNOWN
    assert "effect:proof_timeout" in receipt.refusal_reasons


def test_lower_boundary_wins_over_optimistic_declared_transform() -> None:
    receipt = run_canonical_promotion_sequence(
        _promotion_input(
            declared_authority_transform={
                "requested_evidence_kind": "measurement",
                "requested_decision_grade": "decision_admissible",
            }
        )
    )

    assert receipt.promoted is True
    assert receipt.computed_authority_boundary.decision_grade == "advisory_admissible"
    assert receipt.authority_derivation_trace is not None
    assert receipt.authority_derivation_trace.transform_mismatch_disposition == "downgraded"


def test_no_self_promotion_rejected_by_trace_guard() -> None:
    artifact = ArtifactRef(
        artifact_id="n9.self.promotion",
        artifact_type="runtime.quality.n9_promotion_receipt",
        content_hash=_hash("1"),
        schema_ref="policyos.policy_design_case.layer3_gy.n9_promotion.v1",
        uri="pdc://n9/self",
        version="v1",
    )

    with pytest.raises(ValueError, match="authority_transform hints cannot self-promote"):
        AuthorityDerivationTrace(
            operation_invocation_id="n9.self",
            output_artifact_ref=artifact,
            declared_authority_transform={
                "requested_evidence_kind": "measurement",
                "requested_decision_grade": "decision_admissible",
            },
            computed_evidence_kind="transport",
            computed_decision_grade="advisory_admissible",
            producer_root_classes=["llm_candidate"],
            method_classification="source_flip_probe",
            applicability_result_ref="n9://probe",
            resulting_authority_boundary_ref="n9.self.boundary",
            transform_mismatch_disposition="upgraded",
        )


def test_no_cg2_owner_grant_stays_shadow() -> None:
    receipt = run_canonical_promotion_sequence(
        _promotion_input(
            grounding_decision_certificate=None,
            credal_reference=None,
        )
    )

    assert receipt.promoted is False
    assert "identification:single_obligation_fail" in receipt.refusal_reasons
    assert "resolve_grounding_decision_promotability" in _obligation(
        receipt,
        PromotionObligationClass.IDENTIFICATION,
    ).owner_ref


def test_contract_testing_bind_receipt_is_intrinsically_non_promotable() -> None:
    receipt = run_canonical_promotion_sequence(_promotion_input())

    assert receipt.promoted is True
    assert receipt.promotion_lane == "contract_testing"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "non_production_anchor_scope"


def test_scope_insufficient_obligation_does_not_vacuously_pass() -> None:
    receipt = run_canonical_promotion_sequence(_promotion_input())

    assert receipt.promoted is True
    assert receipt.consumer_promotable is False
    effect = _obligation(receipt, PromotionObligationClass.EFFECT)
    assert effect.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    assert effect.semantic_scope == "scope_insufficient"
    vacuous_value = PromotionObligationRecord.model_construct(
        obligation_class=effect.obligation_class,
        gate_id=effect.gate_id,
        status=PromotionObligationStatus.SATISFIED,
        reason=None,
        owner_ref=effect.owner_ref,
        detail=effect.detail,
        evidence_refs=effect.evidence_refs,
        semantic_scope="scope_insufficient",
    )
    obligations = tuple(
        vacuous_value if item.obligation_class == PromotionObligationClass.EFFECT else item
        for item in receipt.obligations
    )
    gate_outcome_hash = _gate_outcome_hash(obligations)
    assert receipt.authority_derivation_trace is not None
    trace = receipt.authority_derivation_trace.model_copy(
        update={"gate_outcome_hash": gate_outcome_hash}
    )
    trace = trace.model_copy(
        update={"trace_content_hash": recompute_authority_trace_hash(trace)}
    )
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": gate_outcome_hash,
            "authority_derivation_trace": trace,
            "trace_content_hash": trace.trace_content_hash,
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert {issue["code"] for issue in issues} == {"obligation_class_vacuously_passed"}


def test_scope_insufficient_cannot_mint_production_authority() -> None:
    receipt = run_canonical_promotion_sequence(_promotion_input())
    payload = receipt.model_dump(mode="json")
    payload.update(
        {
            "promotion_lane": "production",
            "consumer_promotable": True,
            "non_promotable_reason": None,
        }
    )

    with pytest.raises(ValueError, match="scope_insufficient_cannot_mint_authoritative_promotion"):
        receipt.__class__.model_validate(payload)


def test_unseen_non_panel_value_receipt_flows_unchanged() -> None:
    value = _value_receipt(method_fqn="frontier.unseen.scenario_set@1", representation="scenario_set")
    receipt = run_canonical_promotion_sequence(_promotion_input(value_receipt=value))

    assert receipt.promoted is True
    assert receipt.value_method_family == "frontier.unseen.scenario_set@1"
    assert receipt.value_receipt_ref == value.value_ref


def test_forged_g4_ref_is_refused_by_owner_resolution() -> None:
    receipt = run_canonical_promotion_sequence(
        _promotion_input(g4_governed_promotion_ref="pdc://fake/g4/not-resolved")
    )

    assert receipt.promoted is False
    param = _obligation(receipt, PromotionObligationClass.PARAM)
    assert param.status == PromotionObligationStatus.FAILED
    assert "governed_promotion_record_not_found" in param.detail


def test_gyk_witness_pointer_is_not_a_supported_input() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        _promotion_input(entailment_witness_ref="gyk://forged-witness")


def test_invented_measurement_marker_does_not_supply_authority() -> None:
    value = _value_receipt()
    marked_value = value.value_outer_set.model_copy(
        update={"calibration_scope": {"measurement_status": "pass"}}
    )
    receipt = run_canonical_promotion_sequence(
        _promotion_input(value_receipt=value.model_copy(update={"value_outer_set": marked_value}))
    )
    assert _obligation(receipt, PromotionObligationClass.MEASUREMENT).status == (
        PromotionObligationStatus.SCOPE_INSUFFICIENT
    )


def test_data_trust_typed_fields_fail_data_obligation() -> None:
    value = _value_receipt()
    data_bad = value.value_outer_set.model_copy(
        update={
            "data_trust": DataTrust(
                tier="unit",
                trust_cap=0.2,
                trust_multiplier=1.0,
                promotion_floor=0.5,
                authority_ref="data-trust://unit/insufficient",
            )
        }
    )
    receipt = run_canonical_promotion_sequence(
        _promotion_input(value_receipt=value.model_copy(update={"value_outer_set": data_bad}))
    )
    assert _obligation(receipt, PromotionObligationClass.DATA).status == (
        PromotionObligationStatus.FAILED
    )


def test_s6_typed_posture_fails_implementation_obligation() -> None:
    s6_bad = _s6_posture().model_copy(
        update={
            "overall_posture": "blocked",
            "limitation_summary": "S6 capacity feasibility owner blocked the candidate.",
        }
    )
    receipt = run_canonical_promotion_sequence(
        _promotion_input(s6_blind_spot_posture=s6_bad)
    )
    assert _obligation(receipt, PromotionObligationClass.IMPLEMENTATION).status == (
        PromotionObligationStatus.FAILED
    )


def test_reintroduced_champion_path_turns_strangle_receipt_red() -> None:
    receipt = LegacyPromotionStrangleReceipt.recompute()

    assert receipt.status == "strangled"
    assert receipt.live_policy_champion_callers == ()


def test_hand_edited_derivation_trace_is_rejected() -> None:
    receipt = run_canonical_promotion_sequence(_promotion_input())
    assert receipt.authority_derivation_trace is not None
    trace = receipt.authority_derivation_trace.model_copy(
        update={"trace_content_hash": _hash("9")}
    )
    edited = receipt.model_copy(
        update={
            "authority_derivation_trace": trace,
            "trace_content_hash": _hash("9"),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert {issue["code"] for issue in issues} == {"authority_derivation_trace_hash_drift"}
    assert recompute_authority_trace_hash(receipt.authority_derivation_trace) != _hash("9")


def test_delta_spend_budget_is_enforced() -> None:
    receipt = run_canonical_promotion_sequence(
        _promotion_input(
            risk_budget_delta=0.001,
            risk_spends=(
                PromotionRiskSpendRecord(
                    obligation_class=PromotionObligationClass.CALIBRATION,
                    certificate_ref="n8://calibration",
                    instrument="s10_calibration",
                    declared_delta_spend=0.002,
                ),
            ),
        )
    )

    assert receipt.promoted is False
    assert "calibration:joint_obligation_inconsistency" in receipt.refusal_reasons
    assert receipt.risk_spend.within_budget is False


def _promotion_input(**overrides: object) -> CanonicalPromotionInput:
    summary = overrides.pop("summary", _summary())
    value_receipt = overrides.pop("value_receipt", _value_receipt())
    reference, decision = _cg2_contract_bind()
    kwargs = {
        "candidate_summary": summary,
        "value_receipt": value_receipt,
        "grounding_decision_certificate": decision,
        "credal_reference": reference,
        "s6_blind_spot_posture": _s6_posture(),
        "s7_delegation_posture": _s7_posture(),
        "s8_value_posture": _s8_posture(),
        "declared_authority_transform": {
            "requested_evidence_kind": "transport",
            "requested_decision_grade": "advisory_admissible",
        },
        "risk_spends": (
            PromotionRiskSpendRecord(
                obligation_class=PromotionObligationClass.CALIBRATION,
                certificate_ref="n8://calibration",
                instrument="s10_calibration",
                declared_delta_spend=0.001,
            ),
        ),
    }
    kwargs.update(overrides)
    return CanonicalPromotionInput(**kwargs)


def _summary(
    *,
    current_valid: bool = True,
    grounding_status: str = "current_valid",
) -> CandidateSummary:
    return CandidateSummary(
        candidate_id="candidate_n9",
        content_hash=_hash("2"),
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status=grounding_status,  # type: ignore[arg-type]
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.95,
        current_valid=current_valid,
        value_status="value_ready",
        value_decision_grade="high",
        value_ref=_hash("3"),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )


def _value_receipt(
    *,
    calibration_status: str = "pass",
    transport_status: str = "direct",
    method_fqn: str = "causal.inference.did.standard@1",
    representation: str = "interval_box",
) -> ValueGateReceipt:
    world_hash = _hash("4")
    data_trust = DataTrust(
        tier="unit",
        trust_cap=1.0,
        trust_multiplier=1.0,
        promotion_floor=0.5,
        authority_ref="data-trust://unit",
    )
    if representation == "scenario_set":
        value_set = ValueOuterSet(
            representation="scenario_set",
            identification_status="partial",
            assumption_status="externally_supported",
            data_trust=data_trust,
            world_model_record_ref=world_hash,
            epoch="2026",
            representation_status="certified",
        )
    else:
        value_set = ValueOuterSet.interval_box(
            coordinates=("welfare",),
            lower=(1.0,),
            upper=(1.0,),
            identification_mode="point",
            assumptions=(),
            assumption_status="externally_supported",
            calibration_scope={"scope": "unit"},
            data_trust=data_trust,
            world_model_record_ref=world_hash,
            epoch="2026",
            representation_status="certified",
        )
    return ValueGateReceipt(
        candidate_id="candidate_n9",
        evaluation_mode="simulate_only",
        selected_method_fqn=method_fqn,
        method_selection_trace=(method_fqn,),
        identification_status=value_set.identification_status,
        value_outer_set=value_set,
        transport_receipt=ValueTransportReceipt(
            status=transport_status,  # type: ignore[arg-type]
            world_model_record_id="wmr_n9",
            world_model_record_content_hash=world_hash,
            transport_result_ref="transport://unit",
            transport_status="identified" if transport_status != "blocked" else "blocked",
            transport_mode="direct",
            identification_engine="unit",
        ),
        calibration_receipt=ValueCalibrationReceipt(
            status=calibration_status,  # type: ignore[arg-type]
            forecast_tier="observable_calibrated",
            calibration_record_ref="s10://unit",
            issue_codes=() if calibration_status == "pass" else ("forecast_calibration_blocked",),
        ),
        world_model_record_id="wmr_n9",
        world_model_record_content_hash=world_hash,
        value_ref=_hash("3"),
        wall_time_ms=1.0,
        wmr_cache_status="built",
        k_world_ref_before=world_hash,
        k_world_ref_after=world_hash,
    )


def _cg2_contract_bind() -> tuple[CredalReference, object]:
    reference = _credal_reference()
    engine = GroundingRelationEngine(reference)
    cg1 = engine.certificate_for(_pure_synonym_probe(engine), proposal_id="n9-cg2-bind")
    decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    payload = decision.model_dump(mode="json")
    safe_candidate = next(
        item
        for item in payload["safe_t"]["candidates"]
        if item["relation"] == "exact" and not item["is_adversarial_countercandidate"]
    )
    safe_candidate = {**safe_candidate, "safe": True, "reason": "contract_owner_bind"}
    safe_atom_id = str(safe_candidate["atom_id"])
    payload.update(
        {
            "decision": "bind",
            "decisive_reason": "bind_eligible",
            "selected_relation": "exact",
            "bound_atom_id": safe_atom_id,
            "closed_obligations": tuple(
                sorted(
                    {
                        *payload["closed_obligations"],
                        "unit_scale_consistent",
                    }
                )
            ),
            "open_obligations": (),
            "safe_t": {
                "safe_atom_ids": (safe_atom_id,),
                "candidates": (safe_candidate,),
                "robust_singleton": True,
            },
            "revalidation": {
                **payload["revalidation"],
                "replayed_selected_relation": "exact",
                "replayed_selected_atom_id": safe_atom_id,
                "selected_relation_reproduced": True,
                "selected_atom_reproduced": True,
            },
        }
    )
    payload["content_hash"] = recompute_grounding_decision_content_hash(payload)
    payload["certificate_id"] = (
        f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    )
    return reference, GroundingDecisionCertificate.model_validate(payload)


def _boundary(*, grade: str = "decision_admissible") -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id="n9.test.boundary",
        authoritative_for=["grounded_partial_admissible_policy_design"],
        may_not_use_for=["production_deployment"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=["policyos.policy_design_case.layer3_gy.n9_promotion.v1"],
        evidence_kind="measurement",
        decision_grade=grade,  # type: ignore[arg-type]
    )


def _s6_posture() -> Layer2S6BlindSpotPostureInput:
    return Layer2S6BlindSpotPostureInput(
        overall_posture="clear_fail_closed",
        measurability_record_ref="s6://measure",
        aggregation_validity_record_ref="s6://aggregation",
        capacity_feasibility_record_ref="s6://capacity",
        mandate_legitimacy_record_ref="s6://mandate",
        strategic_response_record_ref="s6://strategic",
        system_dynamics_handoff_required=False,
        regime_reissue_required=False,
        limitation_summary="S6 clear for unit contract lane.",
        false_clear_penalty=0.0,
    )


def _s7_posture() -> Layer2S7DelegationPostureInput:
    now = datetime(2026, 7, 8, tzinfo=UTC)
    return Layer2S7DelegationPostureInput(
        delegation_contract_ref="s7://delegation",
        decision_rights_matrix_ref="s7://rights",
        human_decision_request_ref="s7://request",
        human_decision_record_ref="s7://decision",
        decision_class_id="governed_pilot",
        required_role="policy_owner",
        interaction_mode="recorded_decision",
        disposition="recorded_valid_decision",
        available_actions=["approve"],
        decision_action_exercised="approve",
        five_rights_requirement={"required": True},
        five_rights_check={"status": "pass"},
        value_stakes_impact="bounded",
        attention_cost_rank=1,
        responsibility_integrity_status="pass",
        mandate_record_ref="s6://mandate",
        s6_mandate_firewall_disposition="pass",
        requested_at=now,
        decided_at=now,
        voi_rank=1,
        authority_boundary=_boundary(),
        governed_pilot_eligible=True,
        limitation_summary="S7 valid governed-pilot decision.",
    )


def _s8_posture() -> Layer2S8ValuePostureInput:
    return Layer2S8ValuePostureInput(
        value_choice_provenance_ref="s8://value-choice",
        authorized_value_schedule_ref="s8://schedule",
        objective_function_provenance_ref="s8://objective",
        pareto_archive_ref="s8://pareto",
        value_tradeoff_disclosure_ref="s8://tradeoff",
        mandate_record_ref="s6://mandate",
        s6_mandate_firewall_disposition="pass",
        ranking_mode="ranked_with_authorized_values",
        disposition="authorized",
        p20_firewall_status="pass",
        p22_firewall_status="pass",
        value_provenance_completeness=1.0,
        value_authorization_decision_refs=["s8://decision"],
        handoff_rows=[{"handoff": "s8"}],
        limitation_summary="S8 authorized value posture.",
        authority_boundary=_boundary(),
    )


def _obligation(receipt: object, obligation_class: PromotionObligationClass):
    return next(item for item in receipt.obligations if item.obligation_class == obligation_class)


def _credal_reference() -> CredalReference:
    edges = [
        _operator_edge("tax_relief_rate", minimum=0.0, maximum=0.5, unit="ratio"),
        _target_edge("tax_relief_rate", "global.tax_rate"),
        _lex_edge("tax_relief_statute", "tax_relief_rate"),
        _operator_edge("budget_allocation_multiplier", minimum=0.0, maximum=2.0, unit="ratio"),
        _target_edge("budget_allocation_multiplier", "government.balance"),
        _lex_edge("budget_law", "budget_allocation_multiplier"),
        _world_slot("global.tax_rate", unit="ratio"),
        _world_slot("government.balance", unit="usd"),
        _world_slot("household_cells.disposable_income", unit="usd"),
        _world_slot("household_cells.transfer_intensity", unit="ratio"),
        _policy_slot("tax_slot", "global.tax_rate"),
        _policy_slot("budget_slot", "government.balance"),
        _policy_slot("transfer_slot", "household_cells.transfer_intensity"),
    ]
    edge_index = {edge.key: edge for edge in edges}
    component_versions = {
        "L2": "unit-l2",
        "L3": "unit-l3",
        "L6": _component_hash(edges, prefix="L6_"),
        "WMR": "unit-wmr",
    }
    reference_hash = gy_content_hash(
        {
            "component_versions": component_versions,
            "edges": [edge.to_payload() for edge in sorted(edges, key=lambda item: item.key)],
        }
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=edge_index,
    )


def _operator_edge(
    op: str,
    *,
    minimum: float,
    maximum: float,
    unit: str,
) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "parameter_domain": {
                        "kind": "range",
                        "max_value": maximum,
                        "min_value": minimum,
                        "unit": unit,
                        "value_type": "float",
                    },
                },
                "unit_test_operator",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _target_edge(op: str, target: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_WORLD_SLOT",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "target_world_slots": [target],
                    "world_model_record_id": "unit-wmr",
                },
                "unit_test_target",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _lex_edge(law_token: str, op: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_LEX_INTERVENTION_MAP",
        edge_id=law_token,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"law_token": law_token, "knob_id": op},
                "unit_test_lex_map",
            ),
        ),
        provenance={"owner": "L6", "source": "unit"},
    ).with_content_hash()


def _world_slot(slot: str, *, unit: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_WORLD_SLOT",
        edge_id=slot,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion("fixed", {"world_slot": slot}, "unit_test_wmr_slot"),
        ),
        provenance={"owner": "WMR", "source": "unit"},
        unit=unit,
    ).with_content_hash()


def _policy_slot(policy_slot: str, world_slot: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_POLICY_SLOT_MAP",
        edge_id=f"{policy_slot}:{world_slot}",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"policy_slot": policy_slot, "world_slot": world_slot},
                "unit_test_policy_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "unit"},
    ).with_content_hash()


def _component_hash(edges: list[CredalReferenceEdge], *, prefix: str) -> str:
    return gy_content_hash(
        [
            edge.content_hash
            for edge in sorted(edges, key=lambda item: item.key)
            if edge.modality.startswith(prefix)
        ]
    )


def _tax_atom(engine: GroundingRelationEngine) -> object:
    return next(
        item
        for item in engine.reference_atoms
        if item.signature.op == "tax_relief_rate" and "global.tax_rate" in item.signature.X_do
    )


def _pure_synonym_probe(engine: GroundingRelationEngine) -> dict[str, object]:
    atom = _tax_atom(engine)
    signature = atom.signature.model_dump(mode="json")
    signature["op"] = "tax_credit_rate"
    signature["effect_path"] = [
        "tax_credit_rate",
        *list(atom.signature.X_do),
        *list(atom.signature.outcome),
    ]
    signature["modal_claims"] = {
        "NL": {
            "op": "tax_credit_rate",
            "target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
        "L6": {"knob": "tax_relief_rate"},
        "do_AST": {"op": "tax_credit_rate", "target": atom.signature.X_do[0]},
        "method": {
            "treatment_op": "tax_credit_rate",
            "treatment_target": atom.signature.X_do[0],
            "outcome": atom.signature.outcome[0],
            "estimand": atom.signature.estimand,
        },
    }
    return {
        "raw_text": "levy credit-rate alias for the exact same tax relief do-query.",
        "signature": signature,
    }


def _hash(seed: str) -> str:
    return "sha256:" + seed * 64
