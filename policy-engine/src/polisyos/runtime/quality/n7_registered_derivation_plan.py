"""Build one candidate-only N7 graph from a selected Core registration.

This owner joins an actual compiled model-input port to one registered
derivation profile. It consumes prepared source leaves; it does not discover
suppliers, assert source absence, or authorize a materialized value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core import artifacts

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.quality.acquisition_planner import (
        N7DerivationBasis,
        N7DerivationOperationNode,
        N7DerivationSourceNode,
    )


_REGISTERED_OUTPUT_NODE_ID = "registered-output"
_SUPPORTED_RELATION_PROFILE = "ratio_times_denominator.annual_calendar_flow.v1"


def _base_ref(ref: artifacts.ArtifactRef) -> artifacts.ArtifactRef:
    """Normalize a selected typed Core ref to the canonical four-field wire type."""
    return artifacts.ArtifactRef.model_validate(ref.model_dump(mode="python"))


def _basis_identity_key(basis: N7DerivationBasis) -> tuple[tuple[str, str, str, str | None], ...]:
    return tuple(
        artifacts.artifact_ref_identity_key(getattr(basis, field))
        for field in (
            "semantic_definition_ref",
            "representation_ref",
            "binding_profile_ref",
        )
    )


def persist_registered_n7_derivation_plan(
    store: ArtifactStore,
    *,
    routing_report_ref: artifacts.ArtifactRef,
    obligation_set_ref: artifacts.ArtifactRef,
    target_obligation_ref: artifacts.ArtifactRef,
    registered_profile_ref: artifacts.ArtifactRef,
    dag_budget_profile_ref: artifacts.ArtifactRef,
    role_sources: tuple[tuple[str, N7DerivationSourceNode], ...] | None = None,
    operation_nodes: tuple[N7DerivationOperationNode, ...] | None = None,
    source_nodes: tuple[N7DerivationSourceNode, ...] | None = None,
    root_node_id: str | None = None,
) -> artifacts.ArtifactRef:
    """Persist one registered N7 graph joined to the selected compiler.

    Calls using ``role_sources`` retain the v2 one-operation wire. The bounded
    v3 branch accepts a pre-resolved operation graph and source leaves; the
    canonical bundle writer replays every operation profile and edge before
    persistence. Both branches remain candidate-only and leave the target
    obligation unsatisfied.

    Args:
        store: Canonical artifact store for the selected inputs and output.
        routing_report_ref: Selected report for the full model-input obligation set.
        obligation_set_ref: Independently selected full model-input set.
        target_obligation_ref: One member of that set selected for this plan.
        registered_profile_ref: Selected Core semantic derivation profile.
        dag_budget_profile_ref: Selected planner-owned graph budget.
        role_sources: Legacy v2 source nodes paired with registered roles.
        operation_nodes: Pre-resolved v3 operations with per-operation profile refs.
        source_nodes: Pre-resolved v3 candidate source leaves.
        root_node_id: The v3 operation that supplies the one selected model port.

    Returns:
        The selected persisted N7 derivation bundle reference.

    Raises:
        TypeError: If source-role inputs are not the declared tuple shape.
        ValueError: If any selected join, registered role, graph, or budget is invalid.
    """
    from polisyos.core.contracts import (
        RegisteredDerivedInputProfileRef,
        load_registered_derived_input_profile,
        verify_registered_derived_family,
    )
    from polisyos.core.derivations import load_selected_transform_family_registry
    from polisyos.runtime.quality.acquisition_planner import (
        N7DerivationBasis,
        N7DerivationBundle,
        N7DerivationOperationNode,
        N7DerivationRoleInput,
        N7DerivationSourceNode,
        _n7_load_derivation_dag_budget_profile,
        persist_n7_derivation_bundle,
    )
    from polisyos.runtime.quality.n7_input_obligation_source import (
        _selected_model_requirements,
    )

    if operation_nodes is not None or source_nodes is not None or root_node_id is not None:
        if (
            role_sources is not None
            or type(operation_nodes) is not tuple
            or type(source_nodes) is not tuple
            or type(root_node_id) is not str
        ):
            raise TypeError("n7_registered_derivation_v3_graph_untyped")
        if any(type(row) is not N7DerivationOperationNode for row in operation_nodes) or any(
            type(row) is not N7DerivationSourceNode for row in source_nodes
        ):
            raise TypeError("n7_registered_derivation_v3_node_untyped")

        _compilation, target, _report = _selected_model_requirements(
            store,
            obligation_set_ref=obligation_set_ref,
            routing_report_ref=routing_report_ref,
            target_obligation_ref=target_obligation_ref,
        )
        profile_ref = RegisteredDerivedInputProfileRef.model_validate(
            registered_profile_ref.model_dump(mode="python")
        )
        selected_profile_ref = _base_ref(profile_ref)
        selected_routing_report_ref = _base_ref(routing_report_ref)
        roots = tuple(row for row in operation_nodes if row.node_id == root_node_id)
        if len(operation_nodes) < 2 or len(roots) != 1:
            raise ValueError("n7_registered_derivation_v3_root_operation_required")
        root = roots[0]
        if root.registered_profile_ref is None or artifacts.artifact_ref_identity_key(
            root.registered_profile_ref
        ) != artifacts.artifact_ref_identity_key(selected_profile_ref):
            raise ValueError("n7_registered_derivation_v3_root_profile_mismatch")

        profile = load_registered_derived_input_profile(store, profile_ref)
        if profile.relation_profile != _SUPPORTED_RELATION_PROFILE or len(profile.inputs) != 2:
            raise ValueError("n7_registered_derivation_profile_unsupported")
        target_basis = N7DerivationBasis(
            semantic_definition_ref=target.port.semantic_definition_ref,
            representation_ref=target.port.representation_ref,
            binding_profile_ref=target.port.binding_profile_ref,
        )
        output_basis = N7DerivationBasis(
            semantic_definition_ref=profile.output.semantic_definition_ref,
            representation_ref=profile.output.representation_ref,
            binding_profile_ref=profile.output.binding_profile_ref,
        )
        if _basis_identity_key(output_basis) != _basis_identity_key(target_basis):
            raise ValueError("n7_registered_derivation_output_target_basis_mismatch")

        budget = _n7_load_derivation_dag_budget_profile(store, dag_budget_profile_ref)
        bundle = N7DerivationBundle(
            schema_version="policyos.runtime.n7_derivation_bundle.v3",
            obligation_set_ref=obligation_set_ref,
            model_input_obligation_ref=target_obligation_ref,
            target_basis=target_basis,
            dag_budget_profile_ref=dag_budget_profile_ref,
            dag_budget_profile=budget,
            source_nodes=source_nodes,
            operation_nodes=operation_nodes,
            root_node_id=root_node_id,
            input_closure_status=(
                "inputs_complete"
                if all(source.inputs_complete for source in source_nodes)
                else "partial"
            ),
            registered_profile_ref=selected_profile_ref,
            model_input_routing_report_ref=selected_routing_report_ref,
        )
        return persist_n7_derivation_bundle(store, bundle)

    if type(role_sources) is not tuple:
        raise TypeError("n7_registered_derivation_role_sources_untyped")
    role_map: dict[str, N7DerivationSourceNode] = {}
    for row in role_sources:
        if type(row) is not tuple or len(row) != 2 or type(row[0]) is not str:
            raise TypeError("n7_registered_derivation_role_source_pair_invalid")
        role, source = row
        if type(source) is not N7DerivationSourceNode:
            raise TypeError("n7_registered_derivation_source_node_untyped")
        if role in role_map:
            raise ValueError("n7_registered_derivation_role_duplicate")
        role_map[role] = source

    _compilation, target, _report = _selected_model_requirements(
        store,
        obligation_set_ref=obligation_set_ref,
        routing_report_ref=routing_report_ref,
        target_obligation_ref=target_obligation_ref,
    )
    profile_ref = RegisteredDerivedInputProfileRef.model_validate(
        registered_profile_ref.model_dump(mode="python")
    )
    selected_profile_ref = _base_ref(profile_ref)
    selected_routing_report_ref = _base_ref(routing_report_ref)
    profile = load_registered_derived_input_profile(store, profile_ref)
    if profile.relation_profile != _SUPPORTED_RELATION_PROFILE or len(profile.inputs) != 2:
        raise ValueError("n7_registered_derivation_profile_unsupported")

    target_basis = N7DerivationBasis(
        semantic_definition_ref=target.port.semantic_definition_ref,
        representation_ref=target.port.representation_ref,
        binding_profile_ref=target.port.binding_profile_ref,
    )
    output_basis = N7DerivationBasis(
        semantic_definition_ref=profile.output.semantic_definition_ref,
        representation_ref=profile.output.representation_ref,
        binding_profile_ref=profile.output.binding_profile_ref,
    )
    if _basis_identity_key(output_basis) != _basis_identity_key(target_basis):
        raise ValueError("n7_registered_derivation_output_target_basis_mismatch")

    expected_roles = tuple(row.role for row in profile.inputs)
    if expected_roles != tuple(sorted(set(expected_roles))) or set(role_map) != set(expected_roles):
        raise ValueError("n7_registered_derivation_required_roles_mismatch")
    source_ids = tuple(source.node_id for source in role_map.values())
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("n7_registered_derivation_source_node_duplicate")
    if _REGISTERED_OUTPUT_NODE_ID in source_ids:
        raise ValueError("n7_registered_derivation_source_root_collision")

    role_inputs: list[N7DerivationRoleInput] = []
    for row in profile.inputs:
        source = role_map[row.role]
        registered_basis = N7DerivationBasis(
            semantic_definition_ref=row.basis.semantic_definition_ref,
            representation_ref=row.basis.representation_ref,
            binding_profile_ref=row.basis.binding_profile_ref,
        )
        if _basis_identity_key(source.source_basis) != _basis_identity_key(registered_basis):
            raise ValueError("n7_registered_derivation_source_basis_mismatch")
        role_inputs.append(
            N7DerivationRoleInput(
                role=row.role,
                input_node_id=source.node_id,
                source_basis=source.source_basis,
            )
        )

    registry = load_selected_transform_family_registry(store, profile.registry_ref)
    families = tuple(
        family
        for family in registry.families
        if family.family_id == profile.family_id and family.method_version == profile.method_version
    )
    if len(families) != 1:
        raise ValueError("n7_registered_derivation_family_not_unique")
    verify_registered_derived_family(profile, families[0])

    budget = _n7_load_derivation_dag_budget_profile(store, dag_budget_profile_ref)
    operation = N7DerivationOperationNode(
        node_id=_REGISTERED_OUTPUT_NODE_ID,
        operator_ref=profile.registry_ref,
        family_id=profile.family_id,
        method_version=profile.method_version,
        output_basis=output_basis,
        role_inputs=tuple(role_inputs),
    )
    sources = tuple(role_map.values())
    bundle = N7DerivationBundle(
        schema_version="policyos.runtime.n7_derivation_bundle.v2",
        obligation_set_ref=obligation_set_ref,
        model_input_obligation_ref=target_obligation_ref,
        target_basis=target_basis,
        dag_budget_profile_ref=dag_budget_profile_ref,
        dag_budget_profile=budget,
        source_nodes=sources,
        operation_nodes=(operation,),
        root_node_id=_REGISTERED_OUTPUT_NODE_ID,
        input_closure_status=(
            "inputs_complete" if all(source.inputs_complete for source in sources) else "partial"
        ),
        registered_profile_ref=selected_profile_ref,
        model_input_routing_report_ref=selected_routing_report_ref,
    )
    # The canonical owner normalizes the wire representation and performs its
    # complete selected-profile readback. Comparing the pre-normalized Python
    # model again would reject equivalent typed Core reference subclasses.
    return persist_n7_derivation_bundle(store, bundle)
