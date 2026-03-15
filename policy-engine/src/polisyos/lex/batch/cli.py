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
from polisyos.common.logger import get_logger
from polisyos.lex.batch.config import ALL_STAGES, BatchConfig

logger = get_logger(__name__)


def _parse_gonka_api_keys(raw: str) -> list[str]:
    value = str(raw or "").strip()
    if not value:
        return []
    return [token.strip() for token in value.split(",") if token.strip()]


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
    run_p.add_argument(
        "--gonka-api-keys",
        default="",
        help="Comma-separated Gonka API keys (or GONKA_API_KEY_1..N env)",
    )
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
        "--spo-request-batch-chars",
        type=int,
        default=6000,
        help="Approximate max total provision characters per single LLM request.",
    )
    run_p.add_argument(
        "--spo-group-timeout-seconds",
        type=float,
        default=None,
        help="Optional timeout for one grouped SPO LLM task before deterministic fallback.",
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
        "--export-claims-to-cas",
        dest="export_claims_to_cas",
        action="store_true",
        help="Persist export_claims output as CAS-backed claim sets and fact-log segments.",
    )
    run_p.add_argument(
        "--no-export-claims-to-cas",
        dest="export_claims_to_cas",
        action="store_false",
        help="Keep export_claims output as filesystem JSONL only.",
    )
    run_p.set_defaults(export_claims_to_cas=False)
    run_p.add_argument(
        "--cas-root",
        type=Path,
        default=None,
        help="CAS root for export_claims bridge.",
    )
    run_p.add_argument(
        "--fact-log-root",
        type=Path,
        default=None,
        help="Fact log root for export_claims bridge (default: output-dir/fact_log).",
    )
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
    run_p.add_argument("--quality-max-full-only-docs-pct", type=float, default=25.0)
    run_p.add_argument("--quality-max-empty-statement-rows-pct", type=float, default=10.0)
    run_p.add_argument("--quality-max-oov-action-rate-pct", type=float, default=1.0)
    run_p.add_argument("--quality-max-missing-quote-rate-pct", type=float, default=5.0)
    run_p.add_argument("--quality-max-duplicate-anchor-rate-pct", type=float, default=0.1)
    run_p.add_argument("--quality-max-audit-miss-rate-pct", type=float, default=5.0)
    run_p.add_argument("--quality-min-reference-resolution-coverage-pct", type=float, default=80.0)
    run_p.add_argument("--quality-min-llm-saved-pct", type=float, default=50.0)
    run_p.add_argument("--quality-min-audit-samples-for-rate", type=int, default=10)
    run_p.add_argument("--quality-min-provision-docs-for-doc-rate", type=int, default=25)
    run_p.add_argument("--quality-min-spo-rows-for-row-rate", type=int, default=50)
    run_p.add_argument("--quality-min-statements-for-statement-rate", type=int, default=100)
    run_p.add_argument("--quality-min-reference-rows-for-rate", type=int, default=10)
    run_p.add_argument("--status-filter", nargs="*", default=None, help="Filter by status")
    run_p.add_argument("--type-filter", nargs="*", default=None, help="Filter by doc type")
    run_p.add_argument(
        "--stages",
        default="all",
        help=f"Comma-separated stages: {','.join(sorted(ALL_STAGES))} or 'all'",
    )
    run_p.add_argument(
        "--publish-require-embeddings",
        dest="publish_require_embeddings",
        action="store_true",
        help="Require embeddings for publish_bundle consumer readiness.",
    )
    run_p.add_argument(
        "--no-publish-require-embeddings",
        dest="publish_require_embeddings",
        action="store_false",
        help="Allow publish_bundle without embeddings (server-side backfill prep mode).",
    )
    run_p.set_defaults(publish_require_embeddings=True)
    run_p.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    run_p.add_argument(
        "--max-docs", type=int, default=None,
        help="Stop after processing this many NEW documents.",
    )

    # --- smoke ---
    smoke_p = sub.add_parser("smoke", help="Plan and run a fast informative Lex smoke pass")
    smoke_p.add_argument("--cards", required=True, type=Path, help="Path to cards XML")
    smoke_p.add_argument("--texts", required=True, type=Path, help="Path to texts XML")
    smoke_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    smoke_p.add_argument(
        "--profile",
        choices=("fast", "informative", "acceptance_safe"),
        default="informative",
        help="Smoke profile tuned for local Mac runs.",
    )
    smoke_p.add_argument("--sample-docs", type=int, default=None, help="Override selected document count.")
    smoke_p.add_argument("--scan-docs", type=int, default=None, help="How many matched docs to scan for sampling.")
    smoke_p.add_argument("--clean-output", action="store_true", help="Delete previous outputs before smoke run.")
    smoke_p.add_argument("--resume", action="store_true", help="Resume smoke run output if present.")
    smoke_p.add_argument("--gonka-api-key", default="", help="Gonka API key (or GONKA_API_KEY env)")
    smoke_p.add_argument(
        "--gonka-api-keys",
        default="",
        help="Comma-separated Gonka API keys (or GONKA_API_KEY_1..N env)",
    )
    smoke_p.add_argument("--gonka-base-url", default="https://api.gonkagate.com/v1")
    smoke_p.add_argument(
        "--gonka-disable-json-mode",
        action="store_true",
        help="Do not send response_format=json_object to Gonka chat/completions.",
    )
    smoke_p.add_argument("--llm-model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
    smoke_p.add_argument("--parallel-llm", type=int, default=None, help="Override profile LLM concurrency.")
    smoke_p.add_argument("--gonka-rate-limit-rps", type=float, default=None, help="Override profile Gonka request rate.")
    smoke_p.add_argument("--max-retries", type=int, default=None, help="Override profile retry count.")
    smoke_p.add_argument(
        "--spo-request-batch-chars",
        type=int,
        default=None,
        help="Override profile max total provision characters per LLM request.",
    )
    smoke_p.add_argument(
        "--spo-group-timeout-seconds",
        type=float,
        default=None,
        help="Override profile timeout for one grouped SPO LLM task before deterministic fallback.",
    )
    smoke_p.add_argument("--status-filter", nargs="*", default=None, help="Filter by status")
    smoke_p.add_argument("--type-filter", nargs="*", default=None, help="Filter by doc type")

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

    # --- benchmark ---
    benchmark_p = sub.add_parser("benchmark", help="Run deterministic Lex consumer benchmarks")
    benchmark_p.add_argument("--output-dir", required=True, type=Path)

    # --- publish ---
    publish_p = sub.add_parser("publish", help="Write Lex publish manifest")
    publish_p.add_argument("--output-dir", required=True, type=Path)
    publish_p.add_argument(
        "--require-embeddings",
        dest="require_embeddings",
        action="store_true",
        help="Require embeddings for consumer-ready publish manifest.",
    )
    publish_p.add_argument(
        "--no-require-embeddings",
        dest="require_embeddings",
        action="store_false",
        help="Allow publish manifest without embeddings.",
    )
    publish_p.set_defaults(require_embeddings=True)

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
        for rel_dir in (
            "provisions",
            "spo_results",
            "spo_grounded",
            "references",
            "resolved_references",
            "domains",
            "claim_exports",
            "manifests",
            "benchmark_report.json",
            "publish",
        ):
            target = output_dir / rel_dir
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()


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
        gonka_api_keys=_parse_gonka_api_keys(getattr(args, "gonka_api_keys", "")),
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
        spo_request_batch_chars=args.spo_request_batch_chars,
        spo_group_timeout_seconds=args.spo_group_timeout_seconds,
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
        quality_min_reference_resolution_coverage_pct=args.quality_min_reference_resolution_coverage_pct,
        quality_min_llm_saved_pct=args.quality_min_llm_saved_pct,
        quality_min_audit_samples_for_rate=args.quality_min_audit_samples_for_rate,
        quality_min_provision_docs_for_doc_rate=args.quality_min_provision_docs_for_doc_rate,
        quality_min_spo_rows_for_row_rate=args.quality_min_spo_rows_for_row_rate,
        quality_min_statements_for_statement_rate=args.quality_min_statements_for_statement_rate,
        quality_min_reference_rows_for_rate=args.quality_min_reference_rows_for_rate,
        publish_require_embeddings=args.publish_require_embeddings,
        export_claims_to_cas=args.export_claims_to_cas,
        cas_root=args.cas_root,
        fact_log_root=args.fact_log_root,
    )

    from polisyos.lex.batch.pipeline import run_batch_pipeline

    stats = asyncio.run(run_batch_pipeline(config))
    print("\nPipeline complete:")
    print(f"  Documents:  {stats.total_docs}")
    print(f"  Provisions: {stats.total_provisions}")
    print(f"  SPO triples:{stats.total_spo}")
    print(f"  Entities:   {stats.entities}")
    print(f"  Facts:      {stats.facts}")
    if stats.grounded_facts or stats.normative_facts or stats.candidate_facts:
        print(f"  Candidate facts: {stats.candidate_facts}")
        print(f"  Grounded facts:  {stats.grounded_facts}")
        print(f"  Normative facts: {stats.normative_facts}")
    if stats.reference_edges:
        print(f"  Resolved refs:   {stats.reference_edges}")
    if stats.exported_claims:
        print(f"  Exported claims: {stats.exported_claims}")
    if getattr(stats, "exported_claim_sets", 0):
        print(f"  Claim sets:      {stats.exported_claim_sets}")
    if stats.published_bundle:
        print("  Publish bundle: yes")
    if stats.benchmark_passed is not None:
        print(f"  Benchmark OK: {stats.benchmark_passed}")
    print(f"  Time:       {stats.elapsed_seconds:.1f}s")
    if config.sharded:
        print(f"  Shard:      {config.shard_index + 1}/{config.shard_count} ({config.shard_slug})")
    if stats.quality_passed is not None:
        print(f"  Quality OK: {stats.quality_passed}")
    if stats.benchmark_passed is not None and stats.benchmark_failed_checks:
        print(f"  Benchmark failed checks: {', '.join(stats.benchmark_failed_checks)}")
    for stage, dt in sorted(stats.stage_times.items()):
        print(f"    {stage}: {dt:.1f}s")

    run_artifacts: list[Path] = []
    if config.db_path.exists():
        run_artifacts.append(config.db_path)
    if config.llm_gate_manifest_path.exists():
        run_artifacts.append(config.llm_gate_manifest_path)
    if config.llm_gate_audit_path.exists():
        run_artifacts.append(config.llm_gate_audit_path)
    if config.benchmark_report_path.exists():
        run_artifacts.append(config.benchmark_report_path)

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
            **stats.benchmark_metrics,
        },
        artifacts=run_artifacts + [
            config.consumer_manifest_path,
            config.benchmark_report_path,
            config.claim_exports_dir / "normative_claims.jsonl",
            config.claim_exports_dir / "normative_claim_sets_summary.json",
        ],
        started_at=datetime.now(UTC).isoformat(),
    )


