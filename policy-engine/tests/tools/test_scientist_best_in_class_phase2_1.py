from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase2_1 as gate

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_scientist_phase2_1_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase2_1.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["assessment_id"] == "scientist_best_in_class_phase2_1"
    assert payload["passes_all"] is True
    assert payload["category_results"]["phase2_0_gate_green"] is True
    assert payload["category_results"]["lifecycle_contracts_validate"] is True


def test_scientist_phase2_1_gate_fails_without_reference_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        gate,
        "REFERENCE_TOKENS",
        (*gate.REFERENCE_TOKENS, "__missing_phase2_1_reference_token__"),
    )
    output_json = tmp_path / "phase2_1.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["passes_all"] is False
    assert (
        "missing_reference_token:__missing_phase2_1_reference_token__"
        in payload["notes"]
    )
