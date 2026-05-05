#!/usr/bin/env python3
"""Run the Lex sharded pipeline from a pre-materialized JSONL.ZST shard manifest."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from io import TextIOWrapper
from pathlib import Path

import zstandard as zstd

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.legal.batch.cli import (
    _clean_lex_output,
    _parse_gonka_api_keys,
)
from polisyos.data_forge.domains.legal.batch.config import ALL_STAGES, BatchConfig
from polisyos.data_forge.domains.legal.batch.pipeline import run_batch_pipeline
from polisyos.data_forge.domains.legal.batch.xml_parser import NPACard, NPADocument
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

logger = get_logger(__name__)


@contextlib.contextmanager
def _open_manifest_text(path: Path) -> Iterator[TextIOWrapper]:
    with contextlib.ExitStack() as stack:
        raw_fh = stack.enter_context(path.open("rb"))
        if path.suffix == ".zst":
            dctx = zstd.ZstdDecompressor()
            reader = stack.enter_context(dctx.stream_reader(raw_fh))
            yield stack.enter_context(TextIOWrapper(reader, encoding="utf-8"))
            return
        yield stack.enter_context(TextIOWrapper(raw_fh, encoding="utf-8"))


def _card_from_payload(payload: dict[str, object]) -> NPACard:
    return NPACard(
        doc_id=str(payload.get("doc_id") or ""),
        reestr_code=str(payload.get("reestr_code") or ""),
        date_acc=str(payload.get("date_acc") or ""),
        reestr_date=str(payload.get("reestr_date") or ""),
        status=str(payload.get("status") or ""),
        doc_type=str(payload.get("doc_type") or ""),
        name=str(payload.get("name") or ""),
        publisher=tuple(str(item) for item in (payload.get("publisher") or [])),
        number=str(payload.get("number") or ""),
        publication=tuple(str(item) for item in (payload.get("publication") or [])),
        keywords=tuple(str(item) for item in (payload.get("keywords") or [])),
        reg_date=str(payload.get("reg_date") or ""),
        reg_number=str(payload.get("reg_number") or ""),
    )


def _iter_documents_from_manifest(
    manifest_path: Path,
    *,
    status_filter: frozenset[str] | None = None,
    type_filter: frozenset[str] | None = None,
    doc_id_filter: frozenset[str] | None = None,
) -> Iterator[NPADocument]:
    logger.info("Streaming documents from shard manifest {}", manifest_path)
    matched = 0
    skipped = 0
    remaining_doc_ids = set(doc_id_filter) if doc_id_filter else None

    with _open_manifest_text(manifest_path) as fh:
        for line_number, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in manifest {manifest_path} at line {line_number}"
                ) from exc
            if not isinstance(payload, dict):
                raise ValueError(
                    f"manifest {manifest_path} line {line_number} must be a JSON object"
                )
            card = _card_from_payload(payload)

            if status_filter and card.status not in status_filter:
                skipped += 1
                continue
            if type_filter and card.doc_type not in type_filter:
                skipped += 1
                continue
            if remaining_doc_ids is not None and card.doc_id not in remaining_doc_ids:
                skipped += 1
                continue

            yield NPADocument(card=card, text=str(payload.get("text") or ""))
            matched += 1

            if remaining_doc_ids is not None:
                remaining_doc_ids.discard(card.doc_id)
                if not remaining_doc_ids:
                    break

            if matched % 10_000 == 0:
                logger.info("Manifest iterator yielded {} docs (skipped {})", matched, skipped)

    logger.info("Manifest iterator complete: yielded={} skipped={}", matched, skipped)


@contextlib.contextmanager
def _patched_iter_documents(manifest_path: Path) -> Iterator[None]:
    import polisyos.data_forge.domains.legal.batch.xml_parser as xml_parser

    original = xml_parser.iter_documents

    def _replacement(
        cards_path: Path,
        texts_path: Path,
        *,
        status_filter: frozenset[str] | None = None,
        type_filter: frozenset[str] | None = None,
        doc_id_filter: frozenset[str] | None = None,
    ) -> Iterator[NPADocument]:
        del cards_path, texts_path
        return _iter_documents_from_manifest(
            manifest_path,
            status_filter=status_filter,
            type_filter=type_filter,
            doc_id_filter=doc_id_filter,
        )

    xml_parser.iter_documents = _replacement
    try:
        yield
    finally:
        xml_parser.iter_documents = original


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, required=True, help="Path to pre-sharded JSONL(.ZST) manifest"
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="Pipeline output directory")
    parser.add_argument(
        "--cards-placeholder",
        type=Path,
        default=None,
        help="Placeholder cards path stored in config metadata when raw XML is unavailable.",
    )
    parser.add_argument(
        "--texts-placeholder",
        type=Path,
        default=None,
        help="Placeholder texts path stored in config metadata when raw XML is unavailable.",
    )
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument(
        "--manifest-is-pre-sharded",
        action="store_true",
        help="Treat the manifest as already assigned to this shard and disable hash-based shard filtering.",
    )
    parser.add_argument("--clean-output", action="store_true")
    parser.add_argument("--resume", action="store_true")

    parser.add_argument("--gonka-api-key", default="")
    parser.add_argument("--gonka-api-keys", default="")
    parser.add_argument("--gonka-base-url", default="https://api.gonkagate.com/v1")
    parser.add_argument("--gonka-disable-json-mode", action="store_true")
    parser.add_argument("--llm-model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
    parser.add_argument("--parallel-llm", type=int, default=20)
    parser.add_argument("--parallel-llm-global", type=int, default=None)
    parser.add_argument("--gonka-rate-limit-rps", type=float, default=5.0)
    parser.add_argument("--max-retries", type=int, default=7)
    parser.add_argument("--llm-temperature", type=float, default=0.1)

    parser.add_argument("--spo-connect-timeout-seconds", type=int, default=15)
    parser.add_argument("--spo-read-timeout-seconds", type=int, default=120)
    parser.add_argument("--spo-total-timeout-seconds", type=int, default=180)
    parser.add_argument("--spo-provider-watchdog-seconds", type=int, default=0)
    parser.add_argument("--spo-rate-warmup-seconds", type=float, default=45.0)
    parser.add_argument("--spo-rate-warmup-start-scale", type=float, default=3.0)
    parser.add_argument(
        "--spo-adaptive-rate-enabled",
        dest="spo_adaptive_rate_enabled",
        action="store_true",
    )
    parser.add_argument(
        "--no-spo-adaptive-rate-enabled",
        dest="spo_adaptive_rate_enabled",
        action="store_false",
    )
    parser.set_defaults(spo_adaptive_rate_enabled=True)
    parser.add_argument("--spo-adaptive-rate-recovery-factor", type=float, default=0.97)
    parser.add_argument("--spo-adaptive-rate-penalty-multiplier", type=float, default=1.35)
    parser.add_argument("--spo-adaptive-rate-max-scale", type=float, default=8.0)

    parser.add_argument("--xml-parse-chunk", type=int, default=5000)
    parser.add_argument("--structure-workers", type=int, default=4)
    parser.add_argument("--disable-structure-paragraphs", action="store_true")
    parser.add_argument("--structure-fallback-chunk-chars", type=int, default=1800)
    parser.add_argument("--structure-fallback-chunk-overlap", type=int, default=200)
    parser.add_argument("--spo-batch-docs", type=int, default=500)
    parser.add_argument("--spo-task-batch-size", type=int, default=1000)
    parser.add_argument("--spo-request-batch-size", type=int, default=5)
    parser.add_argument("--spo-request-batch-chars", type=int, default=6000)
    parser.add_argument(
        "--spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_true",
    )
    parser.add_argument(
        "--no-spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_false",
    )
    parser.set_defaults(spo_adaptive_batch_downshift_enabled=True)
    parser.add_argument("--spo-adaptive-batch-soft-chars-share", type=float, default=0.80)
    parser.add_argument("--spo-group-timeout-seconds", type=float, default=None)
    parser.add_argument(
        "--spo-timeout-retry-enabled", dest="spo_timeout_retry_enabled", action="store_true"
    )
    parser.add_argument(
        "--no-spo-timeout-retry-enabled", dest="spo_timeout_retry_enabled", action="store_false"
    )
    parser.set_defaults(spo_timeout_retry_enabled=True)
    parser.add_argument("--spo-timeout-retry-batch-size", type=int, default=1)
    parser.add_argument("--spo-timeout-retry-chars", type=int, default=3000)
    parser.add_argument("--spo-retryable-followup-passes", type=int, default=1)
    parser.add_argument("--spo-retryable-followup-delay-seconds", type=float, default=5.0)
    parser.add_argument("--spo-retryable-followup-worker-scale", type=float, default=0.5)
    parser.add_argument("--spo-retryable-followup-dispatch-rps-scale", type=float, default=0.5)
    parser.add_argument("--spo-retryable-followup-client-rate-scale", type=float, default=0.5)
    parser.add_argument(
        "--spo-retryable-followup-client-concurrency-scale", type=float, default=0.5
    )
    parser.add_argument(
        "--spo-request-log-enabled", dest="spo_request_log_enabled", action="store_true"
    )
    parser.add_argument(
        "--no-spo-request-log-enabled", dest="spo_request_log_enabled", action="store_false"
    )
    parser.set_defaults(spo_request_log_enabled=True)
    parser.add_argument("--spo-extract-mode", choices=("light", "full"), default="light")
    parser.add_argument("--no-spo-skip-trivial", action="store_true")
    parser.add_argument("--spo-verify-mode", choices=("llm", "code"), default="llm")
    parser.add_argument("--spo-max-provisions-per-doc", type=int, default=None)

    parser.add_argument("--llm-gate-enabled", dest="llm_gate_enabled", action="store_true")
    parser.add_argument("--no-llm-gate-enabled", dest="llm_gate_enabled", action="store_false")
    parser.set_defaults(llm_gate_enabled=True)
    parser.add_argument(
        "--llm-gate-mode", choices=("off", "balanced", "aggressive"), default="balanced"
    )
    parser.add_argument("--llm-gate-threshold", type=float, default=0.55)
    parser.add_argument("--llm-gate-max-share", type=float, default=0.35)
    parser.add_argument("--llm-gate-audit-sample-rate", type=float, default=0.02)
    parser.add_argument("--llm-gate-audit-max-miss-rate-pct", type=float, default=3.0)
    parser.add_argument("--llm-gap-fill-mode", choices=("off", "narrow", "wide"), default="off")
    parser.add_argument("--llm-gap-fill-max-share", type=float, default=0.80)

    parser.add_argument("--jurisdiction", default="UA")
    parser.add_argument(
        "--pattern-feedback-enabled", dest="pattern_feedback_enabled", action="store_true"
    )
    parser.add_argument(
        "--no-pattern-feedback-enabled", dest="pattern_feedback_enabled", action="store_false"
    )
    parser.set_defaults(pattern_feedback_enabled=True)
    parser.add_argument("--extract-references", dest="extract_references", action="store_true")
    parser.add_argument("--no-extract-references", dest="extract_references", action="store_false")
    parser.set_defaults(extract_references=True)
    parser.add_argument("--extract-domains", dest="extract_domains", action="store_true")
    parser.add_argument("--no-extract-domains", dest="extract_domains", action="store_false")
    parser.set_defaults(extract_domains=True)

    parser.add_argument("--disable-quality-gates", action="store_true")
    parser.add_argument("--quality-fail-on-critical", action="store_true")
    parser.add_argument("--quality-max-full-only-docs-pct", type=float, default=25.0)
    parser.add_argument("--status-filter", nargs="*", default=None)
    parser.add_argument("--type-filter", nargs="*", default=None)
    parser.add_argument("--stages", default="all")
    parser.add_argument("--max-docs", type=int, default=None)
    return parser


def _build_config(args: argparse.Namespace) -> BatchConfig:
    cards_placeholder = args.cards_placeholder or args.manifest
    texts_placeholder = args.texts_placeholder or args.manifest
    stages = (
        ALL_STAGES
        if args.stages == "all"
        else frozenset(stage.strip() for stage in args.stages.split(",") if stage.strip())
    )
    return BatchConfig(
        cards_path=cards_placeholder,
        texts_path=texts_placeholder,
        output_dir=args.output_dir,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
        gonka_api_key=args.gonka_api_key,
        gonka_api_keys=_parse_gonka_api_keys(args.gonka_api_keys),
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
        manifest_is_pre_sharded=args.manifest_is_pre_sharded,
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
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    args.manifest = args.manifest.resolve()
    args.output_dir = args.output_dir.resolve()
    if not args.manifest.exists():
        raise FileNotFoundError(f"manifest not found: {args.manifest}")
    if args.clean_output and args.resume:
        raise ValueError("--clean-output cannot be used together with --resume")
    if args.clean_output and args.shard_count > 1 and args.shard_index != 0:
        raise ValueError("In sharded mode use --clean-output only on --shard-index 0.")
    if args.clean_output:
        _clean_lex_output(
            args.output_dir, shard_count=args.shard_count, shard_index=args.shard_index
        )

    config = _build_config(args)
    started_at = datetime.now(UTC).isoformat()

    with _patched_iter_documents(args.manifest):
        stats = asyncio.run(run_batch_pipeline(config))

    print("\nManifest pipeline complete:")
    print(f"  Documents:  {stats.total_docs}")
    print(f"  Provisions: {stats.total_provisions}")
    print(f"  SPO triples:{stats.total_spo}")
    print(f"  Facts:      {stats.facts}")
    print(f"  Time:       {stats.elapsed_seconds:.1f}s")
    if config.sharded:
        print(f"  Shard:      {config.shard_index + 1}/{config.shard_count} ({config.shard_slug})")

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
            config.telemetry_path,
            config.llm_gate_manifest_path,
            config.llm_request_log_path,
            config.progress_path,
        ],
        started_at=started_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
