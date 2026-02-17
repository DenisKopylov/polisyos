"""Orchestrate all stages of the Lex batch pipeline in a memory-friendly way."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.progress import ProgressTracker
from polisyos.lex.batch.provisions_io import read_provisions, write_provisions

if TYPE_CHECKING:
    from polisyos.lex.batch.spo_extractor import GonkaClient
    from polisyos.lex.batch.structurer import ProvisionSpan
    from polisyos.lex.batch.xml_parser import NPADocument

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class PipelineStats:
    total_docs: int = 0
    total_provisions: int = 0
    total_spo: int = 0
    entities: int = 0
    facts: int = 0
    provisions_embedded: int = 0
    elapsed_seconds: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    quality_passed: bool | None = None
    quality_report: dict[str, float] = field(default_factory=dict)
    quality_failed_checks: list[str] = field(default_factory=list)
    quality_skipped_checks: list[str] = field(default_factory=list)


def _extract_provisions_worker(payload: dict) -> list[dict]:
    """Worker function for provision extraction (runs in subprocess)."""
    from polisyos.lex.batch.structurer import extract_provisions

    text = str(payload.get("text", ""))
    spans = extract_provisions(
        text,
        enable_paragraphs=bool(payload.get("enable_paragraphs", True)),
        fallback_chunk_chars=int(payload.get("fallback_chunk_chars") or 1800),
        fallback_chunk_overlap=int(payload.get("fallback_chunk_overlap") or 200),
    )
    return [
        {
            "kind": s.kind,
            "number": s.number,
            "anchor_path": s.anchor_path,
            "citation_label": s.citation_label,
            "offset_start": s.offset_start,
            "offset_end": s.offset_end,
            "text": s.text,
            "parent_anchor": s.parent_anchor,
            "depth": s.depth,
            "token_est": s.token_est,
            "text_hash": s.text_hash,
            "is_fallback_chunk": s.is_fallback_chunk,
        }
        for s in spans
    ]


def _chunked(items: list[T], size: int) -> list[list[T]]:
    chunk_size = max(1, size)
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _as_doc_meta(doc: NPADocument) -> dict:
    return {
        "reestr_code": doc.card.reestr_code,
        "name": doc.card.name,
        "doc_type": doc.card.doc_type,
        "date_acc": doc.card.date_acc,
        "status": doc.card.status,
    }


def _to_provision_spans(prov_dicts: list[dict]) -> list[ProvisionSpan]:
    from polisyos.lex.batch.structurer import ProvisionSpan

    spans: list[ProvisionSpan] = []
    for p in prov_dicts:
        spans.append(
            ProvisionSpan(
                kind=str(p["kind"]),
                number=p.get("number"),
                anchor_path=str(p["anchor_path"]),
                citation_label=str(p["citation_label"]),
                offset_start=int(p["offset_start"]),
                offset_end=int(p["offset_end"]),
                text=str(p["text"]),
                parent_anchor=(
                    str(p.get("parent_anchor"))
                    if p.get("parent_anchor") is not None
                    else None
                ),
                depth=int(p.get("depth") or 0),
                token_est=int(p.get("token_est") or 0),
                text_hash=str(p.get("text_hash") or ""),
                is_fallback_chunk=bool(p.get("is_fallback_chunk", False)),
            )
        )
    return spans


async def _process_structure_chunk(
    *,
    config: BatchConfig,
    progress: ProgressTracker,
    docs_chunk: list[NPADocument],
) -> tuple[dict[str, list[dict]], int]:
    """Extract provisions for one document chunk and persist to disk."""
    docs_to_process = docs_chunk
    if config.resume:
        docs_to_process = [
            d for d in docs_chunk if not progress.is_done(d.card.doc_id, "structured")
        ]

    if not docs_to_process:
        return {}, 0

    workers = min(config.structure_workers, len(docs_to_process))
    provisions_by_doc: dict[str, list[dict]] = {}
    total_provisions = 0
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                _extract_provisions_worker,
                {
                    "text": doc.text,
                    "enable_paragraphs": config.structure_enable_paragraphs,
                    "fallback_chunk_chars": config.structure_fallback_chunk_chars,
                    "fallback_chunk_overlap": config.structure_fallback_chunk_overlap,
                },
            ): doc.card.doc_id
            for doc in docs_to_process
        }
        for future in as_completed(futures):
            doc_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - worker crash is environment-specific
                logger.warning("Structure extraction failed for %s: %s", doc_id, exc)
                continue
            provisions_by_doc[doc_id] = result
            total_provisions += len(result)
            write_provisions(
                provisions_dir=config.provisions_dir,
                doc_id=doc_id,
                provisions=result,
            )
            progress.mark_done(doc_id, "structured", stats={"provisions": len(result)})
    return provisions_by_doc, total_provisions


async def _process_spo_chunk(
    *,
    config: BatchConfig,
    progress: ProgressTracker,
    docs_chunk: list[NPADocument],
    structure_cache: dict[str, list[dict]],
    spo_client: GonkaClient | None,
) -> int:
    """Run SPO extraction for one document chunk."""
    if spo_client is None:
        return 0

    from polisyos.lex.batch.spo_extractor import extract_spo_for_documents

    docs_for_spo: list[NPADocument] = []
    spans_by_doc: dict[str, list[ProvisionSpan]] = {}
    for doc in docs_chunk:
        doc_id = doc.card.doc_id
        if config.resume and progress.is_done(doc_id, "spo_extracted"):
            continue

        prov_rows = structure_cache.get(doc_id)
        if prov_rows is None:
            prov_rows = read_provisions(provisions_dir=config.provisions_dir, doc_id=doc_id)
        if not prov_rows:
            continue

        spans = _to_provision_spans(prov_rows)
        if not spans:
            continue

        if config.spo_max_provisions_per_doc is not None:
            limit = int(config.spo_max_provisions_per_doc)
            if len(spans) > limit:
                # Prefer structured spans; fall back to full-text chunks only if needed.
                structured = [s for s in spans if not s.is_fallback_chunk]
                fallback = [s for s in spans if s.is_fallback_chunk]
                spans = (structured + fallback)[:limit]

        docs_for_spo.append(doc)
        spans_by_doc[doc_id] = spans

    if not docs_for_spo:
        return 0

    total_spo = 0
    for docs_batch in _chunked(docs_for_spo, config.spo_batch_docs):
        batch_spo, failed_ids = await extract_spo_for_documents(
            spo_client,
            docs_batch,
            spans_by_doc,
            results_dir=config.spo_results_dir,
            task_batch_size=config.spo_task_batch_size,
            verify_mode=config.spo_verify_mode,
        )
        total_spo += batch_spo
        for doc in docs_batch:
            if doc.card.doc_id not in failed_ids:
                progress.mark_done(doc.card.doc_id, "spo_extracted")
    return total_spo


async def run_batch_pipeline(config: BatchConfig) -> PipelineStats:
    """Run configured stages sequentially with bounded memory."""
    t0 = time.monotonic()
    stats = PipelineStats()
    progress = ProgressTracker(config.progress_path)

    from polisyos.lex.batch.xml_parser import iter_documents

    doc_metadata: dict[str, dict] = {}
    needs_document_stream = bool({"parse", "structure", "spo", "graph"} & set(config.stages))
    if needs_document_stream:
        parse_start = time.monotonic()
        structure_elapsed = 0.0
        spo_elapsed = 0.0

        logger.info("=== Streaming documents ===")
        if config.sharded:
            logger.info(
                "Sharding enabled: %s (%d/%d)",
                config.shard_slug,
                config.shard_index + 1,
                config.shard_count,
            )
        run_structure = "structure" in config.stages
        run_spo = "spo" in config.stages and bool(config.gonka_api_key)
        if "spo" in config.stages and not config.gonka_api_key:
            logger.error("GONKA_API_KEY not set — skipping SPO extraction.")

        spo_client: GonkaClient | None = None
        if run_spo:
            from polisyos.lex.batch.spo_extractor import GonkaClient

            spo_client = GonkaClient(
                api_key=config.gonka_api_key,
                base_url=config.gonka_base_url,
                model=config.llm_model,
                disable_json_mode=config.gonka_disable_json_mode,
                max_concurrent=config.max_concurrent_llm,
                rate_limit_rps=config.rate_limit_rps,
                temperature=config.llm_temperature,
                max_retries=config.max_retries,
            )
            logger.info("SPO verify mode: %s", config.spo_verify_mode)

        # --max-docs: determine which progress stage to count "new" docs against
        _target_stage: str | None = None
        if run_spo:
            _target_stage = "spo_extracted"
        elif run_structure:
            _target_stage = "structured"
        new_docs_count = 0

        chunk: list[NPADocument] = []
        if spo_client is not None:
            await spo_client.__aenter__()
        try:
            for doc in iter_documents(
                config.cards_path,
                config.texts_path,
                status_filter=set(config.status_filter) if config.status_filter else None,
                type_filter=set(config.type_filter) if config.type_filter else None,
            ):
                if not config.is_doc_in_shard(doc.card.doc_id):
                    continue

                # --max-docs: count only docs that still need work
                is_new = _target_stage is None or not progress.is_done(
                    doc.card.doc_id, _target_stage,
                )
                if is_new:
                    new_docs_count += 1

                stats.total_docs += 1
                doc_metadata[doc.card.doc_id] = _as_doc_meta(doc)
                chunk.append(doc)

                # Flush chunk when full OR when --max-docs limit reached
                reached_limit = (
                    config.max_docs is not None and new_docs_count >= config.max_docs
                )
                if not reached_limit and len(chunk) < max(1, config.xml_parse_chunk):
                    continue

                if run_structure:
                    st = time.monotonic()
                    structure_cache, added = await _process_structure_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                    )
                    stats.total_provisions += added
                    structure_elapsed += time.monotonic() - st
                else:
                    structure_cache = {}

                if run_spo:
                    st = time.monotonic()
                    stats.total_spo += await _process_spo_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                        structure_cache=structure_cache,
                        spo_client=spo_client,
                    )
                    spo_elapsed += time.monotonic() - st
                chunk.clear()

                if reached_limit:
                    logger.info(
                        "Reached --max-docs limit (%d new documents). Stopping.",
                        config.max_docs,
                    )
                    break

            if chunk:
                if run_structure:
                    st = time.monotonic()
                    structure_cache, added = await _process_structure_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                    )
                    stats.total_provisions += added
                    structure_elapsed += time.monotonic() - st
                else:
                    structure_cache = {}

                if run_spo:
                    st = time.monotonic()
                    stats.total_spo += await _process_spo_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                        structure_cache=structure_cache,
                        spo_client=spo_client,
                    )
                    spo_elapsed += time.monotonic() - st
                chunk.clear()
        finally:
            if spo_client is not None:
                await spo_client.__aexit__(None, None, None)

        if "parse" in config.stages:
            stats.stage_times["parse"] = time.monotonic() - parse_start
        if "structure" in config.stages:
            stats.stage_times["structure"] = structure_elapsed
        if "spo" in config.stages:
            stats.stage_times["spo"] = spo_elapsed

        if stats.total_docs == 0:
            logger.warning("No documents found. Pipeline complete.")
            stats.elapsed_seconds = time.monotonic() - t0
            return stats

    if "graph" in config.stages:
        st = time.monotonic()
        logger.info("=== Stage 4: Build graph ===")
        from polisyos.lex.batch.graph_builder import build_graph

        graph_stats = build_graph(
            spo_results_dir=config.spo_results_dir,
            provisions_dir=config.provisions_dir,
            doc_metadata=doc_metadata,
            db_path=config.db_path,
            insert_batch_size=config.graph_insert_batch,
        )
        stats.entities = graph_stats.entities
        stats.facts = graph_stats.facts
        stats.stage_times["graph"] = time.monotonic() - st

    if "embed" in config.stages:
        st = time.monotonic()
        logger.info("=== Stage 5: Submit embedding batches ===")
        if not config.openai_api_key:
            logger.error("OPENAI_API_KEY not set — skipping embedding batch submit.")
        else:
            from polisyos.lex.batch.openai_batch_embeddings import submit_embedding_batches

            submit_embedding_batches(
                db_path=config.db_path,
                output_dir=config.output_dir,
                api_key=config.openai_api_key,
                model=config.embedding_model,
                dimensions=config.embedding_dimension,
                chunk_size=config.embedding_chunk_size,
            )
        stats.stage_times["embed"] = time.monotonic() - st

    if config.quality_gates_enabled and "spo" in config.stages:
        st = time.monotonic()
        logger.info("=== Quality gates ===")
        from polisyos.lex.batch.quality_report import (
            QualityGateThresholds,
            build_quality_report,
            evaluate_quality_gates,
        )

        report = build_quality_report(
            provisions_dir=config.provisions_dir,
            spo_results_dir=config.spo_results_dir,
        )
        thresholds = QualityGateThresholds(
            max_full_only_docs_pct=config.quality_max_full_only_docs_pct,
            max_empty_statement_rows_pct=config.quality_max_empty_statement_rows_pct,
            max_oov_action_rate_pct=config.quality_max_oov_action_rate_pct,
            max_missing_quote_rate_pct=config.quality_max_missing_quote_rate_pct,
            max_duplicate_anchor_rate_pct=config.quality_max_duplicate_anchor_rate_pct,
            min_provision_docs_for_doc_rate=config.quality_min_provision_docs_for_doc_rate,
            min_spo_rows_for_row_rate=config.quality_min_spo_rows_for_row_rate,
            min_statements_for_statement_rate=config.quality_min_statements_for_statement_rate,
        )
        gate = evaluate_quality_gates(report=report, thresholds=thresholds)
        stats.quality_passed = gate.passed
        stats.quality_failed_checks = list(gate.failed_checks)
        stats.quality_skipped_checks = list(gate.skipped_checks)
        stats.quality_report = {
            key: float(value) if isinstance(value, (int, float)) else 0.0
            for key, value in gate.report.items()
            if isinstance(value, (int, float))
        }
        stats.stage_times["quality"] = time.monotonic() - st

        logger.info(
            "Quality report: full_only=%.2f%% empty_rows=%.2f%% oov_action=%.2f%% missing_quote=%.2f%% dup_anchor=%.3f%%",
            float(report.get("full_only_docs_pct", 0.0)),
            float(report.get("empty_statement_rows_pct", 0.0)),
            float(report.get("oov_action_rate_pct", 0.0)),
            float(report.get("missing_quote_rate_pct", 0.0)),
            float(report.get("duplicate_anchor_rate_pct", 0.0)),
        )
        if gate.skipped_checks:
            logger.info("Quality checks skipped due to low sample size: %s", ", ".join(gate.skipped_checks))
        if (not gate.passed) and (not config.quality_fail_on_critical):
            logger.warning(
                "Quality gates failed (warn-only): %s",
                ", ".join(gate.failed_checks),
            )
        if (not gate.passed) and config.quality_fail_on_critical:
            raise RuntimeError(
                f"Quality gates failed: {', '.join(gate.failed_checks)}. "
                f"Report: {gate.report}"
            )

    stats.elapsed_seconds = time.monotonic() - t0
    logger.info(
        "Pipeline complete in %.1fs: %d docs, %d entities, %d facts",
        stats.elapsed_seconds,
        stats.total_docs,
        stats.entities,
        stats.facts,
    )
    return stats
