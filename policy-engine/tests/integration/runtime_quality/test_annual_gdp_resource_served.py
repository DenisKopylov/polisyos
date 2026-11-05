"""Annual public GDP source qualification at the candidate-source boundary.

The preserved World Bank rows are real public observations. The local source
authority and transport are software-test inputs only; this test does not grant
rights, establish currentness, or admit claim evidence.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

import pytest

from tests._helpers.candidate_holdout_resource import (
    EXPECTED_2023_TO_2024_CHANGE_USD,
    GENERIC_WDI_PAGE_SIZE,
    MODEL_TIME_INPUT,
    SOFTWARE_FIXTURE_BOUNDARY,
    TARGET_WORLD_SLOT,
    UNIT_ASSIGNMENT_BASIS,
    load_wdi_observations,
    observed_annual_change_usd,
    wdi_response_for_year,
)


@pytest.mark.integration
def test_annual_gdp_source_persists_public_rows_and_refuses_provenance_relabel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real compiler and WDI owner retain annual USD, then fail closed at the source bridge."""
    from polisyos.core.artifacts import FileSystemCAS, load_core_json_artifact
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.fabric.connectors.cache import ResultSerializer
    from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY, SlotKind
    from polisyos.ir.kernel.time_semantics import TimeSemantics
    from polisyos.ir.model_layer.types import TimeFrequency
    from tests._helpers import lane01_candidate_source as source_helper
    from tests._helpers.lane01_candidate_source import (
        GDP_COMPILER_INPUT,
        build_lane01_candidate_source,
        compile_lane01_candidate_report,
    )
    from tests._helpers.lane01_wdi_profiles import GDP_PROFILE

    observations = {row.year: row for row in load_wdi_observations()}
    assert set(observations) == {2023, 2024}
    assert observations[2024].value_usd - observations[2023].value_usd == (
        EXPECTED_2023_TO_2024_CHANGE_USD
    )
    assert observed_annual_change_usd() == EXPECTED_2023_TO_2024_CHANGE_USD
    assert (observations[2023].value_usd, observations[2024].value_usd) == (
        27_811_517_000_000,
        29_298_013_000_000,
    )
    assert observations[2024].raw_unit_field == ""

    slot = DEFAULT_SLOT_REGISTRY.slots[TARGET_WORLD_SLOT]
    assert slot.kind is SlotKind.FLOW
    assert slot.unit is not None and slot.unit.unit_id == "usd"
    model_time = TimeSemantics.model_validate(MODEL_TIME_INPUT)
    assert model_time.frequency is TimeFrequency.YEAR
    assert model_time.start_date == "2023-01-01"
    assert model_time.step_count == 2
    assert SOFTWARE_FIXTURE_BOUNDARY["source_rights"] == "not_established"
    assert SOFTWARE_FIXTURE_BOUNDARY["source_currentness"] == "not_established"
    assert SOFTWARE_FIXTURE_BOUNDARY["claim_evidence_use_allowed"] is False

    report = compile_lane01_candidate_report(
        compiler_input=GDP_COMPILER_INPUT,
        profile=GDP_PROFILE,
    )
    resolutions = tuple(
        item
        for item in (report.capability_requirement_resolutions or ())
        if item.query.construct == "economic.gdp" and item.candidate_discovery is not None
    )
    assert len(resolutions) == 1
    candidates = resolutions[0].candidate_discovery.candidates
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.descriptor["evidence_mode"] == "observed"
    assert candidate.descriptor["rights_envelope"]["access_class"] == "not_established"
    assert candidate.descriptor["freshness_envelope"]["freshness_class"] == "not_established"
    source_metadata = candidate.source_assets[0]["metadata"]
    assert source_metadata["indicator_id"] == "NY.GDP.MKTP.CD"
    assert source_metadata["raw_unit"] == "usd"
    assert source_metadata["canonical_unit"] == "usd"
    assert source_metadata["temporal_granularity"] == "annual"
    assert source_metadata["target_world_slot"] == TARGET_WORLD_SLOT
    assert resolutions[0].query.entity_scope == "country"
    assert resolutions[0].query.geography == "USA"
    assert resolutions[0].query.time_window.start == "2024-01-01"
    assert resolutions[0].query.time_window.end == "2024-12-31"

    store = FileSystemCAS(tmp_path / "candidate-cas")
    executions: list[tuple[Any, Any]] = []
    persist_source = source_helper.persist_candidate_acquisition_source

    def capture_source_execution(artifact_store: Any, **kwargs: Any) -> Any:
        executions.append((artifact_store, kwargs["live_source_execution"]))
        return persist_source(artifact_store, **kwargs)

    monkeypatch.setattr(
        source_helper,
        "persist_candidate_acquisition_source",
        capture_source_execution,
    )
    with pytest.raises(ValueError, match=r"^candidate_source_owner_scope_mismatch$"):
        build_lane01_candidate_source(
            tmp_path / "actual-wdi-source",
            monkeypatch,
            store=store,
            profile=GDP_PROFILE,
            compiler_input=GDP_COMPILER_INPUT,
            response_body=wdi_response_for_year(2024),
        )

    assert len(executions) == 1
    captured_store, source_execution = executions[0]
    assert captured_store is store
    snapshot = DataSnapshot.model_validate(
        load_core_json_artifact(store, source_execution.data_snapshot_ref)
    )
    assert snapshot.evidence_ref == source_execution.evidence_bundle_ref
    result = ResultSerializer.deserialize(store.get_bytes(snapshot.data_ref))
    assert result.row_count == 1
    assert result.schema_id == "worldbank.wdi.generic"
    assert source_execution.transport_trace.params == {
        "date": "2024:2024",
        "format": "json",
        "page": "1",
        "per_page": str(GENERIC_WDI_PAGE_SIZE),
    }
    rows = result.data.to_dict(orient="records")
    assert len(rows) == 1
    assert rows[0]["country_code"] == "USA"
    assert rows[0]["indicator_id"] == "NY.GDP.MKTP.CD"
    assert rows[0]["year"] == 2024
    assert rows[0]["value"] == observations[2024].value_usd


