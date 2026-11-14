"""Component proof for registered N7 graph construction.

The selected obligation set, compiler and routing report are real maintained
fixtures. Leaf nodes in these tests are explicitly component-only markers;
they do not prove a native supplier, source value, absence, or authority.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_composition_binding import (
    RegisteredDerivationRoleBasis,
    RegisteredDerivedInputProfile,
    RegisteredSemanticBasis,
    persist_registered_derived_input_profile,
)
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from polisyos.core.derivations import (
    ArithmeticExpression,
    AssumptionRule,
    BasisSignature,
    TransformFamily,
    TransformFamilyRegistry,
    TransformInputSpec,
    persist_transform_family_registry,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.ir.kernel.units import MoneyUnit
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality.acquisition_planner import (
    N7DerivationBundle,
    load_n7_derivation_bundle,
    persist_n7_derivation_bundle,
    persist_n7_derivation_dag_budget_profile,
)
from polisyos.runtime.quality.model_input_requirements import SelectedProgramGraphInputBasis
from polisyos.runtime.quality.model_input_routing import (
    plan_selected_model_input_routing,
    read_model_input_routing_report,
)
from polisyos.runtime.quality.n7_registered_derivation_plan import (
    persist_registered_n7_derivation_plan,
)
from tests._helpers.acquisition_production import _resolver
from tests._helpers.registered_derived_method_input import (
    prepare_registered_method_input_preflight,
)
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.core.contracts.test_semantic_derived_binding import (
    _definition,
    _representation,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _authority_entry,
)


def _marker(store, name: str, *, kind: str = "tests.n7_registered_plan_component") -> ArtifactRef:
    return store.put_json(
        {"component_marker": name},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.N7RegisteredPlanComponent", version="1.0"),
        ),
        return_selected_profile=True,
    )


def _registered_profile(
    store,
    target,
    registry_bundle_ref: ArtifactRef,
    *,
    role_populations: Mapping[str, str] | None = None,
) -> tuple[RegisteredDerivedInputProfile, ArtifactRef]:
    money = MoneyUnit(currency="USD", nominal_year=2024, price_base="current")
    populations = {} if role_populations is None else dict(role_populations)
    ratio_definition, _ = _definition(store, "component-registered-ratio")
    denominator_definition, _ = _definition(store, "component-registered-denominator")
    ratio_representation, _ = _representation(
        store,
        ratio_definition,
        population=populations.get("ratio", target.port.scope.population_ref),
        money=money,
        numerator_ref=target.port.semantic_definition_ref,
        denominator_ref=denominator_definition,
    )
    denominator_representation, _ = _representation(
        store,
        denominator_definition,
        population=populations.get("denominator", target.port.scope.population_ref),
        money=money,
    )
    family = TransformFamily(
        family_id="test.ratio_times_denominator",
        method_id="arithmetic.ratio_times_denominator",
        method_version="1.0",
        input_specs=(
            TransformInputSpec(
                role="denominator",
                basis=BasisSignature(quantity_kind="flow", unit="usd"),
                allowed_input_kinds=("candidate_source",),
            ),
            TransformInputSpec(
                role="ratio",
                basis=BasisSignature(quantity_kind="flow", unit="ratio"),
                allowed_input_kinds=("candidate_source",),
            ),
        ),
        output_basis=BasisSignature(quantity_kind="flow", unit="usd"),
        year_domain_role="ratio",
        expression=ArithmeticExpression(
            operator="multiply",
            operands=(
                ArithmeticExpression(operator="current_value", role="denominator"),
                ArithmeticExpression(operator="current_value", role="ratio"),
            ),
        ),
        assumption_rules=(AssumptionRule(name="fixture_context", literal_value="declared"),),
    )
    registry_ref = persist_transform_family_registry(
        store,
        TransformFamilyRegistry(families=(family,)),
        registry_bundle_ref=registry_bundle_ref,
    )
    profile = RegisteredDerivedInputProfile(
        registry_ref=SelectedVariableBindingRef.model_validate(
            registry_ref.model_dump(mode="python")
        ),
        family_id=family.family_id,
        method_version=family.method_version,
        ratio_role="ratio",
        denominator_role="denominator",
        inputs=(
            RegisteredDerivationRoleBasis(
                role="denominator",
                basis=RegisteredSemanticBasis(
                    semantic_definition_ref=denominator_definition,
                    representation_ref=denominator_representation,
                    binding_profile_ref=target.port.binding_profile_ref,
                ),
            ),
            RegisteredDerivationRoleBasis(
                role="ratio",
                basis=RegisteredSemanticBasis(
                    semantic_definition_ref=ratio_definition,
                    representation_ref=ratio_representation,
                    binding_profile_ref=target.port.binding_profile_ref,
                ),
            ),
        ),
        output=RegisteredSemanticBasis(
            semantic_definition_ref=target.port.semantic_definition_ref,
            representation_ref=target.port.representation_ref,
            binding_profile_ref=target.port.binding_profile_ref,
        ),
    )
    return profile, persist_registered_derived_input_profile(store, profile)


def _component_sources(store, profile, target, *, complete: bool = False):
    sources: list[tuple[str, planner.N7DerivationSourceNode]] = []
    for index, row in enumerate(profile.inputs):
        basis = planner.N7DerivationBasis(
            semantic_definition_ref=row.basis.semantic_definition_ref,
            representation_ref=row.basis.representation_ref,
            binding_profile_ref=row.basis.binding_profile_ref,
        )
        node_id = f"component-source-{index}"
        if complete:
            supplier = _marker(store, f"{node_id}-supplier")
            node = planner.N7DerivationSourceNode(
                node_id=node_id,
                source_basis=basis,
                supplier_alternatives=(
                    planner.N7DerivationSupplierAlternative(
                        supplier_ref=supplier,
                        source_basis=basis,
                    ),
                ),
                selected_supplier_ref=supplier,
                source_series_ref=_marker(
                    store,
                    f"{node_id}-series",
                    kind=planner._N7_DERIVATION_SOURCE_SERIES_KIND,
                ),
                occurrence_ref=_marker(
                    store,
                    f"{node_id}-occurrence",
                    kind=planner._N7_DERIVATION_OCCURRENCE_KIND,
                ),
                definition_ref=basis.semantic_definition_ref,
                representation_ref=basis.representation_ref,
                source_receipt_ref=_marker(
                    store,
                    f"{node_id}-receipt",
                    kind=planner._N7_DERIVATION_SOURCE_RECEIPT_KIND,
                ),
            )
        else:
            candidate_binding = {
                "candidate_id": target.context.candidate_id,
                "candidate_content_hash": target.context.candidate_content_hash,
                "design_problem_ref": target.context.design_problem_ref,
            }
            gap = planner.AcquisitionRequirementGap(
                requirement_gap_id=f"component-only:{row.role}",
                requirement_family=planner.RequirementGapFamily.DATA,
                compiled_requirement_ref=f"component-only:{row.role}",
                requirement_schema_version="component_test_only.v1",
                gap_type=planner.AcquisitionGapType.DATA_SNAPSHOT_RELEASE,
                claim_ref=f"component-only:{row.role}",
                authority_level=planner.AuthorityLevel.RESEARCH,
                metadata={
                    "candidate_binding": candidate_binding,
                    "component_proof_only": True,
                    "role": row.role,
                },
            )
            node = planner.N7DerivationSourceNode(
                node_id=node_id,
                source_basis=basis,
                requirement_gap=gap,
            )
        sources.append((row.role, node))
    return tuple(sources)


def prepare_selected_plan_case(
    tmp_path: Path,
    *,
    role_populations: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a selected compiler/report/profile fixture without source claims.

    The caller owns ``result["case"]`` and must close it. Role populations let
    a Catalog declaration test bind genuine role-specific selected semantics.
    """
    case, _metadata = prepare_selected_method_input_case(
        tmp_path / "method-input",
        method_class=PeriodFlowToStock,
    )
    preflight = prepare_registered_method_input_preflight(case)
    selected_set, members = load_model_input_obligation_set(
        case.store, preflight.obligation_set_ref
    )
    assert len(members) == len(selected_set.obligation_refs) == 1
    target_ref = selected_set.obligation_refs[0]
    target = members[0]
    basis = SelectedProgramGraphInputBasis(
        context=preflight.invocation.context,
        program_graph_ref=preflight.invocation.program_graph_ref,
        exec_plan_ref=preflight.invocation.exec_plan_ref,
        registry_bundle_ref=preflight.invocation.registry_bundle_ref,
        input_bindings_ref=preflight.invocation.input_bindings_ref,
        steps=preflight.invocation.steps,
        parameter_override_bundle_ref=preflight.invocation.parameter_override_bundle_ref,
    )
    authority, _entry = _resolver(
        tmp_path / "catalog-authority",
        authority_entry=_authority_entry(
            target.port.semantic_definition_ref,
            target.port.representation_ref,
            suffix="n7-registered-plan-component",
        ),
    )
    routing = plan_selected_model_input_routing(
        case.store,
        obligation_set_ref=preflight.obligation_set_ref,
        selected_basis=basis,
        catalog_authority=authority,
        report_version="2.0",
    )
    alternate_routing = plan_selected_model_input_routing(
        case.store,
        obligation_set_ref=preflight.obligation_set_ref,
        selected_basis=basis,
        catalog_authority=authority,
        report_version="1.0",
    )
    profile, profile_ref = _registered_profile(
        case.store,
        target,
        preflight.invocation.registry_bundle_ref,
        role_populations=role_populations,
    )
    budget = planner.N7DerivationDagBudgetProfile(
        profile_id="component-registered-plan-budget",
        max_nodes=16,
        max_edges=32,
        max_depth=8,
        max_unique_sources=16,
    )
    budget_ref = persist_n7_derivation_dag_budget_profile(case.store, budget)
    return {
        "case": case,
        "obligation_set_ref": preflight.obligation_set_ref,
        "target_ref": target_ref,
        "target": target,
        "routing_ref": routing.report_ref,
        "alternate_routing_ref": alternate_routing.report_ref,
        "profile": profile,
        "profile_ref": profile_ref,
        "budget": budget,
        "budget_ref": budget_ref,
    }


