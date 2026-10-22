from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path  # noqa: TC003
from types import SimpleNamespace
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import yaml

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
    from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

CORE_SOURCES = (
    "oecd",
    "eurostat",
    "worldbank",
    "wvs",
    "ilo",
    "who",
    "unesco_uis",
    "unpd",
)
BLOCKING_SOURCES = (
    *CORE_SOURCES,
    "data_gov_ua_exec",
    "data_gov_ro_exec",
    "data_gov_md_exec",
    "data_gov_pl_exec",
)
SEED_PARENTS = (
    "data_gov_ua_broad",
    "data_gov_ro_broad",
    "data_gov_md_broad",
    "data_gov_pl_broad",
)
FIXTURE_SUPPORTED_SOURCE_IDS = frozenset((*BLOCKING_SOURCES, *SEED_PARENTS))
PROFILE_IDS = (
    "worldbank_wdi",
    "wvs_wave7",
    "eurostat_public",
    "oecd_sdmx",
    "ilo_sdmx",
    "who_gho",
    "unpd_dataportal",
    "unesco_uis_public",
    "data_gov_ua",
    "data_gov_ro",
    "data_gov_md",
    "data_gov_pl",
)
_COUNTRIES = (("UA", "UKR"), ("DE", "DEU"), ("PL", "POL"), ("RO", "ROU"), ("MD", "MDA"))


@dataclass(frozen=True)
class PublishedFixture:
    snapshot_root: Path
    database_path: Path
    producer_graph: DatasetCatalogGraph
    profile_registry: SourceProfileRegistry
    readiness: dict[str, bool]
    evaluation_mode: str
    selected_source_ids: tuple[str, ...]
    source_registry_sha256: str
    profile_ids: tuple[str, ...]
    table_counts: dict[str, int]
    report_basis_state: str
    report_basis_reason: str | None
    publish_blocked_reason: str | None
    publish_receipt_state: str
    publish_receipt_reason: str | None
    http_server: ThreadingHTTPServer
    http_server_thread: threading.Thread

    def close(self) -> None:
        self.http_server.shutdown()
        self.http_server.server_close()
        self.http_server_thread.join(timeout=2)


