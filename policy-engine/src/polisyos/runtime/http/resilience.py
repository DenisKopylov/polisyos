"""Dependency guards for runtime slow/unavailable CAS, OPA, and control-store paths."""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
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
from weakref import WeakKeyDictionary, WeakSet, ref

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from polisyos.common.borrowed_execution import _BorrowedControlLiveness
    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactMemberReceipt,
        ArtifactRef,
        ArtifactStore,
        ArtifactStoreReadUsage,
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
    from polisyos.core.artifacts.child_release import (
        ChildJobReleaseClaim,
        ChildJobReleaseLocator,
        ChildJobScopeClaim,
        ChildJobSessionClaim,
    )
    from polisyos.core.artifacts.store import ImportPublication
    from polisyos.core.run.child_custody import (
        ChildComputationBinding,
        ChildComputationCustody,
        _ChildGuardedReadService,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
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
class _RuntimeGuardBinding:
    backend: object
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
    guard_lifecycle_revision: object
    registration_revision: object


@dataclass(frozen=True, slots=True)
class _RuntimeFilesystemGuardBinding(_RuntimeGuardBinding):
    backend: FileSystemCAS
    child_service: _RuntimeChildCasService | None = None


@dataclass(frozen=True, slots=True)
class _RuntimeControlStoreGuardBinding(_RuntimeGuardBinding):
    backend: ControlPlaneStore
    child_verifier: _RuntimeChildJobVerifier | None = None


# Capture the actual Runtime implementation, not an instance-supplied runner.
_RUNTIME_CAS_GUARD_FACTORY = build_runtime_cas_guard
_RUNTIME_CAS_GUARD_FACTORY_CODE = build_runtime_cas_guard.__code__
_RUNTIME_CONTROL_GUARD_FACTORY = build_runtime_control_store_guard
_RUNTIME_CONTROL_GUARD_FACTORY_CODE = build_runtime_control_store_guard.__code__
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


class _RuntimeGuardRegistry[B: _RuntimeGuardBinding](MutableMapping[GuardedDependencyProxy, B]):
    """Keep each registration's identity invalid after removal or replacement."""

    def __init__(self) -> None:
        self._entries: WeakKeyDictionary[GuardedDependencyProxy, B] = WeakKeyDictionary()
        self._revisions: WeakKeyDictionary[GuardedDependencyProxy, object] = WeakKeyDictionary()

    def __getitem__(self, key: GuardedDependencyProxy) -> B:
        with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            return self._entries[key]

    def __setitem__(self, key: GuardedDependencyProxy, value: B) -> None:
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

    def is_current(self, key: GuardedDependencyProxy, binding: B) -> bool:
        with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
            return self._revisions.get(key) is binding.registration_revision


_RUNTIME_FILESYSTEM_GUARDS = _RuntimeGuardRegistry[_RuntimeFilesystemGuardBinding]()
_RUNTIME_CONTROL_STORE_GUARDS = _RuntimeGuardRegistry[_RuntimeControlStoreGuardBinding]()
_RUNTIME_CHILD_VERIFIER_TOKEN = object()
_RUNTIME_CHILD_CAS_SERVICE_TOKEN = object()


class _RuntimeChildCasService:
    """Fixed child service issued with one actual Runtime CAS registration."""

    __slots__ = ("__proxy_ref", "__registration_revision")

    def __init__(
        self,
        proxy: GuardedDependencyProxy,
        binding: _RuntimeFilesystemGuardBinding,
        *,
        token: object,
    ) -> None:
        if token is not _RUNTIME_CHILD_CAS_SERVICE_TOKEN:
            raise ValueError("runtime_child_cas_registration_required")
        self.__proxy_ref = ref(proxy)
        self.__registration_revision = binding.registration_revision

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("runtime child CAS service binding is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("runtime child CAS service binding is immutable")

    def _current(self) -> tuple[GuardedDependencyProxy, _RuntimeFilesystemGuardBinding]:
        proxy = self.__proxy_ref()
        if type(proxy) is not GuardedDependencyProxy:
            raise ValueError("runtime_child_cas_registration_lost")
        binding = _require_runtime_filesystem_guard(proxy)
        if (
            binding.registration_revision is not self.__registration_revision
            or binding.child_service is not self
        ):
            raise ValueError("runtime_child_cas_registration_changed")
        return proxy, binding

    def _backend_for_store(self, guarded_store: object) -> FileSystemCAS:
        """Resolve the actual backend only for the exact registered proxy."""
        proxy, binding = self._current()
        if guarded_store is not proxy:
            raise ValueError("runtime_child_cas_proxy_not_established")
        self._current()
        return binding.backend

    @contextmanager
    def _appointment_registration(self) -> Iterator[None]:
        """Order a short Core appointment against this exact guard transition."""
        proxy, binding = self._current()
        with proxy._runtime_lock, binding.guard._runtime_lock:
            current_proxy, current_binding = self._current()
            if current_proxy is not proxy or current_binding is not binding:
                raise ValueError("runtime_child_cas_registration_changed")
            yield

    def _reader_for_session(self, session: object) -> ChildGuardedReadOwner:
        """Create the fixed guarded reader for its actual Core custody session."""
        from polisyos.core.run.child_custody import ChildComputationCustody

        proxy, binding = self._current()
        if (
            type(session) is not ChildComputationCustody
            or session._root.store is not proxy
            or session._served is not binding.backend
        ):
            raise ValueError("runtime_child_cas_session_not_established")
        reader = ChildGuardedReadOwner(session, proxy)
        try:
            self._current()
        except BaseException:
            reader.close()
            raise
        return reader


def _require_runtime_child_cas_service(guarded_store: object) -> _RuntimeChildCasService:
    """Resolve only the child service issued with the actual CAS registration."""
    binding = _require_runtime_filesystem_guard(guarded_store)
    service = binding.child_service
    if type(service) is not _RuntimeChildCasService or service._current()[0] is not guarded_store:
        raise ValueError("runtime_child_cas_registration_not_established")
    return service


class _RuntimeChildJobVerifier:
    """One fixed verifier issued with the actual Runtime control registration."""

    __slots__ = ("__proxy_ref", "__registration_revision")

    def __init__(
        self,
        proxy: GuardedDependencyProxy,
        binding: _RuntimeControlStoreGuardBinding,
        *,
        token: object,
    ) -> None:
        if token is not _RUNTIME_CHILD_VERIFIER_TOKEN:
            raise ValueError("runtime_child_verifier_registration_required")
        self.__proxy_ref = ref(proxy)
        self.__registration_revision = binding.registration_revision

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("runtime child verifier binding is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("runtime child verifier binding is immutable")

    def _current_proxy(self) -> GuardedDependencyProxy:
        proxy = self.__proxy_ref()
        if type(proxy) is not GuardedDependencyProxy:
            raise ValueError("runtime_child_verifier_registration_lost")
        binding = _require_runtime_control_store_guard(proxy)
        if (
            binding.registration_revision is not self.__registration_revision
            or binding.child_verifier is not self
        ):
            raise ValueError("runtime_child_verifier_registration_changed")
        return proxy

    def verify_intent(self, locator: ChildJobReleaseLocator, claim: ChildJobSessionClaim) -> None:
        """Verify the exact committed session through the registered control guard."""
        proxy = self._current_proxy()
        result = proxy.verify_intent(locator, claim)
        self._current_proxy()
        if result is not None:
            raise ValueError("runtime_child_verifier_result_invalid")

    def verify_scope(self, locator: ChildJobReleaseLocator, claim: ChildJobScopeClaim) -> None:
        """Verify the exact committed scope through the registered control guard."""
        proxy = self._current_proxy()
        result = proxy.verify_scope(locator, claim)
        self._current_proxy()
        if result is not None:
            raise ValueError("runtime_child_verifier_result_invalid")

    def verify_release(self, locator: ChildJobReleaseLocator, claim: ChildJobReleaseClaim) -> None:
        """Verify the exact release authorization through the registered control guard."""
        proxy = self._current_proxy()
        result = proxy.verify_release(locator, claim)
        self._current_proxy()
        if result is not None:
            raise ValueError("runtime_child_verifier_result_invalid")


def _require_runtime_child_job_verifier(guarded_control: object) -> _RuntimeChildJobVerifier:
    """Resolve only the service created by this control-guard registration."""
    binding = _require_runtime_control_store_guard(guarded_control)
    if type(guarded_control) is not GuardedDependencyProxy:
        raise ValueError("registered_control_guard_binding_not_established")
    verifier = binding.child_verifier
    if (
        type(verifier) is not _RuntimeChildJobVerifier
        or verifier._current_proxy() is not guarded_control
    ):
        raise ValueError("runtime_child_verifier_registration_not_established")
    return verifier


def _guard_binding_changed(
    guarded_store: GuardedDependencyProxy, binding: _RuntimeGuardBinding
) -> bool:
    """Compare every dependency that the actual registered guard will use."""
    return (
        type(binding.guard) is not BlockingDependencyGuard
        or guarded_store._runtime_binding_revision is not binding.proxy_revision
        or binding.guard._runtime_binding_revision is not binding.guard_revision
        or binding.guard._runtime_lifecycle_revision is not binding.guard_lifecycle_revision
        or binding.guard._closed
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
    )


def _capture_guard_binding[B: _RuntimeGuardBinding](
    binding_type: type[B],
    *,
    backend: object,
    proxy: GuardedDependencyProxy,
    guard: BlockingDependencyGuard,
) -> B:
    """Snapshot the exact factory-produced proxy and its actual dependencies."""
    return binding_type(
        backend=backend,
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
        guard_lifecycle_revision=guard._runtime_lifecycle_revision,
        registration_revision=object(),
    )


def _require_runtime_guard_open(binding: _RuntimeGuardBinding) -> None:
    """Preserve the existing unavailable error for a currently closed guard."""
    if binding.guard._closed:
        name = binding.snapshot.dependency_name
        raise RuntimeDependencyUnavailableError(name, detail=f"{name} dependency guard is closed")


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
    _require_runtime_guard_open(binding)
    if (
        type(binding.backend) is not FileSystemCAS
        or not registration_current
        or _guard_binding_changed(guarded_store, binding)
    ):
        raise ValueError("registered_sql_guard_binding_changed")
    return binding


def _require_runtime_control_store_guard(
    guarded_store: object,
) -> _RuntimeControlStoreGuardBinding:
    """Reconcile the actual registered control-store proxy and executor."""
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    if type(guarded_store) is not GuardedDependencyProxy:
        raise ValueError("registered_control_guard_binding_not_established")
    with _RUNTIME_FILESYSTEM_GUARDS_LOCK:
        binding = _RUNTIME_CONTROL_STORE_GUARDS.get(guarded_store)
        registration_current = binding is not None and _RUNTIME_CONTROL_STORE_GUARDS.is_current(
            guarded_store, binding
        )
    if binding is None:
        raise ValueError("registered_control_guard_binding_not_established")
    _require_runtime_guard_open(binding)
    if (
        type(binding.backend) is not ControlPlaneStore
        or not registration_current
        or _guard_binding_changed(guarded_store, binding)
    ):
        raise ValueError("registered_control_guard_binding_changed")
    return binding


class _RuntimeGuardedChildFence:
    """Bind a child owner to the actual guarded control job and parent worker."""

    __slots__ = (
        "_admission",
        "_binding",
        "_budget",
        "_cas_proxy",
        "_cas_registration",
        "_control_proxy",
        "_control_registration",
        "_grant",
        "_root",
        "_thread_id",
        "cell_id",
        "control_job_id",
        "root_run_id",
        "tenant_id",
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, name):
            raise AttributeError("guarded child control binding is immutable")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("guarded child control binding is immutable")

    def __init__(
        self,
        root: object,
        guarded_control: object,
        grant: _BorrowedExecutionGrant,
        binding: object,
    ) -> None:
        from polisyos.core.run.child_custody import ChildComputationBinding
        from polisyos.core.run.context import RunContext
        from polisyos.runtime.http.services.control.child_execution_budget import (
            _require_attempt_budget,
        )
        from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionAdmission

        if (
            type(root) is not RunContext
            or type(guarded_control) is not GuardedDependencyProxy
            or type(grant) is not _BorrowedExecutionGrant
            or type(binding) is not ChildComputationBinding
            or binding.control_job_id is None
        ):
            raise ValueError("guarded_child_control_parent_not_established")
        control = _require_runtime_control_store_guard(guarded_control)
        cas = _require_runtime_filesystem_guard(root.store)
        root._require_active_lease_owner()
        root._validate_run_owner_binding()
        fields = {
            "run_id": binding.root_run_id,
            "job_id": binding.control_job_id,
            "attempt_id": binding.parent_attempt_id,
            "basis_ref": _child_parent_basis_json(binding.parent_basis_ref),
        }
        grant.require_parent(**fields)
        admission = guarded_control.current_execution_job_admission()
        if type(admission) is not ControlJobExecutionAdmission:
            raise ValueError("guarded_child_control_admission_not_established")
        budget = _require_attempt_budget(
            binding.control_job_id, binding.root_run_id, admission.attempt
        )
        if (
            budget.control_store is not guarded_control
            or grant._attempt.transition_lock is not budget.transition_lock
            or grant._attempt.budget_uncertain is not budget.uncertain
            or grant._attempt.lease_lost is not budget.interrupt.lost
            or guarded_control.read_child_attempt_budget(binding.control_job_id, admission.attempt)
            != budget.claim
        ):
            raise ValueError("guarded_child_control_budget_owner_mismatch")
        self._root = root
        self._control_proxy = guarded_control
        self._control_registration = control
        self._cas_proxy = root.store
        self._cas_registration = cas
        self._grant = grant
        self._binding = binding.model_copy(deep=True)
        self._admission = admission
        self._budget = budget
        self._thread_id = threading.get_ident()
        self.root_run_id = binding.root_run_id
        self.control_job_id = binding.control_job_id
        self.tenant_id = binding.tenant_id
        self.cell_id = binding.cell_id
        self.check_active()

    def _require_parent(self) -> None:
        from polisyos.runtime.http.services.control.child_execution_budget import (
            _require_attempt_budget,
        )

        if threading.get_ident() != self._thread_id:
            raise ValueError("guarded_child_control_parent_thread_mismatch")
        if (
            self._root.store is not self._cas_proxy
            or self._root._active_lease is None
            or self._root._closed
            or self._root._suspended
            or _require_runtime_filesystem_guard(self._cas_proxy) is not self._cas_registration
            or _require_runtime_control_store_guard(self._control_proxy)
            is not self._control_registration
            or _require_attempt_budget(
                self.control_job_id, self.root_run_id, self._admission.attempt
            )
            is not self._budget
        ):
            raise ValueError("guarded_child_control_owner_changed")
        self._root._require_active_lease_owner()
        self._grant.require_parent(
            run_id=self.root_run_id,
            job_id=self.control_job_id,
            attempt_id=self._binding.parent_attempt_id,
            basis_ref=_child_parent_basis_json(self._binding.parent_basis_ref),
        )

    def check_active(self) -> None:
        """Recheck the live job through its guard and the original parent worker."""
        self._require_parent()
        current = self._control_proxy.current_execution_job_admission()
        self._check_admission(current)
        self._require_parent()

    def _parent_binding_for_core(self, root: object) -> ChildComputationBinding:
        """Return this actual registered parent's binding to its Core owner."""
        from polisyos.core.run.child_custody import ChildComputationBinding

        if root is not self._root:
            raise ValueError("guarded_child_control_parent_changed")
        self.check_active()
        binding = self._binding.model_copy(deep=True)
        if type(binding) is not ChildComputationBinding:
            raise ValueError("guarded_child_control_binding_changed")
        return binding

    def _job_verifier_for_core(self) -> _RuntimeChildJobVerifier:
        """Resolve the fixed job verifier issued with this control registration."""
        self._require_parent()
        verifier = _require_runtime_child_job_verifier(self._control_proxy)
        self._require_parent()
        return verifier

    def _cas_service_for_core(self) -> _RuntimeChildCasService:
        """Resolve the fixed service issued for this parent's actual guarded CAS."""
        self._require_parent()
        service = _require_runtime_child_cas_service(self._cas_proxy)
        self._require_parent()
        return service

    @contextmanager
    def local_consumption(self) -> Iterator[None]:
        """Order a short Core consumption against revocation and guard changes.

        The caller holds the Root/custody locks first. Job reads and copying
        finish before this guard; the original parent grant stays thread-affine.
        """
        with (
            self._control_proxy._runtime_lock,
            self._control_registration.guard._runtime_lock,
            self._grant.publication(),
        ):
            self._require_parent()
            yield

    def _check_admission(self, current: object) -> None:
        from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionAdmission

        expected = self._admission
        if (
            type(current) is not ControlJobExecutionAdmission
            or current.job.job_id != expected.job.job_id
            or current.job.run_id != expected.job.run_id
            or current.job.lease_owner != expected.job.lease_owner
            or current.attempt != expected.attempt
            or current.scope != expected.scope
            or current.job.effective_execution_profile != expected.job.effective_execution_profile
            or current.admission_capability_manifest_ref
            != expected.admission_capability_manifest_ref
            or (
                current.job.run_id,
                current.job.job_id,
                current.scope.tenant_id,
                current.scope.cell_id,
            )
            != (self.root_run_id, self.control_job_id, self.tenant_id, self.cell_id)
        ):
            raise ValueError("guarded_child_control_admission_changed")

    def _check_control_admission(self, current: object) -> None:
        self._require_control_worker()
        self._check_admission(current)

    def _control_liveness_for_core(self, owner: object) -> _BorrowedControlLiveness:
        """Project current parent liveness for a Core-owned one-use decision."""
        from polisyos.core.run.child_custody import ChildComputationCustody

        self._require_parent()
        control_identity: object = self
        if type(owner) is not ChildComputationCustody or (
            owner._root is not self._root or owner._fence is not control_identity
        ):
            raise ValueError("guarded_child_control_session_mismatch")
        return self._grant._control_liveness(
            run_id=self.root_run_id,
            job_id=self.control_job_id,
            attempt_id=self._binding.parent_attempt_id,
            basis_ref=_child_parent_basis_json(self._binding.parent_basis_ref),
        )

    def _require_control_worker(self) -> None:
        """Check the exact live registered guard execution, without parent authority."""
        if (
            threading.get_ident() == self._thread_id
            or _require_runtime_control_store_guard(self._control_proxy)
            is not self._control_registration
        ):
            raise ValueError("guarded_child_control_worker_not_established")
        current = getattr(self._control_registration.guard._execution, "attempt", None)
        if type(current) is not _BlockingAttempt:
            raise ValueError("guarded_child_control_worker_not_established")
        with current.transition_lock:
            if current.revoked or time.monotonic() >= current.deadline:
                raise ValueError("guarded_child_control_worker_not_established")

    def begin_session(self, intent: object) -> object:
        """Commit one Core-owned session decision through the actual guard."""
        from polisyos.core.artifacts.child_release import ChildJobReleaseLocator
        from polisyos.core.run.child_custody import (
            ChildComputationOutcomeUnknown,
            ChildJobSessionIntent,
            ChildSessionAdmissionUnknown,
        )

        self._require_parent()
        if type(intent) is not ChildJobSessionIntent:
            raise ValueError("guarded_child_session_intent_invalid")
        operation = intent._issue_guarded_operation(self)
        recovery = operation._recovery()
        attempted = threading.Event()
        committed = threading.Event()
        try:
            locator = self._control_proxy._record_child_job_event(
                None,
                None,
                None,
                kind="session",
                control_operation=operation,
                on_transaction_attempt=attempted.set,
                on_transaction_committed=committed.set,
            )
            self._require_parent()
            if type(locator) is not ChildJobReleaseLocator:
                raise ValueError("guarded_child_session_locator_invalid")
            return locator
        except BaseException as exc:
            if isinstance(exc, ChildComputationOutcomeUnknown):
                raise
            if (
                isinstance(exc, RuntimeDependencyTimeoutError | RuntimeDependencyUnavailableError)
                or committed.is_set()
                or (attempted.is_set() and isinstance(exc, OSError | sqlite3.Error))
            ):
                raise ChildSessionAdmissionUnknown(recovery) from exc
            raise

    def authorize_release(self, candidate: object) -> object:
        """Commit one Core-owned release decision through the actual guard."""
        from polisyos.core.artifacts.child_release import ChildJobReleaseLocator
        from polisyos.core.run.child_custody import ChildJobReleaseCandidate

        self._require_parent()
        if type(candidate) is not ChildJobReleaseCandidate:
            raise ValueError("guarded_child_release_candidate_invalid")
        operation = candidate._issue_guarded_operation(self)
        locator = self._control_proxy._record_child_job_event(
            None, None, None, kind="authorization", control_operation=operation
        )
        self._require_parent()
        if type(locator) is not ChildJobReleaseLocator:
            raise ValueError("guarded_child_release_locator_invalid")
        return locator

    def publish_head(self, candidate: object, locator: object, claim: object) -> None:
        """Dispatch one Core-owned head decision to the actual guarded job owner."""
        from polisyos.core.artifacts.child_release import (
            ChildJobReleaseClaim,
            ChildJobReleaseLocator,
        )
        from polisyos.core.run.child_custody import ChildJobReleaseCandidate

        self._require_parent()
        if (
            type(candidate) is not ChildJobReleaseCandidate
            or type(locator) is not ChildJobReleaseLocator
            or type(claim) is not ChildJobReleaseClaim
        ):
            raise ValueError("guarded_child_publication_invalid")
        operation = candidate._prepare_guarded_publication(self, locator, claim)
        result = self._control_proxy._publish_child_release_head(control_operation=operation)
        self._require_parent()
        if result is not None:
            raise ValueError("guarded_child_publication_result_invalid")

    def admit_prepared_scope(self, prepared: object) -> object:
        """Commit and reconcile one Core-owned child-scope decision."""
        from polisyos.core.artifacts.child_release import ChildJobReleaseLocator, ChildJobScopeClaim
        from polisyos.core.run.child_custody import (
            ChildComputationOutcomeUnknown,
            ChildPreparedScope,
            ChildScopeAdmissionUnknown,
        )

        self._require_parent()
        if type(prepared) is not ChildPreparedScope:
            raise ValueError("guarded_child_scope_invalid")
        operation = prepared._issue_guarded_operation(self)
        recovery, claim_json = operation._scope_recovery()
        locator: ChildJobReleaseLocator | None = None
        try:
            result = self._control_proxy._record_child_scope(control_operation=operation)
            if (
                type(result) is not tuple
                or len(result) != 2
                or type(result[0]) is not ChildJobReleaseLocator
                or type(result[1]) is not ChildJobScopeClaim
                or result[1] != ChildJobScopeClaim.model_validate_json(claim_json)
            ):
                raise ValueError("guarded_child_scope_locator_invalid")
            locator = result[0]
            self._require_parent()
            return prepared.complete(locator)
        except BaseException as exc:
            if isinstance(exc, ChildComputationOutcomeUnknown):
                raise
            if (
                isinstance(exc, RuntimeDependencyTimeoutError | RuntimeDependencyUnavailableError)
                or locator is not None
            ):
                raise ChildScopeAdmissionUnknown(
                    recovery, scope_claim_json=claim_json, scope_locator=locator
                ) from exc
            raise

    def admit_producer(self, scope: object) -> None:
        """Admit one producer through Core and the exact registered job guard."""
        from polisyos.core.run.child_custody import ChildStagingScope, _ManagedStore

        self._require_parent()
        if type(scope) is not ChildStagingScope or type(scope.store) is not _ManagedStore:
            raise ValueError("guarded_child_producer_scope_invalid")
        operation = scope.store._issue_guarded_producer_operation(scope, self)
        result = self._control_proxy._admit_child_producer(control_operation=operation)
        self._require_parent()
        if result is not None:
            raise ValueError("guarded_child_producer_result_invalid")


def _child_parent_basis_json(ref: object) -> str:
    from polisyos.core.artifacts import ArtifactRef

    if type(ref) is not ArtifactRef or not ref.manifest_profile_sha256:
        raise ValueError("guarded_child_parent_basis_invalid")
    return json.dumps(
        ref.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def _bootstrap_guarded_child_control_fence(
    root: object,
    guarded_control: object,
    grant: _BorrowedExecutionGrant,
    binding: object,
) -> _RuntimeGuardedChildFence:
    """Bind the actual Runtime control guard to the current parent attempt."""
    return _RuntimeGuardedChildFence(root, guarded_control, grant, binding)


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
        if type(served_proxy) is not GuardedDependencyProxy:
            raise ValueError("registered_sql_guard_binding_not_established")
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
        self._check_registrations()

    def require_control_registration(self, control: object) -> None:
        """Recheck registrations for a Core-owned operation on its control worker."""
        if type(control) is not _RuntimeGuardedChildFence:
            raise ValueError("guarded_child_control_worker_not_established")
        control._require_control_worker()
        self._check_registrations()

    def _check_registrations(self) -> None:
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

    @contextmanager
    def control_publication_registration(self, control: object) -> Iterator[None]:
        """Fence exact CAS registrations for the registered control worker."""
        if type(control) is not _RuntimeGuardedChildFence:
            raise ValueError("guarded_child_control_worker_not_established")
        with ExitStack() as stack:
            for lock in (
                control._control_proxy._runtime_lock,
                control._control_registration.guard._runtime_lock,
                self._served_proxy._runtime_lock,
                self._served_registration.guard._runtime_lock,
                self._stage_proxy._runtime_lock,
                self._stage_registration.guard._runtime_lock,
            ):
                stack.enter_context(lock)
            self.require_control_registration(control)
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

    def read_blob_bounded(
        self,
        capability: object,
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> tuple[bytes, ArtifactMemberReceipt, ArtifactStoreReadUsage]:
        """Consume one bounded member wholly inside the appointed CAS worker.

        Core supplies the digest of its sealed selected-manifest read and
        independently reconciles the returned bytes and actual owner receipts.
        The live stream never crosses the guard or escapes its bounded lease.
        """
        proxy, ref = self._claim(capability)

        def read() -> tuple[bytes, ArtifactMemberReceipt, ArtifactStoreReadUsage]:
            attempt = proxy.open_member_bounded(
                ref,
                "blob",
                max_manifest_bytes=max_manifest_bytes,
                expected_manifest_sha256=expected_manifest_sha256,
                max_member_bytes=max_member_bytes,
            )
            with attempt as stream:
                chunks = []
                while chunk := stream.read(65536):
                    chunks.append(chunk)
            return b"".join(chunks), stream.receipt, attempt.usage

        result = self._run_read(proxy, read)
        self._confirm(capability, proxy, ref)
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
        self,
        capability: object,
        *,
        limits: CoreJsonReadLimits,
        manifest_read: CoreJsonManifestBoundedRead | None = None,
    ) -> CoreJsonArtifactBoundedRead:
        """Run the entire canonical bounded reader and preserve its actual usage."""
        from polisyos.core.artifacts import read_core_json_artifact_bounded

        proxy, ref = self._claim(capability)
        result = self._run_read(
            proxy,
            lambda: read_core_json_artifact_bounded(
                proxy, ref, limits=limits, manifest_read=manifest_read
            ),
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


def _bootstrap_guarded_child_custody(
    root_run: object,
    *,
    staging_root: Path,
    closure_resolver: object,
    publication_fence: object,
    served_roots: Sequence[Path] = (),
) -> tuple[ChildComputationCustody, _ChildGuardedReadService]:
    """Connect the real Runtime parent to Core's one-shot appointment port."""
    from polisyos.core.run.worker_lifecycle import ChildRuntimeCapability

    return ChildRuntimeCapability._bootstrap_runtime_session(
        root_run,
        staging_root=staging_root,
        closure_resolver=closure_resolver,
        runtime_control=publication_fence,
        served_roots=served_roots,
    )


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
        binding = _capture_guard_binding(
            _RuntimeFilesystemGuardBinding, backend=target, proxy=proxy, guard=guard
        )
        child_service = _RuntimeChildCasService(
            proxy, binding, token=_RUNTIME_CHILD_CAS_SERVICE_TOKEN
        )
        _RUNTIME_FILESYSTEM_GUARDS[proxy] = replace(binding, child_service=child_service)
    return proxy


def guard_runtime_control_store(target: Any) -> GuardedDependencyProxy:
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    if build_runtime_control_store_guard is _RUNTIME_CONTROL_GUARD_FACTORY:
        factory = FunctionType(_RUNTIME_CONTROL_GUARD_FACTORY_CODE, globals())
        guard = factory()
    else:
        guard = build_runtime_control_store_guard()
    proxy = GuardedDependencyProxy(target=target, guard=guard)
    if (
        type(target) is ControlPlaneStore
        and build_runtime_control_store_guard is _RUNTIME_CONTROL_GUARD_FACTORY
        and type(guard) is BlockingDependencyGuard
        and type(guard._breaker) is CircuitBreaker
    ):
        binding = _capture_guard_binding(
            _RuntimeControlStoreGuardBinding, backend=target, proxy=proxy, guard=guard
        )
        verifier = _RuntimeChildJobVerifier(proxy, binding, token=_RUNTIME_CHILD_VERIFIER_TOKEN)
        _RUNTIME_CONTROL_STORE_GUARDS[proxy] = replace(binding, child_verifier=verifier)
    return proxy


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
