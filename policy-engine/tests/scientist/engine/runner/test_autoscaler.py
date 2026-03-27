"""Tests for AutoScaler and scaling decisions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from polisyos.scientist.engine.runner.autoscaler import (
    AutoScalePolicy,
    AutoScaler,
    ScaleDecision,
    ScaleDirection,
)
from polisyos.scientist.engine.runner.worker_pool import PoolCapacity


def _mock_pool(total: int = 10, active: int = 0) -> AsyncMock:
    pool = AsyncMock()
    pool.current_capacity = AsyncMock(
        return_value=PoolCapacity(
            total_workers=total,
            idle_workers=total - active,
            active_tasks=active,
            queue_depth=0,
        )
    )
    pool.scale_to = AsyncMock()
    return pool


class TestAutoScaler:
    def test_high_load_scales_up(self) -> None:
        pool = _mock_pool(total=10, active=9)
        policy = AutoScalePolicy(
            scale_up_threshold=0.8, max_workers=20, cooldown_s=0,
        )
        scaler = AutoScaler(pool, policy)
        decision = asyncio.run(scaler.evaluate())
        assert decision.direction is ScaleDirection.UP
        assert decision.target_workers > 10

    def test_low_load_scales_down(self) -> None:
        pool = _mock_pool(total=10, active=1)
        policy = AutoScalePolicy(
            scale_down_threshold=0.2, min_workers=2, cooldown_s=0,
        )
        scaler = AutoScaler(pool, policy)
        decision = asyncio.run(scaler.evaluate())
        assert decision.direction is ScaleDirection.DOWN
        assert decision.target_workers < 10

    def test_within_thresholds_no_scale(self) -> None:
        pool = _mock_pool(total=10, active=5)
        policy = AutoScalePolicy(cooldown_s=0)
        scaler = AutoScaler(pool, policy)
        decision = asyncio.run(scaler.evaluate())
        assert decision.direction is ScaleDirection.NONE

    def test_cooldown_prevents_scaling(self) -> None:
        pool = _mock_pool(total=10, active=9)
        policy = AutoScalePolicy(
            scale_up_threshold=0.8, cooldown_s=999,
        )
        scaler = AutoScaler(pool, policy)
        # First evaluation should scale
        # But set last_scale_at to now to simulate cooldown
        import time
        scaler._last_scale_at = time.monotonic()
        decision = asyncio.run(scaler.evaluate())
        assert decision.direction is ScaleDirection.NONE
        assert "cooldown" in decision.reason

    def test_max_workers_cap(self) -> None:
        pool = _mock_pool(total=15, active=14)
        policy = AutoScalePolicy(
            scale_up_threshold=0.8, max_workers=15, cooldown_s=0,
        )
        scaler = AutoScaler(pool, policy)
        decision = asyncio.run(scaler.evaluate())
        assert decision.direction is ScaleDirection.NONE
        assert "max workers" in decision.reason

    def test_min_workers_floor(self) -> None:
        pool = _mock_pool(total=2, active=0)
        policy = AutoScalePolicy(
            scale_down_threshold=0.2, min_workers=2, cooldown_s=0,
        )
        scaler = AutoScaler(pool, policy)
        decision = asyncio.run(scaler.evaluate())
        assert decision.direction is ScaleDirection.NONE

    def test_apply_calls_scale_to(self) -> None:
        pool = _mock_pool(total=10, active=9)
        policy = AutoScalePolicy(cooldown_s=0)
        scaler = AutoScaler(pool, policy)

        decision = ScaleDecision(
            direction=ScaleDirection.UP,
            current_workers=10,
            target_workers=15,
            reason="test",
        )
        asyncio.run(scaler.apply(decision))
        pool.scale_to.assert_awaited_once_with(15)

    def test_apply_noop_for_none(self) -> None:
        pool = _mock_pool()
        scaler = AutoScaler(pool)

        decision = ScaleDecision(
            direction=ScaleDirection.NONE,
            current_workers=10,
            target_workers=10,
            reason="test",
        )
        asyncio.run(scaler.apply(decision))
        pool.scale_to.assert_not_awaited()
