#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 1.0 reconciliation docs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools._lib.fs import atomic_write_text
from tools._lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase1_0"
TOOL_NAME = "ci.check-scientist-best-in-class-phase1-0"

READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")

ALLOWED_HISTORICAL_STATUSES = frozenset(
    {
        "closed",
        "superseded",
        "still_gated",
        "research_first",
        "not_in_scope",
    }
)

REQUIRED_CAPABILITY_IDS: tuple[str, ...] = (
    "workflow_runtime",
    "builtin_nodes",
    "governance_pipeline",
    "causal_validity",
    "policy_design",
    "policy_verified",
    "discovery_runtime",
    "search_funnel",
    "benchmark_frontier_runtime",
    "agent_tool_runtime",
    "deep_research_evidence",
    "replay_provenance",
    "validation_fairness_calibration",
    "autotune_search",
    "cross_graph_evidence",
    "llm_gateway",
    "human_oversight",
    "claim_evidence_readiness_spine",
    "research_dag",
    "voi_reflexive_memory_challenge_factory",
    "active_plan_governance",
)

HISTORICAL_PLAN_SPECS: tuple[tuple[Path, str, re.Pattern[str]], ...] = (
    (
        Path("docs/SCIENTIST_AUDIT_REMEDIATION_PLAN.md"),
        "SCIENTIST_AUDIT_REMEDIATION_PLAN",
        re.compile(r"^### (WS-\d+[A-Z])\.\s+(.+)$", re.MULTILINE),
    ),
    (
        Path("docs/archive/plans/SCIENTIST_SOTA_ROADMAP.md"),
        "SCIENTIST_SOTA_ROADMAP",
        re.compile(r"^### (WS\d+\.\d+) (?:\u2014|-) (.+)$", re.MULTILINE),
    ),
    (
        Path("docs/archive/plans/SCIENTIST_AGENT_SOTA_ROADMAP.md"),
        "SCIENTIST_AGENT_SOTA_ROADMAP",
        re.compile(r"^### Phase (\d+):\s+(.+)$", re.MULTILINE),
    ),
    (
        Path("docs/archive/plans/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md"),
        "SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT",
        re.compile(r"^### Phase ([A-Z]) (?:\u2014|-) (.+)$", re.MULTILINE),
    ),
)


@dataclass(frozen=True)
class HistoricalItem:
    item_id: str
    title: str
    source_path: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _missing_required_docs(repo_root: Path) -> list[str]:
    missing: list[str] = []
    for relative_path in (READINESS_DOC, INVENTORY_DOC, ACTIVE_PLAN_DOC):
        if not (repo_root / relative_path).is_file():
            missing.append(str(relative_path))
    return missing


def _top_level_dirs(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        item.name
        for item in root.iterdir()
        if item.is_dir() and item.name != "__pycache__"
    )


def _extract_historical_items(repo_root: Path) -> tuple[list[HistoricalItem], list[str]]:
    items: list[HistoricalItem] = []
    notes: list[str] = []
    for relative_path, prefix, pattern in HISTORICAL_PLAN_SPECS:
        path = repo_root / relative_path
        if not path.is_file():
            notes.append(f"missing_historical_plan:{relative_path}")
            continue
        text = _read_text(path)
        for match in pattern.finditer(text):
            raw_id = match.group(1)
            title = match.group(2).strip()
            if prefix == "SCIENTIST_AUDIT_REMEDIATION_PLAN":
                item_id = f"{prefix}:{raw_id}"
            elif prefix == "SCIENTIST_AGENT_SOTA_ROADMAP":
                item_id = f"{prefix}:PHASE{raw_id}"
            elif prefix == "SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT":
                item_id = f"{prefix}:PHASE_{raw_id}"
            else:
                item_id = f"{prefix}:{raw_id}"
            items.append(HistoricalItem(item_id=item_id, title=title, source_path=str(relative_path)))
    return items, notes


def _table_status_for(text: str, item_id: str) -> str | None:
    escaped = re.escape(item_id)
    pattern = re.compile(rf"\|\s*`{escaped}`\s*\|\s*`([^`]+)`\s*\|")
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def _contains_token(text: str, token: str) -> bool:
    return token in text


