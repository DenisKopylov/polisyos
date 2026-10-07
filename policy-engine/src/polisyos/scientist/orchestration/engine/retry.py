"""Per-node retry + timeout wrappers for the Scientist engine.

Provides :class:`RetryPolicy` (a Pydantic model embedded in
:class:`NodeInvocation`) and two execution wrappers:

* :func:`execute_with_retry_sync` — for ``WorkflowExecutor``
* :func:`execute_with_retry_async` — for the future ``AsyncWorkflowExecutor``

When ``RetryPolicy.max_retries == 0`` and ``timeout_s is None`` the wrappers
delegate directly to ``node.execute()`` with minimal overhead.
"""

from __future__ import annotations

import asyncio
import base64
import contextvars
import ctypes
import dataclasses
import json
import logging
import multiprocessing as mp
import os
import queue
import random
import signal
import sys
import threading
import time
from concurrent.futures import wait
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.async_tools import get_shared_executor, run_blocking_async
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts import (
    BoundedLivenessConfig,
    bounded_liveness_config_from_mapping,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.errors import (
    CircuitBreakerOpenError,
    NodeTimeoutError,
    RetryExhaustedError,
)
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeOutcome,
    decode_node_outcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.scientist.orchestration.engine.circuit_breaker import CircuitBreaker
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

_logger = logging.getLogger(__name__)

# Node computation has one deadline; framed result delivery has one finite
# window from the actual completion mark. Parent and supervisor drain while
# their producer runs. No Queue feeder or blocking partial-frame read can
# silently extend that window.
_PROCESS_RESULT_POLL_S = 0.01
_PROCESS_GROUP_READY_S = 0.05
_PROCESS_DELIVERY_GRACE_S = 1.0
_PROCESS_CLEANUP_GRACE_S = 1.0


class _WorkerComputeTimeout(Exception):
    """The worker did not finish computation before the node deadline."""


class _WorkerDeliveryTimeout(Exception):
    """The worker finished, but its result was not delivered in bounded time."""


class _WorkerResultChannel:
    """One framed Pipe, drained without blocking on a partial result frame."""

    def __init__(self, context: Any) -> None:
        self._reader, self._writer = context.Pipe(duplex=False)
        try:
            os.set_blocking(self._reader.fileno(), False)
            self._buffer = bytearray()
            self._size: int | None = None
        except BaseException:
            self.close()
            raise

    def put(self, value: Any) -> None:
        status, data = value
        binary = isinstance(data, bytes)
        wire = {
            "status": status,
            "encoding": "bytes" if binary else "json",
            "payload": base64.b64encode(data).decode("ascii") if binary else data,
        }
        payload = json.dumps(wire, separators=(",", ":")).encode("utf-8")
        view = memoryview(len(payload).to_bytes(8, "big") + payload)
        while view:
            written = os.write(self._writer.fileno(), view)
            view = view[written:]

    def get_nowait(self) -> tuple[str, Any]:
        try:
            chunk = os.read(self._reader.fileno(), 65536)
        except BlockingIOError:
            chunk = None
        if chunk:
            self._buffer.extend(chunk)
        if self._size is None and len(self._buffer) >= 8:
            self._size = int.from_bytes(self._buffer[:8], "big")
            del self._buffer[:8]
        if self._size is not None and len(self._buffer) >= self._size:
            wire = json.loads(self._buffer[: self._size])
            if not isinstance(wire, dict) or wire.get("encoding") not in {"bytes", "json"}:
                raise ValueError("invalid worker result envelope")
            data = wire["payload"]
            if wire["encoding"] == "bytes":
                data = base64.b64decode(data, validate=True)
            status = wire["status"]
            if not isinstance(status, str):
                raise ValueError("invalid worker result status")
            return status, data
        if chunk == b"":
            raise EOFError("worker result channel closed before a complete frame")
        raise queue.Empty

    def get(self, *, timeout: float) -> tuple[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            try:
                return self.get_nowait()
            except queue.Empty:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(min(0.001, max(0.0, deadline - time.monotonic())))

    def close_reader(self) -> None:
        self._reader.close()

    def close_writer(self) -> None:
        self._writer.close()

    def close(self) -> None:
        self.close_reader()
        self.close_writer()

    def join_thread(self) -> None:
        # No Queue feeder thread exists on this transport.
        pass


def _enable_child_subreaper() -> None:
    """Set Linux ownership only in the separate supervisor process."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _kernel_parent_pid(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii") as stream:
            # The command field may itself contain spaces and parentheses.
            return int(stream.read().rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def _owned_child_pids() -> tuple[int, ...]:
    """Read kernel PPID; /proc task/children is optional on Linux kernels."""
    parent = os.getpid()
    with os.scandir("/proc") as entries:
        return tuple(
            int(entry.name)
            for entry in entries
            if entry.name.isdecimal() and _kernel_parent_pid(int(entry.name)) == parent
        )


def _kill_owned_child(pid: int) -> None:
    """Pin Linux identity through libc even when Python omits pidfd wrappers."""
    libc = ctypes.CDLL(None, use_errno=True)
    descriptor = libc.pidfd_open(pid, 0)
    if descriptor < 0:
        error = ctypes.get_errno()
        if error == 3:  # ESRCH: already gone.
            return
        raise OSError(error, os.strerror(error))
    try:
        if _kernel_parent_pid(pid) == os.getpid():
            if libc.pidfd_send_signal(descriptor, int(signal.SIGKILL), None, 0) < 0:
                error = ctypes.get_errno()
                if error != 3:
                    raise OSError(error, os.strerror(error))
    finally:
        os.close(descriptor)


def _reap_owned_children() -> bool:
    """Kill and reap adopted descendants, including new-session grandchildren."""
    deadline = time.monotonic() + _PROCESS_CLEANUP_GRACE_S * 0.75
    while True:
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return True
            if pid == 0:
                break
        children = _owned_child_pids()
        for pid in children:
            _kill_owned_child(pid)
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.001)


def _node_execute_supervisor(
    node: Any,
    ctx: Any,
    state: Any,
    result_channel: Any,
    group_ready: Any,
    completion_time: Any,
    compute_deadline: float,
    cleanup_complete: Any,
) -> None:
    """Own one real node process and reap it before exposing its result."""
    result_channel.close_reader()
    if sys.platform != "linux":
        # The established group boundary remains available; native non-Linux
        # descendant reaping is not established by this Linux supervisor.
        _node_execute_worker(node, ctx, state, result_channel, group_ready, completion_time)
        result_channel.close_writer()
        return
    stopped = False
    child_channel: _WorkerResultChannel | None = None
    payload: tuple[str, Any] | None = None

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal stopped
        stopped = True

    try:
        os.setsid()
        _enable_child_subreaper()
        signal.signal(signal.SIGTERM, stop)
        group_ready.set()
        child_channel = _WorkerResultChannel(mp.get_context("fork"))
        worker_pid = os.fork()
        if worker_pid == 0:
            result_channel.close_writer()
            child_channel.close_reader()
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            try:
                try:
                    _node_execute_worker(node, ctx, state, child_channel, None, completion_time)
                except (SystemExit, KeyboardInterrupt) as exc:
                    completion_time.value = time.monotonic()
                    code = exc.code if isinstance(exc, SystemExit) else None
                    if code is not None and not isinstance(code, (int, str)):
                        child_channel.put(
                            (
                                "error",
                                {
                                    "message": "SystemExit code is unsupported by the process control contract",
                                    "category": "fatal",
                                    "code": "node.control_unsupported",
                                },
                            )
                        )
                    else:
                        child_channel.put(
                            (
                                "control",
                                {
                                    "kind": "SystemExit"
                                    if isinstance(exc, SystemExit)
                                    else "KeyboardInterrupt",
                                    "code": code,
                                },
                            )
                        )
                child_channel.close_writer()
            finally:
                os._exit(0)
        child_channel.close_writer()
        while not stopped:
            deadline = (
                float(completion_time.value) + _PROCESS_DELIVERY_GRACE_S
                if completion_time.value > 0
                else compute_deadline
            )
            if time.monotonic() >= deadline:
                break
            try:
                payload = child_channel.get_nowait()
                break
            except queue.Empty:
                time.sleep(0.001)
            except EOFError:
                break
    except _RETRY_RUNTIME_ERRORS as exc:
        completion_time.value = time.monotonic()
        payload = ("error", _worker_error_payload(exc))
    finally:
        clean = _reap_owned_children()
        cleanup_complete.value = clean
        if child_channel is not None:
            child_channel.close()
    if not clean:
        payload = ("cleanup_incomplete", "owned kernel descendants were not reaped")
    if payload is not None and not stopped:
        result_channel.put(payload)
    result_channel.close_writer()


@dataclasses.dataclass
class _WorkerLifecycle:
    """Shared state for one forked worker's compute and cleanup lifetimes."""

    compute_deadline: float
    completion_time: Any
    process_group_id: int | None = None
    cleanup_complete: Any = None

    def completed_before_deadline(self) -> bool:
        """Return whether the worker marked node execution complete in time."""
        return _completion_before_deadline(
            self.completion_time,
            self.compute_deadline,
        )


_RETRY_RUNTIME_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
_DEAD_LETTER_PERSIST_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


# The typed engine store exposes these two persistence calls.  The ownership
# hook is included because RunContext invokes it on the same store during a
# run write; FileSystemCAS-only signing/import helpers are outside this lease.
_STORE_WRITE_METHODS = frozenset(
    {
        "put_bytes",
        "put_json",
        "record_artifact_owner",
    }
)
_RUN_WRITE_METHODS = frozenset(
    {
        "_emit_record",
        "_record_ref_owner",
        "add_input",
        "add_output",
        "emit",
        "finalize",
    }
)
_TRACE_WRITE_METHODS = frozenset({"emit", "close"})
_AUDIT_WRITE_METHODS = frozenset({"append", "close"})
_CLAIM_WRITE_METHODS = frozenset(
    {
        "advance_verified_batch",
        "append_verified_owner_event",
        "finalize_initial_root",
        "migrate_legacy_roots",
        "persist_candidate_ledger",
        "prepare_initial_ledger",
        "produce_owner_event_candidate",
    }
)


class _AttemptAuthority:
    """Serialize attempt-owned writes and revoke them after a timeout.

    The lock is deliberately shared by every facade for one attempt.  A write
    that has acquired it is linearized before ``revoke``; every later write is
    denied.  This is a local authority boundary, not a process sandbox.
    """

    def __init__(self, deadline_monotonic: float | None = None) -> None:
        self._lock = threading.RLock()
        self._active = True
        self._deadline = deadline_monotonic

    def invoke(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        """Run one authorized operation, or deny it after revocation."""
        with self._lock:
            if not self._active or (
                self._deadline is not None and time.monotonic() >= self._deadline
            ):
                return None
            return operation(*args, **kwargs)

    def revoke(self) -> None:
        """Make all subsequent attempt-owned writes no-ops."""
        with self._lock:
            self._active = False


class _AttemptFacade:
    """Delegate reads while gating the named mutating methods."""

    def __init__(
        self,
        target: Any,
        authority: _AttemptAuthority,
        *,
        write_methods: frozenset[str],
    ) -> None:
        self._target = target
        self._authority = authority
        self._write_methods = write_methods

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._target, name)
        if callable(value) and name in self._write_methods:
            return lambda *args, **kwargs: self._authority.invoke(
                value,
                *(_unwrap_manifest_value(arg) for arg in args),
                **{key: _unwrap_manifest_value(item) for key, item in kwargs.items()},
            )
        return value


_MUTATING_COLLECTION_METHODS = frozenset(
    {
        "append",
        "clear",
        "extend",
        "insert",
        "pop",
        "remove",
        "reverse",
        "sort",
        "update",
        "setdefault",
    }
)


class _AttemptCollectionFacade:
    """Gate mutation of a list/dict nested in the run manifest."""

    def __init__(self, target: Any, authority: _AttemptAuthority) -> None:
        self._target = target
        self._authority = authority

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._target, name)
        if callable(value) and name in _MUTATING_COLLECTION_METHODS:
            return lambda *args, **kwargs: _wrap_manifest_value(
                self._authority.invoke(
                    value,
                    *(_unwrap_manifest_value(arg) for arg in args),
                    **{key: _unwrap_manifest_value(item) for key, item in kwargs.items()},
                ),
                self._authority,
            )
        if callable(value) and name == "get":
            return lambda *args, **kwargs: _wrap_manifest_value(
                value(*args, **kwargs), self._authority
            )
        if callable(value) and name == "items":
            return lambda *args, **kwargs: (
                (key, _wrap_manifest_value(item, self._authority))
                for key, item in value(*args, **kwargs)
            )
        if callable(value) and name == "values":
            return lambda *args, **kwargs: (
                _wrap_manifest_value(item, self._authority) for item in value(*args, **kwargs)
            )
        if callable(value) and name == "copy":
            return lambda *args, **kwargs: _wrap_manifest_value(
                value(*args, **kwargs), self._authority
            )
        return value

    def __getitem__(self, key: Any) -> Any:
        return _wrap_manifest_value(self._target[key], self._authority)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._authority.invoke(self._target.__setitem__, key, _unwrap_manifest_value(value))

    def __delitem__(self, key: Any) -> None:
        self._authority.invoke(self._target.__delitem__, key)

    def __iter__(self):
        return (_wrap_manifest_value(item, self._authority) for item in self._target)

    def __len__(self) -> int:
        return len(self._target)

    def __contains__(self, value: object) -> bool:
        return value in self._target


class _AttemptModelFacade:
    """Gate mutable descendants that are Pydantic models in a manifest."""

    def __init__(self, target: BaseModel, authority: _AttemptAuthority) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_authority", authority)

    @property
    def __class__(self) -> type[Any]:
        return type(self._target)

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._target, name)
        if callable(value) and name in {"copy", "model_copy"}:
            return lambda *args, **kwargs: _wrap_manifest_value(
                value(
                    *(_unwrap_manifest_value(arg) for arg in args),
                    **{key: _unwrap_manifest_value(item) for key, item in kwargs.items()},
                ),
                self._authority,
            )
        return _wrap_manifest_value(value, self._authority)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        self._authority.invoke(
            setattr,
            self._target,
            name,
            _unwrap_manifest_value(value),
        )


