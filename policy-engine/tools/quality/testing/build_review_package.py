#!/usr/bin/env python3
"""Build deterministic, offline review packages for a Git commit range."""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final

PACKAGE_MAGIC: Final = b"POLISYOS_REVIEW_PACKAGE\n"
SCHEMA_VERSION: Final = 1
_GIT_CONTEXT_ENVIRONMENT_KEYS: Final = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_ATTR_SOURCE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_DIFF_OPTS",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_EXEC_PATH",
    "GIT_INDEX_FILE",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_TEMPLATE_DIR",
    "GIT_WORK_TREE",
)
_COMMON_DIFF_ARGUMENTS: Final = (
    "--ignore-submodules=none",
    "--submodule=short",
    "--find-renames=50%",
    "--diff-algorithm=histogram",
    "--no-indent-heuristic",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--no-relative",
)
_PATCH_DIFF_ARGUMENTS: Final = (
    "--patch",
    "--binary",
    "--full-index",
    "--unified=3",
    "--inter-hunk-context=0",
    "--src-prefix=a/",
    "--dst-prefix=b/",
)
_NEUTRALIZED_REPOSITORY_CONFIG_KEYS: Final = frozenset(
    {
        "color.ui",
        "core.attributesfile",
        "core.pager",
        "core.quotepath",
        "diff.algorithm",
        "diff.context",
        "diff.external",
        "diff.ignoresubmodules",
        "diff.indentheuristic",
        "diff.interhunkcontext",
        "diff.mnemonicprefix",
        "diff.noprefix",
        "diff.orderfile",
        "diff.renamelimit",
        "diff.submodule",
    }
)
_IRRELEVANT_REPOSITORY_CONFIG_KEYS: Final = frozenset(
    {
        # Repository layout and filesystem facts are consumed during discovery but
        # cannot alter a diff between the two already-resolved commit objects.
        "core.bare",
        "core.filemode",
        "core.hookspath",
        "core.ignorecase",
        "core.logallrefupdates",
        "core.precomposeunicode",
        "core.repositoryformatversion",
        "core.sharedrepository",
        "core.sparsecheckout",
        "core.sparsecheckoutcone",
        "core.symlinks",
        "core.worktree",
        "extensions.compatobjectformat",
        "extensions.objectformat",
        "extensions.partialclone",
        "extensions.preciousobjects",
        "extensions.refstorage",
        "extensions.worktreeconfig",
    }
)


class ReviewPackageError(RuntimeError):
    """Raised when a review package cannot be proven safe to build."""


@dataclass(frozen=True)
class _Repository:
    """Filesystem-anchored identity for the invoking Git worktree."""

    worktree: Path
    git_dir: Path
    common_dir: Path
    object_dir: Path
    object_format: str


@dataclass(frozen=True)
class _BoundOutput:
    """Verified output parent held open across package rendering."""

    parent_fd: int
    parent_path: Path
    filename: str


def _git_environment(*, attribute_source: str | None = None) -> dict[str, str]:
    """Return a noninteractive Git environment with external execution disabled."""

    environment = os.environ.copy()
    for key in _GIT_CONTEXT_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    for key in tuple(environment):
        if key == "GIT_CONFIG_COUNT" or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(key, None)
    environment.pop("GIT_EXTERNAL_DIFF", None)
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PAGER": "cat",
        }
    )
    if attribute_source is not None:
        environment["GIT_ATTR_SOURCE"] = attribute_source
    return environment


def _git_argv(
    *arguments: str,
    git_dir: Path | None = None,
    work_tree: Path | None = None,
) -> list[str]:
    """Build a pinned Git argument vector for deterministic read-only commands."""

    repository_arguments: list[str] = []
    if git_dir is not None:
        repository_arguments.append(f"--git-dir={git_dir}")
    if work_tree is not None:
        repository_arguments.append(f"--work-tree={work_tree}")
    return [
        "git",
        "--no-pager",
        "--no-replace-objects",
        "--literal-pathspecs",
        *repository_arguments,
        "-c",
        "color.ui=false",
        "-c",
        "core.pager=cat",
        "-c",
        "core.quotePath=true",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        "diff.algorithm=histogram",
        "-c",
        "diff.context=3",
        "-c",
        "diff.indentHeuristic=false",
        "-c",
        "diff.interHunkContext=0",
        "-c",
        "diff.mnemonicPrefix=false",
        "-c",
        "diff.noprefix=false",
        "-c",
        f"diff.orderFile={os.devnull}",
        "-c",
        "diff.renameLimit=32767",
        *arguments,
    ]


