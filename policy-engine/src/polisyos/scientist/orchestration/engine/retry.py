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
import hashlib
import inspect
import json
import logging
import multiprocessing as mp
import os
import queue
import random
import secrets
import signal
import sys
import threading
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from concurrent.futures import wait
from datetime import UTC, date, datetime, timedelta
from datetime import time as _time_type
from decimal import Decimal, InvalidOperation
from functools import wraps
from types import GetSetDescriptorType, SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.async_tools import get_shared_executor, run_blocking_async
from polisyos.common.canonical import _admit_canon_spec
from polisyos.common.job_execution_interrupt import (
    JobExecutionInterrupted,
    raise_if_job_execution_interrupted,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, CanonViolation
from polisyos.core.contracts import (
    BoundedLivenessConfig,
    bounded_liveness_config_from_mapping,
)
from polisyos.core.run.child_custody import ChildComputationOutcomeUnknown
from polisyos.core.run.context import RunContext as _RunContext
from polisyos.ir.artifacts.contracts import _register_trusted_artifact_ref_facade
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
    from multiprocessing.context import BaseContext

    from polisyos.core.run.worker_lifecycle import (
        WorkerDispatchBinding,
        WorkerLifecycleCapability,
    )
    from polisyos.scientist.orchestration.engine.circuit_breaker import CircuitBreaker
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

_logger = logging.getLogger(__name__)


@runtime_checkable
class _ContextWithProcessFactory(Protocol):
    """The concrete multiprocessing contexts expose their Process constructor."""

    Process: Callable[..., mp.Process]


def _process_factory(context: BaseContext) -> Callable[..., mp.Process]:
    """Admit a supported context only when its Process factory is callable."""
    if not isinstance(context, _ContextWithProcessFactory):
        raise _timeout_worker_unsupported("process_context_process_factory_unavailable")
    process_factory = context.Process
    if not callable(process_factory):
        raise _timeout_worker_unsupported("process_context_process_factory_unavailable")
    return process_factory


# Node computation has one deadline; framed result delivery has one finite
# window from the actual completion mark. Parent and supervisor drain while
# their producer runs. No Queue feeder or blocking partial-frame read can
# silently extend that window.
_PROCESS_RESULT_POLL_S = 0.01
_PROCESS_GROUP_READY_S = 0.05
_PROCESS_DELIVERY_GRACE_S = 1.0
_PROCESS_CLEANUP_GRACE_S = 1.0
# The spawn timeout wire is intentionally enabled only for the builtin node
# whose real producer/consumer replay and timeout boundary are covered here.
# Adding another node requires its own closed-context and cleanup controls.
_SPAWN_TIMEOUT_TRANSPORTABILITY_NODE_ID = "scientist.node_run_transportability@1.0.0"
_SPAWN_TIMEOUT_NODE_IDS = frozenset(
    {"scientist.node_resolve_parameters@1.0.0", _SPAWN_TIMEOUT_TRANSPORTABILITY_NODE_ID}
)


@dataclasses.dataclass(frozen=True)
class _ForkWorkerReceiptBinding:
    """Parent-issued identity for one inherited-node Linux fork dispatch."""

    capability: WorkerLifecycleCapability
    binding: WorkerDispatchBinding

    @property
    def invocation_id(self) -> str:
        return self.binding.invocation_id

    @property
    def dispatch_sha256(self) -> str:
        return self.binding.dispatch_sha256

    @property
    def owner_snapshot_ref(self) -> ArtifactRef:
        return self.binding.owner_snapshot_ref

    @property
    def run_id(self) -> str:
        return self.binding.run_id


class _WorkerComputeTimeout(Exception):
    """The worker did not finish computation before the node deadline."""


class _WorkerProcessExited(RuntimeError):
    """The worker exited without publishing a completion mark."""

    def __init__(self, exitcode: int | None) -> None:
        super().__init__(f"timeout worker exited before completion (exitcode={exitcode})")
        self.exitcode = exitcode


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
            if not isinstance(wire, dict) or wire.get("encoding") not in {
                "bytes",
                "json",
            }:
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
    except OSError, ValueError, IndexError:
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
    worker_binding: _ForkWorkerReceiptBinding | None = None,
) -> None:
    """Own one real node process and reap it before exposing its result."""
    result_channel.close_reader()
    if sys.platform != "linux":
        # The established group boundary remains available; native non-Linux
        # descendant reaping is not established by this Linux supervisor.
        _node_execute_worker(
            node,
            ctx,
            state,
            result_channel,
            group_ready,
            completion_time,
            worker_binding=worker_binding,
        )
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
                    _node_execute_worker(
                        node,
                        ctx,
                        state,
                        child_channel,
                        None,
                        completion_time,
                        worker_binding=worker_binding,
                    )
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


class _InvocationAttemptPersistenceError(RuntimeError):
    """An engine-owned attempt basis/outcome could not be persisted."""


def _begin_invocation_attempt(
    callback: Callable[[int, ExperimentState], str] | None,
    *,
    attempt_number: int,
    state: ExperimentState,
) -> str | None:
    """Persist an exact attempt input before calling the node implementation."""
    if callback is None:
        return None
    try:
        attempt_id = callback(attempt_number, state)
    except Exception as exc:
        raise _InvocationAttemptPersistenceError(
            "run_invocation_attempt_start_persistence_failed"
        ) from exc
    if not isinstance(attempt_id, str) or not attempt_id:
        raise _InvocationAttemptPersistenceError("run_invocation_attempt_id_invalid")
    return attempt_id


def _attempt_context_for_engine_attempt(
    ctx: ExecutionContext,
    attempt_id: str | None,
    callback: Callable[[str], ExecutionContext] | None,
) -> ExecutionContext:
    """Bind a node context to the exact owner attempt before producer code runs."""
    if callback is None:
        return ctx
    if attempt_id is None:
        raise _InvocationAttemptPersistenceError("run_invocation_attempt_context_id_missing")
    try:
        attempt_context = callback(attempt_id)
    except Exception as exc:
        raise _InvocationAttemptPersistenceError(
            "run_invocation_attempt_context_binding_failed"
        ) from exc
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext as ContextType,
    )

    if not isinstance(attempt_context, ContextType):
        raise _InvocationAttemptPersistenceError("run_invocation_attempt_context_type_invalid")
    return attempt_context


def _finish_invocation_attempt(
    callback: Callable[[str, NodeOutcome | None], None] | None,
    *,
    attempt_id: str | None,
    outcome: NodeOutcome | None,
) -> None:
    """Persist one returned outcome or an explicitly unknown execution result."""
    if callback is None or attempt_id is None:
        return
    try:
        callback(attempt_id, outcome)
    except Exception as exc:
        raise _InvocationAttemptPersistenceError(
            "run_invocation_attempt_outcome_persistence_failed"
        ) from exc


async def _begin_invocation_attempt_async(
    callback: Callable[[int, ExperimentState], Awaitable[str]] | None,
    *,
    attempt_number: int,
    state: ExperimentState,
) -> str | None:
    """Persist an exact async attempt input before calling the node implementation."""
    if callback is None:
        return None
    try:
        attempt_id = await callback(attempt_number, state)
    except Exception as exc:
        raise _InvocationAttemptPersistenceError(
            "run_invocation_attempt_start_persistence_failed"
        ) from exc
    if not isinstance(attempt_id, str) or not attempt_id:
        raise _InvocationAttemptPersistenceError("run_invocation_attempt_id_invalid")
    return attempt_id


async def _finish_invocation_attempt_async(
    callback: Callable[[str, NodeOutcome | None], Awaitable[None]] | None,
    *,
    attempt_id: str | None,
    outcome: NodeOutcome | None,
) -> None:
    """Persist one async outcome or an explicitly unknown execution result."""
    if callback is None or attempt_id is None:
        return
    try:
        await callback(attempt_id, outcome)
    except Exception as exc:
        raise _InvocationAttemptPersistenceError(
            "run_invocation_attempt_outcome_persistence_failed"
        ) from exc


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
        "suspend_for_resume",
        "update_manifest",
    }
)
_TRACE_WRITE_METHODS = frozenset({"emit", "emit_many", "close"})
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
_ATTEMPT_CONTEXT_FACADE_FIELDS = frozenset({"store", "run", "audit", "claim_ledger_owner"})
_ATTEMPT_RUN_FACADE_FIELDS = frozenset({"store", "run_manifest", "trace", "_audit_sink"})


class _AttemptWriteDeniedError(RuntimeError):
    """Identify a persistent write refused after attempt authority expires."""

    code = "attempt_write_revoked"
    reason_code = "attempt_write_revoked"

    def __init__(self) -> None:
        super().__init__(self.reason_code)


