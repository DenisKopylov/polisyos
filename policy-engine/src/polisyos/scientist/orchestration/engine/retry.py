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
from polisyos.scientist.orchestration.engine.state_branching import branch_state

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


@dataclasses.dataclass
class _WorkerLifecycle:
    """Shared state for one forked worker's compute and cleanup lifetimes."""

    compute_deadline: float
    completion_time: Any
    process_group_id: int | None = None

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


def _exception_retry_category(exc: BaseException) -> str:
    """Classify the original exception before any process transport."""
    # Import lazily because ``runner.protocol`` imports ``RetryPolicy``.  A
    # module-level import would make the direct ``engine.retry`` import enter
    # ``runner.__init__`` while ``RetryPolicy`` is still being defined.
    from polisyos.scientist.orchestration.engine.runner.error_classifier import (
        RemoteErrorCategory,
        classify_remote_error,
    )

    typed_category = _typed_error_category(exc)
    if typed_category in {"fatal", "validation"}:
        return typed_category
    if typed_category == "transient":
        category = RemoteErrorCategory.TRANSIENT
    else:
        category = classify_remote_error(exc)
    if category is RemoteErrorCategory.FATAL:
        return category.value
    if isinstance(exc, (AssertionError, AttributeError, LookupError)):
        return "fatal"
    return category.value


def _exception_retry_code(exc: BaseException) -> str:
    """Preserve explicit codes while retaining the established fallback."""
    error_code = getattr(exc, "code", None)
    if not isinstance(error_code, str) or not error_code:
        error_code = "node.exception"
    return error_code


def _should_retry_exception(exc: BaseException, policy: RetryPolicy) -> bool:
    """Apply original category and code semantics to direct or transported errors."""
    return (
        _exception_retry_category(exc)
        not in {
            "fatal",
            "validation",
        }
        and _exception_retry_code(exc) in policy.retry_on
    )


class _WorkerNodeError(RuntimeError):
    """Carry worker retry identity without reconstructing arbitrary exceptions."""

    def __init__(self, message: str, *, category: str, code: str) -> None:
        super().__init__(message)
        self.category = category
        self.code = code


def _worker_error_payload(exc: BaseException) -> dict[str, str]:
    """Send bounded retry identity alongside the existing diagnostic message."""
    return {
        "message": f"{type(exc).__name__}: {exc}",
        "category": _exception_retry_category(exc),
        "code": _exception_retry_code(exc),
    }


