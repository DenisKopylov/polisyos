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
from opentelemetry.metrics import Observation
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
    simulation_compile_seconds: Optional[metrics.Histogram] = None
    simulation_steps_per_second: Optional[GaugeProxy] = None
    simulation_batch_size: Optional[metrics.Histogram] = None
    llm_calls_total: Optional[metrics.Counter] = None
    llm_tokens_total: Optional[metrics.Counter] = None
    drafter_multipass_runs_total: Optional[metrics.Counter] = None
    drafter_multipass_passes_total: Optional[metrics.Counter] = None
    drafter_multipass_findings_total: Optional[metrics.Counter] = None
    drafter_multipass_cost_usd: Optional[metrics.Histogram] = None
    drafter_multipass_pass_duration_seconds: Optional[metrics.Histogram] = None
    drafter_multipass_early_exit_total: Optional[metrics.Counter] = None
    drafter_multipass_budget_stop_total: Optional[metrics.Counter] = None
    constitution_generation_seconds: Optional[metrics.Histogram] = None
    constitution_rules_total: Optional[metrics.Counter] = None
    critic_preemptive_catches_total: Optional[metrics.Counter] = None
    informed_critic_duration_seconds: Optional[metrics.Histogram] = None
    feasibility_query_seconds: Optional[metrics.Histogram] = None
    failure_pattern_index_size: Optional[GaugeProxy] = None
    knowledge_base_gc_removed_total: Optional[metrics.Counter] = None
    active_runs: Optional[metrics.UpDownCounter] = None
    validation_issues_total: Optional[metrics.Counter] = None
    artifact_operations_total: Optional[metrics.Counter] = None
    artifact_io_bytes: Optional[metrics.Histogram] = None
    artifact_io_duration_seconds: Optional[metrics.Histogram] = None
    artifact_cache_hits_total: Optional[metrics.Counter] = None
    artifact_cache_misses_total: Optional[metrics.Counter] = None
    connector_cache_operations_total: Optional[metrics.Counter] = None
    connector_cache_latency_seconds: Optional[metrics.Histogram] = None
    connector_cache_entries_total: Optional[GaugeProxy] = None
    connector_cache_size_bytes: Optional[GaugeProxy] = None
    connector_cache_hit_rate: Optional[GaugeProxy] = None
    connector_cache_evictions_total: Optional[metrics.Counter] = None
    connector_cache_prefetch_jobs_total: Optional[metrics.Counter] = None
    connector_retry_attempts_total: Optional[metrics.Counter] = None
    connector_retry_delay_seconds: Optional[metrics.Histogram] = None
    connector_circuit_state: Optional[GaugeProxy] = None
    connector_circuit_trips_total: Optional[metrics.Counter] = None
    connector_circuit_rejected_requests_total: Optional[metrics.Counter] = None
    connector_rate_limit_wait_seconds: Optional[metrics.Histogram] = None
    connector_rate_limit_throttled_total: Optional[metrics.Counter] = None
    connector_rate_limit_tokens: Optional[GaugeProxy] = None
    connector_fallback_triggered_total: Optional[metrics.Counter] = None
    connector_fallback_success_total: Optional[metrics.Counter] = None
    calibration_loss: Optional[GaugeProxy] = None
    calibration_grad_norm: Optional[GaugeProxy] = None
    calibration_step_duration_seconds: Optional[metrics.Histogram] = None
    calibration_convergence_steps: Optional[metrics.Histogram] = None
    governance_pass_duration_seconds: Optional[metrics.Histogram] = None
    slo_dag_runs_total: Optional[metrics.Counter] = None
    slo_dag_duration_seconds: Optional[metrics.Histogram] = None
    slo_run_cost_usd: Optional[metrics.Histogram] = None
    slo_simulation_nan_total: Optional[metrics.Counter] = None
    slo_simulation_runs_total: Optional[metrics.Counter] = None
    slo_connector_requests_total: Optional[metrics.Counter] = None
    knowledge_bundle_age_seconds: Optional[GaugeProxy] = None
    knowledge_bundle_staleness_ratio: Optional[GaugeProxy] = None
    knowledge_bundle_status: Optional[GaugeProxy] = None
    knowledge_bundle_refresh_total: Optional[metrics.Counter] = None
    knowledge_bundle_check_duration_seconds: Optional[metrics.Histogram] = None
    optimization_solve_duration_seconds: Optional[metrics.Histogram] = None
    optimization_solve_status: Optional[metrics.Counter] = None
    portfolio_combinations_evaluated: Optional[metrics.Counter] = None
    portfolio_best_objective: Optional[GaugeProxy] = None
    cell_router_requests_total: Optional[metrics.Counter] = None
    cell_router_latency_seconds: Optional[metrics.Histogram] = None
    cell_router_failures_total: Optional[metrics.Counter] = None
    security_incidents_total: Optional[metrics.Counter] = None
    cell_tenants_current: Optional[GaugeProxy] = None
    authz_decisions_total: Optional[metrics.Counter] = None
    authz_latency_seconds: Optional[metrics.Histogram] = None
    authz_cache_hits_total: Optional[metrics.Counter] = None
    authz_errors_total: Optional[metrics.Counter] = None
    identity_failures_total: Optional[metrics.Counter] = None
    audit_entries_total: Optional[metrics.Counter] = None
    audit_sink_queue_depth: Optional[GaugeProxy] = None
    audit_write_latency_seconds: Optional[metrics.Histogram] = None
    audit_chain_tamper_detected_total: Optional[metrics.Counter] = None
    audit_cold_tier_errors_total: Optional[metrics.Counter] = None
    audit_tenant_boundary_violations_total: Optional[metrics.Counter] = None
    tee_attestation_total: Optional[metrics.Counter] = None
    tee_attestation_duration_seconds: Optional[metrics.Histogram] = None
    tee_attestation_cache_hit_total: Optional[metrics.Counter] = None
    sbom_generation_total: Optional[metrics.Counter] = None
    sbom_vulnerability_count: Optional[metrics.Histogram] = None
    sbom_deployment_gate_total: Optional[metrics.Counter] = None

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
                # OpenTelemetry SDK expects an iterable; None breaks on recent versions.
                metric_readers=readers,
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

        # Simulation compile time histogram (JIT warmup)
        self.simulation_compile_seconds = self._meter.create_histogram(
            name="polisyos_simulation_compile_seconds",
            description="JIT compilation time for simulation functions",
            unit="s",
        )

        # Simulation throughput gauge
        self.simulation_steps_per_second = GaugeProxy(
            self._meter,
            name="polisyos_simulation_steps_per_second",
            description="Effective simulation throughput",
            unit="1/s",
        )

        # Simulation batch size histogram
        self.simulation_batch_size = self._meter.create_histogram(
            name="polisyos_simulation_batch_size",
            description="Batch dimension for vectorized execution",
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

        # Drafter multipass metrics
        self.drafter_multipass_runs_total = self._meter.create_counter(
            name="polisyos_drafter_multipass_runs_total",
            description="Total multipass drafter runs",
            unit="1",
        )
        self.drafter_multipass_passes_total = self._meter.create_counter(
            name="polisyos_drafter_multipass_passes_total",
            description="Executed passes in multipass drafter runs",
            unit="1",
        )
        self.drafter_multipass_findings_total = self._meter.create_counter(
            name="polisyos_drafter_multipass_findings_total",
            description="Findings discovered by multipass drafter",
            unit="1",
        )
        self.drafter_multipass_cost_usd = self._meter.create_histogram(
            name="polisyos_drafter_multipass_cost_usd",
            description="Estimated cost per multipass drafter run",
            unit="USD",
        )
        self.drafter_multipass_pass_duration_seconds = self._meter.create_histogram(
            name="polisyos_drafter_multipass_pass_duration_seconds",
            description="Duration of multipass drafter passes",
            unit="s",
        )
        self.drafter_multipass_early_exit_total = self._meter.create_counter(
            name="polisyos_drafter_multipass_early_exit_total",
            description="Multipass drafter runs terminated by early-exit condition",
            unit="1",
        )
        self.drafter_multipass_budget_stop_total = self._meter.create_counter(
            name="polisyos_drafter_multipass_budget_stop_total",
            description="Multipass drafter runs terminated by budget/call limits",
            unit="1",
        )
        self.constitution_generation_seconds = self._meter.create_histogram(
            name="polisyos_constitution_generation_seconds",
            description="Time spent generating policy constitutions",
            unit="s",
        )
        self.constitution_rules_total = self._meter.create_counter(
            name="polisyos_constitution_rules_total",
            description="Generated constitution rules by section type",
            unit="1",
        )
        self.critic_preemptive_catches_total = self._meter.create_counter(
            name="polisyos_critic_preemptive_catches_total",
            description="Issues caught by informed critic prechecks",
            unit="1",
        )
        self.informed_critic_duration_seconds = self._meter.create_histogram(
            name="polisyos_informed_critic_duration_seconds",
            description="Total runtime of informed critic (prechecks + inner critique)",
            unit="s",
        )
        self.feasibility_query_seconds = self._meter.create_histogram(
            name="polisyos_feasibility_query_seconds",
            description="Latency of feasibility probe queries",
            unit="s",
        )
        self.failure_pattern_index_size = GaugeProxy(
            self._meter,
            name="polisyos_failure_pattern_index_size",
            description="Current number of entries in failure pattern index",
            unit="1",
        )
        self.knowledge_base_gc_removed_total = self._meter.create_counter(
            name="polisyos_knowledge_base_gc_removed_total",
            description="Failure pattern entries removed by knowledge-base GC",
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

        # Artifact I/O payload sizes
        self.artifact_io_bytes = self._meter.create_histogram(
            name="polisyos_artifact_io_bytes",
            description="Payload size for CAS operations",
            unit="bytes",
        )

        # Artifact I/O durations
        self.artifact_io_duration_seconds = self._meter.create_histogram(
            name="polisyos_artifact_io_duration_seconds",
            description="CAS I/O operation latency",
            unit="s",
        )

        # Artifact cache hit/miss counters
        self.artifact_cache_hits_total = self._meter.create_counter(
            name="polisyos_artifact_cache_hits_total",
            description="CAS cache hit count",
            unit="1",
        )
        self.artifact_cache_misses_total = self._meter.create_counter(
            name="polisyos_artifact_cache_misses_total",
            description="CAS cache miss count",
            unit="1",
        )

        # Connector cache metrics
        self.connector_cache_operations_total = self._meter.create_counter(
            name="polisyos_connector_cache_operations_total",
            description="Total connector cache operations by operation and status",
            unit="1",
        )
        self.connector_cache_latency_seconds = self._meter.create_histogram(
            name="polisyos_connector_cache_latency_seconds",
            description="Connector cache operation latency",
            unit="s",
        )
        self.connector_cache_entries_total = GaugeProxy(
            self._meter,
            name="polisyos_connector_cache_entries_total",
            description="Total cached entries per namespace",
            unit="1",
        )
        self.connector_cache_size_bytes = GaugeProxy(
            self._meter,
            name="polisyos_connector_cache_size_bytes",
            description="Total cache size in bytes per namespace",
            unit="By",
        )
        self.connector_cache_hit_rate = GaugeProxy(
            self._meter,
            name="polisyos_connector_cache_hit_rate",
            description="Cache hit rate per namespace",
            unit="1",
        )
        self.connector_cache_evictions_total = self._meter.create_counter(
            name="polisyos_connector_cache_evictions_total",
            description="Connector cache evictions by reason",
            unit="1",
        )
        self.connector_cache_prefetch_jobs_total = self._meter.create_counter(
            name="polisyos_connector_cache_prefetch_jobs_total",
            description="Connector cache prefetch jobs by status",
            unit="1",
        )

        # Connector resilience metrics
        self.connector_retry_attempts_total = self._meter.create_counter(
            name="polisyos_connector_retry_attempts_total",
            description="Total retry attempts by connector and attempt number",
            unit="1",
        )
        self.connector_retry_delay_seconds = self._meter.create_histogram(
            name="polisyos_connector_retry_delay_seconds",
            description="Delay applied before retry attempts",
            unit="s",
        )
        self.connector_circuit_state = GaugeProxy(
            self._meter,
            name="polisyos_connector_circuit_state",
            description="Circuit breaker state (0=closed,1=open,2=half_open)",
            unit="1",
        )
        self.connector_circuit_trips_total = self._meter.create_counter(
            name="polisyos_connector_circuit_trips_total",
            description="Circuit breaker trips by circuit_id",
            unit="1",
        )
        self.connector_circuit_rejected_requests_total = self._meter.create_counter(
            name="polisyos_connector_circuit_rejected_requests_total",
            description="Requests rejected due to open circuit",
            unit="1",
        )
        self.connector_rate_limit_wait_seconds = self._meter.create_histogram(
            name="polisyos_connector_rate_limit_wait_seconds",
            description="Wait time imposed by rate limiter",
            unit="s",
        )
        self.connector_rate_limit_throttled_total = self._meter.create_counter(
            name="polisyos_connector_rate_limit_throttled_total",
            description="Total rate limit throttling events",
            unit="1",
        )
        self.connector_rate_limit_tokens = GaugeProxy(
            self._meter,
            name="polisyos_connector_rate_limit_tokens",
            description="Current token bucket level",
            unit="1",
        )
        self.connector_fallback_triggered_total = self._meter.create_counter(
            name="polisyos_connector_fallback_triggered_total",
            description="Fallback strategy executions",
            unit="1",
        )
        self.connector_fallback_success_total = self._meter.create_counter(
            name="polisyos_connector_fallback_success_total",
            description="Fallback strategy successes",
            unit="1",
        )

        # Governance pass duration
        self.governance_pass_duration_seconds = self._meter.create_histogram(
            name="polisyos_governance_pass_duration_seconds",
            description="Duration of governance validation passes",
            unit="s",
        )

        # Calibration gauges and histograms
        self.calibration_loss = GaugeProxy(
            self._meter,
            name="polisyos_calibration_loss",
            description="Current calibration loss value",
            unit="1",
        )
        self.calibration_grad_norm = GaugeProxy(
            self._meter,
            name="polisyos_calibration_grad_norm",
            description="Gradient L2 norm during calibration",
            unit="1",
        )
        self.calibration_step_duration_seconds = self._meter.create_histogram(
            name="polisyos_calibration_step_duration_seconds",
            description="Duration per optimization step",
            unit="s",
        )
        self.calibration_convergence_steps = self._meter.create_histogram(
            name="polisyos_calibration_convergence_steps",
            description="Steps to convergence",
            unit="1",
        )

        # SLO metrics
        self.slo_dag_runs_total = self._meter.create_counter(
            name="polisyos_slo_dag_runs_total",
            description="Scientist DAG runs by outcome",
            unit="1",
        )
        self.slo_dag_duration_seconds = self._meter.create_histogram(
            name="polisyos_slo_dag_duration_seconds",
            description="Scientist DAG end-to-end duration",
            unit="s",
        )
        self.slo_run_cost_usd = self._meter.create_histogram(
            name="polisyos_slo_run_cost_usd",
            description="Estimated Scientist run cost in USD",
            unit="USD",
        )
        self.slo_simulation_nan_total = self._meter.create_counter(
            name="polisyos_slo_simulation_nan_total",
            description="NaN/Inf detections in simulations",
            unit="1",
        )
        self.slo_simulation_runs_total = self._meter.create_counter(
            name="polisyos_slo_simulation_runs_total",
            description="Simulation runs for SLO denominator",
            unit="1",
        )
        self.slo_connector_requests_total = self._meter.create_counter(
            name="polisyos_slo_connector_requests_total",
            description="Connector request outcomes",
            unit="1",
        )

        # Scholar freshness metrics
        self.knowledge_bundle_age_seconds = GaugeProxy(
            self._meter,
            name="polisyos_knowledge_bundle_age_seconds",
            description="Age of knowledge bundle in seconds",
            unit="s",
        )
        self.knowledge_bundle_staleness_ratio = GaugeProxy(
            self._meter,
            name="polisyos_knowledge_bundle_staleness_ratio",
            description="Knowledge bundle age divided by staleness threshold",
            unit="1",
        )
        self.knowledge_bundle_status = GaugeProxy(
            self._meter,
            name="polisyos_knowledge_bundle_status",
            description="Knowledge bundle status indicator by status label",
            unit="1",
        )
        self.knowledge_bundle_refresh_total = self._meter.create_counter(
            name="polisyos_knowledge_bundle_refresh_total",
            description="Knowledge bundle refresh attempts",
            unit="1",
        )
        self.knowledge_bundle_check_duration_seconds = self._meter.create_histogram(
            name="polisyos_knowledge_bundle_check_duration_seconds",
            description="Duration of bundle freshness checks",
            unit="s",
        )

        # Optimization catalog metrics
        self.optimization_solve_duration_seconds = self._meter.create_histogram(
            name="polisyos_optimization_solve_duration_seconds",
            description="Optimization solver execution duration",
            unit="s",
        )
        self.optimization_solve_status = self._meter.create_counter(
            name="polisyos_optimization_solve_status_total",
            description="Optimization solver status counts",
            unit="1",
        )

        # Portfolio search metrics
        self.portfolio_combinations_evaluated = self._meter.create_counter(
            name="polisyos_portfolio_combinations_evaluated_total",
            description="Evaluated policy portfolio combinations",
            unit="1",
        )
        self.portfolio_best_objective = GaugeProxy(
            self._meter,
            name="polisyos_portfolio_best_objective",
            description="Best objective observed per portfolio search",
            unit="1",
        )

        # Cell isolation metrics
        self.cell_router_requests_total = self._meter.create_counter(
            name="polisyos_cell_request_total",
            description="Requests routed through tenant cell router",
            unit="1",
        )
        self.cell_router_latency_seconds = self._meter.create_histogram(
            name="polisyos_cell_routing_duration_seconds",
            description="Tenant-to-cell routing latency",
            unit="s",
        )
        self.cell_router_failures_total = self._meter.create_counter(
            name="polisyos_cell_routing_failures_total",
            description="Failed tenant-to-cell routing attempts",
            unit="1",
        )
        self.security_incidents_total = self._meter.create_counter(
            name="polisyos_security_incidents_total",
            description="Security incidents detected by tenant isolation controls",
            unit="1",
        )
        self.cell_tenants_current = GaugeProxy(
            self._meter,
            name="polisyos_cell_tenants_current",
            description="Current tenants assigned per cell",
            unit="1",
        )
        self.authz_decisions_total = self._meter.create_counter(
            name="polisyos_authz_decisions_total",
            description="Authorization decisions by policy and outcome",
            unit="1",
        )
        self.authz_latency_seconds = self._meter.create_histogram(
            name="polisyos_authz_latency_seconds",
            description="Authorization policy evaluation latency",
            unit="s",
        )
        self.authz_cache_hits_total = self._meter.create_counter(
            name="polisyos_authz_cache_hits_total",
            description="Authorization cache hits by policy",
            unit="1",
        )
        self.authz_errors_total = self._meter.create_counter(
            name="polisyos_authz_errors_total",
            description="Authorization errors with fail-closed denies",
            unit="1",
        )
        self.identity_failures_total = self._meter.create_counter(
            name="polisyos_identity_failures_total",
            description="Identity validation and verification failures",
            unit="1",
        )
        self.audit_entries_total = self._meter.create_counter(
            name="polisyos_audit_entries_total",
            description="Total chained audit entries emitted",
            unit="1",
        )
        self.audit_sink_queue_depth = GaugeProxy(
            self._meter,
            name="polisyos_audit_sink_queue_depth",
            description="Current chained-audit replication queue depth",
            unit="1",
        )
        self.audit_write_latency_seconds = self._meter.create_histogram(
            name="polisyos_audit_write_latency_seconds",
            description="Latency of audit write operations by backend",
            unit="s",
        )
        self.audit_chain_tamper_detected_total = self._meter.create_counter(
            name="polisyos_audit_chain_tamper_detected_total",
            description="Detected tamper events in chained audit verification",
            unit="1",
        )
        self.audit_cold_tier_errors_total = self._meter.create_counter(
            name="polisyos_audit_cold_tier_errors_total",
            description="Cold tier audit write failures",
            unit="1",
        )
        self.audit_tenant_boundary_violations_total = self._meter.create_counter(
            name="polisyos_audit_tenant_boundary_violations_total",
            description="Cross-tenant boundary violations recorded by security controls",
            unit="1",
        )

        self.tee_attestation_total = self._meter.create_counter(
            name="polisyos_tee_attestation_total",
            description="TEE attestation attempts by platform and outcome",
            unit="1",
        )
        self.tee_attestation_duration_seconds = self._meter.create_histogram(
            name="polisyos_tee_attestation_duration_seconds",
            description="TEE attestation latency",
            unit="s",
        )
        self.tee_attestation_cache_hit_total = self._meter.create_counter(
            name="polisyos_tee_attestation_cache_hit_total",
            description="TEE attestation cache reuse",
            unit="1",
        )
        self.sbom_generation_total = self._meter.create_counter(
            name="polisyos_sbom_generation_total",
            description="SBOM generation attempts by source and outcome",
            unit="1",
        )
        self.sbom_vulnerability_count = self._meter.create_histogram(
            name="polisyos_sbom_vulnerability_count",
            description="Vulnerability count observed per SBOM scan",
            unit="1",
        )
        self.sbom_deployment_gate_total = self._meter.create_counter(
            name="polisyos_sbom_deployment_gate_total",
            description="Deployment gate decisions from SBOM policy",
            unit="1",
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

    def time_slo_dag(
        self,
        attributes: Optional[dict[str, Any]] = None,
    ) -> HistogramTimer:
        """Context manager for Scientist DAG SLO latency."""
        self._ensure_initialized()
        attrs = self._with_env(attributes)
        return HistogramTimer(self.slo_dag_duration_seconds, attrs)

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

    def record_knowledge_freshness_check(
        self,
        *,
        bundle_ref: str,
        status: str,
        age_seconds: float,
        staleness_ratio: float,
    ) -> None:
        self._ensure_initialized()
        bundle_label = bundle_ref[:16]
        if self.knowledge_bundle_age_seconds is not None:
            self.knowledge_bundle_age_seconds.set(float(age_seconds), {"bundle_ref": bundle_label})
        if self.knowledge_bundle_staleness_ratio is not None:
            self.knowledge_bundle_staleness_ratio.set(
                float(staleness_ratio),
                {"bundle_ref": bundle_label},
            )
        if self.knowledge_bundle_status is not None:
            self.knowledge_bundle_status.set(1.0, {"status": status})

    def record_knowledge_refresh(self, *, reason: str) -> None:
        self._ensure_initialized()
        if self.knowledge_bundle_refresh_total is None:
            return
        self.knowledge_bundle_refresh_total.add(1, {"reason": reason})

    def record_optimization_solve(
        self,
        *,
        method: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        self._ensure_initialized()
        attrs = {"method": method, "status": status}
        if self.optimization_solve_duration_seconds is not None:
            self.optimization_solve_duration_seconds.record(float(duration_seconds), attrs)
        if self.optimization_solve_status is not None:
            self.optimization_solve_status.add(1, attrs)

    def record_portfolio_search(
        self,
        *,
        portfolio_id: str,
        combinations_evaluated: int,
        best_objective: float | None,
    ) -> None:
        self._ensure_initialized()
        attrs = {"portfolio_id": portfolio_id}
        if self.portfolio_combinations_evaluated is not None:
            self.portfolio_combinations_evaluated.add(max(0, int(combinations_evaluated)), attrs)
        if best_objective is not None and self.portfolio_best_objective is not None:
            self.portfolio_best_objective.set(float(best_objective), attrs)

    def record_slo_dag_run(
        self,
        status: str,
        workflow_id: str,
        env: str | None = None,
    ) -> None:
        """Record Scientist DAG run outcome for SLO tracking."""
        self._ensure_initialized()
        if self.slo_dag_runs_total is None:
            return
        attrs = {"status": status, "workflow_id": workflow_id}
        attrs["env"] = env or self._default_env()
        self.slo_dag_runs_total.add(1, attrs)

    def record_slo_run_cost(
        self,
        cost_usd: float,
        workflow_id: str,
        env: str | None = None,
    ) -> None:
        """Record estimated run cost for SLO tracking."""
        self._ensure_initialized()
        if self.slo_run_cost_usd is None:
            return
        attrs = {"workflow_id": workflow_id, "env": env or self._default_env()}
        self.slo_run_cost_usd.record(max(cost_usd, 0.0), attrs)

    def record_slo_simulation_nan(
        self,
        method: str,
        env: str | None = None,
    ) -> None:
        """Record a NaN/Inf detection event."""
        self._ensure_initialized()
        if self.slo_simulation_nan_total is None:
            return
        attrs = {"method": method, "env": env or self._default_env()}
        self.slo_simulation_nan_total.add(1, attrs)

    def record_slo_simulation_run(
        self,
        status: str,
        method: str,
        env: str | None = None,
    ) -> None:
        """Record simulation run status for SLO denominator."""
        self._ensure_initialized()
        if self.slo_simulation_runs_total is None:
            return
        attrs = {"status": status, "method": method, "env": env or self._default_env()}
        self.slo_simulation_runs_total.add(1, attrs)

    def record_slo_connector_request(
        self,
        status: str,
        connector_id: str,
        env: str | None = None,
    ) -> None:
        """Record connector request status for SLO error-rate tracking."""
        self._ensure_initialized()
        if self.slo_connector_requests_total is None:
            return
        attrs = {
            "status": status,
            "connector_id": connector_id,
            "env": env or self._default_env(),
        }
        self.slo_connector_requests_total.add(1, attrs)

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

    def record_drafter_multipass_run(
        self,
        *,
        domain: str,
        executed_passes: int,
        total_findings: int,
        total_cost_usd: float,
        early_exit: bool,
        budget_stop: bool,
        shadow_mode: bool = False,
    ) -> None:
        """Record aggregate metrics for one multipass drafter run."""
        self._ensure_initialized()
        attrs = {
            "domain": domain or "unknown",
            "shadow_mode": str(bool(shadow_mode)).lower(),
        }
        if self.drafter_multipass_runs_total is not None:
            self.drafter_multipass_runs_total.add(1, attrs)
        if self.drafter_multipass_passes_total is not None and executed_passes > 0:
            self.drafter_multipass_passes_total.add(max(0, int(executed_passes)), attrs)
        if self.drafter_multipass_findings_total is not None and total_findings > 0:
            self.drafter_multipass_findings_total.add(max(0, int(total_findings)), attrs)
        if self.drafter_multipass_cost_usd is not None:
            self.drafter_multipass_cost_usd.record(max(0.0, float(total_cost_usd)), attrs)
        if early_exit and self.drafter_multipass_early_exit_total is not None:
            self.drafter_multipass_early_exit_total.add(1, attrs)
        if budget_stop and self.drafter_multipass_budget_stop_total is not None:
            self.drafter_multipass_budget_stop_total.add(1, attrs)

    def record_drafter_multipass_pass(
        self,
        *,
        pass_name: str,
        duration_seconds: float,
        executed: bool,
    ) -> None:
        """Record per-pass duration and findings for multipass drafter."""
        self._ensure_initialized()
        attrs = {
            "pass_name": pass_name,
            "executed": str(bool(executed)).lower(),
        }
        if self.drafter_multipass_pass_duration_seconds is not None:
            self.drafter_multipass_pass_duration_seconds.record(
                max(0.0, float(duration_seconds)),
                attrs,
            )

    def time_informed_critic(
        self,
        attributes: Optional[dict[str, Any]] = None,
    ) -> HistogramTimer:
        """Context manager for measuring informed critic end-to-end latency."""
        self._ensure_initialized()
        return HistogramTimer(self.informed_critic_duration_seconds, attributes)

    def record_constitution_generated(
        self,
        *,
        domain: str,
        duration_seconds: float,
        section_counts: dict[str, int] | None = None,
    ) -> None:
        """Record constitution generation latency and per-section rule counts."""
        self._ensure_initialized()
        attrs = {"domain": domain or "unknown"}
        if self.constitution_generation_seconds is not None:
            self.constitution_generation_seconds.record(max(0.0, float(duration_seconds)), attrs)
        if self.constitution_rules_total is None:
            return
        for section_type, count in (section_counts or {}).items():
            safe_count = max(0, int(count))
            if safe_count <= 0:
                continue
            self.constitution_rules_total.add(
                safe_count,
                {**attrs, "section_type": str(section_type)},
            )

    def record_critic_preemptive_catch(self, *, catch_type: str, count: int = 1) -> None:
        """Record a preemptive issue caught before governance pipeline."""
        self._ensure_initialized()
        if self.critic_preemptive_catches_total is None:
            return
        self.critic_preemptive_catches_total.add(
            max(1, int(count)),
            {"catch_type": catch_type or "unknown"},
        )

    def record_feasibility_query(self, *, duration_seconds: float, status: str) -> None:
        """Record feasibility probe query latency."""
        self._ensure_initialized()
        if self.feasibility_query_seconds is None:
            return
        self.feasibility_query_seconds.record(
            max(0.0, float(duration_seconds)),
            {"status": status or "unknown"},
        )

    def set_failure_pattern_index_size(self, size: int) -> None:
        """Set current failure pattern index size gauge."""
        self._ensure_initialized()
        if self.failure_pattern_index_size is None:
            return
        self.failure_pattern_index_size.set(float(max(0, int(size))))

    def record_knowledge_base_gc_removed(self, count: int) -> None:
        """Record number of stale patterns removed by GC."""
        self._ensure_initialized()
        if self.knowledge_base_gc_removed_total is None:
            return
        safe_count = max(0, int(count))
        if safe_count > 0:
            self.knowledge_base_gc_removed_total.add(safe_count)

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

    def record_cell_router_request(self, *, cell_id: str, tier: str, status: str) -> None:
        self._ensure_initialized()
        if self.cell_router_requests_total is None:
            return
        self.cell_router_requests_total.add(
            1,
            {"cell_id": cell_id, "tier": tier, "status": status},
        )

    def record_cell_router_latency(self, *, cell_id: str, duration_seconds: float) -> None:
        self._ensure_initialized()
        if self.cell_router_latency_seconds is None:
            return
        self.cell_router_latency_seconds.record(max(duration_seconds, 0.0), {"cell_id": cell_id})

    def record_cell_router_failure(self, *, reason: str) -> None:
        self._ensure_initialized()
        if self.cell_router_failures_total is None:
            return
        self.cell_router_failures_total.add(1, {"reason": reason})

    def record_security_incident(self, *, incident_type: str, cell_id: str) -> None:
        self._ensure_initialized()
        if self.security_incidents_total is None:
            return
        self.security_incidents_total.add(1, {"type": incident_type, "cell_id": cell_id})

    def set_cell_tenant_count(self, *, cell_id: str, tier: str, count: int) -> None:
        self._ensure_initialized()
        if self.cell_tenants_current is None:
            return
        self.cell_tenants_current.set(float(max(count, 0)), {"cell_id": cell_id, "tier": tier})

    def record_authz_decision(self, *, policy: str, decision: str, cached: bool) -> None:
        self._ensure_initialized()
        if self.authz_decisions_total is None:
            return
        self.authz_decisions_total.add(
            1,
            {"policy": policy, "decision": decision, "cached": str(cached).lower()},
        )

    def record_authz_latency(self, policy: str, duration_seconds: float) -> None:
        self._ensure_initialized()
        if self.authz_latency_seconds is None:
            return
        self.authz_latency_seconds.record(max(duration_seconds, 0.0), {"policy": policy})

    def record_authz_cache_hit(self, *, policy: str) -> None:
        self._ensure_initialized()
        if self.authz_cache_hits_total is None:
            return
        self.authz_cache_hits_total.add(1, {"policy": policy})

    def record_authz_error(self, *, policy: str, reason: str) -> None:
        self._ensure_initialized()
        if self.authz_errors_total is None:
            return
        self.authz_errors_total.add(1, {"policy": policy, "reason": reason})

    def record_identity_failure(self, *, reason: str, provider: str) -> None:
        self._ensure_initialized()
        if self.identity_failures_total is None:
            return
        self.identity_failures_total.add(1, {"reason": reason, "provider": provider})

    def record_audit_entry(self, *, chain_id: str, event_type: str) -> None:
        self._ensure_initialized()
        if self.audit_entries_total is None:
            return
        self.audit_entries_total.add(1, {"chain_id": chain_id, "event_type": event_type})

    def set_audit_queue_depth(self, *, chain_id: str, depth: int) -> None:
        self._ensure_initialized()
        if self.audit_sink_queue_depth is None:
            return
        self.audit_sink_queue_depth.set(float(max(depth, 0)), {"chain_id": chain_id})

    def record_audit_write_latency(
        self,
        *,
        backend: str,
        duration_seconds: float,
        status: str,
    ) -> None:
        self._ensure_initialized()
        if self.audit_write_latency_seconds is None:
            return
        self.audit_write_latency_seconds.record(
            max(duration_seconds, 0.0),
            {"backend": backend, "status": status},
        )

    def record_audit_chain_tamper(self, *, chain_id: str, count: int = 1) -> None:
        self._ensure_initialized()
        if self.audit_chain_tamper_detected_total is None:
            return
        self.audit_chain_tamper_detected_total.add(max(1, int(count)), {"chain_id": chain_id})

    def record_audit_cold_tier_error(self, *, bucket: str) -> None:
        self._ensure_initialized()
        if self.audit_cold_tier_errors_total is None:
            return
        self.audit_cold_tier_errors_total.add(1, {"bucket": bucket})

    def record_tenant_boundary_violation(
        self,
        *,
        source_tenant: str,
        target_tenant: str,
        resource_type: str,
    ) -> None:
        self._ensure_initialized()
        if self.audit_tenant_boundary_violations_total is None:
            return
        self.audit_tenant_boundary_violations_total.add(
            1,
            {
                "source_tenant": source_tenant,
                "target_tenant": target_tenant,
                "resource_type": resource_type,
            },
        )

    def record_tee_attestation(self, *, platform: str, outcome: str) -> None:
        self._ensure_initialized()
        if self.tee_attestation_total is None:
            return
        self.tee_attestation_total.add(1, {"platform": platform, "outcome": outcome})

    def record_tee_attestation_duration(self, *, platform: str, duration_seconds: float) -> None:
        self._ensure_initialized()
        if self.tee_attestation_duration_seconds is None:
            return
        self.tee_attestation_duration_seconds.record(
            max(duration_seconds, 0.0),
            {"platform": platform},
        )

    def record_tee_attestation_cache_hit(self, *, platform: str) -> None:
        self._ensure_initialized()
        if self.tee_attestation_cache_hit_total is None:
            return
        self.tee_attestation_cache_hit_total.add(1, {"platform": platform})

    def record_sbom_generation(self, *, source: str, outcome: str) -> None:
        self._ensure_initialized()
        if self.sbom_generation_total is None:
            return
        self.sbom_generation_total.add(1, {"source": source, "outcome": outcome})

    def record_sbom_vulnerability_count(self, *, severity: str, count: int) -> None:
        self._ensure_initialized()
        if self.sbom_vulnerability_count is None:
            return
        self.sbom_vulnerability_count.record(float(max(count, 0)), {"severity": severity})

    def record_sbom_deployment_gate(self, *, decision: str) -> None:
        self._ensure_initialized()
        if self.sbom_deployment_gate_total is None:
            return
        self.sbom_deployment_gate_total.add(1, {"decision": decision})

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

    def _default_env(self) -> str:
        if self._config is not None:
            return self._config.environment
        return "unknown"

    def _with_env(self, attributes: Optional[dict[str, Any]]) -> dict[str, Any]:
        attrs: dict[str, Any] = dict(attributes or {})
        attrs.setdefault("env", self._default_env())
        return attrs


# Module-level singleton accessor
_metrics_registry: Optional[MetricsRegistry] = None


def get_metrics() -> MetricsRegistry:
    """Get the global MetricsRegistry instance."""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry
