"""Tests for watermark extraction policies."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from polisyos.core.contracts.cursor import WatermarkType
from polisyos.fabric.data_plane.watermark import (
    ETagWatermark,
    OffsetWatermark,
    RevisionWatermark,
    TimestampWatermark,
    resolve_watermark_policy,
)
from polisyos.ir.connectors import DataVersion, VersionStrategy


_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_result(**kwargs):
    """Create a lightweight result-like object with given attrs."""
    defaults = {
        "source_updated_at": None,
        "fetched_at": _NOW,
        "version": None,
        "row_count": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestTimestampWatermark:
    def test_extracts_from_source_updated_at(self):
        policy = TimestampWatermark()
        assert policy.watermark_type == WatermarkType.TIMESTAMP

        result = _make_result(source_updated_at=_NOW)
        value = policy.extract(result)
        assert value == _NOW.isoformat()

    def test_falls_back_to_fetched_at(self):
        policy = TimestampWatermark()
        result = _make_result(source_updated_at=None, fetched_at=_NOW)
        value = policy.extract(result)
        assert value == _NOW.isoformat()

    def test_returns_none_if_no_timestamp(self):
        policy = TimestampWatermark()
        result = _make_result(source_updated_at=None, fetched_at=None)
        value = policy.extract(result)
        assert value is None


class TestETagWatermark:
    def test_extracts_etag(self):
        policy = ETagWatermark()
        assert policy.watermark_type == WatermarkType.ETAG

        version = DataVersion(
            strategy=VersionStrategy.ETAG,
            value='"etag-v1"',
            timestamp=_NOW,
        )
        result = _make_result(version=version)
        value = policy.extract(result)
        assert value == '"etag-v1"'

    def test_returns_none_for_non_etag(self):
        policy = ETagWatermark()
        version = DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value="2024-01-01",
            timestamp=_NOW,
        )
        result = _make_result(version=version)
        value = policy.extract(result)
        assert value is None

    def test_returns_none_if_no_version(self):
        policy = ETagWatermark()
        result = _make_result(version=None)
        value = policy.extract(result)
        assert value is None


class TestRevisionWatermark:
    def test_extracts_revision(self):
        policy = RevisionWatermark()
        assert policy.watermark_type == WatermarkType.REVISION

        version = DataVersion(
            strategy=VersionStrategy.REVISION,
            value="42",
            timestamp=_NOW,
        )
        result = _make_result(version=version)
        value = policy.extract(result)
        assert value == "42"

    def test_returns_none_for_non_revision(self):
        policy = RevisionWatermark()
        version = DataVersion(
            strategy=VersionStrategy.ETAG,
            value='"etag"',
            timestamp=_NOW,
        )
        result = _make_result(version=version)
        value = policy.extract(result)
        assert value is None


class TestOffsetWatermark:
    def test_extracts_row_count(self):
        policy = OffsetWatermark()
        assert policy.watermark_type == WatermarkType.OFFSET

        result = _make_result(row_count=1500)
        value = policy.extract(result)
        assert value == "1500"


class TestResolvePolicy:
    def test_resolve_known_families(self):
        for family in ("sdmx", "worldbank", "eurostat", "ckan", "socrata", "opendatasoft"):
            policy = resolve_watermark_policy(family)
            assert policy.watermark_type == WatermarkType.TIMESTAMP

        sparql_policy = resolve_watermark_policy("sparql")
        assert sparql_policy.watermark_type == WatermarkType.ETAG

    def test_resolve_unknown_defaults_to_timestamp(self):
        policy = resolve_watermark_policy("nonexistent_family")
        assert policy.watermark_type == WatermarkType.TIMESTAMP
