from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase2_0 as gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_scientist_phase2_0_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase2_0.json"

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
    assert payload["assessment_id"] == "scientist_best_in_class_phase2_0"
    assert payload["passes_all"] is True
    assert payload["category_results"]["wave1_gate_green"] is True
    assert payload["category_results"]["compatibility_contracts_validate"] is True
    assert payload["category_results"]["adrs_complete"] is True


def test_scientist_phase2_0_gate_fails_without_adr_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        gate,
        "ADR_REQUIRED_TOKENS",
        (*gate.ADR_REQUIRED_TOKENS, "__missing_phase2_0_adr_token__"),
    )
    output_json = tmp_path / "phase2_0.json"

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
    assert any(
        "__missing_phase2_0_adr_token__" in note for note in payload["notes"]
    )
