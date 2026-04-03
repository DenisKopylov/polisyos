"""
SDMXSourceConnector — Production SDMX REST connector (SDMX-JSON).

Promoted from the reference implementation with:
- HTTPConnectorBase for resilience/retry/rate-limiting
- Time filter support (startPeriod/endPeriod)
- Proper ConnectorMetadataSpec

Target APIs (configurable via X-SDMX-* headers in ConnectionConfig):
- ECB  (data-api.ecb.europa.eu)
- OECD (sdmx.oecd.org/public/rest)
- IMF  (sdmxcentral.imf.org)
- BIS  (stats.bis.org/api/v1)
"""

from __future__ import annotations

import json as _json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar, Iterable

import aiohttp
import pandas as pd

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    DatasetCapabilitySnapshot,
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
    DataChunk,
    DatasetDescriptor,
    FetchError,
    FreshnessResult,
    FreshnessStatus,
    RateLimitError,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    ResilienceInfo,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _join_url(base: str, *parts: str) -> str:
    if not base:
        return ""
    cleaned = [base.rstrip("/")]
    cleaned.extend(p.strip("/") for p in parts if p)
    return "/".join(cleaned)


def _sdmx_path_parts(*parts: str) -> list[str]:
    return [part for part in parts if part]


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


def _structure_payload_root(body: dict[str, Any]) -> dict[str, Any]:
    structure = body.get("structure")
    if isinstance(structure, dict):
        return structure
    nested = body.get("data")
    if isinstance(nested, dict):
        nested_structure = nested.get("structure")
        if isinstance(nested_structure, dict):
            return nested_structure
        return nested
    return body


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
    if isinstance(body.get("data"), dict):
        nested = body["data"]
        if "dataSets" in nested or "datasets" in nested:
            body = nested
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
                vals = series_values[idx] if idx < len(series_values) else []
                pos = series_indices[idx] if idx < len(series_indices) else 0
                series_row[label] = vals[pos] if pos < len(vals) else str(pos)

            observations = series_entry.get("observations", {})
            for obs_key, obs_value in observations.items():
                obs_indices = [int(x) for x in str(obs_key).split(":") if x != ""]
                obs_row = {}
                for idx, label in enumerate(obs_labels):
                    vals = obs_values[idx] if idx < len(obs_values) else []
                    pos = obs_indices[idx] if idx < len(obs_indices) else 0
                    obs_row[label] = vals[pos] if pos < len(vals) else str(pos)

                value = obs_value[0] if isinstance(obs_value, list) and obs_value else obs_value
                rows.append({**series_row, **obs_row, "value": value})
    else:
        observations = dataset.get("observations", {})
        for obs_key, obs_value in observations.items():
            obs_indices = [int(x) for x in str(obs_key).split(":") if x != ""]
            row: dict[str, Any] = {}
            for idx, label in enumerate(obs_labels):
                vals = obs_values[idx] if idx < len(obs_values) else []
                pos = obs_indices[idx] if idx < len(obs_indices) else 0
                row[label] = vals[pos] if pos < len(vals) else str(pos)
            value = obs_value[0] if isinstance(obs_value, list) and obs_value else obs_value
            row["value"] = value
            rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class SDMXSourceConnector(HTTPConnectorBase[pd.DataFrame]):
    """Production SDMX connector for ECB, OECD, IMF, BIS, ILO, and peers.

    Uses profile-provided base URLs and SDMX agency headers to fetch grouped
    datasets, stream larger responses, and inspect dataset structure.

    Data source:
        Profile-defined SDMX agencies
    Protocol:
        SDMX-JSON / SDMX-ML over HTTP
    Auth:
        Profile-driven, usually none
    Async support:
        Yes, via async fetch and ``fetch_stream()``
    Profile:
        Any ``connector_family='sdmx'`` profile such as ``oecd_sdmx``
    """

    namespace: ClassVar[str] = "sdmx"
    short_id: ClassVar[str] = "source"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = ""  # overridden per profile via ConnectionConfig.url

    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(
        base_delay=2.0,
        max_delay=120.0,
        rate_limit_rps=5.0,
    )

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.FULL_FETCH
        | ConnectorCapability.STREAMING
        | ConnectorCapability.FRESHNESS_CHECK
        | ConnectorCapability.DIMENSION_FILTER
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="SDMX Statistical Data Exchange",
        source_organization="Various statistical agencies (ECB, OECD, IMF, BIS)",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.GOLD,
        capabilities=capabilities_from_flags(
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
            ConnectorCapability.FRESHNESS_CHECK,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    # ------------------------------------------------------------------
    # SDMX config from X-SDMX-* headers
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
            "include_agency_in_data_path": config.headers.get(
                "X-SDMX-IncludeAgencyInDataPath", "true"
            ).strip().lower() not in {"0", "false", "no", "off"},
            "dataflow_detail": config.headers.get(
                "X-SDMX-DataflowDetail", "referencestubs"
            ),
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
        headers.setdefault(
            "Accept", "application/vnd.sdmx.structure+json;version=1.0"
        )
        return headers

    # ------------------------------------------------------------------
    # Lifecycle (extends HTTPConnectorBase)
    # ------------------------------------------------------------------

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = await super().connect(config)
        handle.state["sdmx"] = self._parse_sdmx_config(config)
        return handle

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        cfg = handle.state.get("sdmx") or self._parse_sdmx_config(handle.config)
        base = self._base_url(handle)
        url = _join_url(base, cfg["dataflow_path"], cfg["agency"])
        started = time.monotonic()
        try:
            _body, headers, _raw = await self._sdmx_request_json(
                handle, url, accept="structure",
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
        cfg = handle.state.get("sdmx") or self._parse_sdmx_config(handle.config)
        base = self._base_url(handle)
        detail = cfg["dataflow_detail"]
        url = _join_url(base, cfg["dataflow_path"], cfg["agency"])
        if detail:
            url = f"{url}?detail={detail}"

        body, _headers, _raw = await self._sdmx_request_json(
            handle, url, accept="structure",
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

    @staticmethod
    def _extract_dataflows(body: dict[str, Any]) -> Iterable[dict[str, Any]]:
        structure = _structure_payload_root(body)
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

    @staticmethod
    def _extract_dataflow_version(body: dict[str, Any], dataset_id: str) -> str | None:
        target = dataset_id.split(".")[-1]
        for entry in SDMXSourceConnector._extract_dataflows(body):
            if str(entry.get("id") or "") == target:
                version = str(entry.get("version") or "").strip()
                return version or None
        return None

    @staticmethod
    def _extract_structure_dimension_order(body: dict[str, Any]) -> list[str]:
        structure = _structure_payload_root(body)
        candidate_sets = (
            structure.get("dataStructures"),
            structure.get("datastructures"),
            structure.get("dataStructure"),
            structure.get("datastructure"),
        )
        entries: list[dict[str, Any]] = []
        for candidate in candidate_sets:
            if isinstance(candidate, list):
                entries.extend(entry for entry in candidate if isinstance(entry, dict))
            elif isinstance(candidate, dict):
                if all(isinstance(value, dict) for value in candidate.values()):
                    entries.extend(value for value in candidate.values() if isinstance(value, dict))
                else:
                    entries.append(candidate)
        for entry in entries:
            components = (
                entry.get("dataStructureComponents")
                or entry.get("dataStructureDefinition")
                or entry.get("components")
                or {}
            )
            dimensions = components.get("dimensionList") or components.get("dimensions") or {}
            values = dimensions.get("dimensions") or dimensions.get("dimension") or dimensions
            if isinstance(values, list):
                names = [str(dim.get("id") or "").strip() for dim in values if isinstance(dim, dict)]
                names = [name for name in names if name]
                if names:
                    return names
        return []

    @staticmethod
    def _extract_constraint_positions(body: dict[str, Any]) -> dict[str, list[str]]:
        structure = _structure_payload_root(body)
        constraints = (
            structure.get("contentConstraints")
            or structure.get("contentconstraints")
            or structure.get("constraints")
            or []
        )
        entries: list[dict[str, Any]] = []
        if isinstance(constraints, list):
            entries = [entry for entry in constraints if isinstance(entry, dict)]
        elif isinstance(constraints, dict):
            if all(isinstance(value, dict) for value in constraints.values()):
                entries = [value for value in constraints.values() if isinstance(value, dict)]
            else:
                entries = [constraints]
        allowed: dict[str, set[str]] = {}
        for entry in entries:
            cube_regions = entry.get("cubeRegions") or entry.get("cubeRegion") or []
            if isinstance(cube_regions, dict):
                cube_regions = [cube_regions]
            for region in cube_regions:
                if not isinstance(region, dict):
                    continue
                key_values = region.get("keyValues") or region.get("keyvalues") or {}
                for dim_name, payload in key_values.items():
                    if not isinstance(payload, dict):
                        continue
                    values = payload.get("values") or payload.get("value") or []
                    if isinstance(values, dict):
                        values = [values]
                    bucket = allowed.setdefault(str(dim_name), set())
                    for value in values:
                        if isinstance(value, dict):
                            token = str(value.get("id") or value.get("value") or "").strip()
                        else:
                            token = str(value).strip()
                        if token:
                            bucket.add(token)
        return {
            key: sorted(values)
            for key, values in allowed.items()
            if values
        }

    @staticmethod
    def _estimate_constraint_cardinality(allowed_positions: dict[str, list[str]]) -> int:
        if not allowed_positions:
            return 0
        cardinality = 1
        for values in allowed_positions.values():
            size = len(values)
            if size <= 0:
                continue
            cardinality *= size
        return cardinality

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
            self._base_url(handle),
            *_sdmx_path_parts(
                cfg["data_path"],
                cfg["agency"] if cfg.get("include_agency_in_data_path", True) else "",
                dataflow_key,
            ),
            filter_path,
        )

        # Add time filter params (startPeriod/endPeriod)
        time_params = self._build_time_params(request)
        if time_params:
            qs = "&".join(f"{k}={v}" for k, v in time_params.items())
            url = f"{url}?{qs}"

        started = time.monotonic()
        body, headers, raw = await self._sdmx_request_json(
            handle, url, accept="data",
        )
        duration_ms = self._elapsed_ms(started)

        df = _parse_sdmx_json(body)
        content_hash = compute_content_hash(raw, prefix=True)
        etag = headers.get("ETag")
        last_modified = headers.get("Last-Modified")

        return self._build_fetch_result(
            data=df,
            row_count=len(df),
            schema_id=f"{self.connector_id}.{dataflow_key}",
            schema_version="1.0.0",
            quality_tier=QualityTier.GOLD,
            bytes_transferred=len(raw),
            completeness=frame_completeness(df) if not df.empty else 1.0,
            fetched_at=datetime.now(timezone.utc),
            fetch_duration_ms=duration_ms,
            content_hash=content_hash,
            etag=etag,
            last_modified=last_modified,
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
        group_cols = [
            c for c in df.columns if c not in time_cols and c not in ("value",)
        ]

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
        url = _join_url(
            self._base_url(handle),
            *_sdmx_path_parts(
                cfg["data_path"],
                cfg["agency"] if cfg.get("include_agency_in_data_path", True) else "",
                dataset_id,
            ),
        )
        try:
            head_headers = await self._sdmx_request_head(handle, url)
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
    # Schema
    # ------------------------------------------------------------------

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        return {
            "schema_id": f"{self.connector_id}.{dataset_id}",
            "version": "1.0.0",
            "format": "sdmx-json",
            "fields": [
                {"name": "value", "type": "number"},
            ],
            "notes": "Schema is dynamic — dimension columns depend on the dataflow.",
        }

    async def describe_dataset(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> DatasetCapabilitySnapshot:
        cfg = handle.state.get("sdmx") or self._parse_sdmx_config(handle.config)
        base = self._base_url(handle)
        url = _join_url(base, cfg["dataflow_path"], cfg["agency"], dataset_id)
        url = f"{url}?references=descendants&detail=referencepartial"
        body, _headers, raw = await self._sdmx_request_json(
            handle,
            url,
            accept="structure",
        )
        dimension_order = tuple(self._extract_structure_dimension_order(body))
        allowed_positions = self._extract_constraint_positions(body)
        constraint_hash = compute_content_hash(raw, prefix=True)
        return DatasetCapabilitySnapshot(
            source=str(cfg["agency"]).lower(),
            dataset_id=dataset_id,
            resolved_dataset_id=dataset_id,
            preferred_transport="sdmx",
            dimension_order=dimension_order,
            allowed_positions=allowed_positions,
            availability_hash=constraint_hash,
            constraint_hash=constraint_hash,
            estimated_cardinality=self._estimate_constraint_cardinality(allowed_positions),
            version_hint=self._extract_dataflow_version(body, dataset_id),
            last_checked_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Config validation
    # ------------------------------------------------------------------

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not config.url and not cls._BASE_URL:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="SDMX base URL is required (provide via ConnectionConfig.url or profile)",
                    field="url",
                )
            )
        if issues:
            return ValidationResult.failure(*issues)
        return ValidationResult.success()

    # ------------------------------------------------------------------
    # Filter / time helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_filter_path(
        request: FetchRequest,
        dimension_order: list[str] | None = None,
    ) -> str:
        standard_dims = ["freq", "geo", "indicator", "unit", "multiplier"]
        order = dimension_order or standard_dims
        filter_map = {key: values for key, values in request.filters}

        # Remove SDMX-specific "key" filter (used as raw path segment)
        key_filter = filter_map.pop("key", None)
        if key_filter:
            return "+".join(key_filter)

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

    @staticmethod
    def _build_time_params(request: FetchRequest) -> dict[str, str]:
        params: dict[str, str] = {}
        if request.date_start is not None:
            params["startPeriod"] = request.date_start.strftime("%Y-%m-%d")
        if request.date_end is not None:
            params["endPeriod"] = request.date_end.strftime("%Y-%m-%d")
        return params

    # ------------------------------------------------------------------
    # SDMX-specific HTTP (with custom Accept headers)
    # ------------------------------------------------------------------

    async def _sdmx_request_json(
        self,
        handle: ConnectionHandle,
        url: str,
        *,
        accept: str = "data",
    ) -> tuple[dict[str, Any], dict[str, str], bytes]:
        """SDMX GET with custom Accept header (data or structure)."""
        if accept == "structure":
            req_headers = self._sdmx_structure_headers(handle.config)
        else:
            req_headers = self._sdmx_data_headers(handle.config)

        session = await self._get_session(handle)
        timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)

        async with session.get(url, headers=req_headers, timeout=timeout) as resp:
            headers = dict(resp.headers)
            if resp.status == 429:
                from polisyos.fabric.connectors.sources.http_common import (
                    retry_after_seconds,
                    safe_int,
                )

                retry_after = retry_after_seconds(headers)
                raise RateLimitError(
                    connector_id=self.connector_id,
                    retry_after=int(retry_after) if retry_after is not None else None,
                    limit_remaining=safe_int(headers.get("X-RateLimit-Remaining")) or 0,
                )
            if resp.status >= 400:
                error = FetchError(
                    message=f"SDMX fetch returned HTTP {resp.status}",
                    connector_id=self.connector_id,
                    request_params={"status_code": resp.status, "url": url},
                )
                error.status_code = resp.status  # type: ignore[attr-defined]
                raise error

            raw = await resp.read()
            try:
                body = _json.loads(raw)
            except _json.JSONDecodeError as exc:
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
            return body, headers, raw

    async def _sdmx_request_head(
        self,
        handle: ConnectionHandle,
        url: str,
    ) -> dict[str, str]:
        """SDMX HEAD request for freshness checks."""
        req_headers = self._sdmx_data_headers(handle.config)
        session = await self._get_session(handle)
        timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)
        async with session.head(url, headers=req_headers, timeout=timeout) as resp:
            return dict(resp.headers)


__all__ = ["SDMXSourceConnector"]
