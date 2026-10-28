"""Selected Research DAG production and propagation over the real workflow engine."""

from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.runtime.http.services.adapters.core_run import load_core_run
from polisyos.scientist.methods.research_dag.invalidation import (
    SourceInvalidationEvent,
    propagate_source_invalidation,
)
from polisyos.scientist.methods.research_dag.persistence import load_research_dag
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_RESEARCH_DAG_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor, WorkflowReport
from polisyos.scientist.orchestration.engine.finalization import (
    FINAL_RESEARCH_DAG_STATE_PATH,
    WorkflowStateFinalization,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class _ArtifactNode:
    def __init__(self, name: str, *, consumes_source: bool = False) -> None:
        self.name = name
        self.consumes_source = consumes_source
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(f"scientist.node_dag_{name}@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name=f"DAG {name}",
                description="Bounded real workflow projection witness",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["artifacts_index.source_ref"] if consumes_source else [],
            state_writes=["artifacts_index"],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if self.consumes_source:
            # The dependent executes an actual CAS read, not only a scheduling edge.
            source_bytes = ctx.store.get_bytes(state.artifacts_index["source_ref"])
            assert source_bytes
        ref = ctx.store.put_json(
            {"witness": self.name},
            PutOptions(kind="scientist.dag_witness", media_type="application/json"),
            return_selected_profile=True,
        )
        output = state.model_copy(deep=True)
        output.artifacts_index[f"{self.name}_ref"] = ref
        return NodeOutcome(status="ok", state=output, artifacts=[ref])


def test_engine_selected_dag_reopens_and_propagates_only_real_branched_scope(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=bundle, run_id="R_dag_branch")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.dag_branch"))
    source = _ArtifactNode("source")
    dependent = _ArtifactNode("dependent", consumes_source=True)
    sibling = _ArtifactNode("independent")
    registry = NodeRegistry()
    for node in (source, dependent, sibling):
        registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="scientist_policy_design",
        nodes=[
            NodeInvocation(alias="source", node_id=source.spec.metadata.component_id),
            NodeInvocation(
                alias="dependent",
                node_id=dependent.spec.metadata.component_id,
                depends_on=["source"],
            ),
            NodeInvocation(alias="independent", node_id=sibling.spec.metadata.component_id),
        ],
    )
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="R_dag_branch", params={"research_dag_enabled": True})
    )
    assert result.report.status == "ok"
    report_ref = result.state.reports_index["workflow_report"]
    report = WorkflowReport.model_validate_json(store.get_bytes(report_ref))
    assert {record.alias for record in report.nodes} == {"source", "dependent", "independent"}

    dag_ref = result.state.artifacts_index[ARTIFACT_RESEARCH_DAG_REF]
    assert dag_ref.manifest_profile_sha256 is not None
    assert store.verify(dag_ref).ok
    dag = load_research_dag(store, dag_ref)
    finalization_ref = run.read_runtime_workflow_finalization_ref()
    assert store.verify(finalization_ref).ok
    finalization = WorkflowStateFinalization.model_validate_json(store.get_bytes(finalization_ref))
    assert store.verify(finalization.workflow_spec_ref).ok
    assert store.verify(finalization.final_state_ref).ok
    assert run.trace_path is not None
    indexed = load_core_run(store=store, run_dir=run.trace_path.parent)
    assert indexed is not None
    assert indexed.experiment_state_ref == finalization.final_state_ref
    assert indexed.experiment_state_ref != finalization.prior_state_ref
    assert indexed.workflow_report_ref == report_ref
    assert (
        WorkflowSpec.model_validate_json(store.get_bytes(finalization.workflow_spec_ref))
        == workflow
    )
    persisted_state = ExperimentState.model_validate_json(
        store.get_bytes(finalization.final_state_ref)
    )
    assert persisted_state.artifacts_index[ARTIFACT_RESEARCH_DAG_REF] == dag_ref
    assert persisted_state.reports_index["workflow_report"] == report_ref
    assert store.verify(report_ref).ok
    assert any(
        binding.state_path == FINAL_RESEARCH_DAG_STATE_PATH and binding.artifact_ref == dag_ref
        for binding in finalization.output_bindings
    )
    source_ref = result.state.artifacts_index["source_ref"]
    independent_ref = result.state.artifacts_index["independent_ref"]
    assert source_ref != independent_ref
    assert store.verify(source_ref).ok and store.verify(independent_ref).ok
    event = SourceInvalidationEvent(
        event_id="invalidate-source",
        source_ref=source_ref,
        invalidation_type="withdrawn",
        reason="Bounded source-change witness.",
    )
    impact = propagate_source_invalidation(dag, event)
    assert set(impact.affected_node_ids) == {
        "scientist_policy_design:execution:source",
        "scientist_policy_design:execution:dependent",
    }
    assert "scientist_policy_design:execution:independent" not in impact.affected_node_ids
    assert store.verify(independent_ref).ok
    assert dag.metadata["actual_consumed_basis"] == "not_established"
