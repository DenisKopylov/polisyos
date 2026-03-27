from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from polisyos.datasets.batch import core_sources_ingest as core_ingest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.core_sources_ingest import (
    ObservationPlan,
    _ensure_registry_tables,
    _build_catalog_observation_plans,
    _insert_generic_observations,
    _limit_observation_plans,
    _normalize_observation_row,
    _observation_payload_row_limit,
    run_core_sources_ingest,
)
from polisyos.datasets.knowledge.variable_alignment import AlignmentMethod, VariableAlignment
from polisyos.datasets.batch.graph_builder import build_graph
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord
from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
from polisyos.fabric.connectors.sources.unpd import UNPDConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector


@pytest.fixture(autouse=True)
def _stub_dataset_capability_describe(monkeypatch):
    async def _fake_describe(self, _handle, dataset_id):  # noqa: ARG001
        return DatasetCapabilitySnapshot(
            source=str(getattr(self, "namespace", "test")),
            dataset_id=str(dataset_id),
            resolved_dataset_id=str(dataset_id),
            preferred_transport="test",
            last_checked_at=datetime.now(timezone.utc),
        )

    for connector_cls in (
        WorldBankConnector,
        EurostatConnector,
        SDMXSourceConnector,
        WHOConnector,
        UNPDConnector,
        UNESCOUISConnector,
    ):
        monkeypatch.setattr(connector_cls, "describe_dataset", _fake_describe)


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

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)
    monkeypatch.setattr(
        core_ingest,
        "_load_wvs_bulk_rows",
        lambda _indicator: [
            {
                "country_code": "UA",
                "survey_year": 2020,
                "wave": 7,
                "value": 0.6,
                "sample_size": 1200,
                "sample_weight_field": "S017",
                "data_shape": "survey_repeated_cross_section",
            }
        ],
    )

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

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)
    monkeypatch.setattr(
        core_ingest,
        "_load_wvs_bulk_rows",
        lambda _indicator: [
            {
                "country_code": "UA",
                "survey_year": 2020,
                "wave": 7,
                "value": 0.6,
                "sample_size": 1200,
                "sample_weight_field": "S017",
                "data_shape": "survey_repeated_cross_section",
            }
        ],
    )

    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap")
            stats = run_core_sources_ingest(config)
            assert stats.registry_datasets >= 4
            assert stats.observations > 0

    import asyncio

    asyncio.run(_run())


