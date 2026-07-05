from __future__ import annotations

import pytest

from polisyos.runtime.quality.credal_reference import replace_reference_edge
from polisyos.runtime.quality.grounding_active_controller import (
    GroundingActionCertificate,
    GroundingActionResult,
    GroundingActiveController,
    GroundingActiveControllerPolicy,
    GroundingControllerCase,
    OwnerShapedReferenceEdgeResult,
    extract_grounding_blockers,
    grounding_blocker_denominator,
    recompute_grounding_action_certificate_hash,
    unknown_blocker_fail_safe,
)
from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from tests.unit.runtime.quality.test_grounding_admission import (
    _causal_claim,
    _cg2_novel,
    _novel_transfer_probe,
    _outcome_like_policy_map_probe,
    _reference,
)
from tools.quality.validation.check_grounding_relation_contract import _unknown_unproven_probe


def test_controller_selects_minimal_cost_decisive_acquisition_and_reenters_gate() -> None:
    reference = _reference(include_mechanism=False)
    probe = _novel_transfer_probe()
    cg1, cg2 = _cg2_novel(reference, probe)
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    case = GroundingControllerCase(
        case_id="unit.cg5.acquire",
        proposal=probe,
        cg1_certificate=cg1,
        cg2_certificate=cg2,
        cg3_certificate=cg3,
    )
    controller = GroundingActiveController(reference)

    certificate = controller.certificate_for(case)

    assert cg3.decision == "acquire_then_decide"
    assert certificate.selected_action == "acquire_data"
    assert certificate.selection_reason == "minimal_cost_decisive_dominates_abstain"
    assert certificate.selected_ticket is not None
    assert certificate.selected_ticket.no_resolution_claim is True
    acquire_candidate = next(
        candidate for candidate in certificate.candidates if candidate.action_family == "acquire_data"
    )
    assert acquire_candidate.decisiveness.owner_shaped_resolution["redacted_payload"] is True
    assert "provenance" not in acquire_candidate.decisiveness.owner_shaped_resolution
    reentry_reference = replace_reference_edge(
        reference,
        _causal_claim(
            "household_cells.transfer_intensity",
            "household_cells.disposable_income",
            status="confirmed",
        ),
    )
    reentry_controller = GroundingActiveController(reentry_reference)
    reentry = reentry_controller.route_action_result(
        certificate,
        GroundingActionResult(
            action_family="acquire_data",
            result_id="unit.cg5.result.reference_only",
        ),
        case=case,
    )

    assert reentry.after_disposition == "admit_new_lever"
    assert reentry.advanced_by_gate is True
    assert reentry.false_bind_or_admit is False


def test_self_supplied_owner_edge_payload_is_rejected_in_production() -> None:
    reference = _reference(include_mechanism=False)
    probe = _novel_transfer_probe()
    cg1, cg2 = _cg2_novel(reference, probe)
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    case = GroundingControllerCase(
        case_id="unit.cg5.self_supplied_edge",
        proposal=probe,
        cg1_certificate=cg1,
        cg2_certificate=cg2,
        cg3_certificate=cg3,
    )
    controller = GroundingActiveController(reference)
    certificate = controller.certificate_for(case)

    reentry = controller.route_action_result(
        certificate,
        GroundingActionResult(
            action_family="acquire_data",
            result_id="unit.cg5.attack.self_supplied_edge",
            owner_shaped_edges=(
                OwnerShapedReferenceEdgeResult(
                    modality="L2_CAUSAL_CLAIM",
                    edge_id="unit.cg5.attack.high_trust_edge",
                    status="confirmed",
                    completion_value={
                        "direction": "positive",
                        "dst": "household_cells.disposable_income",
                        "src": "household_cells.transfer_intensity",
                    },
                    completion_reason="attacker_self_asserted_mechanism",
                    provenance={
                        "owner": "L2",
                        "source": "attacker",
                        "signals": {
                            "confidence": 0.95,
                            "strong_design_evidence": True,
                            "trust_score": 0.95,
                        },
                    },
                    verifier_provenance="attacker_self_attested",
                ),
            ),
        ),
        case=case,
    )

    assert reentry.after_disposition == "acquire_then_decide"
    assert reentry.after_reason == "production_result_payload_rejected_owner_data_path"
    assert reentry.advanced_by_gate is False


def test_claimed_resolution_without_owner_data_fails_closed() -> None:
    reference = _reference(include_mechanism=False)
    probe = _novel_transfer_probe()
    cg1, cg2 = _cg2_novel(reference, probe)
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    case = GroundingControllerCase(
        case_id="unit.cg5.forged",
        proposal=probe,
        cg1_certificate=cg1,
        cg2_certificate=cg2,
        cg3_certificate=cg3,
    )
    controller = GroundingActiveController(reference)
    certificate = controller.certificate_for(case)

    reentry = controller.route_action_result(
        certificate,
        GroundingActionResult(
            action_family="acquire_data",
            result_id="unit.cg5.forged.claim",
            claimed_resolution=True,
        ),
        case=case,
    )

    assert reentry.after_disposition == "acquire_then_decide"
    assert reentry.advanced_by_gate is False
    assert reentry.trusted_claimed_resolution is False


