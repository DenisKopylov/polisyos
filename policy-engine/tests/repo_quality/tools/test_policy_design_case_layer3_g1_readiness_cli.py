from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g1_readiness")


def test_layer3_g1_readiness_cli_delegates_to_runtime_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g1_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g1_search_ledger_authority_boundary_leak",
                    "path": "$.search_ledgers[0].authoritative_for",
                    "message": "search ledgers are control-plane records only",
                }
            ],
            "summary": {
                "schema_version": "policyos.policy_design_case.layer3_g1_substrate_grounding.v1",
                "rule_version": "policyos.layer3.g1.substrate_grounding_search.v1",
                "g1_substrate_search_ledger_count": 1,
                "g1_l1_l5_l6_index_coverage_status": "pass",
                "g1_search_recall_status": "pass",
                "g1_index_freshness_status": "pass",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g1_readiness",
        fake_validate_layer3_g1_readiness,
    )
    output = tmp_path / "layer3-g1-readiness.json"

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
    assert payload["status"] == "fail"
    assert payload["summary"]["schema_version"].endswith("layer3_g1_substrate_grounding.v1")
    assert payload["issues"][0]["code"] == "layer3_g1_search_ledger_authority_boundary_leak"
    assert "layer3_g1_search_ledger_authority_boundary_leak" in stdout


def test_layer3_g1_readiness_cli_write_mode_reports_artifacts(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []
    expected_artifacts = [
        "architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json",
        "architecture/policy_design_case/layer3_g1_l1_l5_l6_index_coverage.json",
        "architecture/policy_design_case/layer3_g1_readiness_manifest.json",
    ]

    def fake_validate_layer3_g1_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "status": "pass",
            "issues": [],
            "summary": {
                "schema_version": "policyos.policy_design_case.layer3_g1_substrate_grounding.v1",
                "g1_substrate_search_ledger_count": 1,
                "g1_adapter_contract_path_count": 2,
                "source_contract_snapshot_count": 1,
            },
            "artifacts": {
                "written_artifact_paths": expected_artifacts,
            },
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g1_readiness",
        fake_validate_layer3_g1_readiness,
    )
    output = tmp_path / "layer3-g1-write.json"

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
    assert payload["write"] is True
    assert payload["artifacts"]["written_artifact_paths"] == expected_artifacts
