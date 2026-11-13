"""Selected Foundry step intake and fresh predecessor-chain verification."""

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, WarningRecord, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    MetricsRef,
    SemanticHorizonStepContext,
    SimulationResult,
    SimulationResultRef,
    StateSnapshot,
    StateSnapshotRef,
)
from polisyos.core.contracts.model_input_requirements import (
    ProgramGraphInputInvocation,
    load_model_input_obligation_set,
    load_program_graph_input_interface,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedInputBindingManifest,
    ResolvedMeasurementInput,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.variable_binding import (
    ScopedMeasurementOccurrence,
    SelectedVariableBindingRef,
)
from polisyos.data_forge.domains.catalog.knowledge.measurement_binding import (
    assess_measurement_to_model_candidate,
)
from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute.api import (
    ExecutionSourceAdmission,
    admit_execution_source,
    admit_semantic_horizon_step_chain,
    execute,
    execute_semantic_horizon_step,
)
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.foundry.runtime.test_execute_input_bindings import (
    _stock_declaration_in_source_scope,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context,
    _interface,
    _preflight,
)


def _bind_opening_stock(tmp_path, case, steps):
    store = case.store
    interface_ref = _interface(case)
    (port,) = load_program_graph_input_interface(store, interface_ref).ports
    preflight = _preflight(case, interface_ref, _context(case), steps=steps)
    obligation_set_ref = preflight.obligation_set_ref
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
        model_interface_ref=SelectedVariableBindingRef.model_validate(interface_ref.model_dump()),
        port_id=port.port_id,
    )
    assert correspondence.status == "candidate", correspondence.refusal_codes
    occurrence_ref = correspondence.occurrence_ref
    correspondence_ref = correspondence.correspondence_basis_ref
    assert occurrence_ref is not None and correspondence_ref is not None
    owner.overlay.close()
    obligation_set, members = load_model_input_obligation_set(store, obligation_set_ref)
    (stock,) = members
    assert stock.port.purpose == "initial_state"
    assert {dep.first_required_step for dep in stock.dependencies} == {3}
    (obligation_ref,) = obligation_set.obligation_refs
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
            "measurement": {"value": Decimal(occurrence.canonical_value)},
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

    return (
        ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=built.input_bindings_ref,
            return_selected_profile=True,
        ),
        obligation_set_ref,
        obligation_set.invocation,
        correspondence_ref,
    )


