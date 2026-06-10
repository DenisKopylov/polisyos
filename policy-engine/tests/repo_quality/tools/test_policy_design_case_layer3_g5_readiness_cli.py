from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
G5_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g5_proving_ground_conversion.v1"

EXPECTED_WRITE_ARTIFACTS = [
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
]


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


def test_layer3_g5_readiness_cli_delegates_to_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    """P01/P10 red baseline: CLI must expose typed G5 issue codes, not prose only."""

    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g5_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G5_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g5_w12d_consumer_gate_missing",
                    "path": "$.w12d_consumer_gate",
                    "message": "G5 cannot close without the W12.D consumer gate.",
                }
            ],
            "summary": {
                "schema_version": G5_SCHEMA_VERSION,
                "rule_version": "policyos.layer3.g5.first_proving_ground_conversion.v1",
                "g5_dependency_readiness_status": "fail",
                "g5_w12d_consumer_gate_status": "fail",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g5_readiness",
        fake_validate_layer3_g5_readiness,
    )
    output = tmp_path / "layer3-g5-readiness.json"

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
    assert payload["schema_version"] == G5_SCHEMA_VERSION
    assert payload["status"] == "fail"
    assert payload["issues"][0]["code"] == "layer3_g5_w12d_consumer_gate_missing"
    assert "layer3_g5_w12d_consumer_gate_missing" in stdout


def test_layer3_g5_readiness_cli_write_mode_reports_exact_json_and_toml_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """P03/P07 red baseline: write mode must enumerate every persisted G5 artifact."""

    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g5_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": G5_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {
                "schema_version": G5_SCHEMA_VERSION,
                "g5_dependency_readiness_status": "pass",
                "g5_w12d_consumer_gate_status": "pass",
                "g5_conversion_record_count": 1,
            },
            "artifacts": {
                "written_artifact_paths": EXPECTED_WRITE_ARTIFACTS,
            },
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g5_readiness",
        fake_validate_layer3_g5_readiness,
    )
    output = tmp_path / "layer3-g5-write.json"

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
    assert payload["schema_version"] == G5_SCHEMA_VERSION
    assert payload["write"] is True
    assert payload["artifacts"]["written_artifact_paths"] == EXPECTED_WRITE_ARTIFACTS
