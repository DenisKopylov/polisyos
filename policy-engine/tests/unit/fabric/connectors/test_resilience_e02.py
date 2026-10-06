"""Actual operation ownership under bounded registry pressure and fake monotonic time."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from polisyos.fabric.connectors.resilience import _bounded_registry as registry_module
from polisyos.fabric.connectors.resilience import rate_limiter as limiter_module
from polisyos.fabric.connectors.resilience._bounded_registry import (
    BoundedResourceRegistry,
    BoundedResourceRegistryCapacityError,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("advance", [2.0, 1000.0])
async def test_live_provider_owns_neutral_refilled_limiter_under_pressure(monkeypatch, advance):
    now = [0.0]
    monkeypatch.setattr(registry_module, "_monotonic", lambda: now[0])
    monkeypatch.setattr(limiter_module, "_monotonic", lambda: now[0])
    started, release = asyncio.Event(), asyncio.Event()
    physical_calls = []

    @limiter_module.with_rate_limit(1.0)
    async def actual_provider(handle):
        physical_calls.append(handle.connector_id)
        if handle.connector_id == "live":
            started.set()
            await release.wait()
        return handle.connector_id

    registry = actual_provider._rate_limiters
    registry._max_items = 1
    registry._ttl_seconds = 1.0
    live = asyncio.create_task(actual_provider(SimpleNamespace(connector_id="live")))
    await started.wait()
    original = registry.snapshot()["live"]
    now[0] = advance  # Bucket is neutral and TTL expired while real provider still awaits.
    try:
        with pytest.raises(BoundedResourceRegistryCapacityError):
            await actual_provider(SimpleNamespace(connector_id="pressure"))
        assert registry.snapshot()["live"] is original
        assert physical_calls == ["live"]
        original.record_rate_limit(10.0)
        assert registry.snapshot()["live"] is original
        assert not original.is_quiescent()
    finally:
        release.set()
        assert await live == "live"


@pytest.mark.asyncio
async def test_available_protected_capacity_admits_independent_actual_operation(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(registry_module, "_monotonic", lambda: now[0])
    monkeypatch.setattr(limiter_module, "_monotonic", lambda: now[0])
    started, release = asyncio.Event(), asyncio.Event()

    @limiter_module.with_rate_limit(0.5)
    async def actual_provider(handle):
        if handle.connector_id == "live":
            started.set()
            await release.wait()
        return handle.connector_id

    registry = actual_provider._rate_limiters
    registry._max_items = 2
    registry._ttl_seconds = 1.0
    live = asyncio.create_task(actual_provider(SimpleNamespace(connector_id="live")))
    await started.wait()
    original = registry.snapshot()["live"]
    now[0] = 1000.0
    try:
        assert await actual_provider(SimpleNamespace(connector_id="spare")) == "spare"
        assert registry.snapshot()["live"] is original
    finally:
        release.set()
        await live


@pytest.mark.asyncio
@pytest.mark.parametrize("termination", ["cancel", "error"])
async def test_actual_provider_cancel_or_error_releases_only_its_registry_lease(termination):
    started, release = asyncio.Event(), asyncio.Event()

    @limiter_module.with_rate_limit(1000.0)
    async def actual_provider(handle):
        started.set()
        await release.wait()
        raise ValueError("actual provider failure")

    registry = actual_provider._rate_limiters
    caller = asyncio.create_task(actual_provider(SimpleNamespace(connector_id="owned")))
    await started.wait()
    assert registry._leases == {"owned": 1}
    if termination == "cancel":
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
    else:
        release.set()
        with pytest.raises(ValueError, match="actual provider failure"):
            await caller
    assert registry._leases == {}


def test_same_key_concurrent_owners_share_finite_protected_slot():
    class Neutral:
        def is_quiescent(self):
            return True

    registry = BoundedResourceRegistry(max_items=1)
    with registry.lease("same", Neutral) as first:
        with registry.lease("same", Neutral) as second:
            assert first is second and registry._leases == {"same": 2}
            with pytest.raises(BoundedResourceRegistryCapacityError):
                with registry.lease("foreign", Neutral):
                    pytest.fail("unavailable protected owner was admitted")
        assert registry._leases == {"same": 1}
    assert registry._leases == {} and len(registry.snapshot()) == 1
