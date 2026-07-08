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
)
from polisyos.pdc._impl.layer2_design_search import (
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateSummary,
    ValueCalibrationReceipt,
    ValueGateReceipt,
    ValueTransportReceipt,
)
from polisyos.runtime.quality.grounding_bind import GroundingPromotabilityResolution
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
    assert receipt.authority_derivation_trace is not None
    assert receipt.risk_spend.total_declared_delta == pytest.approx(0.002)
    assert receipt.risk_spend.within_budget is True
    assert validate_canonical_promotion_receipt(receipt) == ()


def test_ungrounded_candidate_stays_shadow_by_real_grounding_owner() -> None:
    receipt = run_canonical_promotion_sequence(
        _promotion_input(
            summary=_summary(current_valid=False, grounding_status="grounded_shadow"),
            grounding_promotability=None,
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


def test_contract_testing_bind_attempting_real_promotion_is_non_promotable() -> None:
    non_promotable = _grounding_resolution(promotable=False, reason="non_production_anchor_scope")
    receipt = run_canonical_promotion_sequence(
        _promotion_input(grounding_promotability=non_promotable)
    )

    assert receipt.promoted is False
    assert "identification:single_obligation_fail" in receipt.refusal_reasons
    assert "non_production_anchor_scope" in _obligation(
        receipt,
        PromotionObligationClass.IDENTIFICATION,
    ).detail


def test_scope_insufficient_obligation_does_not_vacuously_pass() -> None:
    receipt = run_canonical_promotion_sequence(_promotion_input(s8_value_posture=None))

    assert receipt.promoted is False
    value = _obligation(receipt, PromotionObligationClass.VALUE)
    assert value.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    assert value.semantic_scope == "scope_insufficient"
    vacuous_value = PromotionObligationRecord.model_construct(
        obligation_class=value.obligation_class,
        gate_id=value.gate_id,
        status=PromotionObligationStatus.SATISFIED,
        reason=None,
        owner_ref=value.owner_ref,
        detail=value.detail,
        evidence_refs=value.evidence_refs,
        semantic_scope="scope_insufficient",
    )
    obligations = tuple(
        vacuous_value if item.obligation_class == PromotionObligationClass.VALUE else item
        for item in receipt.obligations
    )
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert {issue["code"] for issue in issues} == {"obligation_class_vacuously_passed"}


def test_unseen_non_panel_value_receipt_flows_unchanged() -> None:
    value = _value_receipt(method_fqn="frontier.unseen.scenario_set@1", representation="scenario_set")
    receipt = run_canonical_promotion_sequence(_promotion_input(value_receipt=value))

    assert receipt.promoted is True
    assert receipt.value_method_family == "frontier.unseen.scenario_set@1"
    assert receipt.value_receipt_ref == value.value_ref


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
    kwargs = {
        "candidate_summary": summary,
        "value_receipt": value_receipt,
        "grounding_promotability": _grounding_resolution(),
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
            PromotionRiskSpendRecord(
                obligation_class=PromotionObligationClass.EFFECT,
                certificate_ref="gyk://entailment-witness/current",
                instrument="gyk_entailment",
                declared_delta_spend=0.001,
            ),
        ),
        "promotion_mode": "contract_testing",
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


def _grounding_resolution(
    *,
    promotable: bool = True,
    reason: str = "owned_production_anchor_resolved",
) -> GroundingPromotabilityResolution:
    return GroundingPromotabilityResolution(
        promotable=promotable,
        reason=reason,
        certificate_id="cg2_cert_1111111111111111",
        decision="bind",
        authority_scope="production" if promotable else "contract_testing",
        certificate_promotable_claim=promotable,
        store_authority_scope="production" if promotable else "contract_testing",
        owned_anchor_id="cg2_anchor",
        certificate_anchor_content_hash=_hash("5"),
        store_anchor_content_hash=_hash("5"),
        reference_epoch_match=True,
        content_hash_valid=True,
    )


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


def _hash(seed: str) -> str:
    return "sha256:" + seed * 64
