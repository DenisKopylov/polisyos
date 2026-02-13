"""
CKANResourceConnector — downloads actual data resources from CKAN packages.

Handles CSV and JSON resources from CKAN portals. The dataset_id format is
``{package_id}/{resource_id}`` or a direct resource URL.
"""

from __future__ import annotations

import csv
import io
import json as _json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar

import aiohttp
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
    FetchError,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class CKANResourceConnector(HTTPConnectorBase[pd.DataFrame]):
    """Download and parse individual CKAN resources (CSV/JSON)."""

    namespace: ClassVar[str] = "ckan"
    short_id: ClassVar[str] = "resource"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = ""

    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(
        base_delay=1.0,
        rate_limit_rps=3.0,
    )

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="CKAN Resource",
        source_organization="Various CKAN portals",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        base = self._base_url(handle)
        url = f"{base}/api/3/action/status_show"
        started = time.monotonic()
        try:
            _body, _headers, _raw = await self._resilient_request_json(
                handle, url, params={},
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
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base = self._base_url(handle)
        resource_url, fmt = await self._resolve_resource(handle, base, request.dataset_id)

        started = time.monotonic()
        session = await self._get_session(handle)
        timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)
        async with session.get(resource_url, timeout=timeout) as resp:
            if resp.status >= 400:
                raise FetchError(
                    message=f"CKAN resource download returned HTTP {resp.status}",
                    connector_id=self.connector_id,
                    dataset_id=request.dataset_id,
                )
            raw = await resp.read()
            headers = dict(resp.headers)

        duration_ms = self._elapsed_ms(started)
        df = self._parse_resource(raw, fmt)
        chash = compute_content_hash(raw, prefix=True)

        return self._build_fetch_result(
            data=df,
            row_count=len(df),
            schema_id=f"{self.connector_id}.resource",
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
    # Catalog browse (not applicable — use catalog connector)
    # ------------------------------------------------------------------

    async def list_datasets(
        self,
        handle: ConnectionHandle,
    ) -> AsyncIterator[Any]:
        # Not applicable for resource connector
        return
        yield  # make it an async generator  # pragma: no cover

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        return {
            "schema_id": f"{self.connector_id}.{dataset_id}",
            "version": "1.0.0",
            "format": "dynamic",
            "notes": "Schema depends on the resource format and content.",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _resolve_resource(
        self,
        handle: ConnectionHandle,
        base: str,
        dataset_id: str,
    ) -> tuple[str, str]:
        """Resolve dataset_id to (download_url, format).

        dataset_id can be:
        - ``{package_id}/{resource_id}`` → look up via package_show
        - A direct URL → use as-is with guessed format
        """
        if dataset_id.startswith("http://") or dataset_id.startswith("https://"):
            fmt = "csv" if dataset_id.lower().endswith(".csv") else "json"
            return dataset_id, fmt

        parts = dataset_id.split("/", 1)
        if len(parts) != 2:
            raise FetchError(
                message=f"Invalid dataset_id format: expected 'package_id/resource_id', got '{dataset_id}'",
                connector_id=self.connector_id,
                dataset_id=dataset_id,
            )

        package_id, resource_id = parts
        url = f"{base}/api/3/action/package_show"
        body, _headers, _raw = await self._resilient_request_json(
            handle, url, params={"id": package_id},
        )
        result = body.get("result", {})
        for r in result.get("resources", []):
            if r.get("id") == resource_id:
                return r["url"], (r.get("format", "csv") or "csv").lower()

        raise FetchError(
            message=f"Resource {resource_id} not found in package {package_id}",
            connector_id=self.connector_id,
            dataset_id=dataset_id,
        )

    @staticmethod
    def _parse_resource(raw: bytes, fmt: str) -> pd.DataFrame:
        fmt = fmt.lower()
        if fmt == "csv":
            text = raw.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        if fmt == "json":
            data = _json.loads(raw)
            if isinstance(data, list):
                return pd.DataFrame(data) if data else pd.DataFrame()
            if isinstance(data, dict):
                # Try common wrappers
                for key in ("result", "results", "data", "records"):
                    if key in data and isinstance(data[key], list):
                        return pd.DataFrame(data[key])
                return pd.DataFrame([data])
            return pd.DataFrame()
        # Fallback: try CSV
        text = raw.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return pd.DataFrame(rows) if rows else pd.DataFrame()


__all__ = ["CKANResourceConnector"]