class _FixtureServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "PolicyOSFixture/1"

    def do_HEAD(self) -> None:
        if self.path.startswith(("/reach/", "/resource/")):
            self._send(200, b"", "text/csv")
        else:
            self._send(404, b"", "text/plain")

    def do_GET(self) -> None:
        route = urlparse(self.path)
        path = route.path
        payload: dict[str, object]
        if path.startswith(("/reach/", "/resource/")):
            self._send(200, b"country_code,year,value\nUA,2020,1\n", "text/csv")
            return
        if path in {"/harvest/oecd", "/harvest/eurostat", "/harvest/ilo"}:
            agency = {
                "/harvest/oecd": "OECD",
                "/harvest/eurostat": "ESTAT",
                "/harvest/ilo": "ILO",
            }[path]
            body = (
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<message:Structure xmlns:message='urn:fixture:message' "
                "xmlns:str='urn:fixture:structure' xmlns:com='urn:fixture:common'>"
                "<str:Dataflows>"
                f"<str:Dataflow id='FIXTURE_{agency}' agencyID='{agency}' version='1.0'>"
                f"<com:Name>{agency} fixture source catalog</com:Name>"
                f"<com:Description>Annual statistical data for {agency}</com:Description>"
                "</str:Dataflow></str:Dataflows></message:Structure>"
            ).encode()
            self._send(200, body, "application/xml")
            return
        if path == "/harvest/worldbank":
            rows = [
                {
                    "id": "NY.GDP.PCAP.PP.CD",
                    "name": "GDP per capita purchasing power parity",
                    "sourceNote": "Gross domestic product per capita",
                }
            ]
            self._send(200, json.dumps([{"total": len(rows)}, rows]).encode(), "application/json")
            return
        if path == "/harvest/who":
            payload = {
                "value": [
                    {
                        "IndicatorCode": "WHOSIS_000001",
                        "IndicatorName": "Life expectancy at birth",
                        "Definition": "Life expectancy and health outcomes by country",
                    }
                ]
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
            return
        if path == "/harvest/unesco_uis":
            payload = {
                "data": [
                    {
                        "indicator_id": "UIS.NERA.1",
                        "name": "Primary school enrollment education outcomes",
                        "description": "Education enrollment by country and year",
                    }
                ]
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
            return
        if path == "/harvest/unpd":
            query = parse_qs(route.query)
            page = int(query.get("page", ["1"])[0])
            rows = (
                [
                    {
                        "indicator_id": "POP_001",
                        "name": "International migration flows",
                        "description": "Migration and population movement by country",
                    }
                ]
                if page == 1
                else []
            )
            self._send(200, json.dumps({"data": rows, "next": None}).encode(), "application/json")
            return
        if path in {
            "/harvest/data_gov_ua_broad",
            "/harvest/data_gov_ro_broad",
            "/harvest/data_gov_md_broad",
        }:
            source = path.rsplit("/", 1)[-1]
            package = _ckan_package(source, self._base_url())
            payload = {
                "success": True,
                "result": {"count": 1, "results": [package]},
            }
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
            return
        if path == "/harvest/data_gov_pl_broad":
            payload = {
                "data": [
                    {
                        "id": "fixture-poland-open-data",
                        "type": "datasets",
                        "attributes": {
                            "slug": "budzet-edukacja-zdrowie-bezrobocie-migracja",
                            "title": "Budżet lokalny, edukacja, zdrowie, bezrobocie i migracja",
                            "description": "Dane statystyczne dla Polski",
                            "keywords": [
                                "budżet",
                                "dochody",
                                "wydatki",
                                "edukacja",
                                "zdrowie",
                                "bezrobocie",
                                "migracja",
                                "demografia",
                            ],
                            "formats": ["JSON"],
                            "regions": ["Polska"],
                        },
                        "relationships": {
                            "resources": {"links": {"related": self._base_url() + "/resource/pl"}}
                        },
                        "links": {"self": self._base_url() + "/resource/pl"},
                    }
                ],
                "links": {"next": None},
            }
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")
            return
        self._send(404, b"not found", "text/plain")

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _base_url(self) -> str:
        address = self.server.server_address
        if not isinstance(address, tuple) or len(address) < 2:
            raise AssertionError(f"fixture server returned an invalid address: {address!r}")
        host, port = address[0], address[1]
        if not isinstance(host, str) or not isinstance(port, int):
            raise AssertionError(f"fixture server returned an invalid host/port: {address!r}")
        return f"http://{host}:{port}"


def _records_fetched(outcome: dict[str, object]) -> int:
    """Return a source receipt's nonnegative raw count, failing closed on bad data."""
    raw_count = outcome.get("records_fetched", 0)
    if not isinstance(raw_count, (int, float, str)):
        return 0
    try:
        return max(0, int(raw_count or 0))
    except ValueError:
        return 0


def _ckan_package(source: str, base_url: str) -> dict[str, object]:
    if source == "data_gov_ua_broad":
        slug = "fixture-ukraine-population-migration-labor-health-education-budget"
        title = "Population migration employment health education and public budget statistics"
        keywords = [
            "population",
            "migration",
            "employment",
            "unemployment",
            "health",
            "education",
            "budget",
            "poverty",
        ]
    elif source == "data_gov_ro_broad":
        slug = "fixture-romania-buget-educatie-sanatate-somaj-migratie"
        title = (
            "Buget local municipal educatie sanatate somaj piata muncii migratie "
            "demografie Romania comparator Ukraine regional"
        )
        keywords = [
            "buget",
            "educatie",
            "sanatate",
            "somaj",
            "muncii",
            "migration",
            "demografie",
            "Romania",
            "Ukraine",
            "regional",
            "comparator",
        ]
    else:
        slug = "fixture-moldova-buget-educatie-sanatate-somaj-migratie"
        title = (
            "Buget local municipal educatie sanatate somaj piata muncii migratie "
            "demografie Moldova regional comparator"
        )
        keywords = [
            "buget",
            "educatie",
            "sanatate",
            "somaj",
            "muncii",
            "migration",
            "demografie",
            "Moldova",
            "regional",
            "comparator",
        ]
    return {
        "id": slug,
        "name": slug,
        "title": title,
        "notes": "Annual open data for local public services and regional comparison.",
        "description": title,
        "keywords": keywords,
        "tags": [{"name": value} for value in keywords],
        "organization": {"name": "fixture-public-data-office"},
        "resources": [
            {
                "id": slug + "-csv",
                "name": "fixture machine-readable source data",
                "url": base_url + "/resource/" + slug + ".csv",
                "format": "CSV",
            }
        ],
    }


def _assert_fixture_source_coverage(registry_path: Path) -> frozenset[str]:
    """Fail closed unless the fixture map covers canonical blockers and their seed closure."""
    from polisyos.data_forge.domains.catalog.batch.source_registry import load_source_registry

    required_sources = load_source_registry(registry_path).enabled_sources(
        run_profile="preflight_core"
    )
    required_ids = frozenset(source.name for source in required_sources)
    missing = sorted(required_ids - FIXTURE_SUPPORTED_SOURCE_IDS)
    extra = sorted(FIXTURE_SUPPORTED_SOURCE_IDS - required_ids)
    if missing or extra:
        raise AssertionError(
            "fixture source coverage mismatch: "
            f"owner-required but fixture unsupported={missing}; "
            f"fixture-supported but not owner-required={extra}"
        )
    return required_ids


@dataclass(frozen=True)
class FixtureSourceRegistrySnapshot:
    """Bind fixture selection and writing to one immutable source registry byte snapshot."""

    source_bytes: bytes
    source_sha256: str
    required_source_ids: frozenset[str]
    snapshot_path: Path


def _capture_fixture_source_registry(
    source_registry_path: Path, snapshot_path: Path
) -> FixtureSourceRegistrySnapshot:
    """Read canonical registry bytes once and select from an exact temporary snapshot."""
    source_bytes = source_registry_path.read_bytes()
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(source_bytes)
    if snapshot_path.read_bytes() != source_bytes:
        raise AssertionError("fixture source registry snapshot did not preserve source bytes")
    required_source_ids = _assert_fixture_source_coverage(snapshot_path)
    if snapshot_path.read_bytes() != source_bytes:
        raise AssertionError("fixture source registry snapshot changed during owner selection")
    return FixtureSourceRegistrySnapshot(
        source_bytes=source_bytes,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        required_source_ids=required_source_ids,
        snapshot_path=snapshot_path,
    )


def _write_registry(
    registry_path: Path, base_url: str, snapshot: FixtureSourceRegistrySnapshot
) -> tuple[str, ...]:
    source_bytes = snapshot.source_bytes
    if hashlib.sha256(source_bytes).hexdigest() != snapshot.source_sha256:
        raise AssertionError("fixture source registry bytes changed after coverage preflight")
    if snapshot.snapshot_path.read_bytes() != source_bytes:
        raise AssertionError("fixture source registry snapshot changed after coverage preflight")
    required_source_ids = _assert_fixture_source_coverage(snapshot.snapshot_path)
    if snapshot.snapshot_path.read_bytes() != source_bytes:
        raise AssertionError("fixture source registry snapshot changed during owner selection")
    if required_source_ids != snapshot.required_source_ids:
        raise AssertionError("fixture source selection changed after coverage preflight")
    payload = yaml.safe_load(source_bytes)
    if not isinstance(payload, dict):
        raise AssertionError("fixture source registry snapshot must be a mapping")
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise AssertionError("fixture source registry snapshot must contain a source list")
    selected = [
        dict(item)
        for item in raw_sources
        if isinstance(item, dict) and str(item.get("name")) in required_source_ids
    ]
    selected_names = tuple(str(item["name"]) for item in selected)
    if set(selected_names) != required_source_ids or len(selected_names) != len(
        required_source_ids
    ):
        raise AssertionError("canonical source registry changed after fixture coverage preflight")
    for item in selected:
        item["endpoint"] = f"{base_url}/harvest/{item['name']}"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump({"version": payload["version"], "sources": selected}, sort_keys=False),
        encoding="utf-8",
    )
    return selected_names


def _install_fixture_profiles(
    monkeypatch: MonkeyPatch, *, excluded_profile_input: bool = False
) -> SourceProfileRegistry:
    from polisyos.fabric.connectors.profiles.builtin_profiles import BUILTIN_PROFILES
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config

    builtins = {profile.profile_id: profile for profile in BUILTIN_PROFILES}
    registry = SourceProfileRegistry()
    for profile_id in PROFILE_IDS:
        builtin = builtins.get(profile_id)
        if builtin is None:
            raise AssertionError(f"missing builtin source profile {profile_id}")
        headers = (
            {"X-PolicyOS-Fixture": "present-at-publish"}
            if excluded_profile_input and profile_id == "worldbank_wdi"
            else {}
        )
        profile = builtin.model_copy(update={"headers": headers}, deep=True)
        connection = resolve_connection_config(profile)
        if connection.auth_method or connection.auth_credentials:
            raise AssertionError(f"fixture source profile is not auth-free: {profile_id}")
        if profile_id == "worldbank_wdi" and excluded_profile_input:
            if connection.headers != headers:
                raise AssertionError("publish-time worldbank fixture header was not retained")
        elif connection.headers:
            raise AssertionError(f"fixture source profile has unexpected headers: {profile_id}")
        registry.register(profile)
    monkeypatch.setattr(SourceProfileRegistry, "_instance", registry)
    if tuple(profile.profile_id for profile in registry.list_all()) != tuple(sorted(PROFILE_IDS)):
        raise AssertionError("fixture profile selection differs from the frozen profile inventory")
    return registry


def _patch_connector_edges(monkeypatch: MonkeyPatch) -> None:
    import pandas as pd

    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest
    from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot
    from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
    from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
    from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
    from polisyos.fabric.connectors.sources.unpd import UNPDConnector
    from polisyos.fabric.connectors.sources.who import WHOConnector
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

    def _rows(
        country_column: str, time_column: str, *, iso3: bool = False
    ) -> list[dict[str, object]]:
        output = []
        for iso2, iso3_code in _COUNTRIES:
            country = iso3_code if iso3 else iso2
            for year in range(2018, 2023):
                output.append(
                    {
                        country_column: country,
                        time_column: str(year),
                        "value": float(20 + year - 2018 + len(iso2)),
                    }
                )
        return output

    async def _describe(
        self: object, _handle: object, dataset_id: str
    ) -> DatasetCapabilitySnapshot:
        return DatasetCapabilitySnapshot(
            source=str(getattr(self, "namespace", "fixture-source")),
            dataset_id=str(dataset_id),
            resolved_dataset_id=str(dataset_id),
            preferred_transport="fixture-external-fetch-edge",
            last_checked_at=datetime.now(UTC),
        )

    async def _worldbank_fetch(self: object, _handle: object, _request: object) -> SimpleNamespace:
        return SimpleNamespace(data=pd.DataFrame(_rows("country_code", "year")))

    async def _eurostat_fetch(self: object, _handle: object, _request: object) -> SimpleNamespace:
        return SimpleNamespace(data=pd.DataFrame(_rows("geo", "time_period")))

    async def _sdmx_fetch(self: object, _handle: object, _request: object) -> SimpleNamespace:
        return SimpleNamespace(data=pd.DataFrame(_rows("REF_AREA", "TIME_PERIOD", iso3=True)))

    async def _who_fetch(self: object, _handle: object, _request: object) -> SimpleNamespace:
        return SimpleNamespace(data=pd.DataFrame(_rows("country_code", "year", iso3=True)))

    async def _unpd_fetch(self: object, _handle: object, _request: object) -> SimpleNamespace:
        return SimpleNamespace(data=pd.DataFrame(_rows("country_code", "year")))

    async def _uis_fetch(self: object, _handle: object, _request: object) -> SimpleNamespace:
        return SimpleNamespace(data=pd.DataFrame(_rows("country_code", "year")))

    connector_edges = (
        (WorldBankConnector, _worldbank_fetch),
        (EurostatConnector, _eurostat_fetch),
        (SDMXSourceConnector, _sdmx_fetch),
        (WHOConnector, _who_fetch),
        (UNPDConnector, _unpd_fetch),
        (UNESCOUISConnector, _uis_fetch),
    )
    for connector, fetch in connector_edges:
        monkeypatch.setattr(connector, "describe_dataset", _describe)
        monkeypatch.setattr(connector, "fetch", fetch)

    wvs_rows = [
        {
            "country_code": country,
            "survey_year": 2020,
            "wave": 7,
            "value": 0.6,
            "sample_size": 1200,
            "weighted_sample_size": 1200.0,
            "sample_weight_field": "S017",
            "aggregation_method": "weighted_share_response_1",
            "observation_grain": "country_survey_year_wave",
            "data_shape": "survey_repeated_cross_section",
        }
        for country, _iso3_code in _COUNTRIES
    ]
    monkeypatch.setattr(core_sources_ingest, "_load_wvs_bulk_rows", lambda *_a, **_k: wvs_rows)


def _record(
    *,
    base_url: str,
    record_id: str,
    source: str,
    dataset_id: str,
    title: str,
    metric: str | None,
    connector_id: str = "",
    profile_id: str = "",
    execution_tier: str = "catalog",
    coverage_countries: list[str] | None = None,
    time_start: str = "2018",
    time_end: str = "2022",
    keywords: list[str] | None = None,
) -> DatasetRecord:
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetAccess,
        DatasetCoverage,
        DatasetQuality,
        DatasetRecord,
        DistributionRecord,
    )

    distributions = []
    preferred_distribution_id = ""
    if connector_id:
        preferred_distribution_id = f"dist-{record_id}"
        distributions = [
            DistributionRecord(
                id=preferred_distribution_id,
                url=f"{base_url}/reach/{record_id}.csv",
                format="CSV",
                name=f"{title} machine-readable fixture distribution",
                connector_type=connector_id,
                source_locator=dataset_id,
                profile_id=profile_id,
                media_type="text/csv",
                machine_readable=True,
                parser_supported=True,
                quality_score=1.0,
            )
        ]
    return DatasetRecord(
        id=record_id,
        title=title,
        description=f"{title}; annual country observations and statistical data.",
        publisher="PolicyOS bounded fixture inputs",
        keywords=list(keywords or []),
        variables=[metric] if metric else [],
        formats=["CSV"] if distributions else [],
        distributions=distributions,
        polisyos_metrics=[metric] if metric else [],
        source_portal=source,
        source=source,
        dataset_id=dataset_id,
        source_dataset_id=dataset_id,
        execution_tier=execution_tier,
        update_frequency="annual",
        coverage=DatasetCoverage(
            countries=list(coverage_countries or ["UA", "DE", "PL", "RO", "MD"]),
            time_start=time_start,
            time_end=time_end,
            granularity="annual",
        ),
        access=DatasetAccess(access_type="open", auth_required=False),
        quality=DatasetQuality(
            description_score=0.95,
            machine_readable_score=1.0 if distributions else 0.0,
            parser_support_score=1.0 if distributions else 0.0,
            freshness_score=0.9,
            execution_readiness_score=0.95 if connector_id else 0.0,
        ),
        preferred_distribution_id=preferred_distribution_id,
    )


