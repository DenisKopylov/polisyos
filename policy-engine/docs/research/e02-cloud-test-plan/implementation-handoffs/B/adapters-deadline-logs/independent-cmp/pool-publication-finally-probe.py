"""Exercise real pool deadline/physical drain after contended publication bookkeeping."""

import argparse
import asyncio
from contextlib import suppress
import hashlib
import json
from pathlib import Path
import time

import polisyos.fabric.connectors.pool as pool_module
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig, PoolExhaustedError


class Connector:
    def __init__(self):
        self.health_started = asyncio.Event()
        self.health_proceed = asyncio.Event()
        self.disconnects = []

    async def connect(self, config):
        return ConnectionHandle(connector_id="publication-finally-probe", config=config)

    async def health_check(self, handle):
        self.health_started.set()
        await self.health_proceed.wait()
        return HealthStatus(healthy=True)

    async def disconnect(self, handle):
        self.disconnects.append(handle.session_id)


async def wait_for_lock_waiters(lock, count):
    deadline = asyncio.get_running_loop().time() + 0.3
    while len(lock._waiters or ()) < count:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Real lock scheduling precondition unavailable")
        await asyncio.sleep(0)


async def main(control):
    source_path = Path(pool_module.__file__).resolve()
    source = source_path.read_bytes()
    connector = Connector()
    pool = ConnectionPool(lambda: connector, ConnectionConfig(url="https://e02.invalid"),
                          PoolConfig(max_size=1, acquire_timeout_seconds=0.08,
                                     connection_timeout_seconds=0.5, validate_on_acquire=True),
                          pool_id="publication-finally-probe")
    witness_entered, witness_release = asyncio.Event(), asyncio.Event()

    async def witness():
        async with pool._lock:
            witness_entered.set()
            await witness_release.wait()

    def state():
        return {"in_use": sorted(pool._in_use), "pending": sorted(pool._pending_cleanup),
                "active_acquires": pool._active_acquires,
                "active_acquires_done": pool._active_acquires_done.is_set(),
                "semaphore_value": pool._semaphore._value,
                "disconnects": list(connector.disconnects)}

    task = asyncio.create_task(pool.acquire())
    holder, close = None, None
    lock_owned = False
    result = {"probe": "real pool lock: publication queued before independent holder; expiry while final bookkeeping awaits",
              "control_release_before_expiry": control,
              "module_path": str(source_path), "module_sha256": hashlib.sha256(source).hexdigest(),
              "budget_seconds": 0.08, "cancel_suppression_in_connector": False,
              "start_monotonic": time.monotonic()}
    try:
        await asyncio.wait_for(connector.health_started.wait(), 0.3)
        await pool._lock.acquire()
        lock_owned = True
        connector.health_proceed.set()
        await wait_for_lock_waiters(pool._lock, 1)
        holder = asyncio.create_task(witness())
        await wait_for_lock_waiters(pool._lock, 2)
        pool._lock.release()
        lock_owned = False
        await asyncio.wait_for(witness_entered.wait(), 0.3)
        result["at_witness_entered"] = state()
        if control:
            witness_release.set()
        try:
            handle = await asyncio.wait_for(asyncio.shield(task), 0.3)
            result["acquire_outcome"] = "returned_handle"
            result["returned_session_id"] = handle.session_id
        except PoolExhaustedError:
            result["acquire_outcome"] = "PoolExhaustedError"
        result["after_acquire"] = state()
        witness_release.set()
        await holder
        close = asyncio.create_task(pool.close_all())
        try:
            await asyncio.wait_for(asyncio.shield(close), 0.05)
            result["close_outcome"] = "completed"
        except TimeoutError:
            result["close_outcome"] = "blocked_after_all_connector_operations_settled"
        result["after_close_observation"] = state()
        result["source_unchanged"] = source_path.read_bytes() == source
        result["failures"] = []
        if not control and result["close_outcome"] != "completed":
            result["failures"].append("Real close consumer cannot drain a completed expired acquire; all connector I/O cooperates")
        if result["after_close_observation"]["active_acquires"]:
            result["failures"].append("Completed acquire retains active registration")
        if result["close_outcome"] == "completed" and result["after_close_observation"]["semaphore_value"] != 1:
            result["failures"].append("Physical permit was not returned after completed close")
        print(json.dumps(result, indent=2), flush=True)
    finally:
        if lock_owned:
            pool._lock.release()
        witness_release.set()
        if holder is not None:
            await holder
        connector.health_proceed.set()
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError, PoolExhaustedError):
            await task
        # Explicit test-only rescue AFTER the deciding drain oracle, never acceptance evidence.
        # This avoids leaving a task or real physical handle in the harness after a negative.
        if pool._active_acquires and task.done():
            pool._active_acquires = 0
            pool._active_acquires_done.set()
        if close is not None:
            await asyncio.wait_for(asyncio.shield(close), 0.3)
        else:
            await asyncio.wait_for(pool.close_all(), 0.3)
    return int(bool(result.get("failures")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-before-expiry", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.release_before_expiry)))
