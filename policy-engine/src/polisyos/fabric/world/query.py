"""Read-only query helpers for Fabric world materializations.

These helpers query canonical world tables populated by ``fabric.world.materialize`` and apply
request-time contract normalization plus column allow-listing/masking. They are intentionally
read-only: provenance, conflict resolution, and claim normalization happen earlier during
document/claim ingestion, then this module exposes the materialized result tables.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from polisyos.core.security import AccessScope, DatabaseBackend
from polisyos.fabric.data_plane.temporal import parse_datetime_utc
from polisyos.fabric.quality.safety import validate_sql_identifier
from polisyos.fabric.security import (
    AccessAuditEvent,
    DataClassification,
    JsonlAccessAuditLog,
    RowAccessPolicy,
    apply_requested_column_guard,
    cardinality_bucket,
    classification_allowed,
    current_trace_id,
    mask_dataframe_columns,
    normalize_allowed_columns,
    normalize_classification,
)
from polisyos.fabric.world.store.snapshots import (
    default_world_snapshot_root,
    get_world_snapshot_adapter,
    resolve_world_snapshot,
)
from polisyos.ir.loading.fact_log import canonical_tx_time
from polisyos.ir.world.predicates import (
    WORLD_ARTIFACT_ID,
    WORLD_KIND,
    WORLD_LABEL,
    WORLD_PROPS_REF,
)

if TYPE_CHECKING:
    from polisyos.fabric.io.db import SimulationDB
else:
    try:  # pragma: no cover - import guard for environments without duckdb
        from polisyos.fabric.io.db import SimulationDB
    except ModuleNotFoundError:  # pragma: no cover

        class SimulationDB:  # type: ignore[no-redef]
            pass


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
_AS_OF_SQL_TABLES = frozenset({"world_facts", "world_edges", "world_nodes"})


class _DuckDBSnapshotBackend:
    backend_kind = "duckdb_snapshot"
    placeholder = "?"
    tenant_scope_enforced = False

    def __init__(self, db_path: Path) -> None:
        import duckdb

        self._conn = duckdb.connect(str(db_path), read_only=True)

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        return self._conn.execute(sql, list(params or ()))

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self.execute(sql, params).fetchall()]

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        return self.execute(sql, params).fetchdf()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    @contextmanager
    def tenant_scope(self, tenant_id: str) -> Iterator[None]:
        del tenant_id
        raise WorldQueryError(
            "snapshot-backed DuckDB queries do not support enforced tenant_scope; "
            "use a tenant-aware storage adapter or query an isolated tenant materialization"
        )
        yield

    def close(self) -> None:
        self._conn.close()


@dataclass(frozen=True)
class _CompiledTableSource:
    sql: str
    params: tuple[Any, ...] = ()


class WorldQueryError(ValueError):
    """Raised when a world query request is invalid."""


@dataclass(frozen=True)
class WorldQueryRequest:
    """Validated request contract for one materialized-world table scan.

    Attributes:
        table: Logical table alias such as ``claims`` or ``world_events``.
        columns: Requested output columns. ``("*",)`` means all columns before masking.
        where: Equality filters compiled into parameterized SQL.
        order_by: Sort expressions using ``column`` or ``column ASC|DESC``.
    limit: Maximum number of rows to return. Must be between ``1`` and ``100000``.
        allowed_columns: Optional allow-list; unauthorized columns are rejected or masked out.
    """

    table: str
    columns: tuple[str, ...] = ("*",)
    where: Mapping[str, Any] | None = None
    order_by: tuple[str, ...] = ()
    limit: int = 1_000
    allowed_columns: tuple[str, ...] | None = None
    access_scope: AccessScope | None = None
    classification: DataClassification | str | None = None
    column_classification: Mapping[str, DataClassification | str] | None = None
    purpose_of_use: str = ""
    row_policy: RowAccessPolicy | None = None
    tenant_column: str | None = None
    audit_log: JsonlAccessAuditLog | None = None
    as_of_tx_time: str | None = None
    as_of_valid_time: str | int | None = None
    snapshot_root: str | Path | None = None
    snapshot_id: str | None = None
    branch: str | None = None


def execute_world_query(
    db: SimulationDB | DatabaseBackend,
    request: WorldQueryRequest,
) -> pd.DataFrame:
    """Execute one normalized world query against a materialized Fabric backend.

    Args:
        db: ``SimulationDB`` or ``DatabaseBackend`` with a compatible fetch API.
        request: Logical query contract to validate and compile.

    Returns:
        DataFrame with authorized columns only; disallowed columns are masked by the security
        layer when an allow-list is provided.

    Raises:
        WorldQueryError: If table names, columns, filters, sort expressions, or limits are invalid.
        TypeError: If ``db`` does not provide a supported execution backend.

    Example:
        >>> request = WorldQueryRequest(table="claims", where={"predicate_id": "kpi.gdp"})
        >>> frame = execute_world_query(db, request)
    """
    allowed_columns = normalize_allowed_columns(request.allowed_columns)
    classification = normalize_classification(request.classification)
    access_allowed, deny_reason = classification_allowed(
        request.access_scope,
        classification,
        purpose_of_use=request.purpose_of_use,
    )
    if not access_allowed:
        _emit_access_audit(
            request=request,
            decision="deny",
            denied_reason=deny_reason,
            columns=request.columns,
            classification=classification,
            row_count=0,
        )
        raise WorldQueryError(deny_reason)

    requested_columns = _apply_column_classification_policy(
        requested=request.columns,
        allowed=allowed_columns,
        column_classification=request.column_classification,
        access_scope=request.access_scope,
    )
    try:
        effective_columns = apply_requested_column_guard(
            requested=requested_columns,
            allowed=allowed_columns,
        )
    except ValueError as exc:
        _emit_access_audit(
            request=request,
            decision="deny",
            denied_reason=str(exc),
            columns=requested_columns,
            classification=classification,
            row_count=0,
        )
        raise WorldQueryError(str(exc)) from exc

    with _query_backend(db, request) as active_db:
        placeholder = _resolve_placeholder(active_db)
        source = _resolve_table_source(request, placeholder=placeholder)
        if (
            _as_of_requested(request)
            and request.table not in _AS_OF_SQL_TABLES
            and not _snapshot_context_requested(request)
        ):
            raise WorldQueryError(
                "AS OF queries for projection tables require snapshot_root, snapshot_id, or branch"
            )
        temporal_clauses, temporal_params = _compile_temporal_clauses(
            request=request,
            placeholder=placeholder,
        )
        where_sql, params = _compile_where(
            _merge_where_filters(
                request.where,
                request.row_policy.normalized_filters(tenant_column=request.tenant_column)
                if request.row_policy is not None
                else None,
            ),
            placeholder=placeholder,
            extra_clauses=temporal_clauses,
            extra_params=temporal_params,
        )
        columns_sql = _compile_columns(effective_columns)
        order_by_sql = _compile_order_by(request.order_by, allowed_columns=allowed_columns)
        limit = _normalize_limit(request.limit)

        query = (
            f"SELECT {columns_sql} FROM {source.sql}{where_sql}{order_by_sql} LIMIT {placeholder}"
        )
        params = list(source.params) + params
        params.append(limit)
        row_policy = request.row_policy or RowAccessPolicy()
        with _resolve_tenant_scope(active_db, row_policy=row_policy):
            frame = _execute_fetchdf(active_db, query, params)
    masked = mask_dataframe_columns(frame, allowed=allowed_columns)
    _emit_access_audit(
        request=request,
        decision="allow",
        denied_reason="",
        columns=tuple(str(column) for column in masked.columns),
        classification=classification,
        row_count=len(masked.index),
    )
    return masked


def query_world_table(
    db: SimulationDB | DatabaseBackend,
    *,
    table: str,
    columns: Sequence[str] | None = None,
    where: Mapping[str, Any] | None = None,
    order_by: Iterable[str] | None = None,
    limit: int = 1_000,
    allowed_columns: Sequence[str] | None = None,
    access_scope: AccessScope | None = None,
    classification: DataClassification | str | None = None,
    column_classification: Mapping[str, DataClassification | str] | None = None,
    purpose_of_use: str = "",
    row_policy: RowAccessPolicy | None = None,
    tenant_column: str | None = None,
    audit_log: JsonlAccessAuditLog | None = None,
    as_of_tx_time: str | None = None,
    as_of_valid_time: str | int | None = None,
    snapshot_root: str | Path | None = None,
    snapshot_id: str | None = None,
    branch: str | None = None,
) -> pd.DataFrame:
    """Build and execute a ``WorldQueryRequest`` for a logical world-table alias."""
    request = WorldQueryRequest(
        table=table,
        columns=tuple(columns) if columns else ("*",),
        where=where,
        order_by=tuple(order_by or ()),
        limit=limit,
        allowed_columns=tuple(allowed_columns) if allowed_columns is not None else None,
        access_scope=access_scope,
        classification=classification,
        column_classification=column_classification,
        purpose_of_use=purpose_of_use,
        row_policy=row_policy,
        tenant_column=tenant_column,
        audit_log=audit_log,
        as_of_tx_time=as_of_tx_time,
        as_of_valid_time=as_of_valid_time,
        snapshot_root=snapshot_root,
        snapshot_id=snapshot_id,
        branch=branch,
    )
    return execute_world_query(db, request)


def query_claims(
    db: SimulationDB | DatabaseBackend,
    *,
    where: Mapping[str, Any] | None = None,
    columns: Sequence[str] | None = None,
    limit: int = 1_000,
    allowed_columns: Sequence[str] | None = None,
    access_scope: AccessScope | None = None,
    classification: DataClassification | str | None = None,
    column_classification: Mapping[str, DataClassification | str] | None = None,
    purpose_of_use: str = "",
    row_policy: RowAccessPolicy | None = None,
    tenant_column: str | None = None,
    audit_log: JsonlAccessAuditLog | None = None,
    as_of_tx_time: str | None = None,
    as_of_valid_time: str | int | None = None,
    snapshot_root: str | Path | None = None,
    snapshot_id: str | None = None,
    branch: str | None = None,
) -> pd.DataFrame:
    """Query normalized claim rows ordered by ``claim_id``."""
    return query_world_table(
        db,
        table="claims",
        columns=columns,
        where=where,
        order_by=("claim_id ASC",),
        limit=limit,
        allowed_columns=allowed_columns,
        access_scope=access_scope,
        classification=classification,
        column_classification=column_classification,
        purpose_of_use=purpose_of_use,
        row_policy=row_policy,
        tenant_column=tenant_column,
        audit_log=audit_log,
        as_of_tx_time=as_of_tx_time,
        as_of_valid_time=as_of_valid_time,
        snapshot_root=snapshot_root,
        snapshot_id=snapshot_id,
        branch=branch,
    )


def query_events(
    db: SimulationDB | DatabaseBackend,
    *,
    where: Mapping[str, Any] | None = None,
    columns: Sequence[str] | None = None,
    limit: int = 1_000,
    allowed_columns: Sequence[str] | None = None,
    access_scope: AccessScope | None = None,
    classification: DataClassification | str | None = None,
    column_classification: Mapping[str, DataClassification | str] | None = None,
    purpose_of_use: str = "",
    row_policy: RowAccessPolicy | None = None,
    tenant_column: str | None = None,
    audit_log: JsonlAccessAuditLog | None = None,
    as_of_tx_time: str | None = None,
    as_of_valid_time: str | int | None = None,
    snapshot_root: str | Path | None = None,
    snapshot_id: str | None = None,
    branch: str | None = None,
) -> pd.DataFrame:
    """Query persisted world events ordered by newest ``updated_at`` first."""
    return query_world_table(
        db,
        table="world_events",
        columns=columns,
        where=where,
        order_by=("updated_at DESC",),
        limit=limit,
        allowed_columns=allowed_columns,
        access_scope=access_scope,
        classification=classification,
        column_classification=column_classification,
        purpose_of_use=purpose_of_use,
        row_policy=row_policy,
        tenant_column=tenant_column,
        audit_log=audit_log,
        as_of_tx_time=as_of_tx_time,
        as_of_valid_time=as_of_valid_time,
        snapshot_root=snapshot_root,
        snapshot_id=snapshot_id,
        branch=branch,
    )


@contextmanager
def _query_backend(
    db: SimulationDB | DatabaseBackend,
    request: WorldQueryRequest,
) -> Iterator[SimulationDB | DatabaseBackend | _DuckDBSnapshotBackend]:
    if not _should_resolve_snapshot(request):
        yield db
        return
    if not isinstance(db, SimulationDB):
        raise WorldQueryError("snapshot and branch queries require SimulationDB")
    snapshot_root = (
        Path(request.snapshot_root)
        if request.snapshot_root is not None
        else default_world_snapshot_root(db)
    )
    try:
        snapshot = resolve_world_snapshot(
            snapshot_root,
            snapshot_id=request.snapshot_id,
            branch_name=request.branch,
            as_of_tx_time=_normalize_as_of_tx_time(request.as_of_tx_time),
            as_of_valid_time=_normalize_as_of_valid_time(request.as_of_valid_time),
        )
    except (FileNotFoundError, ValueError) as exc:
        raise WorldQueryError(str(exc)) from exc
    try:
        backend = _open_snapshot_backend(snapshot)
    except ValueError as exc:
        raise WorldQueryError(str(exc)) from exc
    try:
        yield backend
    finally:
        backend.close()


def _should_resolve_snapshot(request: WorldQueryRequest) -> bool:
    if request.snapshot_id or request.branch:
        return True
    return (
        request.snapshot_root is not None
        and _as_of_requested(request)
        and request.table not in _AS_OF_SQL_TABLES
    )


def _snapshot_context_requested(request: WorldQueryRequest) -> bool:
    return bool(request.snapshot_id or request.branch or request.snapshot_root)


def _resolve_tenant_scope(
    db: SimulationDB | DatabaseBackend | _DuckDBSnapshotBackend,
    *,
    row_policy: RowAccessPolicy,
) -> Iterator[None]:
    if row_policy.tenant_id is None:
        return nullcontext()
    tenant_scope = getattr(db, "tenant_scope", None)
    backend_kind = getattr(db, "backend_kind", type(db).__name__)
    if not callable(tenant_scope):
        raise WorldQueryError(
            f"backend {backend_kind!r} does not support enforced tenant_scope; "
            "tenant-scoped world queries require a backend with tenant_scope enforcement"
        )
    if not bool(getattr(db, "tenant_scope_enforced", False)):
        raise WorldQueryError(
            f"backend {backend_kind!r} does not support enforced tenant_scope; "
            "use a tenant-aware storage adapter or query an isolated tenant materialization"
        )
    return tenant_scope(row_policy.tenant_id)


def _open_snapshot_backend(snapshot: Any) -> _DuckDBSnapshotBackend:
    adapter = get_world_snapshot_adapter(str(snapshot.storage_adapter))
    if adapter.adapter_name == "duckdb_native_file_copy":
        return _DuckDBSnapshotBackend(Path(snapshot.snapshot_path))
    raise WorldQueryError(
        f"snapshot adapter {adapter.adapter_name!r} is registered but not queryable in the "
        f"local DuckDB runtime. {adapter.cost_notes}"
    )


def _as_of_requested(request: WorldQueryRequest) -> bool:
    return request.as_of_tx_time is not None or request.as_of_valid_time is not None


def _resolve_table_source(
    request: WorldQueryRequest,
    *,
    placeholder: str,
) -> _CompiledTableSource:
    if request.table == "world_nodes" and _as_of_requested(request):
        return _compile_world_nodes_as_of_source(
            placeholder=placeholder,
            as_of_tx_time=request.as_of_tx_time,
            as_of_valid_time=request.as_of_valid_time,
        )
    return _CompiledTableSource(sql=_resolve_table(request.table))


def _compile_world_nodes_as_of_source(
    *,
    placeholder: str,
    as_of_tx_time: str | None,
    as_of_valid_time: str | int | None,
) -> _CompiledTableSource:
    temporal_clauses, params = _compile_temporal_conditions(
        placeholder=placeholder,
        tx_column="tx_time",
        valid_column="valid_time",
        as_of_tx_time=as_of_tx_time,
        as_of_valid_time=as_of_valid_time,
    )
    filtered_where = ""
    if temporal_clauses:
        filtered_where = "WHERE " + " AND ".join(temporal_clauses)
    sql = f"""
    (
        WITH filtered_facts AS (
            SELECT *
            FROM world.world_facts
            {filtered_where}
        ),
        node_ids AS (
            SELECT DISTINCT subject_id AS node_id
            FROM filtered_facts
            UNION
            SELECT DISTINCT target_id AS node_id
            FROM filtered_facts
            WHERE target_id IS NOT NULL
        ),
        {_ranked_fact_cte(WORLD_KIND, "kind_choice")},
        {_ranked_fact_cte(WORLD_LABEL, "label_choice")},
        {_ranked_fact_cte(WORLD_ARTIFACT_ID, "artifact_choice")},
        {_ranked_fact_cte(WORLD_PROPS_REF, "props_choice")}
        SELECT
            node_ids.node_id,
            COALESCE(kind_choice.kind_choice_value, 'unknown') AS kind,
            label_choice.label_choice_value AS label,
            artifact_choice.artifact_choice_value AS artifact_id,
            props_choice.props_choice_value AS props_ref,
            NULL AS updated_at
        FROM node_ids
        LEFT JOIN kind_choice
            ON kind_choice.subject_id = node_ids.node_id
        LEFT JOIN label_choice
            ON label_choice.subject_id = node_ids.node_id
        LEFT JOIN artifact_choice
            ON artifact_choice.subject_id = node_ids.node_id
        LEFT JOIN props_choice
            ON props_choice.subject_id = node_ids.node_id
    ) AS world_nodes_as_of
    """
    return _CompiledTableSource(sql=sql, params=tuple(params))


def _ranked_fact_cte(predicate_id: str, alias: str) -> str:
    return f"""
    {alias} AS (
        SELECT subject_id, object_value AS {alias}_value
        FROM (
            SELECT
                subject_id,
                object_value,
                ROW_NUMBER() OVER (
                    PARTITION BY subject_id
                    ORDER BY
                        CASE WHEN object_value IS NULL THEN 1 ELSE 0 END ASC,
                        tx_time DESC,
                        fact_id DESC
                ) AS rn
            FROM filtered_facts
            WHERE predicate_id = '{predicate_id}'
        )
        WHERE rn = 1
    )
    """


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
        try:
            compiled.append(validate_sql_identifier(column, what="column"))
        except ValueError as exc:
            raise WorldQueryError(str(exc)) from exc
    return ", ".join(compiled)


def _compile_where(
    where: Mapping[str, Any] | None,
    *,
    placeholder: str,
    extra_clauses: Sequence[str] = (),
    extra_params: Sequence[Any] = (),
) -> tuple[str, list[Any]]:
    parts: list[str] = list(extra_clauses)
    params: list[Any] = list(extra_params)
    for key, value in (where or {}).items():
        if value is None:
            continue
        try:
            column = validate_sql_identifier(key, what="filter key")
        except ValueError as exc:
            raise WorldQueryError(str(exc)) from exc
        parts.append(f"{column} = {placeholder}")
        params.append(value)
    if not parts:
        return "", params
    return " WHERE " + " AND ".join(parts), params


def _compile_temporal_clauses(
    *,
    request: WorldQueryRequest,
    placeholder: str,
) -> tuple[list[str], list[Any]]:
    if request.table not in {"world_facts", "world_edges"}:
        return [], []
    return _compile_temporal_conditions(
        placeholder=placeholder,
        tx_column="tx_time",
        valid_column="valid_time",
        as_of_tx_time=request.as_of_tx_time,
        as_of_valid_time=request.as_of_valid_time,
    )


def _compile_temporal_conditions(
    *,
    placeholder: str,
    tx_column: str,
    valid_column: str,
    as_of_tx_time: str | None,
    as_of_valid_time: str | int | None,
) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    normalized_tx = _normalize_as_of_tx_time(as_of_tx_time)
    if normalized_tx is not None:
        clauses.append(f"{tx_column} <= {placeholder}")
        params.append(normalized_tx)

    normalized_valid = _normalize_as_of_valid_time(as_of_valid_time)
    if normalized_valid is not None:
        clauses.append(f"({valid_column} IS NULL OR {valid_column} <= {placeholder})")
        params.append(normalized_valid)
    return clauses, params


def _normalize_as_of_tx_time(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return canonical_tx_time(value)
    except Exception as exc:
        raise WorldQueryError(f"Invalid as_of_tx_time: {value!r}") from exc


def _normalize_as_of_valid_time(value: str | int | None) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return parse_datetime_utc(value, what="as_of_valid_time").isoformat().replace("+00:00", "Z")
    except Exception:
        # Some valid-time domains are stringly typed rather than timestamp typed.
        return value


def _merge_where_filters(
    requested: Mapping[str, Any] | None,
    enforced: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not requested and not enforced:
        return None
    merged: dict[str, Any] = {}
    for source in (requested or {}, enforced or {}):
        for key, value in source.items():
            if key in merged and merged[key] != value:
                raise WorldQueryError(
                    f"Conflicting row-level filter for {key!r}: {merged[key]!r} != {value!r}"
                )
            merged[key] = value
    return merged


def _apply_column_classification_policy(
    *,
    requested: Sequence[str],
    allowed: frozenset[str] | None,
    column_classification: Mapping[str, DataClassification | str] | None,
    access_scope: AccessScope | None,
) -> tuple[str, ...]:
    if not column_classification:
        return tuple(requested)

    classified = {
        str(column).strip().casefold(): normalize_classification(level)
        for column, level in column_classification.items()
        if str(column).strip()
    }

    if len(requested) == 1 and requested[0] == "*":
        if allowed is None:
            raise WorldQueryError(
                "Wildcard column access requires allowed_columns when column_classification is present"
            )
        candidate_columns = tuple(sorted(allowed)) if allowed is not None else ("*",)
    else:
        candidate_columns = tuple(requested)

    denied: list[str] = []
    effective: list[str] = []
    for column in candidate_columns:
        if column == "*":
            effective.append(column)
            continue
        level = classified.get(str(column).strip().casefold())
        access_ok, _reason = classification_allowed(access_scope, level)
        if level is not None and not access_ok:
            denied.append(str(column))
            continue
        effective.append(str(column))

    if denied:
        raise WorldQueryError(f"Unauthorized classified columns requested: {sorted(denied)}")
    return tuple(effective)


def _compile_order_by(
    order_by: Iterable[str],
    *,
    allowed_columns: frozenset[str] | None = None,
) -> str:
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
        try:
            column = validate_sql_identifier(column, what="order_by column")
        except ValueError as exc:
            raise WorldQueryError(str(exc)) from exc
        if allowed_columns is not None and column not in allowed_columns:
            raise WorldQueryError(f"Unauthorized order_by column: {column!r}")
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
    placeholder = getattr(db, "placeholder", None)
    if isinstance(placeholder, str) and placeholder:
        return placeholder
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
    fetchdf = getattr(db, "fetchdf", None)
    if callable(fetchdf):
        return fetchdf(sql, params)
    raise TypeError(f"Unsupported db backend: {type(db)!r}")


def _emit_access_audit(
    *,
    request: WorldQueryRequest,
    decision: str,
    denied_reason: str,
    columns: Sequence[str],
    classification: DataClassification,
    row_count: int,
) -> None:
    if request.audit_log is None:
        return
    scope = request.access_scope
    request_filters = {
        key: value for key, value in (request.where or {}).items() if value is not None
    }
    event = AccessAuditEvent(
        actor=scope.user_sub if scope is not None else "",
        tenant=scope.tenant_id if scope is not None else "",
        table=request.table,
        query=json_safe(
            {
                "where": request_filters,
                "limit": request.limit,
                "order_by": list(request.order_by),
                "as_of_tx_time": request.as_of_tx_time,
                "as_of_valid_time": request.as_of_valid_time,
                "snapshot_id": request.snapshot_id,
                "branch": request.branch,
            }
        ),
        columns=tuple(str(column) for column in columns if str(column).strip()),
        classification=classification,
        decision=decision,
        denied_reason=denied_reason,
        masking=tuple(sorted(normalize_allowed_columns(request.allowed_columns) or frozenset())),
        cardinality_bucket=cardinality_bucket(row_count),
        purpose_of_use=request.purpose_of_use,
        trace_id=current_trace_id(),
        metadata={
            "tenant_filter": request.row_policy.tenant_id if request.row_policy else "",
        },
    )
    request.audit_log.append(event)


def json_safe(payload: Mapping[str, Any]) -> str:
    items = ", ".join(f"{key}={value!r}" for key, value in sorted(payload.items()))
    return f"world_query({items})"


__all__ = [
    "WorldQueryError",
    "WorldQueryRequest",
    "execute_world_query",
    "query_claims",
    "query_events",
    "query_world_table",
]
