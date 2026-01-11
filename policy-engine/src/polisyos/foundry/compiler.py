from __future__ import annotations

from dataclasses import dataclass
from graphlib import TopologicalSorter
from typing import Iterable

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecPlanRef,
    PolicySurfaceIRRef,
    ProgramEdge,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    ProgramOp,
)
from polisyos.ir.kernel import MechanismTypeRegistry, MergeRuleRegistry, SlotRegistry, UnitsRegistry
from polisyos.ir.surface import InterventionSpec, PolicySurfaceIR, schedule_range
from polisyos.foundry.layout import SlotLayout, build_slot_layout
from polisyos.foundry.treasury import TreasuryPlan, build_treasury_plan


@dataclass
class CompileArtifacts:
    policy_ref: PolicySurfaceIRRef
    program_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    slot_layout_ref: ArtifactRef | None = None
    treasury_plan_ref: ArtifactRef | None = None


def _as_policy_ref(ref: ArtifactRef | PolicySurfaceIRRef) -> PolicySurfaceIRRef:
    if isinstance(ref, PolicySurfaceIRRef):
        return ref
    return PolicySurfaceIRRef(artifact_id=ref.artifact_id)


def put_policy_surface(
    store: FileSystemCAS,
    policy: PolicySurfaceIR,
    *,
    semantic_only: bool = True,
    mechanism_registry: MechanismTypeRegistry | None = None,
    units_registry: UnitsRegistry | None = None,
) -> PolicySurfaceIRRef:
    payload = (
        policy.semantic_fingerprint_payload(
            mechanism_registry=mechanism_registry,
            units_registry=units_registry,
        )
        if semantic_only
        else policy
    )
    ref = store.put_json(
        payload,
        PutOptions(
            kind="ir.policy_surface",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.PolicySurfaceIR", version=policy.schema_version),
        ),
    )
    return _as_policy_ref(ref)


def compile_surface_policy(
    store: FileSystemCAS,
    policy: PolicySurfaceIR,
    *,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
    units_registry: UnitsRegistry | None = None,
    policy_ref: ArtifactRef | None = None,
) -> CompileArtifacts:
    if policy_ref is None:
        policy_ref = put_policy_surface(
            store,
            policy,
            mechanism_registry=mechanism_registry,
            units_registry=units_registry,
        )
    policy_ref = _as_policy_ref(policy_ref)
    program_graph = _build_program_graph(
        policy,
        policy_ref,
        store,
        mechanism_registry=mechanism_registry,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )
    program_inputs = _program_graph_inputs(program_graph, policy_ref, policy)
    program_ref = store.put_json(
        program_graph,
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.1.0"),
            inputs=program_inputs,
        ),
    )
    program_graph_ref = ProgramGraphRef(artifact_id=program_ref.artifact_id)

    order = _build_exec_order(program_graph)
    exec_plan = ExecPlan(program_ref=program_graph_ref, order=order)
    exec_plan_payload_ref = store.put_json(
        exec_plan,
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.1.0"),
            inputs=[InputRef(artifact_id=program_graph_ref.artifact_id, role="program_graph")],
        ),
    )
    exec_plan_ref = ExecPlanRef(artifact_id=exec_plan_payload_ref.artifact_id)
    slot_layout = build_slot_layout(slot_registry)
    slot_layout_ref = store.put_json(
        slot_layout,
        PutOptions(
            kind="foundry.slot_layout",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.SlotLayout", version=slot_layout.schema_version),
            inputs=[InputRef(artifact_id=program_graph_ref.artifact_id, role="program_graph")],
        ),
    )
    treasury_plan = build_treasury_plan(program_graph)
    treasury_plan_ref = store.put_json(
        treasury_plan,
        PutOptions(
            kind="foundry.treasury_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.TreasuryPlan", version=treasury_plan.schema_version),
            inputs=[InputRef(artifact_id=program_ref.artifact_id, role="program_graph")],
        ),
    )
    return CompileArtifacts(
        policy_ref=policy_ref,
        program_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        slot_layout_ref=slot_layout_ref,
        treasury_plan_ref=treasury_plan_ref,
    )


def _program_graph_inputs(
    program_graph: ProgramGraph,
    policy_ref: ArtifactRef,
    policy: PolicySurfaceIR,
) -> list[InputRef]:
    inputs = [InputRef(artifact_id=policy_ref.artifact_id, role="ir")]
    if policy.semantic.registry_bundle_ref:
        inputs.append(
            InputRef(
                artifact_id=ArtifactID.model_validate(policy.semantic.registry_bundle_ref),
                role="registry_bundle",
            )
        )
    for node in program_graph.nodes:
        if node.params_ref is None:
            continue
        inputs.append(
            InputRef(
                artifact_id=node.params_ref.artifact_id,
                role=f"params:{node.node_id}",
            )
        )
    return inputs


