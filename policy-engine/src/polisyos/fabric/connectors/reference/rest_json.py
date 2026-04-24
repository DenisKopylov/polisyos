"""
GenericRESTConnector - Reference implementation for paginated JSON REST APIs.

Capabilities
------------
FULL_FETCH            Fetch all pages of a paginated endpoint.
DATE_RANGE_FILTER     Injects date_start/date_end into query params.
INCREMENTAL_FETCH     Adds a "since" param for incremental fetches.
RATE_LIMIT_AWARE      Parses rate limit headers and raises RateLimitError on 429.

Design Decisions
----------------
* aiohttp is used for async I/O; no thread pool fallbacks.
* Pagination supports PAGE_NUMBER and CURSOR strategies.
* A dot-path extractor pulls data from nested JSON envelopes.
* Response JSON is parsed from raw bytes once (avoids double-read issues).
* Versioning uses ETag -> Last-Modified -> content hash -> now fallback.

Example ConnectionConfig
------------------------
>>> config_json = {
...     "url": "https://api.example.org/v2/indicators",
...     "headers": {
...         "Accept": "application/json",
...         "X-REST-DataPath": "data.items",
...         "X-REST-Pagination": "cursor",   # or "page_number"
...         "X-REST-PageSize": "100",
...         "X-REST-PageParam": "page",
...         "X-REST-CursorParam": "next_cursor",
...         "X-REST-DateStart": "start_date",
...         "X-REST-DateEnd": "end_date",
...     },
...     "auth_method": "bearer",
...     "auth_credentials": {"token": "sk-live-xxxxx"},
...     "timeout_seconds": 30,
...     "max_retries": 5,
...     "rate_limit_rps": 10.0,
... }
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.core.canon import streaming_hash
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
    with_rate_limit,
    with_retry,
)
from polisyos.fabric.connectors.resilience.rate_limiter import parse_retry_after_header
from polisyos.fabric.connectors.types import (
    ConfigurationError,
    FetchError,
    RateLimitError,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from polisyos.fabric.safety import (
    UnsafeDataPathError,
    extract_bounded_data_path,
    validate_data_path,
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

logger = get_logger(__name__)


def _parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except (TypeError, ValueError):
        logger.debug(
            "Failed to parse HTTP datetime value %r",
            value,
            exc_info=True,
        )
        return None


def _extract_nested(obj: Any, path: str | tuple[str, ...]) -> Any:
    """Resolve a dot-separated path through nested dicts/lists."""
    return extract_bounded_data_path(obj, path)


class PaginationStrategy(str, Enum):
    """Supported pagination schemes."""

    PAGE_NUMBER = "page_number"  # ?page=1&page=2 ...
    CURSOR = "cursor"  # response body contains a next-page token


class GenericRESTConnector(BaseConnector[list[dict[str, Any]]]):
    """Paginated JSON REST connector with auth, date filtering, and rate-limit awareness."""

    connector_id: ClassVar[str] = "reference.rest_json"
    _STATE_SESSION_KEY: ClassVar[str] = "session"
    _STATE_SESSION_LOCK_KEY: ClassVar[str] = "_session_lock"

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.INCREMENTAL_FETCH
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="rest_json",
        version="1.0.0",
        namespace="reference",
        source_name="Generic REST JSON API",
        source_organization="PolicyOS Reference",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.INCREMENTAL_FETCH,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    # ------------------------------------------------------------------
    # REST-specific config parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_rest_config(config: ConnectionConfig) -> dict[str, Any]:
        pagination_raw = config.headers.get("X-REST-Pagination", "page_number")
        try:
            pagination = PaginationStrategy(pagination_raw)
        except ValueError as exc:
            raise ConfigurationError(
                message=f"Unknown pagination strategy: {pagination_raw}",
                connector_id="reference.rest_json",
                field="X-REST-Pagination",
            ) from exc
        return {
            "data_path": validate_data_path(config.headers.get("X-REST-DataPath", "data")),
            "pagination": pagination,
            "page_size": int(config.headers.get("X-REST-PageSize", "100")),
            "page_param": config.headers.get("X-REST-PageParam", "page"),
            "page_size_param": config.headers.get("X-REST-PageSizeParam", "limit"),
            "cursor_param": config.headers.get("X-REST-CursorParam", "next_cursor"),
            "cursor_path": validate_data_path(config.headers.get("X-REST-CursorPath", "")),
            "date_start_param": config.headers.get("X-REST-DateStart", "start_date"),
            "date_end_param": config.headers.get("X-REST-DateEnd", "end_date"),
        }

    @staticmethod
    def _strip_internal_headers(headers: dict[str, str]) -> dict[str, str]:
        return {k: v for k, v in headers.items() if not k.startswith("X-REST-")}

    def _build_auth_headers(self, config: ConnectionConfig) -> dict[str, str]:
        headers = self._strip_internal_headers(config.headers)
        if config.auth_method == "bearer":
            token = config.auth_credentials.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif config.auth_method == "api_key":
            key_name = config.auth_credentials.get("header", "X-API-Key")
            headers[key_name] = config.auth_credentials.get("key", "")
        return headers

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        if not config.url:
            raise ConfigurationError(
                message="base_url is required",
                connector_id=self.connector_id,
                field="url",
            )
        handle = self._create_handle(config)
        handle.setdefault_state("rest_json", {})
        handle.set_state(self._STATE_SESSION_KEY, None)
        handle.set_state(self._STATE_SESSION_LOCK_KEY, asyncio.Lock())
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        lock = self._session_lock(handle)
        async with lock:
            session: aiohttp.ClientSession | None = handle.get_state(self._STATE_SESSION_KEY)
            if session is not None and not session.closed:
                await session.close()
            handle.set_state(self._STATE_SESSION_KEY, None)

    def _session_lock(self, handle: ConnectionHandle) -> asyncio.Lock:
        lock = handle.get_state(self._STATE_SESSION_LOCK_KEY)
        if isinstance(lock, asyncio.Lock):
            return lock
        lock = asyncio.Lock()
        handle.set_state(self._STATE_SESSION_LOCK_KEY, lock)
        return lock

    async def _get_session(self, handle: ConnectionHandle) -> aiohttp.ClientSession:
        lock = self._session_lock(handle)
        async with lock:
            session: aiohttp.ClientSession | None = handle.get_state(self._STATE_SESSION_KEY)
            if session is None or session.closed:
                timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)
                session = aiohttp.ClientSession(timeout=timeout)
                handle.set_state(self._STATE_SESSION_KEY, session)
            return session

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @with_retry(max_attempts=3, base_delay=1.0)
    @with_circuit_breaker()
    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        start = time.monotonic()
        headers = self._build_auth_headers(handle.config)
        try:
            session = await self._get_session(handle)
            async with session.get(handle.config.url, headers=headers) as resp:
                latency = (time.monotonic() - start) * 1000
                remaining = resp.headers.get("X-RateLimit-Remaining")
                return HealthStatus(
                    healthy=(resp.status < 400),
                    message=f"HTTP {resp.status}",
                    latency_ms=round(latency, 2),
                    rate_limit_remaining=int(remaining) if remaining else None,
                )
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    # ------------------------------------------------------------------
    # Core fetch with pagination loop
    # ------------------------------------------------------------------
    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict[str, Any]]]:
        cfg = self._parse_rest_config(handle.config)
        headers = self._build_auth_headers(handle.config)
        all_rows: list[dict[str, Any]] = []
        start = time.monotonic()
        total_bytes = 0
        payload_chunks: list[bytes] = []

        state = handle.setdefault_state("rest_json", {})
        state["rate_limit_remaining"] = None
        state["retry_after"] = None

        page_size = request.page_size or cfg["page_size"]

        params: dict[str, Any] = {cfg["page_size_param"]: page_size}
        if request.date_start:
            params[cfg["date_start_param"]] = request.date_start.isoformat()
        if request.date_end:
            params[cfg["date_end_param"]] = request.date_end.isoformat()
        if request.incremental_since:
            params["since"] = request.incremental_since.value
        for key, values in request.filters:
            if not values:
                continue
            params[key] = ",".join(str(value) for value in values)

        page_number = 1
        cursor: str | None = None
        has_more = True
        etag: str | None = None
        last_modified: str | None = None
        etag_mismatch = False
        last_modified_mismatch = False

        session = await self._get_session(handle)
        request_page = self._decorate_request(self._request_page_raw, handle)
        while has_more:
            if cfg["pagination"] == PaginationStrategy.PAGE_NUMBER:
                params[cfg["page_param"]] = str(page_number)
            elif cursor:
                params[cfg["cursor_param"]] = cursor

            body, resp_headers, bytes_xferred = await request_page(
                handle,
                session,
                handle.config.url,
                params,
                headers,
            )
            total_bytes += bytes_xferred
            payload_chunks.append(body["_raw"])

            page_etag = resp_headers.get("ETag")
            if page_etag:
                if etag is None:
                    etag = page_etag
                elif etag != page_etag:
                    etag_mismatch = True

            page_last_modified = resp_headers.get("Last-Modified")
            if page_last_modified:
                if last_modified is None:
                    last_modified = page_last_modified
                elif last_modified != page_last_modified:
                    last_modified_mismatch = True

            rl = resp_headers.get("X-RateLimit-Remaining")
            if rl is not None:
                try:
                    state["rate_limit_remaining"] = int(rl)
                except ValueError:
                    state["rate_limit_remaining"] = None

            try:
                page_data: list[dict[str, Any]] = _extract_nested(body["json"], cfg["data_path"])
            except (KeyError, TypeError) as exc:
                raise FetchError(
                    message=f"Data extraction failed at path '{cfg['data_path']}': {exc}",
                    connector_id=self.connector_id,
                    request_params={"data_path": cfg["data_path"]},
                ) from exc

            all_rows.extend(page_data)

            if not page_data:
                has_more = False
            elif cfg["pagination"] == PaginationStrategy.PAGE_NUMBER:
                page_number += 1
                has_more = len(page_data) >= page_size
            else:
                cursor = self._extract_cursor(body["json"], cfg)
                has_more = cursor is not None

        duration_ms = (time.monotonic() - start) * 1000
        version = self._build_version(
            content_hash=streaming_hash(payload_chunks, prefix=True),
            etag=etag if not etag_mismatch else None,
            last_modified=last_modified if not last_modified_mismatch else None,
            fetched_at=datetime.now(UTC),
        )

        return FetchResult(
            data=all_rows,
            row_count=len(all_rows),
            schema_id=f"{self.connector_id}.{request.dataset_id}",
            schema_version="1.0.0",
            version=version,
            fetched_at=datetime.now(UTC),
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
            fetch_duration_ms=round(duration_ms, 2),
            bytes_transferred=total_bytes,
        )

    def _extract_cursor(self, body: dict[str, Any], cfg: dict[str, Any]) -> str | None:
        cursor_path = cfg.get("cursor_path") or ""
        if cursor_path:
            try:
                cursor_value = _extract_nested(body, cursor_path)
            except KeyError:
                cursor_value = None
        else:
            cursor_value = body.get(cfg["cursor_param"])
        if cursor_value is None:
            return None
        return str(cursor_value)

    def _build_version(
        self,
        *,
        content_hash: str,
        etag: str | None,
        last_modified: str | None,
        fetched_at: datetime,
    ) -> DataVersion:
        if etag:
            return DataVersion(
                strategy=VersionStrategy.ETAG,
                value=etag,
                timestamp=fetched_at,
                content_hash=content_hash,
            )

        parsed_last_modified = _parse_http_datetime(last_modified)
        if last_modified:
            timestamp = parsed_last_modified or fetched_at
            value = parsed_last_modified.isoformat() if parsed_last_modified else last_modified
            return DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=value,
                timestamp=timestamp,
                content_hash=content_hash,
            )

        return DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=content_hash,
            timestamp=fetched_at,
            content_hash=content_hash,
        )

    def _decorate_request(self, func: Any, handle: ConnectionHandle) -> Any:
        wrapped = func
        rate_limit_rps = handle.config.rate_limit_rps
        if rate_limit_rps:
            wrapped = with_rate_limit(rate_limit_rps=rate_limit_rps)(wrapped)
        wrapped = with_circuit_breaker()(wrapped)
        wrapped = with_retry(max_attempts=5, base_delay=1.0)(wrapped)
        return wrapped

    async def _request_page_raw(
        self,
        handle: ConnectionHandle,
        session: aiohttp.ClientSession,
        url: str,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str], int]:
        async with session.get(
            url,
            params=params,
            headers=headers,
        ) as resp:
            headers = dict(resp.headers)
            if resp.status == 429:
                retry_after_header = resp.headers.get("Retry-After")
                retry_after = parse_retry_after_header(retry_after_header)
                state = handle.setdefault_state("rest_json", {})
                state["retry_after"] = retry_after
                rl = resp.headers.get("X-RateLimit-Remaining")
                if rl is not None:
                    try:
                        state["rate_limit_remaining"] = int(rl)
                    except ValueError:
                        state["rate_limit_remaining"] = None
                raise RateLimitError(
                    connector_id=self.connector_id,
                    retry_after=int(retry_after) if retry_after is not None else None,
                    limit_remaining=int(resp.headers.get("X-RateLimit-Remaining", 0) or 0),
                )

            if resp.status != 200:
                error = FetchError(
                    message=f"HTTP {resp.status}",
                    connector_id=self.connector_id,
                    request_params={"status_code": resp.status, "url": url},
                )
                error.status_code = resp.status  # type: ignore[attr-defined]
                raise error

            raw = await resp.read()
            bytes_xferred = len(raw)
            try:
                body_json = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FetchError(
                    message=f"JSON decode failed: {exc}",
                    connector_id=self.connector_id,
                    request_params={"url": url},
                ) from exc

        return (
            {
                "json": body_json,
                "_raw": raw,
                "headers": headers,
            },
            headers,
            bytes_xferred,
        )

    # ------------------------------------------------------------------
    # Config validation
    # ------------------------------------------------------------------
    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not config.url:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="url (base_url) is required",
                    field="url",
                )
            )
        pagination = config.headers.get("X-REST-Pagination", "page_number")
        if pagination not in ("page_number", "cursor"):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Unknown pagination strategy: {pagination}",
                    field="X-REST-Pagination",
                )
            )
        for field_name, header_name, default in (
            ("data_path", "X-REST-DataPath", "data"),
            ("cursor_path", "X-REST-CursorPath", ""),
        ):
            try:
                validate_data_path(config.headers.get(header_name, default))
            except UnsafeDataPathError as exc:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=str(exc),
                        field=field_name,
                    )
                )
        if issues:
            return ValidationResult.failure(*issues)
        return ValidationResult.success()
