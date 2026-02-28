"""Orchestrate all stages of the Lex batch pipeline in a memory-friendly way."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.progress import ProgressTracker
from polisyos.lex.batch.provisions_io import read_provisions, write_provisions

if TYPE_CHECKING:
    from polisyos.lex.batch.llm_gate import GateRuntime
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
    llm_gate_metrics: dict[str, float | int] = field(default_factory=dict)


@dataclass
class LLMGateStats:
    """Runtime counters for LLM gating decisions."""

    provisions_seen: int = 0
    skipped_total: int = 0
    auto_by_code_total: int = 0
    llm_candidate_total: int = 0
    llm_sent_total: int = 0
    deferred_total: int = 0
    audit_sample_total: int = 0
    audit_miss_total: int = 0
    circuit_breaker_hits: int = 0
    dedup_reused_total: int = 0

    @property
    def llm_saved_pct(self) -> float:
        if self.llm_candidate_total <= 0:
            return 100.0
        saved = max(0, self.llm_candidate_total - self.llm_sent_total)
        return (saved * 100.0) / self.llm_candidate_total

    @property
    def audit_miss_rate_pct(self) -> float:
        if self.audit_sample_total <= 0:
            return 0.0
        return (self.audit_miss_total * 100.0) / self.audit_sample_total


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


def _write_jsonl_rows(path: str, rows: list[dict], *, append: bool) -> None:
    from pathlib import Path

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(out_path, mode, encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _doc_content_hash(text: str) -> str:
    """Compute a short content hash for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _write_doc_domain(*, domains_dir: str, doc_id: str, payload: dict) -> None:
    from pathlib import Path

    out_path = Path(domains_dir) / doc_id[:2].lower() / f"{doc_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


async def _process_structure_chunk(
    *,
    config: BatchConfig,
    progress: ProgressTracker,
    docs_chunk: list[NPADocument],
) -> tuple[dict[str, list[dict]], int]:
    """Extract provisions for one document chunk and persist to disk."""
    docs_to_process: list[NPADocument] = []
    for d in docs_chunk:
        doc_hash = _doc_content_hash(d.text)
        if config.resume and progress.is_done_with_hash(d.card.doc_id, "structured", doc_hash):
            continue
        # Even without --resume, skip if provisions file exists and hash matches.
        from polisyos.lex.batch.provisions_io import provision_file_path

        if provision_file_path(config.provisions_dir, d.card.doc_id).exists():
            if progress.is_done_with_hash(d.card.doc_id, "structured", doc_hash):
                continue
        docs_to_process.append(d)

    if not docs_to_process:
        return {}, 0

    workers = min(config.structure_workers, len(docs_to_process))
    provisions_by_doc: dict[str, list[dict]] = {}
    total_provisions = 0
    doc_text_by_id = {d.card.doc_id: d.text for d in docs_to_process}
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
            doc_hash = _doc_content_hash(doc_text_by_id[doc_id])
            progress.mark_done(
                doc_id, "structured",
                stats={"provisions": len(result)},
                content_hash=doc_hash,
            )
    return provisions_by_doc, total_provisions


