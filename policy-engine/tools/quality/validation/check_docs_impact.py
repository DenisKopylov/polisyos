#!/usr/bin/env python3
"""Queue tracked Markdown pages for review when their declared sources change.

The command compares two immutable Git trees and reads every Markdown blob in
the head tree. A page is queued only when a changed tracked path intersects a
parseable leading ``Source of truth`` declaration. The queue requests human
review; it does not decide whether prose is stale or correct.

``Source pin`` and ``Source snapshot`` are recorded as metadata presence only.
Neither is resolved or used as the comparison base. Source declarations use
the bounded path/glob grammar from ``check_docs_source_bindings``. Directory
tokens, brace expansion, and other unsupported forms remain visible as
``unsupported`` instead of being guessed or silently skipped.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from tools.quality.validation import check_docs_source_bindings as source_bindings

MARKDOWN_SUFFIXES = {b".md", b".mdx", b".markdown", b".mdc"}
MARKDOWN_SUFFIX_NAMES = [".md", ".mdc", ".markdown", ".mdx"]
SOURCE_TOKEN_RE = re.compile(r"`([^`\n]+)`")
MAX_CHANGED_PATH_EXAMPLES = 8
UNMEASURED = [
    "whether prose claims are complete, true, or semantically affected by a changed path",
    "source dependencies omitted from a page's declared Source of truth patterns",
    "untracked worktree changes; both inputs are immutable Git commits",
    "test execution, runtime behavior, deployment state, or external services",
    "content inside submodules and resolved bytes behind symlinks",
    "external Git LFS objects; an LFS Markdown pointer is classified read_unrun",
    "source declarations outside the accepted leading metadata block are not parsed",
    "Markdown-like files outside the selected .md, .mdc, .markdown, and .mdx suffixes",
    "historical authority or correctness of Source pin and Source snapshot fields",
]


def _add(digest: Any, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, byteorder="big"))
    digest.update(value)


def _entry_signature(entry: source_bindings.TreeEntry | None) -> bytes:
    if entry is None:
        return b"absent"
    return b"\0".join(
        (
            entry.mode.encode("ascii"),
            entry.object_type.encode("ascii"),
            entry.object_id.encode("ascii"),
        )
    )


def _changed_tree_paths(
    before: dict[bytes, source_bindings.TreeEntry],
    after: dict[bytes, source_bindings.TreeEntry],
) -> tuple[dict[bytes, list[str]], str, Counter[str]]:
    changed: dict[bytes, list[str]] = {}
    digest = hashlib.sha256()
    counts: Counter[str] = Counter()
    for path in sorted(before.keys() | after.keys()):
        left = before.get(path)
        right = after.get(path)
        kinds: list[str] = []
        if left is None:
            kinds.append("added")
        elif right is None:
            kinds.append("removed")
        else:
            if left.object_id != right.object_id or left.object_type != right.object_type:
                kinds.append("content_changed")
            if left.mode != right.mode:
                kinds.append("mode_changed")
        if not kinds:
            continue
        changed[path] = kinds
        for kind in kinds:
            counts[kind] += 1
        _add(digest, path)
        _add(digest, ",".join(kinds).encode("ascii"))
        _add(digest, _entry_signature(left))
        _add(digest, _entry_signature(right))
    return changed, digest.hexdigest(), counts


def _display_path(path: bytes) -> dict[str, str]:
    try:
        return {"path": path.decode("utf-8")}
    except UnicodeDecodeError:
        return {
            "path": path.decode("utf-8", errors="backslashreplace"),
            "path_bytes_base64": base64.b64encode(path).decode("ascii"),
        }


def _row_path_bytes(row: dict[str, Any]) -> bytes:
    if "path_bytes_base64" in row:
        return base64.b64decode(row["path_bytes_base64"], validate=True)
    return str(row["path"]).encode("utf-8")


def _is_markdown_path(path: bytes) -> bool:
    suffix = path.rsplit(b"/", 1)[-1].rsplit(b".", 1)
    return len(suffix) == 2 and b"." + suffix[1].lower() in MARKDOWN_SUFFIXES


def _leading_fields(text: str) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Parse only leading source metadata; body examples are not declarations."""
    lines = text.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines) and lines[index].strip() == "---":
        index += 1
        while index < len(lines) and lines[index].strip() != "---":
            index += 1
        if index == len(lines):
            raise source_bindings.BindingError("unterminated YAML front matter")
        index += 1

    names = {"Source pin", "Source snapshot", "Source of truth"}
    field_counts = dict.fromkeys(names, 0)
    values = {name: [] for name in names}
    active_field: str | None = None
    saw_title = False
    for line in lines[index:]:
        if not line.strip():
            continue
        stripped = line.strip()
        if not saw_title and stripped.startswith("# "):
            saw_title = True
            active_field = None
            continue
        parsed = source_bindings._metadata_line(line)
        if parsed is not None:
            key, value = parsed
            active_field = key if key in names else None
            if key in names:
                field_counts[key] += 1
                values[key].append(value)
            continue
        if active_field == "Source of truth" and line[:1].isspace():
            values[active_field].append(stripped)
            continue
        if active_field == "Source of truth" and line.lstrip().startswith(">"):
            values[active_field].append(line.lstrip()[1:].strip())
            continue
        break

    # Continuation lines add values but do not add field occurrences.
    return ({name: values[name] for name in names}, field_counts)


