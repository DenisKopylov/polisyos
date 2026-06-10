from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
G3_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g3_analytics_search.v1"

EXPECTED_WRITE_ARTIFACTS = [
    "architecture/policy_design_case/layer3_g3_certificate_resolution_report.json",
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
]


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g3_readiness")


def test_layer3_g3_readiness_cli_delegates_to_runtime_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g3_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G3_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g3_certificate_resolution_missing",
                    "path": "$.certificate_resolution_report",
                    "message": "G3 readiness requires resolved typed proof/certificate payloads.",
                }
            ],
            "summary": {
                "schema_version": G3_SCHEMA_VERSION,
                "rule_version": "policyos.layer3.g3.analytics_search.v1",
                "g0_dependency_status": "pass",
                "g1_dependency_status": "pass",
                "g2_dependency_status": "pass",
                "g3_l2_skg_dependency_status": "pass",
                "g3_certificate_resolution_status": "fail",
                "g3_ir_analytics_bridge_status": "fail",
                "g3_w12d_consumer_gate_status": "fail",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g3_readiness",
        fake_validate_layer3_g3_readiness,
    )
    output = tmp_path / "layer3-g3-readiness.json"

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
    assert payload["schema_version"] == G3_SCHEMA_VERSION
    assert payload["status"] == "fail"
    assert payload["summary"]["schema_version"] == G3_SCHEMA_VERSION
    assert payload["issues"][0]["code"] == "layer3_g3_certificate_resolution_missing"
    assert "layer3_g3_certificate_resolution_missing" in stdout


def test_layer3_g3_readiness_cli_write_mode_reports_written_json_and_toml_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g3_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G3_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {
                "schema_version": G3_SCHEMA_VERSION,
                "g0_dependency_status": "pass",
                "g1_dependency_status": "pass",
                "g2_dependency_status": "pass",
                "g3_certificate_resolution_status": "pass",
                "g3_resolved_certificate_count": 1,
                "g3_ir_analytics_bridge_status": "pass",
                "g3_w12d_consumer_gate_status": "pass",
            },
            "artifacts": {
                "written_artifact_paths": EXPECTED_WRITE_ARTIFACTS,
            },
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g3_readiness",
        fake_validate_layer3_g3_readiness,
    )
    output = tmp_path / "layer3-g3-write.json"

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
    assert payload["schema_version"] == G3_SCHEMA_VERSION
    assert payload["write"] is True
    assert payload["artifacts"]["written_artifact_paths"] == EXPECTED_WRITE_ARTIFACTS