@pytest.fixture
def selected_plan_case(tmp_path: Path):
    case = prepare_selected_plan_case(tmp_path)
    try:
        yield case
    finally:
        case["case"].close()


def _persist(case: dict[str, Any], *, role_sources=None, **overrides) -> ArtifactRef:
    values = {
        "routing_report_ref": case["routing_ref"],
        "obligation_set_ref": case["obligation_set_ref"],
        "target_obligation_ref": case["target_ref"],
        "registered_profile_ref": case["profile_ref"],
        "dag_budget_profile_ref": case["budget_ref"],
        "role_sources": (
            _component_sources(case["case"].store, case["profile"], case["target"])
            if role_sources is None
            else role_sources
        ),
    }
    values.update(overrides)
    return persist_registered_n7_derivation_plan(case["case"].store, **values)


def test_registered_plan_joins_actual_target_and_keeps_bundle_candidate_only(
    selected_plan_case,
) -> None:
    """Actual set/compiler/report joins; structural leaves prove graph wiring only."""
    case = selected_plan_case
    ref = _persist(
        case,
        role_sources=tuple(
            reversed(_component_sources(case["case"].store, case["profile"], case["target"]))
        ),
    )
    bundle = load_n7_derivation_bundle(case["case"].store, ref)
    assert bundle.schema_version == "policyos.runtime.n7_derivation_bundle.v2"
    assert type(bundle.registered_profile_ref) is ArtifactRef
    assert type(bundle.model_input_routing_report_ref) is ArtifactRef
    assert artifact_ref_identity_key(bundle.registered_profile_ref) == artifact_ref_identity_key(
        case["profile_ref"]
    )
    assert artifact_ref_identity_key(
        bundle.model_input_routing_report_ref
    ) == artifact_ref_identity_key(case["routing_ref"])
    manifest = case["case"].store.get_manifest(ref)
    assert (
        input_ref_from_artifact_ref(
            bundle.registered_profile_ref, role="selected_registered_semantic_profile"
        )
        in manifest.inputs
    )
    assert (
        input_ref_from_artifact_ref(
            bundle.model_input_routing_report_ref,
            role="selected_model_input_routing_report",
        )
        in manifest.inputs
    )
    for parent_field in ("registered_profile_ref", "model_input_routing_report_ref"):
        payload = bundle.model_dump(mode="python", exclude={parent_field})
        with pytest.raises(ValueError, match="n7_derivation_registered_profile_parent_unselected"):
            N7DerivationBundle.model_validate(payload)
    assert tuple(edge.role for edge in bundle.operation_nodes[0].role_inputs) == tuple(
        row.role for row in case["profile"].inputs
    )
    assert bundle.operation_nodes[0].node_id == "registered-output"
    assert bundle.input_closure_status == "partial"
    assert bundle.target_satisfaction_status == "unsatisfied"
    assert bundle.authority_purpose == "candidate_acquisition_routing_only"
    assert read_model_input_routing_report(case["case"].store, case["routing_ref"])

    complete_ref = _persist(
        case,
        role_sources=_component_sources(
            case["case"].store, case["profile"], case["target"], complete=True
        ),
    )
    complete = load_n7_derivation_bundle(case["case"].store, complete_ref)
    assert complete.input_closure_status == "inputs_complete"
    assert complete.target_satisfaction_status == "unsatisfied"

    # Projecting away only v2's selected parents recovers the exact v1 default
    # and writer shape for existing bundle consumers.
    legacy = N7DerivationBundle.model_validate(
        bundle.model_dump(
            mode="python",
            exclude={
                "schema_version",
                "registered_profile_ref",
                "model_input_routing_report_ref",
            },
        )
    )
    assert legacy.schema_version == "policyos.runtime.n7_derivation_bundle.v1"
    assert legacy.registered_profile_ref is None
    assert legacy.model_input_routing_report_ref is None
    legacy_ref = persist_n7_derivation_bundle(case["case"].store, legacy)
    legacy_wire = json.loads(case["case"].store.get_bytes(legacy_ref))
    assert legacy_wire["schema_version"] == "policyos.runtime.n7_derivation_bundle.v1"
    assert "registered_profile_ref" not in legacy_wire
    assert "model_input_routing_report_ref" not in legacy_wire
    legacy_manifest = case["case"].store.get_manifest(legacy_ref)
    assert legacy_manifest.artifact_schema.version == "1.0"
    assert (
        input_ref_from_artifact_ref(
            case["profile_ref"], role="selected_registered_semantic_profile"
        )
        not in legacy_manifest.inputs
    )
    assert (
        input_ref_from_artifact_ref(case["routing_ref"], role="selected_model_input_routing_report")
        not in legacy_manifest.inputs
    )


