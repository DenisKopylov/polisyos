#!/usr/bin/env python3
"""Migrate tenant-scoped data from DuckDB to PostgreSQL.

Usage:
  python tools/migrate_duckdb_to_pg.py \
      --duckdb-path integration.duckdb \
      --pg-dsn postgresql://user:pass@localhost:5432/polisyos \
      --tenant-id 11111111-1111-1111-1111-111111111111
"""
from __future__ import annotations

import argparse
import uuid

import duckdb

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DuckDB -> PostgreSQL tenant migration")
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--pg-dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tenant_id = str(uuid.UUID(args.tenant_id))

    try:
        import psycopg
        from psycopg.extras import execute_batch
    except ModuleNotFoundError as exc:
        raise SystemExit("psycopg is required. Install policy-engine[multi-tenant].") from exc

    duck = duckdb.connect(args.duckdb_path)
    pg = psycopg.connect(args.pg_dsn)

    migrated_total = 0
    try:
        with pg:
            with pg.cursor() as cur:
                for table in TABLES:
                    try:
                        source_df = duck.execute(f"SELECT * FROM {table}").fetchdf()
                    except Exception:
                        print(f"skip {table}: source table missing")
                        continue

                    if source_df.empty:
                        print(f"skip {table}: no rows")
                        continue

                    source_df["tenant_id"] = tenant_id
                    columns = list(source_df.columns)
                    placeholders = ", ".join(["%s"] * len(columns))
                    column_sql = ", ".join(columns)

                    query = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
                    records = [tuple(row) for row in source_df.itertuples(index=False, name=None)]

                    if args.dry_run:
                        print(f"dry-run {table}: {len(records)} rows")
                        continue

                    execute_batch(cur, query, records, page_size=args.batch_size)
                    migrated_total += len(records)
                    print(f"migrated {table}: {len(records)} rows")

        if args.dry_run:
            print("dry-run completed")
        else:
            print(f"migration completed: {migrated_total} rows")
    finally:
        duck.close()
        pg.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
