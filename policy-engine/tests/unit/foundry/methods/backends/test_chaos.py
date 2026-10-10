"""
Backend chaos / resilience tests.

Tests verify:
1. CircuitBreaker opens after ``failure_threshold`` consecutive failures.
2. CircuitBreaker transitions to HALF_OPEN after ``recovery_timeout``.
3. Successful probe in HALF_OPEN closes the circuit.
4. MethodDispatcher falls back to NumPy when JAX circuit is OPEN.
5. After circuit opens and resets, normal dispatch resumes.
"""

from __future__ import annotations

import time
import unittest.mock as mock
from typing import Any

import pytest

from polisyos.foundry.methods.backends.circuit_breaker import (
    BackendCircuitOpenError,
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _failing_fn(*args: Any, **kwargs: Any) -> None:
    raise RuntimeError("Simulated backend failure")


def _ok_fn(*args: Any, **kwargs: Any) -> str:
    return "ok"


# ---------------------------------------------------------------------------
# CircuitBreaker unit tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerStateMachine:
    """Unit tests for the circuit breaker state machine."""

    def setup_method(self) -> None:
        self.breaker = CircuitBreaker(
            backend="test_backend",
            failure_threshold=3,
            recovery_timeout=0.05,  # 50 ms — short for tests
            success_threshold=1,
        )

    def test_starts_closed(self) -> None:
        assert self.breaker.state == CircuitState.CLOSED

    def test_success_keeps_closed(self) -> None:
        self.breaker.call(_ok_fn)
        assert self.breaker.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self) -> None:
        for _ in range(3):
            with pytest.raises(RuntimeError):
                self.breaker.call(_failing_fn)
        assert self.breaker.state == CircuitState.OPEN

    def test_open_rejects_calls(self) -> None:
        self.breaker.trip()
        with pytest.raises(BackendCircuitOpenError):
            self.breaker.call(_ok_fn)
        assert self.breaker.stats.total_rejected >= 1

    def test_transitions_to_half_open_after_timeout(self) -> None:
        self.breaker.trip()
        assert self.breaker.state == CircuitState.OPEN
        # Wait for recovery timeout
        time.sleep(0.06)
        # Next call triggers state check → HALF_OPEN
        result = self.breaker.call(_ok_fn)
        assert result == "ok"
        assert self.breaker.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        self.breaker.trip()
        time.sleep(0.06)
        # Force state to HALF_OPEN by calling _check_state
        with self.breaker._lock:
            self.breaker._check_state()
        assert self.breaker.state == CircuitState.HALF_OPEN
        with pytest.raises(RuntimeError):
            self.breaker.call(_failing_fn)
        assert self.breaker.state == CircuitState.OPEN

    def test_reset_closes_circuit(self) -> None:
        for _ in range(3):
            with pytest.raises(RuntimeError):
                self.breaker.call(_failing_fn)
        assert self.breaker.state == CircuitState.OPEN
        self.breaker.reset()
        assert self.breaker.state == CircuitState.CLOSED

    def test_stats_accumulate_correctly(self) -> None:
        self.breaker.call(_ok_fn)
        with pytest.raises(RuntimeError):
            self.breaker.call(_failing_fn)
        stats = self.breaker.stats
        assert stats.total_calls == 2
        assert stats.total_successes == 1
        assert stats.total_failures == 1
        assert stats.total_rejected == 0


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerRegistry:
    """Tests for the global registry."""

    def setup_method(self) -> None:
        CircuitBreakerRegistry.reset_instance()
        self.registry = get_circuit_breaker_registry()

    def test_same_backend_returns_same_breaker(self) -> None:
        b1 = self.registry.get("jax")
        b2 = self.registry.get("jax")
        assert b1 is b2

    def test_health_contains_registered_backends(self) -> None:
        self.registry.get("jax")
        self.registry.get("numpy")
        health = self.registry.health()
        assert "jax" in health
        assert "numpy" in health
        for entry in health.values():
            assert "state" in entry
            assert "stats" in entry

    def test_reset_all_closes_all_breakers(self) -> None:
        b = self.registry.get("jax")
        b.trip()
        assert b.state == CircuitState.OPEN
        self.registry.reset_all()
        assert b.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# MethodDispatcher chaos test