class _AttemptManifestFacade(_AttemptModelFacade):
    """Preserve direct on-time manifest writes while denying revoked writes."""


def _wrap_manifest_value(value: Any, authority: _AttemptAuthority) -> Any:
    """Wrap mutable manifest descendants without changing scalar values."""
    if isinstance(value, (list, dict)):
        return _AttemptCollectionFacade(value, authority)
    if isinstance(value, BaseModel):
        return _AttemptModelFacade(value, authority)
    if isinstance(value, tuple):
        return tuple(_wrap_manifest_value(item, authority) for item in value)
    return value


def _unwrap_manifest_value(value: Any) -> Any:
    """Recover the underlying object when a gated value is passed to a write."""
    if isinstance(value, (_AttemptFacade, _AttemptCollectionFacade, _AttemptModelFacade)):
        return value._target
    if isinstance(value, tuple):
        return tuple(_unwrap_manifest_value(item) for item in value)
    return value


class _AttemptRunFacade(_AttemptFacade):
    """Run facade with isolated manifest and trace sink references."""

    def __init__(
        self,
        target: Any,
        authority: _AttemptAuthority,
        store: Any,
    ) -> None:
        super().__init__(target, authority, write_methods=_RUN_WRITE_METHODS)
        object.__setattr__(self, "store", store)
        manifest = getattr(target, "run_manifest", None)
        object.__setattr__(
            self,
            "run_manifest",
            _AttemptManifestFacade(manifest, authority) if manifest is not None else None,
        )
        for name in ("trace", "_audit_sink"):
            sink = getattr(target, name, None)
            if sink is not None:
                setattr(
                    self,
                    name,
                    _AttemptFacade(
                        sink,
                        authority,
                        write_methods=_TRACE_WRITE_METHODS,
                    ),
                )

    def __setattr__(self, name: str, value: Any) -> None:
        if "_target" in self.__dict__:
            target_value = _unwrap_manifest_value(value)
            if name in {"store", "trace", "_audit_sink"}:
                self._authority.invoke(setattr, self._target, name, target_value)
                if target_value is None:
                    value = None
                else:
                    write_methods = (
                        _STORE_WRITE_METHODS if name == "store" else _TRACE_WRITE_METHODS
                    )
                    value = _AttemptFacade(
                        target_value,
                        self._authority,
                        write_methods=write_methods,
                    )
            elif name == "run_manifest":
                self._authority.invoke(
                    setattr,
                    self._target,
                    name,
                    target_value,
                )
                value = _AttemptManifestFacade(target_value, self._authority)
        object.__setattr__(self, name, value)


