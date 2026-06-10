from __future__ import annotations

import json
import tomllib
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g4"
G4_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g4_promotion_gate.v1"
G4_RULE_VERSION = "policyos.layer3.g4.shadow_to_governed_promotion.v1"

EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_g4_a_completeness_ledger.json",
    "architecture/policy_design_case/layer3_g4_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g4_closeout_consumer_gate.json",
    "architecture/policy_design_case/layer3_g4_conformance_report.json",
    "architecture/policy_design_case/layer3_g4_dependency_readiness_snapshot.json",
    "architecture/policy_design_case/layer3_g4_g5_promotion_handoff.json",
    "architecture/policy_design_case/layer3_g4_governance_throughput_delta.json",
    "architecture/policy_design_case/layer3_g4_grounded_contract_set.json",
    "architecture/policy_design_case/layer3_g4_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g4_human_decision_integrity_gate.json",
    "architecture/policy_design_case/layer3_g4_pdc_compiler_consumer_gate.json",
    "architecture/policy_design_case/layer3_g4_promotion_audit_surface.json",
    "architecture/policy_design_case/layer3_g4_promotion_input_set.json",
    "architecture/policy_design_case/layer3_g4_promotion_records.json",
    "architecture/policy_design_case/layer3_g4_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g4_readiness_manifest.json",
    "architecture/policy_design_case/layer3_g4_registry_ratchet_delta.json",
    "architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json",
}

EXPECTED_MANIFEST_DRIFT_KEYS = {
    "schema_version",
    "rule_version",
    "g0_dependency_status",
    "g1_dependency_status",
    "g2_context_status",
    "g3_context_status",
    "gl_context_status",
    "g4_dependency_readiness_status",
    "g4_source_design_record_resolution_status",
    "g4_source_design_record_payload_status",
    "g4_source_design_record_digest_status",
    "g4_w12d_payload_source_status",
    "g4_dependency_artifact_shape_status",
    "g4_runtime_promotion_lane_collision_status",
    "g4_generated_artifact_promotion_target_collision_status",
    "g4_promotion_input_count",
    "g4_grounded_contract_set_status",
    "g4_grounded_contract_ref_count",
    "g4_a_completeness_status",
    "g4_a_completeness_requirement_count",
    "g4_a_completeness_missing_requirement_count",
    "g4_human_decision_integrity_status",
    "g4_s7_human_decision_payload_status",
    "g4_high_stakes_human_decision_bypass_status",
    "g4_s7_manifest_only_blocker_count",
    "g4_weakest_boundary_status",
    "g4_promotion_record_count",
    "g4_governed_promoted_count",
    "g4_promotion_blocked_count",
    "g4_may_not_use_for_completeness_status",
    "g4_closeout_consumer_gate_status",
    "g4_pdc_compiler_consumer_gate_status",
    "g4_g5_promotion_handoff_status",
    "g4_public_export_projection_status",
    "g4_public_projection_mode",
    "g4_public_export_hook_status",
    "g4_promotion_surface_status",
    "g4_governance_throughput_status",
    "g4_conformance_status",
    "g4_adapter_contract_registry_status",
    "g4_registry_ratchet_delta_status",
    "g4_promotion_gate_admission_maturity",
    "g4_promotion_gate_admission_conformance_ref_count",
    "g4_generated_artifacts_registration_status",
    "g4_inventory_surface_status",
    "g4_reference_docs_status",
    "g4_health_metric_ids",
}

TASK0_REQUIRED_ISSUE_CODES = {
    "layer3_g4_a_completeness_failed",
    "layer3_g4_data_promotion_lane_confused",
    "layer3_g4_generated_artifact_promotion_target_confused",
    "layer3_g4_gl_compatibility_gate_overclaimed",
    "layer3_g4_gl_reference_resolution_blocks_promotion",
    "layer3_g4_gl_reissue_required_blocks_promotion",
    "layer3_g4_grounded_contract_ref_missing",
    "layer3_g4_high_stakes_human_decision_not_required_bypass",
    "layer3_g4_human_decision_overrides_a_incompleteness",
    "layer3_g4_human_decision_record_missing",
    "layer3_g4_human_decision_required",
    "layer3_g4_missing_g1_grounded_source_contract",
    "layer3_g4_persisted_artifact_missing",
    "layer3_g4_policy_projection_authority_leak",
    "layer3_g4_public_export_hook_overclaimed",
    "layer3_g4_public_raw_payload_leak",
    "layer3_g4_readiness_summary_only_promotion",
    "layer3_g4_s2_ledger_ref_only_human_decision",
    "layer3_g4_s7_manifest_only_human_decision",
    "layer3_g4_shadow_self_promotion",
    "layer3_g4_source_design_record_digest_missing",
    "layer3_g4_source_design_record_payload_ref_only",
    "layer3_g4_source_design_record_unresolved",
    "layer3_g4_w12d_manifest_only_not_payload",
}

