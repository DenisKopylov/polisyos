from __future__ import annotations

import asyncio

from polisyos.datasets.batch.ckan_curation import curate_ckan_package, guess_ckan_resource_format
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.harvester import harvest_one_source
from polisyos.datasets.batch.source_registry import SourceSpec


def _exec_spec() -> SourceSpec:
    return SourceSpec(
        name="data_gov_ua_exec",
        family="ckan",
        wave="C",
        endpoint="https://data.gov.ua/api/3/action/package_search",
        connector_id="ckan.resource",
        profile_id="data_gov_ua",
        execution_tier="fetchable",
        seed_from="data_gov_ua_broad",
        format_allowlist=("CSV", "JSON", "XLSX", "XLS", "ODS", "ZIP"),
        format_denylist=("PDF", "DOC", "DOCX", "XML"),
        keyword_allowlist=("бюджет", "освіт", "health", "budget"),
        keyword_denylist=("протокол", "рішення"),
        require_curated_resources=True,
    )


def _poland_exec_spec() -> SourceSpec:
    return SourceSpec(
        name="data_gov_pl_exec",
        family="poland_api",
        wave="C",
        endpoint="https://api.dane.gov.pl/1.4/datasets",
        connector_id="rest.json",
        profile_id="data_gov_pl",
        execution_tier="fetchable",
        seed_from="data_gov_pl_broad",
        format_allowlist=("JSON",),
        keyword_allowlist=("budzet", "budżet", "dochody", "wydatki", "edukac", "szkol", "uczni"),
        keyword_denylist=("uchwala", "uchwała", "rozporzadzenie", "rozporządzenie"),
        require_curated_resources=True,
    )


def test_guess_ckan_resource_format_from_url() -> None:
    fmt = guess_ckan_resource_format({"url": "https://example.test/file.xlsx", "format": ""})
    assert fmt == "XLSX"


def test_curate_ckan_package_prunes_resources_and_keeps_exec_dataset() -> None:
    raw = {
        "id": "budget-001",
        "title": "Бюджет громади",
        "notes": "Таблиця з видатками та доходами",
        "resources": [
            {"id": "csv-1", "url": "https://example.test/budget.csv", "format": "CSV"},
            {"id": "pdf-1", "url": "https://example.test/budget.pdf", "format": "PDF"},
        ],
        "tags": [{"name": "бюджет"}],
    }

    curated = curate_ckan_package(raw, _exec_spec())
    assert curated is not None
    assert len(curated["resources"]) == 1
    assert curated["resources"][0]["format"] == "CSV"


def test_curate_ckan_package_filters_non_exec_dataset() -> None:
    raw = {
        "id": "protocol-001",
        "title": "Протокол засідання",
        "notes": "Скан документа",
        "resources": [
            {"id": "pdf-1", "url": "https://example.test/protocol.pdf", "format": "PDF"},
        ],
        "tags": [{"name": "протокол"}],
    }

    curated = curate_ckan_package(raw, _exec_spec())
    assert curated is None


