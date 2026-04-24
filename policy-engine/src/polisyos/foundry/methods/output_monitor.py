"""
Method Output Monitor — anomaly detection on pure_step results.

``MethodOutputMonitor`` provides two tiers of output validation:

1. **Basic** (always-on, near-zero cost): checks for NaN/Inf values and
   validates that output dict keys match the declared output slot names.
   Runs on every dispatch call.

2. **Statistical** (opt-in): z-score-based distribution shift detection
   against a rolling history of previous results. Useful for production
   monitoring where silent numeric drift indicates a data quality problem.

``AnomalyFlag`` records each detected anomaly with a severity level so
callers can decide whether to raise, warn, or emit a metric.

Usage
-----
::

    from polisyos.foundry.methods.output_monitor import MethodOutputMonitor

    monitor = MethodOutputMonitor()
    flags = monitor.check_basic(result, expected_keys={"coefficients", "se"})
    for f in flags:
        if f.severity == "error":
            raise RuntimeError(f.reason)

OpenTelemetry integration
-------------------------
When OTel is active the monitor emits a counter
``foundry.method.anomaly_detected`` keyed by ``method.fqn`` and
``anomaly.reason`` so production dashboards can track numeric quality.
"""

from __future__ import annotations

import statistics
import threading
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

__all__ = [
    "AnomalyFlag",
    "MethodOutputMonitor",
    "get_output_monitor",
]

# ---------------------------------------------------------------------------
# AnomalyFlag
# ---------------------------------------------------------------------------

_SEVERITIES = {"info", "warning", "error"}


@dataclass(frozen=True)
class AnomalyFlag:
    """Represents a single detected anomaly in a method's output."""

    key: str
    """Output dict key where the anomaly was detected (or ``"*"`` for global)."""

    reason: Literal[
        "nan_detected",
        "inf_detected",
        "unexpected_key",
        "missing_key",
        "empty_array",
        "shape_mismatch",
        "distribution_shift",
    ]
    """Machine-readable reason code."""

    severity: Literal["info", "warning", "error"]
    """How serious the anomaly is."""

    detail: str = ""
    """Human-readable detail message."""

    z_score: float | None = None
    """Z-score for ``distribution_shift`` anomalies; None otherwise."""

    def __str__(self) -> str:
        z = f" (z={self.z_score:.2f})" if self.z_score is not None else ""
        return f"[{self.severity.upper()}] {self.key}: {self.reason}{z} — {self.detail}"


# ---------------------------------------------------------------------------
# MethodOutputMonitor
# ---------------------------------------------------------------------------


