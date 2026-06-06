from __future__ import annotations

import copy
import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g0"


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g0_readiness")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _issue_codes(report: dict[str, Any]) -> set[str]:
    return {str(issue["code"]) for issue in report["issues"]}


def _validation() -> dict[str, Any]:
    return _validator().validate_layer3_g0_readiness(REPO_ROOT)


def test_layer3_g0_readiness_fails_until_inventory_triage_ports_and_ledgers_are_frozen() -> None:
    validation = _validation()

    assert validation["status"] == "pass", validation["issues"]
    summary = validation["summary"]
    assert summary["closure_artifact_count"] == 12
    assert summary["readiness_manifest_count"] == 1
    assert summary["health_metric_ledger_count"] == 4
    assert summary["admitted_adapter_count"] == 0
    assert summary["grounded_conversion_count"] == 0


def test_layer3_g0_inventory_covers_current_source_packages_and_data_assets() -> None:
    validation = _validation()
    summary = validation["summary"]

    assert validation["status"] == "pass", validation["issues"]
    assert summary["source_package_count"] == 25
    assert summary["required_data_asset_root_count"] == 6
    assert summary["data_asset_inventory_unclassified_discovered_count"] == 0
    assert summary["processing_transform_inventory_unclassified_discovered_count"] == 0
    assert summary["production_data_manifest_bundle_count"] == 5
    assert summary["ukraine_simulation_manifest_file_count"] == 40
    assert summary["academic_runtime_slim_split_file_count"] == 20
    assert summary["universal_corpus_fixture_count"] == 13
    assert summary["ukraine_ops_runner_script_count"] == 10


def test_layer3_g0_portless_capabilities_are_recorded_as_governed_open_questions() -> None:
    validator = _validator()
    malformed = _fixture("malformed_portless_capability_missing_open_question.json")[
        "payload"
    ]

    report = validator.validate_layer3_g0_bundle_payload(malformed, repo_root=REPO_ROOT)

    assert report["status"] == "fail"
    assert "layer3_g0_portless_capability_missing_open_question" in _issue_codes(report)


def test_layer3_g0_data_inventory_is_manifest_backed_and_does_not_treat_corpus_fixtures_as_authority() -> None:
    validator = _validator()
    malformed = _fixture("malformed_data_asset_missing_evidence.json")["payload"]

    report = validator.validate_layer3_g0_bundle_payload(malformed, repo_root=REPO_ROOT)

    assert report["status"] == "fail"
    assert "layer3_g0_data_asset_evidence_missing" in _issue_codes(report)
    assert "layer3_g0_manifest_backed_data_scan_bypassed" in _issue_codes(report)


def test_layer3_g0_import_firewall_blocks_pdc_source_imports_and_quarantined_adapters() -> None:
    validator = _validator()
    malformed = _fixture("malformed_adapter_admission_quarantined_source.json")[
        "payload"
    ]

    report = validator.validate_layer3_g0_bundle_payload(malformed, repo_root=REPO_ROOT)

    assert report["status"] == "fail"
    assert "layer3_g0_quarantined_source_admitted" in _issue_codes(report)
    assert "layer3_g0_pdc_non_waist_import" in _issue_codes(report)


def test_layer3_g0_manifest_metrics_match_runtime_builder_output() -> None:
    validator = _validator()
    payload = validator.load_layer3_g0_bundle_payload(REPO_ROOT)
    stale = copy.deepcopy(payload)
    stale["readiness_manifest"]["counts"]["port_count"] = 26
    stale["readiness_manifest"]["counts"]["runtime_quality_touchpoint_count"] = 21

    report = validator.validate_layer3_g0_bundle_payload(stale, repo_root=REPO_ROOT)

    assert report["status"] == "fail"
    assert "layer3_g0_manifest_runtime_drift" in _issue_codes(report)


def test_layer3_g0_import_firewall_artifact_is_persisted_and_blocks_all_non_allowlisted_pdc_imports() -> None:
    validation = _validation()
    summary = validation["summary"]
    firewall = validation["artifacts"]["import_firewall_lint"]

    assert validation["status"] == "pass", validation["issues"]
    assert summary["import_firewall_artifact_count"] == 1
    assert summary["pdc_non_waist_import_count"] == 0
    assert firewall["allowlist_roots"] == ["core"]
    assert "ir" in firewall["forbidden_roots"]
    assert "runtime" in firewall["forbidden_roots"]
    assert "scientist" in firewall["forbidden_roots"]


def test_layer3_g0_empty_port_and_adapter_cost_maps_have_ranked_constraints() -> None:
    validator = _validator()
    malformed = _fixture("malformed_empty_port_missing_constraint_rank.json")[
        "payload"
    ]

    report = validator.validate_layer3_g0_bundle_payload(malformed, repo_root=REPO_ROOT)

    assert report["status"] == "fail"
    assert "layer3_g0_empty_port_map_missing_constraint_rank" in _issue_codes(report)
    assert "layer3_g0_adapter_cost_map_missing_near_typed_score" in _issue_codes(report)


def test_layer3_g0_adr_tracks_constitution_open_questions_as_empirically_open() -> None:
    validator = _validator()
    malformed = _fixture("malformed_adr_missing_open_questions.json")["payload"]

    report = validator.validate_layer3_g0_bundle_payload(malformed, repo_root=REPO_ROOT)

    assert report["status"] == "fail"
    assert "layer3_g0_adr_open_questions_missing" in _issue_codes(report)


def test_layer3_g0_policy_and_registry_governance_followups_are_recorded() -> None:
    validation = _validation()
    summary = validation["summary"]

    assert validation["status"] == "pass", validation["issues"]
    assert summary["adr_id"] == "0175"
    assert summary["adr_status"] == "Accepted"
    assert summary["adr_human_acceptance_ref_present"] is True
    assert summary["adr_open_questions_mode"] == "tracked_empirically_open"
    assert summary["import_policy_constitution_conflict_recorded"] is True
    assert summary["policy_toml_pdc_allowlist_narrowing_followup_recorded"] is True
    assert summary["registry_crosswalk_clarification_recorded"] is True