class _AttemptContext:
    """Private worker context preserving the public context attribute surface."""

    def __init__(self, target: Any, authority: _AttemptAuthority) -> None:
        self._target = target
        self.store = _AttemptFacade(
            target.store,
            authority,
            write_methods=_STORE_WRITE_METHODS,
        )
        self.run = _AttemptRunFacade(target.run, authority, self.store)
        audit = getattr(target, "audit", None)
        if audit is not None:
            self.audit = _AttemptFacade(
                audit,
                authority,
                write_methods=_AUDIT_WRITE_METHODS,
            )
        claim_owner = getattr(target, "claim_ledger_owner", None)
        if claim_owner is not None:
            self.claim_ledger_owner = _AttemptFacade(
                claim_owner,
                authority,
                write_methods=_CLAIM_WRITE_METHODS,
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


def _build_attempt_context(target: Any, authority: _AttemptAuthority) -> Any:
    """Build a gated context without changing its concrete public type."""
    proxy = _AttemptContext(target, authority)
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    if not isinstance(target, ExecutionContext):
        return proxy
    field_names = {field.name for field in dataclasses.fields(target)}
    replacements = {
        name: getattr(proxy, name)
        for name in field_names
        if name in {"store", "run", "audit", "claim_ledger_owner"}
    }
    try:
        return dataclasses.replace(target, **replacements)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("failed to preserve ExecutionContext type for timed attempt") from exc


class RetryPolicy(BaseModel):
    """Declarative retry configuration attached to a :class:`NodeInvocation`."""

    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(default=0, ge=0, le=5)
    backoff_base_s: float = Field(default=1.0, ge=0.1, le=60.0)
    backoff_factor: float = Field(default=2.0, ge=1.0, le=10.0)
    jitter: Literal["none", "full", "equal"] = Field(
        default="full",
        description="Jitter strategy: none (exact), full (0..delay), equal (delay/2..delay)",
    )
    retry_on: list[str] = Field(
        default_factory=lambda: ["node.exception"],
        description="Error codes that trigger retry",
    )


def _should_retry(error: NodeError | None, policy: RetryPolicy) -> bool:
    if error is None:
        return False
    return error.code in policy.retry_on


def _retry_write_paths(node: Any) -> tuple[str, ...]:
    """Return the node's declared state write paths for retry isolation."""
    spec = getattr(node, "spec", None)
    raw_paths = getattr(spec, "state_writes", ()) if spec is not None else ()
    if isinstance(raw_paths, str):
        raw_paths = (raw_paths,)
    try:
        return tuple(path for path in raw_paths if isinstance(path, str) and path.strip())
    except TypeError:
        return ()


def _fresh_retry_state(baseline: ExperimentState, node: Any) -> ExperimentState:
    """Create one isolated attempt branch from the immutable logical baseline."""
    return branch_state(baseline, write_paths=_retry_write_paths(node)).state


def _typed_error_category(exc: BaseException) -> str | None:
    """Return an explicit PolicyOS error category when one is declared."""
    category = getattr(exc, "category", None)
    if category is None:
        category = getattr(exc, "default_category", None)
    value = getattr(category, "value", category)
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in {"transient", "fatal", "validation"} else None


def _exception_category(exc: BaseException) -> str:
    """Use the canonical classifier once, before an exception crosses IPC."""
    from polisyos.scientist.orchestration.engine.runner.error_classifier import (
        classify_remote_error,
    )

    category = _typed_error_category(exc)
    if category in {"fatal", "validation"}:
        return "fatal"
    if category == "transient":
        return "transient"
    if isinstance(exc, (AssertionError, AttributeError, LookupError)):
        return "fatal"
    return str(classify_remote_error(exc).value)


def _exception_code(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    return code if isinstance(code, str) and code else "node.exception"


def _should_retry_exception(exc: BaseException, policy: RetryPolicy) -> bool:
    """Apply the same semantic category/code on direct, thread and IPC routes."""
    return _exception_category(exc) != "fatal" and _exception_code(exc) in policy.retry_on


def _worker_control_error(payload: Any) -> BaseException:
    """Restore only the two built-in process control exceptions, without guessing."""
    if not isinstance(payload, dict):
        return _WorkerNodeError(
            message="invalid worker control envelope",
            category="fatal",
            code="node.control_protocol",
        )
    if payload.get("kind") == "KeyboardInterrupt":
        return KeyboardInterrupt()
    if payload.get("kind") == "SystemExit" and (
        payload.get("code") is None or isinstance(payload.get("code"), (int, str))
    ):
        return SystemExit(payload.get("code"))
    return _WorkerNodeError(
        message="invalid worker control envelope", category="fatal", code="node.control_protocol"
    )


class _WorkerNodeError(RuntimeError):
    """Carry typed retry semantics without reconstructing arbitrary exceptions."""

    def __init__(
        self,
        *,
        message: str,
        category: str,
        code: str,
        known_spend: dict[str, Decimal] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.code = code
        self.known_spend = known_spend


class _CompletedAttemptError(RuntimeError):
    """Deliver only known completed-failure spend beside the original local error."""

    def __init__(self, error: BaseException, known_spend: dict[str, Decimal]) -> None:
        super().__init__(str(error))
        self.error = error
        self.category = _exception_category(error)
        self.code = _exception_code(error)
        self.known_spend = known_spend


def _worker_error_payload(
    exc: BaseException, *, known_spend: dict[str, Decimal] | None = None, run_id: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": f"{type(exc).__name__}: {exc}",
        "category": _exception_category(exc),
        "code": _exception_code(exc),
    }
    if known_spend is not None:
        from polisyos.scientist.orchestration.engine.runner.serialization import (
            serialize_state_safe,
        )

        if run_id is None:
            raise ValueError("known failed-spend projection requires its run identity")
        projection = ExperimentState(run_id=run_id, budgets=known_spend)
        wire, _ = serialize_state_safe(projection)
        payload["known_spend_state_v1"] = base64.b64encode(wire).decode("ascii")
    return payload


def _worker_node_error(payload: Any, *, expected_run_id: str | None = None) -> _WorkerNodeError:
    if (
        not isinstance(payload, dict)
        or payload.get("category") not in {"fatal", "transient", "unknown"}
        or not isinstance(payload.get("code"), str)
        or not payload["code"]
        or not isinstance(payload.get("message"), str)
    ):
        raise ValueError("invalid typed node error payload")
    known_spend = None
    if "known_spend_state_v1" in payload:
        from polisyos.scientist.orchestration.engine.runner.serialization import (
            deserialize_state_safe,
        )

        encoded = payload["known_spend_state_v1"]
        if not isinstance(encoded, str):
            raise ValueError("invalid known failed-spend wire payload")
        projection = deserialize_state_safe(base64.b64decode(encoded, validate=True))
        if expected_run_id is not None and projection.run_id != expected_run_id:
            raise ValueError("failed-spend projection run identity mismatch")
        known_spend = _spend_snapshot(projection)
        if set(known_spend) != set(projection.budgets) or any(
            value <= 0 for value in known_spend.values()
        ):
            raise ValueError("invalid known failed-spend quantity")
    return _WorkerNodeError(
        message=payload["message"],
        category=payload["category"],
        code=payload["code"],
        known_spend=known_spend,
    )


def _spend_snapshot(state: ExperimentState) -> dict[str, Decimal]:
    """Read the declared cumulative spend fields from one attempt state."""
    budgets = getattr(state, "budgets", {})
    if not isinstance(budgets, dict):
        return {}
    snapshot: dict[str, Decimal] = {}
    for key, value in budgets.items():
        if not isinstance(key, str) or not key.endswith("_spent_usd"):
            continue
        try:
            snapshot[key] = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            continue
    return snapshot


def _spend_delta(
    baseline: ExperimentState,
    attempt_state: ExperimentState,
) -> dict[str, Decimal]:
    """Return positive spend added by one attempt relative to its baseline."""
    return _spend_changes(_spend_snapshot(baseline), _spend_snapshot(attempt_state))


def _spend_changes(before: dict[str, Decimal], after: dict[str, Decimal]) -> dict[str, Decimal]:
    delta: dict[str, Decimal] = {}
    for key, value in after.items():
        change = value - before.get(key, Decimal(0))
        if change > 0:
            delta[key] = change
    return delta


def _execute_capture_failure(node: Any, ctx: Any, state: ExperimentState) -> NodeOutcome:
    before = _spend_snapshot(state)
    try:
        return node.execute(ctx, state)
    except _RETRY_RUNTIME_ERRORS as exc:
        raise _CompletedAttemptError(exc, _spend_changes(before, _spend_snapshot(state))) from exc


def _accumulate_spend(
    total: dict[str, Decimal],
    delta: dict[str, Decimal],
) -> None:
    """Accumulate spend without carrying ordinary failed state mutations."""
    for key, value in delta.items():
        total[key] = total.get(key, Decimal(0)) + value


def _merge_spend(state: ExperimentState, spend: dict[str, Decimal]) -> None:
    """Publish cumulative failed-attempt spend onto the accepted state branch."""
    if not spend:
        return
    budgets = getattr(state, "budgets", None)
    if not isinstance(budgets, dict):
        return
    for key, value in spend.items():
        current = budgets.get(key, Decimal(0))
        try:
            current_decimal = current if isinstance(current, Decimal) else Decimal(str(current))
        except (InvalidOperation, TypeError, ValueError):
            continue
        budgets[key] = current_decimal + value


def _preserve_retry_spend(
    base_state: ExperimentState,
    terminal_state: ExperimentState,
) -> ExperimentState:
    """Carry failed-attempt spend without publishing ordinary failed writes.

    A synchronous executor catches :class:`RetryExhaustedError` outside this
    wrapper and deliberately falls back to its pre-node state.  The retry
    wrapper has already accumulated only the typed ``*_spent_usd`` fields on
    ``terminal_state``; reapply that delta to a fresh branch of ``base_state``
    instead of replacing the state with the failed branch wholesale.
    """
    spend = _spend_delta(base_state, terminal_state)
    if not spend:
        return base_state
    preserved = branch_state(base_state, write_paths=("budgets",)).state
    _merge_spend(preserved, spend)
    return preserved


def _retry_metrics(
    *,
    attempt: int,
    delay: float,
    spend: dict[str, Decimal],
) -> dict[str, float | int]:
    """Build the typed, durable trace metrics for one failed attempt."""
    metrics: dict[str, float | int] = {
        "attempt": attempt,
        "delay_s": delay,
    }
    if spend:
        metrics["failed_cost_usd"] = float(sum(spend.values(), Decimal(0)))
    return metrics


def _emit_retry_event(
    ctx: ExecutionContext,
    alias: str,
    *,
    attempt: int,
    delay: float,
    spend: dict[str, Decimal],
) -> None:
    """Persist one typed failed-attempt record in the canonical run trace."""
    ctx.run.emit(
        f"scientist.node.{alias}",
        "NODE_RETRY",
        metrics=_retry_metrics(attempt=attempt, delay=delay, spend=spend),
    )


def _emit_dead_letter_event(
    ctx: ExecutionContext,
    alias: str,
    *,
    attempt: int,
    output: ArtifactRef,
    spend: dict[str, Decimal],
) -> None:
    """Persist terminal attempt count and spend with the dead-letter event."""
    metrics: dict[str, float | int] = {"attempts": attempt}
    if spend:
        metrics["failed_cost_usd"] = float(sum(spend.values(), Decimal(0)))
    ctx.run.emit(
        f"scientist.node.{alias}",
        "NODE_DEAD_LETTER",
        outputs=[output],
        metrics=metrics,
    )


def _backoff_delay(attempt: int, policy: RetryPolicy) -> float:
    base = policy.backoff_base_s * (policy.backoff_factor**attempt)
    if policy.jitter == "none":
        return base
    if policy.jitter == "full":
        return random.uniform(0, base)
    # "equal" jitter: half deterministic + half random
    return base / 2 + random.uniform(0, base / 2)


def _persist_dead_letter(
    ctx: ExecutionContext,
    alias: str,
    node_id: str,
    last_error: Exception,
    attempts: int,
    policy: RetryPolicy,
) -> ArtifactRef | None:
    """Persist a dead-letter artifact on retry exhaustion (best-effort)."""
    try:
        payload = {
            "kind": "scientist.dead_letter",
            "run_id": getattr(ctx.run.run_manifest, "run_id", ""),
            "alias": alias,
            "node_id": node_id,
            "error_type": type(last_error).__name__,
            "error_message": str(last_error),
            "attempts": attempts,
            # Canonical JSON forbids floats, so retain numeric retry knobs as
            # strings and let Pydantic coerce them back during replay.
            "policy": _serialize_dead_letter_policy(policy),
            "created_at": datetime.now(UTC).isoformat(),
        }
        return ctx.store.put_json(
            payload,
            PutOptions(
                kind="scientist.dead_letter",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.DeadLetter",
                    version="1.0",
                ),
            ),
        )
    except _DEAD_LETTER_PERSIST_ERRORS as exc:
        emit_degraded_path(
            component="scientist.engine.retry",
            operation="persist_dead_letter",
            reason="dead_letter_persist_failed",
            exc=exc,
            details={"alias": alias, "node_id": node_id, "attempts": attempts},
            log=_logger,
        )
        return None


def _serialize_dead_letter_policy(policy: RetryPolicy) -> dict[str, Any]:
    raw = policy.model_dump(mode="python")
    serialized: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, float):
            serialized[key] = str(value)
            continue
        if isinstance(value, list):
            serialized[key] = [str(item) if isinstance(item, float) else item for item in value]
            continue
        serialized[key] = value
    return serialized


def _apply_bounded_liveness_retry_ceiling(
    *,
    alias: str,
    retry_policy: RetryPolicy,
    liveness_config: BoundedLivenessConfig | Mapping[str, Any] | None,
) -> RetryPolicy:
    if liveness_config is None:
        return retry_policy
    resolved = bounded_liveness_config_from_mapping(liveness_config).resolve(
        f"scientist.node.{alias}",
        requested_retries=retry_policy.max_retries,
    )
    if resolved.retry_ceiling == retry_policy.max_retries:
        return retry_policy
    return retry_policy.model_copy(update={"max_retries": resolved.retry_ceiling})


def _invocation_deadline(timeout_s: float | None, deadline_monotonic: float | None) -> float | None:
    """Resolve one immutable budget before admission or the first attempt."""
    configured = time.monotonic() + timeout_s if timeout_s is not None else None
    if configured is None:
        return deadline_monotonic
    return configured if deadline_monotonic is None else min(configured, deadline_monotonic)


def _deadline_error(execution_state: str) -> NodeTimeoutError:
    return NodeTimeoutError(
        "Node invocation deadline expired",
        code="node.timeout",
        details={"execution_state": execution_state},
    )


def _remaining_deadline(
    deadline: float | None, *, execution_state: str = "not_admitted"
) -> float | None:
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _deadline_error(execution_state)
    return remaining


def _retry_delay_sync(delay: float, deadline: float | None) -> None:
    remaining = _remaining_deadline(deadline, execution_state="retry_not_admitted")
    time.sleep(delay if remaining is None else min(delay, remaining))
    _remaining_deadline(deadline, execution_state="retry_not_admitted")


async def _retry_delay_async(delay: float, deadline: float | None) -> None:
    remaining = _remaining_deadline(deadline, execution_state="retry_not_admitted")
    await asyncio.sleep(delay if remaining is None else min(delay, remaining))
    _remaining_deadline(deadline, execution_state="retry_not_admitted")


def execute_with_retry_sync(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    retry_policy: RetryPolicy,
    timeout_s: float | None,
    alias: str,
    circuit_breaker: CircuitBreaker | None = None,
    liveness_config: BoundedLivenessConfig | Mapping[str, Any] | None = None,
    deadline_monotonic: float | None = None,
) -> NodeOutcome:
    """Sync retry wrapper for ``WorkflowExecutor``.

    One monotonic deadline covers admission, attempts, backoff and publication.
    Process computation retains a separate bounded drain window; publication
    still checks the original invocation deadline. An absent deadline is unbounded.
    """
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    _remaining_deadline(deadline)
    retry_policy = _apply_bounded_liveness_retry_ceiling(
        alias=alias,
        retry_policy=retry_policy,
        liveness_config=liveness_config,
    )
    # Fast path — no retry, no timeout
    if retry_policy.max_retries == 0 and deadline is None and circuit_breaker is None:
        return node.execute(ctx, state)

    last_outcome: NodeOutcome | None = None
    failed_spend: dict[str, Decimal] = {}
    node_id = str((getattr(node, "spec", None) and node.spec.metadata.component_id) or alias)

    for attempt in range(retry_policy.max_retries + 1):
        try:
            remaining = _remaining_deadline(deadline)
        except NodeTimeoutError:
            _merge_spend(state, failed_spend)
            raise
        # Circuit breaker check
        if circuit_breaker is not None and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open for node {alias}",
            )

        attempt_state = _fresh_retry_state(state, node) if retry_policy.max_retries > 0 else state
        try:
            if remaining is not None:
                outcome = _execute_with_timeout_sync(
                    node,
                    ctx,
                    attempt_state,
                    timeout_s=remaining,
                    deadline_monotonic=deadline,
                )
            else:
                outcome = node.execute(ctx, attempt_state)

            try:
                _remaining_deadline(deadline, execution_state="completed_publication_rejected")
            except NodeTimeoutError:
                _accumulate_spend(failed_spend, _spend_delta(state, outcome.state))
                raise
            if outcome.status != "fail":
                _merge_spend(outcome.state, failed_spend)
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
                return outcome

            # Node returned a "fail" outcome — check retry_on filter
            if circuit_breaker is not None:
                circuit_breaker.record_failure()

            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                attempt_spend = _spend_delta(state, outcome.state)
                _accumulate_spend(failed_spend, attempt_spend)
                last_outcome = outcome
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s (attempt %d/%d) after %.1fs",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    delay,
                )
                _emit_retry_event(
                    ctx,
                    alias,
                    attempt=attempt + 1,
                    delay=delay,
                    spend=attempt_spend,
                )
                _retry_delay_sync(delay, deadline)
                continue

            _merge_spend(outcome.state, failed_spend)
            return outcome

        except NodeTimeoutError:
            _merge_spend(state, failed_spend)
            raise
        except CircuitBreakerOpenError:
            raise
        except KeyboardInterrupt:
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            original_error = exc.error if isinstance(exc, _CompletedAttemptError) else exc
            captured_spend = (
                exc.known_spend
                if isinstance(exc, (_CompletedAttemptError, _WorkerNodeError))
                else None
            )
            attempt_spend = (
                captured_spend if captured_spend is not None else _spend_delta(state, attempt_state)
            )
            _accumulate_spend(failed_spend, attempt_spend)
            try:
                _remaining_deadline(
                    deadline, execution_state="completed_error_publication_rejected"
                )
            except NodeTimeoutError:
                _merge_spend(state, failed_spend)
                raise
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            if attempt < retry_policy.max_retries and _should_retry_exception(
                exc,
                retry_policy,
            ):
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s after exception (attempt %d/%d): %s",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    exc,
                )
                _emit_retry_event(
                    ctx,
                    alias,
                    attempt=attempt + 1,
                    delay=delay,
                    spend=attempt_spend,
                )
                try:
                    _retry_delay_sync(delay, deadline)
                except NodeTimeoutError:
                    _merge_spend(state, failed_spend)
                    raise
                continue

            _merge_spend(state, failed_spend)
            dlq_ref = _persist_dead_letter(
                ctx,
                alias,
                node_id,
                original_error,
                attempts=attempt + 1,
                policy=retry_policy,
            )
            if dlq_ref is not None:
                _emit_dead_letter_event(
                    ctx,
                    alias,
                    attempt=attempt + 1,
                    output=dlq_ref,
                    spend=failed_spend,
                )
            raise RetryExhaustedError(
                f"Node {alias}: all {retry_policy.max_retries} retries exhausted",
            ) from original_error

    # Should not reach here, but for safety:
    if last_outcome is not None:
        return last_outcome
    raise RetryExhaustedError(  # pragma: no cover
        f"Node {alias}: all retries exhausted",
    )


