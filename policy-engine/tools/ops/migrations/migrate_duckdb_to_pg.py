#!/usr/bin/env python3
"""Migrate tenant-scoped data from DuckDB to PostgreSQL."""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from tools._lib.imports import repo_root_from

import duckdb

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.fs import normalize_filesystem_path
from tools._lib.sql import render_qualified_identifier, validate_qualified_sql_identifier, validate_sql_identifier

TABLES = [
    "world.world_facts",
    "world.world_nodes",
    "world.world_edges",
    "world.world_events",
    "world.claims",
    "world.claim_citations",
    "world.doc_sources",
    "world.doc_versions",
    "world.doc_fragments",
    "world.conflict_sets",
    "world.conflict_members",
    "world.trust_assessments",
    "world.quality_reports",
    "public.macro_history",
    "public.agents_snapshot",
    "public.run_records",
]

_VALIDATED_TABLES = tuple(
    render_qualified_identifier(*validate_qualified_sql_identifier(table, kind="table", min_parts=2, max_parts=2))
    for table in TABLES
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DuckDB -> PostgreSQL tenant migration")
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--pg-dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv) if argv is not None else parse_args()
    tenant_id = str(uuid.UUID(args.tenant_id))
    duckdb_path = normalize_filesystem_path(
        Path(args.duckdb_path),
        kind="DuckDB path",
        must_exist=True,
        allow_directory=False,
    )
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")

    duck = duckdb.connect(str(duckdb_path), read_only=bool(args.dry_run))
    migrated_total = 0

    try:
        if args.dry_run:
            for table in _VALIDATED_TABLES:
                try:
                    source_df = duck.execute(f"SELECT * FROM {table}").fetchdf()
                except Exception:
                    print(f"skip {table}: source table missing")
                    continue

                if source_df.empty:
                    print(f"skip {table}: no rows")
                    continue

                source_df["tenant_id"] = tenant_id
                safe_columns = [validate_sql_identifier(str(column), kind="column") for column in source_df.columns]
                print(f"dry-run {table}: {len(source_df)} rows, columns={', '.join(safe_columns)}")

            print("dry-run completed")
            return 0

        try:
            import psycopg
            from psycopg.extras import execute_batch
        except ModuleNotFoundError as exc:
            raise SystemExit("psycopg is required. Install policy-engine[multi-tenant].") from exc

        with psycopg.connect(args.pg_dsn) as pg:
            with pg.cursor() as cur:
                for table in _VALIDATED_TABLES:
                    try:
                        source_df = duck.execute(f"SELECT * FROM {table}").fetchdf()
                    except Exception:
                        print(f"skip {table}: source table missing")
                        continue

                    if source_df.empty:
                        print(f"skip {table}: no rows")
                        continue

                    source_df["tenant_id"] = tenant_id
                    safe_columns = [validate_sql_identifier(str(column), kind="column") for column in source_df.columns]
                    placeholders = ", ".join(["%s"] * len(safe_columns))
                    column_sql = ", ".join(safe_columns)
                    query = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
                    records = [tuple(row) for row in source_df.itertuples(index=False, name=None)]

                    execute_batch(cur, query, records, page_size=args.batch_size)
                    migrated_total += len(records)
                    print(f"migrated {table}: {len(records)} rows")
    finally:
        duck.close()

    print(f"migration completed: {migrated_total} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
