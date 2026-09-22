"""Fallback workflow runner — graceful degradation to local execution.

Wraps a primary (distributed) runner with a health check.  A local fallback
is used only when a typed pre-dispatch health decision authorizes it; an
invocation whose outcome is unknown is never replayed locally.

Health status is cached with a configurable TTL to avoid probing
on every call.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.runner.local_runner import LocalWorkflowRunner
from polisyos.scientist.orchestration.engine.runner.protocol import RunnerHealth
from polisyos.scientist.orchestration.engine.state_merge import MergeConflictPolicy

_logger = logging.getLogger(__name__)
_PRIMARY_EXECUTION_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


class HealthFailureDisposition(StrEnum):
    """Typed authority decision for a pre-dispatch primary health failure."""

    ALLOW = "allow_local_fallback"
    BLOCK = "block_local_fallback"


HealthFailureClassifier = Callable[[RunnerHealth], HealthFailureDisposition]


class PrimaryExecutionOutcomeUnknownError(RuntimeError):
    """The primary was invoked but its terminal outcome was not established."""


class FallbackNotAuthorizedError(RuntimeError):
    """The primary health failure did not carry permission for local execution."""


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
    health_failure_classifier:
        Typed authority resolver for a pre-dispatch unhealthy result.  If no
        resolver is supplied by the primary or caller, fallback is denied.
    """

    def __init__(
        self,
        primary: Any,
        *,
        health_ttl_s: float = 30.0,
        max_parallelism: int = 4,
        merge_conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
        health_failure_classifier: HealthFailureClassifier | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = LocalWorkflowRunner(
            max_parallelism=max_parallelism,
            merge_conflict_policy=merge_conflict_policy,
        )
        self._health_ttl_s = health_ttl_s
        self._health_failure_classifier = health_failure_classifier
        self._last_health: RunnerHealth | None = None
        self._last_health_at: float = 0.0

    def _classify_health_failure(self, health: RunnerHealth) -> HealthFailureDisposition:
        """Resolve explicit pre-dispatch fallback authority without parsing prose."""
        classifier = self._health_failure_classifier
        if classifier is None:
            candidate = getattr(self._primary, "classify_health_failure", None)
            if callable(candidate):
                classifier = candidate
        if classifier is None:
            return HealthFailureDisposition.BLOCK
        try:
            disposition = classifier(health)
        except Exception as exc:  # pragma: no cover - defensive authority boundary
            raise FallbackNotAuthorizedError(
                "primary health failure classifier did not establish fallback authority"
            ) from exc
        if not isinstance(disposition, HealthFailureDisposition):
            raise FallbackNotAuthorizedError(
                "primary health failure classifier returned an untyped disposition"
            )
        return disposition

    async def _execute_local_fallback(
        self,
        workflow: Any,
        state: Any,
        ctx: Any,
        registry: Any,
        *,
        checkpoint_hook: Any | None,
        checkpoint_cache_seed_refs: Any | None,
        max_parallelism: int,
        health: RunnerHealth,
    ) -> Any:
        """Execute local work only after an explicit pre-dispatch typed decision."""
        disposition = self._classify_health_failure(health)
        if disposition is not HealthFailureDisposition.ALLOW:
            emit_degraded_path(
                component="engine.runner.fallback",
                operation="probe_primary",
                reason="primary_fallback_not_authorized",
                message=health.message,
                error_type="fallback_not_authorized",
                details={"backend": health.backend},
                log=_logger,
            )
            raise FallbackNotAuthorizedError(
                f"fallback is not authorized for {health.backend} health failure"
            )
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
            "Primary runner (%s) unhealthy before dispatch; using authorized local fallback",
            health.backend,
        )
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
        try:
            health = await self.health_check()
        except _PRIMARY_EXECUTION_ERRORS as exc:
            health = RunnerHealth(
                backend=type(self._primary).__name__,
                healthy=False,
                message="primary health probe raised before dispatch",
            )
            try:
                return await self._execute_local_fallback(
                    workflow,
                    state,
                    ctx,
                    registry,
                    checkpoint_hook=checkpoint_hook,
                    checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
                    max_parallelism=max_parallelism,
                    health=health,
                )
            except FallbackNotAuthorizedError as fallback_exc:
                raise fallback_exc from exc

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
                    reason="primary_execution_outcome_unknown",
                    exc=exc,
                    details={"backend": health.backend, "message": health.message},
                    log=_logger,
                )
                raise PrimaryExecutionOutcomeUnknownError(
                    "primary execution outcome is unknown; reconcile before handover"
                ) from exc
        else:
            return await self._execute_local_fallback(
                workflow,
                state,
                ctx,
                registry,
                checkpoint_hook=checkpoint_hook,
                checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
                max_parallelism=max_parallelism,
                health=health,
            )


__all__ = [
    "FallbackNotAuthorizedError",
    "FallbackWorkflowRunner",
    "HealthFailureClassifier",
    "HealthFailureDisposition",
    "PrimaryExecutionOutcomeUnknownError",
]