def _submit_thread_attempt(
    node: Any, ctx: Any, state: ExperimentState, deadline: float
) -> tuple[Any, _AttemptAuthority, list[float]]:
    authority = _AttemptAuthority(deadline)
    worker_ctx = _build_attempt_context(ctx, authority)
    worker_state = state.model_copy(deep=True)
    completed = [0.0]

    def invoke() -> NodeOutcome:
        _remaining_deadline(deadline)
        try:
            return _execute_capture_failure(node, worker_ctx, worker_state)
        finally:
            completed[0] = time.monotonic()

    context = contextvars.copy_context()
    future = get_shared_executor().submit(context.run, invoke)
    return future, authority, completed


def _thread_deadline_error(future: Any) -> NodeTimeoutError:
    cancelled = future.cancel()
    return _deadline_error("not_started" if cancelled else "external_outcome_unknown")


def _execute_with_timeout_sync(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    timeout_s: float,
    deadline_monotonic: float | None = None,
) -> NodeOutcome:
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    assert deadline is not None
    _remaining_deadline(deadline)
    if _can_use_forked_timeout_worker():
        authority = _AttemptAuthority(deadline)
        return _execute_with_timeout_process(
            node,
            _build_attempt_context(ctx, authority),
            state.model_copy(deep=True),
            timeout_s=timeout_s,
            authority=authority,
            deadline_monotonic=deadline,
        )

    future, authority, completed = _submit_thread_attempt(node, ctx, state, deadline)
    try:
        done, _ = wait([future], timeout=_remaining_deadline(deadline))
        if not done or completed[0] > deadline:
            raise _thread_deadline_error(future)
        # Retrieve outside timeout handling: provider TimeoutError keeps its category.
        return future.result()
    except BaseException:
        future.cancel()
        raise
    finally:
        authority.revoke()


