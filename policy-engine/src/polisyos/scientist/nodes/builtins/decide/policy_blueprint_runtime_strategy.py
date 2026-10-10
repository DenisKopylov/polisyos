from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.calibration_report import (
    build_calibration_report,
    persist_funnel_calibration_report,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    StrategicRuntimeOutput as _SharedStrategicRuntimeOutput,
)
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    persist_runtime_strategic_artifacts as _shared_persist_runtime_strategic_artifacts,
)
from polisyos.scientist.nodes.builtins.state_keys import INPUT_CALIBRATION_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _candidate_search_payload(
    candidate: PolicyCandidateSchema,
    state: ExperimentState,
) -> dict[str, Any]:
    payload = candidate.as_search_payload()
    bundle = candidate.trinity_bundle
    payload["semantic"] = {
        "interventions": [
            {
                "id": intervention.intervention_id,
                "type": intervention.kind,
                "variable": parameter.param_path or parameter.param_id,
                "parameters": intervention.params,
            }
            for intervention in bundle.policy_spec.interventions
            for parameter in bundle.policy_spec.parameters
            if parameter.intervention_id == intervention.intervention_id
        ],
        "objectives": [
            {
                "name": objective.objective_id,
                "variable": objective.metric_id,
            }
            for objective in bundle.problem_frame.objectives
        ],
        "causal_graph": state.params.get("causal_graph"),
    }
    if "causal_graph" in state.params:
        payload["causal_graph"] = state.params["causal_graph"]
    payload.setdefault("metadata", {})
    payload["metadata"]["task_family"] = "policy"
    payload["metadata"]["domain"] = str(
        candidate.metadata.get("domain")
        or state.params.get("policy_request_domain")
        or state.run_id
    )
    return payload


def _ensure_calibration_report(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> ArtifactRef:
    if (ref := state.inputs.get(INPUT_CALIBRATION_REPORT_REF)) is not None:
        return ref
    report = build_calibration_report()
    state_metrics = _resolve_runtime_correlation_metrics(state, None)
    if state_metrics:
        report = report.model_copy(
            update={
                "current_mode": str(state_metrics.get("routing_mode", report.current_mode)),
                "routing_health": {
                    **report.routing_health,
                    **state_metrics,
                },
            }
        )
    return persist_funnel_calibration_report(ctx.store, report)


def _resolve_runtime_correlation_metrics(
    state: ExperimentState,
    calibration_report: Any | None,
) -> dict[str, Any]:
    """Reuse the current calibration projection already attached to the run."""

    state_metrics = state.params.get("correlation_metrics")
    if isinstance(state_metrics, Mapping) and state_metrics:
        metrics = dict(state_metrics)
        raw_sample_count = metrics.get("sample_count")
        try:
            sample_count = int(raw_sample_count) if raw_sample_count is not None else None
        except (TypeError, ValueError):
            sample_count = None
        if sample_count is None or sample_count <= 0:
            # Preserve the existing projection, but do not let an old
            # ``normal`` default turn an empty corpus into measured health.
            metrics["calibration_state"] = "not_established"
            metrics["routing_mode"] = "no_promotion"
            metrics["promotion_ban_active"] = False
        elif sample_count is not None and sample_count > 0:
            metrics.setdefault("calibration_state", "observed")
        return metrics
    if calibration_report is None:
        return {}
    metrics = dict(getattr(calibration_report, "routing_health", {}) or {})
    try:
        sample_count = int(metrics.get("sample_count", 0) or 0)
    except (TypeError, ValueError):
        sample_count = 0
    if sample_count <= 0:
        metrics["calibration_state"] = "not_established"
        metrics["promotion_ban_active"] = False
        metrics["routing_mode"] = "no_promotion"
    else:
        metrics["calibration_state"] = "observed"
        metrics.setdefault("promotion_ban_active", False)
        metrics["routing_mode"] = str(
            getattr(calibration_report, "current_mode", None) or "no_promotion"
        )
    return metrics


def _resolve_runtime_correlation_tracker(
    calibration_report: Any | None,
) -> CorrelationTracker | None:
    """Restore a real tracker snapshot when present; otherwise keep projections read-only."""

    snapshot: Any = None
    if calibration_report is not None:
        metadata = getattr(calibration_report, "metadata", {}) or {}
        if isinstance(metadata, Mapping):
            snapshot = metadata.get("correlation_tracker_snapshot")
    if isinstance(snapshot, Mapping):
        try:
            return CorrelationTracker.from_snapshot(dict(snapshot))
        except (TypeError, ValueError):
            return None
    # There is no existing runtime state key for a tracker snapshot.  Do not
    # invent one or silently create a fresh empty tracker: the node consumes
    # the persisted report/state projection until a real snapshot is supplied.
    return None


def _persist_runtime_strategic_artifacts(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    candidate_ref: ArtifactRef,
    selection_vector_ref: ArtifactRef,
    selection_artifact,
    artifacts_index: dict[str, ArtifactRef],
) -> _SharedStrategicRuntimeOutput:
    return _shared_persist_runtime_strategic_artifacts(
        ctx,
        state,
        artifacts_index=artifacts_index,
        candidate_ref=candidate_ref,
        evidence_ref=selection_vector_ref,
        evidence_role="policy_evaluation",
        baseline_payload=selection_artifact,
    )
