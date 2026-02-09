from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from typing import Any, AsyncIterator, ClassVar

import aiohttp
import pandas as pd

from polisyos.core.canon import streaming_hash
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
from polisyos.fabric.connectors.sources._contracts.world_bank_contracts import WDI_GENERIC_SCHEMA
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


class WorldBankConnector(BaseConnector[pd.DataFrame]):
    """Production connector for World Bank Indicators API v2."""

    namespace: ClassVar[str] = "worldbank"
    short_id: ClassVar[str] = "wdi"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://api.worldbank.org/v2"

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

    @with_retry(max_attempts=3, base_delay=1.0)
    @with_circuit_breaker()
    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        session = await self._get_session(handle)
        base_url = handle.state.get("base_url", self._BASE_URL)
        url = f"{base_url}/country/US/indicator/NY.GDP.MKTP.CD"
        params = {"format": "json", "per_page": "1"}
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
        session = await self._get_session(handle)
        base_url = handle.state.get("base_url", self._BASE_URL)
        url = f"{base_url}/indicator"
        params = {"format": "json", "per_page": "200", "page": "1"}
        body, _headers, _raw = await self._request_json(
            session,
            url,
            params=params,
            connector_id=self.connector_id,
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

    @with_retry(max_attempts=3, base_delay=1.0)
    @with_circuit_breaker()
    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        session = await self._get_session(handle)
        base_url = handle.state.get("base_url", self._BASE_URL)
        indicator_id = request.dataset_id
        countries = self._parse_countries(request)
        date_range = self._parse_date_range(request)

        payload_chunks: list[bytes] = []
        all_records: list[dict[str, Any]] = []
        bytes_transferred = 0
        pages = 1
        page = 1
        etag: str | None = None
        last_modified: str | None = None

        while page <= pages:
            url = f"{base_url}/country/{countries}/indicator/{indicator_id}"
            params: dict[str, str] = {"format": "json", "per_page": "1000", "page": str(page)}
            if date_range:
                params["date"] = date_range

            body, headers, raw = await self._request_json(
                session,
                url,
                params=params,
                connector_id=self.connector_id,
            )
            payload_chunks.append(raw)
            bytes_transferred += len(raw)

            current_etag = headers.get("ETag")
            if etag is None:
                etag = current_etag
            elif current_etag is not None and current_etag != etag:
                etag = None

            current_last_modified = headers.get("Last-Modified")
            if last_modified is None:
                last_modified = current_last_modified
            elif current_last_modified is not None and current_last_modified != last_modified:
                last_modified = None

            if not isinstance(body, list) or len(body) < 2:
                raise FetchError(
                    message=f"Unexpected response format for indicator {indicator_id}",
                    connector_id=self.connector_id,
                    dataset_id=indicator_id,
                )

            meta = body[0] if isinstance(body[0], dict) else {}
            rows = body[1] if isinstance(body[1], list) else []
            pages = max(1, _safe_int(meta.get("pages")) or 1)
            for row in rows:
                if isinstance(row, dict):
                    all_records.append(row)
            page += 1

        frame = self._normalize_records(all_records, indicator_id)
        now = datetime.now(timezone.utc)
        content_hash = streaming_hash(payload_chunks, prefix=True)
        version, source_updated_at = _build_version(
            etag=etag,
            last_modified=last_modified,
            content_hash=content_hash,
            fetched_at=now,
        )

        return FetchResult(
            data=frame,
            row_count=len(frame),
            schema_id=WDI_GENERIC_SCHEMA.schema_id,
            schema_version=str(WDI_GENERIC_SCHEMA.version),
            version=version,
            fetched_at=now,
            source_updated_at=source_updated_at,
            completeness=_frame_completeness(frame),
            quality_tier=QualityTier.GOLD,
            bytes_transferred=bytes_transferred,
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        del handle, dataset_id
        return WDI_GENERIC_SCHEMA.model_dump(mode="python")

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
                    "year": _safe_int(row.get("date")),
                    "value": _safe_float(row.get("value")),
                    "unit": row.get("unit"),
                    "decimal": _safe_int(row.get("decimal")),
                }
            )

        frame = pd.DataFrame(rows, columns=WDI_GENERIC_SCHEMA.field_names())
        if frame.empty:
            return pd.DataFrame(columns=WDI_GENERIC_SCHEMA.field_names())
        return frame

    @staticmethod
    async def _request_json(
        session: aiohttp.ClientSession,
        url: str,
        *,
        params: dict[str, str],
        connector_id: str,
    ) -> tuple[Any, dict[str, str], bytes]:
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
                body = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FetchError(
                    message=f"Invalid JSON response: {exc}",
                    connector_id=connector_id,
                    request_params={"url": url},
                ) from exc
            return body, headers, raw


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
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


__all__ = ["WorldBankConnector"]
