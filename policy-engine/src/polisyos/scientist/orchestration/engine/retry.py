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
import contextvars
import dataclasses
import logging
import multiprocessing as mp
import os
import queue
import random
import signal
import threading
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import UTC, datetime
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

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.scientist.orchestration.engine.circuit_breaker import CircuitBreaker
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

_logger = logging.getLogger(__name__)

# A process timeout bounds node computation.  Queue delivery is a separate,
# short grace period: a worker may have exited while its multiprocessing.Queue
# feeder is still flushing a result.  Keeping the windows distinct prevents a
# large result from consuming an unbounded extension of the node deadline.
_PROCESS_RESULT_POLL_S = 0.01
_PROCESS_GROUP_READY_S = 0.05
_PROCESS_DELIVERY_GRACE_S = 1.0
_PROCESS_CLEANUP_GRACE_S = 1.0


class _WorkerComputeTimeout(Exception):
    """The worker did not finish computation before the node deadline."""


class _WorkerDeliveryTimeout(Exception):
    """The worker finished, but its result was not delivered in bounded time."""

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

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active = True

    def invoke(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        """Run one authorized operation, or deny it after revocation."""
        with self._lock:
            if not self._active:
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
                **{
                    key: _unwrap_manifest_value(item)
                    for key, item in kwargs.items()
                },
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
                    **{
                        key: _unwrap_manifest_value(item)
                        for key, item in kwargs.items()
                    },
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
                _wrap_manifest_value(item, self._authority)
                for item in value(*args, **kwargs)
            )
        if callable(value) and name == "copy":
            return lambda *args, **kwargs: _wrap_manifest_value(
                value(*args, **kwargs), self._authority
            )
        return value

    def __getitem__(self, key: Any) -> Any:
        return _wrap_manifest_value(self._target[key], self._authority)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._authority.invoke(
            self._target.__setitem__, key, _unwrap_manifest_value(value)
        )

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
                    **{
                        key: _unwrap_manifest_value(item)
                        for key, item in kwargs.items()
                    },
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
                        _STORE_WRITE_METHODS
                        if name == "store"
                        else _TRACE_WRITE_METHODS
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
        raise RuntimeError(
            "failed to preserve ExecutionContext type for timed attempt"
        ) from exc


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
) -> NodeOutcome:
    """Sync retry wrapper for ``WorkflowExecutor``.

    * Timeout: runs ``node.execute`` in a thread with
      ``concurrent.futures.Future.result(timeout=...)``.
    * Retry: loops up to ``max_retries``, exponential backoff via ``time.sleep()``.
    """
    retry_policy = _apply_bounded_liveness_retry_ceiling(
        alias=alias,
        retry_policy=retry_policy,
        liveness_config=liveness_config,
    )
    # Fast path — no retry, no timeout
    if retry_policy.max_retries == 0 and timeout_s is None and circuit_breaker is None:
        return node.execute(ctx, state)

    last_outcome: NodeOutcome | None = None
    node_id = str((getattr(node, "spec", None) and node.spec.metadata.component_id) or alias)

    for attempt in range(retry_policy.max_retries + 1):
        # Circuit breaker check
        if circuit_breaker is not None and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open for node {alias}",
            )

        try:
            if timeout_s is not None:
                outcome = _execute_with_timeout_sync(node, ctx, state, timeout_s=timeout_s)
            else:
                outcome = node.execute(ctx, state)

            if outcome.status != "fail":
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
                return outcome

            # Node returned a "fail" outcome — check retry_on filter
            if circuit_breaker is not None:
                circuit_breaker.record_failure()

            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                last_outcome = outcome
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s (attempt %d/%d) after %.1fs",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    delay,
                )
                ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_RETRY",
                    metrics={"attempt": attempt + 1, "delay_s": delay},
                )
                time.sleep(delay)
                continue

            return outcome

        except (NodeTimeoutError, CircuitBreakerOpenError):
            raise
        except KeyboardInterrupt:
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            if attempt < retry_policy.max_retries:
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s after exception (attempt %d/%d): %s",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    exc,
                )
                ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_RETRY",
                    metrics={"attempt": attempt + 1, "delay_s": delay},
                )
                time.sleep(delay)
                continue

            dlq_ref = _persist_dead_letter(
                ctx,
                alias,
                node_id,
                exc,
                attempts=retry_policy.max_retries + 1,
                policy=retry_policy,
            )
            if dlq_ref is not None:
                ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_DEAD_LETTER",
                    outputs=[dlq_ref],
                )
            raise RetryExhaustedError(
                f"Node {alias}: all {retry_policy.max_retries} retries exhausted",
            ) from exc

    # Should not reach here, but for safety:
    if last_outcome is not None:
        return last_outcome
    raise RetryExhaustedError(  # pragma: no cover
        f"Node {alias}: all retries exhausted",
    )


