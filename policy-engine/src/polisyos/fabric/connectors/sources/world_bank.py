from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import streaming_hash
from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, FetchResult, HealthStatus
from polisyos.fabric.connectors.sources._contracts.world_bank_contracts import WDI_GENERIC_SCHEMA
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
from polisyos.fabric.connectors.sources.http_common import (
    frame_completeness,
    retry_after_seconds,
    safe_float,
    safe_int,
)
from polisyos.fabric.connectors.types import DatasetDescriptor, FetchError
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class WorldBankConnector(HTTPConnectorBase[pd.DataFrame]):
    """Production connector for World Bank Indicators API v2."""

    namespace: ClassVar[str] = "worldbank"
    short_id: ClassVar[str] = "wdi"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://api.worldbank.org/v2"
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(base_delay=1.0)

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
        source_name="World Development Indicators",
        source_organization="The World Bank Group",
        source_url=_BASE_URL,
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.GOLD,
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
        base_url = self._base_url(handle)
        url = f"{base_url}/country/US/indicator/NY.GDP.MKTP.CD"
        params = {"format": "json", "per_page": "1"}
        started = time.monotonic()
        try:
            _body, headers, _raw = await self._resilient_request_json(
                handle,
                url,
                params=params,
            )
            return HealthStatus(
                healthy=True,
                message="HTTP 200",
                latency_ms=self._elapsed_ms(started),
                rate_limit_remaining=safe_int(headers.get("X-RateLimit-Remaining")),
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            message = f"HTTP {status_code}" if status_code is not None else str(exc)
            return HealthStatus(
                healthy=False,
                message=message,
                latency_ms=self._elapsed_ms(started),
            )

    async def list_datasets(
        self,
        handle: ConnectionHandle,
    ) -> AsyncIterator[DatasetDescriptor]:
        base_url = self._base_url(handle)
        url = f"{base_url}/indicator"
        params = {"format": "json", "per_page": "200", "page": "1"}
        body, _headers, _raw = await self._resilient_request_json(
            handle,
            url,
            params=params,
        )
        records = body[1] if isinstance(body, list) and len(body) > 1 else []
        for row in records:
            if not isinstance(row, dict):
                continue
            dataset_id = str(row.get("id") or "").strip()
            if not dataset_id:
                continue
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=str(row.get("name") or dataset_id),
                description=str(row.get("sourceNote") or ""),
                tags=("worldbank", "wdi"),
                metadata={
                    "source_organization": row.get("sourceOrganization"),
                    "unit": row.get("unit"),
                },
            )

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base_url = self._base_url(handle)
        indicator_id = request.dataset_id
        countries = self._parse_countries(request)
        date_range = self._parse_date_range(request)
        started = time.monotonic()

        payload_chunks: list[bytes] = []
        all_records: list[dict[str, Any]] = []
        bytes_transferred = 0
        pages = 1
        page = 1

        etag: str | None = None
        last_modified: str | None = None
        etag_conflict = False
        last_modified_conflict = False

        while page <= pages:
            url = f"{base_url}/country/{countries}/indicator/{indicator_id}"
            params: dict[str, str] = {"format": "json", "per_page": "1000", "page": str(page)}
            if date_range:
                params["date"] = date_range

            body, headers, raw = await self._resilient_request_json(
                handle,
                url,
                params=params,
            )
            payload_chunks.append(raw)
            bytes_transferred += len(raw)

            etag, etag_conflict = _update_header_consensus(
                current=etag,
                conflicted=etag_conflict,
                candidate=headers.get("ETag"),
            )
            last_modified, last_modified_conflict = _update_header_consensus(
                current=last_modified,
                conflicted=last_modified_conflict,
                candidate=headers.get("Last-Modified"),
            )

            if not isinstance(body, list) or len(body) < 2:
                raise FetchError(
                    message=f"Unexpected response format for indicator {indicator_id}",
                    connector_id=self.connector_id,
                    dataset_id=indicator_id,
                )

            meta = body[0] if isinstance(body[0], dict) else {}
            rows = body[1] if isinstance(body[1], list) else []
            pages = max(1, safe_int(meta.get("pages")) or 1)
            for row in rows:
                if isinstance(row, dict):
                    all_records.append(row)
            page += 1

        frame = self._normalize_records(all_records, indicator_id)
        now = datetime.now(timezone.utc)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id=WDI_GENERIC_SCHEMA.schema_id,
            schema_version=str(WDI_GENERIC_SCHEMA.version),
            quality_tier=QualityTier.GOLD,
            bytes_transferred=bytes_transferred,
            completeness=frame_completeness(frame),
            fetched_at=now,
            fetch_duration_ms=self._elapsed_ms(started),
            content_hash=streaming_hash(payload_chunks, prefix=True),
            etag=etag if not etag_conflict else None,
            last_modified=last_modified if not last_modified_conflict else None,
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        del handle, dataset_id
        return WDI_GENERIC_SCHEMA.model_dump(mode="python")

    @staticmethod
    def _parse_countries(request: FetchRequest) -> str:
        filters = {key: list(values) for key, values in request.filters}
        countries = filters.get("country")
        if not countries:
            return "all"
        return ";".join(sorted({value for value in countries if value}))

    @staticmethod
    def _parse_date_range(request: FetchRequest) -> str | None:
        if request.date_start is not None and request.date_end is not None:
            return f"{request.date_start.year}:{request.date_end.year}"

        filters = {key: list(values) for key, values in request.filters}
        date_values = filters.get("date")
        if not date_values:
            return None
        return date_values[0]

    @staticmethod
    def _normalize_records(records: list[dict[str, Any]], indicator_id: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for row in records:
            country_info = row.get("country")
            if not isinstance(country_info, dict):
                country_info = {}
            indicator_info = row.get("indicator")
            if not isinstance(indicator_info, dict):
                indicator_info = {}

            rows.append(
                {
                    "country_code": row.get("countryiso3code") or country_info.get("id"),
                    "country_name": country_info.get("value"),
                    "indicator_id": indicator_info.get("id") or indicator_id,
                    "indicator_name": indicator_info.get("value"),
                    "year": safe_int(row.get("date")),
                    "value": safe_float(row.get("value")),
                    "unit": row.get("unit"),
                    "decimal": safe_int(row.get("decimal")),
                }
            )

        frame = pd.DataFrame(rows, columns=WDI_GENERIC_SCHEMA.field_names())
        if frame.empty:
            return pd.DataFrame(columns=WDI_GENERIC_SCHEMA.field_names())
        return frame


def _update_header_consensus(
    *,
    current: str | None,
    conflicted: bool,
    candidate: str | None,
) -> tuple[str | None, bool]:
    if conflicted:
        return None, True
    if candidate is None:
        return current, False
    if current is None:
        return candidate, False
    if current == candidate:
        return current, False
    return None, True


_retry_after_seconds = retry_after_seconds

__all__ = ["WorldBankConnector", "_retry_after_seconds"]
