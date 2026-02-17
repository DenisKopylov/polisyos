from __future__ import annotations

from graphlib import TopologicalSorter
from typing import Any, Callable, Iterable, Protocol

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ProgramEdge,
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)


class InterventionLike(Protocol):
    intervention_id: str
    kind: str
    target: Any
    schedule: Any
    params: dict[str, Any]
    priority: int | None
    notes: list[str]


def put_intervention_payload(store: FileSystemCAS, intervention: InterventionLike) -> ArtifactRef:
    payload = {
        "intervention_id": intervention.intervention_id,
        "kind": intervention.kind,
        "target": _model_dump(intervention.target),
        "schedule": _model_dump(intervention.schedule),
        "params": intervention.params,
        "priority": intervention.priority,
        "notes": getattr(intervention, "notes", []),
    }
    return store.put_json(
        payload,
        PutOptions(kind="ir.intervention_payload", media_type="application/json"),
    )


def build_program_graph(
    store: FileSystemCAS,
    *,
    ir_ref: ArtifactRef,
    interventions: Iterable[InterventionLike],
    resolve_slots: Callable[[InterventionLike], tuple[list[str], list[str]]],
    constraint_ids: list[str],
) -> tuple[ProgramGraph, dict[str, ArtifactRef]]:
    nodes: list[ProgramNode] = []
    edges: list[ProgramEdge] = []
    params_refs: dict[str, ArtifactRef] = {}

    existing: set[str] = set()
    for intervention in sorted(interventions, key=lambda item: item.intervention_id):
        params_ref = put_intervention_payload(store, intervention)
        inputs, outputs = resolve_slots(intervention)

        mask_id = _unique_node_id(f"op.mask.{intervention.intervention_id}", existing)
        existing.add(mask_id)
        apply_id = _unique_node_id(intervention.intervention_id, existing)
        existing.add(apply_id)

        nodes.append(
            ProgramNode(
                node_id=mask_id,
                node_kind="op",
                op=ProgramOp(
                    op_kind="make_mask",
                    params={
                        "intervention_id": intervention.intervention_id,
                        "selector": _model_dump(intervention.target),
                    },
                ),
            )
        )
        nodes.append(
            ProgramNode(
                node_id=apply_id,
                node_kind="op",
                mechanism_type=intervention.kind,
                params_ref=params_ref,
                op=ProgramOp(
                    op_kind="apply_mechanism",
                    params={"mask_id": mask_id},
                ),
                inputs=inputs,
                outputs=outputs,
            )
        )
        edges.append(ProgramEdge(src=mask_id, dst=apply_id, relation="depends_on"))
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
        nodes=nodes,
        edges=edges,
        entrypoints=entrypoints,
        notes=[],
    )
    return graph, params_refs


def build_exec_order(program_graph: ProgramGraph) -> list[str]:
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
        return value.model_dump()
    return value
