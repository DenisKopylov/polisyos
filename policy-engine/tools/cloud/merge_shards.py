"""
Merge 3 pipeline output shards into a single unified graph.

Usage:
    python merge_shards.py /data/shard_1 /data/shard_2 /data/shard_3 --output /data/merged

Each shard_N directory should contain:
    academic/graph/scholar_knowledge.duckdb
    academic/published_claims.jsonl
    academic/merged/all_records.jsonl
    academic/*.json  (stage reports)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb not installed. Run: pip install duckdb")
    sys.exit(1)


# ---------------------------------------------------------------------------
# DuckDB tables to merge (order matters for foreign keys)
# ---------------------------------------------------------------------------
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


def _find_duckdb(shard_dir: Path) -> Path:
    """Locate the DuckDB file inside a shard output directory."""
    candidates = list(shard_dir.rglob("scholar_knowledge.duckdb"))
    if not candidates:
        raise FileNotFoundError(f"No scholar_knowledge.duckdb found in {shard_dir}")
    return candidates[0]


def _find_jsonl(shard_dir: Path, filename: str) -> Path | None:
    """Locate a JSONL file inside a shard."""
    candidates = list(shard_dir.rglob(filename))
    return candidates[0] if candidates else None


def _table_exists(con: duckdb.DuckDBPyConnection, table: str, schema: str = "main") -> bool:
    result = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
        [schema, table],
    ).fetchone()
    return bool(result and result[0] > 0)


def merge_duckdb(shard_paths: list[Path], output_path: Path) -> dict[str, int]:
    """Merge multiple DuckDB shards into one, deduplicating by primary key."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy first shard as base
    print(f"  Base shard: {shard_paths[0]}")
    shutil.copy2(shard_paths[0], output_path)

    con = duckdb.connect(str(output_path))
    stats: dict[str, int] = {}

    # Attach remaining shards
    for i, shard_db in enumerate(shard_paths[1:], start=2):
        alias = f"shard{i}"
        print(f"  Attaching shard {i}: {shard_db}")
        con.execute(f"ATTACH DATABASE '{shard_db}' AS {alias} (READ_ONLY)")

        all_tables = _CORE_TABLES + _SKG_TABLES
        for table in all_tables:
            if not _table_exists(con, table, alias):
                continue
            if not _table_exists(con, table, "main"):
                continue

            # Get columns
            cols_result = con.execute(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_schema = 'main' AND table_name = '{table}' "
                f"ORDER BY ordinal_position"
            ).fetchall()
            cols = [r[0] for r in cols_result]

            # Determine dedup key
            dedup_key = _get_dedup_key(table, cols)

            if dedup_key:
                # Insert only rows not already in main
                where_clause = " AND ".join(
                    f"s.{k} = m.{k}" for k in dedup_key
                )
                con.execute(
                    f"INSERT INTO main.{table} "
                    f"SELECT s.* FROM {alias}.{table} s "
                    f"WHERE NOT EXISTS ("
                    f"  SELECT 1 FROM main.{table} m WHERE {where_clause}"
                    f")"
                )
            else:
                # No dedup key — append all
                con.execute(f"INSERT INTO main.{table} SELECT * FROM {alias}.{table}")

        con.execute(f"DETACH DATABASE {alias}")

    # Collect stats
    for table in _CORE_TABLES + _SKG_TABLES:
        if _table_exists(con, table):
            count = con.execute(f"SELECT count(*) FROM {table}").fetchone()
            stats[table] = count[0] if count else 0

    con.close()
    return stats


