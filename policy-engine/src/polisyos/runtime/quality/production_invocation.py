"""Find new or regressed uninvoked source mechanisms without claiming runtime proof.

Run ``python -m polisyos.runtime.quality.production_invocation --base REF
--receipt PATH`` from the product root. The complete tracked Python denominator
is examined; imports, annotations and class construction are not method calls.
Static paths do not establish execution, receipt persistence or authority.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class _Scope:
    name: str
    module: str
    path: str
    node: ast.AST
    parent: _Scope | None
    bindings: dict[str, str | None] = field(default_factory=dict)
    calls: set[str] = field(default_factory=set)
    constructor: bool = False
    candidate: bool = False


def _module(path: str) -> str:
    parts = path.removesuffix(".py").split("/")
    if parts[0] == "src":
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve(expr: ast.AST, scope: _Scope) -> str | None:
    if isinstance(expr, ast.Name):
        current: _Scope | None = scope
        while current is not None:
            if expr.id in current.bindings:
                return current.bindings[expr.id]
            current = current.parent
        return None
    if isinstance(expr, ast.Attribute):
        value = _resolve(expr.value, scope)
        return f"{value}.{expr.attr}" if value else None
    return None


def _concrete(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = [
        n
        for n in node.body
        if not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        )
    ]
    return any(
        not isinstance(n, ast.Pass)
        and not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and n.value.value is Ellipsis
        )
        for n in body
    )


def _entry_guard(node: ast.If) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _graph(sources: dict[str, str], entries: list[str]) -> tuple[dict[str, _Scope], set[str]]:
    scopes: dict[str, _Scope] = {}
    declarations_by_node: dict[int, _Scope] = {}
    roots: set[str] = set()

    def register(node: ast.AST, parent: _Scope, name: str) -> _Scope:
        scope = _Scope(name, parent.module, parent.path, node, parent)
        scopes[name] = scope
        declarations_by_node[id(node)] = scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            args += [a for a in (node.args.vararg, node.args.kwarg) if a is not None]
            scope.bindings.update({a.arg: None for a in args})
            if isinstance(parent.node, ast.ClassDef) and args:
                scope.bindings[args[0].arg] = parent.name
            scope.candidate = (
                parent.path.startswith("src/") and not node.name.startswith("_") and _concrete(node)
            )
        scope.constructor = isinstance(node, ast.ClassDef)
        return scope

    def declarations(nodes: list[ast.AST], scope: _Scope) -> None:
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{scope.name}.{node.name}"
                scope.bindings[node.name] = name
                child = register(node, scope, name)
                declarations(node.body, child)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    package = scope.module.split(".")[:-1]
                    if scope.path.endswith("/__init__.py"):
                        package = scope.module.split(".")
                    prefix = node.module or ""
                    if node.level:
                        prefix = ".".join(
                            package[: len(package) - node.level + 1] + ([prefix] if prefix else [])
                        )
                    for alias in node.names:
                        scope.bindings[alias.asname or alias.name] = f"{prefix}.{alias.name}"
                else:
                    for alias in node.names:
                        scope.bindings[alias.asname or alias.name.split(".")[0]] = (
                            alias.name if alias.asname else alias.name.split(".")[0]
                        )
            elif isinstance(node, ast.If):
                if isinstance(node.test, ast.Constant):
                    declarations(node.body if node.test.value else node.orelse, scope)
                elif not (isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"):
                    declarations(node.body, scope)
                    declarations(node.orelse, scope)
            else:
                # Statement containers do not create lexical scopes. Derive their
                # children from the grammar, not an enumerated list of containers.
                declarations(list(ast.iter_child_nodes(node)), scope)

    for path, source in sorted(sources.items()):
        module = _module(path)
        parsed = ast.parse(source, filename=path)
        top = _Scope(module, module, path, parsed, None)
        scopes[module] = top
        declarations(parsed.body, top)

    def canonical(name: str | None) -> str | None:
        visited = set()
        while name and name not in scopes and name not in visited:
            visited.add(name)
            parts = name.split(".")
            replacement = None
            for end in range(len(parts) - 1, 0, -1):
                prefix = ".".join(parts[:end])
                if prefix in scopes:
                    bound = scopes[prefix].bindings.get(parts[end])
                    if bound:
                        replacement = ".".join([bound, *parts[end + 1 :]])
                    break
            name = replacement
        return name if name in scopes else None

    def walk(node: ast.AST, scope: _Scope, *, entry: bool = False) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            child = declarations_by_node[id(node)]
            for statement in node.body:
                walk(statement, child)
            return
        if isinstance(node, ast.If):
            if _entry_guard(node) and scope.parent is None:
                root = register(node, scope, f"{scope.name}:<entry>")
                if not scope.path.startswith("tests/"):
                    roots.add(root.name)
                for statement in node.body:
                    walk(statement, root, entry=True)
                return
            if isinstance(node.test, ast.Constant):
                for statement in node.body if node.test.value else node.orelse:
                    walk(statement, scope, entry=entry)
                return
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                return
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            # A concrete construction supports receiver resolution, not method execution.
            resolved = (
                _resolve(value.func, scope)
                if isinstance(value, ast.Call)
                else (_resolve(value, scope) if value else None)
            )
            if isinstance(value, ast.Call):
                known = canonical(resolved)
                resolved = known if known and scopes[known].constructor else None
            for target in targets:
                if isinstance(target, ast.Name):
                    scope.bindings[target.id] = resolved
        if isinstance(node, ast.Call):
            callee = canonical(_resolve(node.func, scope))
            if callee:
                scope.calls.add(callee)
                # __init__ is called by construction; other methods are not.
                if scopes[callee].constructor and f"{callee}.__init__" in scopes:
                    scope.calls.add(f"{callee}.__init__")
        for child in ast.iter_child_nodes(node):
            walk(child, scope, entry=entry)

    for scope in list(scopes.values()):
        if scope.parent is None:
            for node in scope.node.body:
                walk(node, scope)
    for entry in entries:
        target = canonical(entry.replace(":", "."))
        if target and not scopes[target].path.startswith("tests/"):
            roots.add(target)
    return scopes, roots


def _paths(scopes: dict[str, _Scope], roots: set[str]) -> dict[str, str]:
    reached: dict[str, str] = {}
    queue = deque((name, name) for name in sorted(roots))
    while queue:
        name, root = queue.popleft()
        if name in reached or scopes[name].path.startswith("tests/"):
            continue
        reached[name] = root
        queue.extend((callee, root) for callee in sorted(scopes[name].calls))
    return reached


def audit_sources(
    sources: dict[str, str],
    baseline: dict[str, str],
    *,
    deferrals: dict[str, dict[str, str]] | None = None,
    entry_points: list[str] | None = None,
    baseline_entry_points: list[str] | None = None,
) -> dict[str, Any]:
    """Assess every concrete source callable against independently supplied base bytes.

    Args:
        sources: Complete current src/tools/tests Python path-to-text mapping.
        baseline: Complete corresponding base mapping.
        deferrals: Exact symbol to named caller task and reason; never wiring.
        entry_points: Current project script entry points.
        baseline_entry_points: Script entry points at the base.

    Returns:
        Recomputed static diagnostics. A path is never a runtime invocation claim.
    """
    scopes, roots = _graph(sources, entry_points or [])
    old, old_roots = _graph(baseline, baseline_entry_points or [])
    reached, old_reached = _paths(scopes, roots), _paths(old, old_roots)
    callers: dict[str, list[str]] = {}
    for scope in scopes.values():
        for target in scope.calls:
            callers.setdefault(target, []).append(scope.name)
    mechanisms = {}
    regressions = []
    for name, scope in sorted(scopes.items()):
        if not scope.candidate:
            continue
        changed = name not in old or ast.dump(scope.node) != ast.dump(old[name].node)
        regressed = name in old_reached and name not in reached
        decision = (deferrals or {}).get(name)
        if decision is not None and (
            set(decision) != {"task", "reason"}
            or not all(isinstance(v, str) and v.strip() for v in decision.values())
        ):
            raise ValueError(f"invalid_named_deferral:{name}")
        status = "static_path" if name in reached else "deferred" if decision else "uninvoked"
        if (changed or regressed) and status == "uninvoked":
            regressions.append(name)
        mechanisms[name] = {
            "status": status,
            "path": scope.path,
            "terminus": reached.get(name),
            "changed": changed,
            "lost_path": regressed,
            "source_callers": sorted(
                c for c in callers.get(name, []) if not scopes[c].path.startswith("tests/")
            ),
            "test_callers": sorted(
                c for c in callers.get(name, []) if scopes[c].path.startswith("tests/")
            ),
            "deferral": decision,
        }
    return {
        "mechanisms": mechanisms,
        "regressions": regressions,
        "root_count": len(roots),
        "predicate_provenance": "recomputed",
        "runtime_invocation_established": False,
        "limitations": [
            "Static paths do not prove execution, persisted receipts, or gate substance.",
            "Reflection, callbacks, receiver types and conditional aliases need manual tracing.",
            "Concrete public source callables are candidates; helpers are traversed.",
            "No HTTP route is assumed runnable merely because it has a decorator.",
        ],
    }


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise OSError("git_executable_missing")
    # Fixed read-only Git verbs; argument arrays, never a shell.
    return subprocess.check_output(  # noqa: S603
        [executable, "-C", str(root), *args], input=input_bytes
    )


def _read_tree(root: Path, base: str | None) -> tuple[dict[str, str], list[str]]:
    if base is None:
        names = _git(root, "ls-files", "-z", "--", "src", "tools", "tests")
    else:
        names = _git(root, "ls-tree", "-rz", "--name-only", base, "--", "src", "tools", "tests")
    prefix = _git(root, "rev-parse", "--show-prefix").decode().strip()

    paths = [raw.decode() for raw in names.split(b"\0") if raw.endswith(b".py")]
    if base is None:
        sources = {name: (root / name).read_text(encoding="utf-8-sig") for name in paths}
        manifest_path = root / "pyproject.toml"
        manifest_text = manifest_path.read_text() if manifest_path.exists() else ""
    else:
        # One Git process reads the complete pinned set. Per-file git show turned
        # a deterministic census into thousands of process launches.
        queries = [*paths, "pyproject.toml"]
        if any("\n" in name for name in queries):
            raise ValueError("unsupported_newline_in_source_path")
        request = "".join(f"{base}:{prefix}{name}\n" for name in queries).encode()
        raw = _git(root, "cat-file", "--batch", input_bytes=request)
        sources = {}
        offset = 0
        for name in queries:
            header_end = raw.index(b"\n", offset)
            header = raw[offset:header_end].split()
            offset = header_end + 1
            if header[-1] == b"missing" and name == "pyproject.toml":
                continue
            if len(header) != 3 or header[1] != b"blob":
                raise ValueError(f"unresolved_source_blob:{name}")
            size = int(header[2])
            sources[name] = raw[offset : offset + size].decode("utf-8-sig")
            offset += size + 1
        if offset != len(raw):
            raise ValueError("source_blob_denominator_mismatch")
        manifest_text = sources.pop("pyproject.toml", "")
    manifest = tomllib.loads(manifest_text)

    return sources, list(manifest.get("project", {}).get("scripts", {}).values())


def audit_repository(
    root: Path,
    base: str,
    *,
    deferrals: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Read complete tracked denominators and assess their new/lost call paths."""
    base = (
        _git(root, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}")
        .decode()
        .strip()
    )
    current, entries = _read_tree(root, None)
    old, old_entries = _read_tree(root, base)
    result = audit_sources(
        current, old, deferrals=deferrals, entry_points=entries, baseline_entry_points=old_entries
    )
    result["base"] = _git(root, "rev-parse", base).decode().strip()
    result["denominator"] = {
        "paths": "all tracked src/**/*.py, tools/**/*.py, tests/**/*.py",
        "current_files": len(current),
        "base_files": len(old),
        "source_files": sum(p.startswith("src/") for p in current),
        "current_sha256": hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest(),
        "base_sha256": hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest(),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    """Persist exact diagnostic output and refuse unaccounted invocation regressions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--deferrals", type=Path)
    parser.add_argument("--check", type=Path, help="Recompute an existing receipt and compare.")
    args = parser.parse_args(argv)
    try:
        decisions = json.loads(args.deferrals.read_text()) if args.deferrals else None
        result = audit_repository(args.repo_root, args.base, deferrals=decisions)
        if args.check is not None and json.loads(args.check.read_text()) != result:
            raise ValueError("invocation_receipt_drift")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2) + "\n")
        if json.loads(args.receipt.read_text()) != result:
            raise ValueError("invocation_receipt_readback_mismatch")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.stdout.write(json.dumps({"status": "refused", "reason": str(exc)}) + "\n")
        return 2
    sys.stdout.write(
        json.dumps(
            {
                "regressions": result["regressions"],
                "receipt": str(args.receipt),
                "runtime_invocation_established": False,
            }
        )
        + "\n"
    )
    return 1 if result["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
