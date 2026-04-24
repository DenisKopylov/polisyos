from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointGCPolicy,
    load_checkpoint_history,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.metrics import (
    OTelEngineMetrics,
    build_engine_metrics,
    get_metrics_exporter_health,
)
from polisyos.scientist.engine.operational_monitoring import ScientistOperationalMonitor
from polisyos.scientist.engine.protocol import NodeOutcome
from polisyos.scientist.engine.retry import (
    RetryExhaustedError,
    RetryPolicy,
    execute_with_retry_async,
)
from polisyos.scientist.engine.runner.serialization import serialize_context_meta
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.llm.provider_verification import ProviderCapabilityVerification
from polisyos.scientist.provenance.run_dag import RunProvenanceDAG
from polisyos.scientist.replay_backend import list_dead_letters, replay_dead_letter
from polisyos.scientist.search.stages import CorrelationTracker, StageResult


@dataclass
class _InstrumentRecorder:
    calls: list[tuple[str, float | int, dict[str, str]]] = field(default_factory=list)

    def add(self, value: float | int, attrs: dict[str, str]) -> None:
        self.calls.append(("add", value, dict(attrs)))

    def record(self, value: float | int, attrs: dict[str, str]) -> None:
        self.calls.append(("record", value, dict(attrs)))

    def set(self, value: float | int, attrs: dict[str, str]) -> None:
        self.calls.append(("set", value, dict(attrs)))


