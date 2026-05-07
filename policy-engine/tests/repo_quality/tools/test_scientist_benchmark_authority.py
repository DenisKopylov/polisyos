from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_benchmark_authority as gate

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_scientist_benchmark_authority_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "benchmark-authority-gate.json"

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
    assert payload["assessment_id"] == "scientist_benchmark_authority_phase1_5"
    assert payload["passes_all"] is True
    assert payload["category_results"]["models_import_and_validate"] is True
    assert payload["category_results"]["agent_and_frontier_shadow_integration_present"] is True


def test_scientist_benchmark_authority_gate_fails_without_hidden_split_doc(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path, omitted_doc_entry="`hidden_holdout`")
    output_json = tmp_path / "benchmark-authority-gate.json"

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
    assert "missing_split_doc_token:`hidden_holdout`" in payload["notes"]


def _write_minimal_repo(repo_root: Path, *, omitted_doc_entry: str) -> None:
    for path in gate.REQUIRED_PACKAGE_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        content = "phase1_5\n"
        if path.name == "promotion.py":
            content += (
                "benchmark_authority_verdict\n"
                "require_benchmark_authority\n"
                "benchmark_authority_not_allowed\n"
            )
        if path.name == "frontier_runtime.py":
            content += (
                "require_benchmark_authority\n"
                "benchmark_authority_default_enable_allowed\n"
            )
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
            token
            for token in gate.REQUIRED_SPLIT_DOC_TOKENS
            if token != omitted_doc_entry
        ],
    ]
    (repo_root / gate.REFERENCE_DOC).write_text(
        "\n".join(reference_tokens),
        encoding="utf-8",
    )
    (repo_root / gate.ACTIVE_PLAN_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.ACTIVE_PLAN_DOC).write_text(
        "1.5\nBenchmark authority\nclosed\n",
        encoding="utf-8",
    )