def test_low_voi_high_cost_human_resolution_abstains_with_remaining_action() -> None:
    reference = replace_reference_edge(
        _reference(include_mechanism=False),
        _causal_claim(
            "household_cells.transfer_intensity",
            "household_cells.disposable_income",
            status="confirmed",
        ),
    )
    probe = _novel_transfer_probe()
    probe = {
        **probe,
        "signature": {**probe["signature"], "admissibility": "candidate_unverified"},
    }
    cg1, cg2 = _cg2_novel(reference, probe)
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    case = GroundingControllerCase(
        case_id="unit.cg5.elicit",
        proposal=probe,
        cg1_certificate=cg1,
        cg2_certificate=cg2,
        cg3_certificate=cg3,
    )

    certificate = GroundingActiveController(reference).certificate_for(case)

    assert certificate.selected_action == "abstain"
    assert certificate.remaining_candidate_action == "elicit_human"
    assert any(
        candidate.action_family == "elicit_human" and not candidate.within_budget
        for candidate in certificate.candidates
    )


def test_cheap_verify_is_structural_only_without_live_gateway() -> None:
    reference = _reference(include_mechanism=False)
    probe = _unknown_unproven_probe()
    cg1 = GroundingRelationEngine(reference).certificate_for(
        probe,
        proposal_id="unit.cg5.unknown",
    )
    case = GroundingControllerCase(
        case_id="unit.cg5.cheap",
        proposal=probe,
        cg1_certificate=cg1,
    )

    certificate = GroundingActiveController(reference).certificate_for(case)

    assert cg1.selected_relation == "unknown"
    assert certificate.selected_action == "abstain"
    assert any(candidate.action_family == "cheap_verify" for candidate in certificate.candidates)
    assert any(
        candidate.decisiveness.planning_only_reason
        == "structural_only_no_live_gy_k_gateway"
        for candidate in certificate.candidates
        if candidate.action_family == "cheap_verify"
    )


def test_unknown_future_blocker_routes_to_abstain_recorded_gap() -> None:
    blocker = unknown_blocker_fail_safe(
        case_id="unit.cg5.future",
        gate="UNKNOWN",
        blocker_type="new_future_reason",
    )

    assert blocker.action_family == "abstain"
    assert blocker.mapping_status == "unknown_fail_safe"


def test_controller_certificate_is_content_addressed_and_non_authoritative() -> None:
    reference = _reference(include_mechanism=False)
    probe = _novel_transfer_probe()
    cg1, cg2 = _cg2_novel(reference, probe)
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    case = GroundingControllerCase(
        case_id="unit.cg5.hash",
        proposal=probe,
        cg1_certificate=cg1,
        cg2_certificate=cg2,
        cg3_certificate=cg3,
    )
    certificate = GroundingActiveController(reference).certificate_for(case)
    payload = certificate.model_dump(mode="json")
    payload["selected_action"] = "abstain"
    payload["content_hash"] = recompute_grounding_action_certificate_hash(payload)
    payload["certificate_id"] = f"cg5_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    payload["never_buy_bind_boundary"]["controller_can_resolve_gate"] = True
    payload["content_hash"] = recompute_grounding_action_certificate_hash(payload)
    payload["certificate_id"] = f"cg5_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"

    assert certificate.production_authoritative is False
    with pytest.raises(ValueError, match="grounding_action_certificate_claims_gate_authority"):
        GroundingActionCertificate.model_validate(payload)


def test_public_policy_exposes_no_authority_knobs() -> None:
    unsafe_kwargs = [
        {"force_action": "acquire_data"},
        {"voi_override": 1.0},
        {"cost_override": {"acquire_data": 0}},
        {"action_budget": 10},
        {"treat_as_resolved": True},
    ]
    for kwargs in unsafe_kwargs:
        with pytest.raises(ValueError):
            GroundingActiveControllerPolicy(**kwargs)


def test_denominator_covers_gate_typed_vocabularies_and_extracts_real_blockers() -> None:
    denominator = grounding_blocker_denominator()
    reference = _reference(include_mechanism=False)
    probe = _outcome_like_policy_map_probe()
    cg1, cg2 = _cg2_novel(reference, probe)
    cg3 = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    blockers = extract_grounding_blockers(
        GroundingControllerCase(
            case_id="unit.cg5.denominator",
            proposal=probe,
            cg1_certificate=cg1,
            cg2_certificate=cg2,
            cg3_certificate=cg3,
        )
    )

    assert "mechanism_witness_missing" in denominator.cg3_decisive_reasons
    assert "robust_singleton_ambiguous" in denominator.cg2_decisive_reasons
    assert "unknown" in denominator.cg1_selected_relations
    assert any(blocker.blocker_type == "mechanism_witness_missing" for blocker in blockers)