class _FakeMetricsRegistry:
    def __init__(self) -> None:
        self.ensure_initialized_calls = 0
        self.scientist_node_starts_total = _InstrumentRecorder()
        self.scientist_node_duration_seconds = _InstrumentRecorder()
        self.scientist_node_executions_total = _InstrumentRecorder()
        self.scientist_node_retry_count = _InstrumentRecorder()
        self.scientist_tier_duration_seconds = _InstrumentRecorder()
        self.scientist_tier_queue_depth = _InstrumentRecorder()
        self.scientist_semaphore_wait_seconds = _InstrumentRecorder()
        self.scientist_workflow_state = _InstrumentRecorder()
        self.slo_dag_runs_total = _InstrumentRecorder()
        self.slo_dag_duration_seconds = _InstrumentRecorder()
        self.trace_calls: list[dict[str, str | None]] = []
        self.alert_calls: list[dict[str, str | None]] = []

    def ensure_initialized(self) -> None:
        self.ensure_initialized_calls += 1

    def get_exporter_health(self) -> dict[str, dict[str, object]]:
        return {"metrics": {"status": "ok", "failures": []}}

    def record_scientist_trace_correlation(
        self,
        *,
        runner_backend: str,
        workflow_id: str,
        run_id: str,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        self.trace_calls.append(
            {
                "runner_backend": runner_backend,
                "workflow_id": workflow_id,
                "run_id": run_id,
                "trace_id": trace_id,
                "span_id": span_id,
            }
        )

    def record_scientist_operational_alert(
        self,
        *,
        alert_type: str,
        severity: str,
        workflow_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.alert_calls.append(
            {
                "alert_type": alert_type,
                "severity": severity,
                "workflow_id": workflow_id,
                "run_id": run_id,
            }
        )


def _registry_bundle_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "d" * 64,
        kind="core.registry_bundle",
        media_type="application/json",
    )


def _stage_result(*, score: float, passed: bool, stage_name: str) -> StageResult:
    return StageResult(
        policy_candidate={},
        objective_value=score,
        is_promising=passed,
        stage_name=stage_name,
        predicted_score=score,
        actual_score=score,
    )


def test_metrics_exporter_operational_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _FakeMetricsRegistry()

    monkeypatch.setattr(
        "polisyos.scientist.engine.metrics._default_metrics",
        lambda: (_ for _ in ()).throw(
            AssertionError("global metrics lookup should not run when metrics are injected")
        ),
    )

    metrics = build_engine_metrics(metrics=registry)
    health = get_metrics_exporter_health(metrics=registry)

    metrics.record_node_started(
        alias="agent",
        node_id="scientist.agent@1.0.0",
        workflow_id="wf_reliability",
    )
    metrics.record_node_completed(
        alias="agent",
        node_id="scientist.agent@1.0.0",
        workflow_id="wf_reliability",
        status="ok",
        duration_ms=125,
        cache_hit=False,
        retry_count=1,
    )
    metrics.record_workflow_completed(
        workflow_id="wf_reliability",
        status="ok",
        duration_ms=250,
        node_count=5,
    )

    assert health.ready is True
    assert registry.ensure_initialized_calls == 1
    assert registry.scientist_node_starts_total.calls
    assert registry.scientist_node_duration_seconds.calls
    assert registry.scientist_node_executions_total.calls
    assert registry.scientist_node_retry_count.calls
    assert registry.slo_dag_runs_total.calls
    assert registry.slo_dag_duration_seconds.calls


def test_trace_correlation_operational_signal(monkeypatch, tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run = RunContext.start(
        store=store,
        registry_bundle=_registry_bundle_ref(),
        run_id="R_trace_operational",
    )
    metrics = build_engine_metrics(max_trace_correlations=8)
    assert isinstance(metrics, OTelEngineMetrics)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("scientist.trace-operational"),
        metrics=metrics,
    )
    monkeypatch.setattr(
        "polisyos.scientist.engine.runner.serialization._current_trace_ids",
        lambda: ("a" * 32, "b" * 16),
    )

    for backend in ("local", "ray", "temporal"):
        meta = serialize_context_meta(
            ctx,
            workflow_id="wf_trace_operational",
            runner_backend=backend,
        )
        metrics.record_trace_correlation(
            runner_backend=backend,
            workflow_id="wf_trace_operational",
            run_id=str(meta["run_id"]),
            trace_id=meta.get("trace_id"),
            span_id=meta.get("span_id"),
        )

    recent = metrics.recent_trace_correlations()

    assert [item.runner_backend for item in recent] == ["local", "ray", "temporal"]
    assert {item.workflow_id for item in recent} == {"wf_trace_operational"}
    assert {item.trace_id for item in recent} == {"a" * 32}
    assert {item.span_id for item in recent} == {"b" * 16}


@pytest.mark.asyncio
async def test_dlq_replay_operational_signal(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run = RunContext.start(
        store=store,
        registry_bundle=_registry_bundle_ref(),
        run_id="R_dlq_operational",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("scientist.dlq-operational"),
    )
    state = ExperimentState(run_id="R_dlq_operational", params={"replayed": False})

    class _FailingNode:
        def __init__(self) -> None:
            self.spec = type(
                "Spec",
                (),
                {
                    "metadata": type(
                        "Metadata",
                        (),
                        {"component_id": "scientist.agent@1.0.0"},
                    )()
                },
            )()

        def execute(self, ctx, state):
            del ctx, state
            raise RuntimeError("boom")

    with pytest.raises(RetryExhaustedError):
        await execute_with_retry_async(
            _FailingNode(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="agent",
        )

    dead_letters = list_dead_letters(
        store,
        run_id="R_dlq_operational",
        alias="agent",
    )

    class _RecoveryNode:
        def __init__(self) -> None:
            self.spec = type(
                "Spec",
                (),
                {
                    "metadata": type(
                        "Metadata",
                        (),
                        {"component_id": "scientist.agent@1.0.0"},
                    )()
                },
            )()

        def execute(self, ctx, state):
            del ctx
            return NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"replayed": True}}),
            )

    assert len(dead_letters) == 1
    outcome = await replay_dead_letter(
        store,
        dead_letters[0].artifact_ref.artifact_id,
        ctx=ctx,
        state=state,
        node=_RecoveryNode(),
    )

    assert outcome.status == "ok"
    assert outcome.state.params["replayed"] is True


