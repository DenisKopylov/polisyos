from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase1_3 as gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_scientist_best_in_class_phase1_3_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase1-3-gate.json"

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
    assert payload["assessment_id"] == "scientist_best_in_class_phase1_3"
    assert payload["passes_all"] is True
    assert payload["category_results"]["canonical_scholar_contract_extended"] is True
    assert payload["category_results"]["models_import_and_validate"] is True
    assert payload["category_results"]["integration_targets_use_phase1_3_helpers"] is True


def test_scientist_best_in_class_phase1_3_gate_fails_without_scholar_extensions(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path, omit_fetch_safety_fields=True)
    output_json = tmp_path / "phase1-3-gate.json"

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
    assert "missing_scholar_model_token:fetch_safety_events" in payload["notes"]


def _write_minimal_repo(repo_root: Path, *, omit_fetch_safety_fields: bool) -> None:
    for path in gate.REQUIRED_PACKAGE_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "__init__.py":
            absolute.write_text("", encoding="utf-8")
        else:
            content = "phase1_3\n"
            if path.name == "scholar_search_tools.py":
                content += "evaluate_fetch_request\nprompt_injection_suspected\nMAX_FETCH_BYTES\n"
            if path.name == "knowledge_tools_adapter.py":
                content += "adapter\n"
            absolute.write_text(content, encoding="utf-8")

    for path in gate.REQUIRED_TEST_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text("# test stub\n", encoding="utf-8")

    for path, tokens in gate.REQUIRED_NEGATIVE_TEST_TOKENS.items():
        absolute = repo_root / path
        existing = absolute.read_text(encoding="utf-8") if absolute.is_file() else ""
        absolute.write_text(existing + "\n".join(tokens) + "\n", encoding="utf-8")

    (repo_root / gate.SCHOLAR_MODELS).parent.mkdir(parents=True, exist_ok=True)
    scholar_tokens = [
        "class FetchSafetyEvent",
        "class SourceQualitySignal",
        "source_quality_signals",
    ]
    if not omit_fetch_safety_fields:
        scholar_tokens.append("fetch_safety_events")
    (repo_root / gate.SCHOLAR_MODELS).write_text("\n".join(scholar_tokens), encoding="utf-8")

    (repo_root / gate.REFERENCE_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.REFERENCE_DOC).write_text(
        "\n".join(gate.REFERENCE_TOKENS),
        encoding="utf-8",
    )
    (repo_root / gate.ACTIVE_PLAN_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.ACTIVE_PLAN_DOC).write_text(
        "Phase 1.3 - Deep research evidence - closed\n",
        encoding="utf-8",
    )
    knowledge = repo_root / "src/polisyos/scientist/agent/knowledge_tools.py"
    knowledge.parent.mkdir(parents=True, exist_ok=True)
    knowledge.write_text(
        "untrusted evidence data\nfetch_safety_events\nsource_quality_signals\n",
        encoding="utf-8",
    )
    projections = repo_root / "src/polisyos/scientist/methods/research_dag/projections.py"
    projections.parent.mkdir(parents=True, exist_ok=True)
    projections.write_text(
        "project_web_evidence_bundle_to_research_dag\nscholar.web_evidence_bundle\n",
        encoding="utf-8",
    )
