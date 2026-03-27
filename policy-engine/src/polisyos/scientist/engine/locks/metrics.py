"""OTel metrics for lock contention monitoring.

Instruments
-----------
* ``scientist_lock_acquire_duration_seconds`` — histogram (labels: backend, success)
* ``scientist_lock_contention_total`` — counter (labels: backend)
* ``scientist_lock_heartbeat_failures_total`` — counter (labels: backend)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

_logger = logging.getLogger(__name__)

try:
    from opentelemetry import metrics

    _meter = metrics.get_meter("polisyos.scientist.locks")
    _acquire_duration = _meter.create_histogram(
        name="scientist_lock_acquire_duration_seconds",
        description="Time to acquire a run lock",
        unit="s",
    )
    _contention_total = _meter.create_counter(
        name="scientist_lock_contention_total",
        description="Number of lock contention events (failed acquires)",
    )
    _heartbeat_failures = _meter.create_counter(
        name="scientist_lock_heartbeat_failures_total",
        description="Number of lock heartbeat extension failures",
    )
    _HAS_OTEL = True
except Exception:  # noqa: BLE001
    _HAS_OTEL = False


class LockMetrics:
    """Thin helper for recording lock-related OTel metrics.

    Injected into lock backends; no-ops if OTel is unavailable.
    """

    def __init__(self, backend: str) -> None:
        self._backend = backend

    def record_acquire(self, duration_s: float, success: bool) -> None:
        if _HAS_OTEL:
            _acquire_duration.record(
                duration_s,
                attributes={"backend": self._backend, "success": str(success)},
            )

    def record_contention(self) -> None:
        if _HAS_OTEL:
            _contention_total.add(1, attributes={"backend": self._backend})

    def record_heartbeat_failure(self) -> None:
        if _HAS_OTEL:
            _heartbeat_failures.add(1, attributes={"backend": self._backend})

    @contextmanager
    def measure_acquire(self) -> Generator[None, None, None]:
        """Context manager that records acquire duration and contention."""
        t0 = time.monotonic()
        success = False
        try:
            yield
            success = True
        except Exception:
            self.record_contention()
            raise
        finally:
            self.record_acquire(time.monotonic() - t0, success)
