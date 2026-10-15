#!/usr/bin/env python3
"""Compare a documentation page's declared source owners across Git commits.

The check reads only explicitly selected pages. Each page must declare one full
``Source pin`` commit ID and a ``Source of truth`` field containing backticked
repository paths or supported globs. Paths are expanded over complete tracked
trees at that pin and at the requested comparison commit. Tracked blob bytes
and Git modes are compared without exporting source files to disk.

Supported path syntax uses ``*`` and ``?`` within one path component. A
complete ``**`` component matches zero or more path components. Braces,
character classes, absolute paths, backslashes, and parent traversal are not
supported. Symlinks are checked as stored target text; their resolved target
bytes are outside the check. Gitlinks and Git LFS pointer blobs are UNRUN.

Bare paths and ``product:`` paths are product-root-relative; ``repo:`` paths
are Git-root-relative. Namespace selection never depends on path existence.

A PASS means only that every declared path/glob had tracked members and those
members' stored bytes and modes are equal at the two commits. It does not prove
that the declared set covers every claim, that the prose is true, or that tests
or deployed behavior are current.

Git reads disable lazy promisor fetch and replacement refs. Missing objects in
a partial clone therefore produce UNRUN rather than triggering a network fetch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FULL_SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")
METADATA_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 /_-]*\Z")
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1\n"
MAX_CHANGED_EXAMPLES = 8
PATH_NAMESPACE_SEMANTICS = (
    "bare and product: paths are product-root-relative; repo: paths are Git-root-relative"
)
UNMEASURED = (
    "claim coverage and prose truth",
    "test execution and semantic adequacy",
    "test source bytes outside the declared source set",
    "runtime behavior, deployment, and live services",
    "uncommitted source worktree bytes (comparison uses immutable commits)",
    "resolved bytes behind symlinks (only the stored target text is compared)",
)


class BindingError(ValueError):
    """Signal a selected document or Git input that cannot be measured."""


@dataclass(frozen=True)
class RepoContext:
    """Resolved Git and product roots for source path normalization."""

    git_root: Path
    product_root: Path
    product_prefix: str
    requested_root: Path


@dataclass(frozen=True)
class TreeEntry:
    """The tracked Git tree identity for one path."""

    mode: str
    object_type: str
    object_id: str


@dataclass(frozen=True)
class SourceMetadata:
    """A page's leading, unambiguous source binding fields."""

    source_pin: str
    patterns: tuple[str, ...]


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_NO_LAZY_FETCH"] = "1"
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def path_matches(pattern: str, path: str) -> bool:
    """Return whether a supported component glob matches a repository path.

    ``*`` and ``?`` match characters inside a single component. A complete
    ``**`` component matches zero or more path components, including slashes.
    """
    _namespace, path_pattern = _split_source_pattern(pattern)
    _validate_path_pattern(path_pattern)
    return _path_matches_parts(path_pattern.split("/"), path.split("/"))


def _path_matches_parts(pattern: list[str], path: list[str]) -> bool:
    # Dynamic programming keeps deep valid patterns bounded by input size,
    # independent of Python's recursion limit.
    previous = [False] * (len(path) + 1)
    previous[0] = True
    for component in pattern:
        current = [False] * (len(path) + 1)
        if component == "**":
            current[0] = previous[0]
            for path_index in range(1, len(path) + 1):
                current[path_index] = previous[path_index] or current[path_index - 1]
        else:
            for path_index in range(1, len(path) + 1):
                current[path_index] = previous[path_index - 1] and _component_matches(
                    component, path[path_index - 1]
                )
        previous = current
    return previous[-1]


def _component_matches(pattern: str, value: str) -> bool:
    """Match ``*`` and ``?`` in one component without bracket syntax."""
    pattern_index = 0
    value_index = 0
    star_index = -1
    retry_value_index = -1

    while value_index < len(value):
        if pattern_index < len(pattern) and (
            pattern[pattern_index] == "?" or pattern[pattern_index] == value[value_index]
        ):
            pattern_index += 1
            value_index += 1
        elif pattern_index < len(pattern) and pattern[pattern_index] == "*":
            star_index = pattern_index
            retry_value_index = value_index
            pattern_index += 1
        elif star_index >= 0:
            pattern_index = star_index + 1
            retry_value_index += 1
            value_index = retry_value_index
        else:
            return False

    while pattern_index < len(pattern) and pattern[pattern_index] == "*":
        pattern_index += 1
    return pattern_index == len(pattern)


