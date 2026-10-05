from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from polisyos.data_forge.domains.catalog.batch import harvester as harvester_module
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.harvester import harvest_sources
from polisyos.data_forge.domains.catalog.batch.source_registry import load_source_registry
from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
    CatalogSelectionError,
)
from polisyos.data_forge.domains.catalog.registry import default_catalog_source_registry_path


def test_source_registry_filters_and_waves() -> None:
    registry_path = default_catalog_source_registry_path()
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
    assert "data_gov_ua_broad" in blocking
    assert "data_gov_ro_broad" in blocking
    assert "data_gov_md_broad" in blocking
    assert "data_gov_pl_broad" in blocking
    assert "openaq_v2" not in blocking

    rest_backfill = {spec.name for spec in registry.enabled_sources(run_profile="rest_backfill")}
    assert rest_backfill == {"openaq_v2", "open_meteo", "eia_api"}

    catalog_refresh = {
        spec.name for spec in registry.enabled_sources(run_profile="catalog_refresh")
    }
    assert "data_gov_ua_broad" in catalog_refresh
    assert "wikidata_sparql" in catalog_refresh
    assert "data_gov_ua_exec" not in catalog_refresh


def test_batch_default_registry_is_the_canonical_catalog_registry(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path)

    assert config.default_registry_path == default_catalog_source_registry_path()
    assert config.load_registry().version == 1


def test_legacy_batch_registry_path_remains_a_default_alias(tmp_path) -> None:
    legacy_path = Path(__file__).resolve().parents[6] / (
        "src/polisyos/data_forge/domains/catalog/batch/source_registry.yaml"
    )
    config = DatasetBatchConfig(snapshot_root=tmp_path, registry_path=legacy_path)

    assert config.uses_custom_registry is False


@pytest.mark.parametrize(
    ("include_disabled_seed", "seed_id", "error_code"),
    [
        (True, "seed", "dependency_disabled"),
        (False, "missing", "dependency_missing"),
    ],
)
def test_batch_selection_fails_closed_for_unresolvable_seed(
    tmp_path: Path,
    include_disabled_seed: bool,
    seed_id: str,
    error_code: str,
) -> None:
    registry_path = _write_unresolvable_seed_registry(
        tmp_path,
        include_disabled_seed=include_disabled_seed,
        seed_id=seed_id,
    )

    registry = load_source_registry(registry_path)
    with pytest.raises(CatalogSelectionError) as caught:
        registry.enabled_sources(run_profile="prod_full")

    assert caught.value.code == error_code


@pytest.mark.parametrize(
    ("include_disabled_seed", "seed_id", "error_code"),
    [
        (True, "seed", "dependency_disabled"),
        (False, "missing", "dependency_missing"),
    ],
)
def test_batch_harvest_fails_before_processing_unresolvable_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    include_disabled_seed: bool,
    seed_id: str,
    error_code: str,
) -> None:
    registry_path = _write_unresolvable_seed_registry(
        tmp_path,
        include_disabled_seed=include_disabled_seed,
        seed_id=seed_id,
    )
    metrics_map_path = tmp_path / "metrics-map.yaml"
    metrics_map_path.write_text("{}\n", encoding="utf-8")
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        registry_path=registry_path,
        metrics_map_path=metrics_map_path,
    )

    async def fail_if_harvest_is_started(*args, **kwargs):
        raise AssertionError("harvest started before seed closure completed")

    monkeypatch.setattr(harvester_module, "harvest_one_source", fail_if_harvest_is_started)
    with pytest.raises(CatalogSelectionError) as caught:
        asyncio.run(harvest_sources(config))

    assert caught.value.code == error_code


def _write_unresolvable_seed_registry(
    tmp_path: Path,
    *,
    include_disabled_seed: bool,
    seed_id: str,
) -> Path:
    registry_path = tmp_path / f"{seed_id}-source-registry.yaml"
    rows = [
        "  - name: dependent\n"
        "    family: fixture\n"
        "    wave: A\n"
        "    endpoint: https://example.invalid/dependent\n"
        "    connector_id: fixture.fetch\n"
        "    execution_tier: fetchable\n"
        "    run_lane: empirical\n"
        f"    seed_from: {seed_id}\n"
        "    enabled: true\n"
    ]
    if include_disabled_seed:
        rows.append(
            "  - name: seed\n"
            "    family: fixture\n"
            "    wave: A\n"
            "    endpoint: https://example.invalid/seed\n"
            "    connector_id: fixture.catalog\n"
            "    enabled: false\n"
        )
    registry_path.write_text("version: 1\nsources:\n" + "".join(rows), encoding="utf-8")
    return registry_path


def test_batch_selection_holds_unknown_run_profile() -> None:
    registry = load_source_registry(default_catalog_source_registry_path())

    with pytest.raises(CatalogSelectionError) as caught:
        registry.enabled_sources(run_profile="future_profile")

    assert caught.value.code == "unsupported_run_profile"


def test_batch_config_holds_unknown_run_profile_before_loading_inputs(tmp_path) -> None:
    with pytest.raises(CatalogSelectionError) as caught:
        DatasetBatchConfig(snapshot_root=tmp_path, run_profile="future_profile")

    assert caught.value.code == "unsupported_run_profile"


@pytest.mark.parametrize(
    "source_field",
    ["endpoint: 42", "format_denylist: PDF", "format_allowlist: [7]"],
)
def test_batch_registry_rejects_coerced_source_values(
    tmp_path: Path,
    source_field: str,
) -> None:
    registry_path = tmp_path / "invalid-source-registry.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        "  - name: source\n"
        "    family: fixture\n"
        "    wave: A\n"
        "    endpoint: https://example.invalid/source\n"
        "    connector_id: fixture.source\n"
        f"    {source_field}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_source_registry(registry_path)
