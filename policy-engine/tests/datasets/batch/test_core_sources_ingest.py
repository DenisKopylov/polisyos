from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.core_sources_ingest import (
    ObservationPlan,
    _ensure_registry_tables,
    _insert_generic_observations,
    _normalize_observation_row,
    run_core_sources_ingest,
)
from polisyos.datasets.batch.graph_builder import build_graph
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
from polisyos.fabric.connectors.sources.unpd import UNPDConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.sources.wvs import WVSConnector


def test_core_sources_ingest_populates_registry_tables(monkeypatch) -> None:
    async def _fake_wb_fetch(self, _handle, request):  # noqa: ARG001
        df = pd.DataFrame(
            [
                {
                    "country_code": "UA",
                    "year": 2020,
                    "value": 0.5 if request.dataset_id.startswith("R") else 12345.0,
                }
            ]
        )
        return type("WBResult", (), {"data": df})()

    async def _fake_wvs_fetch(self, _handle, _request):  # noqa: ARG001
        df = pd.DataFrame(
            [
                {
                    "country_code": "UA",
                    "survey_year": 2020,
                    "wave": 7,
                    "value": 0.6,
                }
            ]
        )
        return type("WVSResult", (), {"data": df})()

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)
    monkeypatch.setattr(WVSConnector, "fetch", _fake_wvs_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap")
        stats = run_core_sources_ingest(config)
        assert stats.registry_datasets >= 4
        assert stats.variable_alignments > 0
        assert stats.observations > 0

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            reg_count = con.execute("SELECT count(*) FROM ds_registry_datasets").fetchone()[0]
            align_count = con.execute("SELECT count(*) FROM ds_variable_alignments").fetchone()[0]
            obs_count = con.execute("SELECT count(*) FROM ds_observations").fetchone()[0]
        finally:
            con.close()

        assert reg_count >= 4
        assert align_count > 0
        assert obs_count > 0


def test_core_sources_ingest_sync_wrapper_is_event_loop_safe(monkeypatch) -> None:
    async def _fake_wb_fetch(self, _handle, request):  # noqa: ARG001
        df = pd.DataFrame(
            [
                {
                    "country_code": "UA",
                    "year": 2020,
                    "value": 0.5 if request.dataset_id.startswith("R") else 12345.0,
                }
            ]
        )
        return type("WBResult", (), {"data": df})()

    async def _fake_wvs_fetch(self, _handle, _request):  # noqa: ARG001
        df = pd.DataFrame(
            [
                {
                    "country_code": "UA",
                    "survey_year": 2020,
                    "wave": 7,
                    "value": 0.6,
                }
            ]
        )
        return type("WVSResult", (), {"data": df})()

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)
    monkeypatch.setattr(WVSConnector, "fetch", _fake_wvs_fetch)

    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap")
            stats = run_core_sources_ingest(config)
            assert stats.registry_datasets >= 4
            assert stats.observations > 0

    import asyncio

    asyncio.run(_run())


def _catalog_record(
    *,
    source: str,
    dataset_id: str,
    title: str,
    metric: str,
    connector_type: str = "",
    profile_id: str = "",
    execution_tier: str = "fetchable",
) -> DatasetRecord:
    return DatasetRecord(
        id=f"{source}-{dataset_id}",
        title=title,
        description=f"{title} indicator",
        source=source,
        source_portal=source,
        dataset_id=dataset_id,
        source_dataset_id=dataset_id,
        execution_tier=execution_tier,
        update_frequency="annual",
        polisyos_metrics=[metric],
        variables=[dataset_id],
        preferred_distribution_id=f"dist-{source}-{dataset_id}",
        distributions=[
            DistributionRecord(
                id=f"dist-{source}-{dataset_id}",
                connector_type=connector_type,
                source_locator=dataset_id,
                profile_id=profile_id,
                parser_supported=True,
                machine_readable=True,
            )
        ],
    )


def test_normalize_observation_row_preserves_numeric_value() -> None:
    normalized = _normalize_observation_row(
        {
            "REF_AREA": "DEU",
            "FREQ": "A",
            "MEASURE": "MST_TUNE_RT",
            "SEX": "SEX_T",
            "EDU": "EDU_AGGREGATE_TOTAL",
            "CBR": "CBR_BIR_TOTAL",
            "TIME_PERIOD": "2023",
            "value": 3.071,
        }
    )

    assert normalized is not None
    assert normalized[0] == "DE"
    assert normalized[1] == 2023
    assert normalized[4] == 3.071
    assert "CBR_BIR_TOTAL" in normalized[5]