def _run_git(
    cwd: Path,
    *arguments: str,
    accepted_codes: tuple[int, ...] = (0,),
    attribute_source: str | None = None,
    git_dir: Path | None = None,
    work_tree: Path | None = None,
) -> bytes:
    """Run one read-only Git command without a shell and return stdout bytes."""

    result = subprocess.run(  # noqa: S603 - Git argv is explicit and never shell-expanded.
        _git_argv(*arguments, git_dir=git_dir, work_tree=work_tree),
        cwd=cwd,
        env=_git_environment(attribute_source=attribute_source),
        check=False,
        capture_output=True,
        shell=False,
    )
    if result.returncode not in accepted_codes:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        rendered = " ".join(arguments[:2])
        raise ReviewPackageError(
            f"git {rendered} failed with exit {result.returncode}: {detail or 'no diagnostic'}"
        )
    return result.stdout


def _find_git_marker(invocation_cwd: Path) -> tuple[Path, Path]:
    """Find the physical worktree marker without consulting repository config."""

    current = invocation_cwd
    while True:
        marker = current / ".git"
        if marker.is_symlink():
            raise ReviewPackageError("Git worktree marker must not be a symlink")
        if marker.exists():
            return current, marker
        if current == current.parent:
            raise ReviewPackageError("invocation directory is not inside a Git worktree")
        current = current.parent


def _git_dir_from_marker(marker: Path) -> Path:
    """Resolve a directory or linked-worktree ``.git`` marker."""

    if marker.is_dir():
        return marker.resolve(strict=True)
    if not marker.is_file():
        raise ReviewPackageError("Git worktree marker must be a file or directory")
    try:
        payload = marker.read_bytes().removesuffix(b"\n").removesuffix(b"\r")
    except OSError as exc:
        raise ReviewPackageError("Git worktree marker could not be read") from exc
    prefix = b"gitdir: "
    if not payload.startswith(prefix) or b"\n" in payload or b"\r" in payload:
        raise ReviewPackageError("Git worktree marker is malformed")
    raw_path = payload.removeprefix(prefix)
    if not raw_path or b"\x00" in raw_path:
        raise ReviewPackageError("Git worktree marker has an invalid git-dir path")
    path = Path(os.fsdecode(raw_path))
    if not path.is_absolute():
        path = marker.parent / path
    try:
        git_dir = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ReviewPackageError("Git worktree administrative directory does not exist") from exc
    if not git_dir.is_dir():
        raise ReviewPackageError("Git worktree administrative path must be a directory")
    return git_dir


def _decode_absolute_git_path(payload: bytes, *, label: str) -> Path:
    """Decode and validate one absolute path emitted by anchored Git."""

    raw_path = payload.rstrip(b"\r\n")
    if not raw_path:
        raise ReviewPackageError(f"git returned an empty {label} path")
    path = Path(os.fsdecode(raw_path))
    if not path.is_absolute():
        raise ReviewPackageError(f"git returned a non-absolute {label} path")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ReviewPackageError(f"git returned a missing {label} path") from exc
    if not resolved.is_dir():
        raise ReviewPackageError(f"git returned a non-directory {label} path")
    return resolved