def test_registered_plan_refuses_wrong_subject_roles_basis_family_and_budget(
    selected_plan_case,
) -> None:
    """Reject malformed joins and nonregistered graph edges before persistence."""
    case = selected_plan_case
    store = case["case"].store
    sources = _component_sources(store, case["profile"], case["target"])
    with pytest.raises(ValueError, match="n7_pre_numerical_target_not_in_full_obligation_set"):
        _persist(
            case,
            target_obligation_ref=_marker(
                store, "wrong-target", kind="runtime.quality.model_input_obligation"
            ),
        )
    with pytest.raises(ValueError, match="model_input_routing_report_ref_unselected"):
        _persist(case, routing_report_ref=case["profile_ref"])

    with pytest.raises(ValueError, match="n7_registered_derivation_required_roles_mismatch"):
        _persist(case, role_sources=sources[:-1])
    with pytest.raises(ValueError, match="n7_registered_derivation_role_duplicate"):
        _persist(case, role_sources=(*sources, sources[0]))
    with pytest.raises(ValueError, match="n7_registered_derivation_required_roles_mismatch"):
        _persist(case, role_sources=(*sources, ("extra-role", sources[0][1])))

    root_collision = (
        (sources[0][0], sources[0][1].model_copy(update={"node_id": "registered-output"})),
        *sources[1:],
    )
    with pytest.raises(ValueError, match="n7_registered_derivation_source_root_collision"):
        _persist(case, role_sources=root_collision)

    wrong_source_basis = planner.N7DerivationBasis(
        semantic_definition_ref=case["target"].port.semantic_definition_ref,
        representation_ref=sources[0][1].source_basis.representation_ref,
        binding_profile_ref=sources[0][1].source_basis.binding_profile_ref,
    )
    wrong_source = (
        sources[0][0],
        sources[0][1].model_copy(update={"source_basis": wrong_source_basis}),
    )
    with pytest.raises(ValueError, match="n7_registered_derivation_source_basis_mismatch"):
        _persist(case, role_sources=(wrong_source, *sources[1:]))

    wrong_output = case["profile"].model_copy(update={"output": case["profile"].inputs[0].basis})
    wrong_output_ref = persist_registered_derived_input_profile(store, wrong_output)
    with pytest.raises(ValueError, match="n7_registered_derivation_output_target_basis_mismatch"):
        _persist(case, registered_profile_ref=wrong_output_ref)

    foreign_family = case["profile"].model_copy(update={"family_id": "foreign.family"})
    foreign_profile_ref = persist_registered_derived_input_profile(store, foreign_family)
    with pytest.raises(ValueError, match="n7_registered_derivation_family_not_unique"):
        _persist(case, registered_profile_ref=foreign_profile_ref)

    capped_budget = planner.N7DerivationDagBudgetProfile(
        profile_id="component-registered-plan-budget-cap",
        max_nodes=2,
        max_edges=32,
        max_depth=8,
        max_unique_sources=16,
    )
    capped_budget_ref = persist_n7_derivation_dag_budget_profile(store, capped_budget)
    with pytest.raises(ValueError, match="n7_derivation_dag_budget_exceeded"):
        _persist(case, dag_budget_profile_ref=capped_budget_ref)

    # Selected-profile/report hash grafts use real, independently selected
    # manifest hashes rather than hand-authored digest literals.
    # A payload-only method-version change retains the same selected profile.
    # Graft an independently persisted profile with genuinely different parents.
    alternate_profile_ref = wrong_output_ref
    assert (
        alternate_profile_ref.manifest_profile_sha256 != case["profile_ref"].manifest_profile_sha256
    )
    grafted_profile_ref = ArtifactRef.model_validate(
        case["profile_ref"].model_dump(mode="python")
        | {"manifest_profile_sha256": alternate_profile_ref.manifest_profile_sha256}
    )
    assert artifact_ref_identity_key(grafted_profile_ref) != artifact_ref_identity_key(
        case["profile_ref"]
    )
    with pytest.raises((OSError, ValueError)):
        _persist(case, registered_profile_ref=grafted_profile_ref)
    assert (
        case["routing_ref"].manifest_profile_sha256
        != case["alternate_routing_ref"].manifest_profile_sha256
    )
    grafted_routing_ref = ArtifactRef.model_validate(
        case["routing_ref"].model_dump(mode="python")
        | {"manifest_profile_sha256": case["alternate_routing_ref"].manifest_profile_sha256}
    )
    assert artifact_ref_identity_key(grafted_routing_ref) != artifact_ref_identity_key(
        case["routing_ref"]
    )
    with pytest.raises((OSError, ValueError)):
        _persist(case, routing_report_ref=grafted_routing_ref)