def _build_payload(repo_root: Path) -> dict[str, object]:
    notes: list[str] = []
    missing_docs = _missing_required_docs(repo_root)
    notes.extend(f"missing_doc:{path}" for path in missing_docs)

    readiness_text = ""
    inventory_text = ""
    if not missing_docs:
        readiness_text = _read_text(repo_root / READINESS_DOC)
        inventory_text = _read_text(repo_root / INVENTORY_DOC)

    capability_missing = [
        capability_id
        for capability_id in REQUIRED_CAPABILITY_IDS
        if _table_status_for(readiness_text, capability_id) is None
    ]
    notes.extend(f"missing_capability:{item}" for item in capability_missing)

    source_root = repo_root / "src/polisyos/scientist"
    test_root = repo_root / "tests/scientist"
    source_packages = _top_level_dirs(source_root)
    test_packages = _top_level_dirs(test_root)
    source_missing = [
        name
        for name in source_packages
        if not _contains_token(inventory_text, f"src/polisyos/scientist/{name}/**")
    ]
    test_missing = [
        name
        for name in test_packages
        if not _contains_token(inventory_text, f"tests/scientist/{name}/**")
    ]
    notes.extend(f"missing_source_inventory:{item}" for item in source_missing)
    notes.extend(f"missing_test_inventory:{item}" for item in test_missing)

    reference_root = repo_root / "docs/reference/scientist"
    reference_docs = sorted(path.name for path in reference_root.glob("*.md"))
    reference_missing = [
        name for name in reference_docs if not _contains_token(inventory_text, f"[{name}]({name})")
    ]
    notes.extend(f"missing_reference_inventory:{item}" for item in reference_missing)

    historical_items, archive_notes = _extract_historical_items(repo_root)
    notes.extend(archive_notes)
    historical_statuses: dict[str, str | None] = {}
    for item in historical_items:
        status = _table_status_for(inventory_text, item.item_id)
        historical_statuses[item.item_id] = status
        if status is None:
            notes.append(f"missing_historical_mapping:{item.item_id}")
        elif status not in ALLOWED_HISTORICAL_STATUSES:
            notes.append(f"invalid_historical_status:{item.item_id}:{status}")

    active_plan_tokens = (
        "SCIENTIST_BEST_IN_CLASS_PLAN.md",
        "Phase 1.0",
        "Phase 1.1",
        "Phase 1.7",
        "Phase 2.9",
    )
    active_index_missing = [
        token for token in active_plan_tokens if not _contains_token(readiness_text, token)
    ]
    notes.extend(f"missing_active_plan_index:{item}" for item in active_index_missing)

    category_results = {
        "required_docs_exist": not missing_docs,
        "capability_readiness_matrix_complete": not capability_missing,
        "source_inventory_complete": not source_missing,
        "test_inventory_complete": not test_missing,
        "reference_inventory_complete": not reference_missing,
        "historical_plan_map_complete": not any(
            note.startswith("missing_historical_mapping:")
            or note.startswith("invalid_historical_status:")
            or note.startswith("missing_historical_plan:")
            for note in notes
        )
        and bool(historical_items),
        "active_plan_index_complete": not active_index_missing,
    }

    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "required_capability_ids": list(REQUIRED_CAPABILITY_IDS),
        "source_packages": source_packages,
        "test_packages": test_packages,
        "reference_docs": reference_docs,
        "historical_items": [
            {
                "item_id": item.item_id,
                "title": item.title,
                "source_path": item.source_path,
                "status": historical_statuses.get(item.item_id),
            }
            for item in historical_items
        ],
        "allowed_historical_statuses": sorted(ALLOWED_HISTORICAL_STATUSES),
        "notes": notes,
    }


def _phase1_0_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist best-in-class Phase 1.0 reconciliation docs are complete"
        if status == "ok"
        else "Scientist best-in-class Phase 1.0 reconciliation docs are incomplete"
    )
    messages = tuple(
        ToolMessage(
            level="error",
            message=str(item),
            rule_id="SCIENTIST_BEST_IN_CLASS_PHASE1_0",
        )
        for item in note_list
    )
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=summary,
        exit_code=0 if status == "ok" else 1,
        messages=messages,
        data=payload,
    )


def _emit(content: str, *, output: Path | None) -> None:
    if output is not None:
        atomic_write_text(output, content if content.endswith("\n") else content + "\n")
        return
    sys.stdout.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Scientist best-in-class Phase 1.0 reconciliation docs.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to validate. Defaults to the current working directory.",
    )
    parser.add_argument("--output", type=Path, help="Optional output file path.")
    parser.add_argument(
        "--output-format",
        choices=("text", "json", "junit"),
        default="json",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Exit non-zero when the reconciliation gate is incomplete.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    payload = _build_payload(repo_root)

    if args.output_format == "json":
        _emit(json.dumps(payload, indent=2, sort_keys=True), output=args.output)
    else:
        _emit(
            format_tool_result(_phase1_0_result(payload), output_format=args.output_format),
            output=args.output,
        )

    if args.require_passing and not bool(payload.get("passes_all")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
