from __future__ import annotations

from unittest.mock import patch

import pytest
from _helpers.scientist_runtime import (
    build_execution_context,
    build_initial_state,
    build_linear_registry,
    build_linear_workflow_spec,
    default_actual_rows,
    load_json_artifact,
    regression_actual_rows,
)

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.feedback import DecisionReissuePlan, MonitoringVerdict
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.scientist.feedback.core import DecisionFeedbackService
from polisyos.scientist.methods.autotune import calibration as calibration_autotune
from polisyos.scientist.methods.autotune.calibration import CalibrationMetaSearchConfig
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.operational_monitoring import (
    ScientistOperationalMonitor,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService

pytestmark = pytest.mark.integration


def test_linear_scientist_workflow_happy_path(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_scientist_happy"
    ctx, registry_bundle_ref = build_execution_context(store, run_id=run_id)
    state = build_initial_state(
        store,
        run_id=run_id,
        registry_bundle_ref=registry_bundle_ref,
        actual_rows=default_actual_rows(),
    )
    registry, nodes = build_linear_registry(store)

    result = WorkflowExecutor(ctx, registry).execute(build_linear_workflow_spec(), state)

    assert result.report.status == "ok"
    assert [record.alias for record in result.report.nodes] == [
        "agent",
        "search",
        "simulation",
        "governance",
        "decision",
    ]
    assert all(node.calls == 1 for node in nodes.values())
    packet_ref = result.state.artifacts_index["decision_packet_ref"]
    packet_payload = load_json_artifact(store, str(packet_ref.artifact_id))
    assert packet_payload["governance"]["status"] == "approved"
    assert packet_payload["feedback_loop"]["monitoring_contract_ref"]


def test_linear_scientist_workflow_tool_failure_retries_and_succeeds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_scientist_retry"
    ctx, registry_bundle_ref = build_execution_context(store, run_id=run_id)
    state = build_initial_state(
        store,
        run_id=run_id,
        registry_bundle_ref=registry_bundle_ref,
        actual_rows=default_actual_rows(),
    )
    registry, nodes = build_linear_registry(store, search_failures=1)

    with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
        result = WorkflowExecutor(ctx, registry).execute(
            build_linear_workflow_spec(search_retry=1),
            state,
        )

    assert result.report.status == "ok"
    assert nodes["search"].calls == 2
    assert nodes["decision"].calls == 1
    search_record = next(record for record in result.report.nodes if record.alias == "search")
    assert search_record.status == "ok"


def test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_scientist_resume"
    workflow = build_linear_workflow_spec()
    run_dir = tmp_path / "runs" / run_id

    ctx, registry_bundle_ref = build_execution_context(store, run_id=run_id)
    state = build_initial_state(
        store,
        run_id=run_id,
        registry_bundle_ref=registry_bundle_ref,
        actual_rows=default_actual_rows(),
    )
    registry_a, nodes_a = build_linear_registry(store, decision_failures=1)
    hook = CASCheckpointHook(store=store, run_dir=run_dir, checkpoint_policy="strict")

    first = WorkflowExecutor(ctx, registry_a, checkpoint_hook=hook).execute(workflow, state)

    assert first.report.status == "fail"
    assert nodes_a["agent"].calls == 1
    assert nodes_a["search"].calls == 1
    assert nodes_a["simulation"].calls == 1
    assert nodes_a["governance"].calls == 1
    assert nodes_a["decision"].calls == 1

    registry_b, nodes_b = build_linear_registry(store, decision_failures=0)
    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=registry_b,
        registry_bundle_ref=registry_bundle_ref,
        checkpoint_policy="strict",
        run_dir=run_dir,
    )

    assert resumed.report.status == "ok"
    assert nodes_b["agent"].calls == 0
    assert nodes_b["search"].calls == 0
    assert nodes_b["simulation"].calls == 0
    assert nodes_b["governance"].calls == 0
    assert nodes_b["decision"].calls == 1


def test_linear_scientist_workflow_governance_rejection_stops_decision_publication(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_scientist_governance_reject"
    ctx, registry_bundle_ref = build_execution_context(store, run_id=run_id)
    state = build_initial_state(
        store,
        run_id=run_id,
        registry_bundle_ref=registry_bundle_ref,
        actual_rows=default_actual_rows(),
    )
    registry, nodes = build_linear_registry(store, governance_mode="reject")

    result = WorkflowExecutor(ctx, registry).execute(build_linear_workflow_spec(), state)

    assert result.report.status == "fail"
    assert nodes["governance"].calls == 1
    assert nodes["decision"].calls == 0
    governance_record = next(
        record for record in result.report.nodes if record.alias == "governance"
    )
    assert governance_record.status == "fail"
    assert "decision_packet_ref" not in result.state.artifacts_index


def test_linear_scientist_workflow_post_deploy_regression_triggers_alerts_and_reissue(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_scientist_post_deploy"
    ctx, registry_bundle_ref = build_execution_context(store, run_id=run_id)
    state = build_initial_state(
        store,
        run_id=run_id,
        registry_bundle_ref=registry_bundle_ref,
        actual_rows=regression_actual_rows(),
    )
    registry, _nodes = build_linear_registry(store)
    result = WorkflowExecutor(ctx, registry).execute(build_linear_workflow_spec(), state)
    packet_ref = str(result.state.artifacts_index["decision_packet_ref"].artifact_id)
    packet_payload = load_json_artifact(store, packet_ref)
    monitor = ScientistOperationalMonitor(max_recent_alerts=8)
    loaded_context: dict[str, object] = {}

    class _ChampionLoader:
        def load(self, context=None):
            loaded_context.update(dict(context or {}))
            return CalibrationMetaSearchConfig(
                learning_rate=0.0042,
                early_stop_patience=17,
            )

    monkeypatch.setattr("polisyos.scientist.feedback.core.get_operational_monitor", lambda: monitor)
    monkeypatch.setattr(calibration_autotune, "CalibrationMetaRuntimeLoader", _ChampionLoader)

    report, refs = DecisionFeedbackService(store).evaluate_packet(
        run_id=run_id,
        packet_ref=packet_ref,
        packet_payload=packet_payload,
    )

    assert report.overall_verdict == MonitoringVerdict.REFUTED
    assert set(report.refuted_metric_ids) >= {
        "policy_cost",
        "group_fairness_gap",
        "rmse_holdout",
    }
    assert refs.compare_report_ref is not None
    assert refs.reissue_plan_ref is not None
    plan = DecisionReissuePlan.model_validate(load_json_artifact(store, refs.reissue_plan_ref))
    assert plan.calibration_config_ref is not None
    config = CalibrationConfig.model_validate(
        load_json_artifact(store, plan.calibration_config_ref)
    )
    assert config.learning_rate == 0.0042
    assert config.early_stop_patience == 17
    assert {
        (target.target_id, target.model_metric_path, target.fabric_metric)
        for target in config.targets
    } == {
        (metric.metric_id, metric.metric_id, metric.source_metric_id)
        for metric in report.metrics
        if metric.verdict == MonitoringVerdict.REFUTED
    }
    assert loaded_context["source_run_id"] == run_id
    assert loaded_context["source_packet_ref"] == packet_ref
    assert loaded_context["source_packet_payload"] == packet_payload
    assert loaded_context["monitoring_report"] is report
    assert loaded_context["monitoring_report_ref"] == refs.monitoring_report_ref
    assert loaded_context["compare_report_ref"] == refs.compare_report_ref
    alert_types = {item.alert_type for item in monitor.recent_alerts()}
    assert "fairness_regression" in alert_types
    assert "calibration_degradation" in alert_types
    summary = DecisionValidityService(store).get_summary(packet_ref, force=True)
    assert summary["status"] == "requires_human_review"
