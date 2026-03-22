"""Tests for RedisRunLock using mocked Redis client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polisyos.scientist.engine.checkpoint import RunLockError
from polisyos.scientist.engine.lock_protocol import RunLockBackend, RunLockHandle


class TestRedisRunLock:
    def _make_lock(self, redis_mock=None):
        from polisyos.scientist.engine.locks.redis_lock import RedisRunLock

        lock = RedisRunLock(
            redis_url="redis://localhost:6379",
            ttl_seconds=60,
            heartbeat=False,  # Disable heartbeat thread in tests
        )
        if redis_mock is not None:
            lock._client = redis_mock  # Bypass lazy init
        return lock

    def test_satisfies_protocol(self):
        from polisyos.scientist.engine.locks.redis_lock import RedisRunLock

        lock = RedisRunLock.__new__(RedisRunLock)
        assert isinstance(lock, RunLockBackend)

    def test_acquire_success(self):
        redis_mock = MagicMock()
        redis_mock.set.return_value = True

        lock = self._make_lock(redis_mock)
        handle = lock.acquire(run_id="test-001", mode="run")

        assert isinstance(handle, RunLockHandle)
        assert handle.run_id == "test-001"
        # set() is called at least once (for the key itself)
        assert redis_mock.set.call_count >= 1

    def test_acquire_failure_raises(self):
        redis_mock = MagicMock()
        # First set() call (nx=True) returns False → already locked
        redis_mock.set.return_value = False
        redis_mock.get.return_value = "existing-token"

        lock = self._make_lock(redis_mock)
        with pytest.raises(RunLockError, match="already locked"):
            lock.acquire(run_id="test-002", mode="run")

    def test_acquire_force(self):
        redis_mock = MagicMock()
        # First call with nx=True returns False, second (force) succeeds
        redis_mock.set.side_effect = [False, True, True]

        lock = self._make_lock(redis_mock)
        handle = lock.acquire(run_id="test-003", mode="run", force=True)
        assert handle.run_id == "test-003"

    def test_release(self):
        redis_mock = MagicMock()
        redis_mock.set.return_value = True
        redis_mock.eval.return_value = 1

        lock = self._make_lock(redis_mock)
        handle = lock.acquire(run_id="test-004", mode="run")
        handle.release()
        redis_mock.eval.assert_called_once()

    def test_metadata_fields(self):
        redis_mock = MagicMock()
        redis_mock.set.return_value = True

        lock = self._make_lock(redis_mock)
        handle = lock.acquire(run_id="test-005", mode="run")
        assert "mode" in handle.metadata
        assert handle.metadata["mode"] == "run"
        assert "pid" in handle.metadata
        assert "hostname" in handle.metadata
        handle.release()

    def test_handle_satisfies_protocol(self):
        redis_mock = MagicMock()
        redis_mock.set.return_value = True

        lock = self._make_lock(redis_mock)
        handle = lock.acquire(run_id="test-006", mode="run")
        assert isinstance(handle, RunLockHandle)
        handle.release()
