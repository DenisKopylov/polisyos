"""Behavioral checks for canonical source-to-forecast profile binding."""

from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.contracts import ForecastProfileMemberV1
from polisyos.core.contracts.forecast_profile_member import (
    VALUE_DATA_PROFILE_KIND,
    VALUE_OWNER_PROJECTION_KIND,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection,
    CanonicalAcquisitionObservation,
    ObservationProvenanceClass,
)
from polisyos.ir import ArtifactRefModel
from polisyos.runtime.quality.forecast_profile_binding import (
    join_profile_member_to_observed_series,
    validate_profile_projection_binding,
)
from polisyos.runtime.quality.generation_cycle import (
    ValueDataProfile,
    ValueOwnerRow,
    _derived_value_data_modalities,
    _value_owner_row,
    gy_content_hash,
)


def _observation(
    *,
    observation_id: str,
    dataset_id: str,
    unit_id: str = "UA",
    period_id: int,
    value: float,
) -> CanonicalAcquisitionObservation:
    return CanonicalAcquisitionObservation(
        observation_id=observation_id,
        dataset_id=dataset_id,
        raw_variable="metric",
        canonical_var="metric",
        country_code=unit_id,
        year=period_id,
        value=value,
        condition_json='{"unit":"USD"}',
        acquisition_method="controlled_fixture",
        source_watermark="controlled_fixture",
        dataset_version="fixture-v1",
        observation_class=ObservationProvenanceClass.OBSERVED,
    )


def _projection(
    observations: tuple[CanonicalAcquisitionObservation, ...],
) -> ActivatedAcquisitionObservationProjection:
    return ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=CoreArtifactRef(
            artifact_id=ArtifactID("sha256:" + "1" * 64),
            kind="epoch.activated_overlay_admission_receipt",
            media_type="application/json",
        ),
        receipt_content_sha256="sha256:" + "2" * 64,
        passport_ref=CoreArtifactRef(
            artifact_id=ArtifactID("sha256:" + "3" * 64),
            kind="epoch.acquisition_passport_snapshot",
            media_type="application/json",
        ),
        passport_content_sha256="sha256:" + "4" * 64,
        variable_id="metric",
        epoch_id=1,
        passport_id="controlled-candidate-passport",
        admission_content_sha256="sha256:" + "5" * 64,
        observations=observations,
    )


def _profile(
    observations: tuple[CanonicalAcquisitionObservation, ...],
    *,
    unit_id: str = "UA",
) -> ValueDataProfile:
    by_period: dict[int, list[tuple[float, str, str, str]]] = {}
    for observation in observations:
        assert observation.year is not None
        by_period.setdefault(observation.year, []).append(
            (
                observation.value,
                observation.dataset_id,
                observation.observation_id,
                "USD",
            )
        )
    rows = tuple(
        _value_owner_row(
            outcome="metric",
            unit_id=unit_id,
            period_id=period_id,
            source_rows=tuple(by_period[period_id]),
        )
        for period_id in sorted(by_period)
    )
    assert len(rows) >= 4
    return _profile_from_rows(rows)


def _profile_from_rows(
    rows: tuple[ValueOwnerRow, ...],
    *,
    outcome: str = "metric",
    measurement_unit: str = "USD",
) -> ValueDataProfile:
    rows_payload = tuple(row.model_dump(mode="json") for row in rows)
    payload = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": outcome,
        "measurement_unit": measurement_unit,
        "rows": rows_payload,
        "owner_row_count": len(rows),
        "unit_count": len({row.unit_id for row in rows}),
        "period_count": len({row.period_id for row in rows}),
        "available_data_modalities": _derived_value_data_modalities(rows),
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "controlled://candidate-only-profile-fixture",
        "owner_rows_content_hash": gy_content_hash(rows_payload),
    }
    return ValueDataProfile.model_validate({**payload, "content_hash": gy_content_hash(payload)})


def _observations() -> tuple[CanonicalAcquisitionObservation, ...]:
    return tuple(
        _observation(
            observation_id=f"obs-{period_id}-{source_index}",
            dataset_id=f"dataset-{source_index}",
            period_id=period_id,
            value=float(period_id + (1 if source_index == 0 else 3)),
        )
        for period_id in range(4)
        for source_index in range(2)
    )


def _ref(artifact_id: str, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=f"sha256:{artifact_id * 64}",
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )


