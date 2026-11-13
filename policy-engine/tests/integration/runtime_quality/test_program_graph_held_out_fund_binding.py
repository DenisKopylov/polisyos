"""Enroll a distinct, test-owned cash stock into the existing Foundry profile."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from math import isfinite
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.fabric import (
    AcquiredObservationSemanticInputDataSnapshotLineage,
    AcquiredObservationSemanticInputDataSnapshotOwnerBound,
    DataSnapshot,
)
from polisyos.core.contracts.foundry import ExecuteRequest
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPortDeclaration,
    load_program_graph_input_interface,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.core.contracts.variable_binding import (
    ScopedCorrespondenceBasis,
    ScopedMeasurementOccurrence,
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.data_plane import load_input_bindings, prepare_input_bindings
from polisyos.foundry.execute import (
    admit_execution_source,
    load_state_snapshot,
    prepare_program_graph_mechanism_calls,
)
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from polisyos.runtime.quality.data_state_substrate import (
    AcquiredObservationSemanticInputRequest,
    ControlledAcquisitionSlotBinding,
    DataStateSubstrateError,
    acquired_observation_binding_rule,
    materialize_acquired_observation_snapshot,
)
from polisyos.runtime.quality.model_input_requirements import SelectedProgramGraphInputBasis
from polisyos.runtime.quality.model_input_routing import plan_selected_model_input_routing
from tests._helpers.lane01_wdi_profiles import CandidateWDIProfile
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.semantic_epoch_native import (
    NativeEpochFixtureCustodian,
    make_native_live_measurement_history,
    make_native_multivariable_active_projections,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _put_semantic_definition,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context,
    _interface,
    _opening_stock_port,
    _preflight,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path
    from types import SimpleNamespace

    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactStore
    from polisyos.core.contracts.model_input_requirements import ModelInputPort
    from polisyos.data_forge.read_api.catalog import CanonicalAcquisitionAuthority
    from polisyos.runtime.quality.data_state_substrate import AcquiredObservationDataSnapshotResult
    from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight
    from polisyos.runtime.quality.model_input_routing import ModelInputRoutingResult
    from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase


def _fund_port(
    store: CoreJSONArtifactStore, template: ModelInputPort, *, fund: str
) -> ModelInputPort:
    population = f"population:{fund}"
    meaning = (
        f"USD cash held in the {fund} ledger at the start of the calendar year, "
        "excluding balances of other funds and subsequent receipts or expenditure."
    )
    evidence_ref = store.put_bytes(
        meaning.encode(),
        PutOptions(kind="tests.public_fund_ledger_definition", media_type="text/plain"),
        return_selected_profile=True,
    )
    definition_ref = _put_semantic_definition(
        store,
        VariableSemanticDefinition(
            namespace=f"test.{fund}",
            stable_id="opening-cash",
            revision="1",
            meaning=meaning,
            definition_evidence_refs=(
                SelectedVariableBindingRef.model_validate(evidence_ref.model_dump()),
            ),
        ),
    )
    representation = validate_core_model_json_artifact(
        VariableRepresentation, store, template.representation_ref
    ).model_copy(
        update={
            "representation_id": f"test.{fund}.opening-cash-usd",
            "semantic_definition_ref": definition_ref,
            "population_ref": population,
        }
    )
    representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            representation,
            PutOptions(
                kind=representation.ARTIFACT_KIND,
                media_type=representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=representation.ARTIFACT_SCHEMA_NAME,
                    version=representation.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[input_ref_from_artifact_ref(definition_ref, role="semantic_definition")],
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    return template.model_copy(
        update={
            "port_id": "fund-opening-cash",
            "semantic_definition_ref": definition_ref,
            "representation_ref": representation_ref,
            "scope": template.scope.model_copy(
                update={
                    "population_ref": population,
                    "geography_ref": "UA",
                    "jurisdiction_ref": "UA",
                    "period_basis": "calendar_year",
                }
            ),
        }
    )


def _held_out_declaration(store: CoreJSONArtifactStore) -> ArtifactRef:
    # The selected model represents a ring-fenced subsidy fund in its one cash slot.
    port = _fund_port(store, _opening_stock_port(store), fund="public-benefit-fund")
    return persist_model_input_port_declaration(store, ModelInputPortDeclaration(ports=(port,)))


def _treasury_stock_declaration(store: CoreJSONArtifactStore) -> ArtifactRef:
    port = _fund_port(store, _opening_stock_port(store), fund="treasury")
    return persist_model_input_port_declaration(store, ModelInputPortDeclaration(ports=(port,)))


@contextmanager
def _activated_fund(
    tmp_path: Path,
    *,
    store: FileSystemCAS,
    port: ModelInputPort,
    fund: str,
    opening_cash_usd: int | float = 640,
    fixture_custodian: NativeEpochFixtureCustodian | None = None,
    before_activation: Callable[[CanonicalAcquisitionAuthority], None],
) -> Iterator[SimpleNamespace]:
    if isinstance(opening_cash_usd, bool) or not isinstance(opening_cash_usd, int | float):
        raise ValueError("activated_fund_opening_cash_must_be_finite_numeric")
    try:
        opening_cash_is_finite = isfinite(float(opening_cash_usd))
    except OverflowError:
        opening_cash_is_finite = False
    if not opening_cash_is_finite:
        raise ValueError("activated_fund_opening_cash_must_be_finite_numeric")
    active = make_native_multivariable_active_projections(
        tmp_path,
        source_rows=[
            {
                "country_code": "UA",
                "year": 2022,
                "opening_cash_usd": opening_cash_usd,
                "condition_json": {
                    "population_ref": port.scope.population_ref,
                    "jurisdiction_ref": "UA",
                    "time_period_basis": "calendar_year",
                },
            }
        ],
        variable_specs=(
            {
                "target_variable": f"test.{fund}.opening-cash",
                "raw_field": "opening_cash_usd",
                "raw_unit": "usd",
                "canonical_unit": "usd",
                "unit_transform_ref": "fabric://units/usd-identity/v1",
                "valid_max": 10_000.0,
                "source_measure_scope": {
                    "population": port.scope.population_ref,
                    "temporal_granularity": "annual",
                },
                "source_semantic_definition_ref": port.semantic_definition_ref,
                "source_representation_ref": port.representation_ref,
            },
        ),
        artifact_store=store,
        return_selected_raw_profile=True,
        fixture_custodian=fixture_custodian,
        before_activation=before_activation,
    )
    try:
        yield active
    finally:
        active.overlay.close()


def _bind_activated_fund(
    case: ProgramGraphTaxSubsidyInputCase,
    *,
    active: SimpleNamespace,
    routing: ModelInputRoutingResult,
    preflight: ProgramGraphInputPreflight,
    source_port: ModelInputPort,
    workspace: Path,
    expected_opening_cash_usd: int | float = 640,
) -> AcquiredObservationDataSnapshotResult:
    (entry,) = active.entries
    projection = active.projections[entry.target_variable]
    (row,) = projection.observations
    passport = AdmissionPassport.model_validate(
        load_verified_epoch_statement(
            store=case.store,
            ref=projection.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    assert row.observation.value == expected_opening_cash_usd
    assert passport.field_binding.canonical_unit == "usd"
    assert passport.source_authority_verified
    assert passport.source_lane == "local_lift"
    assert passport.authority_entry_id == entry.entry_id
    assert passport.license_evidence.license_id == "CC-BY-4.0"
    assert passport.source_watermark == entry.local_source_sha256
    (route,) = routing.report.routes
    if route.source_descriptor is not None:
        assert route.source_descriptor.authority_entry_id == passport.authority_entry_id
        assert (
            route.source_descriptor.authority_registry_content_sha256
            == passport.authority_registry_content_sha256
        )
    slot_binding = ControlledAcquisitionSlotBinding(
        profile_selection_ref=str(routing.report_ref.artifact_id),
        canonical_variable_id=entry.target_variable,
        target_slot_id=source_port.slot_id,
    )
    binding_rule = acquired_observation_binding_rule(
        observation=row.observation, slot_binding=slot_binding
    )
    return materialize_acquired_observation_snapshot(
        case.store,
        base_data_snapshot_ref=case.data_snapshot_ref,
        overlay=active.overlay,
        receipt_ref=projection.receipt_ref,
        passport=passport,
        authority=active.authority,
        observation_id=row.observation.observation_id,
        slot_binding=slot_binding,
        workspace_dir=workspace,
        transaction_time=datetime(2026, 10, 2, 12, tzinfo=UTC),
        semantic_input_request=AcquiredObservationSemanticInputRequest(
            binding_id=binding_rule.binding_id,
            source_definition_ref=source_port.semantic_definition_ref,
            source_representation_ref=source_port.representation_ref,
            obligation_set_ref=SelectedVariableBindingRef.model_validate(
                preflight.obligation_set_ref.model_dump()
            ),
            expected_invocation=preflight.invocation,
            model_port_id=route.port_id,
        ),
    )


@pytest.mark.integration
def test_live_scoped_stock_reaches_foundry_preparation_with_selected_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A controlled live source reaches a fresh Foundry consumer, without N5."""
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        model_input_port_declaration_builder=_treasury_stock_declaration,
        snapshot_id="live-scoped-stock-predecessor",
    )
    try:
        interface_ref = _interface(case)
        (port,) = load_program_graph_input_interface(case.store, interface_ref).ports
        preflight = _preflight(case, interface_ref, _context(case), steps=(0,))
        assert len(preflight.obligation_refs) == 1
        invocation = preflight.invocation
        selected = SelectedProgramGraphInputBasis(
            context=invocation.context,
            program_graph_ref=invocation.program_graph_ref,
            exec_plan_ref=invocation.exec_plan_ref,
            registry_bundle_ref=invocation.registry_bundle_ref,
            input_bindings_ref=invocation.input_bindings_ref,
            steps=(0,),
        )
        profile = CandidateWDIProfile(
            construct="test.treasury.opening-cash",
            indicator_id="POLICYOS.FIXTURE.TREASURY.STOCK",
            source_title="Test-owned annual treasury stock (current US$)",
            source_description="Controlled test values; no external empirical origin is asserted.",
            target_slot="test.treasury.opening-cash",
            raw_unit="usd",
            canonical_unit="usd",
            transform="identity",
            transform_ref="fabric://units/usd-identity/v1",
            population="population:treasury",
            fixture_value=640.0,
            source_provenance_class="observed",
            valid_min=0.0,
            valid_max=10_000.0,
            country_code="UKR",
            country_id="UA",
            year=2022,
        )
        history = make_native_live_measurement_history(
            tmp_path / "live-source",
            profile=profile,
            semantic_definition_ref=port.semantic_definition_ref,
            representation_ref=port.representation_ref,
            attempt_ids=("live-foundry-preflight",),
            artifact_store=case.store,
            monkeypatch=monkeypatch,
            source_measure_scope={
                "population": "population:treasury",
                "temporal_granularity": "annual",
                "source_geography_id": "UA",
                "geography_ref": "UA",
                "jurisdiction_ref": "UA",
                "time_period_basis": "calendar_year",
            },
        )
        try:
            routing = plan_selected_model_input_routing(
                case.store,
                obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected,
                catalog_authority=history.authority,
            )
            (route,) = routing.report.routes
            assert route.disposition == "resolved"
            assert route.source_descriptor is not None
            assert (
                route.source_descriptor.source_semantic_definition_ref
                == port.semantic_definition_ref
            )
            active = history.admit(640.0)
            assert history.transport_calls == 1
            projection = active.projections[history.entry.target_variable]
            (row,) = projection.observations
            assert row.observation.value == 640.0
            assert row.observation.country_code == "UKR"
            assert active.passport.source_lane == "live_fetch"
            assert active.passport.field_binding.canonical_unit == "usd"
            source_entry = active.passport.source_authority_entry
            assert source_entry is not None and source_entry.source_measure_scope is not None
            assert source_entry.source_semantic_definition_ref == port.semantic_definition_ref
            assert source_entry.source_representation_ref == port.representation_ref
            assert source_entry.source_measure_scope.population == "population:treasury"
            assert source_entry.source_measure_scope.source_geography_id == "UA"
            assert source_entry.source_measure_scope.geography_ref == "UA"
            assert source_entry.source_measure_scope.jurisdiction_ref == "UA"
            assert source_entry.source_measure_scope.time_period_basis == "calendar_year"
            slot_binding = ControlledAcquisitionSlotBinding(
                profile_selection_ref=str(routing.report_ref.artifact_id),
                canonical_variable_id=history.entry.target_variable,
                target_slot_id=port.slot_id,
            )
            rule = acquired_observation_binding_rule(
                observation=row.observation, slot_binding=slot_binding
            )
            semantic_request = AcquiredObservationSemanticInputRequest(
                binding_id=rule.binding_id,
                source_definition_ref=port.semantic_definition_ref,
                source_representation_ref=port.representation_ref,
                obligation_set_ref=SelectedVariableBindingRef.model_validate(
                    preflight.obligation_set_ref.model_dump()
                ),
                expected_invocation=invocation,
                model_port_id=route.port_id,
            )

            def materialize(request: AcquiredObservationSemanticInputRequest, workspace: Path):
                return materialize_acquired_observation_snapshot(
                    case.store,
                    base_data_snapshot_ref=case.data_snapshot_ref,
                    overlay=history.overlay,
                    receipt_ref=projection.receipt_ref,
                    passport=active.passport,
                    authority=history.authority,
                    observation_id=row.observation.observation_id,
                    slot_binding=slot_binding,
                    workspace_dir=workspace,
                    transaction_time=datetime(2026, 10, 2, 12, tzinfo=UTC),
                    semantic_input_request=request,
                )

            acquired = materialize(semantic_request, tmp_path / "acquired")
            selection = acquired.semantic_input_selection
            assert selection is not None
            basis = validate_core_model_json_artifact(
                ScopedCorrespondenceBasis, case.store, selection.correspondence_basis_ref
            )
            occurrence = validate_core_model_json_artifact(
                ScopedMeasurementOccurrence, case.store, selection.occurrence_ref
            )
            assert basis.occurrence_ref == selection.occurrence_ref
            assert (
                basis.source_definition_ref
                == basis.target_definition_ref
                == port.semantic_definition_ref
            )
            assert basis.source_representation_ref == port.representation_ref
            assert basis.scope == occurrence.source_scope == port.scope
            assert occurrence.canonical_unit == port.unit_id == "usd"
            assert float(occurrence.canonical_value) == 640.0
            assert artifact_ref_identity_key(occurrence.source_receipt_ref) == (
                artifact_ref_identity_key(projection.receipt_ref)
            )
            assert artifact_ref_identity_key(occurrence.source_passport_ref) == (
                artifact_ref_identity_key(projection.passport_ref)
            )
            assert artifact_ref_identity_key(occurrence.source_boundary_candidate_ref) == (
                artifact_ref_identity_key(active.passport.semantic_boundary_candidate_ref)
            )
            live_snapshot = validate_core_model_json_artifact(
                DataSnapshot, case.store, active.evidence.data_snapshot_ref
            )
            assert artifact_ref_identity_key(occurrence.source_record_ref) == (
                artifact_ref_identity_key(live_snapshot.data_ref)
            )
            assert artifact_ref_identity_key(occurrence.source_record_ref) == (
                artifact_ref_identity_key(
                    active.finalized.case.scenario.candidate.statement.source_record_ref
                )
            )
            assert (
                occurrence.source_record_ref.artifact_id
                == active.evidence.normalized_data_artifact_id
            )
            assert occurrence.source_record_ref.artifact_id != active.evidence.raw_artifact_id
            assert occurrence.source_watermark == active.evidence.raw_body_sha256
            snapshot = validate_core_model_json_artifact(
                AcquiredObservationSemanticInputDataSnapshotOwnerBound,
                case.store,
                acquired.data_snapshot_ref,
            )
            lineage = snapshot.source_lineage
            assert isinstance(lineage, AcquiredObservationSemanticInputDataSnapshotLineage)
            assert lineage.selection == selection
            assert lineage.passport_ref == projection.passport_ref

            fresh = FileSystemCAS(case.store_root)
            bindings_ref = acquired.semantic_foundry_input_bindings_ref
            assert bindings_ref is not None
            bindings = load_input_bindings(fresh, bindings_ref)
            assert bindings.data_snapshot_ref == acquired.data_snapshot_ref
            assert bindings.resolved_binding_manifest_ref is not None
            manifest = load_resolved_input_binding_manifest(
                fresh, bindings.resolved_binding_manifest_ref
            )
            (resolved,) = manifest.measurements
            assert resolved.selected_occurrence_ref == selection.occurrence_ref
            assert resolved.correspondence_ref == selection.correspondence_basis_ref
            prepared = prepare_input_bindings(
                fresh,
                data_snapshot_ref=bindings.data_snapshot_ref,
                registry_bundle_ref=bindings.registry_bundle_ref,
                rules=bindings.rules,
                resolved_binding_manifest_ref=bindings.resolved_binding_manifest_ref,
            )
            initial = load_state_snapshot(fresh, snapshot_ref=bindings.bound_state_snapshot_ref)
            assert float(prepared.materialized_state.government_balance) == 640.0
            assert float(initial.government_balance) == 640.0
            registry = load_registry_bundle_content(fresh, case.registry_bundle_ref)
            calls = prepare_program_graph_mechanism_calls(
                fresh,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                base_state=initial,
                mechanism_registry=registry.mechanism_registry,
                steps=(0,),
            )
            assert calls and all(step == 0 and callable(call) for _, _, step, call in calls)

            foreign = _fund_port(case.store, port, fund="foreign-treasury")
            assert foreign.binding_profile_ref == port.binding_profile_ref
            assert foreign.semantic_definition_ref != port.semantic_definition_ref
            refused_workspace = tmp_path / "foreign-fund"
            foreign_request = semantic_request.model_copy(
                update={
                    "source_definition_ref": foreign.semantic_definition_ref,
                    "source_representation_ref": foreign.representation_ref,
                }
            )
            with pytest.raises(
                DataStateSubstrateError, match="source_declared_definition_ref_mismatch"
            ):
                materialize(foreign_request, refused_workspace)
            assert not refused_workspace.exists()

            raw_ref = active.evidence.raw_artifact_ref
            assert raw_ref is not None
            read_bytes = fresh.get_bytes

            def missing_selected_raw(ref):
                if getattr(ref, "artifact_id", None) == raw_ref.artifact_id:
                    raise FileNotFoundError("selected live raw source removed")
                return read_bytes(ref)

            with monkeypatch.context() as context:
                context.setattr(fresh, "get_bytes", missing_selected_raw)
                with pytest.raises(FileNotFoundError, match="selected live raw source removed"):
                    prepare_input_bindings(
                        fresh,
                        data_snapshot_ref=bindings.data_snapshot_ref,
                        registry_bundle_ref=bindings.registry_bundle_ref,
                        rules=bindings.rules,
                        resolved_binding_manifest_ref=bindings.resolved_binding_manifest_ref,
                    )
            assert (
                float(
                    prepare_input_bindings(
                        fresh,
                        data_snapshot_ref=bindings.data_snapshot_ref,
                        registry_bundle_ref=bindings.registry_bundle_ref,
                        rules=bindings.rules,
                        resolved_binding_manifest_ref=bindings.resolved_binding_manifest_ref,
                    ).materialized_state.government_balance
                )
                == 640.0
            )
        finally:
            history.overlay.close()
    finally:
        case.close()