def test_core_sources_ingest_catalog_generalizes_across_sources(monkeypatch) -> None:
    async def _fake_wb_fetch(self, _handle, _request):  # noqa: ARG001
        return type("WBResult", (), {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": 1.1}])})()

    async def _fake_wvs_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "WVSResult",
            (),
            {"data": pd.DataFrame([{"country_code": "UA", "survey_year": 2020, "wave": 7, "value": 0.6}])},
        )()

    async def _fake_eurostat_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "EurostatResult",
            (),
            {"data": pd.DataFrame([{"geo": "UA", "time_period": "2020", "value": 11.0}])},
        )()

    async def _fake_sdmx_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "SDMXResult",
            (),
            {"data": pd.DataFrame([{"REF_AREA": "UKR", "TIME_PERIOD": "2020", "value": 22.0}])},
        )()

    async def _fake_who_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "WHOResult",
            (),
            {"data": pd.DataFrame([{"country_code": "UKR", "year": 2020, "value": 33.0}])},
        )()

    async def _fake_unpd_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "UNPDResult",
            (),
            {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": 44.0}])},
        )()

    async def _fake_uis_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "UISResult",
            (),
            {"data": pd.DataFrame([{"country_code": "UKR", "year": 2020, "value": 55.0}])},
        )()

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)
    monkeypatch.setattr(WVSConnector, "fetch", _fake_wvs_fetch)
    monkeypatch.setattr(EurostatConnector, "fetch", _fake_eurostat_fetch)
    monkeypatch.setattr(SDMXSourceConnector, "fetch", _fake_sdmx_fetch)
    monkeypatch.setattr(WHOConnector, "fetch", _fake_who_fetch)
    monkeypatch.setattr(UNPDConnector, "fetch", _fake_unpd_fetch)
    monkeypatch.setattr(UNESCOUISConnector, "fetch", _fake_uis_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap")
        build_graph(
            records=iter(
                [
                    _catalog_record(
                        source="worldbank",
                        dataset_id="NY.GDP.PCAP.PP.CD",
                        title="GDP per capita PPP",
                        metric="gdp_per_capita",
                        connector_type="worldbank.wdi",
                        profile_id="worldbank_wdi",
                        execution_tier="transport_ready",
                    ),
                    _catalog_record(
                        source="wvs",
                        dataset_id="A165",
                        title="Social trust",
                        metric="social_trust",
                        connector_type="wvs.wave7",
                        profile_id="wvs_wave7",
                        execution_tier="transport_ready",
                    ),
                    _catalog_record(
                        source="eurostat",
                        dataset_id="une_rt_a",
                        title="Unemployment rate annual",
                        metric="unemployment_rate",
                        connector_type="eurostat.data",
                        profile_id="eurostat_public",
                    ),
                    _catalog_record(
                        source="oecd",
                        dataset_id="CPI_DATA",
                        title="Inflation index",
                        metric="inflation",
                        connector_type="sdmx.source",
                        profile_id="oecd_sdmx",
                    ),
                    _catalog_record(
                        source="ilo",
                        dataset_id="EMP_DATA",
                        title="Labor force participation",
                        metric="labor_force_participation",
                        connector_type="sdmx.source",
                        profile_id="ilo_sdmx",
                    ),
                    _catalog_record(
                        source="who",
                        dataset_id="LE_001",
                        title="Health outcomes life expectancy",
                        metric="health_outcomes",
                        connector_type="who.indicators",
                        profile_id="who_gho",
                    ),
                    _catalog_record(
                        source="unpd",
                        dataset_id="POP_001",
                        title="Migration indicator",
                        metric="migration",
                        connector_type="unpd.data",
                        profile_id="unpd_dataportal",
                    ),
                    _catalog_record(
                        source="unesco_uis",
                        dataset_id="EDU_001",
                        title="Education outcomes enrollment",
                        metric="education_outcomes",
                        connector_type="unesco_uis.data",
                        profile_id="unesco_uis_public",
                    ),
                ]
            ),
            db_path=config.db_path,
        )

        stats = run_core_sources_ingest(config)
        assert stats.registry_datasets >= 8
        assert stats.variable_alignments >= 8
        assert stats.observations > 0

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            providers = {
                row[0]
                for row in con.execute("SELECT DISTINCT provider FROM ds_registry_datasets").fetchall()
            }
            observed_datasets = {
                row[0]
                for row in con.execute("SELECT DISTINCT dataset_id FROM ds_observations").fetchall()
            }
        finally:
            con.close()

        assert {"worldbank", "wvs", "eurostat", "oecd", "ilo", "who", "unpd", "unesco_uis"}.issubset(providers)
        assert "worldbank-NY.GDP.PCAP.PP.CD" in observed_datasets
        assert "who-LE_001" in observed_datasets
        assert "unpd-POP_001" in observed_datasets
        assert "unesco_uis-EDU_001" in observed_datasets


def test_core_sources_ingest_sampled_run_uses_unfiltered_fallback_for_sdmx(monkeypatch) -> None:
    eurostat_requests: list[tuple] = []
    sdmx_requests: list[tuple[str, tuple]] = []

    async def _fake_eurostat_fetch(self, _handle, request):  # noqa: ARG001
        eurostat_requests.append(request.filters)
        if request.filters:
            raise RuntimeError("HTTP 400")
        return type(
            "EurostatResult",
            (),
            {"data": pd.DataFrame([{"geo": "UA", "time_period": "2020", "value": 11.0}])},
        )()

    async def _fake_sdmx_fetch(self, _handle, request):  # noqa: ARG001
        sdmx_requests.append((request.dataset_id, request.filters))
        if request.filters:
            raise RuntimeError("HTTP 404")
        return type(
            "SDMXResult",
            (),
            {"data": pd.DataFrame([{"REF_AREA": "UKR", "TIME_PERIOD": "2020", "value": 22.0}])},
        )()

    monkeypatch.setattr(EurostatConnector, "fetch", _fake_eurostat_fetch)
    monkeypatch.setattr(SDMXSourceConnector, "fetch", _fake_sdmx_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap", max_datasets_per_source=2)
        build_graph(
            records=iter(
                [
                    _catalog_record(
                        source="eurostat",
                        dataset_id="une_rt_a",
                        title="Unemployment rate annual",
                        metric="unemployment_rate",
                        connector_type="eurostat.data",
                        profile_id="eurostat_public",
                    ),
                    _catalog_record(
                        source="oecd",
                        dataset_id="DSD_OECD@DF_TEST",
                        title="Inflation index",
                        metric="inflation",
                        connector_type="sdmx.source",
                        profile_id="oecd_sdmx",
                    ),
                    _catalog_record(
                        source="ilo",
                        dataset_id="DF_ILO_TEST",
                        title="Labor force participation",
                        metric="labor_force_participation",
                        connector_type="sdmx.source",
                        profile_id="ilo_sdmx",
                    ),
                ]
            ),
            db_path=config.db_path,
        )

        stats = run_core_sources_ingest(config)
        assert stats.observations > 0

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            observed_datasets = {
                row[0]
                for row in con.execute("SELECT DISTINCT dataset_id FROM ds_observations").fetchall()
            }
        finally:
            con.close()

        assert "eurostat-une_rt_a" in observed_datasets
        assert "oecd-DSD_OECD@DF_TEST" in observed_datasets
        assert "ilo-DF_ILO_TEST" in observed_datasets
        assert any(filters for filters in eurostat_requests)
        assert any(not filters for filters in eurostat_requests)
        assert any(filters for _dataset_id, filters in sdmx_requests)
        assert any(not filters for _dataset_id, filters in sdmx_requests)


def test_core_sources_ingest_sampled_run_diversifies_observation_canonical_vars(monkeypatch) -> None:
    async def _fake_sdmx_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "SDMXResult",
            (),
            {"data": pd.DataFrame([{"REF_AREA": "UKR", "TIME_PERIOD": "2020", "value": 22.0}])},
        )()

    monkeypatch.setattr(SDMXSourceConnector, "fetch", _fake_sdmx_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap", max_datasets_per_source=4)
        build_graph(
            records=iter(
                [
                    _catalog_record(
                        source="ilo",
                        dataset_id="DF_MST_TEAP_SEX_EDU_CBR_RT",
                        title="Labour force participation rate by sex, education and place of birth",
                        metric="labor_force_participation",
                        connector_type="sdmx.source",
                        profile_id="ilo_sdmx",
                    ),
                    _catalog_record(
                        source="ilo",
                        dataset_id="DF_MST_TUNE_SEX_EDU_CBR_RT",
                        title="Unemployment rate by sex, education and place of birth",
                        metric="unemployment_rate",
                        connector_type="sdmx.source",
                        profile_id="ilo_sdmx",
                    ),
                ]
            ),
            db_path=config.db_path,
        )

        stats = run_core_sources_ingest(config)
        assert stats.observations > 0

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            canonical_vars = {
                row[0]
                for row in con.execute(
                    "SELECT DISTINCT canonical_var FROM ds_observations WHERE dataset_id LIKE 'ilo-%'"
                ).fetchall()
            }
        finally:
            con.close()

        assert "labor_force_participation" in canonical_vars
        assert "unemployment_rate" in canonical_vars
        assert len(canonical_vars) >= 2


def test_core_sources_ingest_adds_proxy_alignment_for_health_spending(monkeypatch) -> None:
    async def _fake_who_fetch(self, _handle, _request):  # noqa: ARG001
        return type(
            "WHOResult",
            (),
            {"data": pd.DataFrame([{"country_code": "UKR", "year": 2020, "value": 33.0}])},
        )()

    monkeypatch.setattr(WHOConnector, "fetch", _fake_who_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap", max_datasets_per_source=4)
        build_graph(
            records=iter(
                [
                    _catalog_record(
                        source="who",
                        dataset_id="HEALTH_SPEND_1",
                        title="Health expenditure burden indicator",
                        metric="health_spending",
                        connector_type="who.indicators",
                        profile_id="who_gho",
                    ),
                ]
            ),
            db_path=config.db_path,
        )

        stats = run_core_sources_ingest(config)
        assert stats.variable_alignments > 0

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            alignments = con.execute(
                "SELECT canonical_var, is_proxy FROM ds_variable_alignments WHERE dataset_id LIKE 'who-%'"
            ).fetchall()
        finally:
            con.close()

        assert ("health_outcomes", True) in alignments


def test_core_sources_ingest_keeps_multiple_canonical_observations_for_same_raw_value() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap", max_datasets_per_source=6)
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
            rows = [{"REF_AREA": "UKR", "TIME_PERIOD": "2020", "value": 22.0}]
            base_plan = {
                "dataset_id": "ilo-DF_MST_TEAP_SEX_EDU_CCT_RT",
                "source": "ilo",
                "raw_variable": "DF_MST_TEAP_SEX_EDU_CCT_RT",
                "connector_id": "sdmx.source",
                "profile_id": "ilo_sdmx",
                "request_dataset_id": "DF_MST_TEAP_SEX_EDU_CCT_RT",
                "default_filters": {},
                "update_frequency": "annual",
            }
            inserted = _insert_generic_observations(
                con=con,
                plan=ObservationPlan(canonical_var="labor_force_participation", **base_plan),
                rows=rows,
            )
            inserted += _insert_generic_observations(
                con=con,
                plan=ObservationPlan(canonical_var="education_outcomes", **base_plan),
                rows=rows,
            )
            observed = con.execute(
                "SELECT canonical_var, value FROM ds_observations ORDER BY canonical_var"
            ).fetchall()
        finally:
            con.close()

        assert inserted.written == 2
        assert observed == [
            ("education_outcomes", 22.0),
            ("labor_force_participation", 22.0),
        ]


def test_insert_generic_observations_tracks_inserted_and_replaced_rows() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap", max_datasets_per_source=6)
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
            plan = ObservationPlan(
                dataset_id="ilo-DF_MST_TUNE_SEX_EDU_CBR_RT",
                source="ilo",
                raw_variable="DF_MST_TUNE_SEX_EDU_CBR_RT",
                canonical_var="unemployment_rate",
                connector_id="sdmx.source",
                profile_id="ilo_sdmx",
                request_dataset_id="DF_MST_TUNE_SEX_EDU_CBR_RT",
                default_filters={},
                update_frequency="annual",
            )
            first = _insert_generic_observations(
                con=con,
                plan=plan,
                rows=[{"REF_AREA": "UKR", "TIME_PERIOD": "2020", "value": 22.0, "SEX": "T"}],
            )
            second = _insert_generic_observations(
                con=con,
                plan=plan,
                rows=[{"REF_AREA": "UKR", "TIME_PERIOD": "2020", "value": 25.0, "SEX": "T"}],
            )
        finally:
            con.close()

        assert first.attempted == 1
        assert first.inserted == 1
        assert first.replaced == 0
        assert second.attempted == 1
        assert second.inserted == 0
        assert second.replaced == 1
