from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polisyos.scholar.freshness as freshness_module
from polisyos.scholar.freshness import (
    FreshnessPolicy,
    build_freshness_metadata,
    timed_freshness_check,
)


class _FakeDurationMetric:
    def __init__(self) -> None:
        self.records: list[tuple[float, dict[str, object]]] = []

    def record(self, value: float, labels: dict[str, object]) -> None:
        self.records.append((value, labels))


class _FakeMetrics:
    def __init__(self) -> None:
        self.duration_metric = _FakeDurationMetric()
        self.freshness_checks: list[dict[str, object]] = []
        self.refresh_calls: list[dict[str, object]] = []

    @property
    def knowledge_bundle_check_duration_seconds(self) -> _FakeDurationMetric:
        return self.duration_metric

    def record_knowledge_freshness_check(self, **kwargs: object) -> None:
        self.freshness_checks.append(kwargs)

    def record_knowledge_refresh(self, **kwargs: object) -> None:
        self.refresh_calls.append(kwargs)


def test_timed_freshness_check_accepts_injected_metrics(monkeypatch) -> None:
    def _fail_get_metrics():
        raise AssertionError("global metrics lookup should not run when metrics are injected")

    monkeypatch.setattr(freshness_module, "get_metrics", _fail_get_metrics)

    now = datetime(2026, 4, 14, tzinfo=UTC)
    metadata = build_freshness_metadata(
        domain="labor",
        source_freshness_at=now - timedelta(days=60),
        now=now - timedelta(days=60),
    ).model_copy(
        update={
            "staleness_threshold_seconds": 7 * 24 * 3600,
            "expiry_threshold_seconds": 180 * 24 * 3600,
        }
    )
    metrics = _FakeMetrics()

    result = timed_freshness_check(
        FreshnessPolicy(auto_refresh_on_stale=True),
        bundle_ref="bundle.injected-metrics",
        freshness=metadata,
        now=now,
        metrics=metrics,
    )

    assert result.status.value == "stale"
    assert result.needs_refresh is True
    assert metrics.duration_metric.records
    assert metrics.freshness_checks[0]["bundle_ref"] == "bundle.injected-metrics"
    assert metrics.refresh_calls[0]["reason"] == "bundle stale"
