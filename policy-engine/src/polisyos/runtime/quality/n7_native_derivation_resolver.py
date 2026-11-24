"""Resolve registered candidate source roles after the real model preflight.

Selections are deployment inputs to candidate planning. Catalog declaration
snapshots are historical owner evidence, not fetch rights or measurement
admission. Missing or ambiguous registrations leave the model target pending.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core import artifacts

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts import ArtifactStore
    from polisyos.core.contracts import (
        ModelInputContext,
        ModelInputScope,
        RegisteredDerivedInputProfile,
    )
    from polisyos.data_forge.read_api.catalog import AcquisitionSupplierDeclaration
    from polisyos.data_requirement import CompiledModelInputRequirement
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionRequirementGap,
        N7DerivationBasis,
        N7DerivationBundle,
        N7DerivationOperationNode,
        N7DerivationSourceNode,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        NativeDerivationPlanningRoleSupplier,
        NativeDerivationPlanningSelection,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericN5ExecutionJoinExpectation,
    )


ROLE_INPUT_GAP_SCHEMA_VERSION = "policyos.runtime.registered_derivation_role_input_gap.v1"


def _same(left: artifacts.ArtifactRef, right: artifacts.ArtifactRef) -> bool:
    return artifacts.artifact_ref_identity_key(left) == artifacts.artifact_ref_identity_key(right)


def _ref(value: object) -> artifacts.ArtifactRef:
    ref = artifacts.ArtifactRef.model_validate(value)
    if ref.media_type != "application/json" or ref.manifest_profile_sha256 is None:
        raise ValueError("n7_registered_role_selected_parent_required")
    return ref


def _role_scope(
    store: ArtifactStore,
    *,
    target_scope: ModelInputScope,
    basis: N7DerivationBasis,
    declaration: AcquisitionSupplierDeclaration,
) -> ModelInputScope:
    """Preserve output coordinates and the independently declared role population."""
    from polisyos.core.contracts import ModelInputScope, load_variable_representation

    representation = load_variable_representation(store, basis.representation_ref)
    source_scope = declaration.entry.source_measure_scope
    if source_scope is None:
        raise ValueError("n7_registered_role_source_scope_not_established")
    population = representation.population_ref or source_scope.population
    return ModelInputScope.model_validate(
        {**target_scope.model_dump(mode="python"), "population_ref": population}
    )


def _role_input_gap(
    *,
    target: CompiledModelInputRequirement,
    obligation_set_ref: artifacts.ArtifactRef,
    routing_report_ref: artifacts.ArtifactRef,
    profile_ref: artifacts.ArtifactRef,
    role: str,
    basis: N7DerivationBasis,
    declaration_ref: artifacts.ArtifactRef,
    declaration: AcquisitionSupplierDeclaration,
    context: ModelInputContext,
    scope: ModelInputScope,
    authority_level: object,
    operation_role_bindings: tuple[dict[str, object], ...] = (),
) -> AcquisitionRequirementGap:
    """Describe an unbound required role without asserting source/data absence."""
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionGapType,
        AcquisitionRequirementGap,
        AuthorityLevel,
        MandatoryGateState,
        RequirementGapFamily,
        _stable_content_hash,
    )

    level = AuthorityLevel(authority_level)
    binding = {
        "candidate_id": context.candidate_id,
        "candidate_content_hash": context.candidate_content_hash,
        "design_problem_ref": context.design_problem_ref,
    }
    metadata = {
        "source": "registered_derivation_role_input",
        "schema_version": ROLE_INPUT_GAP_SCHEMA_VERSION,
        "authority_purpose": "candidate_acquisition_routing_only",
        "candidate_binding": binding,
        "model_input_obligation_set_ref": obligation_set_ref.model_dump(mode="json"),
        "model_input_obligation_ref": target.obligation_ref.model_dump(mode="json"),
        "model_input_routing_report_ref": routing_report_ref.model_dump(mode="json"),
        "registered_profile_ref": profile_ref.model_dump(mode="json"),
        "role": role,
        "source_basis": basis.model_dump(mode="json"),
        "source_declaration_ref": declaration_ref.model_dump(mode="json"),
        "requested_role_scope": scope.model_dump(mode="json"),
        "variable_id": declaration.entry.target_variable,
        "historical_catalog_absence": "not_established",
        "source_currentness": "not_established",
        "permission_status": "not_established",
        "measurement_admission": "not_established",
        "satisfaction_status": "unsatisfied",
    }
    if operation_role_bindings:
        metadata["operation_role_bindings"] = [dict(row) for row in operation_role_bindings]
    identity = _stable_content_hash(metadata).removeprefix("sha256:")[:24]
    compiled_ref = f"runtime-requirement:registered-derivation-role:{identity}:v1"
    return AcquisitionRequirementGap(
        requirement_gap_id=f"requirement-gap:registered-derivation-role:{identity}",
        requirement_family=RequirementGapFamily.DATA,
        compiled_requirement_ref=compiled_ref,
        requirement_schema_version=ROLE_INPUT_GAP_SCHEMA_VERSION,
        gap_type=AcquisitionGapType.DATA_SNAPSHOT_RELEASE,
        claim_ref=f"registered-model-input:{context.candidate_id}:{target.port.port_id}:{role}",
        scenario_requirement_refs=(context.design_problem_ref, target.requirement_id, compiled_ref),
        missing_requirement_fields=(
            f"canonical_variable_observations:{declaration.entry.target_variable}",
        ),
        authority_level=level,
        mandatory_gate_state=(
            MandatoryGateState.NONE
            if level is AuthorityLevel.RESEARCH
            else MandatoryGateState.NON_OVERRIDABLE
        ),
        mandatory_gate_refs=(compiled_ref,),
        limitation_permitted=False,
        decision_owner_ref="polisyos.runtime.quality.acquisition_planner",
        producer_output_ref=str(declaration_ref.artifact_id),
        metadata=metadata,
    )


def _profile_basis_match(profile: RegisteredDerivedInputProfile, target: object) -> bool:
    return all(
        _same(getattr(profile.output, field), getattr(target.port, field))
        for field in ("semantic_definition_ref", "representation_ref", "binding_profile_ref")
    )


def _require_n7_v3_foundry_target_profile(
    store: ArtifactStore,
    *,
    target: CompiledModelInputRequirement,
    obligation_set_ref: artifacts.ArtifactRef,
) -> None:
    """Apply Foundry's existing bounded graph-target compatibility rules."""
    from polisyos.core.contracts import load_model_input_obligation_set

    selected_set, obligations = load_model_input_obligation_set(store, obligation_set_ref)
    port = target.port
    if (
        len(selected_set.obligation_refs) != 1
        or len(obligations) != 1
        or not _same(selected_set.obligation_refs[0], target.obligation_ref)
        or len(selected_set.invocation.steps) != 1
        or port.purpose != "simulation_input"
        or port.carrier != "method_input"
        or port.physical_encoding is None
        or port.physical_encoding.shape
    ):
        raise ValueError("n7_registered_graph_foundry_target_profile_unsupported")


