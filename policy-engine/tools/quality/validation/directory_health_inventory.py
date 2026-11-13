"""Bounded-retention path sources shared by directory-health reports."""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Iterable, Iterator, Set
from contextlib import closing, suppress
from pathlib import Path
from typing import Any

_GIT_READ_BYTES = 64 * 1024


def iter_nul_records(chunks: Iterable[bytes]) -> Iterator[str]:
    """Decode NUL-delimited filesystem paths from bounded byte chunks."""
    pending = bytearray()
    for chunk in chunks:
        pending.extend(chunk)
        consumed = 0
        while True:
            end = pending.find(b"\0", consumed)
            if end < 0:
                break
            if end > consumed:
                yield os.fsdecode(bytes(pending[consumed:end]))
            consumed = end + 1
        if consumed:
            del pending[:consumed]
    if pending:
        yield os.fsdecode(bytes(pending))


def iter_git_paths(repo_root: Path, *args: str) -> Iterator[str]:
    """Stream one Git path inventory without retaining the command output.

    Git's NUL framing preserves valid names that contain whitespace or newlines. A
    nonzero exit is raised after the stream is exhausted so callers cannot report a
    complete inventory from a failed command.
    """
    command = ["git", *args, "-z"]
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    assert process.stdout is not None
    try:
        chunks = iter(lambda: process.stdout.read(_GIT_READ_BYTES), b"")
        yield from iter_nul_records(chunks)
        returncode = process.wait()
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
    finally:
        process.stdout.close()
        if process.poll() is None:
            with suppress(ProcessLookupError):
                process.terminate()
            process.wait()


def iter_files(root: Path, *, skip_dir_names: Set[str] = frozenset()) -> Iterator[Path]:
    """Stream files below ``root`` without collecting a whole walk's paths.

    Directory symlinks are not followed, matching ``os.walk``'s default. File
    symlinks and non-directory entries remain part of the inventory.
    """
    yield from _iter_scandir_paths(root, files=True, skip_dir_names=skip_dir_names)


def iter_directories(root: Path, *, skip_dir_names: Set[str] = frozenset()) -> Iterator[Path]:
    """Stream visited directories below ``root`` without collecting a walk."""
    yield from _iter_scandir_paths(root, files=False, skip_dir_names=skip_dir_names)


def iter_child_directories(root: Path) -> Iterator[Path]:
    """Stream immediate child directories without building a directory listing."""
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=True):
                    yield Path(entry.path)
    except (FileNotFoundError, NotADirectoryError):
        return


def _iter_scandir_paths(root: Path, *, files: bool, skip_dir_names: Set[str]) -> Iterator[Path]:
    with closing(iter_tree_entries(root, skip_dir_names=skip_dir_names)) as entries:
        for path, is_directory in entries:
            if (files and not is_directory) or (not files and is_directory):
                yield path


def iter_tree_entries(
    root: Path,
    *,
    skip_dir_names: Set[str] = frozenset(),
    root_descriptor: int | None = None,
    opaque_symlinks: bool = False,
) -> Iterator[tuple[Path, bool]]:
    """Walk one admitted root through anchored, no-follow child descriptors.

    The ordinary view retains its prior file/directory symlink classification
    and declared skip names. A caller supplying an already admitted descriptor
    can request opaque symlink leaves, without even inspecting target metadata.
    That descriptor is duplicated; ownership remains with the caller. Directory
    descriptors and scandir iterators are retained only along the current depth.
    """
    flags = _directory_flags()
    try:
        descriptor = (
            os.dup(root_descriptor)
            if root_descriptor is not None
            else os.open(root, flags & ~os.O_NOFOLLOW)
        )
    except (FileNotFoundError, NotADirectoryError):
        return
    stack: list[tuple[int, Path, Iterator[Any]]] = []
    try:
        try:
            stack.append((descriptor, root, os.scandir(descriptor)))
        except BaseException:
            os.close(descriptor)
            raise
        yield root, True
        while stack:
            parent_descriptor, logical_parent, entries = stack[-1]
            try:
                entry = next(entries)
            except StopIteration:
                entries.close()
                os.close(parent_descriptor)
                stack.pop()
                continue
            path = logical_parent / entry.name
            try:
                before = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                if opaque_symlinks:
                    raise
                continue
            if stat.S_ISLNK(before.st_mode) and not opaque_symlinks:
                try:
                    if entry.is_dir(follow_symlinks=True):
                        continue
                except FileNotFoundError:
                    continue
            if not stat.S_ISDIR(before.st_mode):
                yield path, False
                continue
            if entry.name in skip_dir_names:
                continue
            try:
                child = os.open(entry.name, _directory_flags(), dir_fd=parent_descriptor)
            except (FileNotFoundError, NotADirectoryError):
                if opaque_symlinks:
                    raise
                continue
            try:
                opened = os.fstat(child)
                if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                    raise OSError(f"directory changed during inventory: {path}")
                child_entries = os.scandir(child)
            except BaseException:
                os.close(child)
                raise
            stack.append((child, path, child_entries))
            yield path, True
    finally:
        for open_descriptor, _, entries in reversed(stack):
            entries.close()
            os.close(open_descriptor)


def open_directory_beneath(root: Path, parts: tuple[str, ...]) -> int:
    """Open literal directory components without following an alias at any step.

    The caller owns the returned descriptor. This does not create directories or
    change permissions, and a missing/unreadable component remains an exception.
    """
    if any(
        not isinstance(part, str) or part in {"", ".", ".."} or "/" in part or "\0" in part
        for part in parts
    ):
        raise ValueError("directory components must be single literal names")
    descriptor = os.open(root, _directory_flags())
    try:
        for part in parts:
            child = os.open(part, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _directory_flags() -> int:
    directory = getattr(os, "O_DIRECTORY", None)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if directory is None or nofollow is None:
        raise OSError("directory inventory requires O_DIRECTORY and O_NOFOLLOW")
    return os.O_RDONLY | directory | nofollow | getattr(os, "O_CLOEXEC", 0)