def _graph_records(base_url: str, registry_entries: list[dict[str, object]]) -> list[DatasetRecord]:
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetCoverage,
        DatasetRecord,
    )

    core_source_rows = (
        (
            "worldbank",
            "NY.GDP.PCAP.PP.CD",
            "GDP per capita purchasing power parity",
            "gdp_per_capita",
            "worldbank.wdi",
            "worldbank_wdi",
        ),
        ("wvs", "A165", "Social trust and values survey", "social_trust", "wvs.wave7", "wvs_wave7"),
        (
            "eurostat",
            "une_rt_a",
            "Annual unemployment rate",
            "unemployment_rate",
            "eurostat.data",
            "eurostat_public",
        ),
        (
            "oecd",
            "CPI_DATA",
            "Inflation and consumer prices index",
            "inflation",
            "sdmx.source",
            "oecd_sdmx",
        ),
        (
            "ilo",
            "EMP_DATA",
            "Labor force participation and employment",
            "labor_force_participation",
            "sdmx.source",
            "ilo_sdmx",
        ),
        (
            "who",
            "LE_001",
            "Health outcomes and life expectancy",
            "health_outcomes",
            "who.indicators",
            "who_gho",
        ),
        (
            "unpd",
            "POP_001",
            "International migration and population flows",
            "migration",
            "unpd.data",
            "unpd_dataportal",
        ),
        (
            "unesco_uis",
            "EDU_001",
            "Education outcomes and school enrollment",
            "education_outcomes",
            "unesco_uis.data",
            "unesco_uis_public",
        ),
    )
    records = [
        _record(
            base_url=base_url,
            record_id=f"fixture-{source}-{dataset_id.lower().replace('.', '-')}",
            source=source,
            dataset_id=dataset_id,
            title=title,
            metric=metric,
            connector_id=connector_id,
            profile_id=profile_id,
            execution_tier="transport_ready",
            keywords=[metric.replace("_", " "), title.lower()],
        )
        for source, dataset_id, title, metric, connector_id, profile_id in core_source_rows
    ]
    records.extend(
        [
            _record(
                base_url=base_url,
                record_id="fixture-benchmark-poverty",
                source="benchmark_fixture",
                dataset_id="fixture-poverty",
                title="Poverty rate income deprivation",
                metric="poverty_rate",
                connector_id="worldbank.wdi",
                profile_id="worldbank_wdi",
                execution_tier="fetchable",
                keywords=["poverty", "income", "deprivation"],
            ),
            _record(
                base_url=base_url,
                record_id="fixture-benchmark-institutional-quality",
                source="benchmark_fixture",
                dataset_id="fixture-institutional-quality",
                title="Institutional quality and rule of law",
                metric="institutional_quality",
                connector_id="worldbank.wdi",
                profile_id="worldbank_wdi",
                execution_tier="fetchable",
                keywords=["institutional quality", "rule of law", "state capacity"],
            ),
            _record(
                base_url=base_url,
                record_id="fixture-scope-dataset",
                source="worldbank",
                dataset_id="scope_dataset",
                title="Scoped public policy metric",
                metric="scope_metric",
                connector_id="worldbank.wdi",
                profile_id="worldbank_wdi",
                execution_tier="fetchable",
                coverage_countries=["DEU"],
                time_start="2020",
                time_end="2030",
                keywords=["scope metric", "fixture"],
            ),
        ]
    )

    entries = {str(item["name"]): item for item in registry_entries}
    for source, title, words in (
        (
            "data_gov_ua_broad",
            (
                "Public population migration employment health education and budget "
                "open data Ukraine"
            ),
            ["population", "migration", "employment", "health", "education", "budget", "poverty"],
        ),
        (
            "data_gov_ro_broad",
            (
                "Buget local municipal educatie sanatate somaj piata muncii migratie "
                "demografie Romania Ukraine regional comparator"
            ),
            [
                "buget",
                "educatie",
                "sanatate",
                "somaj",
                "muncii",
                "migration",
                "demografie",
                "Romania",
                "Ukraine",
                "regional",
                "comparator",
            ],
        ),
        (
            "data_gov_md_broad",
            (
                "Buget local municipal educatie sanatate somaj piata muncii migratie "
                "demografie Moldova regional comparator"
            ),
            [
                "buget",
                "educatie",
                "sanatate",
                "somaj",
                "muncii",
                "migration",
                "demografie",
                "Moldova",
                "regional",
                "comparator",
            ],
        ),
        (
            "data_gov_pl_broad",
            (
                "Budżet lokalny edukacja zdrowie bezrobocie rynek pracy migracja "
                "demografia Polska comparator regional"
            ),
            [
                "budżet",
                "edukacja",
                "zdrowie",
                "bezrobocie",
                "pracy",
                "migracja",
                "demografia",
                "Polska",
                "comparator",
                "regional",
            ],
        ),
    ):
        records.append(
            DatasetRecord(
                id=f"fixture-{source}",
                title=title,
                description=title,
                publisher="PolicyOS bounded fixture inputs",
                keywords=words,
                source=source,
                dataset_id=f"{source}-package",
                source_dataset_id=f"{source}-package",
                execution_tier="catalog",
                coverage=DatasetCoverage(
                    countries=["UA", "RO", "MD", "PL"],
                    time_start="2018",
                    time_end="2022",
                    granularity="annual",
                ),
            )
        )

    for source in BLOCKING_SOURCES[-4:]:
        spec = entries[source]
        country = source.removeprefix("data_gov_").removesuffix("_exec")
        profile = str(spec["profile_id"])
        connector = str(spec["connector_id"])
        keywords = {
            "ua": ["population", "migration", "employment", "health", "education", "budget"],
            "ro": ["buget", "educatie", "sanatate", "somaj", "migratie", "demografie"],
            "md": ["buget", "educatie", "sanatate", "somaj", "migratie", "demografie"],
            "pl": ["budżet", "edukacja", "zdrowie", "bezrobocie", "migracja", "demografia"],
        }[country]
        records.append(
            _record(
                base_url=base_url,
                record_id=f"fixture-{source}",
                source=source,
                dataset_id=f"{country}-fixture-public-services",
                title=f"{source} public service statistical data",
                metric=None,
                connector_id=connector,
                profile_id=profile,
                execution_tier="fetchable",
                keywords=keywords,
            )
        )
    return records


