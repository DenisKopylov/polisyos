"""Census the finite Git/AST checkpoint surface without importing the product."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SHA = "456f34938731b1ef11555d8333d011d3552574ec"
METHODS = {
    "on_node_complete",
    "on_tier_complete",
    "on_node_complete_async",
    "on_tier_complete_async",
}


def git(repo: Path, *args: str) -> bytes:
    """Read the pinned tree using literal read-only Git operations."""
    return subprocess.check_output(  # noqa: S603 - fixed Git and read-only internal call sites
        ["/usr/bin/git", "-C", str(repo), *args]
    )


class Scan(ast.NodeVisitor):
    """Record declared signatures, direct calls and literal getattr sites."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.stack: list[str] = []
        self.definitions: list[dict[str, object]] = []
        self.calls: list[dict[str, object]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name in METHODS:
            self.definitions.append(
                {
                    "path": self.path,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "qualname": ".".join([*self.stack, node.name]),
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "arguments": ast.unparse(node.args),
                    "accepts_arbitrary_kwargs": node.args.kwarg is not None,
                }
            )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:
        method = node.func.attr if isinstance(node.func, ast.Attribute) else None
        literal_lookup = any(
            isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value in METHODS
            for arg in node.args
        )
        if method in METHODS or literal_lookup:
            self.calls.append(
                {
                    "path": self.path,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "scope": ".".join(self.stack),
                    "expression": ast.unparse(node),
                }
            )
        self.generic_visit(node)


def main() -> None:
    """Emit the complete declared filename and literal surface denominators."""
    repo = Path(
        subprocess.check_output(["/usr/bin/git", "rev-parse", "--show-toplevel"], text=True).strip()
    )
    paths = [
        path
        for path in git(repo, "ls-tree", "-r", "--full-tree", "--name-only", SHA)
        .decode()
        .splitlines()
        if path.endswith(".py")
    ]
    matched: list[dict[str, object]] = []
    definitions: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        data = git(repo, "show", SHA + ":" + path)
        if not any(name.encode() in data for name in METHODS):
            continue
        matched.append(
            {
                "path": path,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "git_blob": git(repo, "rev-parse", SHA + ":" + path).decode().strip(),
            }
        )
        try:
            tree = ast.parse(data.decode(), filename=path)
        except (SyntaxError, UnicodeError) as exc:
            errors.append({"path": path, "error": str(exc)})
            continue
        scanner = Scan(path)
        scanner.visit(tree)
        definitions.extend(scanner.definitions)
        calls.extend(scanner.calls)
    driver = Path(__file__).resolve().relative_to(repo)
    report = {
        "kind": "checkpoint_literal_surface_git_ast_census",
        "source_sha": SHA,
        "source_tree": git(repo, "rev-parse", SHA + "^{tree}").decode().strip(),
        "command": f"{sys.executable} {driver}",
        "cwd": str(repo),
        "interpreter": sys.version,
        "denominator": {
            "complete_tracked_python_paths": len(paths),
            "literal_hook_token_matching_files": len(matched),
            "parsed_matching_files": len(matched) - len(errors),
            "matching_definitions": len(definitions),
            "literal_direct_calls_or_getattr_hooks": len(calls),
        },
        "matched_files": matched,
        "definitions": definitions,
        "calls": calls,
        "parse_errors": errors,
        "scope": (
            "Complete declared tracked Python filename corpus and literal hook surface; "
            "not an external distribution, computed method lookup, dynamic third-party "
            "implementation or runtime reachability proof. Files without a literal hook "
            "token are not AST-parsed; signature compatibility is bounded by the declared "
            "Protocol rather than inferred from zero external matches."
        ),
    }
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
