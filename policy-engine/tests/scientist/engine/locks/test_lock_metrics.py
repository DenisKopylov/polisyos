"""Tests for lock contention metrics."""

from __future__ import annotations

import pytest

from polisyos.scientist.engine.locks.metrics import LockMetrics


class TestLockMetrics:
    """Verify LockMetrics methods execute without error (no-op if OTel not configured)."""

    def test_record_acquire(self) -> None:
        m = LockMetrics(backend="test")
        m.record_acquire(0.05, success=True)
        m.record_acquire(0.1, success=False)

    def test_record_contention(self) -> None:
        m = LockMetrics(backend="test")
        m.record_contention()

    def test_record_heartbeat_failure(self) -> None:
        m = LockMetrics(backend="test")
        m.record_heartbeat_failure()

    def test_measure_acquire_success(self) -> None:
        m = LockMetrics(backend="test")
        with m.measure_acquire():
            pass  # success path

    def test_measure_acquire_failure(self) -> None:
        m = LockMetrics(backend="test")
        with pytest.raises(RuntimeError):
            with m.measure_acquire():
                raise RuntimeError("fail")