def _parse_page_patterns(
    text: str,
    context: source_bindings.RepoContext,
    before: dict[bytes, source_bindings.TreeEntry],
    after: dict[bytes, source_bindings.TreeEntry],
    changed_paths: set[bytes],
) -> dict[str, Any]:
    try:
        fields, field_counts = _leading_fields(text)
    except source_bindings.BindingError as exc:
        return {
            "classification": "unsupported",
            "reason": str(exc),
            "source_pin_present": False,
            "source_snapshot_present": False,
            "source_of_truth_field_count": 0,
            "patterns": [],
            "changed_paths": set(),
        }

    source_values = fields["Source of truth"]
    metadata = {
        "source_pin_present": bool(fields["Source pin"]),
        "source_snapshot_present": bool(fields["Source snapshot"]),
        "source_of_truth_field_count": field_counts["Source of truth"],
    }
    if metadata["source_of_truth_field_count"] == 0:
        reason = "no leading Source of truth path declaration"
        if metadata["source_snapshot_present"]:
            reason = "Source snapshot does not identify source owner paths"
        return {
            "classification": "unmapped",
            "reason": reason,
            **metadata,
            "patterns": [],
            "changed_paths": set(),
        }
    if metadata["source_of_truth_field_count"] != 1:
        return {
            "classification": "unsupported",
            "reason": (
                "expected one leading Source of truth field; found "
                f"{metadata['source_of_truth_field_count']}"
            ),
            **metadata,
            "patterns": [],
            "changed_paths": set(),
        }

    source_value = "\n".join(source_values)
    tokens = SOURCE_TOKEN_RE.findall(source_value)
    malformed_delimiters = source_value.count("`") != 2 * len(tokens)
    pattern_rows: list[dict[str, Any]] = []
    impacted_paths: set[bytes] = set()
    seen: set[str] = set()
    errors: list[str] = []
    if malformed_delimiters:
        errors.append("Source of truth contains unmatched or non-path backticks")
    if not tokens:
        errors.append("Source of truth must contain one or more backticked paths or globs")

    for token in tokens:
        row: dict[str, Any] = {"pattern": token, "status": "unsupported"}
        if token in seen:
            row["reason"] = "duplicate source path/glob declaration"
            pattern_rows.append(row)
            errors.append(f"duplicate source path/glob declaration: {token!r}")
            continue
        seen.add(token)
        try:
            git_pattern = source_bindings._normalize_pattern(context, token)
        except source_bindings.BindingError as exc:
            row["reason"] = str(exc)
            pattern_rows.append(row)
            errors.append(str(exc))
            continue

        base_match_count = sum(
            source_bindings._path_matches_bytes(git_pattern, path) for path in before
        )
        head_match_count = sum(
            source_bindings._path_matches_bytes(git_pattern, path) for path in after
        )
        changed_matches = {
            path for path in changed_paths if source_bindings._path_matches_bytes(git_pattern, path)
        }
        row.update(
            {
                "normalized_pattern": git_pattern,
                "base_match_count": base_match_count,
                "head_match_count": head_match_count,
            }
        )
        if not base_match_count and not head_match_count:
            row["reason"] = "pattern matches no tracked paths at base or head"
            errors.append(f"source pattern matches no tracked paths: {token!r}")
        else:
            row["status"] = "supported"
            impacted_paths.update(changed_matches)
        pattern_rows.append(row)

    classification = "unsupported" if errors else "supported"
    return {
        "classification": classification,
        "reason": "; ".join(dict.fromkeys(errors)) if errors else None,
        **metadata,
        "patterns": pattern_rows,
        "changed_paths": impacted_paths,
    }


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(min(64 * 1024, remaining))
        if not chunk:
            raise source_bindings.BindingError("Git truncated a Markdown blob")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_pages(
    context: source_bindings.RepoContext,
    head_tree: dict[bytes, source_bindings.TreeEntry],
    before: dict[bytes, source_bindings.TreeEntry],
    after: dict[bytes, source_bindings.TreeEntry],
    changed: dict[bytes, list[str]],
) -> tuple[list[dict[str, Any]], dict[bytes, set[bytes]], dict[str, Any]]:
    markdown_paths = sorted(path for path in head_tree if _is_markdown_path(path))
    page_rows: list[dict[str, Any]] = []
    page_sources: dict[bytes, set[bytes]] = {}
    changed_paths = set(changed)
    read_digest = hashlib.sha256()
    successful = 0
    failed = 0
    bytes_read = 0

    try:
        process = subprocess.Popen(
            ["git", "-C", str(context.git_root), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=source_bindings._git_environment(),
        )
    except OSError as exc:
        process = None
        process_error = f"could not start Git blob reader: {type(exc).__name__}: {exc}"
    else:
        process_error = ""

    for path in markdown_paths:
        entry = head_tree[path]
        row: dict[str, Any] = {
            **_display_path(path),
            "classification": "read_unrun",
            "reason": None,
            "read": {"status": "UNRUN", "bytes": None, "sha256": None},
            "source_pin_present": False,
            "source_snapshot_present": False,
            "source_of_truth_field_count": 0,
            "patterns": [],
            "document_changed": path in changed and _is_markdown_path(path),
        }
        if process is None:
            row["reason"] = process_error
        elif entry.object_type != "blob":
            row["reason"] = f"Markdown tree entry is not a blob: {entry.object_type}"
        elif process.stdin is None or process.stdout is None:
            row["reason"] = "Git blob reader did not expose its batch streams"
        else:
            try:
                process.stdin.write(entry.object_id.encode("ascii") + b"\n")
                process.stdin.flush()
                header = process.stdout.readline().rstrip(b"\n").split(b" ")
                if len(header) == 2 and header[1] == b"missing":
                    raise source_bindings.BindingError(
                        "Markdown blob is unavailable in the local Git object database"
                    )
                if (
                    len(header) != 3
                    or header[0].decode("ascii", errors="replace") != entry.object_id
                ):
                    raise source_bindings.BindingError(
                        "Git returned an unreadable Markdown blob header"
                    )
                if header[1] != b"blob":
                    raise source_bindings.BindingError(
                        "Markdown tree entry resolved to a non-blob object"
                    )
                size = int(header[2])
                content = _read_exact(process.stdout, size)
                if process.stdout.read(1) != b"\n":
                    raise source_bindings.BindingError("Git Markdown blob framing failed")
                sha256 = hashlib.sha256(content).hexdigest()
                row["read"] = {"status": "PASS", "bytes": size, "sha256": sha256}
                successful += 1
                bytes_read += size
                if entry.mode == "120000":
                    row["reason"] = "tracked Markdown symlink target is stored but not followed"
                elif content.startswith(source_bindings.LFS_HEADER):
                    row["reason"] = (
                        "Markdown blob is a Git LFS pointer; external object bytes are unavailable"
                    )
                else:
                    try:
                        text = content.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        row["reason"] = f"tracked Markdown blob is not UTF-8: {exc}"
                    else:
                        result = _parse_page_patterns(text, context, before, after, changed_paths)
                        row.update(
                            {
                                "classification": result["classification"],
                                "reason": result["reason"],
                                "source_pin_present": result["source_pin_present"],
                                "source_snapshot_present": result["source_snapshot_present"],
                                "source_of_truth_field_count": result[
                                    "source_of_truth_field_count"
                                ],
                                "patterns": result["patterns"],
                            }
                        )
                        page_sources[path] = result["changed_paths"]
            except (OSError, ValueError, source_bindings.BindingError) as exc:
                row["reason"] = str(exc) or type(exc).__name__

        if row["read"]["status"] == "UNRUN":
            failed += 1
            _add(read_digest, path)
            _add(read_digest, b"UNRUN")
            _add(read_digest, (row["reason"] or "unknown").encode("utf-8", errors="replace"))
        else:
            _add(read_digest, path)
            _add(read_digest, int(row["read"]["bytes"]).to_bytes(8, byteorder="big"))
            _add(read_digest, bytes.fromhex(row["read"]["sha256"]))
        page_rows.append(row)

    process_returncode: int | None = None
    process_stderr = ""
    if process is not None:
        try:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            process_returncode = process.wait()
            if process.stderr is not None:
                process_stderr = process.stderr.read().decode("utf-8", errors="replace").strip()
        except OSError as exc:
            process.kill()
            process.wait()
            process_returncode = -1
            process_stderr = f"{type(exc).__name__}: {exc}"
        if process_returncode != 0:
            process_error = f"Git blob reader exited {process_returncode}: {process_stderr}"
            # A nonzero batch-reader exit invalidates every apparently successful
            # page result because completeness of the stream is no longer established.
            for row in page_rows:
                row["classification"] = "read_unrun"
                row["reason"] = process_error
                row["read"]["status"] = "UNRUN"
            failed = len(page_rows)
            successful = 0
            bytes_read = 0
            page_sources.clear()
            read_digest = hashlib.sha256()
            for row in page_rows:
                _add(read_digest, _row_path_bytes(row))
                _add(read_digest, b"UNRUN")
                _add(read_digest, process_error.encode("utf-8", errors="replace"))

    return (
        page_rows,
        page_sources,
        {
            "status": "PASS" if failed == 0 else "UNRUN",
            "selected_page_count": len(markdown_paths),
            "successful_page_read_count": successful,
            "failed_page_read_count": failed,
            "page_classification_unrun_count": sum(
                row["classification"] == "read_unrun" for row in page_rows
            ),
            "successful_markdown_bytes_read": bytes_read,
            "page_read_set_sha256": read_digest.hexdigest(),
            "process_returncode": process_returncode,
            "process_error": process_error or None,
        },
    )


def _path_change_record(
    path: bytes,
    kinds: list[str],
    before: dict[bytes, source_bindings.TreeEntry],
    after: dict[bytes, source_bindings.TreeEntry],
) -> dict[str, Any]:
    path_id = hashlib.sha256(path).hexdigest()
    result: dict[str, Any] = {
        "id": path_id,
        **_display_path(path),
        "change_kinds": kinds,
    }
    for label, tree in (("base", before), ("head", after)):
        entry = tree.get(path)
        result[f"{label}_entry"] = (
            None
            if entry is None
            else {
                "mode": entry.mode,
                "object_type": entry.object_type,
                "object_id": entry.object_id,
            }
        )
    return result


def _build_report(
    context: source_bindings.RepoContext,
    args: argparse.Namespace,
    base_commit: str,
    head_commit: str,
    before: dict[bytes, source_bindings.TreeEntry],
    after: dict[bytes, source_bindings.TreeEntry],
) -> dict[str, Any]:
    changed, changed_digest, changed_kind_counts = _changed_tree_paths(before, after)
    pages, page_sources, read_report = _read_pages(context, after, before, after, changed)
    changed_markdown = [path for path in changed if _is_markdown_path(path)]
    removed_document_records = [
        {
            **_display_path(path),
            "change_kinds": changed[path],
        }
        for path in sorted(changed_markdown)
        if path in before and path not in after
    ]

    impact_paths: dict[bytes, dict[str, Any]] = {}
    queue: list[dict[str, Any]] = []
    for page in pages:
        if page["classification"] == "read_unrun":
            continue
        doc_bytes = _row_path_bytes(page)
        impacted = sorted(page_sources.get(doc_bytes, set()) - {doc_bytes})
        if not impacted:
            continue
        path_ids: list[str] = []
        for source_path in impacted:
            record = _path_change_record(source_path, changed[source_path], before, after)
            impact_paths[source_path] = record
            path_ids.append(record["id"])
        queue.append(
            {
                "doc": page.get("path"),
                **(
                    {"doc_path_bytes_base64": page["path_bytes_base64"]}
                    if "path_bytes_base64" in page
                    else {}
                ),
                "classification": page["classification"],
                "coverage": (
                    "complete_for_declared_patterns"
                    if page["classification"] == "supported"
                    else "partial_for_declared_patterns"
                ),
                "changed_source_ids": path_ids,
                "document_changed": page["document_changed"],
                "action": "human_review_required",
                "reason": "a changed tracked path matched at least one declared Source of truth pattern",
            }
        )

    counts = Counter(row["classification"] for row in pages)
    gaps = sum(counts[key] for key in ("unmapped", "unsupported", "read_unrun"))
    if read_report["status"] != "PASS":
        gaps += 1
    if not pages:
        gaps += 1
    declared_scan_status = (
        "UNRUN"
        if read_report["status"] != "PASS" or counts.get("read_unrun", 0) or not pages
        else "PARTIAL"
        if gaps
        else "COMPLETE"
    )
    coverage_status = "PARTIAL"
    impact_status = "REVIEW_REQUIRED" if queue else "NO_DECLARED_SOURCE_IMPACT"
    overall_status = (
        "UNRUN" if gaps else ("REVIEW_REQUIRED" if queue else "NO_DECLARED_SOURCE_IMPACT")
    )
    page_inventory_digest = hashlib.sha256()
    for path in sorted(path for path in after if _is_markdown_path(path)):
        _add(page_inventory_digest, path)
        _add(page_inventory_digest, _entry_signature(after[path]))

    return {
        "schema_version": 1,
        "tool": "check-docs-impact",
        "status": overall_status,
        "measured_property": (
            "tracked Markdown pages whose leading declared source paths intersect paths that differ between two immutable Git trees"
        ),
        "decision_semantics": (
            "review_queue entries require human review; they do not prove prose is stale or incorrect"
        ),
        "inputs": {
            "base": {
                "requested_ref": args.base_ref,
                "status": "PASS",
                "resolved_commit": base_commit,
            },
            "head": {
                "requested_ref": args.head_ref,
                "status": "PASS",
                "resolved_commit": head_commit,
            },
        },
        "git_read_policy": {
            "lazy_fetch": "disabled; missing objects are UNRUN",
            "replacement_refs": "disabled; immutable commit IDs name the read trees",
            "working_tree": "not read; uncommitted documentation and source edits are outside this comparison",
            "source_content": "Git tree entry IDs and modes are compared; changed source blob contents are not exported or parsed",
        },
        "scope": {
            "markdown_suffixes": MARKDOWN_SUFFIX_NAMES,
            "enumeration": "all tracked matching paths in the immutable head Git tree, including repository-root and product paths",
            "excluded_matching_paths": [],
            "other_file_types": "outside the Markdown page inventory",
            "source_path_namespace_semantics": source_bindings.PATH_NAMESPACE_SEMANTICS,
            "glob_semantics": "* and ? match within one path component; a complete ** component matches zero or more components",
            "unsupported_path_syntax": [
                "directory tokens ending in /",
                "brace expansion",
                "character classes",
                "absolute paths",
                "backslashes",
                "parent traversal",
            ],
            "self_document_change": "head pages record document_changed; removed Markdown paths are listed separately; the page itself is excluded from its own source-impact item",
        },
        "summary": {
            "tracked_markdown_count": read_report["selected_page_count"],
            "markdown_page_counts_by_classification": {
                key: counts.get(key, 0)
                for key in ("supported", "unmapped", "unsupported", "read_unrun")
            },
            "successful_markdown_reads": read_report["successful_page_read_count"],
            "failed_markdown_reads": read_report["failed_page_read_count"],
            "successful_markdown_bytes_read": read_report["successful_markdown_bytes_read"],
            "changed_repository_path_count": len(changed),
            "changed_markdown_path_count": len(changed_markdown),
            "changed_source_path_count": len(impact_paths),
            "human_review_page_count": len(queue),
        },
        "coverage": {
            "status": coverage_status,
            "declared_binding_scan": {
                "status": declared_scan_status,
                "denominator": len(pages),
                "supported_page_count": counts.get("supported", 0),
                "unmapped_page_count": counts.get("unmapped", 0),
                "unsupported_page_count": counts.get("unsupported", 0),
                "read_unrun_page_count": counts.get("read_unrun", 0),
                "property": "every tracked head Markdown page has one parseable Source of truth declaration whose patterns match tracked paths at base or head",
            },
            "supported_page_count": counts.get("supported", 0),
            "unmapped_page_count": counts.get("unmapped", 0),
            "unsupported_page_count": counts.get("unsupported", 0),
            "read_unrun_page_count": counts.get("read_unrun", 0),
            "read_receipt": read_report,
            "page_inventory_sha256": page_inventory_digest.hexdigest(),
            "unresolved_by_construction": [
                *(["no tracked Markdown pages were available to classify"] if not pages else []),
                *UNMEASURED,
            ],
        },
        "comparison": {
            "semantics": "immutable Git tree difference; commit ancestry is not asserted",
            "base_tree_entry_count": len(before),
            "head_tree_entry_count": len(after),
            "changed_repository_path_count": len(changed),
            "changed_path_kind_counts": dict(sorted(changed_kind_counts.items())),
            "changed_path_set_sha256": changed_digest,
            "changed_path_examples": [
                {**_display_path(path), "change_kinds": changed[path]}
                for path in sorted(changed)[:MAX_CHANGED_PATH_EXAMPLES]
            ],
            "changed_path_examples_omitted": max(0, len(changed) - MAX_CHANGED_PATH_EXAMPLES),
            "impact_status_within_declared_bindings": impact_status,
        },
        "pages": pages,
        "removed_document_paths": removed_document_records,
        "changed_source_paths": [impact_paths[path] for path in sorted(impact_paths)],
        "review_queue": queue,
        "unmeasured": UNMEASURED,
    }


def _unrun_report(
    args: argparse.Namespace, base: dict[str, Any], head: dict[str, Any], reason: str
) -> dict[str, Any]:
    base.setdefault("requested_ref", args.base_ref)
    head.setdefault("requested_ref", args.head_ref)
    return {
        "schema_version": 1,
        "tool": "check-docs-impact",
        "status": "UNRUN",
        "measured_property": (
            "tracked Markdown pages whose leading declared source paths intersect paths that differ between two immutable Git trees"
        ),
        "decision_semantics": "an incomplete scan cannot establish repository-wide absence of documentation impact",
        "inputs": {"base": base, "head": head},
        "scope": {
            "markdown_suffixes": MARKDOWN_SUFFIX_NAMES,
            "enumeration": "all tracked matching paths in the immutable head Git tree, including repository-root and product paths",
            "enumeration_status": "UNRUN",
            "tracked_markdown_count": None,
            "excluded_matching_paths": [],
            "other_file_types": "outside the Markdown page inventory",
        },
        "summary": {
            "tracked_markdown_count": None,
            "markdown_page_counts_by_classification": {},
            "successful_markdown_reads": 0,
            "failed_markdown_reads": 0,
            "successful_markdown_bytes_read": 0,
            "changed_repository_path_count": None,
            "changed_markdown_path_count": None,
            "changed_source_path_count": 0,
            "human_review_page_count": 0,
        },
        "coverage": {
            "status": "UNRUN",
            "declared_binding_scan": {
                "status": "UNRUN",
                "denominator": None,
                "property": "every tracked head Markdown page has one parseable Source of truth declaration whose patterns match tracked paths at base or head",
            },
            "unresolved_by_construction": [reason, *UNMEASURED],
        },
        "comparison": {
            "semantics": "immutable Git tree difference; commit ancestry is not asserted",
            "impact_status_within_declared_bindings": "UNRUN",
        },
        "pages": [],
        "removed_document_paths": [],
        "changed_source_paths": [],
        "review_queue": [],
        "unmeasured": UNMEASURED,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Git root or product root (default: this tool's product root)",
    )
    parser.add_argument(
        "--base-ref", required=True, help="explicit base ref for immutable tree comparison"
    )
    parser.add_argument(
        "--head-ref", required=True, help="explicit head ref for immutable tree comparison"
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--output",
        type=Path,
        help="write the complete text or JSON receipt to a new, untracked path (stdout is summary-only)",
    )
    return parser


def _text_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    coverage = report["coverage"]
    read_receipt = coverage.get("read_receipt", {})
    declared_scan = coverage.get("declared_binding_scan", {})
    comparison = report["comparison"]
    lines = [
        f"Docs impact: {report['status']}",
        f"Documentation coverage: {coverage['status']}",
        f"Declared binding scan: {declared_scan.get('status', 'UNRUN')}",
        f"Requested base ref: {report['inputs']['base'].get('requested_ref', 'UNRUN')}",
        f"Base commit: {report['inputs']['base'].get('resolved_commit', 'UNRUN')}",
        f"Requested head ref: {report['inputs']['head'].get('requested_ref', 'UNRUN')}",
        f"Head commit: {report['inputs']['head'].get('resolved_commit', 'UNRUN')}",
        f"Tracked Markdown: {summary['tracked_markdown_count']}",
        f"Markdown enumeration: {report['scope'].get('enumeration', 'UNRUN')}",
        f"Markdown suffix selector: {', '.join(report['scope'].get('markdown_suffixes', MARKDOWN_SUFFIX_NAMES))}",
        f"Excluded matching Markdown paths: {report['scope'].get('excluded_matching_paths', [])}",
        f"Other file types: {report['scope'].get('other_file_types', 'UNRUN')}",
        f"Source path namespaces: {report['scope'].get('source_path_namespace_semantics', 'UNRUN')}",
        f"Source glob grammar: {report['scope'].get('glob_semantics', 'UNRUN')}",
        f"Unsupported source syntax: {report['scope'].get('unsupported_path_syntax', 'UNRUN')}",
        f"Successful Markdown reads: {summary['successful_markdown_reads']}",
        f"Failed Markdown reads: {summary['failed_markdown_reads']}",
        f"Page classifications UNRUN: {read_receipt.get('page_classification_unrun_count', 0)}",
        f"Markdown bytes read: {summary['successful_markdown_bytes_read']}",
        f"page_read_set_sha256={read_receipt.get('page_read_set_sha256', 'UNRUN')}",
        f"head_page_inventory_sha256={coverage.get('page_inventory_sha256', 'UNRUN')}",
        f"Changed repository paths: {summary['changed_repository_path_count']}",
        f"changed_path_set_sha256={comparison.get('changed_path_set_sha256', 'UNRUN')}",
        f"Changed declared source paths: {summary['changed_source_path_count']}",
        f"Pages requiring human review: {summary['human_review_page_count']}",
        "Page classifications and read receipts:",
    ]
    for page in report["pages"]:
        read = page["read"]
        read_detail = (
            f"bytes={read['bytes']} sha256={read['sha256']}"
            if read["status"] == "PASS"
            else f"reason={page['reason']}"
        )
        lines.append(
            f"- {page['classification']} {page['path']} read={read['status']} {read_detail} "
            f"source_pin_present={page['source_pin_present']} "
            f"source_snapshot_present={page['source_snapshot_present']} "
            f"document_changed={page['document_changed']}"
        )
        if "path_bytes_base64" in page:
            lines.append(f"  path_bytes_base64={page['path_bytes_base64']}")
        if page["reason"] and read["status"] == "PASS":
            lines.append(f"  classification_reason={page['reason']}")
        for pattern in page["patterns"]:
            details = [f"pattern=`{pattern['pattern']}`", f"status={pattern['status']}"]
            if "normalized_pattern" in pattern:
                details.append(f"normalized=`{pattern['normalized_pattern']}`")
            if "base_match_count" in pattern:
                details.append(f"base_matches={pattern['base_match_count']}")
                details.append(f"head_matches={pattern['head_match_count']}")
            if pattern.get("reason"):
                details.append(f"reason={pattern['reason']}")
            lines.append("  " + " ".join(details))

    lines.append("Removed Markdown paths:")
    for item in report["removed_document_paths"]:
        lines.append(f"- {item['path']} kinds={','.join(item['change_kinds'])}")
        if "path_bytes_base64" in item:
            lines.append(f"  path_bytes_base64={item['path_bytes_base64']}")

    lines.append("Changed declared source paths (listed once; queue rows refer to IDs):")
    for item in report["changed_source_paths"]:
        base_entry = item["base_entry"]
        head_entry = item["head_entry"]
        base_oid = base_entry["object_id"] if base_entry else "absent"
        head_oid = head_entry["object_id"] if head_entry else "absent"
        lines.append(
            f"- {item['id']} {item['path']} kinds={','.join(item['change_kinds'])} "
            f"base_oid={base_oid} head_oid={head_oid}"
        )
        if "path_bytes_base64" in item:
            lines.append(f"  path_bytes_base64={item['path_bytes_base64']}")

    lines.append("Human review queue:")
    for item in report["review_queue"]:
        ids = ", ".join(item["changed_source_ids"])
        lines.append(
            f"- {item['doc']} classification={item['classification']} "
            f"coverage={item['coverage']} action={item['action']} source_ids={ids}"
        )
    lines.append("Queue semantics: " + report["decision_semantics"])
    if coverage.get("unresolved_by_construction"):
        lines.append("Unresolved coverage: " + "; ".join(coverage["unresolved_by_construction"]))
    return "\n".join(lines) + "\n"


def _summary_output(report: dict[str, Any], receipt_path: str | None) -> dict[str, Any]:
    summary = {
        "tool": report["tool"],
        "status": report["status"],
        "coverage_status": report["coverage"]["status"],
        "declared_binding_scan_status": report["coverage"]
        .get("declared_binding_scan", {})
        .get("status", "UNRUN"),
        "inputs": report["inputs"],
        "scope": {
            "markdown_suffixes": report["scope"].get("markdown_suffixes", MARKDOWN_SUFFIX_NAMES),
            "enumeration": report["scope"].get("enumeration", "UNRUN"),
            "enumeration_status": report["scope"].get("enumeration_status", "PASS"),
            "other_file_types": report["scope"].get("other_file_types", "UNRUN"),
        },
        "summary": report["summary"],
        "read_receipt": report["coverage"].get("read_receipt", {}),
        "comparison": {
            key: report["comparison"][key]
            for key in (
                "changed_repository_path_count",
                "changed_path_set_sha256",
                "impact_status_within_declared_bindings",
            )
            if key in report["comparison"]
        },
        "review_queue_action": "human review required; queue membership does not prove prose is stale or incorrect",
        "unresolved_coverage": report["coverage"].get("unresolved_by_construction", []),
        "receipt_path": receipt_path,
    }
    if "output_write" in report:
        summary["output_write"] = report["output_write"]
    return summary


def _summary_text(report: dict[str, Any], receipt_path: str | None) -> str:
    summary = report["summary"]
    coverage = report["coverage"]
    read_receipt = coverage.get("read_receipt", {})
    comparison = report["comparison"]
    base = report["inputs"]["base"]
    head = report["inputs"]["head"]
    lines = [
        f"Docs impact: {report['status']}; coverage: {coverage.get('status', 'UNRUN')}; "
        f"declared binding scan: {coverage.get('declared_binding_scan', {}).get('status', 'UNRUN')}",
        f"Base: {base.get('resolved_commit', 'UNRUN')} (requested {base.get('requested_ref', 'UNRUN')})",
        f"Head: {head.get('resolved_commit', 'UNRUN')} (requested {head.get('requested_ref', 'UNRUN')})",
        f"Tracked Markdown: {summary.get('tracked_markdown_count', 'UNRUN')} "
        f"({', '.join(report['scope'].get('markdown_suffixes', MARKDOWN_SUFFIX_NAMES))}; "
        f"{report['scope'].get('enumeration_status', 'PASS')})",
        f"Page classifications: {summary.get('markdown_page_counts_by_classification', {})}",
        f"Successful Markdown reads: {summary.get('successful_markdown_reads', 0)}; "
        f"failed: {summary.get('failed_markdown_reads', 0)}; "
        f"bytes read: {summary.get('successful_markdown_bytes_read', 0)}; "
        f"read-set sha256={read_receipt.get('page_read_set_sha256', 'UNRUN')}",
        f"Changed repository paths: {summary.get('changed_repository_path_count', 'UNRUN')}; "
        f"changed-set sha256={comparison.get('changed_path_set_sha256', 'UNRUN')}",
        f"Changed declared source paths: {summary.get('changed_source_path_count', 0)}; "
        f"Review pages requiring human review: {summary.get('human_review_page_count', 0)}",
        "Queue action: human review required; membership does not prove prose is stale or incorrect.",
        "Coverage boundary: declared source paths do not establish prose truth, completeness, or semantic impact.",
    ]
    unresolved = coverage.get("unresolved_by_construction", [])
    if unresolved:
        detail = (
            "full list in receipt" if receipt_path is not None else "full list requires --output"
        )
        lines.append(f"Unresolved coverage items: {len(unresolved)} ({detail})")
    if receipt_path is not None:
        lines.append(f"Full receipt: {receipt_path}")
    else:
        lines.append("Full receipt omitted; pass --output PATH to write the complete inventory.")
    if "output_write" in report:
        lines.append(f"Receipt write: UNRUN ({report['output_write'].get('reason', 'unknown')})")
    return "\n".join(lines) + "\n"


def _output_path_safety(
    context: source_bindings.RepoContext,
    requested: Path,
    trees: tuple[dict[bytes, source_bindings.TreeEntry], ...] | None,
) -> tuple[Path | None, str | None]:
    try:
        output_path = requested.expanduser().resolve(strict=False)
        if output_path.exists():
            return None, "receipt destination already exists; refusing to overwrite"
        git_output = source_bindings._git(context.git_root, "ls-files", "-z")
        indexed_paths = set(git_output.split(b"\0")) - {b""}
        repo_root = context.git_root.resolve(strict=True)
        if output_path.is_relative_to(repo_root):
            raw_path = os.fsencode(output_path.relative_to(repo_root).as_posix())
            if raw_path in indexed_paths:
                return None, "receipt destination is tracked in the current Git index"
            if trees is None:
                return (
                    None,
                    "cannot verify receipt destination against both immutable comparison trees",
                )
            if any(raw_path in tree for tree in trees):
                return None, "receipt destination is tracked in a base or head comparison tree"
        return output_path, None
    except (OSError, RuntimeError, ValueError, source_bindings.BindingError) as exc:
        return None, f"could not verify receipt destination safety: {type(exc).__name__}: {exc}"


def _emit(
    report: dict[str, Any],
    args: argparse.Namespace,
    *,
    output_path: Path | None = None,
    output_error: str | None = None,
) -> int:
    if args.format == "json":
        full_output = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    else:
        full_output = _text_report(report)

    receipt_path: str | None = None
    if args.output is not None:
        if output_path is None or output_error is not None:
            report["status"] = "UNRUN"
            report["output_write"] = {
                "status": "UNRUN",
                "reason": output_error or "receipt destination was not validated",
            }
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with output_path.open("x", encoding="utf-8") as receipt:
                    receipt.write(full_output)
                receipt_path = str(output_path)
            except OSError as exc:
                reason = f"{type(exc).__name__}: {exc}"
                print(f"Could not write docs impact receipt: {reason}", file=sys.stderr)
                report["status"] = "UNRUN"
                report["output_write"] = {"status": "UNRUN", "reason": reason}

    if args.format == "json":
        sys.stdout.write(
            json.dumps(_summary_output(report, receipt_path), ensure_ascii=True, sort_keys=True)
            + "\n"
        )
    else:
        sys.stdout.write(_summary_text(report, receipt_path))

    if args.output is not None and receipt_path is None:
        return 2
    if report["status"] == "UNRUN":
        return 2
    if report["status"] == "REVIEW_REQUIRED":
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Compare two immutable trees and report documented source impact."""
    args = _parser().parse_args(argv)
    base_result: dict[str, Any] = {"requested_ref": args.base_ref, "status": "UNRUN"}
    head_result: dict[str, Any] = {"requested_ref": args.head_ref, "status": "UNRUN"}
    try:
        context = source_bindings._resolve_context(args.repo_root)
    except source_bindings.BindingError as exc:
        reason = f"Git repository or product root is unavailable: {exc}"
        report = _unrun_report(args, base_result, head_result, reason)
        return _emit(
            report,
            args,
            output_error="cannot verify receipt destination without repository context",
        )

    for label, requested, result in (
        ("base", args.base_ref, base_result),
        ("head", args.head_ref, head_result),
    ):
        try:
            result["resolved_commit"] = source_bindings._resolve_commit(context, requested)
            result["status"] = "PASS"
        except source_bindings.BindingError as exc:
            result["reason"] = str(exc)
            result["status"] = "UNRUN"
    if base_result["status"] != "PASS" or head_result["status"] != "PASS":
        unresolved = "; ".join(
            f"{name}: {result.get('reason', result['status'])}"
            for name, result in (("base", base_result), ("head", head_result))
            if result["status"] != "PASS"
        )
        report = _unrun_report(
            args, base_result, head_result, f"could not resolve both immutable refs: {unresolved}"
        )
        output_path, output_error = (None, None)
        if args.output is not None:
            output_path, output_error = _output_path_safety(context, args.output, None)
        return _emit(report, args, output_path=output_path, output_error=output_error)

    base_commit = base_result["resolved_commit"]
    head_commit = head_result["resolved_commit"]
    before: dict[bytes, source_bindings.TreeEntry] | None = None
    after: dict[bytes, source_bindings.TreeEntry] | None = None
    try:
        before = source_bindings._tree(context, base_commit)
        after = source_bindings._tree(context, head_commit)
        report = _build_report(context, args, base_commit, head_commit, before, after)
    except (OSError, source_bindings.BindingError, KeyError, ValueError) as exc:
        report = _unrun_report(
            args,
            base_result,
            head_result,
            f"could not enumerate immutable Git trees: {type(exc).__name__}: {exc}",
        )
    output_path, output_error = (None, None)
    if args.output is not None:
        complete_trees = (before, after) if before is not None and after is not None else None
        output_path, output_error = _output_path_safety(context, args.output, complete_trees)
    return _emit(report, args, output_path=output_path, output_error=output_error)


if __name__ == "__main__":
    raise SystemExit(main())
