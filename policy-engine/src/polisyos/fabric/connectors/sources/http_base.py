"""Shared HTTP runtime used by production Fabric connectors."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Generic, Protocol, TypeVar, cast

import aiohttp

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchResult,
)
from polisyos.fabric.connectors.resilience import (
    CircuitBreakerConfig,
    ResilienceConfig,
    RetryPolicy,
    apply_resilience,
)
from polisyos.fabric.connectors.sources.http_common import (
    build_data_version,
    quality_flags_from_source_metadata,
    read_bounded_response_body,
    retry_after_seconds,
    safe_int,
)
from polisyos.fabric.connectors.types import (
    FetchError,
    RateLimitError,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from polisyos.ir.connectors import QualityTier, ResilienceInfo

DataT = TypeVar("DataT")
_RAW_HTTP_RESPONSE_OBSERVER_STATE_KEY = "_raw_http_response_observer"


class RawHTTPResponseObserver(Protocol):
    """Observe bounded HTTP attempts and exact response bytes before interpretation."""

    @property
    def max_response_bytes(self) -> int:
        """Maximum encoded response bytes authorized for this execution."""
        ...

    @property
    def max_decompressed_bytes(self) -> int:
        """Maximum decoded response bytes authorized for this execution."""
        ...

    def before_request(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
    ) -> None:
        """Authorize one network attempt before ``session.get`` is called."""
        ...

    def on_raw_response(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
        status_code: int,
        response_headers: Mapping[str, str],
        body: bytes,
    ) -> None:
        """Persist one bounded response witness before status or JSON interpretation."""
        ...


def _install_raw_http_response_observer(
    handle: ConnectionHandle,
    observer: RawHTTPResponseObserver,
) -> None:
    handle.set_state(_RAW_HTTP_RESPONSE_OBSERVER_STATE_KEY, observer)


def _remove_raw_http_response_observer(handle: ConnectionHandle) -> None:
    handle.pop_state(_RAW_HTTP_RESPONSE_OBSERVER_STATE_KEY, None)


def _raw_http_response_observer(
    handle: ConnectionHandle,
) -> RawHTTPResponseObserver | None:
    observer = handle.get_state(_RAW_HTTP_RESPONSE_OBSERVER_STATE_KEY)
    if observer is None:
        return None
    return cast("RawHTTPResponseObserver", observer)


def _raise_for_http_status(
    *,
    connector_id: str,
    url: str,
    status_code: int,
    headers: Mapping[str, str],
) -> None:
    if status_code == 429:
        retry_after = retry_after_seconds(headers)
        raise RateLimitError(
            connector_id=connector_id,
            retry_after=int(retry_after) if retry_after is not None else None,
            limit_remaining=safe_int(headers.get("X-RateLimit-Remaining")) or 0,
        )
    if status_code >= 400:
        error = FetchError(
            message=f"HTTP {status_code}",
            connector_id=connector_id,
            request_params={"url": url, "status": status_code},
        )
        error.status_code = status_code  # type: ignore[attr-defined]
        raise error


def _observer_byte_limit(observer: RawHTTPResponseObserver, field_name: str) -> int:
    value = getattr(observer, field_name, None)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"raw HTTP observer {field_name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class HTTPResilienceProfile:
    """Retry, rate-limit, and circuit-breaker defaults for HTTP connectors.

    The profile captures source-specific resilience defaults that sit on top of
    per-connection overrides from ``ConnectionConfig``.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    jitter_max: float = 0.5
    max_delay: float = 60.0
    rate_limit_rps: float | None = None
    adaptive_rate_limit: bool = False
    circuit_breaker: CircuitBreakerConfig | None = field(default_factory=CircuitBreakerConfig)
    max_response_bytes: int = 10 * 1024 * 1024
    max_json_bytes: int = 5 * 1024 * 1024
    max_decompressed_bytes: int = 25 * 1024 * 1024
    max_rows: int = 200_000


