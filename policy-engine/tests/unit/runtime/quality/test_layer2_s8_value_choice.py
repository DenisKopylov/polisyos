from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality as runtime_quality

CASE_ID = "ua-msme-affordable-loans-2022"
RULE_VERSION_REF = "policyos.layer2.s8.value_choice.v1"
FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures/layer2/s8"
NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _s8(name: str) -> Any:
    return getattr(runtime_quality, name)


def _authority_boundary(
    *,
    authoritative_for: list[str],
    source_authority: str = "human_governance",
    posture: str = "governed",
) -> dict[str, object]:
    return {
        "authoritative_for": authoritative_for,
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "scalar_welfare_authority",
            "preference_learning_authority",
            "mandate_creation",
            "s9_projection_maturity",
            "s10_forecast_support",
            "s11_calibration",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
        ],
        "source_authority": source_authority,
        "posture": posture,
        "rule_version_refs": [RULE_VERSION_REF],
    }


def _authorized_schedule_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schedule_id": "layer2.s8.schedule.ua-msme.2026",
        "schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "case_id": CASE_ID,
        "mandate_record_ref": "pdc://layer2/s6/ua-msme/mandate-legitimacy",
        "s6_mandate_firewall_disposition": "pass",
        "mandate_source_dispositions": ["grounded"],
        "principal_refs": ["principal://ua/ministry-of-economy"],
        "source_class": "authorized_governance_schedule",
        "review_status": "approved",
        "effective_at": NOW,
        "social_weight_provenance_refs": [
            "foundry://welfare/social-weight-provenance/public-budget-2026"
        ],
        "authority_boundary": _authority_boundary(
            authoritative_for=["authorized_value_schedule", "value_choice_provenance"]
        ),
        "may_not_use_for": [
            "production_recommendation",
            "scalar_welfare_authority",
            "preference_learning_authority",
        ],
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _objective_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_id": "layer2.s8.objective-provenance.ua-msme",
        "record_ref": "pdc://layer2/s8/ua-msme/objective-provenance",
        "case_id": CASE_ID,
        "objective_refs": [
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ],
        "objective_source_refs": ["pdc://layer2/s6/ua-msme/mandate-legitimacy"],
        "value_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "measurability_refs": ["pdc://layer2/s6/ua-msme/measurability-adequacy"],
        "proxy_value_loss_disclosures": [
            {
                "construct_ref": "construct://credit_access",
                "value_loss_disclosure_ref": "pdc://layer2/s6/ua-msme/value-loss",
            }
        ],
        "mandate_refs": ["pdc://layer2/s6/ua-msme/mandate-legitimacy"],
        "p20_firewall_status": "pass",
        "p22_firewall_status": "pass",
        "authority_boundary": _authority_boundary(
            authoritative_for=["objective_function_provenance"]
        ),
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _pareto_archive_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "archive_id": "layer2.s8.pareto-archive.ua-msme",
        "archive_ref": "pdc://layer2/s8/ua-msme/pareto-archive",
        "case_id": CASE_ID,
        "frontier_refs": ["foundry://welfare/frontier/ua-msme"],
        "nondominated_alternative_ids": ["targeted_credit", "cash_transfer"],
        "rejected_nondominated_alternative_ids": ["cash_transfer"],
        "objective_refs": [
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ],
        "value_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "ranking_mode": "ranked_with_authorized_values",
        "archive_status": "ranked_with_authorized_values",
        "scenario_value_schedule_refs": [
            "pdc://layer2/s8/ua-msme/value-schedule/shadow-scenario"
        ],
        "claim_refs": ["claim://ua-msme/welfare-frontier"],
        "audit_refs": ["cas://audit/welfare-frontier/ua-msme"],
        "authority_boundary": _authority_boundary(authoritative_for=["pareto_archive"]),
        "may_not_use_for": ["value_choice_authority", "scalar_welfare_authority"],
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _value_choice_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_id": "layer2.s8.value-choice.ua-msme",
        "record_ref": "pdc://layer2/s8/ua-msme/value-choice-provenance",
        "case_id": CASE_ID,
        "selected_alternative_ref": "alternative://targeted_credit",
        "objective_provenance_ref": "pdc://layer2/s8/ua-msme/objective-provenance",
        "value_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/authorized",
        "pareto_archive_ref": "pdc://layer2/s8/ua-msme/pareto-archive",
        "social_weight_provenance_refs": [
            "foundry://welfare/social-weight-provenance/public-budget-2026"
        ],
        "mandate_refs": ["pdc://layer2/s6/ua-msme/mandate-legitimacy"],
        "delegation_refs": ["pdc://layer2/s7/ua-msme/value-authorization-request"],
        "value_authorization_decision_refs": [
            "pdc://layer2/s7/ua-msme/value-authorization-record"
        ],
        "conflict_rows": [],
        "affected_group_rows": [
            {
                "group_ref": "group://low-income-msmes",
                "weight_ref": "swr://policy.welfare/ua-msme#low-income",
                "disclosure_ref": "pdc://layer2/s8/ua-msme/affected-groups",
            }
        ],
        "dissent_refs": ["dissent://ua-msme/sme-panel"],
        "blocking_rights_refs": ["rights://ua-msme/legal-equality"],
        "alternative_schedule_sensitivity_rows": [
            {
                "scenario_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule/scenario",
                "selected_alternative_ref": "alternative://cash_transfer",
                "status": "shadow_scenario_only",
            }
        ],
        "disposition": "authorized",
        "integrity_status": "pass",
        "replay_refs": [
            "pdc://layer2/s8/ua-msme/value-schedule/authorized",
            "pdc://layer2/s8/ua-msme/pareto-archive",
        ],
        "authority_boundary": _authority_boundary(
            authoritative_for=["value_choice_provenance"]
        ),
        "rule_version_ref": RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def test_value_choice_provenance_record_is_strict_replayable_and_mandate_bounded() -> None:
    schedule_model = _s8("AuthorizedValueSchedule")
    record_model = _s8("ValueChoiceProvenanceRecord")

    assert schedule_model.model_config.get("extra") == "forbid"
    assert record_model.model_config.get("extra") == "forbid"

    schedule = schedule_model.model_validate(_authorized_schedule_payload())
    record = record_model.model_validate(_value_choice_payload())

    assert schedule.s6_mandate_firewall_disposition == "pass"
    assert schedule.mandate_record_ref in record.mandate_refs
    assert schedule.schedule_ref == record.value_schedule_ref
    assert record.disposition == "authorized"
    assert "production_recommendation" in record.authority_boundary.may_not_use_for
    assert set(record.replay_refs) >= {schedule.schedule_ref, record.pareto_archive_ref}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        record_model.model_validate(
            {
                **record.model_dump(mode="json"),
                "hidden_scalar_welfare_score": 0.91,
            }
        )


