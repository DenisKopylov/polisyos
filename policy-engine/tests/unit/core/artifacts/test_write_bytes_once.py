from __future__ import annotations

from pathlib import Path

import polisyos.core.artifacts as artifacts
from polisyos.core.artifacts import write_bytes_once


def test_write_bytes_once_is_public_and_does_not_replace_existing_bytes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "immutable.bin"

    assert "write_bytes_once" in artifacts.__all__
    assert write_bytes_once(target, b"first") is True
    assert target.read_bytes() == b"first"
    assert write_bytes_once(target, b"first") is False
    assert write_bytes_once(target, b"different") is False
    assert target.read_bytes() == b"first"


def test_write_bytes_once_can_request_durable_parent(tmp_path: Path) -> None:
    target = tmp_path / "durable.bin"

    assert write_bytes_once(target, b"payload", durable_parent=True) is True
    assert target.read_bytes() == b"payload"
