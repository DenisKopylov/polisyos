"""Real selected-source workflow helpers shared by Runtime comparison witnesses."""

from __future__ import annotations

from typing import Any

from _helpers.control_worker import dispatch_one_control_job
from polisyos.core.artifacts import artifact_ref_identity_key, validate_core_model_json_artifact
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.core.contracts.foundry import (
    ExecPlan,
    MethodExecutionBundle,
    MethodExecutionOccurrence,
    ProgramGraph,
)
from polisyos.core.contracts.runtime import GraphMethodExecutionSelection
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal


def launch_completed_workflow(
    service: Any, request: WorkflowRunRequest, principal: RuntimePrincipal
) -> tuple[Any, Any]:
    """Launch and dispatch one actual authenticated workflow without finalizing it."""
    assert principal.authenticated and principal.fixture_identity
    with tenant_scope(None, tenant_id=principal.tenant_id, cell_id=principal.cell_id):
        launch = service.launch_workflow_run(request, principal=principal)
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )
        == launch.job_id
    )
    job = service._control_store.get_job(launch.job_id)
    assert job is not None and job.state == "completed", job
    return launch, job


def launch_completed_ex_ante_source(
    service: Any, prepared: dict[str, Any], principal: RuntimePrincipal
) -> dict[str, Any]:
    """Execute prepared inputs through real Runtime, compiler and projection owners."""
    plan = ExecutionPlan(
        plan_id="completed_ex_ante_comparison",
        run_id="pending",
        method_dag=[
            MethodDagNode(
                node_id="ex_ante_node",
                method_fqn=prepared["method_fqn"],
                method_version=prepared["method_version"],
                backend=prepared["method_backend"],
                params={"poverty_line": None},
                reads_slots=["baseline", "scenario"],
                writes_slots=["result"],
            )
        ],
    )
    launch, job = launch_completed_workflow(
        service,
        WorkflowRunRequest(
            data_source={
                "data_snapshot_ref": prepared["data_snapshot_ref"].model_dump(mode="json")
            },
            trinity_bundle_ref=prepared["trinity_ref"],
            registry_bundle_ref=prepared["registry_ref"],
            params={
                "control_plane_transition": "legacy_shadow",
                "capture_method_metric_environment": True,
                "method_metric_bindings": [
                    {
                        "objective_id": "objective_ex_ante_mean_change",
                        "node_id": "ex_ante_node",
                        "output_slot_id": "result",
                    }
                ],
                "execution_plan": plan.model_dump(mode="json"),
            },
        ),
        principal,
    )
    with tenant_scope(None, tenant_id=principal.tenant_id, cell_id=principal.cell_id):
        selected = service.get_method_execution_selection(
            run_id=launch.run_id, tenant_id=principal.tenant_id, cell_id=principal.cell_id
        )
        score = service.read_current_completed_ex_ante_candidate_score(
            run_id=launch.run_id, tenant_id=principal.tenant_id, cell_id=principal.cell_id
        )
    assert isinstance(selected, GraphMethodExecutionSelection), selected
    assert selected.metric_verification_status == "verified", selected
    assert selected.source_candidate_ref == prepared["candidate_ref"]
    assert score.status == "selected", score.limitations
    assert score.authority_status == "candidate_only"
    return {"launch": launch, "job": job, "selected": selected, "score": score}


def reconcile_observed_method_occurrence(
    store: Any, bundle: MethodExecutionBundle, *, occurrence_id: str | None
) -> MethodExecutionOccurrence:
    """Reconcile full invocation captures, then join the observed method by identity."""
    graph = validate_core_model_json_artifact(ProgramGraph, store, bundle.program_graph_ref)
    plan = validate_core_model_json_artifact(ExecPlan, store, bundle.exec_plan_ref)
    assert artifact_ref_identity_key(plan.program_ref) == artifact_ref_identity_key(
        bundle.program_graph_ref
    )
    nodes = {node.node_id: node for node in graph.nodes}
    assert len(nodes) == len(graph.nodes)
    assert set(plan.order) == set(nodes)
    assert len(plan.order) == len(set(plan.order))
    assert bundle.occurrences
    invocations: dict[str, list[MethodExecutionOccurrence]] = {}
    for row in bundle.occurrences:
        assert 0 <= row.plan_index < len(plan.order), row
        assert plan.order[row.plan_index] == row.node_id, row
        assert row.node_kind == nodes[row.node_id].node_kind, row
        assert row.status == "succeeded", row
        invocations.setdefault(row.invocation_id, []).append(row)
    for rows in invocations.values():
        ordered = sorted(rows, key=lambda row: row.plan_index)
        assert [row.plan_index for row in ordered] == list(range(len(plan.order)))
        assert [row.node_id for row in ordered] == plan.order
    assert occurrence_id is not None
    matches = [row for row in bundle.occurrences if row.occurrence_id == occurrence_id]
    assert len(matches) == 1, occurrence_id
    selected = matches[0]
    assert selected.node_kind == "method", selected
    return selected
