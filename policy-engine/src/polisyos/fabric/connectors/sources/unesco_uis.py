"""Public sources unesco uis module API."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import streaming_hash
from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, FetchResult, HealthStatus
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
from polisyos.fabric.connectors.sources.http_common import frame_completeness, safe_float, safe_int
from polisyos.fabric.connectors.types import DatasetDescriptor, FetchError
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)

_UIS_FIELDS = (
    "indicator_id",
    "country_code",
    "year",
    "value",
    "magnitude",
    "qualifier",
)


class UNESCOUISConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for UNESCO UIS public education and science indicators.

    Fetches public UIS indicator payloads with limited parallel country fan-out
    and optional bulk-oriented profile settings for backfill work.

    Data source:
        https://api.uis.unesco.org
    Protocol:
        REST JSON
    Auth:
        None
    Async support:
        Standard async HTTP execution only
    Profile:
        ``unesco_uis_public``
    """

    namespace: ClassVar[str] = "unesco_uis"
    short_id: ClassVar[str] = "data"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://api.uis.unesco.org/api/public"
    _PARALLEL_COUNTRY_LIMIT: ClassVar[int] = 4
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(base_delay=1.4)

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.DIMENSION_FILTER
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="UNESCO Institute for Statistics",
        source_organization="UNESCO Institute for Statistics",
        source_url="https://api.uis.unesco.org",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        url = f"{self._base_url(handle)}/definitions/indicators"
        started = time.monotonic()
        try:
            _body, _headers, _raw = await self._resilient_request_json(handle, url, params={})
            return HealthStatus(
                healthy=True,
                message="HTTP 200",
                latency_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            message = f"HTTP {status_code}" if status_code is not None else str(exc)
            return HealthStatus(
                healthy=False,
                message=message,
                latency_ms=self._elapsed_ms(started),
            )

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        url = f"{self._base_url(handle)}/definitions/indicators"
        limit = max(1, safe_int(handle.config.headers.get("X-UIS-CATALOG-LIMIT")) or 200)
        body, _headers, _raw = await self._resilient_request_json(handle, url, params={})
        rows = body if isinstance(body, list) else []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            dataset_id = str(row.get("indicatorCode") or "").strip()
            if not dataset_id:
                continue
            timeline = row.get("dataAvailability", {}).get("timeLine", {}) if isinstance(row.get("dataAvailability"), dict) else {}
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=str(row.get("name") or dataset_id),
                description=f"UIS indicator in theme {row.get('theme') or 'unknown'}",
                tags=("unesco_uis", "education", "statistics"),
                metadata={"theme": row.get("theme")},
                schema_id="unesco_uis.data.generic",
                supports_filters=("country", "year"),
                date_start=_year_to_datetime(timeline.get("min")),
                date_end=_year_to_datetime(timeline.get("max")),
            )

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        indicator_id = request.dataset_id
        countries = self._countries(request)
        start_year, end_year = self._year_bounds(request)
        params = {
            "indicator": indicator_id,
        }
        if start_year is not None:
            params["start"] = str(start_year)
        if end_year is not None:
            params["end"] = str(end_year)

        rows: list[dict[str, Any]] = []
        payload_chunks: list[bytes] = []
        bytes_transferred = 0
        started = time.monotonic()
        last_headers: dict[str, str] = {}

        request_countries = countries or [""]
        semaphore = asyncio.Semaphore(
            max(1, min(self._PARALLEL_COUNTRY_LIMIT, len(request_countries)))
        )

        async def _fetch_country(country: str) -> tuple[Any, dict[str, str], bytes]:
            request_params = dict(params)
            if country:
                request_params["geoUnit"] = country
            async with semaphore:
                body, headers, raw = await self._resilient_request_json(
                    handle,
                    f"{self._base_url(handle)}/data/indicators",
                    params=request_params,
                )
            return body, headers, raw

        for body, headers, raw in await asyncio.gather(
            *(_fetch_country(country) for country in request_countries)
        ):
            last_headers = headers
            payload_chunks.append(raw)
            bytes_transferred += len(raw)
            rows.extend(self._extract_rows(body, indicator_id=indicator_id))

        frame = pd.DataFrame(rows, columns=_UIS_FIELDS) if rows else pd.DataFrame(columns=_UIS_FIELDS)
        now = datetime.now(timezone.utc)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id="unesco_uis.data.generic",
            schema_version="1.0.0",
            quality_tier=QualityTier.SILVER,
            bytes_transferred=bytes_transferred,
            completeness=frame_completeness(frame),
            fetched_at=now,
            fetch_duration_ms=self._elapsed_ms(started),
            content_hash=streaming_hash(payload_chunks, prefix=True),
            etag=last_headers.get("ETag"),
            last_modified=last_headers.get("Last-Modified"),
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        del handle, dataset_id
        return {
            "schema_id": "unesco_uis.data.generic",
            "version": "1.0.0",
            "fields": list(_UIS_FIELDS),
            "time_dimension": "year",
            "geo_dimension": "country_code",
        }

    @staticmethod
    def _countries(request: FetchRequest) -> list[str]:
        filter_map = {key: list(values) for key, values in request.filters}
        countries = [
            UNESCOUISConnector._to_iso3(value)
            for key in ("country", "geo", "geoUnit")
            for value in filter_map.get(key, [])
            if value
        ]
        return sorted({value for value in countries if value})

    @staticmethod
    def _year_bounds(request: FetchRequest) -> tuple[int | None, int | None]:
        if request.date_start is not None or request.date_end is not None:
            start = request.date_start.year if request.date_start is not None else None
            end = request.date_end.year if request.date_end is not None else start
            return start, end
        filter_map = {key: list(values) for key, values in request.filters}
        years = [safe_int(value) for value in filter_map.get("year", [])]
        years = [value for value in years if value is not None]
        if not years:
            return None, None
        return min(years), max(years)

    @staticmethod
    def _extract_rows(body: Any, *, indicator_id: str) -> list[dict[str, Any]]:
        records = body.get("records", []) if isinstance(body, dict) else []
        if not isinstance(records, list):
            records = []

        rows: list[dict[str, Any]] = []
        for row in records:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "indicator_id": str(row.get("indicatorId") or indicator_id),
                    "country_code": str(row.get("geoUnit") or "").strip().upper(),
                    "year": safe_int(row.get("year")),
                    "value": safe_float(row.get("value")),
                    "magnitude": row.get("magnitude"),
                    "qualifier": row.get("qualifier"),
                }
            )
        return rows

    @staticmethod
    def _to_iso3(value: str) -> str:
        normalized = str(value or "").strip().upper()
        iso_map = {
            "UA": "UKR",
            "UKR": "UKR",
            "DE": "DEU",
            "DEU": "DEU",
            "PL": "POL",
            "POL": "POL",
            "US": "USA",
            "USA": "USA",
        }
        return iso_map.get(normalized, normalized)


def _year_to_datetime(value: Any) -> datetime | None:
    year = safe_int(value)
    if year is None:
        return None
    return datetime(year, 1, 1, tzinfo=timezone.utc)


__all__ = ["UNESCOUISConnector"]