def test_core_sources_ingest_injects_unpd_token_into_connection_config(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_UNPD_API_TOKEN", "test-token")

    config = core_ingest._resolve_profile_config("unpd_dataportal")

    assert config.auth_credentials.get("token") == "test-token"
    assert config.auth_method == "bearer"


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


def test_load_wvs_bulk_rows_aggregates_social_trust_as_weighted_share(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "WVS_Time_Series_1981-2022_csv_v5_0.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "COUNTRY_ALPHA,S020,S002VS,S017,S018,A165,A173",
                    "UKR,2020,7,2,2.0,1,5",
                    "UKR,2020,7,1,1.0,2,3",
                    "DEU,2018,7,3,3.0,1,4",
                    "FRA,2020,7,5,5.0,1,5",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(core_ingest, "_wvs_bulk_csv_path", lambda: csv_path)

        rows = core_ingest._load_wvs_bulk_rows("A165")

    assert rows == [
        {
            "country_code": "DE",
            "survey_year": 2018,
            "wave": 7,
            "value": 1.0,
            "sample_size": 1,
            "weighted_sample_size": 3.0,
            "sample_weight_field": "S017",
            "aggregation_method": "weighted_share_response_1",
            "data_shape": "survey_repeated_cross_section",
            "observation_grain": "country_survey_year_wave",
        },
        {
            "country_code": "UA",
            "survey_year": 2020,
            "wave": 7,
            "value": 2.0 / 3.0,
            "sample_size": 2,
            "weighted_sample_size": 3.0,
            "sample_weight_field": "S017",
            "aggregation_method": "weighted_share_response_1",
            "data_shape": "survey_repeated_cross_section",
            "observation_grain": "country_survey_year_wave",
        },
    ]


def test_core_sources_ingest_catalog_generalizes_across_sources(monkeypatch) -> None:
    async def _fake_wb_fetch(self, _handle, _request):  # noqa: ARG001
        return type("WBResult", (), {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": 1.1}])})()

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
    monkeypatch.setattr(
        core_ingest,
        "_load_wvs_bulk_rows",
        lambda _indicator: [
            {
                "country_code": "UA",
                "survey_year": 2020,
                "wave": 7,
                "value": 0.6,
                "sample_size": 1200,
                "sample_weight_field": "S017",
                "data_shape": "survey_repeated_cross_section",
            }
        ],
    )
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


def test_core_sources_ingest_writes_alignment_audit(monkeypatch) -> None:
    async def _fake_wb_fetch(self, _handle, _request):  # noqa: ARG001
        return type("WBResult", (), {"data": pd.DataFrame([{"country_code": "UA", "year": 2020, "value": 1.1}])})()

    monkeypatch.setattr(WorldBankConnector, "fetch", _fake_wb_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap", max_datasets_per_source=1)
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
                ]
            ),
            db_path=config.db_path,
        )

        run_core_sources_ingest(config)

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            rows = con.execute(
                "SELECT raw_variable, canonical_variable, raw_confidence, calibrated_confidence "
                "FROM ds_alignment_audit"
            ).fetchall()
        finally:
            con.close()

        assert rows
        assert rows[0][0]
        assert rows[0][1]
        assert float(rows[0][3]) >= float(rows[0][2])


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


def test_ensure_registry_tables_drops_legacy_unique_observation_index() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "legacy.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            con.execute(
                """
                CREATE TABLE ds_observations (
                    observation_id VARCHAR PRIMARY KEY,
                    dataset_id     VARCHAR NOT NULL,
                    raw_variable   VARCHAR NOT NULL,
                    canonical_var  VARCHAR NOT NULL,
                    country_code   VARCHAR NOT NULL,
                    year           INTEGER,
                    survey_year    INTEGER,
                    wave           INTEGER,
                    value          DOUBLE,
                    condition_json VARCHAR DEFAULT '{}'
                );
                """
            )
            con.execute(
                "CREATE UNIQUE INDEX idx_obs_dedup "
                "ON ds_observations(dataset_id, raw_variable, country_code, year)"
            )

            _ensure_registry_tables(con)

            indexes = con.execute(
                "SELECT index_name, is_unique FROM duckdb_indexes() "
                "WHERE table_name='ds_observations' AND index_name='idx_obs_dedup'"
            ).fetchall()
        finally:
            con.close()

        assert indexes == [("idx_obs_dedup", False)]


def test_insert_generic_observations_preserves_multislice_rows_after_legacy_index_migration() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "legacy_multislice.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            con.execute(
                """
                CREATE TABLE ds_observations (
                    observation_id VARCHAR PRIMARY KEY,
                    dataset_id     VARCHAR NOT NULL,
                    raw_variable   VARCHAR NOT NULL,
                    canonical_var  VARCHAR NOT NULL,
                    country_code   VARCHAR NOT NULL,
                    year           INTEGER,
                    survey_year    INTEGER,
                    wave           INTEGER,
                    value          DOUBLE,
                    condition_json VARCHAR DEFAULT '{}'
                );
                """
            )
            con.execute(
                "CREATE UNIQUE INDEX idx_obs_dedup "
                "ON ds_observations(dataset_id, raw_variable, country_code, year)"
            )
            plan = ObservationPlan(
                dataset_id="eurostat-ILC_MDHO06B",
                source="eurostat",
                raw_variable="ILC_MDHO06B",
                canonical_var="poverty_rate",
                connector_id="eurostat.data",
                profile_id="eurostat_public",
                request_dataset_id="ILC_MDHO06B",
                default_filters={},
                update_frequency="annual",
            )
            inserted = _insert_generic_observations(
                con=con,
                plan=plan,
                rows=[
                    {
                        "geo": "DE",
                        "time_period": "2005",
                        "value": 2.3,
                        "hhtyp": "Single person",
                    },
                    {
                        "geo": "DE",
                        "time_period": "2005",
                        "value": 2.8,
                        "hhtyp": "Households with dependent children",
                    },
                ],
            )
            observed = con.execute(
                "SELECT value, condition_json FROM ds_observations "
                "WHERE dataset_id = ? AND raw_variable = ? AND canonical_var = ? "
                "AND country_code = ? AND year = ? ORDER BY value",
                [plan.dataset_id, plan.raw_variable, plan.canonical_var, "DE", 2005],
            ).fetchall()
            indexes = con.execute(
                "SELECT index_name, is_unique FROM duckdb_indexes() "
                "WHERE table_name='ds_observations' AND index_name='idx_obs_dedup'"
            ).fetchall()
        finally:
            con.close()

        assert inserted.written == 2
        assert observed == [
            (2.3, '{"hhtyp":"Single person"}'),
            (2.8, '{"hhtyp":"Households with dependent children"}'),
        ]
        assert indexes == [("idx_obs_dedup", False)]


