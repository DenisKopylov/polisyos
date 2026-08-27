"""CLI entry point for the Lex staged batch pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.legal.batch.config import ALL_STAGES, BatchConfig
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

logger = get_logger(__name__)


def _parse_gonka_api_keys(raw: str) -> list[str]:
    value = str(raw or "").strip()
    if not value:
        return []
    return [token.strip() for token in value.split(",") if token.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m polisyos.data_forge.domains.legal.batch",
        description="Legal Data Forge pipeline: parse/structure/spo/graph + local embeddings.",
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
    run_p.add_argument(
        "--parallel-llm-global",
        type=int,
        default=None,
        help="Optional global concurrency cap across all Gonka keys.",
    )
    run_p.add_argument(
        "--gonka-rate-limit-rps", type=float, default=5.0, help="Gonka request rate limit"
    )
    run_p.add_argument(
        "--max-retries", type=int, default=7, help="Max retries per LLM request on 429/5xx"
    )
    run_p.add_argument(
        "--llm-temperature", type=float, default=0.1, help="LLM temperature for SPO extraction"
    )
    run_p.add_argument("--spo-connect-timeout-seconds", type=int, default=15)
    run_p.add_argument("--spo-read-timeout-seconds", type=int, default=120)
    run_p.add_argument("--spo-total-timeout-seconds", type=int, default=180)
    run_p.add_argument(
        "--spo-provider-watchdog-seconds",
        type=int,
        default=0,
        help="0 = adaptive watchdog, -1 = disable watchdog.",
    )
    run_p.add_argument(
        "--spo-rate-warmup-seconds",
        type=float,
        default=45.0,
        help="Seconds to ramp from a slower cold-start request rate to the configured target.",
    )
    run_p.add_argument(
        "--spo-rate-warmup-start-scale",
        type=float,
        default=3.0,
        help="Initial slowdown factor during SPO LLM warm-up (>=1.0).",
    )
    run_p.add_argument(
        "--spo-adaptive-rate-enabled",
        dest="spo_adaptive_rate_enabled",
        action="store_true",
        help="Enable adaptive rate cooling/recovery after 429 bursts.",
    )
    run_p.add_argument(
        "--no-spo-adaptive-rate-enabled",
        dest="spo_adaptive_rate_enabled",
        action="store_false",
        help="Disable adaptive rate cooling/recovery for SPO LLM requests.",
    )
    run_p.set_defaults(spo_adaptive_rate_enabled=True)
    run_p.add_argument("--spo-adaptive-rate-recovery-factor", type=float, default=0.97)
    run_p.add_argument("--spo-adaptive-rate-penalty-multiplier", type=float, default=1.35)
    run_p.add_argument("--spo-adaptive-rate-max-scale", type=float, default=8.0)
    run_p.add_argument(
        "--xml-parse-chunk", type=int, default=5000, help="Documents buffered per stream chunk"
    )
    run_p.add_argument(
        "--structure-workers", type=int, default=4, help="Worker processes for structure extraction"
    )
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
    run_p.add_argument(
        "--spo-batch-docs", type=int, default=500, help="Documents per SPO checkpoint batch"
    )
    run_p.add_argument(
        "--spo-task-batch-size", type=int, default=1000, help="Max SPO asyncio tasks per gather"
    )
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
        "--spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_true",
        help="Downshift grouped SPO request size early for long prompts before the hard char cap.",
    )
    run_p.add_argument(
        "--no-spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_false",
        help="Disable prompt-size-aware SPO batch downshift.",
    )
    run_p.set_defaults(spo_adaptive_batch_downshift_enabled=True)
    run_p.add_argument(
        "--spo-adaptive-batch-soft-chars-share",
        type=float,
        default=0.80,
        help="Soft-share of spo-request-batch-chars used for early downshift before the hard cap.",
    )
    run_p.add_argument(
        "--spo-group-timeout-seconds",
        type=float,
        default=None,
        help="Optional timeout for one grouped SPO LLM task before deterministic fallback.",
    )
    run_p.add_argument(
        "--spo-timeout-retry-enabled",
        dest="spo_timeout_retry_enabled",
        action="store_true",
        help="Retry timed out SPO groups once with a narrower batch before deferring.",
    )
    run_p.add_argument(
        "--no-spo-timeout-retry-enabled",
        dest="spo_timeout_retry_enabled",
        action="store_false",
        help="Disable timeout retry for grouped SPO requests.",
    )
    run_p.set_defaults(spo_timeout_retry_enabled=True)
    run_p.add_argument("--spo-timeout-retry-batch-size", type=int, default=1)
    run_p.add_argument("--spo-timeout-retry-chars", type=int, default=3000)
    run_p.add_argument(
        "--spo-retryable-followup-passes",
        type=int,
        default=1,
        help="Extra follow-up passes for retryable LLM failures with reduced pressure.",
    )
    run_p.add_argument(
        "--spo-retryable-followup-delay-seconds",
        type=float,
        default=5.0,
        help="Delay before each retryable follow-up pass.",
    )
    run_p.add_argument("--spo-retryable-followup-worker-scale", type=float, default=0.5)
    run_p.add_argument("--spo-retryable-followup-dispatch-rps-scale", type=float, default=0.5)
    run_p.add_argument("--spo-retryable-followup-client-rate-scale", type=float, default=0.5)
    run_p.add_argument("--spo-retryable-followup-client-concurrency-scale", type=float, default=0.5)
    run_p.add_argument(
        "--spo-request-log-enabled",
        dest="spo_request_log_enabled",
        action="store_true",
        help="Write per-request LLM telemetry to manifests/llm_requests.jsonl.",
    )
    run_p.add_argument(
        "--no-spo-request-log-enabled",
        dest="spo_request_log_enabled",
        action="store_false",
        help="Disable per-request LLM telemetry logging.",
    )
    run_p.set_defaults(spo_request_log_enabled=True)
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
        "--graph-amendment-workers",
        type=int,
        default=1,
        help="Process workers for amendment scan/enrichment during graph build.",
    )
    run_p.add_argument(
        "--graph-amendment-task-chunk",
        type=int,
        default=64,
        help="Provision JSONL files per amendment worker task.",
    )
    run_p.add_argument(
        "--graph-amendment-progress-interval",
        type=int,
        default=100,
        help="Log amendment scan/enrichment progress every N provision files; 0 disables.",
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
        "--llm-gap-fill-mode",
        choices=("off", "narrow", "wide"),
        default="off",
    )
    run_p.add_argument("--llm-gap-fill-max-share", type=float, default=0.80)
    run_p.add_argument(
        "--jurisdiction", default="UA", help="Jurisdiction plugin code, e.g. UA or EU."
    )
    run_p.add_argument(
        "--pattern-feedback-enabled",
        dest="pattern_feedback_enabled",
        action="store_true",
        help="Write audit misses into the pattern feedback queue and candidate clusters.",
    )
    run_p.add_argument(
        "--no-pattern-feedback-enabled",
        dest="pattern_feedback_enabled",
        action="store_false",
        help="Disable pattern feedback queue emission.",
    )
    run_p.set_defaults(pattern_feedback_enabled=True)
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
    run_p.add_argument("--quality-max-hallucination-rate-pct", type=float, default=3.0)
    run_p.add_argument("--quality-max-unresolved-contradictions", type=int, default=10)
    run_p.add_argument("--quality-max-low-confidence-normative-pct", type=float, default=15.0)
    run_p.add_argument("--quality-min-reference-resolution-coverage-pct", type=float, default=80.0)
    run_p.add_argument("--quality-min-amendment-extraction-coverage-pct", type=float, default=60.0)
    run_p.add_argument("--quality-min-amendment-target-resolution-pct", type=float, default=70.0)
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
        "--max-docs",
        type=int,
        default=None,
        help="Stop after processing this many NEW documents.",
    )

    # --- smoke ---
    smoke_p = sub.add_parser("smoke", help="Plan and run a fast informative Lex smoke pass")
    smoke_p.add_argument("--cards", required=True, type=Path, help="Path to cards XML")
    smoke_p.add_argument("--texts", required=True, type=Path, help="Path to texts XML")
    smoke_p.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    smoke_p.add_argument(
        "--profile",
        choices=("fast", "informative", "acceptance_safe", "production_gap_fill_wide"),
        default="informative",
        help="Smoke profile tuned for local Mac runs.",
    )
    smoke_p.add_argument(
        "--sample-docs", type=int, default=None, help="Override selected document count."
    )
    smoke_p.add_argument(
        "--scan-docs", type=int, default=None, help="How many matched docs to scan for sampling."
    )
    smoke_p.add_argument(
        "--clean-output", action="store_true", help="Delete previous outputs before smoke run."
    )
    smoke_p.add_argument(
        "--resume", action="store_true", help="Resume smoke run output if present."
    )
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
    smoke_p.add_argument(
        "--parallel-llm", type=int, default=None, help="Override profile LLM concurrency."
    )
    smoke_p.add_argument(
        "--gonka-rate-limit-rps",
        type=float,
        default=None,
        help="Override profile Gonka request rate.",
    )
    smoke_p.add_argument(
        "--max-retries", type=int, default=None, help="Override profile retry count."
    )
    smoke_p.add_argument(
        "--spo-rate-warmup-seconds",
        type=float,
        default=None,
        help="Override profile SPO LLM warm-up ramp seconds.",
    )
    smoke_p.add_argument(
        "--spo-rate-warmup-start-scale",
        type=float,
        default=None,
        help="Override profile SPO LLM warm-up slowdown factor.",
    )
    smoke_p.add_argument(
        "--spo-adaptive-rate-enabled",
        dest="spo_adaptive_rate_enabled",
        action="store_true",
        help="Enable adaptive SPO LLM rate cooling for smoke run.",
    )
    smoke_p.add_argument(
        "--no-spo-adaptive-rate-enabled",
        dest="spo_adaptive_rate_enabled",
        action="store_false",
        help="Disable adaptive SPO LLM rate cooling for smoke run.",
    )
    smoke_p.set_defaults(spo_adaptive_rate_enabled=None)
    smoke_p.add_argument("--spo-adaptive-rate-recovery-factor", type=float, default=None)
    smoke_p.add_argument("--spo-adaptive-rate-penalty-multiplier", type=float, default=None)
    smoke_p.add_argument("--spo-adaptive-rate-max-scale", type=float, default=None)
    smoke_p.add_argument("--spo-retryable-followup-worker-scale", type=float, default=None)
    smoke_p.add_argument("--spo-retryable-followup-dispatch-rps-scale", type=float, default=None)
    smoke_p.add_argument("--spo-retryable-followup-client-rate-scale", type=float, default=None)
    smoke_p.add_argument(
        "--spo-retryable-followup-client-concurrency-scale", type=float, default=None
    )
    smoke_p.add_argument(
        "--spo-request-batch-chars",
        type=int,
        default=None,
        help="Override profile max total provision characters per LLM request.",
    )
    smoke_p.add_argument(
        "--spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_true",
        help="Enable prompt-size-aware early downshift for grouped SPO requests.",
    )
    smoke_p.add_argument(
        "--no-spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_false",
        help="Disable prompt-size-aware early downshift for grouped SPO requests.",
    )
    smoke_p.set_defaults(spo_adaptive_batch_downshift_enabled=None)
    smoke_p.add_argument("--spo-adaptive-batch-soft-chars-share", type=float, default=None)
    smoke_p.add_argument(
        "--spo-group-timeout-seconds",
        type=float,
        default=None,
        help="Override profile timeout for one grouped SPO LLM task before deterministic fallback.",
    )
    smoke_p.add_argument(
        "--llm-gap-fill-mode",
        choices=("off", "narrow", "wide"),
        default=None,
        help="Override profile LLM gap-fill mode.",
    )
    smoke_p.add_argument(
        "--llm-gap-fill-max-share",
        type=float,
        default=None,
        help="Override profile gap-fill share cap.",
    )
    smoke_p.add_argument("--status-filter", nargs="*", default=None, help="Filter by status")
    smoke_p.add_argument("--type-filter", nargs="*", default=None, help="Filter by doc type")
    smoke_p.add_argument(
        "--stages", default=None, help="Comma-separated stages to run (default: all)"
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
        "--incremental",
        action="store_true",
        help="Only embed new rows not present in existing .npz files.",
    )
    embed_p.add_argument(
        "--fp16",
        action="store_true",
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
        _clean_lex_output(
            args.output_dir, shard_count=args.shard_count, shard_index=args.shard_index
        )

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
        max_concurrent_llm_global=args.parallel_llm_global,
        rate_limit_rps=args.gonka_rate_limit_rps,
        max_retries=args.max_retries,
        llm_temperature=args.llm_temperature,
        spo_connect_timeout_seconds=args.spo_connect_timeout_seconds,
        spo_read_timeout_seconds=args.spo_read_timeout_seconds,
        spo_total_timeout_seconds=args.spo_total_timeout_seconds,
        spo_provider_watchdog_seconds=args.spo_provider_watchdog_seconds,
        spo_rate_warmup_seconds=args.spo_rate_warmup_seconds,
        spo_rate_warmup_start_scale=args.spo_rate_warmup_start_scale,
        spo_adaptive_rate_enabled=args.spo_adaptive_rate_enabled,
        spo_adaptive_rate_recovery_factor=args.spo_adaptive_rate_recovery_factor,
        spo_adaptive_rate_penalty_multiplier=args.spo_adaptive_rate_penalty_multiplier,
        spo_adaptive_rate_max_scale=args.spo_adaptive_rate_max_scale,
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
        spo_adaptive_batch_downshift_enabled=args.spo_adaptive_batch_downshift_enabled,
        spo_adaptive_batch_soft_chars_share=args.spo_adaptive_batch_soft_chars_share,
        spo_group_timeout_seconds=args.spo_group_timeout_seconds,
        spo_timeout_retry_enabled=args.spo_timeout_retry_enabled,
        spo_timeout_retry_batch_size=args.spo_timeout_retry_batch_size,
        spo_timeout_retry_chars=args.spo_timeout_retry_chars,
        spo_retryable_followup_passes=args.spo_retryable_followup_passes,
        spo_retryable_followup_delay_seconds=args.spo_retryable_followup_delay_seconds,
        spo_retryable_followup_worker_scale=args.spo_retryable_followup_worker_scale,
        spo_retryable_followup_dispatch_rps_scale=args.spo_retryable_followup_dispatch_rps_scale,
        spo_retryable_followup_client_rate_scale=args.spo_retryable_followup_client_rate_scale,
        spo_retryable_followup_client_concurrency_scale=args.spo_retryable_followup_client_concurrency_scale,
        spo_request_log_enabled=args.spo_request_log_enabled,
        spo_extract_mode=args.spo_extract_mode,
        spo_skip_trivial=not args.no_spo_skip_trivial,
        spo_verify_mode=args.spo_verify_mode,
        spo_max_provisions_per_doc=args.spo_max_provisions_per_doc,
        graph_amendment_workers=args.graph_amendment_workers,
        graph_amendment_task_chunk=args.graph_amendment_task_chunk,
        graph_amendment_progress_interval=args.graph_amendment_progress_interval,
        jurisdiction=args.jurisdiction,
        pattern_feedback_enabled=args.pattern_feedback_enabled,
        llm_gate_enabled=args.llm_gate_enabled,
        llm_gate_mode=args.llm_gate_mode,
        llm_gate_threshold=args.llm_gate_threshold,
        llm_gate_max_share=args.llm_gate_max_share,
        llm_gate_audit_sample_rate=args.llm_gate_audit_sample_rate,
        llm_gate_audit_max_miss_rate_pct=args.llm_gate_audit_max_miss_rate_pct,
        llm_gap_fill_enabled=args.llm_gap_fill_mode != "off",
        llm_gap_fill_mode=args.llm_gap_fill_mode,
        llm_gap_fill_max_share=args.llm_gap_fill_max_share,
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
        quality_max_hallucination_rate_pct=args.quality_max_hallucination_rate_pct,
        quality_max_unresolved_contradictions=args.quality_max_unresolved_contradictions,
        quality_max_low_confidence_normative_pct=args.quality_max_low_confidence_normative_pct,
        quality_min_reference_resolution_coverage_pct=args.quality_min_reference_resolution_coverage_pct,
        quality_min_amendment_extraction_coverage_pct=args.quality_min_amendment_extraction_coverage_pct,
        quality_min_amendment_target_resolution_pct=args.quality_min_amendment_target_resolution_pct,
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

    from polisyos.data_forge.domains.legal.batch.pipeline import run_batch_pipeline

    stats = asyncio.run(run_batch_pipeline(config))
    if stats.grounded_facts or stats.normative_facts or stats.candidate_facts:
        pass
    if stats.reference_edges:
        pass
    if stats.exported_claims:
        pass
    if getattr(stats, "exported_claim_sets", 0):
        pass
    if stats.published_bundle:
        pass
    if stats.quality_gate_passed is not None or stats.quality_passed is not None:
        pass
    if stats.qc_passed is not None:
        pass
    if stats.benchmark_passed is not None:
        pass
    if stats.release_passed is not None:
        pass
    if config.sharded:
        pass
    if stats.quality_gate_failed_checks:
        pass
    if stats.quality_hotspot_failed_checks:
        pass
    if stats.qc_failed_checks:
        pass
    if stats.benchmark_passed is not None and stats.benchmark_failed_checks:
        pass
    if stats.release_failed_checks:
        pass
    for _stage, _dt in sorted(stats.stage_times.items()):
        pass

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
        artifacts=[
            *run_artifacts,
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

    from polisyos.data_forge.domains.legal.batch.smoke import run_smoke

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
        spo_rate_warmup_seconds=args.spo_rate_warmup_seconds,
        spo_rate_warmup_start_scale=args.spo_rate_warmup_start_scale,
        spo_adaptive_rate_enabled=args.spo_adaptive_rate_enabled,
        spo_adaptive_rate_recovery_factor=args.spo_adaptive_rate_recovery_factor,
        spo_adaptive_rate_penalty_multiplier=args.spo_adaptive_rate_penalty_multiplier,
        spo_adaptive_rate_max_scale=args.spo_adaptive_rate_max_scale,
        spo_retryable_followup_worker_scale=args.spo_retryable_followup_worker_scale,
        spo_retryable_followup_dispatch_rps_scale=args.spo_retryable_followup_dispatch_rps_scale,
        spo_retryable_followup_client_rate_scale=args.spo_retryable_followup_client_rate_scale,
        spo_retryable_followup_client_concurrency_scale=args.spo_retryable_followup_client_concurrency_scale,
        spo_request_batch_chars=args.spo_request_batch_chars,
        spo_adaptive_batch_downshift_enabled=args.spo_adaptive_batch_downshift_enabled,
        spo_adaptive_batch_soft_chars_share=args.spo_adaptive_batch_soft_chars_share,
        spo_group_timeout_seconds=args.spo_group_timeout_seconds,
        llm_gap_fill_mode=args.llm_gap_fill_mode,
        llm_gap_fill_max_share=args.llm_gap_fill_max_share,
        stages=set(args.stages.split(",")) if args.stages else None,
    )
    stats = result["stats"]
    if stats.quality_gate_failed_checks:
        pass
    if stats.quality_hotspot_failed_checks:
        pass
    if stats.qc_failed_checks:
        pass
    if stats.release_failed_checks:
        pass


def _cmd_embed_local(args: argparse.Namespace) -> None:
    from polisyos.data_forge.domains.legal.batch.embedder import build_local_embeddings_and_indexes

    db_path = (
        args.db_path if args.db_path is not None else args.output_dir / "lex_knowledge_graph.duckdb"
    )
    if not db_path.exists():
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
    from polisyos.data_forge.domains.legal.batch.qc import run_qc

    cfg = _minimal_cfg(args.output_dir)
    report = run_qc(cfg, fail_fast=bool(args.fail_fast))

    write_stage_manifest(
        manifest_path=args.output_dir / "manifests" / "qc.json",
        stage="qc",
        status="ok" if report.passed else "failed",
        metrics={"passed": report.passed, **report.metrics},
        artifacts=[args.output_dir / "qc_report.json"],
        started_at=datetime.now(UTC).isoformat(),
    )


def _cmd_benchmark(args: argparse.Namespace) -> None:
    del args
    raise RuntimeError(
        "legal semantic benchmarking is Lex-owned; use polisyos.lex.run_legal_benchmark"
    )


def _cmd_publish(args: argparse.Namespace) -> None:
    from polisyos.data_forge.domains.legal.batch.publish import run_publish

    run_publish(args.output_dir, require_embeddings=bool(args.require_embeddings))


def _cmd_stats(args: argparse.Namespace) -> None:
    import duckdb

    db_path = args.output_dir / "lex_knowledge_graph.duckdb"
    if not db_path.exists():
        sys.exit(1)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()[0]
        con.execute("SELECT COUNT(*) FROM lex_facts").fetchone()[0]
        con.execute("SELECT COUNT(*) FROM lex_provisions").fetchone()[0]
        candidate_facts = _count_table_rows(con, "lex_fact_candidates")
        grounded_facts = _count_table_rows(con, "lex_fact_grounded")
        normative_facts = _count_table_rows(con, "lex_normative_facts")
        reference_edges = _count_table_rows(con, "lex_reference_edges")
        doc_versions = _count_table_rows(con, "lex_doc_versions")
    finally:
        con.close()

    if candidate_facts:
        pass
    if grounded_facts:
        pass
    if normative_facts:
        pass
    if reference_edges:
        pass
    if doc_versions:
        pass


def _cmd_search(args: argparse.Namespace) -> None:
    del args
    raise RuntimeError(
        "interactive legal search is Lex-owned; use "
        "python -m polisyos.lex.knowledge.cli"
    )


def _count_table_rows(con, table_name: str) -> int:  # type: ignore[no-untyped-def]
    exists = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchone()[0]
    if not exists:
        return 0
    return int(con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def main() -> None:
    """Main helper."""
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