def _execute_with_timeout_sync(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    timeout_s: float,
) -> NodeOutcome:
    authority = _AttemptAuthority()
    worker_ctx = _build_attempt_context(ctx, authority)
    worker_state = state.model_copy(deep=True)
    if _can_use_forked_timeout_worker():
        return _execute_with_timeout_process(
            node,
            worker_ctx,
            worker_state,
            timeout_s=timeout_s,
            authority=authority,
        )

    context = contextvars.copy_context()
    future = get_shared_executor().submit(
        context.run,
        node.execute,
        worker_ctx,
        worker_state,
    )
    try:
        return future.result(timeout=timeout_s)
    except FuturesTimeoutError:
        future.cancel()
        authority.revoke()
        raise NodeTimeoutError(
            f"Node exceeded timeout of {timeout_s}s",
        ) from None


def _can_use_forked_timeout_worker() -> bool:
    try:
        return "fork" in mp.get_all_start_methods()
    except (RuntimeError, ValueError):
        return False


def _delivery_deadline() -> float:
    """Return a bounded deadline for Queue feeder delivery."""
    return time.monotonic() + _PROCESS_DELIVERY_GRACE_S


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


def _terminate_owned_process(
    process: mp.Process,
    process_group_id: int | None,
) -> bool:
    """Terminate one worker and any descendants in its owned process group."""
    if not process.is_alive():
        process.join(timeout=0.0)
        return True

    if process_group_id is not None:
        try:
            os.killpg(process_group_id, signal.SIGTERM)
        except OSError:
            process.terminate()
    else:
        process.terminate()
    process.join(timeout=_PROCESS_CLEANUP_GRACE_S)

    if process.is_alive():
        if process_group_id is not None:
            try:
                os.killpg(process_group_id, signal.SIGKILL)
            except OSError:
                process.kill()
        else:
            process.kill()
        process.join(timeout=_PROCESS_CLEANUP_GRACE_S)
    return not process.is_alive()


def _close_worker_process(process: mp.Process) -> None:
    """Release process resources after the owned process has stopped."""
    if process.is_alive():
        return
    process.join(timeout=0.0)
    process.close()


def _close_result_queue(result_queue: Any) -> None:
    """Close the result queue after all needed bytes have been drained."""
    result_queue.close()
    result_queue.join_thread()


def _drain_result_sync(
    process: mp.Process,
    result_queue: mp.Queue[Any],
    *,
    compute_deadline: float,
) -> tuple[str, Any]:
    """Receive a worker result without joining before Queue drain."""
    while process.is_alive():
        remaining = compute_deadline - time.monotonic()
        if remaining <= 0:
            raise _WorkerComputeTimeout
        try:
            return result_queue.get(
                timeout=min(_PROCESS_RESULT_POLL_S, remaining)
            )
        except queue.Empty:
            continue

    delivery_deadline = _delivery_deadline()
    while time.monotonic() < delivery_deadline:
        remaining = delivery_deadline - time.monotonic()
        try:
            return result_queue.get(
                timeout=min(_PROCESS_RESULT_POLL_S, remaining)
            )
        except queue.Empty:
            continue
    raise _WorkerDeliveryTimeout


async def _drain_result_async(
    process: mp.Process,
    result_queue: mp.Queue[Any],
    *,
    compute_deadline: float,
) -> tuple[str, Any]:
    """Async counterpart of :func:`_drain_result_sync`."""
    while process.is_alive():
        try:
            return result_queue.get_nowait()
        except queue.Empty:
            remaining = compute_deadline - time.monotonic()
            if remaining <= 0:
                raise _WorkerComputeTimeout
            await asyncio.sleep(min(_PROCESS_RESULT_POLL_S, remaining))

    delivery_deadline = _delivery_deadline()
    while time.monotonic() < delivery_deadline:
        try:
            return result_queue.get_nowait()
        except queue.Empty:
            remaining = delivery_deadline - time.monotonic()
            await asyncio.sleep(min(_PROCESS_RESULT_POLL_S, remaining))
    raise _WorkerDeliveryTimeout


def _join_worker_until(process: mp.Process, *, deadline: float) -> None:
    """Wait for a result-producing worker to exit before decoding it."""
    while process.is_alive():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _WorkerComputeTimeout
        process.join(timeout=min(_PROCESS_RESULT_POLL_S, remaining))