def _eligible_n7_v3_supplier_rows(
    store: ArtifactStore,
    *,
    rows: tuple[NativeDerivationPlanningRoleSupplier, ...],
    basis: N7DerivationBasis,
    target_scope: ModelInputScope,
) -> tuple[
    tuple[
        NativeDerivationPlanningRoleSupplier,
        AcquisitionSupplierDeclaration,
        ModelInputScope,
    ],
    ...,
]:
    """Recompute one role's eligible supplier projection from Catalog owners."""
    from polisyos.data_forge.read_api.catalog import (
        AcquisitionAuthorityError,
        acquisition_supplier_declaration_scope_refusal,
        load_acquisition_supplier_declaration,
    )

    eligible = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for row in rows:
        key = artifacts.artifact_ref_identity_key(row.source_declaration_ref)
        if key in seen:
            continue
        seen.add(key)
        try:
            declaration = load_acquisition_supplier_declaration(store, row.source_declaration_ref)
            entry = declaration.entry
            if (
                not _same(row.provider.supplier_ref, row.source_declaration_ref)
                or entry.entry_id != row.provider.authority_entry_id
                or declaration.connector_id != row.provider.connector_id
                or entry.source_semantic_definition_ref is None
                or entry.source_representation_ref is None
                or not _same(entry.source_semantic_definition_ref, basis.semantic_definition_ref)
                or not _same(entry.source_representation_ref, basis.representation_ref)
            ):
                continue
            scope = _role_scope(
                store,
                target_scope=target_scope,
                basis=basis,
                declaration=declaration,
            )
            if (
                acquisition_supplier_declaration_scope_refusal(
                    store, row.source_declaration_ref, scope=scope
                )
                is not None
            ):
                continue
        except (AcquisitionAuthorityError, FileNotFoundError, ValueError) as exc:
            artifacts.raise_artifact_read_access_error(exc)
            continue
        eligible.append((row, declaration, scope))
    return tuple(
        sorted(
            eligible,
            key=lambda item: artifacts.artifact_ref_identity_key(item[0].source_declaration_ref),
        )
    )


def _n7_v3_query_country_code(
    scope: ModelInputScope,
    declaration: AcquisitionSupplierDeclaration,
) -> str | None:
    """Resolve a WDI country from a plain scope code or its selected Catalog coordinate."""
    from polisyos.data_forge import read_api

    geography_ref = scope.geography_ref
    if not (geography_ref.isascii() and geography_ref.isalpha() and len(geography_ref) in {2, 3}):
        source_scope = declaration.entry.source_measure_scope
        if (
            source_scope is None
            or source_scope.geography_ref != geography_ref
            or source_scope.source_geography_id is None
        ):
            return None
        geography_ref = source_scope.source_geography_id
    return read_api.catalog.iso2_to_iso3(geography_ref)