def test_authorized_value_schedule_requires_s6_mandate_firewall_pass() -> None:
    schedule = _s8("build_authorized_value_schedule")(**_authorized_schedule_payload())

    assert schedule.s6_mandate_firewall_disposition == "pass"
    assert schedule.source_class == "authorized_governance_schedule"

    for disposition in (None, "limit", "block", "candidate_unverified"):
        with pytest.raises(_s8("P22MandateLegitimacyError"), match=r"P22|mandate"):
            _s8("build_authorized_value_schedule")(
                **_authorized_schedule_payload(
                    s6_mandate_firewall_disposition=disposition,
                )
            )


def test_pareto_archive_cannot_rank_without_authorized_value_schedule() -> None:
    archive = _s8("build_pareto_archive")(
        **_pareto_archive_payload(
            value_schedule_ref=None,
            ranking_mode="unranked_frontier_only",
            archive_status="frontier_only",
        )
    )

    assert archive.ranking_mode == "unranked_frontier_only"
    assert "value_choice_authority" in archive.may_not_use_for

    with pytest.raises(_s8("P20NormativeChoiceError"), match=r"P20|authorized"):
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(
                value_schedule_ref=None,
                ranking_mode="ranked_with_authorized_values",
                archive_status="ranking_attempted",
            )
        )


