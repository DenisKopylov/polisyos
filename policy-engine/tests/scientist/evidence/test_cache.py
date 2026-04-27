from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.scholar.search.cache import CachedPageRecord
from polisyos.scientist.evidence.cache import (
    EvidenceCachePolicy,
    build_url_fetch_cache,
    cached_record_freshness_status,
)


def test_build_url_fetch_cache_uses_scientist_namespace(tmp_path) -> None:
    cache = build_url_fetch_cache(
        cache_index_root=tmp_path,
        policy=EvidenceCachePolicy(ttl_seconds=60, namespace="phase1_3"),
    )

    assert cache.snapshot() == {}


def test_cached_record_freshness_status_respects_ttl() -> None:
    record = CachedPageRecord(
        url="https://example.org/report",
        final_url="https://example.org/report",
        fetched_at=datetime(2026, 4, 26, tzinfo=UTC) - timedelta(seconds=30),
    )

    assert (
        cached_record_freshness_status(
            record,
            ttl_seconds=60,
            now=datetime(2026, 4, 26, tzinfo=UTC),
        )
        == "fresh"
    )
    assert (
        cached_record_freshness_status(
            record,
            ttl_seconds=10,
            now=datetime(2026, 4, 26, tzinfo=UTC),
        )
        == "stale"
    )