async def _execute_with_timeout_thread_async(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    timeout_s: float,
    deadline_monotonic: float | None = None,
) -> NodeOutcome:
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    assert deadline is not None
    _remaining_deadline(deadline)
    future, authority, completed = _submit_thread_attempt(node, ctx, state, deadline)
    wrapped = asyncio.wrap_future(future)
    try:
        done, _ = await asyncio.wait([wrapped], timeout=_remaining_deadline(deadline))
        if not done or completed[0] > deadline:
            raise _thread_deadline_error(future)
        return wrapped.result()
    except BaseException:
        # The actual concurrent Future is cancelled before handing ownership back;
        # asyncio's deferred cancellation callback cannot admit a queued late job.
        future.cancel()
        wrapped.add_done_callback(_consume_finished_task)
        raise
    finally:
        authority.revoke()


def _can_use_forked_timeout_worker() -> bool:
    try:
        return "fork" in mp.get_all_start_methods()
    except (RuntimeError, ValueError):
        return False


def _delivery_deadline(completion_time: Any = None) -> float:
    """Keep a single bounded delivery window from actual compute completion."""
    completed_at = float(completion_time.value) if completion_time is not None else time.monotonic()
    return completed_at + _PROCESS_DELIVERY_GRACE_S


def _completion_before_deadline(
    completion_time: Any,
    compute_deadline: float,
) -> bool:
    """Require an explicit worker completion mark before draining delivery."""
    if completion_time is None:
        return False
    try:
        completed_at = float(completion_time.value)
    except (AttributeError, TypeError, ValueError):
        return False
    return 0.0 < completed_at <= compute_deadline


