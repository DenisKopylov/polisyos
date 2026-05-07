#!/usr/bin/env python3
"""Validate Scientist best-in-class Phase 2.4 reflexive-memory readiness."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase2_4"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-4"

REFERENCE_DOC = Path("docs/reference/scientist/reflexive-memory.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
WAVE2_CONTRACT_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

REQUIRED_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/orchestration/memory/__init__.py"),
    Path("src/polisyos/scientist/orchestration/memory/failure_lessons.py"),
    Path("src/polisyos/scientist/orchestration/memory/applicability.py"),
    Path("src/polisyos/scientist/orchestration/memory/contamination.py"),
    Path("src/polisyos/scientist/orchestration/memory/retrieval.py"),
    Path("src/polisyos/scientist/orchestration/memory/consolidation.py"),
    Path("src/polisyos/scientist/methods/research_dag/projections.py"),
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_4.py"),
    Path("tests/unit/scientist/orchestration/memory/test_failure_lessons.py"),
    Path("tests/unit/scientist/orchestration/memory/test_applicability.py"),
    Path("tests/unit/scientist/orchestration/memory/test_contamination.py"),
    Path("tests/unit/scientist/orchestration/memory/test_retrieval.py"),
    Path("tests/unit/scientist/orchestration/memory/test_consolidation.py"),
    Path("tests/unit/scientist/orchestration/memory/test_research_dag_projection.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase2_4.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "MemoryVisibility",
    "LessonApplicability",
    "ReflexiveMemoryEvent",
    "build_reflexion_memory_recovery_eval_report",
    "format_warning_only_memory_context",
    "hidden eval",
    "hidden benchmark",
    "canary",
    "Research DAG",
    "warnings/anti-patterns",
    "revoked",
    "memory_influence_visible",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.4 - Reflexive memory and failure intelligence",
    "closed",
    "check_scientist_best_in_class_phase2_4.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.4 - Reflexive memory and failure intelligence",
    "reflexive-memory.md",
    "check_scientist_best_in_class_phase2_4.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = ("reflexive-memory.md", "Reflexive memory")
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/reflexive-memory.md",)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _run_phase2_3_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_phase2_3")
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return (
            False,
            {"passes_all": False},
            [f"phase2_3_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "phase2_3.json"
        try:
            exit_code = module.main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--output",
                    str(output_path),
                    "--output-format",
                    "json",
                    "--require-passing",
                ]
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - surfaced in payload.
            return (
                False,
                {"passes_all": False},
                [f"phase2_3_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("phase2_3_gate_failed")
        notes.extend(f"phase2_3:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.scientist.agent.reflexion_evaluator import ReflexionReplayEvaluation
        from polisyos.scientist.orchestration.memory import (
            LessonApplicability,
            MemoryApplicabilityContext,
            MemoryContaminationPolicy,
            MemoryVisibility,
            apply_reflexive_scope,
            assert_lesson_can_influence,
            build_reflexion_memory_recovery_eval_report,
            build_reflexion_recovery_eval_report,
            detect_memory_contamination,
            format_warning_only_memory_context,
            retrieve_reflexive_lessons,
            revoke_lesson,
        )
        from polisyos.scientist.research_dag.projections import (
            project_reflexive_memory_events_to_research_dag,
            validate_memory_influence_dag_attribution,
        )
        from polisyos.scientist.search.lessons import LessonCard, LessonKind, LessonRegistry
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return False, [f"phase2_4_import_failed:{exc.__class__.__name__}:{exc}"]

    lesson = LessonCard(
        lesson_id="lesson_phase2_4",
        kind=LessonKind.FAILURE,
        summary="Do not promote unsupported claims.",
        failure_type="unsupported_claim",
        stage_name="evidence_gate",
        fidelity_level=2,
        candidate_hash="candidate_a",
        source_run_id="source_run",
        task_family="policy",
        domain="tax",
        origin_tenant_hash="tenant_a",
        anti_patterns=["unsupported_claim"],
        remediation_hint="Verify source snippets before promotion.",
    )
    scoped = apply_reflexive_scope(
        lesson,
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        workflow_id="scientist_policy_design",
    )
    context = MemoryApplicabilityContext(
        run_id="run_phase2_4",
        domain="tax",
        workflow_id="scientist_policy_design",
    )
    result = retrieve_reflexive_lessons([scoped], context=context)
    if not result.retrieved_lessons:
        notes.append("memory_retrieval_fixture_missing_lesson")
    if not result.retrieved_lessons[0].applicability.reasons:
        notes.append("memory_retrieval_missing_applicability_reasons")
    if result.retrieved_lessons[0].influence_mode != "warning_anti_pattern":
        notes.append("memory_retrieval_not_warning_only")
    rendered_context = format_warning_only_memory_context(result)
    if "not claim evidence" not in rendered_context:
        notes.append("warning_only_context_not_marked_non_evidence")

    policy = MemoryContaminationPolicy(
        hidden_ref_ids={"hidden-ref"},
        hidden_suite_ids={"hidden-suite"},
        canary_tokens={"CANARY_TOKEN"},
    )
    findings = detect_memory_contamination(
        {
            "summary": "hidden-ref",
            "metadata": {"suite": "hidden-suite"},
            "notes": ["CANARY_TOKEN"],
        },
        policy=policy,
    )
    finding_kinds = {finding.token_kind for finding in findings}
    if not {"artifact_id", "suite_id", "canary"}.issubset(finding_kinds):
        notes.append("hidden_leakage_fixture_not_blocked")

    rejected = retrieve_reflexive_lessons(
        [scoped.model_copy(update={"metadata": {"hidden_suite_id": "hidden-suite"}})],
        context=context,
        contamination_policy=policy,
    )
    if rejected.retrieved_lessons or not rejected.rejected_lessons:
        notes.append("contaminated_lesson_not_rejected")

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        registry = LessonRegistry(
            root=tmp_path / "lessons",
            store=FileSystemCAS(tmp_path / "cas"),
        )
        registry.record_local(scoped)
        revocation = revoke_lesson(
            registry,
            lesson_id=scoped.lesson_id,
            reason="source_withdrawn",
            run_id=context.run_id,
        )
        try:
            assert_lesson_can_influence(revocation.applicability)
        except ValueError:
            pass
        else:
            notes.append("revocation_fixture_still_allows_influence")

    dag = project_reflexive_memory_events_to_research_dag(result.events, run_id=context.run_id)
    if validate_memory_influence_dag_attribution(result.events, dag):
        notes.append("memory_dag_projection_missing_attribution")
    missing = validate_memory_influence_dag_attribution(
        result.events,
        project_reflexive_memory_events_to_research_dag([], run_id=context.run_id),
    )
    if not missing or not str(missing[0]).startswith("memory_influence_missing_dag_node:"):
        notes.append("memory_missing_dag_attribution_not_reported")

    report = build_reflexion_recovery_eval_report(
        run_id="run_memory_eval",
        held_out_scenario_count=20,
        baseline_recovery_rate=0.4,
        memory_recovery_rate=0.55,
    )
    if not report.improved or report.recovery_delta <= 0.0:
        notes.append("recovery_eval_fixture_not_improved")
    replay_report = build_reflexion_memory_recovery_eval_report(
        run_id="run_memory_eval",
        baseline_evaluation=ReflexionReplayEvaluation(sample_count=4, pass_rate=0.25),
        memory_evaluation=ReflexionReplayEvaluation(sample_count=4, pass_rate=0.5),
    )
    if not replay_report.improved or replay_report.held_out_scenario_count != 4:
        notes.append("reflexion_replay_recovery_fixture_not_improved")
    try:
        LessonApplicability(lesson_id="lesson_bad", applies=True, reasons=[])
    except ValueError:
        pass
    else:
        notes.append("applicability_without_reasons_not_blocked")
    revoked_applicability = LessonApplicability(
        lesson_id="revoked_lesson",
        applies=True,
        reasons=["revoked"],
    )
    try:
        format_warning_only_memory_context(
            type(
                "FakeResult",
                (),
                {
                    "retrieved_lessons": [
                        type(
                            "FakeLesson",
                            (),
                            {
                                "lesson_id": "revoked_lesson",
                                "applicability": revoked_applicability,
                                "anti_patterns": [],
                                "remediation_hint": "",
                            },
                        )()
                    ]
                },
            )()
        )
    except ValueError:
        pass
    else:
        notes.append("revoked_prompt_context_not_blocked")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase2_3_ok, phase2_3_payload, phase2_3_notes = _run_phase2_3_gate(repo_root)
    notes.extend(phase2_3_notes)
    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    missing_reference_tokens = _missing_tokens(
        repo_root,
        REFERENCE_DOC,
        REFERENCE_TOKENS,
        "missing_reference_token",
    )
    notes.extend(missing_reference_tokens)
    missing_plan_tokens = _missing_tokens(
        repo_root,
        ACTIVE_PLAN_DOC,
        PLAN_TOKENS,
        "missing_active_plan_token",
    )
    notes.extend(missing_plan_tokens)
    missing_readiness_tokens = _missing_tokens(
        repo_root,
        READINESS_DOC,
        READINESS_TOKENS,
        "missing_readiness_token",
    )
    notes.extend(missing_readiness_tokens)
    missing_inventory_tokens = _missing_tokens(
        repo_root,
        INVENTORY_DOC,
        ("reflexive-memory.md", "check_scientist_best_in_class_phase2_4.py"),
        "missing_inventory_token",
    )
    notes.extend(missing_inventory_tokens)
    missing_index_tokens = _missing_tokens(
        repo_root,
        SCIENTIST_INDEX_DOC,
        INDEX_TOKENS,
        "missing_scientist_index_token",
    )
    notes.extend(missing_index_tokens)
    missing_wave2_tokens = _missing_tokens(
        repo_root,
        WAVE2_CONTRACT_DOC,
        ("Phase 2.4 - Reflexive memory and failure intelligence", "closed"),
        "missing_wave2_contract_token",
    )
    notes.extend(missing_wave2_tokens)
    missing_mkdocs_tokens = _missing_tokens(
        repo_root,
        MKDOCS_CONFIG,
        MKDOCS_TOKENS,
        "missing_mkdocs_token",
    )
    notes.extend(missing_mkdocs_tokens)

    category_results = {
        "deliverables_exist": not missing_files,
        "phase2_3_gate_green": phase2_3_ok,
        "memory_contracts_validate": import_ok,
        "reference_doc_complete": not missing_reference_tokens,
        "active_plan_updated": not missing_plan_tokens,
        "readiness_doc_updated": not missing_readiness_tokens,
        "inventory_doc_updated": not missing_inventory_tokens,
        "scientist_index_updated": not missing_index_tokens,
        "wave2_contract_updated": not missing_wave2_tokens,
        "mkdocs_nav_updated": not missing_mkdocs_tokens,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "phase2_3_gate_report": phase2_3_payload,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    note_list = list(payload.get("notes", []))
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Phase 2.4 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.4 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_4",
            )
            for note in note_list
        ),
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
    result = _result(payload)
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