def _get_dedup_key(table: str, cols: list[str]) -> list[str] | None:
    """Return the natural dedup key for a table, or None for append-all."""
    keys: dict[str, list[str]] = {
        "ac_topics": ["topic_id"],
        "ac_runs": ["run_id"],
        "ac_works": ["id"],
        "ac_work_concepts": ["work_id", "topic_id", "concept"] if "concept" in cols else None,
        "ac_topic_selections": ["run_id", "topic_id", "work_id"],
        "ac_article_extractions": ["extraction_id"] if "extraction_id" in cols else ["run_id", "work_id", "extraction_mode"],
        "ac_causal_claims_raw": ["id"] if "id" in cols else ["work_id", "cause", "effect"],
        "ac_claim_adjudications": ["claim_id"] if "claim_id" in cols else None,
        "ac_causal_claims": ["id"] if "id" in cols else ["work_id", "cause", "effect"],
        "ac_parameter_estimates": ["id"] if "id" in cols else ["work_id", "variable_name", "estimate"],
        "ac_boundary_conditions": ["boundary_id"] if "boundary_id" in cols else None,
        "ac_skg_articles": ["openalex_id"],
        "ac_skg_variables": ["variable_name"] if "variable_name" in cols else ["canonical_name"],
        "ac_skg_edges": ["edge_id"] if "edge_id" in cols else ["src", "dst", "direction"],
        "ac_skg_edge_evidence": ["edge_id", "claim_id", "openalex_id"] if "claim_id" in cols else None,
        "ac_skg_family_edges": ["family_edge_id"] if "family_edge_id" in cols else ["src_family", "dst_family", "direction"],
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
    # Validate all key columns exist
    if all(k in cols for k in key):
        return key
    return None


def merge_jsonl(shard_dirs: list[Path], filename: str, output_path: Path, dedup_field: str | None = None) -> int:
    """Merge JSONL files from shards, optionally deduplicating by a field."""
    seen: set[str] = set()
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as out:
        for shard in shard_dirs:
            src = _find_jsonl(shard, filename)
            if not src:
                continue
            with open(src) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if dedup_field:
                        try:
                            row = json.loads(line)
                            key = str(row.get(dedup_field, ""))
                            if key in seen:
                                continue
                            seen.add(key)
                        except json.JSONDecodeError:
                            continue
                    out.write(line + "\n")
                    count += 1
    return count


def merge_json_reports(shard_dirs: list[Path], filename: str, output_path: Path) -> None:
    """Collect JSON reports from all shards into an array."""
    reports = []
    for i, shard in enumerate(shard_dirs, 1):
        candidates = list(shard.rglob(filename))
        for c in candidates:
            try:
                data = json.loads(c.read_text())
                data["_shard"] = i
                data["_shard_path"] = str(c)
                reports.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(reports, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge pipeline output shards")
    parser.add_argument("shards", nargs="+", help="Paths to shard output directories")
    parser.add_argument("--output", "-o", required=True, help="Output directory for merged results")
    args = parser.parse_args()

    shard_dirs = [Path(s) for s in args.shards]
    output_dir = Path(args.output)

    for sd in shard_dirs:
        if not sd.exists():
            print(f"ERROR: Shard directory not found: {sd}")
            sys.exit(1)

    print(f"Merging {len(shard_dirs)} shards into {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Merge DuckDB ---
    print("\n[1/4] Merging DuckDB databases...")
    db_paths = []
    for sd in shard_dirs:
        try:
            db_paths.append(_find_duckdb(sd))
        except FileNotFoundError as e:
            print(f"  WARNING: {e}")

    if db_paths:
        merged_db = output_dir / "graph" / "scholar_knowledge.duckdb"
        stats = merge_duckdb(db_paths, merged_db)
        print(f"  Merged DB: {merged_db}")
        for table, count in sorted(stats.items()):
            print(f"    {table}: {count} rows")
    else:
        print("  WARNING: No DuckDB files found")

    # --- 2. Merge JSONL files ---
    print("\n[2/4] Merging JSONL files...")
    jsonl_merges = [
        ("published_claims.jsonl", "claim_id"),
        ("published_claims_final.jsonl", "claim_id"),
        ("all_records.jsonl", "id"),
        ("raw_claim_candidates.jsonl", "claim_id"),
        ("raw_claim_candidates_final.jsonl", "claim_id"),
        ("resolve_extract_results.jsonl", "openalex_id"),
        ("resolve_extract_final_results.jsonl", "openalex_id"),
        ("resolve_finalize.jsonl", "id"),
        ("fulltext_resolved.jsonl", "work_id"),
        ("moderation_edges.jsonl", None),
        ("moderation_edges_clean.jsonl", None),
        ("context_attributes.jsonl", None),
        ("context_attributes_clean.jsonl", None),
        ("simulation_ready_numeric_estimates.jsonl", "numeric_id"),
    ]
    for filename, dedup in jsonl_merges:
        out = output_dir / filename
        count = merge_jsonl(shard_dirs, filename, out, dedup_field=dedup)
        if count:
            print(f"  {filename}: {count} records")

    # --- 3. Merge JSON reports ---
    print("\n[3/4] Collecting stage reports...")
    for report_name in ["qc_report.json", "resolve_extract.json", "transport_score.json", "harvest.json"]:
        out = output_dir / f"merged_{report_name}"
        merge_json_reports(shard_dirs, report_name, out)
        print(f"  {report_name} -> {out.name}")

    # --- 4. Summary ---
    print("\n[4/4] Summary")
    print(f"  Output directory: {output_dir}")
    total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    print(f"  Total size: {total_size / (1024 * 1024):.1f} MB")
    print("\nDone! Run QC on merged output to validate:")
    print(f"  python -m polisyos.academic.batch.cli qc --input {output_dir}")


if __name__ == "__main__":
    main()
