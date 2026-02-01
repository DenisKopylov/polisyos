"""
SDMXConnector - Reference implementation for SDMX REST APIs (SDMX-JSON).

Target APIs (URL patterns are configurable via X-SDMX-* headers)
----------------------------------------------------------------
* ECB (data-api.ecb.europa.eu)
* Eurostat (ec.europa.eu/sdmx/get-data)
* OECD (stats.oecd.org/sdmx-rest)
* IMF (api.imf.org)

Capabilities
------------
CATALOG_BROWSE    List available dataflows via the /dataflow/ endpoint.
FULL_FETCH        Download a single dataflow as a DataFrame.
STREAMING         Yield chunks per time-series (downstream-friendly iteration).
FRESHNESS_CHECK   HEAD request to the data endpoint; compares Last-Modified or ETag.
DIMENSION_FILTER  Encodes FetchRequest.filters into SDMX REST path segments.

Design Decisions
----------------
* SDMX-JSON is used (Accept: application/vnd.sdmx.data+json) to avoid XML parsing.
* Dimensions are read from the SDMX-JSON structure block for column names.
* Streaming splits the DataFrame by non-time dimensions; this is not memory-safe
  for very large datasets, but it enables downstream iteration patterns.

Example ConnectionConfig
------------------------
>>> config_json = {
...     "url": "https://stats.oecd.org/sdmx-rest",
...     "headers": {
...         "X-SDMX-Agency": "OECD",
...         "X-SDMX-DataPath": "data",
...         "X-SDMX-DataflowPath": "dataflow",
...         "X-SDMX-DimensionOrder": "freq,geo,indicator,unit,multiplier",
...     },
...     "timeout_seconds": 60,
...     "max_retries": 3,
... }
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar, Iterable

import aiohttp
import pandas as pd

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.resilience import (
    with_circuit_breaker,
    with_retry,
)
from polisyos.fabric.connectors.types import (
    ConfigurationError,
    DataChunk,
    DatasetDescriptor,
    FetchError,
    FreshnessResult,
    FreshnessStatus,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


def _join_url(base: str, *parts: str) -> str:
    if not base:
        return ""
    cleaned = [base.rstrip("/")]
    cleaned.extend(p.strip("/") for p in parts if p)
    return "/".join(cleaned)


def _parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _dimension_values(dim: dict[str, Any]) -> list[str]:
    values = dim.get("values", [])
    labels: list[str] = []
    for entry in values:
        if isinstance(entry, dict):
            labels.append(str(entry.get("id") or entry.get("name") or entry))
        else:
            labels.append(str(entry))
    return labels


def _parse_sdmx_json(body: dict[str, Any]) -> pd.DataFrame:
    """Convert an SDMX-JSON dataset into a flat DataFrame."""
    datasets = body.get("dataSets") or body.get("datasets") or []
    if not datasets:
        return pd.DataFrame()

    dataset = datasets[0]
    structure = body.get("structure", {})
    dims = structure.get("dimensions", {})
    series_dims = dims.get("series", []) or []
    obs_dims = dims.get("observation", []) or []

    series_labels = [d.get("id", f"series_{i}") for i, d in enumerate(series_dims)]
    obs_labels = [d.get("id", f"obs_{i}") for i, d in enumerate(obs_dims)]

    series_values = [_dimension_values(d) for d in series_dims]
    obs_values = [_dimension_values(d) for d in obs_dims]

    rows: list[dict[str, Any]] = []

    if "series" in dataset:
        for series_key, series_entry in dataset.get("series", {}).items():
            series_indices = [int(x) for x in str(series_key).split(":") if x != ""]
            series_row = {}
            for idx, label in enumerate(series_labels):
                values = series_values[idx] if idx < len(series_values) else []
                pos = series_indices[idx] if idx < len(series_indices) else 0
                series_row[label] = values[pos] if pos < len(values) else str(pos)

            observations = series_entry.get("observations", {})
            for obs_key, obs_value in observations.items():
                obs_indices = [int(x) for x in str(obs_key).split(":") if x != ""]
                obs_row = {}
                for idx, label in enumerate(obs_labels):
                    values = obs_values[idx] if idx < len(obs_values) else []
                    pos = obs_indices[idx] if idx < len(obs_indices) else 0
                    obs_row[label] = values[pos] if pos < len(values) else str(pos)

                value = obs_value[0] if isinstance(obs_value, list) and obs_value else obs_value
                rows.append({**series_row, **obs_row, "value": value})
    else:
        observations = dataset.get("observations", {})
        for obs_key, obs_value in observations.items():
            obs_indices = [int(x) for x in str(obs_key).split(":") if x != ""]
            row: dict[str, Any] = {}
            for idx, label in enumerate(obs_labels):
                values = obs_values[idx] if idx < len(obs_values) else []
                pos = obs_indices[idx] if idx < len(obs_indices) else 0
                row[label] = values[pos] if pos < len(values) else str(pos)
            value = obs_value[0] if isinstance(obs_value, list) and obs_value else obs_value
            row["value"] = value
            rows.append(row)

    return pd.DataFrame(rows)


class SDMXConnector(BaseConnector[pd.DataFrame]):
    """SDMX REST connector targeting SDMX-JSON data endpoints."""

    connector_id: ClassVar[str] = "reference.sdmx"

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.FULL_FETCH
        | ConnectorCapability.STREAMING
        | ConnectorCapability.FRESHNESS_CHECK
        | ConnectorCapability.DIMENSION_FILTER
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="sdmx",
        version="1.0.0",
        namespace="reference",
        source_name="SDMX Statistical Data Exchange",
        source_organization="PolicyOS Reference",
        trust_level=TrustLevel.HIGH,
        quality_tier=QualityTier.GOLD,
        capabilities=capabilities_from_flags(
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
            ConnectorCapability.FRESHNESS_CHECK,
            ConnectorCapability.DIMENSION_FILTER,
        ),
    )

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_sdmx_config(config: ConnectionConfig) -> dict[str, Any]:
        dimension_order = config.headers.get("X-SDMX-DimensionOrder")
        order = None
        if dimension_order:
            order = [seg.strip() for seg in dimension_order.split(",") if seg.strip()]
        return {
            "agency": config.headers.get("X-SDMX-Agency", "ECB"),
            "version": config.headers.get("X-SDMX-Version", "2"),
            "data_path": config.headers.get("X-SDMX-DataPath", "data"),
            "dataflow_path": config.headers.get("X-SDMX-DataflowPath", "dataflow"),
            "dimension_order": order,
            "dataflow_detail": config.headers.get("X-SDMX-DataflowDetail", "referencestubs"),
        }

    @staticmethod
    def _strip_internal_headers(headers: dict[str, str]) -> dict[str, str]:
        return {k: v for k, v in headers.items() if not k.startswith("X-SDMX-")}

    def _build_auth_headers(self, config: ConnectionConfig) -> dict[str, str]:
        headers = self._strip_internal_headers(config.headers)
        if config.auth_method == "bearer":
            token = config.auth_credentials.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif config.auth_method == "api_key":
            key_name = config.auth_credentials.get("header", "X-API-Key")
            headers[key_name] = config.auth_credentials.get("key", "")
        return headers

    def _sdmx_data_headers(self, config: ConnectionConfig) -> dict[str, str]:
        headers = self._build_auth_headers(config)
        headers.setdefault("Accept", "application/vnd.sdmx.data+json;version=1.0")
        return headers

    def _sdmx_structure_headers(self, config: ConnectionConfig) -> dict[str, str]:
        headers = self._build_auth_headers(config)
        headers.setdefault("Accept", "application/vnd.sdmx.structure+json;version=1.0")
        return headers

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        if not config.url:
            raise ConfigurationError(
                message="SDMX base URL is required",
                connector_id=self.connector_id,
                field="url",
            )
        handle = self._create_handle(config)
        handle.state["sdmx"] = self._parse_sdmx_config(config)
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @with_retry(max_attempts=3, base_delay=2.0)
    @with_circuit_breaker()
    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        start = time.monotonic()
        cfg = handle.state.get("sdmx") or self._parse_sdmx_config(handle.config)
        url = _join_url(handle.config.url, cfg["dataflow_path"], cfg["agency"])
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self._sdmx_structure_headers(handle.config),
                    timeout=aiohttp.ClientTimeout(total=handle.config.timeout_seconds),
                ) as resp:
                    latency = (time.monotonic() - start) * 1000
                    return HealthStatus(
                        healthy=(resp.status == 200),
                        message=f"HTTP {resp.status}",
                        latency_ms=round(latency, 2),
                    )
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    # ------------------------------------------------------------------
    # Catalog browse
    # ------------------------------------------------------------------
    async def list_datasets(
        self,
        handle: ConnectionHandle,
    ) -> AsyncIterator[DatasetDescriptor]:
        cfg = handle.state.get("sdmx") or self._parse_sdmx_config(handle.config)
        detail = cfg["dataflow_detail"]
        url = _join_url(handle.config.url, cfg["dataflow_path"], cfg["agency"])
        if detail:
            url = f"{url}?detail={detail}"

        body, _headers, _bytes_xferred = await self._request_json(
            handle,
            url,
            headers=self._sdmx_structure_headers(handle.config),
        )

        dataflows = self._extract_dataflows(body)
        for df_entry in dataflows:
            did = str(df_entry.get("id", "unknown"))
            label = df_entry.get("name", df_entry.get("label", ""))
            if isinstance(label, dict):
                label = label.get("en") or next(iter(label.values()), "")
            yield DatasetDescriptor(
                dataset_id=f"{cfg['agency']}.{did}",
                name=str(label) or did,
                description=str(df_entry.get("description", "")),
                tags=("sdmx", str(cfg["agency"]).lower()),
            )

    def _extract_dataflows(self, body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        structure = body.get("structure", body)
        dataflows = (
            structure.get("dataflows")
            or structure.get("dataFlows")
            or structure.get("dataflow")
            or structure.get("dataFlow")
            or []
        )
        if isinstance(dataflows, dict):
            if all(isinstance(v, dict) for v in dataflows.values()):
                return list(dataflows.values())
            return [dataflows]
        if isinstance(dataflows, list):
            return dataflows
        return []

    # ------------------------------------------------------------------
    # Core fetch
    # ------------------------------------------------------------------
    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        cfg = handle.state.get("sdmx") or self._parse_sdmx_config(handle.config)
        filter_path = self._build_filter_path(request, cfg.get("dimension_order"))
        dataflow_key = request.dataset_id
        url = _join_url(
            handle.config.url,
            cfg["data_path"],
            cfg["agency"],
            dataflow_key,
            filter_path,
        )

        start = time.monotonic()
        body, headers, bytes_xferred = await self._request_json(
            handle,
            url,
            headers=self._sdmx_data_headers(handle.config),
        )
        duration_ms = (time.monotonic() - start) * 1000

        df = _parse_sdmx_json(body)

        content_hash = f"sha256:{hashlib.sha256(body.get('_raw', b'')).hexdigest()}"
        last_modified = headers.get("Last-Modified")
        etag = headers.get("ETag")

        if etag:
            version = DataVersion(
                strategy=VersionStrategy.ETAG,
                value=etag,
                timestamp=datetime.now(timezone.utc),
                content_hash=content_hash,
            )
        elif last_modified:
            parsed_last_modified = _parse_http_datetime(last_modified)
            version = DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=parsed_last_modified.isoformat() if parsed_last_modified else last_modified,
                timestamp=parsed_last_modified or datetime.now(timezone.utc),
                content_hash=content_hash,
            )
        else:
            version = DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=content_hash,
                timestamp=datetime.now(timezone.utc),
                content_hash=content_hash,
            )

        return FetchResult(
            data=df,
            row_count=len(df),
            schema_id=f"{self.connector_id}.{dataflow_key}",
            schema_version="1.0.0",
            version=version,
            fetched_at=datetime.now(timezone.utc),
            completeness=1.0,
            quality_tier=QualityTier.GOLD,
            fetch_duration_ms=round(duration_ms, 2),
            bytes_transferred=bytes_xferred,
        )

    # ------------------------------------------------------------------
    # Streaming fetch
    # ------------------------------------------------------------------
    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[pd.DataFrame]]:
        result = await self.fetch(handle, request)
        df: pd.DataFrame = result.data

        if df.empty:
            yield DataChunk(
                data=df,
                chunk_index=0,
                row_count=0,
                is_first=True,
                is_last=True,
                total_chunks=1,
            )
            return

        time_cols = [
            c
            for c in df.columns
            if c.lower() in {"time", "time_period", "period", "date", "obs_time"}
        ]
        group_cols = [c for c in df.columns if c not in time_cols and c not in ("value",)]

        if group_cols:
            groups = df.groupby(group_cols)
            total = len(groups)
            for idx, (_, chunk_df) in enumerate(groups):
                yield DataChunk(
                    data=chunk_df.reset_index(drop=True),
                    chunk_index=idx,
                    row_count=len(chunk_df),
                    is_first=(idx == 0),
                    is_last=(idx == total - 1),
                    total_chunks=total,
                )
        else:
            yield DataChunk(
                data=df,
                chunk_index=0,
                row_count=len(df),
                is_first=True,
                is_last=True,
                total_chunks=1,
            )

    # ------------------------------------------------------------------
    # Freshness check
    # ------------------------------------------------------------------
    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: DataVersion,
    ) -> FreshnessResult:
        cfg = handle.state.get("sdmx") or self._parse_sdmx_config(handle.config)
        url = _join_url(handle.config.url, cfg["data_path"], cfg["agency"], dataset_id)
        headers = self._sdmx_data_headers(handle.config)

        try:
            head_headers = await self._request_head(handle, url, headers=headers)
            last_modified = head_headers.get("Last-Modified")
            etag = head_headers.get("ETag")
        except Exception:
            return FreshnessResult(status=FreshnessStatus.UNKNOWN)

        if cached_version.strategy == VersionStrategy.ETAG and etag:
            if etag != cached_version.value:
                return FreshnessResult(
                    status=FreshnessStatus.STALE,
                    new_version_available=True,
                    new_version_hint=etag,
                    source_updated_at=datetime.now(timezone.utc),
                )
            return FreshnessResult(status=FreshnessStatus.FRESH)

        if cached_version.strategy == VersionStrategy.TIMESTAMP and last_modified:
            if last_modified != cached_version.value:
                return FreshnessResult(
                    status=FreshnessStatus.STALE,
                    new_version_available=True,
                    new_version_hint=last_modified,
                    source_updated_at=datetime.now(timezone.utc),
                )
            return FreshnessResult(status=FreshnessStatus.FRESH)

        return FreshnessResult(status=FreshnessStatus.UNKNOWN)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_filter_path(
        request: FetchRequest,
        dimension_order: list[str] | None = None,
    ) -> str:
        standard_dims = ["freq", "geo", "indicator", "unit", "multiplier"]
        order = dimension_order or standard_dims
        filter_map = {key: values for key, values in request.filters}

        parts: list[str] = []
        for dim in order:
            values = filter_map.pop(dim, ())
            parts.append("+".join(values) if values else "")

        if filter_map:
            for dim in sorted(filter_map.keys()):
                values = filter_map[dim]
                parts.append("+".join(values) if values else "")

        while parts and parts[-1] == "":
            parts.pop()

        return "/".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------
    @with_retry(max_attempts=3, base_delay=2.0)
    @with_circuit_breaker()
    async def _request_json(
        self,
        handle: ConnectionHandle,
        url: str,
        *,
        headers: dict[str, str],
    ) -> tuple[dict[str, Any], dict[str, str], int]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=handle.config.timeout_seconds),
            ) as resp:
                if resp.status != 200:
                    error = FetchError(
                        message=f"SDMX fetch returned HTTP {resp.status}",
                        connector_id=self.connector_id,
                        request_params={"status_code": resp.status, "url": url},
                    )
                    error.status_code = resp.status  # type: ignore[attr-defined]
                    raise error
                raw = await resp.read()
                bytes_xferred = len(raw)
                import json

                try:
                    body = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise FetchError(
                        message=f"SDMX JSON decode failed: {exc}",
                        connector_id=self.connector_id,
                        request_params={"url": url},
                    ) from exc
                if not isinstance(body, dict):
                    raise FetchError(
                        message="SDMX response is not a JSON object",
                        connector_id=self.connector_id,
                    )
                body["_raw"] = raw
                return body, dict(resp.headers), bytes_xferred

    @with_retry(max_attempts=3, base_delay=2.0)
    @with_circuit_breaker()
    async def _request_head(
        self,
        handle: ConnectionHandle,
        url: str,
        *,
        headers: dict[str, str],
    ) -> dict[str, str]:
        async with aiohttp.ClientSession() as session:
            async with session.head(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=handle.config.timeout_seconds),
            ) as resp:
                return dict(resp.headers)

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not config.url:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="SDMX base URL is required",
                    field="url",
                )
            )
        if issues:
            return ValidationResult.failure(*issues)
        return ValidationResult.success()
