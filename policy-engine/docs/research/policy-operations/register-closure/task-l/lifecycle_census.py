#!/usr/bin/env python3
"""Independently derive the current C33 rule-change lifecycle mapping."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

SCHEMA_VERSION = "policyos.research.task_l.lifecycle_census.v1"
RULE_MODULE = Path("src/polisyos/runtime/quality/rule_replay_engine.py")
REQUESTED_ACTIONS = frozenset({"partial_reissue", "full_reissue", "downgrade", "termination"})


class LifecycleCensusError(RuntimeError):
    """Raised when either complete derivation is missing or ambiguous."""


def _literal_assignment(tree: ast.Module, name: str) -> object:
    matches: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            matches.append(node.value)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            matches.append(node.value)
    if len(matches) != 1 or matches[0] is None:
        raise LifecycleCensusError(f"literal_assignment_cardinality:{name}:{len(matches)}")
    try:
        return ast.literal_eval(matches[0])
    except (ValueError, TypeError) as exc:
        raise LifecycleCensusError(f"literal_assignment_not_decodable:{name}") from exc


def _ast_derivation(repo_root: Path) -> tuple[str, dict[str, dict[str, object]]]:
    source_path = repo_root / RULE_MODULE
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(RULE_MODULE))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise LifecycleCensusError(f"rule_module_ambiguous:{type(exc).__name__}") from exc
    owner = _literal_assignment(tree, "RULE_REPLAY_PRODUCER_OWNER")
    table = _literal_assignment(tree, "C33_RULE_CHANGE_CLASS_TABLE")
    if not isinstance(owner, str) or not isinstance(table, dict):
        raise LifecycleCensusError("rule_literal_shape_invalid")
    return owner, table


def _runtime_derivation(repo_root: Path) -> tuple[str, dict[str, dict[str, object]]]:
    code = """
import json
from polisyos.runtime.quality.rule_replay_engine import (
    C33_RULE_CHANGE_CLASS_TABLE,
    RULE_REPLAY_PRODUCER_OWNER,
)
print(json.dumps({
    "owner": RULE_REPLAY_PRODUCER_OWNER,
    "table": C33_RULE_CHANGE_CLASS_TABLE,
}, sort_keys=True, separators=(",", ":")))
"""
    environment = os.environ.copy()
    source_root = str(repo_root / "src")
    prior_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_root if not prior_pythonpath else os.pathsep.join((source_root, prior_pythonpath))
    )
    completed = subprocess.run(  # noqa: S603 - current Python and fixed import probe
        (sys.executable, "-c", code),
        cwd=repo_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise LifecycleCensusError(
            "runtime_derivation_failed:"
            + (completed.stderr.strip() or f"exit={completed.returncode}")
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LifecycleCensusError("runtime_derivation_not_json") from exc
    owner = payload.get("owner")
    table = payload.get("table")
    if not isinstance(owner, str) or not isinstance(table, dict):
        raise LifecycleCensusError("runtime_derivation_shape_invalid")
    return owner, table


def _normalize_table(
    table: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    for change_class, policy in sorted(table.items()):
        if not isinstance(change_class, str) or not isinstance(policy, Mapping):
            raise LifecycleCensusError("rule_table_member_invalid")
        normalized[change_class] = dict(sorted(policy.items()))
    return normalized


def build_report(repo_root: Path) -> dict[str, object]:
    """Return the AST/runtime reconciliation over the complete declared table."""

    repo_root = repo_root.resolve()
    ast_owner, ast_table_raw = _ast_derivation(repo_root)
    runtime_owner, runtime_table_raw = _runtime_derivation(repo_root)
    ast_table = _normalize_table(ast_table_raw)
    runtime_table = _normalize_table(runtime_table_raw)
    actions = {
        change_class: policy.get("lifecycle_action") for change_class, policy in ast_table.items()
    }
    if any(not isinstance(action, str) for action in actions.values()):
        raise LifecycleCensusError("lifecycle_action_missing_or_ambiguous")
    observed_actions = frozenset(actions.values())
    action_counts = Counter(str(action) for action in actions.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "source_path": RULE_MODULE.as_posix(),
        "ast_owner": ast_owner,
        "runtime_owner": runtime_owner,
        "change_class_count": len(ast_table),
        "ast_table": ast_table,
        "runtime_table": runtime_table,
        "derivations_agree": ast_owner == runtime_owner and ast_table == runtime_table,
        "lifecycle_actions_by_change_class": actions,
        "lifecycle_action_counts": dict(sorted(action_counts.items())),
        "unmapped_requested_actions": sorted(REQUESTED_ACTIONS - observed_actions),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print the reconciled lifecycle table as JSON."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_root", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = build_report(args.repo_root)
    except LifecycleCensusError as exc:
        print(str(exc), file=sys.stderr)  # noqa: T201
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))  # noqa: T201
    return 0 if report["derivations_agree"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
