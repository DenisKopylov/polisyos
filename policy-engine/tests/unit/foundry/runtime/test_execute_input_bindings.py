from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts import (
    CoreJSONArtifactStore,
    ManifestLifecycle,
    ensure_ir_artifact_store,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.execution_plan import ExecutionPlan, ExecutionPlanRef, MethodDagNode
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlanRef,
    ExecuteRequest,
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ProgramGraph,
    ProgramGraphRef,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    load_model_input_obligation_set,
    load_program_graph_input_interface,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedInputBindingManifest,
    ResolvedMeasurementInput,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    ScopedCorrespondenceBasis,
    ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    SelectedVariableBindingRef,
    scoped_correspondence_basis_manifest_inputs,
    scoped_measurement_occurrence_manifest_inputs,
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
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelInputPortDeclarationRef, ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from polisyos.runtime.quality.model_input_requirements import (
    derive_program_graph_input_interface,
    preflight_program_graph_inputs,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)
from tests._helpers.program_graph_tax_subsidy_input import (
    ProgramGraphTaxSubsidyInputCase,
    execute_program_graph_tax_subsidy_input_case,
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.data_forge.domains.catalog.knowledge.test_measurement_binding import (
    _definition,
    _representation,
)
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


def _small_input_bindings_execute_request(store: FileSystemCAS) -> ExecuteRequest:
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

    return ExecuteRequest(
        exec_plan_ref=exec_plan_ref,
        input_bindings_ref=FoundryInputBindingsRef(artifact_id=input_bindings_ref.artifact_id),
        registry_bundle_ref=registry_bundle_ref,
    )


def test_execute_supports_input_bindings_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _small_input_bindings_execute_request(store)

    # Keep the existing two-positional call covered for legacy/direct adapters.
    result = execute_foundry(store, request)
    assert result.ok
    assert result.schema_version == "1.0"
    assert result.method_execution_bundle_ref is None
    assert result.simulation_result_ref is not None
    assert any(note == "state_source:input_bindings_ref" for note in result.notes)


def test_execute_persists_run_derived_tenant_context_on_selected_result_profile(
    tmp_path: Path,
) -> None:
    tenant_id = "tenant-execute-result"
    cell_id = "cell-execute-result"
    store = FileSystemCAS(
        tmp_path / "scoped-cas",
        tenant_id=tenant_id,
        cell_id=cell_id,
        ownership_enforced=True,
    )
    request = _small_input_bindings_execute_request(store)
    derived_tenant_context = ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)

    result = execute_foundry(
        store,
        request,
        derived_tenant_context=derived_tenant_context,
    )

    assert result.ok
    assert result.simulation_result_ref is not None
    assert result.simulation_result_ref.manifest_profile_sha256 is not None
    selected_manifest = store.get_manifest(result.simulation_result_ref)
    assert selected_manifest.tenant_context == derived_tenant_context
    assert (
        ManifestLifecycle.profile_sha256(selected_manifest)
        == result.simulation_result_ref.manifest_profile_sha256
    )
    unscoped_ref = store.put_bytes(
        store.get_bytes(result.simulation_result_ref),
        PutOptions(
            kind=selected_manifest.kind,
            media_type=selected_manifest.media_type,
            schema=selected_manifest.artifact_schema,
            inputs=selected_manifest.inputs,
            canon=selected_manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert unscoped_ref.artifact_id == result.simulation_result_ref.artifact_id
    assert (
        unscoped_ref.manifest_profile_sha256 != result.simulation_result_ref.manifest_profile_sha256
    )
    assert store.get_manifest(unscoped_ref).tenant_context is None
    assert store.get_manifest(result.simulation_result_ref).tenant_context == derived_tenant_context

    # The scoped owner must reject a scope copied from another cell even when
    # the tenant ID matches; it must not publish an incorrectly bound profile.
    foreign_cell_context = ArtifactTenantContextInfo(
        tenant_id=tenant_id,
        cell_id="different-cell",
    )
    with pytest.raises(ArtifactOwnershipError, match="different cell"):
        execute_foundry(
            store,
            request,
            derived_tenant_context=foreign_cell_context,
        )


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

    def forbid_dispatch(*args: object, **kwargs: object) -> None:
        pytest.fail("incomplete semantic binding reached the numerical dispatcher")

    with monkeypatch.context() as blocked:
        blocked.setattr(execute_api, "execute_program_graph", forbid_dispatch)
        with pytest.raises(
            ValueError, match=r"^foundry_input_bindings_semantic_selected_execution_required$"
        ):
            execute_foundry(store, request.model_copy(update={"return_selected_profile": False}))
        selected_view = store._manifest_path_for_ref(
            correspondence_ref.artifact_id, correspondence_ref.manifest_profile_sha256
        )
        held_view = selected_view.with_suffix(".held")
        selected_view.rename(held_view)
        try:
            with pytest.raises(
                ValueError, match=r"^foundry_input_bindings_semantic_correspondence_missing$"
            ):
                execute_foundry(store, request)
        finally:
            held_view.rename(selected_view)

    executed = execute_foundry(store, request)
    assert executed.ok and executed.simulation_result_ref is not None
    assert "semantic_input_use:candidate_simulation_input_only" in executed.notes
    assert "semantic_input_limitation:source_currentness_not_established" in executed.notes
    fresh = FileSystemCAS(case.store_root)
    try:
        admitted = admit_execution_source(fresh, executed.simulation_result_ref)
        assert admitted.basis is not None
        assert admitted.semantic_input_limitation_codes is not None
        assert "source_currentness_not_established" in admitted.semantic_input_limitation_codes
        original_model_reader = execute_api._read_typed_model

        def changed_result_notes(model, *args, **kwargs):
            loaded = original_model_reader(model, *args, **kwargs)
            if model is execute_api.SimulationResult:
                return loaded.model_copy(
                    update={"notes": (*loaded.notes, "semantic_input_limitation:forged_extra_code")}
                )
            return loaded

        with monkeypatch.context() as extra_note:
            extra_note.setattr(execute_api, "_read_typed_model", changed_result_notes)
            extra_admitted = admit_execution_source(fresh, executed.simulation_result_ref)
        assert (
            extra_admitted.semantic_input_limitation_codes
            == admitted.semantic_input_limitation_codes
        )
        assert "forged_extra_code" not in extra_admitted.semantic_input_limitation_codes

        def missing_result_notes(model, *args, **kwargs):
            loaded = original_model_reader(model, *args, **kwargs)
            if model is execute_api.SimulationResult:
                return loaded.model_copy(update={"notes": ()})
            return loaded

        with monkeypatch.context() as missing_note:
            missing_note.setattr(execute_api, "_read_typed_model", missing_result_notes)
            with pytest.raises(
                ValueError, match="execution_source_semantic_input_limitations_missing"
            ):
                admit_execution_source(fresh, executed.simulation_result_ref)
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


class _NetOfTaxShare:
    """Test-owned linear model of the share of income left after tax."""

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="net_of_tax_share",
        namespace="tests.foundry.selected_rate",
        version="1.0.0",
        input_slots=frozenset(
            {SlotSpec("global.tax_rate", SlotType.SCALAR, Unit("rate", "ratio"))}
        ),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("rate", "ratio"))}),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Compute the retained share of a declared linear taxable base."
    )

    @staticmethod
    def pure_step(state: dict[str, np.ndarray], _params: dict[str, object]) -> dict[str, object]:
        """Compute the share from the actual selected argument."""
        net_share = 1.0 - float(state["global.tax_rate"])
        return {"result": net_share, "__numpy_artifacts__": {"net_share": {"value": net_share}}}


