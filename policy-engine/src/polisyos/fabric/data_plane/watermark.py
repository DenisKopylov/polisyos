"""Watermark extraction policies for cursor advancement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from polisyos.core.contracts.cursor import WatermarkType
from polisyos.ir.connectors import VersionStrategy


class WatermarkPolicy(ABC):
    """Extracts watermark value from a FetchResult for cursor advancement."""

    @property
    @abstractmethod
    def watermark_type(self) -> WatermarkType:
        ...

    @abstractmethod
    def extract(self, result: Any) -> str | None:
        """Extract watermark value from fetch result. None if not available."""
        ...


class TimestampWatermark(WatermarkPolicy):
    """Uses source_updated_at or fetched_at as watermark."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.TIMESTAMP

    def extract(self, result: Any) -> str | None:
        ts = getattr(result, "source_updated_at", None) or getattr(result, "fetched_at", None)
        if ts is not None:
            return ts.isoformat()
        return None


class ETagWatermark(WatermarkPolicy):
    """Uses ETag from version info."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.ETAG

    def extract(self, result: Any) -> str | None:
        version = getattr(result, "version", None)
        if version is not None and getattr(version, "strategy", None) == VersionStrategy.ETAG:
            return version.value
        return None


class RevisionWatermark(WatermarkPolicy):
    """Uses revision number from version info."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.REVISION

    def extract(self, result: Any) -> str | None:
        version = getattr(result, "version", None)
        if version is not None and getattr(version, "strategy", None) == VersionStrategy.REVISION:
            return version.value
        return None


class OffsetWatermark(WatermarkPolicy):
    """Uses row count as offset watermark (for pagination-based incremental)."""

    @property
    def watermark_type(self) -> WatermarkType:
        return WatermarkType.OFFSET

    def extract(self, result: Any) -> str | None:
        row_count = getattr(result, "row_count", None)
        if row_count is not None:
            return str(row_count)
        return None


# Default mapping: connector_family → watermark policy
DEFAULT_WATERMARK_POLICIES: dict[str, WatermarkPolicy] = {
    "sdmx": TimestampWatermark(),
    "worldbank": TimestampWatermark(),
    "eurostat": TimestampWatermark(),
    "ukons": TimestampWatermark(),
    "ckan": TimestampWatermark(),
    "socrata": TimestampWatermark(),
    "opendatasoft": TimestampWatermark(),
    "sparql": ETagWatermark(),
}


def resolve_watermark_policy(connector_family: str) -> WatermarkPolicy:
    """Resolve the default watermark policy for a connector family."""
    return DEFAULT_WATERMARK_POLICIES.get(connector_family, TimestampWatermark())


__all__ = [
    "DEFAULT_WATERMARK_POLICIES",
    "ETagWatermark",
    "OffsetWatermark",
    "RevisionWatermark",
    "TimestampWatermark",
    "WatermarkPolicy",
    "resolve_watermark_policy",
]
