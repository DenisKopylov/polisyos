"""Public compile graph module API."""
from __future__ import annotations

from graphlib import TopologicalSorter
from typing import Any, Iterable

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    LoweredIRRef,
    LoweredMechanism,
    ProgramEdge,
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)


def build_program_graph(
    store: Any,
    *,
    ir_ref: ArtifactRef,
    lowered_ir_ref: LoweredIRRef,
    mechanisms: Iterable[LoweredMechanism],
    constraint_ids: list[str],
) -> tuple[ProgramGraph, dict[str, ArtifactRef]]:
    """Build program graph."""
    _ = store
    nodes: list[ProgramNode] = []
    edges: list[ProgramEdge] = []
    params_refs: dict[str, ArtifactRef] = {}

    existing: set[str] = set()
    for mechanism in sorted(mechanisms, key=lambda item: item.binding_id):
        params_ref = mechanism.effective_params_ref
        primary_id = mechanism.intervention_ids[0] if mechanism.intervention_ids else mechanism.binding_id

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

    slot_edges = _slot_dependency_edges(nodes)
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
        if node.node_kind == "op" and node.op and node.op.op_kind in {
            "apply_mechanism",
            "apply_method",
        }:
            op_edges.append(ProgramEdge(src=node.node_id, dst=merge_id, relation="depends_on"))
    op_edges.append(ProgramEdge(src=merge_id, dst=check_id, relation="depends_on"))
    return op_nodes, op_edges


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value
