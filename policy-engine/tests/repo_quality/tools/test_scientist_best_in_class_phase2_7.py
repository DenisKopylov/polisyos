from __future__ import annotations

import json

from tools.ci import check_scientist_best_in_class_phase2_7 as gate


def test_phase2_7_gate_passes_for_current_repo(tmp_path) -> None:
    output = tmp_path / "phase2_7.json"

    exit_code = gate.main(
        [
            "--repo-root",
            ".",
            "--output",
            str(output),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["passes_all"] is True
    assert payload["category_results"]["decision_grade_compiler_contracts_validate"] is True


def test_phase2_7_gate_reports_missing_reference_token(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for path in gate.REQUIRED_FILES:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")
    (repo / gate.REFERENCE_DOC).write_text("DecisionGradeExport\n", encoding="utf-8")
    (repo / gate.ACTIVE_PLAN_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo / gate.ACTIVE_PLAN_DOC).write_text(
        "Фаза 2.7 - Decision-grade research compiler\nclosed\n"
        "check_scientist_best_in_class_phase2_7.py\n",
        encoding="utf-8",
    )

    payload = gate._build_payload(repo)

    assert payload["passes_all"] is False
    assert any(str(note).startswith("missing_reference_token:") for note in payload["notes"])
