from __future__ import annotations

from polisyos.runtime.quality.scenario_evidence_contract import (
    SCENARIO_EVIDENCE_CONTRACT_SCHEMA_VERSION,
    evaluate_source_family_binding,
    normalize_scenario_evidence_contract,
)
from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_QUALITY_SCENARIO_ID,
    load_quality_scenario_contract,
)

def _requirements_by_domain(contract: object, domain: str) -> list[object]:
    return [item for item in contract.requirements if item.domain == domain]


def test_normalizes_public_golden_scenario_to_typed_runtime_obligations() -> None:
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)

    contract = normalize_scenario_evidence_contract(scenario)

    assert contract.schema_version == SCENARIO_EVIDENCE_CONTRACT_SCHEMA_VERSION
    assert contract.contract_id == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert contract.scenario_id == DEFAULT_QUALITY_SCENARIO_ID
    assert [item.expected_family for item in _requirements_by_domain(contract, "data")] == [
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    ]
    assert {
        item.expected_family for item in _requirements_by_domain(contract, "legal")
    } >= {"wartime_business_support_authority", "credit_eligibility_rule"}
    assert {
        item.expected_family for item in _requirements_by_domain(contract, "method")
    } >= {"causal_effect_estimation", "uncertainty_interval"}
    assert {
        item.expected_family for item in _requirements_by_domain(contract, "claim")
    } >= {"recommendation_without_budget_guardrail"}


def test_data_requirements_carry_source_admissibility_facets_and_owners() -> None:
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
    contract = normalize_scenario_evidence_contract(scenario)
    requirement = next(
        item
        for item in contract.requirements
        if item.domain == "data" and item.expected_family == "production_msme_panel"
    )

    assert requirement.jurisdiction == "UA"
    assert requirement.producer_owner == "team-fabric"
    assert requirement.reader_owner == "team-runtime-quality"
    assert requirement.rights_scope == "public_policy_research"
    assert {
        "source_rights",
        "dictionary_ref",
        "schema_ref",
        "field_refs",
        "unit_refs",
        "geography_refs",
        "time_coverage_refs",
        "quality_refs",
        "missingness_refs",
        "lineage_refs",
        "transformation_refs",
        "derived_feature_bindings",
    } <= set(requirement.required_facets)


def test_broad_source_family_does_not_satisfy_specific_source_requirement() -> None:
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
    contract = normalize_scenario_evidence_contract(scenario)
    requirement = next(
        item
        for item in contract.requirements
        if item.domain == "data" and item.expected_family == "production_msme_panel"
    )

    failed = evaluate_source_family_binding(requirement, "datasets")
    passed = evaluate_source_family_binding(requirement, "production_msme_panel")

    assert failed["status"] == "failed"
    assert failed["blocker_code"] == "source_family_mismatch"
    assert failed["missing_facets"] == list(requirement.required_facets)
    assert passed["status"] == "satisfied"
    assert passed["blocker_code"] is None


def test_scenario_evidence_contract_serializes_for_request_context() -> None:
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
    contract = normalize_scenario_evidence_contract(scenario).to_dict()

    assert contract["schema_version"] == SCENARIO_EVIDENCE_CONTRACT_SCHEMA_VERSION
    assert contract["contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert contract["requirements"][0]["requirement_id"].startswith(
        "scenario:ukraine_msme_wartime_credit_support:"
    )
    assert all(item["producer_owner"] for item in contract["requirements"])
    assert all(item["reader_owner"] for item in contract["requirements"])
