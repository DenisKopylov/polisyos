from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.scholar.freshness_store import FreshnessStateStore


def test_state_store_roundtrip(tmp_path) -> None:
    store = FreshnessStateStore(tmp_path / "cas")
    key = FreshnessStateStore.make_key("intent", "bundle")
    now = datetime(2026, 2, 1, tzinfo=UTC)

    store.record_check(key, now=now)
    first = store.load(key)
    assert first.last_checked_at == now

    store.record_refresh_attempt(key, now=now + timedelta(minutes=1))
    second = store.load(key)
    assert second.last_refresh_attempt_at == now + timedelta(minutes=1)

    store.record_refresh_failure(
        key,
        cooldown_seconds=1800,
        now=now + timedelta(minutes=2),
    )
    failed = store.load(key)
    assert failed.next_retry_at == now + timedelta(minutes=32)
    assert failed.failed_refresh_count == 1

    store.record_refresh_success(key, now=now + timedelta(minutes=40))
    final = store.load(key)
    assert final.next_retry_at is None
    assert final.failed_refresh_count == 0


def test_refresh_lock_is_exclusive(tmp_path) -> None:
    store = FreshnessStateStore(tmp_path / "cas")
    key = FreshnessStateStore.make_key("intent", "bundle")
    first = store.acquire_lock(key, ttl_seconds=60)
    assert first is not None
    try:
        second = store.acquire_lock(key, ttl_seconds=60)
        assert second is None
    finally:
        first.release()

    third = store.acquire_lock(key, ttl_seconds=60)
    assert third is not None
    third.release()