def test_canonical_aggregated_profile_binds_full_multirow_projection() -> None:
    observations = _observations()
    projection = _projection(observations)
    profile = _profile(observations)

    selected = validate_profile_projection_binding(
        profile=profile,
        projection_payload=projection.model_dump(mode="json"),
    )
    receipt, joined_values = join_profile_member_to_observed_series(
        profile=profile,
        profile_ref=_ref("1", "runtime.value_data_profile"),
        source_projection_ref=_ref("2", "runtime.value_owner_source_projection"),
        projection=selected,
        observed_source_ref=_ref("3", "fabric.data_snapshot"),
        observed_data_ref=_ref("4", "test.observed_data"),
        target_metric="metric",
        unit_id="UA",
        observed_values=[float(period_id + 2) for period_id in range(4)],
    )

    assert len(profile.rows[0].source_row_content_hashes) == 2
    assert profile.rows[0].outcome_value == pytest.approx(2.0)
    assert joined_values == (2.0, 3.0, 4.0, 5.0)
    assert receipt.source_projection_ref.kind == "runtime.value_owner_source_projection"
    assert receipt.source_projection_content_sha256 == projection.projection_content_sha256
    assert receipt.row_count == 4
    assert receipt.authority_scope == "predictive_only"
    assert receipt.source_relation_status == "not_established"
    assert ForecastProfileMemberV1.model_validate(receipt.model_dump(mode="json")) == receipt
    malformed_count = receipt.model_dump(mode="json")
    malformed_count["row_count"] = True
    with pytest.raises(ValueError, match="row_count"):
        ForecastProfileMemberV1.model_validate(malformed_count)


def test_projection_order_is_normalized_but_profile_hash_tuple_order_is_not() -> None:
    observations = _observations()
    profile = _profile(observations)
    reversed_projection = _projection(tuple(reversed(observations)))

    validate_profile_projection_binding(
        profile=profile,
        projection_payload=reversed_projection.model_dump(mode="json"),
    )

    original_row = profile.rows[0]
    reversed_hashes = tuple(reversed(original_row.source_row_content_hashes))
    row_payload = original_row.model_dump(mode="json")
    row_payload["source_row_content_hashes"] = reversed_hashes
    row_payload.pop("row_content_hash")
    forged_row = ValueOwnerRow(
        **row_payload,
        row_content_hash=gy_content_hash(row_payload),
    )
    rows = (forged_row, *profile.rows[1:])
    forged_profile = _profile_from_rows(rows)

    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=forged_profile,
            projection_payload=_projection(observations).model_dump(mode="json"),
        )


def test_binding_refuses_removed_altered_and_foreign_source_rows() -> None:
    observations = _observations()
    profile = _profile(observations)

    removed_projection = _projection(observations[1:])
    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=profile,
            projection_payload=removed_projection.model_dump(mode="json"),
        )

    altered = (
        _observation(
            observation_id="obs-0-0",
            dataset_id="dataset-0",
            period_id=0,
            value=99.0,
        ),
        *observations[1:],
    )
    altered_projection = _projection(tuple(altered))
    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=profile,
            projection_payload=altered_projection.model_dump(mode="json"),
        )

    foreign_rows = tuple(
        _observation(
            observation_id=f"foreign-{period_id}-{source_index}",
            dataset_id=f"foreign-dataset-{source_index}",
            unit_id="PL",
            period_id=period_id,
            value=float(period_id + (1 if source_index == 0 else 3)),
        )
        for period_id in range(4)
        for source_index in range(2)
    )
    foreign_profile = _profile(foreign_rows, unit_id="UA")
    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=foreign_profile,
            projection_payload=_projection(foreign_rows).model_dump(mode="json"),
        )


