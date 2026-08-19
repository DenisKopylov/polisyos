from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6
from tools.quality.validation import check_policy_design_case_layer3_g6_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]
G6_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g6_bounded_agent.v1"
G6_RULE_VERSION = "policyos.layer3.g6.bounded_agent.v1"

EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_g6_dependency_readiness_snapshot.json",
    "architecture/policy_design_case/layer3_g6_request_envelope.json",
    "architecture/policy_design_case/layer3_g6_request_classification.json",
    "architecture/policy_design_case/layer3_g6_policy_grammar_projection.json",
    "architecture/policy_design_case/layer3_g6_grammar_expansion_candidates.json",
    "architecture/policy_design_case/layer3_g6_grounding_demand_record.json",
    "architecture/policy_design_case/layer3_g6_tool_contract_summary.json",
    "architecture/policy_design_case/layer3_g6_prompt_tool_ledger_projection.json",
    "architecture/policy_design_case/layer3_g6_hypothesis_ledger_projection.json",
    "architecture/policy_design_case/layer3_g6_search_ledger.json",
    "architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json",
    "architecture/policy_design_case/layer3_g6_counterexample_refinement_record.json",
    "architecture/policy_design_case/layer3_g6_design_record_candidate_handoff.json",
    "architecture/policy_design_case/layer3_g6_candidate_authority_firewall_report.json",
    "architecture/policy_design_case/layer3_g6_g5_invocation_plan.json",
    "architecture/policy_design_case/layer3_g6_g5_consumer_gate.json",
    "architecture/policy_design_case/layer3_g6_orchestration_continuity.json",
    "architecture/policy_design_case/layer3_g6_replay_manifest.json",
    "architecture/policy_design_case/layer3_g6_agent_run_records.json",
    "architecture/policy_design_case/layer3_g6_grounded_result_or_abstention.json",
    "architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json",
    "architecture/policy_design_case/layer3_g6_agent_audit_surface.json",
    "architecture/policy_design_case/layer3_g6_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g6_conformance_report.json",
    "architecture/policy_design_case/layer3_g6_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g6_agent_route_contract_registry.toml",
    "architecture/policy_design_case/layer3_g6_registry_ratchet_delta.json",
    "architecture/policy_design_case/layer3_g6_readiness_manifest.json",
}
EXPECTED_MANIFEST_DRIFT_KEYS = {
    "g6_engineering_readiness_status",
    "g6_grounded_value_closure_status",
    "g6_policy_grammar_status",
    "g6_agent_loop_trace_status",
    "g6_llm_client_status",
    "g6_search_ledger_status",
    "g6_search_ledger_authority_boundary_status",
    "g6_design_record_candidate_handoff_status",
    "g6_g4_source_design_record_boundary_status",
    "g6_g5_bridge_status",
    "g6_g5_may_not_use_for_boundary_status",
    "g6_orchestration_choice_audit_status",
    "g6_compression_loss_receipt_status",
    "g6_authority_delta_completeness_status",
    "g6_summary_authority_preservation_status",
    "g6_authority_preserving_public_export_status",
    "g6_orchestration_continuity_status",
    "g6_replay_manifest_status",
    "g6_replay_drift_status",
    "g6_runtime_import_boundary_status",
    "g6_public_projection_contract_status",
    "g6_outside_envelope_abstention_quality_status",
    "g6_demand_pull_vs_abstention_status",
}

TASK1_REQUIRED_ISSUE_CODES = {
    "layer3_g6_g5_readiness_missing",
    "layer3_g6_request_envelope_missing",
    "layer3_g6_policy_grammar_projection_missing",
    "layer3_g6_llm_client_unavailable",
    "layer3_g6_agent_candidate_used_as_authority",
    "layer3_g6_g5_bypass_attempt",
    "layer3_g6_public_raw_prompt_leak",
    "layer3_g6_persisted_artifact_missing",
}


def _validator() -> Any:
    return validator


def test_layer3_g6_readiness_module_declares_red_baseline_contract() -> None:
    validator = _validator()
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert validator.G6_SCHEMA_VERSION == g6.G6_SCHEMA_VERSION == G6_SCHEMA_VERSION
    assert validator.G6_RULE_VERSION == g6.G6_RULE_VERSION == G6_RULE_VERSION
    assert expected_paths == EXPECTED_ARTIFACT_PATHS
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert set(validator.ALL_ISSUE_CODES) >= TASK1_REQUIRED_ISSUE_CODES


def test_layer3_g6_readiness_passes_for_persisted_runtime_bundle() -> None:
    validator = _validator()

    write_report = validator.validate_layer3_g6_readiness(REPO_ROOT, write=True)
    validation = validator.validate_layer3_g6_readiness(REPO_ROOT)

    assert write_report["status"] == "pass"
    assert validation["status"] == "pass"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    assert validation["summary"]["g6_g5_bridge_status"] == "pass"
    assert validation["summary"]["g6_policy_grammar_status"] == "pass"
    assert validation["summary"]["g6_agent_loop_trace_status"] == "pass"
    assert validation["summary"]["g6_llm_client_status"] in {
        "pass",
        "blocked_with_typed_issue",
    }
    assert validation["summary"]["g6_search_ledger_status"] == "pass"
    assert validation["summary"]["g6_search_ledger_authority_boundary_status"] == "pass"
    assert validation["summary"]["g6_orchestration_choice_audit_status"] == "pass"
    assert validation["summary"]["g6_compression_loss_receipt_status"] == "pass"
    assert validation["summary"]["g6_authority_delta_completeness_status"] == "pass"
    assert validation["summary"]["g6_summary_authority_preservation_status"] == "pass"
    assert validation["summary"]["g6_authority_preserving_public_export_status"] == (
        "pass"
    )
    assert validation["summary"]["g6_orchestration_continuity_status"] == "pass"
    assert validation["summary"]["g6_replay_manifest_status"] == "pass"
    assert validation["summary"]["g6_runtime_import_boundary_status"] == "pass"
    assert validation["summary"]["g6_public_projection_contract_status"] == "pass"
    assert validation["summary"]["g6_engineering_readiness_status"] == "pass"
    assert validation["summary"]["g6_grounded_value_closure_status"] in {
        "pass",
        "blocked_by_current_g5_unchanged_blocker",
    }