@pytest.mark.integration
def test_annual_gdp_connector_refuses_row_outside_declared_source_year(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response row from 2024 cannot satisfy a compiler/source scope for 2023."""
    from dataclasses import replace

    from polisyos.runtime.quality.acquisition_executor import LiveAcquisitionExecutionError
    from tests._helpers.lane01_candidate_source import (
        GDP_COMPILER_INPUT,
        build_lane01_candidate_source,
    )
    from tests._helpers.lane01_wdi_profiles import GDP_PROFILE

    source_profile = replace(GDP_PROFILE, year=2023)
    compiler_input = replace(
        GDP_COMPILER_INPUT,
        scenario_id="lane01-gdp-usa-2023",
        profile_id="scope:lane01-gdp-usa-2023:v1",
        time_start="2023-01-01",
        time_end="2023-12-31",
    )
    with pytest.raises(LiveAcquisitionExecutionError) as mismatch:
        build_lane01_candidate_source(
            tmp_path / "mismatched-year-source",
            monkeypatch,
            profile=source_profile,
            compiler_input=compiler_input,
            response_body=wdi_response_for_year(2024),
        )
    assert mismatch.value.code == "live_normalized_scope_drift"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_annual_gdp_observation_reaches_fresh_configured_n5_consumer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Route captured annual GDP through observed admission, WMR refresh, and selected N5."""
    import asyncio
    import contextvars
    from dataclasses import replace
    from uuid import uuid4

    import numpy as np

    from polisyos.core.artifacts import (
        ArtifactRef,
        FileSystemCAS,
        input_ref_from_artifact_ref,
        load_core_json_artifact,
    )
    from polisyos.core.contracts import StateSnapshot
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api.catalog import DatasetCatalogGraph
    from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality import acquisition_planner, generation_cycle
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionCandidateWorldRefresh,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.data_state_substrate import (
        L1VariableAvailability,
    )
    from polisyos.runtime.quality.generation_cycle import ValuePortObservation
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.substrate_registry import (
        DEFAULT_L1_DCAT_PATH,
        DEFAULT_L2_SCHOLAR_KG_PATH,
        DEFAULT_L3_LEX_KG_PATH,
        DEFAULT_PRODUCTION_DATA_ROOT,
        build_substrate_registry_from_existing_catalogs,
        catalog_serving_source_scope,
        require_catalog_serving_graph_binding,
        require_catalog_source_registry_binding,
        resolve_catalog_serving_source,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers import (
        acquisition_chain,
        acquisition_production,
        acquisition_served_history,
        controlled_candidate_profile,
        runtime_http,
    )
    from tests._helpers import (
        world_model_record as wmr_fixture,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        candidate_cycle_catalog_source_readback,
        complete_candidate_cycle_catalog_source,
    )
    from tests._helpers.lane01_candidate_source import GDP_COMPILER_INPUT
    from tests._helpers.lane01_wdi_profiles import (
        GDP_PROFILE,
        build_fixture_wdi_authority,
    )
    from tests._helpers.runtime_http import _build_control_service
    from tests.integration.core_runtime import test_acquisition_world_growth_chain as observed_chain
    from tests.unit.runtime.quality.test_substrate_registry import (
        _write_substrate_catalog_fixture,
    )

    observations = {row.year: row for row in load_wdi_observations()}
    row_2024 = observations[2024]
    assert row_2024.value_usd == 29_298_013_000_000
    assert row_2024.indicator_label == "GDP (current US$)"
    assert row_2024.raw_unit_field == ""
    assert (
        GDP_PROFILE.construct,
        GDP_PROFILE.indicator_id,
        GDP_PROFILE.source_title,
        GDP_PROFILE.target_slot,
        GDP_PROFILE.raw_unit,
        GDP_PROFILE.canonical_unit,
        GDP_PROFILE.transform,
        GDP_PROFILE.transform_ref,
    ) == (
        "economic.gdp",
        "NY.GDP.MKTP.CD",
        "GDP (current US$)",
        "global.gdp",
        "usd",
        "usd",
        "identity",
        "fabric://units/usd-identity/v1",
    )
    assert UNIT_ASSIGNMENT_BASIS == (
        "GDP (current US$) indicator label plus the canonical annual WDI capability binding; "
        "the upstream API row unit field is blank"
    )
    assert observed_annual_change_usd() == EXPECTED_2023_TO_2024_CHANGE_USD

    # The shared WMR fixture has no GDP state field. Add an explicit zero-valued
    # test baseline so the typed global.gdp slot exists before the observed row
    # is materialized; this is not an observation or an initial-value claim.
    base_payload = dict(wmr_fixture.FABRIC_PAYLOAD)
    base_payload["gdp"] = 0.0
    monkeypatch.setattr(wmr_fixture, "FABRIC_PAYLOAD", base_payload)

    source_profile = replace(
        GDP_PROFILE,
        country_code="USA",
        country_id="US",
        year=2024,
        fixture_value=float(row_2024.value_usd),
    )
    # The control and WDI authority use a code root distinct from the selected
    # source owner. Epoch L5 metadata belongs to the code root; complete L1/L5
    # source bytes and its published catalog belong to the source owner root.
    fixture_repo_root = (tmp_path / "wdi" / "repo").resolve()
    fixture_repo_root.mkdir(parents=True, exist_ok=True)
    _write_substrate_catalog_fixture(fixture_repo_root, include_graphs=False)
    catalog_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "gdp-n7-catalog",
        outcome_variable="global.gdp",
    )
    catalog_owner_root = catalog_inputs.root.resolve(strict=True)
    catalog_monkeypatch = pytest.MonkeyPatch()
    catalog_source_context = complete_candidate_cycle_catalog_source(
        catalog_owner_root,
        catalog_monkeypatch,
    )
    catalog_context = contextvars.copy_context()
    try:
        catalog_selection, _same_root_source, _same_root_registry = await asyncio.to_thread(
            catalog_context.run,
            catalog_source_context.__enter__,
        )
    except BaseException:
        catalog_monkeypatch.undo()
        raise

    def release_catalog_source() -> None:
        try:
            catalog_context.run(catalog_source_context.__exit__, None, None, None)
        finally:
            catalog_monkeypatch.undo()

    request.addfinalizer(release_catalog_source)
    assert catalog_selection.source_owner_root == catalog_owner_root
    selected_catalog_source = resolve_catalog_serving_source(
        fixture_repo_root,
        selection=catalog_selection,
        requested_profile=catalog_selection.catalog_run_profile,
    )
    selected_catalog_graph = DatasetCatalogGraph(
        selected_catalog_source.database_path,
        selected_catalog_source.index_dir,
        overlay_path=selected_catalog_source.overlay_path,
    )
    request.addfinalizer(selected_catalog_graph.close)
    require_catalog_serving_graph_binding(selected_catalog_graph, selected_catalog_source)
    with catalog_serving_source_scope(selected_catalog_source):
        selected_catalog_registry = build_substrate_registry_from_existing_catalogs(
            fixture_repo_root
        )
        require_catalog_source_registry_binding(
            fixture_repo_root,
            selected_catalog_registry,
            selected_catalog_source,
        )
    selected_catalog_readback = candidate_cycle_catalog_source_readback(
        selected_catalog_source.database_path
    )

    source_paths = selected_catalog_source.substrate_paths
    source_owner_paths = (
        source_paths.root_manifest_path,
        source_paths.measurement_registry_path,
        source_paths.identification_mode_registry_path,
        source_paths.schema_regime_registry_path,
        source_paths.l1_dcat_path,
        catalog_owner_root / DEFAULT_L2_SCHOLAR_KG_PATH,
        catalog_owner_root / DEFAULT_L3_LEX_KG_PATH,
    )
    assert selected_catalog_source.selection_basis == "explicit_path_candidate_only"
    assert selected_catalog_source.repo_root == fixture_repo_root
    assert selected_catalog_source.source_owner_root == catalog_owner_root
    assert selected_catalog_source.snapshot_root.is_relative_to(catalog_owner_root)
    assert selected_catalog_source.database_path == source_paths.l1_dcat_path
    assert selected_catalog_source.database_path.is_relative_to(catalog_owner_root)
    assert selected_catalog_readback["source_database_path"] == str(
        selected_catalog_source.database_path
    )
    assert selected_catalog_readback["source_database_sha256"]
    assert any(
        ref.startswith("catalog_read_source_content://")
        for ref in selected_catalog_registry.source_catalog_refs
    )
    assert all(path.is_file() for path in source_owner_paths)
    assert all(
        path.resolve(strict=True).is_relative_to(catalog_owner_root) for path in source_owner_paths
    )
    epoch_owner_paths = (
        source_paths.epoch_schema_regime_registry_path,
        source_paths.epoch_schema_regime_scope_registry_path,
    )
    assert all(path is not None and path.is_file() for path in epoch_owner_paths)
    assert all(
        path is not None and path.resolve(strict=True).is_relative_to(fixture_repo_root)
        for path in epoch_owner_paths
    )
    root_manifest = json.loads(source_paths.root_manifest_path.read_text(encoding="utf-8"))
    l6_bundle_path = root_manifest["bundles"]["ukraine_simulation"]["path"]
    l6_bundle_root = (
        catalog_owner_root
        / DEFAULT_PRODUCTION_DATA_ROOT
        / l6_bundle_path
        / "production_bundle"
        / "bundles"
    )
    l6_owner_paths = (
        l6_bundle_root / "intervention_bundle_v1/intervention_knob_dictionary.json",
        l6_bundle_root / "intervention_bundle_v1/lex_intervention_map.json",
        l6_bundle_root / "method_contract_bundle_v1/observation_to_contract_manifest.json",
        l6_bundle_root / "intervention_bundle_v1/policy_scenario_templates.json",
    )
    assert all(path.is_file() for path in l6_owner_paths)
    assert all(
        path.resolve(strict=True).is_relative_to(catalog_owner_root) for path in l6_owner_paths
    )

    entry_seed_root = tmp_path / "gdp-entry-seed"
    _entry_seed_authority, gdp_entry = build_fixture_wdi_authority(
        entry_seed_root,
        source_profile,
        attempt_id=acquisition_chain._ATTEMPT_ID,
    )
    monkeypatch.setattr(acquisition_chain, "_entry", lambda: gdp_entry)

    def build_gdp_authority(repo_root: Path, **_kwargs: object):
        selected_root = Path(repo_root).resolve(strict=True)
        assert selected_root == fixture_repo_root
        authority, entry = build_fixture_wdi_authority(
            selected_root,
            source_profile,
            attempt_id=acquisition_chain._ATTEMPT_ID,
        )
        return authority, entry

    monkeypatch.setattr(acquisition_chain, "_resolver", build_gdp_authority)

    registry_provider_builder = runtime_http._build_registry_providers

    def build_selected_registry_providers(*, catalog_run_profile=None):
        providers = registry_provider_builder(catalog_run_profile=catalog_run_profile)
        return replace(
            providers,
            gy_catalog_graph=selected_catalog_graph,
            catalog_source_selection=catalog_selection,
        )

    monkeypatch.setattr(
        runtime_http, "_build_registry_providers", build_selected_registry_providers
    )

    # The connector executes normally against a socket-blocked local response;
    # only its transport bytes are pinned to this captured public API row.
    monkeypatch.setattr(acquisition_production, "_COUNTRY_CODE", "USA")
    monkeypatch.setattr(acquisition_production, "_START_YEAR", 2024)
    monkeypatch.setattr(acquisition_production, "_END_YEAR", 2024)
    monkeypatch.setattr(acquisition_production, "_INDICATOR_ID", "NY.GDP.MKTP.CD")
    monkeypatch.setattr(
        acquisition_production,
        "_normalized_rows",
        lambda **_kwargs: [
            {
                "country_code": "USA",
                "country_name": "United States",
                "indicator_id": "NY.GDP.MKTP.CD",
                "indicator_name": "GDP (current US$)",
                "year": 2024,
                "value": row_2024.value_usd,
                "unit": "",
                "decimal": 0,
            }
        ],
    )
    monkeypatch.setattr(
        acquisition_production,
        "_raw_body",
        lambda _rows, **_kwargs: wdi_response_for_year(2024),
    )
    # This is a declared hypothetical test input to the existing route planner,
    # not a World Bank price, permission, or rights assertion.
    monkeypatch.setitem(
        acquisition_planner._ACQUISITION_GAP_BASIS,
        "global.gdp",
        {
            "basis_ref": "fixture-only:hypothetical-gdp-acquisition-input:v1",
            "collection_mode": "fixture-only annual source routing input",
            "expert_hours": 1,
            "calendar_days": 1,
        },
    )

    problem_seed = controlled_candidate_profile._problem("annual_gdp_usa_2024")
    assert (
        problem_seed.candidate_lever_space.candidate_levers[0].target_slot == "government_balance"
    )
    problem = acquisition_chain.controlled_served_wdi_problem(
        problem_seed,
        raw_request=acquisition_chain.SERVED_WDI_FISCAL_REQUEST,
    )
    assert problem.schema_version == "policyos.runtime.design_problem.v3"
    # The existing v3 fixture owner maps the NL-facing lever name to a
    # registered world slot; retain the canonical physical target here.
    assert problem.candidate_lever_space.candidate_levers[0].target_slot == "government.balance"
    problem_payload = problem.model_dump(mode="json")
    gdp_scope_request = (
        "For USA in calendar year 2024, assess annual nominal GDP in current US dollars "
        "against a candidate budget-allocation multiplier on the government balance."
    )
    candidate_only_request = acquisition_chain.SERVED_WDI_CANDIDATE_ONLY_SOURCE
    problem_payload["domain"] = "economic"
    problem_payload["problem_statement"] = (
        "Assess a candidate-only USA 2024 annual nominal GDP scenario in current US dollars."
    )
    problem_payload["nl_provenance"]["raw_request"] = (
        f"{gdp_scope_request} {candidate_only_request}"
    )
    problem_payload["jurisdiction_time"].update(
        {
            "region": "USA",
            "valid_time": "2024",
            "as_of": "2024-12-31",
            "policy_time": "2024",
            "data_time": "2024",
            "time_semantics": {
                "frequency": "Y",
                "start_date": "2024-01-01",
                "step_count": 1,
            },
        }
    )
    problem_payload["objectives"] = [
        {
            "objective_id": "annual_gdp",
            "description": "Improve annual nominal GDP in current US dollars.",
            "metric_id": "annual_gdp",
            "direction": "maximize",
        }
    ]
    problem_payload["constraints"] = [
        {
            "constraint_id": "annual_gdp_request_scope",
            "description": "Keep the candidate within the requested USA 2024 annual GDP scope.",
            "hard": True,
            "admissibility_basis": "request_text",
            "source_text": gdp_scope_request,
        },
        {
            "constraint_id": "no_authority_without_a",
            "description": "Generated proposals remain candidate-only.",
            "hard": True,
            "admissibility_basis": "request_text",
            "source_text": candidate_only_request,
        },
    ]
    problem_payload["stakeholders"] = [
        {
            "stakeholder_id": "us_economic_analysts",
            "name": "US economic analysts",
            "role": "reviewer",
        }
    ]
    problem_payload["outcome_of_interest"].update(
        {
            "target_variable": "global.gdp",
            "metric_id": "annual_gdp",
            "estimand": "Candidate-only annual nominal GDP in current US dollars.",
            "direction": "maximize",
        }
    )
    problem_payload["evidence_acquisition_needs"] = {
        "needs": [
            {
                "need_id": "annual_gdp_observation",
                "question": "Which annual public source supplies nominal GDP in current US dollars?",
                "required_for": "Candidate-only GDP input availability.",
            }
        ]
    }
    problem_payload["runtime_hints"]["n7_scope_profile"] = {
        "profile_id": GDP_COMPILER_INPUT.profile_id,
        "jurisdiction": GDP_COMPILER_INPUT.jurisdiction,
        "population": GDP_COMPILER_INPUT.population,
        "entity_scope": GDP_COMPILER_INPUT.entity_scope,
        "time_window": {
            "start": GDP_COMPILER_INPUT.time_start,
            "end": GDP_COMPILER_INPUT.time_end,
        },
        "time_role": GDP_COMPILER_INPUT.time_role,
        "granularity": GDP_COMPILER_INPUT.granularity,
        "required_constructs": list(GDP_COMPILER_INPUT.required_constructs),
    }
    problem = controlled_candidate_profile.DesignProblem.model_validate(problem_payload)
    assert problem.schema_version == "policyos.runtime.design_problem.v3"
    assert problem.candidate_lever_space.candidate_levers[0].target_slot == "government.balance"
    assert problem.outcome_of_interest.target_variable == "global.gdp"

    class AnnualGDPGap:
        def __call__(self, *, candidate, problem, **_kwargs):
            return ValuePortObservation(
                status="value_blocked",
                candidate_id=candidate.candidate_id,
                authority_blockers=("acquire_data:value_panel_data_missing",),
                reason="The declared annual GDP input is absent before acquisition.",
                decision_grade="blocked",
                acquisition_requirement=acquisition_planner.l1_variable_availability_requirement_gap(
                    candidate_id=candidate.candidate_id,
                    candidate_content_hash=candidate.atom.content_hash,
                    design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                    availability=L1VariableAvailability(
                        variable_id="global.gdp",
                        status="unavailable",
                        dataset_count=0,
                        metric_binding_count=0,
                        observation_count=0,
                        coverage_ref=(
                            "repo://production_data/dataset_catalog.duckdb#variable/global.gdp"
                        ),
                    ),
                    authority_level=problem.authority_profile.requested_authority_level,
                ),
            )

    tenant_id = observed_chain._SERVED_WDI_FIXTURE_TENANT_ID
    cell_id = "cell-a"
    run_id = "run-annual-gdp-" + uuid4().hex
    source_job_id = "job-annual-gdp-" + uuid4().hex
    store = FileSystemCAS(tmp_path / "control" / ".polisyos")
    profile, declaration = acquisition_served_history._served_wdi_candidate_profile(
        tmp_path=tmp_path / "configured-gdp-profile",
        store=store,
        problem=problem,
        country_code="USA",
        data_year=2024,
        population_scope="national_economy",
    )
    # Give the fixture action a deliberate, numerically resolvable USD delta.
    # This is a declared synthetic SCM input, not an empirical spending effect.
    action_value_usd = 1_000_000_000_000
    profile_payload = profile.model_dump(mode="json", exclude={"content_hash"})
    profile_payload["rule"]["maximum"] = action_value_usd
    profile = CandidateSimulationScenarioProfile.model_validate(
        {**profile_payload, "content_hash": gy_content_hash(profile_payload)}
    )
    declaration_payload = declaration.model_dump(mode="json", exclude={"content_hash"})
    declaration_payload.update(
        {
            "profile_config_ref": candidate_simulation_profile_ref(profile),
            "profile_content_hash": profile.content_hash,
            "target_baseline": profile.n5.baseline_state["government.balance"],
            "outcome_baseline": profile.n5.baseline_state[TARGET_WORLD_SLOT],
            "outcome_per_target_unit": 0.25,
        }
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {**declaration_payload, "content_hash": gy_content_hash(declaration_payload)}
    )
    base_views = world_model_artifact_views(profile.context_inputs.world_model_record)
    base_model = ModelSpec.model_validate(load_core_json_artifact(store, base_views.model_spec_ref))
    assert base_model.time_semantics is not None
    assert base_model.time_semantics.frequency is TimeFrequency.YEAR
    assert base_model.time_semantics.start_date == "2024-01-01"
    assert base_model.time_semantics.step_count == 1
    assert profile.context_inputs.world_model_record.valid_time_scope == "2024-01-01/2024-12-31"
    assert profile.n5.baseline_state["global.gdp"] == 0.0

    # Let the canonical service construct its RetrievalService over the selected
    # source graph. The test asserts graph identity only; it makes no retrieval claim.
    monkeypatch.setattr(
        runtime_http,
        "_NoOpRetrievalService",
        lambda: None,
    )

    control = _build_control_service(
        tmp_path / "control",
        artifact_store=store,
        candidate_simulation_profiles=(profile,),
        candidate_simulation_model_declarations=(declaration,),
        repo_root=fixture_repo_root,
        catalog_run_profile=catalog_selection.catalog_run_profile,
    )
    control_catalog_source = control._catalog_serving_source
    assert control._repo_root == fixture_repo_root
    assert control_catalog_source.repo_root == selected_catalog_source.repo_root
    assert control_catalog_source.source_owner_root == selected_catalog_source.source_owner_root
    assert control_catalog_source.database_path == selected_catalog_source.database_path
    assert control._retrieval_catalog is not None
    request.addfinalizer(control._retrieval_catalog.close)
    require_catalog_serving_graph_binding(control._retrieval_catalog, control_catalog_source)
    assert control._retrieval._dataset_catalog is control._retrieval_catalog

    def under_catalog_source(function, *args, **kwargs):
        with catalog_serving_source_scope(control_catalog_source):
            return function(*args, **kwargs)

    async def await_under_catalog_source(function, *args, **kwargs):
        with catalog_serving_source_scope(control_catalog_source):
            return await function(*args, **kwargs)

    recording = acquisition_chain.load_served_wdi_generation_recording()

    # The existing captured N4 recording is transformed by the fixture owner.
    # Widen only that test-local candidate parameter to match the typed profile
    # and keep the resulting N4 recording content identified.
    original_response_transform = acquisition_chain._controlled_wdi_trinity_response

    def large_action_candidate_response(
        raw: str,
        *,
        outcome_variable: str,
        labor_problem: Any | None = None,
    ) -> str:
        transformed = original_response_transform(
            raw,
            outcome_variable=outcome_variable,
            labor_problem=labor_problem,
        )
        payload = json.loads(transformed)
        interventions = payload["policy_spec"]["interventions"]
        selected_interventions = [
            item for item in interventions if item.get("kind") == "budget_allocation_multiplier"
        ]
        assert len(selected_interventions) == 1
        selected_interventions[0]["params"]["multiplier"] = action_value_usd
        parameters = payload["policy_spec"]["parameters"]
        selected_parameters = [
            item
            for item in parameters
            if item.get("intervention_id") == selected_interventions[0]["intervention_id"]
            and item.get("param_path") == "multiplier"
        ]
        assert len(selected_parameters) == 1
        selected_parameters[0].update(
            {
                "default_value": str(action_value_usd),
                "min_value": "1",
                "max_value": str(action_value_usd),
            }
        )
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    monkeypatch.setattr(
        acquisition_chain,
        "_controlled_wdi_trinity_response",
        large_action_candidate_response,
    )
    # Select the canonical typed L1 source-gap route before N7 compiles the
    # requirement; the legacy scenario-family route is not an executable WDI
    # variable route.
    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    closure, _request = await await_under_catalog_source(
        acquisition_production.persist_wdi_route,
        control,
        generation_cycle_repo_root=fixture_repo_root,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        job_id=source_job_id,
        llm_model_id=str(recording["model_id"]),
        fixture_problem=problem,
        fixture_value_port=AnnualGDPGap(),
        fixture_target_world_slots=("government.balance",),
    )

    refresh = AcquisitionCandidateWorldRefresh(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        route_id=closure.route_id,
        profile_selection_ref=profile.profile_selection_ref,
        canonical_variable_id="global.gdp",
        target_slot_id="global.gdp",
    )
    case = under_catalog_source(
        acquisition_chain.make_wdi_port_case,
        tmp_path / "wdi",
        monkeypatch,
        control=control,
        closure=closure,
        candidate_world_refreshes=(refresh,),
        candidate_scenario_generation=True,
        candidate_generation_recording=recording,
    )
    fixture_baseline = case.authority.baseline_path.resolve(strict=True)
    assert case.authority.repo_root.resolve(strict=True) == fixture_repo_root
    assert case.bridge.repo_root.resolve(strict=True) == fixture_repo_root
    assert fixture_baseline.is_relative_to(fixture_repo_root)
    assert case.authority.registry_path.resolve(strict=True).is_relative_to(fixture_repo_root)
    assert (catalog_owner_root / DEFAULT_L1_DCAT_PATH).is_file()
    assert (catalog_owner_root / DEFAULT_L1_DCAT_PATH).resolve(strict=True) != fixture_baseline
    assert case.transport_calls == []
    negative = under_catalog_source(case.port.execute, closure)
    assert negative.disposition == "quarantined_no_growth"
    case.appoint_native_policy()
    under_catalog_source(case.port.prepare_route_execution, closure)
    action_job_id = "annual-gdp-action-" + uuid4().hex
    action = acquisition_chain.begin_current_wdi_action(
        control,
        closure,
        job_id=action_job_id,
    )
    result = under_catalog_source(
        case.port.execute,
        closure,
        action_phase_ref=action.executing_head.receipt_ref,
    )
    assert result.disposition == "world_committed"
    assert result.admitted_observation_delta == 1
    selected_head = acquisition_chain.select_current_wdi_action_outcome(control, action, result)
    assert selected_head.receipt_phase == "outcome_selected"
    assert len(case.transport_calls) == 1
    method, url, query = case.transport_calls[0]
    assert method == "GET"
    assert url.endswith("/country/USA/indicator/NY.GDP.MKTP.CD")
    assert query == {
        "date": "2024:2024",
        "format": "json",
        "page": "1",
        "per_page": str(GENERIC_WDI_PAGE_SIZE),
    }

    # resume() requires a current job owner for the selected run. Use the same
    # action job ID so its fresh source selector reopens the action head exactly.
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        capability_ref = control._put_json_artifact(
            {"capability": "annual_gdp_candidate_test"},
            kind="runtime.capability_manifest",
            schema_name="CapabilityManifest",
        )
        payload_ref = control._put_json_artifact(
            {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "llm_models": [str(recording["model_id"])],
            },
            kind="runtime.control_job_payload.natural_language_run",
            schema_name="polisyos.runtime.ControlJobPayload",
        )
        actor = "annual-gdp-candidate-test"
        execution_scope = {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": "established",
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "actor_subject": actor,
            "actor_authenticated": True,
            "actor_roles": ["analyst"],
        }
        control._control_store.create_job(
            job_id=action_job_id,
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="dev",
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref=capability_ref,
            payload_ref=payload_ref,
            submitted_by=actor,
            creation_event_payload={
                "job_id": action_job_id,
                "run_id": run_id,
                "job_kind": "natural_language_run",
                "pipeline_id": None,
                "payload_ref": payload_ref,
                "submitted_by": actor,
                "requested_execution_profile": "dev",
                "effective_execution_profile": "dev",
                "policy_flags": {},
                "capability_manifest_ref": capability_ref,
                "execution_scope": execution_scope,
            },
        )
        leased = control._control_store.lease_next_job(worker_id="annual-gdp-reentry-test")
        assert leased is not None and leased.job_id == action_job_id
        with control._control_store.job_execution_fence(
            job_id=action_job_id,
            worker_id=str(leased.lease_owner),
            attempt=leased.attempt,
        ):
            admission = control._control_store.current_execution_job_admission()
            with control._install_execution_scope(admission.scope):
                reentry_ref = under_catalog_source(case.port.reenter, closure, result)

    from polisyos.core import canon
    from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt

    receipt = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(store.get_bytes(reentry_ref))
    )
    refreshed_cycle = receipt.new_cycle
    simulation = refreshed_cycle.simulation
    assert simulation.status == "joint_simulated"
    assert simulation.candidate_simulation_n5_input_ref is not None
    execution_ref_payload = simulation.diagnostics.get(
        "candidate_simulation_execution_selected_ref"
    )
    assert isinstance(execution_ref_payload, dict)
    execution_ref = ArtifactRef.model_validate(execution_ref_payload)

    # Reopen both selected V5 views through a new repository reader, then reopen
    # the persisted numerical result through the same consumer boundary.
    fresh_reader = GenerationSourceRepository(store)
    input_record = fresh_reader.resolve_candidate_simulation_v5(
        ref=simulation.candidate_simulation_n5_input_ref,
        expected_run_id=run_id,
        expected_job_id=action_job_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    execution = fresh_reader.resolve_candidate_simulation_v5(
        ref=execution_ref,
        expected_run_id=run_id,
        expected_job_id=action_job_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    assert type(input_record) is CandidateSimulationN5InputV5
    assert type(execution) is CandidateSimulationExecutionV5
    assert execution.n5_input_ref == simulation.candidate_simulation_n5_input_ref
    assert execution.authority_purpose == "candidate_scenario_n5_only"
    assert input_record.n5.seed == 17
    assert input_record.n5.replications == 2
    assert (
        input_record.n5.horizon.start,
        input_record.n5.horizon.end,
        input_record.n5.horizon.step,
    ) == (0, 0, 1)
    assert input_record.outcome_variable == "global.gdp"
    assert input_record.authority_purpose == "candidate_scenario_n5_only"
    assert execution.authority_purpose == "candidate_scenario_n5_only"
    assert input_record.profile.rule.target_world_slot == "government.balance"
    assert input_record.profile.rule.unit_id == "usd"
    assert input_record.profile.n5.baseline_state["global.gdp"] == pytest.approx(
        row_2024.value_usd,
        rel=2e-7,
    )
    assert input_record.profile.n5.baseline_state["global.gdp"] != 0.0
    assert input_record.profile.context_inputs.world_model_record.valid_time_scope == (
        "not_established"
    )
    assert input_record.profile.context_inputs.world_model_record.authority_status == "limited"
    assert {
        "source_time_not_established",
        "source_to_target_measurement_contract_not_established",
        "causal_coupling_not_established",
    }.issubset(
        input_record.profile.context_inputs.world_model_record.limitations.admissibility_blockers
    )
    views = world_model_artifact_views(input_record.profile.context_inputs.world_model_record)
    snapshot = DataSnapshot.model_validate(load_core_json_artifact(store, views.data_snapshot_ref))
    payload = load_core_json_artifact(store, snapshot.data_ref)
    selected = payload["acquisition"]["selected"]
    assert selected["canonical_variable_id"] == "global.gdp"
    assert selected["value"] == row_2024.value_usd
    assert selected["canonical_unit"] == "usd"
    assert selected["source_time_status"] == "not_established"
    assert selected["reported_time_coordinate"]["year"] == 2024
    assert snapshot.stats["source_time_status"] == "not_established"
    assert snapshot.source_lineage.owner == "acquired_observation_overlay"
    assert observed_annual_change_usd() == 1_486_496_000_000

    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        load_core_json_artifact(store, execution.model_declaration_ref)
    )
    assert declaration.target_unit_id == "usd"
    assert declaration.outcome_unit_id == "usd"
    assert declaration.outcome_variable == "global.gdp"
    assert declaration.assumption == "declared_candidate_scm_not_empirically_grounded"
    assert declaration.outcome_per_target_unit == 0.25
    assert declaration.target_world_slot == "government.balance"
    assert declaration.outcome_variable == "global.gdp"
    assert (
        declaration.target_baseline
        == input_record.profile.n5.baseline_state[declaration.target_world_slot]
    )
    assert (
        declaration.outcome_baseline
        == input_record.profile.n5.baseline_state[declaration.outcome_variable]
    )
    assert declaration.target_unit_id == declaration.outcome_unit_id == "usd"

    numerical = fresh_reader._read_candidate_simulation_v5_numerical_output(
        ref=execution_ref,
        expected_run_id=run_id,
        expected_job_id=action_job_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    assert numerical.execution == execution
    assert numerical.input_record == input_record
    assert numerical.result.receipt.payload_hash == execution.n5_result_content_hash
    assert execution.world_model_record_hash == input_record.materialization.world_model_record_hash
    assert numerical.result.world_model_record_content_hash == (
        input_record.materialization.world_model_record_hash
    )
    assert numerical.result.world_model_record_content_hash == (
        input_record.profile.context_inputs.world_model_record.content_hash
    )
    assert numerical.result.selected_outcomes == (declaration.outcome_variable,)

    # Re-read the state snapshot physically bound by the refreshed WMR. Every
    # N5 baseline slot must resolve through its WMR binding and agree with the
    # persisted input and model declaration; receipt/input echoes are not used
    # as the independent baseline oracle.
    acquired_world = input_record.profile.context_inputs.world_model_record
    views = world_model_artifact_views(acquired_world)
    bound_state_ref = views.bound_state_snapshot_ref
    assert bound_state_ref is not None
    assert bound_state_ref.manifest_profile_sha256 is not None
    state_verification = store.verify(bound_state_ref)
    assert state_verification.ok, state_verification.error
    bound_state_snapshot = StateSnapshot.model_validate(
        load_core_json_artifact(store, bound_state_ref)
    )
    assert store.get_manifest(bound_state_ref).inputs == bound_state_snapshot.lineage_inputs
    assert (
        input_ref_from_artifact_ref(views.data_snapshot_ref, role="input.data_snapshot_ref")
        in bound_state_snapshot.lineage_inputs
    )
    bound_state = load_state_snapshot(store, snapshot_ref=bound_state_ref)
    physical_baseline: dict[str, float] = {}
    for slot_id in sorted(input_record.n5.baseline_state):
        binding = acquired_world.slot_binding(slot_id)
        assert binding is not None and binding.state_path
        state_value = np.asarray(get_state_path(bound_state, binding.state_path))
        assert state_value.size == 1
        physical_baseline[slot_id] = float(state_value.item())
    assert physical_baseline == input_record.n5.baseline_state
    assert declaration.target_baseline == physical_baseline[declaration.target_world_slot]
    assert declaration.outcome_baseline == physical_baseline[declaration.outcome_variable]
    assert physical_baseline[declaration.outcome_variable] == pytest.approx(
        row_2024.value_usd,
        rel=2e-7,
    )
    target_binding = acquired_world.slot_binding(declaration.target_world_slot)
    outcome_binding = acquired_world.slot_binding(declaration.outcome_variable)
    assert target_binding is not None and target_binding.unit == declaration.target_unit_id
    assert outcome_binding is not None and outcome_binding.unit == declaration.outcome_unit_id

    # Independently recompute the declared synthetic SCM from physical bX/bY
    # and the persisted selected action. A $250B output change is far above the
    # float32 spacing at this GDP scale, so a rounded-away effect cannot pass.
    target_value = float(input_record.materialization.value)
    assert target_value == action_value_usd
    physical_target_baseline = physical_baseline[declaration.target_world_slot]
    physical_outcome_baseline = physical_baseline[declaration.outcome_variable]
    expected_effect = declaration.outcome_per_target_unit * (
        target_value - physical_target_baseline
    )
    expected_outcome = physical_outcome_baseline + expected_effect
    assert expected_effect == 250_000_000_000.0
    assert expected_outcome - physical_outcome_baseline == expected_effect
    # The resolved CPU profile disables x64, so compare outputs on its float32
    # lattice with a two-ULP envelope at the GDP result magnitude.
    expected_float32_outcome = np.float32(expected_outcome)
    float32_spacing = float(np.spacing(expected_float32_outcome))
    result_abs_tolerance_usd = 2.0 * float32_spacing
    assert expected_effect > 100.0 * result_abs_tolerance_usd
    assert np.float32(expected_outcome) != np.float32(physical_outcome_baseline)
    selected_decisions = tuple(
        item for item in numerical.result.engine_decisions if item.decision == "selected"
    )
    assert len(selected_decisions) == 1
    atom_ids = (input_record.materialization.derived_n5_atom.intervention_id,)
    assert atom_ids[0] in numerical.result.marginal_effects
    expected_seeds = (17, 18)
    trajectories = tuple(
        item
        for item in numerical.result.trajectories
        if item.atom_ids == atom_ids and item.run_level in {"individual", "joint"}
    )
    assert trajectories
    assert any(trajectory.run_level == "joint" for trajectory in trajectories)
    for trajectory in trajectories:
        assert trajectory.engine_kind == selected_decisions[0].engine_kind
        assert trajectory.diagnostics["actual_replications"] == 2
        assert trajectory.diagnostics["replication_seeds"] == list(expected_seeds)
        assert len(trajectory.points) == 1
        for point in trajectory.points:
            assert point.step == input_record.n5.horizon.start
            if trajectory.run_level == "individual":
                assert numerical.result.marginal_effects[atom_ids[0]][point.step][
                    declaration.outcome_variable
                ] == pytest.approx(
                    expected_effect,
                    rel=0.0,
                    abs=result_abs_tolerance_usd,
                )
            assert point.outcomes[declaration.outcome_variable] == pytest.approx(
                float(expected_float32_outcome),
                rel=0.0,
                abs=result_abs_tolerance_usd,
            )
            assert point.effect[declaration.outcome_variable] == pytest.approx(
                expected_effect,
                rel=0.0,
                abs=result_abs_tolerance_usd,
            )
            assert point.replication_sampling is not None
            sampling = point.replication_sampling
            assert sampling.replicate_count == 2
            assert sampling.seeds == expected_seeds
            assert len(sampling.samples) == 2
            sample_outcomes = [
                sample.outcomes[declaration.outcome_variable] for sample in sampling.samples
            ]
            sample_effects = [
                sample.effects[declaration.outcome_variable] for sample in sampling.samples
            ]
            expected_outcome_se = statistics.stdev(sample_outcomes) / math.sqrt(
                len(sample_outcomes)
            )
            expected_effect_se = statistics.stdev(sample_effects) / math.sqrt(len(sample_effects))
            assert sampling.status == "estimated"
            assert tuple(sample.seed for sample in sampling.samples) == expected_seeds
            for sample in sampling.samples:
                assert sample.outcomes[declaration.outcome_variable] == pytest.approx(
                    float(expected_float32_outcome),
                    rel=0.0,
                    abs=result_abs_tolerance_usd,
                )
                assert sample.effects[declaration.outcome_variable] == pytest.approx(
                    expected_effect,
                    rel=0.0,
                    abs=result_abs_tolerance_usd,
                )
            # The persisted standard error is recomputed from the stored draws
            # in binary64; the float32 output ULP tolerance above does not apply.
            assert sampling.outcomes_standard_error[declaration.outcome_variable] == pytest.approx(
                expected_outcome_se, rel=1e-12, abs=1e-12
            )
            assert sampling.effects_standard_error[declaration.outcome_variable] == pytest.approx(
                expected_effect_se, rel=1e-12, abs=1e-12
            )
    assert SOFTWARE_FIXTURE_BOUNDARY["source_rights"] == "not_established"
    assert SOFTWARE_FIXTURE_BOUNDARY["source_currentness"] == "not_established"
