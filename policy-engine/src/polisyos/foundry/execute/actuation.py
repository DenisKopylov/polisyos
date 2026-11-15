"""Select whole compiled policy actuations without changing world-model calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    CoreJSONArtifactStore,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts import (
    ExecPlan,
    LoweredIR,
    ProgramGraph,
    ProgramGraphActuationSelectionRef,
)
from polisyos.foundry.compile.actuation import (
    PolicyActuationBindingGroup,
    resolve_program_graph_policy_binding_groups,
    validate_policy_actuation_payload,
)


@dataclass(frozen=True, slots=True)
class ProgramGraphActuationResolution:
    """Reconciled policy activation and the complete ordered node denominator."""

    selection_ref: ProgramGraphActuationSelectionRef | None
    selected_intervention_ids: tuple[str, ...] | None
    active_apply_node_ids: tuple[str, ...]
    inactive_apply_node_ids: tuple[str, ...]
    node_execution: tuple[tuple[str, Literal["execute", "skip"]], ...]
    binding_groups: tuple[PolicyActuationBindingGroup, ...]


def _core_ref(ref: ArtifactRef) -> ArtifactRef:
    """Preserve all selected identity fields at Core's exact base-ref seam."""
    return ArtifactRef.model_validate(ref.model_dump(mode="json"))


