"""Dependency guards for runtime slow/unavailable CAS, OPA, and control-store paths."""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import math
import os
import sqlite3
import threading
import time
from collections.abc import Iterator, MutableMapping
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
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from functools import wraps
from types import FunctionType
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast
from weakref import WeakKeyDictionary, WeakSet

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactMemberReceipt,
        ArtifactRef,
        ArtifactStore,
        CoreJsonArtifactBoundedRead,
        CoreJsonManifestBoundedRead,
        CoreJsonReadLimits,
        Ed25519Verifier,
        FileSystemCAS,
        InputRef,
        SignatureVerificationResult,
        SignatureVerifyingArtifactStore,
        VerificationReport,
    )
    from polisyos.core.artifacts._transfer_ops import ImportPublication
    from polisyos.core.run.child_custody import ChildComputationCustody
    from polisyos.scientist.validation.source_admission_owner import _RegisteredSourceAdmissionOwner

from polisyos.common.async_tools import create_dependency_executor
from polisyos.common.borrowed_execution import _BlockingAttempt, _BorrowedExecutionGrant
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
    on_submit: Callable[[Future[Any]], None] | None = None
    on_interrupted: Callable[[Future[Any]], None] | None = None
    on_wait_done: Callable[[Future[Any]], None] | None = None
    parent_transition_lock: Any | None = None
    parent_budget_uncertain: threading.Event | None = None
    parent_lease_lost: threading.Event | None = None


@dataclass(frozen=True, slots=True)
class _GuardCompletionObservation:
    """Owner observation, not a durable completion or effect-settlement receipt."""

    physical_state: Literal["pending", "returned", "failed", "not_started"]
    interrupted: bool


class _GuardCompletionHandle:
    """Owner-issued observation of one actual guard dispatch, not effect settlement."""

    def __init__(self, guard: BlockingDependencyGuard, store: object, budget: object) -> None:
        self._guard = guard
        self._store = store
        self._budget = budget
        self._claim = budget.claim
        self._future: Future[Any] | None = None
        self._callback: object | None = None
        self._used = False
        self._interrupted = False
        self._wait_done = False
        self._lock = threading.Lock()

    def _require_current(self) -> None:
        from polisyos.runtime.http.services.control.child_execution_budget import (
            _require_attempt_budget,
        )

        if (
            _require_attempt_budget(self._budget.job_id, self._budget.run_id, self._budget.attempt)
            is not self._budget
        ):
            raise ValueError("guard_completion_budget_not_current")

    def _reserve(self, guard: BlockingDependencyGuard, callback: object) -> None:
        with self._lock:
            if self._guard is not guard or self._used:
                raise ValueError("guard_completion_handle_not_current")
            self._callback = callback
            self._used = True

    def matches_callback(self, appointed_callback: object) -> bool:
        """Compare the actual dispatched callable to an independently appointed object."""
        with self._lock:
            return self._used and self._callback is appointed_callback

    def _attach(self, future: Future[Any]) -> None:
        with self._lock:
            if not self._used or self._future is not None:
                raise ValueError("guard_completion_handle_already_attached")
            self._future = future

    def _mark_interrupted(self, future: Future[Any]) -> None:
        with self._lock:
            if self._future is not future:
                raise RuntimeError("guard_completion_future_mismatch")
            self._interrupted = True

    def _finish_wait(self, future: Future[Any]) -> None:
        with self._lock:
            if self._future is not future:
                raise RuntimeError("guard_completion_future_mismatch")
            self._wait_done = True

    def observe(self) -> _GuardCompletionObservation:
        """Read exact persisted claim and actual physical worker-wrapper completion.

        A returned callable is not evidence of child/effect/ledger settlement.
        Process loss or an unattached handle is not successful completion.
        """
        from polisyos.common.async_tools import _SharedFuture, get_shared_executor

        with self._lock:
            future = self._future
            used = self._used
        if not used or future is None:
            return _GuardCompletionObservation("pending", True)
        if (
            type(future) is not _SharedFuture
            or future._executor is not get_shared_executor()
            or self._budget.claim is not self._claim
            or self._store.read_child_attempt_budget(self._claim.job_id, self._claim.attempt)
            != self._claim
        ):
            raise RuntimeError("guard_completion_owner_reconciliation_failed")
        # The owner signal and this final observation share one transition lock.
        # The durable readback above is deliberately outside it.
        with self._budget.transition_lock, self._lock:
            interrupted = (
                self._interrupted
                or self._budget.uncertain.is_set()
                or self._budget.interrupt.lost.is_set()
            )
            if not self._wait_done:
                return _GuardCompletionObservation("pending", interrupted)
            return _GuardCompletionObservation(future._physical_completion_state(), interrupted)


