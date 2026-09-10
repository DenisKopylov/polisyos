"""Complete current SCM reference census, independently reconciled to rg."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import subprocess
import tokenize
import tomllib
from pathlib import Path


def path_basis(roots: set[str], suffixes: set[str]) -> tuple[list[Path], set[Path]]:
    declared = {
        Path(item)
        for item in subprocess.check_output(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ]
        )
        .decode()
        .split("\0")
        if item and Path(item).parts[0] in roots and Path(item).suffix in suffixes
    }
    deleted = {
        Path(item)
        for item in subprocess.check_output(
            [
                "git",
                "ls-files",
                "--deleted",
                "-z",
            ]
        )
        .decode()
        .split("\0")
        if item
    }
    paths = sorted(declared - deleted)
    unreadable = [str(path) for path in paths if not path.is_file() or not os.access(path, os.R_OK)]
    assert not unreadable, {"ambiguous_unreadable_paths": unreadable}
    filesystem_paths = sorted(
        {
            Path(directory) / name
            for root in roots
            for directory, _, names in os.walk(root)
            for name in names
            if (Path(directory) / name).suffix in suffixes and (Path(directory) / name).is_file()
        }
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"],
        input="\0".join(map(str, filesystem_paths)) + "\0",
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode in {0, 1}, ignored.stderr
    secondary_paths = set(filesystem_paths) - {
        Path(path) for path in ignored.stdout.split("\0") if path
    }
    assert set(paths) == secondary_paths, sorted(map(str, set(paths) ^ secondary_paths))
    return paths, secondary_paths


def scalar_paths(
    value: object, needle: str, path: tuple[object, ...] = ()
) -> list[dict[str, object]]:
    rows = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and needle in key:
                rows.append({"path": [*path, key], "position": "mapping_key"})
            rows.extend(scalar_paths(child, needle, (*path, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(scalar_paths(child, needle, (*path, index)))
    elif isinstance(value, str) and needle in value:
        rows.append({"path": list(path), "position": "string_value"})
    return rows


def occurrence_roles(path: Path, raw: bytes, needle: str) -> dict[str, object]:
    """Describe actual syntax locations, never infer authority from their names."""
    source = raw.decode()
    if path.suffix == ".json":
        return {"syntax": "json", "value_paths": scalar_paths(json.loads(source), needle)}
    if path.suffix == ".toml":
        return {"syntax": "toml", "value_paths": scalar_paths(tomllib.loads(source), needle)}
    tree = ast.parse(source, filename=str(path))
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    rows = []
    for match in re.finditer(re.escape(needle), source):
        offset = match.start()
        line = next(index for index in range(1, len(offsets)) if offsets[index] > offset)
        column = offset - offsets[line - 1]
        candidates = [
            node
            for node in ast.walk(tree)
            if getattr(node, "lineno", 0) <= line <= getattr(node, "end_lineno", -1)
        ]
        statements = [node for node in candidates if isinstance(node, ast.stmt)]
        closest = min(
            statements,
            key=lambda node: (node.end_lineno - node.lineno, -node.col_offset),
            default=tree,
        )
        enclosing = []
        current = closest
        while current is not None:
            if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                enclosing.append(current.name)
            current = parent.get(current)
        token_types = {
            tokenize.tok_name[token.type]
            for token in tokens
            if token.start <= (line, column) < token.end
        }
        rows.append(
            {
                "line": line,
                "column": column,
                "lexical_owner": ".".join(reversed(enclosing)) or "<module>",
                "statement_type": type(closest).__name__,
                "token_types": sorted(token_types),
            }
        )
    return {"syntax": "python", "occurrences": rows}


def main() -> None:
    roots = {"src", "tests", "tools", "architecture"}
    suffixes = {".py", ".json", ".toml"}
    paths, secondary_paths = path_basis(roots, suffixes)
    snapshots = {path: path.read_bytes() for path in paths}
    rows = []
    needles = (
        "causal.inference.synthetic_control@1.0.0",
        "causal.inference.synthetic_control@2.0.0",
        "SyntheticControlMethod",
        "_fit_scm_weights",
        "augmented_synthetic_control",
    )
    for needle in needles:
        primary = {str(path) for path, raw in snapshots.items() if needle.encode() in raw}
        secondary = set()
        for offset in range(0, len(paths), 200):
            proc = subprocess.run(
                [
                    "rg",
                    "--files-with-matches",
                    "--fixed-strings",
                    "--",
                    needle,
                    *(str(path) for path in paths[offset : offset + 200]),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert proc.returncode in {0, 1}, proc.stderr
            secondary.update(proc.stdout.splitlines())
        assert primary == secondary, {"needle": needle, "delta": sorted(primary ^ secondary)}
        members = [
            {
                "path": str(path),
                "sha256": hashlib.sha256(snapshots[path]).hexdigest(),
                "lines": [
                    number
                    for number, line in enumerate(snapshots[path].decode().splitlines(), 1)
                    if needle in line
                ],
                "location_roles": occurrence_roles(path, snapshots[path], needle),
            }
            for path in paths
            if str(path) in primary
        ]
        rows.append({"needle": needle, "matching_file_count": len(members), "members": members})
    owner = Path("src/polisyos/foundry/methods/catalog/causal/synthetic_control.py")
    text = snapshots[owner].decode()
    tree = ast.parse(text)
    calls = sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_fit_scm_weights"
    )
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    token_calls = sorted(
        token.start[0]
        for index, token in enumerate(tokens)
        if token.type == tokenize.NAME
        and token.string == "_fit_scm_weights"
        and tokens[index + 1].string == "("
        and tokens[index - 1].string != "def"
    )
    assert calls == token_calls
    final_paths, final_secondary_paths = path_basis(roots, suffixes)
    assert paths == final_paths and secondary_paths == final_secondary_paths, (
        "file_population_changed"
    )
    assert all(path.read_bytes() == raw for path, raw in snapshots.items()), "source_changed"
    print(
        json.dumps(
            {
                "scope": {"roots": sorted(roots), "suffixes": sorted(suffixes)},
                "denominator": len(paths),
                "filesystem_minus_ignored_denominator": len(secondary_paths),
                "denominator_by_root": {
                    root: sum(path.parts[0] == root for path in paths) for root in sorted(roots)
                },
                "denominator_by_type": {
                    suffix: sum(path.suffix == suffix for path in paths)
                    for suffix in sorted(suffixes)
                },
                "source_set_digest": hashlib.sha256(
                    "\n".join(
                        f"{path}:{hashlib.sha256(raw).hexdigest()}"
                        for path, raw in snapshots.items()
                    ).encode()
                ).hexdigest(),
                "references": rows,
                "solver_call_lines_ast": calls,
                "solver_call_lines_token": token_calls,
                "independent_reference_identity_delta": [],
                "roles_are": "lexical locations and exact parsed data paths; semantic execution/history roles require owner inspection, never marker promotion",
                "source_and_population_unchanged": True,
                "scope_note": "Current mechanism/test/architecture files only; historical journal receipts and prose excluded explicitly. No exact-version reference is rewritten merely because it appears here.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
