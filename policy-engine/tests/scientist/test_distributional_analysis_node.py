from __future__ import annotations

from dataclasses import replace
import logging

import jax.numpy as jnp

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult, StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir.distributional import CohortDimension, load_distributional_report
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis import (
    RunDistributionalAnalysisNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)


def test_distributional_analysis_node_generates_report(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_dist")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.dist"))

    base_state = GlobalState.empty(n_agents=20, n_firms=4)
    incomes_before = jnp.array([500.0] * 10 + [2000.0] * 10, dtype=jnp.float32)
    incomes_after = jnp.array([525.0] * 10 + [2100.0] * 10, dtype=jnp.float32)
    employers = jnp.array([0] * 5 + [1] * 5 + [2] * 5 + [3] * 5, dtype=jnp.int32)

    baseline_agents = replace(base_state.agents, income=incomes_before, employer_id=employers)
    simulated_agents = replace(base_state.agents, income=incomes_after, employer_id=employers)

    baseline_state = replace(base_state, agents=baseline_agents)
    simulated_state = replace(base_state, agents=simulated_agents)

    baseline_snapshot_ref = put_state_snapshot(store, state=baseline_state, step=0)
    simulated_snapshot_ref = put_state_snapshot(store, state=simulated_state, step=1)

    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=StateSnapshotRef(artifact_id=baseline_snapshot_ref.artifact_id)),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )

    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(simulated_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )

    simulation_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
            state_snapshot_ref=StateSnapshotRef(artifact_id=simulated_snapshot_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_dist",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id),
        },
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: simulation_result_ref,
        },
    )

    outcome = RunDistributionalAnalysisNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_DISTRIBUTIONAL_REPORT_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF]
    report = load_distributional_report(store, report_ref)

    assert report.get_breakdown(CohortDimension.INCOME_QUINTILE) is not None
    assert len(report.breakdowns) >= 1