class MethodOutputMonitor:
    """
    Detects anomalies in Foundry method outputs.

    Thread-safe; can be shared across dispatcher calls.

    Parameters
    ----------
    history_maxlen:
        Maximum number of past scalar statistics to retain per (fqn, key)
        pair for statistical anomaly detection.
    z_score_threshold:
        Absolute z-score above which a ``distribution_shift`` flag is raised.
    """

    def __init__(
        self,
        *,
        history_maxlen: int = 200,
        z_score_threshold: float = 4.0,
    ) -> None:
        self._history_maxlen = history_maxlen
        self._z_threshold = z_score_threshold
        # (fqn, key) -> deque of scalar means
        self._history: dict[tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=self._history_maxlen)
        )
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_basic(
        self,
        result: dict[str, Any],
        *,
        expected_keys: set[str] | frozenset[str] | None = None,
    ) -> list[AnomalyFlag]:
        """
        Fast, always-on check for NaN/Inf and key mismatches.

        Runs in O(n_elements) time, fully vectorized via NumPy.

        Parameters
        ----------
        result:
            Output dict from ``pure_step``.
        expected_keys:
            If provided, flags keys present in result but not in
            expected_keys (``unexpected_key``) and vice-versa
            (``missing_key``).

        Returns
        -------
        list[AnomalyFlag]
            Empty list when no anomalies are found.
        """
        flags: list[AnomalyFlag] = []

        if not isinstance(result, dict):
            # Raw (non-dict) output from legacy pure_step — skip key checks, run as single value
            result = {"output": result}

        if expected_keys is not None:
            result_keys = set(result.keys())
            for k in result_keys - expected_keys:
                flags.append(
                    AnomalyFlag(
                        key=k,
                        reason="unexpected_key",
                        severity="warning",
                        detail=f"Key '{k}' not declared in output slots",
                    )
                )
            for k in expected_keys - result_keys:
                flags.append(
                    AnomalyFlag(
                        key=k,
                        reason="missing_key",
                        severity="error",
                        detail=f"Declared output slot '{k}' missing from result",
                    )
                )

        for key, value in result.items():
            arr = _try_as_array(value)
            if arr is None:
                continue  # non-array output (scalar, str, dict) — skip numeric checks

            if arr.size == 0:
                flags.append(
                    AnomalyFlag(
                        key=key,
                        reason="empty_array",
                        severity="warning",
                        detail=f"Output '{key}' is an empty array",
                    )
                )
                continue

            if not np.issubdtype(arr.dtype, np.floating) and not np.issubdtype(
                arr.dtype, np.complexfloating
            ):
                continue  # integer arrays: NaN/Inf not applicable

            nan_count = int(np.sum(np.isnan(arr)))
            inf_count = int(np.sum(np.isinf(arr)))

            if nan_count > 0:
                flags.append(
                    AnomalyFlag(
                        key=key,
                        reason="nan_detected",
                        severity="error",
                        detail=f"{nan_count} NaN value(s) in '{key}' (shape={arr.shape})",
                    )
                )
            if inf_count > 0:
                flags.append(
                    AnomalyFlag(
                        key=key,
                        reason="inf_detected",
                        severity="error",
                        detail=f"{inf_count} Inf value(s) in '{key}' (shape={arr.shape})",
                    )
                )

        return flags

    def check_statistical(
        self,
        method_fqn: str,
        result: dict[str, Any],
    ) -> list[AnomalyFlag]:
        """
        Statistical anomaly detection using a rolling z-score.

        Compares scalar statistics (mean) of each numeric output array against
        the historical distribution of previous calls for the same method.
        Requires at least 10 historical samples before flagging anything.

        Parameters
        ----------
        method_fqn:
            Fully-qualified method name used as history key.
        result:
            Output dict from ``pure_step``.

        Returns
        -------
        list[AnomalyFlag]
        """
        flags: list[AnomalyFlag] = []

        for key, value in result.items():
            arr = _try_as_array(value)
            if arr is None or arr.size == 0:
                continue
            if not np.issubdtype(arr.dtype, np.floating):
                continue
            if not np.all(np.isfinite(arr)):
                continue  # NaN/Inf already caught by check_basic

            current_mean = float(np.mean(arr))
            hist_key = (method_fqn, key)

            with self._lock:
                history = self._history[hist_key]
                if len(history) >= 10:
                    try:
                        mu = statistics.mean(history)
                        sigma = statistics.stdev(history)
                    except statistics.StatisticsError:
                        history.append(current_mean)
                        continue

                    # Use a small epsilon floor so zero-variance history still
                    # detects extreme outliers (z → ∞ when sigma ≈ 0 and value ≠ mu)
                    effective_sigma = max(sigma, abs(mu) * 1e-6 + 1e-12)
                    z = abs(current_mean - mu) / effective_sigma
                    if z > self._z_threshold:
                        flags.append(
                            AnomalyFlag(
                                key=key,
                                reason="distribution_shift",
                                severity="warning",
                                detail=(
                                    f"Output mean {current_mean:.4g} deviates "
                                    f"{z:.1f}σ from historical μ={mu:.4g}"
                                ),
                                z_score=z,
                            )
                        )

                history.append(current_mean)

        return flags

    def record(self, method_fqn: str, result: dict[str, Any]) -> None:
        """
        Record output statistics without checking for anomalies.

        Useful for building up history before statistical checks become active.
        """
        for key, value in result.items():
            arr = _try_as_array(value)
            if arr is None or arr.size == 0:
                continue
            if not np.issubdtype(arr.dtype, np.floating):
                continue
            if not np.all(np.isfinite(arr)):
                continue
            with self._lock:
                self._history[(method_fqn, key)].append(float(np.mean(arr)))


# ---------------------------------------------------------------------------
# OTel emission helper
# ---------------------------------------------------------------------------


def _emit_anomaly_metric(method_fqn: str, flags: Sequence[AnomalyFlag]) -> None:
    """Increment OTel counter ``foundry.method.anomaly_detected`` if OTel active."""
    if not flags:
        return
    try:
        from polisyos.foundry.methods.observability import (
            _OTEL_AVAILABLE,
            _method_errors_counter,  # type: ignore[attr-defined]
        )

        if not _OTEL_AVAILABLE or _method_errors_counter is None:
            return

        for flag in flags:
            _method_errors_counter.add(
                1,
                {
                    "method.fqn": method_fqn,
                    "anomaly.reason": flag.reason,
                    "anomaly.severity": flag.severity,
                },
            )
    except Exception:  # pragma: no cover
        pass  # OTel not configured — silently skip


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_monitor_lock = threading.Lock()
_default_monitor: MethodOutputMonitor | None = None


def get_output_monitor() -> MethodOutputMonitor:
    """Return the process-wide default MethodOutputMonitor (lazy-initialised)."""
    global _default_monitor
    if _default_monitor is None:
        with _monitor_lock:
            if _default_monitor is None:
                _default_monitor = MethodOutputMonitor()
    return _default_monitor


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _try_as_array(value: Any) -> np.ndarray | None:
    """Coerce value to ndarray if possible; return None otherwise."""
    if isinstance(value, str):
        return None
    if isinstance(value, np.ndarray):
        return value
    try:
        arr = np.asarray(value)
        if arr.dtype == object or np.issubdtype(arr.dtype, np.str_):
            return None
        return arr
    except (TypeError, ValueError):
        return None
