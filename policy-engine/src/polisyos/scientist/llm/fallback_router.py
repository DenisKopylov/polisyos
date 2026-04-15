"""Multi-endpoint fallback router for LLM gateway calls."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from polisyos.scientist.error_semantics import emit_degraded_path

from .gateway_client import GatewayLLMClient, GatewayLLMResponse

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

    async def generate(
        self,
        *,
        model_override: str | None = None,
        **kwargs: Any,
    ) -> GatewayLLMResponse:
        """Route a generate call through available endpoints.

        Falls through to the next endpoint on failure.  Raises
        ``RuntimeError`` if all endpoints are exhausted.
        """
        last_error: Exception | None = None
        for state in self._available_endpoints():
            cfg = state.config
            client = GatewayLLMClient(
                base_url=cfg.url,
                api_key=cfg.api_key,
                model=model_override or cfg.model or kwargs.get("model", "default"),
                timeout_s=cfg.timeout_s,
                max_retries=cfg.max_retries,
                provider_hint=cfg.provider_hint,
                extra_headers=self._extra_headers,
                preset=cfg.preset,
                default_plugins=[dict(plugin) for plugin in cfg.default_plugins],
            )
            try:
                response = await client.generate(**kwargs)
                with self._lock:
                    state.record_success()
                return response
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
                        "endpoint_url": cfg.url,
                        "provider_hint": cfg.provider_hint,
                        "priority": cfg.priority,
                    },
                )
            finally:
                await client.aclose()

        raise RuntimeError(
            "All LLM endpoints exhausted"
        ) from last_error

    async def aclose(self) -> None:
        """No-op close hook for TracedLLMClient compatibility."""
        return None

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