def _split_source_pattern(pattern: str) -> tuple[str, str]:
    if pattern.startswith("repo:"):
        return "repo", pattern[len("repo:") :]
    if pattern.startswith("product:"):
        return "product", pattern[len("product:") :]
    first_component = pattern.split("/", 1)[0]
    if ":" in first_component:
        raise BindingError(f"unsupported source path namespace: {first_component!r}")
    return "product", pattern


def _validate_pattern(pattern: str) -> None:
    _namespace, path_pattern = _split_source_pattern(pattern)
    _validate_path_pattern(path_pattern)


def _validate_path_pattern(pattern: str) -> None:
    if not pattern or "\x00" in pattern:
        raise BindingError("empty or NUL-containing source path")
    if pattern.startswith("/") or DRIVE_PATH_RE.match(pattern):
        raise BindingError(f"absolute source path is unsupported: {pattern!r}")
    if "\\" in pattern:
        raise BindingError(f"backslash in source path is unsupported: {pattern!r}")
    if ":" in pattern:
        raise BindingError("colon in source path is unsupported outside repo:/product: namespace")
    if any(character in pattern for character in "{}[]"):
        raise BindingError(f"brace or character-class glob is unsupported: {pattern!r}")
    parts = pattern.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise BindingError(f"non-normalized or traversing source path: {pattern!r}")
    for part in parts:
        if "**" in part and part != "**":
            raise BindingError(f"double-star must be a complete path component: {pattern!r}")
        if "***" in part:
            raise BindingError(f"unsupported repeated-star pattern: {pattern!r}")


def _metadata_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if text.startswith(">"):
        text = text[1:].lstrip()
    if text.startswith("**"):
        closing = text.find("**", 2)
        if closing < 0:
            return None
        key = text[2:closing].strip()
        rest = text[closing + 2 :].strip()
        if key.endswith(":"):
            key = key[:-1].rstrip()
        elif rest.startswith(":"):
            rest = rest[1:].lstrip()
    elif ":" in text:
        key, rest = text.split(":", 1)
        key = key.strip()
        rest = rest.strip()
    else:
        return None
    if not METADATA_KEY_RE.fullmatch(key):
        return None
    return key, rest


def _leading_metadata(text: str) -> SourceMetadata:
    lines = text.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines) and lines[index].strip() == "---":
        index += 1
        while index < len(lines) and lines[index].strip() != "---":
            index += 1
        if index == len(lines):
            raise BindingError("unterminated YAML front matter")
        index += 1

    fields: dict[str, list[str]] = {"Source pin": [], "Source of truth": []}
    values: dict[str, list[str]] = {"Source pin": [], "Source of truth": []}
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
        parsed = _metadata_line(line)
        if parsed is not None:
            key, value = parsed
            active_field = key if key in fields else None
            if key in fields:
                fields[key].append(line)
                values[key].append(value)
            continue

        if active_field == "Source of truth" and line[:1].isspace():
            values[active_field].append(stripped)
            continue
        if active_field in fields and line.lstrip().startswith(">"):
            values[active_field].append(line.lstrip()[1:].strip())
            continue
        break

    for key, declarations in fields.items():
        if len(declarations) != 1:
            raise BindingError(
                f"expected exactly one leading {key!r} field; found {len(declarations)}"
            )

    pin_value = " ".join(values["Source pin"]).strip()
    if pin_value.startswith("`") and pin_value.endswith("`") and pin_value.count("`") == 2:
        pin_value = pin_value[1:-1]
    if not FULL_SHA_RE.fullmatch(pin_value):
        raise BindingError("Source pin must be one full 40- or 64-hex commit ID")

    source_value = "\n".join(values["Source of truth"])
    tokens = re.findall(r"`([^`\n]+)`", source_value)
    if not tokens or source_value.count("`") != 2 * len(tokens):
        raise BindingError("Source of truth must declare one or more backticked paths or globs")
    unique_tokens: list[str] = []
    for token in tokens:
        _validate_pattern(token)
        if token in unique_tokens:
            raise BindingError(f"duplicate source path/glob declaration: {token!r}")
        unique_tokens.append(token)
    return SourceMetadata(source_pin=pin_value.lower(), patterns=tuple(unique_tokens))