def _configured_v3_operation_graph(
    store: ArtifactStore,
    *,
    selection: NativeDerivationPlanningSelection,
    target: CompiledModelInputRequirement,
    obligation_set_ref: artifacts.ArtifactRef,
    routing_report_ref: artifacts.ArtifactRef,
    context: ModelInputContext,
    authority_level: object,
) -> tuple[tuple[N7DerivationOperationNode, ...], tuple[N7DerivationSourceNode, ...], str] | None:
    """Resolve explicit v3 operation edges and compatible Catalog source leaves."""
    from polisyos.core.contracts import (
        RegisteredDerivedInputProfileRef,
        load_registered_derived_input_profile,
        verify_registered_derived_family,
    )
    from polisyos.core.derivations import load_selected_transform_family_registry
    from polisyos.runtime.quality.acquisition_planner import (
        N7DerivationBasis,
        N7DerivationOperationNode,
        N7DerivationRoleInput,
        N7DerivationSourceNode,
        N7DerivationSupplierAlternative,
    )

    operation_selections = {row.node_id: row for row in selection.operation_nodes}
    if len(operation_selections) != len(selection.operation_nodes):
        return None
    profile_refs = {
        node_id: RegisteredDerivedInputProfileRef.model_validate(
            row.registered_profile_ref.model_dump(mode="python")
        )
        for node_id, row in operation_selections.items()
    }
    profiles = {
        node_id: load_registered_derived_input_profile(store, profile_ref)
        for node_id, profile_ref in profile_refs.items()
    }
    root_id = selection.root_node_id
    if (
        root_id is None
        or root_id not in profiles
        or not _profile_basis_match(profiles[root_id], target)
    ):
        return None
    _require_n7_v3_foundry_target_profile(
        store,
        target=target,
        obligation_set_ref=obligation_set_ref,
    )
    if not _same(profile_refs[root_id], selection.registered_profile_ref):
        return None

    registry_keys = {
        artifacts.artifact_ref_identity_key(profile.registry_ref) for profile in profiles.values()
    }
    if len(registry_keys) != 1:
        return None
    registry_ref = next(iter(profiles.values())).registry_ref
    registry = load_selected_transform_family_registry(store, registry_ref)
    supplier_rows: dict[tuple[str, str], list[NativeDerivationPlanningRoleSupplier]] = {}
    for row in selection.role_suppliers:
        if row.operation_node_id is None:
            return None
        supplier_rows.setdefault((row.operation_node_id, row.role), []).append(row)

    from polisyos.runtime.quality.acquisition_planner import _N7_REGISTERED_RELATION_PROFILE

    operation_nodes = []
    source_edges: dict[
        str,
        list[
            tuple[
                str,
                str,
                artifacts.ArtifactRef,
                N7DerivationBasis,
                tuple[NativeDerivationPlanningRoleSupplier, ...],
            ]
        ],
    ] = {}
    expected_supplier_keys: set[tuple[str, str]] = set()
    for node_id, configured in operation_selections.items():
        profile = profiles[node_id]
        profile_ref = profile_refs[node_id]
        if (
            profile.relation_profile != _N7_REGISTERED_RELATION_PROFILE
            or len(profile.inputs) != 2
            or not _same(profile.registry_ref, registry_ref)
        ):
            return None
        profile_inputs = {row.role: row for row in profile.inputs}
        configured_inputs = {row.role: row for row in configured.role_inputs}
        if set(profile_inputs) != set(configured_inputs):
            return None

        input_kinds: dict[str, str] = {}
        role_inputs = []
        for role, configured_input in configured_inputs.items():
            profile_input = profile_inputs[role]
            source_basis = N7DerivationBasis.model_validate(
                profile_input.basis.model_dump(mode="python")
            )
            if configured_input.input_kind == "certified_derived":
                if (
                    role != profile.denominator_role
                    or configured_input.input_node_id not in operation_selections
                ):
                    return None
                input_kinds[role] = "certified_derived"
            else:
                key = (node_id, role)
                rows = tuple(supplier_rows.get(key, ()))
                if not rows or {row.provider.source_node_id for row in rows} != {
                    configured_input.input_node_id
                }:
                    return None
                expected_supplier_keys.add(key)
                input_kinds[role] = "candidate_source"
                source_edges.setdefault(configured_input.input_node_id, []).append(
                    (node_id, role, profile_ref, source_basis, rows)
                )
            role_inputs.append(
                N7DerivationRoleInput(
                    role=role,
                    input_node_id=configured_input.input_node_id,
                    source_basis=source_basis,
                )
            )

        families = tuple(
            family
            for family in registry.families
            if family.family_id == profile.family_id
            and family.method_version == profile.method_version
        )
        if len(families) != 1:
            return None
        verify_registered_derived_family(
            profile,
            families[0],
            input_kinds=input_kinds,
        )
        output_basis = N7DerivationBasis.model_validate(profile.output.model_dump(mode="python"))
        operation_nodes.append(
            N7DerivationOperationNode(
                node_id=node_id,
                operator_ref=profile.registry_ref,
                family_id=profile.family_id,
                method_version=profile.method_version,
                output_basis=output_basis,
                role_inputs=tuple(role_inputs),
                registered_profile_ref=profile_ref,
            )
        )
    if set(supplier_rows) != expected_supplier_keys:
        return None

    prepared_sources: list[N7DerivationSourceNode] = []
    for source_node_id, edges in sorted(source_edges.items()):
        source_basis = edges[0][3]
        basis_fields = (
            "semantic_definition_ref",
            "representation_ref",
            "binding_profile_ref",
        )
        if any(
            tuple(
                artifacts.artifact_ref_identity_key(getattr(edge[3], field))
                for field in basis_fields
            )
            != tuple(
                artifacts.artifact_ref_identity_key(getattr(source_basis, field))
                for field in basis_fields
            )
            for edge in edges[1:]
        ):
            return None

        alternatives: dict[
            tuple[str, str, str, str | None],
            tuple[artifacts.ArtifactRef, AcquisitionSupplierDeclaration, ModelInputScope],
        ] = {}
        role_bindings: list[dict[str, object]] = []
        for operation_id, role, profile_ref, edge_basis, role_supplier_rows in edges:
            eligible_rows = _eligible_n7_v3_supplier_rows(
                store,
                rows=role_supplier_rows,
                basis=edge_basis,
                target_scope=target.port.scope,
            )
            if not eligible_rows:
                return None
            expected_scopes = [scope for _row, _declaration, scope in eligible_rows]
            for supplier, declaration, scope in eligible_rows:
                supplier_key = artifacts.artifact_ref_identity_key(supplier.source_declaration_ref)
                alternatives[supplier_key] = (
                    supplier.source_declaration_ref,
                    declaration,
                    scope,
                )
            if any(scope != expected_scopes[0] for scope in expected_scopes[1:]):
                return None
            role_bindings.append(
                {
                    "operation_node_id": operation_id,
                    "role": role,
                    "input_kind": "candidate_source",
                    "input_node_id": source_node_id,
                    "registered_profile_ref": profile_ref.model_dump(mode="json"),
                    "source_basis": edge_basis.model_dump(mode="json"),
                }
            )

        declarations = tuple(alternatives.values())
        variables = {row[1].entry.target_variable for row in declarations}
        scopes = {row[2] for row in declarations}
        if len(variables) != 1 or len(scopes) != 1:
            return None
        declaration_ref, declaration, requested_scope = min(
            declarations,
            key=lambda item: artifacts.artifact_ref_identity_key(item[0]),
        )
        role_bindings.sort(key=lambda row: (str(row["operation_node_id"]), str(row["role"])))
        gap = _role_input_gap(
            target=target,
            obligation_set_ref=obligation_set_ref,
            routing_report_ref=routing_report_ref,
            profile_ref=artifacts.ArtifactRef.model_validate(
                role_bindings[0]["registered_profile_ref"]
            ),
            role=str(role_bindings[0]["role"]),
            basis=source_basis,
            declaration_ref=declaration_ref,
            declaration=declaration,
            context=context,
            scope=requested_scope,
            authority_level=authority_level,
            operation_role_bindings=tuple(role_bindings),
        )
        prepared_sources.append(
            N7DerivationSourceNode(
                node_id=source_node_id,
                source_basis=source_basis,
                supplier_alternatives=tuple(
                    N7DerivationSupplierAlternative(
                        supplier_ref=ref,
                        source_basis=source_basis,
                    )
                    for ref, _declaration, _scope in declarations
                ),
                requirement_gap=gap,
            )
        )

    return tuple(operation_nodes), tuple(prepared_sources), root_id


