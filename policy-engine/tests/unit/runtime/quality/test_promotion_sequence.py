from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from inspect import Parameter, signature
from pathlib import Path
from tempfile import mkdtemp
from types import SimpleNamespace
from typing import get_type_hints
from uuid import uuid4

import pytest

import polisyos.runtime.quality.promotion_sequence as promotion_sequence_module
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.pdc import (
    ArtifactRef,
    AuthorityBoundary,
    AuthorityDerivationTrace,
    PromotionObligationClass,
    PromotionObligationRecord,
    PromotionObligationStatus,
    PromotionRiskSpendRecord,
    SearchTerminalKind,
    gy_content_hash,
)
from polisyos.pdc._impl.layer2_design_search import (
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
    PredictableClaimSpec,
    project_n9_promotion_certificate,
)
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateSummary,
    PromotionPortObservation,
    ValueCalibrationReceipt,
    ValueGateReceipt,
    ValueTransportReceipt,
    _apply_promotion_to_summaries,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingBindGate,
    GroundingDecisionCertificate,
    recompute_grounding_decision_content_hash,
)
from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalN9PromotionPort,
    CanonicalPromotionInput,
    CanonicalPromotionReceipt,
    LegacyPromotionStrangleReceipt,
    N9DesignProblemBinding,
    _gate_outcome_hash,
    recompute_authority_trace_hash,
    run_canonical_promotion_sequence,
    validate_canonical_promotion_receipt,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_fixed_time_n8_calibration_is_ledger_refused_and_stays_shadow() -> None:
    promotion_input = _promotion_input()
    session = _ledger_session(binding=promotion_input.design_problem_binding)
    receipt = run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=session,
    )

    assert receipt.promoted is False
    assert receipt.status == "shadow"
    assert receipt.promotion_lane == "contract_testing"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "non_production_anchor_scope"
    assert receipt.authority_derivation_trace is None
    assert receipt.risk_spend.total_declared_delta == 0.0
    assert receipt.risk_spend.within_budget is True
    calibration = _obligation(receipt, PromotionObligationClass.CALIBRATION)
    assert calibration.status == PromotionObligationStatus.FAILED
    assert "non_anytime_valid" in calibration.detail
    assert calibration.risk_spend is not None
    assert calibration.risk_spend.n11_confidence_ledger_ref
    check = session.receipt().checks[-1]
    assert check.execution_status == "refused"
    assert check.refusal_code == "non_anytime_valid"
    assert check.spend_decimal == "0"
    assert receipt.confidence_ledger_receipt_id == session.receipt().receipt_id
    assert receipt.confidence_ledger_projection.ledger_receipt_id == session.receipt().receipt_id
    assert _obligation(receipt, PromotionObligationClass.EFFECT).status == (
        PromotionObligationStatus.SCOPE_INSUFFICIENT
    )
    assert _obligation(receipt, PromotionObligationClass.MEASUREMENT).status == (
        PromotionObligationStatus.SCOPE_INSUFFICIENT
    )
    assert validate_canonical_promotion_receipt(receipt) == ()


def test_n9_receipt_authorizes_only_narrow_projection_and_current_head() -> None:
    receipt = _run(_promotion_input())
    payload = receipt.model_dump(mode="json")

    assert "confidence_ledger_receipt" not in payload
    assert receipt.confidence_ledger_scope_ref == (receipt.confidence_ledger_projection.scope_id)
    assert receipt.confidence_ledger_head_id == (receipt.confidence_ledger_projection.head_event_id)
    assert receipt.confidence_ledger_head_ref == (
        receipt.confidence_ledger_projection.head_event_ref
    )


def test_n9_owner_replay_projection_round_trips_through_json() -> None:
    receipt = _run(_promotion_input())

    restored = CanonicalPromotionReceipt.model_validate(receipt.model_dump(mode="json"))

    assert restored == receipt
    assert validate_canonical_promotion_receipt(restored) == ()


def test_ungrounded_candidate_stays_shadow_by_real_grounding_owner() -> None:
    receipt = _run(
        _promotion_input(
            summary=_summary(current_valid=False, grounding_status="grounded_shadow"),
        )
    )

    assert receipt.promoted is False
    assert "identification:single_obligation_fail" in receipt.refusal_reasons