def _rebind_step_predecessor(
    store: FileSystemCAS,
    selected: ExecutionSourceAdmission,
    foreign: SimulationResultRef,
) -> SimulationResultRef:
    """Rehash a locally consistent result, preserving the original physical base."""
    assert selected.basis is not None and selected.basis_ref is not None
    assert selected.basis.semantic_horizon_step is not None
    assert selected.simulation_result.metrics_ref is not None
    assert selected.simulation_result.state_snapshot_ref is not None
    basis = selected.basis.model_copy(
        update={
            "semantic_horizon_step": selected.basis.semantic_horizon_step.model_copy(
                update={"previous_result_ref": foreign}
            )
        }
    )

    def options(ref: ArtifactRef, replacements: dict[str, ArtifactRef]):
        original = store.get_manifest(ref)
        edges = [
            input_ref_from_artifact_ref(replacements[edge.role], role=edge.role)
            if edge.role in replacements
            else edge
            for edge in original.inputs
        ]
        return PutOptions(
            kind=original.kind,
            media_type=original.media_type,
            schema=original.artifact_schema,
            inputs=edges,
            canon=original.canon,
        )

    def rewrite_profile(ref: ArtifactRef, replacements: dict[str, ArtifactRef]):
        return store.put_bytes(
            store.get_bytes(ref), options(ref, replacements), return_selected_profile=True
        )

    forged_basis = store.put_json(
        basis,
        replace(
            options(selected.basis_ref, {}),
            inputs=execute_api._execution_input_basis_inventory(store, basis),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    delta = execute_api._selected_ref_from_edge(
        store, selected.simulation_result_ref, "state_delta", expected_kind="foundry.state_delta"
    )
    rebased_delta = rewrite_profile(delta, {"execution_input_basis": forged_basis})
    metrics = rewrite_profile(
        selected.simulation_result.metrics_ref, {"execution_input_basis": forged_basis}
    )
    poststate_ref = selected.simulation_result.state_snapshot_ref
    poststate = validate_core_model_json_artifact(StateSnapshot, store, poststate_ref)
    poststate_options = options(poststate_ref, {"state_delta": rebased_delta})
    rebased_poststate = store.put_json(
        poststate.model_copy(update={"lineage_inputs": poststate_options.inputs}),
        poststate_options,
        return_selected_profile=True,
    )
    forged_result = SimulationResult.model_validate(
        selected.simulation_result.model_dump()
        | {
            "execution_input_basis_ref": forged_basis.model_dump(),
            "metrics_ref": MetricsRef.model_validate(metrics.model_dump()),
            "state_snapshot_ref": StateSnapshotRef.model_validate(rebased_poststate.model_dump()),
        }
    )
    return SimulationResultRef.model_validate(
        store.put_json(
            forged_result.to_artifact_payload(),
            options(
                selected.simulation_result_ref,
                {
                    "execution_input_basis": forged_basis,
                    "metrics": metrics,
                    "state_delta": rebased_delta,
                    "state_snapshot": rebased_poststate,
                },
            ),
            return_selected_profile=True,
        ).model_dump()
    )


def test_selected_semantic_horizon_applies_late_steps_to_exact_previous_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    steps = (0, 1, 2, 3, 4)
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        mechanism_start_step=3,
        mechanism_duration_steps=2,
        model_input_port_declaration_builder=_stock_declaration_in_source_scope,
    )
    try:
        store = case.store
        request, obligation_set_ref, invocation, correspondence_ref = _bind_opening_stock(
            tmp_path, case, steps
        )
        with pytest.raises(ValueError, match="semantic_execution_step_mismatch"):
            execute(store, request)

        def run(index: int, seed: int, previous: SimulationResultRef | None = None):
            step = SemanticHorizonStepContext(
                obligation_set_ref=obligation_set_ref,
                steps=steps,
                step_index=index,
                replication_seed=seed,
                previous_result_ref=previous,
            )
            result = execute_semantic_horizon_step(
                store, request, expected_invocation=invocation, step=step
            )
            assert result.ok and result.simulation_result_ref is not None
            return result.simulation_result_ref

        first = run(0, 11)
        other = run(0, 12)
        with pytest.raises(ValueError, match="semantic_horizon_predecessor_scope_mismatch"):
            run(1, 11, other)
        with pytest.raises(ValueError, match="semantic_horizon_predecessor_scope_mismatch"):
            run(2, 11, first)

        refs = [first]
        for index in range(1, len(steps)):
            refs.append(run(index, 11, refs[-1]))
        fresh = FileSystemCAS(case.store_root)
        try:
            with pytest.raises(ValueError, match="semantic_horizon_consumer_required"):
                admit_execution_source(fresh, refs[0])
            with pytest.raises(ValueError, match="semantic_horizon_result_schedule_mismatch"):
                admit_semantic_horizon_step_chain(fresh, tuple(refs[:-1]))
            with pytest.raises(ValueError, match="semantic_horizon_result_schedule_mismatch"):
                admit_semantic_horizon_step_chain(fresh, (*refs[:4], refs[3]))
            with pytest.raises(ValueError, match="semantic_horizon_predecessor_not_admitted"):
                admit_semantic_horizon_step_chain(fresh, (other, *refs[1:]))

            admissions = admit_semantic_horizon_step_chain(fresh, tuple(refs))
            foreign_2 = run(2, 12, run(1, 12, other))
            forged_3 = _rebind_step_predecessor(store, admissions[3], foreign_2)
            # A standalone step check cannot distinguish this coherent rehash.
            isolated = execute_api._admit_execution_source(
                fresh, forged_3, allow_semantic_horizon_step=True
            )
            assert isolated.basis is not None and admissions[3].basis is not None
            assert (
                isolated.basis.base_state_snapshot_ref
                == admissions[3].basis.base_state_snapshot_ref
            )

            def unexpected_work(*args, **kwargs):
                pytest.fail("invalid semantic preflight reached physical dispatch or CAS write")

            with monkeypatch.context() as scope:
                scope.setattr(execute_api, "execute_program_graph", unexpected_work)
                scope.setattr(store, "put_json", unexpected_work)
                scope.setattr(store, "put_bytes", unexpected_work)
                with pytest.raises(ValueError, match="semantic_horizon_predecessor_scope_mismatch"):
                    run(4, 11, forged_3)
                step = SemanticHorizonStepContext(
                    obligation_set_ref=obligation_set_ref,
                    steps=steps,
                    step_index=0,
                    replication_seed=11,
                )
                for invalid, refusal in (
                    (None, "semantic_horizon_expected_invocation_untyped"),
                    (
                        ProgramGraphInputInvocation.model_construct(
                            **(vars(invocation) | {"steps": (0, 0)})
                        ),
                        "model_input_execution_steps_invalid",
                    ),
                ):
                    with pytest.raises(ValueError, match=refusal):
                        execute_semantic_horizon_step(
                            store, request, expected_invocation=invalid, step=step
                        )

            actual = refs[3]
            manifest = store.get_manifest(actual)
            alternate = SimulationResultRef.model_validate(
                store.put_bytes(
                    store.get_bytes(actual),
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=manifest.artifact_schema,
                        inputs=manifest.inputs,
                        canon=manifest.canon,
                        warnings=[WarningRecord(code="test.alternate_view", msg="Same step bytes")],
                    ),
                    return_selected_profile=True,
                ).model_dump()
            )
            assert alternate.artifact_id == actual.artifact_id
            assert alternate.manifest_profile_sha256 != actual.manifest_profile_sha256
            with pytest.raises(ValueError, match="semantic_horizon_predecessor_not_admitted"):
                admit_semantic_horizon_step_chain(fresh, (*refs[:3], alternate, refs[4]))

            for index, (admission, balance) in enumerate(
                zip(admissions, (1000, 1000, 1000, 962.5, 920.3125), strict=True)
            ):
                assert admission.basis is not None
                assert admission.basis.effective_step == steps[index]
                assert admission.basis.effective_seed == 11 + steps[index]
                assert admission.simulation_result.state_snapshot_ref is not None
                state = load_state_snapshot(
                    fresh, snapshot_ref=admission.simulation_result.state_snapshot_ref
                )
                assert float(state.government_balance) == balance
                assert float(state.government_balance + np.sum(state.agents.income)) == 1300
                assert "semantic_input_use:candidate_simulation_input_only" in (
                    admission.simulation_result.notes
                )

            reader = fresh.get_raw_manifest_bytes

            def missing_proof(ref, *args, **kwargs):
                if getattr(ref, "artifact_id", None) == correspondence_ref.artifact_id:
                    raise FileNotFoundError("test removal of selected correspondence")
                return reader(ref, *args, **kwargs)

            with monkeypatch.context() as scope:
                scope.setattr(fresh, "get_raw_manifest_bytes", missing_proof)
                with pytest.raises(ValueError, match="semantic_correspondence_missing"):
                    admit_semantic_horizon_step_chain(fresh, tuple(refs))
            assert admit_semantic_horizon_step_chain(fresh, tuple(refs)) == admissions
        finally:
            close = getattr(fresh, "close", None)
            if callable(close):
                close()
    finally:
        case.close()


