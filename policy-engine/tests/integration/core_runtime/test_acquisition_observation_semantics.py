"""Real preparation/materialization/replay checks for candidate observation semantics."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, load_core_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    FoundryInputBindings,
    SemanticHorizonStepContext,
)
from polisyos.core.contracts.model_input_requirements import (
    load_model_input_obligation_set,
    load_program_graph_input_interface,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedInputBindingManifest,
    ResolvedMeasurementInput,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from polisyos.data_forge import read_api
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    load_input_bindings,
    reconcile_semantic_input_bindings,
)
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.runtime.quality import data_state_substrate as owner
from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
from polisyos.runtime.quality.data_snapshot_lineage import (
    DataSnapshotLineageError,
    validate_data_snapshot_owner_lineage,
)
from tests._helpers import semantic_epoch_native as native_fixture
from tests._helpers import world_model_record as world_fixture
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests.unit.foundry.runtime.test_execute_input_bindings import (
    _stock_declaration_in_source_scope,
)
from tests.unit.runtime.quality.test_acquisition_executor import _activate_real_epoch_scenario
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context,
    _interface,
    _preflight,
    _supplied_rate,
)


def _case(
    root: Path, *, epoch_id: int = 1, fixture_source: SimpleNamespace | None = None
) -> SimpleNamespace:
    scenario = native_fixture._real_epoch_scenario(
        root, epoch_id=epoch_id, fixture_source=fixture_source
    )
    _, activated = _activate_real_epoch_scenario(scenario)
    projection = scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
    )
    selected = projection.observations[0].observation
    args = {
        "base_data_snapshot_ref": world_fixture._data_snapshot_ref(scenario.store),
        "overlay": scenario.overlay,
        "receipt_ref": activated.receipt_ref,
        "passport": scenario.passport,
        "authority": scenario.authority,
        "observation_id": selected.observation_id,
        "slot_binding": owner.ControlledAcquisitionSlotBinding(
            profile_selection_ref="sha256:" + "7" * 64,
            canonical_variable_id=selected.canonical_var,
            target_slot_id="government.balance",
        ),
        "transaction_time": datetime(2026, 10, 2, 12, tzinfo=UTC),
    }
    prepared = owner.prepare_acquired_observation_snapshot(scenario.store, **args)
    return SimpleNamespace(
        scenario=scenario, args=args, prepared=prepared, workspace=root / "materialized"
    )


def test_real_preparation_and_fresh_selected_snapshot_replay_use_one_semantic_projection(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    prepared_values = owner.prepare_acquired_observation_semantic_values(case.prepared)
    issued = owner.materialize_acquired_observation_snapshot(
        case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    fresh_store = FileSystemCAS(case.scenario.store.root)
    replayed = owner.read_acquired_observation_semantic_values(
        fresh_store, issued.data_snapshot_ref
    )
    assert replayed == prepared_values
    expected_rule = owner.read_acquired_observation_binding_rule(
        fresh_store, issued.data_snapshot_ref
    )
    assert expected_rule == issued.foundry_binding_rule
    assert owner.acquired_observation_binding_rule_values(
        case.prepared
    ) == expected_rule.model_dump(mode="json", exclude={"notes"})
    row = case.prepared.observation_projection.observations[0].observation
    semantic_row = replayed["observation"]
    assert isinstance(semantic_row, dict)
    wire_row = row.model_dump(mode="json")
    assert semantic_row == {
        name: wire_row.get(name) for name in type(row).model_fields if name != "observation_id"
    }
    assert replayed["selected_row_count"] == 1
    assert "source_watermark" in semantic_row
    assert "dataset_version" in semantic_row
    assert "condition_json" in semantic_row


def test_real_new_epoch_with_only_occurrence_id_change_has_equal_semantic_values(
    tmp_path: Path,
) -> None:
    previous = _case(tmp_path / "previous", epoch_id=1)
    current = _case(tmp_path / "current", epoch_id=2, fixture_source=previous.scenario)
    assert current.scenario.store is previous.scenario.store
    assert current.scenario.authority is previous.scenario.authority
    assert current.scenario.raw_ref == previous.scenario.raw_ref
    assert current.scenario.passport.registration == previous.scenario.passport.registration
    assert current.scenario.passport.source_watermark == previous.scenario.passport.source_watermark
    assert current.scenario.passport.dataset_version == previous.scenario.passport.dataset_version
    assert previous.prepared.selected_observation_id != current.prepared.selected_observation_id
    assert previous.prepared.foundry_binding_rule != current.prepared.foundry_binding_rule
    previous_row = previous.prepared.observation_projection.observations[0].observation
    current_row = current.prepared.observation_projection.observations[0].observation
    assert previous_row.model_dump(mode="json", exclude={"observation_id"}) == (
        current_row.model_dump(mode="json", exclude={"observation_id"})
    )
    assert owner.prepare_acquired_observation_semantic_values(previous.prepared) == (
        owner.prepare_acquired_observation_semantic_values(current.prepared)
    )
    # The full occurrence reports remain untouched even when effective rules agree.
    assert (
        previous.prepared.payload()["_policyos_acquisition_history"]
        != (current.prepared.payload()["_policyos_acquisition_history"])
    )


@pytest.mark.parametrize(
    "change",
    [
        {"country_code": "PL"},
        {"year": 2023},
        {"survey_year": 2023},
        {"wave": 2},
        {"condition_json": {"population": "other"}},
    ],
)
def test_real_same_value_changed_source_coordinates_change_semantic_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    original = native_fixture._fixture
    rows = [{"country_code": "UA", "year": 2024, "distress_score": 0.42}]
    with monkeypatch.context() as scoped:
        scoped.setattr(native_fixture, "_fixture", partial(original, rows=rows, source_rows=rows))
        previous = _case(tmp_path / "previous")
    changed_rows = [{**rows[0], **change}]
    with monkeypatch.context() as scoped:
        scoped.setattr(
            native_fixture,
            "_fixture",
            partial(original, rows=changed_rows, source_rows=changed_rows),
        )
        current = _case(tmp_path / "current")
    before = owner.prepare_acquired_observation_semantic_values(previous.prepared)
    after = owner.prepare_acquired_observation_semantic_values(current.prepared)
    before_row, after_row = before["observation"], after["observation"]
    assert isinstance(before_row, dict) and isinstance(after_row, dict)
    assert before_row["value"] == after_row["value"]
    assert before != after


def test_duplicate_selected_source_multiplicity_is_refused_by_real_canonical_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = native_fixture._fixture
    repeated = [{"country_code": "UA", "year": 2024, "distress_score": 0.42}] * 2
    with monkeypatch.context() as scoped:
        scoped.setattr(
            native_fixture, "_fixture", partial(original, rows=repeated, source_rows=repeated)
        )
        # The canonical overlay refuses the duplicate at admission, before the
        # substrate preparation is entered; this is not a downstream refusal.
        with pytest.raises(
            read_api.catalog.OverlayAdmissionError, match="identity_aggregation_not_unique"
        ):
            _case(tmp_path)


def test_rule_projection_refuses_extra_notes_before_excluding_generated_report_field(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    rule = case.prepared.foundry_binding_rule.model_copy(
        update={
            "notes": [*case.prepared.foundry_binding_rule.notes, "pretend_semantic_override"],
        }
    )
    changed = replace(case.prepared, foundry_binding_rule=rule)
    changed = replace(
        changed,
        preparation_sha256=owner._acquisition_preparation_sha256(changed, include_digest=False),
    )
    with pytest.raises(owner.DataStateSubstrateError, match="full_binding_rule_mismatch"):
        owner.acquired_observation_binding_rule_values(changed)


def test_reader_refuses_wrong_or_opaque_selected_snapshot_source(tmp_path: Path) -> None:
    case = _case(tmp_path)
    opaque = case.scenario.store.put_bytes(
        b"opaque source",
        PutOptions(kind="foreign.opaque", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    with pytest.raises((owner.DataStateSubstrateError, ValueError)):
        owner.read_acquired_observation_semantic_values(case.scenario.store, opaque)
    without_profile = case.args["base_data_snapshot_ref"].model_copy(
        update={"manifest_profile_sha256": None}
    )
    with pytest.raises(owner.DataStateSubstrateError, match="profile_unselected"):
        owner.read_acquired_observation_semantic_values(case.scenario.store, without_profile)


def test_public_parser_is_the_actual_data_forge_owner_function() -> None:
    from polisyos.data_forge.domains.catalog.knowledge.overlay import derive_canonical_observations

    assert read_api.catalog.derive_canonical_observations is derive_canonical_observations


def test_unknown_valid_time_survives_actual_acquired_snapshot_writer(tmp_path: Path) -> None:
    from polisyos.fabric.world.store.snapshots import resolve_world_snapshot

    root = owner._write_acquired_candidate_fabric_snapshot(
        workspace_dir=tmp_path,
        snapshot_id="unknown-valid-time",
        payload_hash="sha256:" + "a" * 64,
        transaction_time="2026-10-29T12:00:00+00:00",
        as_of_valid_time=None,
    )
    snapshot = resolve_world_snapshot(root, snapshot_id="unknown-valid-time")
    assert snapshot.as_of_valid_time is None
    assert snapshot.as_of_tx_time == "2026-10-29T12:00:00+00:00"


def test_candidate_world_keeps_unknown_base_valid_time_through_actual_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.fabric.world.store.snapshots import resolve_world_snapshot
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry

    case = _case(tmp_path / "source")
    # Reuse this real CAS, not an owner-result substitute, for the base fixture.
    monkeypatch.setattr(world_fixture, "FileSystemCAS", lambda _path: case.scenario.store)
    original_ref = world_fixture._fabric_ref
    monkeypatch.setattr(world_fixture, "_fabric_ref", partial(original_ref, as_of_valid_time=None))
    store, base, _model, _registry = world_fixture._build_record(tmp_path / "base")
    assert base.record.fabric_world_ref.as_of_valid_time is None
    issued = owner.materialize_acquired_observation_snapshot(
        store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    substrate = world_fixture._substrate_registry()
    substrate_ref = persist_substrate_registry(store, substrate)
    built = owner.build_acquired_observation_candidate_world(
        store,
        base_world_model=base.record,
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        materialization=issued,
        workspace_dir=tmp_path / "world",
        transaction_time=case.args["transaction_time"],
    )
    assert built.world_model.record.fabric_world_ref.as_of_valid_time is None
    snapshot = resolve_world_snapshot(
        Path(built.world_model.record.fabric_world_ref.snapshot_root),
        snapshot_id=built.world_model.record.fabric_world_ref.snapshot_id,
    )
    assert snapshot.as_of_valid_time is None
    assert snapshot.as_of_tx_time is not None


def test_actual_materializer_consumes_the_shared_semantic_reconciler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path)

    def refuse(_prepared: owner.AcquiredObservationDataPreparation) -> dict[str, object]:
        raise owner.DataStateSubstrateError("test_semantic_reconciler_removed_control")

    monkeypatch.setattr(owner, "prepare_acquired_observation_semantic_values", refuse)
    with pytest.raises(
        owner.DataStateSubstrateError, match="test_semantic_reconciler_removed_control"
    ):
        owner.materialize_acquired_observation_snapshot(
            case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
        )
    assert not case.workspace.exists()


def test_historical_reader_refuses_opaque_bytes_in_the_actual_selected_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts import ArtifactRef

    case = _case(tmp_path)
    issued = owner.materialize_acquired_observation_snapshot(
        case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    expected = owner.prepare_acquired_observation_semantic_values(case.prepared)
    assert (
        owner.read_acquired_observation_semantic_values(
            FileSystemCAS(case.scenario.store.root), issued.data_snapshot_ref
        )
        == expected
    )
    source_id = case.scenario.candidate.statement.source_record_ref.artifact_id
    original = FileSystemCAS.get_bytes
    denied: list[str] = []

    def corrupted_read(store: FileSystemCAS, selected: object) -> bytes:
        identity = selected.artifact_id if isinstance(selected, ArtifactRef) else selected
        if str(identity) == str(source_id):
            denied.append(str(identity))
            return b"opaque bytes instead of the selected canonical source"
        return original(store, selected)

    # Keep every real persisted blob and receipt; remove only the source read relation.
    assert case.scenario.store.has(source_id)
    monkeypatch.setattr(FileSystemCAS, "get_bytes", corrupted_read)
    with pytest.raises(
        owner.DataStateSubstrateError, match="acquisition_semantic_source_unverified"
    ):
        owner.read_acquired_observation_semantic_values(
            FileSystemCAS(case.scenario.store.root), issued.data_snapshot_ref
        )
    assert denied and set(denied) == {str(source_id)}


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("dataset_id", "other-dataset"),
        ("dataset_version", "other-version"),
        ("raw_variable", "other-field"),
        ("country_code", "PL"),
        ("year", 2023),
        ("survey_year", 2023),
        ("wave", 2),
        ("condition_json", '{"population":"other"}'),
        ("acquisition_method", "other-method"),
        ("observation_class", "proxy"),
    ],
)
def test_each_coordinate_is_decisive_even_when_scalar_and_watermark_are_held_fixed(
    tmp_path: Path, field: str, changed_value: object
) -> None:
    """Exercise the shared pure projector, without issuing a counterfactual admission."""
    case = _case(tmp_path)
    selected = case.prepared.observation_projection.observations[0].observation
    changed = type(selected).model_validate(
        {**selected.model_dump(mode="json"), field: changed_value}
    )
    arguments = {
        "slot_binding": case.prepared.selected_profile,
        "projection_row_count": len(case.prepared.observation_projection.observations),
    }
    before = owner._acquired_observation_semantic_values(observation=selected, **arguments)
    after = owner._acquired_observation_semantic_values(observation=changed, **arguments)
    before_row, after_row = before["observation"], after["observation"]
    assert isinstance(before_row, dict) and isinstance(after_row, dict)
    assert before_row["value"] == after_row["value"]
    assert before_row["source_watermark"] == after_row["source_watermark"]
    assert before_row[field] != after_row[field]
    assert before != after


def test_activated_same_definition_selection_is_bound_to_fresh_foundry_input(
    tmp_path: Path,
) -> None:
    """Bind the real activated row through its selected snapshot and Foundry reader."""
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        model_input_port_declaration_builder=_stock_declaration_in_source_scope,
        snapshot_id="base-acquisition",
    )
    activated_owner = None
    fresh_store = None
    try:
        store = case.store
        interface_ref = _interface(case)
        interface = load_program_graph_input_interface(store, interface_ref)
        (port,) = interface.ports
        override_ref = _supplied_rate(case)
        preflight = _preflight(
            case,
            interface_ref,
            _context(case),
            steps=(0,),
            parameter_override_bundle_ref=override_ref,
        )

        variable_id = "test.treasury.opening-stock"
        activated_owner = native_fixture.make_native_multivariable_active_projections(
            tmp_path / "activated-source",
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
        projection = activated_owner.projections[variable_id]
        (row,) = projection.observations
        passport = AdmissionPassport.model_validate(
            load_verified_epoch_statement(
                store=store,
                ref=projection.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        slot_binding = owner.ControlledAcquisitionSlotBinding(
            profile_selection_ref="sha256:" + "7" * 64,
            canonical_variable_id=variable_id,
            target_slot_id=port.slot_id,
        )
        binding_rule = owner.acquired_observation_binding_rule(
            observation=row.observation, slot_binding=slot_binding
        )
        request = owner.AcquiredObservationSemanticInputRequest(
            binding_id=binding_rule.binding_id,
            source_definition_ref=port.semantic_definition_ref,
            source_representation_ref=port.representation_ref,
            model_interface_ref=SelectedVariableBindingRef.model_validate(
                interface_ref.model_dump(mode="json")
            ),
            model_port_id=port.port_id,
        )
        workspace_dir = tmp_path / "shared-data-forge-workspace"
        transaction_time = datetime(2026, 10, 2, 12, tzinfo=UTC)

        legacy = owner.materialize_acquired_observation_snapshot(
            store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            overlay=activated_owner.overlay,
            receipt_ref=projection.receipt_ref,
            passport=passport,
            authority=activated_owner.authority,
            observation_id=row.observation.observation_id,
            slot_binding=slot_binding,
            workspace_dir=workspace_dir,
            transaction_time=transaction_time,
        )
        legacy_binding_bytes = legacy.data_forge_snapshot_binding_path.read_bytes()
        semantic = owner.materialize_acquired_observation_snapshot(
            store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            overlay=activated_owner.overlay,
            receipt_ref=projection.receipt_ref,
            passport=passport,
            authority=activated_owner.authority,
            observation_id=row.observation.observation_id,
            slot_binding=slot_binding,
            workspace_dir=workspace_dir,
            transaction_time=transaction_time,
            semantic_input_request=request,
        )
        first_semantic_snapshot_bytes = semantic.data_forge_snapshot_binding_path.read_bytes()
        first_semantic_manifest = store.get_manifest(semantic.data_snapshot_ref)
        repeated_semantic = owner.materialize_acquired_observation_snapshot(
            store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            overlay=activated_owner.overlay,
            receipt_ref=projection.receipt_ref,
            passport=passport,
            authority=activated_owner.authority,
            observation_id=row.observation.observation_id,
            slot_binding=slot_binding,
            workspace_dir=workspace_dir,
            transaction_time=transaction_time + timedelta(days=1),
            semantic_input_request=request,
        )
        assert repeated_semantic.data_snapshot_ref != semantic.data_snapshot_ref
        assert repeated_semantic.data_forge_snapshot_binding_path != (
            semantic.data_forge_snapshot_binding_path
        )
        assert semantic.data_forge_snapshot_binding_path.read_bytes() == (
            first_semantic_snapshot_bytes
        )
        assert store.get_manifest(semantic.data_snapshot_ref) == first_semantic_manifest
        assert semantic.semantic_input_selection is not None
        assert legacy.data_forge_snapshot_binding_path != semantic.data_forge_snapshot_binding_path
        assert legacy.data_forge_snapshot_binding_path.read_bytes() == legacy_binding_bytes
        assert store.get_manifest(legacy.data_snapshot_ref).artifact_schema.version == "0.3.0"
        assert store.get_manifest(semantic.data_snapshot_ref).artifact_schema.version == "0.4.0"
        legacy_snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, legacy.data_snapshot_ref)
        )
        legacy_lineage_result = validate_data_snapshot_owner_lineage(
            store,
            legacy.data_snapshot_ref,
            legacy_snapshot,
            candidate_only=True,
        )
        assert legacy_lineage_result.acquisition_source_row_status == "not_established"
        semantic_snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, semantic.data_snapshot_ref)
        )

        wrong_schema_snapshot_ref = store.put_json(
            semantic_snapshot,
            PutOptions(
                kind=DataSnapshot.ARTIFACT_KIND,
                media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                    version="0.2.0",
                ),
                inputs=store.get_manifest(semantic.data_snapshot_ref).inputs,
            ),
            return_selected_profile=True,
        )
        with pytest.raises(
            ValueError,
            match=r"^DataSnapshot owner lineage version differs from its manifest schema$",
        ):
            build_input_bindings(
                store,
                data_snapshot_ref=wrong_schema_snapshot_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                rules=[semantic.foundry_binding_rule],
                return_selected_profile=True,
            )

        semantic_lineage_result = validate_data_snapshot_owner_lineage(
            store,
            semantic.data_snapshot_ref,
            semantic_snapshot,
            candidate_only=True,
        )
        assert semantic_lineage_result.acquisition_source_row_status == "not_established"
        assert semantic_lineage_result.required_admissibility_blockers

        with pytest.raises(
            ValueError,
            match=r"^foundry_input_bindings_semantic_manifest_required$",
        ):
            build_input_bindings(
                store,
                data_snapshot_ref=semantic.data_snapshot_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                rules=[semantic.foundry_binding_rule],
                return_selected_profile=True,
            )

        obligation_set, _ = load_model_input_obligation_set(store, preflight.obligation_set_ref)
        (obligation_ref,) = obligation_set.obligation_refs
        selection = semantic.semantic_input_selection
        measurement = ResolvedMeasurementInput(
            binding_id=selection.binding_id,
            model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
                obligation_ref.model_dump(mode="json")
            ),
            selected_occurrence_ref=selection.occurrence_ref,
            correspondence_ref=selection.correspondence_basis_ref,
            source_path=selection.source_path,
        )
        manifest = ResolvedInputBindingManifest(
            data_snapshot_ref=SelectedVariableBindingRef.model_validate(
                semantic.data_snapshot_ref.model_dump(mode="json")
            ),
            model_input_obligation_set_ref=SelectedVariableBindingRef.model_validate(
                preflight.obligation_set_ref.model_dump(mode="json")
            ),
            measurements=(measurement,),
            retained_binding_ids=("fixture-agents-income",),
        )
        manifest_ref = persist_resolved_input_binding_manifest(store, manifest)
        built = build_input_bindings(
            store,
            data_snapshot_ref=semantic.data_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            resolved_binding_manifest_ref=manifest_ref,
            return_selected_profile=True,
        )
        assert float(
            load_state_snapshot(store, snapshot_ref=built.bound_state_snapshot_ref).government_balance
        ) == 1000.0

        no_interface_case = prepare_program_graph_tax_subsidy_input_case(
            tmp_path / "legacy-binding-without-interface",
            opening_balance_usd=None,
            store=store,
        )
        legacy_bindings = load_input_bindings(store, no_interface_case.input_bindings_ref)
        assert reconcile_semantic_input_bindings(store, legacy_bindings) == ()
        legacy_bindings = legacy_bindings.model_copy(
            update={"data_snapshot_ref": semantic.data_snapshot_ref}
        )
        legacy_bindings_manifest = store.get_manifest(no_interface_case.input_bindings_ref)
        legacy_binding_edges = list(legacy_bindings_manifest.inputs)
        snapshot_edge = input_ref_from_artifact_ref(
            no_interface_case.data_snapshot_ref,
            role="input.data_snapshot_ref",
        )
        assert legacy_binding_edges.count(snapshot_edge) == 1
        legacy_binding_edges[legacy_binding_edges.index(snapshot_edge)] = input_ref_from_artifact_ref(
            semantic.data_snapshot_ref,
            role="input.data_snapshot_ref",
        )
        stored_legacy_bindings_ref = store.put_json(
            legacy_bindings,
            PutOptions(
                kind=FoundryInputBindings.ARTIFACT_KIND,
                media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                    version=legacy_bindings.schema_version,
                ),
                inputs=legacy_binding_edges,
            ),
            return_selected_profile=True,
        )
        stored_legacy_bindings = load_input_bindings(store, stored_legacy_bindings_ref)
        assert stored_legacy_bindings.resolved_binding_manifest_ref is None
        assert no_interface_case.model_input_port_declaration_ref is None
        with pytest.raises(
            ValueError,
            match=r"^foundry_input_bindings_semantic_manifest_required$",
        ):
            reconcile_semantic_input_bindings(store, stored_legacy_bindings)

        misversioned_legacy_bindings = load_input_bindings(
            store, no_interface_case.input_bindings_ref
        ).model_copy(update={"data_snapshot_ref": wrong_schema_snapshot_ref})
        misversioned_binding_edges = list(legacy_bindings_manifest.inputs)
        misversioned_binding_edges[misversioned_binding_edges.index(snapshot_edge)] = (
            input_ref_from_artifact_ref(
                wrong_schema_snapshot_ref,
                role="input.data_snapshot_ref",
            )
        )
        misversioned_legacy_bindings_ref = store.put_json(
            misversioned_legacy_bindings,
            PutOptions(
                kind=FoundryInputBindings.ARTIFACT_KIND,
                media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                    version=misversioned_legacy_bindings.schema_version,
                ),
                inputs=misversioned_binding_edges,
            ),
            return_selected_profile=True,
        )
        misversioned_legacy_bindings = load_input_bindings(
            store, misversioned_legacy_bindings_ref
        )
        assert misversioned_legacy_bindings.resolved_binding_manifest_ref is None
        with pytest.raises(
            ValueError,
            match=r"^DataSnapshot owner lineage version differs from its manifest schema$",
        ):
            reconcile_semantic_input_bindings(store, misversioned_legacy_bindings)

        wrong_manifest = persist_resolved_input_binding_manifest(
            store,
            manifest.model_copy(
                update={
                    "measurements": (
                        measurement.model_copy(
                            update={"source_path": "acquisition.selected.observation_id"}
                        ),
                    )
                }
            ),
        )
        with pytest.raises(
            ValueError,
            match=r"^foundry_input_bindings_semantic_snapshot_selection_mismatch$",
        ):
            build_input_bindings(
                store,
                data_snapshot_ref=semantic.data_snapshot_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                resolved_binding_manifest_ref=wrong_manifest,
                return_selected_profile=True,
            )

        semantic_snapshot_manifest = store.get_manifest(semantic.data_snapshot_ref)
        selected_edge = input_ref_from_artifact_ref(
            selection.occurrence_ref,
            role=f"binding.{selection.binding_id}.occurrence:{selection.source_path}",
        )
        wrong_edges = list(semantic_snapshot_manifest.inputs)
        selected_edge_index = wrong_edges.index(selected_edge)
        wrong_edges[selected_edge_index] = input_ref_from_artifact_ref(
            selection.occurrence_ref,
            role=f"binding.{selection.binding_id}.occurrence:other.path",
        )
        wrong_role_snapshot_ref = store.put_json(
            semantic_snapshot,
            PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.4.0"),
                inputs=wrong_edges,
            ),
            return_selected_profile=True,
        )
        with pytest.raises(
            DataSnapshotLineageError,
            match=r"^data_snapshot_owner_parent_inputs_mismatch$",
        ):
            validate_data_snapshot_owner_lineage(
                store,
                wrong_role_snapshot_ref,
                semantic_snapshot,
                candidate_only=True,
            )

        executed = execute_foundry(
            store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=built.input_bindings_ref,
                parameter_override_bundle_ref=override_ref,
                return_selected_profile=True,
            ),
        )
        assert executed.ok and executed.simulation_result_ref is not None
        assert "semantic_input_use:candidate_simulation_input_only" in executed.notes
        horizon_predecessor = SemanticHorizonStepContext(
            obligation_set_ref=preflight.obligation_set_ref,
            steps=(0, 1),
            step_index=1,
            replication_seed=0,
            previous_result_ref=executed.simulation_result_ref,
        )
        with pytest.raises(
            ValueError,
            match=r"^foundry_input_bindings_semantic_manifest_required$",
        ):
            reconcile_semantic_input_bindings(
                store,
                stored_legacy_bindings,
                semantic_horizon_step=horizon_predecessor,
            )
        with pytest.raises(
            ValueError,
            match=r"^DataSnapshot owner lineage version differs from its manifest schema$",
        ):
            reconcile_semantic_input_bindings(
                store,
                misversioned_legacy_bindings,
                semantic_horizon_step=horizon_predecessor,
            )
        fresh_store = FileSystemCAS(case.store_root)
        admitted = admit_execution_source(fresh_store, executed.simulation_result_ref)
        assert admitted.basis is not None
        assert admitted.basis.input_bindings_ref == built.input_bindings_ref
        assert load_input_bindings(
            fresh_store, built.input_bindings_ref
        ).resolved_binding_manifest_ref == manifest_ref
        assert admitted.simulation_result.state_snapshot_ref is not None
        final_state = load_state_snapshot(
            fresh_store, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        assert float(final_state.government_balance) == 1000.0 - 0.125 * (100 + 200)
    finally:
        if fresh_store is not None:
            close = getattr(fresh_store, "close", None)
            if callable(close):
                close()
        if activated_owner is not None:
            activated_owner.overlay.close()
        case.close()
