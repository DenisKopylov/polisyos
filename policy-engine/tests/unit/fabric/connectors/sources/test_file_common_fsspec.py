"""Typed-boundary behavior for the optional fsspec remote reader."""

from __future__ import annotations

from types import TracebackType
from typing import NoReturn

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.sources import _file_common


class _FakeBinaryReader:
    def __init__(self, payload: bytes, requested_sizes: list[int]) -> None:
        self.payload = payload
        self.requested_sizes = requested_sizes

    def read(self, size: int = -1) -> bytes:
        self.requested_sizes.append(size)
        return self.payload if size < 0 else self.payload[:size]


class _FakeOpenFile:
    def __init__(self, reader: _FakeBinaryReader) -> None:
        self.reader = reader

    def __enter__(self) -> _FakeBinaryReader:
        return self.reader

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> bool:
        return False


class _FakeFileSystem:
    def __init__(self, details: dict[str, object]) -> None:
        self.details = details
        self.info_paths: list[str] = []

    def info(self, path: str) -> dict[str, object]:
        self.info_paths.append(path)
        return self.details


class _FakeFsspec:
    def __init__(self, payload: bytes, details: dict[str, object]) -> None:
        self.filesystem = _FakeFileSystem(details)
        self.requested_sizes: list[int] = []
        self.reader = _FakeBinaryReader(payload, self.requested_sizes)
        self.open_calls: list[tuple[str, str]] = []
        self.resolved_urls: list[str] = []

    def get_fs_token_paths(self, url: str) -> tuple[_FakeFileSystem, str, list[str]]:
        self.resolved_urls.append(url)
        return self.filesystem, "test-token", ["bucket/object.csv"]

    def open(self, url: str, mode: str = "rb") -> _FakeOpenFile:
        self.open_calls.append((url, mode))
        return _FakeOpenFile(self.reader)


@pytest.mark.asyncio
async def test_remote_fsspec_reader_preserves_metadata_and_bounded_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(
        b"id\n1\n",
        {"size": 5, "etag": "etag-v1", "LastModified": "2026-10-19T00:00:00Z"},
    )
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)

    payload, headers = await _file_common.read_location_bytes(
        ConnectionConfig(
            url="s3://bucket/object.csv",
            headers={"X-File-MaxBytes": "8"},
        )
    )

    assert payload == b"id\n1\n"
    assert headers == {
        "ETag": "etag-v1",
        "Last-Modified": "2026-10-19T00:00:00Z",
    }
    assert adapter.resolved_urls == ["s3://bucket/object.csv"]
    assert adapter.filesystem.info_paths == ["bucket/object.csv"]
    assert adapter.open_calls == [("s3://bucket/object.csv", "rb")]
    assert adapter.requested_sizes == [9]


@pytest.mark.asyncio
async def test_remote_fsspec_reader_rejects_oversized_body_without_size_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(b"12345", {})
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)

    with pytest.raises(ValueError, match="safe byte limit"):
        await _file_common.read_location_bytes(
            ConnectionConfig(
                url="s3://bucket/object.csv",
                headers={"X-File-MaxBytes": "4"},
            )
        )

    assert adapter.requested_sizes == [5]


@pytest.mark.asyncio
async def test_remote_fsspec_reader_retains_optional_dependency_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_fsspec() -> NoReturn:
        raise ModuleNotFoundError("No module named 'fsspec'")

    monkeypatch.setattr(_file_common, "_load_fsspec", missing_fsspec)

    with pytest.raises(RuntimeError, match="optional dependency 'fsspec'"):
        await _file_common.read_location_bytes(
            ConnectionConfig(url="s3://bucket/object.csv", headers={})
        )
