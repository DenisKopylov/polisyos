"""The fresh SQL profile recognizes the actual compiler closure and refuses extra reads."""

from __future__ import annotations

from types import SimpleNamespace

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
from polisyos.core.contracts.foundry import LoweredIRRef, ProgramEdge, ProgramNode, ProgramOp
from polisyos.core.security import AccessScope, reset_current_access_scope, set_current_access_scope
from polisyos.foundry.compile._graph import build_program_graph
from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.runtime.http.services.debug_registered_sql import (
    _is_supported_restricted_graph,
    read_registered_sql_source_use,
)


def _actual_compiler_graph(
    *, method_node_id: str = "ex_ante_node", reads: tuple[str, ...] = ("baseline", "scenario")
):
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    signature = ExAnteSimulationEstimator.signature
    plan = ExecutionPlan(
        plan_id="selected-ex-ante",
        method_dag=[
            MethodDagNode(
                node_id=method_node_id,
                method_fqn=signature.fqn,
                method_version=signature.version,
                backend=signature.execution_backend.value,
                params={"poverty_line": None},
                reads_slots=list(reads),
                writes_slots=["result"],
            )
        ],
    )
    graph, _ = build_program_graph(
        None,
        ir_ref=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="ir.trinity_bundle",
            media_type="application/json",
        ),
        lowered_ir_ref=LoweredIRRef(
            artifact_id="sha256:" + "b" * 64,
            kind="foundry.lowered_ir",
            media_type="application/json",
        ),
        mechanisms=[],
        constraint_ids=[],
        method_plan=plan,
    )
    return graph


def test_actual_compiler_housekeeping_is_supported() -> None:
    for method_node_id in ("ex_ante_node", "op.merge_state", "op.check_constraints"):
        for reads in (("baseline", "scenario"), ("scenario", "baseline")):
            graph = _actual_compiler_graph(method_node_id=method_node_id, reads=reads)
            assert graph.nodes[0].inputs == list(reads)
            assert _is_supported_restricted_graph(graph, method_node_id=method_node_id)


def test_actual_compiler_graph_with_unsupported_dependency_is_refused() -> None:
    graph = _actual_compiler_graph()
    method, merge, check = graph.nodes
    changed_check = check.model_copy(
        update={"op": ProgramOp(op_kind="check_constraints", params={"constraint_ids": ["x"]})}
    )
    extra = ProgramNode(node_id="hidden", node_kind="op", op=ProgramOp(op_kind="read_view"))
    adversaries = {
        "hidden_read": graph.model_copy(
            update={
                "nodes": [
                    method.model_copy(update={"inputs": ["baseline", "scenario", "hidden"]}),
                    merge,
                    check,
                ]
            }
        ),
        "duplicate_read": graph.model_copy(
            update={
                "nodes": [
                    method.model_copy(update={"inputs": ["baseline", "baseline"]}),
                    merge,
                    check,
                ]
            }
        ),
        "constraint": graph.model_copy(update={"nodes": [method, merge, changed_check]}),
        "extra_operation": graph.model_copy(update={"nodes": [method, merge, check, extra]}),
        "omitted_edge": graph.model_copy(
            update={"edges": [ProgramEdge(src="op.merge_state", dst="op.check_constraints")]}
        ),
        "reordered_nodes": graph.model_copy(update={"nodes": [method, check, merge]}),
    }

    for name, changed in adversaries.items():
        assert not _is_supported_restricted_graph(changed, method_node_id="ex_ante_node"), name


def test_source_use_requires_the_callers_exact_ambient_tenant_and_cell() -> None:
    run = SimpleNamespace(details=SimpleNamespace(tenant_id="tenant-a", cell_id="cell-a"))
    denied_scopes = (
        None,
        AccessScope.for_service(tenant_id="tenant-a", cell_id="cell-b", spiffe_id="spiffe://b"),
        AccessScope.for_service(tenant_id="tenant-b", cell_id="cell-a", spiffe_id="spiffe://b"),
    )
    for scope in denied_scopes:
        token = set_current_access_scope(scope)
        try:
            result = read_registered_sql_source_use(
                store=object(), control=object(), run=run, simulation_ref=object()
            )
        finally:
            reset_current_access_scope(token)
        assert result.status == "unknown"
        assert result.limitations == ("registered_sql_caller_scope_not_established",)
