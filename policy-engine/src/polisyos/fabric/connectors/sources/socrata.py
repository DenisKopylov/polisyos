"""
SocrataConnector — Socrata Open Data API (SODA) connector.

Fetches data from Socrata-powered open data portals (NYC Open Data,
Chicago Data Portal, etc.) via the SODA 2.1 API.

Key features:
- SoQL query support ($where, $limit, $offset, $order, $select)
- Incremental fetch via $where :updated_at > cursor
- Catalog browse via /api/views
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

_DEFAULT_LIMIT = 10000
_MAX_LIMIT = 50000


class SocrataConnector(HTTPConnectorBase[pd.DataFrame]):
    """Socrata Open Data API (SODA) connector."""

    namespace: ClassVar[str] = "socrata"
    short_id: ClassVar[str] = "soda"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = ""  # per-portal via profile

    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(
        base_delay=1.0,
        rate_limit_rps=5.0,
    )

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.FULL_FETCH
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.DIMENSION_FILTER
        | ConnectorCapability.INCREMENTAL_FETCH
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="Socrata Open Data (SODA)",
        source_organization="Various municipalities and agencies",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.INCREMENTAL_FETCH,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        base = self._base_url(handle)
        url = f"{base}/api/views"
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
        url = f"{base}/api/views"
        page = 1
        limit = 100

        while True:
            params = {"limit": str(limit), "page": str(page)}
            body, _headers, _raw = await self._resilient_request_json(
                handle, url, params=params,
            )
            if not isinstance(body, list):
                break
            for view in body:
                dataset_id = str(view.get("id", "unknown"))
                yield DatasetDescriptor(
                    dataset_id=dataset_id,
                    name=str(view.get("name") or dataset_id),
                    description=str(view.get("description") or "")[:500],
                    tags=("socrata",),
                    metadata={
                        "category": view.get("category", ""),
                        "attribution": view.get("attribution", ""),
                    },
                )
            if len(body) < limit:
                break
            page += 1

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base = self._base_url(handle)
        url = f"{base}/resource/{request.dataset_id}.json"
        params = self._build_soql_params(request)

        started = time.monotonic()
        all_records: list[dict[str, Any]] = []
        total_bytes = 0
        last_headers: dict[str, str] = {}
        all_raw: list[bytes] = []

        offset = 0
        limit = int(params.get("$limit", str(_DEFAULT_LIMIT)))

        while True:
            params["$offset"] = str(offset)
            body, headers, raw = await self._resilient_request_json(
                handle, url, params=params,
            )
            last_headers = headers
            all_raw.append(raw)
            total_bytes += len(raw)

            if not isinstance(body, list):
                break
            all_records.extend(body)

            if len(body) < limit:
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        base = self._base_url(handle)
        url = f"{base}/api/views/{dataset_id}.json"
        body, _headers, _raw = await self._resilient_request_json(
            handle, url, params={},
        )
        columns = body.get("columns", [])
        fields = [
            {
                "name": col.get("fieldName", ""),
                "type": col.get("dataTypeName", "text"),
                "description": col.get("description", ""),
            }
            for col in columns
            if isinstance(col, dict) and col.get("fieldName")
        ]
        return {
            "schema_id": f"{self.connector_id}.{dataset_id}",
            "version": "1.0.0",
            "format": "socrata-soda",
            "fields": fields,
        }

    # ------------------------------------------------------------------
    # SoQL param builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_soql_params(request: FetchRequest) -> dict[str, str]:
        params: dict[str, str] = {
            "$limit": str(_DEFAULT_LIMIT),
            "$order": ":id",
        }

        where_clauses: list[str] = []

        # Dimension filters
        for key, values in request.filters:
            if key == "$select":
                params["$select"] = ",".join(values)
            elif key == "$order":
                params["$order"] = ",".join(values)
            elif key == "$limit":
                params["$limit"] = values[0] if values else str(_DEFAULT_LIMIT)
            elif key == "$where":
                where_clauses.append(values[0] if values else "")
            else:
                # Dimension filter → SoQL $where
                quoted = [f"'{v}'" for v in values]
                if len(quoted) == 1:
                    where_clauses.append(f"{key}={quoted[0]}")
                else:
                    where_clauses.append(f"{key} in({','.join(quoted)})")

        # Time range
        if request.date_start is not None:
            where_clauses.append(
                f":updated_at>='{request.date_start.strftime('%Y-%m-%dT%H:%M:%S')}'"
            )
        if request.date_end is not None:
            where_clauses.append(
                f":updated_at<='{request.date_end.strftime('%Y-%m-%dT%H:%M:%S')}'"
            )

        # Incremental
        if request.incremental_since is not None:
            where_clauses.append(
                f":updated_at>'{request.incremental_since.value}'"
            )

        if where_clauses:
            params["$where"] = " AND ".join(where_clauses)

        return params


__all__ = ["SocrataConnector"]