def _build_program_graph(
    policy: PolicySurfaceIR,
    policy_ref: ArtifactRef,
    store: FileSystemCAS,
    *,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> ProgramGraph:
    nodes: list[ProgramNode] = []
    edges: list[ProgramEdge] = []

    _validate_slot_conflicts(
        policy.semantic.interventions,
        mechanism_registry=mechanism_registry,
        slot_registry=slot_registry,
        merge_registry=merge_registry,
    )

    for intervention in sorted(
        policy.semantic.interventions, key=lambda item: item.intervention_id
    ):
        params_ref = _put_intervention_payload(store, intervention)
        mech = mechanism_registry.mechanisms.get(intervention.kind)
        inputs = list(mech.reads_slots) if mech else []
        outputs = list(mech.writes_slots) if mech else []
        existing = {node.node_id for node in nodes}
        mask_id = _unique_node_id(f"op.mask.{intervention.intervention_id}", existing)
        existing.add(mask_id)
        apply_id = _unique_node_id(intervention.intervention_id, existing)
        nodes.append(
            ProgramNode(
                node_id=mask_id,
                node_kind="op",
                op=ProgramOp(
                    op_kind="make_mask",
                    params={
                        "intervention_id": intervention.intervention_id,
                        "selector": intervention.target.model_dump(),
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

    op_nodes, op_edges = _build_op_nodes(nodes, policy)
    nodes.extend(op_nodes)
    edges.extend(op_edges)
    entrypoints = _entrypoints(nodes, edges)
    return ProgramGraph(
        ir_ref=policy_ref,
        nodes=nodes,
        edges=edges,
        entrypoints=entrypoints,
        notes=[],
    )


def _put_intervention_payload(store: FileSystemCAS, intervention: InterventionSpec) -> ArtifactRef:
    payload = {
        "intervention_id": intervention.intervention_id,
        "kind": intervention.kind,
        "target": intervention.target.model_dump(),
        "schedule": intervention.schedule.model_dump(),
        "params": intervention.params,
        "priority": intervention.priority,
        "notes": intervention.notes,
    }
    return store.put_json(
        payload,
        PutOptions(kind="ir.intervention_payload", media_type="application/json"),
    )


def _build_exec_order(program_graph: ProgramGraph) -> list[str]:
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
    except Exception as exc:
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


def _build_op_nodes(
    nodes: list[ProgramNode], policy: PolicySurfaceIR
) -> tuple[list[ProgramNode], list[ProgramEdge]]:
    existing = {node.node_id for node in nodes}
    merge_id = _unique_node_id("op.merge_state", existing)
    existing.add(merge_id)
    check_id = _unique_node_id("op.check_constraints", existing)

    constraint_ids = sorted(
        {constraint.constraint_id for constraint in policy.semantic.constraints}
    )

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
        if node.node_kind == "op" and node.op and node.op.op_kind == "apply_mechanism":
            op_edges.append(ProgramEdge(src=node.node_id, dst=merge_id, relation="depends_on"))
    op_edges.append(ProgramEdge(src=merge_id, dst=check_id, relation="depends_on"))
    return op_nodes, op_edges


def _validate_slot_conflicts(
    interventions: Iterable[InterventionSpec],
    *,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
    merge_registry: MergeRuleRegistry,
) -> None:
    writers: dict[str, list[InterventionSpec]] = {}
    for intervention in interventions:
        mech = mechanism_registry.mechanisms.get(intervention.kind)
        if mech is None:
            continue
        for slot_id in mech.writes_slots:
            writers.setdefault(slot_id, []).append(intervention)

    for slot_id, interventions_for_slot in writers.items():
        if len(interventions_for_slot) < 2:
            continue
        slot = slot_registry.slots.get(slot_id)
        if slot is None:
            raise ValueError(f"Unknown slot '{slot_id}' for merge evaluation")
        merge_rule_id = slot.merge_rule.rule_id
        rule = merge_registry.rules.get(merge_rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{merge_rule_id}' for slot '{slot_id}'")
        overlapping: set[str] = set()
        interventions_list = list(interventions_for_slot)
        for idx, left in enumerate(interventions_list):
            for right in interventions_list[idx + 1 :]:
                left_start, left_end = schedule_range(left.schedule)
                right_start, right_end = schedule_range(right.schedule)
                if not (left_end < right_start or right_end < left_start):
                    overlapping.add(left.intervention_id)
                    overlapping.add(right.intervention_id)

        if not overlapping:
            continue

        if rule.kind.value == "error":
            ids = ", ".join(sorted(overlapping))
            raise ValueError(f"Merge conflict for slot '{slot_id}': {ids}")
        if rule.kind.value == "priority":
            missing = [
                i.intervention_id
                for i in interventions_list
                if i.intervention_id in overlapping and i.priority is None
            ]
            if missing:
                raise ValueError(
                    f"Merge rule 'priority' requires priority for: {', '.join(sorted(missing))}"
                )
