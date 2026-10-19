"""Typed-boundary behavior for the optional fsspec remote reader."""

from __future__ import annotations

from types import TracebackType
from typing import NoReturn, cast

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.sources import _file_common
from polisyos.fabric.connectors.sources.object_storage import ObjectStorageConnector


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


@pytest.mark.asyncio
async def test_remote_fsspec_reader_uses_default_when_max_bytes_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(b"1234", {})
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)

    payload, _headers = await _file_common.read_location_bytes(
        ConnectionConfig(url="s3://bucket/object.csv", headers={})
    )

    assert payload == b"1234"
    assert adapter.requested_sizes == [_file_common._DEFAULT_MAX_LOCATION_BYTES + 1]


@pytest.mark.parametrize(
    ("headers", "expected_max_bytes"),
    [
        ({"X-File-MaxBytes": "8", "X-GeoJSON-MaxBytes": "4"}, 8),
        ({"X-GeoJSON-MaxBytes": "4"}, 4),
    ],
)
@pytest.mark.asyncio
async def test_remote_fsspec_reader_preserves_max_bytes_prefix_order(
    headers: dict[str, str],
    expected_max_bytes: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(b"1234", {})
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)

    payload, _response_headers = await _file_common.read_location_bytes(
        ConnectionConfig(url="s3://bucket/object.csv", headers=headers),
        prefixes=("X-File-", "X-GeoJSON-"),
    )

    assert payload == b"1234"
    assert adapter.requested_sizes == [expected_max_bytes + 1]


@pytest.mark.parametrize(
    ("raw", "expected_max_bytes"),
    [("+4", 4), (" 4 ", 4), ("4_0", 40), ("４", 4)],
)
@pytest.mark.asyncio
async def test_remote_fsspec_reader_preserves_integer_string_grammar(
    raw: str,
    expected_max_bytes: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(b"1234", {})
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)

    payload, _headers = await _file_common.read_location_bytes(
        ConnectionConfig(
            url="s3://bucket/object.csv",
            headers={"X-File-MaxBytes": raw},
        )
    )

    assert payload == b"1234"
    assert adapter.requested_sizes == [expected_max_bytes + 1]


@pytest.mark.parametrize(
    "raw",
    [None, 8, 8.5, True, "", " ", "0", "-1", "1.5", "garbage", "+", "1e3"],
)
@pytest.mark.asyncio
async def test_remote_fsspec_reader_rejects_present_invalid_max_bytes_before_open(
    raw: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(b"1234", {})
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)
    headers = cast("dict[str, str]", {"X-File-MaxBytes": raw})

    with pytest.raises(ValueError, match="X-File-MaxBytes must be a positive integer"):
        await _file_common.read_location_bytes(
            ConnectionConfig(url="s3://bucket/object.csv", headers=headers)
        )

    assert adapter.resolved_urls == []
    assert adapter.open_calls == []
    assert adapter.requested_sizes == []


@pytest.mark.parametrize(
    ("headers", "expected_header"),
    [
        ({"X-File-MaxBytes": "invalid", "X-GeoJSON-MaxBytes": "4"}, "X-File-MaxBytes"),
        ({"X-GeoJSON-MaxBytes": ""}, "X-GeoJSON-MaxBytes"),
        ({"X-GeoJSON-MaxBytes": None}, "X-GeoJSON-MaxBytes"),
    ],
)
@pytest.mark.asyncio
async def test_remote_fsspec_reader_rejects_invalid_present_prefix_without_fallback(
    headers: dict[str, object],
    expected_header: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(b"1234", {})
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)
    typed_headers = cast("dict[str, str]", headers)

    with pytest.raises(ValueError, match=f"{expected_header} must be a positive integer"):
        await _file_common.read_location_bytes(
            ConnectionConfig(url="s3://bucket/object.csv", headers=typed_headers),
            prefixes=("X-File-", "X-GeoJSON-"),
        )

    assert adapter.resolved_urls == []
    assert adapter.open_calls == []
    assert adapter.requested_sizes == []


@pytest.mark.parametrize(
    ("raw", "expected_healthy", "expected_read_size"),
    [(" 4 ", True, 5), ("", False, None)],
)
@pytest.mark.asyncio
async def test_object_storage_health_check_uses_object_max_bytes_prefix(
    raw: str,
    expected_healthy: bool,
    expected_read_size: int | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _FakeFsspec(b"1234", {})
    monkeypatch.setattr(_file_common, "_load_fsspec", lambda: adapter)
    connector = ObjectStorageConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url="s3://bucket/object.csv",
            headers={"X-Object-MaxBytes": raw},
        )
    )

    status = await connector.health_check(handle)
    await connector.disconnect(handle)

    assert status.healthy is expected_healthy
    if expected_read_size is None:
        assert adapter.resolved_urls == []
        assert adapter.open_calls == []
        assert adapter.requested_sizes == []
    else:
        assert adapter.requested_sizes == [expected_read_size]
        assert adapter.open_calls == [("s3://bucket/object.csv", "rb")]
