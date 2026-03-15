from __future__ import annotations

import json
import os
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

_UNPD_FIELDS = (
    "indicator_id",
    "country_code",
    "location_id",
    "year",
    "value",
    "variant_id",
    "sex_id",
    "age_id",
    "category_id",
    "dimensions_json",
)


class UNPDConnector(HTTPConnectorBase[pd.DataFrame]):
    """Production connector for UN Population Division data portal."""

    namespace: ClassVar[str] = "unpd"
    short_id: ClassVar[str] = "data"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://population.un.org/dataportalapi/api/v1"
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(base_delay=1.8)

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
        source_name="UN Population Division Data Portal",
        source_organization="United Nations Population Division",
        source_url="https://population.un.org/dataportal/",
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
        url = f"{self._base_url(handle)}/indicators/"
        started = time.monotonic()
        try:
            _body, _headers, _raw = await self._resilient_request_json(
                handle,
                url,
                params={"pageSize": "1"},
            )
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
        url = f"{self._base_url(handle)}/indicators/"
        page_size = max(1, safe_int(handle.config.headers.get("X-UNPD-CATALOG-LIMIT")) or 200)
        body, _headers, _raw = await self._resilient_request_json(
            handle,
            url,
            params={"pageSize": str(page_size)},
        )
        rows = body.get("data", []) if isinstance(body, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            dataset_id = str(row.get("id") or "").strip()
            if not dataset_id:
                continue
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=str(row.get("name") or row.get("shortName") or dataset_id),
                description=str(row.get("description") or ""),
                tags=("unpd", "demography", "population"),
                metadata={
                    "source_name": row.get("sourceName"),
                    "source_year": row.get("sourceYear"),
                    "variable_type": row.get("variableType"),
                    "value_type": row.get("valueType"),
                },
                schema_id="unpd.data.generic",
                supports_filters=("country", "location_id", "year"),
            )

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        indicator_id = request.dataset_id
        location_ids = self._location_ids(request)
        if not location_ids:
            raise FetchError(
                message="UNPD fetch requires a country or location_id filter",
                connector_id=self.connector_id,
                dataset_id=indicator_id,
            )
        start_year, end_year = self._year_bounds(request)
        if start_year is None or end_year is None:
            raise FetchError(
                message="UNPD fetch requires date_start/date_end or year filters",
                connector_id=self.connector_id,
                dataset_id=indicator_id,
            )

        auth_headers = self._auth_headers(handle)
        payload_chunks: list[bytes] = []
        rows: list[dict[str, Any]] = []
        bytes_transferred = 0
        started = time.monotonic()

        for location_id in location_ids:
            url = (
                f"{self._base_url(handle)}/data/indicators/{indicator_id}"
                f"/locations/{location_id}/start/{int(start_year)}/end/{int(end_year)}"
            )
            body, headers, raw = await self._resilient_request_json(
                handle,
                url,
                params={},
                headers=auth_headers,
            )
            payload_chunks.append(raw)
            bytes_transferred += len(raw)
            rows.extend(self._extract_rows(body, indicator_id=indicator_id, location_id=location_id))

        frame = pd.DataFrame(rows, columns=_UNPD_FIELDS) if rows else pd.DataFrame(columns=_UNPD_FIELDS)
        now = datetime.now(timezone.utc)
        last_headers = headers if "headers" in locals() else {}
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id="unpd.data.generic",
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
            "schema_id": "unpd.data.generic",
            "version": "1.0.0",
            "fields": list(_UNPD_FIELDS),
            "time_dimension": "year",
            "geo_dimension": "country_code",
        }

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
    def _location_ids(request: FetchRequest) -> list[str]:
        filter_map = {key: list(values) for key, values in request.filters}
        explicit = [str(value).strip() for value in filter_map.get("location_id", []) if str(value).strip()]
        if explicit:
            return sorted(set(explicit))
        countries = [str(value).strip() for value in filter_map.get("country", []) + filter_map.get("geo", []) if str(value).strip()]
        mapped = [UNPDConnector._country_to_numeric(value) for value in countries]
        return sorted({value for value in mapped if value})

    @staticmethod
    def _country_to_numeric(country_code: str) -> str:
        normalized = str(country_code or "").strip().upper()
        iso_map = {
            "UA": "804",
            "UKR": "804",
            "DE": "276",
            "DEU": "276",
            "PL": "616",
            "POL": "616",
            "US": "840",
            "USA": "840",
        }
        return iso_map.get(normalized, normalized)

    @staticmethod
    def _auth_headers(handle: ConnectionHandle) -> dict[str, str]:
        token = str(handle.config.auth_credentials.get("token") or "").strip()
        if not token:
            token = os.getenv("POLISYOS_UNPD_API_TOKEN", "").strip()
        if not token:
            raise FetchError(
                message="UNPD API token is required (set POLISYOS_UNPD_API_TOKEN or auth_credentials.token)",
                connector_id=UNPDConnector.connector_id,
            )
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _extract_rows(body: Any, *, indicator_id: str, location_id: str) -> list[dict[str, Any]]:
        records = body.get("data", []) if isinstance(body, dict) else []
        if not isinstance(records, list):
            records = []

        rows: list[dict[str, Any]] = []
        for row in records:
            if not isinstance(row, dict):
                continue
            dimensions = {
                key: row.get(key)
                for key in ("variantId", "sexId", "ageId", "categoryId")
                if row.get(key) not in (None, "")
            }
            value = safe_float(row.get("value"))
            rows.append(
                {
                    "indicator_id": str(row.get("indicatorId") or indicator_id),
                    "country_code": str(row.get("iso3Code") or row.get("locationCode") or "").strip().upper(),
                    "location_id": str(row.get("locationId") or location_id),
                    "year": safe_int(row.get("timeLabel") or row.get("timeId") or row.get("year")),
                    "value": value,
                    "variant_id": safe_int(row.get("variantId")),
                    "sex_id": safe_int(row.get("sexId")),
                    "age_id": safe_int(row.get("ageId")),
                    "category_id": safe_int(row.get("categoryId")),
                    "dimensions_json": json.dumps(dimensions, sort_keys=True, separators=(",", ":")),
                }
            )
        return rows


__all__ = ["UNPDConnector"]