def _discover_repository(invocation_cwd: Path) -> _Repository:
    """Anchor the invoking worktree and its Git administration by filesystem identity."""

    worktree, marker = _find_git_marker(invocation_cwd)
    git_dir = _git_dir_from_marker(marker)
    anchored_arguments = {"git_dir": git_dir, "work_tree": worktree}
    reported_git_dir = _decode_absolute_git_path(
        _run_git(
            worktree,
            "rev-parse",
            "--path-format=absolute",
            "--absolute-git-dir",
            **anchored_arguments,
        ),
        label="Git directory",
    )
    if reported_git_dir != git_dir:
        raise ReviewPackageError("Git directory identity changed during discovery")
    common_dir = _decode_absolute_git_path(
        _run_git(
            worktree,
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
            **anchored_arguments,
        ),
        label="common Git directory",
    )
    object_dir = _decode_absolute_git_path(
        _run_git(
            worktree,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "objects",
            **anchored_arguments,
        ),
        label="object directory",
    )
    raw_format = _run_git(
        worktree,
        "rev-parse",
        "--show-object-format=storage",
        **anchored_arguments,
    ).strip()
    try:
        object_format = raw_format.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ReviewPackageError("Git returned a non-ASCII object format") from exc
    if object_format not in {"sha1", "sha256"}:
        raise ReviewPackageError("Git returned an unsupported object format")
    return _Repository(
        worktree=worktree,
        git_dir=git_dir,
        common_dir=common_dir,
        object_dir=object_dir,
        object_format=object_format,
    )


def _resolve_commit(repository: _Repository, revision: str, *, label: str) -> str:
    """Resolve and peel one revision to a real commit object."""

    if not revision or "\x00" in revision:
        raise ReviewPackageError(f"{label} revision must not be empty or contain NUL")
    raw_commit = _run_git(
        repository.worktree,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{revision}^{{commit}}",
        git_dir=repository.git_dir,
        work_tree=repository.worktree,
    ).strip()
    try:
        commit = raw_commit.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ReviewPackageError(f"{label} revision resolved to a non-ASCII object id") from exc
    if not commit or any(character not in "0123456789abcdef" for character in commit):
        raise ReviewPackageError(f"{label} revision did not resolve to a full commit id")
    return commit


def _require_ancestor(git_context: Path, base_commit: str, head_commit: str) -> None:
    """Fail unless ``base_commit`` is an ancestor of ``head_commit``."""

    result = subprocess.run(  # noqa: S603 - Git argv is explicit and never shell-expanded.
        _git_argv("merge-base", "--is-ancestor", base_commit, head_commit),
        cwd=git_context,
        env=_git_environment(),
        check=False,
        capture_output=True,
        shell=False,
    )
    if result.returncode == 1:
        raise ReviewPackageError("base commit is not an ancestor of head commit")
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewPackageError(
            "git merge-base --is-ancestor failed with exit "
            f"{result.returncode}: {detail or 'no diagnostic'}"
        )


def _require_neutral_info_attributes(repository: _Repository) -> None:
    """Fail closed when unversioned repository-local attributes could affect a diff."""

    raw_path = _run_git(
        repository.worktree,
        "rev-parse",
        "--git-path",
        "info/attributes",
        git_dir=repository.git_dir,
        work_tree=repository.worktree,
    ).rstrip(b"\r\n")
    if not raw_path:
        raise ReviewPackageError("git returned an empty info/attributes path")
    attributes_path = Path(os.fsdecode(raw_path))
    if not attributes_path.is_absolute():
        attributes_path = repository.worktree / attributes_path
    attributes_path = Path(os.path.abspath(attributes_path))
    if attributes_path.is_symlink():
        raise ReviewPackageError("unversioned info/attributes must not be a symlink")
    if not attributes_path.exists():
        return
    if not attributes_path.is_file():
        raise ReviewPackageError("unversioned info/attributes must be a regular file")
    try:
        payload = attributes_path.read_bytes()
    except OSError as exc:
        raise ReviewPackageError("unversioned info/attributes could not be verified") from exc
    if payload:
        raise ReviewPackageError("unversioned info/attributes must be absent or empty")


def _configured_repository_keys(repository: _Repository, *, scope: str) -> tuple[str, ...]:
    """Return every effective key from one repository-owned config scope."""

    raw_config = _run_git(
        repository.worktree,
        "config",
        f"--{scope}",
        "--includes",
        "--null",
        "--get-regexp",
        r".",
        accepted_codes=(0, 1),
        git_dir=repository.git_dir,
        work_tree=repository.worktree,
    )
    if not raw_config:
        return ()
    if not raw_config.endswith(b"\x00"):
        raise ReviewPackageError(f"{scope} Git config returned an unterminated record")
    keys: set[str] = set()
    for record in raw_config.removesuffix(b"\x00").split(b"\x00"):
        raw_key, separator, _value = record.partition(b"\n")
        if not separator or not raw_key:
            raise ReviewPackageError(f"{scope} Git config returned a malformed record")
        try:
            key = raw_key.decode("utf-8").casefold()
        except UnicodeDecodeError as exc:
            raise ReviewPackageError(f"{scope} Git config returned a non-UTF-8 key") from exc
        keys.add(key)
    return tuple(sorted(keys))


