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
    assert contract.requirement_basis.state == "established"
    assert contract.requirement_basis.source == "explicit_scenario_family_declaration"
    assert contract.requirement_basis.basis_grade == "consumer_asserted"
    assert contract.producer_report_ref.startswith("event://data-requirement/")
    assert contract.input_content_hash.startswith("sha256:")
    assert "scenario:" + contract.scenario_id in contract.subject_refs
    assert contract.rule_version_refs
    assert contract.contract_id == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert contract.scenario_id == DEFAULT_QUALITY_SCENARIO_ID
    assert contract.admissible_data_source_families == (
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    )
    assert len(contract.data_requirement_specs) == 3
    assert all(
        item.source_requirement_refs
        == (
            "legacy-scenario-contract:ukraine_msme_wartime_credit_support:"
            "admissible_data_source_families",
        )
        for item in contract.data_requirement_specs
    )
    assert contract.requirement_basis.state == "established"
    assert contract.requirement_basis.basis_grade == "consumer_asserted"
    assert [item.expected_family for item in _requirements_by_domain(contract, "data")] == [
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    ]
    assert {item.expected_family for item in _requirements_by_domain(contract, "legal")} >= {
        "wartime_business_support_authority",
        "credit_eligibility_rule",
    }
    assert {item.expected_family for item in _requirements_by_domain(contract, "method")} >= {
        "causal_effect_estimation",
        "uncertainty_interval",
    }
    assert {item.expected_family for item in _requirements_by_domain(contract, "claim")} >= {
        "recommendation_without_budget_guardrail"
    }


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


def test_scenario_family_name_alone_does_not_grant_authority() -> None:
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
    assert passed["status"] == "compatibility_projection_only"
    assert passed["blocker_code"] == "scenario_family_authority_lookup_sunset"
    assert passed["authority_granted"] is False
    assert passed["replacement"] == "capability_index_v1"
    assert "source_family_authority_decision_path" in passed["may_not_use_for"]


def test_explicit_unmapped_source_family_remains_candidate_without_resolver() -> None:
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
    scenario["expected_evidence_contract"]["admissible_data_source_families"] = ["datasets"]

    contract = normalize_scenario_evidence_contract(scenario)

    assert contract.admissible_data_source_families == ("datasets",)
    assert len(contract.data_requirement_specs) == 1
    assert contract.data_requirement_specs[0].required_data_families == ("datasets",)
    assert contract.data_requirement_specs[0].source_requirement_refs == (
        "legacy-scenario-contract:ukraine_msme_wartime_credit_support:"
        "admissible_data_source_families",
    )
    assert contract.requirement_basis.state == "established"
    assert contract.requirement_basis.basis_grade == "consumer_asserted"
    data_requirement = _requirements_by_domain(contract, "data")[0]
    assert data_requirement.expected_family == "datasets"
    projected = evaluate_source_family_binding(data_requirement, "datasets")
    assert projected["status"] == "compatibility_projection_only"
    assert projected["authority_granted"] is False


def test_scenario_evidence_contract_serializes_for_request_context() -> None:
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
    contract = normalize_scenario_evidence_contract(scenario).to_dict()

    assert contract["schema_version"] == SCENARIO_EVIDENCE_CONTRACT_SCHEMA_VERSION
    assert contract["requirement_basis"]["basis_grade"] == "consumer_asserted"
    assert contract["producer_report_ref"].startswith("event://data-requirement/")
    assert contract["input_content_hash"].startswith("sha256:")
    assert contract["contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert contract["requirements"][0]["requirement_id"].startswith(
        "scenario:ukraine_msme_wartime_credit_support:"
    )
    assert contract["admissible_data_source_families"] == [
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    ]
    assert len(contract["data_requirement_specs"]) == 3
    assert contract["requirement_basis"]["basis_grade"] == "consumer_asserted"
    assert all(item["producer_owner"] for item in contract["requirements"])
    assert all(item["reader_owner"] for item in contract["requirements"])


def test_unknown_data_basis_is_carried_as_typed_non_authority_limitation() -> None:
    contract = normalize_scenario_evidence_contract(
        {
            "scenario_id": "no-declared-data-basis",
            "text": "A neutral public policy statement.",
            "domain": "healthcare",
            "expected_evidence_contract": {"admissible_data_source_families": []},
        }
    )
    payload = contract.to_dict()

    assert contract.requirement_basis.state == "not_established"
    assert contract.requirement_basis.basis_grade == "not_established"
    assert "empty_compilation_not_proof_of_no_data" in contract.requirement_basis.reason_codes
    assert payload["requirement_basis"]["source"] == "explicit_scenario_family_declaration"
    assert payload["subject_refs"]
    assert payload["rule_version_refs"]
    assert payload["producer_report_ref"] in payload["requirement_basis"]["source_refs"]
    assert payload["input_content_hash"].startswith("sha256:")
