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

pytest_plugins = ("tests._helpers.acquisition_served_history",)


@pytest.mark.integration
def test_annual_gdp_source_persists_public_rows_and_refuses_provenance_relabel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real source owner preserves observed provenance with candidate-only authority."""
    from polisyos.core import canon
    from polisyos.core.artifacts import FileSystemCAS, load_core_json_artifact
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.data_forge.read_api import catalog
    from polisyos.fabric.connectors.cache import ResultSerializer
    from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY, SlotKind
    from polisyos.ir.kernel.time_semantics import TimeSemantics
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.runtime.quality.candidate_acquisition_source import (
        CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3,
        _write_options,
        read_candidate_acquisition_source,
    )
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
    fixture = build_lane01_candidate_source(
        tmp_path / "actual-wdi-source",
        monkeypatch,
        store=store,
        profile=GDP_PROFILE,
        compiler_input=GDP_COMPILER_INPUT,
        response_body=wdi_response_for_year(2024),
    )
    source = fixture.source
    assert source.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3
    assert source.observation_class is catalog.ObservationProvenanceClass.OBSERVED
    assert source.status == "candidate_only"
    assert source.source_currentness == "source_currentness_not_established"
    assert source.observation == observations[2024].value_usd
    fresh = FileSystemCAS(store.root)
    assert read_candidate_acquisition_source(fresh, source_ref=fixture.source_ref) == source
    forged = source.model_copy(
        update={"observation_class": catalog.ObservationProvenanceClass.MODEL_OUTPUT}
    )
    forged_ref = store.put_json(
        forged,
        _write_options(forged),
        canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="candidate_source_provenance_mismatch"):
        read_candidate_acquisition_source(fresh, source_ref=forged_ref)

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
    import sys
    import traceback
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
    from polisyos.runtime.quality import acquisition_planner, generation_cycle, semantic_epoch
    from polisyos.runtime.quality.acquisition_executor import (
        SemanticEpochAdmissionResolutionError,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionCandidateWorldRefresh,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioSetToRule,
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
        CandidateSimulationSyntheticModelDeclarationV1,
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

    # The shared WMR fixture has no GDP state field. Add explicit test-owned
    # scalar baselines so the WDI observation and registered tax-rate slot can
    # be bound physically; neither value is an empirical or authority claim.
    base_payload = dict(wmr_fixture.FABRIC_PAYLOAD)
    base_payload["gdp"] = 0.0
    base_payload["tax_rate"] = 0.5
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
    problem = acquisition_chain.controlled_served_wdi_problem(
        problem_seed,
        raw_request=acquisition_chain.SERVED_WDI_FISCAL_REQUEST,
    )
    assert problem.schema_version == "policyos.runtime.design_problem.v3"
    problem_payload = problem.model_dump(mode="json")
    gdp_scope_request = (
        "For USA in calendar year 2024, assess annual nominal GDP in current US dollars "
        "and a candidate tax_relief_rate set-to on global.tax_rate from a declared 0.5 "
        "ratio baseline to 0.0. Any USD response is a declared synthetic SCM assumption."
    )
    candidate_only_request = acquisition_chain.SERVED_WDI_CANDIDATE_ONLY_SOURCE
    problem_payload["domain"] = "economic"
    problem_payload["problem_statement"] = (
        "Assess a candidate-only USA 2024 annual nominal GDP scenario in current US dollars "
        "with a registered tax-rate set-to from 0.5 to 0.0."
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
    problem_payload["candidate_lever_space"] = {
        "allowed_operator_kinds": ["tax_relief_rate"],
        "candidate_levers": [
            {
                "lever_id": "annual_gdp_tax_relief_rate",
                "operator_kind": "tax_relief_rate",
                "instrument": "Registered candidate tax relief rate",
                "target_slot": "global.tax_rate",
            }
        ],
    }
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
    assert problem.candidate_lever_space.allowed_operator_kinds == ["tax_relief_rate"]
    assert problem.candidate_lever_space.candidate_levers[0].target_slot == "global.tax_rate"
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
        candidate_rule=CandidateScenarioSetToRule(
            operator_kind="tax_relief_rate",
            parameter_id="rate",
            target_world_slot="global.tax_rate",
            unit_id="ratio",
            minimum=0,
            maximum=0,
        ),
    )
    tax_rate_action_value = 0.0
    assert profile.rule.operator_kind == "tax_relief_rate"
    assert profile.rule.parameter_id == "rate"
    assert profile.rule.target_world_slot == "global.tax_rate"
    assert profile.rule.unit_id == "ratio"
    assert profile.rule.minimum == profile.rule.maximum == 0
    assert profile.n5.baseline_state["global.tax_rate"] == 0.5
    base_profile_world = profile.context_inputs.world_model_record
    base_profile_views = world_model_artifact_views(base_profile_world)
    base_profile_state_ref = base_profile_views.bound_state_snapshot_ref
    assert base_profile_state_ref is not None
    base_profile_state = load_state_snapshot(store, snapshot_ref=base_profile_state_ref)
    base_tax_binding = base_profile_world.slot_binding("global.tax_rate")
    assert base_tax_binding is not None and base_tax_binding.unit == "ratio"
    base_tax_value = np.asarray(get_state_path(base_profile_state, base_tax_binding.state_path))
    assert base_tax_value.size == 1 and float(base_tax_value.item()) == 0.5
    declaration_payload = declaration.model_dump(mode="json", exclude={"content_hash"})
    declaration_payload.update(
        {
            "outcome_per_target_unit": -500_000_000_000.0,
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

    # Keep the captured N4 recording as the immutable parent while binding each
    # selected stage to the same test-only annual GDP/tax-rate candidate.
    def annual_gdp_tax_response(
        raw: str,
        *,
        outcome_variable: str,
        labor_problem: Any | None = None,
    ) -> str:
        if outcome_variable != "global.gdp" or labor_problem is not None:
            raise ValueError("annual_gdp_tax_fixture_transform_scope_mismatch")
        payload = json.loads(raw)
        policy_spec = payload["policy_spec"]
        interventions = policy_spec["interventions"]
        tax_actions = [item for item in interventions if item.get("kind") == "tax_relief_rate"]
        assert len(tax_actions) == 1
        tax_action = tax_actions[0]
        original_intervention_id = tax_action["intervention_id"]
        parameters = policy_spec["parameters"]
        rate_parameters = [
            item
            for item in parameters
            if item.get("intervention_id") == original_intervention_id
            and item.get("param_path") == "rate"
        ]
        assert len(rate_parameters) == 1
        test_intervention_id = "annual_gdp_tax_relief_rate"
        tax_action.update(
            {
                "intervention_id": test_intervention_id,
                "schedule": {"start_step": 0, "duration_steps": 1},
                "params": {"rate": 0},
                "notes": [
                    "do.target=global.tax_rate sign=decrease outcome=global.gdp "
                    "effect_path=global.tax_rate,global.gdp; test-owned candidate set-to "
                    "from ratio baseline 0.5 to 0 under a declared synthetic SCM"
                ],
            }
        )
        rate_parameters[0].update(
            {
                "intervention_id": test_intervention_id,
                "param_id": "rate",
                "param_path": "rate",
                "default_value": "0",
                "min_value": "0",
                "max_value": "0.5",
            }
        )
        policy_spec.update(
            {
                "policy_id": "annual_gdp_tax_rate_candidate_policy",
                "description": (
                    "Candidate-only software fixture: set the registered global tax-rate "
                    "ratio from 0.5 to 0.0; the declared GDP response is synthetic."
                ),
                "labels": ["synthetic", "candidate_only", "usa", "annual_gdp", "2024"],
                "interventions": [tax_action],
                "parameters": rate_parameters,
            }
        )
        frame = payload["problem_frame"]
        frame.update(
            {
                "problem_id": problem.design_problem_id,
                "domain": "economic",
                "narrative": problem.problem_statement,
                "labels": ["synthetic", "candidate_only", "usa", "annual_gdp", "2024"],
                "objectives": [
                    {
                        "objective_id": "annual_gdp",
                        "metric_id": "annual_gdp",
                        "direction": "maximize",
                        "weight": "1.0",
                    }
                ],
            }
        )
        model_spec = payload["model_spec"]
        model_spec.update(
            {
                "model_id": "annual_gdp_tax_rate_candidate_model",
                "data_snapshot_ref": str(base_views.data_snapshot_ref.artifact_id),
                "registry_bundle_ref": str(base_views.registry_bundle_ref.artifact_id),
                "time_semantics": base_model.time_semantics.model_dump(mode="json"),
                "labels": ["synthetic", "candidate_only", "usa", "annual_gdp", "2024"],
                "assumptions": [
                    {
                        "assumption_id": "tax_rate_to_annual_gdp_synthetic_coefficient",
                        "assumption_type": "structural",
                        "description": (
                            "Declared test-only SCM coefficient: -500,000,000,000 current "
                            "USD per unit tax-rate ratio. It is not an empirical or "
                            "policy-effect estimate."
                        ),
                        "confidence": "0.0",
                        "sensitivity_flag": True,
                    }
                ],
            }
        )
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    original_controlled_recording = acquisition_chain.controlled_served_wdi_generation_recording

    def _set_recording_response(response: dict[str, Any], body: dict[str, Any]) -> None:
        raw_response = json.dumps(body, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = raw_response
        response["raw_response_hash"] = gy_content_hash(raw_response)

    def annual_gdp_tax_recording(
        source_recording: dict[str, Any],
        *,
        outcome_variable: str,
        labor_problem: Any | None = None,
    ) -> dict[str, Any]:
        controlled = original_controlled_recording(
            source_recording,
            outcome_variable=outcome_variable,
            labor_problem=labor_problem,
        )
        if outcome_variable != "global.gdp" or labor_problem is not None:
            raise ValueError("annual_gdp_tax_fixture_recording_scope_mismatch")
        responses = controlled["responses"]
        formalizer_parent_hashes = {
            acquisition_chain._SERVED_WDI_FIRST_FORMALIZER_HASH,
            acquisition_chain._SERVED_WDI_STAGE_PARENTS["formalizer"][1],
        }
        selected_formalizer_indexes = [
            index
            for index, (source_response, _) in enumerate(
                zip(source_recording["responses"], responses, strict=True)
            )
            if source_response.get("role") == "formalizer"
            and source_response.get("raw_response_hash") in formalizer_parent_hashes
        ]
        if len(selected_formalizer_indexes) != 2:
            raise ValueError("annual_gdp_tax_fixture_formalizer_denominator_mismatch")
        formalizers = [responses[index] for index in selected_formalizer_indexes]
        selected_stage_parent_hashes = {
            stage: acquisition_chain._SERVED_WDI_STAGE_PARENTS[stage][1]
            for stage in ("draft", "drafter_multipass", "critic")
        }
        for source_response, response in zip(source_recording["responses"], responses, strict=True):
            role = response.get("role")
            source_hash = source_response.get("raw_response_hash")
            if role == "draft" and source_hash == selected_stage_parent_hashes["draft"]:
                body = json.loads(response["raw_response"])
                body.update(
                    {
                        "draft_id": "annual-gdp-usa-2024-tax-rate",
                        "problem_frame_ref": problem.design_problem_id,
                        "narrative": problem.problem_statement,
                        "rationale": (
                            "This candidate-only software fixture sets global.tax_rate from "
                            "a physically bound 0.5 ratio baseline to 0.0. The declared "
                            "synthetic coefficient maps the change to 250 billion current "
                            "USD; it makes no empirical or causal claim."
                        ),
                        "confidence": 0.0,
                        "alternatives_considered": [
                            "No-change baseline retained for the N5 comparison."
                        ],
                        "interventions": [
                            {
                                "name": "Annual GDP tax-rate candidate set-to",
                                "description": (
                                    "Set the registered global.tax_rate ratio from 0.5 to 0.0."
                                ),
                                "mechanism_type": "tax_relief_rate",
                                "parameters": {
                                    "rate": 0,
                                    "target_world_slot": "global.tax_rate",
                                    "sign": "decrease",
                                    "outcome_slots": ["global.gdp"],
                                    "effect_path": ["global.tax_rate", "global.gdp"],
                                },
                                "rationale": (
                                    "A declared test-only synthetic SCM provides the USD "
                                    "response; this is not an empirical policy effect."
                                ),
                                "target_population": "USA national economy",
                            }
                        ],
                    }
                )
                _set_recording_response(response, body)
            elif (
                role == "drafter_multipass"
                and source_hash == selected_stage_parent_hashes["drafter_multipass"]
            ):
                body = json.loads(response["raw_response"])
                finding = dict(body["findings"][0])
                finding.update(
                    {
                        "anchor": "annual_gdp_tax_rate_synthetic_coefficient",
                        "description": (
                            "The 250 billion USD change is computed from an explicit synthetic "
                            "coefficient and a 0.5 ratio delta, not independent evidence."
                        ),
                        "affected_intervention": "annual_gdp_tax_relief_rate",
                        "suggested_fix": (
                            "Keep the result candidate-only until a measurement contract and "
                            "causal coupling are independently established."
                        ),
                    }
                )
                body["findings"] = [finding]
                _set_recording_response(response, body)
            elif role == "critic" and source_hash == selected_stage_parent_hashes["critic"]:
                body = json.loads(response["raw_response"])
                issue = dict(body["issues"][0])
                issue.update(
                    {
                        "issue_id": "ANNUAL-GDP-SYNTHETIC-SCM-001",
                        "category": "ALIGNMENT",
                        "severity": "WARNING",
                        "message": (
                            "The tax-rate to GDP coefficient is a declared software-fixture "
                            "assumption, not measured or causally grounded evidence."
                        ),
                        "location": "model_spec.assumptions",
                        "suggestion": (
                            "Preserve limited candidate-only status and do not publish this "
                            "synthetic effect as a policy estimate."
                        ),
                    }
                )
                body.update(
                    {
                        "verdict": "NEEDS_REVISION",
                        "alignment_score": 0.0,
                        "completeness_score": 0.0,
                        "overall_quality": 0.0,
                        "problem_frame_ref": problem.design_problem_id,
                        "report_id": "annual_gdp_tax_rate_candidate_critic",
                        "reflexion_hint": (
                            "The recorded ratio action is unit-consistent, but its USD effect "
                            "is synthetic and remains inadmissible as a causal estimate."
                        ),
                    }
                )
                body["issues"] = [issue]
                _set_recording_response(response, body)
        final_ir_ref = gy_content_hash(json.loads(formalizers[-1]["raw_response"]))
        selected_critics = [
            response
            for source_response, response in zip(
                source_recording["responses"], responses, strict=True
            )
            if source_response.get("role") == "critic"
            and source_response.get("raw_response_hash") == selected_stage_parent_hashes["critic"]
        ]
        if len(selected_critics) != 1:
            raise ValueError("annual_gdp_tax_fixture_critic_denominator_mismatch")
        critic = selected_critics[0]
        critic_body = json.loads(critic["raw_response"])
        critic_body["ir_ref"] = final_ir_ref
        _set_recording_response(critic, critic_body)
        from tools.quality.validation import (
            check_layer3_gy_design_generation_contract as n4_contract,
        )

        identity_seed = gy_content_hash(
            {
                "parent_recording_id": controlled["derived_from_recording_id"],
                "parent_content_hash": controlled["derived_from_content_hash"],
                "problem_id": problem.design_problem_id,
                "response_hashes": [item.get("raw_response_hash") for item in responses],
                "target": "global.tax_rate",
                "outcome": "global.gdp",
            }
        ).removeprefix("sha256:")[:20]
        fixture_id = f"synthetic_annual_gdp_tax_n4_{identity_seed}"
        controlled.update(
            {
                "design_problem_id": problem.design_problem_id,
                "fixture_id": fixture_id,
                "recording_id": fixture_id,
                "recording_source": "synthetic_annual_gdp_tax_overlay_of_recorded_capture",
            }
        )
        controlled["recording_content_hash"] = gy_content_hash(
            {key: value for key, value in controlled.items() if key != "recording_content_hash"}
        )
        n4_contract._validate_recording_fixture(controlled)
        return controlled

    monkeypatch.setattr(
        acquisition_chain,
        "_controlled_wdi_trinity_response",
        annual_gdp_tax_response,
    )
    monkeypatch.setattr(
        acquisition_chain,
        "controlled_served_wdi_generation_recording",
        annual_gdp_tax_recording,
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
        fixture_target_world_slots=("global.tax_rate",),
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
    gdp_epoch_scope = {
        "domain": "fiscal",
        "jurisdiction": source_profile.country_code,
        "year": source_profile.year,
        "population": source_profile.population,
    }
    case = under_catalog_source(
        acquisition_chain.make_wdi_port_case,
        tmp_path / "wdi",
        monkeypatch,
        control=control,
        closure=closure,
        candidate_world_refreshes=(refresh,),
        candidate_scenario_generation=True,
        candidate_generation_recording=recording,
        epoch_scope_payload=gdp_epoch_scope,
        authority_purpose="candidate_simulation",
    )
    assert json.loads(case.selected.epoch_scope_identity.identity_bytes) == gdp_epoch_scope
    assert case.selected.authority_purpose == "candidate_simulation"
    fixture_baseline = case.authority.baseline_path.resolve(strict=True)
    assert case.authority.repo_root.resolve(strict=True) == fixture_repo_root
    assert case.bridge.repo_root.resolve(strict=True) == fixture_repo_root
    assert fixture_baseline.is_relative_to(fixture_repo_root)
    assert case.authority.registry_path.resolve(strict=True).is_relative_to(fixture_repo_root)
    assert (catalog_owner_root / DEFAULT_L1_DCAT_PATH).is_file()
    assert (catalog_owner_root / DEFAULT_L1_DCAT_PATH).resolve(strict=True) != fixture_baseline
    assert case.transport_calls == []

    observed_semantic_admission_codes: list[str] = []
    bridge_admit = case.bridge.admit

    def observe_semantic_admission_code(*args: Any, **kwargs: Any) -> Any:
        try:
            return bridge_admit(*args, **kwargs)
        except SemanticEpochAdmissionResolutionError as exc:
            observed_semantic_admission_codes.append(exc.code)
            raise

    monkeypatch.setattr(case.bridge, "admit", observe_semantic_admission_code)
    finalizer_exceptions: list[str] = []
    finalizer_code = semantic_epoch.SemanticEpochService.finalize_admitted_epoch.__code__
    prior_trace = sys.gettrace()

    def observe_finalizer_exceptions(frame, event, arg):
        prior_local = prior_trace(frame, event, arg) if prior_trace is not None else None
        is_finalizer = (
            event == "call"
            and frame.f_code is finalizer_code
            and frame.f_code.co_filename == finalizer_code.co_filename
            and frame.f_code.co_name == "finalize_admitted_epoch"
        )
        if not is_finalizer and prior_local is None:
            return None

        def observe_frame(frame, event, arg):
            nonlocal prior_local
            if prior_local is not None:
                prior_local = prior_local(frame, event, arg)
            if is_finalizer and event == "exception":
                _exception_type, exception, _exception_traceback = arg
                rendered = "".join(
                    traceback.TracebackException.from_exception(
                        exception,
                        capture_locals=False,
                    ).format(chain=True)
                )
                finalizer_exceptions.append(
                    f"type={type(exception).__qualname__}; "
                    f"code={getattr(exception, 'code', None)!r}\n{rendered}"
                )
            return observe_frame if is_finalizer or prior_local is not None else None

        return observe_frame

    try:
        sys.settrace(observe_finalizer_exceptions)
        negative = under_catalog_source(case.port.execute, closure)
    finally:
        sys.settrace(prior_trace)

    finalizer_diagnostic = (
        "\n".join(finalizer_exceptions) if finalizer_exceptions else "none observed"
    )
    assert negative.disposition == "quarantined_no_growth", (
        f"unexpected acquisition disposition {negative.disposition!r}; "
        f"finalize_admitted_epoch exceptions:\n{finalizer_diagnostic}"
    )
    if case.bridge.has_deferred_admission(closure):
        _deferred_ref, deferral, _attempt = case.bridge._load_deferral(closure)
        assert deferral.negative_receipt.failure_codes == ("policy_admission_missing",), (
            "unexpected persisted semantic-epoch refusal: "
            f"{deferral.negative_receipt.failure_codes!r}; "
            f"finalize_admitted_epoch exceptions:\n{finalizer_diagnostic}"
        )
        assert observed_semantic_admission_codes == [], (
            f"unexpected bridge admission exception codes "
            f"{observed_semantic_admission_codes!r}; "
            f"finalize_admitted_epoch exceptions:\n{finalizer_diagnostic}"
        )
    else:
        pytest.fail(
            "annual GDP expected a persisted policy_admission_missing deferral; "
            f"observed SemanticEpochAdmissionResolutionError.code="
            f"{observed_semantic_admission_codes!r}; "
            f"finalize_admitted_epoch exceptions:\n{finalizer_diagnostic}"
        )
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
    assert input_record.profile.rule.operator_kind == "tax_relief_rate"
    assert input_record.profile.rule.parameter_id == "rate"
    assert input_record.profile.rule.target_world_slot == "global.tax_rate"
    assert input_record.profile.rule.unit_id == "ratio"
    assert input_record.profile.rule.minimum == input_record.profile.rule.maximum == 0
    assert input_record.profile.n5.baseline_state["global.tax_rate"] == 0.5
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
    assert declaration.target_unit_id == "ratio"
    assert declaration.outcome_unit_id == "usd"
    assert declaration.outcome_variable == "global.gdp"
    assert declaration.assumption == "declared_candidate_scm_not_empirically_grounded"
    assert declaration.outcome_per_target_unit == -500_000_000_000.0
    assert declaration.target_world_slot == "global.tax_rate"
    assert declaration.outcome_variable == "global.gdp"
    assert (
        declaration.target_baseline
        == input_record.profile.n5.baseline_state[declaration.target_world_slot]
    )
    assert (
        declaration.outcome_baseline
        == input_record.profile.n5.baseline_state[declaration.outcome_variable]
    )
    assert declaration.target_unit_id == "ratio"
    assert declaration.outcome_unit_id == "usd"

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
    assert physical_baseline[declaration.target_world_slot] == 0.5
    target_binding = acquired_world.slot_binding(declaration.target_world_slot)
    outcome_binding = acquired_world.slot_binding(declaration.outcome_variable)
    assert target_binding is not None and target_binding.unit == declaration.target_unit_id
    assert outcome_binding is not None and outcome_binding.unit == declaration.outcome_unit_id

    # Independently recompute the declared synthetic SCM from physical bX/bY
    # and the persisted selected tax-rate action. The 250 billion USD change is
    # far above float32 spacing at this GDP scale, so a rounded-away effect cannot pass.
    target_value = float(input_record.materialization.value)
    assert target_value == tax_rate_action_value == 0.0
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


@pytest.mark.integration
def test_annual_gdp_candidate_experiment_reaches_distinct_fresh_api_n5_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway,
) -> None:
    """Consume one captured annual observation through the bounded candidate action route."""
    from dataclasses import replace
    from decimal import Decimal
    from types import SimpleNamespace

    import numpy as np

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.contracts import DataSnapshot
    from polisyos.core.contracts.fabric import CandidateAcquisitionSourceDataSnapshotLineage
    from polisyos.core.contracts.runtime import (
        RunCandidateSimulationAcquisitionHistoryEntryV5,
        RunDetailsResponse,
    )
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.foundry.execute.executor import load_state_snapshot
    from polisyos.runtime.http.services import acquisition_surface_execution
    from polisyos.runtime.quality import acquisition_planner, generation_cycle
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedExperimentPolicyTemplate,
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.runtime.quality.data_snapshot_lineage import (
        DataSnapshotSourceRowNotEstablishedError,
        validate_data_snapshot_owner_lineage,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers import acquisition_served_history as served
    from tests._helpers import world_model_record as wmr_fixture
    from tests._helpers.annual_gdp_candidate import (
        ANNUAL_GDP_VALUE_USD,
        ANNUAL_GDP_WDI_PROFILE,
        annual_gdp_candidate_problem,
        annual_gdp_catalog_source,
        build_annual_gdp_candidate_profile,
        build_annual_gdp_candidate_provider,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        run_candidate_experiment_served_execution,
    )
    from tests._helpers.lane01_candidate_action_served import build_candidate_experiment_issuer_port
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        run_candidate_experiment_action_oracle,
    )

    # Declared scenario baselines are test inputs, never inferred measurements.
    base_payload = dict(wmr_fixture.FABRIC_PAYLOAD)
    base_payload.update(gdp=0.0, tax_rate=0.5)
    monkeypatch.setattr(wmr_fixture, "FABRIC_PAYLOAD", base_payload)
    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
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
    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "annual-gdp-source",
        outcome_variable="global.gdp",
        include_owner_slot_manifest=True,
    )
    problem = annual_gdp_candidate_problem()
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="annual-gdp-candidate-experiment",
        total_units=5,
        protected_units=1,
    )
    capture = wdi_response_for_year(2024)
    observed: dict[str, Any] = {}

    def serve_action(**values: Any) -> None:
        control = values["control"]
        run_id = str(values["run_id"])
        assert values["job"].kind == "natural_language_run"
        assert values["job"].state == "completed"
        issuer = build_candidate_experiment_issuer_port(
            tmp_path=tmp_path / "annual-gdp-issuer",
            artifact_store=control._artifact_store,
            source_profile=ANNUAL_GDP_WDI_PROFILE,
        )
        quota_profile = control._llm_producer_settlement_store.snapshot_safe().invocation_profiles[
            run_id
        ]
        template = CandidateUnpricedExperimentPolicyTemplate(
            tenant_id=served.TENANT,
            cell_id=served.CELL,
            authority_entry_id=issuer.entry.entry_id,
            authority_registry_sha256=issuer.registry.content_sha256,
            authority_provision_sha256=issuer.authority.provision_content_sha256,
            attempt_id=issuer.port._provision.live_harness_receipts[0].attempt_id,
            max_http_response_bytes=65_536,
            max_http_decompressed_bytes=65_536,
            max_http_timeout_seconds=15.0,
            max_standard_n5_invocations=quota_profile.total_units - quota_profile.protected_units,
            max_metered_reentry_usd=Decimal("1.00"),
        )
        policy_owner = SimpleNamespace(
            issuer=issuer,
            template=template,
            source_profiles=SourceProfileRegistry.get_instance(),
        )
        original_providers = control._registry_providers
        control._registry_providers = replace(
            original_providers,
            source_profiles=policy_owner.source_profiles,
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(template,),
        )
        try:
            with monkeypatch.context() as scoped:

                def current_issuer(*, control_service: Any) -> Any:
                    assert control_service is control
                    return issuer.port

                scoped.setattr(
                    acquisition_surface_execution,
                    "build_production_world_bank_wdi_execution_port",
                    current_issuer,
                )
                refs = prepare_candidate_experiment_policies_for_completed_job(
                    control_service=control,
                    source_job_id=values["job"].job_id,
                )
                assert len(refs) == 1
                policy_ref, policy = resolve_current_candidate_unpriced_policy(
                    control_service=control,
                    scope=read_candidate_unpriced_policy(
                        store=control._artifact_store,
                        event_log=control._diagnostic_event_log,
                        ref=refs[0],
                    ).scope,
                )
                assert policy.observed_admission is False
                assert policy.publication_authority is False
                assert policy.information_value == policy.monetary_cost == "not_established"

                def fresh_numeric_reader(**reader_values: Any) -> None:
                    reader_control = reader_values["control"]
                    history = reader_values["history"]
                    assert reader_control is not control
                    assert reader_control._artifact_store is not control._artifact_store
                    evaluation = history.evaluation
                    assert evaluation is not None
                    selected = evaluation.selected
                    n5_input = evaluation.input_record
                    world = n5_input.profile.context_inputs.world_model_record
                    views = world_model_artifact_views(world)
                    assert views.bound_state_snapshot_ref is not None
                    state = load_state_snapshot(
                        reader_control._artifact_store,
                        snapshot_ref=views.bound_state_snapshot_ref,
                    )
                    assert float(state.gdp) == pytest.approx(ANNUAL_GDP_VALUE_USD, rel=2e-7)
                    assert float(state.tax_rate) == 0.5
                    assert n5_input.n5.baseline_state["global.gdp"] == float(state.gdp)
                    assert n5_input.n5.baseline_state["global.tax_rate"] == 0.5
                    assert n5_input.materialization.value == 0.0
                    source_job = reader_control._control_store.get_job(history.origin.source_job_id)
                    assert source_job is not None
                    response = reader_values["client"].get(
                        f"/api/v1/runs/{source_job.progress['core_run_id']}",
                        headers=reader_values["headers"],
                    )
                    assert response.status_code == 200, response.text
                    projection = RunDetailsResponse.model_validate_json(
                        response.content
                    ).run.candidate_simulation
                    assert projection is not None and projection.artifact_status == "resolved"
                    assert projection.publication_authority is False
                    entries = tuple(
                        row
                        for row in projection.acquisition_history
                        if type(row) is RunCandidateSimulationAcquisitionHistoryEntryV5
                        and row.candidate_source_ref == history.action.candidate_source_ref
                        and row.selected_evaluation is not None
                        and row.selected_evaluation.n5_result_ref == selected.n5_result_ref
                    )
                    assert len(entries) == 1
                    entry = entries[0]
                    assert entry.observed_admission is False
                    assert entry.publication_authority is False
                    observation = entry.selected_n5_observation
                    assert observation is not None and observation.result_body_status == "resolved"
                    body = observation.result_body
                    assert body is not None and body.artifact_ref == selected.n5_result_ref
                    assert body.outcome_units == {"global.gdp": "usd"}
                    assert body.unit_provenance == "declared_candidate_model"
                    assert body.publication_authority is False
                    assert body.candidate_status == "candidate_unverified"
                    # Independent arithmetic on the physical pre-action state.
                    expected_effect = -500_000_000_000.0 * (0.0 - 0.5)
                    assert expected_effect == 250_000_000_000.0
                    expected_outcome = np.float32(float(state.gdp) + expected_effect)
                    tolerance = 2.0 * float(np.spacing(expected_outcome))
                    assert expected_effect > 100 * tolerance
                    assert np.float32(state.gdp) != expected_outcome
                    assert any(row.run_level == "joint" for row in body.trajectories)
                    for trajectory in body.trajectories:
                        assert len(trajectory.points) == 1
                        point = trajectory.points[0]
                        assert point.step == 0
                        assert point.outcomes["global.gdp"] == pytest.approx(
                            float(expected_outcome), rel=0.0, abs=tolerance
                        )
                        assert point.effects["global.gdp"] == pytest.approx(
                            expected_effect, rel=0.0, abs=tolerance
                        )
                    observed["fresh_numeric_body"] = body

                def execute_after_replay(**execution_values: Any) -> None:
                    execution = run_candidate_experiment_served_execution(
                        values=execution_values["values"],
                        origin=execution_values["origin"],
                        request=execution_values["request"],
                        decision_ref=execution_values["decision_ref"],
                        policy_owner=policy_owner,
                        monkeypatch=scoped,
                        source_profile=ANNUAL_GDP_WDI_PROFILE,
                        wdi_response_bytes=capture,
                        fresh_reader_observer=fresh_numeric_reader,
                    )
                    history = execution.terminal_history
                    assert history.terminal.terminal_outcome == "candidate_reentry_completed"
                    assert execution.current_action.status == "completed"
                    assert execution.current_action.evaluation_disposition == "new"
                    assert history.action.admitted_observation_delta == 0
                    assert history.action.observed_admission is False
                    assert history.action.publication_authority is False
                    source = history.source
                    assert source.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3
                    assert source.observation_class == "observed"
                    assert source.observation == ANNUAL_GDP_VALUE_USD
                    assert source.year == 2024 and source.canonical_unit == "usd"
                    assert control._artifact_store.get_bytes(source.raw_source_ref) == capture
                    assert history.evaluation is not None
                    n5_input = history.evaluation.input_record
                    views = world_model_artifact_views(
                        n5_input.profile.context_inputs.world_model_record
                    )
                    snapshot = DataSnapshot.model_validate(
                        load_core_json_artifact(control._artifact_store, views.data_snapshot_ref)
                    )
                    assert (
                        type(snapshot.source_lineage)
                        is CandidateAcquisitionSourceDataSnapshotLineage
                    )
                    payload = load_core_json_artifact(control._artifact_store, snapshot.data_ref)
                    assert payload["_policyos_candidate_acquisition"]["schema_version"] == (
                        "policyos.runtime.candidate_acquisition_data_state.v2"
                    )
                    assert payload["acquisition"]["selected"]["provenance_class"] == "observed"
                    with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
                        validate_data_snapshot_owner_lineage(
                            control._artifact_store, views.data_snapshot_ref, snapshot
                        )
                    assert execution.execution_owner.transport_calls == [
                        (
                            "GET",
                            "https://api.worldbank.org/v2/country/USA/indicator/NY.GDP.MKTP.CD",
                            {
                                "date": "2024:2024",
                                "format": "json",
                                "page": "1",
                                "per_page": "1000",
                            },
                        )
                    ]
                    observed["execution"] = execution

                observed.update(
                    run_candidate_experiment_action_oracle(
                        tmp_path=tmp_path,
                        values=values,
                        policy_ref=policy_ref,
                        monkeypatch=scoped,
                        idempotency_key="annual-gdp-candidate-experiment-authority",
                        after_replay=execute_after_replay,
                    )
                )
        finally:
            control._registry_providers = original_providers

    with annual_gdp_catalog_source(source_inputs.root, monkeypatch) as prepared:
        result = served._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source_inputs.root,
            prepared_catalog=prepared,
            provider_mode="synthetic_settled_candidate",
            seed_only_context_observer=serve_action,
            run_budget_usd=5.0,
            run_budget_scope="metered_paid_producers_and_bounded_candidate",
            candidate_acquisition_intent="bounded_experiment_voi_unknown",
            invocation_quota_policy=quota,
            seed_problem=problem,
            candidate_profile_builder=build_annual_gdp_candidate_profile,
            candidate_provider_builder=build_annual_gdp_candidate_provider,
        )
    assert result is not None and observed["source_status"] == "completed"
    assert "fresh_numeric_body" in observed and "execution" in observed
    assert SOFTWARE_FIXTURE_BOUNDARY["source_rights"] == "not_established"
    assert SOFTWARE_FIXTURE_BOUNDARY["source_currentness"] == "not_established"