def test_runtime_intake_enforces_canonical_single_row_single_dataset_shape() -> None:
    observations = _observations()
    profile = _profile(observations)
    projection = _projection(observations)

    # The generic tuple primitive remains useful for candidate-only math and
    # still recomputes a valid multirow aggregate.
    validate_profile_projection_binding(
        profile=profile,
        projection_payload=projection.model_dump(mode="json"),
    )

    # Runtime's actual EMP-01 producer refuses every duplicate unit-period,
    # even when the submitted aggregate is content-consistent.
    with pytest.raises(ValueError, match="source_row_binding_ambiguous"):
        validate_profile_projection_binding(
            profile=profile,
            projection_payload=projection.model_dump(mode="json"),
            require_canonical_owner_profile_shape=True,
        )

    single_row_periods = tuple(
        _observation(
            observation_id=f"single-{period_id}",
            dataset_id="one-owner-dataset",
            period_id=period_id,
            value=float(period_id),
        )
        for period_id in range(4)
    )
    valid_single_dataset_profile = _profile(single_row_periods)
    validate_profile_projection_binding(
        profile=valid_single_dataset_profile,
        projection_payload=_projection(single_row_periods).model_dump(mode="json"),
        require_canonical_owner_profile_shape=True,
    )

    split_dataset_periods = tuple(
        _observation(
            observation_id=f"split-{period_id}",
            dataset_id=("dataset-a" if period_id < 2 else "dataset-b"),
            period_id=period_id,
            value=float(period_id),
        )
        for period_id in range(4)
    )
    split_dataset_profile = _profile(split_dataset_periods)

    # Without the Runtime producer contract this remains a deterministic
    # candidate tuple; at the served intake the loader's dataset rule applies.
    validate_profile_projection_binding(
        profile=split_dataset_profile,
        projection_payload=_projection(split_dataset_periods).model_dump(mode="json"),
    )
    with pytest.raises(ValueError, match="source_dataset_ambiguous"):
        validate_profile_projection_binding(
            profile=split_dataset_profile,
            projection_payload=_projection(split_dataset_periods).model_dump(mode="json"),
            require_canonical_owner_profile_shape=True,
        )


def _persist_selected_definition(store, *, variable: str, revision: str):
    from polisyos.core.artifacts import PutOptions, SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.contracts.variable_binding import (
        SelectedVariableBindingRef,
        VariableSemanticDefinition,
        VariableSemanticDefinitionRef,
    )

    evidence = store.put_bytes(
        f"Declared software fixture measure: {variable}, revision {revision}.".encode(),
        PutOptions(kind="test.forecast_outcome_definition", media_type="text/plain"),
        return_selected_profile=True,
    )
    namespace, stable_id = variable.split(".", 1)
    definition = VariableSemanticDefinition(
        namespace=namespace,
        stable_id=stable_id,
        revision=revision,
        meaning=f"Annual observed level of {variable} under its declared scope.",
        definition_evidence_refs=(
            SelectedVariableBindingRef.model_validate(evidence.model_dump()),
        ),
    )
    return VariableSemanticDefinitionRef.model_validate(
        store.put_json(
            definition,
            PutOptions(
                kind=definition.ARTIFACT_KIND,
                media_type=definition.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=definition.ARTIFACT_SCHEMA_NAME,
                    version=definition.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[input_ref_from_artifact_ref(evidence, role="definition_evidence")],
            ),
            return_selected_profile=True,
        ).model_dump()
    )


def _persist_selected_representation(
    store,
    *,
    definition,
    scale,
    temporal_granularity="annual",
    quantity_kind="outcome",
    time_support="period_total",
    aggregation="sum",
    population_ref="national_economy",
):
    from polisyos.core.artifacts import PutOptions, SchemaInfo
    from polisyos.core.contracts.variable_binding import (
        VariableRepresentation,
        VariableRepresentationRef,
        variable_representation_manifest_inputs,
    )

    representation = VariableRepresentation(
        representation_id="forecast.annual-national-account",
        revision="fixture",
        semantic_definition_ref=definition,
        quantity_kind=quantity_kind,
        measure_form="absolute",
        unit_id="usd",
        scale_to_unit=scale,
        time_support=time_support,
        temporal_granularity=temporal_granularity,
        aggregation=aggregation,
        grain=("geography", "calendar_year"),
        population_ref=population_ref,
    )
    return VariableRepresentationRef.model_validate(
        store.put_json(
            representation,
            PutOptions(
                kind=representation.ARTIFACT_KIND,
                media_type=representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=representation.ARTIFACT_SCHEMA_NAME,
                    version=representation.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=variable_representation_manifest_inputs(representation),
            ),
            return_selected_profile=True,
        ).model_dump()
    )


