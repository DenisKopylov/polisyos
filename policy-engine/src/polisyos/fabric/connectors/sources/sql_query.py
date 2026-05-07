"""Connector for generic SQL query execution with sqlite/duckdb first."""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlparse

from polisyos.core.canon import content_hash
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts import infer_schema, make_schema_id
from polisyos.fabric.connectors.types import (
    DatasetDescriptor,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from polisyos.fabric.quality.safety import UnsafeFilterExpressionError, quote_sql_identifier
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


def _safe_identifier(name: str) -> str:
    token = str(name).strip()
    if not token:
        raise ValueError("dataset_id must not be empty")
    return quote_sql_identifier(token, what="SQL table", allow_dotted=True)


_SQL_WRITE_OR_CONTROL_RE = re.compile(
    r"\b("
    r"ALTER|ATTACH|CALL|COPY|CREATE|DELETE|DETACH|DROP|EXEC|EXECUTE|GRANT|INSERT|"
    r"MERGE|PRAGMA|REPLACE|REVOKE|TRUNCATE|UPDATE|VACUUM"
    r")\b",
    flags=re.IGNORECASE,
)


def _validate_read_only_query(query: str) -> str:
    candidate = str(query or "").strip()
    if not candidate:
        raise UnsafeFilterExpressionError("SQL query must not be empty")
    if ";" in candidate:
        raise UnsafeFilterExpressionError("SQL query must be a single read-only statement")
    if "--" in candidate or "/*" in candidate or "*/" in candidate:
        raise UnsafeFilterExpressionError("SQL comments are not allowed in connector queries")
    normalized = re.sub(r"\s+", " ", candidate).strip().upper()
    if not normalized.startswith(("SELECT ", "WITH ")):
        raise UnsafeFilterExpressionError("SQL query must start with SELECT or WITH")
    match = _SQL_WRITE_OR_CONTROL_RE.search(candidate)
    if match:
        raise UnsafeFilterExpressionError(
            f"SQL query contains unsafe statement token: {match.group(1).upper()}"
        )
    return candidate


class SQLQueryConnector(BaseConnector[Any]):
    """Run read-only SQL queries against sqlite or duckdb connections."""

    namespace: ClassVar[str] = "sql"
    short_id: ClassVar[str] = "query"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.CUSTOM_QUERY
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.PROVENANCE_METADATA
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="SQL Query",
        source_organization="PolicyOS Fabric",
        source_url="https://polisyos.io/fabric/connectors/sql",
        trust_level=TrustLevel.HIGH,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.CUSTOM_QUERY,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.PROVENANCE_METADATA,
        ),
        description="Generic read-only SQL connector with sqlite and duckdb adapters.",
    )
    _STATE_KEY: ClassVar[str] = "sql_query"

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        validation = self.validate_config(config)
        if not validation.valid:
            issues = "; ".join(issue.message for issue in validation.issues)
            raise ValueError(f"invalid {self.connector_id} config: {issues}")
        handle = self._create_handle(config)
        handle.set_state(self._STATE_KEY, {"schema_by_dataset": {}})
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle

    def _dialect(self, config: ConnectionConfig) -> str:
        scheme = urlparse(str(config.url)).scheme.lower()
        return scheme or "sqlite"

    def _database_path(self, config: ConnectionConfig) -> str:
        parsed = urlparse(str(config.url))
        if parsed.scheme in {"", "sqlite", "duckdb"}:
            if parsed.scheme:
                return parsed.path
            return str(config.url)
        raise ValueError(
            f"unsupported SQL dialect {parsed.scheme!r}; sqlite and duckdb are supported today"
        )

    def _query(self, config: ConnectionConfig, request: FetchRequest) -> str:
        query = str(config.headers.get("X-SQL-Query", "")).strip()
        if query:
            return _validate_read_only_query(query)
        table = _safe_identifier(str(config.headers.get("X-SQL-Table") or request.dataset_id))
        if request.page_size is not None and int(request.page_size) <= 0:
            raise ValueError("page_size must be positive")
        limit = f" LIMIT {int(request.page_size)}" if request.page_size else ""
        return f"SELECT * FROM {table}{limit}"

    def _connect_db(self, config: ConnectionConfig):
        dialect = self._dialect(config)
        path = self._database_path(config)
        if dialect in {"", "sqlite"}:
            return sqlite3.connect(path)
        if dialect == "duckdb":
            import duckdb  # pragma: no cover - optional dependency in some environments

            return duckdb.connect(path)
        raise ValueError(f"unsupported SQL dialect {dialect!r}")

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        started = time.monotonic()
        try:
            conn = self._connect_db(handle.config)
            try:
                conn.execute("SELECT 1")
            finally:
                conn.close()
            return HealthStatus(
                healthy=True,
                message="connection ok",
                latency_ms=round((time.monotonic() - started) * 1000, 2),
            )
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        conn = self._connect_db(handle.config)
        try:
            dialect = self._dialect(handle.config)
            if dialect in {"", "sqlite"}:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            else:
                rows = conn.execute("SHOW TABLES").fetchall()
        finally:
            conn.close()
        for row in rows:
            name = str(row[0])
            yield DatasetDescriptor(
                dataset_id=name,
                name=name,
                description=f"{dialect or 'sqlite'} table",
                tags=("sql", dialect or "sqlite"),
            )

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[Any]:
        import pandas as pd

        started = time.monotonic()
        query = self._query(handle.config, request)
        conn = self._connect_db(handle.config)
        try:
            frame = pd.read_sql_query(query, conn)
        finally:
            conn.close()

        fetched_at = datetime.now(UTC)
        query_hash = "sha256:" + content_hash(query.encode("utf-8"))
        payload_hash = "sha256:" + content_hash(
            frame.to_json(orient="records", date_format="iso").encode("utf-8")
        )
        schema_id = make_schema_id(self.connector_id, request.dataset_id or "query")
        schema = infer_schema(frame, schema_id=schema_id)

        state = handle.get_state(self._STATE_KEY) or {}
        schema_by_dataset = dict(state.get("schema_by_dataset", {}))
        schema_by_dataset[request.dataset_id or "query"] = {
            "schema_id": schema.schema_id,
            "version": str(schema.version),
            "fields": [
                {
                    "name": field.name,
                    "field_id": field.stable_id,
                    "data_type": field.data_type.value,
                    "nullable": field.nullable,
                }
                for field in schema.fields
            ],
            "database_url": handle.config.url,
            "query": query,
            "query_hash": query_hash,
            "table": request.dataset_id,
        }
        handle.set_state(self._STATE_KEY, {"schema_by_dataset": schema_by_dataset})

        return FetchResult(
            data=frame,
            row_count=len(frame),
            schema_id=schema_id,
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=payload_hash,
                timestamp=fetched_at,
                content_hash=payload_hash,
            ),
            fetched_at=fetched_at,
            completeness=1.0 if len(frame) else 0.0,
            quality_tier=QualityTier.SILVER,
            quality_flags=frozenset({"sql_query"}),
            fetch_duration_ms=round((time.monotonic() - started) * 1000, 2),
            bytes_transferred=len(frame.to_json(orient="records").encode("utf-8")),
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        state = handle.get_state(self._STATE_KEY) or {}
        schema = dict(state.get("schema_by_dataset", {})).get(dataset_id)
        if schema is not None:
            return dict(schema)
        await self.fetch(handle, FetchRequest(dataset_id=dataset_id, page_size=1))
        state = handle.get_state(self._STATE_KEY) or {}
        schema = dict(state.get("schema_by_dataset", {})).get(dataset_id)
        return dict(schema or {"error": f"schema not available for {dataset_id}"})

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not str(config.url).strip():
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="url",
                    message="url is required",
                )
            )
        else:
            scheme = urlparse(str(config.url)).scheme.lower()
            if scheme not in {"", "sqlite", "duckdb"}:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field="url",
                        message=(
                            f"unsupported SQL dialect {scheme!r}; generic connector currently "
                            "supports sqlite and duckdb-first adapters"
                        ),
                    )
                )
        query = str(config.headers.get("X-SQL-Query", "")).strip()
        table = str(config.headers.get("X-SQL-Table", "")).strip()
        if query:
            try:
                _validate_read_only_query(query)
            except UnsafeFilterExpressionError as exc:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field="X-SQL-Query",
                        message=str(exc),
                    )
                )
        if not query and not table:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field="headers",
                    message="X-SQL-Query or X-SQL-Table should be set; dataset_id will be used otherwise",
                )
            )
        return ValidationResult(
            valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
            issues=tuple(issues),
        )


__all__ = ["SQLQueryConnector"]
