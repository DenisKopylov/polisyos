"""
PolicyOS Metrics Registry — Prometheus-compatible metrics with OTel SDK.

Implements a singleton MetricsRegistry to prevent duplicate metric registration
errors during re-imports (common in Jupyter notebooks and test reloads).

Metrics Defined:
- polisyos_workflow_runs_total (Counter): Total workflow runs by status
- polisyos_simulation_duration_seconds (Histogram): Simulation execution time
- polisyos_simulation_steps_total (Counter): Total simulation steps executed
- polisyos_llm_calls_total (Counter): LLM API calls by model and status
- polisyos_llm_tokens_total (Counter): LLM tokens consumed by type
- polisyos_active_runs (Gauge): Currently active experiment runs
- polisyos_validation_issues_total (Counter): Validation issues by severity
- polisyos_artifact_operations_total (Counter): CAS artifact operations

Usage:
    from polisyos.core.observability import metrics

    metrics.workflow_runs_total.add(1, {"status": "success", "phase": "EXECUTE"})

    with metrics.simulation_duration.time({"node": "run_sim"}):
        run_simulation()
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

from .config import MetricsExporterType, OTelConfig, get_default_config, get_resource_config


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


class MetricsRegistry:
    """
    Singleton registry for all PolicyOS metrics.

    Ensures metrics are registered only once, even across multiple imports.
    """

    _instance: Optional["MetricsRegistry"] = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    # Metric instances
    workflow_runs_total: Optional[metrics.Counter] = None
    simulation_duration_seconds: Optional[metrics.Histogram] = None
    simulation_steps_total: Optional[metrics.Counter] = None
    llm_calls_total: Optional[metrics.Counter] = None
    llm_tokens_total: Optional[metrics.Counter] = None
    active_runs: Optional[metrics.UpDownCounter] = None
    validation_issues_total: Optional[metrics.Counter] = None
    artifact_operations_total: Optional[metrics.Counter] = None
    governance_pass_duration_seconds: Optional[metrics.Histogram] = None

    def __new__(cls) -> "MetricsRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if MetricsRegistry._initialized:
            return

        self._config: Optional[OTelConfig] = None
        self._provider: Optional[MeterProvider] = None
        self._meter: Optional[metrics.Meter] = None

    def _ensure_initialized(self) -> None:
        """Lazy initialization of MeterProvider and metrics."""
        if MetricsRegistry._initialized:
            return

        with self._lock:
            if MetricsRegistry._initialized:
                return

            self._config = get_default_config()

            if not self._config.enabled:
                MetricsRegistry._initialized = True
                return

            # Build resource
            resource_config = get_resource_config(self._config)
            resource = Resource.create(resource_config.to_attributes())

            # Configure metric readers
            readers = []

            # Prometheus exporter
            if self._config.metrics_exporter == MetricsExporterType.PROMETHEUS:
                try:
                    from opentelemetry.exporter.prometheus import PrometheusMetricReader
                    from prometheus_client import start_http_server

                    try:
                        start_http_server(self._config.metrics_port)
                        readers.append(PrometheusMetricReader())
                    except Exception:
                        # Avoid crashing if port is already in use
                        pass
                except ImportError:
                    pass

            # Console exporter for debugging
            if self._config.console_export:
                readers.append(
                    PeriodicExportingMetricReader(
                        ConsoleMetricExporter(),
                        export_interval_millis=10000,
                    )
                )

            # Create MeterProvider
            self._provider = MeterProvider(
                resource=resource,
                metric_readers=readers if readers else None,
            )
            metrics.set_meter_provider(self._provider)

            # Get meter
            self._meter = metrics.get_meter(
                "polisyos",
                self._config.service_version,
            )

            # Register metrics
            self._register_metrics()

            MetricsRegistry._initialized = True

    def _register_metrics(self) -> None:
        """Register all PolicyOS metrics."""
        if self._meter is None:
            return

        # Workflow runs counter
        self.workflow_runs_total = self._meter.create_counter(
            name="polisyos_workflow_runs_total",
            description="Total number of workflow runs",
            unit="1",
        )

        # Simulation duration histogram
        # Buckets optimized for JAX simulations (10ms to 10min)
        self.simulation_duration_seconds = self._meter.create_histogram(
            name="polisyos_simulation_duration_seconds",
            description="Duration of simulation execution",
            unit="s",
        )

        # Simulation steps counter
        self.simulation_steps_total = self._meter.create_counter(
            name="polisyos_simulation_steps_total",
            description="Total simulation steps executed",
            unit="1",
        )

        # LLM calls counter
        self.llm_calls_total = self._meter.create_counter(
            name="polisyos_llm_calls_total",
            description="Total LLM API calls",
            unit="1",
        )

        # LLM tokens counter
        self.llm_tokens_total = self._meter.create_counter(
            name="polisyos_llm_tokens_total",
            description="Total LLM tokens consumed",
            unit="1",
        )

        # Active runs gauge (UpDownCounter in OTel)
        self.active_runs = self._meter.create_up_down_counter(
            name="polisyos_active_runs",
            description="Number of currently active experiment runs",
            unit="1",
        )

        # Validation issues counter
        self.validation_issues_total = self._meter.create_counter(
            name="polisyos_validation_issues_total",
            description="Total validation issues detected",
            unit="1",
        )

        # Artifact operations counter
        self.artifact_operations_total = self._meter.create_counter(
            name="polisyos_artifact_operations_total",
            description="Total CAS artifact operations",
            unit="1",
        )

        # Governance pass duration
        self.governance_pass_duration_seconds = self._meter.create_histogram(
            name="polisyos_governance_pass_duration_seconds",
            description="Duration of governance validation passes",
            unit="s",
        )

    def time_simulation(
        self,
        attributes: Optional[dict[str, Any]] = None,
    ) -> HistogramTimer:
        """
        Context manager for timing simulations.

        Usage:
            with metrics.time_simulation({"node": "run_sim"}):
                execute_simulation()
        """
        self._ensure_initialized()
        return HistogramTimer(self.simulation_duration_seconds, attributes)

    def time_governance_pass(
        self,
        attributes: Optional[dict[str, Any]] = None,
    ) -> HistogramTimer:
        """Context manager for timing governance passes."""
        self._ensure_initialized()
        return HistogramTimer(self.governance_pass_duration_seconds, attributes)

    def record_workflow_run(
        self,
        status: str,
        phase: str,
        agent: Optional[str] = None,
    ) -> None:
        """Record a workflow run completion."""
        self._ensure_initialized()
        if self.workflow_runs_total is None:
            return
        attrs = {"status": status, "phase": phase}
        if agent:
            attrs["agent"] = agent
        self.workflow_runs_total.add(1, attrs)

    def record_llm_call(
        self,
        model: str,
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record an LLM API call with token counts."""
        self._ensure_initialized()
        attrs = {"model": model, "status": status}

        if self.llm_calls_total:
            self.llm_calls_total.add(1, attrs)

        if self.llm_tokens_total:
            if prompt_tokens > 0:
                self.llm_tokens_total.add(prompt_tokens, {**attrs, "type": "prompt"})
            if completion_tokens > 0:
                self.llm_tokens_total.add(
                    completion_tokens, {**attrs, "type": "completion"}
                )

    def record_validation_issue(
        self,
        severity: str,
        pass_id: str,
        error_type: Optional[str] = None,
    ) -> None:
        """Record a validation issue."""
        self._ensure_initialized()
        if self.validation_issues_total is None:
            return
        attrs = {"severity": severity, "pass_id": pass_id}
        if error_type:
            attrs["error_type"] = error_type
        self.validation_issues_total.add(1, attrs)

    def increment_active_runs(self) -> None:
        """Increment the active runs gauge."""
        self._ensure_initialized()
        if self.active_runs:
            self.active_runs.add(1)

    def decrement_active_runs(self) -> None:
        """Decrement the active runs gauge."""
        self._ensure_initialized()
        if self.active_runs:
            self.active_runs.add(-1)

    def shutdown(self) -> None:
        """Shutdown the meter provider."""
        if self._provider is not None:
            self._provider.shutdown()


# Module-level singleton accessor
_metrics_registry: Optional[MetricsRegistry] = None


def get_metrics() -> MetricsRegistry:
    """Get the global MetricsRegistry instance."""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry
