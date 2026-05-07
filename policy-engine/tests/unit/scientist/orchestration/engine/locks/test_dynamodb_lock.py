"""Tests for DynamoDB lock backend (mocked boto3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Guard: if boto3 not available, skip all tests
boto3 = pytest.importorskip("boto3")

from polisyos.scientist.orchestration.engine.checkpoint import RunLockError
from polisyos.scientist.orchestration.engine.locks.dynamodb_lock import DynamoDBRunLock


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

    def test_acquire_force_requires_owner_token(self) -> None:
        table = _mock_table()
        from botocore.exceptions import ClientError

        table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
            "PutItem",
        )
        lock = _make_lock(table)
        with pytest.raises(RunLockError, match="requires owner_token"):
            lock.acquire(run_id="run-3", mode="run", force=True)

    def test_acquire_force_with_owner_token(self) -> None:
        table = _mock_table()
        from botocore.exceptions import ClientError

        # First call fails (conditional), second succeeds with token provenance.
        table.put_item.side_effect = [
            ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
                "PutItem",
            ),
            None,
        ]
        lock = _make_lock(table)
        handle = lock.acquire(
            run_id="run-3",
            mode="run",
            force=True,
            owner_token="existing-token",
        )
        assert handle.run_id == "run-3"
        assert table.put_item.call_count == 2
        assert (
            table.put_item.call_args.kwargs["ExpressionAttributeValues"][":owner_token"]
            == "existing-token"
        )


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

    def test_detect_stale_runtime_probe_error_returns_false(self) -> None:
        table = _mock_table()
        table.get_item.side_effect = RuntimeError("ddb down")
        lock = _make_lock(table)
        assert lock.detect_stale("run-8") is False


class TestDynamoDBHandleLiveness:
    def test_is_alive_runtime_probe_error_returns_false(self) -> None:
        table = _mock_table()
        table.get_item.side_effect = RuntimeError("ddb down")
        lock = _make_lock(table)
        handle = lock.acquire(run_id="run-9", mode="run")

        assert handle.is_alive() is False
