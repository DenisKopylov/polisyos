"""Compile real selected method bindings through canonical engine state views."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import pytest
from unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
    _exercise_public_execute_method_metric_source,
)

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import (
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.core.contracts.foundry import (
    METHOD_METRIC_BINDING_LIMIT,
    ExecPlan,
    MethodMetricBindingSet,
    ProgramGraph,
)
from polisyos.core.run.context import RunContext
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_METHOD_METRIC_BINDING_SET_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.orchestration.llm.cycle import persist_candidate_execution_plan

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def selected_compile_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Reuse actual prepared selected inputs; no execute or completion is fabricated."""
    prepared = _exercise_public_execute_method_metric_source(
        tmp_path / "inputs", monkeypatch, prepare_only=True
    )
    store = prepared["store"]
    original = validate_core_model_json_artifact(TrinityBundle, store, prepared["trinity_ref"])
    payload = original.model_dump(mode="json")
    base_objective = payload["problem_frame"]["objectives"][0]
    selections = [
        {
            "objective_id": f"objective_state_view_{index}",
            "node_id": f"ex_ante_node_{index}",
            "output_slot_id": "result",
        }
        for index in range(3)
    ]
    payload["problem_frame"]["objectives"] = [
        {**base_objective, "objective_id": row["objective_id"]} for row in selections
    ]
    policy = TrinityBundle.model_validate(payload)
    policy_ref = store.put_json(
        policy,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(prepared["trinity_ref"], role="source_policy")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    plan = ExecutionPlan(
        plan_id="state_view_selected_plan",
        run_id="R_compile_state_view",
        method_dag=[
            MethodDagNode(
                node_id=row["node_id"],
                method_fqn=prepared["method_fqn"],
                method_version=prepared["method_version"],
                backend=prepared["method_backend"],
                depends_on=[],
                params={"poverty_line": None},
                reads_slots=["baseline", "scenario"],
                writes_slots=["result"],
            )
            for row in selections
        ],
    )
    plan_ref, exact_policy_ref = persist_candidate_execution_plan(store, plan, policy_ref)
    run = RunContext.start(
        store=store,
        registry_bundle=prepared["registry_ref"],
        run_id="R_compile_state_view",
        run_dir=tmp_path / "compile-run",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("tests.compile_state_view"),
        foundry=DefaultFoundryPort(),
    )
    state = ExperimentState(
        run_id="R_compile_state_view",
        execution_profile="dev",
        execution_plan_ref=plan_ref,
        inputs={
            INPUT_TRINITY_BUNDLE_REF: exact_policy_ref,
            INPUT_REGISTRY_BUNDLE_REF: prepared["registry_ref"],
        },
        params={"method_metric_bindings": selections},
    )
    return {"store": store, "ctx": ctx, "state": state, "selections": selections}


def test_real_engine_state_view_bindings_reach_actual_compiled_bundle(
    selected_compile_source: dict[str, Any],
) -> None:
    """The engine's admitted list view produces all three real selected bindings."""
    source = selected_compile_source
    node = CompileFoundryNode()
    state = source["state"]
    # Exercise the actual engine branch owner, not a hand-authored list subclass.
    fork = branch_state(state, write_paths=node.spec.state_writes, enforce_write_scope=True)
    inventory = fork.state.params["method_metric_bindings"]
    assert fork.journal.enforce_write_scope is True
    assert isinstance(inventory, list) and type(inventory) is not list
    assert inventory == source["selections"]
    registry = NodeRegistry()
    registry.register(node)
    result = WorkflowExecutor(source["ctx"], registry).execute(
        WorkflowSpec(
            workflow_id="compile_state_view",
            nodes=[
                NodeInvocation(alias="compile_foundry", node_id=node.spec.metadata.component_id)
            ],
        ),
        state,
    )
    assert result.report.status == "ok", result.report
    assert result.report.nodes[0].status == "ok"
    store = source["store"]
    binding_ref = result.state.artifacts_index[ARTIFACT_METHOD_METRIC_BINDING_SET_REF]
    graph_ref = result.state.artifacts_index[ARTIFACT_PROGRAM_GRAPH_REF]
    plan_ref = result.state.artifacts_index[ARTIFACT_EXEC_PLAN_REF]
    assert all(
        ref.manifest_profile_sha256 is not None for ref in (binding_ref, graph_ref, plan_ref)
    )
    bindings = validate_core_model_json_artifact(MethodMetricBindingSet, store, binding_ref)
    graph = validate_core_model_json_artifact(ProgramGraph, store, graph_ref)
    method_nodes = {node.node_id: node for node in graph.nodes if node.node_kind == "method"}
    selected_ids = {row["node_id"] for row in source["selections"]}
    assert set(method_nodes) == selected_ids
    assert all(node.outputs == [] for node in method_nodes.values())
    # Method returns are a separate plane from the producer's mandatory graph
    # operators. Inspect both without mistaking the method projection for the
    # complete ProgramGraph or pinning a magic full-graph node/edge count.
    merge_nodes = [
        node
        for node in graph.nodes
        if node.node_kind == "op" and node.op is not None and node.op.op_kind == "merge_state"
    ]
    check_nodes = [
        node
        for node in graph.nodes
        if node.node_kind == "op" and node.op is not None and node.op.op_kind == "check_constraints"
    ]
    assert len(merge_nodes) == len(check_nodes) == 1
    merge_id, check_id = merge_nodes[0].node_id, check_nodes[0].node_id
    actual_edges = {(edge.src, edge.dst, edge.relation) for edge in graph.edges}
    required_edges = {
        *((node_id, merge_id, "depends_on") for node_id in selected_ids),
        (merge_id, check_id, "depends_on"),
    }
    assert required_edges <= actual_edges
    assert not any(edge.src in selected_ids and edge.dst in selected_ids for edge in graph.edges)
    actual = [(row.objective_id, row.node_id, row.output_slot_id) for row in bindings.bindings]
    expected = [
        (row["objective_id"], row["node_id"], row["output_slot_id"]) for row in source["selections"]
    ]
    assert actual == expected and len(actual) == 3
    assert artifact_ref_identity_key(bindings.program_graph_ref) == artifact_ref_identity_key(
        graph_ref
    )
    plan = validate_core_model_json_artifact(ExecPlan, store, plan_ref)
    graph_ids = {node.node_id for node in graph.nodes}
    assert set(plan.order) == graph_ids and len(plan.order) == len(graph_ids)
    positions = {node_id: index for index, node_id in enumerate(plan.order)}
    assert all(
        positions[node_id] < positions[merge_id] < positions[check_id] for node_id in selected_ids
    )
    assert artifact_ref_identity_key(plan.program_ref) == artifact_ref_identity_key(graph_ref)
    binding_manifest = store.get_manifest(binding_ref)
    plan_manifest = store.get_manifest(plan_ref)
    assert input_ref_from_artifact_ref(graph_ref, role="program_graph") in binding_manifest.inputs
    assert (
        input_ref_from_artifact_ref(binding_ref, role="method_metric_bindings")
        in plan_manifest.inputs
    )
    # A real multi-method compilation remains outside the single-method rank profile.
    from polisyos.core.artifacts.registry import RegistryBundlePayload
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        _compiled_method_comparison_graph,
        _ProjectionReadBudget,
        _selected_ref,
    )

    policy = validate_core_model_json_artifact(TrinityBundle, store, bindings.policy_ref)
    registry_bundle = validate_core_model_json_artifact(
        RegistryBundlePayload, store, bindings.registry_bundle_ref
    )
    assert (
        _compiled_method_comparison_graph(
            store,
            graph=graph,
            graph_manifest=store.get_manifest(graph_ref),
            plan=plan,
            policy=policy,
            policy_ref=_selected_ref(bindings.policy_ref, kind="ir.trinity_bundle"),
            registry_bundle=registry_bundle,
            registry_bundle_ref=_selected_ref(
                bindings.registry_bundle_ref, kind="core.registry_bundle"
            ),
            registry_bundle_manifest=store.get_manifest(bindings.registry_bundle_ref),
            read_budget=_ProjectionReadBudget(),
        )
        is None
    )
    assert ARTIFACT_METHOD_METRIC_BINDING_SET_REF not in state.artifacts_index
    assert state.params["method_metric_bindings"] == source["selections"]


