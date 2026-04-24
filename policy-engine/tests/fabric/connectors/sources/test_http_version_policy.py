from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("aiohttp")

from polisyos.fabric.connectors.sources.http_common import (
    FRESHNESS_SOURCE_TIMESTAMP_MISSING,
    build_data_version,
    quality_flags_from_source_metadata,
    retry_after_seconds,
)
from polisyos.ir.connectors import VersionStrategy


def test_build_data_version_prefers_etag() -> None:
    now = datetime.now(UTC)
    version, source_updated_at = build_data_version(
        etag='"etag-123"',
        last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
        content_hash="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        fetched_at=now,
    )
    assert version.strategy == VersionStrategy.ETAG
    assert version.value == '"etag-123"'
    assert source_updated_at is not None


def test_build_data_version_uses_last_modified_when_no_etag() -> None:
    now = datetime.now(UTC)
    version, source_updated_at = build_data_version(
        etag=None,
        last_modified="Tue, 02 Jan 2024 00:00:00 GMT",
        content_hash="sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        fetched_at=now,
    )
    assert version.strategy == VersionStrategy.TIMESTAMP
    assert source_updated_at is not None
    assert version.value == source_updated_at.isoformat()


def test_build_data_version_falls_back_to_content_hash() -> None:
    now = datetime.now(UTC)
    version, source_updated_at = build_data_version(
        etag=None,
        last_modified=None,
        content_hash="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        fetched_at=now,
    )
    assert version.strategy == VersionStrategy.CONTENT_HASH
    assert (
        version.value == "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    )
    assert source_updated_at is None


def test_retry_after_seconds_prefers_retry_after_header() -> None:
    value = retry_after_seconds({"Retry-After": "7", "X-RateLimit-Reset": "9999999999"})
    assert value == 7.0


def test_retry_after_seconds_falls_back_to_rate_limit_reset() -> None:
    reset_at = datetime.now(UTC) + timedelta(seconds=30)
    value = retry_after_seconds({"X-RateLimit-Reset": str(reset_at.timestamp())})
    assert value is not None
    assert 0.0 <= value <= 31.0


def test_quality_flags_adds_freshness_hint_when_source_timestamp_missing() -> None:
    flags = quality_flags_from_source_metadata(
        source_updated_at=None,
        base_flags=("custom:flag",),
    )
    assert "custom:flag" in flags
    assert FRESHNESS_SOURCE_TIMESTAMP_MISSING in flags
