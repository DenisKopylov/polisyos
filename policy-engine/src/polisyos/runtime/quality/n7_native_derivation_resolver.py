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
    from polisyos.data_requirement.model_input_requirements import CompiledModelInputRequirement
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionRequirementGap,
        N7DerivationBasis,
    )
    from polisyos.runtime.quality.acquisition_world_growth import NativeDerivationPlanningSelection
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
