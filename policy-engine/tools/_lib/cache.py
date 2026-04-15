"""Shared cache and incremental-execution helpers for tools."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools._lib.fs import atomic_write_json

DEFAULT_TOOL_CACHE_ROOT = ".polisyos-tools"
DEFAULT_TOOL_CACHE_NAMESPACE = "cache"
BASELINE_NAMESPACE = "_baselines"


def stable_json_hash(payload: Any) -> str:
    """Return a deterministic SHA-256 hash for JSON-compatible metadata."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def cache_path(cache_root: Path, namespace: str, key: str, suffix: str = ".json") -> Path:
    """Build a stable, filesystem-safe cache path."""

    safe_namespace = namespace.replace("/", "_").replace("..", "_")
    safe_key = key.replace("/", "_").replace("..", "_")
    return cache_root / safe_namespace / f"{safe_key}{suffix}"


def default_cache_root(repo_root: Path | None = None) -> Path:
    """Return the repository-local cache root used by tooling."""

    root = (repo_root or Path.cwd()).resolve()
    return root / DEFAULT_TOOL_CACHE_ROOT / DEFAULT_TOOL_CACHE_NAMESPACE


def content_addressable_key(*, version: str, payload: Mapping[str, Any]) -> str:
    """Build a deterministic cache key for a payload version."""

    return stable_json_hash({"version": version, **payload})


def read_json_cache(path: Path) -> dict[str, Any] | None:
    """Read a cached JSON payload if present and valid."""

    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def write_json_cache(path: Path, payload: Mapping[str, Any]) -> None:
    """Persist a JSON payload atomically."""

    atomic_write_json(path, dict(payload))


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def git_changed_files(
    repo_root: Path,
    *,
    base_ref: str = "HEAD",
    include_untracked: bool = True,
    pathspecs: Sequence[str | Path] | None = None,
) -> list[Path]:
    """Return changed files for the current worktree relative to ``base_ref``."""

    repo_root = repo_root.resolve()
    path_args = [str(spec) for spec in (pathspecs or ())]
    diff_command = [
        "git",
        "-C",
        str(repo_root),
        "diff",
        "--name-only",
        "--diff-filter=ACMRD",
        base_ref,
        "--",
        *path_args,
    ]
    changed: set[Path] = set()

    diff_result = subprocess.run(
        diff_command,
        check=False,
        capture_output=True,
        text=True,
    )
    if diff_result.returncode != 0:
        return []
    for line in diff_result.stdout.splitlines():
        rel_path = line.strip()
        if not rel_path:
            continue
        changed.add((repo_root / rel_path).resolve())

    if include_untracked:
        untracked_result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard", "--", *path_args],
            check=False,
            capture_output=True,
            text=True,
        )
        if untracked_result.returncode == 0:
            for line in untracked_result.stdout.splitlines():
                rel_path = line.strip()
                if not rel_path:
                    continue
                changed.add((repo_root / rel_path).resolve())

    return sorted(changed)


def baseline_record_path(cache_root: Path, namespace: str, label: str) -> Path:
    """Return the persisted baseline record path for a tool namespace."""

    safe_label = label.replace("/", "_").replace("..", "_").strip() or "default"
    return cache_root / namespace / BASELINE_NAMESPACE / f"{safe_label}.json"


def baseline_matches(
    cache_root: Path,
    namespace: str,
    label: str,
    *,
    fingerprint: str,
) -> bool:
    """Return ``True`` when a successful persisted baseline matches ``fingerprint``."""

    record = read_json_cache(baseline_record_path(cache_root, namespace, label))
    if record is None:
        return False
    return (
        str(record.get("fingerprint") or "") == fingerprint
        and int(record.get("exit_code", 1)) == 0
    )


def persist_baseline(
    cache_root: Path,
    namespace: str,
    label: str,
    *,
    fingerprint: str,
    exit_code: int,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Persist the latest tool baseline fingerprint for future skip-if-unchanged checks."""

    write_json_cache(
        baseline_record_path(cache_root, namespace, label),
        {
            "fingerprint": fingerprint,
            "exit_code": exit_code,
            "updated_at": datetime.now(UTC).isoformat(),
            "metadata": dict(metadata or {}),
        },
    )


def filter_paths_under_root(paths: Sequence[Path], root: Path) -> list[Path]:
    """Return only paths contained by ``root``."""

    resolved_root = root.resolve()
    return [path for path in paths if _path_is_relative_to(path.resolve(), resolved_root)]
