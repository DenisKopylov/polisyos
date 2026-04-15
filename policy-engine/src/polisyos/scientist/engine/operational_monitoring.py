"""Bounded Scientist operational monitoring hooks and alert helpers."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING, Any

from polisyos.core.observability import get_metrics

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry

_FAIRNESS_TOKENS = ("fair", "equity", "gini", "vulnerable", "disparity")
_CALIBRATION_TOKENS = ("calibration", "coverage", "ece", "brier", "rmse", "mae")


@dataclass(frozen=True, slots=True)
class OperationalAlertRecord:
    """One retained operational alert emitted by Scientist runtime hooks."""

    alert_type: str
    severity: str
    workflow_id: str | None
    run_id: str | None
    details: dict[str, Any]
    created_at: datetime


class ScientistOperationalMonitor:
    """Thread-safe, bounded alert monitor backed by core observability metrics."""

    def __init__(
        self,
        *,
        max_recent_alerts: int = 256,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._recent_alerts: deque[OperationalAlertRecord] = deque(
            maxlen=max(1, int(max_recent_alerts)),
        )
        self._lock = RLock()
        self._metrics = metrics if metrics is not None else get_metrics()

    def record_alert(
        self,
        *,
        alert_type: str,
        severity: str = "warn",
        workflow_id: str | None = None,
        run_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> OperationalAlertRecord:
        record = OperationalAlertRecord(
            alert_type=alert_type,
            severity=severity,
            workflow_id=workflow_id,
            run_id=run_id,
            details=dict(details or {}),
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._recent_alerts.append(record)
        self._metrics.record_scientist_operational_alert(
            alert_type=alert_type,
            severity=severity,
            workflow_id=workflow_id,
            run_id=run_id,
        )
        return record

    def ingest_metric_regressions(
        self,
        metric_ids: list[str],
        *,
        workflow_id: str | None = None,
        run_id: str | None = None,
    ) -> list[OperationalAlertRecord]:
        emitted: list[OperationalAlertRecord] = []
        seen_types: set[str] = set()
        for metric_id in metric_ids:
            alert_type = classify_metric_alert(metric_id)
            if alert_type in seen_types:
                continue
            seen_types.add(alert_type)
            emitted.append(
                self.record_alert(
                    alert_type=alert_type,
                    severity="warn",
                    workflow_id=workflow_id,
                    run_id=run_id,
                    details={"metric_ids": list(metric_ids)},
                )
            )
        return emitted

    def recent_alerts(self) -> list[OperationalAlertRecord]:
        with self._lock:
            return list(self._recent_alerts)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = Counter(item.alert_type for item in self._recent_alerts)
            recent = [asdict(item) for item in self._recent_alerts]
        return {
            "alert_counts": dict(counts),
            "recent_alerts": recent,
        }


def classify_metric_alert(metric_id: str) -> str:
    """Map a refuted metric id into a coarse operational alert family."""
    normalized = str(metric_id or "").strip().lower()
    if any(token in normalized for token in _FAIRNESS_TOKENS):
        return "fairness_regression"
    if any(token in normalized for token in _CALIBRATION_TOKENS):
        return "calibration_degradation"
    return "drift"


_OPERATIONAL_MONITOR: ScientistOperationalMonitor | None = None
_OPERATIONAL_MONITOR_LOCK = RLock()


def get_operational_monitor() -> ScientistOperationalMonitor:
    """Return the process-wide bounded Scientist operational monitor."""
    global _OPERATIONAL_MONITOR
    if _OPERATIONAL_MONITOR is not None:
        return _OPERATIONAL_MONITOR
    with _OPERATIONAL_MONITOR_LOCK:
        if _OPERATIONAL_MONITOR is None:
            _OPERATIONAL_MONITOR = ScientistOperationalMonitor()
    return _OPERATIONAL_MONITOR


__all__ = [
    "OperationalAlertRecord",
    "ScientistOperationalMonitor",
    "classify_metric_alert",
    "get_operational_monitor",
]
