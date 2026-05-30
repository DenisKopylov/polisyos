from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase1_1 as gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_scientist_best_in_class_phase1_1_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase1-1-gate.json"

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
    assert payload["assessment_id"] == "scientist_best_in_class_phase1_1"
    assert payload["passes_all"] is True
    assert payload["category_results"]["claim_package_imports"] is True
    assert payload["category_results"]["integration_targets_project_claims"] is True
    assert payload["category_results"]["negative_tests_cover_required_cases"] is True


def test_scientist_best_in_class_phase1_1_gate_fails_on_missing_claim_integration(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path, omit_claims_ref_in_packet=True)
    output_json = tmp_path / "phase1-1-gate.json"

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
    assert (
        "missing_claim_projection_integration:"
        "src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"
        in payload["notes"]
    )


def _write_minimal_repo(repo_root: Path, *, omit_claims_ref_in_packet: bool) -> None:
    for path in gate.REQUIRED_PACKAGE_FILES:
        (repo_root / path).parent.mkdir(parents=True, exist_ok=True)
        if path.name == "readiness.py":
            (repo_root / path).write_text(
                "from polisyos.scientist.methods.search.readiness import DecisionReadiness\n",
                encoding="utf-8",
            )
        elif path.name == "models.py":
            (repo_root / path).write_text(
                "from polisyos.scientist.evidence.claims import ClaimLedger\n",
                encoding="utf-8",
            )
        else:
            (repo_root / path).write_text("# stub\n", encoding="utf-8")

    for path in gate.REQUIRED_TEST_FILES:
        (repo_root / path).parent.mkdir(parents=True, exist_ok=True)
        (repo_root / path).write_text("# test stub\n", encoding="utf-8")

    for path, tokens in gate.REQUIRED_NEGATIVE_TEST_TOKENS.items():
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        existing = absolute.read_text(encoding="utf-8") if absolute.is_file() else ""
        absolute.write_text(existing + "\n".join(tokens) + "\n", encoding="utf-8")

    for path in gate.INTEGRATION_FILES:
        (repo_root / path).parent.mkdir(parents=True, exist_ok=True)
        content = ""
        if not (omit_claims_ref_in_packet and path.name == "build_decision_packet.py"):
            content = "claims_ref\n"
        (repo_root / path).write_text(content, encoding="utf-8")

    (repo_root / gate.REFERENCE_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.REFERENCE_DOC).write_text(
        "\n".join(
            [
                "# Claims",
                "No naked claims",
                "Decision-bearing surface inventory",
                "ClaimRecord",
                "ClaimLedger",
                "claims_ref",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / gate.ACTIVE_PLAN_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.ACTIVE_PLAN_DOC).write_text(
        "Phase 1.1 - Claim/Evidence/Readiness spine - closed\n",
        encoding="utf-8",
    )