def build_published_catalog_fixture(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    excluded_profile_input: bool = False,
) -> PublishedFixture:
    """Run bounded real catalog producers over local deterministic fetch-edge inputs.

    The fixture includes all twelve default publish-blocking source identities and their
    four required seed parents. Its results establish only fixture-scoped producer
    currentness and consumer behavior; they are not empirical or production claims.
    """
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources_ingest import (
        run_core_sources_ingest,
    )
    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        _derive_catalog_readiness,
        current_catalog_report_basis,
        run_content_stage_with_receipt,
        run_dataset_pipeline_sync,
    )
    from polisyos.data_forge.domains.catalog.batch.source_registry import load_source_registry
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
    from polisyos.data_forge.domains.catalog.registry import default_catalog_source_registry_path
    from polisyos.data_forge.kernel.quality.qc import QCReport

    canonical_registry_path = default_catalog_source_registry_path()
    source_snapshot = _capture_fixture_source_registry(
        canonical_registry_path, tmp_path / "canonical-source-registry.snapshot.yaml"
    )
    required_source_ids = source_snapshot.required_source_ids

    server = _FixtureServer(("127.0.0.1", 0), _FixtureHandler)
    server_thread = threading.Thread(
        target=server.serve_forever, name="catalog-fixture-http", daemon=True
    )
    server_thread.start()
    address = server.server_address
    if not isinstance(address, tuple) or len(address) < 2:
        raise AssertionError(f"fixture server returned an invalid address: {address!r}")
    host, port = address[0], address[1]
    if not isinstance(host, str) or not isinstance(port, int):
        raise AssertionError(f"fixture server returned an invalid host/port: {address!r}")
    base_url = f"http://{host}:{port}"
    completed = False
    try:
        selected_names = _write_registry(tmp_path / "registry.yaml", base_url, source_snapshot)
        registry_payload = yaml.safe_load((tmp_path / "registry.yaml").read_text(encoding="utf-8"))
        registry_entries = registry_payload["sources"]
        selected_registry = load_source_registry(tmp_path / "registry.yaml")
        selected = selected_registry.enabled_sources(run_profile="prod_full")
        if {item.name for item in selected} != required_source_ids:
            raise AssertionError("producer selection changed the owner-derived source set")

        profile_registry = _install_fixture_profiles(
            monkeypatch, excluded_profile_input=excluded_profile_input
        )
        _patch_connector_edges(monkeypatch)
        config = DatasetBatchConfig(
            snapshot_root=tmp_path / "snapshot",
            registry_path=tmp_path / "registry.yaml",
            stages=frozenset({"harvest"}),
            run_profile="prod_full",
            observation_mode="core",
            preflight_sources=CORE_SOURCES,
            fail_fast_qc=False,
            harvest_timeout=5,
        )
        harvest_stats = run_dataset_pipeline_sync(config)
        from polisyos.data_forge.domains.catalog.batch.pipeline import _harvest_stage_receipt

        harvest_receipt = _harvest_stage_receipt(config)
        if harvest_receipt is None:
            raise AssertionError(f"native harvest receipt is not current: {harvest_stats.metrics}")
        receipt_sources, source_outcomes, _harvest_artifacts = harvest_receipt
        if set(receipt_sources) != required_source_ids:
            raise AssertionError("native harvest receipt lost an owner-required source")
        missing_raw = sorted(
            source for source, outcome in source_outcomes.items() if _records_fetched(outcome) <= 0
        )
        if missing_raw:
            raise AssertionError(
                f"selected fixture harvest sources returned no raw rows: {missing_raw}"
            )

        graph_stats = build_graph(
            records=iter(_graph_records(base_url, registry_entries)),
            db_path=config.db_path,
        )
        if graph_stats.datasets < 19 or graph_stats.metric_bindings < 11:
            raise AssertionError(
                f"graph producer returned incomplete fixture artifacts: {graph_stats}"
            )

        core_stats = run_core_sources_ingest(config)
        if core_stats.failures or core_stats.failed_shards or core_stats.deferred_shards:
            raise AssertionError(
                f"core producer did not complete its selected fixture work: {core_stats}"
            )
        run_content_stage_with_receipt(config, "benchmark")
        qc_result = run_content_stage_with_receipt(config, "qc")
        if not isinstance(qc_result, QCReport):
            raise AssertionError(f"QC producer returned an unexpected result: {qc_result!r}")
        qc_report = qc_result
        report_basis = current_catalog_report_basis(config)
        if report_basis.get("state") != "current":
            if not excluded_profile_input:
                raise AssertionError(
                    f"native benchmark/QC report basis is not current: {report_basis}"
                )
            if (
                report_basis.get("state") != "not_established"
                or report_basis.get("reason") != "profile_private_inputs_unversioned"
            ):
                raise AssertionError(
                    f"excluded fixture input produced an unexpected basis: {report_basis}"
                )
            if not qc_report.passed:
                failed = [
                    item.name
                    for item in qc_report.checks
                    if not item.passed and item.severity == "critical"
                ]
                raise AssertionError(f"native QC producer failed critical checks: {failed}")
            try:
                run_content_stage_with_receipt(config, "publish")
            except RuntimeError as exc:
                publish_blocked_reason = str(exc)
            else:
                raise AssertionError("publisher admitted an unversioned private profile input")
            expected_error = (
                "Dataset publish blocked: benchmark/QC report basis not_established "
                "(profile_private_inputs_unversioned)"
            )
            if publish_blocked_reason != expected_error:
                raise AssertionError(
                    f"publisher refused for an unexpected reason: {publish_blocked_reason}"
                )
            if config.consumer_readiness_path.exists() or config.publish_manifest_path.exists():
                raise AssertionError("blocked publisher wrote readiness or publish output")
            from polisyos.data_forge.domains.catalog.batch.pipeline import (
                current_catalog_publish_receipt,
            )

            publish_receipt = current_catalog_publish_receipt(
                config.db_path, run_profile="prod_full"
            )
            if (
                publish_receipt.get("state") != "not_established"
                or publish_receipt.get("reason") != "publish_lineage_absent"
            ):
                raise AssertionError(
                    f"blocked publish lineage returned unexpected currentness: {publish_receipt}"
                )
            graph = DatasetCatalogGraph(config.db_path, config.index_dir)
            completed = True
            return PublishedFixture(
                snapshot_root=config.snapshot_root,
                database_path=config.db_path,
                producer_graph=graph,
                profile_registry=profile_registry,
                readiness={},
                evaluation_mode="not-established",
                selected_source_ids=tuple(selected_names),
                source_registry_sha256=source_snapshot.source_sha256,
                profile_ids=tuple(profile.profile_id for profile in profile_registry.list_all()),
                table_counts={},
                report_basis_state=str(report_basis.get("state")),
                report_basis_reason=str(report_basis.get("reason")),
                publish_blocked_reason=publish_blocked_reason,
                publish_receipt_state=str(publish_receipt.get("state")),
                publish_receipt_reason=str(publish_receipt.get("reason")),
                http_server=server,
                http_server_thread=server_thread,
            )
        derived = _derive_catalog_readiness(config, report_basis)
        raw_readiness = derived.get("readiness")
        if not isinstance(raw_readiness, dict):
            raise AssertionError("owner readiness output is not a mapping")
        readiness: dict[str, bool] = {}
        for key, value in raw_readiness.items():
            if not isinstance(key, str) or not isinstance(value, bool):
                raise AssertionError("owner readiness output contains an invalid key/value")
            readiness[key] = value
        expected_keys = {
            "qc_ready",
            "benchmark_ready",
            "search_ready",
            "fetchability_ready",
            "transportability_ready",
            "foundry_ready",
            "source_preflight_ready",
            "evaluation_ready",
            "equivalence_ready",
            "consumer_ready",
            "full_publish_ready",
        }
        if set(readiness) != expected_keys:
            raise AssertionError(f"owner readiness denominator changed: {sorted(readiness)}")
        benchmark = report_basis["benchmark_payload"]
        if not isinstance(benchmark, dict):
            raise AssertionError("native benchmark report is unavailable")
        evaluation_mode = str(benchmark.get("evaluation_mode") or "")
        if not qc_report.passed:
            critical = [
                item.name
                for item in qc_report.checks
                if not item.passed and item.severity == "critical"
            ]
            raise AssertionError(f"native QC producer failed critical checks: {critical}")
        if not readiness["consumer_ready"]:
            failed = sorted(key for key, passed in readiness.items() if not passed)
            raise AssertionError(
                f"actual producer basis did not admit consumer readiness ({failed}); "
                f"evaluation_mode={evaluation_mode}; metrics={benchmark.get('metrics')}"
            )
        if evaluation_mode not in {"core-ready", "full-ready"}:
            raise AssertionError(f"fixture has no current observation readiness: {evaluation_mode}")

        run_content_stage_with_receipt(config, "publish")
        published_readiness = json.loads(config.consumer_readiness_path.read_text(encoding="utf-8"))
        if published_readiness.get("readiness") != readiness:
            raise AssertionError("publish receipt diverged from recomputed owner readiness")
        if published_readiness.get("publish_mode") not in {"core-ready", "full-ready"}:
            raise AssertionError(
                f"producer did not publish a current fixture catalog: {published_readiness}"
            )
        from polisyos.data_forge.domains.catalog.batch.pipeline import (
            current_catalog_publish_receipt,
        )

        publish_receipt = current_catalog_publish_receipt(config.db_path, run_profile="prod_full")
        if publish_receipt.get("state") != "current":
            raise AssertionError(
                f"published catalog receipt did not recompute current: {publish_receipt}"
            )
        graph = DatasetCatalogGraph(config.db_path, config.index_dir)
        completed = True
        return PublishedFixture(
            snapshot_root=config.snapshot_root,
            database_path=config.db_path,
            producer_graph=graph,
            profile_registry=profile_registry,
            readiness=dict(readiness),
            evaluation_mode=evaluation_mode,
            selected_source_ids=tuple(selected_names),
            source_registry_sha256=source_snapshot.source_sha256,
            profile_ids=tuple(profile.profile_id for profile in profile_registry.list_all()),
            table_counts=dict(published_readiness["table_counts"]),
            report_basis_state=str(report_basis.get("state")),
            report_basis_reason=(
                str(report_basis["reason"]) if report_basis.get("reason") is not None else None
            ),
            publish_blocked_reason=None,
            publish_receipt_state=str(publish_receipt.get("state")),
            publish_receipt_reason=(
                str(publish_receipt["reason"])
                if publish_receipt.get("reason") is not None
                else None
            ),
            http_server=server,
            http_server_thread=server_thread,
        )
    finally:
        if not completed:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)