def resolve_configured_n7_derivation_plan(
    store: ArtifactStore,
    *,
    selector: Callable[..., tuple[NativeDerivationPlanningSelection, ...]],
    expected: GenericN5ExecutionJoinExpectation,
    routing_report_ref: artifacts.ArtifactRef,
    authority_level: object,
) -> artifacts.ArtifactRef | None:
    """Persist a candidate plan for one actual target and adopted registration.

    Returns a selected bundle only when exactly one adopted registration matches
    one actual compiler target and every required role has a real compatible
    Catalog declaration. ``None`` preserves target-pending candidate behavior.
    This does not supply prices, currentness, VOI, grants, or semantic admission.
    """
    from polisyos.core.contracts import (
        RegisteredDerivedInputProfileRef,
        load_registered_derived_input_profile,
    )
    from polisyos.data_forge.read_api.catalog import (
        AcquisitionAuthorityError,
        acquisition_supplier_declaration_scope_refusal,
        load_acquisition_supplier_declaration,
    )
    from polisyos.runtime.quality.acquisition_planner import (
        N7DerivationBasis,
        N7DerivationSourceNode,
        N7DerivationSupplierAlternative,
    )
    from polisyos.runtime.quality.acquisition_world_growth import NativeDerivationPlanningSelection
    from polisyos.runtime.quality.model_input_routing import read_model_input_routing_report
    from polisyos.runtime.quality.n7_input_obligation_source import _selected_model_requirements
    from polisyos.runtime.quality.n7_registered_derivation_plan import (
        persist_registered_n7_derivation_plan,
    )

    selections = selector(
        tenant_id=expected.tenant_id,
        cell_id=expected.cell_id,
        profile_selection_ref=expected.profile_selection_ref,
    )
    if type(selections) is not tuple or any(
        type(row) is not NativeDerivationPlanningSelection for row in selections
    ):
        raise TypeError("n7_derivation_planning_selection_untyped")
    selections = tuple(
        NativeDerivationPlanningSelection.model_validate(row.model_dump(mode="python"))
        for row in selections
    )
    if not selections:
        return None
    if expected.model_input_obligation_set_ref is None or expected.status != "simulation_blocked":
        raise ValueError("n7_derivation_planning_blocked_invocation_required")
    routing = read_model_input_routing_report(store, routing_report_ref)
    if not routing.routes:
        return None
    compilation, _target, _routing = _selected_model_requirements(
        store,
        obligation_set_ref=expected.model_input_obligation_set_ref,
        routing_report_ref=routing_report_ref,
        target_obligation_ref=routing.routes[0].obligation_ref,
    )
    context = compilation.context
    if (
        context.run_id != expected.run_id
        or context.candidate_id != expected.candidate_id
        or context.candidate_content_hash != expected.candidate_atom_hash
        or context.design_problem_ref != expected.design_problem_ref
    ):
        raise ValueError("n7_derivation_planning_compiler_context_mismatch")
    matches = []
    for selection in selections:
        if (selection.tenant_id, selection.cell_id, selection.profile_selection_ref) != (
            expected.tenant_id,
            expected.cell_id,
            expected.profile_selection_ref,
        ):
            raise ValueError("n7_derivation_planning_selection_scope_mismatch")
        try:
            profile = load_registered_derived_input_profile(
                store,
                RegisteredDerivedInputProfileRef.model_validate(
                    selection.registered_profile_ref.model_dump(mode="python")
                ),
            )
        except (FileNotFoundError, ValueError):
            continue
        matches.extend(
            (selection, profile, target)
            for target in compilation.requirements
            if _profile_basis_match(profile, target)
        )
    if len(matches) != 1:
        return None
    selection, profile, target = matches[0]
    if selection.operation_nodes:
        try:
            graph = _configured_v3_operation_graph(
                store,
                selection=selection,
                target=target,
                obligation_set_ref=expected.model_input_obligation_set_ref,
                routing_report_ref=routing_report_ref,
                context=context,
                authority_level=authority_level,
            )
            if graph is None:
                return None
            operation_nodes, source_nodes, root_node_id = graph
            return persist_registered_n7_derivation_plan(
                store,
                routing_report_ref=routing_report_ref,
                obligation_set_ref=expected.model_input_obligation_set_ref,
                target_obligation_ref=target.obligation_ref,
                registered_profile_ref=selection.registered_profile_ref,
                dag_budget_profile_ref=selection.dag_budget_profile_ref,
                operation_nodes=operation_nodes,
                source_nodes=source_nodes,
                root_node_id=root_node_id,
            )
        except (FileNotFoundError, ValueError):
            return None
    by_role = {}
    for row in selection.role_suppliers:
        by_role.setdefault(row.role, []).append(row)
    if set(by_role) != {row.role for row in profile.inputs}:
        return None
    prepared = []
    for row in profile.inputs:
        role_rows = by_role[row.role]
        if len({item.provider.source_node_id for item in role_rows}) != 1:
            return None
        basis = N7DerivationBasis.model_validate(row.basis.model_dump(mode="python"))
        alternatives = []
        declarations = []
        for supplier in role_rows:
            try:
                declaration = load_acquisition_supplier_declaration(
                    store, supplier.source_declaration_ref
                )
                entry = declaration.entry
                if (
                    not _same(supplier.provider.supplier_ref, supplier.source_declaration_ref)
                    or entry.entry_id != supplier.provider.authority_entry_id
                    or declaration.connector_id != supplier.provider.connector_id
                    or entry.source_semantic_definition_ref is None
                    or entry.source_representation_ref is None
                    or not _same(
                        entry.source_semantic_definition_ref, basis.semantic_definition_ref
                    )
                    or not _same(entry.source_representation_ref, basis.representation_ref)
                ):
                    continue
                scope = _role_scope(
                    store, target_scope=target.port.scope, basis=basis, declaration=declaration
                )
                if (
                    acquisition_supplier_declaration_scope_refusal(
                        store, supplier.source_declaration_ref, scope=scope
                    )
                    is not None
                ):
                    continue
            except (AcquisitionAuthorityError, FileNotFoundError, ValueError):
                continue
            alternatives.append(
                N7DerivationSupplierAlternative(
                    supplier_ref=supplier.source_declaration_ref, source_basis=basis
                )
            )
            declarations.append((supplier.source_declaration_ref, declaration, scope))
        if (
            not alternatives
            or len(
                {declaration.entry.target_variable for _ref, declaration, _scope in declarations}
            )
            != 1
        ):
            return None
        # The first sorted declaration is the request's owner-carried locator;
        # all accepted alternatives remain explicit OR suppliers in this leaf.
        declaration_ref, declaration, scope = min(
            declarations, key=lambda item: artifacts.artifact_ref_identity_key(item[0])
        )
        gap = _role_input_gap(
            target=target,
            obligation_set_ref=expected.model_input_obligation_set_ref,
            routing_report_ref=routing_report_ref,
            profile_ref=selection.registered_profile_ref,
            role=row.role,
            basis=basis,
            declaration_ref=declaration_ref,
            declaration=declaration,
            context=context,
            scope=scope,
            authority_level=authority_level,
        )
        prepared.append(
            (
                row.role,
                N7DerivationSourceNode(
                    node_id=role_rows[0].provider.source_node_id,
                    source_basis=basis,
                    supplier_alternatives=tuple(alternatives),
                    requirement_gap=gap,
                ),
            )
        )
    try:
        return persist_registered_n7_derivation_plan(
            store,
            routing_report_ref=routing_report_ref,
            obligation_set_ref=expected.model_input_obligation_set_ref,
            target_obligation_ref=target.obligation_ref,
            registered_profile_ref=selection.registered_profile_ref,
            dag_budget_profile_ref=selection.dag_budget_profile_ref,
            role_sources=tuple(prepared),
        )
    except (FileNotFoundError, ValueError):
        return None


