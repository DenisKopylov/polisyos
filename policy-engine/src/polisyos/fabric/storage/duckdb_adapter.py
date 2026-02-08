from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
import re
from typing import Any, Iterator

import pandas as pd

from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world_query import WorldQueryError, query_world_table

from .port import StoragePort

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class DuckDBStorageAdapter(StoragePort):
    """StoragePort adapter for SimulationDB (DuckDB backend)."""

    def __init__(self, db: SimulationDB) -> None:
        self._db = db

    @property
    def raw_db(self) -> SimulationDB:
        return self._db

    def save_macro(self, data: list[dict[str, Any]]) -> None:
        self._db.save_macro(data)

    def save_agents(self, run_id: str, step: int, agents_state: Any) -> None:
        self._db.save_agents(run_id, step, agents_state)

    def save_run_record(self, record: Any) -> None:
        self._db.save_run_record(record)

    def query_table(
        self,
        table: str,
        *,
        columns: Sequence[str] | None = None,
        where: Mapping[str, Any] | None = None,
        order_by: Sequence[str] | None = None,
        limit: int = 1_000,
    ) -> pd.DataFrame:
        try:
            return query_world_table(
                self._db,
                table=table,
                columns=list(columns) if columns is not None else None,
                where=dict(where) if where is not None else None,
                order_by=list(order_by) if order_by is not None else None,
                limit=limit,
            )
        except WorldQueryError:
            return self._query_fallback(
                table=table,
                columns=columns,
                where=where,
                order_by=order_by,
                limit=limit,
            )

    @contextmanager
    def transaction(self) -> Iterator[StoragePort]:
        self._db.conn.execute("BEGIN TRANSACTION")
        try:
            yield self
        except Exception:
            self._db.conn.execute("ROLLBACK")
            raise
        else:
            self._db.conn.execute("COMMIT")

    def close(self) -> None:
        self._db.close()

    def _query_fallback(
        self,
        *,
        table: str,
        columns: Sequence[str] | None,
        where: Mapping[str, Any] | None,
        order_by: Sequence[str] | None,
        limit: int,
    ) -> pd.DataFrame:
        table_name = _validate_identifier(table, what="table")
        column_sql = "*"
        if columns:
            validated = [_validate_identifier(column, what="column") for column in columns]
            column_sql = ", ".join(validated)

        query = f"SELECT {column_sql} FROM {table_name}"
        params: list[Any] = []

        if where:
            clauses: list[str] = []
            for key, value in where.items():
                column = _validate_identifier(str(key), what="where key")
                clauses.append(f"{column} = ?")
                params.append(value)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)

        if order_by:
            compiled: list[str] = []
            for item in order_by:
                tokens = str(item).strip().split()
                if not tokens:
                    continue
                if len(tokens) == 1:
                    column = _validate_identifier(tokens[0], what="order_by column")
                    direction = "ASC"
                elif len(tokens) == 2:
                    column = _validate_identifier(tokens[0], what="order_by column")
                    direction = tokens[1].upper()
                    if direction not in {"ASC", "DESC"}:
                        raise ValueError(f"Invalid order direction: {tokens[1]!r}")
                else:
                    raise ValueError(f"Invalid order_by expression: {item!r}")
                compiled.append(f"{column} {direction}")
            if compiled:
                query += " ORDER BY " + ", ".join(compiled)

        if limit <= 0:
            raise ValueError("limit must be > 0")
        query += " LIMIT ?"
        params.append(int(limit))
        return self._db.conn.execute(query, params).fetchdf()


def _validate_identifier(value: str, *, what: str) -> str:
    if not _IDENT_RE.fullmatch(value):
        raise ValueError(f"Invalid {what}: {value!r}")
    return value


__all__ = ["DuckDBStorageAdapter"]