def test_layer3_g6_readiness_mirrors_exact_artifact_and_drift_scaffold() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g6_readiness(REPO_ROOT, write=True)
    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert expected_paths == EXPECTED_ARTIFACT_PATHS
    assert set(validation["artifacts"]["written_artifact_paths"]) == expected_paths
    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["summary"]["g6_manifest_runtime_drift_key_count"] == 0


def test_layer3_g6_readiness_requires_registered_artifacts_inventory_and_docs() -> None:
    validator = _validator()
    validation = validator.validate_layer3_g6_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "pass"
    assert validation["summary"]["g6_generated_artifacts_registration_status"] == "pass"
    assert validation["summary"]["g6_inventory_surface_status"] == "pass"
    assert validation["summary"]["g6_reference_docs_status"] == "pass"


def test_layer3_g6_registration_and_docs_fail_closed_when_markers_are_missing() -> None:
    validator = _validator()

    issues = validator._validate_registration_and_docs(
        {"generated_artifacts": "fail", "inventory": "fail", "docs": "fail"}
    )

    assert {
        "layer3_g6_generated_artifacts_family_missing",
        "layer3_g6_inventory_surface_missing",
        "layer3_g6_reference_index_missing",
    } <= {issue["code"] for issue in issues}


def test_layer3_g6_registration_rejects_stale_public_export_inventory(
    tmp_path: Path,
) -> None:
    validator = _validator()
    source_path = REPO_ROOT / validator.INVENTORY_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    row = next(
        item
        for item in payload["artifacts"]
        if item.get("id") == "layer3_g6_public_export_projection_refs"
    )
    row["public_export_hook_status"] = "out_of_scope_reference_only"
    row["public_export_bundle_route_registered"] = False
    target_path = tmp_path / validator.INVENTORY_PATH
    target_path.parent.mkdir(parents=True)
    target_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    statuses = validator._registration_statuses(tmp_path)

    assert statuses["inventory"] == "fail"


def test_layer3_g6_registration_rejects_stale_public_surface_prose(
    tmp_path: Path,
) -> None:
    validator = _validator()
    copied_paths = (
        validator.GENERATED_ARTIFACTS_TOML_PATH,
        validator.GENERATED_ARTIFACTS_DOC_PATH,
        validator.DOCS_SURFACE_PATH,
        validator.DOCUMENTATION_INVENTORY_PATH,
        validator.REFERENCE_INDEX_PATH,
        validator.PUBLIC_SURFACE_DOC_PATH,
    )
    for path in copied_paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (REPO_ROOT / path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    public_surface_path = tmp_path / validator.PUBLIC_SURFACE_DOC_PATH
    public_surface_text = public_surface_path.read_text(encoding="utf-8")
    safe_projection_marker = "owner-recomputed safe summary or governed refusal"
    assert safe_projection_marker in public_surface_text
    public_surface_path.write_text(
        public_surface_text.replace(
            safe_projection_marker,
            "caller-supplied clean summary",
            1,
        ),
        encoding="utf-8",
    )

    statuses = validator._registration_statuses(tmp_path)

    assert statuses["docs"] == "fail"


def test_layer3_g6_write_path_must_include_every_expected_artifact(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    omitted = Path("architecture/policy_design_case/layer3_g6_agent_run_records.json")
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [
            path.as_posix() for path in expected_paths if path != omitted
        ],
    )

    validation = validator.validate_layer3_g6_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_g6_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_g6_persisted_compression_tamper_fails_closed(
    tmp_path: Path,
) -> None:
    validator = _validator()
    bundle = validator._build_runtime_bundle(REPO_ROOT)
    validator._write_artifacts(tmp_path, bundle)
    run_records_path = tmp_path / validator.AGENT_RUN_RECORDS_PATH
    payload = json.loads(run_records_path.read_text(encoding="utf-8"))
    receipt = payload["agent_run_records"][0]["prompt_tool_ledger_projection"][
        "prompt_tool_ledger"
    ]["compression_loss_receipts"][0]
    receipt["retained_limitations"] = []
    run_records_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    issues = validator._validate_persisted_artifacts(tmp_path)

    assert "layer3_g6_compression_loss_receipt_blocked" in {
        issue["code"] for issue in issues
    }


def test_layer3_g6_persisted_public_export_tamper_fails_closed(
    tmp_path: Path,
) -> None:
    validator = _validator()
    bundle = validator._build_runtime_bundle(REPO_ROOT)
    validator._write_artifacts(tmp_path, bundle)
    public_export_path = tmp_path / validator.PUBLIC_EXPORT_PROJECTION_REFS_PATH
    payload = json.loads(public_export_path.read_text(encoding="utf-8"))
    compression_result = payload["public_export_bundle"]["artifacts"][
        "g6_summary_authority_preservation"
    ]["compression_result"]
    compression_result["summary"]["limitations"] = []
    public_export_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    issues = validator._validate_persisted_artifacts(tmp_path)

    assert "layer3_g6_public_projection_contract_failed" in {
        issue["code"] for issue in issues
    }
