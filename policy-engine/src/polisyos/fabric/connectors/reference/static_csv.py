"""
StaticCSVConnector - Reference implementation for static, URL-hosted CSV files.

Capabilities
------------
FULL_FETCH            Download and parse the entire CSV into a DataFrame.
SCHEMA_INTROSPECTION  Auto-infer DataSchema on first fetch via Phase 2.3
                      SchemaInference; cache the result per connection handle.

Design Decisions
----------------
* Uses pandas.read_csv on in-memory bytes so gzip / chunked responses work.
* ETag / Last-Modified headers drive the DataVersion strategy.
* Schema inference is lazy and cached per connection handle.
* CSV-specific options are passed via ConnectionConfig.headers using X-CSV-* keys.

Example ConnectionConfig
------------------------
>>> config_json = {
...     "url": "https://example.org/data/gdp_annual.csv",
...     "headers": {
...         "X-CSV-Delimiter": ",",
...         "X-CSV-Encoding": "utf-8",
...         "X-CSV-HasHeader": "true",
...     },
...     "auth_method": None,
...     "auth_credentials": {},
...     "timeout_seconds": 60,
...     "max_retries": 3,
...     "rate_limit_rps": None,
... }
"""
from __future__ import annotations

import hashlib
import io
import time
from datetime import datetime, timezone
from typing import Any, ClassVar