def test_insert_generic_observations_batches_large_upserts(monkeypatch) -> None:
    class _FakeConnection:
        def __init__(self) -> None:
            self.batch_sizes: list[int] = []

        def executemany(self, _sql: str, values: list[tuple]) -> None:
            self.batch_sizes.append(len(values))

    monkeypatch.setattr(core_ingest, "_existing_observation_ids", lambda _con, _ids: set())
    con = _FakeConnection()
    plan = ObservationPlan(
        dataset_id="eurostat-NRG_TE_OILM",
        source="eurostat",
        raw_variable="NRG_TE_OILM",
        canonical_var="energy_use",
        connector_id="eurostat.data",
        profile_id="eurostat_public",
        request_dataset_id="NRG_TE_OILM",
        default_filters={},
        update_frequency="monthly",
    )
    rows = [
        {
            "geo": "PL",
            "time_period": f"2022-{(index % 12) + 1:02d}",
            "value": float(index),
            "partner": f"P{index}",
        }
        for index in range(12_005)
    ]

    inserted = _insert_generic_observations(con=con, plan=plan, rows=rows)  # type: ignore[arg-type]

    assert inserted.attempted == 12_005
    assert inserted.inserted == 12_005
    assert inserted.replaced == 0
    assert con.batch_sizes == [5_000, 5_000, 2_005]


