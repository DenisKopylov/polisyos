"""CLI entry point for the Lex batch pipeline.

Usage::

    python -m polisyos.lex.batch run \
        --cards data/data_lex/edrnpa_cards_2026-02-08.xml \
        --texts data/data_lex/edrnpa_texts_2026-02-08.xml \
        --output-dir data/lex_knowledge \
        --stages all

    python -m polisyos.lex.batch stats --output-dir data/lex_knowledge

    python -m polisyos.lex.batch embed-batch submit --output-dir data/lex_knowledge
    python -m polisyos.lex.batch embed-batch collect --output-dir data/lex_knowledge
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path

from polisyos.lex.batch.config import ALL_STAGES, BatchConfig


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m polisyos.lex.batch",
        description="Lex batch pipeline: build a legal knowledge graph from ЄДРНПА XML.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_p = sub.add_parser("run", help="Run the batch pipeline")
    run_p.add_argument("--cards", required=True, type=Path, help="Path to cards XML")
    run_p.add_argument("--texts", required=True, type=Path, help="Path to texts XML")
    run_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    run_p.add_argument("--shard-count", type=int, default=1, help="Total number of shards")
    run_p.add_argument("--shard-index", type=int, default=0, help="Zero-based shard index")
    run_p.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete previous lex_knowledge outputs before run (full rebuild).",
    )
    run_p.add_argument("--gonka-api-key", default="", help="Gonka API key (or GONKA_API_KEY env)")
    run_p.add_argument("--gonka-base-url", default="https://api.gonkagate.com/v1")
    run_p.add_argument(
        "--gonka-disable-json-mode",
        action="store_true",
        help="Do not send response_format=json_object to Gonka chat/completions.",
    )
    run_p.add_argument("--llm-model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
    run_p.add_argument("--openai-api-key", default="", help="OpenAI API key (or OPENAI_API_KEY env)")
    run_p.add_argument("--parallel-llm", type=int, default=20, help="Max concurrent LLM requests")
    run_p.add_argument("--gonka-rate-limit-rps", type=float, default=5.0, help="Gonka request rate limit")
    run_p.add_argument("--max-retries", type=int, default=7, help="Max retries per LLM request on 429/5xx")
    run_p.add_argument("--llm-temperature", type=float, default=0.1, help="LLM temperature for SPO extraction")
    run_p.add_argument("--xml-parse-chunk", type=int, default=5000, help="Documents buffered per stream chunk")
    run_p.add_argument("--structure-workers", type=int, default=4, help="Worker processes for structure extraction")
    run_p.add_argument(
        "--disable-structure-paragraphs",
        action="store_true",
        help="Disable paragraph-level provision extraction.",
    )
    run_p.add_argument(
        "--structure-fallback-chunk-chars",
        type=int,
        default=1800,
        help="Fallback chunk size when article structure is missing.",
    )
    run_p.add_argument(
        "--structure-fallback-chunk-overlap",
        type=int,
        default=200,
        help="Fallback chunk overlap characters.",
    )
    run_p.add_argument("--spo-batch-docs", type=int, default=500, help="Documents per SPO checkpoint batch")
    run_p.add_argument("--spo-task-batch-size", type=int, default=1000, help="Max SPO asyncio tasks per gather")
    run_p.add_argument(
        "--spo-verify-mode",
        choices=("llm", "code"),
        default="llm",
        help="SPO verify pass mode: llm=second LLM pass, code=deterministic checks only.",
    )
    run_p.add_argument(
        "--spo-max-provisions-per-doc",
        type=int,
        default=None,
        help="Cap number of provision spans per document for SPO (smoke/debug).",
    )
    run_p.add_argument(
        "--disable-quality-gates",
        action="store_true",
        help="Disable SPO quality gate checks.",
    )
    run_p.add_argument(
        "--quality-warn-only",
        action="store_true",
        help="Warn-only quality mode (default behavior, kept for backward compatibility).",
    )
    run_p.add_argument(
        "--quality-fail-on-critical",
        action="store_true",
        help="Fail pipeline when critical quality gates fail.",
    )
    run_p.add_argument(
        "--quality-max-full-only-docs-pct",
        type=float,
        default=30.0,
        help="Max allowed percentage of full-only provision docs.",
    )
    run_p.add_argument(
        "--quality-max-empty-statement-rows-pct",
        type=float,
        default=12.0,
        help="Max allowed percentage of SPO rows with zero statements.",
    )
    run_p.add_argument(
        "--quality-max-oov-action-rate-pct",
        type=float,
        default=1.0,
        help="Max allowed OOV action rate in normalized statements.",
    )
    run_p.add_argument(
        "--quality-max-missing-quote-rate-pct",
        type=float,
        default=5.0,
        help="Max allowed missing-quote rate in statements.",
    )
    run_p.add_argument(
        "--quality-max-duplicate-anchor-rate-pct",
        type=float,
        default=0.1,
        help="Max allowed percentage of docs with duplicate anchors.",
    )
    run_p.add_argument(
        "--quality-min-provision-docs-for-doc-rate",
        type=int,
        default=25,
        help="Minimum provision docs before doc-rate gates are enforced.",
    )
    run_p.add_argument(
        "--quality-min-spo-rows-for-row-rate",
        type=int,
        default=50,
        help="Minimum SPO rows before row-rate gates are enforced.",
    )
    run_p.add_argument(
        "--quality-min-statements-for-statement-rate",
        type=int,
        default=100,
        help="Minimum statements before statement-rate gates are enforced.",
    )
    run_p.add_argument(
        "--status-filter", nargs="*", default=None,
        help="Filter by status, e.g. 'Чинний'",
    )
    run_p.add_argument(
        "--type-filter", nargs="*", default=None,
        help="Filter by doc type, e.g. 'Закон України'",
    )
    run_p.add_argument(
        "--stages", default="all",
        help=f"Comma-separated stages: {','.join(sorted(ALL_STAGES))} or 'all'",
    )
    run_p.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    run_p.add_argument(
        "--max-docs", type=int, default=None,
        help="Stop after processing this many NEW documents (use with --resume for batched runs)",
    )

    # --- stats ---
    stats_p = sub.add_parser("stats", help="Show graph statistics")
    stats_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")

    # --- search ---
    search_p = sub.add_parser("search", help="Interactive search")
    search_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    search_p.add_argument("--query", required=True, help="Search query")
    search_p.add_argument("--top-k", type=int, default=20, help="Number of results")

    # --- embed-batch ---
    embed_batch_p = sub.add_parser(
        "embed-batch",
        help="OpenAI Batch API workflow for embeddings",
    )
    embed_sub = embed_batch_p.add_subparsers(dest="embed_batch_command")

    embed_submit_p = embed_sub.add_parser("submit", help="Submit OpenAI embedding batches")
    embed_submit_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    embed_submit_p.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="DuckDB path (default: <output-dir>/lex_knowledge_graph.duckdb)",
    )
    embed_submit_p.add_argument("--openai-api-key", default="", help="OpenAI API key (or OPENAI_API_KEY env)")
    embed_submit_p.add_argument("--model", default="text-embedding-3-large")
    embed_submit_p.add_argument("--dimension", type=int, default=3072)
    embed_submit_p.add_argument("--chunk-size", type=int, default=5000)
    embed_submit_p.add_argument(
        "--tables",
        default="entities,facts,provisions",
        help="Comma-separated table keys: entities,facts,provisions",
    )
    embed_submit_p.add_argument("--max-input-tokens", type=int, default=8192)
    embed_submit_p.add_argument("--max-request-tokens", type=int, default=250_000)
    embed_submit_p.add_argument("--max-inputs-per-request", type=int, default=128)
    embed_submit_p.add_argument("--fallback-max-chars", type=int, default=12_000)

    embed_collect_p = embed_sub.add_parser(
        "collect",
        help="Collect completed embedding batches and build indexes",
    )
    embed_collect_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    embed_collect_p.add_argument("--openai-api-key", default="", help="OpenAI API key (or OPENAI_API_KEY env)")
    embed_collect_p.add_argument("--wait", action="store_true", help="Poll batches until completion")
    embed_collect_p.add_argument("--poll-interval-s", type=float, default=20.0)
    embed_collect_p.add_argument("--no-build-index", action="store_true", help="Only collect, skip index build")

    return parser


def _shard_slug(shard_count: int, shard_index: int) -> str:
    return f"shard_{shard_index:02d}_of_{shard_count:02d}"


def _shard_state_dir(output_dir: Path, *, shard_count: int, shard_index: int) -> Path:
    if shard_count > 1:
        return output_dir / "_shards" / _shard_slug(shard_count, shard_index)
    return output_dir


def _clean_lex_output(output_dir: Path, *, shard_count: int, shard_index: int) -> None:
    """Delete generated outputs for this run context."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if shard_count > 1 and shard_index == 0:
        shards_root = output_dir / "_shards"
        if shards_root.exists():
            shutil.rmtree(shards_root)

    state_dir = _shard_state_dir(
        output_dir,
        shard_count=shard_count,
        shard_index=shard_index,
    )
    state_dir.mkdir(parents=True, exist_ok=True)

    # Shard-local state.
    for rel_dir in ("openai_batches",):
        target = state_dir / rel_dir
        if target.exists():
            shutil.rmtree(target)

    for rel_file in (
        "progress.jsonl",
        "manifest.jsonl",
        "lex_knowledge_graph.duckdb",
    ):
        target = state_dir / rel_file
        if target.exists():
            target.unlink()

    for sidecar in state_dir.glob("lex_knowledge_graph.duckdb*"):
        if sidecar.is_file():
            sidecar.unlink()

    for pattern in ("*.npz", "*.hnsw"):
        for target in state_dir.glob(pattern):
            if target.is_file():
                target.unlink()

    # Shared outputs are wiped only by shard 0 (or non-sharded run).
    if shard_count == 1 or shard_index == 0:
        for rel_dir in ("provisions", "spo_results"):
            target = output_dir / rel_dir
            if target.exists():
                shutil.rmtree(target)


