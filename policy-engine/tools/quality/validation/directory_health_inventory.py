"""Bounded-retention path sources shared by directory-health reports."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Iterator, Set
from contextlib import suppress
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
    try:
        root_entries = os.scandir(root)
    except (FileNotFoundError, NotADirectoryError):
        return

    stack: list[Iterator[Any]] = [root_entries]
    try:
        if not files:
            yield root
        while stack:
            entries = stack[-1]
            try:
                entry = next(entries)
            except StopIteration:
                entries.close()
                stack.pop()
                continue
            try:
                is_directory = entry.is_dir(follow_symlinks=True)
            except FileNotFoundError:
                continue
            if is_directory:
                try:
                    is_symlink = entry.is_symlink()
                except FileNotFoundError:
                    continue
                if entry.name in skip_dir_names or is_symlink:
                    continue
                try:
                    child_entries = os.scandir(entry.path)
                except (FileNotFoundError, NotADirectoryError):
                    continue
                stack.append(child_entries)
                if not files:
                    yield Path(entry.path)
            elif files:
                yield Path(entry.path)
    finally:
        for entries in reversed(stack):
            entries.close()