def test_worldbank_observation_plans_skip_semantic_only_rows_without_metric_bindings() -> None:
    config = DatasetBatchConfig(snapshot_root=Path(tempfile.mkdtemp()) / "snap")
    datasets = [
        core_ingest.CatalogTransportDataset(
            catalog_dataset_id="worldbank-semantic",
            source="worldbank",
            title="Broad social development series",
            description="",
            source_dataset_id="SH.UHC.NOP2.ZS",
            update_frequency="annual",
            last_updated="2026-03-20",
            coverage_json="{}",
            access_json="{}",
            execution_tier="transport_ready",
            variables=("SH.UHC.NOP2.ZS",),
            keywords=(),
            themes=(),
            polisyos_metrics=(),
            connector_id="worldbank.wdi",
            profile_id="worldbank_wdi",
            request_dataset_id="SH.UHC.NOP2.ZS",
            default_filters={},
        ),
        core_ingest.CatalogTransportDataset(
            catalog_dataset_id="worldbank-metric",
            source="worldbank",
            title="GDP per capita",
            description="",
            source_dataset_id="NY.GDP.PCAP.PP.CD",
            update_frequency="annual",
            last_updated="2026-03-20",
            coverage_json="{}",
            access_json="{}",
            execution_tier="transport_ready",
            variables=("NY.GDP.PCAP.PP.CD",),
            keywords=(),
            themes=(),
            polisyos_metrics=("gdp_per_capita",),
            connector_id="worldbank.wdi",
            profile_id="worldbank_wdi",
            request_dataset_id="NY.GDP.PCAP.PP.CD",
            default_filters={},
        ),
        core_ingest.CatalogTransportDataset(
            catalog_dataset_id="worldbank-exact",
            source="worldbank",
            title="Direct seed aligned poverty indicator",
            description="",
            source_dataset_id="SI.POV.DDAY",
            update_frequency="annual",
            last_updated="2026-03-20",
            coverage_json="{}",
            access_json="{}",
            execution_tier="transport_ready",
            variables=("SI.POV.DDAY",),
            keywords=(),
            themes=(),
            polisyos_metrics=(),
            connector_id="worldbank.wdi",
            profile_id="worldbank_wdi",
            request_dataset_id="SI.POV.DDAY",
            default_filters={},
        ),
    ]
    alignments = [
        VariableAlignment(
            dataset_id="worldbank-semantic",
            dataset_var="SH.UHC.NOP2.ZS",
            canonical_var="health_outcomes",
            method=AlignmentMethod.SEMANTIC,
            confidence=0.82,
            evidence="semantic_jaccard",
        ),
        VariableAlignment(
            dataset_id="worldbank-metric",
            dataset_var="NY.GDP.PCAP.PP.CD",
            canonical_var="gdp_per_capita",
            method=AlignmentMethod.SEMANTIC,
            confidence=0.9,
            evidence="metric_binding_direct_to_canonical_root",
        ),
        VariableAlignment(
            dataset_id="worldbank-exact",
            dataset_var="SI.POV.DDAY",
            canonical_var="poverty_rate",
            method=AlignmentMethod.EXACT,
            confidence=0.99,
            evidence="seed_alignment",
        ),
    ]

    plans = _build_catalog_observation_plans(datasets, alignments, config=config)

    assert {(plan.dataset_id, plan.request_dataset_id) for plan in plans} == {
        ("worldbank-metric", "NY.GDP.PCAP.PP.CD"),
        ("worldbank-exact", "SI.POV.DDAY"),
    }


def test_eurostat_chunked_observation_requests_preserve_default_filters() -> None:
    plan = ObservationPlan(
        dataset_id="eurostat-une_rt_a",
        source="eurostat",
        raw_variable="une_rt_a",
        canonical_var="unemployment_rate",
        connector_id="eurostat.data",
        profile_id="eurostat_public",
        request_dataset_id="une_rt_a",
        default_filters={"unit": ["PC_ACT"], "sex": ["T"]},
        update_frequency="annual",
    )

    filters = core_ingest._eurostat_filters_for_country("PL", base_filters=plan.default_filters)
    requests = core_ingest._chunked_observation_requests(
        plan=plan,
        filters=core_ingest._filters_to_tuple(filters),
        source="eurostat",
    )

    assert [(request.date_start.year, request.date_end.year) for request in requests] == [
        (2018, 2019),
        (2020, 2021),
        (2022, 2022),
    ]
    assert all(request.filters for request in requests)
    assert all(dict(request.filters)["geo"] == ("PL",) for request in requests)
    assert all(dict(request.filters)["unit"] == ("PC_ACT",) for request in requests)
    assert all(dict(request.filters)["sex"] == ("T",) for request in requests)


def test_resolve_catalog_update_frequency_reclassifies_annual_eurostat_social_tables() -> None:
    resolved = core_ingest._resolve_catalog_update_frequency(
        source="eurostat",
        request_dataset_id="ILC_MDHO06B",
        title="Severe housing deprivation rate by household type",
        update_frequency="monthly",
        coverage_json='{"granularity":"annual"}',
    )

    assert resolved == "annual"


def test_resolve_catalog_update_frequency_preserves_explicit_subannual_eurostat_series() -> None:
    resolved = core_ingest._resolve_catalog_update_frequency(
        source="eurostat",
        request_dataset_id="NRG_TE_OILM",
        title="Monthly oil trade series",
        update_frequency="monthly",
        coverage_json='{"granularity":"annual"}',
    )

    assert resolved == "monthly"


