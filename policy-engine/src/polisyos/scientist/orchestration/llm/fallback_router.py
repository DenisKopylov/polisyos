"""Multi-endpoint fallback router for LLM gateway calls."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

from .gateway_client import GatewayLLMClient, GatewayLLMResponse
from .prepared_request import (
    PreparedLLMRequest,
    PreparedLLMResult,
    freeze_wire_object,
    thaw_wire_object,
)

_FALLBACK_ROUTER_RUNTIME_ERRORS = (
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


class EndpointHealth(str, Enum):
    """Endpoint health public type."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class EndpointConfig:
    """Configuration for a single LLM gateway endpoint."""

    url: str
    api_key: str = ""
    model: str = ""
    provider_hint: str | None = None
    priority: int = 0  # lower = higher priority
    timeout_s: float = 60.0
    max_retries: int = 1
    preset: str | None = None
    default_plugins: tuple[dict[str, Any], ...] = ()


@dataclass
class _EndpointState:
    """Mutable health state for an endpoint."""

    config: EndpointConfig
    health: EndpointHealth = EndpointHealth.HEALTHY
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    failure_threshold: int = 3
    recovery_timeout_s: float = 60.0

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.health = EndpointHealth.HEALTHY

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()
        if self.consecutive_failures >= self.failure_threshold:
            self.health = EndpointHealth.UNHEALTHY

    def is_available(self, now: float | None = None) -> bool:
        """Return availability without mutating health state."""
        if self.health == EndpointHealth.HEALTHY:
            return True
        if self.health == EndpointHealth.UNHEALTHY:
            elapsed = (now if now is not None else time.monotonic()) - self.last_failure_time
            return elapsed >= self.recovery_timeout_s
        # DEGRADED — allow one probe request
        return True


class FallbackRouter:
    """Routes LLM calls through ordered endpoints with health tracking.

    Endpoints are tried in priority order (lower ``priority`` value first).
    When an endpoint fails, the router marks it unhealthy and falls through
    to the next one.  Unhealthy endpoints recover after ``recovery_timeout_s``.
    """

    def __init__(
        self,
        endpoints: list[EndpointConfig],
        *,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 60.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not endpoints:
            raise ValueError("At least one endpoint must be provided")
        sorted_eps = sorted(endpoints, key=lambda e: e.priority)
        self._states: list[_EndpointState] = [
            _EndpointState(
                config=ep,
                failure_threshold=failure_threshold,
                recovery_timeout_s=recovery_timeout_s,
            )
            for ep in sorted_eps
        ]
        self._extra_headers = dict(extra_headers or {})
        self._lock = threading.Lock()

    def prepare_cache_request(
        self, *, model_override: str | None = None, **kwargs: Any
    ) -> PreparedLLMRequest:
        """Freeze the current ordered dispatch candidates; alternate success is not reused."""
        caller = thaw_wire_object(freeze_wire_object(kwargs))
        candidates: list[tuple[_EndpointState, GatewayLLMClient, PreparedLLMRequest]] = []
        for state in self._available_endpoints():
            cfg = state.config
            client = GatewayLLMClient(
                base_url=cfg.url,
                api_key=cfg.api_key,
                model=model_override or cfg.model or caller.get("model", "default"),
                timeout_s=cfg.timeout_s,
                max_retries=cfg.max_retries,
                provider_hint=cfg.provider_hint,
                extra_headers=self._extra_headers,
                preset=cfg.preset,
                default_plugins=[dict(plugin) for plugin in cfg.default_plugins],
            )
            candidates.append((state, client, client.prepare_cache_request(**caller)))
        identity = (
            candidates[0][2].identity
            if candidates
            else freeze_wire_object({"no_available_endpoint": True})
        )

        async def execute() -> PreparedLLMResult:
            last_error: Exception | None = None
            for index, (state, client, request) in enumerate(candidates):
                try:
                    result = await request.execute()
                    with self._lock:
                        state.record_success()
                    # A later endpoint or negotiated gateway payload cannot be
                    # promoted to the originally selected request's cache origin.
                    effective = identity if index == 0 and request.admits(result) else b""
                    return PreparedLLMResult(result.response, effective)
                except _FALLBACK_ROUTER_RUNTIME_ERRORS as exc:
                    last_error = exc
                    with self._lock:
                        state.record_failure()
                    emit_degraded_path(
                        component="scientist.llm.fallback_router",
                        operation="generate",
                        reason="endpoint_request_failed",
                        exc=exc,
                        details={
                            "endpoint_url": state.config.url,
                            "provider_hint": state.config.provider_hint,
                            "priority": state.config.priority,
                        },
                    )
                finally:
                    await client.aclose()
            raise RuntimeError("All LLM endpoints exhausted") from last_error

        return PreparedLLMRequest(identity, execute, bool(candidates))

    def cache_request_identity(self, **kwargs: Any) -> dict[str, Any]:
        """Return the actual selected head request, including current availability."""
        return thaw_wire_object(self.prepare_cache_request(**kwargs).identity)

    async def generate(
        self, *, model_override: str | None = None, **kwargs: Any
    ) -> GatewayLLMResponse:
        """Execute the frozen current dispatch plan through its actual endpoints."""
        return (
            await self.prepare_cache_request(model_override=model_override, **kwargs).execute()
        ).response

    async def aclose(self) -> None:
        """No-op close hook for TracedLLMClient compatibility."""
        return None

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        """Fetch model IDs from the first available endpoint for preflight checks."""

        last_error: Exception | None = None
        for state in self._available_endpoints():
            cfg = state.config
            client = GatewayLLMClient(
                base_url=cfg.url,
                api_key=cfg.api_key,
                model=cfg.model or "default",
                timeout_s=cfg.timeout_s,
                max_retries=cfg.max_retries,
                provider_hint=cfg.provider_hint,
                extra_headers=self._extra_headers,
                preset=cfg.preset,
                default_plugins=[dict(plugin) for plugin in cfg.default_plugins],
            )
            try:
                model_ids = await client.list_model_ids(timeout=timeout)
                with self._lock:
                    state.record_success()
                return model_ids
            except _FALLBACK_ROUTER_RUNTIME_ERRORS as exc:
                last_error = exc
                with self._lock:
                    state.record_failure()
                emit_degraded_path(
                    component="scientist.llm.fallback_router",
                    operation="list_model_ids",
                    reason="endpoint_model_catalog_failed",
                    exc=exc,
                    details={
                        "endpoint_url": cfg.url,
                        "provider_hint": cfg.provider_hint,
                        "priority": cfg.priority,
                    },
                )
            finally:
                await client.aclose()

        raise RuntimeError("All LLM endpoints exhausted for model catalog") from last_error

    def _available_endpoints(self) -> list[_EndpointState]:
        with self._lock:
            now = time.monotonic()
            available: list[_EndpointState] = []
            for state in self._states:
                if state.health == EndpointHealth.UNHEALTHY and state.is_available(now):
                    state.health = EndpointHealth.DEGRADED
                if state.is_available(now):
                    available.append(state)
            return available

    def endpoint_health(self) -> list[dict[str, Any]]:
        """Return current health status of all endpoints."""
        with self._lock:
            return [
                {
                    "url": s.config.url,
                    "health": s.health.value,
                    "consecutive_failures": s.consecutive_failures,
                    "priority": s.config.priority,
                }
                for s in self._states
            ]


__all__ = [
    "EndpointConfig",
    "EndpointHealth",
    "FallbackRouter",
]
