#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 1.2 research DAG sidecar."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools._lib.fs import atomic_write_text
from tools._lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase1_2"
TOOL_NAME = "ci.check-scientist-best-in-class-phase1-2"

RESEARCH_DAG_PACKAGE = Path("src/polisyos/scientist/research_dag")
REFERENCE_DOC = Path("docs/reference/scientist/research-dag.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
PUBLIC_DAG_FIXTURE = Path("tests/scientist/research_dag/fixtures/public_dag.json")
REQUIRED_PACKAGE_FILES: tuple[Path, ...] = (
    RESEARCH_DAG_PACKAGE / "__init__.py",
    RESEARCH_DAG_PACKAGE / "models.py",
    RESEARCH_DAG_PACKAGE / "builder.py",
    RESEARCH_DAG_PACKAGE / "persistence.py",
    RESEARCH_DAG_PACKAGE / "replay.py",
    RESEARCH_DAG_PACKAGE / "diff.py",
    RESEARCH_DAG_PACKAGE / "projections.py",
)
REQUIRED_TEST_FILES: tuple[Path, ...] = (
    Path("tests/scientist/research_dag/test_models.py"),
    Path("tests/scientist/research_dag/test_builder.py"),
    Path("tests/scientist/research_dag/test_persistence.py"),
    Path("tests/scientist/research_dag/test_replay.py"),
    Path("tests/scientist/research_dag/test_diff.py"),
    Path("tests/scientist/research_dag/test_projections.py"),
    Path("tests/scientist/research_dag/test_workflow_integration.py"),
    Path("tests/tools/test_scientist_best_in_class_phase1_2.py"),
)
REQUIRED_NEGATIVE_TEST_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("tests/scientist/research_dag/test_builder.py"): (
        "hidden_benchmark",
        "prompt_injection_candidate",
        "not in dag_json",
    ),
    Path("tests/scientist/research_dag/test_models.py"): (
        "orphaned",
        "SUPPORTS",
        "acyclic",
        "hidden artifact ref",
    ),
    Path("tests/scientist/research_dag/test_persistence.py"): ("legacy_missing",),
}
INTEGRATION_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/engine/executor.py"),
    Path("src/polisyos/scientist/engine/trace_attributes.py"),
    Path("src/polisyos/scientist/engine/checkpoint.py"),
    Path("src/polisyos/scientist/provenance/run_dag.py"),
    Path("src/polisyos/scientist/agent/tools/tool_loop.py"),
    Path("src/polisyos/scientist/workflows/builder.py"),
    Path("src/polisyos/scientist/nodes/builtins/planning/plan_policy_request.py"),
    Path("src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py"),
    Path("src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py"),
)
FORBIDDEN_PUBLIC_FIXTURE_TOKENS: tuple[str, ...] = (
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "private_eval",
    "raw_transcript",
    "system prompt",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _import_and_validate_research_dag_fixture(repo_root: Path) -> tuple[bool, list[str]]:
    notes: list[str] = []
    sys.path.insert(0, str(repo_root / "src"))
    try:
        from polisyos.scientist.research_dag import (
            ResearchDAGArtifact,
            ResearchDAGBuilder,
            ResearchNodeType,
            diff_research_dags,
            replay_research_path,
        )
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"research_dag_package_import_failed:{exc.__class__.__name__}:{exc}"]

    try:
        builder = ResearchDAGBuilder(run_id="phase1_2_gate", workflow_id="scientist_policy_design")
        builder.add_node(
            node_type=ResearchNodeType.QUESTION,
            producer="gate",
            summary="Validate ResearchDAGArtifact.",
        )
        old = builder.artifact()
        replay = replay_research_path(old)
        new = ResearchDAGArtifact.model_validate(old.model_dump(mode="python"))
        diff_research_dags(old, new)
        if replay.research_dag_status != "available":
            notes.append("research_dag_replay_status_not_available")
        fixture = repo_root / PUBLIC_DAG_FIXTURE
        if fixture.is_file():
            ResearchDAGArtifact.model_validate(json.loads(_read_text(fixture)))
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        notes.append(f"research_dag_fixture_validation_failed:{exc.__class__.__name__}:{exc}")
    return not notes, notes


def _public_fixture_has_no_hidden_tokens(repo_root: Path) -> bool:
    fixture = repo_root / PUBLIC_DAG_FIXTURE
    if not fixture.is_file():
        return False
    text = _read_text(fixture).lower()
    return not any(token in text for token in FORBIDDEN_PUBLIC_FIXTURE_TOKENS)


