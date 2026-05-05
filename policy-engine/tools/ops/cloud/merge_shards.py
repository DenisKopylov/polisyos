"""
Merge pipeline output shards into a single unified graph snapshot.

Usage:
    python merge_shards.py /data/shard_1 /data/shard_2 /data/shard_3 --output /data/merged --dry-run
    python merge_shards.py /data/shard_1 /data/shard_2 /data/shard_3 --output /data/merged --yes
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from tools.lib.imports import repo_root_from

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root_from(__file__)))

from tools.lib.fs import (
    atomic_replace_path,
    atomic_write_json,
    exclusive_lock,
    normalize_filesystem_path,
)
from tools.lib.sql import quote_sql_string_literal, validate_sql_identifier

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb not installed. Run: pip install duckdb")
    sys.exit(1)


_CORE_TABLES = [
    "ac_topics",
    "ac_runs",
    "ac_works",
    "ac_work_concepts",
    "ac_topic_selections",
    "ac_article_extractions",
    "ac_causal_claims_raw",
    "ac_claim_adjudications",
    "ac_causal_claims",
    "ac_parameter_estimates",
    "ac_boundary_conditions",
]

_SKG_TABLES = [
    "ac_skg_articles",
    "ac_skg_variables",
    "ac_skg_edges",
    "ac_skg_edge_evidence",
    "ac_skg_family_edges",
    "ac_skg_parameters",
    "ac_skg_simulation_parameters",
    "ac_skg_canonization_cache",
    "ac_skg_context_attributes",
    "ac_skg_moderation_edges",
    "ac_skg_context_profiles",
    "ac_skg_transport_scores",
]

_JSONL_SPECS: tuple[tuple[str, str | None], ...] = (
    ("published_claims.jsonl", "claim_id"),
    ("all_records.jsonl", None),
)

_VALID_TABLES = tuple(
    validate_sql_identifier(table, kind="table") for table in (_CORE_TABLES + _SKG_TABLES)
)


def _find_duckdb(shard_dir: Path) -> Path:
    """Locate the DuckDB file inside a shard output directory."""

    safe_shard_dir = normalize_filesystem_path(
        shard_dir,
        kind="shard directory",
        must_exist=True,
        allow_directory=True,
    )
    candidates = sorted(safe_shard_dir.rglob("scholar_knowledge.duckdb"))
    if not candidates:
        raise FileNotFoundError(f"No scholar_knowledge.duckdb found in {safe_shard_dir}")
    return normalize_filesystem_path(
        candidates[0],
        kind="shard database",
        must_exist=True,
        allow_directory=False,
    )


def _find_jsonl(shard_dir: Path, filename: str) -> Path | None:
    """Locate a JSONL file inside a shard."""

    safe_shard_dir = normalize_filesystem_path(
        shard_dir,
        kind="shard directory",
        must_exist=True,
        allow_directory=True,
    )
    candidates = sorted(safe_shard_dir.rglob(filename))
    if not candidates:
        return None
    return normalize_filesystem_path(
        candidates[0],
        kind=f"{filename} path",
        must_exist=True,
        allow_directory=False,
    )


def _table_exists(con: duckdb.DuckDBPyConnection, table: str, schema: str = "main") -> bool:
    safe_table = validate_sql_identifier(table, kind="table")
    safe_schema = validate_sql_identifier(schema, kind="schema")
    result = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
        [safe_schema, safe_table],
    ).fetchone()
    return bool(result and result[0] > 0)


def _table_columns(con: duckdb.DuckDBPyConnection, table: str, schema: str = "main") -> list[str]:
    safe_table = validate_sql_identifier(table, kind="table")
    safe_schema = validate_sql_identifier(schema, kind="schema")
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        [safe_schema, safe_table],
    ).fetchall()
    return [str(row[0]) for row in rows]


def _count_rows(con: duckdb.DuckDBPyConnection, table: str, schema: str = "main") -> int:
    safe_table = validate_sql_identifier(table, kind="table")
    safe_schema = validate_sql_identifier(schema, kind="schema")
    row = con.execute(f"SELECT count(*) FROM {safe_schema}.{safe_table}").fetchone()
    return int(row[0]) if row else 0


def _preview_duckdb(shard_paths: list[Path]) -> dict[str, int]:
    totals: dict[str, int] = dict.fromkeys(_VALID_TABLES, 0)
    for shard_db in shard_paths:
        safe_shard_db = normalize_filesystem_path(
            shard_db,
            kind="shard database",
            must_exist=True,
            allow_directory=False,
        )
        con = duckdb.connect(str(safe_shard_db), read_only=True)
        try:
            for table in _VALID_TABLES:
                if _table_exists(con, table):
                    totals[table] += _count_rows(con, table)
        finally:
            con.close()
    return totals


def _count_jsonl_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _preview_jsonl(shard_dirs: list[Path]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for filename, _ in _JSONL_SPECS:
        count = 0
        for shard_dir in shard_dirs:
            src = _find_jsonl(shard_dir, filename)
            if src is not None:
                count += _count_jsonl_rows(src)
        totals[filename] = count
    return totals


def _print_preview(*, shard_dirs: list[Path], shard_paths: list[Path], output_dir: Path) -> None:
    preview_tables = _preview_duckdb(shard_paths) if shard_paths else {}
    preview_jsonl = _preview_jsonl(shard_dirs)

    print(f"Merging {len(shard_dirs)} shards into {output_dir}")
    print("")
    print("Preview:")
    print(f"  shard directories: {len(shard_dirs)}")
    print(f"  shard databases:   {len(shard_paths)}")
    print(f"  output directory:  {output_dir}")
    if preview_tables:
        print("  source DuckDB rows:")
        for table, count in preview_tables.items():
            if count > 0:
                print(f"    {table}: {count}")
    if preview_jsonl:
        print("  source JSONL rows:")
        for filename, count in preview_jsonl.items():
            print(f"    {filename}: {count}")
    print("")


def merge_duckdb(shard_paths: list[Path], output_path: Path) -> dict[str, int]:
    """Merge multiple DuckDB shards into one, deduplicating by primary key."""

    safe_output_path = normalize_filesystem_path(
        output_path,
        kind="merged database path",
        must_exist=False,
        allow_directory=False,
    )
    safe_output_path.parent.mkdir(parents=True, exist_ok=True)

    base_shard = normalize_filesystem_path(
        shard_paths[0],
        kind="base shard database",
        must_exist=True,
        allow_directory=False,
    )
    print(f"  Base shard: {base_shard}")
    shutil.copy2(base_shard, safe_output_path)

    con = duckdb.connect(str(safe_output_path))
    stats: dict[str, int] = {}

    try:
        for index, shard_db in enumerate(shard_paths[1:], start=2):
            safe_shard_db = normalize_filesystem_path(
                shard_db,
                kind="shard database",
                must_exist=True,
                allow_directory=False,
            )
            alias = validate_sql_identifier(f"shard{index}", kind="alias")
            print(f"  Attaching shard {index}: {safe_shard_db}")
            con.execute(
                f"ATTACH DATABASE {quote_sql_string_literal(str(safe_shard_db))} AS {alias} (READ_ONLY)"
            )
            try:
                for table in _VALID_TABLES:
                    if not _table_exists(con, table, alias):
                        continue
                    if not _table_exists(con, table, "main"):
                        continue

                    cols = _table_columns(con, table, "main")
                    dedup_key = _get_dedup_key(table, cols)
                    main_ref = f"main.{table}"
                    shard_ref = f"{alias}.{table}"

                    if dedup_key:
                        validated_keys = [
                            validate_sql_identifier(column, kind="column") for column in dedup_key
                        ]
                        where_clause = " AND ".join(
                            f"s.{column} = m.{column}" for column in validated_keys
                        )
                        con.execute(
                            f"INSERT INTO {main_ref} "
                            f"SELECT s.* FROM {shard_ref} s "
                            f"WHERE NOT EXISTS ("
                            f"  SELECT 1 FROM {main_ref} m WHERE {where_clause}"
                            f")"
                        )
                    else:
                        con.execute(f"INSERT INTO {main_ref} SELECT * FROM {shard_ref}")
            finally:
                con.execute(f"DETACH DATABASE {alias}")

        for table in _VALID_TABLES:
            if _table_exists(con, table):
                stats[table] = _count_rows(con, table)
    finally:
        con.close()
    return stats


def _get_dedup_key(table: str, cols: list[str]) -> list[str] | None:
    """Return the natural dedup key for a table, or None for append-all."""

    keys: dict[str, list[str] | None] = {
        "ac_topics": ["topic_id"],
        "ac_runs": ["run_id"],
        "ac_works": ["id"],
        "ac_work_concepts": ["work_id", "topic_id", "concept"] if "concept" in cols else None,
        "ac_topic_selections": ["run_id", "topic_id", "work_id"],
        "ac_article_extractions": ["extraction_id"]
        if "extraction_id" in cols
        else ["run_id", "work_id", "extraction_mode"],
        "ac_causal_claims_raw": ["id"] if "id" in cols else ["work_id", "cause", "effect"],
        "ac_claim_adjudications": ["claim_id"] if "claim_id" in cols else None,
        "ac_causal_claims": ["id"] if "id" in cols else ["work_id", "cause", "effect"],
        "ac_parameter_estimates": ["id"]
        if "id" in cols
        else ["work_id", "variable_name", "estimate"],
        "ac_boundary_conditions": ["boundary_id"] if "boundary_id" in cols else None,
        "ac_skg_articles": ["openalex_id"],
        "ac_skg_variables": ["variable_name"] if "variable_name" in cols else ["canonical_name"],
        "ac_skg_edges": ["edge_id"] if "edge_id" in cols else ["src", "dst", "direction"],
        "ac_skg_edge_evidence": ["edge_id", "claim_id", "openalex_id"]
        if "claim_id" in cols
        else None,
        "ac_skg_family_edges": ["family_edge_id"]
        if "family_edge_id" in cols
        else ["src_family", "dst_family", "direction"],
        "ac_skg_parameters": ["param_id"] if "param_id" in cols else None,
        "ac_skg_simulation_parameters": ["numeric_id"] if "numeric_id" in cols else None,
        "ac_skg_canonization_cache": ["raw_name"] if "raw_name" in cols else None,
        "ac_skg_context_attributes": ["attr_id"] if "attr_id" in cols else None,
        "ac_skg_moderation_edges": ["moderation_id"] if "moderation_id" in cols else None,
        "ac_skg_context_profiles": ["profile_id"] if "profile_id" in cols else None,
        "ac_skg_transport_scores": ["transport_id"] if "transport_id" in cols else ["edge_id"],
    }
    key = keys.get(table)
    if key is None:
        return None
    if all(item in cols for item in key):
        return key
    return None


def merge_jsonl(
    shard_dirs: list[Path],
    filename: str,
    output_path: Path,
    *,
    dedup_field: str | None = None,
) -> int:
    """Merge JSONL files from shards, optionally deduplicating by a field."""

    seen: set[str] = set()
    count = 0
    safe_output_path = normalize_filesystem_path(
        output_path,
        kind=f"merged {filename} path",
        must_exist=False,
        allow_directory=False,
    )
    safe_output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=safe_output_path.parent,
            prefix=f".{safe_output_path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            for shard in shard_dirs:
                src = _find_jsonl(shard, filename)
                if src is None:
                    continue
                with src.open("r", encoding="utf-8") as source_handle:
                    for raw_line in source_handle:
                        line = raw_line.strip()
                        if not line:
                            continue
                        if dedup_field:
                            try:
                                row = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            key = str(row.get(dedup_field, ""))
                            if key in seen:
                                continue
                            seen.add(key)
                        handle.write(line + "\n")
                        count += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, safe_output_path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return count


def merge_json_reports(shard_dirs: list[Path], filename: str, output_path: Path) -> None:
    """Collect JSON reports from all shards into an array."""

    reports = []
    for index, shard in enumerate(shard_dirs, start=1):
        safe_shard = normalize_filesystem_path(
            shard,
            kind="shard directory",
            must_exist=True,
            allow_directory=True,
        )
        for candidate in sorted(safe_shard.rglob(filename)):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            data["_shard"] = index
            data["_shard_path"] = str(candidate)
            reports.append(data)

    safe_output_path = normalize_filesystem_path(
        output_path,
        kind=f"merged {filename} report path",
        must_exist=False,
        allow_directory=False,
    )
    atomic_write_json(safe_output_path, reports)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge pipeline output shards")
    parser.add_argument("shards", nargs="+", help="Paths to shard output directories")
    parser.add_argument("--output", "-o", required=True, help="Output directory for merged results")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview affected rows/items without writing merged output",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm replacement of the output directory with staged merged results",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    shard_dirs = [
        normalize_filesystem_path(
            Path(value),
            kind="shard directory",
            must_exist=True,
            allow_directory=True,
        )
        for value in args.shards
    ]
    output_dir = normalize_filesystem_path(
        Path(args.output),
        kind="output directory",
        must_exist=False,
        allow_directory=True,
    )

    db_paths: list[Path] = []
    for shard_dir in shard_dirs:
        try:
            db_paths.append(_find_duckdb(shard_dir))
        except FileNotFoundError as exc:
            print(f"  WARNING: {exc}")

    _print_preview(shard_dirs=shard_dirs, shard_paths=db_paths, output_dir=output_dir)
    if args.dry_run:
        return 0
    if not args.yes:
        print(
            "ERROR: refusing to overwrite merged output without --yes. Use --dry-run for preview.",
            file=sys.stderr,
        )
        return 2

    staged_output_dir = output_dir.parent / f".{output_dir.name}.tmp-{uuid.uuid4().hex[:8]}"
    lock_path = output_dir.parent / f".{output_dir.name}.merge.lock"
    staged_output_dir.mkdir(parents=True, exist_ok=False)
    backup_path: Path | None = None

    try:
        with exclusive_lock(
            lock_path, content=f"pid={os.getpid()}\nstarted_at={datetime.now(UTC).isoformat()}\n"
        ):
            print("[1/4] Merging DuckDB databases...")
            if db_paths:
                merged_db = staged_output_dir / "graph" / "scholar_knowledge.duckdb"
                stats = merge_duckdb(db_paths, merged_db)
                print(f"  Merged DB: {merged_db}")
                print(f"  Tables: {len(stats)}")
            else:
                print("  No DuckDB shards found")

            print("")
            print("[2/4] Merging JSONL files...")
            for filename, dedup_field in _JSONL_SPECS:
                destination = (
                    staged_output_dir / "academic" / "merged" / filename
                    if filename == "all_records.jsonl"
                    else staged_output_dir / "academic" / filename
                )
                count = merge_jsonl(
                    shard_dirs,
                    filename,
                    destination,
                    dedup_field=dedup_field,
                )
                print(f"  {filename}: {count} rows")

            print("")
            print("[3/4] Collecting JSON reports...")
            for report_name in (
                "topic_quality_report.json",
                "topic_selection_report.json",
                "benchmark_report.json",
                "qc_report.json",
            ):
                merge_json_reports(
                    shard_dirs,
                    report_name,
                    staged_output_dir / "reports" / report_name,
                )
                print(f"  {report_name}")

            print("")
            print("[4/4] Publishing staged output...")
            backup_path = atomic_replace_path(
                staged_output_dir,
                output_dir,
                backup_suffix=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
            )
    except FileExistsError as exc:
        shutil.rmtree(staged_output_dir, ignore_errors=True)
        print(f"ERROR: merge already in progress for {output_dir}: {exc}", file=sys.stderr)
        return 3
    except Exception:
        shutil.rmtree(staged_output_dir, ignore_errors=True)
        raise

    print("")
    print("Merge completed.")
    print(f"  Output: {output_dir}")
    if backup_path is not None:
        print(f"  Previous output preserved at: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