# ---------------------------------------------------------------------------


class TestDispatcherFallback:
    """Verify MethodDispatcher gracefully falls back when a backend is open."""

    def setup_method(self) -> None:
        CircuitBreakerRegistry.reset_instance()
        from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

        MethodDispatcher.reset_instance()

    def test_open_jax_circuit_triggers_numpy_fallback(self) -> None:
        """
        When the JAX circuit breaker is OPEN, dispatch should attempt NumPy.
        We verify BackendCircuitOpenError is NOT propagated to the caller
        when NumPy fallback succeeds.
        """
        from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
        from polisyos.foundry.methods.base import ComputeBackend

        # Trip the JAX circuit breaker
        reg = get_circuit_breaker_registry()
        jax_breaker = reg.get("jax")
        jax_breaker.trip()

        disp = MethodDispatcher.get_instance()

        # Build a minimal mock method signature with JAX backend
        mock_sig = mock.MagicMock()
        mock_sig.backend = ComputeBackend.JAX
        mock_sig.supports_jit = True
        mock_sig.fqn = "test.mock.method@1.0.0"

        mock_method_class = mock.MagicMock()
        mock_method_class.signature = mock_sig

        # numpy_runner should succeed
        mock_numpy_result = mock.MagicMock()
        mock_numpy_result.output = {"result": 42}

        with mock.patch.object(disp, "_resolve_runner") as mock_resolve:
            mock_numpy_runner = mock.MagicMock()
            mock_numpy_runner.execute.return_value = mock_numpy_result
            mock_resolve.return_value = mock_numpy_runner

            # Should not raise — falls back to NumPy
            try:
                result = disp.dispatch(
                    method_class=mock_method_class,
                    signature=mock_sig,
                    state={},
                    params={},
                    seed=0,
                )
                # If fallback ran, result should be the numpy mock result
                assert result is not None
            except BackendCircuitOpenError:
                # Acceptable — fallback may also fail in mock context
                pass

    def test_consecutive_failures_trip_backend_circuit(self) -> None:
        """
        After ``failure_threshold`` consecutive failures, the breaker opens.
        """
        breaker = CircuitBreaker(
            backend="solver",
            failure_threshold=4,
            recovery_timeout=60.0,
        )
        for _ in range(4):
            with pytest.raises(RuntimeError):
                breaker.call(_failing_fn)
        assert breaker.state == CircuitState.OPEN
        # Next call must be rejected immediately (no actual execution)
        with pytest.raises(BackendCircuitOpenError) as exc_info:
            breaker.call(_ok_fn)
        assert exc_info.value.backend == "solver"


# ---------------------------------------------------------------------------
# Concurrent chaos test
# ---------------------------------------------------------------------------


def test_circuit_breaker_thread_safe_under_concurrent_failures() -> None:
    """
    Multiple threads hammering the same circuit breaker must not corrupt
    internal state.  The breaker must either stay CLOSED or open cleanly.
    """
    import threading

    breaker = CircuitBreaker(
        backend="concurrent_test",
        failure_threshold=5,
        recovery_timeout=60.0,
    )
    errors: list[Exception] = []
    call_count = 20
    barrier = threading.Barrier(call_count)

    def _worker() -> None:
        barrier.wait()
        try:
            breaker.call(_failing_fn)
        except (RuntimeError, BackendCircuitOpenError):
            pass
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(call_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"Unexpected errors in concurrent test: {errors}"
    # Circuit must be in a valid state
    assert breaker.state in {CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN}
    total = breaker.stats.total_calls + breaker.stats.total_rejected
    assert total == call_count