@pytest.mark.integration
def test_distinct_fund_opening_cash_reaches_foundry_through_the_existing_profile(
    tmp_path: Path,
) -> None:
    """A signed fixture proves enrollment and physical use within one supported profile."""
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        model_input_port_declaration_builder=_held_out_declaration,
        snapshot_id="held-out-fund-predecessor",
    )
    try:
        interface_ref = _interface(case)
        (port,) = load_program_graph_input_interface(case.store, interface_ref).ports
        preflight = _preflight(case, interface_ref, _context(case), steps=(0,))
        assert len(preflight.obligation_refs) == 1
        invocation = preflight.invocation
        selected = SelectedProgramGraphInputBasis(
            context=invocation.context,
            program_graph_ref=invocation.program_graph_ref,
            exec_plan_ref=invocation.exec_plan_ref,
            registry_bundle_ref=invocation.registry_bundle_ref,
            input_bindings_ref=invocation.input_bindings_ref,
            steps=(0,),
        )
        routes: list[ModelInputRoutingResult] = []

        def route_source(authority: CanonicalAcquisitionAuthority) -> None:
            routes.append(
                plan_selected_model_input_routing(
                    case.store,
                    obligation_set_ref=preflight.obligation_set_ref,
                    selected_basis=selected,
                    catalog_authority=authority,
                )
            )

        with _activated_fund(
            tmp_path / "benefit-fund",
            store=case.store,
            port=port,
            fund="public-benefit-fund",
            before_activation=route_source,
        ) as active:
            routing = routes.pop()
            (route,) = routing.report.routes
            assert route.disposition == "resolved"
            assert route.source_descriptor is not None
            assert route.source_descriptor.source_semantic_definition_ref == (
                port.semantic_definition_ref
            )
            selected_snapshot = _bind_activated_fund(
                case,
                active=active,
                routing=routing,
                preflight=preflight,
                source_port=port,
                workspace=tmp_path / "benefit-fund-snapshot",
            )

        foreign_port = _fund_port(case.store, port, fund="transit-fund")
        assert foreign_port.binding_profile_ref == port.binding_profile_ref
        assert foreign_port.semantic_definition_ref != port.semantic_definition_ref
        refused_workspace = tmp_path / "refused-transit-fund-snapshot"
        with _activated_fund(
            tmp_path / "transit-fund",
            store=case.store,
            port=foreign_port,
            fund="transit-fund",
            before_activation=route_source,
        ) as foreign:
            routing = routes.pop()
            (route,) = routing.report.routes
            assert route.reason_code == "model_input_source_descriptor_unresolved"
            with pytest.raises(
                DataStateSubstrateError, match="same_definition_profile_requires_exact_definition"
            ):
                _bind_activated_fund(
                    case,
                    active=foreign,
                    routing=routing,
                    preflight=preflight,
                    source_port=foreign_port,
                    workspace=refused_workspace,
                )
        assert not refused_workspace.exists()

        selected_bindings = selected_snapshot.semantic_foundry_input_bindings_ref
        assert selected_bindings is not None
        execution = execute_foundry(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=selected_bindings,
                return_selected_profile=True,
            ),
        )
        assert execution.ok and execution.simulation_result_ref is not None
        assert "semantic_input_use:candidate_simulation_input_only" in execution.notes
        assert "semantic_input_limitation:source_currentness_not_established" in execution.notes
        fresh = FileSystemCAS(case.store_root)
        admitted = admit_execution_source(fresh, execution.simulation_result_ref)
        assert admitted.basis is not None
        assert admitted.basis.input_bindings_ref == selected_bindings
        bindings = load_input_bindings(fresh, selected_bindings)
        assert bindings.resolved_binding_manifest_ref is not None
        assert bindings.data_snapshot_ref == selected_snapshot.data_snapshot_ref
        initial = load_state_snapshot(fresh, snapshot_ref=bindings.bound_state_snapshot_ref)
        assert float(initial.government_balance) == 640
        assert admitted.simulation_result.state_snapshot_ref is not None
        final = load_state_snapshot(
            fresh, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        assert float(final.government_balance) == 640 - (100 + 200) / 8
    finally:
        case.close()


@pytest.mark.integration
def test_activated_fund_selects_repeatable_stock_rows_from_separate_owner_occurrences(
    tmp_path: Path,
) -> None:
    """Same source row semantics retain the stock profile while changed cash is distinct."""
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        model_input_port_declaration_builder=_treasury_stock_declaration,
        snapshot_id="held-out-fund-source-repeatability",
    )
    try:
        interface_ref = _interface(case)
        (port,) = load_program_graph_input_interface(case.store, interface_ref).ports
        preflight = _preflight(case, interface_ref, _context(case), steps=(0,))
        invocation = preflight.invocation
        selected = SelectedProgramGraphInputBasis(
            context=invocation.context,
            program_graph_ref=invocation.program_graph_ref,
            exec_plan_ref=invocation.exec_plan_ref,
            registry_bundle_ref=invocation.registry_bundle_ref,
            input_bindings_ref=invocation.input_bindings_ref,
            steps=(0,),
        )
        routes: list[ModelInputRoutingResult] = []
        fixture_custodian = NativeEpochFixtureCustodian.create(
            case.store,
            tmp_path / "native-epoch-owner",
        )

        def route_source(authority: CanonicalAcquisitionAuthority) -> None:
            routes.append(
                plan_selected_model_input_routing(
                    case.store,
                    obligation_set_ref=preflight.obligation_set_ref,
                    selected_basis=selected,
                    catalog_authority=authority,
                )
            )

        values = (640, 640, 602.5)
        observations = []
        projections = []
        passports = []
        snapshots = []
        for occurrence, value in enumerate(values, start=1):
            with _activated_fund(
                tmp_path / f"fund-occurrence-{occurrence}",
                store=case.store,
                port=port,
                fund="treasury",
                opening_cash_usd=value,
                fixture_custodian=fixture_custodian,
                before_activation=route_source,
            ) as active:
                routing = routes.pop()
                (route,) = routing.report.routes
                assert route.disposition == "resolved"
                assert route.source_descriptor is not None
                assert route.source_descriptor.source_semantic_definition_ref == (
                    port.semantic_definition_ref
                )
                assert route.source_descriptor.source_representation_ref == port.representation_ref
                assert route.source_descriptor.binding_profile_ref == port.binding_profile_ref

                (entry,) = active.entries
                projection = active.projections[entry.target_variable]
                (row,) = projection.observations
                passport = AdmissionPassport.model_validate(
                    load_verified_epoch_statement(
                        store=case.store,
                        ref=projection.passport_ref,
                        expected_kind="epoch.acquisition_passport_snapshot",
                    )
                )
                representation = validate_core_model_json_artifact(
                    VariableRepresentation,
                    case.store,
                    port.representation_ref,
                )
                assert representation.quantity_kind == "stock"
                assert representation.measure_form == "absolute"
                assert representation.unit_id == "usd"
                assert representation.scale_to_unit == 1
                assert representation.time_support == "state_start"
                assert representation.temporal_granularity == "annual"
                assert representation.population_ref == port.scope.population_ref
                assert row.observation.year == 2022
                assert row.observation.value == value

                snapshot = _bind_activated_fund(
                    case,
                    active=active,
                    routing=routing,
                    preflight=preflight,
                    source_port=port,
                    workspace=tmp_path / f"fund-occurrence-{occurrence}-snapshot",
                    expected_opening_cash_usd=value,
                )
                assert snapshot.selected_observation_id == row.observation.observation_id
                assert snapshot.semantic_foundry_input_bindings_ref is not None
                observations.append(row)
                projections.append(projection)
                passports.append(passport)
                snapshots.append(snapshot)
        assert not routes

        first, repeat, changed = observations
        assert first.observation.model_dump(
            mode="json",
            exclude={"observation_id", "dataset_version"},
        ) == (
            repeat.observation.model_dump(
                mode="json",
                exclude={"observation_id", "dataset_version"},
            )
        )
        assert changed.observation.value == 602.5
        assert changed.observation.observation_id != first.observation.observation_id
        assert changed.row_content_sha256 != first.row_content_sha256

        first_passport, repeat_passport, changed_passport = passports
        assert first_passport.source_watermark == repeat_passport.source_watermark
        assert first_passport.dataset_version != repeat_passport.dataset_version
        assert changed_passport.source_watermark != first_passport.source_watermark
        assert first_passport.raw_artifact_id == repeat_passport.raw_artifact_id
        assert changed_passport.raw_artifact_id != first_passport.raw_artifact_id
        assert first_passport.raw_evidence_ref != repeat_passport.raw_evidence_ref
        assert len({passport.passport_id for passport in passports}) == len(values)
        assert len({str(projection.receipt_ref.artifact_id) for projection in projections}) == len(
            values
        )
        assert snapshots[0].selected_observation_id != snapshots[2].selected_observation_id
    finally:
        case.close()