EXPECTED_HARD_REQUIREMENT_IDS = {
    "g0_readiness_manifest",
    "g0_discovery_search_discipline",
    "g0_engineering_quality_check",
    "g1_readiness_manifest",
    "g1_grounded_source_contract_rows",
    "g1_adapter_admission_registry",
    "g1_conformance_report",
    "source_design_record_replay_ref_and_digest",
}

EXPECTED_CONTEXT_ONLY_IDS = {
    "g2_forecast_contract_families",
    "g3_proof_carrying_contract_families",
    "gl_legal_mandate_contract_families",
    "s7_human_decision_record",
    "w12d_full_report_payload",
}

TASK7_CONFORMANCE_NEGATIVE_IDS = {
    "shadow_design_record_self_promotes",
    "promotion_without_g1_grounded_source_contract",
    "source_design_record_resolution_unresolved",
    "source_design_record_digest_missing",
    "dependency_artifact_shape_mismatch",
    "effect_claim_without_g2_forecast_support",
    "proof_claim_without_g3_proof_record",
    "legal_claim_without_gl_legal_authority",
    "missing_a_firewall_ref_promoted",
    "gl_reissue_required_promoted",
    "gl_g4_compatibility_gate_overclaimed_as_legal_authority",
    "readiness_summary_only_promoted",
    "search_ledger_only_promoted",
    "s7_manifest_only_promoted",
    "s2_ledger_ref_only_human_decision",
    "w12d_manifest_only_source_payload",
    "source_design_record_ref_only_promoted",
    "data_promotion_lane_reused_for_g4",
    "generated_artifact_promotion_target_reused_for_g4",
    "upstream_builder_rerun_in_request_path",
    "upstream_may_not_use_for_ignored",
    "weakest_boundary_ignored",
    "human_decision_missing_for_high_stakes",
    "high_stakes_human_decision_not_required_bypass",
    "human_decision_scope_mismatch",
    "human_decision_overrides_a_incompleteness",
    "promotion_record_claims_closeout",
    "promotion_record_rewrites_closeout_reader",
    "promotion_record_claims_pdc_compile_authority",
    "promotion_record_rewrites_pdc_compiler",
    "promotion_record_claims_production",
    "promotion_record_claims_publication",
    "promotion_record_claims_approval",
    "promotion_record_claims_scorecard",
    "promotion_record_claims_useful_design_credit",
    "promotion_record_incomplete_may_not_use_for",
    "public_projection_raw_payload_leak",
    "public_export_hook_overclaimed",
    "policy_design_case_projection_authority_leak",
    "manifest_runtime_drift",
    "promotion_state_vocab_drops_shadow",
    "promotion_gate_admission_without_conformance",
}


def _validator() -> Any:
    try:
        return import_module("tools.quality.validation.check_policy_design_case_layer3_g4_readiness")
    except ModuleNotFoundError as exc:
        if exc.name == "tools.quality.validation.check_policy_design_case_layer3_g4_readiness":
            pytest.fail(
                "G4 readiness CLI module is missing; add "
                "tools/quality/validation/check_policy_design_case_layer3_g4_readiness.py.",
                pytrace=False,
            )
        raise


def _dependency_audit() -> dict[str, Any]:
    return json.loads(
        (FIXTURE_DIR / "dependency_audit_expected.json").read_text(encoding="utf-8")
    )


def test_layer3_g4_dependency_audit_records_hard_and_context_dependencies() -> None:
    audit = _dependency_audit()
    hard_ids = {entry["id"] for entry in audit["hard_requirements_for_first_passing_promotion"]}
    context_ids = {entry["id"] for entry in audit["context_only_or_conditional_dependencies"]}
    collision_ids = {entry["id"] for entry in audit["non_input_naming_collisions"]}

    assert audit["schema_version"] == "policyos.tests.layer3.g4.dependency_audit.v1"
    assert set(audit["pattern_ids"]) >= {"P01", "P02", "P05", "P10", "P26"}
    assert hard_ids >= EXPECTED_HARD_REQUIREMENT_IDS
    assert context_ids >= EXPECTED_CONTEXT_ONLY_IDS
    assert hard_ids.isdisjoint(context_ids)
    assert collision_ids >= {"runtime_http_promotion_lane", "generated_artifact_promotion_target"}


