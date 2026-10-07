"""Census retired compiler references in every tracked Python blob at a Git ref."""

from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

def find_repository_root(script_path: Path) -> Path:
    """Find the worktree root so the committed copy is location-independent."""

    for candidate in script_path.resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError(f"could not locate the Git worktree above {script_path}")


REPO_ROOT = find_repository_root(Path(__file__))
COMPILER_MODULE = "polisyos.data_requirement.compiler"
PACKAGE_MODULE = "polisyos.data_requirement"
RETIRED_NAMES = frozenset(
    {
        "_data_families_from_obligation_graph",
        "_data_family_token_from_frontier_item",
        "_nested",
        "_normalised_family",
        "_slug_family",
        "_ordered_data_families",
        "_DATA_FAMILY_ORDER",
        "_digest",
    }
)
TARGET_MODULES = frozenset({COMPILER_MODULE, PACKAGE_MODULE})


def git_bytes(*arguments: str, input_bytes: bytes | None = None) -> bytes:
    """Run a read-only Git command and return its complete stdout bytes."""

    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("git executable was not found on PATH")
    # The executable is resolved from PATH; arguments are fixed Git read-only commands.
    result = subprocess.run(  # noqa: S603
        [git_executable, "--no-optional-locks", "-C", str(REPO_ROOT), *arguments],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"git command failed ({result.returncode}): {arguments!r}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
    return result.stdout


def selected_tree_entries(ref: str) -> tuple[str, str, list[tuple[str, str, str]]]:
    """Return the resolved commit/tree and every tracked `.py`/`.pyi` blob path."""

    commit = git_bytes("rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    tree = git_bytes("rev-parse", "--verify", f"{commit}^{{tree}}").decode().strip()
    listing = git_bytes("ls-tree", "-rz", "--full-tree", commit)
    entries: list[tuple[str, str, str]] = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = header.decode("ascii").split()
        if kind != "blob" or not raw_path.endswith((b".py", b".pyi")):
            continue
        path = raw_path.decode("utf-8", errors="strict")
        entries.append((path, mode, object_id))
    return commit, tree, entries


def read_blobs(object_ids: set[str]) -> dict[str, bytes]:
    """Read each selected blob once through Git's batch object reader."""

    request = b"".join(f"{object_id}\n".encode("ascii") for object_id in sorted(object_ids))
    output = git_bytes("cat-file", "--batch", input_bytes=request)
    blobs: dict[str, bytes] = {}
    cursor = 0
    while cursor < len(output):
        header_end = output.index(b"\n", cursor)
        object_id, kind, size_text = output[cursor:header_end].decode("ascii").split()
        if kind != "blob":
            raise RuntimeError(f"selected object is not a blob: {object_id} {kind}")
        size = int(size_text)
        content_start = header_end + 1
        content_end = content_start + size
        if content_end >= len(output) or output[content_end : content_end + 1] != b"\n":
            raise RuntimeError(f"truncated Git blob response for {object_id}")
        blobs[object_id] = output[content_start:content_end]
        cursor = content_end + 1
    if blobs.keys() != object_ids:
        raise RuntimeError("Git batch response did not return the complete selected blob set")
    return blobs


def package_context(path: str, package_init_paths: set[str]) -> str:
    """Infer a file's Python package context from tracked `__init__.py` paths."""

    context: list[str] = []
    prefix: list[str] = []
    for part in PurePosixPath(path).parts[:-1]:
        prefix.append(part)
        if "/".join((*prefix, "__init__.py")) in package_init_paths:
            context.append(part)
        else:
            context.clear()
    return ".".join(context)


def dotted_name(node: ast.AST) -> str | None:
    """Return the dotted name represented by a Name/Attribute expression."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def canonical_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    """Resolve a dotted expression through statically imported module aliases."""

    raw = dotted_name(node)
    if raw is None:
        return None
    parts = raw.split(".")
    for prefix_length in range(len(parts), 0, -1):
        prefix = ".".join(parts[:prefix_length])
        if prefix in aliases:
            suffix = ".".join(parts[prefix_length:])
            return f"{aliases[prefix]}.{suffix}" if suffix else aliases[prefix]
    return raw


def resolved_import(node: ast.ImportFrom, package: str) -> str:
    """Resolve absolute and relative import statements to a module name."""

    if node.level == 0:
        return node.module or ""
    if not package:
        return ""
    relative = "." * node.level + (node.module or "")
    try:
        return importlib.util.resolve_name(relative, package)
    except ImportError:
        return ""


def source_findings(
    path: str,
    source: str,
    package_init_paths: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Parse and report literal/import/reflection references to retired names."""

    tree = ast.parse(source, filename=path, type_comments=True)
    package = package_context(path, package_init_paths)
    aliases: dict[str, str] = {}
    findings: dict[str, list[dict[str, Any]]] = {
        "compiler_api_imports": [],
        "imports": [],
        "module_imports": [],
        "qualified_attributes": [],
        "imported_name_uses": [],
        "reflection_literals": [],
        "computed_module_getattr": [],
        "dynamic_import_literals": [],
        "computed_import_targets": [],
        "retired_name_literals": [],
        "compiler_path_literals": [],
        "wildcard_imports": [],
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == COMPILER_MODULE or alias.name.startswith(f"{COMPILER_MODULE}."):
                    findings["module_imports"].append(
                        {"path": path, "line": node.lineno, "module": alias.name}
                    )
                    if alias.asname:
                        aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = resolved_import(node, package)
            if module in TARGET_MODULES:
                for alias in node.names:
                    findings["compiler_api_imports"].append(
                        {
                            "path": path,
                            "line": node.lineno,
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname,
                        }
                    )
                    if module == COMPILER_MODULE and alias.name == "*":
                        findings["wildcard_imports"].append(
                            {"path": path, "line": node.lineno, "module": module}
                        )
                    elif module == COMPILER_MODULE:
                        if alias.name in RETIRED_NAMES:
                            findings["imports"].append(
                                {
                                    "path": path,
                                    "line": node.lineno,
                                    "name": alias.name,
                                    "alias": alias.asname,
                                }
                            )
                        aliases[alias.asname or alias.name] = f"{module}.{alias.name}"
            if module == PACKAGE_MODULE:
                for alias in node.names:
                    if alias.name == "compiler":
                        aliases[alias.asname or alias.name] = COMPILER_MODULE

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and canonical_name(node, aliases) in {
            f"{COMPILER_MODULE}.{name}" for name in RETIRED_NAMES
        }:
            findings["imported_name_uses"].append(
                {"path": path, "line": node.lineno, "name": canonical_name(node, aliases)}
            )
        if isinstance(node, ast.Attribute):
            parent = canonical_name(node.value, aliases)
            if parent in TARGET_MODULES and node.attr in RETIRED_NAMES:
                findings["qualified_attributes"].append(
                    {"path": path, "line": node.lineno, "module": parent, "name": node.attr}
                )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in RETIRED_NAMES:
                findings["retired_name_literals"].append(
                    {"path": path, "line": node.lineno, "name": node.value}
                )
            if node.value == COMPILER_MODULE or node.value.startswith(f"{COMPILER_MODULE}."):
                findings["compiler_path_literals"].append(
                    {"path": path, "line": node.lineno, "value": node.value}
                )
        if not isinstance(node, ast.Call):
            continue

        called = canonical_name(node.func, aliases)
        if called == "getattr" and len(node.args) >= 2:
            target = canonical_name(node.args[0], aliases)
            if target in TARGET_MODULES:
                name_node = node.args[1]
                if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
                    if name_node.value in RETIRED_NAMES:
                        findings["reflection_literals"].append(
                            {
                                "path": path,
                                "line": node.lineno,
                                "module": target,
                                "name": name_node.value,
                            }
                        )
                else:
                    findings["computed_module_getattr"].append(
                        {"path": path, "line": node.lineno, "module": target}
                    )

        if called in {"importlib.import_module", "import_module", "__import__"}:
            module_arg = node.args[0] if node.args else None
            static_module = (
                module_arg.value
                if isinstance(module_arg, ast.Constant) and isinstance(module_arg.value, str)
                else None
            )
            is_target_module = static_module in TARGET_MODULES or (
                static_module is not None and static_module.startswith(f"{COMPILER_MODULE}.")
            )
            if is_target_module:
                findings["dynamic_import_literals"].append(
                    {"path": path, "line": node.lineno, "module": static_module}
                )
            elif static_module is None:
                findings["computed_import_targets"].append(
                    {"path": path, "line": node.lineno, "call": called}
                )
            if called == "__import__":
                fromlist = node.args[3] if len(node.args) >= 4 else None
                fromlist = next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "fromlist"),
                    fromlist,
                )
            else:
                fromlist = None
            if fromlist is not None:
                if isinstance(fromlist, (ast.List, ast.Tuple)):
                    for item in fromlist.elts:
                        if (
                            is_target_module
                            and isinstance(item, ast.Constant)
                            and item.value in RETIRED_NAMES
                        ):
                            findings["reflection_literals"].append(
                                {
                                    "path": path,
                                    "line": node.lineno,
                                    "module": "__import__ fromlist",
                                    "name": item.value,
                                }
                            )
                elif not isinstance(fromlist, ast.Constant):
                    findings["computed_import_targets"].append(
                        {"path": path, "line": node.lineno, "call": "__import__ fromlist"}
                    )
    return findings


def self_check() -> None:
    """Prove static imports and reflection literals in the selector are detected."""

    probe = """\
from polisyos.data_requirement.compiler import _digest as old_digest
import polisyos.data_requirement.compiler as compiler
getattr(compiler, "_DATA_FAMILY_ORDER")
__import__("polisyos.data_requirement.compiler", fromlist=["_nested"])
"""
    findings = source_findings(
        "synthetic-positive-control.py",
        probe,
        {"polisyos/__init__.py", "polisyos/data_requirement/__init__.py"},
    )
    if (
        not findings["imports"]
        or not findings["reflection_literals"]
        or len(findings["reflection_literals"]) < 2
    ):
        raise RuntimeError("synthetic positive control did not exercise the static detector")


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    result: dict[str, Any] = {
        "counterexample": (
            "A tracked Python source imports a retired compiler name, qualifies it through the "
            "compiler module, or reflects on it with a static name."
        ),
        "inputs": {
            "repository_root": str(REPO_ROOT),
            "requested_ref": ref,
            "operations": [
                "git rev-parse --verify <ref>^{commit}",
                "git rev-parse --verify <commit>^{tree}",
                "git ls-tree -rz --full-tree <commit>",
                "git cat-file --batch <unique selected blob IDs>",
                "UTF-8 decode and ast.parse(type_comments=True) for every selected path",
            ],
            "selector": "all tracked Git blob paths ending in .py or .pyi",
            "exclusions": [],
        },
        "predicate_class": "recomputed",
        "unresolved_by_construction": [
            "computed_import_or_reflection_name: names assembled at runtime or selected from data",
            "external_or_untracked_consumer: packages, plugins, generated code, and untracked "
            "files",
            "non_python_consumer: configuration, notebooks, shell, and other non-.py/.pyi inputs",
            "exec_eval_native_or_service_dispatch: behavior outside statically parsed Python AST",
        ],
    }
    try:
        commit, tree, entries = selected_tree_entries(ref)
        blobs = read_blobs({object_id for _path, _mode, object_id in entries})
        package_init_paths = {
            path for path, _mode, _object_id in entries if PurePosixPath(path).name == "__init__.py"
        }
        file_types = Counter(PurePosixPath(path).suffix for path, _mode, _object_id in entries)
        all_findings: dict[str, list[dict[str, Any]]] = {}
        parse_errors: list[dict[str, str]] = []
        for path, _mode, object_id in entries:
            try:
                source = blobs[object_id].decode("utf-8", errors="strict")
                file_findings = source_findings(path, source, package_init_paths)
            except (UnicodeDecodeError, SyntaxError) as exc:
                parse_errors.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
                continue
            for category, rows in file_findings.items():
                all_findings.setdefault(category, []).extend(rows)
        result["source"] = {
            "commit": commit,
            "tree": tree,
            "selected_path_count": len(entries),
            "selected_unique_blob_count": len(blobs),
            "file_type_denominator": {
                ".py": file_types[".py"],
                ".pyi": file_types[".pyi"],
            },
            "read_blob_count": len(blobs),
            "parsed_path_count": len(entries) - len(parse_errors),
            "parse_error_count": len(parse_errors),
            "parse_errors": parse_errors,
        }
        result["findings"] = {
            category: {"count": len(rows), "rows": rows}
            for category, rows in sorted(all_findings.items())
        }
        api_imports = all_findings.get("compiler_api_imports", [])
        from_import_statements = {(row["path"], row["line"]) for row in api_imports}
        module_imports = all_findings.get("module_imports", [])
        module_import_statements = {(row["path"], row["line"]) for row in module_imports}
        import_statements = from_import_statements | module_import_statements
        result["active_api_import_summary"] = {
            "symbol_import_rows": len(api_imports),
            "from_import_statement_count": len(from_import_statements),
            "module_import_statement_count": len(module_import_statements),
            "all_import_statement_count": len(import_statements),
            "unique_path_count": len({path for path, _line in import_statements}),
        }
        result["verdict"] = "UNRUN" if parse_errors else "complete_for_selected_tracked_python"
        self_check()
        result["positive_control"] = (
            "passed: imported helper, module reflection, and dynamic fromlist"
        )
        if parse_errors:
            result["absence_result"] = "partial_coverage; unreadable or unparsable selected member"
            status = 2
        else:
            result["absence_result"] = (
                "no statically resolved tracked Python caller found"
                if not any(
                    result["findings"][category]["count"]
                    for category in (
                        "imports",
                        "qualified_attributes",
                        "imported_name_uses",
                        "reflection_literals",
                    )
                )
                else "one or more tracked Python references found"
            )
            status = 0
    except Exception as exc:  # The report must distinguish an incomplete run from a zero.
        result["verdict"] = "UNRUN"
        result["absence_result"] = "undecided; Git input, decode, or scanner operation failed"
        result["failure"] = f"{type(exc).__name__}: {exc}"
        status = 2
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
