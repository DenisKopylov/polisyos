#!/usr/bin/env python3
"""Canonical variable auto-approval with preview and staged publish."""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from tools._lib.imports import repo_root_from

if __package__ in {None, ""}:
    repo_root = repo_root_from(__file__)
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "src"))

import duckdb

from tools._lib.fs import atomic_replace_path, atomic_write_json, normalize_filesystem_path

DEFAULT_ORIG_ROOT = Path("/data/output/policyos_fullprod_1000t_20260324")
DEFAULT_OUTPUT_ROOT = Path("/data/output/policyos_fullprod_1000t_20260324_canonical_remap")
DEFAULT_TOPICS_DIR = Path("/data/topics")


@dataclass(frozen=True)
class RunPaths:
    orig_root: Path
    orig_db: Path
    output_root: Path
    output_db: Path
    report_path: Path
    topics_dir: Path

    def with_output_root(self, output_root: Path) -> RunPaths:
        return RunPaths(
            orig_root=self.orig_root,
            orig_db=self.orig_db,
            output_root=output_root,
            output_db=output_root / "academic" / "graph" / "scholar_knowledge.duckdb",
            report_path=output_root / "auto_approve_report.json",
            topics_dir=self.topics_dir,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk-approve canonical variable mappings")
    parser.add_argument("--orig-root", type=Path, default=DEFAULT_ORIG_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--topics-dir", type=Path, default=DEFAULT_TOPICS_DIR)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview affected rows without creating the remap snapshot",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm replacement of the output root with a newly staged remap snapshot",
    )
    return parser.parse_args()


def _build_paths(args: argparse.Namespace) -> RunPaths:
    orig_root = normalize_filesystem_path(
        args.orig_root,
        kind="original snapshot root",
        must_exist=True,
        allow_directory=True,
    )
    output_root = normalize_filesystem_path(
        args.output_root,
        kind="output snapshot root",
        must_exist=False,
        allow_directory=True,
    )
    topics_dir = normalize_filesystem_path(
        args.topics_dir,
        kind="topics directory",
        must_exist=True,
        allow_directory=True,
    )
    orig_db = normalize_filesystem_path(
        orig_root / "academic" / "graph" / "scholar_knowledge.duckdb",
        kind="original DuckDB",
        must_exist=True,
        allow_directory=False,
    )
    if output_root == orig_root:
        raise ValueError("output root must differ from original snapshot root")
    return RunPaths(
        orig_root=orig_root,
        orig_db=orig_db,
        output_root=output_root,
        output_db=output_root / "academic" / "graph" / "scholar_knowledge.duckdb",
        report_path=output_root / "auto_approve_report.json",
        topics_dir=topics_dir,
    )


def _collect_preview(paths: RunPaths) -> dict[str, object]:
    con = duckdb.connect(str(paths.orig_db), read_only=True)
    try:
        total_cache = con.execute("SELECT COUNT(*) FROM ac_skg_canonization_cache").fetchone()[0]
        total_variables = con.execute("SELECT COUNT(*) FROM ac_skg_variables").fetchone()[0]
        unapproved_cache = con.execute(
            "SELECT COUNT(*) FROM ac_skg_canonization_cache WHERE approved = FALSE"
        ).fetchone()[0]
        identity_count = con.execute(
            """
            SELECT COUNT(*)
            FROM ac_skg_canonization_cache
            WHERE approved = FALSE AND raw_name = canonical_name
            """
        ).fetchone()[0]
        non_identity_count = con.execute(
            """
            SELECT COUNT(*)
            FROM ac_skg_canonization_cache
            WHERE approved = FALSE AND raw_name != canonical_name
            """
        ).fetchone()[0]
        approved_variables = con.execute(
            "SELECT COUNT(*) FROM ac_skg_variables WHERE is_approved_canonical = TRUE"
        ).fetchone()[0]
        family_edges = con.execute("SELECT COUNT(*) FROM ac_skg_family_edges").fetchone()[0]
        contested_edges = con.execute("SELECT COUNT(*) FROM ac_skg_contested_edges").fetchone()[0]
    finally:
        con.close()

    return {
        "orig_root": str(paths.orig_root),
        "orig_db": str(paths.orig_db),
        "output_root": str(paths.output_root),
        "topics_dir": str(paths.topics_dir),
        "cache_total": int(total_cache),
        "cache_unapproved": int(unapproved_cache),
        "cache_identity_candidates": int(identity_count),
        "cache_non_identity_candidates": int(non_identity_count),
        "variables_total": int(total_variables),
        "variables_approved_before": int(approved_variables),
        "variables_pending": int(total_variables - approved_variables),
        "family_edges_before": int(family_edges),
        "contested_edges_before": int(contested_edges),
    }


def _print_preview(preview: dict[str, object]) -> None:
    print("=" * 60)
    print("  CANONICAL VARIABLE AUTO-APPROVAL PREVIEW")
    print("=" * 60)
    print(f"  Original root:   {preview['orig_root']}")
    print(f"  Original DB:     {preview['orig_db']}")
    print(f"  Output root:     {preview['output_root']}")
    print(f"  Topics dir:      {preview['topics_dir']}")
    print("")
    print("  Affected rows/items:")
    print(f"    Cache rows total:         {preview['cache_total']}")
    print(f"    Cache rows to approve:    {preview['cache_unapproved']}")
    print(f"      identity mappings:      {preview['cache_identity_candidates']}")
    print(f"      non-identity mappings:  {preview['cache_non_identity_candidates']}")
    print(f"    Variables total:          {preview['variables_total']}")
    print(f"    Variables pending:        {preview['variables_pending']}")
    print(f"    Family edges before:      {preview['family_edges_before']}")
    print(f"    Contested edges before:   {preview['contested_edges_before']}")
    print("")


def _step_copy_db(paths: RunPaths) -> None:
    print("=" * 60)
    print("STEP 1: Copy DuckDB to staged remap directory")
    print("=" * 60)
    paths.output_db.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Copying {paths.orig_db} -> {paths.output_db}")
    started = time.time()
    paths.output_root.mkdir(parents=True, exist_ok=True)
    paths.output_db.parent.mkdir(parents=True, exist_ok=True)
    paths.output_db.unlink(missing_ok=True)
    shutil.copy2(paths.orig_db, paths.output_db)
    elapsed = time.time() - started
    size_gb = paths.output_db.stat().st_size / 1e9
    print(f"  Done in {elapsed:.1f}s, size: {size_gb:.2f} GB")


def _step_bulk_approve(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    print()
    print("=" * 60)
    print("STEP 2: Bulk-approve cache entries")
    print("=" * 60)

    before = con.execute(
        "SELECT approved, COUNT(*) FROM ac_skg_canonization_cache GROUP BY approved"
    ).fetchall()
    print("  Before: " + str(dict(before)))

    identity_count = con.execute(
        """
        SELECT COUNT(*)
        FROM ac_skg_canonization_cache
        WHERE approved = FALSE AND raw_name = canonical_name
        """
    ).fetchone()[0]
    non_identity_count = con.execute(
        """
        SELECT COUNT(*)
        FROM ac_skg_canonization_cache
        WHERE approved = FALSE AND raw_name != canonical_name
        """
    ).fetchone()[0]
    print("  Identity (raw==suggested): %d" % identity_count)
    print("  Non-identity (has mapping): %d" % non_identity_count)

    started = time.time()
    con.execute("UPDATE ac_skg_canonization_cache SET approved = TRUE WHERE approved = FALSE")
    con.execute("CHECKPOINT")
    elapsed = time.time() - started

    after = con.execute(
        "SELECT approved, COUNT(*) FROM ac_skg_canonization_cache GROUP BY approved"
    ).fetchall()
    print("  After:  " + str(dict(after)))
    print("  Approved %d entries in %.1fs" % (identity_count + non_identity_count, elapsed))

    return {
        "identity_approved": identity_count,
        "non_identity_approved": non_identity_count,
        "total_approved": identity_count + non_identity_count,
    }


def _step_update_variables(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    print()
    print("=" * 60)
    print("STEP 3: Update variables table with approved mappings")
    print("=" * 60)

    total_vars = con.execute("SELECT COUNT(*) FROM ac_skg_variables").fetchone()[0]
    approved_before = con.execute(
        "SELECT COUNT(*) FROM ac_skg_variables WHERE is_approved_canonical = TRUE"
    ).fetchone()[0]
    print("  Total variables: %d" % total_vars)
    print("  Approved before: %d" % approved_before)

    started = time.time()
    con.execute(
        """
        UPDATE ac_skg_variables v
        SET is_approved_canonical = TRUE,
            approved_canonical_name = c.canonical_name,
            approved_parent_name = CASE
                WHEN POSITION('.' IN c.canonical_name) > 0
                THEN SPLIT_PART(c.canonical_name, '.', 1)
                ELSE NULL
            END,
            resolution_method = CASE
                WHEN v.resolution_method = '' OR v.resolution_method IS NULL
                    OR v.resolution_method = 'unresolved'
                THEN 'auto_approved'
                ELSE v.resolution_method
            END,
            resolution_confidence = GREATEST(v.resolution_confidence, 0.85)
        FROM ac_skg_canonization_cache c
        WHERE c.approved = TRUE
          AND LOWER(v.canonical_name) = c.raw_name
          AND v.is_approved_canonical = FALSE
        """
    )

    con.execute("CHECKPOINT")
    elapsed = time.time() - started

    approved_after = con.execute(
        "SELECT COUNT(*) FROM ac_skg_variables WHERE is_approved_canonical = TRUE"
    ).fetchone()[0]
    still_unapproved = con.execute(
        "SELECT COUNT(*) FROM ac_skg_variables WHERE is_approved_canonical = FALSE"
    ).fetchone()[0]

    print("  Approved after:  %d (+%d)" % (approved_after, approved_after - approved_before))
    print("  Still unapproved: %d" % still_unapproved)
    print("  Done in %.1fs" % elapsed)

    return {
        "variables_total": total_vars,
        "approved_before": approved_before,
        "approved_after": approved_after,
        "newly_approved": approved_after - approved_before,
        "still_unapproved": still_unapproved,
    }


def _step_resolve_remaining(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    print()
    print("=" * 60)
    print("STEP 4: Re-resolve remaining unapproved variables")
    print("=" * 60)

    from polisyos.academic.knowledge.canonical_resolver import CanonicalVariableResolver

    resolver = CanonicalVariableResolver.from_connection(con)
    print("  Resolver approved names: %d" % len(resolver._approved_set))

    unapproved = con.execute(
        """
        SELECT canonical_name, mention_count
        FROM ac_skg_variables
        WHERE is_approved_canonical = FALSE
        ORDER BY mention_count DESC
        """
    ).fetchall()
    print("  Unapproved variables to re-resolve: %d" % len(unapproved))

    resolved_count = 0
    still_unresolved = 0
    methods: dict[str, int] = {}
    started = time.time()

    for index, (var_name, _) in enumerate(unapproved):
        if index > 0 and index % 5000 == 0:
            elapsed = time.time() - started
            print(
                "    Progress: %d/%d, resolved: %d, elapsed: %.0fs"
                % (index, len(unapproved), resolved_count, elapsed)
            )

        result = resolver.resolve(str(var_name))
        if result.approved and result.canonical_name:
            resolved_count += 1
            methods[result.method] = methods.get(result.method, 0) + 1
            con.execute(
                """
                UPDATE ac_skg_variables
                SET is_approved_canonical = TRUE,
                    approved_canonical_name = ?,
                    approved_parent_name = CASE
                        WHEN POSITION('.' IN ?) > 0
                        THEN SPLIT_PART(?, '.', 1)
                        ELSE NULL
                    END,
                    resolution_method = ?,
                    resolution_confidence = ?
                WHERE canonical_name = ?
                """,
                [
                    result.canonical_name,
                    result.canonical_name,
                    result.canonical_name,
                    result.method,
                    float(result.confidence),
                    var_name,
                ],
            )
            resolver.persist_resolution(con, result)
        else:
            still_unresolved += 1
            if result.canonical_name:
                resolver.persist_resolution(con, result)

    con.execute("CHECKPOINT")
    elapsed = time.time() - started

    print("  Newly resolved: %d" % resolved_count)
    print("  Still unresolved: %d" % still_unresolved)
    print("  Methods: " + str(methods))
    print("  Done in %.1fs" % elapsed)

    final_approved = con.execute(
        "SELECT COUNT(*) FROM ac_skg_variables WHERE is_approved_canonical = TRUE"
    ).fetchone()[0]
    final_total = con.execute("SELECT COUNT(*) FROM ac_skg_variables").fetchone()[0]
    pct = 100 * final_approved / max(1, final_total)
    print("  Final: %d/%d approved (%.1f%%)" % (final_approved, final_total, pct))

    return {
        "newly_resolved": resolved_count,
        "still_unresolved": still_unresolved,
        "methods": methods,
        "final_approved": final_approved,
        "final_total": final_total,
        "final_pct": round(pct, 2),
    }


def _step_run_edge_synthesize(paths: RunPaths) -> dict[str, object]:
    print()
    print("=" * 60)
    print("STEP 5: Re-run edge_synthesize")
    print("=" * 60)

    from polisyos.academic.batch.config import AcademicBatchConfig
    from polisyos.academic.batch.edge_synthesize import run_edge_synthesize

    config = AcademicBatchConfig(
        snapshot_root=paths.output_root,
        topics_dir=paths.topics_dir,
        stages=frozenset({"edge_synthesize"}),
        target_per_topic=5000,
        article_target_fulltext_per_topic=1000,
    )

    print("  db_path: " + str(config.db_path))
    print("  canonical_review_queue_path: " + str(config.canonical_review_queue_path))
    assert str(config.db_path) == str(paths.output_db), (
        "db_path mismatch: %s vs %s" % (config.db_path, paths.output_db)
    )

    started = time.time()
    metrics = run_edge_synthesize(config)
    elapsed = time.time() - started

    print("  Family edges: %d" % metrics.get("family_edges", 0))
    print("  Contested edges: %d" % metrics.get("contested_edges", 0))
    print("  Review queue: %d" % metrics.get("review_queue", 0))
    print("  Resolution rate: %.1f%%" % metrics.get("canonical_resolution_rate_pct", 0))
    print("  Done in %.1fs" % elapsed)

    return {**metrics, "elapsed_s": round(elapsed, 1)}


def _run_workflow(paths: RunPaths) -> dict[str, object]:
    started = time.time()
    print("=" * 60)
    print("  CANONICAL VARIABLE AUTO-APPROVAL")
    print("  Started: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    report: dict[str, object] = {}
    _step_copy_db(paths)

    con = duckdb.connect(str(paths.output_db))
    try:
        report["cache_approval"] = _step_bulk_approve(con)
        report["variables_update"] = _step_update_variables(con)
        report["re_resolution"] = _step_resolve_remaining(con)
    finally:
        con.close()

    report["edge_synthesize"] = _step_run_edge_synthesize(paths)

    orig_con = duckdb.connect(str(paths.orig_db), read_only=True)
    try:
        orig_family = orig_con.execute("SELECT COUNT(*) FROM ac_skg_family_edges").fetchone()[0]
        orig_contested = orig_con.execute("SELECT COUNT(*) FROM ac_skg_contested_edges").fetchone()[0]
    finally:
        orig_con.close()

    new_family = report["edge_synthesize"].get("family_edges", 0)
    new_contested = report["edge_synthesize"].get("contested_edges", 0)
    increase_pct = round(100 * (new_family - orig_family) / max(1, orig_family), 1)

    report["comparison"] = {
        "original_family_edges": orig_family,
        "new_family_edges": new_family,
        "family_edge_increase": new_family - orig_family,
        "family_edge_increase_pct": increase_pct,
        "original_contested_edges": orig_contested,
        "new_contested_edges": new_contested,
    }
    report["paths"] = {
        "orig_root": str(paths.orig_root),
        "orig_db": str(paths.orig_db),
        "output_root": str(paths.output_root),
        "output_db": str(paths.output_db),
        "topics_dir": str(paths.topics_dir),
    }
    report["timing"] = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(time.time() - started, 1),
    }

    atomic_write_json(paths.report_path, report)
    return report


def main() -> int:
    args = _parse_args()
    paths = _build_paths(args)
    preview = _collect_preview(paths)
    _print_preview(preview)

    if args.dry_run:
        return 0
    if not args.yes:
        print("ERROR: refusing to publish remap snapshot without --yes. Use --dry-run for preview.", file=sys.stderr)
        return 2

    staged_root = paths.output_root.parent / f".{paths.output_root.name}.tmp-{uuid.uuid4().hex[:8]}"
    staged_paths = paths.with_output_root(staged_root)
    staged_root.mkdir(parents=True, exist_ok=False)

    try:
        report = _run_workflow(staged_paths)
        backup_path = atomic_replace_path(staged_root, paths.output_root)
    except Exception:
        if staged_root.exists():
            shutil.rmtree(staged_root, ignore_errors=True)
        raise

    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    vars_approved = int(report["variables_update"]["newly_approved"])
    vars_resolved = int(report["re_resolution"]["newly_resolved"])
    comparison = report["comparison"]
    print("  Cache entries approved: %d" % report["cache_approval"]["total_approved"])
    print("  Variables: %d direct + %d re-resolved = %d" % (vars_approved, vars_resolved, vars_approved + vars_resolved))
    print(
        "  Family edges: %d -> %d (+%d, %+.1f%%)"
        % (
            comparison["original_family_edges"],
            comparison["new_family_edges"],
            comparison["family_edge_increase"],
            comparison["family_edge_increase_pct"],
        )
    )
    print(
        "  Contested edges: %d -> %d"
        % (comparison["original_contested_edges"], comparison["new_contested_edges"])
    )
    print("  Approval rate: %.1f%%" % report["re_resolution"]["final_pct"])
    print("  Report: " + str(paths.report_path))
    print("  Remap DB: " + str(paths.output_db))
    if backup_path is not None:
        print("  Previous output preserved at: " + str(backup_path))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
