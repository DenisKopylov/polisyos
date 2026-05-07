from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase1_4 as gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_scientist_best_in_class_phase1_4_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase1-4-gate.json"

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
    assert payload["assessment_id"] == "scientist_best_in_class_phase1_4"
    assert payload["passes_all"] is True
    assert payload["category_results"]["models_import_and_validate"] is True
    assert payload["category_results"]["frontier_projection_present"] is True


def test_scientist_best_in_class_phase1_4_gate_fails_when_doc_omits_capability(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path, omit_capability_id="same_model_fanout")
    output_json = tmp_path / "phase1-4-gate.json"

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
    assert "missing_doc_capability_id:same_model_fanout" in payload["notes"]


def _write_minimal_repo(repo_root: Path, *, omit_capability_id: str) -> None:
    for path in gate.REQUIRED_PACKAGE_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        content = "phase1_4\n"
        if path.name == "promotion.py":
            content += (
                "AgentCapabilityPromotionReport\n"
                "AgentPromotionCoverageDomain\n"
                "AgentPromotionCoverageRecord\n"
                "project_agent_promotion_to_frontier_statuses\n"
                "default_enable_capability_ids\n"
            )
        if path.name == "frontier_runtime.py":
            content += "summarize_agent_promotion_frontier_status\n"
        absolute.write_text(content, encoding="utf-8")

    for path in gate.REQUIRED_TEST_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text("# test stub\n", encoding="utf-8")

    for path, tokens in gate.NEGATIVE_TEST_TOKENS.items():
        absolute = repo_root / path
        existing = absolute.read_text(encoding="utf-8") if absolute.is_file() else ""
        absolute.write_text(existing + "\n".join(tokens) + "\n", encoding="utf-8")

    (repo_root / gate.REFERENCE_DOC).parent.mkdir(parents=True, exist_ok=True)
    reference_tokens = [
        *gate.REFERENCE_TOKENS,
        *[
            f"`{capability_id}`"
            for capability_id in gate.CAPABILITY_IDS
            if capability_id != omit_capability_id
        ],
    ]
    (repo_root / gate.REFERENCE_DOC).write_text(
        "\n".join(reference_tokens),
        encoding="utf-8",
    )
    (repo_root / gate.ACTIVE_PLAN_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.ACTIVE_PLAN_DOC).write_text(
        "1.4\nAgent and tool runtime promotion gates\nclosed\n",
        encoding="utf-8",
    )
