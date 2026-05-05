"""Tests for connector resilience patterns."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.fabric.connectors.resilience import (
    AdaptiveRateLimiter,
    CacheFallback,
    CircuitBreaker,
    CircuitBreakerConfig,
    FallbackChain,
    MockFallback,
    RateLimiterConfig,
    RetryExhaustedError,
    RetryPolicy,
)
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitAttemptLease,
    CircuitLeaseError,
    CircuitState,
)
from polisyos.fabric.observability import FABRIC_TRACE_NAMES
from polisyos.ir.connectors import DataVersion, VersionStrategy


class _CounterStub:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, str]]] = []

    def add(self, value: int | float, attrs: dict[str, str]) -> None:
        self.calls.append((value, dict(attrs)))


class _HistogramStub:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, str]]] = []

    def record(self, value: int | float, attrs: dict[str, str]) -> None:
        self.calls.append((value, dict(attrs)))


class _RetryMetricsStub:
    def __init__(self) -> None:
        self.connector_retry_attempts_total = _CounterStub()
        self.connector_retry_delay_seconds = _HistogramStub()


class _ResilienceMetricsStub:
    def __init__(self) -> None:
        self.connector_fallback_triggered_total = _CounterStub()
        self.connector_fallback_success_total = _CounterStub()
        self.connector_circuit_state = SimpleNamespace(set=lambda value, attrs: None)
        self.connector_circuit_trips_total = _CounterStub()
        self.connector_circuit_rejected_requests_total = _CounterStub()
        self.connector_rate_limit_wait_seconds = _HistogramStub()
        self.connector_rate_limit_acquire_duration_seconds = _HistogramStub()
        self.connector_rate_limit_throttled_total = _CounterStub()


class _SpanStub:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.exceptions: list[str] = []

    def __enter__(self) -> _SpanStub:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def set_status(self, status: object) -> None:
        self.attributes["status"] = status

    def record_exception(self, exc: BaseException) -> None:
        self.exceptions.append(type(exc).__name__)


class _TracerStub:
    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, object], _SpanStub]] = []

    def start_as_current_span(self, name: str, attributes=None):
        span = _SpanStub()
        self.spans.append((name, dict(attributes or {}), span))
        return span


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
async def test_retry_policy_uses_injected_metrics_and_tracer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _RetryMetricsStub()
    tracer = _TracerStub()
    policy = RetryPolicy(
        max_attempts=3,
        base_delay=0.01,
        jitter_max=0.0,
        metrics=metrics,
        tracer=tracer,
    )
    state = {"attempts": 0}

    async def fake_sleep(delay: float) -> None:
        del delay

    async def flaky() -> str:
        state["attempts"] += 1
        if state["attempts"] < 2:
            raise ConnectionError("retry me")
        return "ok"

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        "polisyos.core.resilience.retry.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.core.resilience.retry.get_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("global tracer should not be used")),
    )

    result = await policy.execute(flaky)

    assert result == "ok"
    assert metrics.connector_retry_attempts_total.calls == [(1, {"attempt": "1"})]
    assert metrics.connector_retry_delay_seconds.calls == [(0.01, {"attempt": "1"})]
    assert tracer.spans
    assert tracer.spans[0][0] == "retry.execute"
    assert tracer.spans[0][2].attributes["retry.success_attempt"] == 2


@pytest.mark.asyncio
async def test_fallback_chain_uses_injected_metrics_and_tracer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _ResilienceMetricsStub()
    tracer = _TracerStub()
    mock_result = FetchResult(
        data=[],
        row_count=0,
        schema_id="test.schema",
        schema_version="1.0.0",
        version=DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value="v0",
            timestamp=datetime.now(UTC),
        ),
        fetched_at=datetime.now(UTC),
        completeness=1.0,
    )
    chain = FallbackChain(
        [MockFallback(mock_data=mock_result)],
        metrics=metrics,
        tracer=tracer,
    )

    monkeypatch.setattr(
        "polisyos.fabric.connectors.resilience.fallback.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global fallback metrics should not be used")),
    )

    async def _fail() -> FetchResult[list[dict[str, object]]]:
        raise ConnectionError("boom")

    result = await chain.execute(_fail)

    assert result.resilience is not None
    assert metrics.connector_fallback_triggered_total.calls
    assert metrics.connector_fallback_success_total.calls
    assert tracer.spans


@pytest.mark.asyncio
async def test_rate_limiter_uses_injected_metrics_and_tracer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _ResilienceMetricsStub()
    tracer = _TracerStub()
    limiter = AdaptiveRateLimiter(
        initial_rate_rps=1000.0,
        config=RateLimiterConfig(rate_limit_rps=1000.0),
        metrics=metrics,
        tracer=tracer,
    )

    monkeypatch.setattr(
        "polisyos.fabric.connectors.resilience.rate_limiter.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global rate metrics should not be used")),
    )

    await limiter.acquire()
    limiter.record_rate_limit(retry_after_seconds=1.0)

    assert metrics.connector_rate_limit_acquire_duration_seconds.calls
    assert metrics.connector_rate_limit_throttled_total.calls
    assert tracer.spans


@pytest.mark.asyncio
async def test_circuit_breaker_uses_injected_metrics_and_tracer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _ResilienceMetricsStub()
    tracer = _TracerStub()
    breaker = CircuitBreaker(
        circuit_id="test",
        config=CircuitBreakerConfig(failure_threshold=1, min_throughput=1),
        metrics=metrics,
        tracer=tracer,
    )

    monkeypatch.setattr(
        "polisyos.fabric.connectors.resilience.circuit_breaker.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global circuit metrics should not be used")),
    )

    async def _fail() -> str:
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        await breaker.execute(_fail)

    assert metrics.connector_circuit_trips_total.calls
    assert tracer.spans


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


def test_circuit_breaker_half_open_contention_releases_slot() -> None:
    breaker = CircuitBreaker(
        circuit_id="half-open",
        config=CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            timeout_seconds=60.0,
            half_open_max_calls=1,
            min_throughput=1,
        ),
    )

    breaker.record_failure()
    assert breaker.is_open()

    with breaker._lock:  # type: ignore[attr-defined]
        breaker._opened_at_monotonic = 0.0  # type: ignore[attr-defined]

    import polisyos.fabric.connectors.resilience.circuit_breaker as cb_mod

    original_monotonic = cb_mod._monotonic
    cb_mod._monotonic = lambda: 120.0
    try:
        first_lease = breaker.acquire_attempt()
        blocked_lease = breaker.acquire_attempt()
        assert first_lease is not None
        assert blocked_lease is None

        breaker.record_success(first_lease)
        second_lease = breaker.acquire_attempt()
        assert second_lease is not None
    finally:
        cb_mod._monotonic = original_monotonic


def test_circuit_breaker_rejects_half_open_release_without_ownership() -> None:
    breaker = CircuitBreaker(
        circuit_id="lease-owner",
        config=CircuitBreakerConfig(
            failure_threshold=1,
            timeout_seconds=60.0,
            half_open_max_calls=1,
            min_throughput=1,
        ),
    )
    breaker.record_failure()
    with breaker._lock:  # type: ignore[attr-defined]
        breaker._opened_at_monotonic = 0.0  # type: ignore[attr-defined]

    import polisyos.fabric.connectors.resilience.circuit_breaker as cb_mod

    original_monotonic = cb_mod._monotonic
    cb_mod._monotonic = lambda: 120.0
    try:
        lease = breaker.acquire_attempt()
        assert lease is not None
        with pytest.raises(CircuitLeaseError):
            breaker.record_success(
                CircuitAttemptLease(
                    circuit_id="lease-owner",
                    state=CircuitState.HALF_OPEN,
                    token="not-owned",
                )
            )
        breaker.record_failure(lease)
    finally:
        cb_mod._monotonic = original_monotonic


def test_circuit_breaker_emits_transition_spans(in_memory_exporter) -> None:
    breaker = CircuitBreaker(
        circuit_id="trace-circuit",
        config=CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            timeout_seconds=60.0,
            half_open_max_calls=1,
            min_throughput=1,
        ),
    )

    breaker.record_failure()

    import polisyos.fabric.connectors.resilience.circuit_breaker as cb_mod

    original_monotonic = cb_mod._monotonic
    cb_mod._monotonic = lambda: 120.0
    try:
        with breaker._lock:  # type: ignore[attr-defined]
            breaker._opened_at_monotonic = 0.0  # type: ignore[attr-defined]
        lease = breaker.acquire_attempt()
        assert lease is not None
        breaker.record_success(lease)
    finally:
        cb_mod._monotonic = original_monotonic

    transitions = [
        (
            span.attributes.get("circuit.from_state"),
            span.attributes.get("circuit.to_state"),
        )
        for span in in_memory_exporter.get_finished_spans()
        if span.name == FABRIC_TRACE_NAMES["circuit_transition"]
    ]
    assert ("CLOSED", "OPEN") in transitions
    assert ("OPEN", "HALF_OPEN") in transitions
    assert ("HALF_OPEN", "CLOSED") in transitions


@pytest.mark.asyncio
async def test_rate_limiter_stress_never_goes_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    import polisyos.fabric.connectors.resilience.rate_limiter as rl

    class FakeClock:
        def __init__(self) -> None:
            self.now = 0.0

        def monotonic(self) -> float:
            return self.now

        async def sleep(self, delay: float) -> None:
            self.now += delay

    clock = FakeClock()
    monkeypatch.setattr(rl, "_monotonic", clock.monotonic)
    monkeypatch.setattr(asyncio, "sleep", clock.sleep)

    limiter = AdaptiveRateLimiter(
        initial_rate_rps=2.0,
        config=RateLimiterConfig(rate_limit_rps=2.0, burst_size=1.0),
    )

    await asyncio.gather(*(limiter.acquire() for _ in range(8)))

    stats = limiter.get_stats()
    assert stats["total_requests"] == 8
    assert stats["tokens_available"] >= 0.0
    assert stats["total_acquire_duration_seconds"] >= stats["total_wait_time_seconds"]


@pytest.mark.asyncio
async def test_fallback_chain_preserves_primary_and_fallback_errors() -> None:
    class BrokenFallback:
        async def handle_failure(self, error, func, *args, **kwargs):
            raise ValueError("fallback-one")

    class AlsoBrokenFallback:
        async def handle_failure(self, error, func, *args, **kwargs):
            raise RuntimeError("fallback-two")

    chain = FallbackChain([BrokenFallback(), AlsoBrokenFallback()])

    async def primary() -> None:
        raise ConnectionError("primary boom")

    with pytest.raises(ConnectionError) as exc_info:
        await chain.execute(primary)

    fallback_errors = getattr(exc_info.value, "fallback_errors", ())
    assert len(fallback_errors) == 2
    assert fallback_errors[0]["error_message"] == "fallback-one"
    assert fallback_errors[1]["error_message"] == "fallback-two"
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert str(exc_info.value) == "primary boom"


@pytest.mark.asyncio
async def test_cache_fallback_uses_request_and_sets_resilience() -> None:
    version = DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value="v1",
        timestamp=datetime.now(UTC),
    )
    fetch_result = FetchResult(
        data=[{"ok": True}],
        row_count=1,
        schema_id="test.schema",
        schema_version="1.0.0",
        version=version,
        fetched_at=datetime.now(UTC),
        completeness=1.0,
    )

    class DummyCache:
        def __init__(self) -> None:
            self.seen = None

        def get_any(self, request, *, connector_id=None, max_staleness_seconds=None):
            self.seen = (request, connector_id, max_staleness_seconds)
            return SimpleNamespace(
                result=fetch_result,
                metadata=SimpleNamespace(cached_at=datetime.now(UTC)),
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