import pandas as pd

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts import infer_schema
from polisyos.fabric.connectors.resilience import (
    with_circuit_breaker,
    with_retry,
)
from polisyos.fabric.connectors.types import (
    ConfigurationError,
    FetchError,
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


def _bool_from_header(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "y", "t"}


def _handle_state(handle: ConnectionHandle) -> dict[str, Any]:
    state = handle.state.setdefault("static_csv", {})
    state.setdefault("schema_by_dataset", {})
    state.setdefault("etag_by_dataset", {})
    state.setdefault("last_modified_by_dataset", {})
    state.setdefault("content_hash_by_dataset", {})
    return state


class StaticCSVConnector(BaseConnector[pd.DataFrame]):
    """Fetch and parse a static CSV hosted at a stable URL."""

    connector_id: ClassVar[str] = "reference.static_csv"

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.SCHEMA_INTROSPECTION
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="static_csv",
        version="1.0.0",
        namespace="reference",
        source_name="Static CSV File",
        source_organization="PolicyOS Reference",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.SCHEMA_INTROSPECTION,
        ),
    )

    # ------------------------------------------------------------------
    # CSV-specific config parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_csv_config(config: ConnectionConfig) -> dict[str, Any]:
        return {
            "delimiter": config.headers.get("X-CSV-Delimiter", ","),
            "encoding": config.headers.get("X-CSV-Encoding", "utf-8"),
            "has_header": _bool_from_header(config.headers.get("X-CSV-HasHeader"), True),
        }

    @staticmethod
    def _http_headers(config: ConnectionConfig) -> dict[str, str]:
        return {k: v for k, v in config.headers.items() if not k.startswith("X-CSV-")}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        if not config.url:
            raise ConfigurationError(
                message="URL is required",
                connector_id=self.connector_id,
                field="url",
            )
        handle = self._create_handle(config)
        _handle_state(handle)
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    @with_retry(max_attempts=3, base_delay=1.0)
    @with_circuit_breaker()
    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        import aiohttp

        start = time.monotonic()
        headers = self._http_headers(handle.config)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    handle.config.url,
                    headers=headers,
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
    # Core fetch
    # ------------------------------------------------------------------
    @with_retry(max_attempts=3, base_delay=1.0)
    @with_circuit_breaker()
    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        import aiohttp

        csv_opts = self._parse_csv_config(handle.config)
        headers = self._http_headers(handle.config)
        state = _handle_state(handle)
        dataset_id = request.dataset_id

        etag_map: dict[str, str | None] = state["etag_by_dataset"]
        last_mod_map: dict[str, str | None] = state["last_modified_by_dataset"]
        content_hash_map: dict[str, str | None] = state["content_hash_by_dataset"]

        if etag_map.get(dataset_id):
            headers["If-None-Match"] = etag_map[dataset_id] or ""
        if last_mod_map.get(dataset_id):
            headers["If-Modified-Since"] = last_mod_map[dataset_id] or ""

        start = time.monotonic()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    handle.config.url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=handle.config.timeout_seconds),
                ) as resp:
                    duration_ms = (time.monotonic() - start) * 1000

                    if resp.status == 304:
                        etag_map[dataset_id] = resp.headers.get("ETag") or etag_map.get(dataset_id)
                        last_mod_map[dataset_id] = (
                            resp.headers.get("Last-Modified") or last_mod_map.get(dataset_id)
                        )
                        version = self._current_version(
                            etag_map.get(dataset_id),
                            last_mod_map.get(dataset_id),
                            content_hash_map.get(dataset_id),
                        )
                        return FetchResult(
                            data=pd.DataFrame(),
                            row_count=0,
                            schema_id=f"{self.connector_id}.{dataset_id}",
                            schema_version="1.0.0",
                            version=version,
                            fetched_at=datetime.now(timezone.utc),
                            completeness=1.0,
                            quality_tier=QualityTier.SILVER,
                            fetch_duration_ms=round(duration_ms, 2),
                            bytes_transferred=0,
                            not_modified=True,
                            quality_flags=frozenset({"not_modified"}),
                        )

                    if resp.status != 200:
                        error = FetchError(
                            message=f"HTTP {resp.status} from {handle.config.url}",
                            connector_id=self.connector_id,
                            request_params={"status_code": resp.status, "url": handle.config.url},
                        )
                        error.status_code = resp.status  # type: ignore[attr-defined]
                        raise error

                    body = await resp.read()
                    bytes_xferred = len(body)

                    etag_map[dataset_id] = resp.headers.get("ETag")
                    last_mod_map[dataset_id] = resp.headers.get("Last-Modified")
                    content_hash = self._content_hash(body)
                    content_hash_map[dataset_id] = content_hash
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(
                message=str(exc),
                connector_id=self.connector_id,
            ) from exc

        try:
            df = pd.read_csv(
                io.BytesIO(body),
                delimiter=csv_opts["delimiter"],
                encoding=csv_opts["encoding"],
                header=0 if csv_opts["has_header"] else None,
            )
        except Exception as exc:
            raise FetchError(
                message=f"CSV parse error: {exc}",
                connector_id=self.connector_id,
            ) from exc

        schema_by_dataset: dict[str, dict[str, Any]] = state["schema_by_dataset"]
        if dataset_id not in schema_by_dataset:
            schema_by_dataset[dataset_id] = self._infer_schema(df, dataset_id)

        version = self._current_version(
            etag_map.get(dataset_id),
            last_mod_map.get(dataset_id),
            content_hash_map.get(dataset_id),
        )

        return FetchResult(
            data=df,
            row_count=len(df),
            schema_id=f"{self.connector_id}.{dataset_id}",
            schema_version="1.0.0",
            version=version,
            fetched_at=datetime.now(timezone.utc),
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
            fetch_duration_ms=round(duration_ms, 2),
            bytes_transferred=bytes_xferred,
        )

    # ------------------------------------------------------------------
    # Schema introspection (Phase 2.3 integration)
    # ------------------------------------------------------------------
    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        state = _handle_state(handle)
        schema_by_dataset: dict[str, dict[str, Any]] = state["schema_by_dataset"]
        if dataset_id not in schema_by_dataset:
            return {"error": "Schema not yet inferred. Call fetch() first."}
        return schema_by_dataset[dataset_id]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _infer_schema(self, df: pd.DataFrame, dataset_id: str) -> dict[str, Any]:
        schema = infer_schema(df, schema_id=f"{self.connector_id}.{dataset_id}")
        return {
            "schema_id": schema.schema_id,
            "version": str(schema.version),
            "fields": [
                {
                    "name": field.name,
                    "data_type": field.data_type.value,
                    "nullable": field.nullable,
                    "semantic_type": field.semantic_type.value if field.semantic_type else None,
                }
                for field in schema.fields
            ],
        }

    @staticmethod
    def _content_hash(data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        return f"sha256:{digest}"

    def _current_version(
        self,
        etag: str | None,
        last_modified: str | None,
        content_hash: str | None,
    ) -> DataVersion:
        now = datetime.now(timezone.utc)
        if etag:
            return DataVersion(
                strategy=VersionStrategy.ETAG,
                value=etag,
                timestamp=now,
                content_hash=content_hash,
            )
        if last_modified:
            return DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=last_modified,
                timestamp=now,
                content_hash=content_hash,
            )
        return DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value=now.isoformat(),
            timestamp=now,
            content_hash=content_hash,
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
                    message="url is required",
                    field="url",
                )
            )
        elif not config.url.startswith(("http://", "https://")):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="url must be http or https",
                    field="url",
                )
            )
        if issues:
            return ValidationResult.failure(*issues)
        return ValidationResult.success()
