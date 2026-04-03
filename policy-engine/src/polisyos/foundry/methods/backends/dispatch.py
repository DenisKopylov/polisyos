"""Public backends dispatch module API."""
from __future__ import annotations

import threading
import time as _time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Protocol, runtime_checkable

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
from polisyos.foundry.methods.selection_history import (
    MethodExecutionRecord,
    get_global_selection_history,
)

_log = get_foundry_logger("foundry.backends.dispatch")


def _infer_data_characteristics(state: Any, n_obs: int | None) -> dict[str, Any]:
    characteristics: dict[str, Any] = {}
    if n_obs is not None:
        characteristics["n_obs"] = int(n_obs)
    if isinstance(state, Mapping):
        for key in ("features", "covariates", "X"):
            value = state.get(key)
            shape = getattr(value, "shape", None)
            if shape and len(shape) >= 2:
                characteristics["n_features"] = int(shape[-1])
                break
    return characteristics


def _record_execution(
    *,
    signature: MethodSignature,
    elapsed_ms: float,
    success: bool,
    n_obs: int | None,
    state: Any,
    failure_type: str | None = None,
    backend_used: ComputeBackend | None = None,
) -> None:
    try:
        record = MethodExecutionRecord(
            method_fqn=signature.fqn,
            timestamp=_time.time(),
            latency_ms=max(elapsed_ms, 0.0),
            success=success,
            failure_type=failure_type,
            data_characteristics={
                **_infer_data_characteristics(state, n_obs),
                "backend": (backend_used or signature.backend).value,
            },
        )
        get_global_selection_history().record(record)
    except Exception:
        return


@dataclass(frozen=True)
class BackendNotAvailableError(RuntimeError):
    """Backend not available error exception."""
    backend: ComputeBackend

    def __str__(self) -> str:
        return (
            f"Compute backend '{self.backend.value}' is not available. "
            f"Install optional dependencies for this backend."
        )


@runtime_checkable
class FallbackStrategy(Protocol):
    """Strategy for choosing fallback backend when primary fails."""

    def select_fallback(
        self,
        method_class: type,
        signature: MethodSignature,
        failed_backend: ComputeBackend,
    ) -> ComputeBackend | None: ...


class SignatureAwareFallback:
    """Default fallback: check signature compatibility before falling back."""

    FALLBACK_ORDER = [ComputeBackend.NUMPY]

    def select_fallback(
        self,
        method_class: type,
        signature: MethodSignature,
        failed_backend: ComputeBackend,
    ) -> ComputeBackend | None:
        for backend in self.FALLBACK_ORDER:
            if backend == failed_backend:
                continue
            if self._is_compatible(signature, backend):
                return backend
        return None

    def _is_compatible(self, signature: MethodSignature, backend: ComputeBackend) -> bool:
        # JAX-specific features (vmap, grad) incompatible with NumPy
        if backend == ComputeBackend.NUMPY and (
            signature.supports_grad or signature.supports_vmap
        ):
            return False
        return True


class MethodDispatcher:
    """Thread-safe singleton dispatcher for compute backend routing."""

    _instance: MethodDispatcher | None = None
    _instance_lock = threading.Lock()

    def __init__(
        self, *, fallback_strategy: FallbackStrategy | None = None,
    ) -> None:
        self._dispatcher = BackendDispatcher[ComputeBackend, MethodRunner](
            factory=self._create_runner,
            availability_check=lambda runner: runner.is_available(),
        )
        self._runner_lock = threading.RLock()
        self._fallback_strategy: FallbackStrategy = (
            fallback_strategy or SignatureAwareFallback()
        )

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
        runner = self._resolve_runner(signature.backend)
        breaker = get_circuit_breaker_registry().get(signature.backend.value)
        n_obs = _infer_n_obs(state)
        backend_used = signature.backend

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
            # Backend circuit is open — ask strategy for fallback
            fallback_backend = self._fallback_strategy.select_fallback(
                method_class, signature, signature.backend,
            )
            if fallback_backend is None:
                _log.error(
                    "method_dispatch_error",
                    fqn=signature.fqn,
                    backend=signature.backend.value,
                    reason="circuit_open_no_fallback",
                )
                raise  # no compatible fallback available
            try:
                _log.warning(
                    "method_dispatch_fallback",
                    fqn=signature.fqn,
                    original_backend=signature.backend.value,
                    fallback_backend=fallback_backend.value,
                )
                fallback_runner = self._resolve_runner(fallback_backend)
                backend_used = fallback_backend
                result = fallback_runner.execute(
                    method_class=method_class,
                    signature=signature,
                    state=state,
                    params=params,
                    seed=seed,
                )
            except Exception:
                elapsed_ms = (_time.perf_counter() - t0) * 1000
                _record_execution(
                    signature=signature,
                    elapsed_ms=elapsed_ms,
                    success=False,
                    n_obs=n_obs,
                    state=state,
                    failure_type="fallback_failure",
                    backend_used=fallback_backend,
                )
                raise  # re-raise the fallback failure
        except Exception as exc:
            elapsed_ms = (_time.perf_counter() - t0) * 1000
            _log.error(
                "method_dispatch_error",
                fqn=signature.fqn,
                backend=signature.backend.value,
                elapsed_ms=round(elapsed_ms, 2),
                exc=type(exc).__name__,
            )
            _record_execution(
                signature=signature,
                elapsed_ms=elapsed_ms,
                success=False,
                n_obs=n_obs,
                state=state,
                failure_type=type(exc).__name__,
                backend_used=backend_used,
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
        _record_execution(
            signature=signature,
            elapsed_ms=elapsed_ms,
            success=True,
            n_obs=n_obs,
            state=state,
            backend_used=backend_used,
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
