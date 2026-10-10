#!/usr/bin/env python3
"""Measure local references and unresolved loaders for the DFK-01 schema family.

This census binds every selected source/config/resource byte stream to its output.
It is a static repository observation, not proof about arbitrary runtime dispatch or
published distributions; those boundaries remain explicit in the receipt.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import textwrap
import xml.etree.ElementTree as ET
import zlib
from bisect import bisect_right
from collections import Counter
from pathlib import Path
from typing import Any

from tools.lib.fs import measure_file_reads, measured_read_bytes

SCHEMA = "polisyos.schema_fqn_census.v2"
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
        ".css",
        ".rego",
        ".log",
        ".tmpl",
        ".tpl",
        ".patch",
        ".cypher",
        ".fixture",
        ".example",
        ".blob",
        ".mdc",
        ".reproducible",
        ".retired",
        ".sha256",
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
        ".tsv",
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
        ".nvmrc",
        ".yamllint",
        ".prettierignore",
        "LICENSE",
        "OWNER",
        ".gitkeep",
        "SHA256SUMS",
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
        ".docx",
        ".webm",
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
        ".sqlite-wal",
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

_GZIP_MAGIC = b"\x1f\x8b"
_MAX_GZIP_TEXT_BYTES = 64 * 1024 * 1024


class _GzipTextExpansionLimitError(ValueError):
    """A selected compressed text input expands beyond the bounded decoder limit."""


class _CompressedTextWrongSuffixError(ValueError):
    """A compressed stream is not a declared JUnit XML input."""


class _InvalidCompressedJUnitXmlError(ValueError):
    """A compressed JUnit XML stream is not valid UTF-8 XML."""


def _decode_selected_bytes(
    path: str, raw: bytes
) -> tuple[bytes, dict[str, object] | None]:
    """Decode ordinary bytes or a bounded, well-formed compressed JUnit report."""
    if not raw.startswith(_GZIP_MAGIC):
        return raw, None
    if not path.lower().endswith(".junit.xml"):
        raise _CompressedTextWrongSuffixError(
            "gzip compression is supported only for selected .junit.xml inputs"
        )
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as stream:
        decoded = stream.read(_MAX_GZIP_TEXT_BYTES + 1)
    if len(decoded) > _MAX_GZIP_TEXT_BYTES:
        raise _GzipTextExpansionLimitError(
            f"gzip text expands beyond {_MAX_GZIP_TEXT_BYTES} bytes"
        )
    try:
        decoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _InvalidCompressedJUnitXmlError(
            "decompressed .junit.xml is not UTF-8"
        ) from error
    try:
        document = ET.fromstring(decoded)
    except (ET.ParseError, LookupError, ValueError) as error:
        raise _InvalidCompressedJUnitXmlError(
            f"decompressed .junit.xml is malformed: {error}"
        ) from error
    if document.tag not in {"testsuite", "testsuites"}:
        raise _InvalidCompressedJUnitXmlError(
            f"unsupported JUnit XML root element: {document.tag}"
        )
    return decoded, {
        "compression": "gzip",
        "raw_byte_count": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "decoded_byte_count": len(decoded),
        "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
    }


def _source_snapshot_role(path: str) -> str | None:
    """Return the pair role for a conventionally named archived source snapshot."""
    match = re.search(r"(?:[._-](?P<role>preimage|postimage))\.py$", Path(path).name)
    return match.group("role") if match is not None else None


def _read_selected_json(
    root: Path,
    relative: str,
    selected_paths: set[str],
    cache: dict[str, tuple[dict[str, Any], str, int] | None],
) -> tuple[dict[str, Any], str, int] | None:
    """Read a selected JSON record once through the census read-measurement API."""
    if relative not in selected_paths:
        return None
    if relative not in cache:
        try:
            raw = measured_read_bytes(root / relative)
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            cache[relative] = None
        else:
            cache[relative] = (
                (value, hashlib.sha256(raw).hexdigest(), len(raw))
                if isinstance(value, dict)
                else None
            )
    return cache[relative]


def _indexed_artifact_entries(
    root: Path,
    index: dict[str, Any],
    relative: str,
    sha256: str,
    byte_count: int,
) -> list[dict[str, Any]]:
    """Return exact local path, digest, and byte-count entries from an index."""
    artifacts = index.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    allowed_paths = {relative, f"{root.name}/{relative}"}
    return [
        entry
        for entry in artifacts
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and entry.get("path") in allowed_paths
        and entry.get("sha256") == sha256
        and type(entry.get("bytes")) is int
        and entry.get("bytes") == byte_count
    ]


def _is_sha256_digest(value: object) -> bool:
    """Return whether a pair record contains a lowercase SHA-256 digest."""
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _source_pair_members(
    root: Path,
    relative: str,
    source_role: str,
    source_sha256: str,
    raw: bytes,
    manifest: dict[str, Any],
    index: dict[str, Any],
    selected_paths: set[str],
) -> tuple[str, list[dict[str, str]]] | None:
    """Resolve and content-bind both members of one supported source-pair record."""
    source_path = Path(relative)
    member_names: dict[str, str]
    member_hashes: dict[str, str]
    member_original_paths: dict[str, str | None]
    if manifest.get("schema") == "ORCH04-B114-matched-property-removal-v1":
        changes = manifest.get("changes")
        if not isinstance(changes, list):
            return None
        candidates: list[
            tuple[dict[str, str], dict[str, str], dict[str, str | None]]
        ] = []
        for change in changes:
            if not isinstance(change, dict):
                continue
            preimage = change.get("preimage")
            postimage = change.get("postimage")
            preimage_sha256 = change.get("preimage_sha256")
            postimage_sha256 = change.get("postimage_sha256")
            if (
                not isinstance(preimage, str)
                or not isinstance(postimage, str)
                or not _is_sha256_digest(preimage_sha256)
                or not _is_sha256_digest(postimage_sha256)
            ):
                continue
            names = {
                "preimage": Path(preimage).name,
                "postimage": Path(postimage).name,
            }
            hashes = {"preimage": preimage_sha256, "postimage": postimage_sha256}
            original_paths: dict[str, str | None] = {
                "preimage": preimage,
                "postimage": postimage,
            }
            if (
                _source_snapshot_role(names["preimage"]) != "preimage"
                or _source_snapshot_role(names["postimage"]) != "postimage"
                or names[source_role] != source_path.name
                or hashes[source_role] != source_sha256
            ):
                continue
            candidates.append((names, hashes, original_paths))
        if len(candidates) != 1:
            return None
        pair_format = "ORCH04-B114-matched-property-removal-v1"
        member_names, member_hashes, member_original_paths = candidates[0]
    elif (
        "schema" not in manifest
        and manifest.get("source_files_changed") is False
        and isinstance(manifest.get("qualification"), str)
        and bool(manifest["qualification"].strip())
        and isinstance(manifest.get("semantic_expected_failure"), str)
        and bool(manifest["semantic_expected_failure"].strip())
        and type(manifest.get("actual_accepted")) is int
        and type(manifest.get("positive_expected_accepted")) is int
    ):
        preimage_sha256 = manifest.get("preimage_sha256")
        postimage_sha256 = manifest.get("postimage_sha256")
        if not _is_sha256_digest(preimage_sha256) or not _is_sha256_digest(
            postimage_sha256
        ):
            return None
        member_hashes = {
            "preimage": preimage_sha256,
            "postimage": postimage_sha256,
        }
        if member_hashes[source_role] != source_sha256:
            return None
        role_match = re.search(
            r"([._-])(?P<role>preimage|postimage)(\.py)$", source_path.name
        )
        if role_match is None or role_match.group("role") != source_role:
            return None
        other_role = "postimage" if source_role == "preimage" else "preimage"
        other_name = (
            source_path.name[: role_match.start("role")]
            + other_role
            + role_match.group(3)
        )
        member_names = {source_role: source_path.name, other_role: other_name}
        member_original_paths = {"preimage": None, "postimage": None}
        pair_format = "legacy-b114-paired-hash-record"
    else:
        return None

    if pair_format == "ORCH04-B114-matched-property-removal-v1":
        preimage_original_path = member_original_paths["preimage"]
        postimage_original_path = member_original_paths["postimage"]
        if (
            not isinstance(preimage_original_path, str)
            or not isinstance(postimage_original_path, str)
            or not Path(preimage_original_path).is_absolute()
            or not Path(postimage_original_path).is_absolute()
            or Path(preimage_original_path).name != member_names["preimage"]
            or Path(postimage_original_path).name != member_names["postimage"]
            or Path(preimage_original_path).parent
            != Path(postimage_original_path).parent
        ):
            return None
    member_receipts: list[dict[str, str]] = []
    for role in ("preimage", "postimage"):
        member_relative = (source_path.parent / member_names[role]).as_posix()
        if member_relative not in selected_paths:
            return None
        member_path = root / member_relative
        if member_path.is_symlink():
            return None
        try:
            member_resolved = member_path.resolve()
        except (OSError, RuntimeError):
            return None
        if (
            not member_resolved.is_relative_to(root)
            or member_resolved.relative_to(root).as_posix() != member_relative
        ):
            return None
        if member_relative == relative:
            member_raw = raw
        else:
            try:
                member_raw = measured_read_bytes(member_path)
            except OSError:
                return None
        member_sha256 = hashlib.sha256(member_raw).hexdigest()
        if member_sha256 != member_hashes[role]:
            return None
        index_entries = _indexed_artifact_entries(
            root, index, member_relative, member_sha256, len(member_raw)
        )
        if len(index_entries) != 1:
            return None
        indexed_original_path = index_entries[0].get("original_path")
        declared_original_path = member_original_paths[role]
        if declared_original_path is not None:
            if indexed_original_path != declared_original_path:
                return None
        elif (
            not isinstance(indexed_original_path, str)
            or not Path(indexed_original_path).is_absolute()
            or Path(indexed_original_path).name != Path(member_relative).name
            or _source_snapshot_role(indexed_original_path) != role
        ):
            return None
        member_receipts.append(
            {
                "role": role,
                "path": member_relative,
                "original_path": indexed_original_path,
                "sha256": member_sha256,
            }
        )
    if pair_format == "legacy-b114-paired-hash-record":
        original_paths = {
            item["role"]: item["original_path"] for item in member_receipts
        }
        preimage_original_path = original_paths.get("preimage")
        postimage_original_path = original_paths.get("postimage")
        if (
            not isinstance(preimage_original_path, str)
            or not isinstance(postimage_original_path, str)
            or Path(preimage_original_path).parent
            != Path(postimage_original_path).parent
        ):
            return None
    return pair_format, member_receipts


def _indexed_evidence_snapshot(
    root: Path,
    relative: str,
    resolved_relative: str,
    raw: bytes,
    selected_paths: set[str],
    json_cache: dict[str, tuple[dict[str, Any], str, int] | None],
) -> dict[str, Any] | None:
    """Require content-bound archive and source-pair records before excerpt parsing."""
    source_path = Path(relative)
    parts = source_path.parts
    if (
        parts[:2] != ("docs", "research")
        or parts[0] in {"src", "tests", "tools"}
        or resolved_relative != relative
        or source_path.is_symlink()
        or _source_snapshot_role(relative) is None
    ):
        return None

    source_sha256 = hashlib.sha256(raw).hexdigest()
    source_role = _source_snapshot_role(relative)
    if source_role is None:
        return None

    index_binding: tuple[str, str, dict[str, Any]] | None = None
    for evidence_dir in (root / relative).parents:
        if evidence_dir == root:
            break
        if evidence_dir.name != "evidence" or evidence_dir.is_symlink():
            continue
        index_relative = (
            (evidence_dir / "artifact-index.json").relative_to(root).as_posix()
        )
        index_path = root / index_relative
        if index_path.is_symlink():
            continue
        loaded_index = _read_selected_json(
            root, index_relative, selected_paths, json_cache
        )
        if loaded_index is None:
            continue
        index, index_sha256, _ = loaded_index
        schema = index.get("schema")
        artifacts = index.get("artifacts")
        if (
            not isinstance(schema, str)
            or not schema.endswith(".evidence-index.v1")
            or not isinstance(artifacts, list)
        ):
            continue
        allowed_index_paths = {relative, f"{root.name}/{relative}"}
        matching_entries = [
            entry
            for entry in artifacts
            if isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and entry.get("path") in allowed_index_paths
            and entry.get("sha256") == source_sha256
            and type(entry.get("bytes")) is int
            and entry.get("bytes") == len(raw)
        ]
        if len(matching_entries) == 1:
            index_binding = (index_relative, index_sha256, index)
            break
    if index_binding is None:
        return None

    matching_manifests: list[tuple[str, str, str, str, list[dict[str, str]]]] = []
    parent_path = root / source_path.parent
    try:
        candidate_manifests = sorted(parent_path.glob("*.json"))
    except OSError:
        return None
    _, _, index = index_binding
    for manifest_path in candidate_manifests:
        manifest_relative = manifest_path.relative_to(root).as_posix()
        if manifest_relative not in selected_paths or manifest_path.is_symlink():
            continue
        loaded_manifest = _read_selected_json(
            root, manifest_relative, selected_paths, json_cache
        )
        if loaded_manifest is None:
            continue
        manifest, manifest_sha256, manifest_byte_count = loaded_manifest
        pair_binding = _source_pair_members(
            root,
            relative,
            source_role,
            source_sha256,
            raw,
            manifest,
            index,
            selected_paths,
        )
        if pair_binding is None:
            continue
        manifest_entries = _indexed_artifact_entries(
            root, index, manifest_relative, manifest_sha256, manifest_byte_count
        )
        if len(manifest_entries) != 1:
            continue
        manifest_original_path = manifest_entries[0].get("original_path")
        member_original_paths = {
            item["role"]: item["original_path"] for item in pair_binding[1]
        }
        preimage_original_path = member_original_paths.get("preimage")
        postimage_original_path = member_original_paths.get("postimage")
        if (
            not isinstance(manifest_original_path, str)
            or not Path(manifest_original_path).is_absolute()
            or Path(manifest_original_path).name != manifest_path.name
            or not isinstance(preimage_original_path, str)
            or not isinstance(postimage_original_path, str)
            or Path(manifest_original_path).parent
            != Path(preimage_original_path).parent
            or Path(manifest_original_path).parent
            != Path(postimage_original_path).parent
        ):
            continue
        pair_format, pair_members = pair_binding
        matching_manifests.append(
            (
                manifest_relative,
                manifest_sha256,
                manifest_original_path,
                pair_format,
                pair_members,
            )
        )
    if len(matching_manifests) != 1:
        return None
    (
        manifest_relative,
        manifest_sha256,
        manifest_original_path,
        pair_format,
        pair_members,
    ) = matching_manifests[0]
    return {
        "source_type": "content_bound_archived_source_snapshot",
        "pair_format": pair_format,
        "source_role": source_role,
        "source_sha256": source_sha256,
        "pair_members": pair_members,
        "source_manifest_path": manifest_relative,
        "source_manifest_original_path": manifest_original_path,
        "source_manifest_sha256": manifest_sha256,
        "artifact_index_path": index_binding[0],
        "artifact_index_sha256": index_binding[1],
    }


_FQN_PATTERNS = {
    target: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(target)}(?![A-Za-z0-9_])")
    for target in TARGETS
}


def _module_relative_path(target: str) -> str:
    """Return the package-relative path represented by one exact FQN."""
    return target.removeprefix("polisyos.").replace(".", "/")


def _source_candidate_definitions(target: str) -> tuple[dict[str, str], ...]:
    """Derive both standard Python source forms for an importable module FQN."""
    module_path = _module_relative_path(target)
    return (
        {"kind": "module_file", "relative_path": f"{module_path}.py"},
        {
            "kind": "package_initializer",
            "relative_path": f"{module_path}/__init__.py",
        },
        {
            "kind": "package_resource_tree",
            "relative_path": f"{module_path}/",
        },
    )


def _observed_source_candidates(
    target: str,
    successfully_read_paths: list[str],
) -> list[dict[str, Any]]:
    """Bind source candidates to successfully read files beneath a polisyos package."""
    candidates = _source_candidate_definitions(target)
    observations: list[list[str]] = [[] for _ in candidates]
    for path in successfully_read_paths:
        parts = Path(path).parts
        try:
            package_index = parts.index("polisyos")
        except ValueError:
            continue
        package_relative = Path(*parts[package_index + 1 :]).as_posix()
        for index, candidate in enumerate(candidates):
            relative_path = candidate["relative_path"]
            if candidate["kind"] == "package_resource_tree":
                if package_relative.startswith(relative_path):
                    observations[index].append(path)
            elif package_relative == relative_path:
                observations[index].append(path)
    return [
        {
            **candidate,
            "observed_paths": sorted(observations[index]),
        }
        for index, candidate in enumerate(candidates)
    ]


def _resource_patterns_for_target(target: str) -> tuple[re.Pattern[str], ...]:
    """Cover FQN resources, module files, package directories, and package initializers."""
    module_path = _module_relative_path(target)
    resource_paths = {
        module_path,
        f"polisyos/{module_path}",
        f"{module_path}.py",
        f"polisyos/{module_path}.py",
        f"{module_path}/__init__.py",
        f"polisyos/{module_path}/__init__.py",
    }
    return tuple(
        re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(resource)}(?![A-Za-z0-9_.-])")
        for resource in sorted(resource_paths)
    )


_RESOURCE_PATTERNS = {target: _resource_patterns_for_target(target) for target in TARGETS}


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
        if any(status in {"R", "C"} for status in record[:2]):
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


def _package_name_for_path(path: str) -> str | None:
    module_name = _module_name_for_path(path)
    if module_name is None:
        return None
    if Path(path).stem == "__init__":
        return module_name
    return module_name.rpartition(".")[0]


def _resolve_import_from(path: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    package_name = _package_name_for_path(path)
    if package_name is None:
        return None
    package_parts = package_name.split(".") if package_name else []
    keep = len(package_parts) - (node.level - 1)
    if keep <= 0:
        return None
    prefix = package_parts[:keep]
    if node.module:
        prefix.extend(node.module.split("."))
    return ".".join(prefix)


def _import_from_hits(path: str, node: ast.ImportFrom) -> list[dict[str, Any]]:
    module_name = _resolve_import_from(path, node)
    if module_name is None:
        return []
    evidence = "absolute_import" if node.level == 0 else "relative_import"
    target = _target_for_module(module_name)
    if target:
        return [
            {
                "target": target,
                "imported_module": module_name,
                "path": path,
                "line": node.lineno,
                "evidence_kind": evidence,
                "imported_names": [alias.name for alias in node.names],
            }
        ]

    child_evidence = f"{evidence}_child_candidate"
    hits = []
    for alias in node.names:
        if alias.name == "*":
            continue
        child_module = f"{module_name}.{alias.name}" if module_name else alias.name
        target = _target_for_module(child_module)
        if target:
            hits.append(
                {
                    "target": target,
                    "imported_module": module_name,
                    "imported_module_candidate": child_module,
                    "path": path,
                    "line": node.lineno,
                    "evidence_kind": child_evidence,
                    "imported_names": [alias.name],
                    "resolution": "child_module_or_package_attribute",
                }
            )
    return hits


def _call_path(
    node: ast.expr, module_aliases: dict[str, str], imported_aliases: dict[str, str]
) -> str:
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
        if all(
            isinstance(value, ast.Constant) and isinstance(value.value, str)
            for value in node.values
        ):
            return "".join(str(value.value) for value in node.values)  # type: ignore[attr-defined]
    return None


def _scan_python(
    path: str,
    text: str,
    *,
    source_snapshot: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], dict[str, Any] | None]:
    imports: list[dict[str, Any]] = []
    loader_sites: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    normalization: dict[str, Any] | None = None
    try:
        tree = ast.parse(text, filename=path)
    except (SyntaxError, ValueError, RecursionError) as error:
        if not (
            isinstance(error, IndentationError)
            and error.msg == "unexpected indent"
            and source_snapshot is not None
        ):
            return imports, loader_sites, [f"{path}: {type(error).__name__}: {error}"], None
        normalized_text = textwrap.dedent(text)
        if normalized_text == text:
            return imports, loader_sites, [f"{path}: {type(error).__name__}: {error}"], None
        try:
            tree = ast.parse(normalized_text, filename=path)
        except (SyntaxError, ValueError, RecursionError) as normalized_error:
            return (
                imports,
                loader_sites,
                [
                    f"{path}: {type(normalized_error).__name__}: "
                    f"{normalized_error} after evidence excerpt dedent"
                ],
                None,
            )
        normalization = source_snapshot

    module_aliases: dict[str, str] = {}
    imported_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                imported_name = alias.name if alias.asname else alias.name.split(".")[0]
                module_aliases[local_name] = alias.name if alias.asname else imported_name
        elif isinstance(node, ast.ImportFrom):
            imports.extend(_import_from_hits(path, node))
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
        if call_name in {
            "__import__",
            "builtins.__import__",
            "importlib.import_module",
            "pkgutil.resolve_name",
        }:
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
                "status": "literal_target"
                if literal is not None
                else "unresolved_nonliteral_target",
            }
        )
    return imports, loader_sites, parse_errors, normalization


def _package_metadata(root: Path, selected_text: dict[str, str]) -> dict[str, Any]:
    pyproject = selected_text.get("pyproject.toml")
    hatch = selected_text.get("hatch.toml")
    metadata: dict[str, Any] = {
        "configuration_inputs": [
            name
            for name in ("pyproject.toml", "hatch.toml", "MANIFEST.in")
            if name in selected_text
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
            line.strip()
            for line in lines
            if any(token in line.lower() for token in ("[build", "packages", "include", "exclude"))
        ]
    if pyproject is not None:
        lines = pyproject.splitlines()
        relevant["pyproject_build_system_and_scripts"] = [
            line.strip()
            for line in lines
            if any(
                token in line.lower()
                for token in (
                    "[build-system]",
                    "build-backend",
                    "requires =",
                    "[project.scripts]",
                    "polisyos",
                )
            )
        ]
    metadata["configuration_observation"] = relevant
    metadata["selection_status"] = "configuration_bytes_read; archive membership unverified"
    return metadata


def collect_census(repo_root: Path) -> tuple[dict[str, Any], int]:
    root = repo_root.resolve()
    tracked, tracked_receipt = _git_paths(root, "ls-files", "--cached")
    untracked, untracked_receipt = _git_paths(root, "ls-files", "--others", "--exclude-standard")
    ignored, ignored_receipt = _git_paths(
        root, "ls-files", "--others", "--ignored", "--exclude-standard"
    )
    changed, status_receipt = _git_status_paths(root)
    git_ok = (
        all(
            receipt["returncode"] == 0
            for receipt in (tracked_receipt, untracked_receipt, ignored_receipt, status_receipt)
        )
        and status_receipt.get("prefix_returncode") == 0
    )

    tracked = sorted(set(tracked))
    untracked = sorted(set(untracked))
    ignored = sorted(set(ignored))
    selected = sorted(path for path in set(tracked) | set(untracked) if _is_selected_text(path))
    selected_path_set = set(selected)
    evidence_json_cache: dict[str, tuple[dict[str, Any], str, int] | None] = {}
    selected_ignored = sorted(path for path in ignored if _is_selected_text(path))
    excluded = sorted(
        {
            path: "known_binary_suffix"
            if Path(path).suffix.lower() in KNOWN_BINARY_SUFFIXES
            else "unsupported_filename_or_suffix"
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
    gzip_text_inputs: list[dict[str, object]] = []
    indented_python_excerpts: list[dict[str, object]] = []
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
                decoded_bytes, decoding = _decode_selected_bytes(relative, raw)
            except _GzipTextExpansionLimitError as error:
                unsupported.append(
                    {
                        "path": relative,
                        "class": "gzip_text_expansion_limit",
                        "detail": str(error),
                    }
                )
                continue
            except _CompressedTextWrongSuffixError as error:
                unsupported.append(
                    {
                        "path": relative,
                        "class": "compressed_text_wrong_suffix",
                        "detail": str(error),
                    }
                )
                continue
            except _InvalidCompressedJUnitXmlError as error:
                unsupported.append(
                    {
                        "path": relative,
                        "class": "invalid_compressed_junit_xml",
                        "detail": str(error),
                    }
                )
                continue
            except (OSError, EOFError, zlib.error) as error:
                unsupported.append(
                    {"path": relative, "class": "invalid_gzip_text", "detail": str(error)}
                )
                continue
            try:
                content = decoded_bytes.decode("utf-8")
            except UnicodeDecodeError as error:
                unsupported.append(
                    {"path": relative, "class": "selected_file_not_utf8", "detail": str(error)}
                )
                continue
            if decoding is not None:
                gzip_text_inputs.append({"path": relative, **decoding})
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
                source_snapshot = None
                if _source_snapshot_role(relative) is not None:
                    source_snapshot = _indexed_evidence_snapshot(
                        root,
                        relative,
                        resolved_path.relative_to(root).as_posix(),
                        raw,
                        selected_path_set,
                        evidence_json_cache,
                    )
                imports, loader_sites, errors, normalization = _scan_python(
                    relative, content, source_snapshot=source_snapshot
                )
                all_imports.extend(imports)
                all_loader_sites.extend(loader_sites)
                parse_errors.extend(errors)
                if normalization is not None:
                    indented_python_excerpts.append(
                        {
                            "path": relative,
                            "normalization": "textwrap.dedent",
                            "reason": "content-bound archived source-pair record",
                            "line_count": len(content.splitlines()),
                            "line_numbers_preserved": True,
                            "column_offsets_preserved": False,
                            **normalization,
                        }
                    )
        read_receipt = measurement.snapshot(
            complete_verdict=git_ok and not unreadable and not rejected_paths
        )

    for import_hit in all_imports:
        matched_value = import_hit.get("imported_module_candidate", import_hit["imported_module"])
        all_matches.append({**import_hit, "matched_value": matched_value})
    all_matches.sort(
        key=lambda hit: (hit["target"], hit["path"], hit["line"], hit["evidence_kind"])
    )
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
            "status": "present"
            if any(site["status"] == "unresolved_nonliteral_target" for site in all_loader_sites)
            else "not_established",
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
        "source_normalizations": {
            "gzip_text_inputs": gzip_text_inputs,
            "indented_evidence_python_excerpts": indented_python_excerpts,
        },
        "unsupported_or_ambiguous_inputs": unsupported
        + [
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
                "source_candidates": _observed_source_candidates(target, read_paths),
                "role": {
                    TARGETS[
                        0
                    ]: "compatibility-pending surface; local observations do not authorize retirement",
                    TARGETS[
                        1
                    ]: "mechanisms target; source presence or absence is measured only inside selection",
                    TARGETS[
                        2
                    ]: "compatibility-pending descriptor surface; no generator/codegen role is inferred",
                    TARGETS[
                        3
                    ]: "compatibility-pending alias to canonical kernel.schemas; no sunset decision is inferred",
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
            "criterion_verdict": "partial_coverage"
            if any_incomplete
            else "local_static_census_only",
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
    print(json.dumps(receipt, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
