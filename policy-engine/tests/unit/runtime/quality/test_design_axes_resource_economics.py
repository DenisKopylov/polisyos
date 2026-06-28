from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality as runtime_quality
from polisyos.pdc import ValueOfInformationEstimate

CASE_ID = "ua-msme-affordable-loans-2022"
S12_RULE_VERSION_REF = "policyos.layer2.s12.resource_economics.v1"
REPO_ROOT = Path(__file__).resolve().parents[4]
NEGATIVE_CONTROL_DIR = REPO_ROOT / "tests/fixtures/layer2/s12/negative_controls"
S12_REQUIRED_ARTIFACTS = (
    "KnowledgeGovernanceThroughputLedger",
    "EnvelopeGrowthLedger",
    "ResourceAllocationPolicy",
    "GrowthThermometerRecord",
    "ResourceEconomicsIntegrityReport",
)
S12_REQUIRED_HELPERS = (
    "allocate_value_of_information",
    "build_resource_allocation_policy",
    "build_envelope_growth_ledger",
    "build_growth_thermometers",
    "build_knowledge_governance_throughput_ledger",
    "resolve_s12_resource_refs",
    "verify_resource_authority_envelope",
    "summarize_resource_economics_integrity",
    "build_s12_resource_economics_posture",
)
S12_DENY = (
    "production_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "mdp_bandit_optimizer_authority",
    "budget_interchangeability",
    "mission_or_value_self_authorization",
    "floor_relaxation",
    "s13_envelope_shrink",
    "s13_accountability_closure",
    "s14_universality",
)


def _runtime_attr(name: str) -> Any:
    return getattr(runtime_quality, name)


def _authority_boundary() -> dict[str, object]:
    return {
        "authoritative_for": [
            "value_of_information_allocation",
            "explore_exploit_posture",
            "envelope_growth_ledger",
            "growth_thermometers",
            "knowledge_governance_throughput",
            "allocation_priority_input",
            "expert_machine_resource_projection",
        ],
        "may_not_use_for": list(S12_DENY),
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": [S12_RULE_VERSION_REF],
    }


def _voi_estimates() -> list[ValueOfInformationEstimate]:
    return [
        ValueOfInformationEstimate(
            estimate_id="s12_acquisition_voi",
            purpose="Rank unresolved acquisition gaps without scalarizing budgets.",
            budget_dimensions=["acquisition_money", "legal_access"],
            used_by_sites=["layer2_s3_substrate_acquisition"],
            owner="principal-governance",
            rule_version_ref=S12_RULE_VERSION_REF,
        ),
        ValueOfInformationEstimate(
            estimate_id="s12_refinement_voi",
            purpose="Prioritize S2 refinement while preserving shadow-only posture.",
            budget_dimensions=["compute"],
            used_by_sites=["layer2.s2.shadow_design_loop"],
            owner="principal-governance",
            rule_version_ref=S12_RULE_VERSION_REF,
        ),
        ValueOfInformationEstimate(
            estimate_id="s12_attention_voi",
            purpose="Route high-stakes human attention through S7 decision rights.",
            budget_dimensions=["human_attention", "expert_time"],
            used_by_sites=["layer2.s7.attention"],
            owner="principal-governance",
            rule_version_ref=S12_RULE_VERSION_REF,
        ),
    ]


def _false_clear_counts() -> dict[str, int]:
    return dict.fromkeys(_runtime_attr("S12_FALSE_CLEAR_FIELDS"), 0)


