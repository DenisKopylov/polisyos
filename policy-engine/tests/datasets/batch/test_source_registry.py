from __future__ import annotations

from pathlib import Path

from polisyos.datasets.batch.source_registry import load_source_registry


def test_source_registry_filters_and_waves() -> None:
    registry_path = Path(__file__).resolve().parents[3] / "src/polisyos/datasets/batch/source_registry.yaml"
    registry = load_source_registry(registry_path)

    wave_a = {spec.name: spec for spec in registry.enabled_sources(wave="A")}
    assert "oecd" in wave_a
    assert wave_a["oecd"].agency_prefix == "OECD"
    assert "ecb" in wave_a
    assert wave_a["ecb"].agency_prefix == "ECB"

    undata = wave_a["undata"]
    assert set(undata.agency_allowlist) == {"UNSD", "IAEG", "IAEG-SDGs", "UIS"}
    assert {"ESTAT", "WB"}.issubset(set(undata.exclude_agencies))

    wave_c = {spec.name for spec in registry.enabled_sources(wave="C")}
    assert wave_c == {"data_gov_ua"}

    wave_b = {spec.name for spec in registry.enabled_sources(wave="B")}
    assert "worldbank" in wave_b
    assert "wvs" in wave_b
