"""Assemble redacted debug, governance, workflow, and evidence views for runs.

The service merges data from run manifests, CAS artifacts, trace timelines, and
decision-validity state. Sensitive keys are sanitized before DTOs cross the HTTP
boundary.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.execution_plan import (
    EvaluatorVerdict,
    IterationLifecycleState,
    StopReason,
)
from polisyos.core.contracts.runtime import (
    AgentPipelineAttempt,
    AgentPipelineStep,
    AgentPipelineView,
    EvaluatorReportView,
    EvaluatorScoresView,
    GovernanceDebugView,
    IterationLifecycleView,
    NodeDebugView,
    NodeStatus,
    PreflightDiagnosticView,
    PreflightReportView,
    ReproducibilityView,
    RetrievalPhaseTelemetry,
    RetrievalTelemetryView,
    RunErrorView,
    RunEvidenceContextView,
    RunEvidenceNeedView,
    RunEvidencePlanView,
    RunEvidencePromotionView,
    RunNodeRecord,
    RunWorkflowEdgeView,
    RunWorkflowNodeView,
    RunWorkflowSummary,
    RunWorkflowView,
)
from polisyos.core.trace.record import TraceRecord
from polisyos.scientist.decision_validity import DecisionValidityService

from .run_index import IndexedRunRecord
from .timeline import TimelineService

_GOVERNANCE_REPORT_KEY = "governance_report_ref"
_NORMATIVE_ARBITRATION_RESULT_KEY = "normative_arbitration_result_ref"
_REFLEXION_TERMINAL_KIND = "scientist.reflexion_terminal"
_WORKFLOW_SPEC_KIND = "scientist.workflow_spec"
_DEFAULT_SENSITIVE_KEYS = (
    "authorization",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "cookie",
)
_AGENT_ALIASES: dict[str, str] = {
    "pi": "pi_agent",
    "pi_agent": "pi_agent",
    "pi_decompose": "pi_agent",
    "problem_frame": "pi_agent",
    "data_need_extractor": "data_need_extractor",
    "source_resolver": "source_resolver",
    "executor": "executor",
    "promotion_lane": "promotion_lane",
    "drafter": "drafter",
    "draft": "drafter",
    "formalize": "formalizer",
    "formalizer": "formalizer",
    "critic": "critic",
    "critic_review": "critic",
    "reflexion": "reflexion",
}


logger = get_logger(__name__)

AgentStepStatus = Literal["ok", "warn", "fail", "info"]


class DebugService:
    """Expose read-only runtime debug projections for one indexed run."""
    def __init__(
        self,
        *,
        store: ArtifactStore,
        timeline_service: TimelineService,
        sensitive_keys: tuple[str, ...] = _DEFAULT_SENSITIVE_KEYS,
    ) -> None:
        self._store = store
        self._timeline_service = timeline_service
        self._decision_validity_service = DecisionValidityService(store)
        self._sensitive_keys = tuple(key.lower() for key in sensitive_keys)

    def list_run_nodes(self, run: IndexedRunRecord) -> list[RunNodeRecord]:
        """List workflow nodes by merging workflow-report rows with trace events."""
        timeline_events = self._timeline_service.build_for_run(run).timeline.events
        workflow_nodes = self._load_workflow_nodes(run.workflow_report_ref)
        if not workflow_nodes:
            return _nodes_from_timeline(timeline_events)
        return _merge_workflow_nodes_with_timeline(workflow_nodes, timeline_events)

    def get_node_debug(self, run: IndexedRunRecord, *, alias: str) -> NodeDebugView:
        """Return per-node timeline, cache, and artifact details.

        Raises:
            KeyError: If `alias` does not match any node in the run.
        """
        nodes = self.list_run_nodes(run)
        by_alias = {node.alias: node for node in nodes}
        record = by_alias.get(alias)
        if record is None:
            raise KeyError(alias)

        node_phase = f"scientist.node.{alias}"
        timeline = self._timeline_service.build_for_run(run).timeline.events
        node_events = [event for event in timeline if event.phase == node_phase]

        cache_hits = sum(int(event.metrics.get("cache_hit", 0)) for event in node_events)
        cache_stores = sum(int(event.metrics.get("cache_store", 0)) for event in node_events)
        cache_bypasses = sum(int(event.metrics.get("cache_bypass", 0)) for event in node_events)

        input_ids = sorted({aid for event in node_events for aid in event.input_artifact_ids})
        output_ids = sorted({aid for event in node_events for aid in event.output_artifact_ids})

        enriched_record = record.model_copy(
            update={
                "input_artifact_ids": (
                    record.input_artifact_ids if record.input_artifact_ids else input_ids
                ),
                "output_artifact_ids": (
                    record.output_artifact_ids if record.output_artifact_ids else output_ids
                ),
            }
        )

        return NodeDebugView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            alias=alias,
            record=enriched_record,
            timeline_events=node_events,
            cache_hits=cache_hits,
            cache_stores=cache_stores,
            cache_bypasses=cache_bypasses,
            notes=[],
        )

    def get_governance_debug(self, run: IndexedRunRecord) -> GovernanceDebugView:
        """Return governance verdict, issue summaries, and decision-validity state.

        When a governance report artifact is missing, the service falls back to
        the governance block embedded in the decision packet payload and marks
        that fallback in the response.
        """
        report_ref = None
        validation_trace = None
        fallback = False

        state_payload = self._load_experiment_state_payload(run.experiment_state_ref)
        if state_payload:
            validation_trace = _extract_validation_trace(state_payload)
            report_ref = _extract_report_ref(state_payload, _GOVERNANCE_REPORT_KEY)

        if report_ref is not None:
            report_payload = self._load_json_artifact(report_ref)
            verdict = _as_str(report_payload.get("verdict"))
            issues = _as_list_of_dicts(report_payload.get("issues"))
            notes = _as_list_of_strings(report_payload.get("notes"))
            links = _governance_links_from_payload(report_payload)
            report_manifest = self._load_manifest(report_ref)
            issue_summary = _summarize_issue_counts(issues)
            legal_executed = _legal_executed_from_governance(report_payload)
            packet_payload = self._load_json_artifact(run.decision_packet_ref)
            decision_validity = self._decision_validity_summary(
                run.decision_packet_ref,
                packet_payload,
            )
            return GovernanceDebugView(
                run_id=run.run_id,
                source_kind=run.source_kind,
                verdict=verdict,
                issues=issues,
                issue_summary=issue_summary,
                notes=notes,
                report_ref=report_ref,
                report_kind=report_manifest.kind if report_manifest is not None else None,
                report_schema_version=(
                    report_manifest.artifact_schema.version
                    if report_manifest is not None and report_manifest.artifact_schema is not None
                    else None
                ),
                links=links,
                legal_executed=legal_executed,
                transport_summary=_transport_summary_from_packet(packet_payload),
                validation_trace=validation_trace,
                contract_warnings=_contract_warnings_from_packet(packet_payload),
                decision_validity=decision_validity,
                normative_summary=_normative_summary_from_packet(packet_payload),
                normative_arbitration_result_ref=_artifact_ref_from_packet(
                    packet_payload,
                    _NORMATIVE_ARBITRATION_RESULT_KEY,
                ),
                fallback_from_decision_packet=False,
            )

        packet_payload = self._load_json_artifact(run.decision_packet_ref)
        decision_validity = self._decision_validity_summary(
            run.decision_packet_ref,
            packet_payload,
        )
        governance_block = packet_payload.get("governance")
        if isinstance(governance_block, dict):
            fallback = True
            verdict = _as_str(governance_block.get("verdict"))
            issues = _as_list_of_dicts(governance_block.get("issues"))
            notes = _as_list_of_strings(governance_block.get("notes"))
            links = _governance_links_from_payload(governance_block)
        else:
            verdict = None
            issues = []
            notes = []
            links = None

        return GovernanceDebugView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            verdict=verdict,
            issues=issues,
            issue_summary=_summarize_issue_counts(issues),
            notes=notes,
            report_ref=None,
            report_kind=None,
            report_schema_version=None,
            links=links,
            legal_executed=_legal_executed_from_packet(packet_payload),
            transport_summary=_transport_summary_from_packet(packet_payload),
            validation_trace=validation_trace,
            contract_warnings=_contract_warnings_from_packet(packet_payload),
            decision_validity=decision_validity,
            normative_summary=_normative_summary_from_packet(packet_payload),
            normative_arbitration_result_ref=_artifact_ref_from_packet(
                packet_payload,
                _NORMATIVE_ARBITRATION_RESULT_KEY,
            ),
            fallback_from_decision_packet=fallback,
        )

    def _decision_validity_summary(
        self,
        ref: ArtifactRef | None,
        packet_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if ref is None:
            return None
        return cast(
            "dict[str, Any] | None",
            self._decision_validity_service.get_summary(
                str(ref.artifact_id),
                packet_payload=packet_payload,
            ),
        )

    def get_run_errors(self, run: IndexedRunRecord) -> list[RunErrorView]:
        """Collect sanitized manifest, workflow, and trace errors for one run."""
        errors: list[RunErrorView] = []

        for item in run.manifest_errors:
            errors.append(
                RunErrorView(
                    source="manifest",
                    code=_as_str(item.get("code")) or "manifest.error",
                    message=(
                        _sanitize_string(_as_str(item.get("message")) or "Run manifest error")
                        or "Run manifest error"
                    ),
                    details=_sanitize_payload(dict(item), sensitive_keys=self._sensitive_keys),
                )
            )

        for node in self.list_run_nodes(run):
            if node.status != "fail":
                continue
            errors.append(
                RunErrorView(
                    source="workflow_report",
                    code=node.error_code or "node.failure",
                    message=(
                        _sanitize_string(node.error_message or "Node execution failed")
                        or "Node execution failed"
                    ),
                    node_alias=node.alias,
                    details=_sanitize_payload(
                        dict(node.error_details),
                        sensitive_keys=self._sensitive_keys,
                    ),
                )
            )

        if run.trace_path is not None and run.trace_path.exists():
            for record in _iter_trace_records(run.trace_path):
                for payload in record.errors:
                    errors.append(
                        RunErrorView(
                            source="trace",
                            code=_as_str(payload.get("code")) or "trace.error",
                            message=(
                                _sanitize_string(_as_str(payload.get("msg")) or "Trace error")
                                or "Trace error"
                            ),
                            timestamp=record.ts,
                            details=_sanitize_payload(
                                dict(payload),
                                sensitive_keys=self._sensitive_keys,
                            ),
                        )
                    )

        errors.sort(key=_error_sort_key)
        return errors

    def get_run_agents(self, run: IndexedRunRecord) -> AgentPipelineView:
        """Build the agent-pipeline view from decision packet, state, and trace data.

        The method prefers `decision_packet.audit_trail`, then timeline events,
        then reflexion-terminal payloads, and appends iteration/preflight/
        evaluator/reproducibility metadata when those artifacts are available.
        """
        notes: list[str] = []
        source: str | None = None

        state_payload = self._load_experiment_state_payload(run.experiment_state_ref)
        decision_packet_payload = self._load_json_artifact(run.decision_packet_ref)
        audit_trail_rows = _as_list_of_dicts(decision_packet_payload.get("audit_trail"))
        steps: list[AgentPipelineStep] = []
        if audit_trail_rows:
            steps.extend(
                _agent_steps_from_audit_trail(
                    audit_trail_rows,
                    sensitive_keys=self._sensitive_keys,
                )
            )
            source = "decision_packet.audit_trail"

        if not steps:
            timeline_rows = self._timeline_service.build_for_run(run).timeline.events
            timeline_steps = _agent_steps_from_timeline(
                timeline_rows,
                sensitive_keys=self._sensitive_keys,
            )
            if timeline_steps:
                steps.extend(timeline_steps)
                source = "trace.timeline"

        reflexion_ref = self._find_first_ref_by_kind(run, _REFLEXION_TERMINAL_KIND)
        reflexion_payload = self._load_json_artifact(reflexion_ref)
        reflexion_step = _agent_step_from_reflexion_payload(
            reflexion_payload,
            sensitive_keys=self._sensitive_keys,
        )
        if reflexion_step is not None:
            if not steps or not _contains_agent_step(steps, reflexion_step):
                steps.append(reflexion_step)
            if source is None:
                source = "reflexion_terminal"

        variant_steps = _agent_steps_from_model_variants(
            state_payload,
            sensitive_keys=self._sensitive_keys,
        )
        if variant_steps:
            for step in variant_steps:
                if not _contains_agent_step(steps, step):
                    steps.append(step)
            source = source or "experiment_state.params"
            if source != "experiment_state.params":
                source = f"{source}+experiment_state.params"

        attempts = _group_agent_steps_by_attempt(steps)
        if not attempts:
            notes.append("agent_pipeline_data_not_available")

        latest_verdict = (
            _latest_attempt_verdict(attempts)
            or _as_str(decision_packet_payload.get("verdict"))
            or _as_str(reflexion_payload.get("decision"))
        )
        retrieval = _retrieval_from_state_payload(state_payload)
        execution_plan_ref = _state_ref_from_param(
            state_payload,
            "execution_plan_ref",
            kind="scientist.execution_plan",
        )
        method_catalog_snapshot_ref = _state_ref_from_param(
            state_payload,
            "method_catalog_snapshot_ref",
            kind="foundry.method_catalog_snapshot",
        )
        preflight_report_ref = _state_ref_from_param(
            state_payload,
            "preflight_report_ref",
            kind="scientist.preflight_report",
        )
        evaluator_report_ref = _state_ref_from_param(
            state_payload,
            "evaluator_report_ref",
            kind="scientist.evaluator_report",
        )
        iteration_state_ref = _state_ref_from_param(
            state_payload,
            "iteration_state_ref",
            kind="scientist.iteration_state",
        )
        reproducibility_manifest_ref = _state_ref_from_param(
            state_payload,
            "reproducibility_manifest_ref",
            kind="scientist.reproducibility_manifest",
        )

        preflight_payload = self._load_json_artifact(preflight_report_ref)
        evaluator_payload = self._load_json_artifact(evaluator_report_ref)
        iteration_payload = self._load_json_artifact(iteration_state_ref)
        reproducibility_payload = self._load_json_artifact(reproducibility_manifest_ref)

        preflight_view = PreflightReportView(
            ready_to_run=bool(preflight_payload.get("ready_to_run")),
            diagnostics=[
                PreflightDiagnosticView.model_validate(item)
                for item in _as_list_of_dicts(preflight_payload.get("diagnostics"))
            ],
            notes=_as_list_of_strings(preflight_payload.get("notes")),
            report_ref=preflight_report_ref,
        ) if preflight_report_ref is not None else None

        evaluator_scores_raw = evaluator_payload.get("scores")
        evaluator_scores = (
            EvaluatorScoresView.model_validate(evaluator_scores_raw)
            if isinstance(evaluator_scores_raw, dict)
            else EvaluatorScoresView()
        )
        evaluator_view = EvaluatorReportView(
            verdict=_as_evaluator_verdict(evaluator_payload.get("verdict")),
            scores=evaluator_scores,
            reasons=_as_list_of_strings(evaluator_payload.get("reasons")),
            replanning_hints=_as_list_of_strings(evaluator_payload.get("replanning_hints")),
            diagnostics=[
                PreflightDiagnosticView.model_validate(item)
                for item in _as_list_of_dicts(evaluator_payload.get("diagnostics"))
            ],
            notes=_as_list_of_strings(evaluator_payload.get("notes")),
            report_ref=evaluator_report_ref,
        ) if evaluator_report_ref is not None else None

        iteration_view = IterationLifecycleView(
            iteration=max(1, _as_int(iteration_payload.get("iteration") or 1)),
            state=_as_iteration_lifecycle_state(iteration_payload.get("lifecycle_state")),
            stop_reason=_as_stop_reason(iteration_payload.get("stop_reason")),
            last_verdict=_as_evaluator_verdict(iteration_payload.get("last_verdict")),
            state_ref=iteration_state_ref,
            notes=_as_list_of_strings(iteration_payload.get("notes")),
        ) if iteration_state_ref is not None else None

        reproducibility_view = ReproducibilityView(
            seed=_as_int(reproducibility_payload.get("seed")),
            seed_source=_replay_value(decision_packet_payload, "seed_source"),
            determinism_tier=_replay_value(decision_packet_payload, "determinism_tier"),
            plan_hash=_as_str(reproducibility_payload.get("plan_hash")),
            registry_hash=_as_str(reproducibility_payload.get("registry_hash")),
            method_catalog_hash=_as_str(reproducibility_payload.get("method_catalog_hash")),
            data_snapshot_hash=_as_str(reproducibility_payload.get("data_snapshot_hash")),
            input_bindings_hash=_as_str(reproducibility_payload.get("input_bindings_hash")),
            readiness=_replay_value(decision_packet_payload, "readiness"),
            why_partial=_replay_list(decision_packet_payload, "why_partial"),
            missing_refs=_replay_list(decision_packet_payload, "missing_refs"),
            suggested_next_step=_replay_value(decision_packet_payload, "suggested_next_step"),
            manifest_ref=reproducibility_manifest_ref,
            notes=_as_list_of_strings(reproducibility_payload.get("notes")),
        ) if (reproducibility_manifest_ref is not None or _has_replay_payload(decision_packet_payload)) else None

        return AgentPipelineView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            total_attempts=len(attempts),
            latest_verdict=latest_verdict,
            attempts=attempts,
            decision_packet_ref=run.decision_packet_ref,
            reflexion_terminal_ref=reflexion_ref,
            retrieval=retrieval,
            execution_plan_ref=execution_plan_ref,
            method_catalog_snapshot_ref=method_catalog_snapshot_ref,
            preflight=preflight_view,
            evaluator=evaluator_view,
            iteration_lifecycle=iteration_view,
            reproducibility=reproducibility_view,
            source=source,
            notes=notes,
        )

    def get_run_evidence_context(self, run: IndexedRunRecord) -> RunEvidenceContextView:
        """Return data-needs, fetch-plan, promotion, and related-artifact context."""
        warnings: list[str] = []
        state_payload = self._load_experiment_state_payload(run.experiment_state_ref)
        decision_packet_payload = self._load_json_artifact(run.decision_packet_ref)
        params = state_payload.get("params")
        params_dict = params if isinstance(params, dict) else {}
        retrieval_context = params_dict.get("retrieval_context")
        retrieval_context_dict = retrieval_context if isinstance(retrieval_context, dict) else {}

        execution_plan_ref = (
            _state_ref_from_param(state_payload, "execution_plan_ref", kind="scientist.execution_plan")
            or _artifact_ref_from_string(
                _path_get_as_str(decision_packet_payload, ("artifacts", "execution_plan_ref")),
                kind="scientist.execution_plan",
            )
            or self._find_first_ref_by_kind(run, "scientist.execution_plan")
        )
        execution_plan_payload = self._load_json_artifact(execution_plan_ref)

        plan_needs_raw = execution_plan_payload.get("data_needs")
        context_needs_raw = retrieval_context_dict.get("data_needs")
        data_needs_rows = (
            _as_list_of_dicts(context_needs_raw)
            if isinstance(context_needs_raw, list)
            else _as_list_of_dicts(plan_needs_raw)
        )
        if execution_plan_ref is None:
            warnings.append("execution_plan_ref_missing")
        if not data_needs_rows:
            warnings.append("run_data_needs_missing")

        fetch_plans_rows = _as_list_of_dicts(retrieval_context_dict.get("fetch_plans"))
        if not fetch_plans_rows:
            warnings.append("run_fetch_plans_missing")

        promotion_rows = _as_list_of_dicts(retrieval_context_dict.get("promotion_candidates"))

        needs: list[RunEvidenceNeedView] = []
        needs_by_metric: dict[str, list[str]] = defaultdict(list)
        for row in data_needs_rows:
            need_id = _stable_id(
                "need",
                _as_str(row.get("metric")) or "",
                _as_str(row.get("geography")) or "",
                _as_str(row.get("time_start")) or "",
                _as_str(row.get("time_end")) or "",
                _as_str(row.get("granularity")) or "",
                _as_str(row.get("purpose")) or "",
            )
            metric = _as_str(row.get("metric")) or "unknown.metric"
            needs.append(
                RunEvidenceNeedView(
                    need_id=need_id,
                    metric=metric,
                    geography=_as_str(row.get("geography")),
                    time_start=_as_str(row.get("time_start")),
                    time_end=_as_str(row.get("time_end")),
                    granularity=_as_str(row.get("granularity")) or "annual",
                    quality_min=_as_float(row.get("quality_min"), default=0.6),
                    purpose=_as_str(row.get("purpose")) or "policy_drafting",
                    matched_plan_ids=[],
                    notes=_as_list_of_strings(row.get("notes")),
                )
            )
            needs_by_metric[metric].append(need_id)

        plans: list[RunEvidencePlanView] = []
        plan_ids: set[str] = set()
        plan_ids_by_metric: dict[str, list[str]] = defaultdict(list)
        for row in fetch_plans_rows:
            plan_id = _as_str(row.get("plan_id")) or _stable_id(
                "plan",
                _as_str(row.get("metric_id")) or "",
                _as_str(row.get("connector_id")) or "",
                _as_str(row.get("dataset_id")) or "",
            )
            metric_id = _as_str(row.get("metric_id")) or "unknown.metric"
            matched_need_ids = list(needs_by_metric.get(metric_id, []))
            plans.append(
                RunEvidencePlanView(
                    plan_id=plan_id,
                    metric_id=metric_id,
                    connector_id=_as_str(row.get("connector_id")) or "unknown.connector",
                    dataset_id=_as_str(row.get("dataset_id")) or "unknown.dataset",
                    profile_id=_as_str(row.get("profile_id")),
                    source_lane=_as_str(row.get("source_lane")) or "fastlane",
                    quality_min=_as_float(row.get("quality_min"), default=0.6),
                    filters=_string_list_dict(row.get("filters")),
                    date_start=_as_str(row.get("date_start")),
                    date_end=_as_str(row.get("date_end")),
                    granularity=_as_str(row.get("granularity")),
                    fallback_count=len(_as_list_of_dicts(row.get("fallbacks"))),
                    matched_need_ids=matched_need_ids,
                    notes=_as_list_of_strings(row.get("notes")),
                )
            )
            plan_ids.add(plan_id)
            plan_ids_by_metric[metric_id].append(plan_id)

        if plans:
            needs = [
                item.model_copy(update={"matched_plan_ids": plan_ids_by_metric.get(item.metric, [])})
                for item in needs
            ]

        promotions: list[RunEvidencePromotionView] = []
        for row in promotion_rows:
            metric_id = _as_str(row.get("metric_id")) or "unknown.metric"
            matched_plan_id = None
            candidate_plan_ids = plan_ids_by_metric.get(metric_id, [])
            if len(candidate_plan_ids) == 1:
                matched_plan_id = candidate_plan_ids[0]
            elif candidate_plan_ids:
                connector_id = _as_str(row.get("connector_id"))
                dataset_id = _as_str(row.get("dataset_id"))
                matched_plan_id = next(
                    (
                        plan.plan_id
                        for plan in plans
                        if plan.metric_id == metric_id
                        and plan.connector_id == connector_id
                        and plan.dataset_id == dataset_id
                    ),
                    None,
                )

            promotions.append(
                RunEvidencePromotionView(
                    promotion_id=_as_str(row.get("promotion_id")) or _stable_id(
                        "promotion",
                        metric_id,
                        _as_str(row.get("connector_id")) or "",
                        _as_str(row.get("dataset_id")) or "",
                    ),
                    metric_id=metric_id,
                    connector_id=_as_str(row.get("connector_id")) or "unknown.connector",
                    dataset_id=_as_str(row.get("dataset_id")) or "unknown.dataset",
                    profile_id=_as_str(row.get("profile_id")),
                    source_lane=_as_str(row.get("source_lane")) or "explorelane",
                    confidence=_as_float(row.get("confidence"), default=0.0),
                    status=_as_str(row.get("status")) or "pending",
                    created_at=_as_datetime(row.get("created_at")),
                    signals=_as_list_of_strings(row.get("signals")),
                    matched_plan_id=matched_plan_id,
                    metadata=_as_dict(row.get("metadata")),
                )
            )

        auto_refs = _as_dict(retrieval_context_dict.get("auto_data_source_refs"))
        packet_inputs = _as_dict(decision_packet_payload.get("inputs"))
        data_snapshot_ref = (
            self._find_run_input_ref_by_kind(run, "fabric.data_snapshot")
            or _artifact_ref_from_string(_as_str(auto_refs.get("data_snapshot_ref")), kind="fabric.data_snapshot")
            or _artifact_ref_from_string(_as_str(packet_inputs.get("data_snapshot_ref")), kind="fabric.data_snapshot")
        )
        input_bindings_ref = (
            self._find_run_input_ref_by_kind(run, "foundry.input_bindings")
            or _artifact_ref_from_string(_as_str(auto_refs.get("input_bindings_ref")), kind="foundry.input_bindings")
            or _artifact_ref_from_string(_as_str(packet_inputs.get("input_bindings_ref")), kind="foundry.input_bindings")
        )
        evidence_bundle_ref = (
            self._find_run_input_ref_by_kind(run, "fabric.evidence_bundle")
            or _artifact_ref_from_string(_as_str(auto_refs.get("evidence_bundle_ref")), kind="fabric.evidence_bundle")
            or _artifact_ref_from_string(_as_str(packet_inputs.get("evidence_bundle_ref")), kind="fabric.evidence_bundle")
        )

        related_artifacts = _dedupe_artifact_refs(
            [
                execution_plan_ref,
                data_snapshot_ref,
                input_bindings_ref,
                evidence_bundle_ref,
                _artifact_ref_from_string(
                    _path_get_as_str(decision_packet_payload, ("artifacts", "decision_card_ref")),
                    kind="scientist.decision_card",
                ),
                _artifact_ref_from_string(
                    _path_get_as_str(decision_packet_payload, ("artifacts", "input_binding_report_ref")),
                    kind="foundry.input_binding_report",
                ),
                *run.details.root_artifacts,
            ]
        )

        for plan in plans:
            if plan.matched_need_ids:
                continue
            warnings.append(f"unmatched_fetch_plan:{plan.plan_id}")
        for promotion in promotions:
            if promotion.matched_plan_id is None and plan_ids:
                warnings.append(f"unmatched_promotion_candidate:{promotion.promotion_id}")

        return RunEvidenceContextView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            execution_plan_ref=execution_plan_ref,
            evidence_bundle_ref=evidence_bundle_ref,
            data_snapshot_ref=data_snapshot_ref,
            input_bindings_ref=input_bindings_ref,
            related_artifacts=related_artifacts,
            data_needs=needs,
            fetch_plans=plans,
            promotion_candidates=promotions,
            warnings=_dedupe_strings(warnings),
        )

    def get_run_workflow(self, run: IndexedRunRecord) -> RunWorkflowView:
        """Return a DAG-like workflow projection with node depths, edges, and heat."""
        notes: list[str] = []
        timeline_events = self._timeline_service.build_for_run(run).timeline.events
        timeline_by_alias = {
            item.alias: item for item in _nodes_from_timeline(timeline_events) if item.alias
        }

        report_payload = self._load_json_artifact(run.workflow_report_ref)
        report_rows = _as_list_of_dicts(report_payload.get("nodes"))
        report_by_alias = _workflow_report_nodes_by_alias(report_rows)

        workflow_spec_ref = self._find_run_input_ref_by_kind(run, _WORKFLOW_SPEC_KIND)
        workflow_spec_payload = self._load_json_artifact(workflow_spec_ref)
        spec_rows = _as_list_of_dicts(workflow_spec_payload.get("nodes"))
        spec_by_alias, spec_order = _workflow_spec_nodes(spec_rows)
        if not spec_by_alias:
            notes.append("workflow_spec_missing_or_unavailable")

        aliases: list[str] = []
        aliases.extend(spec_order)
        for alias in report_by_alias:
            if alias not in aliases:
                aliases.append(alias)
        for alias in timeline_by_alias:
            if alias not in aliases:
                aliases.append(alias)

        nodes: list[RunWorkflowNodeView] = []
        for alias in aliases:
            spec_node = spec_by_alias.get(alias, {})
            report_node = report_by_alias.get(alias)
            timeline_node = timeline_by_alias.get(alias)

            depends_on = _as_list_of_strings(spec_node.get("depends_on"))
            node_id = _as_str(spec_node.get("node_id"))
            if report_node:
                node_id = node_id or _as_str(report_node.get("node_id"))

            status = _normalize_status(_as_str(report_node.get("status")) if report_node else None)
            if status == "unknown" and timeline_node is not None:
                status = timeline_node.status

            duration_ms = _as_int(report_node.get("duration_ms")) if report_node else 0
            if duration_ms <= 0 and timeline_node is not None:
                duration_ms = timeline_node.duration_ms

            report_artifacts = _artifact_ids_from_report_node(report_node)
            artifact_ids = sorted(
                set(report_artifacts).union(timeline_node.output_artifact_ids if timeline_node else [])
            )
            input_artifact_ids = timeline_node.input_artifact_ids if timeline_node else []
            output_artifact_ids = timeline_node.output_artifact_ids if timeline_node else []

            raw_error = report_node.get("error") if report_node else None
            error_payload = raw_error if isinstance(raw_error, dict) else {}

            nodes.append(
                RunWorkflowNodeView(
                    alias=alias,
                    node_id=node_id,
                    depends_on=depends_on,
                    depth=0,
                    status=status,
                    duration_ms=duration_ms,
                    error_code=_as_str(error_payload.get("code")),
                    error_message=_sanitize_string(_as_str(error_payload.get("message"))),
                    artifact_ids=artifact_ids,
                    input_artifact_ids=input_artifact_ids,
                    output_artifact_ids=output_artifact_ids,
                    heat=0.0,
                )
            )

        edges = _workflow_edges_from_nodes(nodes)
        depth_by_alias, cycle_detected = _workflow_depths(nodes)
        if cycle_detected:
            notes.append("workflow_cycle_detected")

        max_duration = max((node.duration_ms for node in nodes), default=0)
        enriched_nodes: list[RunWorkflowNodeView] = []
        for node in nodes:
            depth = depth_by_alias.get(node.alias, 0)
            heat = float(node.duration_ms) / float(max_duration) if max_duration > 0 else 0.0
            enriched_nodes.append(
                node.model_copy(
                    update={
                        "depth": depth,
                        "heat": round(heat, 3),
                    }
                )
            )
        enriched_nodes.sort(key=lambda item: (item.depth, item.alias))

        status_counts: defaultdict[str, int] = defaultdict(int)
        for node in enriched_nodes:
            status_counts[node.status] += 1
        critical_path = _critical_path_duration_ms(enriched_nodes)

        summary = RunWorkflowSummary(
            workflow_id=(
                _as_str(workflow_spec_payload.get("workflow_id"))
                or _as_str(report_payload.get("workflow_id"))
            ),
            error_policy=(
                _as_str(workflow_spec_payload.get("error_policy"))
                or _as_str(report_payload.get("error_policy"))
            ),
            status=_as_str(report_payload.get("status")),
            node_count=len(enriched_nodes),
            edge_count=len(edges),
            ok_count=status_counts.get("ok", 0),
            skip_count=status_counts.get("skip", 0),
            fail_count=status_counts.get("fail", 0),
            max_depth=max((node.depth for node in enriched_nodes), default=0),
            critical_path_duration_ms=critical_path,
        )

        return RunWorkflowView(
            run_id=run.run_id,
            source_kind=run.source_kind,
            summary=summary,
            nodes=enriched_nodes,
            edges=edges,
            workflow_spec_ref=workflow_spec_ref,
            workflow_report_ref=run.workflow_report_ref,
            notes=notes,
        )

    def _load_workflow_nodes(self, workflow_report_ref: ArtifactRef | None) -> list[RunNodeRecord]:
        payload = self._load_json_artifact(workflow_report_ref)
        rows = payload.get("nodes")
        if not isinstance(rows, list):
            return []

        result: list[RunNodeRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            artifacts = row.get("artifacts")
            artifact_ids: list[str] = []
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if not isinstance(artifact, dict):
                        continue
                    artifact_id = _as_str(artifact.get("artifact_id"))
                    if artifact_id:
                        artifact_ids.append(artifact_id)

            raw_error = row.get("error")
            error_payload = raw_error if isinstance(raw_error, dict) else {}
            record = RunNodeRecord(
                alias=_as_str(row.get("alias")) or "",
                node_id=_as_str(row.get("node_id")),
                status=_normalize_status(_as_str(row.get("status"))),
                duration_ms=_as_int(row.get("duration_ms")),
                error_code=_as_str(error_payload.get("code")),
                error_message=_sanitize_string(_as_str(error_payload.get("message"))),
                error_details=_sanitize_payload(
                    error_payload.get("details")
                    if isinstance(error_payload.get("details"), dict)
                    else {},
                    sensitive_keys=self._sensitive_keys,
                ),
                skip_reason=_as_str(row.get("skip_reason")),
                artifact_ids=sorted(set(artifact_ids)),
            )
            if record.alias:
                result.append(record)
        result.sort(key=lambda item: item.alias)
        return result

    def _load_experiment_state_payload(self, ref: ArtifactRef | None) -> dict[str, Any]:
        return self._load_json_artifact(ref)

    def _load_json_artifact(self, ref: ArtifactRef | None) -> dict[str, Any]:
        if ref is None:
            return {}
        try:
            payload = from_canonical_bytes(self._store.get_bytes(ref.artifact_id))
        except (FileNotFoundError, OSError, TypeError, ValueError, UnicodeDecodeError) as exc:
            logger.debug("Failed to load JSON artifact %s: %s", ref.artifact_id, exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    def _load_manifest(self, ref: ArtifactRef | None) -> Any:
        if ref is None:
            return None
        try:
            return self._store.get_manifest(ref.artifact_id)
        except (FileNotFoundError, OSError, ValidationError, TypeError, ValueError) as exc:
            logger.debug("Failed to load manifest %s: %s", ref.artifact_id, exc)
            return None

    def _load_run_manifest_payload(self, run: IndexedRunRecord) -> dict[str, Any]:
        return self._load_json_artifact(run.details.manifest_ref)

    def _find_first_ref_by_kind(self, run: IndexedRunRecord, kind: str) -> ArtifactRef | None:
        for ref in run.details.root_artifacts:
            if ref.kind == kind:
                return ref
        manifest_payload = self._load_run_manifest_payload(run)
        for raw in _as_list_of_dicts(manifest_payload.get("outputs")):
            parsed_ref = _artifact_ref_from_payload(raw)
            if parsed_ref is not None and parsed_ref.kind == kind:
                return parsed_ref
        return None

    def _find_run_input_ref_by_kind(self, run: IndexedRunRecord, kind: str) -> ArtifactRef | None:
        manifest_payload = self._load_run_manifest_payload(run)
        for raw in _as_list_of_dicts(manifest_payload.get("inputs")):
            ref = _artifact_ref_from_payload(raw)
            if ref is not None and ref.kind == kind:
                return ref
        return None


def _nodes_from_timeline(events: list[Any]) -> list[RunNodeRecord]:
    grouped: dict[str, RunNodeRecord] = {}
    for event in events:
        if not event.phase.startswith("scientist.node."):
            continue
        alias = event.phase[len("scientist.node.") :]
        if not alias:
            continue
        existing = grouped.get(alias)
        if existing is None:
            existing = RunNodeRecord(alias=alias)
        status = existing.status
        if event.event == "NODE_OK":
            status = "ok"
        elif event.event == "NODE_SKIP":
            status = "skip"
        elif event.event == "NODE_FAIL":
            status = "fail"

        duration_ms = max(existing.duration_ms, _as_int(event.metrics.get("duration_ms")))
        grouped[alias] = existing.model_copy(
            update={
                "status": status,
                "duration_ms": duration_ms,
                "output_artifact_ids": sorted(
                    set(existing.output_artifact_ids).union(event.output_artifact_ids)
                ),
                "input_artifact_ids": sorted(
                    set(existing.input_artifact_ids).union(event.input_artifact_ids)
                ),
            }
        )
    return [grouped[key] for key in sorted(grouped)]


def _state_ref_from_param(
    state_payload: dict[str, Any],
    key: str,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef | None:
    params = state_payload.get("params")
    value = params.get(key) if isinstance(params, dict) else None
    if value is None:
        value = state_payload.get(key)
    if isinstance(value, dict):
        return _artifact_ref_from_payload(value)
    return _artifact_ref_from_string(value if isinstance(value, str) else None, kind=kind, media_type=media_type)


def _workflow_report_nodes_by_alias(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        alias = _as_str(row.get("alias"))
        if alias:
            result[alias] = row
    return result


def _workflow_spec_nodes(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    by_alias: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        alias = _as_str(row.get("alias"))
        if not alias:
            continue
        by_alias[alias] = row
        order.append(alias)
    return by_alias, order


def _artifact_ids_from_report_node(row: dict[str, Any] | None) -> list[str]:
    if row is None:
        return []
    ids: list[str] = []
    for raw_ref in _as_list_of_dicts(row.get("artifacts")):
        artifact_id = _as_str(raw_ref.get("artifact_id"))
        if artifact_id:
            ids.append(artifact_id)
    return sorted(set(ids))


def _workflow_edges_from_nodes(nodes: list[RunWorkflowNodeView]) -> list[RunWorkflowEdgeView]:
    seen: set[tuple[str, str]] = set()
    edges: list[RunWorkflowEdgeView] = []
    aliases = {node.alias for node in nodes}
    for node in nodes:
        for parent in node.depends_on:
            if parent not in aliases:
                continue
            pair = (parent, node.alias)
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(RunWorkflowEdgeView(from_alias=parent, to_alias=node.alias))
    edges.sort(key=lambda item: (item.from_alias, item.to_alias))
    return edges


def _workflow_depths(nodes: list[RunWorkflowNodeView]) -> tuple[dict[str, int], bool]:
    deps = {node.alias: list(node.depends_on) for node in nodes}
    cache: dict[str, int] = {}
    visiting: set[str] = set()
    cycle_detected = False

    def _depth(alias: str) -> int:
        nonlocal cycle_detected
        if alias in cache:
            return cache[alias]
        if alias in visiting:
            cycle_detected = True
            return 0
        visiting.add(alias)
        parents = deps.get(alias) or []
        if not parents:
            value = 0
        else:
            value = 1 + max((_depth(parent) for parent in parents), default=0)
        visiting.discard(alias)
        cache[alias] = max(value, 0)
        return cache[alias]

    for alias in deps:
        _depth(alias)
    return cache, cycle_detected


def _critical_path_duration_ms(nodes: list[RunWorkflowNodeView]) -> int | None:
    if not nodes:
        return None
    node_by_alias = {node.alias: node for node in nodes}
    deps = {node.alias: list(node.depends_on) for node in nodes}
    cache: dict[str, int] = {}
    visiting: set[str] = set()

    def _duration(alias: str) -> int:
        if alias in cache:
            return cache[alias]
        if alias in visiting:
            return 0
        visiting.add(alias)
        node = node_by_alias.get(alias)
        own = node.duration_ms if node is not None else 0
        parents = deps.get(alias) or []
        if not parents:
            total = own
        else:
            total = own + max((_duration(parent) for parent in parents), default=0)
        visiting.discard(alias)
        cache[alias] = max(total, 0)
        return cache[alias]

    durations = [_duration(alias) for alias in deps]
    return max(durations, default=0)


def _retrieval_from_state_payload(payload: dict[str, Any]) -> RetrievalTelemetryView | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None

    telemetry_raw = params.get("retrieval_telemetry")
    telemetry = telemetry_raw if isinstance(telemetry_raw, dict) else {}

    mode = _as_str(telemetry.get("mode")) or _as_str(params.get("retrieval_mode"))
    lane_used = _as_str(telemetry.get("lane_used")) or _as_str(
        params.get("retrieval_lane_used")
    )
    if mode is None and lane_used is None and not telemetry:
        return None

    phases: list[RetrievalPhaseTelemetry] = []
    raw_phases = telemetry.get("phases")
    if isinstance(raw_phases, list):
        for row in raw_phases:
            if not isinstance(row, dict):
                continue
            phases.append(
                RetrievalPhaseTelemetry(
                    phase=_as_str(row.get("phase")) or "unknown",
                    lane=_as_str(row.get("lane")),
                    duration_ms=max(0, _as_int(row.get("duration_ms"))),
                    candidates_total=max(0, _as_int(row.get("candidates_total"))),
                    candidates_selected=max(0, _as_int(row.get("candidates_selected"))),
                    docs_fetched=max(0, _as_int(row.get("docs_fetched"))),
                )
            )
    if not phases:
        durations = params.get("retrieval_phase_durations")
        if isinstance(durations, dict):
            for phase_name, duration in durations.items():
                phases.append(
                    RetrievalPhaseTelemetry(
                        phase=str(phase_name),
                        lane=None,
                        duration_ms=max(0, _as_int(duration)),
                        candidates_total=0,
                        candidates_selected=0,
                        docs_fetched=0,
                    )
                )

    notes = _as_list_of_strings(telemetry.get("warnings"))
    return RetrievalTelemetryView(
        mode=mode or "hybrid",
        lane_used=lane_used or "none",
        metadata_docs_fetched=max(
            0,
            _as_int(
                telemetry.get("metadata_docs_fetched")
                if telemetry
                else params.get("retrieval_metadata_docs_fetched")
            ),
        ),
        local_index_size_bytes=max(
            0,
            _as_int(
                telemetry.get("local_index_size_bytes")
                if telemetry
                else params.get("retrieval_local_index_size_bytes")
            ),
        ),
        local_index_docs_total=max(
            0,
            _as_int(
                telemetry.get("local_index_docs_total")
                if telemetry
                else params.get("retrieval_local_index_docs_total")
            ),
        ),
        candidates_filtered=max(
            0,
            _as_int(
                telemetry.get("candidates_filtered")
                if telemetry
                else params.get("retrieval_candidates_filtered")
            ),
        ),
        candidates_promoted=max(
            0,
            _as_int(
                telemetry.get("candidates_promoted")
                if telemetry
                else params.get("retrieval_candidates_promoted")
            ),
        ),
        phases=phases,
        notes=notes,
    )


def _normalize_agent(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return _AGENT_ALIASES.get(normalized, normalized)


def _status_from_agent_action(
    *,
    action: str | None,
    details: dict[str, Any],
    fallback: AgentStepStatus = "info",
) -> AgentStepStatus:
    lowered_action = (action or "").lower()
    verdict = (_as_str(details.get("verdict")) or "").lower()
    if any(token in lowered_action for token in ("fail", "error", "reject", "abort")):
        return "fail"
    if any(token in lowered_action for token in ("warn", "retry", "revise")):
        return "warn"
    if any(token in lowered_action for token in ("ok", "approve", "success", "done")):
        return "ok"
    if verdict in {"reject", "needs_revision", "abort_with_report"}:
        return "fail"
    if verdict in {"approve", "approved", "pass"}:
        return "ok"
    return fallback


def _extract_attempt(value: Any, *, fallback: int) -> int:
    parsed = _as_int(value)
    if parsed <= 0:
        return fallback
    return parsed


def _agent_steps_from_audit_trail(
    rows: list[dict[str, Any]],
    *,
    sensitive_keys: tuple[str, ...],
) -> list[AgentPipelineStep]:
    steps: list[AgentPipelineStep] = []
    current_attempt = 1
    for row in rows:
        node = _normalize_agent(_as_str(row.get("node")))
        action = _as_str(row.get("action"))
        if node is None or action is None or node == "runtime":
            continue
        details = row.get("details")
        detail_payload = details if isinstance(details, dict) else {}
        attempt = _extract_attempt(detail_payload.get("attempt"), fallback=current_attempt)

        if node == "reflexion":
            can_retry = bool(detail_payload.get("can_retry"))
            if can_retry:
                current_attempt = attempt + 1
            else:
                current_attempt = max(current_attempt, attempt)
        else:
            current_attempt = max(current_attempt, attempt)

        steps.append(
            AgentPipelineStep(
                attempt=attempt,
                agent=node,
                action=action,
                status=_status_from_agent_action(action=action, details=detail_payload),
                timestamp=_as_datetime(row.get("timestamp")),
                summary=(
                    _as_str(detail_payload.get("summary"))
                    or _as_str(detail_payload.get("message"))
                    or _as_str(detail_payload.get("verdict"))
                ),
                details=_sanitize_payload(detail_payload, sensitive_keys=sensitive_keys),
                prompt=_as_str(detail_payload.get("system_prompt"))
                or _as_str(detail_payload.get("prompt")),
                response=_as_str(detail_payload.get("response"))
                or _as_str(detail_payload.get("raw_response")),
                model=_as_str(detail_payload.get("model")),
                provider=_as_str(detail_payload.get("provider")),
                model_variant_id=_as_str(detail_payload.get("model_variant_id")),
                latency_ms=_as_int_or_none(detail_payload.get("latency_ms")),
                cost_usd=_as_float_or_none(detail_payload.get("cost_usd")),
                token_usage=_token_usage(detail_payload.get("token_usage")),
            )
        )
    return steps


def _agent_steps_from_timeline(
    events: list[Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> list[AgentPipelineStep]:
    steps: list[AgentPipelineStep] = []
    for event in events:
        phase = _as_str(getattr(event, "phase", None))
        if phase is None:
            continue
        agent = _normalize_agent(_agent_from_phase(phase))
        if agent is None:
            continue
        action = _as_str(getattr(event, "event", None))
        if action is None:
            continue
        metrics = event.metrics if isinstance(event.metrics, dict) else {}
        attempt = _extract_attempt(metrics.get("attempt"), fallback=1)
        details = _sanitize_payload(metrics, sensitive_keys=sensitive_keys)
        steps.append(
            AgentPipelineStep(
                attempt=attempt,
                agent=agent,
                action=action,
                status=_status_from_agent_action(action=action, details=metrics),
                timestamp=getattr(event, "timestamp", None),
                summary=_as_str(metrics.get("summary")) or _as_str(metrics.get("verdict")),
                details=details if isinstance(details, dict) else {},
                model=_as_str(metrics.get("model")),
                provider=_as_str(metrics.get("provider")),
                model_variant_id=_as_str(metrics.get("model_variant_id")),
                latency_ms=_as_int_or_none(metrics.get("latency_ms"))
                or _as_int_or_none(metrics.get("duration_ms")),
                cost_usd=_as_float_or_none(metrics.get("cost_usd")),
                token_usage=_token_usage(metrics.get("token_usage")),
            )
        )
    return steps


def _agent_steps_from_model_variants(
    payload: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> list[AgentPipelineStep]:
    params = payload.get("params")
    if not isinstance(params, dict):
        return []
    raw_variants = params.get("llm_model_variants")
    if not isinstance(raw_variants, list):
        return []

    steps: list[AgentPipelineStep] = []
    for index, raw_variant in enumerate(raw_variants):
        if not isinstance(raw_variant, dict):
            continue
        attempt = max(index + 1, 1)
        variant_model = _as_str(raw_variant.get("model"))
        variant_provider = _as_str(raw_variant.get("provider"))
        variant_id = _as_str(raw_variant.get("model_variant_id"))
        variant_status = _as_str(raw_variant.get("status")) or "unknown"
        variant_verdict = _as_str(raw_variant.get("verdict"))
        variant_cost = _as_float_or_none(raw_variant.get("cost_usd"))
        token_usage = _token_usage(
            {
                "prompt_tokens": raw_variant.get("prompt_tokens"),
                "completion_tokens": raw_variant.get("completion_tokens"),
                "total_tokens": raw_variant.get("total_tokens"),
            }
        )
        timestamp = _as_datetime(raw_variant.get("finished_at"))
        if timestamp is None:
            timestamp = _as_datetime(raw_variant.get("started_at"))

        nested_steps = raw_variant.get("steps")
        if isinstance(nested_steps, list) and nested_steps:
            for nested in nested_steps:
                if not isinstance(nested, dict):
                    continue
                nested_usage = _token_usage(nested.get("token_usage"))
                nested_prompt = _as_str(nested.get("prompt"))
                nested_response = _as_str(nested.get("response"))
                nested_details = _sanitize_payload(nested.get("details"), sensitive_keys=sensitive_keys)
                raw_status = _as_str(nested.get("status"))
                nested_status = _agent_step_status(
                    raw_status,
                    fallback=_status_from_agent_action(
                        action=_as_str(nested.get("action")),
                        details=nested if isinstance(nested, dict) else {},
                    ),
                )
                steps.append(
                    AgentPipelineStep(
                        attempt=attempt,
                        agent=_normalize_agent(_as_str(nested.get("agent")) or "model_variant")
                        or "model_variant",
                        action=_as_str(nested.get("action")) or "step",
                        status=nested_status,
                        timestamp=_as_datetime(nested.get("timestamp")) or timestamp,
                        summary=_as_str(nested.get("summary")),
                        details=nested_details if isinstance(nested_details, dict) else {},
                        prompt=nested_prompt,
                        response=nested_response,
                        model=_as_str(nested.get("model")) or variant_model,
                        provider=_as_str(nested.get("provider")) or variant_provider,
                        model_variant_id=_as_str(nested.get("model_variant_id")) or variant_id,
                        latency_ms=_as_int_or_none(nested.get("latency_ms")),
                        cost_usd=_as_float_or_none(nested.get("cost_usd")),
                        token_usage=nested_usage,
                    )
                )
            continue

        details = _sanitize_payload(raw_variant, sensitive_keys=sensitive_keys)
        summary_status_map: dict[str, AgentStepStatus] = {
            "completed": "ok",
            "fallback_mock": "warn",
            "budget_exceeded": "warn",
            "failed": "fail",
            "skipped_budget_guard": "warn",
        }
        summary_status = summary_status_map.get(variant_status, "info")
        steps.append(
            AgentPipelineStep(
                attempt=attempt,
                agent="model_variant",
                action=variant_status,
                status=summary_status,
                timestamp=timestamp,
                summary=variant_verdict or variant_status,
                details=details if isinstance(details, dict) else {},
                model=variant_model,
                provider=variant_provider,
                model_variant_id=variant_id,
                latency_ms=_as_int_or_none(raw_variant.get("latency_ms")),
                cost_usd=variant_cost,
                token_usage=token_usage,
            )
        )
    return steps


def _agent_from_phase(phase: str) -> str | None:
    normalized = phase.strip().lower()
    if normalized.startswith("scientist.node."):
        return None
    if normalized.startswith("scientist.agent."):
        return normalized.split(".", 2)[-1]
    for marker in _AGENT_ALIASES:
        if marker in normalized:
            return marker
    return None


def _agent_step_from_reflexion_payload(
    payload: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...],
) -> AgentPipelineStep | None:
    if not payload:
        return None
    decision = _as_str(payload.get("decision"))
    card = payload.get("card")
    card_payload = card if isinstance(card, dict) else {}
    attempt = _extract_attempt(card_payload.get("attempt_number"), fallback=1)
    details: dict[str, Any] = {}
    if card_payload:
        details["card"] = card_payload
    if payload.get("failure_history") is not None:
        details["failure_history"] = payload.get("failure_history")
    if not decision and not details:
        return None
    sanitized = _sanitize_payload(details, sensitive_keys=sensitive_keys)
    detail_payload = sanitized if isinstance(sanitized, dict) else {}
    return AgentPipelineStep(
        attempt=attempt,
        agent="reflexion",
        action=decision or "decision",
        status=_status_from_agent_action(action=decision, details=card_payload),
        timestamp=_as_datetime(card_payload.get("created_at")),
        summary=_as_str(card_payload.get("violation_summary")) or decision,
        details=detail_payload,
        model=_as_str(card_payload.get("model")),
        provider=_as_str(card_payload.get("provider")),
        model_variant_id=_as_str(card_payload.get("model_variant_id")),
        latency_ms=_as_int_or_none(card_payload.get("duration_ms")),
        cost_usd=_as_float_or_none(card_payload.get("cost_usd")),
        token_usage=_token_usage(card_payload.get("token_usage")),
    )


def _contains_agent_step(existing: list[AgentPipelineStep], target: AgentPipelineStep) -> bool:
    for step in existing:
        if (
            step.attempt == target.attempt
            and step.agent == target.agent
            and step.action == target.action
            and step.timestamp == target.timestamp
        ):
            return True
    return False


def _group_agent_steps_by_attempt(steps: list[AgentPipelineStep]) -> list[AgentPipelineAttempt]:
    grouped: dict[int, list[AgentPipelineStep]] = defaultdict(list)
    for step in steps:
        grouped[max(step.attempt, 1)].append(step)

    attempts: list[AgentPipelineAttempt] = []
    for attempt in sorted(grouped):
        items = sorted(
            grouped[attempt],
            key=lambda item: item.timestamp or datetime.max,
        )
        started = next((item.timestamp for item in items if isinstance(item.timestamp, datetime)), None)
        finished = next(
            (item.timestamp for item in reversed(items) if isinstance(item.timestamp, datetime)),
            None,
        )
        duration_ms = None
        if isinstance(started, datetime) and isinstance(finished, datetime):
            duration_ms = max(int((finished - started).total_seconds() * 1000), 0)

        verdict = None
        for item in reversed(items):
            if item.agent == "critic":
                verdict = item.summary or item.action
                if verdict:
                    break
            if item.agent == "reflexion":
                verdict = item.action
                if verdict:
                    break

        status = "running"
        if any(item.status == "fail" for item in items):
            status = "failed"
        elif any(item.agent == "reflexion" and "retry" in item.action.lower() for item in items):
            status = "retry"
        elif any(item.status == "ok" for item in items):
            status = "completed"

        attempts.append(
            AgentPipelineAttempt(
                attempt=attempt,
                status=status,
                verdict=verdict,
                started_at=started,
                finished_at=finished,
                duration_ms=duration_ms,
                steps=items,
                notes=[],
            )
        )
    return attempts


def _latest_attempt_verdict(attempts: list[AgentPipelineAttempt]) -> str | None:
    if not attempts:
        return None
    for attempt in reversed(attempts):
        if attempt.verdict:
            return attempt.verdict
    return None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _as_int_or_none(value: Any) -> int | None:
    parsed = _as_int(value)
    return parsed if parsed > 0 else None


def _as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return max(parsed, 0.0)


def _token_usage(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        prompt = _as_int(value.get("prompt_tokens"))
        completion = _as_int(value.get("completion_tokens"))
        total = _as_int(value.get("total_tokens"))
        out: dict[str, int] = {}
        if prompt > 0:
            out["prompt_tokens"] = prompt
        if completion > 0:
            out["completion_tokens"] = completion
        if total > 0:
            out["total_tokens"] = total
        return out

    if isinstance(value, (int, float)):
        total = _as_int(value)
        return {"total_tokens": total} if total > 0 else {}
    return {}


def _merge_workflow_nodes_with_timeline(
    nodes: list[RunNodeRecord], timeline_events: list[Any]
) -> list[RunNodeRecord]:
    from_timeline = {node.alias: node for node in _nodes_from_timeline(timeline_events)}
    merged: list[RunNodeRecord] = []
    for node in nodes:
        timeline_node = from_timeline.get(node.alias)
        if timeline_node is None:
            merged.append(node)
            continue
        merged.append(
            node.model_copy(
                update={
                    "input_artifact_ids": (
                        node.input_artifact_ids
                        if node.input_artifact_ids
                        else timeline_node.input_artifact_ids
                    ),
                    "output_artifact_ids": (
                        node.output_artifact_ids
                        if node.output_artifact_ids
                        else timeline_node.output_artifact_ids
                    ),
                    "artifact_ids": sorted(
                        set(node.artifact_ids).union(timeline_node.output_artifact_ids)
                    ),
                }
            )
        )
    merged.sort(key=lambda item: item.alias)
    return merged


def _extract_validation_trace(payload: dict[str, Any]) -> dict[str, Any] | None:
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    trace = params.get("validation_trace")
    return trace if isinstance(trace, dict) else None


def _extract_report_ref(payload: dict[str, Any], key: str) -> ArtifactRef | None:
    reports_index = payload.get("reports_index")
    if not isinstance(reports_index, dict):
        return None
    raw_ref = reports_index.get(key)
    if not isinstance(raw_ref, dict):
        return None
    try:
        parsed_ref: ArtifactRef = ArtifactRef.model_validate(raw_ref)
        return parsed_ref
    except (TypeError, ValueError) as exc:
        logger.debug("Failed to parse report ref for key %s: %s", key, exc)
        return None


def _iter_trace_records(path: Path) -> Iterator[TraceRecord]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield TraceRecord.model_validate_json(stripped)
            except (ValueError, TypeError) as exc:
                logger.debug("Failed to parse trace record in %s: %s", path, exc)
                continue


def _error_sort_key(error: RunErrorView) -> tuple[float, str, str]:
    if isinstance(error.timestamp, datetime):
        return (error.timestamp.timestamp(), error.source, error.code)
    return (float("inf"), error.source, error.code)


def _normalize_status(raw: str | None) -> NodeStatus:
    if raw in {"ok", "skip", "fail", "unknown"}:
        return cast("NodeStatus", raw)
    return "unknown"


def _as_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_float(value: Any, *, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0.0)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _artifact_ref_from_string(
    value: str | None,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef | None:
    artifact_id = _artifact_id_from_string(value)
    if artifact_id is None:
        return None
    return ArtifactRef(artifact_id=artifact_id, kind=kind, media_type=media_type)


def _path_get_as_str(payload: dict[str, Any], path: tuple[str, ...]) -> str | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _as_str(current)


def _string_list_dict(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, raw in value.items():
        items = _as_list_of_strings(raw)
        if items:
            result[str(key)] = items
    return result


def _dedupe_artifact_refs(refs: list[ArtifactRef | None]) -> list[ArtifactRef]:
    result: list[ArtifactRef] = []
    seen: set[str] = set()
    for ref in refs:
        if ref is None:
            continue
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        result.append(ref)
    return result


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _summarize_issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    blocker_count = 0
    warning_count = 0
    info_count = 0
    for issue in issues:
        severity = (_as_str(issue.get("severity")) or "").lower()
        if severity == "blocker":
            blocker_count += 1
        elif severity == "warning":
            warning_count += 1
        elif severity == "info":
            info_count += 1
    return {
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "info_count": info_count,
    }


def _legal_executed_from_governance(payload: dict[str, Any]) -> bool | None:
    links = payload.get("links")
    if not isinstance(links, dict):
        return None
    legal_ref = links.get("legal_report_ref")
    if isinstance(legal_ref, dict):
        return _as_str(legal_ref.get("artifact_id")) is not None
    return isinstance(legal_ref, str)


def _legal_executed_from_packet(payload: dict[str, Any]) -> bool | None:
    diagnostics = payload.get("diagnostics_summary")
    if isinstance(diagnostics, dict) and isinstance(diagnostics.get("legal_executed"), bool):
        return bool(diagnostics.get("legal_executed"))
    return None


def _contract_warnings_from_packet(payload: dict[str, Any]) -> list[str]:
    diagnostics = payload.get("diagnostics_summary")
    if not isinstance(diagnostics, dict):
        return []
    return _as_list_of_strings(diagnostics.get("contract_warnings"))


def _normative_summary_from_packet(payload: dict[str, Any]) -> dict[str, Any] | None:
    diagnostics = payload.get("diagnostics_summary")
    tradeoff = payload.get("tradeoff_certificate")
    if not isinstance(diagnostics, dict) and not isinstance(tradeoff, dict):
        return None
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    tradeoff = tradeoff if isinstance(tradeoff, dict) else {}
    return {
        "selected_policy": diagnostics.get("normative_selected_policy")
        or tradeoff.get("selected_policy"),
        "selected_option": diagnostics.get("normative_selected_option")
        or tradeoff.get("selected_option"),
        "model_completeness": diagnostics.get("normative_model_completeness"),
        "residual_dissent_count": diagnostics.get("normative_residual_dissent_count"),
        "rights_violation_count": diagnostics.get("normative_rights_violation_count"),
        "winners": _as_list_of_strings(tradeoff.get("winners")),
        "losers": _as_list_of_strings(tradeoff.get("losers")),
    }


def _artifact_ref_from_packet(payload: dict[str, Any], key: str) -> ArtifactRef | None:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    return _artifact_ref_from_payload(artifacts.get(key))


def _transport_summary_from_packet(payload: dict[str, Any]) -> dict[str, Any] | None:
    causal = payload.get("causal")
    if not isinstance(causal, dict):
        return None
    transport = causal.get("transportability_summary")
    return dict(transport) if isinstance(transport, dict) else None


def _governance_links_from_payload(payload: dict[str, Any]) -> dict[str, ArtifactRef | None] | None:
    links = payload.get("links")
    if not isinstance(links, dict):
        return None
    result: dict[str, ArtifactRef | None] = {}
    for key, value in links.items():
        result[str(key)] = _artifact_ref_from_payload(value)
    return result or None


def _artifact_ref_from_payload(value: Any) -> ArtifactRef | None:
    if isinstance(value, dict):
        try:
            parsed_ref: ArtifactRef = ArtifactRef.model_validate(value)
            return parsed_ref
        except (TypeError, ValueError) as exc:
            logger.debug(
                "Failed to parse generic artifact ref payload %s: %s", value, exc
            )
            return None
    if isinstance(value, str):
        return _artifact_ref_from_string(
            value,
            kind="artifact.unknown",
            media_type="application/json",
        )
    return None


def _agent_step_status(
    value: str | None,
    *,
    fallback: AgentStepStatus = "info",
) -> AgentStepStatus:
    if value in {"ok", "warn", "fail", "info"}:
        return cast("AgentStepStatus", value)
    return fallback


def _as_evaluator_verdict(value: Any) -> EvaluatorVerdict | None:
    if value in {"APPROVE", "REPLAN_DATA", "REPLAN_METHOD", "REPLAN_PARAMS", "STOP_BUDGET"}:
        return cast("EvaluatorVerdict", value)
    return None


def _as_iteration_lifecycle_state(value: Any) -> IterationLifecycleState:
    if value in {
        "plan_created",
        "preflight_running",
        "preflight_failed",
        "ready_to_run",
        "executing",
        "evaluating",
        "replanning",
        "approved",
        "stopped_budget",
        "stopped_no_delta",
        "stopped_guardrail",
    }:
        return cast("IterationLifecycleState", value)
    return "plan_created"


def _as_stop_reason(value: Any) -> StopReason | None:
    if value in {"approved", "budget_exhausted", "no_delta", "guardrail_violation"}:
        return cast("StopReason", value)
    return None


def _artifact_id_from_string(value: str | None) -> ArtifactID | None:
    if not value:
        return None
    try:
        parsed_id: ArtifactID = ArtifactID.model_validate(value)
        return parsed_id
    except (TypeError, ValueError, ValidationError) as exc:
        logger.debug("Failed to parse artifact id %s: %s", value, exc)
        return None


def _has_replay_payload(payload: dict[str, Any]) -> bool:
    replay = payload.get("replay")
    return isinstance(replay, dict)


def _replay_value(payload: dict[str, Any], key: str) -> str | None:
    replay = payload.get("replay")
    if not isinstance(replay, dict):
        return None
    return _as_str(replay.get(key))


def _replay_list(payload: dict[str, Any], key: str) -> list[str]:
    replay = payload.get("replay")
    if not isinstance(replay, dict):
        return []
    return _as_list_of_strings(replay.get(key))


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(item)
    return result


def _as_list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        result.append(str(item))
    return result


def _sanitize_payload(value: Any, *, sensitive_keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered_key = str(key).lower()
            if any(marker in lowered_key for marker in sensitive_keys):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_payload(item, sensitive_keys=sensitive_keys)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item, sensitive_keys=sensitive_keys) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def _sanitize_string(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if "bearer " in lowered:
        return "[REDACTED]"
    if lowered.startswith("eyj") and len(value) >= 32:
        return "[REDACTED]"
    return value