def _allocation_policy_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": _runtime_attr("LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION"),
        "policy_id": "s12.resource-allocation.ua-msme",
        "policy_ref": "pdc://layer2/s12/ua-msme/resource-allocation-policy",
        "case_id": CASE_ID,
        "explore_exploit_posture": "balanced_governed",
        "explore_exploit_dial_ref": "pdc://layer2/s7/ua-msme/explore-exploit-dial",
        "delegation_contract_ref": "pdc://layer2/s7/ua-msme/delegation-contract",
        "principal_ref": "principal://ua/policy-design-governance-reviewer",
        "mission_ref": "mission://ua-msme/credit-access",
        "voi_allocations": [
            {
                "site": "acquisition",
                "voi_estimate_ref": "voi://s12/acquisition",
                "budget_kind": "acquisition_money",
                "used_by_sites": ["layer2_s3_substrate_acquisition"],
            },
            {
                "site": "refinement",
                "voi_estimate_ref": "voi://s12/refinement",
                "budget_kind": "compute",
                "used_by_sites": ["layer2.s2.shadow_design_loop"],
            },
            {
                "site": "attention",
                "voi_estimate_ref": "voi://s12/attention",
                "budget_kind": "human_attention",
                "used_by_sites": ["layer2.s7.attention"],
            },
        ],
        "voi_site_count": 3,
        "typed_budget_rows": [
            {
                "budget_kind": "compute",
                "budget_ref": "budget://ua-msme/compute",
                "voi_estimate_ref": "voi://s12/refinement",
            },
            {
                "budget_kind": "acquisition_money",
                "budget_ref": "budget://ua-msme/acquisition",
                "voi_estimate_ref": "voi://s12/acquisition",
            },
            {
                "budget_kind": "expert_time",
                "budget_ref": "budget://ua-msme/expert-time",
                "voi_estimate_ref": "voi://s12/attention",
            },
            {
                "budget_kind": "human_attention",
                "budget_ref": "budget://ua-msme/human-attention",
                "voi_estimate_ref": "voi://s12/attention",
            },
            {
                "budget_kind": "legal_access",
                "budget_ref": "budget://ua-msme/legal-access",
                "voi_estimate_ref": "voi://s12/acquisition",
            },
        ],
        "pareto_archive_ref": "pdc://layer2/s8/ua-msme/allocation-pareto-archive",
        "ranking_mode": "ranked_with_authorized_values",
        "selected_policy_ref": "allocation-policy://ua-msme/balanced-governed",
        "rejected_nondominated_policy_refs": [
            "allocation-policy://ua-msme/acquisition-heavy"
        ],
        "allocation_priority_rows": [
            {
                "priority_ref": "priority://ua-msme/acquisition/source-rights",
                "site": "acquisition",
                "budget_kind": "legal_access",
                "reason": "Source-rights gap blocks admissible substrate use.",
            }
        ],
        "disposition": "advisory_only",
        "limitation_refs": ["limitation://s12/no-production-authority"],
        "authority_boundary": _authority_boundary(),
        "may_not_use_for": list(S12_DENY),
        "rule_version_ref": S12_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _growth_ledger_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": _runtime_attr("LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION"),
        "ledger_id": "s12.envelope-growth.ua-msme",
        "ledger_ref": "pdc://layer2/s12/ua-msme/envelope-growth-ledger",
        "case_id": CASE_ID,
        "growth_entries": [
            {
                "entry_ref": "pdc://layer2/s12/ua-msme/growth-entry/001",
                "demand_act_ref": "demand-act://ua-msme/value-authorization",
                "certified_envelope_delta_ref": "delta://layer2/open-cell-count/1-to-0",
                "pending_envelope_delta_ref": None,
                "growth_counting_disposition": "counted_mechanism_growth",
                "reuse_evidence_refs": ["primitive://facet/actor"],
                "bespoke_flag_reason": None,
                "a_completeness_delta_ref": "delta://ua-msme/a-completeness/covered",
                "b_capability_delta_ref": "delta://ua-msme/b-capability/covered",
            }
        ],
        "counted_mechanism_growth_count": 1,
        "flagged_bespoke_one_off_count": 0,
        "blocked_no_envelope_delta_count": 0,
        "cluster_map_open_cell_count_before": 1,
        "cluster_map_open_cell_count_after": 0,
        "authority_boundary": _authority_boundary(),
        "may_not_use_for": list(S12_DENY),
        "rule_version_ref": S12_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _thermometer_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": _runtime_attr("LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION"),
        "thermometer_id": "s12.growth-thermometer.ua-msme",
        "thermometer_ref": "pdc://layer2/s12/ua-msme/growth-thermometer",
        "case_id": CASE_ID,
        "override_rate": 0.0,
        "override_rate_trend": "flat",
        "override_decision_kinds": [
            "final_choice",
            "value_authorization",
            "a_spec_gap",
            "mandate_boundary",
        ],
        "uninstrumented_override_dimensions": ["regime", "decomposition"],
        "required_question_count": 4,
        "reuse_rate": 1.0,
        "reuse_rate_trend": "improving",
        "frozen_primitive_set_ref": (
            "repo://architecture/policy_design_case/layer2_minimal_seed_manifest.json"
        ),
        "reused_primitive_refs": [
            "facet://actor",
            "facet://instrument",
            "projection://authority_boundary",
        ],
        "one_off_growth_refs": [],
        "held_out_status": "pending_s14",
        "held_out_battery_ref": None,
        "floor_id": "s12_growth_thermometers",
        "floor_passed": True,
        "threshold_ref": (
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s12"
        ),
        "authority_boundary": _authority_boundary(),
        "may_not_use_for": list(S12_DENY),
        "rule_version_ref": S12_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _throughput_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": _runtime_attr("LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION"),
        "ledger_id": "s12.knowledge-throughput.ua-msme",
        "ledger_ref": "pdc://layer2/s12/ua-msme/knowledge-throughput-ledger",
        "case_id": CASE_ID,
        "throughput_rows": [
            {
                "mode": "automated_proposal",
                "cost_ref": "cost://s12/automated-proposal",
                "latency_ref": "latency://s12/automated-proposal",
            },
            {
                "mode": "human_reviewed",
                "cost_ref": "cost://s12/human-reviewed",
                "latency_ref": "latency://s12/human-reviewed",
            },
        ],
        "governance_mode_counts": {
            "automated_proposal": 1,
            "human_reviewed": 1,
            "institution_owned": 0,
            "manual_bespoke": 0,
        },
        "manual_bespoke_ratio": 0.0,
        "authority_boundary": _authority_boundary(),
        "may_not_use_for": list(S12_DENY),
        "rule_version_ref": S12_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _integrity_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": _runtime_attr("LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION"),
        "report_id": "s12.resource-economics.integrity",
        "case_count": 13,
        "voi_site_count": 3,
        "typed_budget_count": 5,
        "override_rate_trend": "flat",
        "reuse_rate_trend": "improving",
        "held_out_status": "pending_s14",
        "counted_mechanism_growth_count": 1,
        "flagged_bespoke_one_off_count": 0,
        "growth_without_envelope_delta_count": 0,
        "weakest_boundary_inheritance_count": 13,
        "false_clear_counts": _false_clear_counts(),
        "authority_boundary": _authority_boundary(),
        "may_not_use_for": list(S12_DENY),
        "rule_version_ref": S12_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _row_value(row: object, key: str) -> object:
    if isinstance(row, dict):
        return row[key]
    return getattr(row, key)