def _require_selected_ref(ref: ArtifactRef, kind: str) -> None:
    if (
        not isinstance(ref, ArtifactRef)
        or ref.kind != kind
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("program_graph_actuation_selected_source_required")


def _require_edge(manifest: ArtifactManifest, role: str, ref: ArtifactRef) -> None:
    if [edge for edge in manifest.inputs if edge.role == role] != [
        input_ref_from_artifact_ref(ref, role=role)
    ]:
        raise ValueError("program_graph_actuation_source_edge_mismatch")


def _load_program(
    store: CoreJSONArtifactStore,
    *,
    program_ref: ArtifactRef,
    exec_plan_ref: ArtifactRef,
) -> tuple[ProgramGraph, ExecPlan, tuple[str, ...]]:
    from polisyos.foundry.compile._graph import build_exec_order

    _require_selected_ref(program_ref, ProgramGraph.ARTIFACT_KIND)
    _require_selected_ref(exec_plan_ref, ExecPlan.ARTIFACT_KIND)
    graph = validate_core_model_json_artifact(ProgramGraph, store, _core_ref(program_ref))
    plan = validate_core_model_json_artifact(ExecPlan, store, _core_ref(exec_plan_ref))
    if artifact_ref_identity_key(plan.program_ref) != artifact_ref_identity_key(program_ref):
        raise ValueError("program_graph_actuation_execution_plan_mismatch")
    _require_edge(store.get_manifest(exec_plan_ref), "program_graph", program_ref)
    order = tuple(plan.order)
    if (
        len(graph.nodes) > 256
        or len(order) != len(graph.nodes)
        or len(order) != len(set(order))
        or order != tuple(build_exec_order(graph))
    ):
        raise ValueError("program_graph_actuation_execution_order_mismatch")
    return graph, plan, order


def _load_binding_groups(
    store: CoreJSONArtifactStore,
    *,
    program_ref: ArtifactRef,
    graph: ProgramGraph,
) -> tuple[PolicyActuationBindingGroup, ...]:
    lowered_ref = graph.lowered_ir_ref
    if lowered_ref is None:
        raise ValueError("program_graph_actuation_lowered_ir_missing")
    _require_selected_ref(lowered_ref, "foundry.lowered_ir")
    _require_selected_ref(graph.ir_ref, "ir.trinity_bundle")
    graph_manifest = store.get_manifest(program_ref)
    _require_edge(graph_manifest, "ir", graph.ir_ref)
    _require_edge(graph_manifest, "lowered_ir", lowered_ref)
    lowered_manifest = store.get_manifest(lowered_ref)
    if lowered_manifest.artifact_schema != SchemaInfo(
        name="polisyos.foundry.LoweredIR", version="0.2.0"
    ):
        raise ValueError("program_graph_actuation_lowered_ir_profile_unsupported")
    _require_edge(lowered_manifest, "ir", graph.ir_ref)
    graph_registry = [edge for edge in graph_manifest.inputs if edge.role == "registry_bundle"]
    lowered_registry = [edge for edge in lowered_manifest.inputs if edge.role == "registry_bundle"]
    if (
        len(graph_registry) != 1
        or len(lowered_registry) != 1
        or graph_registry[0].manifest_profile_sha256 is None
        or lowered_registry[0].manifest_profile_sha256 is None
        or graph_registry[0] != lowered_registry[0]
    ):
        raise ValueError("program_graph_actuation_registry_source_mismatch")
    lowered = LoweredIR.model_validate(load_core_json_artifact(store, _core_ref(lowered_ref)))
    if artifact_ref_identity_key(lowered.ir_ref) != artifact_ref_identity_key(graph.ir_ref):
        raise ValueError("program_graph_actuation_lowered_ir_source_mismatch")
    groups = resolve_program_graph_policy_binding_groups(graph, lowered)
    # Reopen the actual compiled payloads. References alone do not demonstrate
    # that the materialized schedule/selector belongs to the selected row.
    for row, group in zip(lowered.mechanisms, groups, strict=True):
        ref = group.effective_params_ref
        _require_selected_ref(ref, "foundry.lowered_mechanism_payload")
        _require_edge(graph_manifest, f"params:{group.apply_node_id}", ref)
        manifest = store.get_manifest(ref)
        if manifest.artifact_schema != SchemaInfo(
            name="polisyos.foundry.LoweredMechanismPayload", version="0.2.0"
        ):
            raise ValueError("program_graph_actuation_parameter_profile_unsupported")
        _require_edge(manifest, "ir", graph.ir_ref)
        payload = load_core_json_artifact(store, _core_ref(ref))
        validate_policy_actuation_payload(row, payload)
    return groups


def _resolve_selection(
    *,
    selection_ref: ProgramGraphActuationSelectionRef | None,
    selected_intervention_ids: tuple[str, ...] | None,
    graph: ProgramGraph,
    order: tuple[str, ...],
    groups: tuple[PolicyActuationBindingGroup, ...],
) -> ProgramGraphActuationResolution:
    selected = None if selected_intervention_ids is None else set(selected_intervention_ids)
    declared = {item for group in groups for item in group.intervention_ids}
    if selected is not None and not selected <= declared:
        raise ValueError("program_graph_actuation_unknown_intervention")
    active: set[str] = set()
    inactive: set[str] = set()
    for group in groups:
        members = set(group.intervention_ids)
        chosen = members if selected is None else members & selected
        if chosen and chosen != members:
            raise ValueError("program_graph_actuation_partial_binding_group")
        (active if chosen else inactive).add(group.apply_node_id)
    if selected is None:
        # Legacy callers preserve all existing compiled applies. No explicit
        # policy-row eligibility is inferred for an unselected legacy graph.
        active.update(
            node.node_id
            for node in graph.nodes
            if node.node_kind == "op"
            and node.op is not None
            and node.op.op_kind == "apply_mechanism"
        )
    return ProgramGraphActuationResolution(
        selection_ref=selection_ref,
        selected_intervention_ids=selected_intervention_ids,
        active_apply_node_ids=tuple(node_id for node_id in order if node_id in active),
        inactive_apply_node_ids=tuple(node_id for node_id in order if node_id in inactive),
        node_execution=tuple(
            (node_id, "skip" if node_id in inactive else "execute") for node_id in order
        ),
        binding_groups=groups,
    )


def create_program_graph_actuation_selection(
    store: CoreJSONArtifactStore,
    *,
    program_ref: ArtifactRef,
    exec_plan_ref: ArtifactRef,
    selected_intervention_ids: tuple[str, ...],
) -> ProgramGraphActuationSelectionRef:
    """Persist an exact whole-row policy selection; an empty tuple is baseline.

    Args:
        store: Canonical source reader and selected-profile artifact writer.
        program_ref: Selected compiled graph.
        exec_plan_ref: Selected plan for that graph.
        selected_intervention_ids: Sorted unique complete intervention groups.

    Returns:
        The selected candidate-only actuation artifact reference.

    Raises:
        ValueError: If the complete compiler inventory or selection disagrees.
    """
    from polisyos.core.contracts import ProgramGraphActuationSelection

    graph, _, order = _load_program(store, program_ref=program_ref, exec_plan_ref=exec_plan_ref)
    groups = _load_binding_groups(store, program_ref=program_ref, graph=graph)
    selection = ProgramGraphActuationSelection(
        program_graph_ref=program_ref,
        exec_plan_ref=exec_plan_ref,
        lowered_ir_ref=graph.lowered_ir_ref,
        selected_intervention_ids=selected_intervention_ids,
    )
    _resolve_selection(
        selection_ref=None,
        selected_intervention_ids=selection.selected_intervention_ids,
        graph=graph,
        order=order,
        groups=groups,
    )
    ref = store.put_json(
        selection,
        PutOptions(
            kind=selection.ARTIFACT_KIND,
            media_type=selection.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=selection.ARTIFACT_SCHEMA_NAME, version=selection.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[
                input_ref_from_artifact_ref(source, role=role)
                for role, source in (
                    ("program_graph", program_ref),
                    ("exec_plan", exec_plan_ref),
                    ("lowered_ir", selection.lowered_ir_ref),
                )
            ],
        ),
        return_selected_profile=True,
    )
    return ProgramGraphActuationSelectionRef.model_validate(ref.model_dump(mode="python"))


def resolve_program_graph_actuation(
    store: CoreJSONArtifactStore,
    *,
    program_ref: ArtifactRef,
    exec_plan_ref: ArtifactRef,
    actuation_selection_ref: ProgramGraphActuationSelectionRef | None,
) -> ProgramGraphActuationResolution:
    """Replay the selected actuation and complete execution/skip inventory.

    Args:
        store: Canonical artifact source reader.
        program_ref: Exact selected graph used for preparation or execution.
        exec_plan_ref: Exact selected execution plan.
        actuation_selection_ref: Explicit activation artifact, or legacy-all.

    Returns:
        Reconciled source groups and all ordered executable/skipped node IDs.

    Raises:
        ValueError: If a source, manifest edge, group, or selection is invalid.
    """
    from polisyos.core.contracts import ProgramGraphActuationSelection

    graph, _, order = _load_program(store, program_ref=program_ref, exec_plan_ref=exec_plan_ref)
    if actuation_selection_ref is None:
        return _resolve_selection(
            selection_ref=None,
            selected_intervention_ids=None,
            graph=graph,
            order=order,
            groups=(),
        )
    _require_selected_ref(actuation_selection_ref, ProgramGraphActuationSelection.ARTIFACT_KIND)
    selection = validate_core_model_json_artifact(
        ProgramGraphActuationSelection, store, _core_ref(actuation_selection_ref)
    )
    if graph.lowered_ir_ref is None or any(
        artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected)
        for actual, expected in (
            (selection.program_graph_ref, program_ref),
            (selection.exec_plan_ref, exec_plan_ref),
            (selection.lowered_ir_ref, graph.lowered_ir_ref),
        )
    ):
        raise ValueError("program_graph_actuation_selection_source_mismatch")
    manifest = store.get_manifest(actuation_selection_ref)
    expected_inputs = [
        input_ref_from_artifact_ref(source, role=role)
        for role, source in (
            ("program_graph", program_ref),
            ("exec_plan", exec_plan_ref),
            ("lowered_ir", graph.lowered_ir_ref),
        )
    ]
    if manifest.inputs != expected_inputs:
        raise ValueError("program_graph_actuation_selection_inventory_mismatch")
    groups = _load_binding_groups(store, program_ref=program_ref, graph=graph)
    return _resolve_selection(
        selection_ref=actuation_selection_ref,
        selected_intervention_ids=selection.selected_intervention_ids,
        graph=graph,
        order=order,
        groups=groups,
    )
