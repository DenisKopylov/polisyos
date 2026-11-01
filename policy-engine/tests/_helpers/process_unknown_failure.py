"""Actual process-entry error transport for the canonical retry boundary.

This fixture uses the real worker, framed channel, drain and error decoder.  It
does not qualify Darwin's closed builtin-node timeout admission, Linux process
tree supervision, paid effects or transport of a settlement/control capability.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import os
import sqlite3
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from polisyos.core import run as core_run
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.errors import ErrorCategory
from polisyos.core.registry import build_default_registry_bundle
from polisyos.scientist.orchestration.engine import retry as retry_module
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import NodeExecutionError
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState

FailureKind = Literal["known_transient", "wrapped_unknown", "grouped_unknown", "forwarded_unknown"]


def create_entry_database(path: Path) -> None:
    """Create the independent physical-entry observer, without suppressing repeats."""
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE entries (pid INTEGER, run_id TEXT, run_dir TEXT, kind TEXT)")


def read_entries(path: Path) -> list[tuple[int, str, str, str]]:
    """Read committed entries through a fresh SQLite connection."""
    with sqlite3.connect(path) as database:
        return database.execute(
            "SELECT pid, run_id, run_dir, kind FROM entries ORDER BY rowid"
        ).fetchall()


@dataclass(frozen=True)
class _ErrorProducer:
    database_path: Path
    kind: FailureKind
    run_id: str
    run_dir: Path

    def execute(self, context: object, state: ExperimentState) -> NodeOutcome:
        del context
        # Entry observations are not idempotency guards or atomic external
        # effects: if retry redispatches, another committed row must appear.
        with sqlite3.connect(self.database_path) as database:
            database.execute(
                "INSERT INTO entries VALUES (?, ?, ?, ?)",
                (os.getpid(), self.run_id, str(self.run_dir), self.kind),
            )
        state.params["failed_worker_write"] = "must not reach the parent"
        error = NodeExecutionError(
            "Same declared transient diagnostic",
            category=ErrorCategory.TRANSIENT,
            code="fixture.transient",
        )
        if self.kind == "known_transient":
            raise error
        unknown = core_run.ChildOutcomeUnknownError(
            "The child effect needs reconciliation",
            run_id=self.run_id,
            run_dir=self.run_dir,
        )
        if self.kind == "grouped_unknown":
            raise error from ExceptionGroup("concurrent work", [ValueError("other"), unknown])
        if self.kind == "forwarded_unknown":
            try:
                raise error from unknown
            except NodeExecutionError as wrapped:
                forwarded = retry_module._worker_node_error(
                    retry_module._worker_error_payload(wrapped), expected_run_id=self.run_id
                )
            # The old Python cause/context is gone after decoding. The second
            # encoder must consult the decoder's typed recovery locators.
            assert forwarded.__cause__ is None and forwarded.__context__ is None
            raise NodeExecutionError(
                "Same declared transient diagnostic",
                category=ErrorCategory.TRANSIENT,
                code="fixture.transient",
            ) from forwarded
        raise error from unknown


def _worker_entry(
    root: Path,
    database_path: Path,
    kind: FailureKind,
    state_bytes: bytes,
    channel: Any,
    completion_time: Any,
    remove_encoder_guard: bool,
) -> None:
    from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_state_safe

    run = None
    try:
        state = deserialize_state_safe(state_bytes)
        store = FileSystemCAS(root / "cas")
        registry = build_default_registry_bundle(store, return_selected_profile=True)
        run = core_run.RunContext.start(store, registry.bundle_ref, run_id=state.run_id)
        context = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
        assert run.trace_path is not None
        node = _ErrorProducer(database_path, kind, state.run_id, run.trace_path.parent)
        if remove_encoder_guard:
            # A removal in this isolated interpreter exercises the same real
            # worker/encoder/receiver. No file or parent process is modified.
            retry_module._error_chain = lambda error: iter((error,))
        retry_module._node_execute_worker(
            node,
            context,
            state,
            channel,
            completion_time=completion_time,
        )
    except BaseException:
        root.mkdir(parents=True, exist_ok=True)
        (root / "bootstrap-failure.txt").write_text(traceback.format_exc())
        raise
    finally:
        if run is not None:
            run.suspend_for_resume()


@dataclass
class ProcessErrorBridge:
    """Use the canonical process entry and receiver from an ordinary retry node."""

    root: Path
    database_path: Path
    kind: FailureKind
    remove_encoder_guard: bool = False
    payloads: list[dict[str, Any]] = field(default_factory=list)
    decoded: list[BaseException] = field(default_factory=list)
    child_pids: list[int] = field(default_factory=list)

    def _start(self, state: ExperimentState) -> tuple[Any, Any, Any, float, Path]:
        from polisyos.scientist.orchestration.engine.runner.serialization import (
            serialize_state_safe,
        )

        process_context = mp.get_context("spawn")
        channel = retry_module._WorkerResultChannel(process_context)
        completed = process_context.Value("d", 0.0)
        root = self.root / uuid.uuid4().hex
        deadline = time.monotonic() + 60.0
        state_bytes, _ = serialize_state_safe(state)
        process = process_context.Process(
            target=_worker_entry,
            args=(
                root,
                self.database_path,
                self.kind,
                state_bytes,
                channel,
                completed,
                self.remove_encoder_guard,
            ),
        )
        process.start()
        assert process.pid is not None
        self.child_pids.append(process.pid)
        channel.close_writer()
        return process, channel, completed, deadline, root

    @staticmethod
    def _close(process: Any, channel: Any, root: Path) -> None:
        try:
            process.join(timeout=3)
            if process.is_alive():
                process.terminate()
                process.join(timeout=3)
                raise AssertionError("native process entry did not finish after delivery")
            diagnostic = root / "bootstrap-failure.txt"
            assert process.exitcode == 0, (
                process.exitcode,
                diagnostic.read_text() if diagnostic.exists() else "no bootstrap diagnostic",
            )
        finally:
            if process.is_alive():
                process.kill()
                process.join(timeout=3)
            process.close()
            retry_module._close_result_queue(channel)

    def _receive(self, status: str, payload: Any, run_id: str) -> NodeOutcome:
        assert status == "error", (status, payload)
        assert isinstance(payload, dict)
        self.payloads.append(payload)
        decoded = retry_module._worker_node_error(payload, expected_run_id=run_id)
        self.decoded.append(decoded)
        raise decoded

    def execute(self, context: object, state: ExperimentState) -> NodeOutcome:
        del context
        process, channel, completed, deadline, root = self._start(state)
        try:
            status, payload = retry_module._drain_result_sync(
                process, channel, compute_deadline=deadline, completion_time=completed
            )
        finally:
            self._close(process, channel, root)
        return self._receive(status, payload, state.run_id)

    async def execute_async(self, context: object, state: ExperimentState) -> NodeOutcome:
        del context
        process, channel, completed, deadline, root = self._start(state)
        try:
            status, payload = await retry_module._drain_result_async(
                process, channel, compute_deadline=deadline, completion_time=completed
            )
        finally:
            # A completed worker has no producer work to wait for here.
            await asyncio.to_thread(self._close, process, channel, root)
        return self._receive(status, payload, state.run_id)
