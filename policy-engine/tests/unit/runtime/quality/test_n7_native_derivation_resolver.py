"""Component proof for pre-numerical N7 role selection.

The selected model set, compiler, v2 routing report, registered profile, and
Catalog supplier declarations are real CAS artifacts. Generic N5 expectation
refs in this file are labelled component markers only; they do not establish
Generic admission, numerical execution, source values, or source currentness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.semantic_composition_binding import (
    persist_registered_derived_input_profile,
)
from polisyos.core.contracts.variable_binding import (
    load_variable_representation,
)
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionSourceMeasureScope,
    CanonicalAcquisitionAuthority,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.acquisition_planner import (
    AuthorityLevel,
    N7DerivationDagBudgetProfile,
    load_n7_derivation_bundle,
    persist_n7_derivation_dag_budget_profile,
)
from polisyos.runtime.quality.acquisition_route_loop import NativeDerivationLeafProviderSelection
from polisyos.runtime.quality.acquisition_world_growth import (
    NativeDerivationPlanningRoleSupplier,
    NativeDerivationPlanningSelection,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericN5ExecutionJoinExpectation,
)
from polisyos.runtime.quality.n7_native_derivation_resolver import (
    resolve_configured_n7_derivation_plan,
    validate_registered_derivation_role_input_gap,
)
from tests._helpers.acquisition_production import (
    _baseline,
    _sha,
    _write_l5,
    _write_provision,
)
from tests._helpers.registered_derived_method_input import prepare_registered_method_input_preflight
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _authority_entry,
)
from tests.unit.runtime.quality.test_n7_registered_derivation_plan import (
    prepare_selected_plan_case,
)

_TENANT_ID = "tenant-component-fixture"
_CELL_ID = "cell-component-fixture"
_PROFILE_SELECTION_REF = "sha256:" + "c" * 64
_ROLE_POPULATIONS = {
    "denominator": "population:registered-denominator",
    "ratio": "population:registered-ratio",
}


def _marker(store: FileSystemCAS, name: str, *, kind: str) -> ArtifactRef:
    """Persist a selected marker used only for the excluded Generic-owner join."""
    return store.put_json(
        {"component_marker": name, "owner_admission": "out_of_scope"},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.tests.N7ResolverComponentMarker", version="1.0"),
        ),
        return_selected_profile=True,
    )


@pytest.fixture
def native_resolver_case(tmp_path: Path):
    """Reuse the actual compiler/report/profile fixture and close its CAS owner."""
    case = prepare_selected_plan_case(tmp_path, role_populations=_ROLE_POPULATIONS)
    try:
        yield case
    finally:
        case["case"].close()


def _supplier_snapshot(
    case: dict[str, Any],
    tmp_path: Path,
    *,
    requested_role: str,
    source_role: str,
    suffix: str,
    declared_population: str | None = None,
    target_variable: str | None = None,
    canonical_unit: str | None = None,
) -> dict[str, Any]:
    """Persist and reopen one real owner declaration for an exact profile basis."""
    store = case["case"].store
    profile_input = next(row for row in case["profile"].inputs if row.role == source_role)
    entry = _authority_entry(
        profile_input.basis.semantic_definition_ref,
        profile_input.basis.representation_ref,
        suffix=suffix,
    )
    values = entry.model_dump(mode="python", exclude={"entry_id"})
    source_scope = entry.source_measure_scope
    assert source_scope is not None
    representation = load_variable_representation(store, profile_input.basis.representation_ref)
    target_scope = case["target"].port.scope
    population = (
        representation.population_ref if declared_population is None else declared_population
    )
    source_geography_id = entry.country_codes[0]
    scope_values = {
        **source_scope.model_dump(mode="python"),
        "population": population,
        "jurisdiction_ref": target_scope.jurisdiction_ref,
        "geography_ref": target_scope.geography_ref,
        "source_geography_id": source_geography_id,
        "time_period_basis": target_scope.period_basis,
    }
    if representation.measure_form in {"ratio", "rate"} or (
        representation.denominator_ref is not None
    ):
        assert representation.denominator_ref is not None
        scope_values.update(
            quantity_kind="share_of_denominator",
            denominator=str(representation.denominator_ref.artifact_id),
        )
    values["source_measure_scope"] = AcquisitionSourceMeasureScope.model_validate(scope_values)
    raw_unit = "percent_gdp" if representation.unit_id == "ratio" else representation.unit_id
    declared_unit = representation.unit_id if canonical_unit is None else canonical_unit
    if raw_unit == declared_unit:
        unit_transform = "identity"
        unit_transform_ref = "fabric://units/identity/v1"
    elif raw_unit == "percent_gdp" and declared_unit == "ratio":
        unit_transform = "fixed_multiplicative"
        unit_transform_ref = "fabric://units/fixed-multiplicative/v1"
    else:
        unit_transform = "test_candidate_unit_mismatch"
        unit_transform_ref = "fabric://units/test-candidate-unit-mismatch/v1"
    values.update(
        raw_unit=raw_unit,
        canonical_unit=declared_unit,
        unit_transform=unit_transform,
        unit_transform_ref=unit_transform_ref,
    )
    if target_variable is not None:
        values["target_variable"] = target_variable
    entry = build_authority_entry(**values)
    repo_root = tmp_path / suffix
    baseline = _baseline(repo_root)
    l5_path = _write_l5(repo_root)
    if raw_unit == "usd":
        con = duckdb.connect(str(baseline))
        try:
            con.execute(
                "UPDATE ds_datasets SET title = ?, description = ? WHERE id = ?",
                [
                    "Synthetic test source in current US dollars",
                    "Test-owned declaration for a scalar USD role.",
                    entry.source_catalog_dataset_id,
                ],
            )
        finally:
            con.close()
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5_path),
        entries=(entry,),
    )
    registry_path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    _write_provision(
        repo_root,
        baseline=baseline,
        l5_path=l5_path,
        baseline_owner_ref="repo://catalog/catalog.duckdb",
    )
    authority = CanonicalAcquisitionAuthority.from_provision(
        repo_root=repo_root,
        baseline_path=baseline,
        l5_measurement_registry_path=l5_path,
    )
    declaration_ref = catalog_read_api.persist_acquisition_supplier_declaration(
        store,
        authority,
        entry_id=entry.entry_id,
    )
    declaration = catalog_read_api.load_acquisition_supplier_declaration(store, declaration_ref)
    provider = NativeDerivationLeafProviderSelection(
        source_node_id=f"component-source-{requested_role}",
        supplier_ref=declaration_ref,
        authority_entry_id=entry.entry_id,
        connector_id=declaration.connector_id,
    )
    return {
        "role": requested_role,
        "entry": entry,
        "ref": declaration_ref,
        "declaration": declaration,
        "provider": provider,
        "selection_row": NativeDerivationPlanningRoleSupplier(
            role=requested_role,
            provider=provider,
            source_declaration_ref=declaration_ref,
        ),
    }


def _snapshots(case: dict[str, Any], tmp_path: Path) -> dict[str, dict[str, Any]]:
    """Persist exact role-basis declarations with role populations from Core."""
    return {
        row.role: _supplier_snapshot(
            case,
            tmp_path / row.role,
            requested_role=row.role,
            source_role=row.role,
            suffix=f"n7-native-{row.role}",
        )
        for row in case["profile"].inputs
    }


def _selection(
    case: dict[str, Any],
    snapshots: tuple[dict[str, Any], ...],
    *,
    profile_ref: ArtifactRef | None = None,
    budget_ref: ArtifactRef | None = None,
) -> NativeDerivationPlanningSelection:
    """Select real declaration snapshots for one deployment profile."""
    return NativeDerivationPlanningSelection(
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
        profile_selection_ref=_PROFILE_SELECTION_REF,
        registered_profile_ref=case["profile_ref"] if profile_ref is None else profile_ref,
        dag_budget_profile_ref=case["budget_ref"] if budget_ref is None else budget_ref,
        binding_id="component-registered-n7",
        role_suppliers=tuple(row["selection_row"] for row in snapshots),
    )


def _expectation(case: dict[str, Any]) -> GenericN5ExecutionJoinExpectation:
    """Build a component-only Generic expectation around the actual target context."""
    store = case["case"].store
    context = case["target"].context
    return GenericN5ExecutionJoinExpectation(
        input_ref=_marker(store, "generic-input", kind="tests.generic_n5_input_component"),
        result_ref=None,
        status="simulation_blocked",
        model_input_obligation_set_ref=case["obligation_set_ref"],
        n4_source_ref=_marker(store, "generic-n4", kind="tests.generic_n4_source_component"),
        context_job_ref=_marker(store, "generic-context", kind="tests.generic_context_component"),
        profile_ref=_marker(store, "generic-profile", kind="tests.generic_profile_component"),
        child_family_ref=None,
        child_set_ref=None,
        profile_selection_ref=_PROFILE_SELECTION_REF,
        design_problem_ref=context.design_problem_ref,
        outcome_variable="component-only-outcome",
        cycle_index=1,
        candidate_id=context.candidate_id,
        candidate_atom_hash=context.candidate_content_hash,
        world_model_record_content_hash="sha256:" + "f" * 64,
        job_id="component-only-job",
        run_id=context.run_id,
        source_run_id="component-only-source-run",
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
    )


def _resolve(
    case: dict[str, Any],
    selection: NativeDerivationPlanningSelection,
    *,
    expected: GenericN5ExecutionJoinExpectation | None = None,
    routing_ref: ArtifactRef | None = None,
) -> ArtifactRef | None:
    """Invoke the real resolver with only the Generic admission seam component-marked."""
    selected_expectation = _expectation(case) if expected is None else expected

    def selector(*, tenant_id: str, cell_id: str, profile_selection_ref: str):
        if (tenant_id, cell_id, profile_selection_ref) != (
            selected_expectation.tenant_id,
            selected_expectation.cell_id,
            selected_expectation.profile_selection_ref,
        ):
            return ()
        return (selection,)

    return resolve_configured_n7_derivation_plan(
        case["case"].store,
        selector=selector,
        expected=selected_expectation,
        routing_report_ref=case["routing_ref"] if routing_ref is None else routing_ref,
        authority_level=AuthorityLevel.RESEARCH,
    )


def _role_gap(case: dict[str, Any], bundle_ref: ArtifactRef, role: str):
    bundle = load_n7_derivation_bundle(case["case"].store, bundle_ref)
    operation = bundle.operation_nodes[0]
    source_by_id = {row.node_id: row for row in bundle.source_nodes}
    edge = next(row for row in operation.role_inputs if row.role == role)
    gap = source_by_id[edge.input_node_id].requirement_gap
    assert gap is not None
    return bundle, source_by_id[edge.input_node_id], gap


def test_resolver_persists_selected_catalog_roles_as_candidate_only_plan(
    native_resolver_case: dict[str, Any], tmp_path: Path
) -> None:
    """Actual role declarations join the exact v2 target without numeric admission."""
    case = native_resolver_case
    store = case["case"].store
    snapshots = _snapshots(case, tmp_path)
    selection = _selection(case, tuple(snapshots.values()))

    bundle_ref = _resolve(case, selection)

    assert type(bundle_ref) is ArtifactRef
    bundle, _source, gap = _role_gap(case, bundle_ref, "denominator")
    assert bundle.schema_version == "policyos.runtime.n7_derivation_bundle.v2"
    assert artifact_ref_identity_key(bundle.obligation_set_ref) == artifact_ref_identity_key(
        case["obligation_set_ref"]
    )
    assert artifact_ref_identity_key(
        bundle.model_input_obligation_ref
    ) == artifact_ref_identity_key(case["target_ref"])
    assert artifact_ref_identity_key(bundle.registered_profile_ref) == artifact_ref_identity_key(
        case["profile_ref"]
    )
    assert artifact_ref_identity_key(
        bundle.model_input_routing_report_ref
    ) == artifact_ref_identity_key(case["routing_ref"])
    assert bundle.input_closure_status == "partial"
    assert bundle.target_satisfaction_status == "unsatisfied"
    assert bundle.authority_purpose == "candidate_acquisition_routing_only"

    target_population = case["target"].port.scope.population_ref
    for role, snapshot in snapshots.items():
        actual_bundle, source, actual_gap = _role_gap(case, bundle_ref, role)
        declaration = catalog_read_api.load_acquisition_supplier_declaration(store, snapshot["ref"])
        representation = load_variable_representation(
            store,
            next(
                row for row in case["profile"].inputs if row.role == role
            ).basis.representation_ref,
        )
        assert actual_bundle == bundle
        assert source.requirement_gap == actual_gap
        assert len(source.supplier_alternatives) == 1
        assert source.selected_supplier_ref is None
        assert source.source_series_ref is None
        assert source.occurrence_ref is None
        assert source.source_receipt_ref is None
        assert artifact_ref_identity_key(source.supplier_alternatives[0].supplier_ref) == (
            artifact_ref_identity_key(snapshot["ref"])
        )
        assert actual_gap.metadata["role"] == role
        assert actual_gap.metadata["variable_id"] == declaration.entry.target_variable
        assert actual_gap.metadata["requested_role_scope"]["population_ref"] == (
            representation.population_ref
        )
        assert representation.population_ref != target_population
        assert declaration.semantic_refs_status == "declared"
        assert declaration.source_scope_status == "declared"
        assert declaration.semantic_authority == "not_established"
        assert declaration.acquisition_permission == "not_established"
        assert declaration.source_currentness == "not_established"
        assert actual_gap.metadata["historical_catalog_absence"] == "not_established"
        assert actual_gap.metadata["source_currentness"] == "not_established"
        assert actual_gap.metadata["permission_status"] == "not_established"
        assert actual_gap.metadata["measurement_admission"] == "not_established"
        assert declaration.entry.source_measure_scope.quantity_kind == (
            "share_of_denominator" if role == "ratio" else "unconstrained"
        )

        manifest = store.get_manifest(bundle_ref)
        source_id = source.node_id
        assert (
            input_ref_from_artifact_ref(snapshot["ref"], role=f"source.{source_id}.supplier.0")
            in manifest.inputs
        )

    assert gap.metadata["source"] == "registered_derivation_role_input"
    assert gap.metadata["satisfaction_status"] == "unsatisfied"
    returned_variable = validate_registered_derivation_role_input_gap(
        store,
        gap,
        supplier_ref=snapshots["denominator"]["ref"],
        authority_entry_id=snapshots["denominator"]["entry"].entry_id,
        connector_id=snapshots["denominator"]["declaration"].connector_id,
        expected_registered_profile_ref=case["profile_ref"],
        expected_obligation_set_ref=case["obligation_set_ref"],
        expected_target_obligation_ref=case["target_ref"],
        expected_routing_report_ref=case["routing_ref"],
    )
    assert returned_variable == snapshots["denominator"]["entry"].target_variable

    alternate_variable = _supplier_snapshot(
        case,
        tmp_path / "alternate-variable",
        requested_role="denominator",
        source_role="denominator",
        suffix="n7-native-alternate-variable",
        target_variable="owner-declared-alternate-variable",
    )
    assert alternate_variable["entry"].source_semantic_definition_ref == (
        snapshots["denominator"]["entry"].source_semantic_definition_ref
    )
    assert alternate_variable["entry"].source_representation_ref == (
        snapshots["denominator"]["entry"].source_representation_ref
    )
    assert alternate_variable["entry"].target_variable != (
        snapshots["denominator"]["entry"].target_variable
    )
    with pytest.raises(ValueError, match="n7_registered_role_selected_supplier_refused"):
        validate_registered_derivation_role_input_gap(
            store,
            gap,
            supplier_ref=alternate_variable["ref"],
            authority_entry_id=alternate_variable["entry"].entry_id,
            connector_id=alternate_variable["declaration"].connector_id,
            expected_registered_profile_ref=case["profile_ref"],
            expected_obligation_set_ref=case["obligation_set_ref"],
            expected_target_obligation_ref=case["target_ref"],
            expected_routing_report_ref=case["routing_ref"],
        )

    foreign_basis = _supplier_snapshot(
        case,
        tmp_path / "foreign-basis",
        requested_role="denominator",
        source_role="ratio",
        suffix="n7-native-same-variable-foreign-basis",
        declared_population=_ROLE_POPULATIONS["denominator"],
    )
    assert (
        foreign_basis["entry"].target_variable == snapshots["denominator"]["entry"].target_variable
    )
    assert foreign_basis["entry"].source_semantic_definition_ref != (
        snapshots["denominator"]["entry"].source_semantic_definition_ref
    )
    with pytest.raises(ValueError, match="n7_registered_role_selected_supplier_refused"):
        validate_registered_derivation_role_input_gap(
            store,
            gap,
            supplier_ref=foreign_basis["ref"],
            authority_entry_id=foreign_basis["entry"].entry_id,
            connector_id=foreign_basis["declaration"].connector_id,
            expected_registered_profile_ref=case["profile_ref"],
            expected_obligation_set_ref=case["obligation_set_ref"],
            expected_target_obligation_ref=case["target_ref"],
            expected_routing_report_ref=case["routing_ref"],
        )

    for kwargs in (
        {"authority_entry_id": "acquisition-authority:sha256:" + "0" * 64},
        {"connector_id": "foreign.connector"},
    ):
        with pytest.raises(ValueError, match="n7_registered_role_selected_supplier_refused"):
            validate_registered_derivation_role_input_gap(
                store,
                gap,
                supplier_ref=snapshots["denominator"]["ref"],
                authority_entry_id=kwargs.get(
                    "authority_entry_id", snapshots["denominator"]["entry"].entry_id
                ),
                connector_id=kwargs.get(
                    "connector_id", snapshots["denominator"]["declaration"].connector_id
                ),
                expected_registered_profile_ref=case["profile_ref"],
                expected_obligation_set_ref=case["obligation_set_ref"],
                expected_target_obligation_ref=case["target_ref"],
                expected_routing_report_ref=case["routing_ref"],
            )

    with pytest.raises(ValueError, match="n7_registered_role_gap_selected_parent_mismatch"):
        validate_registered_derivation_role_input_gap(
            store,
            gap,
            supplier_ref=snapshots["denominator"]["ref"],
            authority_entry_id=snapshots["denominator"]["entry"].entry_id,
            connector_id=snapshots["denominator"]["declaration"].connector_id,
            expected_registered_profile_ref=case["profile_ref"],
            expected_obligation_set_ref=case["target_ref"],
            expected_target_obligation_ref=case["target_ref"],
            expected_routing_report_ref=case["routing_ref"],
        )


def test_resolver_refuses_missing_or_mismatched_configuration(
    native_resolver_case: dict[str, Any], tmp_path: Path
) -> None:
    """Missing config, bad scope, profile, candidate, role, and cap stay pending."""
    case = native_resolver_case
    store = case["case"].store
    snapshots = _snapshots(case, tmp_path)
    rows = tuple(snapshots.values())
    selection = _selection(case, rows)
    expected = _expectation(case)

    assert (
        resolve_configured_n7_derivation_plan(
            store,
            selector=lambda **_scope: (),
            expected=expected,
            routing_report_ref=case["routing_ref"],
            authority_level=AuthorityLevel.RESEARCH,
        )
        is None
    )

    unregistered_profile = case["profile"].model_copy(update={"family_id": "foreign.family"})
    unregistered_profile_ref = persist_registered_derived_input_profile(store, unregistered_profile)
    assert (
        _resolve(
            case,
            _selection(case, rows, profile_ref=unregistered_profile_ref),
        )
        is None
    )

    no_match_profile = case["profile"].model_copy(
        update={"output": case["profile"].inputs[0].basis}
    )
    no_match_profile_ref = persist_registered_derived_input_profile(store, no_match_profile)
    assert (
        _resolve(
            case,
            _selection(case, rows, profile_ref=no_match_profile_ref),
        )
        is None
    )

    missing_role_selection = selection.model_copy(
        update={"role_suppliers": selection.role_suppliers[:-1]}
    )
    assert _resolve(case, missing_role_selection) is None
    foreign_role_row = selection.role_suppliers[0].model_copy(update={"role": "foreign-role"})
    foreign_role_selection = selection.model_copy(
        update={
            "role_suppliers": (
                foreign_role_row,
                *selection.role_suppliers[1:],
            )
        }
    )
    assert _resolve(case, foreign_role_selection) is None

    wrong_scope_snapshot = _supplier_snapshot(
        case,
        tmp_path / "scope-mismatch",
        requested_role="denominator",
        source_role="denominator",
        suffix="n7-native-wrong-population",
        declared_population="population:outside-selected-role",
    )
    scope_mismatch_rows = tuple(
        wrong_scope_snapshot if row["role"] == "denominator" else row for row in rows
    )
    assert _resolve(case, _selection(case, scope_mismatch_rows)) is None

    wrong_unit_snapshot = _supplier_snapshot(
        case,
        tmp_path / "unit-mismatch",
        requested_role="denominator",
        source_role="denominator",
        suffix="n7-native-wrong-canonical-unit",
        canonical_unit="fixture-wrong-canonical-unit",
    )
    wrong_unit_scope = case["target"].port.scope.model_copy(
        update={"population_ref": _ROLE_POPULATIONS["denominator"]}
    )
    assert (
        catalog_read_api.acquisition_supplier_declaration_scope_refusal(
            store,
            wrong_unit_snapshot["ref"],
            scope=wrong_unit_scope,
        )
        == "source_descriptor_definition_or_unit_mismatch"
    )
    wrong_unit_rows = tuple(
        wrong_unit_snapshot if row["role"] == "denominator" else row for row in rows
    )
    assert _resolve(case, _selection(case, wrong_unit_rows)) is None

    same_variable_foreign_basis = _supplier_snapshot(
        case,
        tmp_path / "same-variable-foreign-basis",
        requested_role="denominator",
        source_role="ratio",
        suffix="n7-native-same-variable-wrong-role-basis",
        declared_population=_ROLE_POPULATIONS["denominator"],
    )
    assert same_variable_foreign_basis["entry"].target_variable == (
        snapshots["denominator"]["entry"].target_variable
    )
    assert same_variable_foreign_basis["entry"].source_semantic_definition_ref != (
        snapshots["denominator"]["entry"].source_semantic_definition_ref
    )
    foreign_basis_rows = tuple(
        same_variable_foreign_basis if row["role"] == "denominator" else row for row in rows
    )
    assert _resolve(case, _selection(case, foreign_basis_rows)) is None

    capped_budget_ref = persist_n7_derivation_dag_budget_profile(
        store,
        N7DerivationDagBudgetProfile(
            profile_id="component-registered-plan-budget-cap",
            max_nodes=2,
            max_edges=32,
            max_depth=8,
            max_unique_sources=16,
        ),
    )
    assert _resolve(case, _selection(case, rows, budget_ref=capped_budget_ref)) is None

    foreign_candidate = expected.model_copy(update={"candidate_id": "foreign-candidate"})
    with pytest.raises(ValueError, match="n7_derivation_planning_compiler_context_mismatch"):
        _resolve(case, selection, expected=foreign_candidate)

    foreign_case, _metadata = prepare_selected_method_input_case(
        tmp_path / "foreign-fullset",
        method_class=PeriodFlowToStock,
        income_values=(7,),
        store=store,
    )
    try:
        foreign_preflight = prepare_registered_method_input_preflight(foreign_case)
        foreign_expected = expected.model_copy(
            update={"model_input_obligation_set_ref": foreign_preflight.obligation_set_ref}
        )
        with pytest.raises(
            ValueError, match="n7_pre_numerical_model_input_report_subject_mismatch"
        ):
            _resolve(case, selection, expected=foreign_expected)
    finally:
        foreign_case.close()


def test_resolver_reopens_selected_parents_and_restores_after_source_removal(
    native_resolver_case: dict[str, Any], tmp_path: Path
) -> None:
    """A removed declaration leaves the plan pending; restored refs replay exactly."""
    case = native_resolver_case
    store = case["case"].store
    snapshots = _snapshots(case, tmp_path)
    selection = _selection(case, tuple(snapshots.values()))
    bundle_ref = _resolve(case, selection)
    assert type(bundle_ref) is ArtifactRef
    original = load_n7_derivation_bundle(store, bundle_ref)

    selected_snapshot = snapshots["denominator"]
    source_path, _manifest_path = store._paths(selected_snapshot["ref"].artifact_id)
    selected_bytes = source_path.read_bytes()
    source_path.unlink()
    assert _resolve(case, selection) is None
    with pytest.raises((OSError, ValueError)):
        load_n7_derivation_bundle(store, bundle_ref)
    source_path.write_bytes(selected_bytes)
    assert (
        catalog_read_api.load_acquisition_supplier_declaration(
            FileSystemCAS(store.root), selected_snapshot["ref"]
        )
        == selected_snapshot["declaration"]
    )

    restored_ref = _resolve(case, selection)
    assert type(restored_ref) is ArtifactRef
    restored = load_n7_derivation_bundle(FileSystemCAS(store.root), restored_ref)
    assert restored == original

    # Parent/profile grafts must change the selected profile, not just payload.
    alternate_profile = case["profile"].model_copy(
        update={"output": case["profile"].inputs[0].basis}
    )
    alternate_profile_ref = persist_registered_derived_input_profile(store, alternate_profile)
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
    assert (
        _resolve(
            case,
            _selection(case, tuple(snapshots.values()), profile_ref=grafted_profile_ref),
        )
        is None
    )

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
        _resolve(case, selection, routing_ref=grafted_routing_ref)

    profile_path, _profile_manifest_path = store._paths(case["profile_ref"].artifact_id)
    profile_bytes = profile_path.read_bytes()
    profile_path.unlink()
    assert _resolve(case, selection) is None
    with pytest.raises((OSError, ValueError)):
        load_n7_derivation_bundle(store, restored_ref)
    profile_path.write_bytes(profile_bytes)

    routing_path, _routing_manifest_path = store._paths(case["routing_ref"].artifact_id)
    routing_bytes = routing_path.read_bytes()
    routing_path.unlink()
    with pytest.raises((OSError, ValueError)):
        _resolve(case, selection)
    with pytest.raises((OSError, ValueError)):
        load_n7_derivation_bundle(store, restored_ref)
    routing_path.write_bytes(routing_bytes)
