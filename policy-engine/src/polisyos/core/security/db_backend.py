"""Database backend abstraction for tenant-aware execution."""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.security.exceptions import TenantIsolationError

logger = get_logger("polisyos.security.db_backend")

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


def validate_tenant_id(tenant_id: str) -> None:
    try:
        uuid.UUID(tenant_id)
    except ValueError as exc:
        raise TenantIsolationError(f"Invalid tenant_id format: {tenant_id!r}") from exc


_validate_tenant_id = validate_tenant_id


@runtime_checkable
class DatabaseBackend(Protocol):
    """Protocol implemented by tenant-aware DB adapters."""

    backend_kind: str
    placeholder: str

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        ...

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        ...

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        ...

    @contextmanager
    def transaction(self) -> Iterator[None]:
        ...

    @contextmanager
    def tenant_scope(self, tenant_id: str) -> Iterator[None]:
        ...

    def close(self) -> None:
        ...


class PostgresBackend:
    """Synchronous PostgreSQL backend with RLS tenant context."""

    backend_kind = "postgres"
    placeholder = "%s"
    tenant_scope_enforced = True

    def __init__(self, dsn: str, *, fail_closed: bool = True) -> None:
        self._dsn = dsn
        self._conn: Any | None = None
        self._fail_closed = fail_closed
        self._in_transaction = False

    def connect(self) -> None:
        try:
            import psycopg
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresBackend") from exc
        self._conn = psycopg.connect(self._dsn, autocommit=False)

    def _ensure_conn(self) -> Any:
        if self._conn is None:
            self.connect()
        if self._conn is None:
            raise RuntimeError("PostgreSQL connection is not initialized")
        return self._conn

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        conn = self._ensure_conn()
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params or ()))
            if cur.description:
                return cur.fetchall()
            return None

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        conn = self._ensure_conn()
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params or ()))
            rows = cur.fetchall()
        return [tuple(row) for row in rows]

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        conn = self._ensure_conn()
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params or ()))
            rows = cur.fetchall()
            columns = [desc[0] for desc in (cur.description or [])]
        return pd.DataFrame(rows, columns=columns)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._in_transaction:
            raise RuntimeError("Nested transactions are not supported")
        conn = self._ensure_conn()
        self._in_transaction = True
        try:
            yield
            conn.commit()
        except Exception as exc:
            logger.debug("Postgres transaction rollback due to error: %s", exc)
            conn.rollback()
            raise
        finally:
            self._in_transaction = False

    @contextmanager
    def tenant_scope(self, tenant_id: str) -> Iterator[None]:
        validate_tenant_id(tenant_id)
        conn = self._ensure_conn()

        if self._fail_closed and not self._in_transaction:
            raise TenantIsolationError(
                "tenant_scope requires an active transaction for SET LOCAL safety"
            )

        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.current_tenant = %s", (tenant_id,))
        try:
            yield
        finally:
            # Keep explicit reset for safety with pooled and reused sessions.
            with conn.cursor() as cur:
                cur.execute("RESET app.current_tenant")

    def reset_session(self) -> None:
        conn = self._ensure_conn()
        with conn.cursor() as cur:
            cur.execute("DISCARD ALL")

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class DuckDBLegacyBackend:
    """Adapter around existing SimulationDB for compatibility."""

    backend_kind = "duckdb"
    placeholder = "?"
    tenant_scope_enforced = False

    def __init__(self, simulation_db: Any) -> None:
        self._db = simulation_db

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        if params is None:
            return self._db.conn.execute(sql)
        return self._db.conn.execute(sql, list(params))

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        return [tuple(row) for row in rows]

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        cursor = self.execute(sql, params)
        return cursor.fetchdf()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._db.conn.execute("BEGIN")
        try:
            yield
            self._db.conn.execute("COMMIT")
        except Exception as exc:
            logger.debug("DuckDB transaction rollback due to error: %s", exc)
            self._db.conn.execute("ROLLBACK")
            raise

    @contextmanager
    def tenant_scope(self, tenant_id: str) -> Iterator[None]:
        validate_tenant_id(tenant_id)
        yield

    def close(self) -> None:
        self._db.close()


__all__ = [
    "DatabaseBackend",
    "DuckDBLegacyBackend",
    "PostgresBackend",
    "validate_tenant_id",
]
