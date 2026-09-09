"""Enumerate tracked Python observation-ref and recorded-epoch readers."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path


def main() -> int:
    root = Path.cwd()
    scopes = ("src", "tools", "tests")
    tracked = subprocess.check_output(  # noqa: S603 - fixed read-only local git arguments
        ["/usr/bin/git", "ls-files", "-z", "--", *scopes], text=True,
    ).split("\0")
    files = {name for name in tracked if name.endswith(".py")}
    physical = {
        path.relative_to(root).as_posix()
        for scope in scopes for path in (root / scope).rglob("*.py")
        if path.relative_to(root).as_posix() in files
    }
    if files != physical:
        raise RuntimeError(f"tracked/physical disagreement: {sorted(files ^ physical)}")
    expression = re.compile(
        r"observational_data_ref|recorded_panel_(?:measurement_root|method_binding)\.v[0-9]+"
    )
    unreadable = []
    rows = []
    raw_members, ast_members = set(), set()
    for name in sorted(files):
        try:
            raw = (root / name).read_bytes()
            source = raw.decode("utf-8")
            tree = ast.parse(source, filename=name)
        except (OSError, UnicodeError, SyntaxError) as exc:
            unreadable.append({"path": name, "reason": repr(exc)})
            continue
        if expression.search(source):
            raw_members.add(name)
        matches = []
        for node in ast.walk(tree):
            value = (
                node.attr if isinstance(node, ast.Attribute)
                else node.id if isinstance(node, ast.Name)
                else node.arg or "" if isinstance(node, (ast.arg, ast.keyword))
                else node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                else node.value if isinstance(node, ast.Constant) and isinstance(node.value, str)
                else ""
            )
            if expression.search(value):
                matches.append({"line": node.lineno, "ast": type(node).__name__, "value": value})
        if matches:
            ast_members.add(name)
            # Full relevant function identity set, not duplicated function bodies.
            functions = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    block = "\n".join(source.splitlines()[node.lineno - 1:node.end_lineno])
                    if expression.search(block):
                        functions.append({
                            "name": node.name, "line": node.lineno,
                            "calls": sorted({
                                ast.unparse(call.func) for call in ast.walk(node)
                                if isinstance(call, ast.Call)
                                and any(token in ast.unparse(call.func) for token in (
                                    "get_bytes", "model_validate", "materialize", "verify",
                                    "put_json", "produce", "get_manifest", "load",
                                ))
                            }),
                        })
            rows.append({
                "path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                "matches": matches, "relevant_functions": functions,
            })
    # Regex sees comments too. Report that difference explicitly; do not silently
    # equate a comment with a reader. All AST matches must be in the raw set.
    if ast_members - raw_members:
        raise RuntimeError("AST membership cannot exceed matching source membership")
    print(json.dumps({  # noqa: T201 - complete census command output
        "denominator": "all tracked src/tools/tests Python files, independent physical walk",
        "tracked_python_files": len(files), "physical_tracked_python_files": len(physical),
        "denominator_identity_sha256": hashlib.sha256(
            "\n".join(sorted(files)).encode(),
        ).hexdigest(),
        "regex_member_count": len(raw_members), "ast_member_count": len(ast_members),
        "comment_only_members": sorted(raw_members - ast_members),
        "unreadable": unreadable, "members": rows,
    }, indent=2))
    return int(bool(unreadable))


if __name__ == "__main__":
    raise SystemExit(main())
