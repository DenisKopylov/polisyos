from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from typing import Any, AsyncIterator, ClassVar

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
from polisyos.fabric.connectors.resilience import with_circuit_breaker, with_retry
from polisyos.fabric.connectors.resilience.rate_limiter import parse_retry_after_header
from polisyos.fabric.connectors.sources._contracts.eurostat_contracts import EUROSTAT_GENERIC_SCHEMA
from polisyos.fabric.connectors.types import (
    DatasetDescriptor,
    FetchError,
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
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


class EurostatConnector(BaseConnector[pd.DataFrame]):
    """Connector for Eurostat JSON Statistics API."""

    namespace: ClassVar[str] = "eurostat"
    short_id: ClassVar[str] = "data"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    )

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
        source_name="Eurostat Statistics Database",
        source_organization="European Commission - Eurostat",
        source_url="https://ec.europa.eu/eurostat/",
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

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = self._create_handle(config)
        handle.state["base_url"] = config.url or self._BASE_URL
        handle.state["session"] = None
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        session: aiohttp.ClientSession | None = handle.state.get("session")
        if session is not None and not session.closed:
            await session.close()
        handle.state["session"] = None

    @with_retry(max_attempts=3, base_delay=1.5)
    @with_circuit_breaker()
    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        session = await self._get_session(handle)
        base_url = handle.state.get("base_url", self._BASE_URL)
        dataset = handle.config.headers.get("X-EUROSTAT-HEALTH-DATASET", "nama_10_gdp")
        url = f"{base_url}/{dataset}"
        params = {"format": "JSON", "lang": "en"}
        started = datetime.now(timezone.utc)
        try:
            async with session.get(url, params=params) as response:
                latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
                return HealthStatus(
                    healthy=response.status < 400,
                    message=f"HTTP {response.status}",
                    latency_ms=latency_ms,
                    rate_limit_remaining=_safe_int(response.headers.get("X-RateLimit-Remaining")),
                )
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    async def list_datasets(
        self,
        handle: ConnectionHandle,
    ) -> AsyncIterator[DatasetDescriptor]:
        configured = handle.config.headers.get("X-EUROSTAT-DATASETS", "")
        for raw in configured.split(","):
            dataset_id = raw.strip()
            if not dataset_id:
                continue
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=dataset_id,
                description="Configured Eurostat dataset",
                tags=("eurostat", "configured"),
            )

    @with_retry(max_attempts=3, base_delay=2.0)
    @with_circuit_breaker()
    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        session = await self._get_session(handle)
        base_url = handle.state.get("base_url", self._BASE_URL)
        dataset_id = request.dataset_id
        url = f"{base_url}/{dataset_id}"

        params = self._build_params(request)
        body, headers, raw = await self._request_json(
            session,
            url,
            params=params,
            connector_id=self.connector_id,
        )
        frame = self._parse_jsonstat(body, dataset_id)
        now = datetime.now(timezone.utc)
        content_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        version, source_updated_at = _build_version(
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
            content_hash=content_hash,
            fetched_at=now,
        )

        return FetchResult(
            data=frame,
            row_count=len(frame),
            schema_id=EUROSTAT_GENERIC_SCHEMA.schema_id,
            schema_version=str(EUROSTAT_GENERIC_SCHEMA.version),
            version=version,
            fetched_at=now,
            source_updated_at=source_updated_at,
            completeness=_frame_completeness(frame),
            quality_tier=QualityTier.GOLD,
            bytes_transferred=len(raw),
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        del handle, dataset_id
        return EUROSTAT_GENERIC_SCHEMA.model_dump(mode="python")

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not config.url and not cls._BASE_URL:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="URL is required",
                    field="url",
                )
            )
        if issues:
            return ValidationResult.failure(*issues)
        return ValidationResult.success()

    async def _get_session(self, handle: ConnectionHandle) -> aiohttp.ClientSession:
        session: aiohttp.ClientSession | None = handle.state.get("session")
        if session is None or session.closed:
            timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)
            session = aiohttp.ClientSession(timeout=timeout)
            handle.state["session"] = session
        return session

    @staticmethod
    def _build_params(request: FetchRequest) -> dict[str, str]:
        params: dict[str, str] = {"format": "JSON", "lang": "en"}
        for key, values in request.filters:
            if values:
                params[key] = ",".join(values)
        if request.date_start is not None and request.date_end is not None and "time" not in params:
            years = [str(year) for year in range(request.date_start.year, request.date_end.year + 1)]
            params["time"] = ",".join(years)
        return params

    @staticmethod
    def _parse_jsonstat(body: dict[str, Any], dataset_id: str) -> pd.DataFrame:
        dim_ids = body.get("id", [])
        dim_sizes = body.get("size", [])
        dimensions = body.get("dimension", {})
        values_any = body.get("value", {})

        if not isinstance(dim_ids, list) or not isinstance(dim_sizes, list):
            return pd.DataFrame(columns=EUROSTAT_GENERIC_SCHEMA.field_names())

        dimension_codes: dict[str, list[str]] = {}
        for dim_id in dim_ids:
            info = dimensions.get(dim_id, {})
            if not isinstance(info, dict):
                info = {}
            dimension_codes[str(dim_id)] = _dimension_codes(info)

        observations: list[tuple[int, Any]] = []
        if isinstance(values_any, dict):
            for key, value in values_any.items():
                try:
                    idx = int(key)
                except (TypeError, ValueError):
                    continue
                observations.append((idx, value))
        elif isinstance(values_any, list):
            observations = list(enumerate(values_any))
        else:
            observations = []

        rows: list[dict[str, Any]] = []
        for idx, raw_value in observations:
            coords = _decode_index(idx, dim_sizes)
            dim_values: dict[str, str] = {}
            for dim_pos, dim_id in enumerate(dim_ids):
                codes = dimension_codes.get(str(dim_id), [])
                coord = coords[dim_pos] if dim_pos < len(coords) else 0
                if 0 <= coord < len(codes):
                    dim_values[str(dim_id)] = codes[coord]
                else:
                    dim_values[str(dim_id)] = str(coord)

            rows.append(
                {
                    "dataset_id": dataset_id,
                    "observation_index": idx,
                    "time_period": dim_values.get("time") or dim_values.get("TIME_PERIOD"),
                    "unit": dim_values.get("unit"),
                    "value": _safe_float(raw_value),
                    "dimensions_json": json.dumps(
                        dim_values,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )

        if not rows:
            return pd.DataFrame(columns=EUROSTAT_GENERIC_SCHEMA.field_names())
        return pd.DataFrame(rows, columns=EUROSTAT_GENERIC_SCHEMA.field_names())

    @staticmethod
    async def _request_json(
        session: aiohttp.ClientSession,
        url: str,
        *,
        params: dict[str, str],
        connector_id: str,
    ) -> tuple[dict[str, Any], dict[str, str], bytes]:
        async with session.get(url, params=params) as response:
            headers = dict(response.headers)
            if response.status == 429:
                retry_after = _retry_after_seconds(headers)
                raise RateLimitError(
                    connector_id=connector_id,
                    retry_after=int(retry_after) if retry_after is not None else None,
                    limit_remaining=_safe_int(headers.get("X-RateLimit-Remaining")) or 0,
                )
            if response.status >= 400:
                error = FetchError(
                    message=f"HTTP {response.status}",
                    connector_id=connector_id,
                    request_params={"url": url, "status": response.status},
                )
                error.status_code = response.status  # type: ignore[attr-defined]
                raise error
            raw = await response.read()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FetchError(
                    message=f"Invalid JSON response: {exc}",
                    connector_id=connector_id,
                    request_params={"url": url},
                ) from exc
            if not isinstance(payload, dict):
                raise FetchError(
                    message="Unexpected payload type (expected object)",
                    connector_id=connector_id,
                    request_params={"url": url},
                )
            return payload, headers, raw


def _dimension_codes(info: dict[str, Any]) -> list[str]:
    category = info.get("category", {})
    if not isinstance(category, dict):
        return []
    index = category.get("index", {})
    labels = category.get("label", {})

    if isinstance(index, dict):
        ordered_keys = [key for key, _ in sorted(index.items(), key=lambda item: int(item[1]))]
    elif isinstance(index, list):
        ordered_keys = [str(value) for value in index]
    else:
        ordered_keys = []

    if not ordered_keys and isinstance(labels, dict):
        ordered_keys = sorted(str(key) for key in labels)

    resolved: list[str] = []
    for key in ordered_keys:
        if isinstance(labels, dict) and key in labels:
            resolved.append(str(labels[key]))
        else:
            resolved.append(str(key))
    return resolved


def _decode_index(index: int, sizes: list[Any]) -> list[int]:
    if not sizes:
        return []
    coords = [0] * len(sizes)
    remaining = int(index)
    for pos in range(len(sizes) - 1, -1, -1):
        try:
            size = int(sizes[pos])
        except (TypeError, ValueError):
            size = 1
        size = max(size, 1)
        coords[pos] = remaining % size
        remaining //= size
    return coords


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _frame_completeness(frame: pd.DataFrame) -> float:
    if frame.size == 0:
        return 1.0
    null_ratio = float(frame.isna().sum().sum()) / float(frame.size)
    return 1.0 - null_ratio


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    retry_after = parse_retry_after_header(headers.get("Retry-After"))
    if retry_after is not None:
        return retry_after

    reset = headers.get("X-RateLimit-Reset")
    if reset is None:
        return None
    try:
        reset_ts = float(reset)
    except (TypeError, ValueError):
        return None
    now_ts = datetime.now(timezone.utc).timestamp()
    return max(0.0, reset_ts - now_ts)


def _build_version(
    *,
    etag: str | None,
    last_modified: str | None,
    content_hash: str,
    fetched_at: datetime,
) -> tuple[DataVersion, datetime | None]:
    source_updated_at = _parse_http_datetime(last_modified)
    if etag:
        return (
            DataVersion(
                strategy=VersionStrategy.ETAG,
                value=etag,
                timestamp=fetched_at,
                content_hash=content_hash,
            ),
            source_updated_at,
        )
    if source_updated_at is not None:
        return (
            DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=source_updated_at.isoformat(),
                timestamp=source_updated_at,
                content_hash=content_hash,
            ),
            source_updated_at,
        )
    return (
        DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=content_hash,
            timestamp=fetched_at,
            content_hash=content_hash,
        ),
        source_updated_at,
    )


def _parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = ["EurostatConnector"]