def _owned_process_group_id(
    process: mp.Process,
    group_ready: Any,
    *,
    deadline: float,
) -> int | None:
    """Resolve a worker-owned process group without ever targeting our own.

    The worker creates its own session before executing user code.  The parent
    waits only briefly for that handshake; if it is unavailable, cleanup falls
    back to the owned ``multiprocessing.Process`` handle rather than guessing
    at a process group.  A group is accepted only when its id is the worker
    pid and it differs from the parent's group.
    """
    if group_ready is not None and not group_ready.is_set():
        remaining = max(0.0, deadline - time.monotonic())
        group_ready.wait(timeout=min(_PROCESS_GROUP_READY_S, remaining))
    if group_ready is not None and not group_ready.is_set():
        return None
    if not process.is_alive():
        return None
    try:
        process_group_id = os.getpgid(process.pid)
    except OSError:
        return None
    if process_group_id != process.pid or process_group_id == os.getpgrp():
        return None
    return process_group_id


def _owned_process_group_is_alive(process_group_id: int | None) -> bool:
    """Check only a validated non-parent process group."""
    if process_group_id is None or process_group_id <= 0:
        return False
    if process_group_id == os.getpgrp():
        return False
    try:
        os.killpg(process_group_id, 0)
    except OSError:
        return False
    return True


def _signal_owned_process_group(process_group_id: int | None, signum: int) -> None:
    """Signal an owned group, never the caller's process group."""
    if process_group_id is None or process_group_id <= 0:
        return
    if process_group_id == os.getpgrp():
        return
    try:
        os.killpg(process_group_id, signum)
    except OSError:
        return


def _wait_for_owned_process_group_exit(process_group_id: int | None) -> bool:
    """Bounded wait for descendants after the worker itself has stopped."""
    deadline = time.monotonic() + _PROCESS_CLEANUP_GRACE_S
    while _owned_process_group_is_alive(process_group_id):
        if time.monotonic() >= deadline:
            return False
        time.sleep(_PROCESS_RESULT_POLL_S)
    return True


def _terminate_owned_process(
    process: mp.Process,
    process_group_id: int | None,
    cleanup_complete: Any = None,
) -> bool:
    """Terminate one worker and any descendants in its owned process group."""
    _signal_owned_process_group(process_group_id, signal.SIGTERM)
    if process.is_alive():
        process.terminate()
    process.join(timeout=_PROCESS_CLEANUP_GRACE_S)

    if process.is_alive():
        _signal_owned_process_group(process_group_id, signal.SIGKILL)
        process.kill()
        process.join(timeout=_PROCESS_CLEANUP_GRACE_S)

    group_clean = _wait_for_owned_process_group_exit(process_group_id)
    if not group_clean:
        _signal_owned_process_group(process_group_id, signal.SIGKILL)
        group_clean = _wait_for_owned_process_group_exit(process_group_id)
    if cleanup_complete is not None:
        return not process.is_alive() and bool(cleanup_complete.value)
    if process_group_id is None:
        # A direct Process handle proves only worker termination; descendant
        # absence is not established without the owned-group handshake.
        return False
    return not process.is_alive() and group_clean


def _close_worker_process(process: mp.Process) -> None:
    """Release process resources after the owned process has stopped."""
    if process.is_alive():
        return
    if process.pid is not None:
        process.join(timeout=0.0)
    process.close()


def _close_result_queue(result_queue: Any) -> None:
    """Close the result queue after all needed bytes have been drained."""
    result_queue.close()
    result_queue.join_thread()


def _drain_result_sync(
    process: mp.Process,
    result_queue: Any,
    *,
    compute_deadline: float,
    completion_time: Any = None,
) -> tuple[str, Any]:
    """Receive a result while its producer runs, without partial-frame blocking."""
    while process.is_alive() and not _completion_before_deadline(
        completion_time,
        compute_deadline,
    ):
        remaining = compute_deadline - time.monotonic()
        if remaining <= 0:
            raise _WorkerComputeTimeout
        try:
            result = result_queue.get(timeout=min(_PROCESS_RESULT_POLL_S, remaining))
        except EOFError:
            raise _WorkerComputeTimeout from None
        except queue.Empty:
            continue
        if not _completion_before_deadline(completion_time, compute_deadline):
            raise _WorkerComputeTimeout
        return result

    if not _completion_before_deadline(completion_time, compute_deadline):
        raise _WorkerComputeTimeout

    delivery_deadline = _delivery_deadline(completion_time)
    while time.monotonic() < delivery_deadline:
        remaining = delivery_deadline - time.monotonic()
        try:
            return result_queue.get(timeout=min(_PROCESS_RESULT_POLL_S, remaining))
        except EOFError:
            raise _WorkerDeliveryTimeout from None
        except queue.Empty:
            continue
    raise _WorkerDeliveryTimeout


async def _drain_result_async(
    process: mp.Process,
    result_queue: Any,
    *,
    compute_deadline: float,
    completion_time: Any = None,
) -> tuple[str, Any]:
    """Async counterpart of :func:`_drain_result_sync`."""
    while process.is_alive() and not _completion_before_deadline(
        completion_time,
        compute_deadline,
    ):
        try:
            result = result_queue.get_nowait()
        except EOFError:
            raise _WorkerComputeTimeout from None
        except queue.Empty:
            remaining = compute_deadline - time.monotonic()
            if remaining <= 0:
                raise _WorkerComputeTimeout
            await asyncio.sleep(min(_PROCESS_RESULT_POLL_S, remaining))
        else:
            if not _completion_before_deadline(completion_time, compute_deadline):
                raise _WorkerComputeTimeout
            return result

    if not _completion_before_deadline(completion_time, compute_deadline):
        raise _WorkerComputeTimeout

    delivery_deadline = _delivery_deadline(completion_time)
    while time.monotonic() < delivery_deadline:
        try:
            return result_queue.get_nowait()
        except EOFError:
            raise _WorkerDeliveryTimeout from None
        except queue.Empty:
            remaining = delivery_deadline - time.monotonic()
            await asyncio.sleep(min(_PROCESS_RESULT_POLL_S, remaining))
    raise _WorkerDeliveryTimeout


def _join_worker_until(process: mp.Process, *, deadline: float) -> None:
    """Wait for a result-producing worker to exit before decoding it."""
    while process.is_alive():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _WorkerDeliveryTimeout
        process.join(timeout=min(_PROCESS_RESULT_POLL_S, remaining))


async def _join_worker_until_async(process: mp.Process, *, deadline: float) -> None:
    """Async wait for a result-producing worker to exit."""
    while process.is_alive():
        if deadline - time.monotonic() <= 0:
            raise _WorkerDeliveryTimeout
        process.join(timeout=0.0)
        await asyncio.sleep(min(_PROCESS_RESULT_POLL_S, max(0.0, deadline - time.monotonic())))


def _worker_timeout_error(
    timeout_s: float,
    *,
    cleanup_complete: bool,
) -> NodeTimeoutError:
    suffix = "" if cleanup_complete else "; owned process cleanup incomplete"
    return NodeTimeoutError(
        f"Node exceeded timeout of {timeout_s}s{suffix}",
        code="node.timeout",
        details={
            "execution_state": "owned_processes_reaped"
            if cleanup_complete
            else "external_outcome_unknown",
            "cleanup_complete": cleanup_complete,
        },
    )