def test_p20_rejects_llm_or_corpus_derived_social_weights() -> None:
    probe = _fixture("llm_social_weight_probe.json")
    for social_weight_provenance in probe["social_weight_provenance_candidates"]:
        with pytest.raises(_s8("P20NormativeChoiceError"), match=r"P20|value|authority"):
            _s8("coerce_social_weight_provenance_for_s8")(
                social_weight_provenance,
                authority_required=True,
                rule_version_ref=RULE_VERSION_REF,
            )


def test_p22_rejects_absent_limit_block_or_candidate_unverified_mandate_source() -> None:
    probe = _fixture("blocked_mandate_value_choice_probe.json")

    for disposition in (None, "limit", "block"):
        with pytest.raises(_s8("P22MandateLegitimacyError"), match=r"P22|mandate"):
            _s8("build_authorized_value_schedule")(
                **_authorized_schedule_payload(
                    mandate_record_ref=probe["mandate_record_ref"],
                    s6_mandate_firewall_disposition=disposition,
                )
            )

    with pytest.raises(_s8("P22MandateLegitimacyError"), match="candidate_unverified"):
        _s8("build_authorized_value_schedule")(
            **_authorized_schedule_payload(
                s6_mandate_firewall_disposition="pass",
                mandate_source_dispositions=["candidate_unverified"],
            )
        )


def test_shadow_scenario_value_schedule_is_visible_but_not_authority() -> None:
    scenario = _s8("build_shadow_scenario_value_schedule")(
        schedule_ref="pdc://layer2/s8/ua-msme/value-schedule/shadow-scenario",
        case_id=CASE_ID,
        principal_refs=["principal://ua/ministry-of-economy"],
        social_weight_provenance_refs=["swr://scenario/low-income-heavy"],
        scenario_label="low-income-heavy sensitivity",
        rule_version_ref=RULE_VERSION_REF,
    )

    assert scenario.disposition == "shadow_scenario_only"
    assert "ranked_recommendation_authority" in scenario.may_not_use_for

    with pytest.raises(_s8("P20NormativeChoiceError"), match="shadow_scenario"):
        _s8("build_pareto_archive")(
            **_pareto_archive_payload(
                value_schedule_ref=scenario.schedule_ref,
                ranking_mode="ranked_with_authorized_values",
            )
        )


def test_multi_principal_conflict_is_contested_not_silent_average() -> None:
    conflict_rows = [
        {
            "principal_ref": "principal://city/tenant-board",
            "schedule_ref": "pdc://layer2/s8/rent-cap/tenant-schedule",
            "incompatible_with": ["principal://city/landlord-board"],
            "conflict_reason": "tenant stability and owner exit risk cannot be averaged",
        },
        {
            "principal_ref": "principal://city/landlord-board",
            "schedule_ref": "pdc://layer2/s8/rent-cap/owner-schedule",
            "incompatible_with": ["principal://city/tenant-board"],
            "conflict_reason": "owner solvency priority conflicts with tenant schedule",
        },
    ]
    record = _s8("build_value_choice_provenance_record")(
        **_value_choice_payload(
            conflict_rows=conflict_rows,
            disposition="authorized",
        )
    )

    assert record.disposition == "contested_multi_principal"
    assert record.conflict_rows == conflict_rows
    assert "silent_average" not in json.dumps(record.model_dump(mode="json"))

    with pytest.raises(_s8("P20NormativeChoiceError"), match=r"affected|dissent|blocking"):
        _s8("build_value_choice_provenance_record")(
            **_value_choice_payload(
                conflict_rows=conflict_rows,
                affected_group_rows=[],
                dissent_refs=[],
                blocking_rights_refs=[],
                alternative_schedule_sensitivity_rows=[],
            )
        )


