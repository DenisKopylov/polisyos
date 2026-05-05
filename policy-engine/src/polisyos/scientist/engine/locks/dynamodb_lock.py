"""Distributed run lock backed by DynamoDB.

Uses conditional ``PutItem`` with ``attribute_not_exists`` for atomic
acquisition and ``DeleteItem`` with token condition for safe release.
A daemon heartbeat thread extends ``expires_at`` via ``UpdateItem``.

Requires ``boto3`` (import-guarded).

Table schema
------------
* Partition key: ``lock_key`` (S)
* Attributes: ``token`` (S), ``metadata`` (S, JSON), ``expires_at`` (N, epoch seconds)
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.engine.checkpoint import RunLockError
from polisyos.scientist.engine.error_semantics import emit_degraded_path

logger = get_logger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError

    _HAS_BOTO3 = True
except ImportError:
    _HAS_BOTO3 = False
    ClientError = RuntimeError  # type: ignore[assignment,misc]

_DYNAMODB_LOCK_RUNTIME_ERRORS = (
    ClientError,
    AttributeError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


@dataclass
class DynamoDBLockHandle:
    """Handle for an acquired DynamoDB-based distributed lock."""

    run_id: str
    metadata: dict[str, Any]
    _table: Any = field(repr=False)
    _lock_key: str = field(repr=False)
    _token: str = field(repr=False)
    _heartbeat_stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _heartbeat_thread: threading.Thread | None = field(default=None, repr=False)

    def release(self) -> None:
        """Release the lock by conditionally deleting the DynamoDB item."""
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5)
        try:
            self._table.delete_item(
                Key={"lock_key": self._lock_key},
                ConditionExpression="attribute_exists(lock_key) AND #t = :token",
                ExpressionAttributeNames={"#t": "token"},
                ExpressionAttributeValues={":token": self._token},
            )
        except ClientError:
            logger.debug("Failed to release lock %s (already released?)", self._lock_key)

    def is_alive(self) -> bool:
        """Check if the DynamoDB item still exists and our token matches."""
        try:
            resp = self._table.get_item(Key={"lock_key": self._lock_key})
            item = resp.get("Item")
            if not item:
                return False
            if str(item.get("token") or "") != self._token:
                return False
            expires_at = int(item.get("expires_at", 0))
            return int(time.time()) <= expires_at
        except _DYNAMODB_LOCK_RUNTIME_ERRORS as exc:
            emit_degraded_path(
                component="scientist.engine.locks.dynamodb",
                operation="is_alive",
                reason="dynamodb_lock_status_probe_failed",
                exc=exc,
                details={"run_id": self.run_id, "lock_key": self._lock_key},
                log=logger,
            )
            return False

    def _start_heartbeat(self, ttl_s: int) -> None:
        interval = max(ttl_s // 3, 1)

        def _extend() -> None:
            while not self._heartbeat_stop.wait(interval):
                new_expires = int(time.time()) + ttl_s
                try:
                    self._table.update_item(
                        Key={"lock_key": self._lock_key},
                        UpdateExpression="SET expires_at = :ea",
                        ConditionExpression="#t = :token",
                        ExpressionAttributeNames={"#t": "token"},
                        ExpressionAttributeValues={
                            ":ea": new_expires,
                            ":token": self._token,
                        },
                    )
                except _DYNAMODB_LOCK_RUNTIME_ERRORS as exc:
                    emit_degraded_path(
                        component="scientist.engine.locks.dynamodb",
                        operation="heartbeat_extend",
                        reason="dynamodb_lock_heartbeat_failed",
                        exc=exc,
                        details={"run_id": self.run_id, "lock_key": self._lock_key},
                        log=logger,
                    )
                    self._heartbeat_stop.set()
                    break

        t = threading.Thread(target=_extend, daemon=True, name=f"ddb-lock-hb-{self.run_id}")
        self._heartbeat_thread = t
        t.start()


class DynamoDBRunLock:
    """Distributed run lock using DynamoDB conditional writes.

    Satisfies ``RunLockBackend`` protocol.
    """

    def __init__(
        self,
        *,
        table_name: str,
        region: str | None = None,
        key_prefix: str = "polisyos:run_lock:",
        ttl_seconds: int = 3600,
        heartbeat: bool = True,
    ) -> None:
        if not _HAS_BOTO3:
            raise ImportError(
                "boto3 is required for the DynamoDB lock backend. "
                "Install it with: pip install boto3"
            )
        self._table_name = table_name
        self._region = region
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._heartbeat = heartbeat
        self._table: Any = None
        self._init_lock = threading.Lock()

    def _get_table(self) -> Any:
        if self._table is not None:
            return self._table
        with self._init_lock:
            if self._table is None:
                kwargs: dict[str, Any] = {}
                if self._region:
                    kwargs["region_name"] = self._region
                resource = boto3.resource("dynamodb", **kwargs)
                self._table = resource.Table(self._table_name)
        return self._table

    def acquire(
        self, *, run_id: str, mode: str, force: bool = False, owner_token: str | None = None
    ) -> DynamoDBLockHandle:
        table = self._get_table()
        lock_key = f"{self._key_prefix}{run_id}"
        token = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
        expires_at = int(time.time()) + self._ttl_seconds

        metadata = {
            "run_id": run_id,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "mode": mode,
            "owner_token": token,
            "started_at": datetime.now(UTC).isoformat(),
        }
        metadata_json = json.dumps(metadata, ensure_ascii=True, sort_keys=True)

        try:
            table.put_item(
                Item={
                    "lock_key": lock_key,
                    "token": token,
                    "metadata": metadata_json,
                    "expires_at": expires_at,
                },
                ConditionExpression=("attribute_not_exists(lock_key) OR expires_at < :now"),
                ExpressionAttributeValues={
                    ":now": int(time.time()),
                },
            )
        except ClientError as exc:
            error_code = (
                exc.response.get("Error", {}).get("Code", "") if hasattr(exc, "response") else ""
            )
            if error_code == "ConditionalCheckFailedException":
                if force:
                    if not owner_token:
                        raise RunLockError(
                            f"run {run_id} force acquisition requires owner_token"
                        ) from exc
                    try:
                        table.put_item(
                            Item={
                                "lock_key": lock_key,
                                "token": token,
                                "metadata": metadata_json,
                                "expires_at": expires_at,
                            },
                            ConditionExpression=(
                                "attribute_exists(lock_key) AND #t = :owner_token"
                            ),
                            ExpressionAttributeNames={"#t": "token"},
                            ExpressionAttributeValues={":owner_token": owner_token},
                        )
                    except ClientError as force_exc:
                        raise RunLockError(
                            f"run {run_id} force acquisition rejected: owner token mismatch"
                        ) from force_exc
                else:
                    raise RunLockError(f"run {run_id} is already locked in DynamoDB") from exc
            else:
                raise

        handle = DynamoDBLockHandle(
            run_id=run_id,
            metadata=metadata,
            _table=table,
            _lock_key=lock_key,
            _token=token,
        )
        if self._heartbeat:
            handle._start_heartbeat(self._ttl_seconds)
        return handle

    def detect_stale(self, run_id: str) -> bool:
        """Check if the lock for *run_id* has expired."""
        table = self._get_table()
        lock_key = f"{self._key_prefix}{run_id}"
        try:
            resp = table.get_item(Key={"lock_key": lock_key})
            item = resp.get("Item")
            if item is None:
                return False
            expires_at = int(item.get("expires_at", 0))
            return int(time.time()) > expires_at
        except _DYNAMODB_LOCK_RUNTIME_ERRORS as exc:
            emit_degraded_path(
                component="scientist.engine.locks.dynamodb",
                operation="detect_stale",
                reason="dynamodb_lock_stale_probe_failed",
                exc=exc,
                details={"run_id": run_id, "lock_key": lock_key},
                log=logger,
            )
            return False
