"""Tests for the MetricsRegistry singleton."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from polisyos.core.observability import get_metrics
from polisyos.ir.kernel.metrics import (
    MetricTaxonomyValidationError,
    build_production_metric_taxonomy,
    canonicalize_metric_id_with_diagnostics,
)


class TestMetricsRegistry:
    """Tests for the MetricsRegistry singleton."""

    def test_singleton_pattern(self):
        """Metrics registry should be a singleton."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()
        assert metrics1 is metrics2

    def test_histogram_timer(self, test_tracer_provider):
        """Histogram timer should record durations."""
        metrics = get_metrics()

        with metrics.time_simulation({"node": "test"}):
            time.sleep(0.01)

        # Metric was recorded (we can't easily verify the value without a reader)
        # This test mainly verifies no exceptions are raised

    def test_counter_recording(self, test_tracer_provider):
        """Counters should increment without error."""
        metrics = get_metrics()

        metrics.record_workflow_run("success", "EXECUTE", "drafter")
        metrics.record_llm_call("gpt-4", "success", 100, 50)
        metrics.record_validation_issue("blocker", "schema_pass", "type_error")

        # No exceptions = success

    def test_get_metrics_is_thread_safe_singleton(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            instances = list(pool.map(lambda _: get_metrics(), range(32)))
        assert len({id(instance) for instance in instances}) == 1

    def test_new_runtime_control_recorders_are_noop_when_otel_disabled(
        self,
        in_memory_exporter,
        monkeypatch,
    ):
        del in_memory_exporter
        monkeypatch.setenv("POLISYOS_OTEL_ENABLED", "false")
        metrics = get_metrics()

        metrics.record_runtime_rate_limit_event(
            endpoint="POST:/api/v1/control/runs/nl",
            mode="request",
            outcome="allowed",
        )
        metrics.set_runtime_live_streams(
            endpoint="live:/api/v1/runs/live",
            active_streams=1,
        )
        metrics.record_control_plane_job_execution(
            job_kind="nl_run",
            status="success",
            duration_seconds=0.01,
            queue_lag_seconds=0.02,
        )


def test_production_metric_taxonomy_has_stable_evidence_fingerprint() -> None:
    taxonomy = build_production_metric_taxonomy()
    evidence = taxonomy.evidence()

    assert evidence["taxonomy_version"] == taxonomy.taxonomy_version
    assert evidence["canonicalizer"] == taxonomy.canonicalizer
    assert evidence["metric_count"] == len(taxonomy.metrics)
    assert evidence["fingerprint"].startswith("sha256:")
    assert "msme_survival_rate" in taxonomy.metrics
    assert "small_business_survival_rate" in taxonomy.metrics
    assert "household_disposable_income_stability" in taxonomy.metrics
    assert "essential_medicine_access_rate" in taxonomy.metrics
    assert "critical_outage_hours_reduced" in taxonomy.metrics
    assert "post_training_employment_rate" in taxonomy.metrics
    assert "eligible_household_access_rate" in taxonomy.metrics


def test_metric_canonicalizer_records_alias_diagnostics() -> None:
    result = canonicalize_metric_id_with_diagnostics(
        "MSME credit volume",
        path="context.query_outcome",
    )

    assert result.metric_id == "msme_loan_volume"
    assert result.changed is True
    assert result.diagnostics == [
        {
            "path": "context.query_outcome",
            "raw": "MSME credit volume",
            "normalized": "msme_loan_volume",
            "canonical_metric_id": "msme_loan_volume",
            "canonicalizer": "production_metric_taxonomy.v1",
            "taxonomy_version": build_production_metric_taxonomy().taxonomy_version,
            "reason": "alias",
        }
    ]


def test_metric_canonicalizer_suggests_close_matches_for_unknown_metrics() -> None:
    try:
        canonicalize_metric_id_with_diagnostics(
            "msme_survivl_rate",
            path="context.query_outcome",
            fail_unknown=True,
        )
    except MetricTaxonomyValidationError as exc:
        assert exc.unknown_metrics == ["msme_survivl_rate"]
        assert "msme_survival_rate" in exc.suggestions["msme_survivl_rate"]
        assert exc.failure["code"] == "unknown_production_metric"
        assert exc.failure["phase"] == "metric_taxonomy"
    else:  # pragma: no cover - documents the required fail-fast behavior
        raise AssertionError("unknown production metrics must fail")
