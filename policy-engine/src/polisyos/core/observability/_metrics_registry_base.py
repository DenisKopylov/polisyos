"""
MetricsRegistry base: singleton pattern, MeterProvider bootstrap, metric creation.

This module contains the core infrastructure for the MetricsRegistry singleton,
including lazy initialization of the OpenTelemetry MeterProvider, all metric
instrument declarations, and the ``_register_metrics`` method that creates
every counter / histogram / gauge used by PolicyOS.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Self, cast

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

from ..observability._metrics_helpers import GaugeProxy
from ..observability.config import (
    MetricsExporterType,
    OTelConfig,
    get_default_config,
    get_resource_config,
)

__all__ = ["MetricsRegistryBase"]

_bootstrap_logger = logging.getLogger(__name__)


class _MetricsRegistryBase:
    """
    Singleton registry base for all PolicyOS metrics.

    Ensures metrics are registered only once, even across multiple imports.
    Subclasses (mixins) add domain-specific recording methods.
    """

    _instance: _MetricsRegistryBase | None = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    @classmethod
    def current_instance(cls) -> Self | None:
        """Return the cached singleton instance without forcing initialization."""
        return cast("Self | None", cls._instance)

    # -- Workflow metric instruments ----------------------------------------
    workflow_runs_total: metrics.Counter | None = None
    simulation_duration_seconds: metrics.Histogram | None = None
    simulation_steps_total: metrics.Counter | None = None
    simulation_compile_seconds: metrics.Histogram | None = None
    simulation_steps_per_second: GaugeProxy | None = None
    simulation_batch_size: metrics.Histogram | None = None
    llm_calls_total: metrics.Counter | None = None
    llm_tokens_total: metrics.Counter | None = None
    llm_cost_usd: metrics.Histogram | None = None
    llm_latency_ms: metrics.Histogram | None = None
    drafter_multipass_runs_total: metrics.Counter | None = None
    drafter_multipass_passes_total: metrics.Counter | None = None
    drafter_multipass_findings_total: metrics.Counter | None = None
    drafter_multipass_cost_usd: metrics.Histogram | None = None
    drafter_multipass_pass_duration_seconds: metrics.Histogram | None = None
    drafter_multipass_early_exit_total: metrics.Counter | None = None
    drafter_multipass_budget_stop_total: metrics.Counter | None = None
    constitution_generation_seconds: metrics.Histogram | None = None
    constitution_rules_total: metrics.Counter | None = None
    critic_preemptive_catches_total: metrics.Counter | None = None
    informed_critic_duration_seconds: metrics.Histogram | None = None
    feasibility_query_seconds: metrics.Histogram | None = None
    failure_pattern_index_size: GaugeProxy | None = None
    knowledge_base_gc_removed_total: metrics.Counter | None = None
    active_runs: metrics.UpDownCounter | None = None
    validation_issues_total: metrics.Counter | None = None
    degraded_paths_total: metrics.Counter | None = None

    # -- Scientist engine node-level instruments ----------------------------
    scientist_node_starts_total: metrics.Counter | None = None
    scientist_node_duration_seconds: metrics.Histogram | None = None
    scientist_node_executions_total: metrics.Counter | None = None
    scientist_tier_duration_seconds: metrics.Histogram | None = None
    scientist_node_retry_count: metrics.Histogram | None = None
    scientist_workflow_state: metrics.Counter | None = None
    scientist_tier_queue_depth: GaugeProxy | None = None
    scientist_semaphore_wait_seconds: metrics.Histogram | None = None
    scientist_trace_correlations_total: metrics.Counter | None = None
    scientist_operational_alerts_total: metrics.Counter | None = None
    scientist_llm_budget_utilization: GaugeProxy | None = None
    scientist_llm_cost_anomalies_total: metrics.Counter | None = None

    # -- Artifact / connector metric instruments ----------------------------
    artifact_operations_total: metrics.Counter | None = None
    artifact_io_bytes: metrics.Histogram | None = None
    artifact_io_duration_seconds: metrics.Histogram | None = None
    artifact_cache_hits_total: metrics.Counter | None = None
    artifact_cache_misses_total: metrics.Counter | None = None
    connector_cache_operations_total: metrics.Counter | None = None
    connector_cache_latency_seconds: metrics.Histogram | None = None
    connector_cache_entries_total: GaugeProxy | None = None
    connector_cache_size_bytes: GaugeProxy | None = None
    connector_cache_hit_rate: GaugeProxy | None = None
    connector_cache_evictions_total: metrics.Counter | None = None
    connector_cache_prefetch_jobs_total: metrics.Counter | None = None
    connector_retry_attempts_total: metrics.Counter | None = None
    connector_retry_delay_seconds: metrics.Histogram | None = None
    connector_circuit_state: GaugeProxy | None = None
    connector_circuit_trips_total: metrics.Counter | None = None
    connector_circuit_rejected_requests_total: metrics.Counter | None = None
    connector_rate_limit_wait_seconds: metrics.Histogram | None = None
    connector_rate_limit_acquire_duration_seconds: metrics.Histogram | None = None
    connector_rate_limit_throttled_total: metrics.Counter | None = None
    connector_rate_limit_tokens: GaugeProxy | None = None
    connector_fallback_triggered_total: metrics.Counter | None = None
    connector_fallback_success_total: metrics.Counter | None = None
    fabric_connector_fetch_duration_seconds: metrics.Histogram | None = None
    fabric_connector_rows_total: metrics.Counter | None = None
    fabric_connector_bytes_total: metrics.Counter | None = None
    fabric_query_duration_seconds: metrics.Histogram | None = None
    fabric_query_rows_total: metrics.Counter | None = None
    fabric_materialization_lag_seconds: GaugeProxy | None = None
    fabric_segment_count: GaugeProxy | None = None
    fabric_quality_score: GaugeProxy | None = None
    fabric_freshness_age_seconds: GaugeProxy | None = None
    fabric_lineage_graph_nodes: GaugeProxy | None = None
    fabric_lineage_graph_edges: GaugeProxy | None = None
    fabric_prefetch_backlog: GaugeProxy | None = None
    fabric_dlq_entries: GaugeProxy | None = None
    fabric_sli_value: GaugeProxy | None = None
    fabric_error_budget_burn_ratio: GaugeProxy | None = None
    calibration_loss: GaugeProxy | None = None
    calibration_grad_norm: GaugeProxy | None = None
    calibration_step_duration_seconds: metrics.Histogram | None = None
    calibration_convergence_steps: metrics.Histogram | None = None
    governance_pass_duration_seconds: metrics.Histogram | None = None
    slo_dag_runs_total: metrics.Counter | None = None
    slo_dag_duration_seconds: metrics.Histogram | None = None
    slo_run_cost_usd: metrics.Histogram | None = None
    slo_simulation_nan_total: metrics.Counter | None = None
    slo_simulation_runs_total: metrics.Counter | None = None
    slo_connector_requests_total: metrics.Counter | None = None
    knowledge_bundle_age_seconds: GaugeProxy | None = None
    knowledge_bundle_staleness_ratio: GaugeProxy | None = None
    knowledge_bundle_status: GaugeProxy | None = None
    knowledge_bundle_refresh_total: metrics.Counter | None = None
    knowledge_bundle_check_duration_seconds: metrics.Histogram | None = None
    optimization_solve_duration_seconds: metrics.Histogram | None = None
    optimization_solve_status: metrics.Counter | None = None
    portfolio_combinations_evaluated: metrics.Counter | None = None
    portfolio_best_objective: GaugeProxy | None = None

    # -- Infrastructure metric instruments ----------------------------------
    cell_router_requests_total: metrics.Counter | None = None
    cell_router_latency_seconds: metrics.Histogram | None = None
    cell_router_failures_total: metrics.Counter | None = None
    security_incidents_total: metrics.Counter | None = None
    cell_tenants_current: GaugeProxy | None = None
    authz_decisions_total: metrics.Counter | None = None
    authz_latency_seconds: metrics.Histogram | None = None
    authz_cache_hits_total: metrics.Counter | None = None
    authz_errors_total: metrics.Counter | None = None
    identity_failures_total: metrics.Counter | None = None
    audit_entries_total: metrics.Counter | None = None
    audit_sink_queue_depth: GaugeProxy | None = None
    audit_write_latency_seconds: metrics.Histogram | None = None
    audit_chain_tamper_detected_total: metrics.Counter | None = None
    audit_cold_tier_errors_total: metrics.Counter | None = None
    audit_tenant_boundary_violations_total: metrics.Counter | None = None
    tee_attestation_total: metrics.Counter | None = None
    tee_attestation_duration_seconds: metrics.Histogram | None = None
    tee_attestation_cache_hit_total: metrics.Counter | None = None
    sbom_generation_total: metrics.Counter | None = None
    sbom_vulnerability_count: metrics.Histogram | None = None
    sbom_deployment_gate_total: metrics.Counter | None = None
    runtime_api_requests_total: metrics.Counter | None = None
    runtime_api_duration_seconds: metrics.Histogram | None = None
    runtime_api_errors_total: metrics.Counter | None = None
    runtime_data_access_total: metrics.Counter | None = None
    runtime_cache_operations_total: metrics.Counter | None = None
    runtime_cache_rebuild_duration_seconds: metrics.Histogram | None = None
    runtime_cache_item_count: GaugeProxy | None = None
    runtime_cache_staleness_seconds: GaugeProxy | None = None
    control_plane_job_admissions_total: metrics.Counter | None = None
    control_plane_job_admission_duration_seconds: metrics.Histogram | None = None

    # -- Singleton ----------------------------------------------------------

    def __new__(cls) -> _MetricsRegistryBase:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Re-establish instance attributes even if singleton state was reset
        # while the process kept a previously allocated instance alive.
        if not hasattr(self, "_config"):
            self._config: OTelConfig | None = None
            self._provider: MeterProvider | None = None
            self._meter: metrics.Meter | None = None
            self._exporter_health: dict[str, Any] = {
                "metrics": {
                    "status": "unknown",
                    "failures": [],
                }
            }
        if _MetricsRegistryBase._initialized:
            return

    # -- Lazy initialisation ------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Lazy initialization of MeterProvider and metrics."""
        if _MetricsRegistryBase._initialized:
            return

        with self._lock:
            if _MetricsRegistryBase._initialized:
                return

            self._config = get_default_config()
            self._exporter_health = {
                "metrics": {
                    "status": "disabled" if not self._config.enabled else "initializing",
                    "failures": [],
                }
            }

            if not self._config.enabled:
                _MetricsRegistryBase._initialized = True
                return

            # Build resource
            resource_config = get_resource_config(self._config)
            resource = Resource.create(resource_config.to_attributes())

            # Configure metric readers
            readers: list[MetricReader] = []

            # Prometheus exporter
            if self._config.metrics_exporter == MetricsExporterType.PROMETHEUS:
                try:
                    from opentelemetry.exporter.prometheus import PrometheusMetricReader
                    from prometheus_client import start_http_server

                    try:
                        start_http_server(self._config.metrics_port)
                        readers.append(PrometheusMetricReader())
                    except (OSError, RuntimeError) as exc:
                        self._record_exporter_failure("metrics", exc)
                        _bootstrap_logger.warning(
                            "Prometheus metrics exporter disabled after bootstrap failure: %s",
                            exc,
                        )
                except ImportError:
                    self._record_exporter_failure(
                        "metrics",
                        RuntimeError("prometheus exporter dependency missing"),
                    )
                    _bootstrap_logger.warning(
                        "Prometheus metrics exporter requested but optional dependency is missing"
                    )

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
            self._mark_exporter_ready("metrics")

            _MetricsRegistryBase._initialized = True

    # -- Metric registration ------------------------------------------------

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
        self.degraded_paths_total = self._meter.create_counter(
            name="polisyos_degraded_paths_total",
            description="Total degraded-but-recoverable execution paths",
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
            description="Throttle sleep time imposed by rate limiter",
            unit="s",
        )
        self.connector_rate_limit_acquire_duration_seconds = self._meter.create_histogram(
            name="polisyos_connector_rate_limit_acquire_duration_seconds",
            description="Wall-clock duration spent acquiring from the rate limiter",
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
        self.fabric_connector_fetch_duration_seconds = self._meter.create_histogram(
            name="polisyos_fabric_connector_fetch_duration_seconds",
            description="End-to-end Fabric connector fetch latency",
            unit="s",
        )
        self.fabric_connector_rows_total = self._meter.create_counter(
            name="polisyos_fabric_connector_rows_total",
            description="Rows fetched through Fabric connectors",
            unit="1",
        )
        self.fabric_connector_bytes_total = self._meter.create_counter(
            name="polisyos_fabric_connector_bytes_total",
            description="Bytes fetched through Fabric connectors",
            unit="By",
        )
        self.fabric_query_duration_seconds = self._meter.create_histogram(
            name="polisyos_fabric_query_duration_seconds",
            description="Latency of Fabric retrieval/query operations",
            unit="s",
        )
        self.fabric_query_rows_total = self._meter.create_counter(
            name="polisyos_fabric_query_rows_total",
            description="Rows returned by Fabric queries/materialized lookups",
            unit="1",
        )
        self.fabric_materialization_lag_seconds = GaugeProxy(
            self._meter,
            name="polisyos_fabric_materialization_lag_seconds",
            description="Lag between world segment availability and materialization",
            unit="s",
        )
        self.fabric_segment_count = GaugeProxy(
            self._meter,
            name="polisyos_fabric_segment_count",
            description="World/data-plane segment count visible to Fabric",
            unit="1",
        )
        self.fabric_quality_score = GaugeProxy(
            self._meter,
            name="polisyos_fabric_quality_score",
            description="Fabric quality score by metric or report id",
            unit="1",
        )
        self.fabric_freshness_age_seconds = GaugeProxy(
            self._meter,
            name="polisyos_fabric_freshness_age_seconds",
            description="Age of source or cache data used by Fabric freshness checks",
            unit="s",
        )
        self.fabric_lineage_graph_nodes = GaugeProxy(
            self._meter,
            name="polisyos_fabric_lineage_graph_nodes",
            description="Node count for Fabric provenance/lineage graphs",
            unit="1",
        )
        self.fabric_lineage_graph_edges = GaugeProxy(
            self._meter,
            name="polisyos_fabric_lineage_graph_edges",
            description="Edge count for Fabric provenance/lineage graphs",
            unit="1",
        )
        self.fabric_prefetch_backlog = GaugeProxy(
            self._meter,
            name="polisyos_fabric_prefetch_backlog",
            description="Outstanding Fabric cache prefetch backlog",
            unit="1",
        )
        self.fabric_dlq_entries = GaugeProxy(
            self._meter,
            name="polisyos_fabric_dlq_entries",
            description="Fabric dead-letter or quarantined entry count",
            unit="1",
        )
        self.fabric_sli_value = GaugeProxy(
            self._meter,
            name="polisyos_fabric_sli_value",
            description="Observed Fabric SLI value by name and rolling window",
            unit="1",
        )
        self.fabric_error_budget_burn_ratio = GaugeProxy(
            self._meter,
            name="polisyos_fabric_error_budget_burn_ratio",
            description="Fabric SLO error-budget burn ratio by SLI",
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
        self.scientist_node_starts_total = self._meter.create_counter(
            name="polisyos_scientist_node_starts_total",
            description="Scientist node start events by node_id and workflow_id",
            unit="1",
        )
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

        # Scientist engine SLO / backpressure metrics
        self.scientist_node_retry_count = self._meter.create_histogram(
            name="polisyos_scientist_node_retry_count",
            description="Retry attempts per node execution",
            unit="1",
        )
        self.scientist_workflow_state = self._meter.create_counter(
            name="polisyos_scientist_workflow_state",
            description="Workflow state transitions by run_id and state",
            unit="1",
        )
        self.scientist_tier_queue_depth = GaugeProxy(
            self._meter,
            name="polisyos_scientist_tier_queue_depth",
            description="Queued tasks per tier (backpressure indicator)",
            unit="1",
        )
        self.scientist_semaphore_wait_seconds = self._meter.create_histogram(
            name="polisyos_scientist_semaphore_wait_seconds",
            description="Time spent waiting for execution semaphore",
            unit="s",
        )
        self.scientist_trace_correlations_total = self._meter.create_counter(
            name="polisyos_scientist_trace_correlations_total",
            description="Cross-runner trace correlation records emitted by Scientist runtimes",
            unit="1",
        )
        self.scientist_operational_alerts_total = self._meter.create_counter(
            name="polisyos_scientist_operational_alerts_total",
            description=(
                "Operational monitoring alerts for drift, fairness, calibration, and budget paths"
            ),
            unit="1",
        )

        # LLM budget utilization gauge
        self.scientist_llm_budget_utilization = GaugeProxy(
            self._meter,
            name="polisyos_scientist_llm_budget_utilization",
            description="LLM budget utilization ratio (spent / max)",
            unit="1",
        )
        self.scientist_llm_cost_anomalies_total = self._meter.create_counter(
            name="polisyos_scientist_llm_cost_anomalies_total",
            description="Anomalous LLM call costs detected (> 3σ from rolling mean)",
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
        self.artifact_integrity_failures_total = self._meter.create_counter(
            name="polisyos_artifact_integrity_failures_total",
            description="Artifact/blob-manifest read-time integrity failures",
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
        self.runtime_data_access_total = self._meter.create_counter(
            name="polisyos_runtime_data_access_total",
            description="Runtime data-access events by resource kind, endpoint, and outcome",
            unit="1",
        )
        self.runtime_cache_operations_total = self._meter.create_counter(
            name="polisyos_runtime_cache_operations_total",
            description="Runtime cache lookups and refresh decisions by cache and outcome",
            unit="1",
        )
        self.runtime_cache_rebuild_duration_seconds = self._meter.create_histogram(
            name="polisyos_runtime_cache_rebuild_duration_seconds",
            description="Runtime cache rebuild latency",
            unit="s",
        )
        self.runtime_cache_item_count = GaugeProxy(
            self._meter,
            name="polisyos_runtime_cache_item_count",
            description="Current item count for runtime caches",
            unit="1",
        )
        self.runtime_cache_staleness_seconds = GaugeProxy(
            self._meter,
            name="polisyos_runtime_cache_staleness_seconds",
            description="Observed staleness of runtime caches since last successful rebuild",
            unit="s",
        )
        self.runtime_rate_limit_events_total = self._meter.create_counter(
            name="polisyos_runtime_rate_limit_events_total",
            description="Runtime request/live-stream rate-limit decisions and throttles",
            unit="1",
        )
        self.runtime_live_streams_current = GaugeProxy(
            self._meter,
            name="polisyos_runtime_live_streams_current",
            description="Current number of active runtime live streams per endpoint",
            unit="1",
        )
        self.control_plane_job_admissions_total = self._meter.create_counter(
            name="polisyos_control_plane_job_admissions_total",
            description="Control-plane durable job admission attempts by kind/profile/outcome",
            unit="1",
        )
        self.control_plane_job_admission_duration_seconds = self._meter.create_histogram(
            name="polisyos_control_plane_job_admission_duration_seconds",
            description="Control-plane durable job admission latency",
            unit="s",
        )
        self.control_plane_job_executions_total = self._meter.create_counter(
            name="polisyos_control_plane_job_executions_total",
            description="Control-plane durable job execution outcomes by kind/status",
            unit="1",
        )
        self.control_plane_job_execution_duration_seconds = self._meter.create_histogram(
            name="polisyos_control_plane_job_execution_duration_seconds",
            description="Control-plane durable job execution duration",
            unit="s",
        )
        self.control_plane_job_queue_lag_seconds = self._meter.create_histogram(
            name="polisyos_control_plane_job_queue_lag_seconds",
            description="Control-plane queue lag from job creation to worker execution",
            unit="s",
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

    def ensure_initialized(self) -> None:
        """Public bootstrap hook for startup checks and health endpoints."""
        self._ensure_initialized()

    def get_exporter_health(self) -> dict[str, Any]:
        """Return exporter bootstrap state for health/readiness surfaces."""
        self._ensure_initialized()
        metrics_health = self._exporter_health.get("metrics")
        if isinstance(metrics_health, dict):
            return {
                "metrics": {
                    "status": str(metrics_health.get("status", "unknown")),
                    "failures": list(metrics_health.get("failures", [])),
                }
            }
        return {"metrics": {"status": "unknown", "failures": []}}

    # -- Internal helpers ---------------------------------------------------

    def _default_env(self) -> str:
        config = getattr(self, "_config", None)
        if config is not None:
            return str(config.environment)
        return "unknown"

    def _with_env(self, attributes: dict[str, Any] | None) -> dict[str, Any]:
        attrs: dict[str, Any] = dict(attributes or {})
        attrs.setdefault("env", self._default_env())
        return attrs

    def _record_exporter_failure(self, exporter: str, exc: BaseException) -> None:
        health = self._exporter_health.setdefault(exporter, {"status": "degraded", "failures": []})
        health["status"] = "degraded"
        failures = health.setdefault("failures", [])
        failures.append(str(exc))

    def _mark_exporter_ready(self, exporter: str) -> None:
        health = self._exporter_health.setdefault(exporter, {"status": "ok", "failures": []})
        if health.get("status") != "degraded":
            health["status"] = "ok"


MetricsRegistryBase = _MetricsRegistryBase
