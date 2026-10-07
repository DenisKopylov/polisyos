#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tools.lib.fs import iter_repository_files, measure_file_reads, measured_read_text
from tools.lib.imports import repo_root_from

if TYPE_CHECKING:
    from pathlib import Path

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"

_STATE_BUCKETS = {"inputs", "artifacts_index", "reports_index", "params", "budgets"}
_SKIP_FILES = {"__init__.py", "errors.py", "state_keys.py"}
_NODE_SPEC_CONSTRUCTORS = {"NodeSpec", "OutputAwareNodeSpec"}


@dataclass(frozen=True)
class ReadRequirements:
    exact: set[str]
    prefix: set[str]


class _StateReadVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.exact: set[str] = set()
        self.prefix: set[str] = set()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == "state":
            if node.attr == "run_id":
                self.exact.add("run_id")
            elif node.attr in _STATE_BUCKETS:
                self.prefix.add(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            bucket = _state_bucket(node.func.value)
            if bucket is not None:
                key = _string_arg(node)
                if key is not None:
                    self.exact.add(f"{bucket}.{key}")
                else:
                    self.prefix.add(bucket)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        bucket = _state_bucket(node.value)
        if bucket is not None:
            key = _string_subscript(node.slice)
            if key is not None:
                self.exact.add(f"{bucket}.{key}")
            else:
                self.prefix.add(bucket)
        self.generic_visit(node)


def _state_bucket(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Attribute):
        return None
    if not isinstance(node.value, ast.Name) or node.value.id != "state":
        return None
    if node.attr in _STATE_BUCKETS:
        return node.attr
    return None


def _string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _string_subscript(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_execute_requirements(tree: ast.Module) -> ReadRequirements:
    visitor = _StateReadVisitor()
    for parsed in ast.walk(tree):
        if isinstance(parsed, (ast.FunctionDef, ast.AsyncFunctionDef)) and parsed.name == "execute":
            visitor.visit(parsed)
    return ReadRequirements(exact=visitor.exact, prefix=visitor.prefix)


def _read_value_to_path(value: ast.AST) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.JoinedStr):
        static_prefix = ""
        for item in value.values:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                static_prefix += item.value
            else:
                break
        static_prefix = static_prefix.rstrip(".")
        return static_prefix or None
    return None


def _extract_spec_reads(tree: ast.Module) -> tuple[set[str], set[str]]:
    exact: set[str] = set()
    prefix: set[str] = set()
    for parsed in ast.walk(tree):
        if not isinstance(parsed, (ast.Assign, ast.AnnAssign)):
            continue
        targets = [parsed.target] if isinstance(parsed, ast.AnnAssign) else parsed.targets
        if not any(isinstance(target, ast.Name) and target.id == "_SPEC" for target in targets):
            continue
        if not (
            isinstance(parsed.value, ast.Call)
            and isinstance(parsed.value.func, ast.Name)
            and parsed.value.func.id in _NODE_SPEC_CONSTRUCTORS
        ):
            raise ValueError("unsupported_spec_constructor")
        if parsed.value.args or any(kw.arg is None for kw in parsed.value.keywords):
            raise ValueError("unsupported_spec_arguments")
        for kw in parsed.value.keywords:
            if kw.arg != "state_reads":
                continue
            if not isinstance(kw.value, (ast.List, ast.Tuple)):
                raise ValueError("unsupported_state_reads_expression")
            for entry in kw.value.elts:
                path = _read_value_to_path(entry)
                if not path:
                    raise ValueError("unsupported_state_reads_entry")
                exact.add(path)
                prefix.add(path.split(".", 1)[0])
    return exact, prefix


def _covers_prefix(spec_exact: set[str], spec_prefix: set[str], path: str) -> bool:
    if path in spec_prefix:
        return True
    return any(entry.startswith(f"{path}.") for entry in spec_exact)


def _covers_exact(spec_exact: set[str], spec_prefix: set[str], path: str) -> bool:
    if path == "run_id":
        return "run_id" in spec_exact
    if path in spec_exact:
        return True
    bucket = path.split(".", 1)[0]
    return bucket in spec_prefix


def _iter_node_files() -> list[Path]:
    roots = [
        SRC_ROOT / "polisyos" / "scientist" / "nodes" / "builtins",
        SRC_ROOT / "polisyos" / "scientist" / "engine" / "builtins",
    ]
    return sorted(
        path
        for path in iter_repository_files(SRC_ROOT)
        if path.suffix == ".py"
        and path.name not in _SKIP_FILES
        and any(path.is_relative_to(root) for root in roots)
    )


def main() -> int:
    errors: list[str] = []
    incomplete: list[dict[str, str]] = []
    with measure_file_reads(REPO_ROOT) as reads:
        try:
            files = _iter_node_files()
        except (OSError, RuntimeError) as error:
            files = []
            incomplete.append({"path": str(SRC_ROOT), "reason": type(error).__name__})
        for file_path in files:
            try:
                tree = ast.parse(measured_read_text(file_path, encoding="utf-8"))
            except (OSError, UnicodeError, SyntaxError) as error:
                incomplete.append({"path": str(file_path), "reason": type(error).__name__})
                continue
            try:
                spec_exact, spec_prefix = _extract_spec_reads(tree)
            except ValueError as error:
                incomplete.append({"path": str(file_path), "reason": str(error)})
                continue
            requirements = _extract_execute_requirements(tree)
            for prefix in sorted(requirements.prefix):
                if not _covers_prefix(spec_exact, spec_prefix, prefix):
                    errors.append(f"{file_path}: missing state_reads prefix '{prefix}'")
            for exact in sorted(requirements.exact):
                if not _covers_exact(spec_exact, spec_prefix, exact):
                    errors.append(f"{file_path}: missing state_reads path '{exact}'")
        receipt = reads.snapshot(complete_verdict=not incomplete)
        receipt.update(
            {
                "verdict": "UNRUN" if incomplete else "FAIL" if errors else "PASS",
                "selected_input_denominator": len(files),
                "selected_paths": [str(path) for path in files],
                "selector": [
                    "src/polisyos/scientist/nodes/builtins/**/*.py",
                    "src/polisyos/scientist/engine/builtins/**/*.py",
                ],
                "exclusions": sorted(_SKIP_FILES),
                "enumeration": (
                    "Git tracked paths; complete filesystem set only for non-Git fixtures"
                ),
                "unresolved_inputs": incomplete,
            }
        )
        receipt["unresolved_by_construction"].append(
            "Only direct state-name reads in sync/async execute and Assign/AnnAssign "
            "unqualified _SPEC calls to "
            "NodeSpec/OutputAwareNodeSpec are interpreted; aliases, indirect reads, "
            "runtime dispatch and files outside the declared selector are undecided."
        )
        print("state_reads measurement: " + json.dumps(receipt, sort_keys=True))
    for issue in errors:
        print(issue)
    for issue in incomplete:
        print(f"{issue['path']}: state_reads unresolved {issue['reason']}")
    if incomplete:
        return 2
    if errors:
        return 1
    print("state_reads contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
