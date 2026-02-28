"""CLI for staged dataset catalog pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from polisyos.datasets.batch.config import ALL_STAGES, DatasetBatchConfig

_STAGE_ALIAS = {
    "merge-dedup": "merge_dedup",
    "graph-load": "graph_load",
    "graph-index": "graph_index",
}


def _normalize_stage_name(name: str) -> str:
    return _STAGE_ALIAS.get(name, name.replace("-", "_"))


def _parse_stages(raw: str | None) -> frozenset[str]:
    if not raw:
        return ALL_STAGES
    items = [_normalize_stage_name(v.strip()) for v in raw.split(",") if v.strip()]
    return frozenset(items)


def _build_config(args: argparse.Namespace, *, stages: frozenset[str]) -> DatasetBatchConfig:
    return DatasetBatchConfig(
        snapshot_root=Path(args.snapshot_root),
        stages=stages,
        resume=bool(getattr(args, "resume", False)),
        registry_path=Path(args.registry_path) if getattr(args, "registry_path", None) else None,
        wave=getattr(args, "wave", None),
        max_datasets_per_source=int(getattr(args, "max_datasets_per_source", 100_000)),
        fail_fast_qc=bool(getattr(args, "fail_fast", True)),
    )


async def _run_single_stage(args: argparse.Namespace, stage: str) -> None:
    from polisyos.datasets.batch.dedup import merge_and_dedup
    from polisyos.datasets.batch.embedder import run_embed
    from polisyos.datasets.batch.graph_builder import run_graph_index, run_graph_load
    from polisyos.datasets.batch.harvester import harvest_sources
    from polisyos.datasets.batch.normalizer import normalize_raw_sources
    from polisyos.datasets.batch.pipeline import run_dataset_pipeline
    from polisyos.datasets.batch.publish import run_publish
    from polisyos.datasets.batch.qc import run_qc

    stage_name = _normalize_stage_name(stage)
    if stage_name == "run":
        cfg = _build_config(args, stages=_parse_stages(getattr(args, "stages", None)))
        stats = await run_dataset_pipeline(cfg, thermal=bool(getattr(args, "thermal", False)))
        print(f"Done in {stats.elapsed_seconds:.1f}s")
        for name, duration in sorted(stats.stage_times.items()):
            print(f"  {name}: {duration:.1f}s")
        return

    cfg = _build_config(args, stages=frozenset({stage_name}))
    if stage_name == "harvest":
        records = await harvest_sources(cfg)
        print(f"Harvested sources: {len(records)}")
        print(f"Records: {sum(len(v) for v in records.values())}")
    elif stage_name == "normalize":
        counts = normalize_raw_sources(cfg)
        print(f"Normalized sources: {len(counts)}")
        print(f"Records: {sum(counts.values())}")
    elif stage_name == "merge_dedup":
        stats = merge_and_dedup(cfg)
        print(f"Merged: {stats.get('merged_records', 0)}")
        print(f"Duplicates: {stats.get('duplicates', 0)}")
    elif stage_name == "graph_load":
        stats = run_graph_load(cfg)
        print(f"Graph loaded: datasets={stats.datasets}, distributions={stats.distributions}")
    elif stage_name == "graph_index":
        run_graph_index(cfg)
        print("Graph indexes created")
    elif stage_name == "embed":
        embedded = run_embed(cfg, thermal=bool(getattr(args, "thermal", False)))
        print(f"Embedded datasets: {embedded}")
    elif stage_name == "qc":
        report = run_qc(cfg, fail_fast=bool(getattr(args, "fail_fast", True)))
        print(f"QC passed: {report.passed}")
        print(f"QC report: {cfg.qc_report_path}")
    elif stage_name == "publish":
        manifest = run_publish(cfg)
        print(f"Publish manifest: {manifest}")
    else:
        raise ValueError(f"Unsupported stage command: {stage}")


def _cmd_stats(args: argparse.Namespace) -> None:
    import duckdb

    con = duckdb.connect(str(args.db_path), read_only=True)
    try:
        ds_count = con.execute("SELECT count(*) FROM ds_datasets").fetchone()[0]
        dist_count = con.execute("SELECT count(*) FROM ds_distributions").fetchone()[0]
        sources = con.execute("SELECT source, count(*) FROM ds_datasets GROUP BY source ORDER BY count(*) DESC").fetchall()
    finally:
        con.close()

    print(f"Datasets: {ds_count}")
    print(f"Distributions: {dist_count}")
    for source, count in sources:
        print(f"  {source}: {count}")


def _cmd_search(args: argparse.Namespace) -> None:
    from polisyos.datasets.knowledge.search import DatasetCatalogGraph

    graph = DatasetCatalogGraph(db_path=Path(args.db_path), index_dir=Path(args.db_path).parent)
    try:
        results = graph.search_datasets(args.query, top_k=args.top_k)
    finally:
        graph.close()

    if not results:
        print("No results found")
        return
    for i, row in enumerate(results, start=1):
        print(f"[{i}] {row.title}")
        print(f"    source={row.source} agency={row.agency} dataset_id={row.dataset_id} similarity={row.similarity:.3f}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dataset catalog staged CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--snapshot-root", required=True)

    harvest = sub.add_parser("harvest", parents=[common], help="Harvest raw metadata by wave")
    harvest.add_argument("--wave", choices=["A", "B", "C", "D"], required=False)
    harvest.add_argument("--resume", action="store_true")
    harvest.add_argument("--registry-path", default=None)
    harvest.add_argument("--max-datasets-per-source", type=int, default=100000)

    sub.add_parser("normalize", parents=[common], help="Normalize raw snapshots per source")
    sub.add_parser("merge-dedup", parents=[common], help="Merge normalized files and deduplicate")
    sub.add_parser("graph-load", parents=[common], help="Load merged records into DuckDB")
    sub.add_parser("graph-index", parents=[common], help="Build DuckDB indexes")

    embed = sub.add_parser("embed", parents=[common], help="Build local embeddings + HNSW")
    embed.add_argument("--thermal", action="store_true")

    qc = sub.add_parser("qc", parents=[common], help="Run QC checks")
    qc.add_argument("--fail-fast", dest="fail_fast", action="store_true")
    qc.add_argument("--no-fail-fast", dest="fail_fast", action="store_false")
    qc.set_defaults(fail_fast=True)

    sub.add_parser("publish", parents=[common], help="Write publish manifest")

    run = sub.add_parser("run", parents=[common], help="Thin wrapper over staged commands")
    run.add_argument("--stages", default=None, help="Comma-separated stages")
    run.add_argument("--wave", choices=["A", "B", "C", "D"], required=False)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--registry-path", default=None)
    run.add_argument("--max-datasets-per-source", type=int, default=100000)
    run.add_argument("--thermal", action="store_true")
    run.add_argument("--fail-fast", dest="fail_fast", action="store_true")
    run.add_argument("--no-fail-fast", dest="fail_fast", action="store_false")
    run.set_defaults(fail_fast=True)

    stats = sub.add_parser("stats", help="Show DB counts")
    stats.add_argument("--db-path", required=True)

    search = sub.add_parser("search", help="Search in built catalog")
    search.add_argument("--db-path", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=10)

    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args()

    if args.command in {
        "harvest",
        "normalize",
        "merge-dedup",
        "graph-load",
        "graph-index",
        "embed",
        "qc",
        "publish",
        "run",
    }:
        asyncio.run(_run_single_stage(args, args.command))
        return

    if args.command == "stats":
        _cmd_stats(args)
        return
    if args.command == "search":
        _cmd_search(args)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
