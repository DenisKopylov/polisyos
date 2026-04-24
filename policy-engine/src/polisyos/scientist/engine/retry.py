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
import logging
import multiprocessing as mp
import queue
import random
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.async_tools import get_shared_executor, run_blocking_async
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.scientist.engine.errors import (
    CircuitBreakerOpenError,
    NodeTimeoutError,
    RetryExhaustedError,
)
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.error_semantics import emit_degraded_path

if TYPE_CHECKING:
    from polisyos.scientist.engine.circuit_breaker import CircuitBreaker
    from polisyos.scientist.engine.context import ExecutionContext
    from polisyos.scientist.engine.state import ExperimentState

_logger = logging.getLogger(__name__)

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
                    name="polisyos.scientist.engine.DeadLetter",
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


def execute_with_retry_sync(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    retry_policy: RetryPolicy,
    timeout_s: float | None,
    alias: str,
    circuit_breaker: CircuitBreaker | None = None,
) -> NodeOutcome:
    """Sync retry wrapper for ``WorkflowExecutor``.

    * Timeout: runs ``node.execute`` in a thread with
      ``concurrent.futures.Future.result(timeout=...)``.
    * Retry: loops up to ``max_retries``, exponential backoff via ``time.sleep()``.
    """
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
    if _can_use_forked_timeout_worker():
        return _execute_with_timeout_process(node, ctx, state, timeout_s=timeout_s)

    future = get_shared_executor().submit(node.execute, ctx, state)
    try:
        return future.result(timeout=timeout_s)
    except FuturesTimeoutError:
        future.cancel()
        raise NodeTimeoutError(
            f"Node exceeded timeout of {timeout_s}s",
        ) from None


def _can_use_forked_timeout_worker() -> bool:
    try:
        return "fork" in mp.get_all_start_methods()
    except (RuntimeError, ValueError):
        return False


def _execute_with_timeout_process(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    timeout_s: float,
) -> NodeOutcome:
    mp_ctx = mp.get_context("fork")
    result_queue: mp.Queue[Any] = mp_ctx.Queue(maxsize=1)
    process = mp_ctx.Process(
        target=_node_execute_worker,
        args=(node, ctx, state, result_queue),
        daemon=True,
    )
    process.start()
    process.join(timeout=timeout_s)
    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=1.0)
        result_queue.close()
        result_queue.join_thread()
        raise NodeTimeoutError(
            f"Node exceeded timeout of {timeout_s}s",
        ) from None

    try:
        status, payload = result_queue.get_nowait()
    except queue.Empty as exc:
        raise RuntimeError(
            f"Node timeout worker exited without result (exitcode={process.exitcode})"
        ) from exc
    finally:
        result_queue.close()
        result_queue.join_thread()

    if status == "ok":
        return NodeOutcome.model_validate(payload)
    if status == "error":
        raise RuntimeError(str(payload))
    raise RuntimeError(f"Node timeout worker returned invalid status: {status!r}")


async def _execute_with_timeout_process_async(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    timeout_s: float,
) -> NodeOutcome:
    mp_ctx = mp.get_context("fork")
    result_queue: mp.Queue[Any] = mp_ctx.Queue(maxsize=1)
    process = mp_ctx.Process(
        target=_node_execute_worker,
        args=(node, ctx, state, result_queue),
        daemon=True,
    )
    process.start()
    deadline = time.monotonic() + timeout_s
    while process.is_alive() and time.monotonic() < deadline:
        await asyncio.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=1.0)
        result_queue.close()
        result_queue.join_thread()
        raise NodeTimeoutError(
            f"Node exceeded timeout of {timeout_s}s",
        ) from None

    try:
        status, payload = result_queue.get_nowait()
    except queue.Empty as exc:
        raise RuntimeError(
            f"Node timeout worker exited without result (exitcode={process.exitcode})"
        ) from exc
    finally:
        result_queue.close()
        result_queue.join_thread()

    if status == "ok":
        return NodeOutcome.model_validate(payload)
    if status == "error":
        raise RuntimeError(str(payload))
    raise RuntimeError(f"Node timeout worker returned invalid status: {status!r}")


def _node_execute_worker(
    node: Any,
    ctx: ExecutionContext,
    state: ExperimentState,
    result_queue: mp.Queue[Any],
) -> None:
    try:
        outcome = node.execute(ctx, state)
        if hasattr(outcome, "model_dump"):
            result_queue.put(("ok", outcome.model_dump(mode="python")))
        else:
            result_queue.put(("error", f"invalid node outcome: {type(outcome).__name__}"))
    except _RETRY_RUNTIME_ERRORS as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


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
) -> NodeOutcome:
    """Async retry wrapper for ``AsyncWorkflowExecutor``.

    * Timeout: ``asyncio.wait_for(asyncio.to_thread(...), timeout=...)``.
    * Retry: loop + ``asyncio.sleep()``.
    """
    # Detect real execute_async (not MagicMock auto-generated attributes).
    # Check the class dict to avoid MagicMock's __getattr__ false positives.
    _has_async = "execute_async" in type(node).__dict__ or (
        hasattr(node, "__class__")
        and any("execute_async" in getattr(klass, "__dict__", {}) for klass in type(node).__mro__)
    )

    async def _invoke() -> NodeOutcome:
        if _has_async:
            return await node.execute_async(ctx, state)
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
            if timeout_s is not None and _has_async:
                coro = _invoke()
                try:
                    outcome = await asyncio.wait_for(coro, timeout=timeout_s)
                except TimeoutError:
                    raise NodeTimeoutError(
                        f"Node exceeded timeout of {timeout_s}s",
                    ) from None
            else:
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