def _build_payload(repo_root: Path) -> dict[str, object]:
    notes: list[str] = []
    missing_package_files = [
        str(path) for path in REQUIRED_PACKAGE_FILES if not (repo_root / path).is_file()
    ]
    missing_tests = [str(path) for path in REQUIRED_TEST_FILES if not (repo_root / path).is_file()]
    missing_integrations = [
        str(path) for path in INTEGRATION_FILES if not (repo_root / path).is_file()
    ]
    notes.extend(f"missing_package_file:{path}" for path in missing_package_files)
    notes.extend(f"missing_test_file:{path}" for path in missing_tests)
    notes.extend(f"missing_integration_file:{path}" for path in missing_integrations)

    missing_negative_test_tokens: list[str] = []
    for path, tokens in REQUIRED_NEGATIVE_TEST_TOKENS.items():
        absolute = repo_root / path
        if not absolute.is_file():
            missing_negative_test_tokens.append(f"{path}:<file>")
            continue
        text = _read_text(absolute)
        missing_negative_test_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_required_negative_test_token:{token}"
        for token in missing_negative_test_tokens
    )

    import_ok, import_notes = _import_and_validate_research_dag_fixture(repo_root)
    notes.extend(import_notes)

    reference_exists = (repo_root / REFERENCE_DOC).is_file()
    if not reference_exists:
        notes.append(f"missing_reference_doc:{REFERENCE_DOC}")
    reference_tokens = (
        "ResearchDAGArtifact",
        "research_dag_ref",
        "DAG replay",
        "DAG diff",
        "untrusted web/page text",
    )
    missing_reference_tokens = [
        token for token in reference_tokens if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    notes.extend(f"missing_reference_token:{token}" for token in missing_reference_tokens)

    missing_integration_tokens: list[str] = []
    for path in INTEGRATION_FILES:
        absolute = repo_root / path
        if not absolute.is_file():
            continue
        text = _read_text(absolute)
        if "research_dag" not in text and "ResearchDAG" not in text:
            missing_integration_tokens.append(str(path))
    notes.extend(
        f"missing_research_dag_integration:{path}" for path in missing_integration_tokens
    )

    public_fixture_clean = _public_fixture_has_no_hidden_tokens(repo_root)
    if not (repo_root / PUBLIC_DAG_FIXTURE).is_file():
        notes.append(f"missing_public_dag_fixture:{PUBLIC_DAG_FIXTURE}")
    elif not public_fixture_clean:
        notes.append("public_dag_fixture_contains_hidden_eval_or_raw_transcript")

    active_plan_tokens = ("1.2", "Research DAG", "closed")
    active_plan_missing = [
        token for token in active_plan_tokens if not _contains(repo_root / ACTIVE_PLAN_DOC, token)
    ]
    notes.extend(f"missing_active_plan_token:{token}" for token in active_plan_missing)

    category_results = {
        "package_files_exist": not missing_package_files,
        "models_import_and_validate": import_ok,
        "reference_doc_complete": reference_exists and not missing_reference_tokens,
        "tests_present": not missing_tests,
        "negative_tests_cover_required_cases": not missing_negative_test_tokens,
        "integration_targets_project_dag": not missing_integrations
        and not missing_integration_tokens,
        "public_fixture_redacted": public_fixture_clean,
        "active_plan_updated": not active_plan_missing,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "required_package_files": [str(path) for path in REQUIRED_PACKAGE_FILES],
        "required_test_files": [str(path) for path in REQUIRED_TEST_FILES],
        "required_negative_test_tokens": {
            str(path): list(tokens)
            for path, tokens in REQUIRED_NEGATIVE_TEST_TOKENS.items()
        },
        "integration_files": [str(path) for path in INTEGRATION_FILES],
        "public_dag_fixture": str(PUBLIC_DAG_FIXTURE),
        "notes": notes,
    }


def _phase1_2_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist best-in-class Phase 1.2 research DAG is complete"
        if status == "ok"
        else "Scientist best-in-class Phase 1.2 research DAG is incomplete"
    )
    messages = tuple(
        ToolMessage(
            level="error" if status == "failed" else "info",
            message=str(note),
            rule_id="SCIENTIST_BEST_IN_CLASS_PHASE1_2",
        )
        for note in note_list
    )
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=summary,
        exit_code=0 if status == "ok" else 1,
        messages=messages,
        data=payload,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--require-passing", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    payload = _build_payload(repo_root)
    result = _phase1_2_result(payload)

    rendered = (
        json.dumps(payload, indent=2, sort_keys=True)
        if args.output_format == "json"
        else format_tool_result(result)
    )
    if args.output is not None:
        atomic_write_text(args.output, rendered + "\n")
    else:
        print(rendered)
    return 0 if result.exit_code == 0 or not args.require_passing else result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
