from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

from polisyos.core.backends import BackendDispatcher
from polisyos.core.backends import BackendNotAvailableError as CoreBackendNotAvailableError
from polisyos.foundry.methods.backends.circuit_breaker import (
    BackendCircuitOpenError,
    CircuitBreaker,
    get_circuit_breaker_registry,
)
from polisyos.foundry.methods._logging import _infer_n_obs, get_foundry_logger
from polisyos.foundry.methods.backends.protocol import MethodResult, MethodRunner
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.output_monitor import _emit_anomaly_metric, get_output_monitor

_log = get_foundry_logger("foundry.backends.dispatch")


@dataclass(frozen=True)
class BackendNotAvailableError(RuntimeError):
    backend: ComputeBackend

    def __str__(self) -> str:
        return (
            f"Compute backend '{self.backend.value}' is not available. "
            f"Install optional dependencies for this backend."
        )


class MethodDispatcher:
    """Thread-safe singleton dispatcher for compute backend routing."""

    _instance: MethodDispatcher | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._dispatcher = BackendDispatcher[ComputeBackend, MethodRunner](
            factory=self._create_runner,
            availability_check=lambda runner: runner.is_available(),
        )
        self._runner_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> MethodDispatcher:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    def register_runner(self, runner: MethodRunner) -> None:
        with self._runner_lock:
            for backend in runner.supported_backends:
                self._dispatcher.register(backend, runner)

    def available_backends(self) -> frozenset[ComputeBackend]:
        with self._runner_lock:
            return self._dispatcher.available_backends()

    def dispatch(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        import time as _time

        runner = self._resolve_runner(signature.backend)
        breaker = get_circuit_breaker_registry().get(signature.backend.value)
        n_obs = _infer_n_obs(state)

        _log.debug(
            "method_dispatch_start",
            fqn=signature.fqn,
            backend=signature.backend.value,
            n_obs=n_obs,
        )
        t0 = _time.perf_counter()

        def _execute() -> MethodResult:
            return runner.execute(
                method_class=method_class,
                signature=signature,
                state=state,
                params=params,
                seed=seed,
            )

        try:
            result = breaker.call(_execute)
        except BackendCircuitOpenError:
            # Backend circuit is open — attempt fallback to NumPy
            fallback_backend = ComputeBackend.NUMPY
            if signature.backend == fallback_backend:
                _log.error(
                    "method_dispatch_error",
                    fqn=signature.fqn,
                    backend=signature.backend.value,
                    reason="circuit_open_no_fallback",
                )
                raise  # no fallback available
            try:
                _log.warning(
                    "method_dispatch_fallback",
                    fqn=signature.fqn,
                    original_backend=signature.backend.value,
                    fallback_backend=fallback_backend.value,
                )
                fallback_runner = self._resolve_runner(fallback_backend)
                result = fallback_runner.execute(
                    method_class=method_class,
                    signature=signature,
                    state=state,
                    params=params,
                    seed=seed,
                )
            except Exception:
                raise  # re-raise the original BackendCircuitOpenError's cause
        except Exception as exc:
            elapsed_ms = (_time.perf_counter() - t0) * 1000
            _log.error(
                "method_dispatch_error",
                fqn=signature.fqn,
                backend=signature.backend.value,
                elapsed_ms=round(elapsed_ms, 2),
                exc=type(exc).__name__,
            )
            raise

        elapsed_ms = (_time.perf_counter() - t0) * 1000
        _log.info(
            "method_dispatch_complete",
            fqn=signature.fqn,
            backend=signature.backend.value,
            elapsed_ms=round(elapsed_ms, 2),
            n_obs=n_obs,
        )

        # Basic anomaly detection: NaN/Inf + key sanity (vectorised, near-zero cost)
        expected_keys: set[str] | None = None
        if signature.output_slots:
            expected_keys = {s.name for s in signature.output_slots}
        monitor = get_output_monitor()
        flags = monitor.check_basic(result.output, expected_keys=expected_keys)
        if flags:
            import warnings
            for flag in flags:
                warnings.warn(str(flag), stacklevel=3)
            _emit_anomaly_metric(signature.fqn, flags)

        return result

    def _resolve_runner(self, backend: ComputeBackend) -> MethodRunner:
        try:
            return self._dispatcher.resolve(backend)
        except CoreBackendNotAvailableError as exc:
            raise BackendNotAvailableError(backend) from exc

    @staticmethod
    @lru_cache(maxsize=8)
    def _create_runner(backend: ComputeBackend) -> MethodRunner:
        if backend is ComputeBackend.JAX:
            from polisyos.foundry.methods.backends.jax_runner import JaxRunner

            return JaxRunner()
        if backend is ComputeBackend.NUMPY:
            from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner

            return NumpyRunner()
        if backend is ComputeBackend.SOLVER:
            from polisyos.foundry.methods.backends.solver_runner import SolverRunner

            return SolverRunner()
        if backend is ComputeBackend.BAYESIAN:
            from polisyos.foundry.methods.backends.bayesian_runner import BayesianRunner

            return BayesianRunner()
        raise ValueError(f"Unsupported backend: {backend}")
