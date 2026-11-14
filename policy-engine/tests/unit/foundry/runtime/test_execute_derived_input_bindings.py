"""A declared aggregate income flow reaches actual Foundry and a fresh reader.

The fiscal-flow algebra is tested separately in Core. This consumer is the
existing income mechanism and makes no fiscal-flow-to-income or stock alias.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import load_core_json_artifact, validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    FoundryInputBindingRule,
    FoundryInputBindings,
)
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    load_model_input_obligation_set,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.semantic_derived_binding import (
    DerivedInputProfile,
    DerivedMeasurementRole,
    RatioDenominatorSourceContext,
    load_derived_input_correspondence,
    persist_derived_input_correspondence,
    persist_derived_input_profile,
    persist_ratio_denominator_source_context,
)
from polisyos.core.contracts.semantic_input_binding import (
    load_resolved_input_binding_manifest,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    ModelInputScope,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    SelectedVariableBindingRef,
    replay_scoped_measurement_occurrence,
    scoped_measurement_occurrence_manifest_inputs,
    scoped_source_selection_from_passport_mapping,
)
from polisyos.core.derivations import DerivationRefusalCode, DerivationRefusalError
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    load_input_bindings,
    reconcile_semantic_input_bindings,
)
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.ir.kernel.units import MoneyUnit
from polisyos.runtime.quality.model_input_routing import materialize_derived_model_input
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections
from tests.unit.core.contracts.test_semantic_derived_binding import (
    _arithmetic,
    _definition,
    _put_contract,
    _representation,
    _selected,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context,
    _interface,
    _preflight,
    _supplied_rate,
)


def _income_flow_declaration(store, metadata, *, shape=(1,)):
    """Declare one aggregate income community, with no change to slot meaning."""
    target_ref, _ = _definition(store, "aggregate-household-income-flow")
    ratio_ref, _ = _definition(store, "aggregate-household-income-gdp-ratio")
    denominator_ref, _ = _definition(store, "economy-gdp-flow")
    money = MoneyUnit(currency="USD", nominal_year=2024, price_base="current")
    representations = {
        "target": _representation(
            store, target_ref, population="population:aggregate-households", money=money
        ),
        "ratio": _representation(
            store,
            ratio_ref,
            population="population:aggregate-households",
            money=money,
            numerator_ref=target_ref,
            denominator_ref=denominator_ref,
        ),
        "denominator": _representation(
            store, denominator_ref, population="population:economy", money=money
        ),
    }
    profile = MeasurementBindingProfile(
        schema_version="polisyos.catalog.measurement_binding_profile.v3",
        profile_id="fixture.aggregate_income_flow",
        revision="1",
        required_axes=(
            MeasurementAxis.QUANTITY_KIND,
            MeasurementAxis.MEASURE_FORM,
            MeasurementAxis.UNIT_ID,
            MeasurementAxis.TIME_SUPPORT,
            MeasurementAxis.TEMPORAL_GRANULARITY,
            MeasurementAxis.AGGREGATION,
            MeasurementAxis.GRAIN,
            MeasurementAxis.POPULATION_REF,
            MeasurementAxis.MONEY_UNIT,
        ),
    )
    profile_ref = MeasurementBindingProfileRef.model_validate(
        _put_contract(store, profile, version="3.0").model_dump()
    )
    port = ModelInputPort(
        port_id="aggregate-household-income-flow",
        slot_id="agents.income",
        state_path="agents.income",
        unit_id="usd",
        purpose="simulation_input",
        semantic_definition_ref=target_ref,
        representation_ref=representations["target"][0],
        binding_profile_ref=profile_ref,
        scope=ModelInputScope(
            population_ref="population:aggregate-households",
            geography_ref="UA",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
        physical_encoding=ModelInputPhysicalEncoding(
            shape=shape, dtype="float32", max_absolute_error=Decimal("0")
        ),
    )
    metadata.update(
        target_ref=target_ref,
        ratio_ref=ratio_ref,
        denominator_ref=denominator_ref,
        representations=representations,
        money=money,
        port=port,
    )
    return persist_model_input_port_declaration(store, ModelInputPortDeclaration(ports=(port,)))


def _one_aggregate_income_case(tmp_path: Path, *, shape=(1,)):
    metadata = {}
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=1000,
        model_input_port_declaration_builder=lambda store: _income_flow_declaration(
            store, metadata, shape=shape
        ),
    )
    # The compiled source declares the aggregate community. Its predecessor has
    # no income writer, so the real graph preflight must produce that obligation.
    source = case.store.put_json(
        {"agents": {"income": [0]}, "government_balance": 1000},
        PutOptions(kind="fixture.aggregate_income_context", media_type="application/json"),
        return_selected_profile=True,
    )
    snapshot = DataSnapshot(data_ref=source, notes=["One synthetic aggregate income community."])
    snapshot_ref = case.store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(source, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    predecessor = build_input_bindings(
        case.store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        rules=[
            FoundryInputBindingRule(
                binding_id="opening-stock",
                source_path="government_balance",
                target_slot_id="government.balance",
            )
        ],
        return_selected_profile=True,
    )
    case = replace(
        case,
        source_ref=source,
        data_snapshot_ref=snapshot_ref,
        input_bindings_ref=predecessor.input_bindings_ref,
        bound_state_snapshot_ref=predecessor.bound_state_snapshot_ref,
    )
    return case, metadata


def _replay_native_role(store, owner, variable_id: str, *, role: str, arithmetic, metadata):
    projection = owner.projections[variable_id]
    (row,) = projection.observations
    passport = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=projection.passport_ref,
        expected_kind="epoch.acquisition_passport_snapshot",
    )
    boundary_ref = _selected(
        store, ArtifactRef.model_validate(passport["semantic_boundary_candidate_ref"])
    )
    boundary = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=boundary_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
    )
    source = scoped_source_selection_from_passport_mapping(
        passport,
        source_receipt_ref=_selected(store, projection.receipt_ref),
        source_passport_ref=_selected(store, projection.passport_ref),
        source_boundary_candidate_ref=boundary_ref,
        source_record_ref=_selected(store, boundary.source_record_ref),
    )
    occurrence = replay_scoped_measurement_occurrence(
        catalog_read_api.read_scoped_measurement_source_body(
            store, passport_mapping=passport, source_selection=source
        ),
        observation_id=row.observation.observation_id,
        source_selection=source,
        unit_transform_evidence=None,
    )
    occurrence_ref = ScopedMeasurementOccurrenceRef.model_validate(
        _put_contract(
            store, occurrence, inputs=scoped_measurement_occurrence_manifest_inputs(occurrence)
        ).model_dump()
    )
    return DerivedMeasurementRole(
        role=role,
        source_series_ref=arithmetic.source_refs[role],
        occurrence_ref=occurrence_ref,
        definition_ref=metadata[f"{role}_ref"],
        representation_ref=metadata["representations"][role][0],
    )


def test_declared_derived_income_flow_reaches_actual_step_and_fresh_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, metadata = _one_aggregate_income_case(tmp_path)
    owner = None
    try:
        store = case.store
        interface_ref = _interface(case)
        override_ref = _supplied_rate(case)
        preflight = _preflight(
            case,
            interface_ref,
            _context(case),
            steps=(0,),
            parameter_override_bundle_ref=override_ref,
        )
        selected_set, (obligation,) = load_model_input_obligation_set(
            store, preflight.obligation_set_ref
        )
        (obligation_ref,) = selected_set.obligation_refs
        assert obligation.port.slot_id == "agents.income"
        assert selected_set.supplied_initial_slots == ("government.balance",)
        arithmetic = _arithmetic(
            store,
            ratio_id="fixture.aggregate-household-income-gdp-ratio",
            denominator_id="fixture.economy-gdp-flow",
            target_id="fixture.aggregate-household-income-flow",
        )
        specs = []
        for role, raw_field, population, unit, minimum, maximum in (
            ("ratio", "income_gdp_ratio", "population:aggregate-households", "ratio", -1, 1),
            ("denominator", "gdp_usd", "population:economy", "usd", 0, 300_000_000_000),
        ):
            definition_id = (
                "fixture.aggregate-household-income-gdp-ratio"
                if role == "ratio"
                else "fixture.economy-gdp-flow"
            )
            specs.append(
                {
                    "target_variable": definition_id,
                    "raw_field": raw_field,
                    "raw_unit": unit,
                    "canonical_unit": unit,
                    "unit_transform_ref": f"fabric://units/{unit}-identity/v1",
                    "valid_min": minimum,
                    "valid_max": maximum,
                    "source_measure_scope": {
                        "population": population,
                        "temporal_granularity": "annual",
                        "jurisdiction_ref": "jurisdiction:fixture",
                        "time_period_basis": "calendar_year",
                        "source_geography_id": "UA",
                        "geography_ref": "UA",
                    },
                    "source_semantic_definition_ref": metadata[f"{role}_ref"],
                    "source_representation_ref": metadata["representations"][role][0],
                }
            )
        owner = make_native_multivariable_active_projections(
            tmp_path / "sources",
            source_rows=[
                {
                    "country_code": "UA",
                    "year": 2024,
                    "income_gdp_ratio": -0.03,
                    "gdp_usd": 200_000_000_000,
                    "condition_json": {},
                }
            ],
            variable_specs=tuple(specs),
            artifact_store=store,
            return_selected_raw_profile=True,
        )
        ratio = _replay_native_role(
            store,
            owner,
            "fixture.aggregate-household-income-gdp-ratio",
            role="ratio",
            arithmetic=arithmetic,
            metadata=metadata,
        )
        denominator = _replay_native_role(
            store,
            owner,
            "fixture.economy-gdp-flow",
            role="denominator",
            arithmetic=arithmetic,
            metadata=metadata,
        )
        source_context_ref = persist_ratio_denominator_source_context(
            store,
            RatioDenominatorSourceContext(
                scope_note="Fixture-owned annual aggregate household income/GDP context. No external empirical claim.",
                ratio_occurrence_ref=ratio.occurrence_ref,
                ratio_definition_ref=ratio.definition_ref,
                ratio_representation_ref=ratio.representation_ref,
                denominator_occurrence_ref=denominator.occurrence_ref,
                denominator_definition_ref=denominator.definition_ref,
                denominator_representation_ref=denominator.representation_ref,
                money_unit=metadata["money"],
            ),
        )
        profile_ref = persist_derived_input_profile(
            store, DerivedInputProfile(output_projection="singleton_vector")
        )
        materialized = materialize_derived_model_input(
            store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=preflight.obligation_set_ref,
            model_input_obligation_ref=obligation_ref,
            profile_ref=profile_ref,
            source_context_ref=source_context_ref,
            recipe_ref=arithmetic.recipe_ref,
            certificate_ref=arithmetic.materialized.certificate_artifact_ref,
            output_ref=arithmetic.materialized.derived_artifact_ref,
            roles=(denominator, ratio),
            year=2024,
            binding_id="income-derived",
        )
        request = ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=materialized.input_bindings_ref,
            parameter_override_bundle_ref=override_ref,
            return_selected_profile=True,
        )
        bound = load_input_bindings(store, materialized.input_bindings_ref)
        bound_state = load_state_snapshot(store, snapshot_ref=bound.bound_state_snapshot_ref)
        assert tuple(float(value) for value in bound_state.agents.income) == (-6_000_000_000.0,)
        executed = execute_foundry(store, request)
        assert executed.ok and executed.simulation_result_ref is not None
        fresh = FileSystemCAS(case.store_root)
        admitted = admit_execution_source(fresh, executed.simulation_result_ref)
        assert admitted.semantic_input_limitation_codes is not None
        assert (
            "external_empirical_context_not_established" in admitted.semantic_input_limitation_codes
        )
        assert "derivation_uncertainty_not_established" in admitted.semantic_input_limitation_codes
        assert "n7_derivation_bundle_not_established" in admitted.semantic_input_limitation_codes
        assert admitted.simulation_result.state_snapshot_ref is not None
        final_state = load_state_snapshot(
            fresh, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        # Independent literal: a 1/8 subsidy on -6B is -750M, deducted from 1000.
        assert float(final_state.government_balance) == pytest.approx(750_001_000, abs=64)
        assert float(final_state.agents.income[0]) == pytest.approx(-6_750_000_000, abs=512)

        original_recipe_bytes = fresh.get_bytes

        def missing_recipe(ref, *args, **kwargs):
            if getattr(ref, "artifact_id", None) == arithmetic.recipe_ref.artifact_id:
                raise FileNotFoundError("exact persisted recipe removed")
            return original_recipe_bytes(ref, *args, **kwargs)

        def corrupt_recipe(ref, *args, **kwargs):
            if getattr(ref, "artifact_id", None) == arithmetic.recipe_ref.artifact_id:
                return b"{}"
            return original_recipe_bytes(ref, *args, **kwargs)

        for control in (missing_recipe, corrupt_recipe):
            with monkeypatch.context() as patch:
                patch.setattr(fresh, "get_bytes", control)
                with pytest.raises(
                    ValueError, match=r"^foundry_input_bindings_derived_recipe_unavailable$"
                ):
                    admit_execution_source(fresh, executed.simulation_result_ref)
            assert (
                admit_execution_source(fresh, executed.simulation_result_ref).basis
                == admitted.basis
            )

        def missing_denominator(ref, *args, **kwargs):
            if getattr(ref, "artifact_id", None) == denominator.source_series_ref.artifact_id:
                raise FileNotFoundError("selected AND denominator input removed")
            return original_recipe_bytes(ref, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(fresh, "get_bytes", missing_denominator)
            with pytest.raises(DerivationRefusalError) as missing_input:
                admit_execution_source(fresh, executed.simulation_result_ref)
            assert missing_input.value.code == DerivationRefusalCode.CERTIFICATE_DRIFT
        assert admit_execution_source(fresh, executed.simulation_result_ref).basis == admitted.basis
        with pytest.raises(ValidationError) as partial_roles:
            materialize_derived_model_input(
                store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=preflight.obligation_set_ref,
                model_input_obligation_ref=obligation_ref,
                profile_ref=profile_ref,
                source_context_ref=source_context_ref,
                recipe_ref=arithmetic.recipe_ref,
                certificate_ref=arithmetic.materialized.certificate_artifact_ref,
                output_ref=arithmetic.materialized.derived_artifact_ref,
                roles=(ratio,),
                year=2024,
                binding_id="income-derived",
            )
        assert any(
            error["loc"] == ("roles",) and error["type"] == "too_short"
            for error in partial_roles.value.errors()
        )
        assert admit_execution_source(fresh, executed.simulation_result_ref).basis == admitted.basis

        wrong_year = _arithmetic(
            store,
            ratio_id="fixture.aggregate-household-income-gdp-ratio",
            denominator_id="fixture.economy-gdp-flow",
            target_id="fixture.aggregate-household-income-flow",
            year=2023,
        )
        with pytest.raises(
            ValueError,
            match="foundry_input_bindings_derived_correspondence_refused:.*denominator_series_point_mismatch",
        ):
            materialize_derived_model_input(
                store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=preflight.obligation_set_ref,
                model_input_obligation_ref=obligation_ref,
                profile_ref=profile_ref,
                source_context_ref=source_context_ref,
                recipe_ref=wrong_year.recipe_ref,
                certificate_ref=wrong_year.materialized.certificate_artifact_ref,
                output_ref=wrong_year.materialized.derived_artifact_ref,
                roles=(
                    denominator.model_copy(
                        update={"source_series_ref": wrong_year.source_refs["denominator"]}
                    ),
                    ratio.model_copy(update={"source_series_ref": wrong_year.source_refs["ratio"]}),
                ),
                year=2023,
                binding_id="income-derived",
            )
        assert admit_execution_source(fresh, executed.simulation_result_ref).basis == admitted.basis
        original_occurrence = validate_core_model_json_artifact(
            ScopedMeasurementOccurrence, store, denominator.occurrence_ref
        )
        occurrence_manifest = store.get_manifest(denominator.occurrence_ref)
        grafted_occurrence_ref = ScopedMeasurementOccurrenceRef.model_validate(
            store.put_json(
                original_occurrence,
                PutOptions(
                    kind=original_occurrence.ARTIFACT_KIND,
                    media_type=original_occurrence.ARTIFACT_MEDIA_TYPE,
                    schema=occurrence_manifest.artifact_schema,
                    inputs=occurrence_manifest.inputs,
                    producer=ProducerInfo(
                        component="fixture.alternate_occurrence_profile", version="1.0"
                    ),
                ),
                return_selected_profile=True,
            ).model_dump()
        )
        assert grafted_occurrence_ref.artifact_id == denominator.occurrence_ref.artifact_id
        assert (
            grafted_occurrence_ref.manifest_profile_sha256
            != denominator.occurrence_ref.manifest_profile_sha256
        )
        with pytest.raises(
            ValueError,
            match="foundry_input_bindings_derived_correspondence_refused:.*denominator_source_context_mismatch",
        ):
            materialize_derived_model_input(
                store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=preflight.obligation_set_ref,
                model_input_obligation_ref=obligation_ref,
                profile_ref=profile_ref,
                source_context_ref=source_context_ref,
                recipe_ref=arithmetic.recipe_ref,
                certificate_ref=arithmetic.materialized.certificate_artifact_ref,
                output_ref=arithmetic.materialized.derived_artifact_ref,
                roles=(
                    denominator.model_copy(update={"occurrence_ref": grafted_occurrence_ref}),
                    ratio,
                ),
                year=2024,
                binding_id="income-derived",
            )
        assert admit_execution_source(fresh, executed.simulation_result_ref).basis == admitted.basis
        # The new payload stays derived even if a caller strips its manifest.
        with pytest.raises(
            ValueError, match=r"^foundry_input_bindings_semantic_manifest_required$"
        ):
            build_input_bindings(
                store,
                data_snapshot_ref=materialized.data_snapshot_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                rules=[],
                return_selected_profile=True,
            )
        unselected_legacy = FoundryInputBindings(
            data_snapshot_ref=bound.data_snapshot_ref.model_copy(
                update={"manifest_profile_sha256": None}
            ),
            registry_bundle_ref=bound.registry_bundle_ref,
            rules=bound.rules,
            bound_state_snapshot_ref=bound.bound_state_snapshot_ref,
        )
        with pytest.raises(
            ValueError, match=r"^foundry_input_bindings_semantic_manifest_required$"
        ):
            reconcile_semantic_input_bindings(fresh, unselected_legacy)
        plain_legacy = load_input_bindings(fresh, case.input_bindings_ref)
        plain_legacy = plain_legacy.model_copy(
            update={
                "data_snapshot_ref": plain_legacy.data_snapshot_ref.model_copy(
                    update={"manifest_profile_sha256": None}
                )
            }
        )
        assert reconcile_semantic_input_bindings(fresh, plain_legacy) == ()
        snapshot = validate_core_model_json_artifact(
            DataSnapshot, store, materialized.data_snapshot_ref
        )
        assert snapshot.source_lineage is None
        assert "derived_input_not_acquired_observation" in snapshot.notes
    finally:
        if owner is not None:
            owner.overlay.close()
        case.close()


def test_preflight_refuses_two_value_shape_without_implicit_broadcast(tmp_path: Path) -> None:
    case, _ = _one_aggregate_income_case(tmp_path, shape=(2,))
    try:
        with pytest.raises(ValueError, match=r"^model_input_port_physical_profile_unsupported$"):
            _preflight(
                case,
                _interface(case),
                _context(case),
                steps=(0,),
                parameter_override_bundle_ref=_supplied_rate(case),
            )
    finally:
        case.close()