def _cmd_smoke(args: argparse.Namespace) -> None:
    if args.clean_output:
        _clean_lex_output(args.output_dir, shard_count=1, shard_index=0)

    from polisyos.lex.batch.smoke import run_smoke

    result = run_smoke(
        cards_path=args.cards,
        texts_path=args.texts,
        output_dir=args.output_dir,
        profile_name=args.profile,
        gonka_api_key=args.gonka_api_key,
        gonka_api_keys=_parse_gonka_api_keys(getattr(args, "gonka_api_keys", "")),
        gonka_base_url=args.gonka_base_url,
        gonka_disable_json_mode=args.gonka_disable_json_mode,
        llm_model=args.llm_model,
        resume=bool(args.resume),
        status_filter=frozenset(args.status_filter) if args.status_filter else None,
        type_filter=frozenset(args.type_filter) if args.type_filter else None,
        sample_docs=args.sample_docs,
        scan_docs=args.scan_docs,
        parallel_llm=args.parallel_llm,
        gonka_rate_limit_rps=args.gonka_rate_limit_rps,
        max_retries=args.max_retries,
        spo_request_batch_chars=args.spo_request_batch_chars,
        spo_group_timeout_seconds=args.spo_group_timeout_seconds,
    )
    stats = result["stats"]
    print("\nSmoke run complete:")
    print(f"  Profile:        {result['profile'].name}")
    print(f"  Scanned docs:   {result['scanned_docs']}")
    print(f"  Selected docs:  {result['selected_docs']}")
    print(f"  Processed docs: {stats.total_docs}")
    print(f"  Provisions:     {stats.total_provisions}")
    print(f"  SPO rows:       {stats.total_spo}")
    print(f"  Grounded facts: {stats.grounded_facts}")
    print(f"  Normative facts:{stats.normative_facts}")
    print(f"  Resolved refs:  {stats.reference_edges}")
    print(f"  Quality OK:     {stats.quality_passed}")
    if stats.quality_failed_checks:
        print(f"  Failed checks:  {', '.join(stats.quality_failed_checks)}")
    print(f"  Time:           {stats.elapsed_seconds:.1f}s")
    print(f"  Plan:           {result['plan_path']}")
    print(f"  Report:         {result['report_path']}")
    print(f"  Summary:        {result['summary_path']}")


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