async def _process_spo_chunk(
    *,
    config: BatchConfig,
    progress: ProgressTracker,
    docs_chunk: list[NPADocument],
    structure_cache: dict[str, list[dict]],
    spo_client: GonkaClient | None,
    gate_runtime: GateRuntime,
    gate_stats: LLMGateStats,
) -> int:
    """Run SPO extraction for one document chunk with deterministic-first gating."""
    from polisyos.lex.batch.deterministic_spo import extract_deterministic_spo
    from polisyos.lex.batch.domain_classifier import classify_domains
    from polisyos.lex.batch.llm_gate import build_gate_features, decide_route
    from polisyos.lex.batch.provisions_io import _shard_prefix
    from polisyos.lex.batch.reference_extractor import extract_references
    from polisyos.lex.batch.rule_classifier import classify_provision
    from polisyos.lex.batch.spo_extractor import extract_spo_for_documents
    from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult

    llm_available = spo_client is not None
    docs_for_llm: dict[str, NPADocument] = {}
    docs_for_audit_llm: dict[str, NPADocument] = {}
    spans_by_doc_llm: dict[str, list[ProvisionSpan]] = {}
    spans_by_doc_audit: dict[str, list[ProvisionSpan]] = {}
    gate_meta_by_anchor: dict[str, dict[str, tuple[float, list[str]]]] = {}
    gate_meta_by_anchor_audit: dict[str, dict[str, tuple[float, list[str]]]] = {}
    audit_baseline: dict[str, dict[str, int]] = {}
    docs_to_mark_done: set[str] = set()

    # --- Provision deduplication across all docs in this chunk ---
    # Maps text_hash → (doc_id, anchor_path) of the first occurrence.
    # Duplicate provisions get their SPO results cloned from the first.
    dedup_map: dict[str, tuple[str, str]] = {}  # text_hash → (doc_id, anchor)
    dedup_pending: dict[str, list[tuple[str, ProvisionSpan]]] = {}  # text_hash → [(doc_id, span), ...]

    total_spo = 0
    for doc in docs_chunk:
        doc_id = doc.card.doc_id
        doc_hash = _doc_content_hash(doc.text)
        if config.resume and progress.is_done_with_hash(doc_id, "spo_extracted", doc_hash):
            continue

        prov_rows = structure_cache.get(doc_id)
        if prov_rows is None:
            prov_rows = read_provisions(provisions_dir=config.provisions_dir, doc_id=doc_id)
        if not prov_rows:
            progress.mark_done(doc_id, "spo_extracted", content_hash=doc_hash)
            continue

        spans = _to_provision_spans(prov_rows)
        if not spans:
            progress.mark_done(doc_id, "spo_extracted", content_hash=doc_hash)
            continue

        if config.spo_max_provisions_per_doc is not None:
            limit = int(config.spo_max_provisions_per_doc)
            if len(spans) > limit:
                structured = [s for s in spans if not s.is_fallback_chunk]
                fallback = [s for s in spans if s.is_fallback_chunk]
                spans = (structured + fallback)[:limit]

        # Reset per-doc SPO output when not resuming.
        spo_path = config.spo_results_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"
        if not config.resume and spo_path.exists():
            spo_path.unlink()

        # Deterministic reference graph.
        if config.extract_references_enabled:
            reference_rows: list[dict] = []
            for span in spans:
                for hit in extract_references(
                    text=span.text,
                    doc_id=doc_id,
                    anchor_path=span.anchor_path,
                ):
                    reference_rows.append(hit.as_dict())
            if reference_rows:
                _write_jsonl_rows(
                    str(config.references_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"),
                    reference_rows,
                    append=False,
                )

        # Deterministic domain classification.
        if config.extract_domains_enabled:
            domain_payload = classify_domains(
                text=f"{doc.card.name}\n{doc.text}",
                doc_id=doc_id,
            ).as_dict()
            _write_doc_domain(
                domains_dir=str(config.domains_dir),
                doc_id=doc_id,
                payload=domain_payload,
            )

        # --- Template-based full-document extraction (before per-provision loop) ---
        from polisyos.lex.batch.template_extractor import try_template_extraction

        template_match = try_template_extraction(
            doc_id=doc_id,
            doc_type=doc.card.doc_type,
            publisher=doc.card.publisher,
            doc_title=doc.card.name,
            provisions=[
                {"text": s.text, "anchor_path": s.anchor_path, "citation_label": s.citation_label}
                for s in spans
            ],
        )
        if template_match.matched and template_match.results:
            template_rows: list[dict] = []
            for tmpl_result in template_match.results:
                template_rows.append(tmpl_result.model_dump(mode="json"))
                total_spo += len(tmpl_result.statements)
                gate_stats.auto_by_code_total += len(tmpl_result.statements)
                gate_stats.provisions_seen += 1
            _write_jsonl_rows(str(spo_path), template_rows, append=True)
            docs_to_mark_done.add(doc_id)
            continue

        local_rows: list[dict] = []
        docs_to_mark_done.add(doc_id)
        for span in spans:
            gate_stats.provisions_seen += 1

            # --- Provision dedup by text_hash ---
            th = span.text_hash
            if th and th in dedup_map:
                # This text was already processed; defer result cloning.
                dedup_pending.setdefault(th, []).append((doc_id, span))
                gate_stats.dedup_reused_total += 1
                continue
            if th:
                dedup_map[th] = (doc_id, span.anchor_path)

            reference_hits = (
                extract_references(
                    text=span.text,
                    doc_id=doc_id,
                    anchor_path=span.anchor_path,
                )
                if config.extract_references_enabled
                else []
            )

            if config.spo_skip_trivial:
                cls = classify_provision(span.text, span.citation_label)
                if cls.action == "skip":
                    gate_stats.skipped_total += 1
                    continue
                if cls.action == "auto" and cls.auto_statements:
                    candidates: list[SPOCandidate] = []
                    for st in cls.auto_statements:
                        try:
                            candidates.append(
                                SPOCandidate.model_validate(
                                    {
                                        "subject_en": st.get("subject_uk", ""),
                                        "subject_uk": st.get("subject_uk", ""),
                                        "predicate": st.get("predicate", "requires"),
                                        "object_en": st.get("object_uk", ""),
                                        "object_uk": st.get("object_uk", ""),
                                        "fact_text": st.get("fact_text", ""),
                                        "confidence": float(st.get("confidence", "0.9")),
                                        "norm_type": st.get("norm_type", "obligation"),
                                        "action_raw": st.get("predicate", "requires"),
                                        "action_canon": st.get("predicate", "requires"),
                                        "norm_type_raw": st.get("norm_type", "obligation"),
                                        "norm_type_canon": st.get("norm_type", "obligation"),
                                        "source_quote_uk": st.get("source_quote_uk", ""),
                                    }
                                )
                            )
                        except Exception:
                            continue
                    if candidates:
                        result = SPOExtractionResult(
                            doc_id=doc_id,
                            provision_anchor=span.anchor_path,
                            provision_citation=span.citation_label,
                            statements=candidates,
                            prompt_version="rule_classifier_v1",
                            extract_passes=0,
                            extraction_source="rule_auto",
                            gate_score=0.0,
                            gate_reason_codes=["rule_classifier_auto"],
                        )
                        local_rows.append(result.model_dump(mode="json"))
                        total_spo += len(candidates)
                        gate_stats.auto_by_code_total += len(candidates)
                    continue

            deterministic = extract_deterministic_spo(
                text=span.text,
                citation_label=span.citation_label,
                doc_title=doc.card.name,
            )

            gate_stats.llm_candidate_total += 1
            llm_share = gate_stats.llm_sent_total / max(1, gate_stats.llm_candidate_total)
            features = build_gate_features(
                text=span.text,
                deterministic_confidence=deterministic.confidence,
                reference_count=len(reference_hits),
                fallback_chunk=span.is_fallback_chunk,
                publisher=" ".join(doc.card.publisher) if doc.card.publisher else "",
            )
            decision = decide_route(
                gate_enabled=config.llm_gate_enabled,
                runtime=gate_runtime,
                llm_available=llm_available,
                llm_share=llm_share,
                deterministic_confidence=deterministic.confidence,
                auto_conf_threshold=config.llm_gate_auto_conf_threshold,
                min_score_force_llm=config.llm_gate_min_score_force_llm,
                features=features,
                audit_sample_rate=config.llm_gate_audit_sample_rate,
                audit_seed=f"{doc_id}:{span.anchor_path}",
            )
            reason_codes = sorted(set(decision.reason_codes + deterministic.reason_codes))

            if decision.route == "auto":
                result = SPOExtractionResult(
                    doc_id=doc_id,
                    provision_anchor=span.anchor_path,
                    provision_citation=span.citation_label,
                    statements=deterministic.candidates,
                    prompt_version="deterministic_spo_v1",
                    extract_passes=0,
                    low_confidence=deterministic.confidence < config.llm_gate_auto_conf_threshold,
                    extraction_source="rule_auto",
                    gate_score=decision.score,
                    gate_reason_codes=reason_codes,
                )
                local_rows.append(result.model_dump(mode="json"))
                total_spo += len(deterministic.candidates)
                gate_stats.auto_by_code_total += len(deterministic.candidates)
                continue

            if decision.route == "llm" and llm_available:
                docs_for_llm[doc_id] = doc
                spans_by_doc_llm.setdefault(doc_id, []).append(span)
                gate_meta_by_anchor.setdefault(doc_id, {})[span.anchor_path] = (decision.score, reason_codes)
                gate_stats.llm_sent_total += 1
                continue

            if decision.route == "audit_llm" and llm_available:
                docs_for_audit_llm[doc_id] = doc
                spans_by_doc_audit.setdefault(doc_id, []).append(span)
                gate_meta_by_anchor_audit.setdefault(doc_id, {})[span.anchor_path] = (decision.score, reason_codes)
                audit_baseline.setdefault(doc_id, {})[span.anchor_path] = len(deterministic.candidates)
                gate_stats.audit_sample_total += 1
                gate_stats.llm_sent_total += 1
                continue

            # deferred: keep deterministic rows but mark provenance and low confidence.
            result = SPOExtractionResult(
                doc_id=doc_id,
                provision_anchor=span.anchor_path,
                provision_citation=span.citation_label,
                statements=deterministic.candidates,
                prompt_version="deterministic_spo_v1",
                extract_passes=0,
                low_confidence=True,
                low_confidence_reasons=["deferred_no_llm"],
                extraction_source="deferred",
                gate_score=decision.score,
                gate_reason_codes=reason_codes,
            )
            local_rows.append(result.model_dump(mode="json"))
            total_spo += len(deterministic.candidates)
            gate_stats.deferred_total += 1

        if local_rows:
            _write_jsonl_rows(str(spo_path), local_rows, append=True)

    failed_doc_ids_total: set[str] = set()
    if llm_available and docs_for_llm:
        llm_docs = list(docs_for_llm.values())
        for docs_batch in _chunked(llm_docs, config.spo_batch_docs):
            batch_spo, failed_ids = await extract_spo_for_documents(
                spo_client,
                docs_batch,
                spans_by_doc_llm,
                results_dir=config.spo_results_dir,
                task_batch_size=config.spo_task_batch_size,
                request_batch_size=config.spo_request_batch_size,
                verify_mode=config.spo_verify_mode,
                extract_mode=config.spo_extract_mode,
                overwrite_existing=False,
                extraction_source="llm",
                gate_meta_by_anchor=gate_meta_by_anchor,
            )
            total_spo += batch_spo
            failed_doc_ids_total.update(failed_ids)

    if llm_available and docs_for_audit_llm:
        audit_rows: list[dict] = []
        chunk_audit_miss = 0
        chunk_audit_total = 0

        def _audit_sink(row: dict[str, object]) -> None:
            nonlocal chunk_audit_miss, chunk_audit_total
            doc_id = str(row.get("doc_id", ""))
            anchor = str(row.get("provision_anchor", ""))
            statements = row.get("statements")
            llm_count = len(statements) if isinstance(statements, list) else 0
            baseline_count = int(audit_baseline.get(doc_id, {}).get(anchor, 0))
            miss = llm_count > baseline_count
            chunk_audit_total += 1
            if miss:
                chunk_audit_miss += 1
            audit_rows.append(
                {
                    "doc_id": doc_id,
                    "provision_anchor": anchor,
                    "baseline_count": baseline_count,
                    "llm_count": llm_count,
                    "miss": miss,
                }
            )

        audit_docs = list(docs_for_audit_llm.values())
        for docs_batch in _chunked(audit_docs, config.spo_batch_docs):
            batch_spo, failed_ids = await extract_spo_for_documents(
                spo_client,
                docs_batch,
                spans_by_doc_audit,
                results_dir=config.spo_results_dir,
                task_batch_size=config.spo_task_batch_size,
                request_batch_size=config.spo_request_batch_size,
                verify_mode=config.spo_verify_mode,
                extract_mode=config.spo_extract_mode,
                overwrite_existing=False,
                extraction_source="audit_llm",
                gate_meta_by_anchor=gate_meta_by_anchor_audit,
                result_sink=_audit_sink,
            )
            total_spo += batch_spo
            failed_doc_ids_total.update(failed_ids)

        if audit_rows:
            _write_jsonl_rows(str(config.llm_gate_audit_path), audit_rows, append=True)
        gate_stats.audit_miss_total += chunk_audit_miss
        if chunk_audit_total > 0:
            miss_rate = (chunk_audit_miss * 100.0) / chunk_audit_total
            if gate_runtime.register_audit_miss_rate(miss_rate):
                logger.warning(
                    "LLM gate circuit breaker triggered (audit miss rate %.2f%%). Safe-pass enabled.",
                    miss_rate,
                )
            gate_stats.circuit_breaker_hits = gate_runtime.circuit_breaker_hits

    # --- Resolve dedup pending: clone SPO results for duplicate provisions ---
    if dedup_pending:
        from polisyos.lex.batch.provisions_io import _shard_prefix as _sp

        for text_hash, duplicates in dedup_pending.items():
            orig_doc_id, orig_anchor = dedup_map.get(text_hash, ("", ""))
            if not orig_doc_id:
                continue
            # Read the original SPO result for this provision.
            orig_spo_path = config.spo_results_dir / _sp(orig_doc_id) / f"{orig_doc_id}.jsonl"
            orig_row: dict | None = None
            if orig_spo_path.exists():
                with open(orig_spo_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        if row.get("provision_anchor") == orig_anchor:
                            orig_row = row
                            break
            if orig_row is None:
                continue
            # Clone for each duplicate.
            for dup_doc_id, dup_span in duplicates:
                cloned = dict(orig_row)
                cloned["doc_id"] = dup_doc_id
                cloned["provision_anchor"] = dup_span.anchor_path
                cloned["provision_citation"] = dup_span.citation_label
                cloned["extraction_source"] = "dedup_clone"
                dup_spo_path = config.spo_results_dir / _sp(dup_doc_id) / f"{dup_doc_id}.jsonl"
                _write_jsonl_rows(str(dup_spo_path), [cloned], append=True)
                stmts = cloned.get("statements", [])
                total_spo += len(stmts) if isinstance(stmts, list) else 0

        if gate_stats.dedup_reused_total > 0:
            logger.info("Provision dedup: %d provisions reused from %d unique texts",
                        gate_stats.dedup_reused_total, len(dedup_map))

    for doc_id in docs_to_mark_done:
        if doc_id not in failed_doc_ids_total:
            doc_hash = _doc_content_hash(next(
                (d.text for d in docs_chunk if d.card.doc_id == doc_id), "",
            ))
            progress.mark_done(doc_id, "spo_extracted", content_hash=doc_hash)

    logger.info(
        "LLM gate chunk: seen=%d auto=%d llm_sent=%d deferred=%d skipped=%d dedup=%d audit_miss_rate=%.2f%%",
        gate_stats.provisions_seen,
        gate_stats.auto_by_code_total,
        gate_stats.llm_sent_total,
        gate_stats.deferred_total,
        gate_stats.skipped_total,
        gate_stats.dedup_reused_total,
        gate_stats.audit_miss_rate_pct,
    )
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
        run_spo = "spo" in config.stages
        llm_available = bool(config.gonka_api_key)
        if run_spo and not llm_available:
            logger.warning("GONKA_API_KEY not set — running deterministic SPO only (no LLM calls).")

        spo_client: GonkaClient | None = None
        if run_spo and llm_available:
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
            if config.spo_cache_enabled:
                from polisyos.lex.batch.spo_cache import SPOCache

                cache_path = config.spo_cache_path or (config.output_dir / "spo_cache.sqlite")
                spo_response_cache = SPOCache(cache_path)
                spo_client.set_cache(spo_response_cache)
                logger.info("SPO response cache enabled: %s", cache_path)
            else:
                spo_response_cache = None

            logger.info(
                "SPO extract_mode=%s, verify_mode=%s, skip_trivial=%s, gate_mode=%s",
                config.spo_extract_mode,
                config.spo_verify_mode,
                config.spo_skip_trivial,
                config.llm_gate_mode,
            )
        if run_spo:
            from polisyos.lex.batch.llm_gate import GateRuntime

            gate_runtime = GateRuntime(
                threshold=config.llm_gate_threshold,
                mode=config.llm_gate_mode,
                max_share=config.llm_gate_max_share,
                audit_max_miss_rate_pct=config.llm_gate_audit_max_miss_rate_pct,
                circuit_breaker_enabled=config.llm_gate_circuit_breaker_enabled,
            )
            gate_stats = LLMGateStats()
        else:
            gate_runtime = None
            gate_stats = LLMGateStats()

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
                        gate_runtime=gate_runtime,
                        gate_stats=gate_stats,
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
                        gate_runtime=gate_runtime,
                        gate_stats=gate_stats,
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
            stats.llm_gate_metrics = {
                "provisions_seen": gate_stats.provisions_seen,
                "skipped_total": gate_stats.skipped_total,
                "auto_by_code_total": gate_stats.auto_by_code_total,
                "llm_candidate_total": gate_stats.llm_candidate_total,
                "llm_sent_total": gate_stats.llm_sent_total,
                "deferred_total": gate_stats.deferred_total,
                "dedup_reused_total": gate_stats.dedup_reused_total,
                "llm_saved_pct": round(gate_stats.llm_saved_pct, 3),
                "audit_sample_total": gate_stats.audit_sample_total,
                "audit_miss_total": gate_stats.audit_miss_total,
                "audit_miss_rate_pct": round(gate_stats.audit_miss_rate_pct, 3),
                "circuit_breaker_hits": gate_stats.circuit_breaker_hits,
                "safe_pass_active": int(bool(gate_runtime.safe_pass_active)) if gate_runtime else 0,
            }
            (config.output_dir / "manifests").mkdir(parents=True, exist_ok=True)
            with open(config.llm_gate_manifest_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "kind": "stage",
                        "stage": "llm_gate",
                        "mode": config.llm_gate_mode,
                        "gate_enabled": config.llm_gate_enabled,
                        "threshold": config.llm_gate_threshold,
                        "max_share": config.llm_gate_max_share,
                        "metrics": stats.llm_gate_metrics,
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )

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
            references_dir=config.references_dir if config.extract_references_enabled else None,
            domains_dir=config.domains_dir if config.extract_domains_enabled else None,
            doc_metadata=doc_metadata,
            db_path=config.db_path,
            insert_batch_size=config.graph_insert_batch,
        )
        stats.entities = graph_stats.entities
        stats.facts = graph_stats.facts
        stats.stage_times["graph"] = time.monotonic() - st

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
            llm_gate_manifest_path=config.llm_gate_manifest_path,
            llm_gate_audit_path=config.llm_gate_audit_path,
        )
        thresholds = QualityGateThresholds(
            max_full_only_docs_pct=config.quality_max_full_only_docs_pct,
            max_empty_statement_rows_pct=config.quality_max_empty_statement_rows_pct,
            max_oov_action_rate_pct=config.quality_max_oov_action_rate_pct,
            max_missing_quote_rate_pct=config.quality_max_missing_quote_rate_pct,
            max_duplicate_anchor_rate_pct=config.quality_max_duplicate_anchor_rate_pct,
            max_audit_miss_rate_pct=config.quality_max_audit_miss_rate_pct,
            min_llm_saved_pct=config.quality_min_llm_saved_pct,
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
        if gate.warning_failed_checks:
            logger.warning("Quality warning checks failed: %s", ", ".join(gate.warning_failed_checks))
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
