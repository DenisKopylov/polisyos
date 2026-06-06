from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def _validator() -> Any:
    return import_module("tools.quality.validation.check_policy_design_case_layer3_g0_readiness")


def test_layer3_g0_readiness_cli_delegates_to_runtime_validator_and_reports_issue_codes(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    validator = _validator()
    calls: list[Path] = []

    def fake_validate_layer3_g0_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]:
        calls.append(Path(repo_root))
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "layer3_g0_inventory_missing_capability_source",
                    "path": "$.capability_inventory",
                    "message": "inventory is not frozen",
                }
            ],
            "summary": {
                "source_package_count": 0,
                "closure_artifact_count": 0,
            },
            "write": write,
        }

    monkeypatch.setattr(
        validator,
        "validate_layer3_g0_readiness",
        fake_validate_layer3_g0_readiness,
    )
    output = tmp_path / "layer3-g0-readiness.json"

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
    assert calls == [REPO_ROOT]
    assert payload["status"] == "fail"
    assert payload["issues"][0]["code"] == "layer3_g0_inventory_missing_capability_source"
    assert "layer3_g0_inventory_missing_capability_source" in stdout
