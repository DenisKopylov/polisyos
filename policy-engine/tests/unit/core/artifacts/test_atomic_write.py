"""Behavioral checks for Core's prepared atomic replacement."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from polisyos.core.artifacts._atomic_write import _PreparedAtomicReplace

if TYPE_CHECKING:
    from pathlib import Path


def test_prepared_replacement_is_one_use_and_preserves_the_target(tmp_path: Path) -> None:
    target = tmp_path / "head.json"
    target.write_bytes(b"old")
    prepared = _PreparedAtomicReplace(target, b"new")
    try:
        assert target.read_bytes() == b"old"
        prepared.replace()
        assert target.read_bytes() == b"new"
        prepared.sync_parent()
        with pytest.raises(OSError, match="prepared_atomic_write_not_current"):
            prepared.replace()
    finally:
        prepared.close()
    assert target.read_bytes() == b"new"


def test_changed_prepared_bytes_cannot_replace_the_head(tmp_path: Path) -> None:
    target = tmp_path / "head.json"
    target.write_bytes(b"old")
    prepared = _PreparedAtomicReplace(target, b"new")
    try:
        original = prepared._tmp.stat()
        prepared._tmp.write_bytes(b"bad")
        os.utime(prepared._tmp, ns=(original.st_atime_ns, original.st_mtime_ns))
        with pytest.raises(OSError, match="prepared_atomic_write_changed"):
            prepared.replace()
        assert target.read_bytes() == b"old"
    finally:
        prepared.close()


def test_temporary_collision_does_not_remove_another_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts import _atomic_write

    target = tmp_path / "head.json"
    collision = target.with_suffix(target.suffix + f".tmp-{UUID(int=0).hex}")
    collision.write_bytes(b"another owner")
    monkeypatch.setattr(_atomic_write.uuid, "uuid4", lambda: UUID(int=0))
    with pytest.raises(FileExistsError):
        _PreparedAtomicReplace(target, b"new")
    assert collision.read_bytes() == b"another owner"


def test_replaced_temporary_name_is_not_removed_on_close(tmp_path: Path) -> None:
    target = tmp_path / "head.json"
    prepared = _PreparedAtomicReplace(target, b"new")
    prepared._tmp.replace(tmp_path / "moved-staged-file")
    prepared._tmp.write_bytes(b"another owner")
    prepared.close()
    assert prepared._tmp.read_bytes() == b"another owner"
