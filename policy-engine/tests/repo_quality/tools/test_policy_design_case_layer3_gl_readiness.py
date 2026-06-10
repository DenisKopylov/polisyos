from __future__ import annotations

import json
import tomllib
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
GL_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gl_legal_mandate_search.v1"

EXPECTED_ARTIFACT_PATHS = {
    "architecture/policy_design_case/layer3_gl_adapter_admission_registry.json",
    "architecture/policy_design_case/layer3_gl_l3_legal_kg_index_coverage.json",
    "architecture/policy_design_case/layer3_gl_l3_legal_kg_search_ledgers.json",
    "architecture/policy_design_case/layer3_gl_l3_legal_kg_query_traces.json",
    "architecture/policy_design_case/layer3_gl_search_recall_freshness.json",
    "architecture/policy_design_case/layer3_gl_l5_calibration_bindings.json",
    "architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json",
    "architecture/policy_design_case/layer3_gl_authority_facet_bindings.json",
    "architecture/policy_design_case/layer3_gl_norm_candidate_bindings.json",
    "architecture/policy_design_case/layer3_gl_threshold_authority_records.json",
    "architecture/policy_design_case/layer3_gl_mandate_authority_records.json",
    "architecture/policy_design_case/layer3_gl_temporal_competence_records.json",
    "architecture/policy_design_case/layer3_gl_amendment_lineage_records.json",
    "architecture/policy_design_case/layer3_gl_reference_resolution_records.json",
    "architecture/policy_design_case/layer3_gl_legal_authority_report.json",
    "architecture/policy_design_case/layer3_gl_lex_intervention_map_bindings.json",
    "architecture/policy_design_case/layer3_gl_claim_registry_consumer_gate.json",
    "architecture/policy_design_case/layer3_gl_semantic_binding_consumer_gate.json",
    ("architecture/policy_design_case/layer3_gl_argument_graph_readiness_consumer_gate.json"),
    "architecture/policy_design_case/layer3_gl_s6_mandate_consumer_gate.json",
    "architecture/policy_design_case/layer3_gl_s7_delegation_consumer_gate.json",
    "architecture/policy_design_case/layer3_gl_s8_value_choice_consumer_gate.json",
    "architecture/policy_design_case/layer3_gl_pdc_compiler_consumer_gate.json",
    "architecture/policy_design_case/layer3_gl_design_constraint_consumer_gate.json",
    ("architecture/policy_design_case/layer3_gl_g4_promotion_gate_consumer_gate.json"),
    "architecture/policy_design_case/layer3_gl_promotion_gate_handoff.json",
    "architecture/policy_design_case/layer3_gl_legal_mandate_audit_surface.json",
    "architecture/policy_design_case/layer3_gl_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_gl_conformance_report.json",
    "architecture/policy_design_case/layer3_gl_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_gl_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_gl_readiness_manifest.json",
}

REQUIRED_ADAPTER_PATH_IDS = {
    "layer3_gl_l3_legal_kg_to_search_ledger",
    "layer3_gl_search_ledger_to_norm_candidate_binding",
    "layer3_gl_l3_legal_kg_to_authority_facet_binding",
    "layer3_gl_legal_requirement_to_legal_authority_report",
    "layer3_gl_authority_facet_binding_to_legal_authority_report",
    "layer3_gl_legal_authority_report_to_threshold_authority_record",
    "layer3_gl_legal_authority_report_to_mandate_authority_record",
    "layer3_gl_temporal_lineage_to_competence_record",
    "layer3_gl_amendment_lineage_to_reissue_gate",
    "layer3_gl_authority_record_to_lex_intervention_map_binding",
    "layer3_gl_authority_record_to_claim_registry",
    "layer3_gl_authority_record_to_argument_graph_readiness",
    "layer3_gl_mandate_record_to_s6_s7_consumer_gate",
    "layer3_gl_mandate_record_to_s8_value_choice_consumer_gate",
    "layer3_gl_authority_record_to_design_constraints",
    "layer3_gl_authority_record_to_g4_promotion_gate_input",
    "layer3_gl_audit_surface_to_public_projection_refs",
    "layer3_gl_public_projection_refs_to_reference_only_surface",
}
REFERENCE_ONLY_PUBLIC_ROUTE = "layer3_gl_public_projection_refs_to_reference_only_surface"
PUBLIC_EXPORT_BUNDLE_ROUTE = "layer3_gl_public_projection_refs_to_public_export_bundle"
GL_READINESS_CHECK_ID = "layer3_gl_legal_mandate_search_readiness_gate"

