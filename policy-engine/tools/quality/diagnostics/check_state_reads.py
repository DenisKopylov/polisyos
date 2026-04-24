#!/usr/bin/env python3
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"

_STATE_BUCKETS = {"inputs", "artifacts_index", "reports_index", "params", "budgets"}
_SKIP_FILES = {"__init__.py", "errors.py", "state_keys.py"}


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
        if isinstance(parsed, ast.FunctionDef) and parsed.name == "execute":
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
        if not isinstance(parsed, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "_SPEC" for target in parsed.targets
        ):
            continue
        if not isinstance(parsed.value, ast.Call):
            continue
        if not isinstance(parsed.value.func, ast.Name) or parsed.value.func.id != "NodeSpec":
            continue
        for kw in parsed.value.keywords:
            if kw.arg != "state_reads":
                continue
            if not isinstance(kw.value, (ast.List, ast.Tuple)):
                continue
            for entry in kw.value.elts:
                path = _read_value_to_path(entry)
                if not path:
                    continue
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
    files: list[Path] = []
    for root in roots:
        for file_path in root.rglob("*.py"):
            if file_path.name in _SKIP_FILES:
                continue
            files.append(file_path)
    return sorted(files)


def main() -> int:
    errors: list[str] = []
    for file_path in _iter_node_files():
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        spec_exact, spec_prefix = _extract_spec_reads(tree)
        requirements = _extract_execute_requirements(tree)
        for prefix in sorted(requirements.prefix):
            if not _covers_prefix(spec_exact, spec_prefix, prefix):
                errors.append(f"{file_path}: missing state_reads prefix '{prefix}'")
        for exact in sorted(requirements.exact):
            if not _covers_exact(spec_exact, spec_prefix, exact):
                errors.append(f"{file_path}: missing state_reads path '{exact}'")

    if errors:
        for issue in errors:
            print(issue)
        return 1
    print("state_reads contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
