"""CLI for staged dataset catalog pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from polisyos.data_forge.domains.catalog.batch.config import DEFAULT_RUN_STAGES, DatasetBatchConfig

_STAGE_ALIAS = {
    "merge-dedup": "merge_dedup",
    "graph-load": "graph_load",
    "graph-index": "graph_index",
    "core-sources-ingest": "core_sources_ingest",
}


def _normalize_stage_name(name: str) -> str:
    return _STAGE_ALIAS.get(name, name.replace("-", "_"))


def _parse_stages(raw: str | None) -> frozenset[str]:
    if not raw:
        return DEFAULT_RUN_STAGES
    items = [_normalize_stage_name(v.strip()) for v in raw.split(",") if v.strip()]
    return frozenset(items)


def _parse_sources(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(sorted({value.strip() for value in raw.split(",") if value.strip()}))


def _parse_countries(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(sorted({value.strip().upper() for value in raw.split(",") if value.strip()}))


def _parse_year_window(raw: str | None) -> tuple[int, int]:
    if not raw:
        return (2018, 2022)
    parts = [part.strip() for part in str(raw).split(":") if part.strip()]
    if len(parts) != 2:
        raise ValueError("--year-window must be START:END")
    return (int(parts[0]), int(parts[1]))


def _build_config(args: argparse.Namespace, *, stages: frozenset[str]) -> DatasetBatchConfig:
    return DatasetBatchConfig(
        snapshot_root=Path(args.snapshot_root),
        stages=stages,
        resume=bool(getattr(args, "resume", False)),
        registry_path=Path(args.registry_path) if getattr(args, "registry_path", None) else None,
        metrics_map_path=Path(args.metrics_map) if getattr(args, "metrics_map", None) else None,
        wave=getattr(args, "wave", None),
        run_profile=getattr(args, "run_profile", "prod_full"),
        max_datasets_per_source=int(getattr(args, "max_datasets_per_source", 100_000)),
        promoted_sources=_parse_sources(getattr(args, "promoted_sources", None)),
        date_start=getattr(args, "date_start", None),
        date_end=getattr(args, "date_end", None),
        country_scope=getattr(args, "country_scope", "regional_extended"),
        active_countries=_parse_countries(getattr(args, "active_countries", None)),
        active_year_window=_parse_year_window(getattr(args, "year_window", None)),
        observation_mode=getattr(args, "observation_mode", "all"),
        resume_mode=getattr(args, "resume_mode", "smart"),
        preflight_sources=_parse_sources(getattr(args, "preflight_sources", None)),
        preflight_only=bool(getattr(args, "preflight_only", False)),
        defer_unsupported_observation_plans=not bool(
            getattr(args, "fail_on_unsupported_observation_plans", False)
        ),
        fail_fast_qc=bool(getattr(args, "fail_fast", True)),
    )


async def _run_single_stage(args: argparse.Namespace, stage: str) -> None:
    from polisyos.data_forge.domains.catalog.batch.benchmark import run_benchmark
    from polisyos.data_forge.domains.catalog.batch.core_sources_ingest import (
        run_core_sources_ingest_async,
    )
    from polisyos.data_forge.domains.catalog.batch.dedup import merge_and_dedup
    from polisyos.data_forge.domains.catalog.batch.embedder import run_embed
    from polisyos.data_forge.domains.catalog.batch.graph_builder import (
        run_graph_index,
        run_graph_load,
    )
    from polisyos.data_forge.domains.catalog.batch.harvester import harvest_sources
    from polisyos.data_forge.domains.catalog.batch.normalizer import normalize_raw_sources
    from polisyos.data_forge.domains.catalog.batch.pipeline import run_dataset_pipeline
    from polisyos.data_forge.domains.catalog.batch.publish import run_publish
    from polisyos.data_forge.domains.catalog.batch.qc import run_qc

    stage_name = _normalize_stage_name(stage)
    if stage_name == "run":
        cfg = _build_config(args, stages=_parse_stages(getattr(args, "stages", None)))
        stats = await run_dataset_pipeline(cfg, thermal=bool(getattr(args, "thermal", False)))
        for _name, _duration in sorted(stats.stage_times.items()):
            pass
        return

    cfg = _build_config(args, stages=frozenset({stage_name}))
    if stage_name == "harvest":
        await harvest_sources(cfg)
    elif stage_name == "normalize":
        normalize_raw_sources(cfg)
    elif stage_name == "merge_dedup":
        stats = merge_and_dedup(cfg)
    elif stage_name == "graph_load":
        stats = run_graph_load(cfg)
    elif stage_name == "graph_index":
        run_graph_index(cfg)
    elif stage_name == "core_sources_ingest":
        stats = await run_core_sources_ingest_async(cfg)
    elif stage_name == "embed":
        run_embed(cfg, thermal=bool(getattr(args, "thermal", False)))
    elif stage_name == "benchmark":
        run_benchmark(cfg)
    elif stage_name == "qc":
        run_qc(cfg, fail_fast=bool(getattr(args, "fail_fast", True)))
    elif stage_name == "publish":
        run_publish(cfg)
    else:
        raise ValueError(f"Unsupported stage command: {stage}")


def _cmd_stats(args: argparse.Namespace) -> None:
    import duckdb

    con = duckdb.connect(str(args.db_path), read_only=True)
    try:
        con.execute("SELECT count(*) FROM ds_datasets").fetchone()[0]
        con.execute("SELECT count(*) FROM ds_distributions").fetchone()[0]
        sources = con.execute(
            "SELECT source, count(*) FROM ds_datasets GROUP BY source ORDER BY count(*) DESC"
        ).fetchall()
    finally:
        con.close()

    for _source, _count in sources:
        pass


def _cmd_search(args: argparse.Namespace) -> None:
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph

    graph = DatasetCatalogGraph(db_path=Path(args.db_path), index_dir=Path(args.db_path).parent)
    try:
        results = graph.search_datasets(args.query, top_k=args.top_k)
    finally:
        graph.close()

    if not results:
        return
    for _i, _row in enumerate(results, start=1):
        pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dataset catalog staged CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--snapshot-root", required=True)
    common.add_argument("--metrics-map", default=None, help="Path to metrics_map YAML")
    common.add_argument(
        "--promoted-sources", default=None, help="Comma-separated promoted/core sources"
    )
    common.add_argument(
        "--run-profile",
        default="prod_full",
        choices=[
            "prod_full",
            "prod_core_blocking",
            "rest_backfill",
            "catalog_refresh",
            "preflight_core",
            "observations_backfill",
        ],
        help="Source selection profile for manual snapshot runs",
    )
    common.add_argument(
        "--date-start", default=None, help="Optional manual history override start date"
    )
    common.add_argument(
        "--date-end", default=None, help="Optional manual history override end date"
    )
    common.add_argument("--country-scope", default="regional_extended")
    common.add_argument(
        "--active-countries", default=None, help="Comma-separated ISO2 country codes override"
    )
    common.add_argument(
        "--year-window", default=None, help="Observation/support year window as START:END"
    )
    common.add_argument(
        "--observation-mode",
        default="all",
        choices=["all", "core", "backfill"],
        help="Observation planner/runtime phase selection",
    )
    common.add_argument("--resume-mode", default="smart", choices=["smart", "force", "off"])
    common.add_argument(
        "--preflight-sources", default=None, help="Comma-separated source override for preflight"
    )
    common.add_argument("--preflight-only", action="store_true")
    common.add_argument(
        "--fail-on-unsupported-observation-plans",
        action="store_true",
        help="Fail ingest instead of deferring unsupported observation shards",
    )

    harvest = sub.add_parser("harvest", parents=[common], help="Harvest raw metadata by wave")
    harvest.add_argument("--wave", choices=["A", "B", "C", "D"], required=False)
    harvest.add_argument("--resume", action="store_true")
    harvest.add_argument("--registry-path", default=None)
    harvest.add_argument("--max-datasets-per-source", type=int, default=100000)

    sub.add_parser("normalize", parents=[common], help="Normalize raw snapshots per source")
    sub.add_parser("merge-dedup", parents=[common], help="Merge normalized files and deduplicate")
    sub.add_parser("graph-load", parents=[common], help="Load merged records into DuckDB")
    sub.add_parser("graph-index", parents=[common], help="Build DuckDB indexes")
    sub.add_parser(
        "core-sources-ingest",
        parents=[common],
        help="Ingest transportability registry/alignments/observations for core international sources",
    )

    embed = sub.add_parser("embed", parents=[common], help="Build local embeddings + HNSW")
    embed.add_argument("--thermal", action="store_true")

    sub.add_parser(
        "benchmark", parents=[common], help="Run consumer benchmark suites on built catalog"
    )

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
    """Main helper."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = _build_parser()
    args = parser.parse_args()

    if args.command in {
        "harvest",
        "normalize",
        "merge-dedup",
        "graph-load",
        "graph-index",
        "core-sources-ingest",
        "embed",
        "benchmark",
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