def test_semantic_horizon_observer_sees_actual_selected_mechanism_calls(tmp_path: Path) -> None:
    """The optional port observes the real bound call without supplying its result."""
    from polisyos.foundry.execute.mechanisms.fiscal import TaxSubsidy

    class Observer:
        def __init__(self) -> None:
            self.started = []
            self.nodes = []
            self.calls = []
            self.finished = []

        def graph_started(self, **values):
            self.started.append(values)

        def node_finished(self, **values):
            self.nodes.append(values)

        def mechanism_started(self, **values):
            self.calls.append(values)

        def mechanism_finished(self, **values):
            self.finished.append(("call", values))

        def graph_finished(self, **values):
            self.finished.append(("graph", values))

    steps = (0, 1, 2, 3, 4)
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        mechanism_start_step=3,
        mechanism_duration_steps=2,
        model_input_port_declaration_builder=_stock_declaration_in_source_scope,
    )
    try:
        request, obligation_set_ref, invocation, _ = _bind_opening_stock(tmp_path, case, steps)
        observer = Observer()
        refs = []
        for index in range(len(steps)):
            step = SemanticHorizonStepContext(
                obligation_set_ref=obligation_set_ref,
                steps=steps,
                step_index=index,
                replication_seed=11,
                previous_result_ref=refs[-1] if refs else None,
            )
            executed = execute_semantic_horizon_step(
                case.store, request, expected_invocation=invocation, step=step, observer=observer
            )
            assert executed.ok and executed.simulation_result_ref is not None
            refs.append(executed.simulation_result_ref)
        assert [(row["step"], row["seed"]) for row in observer.started] == [
            (index, 11 + index) for index in steps
        ]
        for row in observer.started:
            expected_nodes = tuple(item[0] for item in row["nodes"])
            actual_nodes = tuple(
                item["node_id"] for item in observer.nodes if item["step"] == row["step"]
            )
            assert actual_nodes == expected_nodes
        assert [call["step"] for call in observer.calls] == [3, 4]
        assert all(
            call["selected_call"].__func__ is TaxSubsidy.emit_patches
            and type(call["selected_call"].__self__) is TaxSubsidy
            for call in observer.calls
        )
        assert [item[1]["status"] for item in observer.finished if item[0] == "call"] == [
            "returned",
            "returned",
        ]
        assert len([item for item in observer.finished if item[0] == "graph"]) == len(steps)
        final = admit_semantic_horizon_step_chain(case.store, tuple(refs))[-1]
        assert final.simulation_result.state_snapshot_ref is not None
        state = load_state_snapshot(
            case.store, snapshot_ref=final.simulation_result.state_snapshot_ref
        )
        assert float(state.government_balance) == 920.3125
    finally:
        case.close()
