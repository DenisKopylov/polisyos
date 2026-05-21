from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests/fixtures/production_quality/cloud_debug_20260520/evidence_spine_connectivity_fixture.json"
)


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_cloud_connectivity_fixture_preserves_spine_breaks() -> None:
    fixture = _load_fixture()

    assert fixture["schema_version"] == "policyos.evidence_spine_connectivity_fixture.v1"
    assert fixture["source_run"]["lane_id"] == (
        "profile-research__provider-live_gonka_proxy__data-canonical_production__"
        "scenario-public_golden__ui-api_only"
    )

    request = fixture["request"]
    assert request["scenario_evidence_contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert request["requirement_count"] == 18

    fabric = fixture["fabric"]
    assert fabric["top_level_scenario_evidence_contract_id"] is None
    assert fabric["nested_scenario_evidence_contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )

    lex = fixture["lex"]
    assert lex["top_level_legal_requirement_count"] == 0
    assert lex["query_normalization_legal_requirement_count"] == 4

    production_data = fixture["production_data"]
    assert production_data["curated_contract_ids"] == [
        "us.macro.gdp_nominal",
        "us.macro.unemployment_rate",
        "agent.income.salary",
    ]
    assert production_data["missing_scenario_families"] == [
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    ]

    semantic = fixture["semantic_binding"]
    assert semantic["status"] == "pass"
    assert semantic["runtime_report_status"] is None

    policy_design_case = fixture["policy_design_case"]
    assert policy_design_case["status"] == "pass"
    assert policy_design_case["records_present"] is False
    assert policy_design_case["record_families_present"] is False

    continuous_governance = fixture["continuous_governance"]
    assert (
        continuous_governance["borrowed_authority_envelope"]["artifact_kind"]
        == "runtime.production_data_quality_report"
    )


def test_cloud_connectivity_fixture_preserves_erasure_guards() -> None:
    fixture = _load_fixture()

    guards = fixture["erasure_guards"]
    assert guards["dropped_contract_id"] == {
        "producer": "fabric_retrieval_trace",
        "consumed_contract_id": "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1",
        "emitted_contract_id": None,
        "blocker_code": "evidence_spine_contract_dropped",
    }
    assert guards["global_to_claim_anchor_gap"]["global_selected_norm_ref_count"] == 33
    assert guards["global_to_claim_anchor_gap"]["per_claim_selected_norm_ref_count"] == 0
    assert guards["producer_pass_reader_fail_gap"] == {
        "semantic_binding_status": "pass",
        "semantic_binding_runtime_report_status": None,
        "semantic_scorecard_failure_count": 108,
        "policy_design_case_status": "pass",
        "policy_design_case_records_present": False,
        "policy_design_case_record_families_present": False,
    }
    assert guards["borrowed_envelope"] == {
        "report_family": "continuous_governance",
        "borrowed_artifact_kind": "runtime.production_data_quality_report",
        "borrowed_schema_name": "polisyos.runtime.ProductionDataQualityReport",
        "borrowed_phase": "production_data_quality",
    }


def test_cloud_connectivity_fixture_describes_all_eight_patterns() -> None:
    fixture = _load_fixture()

    pattern_ids = [pattern["pattern_id"] for pattern in fixture["connectivity_patterns"]]
    assert pattern_ids == [
        "context_exists_but_becomes_local_metadata",
        "data_availability_confused_with_scenario_admissibility",
        "global_evidence_pools_treated_as_claim_anchors",
        "invalid_candidates_remain_selected",
        "producers_pass_when_readers_know_closure_failed",
        "authority_envelopes_borrowed_across_report_kinds",
        "deployed_combination_compatibility_not_verified",
        "secondary_signals_confounded_by_upstream_connectivity",
    ]
    for pattern in fixture["connectivity_patterns"]:
        assert pattern["status"] == "preserved_regression"
        assert pattern["evidence"], pattern["pattern_id"]
        assert pattern["plan_waves"], pattern["pattern_id"]
