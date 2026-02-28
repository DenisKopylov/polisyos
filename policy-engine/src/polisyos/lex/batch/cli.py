"""CLI entry point for the Lex staged batch pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.lex.batch.config import ALL_STAGES, BatchConfig


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m polisyos.lex.batch",
        description="Lex pipeline: parse/structure/spo/graph + local embeddings.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_p = sub.add_parser("run", help="Run parse/structure/spo/graph stages")
    run_p.add_argument("--cards", required=True, type=Path, help="Path to cards XML")
    run_p.add_argument("--texts", required=True, type=Path, help="Path to texts XML")
    run_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    run_p.add_argument("--shard-count", type=int, default=1, help="Total number of shards")
    run_p.add_argument("--shard-index", type=int, default=0, help="Zero-based shard index")
    run_p.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete previous outputs for this run context before start.",
    )
    run_p.add_argument("--gonka-api-key", default="", help="Gonka API key (or GONKA_API_KEY env)")
    run_p.add_argument("--gonka-base-url", default="https://api.gonkagate.com/v1")
    run_p.add_argument(
        "--gonka-disable-json-mode",
        action="store_true",
        help="Do not send response_format=json_object to Gonka chat/completions.",
    )
    run_p.add_argument("--llm-model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
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
        "--spo-request-batch-size",
        type=int,
        default=5,
        help="Provision count per single LLM request (batch reduces HTTP round-trips).",
    )
    run_p.add_argument(
        "--spo-extract-mode",
        choices=("light", "full"),
        default="light",
        help="SPO extraction mode.",
    )
    run_p.add_argument(
        "--no-spo-skip-trivial",
        action="store_true",
        help="Disable rule-based pre-filtering of trivial provisions.",
    )
    run_p.add_argument(
        "--spo-verify-mode",
        choices=("llm", "code"),
        default="llm",
        help="SPO verify pass mode.",
    )
    run_p.add_argument(
        "--spo-max-provisions-per-doc",
        type=int,
        default=None,
        help="Cap number of provision spans per document for SPO.",
    )
    run_p.add_argument(
        "--llm-gate-enabled",
        dest="llm_gate_enabled",
        action="store_true",
        help="Enable LLM routing gate (deterministic-first).",
    )
    run_p.add_argument(
        "--no-llm-gate-enabled",
        dest="llm_gate_enabled",
        action="store_false",
        help="Disable LLM routing gate and send all non-auto candidates to LLM.",
    )
    run_p.set_defaults(llm_gate_enabled=True)
    run_p.add_argument(
        "--llm-gate-mode",
        choices=("off", "balanced", "aggressive"),
        default="balanced",
    )
    run_p.add_argument("--llm-gate-threshold", type=float, default=0.55)
    run_p.add_argument("--llm-gate-max-share", type=float, default=0.35)
    run_p.add_argument("--llm-gate-audit-sample-rate", type=float, default=0.02)
    run_p.add_argument("--llm-gate-audit-max-miss-rate-pct", type=float, default=3.0)
    run_p.add_argument(
        "--extract-references",
        dest="extract_references",
        action="store_true",
        help="Enable deterministic reference extraction.",
    )
    run_p.add_argument(
        "--no-extract-references",
        dest="extract_references",
        action="store_false",
        help="Disable deterministic reference extraction.",
    )
    run_p.set_defaults(extract_references=True)
    run_p.add_argument(
        "--extract-domains",
        dest="extract_domains",
        action="store_true",
        help="Enable deterministic domain classification.",
    )
    run_p.add_argument(
        "--no-extract-domains",
        dest="extract_domains",
        action="store_false",
        help="Disable deterministic domain classification.",
    )
    run_p.set_defaults(extract_domains=True)
    run_p.add_argument(
        "--disable-quality-gates",
        action="store_true",
        help="Disable SPO quality gate checks.",
    )
    run_p.add_argument(
        "--quality-fail-on-critical",
        action="store_true",
        help="Fail pipeline when critical quality gates fail.",
    )
    run_p.add_argument("--quality-max-full-only-docs-pct", type=float, default=30.0)
    run_p.add_argument("--quality-max-empty-statement-rows-pct", type=float, default=12.0)
    run_p.add_argument("--quality-max-oov-action-rate-pct", type=float, default=1.0)
    run_p.add_argument("--quality-max-missing-quote-rate-pct", type=float, default=5.0)
    run_p.add_argument("--quality-max-duplicate-anchor-rate-pct", type=float, default=0.1)
    run_p.add_argument("--quality-max-audit-miss-rate-pct", type=float, default=3.0)
    run_p.add_argument("--quality-min-llm-saved-pct", type=float, default=50.0)
    run_p.add_argument("--quality-min-provision-docs-for-doc-rate", type=int, default=25)
    run_p.add_argument("--quality-min-spo-rows-for-row-rate", type=int, default=50)
    run_p.add_argument("--quality-min-statements-for-statement-rate", type=int, default=100)
    run_p.add_argument("--status-filter", nargs="*", default=None, help="Filter by status")
    run_p.add_argument("--type-filter", nargs="*", default=None, help="Filter by doc type")
    run_p.add_argument(
        "--stages",
        default="all",
        help=f"Comma-separated stages: {','.join(sorted(ALL_STAGES))} or 'all'",
    )
    run_p.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    run_p.add_argument(
        "--max-docs", type=int, default=None,
        help="Stop after processing this many NEW documents.",
    )

    # --- embed-local ---
    embed_p = sub.add_parser("embed-local", help="Build local embeddings and HNSW indexes")
    embed_p.add_argument("--output-dir", required=True, type=Path)
    embed_p.add_argument("--db-path", type=Path, default=None)
    embed_p.add_argument("--model", default="intfloat/multilingual-e5-large")
    embed_p.add_argument("--device", default="mps")
    embed_p.add_argument("--batch-size", type=int, default=24)
    embed_p.add_argument("--chunk-size", type=int, default=2000)
    embed_p.add_argument("--thermal", action="store_true")
    embed_p.add_argument(
        "--incremental", action="store_true",
        help="Only embed new rows not present in existing .npz files.",
    )
    embed_p.add_argument(
        "--fp16", action="store_true",
        help="Use FP16 inference for faster encoding on MPS/CUDA (slight quality trade-off).",
    )

    # --- qc ---
    qc_p = sub.add_parser("qc", help="Run QC checks for Lex artifacts")
    qc_p.add_argument("--output-dir", required=True, type=Path)
    qc_p.add_argument("--fail-fast", dest="fail_fast", action="store_true")
    qc_p.add_argument("--no-fail-fast", dest="fail_fast", action="store_false")
    qc_p.set_defaults(fail_fast=True)

    # --- publish ---
    publish_p = sub.add_parser("publish", help="Write Lex publish manifest")
    publish_p.add_argument("--output-dir", required=True, type=Path)

    # --- stats ---
    stats_p = sub.add_parser("stats", help="Show graph statistics")
    stats_p.add_argument("--output-dir", required=True, type=Path)

    # --- search ---
    search_p = sub.add_parser("search", help="Interactive search")
    search_p.add_argument("--output-dir", required=True, type=Path)
    search_p.add_argument("--query", required=True, help="Search query")
    search_p.add_argument("--top-k", type=int, default=20, help="Number of results")

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

    state_dir = _shard_state_dir(output_dir, shard_count=shard_count, shard_index=shard_index)
    state_dir.mkdir(parents=True, exist_ok=True)

    for rel_file in ("progress.jsonl", "manifest.jsonl", "lex_knowledge_graph.duckdb"):
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
        raise ValueError("In sharded mode use --clean-output only on --shard-index 0.")

    if args.clean_output:
        _clean_lex_output(args.output_dir, shard_count=args.shard_count, shard_index=args.shard_index)

    stages_str: str = args.stages
    if stages_str == "all":
        stages = ALL_STAGES
    else:
        stages = frozenset(s.strip() for s in stages_str.split(",") if s.strip())

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
        spo_request_batch_size=args.spo_request_batch_size,
        spo_extract_mode=args.spo_extract_mode,
        spo_skip_trivial=not args.no_spo_skip_trivial,
        spo_verify_mode=args.spo_verify_mode,
        spo_max_provisions_per_doc=args.spo_max_provisions_per_doc,
        llm_gate_enabled=args.llm_gate_enabled,
        llm_gate_mode=args.llm_gate_mode,
        llm_gate_threshold=args.llm_gate_threshold,
        llm_gate_max_share=args.llm_gate_max_share,
        llm_gate_audit_sample_rate=args.llm_gate_audit_sample_rate,
        llm_gate_audit_max_miss_rate_pct=args.llm_gate_audit_max_miss_rate_pct,
        extract_references_enabled=args.extract_references,
        extract_domains_enabled=args.extract_domains,
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
        quality_max_audit_miss_rate_pct=args.quality_max_audit_miss_rate_pct,
        quality_min_llm_saved_pct=args.quality_min_llm_saved_pct,
        quality_min_provision_docs_for_doc_rate=args.quality_min_provision_docs_for_doc_rate,
        quality_min_spo_rows_for_row_rate=args.quality_min_spo_rows_for_row_rate,
        quality_min_statements_for_statement_rate=args.quality_min_statements_for_statement_rate,
    )

    from polisyos.lex.batch.pipeline import run_batch_pipeline

    stats = asyncio.run(run_batch_pipeline(config))
    print("\nPipeline complete:")
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
    for stage, dt in sorted(stats.stage_times.items()):
        print(f"    {stage}: {dt:.1f}s")

    run_artifacts: list[Path] = []
    if config.db_path.exists():
        run_artifacts.append(config.db_path)
    if config.llm_gate_manifest_path.exists():
        run_artifacts.append(config.llm_gate_manifest_path)
    if config.llm_gate_audit_path.exists():
        run_artifacts.append(config.llm_gate_audit_path)

    write_stage_manifest(
        manifest_path=config.output_dir / "manifests" / "run.json",
        stage="run",
        status="ok",
        metrics={
            "documents": stats.total_docs,
            "provisions": stats.total_provisions,
            "spo": stats.total_spo,
            "entities": stats.entities,
            "facts": stats.facts,
            "elapsed_seconds": round(stats.elapsed_seconds, 3),
            **stats.llm_gate_metrics,
        },
        artifacts=run_artifacts,
        started_at=datetime.now(UTC).isoformat(),
    )


def _cmd_embed_local(args: argparse.Namespace) -> None:
    from polisyos.lex.batch.embedder import build_local_embeddings_and_indexes

    db_path = args.db_path if args.db_path is not None else args.output_dir / "lex_knowledge_graph.duckdb"
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    stats = build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=args.output_dir,
        embedding_model=args.model,
        embedding_device=args.device,
        embedding_batch_size=args.batch_size,
        embedding_chunk_size=args.chunk_size,
        thermal_pause_seconds=0.5 if args.thermal else 0.0,
        incremental=args.incremental,
        fp16=args.fp16,
    )

    print("Local embedding complete:")
    print(f"  entities:   {stats.entities_embedded} (skipped: {stats.entities_skipped})")
    print(f"  facts:      {stats.facts_embedded} (skipped: {stats.facts_skipped})")
    print(f"  provisions: {stats.provisions_embedded} (skipped: {stats.provisions_skipped})")
    print(f"  time:       {stats.elapsed_seconds:.1f}s")

    write_stage_manifest(
        manifest_path=args.output_dir / "manifests" / "embed_local.json",
        stage="embed_local",
        status="ok",
        metrics={
            "entities": stats.entities_embedded,
            "entities_skipped": stats.entities_skipped,
            "facts": stats.facts_embedded,
            "facts_skipped": stats.facts_skipped,
            "provisions": stats.provisions_embedded,
            "provisions_skipped": stats.provisions_skipped,
            "elapsed_seconds": round(stats.elapsed_seconds, 3),
            "incremental": bool(args.incremental),
            "fp16": bool(args.fp16),
            "thermal": bool(args.thermal),
        },
        artifacts=[
            args.output_dir / "lex_entity_embeddings.npz",
            args.output_dir / "lex_entity_index.hnsw",
            args.output_dir / "lex_fact_embeddings.npz",
            args.output_dir / "lex_fact_index.hnsw",
            args.output_dir / "lex_provision_embeddings.npz",
            args.output_dir / "lex_provision_index.hnsw",
        ],
        started_at=datetime.now(UTC).isoformat(),
    )


def _minimal_cfg(output_dir: Path) -> BatchConfig:
    return BatchConfig(
        cards_path=output_dir / "_placeholder_cards.xml",
        texts_path=output_dir / "_placeholder_texts.xml",
        output_dir=output_dir,
        stages=frozenset({"parse"}),
    )


def _cmd_qc(args: argparse.Namespace) -> None:
    from polisyos.lex.batch.qc import run_qc

    cfg = _minimal_cfg(args.output_dir)
    report = run_qc(cfg, fail_fast=bool(args.fail_fast))
    print(f"QC passed: {report.passed}")
    print(f"QC report: {args.output_dir / 'qc_report.json'}")

    write_stage_manifest(
        manifest_path=args.output_dir / "manifests" / "qc.json",
        stage="qc",
        status="ok" if report.passed else "failed",
        metrics={"passed": report.passed, **report.metrics},
        artifacts=[args.output_dir / "qc_report.json"],
        started_at=datetime.now(UTC).isoformat(),
    )


def _cmd_publish(args: argparse.Namespace) -> None:
    from polisyos.lex.batch.publish import run_publish

    manifest = run_publish(args.output_dir)
    print(f"Publish manifest: {manifest}")


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
    finally:
        con.close()

    print(f"Knowledge graph: {db_path}")
    print(f"  Entities:   {entities:,}")
    print(f"  Facts:      {facts:,}")
    print(f"  Provisions: {provisions:,}")


def _cmd_search(args: argparse.Namespace) -> None:
    from polisyos.lex.knowledge.store import LegalKnowledgeStore

    store = LegalKnowledgeStore(db_path=args.output_dir / "lex_knowledge_graph.duckdb", index_dir=args.output_dir)
    try:
        results = store.text_search_facts(args.query, top_k=args.top_k)
    finally:
        store.close()

    if not results:
        print("No results found.")
        return
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r.fact_text}")
        print(f"    {r.subject_name} → {r.predicate} → {r.object_name}")
        print(f"    doc: {r.doc_name} ({r.doc_reestr_code})")
        print(f"    provision: {r.provision_citation}")
        print(f"    confidence: {r.confidence:.2f}, similarity: {r.similarity:.2f}")


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
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
    elif args.command == "embed-local":
        _cmd_embed_local(args)
    elif args.command == "qc":
        _cmd_qc(args)
    elif args.command == "publish":
        _cmd_publish(args)
    elif args.command == "stats":
        _cmd_stats(args)
    elif args.command == "search":
        _cmd_search(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