def _load_probe(name: str) -> dict[str, object]:
    return json.loads((NEGATIVE_CONTROL_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _assert_probe_blocks(name: str) -> None:
    probe = _load_probe(name)
    result = _runtime_attr("verify_resource_authority_envelope")(probe)
    payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)

    assert payload["disposition"] == probe["expected_disposition"]
    assert probe["false_clear_field"] in set(payload["issue_codes"])
    assert payload["false_clear_counts"][probe["false_clear_field"]] == (
        probe["expected_false_clear_count"]
    )


def test_s12_contracts_are_strict_replayable_and_exported() -> None:
    for name in (
        "LAYER2_S12_RESOURCE_ECONOMICS_SCHEMA_VERSION",
        "LAYER2_S12_RESOURCE_ECONOMICS_RULE_VERSION",
        "S12_GROWTH_THERMOMETERS_FLOOR_ID",
        "S12_VOI_SITES",
        "S12_TYPED_BUDGETS",
        "S12_FALSE_CLEAR_FIELDS",
        *S12_REQUIRED_ARTIFACTS,
        *S12_REQUIRED_HELPERS,
    ):
        _runtime_attr(name)
        assert name in runtime_quality.__all__, name

    for artifact_name in S12_REQUIRED_ARTIFACTS:
        artifact = _runtime_attr(artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name

    report_model = _runtime_attr("ResourceEconomicsIntegrityReport")
    report = report_model.model_validate(_integrity_payload())
    report_json = report.model_dump(mode="json")
    assert json.loads(json.dumps(report_json)) == report_json

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        report_model.model_validate(
            {
                **report_json,
                "production_recommendation": "allocate to selected policy",
            }
        )


def test_voi_allocation_uses_shared_currency_across_at_least_three_sites() -> None:
    allocation = _runtime_attr("allocate_value_of_information")(
        case_id=CASE_ID,
        voi_estimates=_voi_estimates(),
        rule_version_ref=S12_RULE_VERSION_REF,
    )

    assert allocation.voi_site_count >= 3
    assert {row.site for row in allocation.voi_allocations} >= {
        "acquisition",
        "refinement",
        "attention",
    }
    assert all(row.shared_currency == "ValueOfInformationEstimate" for row in allocation.voi_allocations)
    assert all(row.numeric_voi_score is None for row in allocation.voi_allocations)


def test_s12_resource_refs_resolve_real_objects_and_downgrade_authorial_refs() -> None:
    allocation = _runtime_attr("allocate_value_of_information")(
        case_id=CASE_ID,
        voi_estimates=_voi_estimates(),
        rule_version_ref=S12_RULE_VERSION_REF,
    )
    policy = _runtime_attr("build_resource_allocation_policy")(
        case_id=CASE_ID,
        delegation_contract_ref="pdc://layer2/s7/ua-msme/delegation-contract",
        explore_exploit_dial_ref="pdc://layer2/s7/ua-msme/explore-exploit-dial",
        principal_ref="principal://ua/policy-design-governance-reviewer",
        mission_ref="mission://ua-msme/credit-access",
        voi_estimates=_voi_estimates(),
        candidate_policy_refs=[
            "allocation-policy://ua-msme/acquisition-heavy",
            "allocation-policy://ua-msme/balanced-governed",
        ],
        rule_version_ref=S12_RULE_VERSION_REF,
    )

    resolutions = _runtime_attr("resolve_s12_resource_refs")(
        [
            allocation.allocation_ref,
            policy.policy_ref,
            allocation.voi_allocations[0].voi_estimate_ref,
            "voi://ua-msme/layer3-g5",
        ],
        voi_allocations=(allocation,),
        allocation_policies=(policy,),
    )
    by_ref = {resolution.source_ref: resolution for resolution in resolutions}

    assert by_ref[allocation.allocation_ref].disposition == "authority_admitted"
    assert by_ref[policy.policy_ref].resolved_object_type == "ResourceAllocationPolicy"
    assert (
        by_ref[allocation.voi_allocations[0].voi_estimate_ref].resolved_object_type
        == "ValueOfInformationAllocation"
    )
    assert by_ref["voi://ua-msme/layer3-g5"].disposition == "candidate_only"
    assert "s12_ref_non_dereferenceable" in by_ref["voi://ua-msme/layer3-g5"].issue_codes


def test_typed_budgets_are_not_freely_interchangeable() -> None:
    policy = _runtime_attr("ResourceAllocationPolicy").model_validate(
        _allocation_policy_payload()
    )

    assert {_row_value(row, "budget_kind") for row in policy.typed_budget_rows} == set(
        _runtime_attr("S12_TYPED_BUDGETS")
    )
    assert all(_row_value(row, "budget_ref") for row in policy.typed_budget_rows)
    assert not any(
        _row_value(row, "budget_kind") == "compute"
        and _row_value(row, "budget_ref") == "budget://ua-msme/human-attention"
        for row in policy.typed_budget_rows
    )
    _assert_probe_blocks("interchangeable_budget_probe")


def test_explore_exploit_posture_reads_s7_delegation_dial_not_self_set() -> None:
    policy = _runtime_attr("build_resource_allocation_policy")(
        case_id=CASE_ID,
        delegation_contract_ref="pdc://layer2/s7/ua-msme/delegation-contract",
        explore_exploit_dial_ref="pdc://layer2/s7/ua-msme/explore-exploit-dial",
        principal_ref="principal://ua/policy-design-governance-reviewer",
        mission_ref="mission://ua-msme/credit-access",
        voi_estimates=_voi_estimates(),
        candidate_policy_refs=[
            "allocation-policy://ua-msme/acquisition-heavy",
            "allocation-policy://ua-msme/balanced-governed",
        ],
        rule_version_ref=S12_RULE_VERSION_REF,
    )

    assert policy.explore_exploit_dial_ref == "pdc://layer2/s7/ua-msme/explore-exploit-dial"
    assert policy.explore_exploit_posture in {
        "exploit_in_envelope",
        "invest_in_growth",
        "balanced_governed",
    }
    assert "mission_or_value_self_authorization" in policy.may_not_use_for
    _assert_probe_blocks("meta_regress_past_principal_probe")


def test_allocation_policy_presents_pareto_frontier_not_hidden_scalar() -> None:
    policy = _runtime_attr("ResourceAllocationPolicy").model_validate(
        _allocation_policy_payload()
    )

    assert policy.pareto_archive_ref
    assert policy.ranking_mode == "ranked_with_authorized_values"
    assert policy.selected_policy_ref
    assert policy.rejected_nondominated_policy_refs
    assert not hasattr(policy, "hidden_scalar_score")
    assert "mdp_bandit_optimizer_authority" in policy.may_not_use_for


def test_growth_entry_requires_certified_envelope_delta() -> None:
    ledger_model = _runtime_attr("EnvelopeGrowthLedger")
    invalid_entry = {
        "entry_ref": "pdc://layer2/s12/ua-msme/growth-entry/no-delta",
        "demand_act_ref": "demand-act://ua-msme/value-authorization",
        "certified_envelope_delta_ref": None,
        "pending_envelope_delta_ref": None,
        "growth_counting_disposition": "counted_mechanism_growth",
        "reuse_evidence_refs": ["primitive://facet/actor"],
        "bespoke_flag_reason": None,
        "a_completeness_delta_ref": "delta://ua-msme/a-completeness/covered",
        "b_capability_delta_ref": "delta://ua-msme/b-capability/covered",
    }

    with pytest.raises(ValidationError, match="envelope delta"):
        ledger_model.model_validate(_growth_ledger_payload(growth_entries=[invalid_entry]))

    _assert_probe_blocks("growth_without_envelope_delta_probe")


def test_bespoke_one_off_growth_is_flagged_not_counted_as_mechanism_growth() -> None:
    ledger = _runtime_attr("EnvelopeGrowthLedger").model_validate(
        _growth_ledger_payload(
            growth_entries=[
                {
                    "entry_ref": "pdc://layer2/s12/ua-msme/growth-entry/bespoke",
                    "demand_act_ref": "demand-act://ua-msme/ad-hoc-dashboard",
                    "certified_envelope_delta_ref": None,
                    "pending_envelope_delta_ref": "pending-delta://ua-msme/bespoke",
                    "growth_counting_disposition": "flagged_bespoke_one_off",
                    "reuse_evidence_refs": [],
                    "bespoke_flag_reason": "construct is not in the frozen seed primitive set",
                    "a_completeness_delta_ref": "delta://ua-msme/a-completeness/flat",
                    "b_capability_delta_ref": "delta://ua-msme/b-capability/bespoke",
                }
            ],
            counted_mechanism_growth_count=0,
            flagged_bespoke_one_off_count=1,
        )
    )

    assert ledger.counted_mechanism_growth_count == 0
    assert ledger.flagged_bespoke_one_off_count == 1
    _assert_probe_blocks("bespoke_one_off_growth_probe")


def test_allocation_gaming_internal_metrics_is_blocked() -> None:
    _assert_probe_blocks("allocation_gaming_internal_metrics_probe")


def test_floor_lowering_for_useful_design_rate_is_blocked() -> None:
    _assert_probe_blocks("floor_lowering_for_useful_design_rate_probe")


def test_b_capability_cannot_grow_faster_than_a_completeness_in_same_envelope() -> None:
    _assert_probe_blocks("b_faster_than_a_growth_probe")


def test_meta_regress_stops_at_principal() -> None:
    _assert_probe_blocks("meta_regress_past_principal_probe")


def test_reuse_rate_up_and_override_rate_down_trend_passes_floor() -> None:
    thermometer = _runtime_attr("GrowthThermometerRecord").model_validate(
        _thermometer_payload()
    )

    assert thermometer.floor_id == "s12_growth_thermometers"
    assert thermometer.floor_passed is True
    assert thermometer.override_rate_trend in {"improving", "flat"}
    assert thermometer.reuse_rate_trend in {"improving", "flat"}
    assert thermometer.required_question_count == 4
    assert set(thermometer.uninstrumented_override_dimensions) == {
        "regime",
        "decomposition",
    }


def test_held_out_status_is_pending_s14_not_executed() -> None:
    thermometer_model = _runtime_attr("GrowthThermometerRecord")
    thermometer = thermometer_model.model_validate(_thermometer_payload())

    assert thermometer.held_out_status == "pending_s14"
    assert thermometer.held_out_battery_ref is None

    with pytest.raises(ValidationError, match="pending_s14"):
        thermometer_model.model_validate(
            _thermometer_payload(
                held_out_status="executed",
                held_out_battery_ref="battery://s14/universality",
            )
        )


def test_s12_integrity_report_requires_exact_false_clear_keys() -> None:
    report_model = _runtime_attr("ResourceEconomicsIntegrityReport")
    false_clear_counts = _false_clear_counts()
    report = report_model.model_validate(
        _integrity_payload(false_clear_counts=false_clear_counts)
    )

    assert set(report.false_clear_counts) == set(_runtime_attr("S12_FALSE_CLEAR_FIELDS"))
    assert all(value == 0 for value in report.false_clear_counts.values())

    missing_key_counts = dict(false_clear_counts)
    missing_key_counts.pop("growth_without_envelope_delta")
    with pytest.raises(ValidationError, match="false_clear_counts"):
        report_model.model_validate(_integrity_payload(false_clear_counts=missing_key_counts))

    extra_key_counts = {**false_clear_counts, "unexpected_clear": 0}
    with pytest.raises(ValidationError, match="false_clear_counts"):
        report_model.model_validate(_integrity_payload(false_clear_counts=extra_key_counts))
