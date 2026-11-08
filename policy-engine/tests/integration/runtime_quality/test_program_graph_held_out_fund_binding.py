"""Enroll a distinct, test-owned cash stock into the existing Foundry profile."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.foundry import ExecuteRequest
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPortDeclaration,
    load_program_graph_input_interface,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.variable_binding import (
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
)
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.execute import admit_execution_source, load_state_snapshot
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
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
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


@contextmanager
def _activated_fund(
    tmp_path: Path,
    *,
    store: FileSystemCAS,
    port: ModelInputPort,
    fund: str,
    before_activation: Callable[[CanonicalAcquisitionAuthority], None],
) -> Iterator[SimpleNamespace]:
    active = make_native_multivariable_active_projections(
        tmp_path,
        source_rows=[
            {
                "country_code": "UA",
                "year": 2022,
                "opening_cash_usd": 640,
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
    assert row.observation.value == 640
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