def _registered_n7_v3_bundle_graph(
    store: ArtifactStore,
    bundle: N7DerivationBundle,
) -> tuple[
    object,
    CompiledModelInputRequirement,
    dict[str, tuple[dict[str, object], ...]],
    dict[tuple[str, str], dict[str, object]],
    dict[str, RegisteredDerivedInputProfile],
]:
    """Reopen the exact v3 registered graph and derive its source-role edges."""
    from polisyos.core.contracts import (
        RegisteredDerivedInputProfileRef,
        load_registered_derived_input_profile,
        verify_registered_derived_family,
    )
    from polisyos.core.derivations import load_selected_transform_family_registry
    from polisyos.runtime.quality.acquisition_planner import (
        _N7_REGISTERED_RELATION_PROFILE,
        N7DerivationBasis,
        N7DerivationBundle,
        _n7_exact_wire,
    )
    from polisyos.runtime.quality.n7_input_obligation_source import (
        _selected_model_requirements,
    )

    if (
        type(bundle) is not N7DerivationBundle
        or bundle.schema_version != "policyos.runtime.n7_derivation_bundle.v3"
        or bundle.model_input_routing_report_ref is None
        or bundle.registered_profile_ref is None
    ):
        raise ValueError("n7_registered_graph_bundle_version_invalid")
    bundle = N7DerivationBundle.model_validate(bundle.model_dump(mode="python"))
    compilation, target, _routing = _selected_model_requirements(
        store,
        obligation_set_ref=bundle.obligation_set_ref,
        routing_report_ref=bundle.model_input_routing_report_ref,
        target_obligation_ref=bundle.model_input_obligation_ref,
    )
    _require_n7_v3_foundry_target_profile(
        store,
        target=target,
        obligation_set_ref=bundle.obligation_set_ref,
    )

    source_nodes = {row.node_id: row for row in bundle.source_nodes}
    operation_nodes = {row.node_id: row for row in bundle.operation_nodes}
    if len(source_nodes) != len(bundle.source_nodes) or len(operation_nodes) != len(
        bundle.operation_nodes
    ):
        raise ValueError("n7_registered_graph_node_duplicate")
    if set(source_nodes).intersection(operation_nodes):
        raise ValueError("n7_registered_graph_node_duplicate")

    profiles: dict[str, RegisteredDerivedInputProfile] = {}
    registry_keys: set[tuple[str, str, str, str | None]] = set()
    for node_id, operation in operation_nodes.items():
        profile_ref = operation.registered_profile_ref
        if profile_ref is None:
            raise ValueError("n7_registered_graph_operation_profile_missing")
        profile = load_registered_derived_input_profile(
            store,
            RegisteredDerivedInputProfileRef.model_validate(profile_ref.model_dump(mode="python")),
        )
        if (
            profile.relation_profile != _N7_REGISTERED_RELATION_PROFILE
            or len(profile.inputs) != 2
            or profile.family_id != operation.family_id
            or profile.method_version != operation.method_version
            or not _same(profile.registry_ref, operation.operator_ref)
            or _basis_identity_key(profile.output) != _basis_identity_key(operation.output_basis)
        ):
            raise ValueError("n7_registered_graph_operation_profile_mismatch")
        profiles[node_id] = profile
        registry_keys.add(artifacts.artifact_ref_identity_key(profile.registry_ref))

    if len(registry_keys) != 1:
        raise ValueError("n7_registered_graph_registry_mismatch")
    root_profile = profiles.get(bundle.root_node_id)
    root_operation = operation_nodes.get(bundle.root_node_id)
    if (
        root_profile is None
        or root_operation is None
        or root_operation.registered_profile_ref is None
        or not _same(root_operation.registered_profile_ref, bundle.registered_profile_ref)
        or not _profile_basis_match(root_profile, target)
        or _basis_identity_key(root_profile.output) != _basis_identity_key(bundle.target_basis)
    ):
        raise ValueError("n7_registered_graph_root_profile_mismatch")

    registry_ref = root_profile.registry_ref
    registry = load_selected_transform_family_registry(store, registry_ref)
    role_edges: dict[tuple[str, str], dict[str, object]] = {}
    source_bindings: dict[str, list[dict[str, object]]] = {}
    for node_id, operation in operation_nodes.items():
        profile = profiles[node_id]
        profile_inputs = {row.role: row for row in profile.inputs}
        operation_inputs = {row.role: row for row in operation.role_inputs}
        if set(profile_inputs) != set(operation_inputs):
            raise ValueError("n7_registered_graph_operation_roles_mismatch")
        input_kinds: dict[str, str] = {}
        for role, edge in operation_inputs.items():
            profile_input = profile_inputs[role]
            basis = N7DerivationBasis.model_validate(profile_input.basis.model_dump(mode="python"))
            if _basis_identity_key(basis) != _basis_identity_key(edge.source_basis):
                raise ValueError("n7_registered_graph_edge_basis_mismatch")
            if edge.input_node_id in source_nodes:
                input_kind = "candidate_source"
                input_kinds[role] = input_kind
                binding = {
                    "operation_node_id": node_id,
                    "role": role,
                    "input_kind": input_kind,
                    "input_node_id": edge.input_node_id,
                    "registered_profile_ref": operation.registered_profile_ref.model_dump(
                        mode="json"
                    ),
                    "source_basis": basis.model_dump(mode="json"),
                }
                source_bindings.setdefault(edge.input_node_id, []).append(binding)
            elif edge.input_node_id in operation_nodes:
                input_kind = "certified_derived"
                if role != profile.denominator_role or _basis_identity_key(
                    operation_nodes[edge.input_node_id].output_basis
                ) != _basis_identity_key(basis):
                    raise ValueError("n7_registered_graph_derived_edge_refused")
                input_kinds[role] = input_kind
            else:
                raise ValueError("n7_registered_graph_input_node_missing")
            role_edges[(node_id, role)] = {
                "operation_node_id": node_id,
                "role": role,
                "input_kind": input_kind,
                "input_node_id": edge.input_node_id,
                "registered_profile_ref": operation.registered_profile_ref,
                "source_basis": basis,
            }

        family = tuple(
            row
            for row in registry.families
            if row.family_id == profile.family_id and row.method_version == profile.method_version
        )
        if len(family) != 1:
            raise ValueError("n7_registered_graph_family_missing")
        verify_registered_derived_family(profile, family[0], input_kinds=input_kinds)

    if set(source_bindings) != set(source_nodes):
        raise ValueError("n7_registered_graph_source_edge_set_mismatch")
    canonical_bindings: dict[str, tuple[dict[str, object], ...]] = {}
    for source_node_id, rows in source_bindings.items():
        rows.sort(key=lambda row: (str(row["operation_node_id"]), str(row["role"])))
        canonical = tuple(rows)
        source = source_nodes[source_node_id]
        if any(
            _basis_identity_key(N7DerivationBasis.model_validate(row["source_basis"]))
            != _basis_identity_key(source.source_basis)
            for row in canonical
        ):
            raise ValueError("n7_registered_graph_source_basis_mismatch")
        gap = source.requirement_gap
        if gap is not None:
            metadata = gap.metadata
            if (
                gap.requirement_schema_version != ROLE_INPUT_GAP_SCHEMA_VERSION
                or metadata.get("source") != "registered_derivation_role_input"
                or _n7_exact_wire(metadata.get("operation_role_bindings"))
                != _n7_exact_wire(list(canonical))
                or not _same(
                    _ref(metadata.get("registered_profile_ref")),
                    artifacts.ArtifactRef.model_validate(canonical[0]["registered_profile_ref"]),
                )
                or metadata.get("role") != canonical[0]["role"]
                or _n7_exact_wire(metadata.get("source_basis"))
                != _n7_exact_wire(source.source_basis.model_dump(mode="json"))
            ):
                raise ValueError("n7_registered_graph_source_gap_binding_mismatch")
        canonical_bindings[source_node_id] = canonical
    return compilation, target, canonical_bindings, role_edges, profiles


