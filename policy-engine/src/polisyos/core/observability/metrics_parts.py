"""Metrics facade built from registry base + recording methods."""

from __future__ import annotations

import threading
from typing import Any, cast

from ._metrics_helpers import GaugeProxy, HistogramTimer
from ._metrics_registry_base import MetricsRegistryBase


class MetricsRegistry(MetricsRegistryBase):
    """Metrics registry implementation."""

    def time_simulation(
        self,
        attributes: dict[str, Any] | None = None,
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
        attributes: dict[str, Any] | None = None,
    ) -> HistogramTimer:
        """Context manager for timing governance passes."""
        self._ensure_initialized()
        return HistogramTimer(self.governance_pass_duration_seconds, attributes)

    def time_slo_dag(
        self,
        attributes: dict[str, Any] | None = None,
    ) -> HistogramTimer:
        """Context manager for Scientist DAG SLO latency."""
        self._ensure_initialized()
        attrs = self._with_env(attributes)
        return HistogramTimer(self.slo_dag_duration_seconds, attrs)

    def record_workflow_run(
        self,
        status: str,
        phase: str,
        agent: str | None = None,
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

    def record_node_started(
        self,
        *,
        alias: str,
        node_id: str,
        workflow_id: str,
    ) -> None:
        """Record a Scientist engine node start event.

        The runtime passes the shared core registry into Scientist workflows,
        so the registry itself must satisfy the engine metrics protocol.
        """
        self._ensure_initialized()
        if self.scientist_node_starts_total is None:
            return
        self.scientist_node_starts_total.add(
            1,
            {
                "alias": alias,
                "node_id": node_id,
                "workflow_id": workflow_id,
            },
        )

    def record_node_completed(
        self,
        *,
        alias: str,
        node_id: str,
        workflow_id: str,
        status: str,
        duration_ms: int,
        cache_hit: bool,
        retry_count: int,
    ) -> None:
        """Record a Scientist engine node completion event."""
        self._ensure_initialized()
        attrs = {
            "node_id": node_id,
            "status": status,
            "workflow_id": workflow_id,
        }
        if alias:
            attrs["alias"] = alias
        if self.scientist_node_duration_seconds is not None:
            self.scientist_node_duration_seconds.record(
                max(0.0, float(duration_ms) / 1000.0),
                attrs,
            )
        if self.scientist_node_executions_total is not None:
            self.scientist_node_executions_total.add(
                1,
                {
                    "node_id": node_id,
                    "status": status,
                    "workflow_id": workflow_id,
                    "cache_hit": str(bool(cache_hit)).lower(),
                },
            )
        if retry_count > 0 and self.scientist_node_retry_count is not None:
            self.scientist_node_retry_count.record(
                int(retry_count),
                {"node_id": node_id, "workflow_id": workflow_id},
            )

    def record_tier_completed(
        self,
        *,
        tier_index: int,
        tier_size: int,
        duration_ms: int,
        workflow_id: str,
    ) -> None:
        """Record per-tier execution duration for parallel DAG tiers."""
        self._ensure_initialized()
        if self.scientist_tier_duration_seconds is None:
            return
        self.scientist_tier_duration_seconds.record(
            max(0.0, float(duration_ms) / 1000.0),
            {
                "tier_index": str(tier_index),
                "tier_size": str(tier_size),
                "workflow_id": workflow_id,
            },
        )

    def record_workflow_completed(
        self,
        *,
        workflow_id: str,
        status: str,
        duration_ms: int,
        node_count: int,
    ) -> None:
        """Record Scientist workflow completion through the SLO DAG instruments."""
        self._ensure_initialized()
        attrs = {"workflow_id": workflow_id, "status": status}
        if self.slo_dag_runs_total is not None:
            self.slo_dag_runs_total.add(1, attrs)
        if self.slo_dag_duration_seconds is not None:
            duration_attrs = dict(attrs)
            duration_attrs["node_count"] = str(max(0, int(node_count)))
            self.slo_dag_duration_seconds.record(
                max(0.0, float(duration_ms) / 1000.0),
                duration_attrs,
            )

    def record_backpressure(
        self,
        *,
        tier_index: int,
        queued_tasks: int,
        active_tasks: int,
        workflow_id: str,
    ) -> None:
        """Record queue depth for Scientist parallel DAG execution."""
        self._ensure_initialized()
        if self.scientist_tier_queue_depth is None:
            return
        self.scientist_tier_queue_depth.set(
            max(0, int(queued_tasks)),
            {
                "tier_index": str(tier_index),
                "workflow_id": workflow_id,
                "active_tasks": str(max(0, int(active_tasks))),
            },
        )

    def record_semaphore_wait(
        self,
        *,
        tier_index: int,
        wait_seconds: float,
        workflow_id: str,
    ) -> None:
        """Record time spent waiting for Scientist execution semaphore permits."""
        self._ensure_initialized()
        if self.scientist_semaphore_wait_seconds is None:
            return
        self.scientist_semaphore_wait_seconds.record(
            max(0.0, float(wait_seconds)),
            {"tier_index": str(tier_index), "workflow_id": workflow_id},
        )

    def record_workflow_state(
        self,
        *,
        run_id: str,
        workflow_id: str,
        state: str,
    ) -> None:
        """Record a Scientist workflow state transition."""
        self._ensure_initialized()
        if self.scientist_workflow_state is None:
            return
        self.scientist_workflow_state.add(
            1,
            {"run_id": run_id, "workflow_id": workflow_id, "state": state},
        )

    def record_trace_correlation(
        self,
        *,
        runner_backend: str,
        workflow_id: str,
        run_id: str,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """EngineMetricsCollector-compatible trace-correlation entrypoint."""
        self.record_scientist_trace_correlation(
            runner_backend=runner_backend,
            workflow_id=workflow_id,
            run_id=run_id,
            trace_id=trace_id,
            span_id=span_id,
        )

    def record_operational_alert(
        self,
        *,
        alert_type: str,
        severity: str,
        workflow_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """EngineMetricsCollector-compatible operational-alert entrypoint."""
        self.record_scientist_operational_alert(
            alert_type=alert_type,
            severity=severity,
            workflow_id=workflow_id,
            run_id=run_id,
        )

    def record_fabric_connector_fetch(
        self,
        *,
        connector_id: str,
        status: str,
        duration_seconds: float,
        row_count: int | None = None,
        payload_bytes: int | None = None,
    ) -> None:
        """Record Fabric connector fetch latency plus optional row/byte volume."""
        self._ensure_initialized()
        attrs = {"connector_id": connector_id, "status": status}
        if self.fabric_connector_fetch_duration_seconds is not None:
            self.fabric_connector_fetch_duration_seconds.record(
                max(0.0, float(duration_seconds)),
                attrs,
            )
        if (
            row_count is not None
            and self.fabric_connector_rows_total is not None
            and row_count >= 0
        ):
            self.fabric_connector_rows_total.add(int(row_count), attrs)
        if (
            payload_bytes is not None
            and self.fabric_connector_bytes_total is not None
            and payload_bytes >= 0
        ):
            self.fabric_connector_bytes_total.add(int(payload_bytes), attrs)

    def record_fabric_query(
        self,
        *,
        operation: str,
        duration_seconds: float,
        row_count: int | None = None,
        status: str = "success",
    ) -> None:
        """Record query/retrieval latency plus optional output cardinality."""
        self._ensure_initialized()
        attrs = {"operation": operation, "status": status}
        if self.fabric_query_duration_seconds is not None:
            self.fabric_query_duration_seconds.record(
                max(0.0, float(duration_seconds)),
                attrs,
            )
        if row_count is not None and self.fabric_query_rows_total is not None and row_count >= 0:
            self.fabric_query_rows_total.add(int(row_count), attrs)

    def set_fabric_materialization_lag(
        self,
        lag_seconds: float,
        *,
        scope: str = "world",
        tenant_id: str | None = None,
    ) -> None:
        self._ensure_initialized()
        if self.fabric_materialization_lag_seconds is None:
            return
        attrs = {"scope": scope}
        if tenant_id:
            attrs["tenant_id"] = tenant_id
        self.fabric_materialization_lag_seconds.set(
            max(0.0, float(lag_seconds)),
            attrs,
        )

    def set_fabric_segment_count(
        self,
        count: float,
        *,
        scope: str = "world",
        tenant_id: str | None = None,
    ) -> None:
        self._ensure_initialized()
        if self.fabric_segment_count is None:
            return
        attrs = {"scope": scope}
        if tenant_id:
            attrs["tenant_id"] = tenant_id
        self.fabric_segment_count.set(max(0.0, float(count)), attrs)

    def record_fabric_quality_score(
        self,
        *,
        metric_id: str,
        score: float,
    ) -> None:
        self._ensure_initialized()
        if self.fabric_quality_score is None:
            return
        self.fabric_quality_score.set(float(score), {"metric_id": metric_id})

    def record_fabric_freshness_age(
        self,
        *,
        dataset_id: str,
        age_seconds: float,
    ) -> None:
        self._ensure_initialized()
        if self.fabric_freshness_age_seconds is None:
            return
        self.fabric_freshness_age_seconds.set(
            max(0.0, float(age_seconds)),
            {"dataset_id": dataset_id},
        )

    def record_fabric_lineage_graph(
        self,
        *,
        graph_id: str,
        node_count: int,
        edge_count: int,
    ) -> None:
        self._ensure_initialized()
        if self.fabric_lineage_graph_nodes is not None:
            self.fabric_lineage_graph_nodes.set(max(0.0, float(node_count)), {"graph_id": graph_id})
        if self.fabric_lineage_graph_edges is not None:
            self.fabric_lineage_graph_edges.set(max(0.0, float(edge_count)), {"graph_id": graph_id})

    def set_fabric_prefetch_backlog(
        self,
        backlog: int,
        *,
        namespace: str = "connector_cache",
        tenant_id: str | None = None,
    ) -> None:
        self._ensure_initialized()
        if self.fabric_prefetch_backlog is None:
            return
        attrs = {"namespace": namespace}
        if tenant_id:
            attrs["tenant_id"] = tenant_id
        self.fabric_prefetch_backlog.set(max(0.0, float(backlog)), attrs)

    def set_fabric_dlq_count(
        self,
        count: float,
        *,
        queue_name: str = "fabric",
        tenant_id: str | None = None,
    ) -> None:
        self._ensure_initialized()
        if self.fabric_dlq_entries is None:
            return
        attrs = {"queue": queue_name}
        if tenant_id:
            attrs["tenant_id"] = tenant_id
        self.fabric_dlq_entries.set(max(0.0, float(count)), attrs)

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
        """Record Fabric SLI value and SLO burn state."""

        self._ensure_initialized()
        attrs = {
            "sli": sli_name,
            "priority": priority,
            "window": window,
            "healthy": str(bool(healthy)).lower(),
        }
        if observed_value is not None and self.fabric_sli_value is not None:
            self.fabric_sli_value.set(max(0.0, float(observed_value)), attrs)
        if burn_ratio is not None and self.fabric_error_budget_burn_ratio is not None:
            self.fabric_error_budget_burn_ratio.set(max(0.0, float(burn_ratio)), attrs)

    def record_llm_call(
        self,
        model: str,
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        provider: str | None = None,
        run_id: str | None = None,
        model_variant_id: str | None = None,
        cost_usd: float | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Record an LLM API call with token counts."""
        self._ensure_initialized()
        attrs: dict[str, str] = {"model": model, "status": status}
        if provider:
            attrs["provider"] = provider
        if run_id:
            attrs["run_id"] = run_id
        if model_variant_id:
            attrs["model_variant_id"] = model_variant_id

        if self.llm_calls_total:
            self.llm_calls_total.add(1, attrs)

        if self.llm_tokens_total:
            if prompt_tokens > 0:
                self.llm_tokens_total.add(prompt_tokens, {**attrs, "type": "prompt"})
            if completion_tokens > 0:
                self.llm_tokens_total.add(completion_tokens, {**attrs, "type": "completion"})
        if self.llm_cost_usd is not None and cost_usd is not None:
            self.llm_cost_usd.record(max(0.0, float(cost_usd)), attrs)
        if self.llm_latency_ms is not None and latency_ms is not None:
            self.llm_latency_ms.record(max(0.0, float(latency_ms)), attrs)

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
        attributes: dict[str, Any] | None = None,
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
        error_type: str | None = None,
    ) -> None:
        """Record a validation issue."""
        self._ensure_initialized()
        if self.validation_issues_total is None:
            return
        attrs = {"severity": severity, "pass_id": pass_id}
        if error_type:
            attrs["error_type"] = error_type
        self.validation_issues_total.add(1, attrs)

    def record_degraded_path(
        self,
        *,
        component: str,
        operation: str,
        reason: str,
        error_type: str | None = None,
    ) -> None:
        """Record a degraded-but-recoverable execution path."""
        self._ensure_initialized()
        if self.degraded_paths_total is None:
            return
        attrs = {
            "component": component or "unknown",
            "operation": operation or "unknown",
            "reason": reason or "unknown",
        }
        if error_type:
            attrs["error_type"] = error_type
        self.degraded_paths_total.add(1, attrs)

    def record_scientist_trace_correlation(
        self,
        *,
        runner_backend: str,
        workflow_id: str,
        run_id: str,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """Record one trace-correlation handoff between Scientist runners/workers."""
        self._ensure_initialized()
        if self.scientist_trace_correlations_total is None:
            return
        attrs = {
            "runner_backend": runner_backend or "unknown",
            "workflow_id": workflow_id or "unknown",
            "run_id": run_id or "unknown",
            "trace_bound": str(bool(trace_id)).lower(),
            "span_bound": str(bool(span_id)).lower(),
        }
        self.scientist_trace_correlations_total.add(1, attrs)

    def record_scientist_operational_alert(
        self,
        *,
        alert_type: str,
        severity: str,
        workflow_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Record one Scientist operational alert for runtime monitoring."""
        self._ensure_initialized()
        if self.scientist_operational_alerts_total is None:
            return
        attrs = {
            "alert_type": alert_type or "unknown",
            "severity": severity or "warn",
            "workflow_id": workflow_id or "unknown",
            "run_id": run_id or "unknown",
        }
        self.scientist_operational_alerts_total.add(1, attrs)

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
        self.identity_failures_total.add(
            1,
            self._with_env({"reason": reason, "provider": provider}),
        )

    def record_runtime_api_request(
        self,
        *,
        route: str,
        method: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        self._ensure_initialized()
        attrs = self._with_env(
            {
                "route": route,
                "method": method.upper(),
                "status": status,
            }
        )
        if self.runtime_api_requests_total is not None:
            self.runtime_api_requests_total.add(1, attrs)
        if self.runtime_api_duration_seconds is not None:
            self.runtime_api_duration_seconds.record(max(duration_seconds, 0.0), attrs)
        try:
            status_code = int(status)
        except (TypeError, ValueError):
            status_code = 0
        if status_code >= 400 and self.runtime_api_errors_total is not None:
            self.runtime_api_errors_total.add(1, attrs)

    def record_runtime_data_access(
        self,
        *,
        resource_kind: str,
        endpoint: str,
        outcome: str,
        tenant_scoped: bool,
    ) -> None:
        self._ensure_initialized()
        if self.runtime_data_access_total is None:
            return
        attrs = self._with_env(
            {
                "resource_kind": resource_kind or "unknown",
                "endpoint": endpoint or "unknown",
                "outcome": outcome or "unknown",
                "tenant_scoped": str(bool(tenant_scoped)).lower(),
            }
        )
        self.runtime_data_access_total.add(1, attrs)

    def record_runtime_cache_event(
        self,
        *,
        cache_name: str,
        operation: str,
        outcome: str,
    ) -> None:
        self._ensure_initialized()
        if self.runtime_cache_operations_total is None:
            return
        attrs = self._with_env(
            {
                "cache_name": cache_name or "unknown",
                "operation": operation or "unknown",
                "outcome": outcome or "unknown",
            }
        )
        self.runtime_cache_operations_total.add(1, attrs)

    def record_runtime_cache_rebuild(
        self,
        *,
        cache_name: str,
        duration_seconds: float,
        item_count: int,
    ) -> None:
        self._ensure_initialized()
        attrs = self._with_env({"cache_name": cache_name or "unknown"})
        if self.runtime_cache_rebuild_duration_seconds is not None:
            self.runtime_cache_rebuild_duration_seconds.record(max(duration_seconds, 0.0), attrs)
        if self.runtime_cache_item_count is not None:
            self.runtime_cache_item_count.set(float(max(item_count, 0)), attrs)

    def set_runtime_cache_staleness(
        self,
        *,
        cache_name: str,
        staleness_seconds: float,
    ) -> None:
        self._ensure_initialized()
        if self.runtime_cache_staleness_seconds is None:
            return
        self.runtime_cache_staleness_seconds.set(
            max(float(staleness_seconds), 0.0),
            self._with_env({"cache_name": cache_name or "unknown"}),
        )

    def record_runtime_rate_limit_event(
        self,
        *,
        endpoint: str,
        mode: str,
        outcome: str,
    ) -> None:
        self._ensure_initialized()
        if self.runtime_rate_limit_events_total is None:
            return
        self.runtime_rate_limit_events_total.add(
            1,
            self._with_env(
                {
                    "endpoint": endpoint or "unknown",
                    "mode": mode or "unknown",
                    "outcome": outcome or "unknown",
                }
            ),
        )

    def set_runtime_live_streams(
        self,
        *,
        endpoint: str,
        active_streams: int,
    ) -> None:
        self._ensure_initialized()
        if self.runtime_live_streams_current is None:
            return
        self.runtime_live_streams_current.set(
            float(max(active_streams, 0)),
            self._with_env({"endpoint": endpoint or "unknown"}),
        )

    def record_control_plane_job_admission(
        self,
        *,
        job_kind: str,
        effective_profile: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        self._ensure_initialized()
        attrs = self._with_env(
            {
                "job_kind": job_kind,
                "effective_profile": effective_profile,
                "status": status,
            }
        )
        if self.control_plane_job_admissions_total is not None:
            self.control_plane_job_admissions_total.add(1, attrs)
        if self.control_plane_job_admission_duration_seconds is not None:
            self.control_plane_job_admission_duration_seconds.record(
                max(duration_seconds, 0.0),
                attrs,
            )

    def record_control_plane_job_execution(
        self,
        *,
        job_kind: str,
        status: str,
        duration_seconds: float,
        queue_lag_seconds: float,
    ) -> None:
        self._ensure_initialized()
        attrs = self._with_env(
            {
                "job_kind": job_kind or "unknown",
                "status": status or "unknown",
            }
        )
        if self.control_plane_job_executions_total is not None:
            self.control_plane_job_executions_total.add(1, attrs)
        if self.control_plane_job_execution_duration_seconds is not None:
            self.control_plane_job_execution_duration_seconds.record(
                max(duration_seconds, 0.0),
                attrs,
            )
        if self.control_plane_job_queue_lag_seconds is not None:
            self.control_plane_job_queue_lag_seconds.record(
                max(queue_lag_seconds, 0.0),
                self._with_env({"job_kind": job_kind or "unknown"}),
            )

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

    def record_artifact_integrity_failure(
        self,
        *,
        backend: str,
        reason: str,
    ) -> None:
        self._ensure_initialized()
        if self.artifact_integrity_failures_total is None:
            return
        self.artifact_integrity_failures_total.add(
            1,
            self._with_env(
                {
                    "backend": backend or "unknown",
                    "reason": reason or "unknown",
                }
            ),
        )


_metrics_registry: MetricsRegistryBase | None = None
_metrics_registry_lock = threading.Lock()


def get_metrics() -> MetricsRegistry:
    """Get the global MetricsRegistry instance."""
    global _metrics_registry
    current_instance = MetricsRegistry.current_instance()
    if (
        _metrics_registry is not None
        and current_instance is not None
        and _metrics_registry is current_instance
    ):
        return cast("MetricsRegistry", _metrics_registry)
    with _metrics_registry_lock:
        current_instance = MetricsRegistry.current_instance()
        if (
            _metrics_registry is None
            or current_instance is None
            or _metrics_registry is not current_instance
        ):
            _metrics_registry = MetricsRegistry()
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return cast("MetricsRegistry", _metrics_registry)


__all__ = [
    "GaugeProxy",
    "HistogramTimer",
    "MetricsRegistry",
    "get_metrics",
]
