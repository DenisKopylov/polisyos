from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality as runtime_quality

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures/layer2/s7"
CASE_ID = "ua-msme-affordable-loans-2022"
RULE_VERSION_REF = "policyos.layer2.s7.delegation.v1"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _s7(name: str) -> Any:
    return getattr(runtime_quality, name)


def _registry() -> object:
    return _s7("build_governance_decision_class_registry")(
        case_id=CASE_ID,
        rule_version_ref=RULE_VERSION_REF,
    )


def _matrix() -> object:
    return _s7("build_decision_rights_matrix")(
        case_id=CASE_ID,
        governance_decision_classes=_registry(),
        rule_version_ref=RULE_VERSION_REF,
    )


def _contract() -> object:
    return _s7("build_delegation_contract")(
        case_id=CASE_ID,
        matrix=_matrix(),
        governance_decision_classes=_registry(),
        s6_mandate_record_ref="pdc://layer2/s6/ua-msme/mandate-legitimacy",
        s6_mandate_firewall_disposition="pass",
        rule_version_ref=RULE_VERSION_REF,
    )


def _request(
    *,
    decision_class_id: str = "a_spec_gap",
    need_reasons: list[str] | None = None,
    voi_rank: int = 1,
    s6_mandate_firewall_disposition: str = "pass",
) -> object:
    return _s7("build_human_decision_request")(
        case_id=CASE_ID,
        contract=_contract(),
        decision_class_id=decision_class_id,
        need_reasons=need_reasons or ["high_stakes", "value_laden"],
        voi_rank=voi_rank,
        s6_mandate_record_ref="pdc://layer2/s6/ua-msme/mandate-legitimacy",
        s6_mandate_firewall_disposition=s6_mandate_firewall_disposition,
        rule_version_ref=RULE_VERSION_REF,
    )


def _request_from_probe(probe: dict[str, object]) -> object:
    request = probe["request"]
    assert isinstance(request, dict)
    return _request(
        decision_class_id=str(request["decision_class_id"]),
        need_reasons=list(request["need_reasons"]),
        voi_rank=int(request["voi_rank"]),
        s6_mandate_firewall_disposition=str(request["s6_mandate_firewall_disposition"]),
    )


def test_s7_artifacts_are_strict_replayable_and_exported() -> None:
    for model_name in (
        "DelegationContract",
        "DecisionRightsMatrix",
        "HumanDecisionRequest",
        "HumanDecisionRecord",
    ):
        model = _s7(model_name)
        assert model.model_config.get("extra") == "forbid"
        assert hasattr(runtime_quality, model_name)


def test_v1_human_decision_record_cannot_mint_custody_claim() -> None:
    request = _request()
    record = _s7("record_human_decision")(
        case_id=CASE_ID,
        request=request,
        actor_ref="institution://mandate-owner/reviewer-1",
        actor_role=request.required_role,
        decision_action_exercised="approve",
        evidence_summary_ref="sha256:" + "a" * 64,
        disconfirming_evidence_refs=["sha256:" + "b" * 64],
        active_choice=True,
        accountability_statement="I accept accountability for this exact decision.",
        five_rights_check={
            "right_decision": True,
            "right_person": True,
            "right_information": True,
            "right_format_channel": True,
            "right_time": True,
        },
        mandate_record_ref=request.s6_mandate_record_ref,
        rule_version_ref=RULE_VERSION_REF,
    )
    forged_v1 = {
        **record.model_dump(mode="json"),
        "custody_signer_identity": record.actor_ref,
    }

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        _s7("HumanDecisionRecord").model_validate(forged_v1)


def test_delegation_contract_embeds_governance_decision_class_registry() -> None:
    registry = _registry()
    contract = _contract()

    assert contract.governance_decision_classes == registry
    assert {row.decision_class_id for row in registry} >= {
        "a_spec_gap",
        "budget_use",
        "acquisition",
        "final_choice",
    }
    assert contract.decision_rights_matrix_ref == _matrix().matrix_ref
    assert "production_claim_authority" in contract.authority_boundary.may_not_use_for


def test_decision_rights_matrix_maps_classes_to_roles_modes_actions_and_five_rights() -> None:
    matrix = _matrix()

    row = matrix.row_for_decision_class("a_spec_gap")
    assert row.required_role == "policy_design_governance_reviewer"
    assert set(row.available_actions) == {
        "request_evidence",
        "approve",
        "reject",
        "revise_scope",
        "escalate",
    }
    assert row.default_interaction_mode == "request_driven"
    assert row.ai_first_allowed is False
    assert set(row.five_rights_dimensions) == {
        "right_decision",
        "right_person",
        "right_information",
        "right_format_channel",
        "right_time",
    }


def test_high_stakes_value_laden_or_out_of_envelope_never_defaults_to_ai_first() -> None:
    request = _request(need_reasons=["high_stakes", "value_laden", "out_of_envelope"])

    assert request.interaction_mode in {"ai_follow", "request_driven"}
    assert request.interaction_mode != "ai_first"
    assert request.disposition == "request_human_decision"


def test_ai_follow_is_valid_for_high_stakes_when_matrix_selects_it() -> None:
    matrix = _matrix()
    ai_follow_rows = [
        row
        for row in matrix.rows
        if row.default_interaction_mode == "ai_follow" and row.ai_first_allowed is False
    ]

    assert ai_follow_rows
    request = _request(
        decision_class_id=ai_follow_rows[0].decision_class_id,
        need_reasons=["high_stakes"],
    )
    assert request.interaction_mode == "ai_follow"
    assert request.disposition == "request_human_decision"


