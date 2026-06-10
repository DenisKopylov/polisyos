from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
G2_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g2_causal_forecast.v1"

EXPECTED_WRITE_ARTIFACTS = [
    "architecture/policy_design_case/layer3_g2_method_requirement_bindings.json",
    "architecture/policy_design_case/layer3_g2_semantic_spine_bindings.json",
    "architecture/policy_design_case/layer3_g2_w12d_consumer_gate.json",
    "architecture/policy_design_case/layer3_g2_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g2_readiness_manifest.json",
]


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g2_readiness")


def test_layer3_g2_readiness_cli_delegates_to_runtime_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g2_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G2_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g2_s10_consumer_bridge_missing",
                    "path": "$.w12d_consumer_gate",
                    "message": "G2 readiness requires a consumed S10 posture gate.",
                }
            ],
            "summary": {
                "schema_version": G2_SCHEMA_VERSION,
                "rule_version": "policyos.layer3.g2.causal_forecast_search.v1",
                "g1_dependency_status": "pass",
                "g2_l2_skg_coverage_status": "pass",
                "g2_method_requirement_binding_count": 1,
                "g2_semantic_spine_binding_count": 1,
                "g2_w12d_consumer_gate_status": "fail",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g2_readiness",
        fake_validate_layer3_g2_readiness,
    )
    output = tmp_path / "layer3-g2-readiness.json"

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
    assert payload["schema_version"] == G2_SCHEMA_VERSION
    assert payload["status"] == "fail"
    assert payload["summary"]["schema_version"] == G2_SCHEMA_VERSION
    assert payload["issues"][0]["code"] == "layer3_g2_s10_consumer_bridge_missing"
    assert "layer3_g2_s10_consumer_bridge_missing" in stdout


def test_layer3_g2_readiness_cli_write_mode_reports_written_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g2_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G2_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {
                "schema_version": G2_SCHEMA_VERSION,
                "g1_dependency_status": "pass",
                "g2_method_requirement_binding_count": 1,
                "g2_semantic_spine_binding_count": 1,
                "g2_w12d_consumer_gate_status": "pass",
            },
            "artifacts": {
                "written_artifact_paths": EXPECTED_WRITE_ARTIFACTS,
            },
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g2_readiness",
        fake_validate_layer3_g2_readiness,
    )
    output = tmp_path / "layer3-g2-write.json"

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
    assert payload["schema_version"] == G2_SCHEMA_VERSION
    assert payload["write"] is True
    assert payload["artifacts"]["written_artifact_paths"] == EXPECTED_WRITE_ARTIFACTS
