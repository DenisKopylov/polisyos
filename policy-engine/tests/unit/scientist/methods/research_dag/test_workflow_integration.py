from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_RESEARCH_DAG_REF
from polisyos.scientist.methods.research_dag.persistence import load_research_dag
from polisyos.scientist.methods.research_dag.projections import RESEARCH_DAG_FEATURE_FLAG


@pytest.mark.parametrize(
    "workflow_id",
    [
        "scientist_policy_design",
        "scientist_policy_verified",
        "scientist_causal_full",
    ],
)
def test_selected_workflow_persists_research_dag_ref_when_enabled(
    tmp_path,
    workflow_id: str,
) -> None:
    store = FileSystemCAS(tmp_path)
    run = MagicMock()
    run.trace_path = None
    run.emit = MagicMock()
    run.add_input = MagicMock()
    run.add_output = MagicMock()
    run.finalize.return_value = ArtifactRef(
        artifact_id="sha256:" + "f" * 64,
        kind="run",
        media_type="application/json",
    )
    ctx = ExecutionContext(store=store, run=run, logger=MagicMock())
    state = ExperimentState(
        run_id="run_1",
        params={
            RESEARCH_DAG_FEATURE_FLAG: True,
            "policy_question": "Should the policy be adopted?",
        },
    )
    node = MagicMock()
    node.spec.state_reads = []
    node.spec.state_writes = []
    node.spec.node_id = "scientist.node_noop@1.0.0"
    node.execute.return_value = NodeOutcome(status="ok", state=state, events=[], artifacts=[])
    registry = MagicMock(spec=NodeRegistry)
    registry.get.return_value = node
    workflow = WorkflowSpec(
        workflow_id=workflow_id,
        nodes=[NodeInvocation(alias="plan_policy_request", node_id="scientist.node_noop@1.0.0")],
    )

    result = WorkflowExecutor(ctx, registry).execute(workflow, state)

    research_dag_ref = result.state.artifacts_index[ARTIFACT_RESEARCH_DAG_REF]
    loaded = load_research_dag(store, research_dag_ref)
    assert loaded.workflow_id == workflow_id
    assert loaded.metadata["selected_workflow"] is True
