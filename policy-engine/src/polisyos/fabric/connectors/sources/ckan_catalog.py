"""
CKANCatalogConnector — CKAN Action API catalog discovery.

Provides dataset discovery and metadata retrieval from CKAN portals
(data.gov.uk, data.gov, etc.) via the CKAN Action API v3.

Endpoints used:
- /api/3/action/status_show       — health check
- /api/3/action/package_list      — enumerate all packages
- /api/3/action/package_search    — search with query/filters
- /api/3/action/package_show      — single package metadata + resources
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar

import pandas as pd

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.connectors.base import (
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts import make_field_id, make_schema_id
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


class CKANCatalogConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for CKAN package and dataset discovery.

    Uses the CKAN Action API to enumerate packages, metadata, and resource
    descriptors before a resource-specific fetch is delegated elsewhere.

    Data source:
        CKAN-compatible portals
    Protocol:
        CKAN Action API v3
    Auth:
        Profile-driven per portal
    Async support:
        Standard async HTTP execution only
    Profile:
        Any ``connector_family='ckan'`` catalog profile
    """

    namespace: ClassVar[str] = "ckan"
    short_id: ClassVar[str] = "catalog"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = ""  # overridden per profile

    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(
        base_delay=1.0,
        rate_limit_rps=5.0,
    )

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.FULL_FETCH
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="CKAN Catalog",
        source_organization="Various CKAN portals",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )
    _MAX_LIST_PAGES: ClassVar[int] = 1_000

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        base = self._base_url(handle)
        url = f"{base}/api/3/action/status_show"
        started = time.monotonic()
        try:
            _body, _headers, _raw = await self._resilient_request_json(
                handle,
                url,
                params={},
            )
            return HealthStatus(
                healthy=True,
                message="HTTP 200",
                latency_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            return HealthStatus(
                healthy=False,
                message=str(exc),
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
        url = f"{base}/api/3/action/package_search"
        offset = 0
        rows_per_page = 100
        pages_seen = 0
        seen_page_fingerprints: set[tuple[str, ...]] = set()

        while True:
            pages_seen += 1
            if pages_seen > self._MAX_LIST_PAGES:
                raise FetchError(
                    message=(
                        "CKAN catalog pagination exceeded safe page limit "
                        f"({pages_seen} > {self._MAX_LIST_PAGES})"
                    ),
                    connector_id=self.connector_id,
                )
            params = {"rows": str(rows_per_page), "start": str(offset)}
            body, _headers, _raw = await self._resilient_request_json(
                handle,
                url,
                params=params,
            )
            result = body.get("result", {})
            results_list = result.get("results", [])
            if not isinstance(results_list, list) or not results_list:
                break

            page_fingerprint = tuple(
                str(pkg.get("id") or pkg.get("name") or idx)
                for idx, pkg in enumerate(results_list)
                if isinstance(pkg, dict)
            )
            if page_fingerprint in seen_page_fingerprints:
                raise FetchError(
                    message="CKAN catalog pagination repeated a prior page fingerprint",
                    connector_id=self.connector_id,
                )
            seen_page_fingerprints.add(page_fingerprint)

            for pkg in results_list:
                dataset_id = str(pkg.get("name") or pkg.get("id", "unknown"))
                title = str(pkg.get("title") or dataset_id)
                notes = str(pkg.get("notes") or "")
                org = pkg.get("organization", {})
                org_name = str(org.get("title", "")) if isinstance(org, dict) else ""
                yield DatasetDescriptor(
                    dataset_id=dataset_id,
                    name=title,
                    description=notes[:500],
                    tags=("ckan",),
                    metadata={"organization": org_name},
                )

            if len(results_list) < rows_per_page:
                break
            offset += rows_per_page

    # ------------------------------------------------------------------
    # Fetch (package metadata + resources)
    # ------------------------------------------------------------------

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base = self._base_url(handle)
        url = f"{base}/api/3/action/package_show"
        params = {"id": request.dataset_id}

        started = time.monotonic()
        body, headers, raw = await self._resilient_request_json(
            handle,
            url,
            params=params,
        )
        duration_ms = self._elapsed_ms(started)

        result = body.get("result", {})
        if not result:
            raise FetchError(
                message=f"Package {request.dataset_id} not found",
                connector_id=self.connector_id,
                dataset_id=request.dataset_id,
            )

        resources = result.get("resources", [])
        rows = []
        for r in resources:
            rows.append(
                {
                    "resource_id": r.get("id", ""),
                    "name": r.get("name", ""),
                    "format": r.get("format", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                    "created": r.get("created", ""),
                    "last_modified": r.get("last_modified", ""),
                    "size": r.get("size"),
                }
            )

        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        content_hash = compute_content_hash(raw, prefix=True)
        etag = headers.get("ETag")
        last_modified = headers.get("Last-Modified")

        return self._build_fetch_result(
            data=df,
            row_count=len(df),
            schema_id=make_schema_id(self.connector_id, "package"),
            schema_version="1.0.0",
            quality_tier=QualityTier.SILVER,
            bytes_transferred=len(raw),
            completeness=frame_completeness(df) if not df.empty else 1.0,
            fetched_at=datetime.now(UTC),
            fetch_duration_ms=duration_ms,
            content_hash=content_hash,
            etag=etag,
            last_modified=last_modified,
        )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        schema_id = make_schema_id(self.connector_id, dataset_id)
        field_names = (
            "resource_id",
            "name",
            "format",
            "url",
            "description",
            "created",
            "last_modified",
            "size",
        )
        field_types = {
            "size": "number",
        }
        return {
            "schema_id": schema_id,
            "version": "1.0.0",
            "format": "ckan-package",
            "fields": [
                {
                    "name": field_name,
                    "field_id": make_field_id(schema_id, field_name),
                    "type": field_types.get(field_name, "string"),
                }
                for field_name in field_names
            ],
        }


__all__ = ["CKANCatalogConnector"]
