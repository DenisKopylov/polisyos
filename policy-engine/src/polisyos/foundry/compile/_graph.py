"""Public compile graph module API."""

from __future__ import annotations

from collections.abc import Iterable
from graphlib import TopologicalSorter
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.execution_plan import ExecutionPlan
from polisyos.core.contracts.foundry import (
    LoweredIRRef,
    LoweredMechanism,
    ProgramEdge,
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)
from polisyos.foundry.methods.base import MethodKind
from polisyos.foundry.methods.registry import MethodRegistry


def build_program_graph(
    store: Any,
    *,
    ir_ref: ArtifactRef,
    lowered_ir_ref: LoweredIRRef,
    mechanisms: Iterable[LoweredMechanism],
    constraint_ids: list[str],
    method_plan: ExecutionPlan | None = None,
) -> tuple[ProgramGraph, dict[str, ArtifactRef]]:
    """Build program graph."""
    _ = store
    nodes: list[ProgramNode] = []
    edges: list[ProgramEdge] = []
    params_refs: dict[str, ArtifactRef] = {}

    existing: set[str] = set()
    for mechanism in sorted(mechanisms, key=lambda item: item.binding_id):
        params_ref = mechanism.effective_params_ref
        primary_id = (
            mechanism.intervention_ids[0] if mechanism.intervention_ids else mechanism.binding_id
        )

        mask_id = _unique_node_id(f"op.mask.{primary_id}", existing)
        existing.add(mask_id)
        apply_id = _unique_node_id(primary_id, existing)
        existing.add(apply_id)

        nodes.append(
            ProgramNode(
                node_id=mask_id,
                node_kind="op",
                op=ProgramOp(
                    op_kind="make_mask",
                    params={
                        "binding_id": mechanism.binding_id,
                        "intervention_ids": list(mechanism.intervention_ids),
                        "selector": _model_dump(mechanism.target_selector),
                    },
                ),
            )
        )
        nodes.append(
            ProgramNode(
                node_id=apply_id,
                node_kind="op",
                mechanism_type=mechanism.mechanism_id,
                params_ref=params_ref,
                op=ProgramOp(
                    op_kind="apply_mechanism",
                    params={
                        "mask_id": mask_id,
                        "binding_id": mechanism.binding_id,
                        "selected_fidelity": mechanism.selected_fidelity,
                    },
                ),
                inputs=list(mechanism.inputs),
                outputs=list(mechanism.outputs),
            )
        )
        edges.append(ProgramEdge(src=mask_id, dst=apply_id, relation="depends_on"))
        if params_ref is not None:
            params_refs[apply_id] = params_ref

    method_node_ids: set[str] = set()
    planned_method_edges: set[tuple[str, str]] = set()
    if method_plan is not None:
        method_nodes, method_edges = _method_plan_graph_nodes(
            method_plan, existing, existing_nodes=nodes
        )
        method_node_ids = {node.node_id for node in method_nodes}
        planned_method_edges = {(edge.src, edge.dst) for edge in method_edges}
        nodes.extend(method_nodes)
        edges.extend(method_edges)

    slot_edges = _slot_dependency_edges(nodes)
    if method_plan is not None:
        for edge in slot_edges:
            if edge.src in method_node_ids or edge.dst in method_node_ids:
                if (
                    edge.src not in method_node_ids
                    or edge.dst not in method_node_ids
                    or (edge.src, edge.dst) not in planned_method_edges
                ):
                    raise ValueError("execution_plan_method_slot_dependency_not_declared")
    if slot_edges:
        edge_keys = {(edge.src, edge.dst, edge.relation) for edge in edges}
        for edge in slot_edges:
            key = (edge.src, edge.dst, edge.relation)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append(edge)

    op_nodes, op_edges = _build_op_nodes(nodes, constraint_ids)
    nodes.extend(op_nodes)
    edges.extend(op_edges)

    entrypoints = _entrypoints(nodes, edges)
    graph = ProgramGraph(
        ir_ref=ir_ref,
        lowered_ir_ref=lowered_ir_ref,
        nodes=nodes,
        edges=edges,
        entrypoints=entrypoints,
        notes=[],
    )
    return graph, params_refs


