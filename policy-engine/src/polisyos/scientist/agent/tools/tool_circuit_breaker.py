"""Per-tool circuit breaker registry.

Wraps :class:`~polisyos.scientist.engine.circuit_breaker.CircuitBreaker` to
provide isolated failure tracking for each tool in a :class:`ToolRegistry`.
"""

from __future__ import annotations

import threading

from polisyos.scientist.engine.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)

__all__ = ["ToolCircuitBreakerRegistry"]


class ToolCircuitBreakerRegistry:
    """Lazily creates one :class:`CircuitBreaker` per tool name.

    Parameters
    ----------
    failure_threshold:
        Number of consecutive failures before the breaker opens.
    recovery_timeout_s:
        Seconds to wait in *open* state before transitioning to *half_open*.
    half_open_max_calls:
        Max probe calls allowed while *half_open*.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout_s=recovery_timeout_s,
            half_open_max_calls=half_open_max_calls,
        )
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_breaker(self, tool_name: str) -> CircuitBreaker:
        """Return (or lazily create) the breaker for *tool_name*."""
        with self._lock:
            if tool_name not in self._breakers:
                self._breakers[tool_name] = CircuitBreaker(
                    self._config,
                    name=tool_name,
                )
            return self._breakers[tool_name]

    def allow_request(self, tool_name: str) -> bool:
        """Check if *tool_name* is allowed (breaker not open)."""
        return self.get_breaker(tool_name).allow_request()

    def record_success(self, tool_name: str) -> None:
        self.get_breaker(tool_name).record_success()

    def record_failure(self, tool_name: str) -> None:
        self.get_breaker(tool_name).record_failure()

    def reset(self, tool_name: str) -> None:
        """Force-reset a single breaker (testing use)."""
        self.get_breaker(tool_name).reset()

    def reset_all(self) -> None:
        """Force-reset every tracked breaker."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()