def test_s7_human_decision_refs_cannot_substitute_for_s8_value_authority() -> None:
    probe = _fixture("s7_human_decision_substitution_probe.json")

    with pytest.raises(_s8("P20NormativeChoiceError"), match=r"S7|value"):
        _s8("build_value_choice_provenance_record")(
            **_value_choice_payload(
                value_schedule_ref=None,
                delegation_refs=probe["delegation_refs"],
                value_authorization_decision_refs=probe["value_authorization_decision_refs"],
                disposition="authorized",
            )
        )


def test_s7_value_authorization_route_requires_governance_decision_class_and_five_rights() -> None:
    registry = runtime_quality.build_governance_decision_class_registry(
        case_id=CASE_ID,
        rule_version_ref="policyos.layer2.s7.delegation.v1",
    )
    matrix = runtime_quality.build_decision_rights_matrix(
        case_id=CASE_ID,
        governance_decision_classes=registry,
        rule_version_ref="policyos.layer2.s7.delegation.v1",
    )
    row = matrix.row_for_decision_class("value_authorization")

    assert row.required_role == "principal"
    assert row.default_interaction_mode == "request_driven"
    assert row.ai_first_allowed is False
    assert row.delegated_autonomous_allowed is False
    assert set(row.five_rights_dimensions) == {
        "right_decision",
        "right_person",
        "right_information",
        "right_format_channel",
        "right_time",
    }

    with pytest.raises(_s8("P26ResponsibilityIntegrityError"), match="value_authorization"):
        _s8("build_authorized_value_schedule")(
            **_authorized_schedule_payload(
                s7_decision_rights_matrix_ref=matrix.matrix_ref,
                s7_value_authorization_request_ref=(
                    "pdc://layer2/s7/ua-msme/human-decision-request/a_spec_gap"
                ),
                s7_value_authorization_record_ref=(
                    "pdc://layer2/s7/ua-msme/human-decision-record/a_spec_gap"
                ),
                s7_value_authorization_decision_class_id="a_spec_gap",
                s7_five_rights_passed=True,
            )
        )


def test_value_tradeoff_disclosure_has_audience_bounded_public_projection() -> None:
    public = _s8("project_value_tradeoff_disclosure")(
        value_choice_record=_value_choice_payload(),
        audience="PUBLIC",
        rule_version_ref=RULE_VERSION_REF,
    )
    machine = _s8("project_value_tradeoff_disclosure")(
        value_choice_record=_value_choice_payload(),
        audience="MACHINE",
        rule_version_ref=RULE_VERSION_REF,
    )

    public_payload = public.model_dump(mode="json")
    machine_payload = machine.model_dump(mode="json")
    assert public_payload["audience"] == "PUBLIC"
    assert public_payload["decision_tradeoff_summary"]
    assert "raw_social_weights" not in public_payload
    assert "value_schedule_details" not in public_payload
    assert machine_payload["audience"] == "MACHINE"
    assert machine_payload["value_schedule_ref"] == _value_choice_payload()["value_schedule_ref"]
    assert machine_payload["affected_group_rows"]
    assert machine_payload["authority_boundary"]["may_not_use_for"]


def test_value_choice_records_are_exported_from_runtime_quality() -> None:
    required_exports = {
        "LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION",
        "LAYER2_S8_VALUE_CHOICE_RULE_VERSION",
        "S8_VALUE_CHOICE_CELL_REF",
        "S8_VALUE_CHOICE_FLOOR_ID",
        "AuthorizedValueSchedule",
        "ObjectiveFunctionProvenanceRecord",
        "ParetoArchive",
        "ValueChoiceProvenanceRecord",
        "ValueTradeoffDisclosureRecord",
        "ValueChoiceIntegrityReport",
        "P20NormativeChoiceError",
        "P22MandateLegitimacyError",
        "build_authorized_value_schedule",
        "build_shadow_scenario_value_schedule",
        "build_objective_function_provenance",
        "build_pareto_archive",
        "build_value_choice_provenance_record",
        "project_value_tradeoff_disclosure",
        "s8_value_provenance_integrity",
    }

    missing = sorted(name for name in required_exports if not hasattr(runtime_quality, name))
    assert missing == []
