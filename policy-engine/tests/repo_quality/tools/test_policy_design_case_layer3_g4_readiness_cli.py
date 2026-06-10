from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
G4_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g4_promotion_gate.v1"
EXPECTED_WRITE_ARTIFACTS = [
    "architecture/policy_design_case/layer3_g4_dependency_readiness_snapshot.json",
    "architecture/policy_design_case/layer3_g4_promotion_input_set.json",
    "architecture/policy_design_case/layer3_g4_grounded_contract_set.json",
    "architecture/policy_design_case/layer3_g4_a_completeness_ledger.json",
    "architecture/policy_design_case/layer3_g4_human_decision_integrity_gate.json",
    "architecture/policy_design_case/layer3_g4_weakest_boundary_composition.json",
    "architecture/policy_design_case/layer3_g4_promotion_records.json",
    "architecture/policy_design_case/layer3_g4_closeout_consumer_gate.json",
    "architecture/policy_design_case/layer3_g4_pdc_compiler_consumer_gate.json",
    "architecture/policy_design_case/layer3_g4_g5_promotion_handoff.json",
    "architecture/policy_design_case/layer3_g4_governance_throughput_delta.json",
    "architecture/policy_design_case/layer3_g4_promotion_audit_surface.json",
    "architecture/policy_design_case/layer3_g4_public_export_projection_refs.json",
    "architecture/policy_design_case/layer3_g4_conformance_report.json",
    "architecture/policy_design_case/layer3_g4_health_metric_delta.toml",
    "architecture/policy_design_case/layer3_g4_adapter_contract_registry.toml",
    "architecture/policy_design_case/layer3_g4_registry_ratchet_delta.json",
    "architecture/policy_design_case/layer3_g4_readiness_manifest.json",
]


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


def test_layer3_g4_readiness_cli_delegates_to_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g4_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G4_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g4_readiness_summary_only_promotion",
                    "path": "$.promotion_inputs[0].grounded_contract_refs",
                    "message": "Readiness summaries cannot satisfy G4 promotion.",
                }
            ],
            "summary": {
                "schema_version": G4_SCHEMA_VERSION,
                "rule_version": "policyos.layer3.g4.shadow_to_governed_promotion.v1",
                "g0_dependency_status": "pass",
                "g1_dependency_status": "pass",
                "g4_grounded_contract_set_status": "fail",
                "g4_promotion_blocked_count": 1,
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g4_readiness",
        fake_validate_layer3_g4_readiness,
    )
    output = tmp_path / "layer3-g4-readiness.json"

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
    assert payload["schema_version"] == G4_SCHEMA_VERSION
    assert payload["status"] == "fail"
    assert payload["issues"][0]["code"] == "layer3_g4_readiness_summary_only_promotion"
    assert "layer3_g4_readiness_summary_only_promotion" in stdout


def test_layer3_g4_readiness_cli_write_mode_reports_exact_json_and_toml_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g4_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G4_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {
                "schema_version": G4_SCHEMA_VERSION,
                "g0_dependency_status": "pass",
                "g1_dependency_status": "pass",
                "g4_a_completeness_status": "pass",
                "g4_promotion_record_count": 2,
                "g4_governed_promoted_count": 1,
                "g4_promotion_blocked_count": 1,
            },
            "artifacts": {
                "written_artifact_paths": EXPECTED_WRITE_ARTIFACTS,
            },
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g4_readiness",
        fake_validate_layer3_g4_readiness,
    )
    output = tmp_path / "layer3-g4-write.json"

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
    assert payload["schema_version"] == G4_SCHEMA_VERSION
    assert payload["write"] is True
    assert payload["artifacts"]["written_artifact_paths"] == EXPECTED_WRITE_ARTIFACTS
