"""Tests for connector resilience patterns."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.fabric.connectors.resilience import (
    AdaptiveRateLimiter,
    CacheFallback,
    CircuitBreaker,
    CircuitBreakerConfig,
    RateLimiterConfig,
    RetryExhaustedError,
    RetryPolicy,
)
from polisyos.ir.connectors import DataVersion, VersionStrategy


@pytest.mark.asyncio
async def test_retry_exhausted_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = RetryPolicy(max_attempts=2, base_delay=0.01, jitter_max=0.0)
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def always_fail() -> str:
        raise ConnectionError("fail")

    with pytest.raises(RetryExhaustedError):
        await policy.execute(always_fail)

    assert len(sleep_calls) == 1


@pytest.mark.asyncio
async def test_retry_non_retryable_error() -> None:
    policy = RetryPolicy(max_attempts=3)

    async def always_fail() -> str:
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        await policy.execute(always_fail)


@pytest.mark.asyncio
async def test_retry_respects_request_retryable_false() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay=0.01)
    request = FetchRequest(dataset_id="test.dataset", retryable=False)
    handle = SimpleNamespace(connector_id="test", config=SimpleNamespace())
    call_count = 0

    async def always_fail(_handle, _request) -> str:
        nonlocal call_count
        call_count += 1
        raise ConnectionError("fail")

    with pytest.raises(ConnectionError):
        await policy.execute(always_fail, handle, request)

    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_cancelled_not_retried() -> None:
    policy = RetryPolicy(max_attempts=3)

    async def cancelled() -> str:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await policy.execute(cancelled)


@pytest.mark.asyncio
async def test_adaptive_rate_limiter_retry_after_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    import polisyos.fabric.connectors.resilience.rate_limiter as rl

    class FakeClock:
        def __init__(self) -> None:
            self.now = 0.0

        def monotonic(self) -> float:
            return self.now

        async def sleep(self, delay: float) -> None:
            self.now += delay
            sleep_calls.append(delay)

    sleep_calls: list[float] = []
    clock = FakeClock()

    monkeypatch.setattr(rl, "_monotonic", clock.monotonic)
    monkeypatch.setattr(asyncio, "sleep", clock.sleep)

    limiter = AdaptiveRateLimiter(
        initial_rate_rps=1000.0,
        config=RateLimiterConfig(rate_limit_rps=1000.0),
    )

    limiter.record_rate_limit(retry_after_seconds=5.0)
    await limiter.acquire()

    assert sleep_calls
    assert sleep_calls[0] >= 5.0
    assert clock.now >= 5.0


def test_adaptive_rate_limiter_adjusts_without_deadlock() -> None:
    limiter = AdaptiveRateLimiter(
        initial_rate_rps=10.0,
        config=RateLimiterConfig(rate_limit_rps=10.0, min_rate_rps=1.0, max_rate_rps=20.0),
    )

    limiter.record_rate_limit()
    assert limiter.rate_limit_rps == 5.0

    for _ in range(100):
        limiter.record_success()

    assert limiter.rate_limit_rps > 5.0


@pytest.mark.asyncio
async def test_circuit_breaker_does_not_count_cancellations() -> None:
    breaker = CircuitBreaker(
        circuit_id="test",
        config=CircuitBreakerConfig(failure_threshold=1, min_throughput=1),
    )

    async def cancelled() -> str:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await breaker.execute(cancelled)

    assert breaker.is_closed()


@pytest.mark.asyncio
async def test_cache_fallback_uses_request_and_sets_resilience() -> None:
    version = DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value="v1",
        timestamp=datetime.now(timezone.utc),
    )
    fetch_result = FetchResult(
        data=[{"ok": True}],
        row_count=1,
        schema_id="test.schema",
        schema_version="1.0.0",
        version=version,
        fetched_at=datetime.now(timezone.utc),
        completeness=1.0,
    )

    class DummyCache:
        def __init__(self) -> None:
            self.seen = None

        def get_any(self, request, *, connector_id=None, max_staleness_seconds=None):
            self.seen = (request, connector_id, max_staleness_seconds)
            return SimpleNamespace(
                result=fetch_result,
                metadata=SimpleNamespace(cached_at=datetime.now(timezone.utc)),
            )

    cache = DummyCache()
    fallback = CacheFallback(cache_store=cache, max_staleness_seconds=60.0)
    request = FetchRequest(dataset_id="test.dataset")
    handle = SimpleNamespace(connector_id="test", config=SimpleNamespace())

    async def primary(_handle, _request):
        raise ConnectionError("boom")

    result = await fallback.handle_failure(
        ConnectionError("boom"),
        primary,
        object(),
        handle,
        request,
    )

    assert result is not None
    assert result.resilience is not None
    assert result.resilience.fallback_used is True
    assert result.resilience.fallback_strategy == "CacheFallback"
    assert cache.seen is not None
    assert cache.seen[0] == request
    assert cache.seen[1] == "test"
