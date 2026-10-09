"""Validate the complete E02 task graph against canonical finding occurrences."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def require(condition: object, message: str) -> None:
    """Refuse an invalid planning input even under optimized Python."""
    if not condition:
        raise ValueError(message)


def main() -> None:
    """Emit a recomputed planning receipt; this does not verify runtime behavior."""
    pack = Path(__file__).resolve().parent
    research = pack.parent.parent
    coverage_path = research / "closure-decisions/coverage.json"
    original_path = research / "integration/connected-closeout-plan-2026-10-08/findings.json"
    original_tasks_path = original_path.with_name("tasks.json")
    tasks_path = pack / "TASKS.json"
    inputs_path = pack / "INPUTS.json"
    coverage = json.loads(coverage_path.read_text())
    original = json.loads(original_path.read_text())
    original_tasks = json.loads(original_tasks_path.read_text())["tasks"]
    tasks_doc = json.loads(tasks_path.read_text())
    tasks = tasks_doc["tasks"]
    inputs = json.loads(inputs_path.read_text())
    ids = {row["id"] for row in coverage["findings"]}
    require(len(ids) == len(coverage["findings"]), "duplicate canonical finding")
    require(ids == {row["id"] for row in original["rows"]}, "canonical ID drift")
    occurrences = sum(len(row["criterion_refs"]) for row in coverage["findings"])
    measured = {
        "bundles": len(coverage["bundles"]),
        "findings": len(ids),
        "criterion_occurrences": occurrences,
    }
    require(
        measured == original["denominator"] == tasks_doc["original_denominator"],
        "invalid execution pack",
    )
    proposals = dict(Counter(row["author_proposal"] for row in original["rows"]))
    historical = dict(Counter(row["ledger_status_historical"] for row in coverage["findings"]))
    require(proposals == original["author_proposals"], "invalid execution pack")
    require(historical == coverage["historical_ledger_counts"], "invalid execution pack")
    require(
        sum(proposals.values()) == sum(historical.values()) == len(ids), "invalid execution pack"
    )
    covered: set[str] = set()
    links = 0
    for task_id, task in tasks.items():
        selected = task.get("finding_ids", [])
        require(len(selected) == len(set(selected)), f"duplicate route in {task_id}")
        require(set(selected) <= ids, f"unknown finding in {task_id}")
        covered.update(selected)
        links += len(selected)
        require(set(task.get("depends", [])) <= set(tasks), f"unknown dependency in {task_id}")
    require(covered == ids, f"missing routes: {sorted(ids - covered)}")
    require(set(original_tasks) <= set(tasks), "lost original task")
    for row in original["rows"]:
        for task_id in row["next_tasks"]:
            require(row["id"] in tasks[task_id]["finding_ids"], "lost original task route")
        pointer = row["original_criteria_pointer"].strip("/").split("/")
        value = coverage
        for part in pointer:
            value = value[int(part)] if isinstance(value, list) else value[part]
        require(value, "empty original criterion pointer")
        require(all(ref["criterion_id"] == row["id"] for ref in value), "invalid execution pack")
    visited: set[str] = set()
    active: set[str] = set()
    order: list[str] = []

    def visit(task_id: str) -> None:
        require(task_id not in active, f"dependency cycle through {task_id}")
        if task_id in visited:
            return
        active.add(task_id)
        for dependency in tasks[task_id].get("depends", []):
            visit(dependency)
        active.remove(task_id)
        visited.add(task_id)
        order.append(task_id)

    for task_id in tasks:
        visit(task_id)
    require(
        not inputs["formal_closure_ids"] and not tasks_doc["formal_closure_ids"],
        "invalid execution pack",
    )
    require(
        next(row for row in coverage["findings"] if row["id"] == "B198")["ledger_status_historical"]
        == "closed",
        "historical B198 was reopened",
    )
    paths = [coverage_path, original_path, original_tasks_path, tasks_path, inputs_path]
    receipt = {
        "schema": "policyos.e02.local_execution_pack_validation.v1",
        "scope": "complete planning graph/criterion pointers; no runtime acceptance",
        "result": "PASS",
        "sources": [
            {
                "path": str(path.relative_to(research.parents[2])),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in paths
        ],
        "denominator": measured,
        "author_proposals": proposals,
        "historical_ledger_counts": historical,
        "tasks": len(tasks),
        "original_tasks": len(original_tasks),
        "finding_task_links": links,
        "topological_order": order,
        "unrouted_findings": sorted(ids - covered),
        "all_original_criterion_pointers_resolved": True,
        "historical_B198_retained": True,
        "new_formal_closure_ids": [],
    }
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