def test_bounded_retention_operational_signal(tmp_path) -> None:
    run_id = "R_bounded_retention"
    store = FileSystemCAS(tmp_path)
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
        gc_policy=CheckpointGCPolicy(
            max_checkpoints=3,
            max_age_hours=72.0,
            max_incremental_chain=2,
        ),
    )
    for index in range(32):
        result = hook.on_node_complete(
            state=ExperimentState(
                run_id=run_id,
                params={"phase": "EXECUTE", "step": index},
            ),
            alias=f"step_{index}",
            node_id=f"scientist.step_{index}@1.0.0",
            completed_nodes=[f"step_{item}" for item in range(index + 1)],
            workflow_id="wf_bounded_retention",
            workflow_fingerprint="f" * 64,
            cache_entry_ref=None,
        )
        assert result is not None

    history = load_checkpoint_history(tmp_path / "runs" / run_id)
    assert history is not None
    assert len(history.entries) <= 6
    assert max(entry.sequence_number for entry in history.entries) == 31

    trace_metrics = build_engine_metrics(max_trace_correlations=7)
    assert isinstance(trace_metrics, OTelEngineMetrics)
    for index in range(128):
        trace_metrics.record_trace_correlation(
            runner_backend=f"runner-{index % 3}",
            workflow_id="wf_bounded_retention",
            run_id=run_id,
            trace_id=f"{index:032x}"[-32:],
            span_id=f"{index:016x}"[-16:],
        )
    assert len(trace_metrics.recent_trace_correlations()) == 7

    monitor = ScientistOperationalMonitor(max_recent_alerts=5)
    for index in range(64):
        monitor.record_alert(
            alert_type=f"alert_{index}",
            severity="warn",
            workflow_id="wf_bounded_retention",
            run_id=run_id,
        )
    assert len(monitor.recent_alerts()) == 5

    dag = RunProvenanceDAG(run_id=run_id, max_llm_records=4)
    for index in range(48):
        dag.record_llm_call(
            node_alias=f"drafter_{index}",
            model_id="gpt-4o-mini",
            temperature=0.1,
            input_tokens=10 + index,
            output_tokens=20 + index,
            cost_usd=Decimal("0.01"),
        )
    assert len(dag.llm_records) == 4

    tracker = CorrelationTracker(max_records=6, drift_window_size=4)
    for index in range(40):
        tracker.record(
            _stage_result(score=float(index), passed=True, stage_name="L2"),
            _stage_result(score=float(index) + 0.1, passed=True, stage_name="L4"),
            f"candidate-{index}",
        )
    assert tracker.record_count == 6

    verification = ProviderCapabilityVerification(
        provider="gonka",
        model_id="qwen",
        base_url="https://api.gonkagate.com/v1",
        request_ids=[f"req-{idx}" for idx in range(96)],
        verification_notes=[f"note-{idx}" for idx in range(96)],
    )
    assert len(verification.request_ids) == 64
    assert len(verification.verification_notes) == 64


def test_monitoring_alerts_operational_signal() -> None:
    registry = _FakeMetricsRegistry()
    monitor = ScientistOperationalMonitor(max_recent_alerts=8, metrics=registry)

    emitted = monitor.ingest_metric_regressions(
        ["group_fairness_gap", "rmse_holdout", "policy_cost"],
        workflow_id="wf_monitoring",
        run_id="R_monitoring",
    )
    budget = monitor.record_alert(
        alert_type="budget_anomaly",
        severity="warn",
        workflow_id="wf_monitoring",
        run_id="R_monitoring",
    )

    snapshot = monitor.snapshot()

    assert [item.alert_type for item in emitted] == [
        "fairness_regression",
        "calibration_degradation",
        "drift",
    ]
    assert budget.alert_type == "budget_anomaly"
    assert snapshot["alert_counts"]["budget_anomaly"] == 1
    assert {item["alert_type"] for item in snapshot["recent_alerts"]} >= {
        "fairness_regression",
        "calibration_degradation",
        "drift",
        "budget_anomaly",
    }
    assert len(registry.alert_calls) == 4
