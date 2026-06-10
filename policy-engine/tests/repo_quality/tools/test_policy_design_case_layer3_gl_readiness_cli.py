from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
GL_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gl_legal_mandate_search.v1"
GL_RULE_VERSION = "policyos.layer3.gl.legal_mandate_search.v1"

EXPECTED_WRITE_ARTIFACTS = [
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
]


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_gl_readiness")


def test_layer3_gl_readiness_cli_delegates_to_runtime_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_gl_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": GL_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_gl_legal_authority_report_missing",
                    "path": "$.legal_authority_report",
                    "message": "GL readiness requires claim-level legal authority report binding.",
                }
            ],
            "summary": {
                "schema_version": GL_SCHEMA_VERSION,
                "rule_version": GL_RULE_VERSION,
                "g0_dependency_status": "pass",
                "g1_context_status": "loaded_context",
                "g2_context_status": "loaded_context",
                "g3_context_status": "loaded_context",
                "gl_l3_legal_kg_route_status": "pass",
                "gl_legal_authority_report_status": "fail",
                "gl_claim_registry_consumer_gate_status": "fail",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_gl_readiness",
        fake_validate_layer3_gl_readiness,
    )
    output = tmp_path / "layer3-gl-readiness.json"

    exit_code = validator.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output),
            "--output-format",
            "json",
        ]
    )
    stdout = capsys.readouterr().out
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert calls == [(REPO_ROOT, False)]
    assert set(payload) >= {"schema_version", "status", "summary", "issues"}
    assert payload["schema_version"] == GL_SCHEMA_VERSION
    assert payload["status"] == "fail"
    assert payload["summary"]["schema_version"] == GL_SCHEMA_VERSION
    assert payload["issues"][0]["code"] == "layer3_gl_legal_authority_report_missing"
    assert "layer3_gl_legal_authority_report_missing" in stdout


def test_layer3_gl_readiness_cli_write_mode_reports_written_json_and_toml_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_gl_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": GL_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {
                "schema_version": GL_SCHEMA_VERSION,
                "rule_version": GL_RULE_VERSION,
                "g0_dependency_status": "pass",
                "g1_context_status": "loaded_context",
                "g2_context_status": "loaded_context",
                "g3_context_status": "loaded_context",
                "gl_l3_legal_kg_route_status": "pass",
                "gl_legal_authority_report_status": "pass",
                "gl_claim_registry_consumer_gate_status": "pass",
            },
            "artifacts": {
                "written_artifact_paths": EXPECTED_WRITE_ARTIFACTS,
            },
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_gl_readiness",
        fake_validate_layer3_gl_readiness,
    )
    output = tmp_path / "layer3-gl-write.json"

    exit_code = validator.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--write",
            "--output",
            str(output),
            "--output-format",
            "json",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert calls == [(REPO_ROOT, True)]
    assert payload["schema_version"] == GL_SCHEMA_VERSION
    assert payload["write"] is True
    assert payload["artifacts"]["written_artifact_paths"] == EXPECTED_WRITE_ARTIFACTS
