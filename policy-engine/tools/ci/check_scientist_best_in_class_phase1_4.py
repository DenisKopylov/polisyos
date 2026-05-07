#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 1.4 agent promotion surface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase1_4"
TOOL_NAME = "ci.check-scientist-best-in-class-phase1-4"

REFERENCE_DOC = Path("docs/reference/scientist/agent-capability-promotion.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
REQUIRED_PACKAGE_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/agent/runtime_capabilities.py"),
    Path("src/polisyos/scientist/agent/promotion.py"),
    Path("src/polisyos/scientist/agent/tool_contracts.py"),
    Path("src/polisyos/scientist/agent/supervisor_eval.py"),
    Path("src/polisyos/scientist/orchestration/engine/frontier_runtime.py"),
)
REQUIRED_TEST_FILES: tuple[Path, ...] = (
    Path("tests/unit/scientist/agent/test_runtime_capabilities.py"),
    Path("tests/unit/scientist/agent/test_tool_contracts.py"),
    Path("tests/unit/scientist/agent/test_supervisor_eval.py"),
    Path("tests/unit/scientist/agent/test_promotion.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase1_4.py"),
)
CAPABILITY_IDS: tuple[str, ...] = (
    "tool_loop",
    "supervisor_worker",
    "deep_research_subgraph",
    "tree_of_thought",
    "lats_mcts",
    "learned_routing",
    "learned_voi",
    "same_model_fanout",
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "AgentCapabilityPromotionReport",
    "AgentPromotionCoverageRecord",
    "FrontierCapabilityStatus",
    "context_memory",
    "provider_behavior",
    "missing_context_memory_eval_ref",
    "missing_provider_behavior_eval_ref",
    "offline_validation_ref",
    "benchmark_pack_ref",
    "ToolContractSummary",
    "SupervisorPromotionEvaluation",
)
NEGATIVE_TEST_TOKENS: dict[Path, tuple[str, ...]] = {
    Path("tests/unit/scientist/agent/test_promotion.py"): (
        "missing_benchmark_pack_ref",
        "tool_schema_not_ready",
        "missing_supervisor_handoff_eval_ref",
        "missing_citation_faithfulness_eval_ref",
    ),
    Path("tests/unit/scientist/agent/test_tool_contracts.py"): (
        "schema_allows_additional_properties",
        "runtime_missing_response_cap",
    ),
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    sys.path.insert(0, str(repo_root / "src"))
    notes: list[str] = []
    try:
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.agent.promotion import (
            build_agent_capability_promotion_report,
            project_agent_promotion_to_frontier_statuses,
        )
        from polisyos.scientist.agent.runtime_capabilities import (
            AgentCapabilityId,
            list_agent_capabilities,
        )
        from polisyos.scientist.agent.tool_contracts import summarize_tool_contracts
        from polisyos.scientist.agent.tools.schema import ToolDefinition
        from polisyos.scientist.orchestration.engine.frontier_runtime import FrontierCapabilityStatus
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"phase1_4_import_failed:{exc.__class__.__name__}:{exc}"]

    observed_ids = [item.capability_id.value for item in list_agent_capabilities()]
    if observed_ids != list(CAPABILITY_IDS):
        notes.append(f"capability_registry_mismatch:{observed_ids}")

    strict_summary = summarize_tool_contracts(
        [
            ToolDefinition(
                name="phase1_4_gate_tool",
                description="Gate fixture tool",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                timeout_s=5.0,
                response_max_chars=4096,
            )
        ]
    )
    offline_ref = ArtifactRef(
        artifact_id=f"sha256:{'a' * 64}",
        kind="scientist.agent.offline_validation",
        media_type="application/json",
    )
    blocked = build_agent_capability_promotion_report(
        default_enable_requested=True,
        default_enable_capability_ids=[AgentCapabilityId.TOOL_LOOP],
        offline_validation_ref=offline_ref,
        tool_contract_summary=strict_summary,
    )
    if blocked.default_enable_eligible:
        notes.append("default_enable_fixture_without_benchmark_did_not_block")
    if "missing_benchmark_pack_ref" not in blocked.blockers:
        notes.append("missing_benchmark_pack_blocker_absent")

    statuses = project_agent_promotion_to_frontier_statuses(blocked)
    if set(statuses) != set(CAPABILITY_IDS):
        notes.append(f"frontier_projection_mismatch:{sorted(statuses)}")
    if not all(isinstance(status, FrontierCapabilityStatus) for status in statuses.values()):
        notes.append("frontier_status_values_not_aligned")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, object]:
    notes: list[str] = []
    missing_package_files = [
        str(path) for path in REQUIRED_PACKAGE_FILES if not (repo_root / path).is_file()
    ]
    missing_tests = [str(path) for path in REQUIRED_TEST_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_package_file:{path}" for path in missing_package_files)
    notes.extend(f"missing_test_file:{path}" for path in missing_tests)

    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    reference_exists = (repo_root / REFERENCE_DOC).is_file()
    if not reference_exists:
        notes.append(f"missing_reference_doc:{REFERENCE_DOC}")
    missing_reference_tokens = [
        token for token in REFERENCE_TOKENS if not _contains(repo_root / REFERENCE_DOC, token)
    ]
    notes.extend(f"missing_reference_token:{token}" for token in missing_reference_tokens)

    missing_doc_capability_ids = [
        capability_id
        for capability_id in CAPABILITY_IDS
        if not _contains(repo_root / REFERENCE_DOC, f"`{capability_id}`")
    ]
    notes.extend(f"missing_doc_capability_id:{item}" for item in missing_doc_capability_ids)

    missing_negative_test_tokens: list[str] = []
    for path, tokens in NEGATIVE_TEST_TOKENS.items():
        absolute = repo_root / path
        if not absolute.is_file():
            missing_negative_test_tokens.append(f"{path}:<file>")
            continue
        text = _read_text(absolute)
        missing_negative_test_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_required_negative_test_token:{token}" for token in missing_negative_test_tokens
    )

    integration_tokens = {
        Path("src/polisyos/scientist/orchestration/engine/frontier_runtime.py"): (
            "summarize_agent_promotion_frontier_status",
        ),
        Path("src/polisyos/scientist/agent/promotion.py"): (
            "AgentCapabilityPromotionReport",
            "AgentPromotionCoverageDomain",
            "AgentPromotionCoverageRecord",
            "project_agent_promotion_to_frontier_statuses",
            "default_enable_capability_ids",
        ),
    }
    missing_integration_tokens: list[str] = []
    for path, tokens in integration_tokens.items():
        text = _read_text(repo_root / path) if (repo_root / path).is_file() else ""
        missing_integration_tokens.extend(
            f"{path}:{token}" for token in tokens if token not in text
        )
    notes.extend(
        f"missing_phase1_4_integration_token:{token}" for token in missing_integration_tokens
    )

    active_plan_tokens = ("1.4", "Agent and tool runtime promotion gates", "closed")
    active_plan_missing = [
        token for token in active_plan_tokens if not _contains(repo_root / ACTIVE_PLAN_DOC, token)
    ]
    notes.extend(f"missing_active_plan_token:{token}" for token in active_plan_missing)

    category_results = {
        "package_files_exist": not missing_package_files,
        "tests_present": not missing_tests,
        "models_import_and_validate": import_ok,
        "reference_doc_complete": (
            reference_exists and not missing_reference_tokens and not missing_doc_capability_ids
        ),
        "negative_tests_cover_required_cases": not missing_negative_test_tokens,
        "frontier_projection_present": not missing_integration_tokens,
        "active_plan_updated": not active_plan_missing,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "required_package_files": [str(path) for path in REQUIRED_PACKAGE_FILES],
        "required_test_files": [str(path) for path in REQUIRED_TEST_FILES],
        "capability_ids": list(CAPABILITY_IDS),
        "notes": notes,
    }


def _phase1_4_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist best-in-class Phase 1.4 agent promotion surface is complete"
        if status == "ok"
        else "Scientist best-in-class Phase 1.4 agent promotion surface is incomplete"
    )
    messages = tuple(
        ToolMessage(
            level="error" if status == "failed" else "info",
            message=str(note),
            rule_id="SCIENTIST_BEST_IN_CLASS_PHASE1_4",
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
    result = _phase1_4_result(payload)
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
