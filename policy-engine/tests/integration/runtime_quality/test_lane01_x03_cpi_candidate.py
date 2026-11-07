"""Candidate-only CPI source binding, with the distinct annual-growth control.

The compact World Bank WDI response bodies below were captured from
``https://api.worldbank.org/v2/country/UKR/indicator/{indicator}?date=2024:2024&format=json&page=1&per_page=1000``
on 2026-11-07. They are retained as source-labelled test inputs, not as a
claim of currentness, permission, measurement authority, or claim evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests._helpers.lane01_candidate_source import (
    Lane01CandidateCompilerInput,
    build_lane01_candidate_source,
    compile_lane01_candidate_report,
)
from tests._helpers.lane01_wdi_profiles import CPI_PROFILE

CPI_LEVEL_RESPONSE = (
    b'[{"page":1,"pages":1,"per_page":1000,"total":1,"sourceid":"2",'
    b'"lastupdated":"2026-10-08"},[{"indicator":{"id":"FP.CPI.TOTL",'
    b'"value":"Consumer price index (2010 = 100)"},"country":{"id":"UA",'
    b'"value":"Ukraine"},"countryiso3code":"UKR","date":"2024",'
    b'"value":457.090971982012,"unit":"","obs_status":"","decimal":1}]]'
)
CPI_GROWTH_RESPONSE = (
    b'[{"page":1,"pages":1,"per_page":1000,"total":1,"sourceid":"2",'
    b'"lastupdated":"2026-10-08"},[{"indicator":{"id":"FP.CPI.TOTL.ZG",'
    b'"value":"Inflation, consumer prices (annual %)"},"country":{"id":"UA",'
    b'"value":"Ukraine"},"countryiso3code":"UKR","date":"2024",'
    b'"value":6.50198464669254,"unit":"","obs_status":"","decimal":1}]]'
)

CPI_COMPILER_INPUT = Lane01CandidateCompilerInput(
    scenario_id="lane01-cpi-ukr-2024",
    text=(
        "Assess the candidate annual consumer price index level for Ukraine in 2024; "
        "the index uses the World Bank's 2010=100 base."
    ),
    domain="economic",
    profile_id="scope:lane01-cpi-ukr-2024:v1",
    jurisdiction="UKR",
    population="national_economy",
    entity_scope="country",
    time_start="2024-01-01",
    time_end="2024-12-31",
    time_role="observation_time",
    granularity="annual",
    required_constructs=("economic.consumer_price_index",),
)


@pytest.mark.integration
def test_x03_cpi_source_binds_index_level_and_rejects_annual_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bind the exact CPI level through Catalog and refuse the annual growth indicator."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.data_forge.read_api import catalog
    from polisyos.runtime.quality.acquisition_executor import LiveAcquisitionExecutionError
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )

    assert CPI_PROFILE.index_base_year == 2010
    assert CPI_PROFILE.indicator_id == "FP.CPI.TOTL"
    assert CPI_PROFILE.raw_unit == CPI_PROFILE.canonical_unit == "index"
    assert CPI_PROFILE.target_slot == "global.consumer_price_index"
    assert CPI_PROFILE.catalog_metric_id == "consumer_price_index"
    assert CPI_PROFILE.population == "national_economy"
    assert CPI_PROFILE.denominator is None
    assert CPI_PROFILE.quantity_kind == "unconstrained"
    assert hashlib.sha256(CPI_LEVEL_RESPONSE).hexdigest() == (
        "643ff4ff1951612f925996b0f4905c44f4a888956e3601818793580d222485ae"
    )
    assert hashlib.sha256(CPI_GROWTH_RESPONSE).hexdigest() == (
        "13ccf242f048652fc73986ed9833826160174c8c195fe14d211893cc7613d55d"
    )

    report = compile_lane01_candidate_report(
        compiler_input=CPI_COMPILER_INPUT,
        profile=CPI_PROFILE,
    )
    resolutions = tuple(
        item
        for item in (report.capability_requirement_resolutions or ())
        if item.query.construct == CPI_PROFILE.construct and item.candidate_discovery is not None
    )
    assert len(resolutions) == 1
    assert len(resolutions[0].candidate_discovery.candidates) == 1
    candidate = resolutions[0].candidate_discovery.candidates[0]
    metadata = candidate.source_assets[0]["metadata"]
    assert metadata["catalog_fetch_binding"] == {
        "connector_id": "worldbank.wdi",
        "dataset_id": "FP.CPI.TOTL",
        "metric_id": "consumer_price_index",
        "profile_id": "worldbank_wdi",
    }
    assert metadata["index_base_year"] == 2010
    assert metadata["indicator_id"] == CPI_PROFILE.indicator_id
    assert metadata["target_world_slot"] == CPI_PROFILE.target_slot
    assert metadata["raw_unit"] == metadata["canonical_unit"] == "index"
    assert metadata["population_scope"] == "national_economy"
    assert metadata["source_release"] == "not_established"
    assert candidate.descriptor["rights_envelope"]["claim_evidence_use_allowed"] is False
    assert candidate.descriptor["freshness_envelope"]["freshness_class"] == "not_established"

    store = FileSystemCAS(tmp_path / "cpi-cas")
    fixture = build_lane01_candidate_source(
        tmp_path / "cpi-level-source",
        monkeypatch,
        store=store,
        profile=CPI_PROFILE,
        compiler_input=CPI_COMPILER_INPUT,
        response_body=CPI_LEVEL_RESPONSE,
    )
    source = fixture.source
    entry = source.resolved_source.entry
    registration = source.resolved_source.registration
    assert source.candidate_digest == candidate.content_digest
    assert source.requirement_id == resolutions[0].query.requirement_id
    assert source.status == "candidate_only"
    assert source.source_currentness == "source_currentness_not_established"
    assert source.observation_class is catalog.ObservationProvenanceClass.OBSERVED
    assert source.observation == pytest.approx(457.090971982012, rel=0, abs=1e-12)
    assert source.country_code == "UKR" and source.year == 2024
    assert source.target_slot_id == "global.consumer_price_index"
    assert source.population == "national_economy"
    assert source.denominator is None and source.quantity_kind == "unconstrained"
    assert source.canonical_unit == "index"
    assert entry.target_variable == "global.consumer_price_index"
    assert entry.upstream_metric_id == "consumer_price_index"
    assert entry.raw_unit == entry.canonical_unit == "index"
    assert entry.title == "Consumer price index (2010 = 100)"
    assert registration.request_dataset_id == "FP.CPI.TOTL"
    assert registration.metric_id == "global.consumer_price_index"
    assert store.get_bytes(source.raw_source_ref) == CPI_LEVEL_RESPONSE
    fresh_store = FileSystemCAS(store.root)
    assert read_candidate_acquisition_source(fresh_store, source_ref=fixture.source_ref) == source

    with pytest.raises(LiveAcquisitionExecutionError) as mismatch:
        build_lane01_candidate_source(
            tmp_path / "cpi-growth-as-level-control",
            monkeypatch,
            profile=CPI_PROFILE,
            compiler_input=CPI_COMPILER_INPUT,
            response_body=CPI_GROWTH_RESPONSE,
        )
    assert mismatch.value.code == "live_normalized_scope_drift"
