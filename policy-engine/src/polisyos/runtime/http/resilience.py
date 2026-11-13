"""Dependency guards for runtime slow/unavailable CAS, OPA, and control-store paths."""

from __future__ import annotations

import asyncio
import contextvars
import math
import os
import sqlite3
import sys
import threading
import time
from concurrent.futures import (
    CancelledError as FutureCancelledError,
)
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
)
from concurrent.futures import (
    TimeoutError as FutureTimeoutError,
)
from dataclasses import dataclass, field, replace
from functools import wraps
from types import FunctionType, MethodType
from typing import TYPE_CHECKING, Any, TypeVar, cast
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactStore,
        Ed25519Verifier,
        SignatureVerificationResult,
        SignatureVerifyingArtifactStore,
    )
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.scientist.validation.source_admission_owner import _RegisteredSourceAdmissionOwner

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


@dataclass
class _BlockingAttempt:
    unavailable: bool = False
    started_at: float | None = None
    completion: _BlockingCompletion | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass(frozen=True, slots=True)
class _BlockingCompletion:
    completed_at: float
    value: Any = None
    error: BaseException | None = None


def _safe_symbol(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 160
        or not all(ch.isascii() and (ch.isalnum() or ch in "._<>") for ch in value)
    ):
        return "not_established"
    return value


def _safe_operation_identity(func: object) -> dict[str, str]:
    target = func.__func__ if type(func) is MethodType else func
    if type(target) is not FunctionType:
        return {"module": "not_established", "qualname": "not_established"}
    return {
        "module": _safe_symbol(target.__module__),
        "qualname": _safe_symbol(target.__qualname__),
    }


def _safe_guard_caller() -> dict[str, str]:
    # Read code identity only; never retain frames, arguments or exception text.
    try:
        frame = sys._getframe(1)
    except ValueError:
        return {"module": "not_established", "qualname": "not_established"}
    for _ in range(16):
        module = frame.f_globals.get("__name__")
        if module != __name__:
            return {
                "module": _safe_symbol(module),
                "qualname": _safe_symbol(frame.f_code.co_qualname),
            }
        if frame.f_back is None:
            break
        frame = frame.f_back
    return {"module": "not_established", "qualname": "not_established"}


class _BlockingDependencyWaitTimeoutError(RuntimeDependencyTimeoutError):
    """A dependency deadline expired; the underlying work may still be running."""

    def __init__(self, dependency_name: str, *, diagnostic: dict[str, object]) -> None:
        super().__init__(dependency_name)
        self._diagnostic = diagnostic

    def diagnostic(self) -> dict[str, object]:
        """Return bounded, non-authoritative wait details without caller payloads."""
        values = self._diagnostic if type(self._diagnostic) is dict else {}

        def seconds(name: str) -> float | None:
            value = values.get(name)
            if (
                type(value) not in (int, float)
                or value < 0
                or value > 604_800
                or not math.isfinite(value)
            ):
                return None
            return float(value)

        def identity(name: str) -> dict[str, str]:
            value = values.get(name)
            if type(value) is not dict:
                value = {}
            return {
                "module": _safe_symbol(value.get("module")),
                "qualname": _safe_symbol(value.get("qualname")),
            }

        disposition = values.get("wait_disposition")
        if type(disposition) is not str or disposition not in {
            "cancelled_before_start",
            "finished_after_deadline",
            "running_at_observation",
            "start_not_observed",
        }:
            disposition = "not_established"
        return {
            "timeout_seconds": seconds("timeout_seconds"),
            "wait_elapsed_seconds": seconds("wait_elapsed_seconds"),
            "queue_wait_seconds": seconds("queue_wait_seconds"),
            "operation_elapsed_seconds": seconds("operation_elapsed_seconds"),
            "wait_disposition": disposition,
            "operation": identity("operation"),
            "caller": identity("caller"),
        }


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


