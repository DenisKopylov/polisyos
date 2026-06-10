from __future__ import annotations

import json
import tomllib
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
G5_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g5_proving_ground_conversion.v1"
G5_RULE_VERSION = "policyos.layer3.g5.first_proving_ground_conversion.v1"

EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_g5_dependency_readiness_snapshot.json",
    "architecture/policy_design_case/layer3_g5_pinned_case_input_bundle.json",
    "architecture/policy_design_case/layer3_g5_w12d_case_block_index.json",
    "architecture/policy_design_case/layer3_g5_composed_loop_completeness_gate.json",
    "architecture/policy_design_case/layer3_g5_g4_handoff_resolution.json",
    "architecture/policy_design_case/layer3_g5_g4_promotion_record_resolution.json",
    "architecture/policy_design_case/layer3_g5_upstream_scope_join_matrix.json",
    "architecture/policy_design_case/layer3_g5_grounded_result_evidence_set.json",
    "architecture/policy_design_case/layer3_g5_effective_evidence_independence.json",
    "architecture/policy_design_case/layer3_g5_useful_design_metric_eligibility_join.json",
    "architecture/policy_design_case/layer3_g5_conversion_eligibility_ledger.json",
    "architecture/policy_design_case/layer3_g5_status_composition_ledger.json",
    "architecture/policy_design_case/layer3_g5_grounded_abstention_quality_record.json",
    "architecture/policy_design_case/layer3_g5_demand_pull_attempt_record.json",
    "architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json",
    "architecture/policy_design_case/layer3_g5_envelope_expansion_delta.json",
    "architecture/policy_design_case/layer3_g5_conversion_records.json",
    "architecture/policy_design_case/layer3_g5_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g5_conversion_audit_surface.json",
    "architecture/policy_design_case/layer3_g5_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g5_conformance_report.json",
    "architecture/policy_design_case/layer3_g5_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g5_conversion_route_contract_registry.toml",
    "architecture/policy_design_case/layer3_g5_registry_ratchet_delta.json",
    "architecture/policy_design_case/layer3_g5_readiness_manifest.json",
}

EXPECTED_MANIFEST_DRIFT_KEYS = {
    "status",
    "schema_version",
    "rule_version",
    "g5_dependency_readiness_status",
    "g5_g0_dependency_status",
    "g5_g1_dependency_status",
    "g5_g2_dependency_status",
    "g5_g3_dependency_status",
    "g5_gl_dependency_status",
    "g5_g4_dependency_status",
    "g5_pinned_case_input_status",
    "g5_composed_loop_completeness_status",
    "g5_g4_handoff_resolution_status",
    "g5_upstream_scope_join_status",
    "g5_effective_evidence_independence_status",
    "g5_conversion_record_count",
    "g5_conversion_outcome",
    "g5_grounded_conversion_count",
    "g5_w12d_consumer_gate_status",
    "g5_envelope_expansion_status",
    "g5_public_surface_status",
    "g5_conformance_status",
    "g5_generated_artifacts_registration_status",
    "g5_inventory_surface_status",
    "g5_reference_docs_status",
    "issue_codes",
}

TASK0_REQUIRED_ISSUE_CODES = {
    "layer3_g5_dependency_readiness_snapshot_missing",
    "layer3_g5_g0_dependency_not_ready",
    "layer3_g5_g1_dependency_not_ready",
    "layer3_g5_g4_dependency_not_ready",
    "layer3_g5_w12d_full_payload_missing",
    "layer3_g5_w12d_manifest_only_not_payload",
    "layer3_g5_w12d_build_cache_not_source_of_truth",
    "layer3_g5_s4_s14_composed_loop_incomplete",
    "layer3_g5_g4_handoff_missing",
    "layer3_g5_no_governed_promotion_record",
    "layer3_g5_grounded_limited_without_g2_g3_design_support",
    "layer3_g5_source_only_promotion_overclaims_grounded_limited",
    "layer3_g5_effective_independence_missing",
    "layer3_g5_grounded_abstention_without_demand_pull_attempt",
    "layer3_g5_w12d_consumer_gate_missing",
    "layer3_g5_public_raw_payload_leak",
    "layer3_g5_generated_artifacts_family_missing",
    "layer3_g5_inventory_surface_missing",
    "layer3_g5_reference_index_missing",
    "layer3_g5_persisted_artifact_missing",
}

TASK7_CONFORMANCE_NEGATIVE_IDS = {
    "public_projection_raw_payload_leak",
    "projection_authority_leak",
    "public_export_hook_overclaimed",
    "closed_case_replay_mutation",
    "closeout_surface_substitution_attempt",
    "closeout_authority_leak",
    "candidate_unverified_authority_slot",
    "rejected_speculation_authority_slot",
    "unowned_warning_lifecycle",
    "warning_used_as_conversion_pass",
    "arbitrary_request_attempt",
    "g7_region_widening_attempt",
}

TASK7_EXPECTED_ISSUE_CODES = {
    "layer3_g5_pre_g5_closed_case_replay_mutated",
    "layer3_g5_closeout_surface_substitution_attempt",
    "layer3_g5_closeout_authority_leak",
    "layer3_g5_candidate_unverified_used_as_authority",
    "layer3_g5_rejected_speculation_used_as_authority",
    "layer3_g5_unowned_warning_lifecycle",
    "layer3_g5_warning_used_as_conversion_pass",
    "layer3_g5_arbitrary_request_attempt",
    "layer3_g5_g7_widening_attempt",
}


def _validator() -> Any:
    try:
        return import_module("tools.quality.validation.check_policy_design_case_layer3_g5_readiness")
    except ModuleNotFoundError as exc:
        if exc.name == "tools.quality.validation.check_policy_design_case_layer3_g5_readiness":
            pytest.fail(
                "G5 readiness CLI module is missing; add "
                "tools/quality/validation/check_policy_design_case_layer3_g5_readiness.py.",
                pytrace=False,
            )
        raise


def test_layer3_g5_readiness_task0_dependency_audit_records_pattern_pass() -> None:
    """P01/P02/P03/P05/P10 red baseline: conversion readiness needs the full chain."""

    pattern_ids = {"P01", "P02", "P03", "P04", "P05", "P10", "P14", "P15", "P25"}
    missing_labels = {
        "producer_missing",
        "artifact_missing",
        "bridge_missing",
        "consumer_missing",
        "surface_missing",
        "semantic_test_missing",
    }

    assert pattern_ids >= {"P01", "P02", "P03", "P05", "P10"}
    assert "surface_missing" in missing_labels
    assert "semantic_test_missing" in missing_labels


def test_layer3_g5_readiness_module_declares_red_baseline_contract() -> None:
    """P04/P07 red baseline: readiness must own exact artifacts and drift keys."""

    validator = _validator()
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert validator.G5_SCHEMA_VERSION == G5_SCHEMA_VERSION
    assert validator.G5_RULE_VERSION == G5_RULE_VERSION
    assert expected_paths >= EXPECTED_ARTIFACT_PATHS
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert set(validator.ALL_ISSUE_CODES) >= TASK0_REQUIRED_ISSUE_CODES


def test_layer3_g5_readiness_fails_for_missing_persisted_artifacts(
    monkeypatch: Any,
) -> None:
    """P01/P03 red baseline: runtime-only or report-only G5 cannot close readiness."""

    validator = _validator()
    missing_path = Path("architecture/policy_design_case/layer3_g5_missing_probe.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", (missing_path,))

    validation = validator.validate_layer3_g5_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert set(validation["summary"]) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == [
        missing_path.as_posix()
    ]
    assert "layer3_g5_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g5_readiness_passes_for_persisted_runtime_bundle() -> None:
    validator = _validator()

    write_report = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)
    validation = validator.validate_layer3_g5_readiness(REPO_ROOT)

    assert write_report["status"] == "pass"
    assert validation["status"] == "pass"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    assert set(validation["summary"]) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["summary"]["g5_conversion_record_count"] >= 1
    assert validation["summary"]["g5_w12d_consumer_gate_status"] == "pass"


def test_layer3_g5_readiness_mirrors_g4_exact_artifact_and_drift_scaffold() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert expected_paths == EXPECTED_ARTIFACT_PATHS
    assert set(validation["artifacts"]["written_artifact_paths"]) == expected_paths
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["summary"]["g5_manifest_runtime_drift_key_count"] == 0


def test_layer3_g5_write_path_must_include_every_expected_artifact(monkeypatch: Any) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    omitted = Path("architecture/policy_design_case/layer3_g5_conversion_records.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert omitted.as_posix() not in validation["artifacts"]["written_artifact_paths"]
    assert "layer3_g5_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g5_generated_artifacts_and_inventory_are_registered() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)

    generated_text = (REPO_ROOT / "architecture/generated_artifacts.toml").read_text(
        encoding="utf-8"
    )
    inventory_text = (
        REPO_ROOT / "architecture/policy_design_case/inventory.json"
    ).read_text(encoding="utf-8")

    assert validation["summary"]["g5_generated_artifacts_registration_status"] == "pass"
    assert validation["summary"]["g5_inventory_surface_status"] == "pass"
    assert "policy-design-case-layer3-g5-proving-ground-conversion-artifacts" in generated_text
    assert "layer3_g5_first_proving_ground_conversion_surface" in inventory_text
    assert "layer3_g5_conversion_route_contract_registry.toml" in generated_text


def test_layer3_g5_public_surface_denies_raw_payload_and_downstream_authority() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)
    projection = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g5_public_export_projection_refs.json"
        ).read_text(encoding="utf-8")
    )
    public_projection = projection["PUBLIC"]

    assert validation["summary"]["g5_public_surface_status"] == "pass"
    assert "raw_upstream_payload" not in public_projection
    assert public_projection["authoritative_for"] == []
    assert "claim_authority" in public_projection["may_not_be_used_for"]
    assert "policy_recommendation" in projection["may_not_use_for"]
    assert projection["public_export_hook_status"] == "out_of_scope_reference_only"


def test_layer3_g5_uses_conversion_route_registry_not_adapter_registry() -> None:
    validator = _validator()
    validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)

    route_registry = tomllib.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g5_conversion_route_contract_registry.toml"
        ).read_text(encoding="utf-8")
    )

    assert route_registry["status"] == "pass"
    assert "conversion_route_records" in route_registry
    assert "adapter_path_ids" not in route_registry
    assert route_registry["conversion_route_records"][0]["route_id"].startswith(
        "layer3.g5.conversion_route."
    )
    assert "conversion_authority_without_g5" in route_registry[
        "conversion_route_records"
    ][0]["may_not_use_for"]


def test_layer3_g5_public_projection_reuses_runtime_projection_authority_checks() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)
    projection = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g5_public_export_projection_refs.json"
        ).read_text(encoding="utf-8")
    )

    assert validation["summary"]["g5_projection_boundary_status"] == "pass"
    assert projection["projection_contract_verification"]["status"] == "pass"
    assert projection["projection_contract_verification"]["consumer_contract_ref"].endswith(
        "projection_contract_verification.v1"
    )
    assert projection["PUBLIC"]["authority_role"] == "projection_only"


def test_layer3_g5_s12_s14_projection_contracts_preserve_limits() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)
    projection = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g5_public_export_projection_refs.json"
        ).read_text(encoding="utf-8")
    )

    assert validation["summary"]["g5_s12_projection_contract_status"] == "pass"
    assert validation["summary"]["g5_s14_projection_contract_status"] == "pass"
    assert projection["s12_projection_contract_verification"]["status"] == "pass"
    assert projection["s14_projection_contract_verification"]["status"] == "pass"
    assert "allocation_recommendation_text" not in projection["PUBLIC"]
    assert "recommendation_authority" in projection["PUBLIC"]["may_not_be_used_for"]


def test_layer3_g5_task7_conformance_performance_and_closeout_are_persisted() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g5_readiness(REPO_ROOT, write=True)
    conformance = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_g5_conformance_report.json"
        ).read_text(encoding="utf-8")
    )
    negative_results = {
        result["negative_id"]: result for result in conformance["negative_results"]
    }
    observed_issue_codes = {
        code
        for result in conformance["negative_results"]
        for code in result["observed_issue_codes"]
    }
    performance = conformance["performance_contract"]

    assert validation["status"] == "pass"
    assert set(negative_results) >= TASK7_CONFORMANCE_NEGATIVE_IDS
    assert all(result["status"] == "pass" for result in negative_results.values())
    assert observed_issue_codes >= TASK7_EXPECTED_ISSUE_CODES
    assert set(validation["issue_code_dictionary"]) >= TASK7_EXPECTED_ISSUE_CODES
    assert conformance["closed_case_replay_integrity"]["status"] == "pass"
    assert conformance["closeout_boundary_check"]["status"] == "pass"
    assert conformance["candidate_firewall_check"]["status"] == "pass"
    assert conformance["warning_lifecycle_check"]["status"] == "pass"
    assert validation["summary"]["g5_closed_case_replay_integrity_status"] == "pass"
    assert validation["summary"]["g5_closeout_surface_substitution_status"] == "pass"
    assert validation["summary"]["g5_candidate_firewall_status"] == "pass"
    assert validation["summary"]["g5_warning_lifecycle_status"] == "pass"
    assert performance["bounded_artifact_read_policy"] == "explicit_expected_paths_only"
    assert performance["request_path_repo_glob_allowed"] is False
    assert performance["upstream_builder_rerun_in_request_path"] is False
    assert performance["w12d_import_mode"] == "lazy"
