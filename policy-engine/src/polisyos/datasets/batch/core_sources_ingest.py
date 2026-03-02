"""Stage 0b: ingest core transportability sources (WGI/WDI/WVS) into registry tables."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.knowledge.variable_alignment import load_seed_alignments
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.sources.wvs import WVSConnector

logger = logging.getLogger(__name__)

_WGI_INDICATORS: dict[str, str] = {
    "RL.EST": "institutional_quality",
    "CC.EST": "corruption_level",
    "GE.EST": "state_capacity",
}
_WDI_INDICATORS: dict[str, str] = {
    "NY.GDP.PCAP.PP.CD": "gdp_per_capita",
}
_WVS_INDICATORS: dict[str, str] = {
    "A165": "social_trust",
    "A173": "cultural_cluster",
}
_CORE_COUNTRIES: tuple[str, ...] = ("UA", "DE", "PL")
_CORE_YEARS: tuple[int, ...] = (2018, 2019, 2020, 2021, 2022)


@dataclass
class CoreSourcesIngestStats:
    registry_datasets: int = 0
    variable_alignments: int = 0
    observations: int = 0
    failures: int = 0


def run_core_sources_ingest(config: DatasetBatchConfig) -> CoreSourcesIngestStats:
    """Sync wrapper for ingesting registry/observation data used by DatasetRegistry."""
    started_at = datetime.now(UTC).isoformat()
    stats = asyncio.run(_run_core_sources_ingest_async(config))
    write_stage_manifest(
        manifest_path=config.manifests_dir / "core_sources_ingest.json",
        stage="core_sources_ingest",
        status="ok" if stats.failures == 0 else "warning",
        metrics={
            "registry_datasets": stats.registry_datasets,
            "variable_alignments": stats.variable_alignments,
            "observations": stats.observations,
            "failures": stats.failures,
        },
        artifacts=[config.db_path],
        started_at=started_at,
    )
    return stats


async def _run_core_sources_ingest_async(config: DatasetBatchConfig) -> CoreSourcesIngestStats:
    stats = CoreSourcesIngestStats()

    with duckdb.connect(str(config.db_path)) as con:
        _ensure_registry_tables(con)
        stats.registry_datasets = _upsert_registry_datasets(con)
        stats.variable_alignments = _upsert_seed_alignments(con, _seed_alignments_path())

    wb = WorldBankConnector()
    wvs = WVSConnector()
    wb_handle = None
    wvs_handle = None
    try:
        wb_handle = await wb.connect(_resolve_profile_config("worldbank_wdi"))
        wvs_handle = await wvs.connect(_resolve_profile_config("wvs_wave7"))

        with duckdb.connect(str(config.db_path)) as con:
            for country in _CORE_COUNTRIES:
                for indicator, canonical_var in _WGI_INDICATORS.items():
                    try:
                        result = await wb.fetch(
                            wb_handle,
                            FetchRequest(
                                dataset_id=indicator,
                                filters=(("country", (country,)),),
                                date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                                date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                            ),
                        )
                        stats.observations += _insert_world_bank_observations(
                            con=con,
                            dataset_id="WB_WGI",
                            raw_variable=indicator,
                            canonical_var=canonical_var,
                            country_code=country,
                            frame=result.data,
                        )
                    except Exception as exc:
                        stats.failures += 1
                        logger.warning("WGI ingest failed for %s/%s: %s", country, indicator, exc)

                for indicator, canonical_var in _WDI_INDICATORS.items():
                    try:
                        result = await wb.fetch(
                            wb_handle,
                            FetchRequest(
                                dataset_id=indicator,
                                filters=(("country", (country,)),),
                                date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                                date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                            ),
                        )
                        stats.observations += _insert_world_bank_observations(
                            con=con,
                            dataset_id="WB_WDI",
                            raw_variable=indicator,
                            canonical_var=canonical_var,
                            country_code=country,
                            frame=result.data,
                        )
                    except Exception as exc:
                        stats.failures += 1
                        logger.warning("WDI ingest failed for %s/%s: %s", country, indicator, exc)

                for indicator, canonical_var in _WVS_INDICATORS.items():
                    for year in _CORE_YEARS:
                        try:
                            result = await wvs.fetch(
                                wvs_handle,
                                FetchRequest(
                                    dataset_id=indicator,
                                    filters=(
                                        ("country", (country,)),
                                        ("survey_year", (str(year),)),
                                    ),
                                ),
                            )
                            stats.observations += _insert_wvs_observations(
                                con=con,
                                dataset_id="WVS_W7",
                                raw_variable=indicator,
                                canonical_var=canonical_var,
                                country_code=country,
                                frame=result.data,
                            )
                        except Exception as exc:
                            stats.failures += 1
                            logger.warning(
                                "WVS ingest failed for %s/%s/%s: %s",
                                country,
                                indicator,
                                year,
                                exc,
                            )
            con.execute("CHECKPOINT")
    finally:
        if wb_handle is not None:
            await wb.disconnect(wb_handle)
        if wvs_handle is not None:
            await wvs.disconnect(wvs_handle)

    return stats


def _resolve_profile_config(profile_id: str) -> ConnectionConfig:
    registry = SourceProfileRegistry.get_instance()
    profile = registry.get(profile_id)
    if profile is None:
        raise ValueError(f"Missing source profile: {profile_id}")
    return resolve_connection_config(profile)


def _seed_alignments_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )


def _ensure_registry_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_registry_datasets (
            dataset_id    VARCHAR PRIMARY KEY,
            provider      VARCHAR NOT NULL,
            title         VARCHAR NOT NULL,
            coverage_json VARCHAR NOT NULL,
            access_json   VARCHAR NOT NULL,
            update_freq   VARCHAR NOT NULL,
            last_updated  VARCHAR NOT NULL
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_variable_alignments (
            dataset_id     VARCHAR NOT NULL,
            raw_variable   VARCHAR NOT NULL,
            canonical_var  VARCHAR NOT NULL,
            method         VARCHAR NOT NULL,
            confidence     FLOAT NOT NULL,
            evidence       VARCHAR NOT NULL,
            is_proxy       BOOLEAN DEFAULT FALSE,
            proxy_penalty  FLOAT DEFAULT 0.0,
            PRIMARY KEY (dataset_id, raw_variable, canonical_var)
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_observations (
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
        "CREATE INDEX IF NOT EXISTS idx_registry_provider "
        "ON ds_registry_datasets(provider)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_va_canonical "
        "ON ds_variable_alignments(canonical_var)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_va_dataset "
        "ON ds_variable_alignments(dataset_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_country_year "
        "ON ds_observations(country_code, year)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_dataset_raw "
        "ON ds_observations(dataset_id, raw_variable)"
    )


def _upsert_registry_datasets(con: duckdb.DuckDBPyConnection) -> int:
    last_updated = datetime.now(UTC).date().isoformat()
    datasets = [
        (
            "WB_WGI",
            "world_bank",
            "World Governance Indicators",
            json.dumps(
                {"countries": [], "time_range": "1996-2023", "granularity": "country-year"},
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "access_type": "open",
                    "api_endpoint": "https://api.worldbank.org/v2",
                    "license": "CC-BY-4.0",
                },
                separators=(",", ":"),
            ),
            "annual",
            last_updated,
        ),
        (
            "WB_WDI",
            "world_bank",
            "World Development Indicators",
            json.dumps(
                {"countries": [], "time_range": "1960-2023", "granularity": "country-year"},
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "access_type": "open",
                    "api_endpoint": "https://api.worldbank.org/v2",
                    "license": "CC-BY-4.0",
                },
                separators=(",", ":"),
            ),
            "annual",
            last_updated,
        ),
        (
            "WVS_W7",
            "world_values_survey",
            "World Values Survey Wave 7",
            json.dumps(
                {"countries": [], "time_range": "2017-2022", "granularity": "country-wave"},
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "access_type": "open",
                    "api_endpoint": "https://api.worldvaluessurvey.org/v1",
                    "license": "WVS terms",
                },
                separators=(",", ":"),
            ),
            "wave",
            last_updated,
        ),
        (
            "IMF_SHADOW",
            "imf",
            "IMF Shadow Economy Estimates",
            json.dumps(
                {"countries": [], "time_range": "1990-2022", "granularity": "country-year"},
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "access_type": "open",
                    "api_endpoint": None,
                    "license": "IMF terms",
                },
                separators=(",", ":"),
            ),
            "annual",
            last_updated,
        ),
    ]
    con.executemany(
        "INSERT OR REPLACE INTO ds_registry_datasets "
        "(dataset_id, provider, title, coverage_json, access_json, update_freq, last_updated) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        datasets,
    )
    return len(datasets)


def _upsert_seed_alignments(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    alignments = load_seed_alignments(path)
    rows = [
        (
            item.dataset_id,
            item.dataset_var,
            item.canonical_var,
            item.method.value,
            item.confidence,
            item.evidence,
            item.is_proxy,
            item.proxy_penalty,
        )
        for item in alignments
    ]
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO ds_variable_alignments "
        "(dataset_id, raw_variable, canonical_var, method, confidence, "
        "evidence, is_proxy, proxy_penalty) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _insert_world_bank_observations(
    *,
    con: duckdb.DuckDBPyConnection,
    dataset_id: str,
    raw_variable: str,
    canonical_var: str,
    country_code: str,
    frame,
) -> int:
    if frame is None or frame.empty:
        return 0
    rows: list[tuple] = []
    for _, row in frame.iterrows():
        year = _as_int(row.get("year"))
        value = _as_float(row.get("value"))
        cc = str(row.get("country_code") or country_code or "").strip().upper()
        if year is None or value is None or not cc:
            continue
        obs_id = _observation_id(
            dataset_id,
            raw_variable,
            cc,
            year=year,
            survey_year=None,
            wave=None,
        )
        rows.append(
            (
                obs_id,
                dataset_id,
                raw_variable,
                canonical_var,
                cc,
                year,
                None,
                None,
                value,
                "{}",
            )
        )
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO ds_observations "
        "(observation_id, dataset_id, raw_variable, canonical_var, country_code, "
        "year, survey_year, wave, value, condition_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _insert_wvs_observations(
    *,
    con: duckdb.DuckDBPyConnection,
    dataset_id: str,
    raw_variable: str,
    canonical_var: str,
    country_code: str,
    frame,
) -> int:
    if frame is None or frame.empty:
        return 0
    rows: list[tuple] = []
    for _, row in frame.iterrows():
        survey_year = _as_int(row.get("survey_year"))
        wave = _as_int(row.get("wave"))
        value = _as_float(row.get("value"))
        cc = str(row.get("country_code") or country_code or "").strip().upper()
        if survey_year is None or value is None or not cc:
            continue
        obs_id = _observation_id(
            dataset_id,
            raw_variable,
            cc,
            year=survey_year,
            survey_year=survey_year,
            wave=wave,
        )
        rows.append(
            (
                obs_id,
                dataset_id,
                raw_variable,
                canonical_var,
                cc,
                survey_year,
                survey_year,
                wave,
                value,
                "{}",
            )
        )
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO ds_observations "
        "(observation_id, dataset_id, raw_variable, canonical_var, country_code, "
        "year, survey_year, wave, value, condition_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _observation_id(
    dataset_id: str,
    raw_variable: str,
    country_code: str,
    *,
    year: int | None,
    survey_year: int | None,
    wave: int | None,
) -> str:
    text = f"{dataset_id}|{raw_variable}|{country_code}|{year}|{survey_year}|{wave}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _as_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["CoreSourcesIngestStats", "run_core_sources_ingest"]
