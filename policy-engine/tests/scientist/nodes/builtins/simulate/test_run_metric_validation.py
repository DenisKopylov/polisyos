from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    MetricObservationBundle,
    Metrics,
    MetricsRef,
    ModelOutputs,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.metric_validation_report import load_metric_validation_report
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.simulate.run_metric_validation import RunMetricValidationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRICS_REF,
    ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
)
from polisyos.scientist.validation.metrics import persist_metric_observation_bundle


def test_run_metric_validation_node_persists_report_and_updates_simulation_result(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_metric_validation_node")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.metric_validation.node"))

    exec_plan_payload = store.put_json(
        {"order": ["noop"]},
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="1.0"),
        ),
    )
    metrics_payload = store.put_json(
        Metrics(values={"roc_auc": 0.72, "accuracy": 0.75}).model_dump(mode="json"),
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    bundle_ref = persist_metric_observation_bundle(
        store,
        MetricObservationBundle(
            dataset_id="holdout_v1",
            task="binary",
            sample_ids=["a", "b", "c", "d", "e", "f"],
            y_true=[0, 1, 0, 1, 1, 0],
            models={
                "baseline": ModelOutputs(
                    model_id="baseline",
                    y_pred=[0, 1, 0, 0, 1, 0],
                    y_score=[0.2, 0.9, 0.3, 0.4, 0.7, 0.2],
                ),
                "candidate": ModelOutputs(
                    model_id="candidate",
                    y_pred=[0, 1, 0, 1, 1, 0],
                    y_score=[0.1, 0.95, 0.25, 0.8, 0.75, 0.1],
                ),
            },
            metadata={"run_id": "R_metric_validation_node", "baseline_model_id": "baseline"},
        ),
    )
    simulation_result_payload = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_payload.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_payload.artifact_id),
            metric_observation_bundle_ref=bundle_ref,
        ).model_dump(mode="json"),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
        ),
    )

    state = ExperimentState(
        run_id="R_metric_validation_node",
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: SimulationResultRef(
                artifact_id=simulation_result_payload.artifact_id
            ),
            ARTIFACT_METRICS_REF: MetricsRef(artifact_id=metrics_payload.artifact_id),
            ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF: bundle_ref,
        },
        params={
            "metric_validation": {
                "baseline_model_id": "baseline",
                "candidate_model_ids": ["candidate"],
                "metric_ids": ["roc_auc", "accuracy"],
                "n_resamples": 500,
                "random_seed": 7,
            }
        },
    )

    outcome = RunMetricValidationNode().execute(ctx, state)

    assert outcome.status == "ok"
    metric_validation_ref = outcome.state.artifacts_index[ARTIFACT_METRIC_VALIDATION_REPORT_REF]
    report = load_metric_validation_report(store, metric_validation_ref)
    assert report.dataset_id == "holdout_v1"
    assert {comparison.metric_id for comparison in report.comparisons} == {"roc_auc", "accuracy"}

    updated_sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_sim_payload = from_canonical_bytes(store.get_bytes(updated_sim_ref.artifact_id))
    updated_simulation_result = SimulationResult.model_validate(updated_sim_payload)
    assert updated_simulation_result.metric_observation_bundle_ref == bundle_ref
    assert updated_simulation_result.metric_validation_report_ref == metric_validation_ref

