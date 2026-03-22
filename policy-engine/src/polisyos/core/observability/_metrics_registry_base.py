"""
MetricsRegistry base: singleton pattern, MeterProvider bootstrap, metric creation.

This module contains the core infrastructure for the MetricsRegistry singleton,
including lazy initialization of the OpenTelemetry MeterProvider, all metric
instrument declarations, and the ``_register_metrics`` method that creates
every counter / histogram / gauge used by PolicyOS.
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

from ..observability._metrics_helpers import GaugeProxy, HistogramTimer
from ..observability.config import (
    MetricsExporterType,
    OTelConfig,
    get_default_config,
    get_resource_config,
)

__all__ = ["_MetricsRegistryBase"]


class _MetricsRegistryBase:
    """
    Singleton registry base for all PolicyOS metrics.

    Ensures metrics are registered only once, even across multiple imports.
    Subclasses (mixins) add domain-specific recording methods.
    """

    _instance: Optional["_MetricsRegistryBase"] = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    # -- Workflow metric instruments ----------------------------------------
    workflow_runs_total: Optional[metrics.Counter] = None
    simulation_duration_seconds: Optional[metrics.Histogram] = None
    simulation_steps_total: Optional[metrics.Counter] = None
    simulation_compile_seconds: Optional[metrics.Histogram] = None
    simulation_steps_per_second: Optional[GaugeProxy] = None
    simulation_batch_size: Optional[metrics.Histogram] = None
    llm_calls_total: Optional[metrics.Counter] = None
    llm_tokens_total: Optional[metrics.Counter] = None
    llm_cost_usd: Optional[metrics.Histogram] = None
    llm_latency_ms: Optional[metrics.Histogram] = None
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

    # -- Scientist engine node-level instruments ----------------------------
    scientist_node_duration_seconds: Optional[metrics.Histogram] = None
    scientist_node_executions_total: Optional[metrics.Counter] = None
    scientist_tier_duration_seconds: Optional[metrics.Histogram] = None

    # -- Artifact / connector metric instruments ----------------------------
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

    # -- Infrastructure metric instruments ----------------------------------
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
    runtime_api_requests_total: Optional[metrics.Counter] = None
    runtime_api_duration_seconds: Optional[metrics.Histogram] = None
    runtime_api_errors_total: Optional[metrics.Counter] = None

    # -- Singleton ----------------------------------------------------------

    def __new__(cls) -> "_MetricsRegistryBase":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if _MetricsRegistryBase._initialized:
            return

        self._config: Optional[OTelConfig] = None
        self._provider: Optional[MeterProvider] = None
        self._meter: Optional[metrics.Meter] = None

    # -- Lazy initialisation ------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Lazy initialization of MeterProvider and metrics."""
        if _MetricsRegistryBase._initialized:
            return

        with self._lock:
            if _MetricsRegistryBase._initialized:
                return

            self._config = get_default_config()

            if not self._config.enabled:
                _MetricsRegistryBase._initialized = True
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

            _MetricsRegistryBase._initialized = True

    # -- Metric registration ------------------------------------------------

    def _register_metrics(self) -> None:  # noqa: C901 — long but linear
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
        self.llm_cost_usd = self._meter.create_histogram(
            name="polisyos_llm_cost_usd",
            description="Estimated or reported LLM call cost",
            unit="USD",
        )
        self.llm_latency_ms = self._meter.create_histogram(
            name="polisyos_llm_latency_ms",
            description="LLM call latency in milliseconds",
            unit="ms",
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

        # Scientist engine node-level metrics
        self.scientist_node_duration_seconds = self._meter.create_histogram(
            name="polisyos_scientist_node_duration_seconds",
            description="Per-node execution duration in the Scientist DAG",
            unit="s",
        )
        self.scientist_node_executions_total = self._meter.create_counter(
            name="polisyos_scientist_node_executions_total",
            description="Scientist node executions by node_id, status, and cache_hit",
            unit="1",
        )
        self.scientist_tier_duration_seconds = self._meter.create_histogram(
            name="polisyos_scientist_tier_duration_seconds",
            description="Per-tier execution duration for parallel DAG tiers",
            unit="s",
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
        self.runtime_api_requests_total = self._meter.create_counter(
            name="polisyos_runtime_api_requests_total",
            description="Runtime API HTTP requests by route/method/status",
            unit="1",
        )
        self.runtime_api_duration_seconds = self._meter.create_histogram(
            name="polisyos_runtime_api_duration_seconds",
            description="Runtime API HTTP request latency",
            unit="s",
        )
        self.runtime_api_errors_total = self._meter.create_counter(
            name="polisyos_runtime_api_errors_total",
            description="Runtime API HTTP error responses (status >= 400)",
            unit="1",
        )

    # -- Lifecycle ----------------------------------------------------------

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

    # -- Internal helpers ---------------------------------------------------

    def _default_env(self) -> str:
        if self._config is not None:
            return self._config.environment
        return "unknown"

    def _with_env(self, attributes: Optional[dict[str, Any]]) -> dict[str, Any]:
        attrs: dict[str, Any] = dict(attributes or {})
        attrs.setdefault("env", self._default_env())
        return attrs
