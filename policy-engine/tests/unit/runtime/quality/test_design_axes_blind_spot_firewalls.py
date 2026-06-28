from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.pdc import AxisFirewallStatus, AxisPositionDeclaration
from polisyos.runtime.quality.design_axes.blind_spot_firewalls import (
    AggregationValidityRecord,
    BlindSpotFirewallReport,
    CapacityFeasibilityRecord,
    ClusterAuthorityDimensionRecord,
    MandateLegitimacyRecord,
    MeasurabilityAdequacyRecord,
    P18StreetlightMeasurabilityError,
    P19AggregationLaunderingError,
    P21CapacityFeasibilityError,
    P22MandateLegitimacyError,
    P24StrategicResponseError,
    StrategicResponseRecord,
    build_s6_blind_spot_firewall_report,
    evaluate_aggregation_validity,
    evaluate_capacity_feasibility,
    evaluate_mandate_legitimacy,
    evaluate_measurability_adequacy,
    evaluate_strategic_response,
    s6_fail_closed_coverage,
    s6_firewall_report_to_axis_positions,
    s6_firewall_report_to_c3_dimension_records,
)

RULE_REF = "repo://docs/reference/policy-design-case-failure-patterns.md#S6"
FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "layer2" / "s6"

NEGATIVE_PROBE_FIXTURES = (
    "streetlight_proxy_laundering_probe.json",
    "aggregation_scope_drift_probe.json",
    "capacity_fantasy_probe.json",
    "mandate_speculation_probe.json",
    "goodhart_post_intervention_probe.json",
)

S6_CELL_REFS = {
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
    "ACTOR.state_capacity_feasibility",
    "ACTOR.mandate_legitimacy",
    "OTHER_AGENTS.strategic_response",
}

S6_C3_DIMENSIONS = {
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
}


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


def _valid_records() -> tuple[
    MeasurabilityAdequacyRecord,
    AggregationValidityRecord,
    CapacityFeasibilityRecord,
    MandateLegitimacyRecord,
    StrategicResponseRecord,
]:
    case_id = "s6_valid_fixture"
    design_ref = "pdc://layer2/s6/valid/design"
    measurability = evaluate_measurability_adequacy(
        case_id=case_id,
        design_ref=design_ref,
        construct_rows=[
            {
                "construct_ref": "construct://eligible-applications",
                "construct_label": "eligible applications",
                "measurability_status": "observed",
                "proxy_validity": "not_applicable",
                "value_loss_disclosure_ref": "disclosure://none-required",
                "evidence_refs": ["fixture://layer2/s6/valid/measurability"],
            }
        ],
        semantic_binding_ledger={
            "ledger_ref": "fixture://layer2/s6/valid/semantic-binding-ledger",
            "declared_measurability_pass": False,
        },
        rule_version_ref=RULE_REF,
    )
    aggregation = evaluate_aggregation_validity(
        case_id=case_id,
        design_ref=design_ref,
        claim_scope="firm",
        evidence_scope="firm",
        aggregation_rows=[
            {
                "claim_scope": "firm",
                "evidence_scope": "firm",
                "aggregation_validity": "valid",
                "validity_proof_ref": "fixture://layer2/s6/valid/aggregation-proof",
                "evidence_refs": ["fixture://layer2/s6/valid/firm-level-panel"],
            }
        ],
        concept_spine_carrier={
            "carrier_ref": "fixture://layer2/s6/valid/concept-spine-carrier",
            "declared_aggregation_pass": False,
        },
        rule_version_ref=RULE_REF,
    )
    capacity = evaluate_capacity_feasibility(
        case_id=case_id,
        design_ref=design_ref,
        actor_ref="actor://program-operator",
        jurisdiction_ref="jurisdiction://ua",
        instrument_ref="instrument://audited-benefit-rule",
        capacity_dimensions=[
            {
                "dimension": "administrative",
                "required": True,
                "disposition": "grounded",
                "evidence_ref": "fixture://layer2/s6/valid/admin-capacity",
                "capacity_building_obligation_ref": None,
            },
            {
                "dimension": "participation_capacity",
                "required": True,
                "disposition": "grounded",
                "evidence_ref": "fixture://layer2/s6/valid/participation-capacity",
                "capacity_building_obligation_ref": None,
            },
        ],
        rule_version_ref=RULE_REF,
    )
    mandate = evaluate_mandate_legitimacy(
        case_id=case_id,
        design_ref=design_ref,
        objective_refs=["objective://audited-benefit-access"],
        mandate_sources=[
            {
                "basis": "statutory",
                "source_authority": "human_governance",
                "source_ref": "legal://ua/benefit-statute",
                "provenance_ref": "fixture://layer2/s6/valid/statutory-mandate",
                "disposition": "grounded",
                "authorized_objective_refs": ["objective://audited-benefit-access"],
            }
        ],
        participation_evaluations=[
            {
                "evaluation_ref": "fixture://layer2/s6/valid/participation-evaluation",
                "claim_use_allowed": True,
                "blockers": [],
            }
        ],
        consultation_validations=[
            {
                "validation_ref": "fixture://layer2/s6/valid/consultation-validation",
                "unresolved_high_severity_objection": False,
            }
        ],
        rule_version_ref=RULE_REF,
    )
    strategic_response = evaluate_strategic_response(
        case_id=case_id,
        design_ref=design_ref,
        response_channels=[
            {
                "channel": "compliance_response",
                "disposition": "modeled",
                "risk_level": "low",
                "response_model_ref": "fixture://layer2/s6/valid/compliance-response-model",
                "post_intervention_dgp_update_ref": (
                    "pdc://layer2/s6/s6_valid_fixture/post-intervention-dgp"
                ),
                "evidence_refs": ["fixture://layer2/s6/valid/compliance-response"],
            }
        ],
        pre_policy_effect_refs=["effect://pre-policy/audited-benefit-access"],
        s5_composition_posture={
            "composition_disposition": "compose_with_limitations",
            "system_dynamics_requirement_ref": None,
        },
        strategic_response_entries=[
            {
                "entry_ref": "fixture://layer2/s6/valid/strategic-response-entry",
                "projected_post_policy_effect_ref": "effect://post-policy/audited-benefit-access",
                "declared_unchanged_effect": False,
            }
        ],
        rule_version_ref=RULE_REF,
    )
    return measurability, aggregation, capacity, mandate, strategic_response


