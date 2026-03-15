from __future__ import annotations

from pathlib import Path

from polisyos.datasets.batch.source_registry import load_source_registry


def test_source_registry_filters_and_waves() -> None:
    registry_path = Path(__file__).resolve().parents[3] / "src/polisyos/datasets/batch/source_registry.yaml"
    registry = load_source_registry(registry_path)
    all_specs = {spec.name: spec for spec in registry.sources}

    wave_a = {spec.name: spec for spec in registry.enabled_sources(wave="A")}
    assert "oecd" in wave_a
    assert wave_a["oecd"].agency_prefix == "OECD"
    assert wave_a["oecd"].connector_id == "sdmx.source"
    assert wave_a["oecd"].execution_tier == "transport_ready"
    assert wave_a["oecd"].publish_blocking is True
    assert "ecb" in wave_a
    assert wave_a["ecb"].agency_prefix == "ECB"

    undata = wave_a["undata"]
    assert set(undata.agency_allowlist) == {"UNSD", "IAEG", "IAEG-SDGs", "UIS"}
    assert {"ESTAT", "WB"}.issubset(set(undata.exclude_agencies))

    wave_c = {spec.name: spec for spec in registry.enabled_sources(wave="C")}
    assert {
        "data_gov_ua_broad",
        "data_gov_ua_exec",
        "data_gov_ro_broad",
        "data_gov_ro_exec",
        "data_gov_md_broad",
        "data_gov_md_exec",
        "data_gov_pl_broad",
        "data_gov_pl_exec",
    }.issubset(set(wave_c))
    assert wave_c["data_gov_ua_exec"].seed_from == "data_gov_ua_broad"
    assert "ZIP" in wave_c["data_gov_ua_exec"].format_allowlist
    assert all_specs["data_gov_ro_broad"].enabled is True
    assert all_specs["data_gov_ro_exec"].seed_from == "data_gov_ro_broad"
    assert all_specs["data_gov_ro_exec"].publish_blocking is True
    assert all_specs["data_gov_md_broad"].enabled is True
    assert all_specs["data_gov_md_exec"].seed_from == "data_gov_md_broad"
    assert all_specs["data_gov_pl_broad"].enabled is True
    assert all_specs["data_gov_pl_exec"].seed_from == "data_gov_pl_broad"
    assert all_specs["data_gov_uk"].enabled is False
    assert all_specs["data_gov_us"].enabled is False

    wave_b = {spec.name for spec in registry.enabled_sources(wave="B")}
    assert "worldbank" in wave_b
    assert "wvs" in wave_b

    blocking = {spec.name for spec in registry.enabled_sources(run_profile="prod_core_blocking")}
    assert "worldbank" in blocking
    assert "oecd" in blocking
    assert "data_gov_ua_exec" in blocking
    assert "openaq_v2" not in blocking

    rest_backfill = {spec.name for spec in registry.enabled_sources(run_profile="rest_backfill")}
    assert rest_backfill == {"openaq_v2", "open_meteo", "eia_api"}

    catalog_refresh = {spec.name for spec in registry.enabled_sources(run_profile="catalog_refresh")}
    assert "data_gov_ua_broad" in catalog_refresh
    assert "wikidata_sparql" in catalog_refresh
    assert "data_gov_ua_exec" not in catalog_refresh
