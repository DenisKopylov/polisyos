"""Reconcile frozen historical directory inputs without trusting their location alone."""

from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
import subprocess
import tomllib
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from tools.quality.validation import directory_health_inventory

SCOPE_SCHEMA = "polisyos.directory-health.frozen-git-tree.v1"
_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class FrozenArchiveScope:
    """Observed exact historical leaves and directories, not a path allowlist."""

    files: frozenset[str]
    directories: frozenset[str]
    observed_files: frozenset[str]
    measurement: dict[str, Any]


class FrozenArchiveInspectionError(ValueError):
    """Carry actual partial reads when the historical classification is undecided."""

    def __init__(self, reason: str, measurement: dict[str, Any]) -> None:
        super().__init__(reason)
        self.measurement = measurement


def measure_frozen_archives(
    repo_root: Path, directory_contracts: dict[str, Any]
) -> FrozenArchiveScope | None:
    """Bind each opted-in archive class to Git and actual no-follow worktree reads.

    Missing Git objects and unreadable deciding inputs raise ``ValueError`` or
    ``OSError``. The CLI then reports UNRUN rather than an empty historical set.
    Changed, staged, untracked and explicitly active source entries remain active.
    """
    rows = directory_contracts.get("archive_class", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("frozen_archive_classes_must_be_tables")
    if not any("frozen_scope_schema" in row or "frozen_git_tree" in row for row in rows):
        return None
    repo_root = repo_root.resolve()
    measurement: dict[str, Any] = {"schema": SCOPE_SCHEMA, "classes": [], "git_reads": []}
    try:
        return _measure_frozen_archives(repo_root, directory_contracts, measurement)
    except (OSError, ValueError) as error:
        measurement.update(
            complete=False,
            unresolved_by_construction=["frozen_archive_inspection_incomplete"],
            reason=f"{type(error).__name__}: {error}",
        )
        raise FrozenArchiveInspectionError(str(error), measurement) from error


def _measure_frozen_archives(
    repo_root: Path, directory_contracts: dict[str, Any], measurement: dict[str, Any]
) -> FrozenArchiveScope:
    classes = [
        row
        for row in directory_contracts.get("archive_class", [])
        if "frozen_scope_schema" in row or "frozen_git_tree" in row
    ]
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise ValueError("frozen_archive_no_follow_reads_unavailable")

    policy = repo_root / "architecture/policies/directory_contracts.toml"
    measurement["policy_read"] = {
        "path": "architecture/policies/directory_contracts.toml",
        "status": "attempted",
    }
    policy_bytes = policy.read_bytes()
    measurement["policy_read"] = {
        "path": "architecture/policies/directory_contracts.toml",
        "bytes": len(policy_bytes),
        "sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "status": "read",
    }
    if tomllib.loads(policy_bytes.decode("utf-8")) != directory_contracts:
        raise ValueError("frozen_archive_policy_changed_after_parse")

    def read_git(*args: str, cwd: Path | None = None) -> bytes:
        return _git(cwd or top, *args, reads=measurement["git_reads"])

    top = Path(
        os.fsdecode(read_git("rev-parse", "--show-toplevel", cwd=repo_root)).removesuffix("\n")
    ).resolve()
    prefix = repo_root.relative_to(top).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    head = read_git("rev-parse", "HEAD").decode("ascii").strip()
    algorithm = read_git("rev-parse", "--show-object-format").decode("ascii").strip()
    measurement.update(head_commit_read=head, git_object_format=algorithm)
    if algorithm not in {"sha1", "sha256"}:
        raise ValueError("frozen_archive_git_object_format_unsupported")
    all_files: set[str] = set()
    all_directories: set[str] = set()
    all_observed: set[str] = set()
    reports: list[dict[str, Any]] = measurement["classes"]
    roots: list[str] = []
    for row in classes:
        root, tree = _class_identity(row, algorithm)
        active_roots = _active_source_roots(directory_contracts, root)
        if any(_under(root, other) or _under(other, root) for other in roots):
            raise ValueError("frozen_archive_roots_overlap")
        roots.append(root)
        object_type = read_git("cat-file", "-t", tree).decode("ascii").strip()
        if object_type != "tree":
            raise ValueError("frozen_archive_object_is_not_tree")
        frozen = _tree_entries(read_git("ls-tree", "--full-tree", "-rz", tree))
        git_root = prefix + root
        current = _tree_entries(
            read_git("ls-tree", "--full-tree", "-rz", head, "--", git_root),
            strip_prefix=git_root + "/",
        )
        index_raw = read_git("ls-files", "--stage", "-z", "--", git_root)
        index = _index_entries(index_raw, strip_prefix=git_root + "/")
        observed_files, observed_dirs = _observed_paths(repo_root, root)
        historical: set[str] = set()
        blocked_dirs: set[str] = set()
        read_digest = hashlib.sha256()
        read_count = 0
        read_bytes = 0
        reasons: dict[str, int] = {}
        for relative in sorted(set(frozen) | set(observed_files)):
            logical = f"{root}/{relative}"
            expected = frozen.get(relative)
            reason = "unchanged"
            if any(_under(logical, active) for active in active_roots):
                reason = "active_source_contract"
            elif relative not in observed_files:
                reason = "missing_worktree_entry"
            elif expected is None:
                reason = "outside_frozen_tree"
            elif current.get(relative) != expected:
                reason = "head_identity_changed"
            elif index.get(relative) != expected:
                reason = "index_identity_changed"
            else:
                measurement["progress"] = {
                    "worktree_path": logical,
                    "completed_identity_reads": read_count,
                    "completed_identity_reads_sha256": read_digest.hexdigest(),
                }
                actual, count = _worktree_identity(repo_root, logical, algorithm)
                read_count += 1
                read_bytes += count
                read_digest.update(
                    os.fsencode(logical) + b"\0" + repr(actual).encode("ascii") + b"\0"
                )
                measurement["progress"].update(
                    completed_identity_reads=read_count,
                    completed_identity_reads_sha256=read_digest.hexdigest(),
                    content_bytes_read=read_bytes,
                    last_read_status="read",
                )
                if actual != expected:
                    reason = "worktree_identity_changed"
                else:
                    historical.add(logical)
            reasons[reason] = reasons.get(reason, 0) + 1
            if reason != "unchanged":
                blocked_dirs.update(_parents(logical, root))

        frozen_dirs = {root}
        for relative in frozen:
            frozen_dirs.update(_parents(f"{root}/{relative}", root))
        for directory in observed_dirs:
            if directory not in frozen_dirs or any(
                _under(directory, active) for active in active_roots
            ):
                blocked_dirs.add(directory)
                blocked_dirs.update(_parents(directory, root))
        historical_dirs = (observed_dirs & frozen_dirs) - blocked_dirs
        if read_git("ls-files", "--stage", "-z", "--", git_root) != index_raw:
            raise ValueError("frozen_archive_index_changed_during_inspection")
        if _observed_paths(repo_root, root) != (observed_files, observed_dirs):
            raise ValueError("frozen_archive_paths_changed_during_inspection")
        all_files.update(historical)
        all_directories.update(historical_dirs)
        all_observed.update(f"{root}/{relative}" for relative in observed_files)
        reports.append(
            {
                "id": row["id"],
                "owner": row["owner"],
                "root": root,
                "active_contract_override_roots": list(active_roots),
                "frozen_git_tree": tree,
                "frozen_leaf_count": len(frozen),
                "head_leaf_count": len(current),
                "index_stage_zero_leaf_count": len(index),
                "filesystem_leaf_count": len(observed_files),
                "filesystem_directory_count": len(observed_dirs),
                "historical_leaf_count": len(historical),
                "historical_directory_count": len(historical_dirs),
                "leaf_dispositions": dict(sorted(reasons.items())),
                "worktree_identity_read_count": read_count,
                "worktree_content_bytes_read": read_bytes,
                "worktree_identity_reads_sha256": read_digest.hexdigest(),
                "filesystem_paths_sha256": _path_digest(observed_files),
                "historical_paths_sha256": _path_digest(historical),
            }
        )
    measurement.pop("progress", None)
    measurement.update(
        complete=True,
        unresolved_by_construction=[],
        limitations=[
            "Git object identity is not institutional or runtime authority.",
            "Only unchanged frozen leaves and wholly reconciled directories are excluded; "
            "other filesystem entries remain in the active health scope.",
            "Symlink mode and target bytes are reconciled; target contents are not followed.",
            "Filesystem reads are observed during this operation, not an atomic filesystem "
            "snapshot or a guarantee against later mutation.",
            "Git modes cover regular/executable files and symlinks, not ACLs or ownership.",
        ],
    )
    return FrozenArchiveScope(
        frozenset(all_files),
        frozenset(all_directories),
        frozenset(all_observed),
        measurement,
    )


def _class_identity(row: dict[str, Any], algorithm: str) -> tuple[str, str]:
    if row.get("frozen_scope_schema") != SCOPE_SCHEMA or any(
        not isinstance(row.get(key), str) or not row[key].strip() for key in ("id", "owner")
    ):
        raise ValueError("frozen_archive_class_contract_invalid")
    roots = row.get("allowed_roots")
    if not isinstance(roots, list) or len(roots) != 1 or not isinstance(roots[0], str):
        raise ValueError("frozen_archive_requires_one_literal_root")
    root = roots[0].removesuffix("/")
    if not _safe_relative(root) or any(c in root for c in "*?[\\"):
        raise ValueError("frozen_archive_root_must_be_literal_relative_path")
    tree = row.get("frozen_git_tree")
    length = 40 if algorithm == "sha1" else 64
    if not isinstance(tree, str) or re.fullmatch(rf"[0-9a-f]{{{length}}}", tree) is None:
        raise ValueError("frozen_archive_tree_identity_invalid")
    return root, tree


def _active_source_roots(contract: dict[str, Any], archive_root: str) -> tuple[str, ...]:
    roots = []
    for row in contract.get("contract", []):
        if row.get("status") not in {"active", "active_transitional"}:
            continue
        root = row.get("path")
        children = row.get("allowed_child_directory_kinds", [])
        if (
            not isinstance(root, str)
            or not _safe_relative(root)
            or any(character in root for character in "*?[\\")
            or not isinstance(children, list)
            or any(not isinstance(kind, str) for kind in children)
        ):
            raise ValueError("frozen_archive_active_source_root_invalid")
        # A specific maintained contract always wins. A broader owner may host
        # the historical class only when its own contract permits archive children.
        if _under(root, archive_root) or (_under(archive_root, root) and "archive" not in children):
            roots.append(root)
    return tuple(roots)


def _git(repo_root: Path, *args: str, reads: list[dict[str, Any]]) -> bytes:
    environment = {
        **os.environ,
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    read = {
        "cwd": str(repo_root),
        "arguments": list(args),
        "status": "attempted",
        "lazy_fetch": "disabled",
        "replace_objects": "disabled",
    }
    reads.append(read)
    try:
        result = subprocess.run(  # noqa: S603 -- fixed Git command, structured local arguments.
            ["git", *args], cwd=repo_root, capture_output=True, check=False, env=environment
        )
    except OSError as error:
        read.update(status="error", error_type=type(error).__name__)
        raise
    read.update(
        {
            "exit_code": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "status": "read" if result.returncode == 0 else "error",
        }
    )
    if result.returncode:
        error = os.fsdecode(result.stderr).strip()
        raise ValueError(f"frozen_archive_git_read_unavailable: git {args[0]}: {error}")
    return result.stdout


def _tree_entries(raw: bytes, *, strip_prefix: str = "") -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        path = os.fsdecode(path_bytes)
        if strip_prefix:
            if not path.startswith(strip_prefix):
                raise ValueError("frozen_archive_git_path_outside_root")
            path = path.removeprefix(strip_prefix)
        if kind != "blob" or mode not in {"100644", "100755", "120000"} or not _safe_relative(path):
            raise ValueError("frozen_archive_git_entry_unsupported")
        if path in entries:
            raise ValueError("frozen_archive_duplicate_git_path")
        entries[path] = (mode, oid)
    return entries


def _index_entries(raw: bytes, *, strip_prefix: str) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        path = os.fsdecode(path_bytes)
        if not path.startswith(strip_prefix):
            raise ValueError("frozen_archive_index_path_outside_root")
        if stage == "0":
            entries[path.removeprefix(strip_prefix)] = (mode, oid)
    return entries


def _observed_paths(repo_root: Path, root: str) -> tuple[set[str], set[str]]:
    try:
        descriptor = directory_health_inventory.open_directory_beneath(
            repo_root, PurePosixPath(root).parts
        )
    except FileNotFoundError:
        return set(), set()
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise ValueError("frozen_archive_root_is_not_a_real_directory") from error
        raise
    files: set[str] = set()
    directories: set[str] = set()
    archive_root = repo_root / root
    try:
        with closing(
            directory_health_inventory.iter_tree_entries(
                archive_root, root_descriptor=descriptor, opaque_symlinks=True
            )
        ) as entries:
            for path, is_directory in entries:
                if is_directory:
                    directories.add(path.relative_to(repo_root).as_posix())
                else:
                    files.add(path.relative_to(archive_root).as_posix())
    finally:
        os.close(descriptor)
    return files, directories


def _worktree_identity(
    repo_root: Path, relative: str, algorithm: str
) -> tuple[tuple[str, str], int]:
    parts = PurePosixPath(relative).parts
    descriptor = directory_health_inventory.open_directory_beneath(repo_root, parts[:-1])
    try:
        before = os.stat(parts[-1], dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode):
            body = os.fsencode(os.readlink(parts[-1], dir_fd=descriptor))
            digest = _blob_hasher(algorithm, len(body))
            digest.update(body)
            mode, count = "120000", len(body)
        elif stat.S_ISREG(before.st_mode):
            mode = "100755" if before.st_mode & stat.S_IXUSR else "100644"
            digest = _blob_hasher(algorithm, before.st_size)
            child = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
            count = 0
            with os.fdopen(child, "rb") as stream:
                for chunk in iter(lambda: stream.read(_CHUNK_BYTES), b""):
                    digest.update(chunk)
                    count += len(chunk)
            if count != before.st_size:
                raise ValueError("frozen_archive_file_changed_during_read")
        else:
            return (("unsupported", ""), 0)
        after = os.stat(parts[-1], dir_fd=descriptor, follow_symlinks=False)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError("frozen_archive_file_changed_during_read")
        return ((mode, digest.hexdigest()), count)
    finally:
        os.close(descriptor)


def _blob_hasher(algorithm: str, size: int) -> Any:
    # Git SHA-1 is an object identifier, not a new security or authority claim.
    digest = hashlib.new(algorithm, usedforsecurity=False)
    digest.update(f"blob {size}\0".encode("ascii"))
    return digest


def _safe_relative(path: str) -> bool:
    return (
        bool(PurePosixPath(path).parts)
        and not path.startswith("/")
        and str(PurePosixPath(path)) == path
        and all(part not in {".", ".."} for part in PurePosixPath(path).parts)
    )


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def _parents(path: str, root: str) -> set[str]:
    return {
        parent.as_posix()
        for parent in PurePosixPath(path).parents
        if _under(parent.as_posix(), root)
    }


def _path_digest(paths: set[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(os.fsencode(path) + b"\0")
    return digest.hexdigest()
