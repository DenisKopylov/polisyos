#!/usr/bin/env python3
"""Recompute the tracked static caller census for REQ-01 / LA-045.

Run from the repository root. The script reads source blobs and search results
from BASE_SHA, not from the working tree, and prints a compact JSON result.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from collections import Counter
from pathlib import PurePosixPath
from typing import Any

BASE_SHA = "c40d4acae1ce58b597267255026d9356565828fd"
COMPILER_PATH = "policy-engine/src/polisyos/data_requirement/compiler.py"
PACKAGE_PATH = "policy-engine/src/polisyos/data_requirement/__init__.py"
SYMBOLS = (
    "_data_families_from_obligation_graph",
    "_data_family_token_from_frontier_item",
    "_nested",
    "_normalised_family",
    "_slug_family",
    "_ordered_data_families",
    "_DATA_FAMILY_ORDER",
    "_digest",
)


def _git(*args: str, check: bool = True) -> str:
    # Arguments are fixed switches, pinned refs, or paths read from that ref;
    # pass them without a shell so tracked text cannot become executable input.
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        check=False,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _git_grep(*args: str) -> list[str]:
    return _git("grep", *args, check=False).splitlines()


def _tracked_paths() -> list[str]:
    raw = subprocess.check_output(  # noqa: S603
        ["git", "ls-tree", "-r", "-z", "--name-only", BASE_SHA]  # noqa: S607
    )
    return [path.decode("utf-8") for path in raw.split(b"\0") if path]


def _tracked_python_sources() -> tuple[dict[str, str], list[dict[str, str]]]:
    tree = subprocess.check_output(  # noqa: S603
        ["git", "ls-tree", "-r", "-z", BASE_SHA]  # noqa: S607
    )
    entries: list[tuple[str, bytes]] = []
    for record in tree.split(b"\0"):
        if not record:
            continue
        header, path_bytes = record.split(b"\t", 1)
        _mode, object_type, object_id = header.split()
        if object_type != b"blob" or not path_bytes.endswith((b".py", b".pyi")):
            continue
        entries.append((path_bytes.decode("utf-8"), object_id))

    batch_input = b"".join(object_id + b"\n" for _, object_id in entries)
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],  # noqa: S607
        input=batch_input,
        capture_output=True,
        check=True,
    ).stdout
    sources: dict[str, str] = {}
    read_errors: list[dict[str, str]] = []
    offset = 0
    for path, expected_object_id in entries:
        header_end = batch.find(b"\n", offset)
        if header_end < 0:
            raise RuntimeError(f"git cat-file header missing for {path}")
        returned_object_id, object_type, size_text = batch[offset:header_end].split()
        if returned_object_id != expected_object_id or object_type != b"blob":
            raise RuntimeError(f"git cat-file returned an unexpected object for {path}")
        content_start = header_end + 1
        content_end = content_start + int(size_text)
        content = batch[content_start:content_end]
        if batch[content_end : content_end + 1] != b"\n":
            raise RuntimeError(f"git cat-file content terminator missing for {path}")
        offset = content_end + 1
        try:
            sources[path] = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            read_errors.append({"path": path, "error": str(exc)})
    return sources, read_errors


def _blob(path: str) -> str:
    raw = subprocess.check_output(  # noqa: S603
        ["git", "show", f"{BASE_SHA}:{path}"]  # noqa: S607
    )
    return raw.decode("utf-8")


def _module_names(path: str) -> tuple[str, str]:
    posix = PurePosixPath(path)
    module = ".".join(posix.with_suffix("").parts)
    if module.endswith(".__init__"):
        module = module.removesuffix(".__init__")
        return module, module
    return module, module.rpartition(".")[0]


def _resolve_import(module: str, package: str, level: int, target: str | None) -> str:
    if not level:
        return target or ""
    package_parts = package.split(".") if package else []
    prefix = package_parts[: max(0, len(package_parts) - level + 1)]
    suffix = target.split(".") if target else []
    return ".".join((*prefix, *suffix))


def _dotted_name(node: ast.AST) -> tuple[str, tuple[str, ...]] | None:
    attrs: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        attrs.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return current.id, tuple(reversed(attrs))


def _static_exports(tree: ast.Module) -> tuple[set[str], set[str]]:
    definitions: set[str] = set()
    exports: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions.add(target.id)
                    if target.id == "__all__" and node.value is not None:
                        value = ast.literal_eval(node.value)
                        if isinstance(value, (list, tuple)) and all(
                            isinstance(item, str) for item in value
                        ):
                            exports.update(value)
    return definitions, exports


def main() -> None:
    tracked = _tracked_paths()
    path_counts = Counter(PurePosixPath(path).suffix for path in tracked)
    denominator = {
        "tracked_paths": len(tracked),
        "tracked_python_files": path_counts[".py"] + path_counts[".pyi"],
        "tracked_py": path_counts[".py"],
        "tracked_pyi": path_counts[".pyi"],
    }
    python_sources, read_errors = _tracked_python_sources()
    if len(python_sources) + len(read_errors) != denominator["tracked_python_files"]:
        raise RuntimeError("tracked Python source read count does not match the tree denominator")

    exact_hits: dict[str, dict[str, Any]] = {}
    candidate_paths: set[str] = set()
    for symbol in SYMBOLS:
        occurrences = _git_grep(
            "-I",
            "-o",
            "-w",
            "-e",
            symbol,
            BASE_SHA,
            "--",
            "*.py",
            "*.pyi",
        )
        files: set[str] = set()
        for row in occurrences:
            prefix = f"{BASE_SHA}:"
            if row.startswith(prefix):
                path = row[len(prefix) :].rsplit(":", 2)[0]
                files.add(path)
                candidate_paths.add(path)
        exact_hits[symbol] = {
            "python_occurrences": len(occurrences),
            "python_files": len(files),
            "paths": sorted(files),
        }

    caller_hits: list[dict[str, Any]] = []
    parse_errors = list(read_errors)
    for path, source in sorted(python_sources.items()):
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            parse_errors.append({"path": path, "error": str(exc)})
            continue

        module, package = _module_names(path)
        aliases: dict[str, str] = {}
        nodes = list(ast.walk(tree))
        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                target = _resolve_import(module, package, node.level, node.module)
                if target.endswith("data_requirement.compiler"):
                    for alias in node.names:
                        if alias.name == "*":
                            caller_hits.append(
                                {
                                    "path": path,
                                    "line": node.lineno,
                                    "kind": "star_import",
                                    "target": target,
                                }
                            )
                        elif alias.name in SYMBOLS:
                            caller_hits.append(
                                {
                                    "path": path,
                                    "line": node.lineno,
                                    "kind": "direct_import",
                                    "target": target,
                                    "symbol": alias.name,
                                }
                            )
                        aliases[alias.asname or alias.name] = f"{target}.{alias.name}"
                elif target.endswith("data_requirement"):
                    for alias in node.names:
                        if alias.name == "compiler":
                            aliases[alias.asname or alias.name] = f"{target}.compiler"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    aliases[local] = alias.name if alias.asname else local
                    if alias.name.endswith("data_requirement.compiler"):
                        aliases[alias.name] = alias.name

        def module_expression(
            node: ast.AST, alias_map: dict[str, str] = aliases
        ) -> str | None:
            dotted = _dotted_name(node)
            if dotted is None:
                return None
            root, attrs = dotted
            target = alias_map.get(root)
            if target is None:
                return None
            return ".".join((target, *attrs))

        for node in nodes:
            if isinstance(node, ast.Assign):
                value = node.value
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Attribute)
                    and value.func.attr in {"import_module", "__import__"}
                    and value.args
                    and isinstance(value.args[0], ast.Constant)
                    and isinstance(value.args[0].value, str)
                    and value.args[0].value.endswith("data_requirement.compiler")
                ):
                    for assigned in node.targets:
                        if isinstance(assigned, ast.Name):
                            aliases[assigned.id] = value.args[0].value
            elif isinstance(node, ast.Attribute) and node.attr in SYMBOLS:
                target = module_expression(node.value)
                if target and target.endswith("data_requirement.compiler"):
                    caller_hits.append(
                        {
                            "path": path,
                            "line": node.lineno,
                            "kind": "module_attribute",
                            "target": target,
                            "symbol": node.attr,
                        }
                    )
            elif isinstance(node, ast.Call):
                func_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if (
                    func_name in {"import_module", "__import__"}
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and node.args[0].value.endswith("data_requirement.compiler")
                ):
                    caller_hits.append(
                        {
                            "path": path,
                            "line": node.lineno,
                            "kind": "literal_string_loader",
                            "target": node.args[0].value,
                        }
                    )
                if (
                    func_name == "getattr"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value in SYMBOLS
                ):
                    target = module_expression(node.args[0])
                    if target and target.endswith("data_requirement.compiler"):
                        caller_hits.append(
                            {
                                "path": path,
                                "line": node.lineno,
                                "kind": "literal_getattr",
                                "target": target,
                                "symbol": node.args[1].value,
                            }
                        )

    module_files = set(
        _git_grep(
            "-I",
            "-l",
            "-F",
            "-e",
            "polisyos.data_requirement.compiler",
            BASE_SHA,
            "--",
        )
    )
    module_files |= set(
        _git_grep(
            "-I",
            "-l",
            "-F",
            "-e",
            "data_requirement.compiler",
            BASE_SHA,
            "--",
        )
    )
    module_files = {
        row[len(BASE_SHA) + 1 :] if row.startswith(f"{BASE_SHA}:") else row
        for row in module_files
    }
    module_symbol_intersections: dict[str, list[str]] = {}
    for symbol in SYMBOLS:
        symbol_files = {
            row[len(BASE_SHA) + 1 :]
            for row in _git_grep(
                "-I", "-l", "-w", "-e", symbol, BASE_SHA, "--"
            )
            if row.startswith(f"{BASE_SHA}:")
        }
        module_symbol_intersections[symbol] = sorted(module_files & symbol_files)

    compiler_source = _blob(COMPILER_PATH)
    package_source = _blob(PACKAGE_PATH)
    compiler_tree = ast.parse(compiler_source, filename=COMPILER_PATH)
    package_tree = ast.parse(package_source, filename=PACKAGE_PATH)
    compiler_names, compiler_exports = _static_exports(compiler_tree)
    _, package_exports = _static_exports(package_tree)
    result = {
        "base_sha": BASE_SHA,
        "tracked_denominator": denominator,
        "symbol_python_exact_hits": exact_hits,
        "exact_symbol_candidate_python_files": len(candidate_paths),
        "ast_files_scanned": len(python_sources),
        "ast_parse_errors": parse_errors,
        "ast_caller_hits": caller_hits,
        "module_string_files": len(module_files),
        "module_string_and_symbol_same_file": module_symbol_intersections,
        "compiler_source": {
            "path": COMPILER_PATH,
            "blob_sha": _git("rev-parse", f"{BASE_SHA}:{COMPILER_PATH}").strip(),
            "historical_names_defined": sorted(set(SYMBOLS) & compiler_names),
            "historical_names_exported": sorted(set(SYMBOLS) & compiler_exports),
        },
        "package_facade": {
            "path": PACKAGE_PATH,
            "blob_sha": _git("rev-parse", f"{BASE_SHA}:{PACKAGE_PATH}").strip(),
            "historical_names_exported": sorted(set(SYMBOLS) & package_exports),
        },
        "scope_limit": (
            "All tracked .py/.pyi exact symbol tokens and AST imports, plus literal compiler "
            "module strings across tracked paths. Nonliteral/dynamically constructed loader paths "
            "and consumers outside this repository are unresolved by construction."
        ),
    }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