class _AttemptAuthority:
    """Serialize attempt-owned writes and revoke them after a timeout.

    The lock is deliberately shared by every facade for one attempt. A write
    that has acquired it is linearized before ``revoke``; every later write is
    denied. This is a local authority boundary, not a process sandbox.
    """

    def __init__(
        self,
        deadline_monotonic: float | None = None,
        *,
        shared_active: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        self._active = True
        self._deadline = deadline_monotonic
        self._shared_active = shared_active

    def _is_active_locked(self) -> bool:
        active = self._active if self._shared_active is None else bool(self._shared_active.value)
        return active and (self._deadline is None or time.monotonic() < self._deadline)

    def invoke(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a best-effort operation; revoked non-persistent writes are no-ops."""
        with self._lock:
            if not self._is_active_locked():
                return None
            return operation(*args, **kwargs)

    def invoke_persistent_write(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a CAS persistence operation or raise a typed revocation refusal."""
        with self._lock:
            if not self._is_active_locked():
                raise _AttemptWriteDeniedError()
            return operation(*args, **kwargs)

    def revoke(self) -> None:
        """Make all subsequent attempt-owned writes no-ops."""
        with self._lock:
            if self._shared_active is None:
                self._active = False
            else:
                self._shared_active.value = False


def _new_attempt_authority(
    deadline_monotonic: float | None,
    *,
    process_context: BaseContext | None = None,
) -> _AttemptAuthority:
    """Create a local or process-shared attempt authority for one invocation."""
    if process_context is None:
        return _AttemptAuthority(deadline_monotonic)
    return _AttemptAuthority(
        deadline_monotonic,
        shared_active=process_context.Value("b", True, lock=False),
    )


def _has_selected_profile_writer_api(operation: Any) -> bool:
    """Check the wrapped call shape needed to forward Core's selected-profile keyword.

    This is only an API-routing check. The producer must still validate the
    writer's returned ArtifactRef and the consumer must verify the persisted view.
    """
    if not callable(operation):
        return False
    try:
        parameter = inspect.signature(operation).parameters.get("return_selected_profile")
    except TypeError, ValueError:
        return False
    return parameter is not None and parameter.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )


class _AttemptFacade:
    """Delegate reads while gating the named mutating methods."""

    def __init__(
        self,
        target: Any,
        authority: _AttemptAuthority,
        *,
        write_methods: frozenset[str],
        raise_on_revoked_write: bool = False,
    ) -> None:
        self._target = target
        self._authority = authority
        self._write_methods = write_methods
        self._raise_on_revoked_write = raise_on_revoked_write
        # Preserve the named Core API only when the target can receive it. This
        # does not prove the target honors the option; selected refs are checked
        # at the producer/consumer boundary.
        for name in ("put_bytes", "put_json"):
            operation = getattr(target, name, None)
            if not _has_selected_profile_writer_api(operation):
                setattr(self, name, self.__getattr__(name) if callable(operation) else None)

    def _invoke_store_write(self, name: str, *args: Any, **kwargs: Any) -> object:
        default_spec: CanonSpec | None = None
        if name == "put_json":
            # Admit before consulting the wrapped operation: even its attribute
            # access may be a callback that mutates the caller's original spec.
            if len(args) > 2:
                selected = _admit_canon_spec(
                    args[2], CanonSpec, violation_type=CanonViolation, artifact_writer=True
                )
                args = (*args[:2], selected, *args[3:])
            if "canon_spec" in kwargs:
                kwargs["canon_spec"] = _admit_canon_spec(
                    kwargs["canon_spec"],
                    CanonSpec,
                    violation_type=CanonViolation,
                    artifact_writer=True,
                )
            if len(args) <= 2 and "canon_spec" not in kwargs:
                default_spec = _admit_canon_spec(
                    None, CanonSpec, violation_type=CanonViolation, artifact_writer=True
                )
        operation = getattr(self._target, name)
        if default_spec is not None:
            try:
                parameter = inspect.signature(operation).parameters.get("canon_spec")
            except (TypeError, ValueError):
                parameter = None
            if parameter is not None and parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                kwargs["canon_spec"] = default_spec
            elif (
                parameter is not None
                and parameter.kind is inspect.Parameter.POSITIONAL_ONLY
                and len(args) == 2
            ):
                args = (*args, default_spec)
        if name not in self._write_methods:
            return operation(*args, **kwargs)
        invoke = (
            self._authority.invoke_persistent_write
            if self._raise_on_revoked_write
            else self._authority.invoke
        )
        result: object = invoke(
            operation,
            *(_unwrap_manifest_value(arg) for arg in args),
            **{key: _unwrap_manifest_value(item) for key, item in kwargs.items()},
        )
        return result

    def put_bytes(
        self,
        data: bytes,
        opts: PutOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        """Write bytes through the attempt gate with the Core writer signature."""
        call_options: dict[str, Any] = {}
        if return_selected_profile is not False:
            call_options["return_selected_profile"] = return_selected_profile
        return _require_artifact_ref(
            self._invoke_store_write("put_bytes", data, opts, **call_options)
        )

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: Any = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        """Write JSON through the attempt gate with the Core writer signature."""
        args: tuple[Any, ...] = (obj, opts)
        if canon_spec is not None:
            args += (canon_spec,)
        call_options: dict[str, Any] = {}
        if return_selected_profile is not False:
            call_options["return_selected_profile"] = return_selected_profile
        return _require_artifact_ref(self._invoke_store_write("put_json", *args, **call_options))

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._target, name)
        if callable(value) and name == "put_json":
            # The constructor uses this path for legacy writer signatures.
            # Preserve signature inspection while routing through the same
            # spec admission as the named selected-profile method.
            @wraps(value)
            def put_json_with_admission(*args: Any, **kwargs: Any) -> object:
                return self._invoke_store_write(name, *args, **kwargs)

            return put_json_with_admission
        if callable(value) and name in self._write_methods:
            invoke = (
                self._authority.invoke_persistent_write
                if self._raise_on_revoked_write
                else self._authority.invoke
            )
            return lambda *args, **kwargs: invoke(
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

    def __iter__(self) -> Iterator[object]:
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

    @__class__.setter
    def __class__(self, value: object) -> None:
        del value
        raise AttributeError("attempt model facade class is read-only")

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


_register_trusted_artifact_ref_facade(_AttemptModelFacade, _unwrap_manifest_value)
_register_trusted_artifact_ref_facade(_AttemptManifestFacade, _unwrap_manifest_value)


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
            try:
                sink = getattr(target, name)
            except AttributeError:
                continue
            wrapped_sink = (
                _AttemptFacade(
                    sink,
                    self._authority,
                    write_methods=_TRACE_WRITE_METHODS,
                )
                if sink is not None
                else None
            )
            object.__setattr__(self, name, wrapped_sink)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _ATTEMPT_RUN_FACADE_FIELDS and "_target" in self.__dict__:
            raise AttributeError("timed run facade fields cannot be rebound")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in _ATTEMPT_RUN_FACADE_FIELDS and "_target" in self.__dict__:
            raise AttributeError("timed run facade fields cannot be removed")
        object.__delattr__(self, name)

    def __getattr__(self, name: str) -> Any:
        if name in _ATTEMPT_RUN_FACADE_FIELDS:
            try:
                target_value = getattr(self._target, name)
            except AttributeError:
                raise AttributeError(
                    f"protected timed run facade field {name!r} is unavailable"
                ) from None
            if target_value is None:
                return None
            raise AttributeError(f"protected timed run facade field {name!r} is unavailable")
        return super().__getattr__(name)


_MAX_EXACT_WORKER_RUN_FACADE_DEPTH = 8


def _resolve_exact_worker_run_view(value: Any) -> Any | None:
    """Find a worker run view only through bounded engine-owned attempt facades.

    The returned leaf is for identity and capability recognition only. Callers
    retain the original outer facade for every write so each attempt authority
    continues to gate staged receipts.
    """
    from polisyos.core.run.worker_lifecycle import WorkerRunView

    current = value
    seen: set[int] = set()
    depth = 0
    while True:
        if type(current) is WorkerRunView:
            return current
        if type(current) is not _AttemptRunFacade or id(current) in seen:
            return None
        seen.add(id(current))
        depth += 1
        if depth > _MAX_EXACT_WORKER_RUN_FACADE_DEPTH:
            return None
        current = object.__getattribute__(current, "_target")


_MANIFEST_SNAPSHOT_SCALAR_TYPES = (
    str,
    bytes,
    bool,
    int,
    float,
    type(None),
    date,
    datetime,
    _time_type,
    timedelta,
    Decimal,
)
_MANIFEST_SNAPSHOT_KEY_TYPES = (str, bytes, bool, int, float, type(None))


def _snapshot_manifest_value(
    value: Any,
    *,
    _memo: dict[int, Any] | None = None,
    _active: set[int] | None = None,
) -> Any:
    # Copy only known immutable values and exact builtin data containers.
    value_type = type(value)
    if any(value_type is scalar_type for scalar_type in _MANIFEST_SNAPSHOT_SCALAR_TYPES):
        return value
    if type(value) is bytearray:
        return bytearray(value)

    memo = {} if _memo is None else _memo
    active = set() if _active is None else _active
    identity = id(value)
    if identity in active:
        raise TypeError("run_manifest_snapshot_cycle")
    if identity in memo:
        return memo[identity]

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import EnvInfo, GitInfo, ProducerInfo
    from polisyos.core.components import ComponentId
    from polisyos.core.run.manifest import RunManifest

    model_type = type(value)
    owned_model_types = (
        ArtifactID,
        ArtifactRef,
        ComponentId,
        EnvInfo,
        GitInfo,
        ProducerInfo,
        RunManifest,
    )
    if any(model_type is owned_type for owned_type in owned_model_types):
        active.add(identity)
        try:
            raw_fields = object.__getattribute__(value, "__dict__")
            expected_fields = model_type.model_fields
            if (
                type(raw_fields) is not dict
                or any(type(name) is not str for name in raw_fields)
                or set(raw_fields) != set(expected_fields)
            ):
                raise TypeError("run_manifest_snapshot_model_fields_invalid")
            if (
                object.__getattribute__(value, "__pydantic_extra__") is not None
                or object.__getattribute__(value, "__pydantic_private__") is not None
            ):
                raise TypeError("run_manifest_snapshot_model_private_state_unsupported")

            fields = {
                name: _snapshot_manifest_value(item, _memo=memo, _active=active)
                for name, item in raw_fields.items()
            }
            raw_fields_set = object.__getattribute__(value, "__pydantic_fields_set__")
            if type(raw_fields_set) is not set or any(
                type(name) is not str or name not in expected_fields for name in raw_fields_set
            ):
                raise TypeError("run_manifest_snapshot_model_fields_set_invalid")
            fields_set = _snapshot_manifest_value(raw_fields_set, _memo=memo, _active=active)
            if model_type is ArtifactID or model_type is ComponentId:
                if set(fields) != {"root"}:
                    raise TypeError("run_manifest_snapshot_root_model_invalid")
                detached_model = model_type.model_validate(fields["root"])
            else:
                detached_model = model_type.model_validate(fields)
            if type(detached_model) is not model_type:
                raise TypeError("run_manifest_snapshot_model_type_changed")
            object.__setattr__(detached_model, "__pydantic_fields_set__", fields_set)
            memo[identity] = detached_model
            return detached_model
        finally:
            active.remove(identity)

    # Unknown metaclasses may execute hooks during ordinary class-namespace
    # access. Owned Pydantic models were handled above by exact type identity.
    if type(model_type) is not type:
        raise TypeError("run_manifest_snapshot_model_type_unsupported")

    if type(value) is list:
        active.add(identity)
        detached: list[Any] = []
        memo[identity] = detached
        try:
            detached.extend(
                _snapshot_manifest_value(item, _memo=memo, _active=active) for item in value
            )
            return detached
        finally:
            active.remove(identity)
    if type(value) is dict:
        active.add(identity)
        detached_dict: dict[Any, Any] = {}
        memo[identity] = detached_dict
        try:
            for key, item in value.items():
                key_type = type(key)
                if not any(
                    key_type is allowed_type for allowed_type in _MANIFEST_SNAPSHOT_KEY_TYPES
                ):
                    raise TypeError("run_manifest_snapshot_key_unsupported")
                detached_dict[key] = _snapshot_manifest_value(item, _memo=memo, _active=active)
            return detached_dict
        finally:
            active.remove(identity)
    if type(value) is set:
        active.add(identity)
        detached_set: set[Any] = set()
        memo[identity] = detached_set
        try:
            detached_set.update(
                _snapshot_manifest_value(item, _memo=memo, _active=active) for item in value
            )
            return detached_set
        finally:
            active.remove(identity)
    if type(value) is frozenset:
        active.add(identity)
        try:
            detached_frozen = frozenset(
                _snapshot_manifest_value(item, _memo=memo, _active=active) for item in value
            )
            memo[identity] = detached_frozen
            return detached_frozen
        finally:
            active.remove(identity)
    if type(value) is tuple:
        active.add(identity)
        try:
            detached_tuple = tuple(
                _snapshot_manifest_value(item, _memo=memo, _active=active) for item in value
            )
            memo[identity] = detached_tuple
            return detached_tuple
        finally:
            active.remove(identity)

    if type(value) is SimpleNamespace:
        fields = object.__getattribute__(value, "__dict__")
        if type(fields) is not dict:
            raise TypeError("run_manifest_snapshot_namespace_invalid")
        active.add(identity)
        detached_namespace = SimpleNamespace()
        memo[identity] = detached_namespace
        try:
            copied_fields = object.__getattribute__(detached_namespace, "__dict__")
            for name, item in fields.items():
                if type(name) is not str:
                    raise TypeError("run_manifest_snapshot_field_name_invalid")
                copied_fields[name] = _snapshot_manifest_value(item, _memo=memo, _active=active)
            return detached_namespace
        finally:
            active.remove(identity)

    record_type = model_type
    record_mro = type.__getattribute__(record_type, "__mro__")
    record_namespace = type.__getattribute__(record_type, "__dict__")
    if (
        len(record_mro) != 2
        or record_mro[0] is not record_type
        or record_mro[1] is not object
        or "__slots__" in record_namespace
        or any(
            name in record_namespace
            for name in (
                "__getattribute__",
                "__getattr__",
                "__setattr__",
                "__delattr__",
                "__new__",
                "__deepcopy__",
                "__reduce__",
                "__reduce_ex__",
            )
        )
    ):
        raise TypeError("run_manifest_snapshot_record_type_unsupported")
    metadata_names = {
        "__module__",
        "__firstlineno__",
        "__static_attributes__",
        "__qualname__",
        "__doc__",
        "__dict__",
        "__weakref__",
        "__annotations__",
        "__classcell__",
    }
    if any(
        name not in metadata_names and name.startswith("__") and name.endswith("__")
        for name in record_namespace
    ):
        raise TypeError("run_manifest_snapshot_record_type_unsupported")
    storage_descriptor = record_namespace.get("__dict__")
    if (
        type(storage_descriptor) is not GetSetDescriptorType
        or object.__getattribute__(storage_descriptor, "__objclass__") is not record_type
    ):
        raise TypeError("run_manifest_snapshot_record_storage_unsupported")
    instance_fields = object.__getattribute__(value, "__dict__")
    if type(instance_fields) is not dict:
        raise TypeError("run_manifest_snapshot_record_state_unsupported")
    fields = {
        name: item
        for name, item in record_namespace.items()
        if not (name.startswith("__") and name.endswith("__"))
    }
    for item in fields.values():
        item_type = type(item)
        if type(item_type) is not type:
            raise TypeError("run_manifest_snapshot_record_type_unsupported")
        item_namespace = type.__getattribute__(item_type, "__dict__")
        if any(name in item_namespace for name in ("__get__", "__set__", "__delete__")):
            raise TypeError("run_manifest_snapshot_record_descriptor_unsupported")
    if any(callable(item) for item in fields.values()):
        raise TypeError("run_manifest_snapshot_record_hook_unsupported")
    fields.update(instance_fields)

    active.add(identity)
    try:
        detached_record = object.__new__(record_type)
        memo[identity] = detached_record
        for name, item in fields.items():
            if type(name) is not str:
                raise TypeError("run_manifest_snapshot_field_name_invalid")
            object.__setattr__(
                detached_record,
                name,
                _snapshot_manifest_value(item, _memo=memo, _active=active),
            )
        return detached_record
    except TypeError:
        memo.pop(identity, None)
        raise
    finally:
        active.remove(identity)


def _snapshot_attempt_manifest_value(value: Any) -> Any:
    """Snapshot a manifest after peeling bounded exact attempt wrappers for reading.

    Write-side argument unwrapping remains one-layer and authority-gated. This
    reader recognizes only the engine's exact manifest facade and detaches the
    underlying value through the strict callback-free snapshotter.
    """
    seen: set[int] = set()
    depth = 0
    while type(value) is _AttemptManifestFacade:
        identity = id(value)
        if identity in seen:
            raise TypeError("run_manifest_snapshot_attempt_facade_cycle")
        seen.add(identity)
        depth += 1
        if depth > _MAX_EXACT_WORKER_RUN_FACADE_DEPTH:
            raise TypeError("run_manifest_snapshot_attempt_facade_depth_exceeded")
        value = object.__getattribute__(value, "_target")
    return _snapshot_manifest_value(value)


_ENGINE_NODE_RUN_VIEW_TOKEN = object()


class _EngineNodeRunView(_RunContext):
    """RunContext view with narrow staged receipt writes for worker attempts."""

    __slots__ = ("__stage_worker_receipt_writes", "__target")
    _STAGED_WORKER_WRITE_METHODS = frozenset({"add_input", "add_output"})
    _READ_FIELDS = frozenset(
        {
            "access_scope",
            "cell_id",
            "dispatch_binding",
            "store",
            "tenant_id",
            "trace_path",
        }
    )
    _READ_METHODS = frozenset(
        {
            "read_runtime_invocation_attempts",
            "read_runtime_owner_output_refs",
            "read_runtime_workflow_finalization_ref",
            "artifact_tenant_context",
        }
    )
    _LOCAL_METHODS = frozenset(
        {
            "__class__",
            "__delattr__",
            "__getattribute__",
            "__init__",
            "__repr__",
            "__setattr__",
            "emit",
            "read_runtime_invocation_attempts",
            "read_runtime_owner_output_refs",
            "read_runtime_workflow_finalization_ref",
            "update_manifest",
        }
    )

    def __init__(
        self,
        target: Any,
        *,
        _token: object,
        stage_worker_receipt_writes: bool = False,
    ) -> None:
        if _token is not _ENGINE_NODE_RUN_VIEW_TOKEN:
            raise TypeError("engine node run views are created by the executor")
        if type(stage_worker_receipt_writes) is not bool:
            raise TypeError("worker receipt staging must be an explicit boolean")
        if stage_worker_receipt_writes:
            from polisyos.core.run.worker_lifecycle import WorkerRunView

            if (
                type(target) is not _AttemptRunFacade
                or _resolve_exact_worker_run_view(target) is None
            ):
                raise TypeError("worker receipt staging requires the typed attempt view")
        object.__setattr__(self, "_EngineNodeRunView__target", target)
        object.__setattr__(
            self,
            "_EngineNodeRunView__stage_worker_receipt_writes",
            stage_worker_receipt_writes,
        )

    def __getattribute__(self, name: str) -> Any:
        if name in _EngineNodeRunView._STAGED_WORKER_WRITE_METHODS:
            if not object.__getattribute__(self, "_EngineNodeRunView__stage_worker_receipt_writes"):
                raise AttributeError(name)
            return object.__getattribute__(self, name)
        if name == "run_manifest":
            target = object.__getattribute__(self, "_EngineNodeRunView__target")
            manifest = getattr(target, name)
            return _snapshot_attempt_manifest_value(manifest)
        if name in _EngineNodeRunView._LOCAL_METHODS:
            return object.__getattribute__(self, name)
        if name in _EngineNodeRunView._READ_FIELDS | _EngineNodeRunView._READ_METHODS:
            target = object.__getattribute__(self, "_EngineNodeRunView__target")
            return getattr(target, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("engine node RunContext fields are read only")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("engine node RunContext fields are read only")

    def __repr__(self) -> str:
        return f"EngineNodeRunView(run_id={self.run_manifest.run_id!r})"

    def emit(self, *args: Any, **kwargs: Any) -> None:
        """Forward only the non-Core trace operation accepted by RunContext."""
        target = object.__getattribute__(self, "_EngineNodeRunView__target")
        target.emit(*args, **kwargs)

    def add_input(self, ref: ArtifactRef) -> None:
        """Stage a worker input through the enclosing attempt facade."""
        if not object.__getattribute__(self, "_EngineNodeRunView__stage_worker_receipt_writes"):
            raise AttributeError("add_input")
        target = object.__getattribute__(self, "_EngineNodeRunView__target")
        target.add_input(ref)

    def add_output(self, ref: ArtifactRef) -> None:
        """Stage a worker output through the enclosing attempt facade."""
        if not object.__getattribute__(self, "_EngineNodeRunView__stage_worker_receipt_writes"):
            raise AttributeError("add_output")
        target = object.__getattribute__(self, "_EngineNodeRunView__target")
        target.add_output(ref)

    def update_manifest(self, **changes: object) -> None:
        """Forward the existing allowlisted provenance update operation."""
        target = object.__getattribute__(self, "_EngineNodeRunView__target")
        target.update_manifest(**changes)

    def read_runtime_invocation_attempts(self) -> Any:
        target = object.__getattribute__(self, "_EngineNodeRunView__target")
        return target.read_runtime_invocation_attempts()

    def read_runtime_owner_output_refs(self) -> Any:
        target = object.__getattribute__(self, "_EngineNodeRunView__target")
        return target.read_runtime_owner_output_refs()

    def read_runtime_workflow_finalization_ref(self) -> Any:
        target = object.__getattribute__(self, "_EngineNodeRunView__target")
        return target.read_runtime_workflow_finalization_ref()


class _EngineNodeContextView:
    """Preserve a timeout facade while replacing its RunContext with the node view."""

    __slots__ = ("__run", "__target")

    def __init__(self, target: Any, run: _EngineNodeRunView) -> None:
        object.__setattr__(self, "_EngineNodeContextView__target", target)
        object.__setattr__(self, "_EngineNodeContextView__run", run)

    def __getattr__(self, name: str) -> Any:
        if name == "run":
            return object.__getattribute__(self, "_EngineNodeContextView__run")
        return getattr(object.__getattribute__(self, "_EngineNodeContextView__target"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        del name, value
        raise AttributeError("engine node context fields are read only")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("engine node context fields are read only")


def _node_facing_context(ctx: Any) -> Any:
    """Project every engine callback onto the supported node-facing run API."""
    if not hasattr(ctx, "run"):
        return ctx
    from polisyos.core.run.worker_lifecycle import WorkerRunView
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    run = ctx.run
    if type(run) in (WorkerRunView, _EngineNodeRunView):
        return ctx
    stage_worker_receipt_writes = (
        type(run) is _AttemptRunFacade and _resolve_exact_worker_run_view(run) is not None
    )
    run_view = _EngineNodeRunView(
        run,
        _token=_ENGINE_NODE_RUN_VIEW_TOKEN,
        stage_worker_receipt_writes=stage_worker_receipt_writes,
    )
    if isinstance(ctx, ExecutionContext):
        return dataclasses.replace(ctx, run=run_view)
    return _EngineNodeContextView(ctx, run_view)


class _AttemptContext:
    """Private worker context preserving the public context attribute surface."""

    def __init__(self, target: Any, authority: _AttemptAuthority) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(
            self,
            "store",
            _AttemptFacade(
                target.store,
                authority,
                write_methods=_STORE_WRITE_METHODS,
                raise_on_revoked_write=True,
            ),
        )
        object.__setattr__(self, "run", _AttemptRunFacade(target.run, authority, self.store))
        audit = getattr(target, "audit", None)
        if audit is not None:
            object.__setattr__(
                self,
                "audit",
                _AttemptFacade(
                    audit,
                    authority,
                    write_methods=_AUDIT_WRITE_METHODS,
                ),
            )
        claim_owner = getattr(target, "claim_ledger_owner", None)
        if claim_owner is not None:
            object.__setattr__(
                self,
                "claim_ledger_owner",
                _AttemptFacade(
                    claim_owner,
                    authority,
                    write_methods=_CLAIM_WRITE_METHODS,
                ),
            )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _ATTEMPT_CONTEXT_FACADE_FIELDS and "_target" in self.__dict__:
            raise AttributeError("timed attempt context facades cannot be rebound")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in _ATTEMPT_CONTEXT_FACADE_FIELDS and "_target" in self.__dict__:
            raise AttributeError("timed attempt context facades cannot be removed")
        object.__delattr__(self, name)

    def __getattr__(self, name: str) -> Any:
        if name in _ATTEMPT_CONTEXT_FACADE_FIELDS:
            try:
                target_value = getattr(self._target, name)
            except AttributeError:
                raise AttributeError(f"{type(self).__name__} has no attribute {name!r}") from None
            if target_value is None:
                return None
            raise AttributeError(f"protected timed attempt facade field {name!r} is unavailable")
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
        message="invalid worker control envelope",
        category="fatal",
        code="node.control_protocol",
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

    def __init__(self, error: Exception, known_spend: dict[str, Decimal]) -> None:
        super().__init__(str(error))
        self.error = error
        self.category = _exception_category(error)
        self.code = _exception_code(error)
        self.known_spend = known_spend


def _worker_error_payload(
    exc: BaseException,
    *,
    known_spend: dict[str, Decimal] | None = None,
    run_id: str | None = None,
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
        except InvalidOperation, TypeError, ValueError:
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


def _require_artifact_ref(value: object) -> ArtifactRef:
    """Require the existing artifact writer result contract at the dynamic boundary."""
    if not isinstance(value, ArtifactRef):
        raise TypeError("artifact_store_write_returned_invalid_ref")
    return value


def _require_node_outcome(value: object) -> NodeOutcome:
    """Require node implementations to return the engine's typed outcome."""
    if not isinstance(value, NodeOutcome):
        raise TypeError("node execution must return a NodeOutcome")
    return value


def _execute_capture_failure(node: Any, ctx: Any, state: ExperimentState) -> NodeOutcome:
    before = _spend_snapshot(state)
    try:
        return _require_node_outcome(node.execute(_node_facing_context(ctx), state))
    except ChildComputationOutcomeUnknown:
        raise
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
        except InvalidOperation, TypeError, ValueError:
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


def _attempt_dispatch_basis_ref(ctx: ExecutionContext) -> ArtifactRef | None:
    """Return the exact engine-owned basis bound to the current attempt, if any."""
    binding = getattr(ctx, "_engine_invocation", None)
    basis_ref = getattr(binding, "basis_ref", None)
    return basis_ref if isinstance(basis_ref, ArtifactRef) else None


def _verified_dead_letter_dispatch_basis(
    ctx: ExecutionContext,
    *,
    alias: str,
    node_id: str,
    dispatch_params: Mapping[str, Any] | None,
    basis_ref: ArtifactRef | None,
) -> ArtifactRef | None:
    """Admit only the current owner-linked attempt and its exact workflow params."""
    if (
        basis_ref is None
        or basis_ref.manifest_profile_sha256 is None
        or dispatch_params is None
        or not isinstance(dispatch_params, Mapping)
    ):
        return None
    try:
        run_id = ctx.run.run_manifest.run_id
        attempts = ctx.run.read_runtime_invocation_attempts()
        matches = [
            attempt
            for attempt in attempts
            if artifact_ref_identity_key(attempt.basis_ref) == artifact_ref_identity_key(basis_ref)
        ]
        if len(matches) != 1:
            return None
        attempt = matches[0]
        basis = attempt.basis
        if (
            basis.run_id != run_id
            or basis.node_alias != alias
            or basis.component_id != node_id
            or attempt.outcome is None
            or attempt.outcome.status != "unknown"
        ):
            return None
        from polisyos.scientist.orchestration.engine.producer_currentness import (
            _workflow_invocation_params,
        )

        if _workflow_invocation_params(ctx, basis) != dict(dispatch_params):
            return None
        return attempt.basis_ref
    except Exception:
        return None


def _persist_dead_letter(
    ctx: ExecutionContext,
    alias: str,
    node_id: str,
    last_error: Exception,
    attempts: int,
    policy: RetryPolicy,
    *,
    dispatch_params: Mapping[str, Any] | None = None,
    dispatch_basis_ref: ArtifactRef | None = None,
) -> ArtifactRef | None:
    """Persist a dead letter and its verified source ref, without copying raw params."""
    try:
        selected_basis_ref = _verified_dead_letter_dispatch_basis(
            ctx,
            alias=alias,
            node_id=node_id,
            dispatch_params=dispatch_params,
            basis_ref=dispatch_basis_ref,
        )
        payload = {
            "kind": "scientist.dead_letter",
            "run_id": getattr(ctx.run.run_manifest, "run_id", ""),
            "alias": alias,
            "node_id": node_id,
            "error_type": type(last_error).__name__,
            "error_message": str(last_error),
            "attempts": attempts,
            "dispatch_basis_status": (
                "selected" if selected_basis_ref is not None else "not_established"
            ),
            "dispatch_basis_ref": (
                selected_basis_ref.model_dump(mode="json")
                if selected_basis_ref is not None
                else None
            ),
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
                    version="2.0",
                ),
                inputs=(
                    [input_ref_from_artifact_ref(selected_basis_ref, role="dispatch_basis")]
                    if selected_basis_ref is not None
                    else []
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
    dispatch_params: Mapping[str, Any] | None = None,
    attempt_started: Callable[[int, ExperimentState], str] | None = None,
    attempt_completed: Callable[[str, NodeOutcome | None], None] | None = None,
    attempt_context: Callable[[str], ExecutionContext] | None = None,
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
        attempt_id = _begin_invocation_attempt(
            attempt_started,
            attempt_number=1,
            state=state,
        )
        try:
            attempt_ctx = _attempt_context_for_engine_attempt(ctx, attempt_id, attempt_context)
            outcome_value = node.execute(_node_facing_context(attempt_ctx), state)
            if not isinstance(outcome_value, NodeOutcome):
                raise TypeError("node execution must return a NodeOutcome")
            outcome = outcome_value
        except ChildComputationOutcomeUnknown as settlement:
            try:
                _finish_invocation_attempt(attempt_completed, attempt_id=attempt_id, outcome=None)
            except BaseException as completion_error:
                raise settlement from completion_error
            raise
        except BaseException:
            _finish_invocation_attempt(
                attempt_completed,
                attempt_id=attempt_id,
                outcome=None,
            )
            raise
        _finish_invocation_attempt(
            attempt_completed,
            attempt_id=attempt_id,
            outcome=outcome if isinstance(outcome, NodeOutcome) else None,
        )
        return outcome

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
        attempt_id = _begin_invocation_attempt(
            attempt_started,
            attempt_number=attempt + 1,
            state=attempt_state,
        )
        attempt_recorded = False
        attempt_dispatch_basis_ref: ArtifactRef | None = None
        try:
            attempt_ctx = _attempt_context_for_engine_attempt(ctx, attempt_id, attempt_context)
            attempt_dispatch_basis_ref = _attempt_dispatch_basis_ref(attempt_ctx)
            if remaining is not None:
                outcome = _execute_with_timeout_sync(
                    node,
                    attempt_ctx,
                    attempt_state,
                    timeout_s=remaining,
                    deadline_monotonic=deadline,
                    alias=alias,
                    dispatch_params=dispatch_params,
                )
            else:
                outcome_value = node.execute(_node_facing_context(attempt_ctx), attempt_state)
                if not isinstance(outcome_value, NodeOutcome):
                    raise TypeError("node execution must return a NodeOutcome")
                outcome = outcome_value

            try:
                _remaining_deadline(deadline, execution_state="completed_publication_rejected")
            except NodeTimeoutError:
                _accumulate_spend(failed_spend, _spend_delta(state, outcome.state))
                raise
            if outcome.status != "fail":
                _merge_spend(outcome.state, failed_spend)
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
                _finish_invocation_attempt(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=outcome,
                )
                attempt_recorded = True
                return outcome

            # Node returned a "fail" outcome — check retry_on filter
            if circuit_breaker is not None:
                circuit_breaker.record_failure()

            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                attempt_spend = _spend_delta(state, outcome.state)
                _accumulate_spend(failed_spend, attempt_spend)
                last_outcome = outcome
                _finish_invocation_attempt(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=outcome,
                )
                attempt_recorded = True
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
            _finish_invocation_attempt(
                attempt_completed,
                attempt_id=attempt_id,
                outcome=outcome,
            )
            attempt_recorded = True
            return outcome

        except NodeTimeoutError:
            if not attempt_recorded:
                _finish_invocation_attempt(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
            _merge_spend(state, failed_spend)
            raise
        except CircuitBreakerOpenError:
            if not attempt_recorded:
                _finish_invocation_attempt(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
            raise
        except KeyboardInterrupt:
            if not attempt_recorded:
                _finish_invocation_attempt(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
            raise
        except _InvocationAttemptPersistenceError:
            raise
        except ChildComputationOutcomeUnknown as settlement:
            if not attempt_recorded:
                try:
                    _finish_invocation_attempt(
                        attempt_completed, attempt_id=attempt_id, outcome=None
                    )
                except BaseException as completion_error:
                    raise settlement from completion_error
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            if not attempt_recorded:
                _finish_invocation_attempt(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
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
                dispatch_params=dispatch_params,
                dispatch_basis_ref=attempt_dispatch_basis_ref,
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
    alias: str | None = None,
    dispatch_params: Mapping[str, Any] | None = None,
) -> NodeOutcome:
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    assert deadline is not None
    _remaining_deadline(deadline)
    start_method = _timeout_worker_start_method()
    if start_method == "spawn":
        process_context = mp.get_context(start_method)
        authority = _new_attempt_authority(deadline, process_context=process_context)
        return _execute_with_timeout_process(
            node,
            ctx,
            state.model_copy(deep=True),
            timeout_s=timeout_s,
            authority=authority,
            deadline_monotonic=deadline,
            alias=alias,
            process_context=process_context,
            dispatch_params=dispatch_params,
        )
    if start_method == "fork":
        authority = _new_attempt_authority(deadline)
        return _execute_with_timeout_process(
            node,
            ctx,
            state.model_copy(deep=True),
            timeout_s=timeout_s,
            authority=authority,
            deadline_monotonic=deadline,
            alias=alias,
            dispatch_params=dispatch_params,
        )
    if sys.platform == "darwin":
        raise _timeout_worker_unsupported("safe_process_start_method_unavailable")

    future, authority, completed = _submit_thread_attempt(node, ctx, state, deadline)
    try:
        done, _ = wait([future], timeout=_remaining_deadline(deadline))
        if not done or completed[0] > deadline:
            raise _thread_deadline_error(future)
        # Retrieve outside timeout handling: provider TimeoutError keeps its category.
        return _require_node_outcome(future.result())
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
        return _require_node_outcome(wrapped.result())
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
    except RuntimeError, ValueError:
        return False


def _timeout_worker_start_method() -> Literal["fork", "spawn"] | None:
    """Choose the platform's supported bounded-process start method.

    Linux retains its supervisor/subreaper fork implementation. macOS uses a
    spawn worker with the closed typed task/context wire; it never inherits a
    multithreaded parent image through ``fork``.
    """
    try:
        methods = mp.get_all_start_methods()
    except RuntimeError, ValueError:
        return None
    if sys.platform == "linux" and "fork" in methods:
        return "fork"
    if sys.platform == "darwin" and "spawn" in methods:
        return "spawn"
    return None


def _timeout_worker_unsupported(reason: str) -> NodeTimeoutError:
    """Return the typed refusal used when no safe timeout worker can admit input."""
    return NodeTimeoutError(
        f"Timed node execution refused: {reason}",
        code="node.timeout_worker_unsupported",
        details={
            "execution_state": "unsupported_timeout_worker_input",
            "reason": reason,
        },
    )


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
    except AttributeError, TypeError, ValueError:
        return False
    return 0.0 < completed_at <= compute_deadline


def _owned_process_group_id(
    process: mp.Process,
    group_ready: Any,
    *,
    deadline: float,
    wait_until_deadline: bool = False,
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
        readiness_grace = remaining if wait_until_deadline else _PROCESS_GROUP_READY_S
        group_ready.wait(timeout=min(readiness_grace, remaining))
    if group_ready is not None and not group_ready.is_set():
        return None
    if not process.is_alive():
        return None
    process_id = process.pid
    if process_id is None:
        return None
    try:
        process_group_id = os.getpgid(process_id)
    except OSError:
        return None
    if process_group_id != process_id or process_group_id == os.getpgrp():
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


def _require_worker_result_frame(value: object) -> tuple[str, object]:
    """Admit the two-field worker status envelope before consuming its payload."""
    if not isinstance(value, tuple) or len(value) != 2:
        raise RuntimeError("timeout_worker_result_frame_invalid")
    status, payload = value
    if not isinstance(status, str):
        raise RuntimeError("timeout_worker_result_frame_invalid")
    return status, payload


def _drain_result_sync(
    process: mp.Process,
    result_queue: Any,
    *,
    compute_deadline: float,
    completion_time: Any = None,
) -> tuple[str, object]:
    """Receive a result while its producer runs, without partial-frame blocking."""
    raise_if_job_execution_interrupted()
    while process.is_alive() and not _completion_before_deadline(
        completion_time,
        compute_deadline,
    ):
        raise_if_job_execution_interrupted()
        remaining = compute_deadline - time.monotonic()
        if remaining <= 0:
            raise _WorkerComputeTimeout
        try:
            raw_frame: object = result_queue.get(timeout=min(_PROCESS_RESULT_POLL_S, remaining))
        except EOFError:
            raise _WorkerComputeTimeout from None
        except queue.Empty:
            continue
        if not _completion_before_deadline(completion_time, compute_deadline):
            raise _WorkerComputeTimeout
        raise_if_job_execution_interrupted()
        return _require_worker_result_frame(raw_frame)

    if not process.is_alive() and not _completion_before_deadline(
        completion_time,
        compute_deadline,
    ):
        raise _WorkerProcessExited(process.exitcode)
    if not _completion_before_deadline(completion_time, compute_deadline):
        raise _WorkerComputeTimeout

    delivery_deadline = _delivery_deadline(completion_time)
    while time.monotonic() < delivery_deadline:
        raise_if_job_execution_interrupted()
        remaining = delivery_deadline - time.monotonic()
        try:
            delivered_frame: object = result_queue.get(
                timeout=min(_PROCESS_RESULT_POLL_S, remaining)
            )
            raise_if_job_execution_interrupted()
            return _require_worker_result_frame(delivered_frame)
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
) -> tuple[str, object]:
    """Async counterpart of :func:`_drain_result_sync`."""
    raise_if_job_execution_interrupted()
    while process.is_alive() and not _completion_before_deadline(
        completion_time,
        compute_deadline,
    ):
        raise_if_job_execution_interrupted()
        try:
            raw_frame: object = result_queue.get_nowait()
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
            raise_if_job_execution_interrupted()
            return _require_worker_result_frame(raw_frame)

    if not process.is_alive() and not _completion_before_deadline(
        completion_time,
        compute_deadline,
    ):
        raise _WorkerProcessExited(process.exitcode)
    if not _completion_before_deadline(completion_time, compute_deadline):
        raise _WorkerComputeTimeout

    delivery_deadline = _delivery_deadline(completion_time)
    while time.monotonic() < delivery_deadline:
        raise_if_job_execution_interrupted()
        try:
            delivered_frame: object = result_queue.get_nowait()
            raise_if_job_execution_interrupted()
            return _require_worker_result_frame(delivered_frame)
        except EOFError:
            raise _WorkerDeliveryTimeout from None
        except queue.Empty:
            remaining = delivery_deadline - time.monotonic()
            await asyncio.sleep(min(_PROCESS_RESULT_POLL_S, remaining))
    raise _WorkerDeliveryTimeout


def _join_worker_until(process: mp.Process, *, deadline: float) -> None:
    """Wait for a result-producing worker to exit before decoding it."""
    while process.is_alive():
        raise_if_job_execution_interrupted()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _WorkerDeliveryTimeout
        process.join(timeout=min(_PROCESS_RESULT_POLL_S, remaining))


async def _join_worker_until_async(process: mp.Process, *, deadline: float) -> None:
    """Async wait for a result-producing worker to exit."""
    while process.is_alive():
        raise_if_job_execution_interrupted()
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


def _build_spawn_timeout_task(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    *,
    alias: str | None,
    dispatch_params: Mapping[str, Any] | None,
    timeout_s: float | None = None,
    supervisor_deadline_monotonic: float | None = None,
) -> Any:
    """Build the closed ``NodeTask`` accepted by the macOS spawn worker."""
    from polisyos.scientist.orchestration.engine.registry import (
        NodeRegistry,
        discover_nodes,
    )
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        capture_timeout_worker_engine_invocation,
        serialize_state,
        serialize_timeout_context,
        worker_dispatch_sha256,
    )
    from polisyos.scientist.orchestration.engine.runner.worker_pool import NodeTask
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.state_branching import (
        mutation_journal_for_state,
    )

    spec = getattr(node, "spec", None)
    metadata = getattr(spec, "metadata", None)
    component_id = getattr(metadata, "component_id", None)
    if component_id is None:
        raise ValueError("timeout_worker_canonical_node_required")
    node_id = str(component_id)
    if node_id not in _SPAWN_TIMEOUT_NODE_IDS:
        raise ValueError("timeout_worker_node_not_supported")
    registry = NodeRegistry()
    report = discover_nodes(
        registry,
        include_entry_points=False,
        include_builtin_nodes=True,
        include_dev_scan=False,
    )
    if report.errors or report.discovery_errors:
        raise ValueError("timeout_worker_builtin_registry_unavailable")
    try:
        canonical = registry.get(node_id)
    except _RETRY_RUNTIME_ERRORS as exc:
        raise ValueError("timeout_worker_node_not_registered") from exc
    if type(node) is not type(canonical) or node != canonical:
        raise ValueError("timeout_worker_canonical_node_instance_required")
    journal = mutation_journal_for_state(state)
    if journal is not None and journal.operations:
        raise ValueError("timeout_worker_preexisting_state_mutations_unsupported")
    if dispatch_params is None:
        raise ValueError("timeout_worker_dispatch_params_not_bound")

    engine_invocation = None
    if node_id == _SPAWN_TIMEOUT_TRANSPORTABILITY_NODE_ID:
        if timeout_s is None or supervisor_deadline_monotonic is None:
            raise ValueError("timeout_worker_transportability_budget_required")
        engine_invocation = capture_timeout_worker_engine_invocation(
            ctx,
            expected_run_id=state.run_id,
            node_alias=alias or node_id,
            component_id=node_id,
            dispatch_params=dispatch_params,
            timeout_s=timeout_s,
            supervisor_deadline_monotonic=supervisor_deadline_monotonic,
            state=state,
        )
    context_meta = serialize_timeout_context(
        ctx,
        expected_run_id=state.run_id,
        engine_invocation=engine_invocation,
    )
    if engine_invocation is None:
        plain_state = ExperimentState.model_validate(
            state.model_dump(mode="python", by_alias=True, exclude_none=False)
        )
    else:
        from polisyos.core.canon import from_canonical_bytes

        plain_state = ExperimentState.model_validate(
            from_canonical_bytes(ctx.store.get_bytes(engine_invocation.input_state_ref))
        )
    alias_value = alias or node_id
    state_bytes = serialize_state(plain_state)
    params = dict(dispatch_params)
    trace_carrier: dict[str, str] = {}
    invocation_id = secrets.token_hex(32)
    dispatch_digest = worker_dispatch_sha256(
        node_id=node_id,
        alias=alias_value,
        params=params,
        state_bytes=state_bytes,
        trace_carrier=trace_carrier,
        timeout_s=None,
        max_retries=0,
        context_meta=context_meta,
    )
    return NodeTask(
        node_id=node_id,
        alias=alias_value,
        params=params,
        state_bytes=state_bytes,
        trace_carrier=trace_carrier,
        timeout_s=None,
        context_meta=context_meta,
        worker_invocation_id=invocation_id,
        worker_dispatch_sha256=dispatch_digest,
    )


def _bind_spawn_timeout_dispatch(
    ctx: Any,
    task: Any,
    *,
    expected_run_id: str,
) -> tuple[WorkerLifecycleCapability, WorkerDispatchBinding]:
    """Bind a spawn task to the exact current Core owner before process launch."""
    run_adapter = getattr(ctx, "run", None)
    lifecycle_factory = getattr(run_adapter, "_worker_lifecycle_capability", None)
    if not callable(lifecycle_factory):
        raise _timeout_worker_unsupported("spawn_parent_core_run_required")
    try:
        capability = lifecycle_factory()
        snapshot = capability.snapshot()
        run_meta = task.context_meta["run"]
        owner_ref_payload = run_meta["owner_snapshot_ref"]
        if (
            snapshot.run_id != expected_run_id
            or run_meta["manifest"]["run_id"] != expected_run_id
            or snapshot.owner_snapshot_ref.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=False,
            )
            != owner_ref_payload
        ):
            raise ValueError("spawn_parent_owner_snapshot_mismatch")
        binding = capability.bind_dispatch(
            invocation_id=task.worker_invocation_id,
            dispatch_sha256=task.worker_dispatch_sha256,
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise _timeout_worker_unsupported("spawn_parent_owner_snapshot_not_active") from exc
    return capability, binding


def _build_fork_worker_receipt_binding(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    *,
    alias: str | None,
    timeout_s: float,
    dispatch_params: Mapping[str, Any] | None,
) -> _ForkWorkerReceiptBinding | None:
    """Bind an inherited node and its exact caller source to the active Core run.

    The fork transport inherits the node object from the parent and therefore
    does not serialize arbitrary node instances. It still binds the declared
    node contract, original invocation params, state bytes, timeout, parent
    owner snapshot, and a fresh parent nonce before the worker starts.
    """
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        serialize_state,
        worker_dispatch_sha256,
    )

    if not isinstance(ctx, ExecutionContext):
        # Lightweight non-product test doubles retain the legacy timeout route.
        # Every declared ExecutionContext must use a live Core parent writer.
        return None

    run_facade = ctx.run
    lifecycle_factory = getattr(run_facade, "_worker_lifecycle_capability", None)
    if not callable(lifecycle_factory):
        raise _timeout_worker_unsupported("fork_parent_core_run_required")
    try:
        capability = lifecycle_factory()
        snapshot = capability.snapshot()
    except (AttributeError, TypeError, ValueError) as exc:
        raise _timeout_worker_unsupported("fork_parent_owner_snapshot_not_active") from exc
    owner_snapshot_ref = snapshot.owner_snapshot_ref
    if snapshot.run_id != state.run_id:
        raise _timeout_worker_unsupported("fork_parent_owner_snapshot_not_active")
    if dispatch_params is None or not isinstance(dispatch_params, Mapping):
        raise _timeout_worker_unsupported("fork_dispatch_params_not_bound")

    spec = getattr(node, "spec", None)
    if spec is None:
        raise _timeout_worker_unsupported("fork_node_source_contract_not_typed")
    metadata = getattr(spec, "metadata", None)
    component_id = getattr(metadata, "component_id", None)
    if component_id is None or not callable(getattr(spec, "model_dump", None)):
        raise _timeout_worker_unsupported("fork_node_source_contract_not_typed")
    node_id = str(component_id)
    try:
        spec_payload = spec.model_dump(mode="json", by_alias=True, exclude_none=False)
        spec_bytes = json.dumps(
            spec_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        state_bytes = serialize_state(state)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _timeout_worker_unsupported("fork_dispatch_source_not_serializable") from exc

    invocation_id = secrets.token_hex(32)
    run_id = state.run_id
    context_meta = {
        "wire_schema": "polisyos.scientist.fork_inherited_dispatch.v1",
        "run_id": run_id,
        "owner_snapshot_ref": owner_snapshot_ref.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
        ),
        "node_type": f"{type(node).__module__}.{type(node).__qualname__}",
        "node_spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
        "dispatch_nonce": invocation_id,
    }
    try:
        dispatch_digest = worker_dispatch_sha256(
            node_id=node_id,
            alias=alias or node_id,
            params=dispatch_params,
            state_bytes=state_bytes,
            trace_carrier={},
            timeout_s=timeout_s,
            max_retries=0,
            context_meta=context_meta,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _timeout_worker_unsupported("fork_dispatch_source_not_serializable") from exc
    try:
        binding = capability.bind_dispatch(
            invocation_id=invocation_id,
            dispatch_sha256=dispatch_digest,
        )
    except (TypeError, ValueError) as exc:
        raise _timeout_worker_unsupported("fork_parent_owner_snapshot_not_active") from exc
    return _ForkWorkerReceiptBinding(capability=capability, binding=binding)


def _admit_spawn_timeout_worker_result(
    ctx: Any,
    task: Any,
    payload: Any,
    *,
    expected_run_id: str,
    capability: WorkerLifecycleCapability,
    binding: WorkerDispatchBinding,
) -> NodeOutcome:
    """Validate a worker receipt against the parent dispatch before returning its outcome."""
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        worker_dispatch_sha256,
    )

    if task is None:
        raise RuntimeError("timeout_worker_dispatch_not_established")
    expected_dispatch = worker_dispatch_sha256(
        node_id=task.node_id,
        alias=task.alias,
        params=task.params,
        state_bytes=task.state_bytes,
        trace_carrier=task.trace_carrier,
        timeout_s=None,
        max_retries=0,
        context_meta=task.context_meta,
    )
    if (
        not isinstance(task.worker_invocation_id, str)
        or len(task.worker_invocation_id) != 64
        or task.worker_dispatch_sha256 != expected_dispatch
    ):
        raise RuntimeError("timeout_worker_parent_dispatch_binding_invalid")

    if (
        binding is None
        or binding.invocation_id != task.worker_invocation_id
        or binding.dispatch_sha256 != expected_dispatch
        or binding.run_id != expected_run_id
    ):
        raise RuntimeError("timeout_worker_parent_owner_snapshot_not_established")
    return _admit_worker_execution_receipt(
        ctx,
        payload,
        capability=capability,
        binding=binding,
        expected_run_id=expected_run_id,
    )


def _admit_fork_timeout_worker_result(
    ctx: Any,
    binding: _ForkWorkerReceiptBinding,
    payload: Any,
) -> NodeOutcome:
    """Admit one Linux fork worker result into the exact live parent RunContext."""
    return _admit_worker_execution_receipt(
        ctx,
        payload,
        capability=binding.capability,
        binding=binding.binding,
        expected_run_id=binding.run_id,
    )


def _admit_worker_execution_receipt(
    ctx: Any,
    payload: Any,
    *,
    capability: WorkerLifecycleCapability,
    binding: WorkerDispatchBinding,
    expected_run_id: str,
) -> NodeOutcome:
    """Validate one result envelope and merge its trace only through its parent."""
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        DeserializationError,
        deserialize_outcome,
        deserialize_worker_execution_receipt,
    )

    try:
        (
            outcome_bytes,
            error_payload,
            receipt_invocation_id,
            dispatch_digest,
            receipt_owner_ref,
            records,
        ) = deserialize_worker_execution_receipt(payload)
    except DeserializationError as exc:
        raise RuntimeError("timeout_worker_receipt_invalid") from exc
    if (
        receipt_invocation_id != binding.invocation_id
        or dispatch_digest != binding.dispatch_sha256
        or receipt_owner_ref != binding.owner_snapshot_ref
        or binding.run_id != expected_run_id
    ):
        raise RuntimeError("timeout_worker_receipt_binding_mismatch")
    try:
        if error_payload is not None:
            worker_error: _WorkerNodeError | None = _worker_node_error(
                error_payload, expected_run_id=expected_run_id
            )
            outcome: NodeOutcome | None = None
        elif outcome_bytes is not None:
            decoded_outcome: object = deserialize_outcome(outcome_bytes)
            if not isinstance(decoded_outcome, NodeOutcome) or (
                decoded_outcome.state.run_id != expected_run_id
            ):
                raise RuntimeError("timeout_worker_outcome_run_binding_mismatch")
            outcome = decoded_outcome
            worker_error = None
        else:
            raise RuntimeError("timeout_worker_result_kind_missing")
    except DeserializationError as exc:
        raise RuntimeError("timeout_worker_outcome_invalid") from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("timeout_worker_result_invalid") from exc

    try:
        authority = getattr(ctx.run, "_authority", None)
        if isinstance(authority, _AttemptAuthority):
            authority.invoke_persistent_write(
                capability.admit_worker_events,
                binding,
                records,
            )
        else:
            capability.admit_worker_events(binding, records)
    except (_AttemptWriteDeniedError, AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("timeout_worker_parent_receipt_admission_failed") from exc
    if worker_error is not None:
        raise worker_error
    if outcome is None:
        raise RuntimeError("timeout_worker_outcome_missing_after_admission")
    return outcome


def _typed_node_timeout_worker(
    task: Any,
    result_channel: Any,
    group_ready: Any,
    completion_time: Any,
    deadline_monotonic: float,
    authority_active: Any,
) -> None:
    """Execute one typed task in a spawn child and publish a bounded result."""
    result_channel.close_reader()
    try:
        os.setsid()
    except OSError as exc:
        group_ready.set()
        completion_time.value = time.monotonic()
        result_channel.put(("error", _worker_error_payload(exc)))
        result_channel.close_writer()
        return
    group_ready.set()

    try:
        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_node_task_in_timeout_worker_sync,
        )

        payload = run_node_task_in_timeout_worker_sync(
            task,
            authority_active=authority_active,
            deadline_monotonic=deadline_monotonic,
        )
        completion_time.value = time.monotonic()
        result_channel.put(("ok", payload))
    except (SystemExit, KeyboardInterrupt) as exc:
        completion_time.value = time.monotonic()
        code = exc.code if isinstance(exc, SystemExit) else None
        if code is not None and not isinstance(code, (int, str)):
            result_channel.put(
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
            result_channel.put(
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
    except _RETRY_RUNTIME_ERRORS as exc:
        completion_time.value = time.monotonic()
        result_channel.put(("error", _worker_error_payload(exc)))
    finally:
        result_channel.close_writer()


def _decode_worker_node_outcome(payload: object) -> NodeOutcome:
    """Decode one admitted worker payload without passing non-bytes to the wire reader."""
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        _coerce_wire_bytes,
        deserialize_outcome,
    )

    if isinstance(payload, (bytes, bytearray, memoryview, str)) or (
        isinstance(payload, list) and all(isinstance(item, int) for item in payload)
    ):
        outcome_value = deserialize_outcome(_coerce_wire_bytes(payload))
        return _require_node_outcome(outcome_value)
    return decode_node_outcome(payload)


def _execute_with_timeout_process(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    *,
    timeout_s: float,
    authority: _AttemptAuthority | None = None,
    deadline_monotonic: float | None = None,
    alias: str | None = None,
    process_context: BaseContext | None = None,
    dispatch_params: Mapping[str, Any] | None = None,
) -> NodeOutcome:
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    compute_deadline = deadline if deadline is not None else time.monotonic() + timeout_s
    start_method = _timeout_worker_start_method()
    if start_method is None:
        raise _timeout_worker_unsupported("safe_process_start_method_unavailable")
    mp_ctx = process_context or mp.get_context(start_method)
    authority = authority or _new_attempt_authority(
        deadline,
        process_context=mp_ctx if start_method == "spawn" else None,
    )
    task = None
    fork_binding = None
    spawn_capability = None
    spawn_binding = None
    if start_method == "spawn":
        if authority._shared_active is None:
            raise _timeout_worker_unsupported("process_shared_attempt_authority_required")
        try:
            task = _build_spawn_timeout_task(
                node,
                ctx,
                state,
                alias=alias,
                dispatch_params=dispatch_params,
                timeout_s=timeout_s,
                supervisor_deadline_monotonic=compute_deadline,
            )
            spawn_capability, spawn_binding = _bind_spawn_timeout_dispatch(
                ctx,
                task,
                expected_run_id=state.run_id,
            )
        except _RETRY_RUNTIME_ERRORS as exc:
            authority.revoke()
            reason = str(exc) or type(exc).__name__
            raise _timeout_worker_unsupported(reason) from exc
    elif start_method == "fork":
        try:
            fork_binding = _build_fork_worker_receipt_binding(
                node,
                ctx,
                state,
                alias=alias,
                timeout_s=timeout_s,
                dispatch_params=dispatch_params,
            )
        except _RETRY_RUNTIME_ERRORS as exc:
            authority.revoke()
            if isinstance(exc, NodeTimeoutError):
                raise
            reason = str(exc) or type(exc).__name__
            raise _timeout_worker_unsupported(reason) from exc
    result_queue: _WorkerResultChannel | None = None
    process: Any = None
    lifecycle = _WorkerLifecycle(compute_deadline=compute_deadline, completion_time=None)
    try:
        result_queue = _WorkerResultChannel(mp_ctx)
        group_ready = mp_ctx.Event()
        completion_time = mp_ctx.Value("d", 0.0)
        lifecycle.completion_time = completion_time
        lifecycle.cleanup_complete = mp_ctx.Value("b", False) if start_method == "fork" else None
        process_factory = _process_factory(mp_ctx)
        if start_method == "spawn":
            if task is None:
                raise RuntimeError("spawn_timeout_task_missing_after_admission")
            if authority._shared_active is None:
                raise RuntimeError("spawn_timeout_authority_missing_after_admission")
            process = process_factory(
                target=_typed_node_timeout_worker,
                args=(
                    task,
                    result_queue,
                    group_ready,
                    completion_time,
                    lifecycle.compute_deadline,
                    authority._shared_active,
                ),
                daemon=True,
            )
        else:
            process = process_factory(
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
                    fork_binding,
                ),
                daemon=True,
            )
        raise_if_job_execution_interrupted()
        process.start()
        result_queue.close_writer()
        lifecycle.process_group_id = _owned_process_group_id(
            process,
            group_ready,
            deadline=lifecycle.compute_deadline,
            wait_until_deadline=start_method == "spawn",
        )
        status, payload = _drain_result_sync(
            process,
            result_queue,
            compute_deadline=lifecycle.compute_deadline,
            completion_time=lifecycle.completion_time,
        )
        if start_method == "spawn":
            cleanup_complete = _terminate_owned_process(
                process,
                lifecycle.process_group_id,
                lifecycle.cleanup_complete,
            )
            if not cleanup_complete:
                raise _worker_timeout_error(timeout_s, cleanup_complete=False)
        else:
            _join_worker_until(process, deadline=_delivery_deadline(lifecycle.completion_time))
        raise_if_job_execution_interrupted()
    except JobExecutionInterrupted:
        authority.revoke()
        if process is not None and process.pid is not None:
            # The validated owner group can outlive the immediate child.
            _terminate_owned_process(
                process, lifecycle.process_group_id, lifecycle.cleanup_complete
            )
        raise
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
    except _WorkerProcessExited:
        authority.revoke()
        if process is not None:
            _terminate_owned_process(
                process, lifecycle.process_group_id, lifecycle.cleanup_complete
            )
        raise
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
                _terminate_owned_process(
                    process, lifecycle.process_group_id, lifecycle.cleanup_complete
                )
            _close_worker_process(process)
        if result_queue is not None:
            _close_result_queue(result_queue)

    if status == "ok":
        if start_method == "spawn":
            return _admit_spawn_timeout_worker_result(
                ctx,
                task,
                payload,
                expected_run_id=state.run_id,
                capability=spawn_capability,
                binding=spawn_binding,
            )
        return _decode_worker_node_outcome(payload)
    if status == "worker_receipt":
        if fork_binding is None:
            raise RuntimeError("fork_worker_receipt_without_parent_dispatch")
        return _admit_fork_timeout_worker_result(ctx, fork_binding, payload)
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
    alias: str | None = None,
    process_context: BaseContext | None = None,
    dispatch_params: Mapping[str, Any] | None = None,
) -> NodeOutcome:
    deadline = _invocation_deadline(timeout_s, deadline_monotonic)
    compute_deadline = deadline if deadline is not None else time.monotonic() + timeout_s
    start_method = _timeout_worker_start_method()
    if start_method is None:
        raise _timeout_worker_unsupported("safe_process_start_method_unavailable")
    mp_ctx = process_context or mp.get_context(start_method)
    if authority is None:
        authority = _new_attempt_authority(
            deadline,
            process_context=mp_ctx if start_method == "spawn" else None,
        )
        state = state.model_copy(deep=True)
    task = None
    fork_binding = None
    spawn_capability = None
    spawn_binding = None
    if start_method == "spawn":
        if authority._shared_active is None:
            raise _timeout_worker_unsupported("process_shared_attempt_authority_required")
        try:
            task = _build_spawn_timeout_task(
                node,
                ctx,
                state,
                alias=alias,
                dispatch_params=dispatch_params,
                timeout_s=timeout_s,
                supervisor_deadline_monotonic=compute_deadline,
            )
            spawn_capability, spawn_binding = _bind_spawn_timeout_dispatch(
                ctx,
                task,
                expected_run_id=state.run_id,
            )
        except _RETRY_RUNTIME_ERRORS as exc:
            authority.revoke()
            reason = str(exc) or type(exc).__name__
            raise _timeout_worker_unsupported(reason) from exc
    elif start_method == "fork":
        try:
            fork_binding = _build_fork_worker_receipt_binding(
                node,
                ctx,
                state,
                alias=alias,
                timeout_s=timeout_s,
                dispatch_params=dispatch_params,
            )
        except _RETRY_RUNTIME_ERRORS as exc:
            authority.revoke()
            if isinstance(exc, NodeTimeoutError):
                raise
            reason = str(exc) or type(exc).__name__
            raise _timeout_worker_unsupported(reason) from exc
    result_queue: _WorkerResultChannel | None = None
    process: Any = None
    lifecycle = _WorkerLifecycle(compute_deadline=compute_deadline, completion_time=None)
    try:
        result_queue = _WorkerResultChannel(mp_ctx)
        group_ready = mp_ctx.Event()
        completion_time = mp_ctx.Value("d", 0.0)
        lifecycle.completion_time = completion_time
        lifecycle.cleanup_complete = mp_ctx.Value("b", False) if start_method == "fork" else None
        process_factory = _process_factory(mp_ctx)
        if start_method == "spawn":
            if task is None:
                raise RuntimeError("spawn_timeout_task_missing_after_admission")
            if authority._shared_active is None:
                raise RuntimeError("spawn_timeout_authority_missing_after_admission")
            process = process_factory(
                target=_typed_node_timeout_worker,
                args=(
                    task,
                    result_queue,
                    group_ready,
                    completion_time,
                    lifecycle.compute_deadline,
                    authority._shared_active,
                ),
                daemon=True,
            )
        else:
            process = process_factory(
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
                    fork_binding,
                ),
                daemon=True,
            )
        raise_if_job_execution_interrupted()
        process.start()
        result_queue.close_writer()
        lifecycle.process_group_id = _owned_process_group_id(
            process,
            group_ready,
            deadline=lifecycle.compute_deadline,
            wait_until_deadline=start_method == "spawn",
        )
        status, payload = await _drain_result_async(
            process,
            result_queue,
            compute_deadline=lifecycle.compute_deadline,
            completion_time=lifecycle.completion_time,
        )
        if start_method == "spawn":
            cleanup_complete = _terminate_owned_process(
                process,
                lifecycle.process_group_id,
                lifecycle.cleanup_complete,
            )
            if not cleanup_complete:
                raise _worker_timeout_error(timeout_s, cleanup_complete=False)
        else:
            await _join_worker_until_async(
                process, deadline=_delivery_deadline(lifecycle.completion_time)
            )
        raise_if_job_execution_interrupted()
    except JobExecutionInterrupted:
        authority.revoke()
        if process is not None and process.pid is not None:
            # The validated owner group can outlive the immediate child.
            _terminate_owned_process(
                process, lifecycle.process_group_id, lifecycle.cleanup_complete
            )
        raise
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
    except _WorkerProcessExited:
        authority.revoke()
        if process is not None:
            _terminate_owned_process(
                process, lifecycle.process_group_id, lifecycle.cleanup_complete
            )
        raise
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
                _terminate_owned_process(
                    process, lifecycle.process_group_id, lifecycle.cleanup_complete
                )
            _close_worker_process(process)
        if result_queue is not None:
            _close_result_queue(result_queue)

    if status == "ok":
        if start_method == "spawn":
            return _admit_spawn_timeout_worker_result(
                ctx,
                task,
                payload,
                expected_run_id=state.run_id,
                capability=spawn_capability,
                binding=spawn_binding,
            )
        return _decode_worker_node_outcome(payload)
    if status == "worker_receipt":
        if fork_binding is None:
            raise RuntimeError("fork_worker_receipt_without_parent_dispatch")
        return _admit_fork_timeout_worker_result(ctx, fork_binding, payload)
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
            return _require_node_outcome(
                await node.execute_async(_node_facing_context(worker_ctx), worker_state)
            )
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
    worker_binding: _ForkWorkerReceiptBinding | None = None,
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

    staged_trace = None

    def _send_worker_error(exc: BaseException, *, known_spend: dict[str, Decimal]) -> None:
        error_payload = _worker_error_payload(
            exc,
            known_spend=known_spend,
            run_id=state.run_id,
        )
        if worker_binding is None:
            _send("error", error_payload)
            return
        from polisyos.scientist.orchestration.engine.runner.serialization import (
            serialize_worker_execution_receipt,
        )

        _send(
            "worker_receipt",
            serialize_worker_execution_receipt(
                error_payload=error_payload,
                invocation_id=worker_binding.invocation_id,
                dispatch_sha256=worker_binding.dispatch_sha256,
                owner_snapshot_ref=worker_binding.owner_snapshot_ref,
                records=[] if staged_trace is None else staged_trace.records,
            ),
        )

    before_spend = _spend_snapshot(state)
    try:
        if worker_binding is not None:
            from polisyos.scientist.orchestration.engine.context import ExecutionContext
            from polisyos.scientist.orchestration.engine.runner._activity_worker import (
                _StagedWorkerTraceSink,
            )

            staged_trace = _StagedWorkerTraceSink()
            if not isinstance(ctx, ExecutionContext):
                raise TypeError("fork_worker_execution_context_not_typed")
            run_facade = ctx.run
            capability = worker_binding.capability
            worker_run = capability.worker_view(
                run_adapter=run_facade,
                trace=staged_trace,
                binding=worker_binding.binding,
            )
            authority = getattr(run_facade, "_authority", None)
            if isinstance(authority, _AttemptAuthority):
                object.__setattr__(
                    run_facade,
                    "trace",
                    _AttemptFacade(
                        staged_trace,
                        authority,
                        write_methods=_TRACE_WRITE_METHODS,
                    ),
                )
            worker_ctx = dataclasses.replace(ctx, run=worker_run)

        else:
            worker_ctx = ctx

        outcome = node.execute(_node_facing_context(worker_ctx), state)
        _mark_completion()
        if isinstance(outcome, NodeOutcome):
            from polisyos.scientist.orchestration.engine.runner.serialization import (
                serialize_outcome,
            )

            outcome_bytes = serialize_outcome(outcome)
            if worker_binding is None:
                _send("ok", outcome_bytes)
            else:
                from polisyos.scientist.orchestration.engine.runner.serialization import (
                    serialize_worker_execution_receipt,
                )

                _send(
                    "worker_receipt",
                    serialize_worker_execution_receipt(
                        outcome_bytes=outcome_bytes,
                        invocation_id=worker_binding.invocation_id,
                        dispatch_sha256=worker_binding.dispatch_sha256,
                        owner_snapshot_ref=worker_binding.owner_snapshot_ref,
                        records=[] if staged_trace is None else staged_trace.records,
                    ),
                )
        elif hasattr(outcome, "model_dump"):
            # Preserve the established diagnostic when an attempted model dump
            # itself fails; the parent still validates the returned wire type.
            if worker_binding is None:
                _send("ok", outcome.model_dump(mode="python"))
            else:
                from polisyos.scientist.orchestration.engine.runner.serialization import (
                    serialize_outcome,
                    serialize_worker_execution_receipt,
                )

                _send(
                    "worker_receipt",
                    serialize_worker_execution_receipt(
                        outcome_bytes=serialize_outcome(outcome),
                        invocation_id=worker_binding.invocation_id,
                        dispatch_sha256=worker_binding.dispatch_sha256,
                        owner_snapshot_ref=worker_binding.owner_snapshot_ref,
                        records=[] if staged_trace is None else staged_trace.records,
                    ),
                )
        else:
            _send_worker_error(
                ValueError(f"invalid node outcome: {type(outcome).__name__}"),
                known_spend={},
            )
    except _RETRY_RUNTIME_ERRORS as exc:
        _mark_completion()
        _send_worker_error(
            exc,
            known_spend=_spend_changes(before_spend, _spend_snapshot(state)),
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
    dispatch_params: Mapping[str, Any] | None = None,
    attempt_started: Callable[[int, ExperimentState], Awaitable[str]] | None = None,
    attempt_completed: Callable[[str, NodeOutcome | None], Awaitable[None]] | None = None,
    attempt_context: Callable[[str], ExecutionContext] | None = None,
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

    async def _invoke(
        attempt_state: ExperimentState,
        attempt_ctx: ExecutionContext,
    ) -> NodeOutcome:
        remaining = _remaining_deadline(deadline)
        if _has_async:
            if remaining is None:
                return _require_node_outcome(
                    await node.execute_async(_node_facing_context(attempt_ctx), attempt_state)
                )
            return await _execute_with_timeout_async(
                node,
                attempt_ctx,
                attempt_state,
                timeout_s=remaining,
                deadline_monotonic=deadline,
            )
        if remaining is not None:
            if _timeout_worker_start_method() is not None:
                return await _execute_with_timeout_process_async(
                    node,
                    attempt_ctx,
                    attempt_state,
                    timeout_s=remaining,
                    deadline_monotonic=deadline,
                    alias=alias,
                    dispatch_params=dispatch_params,
                )
            if sys.platform == "darwin":
                raise _timeout_worker_unsupported("safe_process_start_method_unavailable")
            return await _execute_with_timeout_thread_async(
                node,
                attempt_ctx,
                attempt_state,
                timeout_s=remaining,
                deadline_monotonic=deadline,
            )
        authority = _AttemptAuthority()
        worker_ctx = _build_attempt_context(attempt_ctx, authority)
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
        attempt_id = await _begin_invocation_attempt_async(
            attempt_started,
            attempt_number=1,
            state=state,
        )
        try:
            attempt_ctx = _attempt_context_for_engine_attempt(ctx, attempt_id, attempt_context)
            outcome = await _invoke(state, attempt_ctx)
        except _CompletedAttemptError as exc:
            await _finish_invocation_attempt_async(
                attempt_completed,
                attempt_id=attempt_id,
                outcome=None,
            )
            _merge_spend(state, exc.known_spend)
            raise exc.error from None
        except ChildComputationOutcomeUnknown as settlement:
            try:
                await _finish_invocation_attempt_async(
                    attempt_completed, attempt_id=attempt_id, outcome=None
                )
            except BaseException as completion_error:
                raise settlement from completion_error
            raise
        except BaseException:
            await _finish_invocation_attempt_async(
                attempt_completed,
                attempt_id=attempt_id,
                outcome=None,
            )
            raise
        await _finish_invocation_attempt_async(
            attempt_completed,
            attempt_id=attempt_id,
            outcome=outcome if isinstance(outcome, NodeOutcome) else None,
        )
        return outcome

    last_outcome: NodeOutcome | None = None
    failed_spend: dict[str, Decimal] = {}
    node_id = str((getattr(node, "spec", None) and node.spec.metadata.component_id) or alias)

    for attempt in range(retry_policy.max_retries + 1):
        try:
            _remaining_deadline(deadline)
        except NodeTimeoutError:
            _merge_spend(state, failed_spend)
            raise
        # Circuit breaker check
        if circuit_breaker is not None and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open for node {alias}",
            )

        attempt_state = _fresh_retry_state(state, node) if retry_policy.max_retries > 0 else state
        attempt_id = await _begin_invocation_attempt_async(
            attempt_started,
            attempt_number=attempt + 1,
            state=attempt_state,
        )
        attempt_recorded = False
        attempt_dispatch_basis_ref: ArtifactRef | None = None
        try:
            attempt_ctx = _attempt_context_for_engine_attempt(ctx, attempt_id, attempt_context)
            attempt_dispatch_basis_ref = _attempt_dispatch_basis_ref(attempt_ctx)
            outcome = await _invoke(attempt_state, attempt_ctx)

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
                await _finish_invocation_attempt_async(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=outcome,
                )
                attempt_recorded = True
                return outcome

            if circuit_breaker is not None:
                circuit_breaker.record_failure()

            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                attempt_spend = _spend_delta(state, outcome.state)
                _accumulate_spend(failed_spend, attempt_spend)
                last_outcome = outcome
                await _finish_invocation_attempt_async(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=outcome,
                )
                attempt_recorded = True
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
            await _finish_invocation_attempt_async(
                attempt_completed,
                attempt_id=attempt_id,
                outcome=outcome,
            )
            attempt_recorded = True
            return outcome

        except NodeTimeoutError:
            if not attempt_recorded:
                await _finish_invocation_attempt_async(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
            _merge_spend(state, failed_spend)
            raise
        except CircuitBreakerOpenError:
            if not attempt_recorded:
                await _finish_invocation_attempt_async(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
            raise
        except asyncio.CancelledError:
            if not attempt_recorded:
                await _finish_invocation_attempt_async(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
            _logger.info("Node %s cancelled during attempt %d", alias, attempt)
            raise
        except _InvocationAttemptPersistenceError:
            raise
        except ChildComputationOutcomeUnknown as settlement:
            if not attempt_recorded:
                try:
                    await _finish_invocation_attempt_async(
                        attempt_completed, attempt_id=attempt_id, outcome=None
                    )
                except BaseException as completion_error:
                    raise settlement from completion_error
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            if not attempt_recorded:
                await _finish_invocation_attempt_async(
                    attempt_completed,
                    attempt_id=attempt_id,
                    outcome=None,
                )
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
                dispatch_params=dispatch_params,
                dispatch_basis_ref=attempt_dispatch_basis_ref,
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