EXPECTED_MANIFEST_DRIFT_KEYS = {
    "schema_version",
    "rule_version",
    "g0_dependency_status",
    "g1_context_status",
    "g2_context_status",
    "g3_context_status",
    "gl_l3_legal_kg_route_status",
    "gl_l3_legal_kg_table_count",
    "gl_l3_legal_kg_index_coverage_status",
    "gl_search_ledger_count",
    "gl_query_trace_count",
    "gl_search_recall_freshness_status",
    "gl_l5_calibration_binding_status",
    "gl_l5_calibration_binding_count",
    "gl_legal_requirement_binding_count",
    "gl_authority_facet_binding_status",
    "gl_authority_facet_binding_count",
    "gl_norm_candidate_binding_count",
    "gl_legal_authority_report_status",
    "gl_selected_norm_ref_count",
    "gl_legal_authority_record_count",
    "gl_threshold_authority_record_count",
    "gl_mandate_authority_record_count",
    "gl_temporal_competence_status",
    "gl_amendment_lineage_status",
    "gl_reference_resolution_status",
    "gl_lex_intervention_map_binding_status",
    "gl_claim_registry_consumer_gate_status",
    "gl_semantic_binding_consumer_gate_status",
    "gl_argument_graph_readiness_consumer_gate_status",
    "gl_s6_mandate_consumer_gate_status",
    "gl_s7_delegation_consumer_gate_status",
    "gl_s8_value_choice_consumer_gate_status",
    "gl_design_constraint_consumer_gate_status",
    "gl_g4_promotion_gate_consumer_gate_status",
    "gl_public_export_projection_status",
    "gl_public_export_projection_hook_status",
    "gl_public_export_projection_mode",
    "gl_public_export_projection_ref_surface_status",
    "gl_inventory_surface_status",
    "gl_reference_docs_status",
    "gl_invariant_readiness_check_registration_status",
    "gl_adapter_semantic_loss_status",
    "gl_governance_throughput_status",
    "gl_conformance_status",
    "gl_adapter_contract_registry_status",
    "gl_adapter_contract_path_count",
    "gl_health_metric_ids",
}

REQUIRED_ISSUE_CODES = {
    "layer3_gl_l3_legal_kg_missing",
    "layer3_gl_l3_legal_kg_route_not_bound",
    "layer3_gl_persisted_artifact_missing",
    "layer3_gl_manifest_runtime_drift",
    "layer3_gl_search_ledger_missing",
    "layer3_gl_query_trace_missing",
    "layer3_gl_false_abstention_recall_unmeasured",
    "layer3_gl_legal_requirement_binding_missing",
    "layer3_gl_authority_facet_binding_missing",
    "layer3_gl_kg_authority_facets_assumed_present",
    "layer3_gl_norm_candidate_binding_missing",
    "layer3_gl_l5_calibration_binding_missing",
    "layer3_gl_legal_authority_report_missing",
    "layer3_gl_selected_norm_without_legal_authority_record",
    "layer3_gl_threshold_row_not_hydrated",
    "layer3_gl_thresholds_json_used_as_authority",
    "layer3_gl_compiler_default_authority_type_laundered",
    "layer3_gl_internal_requirement_compile_used_for_closure",
    "layer3_gl_runtime_candidate_norm_snapshot_used_for_closure",
    "layer3_gl_lex_intervention_map_used_as_authority",
    "layer3_gl_mandate_source_refs_missing",
    "layer3_gl_s6_mandate_semantics_forked",
    "layer3_gl_claim_registry_consumer_gate_missing",
    "layer3_gl_semantic_binding_consumer_gate_missing",
    "layer3_gl_argument_graph_readiness_consumer_gate_missing",
    "layer3_gl_s6_mandate_consumer_gate_missing",
    "layer3_gl_s7_delegation_consumer_gate_missing",
    "layer3_gl_s8_value_choice_consumer_gate_missing",
    "layer3_gl_public_raw_legal_payload_leak",
    "layer3_gl_public_export_hook_overclaimed",
    "layer3_gl_public_export_projection_mode_mismatch",
    "layer3_gl_public_export_projection_ref_surface_missing",
    "layer3_gl_adapter_contract_registry_missing",
    "layer3_gl_adapter_registry_summary_only",
    "layer3_gl_generated_artifacts_family_missing",
    "layer3_gl_inventory_surface_missing",
    "layer3_gl_reference_index_missing",
    "layer3_gl_public_surface_visibility_missing",
    "layer3_gl_import_laziness_violation",
}


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_gl_readiness")


