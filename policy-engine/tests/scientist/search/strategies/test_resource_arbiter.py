from __future__ import annotations

from polisyos.scientist.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourceMode,
    ResourcePolicy,
)


def test_resource_arbiter_owner_tracking() -> None:
    arbiter = ResourceArbiter(policy=ResourcePolicy(mode=ResourceMode.SEQUENTIAL_LOCK))
    assert arbiter.current_owner() is None
    with arbiter.acquire("torch"):
        assert arbiter.current_owner() == "torch"
    assert arbiter.current_owner() is None


def test_resource_arbiter_enforce_limits() -> None:
    arbiter = ResourceArbiter(policy=ResourcePolicy(soft_rss_mb=0, hard_rss_mb=0))
    soft, hard = arbiter.enforce_limits()
    assert soft
    assert hard


def test_resource_arbiter_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SCIENTIST_RESOURCE_MODE", "disabled")
    monkeypatch.setenv("SCIENTIST_SOFT_RSS_MB", "999")
    monkeypatch.setenv("SCIENTIST_HARD_RSS_MB", "1111")
    monkeypatch.setenv("SCIENTIST_ENABLE_MEMORY_CLEANUP", "0")

    arbiter = ResourceArbiter.from_env()
    assert arbiter.policy.mode == ResourceMode.DISABLED
    assert arbiter.policy.soft_rss_mb == 999
    assert arbiter.policy.hard_rss_mb == 1111
    assert not arbiter.policy.enable_cleanup