def _valid_report() -> BlindSpotFirewallReport:
    measurability, aggregation, capacity, mandate, strategic_response = _valid_records()
    return build_s6_blind_spot_firewall_report(
        case_id="s6_valid_fixture",
        design_ref="pdc://layer2/s6/valid/design",
        measurability=measurability,
        aggregation=aggregation,
        capacity=capacity,
        mandate=mandate,
        strategic_response=strategic_response,
        rule_version_ref=RULE_REF,
    )


def test_proxy_only_construct_records_value_loss_and_blocks_streetlight_pass() -> None:
    probe = _fixture("streetlight_proxy_laundering_probe.json")

    with pytest.raises(P18StreetlightMeasurabilityError, match=r"P18|value|proxy"):
        evaluate_measurability_adequacy(
            case_id=probe["case_id"],
            design_ref=probe["design_ref"],
            construct_rows=probe["construct_rows"],
            semantic_binding_ledger={
                "ledger_ref": probe["semantic_binding_ledger_ref"],
                "declared_measurability_pass": probe["declared_measurability_pass"],
            },
            rule_version_ref=probe["rule_version_ref"],
        )


def test_jurisdiction_average_hiding_subgroup_harm_fails_p19() -> None:
    probe = _fixture("aggregation_scope_drift_probe.json")

    with pytest.raises(P19AggregationLaunderingError, match=r"P19|aggregation|scope"):
        evaluate_aggregation_validity(
            case_id=probe["case_id"],
            design_ref=probe["design_ref"],
            claim_scope=probe["claim_scope"],
            evidence_scope=probe["evidence_scope"],
            aggregation_rows=probe["aggregation_rows"],
            concept_spine_carrier={
                "carrier_ref": probe["concept_spine_carrier_ref"],
                "declared_aggregation_pass": probe["declared_aggregation_pass"],
            },
            rule_version_ref=probe["rule_version_ref"],
        )


def test_capacity_assumption_copied_across_jurisdictions_fails_p21() -> None:
    probe = _fixture("capacity_fantasy_probe.json")

    with pytest.raises(P21CapacityFeasibilityError, match=r"P21|capacity|obligation"):
        evaluate_capacity_feasibility(
            case_id=probe["case_id"],
            design_ref=probe["design_ref"],
            actor_ref=probe["actor_ref"],
            jurisdiction_ref=probe["jurisdiction_ref"],
            instrument_ref=probe["instrument_ref"],
            capacity_dimensions=probe["capacity_dimensions"],
            rule_version_ref=probe["rule_version_ref"],
        )


def test_llm_participation_speculation_cannot_authorize_mandate() -> None:
    probe = _fixture("mandate_speculation_probe.json")

    with pytest.raises(P22MandateLegitimacyError, match=r"P22|LLM|mandate|participation"):
        evaluate_mandate_legitimacy(
            case_id=probe["case_id"],
            design_ref=probe["design_ref"],
            objective_refs=probe["objective_refs"],
            mandate_sources=probe["mandate_sources"],
            participation_evaluations=probe["participation_evaluations"],
            consultation_validations=probe["consultation_validations"],
            rule_version_ref=probe["rule_version_ref"],
        )


def test_goodhart_probe_updates_post_intervention_dgp_and_blocks_unchanged_effect() -> None:
    probe = _fixture("goodhart_post_intervention_probe.json")

    with pytest.raises(P24StrategicResponseError, match=r"P24|Goodhart|DGP|unchanged"):
        evaluate_strategic_response(
            case_id=probe["case_id"],
            design_ref=probe["design_ref"],
            response_channels=probe["response_channels"],
            pre_policy_effect_refs=probe["pre_policy_effect_refs"],
            s5_composition_posture=probe["s5_composition_posture"],
            strategic_response_entries=[
                {
                    "projected_post_policy_effect_ref": probe["projected_post_policy_effect_ref"],
                    "declared_unchanged_effect": probe["declared_unchanged_effect"],
                }
            ],
            rule_version_ref=probe["rule_version_ref"],
        )


