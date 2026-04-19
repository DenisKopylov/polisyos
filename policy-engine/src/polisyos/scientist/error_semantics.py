"""Shared error envelope and degraded-path helpers for Scientist runtime."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, cast

from polisyos.common.logger import get_logger

logger = get_logger(__name__)


class SupportsRecordDegradedPath(Protocol):
    """Metrics surface required by the degraded-path helper."""

    def record_degraded_path(
        self,
        *,
        component: str,
        operation: str,
        reason: str,
        error_type: str,
    ) -> None: ...


class SupportsWarningLog(Protocol):
    """Minimal logger contract for degraded-path reporting."""

    def warning(self, message: object, *args: object, **kwargs: object) -> Any: ...


MetricsProvider = Callable[[], SupportsRecordDegradedPath]


@dataclass(slots=True)
class ErrorEnvelope:
    """Structured description of a failure or degraded path."""

    component: str
    operation: str
    reason: str
    error_type: str
    message: str
    retryable: bool = False
    degraded: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload["details"]:
            payload.pop("details")
        return payload


def _default_metrics() -> SupportsRecordDegradedPath:
    from polisyos.core.observability import get_metrics

    return cast("SupportsRecordDegradedPath", get_metrics())


def build_error_envelope(
    *,
    component: str,
    operation: str,
    reason: str,
    exc: BaseException | None = None,
    message: str | None = None,
    error_type: str | None = None,
    retryable: bool = False,
    degraded: bool = True,
    details: Mapping[str, Any] | None = None,
) -> ErrorEnvelope:
    """Construct a serializable error envelope."""
    envelope_details: dict[str, Any] = {
        str(key): _safe_detail_value(value)
        for key, value in dict(details or {}).items()
    }
    if exc is not None and "exception_type" not in envelope_details:
        envelope_details["exception_type"] = exc.__class__.__name__
    return ErrorEnvelope(
        component=component,
        operation=operation,
        reason=reason,
        error_type=error_type or (exc.__class__.__name__ if exc is not None else "runtime_error"),
        message=message or (str(exc) if exc is not None else reason),
        retryable=bool(retryable),
        degraded=bool(degraded),
        details=envelope_details,
    )


def emit_degraded_path(
    *,
    component: str,
    operation: str,
    reason: str,
    exc: BaseException | None = None,
    message: str | None = None,
    error_type: str | None = None,
    retryable: bool = False,
    details: Mapping[str, Any] | None = None,
    log: SupportsWarningLog | logging.Logger | None = None,
    metrics: SupportsRecordDegradedPath | None = None,
    metrics_provider: MetricsProvider | None = None,
) -> dict[str, Any]:
    """Log and count a degraded-but-recoverable path, returning its envelope."""
    envelope = build_error_envelope(
        component=component,
        operation=operation,
        reason=reason,
        exc=exc,
        message=message,
        error_type=error_type,
        retryable=retryable,
        degraded=True,
        details=details,
    )
    (log or logger).warning(
        f"Degraded path component={component} operation={operation} "
        f"reason={reason} envelope={envelope.to_dict()}"
    )
    _record_degraded_metric(
        envelope,
        metrics=metrics,
        metrics_provider=metrics_provider,
    )
    return envelope.to_dict()


def _record_degraded_metric(
    envelope: ErrorEnvelope,
    *,
    metrics: SupportsRecordDegradedPath | None = None,
    metrics_provider: MetricsProvider | None = None,
) -> None:
    try:
        resolved_metrics = metrics
        if resolved_metrics is None:
            if metrics_provider is not None:
                resolved_metrics = metrics_provider()
            else:
                resolved_metrics = _default_metrics()
        resolved_metrics.record_degraded_path(
            component=envelope.component,
            operation=envelope.operation,
            reason=envelope.reason,
            error_type=envelope.error_type,
        )
    except ModuleNotFoundError:
        return
    except AttributeError:
        return


def _safe_detail_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _safe_detail_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_detail_value(item) for item in value]
    return str(value)


__all__ = [
    "ErrorEnvelope",
    "build_error_envelope",
    "emit_degraded_path",
]