def _worker_error_from_payload(payload: Any) -> RuntimeError:
    """Restore semantic fields; legacy transport diagnostics remain opaque."""
    if isinstance(payload, dict):
        message, category, code = (payload.get(key) for key in ("message", "category", "code"))
        if (
            isinstance(message, str)
            and isinstance(category, str)
            and category in {"transient", "fatal", "validation", "unknown"}
            and isinstance(code, str)
            and code
        ):
            return _WorkerNodeError(message, category=category, code=code)
        return _WorkerNodeError(
            "invalid node error payload", category="fatal", code="node.invalid_error"
        )
    return RuntimeError(str(payload))


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
    before = _spend_snapshot(baseline)
    after = _spend_snapshot(attempt_state)
    delta: dict[str, Decimal] = {}
    for key, value in after.items():
        change = value - before.get(key, Decimal(0))
        if change > 0:
            delta[key] = change
    return delta


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

    * Timeout: fork worker when available, with an owned Linux supervisor;
      otherwise a shared thread with revocable attempt authority.
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
    failed_spend: dict[str, Decimal] = {}
    node_id = str((getattr(node, "spec", None) and node.spec.metadata.component_id) or alias)

    for attempt in range(retry_policy.max_retries + 1):
        # Circuit breaker check
        if circuit_breaker is not None and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open for node {alias}",
            )

        attempt_state = _fresh_retry_state(state, node) if retry_policy.max_retries > 0 else state
        try:
            if timeout_s is not None:
                outcome = _execute_with_timeout_sync(
                    node,
                    ctx,
                    attempt_state,
                    timeout_s=timeout_s,
                )
            else:
                outcome = node.execute(ctx, attempt_state)

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
                time.sleep(delay)
                continue

            _merge_spend(outcome.state, failed_spend)
            return outcome

        except (NodeTimeoutError, CircuitBreakerOpenError):
            raise
        except KeyboardInterrupt:
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            attempt_spend = _spend_delta(state, attempt_state)
            _accumulate_spend(failed_spend, attempt_spend)
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
                time.sleep(delay)
                continue

            _merge_spend(state, failed_spend)
            dlq_ref = _persist_dead_letter(
                ctx,
                alias,
                node_id,
                exc,
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
    done, _pending = wait({future}, timeout=timeout_s)
    if future not in done:
        future.cancel()
        authority.revoke()
        raise NodeTimeoutError(
            f"Node exceeded timeout of {timeout_s}s",
        ) from None
    # Read the result after the completion decision. A node's own TimeoutError
    # is a transient provider failure, not evidence that this wait expired.
    return future.result()


def _can_use_forked_timeout_worker() -> bool:
    try:
        return "fork" in mp.get_all_start_methods()
    except (RuntimeError, ValueError):
        return False


def _delivery_deadline() -> float:
    """Return a bounded deadline for Queue feeder delivery."""
    return time.monotonic() + _PROCESS_DELIVERY_GRACE_S


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
    if process_group_id is None:
        # A direct Process handle proves only worker termination; descendant
        # absence is not established without the owned-group handshake.
        return False
    return not process.is_alive() and group_clean


def _close_worker_process(process: mp.Process) -> None:
    """Release process resources after the owned process has stopped."""
    if process.pid is None:
        process.close()
        return
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
    completion_time: Any = None,
) -> tuple[str, Any]:
    """Receive a worker result without joining before Queue drain."""
    while process.is_alive() and not _completion_before_deadline(
        completion_time,
        compute_deadline,
    ):
        remaining = compute_deadline - time.monotonic()
        if remaining <= 0:
            raise _WorkerComputeTimeout
        try:
            result = result_queue.get(timeout=min(_PROCESS_RESULT_POLL_S, remaining))
        except queue.Empty:
            continue
        if not _completion_before_deadline(completion_time, compute_deadline):
            raise _WorkerComputeTimeout
        return result

    if not _completion_before_deadline(completion_time, compute_deadline):
        raise _WorkerComputeTimeout

    delivery_deadline = _delivery_deadline()
    while time.monotonic() < delivery_deadline:
        remaining = delivery_deadline - time.monotonic()
        try:
            return result_queue.get(timeout=min(_PROCESS_RESULT_POLL_S, remaining))
        except queue.Empty:
            continue
    raise _WorkerDeliveryTimeout


