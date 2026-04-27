from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_best_in_class_phase1_2 as gate

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_scientist_best_in_class_phase1_2_gate_passes_repo(tmp_path: Path) -> None:
    output_json = tmp_path / "phase1-2-gate.json"

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
    assert payload["assessment_id"] == "scientist_best_in_class_phase1_2"
    assert payload["passes_all"] is True
    assert payload["category_results"]["models_import_and_validate"] is True
    assert payload["category_results"]["integration_targets_project_dag"] is True
    assert payload["category_results"]["public_fixture_redacted"] is True


def test_scientist_best_in_class_phase1_2_gate_fails_on_missing_dag_integration(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path, omit_research_dag_in_executor=True)
    output_json = tmp_path / "phase1-2-gate.json"

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
        "missing_research_dag_integration:src/polisyos/scientist/engine/executor.py"
        in payload["notes"]
    )


def _write_minimal_repo(repo_root: Path, *, omit_research_dag_in_executor: bool) -> None:
    for path in gate.REQUIRED_PACKAGE_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "models.py":
            absolute.write_text(
                "\n".join(
                    [
                        "from enum import Enum",
                        "from pydantic import BaseModel",
                        "class ResearchNodeType(str, Enum):",
                        "    QUESTION = 'question'",
                        "class ResearchDAGArtifact(BaseModel):",
                        "    run_id: str",
                    ]
                ),
                encoding="utf-8",
            )
        elif path.name == "__init__.py":
            absolute.write_text(
                "\n".join(
                    [
                        "class ResearchDAGBuilder:",
                        "    def __init__(self, **kwargs): self.kwargs = kwargs",
                        "    def add_node(self, **kwargs): return None",
                        "    def artifact(self): return type('D', (), {'model_dump': lambda self, mode=None: {'run_id': 'x'}})()",
                        "class ResearchNodeType:",
                        "    QUESTION = 'question'",
                        "class ResearchDAGArtifact:",
                        "    @classmethod",
                        "    def model_validate(cls, value): return value",
                        "def replay_research_path(value): return type('R', (), {'research_dag_status': 'available'})()",
                        "def diff_research_dags(old, new): return None",
                    ]
                ),
                encoding="utf-8",
            )
        else:
            absolute.write_text("# research_dag stub\n", encoding="utf-8")

    for path in gate.REQUIRED_TEST_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_text("# test stub\n", encoding="utf-8")

    for path, tokens in gate.REQUIRED_NEGATIVE_TEST_TOKENS.items():
        absolute = repo_root / path
        existing = absolute.read_text(encoding="utf-8") if absolute.is_file() else ""
        absolute.write_text(existing + "\n".join(tokens) + "\n", encoding="utf-8")

    for path in gate.INTEGRATION_FILES:
        absolute = repo_root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        content = ""
        if not (omit_research_dag_in_executor and path.name == "executor.py"):
            content = "research_dag_ref\n"
        absolute.write_text(content, encoding="utf-8")

    (repo_root / gate.REFERENCE_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.REFERENCE_DOC).write_text(
        "\n".join(
            [
                "# Research DAG",
                "ResearchDAGArtifact",
                "research_dag_ref",
                "DAG replay",
                "DAG diff",
                "untrusted web/page text",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / gate.ACTIVE_PLAN_DOC).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / gate.ACTIVE_PLAN_DOC).write_text(
        "Phase 1.2 - Research DAG - closed\n",
        encoding="utf-8",
    )
    fixture = repo_root / gate.PUBLIC_DAG_FIXTURE
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text('{"run_id":"fixture","workflow_id":"scientist_policy_design"}\n', encoding="utf-8")
