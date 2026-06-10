from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
G3_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g3_analytics_search.v1"

EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_g3_adapter_admission_registry.json",
    "architecture/policy_design_case/layer3_g3_l2_skg_proof_candidate_bindings.json",
    "architecture/policy_design_case/layer3_g3_ir_analytics_search_ledgers.json",
    "architecture/policy_design_case/layer3_g3_ir_analytics_query_traces.json",
    "architecture/policy_design_case/layer3_g3_ir_catalog_coverage.json",
    "architecture/policy_design_case/layer3_g3_ir_artifact_store_index.json",
    "architecture/policy_design_case/layer3_g3_certificate_resolution_report.json",
    "architecture/policy_design_case/layer3_g3_search_recall_freshness.json",
    "architecture/policy_design_case/layer3_g3_method_requirement_bindings.json",
    "architecture/policy_design_case/layer3_g3_semantic_spine_bindings.json",
    "architecture/policy_design_case/layer3_g3_proof_carrying_analytics_records.json",
    "architecture/policy_design_case/layer3_g3_ir_analytics_claim_bridge.json",
    "architecture/policy_design_case/layer3_g3_s11_prerequisite_bindings.json",
    "architecture/policy_design_case/layer3_g3_s11_calibration_bindings.json",
    "architecture/policy_design_case/layer3_g3_s11_predictive_posture_bindings.json",
    "architecture/policy_design_case/layer3_g3_claim_registry_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_baseline_comparison_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g3_proof_carrying_audit_surface.json",
    "architecture/policy_design_case/layer3_g3_conformance_report.json",
    "architecture/policy_design_case/layer3_g3_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g3_readiness_manifest.json",
}

EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "rule_version",
    "g0_dependency_status",
    "g1_dependency_status",
    "g2_dependency_status",
    "g3_l2_skg_dependency_status",
    "g3_l2_skg_proof_candidate_binding_count",
    "g3_ir_catalog_coverage_status",
    "g3_ir_artifact_store_index_status",
    "g3_search_ledger_count",
    "g3_query_trace_count",
    "g3_certificate_resolution_status",
    "g3_resolved_certificate_count",
    "g3_search_recall_freshness_status",
    "g3_search_recall_seed_count",
    "g3_search_recall_recalled_seed_count",
    "g3_method_requirement_binding_count",
    "g3_proof_carrying_record_count",
    "g3_ir_analytics_bridge_status",
    "g3_s11_prerequisite_binding_status",
    "g3_s11_predictive_posture_binding_count",
    "g3_claim_registry_consumer_gate_status",
    "g3_baseline_comparison_consumer_gate_status",
    "g3_w12d_consumer_gate_status",
    "g3_public_export_projection_status",
    "g3_search_engineering_quality_status",
    "g3_conformance_status",
    "g3_adapter_contract_registry_status",
    "g3_adapter_contract_path_count",
    "g3_health_metric_ids",
}

REQUIRED_WRITE_PATHS = {
    "architecture/policy_design_case/layer3_g3_certificate_resolution_report.json",
    "architecture/policy_design_case/layer3_g3_search_recall_freshness.json",
    "architecture/policy_design_case/layer3_g3_proof_carrying_analytics_records.json",
    "architecture/policy_design_case/layer3_g3_ir_analytics_claim_bridge.json",
    "architecture/policy_design_case/layer3_g3_s11_predictive_posture_bindings.json",
    "architecture/policy_design_case/layer3_g3_claim_registry_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_baseline_comparison_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g3_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g3_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g3_readiness_manifest.json",
}

REQUIRED_ISSUE_CODES = {
    "layer3_g3_l2_skg_proof_candidate_binding_missing",
    "layer3_g3_certificate_resolution_missing",
    "layer3_g3_search_hit_laundered_as_certificate",
    "layer3_g3_fixture_certificate_laundered",
    "layer3_g3_unresolved_certificate_binding",
    "layer3_g3_negative_certificate_ignored",
    "layer3_g3_proof_composability_bypass",
    "layer3_g3_method_requirement_bypass",
    "layer3_g3_proof_carrying_record_missing",
    "layer3_g3_ir_analytics_bridge_missing",
    "layer3_g3_s11_posture_without_s6_s10",
    "layer3_g3_claim_registry_consumer_gate_missing",
    "layer3_g3_baseline_comparison_consumer_gate_missing",
    "layer3_g3_w12d_consumer_gate_missing",
    "layer3_g3_public_raw_proof_leak",
    "layer3_g3_adapter_registry_summary_only",
    "layer3_g3_search_recall_seed_miss_blocks_domain_ceiling",
    "layer3_g3_search_ceiling_repair_required",
}


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g3_readiness")


