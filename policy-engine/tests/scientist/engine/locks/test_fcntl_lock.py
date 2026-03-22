"""Tests for FcntlRunLock."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from polisyos.scientist.engine.checkpoint import RunLockError
from polisyos.scientist.engine.lock_protocol import RunLockBackend, RunLockHandle


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl is Unix-only")
class TestFcntlRunLock:
    def test_satisfies_protocol(self, tmp_path: Path):
        from polisyos.scientist.engine.locks.fcntl_lock import FcntlRunLock

        lock_backend = FcntlRunLock(run_dir=tmp_path)
        assert isinstance(lock_backend, RunLockBackend)

    def test_acquire_and_release(self, tmp_path: Path):
        from polisyos.scientist.engine.locks.fcntl_lock import FcntlRunLock

        lock_backend = FcntlRunLock(run_dir=tmp_path)
        handle = lock_backend.acquire(run_id="test-001", mode="run")
        assert isinstance(handle, RunLockHandle)
        assert handle.run_id == "test-001"
        assert "mode" in handle.metadata
        handle.release()

    def test_double_acquire_raises(self, tmp_path: Path):
        from polisyos.scientist.engine.locks.fcntl_lock import FcntlRunLock

        lock_backend = FcntlRunLock(run_dir=tmp_path)
        handle = lock_backend.acquire(run_id="test-002", mode="run")
        try:
            with pytest.raises(RunLockError):
                lock_backend.acquire(run_id="test-002", mode="run")
        finally:
            handle.release()

    def test_force_with_stale_lock_metadata(self, tmp_path: Path):
        """Force acquire when lock file has stale metadata (dead PID)."""
        import json

        from polisyos.scientist.engine.checkpoint import RUN_LOCK_FILENAME
        from polisyos.scientist.engine.locks.fcntl_lock import FcntlRunLock

        # Write stale lock metadata with a non-existent PID
        lock_path = tmp_path / RUN_LOCK_FILENAME
        lock_path.write_text(json.dumps({
            "run_id": "test-003",
            "pid": 999999999,  # non-existent PID
            "hostname": "other-host",
            "mode": "run",
        }))

        lock_backend = FcntlRunLock(run_dir=tmp_path)
        # Should succeed since no flock is actually held (only metadata exists)
        handle = lock_backend.acquire(run_id="test-003", mode="run")
        handle.release()

    def test_metadata_has_expected_fields(self, tmp_path: Path):
        from polisyos.scientist.engine.locks.fcntl_lock import FcntlRunLock

        lock_backend = FcntlRunLock(run_dir=tmp_path)
        handle = lock_backend.acquire(run_id="test-004", mode="run")
        try:
            assert "mode" in handle.metadata
            assert "pid" in handle.metadata
            assert "hostname" in handle.metadata
        finally:
            handle.release()
