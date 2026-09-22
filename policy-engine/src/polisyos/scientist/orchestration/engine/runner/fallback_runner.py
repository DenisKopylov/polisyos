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
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from polisyos.core.errors import ErrorCategory, PolicyOSError
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
    PolicyOSError,
)


class HealthFailureDisposition(StrEnum):
    """Typed authority decision for a pre-dispatch primary health failure."""

    ALLOW = "allow_local_fallback"
    BLOCK = "block_local_fallback"


HealthFailureClassifier = Callable[[RunnerHealth], HealthFailureDisposition]


@dataclass(frozen=True)
class _HealthFailureSample:
    """Private, probe-bound authority emitted by a concrete backend."""

    health: RunnerHealth
    disposition: HealthFailureDisposition
    probe_id: int


_HealthSampleProvider = Callable[[], object]


def _classify_health_probe_exception(exc: BaseException) -> HealthFailureDisposition:
    """Classify a probe exception using typed facts, never its message."""

    if isinstance(exc, PolicyOSError):
        return (
            HealthFailureDisposition.ALLOW
            if exc.category == ErrorCategory.TRANSIENT
            else HealthFailureDisposition.BLOCK
        )
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return HealthFailureDisposition.ALLOW
    return HealthFailureDisposition.BLOCK


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
    _health_sample_provider:
        Private backend probe hand-off used by the factory.  It is deliberately
        not part of the public runner configuration contract.
    """

    def __init__(
        self,
        primary: Any,
        *,
        health_ttl_s: float = 30.0,
        max_parallelism: int = 4,
        merge_conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
        health_failure_classifier: HealthFailureClassifier | None = None,
        _health_sample_provider: _HealthSampleProvider | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = LocalWorkflowRunner(
            max_parallelism=max_parallelism,
            merge_conflict_policy=merge_conflict_policy,
        )
        self._health_ttl_s = health_ttl_s
        self._health_failure_classifier = health_failure_classifier
        discovered_provider = getattr(primary, "_get_health_sample", None)
        self._health_sample_provider = _health_sample_provider or (
            discovered_provider if callable(discovered_provider) else None
        )
        self._last_health: RunnerHealth | None = None
        self._last_health_sample: _HealthFailureSample | None = None
        self._last_health_at: float = 0.0
        self._last_probe_id: int | None = None
        self._probe_id = 0

    def _read_health_sample(self, health: RunnerHealth) -> _HealthFailureSample | None:
        """Read and validate the authority witness for one concrete probe."""
        provider = self._health_sample_provider
        if provider is None:
            return None
        try:
            sample = provider()
        except Exception:  # pragma: no cover - defensive boundary
            return None
        if not isinstance(sample, _HealthFailureSample):
            return None
        if sample.health is not health:
            return None
        if not isinstance(sample.disposition, HealthFailureDisposition):
            return None
        if isinstance(sample.probe_id, bool) or not isinstance(sample.probe_id, int):
            return None
        if self._last_probe_id is not None and sample.probe_id <= self._last_probe_id:
            return None
        self._last_probe_id = sample.probe_id
        return sample

    def _legacy_health_failure_disposition(
        self,
        health: RunnerHealth,
    ) -> HealthFailureDisposition | None:
        """Read a valid legacy classifier result, if one is available."""
        classifier = self._health_failure_classifier
        explicit_classifier = classifier is not None
        if classifier is None:
            candidate = getattr(self._primary, "classify_health_failure", None)
            if callable(candidate):
                classifier = candidate
        if classifier is None:
            return None
        try:
            disposition = classifier(health)
        except Exception as exc:  # pragma: no cover - defensive authority boundary
            if explicit_classifier:
                raise FallbackNotAuthorizedError(
                    "primary health failure classifier did not establish fallback authority"
                ) from exc
            return None
        if not isinstance(disposition, HealthFailureDisposition):
            if explicit_classifier:
                raise FallbackNotAuthorizedError(
                    "primary health failure classifier returned an untyped disposition"
                )
            return None
        return disposition

    def _classify_health_failure(
        self,
        health: RunnerHealth,
        sample: _HealthFailureSample | None,
    ) -> HealthFailureDisposition:
        """Resolve pre-dispatch authority with limiting legacy semantics."""
        if sample is not None:
            # A typed BLOCK is terminal.  A typed ALLOW remains usable unless
            # a valid legacy classifier supplies a narrower BLOCK decision.
            if sample.disposition is HealthFailureDisposition.BLOCK:
                return HealthFailureDisposition.BLOCK
            legacy = self._legacy_health_failure_disposition(health)
            if legacy is HealthFailureDisposition.BLOCK:
                return HealthFailureDisposition.BLOCK
            return HealthFailureDisposition.ALLOW
        if self._health_sample_provider is not None:
            return HealthFailureDisposition.BLOCK

        legacy = self._legacy_health_failure_disposition(health)
        if legacy is None:
            return HealthFailureDisposition.BLOCK
        return legacy

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
        health_sample: _HealthFailureSample | None,
    ) -> Any:
        """Execute local work only after an explicit pre-dispatch typed decision."""
        disposition = self._classify_health_failure(health, health_sample)
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
        self._last_health_sample = None
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

        self._probe_id += 1
        self._last_health_sample = None
        health = await self._primary.health_check()
        self._last_health = health
        self._last_health_at = now
        self._last_health_sample = self._read_health_sample(health)
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
            self._last_health = health
            self._last_health_sample = _HealthFailureSample(
                health=health,
                disposition=_classify_health_probe_exception(exc),
                probe_id=self._probe_id,
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
                    health_sample=self._last_health_sample,
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
                health_sample=self._last_health_sample,
            )


__all__ = [
    "FallbackNotAuthorizedError",
    "FallbackWorkflowRunner",
    "HealthFailureClassifier",
    "HealthFailureDisposition",
    "PrimaryExecutionOutcomeUnknownError",
]
