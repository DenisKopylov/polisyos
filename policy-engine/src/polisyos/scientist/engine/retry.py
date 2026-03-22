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
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.engine.errors import NodeTimeoutError, RetryExhaustedError
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome

if TYPE_CHECKING:
    from polisyos.scientist.engine.context import ExecutionContext
    from polisyos.scientist.engine.state import ExperimentState

_logger = logging.getLogger(__name__)


class RetryPolicy(BaseModel):
    """Declarative retry configuration attached to a :class:`NodeInvocation`."""

    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(default=0, ge=0, le=5)
    backoff_base_s: float = Field(default=1.0, ge=0.1, le=60.0)
    backoff_factor: float = Field(default=2.0, ge=1.0, le=10.0)
    retry_on: list[str] = Field(
        default_factory=lambda: ["node.exception"],
        description="Error codes that trigger retry",
    )


def _should_retry(error: NodeError | None, policy: RetryPolicy) -> bool:
    if error is None:
        return False
    return error.code in policy.retry_on


def _backoff_delay(attempt: int, policy: RetryPolicy) -> float:
    return policy.backoff_base_s * (policy.backoff_factor ** attempt)


def execute_with_retry_sync(
    node: Any,
    ctx: "ExecutionContext",
    state: "ExperimentState",
    *,
    retry_policy: RetryPolicy,
    timeout_s: float | None,
    alias: str,
) -> NodeOutcome:
    """Sync retry wrapper for ``WorkflowExecutor``.

    * Timeout: runs ``node.execute`` in a thread with
      ``concurrent.futures.Future.result(timeout=...)``.
    * Retry: loops up to ``max_retries``, exponential backoff via ``time.sleep()``.
    """
    # Fast path — no retry, no timeout
    if retry_policy.max_retries == 0 and timeout_s is None:
        return node.execute(ctx, state)

    last_error: Exception | None = None
    last_outcome: NodeOutcome | None = None

    for attempt in range(retry_policy.max_retries + 1):
        try:
            if timeout_s is not None:
                outcome = _execute_with_timeout_sync(node, ctx, state, timeout_s=timeout_s)
            else:
                outcome = node.execute(ctx, state)

            if outcome.status != "fail":
                return outcome

            # Node returned a "fail" outcome — check retry_on filter
            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                last_outcome = outcome
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s (attempt %d/%d) after %.1fs",
                    alias, attempt + 1, retry_policy.max_retries, delay,
                )
                ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_RETRY",
                    metrics={"attempt": attempt + 1, "delay_s": delay},
                )
                time.sleep(delay)
                continue

            return outcome

        except NodeTimeoutError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retry_policy.max_retries:
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s after exception (attempt %d/%d): %s",
                    alias, attempt + 1, retry_policy.max_retries, exc,
                )
                ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_RETRY",
                    metrics={"attempt": attempt + 1, "delay_s": delay},
                )
                time.sleep(delay)
                continue
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
    ctx: "ExecutionContext",
    state: "ExperimentState",
    *,
    timeout_s: float,
) -> NodeOutcome:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(node.execute, ctx, state)
        try:
            return future.result(timeout=timeout_s)
        except FuturesTimeoutError:
            future.cancel()
            raise NodeTimeoutError(
                f"Node exceeded timeout of {timeout_s}s",
            ) from None


async def execute_with_retry_async(
    node: Any,
    ctx: "ExecutionContext",
    state: "ExperimentState",
    *,
    retry_policy: RetryPolicy,
    timeout_s: float | None,
    alias: str,
) -> NodeOutcome:
    """Async retry wrapper for ``AsyncWorkflowExecutor``.

    * Timeout: ``asyncio.wait_for(asyncio.to_thread(...), timeout=...)``.
    * Retry: loop + ``asyncio.sleep()``.
    """
    # Fast path
    if retry_policy.max_retries == 0 and timeout_s is None:
        return await asyncio.to_thread(node.execute, ctx, state)

    last_outcome: NodeOutcome | None = None

    for attempt in range(retry_policy.max_retries + 1):
        try:
            coro = asyncio.to_thread(node.execute, ctx, state)
            if timeout_s is not None:
                try:
                    outcome = await asyncio.wait_for(coro, timeout=timeout_s)
                except asyncio.TimeoutError:
                    raise NodeTimeoutError(
                        f"Node exceeded timeout of {timeout_s}s",
                    ) from None
            else:
                outcome = await coro

            if outcome.status != "fail":
                return outcome

            if attempt < retry_policy.max_retries and _should_retry(outcome.error, retry_policy):
                last_outcome = outcome
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s (attempt %d/%d) after %.1fs",
                    alias, attempt + 1, retry_policy.max_retries, delay,
                )
                await asyncio.sleep(delay)
                continue

            return outcome

        except NodeTimeoutError:
            raise
        except Exception as exc:  # noqa: BLE001
            if attempt < retry_policy.max_retries:
                delay = _backoff_delay(attempt, retry_policy)
                _logger.info(
                    "Retrying node %s after exception (attempt %d/%d): %s",
                    alias, attempt + 1, retry_policy.max_retries, exc,
                )
                await asyncio.sleep(delay)
                continue
            raise RetryExhaustedError(
                f"Node {alias}: all {retry_policy.max_retries} retries exhausted",
            ) from exc

    if last_outcome is not None:  # pragma: no cover
        return last_outcome
    raise RetryExhaustedError(  # pragma: no cover
        f"Node {alias}: all retries exhausted",
    )