def _execute_with_timeout_process(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    *,
    timeout_s: float,
    authority: _AttemptAuthority | None = None,
    deadline_monotonic: float | None = None,
) -> NodeOutcome:
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    authority = authority or _AttemptAuthority(deadline)
    mp_ctx = mp.get_context("fork")
    result_queue: _WorkerResultChannel | None = None
    process: Any = None
    lifecycle: _WorkerLifecycle | None = None
    try:
        result_queue = _WorkerResultChannel(mp_ctx)
        group_ready = mp_ctx.Event()
        completion_time = mp_ctx.Value("d", 0.0)
        lifecycle = _WorkerLifecycle(
            compute_deadline=deadline if deadline is not None else time.monotonic() + timeout_s,
            completion_time=completion_time,
            cleanup_complete=mp_ctx.Value("b", False),
        )
        process = mp_ctx.Process(
            target=_node_execute_supervisor,
            args=(
                node,
                ctx,
                state,
                result_queue,
                group_ready,
                completion_time,
                lifecycle.compute_deadline,
                lifecycle.cleanup_complete,
            ),
            daemon=True,
        )
        process.start()
        result_queue.close_writer()
        lifecycle.process_group_id = _owned_process_group_id(
            process,
            group_ready,
            deadline=lifecycle.compute_deadline,
        )
        status, payload = _drain_result_sync(
            process,
            result_queue,
            compute_deadline=lifecycle.compute_deadline,
            completion_time=lifecycle.completion_time,
        )
        _join_worker_until(process, deadline=_delivery_deadline(lifecycle.completion_time))
    except _WorkerComputeTimeout:
        cleanup_complete = _terminate_owned_process(
            process,
            lifecycle.process_group_id,
            lifecycle.cleanup_complete,
        )
        authority.revoke()
        raise _worker_timeout_error(
            timeout_s,
            cleanup_complete=cleanup_complete,
        ) from None
    except _WorkerDeliveryTimeout as exc:
        cleanup_complete = _terminate_owned_process(
            process,
            lifecycle.process_group_id,
            lifecycle.cleanup_complete,
        )
        authority.revoke()
        if not cleanup_complete:
            raise _worker_timeout_error(timeout_s, cleanup_complete=False) from exc
        cleanup_suffix = ""
        raise RuntimeError(
            "Node timeout worker result delivery exceeded bounded grace "
            f"(exitcode={process.exitcode}{cleanup_suffix})"
        ) from exc
    finally:
        authority.revoke()
        if process is not None:
            if process.is_alive():
                assert lifecycle is not None
                _terminate_owned_process(
                    process, lifecycle.process_group_id, lifecycle.cleanup_complete
                )
            _close_worker_process(process)
        if result_queue is not None:
            _close_result_queue(result_queue)

    if status == "ok":
        from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome

        if isinstance(payload, (bytes, bytearray, memoryview, str)) or (
            isinstance(payload, list) and all(isinstance(item, int) for item in payload)
        ):
            return deserialize_outcome(payload)
        return decode_node_outcome(payload)
    if status == "error":
        raise _worker_node_error(payload, expected_run_id=state.run_id)
    if status == "control":
        raise _worker_control_error(payload)
    if status == "cleanup_incomplete":
        raise _worker_timeout_error(timeout_s, cleanup_complete=False)
    raise RuntimeError(f"Node timeout worker returned invalid status: {status!r}")


async def _execute_with_timeout_process_async(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    *,
    timeout_s: float,
    authority: _AttemptAuthority | None = None,
    deadline_monotonic: float | None = None,
) -> NodeOutcome:
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    if authority is None:
        authority = _AttemptAuthority(deadline)
        ctx = _build_attempt_context(ctx, authority)
        state = state.model_copy(deep=True)
    mp_ctx = mp.get_context("fork")
    result_queue: _WorkerResultChannel | None = None
    process: Any = None
    lifecycle: _WorkerLifecycle | None = None
    try:
        result_queue = _WorkerResultChannel(mp_ctx)
        group_ready = mp_ctx.Event()
        completion_time = mp_ctx.Value("d", 0.0)
        lifecycle = _WorkerLifecycle(
            compute_deadline=deadline if deadline is not None else time.monotonic() + timeout_s,
            completion_time=completion_time,
            cleanup_complete=mp_ctx.Value("b", False),
        )
        process = mp_ctx.Process(
            target=_node_execute_supervisor,
            args=(
                node,
                ctx,
                state,
                result_queue,
                group_ready,
                completion_time,
                lifecycle.compute_deadline,
                lifecycle.cleanup_complete,
            ),
            daemon=True,
        )
        process.start()
        result_queue.close_writer()
        lifecycle.process_group_id = _owned_process_group_id(
            process,
            group_ready,
            deadline=lifecycle.compute_deadline,
        )
        status, payload = await _drain_result_async(
            process,
            result_queue,
            compute_deadline=lifecycle.compute_deadline,
            completion_time=lifecycle.completion_time,
        )
        await _join_worker_until_async(
            process, deadline=_delivery_deadline(lifecycle.completion_time)
        )
    except _WorkerComputeTimeout:
        cleanup_complete = _terminate_owned_process(
            process,
            lifecycle.process_group_id,
            lifecycle.cleanup_complete,
        )
        authority.revoke()
        raise _worker_timeout_error(
            timeout_s,
            cleanup_complete=cleanup_complete,
        ) from None
    except _WorkerDeliveryTimeout as exc:
        cleanup_complete = _terminate_owned_process(
            process,
            lifecycle.process_group_id,
            lifecycle.cleanup_complete,
        )
        authority.revoke()
        if not cleanup_complete:
            raise _worker_timeout_error(timeout_s, cleanup_complete=False) from exc
        cleanup_suffix = ""
        raise RuntimeError(
            "Node timeout worker result delivery exceeded bounded grace "
            f"(exitcode={process.exitcode}{cleanup_suffix})"
        ) from exc
    finally:
        authority.revoke()
        if process is not None:
            if process.is_alive():
                assert lifecycle is not None
                _terminate_owned_process(
                    process, lifecycle.process_group_id, lifecycle.cleanup_complete
                )
            _close_worker_process(process)
        if result_queue is not None:
            _close_result_queue(result_queue)

    if status == "ok":
        from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome

        if isinstance(payload, (bytes, bytearray, memoryview, str)) or (
            isinstance(payload, list) and all(isinstance(item, int) for item in payload)
        ):
            return deserialize_outcome(payload)
        return decode_node_outcome(payload)
    if status == "error":
        raise _worker_node_error(payload, expected_run_id=state.run_id)
    if status == "control":
        raise _worker_control_error(payload)
    if status == "cleanup_incomplete":
        raise _worker_timeout_error(timeout_s, cleanup_complete=False)
    raise RuntimeError(f"Node timeout worker returned invalid status: {status!r}")


def _consume_finished_task(task: asyncio.Future[Any]) -> None:
    """Consume a detached attempt result so timeout cleanup is observable only once."""
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


async def _execute_with_timeout_async(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    timeout_s: float,
    deadline_monotonic: float | None = None,
) -> NodeOutcome:
    """Wait for completion without confusing a provider exception with expiry."""
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    assert deadline is not None
    authority = _AttemptAuthority(deadline)
    worker_ctx = _build_attempt_context(ctx, authority)
    worker_state = state.model_copy(deep=True)
    completed = [0.0]

    async def invoke() -> NodeOutcome:
        _remaining_deadline(deadline)
        before = _spend_snapshot(worker_state)
        try:
            return await node.execute_async(worker_ctx, worker_state)
        except _RETRY_RUNTIME_ERRORS as exc:
            raise _CompletedAttemptError(
                exc, _spend_changes(before, _spend_snapshot(worker_state))
            ) from exc
        finally:
            completed[0] = time.monotonic()

    task = asyncio.create_task(invoke())
    try:
        done, _ = await asyncio.wait([task], timeout=_remaining_deadline(deadline))
        if not done or completed[0] > deadline:
            raise _deadline_error(
                "running_external_outcome_unknown" if not done else "completed_after_deadline"
            )
        return task.result()
    except BaseException:
        task.add_done_callback(_consume_finished_task)
        raise
    finally:
        authority.revoke()


