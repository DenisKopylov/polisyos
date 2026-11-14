"""Persisted N7 derivation bundles keep source AND/OR closure candidate-only."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.foundry import ExecPlanRef, ProgramGraphRef
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    load_model_input_obligation_set,
)
from polisyos.runtime.quality import acquisition_planner as owner
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.model_input_requirements import (
    derive_program_graph_input_interface,
    preflight_program_graph_inputs,
)
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests.unit.runtime.quality.test_model_input_requirements import _stock_declaration
from tests.unit.runtime.quality.test_n7_descriptor_source_join import _source_gap


def _marker(store, name: str, *, kind: str = "tests.n7_derivation_marker") -> ArtifactRef:
    return store.put_json(
        {"name": name},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.N7DerivationMarker", version="1.0"),
        ),
        return_selected_profile=True,
    )


def _selected_target(tmp_path: Path):
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=1000,
        model_input_port_declaration_builder=_stock_declaration,
    )
    interface_ref = derive_program_graph_input_interface(
        case.store,
        program_graph_ref=ProgramGraphRef.model_validate(case.program_graph_ref.model_dump()),
        exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump()),
        registry_bundle_ref=case.registry_bundle_ref,
    )
    assert interface_ref is not None
    context = ModelInputContext(
        run_id="n7-derivation-bundle-test",
        candidate_id="program_graph_tax_subsidy_input",
        candidate_content_hash=str(case.policy_candidate_ref.artifact_id),
        design_problem_ref=str(case.trinity_ref.artifact_id),
        candidate_source_ref=case.policy_candidate_ref,
    )
    preflight = preflight_program_graph_inputs(
        case.store,
        interface_ref=interface_ref,
        program_graph_ref=ProgramGraphRef.model_validate(case.program_graph_ref.model_dump()),
        exec_plan_ref=ExecPlanRef.model_validate(case.exec_plan_ref.model_dump()),
        registry_bundle_ref=case.registry_bundle_ref,
        input_bindings_ref=case.input_bindings_ref,
        context=context,
        steps=(0, 1, 2),
    )
    selected_set, members = load_model_input_obligation_set(
        case.store, preflight.obligation_set_ref
    )
    assert len(members) == len(selected_set.obligation_refs) == 1
    obligation_ref = preflight.obligation_refs[0]
    target = owner.N7DerivationBasis(
        semantic_definition_ref=members[0].port.semantic_definition_ref,
        representation_ref=members[0].port.representation_ref,
        binding_profile_ref=members[0].port.binding_profile_ref,
    )
    return case, preflight.obligation_set_ref, obligation_ref, target, context


def _target_gap(context: ModelInputContext, variable_id: str) -> owner.AcquisitionRequirementGap:
    return owner.l1_variable_availability_requirement_gap(
        candidate_id=context.candidate_id,
        candidate_content_hash=context.candidate_content_hash,
        design_problem_ref=context.design_problem_ref,
        authority_level=owner.AuthorityLevel.RESEARCH,
        availability=L1VariableAvailability(
            variable_id=variable_id,
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref=f"fixture://missing/{variable_id}",
        ),
    )


def _profile(store) -> tuple[owner.N7DerivationDagBudgetProfile, ArtifactRef]:
    profile = owner.N7DerivationDagBudgetProfile(
        profile_id="test-small-graph",
        max_nodes=16,
        max_edges=32,
        max_depth=8,
        max_unique_sources=16,
    )
    return profile, owner.persist_n7_derivation_dag_budget_profile(store, profile)


def _registry_ref(store) -> ArtifactRef:
    from polisyos.core.derivations import (
        ArithmeticExpression,
        AssumptionRule,
        BasisSignature,
        TransformFamily,
        TransformFamilyRegistry,
        TransformInputSpec,
        persist_transform_family_registry,
    )

    family = TransformFamily(
        family_id="test.ratio_times_denominator",
        method_id="arithmetic.ratio_times_denominator",
        method_version="1.0",
        input_specs=(
            TransformInputSpec(
                role="denominator",
                basis=BasisSignature(quantity_kind="flow", unit="usd"),
            ),
            TransformInputSpec(
                role="ratio",
                basis=BasisSignature(quantity_kind="flow", unit="ratio"),
            ),
        ),
        output_basis=BasisSignature(quantity_kind="flow", unit="usd"),
        year_domain_role="ratio",
        expression=ArithmeticExpression(
            operator="multiply",
            operands=(
                ArithmeticExpression(operator="current_value", role="ratio"),
                ArithmeticExpression(operator="current_value", role="denominator"),
            ),
        ),
        assumption_rules=(AssumptionRule(name="fixture_context", literal_value="declared"),),
    )
    unselected = persist_transform_family_registry(
        store, TransformFamilyRegistry(families=(family,))
    )
    return ArtifactRef(
        artifact_id=unselected.artifact_id,
        kind=unselected.kind,
        media_type=unselected.media_type,
        manifest_profile_sha256=owner.artifacts.artifact_manifest_profile_sha256(
            store.get_manifest(unselected)
        ),
    )


def _source_basis(store, label: str) -> owner.N7DerivationBasis:
    return owner.N7DerivationBasis(
        semantic_definition_ref=_marker(
            store, f"{label}-definition", kind=owner._N7_DERIVATION_DEFINITION_KIND
        ),
        representation_ref=_marker(
            store, f"{label}-representation", kind=owner._N7_DERIVATION_REPRESENTATION_KIND
        ),
        binding_profile_ref=_marker(
            store, f"{label}-profile", kind=owner._N7_DERIVATION_BINDING_PROFILE_KIND
        ),
    )


def _complete_source(store, node_id: str, basis: owner.N7DerivationBasis):
    supplier_ref = _marker(store, f"{node_id}-supplier")
    return owner.N7DerivationSourceNode(
        node_id=node_id,
        source_basis=basis,
        supplier_alternatives=(
            owner.N7DerivationSupplierAlternative(
                supplier_ref=supplier_ref,
                source_basis=basis,
            ),
        ),
        selected_supplier_ref=supplier_ref,
        source_series_ref=_marker(
            store, f"{node_id}-series", kind=owner._N7_DERIVATION_SOURCE_SERIES_KIND
        ),
        occurrence_ref=_marker(
            store, f"{node_id}-occurrence", kind=owner._N7_DERIVATION_OCCURRENCE_KIND
        ),
        definition_ref=basis.semantic_definition_ref,
        representation_ref=basis.representation_ref,
        source_receipt_ref=_marker(
            store, f"{node_id}-receipt", kind=owner._N7_DERIVATION_SOURCE_RECEIPT_KIND
        ),
    )


def _pending_source(
    node_id: str,
    basis: owner.N7DerivationBasis,
    gap: owner.AcquisitionRequirementGap,
    *,
    alternatives: tuple[ArtifactRef, ...] = (),
):
    return owner.N7DerivationSourceNode(
        node_id=node_id,
        source_basis=basis,
        supplier_alternatives=tuple(
            owner.N7DerivationSupplierAlternative(supplier_ref=ref, source_basis=basis)
            for ref in alternatives
        ),
        requirement_gap=gap,
    )


def _bundle(
    *,
    obligation_set_ref: ArtifactRef,
    obligation_ref: ArtifactRef,
    target_basis: owner.N7DerivationBasis,
    budget: owner.N7DerivationDagBudgetProfile,
    budget_ref: ArtifactRef,
    sources: tuple[owner.N7DerivationSourceNode, ...],
    operator_ref: ArtifactRef,
    role_inputs: tuple[owner.N7DerivationRoleInput, ...],
    root_node_id: str = "derive-target",
    operation_nodes: tuple[owner.N7DerivationOperationNode, ...] | None = None,
) -> owner.N7DerivationBundle:
    operations = operation_nodes or (
        owner.N7DerivationOperationNode(
            node_id=root_node_id,
            operator_ref=operator_ref,
            family_id="test.ratio_times_denominator",
            method_version="1.0",
            output_basis=target_basis,
            role_inputs=role_inputs,
        ),
    )
    return owner.N7DerivationBundle(
        obligation_set_ref=obligation_set_ref,
        model_input_obligation_ref=obligation_ref,
        target_basis=target_basis,
        dag_budget_profile_ref=budget_ref,
        dag_budget_profile=budget,
        source_nodes=sources,
        operation_nodes=operations,
        root_node_id=root_node_id,
        input_closure_status=(
            "inputs_complete" if all(item.inputs_complete for item in sources) else "partial"
        ),
    )


def test_partial_and_bundle_persists_with_each_role_and_or_supplier_set(tmp_path: Path) -> None:
    case, obligation_set_ref, obligation_ref, target_basis, context = _selected_target(tmp_path)
    try:
        budget, budget_ref = _profile(case.store)
        ratio_basis = _source_basis(case.store, "ratio")
        denominator_basis = _source_basis(case.store, "denominator")
        ratio = _complete_source(case.store, "ratio-leaf", ratio_basis)
        supplier_a = _marker(case.store, "denominator-supplier-a")
        supplier_b = _marker(case.store, "denominator-supplier-b")
        denominator_gap = _target_gap(context, "economic.gdp")
        denominator = _pending_source(
            "denominator-leaf",
            denominator_basis,
            denominator_gap,
            alternatives=(supplier_a, supplier_b),
        )
        operator_ref = _registry_ref(case.store)
        bundle = _bundle(
            obligation_set_ref=obligation_set_ref,
            obligation_ref=obligation_ref,
            target_basis=target_basis,
            budget=budget,
            budget_ref=budget_ref,
            sources=(ratio, denominator),
            operator_ref=operator_ref,
            role_inputs=(
                owner.N7DerivationRoleInput(
                    role="ratio", input_node_id=ratio.node_id, source_basis=ratio_basis
                ),
                owner.N7DerivationRoleInput(
                    role="denominator",
                    input_node_id=denominator.node_id,
                    source_basis=denominator_basis,
                ),
            ),
        )

        selected = owner.persist_n7_derivation_bundle(case.store, bundle)
        reopened = owner.load_n7_derivation_bundle(case.store, selected)

        assert reopened.input_closure_status == "partial"
        assert reopened.target_satisfaction_status == "unsatisfied"
        assert len(reopened.operation_nodes[0].role_inputs) == 2
        pending = owner.n7_pending_unique_derivation_source_gaps(reopened)
        assert pending == (denominator_gap,)
        reopened_denominator = next(
            source for source in reopened.source_nodes if source.node_id == denominator.node_id
        )
        assert len(reopened_denominator.supplier_alternatives) == 2
        assert reopened_denominator.selected_supplier_ref is None
        wrong_roles = bundle.model_copy(
            update={
                "operation_nodes": (
                    bundle.operation_nodes[0].model_copy(
                        update={
                            "role_inputs": tuple(
                                edge.model_copy(update={"role": "base"})
                                if edge.role == "denominator"
                                else edge
                                for edge in bundle.operation_nodes[0].role_inputs
                            )
                        }
                    ),
                )
            }
        )
        with pytest.raises(ValueError, match="n7_derivation_operator_required_roles_mismatch"):
            owner.persist_n7_derivation_bundle(case.store, wrong_roles)

        complete_denominator = owner.N7DerivationSourceNode(
            node_id=denominator.node_id,
            source_basis=denominator.source_basis,
            supplier_alternatives=denominator.supplier_alternatives,
            selected_supplier_ref=supplier_a,
            source_series_ref=_marker(
                case.store,
                "denominator-series",
                kind=owner._N7_DERIVATION_SOURCE_SERIES_KIND,
            ),
            occurrence_ref=_marker(
                case.store,
                "denominator-occurrence",
                kind=owner._N7_DERIVATION_OCCURRENCE_KIND,
            ),
            definition_ref=denominator_basis.semantic_definition_ref,
            representation_ref=denominator_basis.representation_ref,
            source_receipt_ref=_marker(
                case.store,
                "denominator-receipt",
                kind=owner._N7_DERIVATION_SOURCE_RECEIPT_KIND,
            ),
            requirement_gap=denominator_gap,
        )
        complete_bundle = bundle.model_copy(
            update={
                "source_nodes": (ratio, complete_denominator),
                "input_closure_status": "inputs_complete",
            }
        )
        complete_ref = owner.persist_n7_derivation_bundle(case.store, complete_bundle)
        complete_reopened = owner.load_n7_derivation_bundle(case.store, complete_ref)
        assert complete_reopened.input_closure_status == "inputs_complete"
        assert complete_reopened.target_satisfaction_status == "unsatisfied"
        assert owner.n7_pending_unique_derivation_source_gaps(complete_reopened) == ()
        with pytest.raises(ValueError):
            owner.N7DerivationBundle.model_validate(
                {**bundle.model_dump(mode="json"), "output_ref": "sha256:" + "f" * 64}
            )
    finally:
        case.close()


def test_or_supplier_permutation_keeps_the_same_selected_bundle(tmp_path: Path) -> None:
    case, obligation_set_ref, obligation_ref, target_basis, context = _selected_target(tmp_path)
    try:
        budget, budget_ref = _profile(case.store)
        ratio_basis = _source_basis(case.store, "ratio")
        denominator_basis = _source_basis(case.store, "denominator")
        ratio = _complete_source(case.store, "ratio-leaf", ratio_basis)
        supplier_a = _marker(case.store, "denominator-supplier-a")
        supplier_b = _marker(case.store, "denominator-supplier-b")
        gap = _target_gap(context, "economic.gdp")
        operator_ref = _registry_ref(case.store)
        bundle = _bundle(
            obligation_set_ref=obligation_set_ref,
            obligation_ref=obligation_ref,
            target_basis=target_basis,
            budget=budget,
            budget_ref=budget_ref,
            sources=(
                ratio,
                _pending_source(
                    "denominator-leaf",
                    denominator_basis,
                    gap,
                    alternatives=(supplier_a, supplier_b),
                ),
            ),
            operator_ref=operator_ref,
            role_inputs=(
                owner.N7DerivationRoleInput(
                    role="ratio", input_node_id=ratio.node_id, source_basis=ratio_basis
                ),
                owner.N7DerivationRoleInput(
                    role="denominator",
                    input_node_id="denominator-leaf",
                    source_basis=denominator_basis,
                ),
            ),
        )
        permuted = bundle.model_copy(
            update={
                "source_nodes": (
                    bundle.source_nodes[0],
                    bundle.source_nodes[1].model_copy(
                        update={
                            "supplier_alternatives": tuple(
                                reversed(bundle.source_nodes[1].supplier_alternatives)
                            )
                        }
                    ),
                )
            }
        )

        first_ref = owner.persist_n7_derivation_bundle(case.store, bundle)
        second_ref = owner.persist_n7_derivation_bundle(case.store, permuted)

        assert owner.artifacts.artifact_ref_identity_key(
            first_ref
        ) == owner.artifacts.artifact_ref_identity_key(second_ref)
        assert (
            owner.load_n7_derivation_bundle(case.store, second_ref).target_satisfaction_status
            == "unsatisfied"
        )
    finally:
        case.close()


def test_shared_pending_source_leaf_is_one_unique_n7_request() -> None:
    def ref(index: int, kind: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=f"sha256:{index:064x}",
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=f"sha256:{index + 1000:064x}",
        )

    shared_basis = owner.N7DerivationBasis(
        semantic_definition_ref=ref(1, owner._N7_DERIVATION_DEFINITION_KIND),
        representation_ref=ref(2, owner._N7_DERIVATION_REPRESENTATION_KIND),
        binding_profile_ref=ref(3, owner._N7_DERIVATION_BINDING_PROFILE_KIND),
    )
    left_basis = owner.N7DerivationBasis(
        semantic_definition_ref=ref(4, owner._N7_DERIVATION_DEFINITION_KIND),
        representation_ref=ref(5, owner._N7_DERIVATION_REPRESENTATION_KIND),
        binding_profile_ref=ref(6, owner._N7_DERIVATION_BINDING_PROFILE_KIND),
    )
    right_basis = owner.N7DerivationBasis(
        semantic_definition_ref=ref(7, owner._N7_DERIVATION_DEFINITION_KIND),
        representation_ref=ref(8, owner._N7_DERIVATION_REPRESENTATION_KIND),
        binding_profile_ref=ref(9, owner._N7_DERIVATION_BINDING_PROFILE_KIND),
    )
    target_basis = owner.N7DerivationBasis(
        semantic_definition_ref=ref(10, owner._N7_DERIVATION_DEFINITION_KIND),
        representation_ref=ref(11, owner._N7_DERIVATION_REPRESENTATION_KIND),
        binding_profile_ref=ref(12, owner._N7_DERIVATION_BINDING_PROFILE_KIND),
    )
    source = owner.N7DerivationSourceNode(
        node_id="one-pending-source",
        source_basis=shared_basis,
        requirement_gap=_source_gap("test.shared_source"),
    )
    operations = (
        owner.N7DerivationOperationNode(
            node_id="left-operation",
            operator_ref=ref(13, owner._N7_DERIVATION_OPERATOR_REGISTRY_KIND),
            family_id="test.ratio_times_denominator",
            method_version="1.0",
            output_basis=left_basis,
            role_inputs=(
                owner.N7DerivationRoleInput(
                    role="source", input_node_id=source.node_id, source_basis=shared_basis
                ),
            ),
        ),
        owner.N7DerivationOperationNode(
            node_id="right-operation",
            operator_ref=ref(14, owner._N7_DERIVATION_OPERATOR_REGISTRY_KIND),
            family_id="test.ratio_times_denominator",
            method_version="1.0",
            output_basis=right_basis,
            role_inputs=(
                owner.N7DerivationRoleInput(
                    role="source", input_node_id=source.node_id, source_basis=shared_basis
                ),
            ),
        ),
        owner.N7DerivationOperationNode(
            node_id="root-operation",
            operator_ref=ref(15, owner._N7_DERIVATION_OPERATOR_REGISTRY_KIND),
            family_id="test.ratio_times_denominator",
            method_version="1.0",
            output_basis=target_basis,
            role_inputs=(
                owner.N7DerivationRoleInput(
                    role="left", input_node_id="left-operation", source_basis=left_basis
                ),
                owner.N7DerivationRoleInput(
                    role="right", input_node_id="right-operation", source_basis=right_basis
                ),
            ),
        ),
    )
    bundle = owner.N7DerivationBundle(
        obligation_set_ref=ref(16, "runtime.quality.model_input_obligation_set"),
        model_input_obligation_ref=ref(17, "runtime.quality.model_input_obligation"),
        target_basis=target_basis,
        dag_budget_profile_ref=ref(18, owner._N7_DERIVATION_BUDGET_KIND),
        dag_budget_profile=owner.N7DerivationDagBudgetProfile(
            profile_id="shared-source-test",
            max_nodes=16,
            max_edges=32,
            max_depth=8,
            max_unique_sources=16,
        ),
        source_nodes=(source,),
        operation_nodes=operations,
        root_node_id="root-operation",
        input_closure_status="partial",
    )

    assert owner.n7_pending_unique_derivation_source_gaps(bundle) == (source.requirement_gap,)


def test_bundle_rejects_cycle_budget_overflow_and_role_basis_substitution() -> None:
    def ref(index: int, kind: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=f"sha256:{index:064x}",
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256=f"sha256:{index + 1000:064x}",
        )

    budget = owner.N7DerivationDagBudgetProfile(
        profile_id="bounded-test",
        max_nodes=16,
        max_edges=32,
        max_depth=8,
        max_unique_sources=16,
    )
    set_ref = ref(1, "runtime.quality.model_input_obligation_set")
    obligation_ref = ref(2, "runtime.quality.model_input_obligation")
    budget_ref = ref(3, owner._N7_DERIVATION_BUDGET_KIND)
    target_basis = owner.N7DerivationBasis(
        semantic_definition_ref=ref(4, owner._N7_DERIVATION_DEFINITION_KIND),
        representation_ref=ref(5, owner._N7_DERIVATION_REPRESENTATION_KIND),
        binding_profile_ref=ref(6, owner._N7_DERIVATION_BINDING_PROFILE_KIND),
    )
    source_basis = owner.N7DerivationBasis(
        semantic_definition_ref=ref(7, owner._N7_DERIVATION_DEFINITION_KIND),
        representation_ref=ref(8, owner._N7_DERIVATION_REPRESENTATION_KIND),
        binding_profile_ref=ref(9, owner._N7_DERIVATION_BINDING_PROFILE_KIND),
    )
    source = _pending_source(
        "leaf",
        source_basis,
        _source_gap("economic.gdp"),
    )
    operator_a = ref(10, owner._N7_DERIVATION_OPERATOR_REGISTRY_KIND)
    operator_b = ref(11, owner._N7_DERIVATION_OPERATOR_REGISTRY_KIND)
    input_edge = owner.N7DerivationRoleInput(
        role="input", input_node_id="leaf", source_basis=source_basis
    )
    base = _bundle(
        obligation_set_ref=set_ref,
        obligation_ref=obligation_ref,
        target_basis=target_basis,
        budget=budget,
        budget_ref=budget_ref,
        sources=(source,),
        operator_ref=operator_a,
        role_inputs=(input_edge,),
    )

    with pytest.raises(ValueError, match="n7_derivation_dag_budget_exceeded"):
        owner.N7DerivationBundle.model_validate(
            {
                **base.model_dump(mode="python"),
                "dag_budget_profile": budget.model_copy(update={"max_nodes": 1}),
            }
        )

    source_with_supplier_alternative = owner.N7DerivationSourceNode(
        node_id="leaf",
        source_basis=source_basis,
        supplier_alternatives=(
            owner.N7DerivationSupplierAlternative(
                supplier_ref=ref(20, "tests.supplier"),
                source_basis=source_basis,
            ),
        ),
        requirement_gap=source.requirement_gap,
    )
    with pytest.raises(ValueError, match="n7_derivation_dag_budget_exceeded"):
        _bundle(
            obligation_set_ref=set_ref,
            obligation_ref=obligation_ref,
            target_basis=target_basis,
            budget=budget.model_copy(update={"max_edges": 1}),
            budget_ref=budget_ref,
            sources=(source_with_supplier_alternative,),
            operator_ref=operator_a,
            role_inputs=(input_edge,),
        )

    cycle_operations = (
        owner.N7DerivationOperationNode(
            node_id="derive-target",
            operator_ref=operator_a,
            family_id="test.ratio_times_denominator",
            method_version="1.0",
            output_basis=target_basis,
            role_inputs=(
                owner.N7DerivationRoleInput(
                    role="cycle", input_node_id="cycle-node", source_basis=target_basis
                ),
                input_edge,
            ),
        ),
        owner.N7DerivationOperationNode(
            node_id="cycle-node",
            operator_ref=operator_b,
            family_id="test.ratio_times_denominator",
            method_version="1.0",
            output_basis=target_basis,
            role_inputs=(
                owner.N7DerivationRoleInput(
                    role="cycle", input_node_id="derive-target", source_basis=target_basis
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="n7_derivation_cycle_detected"):
        _bundle(
            obligation_set_ref=set_ref,
            obligation_ref=obligation_ref,
            target_basis=target_basis,
            budget=budget,
            budget_ref=budget_ref,
            sources=(source,),
            operator_ref=operator_a,
            role_inputs=(input_edge,),
            operation_nodes=cycle_operations,
        )

    inner_operation = owner.N7DerivationOperationNode(
        node_id="inner-operation",
        operator_ref=operator_b,
        family_id="test.ratio_times_denominator",
        method_version="1.0",
        output_basis=source_basis,
        role_inputs=(input_edge,),
    )
    root_operation = owner.N7DerivationOperationNode(
        node_id="derive-target",
        operator_ref=operator_a,
        family_id="test.ratio_times_denominator",
        method_version="1.0",
        output_basis=target_basis,
        role_inputs=(
            owner.N7DerivationRoleInput(
                role="inner", input_node_id="inner-operation", source_basis=source_basis
            ),
        ),
    )
    with pytest.raises(ValueError, match="n7_derivation_dag_budget_exceeded"):
        _bundle(
            obligation_set_ref=set_ref,
            obligation_ref=obligation_ref,
            target_basis=target_basis,
            budget=budget.model_copy(update={"max_depth": 1}),
            budget_ref=budget_ref,
            sources=(source,),
            operator_ref=operator_a,
            role_inputs=(input_edge,),
            operation_nodes=(inner_operation, root_operation),
        )

    wrong_role_edge = owner.N7DerivationRoleInput(
        role="denominator",
        input_node_id="leaf",
        source_basis=target_basis,
    )
    with pytest.raises(ValueError, match="n7_derivation_role_source_basis_mismatch"):
        _bundle(
            obligation_set_ref=set_ref,
            obligation_ref=obligation_ref,
            target_basis=target_basis,
            budget=budget,
            budget_ref=budget_ref,
            sources=(source,),
            operator_ref=operator_a,
            role_inputs=(input_edge, wrong_role_edge),
        )
