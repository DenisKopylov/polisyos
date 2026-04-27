from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase1_6 as gate

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_scientist_phase1_6_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase1_6.json"

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
    assert payload["assessment_id"] == "scientist_best_in_class_phase1_6"
    assert payload["passes_all"] is True
    assert payload["category_results"]["models_import_and_validate"] is True


def test_scientist_phase1_6_gate_fails_without_reference_token(tmp_path: Path) -> None:
    _write_minimal_repo(
        tmp_path,
        omitted_reference_token="HumanReviewPacket",  # noqa: S106 - reference token fixture.
    )
    output_json = tmp_path / "phase1_6.json"

    exit_code = gate.main(
        [
            "--repo-root",
            str(tmp_path),
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
    assert "missing_reference_token:HumanReviewPacket" in payload["notes"]


def _write_minimal_repo(repo_root: Path, *, omitted_reference_token: str) -> None:
    for path in (*gate.REQUIRED_PACKAGE_FILES, *gate.REQUIRED_INTEGRATION_FILES):
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        tokens = ["phase1_6"]
        tokens.extend(gate.INTEGRATION_TOKENS.get(path, ()))
        absolute.write_text("\n".join(tokens) + "\n", encoding="utf-8")

    for path in gate.REQUIRED_TEST_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(gate.NEGATIVE_TEST_TOKENS.get(path, ("test",)))
        absolute.write_text(content + "\n", encoding="utf-8")

    (repo_root / gate.REFERENCE_DOC).parent.mkdir(parents=True, exist_ok=True)
    reference_tokens = [
        token for token in gate.REFERENCE_TOKENS if token != omitted_reference_token
    ]
    (repo_root / gate.REFERENCE_DOC).write_text(
        "\n".join(reference_tokens),
        encoding="utf-8",
    )
    (repo_root / gate.ACTIVE_PLAN_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.ACTIVE_PLAN_DOC).write_text(
        "1.6\nHuman oversight\nclosed\n",
        encoding="utf-8",
    )
