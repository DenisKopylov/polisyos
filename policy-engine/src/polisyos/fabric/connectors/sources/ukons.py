from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from typing import Any, AsyncIterator, ClassVar, Iterable

import aiohttp
import pandas as pd

from polisyos.core.canon import content_hash as compute_content_hash
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
from polisyos.fabric.connectors.sources._contracts.ukons_contracts import UKONS_GENERIC_SCHEMA
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


class UKONSConnector(BaseConnector[pd.DataFrame]):
    """Connector for UK ONS API v1."""

    namespace: ClassVar[str] = "ukons"
    short_id: ClassVar[str] = "datasets"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://api.ons.gov.uk"

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="UK Office for National Statistics API",
        source_organization="Office for National Statistics",
        source_url=_BASE_URL,
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.GOLD,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
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
        url = f"{base_url}/dataset"
        started = datetime.now(timezone.utc)
        try:
            async with session.get(url, params={"limit": "1"}) as response:
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
        url = f"{base_url}/dataset"
        payload, _headers, _raw = await self._request_json(
            session,
            url,
            params={"limit": "50"},
            connector_id=self.connector_id,
        )
        for row in _extract_dataset_rows(payload):
            dataset_id = row.get("id")
            if not isinstance(dataset_id, str):
                continue
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=str(row.get("title") or dataset_id),
                description=str(row.get("description") or ""),
                tags=("ukons", "ons"),
                metadata={
                    "release": row.get("release"),
                    "links": row.get("links"),
                },
            )

    @with_retry(max_attempts=3, base_delay=1.5)
    @with_circuit_breaker()
    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        session = await self._get_session(handle)
        base_url = handle.state.get("base_url", self._BASE_URL)
        dataset_id = request.dataset_id
        url = f"{base_url}/dataset/{dataset_id}/observations"
        params = self._build_params(request)
        payload, headers, raw = await self._request_json(
            session,
            url,
            params=params,
            connector_id=self.connector_id,
        )
        frame = self._parse_observations(payload, dataset_id)
        now = datetime.now(timezone.utc)
        content_hash = compute_content_hash(raw, prefix=True)
        version, source_updated_at = _build_version(
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
            content_hash=content_hash,
            fetched_at=now,
        )

        return FetchResult(
            data=frame,
            row_count=len(frame),
            schema_id=UKONS_GENERIC_SCHEMA.schema_id,
            schema_version=str(UKONS_GENERIC_SCHEMA.version),
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
        return UKONS_GENERIC_SCHEMA.model_dump(mode="python")

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
        params: dict[str, str] = {}
        for key, values in request.filters:
            if values:
                params[key] = ",".join(values)
        if request.date_start is not None and request.date_end is not None and "time" not in params:
            params["time"] = f"{request.date_start.date()}/{request.date_end.date()}"
        return params

    @staticmethod
    def _parse_observations(payload: dict[str, Any], dataset_id: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        observations = payload.get("observations", [])
        iterable: Iterable[Any]
        if isinstance(observations, dict):
            iterable = observations.values()
        elif isinstance(observations, list):
            iterable = observations
        else:
            iterable = ()

        for row in iterable:
            if not isinstance(row, dict):
                continue
            dimensions = _extract_dimensions(row.get("dimensions"))
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "observation": _safe_float(row.get("observation")),
                    "time_period": dimensions.get("time") or dimensions.get("Time"),
                    "geography": dimensions.get("geography") or dimensions.get("Geography"),
                    "dimensions_json": json.dumps(
                        dimensions,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )

        if not rows:
            return pd.DataFrame(columns=UKONS_GENERIC_SCHEMA.field_names())
        return pd.DataFrame(rows, columns=UKONS_GENERIC_SCHEMA.field_names())

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
                body = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FetchError(
                    message=f"Invalid JSON response: {exc}",
                    connector_id=connector_id,
                    request_params={"url": url},
                ) from exc
            if not isinstance(body, dict):
                raise FetchError(
                    message="Unexpected payload type (expected object)",
                    connector_id=connector_id,
                    request_params={"url": url},
                )
            return body, headers, raw


def _extract_dataset_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "datasets", "links"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _extract_dimensions(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(raw) for key, raw in value.items() if raw is not None}
    if isinstance(value, list):
        result: dict[str, str] = {}
        for row in value:
            if not isinstance(row, dict):
                continue
            key = row.get("dimension_id") or row.get("id") or row.get("name")
            raw_value = row.get("option_id") or row.get("value") or row.get("label")
            if key is None or raw_value is None:
                continue
            result[str(key)] = str(raw_value)
        return result
    return {}


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


__all__ = ["UKONSConnector"]
