"""Resolve exact compiled intervention rows into policy actuation groups.

This module reconciles the selected LoweredIR rows with the compiled mask and
apply nodes. It does not select a subset of interventions, open CAS artifacts,
or decide whether a group should run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeGuard

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts import (
    LoweredIR,
    LoweredMechanism,
    ProgramGraph,
    ProgramNode,
)

__all__ = (
    "PolicyActuationBindingGroup",
    "resolve_program_graph_policy_binding_groups",
    "validate_policy_actuation_payload",
)

_GRAPH_SCHEMA_VERSIONS = frozenset({"0.2", "0.3"})
_LOWERED_IR_SCHEMA_VERSION = "0.2"
_PARAMS_REF_KIND = "foundry.lowered_mechanism_payload"
_OP_APPLY_PARAMS = frozenset({"mask_id", "binding_id", "selected_fidelity"})
_OP_MASK_PARAMS = frozenset({"binding_id", "intervention_ids", "selector"})
_LOWERED_PAYLOAD_KEYS = frozenset(
    {
        "binding_id",
        "mechanism_id",
        "intervention_ids",
        "priority",
        "params",
        "schedule",
        "selector",
        "selected_fidelity",
        "legacy_kind_alias_used",
        "notes",
    }
)
_SELECTOR_CANON_SPEC = CanonSpec(forbid_floats=False)


@dataclass(frozen=True, slots=True)
class PolicyActuationBindingGroup:
    """One exact LoweredMechanism row and its compiled mask/apply pair."""

    binding_id: str
    intervention_ids: tuple[str, ...]
    mask_node_id: str
    apply_node_id: str
    mechanism_id: str
    effective_params_ref: ArtifactRef
    input_slot_ids: tuple[str, ...]
    output_slot_ids: tuple[str, ...]
    selected_fidelity: str


@dataclass(frozen=True, slots=True)
class _ActuationPair:
    """One structurally linked apply node and its referenced mask node."""

    mask_node: ProgramNode
    apply_node: ProgramNode
    binding_id: str
    intervention_ids_in_source_order: tuple[str, ...]
    selector_bytes: bytes


def resolve_program_graph_policy_binding_groups(
    graph: ProgramGraph,
    lowered_ir: LoweredIR,
) -> tuple[PolicyActuationBindingGroup, ...]:
    """Reconcile every lowered actuation row with exactly one compiled pair.

    Each result represents one ``LoweredMechanism`` row. Rows are never merged
    by ``binding_id``: one explicit binding may legitimately serve several
    intervention rows. The row is joined through the apply node's actual
    ``mask_id`` reference and the mask's binding and intervention identities.

    Args:
        graph: Selected ProgramGraph containing compiled operation nodes.
        lowered_ir: Selected LoweredIR containing the corresponding mechanism
            rows.

    Returns:
        One immutable actuation group per LoweredMechanism row, in LoweredIR
        order. Intervention IDs in each group are canonical sorted unique IDs;
        input and output slots preserve the exact compiled order.

    Raises:
        ValueError: If either artifact uses an unsupported profile or if the
            complete row, mask, apply, selected-reference, selector, or edge
            census is missing, extra, ambiguous, or inconsistent.
    """
    if type(graph) is not ProgramGraph or type(lowered_ir) is not LoweredIR:
        raise ValueError("foundry_policy_actuation_inputs_invalid")
    if graph.schema_version not in _GRAPH_SCHEMA_VERSIONS:
        raise ValueError("foundry_policy_actuation_graph_profile_unsupported")
    if lowered_ir.schema_version != _LOWERED_IR_SCHEMA_VERSION:
        raise ValueError("foundry_policy_actuation_lowered_ir_profile_unsupported")

    node_ids = [node.node_id for node in graph.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("foundry_policy_actuation_graph_node_ids_not_unique")
    nodes_by_id = {node.node_id: node for node in graph.nodes}

    if any(node.node_kind == "mechanism" for node in graph.nodes):
        raise ValueError("foundry_policy_actuation_legacy_direct_mechanism_unsupported")

    apply_nodes = tuple(
        node
        for node in graph.nodes
        if node.node_kind == "op" and node.op is not None and node.op.op_kind == "apply_mechanism"
    )
    mask_nodes = tuple(
        node
        for node in graph.nodes
        if node.node_kind == "op" and node.op is not None and node.op.op_kind == "make_mask"
    )
    actuation_ops = tuple(
        node
        for node in graph.nodes
        if node.op is not None and node.op.op_kind in {"apply_mechanism", "make_mask"}
    )
    if len(actuation_ops) != len(apply_nodes) + len(mask_nodes):
        raise ValueError("foundry_policy_actuation_op_node_kind_mismatch")

    rows = tuple(lowered_ir.mechanisms)
    if not rows and not apply_nodes and not mask_nodes:
        return ()
    if len(rows) != len(apply_nodes) or len(rows) != len(mask_nodes):
        raise ValueError("foundry_policy_actuation_row_apply_mask_census_mismatch")

    normalized_rows = tuple(_validate_lowered_row(row) for row in rows)
    referenced_mask_ids: list[str] = []
    for apply_node in apply_nodes:
        if apply_node.op is None or set(apply_node.op.params) != _OP_APPLY_PARAMS:
            raise ValueError("foundry_policy_actuation_apply_op_profile_mismatch")
        mask_id = apply_node.op.params.get("mask_id")
        if not _is_nonempty_trimmed_string(mask_id):
            raise ValueError("foundry_policy_actuation_apply_link_identity_invalid")
        referenced_mask_ids.append(mask_id)
    if len(referenced_mask_ids) != len(set(referenced_mask_ids)):
        raise ValueError("foundry_policy_actuation_mask_reused")

    pairs = tuple(
        _resolve_apply_pair(
            apply_node=apply_node,
            nodes_by_id=nodes_by_id,
            graph=graph,
        )
        for apply_node in apply_nodes
    )

    mask_usage: dict[str, int] = {}
    for pair in pairs:
        mask_usage[pair.mask_node.node_id] = mask_usage.get(pair.mask_node.node_id, 0) + 1
        if mask_usage[pair.mask_node.node_id] != 1:
            raise ValueError("foundry_policy_actuation_mask_reused")
    if set(mask_usage) != {node.node_id for node in mask_nodes}:
        raise ValueError("foundry_policy_actuation_mask_unbound")

    groups_by_row: dict[int, PolicyActuationBindingGroup] = {}
    for pair in pairs:
        matching_indices = [
            index
            for index, normalized in enumerate(normalized_rows)
            if _row_matches_pair(normalized, pair)
        ]
        if not matching_indices:
            raise ValueError("foundry_policy_actuation_row_apply_binding_unmatched")
        if len(matching_indices) != 1:
            raise ValueError("foundry_policy_actuation_row_apply_binding_ambiguous")
        row_index = matching_indices[0]
        if row_index in groups_by_row:
            raise ValueError("foundry_policy_actuation_row_matched_multiple_times")
        groups_by_row[row_index] = _group_from_pair(normalized_rows[row_index], pair)

    if set(groups_by_row) != set(range(len(rows))):
        raise ValueError("foundry_policy_actuation_row_unmatched")
    return tuple(groups_by_row[index] for index in range(len(rows)))


def validate_policy_actuation_payload(row: LoweredMechanism, payload: object) -> None:
    """Validate one stored lowered-mechanism payload against its IR row.

    This checks the compiler-owned mirror between a typed ``LoweredMechanism``
    and the selected JSON payload. It does not open CAS, validate manifest
    lineage, or interpret mechanism parameters.

    Args:
        row: Lowered mechanism row that selects the payload artifact.
        payload: Decoded payload read from that exact selected artifact.

    Raises:
        ValueError: If the payload shape is not the current compiler profile or
            any mirrored field differs structurally from the LoweredIR row.
    """
    if type(row) is not LoweredMechanism or type(payload) is not dict:
        raise ValueError("foundry_policy_actuation_payload_invalid")
    if set(payload) != _LOWERED_PAYLOAD_KEYS:
        raise ValueError("foundry_policy_actuation_payload_profile_mismatch")
    if type(payload["params"]) is not dict:
        raise ValueError("foundry_policy_actuation_payload_params_invalid")
    _validate_lowered_row(row)

    expected_fields = {
        "binding_id": row.binding_id,
        "mechanism_id": row.mechanism_id,
        "intervention_ids": row.intervention_ids,
        "priority": row.priority,
        "schedule": row.effective_schedule,
        "selector": row.target_selector,
        "selected_fidelity": row.selected_fidelity,
        "legacy_kind_alias_used": row.legacy_kind_alias_used,
        "notes": row.notes,
    }
    for field_name, expected in expected_fields.items():
        try:
            actual_bytes = to_canonical_bytes(payload[field_name], spec=_SELECTOR_CANON_SPEC)
            expected_bytes = to_canonical_bytes(expected, spec=_SELECTOR_CANON_SPEC)
        except (TypeError, ValueError) as exc:
            raise ValueError("foundry_policy_actuation_payload_field_invalid") from exc
        if actual_bytes != expected_bytes:
            raise ValueError("foundry_policy_actuation_payload_row_mismatch")


@dataclass(frozen=True, slots=True)
class _NormalizedLoweredRow:
    """Validated matching projection of one LoweredMechanism row."""

    binding_id: str
    intervention_ids_in_source_order: tuple[str, ...]
    intervention_ids: tuple[str, ...]
    mechanism_id: str
    effective_params_ref: ArtifactRef
    input_slot_ids: tuple[str, ...]
    output_slot_ids: tuple[str, ...]
    selected_fidelity: str
    selector_bytes: bytes


def _validate_lowered_row(row: LoweredMechanism) -> _NormalizedLoweredRow:
    """Validate required identities and selected artifact reference on a row."""
    binding_id = row.binding_id
    mechanism_id = row.mechanism_id
    if not _is_nonempty_trimmed_string(binding_id) or not _is_nonempty_trimmed_string(mechanism_id):
        raise ValueError("foundry_policy_actuation_lowered_row_identity_invalid")

    intervention_ids = _string_sequence(
        row.intervention_ids,
        code="foundry_policy_actuation_lowered_intervention_ids_invalid",
        require_nonempty=True,
    )
    if len(intervention_ids) != len(set(intervention_ids)):
        raise ValueError("foundry_policy_actuation_lowered_intervention_ids_not_unique")

    effective_params_ref = row.effective_params_ref
    if not _is_selected_params_ref(effective_params_ref):
        raise ValueError("foundry_policy_actuation_selected_params_ref_required")

    input_slot_ids = _string_sequence(
        row.inputs,
        code="foundry_policy_actuation_lowered_input_slots_invalid",
    )
    output_slot_ids = _string_sequence(
        row.outputs,
        code="foundry_policy_actuation_lowered_output_slots_invalid",
    )
    if len(input_slot_ids) != len(set(input_slot_ids)):
        raise ValueError("foundry_policy_actuation_lowered_input_slots_not_unique")
    if len(output_slot_ids) != len(set(output_slot_ids)):
        raise ValueError("foundry_policy_actuation_lowered_output_slots_not_unique")

    selected_fidelity = row.selected_fidelity
    if not _is_nonempty_trimmed_string(selected_fidelity):
        raise ValueError("foundry_policy_actuation_selected_fidelity_missing")

    selector_bytes = _selector_identity(row.target_selector)
    return _NormalizedLoweredRow(
        binding_id=binding_id,
        intervention_ids_in_source_order=intervention_ids,
        intervention_ids=tuple(sorted(intervention_ids)),
        mechanism_id=mechanism_id,
        effective_params_ref=effective_params_ref,
        input_slot_ids=input_slot_ids,
        output_slot_ids=output_slot_ids,
        selected_fidelity=selected_fidelity,
        selector_bytes=selector_bytes,
    )


def _resolve_apply_pair(
    *,
    apply_node: ProgramNode,
    nodes_by_id: dict[str, ProgramNode],
    graph: ProgramGraph,
) -> _ActuationPair:
    """Resolve an apply node through its actual mask reference and edge."""
    if apply_node.op is None or set(apply_node.op.params) != _OP_APPLY_PARAMS:
        raise ValueError("foundry_policy_actuation_apply_op_profile_mismatch")
    if (
        apply_node.method_fqn is not None
        or apply_node.method_version is not None
        or apply_node.method_params
        or apply_node.input_ports is not None
    ):
        raise ValueError("foundry_policy_actuation_apply_node_projection_mismatch")
    mask_id = apply_node.op.params.get("mask_id")
    binding_id = apply_node.op.params.get("binding_id")
    if not _is_nonempty_trimmed_string(mask_id) or not _is_nonempty_trimmed_string(binding_id):
        raise ValueError("foundry_policy_actuation_apply_link_identity_invalid")

    mask_node = nodes_by_id.get(mask_id)
    if (
        mask_node is None
        or mask_node.node_kind != "op"
        or mask_node.op is None
        or mask_node.op.op_kind != "make_mask"
    ):
        raise ValueError("foundry_policy_actuation_apply_mask_reference_invalid")
    if set(mask_node.op.params) != _OP_MASK_PARAMS:
        raise ValueError("foundry_policy_actuation_mask_op_profile_mismatch")
    if (
        mask_node.inputs
        or mask_node.outputs
        or mask_node.params_ref is not None
        or mask_node.mechanism_type is not None
        or mask_node.method_fqn is not None
        or mask_node.method_version is not None
        or mask_node.method_params
        or mask_node.input_ports is not None
    ):
        raise ValueError("foundry_policy_actuation_mask_node_projection_mismatch")

    mask_binding_id = mask_node.op.params.get("binding_id")
    intervention_ids = _string_sequence(
        mask_node.op.params.get("intervention_ids"),
        code="foundry_policy_actuation_mask_intervention_ids_invalid",
        require_nonempty=True,
    )
    if len(intervention_ids) != len(set(intervention_ids)):
        raise ValueError("foundry_policy_actuation_mask_intervention_ids_not_unique")
    if not _is_nonempty_trimmed_string(mask_binding_id) or mask_binding_id != binding_id:
        raise ValueError("foundry_policy_actuation_mask_binding_mismatch")

    selector_bytes = _selector_identity(mask_node.op.params.get("selector"))
    incident_mask_edges = [
        edge
        for edge in graph.edges
        if edge.src == mask_node.node_id or edge.dst == mask_node.node_id
    ]
    direct_edges = [
        edge
        for edge in graph.edges
        if edge.src == mask_node.node_id
        and edge.dst == apply_node.node_id
        and edge.relation == "depends_on"
    ]
    if len(incident_mask_edges) != 1 or len(direct_edges) != 1:
        raise ValueError("foundry_policy_actuation_mask_apply_direct_edge_invalid")

    selected_fidelity = apply_node.op.params.get("selected_fidelity")
    if not _is_nonempty_trimmed_string(selected_fidelity):
        raise ValueError("foundry_policy_actuation_apply_fidelity_missing")
    return _ActuationPair(
        mask_node=mask_node,
        apply_node=apply_node,
        binding_id=binding_id,
        intervention_ids_in_source_order=intervention_ids,
        selector_bytes=selector_bytes,
    )


def _row_matches_pair(row: _NormalizedLoweredRow, pair: _ActuationPair) -> bool:
    """Compare all lowering-owned fields against one compiled pair."""
    mask_params = pair.mask_node.op.params if pair.mask_node.op is not None else {}
    apply = pair.apply_node
    apply_params = apply.op.params if apply.op is not None else {}
    params_ref = apply.params_ref
    return (
        row.binding_id == pair.binding_id
        and row.intervention_ids_in_source_order == pair.intervention_ids_in_source_order
        and row.selector_bytes == pair.selector_bytes
        and row.mechanism_id == apply.mechanism_type
        and _is_selected_params_ref(params_ref)
        and artifact_ref_identity_key(row.effective_params_ref)
        == artifact_ref_identity_key(params_ref)
        and row.input_slot_ids == tuple(apply.inputs)
        and row.output_slot_ids == tuple(apply.outputs)
        and row.selected_fidelity == apply_params.get("selected_fidelity")
        and mask_params.get("binding_id") == apply_params.get("binding_id")
    )


def _group_from_pair(
    row: _NormalizedLoweredRow,
    pair: _ActuationPair,
) -> PolicyActuationBindingGroup:
    """Project one fully matched row into the downstream immutable group."""
    return PolicyActuationBindingGroup(
        binding_id=row.binding_id,
        intervention_ids=row.intervention_ids,
        mask_node_id=pair.mask_node.node_id,
        apply_node_id=pair.apply_node.node_id,
        mechanism_id=row.mechanism_id,
        effective_params_ref=row.effective_params_ref,
        input_slot_ids=row.input_slot_ids,
        output_slot_ids=row.output_slot_ids,
        selected_fidelity=row.selected_fidelity,
    )


def _is_selected_params_ref(ref: object) -> TypeGuard[ArtifactRef]:
    """Return whether a ref identifies a selected lowered-mechanism JSON view."""
    return (
        isinstance(ref, ArtifactRef)
        and type(ref) is ArtifactRef
        and ref.kind == _PARAMS_REF_KIND
        and ref.media_type == "application/json"
        and ref.manifest_profile_sha256 is not None
    )


def _is_nonempty_trimmed_string(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and type(value) is str and bool(value) and value == value.strip()


def _string_sequence(
    value: object,
    *,
    code: str,
    require_nonempty: bool = False,
) -> tuple[str, ...]:
    """Validate a list-like source field without coercion or identity loss."""
    if type(value) is not list:
        raise ValueError(code)
    result = tuple(value)
    if require_nonempty and not result:
        raise ValueError(code)
    if any(not _is_nonempty_trimmed_string(item) for item in result):
        raise ValueError(code)
    return result


def _selector_identity(value: object) -> bytes:
    """Return strict canonical bytes for a structural JSON selector."""
    if type(value) is not dict or not value:
        raise ValueError("foundry_policy_actuation_selector_missing_or_invalid")
    try:
        return to_canonical_bytes(value, spec=_SELECTOR_CANON_SPEC)
    except (TypeError, ValueError) as exc:
        raise ValueError("foundry_policy_actuation_selector_missing_or_invalid") from exc