def _cmd_run(args: argparse.Namespace) -> None:
    if args.shard_count < 1:
        raise ValueError("--shard-count must be >= 1")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise ValueError("--shard-index must satisfy 0 <= shard-index < shard-count")

    if args.clean_output and args.resume:
        raise ValueError("--clean-output cannot be used together with --resume")

    if args.clean_output and args.shard_count > 1 and args.shard_index != 0:
        raise ValueError(
            "In sharded mode use --clean-output only on --shard-index 0 "
            "(clean once before launching all shards)."
        )
    if args.quality_warn_only and args.quality_fail_on_critical:
        raise ValueError(
            "--quality-warn-only and --quality-fail-on-critical are mutually exclusive"
        )

    if args.clean_output:
        _clean_lex_output(
            args.output_dir,
            shard_count=args.shard_count,
            shard_index=args.shard_index,
        )

    stages_str: str = args.stages
    if stages_str == "all":
        stages = ALL_STAGES
    else:
        stages = frozenset(s.strip() for s in stages_str.split(","))

    config = BatchConfig(
        cards_path=args.cards,
        texts_path=args.texts,
        output_dir=args.output_dir,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
        gonka_api_key=args.gonka_api_key,
        gonka_base_url=args.gonka_base_url,
        gonka_disable_json_mode=args.gonka_disable_json_mode,
        llm_model=args.llm_model,
        openai_api_key=args.openai_api_key,
        max_concurrent_llm=args.parallel_llm,
        rate_limit_rps=args.gonka_rate_limit_rps,
        max_retries=args.max_retries,
        llm_temperature=args.llm_temperature,
        stages=stages,
        resume=args.resume,
        xml_parse_chunk=args.xml_parse_chunk,
        structure_workers=args.structure_workers,
        structure_enable_paragraphs=not args.disable_structure_paragraphs,
        structure_fallback_chunk_chars=args.structure_fallback_chunk_chars,
        structure_fallback_chunk_overlap=args.structure_fallback_chunk_overlap,
        spo_batch_docs=args.spo_batch_docs,
        spo_task_batch_size=args.spo_task_batch_size,
        spo_verify_mode=args.spo_verify_mode,
        spo_max_provisions_per_doc=args.spo_max_provisions_per_doc,
        status_filter=frozenset(args.status_filter) if args.status_filter else None,
        type_filter=frozenset(args.type_filter) if args.type_filter else None,
        max_docs=args.max_docs,
        quality_gates_enabled=not args.disable_quality_gates,
        quality_fail_on_critical=args.quality_fail_on_critical,
        quality_max_full_only_docs_pct=args.quality_max_full_only_docs_pct,
        quality_max_empty_statement_rows_pct=args.quality_max_empty_statement_rows_pct,
        quality_max_oov_action_rate_pct=args.quality_max_oov_action_rate_pct,
        quality_max_missing_quote_rate_pct=args.quality_max_missing_quote_rate_pct,
        quality_max_duplicate_anchor_rate_pct=args.quality_max_duplicate_anchor_rate_pct,
        quality_min_provision_docs_for_doc_rate=args.quality_min_provision_docs_for_doc_rate,
        quality_min_spo_rows_for_row_rate=args.quality_min_spo_rows_for_row_rate,
        quality_min_statements_for_statement_rate=args.quality_min_statements_for_statement_rate,
    )

    from polisyos.lex.batch.pipeline import run_batch_pipeline

    stats = asyncio.run(run_batch_pipeline(config))
    print(f"\nPipeline complete:")
    print(f"  Documents:  {stats.total_docs}")
    print(f"  Provisions: {stats.total_provisions}")
    print(f"  SPO triples:{stats.total_spo}")
    print(f"  Entities:   {stats.entities}")
    print(f"  Facts:      {stats.facts}")
    print(f"  Time:       {stats.elapsed_seconds:.1f}s")
    if config.sharded:
        print(f"  Shard:      {config.shard_index + 1}/{config.shard_count} ({config.shard_slug})")
    if stats.quality_passed is not None:
        print(f"  Quality OK: {stats.quality_passed}")
        print(
            "  Quality:    full_only={:.2f}% empty_rows={:.2f}% oov_action={:.2f}% missing_quote={:.2f}% dup_anchor={:.3f}%".format(
                stats.quality_report.get("full_only_docs_pct", 0.0),
                stats.quality_report.get("empty_statement_rows_pct", 0.0),
                stats.quality_report.get("oov_action_rate_pct", 0.0),
                stats.quality_report.get("missing_quote_rate_pct", 0.0),
                stats.quality_report.get("duplicate_anchor_rate_pct", 0.0),
            ),
        )
        if stats.quality_failed_checks:
            print(f"  Quality failed checks: {', '.join(stats.quality_failed_checks)}")
        if stats.quality_skipped_checks:
            print(f"  Quality skipped checks: {', '.join(stats.quality_skipped_checks)}")
    for stage, dt in sorted(stats.stage_times.items()):
        print(f"    {stage}: {dt:.1f}s")