def test_layer3_g4_readiness_module_declares_red_baseline_contract() -> None:
    validator = _validator()
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert validator.G4_SCHEMA_VERSION == G4_SCHEMA_VERSION
    assert validator.G4_RULE_VERSION == G4_RULE_VERSION
    assert expected_paths >= EXPECTED_ARTIFACT_PATHS
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert set(validator.ALL_ISSUE_CODES) >= TASK0_REQUIRED_ISSUE_CODES


def test_layer3_g4_readiness_fails_for_missing_persisted_artifacts(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    missing_path = Path("architecture/policy_design_case/layer3_g4_missing_probe.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", (missing_path,))

    validation = validator.validate_layer3_g4_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert set(validation["summary"]) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == [
        missing_path.as_posix()
    ]
    assert "layer3_g4_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g4_readiness_passes_for_persisted_runtime_bundle() -> None:
    validation = _validator().validate_layer3_g4_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    assert set(validation["summary"]) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["summary"]["g4_governed_promoted_count"] >= 1
    assert validation["summary"]["g4_promotion_blocked_count"] >= 1


def test_layer3_g4_readiness_persisted_conformance_covers_task7_negatives() -> None:
    validation = _validator().validate_layer3_g4_readiness(REPO_ROOT)
    conformance = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g4_conformance_report.json"
        ).read_text(encoding="utf-8")
    )
    results = {item["negative_id"]: item for item in conformance["negative_results"]}

    assert validation["status"] == "pass"
    assert set(conformance["negative_ids"]) >= TASK7_CONFORMANCE_NEGATIVE_IDS
    assert set(results) >= TASK7_CONFORMANCE_NEGATIVE_IDS
    assert all(
        results[negative_id]["status"] == "pass"
        for negative_id in TASK7_CONFORMANCE_NEGATIVE_IDS
    )
    assert conformance["performance_contract"]["status"] == "pass"
    assert validation["summary"]["g4_conformance_negative_count"] >= len(
        TASK7_CONFORMANCE_NEGATIVE_IDS
    )
    assert validation["summary"]["g4_conformance_negative_pass_count"] >= len(
        TASK7_CONFORMANCE_NEGATIVE_IDS
    )
    assert validation["summary"]["g4_performance_contract_status"] == "pass"


def test_layer3_g4_persisted_adapter_registry_and_throughput_are_semantic() -> None:
    validation = _validator().validate_layer3_g4_readiness(REPO_ROOT)
    adapter_registry = tomllib.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g4_adapter_contract_registry.toml"
        ).read_text(encoding="utf-8")
    )
    throughput = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g4_governance_throughput_delta.json"
        ).read_text(encoding="utf-8")
    )

    bridge_records = adapter_registry["bridge_records"]
    assert validation["status"] == "pass"
    assert len(bridge_records) == adapter_registry["adapter_path_count"]
    assert all(record["producer_artifact_family"] for record in bridge_records)
    assert all(record["consumer"] for record in bridge_records)
    assert all(record["verification_refs"] for record in bridge_records)
    assert all(record["conformance_negative_refs"] for record in bridge_records)
    assert "block_reason_counts" in throughput
    assert "stall_reason_counts" in throughput
    assert "hard_a_incompleteness" in throughput["block_reason_counts"]
    assert "search_health_stall" in throughput["stall_reason_counts"]


def test_layer3_g4_write_path_must_include_every_expected_artifact(monkeypatch: Any) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [path.as_posix() for path in expected_paths],
    )

    validation = validator.validate_layer3_g4_readiness(REPO_ROOT, write=True)
    written_paths = set(validation["artifacts"]["written_artifact_paths"])

    assert validation["write"] is True
    assert written_paths >= EXPECTED_ARTIFACT_PATHS
    assert written_paths <= {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}


def test_layer3_g4_write_path_omission_keeps_readiness_red(monkeypatch: Any) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    omitted = Path("architecture/policy_design_case/layer3_g4_promotion_records.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g4_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert omitted.as_posix() not in validation["artifacts"]["written_artifact_paths"]
    assert "layer3_g4_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }
