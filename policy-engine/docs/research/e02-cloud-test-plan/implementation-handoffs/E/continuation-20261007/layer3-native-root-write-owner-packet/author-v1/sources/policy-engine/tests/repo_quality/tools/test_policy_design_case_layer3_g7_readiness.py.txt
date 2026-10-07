from __future__ import annotations

from pathlib import Path
from typing import Any

from polisyos.runtime.quality.proving_ground import region_widening as g7
from tools.quality.validation import check_policy_design_case_layer3_g7_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]
G7_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g7_region_widening.v1"
G7_RULE_VERSION = "policyos.layer3.g7.region_widening.v1"

EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_g7_dependency_readiness_snapshot.json",
    "architecture/policy_design_case/layer3_g7_region_candidate_set.json",
    "architecture/policy_design_case/layer3_g7_region_grounding_matrix.json",
    "architecture/policy_design_case/layer3_g7_region_case_conversion_inputs.json",
    "architecture/policy_design_case/layer3_g7_region_conversion_records.json",
    "architecture/policy_design_case/layer3_g7_region_conversion_status_matrix.json",
    "architecture/policy_design_case/layer3_g7_governed_promotion_join.json",
    "architecture/policy_design_case/layer3_g7_status_composition_ledger.json",
    "architecture/policy_design_case/layer3_g7_s12_growth_thermometer_projection.json",
    "architecture/policy_design_case/layer3_g7_mechanism_reuse_ledger.json",
    "architecture/policy_design_case/layer3_g7_marginal_grounding_cost_ledger.json",
    "architecture/policy_design_case/layer3_g7_region_envelope_expansion_delta.json",
    "architecture/policy_design_case/layer3_g7_region_semantic_loss_ledger.json",
    "architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json",
    "architecture/policy_design_case/layer3_g7_g5_g6_authority_boundary_report.json",
    "architecture/policy_design_case/layer3_g7_s14_grounded_breadth_feed.json",
    "architecture/policy_design_case/layer3_g7_s14_mechanism_generality_projection.json",
    "architecture/policy_design_case/layer3_g7_s14_battery_input_manifest.json",
    "architecture/policy_design_case/layer3_g7_s14_consumer_gate.json",
    "architecture/policy_design_case/layer3_g7_region_scorecard.json",
    "architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json",
    "architecture/policy_design_case/layer3_g7_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g7_orchestration_continuity.json",
    "architecture/policy_design_case/layer3_g7_replay_manifest.json",
    "architecture/policy_design_case/layer3_g7_conformance_report.json",
    "architecture/policy_design_case/layer3_g7_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g7_region_route_contract_registry.toml",
    "architecture/policy_design_case/layer3_g7_registry_ratchet_delta.json",
    "architecture/policy_design_case/layer3_g7_readiness_manifest.json",
}
EXPECTED_MANIFEST_DRIFT_KEYS = {
    "g7_engineering_readiness_status",
    "g7_region_value_closure_status",
    "g7_current_g5_conversion_outcome",
    "g7_current_g5_unchanged_blocker_status",
    "g7_g1_search_control_plane_status",
    "g7_g1_free_growth_status",
    "g7_g1_no_hardcode_lint_status",
    "g7_g4_promotion_gate_shape_status",
    "g7_g4_region_promotion_projection_status",
    "g7_g5_g6_authority_boundary_status",
    "g7_region_candidate_set_status",
    "g7_region_grounding_matrix_status",
    "g7_region_grounded_case_count",
    "g7_region_blocked_case_count",
    "g7_status_composition_status",
    "g7_governed_promotion_join_status",
    "g7_s12_growth_thermometer_status",
    "g7_s12_resource_projection_contract_status",
    "g7_s13_certified_delta_status",
    "g7_mechanism_reuse_status",
    "g7_mechanism_reuse_rate",
    "g7_marginal_cost_status",
    "g7_region_envelope_expansion_rate",
    "g7_region_semantic_loss_status",
    "g7_governance_throughput_status",
    "g7_s14_grounded_breadth_feed_status",
    "g7_s14_mechanism_generality_status",
    "g7_s14_battery_input_manifest_status",
    "g7_s14_consumer_gate_status",
    "g7_s14_runner_input_hook_status",
    "g7_s14_projection_contract_status",
    "g7_public_projection_contract_status",
    "g7_public_projection_official_use_status",
    "g7_replay_manifest_status",
    "g7_orchestration_continuity_status",
    "g7_generated_artifacts_registration_status",
    "g7_inventory_surface_status",
    "g7_reference_docs_status",
    "g7_route_contract_registry_status",
    "g7_registry_ratchet_status",
    "g7_conformance_status",
}
REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS = {
    "g5_unchanged_blocker_as_region_grounded",
    "g6_candidate_as_region_grounded",
    "fixture_breadth_as_grounded",
    "hardcoded_candidate_set_as_region_coverage",
    "search_hit_as_region_coverage",
    "grounded_case_without_governed_promotion",
    "g4_seed_promotion_as_region_governance",
    "g4_promotion_without_full_gate_shape",
    "g4_mapping_fallback_as_region_governance",
    "bespoke_patch_as_mechanism_reuse",
    "sublinear_cost_without_cost_ledger",
    "sublinear_cost_without_grounded_cases",
    "s12_growth_thermometer_missing",
    "s12_projection_bypasses_resource_economics_shape",
    "s12_growth_without_certified_delta",
    "s12_held_out_status_overclaimed",
    "s12_deny_list_omitted",
    "s13_certified_delta_missing",
    "pending_delta_as_region_expansion",
    "semantic_loss_hidden_by_region_score",
    "effective_independence_inflated",
    "g5_may_not_use_for_ignored",
    "g6_may_not_use_for_ignored",
    "s14_feed_missing",
    "s14_battery_input_manifest_missing",
    "s14_feed_uses_fixtures",
    "s14_manifest_as_runner_output",
    "universal_claim_without_s14_gate",
    "public_projection_authority_leak",
    "public_projection_raw_payload_leak",
    "public_projection_required_deny_list_missing",
    "public_projection_contract_missing_or_failed",
    "generated_artifacts_family_missing",
    "inventory_surface_missing",
    "reference_index_missing",
    "route_contract_registry_missing",
    "manifest_runtime_drift",
    "replay_manifest_missing",
    "orchestration_continuity_missing",
    "replay_helper_bypassed",
    "closed_case_replay_mutated",
}

TASK1_REQUIRED_ISSUE_CODES = {
    "layer3_g7_g5_readiness_missing",
    "layer3_g7_g6_readiness_missing",
    "layer3_g7_current_g5_unchanged_blocker",
    "layer3_g7_no_real_grounded_region_breadth",
    "layer3_g7_region_candidate_set_missing",
    "layer3_g7_candidate_set_hardcoded_as_coverage",
    "layer3_g7_region_case_without_grounding_matrix",
    "layer3_g7_status_composition_missing",
    "layer3_g7_g5_unchanged_blocker_counted_as_grounded",
    "layer3_g7_g6_candidate_counted_as_grounded",
    "layer3_g7_fixture_breadth_counted_as_grounded",
    "layer3_g7_grounded_case_without_governed_promotion",
    "layer3_g7_g4_seed_promotion_projected_to_region",
    "layer3_g7_g4_promotion_gate_shape_missing",
    "layer3_g7_g4_mapping_fallback_counted_as_governed",
    "layer3_g7_bespoke_patch_counted_as_reuse",
    "layer3_g7_marginal_cost_without_cost_ledger",
    "layer3_g7_sublinear_claim_without_grounded_cases",
    "layer3_g7_s12_growth_thermometer_missing",
    "layer3_g7_s12_projection_bypasses_resource_economics_shape",
    "layer3_g7_s12_growth_without_certified_delta",
    "layer3_g7_s12_held_out_status_overclaimed",
    "layer3_g7_s12_deny_list_omitted",
    "layer3_g7_s13_certified_delta_missing",
    "layer3_g7_pending_delta_counted_as_expansion",
    "layer3_g7_search_hit_counted_as_coverage",
    "layer3_g7_search_recall_or_freshness_missing",
    "layer3_g7_governance_throughput_missing",
    "layer3_g7_accountable_principal_missing",
    "layer3_g7_effective_independence_inflated",
    "layer3_g7_semantic_loss_hidden_by_region_score",
    "layer3_g7_g5_may_not_use_for_ignored",
    "layer3_g7_g6_may_not_use_for_ignored",
    "layer3_g7_s14_feed_missing",
    "layer3_g7_s14_battery_input_manifest_missing",
    "layer3_g7_s14_feed_uses_fixtures",
    "layer3_g7_s14_consumer_gate_missing",
    "layer3_g7_s14_manifest_runner_output_conflated",
    "layer3_g7_universal_claim_without_s14_gate",
    "layer3_g7_public_projection_authority_leak",
    "layer3_g7_public_raw_payload_leak",
    "layer3_g7_projection_omits_required_deny_list",
    "layer3_g7_public_projection_contract_failed",
    "layer3_g7_generated_artifacts_family_missing",
    "layer3_g7_inventory_surface_missing",
    "layer3_g7_reference_index_missing",
    "layer3_g7_route_contract_registry_missing",
    "layer3_g7_manifest_runtime_drift",
    "layer3_g7_replay_manifest_missing",
    "layer3_g7_orchestration_continuity_missing",
    "layer3_g7_replay_helper_bypassed",
    "layer3_g7_closed_case_replay_mutated",
    "layer3_g7_persisted_artifact_missing",
}


def _validator() -> Any:
    return validator


def test_layer3_g7_readiness_module_declares_red_baseline_contract() -> None:
    validator = _validator()
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert validator.G7_SCHEMA_VERSION == g7.G7_SCHEMA_VERSION == G7_SCHEMA_VERSION
    assert validator.G7_RULE_VERSION == g7.G7_RULE_VERSION == G7_RULE_VERSION
    assert validator.G7_GENERATED_ARTIFACT_FAMILY_ID == (
        "policy-design-case-layer3-g7-region-widening-artifacts"
    )
    assert expected_paths == EXPECTED_ARTIFACT_PATHS
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) == EXPECTED_MANIFEST_DRIFT_KEYS
    assert set(validator.ALL_ISSUE_CODES) == TASK1_REQUIRED_ISSUE_CODES
    assert set(g7.ALL_ISSUE_CODES) == TASK1_REQUIRED_ISSUE_CODES


def test_layer3_g7_readiness_passes_current_blocked_runtime_bundle() -> None:
    validator = _validator()

    write_report = validator.validate_layer3_g7_readiness(REPO_ROOT, write=True)
    validation = validator.validate_layer3_g7_readiness(REPO_ROOT)

    assert write_report["status"] == "pass"
    assert validation["status"] == "pass"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    assert validation["summary"]["g7_engineering_readiness_status"] == "pass"
    assert validation["summary"]["g7_region_value_closure_status"] == (
        "blocked_by_current_g5_unchanged_blocker"
    )
    assert validation["summary"]["g7_current_g5_conversion_outcome"] == (
        "unchanged_blocker"
    )
    assert validation["summary"]["g7_current_g5_unchanged_blocker_status"] == "blocked"
    assert validation["summary"]["g7_region_grounded_case_count"] == 0
    assert validation["summary"]["g7_marginal_cost_status"] == (
        "blocked_insufficient_grounded_cases"
    )
    assert validation["summary"]["g7_s14_grounded_breadth_feed_status"] == (
        "blocked_no_real_grounded_breadth"
    )
    assert validation["summary"]["g7_s14_battery_input_manifest_status"] == (
        "blocked_no_real_grounded_breadth"
    )
    assert validation["summary"]["g7_public_projection_contract_status"] == "pass"
    assert validation["summary"]["g7_public_projection_official_use_status"] == "pass"


def test_layer3_g7_readiness_writes_exact_artifact_and_drift_scaffold() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g7_readiness(REPO_ROOT, write=True)
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert expected_paths == EXPECTED_ARTIFACT_PATHS
    assert set(validation["artifacts"]["written_artifact_paths"]) == expected_paths
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) == EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["summary"]["g7_manifest_runtime_drift_key_count"] == 0
    assert validation["summary"]["g7_route_contract_registry_status"] == "pass"
    assert validation["summary"]["g7_generated_artifacts_registration_status"] == "pass"


def test_layer3_g7_readiness_requires_registered_artifacts_inventory_and_docs() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g7_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["summary"]["g7_generated_artifacts_registration_status"] == "pass"
    assert validation["summary"]["g7_inventory_surface_status"] == "pass"
    assert validation["summary"]["g7_reference_docs_status"] == "pass"


def test_layer3_g7_registration_and_docs_fail_closed_when_markers_are_missing() -> None:
    validator = _validator()

    issues = validator._validate_registration_and_docs(
        {
            "generated_artifacts": "fail",
            "inventory": "fail",
            "docs": "fail",
            "route_contract_registry": "fail",
            "registry_ratchet": "fail",
        }
    )

    assert {
        "layer3_g7_generated_artifacts_family_missing",
        "layer3_g7_inventory_surface_missing",
        "layer3_g7_reference_index_missing",
        "layer3_g7_route_contract_registry_missing",
    } <= {issue["code"] for issue in issues}


def test_layer3_g7_write_path_must_include_every_expected_artifact(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    omitted = Path("architecture/policy_design_case/layer3_g7_replay_manifest.json")
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g7_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_g7_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g7_route_registry_is_generated_route_contract_registry() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g7_readiness(REPO_ROOT, write=True)
    registry_path = (
        REPO_ROOT / "architecture/policy_design_case/layer3_g7_region_route_contract_registry.toml"
    )
    registry_text = registry_path.read_text(encoding="utf-8")

    assert validation["summary"]["g7_route_contract_registry_status"] == "pass"
    assert "route_contract_registry_kind = \"generated_region_route_contract_registry\"" in registry_text
    assert "adapter_contract_registry" not in registry_text


def test_layer3_g7_stale_persisted_manifest_fails_closed(monkeypatch: Any) -> None:
    validator = _validator()

    monkeypatch.setattr(
        validator,
        "_manifest_runtime_drift_keys",
        lambda _repo_root, _bundle: ["g7_public_projection_contract_status"],
    )

    validation = validator.validate_layer3_g7_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert "layer3_g7_manifest_runtime_drift" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g7_readiness_writes_complete_conformance_negative_matrix() -> None:
    validator = _validator()

    validation = validator.validate_layer3_g7_readiness(REPO_ROOT, write=True)
    conformance = (
        REPO_ROOT / "architecture/policy_design_case/layer3_g7_conformance_report.json"
    )
    payload = validator._read_json(conformance)
    results = {
        result["negative_id"]: result
        for result in payload["negative_results"]
    }

    assert validation["summary"]["g7_conformance_status"] == "pass"
    assert set(g7.REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS) == (
        REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS
    )
    assert set(results) == REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS
    assert payload["missing_negative_ids"] == []
    assert payload["failing_negative_ids"] == []
    assert all(result["expected_issue_codes"] for result in results.values())
    assert all(result["observed_issue_codes"] for result in results.values())
    assert results["manifest_runtime_drift"]["observed_issue_codes"] == [
        "layer3_g7_manifest_runtime_drift"
    ]
    assert results["route_contract_registry_missing"]["observed_issue_codes"] == [
        "layer3_g7_route_contract_registry_missing"
    ]


def test_layer3_g7_readiness_fails_when_conformance_negative_is_missing(
    monkeypatch: Any,
) -> None:
    validator = _validator()

    def failing_conformance_report(**_kwargs: Any) -> dict[str, Any]:
        return {
            "schema_version": g7.G7_SCHEMA_VERSION,
            "rule_version": g7.G7_RULE_VERSION,
            "report_id": "layer3-g7://conformance/report",
            "status": "fail",
            "capability_reality_label": "semantic_test_missing",
            "negative_results": [],
            "missing_negative_ids": ["public_projection_authority_leak"],
            "failing_negative_ids": [],
            "issue_codes": ["public_projection_authority_leak"],
        }

    monkeypatch.setattr(g7, "build_g7_conformance_report", failing_conformance_report)

    validation = validator.validate_layer3_g7_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert validation["summary"]["g7_conformance_status"] == "fail"
    assert "layer3_g7_replay_helper_bypassed" in {
        issue["code"] for issue in validation["issues"]
    }
