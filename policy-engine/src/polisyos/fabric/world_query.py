from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

import pandas as pd

from polisyos.core.security.db_backend import DatabaseBackend

if TYPE_CHECKING:
    from polisyos.fabric.io.db import SimulationDB
else:
    try:  # pragma: no cover - import guard for environments without duckdb
        from polisyos.fabric.io.db import SimulationDB
    except ModuleNotFoundError:  # pragma: no cover
        class SimulationDB:  # type: ignore[no-redef]
            pass

_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_TABLES: dict[str, str] = {
    "world_nodes": "world.world_nodes",
    "world_edges": "world.world_edges",
    "world_facts": "world.world_facts",
    "world_events": "world.world_events",
    "claims": "world.claims",
    "claim_citations": "world.claim_citations",
    "doc_sources": "world.doc_sources",
    "doc_versions": "world.doc_versions",
    "doc_fragments": "world.doc_fragments",
    "conflict_sets": "world.conflict_sets",
    "conflict_members": "world.conflict_members",
    "trust_assessments": "world.trust_assessments",
    "quality_reports": "world.quality_reports",
}


class WorldQueryError(ValueError):
    """Raised when a world query request is invalid."""


@dataclass(frozen=True)
class WorldQueryRequest:
    table: str
    columns: tuple[str, ...] = ("*",)
    where: Mapping[str, Any] | None = None
    order_by: tuple[str, ...] = ()
    limit: int = 1_000


def execute_world_query(
    db: SimulationDB | DatabaseBackend,
    request: WorldQueryRequest,
) -> pd.DataFrame:
    table_sql = _resolve_table(request.table)
    columns_sql = _compile_columns(request.columns)
    placeholder = _resolve_placeholder(db)
    where_sql, params = _compile_where(request.where, placeholder=placeholder)
    order_by_sql = _compile_order_by(request.order_by)
    limit = _normalize_limit(request.limit)

    query = (
        f"SELECT {columns_sql} FROM {table_sql}{where_sql}{order_by_sql} "
        f"LIMIT {placeholder}"
    )
    params.append(limit)
    return _execute_fetchdf(db, query, params)


def query_world_table(
    db: SimulationDB | DatabaseBackend,
    *,
    table: str,
    columns: Sequence[str] | None = None,
    where: Mapping[str, Any] | None = None,
    order_by: Iterable[str] | None = None,
    limit: int = 1_000,
) -> pd.DataFrame:
    request = WorldQueryRequest(
        table=table,
        columns=tuple(columns) if columns else ("*",),
        where=where,
        order_by=tuple(order_by or ()),
        limit=limit,
    )
    return execute_world_query(db, request)


def query_claims(
    db: SimulationDB | DatabaseBackend,
    *,
    where: Mapping[str, Any] | None = None,
    columns: Sequence[str] | None = None,
    limit: int = 1_000,
) -> pd.DataFrame:
    return query_world_table(
        db,
        table="claims",
        columns=columns,
        where=where,
        order_by=("claim_id ASC",),
        limit=limit,
    )


def query_events(
    db: SimulationDB | DatabaseBackend,
    *,
    where: Mapping[str, Any] | None = None,
    columns: Sequence[str] | None = None,
    limit: int = 1_000,
) -> pd.DataFrame:
    return query_world_table(
        db,
        table="world_events",
        columns=columns,
        where=where,
        order_by=("updated_at DESC",),
        limit=limit,
    )


def _resolve_table(name: str) -> str:
    table = _TABLES.get(name)
    if table is None:
        known = ", ".join(sorted(_TABLES))
        raise WorldQueryError(f"Unknown world table '{name}'. Known tables: {known}")
    return table


def _compile_columns(columns: Sequence[str]) -> str:
    if not columns:
        return "*"
    if len(columns) == 1 and columns[0] == "*":
        return "*"
    compiled: list[str] = []
    for column in columns:
        if not _IDENT_RE.fullmatch(column):
            raise WorldQueryError(f"Invalid column name: {column!r}")
        compiled.append(column)
    return ", ".join(compiled)


def _compile_where(
    where: Mapping[str, Any] | None,
    *,
    placeholder: str,
) -> tuple[str, list[Any]]:
    if not where:
        return "", []
    parts: list[str] = []
    params: list[Any] = []
    for key, value in where.items():
        if value is None:
            continue
        if not _IDENT_RE.fullmatch(key):
            raise WorldQueryError(f"Invalid filter key: {key!r}")
        parts.append(f"{key} = {placeholder}")
        params.append(value)
    if not parts:
        return "", params
    return " WHERE " + " AND ".join(parts), params


def _compile_order_by(order_by: Iterable[str]) -> str:
    parts: list[str] = []
    for entry in order_by:
        item = entry.strip()
        if not item:
            continue
        tokens = item.split()
        if len(tokens) == 1:
            column = tokens[0]
            direction = "ASC"
        elif len(tokens) == 2:
            column, direction = tokens
        else:
            raise WorldQueryError(f"Invalid order_by expression: {entry!r}")
        if not _IDENT_RE.fullmatch(column):
            raise WorldQueryError(f"Invalid order_by column: {column!r}")
        direction_norm = direction.upper()
        if direction_norm not in {"ASC", "DESC"}:
            raise WorldQueryError(f"Invalid order_by direction: {direction!r}")
        parts.append(f"{column} {direction_norm}")
    if not parts:
        return ""
    return " ORDER BY " + ", ".join(parts)


def _normalize_limit(limit: int) -> int:
    if limit <= 0:
        raise WorldQueryError("limit must be > 0")
    if limit > 100_000:
        raise WorldQueryError("limit must be <= 100000")
    return int(limit)


def _resolve_placeholder(db: SimulationDB | DatabaseBackend) -> str:
    if isinstance(db, SimulationDB):
        return "?"
    if isinstance(db, DatabaseBackend):
        return db.placeholder
    return "?"


def _execute_fetchdf(
    db: SimulationDB | DatabaseBackend,
    sql: str,
    params: Sequence[Any],
) -> pd.DataFrame:
    if isinstance(db, SimulationDB):
        return db.conn.execute(sql, list(params)).fetchdf()
    if isinstance(db, DatabaseBackend):
        return db.fetchdf(sql, params)
    raise TypeError(f"Unsupported db backend: {type(db)!r}")


__all__ = [
    "WorldQueryError",
    "WorldQueryRequest",
    "execute_world_query",
    "query_world_table",
    "query_claims",
    "query_events",
]