def _basis_identity_key(value: object) -> tuple[tuple[str, str, str, str | None], ...]:
    return tuple(
        artifacts.artifact_ref_identity_key(getattr(value, field))
        for field in (
            "semantic_definition_ref",
            "representation_ref",
            "binding_profile_ref",
        )
    )


def validate_registered_n7_v3_planning_selection(
    store: ArtifactStore,
    selection: NativeDerivationPlanningSelection,
    bundle: N7DerivationBundle,
) -> tuple[NativeDerivationPlanningRoleSupplier, ...]:
    """Replay graph edges and return only the persisted leaf supplier projection."""
    from polisyos.runtime.quality.acquisition_planner import (
        N7DerivationBasis,
        N7DerivationBundle,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        NativeDerivationPlanningSelection,
    )

    if (
        type(selection) is not NativeDerivationPlanningSelection
        or type(bundle) is not N7DerivationBundle
        or bundle.schema_version != "policyos.runtime.n7_derivation_bundle.v3"
    ):
        raise ValueError("n7_registered_graph_planning_selection_invalid")
    _compilation, target, _bindings_by_source, edges, profiles = _registered_n7_v3_bundle_graph(
        store, bundle
    )
    operations = {row.node_id: row for row in bundle.operation_nodes}
    configured = {row.node_id: row for row in selection.operation_nodes}
    if (
        selection.root_node_id != bundle.root_node_id
        or len(configured) != len(selection.operation_nodes)
        or set(configured) != set(operations)
        or not _same(selection.registered_profile_ref, bundle.registered_profile_ref)
        or not _same(selection.dag_budget_profile_ref, bundle.dag_budget_profile_ref)
    ):
        raise ValueError("n7_registered_graph_planning_root_mismatch")
    for node_id, operation in operations.items():
        selected_operation = configured[node_id]
        if operation.registered_profile_ref is None or not _same(
            selected_operation.registered_profile_ref,
            operation.registered_profile_ref,
        ):
            raise ValueError("n7_registered_graph_planning_profile_mismatch")
        selected_inputs = {row.role: row for row in selected_operation.role_inputs}
        expected_inputs = {row.role: row for row in operation.role_inputs}
        if set(selected_inputs) != set(expected_inputs):
            raise ValueError("n7_registered_graph_planning_role_set_mismatch")
        for role, selected_input in selected_inputs.items():
            expected = edges[(node_id, role)]
            if (
                selected_input.input_kind != expected["input_kind"]
                or selected_input.input_node_id != expected["input_node_id"]
            ):
                raise ValueError("n7_registered_graph_planning_edge_mismatch")

    expected_supplier_roles = {
        key for key, row in edges.items() if row["input_kind"] == "candidate_source"
    }
    supplied_rows: dict[tuple[str, str], list[NativeDerivationPlanningRoleSupplier]] = {}
    for row in selection.role_suppliers:
        if row.operation_node_id is None:
            raise ValueError("n7_registered_graph_planning_supplier_unbound")
        key = (row.operation_node_id, row.role)
        if key not in expected_supplier_roles:
            raise ValueError("n7_registered_graph_planning_supplier_role_mismatch")
        expected = edges[key]
        if row.provider.source_node_id != expected["input_node_id"]:
            raise ValueError("n7_registered_graph_planning_supplier_node_mismatch")
        supplied_rows.setdefault(key, []).append(row)
    if set(supplied_rows) != expected_supplier_roles:
        raise ValueError("n7_registered_graph_planning_supplier_set_mismatch")

    source_nodes = {row.node_id: row for row in bundle.source_nodes}
    source_scopes: dict[str, set[object]] = {}
    source_variables: dict[str, set[str]] = {}
    eligible_supplier_refs: dict[str, set[tuple[str, str, str, str | None]]] = {}
    eligible_provider_rows: dict[
        tuple[str, tuple[str, str, str, str | None]], NativeDerivationPlanningRoleSupplier
    ] = {}
    for (operation_node_id, role), rows in supplied_rows.items():
        expected = edges[(operation_node_id, role)]
        basis = N7DerivationBasis.model_validate(expected["source_basis"])
        source_node = source_nodes[str(expected["input_node_id"])]
        profile = profiles[operation_node_id]
        original_inputs = {row.role: row for row in profile.inputs}
        if role not in original_inputs or _basis_identity_key(original_inputs[role].basis) != (
            _basis_identity_key(basis)
        ):
            raise ValueError("n7_registered_graph_planning_supplier_basis_mismatch")
        eligible_rows = _eligible_n7_v3_supplier_rows(
            store,
            rows=tuple(rows),
            basis=basis,
            target_scope=target.port.scope,
        )
        if not eligible_rows:
            raise ValueError("n7_registered_graph_planning_supplier_scope_refused")
        scopes = {scope for _row, _declaration, scope in eligible_rows}
        variables = {
            declaration.entry.target_variable for _row, declaration, _scope in eligible_rows
        }
        if len(variables) != 1 or len(scopes) != 1:
            raise ValueError("n7_registered_graph_planning_supplier_scope_ambiguous")
        for row, declaration, scope in eligible_rows:
            ref_key = artifacts.artifact_ref_identity_key(row.source_declaration_ref)
            eligible_supplier_refs.setdefault(source_node.node_id, set()).add(ref_key)
            eligible_provider_rows[(source_node.node_id, ref_key)] = row
            source_scopes.setdefault(source_node.node_id, set()).add(scope)
            source_variables.setdefault(source_node.node_id, set()).add(
                declaration.entry.target_variable
            )

    for source_node_id, source_node in source_nodes.items():
        eligible = eligible_supplier_refs.get(source_node_id, set())
        persisted = {
            artifacts.artifact_ref_identity_key(item.supplier_ref)
            for item in source_node.supplier_alternatives
        }
        if not eligible or eligible != persisted:
            raise ValueError("n7_registered_graph_planning_supplier_alternatives_mismatch")
        gap = source_node.requirement_gap
        if gap is None:
            raise ValueError("n7_registered_graph_planning_source_gap_missing")
        for (_node_id, _ref_key), row in sorted(eligible_provider_rows.items()):
            if row.provider.source_node_id != source_node_id:
                continue
            validate_registered_n7_v3_role_input_gap(
                store,
                bundle,
                source_node,
                gap,
                supplier_ref=row.source_declaration_ref,
                authority_entry_id=row.provider.authority_entry_id,
                connector_id=row.provider.connector_id,
            )
    if any(len(values) != 1 for values in (*source_scopes.values(), *source_variables.values())):
        raise ValueError("n7_registered_graph_planning_source_alternatives_ambiguous")
    return tuple(eligible_provider_rows[key] for key in sorted(eligible_provider_rows))