def _has_named_suffix(key: str, *, prefix: str, suffixes: frozenset[str]) -> bool:
    """Return whether a namespaced config key has one allowed terminal field."""

    if not key.startswith(prefix):
        return False
    name, separator, suffix = key.removeprefix(prefix).rpartition(".")
    return bool(name and separator and suffix in suffixes)


def _repository_config_key_is_bound(key: str) -> bool:
    """Return whether a repository key is irrelevant or explicitly neutralized."""

    if key in _NEUTRALIZED_REPOSITORY_CONFIG_KEYS:
        return True
    if key in _IRRELEVANT_REPOSITORY_CONFIG_KEYS:
        return True
    if key.startswith("color.diff."):
        return True
    if key.startswith("pager."):
        return True
    if key.startswith("diff.") and key.endswith(".textconv"):
        return True
    if _has_named_suffix(
        key,
        prefix="branch.",
        suffixes=frozenset({"merge", "remote", "vscode-merge-base"}),
    ):
        return True
    if _has_named_suffix(
        key,
        prefix="remote.",
        suffixes=frozenset({"fetch", "partialclonefilter", "promisor", "url"}),
    ):
        return True
    return _has_named_suffix(
        key,
        prefix="submodule.",
        suffixes=frozenset({"active", "ignore", "url"}),
    )


def _require_bound_repository_configuration(repository: _Repository) -> None:
    """Fail closed on repository-owned settings outside the deterministic boundary."""

    unsupported = [
        f"{scope}:{key}"
        for scope in ("local", "worktree")
        for key in _configured_repository_keys(repository, scope=scope)
        if not _repository_config_key_is_bound(key)
    ]
    if unsupported:
        rendered = ", ".join(unsupported)
        raise ReviewPackageError(
            "repository-owned Git configuration is not bound or allowlisted: " + rendered
        )


def _is_at_or_below(path: Path, root: Path) -> bool:
    """Return whether ``path`` is ``root`` or one of its descendants."""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_symlink_components(path: Path, *, worktree: Path, label: str) -> None:
    """Reject an existing symlink at any worktree-relative path component."""

    relative = path.relative_to(worktree)
    current = worktree
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ReviewPackageError(f"{label} path must not traverse a symlink")
        if not current.exists():
            break


def _touches_admin_state(path: Path, *, admin_roots: tuple[Path, ...]) -> bool:
    """Detect administrative ancestors by inode, including case-folded aliases."""

    current = path if path.exists() else path.parent
    while True:
        for admin_root in admin_roots:
            if _is_at_or_below(current, admin_root):
                return True
            try:
                if current.exists() and admin_root.exists() and current.samefile(admin_root):
                    return True
            except OSError:
                continue
        if current == current.parent:
            return False
        current = current.parent


def _paths_alias(left: Path, right: Path) -> bool:
    """Compare path identity lexically and by filesystem inode when both exist."""

    if left == right:
        return True
    if not left.exists() or not right.exists():
        return False
    try:
        return left.samefile(right)
    except OSError as exc:
        raise ReviewPackageError(
            "output/checklist filesystem identity could not be verified"
        ) from exc


