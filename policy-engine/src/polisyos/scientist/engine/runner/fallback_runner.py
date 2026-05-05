"""Fallback workflow runner — graceful degradation to local execution.

Wraps a primary (distributed) runner with a health check.  When the
primary is unhealthy the runner transparently falls back to a local
``LocalWorkflowRunner``, emitting a warning log and an OTel event.

Health status is cached with a configurable TTL to avoid probing
on every call.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from polisyos.scientist.engine.error_semantics import emit_degraded_path
from polisyos.scientist.engine.runner.local_runner import LocalWorkflowRunner
from polisyos.scientist.engine.runner.protocol import RunnerHealth
from polisyos.scientist.engine.state_merge import MergeConflictPolicy

_logger = logging.getLogger(__name__)
_PRIMARY_EXECUTION_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


class FallbackWorkflowRunner:
    """Wrapper that falls back to local execution when the primary runner is unhealthy.

    Parameters
    ----------
    primary:
        The distributed runner (Ray, Temporal, etc.).
    health_ttl_s:
        Seconds to cache the last health check result (default 30).
    max_parallelism:
        Max parallelism for the fallback local runner.
    """

    def __init__(
        self,
        primary: Any,
        *,
        health_ttl_s: float = 30.0,
        max_parallelism: int = 4,
        merge_conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
    ) -> None:
        self._primary = primary
        self._fallback = LocalWorkflowRunner(
            max_parallelism=max_parallelism,
            merge_conflict_policy=merge_conflict_policy,
        )
        self._health_ttl_s = health_ttl_s
        self._last_health: RunnerHealth | None = None
        self._last_health_at: float = 0.0

    async def health_check(self) -> RunnerHealth:
        """Probe the primary runner, caching the result for ``health_ttl_s``."""
        now = time.monotonic()
        if self._last_health is not None and (now - self._last_health_at) < self._health_ttl_s:
            return self._last_health

        health = await self._primary.health_check()
        self._last_health = health
        self._last_health_at = now
        return health

    async def execute_workflow(
        self,
        workflow: Any,
        state: Any,
        ctx: Any,
        registry: Any,
        *,
        checkpoint_hook: Any | None = None,
        checkpoint_cache_seed_refs: Any | None = None,
        max_parallelism: int = 4,
    ) -> Any:
        """Execute workflow via the primary runner, falling back to local on failure."""
        health = await self.health_check()

        if health.healthy:
            try:
                return await self._primary.execute_workflow(
                    workflow,
                    state,
                    ctx,
                    registry,
                    checkpoint_hook=checkpoint_hook,
                    checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
                    max_parallelism=max_parallelism,
                )
            except _PRIMARY_EXECUTION_ERRORS as exc:
                emit_degraded_path(
                    component="engine.runner.fallback",
                    operation="execute_primary",
                    reason="primary_runner_execution_failed",
                    exc=exc,
                    details={"backend": health.backend, "message": health.message},
                    log=_logger,
                )
                _logger.warning(
                    "Primary runner (%s) raised during execution; falling back to local",
                    health.backend,
                )
        else:
            emit_degraded_path(
                component="engine.runner.fallback",
                operation="probe_primary",
                reason="primary_runner_unhealthy",
                message=health.message,
                error_type="runner_unhealthy",
                details={"backend": health.backend},
                log=_logger,
            )
            _logger.warning(
                "Primary runner (%s) unhealthy: %s — falling back to local",
                health.backend,
                health.message,
            )
            # Invalidate cache so next call re-probes
            self._last_health = None

        return await self._fallback.execute_workflow(
            workflow,
            state,
            ctx,
            registry,
            checkpoint_hook=checkpoint_hook,
            checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
            max_parallelism=max_parallelism,
        )