@dataclass(frozen=True, slots=True)
class _BlockingGuardSnapshot:
    """The actual guard dependencies and timeout for one attempt."""

    dependency_name: str
    timeout_seconds: float
    breaker: CircuitBreaker
    executor: ThreadPoolExecutor
    execution: threading.local
    unavailable_exception_types: tuple[type[BaseException], ...]
    unavailable_exception_predicate: Callable[[BaseException], bool] | None
    on_timeout: Callable[[Future[Any]], None] | None = None


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
        self._execution = threading.local()

    def _snapshot(self) -> _BlockingGuardSnapshot:
        return _BlockingGuardSnapshot(
            dependency_name=self._dependency_name,
            timeout_seconds=self._timeout_seconds,
            breaker=self._breaker,
            executor=self._executor,
            execution=self._execution,
            unavailable_exception_types=self._unavailable_exception_types,
            unavailable_exception_predicate=self._unavailable_exception_predicate,
        )

    def run(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        return self._run_snapshot(self._snapshot(), func, *args, **kwargs)

    def _run_snapshot(
        self,
        snapshot: _BlockingGuardSnapshot,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        # Timeout and dependencies belong to this attempt. The source owner
        # supplies the immutable snapshot captured by the Runtime factory.
        def unavailable(exc: BaseException) -> bool:
            return bool(
                (
                    snapshot.unavailable_exception_types
                    and isinstance(exc, snapshot.unavailable_exception_types)
                )
                or (
                    snapshot.unavailable_exception_predicate is not None
                    and snapshot.unavailable_exception_predicate(exc)
                )
            )

        def release_cancelled(lease: CircuitAttemptLease | None) -> None:
            if lease is None:
                return
            release = getattr(snapshot.breaker, "_release_cancelled_lease", None)
            if callable(release):
                release(lease)

        if self._closed:
            raise RuntimeDependencyUnavailableError(
                snapshot.dependency_name,
                detail=f"{snapshot.dependency_name} dependency guard is closed",
            )
        active = getattr(snapshot.execution, "attempt", None)
        if active is not None:
            # The outer attempt owns the deadline and breaker lease. Keep nested
            # transaction operations on its worker; copied contexts on another
            # worker must not inherit this thread-affine permission.
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if unavailable(exc):
                    active.unavailable = True
                    raise RuntimeDependencyUnavailableError(
                        snapshot.dependency_name,
                        detail=str(exc) or f"{snapshot.dependency_name} is temporarily unavailable",
                    ) from exc
                raise
        lease = snapshot.breaker.acquire_attempt()
        if lease is None:
            raise RuntimeDependencyUnavailableError(
                snapshot.dependency_name,
                detail=f"{snapshot.dependency_name} circuit breaker is open",
            )
        try:
            context = contextvars.copy_context()
            attempt = _BlockingAttempt()

            def _invoke() -> T:
                with attempt.lock:
                    attempt.started_at = time.monotonic()
                snapshot.execution.attempt = attempt
                try:
                    value = func(*args, **kwargs)
                except BaseException as error:
                    with attempt.lock:
                        attempt.completion = _BlockingCompletion(
                            completed_at=time.monotonic(), error=error
                        )
                    raise
                else:
                    with attempt.lock:
                        attempt.completion = _BlockingCompletion(
                            completed_at=time.monotonic(), value=value
                        )
                    return value
                finally:
                    snapshot.execution.attempt = None

            submitted_at = time.monotonic()
            future = snapshot.executor.submit(context.run, _invoke)
        except RuntimeError as exc:
            release_cancelled(lease)
            raise RuntimeDependencyUnavailableError(
                snapshot.dependency_name,
                detail=f"{snapshot.dependency_name} executor is unavailable",
            ) from exc
        wait_started_at = time.monotonic()
        deadline = wait_started_at + snapshot.timeout_seconds
        operation_error: BaseException | None = None
        wait_timeout: FutureTimeoutError | None = None
        try:
            result = future.result(timeout=snapshot.timeout_seconds)
        except (FutureCancelledError, asyncio.CancelledError):
            release_cancelled(lease)
            raise
        except FutureTimeoutError as exc:
            wait_timeout = exc
        except Exception as exc:
            operation_error = exc

        # Future.result uses the same TimeoutError class as an operation, and
        # the worker may finish before its Future publishes that outcome. Use
        # the operation's own timestamp, including when a late worker finishes
        # before the waiting thread gets scheduled again.
        with attempt.lock:
            completion = attempt.completion
        expired = (
            completion.completed_at > deadline
            if completion is not None
            else wait_timeout is not None
        )
        if expired:
            cancelled = future.cancel()
            if not cancelled and snapshot.on_timeout is not None:
                snapshot.on_timeout(future)
            observed_at = time.monotonic()
            with attempt.lock:
                started_at = attempt.started_at
                observed_completion = attempt.completion
            if cancelled:
                disposition = "cancelled_before_start"
            elif observed_completion is not None:
                disposition = "finished_after_deadline"
            elif started_at is not None:
                disposition = "running_at_observation"
            else:
                disposition = "start_not_observed"
            diagnostic: dict[str, object] = {
                "timeout_seconds": snapshot.timeout_seconds,
                "wait_elapsed_seconds": max(0.0, observed_at - wait_started_at),
                "queue_wait_seconds": (
                    max(0.0, started_at - submitted_at) if started_at is not None else None
                ),
                "operation_elapsed_seconds": (
                    max(
                        0.0,
                        (observed_completion.completed_at if observed_completion else observed_at)
                        - started_at,
                    )
                    if started_at is not None
                    else None
                ),
                "wait_disposition": disposition,
                "operation": _safe_operation_identity(func),
                "caller": _safe_guard_caller(),
            }
            snapshot.breaker.record_failure(lease)
            raise _BlockingDependencyWaitTimeoutError(
                snapshot.dependency_name, diagnostic=diagnostic
            ) from wait_timeout
        if wait_timeout is not None and completion is not None:
            result = cast("T", completion.value)
            operation_error = completion.error
        if operation_error is not None:
            if isinstance(operation_error, FutureCancelledError | asyncio.CancelledError):
                release_cancelled(lease)
                raise operation_error
            if not isinstance(operation_error, Exception):
                raise operation_error
            if attempt.unavailable:
                snapshot.breaker.record_failure(lease)
                raise operation_error
            if unavailable(operation_error):
                snapshot.breaker.record_failure(lease)
                raise RuntimeDependencyUnavailableError(
                    snapshot.dependency_name,
                    detail=str(operation_error)
                    or f"{snapshot.dependency_name} is temporarily unavailable",
                ) from operation_error
            snapshot.breaker.record_success(lease)
            raise operation_error
        if attempt.unavailable:
            snapshot.breaker.record_failure(lease)
        else:
            snapshot.breaker.record_success(lease)
        return result

    def _release_cancelled_lease(self, lease: CircuitAttemptLease | None) -> None:
        if lease is None:
            return
        release = getattr(self._breaker, "_release_cancelled_lease", None)
        if callable(release):
            release(lease)

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
            if self._is_unavailable_exception(exc):
                self._breaker.record_failure(lease)
                raise RuntimeDependencyUnavailableError(
                    self._dependency_name,
                    detail=str(exc) or f"{self._dependency_name} is temporarily unavailable",
                ) from exc
            self._breaker.record_success(lease)
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
        if lease is None:
            return
        release = getattr(self._breaker, "_release_cancelled_lease", None)
        if callable(release):
            release(lease)


class GuardedDependencyProxy:
    """Wrap a dependency object so each callable is guarded by timeout/breaker policy."""

    def __init__(self, *, target: Any, guard: BlockingDependencyGuard) -> None:
        self._target = target
        self._guard = guard

    def run_operation(self, operation: Callable[[], T]) -> T:
        """Run a complete operation, including its transaction, on one worker."""

        return _run_guarded_dependency(self._guard, operation)

    def with_ambient_ownership_enforcement(self) -> GuardedDependencyProxy:
        """Retain this runtime guard while selecting a tenant-enforced store view."""
        enforcer = getattr(self._target, "with_ambient_ownership_enforcement", None)
        if not callable(enforcer):
            return self
        enforced_target = _run_guarded_dependency(self._guard, enforcer)
        if enforced_target is self._target:
            return self
        return GuardedDependencyProxy(target=enforced_target, guard=self._guard)

    def __getattr__(self, name: str) -> Any:
        if name == "close":
            return self.close
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        @wraps(attr)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            return _run_guarded_dependency(self._guard, attr, *args, **kwargs)

        return _wrapped

    def close(self) -> None:
        try:
            target_close = getattr(self._target, "close", None)
            if callable(target_close):
                target_close()
        finally:
            self._guard.close()


@dataclass(frozen=True)
class _GuardedStoreSignatureVerifier:
    """Expose signature verification through the exact guarded CAS handle."""

    guarded_store: ArtifactStore

    def verify_signature(
        self,
        artifact_id: ArtifactID,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        store = cast("SignatureVerifyingArtifactStore", self.guarded_store)
        return store.verify_signature(artifact_id, verifier, strict_identity=strict_identity)


def build_guarded_signature_verifier(
    *, backend: str, guarded_store: ArtifactStore
) -> SignatureVerifyingArtifactStore | None:
    """Select filesystem signature verification without unwrapping its guard.

    Other configured backends do not currently own a detached-signature
    verifier and therefore remain explicitly unavailable. Callers that inject
    their own store must supply a separately typed capability.
    """

    if backend != "filesystem":
        return None
    return _GuardedStoreSignatureVerifier(guarded_store=guarded_store)


def run_guarded_dependency_operation[T](dependency: object, operation: Callable[[], T]) -> T:
    """Keep a complete operation within its configured dependency guard."""

    if isinstance(dependency, GuardedDependencyProxy):
        return dependency.run_operation(operation)
    return operation()


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
        unavailable_exception_types=(),
        unavailable_exception_predicate=lambda exc: isinstance(exc, OSError)
        and not isinstance(exc, FileNotFoundError | PermissionError),
    )


def build_runtime_control_store_guard() -> BlockingDependencyGuard:
    """Build the control-store guard with capacity reserved from compute work.

    Lease renewal and fencing are control-plane operations: placing them behind
    the candidate compute executor lets a saturated worker plus its queued item
    consume the entire service path.  The guard therefore owns its existing
    bounded dependency executor.  This does not add compute admission capacity;
    it only preserves the control path which decides who may publish results.
    """
    return BlockingDependencyGuard(
        dependency_name="control_plane_store",
        timeout_seconds=_env_float("POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS", 1.5),
        breaker=_build_breaker(
            circuit_id="runtime.control_store",
            env_prefix="POLISYOS_RUNTIME_CONTROL_STORE",
        ),
        executor_max_workers=_env_int("POLISYOS_RUNTIME_CONTROL_STORE_EXECUTOR_MAX_WORKERS", 4),
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


@dataclass(frozen=True, slots=True)
class _RuntimeFilesystemGuardBinding:
    backend: FileSystemCAS
    guard: BlockingDependencyGuard
    snapshot: _BlockingGuardSnapshot
    breaker: object
    executor: object
    execution: object
    timeout_seconds: float
    unavailable_exception_types: tuple[type[BaseException], ...]
    unavailable_exception_predicate: object


# Capture the actual Runtime implementation, not an instance-supplied runner.
_RUNTIME_CAS_GUARD_FACTORY = build_runtime_cas_guard
_RUNTIME_CAS_GUARD_FACTORY_CODE = build_runtime_cas_guard.__code__
_RUNTIME_BLOCKING_GUARD_CODE = BlockingDependencyGuard._run_snapshot.__code__
_ACTIVE_REGISTERED_ACQUISITION_GUARD: contextvars.ContextVar[
    tuple[BlockingDependencyGuard, _BlockingGuardSnapshot, Callable[[Future[Any]], None]] | None
] = contextvars.ContextVar("registered_acquisition_guard", default=None)


def _run_guarded_dependency[T](
    guard: BlockingDependencyGuard, func: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    active = _ACTIVE_REGISTERED_ACQUISITION_GUARD.get()
    if active is None or active[0] is not guard:
        return guard.run(func, *args, **kwargs)
    snapshot = replace(active[1], on_timeout=active[2])
    run = FunctionType(_RUNTIME_BLOCKING_GUARD_CODE, globals())
    return cast("T", run(guard, snapshot, func, *args, **kwargs))


_RUNTIME_FILESYSTEM_GUARDS: WeakKeyDictionary[
    GuardedDependencyProxy, _RuntimeFilesystemGuardBinding
] = WeakKeyDictionary()
_RUNTIME_FILESYSTEM_GUARDS_LOCK = threading.RLock()


def _require_runtime_filesystem_guard(
    guarded_store: object,
) -> _RuntimeFilesystemGuardBinding:
    from polisyos.core.artifacts.store import FileSystemCAS

    if type(guarded_store) is not GuardedDependencyProxy:
        raise ValueError("registered_sql_guard_binding_not_established")
    with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
        binding = _RUNTIME_FILESYSTEM_GUARDS.get(guarded_store)
    if binding is None:
        raise ValueError("registered_sql_guard_binding_not_established")
    if (
        type(binding.backend) is not FileSystemCAS
        or type(binding.guard) is not BlockingDependencyGuard
        or guarded_store._target is not binding.backend
        or guarded_store._guard is not binding.guard
        or binding.guard._dependency_name != binding.snapshot.dependency_name
        or binding.guard._breaker is not binding.breaker
        or binding.guard._executor is not binding.executor
        or binding.guard._execution is not binding.execution
        or binding.guard._timeout_seconds != binding.timeout_seconds
        or binding.guard._unavailable_exception_types != binding.unavailable_exception_types
        or binding.guard._unavailable_exception_predicate
        is not binding.unavailable_exception_predicate
    ):
        raise ValueError("registered_sql_guard_binding_changed")
    return binding


def _require_runtime_ambient_ownership(guarded_store: object) -> None:
    """Require the installed exact CAS to enforce the caller's tenant context."""
    binding = _require_runtime_filesystem_guard(guarded_store)
    if (
        binding.backend._ownership_enforced is not True
        or binding.backend._tenant_id is not None
        or binding.backend._cell_id is not None
    ):
        raise ValueError("registered_sql_ambient_ownership_not_established")


def _has_runtime_filesystem_guard(guarded_store: object) -> bool:
    if type(guarded_store) is not GuardedDependencyProxy:
        return False
    with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
        return guarded_store in _RUNTIME_FILESYSTEM_GUARDS


class _GuardedRegisteredSourceOwner:
    """Guard complete source-owner operations using the installed CAS guard."""

    _OPERATIONS = frozenset(
        {
            "register",
            "admit",
            "transition",
            "event_receipt",
            "materialization_event",
            "scope_head",
            "carrier_history",
            "read",
            "run_serialized_acquisition",
            "install_issuer_verifier",
            "require_issuer_verifier",
        }
    )

    def __init__(
        self,
        *,
        guarded_store: GuardedDependencyProxy,
        source_owner: object,
        decision_owner: object,
    ) -> None:
        from polisyos.scientist.validation.source_admission_owner import (
            _RegisteredSourceAdmissionOwner,
        )

        binding = _require_runtime_filesystem_guard(guarded_store)
        if type(source_owner) is not _RegisteredSourceAdmissionOwner:
            raise ValueError("registered_sql_source_owner_not_established")
        _RegisteredSourceAdmissionOwner._require_runtime_binding(
            source_owner,
            binding.backend,
            decision_owner=decision_owner,
            guarded_store=guarded_store,
        )
        self._guarded_store = guarded_store
        self._binding = binding
        self._source_owner = cast("_RegisteredSourceAdmissionOwner", source_owner)
        self._decision_owner = decision_owner
        self._check_backend = _RegisteredSourceAdmissionOwner._require_runtime_binding
        self._methods = {
            name: getattr(_RegisteredSourceAdmissionOwner, name) for name in self._OPERATIONS
        }

    def __getattr__(self, name: str) -> Any:
        if name not in self._OPERATIONS:
            raise AttributeError(name)
        method = self._methods[name]

        def execute(*args: Any, **kwargs: Any) -> Any:
            binding = _require_runtime_filesystem_guard(self._guarded_store)
            if binding is not self._binding:
                raise ValueError("registered_sql_guard_binding_changed")

            def invoke() -> Any:
                if _require_runtime_filesystem_guard(self._guarded_store) is not binding:
                    raise ValueError("registered_sql_guard_binding_changed")
                self._check_backend(
                    self._source_owner,
                    binding.backend,
                    decision_owner=self._decision_owner,
                    guarded_store=self._guarded_store,
                )
                result = method(self._source_owner, *args, **kwargs)
                if _require_runtime_filesystem_guard(self._guarded_store) is not binding:
                    raise ValueError("registered_sql_guard_binding_changed")
                return result

            if name == "run_serialized_acquisition":
                # Acquisition includes SQL and must not occupy the shared CAS
                # executor. Its actual owner/CAS calls enter the guard below;
                # a busy source stripe fails without waiting for another caller.
                # Ordinary guarded CAS calls inside the action need the same
                # in-flight completion retention as source-owner operations.
                from polisyos.scientist.validation.source_admission_owner import (
                    _retain_source_acquisition_until_complete,
                )

                token = _ACTIVE_REGISTERED_ACQUISITION_GUARD.set(
                    (binding.guard, binding.snapshot, _retain_source_acquisition_until_complete)
                )
                try:
                    return invoke()
                finally:
                    _ACTIVE_REGISTERED_ACQUISITION_GUARD.reset(token)
            # A function object is mutable through __code__. Execute the
            # factory-captured immutable code with this attempt's factory
            # snapshot, not a later mutable method lookup or guard fields.
            from polisyos.scientist.validation.source_admission_owner import (
                _retain_source_acquisition_until_complete,
            )

            run = FunctionType(_RUNTIME_BLOCKING_GUARD_CODE, globals())
            snapshot = replace(
                binding.snapshot, on_timeout=_retain_source_acquisition_until_complete
            )
            return run(binding.guard, snapshot, invoke)

        return execute


def _bind_registered_source_owner(*, owner: object, guarded_store: object) -> None:
    """Install one attested local backend under the existing validity owner.

    Only this trusted Runtime factory sees the exact backend; no caller-supplied
    callback, backend identity string, or proxy unwrapping acts as evidence.
    """
    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from polisyos.scientist.validation.source_admission_owner import _RegisteredSourceAdmissionOwner

    binding = _require_runtime_filesystem_guard(guarded_store)
    if type(owner) is not DecisionValidityService or owner._store is not guarded_store:
        raise ValueError("registered_sql_source_owner_not_established")
    existing = owner._source_admission
    if type(existing) is _GuardedRegisteredSourceOwner:
        if (
            existing._guarded_store is not guarded_store
            or existing._binding is not binding
            or existing._decision_owner is not owner
        ):
            raise ValueError("registered_sql_guard_binding_changed")
        existing._check_backend(
            existing._source_owner,
            binding.backend,
            decision_owner=owner,
            guarded_store=guarded_store,
        )
        return
    if type(existing) is not _RegisteredSourceAdmissionOwner:
        raise ValueError("registered_sql_source_owner_not_established")
    source_owner = _RegisteredSourceAdmissionOwner(
        binding.backend,
        owner._state._base,
        owner._state.owner_transaction,
        runtime_decision_owner=owner,
        runtime_guarded_store=guarded_store,
    )
    _RegisteredSourceAdmissionOwner._require_runtime_binding(
        source_owner, binding.backend, decision_owner=owner, guarded_store=guarded_store
    )
    wrapped = _GuardedRegisteredSourceOwner(
        guarded_store=cast("GuardedDependencyProxy", guarded_store),
        source_owner=source_owner,
        decision_owner=owner,
    )
    owner._source_admission = cast("Any", wrapped)


def guard_runtime_cas(target: Any) -> GuardedDependencyProxy:
    from polisyos.core.artifacts.store import FileSystemCAS

    if build_runtime_cas_guard is _RUNTIME_CAS_GUARD_FACTORY:
        # Retain legacy replacement of the factory object, but an in-place
        # __code__ replacement cannot become the attested factory execution.
        factory = FunctionType(_RUNTIME_CAS_GUARD_FACTORY_CODE, globals())
        guard = factory()
    else:
        guard = build_runtime_cas_guard()
    proxy = GuardedDependencyProxy(target=target, guard=guard)
    if (
        type(target) is FileSystemCAS
        and build_runtime_cas_guard is _RUNTIME_CAS_GUARD_FACTORY
        and type(guard) is BlockingDependencyGuard
        and type(guard._breaker) is CircuitBreaker
    ):
        binding = _RuntimeFilesystemGuardBinding(
            backend=target,
            guard=guard,
            snapshot=_BlockingGuardSnapshot(
                dependency_name=guard._dependency_name,
                timeout_seconds=guard._timeout_seconds,
                breaker=guard._breaker,
                executor=guard._executor,
                execution=guard._execution,
                unavailable_exception_types=guard._unavailable_exception_types,
                unavailable_exception_predicate=guard._unavailable_exception_predicate,
            ),
            breaker=guard._breaker,
            executor=guard._executor,
            execution=guard._execution,
            timeout_seconds=guard._timeout_seconds,
            unavailable_exception_types=guard._unavailable_exception_types,
            unavailable_exception_predicate=guard._unavailable_exception_predicate,
        )
        with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            _RUNTIME_FILESYSTEM_GUARDS[proxy] = binding
    return proxy


def guard_runtime_control_store(target: Any) -> GuardedDependencyProxy:
    return GuardedDependencyProxy(target=target, guard=build_runtime_control_store_guard())


__all__ = [
    "AsyncDependencyGuard",
    "BlockingDependencyGuard",
    "GuardedDependencyProxy",
    "build_guarded_signature_verifier",
    "build_runtime_opa_async_guard",
    "guard_runtime_cas",
    "guard_runtime_control_store",
    "run_guarded_dependency_operation",
]