def _git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            input=input_bytes,
            capture_output=True,
            check=False,
            env=_git_environment(),
        )
    except OSError as exc:
        raise BindingError(f"could not run Git: {type(exc).__name__}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise BindingError(f"Git {' '.join(args[:2])} failed: {detail or result.returncode}")
    return result.stdout


def _resolve_context(requested_root: Path) -> RepoContext:
    try:
        requested = requested_root.resolve(strict=True)
    except OSError as exc:
        raise BindingError(f"repository root is unavailable: {exc}") from exc
    if not requested.is_dir():
        raise BindingError(f"repository root is not a directory: {requested}")
    raw_root = _git(requested, "rev-parse", "--show-toplevel").decode().strip()
    git_root = Path(raw_root).resolve()
    if (
        requested != git_root
        and (requested / "pyproject.toml").is_file()
        and (requested / "src").is_dir()
    ):
        product_root = requested
        prefix = product_root.relative_to(git_root).as_posix()
        return RepoContext(git_root, product_root, "" if prefix == "." else prefix, requested)
    if (
        requested == git_root
        and (git_root / "pyproject.toml").is_file()
        and (git_root / "src").is_dir()
    ):
        return RepoContext(git_root, git_root, "", requested)

    candidates: list[Path] = []
    nested_product = git_root / "policy-engine"
    if (nested_product / "pyproject.toml").is_file() and (nested_product / "src").is_dir():
        candidates.append(nested_product)
    product_root = candidates[0] if candidates else git_root
    prefix = product_root.relative_to(git_root).as_posix()
    if prefix == ".":
        prefix = ""
    return RepoContext(git_root, product_root, prefix, requested)


def _resolve_doc_path(context: RepoContext, value: str) -> tuple[Path, str]:
    provided = Path(value).expanduser()
    candidates: list[Path]
    if provided.is_absolute():
        candidates = [provided]
    else:
        candidates = [context.requested_root / provided, context.git_root / provided]
        if context.product_root != context.git_root:
            candidates.append(context.product_root / provided)
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            relative = resolved.relative_to(context.git_root).as_posix()
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            return resolved, relative
    raise BindingError(f"selected Markdown page does not resolve inside the repository: {value!r}")


def _worktree_state(
    context: RepoContext, doc_path: Path, git_path: str
) -> tuple[bytes, dict[str, Any]]:
    try:
        content = doc_path.read_bytes()
    except OSError as exc:
        raise BindingError(
            f"cannot read selected Markdown page: {type(exc).__name__}: {exc}"
        ) from exc
    status_raw = _git(
        context.git_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        git_path,
    )
    if not status_raw:
        status = "clean"
    else:
        code = status_raw[:2].decode("ascii", errors="replace")
        if code == "??":
            status = "untracked"
        elif "D" in code:
            status = "deleted"
        elif "R" in code or "C" in code:
            status = "renamed_or_copied"
        else:
            status = "modified"
    return content, {
        "status": status,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "read_count": 1,
        "source": "single selected Markdown byte buffer reused for hash and metadata parse",
    }


def _resolve_commit(context: RepoContext, value: str) -> str:
    raw = (
        _git(
            context.git_root,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{value}^{{commit}}",
        )
        .decode()
        .strip()
    )
    if not FULL_SHA_RE.fullmatch(raw):
        raise BindingError(f"Git returned a non-full commit ID for {value!r}")
    return raw.lower()


def _resolve_pinned_commit(context: RepoContext, pin: str) -> str:
    if not FULL_SHA_RE.fullmatch(pin):
        raise BindingError("Source pin is not a full commit ID")
    resolved = _resolve_commit(context, pin)
    if resolved != pin.lower():
        raise BindingError("Source pin did not resolve to the exact full commit ID")
    return resolved


def _tree(context: RepoContext, commit: str) -> dict[bytes, TreeEntry]:
    raw = _git(context.git_root, "ls-tree", "-r", "-z", "--full-tree", commit)
    entries: dict[bytes, TreeEntry] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.split(b" ", 2)
        except ValueError as exc:
            raise BindingError("Git returned an unreadable NUL-delimited tree entry") from exc
        entries[path] = TreeEntry(
            mode.decode("ascii"), object_type.decode("ascii"), object_id.decode("ascii")
        )
    return entries


def _normalize_pattern(context: RepoContext, pattern: str) -> str:
    namespace, path_pattern = _split_source_pattern(pattern)
    _validate_path_pattern(path_pattern)
    if namespace == "repo" or not context.product_prefix:
        return path_pattern
    return f"{context.product_prefix}/{path_pattern}"


def _path_matches_bytes(pattern: str, path: bytes) -> bool:
    try:
        decoded = path.decode("utf-8")
    except UnicodeDecodeError:
        # A wildcard can match a non-UTF-8 Git path, so preserve its bytes with
        # surrogate escapes for component matching rather than dropping it.
        decoded = path.decode("utf-8", errors="surrogateescape")
    return _path_matches_parts(pattern.split("/"), decoded.split("/"))


def _expand(
    patterns: tuple[tuple[str, str], ...],
    before: dict[bytes, TreeEntry],
    after: dict[bytes, TreeEntry],
) -> tuple[set[bytes], dict[str, tuple[int, int]]]:
    matched: set[bytes] = set()
    per_pattern: dict[str, tuple[int, int]] = {}
    for declared_pattern, git_pattern in patterns:
        before_paths = {path for path in before if _path_matches_bytes(git_pattern, path)}
        after_paths = {path for path in after if _path_matches_bytes(git_pattern, path)}
        per_pattern[declared_pattern] = (len(before_paths), len(after_paths))
        if not before_paths and not after_paths:
            raise BindingError(
                f"declared path/glob matches no tracked files at either commit: {declared_pattern!r}"
            )
        matched.update(before_paths)
        matched.update(after_paths)
    return matched, per_pattern


def _selected_read_digest(
    matched: set[bytes],
    before: dict[bytes, TreeEntry],
    after: dict[bytes, TreeEntry],
    blob_hashes: dict[str, dict[str, Any]],
) -> str:
    """Hash the complete selected path/mode/content comparison without listing it."""
    digest = hashlib.sha256()

    def add_field(value: bytes) -> None:
        digest.update(len(value).to_bytes(8, byteorder="big"))
        digest.update(value)

    for path in sorted(matched):
        add_field(path)
        for entry in (before.get(path), after.get(path)):
            if entry is None:
                add_field(b"absent")
                continue
            add_field(entry.mode.encode("ascii"))
            add_field(entry.object_type.encode("ascii"))
            add_field(bytes.fromhex(blob_hashes[entry.object_id]["sha256"]))
    return digest.hexdigest()


def _hash_blobs(
    context: RepoContext, object_ids: set[str]
) -> tuple[dict[str, dict[str, Any]], int]:
    """Hash unique Git blobs as a stream without exporting them to disk."""
    hashes: dict[str, dict[str, Any]] = {}
    bytes_hashed = 0
    try:
        process = subprocess.Popen(
            ["git", "-C", str(context.git_root), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_git_environment(),
        )
    except OSError as exc:
        raise BindingError(f"could not start Git blob reader: {type(exc).__name__}: {exc}") from exc
    if process.stdin is None or process.stdout is None:
        process.kill()
        process.wait()
        raise BindingError("Git blob reader did not expose its batch streams")
    stdin = process.stdin
    stdout = process.stdout
    try:
        for object_id in sorted(object_ids):
            stdin.write(object_id.encode("ascii") + b"\n")
            stdin.flush()
            header = stdout.readline()
            fields = header.rstrip(b"\n").split(b" ")
            if len(fields) != 3 or fields[0].decode("ascii", errors="replace") != object_id:
                raise BindingError(f"Git could not resolve declared blob {object_id}")
            if fields[1] != b"blob":
                raise BindingError(f"Git object {object_id} is not a blob")
            try:
                size = int(fields[2])
            except ValueError as exc:
                raise BindingError(f"Git returned an invalid blob size for {object_id}") from exc
            digest = hashlib.sha256()
            prefix = bytearray()
            remaining = size
            while remaining:
                chunk = stdout.read(min(64 * 1024, remaining))
                if not chunk:
                    raise BindingError(f"Git truncated blob {object_id}")
                digest.update(chunk)
                if len(prefix) < len(LFS_HEADER):
                    prefix.extend(chunk[: len(LFS_HEADER) - len(prefix)])
                remaining -= len(chunk)
            if stdout.read(1) != b"\n":
                raise BindingError(f"Git blob framing failed for {object_id}")
            hashes[object_id] = {
                "sha256": digest.hexdigest(),
                "bytes": size,
                "lfs_pointer": bytes(prefix).startswith(LFS_HEADER),
            }
            bytes_hashed += size
        stdin.close()
        return_code = process.wait()
        stderr = process.stderr.read() if process.stderr is not None else b""
        if return_code:
            raise BindingError(
                "Git blob reader failed: " + stderr.decode("utf-8", errors="replace").strip()
            )
    except Exception:
        process.kill()
        process.wait()
        raise
    return hashes, bytes_hashed


def _changed_examples(paths: set[bytes]) -> list[str]:
    return [
        path.decode("utf-8", errors="backslashreplace").encode("unicode_escape").decode("ascii")
        for path in sorted(paths)[:MAX_CHANGED_EXAMPLES]
    ]


def _check_one(
    context: RepoContext, doc_argument: str, against_commit: str | None, against_error: str | None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "doc": doc_argument,
        "status": "UNRUN",
        "against_commit": against_commit,
        "unmeasured": list(UNMEASURED),
        "git_read_policy": {
            "lazy_fetch": "disabled; missing objects return UNRUN",
            "replacement_refs": "disabled; reads the object named by the commit ID",
        },
    }
    try:
        doc_path, git_path = _resolve_doc_path(context, doc_argument)
        result["doc"] = git_path
        doc_bytes, doc_worktree = _worktree_state(context, doc_path, git_path)
        result["doc_worktree"] = doc_worktree
        if against_error:
            raise BindingError(against_error)
        try:
            text = doc_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BindingError("selected Markdown page is not valid UTF-8") from exc
        metadata = _leading_metadata(text)
        result["source_pin"] = metadata.source_pin
        result["pattern_count"] = len(metadata.patterns)
        pin_commit = _resolve_pinned_commit(context, metadata.source_pin)
        result["source_pin_commit"] = pin_commit
        assert against_commit is not None
        before = _tree(context, pin_commit)
        after = _tree(context, against_commit)
        normalized_patterns = tuple(
            (pattern, _normalize_pattern(context, pattern)) for pattern in metadata.patterns
        )
        matched, expansions = _expand(normalized_patterns, before, after)
        result["pattern_expansion"] = {
            pattern: {"at_source_pin": counts[0], "at_comparison_commit": counts[1]}
            for pattern, counts in expansions.items()
        }
        result["matched_path_count"] = len(matched)

        before_ids = {before[path].object_id for path in matched if path in before}
        after_ids = {after[path].object_id for path in matched if path in after}
        gitlinks = {
            path
            for path in matched
            if any(
                entry is not None and (entry.mode == "160000" or entry.object_type == "commit")
                for entry in (before.get(path), after.get(path))
            )
        }
        if gitlinks:
            raise BindingError(
                f"declared source set contains {len(gitlinks)} gitlink(s); submodule bytes are unavailable"
            )
        unsupported = {
            path
            for path in matched
            if any(
                entry is not None and entry.object_type != "blob"
                for entry in (before.get(path), after.get(path))
            )
        }
        if unsupported:
            raise BindingError(f"declared source set contains {len(unsupported)} non-blob path(s)")

        blob_hashes, bytes_hashed = _hash_blobs(context, before_ids | after_ids)
        result["unique_blob_object_count"] = len(blob_hashes)
        result["unique_blob_bytes_hashed"] = bytes_hashed
        lfs_paths = {
            path
            for path in matched
            if any(
                entry is not None and blob_hashes[entry.object_id]["lfs_pointer"]
                for entry in (before.get(path), after.get(path))
            )
        }
        if lfs_paths:
            raise BindingError(
                f"declared source set contains {len(lfs_paths)} Git LFS pointer blob(s); external objects are unavailable"
            )

        added = {path for path in matched if path not in before and path in after}
        removed = {path for path in matched if path in before and path not in after}
        common = {path for path in matched if path in before and path in after}
        content_changed = {
            path
            for path in common
            if blob_hashes[before[path].object_id]["sha256"]
            != blob_hashes[after[path].object_id]["sha256"]
        }
        mode_changed = {path for path in common if before[path].mode != after[path].mode}
        unchanged = common - content_changed - mode_changed
        symlinks = {
            path
            for path in matched
            if any(
                entry is not None and entry.mode == "120000"
                for entry in (before.get(path), after.get(path))
            )
        }
        drift_paths = added | removed | content_changed | mode_changed
        selected_read_digest = _selected_read_digest(matched, before, after, blob_hashes)
        result.update(
            {
                "status": "FAILED" if drift_paths else "PASS",
                "matched_path_count": len(matched),
                "unchanged_path_count": len(unchanged),
                "added_path_count": len(added),
                "removed_path_count": len(removed),
                "content_changed_path_count": len(content_changed),
                "mode_changed_path_count": len(mode_changed),
                "symlink_path_count": len(symlinks),
                "selected_read_set_sha256": selected_read_digest,
                "changed_path_examples": _changed_examples(drift_paths),
                "changed_path_examples_omitted": max(0, len(drift_paths) - MAX_CHANGED_EXAMPLES),
                "source_bytes": "Git blob contents read through cat-file; no files exported",
            }
        )
        if drift_paths:
            result["reason"] = (
                "declared source members or stored modes differ between the pinned and comparison commits"
            )
        return result
    except (BindingError, OSError, UnicodeError, KeyError, AssertionError) as exc:
        result["status"] = "UNRUN"
        result["reason"] = str(exc) or type(exc).__name__
        return result


def _print_text(report: dict[str, Any]) -> None:
    for document in report["documents"]:
        status = document["status"]
        fields = [status, str(document["doc"])]
        if document.get("source_pin"):
            fields.append(f"pin={document['source_pin']}")
        if document.get("against_commit"):
            fields.append(f"against={document['against_commit']}")
        if document.get("matched_path_count") is not None:
            fields.append(f"paths={document['matched_path_count']}")
            fields.append(f"unchanged={document.get('unchanged_path_count', 0)}")
            fields.append(f"added={document.get('added_path_count', 0)}")
            fields.append(f"removed={document.get('removed_path_count', 0)}")
            fields.append(f"content_changed={document.get('content_changed_path_count', 0)}")
            fields.append(f"mode_changed={document.get('mode_changed_path_count', 0)}")
        worktree = document.get("doc_worktree")
        if worktree:
            fields.append(f"doc_worktree={worktree['status']}")
            fields.append(f"doc_sha256={worktree['sha256']}")
        if document.get("reason"):
            fields.append(f"reason={document['reason']}")
        print(" ".join(fields))
        examples = document.get("changed_path_examples", [])
        if examples:
            suffix = (
                f" (+{document['changed_path_examples_omitted']} more)"
                if document.get("changed_path_examples_omitted")
                else ""
            )
            print(f"  changed examples: {', '.join(examples)}{suffix}")
    print("Unmeasured: " + "; ".join(UNMEASURED))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Git root or product root (default: this tool's product root)",
    )
    parser.add_argument(
        "--doc",
        action="append",
        required=True,
        help="explicit Markdown page to check; repeat for each selected page",
    )
    parser.add_argument(
        "--against-ref",
        default="HEAD",
        help="comparison Git ref, resolved once to an immutable full commit ID (default: HEAD)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the explicitly scoped source-binding comparison."""
    args = _parser().parse_args(argv)
    try:
        context = _resolve_context(args.repo_root)
    except BindingError as exc:
        report = {
            "against_ref": args.against_ref,
            "against_commit": None,
            "documents": [
                {
                    "doc": doc,
                    "status": "UNRUN",
                    "reason": str(exc),
                    "unmeasured": list(UNMEASURED),
                    "git_read_policy": {
                        "lazy_fetch": "disabled; missing objects return UNRUN",
                        "replacement_refs": "disabled; reads the object named by the commit ID",
                    },
                }
                for doc in args.doc
            ],
            "measured_property": "declared tracked source bytes and modes are equal across two immutable commits",
            "path_namespace_semantics": PATH_NAMESPACE_SEMANTICS,
            "unmeasured": list(UNMEASURED),
        }
        if args.format == "json":
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_text(report)
        return 2

    against_commit: str | None = None
    against_error: str | None = None
    try:
        against_commit = _resolve_commit(context, args.against_ref)
    except BindingError as exc:
        against_error = str(exc)

    documents = [_check_one(context, doc, against_commit, against_error) for doc in args.doc]
    report = {
        "against_ref": args.against_ref,
        "against_commit": against_commit,
        "documents": documents,
        "measured_property": "declared tracked source bytes and modes are equal across two immutable commits",
        "unmeasured": list(UNMEASURED),
        "glob_semantics": "* and ? stay within one component; a complete ** component matches zero or more components",
        "path_namespace_semantics": PATH_NAMESPACE_SEMANTICS,
    }
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)
    statuses = {document["status"] for document in documents}
    if "UNRUN" in statuses:
        return 2
    if "FAILED" in statuses:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
