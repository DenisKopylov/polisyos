#!/usr/bin/env python3
"""Measure local references and unresolved loaders for the DFK-01 schema family.

This census binds every selected source/config/resource byte stream to its output.
It is a static repository observation, not proof about arbitrary runtime dispatch or
published distributions; those boundaries remain explicit in the receipt.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
from bisect import bisect_right
from collections import Counter
from pathlib import Path
from typing import Any

from tools.lib.fs import measure_file_reads, measured_read_bytes

SCHEMA = "polisyos.schema_fqn_census.v1"
TARGETS = (
    "polisyos.foundry.domain.schema",
    "polisyos.foundry.domain.mechanisms",
    "polisyos.data_forge.kernel.schemas.codegen",
    "polisyos.data_forge.kernel.pipeline.schemas",
)

TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".pyx",
        ".pxd",
        ".json",
        ".jsonl",
        ".jsonc",
        ".json5",
        ".ndjson",
        ".geojson",
        ".ipynb",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".xml",
        ".xsd",
        ".dtd",
        ".svg",
        ".rss",
        ".xhtml",
        ".md",
        ".mdx",
        ".rst",
        ".txt",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".proto",
        ".thrift",
        ".graphql",
        ".gql",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".vue",
        ".svelte",
        ".html",
        ".jinja",
        ".j2",
        ".csv",
        ".lock",
        ".typed",
        ".properties",
        ".tf",
        ".hcl",
        ".nix",
        ".r",
        ".rmd",
        ".plist",
        ".env.example",
        ".gitignore",
        ".gitattributes",
    }
)
TEXT_NAMES = frozenset(
    {
        "Dockerfile",
        "Makefile",
        "GNUmakefile",
        "MANIFEST.in",
        "PKG-INFO",
        "uv.lock",
        "hatch.toml",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".pre-commit-config.yaml",
        ".python-version",
    }
)
KNOWN_BINARY_SUFFIXES = frozenset(
    {
        ".pyc",
        ".pyo",
        ".whl",
        ".egg",
        ".zip",
        ".gz",
        ".bz2",
        ".xz",
        ".zst",
        ".tar",
        ".7z",
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".mp3",
        ".mp4",
        ".mov",
        ".parquet",
        ".duckdb",
        ".sqlite",
        ".db",
        ".npy",
        ".npz",
        ".h5",
        ".hdf5",
        ".pickle",
        ".pkl",
        ".bin",
        ".dylib",
        ".so",
        ".dll",
    }
)

_FQN_PATTERNS = {
    target: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(target)}(?![A-Za-z0-9_])")
    for target in TARGETS
}
_RESOURCE_PATTERNS = {
    target: tuple(
        re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(resource)}(?![A-Za-z0-9_.-])")
        for resource in resources
    )
    for target, resources in {
        TARGETS[0]: (
            "foundry/domain/schema.py",
            "polisyos/foundry/domain/schema.py",
        ),
        TARGETS[1]: (
            "foundry/domain/mechanisms.py",
            "polisyos/foundry/domain/mechanisms.py",
        ),
        TARGETS[2]: (
            "data_forge/kernel/schemas/codegen.py",
            "polisyos/data_forge/kernel/schemas/codegen.py",
        ),
        TARGETS[3]: (
            "data_forge/kernel/pipeline/schemas",
            "polisyos/data_forge/kernel/pipeline/schemas",
        ),
    }.items()
}


def _git_paths(root: Path, *args: str) -> tuple[list[str], dict[str, Any]]:
    """Run a Git path query and retain its subprocess-boundary receipt."""
    command = ["git", *args, "-z", "--", "."]
    completed = subprocess.run(command, cwd=root, capture_output=True, check=False)
    metadata = {
        "command": command,
        "returncode": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "stdout_bytes": len(completed.stdout),
        "stderr_bytes": len(completed.stderr),
    }
    if completed.returncode:
        return [], metadata
    paths = sorted({os.fsdecode(item) for item in completed.stdout.split(b"\0") if item})
    return paths, metadata


def _git_status_paths(root: Path) -> tuple[list[str], dict[str, Any]]:
    """Read and parse the working-tree path set from Git's NUL-delimited status."""
    command = ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    completed = subprocess.run(command, cwd=root, capture_output=True, check=False)
    metadata = {
        "command": command,
        "returncode": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "stdout_bytes": len(completed.stdout),
        "stderr_bytes": len(completed.stderr),
    }
    if completed.returncode:
        return [], metadata

    # Porcelain v1 records status + path; renames add an extra NUL path. Keep both
    # old and new names in the changed denominator without interpreting quoting.
    chunks = completed.stdout.split(b"\0")
    names: set[str] = set()
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        i += 1
        if not chunk:
            continue
        record = os.fsdecode(chunk)
        if len(record) >= 4:
            names.add(record[3:])
        if record[:2] in {"R ", " R", "RM", "AM", " M", "M ", "C ", " C"}:
            if i < len(chunks) and chunks[i]:
                names.add(os.fsdecode(chunks[i]))
                i += 1
    prefix = subprocess.run(
        ["git", "rev-parse", "--show-prefix"], cwd=root, capture_output=True, check=False
    )
    metadata["prefix_command"] = ["git", "rev-parse", "--show-prefix"]
    metadata["prefix_returncode"] = prefix.returncode
    metadata["prefix_stdout_sha256"] = hashlib.sha256(prefix.stdout).hexdigest()
    metadata["prefix_stderr_sha256"] = hashlib.sha256(prefix.stderr).hexdigest()
    prefix_value = os.fsdecode(prefix.stdout).strip("\n")
    metadata["path_prefix"] = prefix_value
    if prefix.returncode == 0 and prefix_value:
        prefix_value = prefix_value.rstrip("/") + "/"
        names = {name.removeprefix(prefix_value) for name in names if name.startswith(prefix_value)}
    return sorted(names), metadata


