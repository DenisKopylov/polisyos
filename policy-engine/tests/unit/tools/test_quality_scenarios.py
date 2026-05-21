from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_QUALITY_SCENARIO_ID,
    QualityScenarioContractError,
    available_quality_scenario_ids,
    load_quality_scenario_contract,
    validate_quality_scenario_contract,
)


def test_default_quality_scenarios_have_expected_evidence_contracts() -> None:
    scenario_ids = available_quality_scenario_ids()

    assert DEFAULT_QUALITY_SCENARIO_ID in scenario_ids
    assert len(scenario_ids) >= 4

    contract = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
    expected = contract["expected_evidence_contract"]
    assert contract["scenario_id"] == DEFAULT_QUALITY_SCENARIO_ID
    assert contract["request"]
    assert contract["domain_hint"]
    assert expected["normative_fact_classes"]
    assert expected["admissible_data_source_families"]
    assert expected["foundry_method_expectations"]
    assert expected["conflict_checks"]
    assert expected["unacceptable_recommendations"]
    scenario_contract = contract["scenario_evidence_contract"]
    assert scenario_contract["schema_version"] == "policyos.scenario_evidence_contract.v1"
    assert scenario_contract["contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert {
        item["expected_family"]
        for item in scenario_contract["requirements"]
        if item["domain"] == "data"
    } == {
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    }


def test_quality_scenario_loader_quarantines_hidden_and_rotating_packs_by_default() -> None:
    scenario_ids = available_quality_scenario_ids()

    assert "hidden_energy_tariff_targeting_holdout" not in scenario_ids
    assert "digital_training_grants_regional_equity" not in scenario_ids

    with pytest.raises(QualityScenarioContractError) as exc_info:
        load_quality_scenario_contract("hidden_energy_tariff_targeting_holdout")

    assert any(
        failure["code"] == "quality_scenario_quarantined"
        for failure in exc_info.value.failures
    )

    hidden_contract = load_quality_scenario_contract(
        "hidden_energy_tariff_targeting_holdout",
        include_quarantined=True,
    )

    assert hidden_contract["pack"] == "hidden"
    assert hidden_contract["hidden_answer"]


def test_quality_scenario_validation_failure_is_actionable() -> None:
    broken_contract = {
        "scenario_id": "broken_scenario",
        "request": "Design a policy.",
        "domain_hint": "Broken policy scenario",
        "context": {"country": "UA"},
        "expected_evidence_contract": {
            "normative_fact_classes": ["eligibility_rule"],
        },
    }

    with pytest.raises(QualityScenarioContractError) as exc_info:
        validate_quality_scenario_contract(broken_contract)

    failures = exc_info.value.failures
    missing_types = {failure["missing_evidence_type"] for failure in failures}
    assert "admissible_data_source_families" in missing_types
    assert "foundry_method_expectations" in missing_types
    assert "conflict_checks" in missing_types
    assert all(failure["layer"] == "quality_scenarios" for failure in failures)
    assert all(failure["phase"] == "contract_validation" for failure in failures)
    assert all(failure["next_action"] for failure in failures)


def test_quality_scenario_loader_can_read_custom_contract_file(tmp_path: Path) -> None:
    scenario_file = tmp_path / "quality_scenarios.json"
    scenario_file.write_text(
        json.dumps(
            {
                "schema_version": "policyos.golden_quality_scenarios.v1",
                "scenarios": [
                    {
                        "scenario_id": "custom_tax_relief",
                        "title": "Custom tax relief",
                        "request": "Assess targeted tax relief.",
                        "domain_hint": "Custom tax relief policy",
                        "context": {
                            "country": "UA",
                            "policy_domain": "tax_relief",
                            "query_outcome": "business_survival_rate",
                            "query_treatment": "temporary_tax_relief",
                        },
                        "expected_evidence_contract": {
                            "normative_fact_classes": ["tax_authority_rule"],
                            "admissible_data_source_families": ["tax_admin_panel"],
                            "foundry_method_expectations": ["budget_impact"],
                            "conflict_checks": ["budget_rule_mismatch"],
                            "unacceptable_recommendations": ["uncapped_tax_exemption"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    contract = load_quality_scenario_contract(
        "custom_tax_relief",
        scenarios_file=scenario_file,
    )

    assert contract["scenario_id"] == "custom_tax_relief"
    assert contract["context"]["query_treatment"] == "temporary_tax_relief"
    assert contract["scenario_evidence_contract"]["scenario_id"] == "custom_tax_relief"
    assert {
        item["domain"] for item in contract["scenario_evidence_contract"]["requirements"]
    } >= {"data", "legal", "method", "claim"}