async def _join_worker_until_async(process: mp.Process, *, deadline: float) -> None:
    """Async wait for a result-producing worker to exit."""
    while process.is_alive():
        if deadline - time.monotonic() <= 0:
            raise _WorkerComputeTimeout
        process.join(timeout=0.0)
        await asyncio.sleep(
            min(_PROCESS_RESULT_POLL_S, max(0.0, deadline - time.monotonic()))
        )


def _worker_timeout_error(
    timeout_s: float,
    *,
    cleanup_complete: bool,
) -> NodeTimeoutError:
    suffix = "" if cleanup_complete else "; owned process cleanup incomplete"
    return NodeTimeoutError(f"Node exceeded timeout of {timeout_s}s{suffix}")


def _execute_with_timeout_process(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    *,
    timeout_s: float,
    authority: _AttemptAuthority | None = None,
) -> NodeOutcome:
    authority = authority or _AttemptAuthority()
    mp_ctx = mp.get_context("fork")
    result_queue: mp.Queue[Any] = mp_ctx.Queue(maxsize=1)
    group_ready = mp_ctx.Event()
    process = mp_ctx.Process(
        target=_node_execute_worker,
        args=(node, ctx, state, result_queue, group_ready),
        daemon=True,
    )
    compute_deadline = time.monotonic() + timeout_s
    process_group_id: int | None = None
    try:
        process.start()
        process_group_id = _owned_process_group_id(
            process,
            group_ready,
            deadline=compute_deadline,
        )
        status, payload = _drain_result_sync(
            process,
            result_queue,
            compute_deadline=compute_deadline,
        )
        _join_worker_until(process, deadline=_delivery_deadline())
    except _WorkerComputeTimeout:
        cleanup_complete = _terminate_owned_process(process, process_group_id)
        authority.revoke()
        raise _worker_timeout_error(
            timeout_s,
            cleanup_complete=cleanup_complete,
        ) from None
    except _WorkerDeliveryTimeout as exc:
        cleanup_complete = _terminate_owned_process(process, process_group_id)
        authority.revoke()
        cleanup_suffix = (
            "" if cleanup_complete else "; owned process cleanup incomplete"
        )
        raise RuntimeError(
            "Node timeout worker result delivery exceeded bounded grace "
            f"(exitcode={process.exitcode}{cleanup_suffix})"
        ) from exc
    finally:
        if process.is_alive():
            _terminate_owned_process(process, process_group_id)
        _close_worker_process(process)
        _close_result_queue(result_queue)

    if status == "ok":
        return decode_node_outcome(payload)
    if status == "error":
        raise RuntimeError(str(payload))
    raise RuntimeError(f"Node timeout worker returned invalid status: {status!r}")


async def _execute_with_timeout_process_async(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    *,
    timeout_s: float,
    authority: _AttemptAuthority | None = None,
) -> NodeOutcome:
    if authority is None:
        authority = _AttemptAuthority()
        ctx = _build_attempt_context(ctx, authority)
        state = state.model_copy(deep=True)
    mp_ctx = mp.get_context("fork")
    result_queue: mp.Queue[Any] = mp_ctx.Queue(maxsize=1)
    group_ready = mp_ctx.Event()
    process = mp_ctx.Process(
        target=_node_execute_worker,
        args=(node, ctx, state, result_queue, group_ready),
        daemon=True,
    )
    compute_deadline = time.monotonic() + timeout_s
    process_group_id: int | None = None
    try:
        process.start()
        process_group_id = _owned_process_group_id(
            process,
            group_ready,
            deadline=compute_deadline,
        )
        status, payload = await _drain_result_async(
            process,
            result_queue,
            compute_deadline=compute_deadline,
        )
        await _join_worker_until_async(process, deadline=_delivery_deadline())
    except _WorkerComputeTimeout:
        cleanup_complete = _terminate_owned_process(process, process_group_id)
        authority.revoke()
        raise _worker_timeout_error(
            timeout_s,
            cleanup_complete=cleanup_complete,
        ) from None
    except _WorkerDeliveryTimeout as exc:
        cleanup_complete = _terminate_owned_process(process, process_group_id)
        authority.revoke()
        cleanup_suffix = (
            "" if cleanup_complete else "; owned process cleanup incomplete"
        )
        raise RuntimeError(
            "Node timeout worker result delivery exceeded bounded grace "
            f"(exitcode={process.exitcode}{cleanup_suffix})"
        ) from exc
    finally:
        if process.is_alive():
            _terminate_owned_process(process, process_group_id)
        _close_worker_process(process)
        _close_result_queue(result_queue)

    if status == "ok":
        return decode_node_outcome(payload)
    if status == "error":
        raise RuntimeError(str(payload))
    raise RuntimeError(f"Node timeout worker returned invalid status: {status!r}")


