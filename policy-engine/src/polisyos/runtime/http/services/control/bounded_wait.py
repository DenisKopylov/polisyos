"""Finite Runtime waits for shared-executor work with truthful timeout disposition."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from polisyos.common.async_tools import SharedExecutorWaitTimeoutError

if TYPE_CHECKING:
    from polisyos.core.contracts.bounded_liveness import BoundedLivenessResolution


class _WaitHandle(Protocol):
    """Minimal timeout-capable shared-executor handle used by Runtime."""

    def result(self, timeout: float | None = None) -> object: ...


class ControlProducerExecutionError(RuntimeError):
    """Preserve bounded executor failure identity without publishing raw exception text."""

    def __init__(
        self,
        *,
        resolution: BoundedLivenessResolution,
        exception_type: str,
        code: str,
        retryable: bool,
    ) -> None:
        if (
            not exception_type
            or len(exception_type) > 128
            or any(not (character.isalnum() or character in "._") for character in exception_type)
        ):
            exception_type = "not_established"
        if (
            not code
            or len(code) > 96
            or any(not (character.isalnum() or character in "._-") for character in code)
        ):
            code = "shared_execution_failed"
        if type(retryable) is not bool:
            retryable = False
        super().__init__(f"shared_execution_failed:{resolution.producer_key}:{code}")
        self.resolution = resolution
        self.exception_type = exception_type
        self.code = code
        self.retryable = retryable

    def diagnostic(self) -> dict[str, object]:
        """Return bounded executor identity without an untrusted message excerpt."""
        return {
            "code": self.code,
            "producer_key": self.resolution.producer_key,
            "exception_type": self.exception_type,
            "retryable": self.retryable,
            "config_id": self.resolution.config_id,
            "config_version": self.resolution.config_version,
        }


def wrap_shared_execution_exception(
    error: Exception,
    resolution: BoundedLivenessResolution,
) -> ControlProducerExecutionError:
    """Convert a submission exception into a bounded, privacy-safe Runtime failure."""
    error_code = getattr(error, "code", "shared_executor_submit_failed")
    retryable = getattr(error, "retryable", False)
    return ControlProducerExecutionError(
        resolution=resolution,
        exception_type=type(error).__name__,
        code=error_code if isinstance(error_code, str) else "shared_executor_submit_failed",
        retryable=retryable if type(retryable) is bool else False,
    )


def require_shared_execution_value(
    completion: object,
    resolution: BoundedLivenessResolution,
) -> object:
    """Require a successful fixed-work completion, retaining typed failure identity."""
    status = getattr(completion, "status", None)
    value = getattr(completion, "value", None)
    if status == "completed" and value is not None:
        return value
    failure = getattr(completion, "failure", None)
    exception_type = getattr(failure, "exception_type", "not_established")
    code = getattr(failure, "code", "shared_execution_failed")
    if (
        resolution.producer_key == "runtime.observational_method_execution"
        and exception_type == "polisyos.foundry.data_plane.bindings.HTEInputPreparationRefusal"
    ):
        code = "observational_input_refused"
    retryable = getattr(failure, "retryable", False)
    raise ControlProducerExecutionError(
        resolution=resolution,
        exception_type=exception_type if isinstance(exception_type, str) else "not_established",
        code=code if isinstance(code, str) else "shared_execution_failed",
        retryable=retryable if type(retryable) is bool else False,
    ) from None


class ControlProducerWaitTimeoutError(RuntimeError):
    """A bounded caller wait expired without claiming running work stopped."""

    def __init__(
        self,
        *,
        resolution: BoundedLivenessResolution,
        cancelled_before_start: bool,
        running_slot_retained: bool,
    ) -> None:
        if type(cancelled_before_start) is not bool or type(running_slot_retained) is not bool:
            raise TypeError("control_producer_wait_disposition_must_be_boolean")
        if running_slot_retained is cancelled_before_start:
            raise ValueError("control_producer_wait_disposition_incoherent")
        super().__init__(f"bounded_producer_wait_deadline_exceeded:{resolution.producer_key}")
        self.resolution = resolution
        self.cancelled_before_start = cancelled_before_start
        self.running_slot_retained = running_slot_retained

    @property
    def retryable(self) -> bool:
        """Only queued work cancelled before start can be retried safely."""
        return self.cancelled_before_start and self.resolution.retry_ceiling > 0

    def diagnostic(self) -> dict[str, object]:
        """Return bounded policy and wait disposition suitable for progress/audit."""
        return {
            "code": "bounded_producer_wait_deadline_exceeded",
            "producer_key": self.resolution.producer_key,
            "deadline_s": self.resolution.deadline_s,
            "retry_ceiling": self.resolution.retry_ceiling,
            "config_id": self.resolution.config_id,
            "config_version": self.resolution.config_version,
            "owner": self.resolution.owner,
            "feature_flag": self.resolution.feature_flag,
            "wait_disposition": (
                "cancelled_before_start" if self.cancelled_before_start else "running_slot_retained"
            ),
            "retryable": self.retryable,
        }


def wait_for_shared_execution(
    handle: _WaitHandle,
    resolution: BoundedLivenessResolution,
) -> object:
    """Wait at most the owner-resolved deadline and preserve queue/run distinction."""
    try:
        return handle.result(timeout=resolution.deadline_s)
    except SharedExecutorWaitTimeoutError as exc:
        cancelled = exc.cancelled_before_start
        running = exc.running_slot_retained
        if type(cancelled) is not bool or type(running) is not bool or running == cancelled:
            raise RuntimeError("shared_executor_wait_timeout_disposition_invalid") from None
        raise ControlProducerWaitTimeoutError(
            resolution=resolution,
            cancelled_before_start=cancelled,
            running_slot_retained=running,
        ) from None