def _persist_outcome_level_member(store, *, variable, profile, projection, passport, values):
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.ir import CanonSpec, InputRef, put_json_artifact
    from polisyos.runtime.quality.forecast_profile_binding import (
        FORECAST_PROFILE_MEMBER_KIND,
        FORECAST_PROFILE_MEMBER_SCHEMA,
        FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
        VALUE_DATA_PROFILE_SCHEMA,
        VALUE_DATA_PROFILE_SCHEMA_VERSION,
        VALUE_OWNER_PROJECTION_SCHEMA,
        VALUE_OWNER_PROJECTION_SCHEMA_VERSION,
        ResolvedValueProfileProjection,
    )

    ir_store = ensure_ir_artifact_store(store)

    def persist(body, *, kind, schema, version, dependencies=()):
        return ArtifactRefModel.model_validate(
            put_json_artifact(
                ir_store,
                body,
                kind=kind,
                schema_name=schema,
                schema_version=version,
                inputs=[
                    InputRef(
                        artifact_id=ref.artifact_id,
                        role=role,
                        manifest_profile_sha256=ref.manifest_profile_sha256,
                    )
                    for role, ref in dependencies
                ],
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )

    projection_ref = persist(
        projection.model_dump(mode="json"),
        kind=VALUE_OWNER_PROJECTION_KIND,
        schema=VALUE_OWNER_PROJECTION_SCHEMA,
        version=VALUE_OWNER_PROJECTION_SCHEMA_VERSION,
    )
    profile_ref = persist(
        profile.model_dump(mode="json"),
        kind=VALUE_DATA_PROFILE_KIND,
        schema=VALUE_DATA_PROFILE_SCHEMA,
        version=VALUE_DATA_PROFILE_SCHEMA_VERSION,
        dependencies=(("activated_source_projection", projection_ref),),
    )
    data_ref = persist(
        {variable: values},
        kind="test.forecast.values",
        schema="test.forecast.values",
        version="1.0",
    )
    snapshot = DataSnapshot(data_ref=CoreArtifactRef.model_validate(data_ref.model_dump()))
    snapshot_ref = persist(
        snapshot.model_dump(mode="json"),
        kind=DataSnapshot.ARTIFACT_KIND,
        schema=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
        dependencies=(("data_ref", data_ref),),
    )
    member, compared = join_profile_member_to_observed_series(
        profile=profile,
        profile_ref=profile_ref,
        source_projection_ref=projection_ref,
        projection=projection,
        observed_source_ref=snapshot_ref,
        observed_data_ref=data_ref,
        target_metric=variable,
        unit_id="UA",
        observed_values=values,
        source_passport=passport,
    )
    assert compared == tuple(values)
    member_ref = persist(
        member.model_dump(mode="json"),
        kind=FORECAST_PROFILE_MEMBER_KIND,
        schema=FORECAST_PROFILE_MEMBER_SCHEMA,
        version=FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
        dependencies=(
            ("value_data_profile", profile_ref),
            ("activated_source_projection", projection_ref),
            ("observed_source", snapshot_ref),
            ("observed_data", data_ref),
        ),
    )
    return (
        CoreArtifactRef.model_validate(member_ref.model_dump()),
        CoreArtifactRef.model_validate(profile_ref.model_dump()),
        member,
        ResolvedValueProfileProjection(profile, projection_ref, projection, passport),
    )


async def _stock_annual_gdp_candidate(store, tmp_path, monkeypatch, port):
    """Persist the stock N4 scenario with one explicit model-owned outcome port."""
    from pathlib import Path

    from polisyos.core.contracts.model_input_requirements import (
        ModelInputPortDeclaration,
        persist_model_input_port_declaration,
    )
    from polisyos.ir.kernel.time_semantics import TimeSemantics
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.runtime.quality import world_model_record
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationContextOffer,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        CycleSubstrateContextArtifactOwner,
    )
    from polisyos.runtime.quality.forecast_profile_binding import OBSERVED_OUTCOME_LEVEL_ESTIMAND
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        N4GenerationPort,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )
    from tests._helpers.controlled_candidate_profile import (
        _build_configured_procurement_profile,
        _controlled_procurement_recording,
        _current_compiler_problem,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import (
        _authenticated_tenant_scope,
        _TestCurrentJobExecutionOwner,
    )
    from tools.quality.validation import check_layer3_gy_design_generation_contract as n4_contract

    repo_root = Path(__file__).resolve().parents[4]
    recording = next(
        row
        for row in n4_contract._load_recordings(repo_root)
        if row["design_problem_id"] == "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
    )
    controlled = _controlled_procurement_recording(recording, outcome_variable=port.slot_id)
    problem = _current_compiler_problem(controlled, outcome_variable=port.slot_id)
    problem_data = problem.model_dump(mode="json")
    problem_data["outcome_of_interest"].update(
        estimand=OBSERVED_OUTCOME_LEVEL_ESTIMAND,
        metric_id="gdp_observed_level",
        measurement_unit=port.unit_id,
    )
    problem_data["objectives"][0].update(
        description="Forecast the annual nominal GDP level of the selected observed series.",
        metric_id="gdp_observed_level",
    )
    problem = type(problem).model_validate(problem_data)
    declaration_ref = persist_model_input_port_declaration(
        store, ModelInputPortDeclaration(ports=(port,))
    )
    original_build = world_model_record.build_world_model_record

    def configure_outcome_port(artifact_store, **inputs):
        original_model = inputs["model_spec"]
        inputs["model_spec"] = type(original_model).model_validate(
            {
                **original_model.model_dump(mode="json"),
                "schema_version": "1.1",
                "model_input_port_declaration_ref": declaration_ref.model_dump(mode="json"),
            }
        )
        return original_build(artifact_store, **inputs)

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "forecast-observed-level"
    job_id = "job-forecast-observed-level"
    run_id = "run-forecast-observed-level"
    with monkeypatch.context() as configure:
        # Supply a fixture-owned model declaration before the unchanged WMR owner writes.
        configure.setattr(world_model_record, "build_world_model_record", configure_outcome_port)
        profile, model_declaration, _ = _build_configured_procurement_profile(
            recorded_problem=problem,
            artifact_store=store,
            tenant_id=tenant_id,
            cell_id=cell_id,
            tmp_path=tmp_path,
            repo_root=repo_root,
            candidate_model_time_semantics=TimeSemantics(
                frequency=TimeFrequency.YEAR,
                start_date="2020-01-01",
                step_count=7,
            ),
            candidate_outcome_unit_id=port.unit_id,
            candidate_population_scope=port.scope.population_ref,
            candidate_resolution="country_year",
        )
    admission = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(profile,), model_declarations=(model_declaration,), store=store
    )
    context_owner = CycleSubstrateContextArtifactOwner(
        store=store, control_store=_TestCurrentJobExecutionOwner(job_id, run_id)
    )
    with _authenticated_tenant_scope(tenant_id=tenant_id, cell_id=cell_id):
        offer = admission.admit_context(
            problem=problem,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        assert type(offer) is CandidateSimulationContextOffer, offer
        job_ref = context_owner.persist_for_current_job(
            offer.context, problem=problem, repo_root=repo_root
        )
        handoff = CandidateSimulationContextHandoff(
            context=offer.context,
            context_job_ref=job_ref,
            profile=offer.profile,
            profile_config_ref=offer.profile_config_ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            model_declaration=offer.model_declaration,
            model_declaration_ref=offer.model_declaration_ref,
            ncm_ref=offer.ncm_ref,
        )
        n4 = N4GenerationPort(
            model_id=recording["model_id"],
            llm_client=n4_contract.RecordedGenerationReplayClient(controlled),
            repo_root=repo_root,
            cycle_substrate_context=offer.context,
            candidate_simulation_handoff=handoff,
        )
        controller = GenerationCycleController(
            generation_port=n4,
            repo_root=repo_root,
            artifact_store=store,
            cycle_substrate_context=offer.context,
            candidate_simulation_handoff=handoff,
            candidate_simulation_currentness_resolver=lambda: True,
            authority_scope="contract_testing",
        )
        with monkeypatch.context() as scratch:
            scratch.setattr(controller, "_repo_root", tmp_path)
            controller._begin_source_run(run_id)
        with n4_contract._recorded_runtime_environment(controlled):
            proposal = await n4(problem, cycle_index=0)
        generated = controller._candidate_scenario_proposal_result(
            proposal,
            problem=problem,
            stable_subject_ref=gy_content_hash(problem.model_dump(mode="json")),
            origin_source_ref=None,
        )
        assert generated.status == "generated" and generated.source_ref is not None, (
            generated.status,
            controller._source_issues,
        )
        candidate = GenerationSourceRepository(store).load_candidate_scenario_source_for_n5(
            generated.source_ref,
            expected_run_id=run_id,
            expected_job_id=job_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
    assert type(candidate) is N4CandidateScenarioSourceRecordV3
    assert candidate.n5_status == "not_run"
    return generated.source_ref, candidate, offer.context.world_model_record


@pytest.mark.asyncio
async def test_outcome_level_binding_compares_two_native_observed_measures(tmp_path, monkeypatch):
    """Distinct selected measures reuse the same finite source/model predicate."""
    from dataclasses import replace
    from datetime import date
    from decimal import Decimal

    from polisyos.core.artifacts import (
        FileSystemCAS,
        PutOptions,
        SchemaInfo,
        artifact_ref_for_manifest,
    )
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.core.contracts.epoch import load_verified_epoch_statement
    from polisyos.core.contracts.model_input_requirements import (
        ModelInputPort,
        ModelInputPortDeclaration,
        load_model_input_port_declaration,
        persist_model_input_port_declaration,
    )
    from polisyos.core.contracts.variable_binding import (
        MeasurementAxis,
        MeasurementBindingProfile,
        MeasurementBindingProfileRef,
        ModelInputScope,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.forecast_profile_binding import (
        _match_outcome_level_observed_scope,
        _reopen_outcome_level_profile_member,
        _verify_outcome_level_representation,
        build_forecast_outcome_level_relation,
        forecast_outcome_level_relation_inputs,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers.semantic_epoch_native import make_native_multivariable_active_projections

    store = FileSystemCAS(tmp_path / "cas")
    columns = {"economic.gdp": "gdp", "fiscal.revenue": "revenue"}
    definitions = {
        variable: _persist_selected_definition(store, variable=variable, revision="fixture-v1")
        for variable in columns
    }
    representations = {
        variable: _persist_selected_representation(store, definition=definition, scale=Decimal(1))
        for variable, definition in definitions.items()
    }
    years = range(2020, 2024)
    source = make_native_multivariable_active_projections(
        tmp_path / "native",
        source_rows=[
            {
                "country_code": "UA",
                "year": year,
                "gdp": float(year * 3),
                "revenue": float(year + 51),
                "condition_json": json.dumps(
                    {
                        "population_ref": "national_economy",
                        "geography_ref": "UA",
                        "jurisdiction_ref": "UA",
                        "time_period_basis": "calendar_year",
                    },
                    sort_keys=True,
                ),
            }
            for year in years
        ],
        variable_specs=tuple(
            {
                "target_variable": variable,
                "raw_field": raw_field,
                "raw_unit": "usd",
                "canonical_unit": "usd",
                "valid_min": 0,
                "valid_max": 10_000,
                "source_measure_scope": {
                    "population": "national_economy",
                    "temporal_granularity": "annual",
                    "jurisdiction_ref": "UA",
                    "time_period_basis": "calendar_year",
                    "source_geography_id": "UA",
                    "geography_ref": "UA",
                },
                "source_semantic_definition_ref": definitions[variable],
                "source_representation_ref": representations[variable],
            }
            for variable, raw_field in columns.items()
        ),
        condition_units_by_raw_field=dict.fromkeys(columns.values(), "usd"),
        artifact_store=store,
        return_selected_raw_profile=True,
    )
    scope = ModelInputScope(
        population_ref="national_economy",
        geography_ref="UA",
        jurisdiction_ref="UA",
        period_start=date(2018, 1, 1),
        period_end=date(2024, 12, 31),
        period_basis="calendar_year",
        time_role="observation_time",
    )
    profile = MeasurementBindingProfile(
        profile_id="forecast.outcome-level",
        revision="fixture",
        required_axes=(
            MeasurementAxis.QUANTITY_KIND,
            MeasurementAxis.MEASURE_FORM,
            MeasurementAxis.UNIT_ID,
            MeasurementAxis.TIME_SUPPORT,
        ),
    )
    binding_profile_ref = MeasurementBindingProfileRef.model_validate(
        store.put_json(
            profile,
            PutOptions(
                kind=profile.ARTIFACT_KIND,
                media_type=profile.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=profile.ARTIFACT_SCHEMA_NAME,
                    version=profile.ARTIFACT_SCHEMA_VERSION,
                ),
            ),
            return_selected_profile=True,
        ).model_dump()
    )
    ports = tuple(
        ModelInputPort(
            purpose="outcome_validation",
            port_id=raw_field,
            slot_id=f"global.{raw_field}",
            state_path=raw_field,
            unit_id="usd",
            semantic_definition_ref=definitions[variable],
            representation_ref=representations[variable],
            binding_profile_ref=binding_profile_ref,
            scope=scope,
        )
        for variable, raw_field in columns.items()
    )
    port_declaration_ref = persist_model_input_port_declaration(
        store, ModelInputPortDeclaration(ports=ports)
    )
    declaration = load_model_input_port_declaration(store, port_declaration_ref)
    try:
        for variable, port in zip(columns, declaration.ports, strict=True):
            projection = source.projections[variable]
            passport = AdmissionPassport.model_validate(
                load_verified_epoch_statement(
                    store=store,
                    ref=projection.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            rows = tuple(
                _value_owner_row(
                    outcome=variable,
                    unit_id="UA",
                    period_id=observation.year,
                    source_rows=(
                        (
                            observation.value,
                            observation.dataset_id,
                            observation.observation_id,
                            "usd",
                        ),
                    ),
                )
                for observation in (
                    row.observation
                    for row in sorted(projection.observations, key=lambda row: row.observation.year)
                )
            )
            profile = _profile_from_rows(rows, outcome=variable, measurement_unit="usd")
            member_ref, profile_ref, member, resolved = _persist_outcome_level_member(
                store,
                variable=variable,
                profile=profile,
                projection=projection,
                passport=passport,
                values=[row.outcome_value for row in rows],
            )
            assert (
                _reopen_outcome_level_profile_member(store, member_ref, profile_ref, resolved)
                == member
            )
            with pytest.raises(ValueError, match="forecast_outcome_level_member_unselected"):
                _reopen_outcome_level_profile_member(
                    store,
                    member_ref.model_copy(update={"manifest_profile_sha256": None}),
                    profile_ref,
                    resolved,
                )

            entry, observed_scope, version = _match_outcome_level_observed_scope(
                member=member,
                resolved_profile=resolved,
                port=port,
            )
            representation, compared, unknown = _verify_outcome_level_representation(
                store, selected_source=entry, member=member, port=port
            )

            assert representation == representations[variable]
            assert observed_scope.period_start == date(2020, 1, 1)
            assert observed_scope.period_end == date(2023, 12, 31)
            assert member.period_ids == tuple(years)
            assert version == passport.dataset_version
            assert MeasurementAxis.UNIT_ID in compared
            assert unknown == ()

            foreign_definition = _persist_selected_definition(
                store, variable=variable, revision="foreign-same-name"
            )
            foreign_port = port.model_copy(
                update={
                    "semantic_definition_ref": foreign_definition,
                    "representation_ref": _persist_selected_representation(
                        store, definition=foreign_definition, scale=Decimal(1)
                    ),
                }
            )
            with pytest.raises(ValueError, match="forecast_outcome_level_definition_mismatch"):
                _verify_outcome_level_representation(
                    store, selected_source=entry, member=member, port=foreign_port
                )
            scaled_port = port.model_copy(
                update={
                    "representation_ref": _persist_selected_representation(
                        store, definition=definitions[variable], scale=Decimal(1000)
                    ),
                }
            )
            with pytest.raises(ValueError, match="forecast_outcome_level_representation_mismatch"):
                _verify_outcome_level_representation(
                    store, selected_source=entry, member=member, port=scaled_port
                )
            narrow_port = port.model_copy(
                update={"scope": scope.model_copy(update={"period_start": date(2021, 1, 1)})}
            )
            with pytest.raises(
                ValueError, match="forecast_outcome_level_observed_period_out_of_scope"
            ):
                _match_outcome_level_observed_scope(
                    member=member,
                    resolved_profile=resolved,
                    port=narrow_port,
                )

            if variable == "economic.gdp":
                source_ref, candidate, world = await _stock_annual_gdp_candidate(
                    store, tmp_path / "configured", monkeypatch, port
                )
                precursor = candidate.profile.context_inputs.world_model_record
                assert precursor.content_hash != world.content_hash
                assert world.content_hash == candidate.world_model_record_hash
                assert (
                    world.world_model_record_id == candidate.candidate.atom.world_model_record_ref
                )
                assert world.slot_binding("global.gdp").temporal_granularity == "flow"
                model_ref = artifact_ref_for_manifest(
                    store.get_manifest(world_model_artifact_views(world).model_spec_ref)
                )
                relation_inputs = {
                    "candidate_source_ref": source_ref,
                    "candidate_source": candidate,
                    "model_spec_ref": model_ref,
                    "observed_member_ref": member_ref,
                    "value_data_profile_ref": profile_ref,
                    "resolved_profile": resolved,
                }
                relation = build_forecast_outcome_level_relation(store, **relation_inputs)
                assert relation.target_variable == "global.gdp"
                assert relation.n4_metric_id == "gdp_observed_level"
                assert relation.world_model_content_hash == world.content_hash
                assert relation.observed_target_metric == variable
                assert relation.value_data_profile_ref == profile_ref
                assert relation.observed_scope == observed_scope
                assert relation.measurement_unit == "usd"
                assert relation.source_dataset_version == version
                assert relation.transformation == "identity"
                assert relation.authority_scope == "predictive_only"
                assert relation.issuer_status == relation.source_time_status == "not_established"
                assert relation.population_scope_status == "not_established"
                assert {
                    (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256)
                    for edge in forecast_outcome_level_relation_inputs(relation)
                } >= {
                    (
                        "candidate_source",
                        str(source_ref.artifact_id),
                        source_ref.manifest_profile_sha256,
                    ),
                    (
                        "value_data_profile",
                        str(profile_ref.artifact_id),
                        profile_ref.manifest_profile_sha256,
                    ),
                }

                wrong_candidate = candidate.model_copy(
                    update={"stable_subject_ref": "sha256:" + "f" * 64}
                )
                with pytest.raises(
                    ValueError, match="forecast_outcome_level_candidate_selection_mismatch"
                ):
                    build_forecast_outcome_level_relation(
                        store, **{**relation_inputs, "candidate_source": wrong_candidate}
                    )

                manifest = store.get_manifest(profile_ref)
                sibling = store.put_bytes(
                    store.get_bytes(profile_ref),
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=manifest.artifact_schema,
                        inputs=manifest.inputs,
                        canon=manifest.canon,
                        producer=ProducerInfo(component="test.different_profile", version="1.0"),
                    ),
                    return_selected_profile=True,
                )
                assert sibling.artifact_id == profile_ref.artifact_id
                assert sibling.manifest_profile_sha256 != profile_ref.manifest_profile_sha256
                with pytest.raises(
                    ValueError, match="forecast_outcome_level_member_profile_selection_mismatch"
                ):
                    build_forecast_outcome_level_relation(
                        store, **{**relation_inputs, "value_data_profile_ref": sibling}
                    )

                source_measure_scope = entry.source_measure_scope
                assert source_measure_scope is not None
                share_entry = entry.model_copy(
                    update={
                        "source_measure_scope": source_measure_scope.model_copy(
                            update={
                                "quantity_kind": "share_of_denominator",
                                "denominator": "national_economy",
                            }
                        )
                    }
                )
                with pytest.raises(
                    ValueError, match="forecast_outcome_level_source_quantity_scope_mismatch"
                ):
                    _verify_outcome_level_representation(
                        store, selected_source=share_entry, member=member, port=port
                    )

                monthly_rep = _persist_selected_representation(
                    store,
                    definition=definitions[variable],
                    scale=Decimal(1),
                    temporal_granularity="monthly",
                )
                monthly_entry = entry.model_copy(
                    update={
                        "source_measure_scope": source_measure_scope.model_copy(
                            update={"temporal_granularity": "monthly"}
                        ),
                        "source_representation_ref": monthly_rep,
                    }
                )
                monthly_port = port.model_copy(update={"representation_ref": monthly_rep})
                with pytest.raises(
                    ValueError, match="forecast_outcome_level_representation_mismatch"
                ):
                    _verify_outcome_level_representation(
                        store, selected_source=monthly_entry, member=member, port=monthly_port
                    )
                monthly_source = replace(
                    resolved,
                    source_passport=passport.model_copy(
                        update={"source_authority_entry": monthly_entry}
                    ),
                )
                with pytest.raises(
                    ValueError, match="forecast_outcome_level_observed_scope_mismatch"
                ):
                    _match_outcome_level_observed_scope(
                        member=member, resolved_profile=monthly_source, port=monthly_port
                    )
    finally:
        source.overlay.close()