def _resolve_openai_key(cli_value: str) -> str:
    if cli_value.strip():
        return cli_value.strip()
    return os.environ.get("OPENAI_API_KEY", "").strip()


def _parse_tables_arg(raw: str) -> tuple[str, ...]:
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if not values:
        raise ValueError("At least one table must be provided in --tables")
    return tuple(values)


def _cmd_embed_batch_submit(args: argparse.Namespace) -> None:
    from polisyos.lex.batch.openai_batch_embeddings import submit_embedding_batches

    openai_key = _resolve_openai_key(args.openai_api_key)
    if not openai_key:
        print("OPENAI_API_KEY not set.")
        sys.exit(1)

    db_path = args.db_path if args.db_path is not None else args.output_dir / "lex_knowledge_graph.duckdb"
    result = submit_embedding_batches(
        db_path=db_path,
        output_dir=args.output_dir,
        api_key=openai_key,
        model=args.model,
        dimensions=args.dimension,
        tables=_parse_tables_arg(args.tables),
        chunk_size=args.chunk_size,
        max_input_tokens=args.max_input_tokens,
        max_request_tokens=args.max_request_tokens,
        max_inputs_per_request=args.max_inputs_per_request,
        fallback_max_chars=args.fallback_max_chars,
    )
    print("Embedding batch submit complete:")
    print(f"  batches_created:   {result['batches_created']}")
    print(f"  requests_submitted:{result['requests_submitted']}")
    print(f"  inputs_submitted:  {result['inputs_submitted']}")