def test_eurostat_monthly_observation_requests_split_to_single_year_windows() -> None:
    plan = ObservationPlan(
        dataset_id="eurostat-NRG_TE_OILM",
        source="eurostat",
        raw_variable="NRG_TE_OILM",
        canonical_var="energy_use",
        connector_id="eurostat.data",
        profile_id="eurostat_public",
        request_dataset_id="NRG_TE_OILM",
        default_filters={"unit": ["TJ"]},
        update_frequency="monthly",
    )

    filters = core_ingest._eurostat_filters_for_country("UA", base_filters=plan.default_filters)
    requests = core_ingest._chunked_observation_requests(
        plan=plan,
        filters=core_ingest._filters_to_tuple(filters),
        source="eurostat",
    )

    assert [(request.date_start.year, request.date_end.year) for request in requests] == [
        (2018, 2018),
        (2019, 2019),
        (2020, 2020),
        (2021, 2021),
        (2022, 2022),
    ]
    assert all(dict(request.filters)["geo"] == ("UA",) for request in requests)
    assert all(dict(request.filters)["unit"] == ("TJ",) for request in requests)


def test_build_observation_shards_batches_worldbank_countries_into_one_request() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(
            snapshot_root=Path(tmpdir) / "snap",
            active_countries=("UA", "DE", "PL"),
        )
        plan = ObservationPlan(
            dataset_id="worldbank-NY.GDP.PCAP.PP.CD",
            source="worldbank",
            raw_variable="NY.GDP.PCAP.PP.CD",
            canonical_var="gdp_per_capita",
            connector_id="worldbank.wdi",
            profile_id="worldbank_wdi",
            request_dataset_id="NY.GDP.PCAP.PP.CD",
            default_filters={},
            update_frequency="annual",
        )

        shards = core_ingest._build_observation_shards([plan], config=config)

        assert len(shards) == 1
        assert shards[0].country_code is None
        assert core_ingest._shard_countries(shards[0], config=config) == ("DE", "PL", "UA")


def test_observation_plan_order_prioritizes_annual_before_monthly() -> None:
    config = DatasetBatchConfig(snapshot_root=Path(tempfile.mkdtemp()) / "snap")
    datasets = [
        core_ingest.CatalogTransportDataset(
            catalog_dataset_id="eurostat-annual",
            source="eurostat",
            title="Annual unemployment",
            description="",
            source_dataset_id="UNE_RT_A",
            update_frequency="annual",
            last_updated="2026-03-19",
            coverage_json="{}",
            access_json="{}",
            execution_tier="transport_ready",
            variables=("UNE_RT_A",),
            keywords=(),
            themes=(),
            polisyos_metrics=("unemployment_rate",),
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="UNE_RT_A",
            default_filters={},
        ),
        core_ingest.CatalogTransportDataset(
            catalog_dataset_id="eurostat-monthly",
            source="eurostat",
            title="Monthly oil trade",
            description="",
            source_dataset_id="NRG_TE_OILM",
            update_frequency="monthly",
            last_updated="2026-03-19",
            coverage_json="{}",
            access_json="{}",
            execution_tier="transport_ready",
            variables=("NRG_TE_OILM",),
            keywords=(),
            themes=(),
            polisyos_metrics=("energy_use",),
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="NRG_TE_OILM",
            default_filters={},
        ),
    ]
    plans = [
        ObservationPlan(
            dataset_id="eurostat-monthly",
            source="eurostat",
            raw_variable="NRG_TE_OILM",
            canonical_var="energy_use",
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="NRG_TE_OILM",
            default_filters={},
            update_frequency="monthly",
        ),
        ObservationPlan(
            dataset_id="eurostat-annual",
            source="eurostat",
            raw_variable="UNE_RT_A",
            canonical_var="unemployment_rate",
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="UNE_RT_A",
            default_filters={},
            update_frequency="annual",
        ),
    ]

    ordered = _limit_observation_plans(plans, datasets, config=config)

    assert [plan.dataset_id for plan in ordered] == ["eurostat-annual", "eurostat-monthly"]


