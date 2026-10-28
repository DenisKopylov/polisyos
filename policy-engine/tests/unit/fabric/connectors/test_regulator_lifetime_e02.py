"""Behavioral counterexamples for B91/B93 regulator admission and lifetime."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.fabric.connectors.resilience._bounded_registry as registry_module
import polisyos.fabric.connectors.resilience.circuit_breaker as breaker_module
import polisyos.fabric.connectors.resilience.rate_limiter as rate_module
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, FetchRequest
from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.resilience import (
    AdaptiveRateLimiter,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    RateLimiter,
    RateLimiterConfig,
    ResilienceConfig,
    apply_resilience,
    with_circuit_breaker,
    with_rate_limit,
)
from polisyos.fabric.connectors.resilience._bounded_registry import (
    BoundedResourceRegistry,
    BoundedResourceRegistryCapacityError,
)
from polisyos.fabric.connectors.types import RateLimitError


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.now += delay


def _clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    clock = _Clock()
    monkeypatch.setattr(registry_module, "_monotonic", clock.monotonic)
    monkeypatch.setattr(rate_module, "_monotonic", clock.monotonic)
    monkeypatch.setattr(breaker_module, "_monotonic", clock.monotonic)
    monkeypatch.setattr(asyncio, "sleep", clock.sleep)
    return clock


def test_valid_finite_adaptive_rate_does_not_overflow_before_clamp() -> None:
    rate = 1.7e308
    limiter = AdaptiveRateLimiter(rate, RateLimiterConfig(rate_limit_rps=rate))
    for _ in range(100):
        limiter.record_success()
    assert limiter.rate_limit_rps == rate
    with pytest.raises(ValueError):
        limiter.adjust_rate(float("inf"))


def test_adaptive_rate_reduction_saturates_before_float_underflow() -> None:
    tiny = 5e-324
    config = RateLimiterConfig(
        rate_limit_rps=tiny, min_rate_rps=tiny, max_rate_rps=1.0, burst_size=1.0
    )
    limiter = AdaptiveRateLimiter(tiny, config)
    limiter.record_rate_limit()
    assert limiter.rate_limit_rps == tiny


@pytest.mark.parametrize("rate", [0.0, -1.0, float("nan"), float("inf"), -float("inf")])
@pytest.mark.asyncio
async def test_declared_invalid_mapping_rate_refuses_before_provider(rate: float) -> None:
    calls: list[str] = []

    async def provider() -> str:
        calls.append("called")
        return "ok"

    # An explicit invalid primary value cannot be silently replaced by an alias.
    wrapped = apply_resilience(provider, config={"rate_limit_rps": rate, "rate_limit": 1.0})
    with pytest.raises(ValueError):
        await wrapped()
    assert calls == []


@pytest.mark.asyncio
async def test_absent_rate_is_an_opt_out_not_invalid_zero() -> None:
    calls: list[str] = []

    async def provider() -> str:
        calls.append("called")
        return "ok"

    wrapped = apply_resilience(provider, config=ResilienceConfig(rate_limit_rps=None))
    assert await wrapped() == "ok"
    assert calls == ["called"]


class _RecordingREST(GenericRESTConnector):
    """Exercise real fetch/pagination and resilience around an in-memory provider seam."""

    def __init__(self, clock: _Clock) -> None:
        self.clock = clock
        self.calls: list[tuple[str, float, str]] = []
        self.fail = False
        super().__init__()

    async def _get_session(self, handle: ConnectionHandle) -> Any:
        del handle
        return object()

    async def _request_page_raw(
        self,
        handle: ConnectionHandle,
        session: Any,
        url: str,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        del session, headers
        page = str(params.get("page", "1"))
        self.calls.append((url, self.clock.now, page))
        if self.fail:
            raise ValueError("provider failed")
        rows = [{"id": 1}] if page == "1" else []
        data = {"data": rows}
        raw = b'{"data":[{"id":1}]}' if rows else b'{"data":[]}'
        return {"json": data, "_raw": raw, "headers": {}}, {}, len(raw)


@pytest.mark.parametrize("rate", [0.0, -1.0, float("nan"), float("inf")])
@pytest.mark.asyncio
async def test_rest_declared_invalid_rate_never_calls_provider(
    monkeypatch: pytest.MonkeyPatch, rate: float
) -> None:
    clock = _clock(monkeypatch)
    connector = _RecordingREST(clock)
    handle = await connector.connect(
        ConnectionConfig(url="https://example.test/", rate_limit_rps=rate)
    )
    with pytest.raises(ValueError):
        await connector.fetch(handle, FetchRequest(dataset_id="a"))
    assert connector.calls == []


@pytest.mark.asyncio
async def test_registry_installed_zero_rate_refuses_before_real_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    connector = _RecordingREST(clock)
    connector.resilience_config = {"rate_limit_rps": 0.0}
    registry = ConnectorRegistry()
    registry.register(_RecordingREST, factory=lambda: connector)
    admitted = registry.get("rest_json")
    handle = await admitted.connect(ConnectionConfig(url="https://example.test/"))
    with pytest.raises(ValueError):
        await admitted.fetch(handle, FetchRequest(dataset_id="a"))
    assert connector.calls == []


@pytest.mark.asyncio
async def test_rest_pages_and_later_fetch_share_one_fractional_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    connector = _RecordingREST(clock)
    handle = await connector.connect(
        ConnectionConfig(
            url="https://example.test/",
            headers={"X-REST-PageSize": "1"},
            rate_limit_rps=0.2,
        )
    )
    req = FetchRequest(dataset_id="a")
    assert (await connector.fetch(handle, req)).row_count == 1
    handle.clear_state()  # Diagnostic state is not the regulator owner.
    assert (await connector.fetch(handle, req)).row_count == 1
    assert [(when, page) for _, when, page in connector.calls] == [
        (0.0, "1"),
        (5.0, "2"),
        (10.0, "1"),
        (15.0, "2"),
    ]

    same = await connector.connect(
        ConnectionConfig(url="https://example.test/", rate_limit_rps=0.2)
    )
    assert (await connector.fetch(same, req)).row_count == 1
    assert connector.calls[-1][:2] == ("https://example.test/", 20.0)

    other = await connector.connect(ConnectionConfig(url="https://other.test/", rate_limit_rps=0.2))
    assert (await connector.fetch(other, req)).row_count == 1
    assert connector.calls[-1][:2] == ("https://other.test/", 20.0)


@pytest.mark.asyncio
async def test_equal_int_and_float_rates_share_the_rest_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    connector = _RecordingREST(clock)
    first = await connector.connect(ConnectionConfig(url="https://example.test/", rate_limit_rps=1))
    second = await connector.connect(
        ConnectionConfig(url="https://example.test/", rate_limit_rps=1.0)
    )
    request = FetchRequest(dataset_id="a")
    assert (await connector.fetch(first, request)).row_count == 1
    assert (await connector.fetch(second, request)).row_count == 1
    assert [when for _, when, _ in connector.calls] == [0.0, 1.0]


@pytest.mark.asyncio
async def test_equivalent_rates_share_apply_resilience_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    calls: list[float] = []

    async def provider(handle: ConnectionHandle) -> str:
        del handle
        calls.append(clock.now)
        return "ok"

    wrapped = apply_resilience(provider, config=ResilienceConfig(inherit_connection_config=True))
    first = ConnectionHandle(
        connector_id="same", config=ConnectionConfig(url="https://example.test/", rate_limit_rps=1)
    )
    second = ConnectionHandle(
        connector_id="same",
        config=ConnectionConfig(url="https://example.test/", rate_limit_rps=1.0),
    )
    assert await wrapped(first) == "ok"
    assert await wrapped(second) == "ok"
    assert calls == [0.0, 1.0]


@pytest.mark.asyncio
async def test_rest_circuit_failure_history_survives_distinct_fetches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    connector = _RecordingREST(clock)
    handle = await connector.connect(ConnectionConfig(url="https://example.test/"))
    request = FetchRequest(dataset_id="a")
    connector.fail = True
    for _ in range(10):
        with pytest.raises(ValueError, match="provider failed"):
            await connector.fetch(handle, request)
    assert len(connector.calls) == 10
    with pytest.raises(CircuitOpenError):
        await connector.fetch(handle, request)
    assert len(connector.calls) == 10

    connector.fail = False
    same = await connector.connect(ConnectionConfig(url="https://example.test/"))
    with pytest.raises(CircuitOpenError):
        await connector.fetch(same, request)
    assert len(connector.calls) == 10

    other = await connector.connect(ConnectionConfig(url="https://other.test/"))
    assert (await connector.fetch(other, request)).row_count == 1
    assert len(connector.calls) == 11


@pytest.mark.asyncio
async def test_provider_retry_after_protects_other_same_key_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    calls: list[float] = []

    @with_rate_limit(rate_limit_rps=100.0)
    async def provider(handle: Any) -> str:
        calls.append(clock.now)
        if len(calls) == 1:
            raise RateLimitError(connector_id=handle.connector_id, retry_after=30)
        return "ok"

    handle = SimpleNamespace(connector_id="a", config=SimpleNamespace(url="https://a.test/"))
    with pytest.raises(RateLimitError):
        await provider(handle)
    assert await provider(handle) == "ok"
    assert calls == [0.0, 30.0]


@pytest.mark.asyncio
async def test_cancelled_owner_releases_pin_after_state_becomes_neutral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    entered = asyncio.Event()
    hold = asyncio.Event()

    @with_rate_limit(rate_limit_rps=0.2)
    async def provider(handle: Any) -> str:
        if handle.connector_id == "a":
            entered.set()
            await hold.wait()
        return handle.connector_id

    registry = provider._rate_limiters  # type: ignore[attr-defined]
    registry._max_items = 1
    registry._ttl_seconds = 1.0
    a = SimpleNamespace(connector_id="a", config=SimpleNamespace(url="https://a.test/"))
    b = SimpleNamespace(connector_id="b", config=SimpleNamespace(url="https://b.test/"))
    task = asyncio.create_task(provider(a))
    await asyncio.wait_for(entered.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    clock.now = 6.0
    assert await provider(b) == "b"


@pytest.mark.asyncio
async def test_local_capacity_refusal_does_not_open_source_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    entered = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def provider(handle: Any) -> str:
        calls.append(handle.connector_id)
        if handle.connector_id == "a":
            entered.set()
            await release.wait()
        return handle.connector_id

    wrapped = apply_resilience(
        provider,
        config=ResilienceConfig(
            rate_limit_rps=1.0,
            circuit_breaker=CircuitBreakerConfig(failure_threshold=1, min_throughput=1),
        ),
    )
    rate_registry = wrapped._resilience_rate_limiters  # type: ignore[attr-defined]
    rate_registry._max_items = 1
    a = SimpleNamespace(connector_id="a", config=SimpleNamespace(url="https://a.test/"))
    b = SimpleNamespace(connector_id="b", config=SimpleNamespace(url="https://b.test/"))
    first = asyncio.create_task(wrapped(a))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        with pytest.raises(BoundedResourceRegistryCapacityError):
            await wrapped(b)
        assert calls == ["a"]
        release.set()
        assert await asyncio.wait_for(first, timeout=2) == "a"
        clock.now = 2.0
        assert await wrapped(b) == "b"
        assert calls == ["a", "b"]
    finally:
        release.set()
        if not first.done():
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first


@pytest.mark.asyncio
async def test_provider_capacity_named_exception_is_not_local_admission() -> None:
    calls: list[str] = []

    @with_circuit_breaker(CircuitBreakerConfig(failure_threshold=1, min_throughput=1))
    async def provider() -> None:
        calls.append("provider")
        raise BoundedResourceRegistryCapacityError("provider itself failed")

    with pytest.raises(BoundedResourceRegistryCapacityError):
        await provider()
    with pytest.raises(CircuitOpenError):
        await provider()
    assert calls == ["provider"]


@pytest.mark.asyncio
async def test_invalid_local_rate_does_not_open_source_breaker() -> None:
    calls: list[str] = []

    @with_circuit_breaker(CircuitBreakerConfig(failure_threshold=1, min_throughput=1))
    @with_rate_limit(rate_limit_rps=0.0)
    async def provider() -> str:
        calls.append("provider")
        return "ok"

    for _ in range(2):
        with pytest.raises(ValueError):
            await provider()
    assert calls == []


@pytest.mark.parametrize("ttl_pressure", [False, True], ids=["lru", "ttl"])
def test_half_open_circuit_is_protected_under_registry_pressure(
    monkeypatch: pytest.MonkeyPatch, ttl_pressure: bool
) -> None:
    clock = _clock(monkeypatch)
    registry = BoundedResourceRegistry[CircuitBreaker](
        max_items=1, ttl_seconds=1.0 if ttl_pressure else 100.0
    )

    def build(key: str) -> CircuitBreaker:
        return CircuitBreaker(
            circuit_id=key,
            config=CircuitBreakerConfig(failure_threshold=1, min_throughput=1, timeout_seconds=1.0),
        )

    with registry.lease("a", lambda: build("a")) as first:
        first.record_failure()
        old_identity = id(first)
    clock.now = 2.0
    with pytest.raises(BoundedResourceRegistryCapacityError):
        with registry.lease("b", lambda: build("b")):
            pass
    with registry.lease("a", lambda: build("a")) as current:
        assert id(current) == old_identity
        assert current.is_half_open()


@pytest.mark.parametrize("ttl_pressure", [False, True], ids=["lru", "ttl"])
@pytest.mark.asyncio
async def test_rate_owner_pin_blocks_eviction_before_real_acquire(
    monkeypatch: pytest.MonkeyPatch, ttl_pressure: bool
) -> None:
    clock = _clock(monkeypatch)
    entered = asyncio.Event()
    resume = asyncio.Event()
    provider_release = asyncio.Event()
    provider_started = asyncio.Event()
    paused = False
    original = RateLimiter.acquire

    async def observed_acquire(self: RateLimiter, tokens: float = 1.0) -> None:
        nonlocal paused
        if not paused:
            paused = True
            entered.set()
            await resume.wait()
        await original(self, tokens)

    monkeypatch.setattr(RateLimiter, "acquire", observed_acquire)
    calls: list[tuple[str, float]] = []

    @with_rate_limit(rate_limit_rps=0.2)
    async def provider(handle: Any) -> str:
        calls.append((handle.connector_id, clock.now))
        if len(calls) == 1:
            provider_started.set()
            await provider_release.wait()
        return "ok"

    registry = provider._rate_limiters  # type: ignore[attr-defined]
    registry._max_items = 1
    registry._ttl_seconds = 1.0
    a = SimpleNamespace(connector_id="a", config=SimpleNamespace(url="https://a.test/"))
    b = SimpleNamespace(connector_id="b", config=SimpleNamespace(url="https://b.test/"))
    first = asyncio.create_task(provider(a))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        if ttl_pressure:
            clock.now = 2.0
        with pytest.raises(BoundedResourceRegistryCapacityError):
            await provider(b)
        assert calls == []
        resume.set()
        # Wait until the first real producer crosses the rate boundary.
        await asyncio.wait_for(provider_started.wait(), timeout=2)
        second = asyncio.create_task(provider(a))
        assert await asyncio.wait_for(second, timeout=2) == "ok"
        assert [key for key, _ in calls] == ["a", "a"]
        assert calls[1][1] - calls[0][1] == pytest.approx(5.0)
    finally:
        resume.set()
        provider_release.set()
        await asyncio.wait_for(first, timeout=2)


@pytest.mark.parametrize("ttl_pressure", [False, True], ids=["lru", "ttl"])
@pytest.mark.asyncio
async def test_circuit_owner_pin_blocks_eviction_before_real_attempt(
    monkeypatch: pytest.MonkeyPatch, ttl_pressure: bool
) -> None:
    clock = _clock(monkeypatch)
    entered = asyncio.Event()
    resume = asyncio.Event()
    paused = False
    original = CircuitBreaker.execute

    async def observed_execute(self: CircuitBreaker, *args: Any, **kwargs: Any) -> Any:
        nonlocal paused
        if not paused:
            paused = True
            entered.set()
            await resume.wait()
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(CircuitBreaker, "execute", observed_execute)
    calls: list[str] = []

    @with_circuit_breaker(CircuitBreakerConfig(failure_threshold=1, min_throughput=1))
    async def provider(handle: Any) -> None:
        calls.append(handle.connector_id)
        raise ValueError("source failed")

    registry = provider._circuit_breakers  # type: ignore[attr-defined]
    registry._max_items = 1
    registry._ttl_seconds = 1.0
    a = SimpleNamespace(connector_id="a", config=SimpleNamespace(url="https://a.test/"))
    b = SimpleNamespace(connector_id="b", config=SimpleNamespace(url="https://b.test/"))
    first = asyncio.create_task(provider(a))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        if ttl_pressure:
            clock.now = 2.0
        with pytest.raises(BoundedResourceRegistryCapacityError):
            await provider(b)
        assert calls == []
        resume.set()
        with pytest.raises(ValueError, match="source failed"):
            await asyncio.wait_for(first, timeout=2)
        with pytest.raises(CircuitOpenError):
            await provider(a)
        assert calls == ["a"]
    finally:
        resume.set()
        if not first.done():
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
