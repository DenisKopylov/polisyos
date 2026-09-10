"""Reconcile the complete authoritative task table with two independent parsers.

This checks delivery bookkeeping, not whether a task's semantic Done is true.
Those claims bind to the independently reviewed workstream gates in the journal.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = "992aa493f"
PLAN = "docs/plans/active/layer3-slices/GY-engine-subordination.md"
TASKS = frozenset({"GY-VC1", "GY-AS1", "GY-CR2", "GY-CR3", "GY-CR5"})
FINAL_STATUSES = {key: "blocked" if key == "GY-AS1" else "executed" for key in TASKS}


def git(*args: str) -> str:
    """Read exact git state without moving the branch or changing its index."""
    # Every argument comes from this file's fixed read-only calls, never the plan.
    return subprocess.check_output(["/usr/bin/git", *args], cwd=ROOT, text=True)  # noqa: S603


def regex_rows(text: str) -> dict[str, tuple[str, str]]:
    """Parse a bounded complete section with anchored row/status syntax."""
    start = text.index("## 8.5 Task standing (authoritative)")
    finish = text.find("\n## ", start + 1)
    section = text[start:] if finish == -1 else text[start:finish]
    result = {}
    for line in section.splitlines():
        if not line.startswith("| `GY-"):
            continue
        match = re.match(r"^\| `(GY-[^`]+)` \|[^|]*\|\s*(?:\*\*)?`([^`]+)`(?:\*\*)?\s*\|", line)
        if match is None or match[1] in result:
            raise ValueError("regex_unreadable_or_duplicate_row")
        result[match[1]] = (match[2], line)
    return result


def cell_rows(text: str) -> dict[str, tuple[str, str]]:
    """Independently parse the section as a line-state machine and table cells."""
    active = False
    result = {}
    for line in text.splitlines():
        if line.startswith("## "):
            if active:
                break
            active = line.split(maxsplit=2)[1] == "8.5"
            continue
        if not active or not line.startswith("|"):
            continue
        cells = [cell.strip().replace("`", "").replace("**", "") for cell in line.split("|")[1:-1]]
        if not cells or not cells[0].startswith("GY-"):
            continue
        if len(cells) != 6 or not cells[2] or cells[0] in result:
            raise ValueError("cell_unreadable_or_duplicate_row")
        result[cells[0]] = (cells[2], line)
    return result


def check(text: str) -> dict[str, object]:
    """Require exactly the commissioned rows to move and preserve all others."""
    base_text = git("show", f"{BASE}:policy-engine/{PLAN}")
    before, after = regex_rows(base_text), regex_rows(text)
    if before != cell_rows(base_text) or after != cell_rows(text):
        raise ValueError("independent_table_parsers_disagree")
    if len(before) != 74 or set(before) != set(after):
        raise ValueError("task_table_denominator_changed")
    if Counter(value[0] for value in before.values()) != {
        "executed": 50, "not_started": 17, "blocked": 5, "not_executed": 2,
    }:
        raise ValueError("lane_base_distribution_changed")
    moved = {key for key in before if before[key] != after[key]}
    if moved != TASKS:
        raise ValueError(
            "uncommissioned_or_missing_row_movement:" + ",".join(sorted(moved ^ TASKS))
        )
    if any(
        before[key][0] != "not_started" or after[key][0] != FINAL_STATUSES[key]
        for key in TASKS
    ):
        raise ValueError("commissioned_task_transition_mismatch")
    # Full-file preservation, not merely an unchanged selected table count.
    restored = text
    for key in TASKS:
        restored = restored.replace(after[key][1], before[key][1], 1)
    if restored != base_text:
        raise ValueError("plan_changed_outside_five_rows")
    if git("symbolic-ref", "--short", "HEAD").strip() != "codex/gy-lattice-and-custody":
        raise ValueError("branch_attachment_changed")
    changed = set(git("diff", "--name-only", BASE).splitlines())
    forbidden = {
        "policy-engine/docs/plans/active/DEBT-REGISTER.md",
        "policy-engine/docs/plans/active/LEDGER.md",
    }
    if changed & forbidden:
        raise ValueError("architect_owned_register_changed")
    existing_source = {
        path for path in git("diff", "--name-only", "--diff-filter=M", BASE).splitlines()
        if path.startswith("policy-engine/src/") and not path.endswith("/README.md")
    }
    if existing_source:
        raise ValueError("closed_production_source_modified:" + ",".join(sorted(existing_source)))
    return {
        "result": "pass", "lane_base": BASE, "path_denominator": PLAN,
        "file_type_denominator": "one Markdown file, complete authoritative section 8.5",
        "rows": len(after), "changed_tasks": sorted(moved),
        "before": dict(Counter(value[0] for value in before.values())),
        "after": dict(Counter(value[0] for value in after.values())),
        "independent_parsers_agree": True,
    }


def main() -> int:
    """Read the real plan or an explicit corruption probe and return a gate code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / PLAN)
    args = parser.parse_args()
    try:
        result = check(args.plan.read_text())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"result": "fail", "reason": str(exc)}))  # noqa: T201
        return 1
    print(json.dumps(result, indent=2))  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
