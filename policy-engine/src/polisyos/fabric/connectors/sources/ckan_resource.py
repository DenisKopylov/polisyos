"""
CKANResourceConnector — downloads actual data resources from CKAN packages.

Handles CSV, JSON, spreadsheets, and ZIP-wrapped tabular resources from CKAN portals. The dataset_id format is
``{package_id}/{resource_id}`` or a direct resource URL.
"""

from __future__ import annotations

import csv
import io
import importlib.util
import json as _json
import time
import zipfile
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar
from urllib.parse import urlparse

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
    """Download and parse individual CKAN resources."""

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
            fmt = self._guess_format(dataset_id, "")
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
                return r["url"], self._guess_format(str(r.get("url") or ""), str(r.get("format") or ""))

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
        if fmt in {"xlsx", "xls", "ods"}:
            return CKANResourceConnector._parse_spreadsheet(raw, fmt)
        if fmt == "zip":
            return CKANResourceConnector._parse_zip_archive(raw)
        # Fallback: try CSV
        text = raw.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    @staticmethod
    def _parse_spreadsheet(raw: bytes, fmt: str) -> pd.DataFrame:
        engine_map = {
            "xlsx": "openpyxl",
            "xls": "xlrd",
            "ods": "odf",
        }
        engine = engine_map.get(fmt)
        if engine and not importlib.util.find_spec(engine):
            engine = None

        try:
            workbook = pd.read_excel(
                io.BytesIO(raw),
                sheet_name=None,
                engine=engine,
            )
        except Exception as exc:
            raise FetchError(
                message=f"Failed to parse {fmt.upper()} resource: {exc}",
                connector_id=CKANResourceConnector.connector_id,
            ) from exc

        if isinstance(workbook, pd.DataFrame):
            return workbook

        frames: list[pd.DataFrame] = []
        if isinstance(workbook, dict):
            for sheet_name, frame in workbook.items():
                if not isinstance(frame, pd.DataFrame):
                    continue
                enriched = frame.copy()
                enriched["__sheet_name"] = sheet_name
                frames.append(enriched)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True, sort=False)

    @staticmethod
    def _parse_zip_archive(raw: bytes) -> pd.DataFrame:
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise FetchError(
                message=f"Failed to parse ZIP resource: {exc}",
                connector_id=CKANResourceConnector.connector_id,
            ) from exc

        frames: list[pd.DataFrame] = []
        with archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                inner_fmt = CKANResourceConnector._guess_format(name, "")
                if inner_fmt not in {"csv", "json", "xlsx", "xls", "ods"}:
                    continue
                inner_raw = archive.read(name)
                try:
                    frame = CKANResourceConnector._parse_resource(inner_raw, inner_fmt)
                except FetchError:
                    continue
                if frame.empty:
                    continue
                enriched = frame.copy()
                enriched["__source_file"] = name
                frames.append(enriched)

        if not frames:
            raise FetchError(
                message="ZIP resource does not contain supported tabular files",
                connector_id=CKANResourceConnector.connector_id,
            )
        return pd.concat(frames, ignore_index=True, sort=False)

    @staticmethod
    def _guess_format(url: str, raw_format: str) -> str:
        value = str(raw_format or "").strip().lower()
        aliases = {
            "csv": "csv",
            "json": "json",
            "xlsx": "xlsx",
            "xls": "xls",
            "xlsm": "xlsx",
            "ods": "ods",
            "zip": "zip",
            "application/zip": "zip",
            "application/json": "json",
            "text/csv": "csv",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.ms-excel": "xls",
            "application/vnd.oasis.opendocument.spreadsheet": "ods",
        }
        if value in aliases:
            return aliases[value]

        url_lc = urlparse(url).path.lower()
        for suffix, detected in (
            (".csv", "csv"),
            (".json", "json"),
            (".xlsx", "xlsx"),
            (".xls", "xls"),
            (".ods", "ods"),
            (".zip", "zip"),
        ):
            if url_lc.endswith(suffix):
                return detected
        return value or "csv"


__all__ = ["CKANResourceConnector"]