@pytest.mark.parametrize("kind", ["bool", "tuple", "object", "field_bool", "extra", "over_limit"])
def test_branched_invalid_binding_inventory_is_refused_before_foundry(
    selected_compile_source: dict[str, Any], kind: str
) -> None:
    """Admitting a canonical list view never relaxes JSON-array or strict DTO rules."""
    source = selected_compile_source
    selected = source["selections"][0]
    values = {
        "bool": True,
        "tuple": (selected,),
        "object": selected,
        "field_bool": [{**selected, "node_id": True}],
        "extra": [{**selected, "unclaimed": True}],
        "over_limit": [selected] * (METHOD_METRIC_BINDING_LIMIT + 1),
    }
    state = source["state"].model_copy(deep=True)
    state.params["method_metric_bindings"] = values[kind]
    calls: list[object] = []

    class CountingFoundry(DefaultFoundryPort):
        def compile(self, store, request):
            calls.append(request)
            return super().compile(store, request)

    node = CompileFoundryNode()
    ctx = replace(source["ctx"], foundry=CountingFoundry())
    fork = branch_state(state, write_paths=node.spec.state_writes, enforce_write_scope=True)
    assert fork.journal.enforce_write_scope is True
    outcome = node.execute(ctx, fork.state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "node.invalid_state"
    assert calls == []
    assert ARTIFACT_METHOD_METRIC_BINDING_SET_REF not in outcome.state.artifacts_index
