"""Lightweight byte dependency receipts for isolated governed projections."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
from contextlib import suppress
from pathlib import Path

_IGNORED_DEPENDENCY_PARTS = frozenset(
    {".git", ".tmp", ".venv", "__pycache__", "_cache", "node_modules"}
)


def _hash_mapping(value: dict[str, str]) -> str:
    raw = json.dumps(
        dict(sorted(value.items())),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


class DependencyTracker:
    """Record byte and directory identities consulted by one owner validation."""

    def __init__(self, root: Path) -> None:
        self._root = Path(os.path.abspath(root))
        self._initial: dict[str, str] = {}
        self._original_builtin_open = builtins.open
        self._original_io_open = io.open
        self._original_os_open = os.open
        self._original_stat = os.stat
        self._original_lstat = os.lstat
        self._original_listdir = os.listdir
        self._original_scandir = os.scandir

    def _relative(self, value: object) -> tuple[str, Path] | None:
        if isinstance(value, int):
            return None
        try:
            raw = os.fsdecode(value)  # type: ignore[arg-type]
        except TypeError:
            return None
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self._root / candidate
        absolute = Path(os.path.abspath(candidate))
        try:
            relative = absolute.relative_to(self._root)
        except ValueError:
            return None
        if not relative.parts or any(
            part in _IGNORED_DEPENDENCY_PARTS for part in relative.parts
        ):
            return None
        return relative.as_posix(), absolute

    def record(self, value: object) -> None:
        """Capture the first identity observed for a repository-relative path."""

        resolved = self._relative(value)
        if resolved is None:
            return
        relative, absolute = resolved
        if relative not in self._initial:
            self._initial[relative] = self.identity(absolute)

    def identity(self, path: Path) -> str:
        """Return a content identity for one file, directory listing, or absence."""

        try:
            metadata = self._original_stat(path)
        except OSError:
            return "missing"
        if stat.S_ISREG(metadata.st_mode):
            digest = hashlib.sha256()
            try:
                with self._original_builtin_open(path, "rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError:
                return "unreadable"
            return f"file:sha256:{digest.hexdigest()}"
        if stat.S_ISDIR(metadata.st_mode):
            entries: dict[str, str] = {}
            try:
                with self._original_scandir(path) as iterator:
                    for entry in iterator:
                        if entry.name in _IGNORED_DEPENDENCY_PARTS:
                            continue
                        try:
                            entry_mode = entry.stat(follow_symlinks=False).st_mode
                        except OSError:
                            entry_kind = "unreadable"
                        else:
                            entry_kind = (
                                "directory"
                                if stat.S_ISDIR(entry_mode)
                                else "symlink"
                                if stat.S_ISLNK(entry_mode)
                                else "file"
                                if stat.S_ISREG(entry_mode)
                                else "other"
                            )
                        entries[entry.name] = entry_kind
            except OSError:
                return "directory:unreadable"
            return f"directory:{_hash_mapping(entries)}"
        return f"special:{metadata.st_mode}:{metadata.st_size}"

    def record_loaded_modules(self) -> None:
        """Bind every repository module loaded by the isolated validation worker."""

        for module in tuple(sys.modules.values()):
            raw_path = getattr(module, "__file__", None)
            if not isinstance(raw_path, str) or not raw_path:
                continue
            module_path = Path(raw_path)
            if module_path.suffix in {".pyc", ".pyo"}:
                with suppress(ValueError):
                    module_path = Path(importlib.util.source_from_cache(str(module_path)))
            self.record(module_path)

    def __enter__(self) -> DependencyTracker:
        def tracked_builtin_open(
            file: object,
            *args: object,
            **kwargs: object,
        ) -> object:
            self.record(file)
            return self._original_builtin_open(file, *args, **kwargs)

        def tracked_io_open(file: object, *args: object, **kwargs: object) -> object:
            self.record(file)
            return self._original_io_open(file, *args, **kwargs)

        def tracked_os_open(path: object, *args: object, **kwargs: object) -> int:
            self.record(path)
            return self._original_os_open(path, *args, **kwargs)

        def tracked_stat(
            path: object,
            *args: object,
            **kwargs: object,
        ) -> os.stat_result:
            self.record(path)
            return self._original_stat(path, *args, **kwargs)

        def tracked_lstat(
            path: object,
            *args: object,
            **kwargs: object,
        ) -> os.stat_result:
            self.record(path)
            return self._original_lstat(path, *args, **kwargs)

        def tracked_listdir(path: object = ".") -> object:
            self.record(path)
            return self._original_listdir(path)

        def tracked_scandir(path: object = ".") -> object:
            self.record(path)
            return self._original_scandir(path)

        builtins.open = tracked_builtin_open  # type: ignore[assignment]
        io.open = tracked_io_open  # type: ignore[assignment]
        os.open = tracked_os_open  # type: ignore[assignment]
        os.stat = tracked_stat  # type: ignore[assignment]
        os.lstat = tracked_lstat  # type: ignore[assignment]
        os.listdir = tracked_listdir  # type: ignore[assignment]
        os.scandir = tracked_scandir  # type: ignore[assignment]
        return self

    def __exit__(self, *_args: object) -> None:
        builtins.open = self._original_builtin_open
        io.open = self._original_io_open
        os.open = self._original_os_open
        os.stat = self._original_stat
        os.lstat = self._original_lstat
        os.listdir = self._original_listdir
        os.scandir = self._original_scandir

    def receipt(self) -> tuple[dict[str, str], tuple[str, ...]]:
        """Return current bindings and detect a dependency that changed mid-run."""

        current = {
            relative: self.identity(self._root / relative)
            for relative in sorted(self._initial)
        }
        issues = () if current == self._initial else ("dependency_changed_during_validation",)
        return current, issues


def dependency_manifest_matches(root: Path, bindings: dict[str, str]) -> bool:
    """Re-hash a cached receipt without importing any artifact owner."""

    tracker = DependencyTracker(root)
    for relative, expected in bindings.items():
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            return False
        if tracker.identity(root / candidate) != expected:
            return False
    return True


__all__ = ["DependencyTracker", "dependency_manifest_matches"]
