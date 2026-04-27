"""
PolicyOS Observability Module — Production-grade telemetry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import OTelConfig, get_default_config

if TYPE_CHECKING:
    from .decorators import traced, traced_method
    from .logs import (
        StructuredFormatter,
        TraceContextFilter,
        configure_otel_logging_handler,
        get_trace_context_dict,
    )
    from .metrics import MetricsRegistry, get_metrics
    from .pricing import estimate_llm_cost_usd, pricing_table
    from .propagation import (
        TracedExecutorWrapper,
        extract_headers,
        inject_headers,
        propagate_context,
        with_context_vars,
        with_trace_context,
    )
    from .tracer import PolicyOSTracer, get_current_trace_context, get_tracer
else:
    try:
        from .decorators import traced, traced_method
        from .logs import (
            StructuredFormatter,
            TraceContextFilter,
            configure_otel_logging_handler,
            get_trace_context_dict,
        )
        from .metrics import MetricsRegistry, get_metrics
        from .pricing import estimate_llm_cost_usd, pricing_table
        from .propagation import (
            TracedExecutorWrapper,
            extract_headers,
            inject_headers,
            propagate_context,
            with_context_vars,
            with_trace_context,
        )
        from .tracer import PolicyOSTracer, get_current_trace_context, get_tracer
    except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency

        class _NoopMetric:
            def add(self, value, attrs=None) -> None:
                return None

            def record(self, value, attrs=None) -> None:
                return None

            def set(self, value, attrs=None) -> None:
                return None

        class _NoopTimer:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class MetricsRegistry:
            def __getattr__(self, name: str):
                return _NoopMetric()

            def record_knowledge_freshness_check(
                self,
                *,
                bundle_ref: str,
                status: str,
                age_seconds: float,
                staleness_ratio: float,
            ) -> None:
                return None

            def record_knowledge_refresh(self, *, reason: str) -> None:
                return None

            def record_optimization_solve(
                self,
                *,
                method: str,
                status: str,
                duration_seconds: float,
            ) -> None:
                return None

            def record_portfolio_search(
                self,
                *,
                portfolio_id: str,
                combinations_evaluated: int,
                best_objective: float | None,
            ) -> None:
                return None

            def record_degraded_path(
                self,
                *,
                component: str,
                operation: str,
                reason: str,
                error_type: str | None = None,
            ) -> None:
                del component, operation, reason, error_type
                return None

            def record_scientist_trace_correlation(
                self,
                *,
                runner_backend: str,
                workflow_id: str,
                run_id: str,
                trace_id: str | None = None,
                span_id: str | None = None,
            ) -> None:
                del runner_backend, workflow_id, run_id, trace_id, span_id
                return None

            def record_scientist_operational_alert(
                self,
                *,
                alert_type: str,
                severity: str,
                workflow_id: str | None = None,
                run_id: str | None = None,
            ) -> None:
                del alert_type, severity, workflow_id, run_id
                return None

            def record_cell_router_request(self, *, cell_id: str, tier: str, status: str) -> None:
                return None

            def record_cell_router_latency(self, *, cell_id: str, duration_seconds: float) -> None:
                return None

            def record_cell_router_failure(self, *, reason: str) -> None:
                return None

            def record_security_incident(self, *, incident_type: str, cell_id: str) -> None:
                return None

            def set_cell_tenant_count(self, *, cell_id: str, tier: str, count: int) -> None:
                return None

            def record_authz_decision(self, *, policy: str, decision: str, cached: bool) -> None:
                return None

            def record_authz_latency(self, policy: str, duration_seconds: float) -> None:
                return None

            def record_authz_cache_hit(self, *, policy: str) -> None:
                return None

            def record_authz_error(self, *, policy: str, reason: str) -> None:
                return None

            def record_identity_failure(self, *, reason: str, provider: str) -> None:
                return None

            def record_runtime_api_request(
                self,
                *,
                route: str,
                method: str,
                status: str,
                duration_seconds: float,
            ) -> None:
                del route, method, status, duration_seconds
                return None

            def record_runtime_data_access(
                self,
                *,
                resource_kind: str,
                endpoint: str,
                outcome: str,
                tenant_scoped: bool,
            ) -> None:
                del resource_kind, endpoint, outcome, tenant_scoped
                return None

            def record_runtime_cache_event(
                self,
                *,
                cache_name: str,
                operation: str,
                outcome: str,
            ) -> None:
                del cache_name, operation, outcome
                return None

            def record_runtime_cache_rebuild(
                self,
                *,
                cache_name: str,
                duration_seconds: float,
                item_count: int,
            ) -> None:
                del cache_name, duration_seconds, item_count
                return None

            def set_runtime_cache_staleness(
                self,
                *,
                cache_name: str,
                staleness_seconds: float,
            ) -> None:
                del cache_name, staleness_seconds
                return None

            def record_runtime_rate_limit_event(
                self,
                *,
                endpoint: str,
                mode: str,
                outcome: str,
            ) -> None:
                del endpoint, mode, outcome
                return None

            def set_runtime_live_streams(
                self,
                *,
                endpoint: str,
                active_streams: int,
            ) -> None:
                del endpoint, active_streams
                return None

            def record_fabric_connector_fetch(
                self,
                *,
                connector_id: str,
                status: str,
                duration_seconds: float,
                row_count: int | None = None,
                payload_bytes: int | None = None,
            ) -> None:
                del connector_id, status, duration_seconds, row_count, payload_bytes
                return None

            def record_fabric_query(
                self,
                *,
                operation: str,
                duration_seconds: float,
                row_count: int | None = None,
                status: str = "success",
            ) -> None:
                del operation, duration_seconds, row_count, status
                return None

            def set_fabric_materialization_lag(
                self,
                lag_seconds: float,
                *,
                scope: str = "world",
                tenant_id: str | None = None,
            ) -> None:
                del lag_seconds, scope, tenant_id
                return None

            def set_fabric_segment_count(
                self,
                count: float,
                *,
                scope: str = "world",
                tenant_id: str | None = None,
            ) -> None:
                del count, scope, tenant_id
                return None

            def record_fabric_quality_score(
                self,
                *,
                metric_id: str,
                score: float,
            ) -> None:
                del metric_id, score
                return None

            def record_fabric_freshness_age(
                self,
                *,
                dataset_id: str,
                age_seconds: float,
            ) -> None:
                del dataset_id, age_seconds
                return None

            def record_fabric_lineage_graph(
                self,
                *,
                graph_id: str,
                node_count: int,
                edge_count: int,
            ) -> None:
                del graph_id, node_count, edge_count
                return None

            def set_fabric_prefetch_backlog(
                self,
                backlog: int,
                *,
                namespace: str = "connector_cache",
                tenant_id: str | None = None,
            ) -> None:
                del backlog, namespace, tenant_id
                return None

            def set_fabric_dlq_count(
                self,
                count: float,
                *,
                queue_name: str = "fabric",
                tenant_id: str | None = None,
            ) -> None:
                del count, queue_name, tenant_id
                return None

            def record_fabric_slo_assessment(
                self,
                *,
                sli_name: str,
                observed_value: float | None,
                burn_ratio: float | None,
                healthy: bool,
                priority: str,
                window: str,
            ) -> None:
                del sli_name, observed_value, burn_ratio, healthy, priority, window
                return None

            def record_audit_entry(self, *, chain_id: str, event_type: str) -> None:
                return None

            def set_audit_queue_depth(self, *, chain_id: str, depth: int) -> None:
                return None

            def record_audit_write_latency(
                self,
                *,
                backend: str,
                duration_seconds: float,
                status: str,
            ) -> None:
                return None

            def record_audit_chain_tamper(self, *, chain_id: str, count: int = 1) -> None:
                return None

            def record_audit_cold_tier_error(self, *, bucket: str) -> None:
                return None

            def record_tenant_boundary_violation(
                self,
                *,
                source_tenant: str,
                target_tenant: str,
                resource_type: str,
            ) -> None:
                return None

            def record_tee_attestation(self, *, platform: str, outcome: str) -> None:
                return None

            def record_tee_attestation_duration(
                self,
                *,
                platform: str,
                duration_seconds: float,
            ) -> None:
                return None

            def record_tee_attestation_cache_hit(self, *, platform: str) -> None:
                return None

            def record_sbom_generation(self, *, source: str, outcome: str) -> None:
                return None

            def record_sbom_vulnerability_count(self, *, severity: str, count: int) -> None:
                return None

            def record_sbom_deployment_gate(self, *, decision: str) -> None:
                return None

            def record_artifact_integrity_failure(self, *, backend: str, reason: str) -> None:
                del backend, reason
                return None

            def record_control_plane_job_admission(
                self,
                *,
                job_kind: str,
                effective_profile: str,
                status: str,
                duration_seconds: float,
            ) -> None:
                del job_kind, effective_profile, status, duration_seconds
                return None

            def record_control_plane_job_execution(
                self,
                *,
                job_kind: str,
                status: str,
                duration_seconds: float,
                queue_lag_seconds: float,
            ) -> None:
                del job_kind, status, duration_seconds, queue_lag_seconds
                return None

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
                return None

            def record_drafter_multipass_pass(
                self,
                *,
                pass_name: str,
                duration_seconds: float,
                executed: bool,
            ) -> None:
                return None

            def time_informed_critic(self, attributes=None):
                del attributes
                return _NoopTimer()

            def record_constitution_generated(
                self,
                *,
                domain: str,
                duration_seconds: float,
                section_counts: dict[str, int] | None = None,
            ) -> None:
                del domain, duration_seconds, section_counts
                return None

            def record_critic_preemptive_catch(self, *, catch_type: str, count: int = 1) -> None:
                del catch_type, count
                return None

            def record_feasibility_query(self, *, duration_seconds: float, status: str) -> None:
                del duration_seconds, status
                return None

            def set_failure_pattern_index_size(self, size: int) -> None:
                del size
                return None

            def record_knowledge_base_gc_removed(self, count: int) -> None:
                del count
                return None

            def ensure_initialized(self) -> None:
                return None

            def get_exporter_health(self) -> dict[str, dict[str, object]]:
                return {"metrics": {"status": "disabled", "failures": []}}

        class _NoopSpan:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def set_attribute(self, key, value) -> None:
                return None

            def set_status(self, status) -> None:
                return None

            def record_exception(self, exc) -> None:
                return None

        class PolicyOSTracer:
            def start_as_current_span(self, name: str, attributes=None):
                return _NoopSpan()

        def get_tracer() -> PolicyOSTracer:
            return PolicyOSTracer()

        _METRICS = MetricsRegistry()

        def get_metrics() -> MetricsRegistry:
            return _METRICS

        def traced(*args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

        def traced_method(*args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

        def configure_otel_logging_handler(*args, **kwargs) -> None:
            return None

        def get_trace_context_dict() -> dict[str, str]:
            return {}

        class StructuredFormatter:
            pass

        class TraceContextFilter:
            pass

        def inject_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
            return headers or {}

        def extract_headers(headers: dict[str, str] | None = None):
            return None

        def propagate_context(*args, **kwargs):
            return None

        def with_trace_context(*args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

        def with_context_vars(*args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

        class TracedExecutorWrapper:
            def __init__(self, executor):
                self._executor = executor

            def submit(self, fn, *args, **kwargs):
                return self._executor.submit(fn, *args, **kwargs)

        def get_current_trace_context() -> dict[str, str]:
            return {}

        def pricing_table() -> dict[str, dict[str, float]]:
            return {}

        def estimate_llm_cost_usd(
            *,
            model: str,
            prompt_tokens: int,
            completion_tokens: int,
        ) -> float:
            return 0.0


__all__ = [
    "MetricsRegistry",
    "OTelConfig",
    "PolicyOSTracer",
    "StructuredFormatter",
    "TraceContextFilter",
    "TracedExecutorWrapper",
    "configure_otel_logging_handler",
    "estimate_llm_cost_usd",
    "extract_headers",
    "get_current_trace_context",
    "get_default_config",
    "get_metrics",
    "get_trace_context_dict",
    "get_tracer",
    "inject_headers",
    "pricing_table",
    "propagate_context",
    "traced",
    "traced_method",
    "with_context_vars",
    "with_trace_context",
]
