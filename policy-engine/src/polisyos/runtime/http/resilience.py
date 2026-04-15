"""Dependency guards for runtime slow/unavailable CAS, OPA, and control-store paths."""
from __future__ import annotations

import asyncio
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from polisyos.common.async_tools import get_shared_executor
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitAttemptLease,
    CircuitBreaker,
    CircuitBreakerConfig,
)
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)

T = TypeVar("T")
_MIN_BLOCKING_TIMEOUT_SECONDS = 0.1


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class BlockingDependencyGuard:
    """Protect one blocking dependency with timeout and a circuit breaker."""

    def __init__(
        self,
        *,
        dependency_name: str,
        timeout_seconds: float,
        breaker: CircuitBreaker,
        executor_max_workers: int = 4,
        executor: ThreadPoolExecutor | None = None,
        unavailable_exception_types: tuple[type[BaseException], ...] = (),
        unavailable_exception_predicate: Callable[[BaseException], bool] | None = None,
    ) -> None:
        self._dependency_name = dependency_name
        # Blocking dependencies routinely pay thread handoff + filesystem/SQLite
        # scheduling overhead, so a 50ms floor is too aggressive and can trip the
        # breaker on healthy startup paths under suite or production load.
        self._timeout_seconds = max(timeout_seconds, _MIN_BLOCKING_TIMEOUT_SECONDS)
        self._breaker = breaker
        self._closed = False
        self._owns_executor = executor is None
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max(executor_max_workers, 1),
            thread_name_prefix=f"runtime-{dependency_name}",
        )
        self._unavailable_exception_types = unavailable_exception_types
        self._unavailable_exception_predicate = unavailable_exception_predicate

    def run(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        if self._closed:
            raise RuntimeDependencyUnavailableError(
                self._dependency_name,
                detail=f"{self._dependency_name} dependency guard is closed",
            )
        lease = self._breaker.acquire_attempt()
        if lease is None:
            raise RuntimeDependencyUnavailableError(
                self._dependency_name,
                detail=f"{self._dependency_name} circuit breaker is open",
            )
        try:
            future = self._executor.submit(func, *args, **kwargs)
        except RuntimeError as exc:
            raise RuntimeDependencyUnavailableError(
                self._dependency_name,
                detail=f"{self._dependency_name} executor is unavailable",
            ) from exc
        try:
            result = future.result(timeout=self._timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            self._breaker.record_failure(lease)
            raise RuntimeDependencyTimeoutError(self._dependency_name) from exc
        except Exception as exc:
            self._breaker.record_failure(lease)
            if self._is_unavailable_exception(exc):
                raise RuntimeDependencyUnavailableError(
                    self._dependency_name,
                    detail=str(exc) or f"{self._dependency_name} is temporarily unavailable",
                ) from exc
            raise
        self._breaker.record_success(lease)
        return result

    def record_failure(self) -> None:
        self._breaker.record_failure()

    def close(self) -> None:
        self._closed = True
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _is_unavailable_exception(self, exc: BaseException) -> bool:
        if self._unavailable_exception_types and isinstance(exc, self._unavailable_exception_types):
            return True
        if self._unavailable_exception_predicate is not None:
            return self._unavailable_exception_predicate(exc)
        return False


class AsyncDependencyGuard:
    """Protect one async dependency with timeout and a circuit breaker."""

    def __init__(
        self,
        *,
        dependency_name: str,
        timeout_seconds: float,
        breaker: CircuitBreaker,
        unavailable_exception_types: tuple[type[BaseException], ...] = (),
        unavailable_exception_predicate: Callable[[BaseException], bool] | None = None,
    ) -> None:
        self._dependency_name = dependency_name
        self._timeout_seconds = max(timeout_seconds, 0.05)
        self._breaker = breaker
        self._unavailable_exception_types = unavailable_exception_types
        self._unavailable_exception_predicate = unavailable_exception_predicate

    async def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        lease = self._breaker.acquire_attempt()
        if lease is None:
            raise RuntimeDependencyUnavailableError(
                self._dependency_name,
                detail=f"{self._dependency_name} circuit breaker is open",
            )
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            self._breaker.record_failure(lease)
            raise RuntimeDependencyTimeoutError(self._dependency_name) from exc
        except asyncio.CancelledError:
            self._release_cancelled_lease(lease)
            raise
        except Exception as exc:
            self._breaker.record_failure(lease)
            if self._is_unavailable_exception(exc):
                raise RuntimeDependencyUnavailableError(
                    self._dependency_name,
                    detail=str(exc) or f"{self._dependency_name} is temporarily unavailable",
                ) from exc
            raise
        self._breaker.record_success(lease)
        return result

    def record_failure(self) -> None:
        self._breaker.record_failure()

    def _is_unavailable_exception(self, exc: BaseException) -> bool:
        if self._unavailable_exception_types and isinstance(exc, self._unavailable_exception_types):
            return True
        if self._unavailable_exception_predicate is not None:
            return self._unavailable_exception_predicate(exc)
        return False

    def _release_cancelled_lease(self, lease: CircuitAttemptLease | None) -> None:
        if lease is None or not lease.owns_half_open_slot:
            return
        release = getattr(self._breaker, "_release_cancelled_lease", None)
        if callable(release):
            release(lease)


class GuardedDependencyProxy:
    """Wrap a dependency object so each callable is guarded by timeout/breaker policy."""

    def __init__(self, *, target: Any, guard: BlockingDependencyGuard) -> None:
        self._target = target
        self._guard = guard

    def __getattr__(self, name: str) -> Any:
        if name == "close":
            return self.close
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        @wraps(attr)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return self._guard.run(attr, *args, **kwargs)

        return _wrapped

    def close(self) -> None:
        try:
            target_close = getattr(self._target, "close", None)
            if callable(target_close):
                target_close()
        finally:
            self._guard.close()


def _build_breaker(*, circuit_id: str, env_prefix: str) -> CircuitBreaker:
    return CircuitBreaker(
        circuit_id=circuit_id,
        config=CircuitBreakerConfig(
            failure_threshold=max(_env_int(f"{env_prefix}_BREAKER_FAILURE_THRESHOLD", 3), 1),
            success_threshold=1,
            timeout_seconds=max(_env_float(f"{env_prefix}_BREAKER_TIMEOUT_SECONDS", 30.0), 1.0),
            half_open_max_calls=1,
            window_size_seconds=max(_env_float(f"{env_prefix}_BREAKER_WINDOW_SECONDS", 60.0), 1.0),
            min_throughput=1,
        ),
    )


def build_runtime_cas_guard() -> BlockingDependencyGuard:
    return BlockingDependencyGuard(
        dependency_name="content_addressed_storage",
        timeout_seconds=_env_float("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", 1.5),
        breaker=_build_breaker(circuit_id="runtime.cas", env_prefix="POLISYOS_RUNTIME_CAS"),
        executor_max_workers=_env_int("POLISYOS_RUNTIME_CAS_EXECUTOR_MAX_WORKERS", 4),
        executor=get_shared_executor(),
        unavailable_exception_types=(OSError,),
        unavailable_exception_predicate=lambda exc: isinstance(exc, OSError)
        and not isinstance(exc, FileNotFoundError),
    )


def build_runtime_control_store_guard() -> BlockingDependencyGuard:
    return BlockingDependencyGuard(
        dependency_name="control_plane_store",
        timeout_seconds=_env_float("POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS", 1.5),
        breaker=_build_breaker(
            circuit_id="runtime.control_store",
            env_prefix="POLISYOS_RUNTIME_CONTROL_STORE",
        ),
        executor_max_workers=_env_int("POLISYOS_RUNTIME_CONTROL_STORE_EXECUTOR_MAX_WORKERS", 4),
        executor=get_shared_executor(),
        unavailable_exception_types=(sqlite3.Error, OSError, ConnectionError),
        unavailable_exception_predicate=lambda exc: isinstance(exc, RuntimeError)
        and (
            "control-plane store" in str(exc).lower()
            or "psycopg" in str(exc).lower()
            or "postgres" in str(exc).lower()
        ),
    )


def build_runtime_opa_async_guard() -> AsyncDependencyGuard:
    return AsyncDependencyGuard(
        dependency_name="authorization_dependency",
        timeout_seconds=_env_float("POLISYOS_RUNTIME_OPA_TIMEOUT_SECONDS", 1.5),
        breaker=_build_breaker(circuit_id="runtime.review_opa", env_prefix="POLISYOS_RUNTIME_OPA"),
    )


def guard_runtime_cas(target: Any) -> GuardedDependencyProxy:
    return GuardedDependencyProxy(target=target, guard=build_runtime_cas_guard())


def guard_runtime_control_store(target: Any) -> GuardedDependencyProxy:
    return GuardedDependencyProxy(target=target, guard=build_runtime_control_store_guard())


__all__ = [
    "AsyncDependencyGuard",
    "BlockingDependencyGuard",
    "GuardedDependencyProxy",
    "build_runtime_opa_async_guard",
    "guard_runtime_cas",
    "guard_runtime_control_store",
]
