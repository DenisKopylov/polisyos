from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_wave1 as gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_scientist_wave1_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "wave1.json"

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
    assert payload["assessment_id"] == "scientist_best_in_class_wave1"
    assert payload["passes_all"] is True
    assert payload["category_results"]["phase_gates_green"] is True
    assert payload["category_results"]["cross_phase_contracts_validate"] is True
    assert set(payload["phase_gate_reports"]) == {
        "phase1_0",
        "phase1_1",
        "phase1_2",
        "phase1_3",
        "phase1_4",
        "phase1_5",
        "phase1_6",
    }


def test_scientist_wave1_gate_fails_without_reference_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        gate,
        "REFERENCE_TOKENS",
        (*gate.REFERENCE_TOKENS, "__missing_wave1_reference_token__"),
    )
    output_json = tmp_path / "wave1.json"

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
        "missing_reference_token:__missing_wave1_reference_token__"
        in payload["notes"]
    )