def _is_selected_text(path: str) -> bool:
    candidate = Path(path)
    return candidate.name in TEXT_NAMES or candidate.suffix.lower() in TEXT_SUFFIXES


def _line_starts(text: str) -> list[int]:
    return [0, *(index + 1 for index, char in enumerate(text) if char == "\n")]


def _line_for_offset(line_starts: list[int], offset: int) -> int:
    return bisect_right(line_starts, offset)


def _target_for_module(value: str) -> str | None:
    return next(
        (target for target in TARGETS if value == target or value.startswith(target + ".")),
        None,
    )


def _module_name_for_path(path: str) -> str | None:
    parts = Path(path).parts
    try:
        source_index = parts.index("polisyos")
    except ValueError:
        return None
    module_parts = list(parts[source_index:])
    suffix = Path(path).suffix
    if suffix not in {".py", ".pyi", ".pyx", ".pxd"}:
        return None
    module_parts[-1] = Path(module_parts[-1]).stem
    if module_parts[-1] == "__init__":
        module_parts.pop()
    return ".".join(module_parts)


def _resolve_import_from(path: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    module_name = _module_name_for_path(path)
    if module_name is None:
        return None
    package_parts = module_name.split(".")[:-1]
    keep = len(package_parts) - (node.level - 1)
    if keep < 0:
        return None
    prefix = package_parts[:keep]
    if node.module:
        prefix.extend(node.module.split("."))
    return ".".join(prefix)


def _call_path(node: ast.expr, module_aliases: dict[str, str], imported_aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return imported_aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        prefix = _call_path(node.value, module_aliases, imported_aliases)
        if prefix in module_aliases:
            prefix = module_aliases[prefix]
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _literal_target(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        if all(isinstance(value, ast.Constant) and isinstance(value.value, str) for value in node.values):
            return "".join(str(value.value) for value in node.values)  # type: ignore[attr-defined]
    return None


def _scan_python(path: str, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    imports: list[dict[str, Any]] = []
    loader_sites: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    try:
        tree = ast.parse(text, filename=path)
    except (SyntaxError, ValueError, RecursionError) as error:
        return imports, loader_sites, [f"{path}: {type(error).__name__}: {error}"]

    module_aliases: dict[str, str] = {}
    imported_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                imported_name = alias.name if alias.asname else alias.name.split(".")[0]
                module_aliases[local_name] = alias.name if alias.asname else imported_name
        elif isinstance(node, ast.ImportFrom):
            module_name = _resolve_import_from(path, node)
            target = _target_for_module(module_name or "")
            if target:
                evidence = "absolute_import" if node.level == 0 else "relative_import"
                imports.append(
                    {
                        "target": target,
                        "imported_module": module_name,
                        "path": path,
                        "line": node.lineno,
                        "evidence_kind": evidence,
                        "imported_names": [alias.name for alias in node.names],
                    }
                )
            if node.module in {
                "importlib",
                "importlib.resources",
                "importlib.util",
                "importlib.machinery",
                "pkgutil",
                "builtins",
            }:
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    imported_aliases[local_name] = f"{node.module}.{alias.name}"

    loader_prefixes = {
        "builtins.__import__",
        "__import__",
        "importlib.import_module",
        "pkgutil.resolve_name",
        "importlib.util.find_spec",
        "importlib.util.spec_from_file_location",
        "importlib.machinery.SourceFileLoader",
        "importlib.resources.files",
        "importlib.resources.read_binary",
        "importlib.resources.read_text",
        "importlib.resources.open_binary",
        "importlib.resources.open_text",
        "importlib.resources.as_file",
        "pkgutil.get_data",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_path(node.func, module_aliases, imported_aliases)
        if call_name in {"__import__", "builtins.__import__", "importlib.import_module", "pkgutil.resolve_name"}:
            kind = "dynamic_module_loader"
        elif call_name in {
            "importlib.util.find_spec",
            "importlib.util.spec_from_file_location",
            "importlib.machinery.SourceFileLoader",
        }:
            kind = "filename_or_spec_loader"
        elif call_name.startswith("importlib.resources.") or call_name == "pkgutil.get_data":
            kind = "package_resource_loader"
        else:
            continue
        if call_name not in loader_prefixes and not call_name.startswith("importlib.resources."):
            continue
        argument = node.args[0] if node.args else None
        literal = _literal_target(argument)
        loader_sites.append(
            {
                "path": path,
                "line": node.lineno,
                "loader": call_name,
                "loader_kind": kind,
                "literal_target": literal,
                "status": "literal_target" if literal is not None else "unresolved_nonliteral_target",
            }
        )
    return imports, loader_sites, parse_errors


def _package_metadata(root: Path, selected_text: dict[str, str]) -> dict[str, Any]:
    pyproject = selected_text.get("pyproject.toml")
    hatch = selected_text.get("hatch.toml")
    metadata: dict[str, Any] = {
        "configuration_inputs": [
            name for name in ("pyproject.toml", "hatch.toml", "MANIFEST.in") if name in selected_text
        ],
        "wheel": "UNRUN",
        "sdist": "UNRUN",
        "configuration_observation": "not parsed; see hashed input receipts",
        "unresolved_by_construction": [
            "Hatch selection semantics, build backend execution, build isolation, and archive contents were not exercised.",
        ],
    }
    if pyproject is None and hatch is None:
        metadata["configuration_observation"] = "package configuration not selected or not present"
        return metadata
    relevant: dict[str, list[str]] = {}
    if hatch is not None:
        lines = hatch.splitlines()
        relevant["hatch_build_targets"] = [
            line.strip() for line in lines if any(token in line.lower() for token in ("[build", "packages", "include", "exclude"))
        ]
    if pyproject is not None:
        lines = pyproject.splitlines()
        relevant["pyproject_build_system_and_scripts"] = [
            line.strip()
            for line in lines
            if any(token in line.lower() for token in ("[build-system]", "build-backend", "requires =", "[project.scripts]", "polisyos"))
        ]
    metadata["configuration_observation"] = relevant
    metadata["selection_status"] = "configuration_bytes_read; archive membership unverified"
    return metadata


def collect_census(repo_root: Path) -> tuple[dict[str, Any], int]:
    root = repo_root.resolve()
    tracked, tracked_receipt = _git_paths(root, "ls-files", "--cached")
    untracked, untracked_receipt = _git_paths(root, "ls-files", "--others", "--exclude-standard")
    ignored, ignored_receipt = _git_paths(root, "ls-files", "--others", "--ignored", "--exclude-standard")
    changed, status_receipt = _git_status_paths(root)
    git_ok = all(
        receipt["returncode"] == 0
        for receipt in (tracked_receipt, untracked_receipt, ignored_receipt, status_receipt)
    ) and status_receipt.get("prefix_returncode") == 0

    tracked = sorted(set(tracked))
    untracked = sorted(set(untracked))
    ignored = sorted(set(ignored))
    selected = sorted(path for path in set(tracked) | set(untracked) if _is_selected_text(path))
    selected_ignored = sorted(path for path in ignored if _is_selected_text(path))
    excluded = sorted(
        {
            path: "known_binary_suffix" if Path(path).suffix.lower() in KNOWN_BINARY_SUFFIXES else "unsupported_filename_or_suffix"
            for path in set(tracked) | set(untracked)
            if not _is_selected_text(path)
        }.items()
    )

    read_paths: list[str] = []
    unreadable: list[str] = []
    rejected_paths: list[str] = []
    unsupported: list[dict[str, str]] = []
    package_inputs: dict[str, str] = {}
    decoded_input_count = 0
    all_imports: list[dict[str, Any]] = []
    all_loader_sites: list[dict[str, Any]] = []
    all_matches: list[dict[str, Any]] = []
    scanned_by_suffix: Counter[str] = Counter()
    parse_errors: list[str] = []

    with measure_file_reads(root) as measurement:
        for relative in selected:
            path = root / relative
            try:
                resolved_path = path.resolve()
            except (OSError, RuntimeError) as error:
                measurement.record(
                    path,
                    "resolve_path",
                    status="unreadable",
                    error=type(error).__name__,
                )
                unreadable.append(relative)
                continue
            if not resolved_path.is_relative_to(root):
                measurement.record(path, "read_bytes", status="rejected_outside_admitted_root")
                rejected_paths.append(relative)
                unsupported.append(
                    {
                        "path": relative,
                        "class": "symlink_escapes_admitted_root",
                        "detail": "The selected path resolves outside the census root and was not read.",
                    }
                )
                continue
            try:
                raw = measured_read_bytes(path)
            except OSError:
                unreadable.append(relative)
                continue
            read_paths.append(relative)
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                unsupported.append(
                    {"path": relative, "class": "selected_file_not_utf8", "detail": str(error)}
                )
                continue
            decoded_input_count += 1
            if "/" not in relative:
                package_inputs[relative] = content
            suffix = Path(relative).suffix.lower() or "<no suffix>"
            scanned_by_suffix[suffix] += 1
            line_starts = _line_starts(content)

            for target, pattern in _FQN_PATTERNS.items():
                for match in pattern.finditer(content):
                    all_matches.append(
                        {
                            "target": target,
                            "path": relative,
                            "line": _line_for_offset(line_starts, match.start()),
                            "evidence_kind": "serialized_or_text_reference",
                            "matched_value": target,
                        }
                    )
            for target, patterns in _RESOURCE_PATTERNS.items():
                for pattern in patterns:
                    for match in pattern.finditer(content):
                        all_matches.append(
                            {
                                "target": target,
                                "path": relative,
                                "line": _line_for_offset(line_starts, match.start()),
                                "evidence_kind": "resource_path_reference",
                                "matched_value": match.group(0),
                            }
                        )
            if Path(relative).suffix.lower() in {".py", ".pyi", ".pyx", ".pxd"}:
                imports, loader_sites, errors = _scan_python(relative, content)
                all_imports.extend(imports)
                all_loader_sites.extend(loader_sites)
                parse_errors.extend(errors)
        read_receipt = measurement.snapshot(
            complete_verdict=git_ok and not unreadable and not rejected_paths
        )

    for import_hit in all_imports:
        all_matches.append({**import_hit, "matched_value": import_hit["imported_module"]})
    all_matches.sort(key=lambda hit: (hit["target"], hit["path"], hit["line"], hit["evidence_kind"]))
    all_loader_sites.sort(key=lambda site: (site["path"], site["line"], site["loader"]))

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
        )
        head_value = head.stdout.strip() if head.returncode == 0 else None
        head_receipt = {
            "command": ["git", "rev-parse", "HEAD"],
            "returncode": head.returncode,
            "stdout_sha256": hashlib.sha256(head.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(head.stderr.encode()).hexdigest(),
        }
    except OSError as error:
        head_value = None
        head_receipt = {"error": type(error).__name__}

    package_artifacts = _package_metadata(root, package_inputs)
    any_incomplete = not git_ok or bool(unreadable) or bool(unsupported) or bool(parse_errors)
    result = (
        "partial_unreadable_input"
        if unreadable or not git_ok
        else "partial_unsupported_or_ambiguous"
        if unsupported or parse_errors
        else "complete_for_selected_local_text_inputs"
    )
    unresolved = [
        {
            "class": "unresolved_runtime_dispatch",
            "status": "present" if any(site["status"] == "unresolved_nonliteral_target" for site in all_loader_sites) else "not_established",
            "detail": "Static AST inspection cannot resolve runtime-computed module names, loader arguments, or effects of arbitrary code.",
        },
        {
            "class": "unselected_ignored_inputs",
            "status": "present" if selected_ignored else "none_enumerated",
            "detail": "Ignored files are enumerated by Git and deliberately not read; ignored candidate path names are listed separately.",
        },
        {
            "class": "unsupported_file_types",
            "status": "present" if excluded else "none_enumerated",
            "detail": "Binary and unsupported suffixes are excluded by the declared selector; see exact excluded paths and denominator.",
        },
        {
            "class": "wheel_sdist_archive_membership",
            "status": "UNRUN",
            "detail": "The census reads packaging configuration only; it does not build or inspect wheel/sdist archives.",
        },
        {
            "class": "external_consumers",
            "status": "not_established",
            "detail": "Local Git-visible repository census does not observe installed clients, external checkouts, registries, or network search.",
        },
    ]
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "result": result,
        "head": head_value,
        "git_enumeration": {
            "tracked": tracked_receipt,
            "untracked_nonignored": untracked_receipt,
            "ignored_nontracked": ignored_receipt,
            "working_tree_status": status_receipt,
            "head": head_receipt,
            "tracked_path_count": len(tracked),
            "untracked_path_count": len(untracked),
            "ignored_path_count": len(ignored),
            "complete_verdict": git_ok,
            "unresolved_by_construction": "Git refs/index/process reads are represented by command/output digests and path outputs; tools.lib.fs does not observe subprocess reads.",
        },
        "selection": {
            "selector": {
                "include_suffixes": sorted(TEXT_SUFFIXES),
                "include_names": sorted(TEXT_NAMES),
                "exclude_known_binary_suffixes": sorted(KNOWN_BINARY_SUFFIXES),
                "tracked_and_untracked_nonignored": True,
            },
            "tracked_path_count": len(tracked),
            "untracked_path_count": len(untracked),
            "ignored_path_count": len(ignored),
            "selected_path_count": len(selected),
            "tracked_paths": tracked,
            "untracked_paths": untracked,
            "ignored_paths": selected_ignored,
            "ignored_paths_total_candidate_count": len(selected_ignored),
            "selected_paths": selected,
            "excluded_paths": [{"path": path, "reason": reason} for path, reason in excluded],
            "excluded_path_count": len(excluded),
            "working_tree_changes": sorted(set(changed) & set(selected)),
            "unresolved_by_construction": [
                "The selected set is Git-visible tracked plus nonignored untracked files; ignored files, external consumers, and unregistered files outside this checkout are outside selection.",
                "File type classification is suffix/name based; unrecognized non-text formats may not be UTF-8-parsed.",
            ],
        },
        "read_receipt": read_receipt,
        "unreadable_paths": sorted(unreadable),
        "rejected_outside_root_paths": sorted(rejected_paths),
        "unsupported_or_ambiguous_inputs": unsupported + [
            {"path": "<python-ast>", "class": "unsupported_syntax_or_ast", "detail": error}
            for error in parse_errors
        ],
        "scanned_denominator": {
            "selected_paths": len(selected),
            "successful_byte_reads": len(read_paths),
            "decoded_utf8_inputs": decoded_input_count,
            "decoded_suffix_counts": dict(sorted(scanned_by_suffix.items())),
            "read_paths": read_paths,
            "unreadable_paths": sorted(unreadable),
        },
        "targets": [
            {
                "fqn": target,
                "local_source_path": target.removeprefix("polisyos.").replace(".", "/") + ("/__init__.py" if target.endswith(".schemas") else ".py"),
                "role": {
                    TARGETS[0]: "early compatibility DTO module; preserve pending explicit owner/consumer decision",
                    TARGETS[1]: "confirmed empty tombstone; do not retire until canonical world/simulator real consumer is established and owner decision admits the exact empty namespace change",
                    TARGETS[2]: "descriptor-only GeneratedSchemaModule surface; no generator/codegen role is inferred",
                    TARGETS[3]: "compatibility import alias; preserve object identities while pending alias-owner decision",
                }[target],
                "matches": [hit for hit in all_matches if hit["target"] == target],
            }
            for target in TARGETS
        ],
        "matches": all_matches,
        "dynamic_loader_sites": all_loader_sites,
        "package_artifacts": package_artifacts,
        "unresolved_by_construction": unresolved,
        "interpretation_boundary": {
            "criterion_verdict": "partial_coverage" if any_incomplete else "local_static_census_only",
            "complete_verdict_scope": "enumerated Git-visible, nonignored UTF-8 text inputs only",
            "not_a_retirement_authorization": True,
        },
    }
    return receipt, 2 if any_incomplete else 0


def main(argv: list[str] | None = None) -> int:
    """Emit one JSON receipt for a Git-visible local schema-FQN census."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt, code = collect_census(args.repo_root)
    except (OSError, ValueError) as error:
        receipt = {
            "schema": SCHEMA,
            "result": "partial_unreadable_input",
            "error": f"{type(error).__name__}: {error}",
            "unresolved_by_construction": [
                "Repository enumeration or root admission failed; no absence conclusion is available."
            ],
        }
        code = 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