def test_uncalibrated_candidate_stays_shadow() -> None:
    value = _value_receipt(calibration_status="blocked")
    receipt = _run(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert "calibration:single_obligation_fail" in receipt.refusal_reasons


def test_untransportable_candidate_stays_shadow() -> None:
    value = _value_receipt(transport_status="blocked")
    receipt = _run(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert "slot:single_obligation_fail" in receipt.refusal_reasons


def test_timeout_unknown_never_promotes_or_fabricates_block() -> None:
    receipt = _run(_promotion_input(force_proof_timeout=True))

    assert receipt.promoted is False
    assert receipt.status == "shadow"
    effect = _obligation(receipt, PromotionObligationClass.EFFECT)
    assert effect.status == PromotionObligationStatus.UNKNOWN
    assert "effect:proof_timeout" in receipt.refusal_reasons


def test_lower_boundary_wins_over_optimistic_declared_transform() -> None:
    receipt = _run(
        _promotion_input(
            declared_authority_transform={
                "requested_evidence_kind": "measurement",
                "requested_decision_grade": "decision_admissible",
            }
        )
    )

    assert receipt.promoted is False
    assert receipt.computed_authority_boundary.decision_grade == "advisory_admissible"
    assert receipt.authority_derivation_trace is None
    assert "calibration:single_obligation_fail" in receipt.refusal_reasons


def test_no_self_promotion_rejected_by_trace_guard() -> None:
    artifact = ArtifactRef(
        artifact_id="n9.self.promotion",
        artifact_type="runtime.quality.n9_promotion_receipt",
        content_hash=_hash("1"),
        schema_ref="policyos.policy_design_case.layer3_gy.n9_promotion.v2",
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
    receipt = _run(
        _promotion_input(
            grounding_decision_certificate=None,
            credal_reference=None,
        )
    )

    assert receipt.promoted is False
    assert "identification:single_obligation_fail" in receipt.refusal_reasons
    assert (
        "resolve_grounding_decision_promotability"
        in _obligation(
            receipt,
            PromotionObligationClass.IDENTIFICATION,
        ).owner_ref
    )


def test_contract_testing_bind_receipt_is_intrinsically_non_promotable() -> None:
    receipt = _run(_promotion_input())

    assert receipt.promoted is False
    assert receipt.promotion_lane == "contract_testing"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "non_production_anchor_scope"


def test_scope_insufficient_obligation_does_not_vacuously_pass() -> None:
    receipt = _run(_promotion_input())

    assert receipt.promoted is False
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
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": gate_outcome_hash,
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert {issue["code"] for issue in issues} == {"obligation_class_vacuously_passed"}


def test_scope_insufficient_cannot_mint_production_authority() -> None:
    receipt = _run(_promotion_input())
    edited = receipt.model_copy(
        update={
            "promoted": True,
            "promotion_lane": "production",
            "consumer_promotable": True,
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "scope_insufficient_authority_laundering" in {issue["code"] for issue in issues}


def test_unseen_non_panel_value_receipt_flows_unchanged() -> None:
    value = _value_receipt(
        method_fqn="frontier.unseen.scenario_set@1", representation="scenario_set"
    )
    receipt = _run(_promotion_input(value_receipt=value))

    assert receipt.promoted is False
    assert receipt.value_method_family == "frontier.unseen.scenario_set@1"
    assert receipt.value_receipt_ref == value.value_ref


def test_forged_g4_ref_is_refused_by_owner_resolution() -> None:
    receipt = _run(_promotion_input(g4_governed_promotion_ref="pdc://fake/g4/not-resolved"))

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
    receipt = _run(
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
    receipt = _run(
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
    receipt = _run(_promotion_input(s6_blind_spot_posture=s6_bad))
    assert _obligation(receipt, PromotionObligationClass.IMPLEMENTATION).status == (
        PromotionObligationStatus.FAILED
    )


def test_reintroduced_champion_path_turns_strangle_receipt_red() -> None:
    receipt = LegacyPromotionStrangleReceipt.recompute()

    assert receipt.status == "strangled"
    assert receipt.live_policy_champion_callers == ()


def test_hand_edited_confidence_projection_is_rejected() -> None:
    receipt = _run(_promotion_input())
    projection = receipt.confidence_ledger_projection.model_copy(
        update={"projection_hash": _hash("9")}
    )
    edited = receipt.model_copy(update={"confidence_ledger_projection": projection})

    issues = validate_canonical_promotion_receipt(edited)

    assert {issue["code"] for issue in issues} == {"confidence_ledger_projection_drift"}


def test_caller_cannot_supply_authoritative_risk_spends() -> None:
    supplied = PromotionRiskSpendRecord(
        obligation_class=PromotionObligationClass.CALIBRATION,
        certificate_ref="caller://forged-risk-spend",
        instrument="caller_claimed_anytime_valid",
        certificate_role="promotion",
        claim_polarity="false_accept",
        declared_delta_spend=0.0,
        n11_confidence_ledger_ref="confidence-check:sha256:" + "1" * 64,
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        _promotion_input(risk_spends=(supplied,))


def test_standalone_promotion_requires_non_optional_authority_ledger_session() -> None:
    parameter = signature(run_canonical_promotion_sequence).parameters["confidence_ledger_session"]

    assert parameter.default is Parameter.empty
    assert (
        get_type_hints(run_canonical_promotion_sequence)["confidence_ledger_session"]
        is ConfidenceLedgerSession
    )


def test_n9_rejects_session_bound_to_a_different_design_problem() -> None:
    promotion_input = _promotion_input()
    unrelated_session = _ledger_session(
        binding=_problem_binding(run_ref="unrelated-design-problem")
    )

    with pytest.raises(ValueError, match="confidence_ledger_scope_binding_mismatch"):
        run_canonical_promotion_sequence(
            promotion_input,
            confidence_ledger_session=unrelated_session,
        )


def test_value_receipt_candidate_mismatch_fails_closed_before_accounting() -> None:
    value = _value_receipt().model_copy(update={"candidate_id": "candidate_from_another_owner"})

    with pytest.raises(ValueError, match="promotion_value_candidate_binding_mismatch"):
        _promotion_input(value_receipt=value)


def test_verification_ledger_session_cannot_run_n9_authority_path() -> None:
    with pytest.raises(ValueError, match="confidence_ledger_authority_session_required"):
        run_canonical_promotion_sequence(
            _promotion_input(),
            confidence_ledger_session=_verification_ledger_session(),
        )


def test_private_verification_sequence_stamps_receipt_non_consumer_promotable() -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)

    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    assert receipt.confidence_ledger_projection.authority_provenance == "verification"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "verification_only_replay"


def test_private_verification_boundary_rejects_alternate_registry() -> None:
    promotion_input = _promotion_input()
    canonical_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=canonical_session,
    )
    alternate_payload = deepcopy(canonical_session.registry.source_payload())
    alternate_payload["schedule_profiles"][0]["mass"]["denominator"] = 2
    alternate_session = _verification_ledger_session(
        binding=promotion_input.design_problem_binding,
        registry_source=alternate_payload,
    )

    with pytest.raises(
        ValueError,
        match="confidence_ledger_verification_registry_invalid",
    ):
        promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
            promotion_input,
            confidence_ledger_session=alternate_session,
        )
    with pytest.raises(
        ValueError,
        match="confidence_ledger_verification_registry_invalid",
    ):
        CanonicalN9PromotionPort._for_verification(
            repo_root=REPO_ROOT,
            confidence_ledger_session=alternate_session,
        )

    assert promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        receipt,
        repo_root=REPO_ROOT,
        confidence_ledger_session=alternate_session,
    ) == ({"code": "confidence_ledger_verification_registry_invalid"},)


def test_public_validator_exposes_no_ledger_session_injection() -> None:
    assert (
        "confidence_ledger_session"
        not in signature(validate_canonical_promotion_receipt).parameters
    )


def test_public_validator_rejects_verification_before_opening_authority_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    def _forbid_authority_open(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("verification receipt touched canonical ledger namespace")

    monkeypatch.setattr(
        promotion_sequence_module,
        "_open_projected_confidence_ledger_session",
        _forbid_authority_open,
    )

    issues = validate_canonical_promotion_receipt(receipt)

    assert issues == ({"code": "confidence_ledger_authority_provenance_invalid"},)


def test_private_verification_revalidator_recomputes_current_head() -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        receipt,
        repo_root=REPO_ROOT,
        candidate_summary=promotion_input.candidate_summary,
        value_receipt=promotion_input.value_receipt,
        confidence_ledger_session=session,
    )

    assert issues == ()


def test_private_verification_revalidator_requires_loaded_owner_repo(
    tmp_path: Path,
) -> None:
    promotion_input = _promotion_input()
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=session,
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        receipt,
        repo_root=tmp_path,
        confidence_ledger_session=session,
    )

    assert issues == ({"code": "verification_owner_repo_root_invalid"},)


def test_verification_projection_is_not_n9_authority_provenance() -> None:
    receipt = _run(_promotion_input())
    projection = receipt.confidence_ledger_projection.model_copy(
        update={"authority_provenance": "verification"}
    )
    edited = receipt.model_copy(update={"confidence_ledger_projection": projection})

    issues = validate_canonical_promotion_receipt(edited)

    assert "confidence_ledger_authority_provenance_invalid" in {issue["code"] for issue in issues}


def test_schedule_slot_is_reserved_before_obligation_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, object]] = []
    promotion_input = _promotion_input()
    session = _ledger_session(
        run_ref="ledger-run:n9-ordering",
        binding=promotion_input.design_problem_binding,
    )
    original_prepare_check = ConfidenceLedgerSession.prepare_check

    def _record_prepare_check(
        current: ConfidenceLedgerSession,
        **kwargs: object,
    ) -> object:
        if current is session:
            events.append(("prepare", kwargs))
        return original_prepare_check(current, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        ConfidenceLedgerSession,
        "prepare_check",
        _record_prepare_check,
    )

    def _stop_after_reservation(*args: object, **kwargs: object) -> object:
        del args, kwargs
        events.append(("compile", None))
        raise RuntimeError("stop_after_reservation")

    monkeypatch.setattr(
        promotion_sequence_module,
        "_compile_obligations",
        _stop_after_reservation,
    )

    with pytest.raises(RuntimeError, match="stop_after_reservation"):
        run_canonical_promotion_sequence(
            promotion_input,
            confidence_ledger_session=session,
        )

    assert [event for event, _ in events] == ["prepare", "compile"]
    reservation = events[0][1]
    assert isinstance(reservation, dict)
    assert reservation["obligation_class"] == PromotionObligationClass.CALIBRATION
    assert reservation["instrument_id"] == "fixed_time_confidence_interval"
    assert reservation["certificate_ref"] == "s10://unit"


def test_n9_port_rebinds_every_adaptive_receipt_to_one_final_ledger_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    port = CanonicalN9PromotionPort(repo_root=REPO_ROOT)
    problem_id = f"adaptive_ledger_{uuid4().hex}"
    problem = SimpleNamespace(
        design_problem_id=problem_id,
        model_spec_ref=None,
        schema_version="policyos.runtime.design_problem.test.v1",
        model_dump=lambda **kwargs: {
            "design_problem_id": problem_id,
            "schema_version": "policyos.runtime.design_problem.test.v1",
        },
    )
    first = _summary()
    second = first.model_copy(
        update={
            "candidate_id": "candidate_n9_second",
            "content_hash": _hash("8"),
        }
    )

    observation = port(summaries=(first, second), problem=problem)  # type: ignore[arg-type]
    receipts = tuple(
        CanonicalPromotionReceipt.model_validate(item) for item in observation.receipts
    )

    assert len(receipts) == 2
    assert len({item.confidence_ledger_head_id for item in receipts}) == 1
    assert len({item.confidence_ledger_receipt_id for item in receipts}) == 1
    check_refs = {item.risk_spend.spend_records[0].n11_confidence_ledger_ref for item in receipts}
    projected_check_refs = {
        row.check_id for row in receipts[0].confidence_ledger_projection.promotion_rows
    }
    assert len(check_refs) == 2
    assert check_refs <= projected_check_refs
    assert all(validate_canonical_promotion_receipt(item) == () for item in receipts)


def test_verification_port_never_certifies_candidates() -> None:
    problem_id = f"verification_port_{uuid4().hex}"
    problem = SimpleNamespace(
        design_problem_id=problem_id,
        model_spec_ref=None,
        schema_version="policyos.runtime.design_problem.test.v1",
        model_dump=lambda **kwargs: {
            "design_problem_id": problem_id,
            "schema_version": "policyos.runtime.design_problem.test.v1",
        },
    )
    binding = N9DesignProblemBinding.from_problem(problem)  # type: ignore[arg-type]
    session = _verification_ledger_session(binding=binding)
    port = CanonicalN9PromotionPort._for_verification(
        repo_root=REPO_ROOT,
        confidence_ledger_session=session,
    )

    observation = port(summaries=(_summary(),), problem=problem)  # type: ignore[arg-type]
    receipt = CanonicalPromotionReceipt.model_validate(observation.receipts[0])

    assert observation.status == "not_promoted"
    assert observation.certified_candidate_ids == ()
    assert receipt.confidence_ledger_projection.authority_provenance == "verification"
    assert receipt.consumer_promotable is False
    assert receipt.non_promotable_reason == "verification_only_replay"


def test_verification_port_requires_loaded_repo_for_non_ledger_owners(
    tmp_path: Path,
) -> None:
    session = _verification_ledger_session()

    with pytest.raises(ValueError, match="verification_owner_repo_root_invalid"):
        CanonicalN9PromotionPort._for_verification(
            repo_root=tmp_path,
            confidence_ledger_session=session,
        )


@pytest.mark.parametrize(
    ("kwarg", "value"),
    [
        ("confidence_ledger_session_factory", lambda _problem: _ledger_session()),
        (
            "confidence_ledger_artifact_store",
            FileSystemCAS(REPO_ROOT / ".tmp" / "gy-n11-forbidden-cas"),
        ),
        (
            "confidence_ledger_state_root",
            REPO_ROOT / ".tmp" / "gy-n11-forbidden-state",
        ),
    ],
)
def test_n9_port_exposes_no_custom_ledger_namespace_injection(
    kwarg: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        CanonicalN9PromotionPort(**{kwarg: value})  # type: ignore[arg-type]


def test_probabilistic_certificate_bypassing_ledger_is_rejected() -> None:
    receipt = _run(_promotion_input())
    calibration = _obligation(receipt, PromotionObligationClass.CALIBRATION)
    bypass = calibration.model_copy(
        update={
            "status": PromotionObligationStatus.SATISFIED,
            "reason": None,
            "risk_spend": None,
            "detail": "forged fixed-time certificate bypassed N11",
        }
    )
    obligations = tuple(
        bypass if item.obligation_class == PromotionObligationClass.CALIBRATION else item
        for item in receipt.obligations
    )
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "probabilistic_certificate_bypassed_confidence_ledger" in {
        issue["code"] for issue in issues
    }


def test_rehashed_owner_outcome_relabel_is_rejected_by_owner_recomputation() -> None:
    receipt = _run(_promotion_input())
    obligations = tuple(
        obligation.model_copy(
            update={
                "status": PromotionObligationStatus.SATISFIED,
                "reason": None,
                "semantic_scope": "real_semantics",
            }
        )
        if obligation.obligation_class
        in {PromotionObligationClass.EFFECT, PromotionObligationClass.MEASUREMENT}
        else obligation
        for obligation in receipt.obligations
    )
    edited = receipt.model_copy(
        update={
            "obligations": obligations,
            "gate_outcome_hash": _gate_outcome_hash(obligations),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_owner_recomputation_drift" in {issue["code"] for issue in issues}


def test_rehashed_computed_boundary_is_rejected_by_owner_recomputation() -> None:
    receipt = _run(_promotion_input())
    boundary = receipt.computed_authority_boundary.model_copy(
        update={"boundary_id": "n9.forged.rehashed.boundary"}
    )
    edited = receipt.model_copy(update={"computed_authority_boundary": boundary})

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_owner_recomputation_drift" in {issue["code"] for issue in issues}


def test_rehashed_contract_lane_as_production_is_rejected_by_owner_recomputation() -> None:
    receipt = _run(_promotion_input())
    refusal_reasons = promotion_sequence_module._refusal_reasons(
        receipt.obligations,
        risk_spend=receipt.risk_spend,
        allow_non_authoritative_contract_scope_gaps=False,
    )
    edited = receipt.model_copy(
        update={
            "promotion_lane": "production",
            "refusal_reasons": tuple(refusal_reasons),
        }
    )

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_owner_recomputation_drift" in {issue["code"] for issue in issues}


def test_receipt_candidate_id_must_match_replayed_owner_input() -> None:
    receipt = _run(_promotion_input())
    edited = receipt.model_copy(update={"candidate_id": "candidate_forged_replay"})

    issues = validate_canonical_promotion_receipt(edited)

    assert "promotion_owner_recomputation_drift" in {issue["code"] for issue in issues}


def test_rehashed_owner_projection_still_fails_live_candidate_binding() -> None:
    receipt = _run(_promotion_input())
    sibling = receipt.owner_projection.candidate_summary.model_copy(
        update={
            "candidate_id": "candidate_sibling_replay",
            "content_hash": _hash("6"),
        }
    )
    projection_payload = receipt.owner_projection.model_dump(
        mode="json",
        exclude={"projection_hash"},
    )
    projection_payload["candidate_summary"] = sibling.model_dump(mode="json")
    projection_payload["projection_hash"] = gy_content_hash(projection_payload)
    owner_projection = type(receipt.owner_projection).model_validate(projection_payload)
    edited = receipt.model_copy(
        update={
            "owner_projection": owner_projection,
            "candidate_id": sibling.candidate_id,
        }
    )

    issues = validate_canonical_promotion_receipt(
        edited,
        candidate_summary=receipt.owner_projection.candidate_summary,
    )

    assert "promotion_candidate_owner_binding_invalid" in {issue["code"] for issue in issues}


def test_empty_ledger_projection_cannot_insure_forged_probabilistic_success() -> None:
    promotion_input = _promotion_input()
    receipt_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    receipt = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=receipt_session,
    )
    empty_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    empty_ledger = empty_session.receipt()
    empty_projection = project_n9_promotion_certificate(
        empty_ledger,
        session=empty_session,
    )
    risk_spend = promotion_sequence_module._risk_spend_summary((), empty_projection)
    calibration = _obligation(receipt, PromotionObligationClass.CALIBRATION)
    forged_calibration = calibration.model_copy(
        update={
            "status": PromotionObligationStatus.SATISFIED,
            "reason": None,
            "risk_spend": None,
            "detail": "forged probabilistic success with an empty N11 projection",
        }
    )
    obligations = tuple(
        forged_calibration
        if item.obligation_class == PromotionObligationClass.CALIBRATION
        else item
        for item in receipt.obligations
    )
    gate_hash = _gate_outcome_hash(obligations)
    trace = promotion_sequence_module._authority_derivation_trace(
        promotion_input,
        obligations=obligations,
        boundary=receipt.computed_authority_boundary,
        gate_hash=gate_hash,
        risk_spend=risk_spend,
        confidence_ledger_receipt=empty_ledger,
        confidence_ledger_projection=empty_projection,
    )
    trace_hash = recompute_authority_trace_hash(trace)
    trace = trace.model_copy(update={"trace_content_hash": trace_hash})
    edited = receipt.model_copy(
        update={
            "status": "grounded_partial_admissible",
            "promoted": True,
            "terminal_kind": SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE,
            "obligations": obligations,
            "risk_spend": risk_spend,
            "confidence_ledger_scope_ref": empty_projection.scope_id,
            "confidence_ledger_head_id": empty_projection.head_event_id,
            "confidence_ledger_head_ref": empty_projection.head_event_ref,
            "confidence_ledger_receipt_id": empty_projection.ledger_receipt_id,
            "confidence_ledger_projection": empty_projection,
            "authority_derivation_trace": trace,
            "gate_outcome_hash": gate_hash,
            "trace_content_hash": trace_hash,
            "refusal_reasons": (),
        }
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        edited,
        repo_root=REPO_ROOT,
        confidence_ledger_session=empty_session,
    )

    assert "probabilistic_certificate_bypassed_confidence_ledger" in {
        issue["code"] for issue in issues
    }


def test_ledger_claim_scope_is_recomputed_from_candidate_owner() -> None:
    promotion_input = _promotion_input()
    canonical_session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    canonical = promotion_sequence_module._run_canonical_promotion_sequence_for_verification(
        promotion_input,
        confidence_ledger_session=canonical_session,
    )
    session = _verification_ledger_session(binding=promotion_input.design_problem_binding)
    expected = promotion_sequence_module._expected_calibration_check(promotion_input)
    wrong_claim = PredictableClaimSpec(
        claim_ref=expected.claim.claim_ref,
        null_ref=expected.claim.null_ref,
        claim_scope_ref="n9://candidate-summary/sha256:" + "9" * 64,
        data_window_ref=expected.claim.data_window_ref,
        certificate_role=expected.claim.certificate_role,
        claim_polarity=expected.claim.claim_polarity,
    )
    with pytest.raises(promotion_sequence_module.ConfidenceLedgerError):
        session.prepare_check(
            history_token=session.observe_history(),
            request_key=expected.request_key,
            obligation_class=expected.obligation_class,
            instrument_id=expected.instrument_id,
            certificate_ref=expected.certificate_ref,
            claim=wrong_claim,
        )
    check = promotion_sequence_module._ledger_check_for_request(
        session,
        request_key=expected.request_key,
    )
    if check.outcome == "prepared":
        check = session.execute_check(check)
    ledger = session.receipt()
    projection = project_n9_promotion_certificate(ledger, session=session)
    risk_spend = promotion_sequence_module._risk_spend_summary((check,), projection)
    edited = canonical.model_copy(
        update={
            "risk_spend": risk_spend,
            "confidence_ledger_scope_ref": projection.scope_id,
            "confidence_ledger_head_id": projection.head_event_id,
            "confidence_ledger_head_ref": projection.head_event_ref,
            "confidence_ledger_receipt_id": projection.ledger_receipt_id,
            "confidence_ledger_projection": projection,
        }
    )

    issues = promotion_sequence_module._validate_canonical_promotion_receipt_for_verification(
        edited,
        repo_root=REPO_ROOT,
        confidence_ledger_session=session,
    )

    assert "probabilistic_certificate_bypassed_confidence_ledger" in {
        issue["code"] for issue in issues
    }


def test_failed_obligation_cannot_be_relabelled_into_decision_front() -> None:
    promotion_input = _promotion_input()
    session = _ledger_session(
        run_ref="ledger-run:n9-forged-decision",
        binding=promotion_input.design_problem_binding,
    )
    receipt = run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=session,
    )
    obligations = tuple(
        obligation.model_copy(
            update={
                "status": PromotionObligationStatus.SATISFIED,
                "reason": None,
                "semantic_scope": "real_semantics",
            }
        )
        if obligation.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
        else obligation
        for obligation in receipt.obligations
    )
    assert any(obligation.status == PromotionObligationStatus.FAILED for obligation in obligations)
    gate_hash = _gate_outcome_hash(obligations)
    trace = promotion_sequence_module._authority_derivation_trace(
        promotion_input,
        obligations=obligations,
        boundary=receipt.computed_authority_boundary,
        gate_hash=gate_hash,
        risk_spend=receipt.risk_spend,
        confidence_ledger_receipt=session.receipt(),
        confidence_ledger_projection=receipt.confidence_ledger_projection,
    )
    trace_hash = recompute_authority_trace_hash(trace)
    trace = trace.model_copy(update={"trace_content_hash": trace_hash})
    forged = receipt.model_copy(
        update={
            "obligations": obligations,
            "refusal_reasons": (),
            "promoted": True,
            "status": "grounded_partial_admissible",
            "terminal_kind": SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE,
            "promotion_lane": "production",
            "consumer_promotable": True,
            "non_promotable_reason": None,
            "authority_derivation_trace": trace,
            "trace_content_hash": trace_hash,
            "gate_outcome_hash": gate_hash,
        }
    )

    issue_codes = {
        issue["code"]
        for issue in validate_canonical_promotion_receipt(
            forged,
        )
    }
    promotion = PromotionPortObservation(
        status="certified_current_valid",
        certified_candidate_ids=(forged.candidate_id,),
        reason="forged decision fields",
        receipts=(forged.model_dump(mode="json"),),
    )
    summaries = _apply_promotion_to_summaries(
        (promotion_input.candidate_summary,),
        promotion,
    )

    assert {
        "promotion_refusal_reasons_drift",
        "promotion_promoted_drift",
        "promotion_status_drift",
        "promotion_terminal_kind_drift",
        "promotion_consumer_promotable_drift",
        "promotion_trace_presence_drift",
    } <= issue_codes
    assert summaries[0].front == "research"
    assert summaries[0].certified_by_n9 is False


def _ledger_session(
    *,
    run_ref: str = "ledger-run:n9-promotion-test",
    binding: N9DesignProblemBinding | None = None,
) -> ConfidenceLedgerSession:
    owner_binding = binding or _problem_binding(run_ref=run_ref)
    risk_scope = ConfidenceRiskBudgetScope(
        scope_owner_ref=promotion_sequence_module.PROMOTION_SEQUENCE_REF,
        authority_purpose="n9_promotion",
        owner_scope_key=f"design-problem:{owner_binding.design_problem_id}",
        owner_projection_hash=owner_binding.problem_content_hash,
        epoch_ref=None,
        model_ref=owner_binding.model_spec_ref,
        rule_ref="policyos.policy_design_case.layer3_gy.n9_promotion.v2",
        schema_ref=owner_binding.problem_schema_version,
    )
    return ConfidenceLedgerSession.from_repo(
        REPO_ROOT,
        risk_scope=risk_scope,
    )


def _verification_ledger_session(
    *,
    binding: N9DesignProblemBinding | None = None,
    registry_source: object | None = None,
) -> ConfidenceLedgerSession:
    state_base = Path(mkdtemp(prefix="gy-n11-confidence-ledger-"))
    owner_binding = binding or _problem_binding(run_ref="n9-verification")
    risk_scope = ConfidenceRiskBudgetScope(
        scope_owner_ref=promotion_sequence_module.PROMOTION_SEQUENCE_REF,
        authority_purpose="n9_promotion",
        owner_scope_key=f"design-problem:{owner_binding.design_problem_id}",
        owner_projection_hash=owner_binding.problem_content_hash,
        epoch_ref=None,
        model_ref=owner_binding.model_spec_ref,
        rule_ref="policyos.policy_design_case.layer3_gy.n9_promotion.v2",
        schema_ref=owner_binding.problem_schema_version,
    )
    return ConfidenceLedgerSession._for_verification(
        REPO_ROOT,
        risk_scope=risk_scope,
        artifact_store=FileSystemCAS(state_base / "cas"),
        state_root=state_base / "state",
        registry_source=registry_source,
    )


def _run(promotion_input: CanonicalPromotionInput) -> CanonicalPromotionReceipt:
    return run_canonical_promotion_sequence(
        promotion_input,
        confidence_ledger_session=_ledger_session(binding=promotion_input.design_problem_binding),
    )


def _promotion_input(**overrides: object) -> CanonicalPromotionInput:
    summary = overrides.pop("summary", _summary())
    value_receipt = overrides.pop("value_receipt", _value_receipt())
    reference, decision = _cg2_contract_bind()
    kwargs = {
        "design_problem_binding": overrides.pop(
            "design_problem_binding",
            _problem_binding(),
        ),
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
    }
    kwargs.update(overrides)
    return CanonicalPromotionInput(**kwargs)


def _problem_binding(
    *,
    run_ref: str = "n9-promotion-test",
) -> N9DesignProblemBinding:
    problem_id = f"n9_{uuid4().hex}"
    return N9DesignProblemBinding(
        design_problem_id=problem_id,
        problem_content_hash=gy_content_hash(
            {
                "design_problem_id": problem_id,
                "run_ref": run_ref,
                "schema_version": "policyos.runtime.design_problem.test.v1",
            }
        ),
        model_spec_ref=None,
        problem_schema_version="policyos.runtime.design_problem.test.v1",
    )


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
    payload["certificate_id"] = f"cg2_cert_{payload['content_hash'].removeprefix('sha256:')[:16]}"
    return reference, GroundingDecisionCertificate.model_validate(payload)


def _boundary(*, grade: str = "decision_admissible") -> AuthorityBoundary:
    return AuthorityBoundary(
        boundary_id="n9.test.boundary",
        authoritative_for=["grounded_partial_admissible_policy_design"],
        may_not_use_for=["production_deployment"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=["policyos.policy_design_case.layer3_gy.n9_promotion.v2"],
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