@pytest.mark.parametrize("parent", ["registered_profile", "routing_report"])
def test_registered_plan_reopens_and_rejects_removed_selected_parent(
    selected_plan_case, parent: str
) -> None:
    """The selected Core profile and routing report remain live parents."""
    case = selected_plan_case
    store = case["case"].store
    ref = _persist(case)
    parent_ref = case["profile_ref"] if parent == "registered_profile" else case["routing_ref"]
    blob_path, _manifest_path = store._paths(parent_ref.artifact_id)
    blob_path.unlink()
    with pytest.raises((OSError, ValueError)):
        load_n7_derivation_bundle(store, ref)


def test_registered_plan_reopens_and_rejects_tampered_selected_profile(
    selected_plan_case,
) -> None:
    """A selected profile's content hash is replayed before a bundle is written."""
    case = selected_plan_case
    store = case["case"].store
    tampered_profile = case["profile"].model_copy(update={"family_id": "component.tampered"})
    tampered_ref = persist_registered_derived_input_profile(store, tampered_profile)
    tampered_blob, _tampered_manifest = store._paths(tampered_ref.artifact_id)
    tampered_blob.write_bytes(b"tampered selected Core profile")
    with pytest.raises(ValueError):
        _persist(case, registered_profile_ref=tampered_ref)