def _consume_finished_task(task: asyncio.Task[Any]) -> None:
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
) -> NodeOutcome:
    """Run an async attempt with a revocable authority boundary."""
    authority = _AttemptAuthority()
    worker_ctx = _build_attempt_context(ctx, authority)
    worker_state = state.model_copy(deep=True)
    task = asyncio.create_task(node.execute_async(worker_ctx, worker_state))
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=timeout_s)
    except TimeoutError:
        authority.revoke()
        task.add_done_callback(_consume_finished_task)
        raise NodeTimeoutError(
            f"Node exceeded timeout of {timeout_s}s",
        ) from None
    except asyncio.CancelledError:
        authority.revoke()
        task.add_done_callback(_consume_finished_task)
        raise


def _node_execute_worker(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    result_queue: mp.Queue[Any],
    group_ready: Any = None,
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
                        "failed to send result: "
                        f"{type(send_exc).__name__}: {send_exc}",
                    )
                )
            except _RETRY_RUNTIME_ERRORS as fallback_exc:
                raise RuntimeError(
                    "failed to send result: "
                    f"{type(send_exc).__name__}: {send_exc}"
                ) from fallback_exc

    try:
        outcome = node.execute(ctx, state)
        if hasattr(outcome, "model_dump"):
            _send("ok", outcome.model_dump(mode="python"))
        else:
            _send("error", f"invalid node outcome: {type(outcome).__name__}")
    except _RETRY_RUNTIME_ERRORS as exc:
        _send("error", f"{type(exc).__name__}: {exc}")


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
) -> NodeOutcome:
    """Async retry wrapper for ``AsyncWorkflowExecutor``.

    * Timeout: a bounded async task or worker with a revocable attempt authority.
    * Retry: loop + ``asyncio.sleep()``.
    """
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

    async def _invoke() -> NodeOutcome:
        if _has_async:
            if timeout_s is None:
                return await node.execute_async(ctx, state)
            return await _execute_with_timeout_async(
                node,
                ctx,
                state,
                timeout_s=timeout_s,
            )
        if timeout_s is not None:
            if _can_use_forked_timeout_worker():
                return await _execute_with_timeout_process_async(
                    node,
                    ctx,
                    state,
                    timeout_s=timeout_s,
                )
            return await run_blocking_async(
                _execute_with_timeout_sync,
                node,
                ctx,
                state,
                timeout_s=timeout_s,
                timeout_seconds=timeout_s,
            )
        return await run_blocking_async(node.execute, ctx, state)

    # Fast path
    if retry_policy.max_retries == 0 and timeout_s is None and circuit_breaker is None:
        if retry_stats is not None:
            retry_stats["attempts"] = 1
        return await _invoke()

    last_outcome: NodeOutcome | None = None
    node_id = str((getattr(node, "spec", None) and node.spec.metadata.component_id) or alias)

    for attempt in range(retry_policy.max_retries + 1):
        # Circuit breaker check
        if circuit_breaker is not None and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open for node {alias}",
            )

        try:
            outcome = await _invoke()

            if outcome.status != "fail":
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
                if retry_stats is not None:
                    retry_stats["attempts"] = attempt + 1
                return outcome

            if circuit_breaker is not None:
                circuit_breaker.record_failure()

            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                last_outcome = outcome
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s (attempt %d/%d) after %.1fs",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if retry_stats is not None:
                retry_stats["attempts"] = attempt + 1
            return outcome

        except (NodeTimeoutError, CircuitBreakerOpenError):
            raise
        except asyncio.CancelledError:
            _logger.info("Node %s cancelled during attempt %d", alias, attempt)
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            if attempt < retry_policy.max_retries:
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s after exception (attempt %d/%d): %s",
                    alias,
                    attempt + 1,
                    retry_policy.max_retries,
                    exc,
                )
                await asyncio.sleep(delay)
                continue

            if retry_stats is not None:
                retry_stats["attempts"] = attempt + 1
            dlq_ref = _persist_dead_letter(
                ctx,
                alias,
                node_id,
                exc,
                attempts=retry_policy.max_retries + 1,
                policy=retry_policy,
            )
            if dlq_ref is not None:
                ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_DEAD_LETTER",
                    outputs=[dlq_ref],
                )
            raise RetryExhaustedError(
                f"Node {alias}: all {retry_policy.max_retries} retries exhausted",
            ) from exc

    if last_outcome is not None:  # pragma: no cover
        return last_outcome
    raise RetryExhaustedError(  # pragma: no cover
        f"Node {alias}: all retries exhausted",
    )