class BlockingDependencyGuard:
    """Protect one blocking dependency with timeout and a circuit breaker."""

    _BINDING_FIELDS = frozenset(
        {
            "_dependency_name",
            "_timeout_seconds",
            "_breaker",
            "_executor",
            "_execution",
            "_unavailable_exception_types",
            "_unavailable_exception_predicate",
        }
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if (
            name in {"_runtime_binding_revision", "_runtime_lifecycle_revision", "_runtime_lock"}
            and name in self.__dict__
        ):
            raise AttributeError("runtime guard binding state is owner-controlled")
        if name in BlockingDependencyGuard._BINDING_FIELDS | {"_closed"} and name in self.__dict__:
            with self._runtime_lock:
                revision = (
                    "_runtime_lifecycle_revision"
                    if name == "_closed"
                    else "_runtime_binding_revision"
                )
                object.__setattr__(self, revision, object())
                object.__setattr__(self, name, value)
            return
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in {"_runtime_binding_revision", "_runtime_lifecycle_revision", "_runtime_lock"}:
            raise AttributeError("runtime guard binding state is owner-controlled")
        if name in BlockingDependencyGuard._BINDING_FIELDS | {"_closed"} and name in self.__dict__:
            with self._runtime_lock:
                revision = (
                    "_runtime_lifecycle_revision"
                    if name == "_closed"
                    else "_runtime_binding_revision"
                )
                object.__setattr__(self, revision, object())
                object.__delattr__(self, name)
            return
        object.__delattr__(self, name)

    def __init__(
        self,
        *,
        dependency_name: str,
        timeout_seconds: float,
        breaker: CircuitBreaker,
        executor_max_workers: int = 4,
        executor: ThreadPoolExecutor | None = None,
        owns_executor: bool = False,
        unavailable_exception_types: tuple[type[BaseException], ...] = (),
        unavailable_exception_predicate: Callable[[BaseException], bool] | None = None,
    ) -> None:
        self._runtime_lock = threading.RLock()
        self._dependency_name = dependency_name
        # Blocking dependencies routinely pay thread handoff + filesystem/SQLite
        # scheduling overhead, so a 50ms floor is too aggressive and can trip the
        # breaker on healthy startup paths under suite or production load.
        self._timeout_seconds = max(timeout_seconds, _MIN_BLOCKING_TIMEOUT_SECONDS)
        self._breaker = breaker
        self._closed = False
        self._owns_executor = executor is None or owns_executor
        self._timed_out_lock = threading.Lock()
        self._timed_out_futures: set[Future[Any]] = set()
        self._unobservable_timeout = False
        self._completion_handles: WeakSet[_GuardCompletionHandle] = WeakSet()
        self._completion_lock = threading.Lock()
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max(executor_max_workers, 1),
            thread_name_prefix=f"runtime-{dependency_name}",
        )
        self._unavailable_exception_types = unavailable_exception_types
        self._unavailable_exception_predicate = unavailable_exception_predicate
        self._execution = threading.local()
        self._runtime_binding_revision = object()
        self._runtime_lifecycle_revision = object()

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

    def create_parent_completion(
        self, control_store: object, budget: object
    ) -> _GuardCompletionHandle:
        """Bind an actual live attempt budget and committed claim to this guard."""
        from polisyos.runtime.http.services.control.child_execution_budget import (
            ChildBudgetClaimLocator,
            _AttemptBudget,
            _require_attempt_budget,
        )
        from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

        if (
            type(control_store) not in {ControlPlaneStore, GuardedDependencyProxy}
            or type(budget) is not _AttemptBudget
        ):
            raise TypeError("guard_completion_owner_type_invalid")
        if _require_attempt_budget(budget.job_id, budget.run_id, budget.attempt) is not budget:
            raise ValueError("guard_completion_budget_not_current")
        claim = budget.claim
        if (
            type(claim) is not ChildBudgetClaimLocator
            or budget.control_store is not control_store
            or (claim.job_id, claim.run_id, claim.attempt, claim.worker_id)
            != (budget.job_id, budget.run_id, budget.attempt, budget.interrupt.worker_id)
        ):
            raise ValueError("guard_completion_claim_owner_mismatch")
        if control_store.read_child_attempt_budget(budget.job_id, budget.attempt) != claim:
            raise ValueError("guard_completion_claim_mismatch")
        handle = _GuardCompletionHandle(self, control_store, budget)
        with self._completion_lock:
            self._completion_handles.add(handle)
        return handle

    def run_with_parent_admission(
        self,
        func: Callable[[_BorrowedExecutionGrant], T],
        *,
        deadline_monotonic: float,
        completion: _GuardCompletionHandle | None = None,
    ) -> T:
        """Run the parent on the shared owner, bounded by its inherited deadline."""
        if not math.isfinite(deadline_monotonic):
            raise ValueError("parent_execution_deadline_must_be_finite")
        remaining = deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("parent_execution_deadline_expired")

        def invoke() -> T:
            if completion is not None:
                completion._require_current()
            attempt = getattr(self._execution, "attempt", None)
            if not isinstance(attempt, _BlockingAttempt) or attempt.grant is not None:
                raise RuntimeError("parent_execution_admission_unavailable")
            attempt.deadline = min(attempt.deadline, deadline_monotonic)
            grant = _BorrowedExecutionGrant(attempt, self._execution, self._executor)
            attempt.grant = grant
            try:
                grant.check_current()
                return func(grant)
            finally:
                attempt.revoke()

        snapshot = self._snapshot()
        if completion is not None:
            if type(completion) is not _GuardCompletionHandle:
                raise TypeError("guard_completion_handle_type_invalid")
            completion._require_current()
            if deadline_monotonic != completion._budget.deadline_monotonic:
                raise ValueError("guard_completion_deadline_mismatch")
            with self._completion_lock:
                if completion not in self._completion_handles:
                    raise ValueError("guard_completion_handle_not_issued")
                completion._reserve(self, func)
            snapshot = replace(
                snapshot,
                on_submit=completion._attach,
                on_interrupted=completion._mark_interrupted,
                on_wait_done=completion._finish_wait,
                parent_transition_lock=completion._budget.transition_lock,
                parent_budget_uncertain=completion._budget.uncertain,
                parent_lease_lost=completion._budget.interrupt.lost,
            )
        return self._run_snapshot(
            replace(snapshot, timeout_seconds=min(snapshot.timeout_seconds, remaining)), invoke
        )

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
            attempt = _BlockingAttempt(deadline=time.monotonic() + snapshot.timeout_seconds)
            # Fix the issuer's synchronization identity before the attempt can
            # be observed by either the worker or the timeout/revocation path.
            if snapshot.parent_transition_lock is not None:
                attempt.transition_lock = snapshot.parent_transition_lock
                attempt.budget_uncertain = snapshot.parent_budget_uncertain
                attempt.lease_lost = snapshot.parent_lease_lost

            def _invoke() -> T:
                snapshot.execution.attempt = attempt
                try:
                    return func(*args, **kwargs)
                finally:
                    attempt.revoke()
                    snapshot.execution.attempt = None

            future = snapshot.executor.submit(context.run, _invoke)
            if snapshot.on_submit is not None:
                snapshot.on_submit(future)
        except RuntimeError as exc:
            release_cancelled(lease)
            raise RuntimeDependencyUnavailableError(
                snapshot.dependency_name,
                detail=f"{snapshot.dependency_name} executor is unavailable",
            ) from exc
        try:
            result = future.result(timeout=snapshot.timeout_seconds)
        except (FutureCancelledError, asyncio.CancelledError):
            attempt.revoke()
            self._retain_timed_out_future(future)
            if snapshot.on_interrupted is not None:
                snapshot.on_interrupted(future)
            release_cancelled(lease)
            if snapshot.on_wait_done is not None:
                snapshot.on_wait_done(future)
            raise
        except FutureTimeoutError as exc:
            attempt.revoke()
            if snapshot.on_interrupted is not None:
                snapshot.on_interrupted(future)
            cancelled = future.cancel()
            # Cancellation may precede the executor's queue and callback cleanup.
            # Retain the actual owner's observation even for a queued cancellation.
            self._retain_timed_out_future(future)
            if not cancelled and snapshot.on_timeout is not None:
                snapshot.on_timeout(future)
            snapshot.breaker.record_failure(lease)
            if snapshot.on_wait_done is not None:
                snapshot.on_wait_done(future)
            raise RuntimeDependencyTimeoutError(snapshot.dependency_name) from exc
        except Exception as exc:
            self._retain_timed_out_future(future)
            if attempt.unavailable or unavailable(exc):
                snapshot.breaker.record_failure(lease)
                if snapshot.on_wait_done is not None:
                    snapshot.on_wait_done(future)
                if attempt.unavailable:
                    raise
                raise RuntimeDependencyUnavailableError(
                    snapshot.dependency_name,
                    detail=str(exc) or f"{snapshot.dependency_name} is temporarily unavailable",
                ) from exc
            snapshot.breaker.record_success(lease)
            if snapshot.on_wait_done is not None:
                snapshot.on_wait_done(future)
            raise
        except BaseException:
            attempt.revoke()
            self._retain_timed_out_future(future)
            if snapshot.on_interrupted is not None:
                snapshot.on_interrupted(future)
            if snapshot.on_wait_done is not None:
                snapshot.on_wait_done(future)
            raise
        if attempt.unavailable:
            snapshot.breaker.record_failure(lease)
        else:
            snapshot.breaker.record_success(lease)
        if snapshot.on_wait_done is not None:
            snapshot.on_wait_done(future)
        return result

    @staticmethod
    def _physically_unsettled(future: Future[Any]) -> bool:
        from polisyos.common.async_tools import _SharedFuture

        # A standard Future has no proof its physical wrapper released a slot.
        # Keep that boundary unknown rather than treating done() as quiescence.
        if type(future) is not _SharedFuture:
            return True
        return future._physical_completion_state() == "pending"

    def _retain_timed_out_future(self, future: Future[Any]) -> None:
        from polisyos.common.async_tools import _SharedFuture

        # Late callback registration can wait for pool capacity. A foreign
        # executor lacks a slot-release proof; retain one unknown bit instead of
        # an unbounded collection of completed Futures.
        with self._timed_out_lock:
            self._timed_out_futures = {
                item for item in self._timed_out_futures if self._physically_unsettled(item)
            }
            if type(future) is not _SharedFuture:
                self._unobservable_timeout = True
            elif self._physically_unsettled(future):
                self._timed_out_futures.add(future)

    def has_unsettled_operations(self) -> bool:
        """Report interrupted or failed operations lacking owner-observed cleanup."""
        with self._timed_out_lock:
            self._timed_out_futures = {
                item for item in self._timed_out_futures if self._physically_unsettled(item)
            }
            return self._unobservable_timeout or bool(self._timed_out_futures)

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

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_runtime_binding_revision", "_runtime_lock"} and name in self.__dict__:
            raise AttributeError("runtime proxy binding state is owner-controlled")
        if name in {"_target", "_guard"} and name in self.__dict__:
            with self._runtime_lock:
                object.__setattr__(self, "_runtime_binding_revision", object())
                object.__setattr__(self, name, value)
            return
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in {"_runtime_binding_revision", "_runtime_lock"}:
            raise AttributeError("runtime proxy binding state is owner-controlled")
        if name in {"_target", "_guard"} and name in self.__dict__:
            with self._runtime_lock:
                object.__setattr__(self, "_runtime_binding_revision", object())
                object.__delattr__(self, name)
            return
        object.__delattr__(self, name)

    def __init__(self, *, target: Any, guard: BlockingDependencyGuard) -> None:
        self._runtime_lock = threading.RLock()
        self._target = target
        self._guard = guard
        self._runtime_binding_revision = object()

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
    """Build an independently bounded CAS I/O owner with its own timeout."""
    workers = max(_env_int("POLISYOS_RUNTIME_CAS_EXECUTOR_MAX_WORKERS", 4), 1)
    queued = max(_env_int("POLISYOS_RUNTIME_CAS_EXECUTOR_MAX_QUEUED", workers), 0)
    executor = create_dependency_executor(
        max_workers=workers, max_queued=queued, thread_name_prefix="runtime-cas-io"
    )
    return BlockingDependencyGuard(
        dependency_name="content_addressed_storage",
        timeout_seconds=_env_float("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", 1.5),
        breaker=_build_breaker(circuit_id="runtime.cas", env_prefix="POLISYOS_RUNTIME_CAS"),
        executor=executor,
        owns_executor=True,
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
    proxy_revision: object
    guard_revision: object
    registration_revision: object


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


_RUNTIME_FILESYSTEM_GUARDS_LOCK = threading.RLock()


class _RuntimeFilesystemGuardRegistry(
    MutableMapping[GuardedDependencyProxy, _RuntimeFilesystemGuardBinding]
):
    """Keep each registration's identity invalid after removal or replacement."""

    def __init__(self) -> None:
        self._entries: WeakKeyDictionary[GuardedDependencyProxy, _RuntimeFilesystemGuardBinding] = (
            WeakKeyDictionary()
        )
        self._revisions: WeakKeyDictionary[GuardedDependencyProxy, object] = WeakKeyDictionary()

    def __getitem__(self, key: GuardedDependencyProxy) -> _RuntimeFilesystemGuardBinding:
        with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            return self._entries[key]

    def __setitem__(
        self, key: GuardedDependencyProxy, value: _RuntimeFilesystemGuardBinding
    ) -> None:
        with key._runtime_lock, _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            self._revisions[key] = (
                object() if key in self._revisions else value.registration_revision
            )
            self._entries[key] = value

    def __delitem__(self, key: GuardedDependencyProxy) -> None:
        with key._runtime_lock, _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            del self._entries[key]
            self._revisions[key] = object()

    def __iter__(self) -> Iterator[GuardedDependencyProxy]:
        with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            return iter(tuple(self._entries))

    def __len__(self) -> int:
        with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            return len(self._entries)

    def is_current(
        self, key: GuardedDependencyProxy, binding: _RuntimeFilesystemGuardBinding
    ) -> bool:
        with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            return self._revisions.get(key) is binding.registration_revision


_RUNTIME_FILESYSTEM_GUARDS = _RuntimeFilesystemGuardRegistry()


def _require_runtime_filesystem_guard(
    guarded_store: object,
) -> _RuntimeFilesystemGuardBinding:
    from polisyos.core.artifacts.store import FileSystemCAS

    if type(guarded_store) is not GuardedDependencyProxy:
        raise ValueError("registered_sql_guard_binding_not_established")
    with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
        binding = _RUNTIME_FILESYSTEM_GUARDS.get(guarded_store)
        registration_current = binding is not None and _RUNTIME_FILESYSTEM_GUARDS.is_current(
            guarded_store, binding
        )
    if binding is None:
        raise ValueError("registered_sql_guard_binding_not_established")
    if (
        type(binding.backend) is not FileSystemCAS
        or type(binding.guard) is not BlockingDependencyGuard
        or not registration_current
        or guarded_store._runtime_binding_revision is not binding.proxy_revision
        or binding.guard._runtime_binding_revision is not binding.guard_revision
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


def run_guarded_cas_operation[T](guarded_store: object, operation: Callable[[], T]) -> T:
    """Run an entire trusted CAS operation only through its appointed exact guard."""
    _require_runtime_filesystem_guard(guarded_store)
    return run_guarded_dependency_operation(guarded_store, operation)


def run_guarded_cas_member(
    guarded_store: object,
    artifact_ref: object,
    member: str,
    consume: Callable[[Any], bytes],
    **options: Any,
) -> bytes:
    """Run full selected CAS stream enter, consumption and exit on its guard worker.

    The trusted consumer must not retain the stream or perform unrelated work.
    This managed interface is not a sandbox for arbitrary in-process Python.
    """
    binding = _require_runtime_filesystem_guard(guarded_store)

    def read() -> bytes:
        with binding.backend.open_member(artifact_ref, member, **options) as stream:
            result = consume(stream)
            if type(result) is not bytes:
                raise ValueError("guarded_cas_member_result_must_be_bytes")
            return result

    return run_guarded_cas_operation(guarded_store, read)


class ChildGuardedReadOwner:
    """Fixed guarded read service retained by one trusted Core custody session."""

    __slots__ = (
        "_owner_thread",
        "_served_backend",
        "_served_lifecycle",
        "_served_proxy",
        "_served_registration",
        "_session",
        "_stage_backend",
        "_stage_lifecycle",
        "_stage_proxy",
        "_stage_registration",
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, name):
            raise AttributeError("child guarded service binding is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("child guarded service binding is immutable")

    def __init__(self, session: object, served_proxy: object) -> None:
        from polisyos.core.artifacts import FileSystemCAS
        from polisyos.core.run.child_custody import ChildComputationCustody

        if type(session) is not ChildComputationCustody:
            raise TypeError("child_read_session_type_invalid")
        served = _require_runtime_filesystem_guard(served_proxy)
        if served.backend is not session._served or type(session._stage) is not FileSystemCAS:
            raise ValueError("child_read_backend_owner_mismatch")
        self._session = session
        self._owner_thread = threading.get_ident()
        self._served_backend = served.backend
        self._served_proxy = served_proxy
        self._served_registration = served
        self._served_lifecycle = served.guard._runtime_lifecycle_revision
        self._stage_backend = session._stage
        self._stage_proxy = guard_runtime_cas(self._stage_backend)
        self._stage_registration = _require_runtime_filesystem_guard(self._stage_proxy)
        self._stage_lifecycle = self._stage_registration.guard._runtime_lifecycle_revision

    def require_registration(self) -> None:
        """Recheck both exact registry entries before Core owner decisions."""
        if threading.get_ident() != self._owner_thread:
            raise ValueError("child_read_owner_thread_mismatch")
        if (
            _require_runtime_filesystem_guard(self._served_proxy) is not self._served_registration
            or _require_runtime_filesystem_guard(self._stage_proxy) is not self._stage_registration
            or self._served_registration.guard._runtime_lifecycle_revision
            is not self._served_lifecycle
            or self._stage_registration.guard._runtime_lifecycle_revision
            is not self._stage_lifecycle
            or self._served_registration.guard._closed
            or self._stage_registration.guard._closed
        ):
            raise ValueError("child_read_guard_binding_changed")

    @contextmanager
    def publication_registration(self) -> Iterator[None]:
        """Order one short owner-head commit against registration transitions."""
        with ExitStack() as stack:
            for lock in (
                self._served_proxy._runtime_lock,
                self._served_registration.guard._runtime_lock,
                self._stage_proxy._runtime_lock,
                self._stage_registration.guard._runtime_lock,
            ):
                stack.enter_context(lock)
            self.require_registration()
            yield

    def _claim(self, capability: object) -> tuple[object, ArtifactRef]:
        from polisyos.core.artifacts import ArtifactRef
        from polisyos.core.run.child_custody import ChildOneRefReadCapability

        if threading.get_ident() != self._owner_thread:
            raise ValueError("child_read_owner_thread_mismatch")
        if type(capability) is not ChildOneRefReadCapability:
            raise TypeError("child_read_capability_type_invalid")
        backend, ref = ChildOneRefReadCapability._claim_for_runtime(capability, self._session)
        if type(ref) is not ArtifactRef or not ref.manifest_profile_sha256:
            raise ValueError("child_read_selected_profile_missing")
        if backend is self._served_backend:
            proxy = self._served_proxy
        elif backend is self._stage_backend:
            proxy = self._stage_proxy
        else:
            raise ValueError("child_read_backend_owner_mismatch")
        if _require_runtime_filesystem_guard(proxy).backend is not backend:
            raise ValueError("child_read_guard_binding_changed")
        return proxy, ref.model_copy(deep=True)

    def _confirm(self, capability: object, proxy: object, ref: ArtifactRef) -> None:
        current_proxy, current_ref = self._claim(capability)
        if current_proxy is not proxy or current_ref != ref:
            raise ValueError("child_read_scope_changed_during_operation")

    def _run_read[T](self, proxy: object, operation: Callable[[], T]) -> T:
        from polisyos.core.run.child_custody import ChildGuardedReadUnknown

        try:
            return run_guarded_cas_operation(proxy, operation)
        except RuntimeDependencyTimeoutError as exc:
            raise ChildGuardedReadUnknown(self._session._recovery_locator()) from exc

    def has(self, capability: object) -> bool:
        """Check exact selected availability through the appointed CAS guard."""
        proxy, ref = self._claim(capability)
        result = self._run_read(proxy, lambda: proxy.has(ref))
        self._confirm(capability, proxy, ref)
        if type(result) is not bool:
            raise ValueError("child_has_result_must_be_boolean")
        return result

    def verify(self, capability: object) -> VerificationReport:
        """Verify the exact selected profile through the appointed CAS guard."""
        from polisyos.core.artifacts import VerificationReport

        proxy, ref = self._claim(capability)
        result = self._run_read(proxy, lambda: proxy.verify(ref))
        self._confirm(capability, proxy, ref)
        if type(result) is not VerificationReport:
            raise ValueError("child_verify_result_type_invalid")
        return result

    def read_blob(self, capability: object) -> bytes:
        """Run the existing complete selected blob read under the CAS guard."""
        proxy, ref = self._claim(capability)
        result = self._run_read(proxy, lambda: proxy.get_bytes(ref))
        self._confirm(capability, proxy, ref)
        if type(result) is not bytes:
            raise ValueError("child_read_blob_result_must_be_bytes")
        return result

    def read_manifest(
        self, capability: object, *, max_manifest_bytes: int, allow_profile_absent: bool
    ) -> CoreJsonManifestBoundedRead:
        """Read one exact selected bounded manifest on the CAS worker."""
        from polisyos.core.artifacts import read_core_manifest_profile_bounded

        proxy, ref = self._claim(capability)
        result = self._run_read(
            proxy,
            lambda: read_core_manifest_profile_bounded(
                proxy,
                ref,
                max_manifest_bytes=max_manifest_bytes,
                allow_profile_absent=allow_profile_absent,
            ),
        )
        self._confirm(capability, proxy, ref)
        if result.effective_ref != ref:
            raise ValueError("child_read_manifest_selection_mismatch")
        return result

    def read_input_manifest(
        self, capability: object, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> CoreJsonManifestBoundedRead:
        """Read the canonical input edge against the admitted exact profile."""
        from polisyos.core.artifacts import (
            InputRef,
            read_core_input_manifest_profile_bounded,
        )

        proxy, ref = self._claim(capability)
        if (
            type(input_ref) is not InputRef
            or input_ref.artifact_id != ref.artifact_id
            or input_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
        ):
            raise ValueError("child_read_input_selection_mismatch")
        frozen_input = input_ref.model_copy(deep=True)
        result = self._run_read(
            proxy,
            lambda: read_core_input_manifest_profile_bounded(
                proxy, frozen_input, max_manifest_bytes=max_manifest_bytes
            ),
        )
        self._confirm(capability, proxy, ref)
        if result.effective_ref != ref:
            raise ValueError("child_read_input_effective_ref_mismatch")
        return result

    def read_json(
        self, capability: object, *, limits: CoreJsonReadLimits
    ) -> CoreJsonArtifactBoundedRead:
        """Run the entire canonical bounded reader and preserve its actual usage."""
        from polisyos.core.artifacts import read_core_json_artifact_bounded

        proxy, ref = self._claim(capability)
        result = self._run_read(
            proxy, lambda: read_core_json_artifact_bounded(proxy, ref, limits=limits)
        )
        self._confirm(capability, proxy, ref)
        return result

    def verify_blob(
        self, capability: object, *, max_manifest_bytes: int, max_member_bytes: int
    ) -> ArtifactMemberReceipt:
        """Consume one bounded selected blob on the worker without exposing its stream."""
        from polisyos.core.artifacts import read_core_manifest_profile_bounded

        proxy, ref = self._claim(capability)

        def verify() -> ArtifactMemberReceipt:
            manifest = read_core_manifest_profile_bounded(
                proxy, ref, max_manifest_bytes=max_manifest_bytes, allow_profile_absent=True
            )
            if manifest.effective_ref != ref:
                raise ValueError("child_read_manifest_selection_mismatch")
            digest = hashlib.sha256(manifest.raw_manifest_bytes).hexdigest()
            with proxy.open_member_bounded(
                ref,
                "blob",
                max_manifest_bytes=max_manifest_bytes,
                expected_manifest_sha256=digest,
                max_member_bytes=max_member_bytes,
            ) as stream:
                while stream.read(65536):
                    pass
            return stream.receipt

        result = self._run_read(proxy, verify)
        self._confirm(capability, proxy, ref)
        return result

    def _claim_stage_write(
        self, capability: object, kind: str
    ) -> tuple[object, object, object, object, object]:
        from polisyos.core.artifacts import ArtifactWriteOptions
        from polisyos.core.run.child_custody import ChildStageWriteCapability

        if threading.get_ident() != self._owner_thread:
            raise ValueError("child_write_owner_thread_mismatch")
        if type(capability) is not ChildStageWriteCapability:
            raise TypeError("child_write_capability_type_invalid")
        claim = ChildStageWriteCapability._claim_for_runtime(capability, self._session)
        stage, operation, payload, options, spec = claim
        if (
            stage is not self._stage_backend
            or operation != kind
            or type(options) is not ArtifactWriteOptions
            or (kind == "bytes" and (type(payload) is not bytes or spec is not None))
        ):
            raise ValueError("child_write_owner_binding_mismatch")
        if _require_runtime_filesystem_guard(self._stage_proxy).backend is not stage:
            raise ValueError("child_write_guard_binding_changed")
        return claim

    def write_bytes(self, capability: object) -> ArtifactRef:
        """Write one Core-owned immutable payload to the selected private stage."""
        from polisyos.core.artifacts import ArtifactRef

        claim = self._claim_stage_write(capability, "bytes")
        _, _, payload, options, _ = claim
        proxy = self._stage_proxy
        result = run_guarded_cas_operation(
            proxy, lambda: proxy.put_bytes(payload, options, return_selected_profile=True)
        )
        if self._claim_stage_write(capability, "bytes") != claim:
            raise ValueError("child_write_scope_changed_during_operation")
        if type(result) is not ArtifactRef or not result.manifest_profile_sha256:
            raise ValueError("child_write_selected_profile_missing")
        return result

    def write_json(self, capability: object) -> ArtifactRef:
        """Write a Core-detached canonical payload to the selected private stage."""
        from polisyos.core.artifacts import ArtifactRef

        claim = self._claim_stage_write(capability, "json")
        _, _, payload, options, spec = claim
        proxy = self._stage_proxy
        result = run_guarded_cas_operation(
            proxy, lambda: proxy.put_json(payload, options, spec, return_selected_profile=True)
        )
        if self._claim_stage_write(capability, "json") != claim:
            raise ValueError("child_write_scope_changed_during_operation")
        if type(result) is not ArtifactRef or not result.manifest_profile_sha256:
            raise ValueError("child_write_selected_profile_missing")
        return result

    def transfer_selected(self, capability: object) -> ImportPublication:
        """Transfer one Core-authorized exact profile set without committing a head."""
        from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
        from polisyos.core.artifacts.child_release import _CHILD_STAGING_TOKEN
        from polisyos.core.run.child_custody import ChildSelectedTransferCapability

        if threading.get_ident() != self._owner_thread:
            raise ValueError("child_transfer_owner_thread_mismatch")
        if type(capability) is not ChildSelectedTransferCapability:
            raise TypeError("child_transfer_capability_type_invalid")
        source, destination, refs, ledger = ChildSelectedTransferCapability._claim_for_runtime(
            capability, self._session
        )
        if (
            source is not self._stage_backend
            or destination is not self._served_backend
            or ledger is not self._session._ledger
            or type(refs) is not tuple
            or not refs
            or any(type(ref) is not ArtifactRef or not ref.manifest_profile_sha256 for ref in refs)
        ):
            raise ValueError("child_transfer_owner_binding_mismatch")
        frozen_refs = tuple(ref.model_copy(deep=True) for ref in refs)
        proxy = self._served_proxy
        result = run_guarded_cas_operation(
            proxy,
            lambda: FileSystemCAS._publish_child_release_profiles(
                destination, source, frozen_refs, ledger, token=_CHILD_STAGING_TOKEN
            ),
        )
        source_after, destination_after, refs_after, ledger_after = (
            ChildSelectedTransferCapability._claim_for_runtime(capability, self._session)
        )
        if (
            source_after is not source
            or destination_after is not destination
            or ledger_after is not ledger
            or refs_after != frozen_refs
        ):
            raise ValueError("child_transfer_scope_changed_during_operation")
        return result

    def has_unsettled_operations(self) -> bool:
        """Report timed-out served or stage operations that have not finished."""
        served = _require_runtime_filesystem_guard(self._served_proxy)
        return (
            served.guard.has_unsettled_operations()
            or self._stage_proxy._guard.has_unsettled_operations()
        )

    def has_unsettled_stage_reads(self) -> bool:
        """Report staged calls that outlived their caller's timeout."""
        return self._stage_proxy._guard.has_unsettled_operations()

    def close(self) -> None:
        """Stop stage admission without asserting entered I/O has quiesced."""
        self._stage_proxy.close()


def _bootstrap_child_guarded_read_owner(
    session: object, served_proxy: object
) -> ChildGuardedReadOwner:
    """Appoint the fixed reader once from the trusted runtime bootstrap."""
    from polisyos.core.run.child_custody import (
        _CHILD_GUARDED_READER_BOOTSTRAP_TOKEN,
        ChildComputationCustody,
    )

    service = ChildGuardedReadOwner(session, served_proxy)
    try:
        ChildComputationCustody._appoint_guarded_reader(
            session, service, token=_CHILD_GUARDED_READER_BOOTSTRAP_TOKEN
        )
    except BaseException:
        service.close()
        raise
    return service


def _bootstrap_guarded_child_custody(
    root_run: object,
    *,
    staging_root: Path,
    closure_resolver: object,
    publication_fence: object,
    served_roots: Sequence[Path] = (),
) -> tuple[ChildComputationCustody, ChildGuardedReadOwner]:
    """Build one Core custody and reader from the actual runtime-attested Root."""
    from polisyos.core.run.child_custody import (
        _CHILD_GUARDED_ROOT_BOOTSTRAP_TOKEN,
        ChildComputationCustody,
        _bind_guarded_root,
    )
    from polisyos.core.run.context import RunContext

    if type(root_run) is not RunContext:
        raise TypeError("child_guarded_root_type_invalid")
    served_proxy = root_run.store
    binding = _require_runtime_filesystem_guard(served_proxy)
    root_binding = _bind_guarded_root(
        root_run, binding.backend, token=_CHILD_GUARDED_ROOT_BOOTSTRAP_TOKEN
    )
    session = ChildComputationCustody(
        root_run,
        staging_root=staging_root,
        closure_resolver=closure_resolver,
        publication_fence=publication_fence,
        served_roots=served_roots,
        _guarded_root_binding=root_binding,
    )
    reader = _bootstrap_child_guarded_read_owner(session, served_proxy)
    return session, reader


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
            proxy_revision=proxy._runtime_binding_revision,
            guard_revision=guard._runtime_binding_revision,
            registration_revision=object(),
        )
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
    "run_guarded_cas_member",
    "run_guarded_cas_operation",
    "run_guarded_dependency_operation",
]