def test_layer3_gl_readiness_module_exists_and_declares_complete_expected_artifact_set() -> None:
    validator = _validator()

    expected_paths = {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}

    assert validator.GL_SCHEMA_VERSION == GL_SCHEMA_VERSION
    assert expected_paths >= EXPECTED_ARTIFACT_PATHS


def test_layer3_gl_readiness_requires_missing_persisted_artifacts_to_fail(monkeypatch: Any) -> None:
    validator = _validator()
    missing_path = Path("architecture/policy_design_case/layer3_gl_missing_probe.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", (missing_path,))

    validation = validator.validate_layer3_gl_readiness(REPO_ROOT)

    assert validation["status"] == "fail"
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == [missing_path.as_posix()]
    assert "layer3_gl_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_layer3_gl_readiness_manifest_drift_keys_are_enforced() -> None:
    validator = _validator()

    assert set(validator.EXPECTED_MANIFEST_DRIFT_KEYS) >= EXPECTED_MANIFEST_DRIFT_KEYS

    validation = validator.validate_layer3_gl_readiness(REPO_ROOT)

    assert set(validation["summary"]) >= EXPECTED_MANIFEST_DRIFT_KEYS
    assert validation["summary"]["schema_version"] == GL_SCHEMA_VERSION
    assert "gl_manifest_runtime_drift_key_count" in validation["summary"]


def test_layer3_gl_write_path_includes_every_required_runtime_artifact(monkeypatch: Any) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [path.as_posix() for path in expected_paths],
    )

    validation = validator.validate_layer3_gl_readiness(REPO_ROOT, write=True)

    written_paths = set(validation["artifacts"]["written_artifact_paths"])
    assert validation["write"] is True
    assert written_paths >= EXPECTED_ARTIFACT_PATHS
    assert written_paths <= {path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS}


def test_layer3_gl_readiness_fails_when_write_path_omits_consumer_or_authority_records(
    monkeypatch: Any,
) -> None:
    validator = _validator()
    expected_paths = tuple(Path(path) for path in sorted(EXPECTED_ARTIFACT_PATHS))
    omitted = Path("architecture/policy_design_case/layer3_gl_legal_authority_report.json")
    monkeypatch.setattr(validator, "EXPECTED_ARTIFACT_PATHS", expected_paths)
    monkeypatch.setattr(
        validator,
        "_write_artifacts",
        lambda _repo_root, _bundle: [path.as_posix() for path in expected_paths if path != omitted],
    )

    validation = validator.validate_layer3_gl_readiness(REPO_ROOT, write=True)

    assert validation["status"] == "fail"
    assert "layer3_gl_persisted_artifact_missing" in {
        issue["code"] for issue in validation["issues"]
    }
    assert omitted.as_posix() not in validation["artifacts"]["written_artifact_paths"]


def test_layer3_gl_readiness_reports_gl_specific_issue_code_dictionary() -> None:
    issue_codes = set(_validator().ALL_ISSUE_CODES)

    assert issue_codes >= REQUIRED_ISSUE_CODES