def test_ingest_catalog_observations_skips_oversized_monthly_payload(monkeypatch) -> None:
    async def _fake_fetch_rows(_plan, _cache, *, config):  # noqa: ARG001
        return [
            {"geo": "PL", "time_period": f"2022-{(index % 12) + 1:02d}", "value": float(index)}
            for index in range(_observation_payload_row_limit(plan) + 1)  # type: ignore[arg-type]
        ]

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap", max_datasets_per_source=5)
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
        finally:
            con.close()

        plan = ObservationPlan(
            dataset_id="eurostat-NRG_TE_OILM",
            source="eurostat",
            raw_variable="NRG_TE_OILM",
            canonical_var="energy_use",
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="NRG_TE_OILM",
            default_filters={},
            update_frequency="monthly",
        )
        monkeypatch.setattr(core_ingest, "_fetch_observation_rows", _fake_fetch_rows)

        stats = core_ingest.run_coro_sync(
            core_ingest._ingest_catalog_observations(config.db_path, [plan], config=config)
        )

        assert stats.failures == 1
        assert stats.observations == 0

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            observed = con.execute("SELECT COUNT(*) FROM ds_observations").fetchone()[0]
        finally:
            con.close()

        assert observed == 0


def test_ingest_catalog_observations_keeps_large_payloads_in_full_run(monkeypatch) -> None:
    async def _fake_fetch_rows(_plan, _cache, *, config):  # noqa: ARG001
        return [
            {
                "geo": "PL",
                "time_period": "2022",
                "value": float(index),
                "partner": f"P{index}",
            }
            for index in range(6)
        ]

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(snapshot_root=Path(tmpdir) / "snap")
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
        finally:
            con.close()

        plan = ObservationPlan(
            dataset_id="eurostat-NRG_TE_OILM",
            source="eurostat",
            raw_variable="NRG_TE_OILM",
            canonical_var="energy_use",
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="NRG_TE_OILM",
            default_filters={},
            update_frequency="monthly",
        )
        monkeypatch.setattr(core_ingest, "_fetch_observation_rows", _fake_fetch_rows)
        monkeypatch.setattr(core_ingest, "_observation_payload_row_limit", lambda _plan: 5)

        stats = core_ingest.run_coro_sync(
            core_ingest._ingest_catalog_observations(config.db_path, [plan], config=config)
        )

        assert stats.failures == 0
        assert stats.observations == 6

        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            observed = con.execute("SELECT COUNT(*) FROM ds_observations").fetchone()[0]
        finally:
            con.close()

        assert observed == 6


def test_parallel_observation_ingest_dedupes_shared_upstream_fetches(monkeypatch) -> None:
    fetch_calls: list[tuple[str, str, str]] = []

    async def _fake_fetch_rows(shard, _cache, *, config):  # noqa: ARG001
        fetch_calls.append((shard.plan.request_dataset_id, shard.country_code or "", shard.plan.canonical_var))
        return [{"geo": "UA", "time_period": "2022", "value": 1.0}]

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(
            snapshot_root=Path(tmpdir) / "snap",
            max_datasets_per_source=5,
            active_countries=("UA",),
        )
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
        finally:
            con.close()

        plans = [
            ObservationPlan(
                dataset_id="eurostat-une_rt_a",
                source="eurostat",
                raw_variable="une_rt_a",
                canonical_var="unemployment_rate",
                connector_id="eurostat.data",
                profile_id="eurostat_public",
                request_dataset_id="une_rt_a",
                default_filters={"unit": ["PC_ACT"]},
                update_frequency="annual",
            ),
            ObservationPlan(
                dataset_id="eurostat-une_rt_a",
                source="eurostat",
                raw_variable="une_rt_a",
                canonical_var="labor_force_participation",
                connector_id="eurostat.data",
                profile_id="eurostat_public",
                request_dataset_id="une_rt_a",
                default_filters={"unit": ["PC_ACT"]},
                update_frequency="annual",
            ),
        ]
        monkeypatch.setattr(core_ingest, "_fetch_observation_rows", _fake_fetch_rows)

        stats = core_ingest.run_coro_sync(
            core_ingest._ingest_catalog_observations(config.db_path, plans, config=config)
        )

        assert len(fetch_calls) == 1
        assert stats.observations == 2


