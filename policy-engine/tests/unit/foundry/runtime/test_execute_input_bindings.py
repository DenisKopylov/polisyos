from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts import CoreJSONArtifactStore, validate_core_model_json_artifact
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPortDeclaration,
    load_model_input_obligation_set,
    load_program_graph_input_interface,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.semantic_input_binding import (
    RESOLVED_INPUT_BINDING_MANIFEST_ROLE,
    ResolvedInputBindingManifest,
    ResolvedMeasurementInput,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.variable_binding import (
    ModelInputScope,
    ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    SelectedVariableBindingRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.data_forge.domains.catalog.knowledge.measurement_binding import (
    assess_measurement_to_model_candidate,
)
from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane.bindings import build_input_bindings, load_input_bindings
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from tests._helpers.program_graph_tax_subsidy_input import (
    ProgramGraphTaxSubsidyInputCase,
    execute_program_graph_tax_subsidy_input_case,
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.foundry.data_plane.test_input_bindings_preparation import (
    _selected_legacy_initial_binding,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context,
    _interface,
    _opening_stock_port,
    _preflight,
    _stock_declaration,
    _supplied_rate,
)


def _compile_exec_plan(store: FileSystemCAS):
    registry_bundle = build_default_registry_bundle(store)
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="p8_execute", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_input_bindings",
            interventions=[
                InterventionSpec(
                    intervention_id="cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_input_bindings",
            data_snapshot_ref="sha256:" + ("0" * 64),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        ),
    )
    trinity_ref = store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
        ),
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=trinity_ref,
            registry_bundle_ref=registry_bundle.bundle_ref,
        ),
    )
    assert compile_result.ok
    assert compile_result.exec_plan_ref is not None
    return compile_result.exec_plan_ref, registry_bundle.bundle_ref


def test_execute_supports_input_bindings_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    exec_plan_ref, registry_bundle_ref = _compile_exec_plan(store)

    base_state = GlobalState.empty(n_agents=4, n_firms=2)
    state_snapshot_ref = put_state_snapshot(store, state=base_state, step=0)

    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id)),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    input_bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            rules=[],
            bound_state_snapshot_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id),
        ),
        PutOptions(
            kind="foundry.input_bindings",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FoundryInputBindings", version="1.0"),
        ),
    )

    result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=input_bindings_ref.artifact_id),
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    assert result.ok
    assert result.schema_version == "1.0"
    assert result.method_execution_bundle_ref is None
    assert result.simulation_result_ref is not None
    assert any(note == "state_source:input_bindings_ref" for note in result.notes)


def test_execute_refuses_semantic_binding_without_exact_correspondence_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    plan_ref, _ = _compile_exec_plan(store)
    predecessor_ref = _selected_legacy_initial_binding(
        store,
        {"income": [100, 200]},
        FoundryInputBindingRule(
            binding_id="income", source_path="income", target_slot_id="agents.income"
        ),
    )
    predecessor = load_input_bindings(store, predecessor_ref)
    manifest_ref = persist_resolved_input_binding_manifest(
        store,
        ResolvedInputBindingManifest(
            data_snapshot_ref=SelectedVariableBindingRef.model_validate(
                predecessor.data_snapshot_ref.model_dump()
            ),
            model_input_obligation_set_ref=SelectedVariableBindingRef(
                artifact_id="sha256:" + "1" * 64,
                kind="runtime.quality.model_input_obligation_set",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "2" * 64,
            ),
            measurements=(
                ResolvedMeasurementInput(
                    binding_id="selected",
                    model_input_obligation_ref=SelectedVariableBindingRef(
                        artifact_id="sha256:" + "3" * 64,
                        kind="runtime.quality.model_input_obligation",
                        media_type="application/json",
                        manifest_profile_sha256="sha256:" + "4" * 64,
                    ),
                    selected_occurrence_ref=ScopedMeasurementOccurrenceRef(
                        artifact_id="sha256:" + "5" * 64,
                        manifest_profile_sha256="sha256:" + "6" * 64,
                    ),
                    correspondence_ref=ScopedCorrespondenceBasisRef(
                        artifact_id="sha256:" + "7" * 64,
                        manifest_profile_sha256="sha256:" + "8" * 64,
                    ),
                    source_path="measurement.value",
                ),
            ),
            retained_binding_ids=("income",),
        ),
    )
    semantic = FoundryInputBindings.model_validate(
        predecessor.model_dump()
        | {"schema_version": "1.2", "resolved_binding_manifest_ref": manifest_ref}
    )
    semantic_ref = store.put_json(
        semantic,
        PutOptions(
            kind=semantic.ARTIFACT_KIND,
            media_type=semantic.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=semantic.ARTIFACT_SCHEMA_NAME, version="1.2"),
            inputs=[
                *store.get_manifest(predecessor_ref).inputs,
                input_ref_from_artifact_ref(
                    manifest_ref, role=RESOLVED_INPUT_BINDING_MANIFEST_ROLE
                ),
            ],
        ),
        return_selected_profile=True,
    )

    def forbid_dispatch(*args: object, **kwargs: object) -> None:
        pytest.fail("incomplete semantic binding reached the numerical dispatcher")

    monkeypatch.setattr(execute_api, "execute_program_graph", forbid_dispatch)
    request = ExecuteRequest(
        exec_plan_ref=plan_ref,
        registry_bundle_ref=semantic.registry_bundle_ref,
        input_bindings_ref=FoundryInputBindingsRef.model_validate(semantic_ref.model_dump()),
        return_selected_profile=True,
    )
    with pytest.raises(
        ValueError, match=r"^foundry_input_bindings_semantic_correspondence_missing$"
    ):
        execute_foundry(store, request)
    with pytest.raises(
        ValueError, match=r"^foundry_input_bindings_semantic_selected_execution_required$"
    ):
        execute_foundry(store, request.model_copy(update={"return_selected_profile": False}))


