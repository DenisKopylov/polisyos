from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

from polisyos.core.backends import BackendDispatcher, BackendNotAvailableError as CoreBackendNotAvailableError
from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.backends.protocol import MethodResult, MethodRunner


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
        runner = self._resolve_runner(signature.backend)
        return runner.execute(
            method_class=method_class,
            signature=signature,
            state=state,
            params=params,
            seed=seed,
        )

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
        raise ValueError(f"Unsupported backend: {backend}")