def test_harvest_one_source_can_build_exec_slice_from_broad(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    broad_rows = [
        {
            "id": "budget-001",
            "title": "Бюджет громади",
            "notes": "Таблиця з видатками",
            "resources": [
                {"id": "csv-1", "url": "https://example.test/budget.csv", "format": "CSV"},
                {"id": "pdf-1", "url": "https://example.test/budget.pdf", "format": "PDF"},
            ],
            "tags": [{"name": "бюджет"}],
        },
        {
            "id": "protocol-001",
            "title": "Протокол засідання",
            "notes": "Скан документа",
            "resources": [
                {"id": "pdf-1", "url": "https://example.test/protocol.pdf", "format": "PDF"},
            ],
            "tags": [{"name": "протокол"}],
        },
    ]

    rows = asyncio.run(
        harvest_one_source(
            _exec_spec(),
            config,
            harvested={"data_gov_ua_broad": broad_rows},
        )
    )

    assert len(rows) == 1
    assert rows[0]["id"] == "budget-001"
    assert len(rows[0]["resources"]) == 1


def test_harvest_one_source_keeps_poland_exec_seed_with_related_resources(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")
    broad_rows = [
        {
            "id": "179",
            "title": "Prognoza wpływów i wydatków funduszu emerytalnego do 2060 roku",
            "description": "Dochody i wydatki funduszu emerytalnego.",
            "formats": ["HTML"],
            "resources_related_url": "https://api.dane.gov.pl/1.4/datasets/179/resources",
            "dataset_url": "https://api.dane.gov.pl/1.4/datasets/179",
        }
    ]

    rows = asyncio.run(
        harvest_one_source(
            _poland_exec_spec(),
            config,
            harvested={"data_gov_pl_broad": broad_rows},
        )
    )

    assert len(rows) == 1
    assert rows[0]["id"] == "179"


def test_harvest_one_source_applies_global_limit_after_family_harvest(monkeypatch, tmp_path) -> None:
    async def _fake_harvest_sdmx_dataflows(_spec, _timeout_s):  # type: ignore[no-untyped-def]
        return [{"id": f"df-{idx}", "agencyID": "TEST", "name": f"Flow {idx}"} for idx in range(10)]

    monkeypatch.setattr(
        "polisyos.datasets.batch.harvester._harvest_sdmx_dataflows",
        _fake_harvest_sdmx_dataflows,
    )

    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", max_datasets_per_source=3)
    spec = SourceSpec(
        name="oecd",
        family="sdmx",
        wave="B",
        endpoint="https://example.test/sdmx",
    )

    rows = asyncio.run(harvest_one_source(spec, config))

    assert len(rows) == 3
    assert [row["id"] for row in rows] == ["df-0", "df-1", "df-2"]


def test_harvest_one_source_prioritizes_metric_relevant_sdmx_rows(monkeypatch, tmp_path) -> None:
    async def _fake_harvest_sdmx_dataflows(_spec, _timeout_s):  # type: ignore[no-untyped-def]
        return [
            {"id": "CLIM_1", "agencyID": "OECD", "name": "Climate projections by city", "description": "Wildfire and drought"},
            {"id": "UNE_1", "agencyID": "OECD", "name": "Unemployment rate by country", "description": "Labour market"},
            {"id": "GDP_1", "agencyID": "OECD", "name": "GDP per capita", "description": "Gross domestic product per capita"},
            {"id": "EDU_1", "agencyID": "OECD", "name": "Education outcomes enrollment", "description": "School enrollment"},
        ]

    monkeypatch.setattr(
        "polisyos.datasets.batch.harvester._harvest_sdmx_dataflows",
        _fake_harvest_sdmx_dataflows,
    )

    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", max_datasets_per_source=2)
    spec = SourceSpec(
        name="oecd",
        family="sdmx",
        wave="B",
        endpoint="https://example.test/sdmx",
        agency_prefix="OECD",
    )
    metrics_map = {
        "unemployment_rate": {"keywords": ["unemployment"]},
        "gdp_per_capita": {"keywords": []},
        "education_outcomes": {"keywords": []},
    }

    rows = asyncio.run(harvest_one_source(spec, config, metrics_map=metrics_map))

    assert len(rows) == 2
    assert {row["id"] for row in rows} == {"UNE_1", "GDP_1"}
    assert "CLIM_1" not in {row["id"] for row in rows}
    assert any("unemployment_rate" in row.get("harvest_metric_candidates", []) for row in rows)


def test_harvest_one_source_diversifies_metrics_for_worldbank_sample(monkeypatch, tmp_path) -> None:
    async def _fake_harvest_worldbank(_endpoint, limit, _timeout_s):  # type: ignore[no-untyped-def]
        assert limit > 3
        return [
            {"id": "SI.POV.DDAY", "name": "Poverty headcount ratio", "sourceNote": "Poverty headcount ratio at $2.15 a day"},
            {"id": "NY.GDP.PCAP.CD", "name": "GDP per capita (current US$)", "sourceNote": "Gross domestic product per capita"},
            {"id": "NY.GDP.PCAP.PP.CD", "name": "GDP per capita, PPP (current international $)", "sourceNote": "Gross domestic product per capita PPP"},
            {"id": "RL.EST", "name": "Rule of Law: Estimate", "sourceNote": "Rule of law estimate"},
            {"id": "SL.TLF.CACT.ZS", "name": "Labor force participation rate", "sourceNote": "Labor force participation"},
            {"id": "EN.ATM.CO2E.PC", "name": "CO2 emissions", "sourceNote": "Carbon emissions"},
        ]

    monkeypatch.setattr(
        "polisyos.datasets.batch.harvester._harvest_worldbank",
        _fake_harvest_worldbank,
    )

    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", max_datasets_per_source=4)
    spec = SourceSpec(
        name="worldbank",
        family="worldbank",
        wave="B",
        endpoint="https://example.test/worldbank",
        metrics_required=True,
    )
    metrics_map = {
        "poverty_rate": {"keywords": ["poverty"], "worldbank_indicators": ["SI.POV.DDAY"]},
        "gdp_per_capita": {"keywords": ["gdp per capita"], "worldbank_indicators": ["NY.GDP.PCAP.CD"]},
        "institutional_quality": {"keywords": ["rule of law"], "worldbank_indicators": ["RL.EST"]},
        "labor_force_participation": {"keywords": ["labor force participation"], "worldbank_indicators": ["SL.TLF.CACT.ZS"]},
    }

    rows = asyncio.run(harvest_one_source(spec, config, metrics_map=metrics_map))

    assert len(rows) == 4
    assert [row["id"] for row in rows] == [
        "NY.GDP.PCAP.CD",
        "SI.POV.DDAY",
        "RL.EST",
        "SL.TLF.CACT.ZS",
    ]


def test_harvest_one_source_prioritizes_romania_ckan_policy_domains(monkeypatch, tmp_path) -> None:
    async def _fake_harvest_ckan(_endpoint, limit, _timeout_s):  # type: ignore[no-untyped-def]
        assert limit > 4
        return [
            {"id": "misc-1", "title": "Anunt administrativ", "notes": "Document intern", "tags": [{"name": "administrativ"}]},
            {"id": "budget-1", "title": "Buget local al municipiului", "notes": "Venituri si cheltuieli buget local", "tags": [{"name": "buget"}]},
            {"id": "edu-1", "title": "Unitati scolare si elevi", "notes": "Educatie si scoli", "tags": [{"name": "educatie"}]},
            {"id": "health-1", "title": "Spitale si servicii de sanatate", "notes": "Sanatate publica", "tags": [{"name": "sanatate"}]},
            {"id": "labor-1", "title": "Somaj si piata muncii", "notes": "Date despre somaj", "tags": [{"name": "munca"}]},
            {"id": "migration-1", "title": "Migratie si demografie", "notes": "Populatie, nasteri, decese", "tags": [{"name": "demografie"}]},
        ]

    monkeypatch.setattr(
        "polisyos.datasets.batch.harvester._harvest_ckan",
        _fake_harvest_ckan,
    )

    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", max_datasets_per_source=4)
    spec = SourceSpec(
        name="data_gov_ro",
        family="ckan",
        wave="C",
        endpoint="https://data.gov.ro/api/3/action/package_search",
    )

    rows = asyncio.run(harvest_one_source(spec, config))

    assert len(rows) == 4
    selected_ids = {row["id"] for row in rows}
    assert "budget-1" in selected_ids
    assert "edu-1" in selected_ids
    assert "health-1" in selected_ids
    assert "labor-1" in selected_ids or "migration-1" in selected_ids


def test_harvest_one_source_prioritizes_poland_policy_domains(monkeypatch, tmp_path) -> None:
    async def _fake_harvest_poland_open_data(_endpoint, limit, _timeout_s):  # type: ignore[no-untyped-def]
        assert limit > 4
        return [
            {"id": "misc-1", "title": "Komunikat administracyjny", "description": "dokument wewnetrzny", "notes": "administracja", "tags": [{"name": "administracja"}]},
            {"id": "budget-1", "title": "Budzet lokalny miasta", "description": "Dochody i wydatki budzetowe", "notes": "budzet lokalny", "tags": [{"name": "budzet"}]},
            {"id": "edu-1", "title": "Edukacja i szkoly", "description": "Dane o uczniach i szkolach", "notes": "edukacja publiczna", "tags": [{"name": "edukacja"}]},
            {"id": "health-1", "title": "Zdrowie publiczne i szpitale", "description": "Zdrowie i opieka medyczna", "notes": "zdrowie publiczne", "tags": [{"name": "zdrowie"}]},
            {"id": "labor-1", "title": "Bezrobocie i rynek pracy", "description": "Dane o rynku pracy", "notes": "bezrobocie", "tags": [{"name": "praca"}]},
            {"id": "migration-1", "title": "Migracja i demografia", "description": "Ludnosc i migracja", "notes": "migracja", "tags": [{"name": "demografia"}]},
        ]

    monkeypatch.setattr(
        "polisyos.datasets.batch.harvester._harvest_poland_open_data",
        _fake_harvest_poland_open_data,
    )

    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap", max_datasets_per_source=4)
    spec = SourceSpec(
        name="data_gov_pl",
        family="poland_api",
        wave="C",
        endpoint="https://api.dane.gov.pl/1.4/datasets",
    )

    rows = asyncio.run(harvest_one_source(spec, config))

    assert len(rows) == 4
    selected_ids = {row["id"] for row in rows}
    assert "budget-1" in selected_ids
    assert "edu-1" in selected_ids
    assert "health-1" in selected_ids
    assert "labor-1" in selected_ids or "migration-1" in selected_ids
