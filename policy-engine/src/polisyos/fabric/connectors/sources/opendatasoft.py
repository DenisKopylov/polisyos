"""
OpendatasoftConnector — Opendatasoft Explore API v2.1 connector.

Two data paths controlled by X-ODS-ExportMode header:
- "records" (default): /api/explore/v2.1/catalog/datasets/{id}/records
  Bounded, supports ODSQL where/select/limit/offset.
- "exports": /api/explore/v2.1/catalog/datasets/{id}/exports/json
  Full dump, unbounded.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.sources.http_base import (
    HTTPConnectorBase,
    HTTPResilienceProfile,
)
from polisyos.fabric.connectors.sources.http_common import frame_completeness
from polisyos.fabric.connectors.types import (
    DatasetDescriptor,
    FetchError,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class OpendatasoftConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for Opendatasoft Explore API datasets.

    Retrieves tabular datasets from Opendatasoft hubs with profile-driven
    authentication and filter normalization.

    Data source:
        Opendatasoft portals
    Protocol:
        Explore API v2.1 / REST JSON
    Auth:
        API key or none, depending on profile
    Async support:
        Standard async HTTP execution only
    Profile:
        Any ``connector_family='opendatasoft'`` profile
    """

    namespace: ClassVar[str] = "opendatasoft"
    short_id: ClassVar[str] = "ods"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = ""

    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(
        base_delay=1.0,
        rate_limit_rps=5.0,
    )

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.FULL_FETCH
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.DIMENSION_FILTER
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="Opendatasoft",
        source_organization="Various Opendatasoft portals",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _export_mode(config: ConnectionConfig) -> str:
        return config.headers.get("X-ODS-ExportMode", "records")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        base = self._base_url(handle)
        url = f"{base}/api/explore/v2.1/catalog/datasets"
        params = {"limit": "1"}
        started = time.monotonic()
        try:
            _body, _headers, _raw = await self._resilient_request_json(
                handle, url, params=params,
            )
            return HealthStatus(
                healthy=True, message="HTTP 200",
                latency_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            return HealthStatus(
                healthy=False, message=str(exc),
                latency_ms=self._elapsed_ms(started),
            )

    # ------------------------------------------------------------------
    # Catalog browse
    # ------------------------------------------------------------------

    async def list_datasets(
        self,
        handle: ConnectionHandle,
    ) -> AsyncIterator[DatasetDescriptor]:
        base = self._base_url(handle)
        url = f"{base}/api/explore/v2.1/catalog/datasets"
        offset = 0
        limit = 100

        while True:
            params = {"limit": str(limit), "offset": str(offset)}
            body, _headers, _raw = await self._resilient_request_json(
                handle, url, params=params,
            )
            results = body.get("results", [])
            for ds in results:
                metas = ds.get("metas", ds.get("dataset", {}))
                default = metas.get("default", metas)
                dataset_id = ds.get("dataset_id") or ds.get("datasetid", "unknown")
                title = default.get("title") or dataset_id
                description = default.get("description") or ""
                yield DatasetDescriptor(
                    dataset_id=str(dataset_id),
                    name=str(title),
                    description=str(description)[:500],
                    tags=("opendatasoft",),
                )
            if len(results) < limit:
                break
            offset += limit

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        mode = self._export_mode(handle.config)
        if mode == "exports":
            return await self._fetch_exports(handle, request)
        return await self._fetch_records(handle, request)

    async def _fetch_records(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base = self._base_url(handle)
        url = f"{base}/api/explore/v2.1/catalog/datasets/{request.dataset_id}/records"

        started = time.monotonic()
        all_records: list[dict[str, Any]] = []
        total_bytes = 0
        all_raw: list[bytes] = []
        last_headers: dict[str, str] = {}
        offset = 0
        limit = 100

        where = self._build_where(request)
        while True:
            params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
            if where:
                params["where"] = where
            body, headers, raw = await self._resilient_request_json(
                handle, url, params=params,
            )
            last_headers = headers
            all_raw.append(raw)
            total_bytes += len(raw)

            results = body.get("results", [])
            for rec in results:
                record = rec.get("record", rec)
                fields = record.get("fields", record)
                all_records.append(fields)
            if len(results) < limit:
                break
            offset += limit

        duration_ms = self._elapsed_ms(started)
        df = pd.DataFrame(all_records) if all_records else pd.DataFrame()
        chash = compute_content_hash(b"".join(all_raw), prefix=True)

        return self._build_fetch_result(
            data=df,
            row_count=len(df),
            schema_id=f"{self.connector_id}.{request.dataset_id}",
            schema_version="1.0.0",
            quality_tier=QualityTier.SILVER,
            bytes_transferred=total_bytes,
            completeness=frame_completeness(df) if not df.empty else 1.0,
            fetched_at=datetime.now(timezone.utc),
            fetch_duration_ms=duration_ms,
            content_hash=chash,
            etag=last_headers.get("ETag"),
            last_modified=last_headers.get("Last-Modified"),
        )

    async def _fetch_exports(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base = self._base_url(handle)
        url = f"{base}/api/explore/v2.1/catalog/datasets/{request.dataset_id}/exports/json"

        started = time.monotonic()
        body, headers, raw = await self._resilient_request_json(
            handle, url, params={},
        )
        duration_ms = self._elapsed_ms(started)

        records = body if isinstance(body, list) else []
        df = pd.DataFrame(records) if records else pd.DataFrame()
        chash = compute_content_hash(raw, prefix=True)

        return self._build_fetch_result(
            data=df,
            row_count=len(df),
            schema_id=f"{self.connector_id}.{request.dataset_id}",
            schema_version="1.0.0",
            quality_tier=QualityTier.SILVER,
            bytes_transferred=len(raw),
            completeness=frame_completeness(df) if not df.empty else 1.0,
            fetched_at=datetime.now(timezone.utc),
            fetch_duration_ms=duration_ms,
            content_hash=chash,
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        base = self._base_url(handle)
        url = f"{base}/api/explore/v2.1/catalog/datasets/{dataset_id}"
        body, _headers, _raw = await self._resilient_request_json(
            handle, url, params={},
        )
        fields_meta = body.get("fields", [])
        fields = [
            {
                "name": f.get("name", ""),
                "type": f.get("type", "text"),
                "description": f.get("description", ""),
            }
            for f in fields_meta
            if isinstance(f, dict)
        ]
        return {
            "schema_id": f"{self.connector_id}.{dataset_id}",
            "version": "1.0.0",
            "format": "opendatasoft",
            "fields": fields,
        }

    # ------------------------------------------------------------------
    # ODSQL where builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_where(request: FetchRequest) -> str:
        clauses: list[str] = []
        for key, values in request.filters:
            if key == "where":
                clauses.append(values[0] if values else "")
            else:
                quoted = [f"'{v}'" for v in values]
                if len(quoted) == 1:
                    clauses.append(f"{key}={quoted[0]}")
                else:
                    clauses.append(f"{key} in ({','.join(quoted)})")

        if request.date_start is not None:
            clauses.append(f"date>='{request.date_start.strftime('%Y-%m-%d')}'")
        if request.date_end is not None:
            clauses.append(f"date<='{request.date_end.strftime('%Y-%m-%d')}'")

        return " AND ".join(clauses)


__all__ = ["OpendatasoftConnector"]