def validate_registered_n7_v3_role_input_gap(
    store: ArtifactStore,
    bundle: N7DerivationBundle,
    source_node: N7DerivationSourceNode,
    gap: AcquisitionRequirementGap,
    *,
    supplier_ref: artifacts.ArtifactRef,
    authority_entry_id: str,
    connector_id: str,
    expected_country_code: str | None = None,
    expected_data_time: str | None = None,
) -> str:
    """Replay one selected v3 source leaf against every operation edge using it."""
    from polisyos.data_forge.read_api.catalog import (
        acquisition_supplier_declaration_scope_refusal,
        load_acquisition_supplier_declaration,
    )
    from polisyos.runtime.quality.acquisition_planner import N7DerivationBasis, _n7_exact_wire

    compilation, target, bindings_by_source, _edges, _profiles = _registered_n7_v3_bundle_graph(
        store, bundle
    )
    current_nodes = tuple(row for row in bundle.source_nodes if row.node_id == source_node.node_id)
    if (
        len(current_nodes) != 1
        or _n7_exact_wire(current_nodes[0].model_dump(mode="json"))
        != _n7_exact_wire(source_node.model_dump(mode="json"))
        or source_node.requirement_gap is None
        or _n7_exact_wire(gap.model_dump(mode="json"))
        != _n7_exact_wire(source_node.requirement_gap.model_dump(mode="json"))
        or gap.requirement_schema_version != ROLE_INPUT_GAP_SCHEMA_VERSION
        or gap.metadata.get("source") != "registered_derivation_role_input"
    ):
        raise ValueError("n7_registered_graph_source_leaf_mismatch")
    bindings = bindings_by_source.get(source_node.node_id)
    if not bindings:
        raise ValueError("n7_registered_graph_source_role_missing")
    metadata = gap.metadata
    for field, expected_ref in (
        ("model_input_obligation_set_ref", bundle.obligation_set_ref),
        ("model_input_obligation_ref", bundle.model_input_obligation_ref),
        ("model_input_routing_report_ref", bundle.model_input_routing_report_ref),
    ):
        if expected_ref is None or not _same(_ref(metadata.get(field)), expected_ref):
            raise ValueError("n7_registered_graph_source_parent_mismatch")
    if _n7_exact_wire(metadata.get("operation_role_bindings")) != _n7_exact_wire(list(bindings)):
        raise ValueError("n7_registered_graph_source_role_binding_mismatch")

    first = bindings[0]
    first_profile_ref = artifacts.ArtifactRef.model_validate(first["registered_profile_ref"])
    original_ref = _ref(metadata.get("source_declaration_ref"))
    original = load_acquisition_supplier_declaration(store, original_ref)
    selected = load_acquisition_supplier_declaration(store, supplier_ref)
    requested_scopes = []
    for binding in bindings:
        basis = N7DerivationBasis.model_validate(binding["source_basis"])
        for declaration_ref, declaration in ((original_ref, original), (supplier_ref, selected)):
            entry = declaration.entry
            if (
                entry.source_semantic_definition_ref is None
                or entry.source_representation_ref is None
                or not _same(entry.source_semantic_definition_ref, basis.semantic_definition_ref)
                or not _same(entry.source_representation_ref, basis.representation_ref)
            ):
                raise ValueError("n7_registered_graph_source_basis_refused")
            scope = _role_scope(
                store,
                target_scope=target.port.scope,
                basis=basis,
                declaration=declaration,
            )
            if (
                acquisition_supplier_declaration_scope_refusal(store, declaration_ref, scope=scope)
                is not None
            ):
                raise ValueError("n7_registered_graph_source_scope_refused")
            requested_scopes.append(scope)
    if len(set(requested_scopes)) != 1 or _n7_exact_wire(
        metadata.get("requested_role_scope")
    ) != _n7_exact_wire(requested_scopes[0].model_dump(mode="json")):
        raise ValueError("n7_registered_graph_source_scope_mismatch")
    if (
        original.entry.target_variable != selected.entry.target_variable
        or metadata.get("variable_id") != original.entry.target_variable
        or selected.entry.entry_id != authority_entry_id
        or selected.connector_id != connector_id
        or artifacts.artifact_ref_identity_key(supplier_ref)
        not in {
            artifacts.artifact_ref_identity_key(row.supplier_ref)
            for row in source_node.supplier_alternatives
        }
    ):
        raise ValueError("n7_registered_graph_selected_supplier_refused")
    if (expected_country_code is None) != (expected_data_time is None):
        raise ValueError("n7_registered_graph_query_scope_incomplete")
    if expected_country_code is not None and expected_data_time is not None:
        from datetime import date

        scope = target.port.scope
        if (
            not expected_country_code.isascii()
            or not expected_country_code.isalpha()
            or len(expected_country_code) != 3
            or not expected_data_time.isascii()
            or not expected_data_time.isdecimal()
            or len(expected_data_time) != 4
        ):
            raise ValueError("n7_registered_graph_query_scope_invalid")
        query_year = int(expected_data_time)
        if (
            _n7_v3_query_country_code(scope, selected) != expected_country_code
            or scope.period_basis != "calendar_year"
            or scope.time_role != "observation_time"
            or scope.period_start != date(query_year, 1, 1)
            or scope.period_end != date(query_year, 12, 31)
            or expected_country_code not in selected.entry.country_codes
        ):
            raise ValueError("n7_registered_graph_query_scope_mismatch")
    recomputed = _role_input_gap(
        target=target,
        obligation_set_ref=bundle.obligation_set_ref,
        routing_report_ref=bundle.model_input_routing_report_ref,
        profile_ref=first_profile_ref,
        role=str(first["role"]),
        basis=N7DerivationBasis.model_validate(first["source_basis"]),
        declaration_ref=original_ref,
        declaration=original,
        context=compilation.context,
        scope=requested_scopes[0],
        authority_level=gap.authority_level,
        operation_role_bindings=bindings,
    )
    if _n7_exact_wire(gap.model_dump(mode="json")) != _n7_exact_wire(
        recomputed.model_dump(mode="json")
    ):
        raise ValueError("n7_registered_graph_source_gap_content_mismatch")
    return selected.entry.target_variable


