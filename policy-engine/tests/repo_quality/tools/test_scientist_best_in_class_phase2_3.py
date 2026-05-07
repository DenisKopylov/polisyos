from __future__ import annotations

import json

from tools.ci import check_scientist_best_in_class_phase2_3 as gate


def test_phase2_3_gate_passes_for_current_repo(tmp_path) -> None:
    output = tmp_path / "phase2_3.json"

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
    assert payload["category_results"]["voi_contracts_validate"] is True


def test_phase2_3_gate_reports_missing_reference_token(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs/reference/scientist").mkdir(parents=True)
    (repo / "docs/plans/active").mkdir(parents=True)
    (repo / "src/polisyos/scientist/search").mkdir(parents=True)
    (repo / "src/polisyos/scientist/governance/human_review").mkdir(parents=True)
    (repo / "src/polisyos/scientist/evidence").mkdir(parents=True)
    (repo / "tools/ci").mkdir(parents=True)
    (repo / "tests/unit/scientist/search").mkdir(parents=True)
    (repo / "tests/unit/scientist/evidence").mkdir(parents=True)
    (repo / "tests/unit/scientist/governance/human_review").mkdir(parents=True)
    (repo / "tests/repo_quality/tools").mkdir(parents=True)
    for path in gate.REQUIRED_FILES:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")
    (repo / gate.REFERENCE_DOC).write_text("VOIDecisionRecord\n", encoding="utf-8")

    payload = gate._build_payload(repo)

    assert payload["passes_all"] is False
    assert any(str(note).startswith("missing_reference_token:") for note in payload["notes"])