class HTTPConnectorBase(BaseConnector[DataT], Generic[DataT]):
    """Shared runtime for HTTP/JSON connector implementations.

    Provides authenticated request execution, resilient retry / rate-limit
    handling, session lifecycle management, and normalized ``FetchResult``
    construction for concrete source connectors.
    """

    _BASE_URL: ClassVar[str] = ""
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile()

    _STATE_BASE_URL_KEY: ClassVar[str] = "base_url"
    _STATE_SESSION_KEY: ClassVar[str] = "session"
    _STATE_SESSION_LOCK_KEY: ClassVar[str] = "_session_lock"
    _STATE_JSON_EXECUTOR_KEY: ClassVar[str] = "_http_json_executor"
    _STATE_JSON_EXECUTOR_CONFIG_KEY: ClassVar[str] = "_http_json_executor_config"
    _READ_CHUNK_SIZE: ClassVar[int] = 64 * 1024

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = self._create_handle(config)
        handle.set_state(self._STATE_BASE_URL_KEY, config.url or self._BASE_URL)
        handle.set_state(self._STATE_SESSION_KEY, None)
        handle.set_state(self._STATE_SESSION_LOCK_KEY, asyncio.Lock())
        handle.set_state(self._STATE_JSON_EXECUTOR_KEY, None)
        handle.set_state(self._STATE_JSON_EXECUTOR_CONFIG_KEY, None)
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        lock = self._session_lock(handle)
        async with lock:
            session: aiohttp.ClientSession | None = handle.get_state(self._STATE_SESSION_KEY)
            if session is not None and not session.closed:
                await session.close()
            handle.set_state(self._STATE_SESSION_KEY, None)
        handle.set_state(self._STATE_JSON_EXECUTOR_KEY, None)
        handle.set_state(self._STATE_JSON_EXECUTOR_CONFIG_KEY, None)

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

    def _base_url(self, handle: ConnectionHandle) -> str:
        return str(handle.get_state(self._STATE_BASE_URL_KEY) or self._BASE_URL)

    async def _get_session(self, handle: ConnectionHandle) -> aiohttp.ClientSession:
        lock = self._session_lock(handle)
        async with lock:
            session: aiohttp.ClientSession | None = handle.get_state(self._STATE_SESSION_KEY)
            if session is None or session.closed:
                timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)
                session = aiohttp.ClientSession(timeout=timeout)
                handle.set_state(self._STATE_SESSION_KEY, session)
            return session

    def _session_lock(self, handle: ConnectionHandle) -> asyncio.Lock:
        lock = handle.get_state(self._STATE_SESSION_LOCK_KEY)
        if isinstance(lock, asyncio.Lock):
            return lock
        lock = asyncio.Lock()
        handle.set_state(self._STATE_SESSION_LOCK_KEY, lock)
        return lock

    def _retry_policy(self, handle: ConnectionHandle) -> RetryPolicy:
        profile = self.resilience_profile
        max_attempts = max(1, int(handle.config.max_retries))
        base_delay = (
            float(handle.config.retry_delay_seconds)
            if handle.config.retry_delay_seconds > 0
            else profile.base_delay
        )
        return RetryPolicy(
            max_attempts=max_attempts,
            base_delay=base_delay,
            backoff_factor=profile.backoff_factor,
            jitter_max=profile.jitter_max,
            max_delay=profile.max_delay,
        )

    def _rate_limit_rps(self, handle: ConnectionHandle) -> float | None:
        if handle.config.rate_limit_rps is not None:
            return handle.config.rate_limit_rps
        return self.resilience_profile.rate_limit_rps

    def _resilience_cache_key(self, handle: ConnectionHandle) -> tuple[Any, ...]:
        profile = self.resilience_profile
        cb = profile.circuit_breaker
        cb_key: tuple[Any, ...] | None = None
        if cb is not None:
            cb_key = (
                cb.failure_threshold,
                cb.success_threshold,
                cb.timeout_seconds,
                cb.half_open_max_calls,
                cb.window_size_seconds,
                cb.min_throughput,
            )
        return (
            handle.config.max_retries,
            handle.config.retry_delay_seconds,
            self._rate_limit_rps(handle),
            profile.backoff_factor,
            profile.jitter_max,
            profile.max_delay,
            profile.adaptive_rate_limit,
            cb_key,
        )

    def _resilience_config(self, handle: ConnectionHandle) -> ResilienceConfig:
        profile = self.resilience_profile
        return ResilienceConfig(
            retry_policy=self._retry_policy(handle),
            circuit_breaker=profile.circuit_breaker,
            rate_limit_rps=self._rate_limit_rps(handle),
            adaptive_rate_limit=profile.adaptive_rate_limit,
            inherit_connection_config=False,
        )

    def _json_executor(self, handle: ConnectionHandle) -> Callable[..., Any]:
        cached_key = handle.get_state(self._STATE_JSON_EXECUTOR_CONFIG_KEY)
        key = self._resilience_cache_key(handle)
        cached = handle.get_state(self._STATE_JSON_EXECUTOR_KEY)
        if cached is not None and cached_key == key:
            return cached

        async def _raw_request(
            *,
            handle: ConnectionHandle,
            session: aiohttp.ClientSession,
            url: str,
            params: dict[str, str],
            connector_id: str,
            headers: dict[str, str] | None = None,
        ) -> tuple[Any, dict[str, str], bytes]:
            request_kwargs: dict[str, Any] = {
                "params": params,
                "connector_id": connector_id,
            }
            if headers:
                request_kwargs["headers"] = headers
            observer = _raw_http_response_observer(handle)
            if observer is not None:
                request_kwargs["raw_http_response_observer"] = observer
            return await self._request_json(session, url, **request_kwargs)

        wrapped = apply_resilience(
            _raw_request,
            config=self._resilience_config(handle),
        )
        handle.set_state(self._STATE_JSON_EXECUTOR_KEY, wrapped)
        handle.set_state(self._STATE_JSON_EXECUTOR_CONFIG_KEY, key)
        return wrapped

    async def _resilient_request_json(
        self,
        handle: ConnectionHandle,
        url: str,
        *,
        params: dict[str, str],
        connector_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any, dict[str, str], bytes]:
        session = await self._get_session(handle)
        executor = self._json_executor(handle)
        request_headers = self._build_auth_headers(handle, headers)
        kwargs: dict[str, Any] = {
            "handle": handle,
            "session": session,
            "url": url,
            "params": params,
            "connector_id": connector_id or self.connector_id,
        }
        if request_headers:
            kwargs["headers"] = request_headers
        return await executor(
            **kwargs,
        )

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        params: dict[str, str],
        connector_id: str,
        headers: dict[str, str] | None = None,
        raw_http_response_observer: RawHTTPResponseObserver | None = None,
    ) -> tuple[Any, dict[str, str], bytes]:
        max_response_bytes = self.resilience_profile.max_response_bytes
        max_decompressed_bytes = self.resilience_profile.max_decompressed_bytes
        if raw_http_response_observer is not None:
            max_response_bytes = min(
                max_response_bytes,
                _observer_byte_limit(raw_http_response_observer, "max_response_bytes"),
            )
            max_decompressed_bytes = min(
                max_decompressed_bytes,
                _observer_byte_limit(
                    raw_http_response_observer,
                    "max_decompressed_bytes",
                ),
            )
            raw_http_response_observer.before_request(connector_id, url, dict(params))
        async with session.get(url, params=params, headers=headers) as response:
            headers = dict(response.headers)
            on_progress: Callable[[int], None] | None = None
            if raw_http_response_observer is not None:
                response_headers_observer = getattr(
                    raw_http_response_observer,
                    "on_response_headers",
                    None,
                )
                if callable(response_headers_observer):
                    response_headers_observer(
                        connector_id,
                        url,
                        dict(params),
                        response.status,
                        dict(headers),
                    )
                body_progress_observer = getattr(
                    raw_http_response_observer,
                    "on_body_progress",
                    None,
                )
                if callable(body_progress_observer):

                    def _report_progress(bytes_read: int) -> None:
                        body_progress_observer(
                            connector_id,
                            url,
                            dict(params),
                            bytes_read,
                        )

                    on_progress = _report_progress
            if raw_http_response_observer is None:
                _raise_for_http_status(
                    connector_id=connector_id,
                    url=url,
                    status_code=response.status,
                    headers=headers,
                )
            before_classification: Callable[[bytes], None] | None = None
            if raw_http_response_observer is not None:

                def _persist_raw_before_classification(body: bytes) -> None:
                    raw_http_response_observer.on_raw_response(
                        connector_id,
                        url,
                        dict(params),
                        response.status,
                        dict(headers),
                        body,
                    )

                before_classification = _persist_raw_before_classification
            raw = await self._read_response_body(
                response,
                connector_id=connector_id,
                url=url,
                max_response_bytes=max_response_bytes,
                max_decompressed_bytes=max_decompressed_bytes,
                before_classification=before_classification,
                on_progress=on_progress,
            )
            if raw_http_response_observer is not None:
                _raise_for_http_status(
                    connector_id=connector_id,
                    url=url,
                    status_code=response.status,
                    headers=headers,
                )

            if len(raw) > self.resilience_profile.max_json_bytes:
                raise FetchError(
                    message=(
                        "JSON response body exceeds safe limit "
                        f"({len(raw)} > {self.resilience_profile.max_json_bytes} bytes)"
                    ),
                    connector_id=connector_id,
                    request_params={"url": url},
                )
            try:
                body = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FetchError(
                    message=f"Invalid JSON response: {exc}",
                    connector_id=connector_id,
                    request_params={"url": url},
                ) from exc
            if isinstance(body, list) and len(body) > self.resilience_profile.max_rows:
                raise FetchError(
                    message=(
                        "JSON response row count exceeds safe limit "
                        f"({len(body)} > {self.resilience_profile.max_rows})"
                    ),
                    connector_id=connector_id,
                    request_params={"url": url},
                )
            return body, headers, raw

    async def _read_response_body(
        self,
        response: aiohttp.ClientResponse,
        *,
        connector_id: str,
        url: str,
        max_response_bytes: int | None = None,
        max_decompressed_bytes: int | None = None,
        before_classification: Callable[[bytes], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
    ) -> bytes:
        """Read a response body in bounded chunks instead of one blind read."""
        return await read_bounded_response_body(
            response,
            connector_id=connector_id,
            url=url,
            max_response_bytes=max_response_bytes,
            max_decompressed_bytes=max_decompressed_bytes,
            chunk_size=self._READ_CHUNK_SIZE,
            before_classification=before_classification,
            on_progress=on_progress,
        )

    @staticmethod
    def _build_auth_headers(
        handle: ConnectionHandle,
        headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        request_headers = dict(headers or {})
        auth_method = (handle.config.auth_method or "").strip().lower()
        credentials = handle.config.auth_credentials or {}

        if auth_method == "bearer":
            token = str(credentials.get("token") or "").strip()
            if token:
                request_headers.setdefault("Authorization", f"Bearer {token}")
        elif auth_method == "api_key":
            key = str(credentials.get("key") or "").strip()
            header_name = str(credentials.get("header") or "X-API-Key").strip() or "X-API-Key"
            if key:
                request_headers.setdefault(header_name, key)

        return request_headers

    def _build_fetch_result(
        self,
        *,
        data: DataT,
        row_count: int,
        schema_id: str,
        schema_version: str,
        quality_tier: QualityTier,
        bytes_transferred: int,
        completeness: float,
        fetched_at: datetime,
        fetch_duration_ms: float,
        content_hash: str,
        etag: str | None = None,
        last_modified: str | None = None,
        quality_flags: tuple[str, ...] = (),
        resilience: ResilienceInfo | None = None,
    ) -> FetchResult[DataT]:
        version, source_updated_at = build_data_version(
            etag=etag,
            last_modified=last_modified,
            content_hash=content_hash,
            fetched_at=fetched_at,
        )
        normalized_flags = quality_flags_from_source_metadata(
            source_updated_at=source_updated_at,
            base_flags=quality_flags,
        )

        return FetchResult(
            data=data,
            row_count=row_count,
            schema_id=schema_id,
            schema_version=schema_version,
            version=version,
            fetched_at=fetched_at,
            source_updated_at=source_updated_at,
            completeness=completeness,
            quality_tier=quality_tier,
            quality_flags=normalized_flags,
            fetch_duration_ms=max(float(fetch_duration_ms), 0.001),
            bytes_transferred=bytes_transferred,
            resilience=resilience,
        )

    @staticmethod
    def _elapsed_ms(started_at_monotonic: float) -> float:
        return max((time.monotonic() - started_at_monotonic) * 1000.0, 0.001)


__all__ = ["HTTPConnectorBase", "HTTPResilienceProfile", "RawHTTPResponseObserver"]
