"""Scientist adapter for the CAS-backed Scholar URL/content cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.scholar.search.cache import CachedPageRecord, UrlFetchCache


@dataclass(frozen=True, slots=True)
class EvidenceCachePolicy:
    """Cache freshness policy for public-web evidence acquisition."""

    ttl_seconds: int = 86_400
    namespace: str = "scientist_deep_research"


def build_url_fetch_cache(
    *,
    cas: Any | None = None,
    cache_index_root: Path | None = None,
    policy: EvidenceCachePolicy | None = None,
) -> UrlFetchCache:
    """Create a Scholar UrlFetchCache with Scientist defaults."""

    active_policy = policy or EvidenceCachePolicy()
    index_path: Path | None = None
    if cache_index_root is not None:
        index_path = cache_index_root / active_policy.namespace / "url_fetch_index.json"
    elif cas is not None:
        root = getattr(cas, "root", None)
        if isinstance(root, Path):
            index_path = root / active_policy.namespace / "url_fetch_index.json"
        elif isinstance(root, str):
            index_path = Path(root) / active_policy.namespace / "url_fetch_index.json"
    return UrlFetchCache(
        index_path=index_path,
        cas=cas,
        ttl_seconds=active_policy.ttl_seconds,
    )


def cached_record_freshness_status(
    record: CachedPageRecord,
    *,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    """Return a small status string for cache freshness dashboards/gates."""

    if ttl_seconds <= 0:
        return "disabled"
    clock = now or datetime.now(UTC)
    age = (clock - record.fetched_at).total_seconds()
    if age <= ttl_seconds:
        return "fresh"
    return "stale"


__all__ = [
    "EvidenceCachePolicy",
    "build_url_fetch_cache",
    "cached_record_freshness_status",
]