def test_parallel_observation_ingest_negative_support_cache_skips_sibling_shards(monkeypatch) -> None:
    fetch_calls: list[tuple[str | None, int, int]] = []

    async def _fake_fetch_rows(shard, _cache, *, config):  # noqa: ARG001
        fetch_calls.append((shard.country_code, shard.start_year, shard.end_year))
        raise RuntimeError("HTTP 400")

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(
            snapshot_root=Path(tmpdir) / "snap",
            active_countries=("UA",),
        )
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
        finally:
            con.close()

        plan = ObservationPlan(
            dataset_id="eurostat-NRG_TE_OILM",
            source="eurostat",
            raw_variable="NRG_TE_OILM",
            canonical_var="energy_use",
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="NRG_TE_OILM",
            default_filters={},
            update_frequency="monthly",
        )
        monkeypatch.setattr(core_ingest, "_fetch_observation_rows", _fake_fetch_rows)

        stats = core_ingest.run_coro_sync(
            core_ingest._ingest_catalog_observations(config.db_path, [plan], config=config)
        )

        assert len(fetch_calls) == 1
        assert stats.failures == 1
        assert stats.empty_shards == 4


def test_parallel_observation_ingest_persists_capability_snapshots_and_writer_metrics(monkeypatch) -> None:
    async def _fake_fetch_rows(_shard, _cache, *, config):  # noqa: ARG001
        return [{"geo": "UA", "time_period": "2022", "value": 1.0}]

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(
            snapshot_root=Path(tmpdir) / "snap",
            active_countries=("UA",),
        )
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
        finally:
            con.close()

        plan = ObservationPlan(
            dataset_id="eurostat-une_rt_a",
            source="eurostat",
            raw_variable="une_rt_a",
            canonical_var="unemployment_rate",
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="une_rt_a",
            default_filters={},
            update_frequency="annual",
        )
        monkeypatch.setattr(core_ingest, "_fetch_observation_rows", _fake_fetch_rows)

        stats = core_ingest.run_coro_sync(
            core_ingest._ingest_catalog_observations(config.db_path, [plan], config=config)
        )

        assert stats.completed_shards == 3
        with open(config.observation_ingest_checkpoint_path, "r", encoding="utf-8") as fh:
            checkpoint = json.load(fh)
        assert "capability_snapshots" in checkpoint
        assert checkpoint["capability_snapshots"]

        with open(config.stage_state_path, "r", encoding="utf-8") as fh:
            stage_state = json.load(fh)
        metadata = stage_state["core_sources_ingest"]["metadata"]
        assert "writer_flush_count" in metadata
        assert metadata["writer_flush_count"] >= 1
        assert "request_count_by_source" in metadata
        assert metadata["request_count_by_source"].get("eurostat", 0) >= 0


