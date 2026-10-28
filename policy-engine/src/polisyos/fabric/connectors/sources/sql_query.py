"""Connector for generic SQL query execution with sqlite/duckdb first."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import duckdb
    import pandas as pd

from polisyos.core.canon import content_hash
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
    _ConnectionStateKey,
    _DatasetSchemaState,
    _is_dataset_schema_state,
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


def _open_sql_database(
    dialect: str, path: str, *, timeout_seconds: float | None = None
) -> sqlite3.Connection | duckdb.DuckDBPyConnection:
    if dialect in {"", "sqlite"}:
        if timeout_seconds is None:
            return sqlite3.connect(path)
        return sqlite3.connect(path, timeout=timeout_seconds)
    if dialect == "duckdb":
        import duckdb  # pragma: no cover - optional dependency in some environments

        return duckdb.connect(path)
    raise ValueError(f"unsupported SQL dialect {dialect!r}")


_SCHEMA_CACHE_STATE_KEY: _ConnectionStateKey[_DatasetSchemaState] = _ConnectionStateKey(
    "sql_query", _is_dataset_schema_state
)


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class SQLQueryExecution:
    """Observed execution data; a value alone never grants source authority.

    Configuration and SQL may contain secrets. They are intentionally omitted
    from repr and belong only in protected producer custody. The result's data
    may be mutable, so an authority-bearing caller must compare its canonical
    output bytes with ``output_json`` before persisting and admitting it.
    """

    result: FetchResult[Any] = field(repr=False)
    request: FetchRequest = field(repr=False)
    config_fingerprint: str = field(repr=False)
    query: str = field(repr=False)
    parameters: tuple[()]
    output_json: bytes = field(repr=False)
    columns: tuple[str, ...] = field(repr=False)
    dtypes: tuple[str, ...] = field(repr=False)


def _driver_rows_json(frame: pd.DataFrame) -> bytes:
    """Encode the actual pandas-produced view; refuse unsupported row values.

    This is the connector's produced view after pandas/driver conversion, not a
    claim that raw external database values have an identical representation.
    """
    columns = tuple(frame.columns)
    if any(type(column) is not str for column in columns) or len(set(columns)) != len(columns):
        raise ValueError("registered_sql_result_schema_not_established")
    rows = frame.to_dict(orient="records")
    if any(not isinstance(row, dict) or tuple(row) != columns for row in rows):
        raise ValueError("registered_sql_result_schema_not_established")
    try:
        return json.dumps(
            rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("registered_sql_result_profile_not_supported") from exc


@dataclass(frozen=True, slots=True)
class _SQLExecutionRecord:
    connector: SQLQueryConnector
    config: ConnectionConfig
    request: FetchRequest
    result: FetchResult[Any]
    query: str
    output_json: bytes
    columns: tuple[str, ...]
    dtypes: tuple[str, ...]


# Identity alone is not a grant. This record is populated only after the
# canonical method has made its driver call, and all fields are reconciled
# again by the protected producer before any validity-owner admission.
_SQL_EXECUTIONS: WeakKeyDictionary[SQLQueryExecution, _SQLExecutionRecord] = WeakKeyDictionary()
_SQL_EXECUTIONS_LOCK = RLock()


def _require_sql_execution(observed: SQLQueryExecution) -> _SQLExecutionRecord:
    if type(observed) is not SQLQueryExecution:
        raise ValueError("registered_sql_execution_not_observed")
    with _SQL_EXECUTIONS_LOCK:
        record = _SQL_EXECUTIONS.get(observed)
    if record is None:
        raise ValueError("registered_sql_execution_not_observed")
    try:
        current_output = _driver_rows_json(record.result.data)
        columns = tuple(record.result.data.columns)
        dtypes = tuple(str(dtype) for dtype in record.result.data.dtypes)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("registered_sql_execution_changed") from exc
    if (
        observed.result is not record.result
        or observed.request is not record.request
        or observed.config_fingerprint != record.config.cache_scope_fingerprint
        or observed.query != record.query
        or observed.parameters != ()
        or observed.output_json != record.output_json
        or observed.columns != record.columns
        or observed.dtypes != record.dtypes
        or columns != record.columns
        or dtypes != record.dtypes
        or current_output != record.output_json
    ):
        raise ValueError("registered_sql_execution_changed")
    return record


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
        handle._set_typed_state(_SCHEMA_CACHE_STATE_KEY, {"schema_by_dataset": {}})
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

    def _connect_db(
        self,
        config: ConnectionConfig,
    ) -> sqlite3.Connection | duckdb.DuckDBPyConnection:
        return _open_sql_database(self._dialect(config), self._database_path(config))

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
        """Fetch with the existing connector behavior and result contract."""
        return (await self._execute_observed(handle, request)).result

    async def _execute_observed(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
        *,
        canonical: bool = False,
        canonical_query: str | None = None,
    ) -> SQLQueryExecution:
        """Execute and record the actual driver query and result in one call.

        This observation is not issuer authority and must not be published.
        """
        import pandas as pd

        started = time.monotonic()
        config = handle.config
        if canonical:
            if canonical_query is None:
                raise ValueError("registered_sql_query_not_bound")
            query = canonical_query
        else:
            query = self._query(config, request)
        conn = (
            _open_sql_database(
                SQLQueryConnector._dialect(self, config),
                SQLQueryConnector._database_path(self, config),
                timeout_seconds=float(config.timeout_seconds),
            )
            if canonical
            else self._connect_db(config)
        )
        try:
            frame = pd.read_sql_query(query, conn)
        finally:
            conn.close()

        # This FetchResult wire type has a non-null has_more boolean. A full
        # limited result does not establish whether additional rows exist, so
        # do not report the default False as fact on the selected profile.
        if canonical and request.page_size is not None and len(frame) == request.page_size:
            raise ValueError("registered_sql_page_continuation_not_established")

        fetched_at = datetime.now(UTC)
        query_hash = "sha256:" + content_hash(query.encode("utf-8"))
        output_json = (
            _driver_rows_json(frame)
            if canonical
            else frame.to_json(orient="records", date_format="iso").encode("utf-8")
        )
        payload_hash = "sha256:" + content_hash(output_json)
        schema_id = make_schema_id(self.connector_id, request.dataset_id or "query")
        schema = infer_schema(frame, schema_id=schema_id)

        state = handle._read_typed_state_or_default(
            _SCHEMA_CACHE_STATE_KEY, {"schema_by_dataset": {}}
        )
        schema_by_dataset = dict(state["schema_by_dataset"])
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
        handle._set_typed_state(_SCHEMA_CACHE_STATE_KEY, {"schema_by_dataset": schema_by_dataset})

        result = FetchResult(
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
            # FetchResult has no unknown completeness representation. This
            # selected profile uses zero as a conservative gate value and makes
            # the missing source proof explicit; legacy behavior is preserved.
            completeness=0.0 if canonical else (1.0 if len(frame) else 0.0),
            quality_tier=QualityTier.UNVERIFIED if canonical else QualityTier.SILVER,
            quality_flags=frozenset(
                {"sql_query", "source_completeness_unknown"} if canonical else {"sql_query"}
            ),
            fetch_duration_ms=round((time.monotonic() - started) * 1000, 2),
            bytes_transferred=(
                len(output_json)
                if canonical
                else len(frame.to_json(orient="records").encode("utf-8"))
            ),
        )
        observed = SQLQueryExecution(
            result=result,
            request=request,
            config_fingerprint=config.cache_scope_fingerprint,
            query=query,
            parameters=(),
            output_json=output_json,
            columns=tuple(str(column) for column in frame.columns),
            dtypes=tuple(str(dtype) for dtype in frame.dtypes),
        )
        if canonical:
            record = _SQLExecutionRecord(
                connector=self,
                config=config,
                request=request,
                result=result,
                query=query,
                output_json=output_json,
                columns=observed.columns,
                dtypes=observed.dtypes,
            )
            with _SQL_EXECUTIONS_LOCK:
                _SQL_EXECUTIONS[observed] = record
        return observed

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        state = handle._read_typed_state_or_default(
            _SCHEMA_CACHE_STATE_KEY, {"schema_by_dataset": {}}
        )
        schema = dict(state["schema_by_dataset"]).get(dataset_id)
        if schema is not None:
            return dict(schema)
        await self.fetch(handle, FetchRequest(dataset_id=dataset_id, page_size=1))
        state = handle._read_typed_state_or_default(
            _SCHEMA_CACHE_STATE_KEY, {"schema_by_dataset": {}}
        )
        schema = dict(state["schema_by_dataset"]).get(dataset_id)
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
                    message=(
                        "X-SQL-Query or X-SQL-Table should be set; "
                        "dataset_id will be used otherwise"
                    ),
                )
            )
        return ValidationResult(
            valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
            issues=tuple(issues),
        )


__all__ = ["SQLQueryConnector"]