async def _drain_result_async(
    process: mp.Process,
    result_queue: mp.Queue[Any],
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
    return NodeTimeoutError(f"Node exceeded timeout of {timeout_s}s{suffix}")


def _enable_linux_child_subreaper() -> None:
    """Adopt orphaned descendants only inside the owned supervisor process."""
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _node_execute_supervisor(
    node: Any,
    ctx: Any,
    state: ExperimentState,
    result_queue: mp.Queue[Any],
    group_ready: Any,
    completion_time: Any,
) -> None:
    """Own computation and reap its process tree before reporting worker exit.

    Linux PID1 may retain orphan zombies indefinitely. An isolated subreaper
    keeps that reaping obligation here, without changing the caller process.
    Descendants that leave the process group are adopted when their parent
    exits and killed through the kernel parent relation. This is ownership
    and cleanup, not a sandbox against a deliberately escaping node.
    """
    stopping = False

    def _request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stopping
        stopping = True

    try:
        _enable_linux_child_subreaper()
        os.setsid()
        signal.signal(signal.SIGTERM, _request_stop)
        group_ready.set()
        worker_pid = os.fork()
    except _RETRY_RUNTIME_ERRORS as exc:
        completion_time.value = time.monotonic()
        result_queue.put(("error", f"worker supervision failed: {type(exc).__name__}: {exc}"))
        return

    if worker_pid == 0:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        if stopping:
            os._exit(1)
        exit_code = 0
        try:
            _node_execute_worker(node, ctx, state, result_queue, completion_time=completion_time)
        except BaseException:
            exit_code = 1
        finally:
            # os._exit does not run multiprocessing's Queue finalizers. Flush
            # while the caller drains; large results must not vanish on exit.
            _close_result_queue(result_queue)
        os._exit(exit_code)

    worker_stopped = False
    cleanup_deadline: float | None = None
    while True:
        try:
            child_pid, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if child_pid > 0:
            worker_stopped = worker_stopped or child_pid == worker_pid
            continue
        if (stopping or worker_stopped) and cleanup_deadline is None:
            cleanup_deadline = time.monotonic() + _PROCESS_CLEANUP_GRACE_S / 2
            # Our handler keeps the supervisor alive to reap every killed child.
            os.killpg(os.getpgrp(), signal.SIGTERM)
        if cleanup_deadline is not None and time.monotonic() >= cleanup_deadline:
            # SIGKILL cannot target our group without killing the reaper itself.
            # Only the supervisor's current, adopted direct children are ours.
            # Read the kernel parent relation: task/children is absent on kernels
            # without CONFIG_CHECKPOINT_RESTORE. Unreaped children cannot have
            # their PIDs reused between this read and the next waitpid call.
            from pathlib import Path

            for process_path in Path("/proc").iterdir():
                if not process_path.name.isdecimal():
                    continue
                try:
                    process_stat = (process_path / "stat").read_text()
                except (FileNotFoundError, ProcessLookupError):
                    continue
                parent_pid = int(process_stat.rsplit(")", 1)[1].split()[1])
                if parent_pid == os.getpid():
                    try:
                        os.kill(int(process_path.name), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        time.sleep(_PROCESS_RESULT_POLL_S)


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
    completion_time = mp_ctx.Value("d", 0.0)
    process = mp_ctx.Process(
        target=_node_execute_supervisor if sys.platform == "linux" else _node_execute_worker,
        args=(node, ctx, state, result_queue, group_ready, completion_time),
        daemon=True,
    )
    lifecycle = _WorkerLifecycle(
        compute_deadline=time.monotonic() + timeout_s,
        completion_time=completion_time,
    )
    try:
        process.start()
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
        _join_worker_until(process, deadline=_delivery_deadline())
        if process.exitcode != 0:
            raise RuntimeError(f"Node timeout worker cleanup failed (exitcode={process.exitcode})")
    except _WorkerComputeTimeout:
        cleanup_complete = _terminate_owned_process(
            process,
            lifecycle.process_group_id,
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
        )
        authority.revoke()
        cleanup_suffix = "" if cleanup_complete else "; owned process cleanup incomplete"
        raise RuntimeError(
            "Node timeout worker result delivery exceeded bounded grace "
            f"(exitcode={process.exitcode}{cleanup_suffix})"
        ) from exc
    finally:
        if process.is_alive() or _owned_process_group_is_alive(lifecycle.process_group_id):
            _terminate_owned_process(process, lifecycle.process_group_id)
        _close_worker_process(process)
        _close_result_queue(result_queue)

    if status == "ok":
        from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome

        if isinstance(payload, (bytes, bytearray, memoryview, str)) or (
            isinstance(payload, list) and all(isinstance(item, int) for item in payload)
        ):
            return deserialize_outcome(payload)
        return decode_node_outcome(payload)
    if status == "error":
        raise _worker_error_from_payload(payload)
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
    completion_time = mp_ctx.Value("d", 0.0)
    process = mp_ctx.Process(
        target=_node_execute_supervisor if sys.platform == "linux" else _node_execute_worker,
        args=(node, ctx, state, result_queue, group_ready, completion_time),
        daemon=True,
    )
    lifecycle = _WorkerLifecycle(
        compute_deadline=time.monotonic() + timeout_s,
        completion_time=completion_time,
    )
    try:
        process.start()
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
        await _join_worker_until_async(process, deadline=_delivery_deadline())
        if process.exitcode != 0:
            raise RuntimeError(f"Node timeout worker cleanup failed (exitcode={process.exitcode})")
    except _WorkerComputeTimeout:
        cleanup_complete = _terminate_owned_process(
            process,
            lifecycle.process_group_id,
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
        )
        authority.revoke()
        cleanup_suffix = "" if cleanup_complete else "; owned process cleanup incomplete"
        raise RuntimeError(
            "Node timeout worker result delivery exceeded bounded grace "
            f"(exitcode={process.exitcode}{cleanup_suffix})"
        ) from exc
    finally:
        if process.is_alive() or _owned_process_group_is_alive(lifecycle.process_group_id):
            _terminate_owned_process(process, lifecycle.process_group_id)
        _close_worker_process(process)
        _close_result_queue(result_queue)

    if status == "ok":
        from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome

        if isinstance(payload, (bytes, bytearray, memoryview, str)) or (
            isinstance(payload, list) and all(isinstance(item, int) for item in payload)
        ):
            return deserialize_outcome(payload)
        return decode_node_outcome(payload)
    if status == "error":
        raise _worker_error_from_payload(payload)
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
) -> NodeOutcome:
    """Run an async attempt with a revocable authority boundary."""
    authority = _AttemptAuthority()
    worker_ctx = _build_attempt_context(ctx, authority)
    worker_state = state.model_copy(deep=True)
    task = asyncio.create_task(node.execute_async(worker_ctx, worker_state))
    return await _await_timed_attempt(task, authority, timeout_s=timeout_s)


async def _execute_with_timeout_thread_async(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    timeout_s: float,
) -> NodeOutcome:
    """Own one executor future, including queue time, without a nested timeout."""
    authority = _AttemptAuthority()
    worker_ctx = _build_attempt_context(ctx, authority)
    worker_state = state.model_copy(deep=True)
    context = contextvars.copy_context()
    future = get_shared_executor().submit(context.run, node.execute, worker_ctx, worker_state)
    task = asyncio.wrap_future(future)
    try:
        return await _await_timed_attempt(task, authority, timeout_s=timeout_s)
    except (NodeTimeoutError, asyncio.CancelledError):
        # Cancelling only the asyncio wrapper defers forwarding to a loop
        # callback. Refuse the actual queued compute before a worker is freed.
        future.cancel()
        raise


async def _await_timed_attempt(
    task: asyncio.Future[NodeOutcome], authority: _AttemptAuthority, *, timeout_s: float
) -> NodeOutcome:
    """Separate wrapper expiration from an exception in a completed attempt."""
    try:
        done, _pending = await asyncio.wait({task}, timeout=timeout_s)
        if task not in done:
            authority.revoke()
            task.add_done_callback(_consume_finished_task)
            raise NodeTimeoutError(
                f"Node exceeded timeout of {timeout_s}s",
            ) from None
        return task.result()
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
            _send("error", f"invalid node outcome: {type(outcome).__name__}")
    except _RETRY_RUNTIME_ERRORS as exc:
        _mark_completion()
        _send("error", _worker_error_payload(exc))


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

    async def _invoke(attempt_state: ExperimentState) -> NodeOutcome:
        if _has_async:
            if timeout_s is None:
                return await node.execute_async(ctx, attempt_state)
            return await _execute_with_timeout_async(
                node,
                ctx,
                attempt_state,
                timeout_s=timeout_s,
            )
        if timeout_s is not None:
            if _can_use_forked_timeout_worker():
                return await _execute_with_timeout_process_async(
                    node,
                    ctx,
                    attempt_state,
                    timeout_s=timeout_s,
                )
            return await _execute_with_timeout_thread_async(
                node,
                ctx,
                attempt_state,
                timeout_s=timeout_s,
            )
        return await run_blocking_async(node.execute, ctx, attempt_state)

    # Fast path
    if retry_policy.max_retries == 0 and timeout_s is None and circuit_breaker is None:
        if retry_stats is not None:
            retry_stats["attempts"] = 1
        return await _invoke(state)

    last_outcome: NodeOutcome | None = None
    failed_spend: dict[str, Decimal] = {}
    node_id = str((getattr(node, "spec", None) and node.spec.metadata.component_id) or alias)

    for attempt in range(retry_policy.max_retries + 1):
        # Circuit breaker check
        if circuit_breaker is not None and not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{circuit_breaker.name}' is open for node {alias}",
            )

        attempt_state = _fresh_retry_state(state, node) if retry_policy.max_retries > 0 else state
        try:
            outcome = await _invoke(attempt_state)

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
                await asyncio.sleep(delay)
                continue

            if retry_stats is not None:
                retry_stats["attempts"] = attempt + 1
            _merge_spend(outcome.state, failed_spend)
            return outcome

        except (NodeTimeoutError, CircuitBreakerOpenError):
            raise
        except asyncio.CancelledError:
            _logger.info("Node %s cancelled during attempt %d", alias, attempt)
            raise
        except _RETRY_RUNTIME_ERRORS as exc:
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            attempt_spend = _spend_delta(state, attempt_state)
            _accumulate_spend(failed_spend, attempt_spend)
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
                await asyncio.sleep(delay)
                continue

            if retry_stats is not None:
                retry_stats["attempts"] = attempt + 1
            _merge_spend(state, failed_spend)
            dlq_ref = _persist_dead_letter(
                ctx,
                alias,
                node_id,
                exc,
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
            ) from exc

    if last_outcome is not None:  # pragma: no cover
        return last_outcome
    raise RetryExhaustedError(  # pragma: no cover
        f"Node {alias}: all retries exhausted",
    )