def test_low_voi_in_envelope_action_records_no_interrupt() -> None:
    request = _request(
        decision_class_id="routine_in_envelope",
        need_reasons=["low_voi_no_interrupt"],
        voi_rank=13,
    )

    assert request.interaction_mode == "delegated_autonomous"
    assert request.disposition == "no_interrupt"
    assert request.attention_cost_rank > 0
    assert "low_voi_no_interrupt" in request.need_reasons


def test_oversight_theater_probe_invalidates_human_decision_record() -> None:
    probe = _fixture("oversight_theater_probe.json")
    request = _request_from_probe(probe)
    record = probe["record"]
    assert isinstance(record, dict)

    with pytest.raises(
        _s7("P26ResponsibilityIntegrityError"),
        match="oversight_theater",
    ):
        _s7("record_human_decision")(
            case_id=str(probe["case_id"]),
            request=request,
            rule_version_ref=RULE_VERSION_REF,
            **record,
        )


def test_wrong_role_approval_probe_invalidates_human_decision_record() -> None:
    probe = _fixture("wrong_role_approval_probe.json")
    request = _request_from_probe(probe)
    record = probe["record"]
    assert isinstance(record, dict)

    with pytest.raises(
        _s7("P26ResponsibilityIntegrityError"),
        match="wrong_role_approval",
    ):
        _s7("record_human_decision")(
            case_id=str(probe["case_id"]),
            request=request,
            rule_version_ref=RULE_VERSION_REF,
            **record,
        )


def test_ai_first_high_stakes_probe_blocks() -> None:
    probe = _fixture("ai_first_high_stakes_probe.json")

    report = _s7("evaluate_delegation_for_case")(
        case_id=str(probe["case_id"]),
        s6_mandate_posture=probe["s6_mandate_posture"],
        case_signals=probe["case_signals"],
        expert_label=probe["expert_label"],
        rule_version_ref=RULE_VERSION_REF,
    )

    assert report.disposition == "blocked_ai_first_forbidden"
    assert report.responsibility_integrity.status == "block"
    assert "P26" in report.firewall_pattern_ids


def test_mandate_absent_delegation_probe_blocks_delegated_autonomous() -> None:
    probe = _fixture("mandate_absent_delegation_probe.json")

    report = _s7("evaluate_delegation_for_case")(
        case_id=str(probe["case_id"]),
        s6_mandate_posture=probe["s6_mandate_posture"],
        case_signals=probe["case_signals"],
        expert_label=probe["expert_label"],
        rule_version_ref=RULE_VERSION_REF,
    )

    assert report.disposition == "blocked_mandate_missing"
    assert report.responsibility_integrity.status == "block"
    assert "delegated_autonomy_without_mandate" in report.block_reason


def test_s7_delegation_integrity_metric_requires_precision_recall_and_responsibility() -> None:
    metrics = _s7("s7_delegation_integrity")(
        [
            {
                "case_id": CASE_ID,
                "predicted_disposition": "request_human_decision",
                "expected_disposition": "request_human_decision",
                "responsibility_integrity_status": "pass",
                "negative_control_false_clear": False,
            },
            {
                "case_id": "oversight_theater_probe",
                "predicted_disposition": "blocked_oversight_theater",
                "expected_disposition": "blocked_oversight_theater",
                "responsibility_integrity_status": "block",
                "negative_control_false_clear": False,
            },
        ]
    )

    assert metrics["delegation_precision"] == 1.0
    assert metrics["delegation_recall"] == 1.0
    assert metrics["responsibility_integrity_pass_rate"] == 1.0
    assert metrics["oversight_theater_false_clear_count"] == 0
    assert metrics["wrong_role_false_clear_count"] == 0
    assert metrics["workflow_only_summary_false_clear_count"] == 0


def test_s7_does_not_import_production_approval_or_human_review_as_authority() -> None:
    module = importlib.import_module("polisyos.runtime.quality.design_axes.mandate_bounded_delegation")
    source = inspect.getsource(module)

    forbidden_authority_imports = (
        "from polisyos.runtime.quality.approval",
        "from polisyos.runtime.quality.human_review",
        "from polisyos.scientist.governance.human_review",
        "import polisyos.runtime.quality.approval",
        "import polisyos.runtime.quality.human_review",
        "import polisyos.scientist.governance.human_review",
    )
    assert not any(pattern in source for pattern in forbidden_authority_imports)


def test_s7_registry_contains_value_authorization_decision_class() -> None:
    registry = _registry()
    by_id = {row.decision_class_id: row for row in registry}

    assert "value_authorization" in by_id
    value_authorization = by_id["value_authorization"]
    assert value_authorization.required_role == "principal"
    assert value_authorization.high_stakes is True
    assert value_authorization.default_posture == "shadow"
    assert "value_choice_authority" in value_authorization.authority_boundary.may_not_use_for


def test_value_authorization_matrix_row_is_request_driven_and_non_autonomous() -> None:
    matrix = _matrix()
    row = matrix.row_for_decision_class("value_authorization")

    assert row.required_role == "principal"
    assert row.default_interaction_mode == "request_driven"
    assert row.ai_first_allowed is False
    assert row.delegated_autonomous_allowed is False
    assert row.non_overridable is True
    assert set(row.available_actions) == {
        "request_evidence",
        "approve",
        "reject",
        "revise_scope",
        "escalate",
    }

    request = _request(
        decision_class_id="value_authorization",
        need_reasons=["high_stakes", "value_laden"],
    )
    assert request.required_role == "principal"
    assert request.interaction_mode == "request_driven"
    assert request.disposition == "request_human_decision"
    assert "value_choice_authority" in request.authority_boundary.may_not_use_for
