from __future__ import annotations

from dataclasses import dataclass
from graphlib import TopologicalSorter
from typing import Iterable

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.common.logger import get_logger
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
from polisyos.ir.kernel.mechanisms import resolve_mechanism_slots
from polisyos.ir.surface import InterventionSpec, PolicySurfaceIR, schedule_range
from polisyos.foundry.conflict_checker import CompileTimeConflictChecker, ConflictReport
from polisyos.foundry.cost_model import CostBudget, CostEstimate, CostModel
from polisyos.foundry.layout import SlotLayout, build_slot_layout
from polisyos.foundry.treasury import TreasuryPlan, build_treasury_plan
from polisyos.foundry.runtime.fingerprint import DeterminismTier, EnvironmentFingerprint
from polisyos.scientist.governance.profiles import ProfileLevel, ValidationProfile


@dataclass
class SimulationConfig:
    """
    Simulation determinism configuration captured at compile time.
    """

    determinism_tier: DeterminismTier = DeterminismTier.NONDETERMINISTIC
    random_seed: int = 42
    environment_fingerprint: EnvironmentFingerprint | None = None

    def __post_init__(self) -> None:
        if self.environment_fingerprint is None:
            self.environment_fingerprint = EnvironmentFingerprint.capture(
                tier=self.determinism_tier,
                seed=self.random_seed,
            )
        warnings = self.environment_fingerprint.validate_for_tier()
        if warnings:
            log = get_logger(__name__)
            for warning in warnings:
                log.warning("Determinism config issue: %s", warning)


@dataclass
class CompileArtifacts:
    policy_ref: PolicySurfaceIRRef
    program_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    slot_layout_ref: ArtifactRef | None = None
    treasury_plan_ref: ArtifactRef | None = None
    conflict_report: ConflictReport | None = None
    cost_estimate: CostEstimate | None = None


class CompileError(Exception):
    """Raised when compilation fails due to conflicts or budget."""

    def __init__(
        self,
        message: str,
        conflict_report: ConflictReport | None = None,
        cost_estimate: CostEstimate | None = None,
    ):
        super().__init__(message)
        self.conflict_report = conflict_report
        self.cost_estimate = cost_estimate


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
    simulation_config: SimulationConfig | None = None,
    profile: ValidationProfile | None = None,
    cost_budget: CostBudget | None = None,
    n_agents: int = 1000,
    time_steps: int = 100,
    strict_conflict_check: bool = True,
) -> CompileArtifacts:
    profile = profile or ValidationProfile.mvp()
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

    conflict_checker = CompileTimeConflictChecker(
        slot_registry=slot_registry,
        merge_registry=merge_registry,
        strict_mode=strict_conflict_check,
    )
    conflict_report = conflict_checker.check(program_graph)
    if not conflict_report.ok and strict_conflict_check:
        raise CompileError(
            f"Compile-time conflict detection failed: {len(conflict_report.conflicts)} conflicts",
            conflict_report=conflict_report,
        )

    cost_model = CostModel()
    cost_estimate = cost_model.estimate(
        program_graph,
        n_agents=n_agents,
        time_steps=time_steps,
        budget=cost_budget,
    )
    if cost_budget is not None and cost_estimate.exceeds_budget:
        raise CompileError(
            f"Cost estimate exceeds budget: {cost_estimate.budget_violations}",
            cost_estimate=cost_estimate,
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
    env_fingerprint = None
    determinism_tier = None
    random_seed = None
    if simulation_config is not None:
        if simulation_config.environment_fingerprint is None:
            simulation_config.environment_fingerprint = EnvironmentFingerprint.capture(
                tier=simulation_config.determinism_tier,
                seed=simulation_config.random_seed,
            )
        env_fingerprint = simulation_config.environment_fingerprint.compute_hash()
        determinism_tier = simulation_config.determinism_tier.value
        random_seed = simulation_config.random_seed

    exec_plan = ExecPlan(
        program_ref=program_graph_ref,
        order=order,
        environment_fingerprint=env_fingerprint,
        determinism_tier=determinism_tier,
        random_seed=random_seed,
        nan_guard_enabled=profile.level == ProfileLevel.STRICT,
    )
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
        conflict_report=conflict_report,
        cost_estimate=cost_estimate,
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
        inputs, outputs = resolve_mechanism_slots(mech, intervention.params)
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

    slot_edges = _slot_dependency_edges(nodes)
    if slot_edges:
        edge_keys = {(edge.src, edge.dst, edge.relation) for edge in edges}
        for edge in slot_edges:
            key = (edge.src, edge.dst, edge.relation)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append(edge)

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


def _slot_dependency_edges(nodes: list[ProgramNode]) -> list[ProgramEdge]:
    def _is_mechanism_node(node: ProgramNode) -> bool:
        if node.node_kind == "mechanism":
            return True
        return bool(node.op and node.op.op_kind == "apply_mechanism")

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
        _, writes = resolve_mechanism_slots(mech, intervention.params)
        for slot_id in writes:
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