def validate_registered_derivation_role_input_gap(
    store: ArtifactStore,
    gap: AcquisitionRequirementGap,
    *,
    supplier_ref: artifacts.ArtifactRef,
    authority_entry_id: str,
    connector_id: str,
    expected_registered_profile_ref: artifacts.ArtifactRef,
    expected_obligation_set_ref: artifacts.ArtifactRef,
    expected_target_obligation_ref: artifacts.ArtifactRef,
    expected_routing_report_ref: artifacts.ArtifactRef,
) -> str:
    """Replay a role request at the native effect boundary, without granting it.

    The caller independently selects the actual v2 bundle/source/cycle. This
    helper verifies their exact profile/set/target/routing namespace, the full
    compiler denominator, and the selected supplier's actual Catalog declaration.
    The returned variable identity is a source-owner value, not a name guessed
    from an arithmetic role. Current rights, quote, PA2 and DS9 stay separate.
    """
    from polisyos.core.contracts import (
        RegisteredDerivedInputProfileRef,
        load_registered_derived_input_profile,
    )
    from polisyos.data_forge.read_api.catalog import (
        acquisition_supplier_declaration_scope_refusal,
        load_acquisition_supplier_declaration,
    )
    from polisyos.runtime.quality.acquisition_planner import N7DerivationBasis, _n7_exact_wire
    from polisyos.runtime.quality.n7_input_obligation_source import _selected_model_requirements

    metadata = gap.metadata
    if (
        gap.requirement_schema_version != ROLE_INPUT_GAP_SCHEMA_VERSION
        or metadata.get("source") != "registered_derivation_role_input"
    ):
        raise ValueError("n7_registered_role_gap_schema_invalid")
    for field, expected_ref in (
        ("registered_profile_ref", expected_registered_profile_ref),
        ("model_input_obligation_set_ref", expected_obligation_set_ref),
        ("model_input_obligation_ref", expected_target_obligation_ref),
        ("model_input_routing_report_ref", expected_routing_report_ref),
    ):
        if not _same(_ref(metadata.get(field)), expected_ref):
            raise ValueError("n7_registered_role_gap_selected_parent_mismatch")
    compilation, target, _routing = _selected_model_requirements(
        store,
        obligation_set_ref=expected_obligation_set_ref,
        routing_report_ref=expected_routing_report_ref,
        target_obligation_ref=expected_target_obligation_ref,
    )
    profile = load_registered_derived_input_profile(
        store,
        RegisteredDerivedInputProfileRef.model_validate(
            expected_registered_profile_ref.model_dump(mode="python")
        ),
    )
    if not _profile_basis_match(profile, target):
        raise ValueError("n7_registered_role_gap_profile_target_mismatch")
    roles = tuple(row for row in profile.inputs if row.role == metadata.get("role"))
    if len(roles) != 1:
        raise ValueError("n7_registered_role_gap_profile_role_missing")
    role = roles[0]
    basis = N7DerivationBasis.model_validate(role.basis.model_dump(mode="python"))
    original_ref = _ref(metadata.get("source_declaration_ref"))
    original = load_acquisition_supplier_declaration(store, original_ref)
    scope = _role_scope(store, target_scope=target.port.scope, basis=basis, declaration=original)
    if (
        original.entry.source_semantic_definition_ref is None
        or original.entry.source_representation_ref is None
        or not _same(original.entry.source_semantic_definition_ref, basis.semantic_definition_ref)
        or not _same(original.entry.source_representation_ref, basis.representation_ref)
        or acquisition_supplier_declaration_scope_refusal(store, original_ref, scope=scope)
        is not None
    ):
        raise ValueError("n7_registered_role_gap_declaration_basis_refused")
    recomputed = _role_input_gap(
        target=target,
        obligation_set_ref=expected_obligation_set_ref,
        routing_report_ref=expected_routing_report_ref,
        profile_ref=expected_registered_profile_ref,
        role=role.role,
        basis=basis,
        declaration_ref=original_ref,
        declaration=original,
        context=compilation.context,
        scope=scope,
        authority_level=gap.authority_level,
    )
    if _n7_exact_wire(gap.model_dump(mode="json")) != _n7_exact_wire(
        recomputed.model_dump(mode="json")
    ):
        raise ValueError("n7_registered_role_gap_content_mismatch")
    selected = load_acquisition_supplier_declaration(store, supplier_ref)
    selected_scope = _role_scope(
        store, target_scope=target.port.scope, basis=basis, declaration=selected
    )
    if (
        selected.entry.entry_id != authority_entry_id
        or selected.connector_id != connector_id
        or selected.entry.target_variable != original.entry.target_variable
        or selected.entry.source_semantic_definition_ref is None
        or selected.entry.source_representation_ref is None
        or not _same(selected.entry.source_semantic_definition_ref, basis.semantic_definition_ref)
        or not _same(selected.entry.source_representation_ref, basis.representation_ref)
        or acquisition_supplier_declaration_scope_refusal(store, supplier_ref, scope=selected_scope)
        is not None
    ):
        raise ValueError("n7_registered_role_selected_supplier_refused")
    return selected.entry.target_variable