def test_absent_axis_evidence_defaults_to_limit_or_block_not_pass() -> None:
    records = (
        evaluate_measurability_adequacy(
            case_id="s6_absent_fixture",
            design_ref="pdc://layer2/s6/absent/design",
            construct_rows=[],
            semantic_binding_ledger=None,
            rule_version_ref=RULE_REF,
        ),
        evaluate_aggregation_validity(
            case_id="s6_absent_fixture",
            design_ref="pdc://layer2/s6/absent/design",
            claim_scope="firm",
            evidence_scope="firm",
            aggregation_rows=[],
            concept_spine_carrier=None,
            rule_version_ref=RULE_REF,
        ),
        evaluate_capacity_feasibility(
            case_id="s6_absent_fixture",
            design_ref="pdc://layer2/s6/absent/design",
            actor_ref="actor://missing",
            jurisdiction_ref="jurisdiction://missing",
            instrument_ref="instrument://missing",
            capacity_dimensions=[],
            rule_version_ref=RULE_REF,
        ),
        evaluate_mandate_legitimacy(
            case_id="s6_absent_fixture",
            design_ref="pdc://layer2/s6/absent/design",
            objective_refs=["objective://missing"],
            mandate_sources=[],
            participation_evaluations=[],
            consultation_validations=[],
            rule_version_ref=RULE_REF,
        ),
        evaluate_strategic_response(
            case_id="s6_absent_fixture",
            design_ref="pdc://layer2/s6/absent/design",
            response_channels=[],
            pre_policy_effect_refs=[],
            s5_composition_posture=None,
            strategic_response_entries=[],
            rule_version_ref=RULE_REF,
        ),
    )

    assert {record.firewall_disposition for record in records} <= {"limit", "block"}
    assert "pass" not in {record.firewall_disposition for record in records}


def test_cluster_authority_dimension_records_cover_all_five_axes() -> None:
    report = _valid_report()

    dimension_records = s6_firewall_report_to_c3_dimension_records(report)

    assert all(isinstance(record, ClusterAuthorityDimensionRecord) for record in dimension_records)
    assert {record.cell_ref for record in dimension_records} == S6_CELL_REFS
    assert {record.authority_dimension for record in dimension_records} == S6_C3_DIMENSIONS
    assert all(record.maturity == "fail_closed" for record in dimension_records)
    assert all(record.producer_ref.startswith("pdc://layer2/s6/") for record in dimension_records)


def test_s6_records_are_strict_frozen_and_replayable() -> None:
    measurability = _valid_records()[0]
    payload = measurability.model_dump()
    payload["unexpected_field"] = "nope"

    with pytest.raises(ValidationError):
        MeasurabilityAdequacyRecord.model_validate(payload)
    with pytest.raises(ValidationError):
        measurability.firewall_disposition = "pass"  # type: ignore[misc]

    replayed = MeasurabilityAdequacyRecord.model_validate_json(measurability.model_dump_json())
    assert replayed.model_dump() == measurability.model_dump()
    assert measurability.record_ref == "pdc://layer2/s6/s6_valid_fixture/measurability-adequacy"


def test_s6_report_exports_axis_positions_firewalls_and_refs() -> None:
    report = _valid_report()
    positions, firewalls = s6_firewall_report_to_axis_positions(report)
    record_refs = {record.record_ref for record in _valid_records()}

    assert isinstance(report, BlindSpotFirewallReport)
    assert all(isinstance(position, AxisPositionDeclaration) for position in positions)
    assert all(isinstance(firewall, AxisFirewallStatus) for firewall in firewalls)
    assert {position.cell_ref for position in positions} == S6_CELL_REFS
    assert {firewall.cell_ref for firewall in firewalls} == S6_CELL_REFS
    assert {"P18", "P19", "P21", "P22", "P24"} <= set().union(
        *(set(firewall.pattern_ids) for firewall in firewalls)
    )
    assert record_refs <= set(report.ledger_refs)
    assert "pdc://layer2/s6/s6_valid_fixture/cluster-authority-dimensions" in report.ledger_refs


def test_s6_fail_closed_coverage_counts_all_five_negative_controls() -> None:
    probe_results = [
        {
            "case_id": probe["case_id"],
            "axis": probe["axis"],
            "expected_error": probe["expected_error"],
            "observed_error": probe["expected_error"],
            "observed_disposition": probe["expected_fail_closed_disposition"],
            "false_clear": False,
        }
        for probe in (_fixture(name) for name in NEGATIVE_PROBE_FIXTURES)
    ]

    coverage = s6_fail_closed_coverage(probe_results)

    assert coverage["case_count"] == 5
    assert coverage["axis_coverage_count"] == 5
    assert coverage["all_five_axes_covered"] is True
    assert coverage["per_axis_fail_closed_negative_control_pass_rate"] == pytest.approx(1.0)
    assert coverage["false_clear_count"] == 0