def _resolve_inside_worktree(
    raw_path: str | Path,
    *,
    invocation_cwd: Path,
    repository: _Repository,
    label: str,
    must_exist: bool = False,
) -> Path:
    """Resolve a file path and reject symlinks, admin paths, or worktree escapes."""

    worktree = repository.worktree
    rendered = str(raw_path)
    if not rendered or "\x00" in rendered:
        raise ReviewPackageError(f"{label} path must not be empty or contain NUL")
    candidate = Path(rendered)
    if not candidate.is_absolute():
        candidate = invocation_cwd / candidate
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical.relative_to(worktree)
    except ValueError as exc:
        raise ReviewPackageError(f"{label} path must stay inside the Git worktree") from exc
    git_marker = worktree / ".git"
    if _is_at_or_below(lexical, git_marker):
        raise ReviewPackageError(f"{label} path must not target the Git marker")
    _reject_symlink_components(lexical, worktree=worktree, label=label)
    try:
        resolved = lexical.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise ReviewPackageError(f"{label} path does not exist") from exc
    try:
        resolved.relative_to(worktree)
    except ValueError as exc:
        raise ReviewPackageError(f"{label} real path must stay inside the Git worktree") from exc
    if _touches_admin_state(
        resolved,
        admin_roots=(git_marker, repository.git_dir, repository.common_dir),
    ):
        raise ReviewPackageError(f"{label} path must not target Git administrative state")
    if must_exist and not resolved.exists():
        raise ReviewPackageError(f"{label} path does not exist")
    if resolved.exists() and not resolved.is_file():
        raise ReviewPackageError(f"{label} path must name a file")
    return resolved


def _directory_open_flags() -> int:
    """Return flags that open a directory without following its final component."""

    try:
        return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    except AttributeError as exc:
        raise ReviewPackageError("secure directory-descriptor writes are unsupported") from exc


