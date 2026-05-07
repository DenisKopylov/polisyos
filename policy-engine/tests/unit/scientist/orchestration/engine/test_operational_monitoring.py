from __future__ import annotations

from polisyos.scientist.orchestration.engine.operational_monitoring import (
    ScientistOperationalMonitor,
    classify_metric_alert,
)


class _FakeMetrics:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def record_scientist_operational_alert(
        self,
        *,
        alert_type: str,
        severity: str,
        workflow_id: str | None,
        run_id: str | None,
    ) -> None:
        self.calls.append(
            {
                "alert_type": alert_type,
                "severity": severity,
                "workflow_id": workflow_id,
                "run_id": run_id,
            }
        )


def test_classify_metric_alert_maps_fairness_and_calibration() -> None:
    assert classify_metric_alert("group_fairness_gap") == "fairness_regression"
    assert classify_metric_alert("rmse_holdout") == "calibration_degradation"
    assert classify_metric_alert("unknown_metric") == "drift"


def test_operational_monitor_is_bounded() -> None:
    monitor = ScientistOperationalMonitor(max_recent_alerts=2)
    monitor.record_alert(alert_type="drift", run_id="r1")
    monitor.record_alert(alert_type="budget_anomaly", run_id="r1")
    monitor.record_alert(alert_type="fairness_regression", run_id="r1")

    snapshot = monitor.snapshot()

    assert [item["alert_type"] for item in snapshot["recent_alerts"]] == [
        "budget_anomaly",
        "fairness_regression",
    ]


def test_operational_monitor_emits_one_alert_per_metric_family() -> None:
    monitor = ScientistOperationalMonitor(max_recent_alerts=5)

    emitted = monitor.ingest_metric_regressions(
        ["group_fairness_gap", "rmse_holdout", "rmse_validation"],
        workflow_id="scientist_default",
        run_id="r-1",
    )

    assert [item.alert_type for item in emitted] == [
        "fairness_regression",
        "calibration_degradation",
    ]


def test_operational_monitor_accepts_injected_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.operational_monitoring._default_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )
    metrics = _FakeMetrics()
    monitor = ScientistOperationalMonitor(max_recent_alerts=2, metrics=metrics)

    record = monitor.record_alert(
        alert_type="budget_anomaly",
        severity="warn",
        workflow_id="wf-1",
        run_id="run-1",
    )

    assert record.alert_type == "budget_anomaly"
    assert metrics.calls == [
        {
            "alert_type": "budget_anomaly",
            "severity": "warn",
            "workflow_id": "wf-1",
            "run_id": "run-1",
        }
    ]
