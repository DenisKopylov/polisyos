"""Filesystem helpers for hardened tooling flows."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def normalize_filesystem_path(
    value: str | Path,
    *,
    kind: str = "path",
    must_exist: bool = True,
    allow_directory: bool | None = None,
) -> Path:
    """Normalize and validate a filesystem path before use."""

    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{kind} must not be empty")
    if "\x00" in raw:
        raise ValueError(f"{kind} must not contain NUL bytes")

    path = Path(raw).expanduser().resolve(strict=must_exist)
    if must_exist and not path.exists():
        raise FileNotFoundError(f"{kind} not found: {path}")

    if allow_directory is True and path.exists() and not path.is_dir():
        raise ValueError(f"{kind} must be a directory: {path}")
    if allow_directory is False and path.exists() and path.is_dir():
        raise ValueError(f"{kind} must be a file: {path}")
    return path


def atomic_write_text(path: Path, data: str, *, encoding: str = "utf-8") -> None:
    """Write a text file atomically via a sibling temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write a binary file atomically via a sibling temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    trailing_newline: bool = True,
) -> None:
    """Serialize JSON atomically."""

    rendered = json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
    if trailing_newline:
        rendered += "\n"
    atomic_write_text(
        path,
        rendered,
        encoding=encoding,
    )


def write_text_exclusive(path: Path, data: str, *, encoding: str = "utf-8") -> None:
    """Create a text file only if it does not already exist."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o644)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def write_json_exclusive(
    path: Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    trailing_newline: bool = True,
) -> None:
    """Create a JSON file only if it does not already exist."""

    rendered = json.dumps(payload, indent=indent, ensure_ascii=False, default=str)
    if trailing_newline:
        rendered += "\n"
    write_text_exclusive(path, rendered, encoding=encoding)


@contextmanager
def exclusive_lock(path: Path, *, content: str = "") -> Iterator[Path]:
    """Acquire a lock file via O_CREAT|O_EXCL and remove it on exit."""

    write_text_exclusive(path, content, encoding="utf-8")
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def atomic_replace_path(
    staged_path: Path,
    final_path: Path,
    *,
    backup_suffix: str | None = None,
) -> Path | None:
    """Atomically replace a file or directory, preserving the previous target as a backup."""

    staged_path = normalize_filesystem_path(staged_path, kind="staged path", must_exist=True)
    final_path = normalize_filesystem_path(final_path, kind="final path", must_exist=False)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    backup_path: Path | None = None
    if final_path.exists():
        suffix = backup_suffix or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = final_path.with_name(f"{final_path.name}.bak.{suffix}")
        if backup_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing backup path: {backup_path}")
        final_path.replace(backup_path)

    try:
        staged_path.replace(final_path)
    except Exception:
        if backup_path is not None and backup_path.exists() and not final_path.exists():
            backup_path.replace(final_path)
        raise

    return backup_path