def _method_plan_graph_nodes(
    plan: ExecutionPlan,
    existing_node_ids: set[str],
    *,
    existing_nodes: list[ProgramNode],
) -> tuple[list[ProgramNode], list[ProgramEdge]]:
    """Adapt the whole supported method DAG to the existing graph ABI or refuse it."""
    method_ids = [node.node_id for node in plan.method_dag]
    if len(method_ids) != len(set(method_ids)):
        raise ValueError("execution_plan_method_node_ids_not_unique")
    if existing_node_ids.intersection(method_ids):
        raise ValueError("execution_plan_method_node_id_collides_with_compiled_graph")
    method_id_set = set(method_ids)
    registry = MethodRegistry.get_instance()
    program_nodes: list[ProgramNode] = []
    dependencies: set[tuple[str, str]] = set()
    return_slots_by_node: dict[str, set[str]] = {}
    read_slots_by_node: dict[str, set[str]] = {}
    for source in plan.method_dag:
        if source.incompatibilities or source.deprecations:
            raise ValueError("execution_plan_method_status_fields_unsupported")
        signature = registry.get_signature(source.method_fqn)
        if signature is None or signature.fqn != source.method_fqn:
            raise ValueError("execution_plan_method_exact_signature_unavailable")
        if signature.kind is not MethodKind.PURE:
            raise ValueError("execution_plan_method_kind_unsupported")
        if source.method_version is None or source.method_version != signature.version:
            raise ValueError("execution_plan_method_version_mismatch")
        if source.backend is None or source.backend != signature.execution_backend.value:
            raise ValueError("execution_plan_method_backend_mismatch")
        input_slots = [slot.name for slot in signature.input_slots]
        output_slots = [slot.name for slot in signature.output_slots]
        if (
            len(source.reads_slots) != len(set(source.reads_slots))
            or set(source.reads_slots) != set(input_slots)
            or len(source.writes_slots) != len(set(source.writes_slots))
            or set(source.writes_slots) != set(output_slots)
        ):
            raise ValueError("execution_plan_method_slots_mismatch")
        parameter_names = {parameter.name for parameter in signature.parameters}
        if any(type(name) is not str for name in source.params):
            raise ValueError("execution_plan_method_parameter_names_invalid")
        if set(source.params) - parameter_names:
            raise ValueError("execution_plan_method_unknown_parameter")
        if len(source.depends_on) != len(set(source.depends_on)):
            raise ValueError("execution_plan_method_dependencies_not_unique")
        dependencies.update((dependency, source.node_id) for dependency in source.depends_on)
        return_slots_by_node[source.node_id] = set(output_slots)
        read_slots_by_node[source.node_id] = set(source.reads_slots)
        program_nodes.append(
            ProgramNode(
                node_id=source.node_id,
                node_kind="method",
                method_fqn=source.method_fqn,
                method_version=source.method_version,
                method_params=dict(source.params),
                inputs=list(source.reads_slots),
                # Method returns are captured by the selected metric binding. ProgramNode.outputs
                # is the graph state-patch namespace, so pure returns stay out of that plane.
                outputs=[],
            )
        )
    explicit_edges: set[tuple[str, str]] = set()
    for source in plan.method_edges:
        if source.relation != "depends_on":
            raise ValueError("execution_plan_method_edge_relation_unsupported")
        edge_key = (source.src, source.dst)
        if edge_key in explicit_edges:
            raise ValueError("execution_plan_method_edges_not_unique")
        explicit_edges.add(edge_key)
    dependencies.update(explicit_edges)
    if any(
        source not in method_id_set or target not in method_id_set
        for source, target in dependencies
    ):
        raise ValueError("execution_plan_method_dependency_endpoint_missing")
    # The adapter has no typed transfer between a method return and a later graph
    # node. Refuse direct slot matches and declared dependency paths that could
    # carry a return under a different alias, before ProgramGraph construction.
    all_return_slots = (
        set().union(*return_slots_by_node.values()) if return_slots_by_node else set()
    )
    all_method_reads = set().union(*read_slots_by_node.values()) if read_slots_by_node else set()
    if all_return_slots.intersection(all_method_reads):
        raise ValueError("execution_plan_method_return_slot_consumer_unsupported")

    dependents: dict[str, set[str]] = {node_id: set() for node_id in method_ids}
    for source, target in dependencies:
        dependents[source].add(target)
    for producer_id, produced_slots in return_slots_by_node.items():
        if not produced_slots:
            continue
        pending = list(dependents[producer_id])
        visited: set[str] = set()
        while pending:
            consumer_id = pending.pop()
            if consumer_id in visited:
                continue
            visited.add(consumer_id)
            if read_slots_by_node[consumer_id]:
                raise ValueError("execution_plan_method_return_slot_consumer_unsupported")
            pending.extend(dependents[consumer_id])

    graph_method_nodes = [
        node
        for node in existing_nodes
        if node.node_kind == "mechanism"
        or (
            node.node_kind == "op"
            and node.op is not None
            and node.op.op_kind in {"apply_mechanism", "apply_method"}
        )
    ]
    graph_inputs = {slot for node in graph_method_nodes for slot in node.inputs}
    graph_outputs = {slot for node in graph_method_nodes for slot in node.outputs}
    if all_return_slots.intersection(graph_inputs):
        raise ValueError("execution_plan_method_return_slot_consumer_unsupported")
    if all_method_reads.intersection(graph_outputs):
        raise ValueError("execution_plan_method_graph_data_transfer_unsupported")

    sorter = TopologicalSorter()
    for method_id in method_ids:
        sorter.add(method_id)
    for source, target in dependencies:
        sorter.add(target, source)
    try:
        tuple(sorter.static_order())
    except Exception as exc:
        raise ValueError("execution_plan_method_dependency_cycle") from exc
    program_edges = [
        ProgramEdge(src=source, dst=target, relation="depends_on")
        for source, target in sorted(dependencies)
    ]
    return program_nodes, program_edges