def test_parallel_observation_ingest_uses_eurostat_async_path(monkeypatch) -> None:
    async def _fake_describe(self, _handle, dataset_id):  # noqa: ARG001
        return DatasetCapabilitySnapshot(
            source="eurostat",
            dataset_id=str(dataset_id),
            resolved_dataset_id=str(dataset_id),
            preferred_transport="dual",
            dimension_order=("geo", "time", "partner"),
            allowed_positions={
                "geo": ("UA",),
                "partner": tuple(f"P{index}" for index in range(30_000)),
            },
            estimated_cardinality=60_000,
            version_hint="latest",
            last_checked_at=datetime.now(timezone.utc),
        )

    async def _fail_sync_fetch(self, _handle, _request):  # noqa: ARG001
        raise AssertionError("sync Eurostat fetch should not be used for async-eligible shard")

    async def _fake_fetch_async(self, _handle, request):  # noqa: ARG001
        return core_ingest.AsyncFetchLease(
            lease_id=f"lease-{request.dataset_id}",
            connector_id=self.connector_id,
            dataset_id=request.dataset_id,
            request_key=request.dataset_id,
            status="submitted",
            poll_after_seconds=0.0,
            status_url="https://example.test/status",
            download_url="https://example.test/data",
        )

    async def _fake_poll_async_fetch(self, _handle, lease):  # noqa: ARG001
        return type(
            "EurostatAsyncResult",
            (),
            {
                "data": pd.DataFrame([{"geo": "UA", "time_period": "2022", "value": 1.0}]),
                "bytes_transferred": 123,
            },
        )()

    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetBatchConfig(
            snapshot_root=Path(tmpdir) / "snap",
            active_countries=("UA",),
        )
        con = duckdb.connect(str(config.db_path))
        try:
            _ensure_registry_tables(con)
        finally:
            con.close()

        plan = ObservationPlan(
            dataset_id="eurostat-async-ds",
            source="eurostat",
            raw_variable="ASYNC_DS",
            canonical_var="energy_use",
            connector_id="eurostat.data",
            profile_id="eurostat_public",
            request_dataset_id="ASYNC_DS",
            default_filters={},
            update_frequency="annual",
        )
        monkeypatch.setattr(EurostatConnector, "describe_dataset", _fake_describe)
        monkeypatch.setattr(EurostatConnector, "fetch", _fail_sync_fetch)
        monkeypatch.setattr(EurostatConnector, "fetch_async", _fake_fetch_async)
        monkeypatch.setattr(EurostatConnector, "poll_async_fetch", _fake_poll_async_fetch)

        stats = core_ingest.run_coro_sync(
            core_ingest._ingest_catalog_observations(config.db_path, [plan], config=config)
        )

        assert stats.completed_shards == 3
        with open(config.observation_ingest_checkpoint_path, "r", encoding="utf-8") as fh:
            checkpoint = json.load(fh)
        assert checkpoint["async_fetch_leases"] == {}


def test_append_shard_result_tracks_complete_empty_and_complete_with_rows() -> None:
    completed_results: list[dict[str, object]] = []
    failed_results: list[dict[str, object]] = []
    deferred_results: list[dict[str, object]] = []
    source_summary: dict[str, dict[str, int]] = {}

    core_ingest._append_shard_result(
        result=core_ingest.ObservationShardResult(
            shard_id="rows",
            status="complete_with_rows",
            source="worldbank",
            dataset_id="ds",
            raw_variable="value",
            canonical_var="gdp_per_capita",
            country_code="UA",
            start_year=2020,
            end_year=2020,
            row_count=3,
        ),
        completed_results=completed_results,
        failed_results=failed_results,
        deferred_results=deferred_results,
        source_summary=source_summary,
    )
    core_ingest._append_shard_result(
        result=core_ingest.ObservationShardResult(
            shard_id="empty",
            status="complete_empty",
            source="worldbank",
            dataset_id="ds",
            raw_variable="value",
            canonical_var="gdp_per_capita",
            country_code="UA",
            start_year=2021,
            end_year=2021,
            row_count=0,
        ),
        completed_results=completed_results,
        failed_results=failed_results,
        deferred_results=deferred_results,
        source_summary=source_summary,
    )

    assert len(completed_results) == 2
    assert source_summary["worldbank"]["complete"] == 2
    assert source_summary["worldbank"]["complete_with_rows"] == 1
    assert source_summary["worldbank"]["complete_empty"] == 1
    assert source_summary["worldbank"]["rows"] == 3


def test_core_sources_ingest_manifest_propagates_shard_counts(monkeypatch, tmp_path) -> None:
    async def _fake_run(_config):
        return core_ingest.CoreSourcesIngestStats(
            registry_datasets=1,
            variable_alignments=2,
            observations=3,
            observations_attempted=3,
            observations_inserted=3,
            observations_replaced=0,
            failures=1,
            completed_shards=4,
            deferred_shards=5,
            failed_shards=6,
        )

    monkeypatch.setattr(core_ingest, "_run_core_sources_ingest_async", _fake_run)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    import asyncio

    stats = asyncio.run(core_ingest.run_core_sources_ingest_async(config))

    assert stats.completed_shards == 4
    with open(config.manifests_dir / "core_sources_ingest.json", "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["metrics"]["completed_shards"] == 4
    assert payload["metrics"]["deferred_shards"] == 5
    assert payload["metrics"]["failed_shards"] == 6
