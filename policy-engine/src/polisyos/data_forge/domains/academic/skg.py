"""Read-only Academic SKG inspection helpers."""

from __future__ import annotations

from pathlib import Path

import duckdb
from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel


class AcademicSKGTableSummary(DataForgeModel):
    """Summary of one table in an academic SKG DuckDB artifact."""

    table_name: str = Field(min_length=1)
    row_count: int = Field(ge=0)


class AcademicSKGSummary(DataForgeModel):
    """Read-only summary of an academic SKG DuckDB artifact."""

    db_path: str = Field(min_length=1)
    exists: bool
    readable: bool
    tables: tuple[AcademicSKGTableSummary, ...] = Field(default_factory=tuple)
    latest_version_id: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)

    def table_by_name(self, table_name: str) -> AcademicSKGTableSummary | None:
        """Return a table summary by name."""
        for table in self.tables:
            if table.table_name == table_name:
                return table
        return None


def load_academic_skg_summary(db_path: str | Path) -> AcademicSKGSummary:
    """Inspect an academic SKG DuckDB artifact in read-only mode."""
    path = Path(db_path)
    if not path.exists():
        return AcademicSKGSummary(
            db_path=str(path),
            exists=False,
            readable=False,
            warnings=(f"missing SKG artifact: {path}",),
        )

    try:
        con = duckdb.connect(str(path), read_only=True)
        try:
            table_names = _table_names(con)
            return AcademicSKGSummary(
                db_path=str(path),
                exists=True,
                readable=True,
                tables=tuple(
                    AcademicSKGTableSummary(
                        table_name=table_name,
                        row_count=_table_row_count(con, table_name),
                    )
                    for table_name in table_names
                ),
                latest_version_id=_latest_version_id(con, table_names),
            )
        finally:
            con.close()
    except (duckdb.Error, OSError, RuntimeError, TypeError, ValueError) as exc:
        return AcademicSKGSummary(
            db_path=str(path),
            exists=True,
            readable=False,
            warnings=(f"duckdb read failed: {exc.__class__.__name__}: {exc}",),
        )


def _table_names(con: duckdb.DuckDBPyConnection) -> tuple[str, ...]:
    rows = con.execute("SHOW TABLES").fetchall()
    return tuple(sorted(str(row[0]) for row in rows))


def _table_row_count(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    row = con.execute(
        "SELECT COUNT(*) FROM " + _quote_identifier(table_name)  # noqa: S608
    ).fetchone()
    if row is None:
        return 0
    value = row[0]
    return int(value) if isinstance(value, int) else 0


def _latest_version_id(
    con: duckdb.DuckDBPyConnection,
    table_names: tuple[str, ...],
) -> str | None:
    if "ac_skg_versions" not in table_names:
        return None
    columns = {
        str(row[1]) for row in con.execute("PRAGMA table_info('ac_skg_versions')").fetchall()
    }
    if "version_id" not in columns:
        return None
    order_clause = "created_at DESC" if "created_at" in columns else "version_id DESC"
    row = con.execute(
        "SELECT version_id FROM ac_skg_versions ORDER BY " + order_clause + " LIMIT 1"  # noqa: S608
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return str(row[0])


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


__all__ = [
    "AcademicSKGSummary",
    "AcademicSKGTableSummary",
    "load_academic_skg_summary",
]
