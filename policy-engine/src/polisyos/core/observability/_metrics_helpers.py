"""
Metric helper classes: context-manager timer and observable gauge proxy.

These are used by MetricsRegistry and its mixins to record durations
and expose observable gauge values.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

from opentelemetry import metrics
from opentelemetry.metrics import Observation

__all__ = [
    "HistogramTimer",
    "GaugeProxy",
]


class HistogramTimer:
    """
    Context manager for timing operations with histograms.

    Provides both context manager and decorator interfaces.
    """

    def __init__(
        self,
        histogram: Optional[metrics.Histogram],
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        self._histogram = histogram
        self._attributes = attributes or {}
        self._start_time: Optional[float] = None

    def __enter__(self) -> "HistogramTimer":
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._histogram is None:
            return
        if self._start_time is not None:
            duration = time.perf_counter() - self._start_time
            attrs = dict(self._attributes)
            if exc_type is not None:
                attrs["error"] = "true"
            self._histogram.record(duration, attrs)


class GaugeProxy:
    """
    Simple observable gauge wrapper with a set() API.

    Stores the latest value per attribute set and exposes them
    via an observable gauge callback.
    """

    def __init__(
        self,
        meter: metrics.Meter,
        *,
        name: str,
        description: str,
        unit: str,
    ) -> None:
        self._lock = threading.Lock()
        self._values: dict[tuple[tuple[str, Any], ...], float] = {}

        def _callback(_options: Any) -> list[Observation]:
            with self._lock:
                items = list(self._values.items())
            return [Observation(value, dict(attrs)) for attrs, value in items]

        self._gauge = meter.create_observable_gauge(
            name=name,
            callbacks=[_callback],
            description=description,
            unit=unit,
        )

    def set(self, value: float, attributes: Optional[dict[str, Any]] = None) -> None:
        attrs = attributes or {}
        key = tuple(sorted(attrs.items()))
        with self._lock:
            self._values[key] = float(value)
