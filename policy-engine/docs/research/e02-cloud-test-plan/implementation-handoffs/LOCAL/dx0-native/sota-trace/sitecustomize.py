"""Capture repository file reads and pathlib input enumerations for one run."""

from __future__ import annotations

import atexit
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_root = Path(os.environ["E02_SOTA_TRACE_ROOT"]).resolve()
_log = Path(os.environ["E02_SOTA_TRACE_LOG"]).resolve()
_excluded = Path(os.environ["E02_SOTA_TRACE_EXCLUDED"]).resolve()
_reads: set[str] = set()
_probes: set[tuple[str, str]] = set()
_enumerations: dict[tuple[str, str], set[str]] = {}


def _relative(path: object) -> str | None:
    try:
        resolved = Path(path).resolve()
        if resolved.is_relative_to(_root) and not resolved.is_relative_to(_excluded):
            parts = resolved.relative_to(_root).parts
            if not any(
                part in {".venv", "__pycache__", "node_modules", "_build"} for part in parts
            ):
                return resolved.relative_to(_root).as_posix()
    except (OSError, TypeError, ValueError):
        return None
    return None


def _record_read(path: object) -> None:
    relative = _relative(path)
    if relative is not None:
        _reads.add(relative)


def _audit(event: str, args: tuple[object, ...]) -> None:
    if event != "open" or not args:
        return
    path = args[0]
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else None
    if isinstance(mode, str):
        if mode.startswith("r") and "+" not in mode:
            _record_read(path)
        return
    if isinstance(flags, int) and not flags & (os.O_WRONLY | os.O_RDWR):
        _record_read(path)


sys.addaudithook(_audit)

_path_type = type(Path("."))
_original_exists = _path_type.exists
_original_is_file = _path_type.is_file
_original_is_dir = _path_type.is_dir
_original_open = _path_type.open
_original_glob = _path_type.glob
_original_rglob = _path_type.rglob
_original_iterdir = _path_type.iterdir


def _probe(operation: str, path: object) -> None:
    relative = _relative(path)
    if relative is not None:
        _probes.add((operation, relative))


def _exists(self: Path, *args: object, **kwargs: object) -> bool:
    _probe("exists", self)
    return _original_exists(self, *args, **kwargs)


def _is_file(self: Path, *args: object, **kwargs: object) -> bool:
    _probe("is_file", self)
    return _original_is_file(self, *args, **kwargs)


def _is_dir(self: Path, *args: object, **kwargs: object) -> bool:
    _probe("is_dir", self)
    return _original_is_dir(self, *args, **kwargs)


def _open(self: Path, mode: str = "r", *args: object, **kwargs: object) -> object:
    if mode.startswith("r") and "+" not in mode:
        _record_read(self)
    return _original_open(self, mode, *args, **kwargs)


def _glob(self: Path, pattern: str, *args: object, **kwargs: object) -> Iterator[Path]:
    relative = _relative(self)
    key = (relative or str(self), pattern)
    matches = _enumerations.setdefault(key, set())
    for path in _original_glob(self, pattern, *args, **kwargs):
        item = _relative(path)
        if item is not None:
            matches.add(item)
        yield path


def _rglob(self: Path, pattern: str, *args: object, **kwargs: object) -> Iterator[Path]:
    relative = _relative(self)
    key = (relative or str(self), f"**/{pattern}")
    matches = _enumerations.setdefault(key, set())
    for path in _original_rglob(self, pattern, *args, **kwargs):
        item = _relative(path)
        if item is not None:
            matches.add(item)
        yield path


def _iterdir(self: Path, *args: object, **kwargs: object) -> Iterator[Path]:
    relative = _relative(self)
    key = (relative or str(self), "<iterdir>")
    matches = _enumerations.setdefault(key, set())
    for path in _original_iterdir(self, *args, **kwargs):
        item = _relative(path)
        if item is not None:
            matches.add(item)
        yield path


_path_type.exists = _exists
_path_type.is_file = _is_file
_path_type.is_dir = _is_dir
_path_type.open = _open
_path_type.glob = _glob
_path_type.rglob = _rglob
_path_type.iterdir = _iterdir


def _write_manifest() -> None:
    payload = {
        "schema": "policyos.e02.sota_contract_runtime_inputs.v1",
        "repository_root": str(_root),
        "read_files": sorted(_reads),
        "path_probes": [
            {"operation": operation, "path": path} for operation, path in sorted(_probes)
        ],
        "path_enumerations": [
            {
                "root": root,
                "pattern": pattern,
                "matches": sorted(matches),
            }
            for (root, pattern), matches in sorted(_enumerations.items())
        ],
    }
    _log.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


atexit.register(_write_manifest)