@contextmanager
def _bind_output_parent(destination: Path, *, worktree: Path) -> Iterator[_BoundOutput]:
    """Hold the verified output parent open without following path components."""

    try:
        relative_parent = destination.parent.relative_to(worktree)
    except ValueError as exc:
        raise ReviewPackageError("output parent must stay inside the Git worktree") from exc
    flags = _directory_open_flags()
    parent_fd: int | None = None
    try:
        parent_fd = os.open(worktree, flags)
        for component in relative_parent.parts:
            try:
                child_fd = os.open(component, flags, dir_fd=parent_fd)
            except FileNotFoundError:
                with suppress(FileExistsError):
                    os.mkdir(component, mode=0o755, dir_fd=parent_fd)
                child_fd = os.open(component, flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = child_fd
    except OSError as exc:
        if parent_fd is not None:
            os.close(parent_fd)
        raise ReviewPackageError("output parent could not be bound without symlinks") from exc
    try:
        yield _BoundOutput(
            parent_fd=parent_fd,
            parent_path=destination.parent,
            filename=destination.name,
        )
    finally:
        os.close(parent_fd)


def _bound_parent_matches_path(bound_output: _BoundOutput) -> bool:
    """Return whether the output pathname still names the held directory."""

    try:
        path_stat = os.stat(bound_output.parent_path, follow_symlinks=False)
        descriptor_stat = os.fstat(bound_output.parent_fd)
    except OSError:
        return False
    return os.path.samestat(path_stat, descriptor_stat)


def _snapshot_bound_destination(bound_output: _BoundOutput) -> str | None:
    """Hard-link the prior regular output so a detected parent race can roll back."""

    try:
        destination_stat = os.stat(
            bound_output.filename,
            dir_fd=bound_output.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(destination_stat.st_mode):
        raise ReviewPackageError("output changed to a non-regular file after validation")
    backup_name = f".polisyos-review-prior-{secrets.token_hex(16)}.tmp"
    try:
        os.link(
            bound_output.filename,
            backup_name,
            src_dir_fd=bound_output.parent_fd,
            dst_dir_fd=bound_output.parent_fd,
            follow_symlinks=False,
        )
        backup_stat = os.stat(
            backup_name,
            dir_fd=bound_output.parent_fd,
            follow_symlinks=False,
        )
        if not os.path.samestat(destination_stat, backup_stat):
            raise ReviewPackageError("output changed while its prior version was preserved")
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(backup_name, dir_fd=bound_output.parent_fd)
        raise
    return backup_name


def _restore_bound_destination(
    bound_output: _BoundOutput,
    *,
    backup_name: str | None,
) -> None:
    """Restore the pre-replace output (or absence) inside the still-held directory."""

    if backup_name is None:
        with suppress(FileNotFoundError):
            os.unlink(bound_output.filename, dir_fd=bound_output.parent_fd)
    else:
        os.replace(
            backup_name,
            bound_output.filename,
            src_dir_fd=bound_output.parent_fd,
            dst_dir_fd=bound_output.parent_fd,
        )
    os.fsync(bound_output.parent_fd)


def _atomic_write_bound_output(bound_output: _BoundOutput, payload: bytes) -> None:
    """Atomically replace an output relative to its verified parent descriptor."""

    if not _bound_parent_matches_path(bound_output):
        raise ReviewPackageError("output parent changed after validation")
    temporary_name = f".polisyos-review-{secrets.token_hex(16)}.tmp"
    temporary_fd: int | None = None
    backup_name: str | None = None
    preserve_backup = False
    try:
        temporary_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=bound_output.parent_fd,
        )
        remaining = memoryview(payload)
        while remaining:
            written = os.write(temporary_fd, remaining)
            if written <= 0:
                raise OSError("atomic package write made no progress")
            remaining = remaining[written:]
        os.fsync(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = None
        if not _bound_parent_matches_path(bound_output):
            raise ReviewPackageError("output parent changed during package write")
        backup_name = _snapshot_bound_destination(bound_output)
        if not _bound_parent_matches_path(bound_output):
            raise ReviewPackageError("output parent changed before atomic replace")
        os.replace(
            temporary_name,
            bound_output.filename,
            src_dir_fd=bound_output.parent_fd,
            dst_dir_fd=bound_output.parent_fd,
        )
        if not _bound_parent_matches_path(bound_output):
            try:
                _restore_bound_destination(bound_output, backup_name=backup_name)
                backup_name = None
            except OSError as exc:
                preserve_backup = backup_name is not None
                raise ReviewPackageError(
                    "output parent changed during atomic replace and prior output "
                    f"rollback failed; retained backup {backup_name or 'was absent'}"
                ) from exc
            raise ReviewPackageError("output parent changed during atomic replace")
        if backup_name is not None:
            os.unlink(backup_name, dir_fd=bound_output.parent_fd)
            backup_name = None
        os.fsync(bound_output.parent_fd)
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        with suppress(FileNotFoundError):
            os.unlink(temporary_name, dir_fd=bound_output.parent_fd)
        if backup_name is not None and not preserve_backup:
            with suppress(FileNotFoundError):
                os.unlink(backup_name, dir_fd=bound_output.parent_fd)


def _normalize_git_text(payload: bytes) -> bytes:
    """Normalize generated Git text to LF without decoding repository paths."""

    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


@contextmanager
def _hermetic_git_context(repository: _Repository) -> Iterator[Path]:
    """Yield a config- and graph-overlay-free bare view of source objects."""

    encoded_object_dir = os.fsencode(repository.object_dir)
    if b"\x00" in encoded_object_dir or b"\n" in encoded_object_dir or b"\r" in encoded_object_dir:
        raise ReviewPackageError("Git object directory cannot be represented hermetically")
    with tempfile.TemporaryDirectory(prefix="polisyos-review-package-") as raw_directory:
        scratch = Path(raw_directory)
        git_context = scratch / "review.git"
        _run_git(
            scratch,
            "init",
            "--bare",
            "--template=",
            f"--object-format={repository.object_format}",
            str(git_context),
        )
        alternates = git_context / "objects" / "info" / "alternates"
        alternates.write_bytes(encoded_object_dir + b"\n")
        yield git_context


def _render_section(name: str, payload: bytes, *, digest: str | None = None) -> bytes:
    """Render one length-delimited deterministic package section."""

    header = f"section={name}\nlength={len(payload)}\n".encode("ascii")
    if digest is not None:
        header += f"sha256={digest}\n".encode("ascii")
    header += b"\n"
    return header + payload + b"\nend_section\n"


def _render_package(
    worktree: Path,
    *,
    base_commit: str,
    head_commit: str,
    prior_findings: bytes | None,
) -> bytes:
    """Render the stable shared sections for a full or delta package."""

    commit_list = _normalize_git_text(
        _run_git(
            worktree,
            "rev-list",
            "--reverse",
            "--topo-order",
            f"{base_commit}..{head_commit}",
        )
    )
    diff_stat = _normalize_git_text(
        _run_git(
            worktree,
            "diff",
            "--stat=120,100,9999",
            "--stat-graph-width=20",
            *_COMMON_DIFF_ARGUMENTS,
            base_commit,
            head_commit,
            "--",
            attribute_source=head_commit,
        )
    )
    name_status = _normalize_git_text(
        _run_git(
            worktree,
            "diff",
            "--name-status",
            *_COMMON_DIFF_ARGUMENTS,
            base_commit,
            head_commit,
            "--",
            attribute_source=head_commit,
        )
    )
    patch = _normalize_git_text(
        _run_git(
            worktree,
            "diff",
            *_COMMON_DIFF_ARGUMENTS,
            *_PATCH_DIFF_ARGUMENTS,
            base_commit,
            head_commit,
            "--",
            attribute_source=head_commit,
        )
    )
    package_kind = "delta" if prior_findings is not None else "full"
    metadata = (
        PACKAGE_MAGIC
        + f"schema_version={SCHEMA_VERSION}\n".encode("ascii")
        + f"package_kind={package_kind}\n".encode("ascii")
        + f"base_commit={base_commit}\n".encode("ascii")
        + f"head_commit={head_commit}\n\n".encode("ascii")
    )
    sections = [
        metadata,
        _render_section("commit_list", commit_list),
        _render_section("diff_stat", diff_stat),
        _render_section("name_status", name_status),
        _render_section("patch", patch),
    ]
    if prior_findings is not None:
        sections.append(
            _render_section(
                "prior_findings",
                prior_findings,
                digest=hashlib.sha256(prior_findings).hexdigest(),
            )
        )
    sections.append(b"end_package\n")
    return b"".join(sections)


def build_review_package(
    *,
    base_revision: str,
    head_revision: str,
    output_path: str | Path,
    prior_findings_path: str | Path | None = None,
    invocation_cwd: Path | None = None,
) -> bytes:
    """Build and atomically persist one full or delta commit-range review package.

    Args:
        base_revision: Revision naming the already-reviewed lower bound.
        head_revision: Revision naming the upper review bound.
        output_path: Destination inside the current Git worktree.
        prior_findings_path: Exact prior-review checklist for delta mode.
        invocation_cwd: Directory from which Git worktree discovery starts.

    Returns:
        The exact package bytes written to ``output_path``.

    Raises:
        ReviewPackageError: If revisions, ancestry, or the destination fail validation.
    """

    origin = (invocation_cwd or Path.cwd()).resolve(strict=True)
    repository = _discover_repository(origin)
    destination = _resolve_inside_worktree(
        output_path,
        invocation_cwd=origin,
        repository=repository,
        label="output",
    )
    prior_findings: bytes | None = None
    if prior_findings_path is not None:
        checklist = _resolve_inside_worktree(
            prior_findings_path,
            invocation_cwd=origin,
            repository=repository,
            label="prior findings",
            must_exist=True,
        )
        if _paths_alias(checklist, destination):
            raise ReviewPackageError("output path must differ from prior findings path")
        prior_findings = checklist.read_bytes()
        if not prior_findings or not prior_findings.strip():
            raise ReviewPackageError("prior findings file must not be empty")
    _require_neutral_info_attributes(repository)
    _require_bound_repository_configuration(repository)
    base_commit = _resolve_commit(repository, base_revision, label="base")
    head_commit = _resolve_commit(repository, head_revision, label="head")
    with _hermetic_git_context(repository) as git_context:
        _require_ancestor(git_context, base_commit, head_commit)
        with _bind_output_parent(destination, worktree=repository.worktree) as bound_output:
            package = _render_package(
                git_context,
                base_commit=base_commit,
                head_commit=head_commit,
                prior_findings=prior_findings,
            )
            _require_neutral_info_attributes(repository)
            _require_bound_repository_configuration(repository)
            _atomic_write_bound_output(bound_output, package)
    return package


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the standalone review-package command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Lower commit-range revision.")
    parser.add_argument("--head", required=True, help="Upper commit-range revision.")
    parser.add_argument("--output", required=True, help="Output path inside the Git worktree.")
    parser.add_argument(
        "--prior-findings",
        help="Prior-review findings checklist; when present, build a delta package.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Build a review package and return a shell-compatible exit code."""

    args = _parse_args(argv)
    try:
        package = build_review_package(
            base_revision=args.base,
            head_revision=args.head,
            output_path=args.output,
            prior_findings_path=args.prior_findings,
        )
    except (OSError, ReviewPackageError) as exc:
        print(f"review-package error: {exc}", file=sys.stderr)
        return 2
    print(f"review package written ({len(package)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