def test_layer3_gl_task8_readiness_passes_for_persisted_closeout_bundle() -> None:
    validation = _validator().validate_layer3_gl_readiness(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["issues"] == []
    assert validation["artifacts"]["missing_persisted_artifact_paths"] == []
    assert validation["summary"]["gl_manifest_runtime_drift_key_count"] == 0
    assert validation["summary"]["persisted_gl_artifact_count"] == 32
    assert validation["summary"]["gl_conformance_status"] == "pass"
    assert validation["summary"]["gl_adapter_semantic_loss_status"] == "pass"
    assert validation["summary"]["gl_governance_throughput_status"] == "pass"


def test_layer3_gl_adapter_contract_registry_paths_match_reference_only_projection_mode() -> None:
    validator = _validator()
    bundle = validator.gl.build_layer3_gl_bundle(REPO_ROOT)
    registry = bundle.adapter_contract_registry
    path_ids = set(registry.get("adapter_path_ids", ()))
    public_routes = path_ids & {REFERENCE_ONLY_PUBLIC_ROUTE, PUBLIC_EXPORT_BUNDLE_ROUTE}

    assert path_ids >= REQUIRED_ADAPTER_PATH_IDS
    assert registry["adapter_path_count"] == len(path_ids)
    assert registry["public_projection_mode"] == "reference_only"
    assert registry["public_projection_route"] == REFERENCE_ONLY_PUBLIC_ROUTE
    assert registry["public_export_bundle_route_registered"] is False
    assert public_routes == {REFERENCE_ONLY_PUBLIC_ROUTE}
    assert PUBLIC_EXPORT_BUNDLE_ROUTE not in path_ids
    assert bundle.readiness_manifest.gl_adapter_contract_registry_status == "pass"
    assert bundle.readiness_manifest.gl_adapter_contract_path_count == len(path_ids)


def test_layer3_gl_readiness_rejects_summary_only_adapter_contract_registry() -> None:
    validator = _validator()
    bundle = validator.gl.build_layer3_gl_bundle(REPO_ROOT)
    summary_only = bundle.model_copy(
        update={
            "adapter_contract_registry": {
                "status": "reference_only",
                "adapter_path_ids": ("layer3_gl_l3_legal_kg_to_search_ledger",),
                "public_projection_mode": "reference_only",
            }
        }
    )

    issues = validator._validate_runtime_surfaces(summary_only)

    assert "layer3_gl_adapter_registry_summary_only" in {issue["code"] for issue in issues}


def test_layer3_gl_generated_artifact_family_inventory_and_reference_docs_are_registered() -> None:
    validator = _validator()
    generated = tomllib.loads(
        (REPO_ROOT / "architecture/generated_artifacts.toml").read_text(encoding="utf-8")
    )
    families = {family["id"]: family for family in generated["family"]}
    family = families[validator.gl.GL_GENERATED_ARTIFACT_FAMILY_ID]
    inventory = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/inventory.json").read_text(encoding="utf-8")
    )
    inventory_ids = {artifact["id"] for artifact in inventory["artifacts"]}
    generated_docs = (REPO_ROOT / "docs/reference/generated-artifacts.md").read_text(
        encoding="utf-8"
    )

    assert set(family["outputs"]) >= EXPECTED_ARTIFACT_PATHS
    assert "check_policy_design_case_layer3_gl_readiness.py" in family["workflow"]
    assert validator.gl.GL_SURFACE_ID in inventory_ids
    assert validator.gl.GL_PUBLIC_PROJECTION_SURFACE_ID in inventory_ids
    assert validator.gl.GL_GENERATED_ARTIFACT_FAMILY_ID in generated_docs
    assert "layer3_gl_readiness_manifest.json" in generated_docs


def test_layer3_gl_argument_graph_readiness_check_is_known_to_invariant_validator() -> None:
    from polisyos.runtime.quality.invariants import KNOWN_READINESS_CHECKS

    validator = _validator()
    validation = validator.validate_layer3_gl_readiness(REPO_ROOT)
    gate = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gl_argument_graph_readiness_consumer_gate.json"
        ).read_text(encoding="utf-8")
    )
    readiness_checks = {
        row["readiness_check"] for row in gate["readiness_rows"] if row.get("readiness_check")
    }

    assert GL_READINESS_CHECK_ID in readiness_checks
    assert GL_READINESS_CHECK_ID in KNOWN_READINESS_CHECKS
    assert validation["summary"]["gl_invariant_readiness_check_registration_status"] == "pass"
    assert "layer3_gl_invariant_readiness_check_unknown" not in {
        issue["code"] for issue in validation["issues"]
    }
