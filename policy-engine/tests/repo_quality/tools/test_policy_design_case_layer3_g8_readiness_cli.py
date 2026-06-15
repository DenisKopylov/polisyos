from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polisyos.runtime.quality.layer3_health_metric_governance as g8
from tools.quality.validation import check_policy_design_case_layer3_g8_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_layer3_g8_readiness_cli_delegates_to_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g8_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": g8.G8_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g8_conformance_negative_missing",
                    "path": (
                        "architecture/policy_design_case/"
                        "layer3_g8_conformance_report.json"
                    ),
                    "message": (
                        "G8 conformance report must pass all required negative probes."
                    ),
                }
            ],
            "summary": {
                "schema_version": g8.G8_SCHEMA_VERSION,
                "g8_conformance_status": "blocked",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g8_readiness",
        fake_validate_layer3_g8_readiness,
    )
    output = tmp_path / "layer3-g8-readiness.json"

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
    assert payload["issues"][0]["code"] == "layer3_g8_conformance_negative_missing"
    assert "layer3_g8_conformance_negative_missing" in stdout


def test_layer3_g8_readiness_cli_write_mode_reports_exact_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    expected = sorted(path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS)
    monkeypatch.setattr(
        validator,
        "validate_layer3_g8_readiness",
        lambda repo_root, *, write=False: {
            "schema_version": g8.G8_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {"schema_version": g8.G8_SCHEMA_VERSION},
            "artifacts": {"written_artifact_paths": expected},
            "write": write,
        },
    )
    output = tmp_path / "layer3-g8-write.json"

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
    assert payload["write"] is True
    assert sorted(payload["artifacts"]["written_artifact_paths"]) == expected