def _node_execute_worker(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    result_queue: Any,
    group_ready: Any = None,
    completion_time: Any = None,
) -> None:
    if group_ready is not None:
        try:
            os.setsid()
        except OSError:
            # Parent-side validation refuses to target an unowned group.
            pass
        finally:
            group_ready.set()

    def _send(status: str, payload: Any) -> None:
        try:
            result_queue.put((status, payload))
        except _RETRY_RUNTIME_ERRORS as send_exc:
            try:
                result_queue.put(
                    (
                        "error",
                        f"failed to send result: {type(send_exc).__name__}: {send_exc}",
                    )
                )
            except _RETRY_RUNTIME_ERRORS as fallback_exc:
                raise RuntimeError(
                    f"failed to send result: {type(send_exc).__name__}: {send_exc}"
                ) from fallback_exc

    def _mark_completion() -> None:
        if completion_time is not None:
            completion_time.value = time.monotonic()

    before_spend = _spend_snapshot(state)
    try:
        outcome = node.execute(ctx, state)
        _mark_completion()
        if isinstance(outcome, NodeOutcome):
            from polisyos.scientist.orchestration.engine.runner.serialization import (
                serialize_outcome,
            )

            _send("ok", serialize_outcome(outcome))
        elif hasattr(outcome, "model_dump"):
            # Preserve the established diagnostic when an attempted model dump
            # itself fails; the parent still validates the returned wire type.
            _send("ok", outcome.model_dump(mode="python"))
        else:
            _send(
                "error",
                _worker_error_payload(
                    ValueError(f"invalid node outcome: {type(outcome).__name__}")
                ),
            )
    except _RETRY_RUNTIME_ERRORS as exc:
        _mark_completion()
        _send(
            "error",
            _worker_error_payload(
                exc,
                known_spend=_spend_changes(before_spend, _spend_snapshot(state)),
                run_id=state.run_id,
            ),
        )


async def execute_with_retry_async(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    retry_policy: RetryPolicy,
    timeout_s: float | None,
    alias: str,
    circuit_breaker: CircuitBreaker | None = None,
    retry_stats: dict[str, int] | None = None,
    liveness_config: BoundedLivenessConfig | Mapping[str, Any] | None = None,
    deadline_monotonic: float | None = None,
) -> NodeOutcome:
    """Async retry wrapper for ``AsyncWorkflowExecutor``.

    One monotonic deadline covers admission, attempts, backoff and publication.
    Provider TimeoutError retains its category; owner expiry is terminal.
    An unconfigured sync bridge explicitly opts into unbounded execution.
    """
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    _remaining_deadline(deadline)
    retry_policy = _apply_bounded_liveness_retry_ceiling(
        alias=alias,
        retry_policy=retry_policy,
        liveness_config=liveness_config,
    )
    # Detect real execute_async (not MagicMock auto-generated attributes).
    # Check the class dict to avoid MagicMock's __getattr__ false positives.
    _has_async = "execute_async" in type(node).__dict__ or (
        hasattr(node, "__class__")
        and any("execute_async" in getattr(klass, "__dict__", {}) for klass in type(node).__mro__)
    )

    async def _invoke(attempt_state: ExperimentState) -> NodeOutcome:
        remaining = _remaining_deadline(deadline)
        if _has_async:
            if remaining is None:
                return await node.execute_async(ctx, attempt_state)
            return await _execute_with_timeout_async(
                node,
                ctx,
                attempt_state,
                timeout_s=remaining,
                deadline_monotonic=deadline,
            )
        if remaining is not None:
            if _can_use_forked_timeout_worker():
                return await _execute_with_timeout_process_async(
                    node,
                    ctx,
                    attempt_state,
                    timeout_s=remaining,
                    deadline_monotonic=deadline,
                )
            return await _execute_with_timeout_thread_async(
                node,
                ctx,
                attempt_state,
                timeout_s=remaining,
                deadline_monotonic=deadline,
            )
        authority = _AttemptAuthority()
        worker_ctx = _build_attempt_context(ctx, authority)
        worker_state = attempt_state.model_copy(deep=True)
        try:
            return await run_blocking_async(
                _execute_capture_failure, node, worker_ctx, worker_state, unbounded=True
            )
        finally:
            authority.revoke()

    # Fast path
    if retry_policy.max_retries == 0 and deadline is None and circuit_breaker is None:
        if retry_stats is not None:
            retry_stats["attempts"] = 1
        try:
            return await _invoke(state)
        except _CompletedAttemptError as exc:
            _merge_spend(state, exc.known_spend)
            raise exc.error from None

    last_outcome: NodeOutcome | None = None
    failed_spend: dict[str, Decimal] = {}
    node_id = str((getattr(node, "spec", None) and node.spec.metadata.component_id) or alias)

    for attempt in range(retry_policy.max_retries + 1):
        try:
            remaining = _remaining_deadline(deadline)
        except NodeTimeoutError:
            _merge_spend(state, failed_spend)
            raise
        # Circuit breaker check
        if circuit_breaker is not None and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open for node {alias}",
            )

        attempt_state = _fresh_retry_state(state, node) if retry_policy.max_retries > 0 else state
        try:
            outcome = await _invoke(attempt_state)

            try:
                _remaining_deadline(deadline, execution_state="completed_publication_rejected")
            except NodeTimeoutError:
                _accumulate_spend(failed_spend, _spend_delta(state, outcome.state))
                raise
            if outcome.status != "fail":
                _merge_spend(outcome.state, failed_spend)
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
                if retry_stats is not None:
                    retry_stats["attempts"] = attempt + 1
                return outcome

            if circuit_breaker is not None:
                circuit_breaker.record_failure()

            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                attempt_spend = _spend_delta(state, outcome.state)
                _accumulate_spend(failed_spend, attempt_spend)
                last_outcome = outcome
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s (attempt %d/%d) after %.1fs",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    delay,
                )
                _emit_retry_event(
                    ctx,
                    alias,
                    attempt=attempt + 1,
                    delay=delay,
                    spend=attempt_spend,
                )
                await _retry_delay_async(delay, deadline)
                continue

            if retry_stats is not None:
                retry_stats["attempts"] = attempt + 1
            _merge_spend(outcome.state, failed_spend)
            return outcome

        except NodeTimeoutError:
            _merge_spend(state, failed_spend)
            raise
        except CircuitBreakerOpenError:
            raise
        except asyncio.CancelledError:
            _logger.info("Node %s cancelled during attempt %d", alias, attempt)
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            original_error = exc.error if isinstance(exc, _CompletedAttemptError) else exc
            captured_spend = (
                exc.known_spend
                if isinstance(exc, (_CompletedAttemptError, _WorkerNodeError))
                else None
            )
            attempt_spend = (
                captured_spend if captured_spend is not None else _spend_delta(state, attempt_state)
            )
            _accumulate_spend(failed_spend, attempt_spend)
            try:
                _remaining_deadline(
                    deadline, execution_state="completed_error_publication_rejected"
                )
            except NodeTimeoutError:
                _merge_spend(state, failed_spend)
                raise
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            if attempt < retry_policy.max_retries and _should_retry_exception(
                exc,
                retry_policy,
            ):
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s after exception (attempt %d/%d): %s",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    exc,
                )
                _emit_retry_event(
                    ctx,
                    alias,
                    attempt=attempt + 1,
                    delay=delay,
                    spend=attempt_spend,
                )
                try:
                    await _retry_delay_async(delay, deadline)
                except NodeTimeoutError:
                    _merge_spend(state, failed_spend)
                    raise
                continue

            if retry_stats is not None:
                retry_stats["attempts"] = attempt + 1
            _merge_spend(state, failed_spend)
            dlq_ref = _persist_dead_letter(
                ctx,
                alias,
                node_id,
                original_error,
                attempts=attempt + 1,
                policy=retry_policy,
            )
            if dlq_ref is not None:
                _emit_dead_letter_event(
                    ctx,
                    alias,
                    attempt=attempt + 1,
                    output=dlq_ref,
                    spend=failed_spend,
                )
            raise RetryExhaustedError(
                f"Node {alias}: all {retry_policy.max_retries} retries exhausted",
            ) from original_error

    if last_outcome is not None:  # pragma: no cover
        return last_outcome
    raise RetryExhaustedError(  # pragma: no cover
        f"Node {alias}: all retries exhausted",
    )
