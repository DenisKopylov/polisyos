from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.proving_ground import region_widening as g7
from tools.quality.validation import check_policy_design_case_layer3_g7_readiness as validator

REPO_ROOT = Path(__file__).resolve().parents[3]


def _validator() -> Any:
    return validator


def test_layer3_g7_readiness_cli_delegates_to_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[tuple[Path, bool]] = []

    def fake_validate_layer3_g7_readiness(
        repo_root: Path,
        *,
        write: bool = False,
    ) -> dict[str, Any]:
        calls.append((Path(repo_root), write))
        return {
            "schema_version": g7.G7_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g7_orchestration_continuity_missing",
                    "path": "$.orchestration_continuity",
                    "message": "G7 replay continuity is missing required refs.",
                }
            ],
            "summary": {
                "schema_version": g7.G7_SCHEMA_VERSION,
                "g7_orchestration_continuity_status": "fail",
            },
            "artifacts": {},
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g7_readiness",
        fake_validate_layer3_g7_readiness,
    )
    output = tmp_path / "layer3-g7-readiness.json"

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
    assert payload["issues"][0]["code"] == "layer3_g7_orchestration_continuity_missing"
    assert "layer3_g7_orchestration_continuity_missing" in stdout


def test_layer3_g7_readiness_cli_write_mode_reports_exact_artifact_paths(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    validator = _validator()
    expected = sorted(path.as_posix() for path in validator.EXPECTED_ARTIFACT_PATHS)

    monkeypatch.setattr(
        validator,
        "validate_layer3_g7_readiness",
        lambda repo_root, *, write=False: {
            "schema_version": g7.G7_SCHEMA_VERSION,
            "status": "pass",
            "issues": [],
            "summary": {"schema_version": g7.G7_SCHEMA_VERSION},
            "artifacts": {"written_artifact_paths": expected},
            "write": write,
        },
    )
    output = tmp_path / "layer3-g7-write.json"

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