def _cmd_embed_batch_collect(args: argparse.Namespace) -> None:
    from polisyos.lex.batch.openai_batch_embeddings import collect_embedding_batches

    openai_key = _resolve_openai_key(args.openai_api_key)
    if not openai_key:
        print("OPENAI_API_KEY not set.")
        sys.exit(1)

    result = collect_embedding_batches(
        output_dir=args.output_dir,
        api_key=openai_key,
        wait_for_completion=args.wait,
        poll_interval_s=args.poll_interval_s,
        build_index=not args.no_build_index,
    )
    print("Embedding batch collect complete:")
    print(f"  completed_batches: {result['completed_batches']}")
    print(f"  pending_batches:   {result['pending_batches']}")
    print(f"  failed_batches:    {result['failed_batches']}")
    print(f"  indexes_built:     {result['indexes_built']}")


def _cmd_stats(args: argparse.Namespace) -> None:
    import duckdb

    db_path = args.output_dir / "lex_knowledge_graph.duckdb"
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        entities = con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()[0]
        facts = con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()[0]
        provisions = con.execute("SELECT COUNT(*) FROM lex_provisions").fetchone()[0]

        print(f"Knowledge graph: {db_path}")
        print(f"  Entities:   {entities:,}")
        print(f"  Facts:      {facts:,}")
        print(f"  Provisions: {provisions:,}")

        # Top predicates
        print("\nTop predicates:")
        rows = con.execute(
            "SELECT predicate, COUNT(*) AS cnt FROM lex_facts "
            "GROUP BY predicate ORDER BY cnt DESC LIMIT 15"
        ).fetchall()
        for pred, cnt in rows:
            print(f"  {pred}: {cnt:,}")

        # Top entity types
        print("\nEntity types:")
        rows = con.execute(
            "SELECT entity_type, COUNT(*) AS cnt FROM lex_entities "
            "GROUP BY entity_type ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        for etype, cnt in rows:
            print(f"  {etype}: {cnt:,}")
    finally:
        con.close()


def _cmd_search(args: argparse.Namespace) -> None:
    from polisyos.lex.knowledge.store import LegalKnowledgeStore

    store = LegalKnowledgeStore(
        db_path=args.output_dir / "lex_knowledge_graph.duckdb",
        index_dir=args.output_dir,
    )
    try:
        results = store.text_search_facts(args.query, top_k=args.top_k)
        if not results:
            print("No results found.")
            return
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] {r.fact_text}")
            print(f"    {r.subject_name} → {r.predicate} → {r.object_name}")
            print(f"    doc: {r.doc_name} ({r.doc_reestr_code})")
            print(f"    provision: {r.provision_citation}")
            print(f"    confidence: {r.confidence:.2f}, similarity: {r.similarity:.2f}")
    finally:
        store.close()


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # Optional: CLI still works with explicit env exports.
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        _cmd_run(args)
    elif args.command == "stats":
        _cmd_stats(args)
    elif args.command == "search":
        _cmd_search(args)
    elif args.command == "embed-batch":
        if args.embed_batch_command == "submit":
            _cmd_embed_batch_submit(args)
        elif args.embed_batch_command == "collect":
            _cmd_embed_batch_collect(args)
        else:
            parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