def test_opted_in_compiled_model_refuses_legacy_binding_before_dispatch(tmp_path: Path) -> None:
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=None,
        model_input_port_declaration_builder=_stock_declaration,
    )
    try:
        with pytest.raises(
            ValueError, match=r"^foundry_input_bindings_semantic_manifest_required$"
        ):
            execute_program_graph_tax_subsidy_input_case(case)
    finally:
        case.close()


def _stock_declaration_in_source_scope(store: CoreJSONArtifactStore):
    port = _opening_stock_port(store)
    scope = ModelInputScope.model_validate(
        port.scope.model_dump() | {"geography_ref": "UA", "period_basis": "calendar_year"}
    )
    port = port.model_copy(update={"scope": scope})
    return persist_model_input_port_declaration(store, ModelInputPortDeclaration(ports=(port,)))


def test_selected_catalog_stock_reaches_actual_foundry_and_fresh_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        model_input_port_declaration_builder=_stock_declaration_in_source_scope,
    )
    owner = None
    try:
        store = case.store
        interface_ref = _interface(case)
        (port,) = load_program_graph_input_interface(store, interface_ref).ports
        override_ref = _supplied_rate(case)
        preflight = _preflight(
            case,
            interface_ref,
            _context(case),
            steps=(0,),
            parameter_override_bundle_ref=override_ref,
        )
        variable_id = "test.treasury.opening-stock"
        owner = make_native_multivariable_active_projections(
            tmp_path / "source",
            source_rows=[
                {
                    "country_code": "UA",
                    "year": 2022,
                    "opening_usd": 1000,
                    "condition_json": {
                        "population_ref": "population:treasury",
                        "jurisdiction_ref": "jurisdiction:fixture",
                        "time_period_basis": "calendar_year",
                    },
                }
            ],
            variable_specs=(
                {
                    "target_variable": variable_id,
                    "raw_field": "opening_usd",
                    "raw_unit": "usd",
                    "canonical_unit": "usd",
                    "unit_transform_ref": "fabric://units/usd-identity/v1",
                    "valid_min": 0.0,
                    "valid_max": 10_000.0,
                },
            ),
            artifact_store=store,
            return_selected_raw_profile=True,
        )
        projection = owner.projections[variable_id]
        (row,) = projection.observations
        assert json.loads(row.observation.condition_json)["time_period_basis"] == "calendar_year"
        passport = AdmissionPassport.model_validate(
            load_verified_epoch_statement(
                store=store,
                ref=projection.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        correspondence = assess_measurement_to_model_candidate(
            store,
            owner.overlay,
            receipt_ref=projection.receipt_ref,
            passport=passport,
            authority=owner.authority,
            observation_id=row.observation.observation_id,
            source_definition_ref=port.semantic_definition_ref,
            source_representation_ref=port.representation_ref,
            model_interface_ref=SelectedVariableBindingRef.model_validate(
                interface_ref.model_dump()
            ),
            port_id=port.port_id,
        )
        assert correspondence.status == "candidate", correspondence.refusal_codes
        occurrence_ref = correspondence.occurrence_ref
        correspondence_ref = correspondence.correspondence_basis_ref
        assert occurrence_ref is not None and correspondence_ref is not None
        _exercise_selected_stock_binding(
            case,
            obligation_set_ref=preflight.obligation_set_ref,
            occurrence_ref=occurrence_ref,
            correspondence_ref=correspondence_ref,
            monkeypatch=monkeypatch,
        )
    finally:
        if owner is not None:
            owner.overlay.close()
        case.close()


def _exercise_selected_stock_binding(
    case: ProgramGraphTaxSubsidyInputCase,
    *,
    obligation_set_ref: ArtifactRef,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
    correspondence_ref: ScopedCorrespondenceBasisRef,
    monkeypatch: pytest.MonkeyPatch,
) -> SimulationResultRef:
    """Exercise the actual composition from already activated selected inputs."""
    store = case.store
    obligation_set, _ = load_model_input_obligation_set(store, obligation_set_ref)
    (obligation_ref,) = obligation_set.obligation_refs
    override_ref = obligation_set.invocation.parameter_override_bundle_ref
    occurrence = validate_core_model_json_artifact(
        ScopedMeasurementOccurrence, store, occurrence_ref
    )
    measurement = ResolvedMeasurementInput(
        binding_id="stock",
        model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
            obligation_ref.model_dump()
        ),
        selected_occurrence_ref=occurrence_ref,
        correspondence_ref=correspondence_ref,
        source_path="measurement.value",
    )
    source = store.put_json(
        {
            "agents": {"income": [100, 200]},
            "measurement": {
                "value": Decimal(occurrence.canonical_value),
                "other": Decimal(occurrence.canonical_value),
            },
        },
        PutOptions(
            kind="tests.program_graph.semantic_input",
            media_type="application/json",
            inputs=[
                input_ref_from_artifact_ref(
                    occurrence_ref, role=measurement.payload_occurrence_role()
                )
            ],
        ),
        return_selected_profile=True,
    )
    evidence = persist_evidence_bundle(
        store, build_evidence_bundle(sources=[source]), return_selected_profile=True
    )
    data_snapshot_ref = run_coro_sync(
        _build_snapshot_from_evidence_async(
            store=ensure_async_artifact_store(store),
            evidence_ref=evidence,
            datasets_fetched=1,
            source="test_catalog_stock_input",
        )
    )
    assert data_snapshot_ref is not None
    selection = ResolvedInputBindingManifest(
        data_snapshot_ref=SelectedVariableBindingRef.model_validate(data_snapshot_ref.model_dump()),
        model_input_obligation_set_ref=SelectedVariableBindingRef.model_validate(
            obligation_set_ref.model_dump()
        ),
        measurements=(measurement,),
        retained_binding_ids=("fixture-agents-income",),
    )
    selection_ref = persist_resolved_input_binding_manifest(store, selection)
    built = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        resolved_binding_manifest_ref=selection_ref,
        return_selected_profile=True,
    )
    request = ExecuteRequest(
        exec_plan_ref=case.exec_plan_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        input_bindings_ref=built.input_bindings_ref,
        parameter_override_bundle_ref=override_ref,
        return_selected_profile=True,
    )
    executed = execute_foundry(store, request)
    assert executed.ok and executed.simulation_result_ref is not None
    assert "semantic_input_use:candidate_simulation_input_only" in executed.notes
    assert "semantic_input_limitation:source_currentness_not_established" in executed.notes
    fresh = FileSystemCAS(case.store_root)
    try:
        admitted = admit_execution_source(fresh, executed.simulation_result_ref)
        assert admitted.basis is not None
        assert admitted.basis.input_bindings_ref == built.input_bindings_ref
        assert load_input_bindings(
            fresh, built.input_bindings_ref
        ).resolved_binding_manifest_ref == (selection_ref)
        assert admitted.simulation_result.state_snapshot_ref is not None
        state = load_state_snapshot(
            fresh, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        # The selected subsidy pays a share of both incomes out of the opening stock.
        assert float(state.government_balance) == 1000 - 0.125 * (100 + 200)

        original_manifest_reader = fresh.get_raw_manifest_bytes

        def missing_correspondence(*args: object, **kwargs: object):
            if args and getattr(args[0], "artifact_id", None) == correspondence_ref.artifact_id:
                raise FileNotFoundError("test control removes exact correspondence")
            return original_manifest_reader(*args, **kwargs)

        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(fresh, "get_raw_manifest_bytes", missing_correspondence)
            with pytest.raises(
                ValueError, match=r"^foundry_input_bindings_semantic_correspondence_missing$"
            ):
                admit_execution_source(fresh, executed.simulation_result_ref)
        assert admit_execution_source(fresh, executed.simulation_result_ref).basis == admitted.basis
    finally:
        close = getattr(fresh, "close", None)
        if callable(close):
            close()
    other_path_ref = persist_resolved_input_binding_manifest(
        store,
        selection.model_copy(
            update={
                "measurements": (
                    measurement.model_copy(update={"source_path": "measurement.other"}),
                )
            }
        ),
    )
    with pytest.raises(
        ValueError, match=r"^foundry_input_bindings_semantic_payload_occurrence_mismatch$"
    ):
        build_input_bindings(
            store,
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            resolved_binding_manifest_ref=other_path_ref,
            return_selected_profile=True,
        )
    return executed.simulation_result_ref
