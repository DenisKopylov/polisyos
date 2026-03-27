"""Tests for DynamoDB lock backend (mocked boto3)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# Guard: if boto3 not available, skip all tests
boto3 = pytest.importorskip("boto3")

from polisyos.scientist.engine.checkpoint import RunLockError
from polisyos.scientist.engine.locks.dynamodb_lock import (
    DynamoDBLockHandle,
    DynamoDBRunLock,
)


def _mock_table() -> MagicMock:
    table = MagicMock()
    table.put_item = MagicMock()
    table.delete_item = MagicMock()
    table.get_item = MagicMock(return_value={})
    table.update_item = MagicMock()
    return table


def _make_lock(table: MagicMock | None = None) -> DynamoDBRunLock:
    lock = DynamoDBRunLock(table_name="test-locks", region="us-east-1", heartbeat=False)
    lock._table = table or _mock_table()
    return lock


class TestDynamoDBLockAcquire:
    def test_acquire_success(self) -> None:
        table = _mock_table()
        lock = _make_lock(table)
        handle = lock.acquire(run_id="run-1", mode="run")
        assert handle.run_id == "run-1"
        assert handle.metadata["mode"] == "run"
        table.put_item.assert_called_once()

    def test_acquire_contention_raises(self) -> None:
        table = _mock_table()
        from botocore.exceptions import ClientError

        table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
            "PutItem",
        )
        lock = _make_lock(table)
        with pytest.raises(RunLockError, match="already locked"):
            lock.acquire(run_id="run-2", mode="run")

    def test_acquire_force_overwrites(self) -> None:
        table = _mock_table()
        from botocore.exceptions import ClientError

        # First call fails (conditional), second succeeds (force overwrite)
        table.put_item.side_effect = [
            ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
                "PutItem",
            ),
            None,
        ]
        lock = _make_lock(table)
        handle = lock.acquire(run_id="run-3", mode="run", force=True)
        assert handle.run_id == "run-3"
        assert table.put_item.call_count == 2


class TestDynamoDBLockRelease:
    def test_release_calls_delete(self) -> None:
        table = _mock_table()
        lock = _make_lock(table)
        handle = lock.acquire(run_id="run-4", mode="run")
        handle.release()
        table.delete_item.assert_called_once()


class TestDynamoDBStaleDetection:
    def test_detect_stale_expired(self) -> None:
        table = _mock_table()
        table.get_item.return_value = {"Item": {"lock_key": "k", "expires_at": 0}}
        lock = _make_lock(table)
        assert lock.detect_stale("run-5") is True

    def test_detect_stale_not_expired(self) -> None:
        import time

        table = _mock_table()
        table.get_item.return_value = {
            "Item": {"lock_key": "k", "expires_at": int(time.time()) + 9999}
        }
        lock = _make_lock(table)
        assert lock.detect_stale("run-6") is False

    def test_detect_stale_no_item(self) -> None:
        table = _mock_table()
        table.get_item.return_value = {}
        lock = _make_lock(table)
        assert lock.detect_stale("run-7") is False