def build_exec_order(program_graph: ProgramGraph) -> list[str]:
    """Build exec order."""
    if not program_graph.edges:
        return sorted(node.node_id for node in program_graph.nodes)

    sorter = TopologicalSorter()
    node_ids = sorted(node.node_id for node in program_graph.nodes)
    for node_id in node_ids:
        sorter.add(node_id)
    for edge in sorted(program_graph.edges, key=lambda item: (item.src, item.dst, item.relation)):
        sorter.add(edge.dst, edge.src)
    try:
        return list(sorter.static_order())
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"ProgramGraph has cycles: {exc}") from exc


def _entrypoints(nodes: list[ProgramNode], edges: list[ProgramEdge]) -> list[str]:
    if not nodes:
        return []
    incoming: dict[str, int] = {node.node_id: 0 for node in nodes}
    for edge in edges:
        incoming[edge.dst] = incoming.get(edge.dst, 0) + 1
    return sorted([node_id for node_id, count in incoming.items() if count == 0])


def _unique_node_id(base_id: str, existing: set[str]) -> str:
    if base_id not in existing:
        return base_id
    suffix = 2
    while f"{base_id}_{suffix}" in existing:
        suffix += 1
    return f"{base_id}_{suffix}"


def _slot_dependency_edges(nodes: list[ProgramNode]) -> list[ProgramEdge]:
    def _is_mechanism_node(node: ProgramNode) -> bool:
        if node.node_kind in {"mechanism", "method"}:
            return True
        return bool(node.op and node.op.op_kind in {"apply_mechanism", "apply_method"})

    mech_nodes = [node for node in nodes if _is_mechanism_node(node)]
    edge_keys: set[tuple[str, str]] = set()
    edges: list[ProgramEdge] = []
    for writer in mech_nodes:
        if not writer.outputs:
            continue
        writer_slots = set(writer.outputs)
        for reader in mech_nodes:
            if writer.node_id == reader.node_id or not reader.inputs:
                continue
            reader_slots = set(reader.inputs) - set(reader.outputs)
            if writer_slots.intersection(reader_slots):
                key = (writer.node_id, reader.node_id)
                if key in edge_keys:
                    continue
                edge_keys.add(key)
                edges.append(
                    ProgramEdge(src=writer.node_id, dst=reader.node_id, relation="depends_on")
                )
    edges.sort(key=lambda edge: (edge.src, edge.dst, edge.relation))
    return edges


def _build_op_nodes(
    nodes: list[ProgramNode], constraint_ids: list[str]
) -> tuple[list[ProgramNode], list[ProgramEdge]]:
    existing = {node.node_id for node in nodes}
    merge_id = _unique_node_id("op.merge_state", existing)
    existing.add(merge_id)
    check_id = _unique_node_id("op.check_constraints", existing)

    op_nodes = [
        ProgramNode(
            node_id=merge_id,
            node_kind="op",
            mechanism_type=None,
            op=ProgramOp(op_kind="merge_state"),
        ),
        ProgramNode(
            node_id=check_id,
            node_kind="op",
            mechanism_type=None,
            op=ProgramOp(op_kind="check_constraints", params={"constraint_ids": constraint_ids}),
        ),
    ]

    op_edges: list[ProgramEdge] = []
    for node in nodes:
        if node.node_kind == "method":
            op_edges.append(ProgramEdge(src=node.node_id, dst=merge_id, relation="depends_on"))
        if (
            node.node_kind == "op"
            and node.op
            and node.op.op_kind
            in {
                "apply_mechanism",
                "apply_method",
            }
        ):
            op_edges.append(ProgramEdge(src=node.node_id, dst=merge_id, relation="depends_on"))
    op_edges.append(ProgramEdge(src=merge_id, dst=check_id, relation="depends_on"))
    return op_nodes, op_edges


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value