def _cmd_benchmark(args: argparse.Namespace) -> None:
    from polisyos.lex.batch.benchmark import run_benchmark

    cfg = _minimal_cfg(args.output_dir)
    outcome = run_benchmark(cfg)
    print(f"Benchmark passed: {outcome.passed}")
    if outcome.failed_checks:
        print(f"Failed checks: {', '.join(outcome.failed_checks)}")
    print(f"Benchmark report: {cfg.benchmark_report_path}")


def _cmd_publish(args: argparse.Namespace) -> None:
    from polisyos.lex.batch.publish import run_publish

    manifest = run_publish(args.output_dir, require_embeddings=bool(args.require_embeddings))
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
        candidate_facts = _count_table_rows(con, "lex_fact_candidates")
        grounded_facts = _count_table_rows(con, "lex_fact_grounded")
        normative_facts = _count_table_rows(con, "lex_normative_facts")
        reference_edges = _count_table_rows(con, "lex_reference_edges")
        doc_versions = _count_table_rows(con, "lex_doc_versions")
    finally:
        con.close()

    print(f"Knowledge graph: {db_path}")
    print(f"  Entities:   {entities:,}")
    print(f"  Facts:      {facts:,}")
    print(f"  Provisions: {provisions:,}")
    if candidate_facts:
        print(f"  Candidate facts: {candidate_facts:,}")
    if grounded_facts:
        print(f"  Grounded facts:  {grounded_facts:,}")
    if normative_facts:
        print(f"  Normative facts: {normative_facts:,}")
    if reference_edges:
        print(f"  Resolved refs:   {reference_edges:,}")
    if doc_versions:
        print(f"  Doc versions:    {doc_versions:,}")


def _cmd_search(args: argparse.Namespace) -> None:
    from polisyos.lex.knowledge.store import LegalKnowledgeStore

    store = LegalKnowledgeStore(db_path=args.output_dir / "lex_knowledge_graph.duckdb", index_dir=args.output_dir)
    try:
        results = store.text_search_facts(
            args.query,
            top_k=args.top_k,
            trust_tier="grounded_fact",
        )
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


def _count_table_rows(con, table_name: str) -> int:  # type: ignore[no-untyped-def]
    exists = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchone()[0]
    if not exists:
        return 0
    return int(con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def main() -> None:
    try:
        from dotenv import load_dotenv


        load_dotenv()
    except Exception as exc:
        logger.debug("Ignored exception: {}", exc)

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
    elif args.command == "smoke":
        _cmd_smoke(args)
    elif args.command == "embed-local":
        _cmd_embed_local(args)
    elif args.command == "qc":
        _cmd_qc(args)
    elif args.command == "benchmark":
        _cmd_benchmark(args)
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