def _compile_tax_rate_reader(
    store: FileSystemCAS, inputs: FoundryInputBindings, port: ModelInputPort
) -> tuple[ProgramGraphRef, ExecPlanRef, ModelInputContext]:
    declaration = persist_model_input_port_declaration(
        store, ModelInputPortDeclaration(ports=(port,))
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="observed_tax_rate", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="observed_tax_rate", interventions=[]),
        model_spec=ModelSpec(
            schema_version="1.1",
            model_id="net_of_tax_share",
            data_snapshot_ref=str(inputs.data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(inputs.registry_bundle_ref.artifact_id),
            model_input_port_declaration_ref=ModelInputPortDeclarationRef.model_validate(
                declaration.model_dump()
            ),
        ),
    )
    candidate = persist_policy_candidate_schema(
        store,
        PolicyCandidateSchema(
            candidate_id="net_of_tax_share",
            trinity_bundle=trinity,
            target_population=TargetPopulationSpec(
                population_id="country", description="Test-owned taxable income population."
            ),
        ),
        inputs=[
            input_ref_from_artifact_ref(inputs.data_snapshot_ref, role="world_model_data_snapshot"),
            input_ref_from_artifact_ref(inputs.registry_bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            trinity,
            inputs=[
                input_ref_from_artifact_ref(candidate, role="policy_candidate"),
                input_ref_from_artifact_ref(declaration, role="model_input_port_declaration"),
            ],
        ).model_dump()
    )
    signature = _NetOfTaxShare.signature
    plan = ExecutionPlan(
        schema_version="1.1",
        plan_id="net_of_tax_share",
        method_dag=[
            MethodDagNode(
                node_id="net_of_tax_share",
                method_fqn=signature.fqn,
                method_version=signature.version,
                backend=signature.execution_backend.value,
                reads_slots=[port.slot_id],
                writes_slots=["result"],
                state_writes=[],
            )
        ],
    )
    plan_ref = store.put_json(
        plan,
        PutOptions(
            kind="scientist.execution_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecutionPlan", version=plan.schema_version),
            inputs=[input_ref_from_artifact_ref(trinity_ref, role="policy_candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    compiled = compile_foundry(
        store,
        CompileRequest(
            schema_version="1.2",
            input_kind="trinity",
            policy_ref=trinity_ref,
            registry_bundle_ref=inputs.registry_bundle_ref,
            method_execution_plan_ref=ExecutionPlanRef.model_validate(plan_ref.model_dump()),
            return_selected_profile=True,
        ),
    )
    assert compiled.ok and compiled.exec_plan_ref is not None, compiled.notes
    (graph_ref,) = (item.ref for item in compiled.derived_refs if item.role == "program_graph")
    graph_ref = ProgramGraphRef.model_validate(graph_ref.model_dump())
    graph = validate_core_model_json_artifact(ProgramGraph, store, graph_ref)
    assert graph.schema_version == "0.2"
    (method,) = (node for node in graph.nodes if node.node_kind == "method")
    assert method.inputs == [port.slot_id] and method.input_ports is None
    return (
        graph_ref,
        compiled.exec_plan_ref,
        ModelInputContext(
            run_id="net_of_tax_share",
            candidate_id="net_of_tax_share",
            candidate_content_hash=str(candidate.artifact_id),
            design_problem_ref=str(trinity_ref.artifact_id),
            candidate_source_ref=candidate,
        ),
    )


def _read_tax_share_in_fresh_process(
    store: FileSystemCAS, result_ref: SimulationResultRef, selection_ref: ArtifactRef
) -> dict[str, object]:
    fixture_path = Path(__file__).resolve()
    product = fixture_path.parents[4]
    child_code = """
import hashlib
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import MethodArtifactOutputPayload, MethodExecutionBundle, SimulationResultRef
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute import api
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.registry import MethodRegistry
from tests.unit.foundry.runtime import test_execute_input_bindings as fixture

assert Path(fixture.__file__).resolve() == Path(sys.argv[5])
assert hashlib.sha256(Path(fixture.__file__).read_bytes()).hexdigest() == sys.argv[6]
assert Path(api.__file__).resolve().is_relative_to(Path(sys.argv[4]))
with redirect_stdout(sys.stderr):
    MethodRegistry.get_instance().register(fixture._NetOfTaxShare)

def forbidden(*args, **kwargs):
    raise AssertionError("fresh reader attempted numerical execution")

api.execute = forbidden
api.execute_program_graph = forbidden
MethodDispatcher.dispatch = forbidden
store = FileSystemCAS.open_existing_read_only(Path(sys.argv[1]))
result = SimulationResultRef.model_validate_json(sys.argv[2])
selection = ArtifactRef.model_validate_json(sys.argv[3])
admitted = api.admit_execution_source(store, result)
assert admitted.basis is not None and admitted.basis.input_bindings_ref is not None
bindings = load_input_bindings(store, admitted.basis.input_bindings_ref)
assert artifact_ref_identity_key(bindings.resolved_binding_manifest_ref) == artifact_ref_identity_key(selection)
state = load_state_snapshot(store, snapshot_ref=admitted.simulation_result.state_snapshot_ref)
(edge,) = (edge for edge in store.get_manifest(result).inputs if edge.role == "method_execution")
bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, ArtifactRef(
    artifact_id=edge.artifact_id, manifest_profile_sha256=edge.manifest_profile_sha256,
    kind=MethodExecutionBundle.ARTIFACT_KIND, media_type="application/json",
))
(occurrence,) = (row for row in bundle.occurrences if row.node_kind == "method")
assert occurrence.status == "succeeded" and occurrence.dispatch is not None
assert occurrence.method_fqn == "tests.foundry.selected_rate.net_of_tax_share@1.0.0"
(argument,) = occurrence.dispatch.input_slot_values
assert argument.slot_id == "global.tax_rate" and argument.status == "captured"
assert argument.runtime_shape == () and argument.runtime_dtype == "<f4"
(output,) = (row for row in occurrence.artifacts if row.artifact_key == "net_share")
assert output.status == "captured" and output.artifact_ref is not None
payload = validate_core_model_json_artifact(MethodArtifactOutputPayload, store, output.artifact_ref)
assert (payload.occurrence_id, payload.invocation_id, payload.node_id, payload.artifact_key) == (
    occurrence.occurrence_id, occurrence.invocation_id, occurrence.node_id, output.artifact_key,
)
print(json.dumps({"tax_rate": float(state.tax_rate), "net_share": payload.payload["value"],
                  "argument_sha256": argument.value_sha256}))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            child_code,
            str(store.root),
            result_ref.model_dump_json(),
            selection_ref.model_dump_json(),
            str(product / "src"),
            str(fixture_path),
            hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        ],
        cwd=product,
        env=os.environ
        | {
            "PYTHONPATH": os.pathsep.join(map(str, (product / "src", product))),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert child.returncode == 0, (child.stdout, child.stderr)
    return json.loads(child.stdout)


def test_selected_catalog_tax_rate_reaches_compiled_state_reader(tmp_path: Path) -> None:
    """Qualify a selected ratio against its fiscal near miss through the actual Foundry call."""
    store = FileSystemCAS(tmp_path / "cas")
    registry = MethodRegistry.get_instance()
    registry.register(_NetOfTaxShare)
    owner = None
    try:
        opening_ref = _selected_legacy_initial_binding(
            store,
            {"agents": {"income": [100, 200]}},
            FoundryInputBindingRule(
                binding_id="fixture-agents-income",
                source_path="agents.income",
                target_slot_id="agents.income",
            ),
        )
        opening = load_input_bindings(store, opening_ref)
        rate_def = _definition(store, "test.policy", "income_tax_rate", "Tax / taxable income.")
        tax = _definition(store, "test.policy", "income_tax", "Tax on personal income.")
        base = _definition(store, "test.policy", "taxable_income", "Taxable personal income.")
        fiscal_def = _definition(store, "test.fiscal", "balance_to_gdp", "Fiscal balance / GDP.")
        balance = _definition(store, "test.fiscal", "balance", "Fiscal balance for the period.")
        gdp = _definition(store, "test.fiscal", "gdp", "Nominal gross domestic product.")
        rate_rep = _representation(store, ("test.rate", rate_def, tax, base, "parameter"))
        fiscal_rep = _representation(store, ("test.fiscal", fiscal_def, balance, gdp, "flow"))
        foreign_denominator = _representation(
            store, ("test.rate.foreign-denominator", rate_def, tax, gdp, "parameter")
        )
        profile = MeasurementBindingProfile(
            profile_id="test.observed-tax-rate",
            revision="1",
            required_axes=(
                MeasurementAxis.QUANTITY_KIND,
                MeasurementAxis.MEASURE_FORM,
                MeasurementAxis.UNIT_ID,
                MeasurementAxis.NUMERATOR_REF,
                MeasurementAxis.DENOMINATOR_REF,
                MeasurementAxis.TIME_SUPPORT,
                MeasurementAxis.TEMPORAL_GRANULARITY,
                MeasurementAxis.AGGREGATION,
                MeasurementAxis.GRAIN,
                MeasurementAxis.POPULATION_REF,
            ),
        )
        profile_ref = store.put_json(
            profile,
            PutOptions(
                kind=profile.ARTIFACT_KIND,
                media_type=profile.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=profile.ARTIFACT_SCHEMA_NAME, version=profile.ARTIFACT_SCHEMA_VERSION
                ),
            ),
            return_selected_profile=True,
        )
        port = ModelInputPort(
            port_id="observed-tax-rate",
            slot_id="global.tax_rate",
            state_path="tax_rate",
            unit_id="ratio",
            purpose="initial_state",
            semantic_definition_ref=rate_def,
            representation_ref=rate_rep,
            binding_profile_ref=MeasurementBindingProfileRef.model_validate(
                profile_ref.model_dump()
            ),
            scope=ModelInputScope(
                population_ref="population:country",
                geography_ref="UA",
                jurisdiction_ref="UA",
                period_start=date(2022, 1, 1),
                period_end=date(2022, 12, 31),
                time_role="observation_time",
                period_basis="calendar_year",
            ),
            physical_encoding=ModelInputPhysicalEncoding(
                shape=(), dtype="float32", max_absolute_error=Decimal("0.00000001")
            ),
        )
        graph_ref, exec_plan_ref, context = _compile_tax_rate_reader(store, opening, port)
        interface_ref = derive_program_graph_input_interface(
            store,
            program_graph_ref=graph_ref,
            exec_plan_ref=exec_plan_ref,
            registry_bundle_ref=opening.registry_bundle_ref,
        )
        assert interface_ref is not None
        preflight = preflight_program_graph_inputs(
            store,
            interface_ref=interface_ref,
            program_graph_ref=graph_ref,
            exec_plan_ref=exec_plan_ref,
            registry_bundle_ref=opening.registry_bundle_ref,
            input_bindings_ref=opening_ref,
            context=context,
            steps=(0,),
        )
        obligations, _ = load_model_input_obligation_set(store, preflight.obligation_set_ref)
        (obligation_ref,) = obligations.obligation_refs
        assert obligations.supplied_initial_slots == ()
        variables = (
            ("test.policy.income_tax_rate", "rate"),
            ("test.fiscal.balance_to_gdp", "fiscal"),
        )
        owner = make_native_multivariable_active_projections(
            tmp_path / "source",
            source_rows=[
                {
                    "country_code": "UA",
                    "year": 2022,
                    "rate": 20.0,
                    "fiscal": 20.0,
                    "condition_json": json.dumps(
                        {
                            "population_ref": "population:country",
                            "geography_ref": "UA",
                            "jurisdiction_ref": "UA",
                            "time_period_basis": "calendar_year",
                        }
                    ),
                }
            ],
            variable_specs=tuple(
                {
                    "target_variable": variable,
                    "raw_field": field,
                    "raw_unit": "percent",
                    "canonical_unit": "ratio",
                    "unit_transform": "fixed_multiplicative",
                    "unit_transform_ref": "fabric://units/fixed-multiplicative/v1",
                    "valid_min": 0.0,
                    "valid_max": 100.0,
                }
                for variable, field in variables
            ),
            condition_units_by_raw_field={field: "percent" for _, field in variables},
            artifact_store=store,
            return_selected_raw_profile=True,
        )

        def assess(variable, definition_ref, representation_ref):
            projection = owner.projections[variable]
            (row,) = projection.observations
            assert Decimal(str(row.observation.value)) == Decimal("0.2")
            passport = AdmissionPassport.model_validate(
                load_verified_epoch_statement(
                    store=store,
                    ref=projection.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            return assess_measurement_to_model_candidate(
                store,
                owner.overlay,
                receipt_ref=projection.receipt_ref,
                passport=passport,
                authority=owner.authority,
                observation_id=row.observation.observation_id,
                source_definition_ref=definition_ref,
                source_representation_ref=representation_ref,
                model_interface_ref=SelectedVariableBindingRef.model_validate(
                    interface_ref.model_dump()
                ),
                port_id=port.port_id,
            )

        valid = assess(variables[0][0], rate_def, rate_rep)
        assert valid.status == "candidate", valid.refusal_codes
        wrong = assess(variables[1][0], fiscal_def, fiscal_rep)
        assert wrong.status == "refused"
        assert "same_definition_profile_requires_exact_definition" in wrong.refusal_codes
        assert wrong.correspondence_basis_ref is None
        wrong_base = assess(variables[0][0], rate_def, foreign_denominator)
        assert wrong_base.status == "refused"
        assert "required_axis_mismatch:denominator_ref" in wrong_base.refusal_codes
        assert wrong_base.correspondence_basis_ref is None
        restored = assess(variables[0][0], rate_def, rate_rep)
        assert restored == valid
        occurrence_ref, basis_ref = restored.occurrence_ref, restored.correspondence_basis_ref
        assert occurrence_ref is not None and basis_ref is not None
        occurrence = validate_core_model_json_artifact(
            ScopedMeasurementOccurrence, store, occurrence_ref
        )
        assert tuple(map(Decimal, occurrence.raw_values)) == (Decimal(20),)
        assert Decimal(occurrence.canonical_value) == Decimal("0.2")
        witness = occurrence.unit_transform_evidence
        assert witness is not None and (witness.raw_unit, witness.canonical_unit) == (
            "percent",
            "ratio",
        )
        assert Decimal(witness.multiplier) == Decimal("0.01")
        measurement = ResolvedMeasurementInput(
            binding_id="observed-tax-rate",
            model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
                obligation_ref.model_dump()
            ),
            selected_occurrence_ref=occurrence_ref,
            correspondence_ref=basis_ref,
            source_path="measurement.value",
        )

        def select_measurement(selected: ResolvedMeasurementInput):
            source = store.put_json(
                {"measurement": {"value": Decimal("0.2")}},
                PutOptions(
                    kind="tests.program_graph.semantic_input",
                    media_type="application/json",
                    inputs=[
                        input_ref_from_artifact_ref(
                            selected.selected_occurrence_ref,
                            role=selected.payload_occurrence_role(),
                        )
                    ],
                ),
                return_selected_profile=True,
            )
            evidence = persist_evidence_bundle(
                store, build_evidence_bundle(sources=[source]), return_selected_profile=True
            )
            snapshot = run_coro_sync(
                _build_snapshot_from_evidence_async(
                    store=ensure_async_artifact_store(store),
                    evidence_ref=evidence,
                    datasets_fetched=1,
                    source="test_catalog_tax_rate",
                )
            )
            assert snapshot is not None
            selection = persist_resolved_input_binding_manifest(
                store,
                ResolvedInputBindingManifest(
                    data_snapshot_ref=SelectedVariableBindingRef.model_validate(
                        snapshot.model_dump()
                    ),
                    model_input_obligation_set_ref=SelectedVariableBindingRef.model_validate(
                        preflight.obligation_set_ref.model_dump()
                    ),
                    measurements=(selected,),
                ),
            )
            return snapshot, selection

        def bind(snapshot, selection):
            return build_input_bindings(
                store,
                data_snapshot_ref=snapshot,
                registry_bundle_ref=opening.registry_bundle_ref,
                resolved_binding_manifest_ref=selection,
                return_selected_profile=True,
            )

        def replace_selected(original, changed, inputs):
            manifest = store.get_manifest(original)
            return type(original).model_validate(
                store.put_json(
                    changed,
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=manifest.artifact_schema,
                        inputs=inputs,
                    ),
                    return_selected_profile=True,
                ).model_dump()
            )

        proof = validate_core_model_json_artifact(ScopedCorrespondenceBasis, store, basis_ref)
        forged_occurrence = occurrence.model_copy(
            update={"unit_transform_evidence": witness.model_copy(update={"multiplier": "0.02"})}
        )
        forged_occurrence_ref = replace_selected(
            occurrence_ref,
            forged_occurrence,
            scoped_measurement_occurrence_manifest_inputs(forged_occurrence),
        )
        forged_proof = proof.model_copy(update={"occurrence_ref": forged_occurrence_ref})
        forged_proof_ref = replace_selected(
            basis_ref, forged_proof, scoped_correspondence_basis_manifest_inputs(forged_proof)
        )
        forged_selection = select_measurement(
            measurement.model_copy(
                update={
                    "selected_occurrence_ref": forged_occurrence_ref,
                    "correspondence_ref": forged_proof_ref,
                }
            )
        )
        with pytest.raises(ValueError, match="^occurrence_transform_mismatch$"):
            bind(*forged_selection)

        snapshot, selection = select_measurement(measurement)
        selected_view = store._manifest_path_for_ref(
            basis_ref.artifact_id, basis_ref.manifest_profile_sha256
        )
        held = selected_view.with_suffix(".held")
        selected_view.rename(held)
        try:
            with pytest.raises(
                ValueError, match="^foundry_input_bindings_semantic_correspondence_missing$"
            ):
                bind(snapshot, selection)
        finally:
            held.rename(selected_view)

        bound = bind(snapshot, selection)
        result = execute_foundry(
            store,
            ExecuteRequest(
                exec_plan_ref=exec_plan_ref,
                registry_bundle_ref=opening.registry_bundle_ref,
                input_bindings_ref=bound.input_bindings_ref,
                return_selected_profile=True,
            ),
        )
        assert result.ok and result.simulation_result_ref is not None, result.notes
        fresh = _read_tax_share_in_fresh_process(store, result.simulation_result_ref, selection)
        rate = np.asarray(0.2, dtype="<f4")
        assert fresh == {
            "tax_rate": float(rate),
            "net_share": 1.0 - float(rate),
            "argument_sha256": hashlib.sha256(b"<f4[]" + rate.tobytes()).hexdigest(),
        }
    finally:
        if owner is not None:
            owner.overlay.close()
        registry.unregister(_NetOfTaxShare.signature.fqn)