def test_layer3_g3_readiness_passes_only_for_persisted_runtime_bundle() -> None:
    validation = _validator().validate_layer3_g3_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["summary"]["schema_version"] == G3_SCHEMA_VERSION
    assert validation["summary"]["g0_dependency_status"] == "pass"
    assert validation["summary"]["g1_dependency_status"] == "pass"
    assert validation["summary"]["g2_dependency_status"] == "pass"
    assert validation["summary"]["g3_l2_skg_dependency_status"] == "pass"
    assert validation["summary"]["g3_l2_skg_proof_candidate_binding_count"] >= 1
    assert validation["summary"]["g3_ir_catalog_coverage_status"] == "pass"
    assert validation["summary"]["g3_ir_artifact_store_index_status"] == "pass"
    assert validation["summary"]["g3_certificate_resolution_status"] == "pass"
    assert validation["summary"]["g3_resolved_certificate_count"] >= 1
    assert validation["summary"]["g3_search_recall_freshness_status"] == "pass"
    assert validation["summary"]["g3_search_recall_seed_count"] >= 3
    assert (
        validation["summary"]["g3_search_recall_recalled_seed_count"]
        == validation["summary"]["g3_search_recall_seed_count"]
    )
    assert validation["summary"]["g3_method_requirement_binding_count"] >= 1
    assert validation["summary"]["g3_proof_carrying_record_count"] >= 1
    assert validation["summary"]["g3_ir_analytics_bridge_status"] == "pass"
    assert validation["summary"]["g3_s11_prerequisite_binding_status"] == "pass"
    assert validation["summary"]["g3_s11_predictive_posture_binding_count"] >= 1
    assert validation["summary"]["g3_claim_registry_consumer_gate_status"] == "pass"
    assert validation["summary"]["g3_baseline_comparison_consumer_gate_status"] == "pass"
    assert validation["summary"]["g3_w12d_consumer_gate_status"] == "pass"
    assert validation["summary"]["g3_public_export_projection_status"] == "pass"
    assert validation["summary"]["g3_conformance_status"] == "pass"
    assert validation["summary"]["g3_adapter_contract_registry_status"] == "pass"
    assert validation["summary"]["g3_manifest_runtime_drift_key_count"] == 0
    assert validation["issues"] == []


def test_layer3_g3_readiness_declares_complete_expected_artifact_set() -> None:
    validator = _validator()

    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert expected_paths >= EXPECTED_ARTIFACT_PATHS


def test_layer3_g3_readiness_requires_persisted_artifacts(monkeypatch: Any) -> None:
    validator = _validator()
    missing_path = Path(
        "architecture/policy_design_case/layer3_g3_missing_certificate_resolution.json"
    )
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", (missing_path,))

    validation = validator.validate_layer3_g3_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == [
        missing_path.as_posix()
    ]
    assert "layer3_g3_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g3_readiness_manifest_contains_selected_runtime_drift_keys() -> None:
    validation = _validator().validate_layer3_g3_readiness(REPO_ROOT)

    assert set(validation["summary"]) >= EXPECTED_MANIFEST_KEYS
    assert validation["summary"]["schema_version"] == G3_SCHEMA_VERSION
    assert validation["summary"]["g3_manifest_runtime_drift_key_count"] == 0


def test_layer3_g3_write_path_includes_resolution_bridge_consumer_toml_and_manifest_records(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [path.as_posix() for path in expected_paths],
    )

    validation = validator.validate_layer3_g3_readiness(REPO_ROOT, write=True)

    written_paths = set(validation["artifacts"]["written_artifact_paths"])

    assert validation["write"] is True
    assert written_paths >= REQUIRED_WRITE_PATHS
    assert written_paths <= {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}


def test_layer3_g3_readiness_fails_when_write_path_omits_resolution_or_consumer_records(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    omitted = Path("architecture/policy_design_case/layer3_g3_certificate_resolution_report.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g3_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_g3_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }
    assert omitted.as_posix() not in validation["artifacts"]["written_artifact_paths"]


def test_layer3_g3_readiness_reports_resolution_bridge_s11_consumer_and_registry_issue_codes() -> None:
    issue_codes = set(_validator().ALL_ISSUE_CODES)

    assert issue_codes >= REQUIRED_ISSUE_CODES
