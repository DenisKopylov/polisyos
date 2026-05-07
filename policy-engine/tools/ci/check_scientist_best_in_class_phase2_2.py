#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 2.2 Research DAG replay surface."""

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

ASSESSMENT_ID = "scientist_best_in_class_phase2_2"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-2"

REFERENCE_DOC = Path("docs/reference/scientist/research-dag-replay.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
WAVE2_CONTRACT_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

REQUIRED_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/methods/research_dag/replay.py"),
    Path("src/polisyos/scientist/methods/research_dag/comparison.py"),
    Path("src/polisyos/scientist/methods/research_dag/invalidation.py"),
    Path("src/polisyos/scientist/methods/research_dag/diff.py"),
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_2.py"),
    Path("tests/unit/scientist/methods/research_dag/test_replay_plan.py"),
    Path("tests/unit/scientist/methods/research_dag/test_comparison.py"),
    Path("tests/unit/scientist/methods/research_dag/test_invalidation.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase2_2.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "ResearchReplayPlan",
    "ReplayMode",
    "ResearchTrajectoryComparisonReport",
    "SourceInvalidationEvent",
    "legacy_minimal",
    "changed_queries",
    "changed_sources",
    "changed_snippets",
    "changed_claim_ids",
    "changed_governance_outcomes",
    "marked_stale",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.2 - Research DAG replay and comparison",
    "closed",
    "check_scientist_best_in_class_phase2_2.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.2 - Research DAG replay and comparison",
    "research-dag-replay.md",
    "check_scientist_best_in_class_phase2_2.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = (
    "research-dag-replay.md",
    "Research DAG replay",
)
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/research-dag-replay.md",)
INTEGRATION_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("src/polisyos/scientist/methods/research_dag/replay.py"): (
        "ResearchReplayPlan",
        "ReplayMode",
        "legacy_minimal",
        "public_replay_export",
    ),
    Path("src/polisyos/scientist/methods/research_dag/comparison.py"): (
        "ResearchTrajectoryComparisonReport",
        "changed_queries",
        "changed_snippets",
    ),
    Path("src/polisyos/scientist/methods/research_dag/invalidation.py"): (
        "SourceInvalidationEvent",
        "propagate_source_invalidation",
        "ClaimLifecycleAction.MARKED_STALE",
    ),
    Path("src/polisyos/scientist/evidence/claims/lifecycle.py"): ("MARKED_STALE",),
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _run_phase2_1_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_phase2_1")
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return (
            False,
            {"passes_all": False},
            [f"phase2_1_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "phase2_1.json"
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
        except Exception as exc:  # pragma: no cover - surfaced in gate payload.
            return (
                False,
                {"passes_all": False},
                [f"phase2_1_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("phase2_1_gate_failed")
        notes.extend(f"phase2_1:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.research_dag.builder import ResearchDAGBuilder
        from polisyos.scientist.research_dag.comparison import (
            compare_research_trajectories,
            public_comparison_export,
        )
        from polisyos.scientist.research_dag.invalidation import (
            SourceInvalidationEvent,
            propagate_source_invalidation,
        )
        from polisyos.scientist.research_dag.models import (
            ResearchDAGArtifact,
            ResearchEdgeType,
            ResearchNodeType,
        )
        from polisyos.scientist.research_dag.replay import (
            ReplayMode,
            plan_research_replay,
            public_replay_export,
        )
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"phase2_2_import_failed:{exc.__class__.__name__}:{exc}"]

    def ref(seed: str, *, kind: str = "scientist.source") -> ArtifactRef:
        return ArtifactRef(
            artifact_id="sha256:" + seed * 64,
            kind=kind,
            media_type="application/json",
        )

    source_old = ref("1")
    source_new = ref("2")
    dag_ref = ref("3", kind="scientist.research_dag")

    def dag(
        run_id: str,
        query: str,
        source: ArtifactRef,
        snippet: str,
        claim: str,
        verdict: str,
    ) -> ResearchDAGArtifact:
        builder = ResearchDAGBuilder(run_id=run_id, workflow_id="scientist_policy_design")
        q = builder.add_node(
            node_type=ResearchNodeType.QUESTION,
            producer="planner",
            summary=query,
            metadata={"query": query},
        )
        s = builder.add_node(
            node_type=ResearchNodeType.SOURCE_READ,
            producer="safe_fetch",
            summary="Read source.",
            artifact_refs=[source],
        )
        e = builder.add_node(
            node_type=ResearchNodeType.EXTRACTION,
            producer="extractor",
            summary="Extract snippet.",
            metadata={"snippet_id": snippet},
            claim_ids=[claim],
        )
        g = builder.add_node(
            node_type=ResearchNodeType.GOVERNANCE,
            producer="governance",
            summary=f"Governance {verdict}",
            metadata={"verdict": verdict},
        )
        builder.add_edge(
            source_node_id=q.node_id,
            target_node_id=s.node_id,
            edge_type=ResearchEdgeType.DEPENDS_ON,
        )
        builder.add_edge(
            source_node_id=s.node_id,
            target_node_id=e.node_id,
            edge_type=ResearchEdgeType.SUPPORTS,
            claim_ids=[claim],
        )
        builder.add_edge(
            source_node_id=e.node_id,
            target_node_id=g.node_id,
            edge_type=ResearchEdgeType.GATES,
            claim_ids=[claim],
        )
        return builder.artifact()

    old = dag("old", "old query", source_old, "snippet_old", "claim_old", "warn")
    new = dag("new", "new query", source_new, "snippet_new", "claim_new", "pass")
    plan = plan_research_replay(new, dag_ref=dag_ref, mode=ReplayMode.PINNED_INPUT_REPLAY)
    if plan.live_fetch_required:
        notes.append("pinned_replay_requires_live_fetch")
    if plan.required_artifact_refs != [source_new]:
        notes.append("pinned_replay_missing_required_source")
    report = compare_research_trajectories(old, new)
    if not report.changed_sources:
        notes.append("comparison_missing_changed_sources")
    if not report.changed_claim_ids:
        notes.append("comparison_missing_changed_claims")
    if not report.changed_governance_outcomes:
        notes.append("comparison_missing_changed_governance")
    if not report.changed_queries or not report.changed_snippets:
        notes.append("comparison_missing_query_or_snippet_diff")

    hidden_ref = ref("9", kind="scientist.hidden_benchmark.answer")
    hidden_builder = ResearchDAGBuilder(run_id="hidden", workflow_id="scientist_policy_design")
    hidden_builder.add_node(
        node_type=ResearchNodeType.SOURCE_READ,
        producer="hidden_eval",
        summary="hidden_benchmark answer read.",
        artifact_refs=[hidden_ref],
    )
    hidden_replay_json = json.dumps(public_replay_export(hidden_builder.artifact()))
    hidden_comparison_json = json.dumps(
        public_comparison_export(compare_research_trajectories(old, hidden_builder.artifact()))
    )
    if (
        str(hidden_ref.artifact_id) in hidden_replay_json
        or "hidden_benchmark" in hidden_replay_json
        or "hidden_eval" in hidden_replay_json
    ):
        notes.append("public_replay_leaks_hidden_ref")
    if "hidden_benchmark" in hidden_comparison_json or "hidden_eval" in hidden_comparison_json:
        notes.append("public_comparison_leaks_hidden_ref")

    event = SourceInvalidationEvent(
        event_id="source_invalid_1",
        source_ref=source_new,
        invalidation_type="stale",
        reason="Source TTL expired.",
    )
    impact = propagate_source_invalidation(new, event)
    if "claim_new" not in impact.stale_claim_ids:
        notes.append("source_invalidation_missing_dependent_claim")

    return not notes, notes


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase2_1_ok, phase2_1_payload, phase2_1_notes = _run_phase2_1_gate(repo_root)
    notes.extend(phase2_1_notes)

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
        ("research-dag-replay.md", "check_scientist_best_in_class_phase2_2.py"),
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
        ("Phase 2.2 - Research DAG replay and comparison", "closed"),
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

    missing_integration_tokens: list[str] = []
    for path, tokens in INTEGRATION_TOKENS.items():
        text = _read_text(repo_root / path) if (repo_root / path).is_file() else ""
        missing_integration_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_phase2_2_integration_token:{token}" for token in missing_integration_tokens
    )

    category_results = {
        "deliverables_exist": not missing_files,
        "phase2_1_gate_green": phase2_1_ok,
        "replay_comparison_invalidation_validate": import_ok,
        "reference_doc_complete": not missing_reference_tokens,
        "active_plan_updated": not missing_plan_tokens,
        "readiness_doc_updated": not missing_readiness_tokens,
        "inventory_doc_updated": not missing_inventory_tokens,
        "scientist_index_updated": not missing_index_tokens,
        "wave2_contract_updated": not missing_wave2_tokens,
        "mkdocs_nav_updated": not missing_mkdocs_tokens,
        "integration_tokens_present": not missing_integration_tokens,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "phase2_1_gate_report": phase2_1_payload,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Phase 2.2 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.2 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_2",
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
