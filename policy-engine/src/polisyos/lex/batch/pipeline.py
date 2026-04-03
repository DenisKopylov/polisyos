"""Orchestrate all stages of the Lex batch pipeline in a memory-friendly way."""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from polisyos.common.logger import get_logger
from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.doc_family import classify_doc_family, infer_doc_type_category
from polisyos.lex.batch.pipeline_helpers import (
    _active_references_dir,
    _active_spo_results_dir,
    _as_doc_meta,
    _build_llm_fallback_row,
    _build_spo_doc_routing_plan,
    _bump_counter,
    _call_extract_spo_for_documents,
    _check_structure_quality_gate,
    _chunked,
    _doc_content_hash,
    _extract_provisions_worker,
    _group_docs_by_spo_settings,
    _process_structure_chunk,
    _should_extract_spo_from_span,
    _should_route_llm_gap_fill,
    _should_skip_audit_for_span,
    _span_signal_payload,
    _statement_category_set,
    _to_provision_spans,
    _write_doc_domain,
    _load_doc_metadata_manifest,
    _write_doc_metadata_manifest,
    _write_jsonl_rows,
)
from polisyos.lex.batch.pipeline_types import (
    LLMGateStats,
    PipelineStats,
    StratifiedAuditSampler,
    StructureQualityStats,
    SPOLLMSettings,
)
from polisyos.lex.batch.progress import ProgressTracker
from polisyos.lex.batch.provisions_io import read_provisions

if TYPE_CHECKING:
    from polisyos.lex.batch.llm_gate import GateRuntime
    from polisyos.lex.batch.spo_extractor import GonkaClient
    from polisyos.lex.batch.structurer import ProvisionSpan
    from polisyos.lex.batch.xml_parser import NPADocument

logger = get_logger(__name__)

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
    from polisyos.lex.batch.deterministic_spo import extract_deterministic_spo, extract_family_retry_spo
    from polisyos.lex.batch.domain_classifier import classify_domains
    from polisyos.lex.batch.jurisdictions import get_jurisdiction_plugin
    from polisyos.lex.batch.llm_gate import build_gate_features, decide_route
    from polisyos.lex.batch.provisions_io import _shard_prefix
    from polisyos.lex.batch.reference_extractor import extract_references
    from polisyos.lex.batch.rule_classifier import classify_provision
    from polisyos.lex.batch.spo_extractor import extract_spo_for_documents
    from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult

    llm_available = spo_client is not None
    docs_for_llm: dict[str, NPADocument] = {}
    docs_for_gap_fill: dict[str, NPADocument] = {}
    docs_for_audit_llm: dict[str, NPADocument] = {}
    spans_by_doc_llm: dict[str, list[ProvisionSpan]] = {}
    spans_by_doc_gap_fill: dict[str, list[ProvisionSpan]] = {}
    spans_by_doc_audit: dict[str, list[ProvisionSpan]] = {}
    llm_settings_by_doc: dict[str, SPOLLMSettings] = {}
    gap_fill_settings_by_doc: dict[str, SPOLLMSettings] = {}
    audit_settings_by_doc: dict[str, SPOLLMSettings] = {}
    gate_meta_by_anchor: dict[str, dict[str, dict[str, Any]]] = {}
    gate_meta_by_anchor_gap_fill: dict[str, dict[str, dict[str, Any]]] = {}
    gate_meta_by_anchor_audit: dict[str, dict[str, dict[str, Any]]] = {}
    fallback_rows_by_anchor: dict[str, dict[str, dict[str, Any]]] = {}
    fallback_rows_by_anchor_gap_fill: dict[str, dict[str, dict[str, Any]]] = {}
    fallback_rows_by_anchor_audit: dict[str, dict[str, dict[str, Any]]] = {}
    audit_baseline: dict[str, dict[str, dict[str, Any]]] = {}
    gap_fill_family_by_anchor: dict[tuple[str, str], str] = {}
    gap_fill_subtype_by_anchor: dict[tuple[str, str], str] = {}
    audit_sampler = StratifiedAuditSampler(base_rate=config.llm_gate_audit_sample_rate)
    docs_to_mark_done: set[str] = set()
    timeout_retry_telemetry = {
        "timeout_retry_groups_total": 0,
        "timeout_retry_success_total": 0,
        "timeout_retry_failure_total": 0,
        "retry_followup_passes_run": 0,
        "retry_followup_pending_items_total": 0,
        "retry_followup_recovered_items_total": 0,
        "retry_followup_items_exhausted_total": 0,
    }
    jurisdiction_plugin = get_jurisdiction_plugin(config.jurisdiction)

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

        doc_type_category = infer_doc_type_category(
            doc_type=doc.card.doc_type,
            doc_name=doc.card.name,
        )
        quality_family = classify_doc_family(
            doc_type=doc.card.doc_type,
            doc_name=doc.card.name,
            doc_type_category_value=doc_type_category,
            provision_rows=prov_rows,
        )

        reasoning_spans = [span for span in spans if _should_extract_spo_from_span(span)]
        routing_plan = _build_spo_doc_routing_plan(
            doc=doc,
            prov_rows=prov_rows,
            reasoning_spans=reasoning_spans,
            quality_family=quality_family,
            config=config,
        )
        reasoning_spans = routing_plan.reasoning_spans
        doc_llm_available = llm_available and routing_plan.llm_allowed
        llm_settings_by_doc[doc_id] = routing_plan.llm_settings
        audit_settings_by_doc[doc_id] = routing_plan.llm_settings

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
                    jurisdiction_plugin=jurisdiction_plugin,
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

        if len(reasoning_spans) < len(spans):
            logger.debug(
                "SPO reasoning filter skipped {} search-only provisions for {}",
                len(spans) - len(reasoning_spans),
                doc_id,
            )
        if routing_plan.flags:
            logger.info(
                "SPO routing for {}: flags={} total={} reasoning={} selected={} llm_allowed={} batch={}/{}/{} timeout={}",
                doc_id,
                ",".join(routing_plan.flags),
                len(spans),
                len([span for span in spans if _should_extract_spo_from_span(span)]),
                len(reasoning_spans),
                doc_llm_available,
                routing_plan.llm_settings.task_batch_size,
                routing_plan.llm_settings.request_batch_size,
                routing_plan.llm_settings.request_batch_chars,
                routing_plan.llm_settings.group_timeout_seconds,
            )

        if not reasoning_spans:
            docs_to_mark_done.add(doc_id)
            continue

        # --- Template-based full-document extraction (before per-provision loop) ---
        from polisyos.lex.batch.template_extractor import try_template_extraction

        template_match = try_template_extraction(
            doc_id=doc_id,
            doc_type=doc.card.doc_type,
            publisher=doc.card.publisher,
            doc_title=doc.card.name,
            provisions=[
                {"text": s.text, "anchor_path": s.anchor_path, "citation_label": s.citation_label}
                for s in reasoning_spans
            ],
        )
        if template_match.matched and template_match.results:
            template_rows: list[dict] = []
            span_by_anchor = {span.anchor_path: span for span in reasoning_spans}
            for tmpl_result in template_match.results:
                row = tmpl_result.model_dump(mode="json")
                span = span_by_anchor.get(str(row.get("provision_anchor") or ""))
                if span is not None:
                    row.update(_span_signal_payload(span))
                template_rows.append(row)
                total_spo += len(tmpl_result.statements)
                gate_stats.auto_by_code_total += len(tmpl_result.statements)
                gate_stats.provisions_seen += 1
            _write_jsonl_rows(str(spo_path), template_rows, append=True)
            docs_to_mark_done.add(doc_id)
            continue

        local_rows: list[dict] = []
        docs_to_mark_done.add(doc_id)
        for span in reasoning_spans:
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
                    jurisdiction_plugin=jurisdiction_plugin,
                )
                if config.extract_references_enabled
                else []
            )

            if config.spo_skip_trivial:
                cls = classify_provision(span.text, span.citation_label, doc.card.name)
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
                            logger.debug("Failed to validate SPOCandidate from rule classifier for doc {}", doc_id)
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
                            **_span_signal_payload(span),
                        )
                        local_rows.append(result.model_dump(mode="json"))
                        total_spo += len(candidates)
                        gate_stats.auto_by_code_total += len(candidates)
                    continue

            deterministic = extract_deterministic_spo(
                text=span.text,
                citation_label=span.citation_label,
                doc_title=doc.card.name,
                legal_unit_subtype=span.legal_unit_subtype,
                legal_unit_micro_subtype=span.legal_unit_micro_subtype,
                quality_family=quality_family,
                reference_bearing=span.reference_bearing,
                threshold_bearing=span.threshold_bearing,
                context_prefix=span.context_prefix,
            )
            if not deterministic.candidates and quality_family in {"law", "appendix_heavy", "treaty_protocol"}:
                retry_deterministic = extract_family_retry_spo(
                    text=span.text,
                    citation_label=span.citation_label,
                    doc_title=doc.card.name,
                    quality_family=quality_family,
                    struct_kind=span.struct_kind or span.kind,
                    legal_unit_subtype=span.legal_unit_subtype,
                    legal_unit_micro_subtype=span.legal_unit_micro_subtype,
                    context_prefix=span.context_prefix,
                )
                if retry_deterministic.candidates:
                    deterministic = retry_deterministic

            gate_stats.llm_candidate_total += 1
            llm_share = gate_stats.llm_primary_sent_total / max(1, gate_stats.llm_candidate_total)
            gap_fill_share = gate_stats.llm_gap_fill_sent_total / max(1, gate_stats.llm_candidate_total)
            features = build_gate_features(
                text=span.text,
                deterministic_confidence=deterministic.confidence,
                reference_count=len(reference_hits),
                fallback_chunk=span.is_fallback_chunk,
                publisher=" ".join(doc.card.publisher) if doc.card.publisher else "",
                doc_title=doc.card.name,
                citation_label=span.citation_label,
                struct_kind=span.struct_kind or span.kind,
                section_role=span.section_role,
                doc_type_category=doc_type_category,
                legal_unit_subtype=span.legal_unit_subtype,
                route_class=span.route_class,
                empty_spo_retry_eligible=span.empty_spo_retry_eligible,
                audit_miss_prone=span.audit_miss_prone,
                reference_bearing=span.reference_bearing,
                threshold_bearing=span.threshold_bearing,
                jurisdiction_plugin=jurisdiction_plugin,
            )
            gap_fill_eligible, gap_fill_priority, gap_fill_reason_codes = _should_route_llm_gap_fill(
                config=config,
                span=span,
                quality_family=quality_family,
                deterministic_candidates=deterministic.candidates,
            )
            decision = decide_route(
                gate_enabled=config.llm_gate_enabled,
                runtime=gate_runtime,
                llm_available=doc_llm_available,
                llm_share=llm_share,
                gap_fill_enabled=config.llm_gap_fill_enabled,
                gap_fill_eligible=gap_fill_eligible,
                gap_fill_share=gap_fill_share,
                gap_fill_max_share=config.llm_gap_fill_max_share,
                gap_fill_priority=gap_fill_priority,
                deterministic_confidence=deterministic.confidence,
                auto_conf_threshold=config.llm_gate_auto_conf_threshold,
                min_score_force_llm=config.llm_gate_min_score_force_llm,
                features=features,
                audit_sample_rate=config.llm_gate_audit_sample_rate,
                audit_seed=f"{doc_id}:{span.anchor_path}",
            )
            reason_codes = sorted(set(decision.reason_codes + deterministic.reason_codes + gap_fill_reason_codes))
            audit_eligible = not _should_skip_audit_for_span(span)
            forced_audit_sample = False
            if (
                audit_eligible
                and
                decision.route not in {"llm", "llm_gap_fill", "audit_llm"}
                and audit_sampler.should_force_sample(
                    family=quality_family,
                    subtype=span.legal_unit_subtype,
                    route_class=span.route_class,
                    llm_available=doc_llm_available,
                )
            ):
                decision = type(decision)(
                    route="audit_llm",
                    score=decision.score,
                    reason_codes=sorted(set(reason_codes + ["stratified_audit_quota"])),
                )
                reason_codes = list(decision.reason_codes)
                forced_audit_sample = True
            if not audit_eligible and decision.route == "audit_llm":
                fallback_route = "auto" if deterministic.candidates else "deferred"
                decision = type(decision)(
                    route=fallback_route,
                    score=decision.score,
                    reason_codes=sorted(set(reason_codes + ["audit_skip_low_signal_label"])),
                )
                reason_codes = list(decision.reason_codes)

            if decision.route == "auto":
                if deterministic.candidates:
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
                        **_span_signal_payload(span),
                    )
                    local_rows.append(result.model_dump(mode="json"))
                    total_spo += len(deterministic.candidates)
                    gate_stats.auto_by_code_total += len(deterministic.candidates)
                else:
                    gate_stats.auto_empty_skipped_total += 1
                continue

            if decision.route == "llm" and doc_llm_available:
                docs_for_llm[doc_id] = doc
                spans_by_doc_llm.setdefault(doc_id, []).append(span)
                gate_meta_by_anchor.setdefault(doc_id, {})[span.anchor_path] = {
                    "gate_score": float(decision.score),
                    "gate_reason_codes": list(reason_codes),
                    **_span_signal_payload(span),
                }
                fallback_rows_by_anchor.setdefault(doc_id, {})[span.anchor_path] = _build_llm_fallback_row(
                    doc_id=doc_id,
                    span=span,
                    deterministic_candidates=deterministic.candidates,
                    gate_score=decision.score,
                    gate_reason_codes=reason_codes,
                    source_tag="llm_timeout_fallback",
                )
                gate_stats.llm_sent_total += 1
                gate_stats.llm_primary_sent_total += 1
                continue

            if decision.route == "llm_gap_fill" and doc_llm_available:
                docs_for_gap_fill[doc_id] = doc
                spans_by_doc_gap_fill.setdefault(doc_id, []).append(span)
                gap_fill_settings_by_doc[doc_id] = routing_plan.llm_settings
                for reason_code in gap_fill_reason_codes:
                    gate_stats.llm_gap_fill_trigger_counts[reason_code] = int(
                        gate_stats.llm_gap_fill_trigger_counts.get(reason_code, 0) or 0
                    ) + 1
                gate_meta_by_anchor_gap_fill.setdefault(doc_id, {})[span.anchor_path] = {
                    "gate_score": float(decision.score),
                    "gate_reason_codes": list(reason_codes),
                    **_span_signal_payload(span),
                }
                fallback_rows_by_anchor_gap_fill.setdefault(doc_id, {})[span.anchor_path] = _build_llm_fallback_row(
                    doc_id=doc_id,
                    span=span,
                    deterministic_candidates=deterministic.candidates,
                    gate_score=decision.score,
                    gate_reason_codes=reason_codes,
                    source_tag="llm_gap_fill_timeout_fallback",
                )
                gap_fill_family_by_anchor[(doc_id, span.anchor_path)] = quality_family
                gap_fill_subtype_by_anchor[(doc_id, span.anchor_path)] = span.legal_unit_subtype or ""
                gate_stats.llm_sent_total += 1
                gate_stats.llm_gap_fill_sent_total += 1
                continue

            if decision.route == "audit_llm" and doc_llm_available:
                audit_sampler.register_sample(
                    family=quality_family,
                    subtype=span.legal_unit_subtype,
                    route_class=span.route_class,
                    forced=forced_audit_sample,
                )
                docs_for_audit_llm[doc_id] = doc
                spans_by_doc_audit.setdefault(doc_id, []).append(span)
                gate_meta_by_anchor_audit.setdefault(doc_id, {})[span.anchor_path] = {
                    "gate_score": float(decision.score),
                    "gate_reason_codes": list(reason_codes),
                    **_span_signal_payload(span),
                }
                fallback_rows_by_anchor_audit.setdefault(doc_id, {})[span.anchor_path] = _build_llm_fallback_row(
                    doc_id=doc_id,
                    span=span,
                    deterministic_candidates=deterministic.candidates,
                    gate_score=decision.score,
                    gate_reason_codes=reason_codes,
                    source_tag="audit_llm_timeout_fallback",
                )
                audit_baseline.setdefault(doc_id, {})[span.anchor_path] = {
                    "baseline_count": len(deterministic.candidates),
                    "baseline_categories": _statement_category_set(deterministic.candidates),
                    "doc_type_category": doc_type_category,
                    "quality_family": quality_family,
                    "gate_reason_codes": reason_codes,
                    "search_only_structure": not span.fallback_allowed_for_reasoning,
                    "empty_spo_only": len(deterministic.candidates) == 0,
                    "section_role": span.section_role,
                    "struct_kind": span.struct_kind or span.kind,
                    **_span_signal_payload(span),
                }
                gate_stats.audit_sample_total += 1
                gate_stats.llm_sent_total += 1
                continue

            # deferred: keep deterministic rows but mark provenance and low confidence.
            if deterministic.candidates:
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
                    **_span_signal_payload(span),
                )
                local_rows.append(result.model_dump(mode="json"))
                total_spo += len(deterministic.candidates)
            gate_stats.deferred_total += 1
            deferred_reason = next((reason for reason in reason_codes if reason), "deferred_no_llm")
            _bump_counter(gate_stats.deferred_reason_counts, deferred_reason)

        if local_rows:
            _write_jsonl_rows(str(spo_path), local_rows, append=True)

    failed_doc_ids_total: set[str] = set()
    if llm_available and docs_for_llm:
        for llm_settings, llm_docs in _group_docs_by_spo_settings(docs_for_llm, llm_settings_by_doc):
            for docs_batch in _chunked(llm_docs, config.spo_batch_docs):
                batch_spo, failed_ids = await _call_extract_spo_for_documents(
                    extract_spo_for_documents,
                    spo_client,
                    docs_batch,
                    spans_by_doc_llm,
                    results_dir=config.spo_results_dir,
                    task_batch_size=llm_settings.task_batch_size,
                    request_batch_size=llm_settings.request_batch_size,
                    request_batch_chars=llm_settings.request_batch_chars,
                    adaptive_batch_downshift_enabled=config.spo_adaptive_batch_downshift_enabled,
                    adaptive_batch_soft_chars_share=config.spo_adaptive_batch_soft_chars_share,
                    group_timeout_seconds=llm_settings.group_timeout_seconds,
                    verify_mode=config.spo_verify_mode,
                    extract_mode=config.spo_extract_mode,
                    overwrite_existing=False,
                    extraction_source="llm",
                    gate_meta_by_anchor=gate_meta_by_anchor,
                    fallback_rows_by_anchor=fallback_rows_by_anchor,
                    timeout_retry_enabled=config.spo_timeout_retry_enabled,
                    timeout_retry_batch_size=config.spo_timeout_retry_batch_size,
                    timeout_retry_chars=config.spo_timeout_retry_chars,
                    retryable_followup_passes=config.spo_retryable_followup_passes,
                    retryable_followup_delay_seconds=config.spo_retryable_followup_delay_seconds,
                    retryable_followup_worker_scale=config.spo_retryable_followup_worker_scale,
                    retryable_followup_dispatch_rps_scale=config.spo_retryable_followup_dispatch_rps_scale,
                    retryable_followup_client_rate_scale=config.spo_retryable_followup_client_rate_scale,
                    retryable_followup_client_concurrency_scale=config.spo_retryable_followup_client_concurrency_scale,
                    telemetry=timeout_retry_telemetry,
                )
                total_spo += batch_spo
                failed_doc_ids_total.update(failed_ids)

    if llm_available and docs_for_gap_fill:
        def _gap_fill_sink(row: dict[str, object]) -> None:
            doc_id = str(row.get("doc_id") or "")
            anchor = str(row.get("provision_anchor") or "")
            family = gap_fill_family_by_anchor.get((doc_id, anchor), "other")
            subtype = gap_fill_subtype_by_anchor.get((doc_id, anchor), str(row.get("legal_unit_subtype") or ""))
            gate_stats.llm_gap_fill_family_counts[family] = int(
                gate_stats.llm_gap_fill_family_counts.get(family, 0) or 0
            ) + 1
            if subtype:
                gate_stats.llm_gap_fill_subtype_counts[subtype] = int(
                    gate_stats.llm_gap_fill_subtype_counts.get(subtype, 0) or 0
                ) + 1
            gate_stats.llm_gap_fill_added_statements_total += int(
                row.get("llm_gap_fill_added_statement_count", 0) or 0
            )
            extraction_source = str(row.get("extraction_source") or "")
            if extraction_source.endswith("timeout_fallback"):
                gate_stats.llm_gap_fill_timeout_fallback_total += 1
                gate_stats.llm_gap_fill_timeout_family_counts[family] = int(
                    gate_stats.llm_gap_fill_timeout_family_counts.get(family, 0) or 0
                ) + 1
            elif extraction_source == "llm_gap_fill" and int(row.get("llm_gap_fill_llm_statement_count", 0) or 0) == 0:
                gate_stats.llm_gap_fill_empty_responses_total += 1
                gate_stats.llm_gap_fill_null_yield_total += 1
                statements = row.get("statements")
                statement_count = len(statements) if isinstance(statements, list) else 0
                baseline_count = int(row.get("baseline_statement_count", 0) or 0)
                if statement_count == 0:
                    gate_stats.llm_gap_fill_null_yield_persisted_empty_total += 1
                elif baseline_count > 0:
                    gate_stats.llm_gap_fill_null_yield_preserved_baseline_total += 1

        for gap_fill_settings, gap_fill_docs in _group_docs_by_spo_settings(docs_for_gap_fill, gap_fill_settings_by_doc):
            for docs_batch in _chunked(gap_fill_docs, config.spo_batch_docs):
                batch_spo, failed_ids = await _call_extract_spo_for_documents(
                    extract_spo_for_documents,
                    spo_client,
                    docs_batch,
                    spans_by_doc_gap_fill,
                    results_dir=config.spo_results_dir,
                    task_batch_size=gap_fill_settings.task_batch_size,
                    request_batch_size=gap_fill_settings.request_batch_size,
                    request_batch_chars=gap_fill_settings.request_batch_chars,
                    adaptive_batch_downshift_enabled=config.spo_adaptive_batch_downshift_enabled,
                    adaptive_batch_soft_chars_share=config.spo_adaptive_batch_soft_chars_share,
                    group_timeout_seconds=gap_fill_settings.group_timeout_seconds,
                    verify_mode=config.spo_verify_mode,
                    extract_mode=config.spo_extract_mode,
                    overwrite_existing=False,
                    extraction_source="llm_gap_fill",
                    gate_meta_by_anchor=gate_meta_by_anchor_gap_fill,
                    fallback_rows_by_anchor=fallback_rows_by_anchor_gap_fill,
                    merge_baseline_rows_by_anchor=fallback_rows_by_anchor_gap_fill,
                    result_sink=_gap_fill_sink,
                    timeout_retry_enabled=config.spo_timeout_retry_enabled,
                    timeout_retry_batch_size=config.spo_timeout_retry_batch_size,
                    timeout_retry_chars=config.spo_timeout_retry_chars,
                    retryable_followup_passes=config.spo_retryable_followup_passes,
                    retryable_followup_delay_seconds=config.spo_retryable_followup_delay_seconds,
                    retryable_followup_worker_scale=config.spo_retryable_followup_worker_scale,
                    retryable_followup_dispatch_rps_scale=config.spo_retryable_followup_dispatch_rps_scale,
                    retryable_followup_client_rate_scale=config.spo_retryable_followup_client_rate_scale,
                    retryable_followup_client_concurrency_scale=config.spo_retryable_followup_client_concurrency_scale,
                    telemetry=timeout_retry_telemetry,
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
            baseline_meta = audit_baseline.get(doc_id, {}).get(anchor, {})
            baseline_count = int(baseline_meta.get("baseline_count", 0) or 0)
            miss = llm_count > baseline_count
            llm_categories = _statement_category_set(statements if isinstance(statements, list) else [])
            baseline_categories = {
                str(item)
                for item in baseline_meta.get("baseline_categories", [])
                if str(item).strip()
            }
            miss_categories = sorted(set(llm_categories) - baseline_categories)
            if miss and not miss_categories:
                miss_categories = ["additional_statement"]
            primary_categories = {
                "obligation",
                "permission",
                "prohibition",
                "threshold",
                "reference_amendment",
                "sanction",
                "sanction_clause",
            }
            secondary_categories = {
                "additional_statement",
                "temporal",
                "temporal_clause",
                "condition",
                "completion",
            }
            primary_clause_miss_categories = sorted(
                category for category in miss_categories if category in primary_categories
            )
            secondary_clause_miss_categories = sorted(
                category
                for category in miss_categories
                if category in secondary_categories or category not in primary_categories
            )
            chunk_audit_total += 1
            if miss:
                chunk_audit_miss += 1
                for category in miss_categories:
                    _bump_counter(gate_stats.audit_miss_category_counts, category)
            audit_rows.append(
                {
                    "doc_id": doc_id,
                    "provision_anchor": anchor,
                    "baseline_count": baseline_count,
                    "llm_count": llm_count,
                    "miss": miss,
                    "miss_categories": miss_categories,
                    "baseline_categories": sorted(baseline_categories),
                    "llm_categories": llm_categories,
                    "primary_clause_miss": bool(primary_clause_miss_categories),
                    "secondary_clause_miss": bool(secondary_clause_miss_categories),
                    "primary_clause_miss_categories": primary_clause_miss_categories,
                    "secondary_clause_miss_categories": secondary_clause_miss_categories,
                    "empty_spo_only": bool(baseline_meta.get("empty_spo_only", False)),
                    "llm_timeout_fallback": str(row.get("extraction_source") or "").endswith("timeout_fallback"),
                    "doc_type_category": str(baseline_meta.get("doc_type_category") or ""),
                    "quality_family": str(baseline_meta.get("quality_family") or "other"),
                    "gate_reason_codes": list(baseline_meta.get("gate_reason_codes") or []),
                    "search_only_structure": bool(baseline_meta.get("search_only_structure", False)),
                    "struct_kind": str(baseline_meta.get("struct_kind") or ""),
                    "section_role": str(baseline_meta.get("section_role") or ""),
                    "legal_unit_subtype": str(baseline_meta.get("legal_unit_subtype") or ""),
                    "legal_unit_micro_subtype": str(baseline_meta.get("legal_unit_micro_subtype") or ""),
                    "route_class": str(baseline_meta.get("route_class") or ""),
                    "empty_spo_retry_eligible": bool(baseline_meta.get("empty_spo_retry_eligible", False)),
                    "audit_miss_prone": bool(baseline_meta.get("audit_miss_prone", False)),
                    "reference_bearing": bool(baseline_meta.get("reference_bearing", False)),
                    "threshold_bearing": bool(baseline_meta.get("threshold_bearing", False)),
                }
            )

        for audit_settings, audit_docs in _group_docs_by_spo_settings(docs_for_audit_llm, audit_settings_by_doc):
            for docs_batch in _chunked(audit_docs, config.spo_batch_docs):
                batch_spo, failed_ids = await _call_extract_spo_for_documents(
                    extract_spo_for_documents,
                    spo_client,
                    docs_batch,
                    spans_by_doc_audit,
                    results_dir=config.spo_results_dir,
                    task_batch_size=audit_settings.task_batch_size,
                    request_batch_size=audit_settings.request_batch_size,
                    request_batch_chars=audit_settings.request_batch_chars,
                    adaptive_batch_downshift_enabled=config.spo_adaptive_batch_downshift_enabled,
                    adaptive_batch_soft_chars_share=config.spo_adaptive_batch_soft_chars_share,
                    group_timeout_seconds=audit_settings.group_timeout_seconds,
                    verify_mode=config.spo_verify_mode,
                    extract_mode=config.spo_extract_mode,
                    overwrite_existing=False,
                    extraction_source="audit_llm",
                    gate_meta_by_anchor=gate_meta_by_anchor_audit,
                    fallback_rows_by_anchor=fallback_rows_by_anchor_audit,
                    result_sink=_audit_sink,
                    timeout_retry_enabled=config.spo_timeout_retry_enabled,
                    timeout_retry_batch_size=config.spo_timeout_retry_batch_size,
                    timeout_retry_chars=config.spo_timeout_retry_chars,
                    retryable_followup_passes=config.spo_retryable_followup_passes,
                    retryable_followup_delay_seconds=config.spo_retryable_followup_delay_seconds,
                    retryable_followup_worker_scale=config.spo_retryable_followup_worker_scale,
                    retryable_followup_dispatch_rps_scale=config.spo_retryable_followup_dispatch_rps_scale,
                    retryable_followup_client_rate_scale=config.spo_retryable_followup_client_rate_scale,
                    retryable_followup_client_concurrency_scale=config.spo_retryable_followup_client_concurrency_scale,
                    telemetry=timeout_retry_telemetry,
                )
                total_spo += batch_spo
                failed_doc_ids_total.update(failed_ids)

        if audit_rows:
            _write_jsonl_rows(str(config.llm_gate_audit_path), audit_rows, append=True)
            if config.pattern_feedback_enabled:
                from polisyos.lex.batch.feedback import build_feedback_queue_rows, write_candidate_patterns

                feedback_rows = build_feedback_queue_rows(audit_rows)
                if feedback_rows:
                    _write_jsonl_rows(str(config.pattern_feedback_queue_path), feedback_rows, append=True)
                    write_candidate_patterns(
                        feedback_rows=feedback_rows,
                        output_dir=config.pattern_candidates_dir,
                    )
        gate_stats.audit_miss_total += chunk_audit_miss
        if chunk_audit_total > 0:
            miss_rate = (chunk_audit_miss * 100.0) / chunk_audit_total
            if gate_runtime.register_audit_miss_rate(miss_rate):
                logger.warning(
                    "LLM gate circuit breaker triggered (audit miss rate %.2f%%). Safe-pass enabled.",
                    miss_rate,
                )
            gate_stats.circuit_breaker_hits = gate_runtime.circuit_breaker_hits
    gate_stats.timeout_retry_groups_total += int(timeout_retry_telemetry["timeout_retry_groups_total"])
    gate_stats.timeout_retry_success_total += int(timeout_retry_telemetry["timeout_retry_success_total"])
    gate_stats.timeout_retry_failure_total += int(timeout_retry_telemetry["timeout_retry_failure_total"])
    gate_stats.retry_followup_passes_run += int(timeout_retry_telemetry["retry_followup_passes_run"])
    gate_stats.retry_followup_pending_items_total += int(timeout_retry_telemetry["retry_followup_pending_items_total"])
    gate_stats.retry_followup_recovered_items_total += int(timeout_retry_telemetry["retry_followup_recovered_items_total"])
    gate_stats.retry_followup_items_exhausted_total += int(timeout_retry_telemetry["retry_followup_items_exhausted_total"])

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
            logger.info(
                "Provision dedup: {} provisions reused from {} unique texts",
                gate_stats.dedup_reused_total,
                len(dedup_map),
            )

    for doc_id in docs_to_mark_done:
        if doc_id not in failed_doc_ids_total:
            doc_hash = _doc_content_hash(next(
                (d.text for d in docs_chunk if d.card.doc_id == doc_id), "",
            ))
            progress.mark_done(doc_id, "spo_extracted", content_hash=doc_hash)

    logger.info(
        "LLM gate chunk: seen={} auto={} auto_empty_skip={} llm_sent={} gap_fill_sent={} gap_fill_added={} deferred={} skipped={} dedup={} audit_miss_rate={:.2f}%",
        gate_stats.provisions_seen,
        gate_stats.auto_by_code_total,
        gate_stats.auto_empty_skipped_total,
        gate_stats.llm_sent_total,
        gate_stats.llm_gap_fill_sent_total,
        gate_stats.llm_gap_fill_added_statements_total,
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
    needs_extraction_stream = bool({"parse", "structure", "spo"} & set(config.stages))
    needs_doc_metadata = bool({"resolve_refs", "graph"} & set(config.stages))
    if needs_extraction_stream:
        parse_start = time.monotonic()
        structure_elapsed = 0.0
        spo_elapsed = 0.0
        structure_quality_stats = StructureQualityStats()

        logger.info("=== Streaming documents ===")
        if config.sharded:
            logger.info(
                "Sharding enabled: {} ({}/{})",
                config.shard_slug,
                config.shard_index + 1,
                config.shard_count,
            )
        run_structure = "structure" in config.stages
        run_spo = "spo" in config.stages
        llm_keys = [str(key).strip() for key in config.gonka_api_keys if str(key).strip()]
        llm_available = bool(llm_keys or config.gonka_api_key)
        if run_spo and not llm_available:
            logger.warning("GONKA_API_KEY not set — running deterministic SPO only (no LLM calls).")

        spo_client = None
        if run_spo and llm_available:
            from polisyos.lex.batch.spo_extractor import GonkaClient, GonkaClientPool

            if len(llm_keys) > 1:
                spo_client = GonkaClientPool(
                    api_keys=llm_keys,
                    base_url=config.gonka_base_url,
                    model=config.llm_model,
                    disable_json_mode=config.gonka_disable_json_mode,
                    max_concurrent=config.max_concurrent_llm,
                    rate_limit_rps=config.rate_limit_rps,
                    temperature=config.llm_temperature,
                    max_retries=config.max_retries,
                    connect_timeout_seconds=config.spo_connect_timeout_seconds,
                    read_timeout_seconds=config.spo_read_timeout_seconds,
                    total_timeout_seconds=config.spo_total_timeout_seconds,
                    provider_watchdog_seconds=(
                        None
                        if config.spo_provider_watchdog_seconds < 0
                        else (
                            float(max(300, config.spo_total_timeout_seconds + 15))
                            if config.spo_provider_watchdog_seconds == 0
                            else float(config.spo_provider_watchdog_seconds)
                        )
                    ),
                    global_concurrent_cap=config.max_concurrent_llm_global,
                    rate_warmup_seconds=config.spo_rate_warmup_seconds,
                    rate_warmup_start_scale=config.spo_rate_warmup_start_scale,
                    adaptive_rate_enabled=config.spo_adaptive_rate_enabled,
                    adaptive_rate_recovery_factor=config.spo_adaptive_rate_recovery_factor,
                    adaptive_rate_penalty_multiplier=config.spo_adaptive_rate_penalty_multiplier,
                    adaptive_rate_max_scale=config.spo_adaptive_rate_max_scale,
                )
                logger.info(
                    "Using Gonka key pool: {} keys, per_key_concurrency={}, global_concurrency_cap={}, approx total rps={:.2f}",
                    len(llm_keys),
                    config.max_concurrent_llm,
                    getattr(spo_client, "dispatch_worker_hint", len(llm_keys) * config.max_concurrent_llm),
                    len(llm_keys) * config.rate_limit_rps,
                )
            else:
                spo_client = GonkaClient(
                    api_key=config.gonka_api_key,
                    base_url=config.gonka_base_url,
                    model=config.llm_model,
                    disable_json_mode=config.gonka_disable_json_mode,
                    max_concurrent=config.max_concurrent_llm,
                    rate_limit_rps=config.rate_limit_rps,
                    temperature=config.llm_temperature,
                    max_retries=config.max_retries,
                    connect_timeout_seconds=config.spo_connect_timeout_seconds,
                    read_timeout_seconds=config.spo_read_timeout_seconds,
                    total_timeout_seconds=config.spo_total_timeout_seconds,
                    provider_watchdog_seconds=(
                        None
                        if config.spo_provider_watchdog_seconds < 0
                        else (
                            float(max(300, config.spo_total_timeout_seconds + 15))
                            if config.spo_provider_watchdog_seconds == 0
                            else float(config.spo_provider_watchdog_seconds)
                        )
                    ),
                    rate_warmup_seconds=config.spo_rate_warmup_seconds,
                    rate_warmup_start_scale=config.spo_rate_warmup_start_scale,
                    adaptive_rate_enabled=config.spo_adaptive_rate_enabled,
                    adaptive_rate_recovery_factor=config.spo_adaptive_rate_recovery_factor,
                    adaptive_rate_penalty_multiplier=config.spo_adaptive_rate_penalty_multiplier,
                    adaptive_rate_max_scale=config.spo_adaptive_rate_max_scale,
                )
            if config.spo_cache_enabled:
                from polisyos.lex.batch.spo_cache import SPOCache

                cache_path = config.spo_cache_path or (config.output_dir / "spo_cache.sqlite")
                spo_response_cache = SPOCache(cache_path)
                spo_client.set_cache(spo_response_cache)
                logger.info("SPO response cache enabled: {}", cache_path)
            else:
                spo_response_cache = None

            if config.spo_request_log_enabled and hasattr(spo_client, "set_request_log_path"):
                if not config.resume and config.llm_request_log_path.exists():
                    config.llm_request_log_path.unlink()
                spo_client.set_request_log_path(config.llm_request_log_path)
                logger.info("SPO request logging enabled: {}", config.llm_request_log_path)

            logger.info(
                "SPO extract_mode={}, verify_mode={}, skip_trivial={}, gate_mode={}",
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
                doc_id_filter=set(config.doc_id_filter) if config.doc_id_filter else None,
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
                    structure_cache, added, chunk_structure_stats = await _process_structure_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                    )
                    stats.total_provisions += added
                    structure_quality_stats.provision_docs_total += chunk_structure_stats.provision_docs_total
                    structure_quality_stats.full_only_docs += chunk_structure_stats.full_only_docs
                    structure_quality_stats.duplicate_anchor_docs += chunk_structure_stats.duplicate_anchor_docs
                    structure_elapsed += time.monotonic() - st
                    _check_structure_quality_gate(
                        config=config,
                        stats=structure_quality_stats,
                    )
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
                        "Reached --max-docs limit ({} new documents). Stopping.",
                        config.max_docs,
                    )
                    break

            if chunk:
                if run_structure:
                    st = time.monotonic()
                    structure_cache, added, chunk_structure_stats = await _process_structure_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                    )
                    stats.total_provisions += added
                    structure_quality_stats.provision_docs_total += chunk_structure_stats.provision_docs_total
                    structure_quality_stats.full_only_docs += chunk_structure_stats.full_only_docs
                    structure_quality_stats.duplicate_anchor_docs += chunk_structure_stats.duplicate_anchor_docs
                    structure_elapsed += time.monotonic() - st
                    _check_structure_quality_gate(
                        config=config,
                        stats=structure_quality_stats,
                    )
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
                "auto_empty_skipped_total": gate_stats.auto_empty_skipped_total,
                "llm_candidate_total": gate_stats.llm_candidate_total,
                "llm_sent_total": gate_stats.llm_sent_total,
                "llm_primary_sent_total": gate_stats.llm_primary_sent_total,
                "llm_gap_fill_sent_total": gate_stats.llm_gap_fill_sent_total,
                "llm_gap_fill_added_statements_total": gate_stats.llm_gap_fill_added_statements_total,
                "baseline_vs_gap_fill_added_statements_total": gate_stats.llm_gap_fill_added_statements_total,
                "llm_gap_fill_timeout_fallback_total": gate_stats.llm_gap_fill_timeout_fallback_total,
                "llm_gap_fill_empty_responses_total": gate_stats.llm_gap_fill_empty_responses_total,
                "gap_fill_null_yield_total": gate_stats.llm_gap_fill_null_yield_total,
                "gap_fill_null_yield_persisted_empty_total": gate_stats.llm_gap_fill_null_yield_persisted_empty_total,
                "gap_fill_null_yield_preserved_baseline_total": gate_stats.llm_gap_fill_null_yield_preserved_baseline_total,
                "llm_gap_fill_gain_rate_pct": round(gate_stats.gap_fill_gain_rate_pct, 3),
                "gap_fill_null_yield_pct": round(gate_stats.gap_fill_null_yield_pct, 3),
                "deferred_total": gate_stats.deferred_total,
                "deferred_reason_counts": gate_stats.deferred_reason_counts,
                "dedup_reused_total": gate_stats.dedup_reused_total,
                "llm_saved_pct": round(gate_stats.llm_saved_pct, 3),
                "primary_llm_saved_pct": round(gate_stats.primary_llm_saved_pct, 3),
                "audit_sample_total": gate_stats.audit_sample_total,
                "audit_miss_total": gate_stats.audit_miss_total,
                "audit_miss_rate_pct": round(gate_stats.audit_miss_rate_pct, 3),
                "audit_miss_category_counts": gate_stats.audit_miss_category_counts,
                "audit_miss_rate_pct_before_gap_fill_baseline": round(gate_stats.audit_miss_rate_pct, 3),
                "audit_miss_rate_pct_after_gap_fill": round(gate_stats.audit_miss_rate_pct, 3),
                "circuit_breaker_hits": gate_stats.circuit_breaker_hits,
                "safe_pass_active": int(bool(gate_runtime.safe_pass_active)) if gate_runtime else 0,
                "timeout_retry_groups_total": gate_stats.timeout_retry_groups_total,
                "timeout_retry_success_total": gate_stats.timeout_retry_success_total,
                "timeout_retry_failure_total": gate_stats.timeout_retry_failure_total,
                "retry_followup_passes_run": gate_stats.retry_followup_passes_run,
                "retry_followup_pending_items_total": gate_stats.retry_followup_pending_items_total,
                "retry_followup_recovered_items_total": gate_stats.retry_followup_recovered_items_total,
                "retry_followup_items_exhausted_total": gate_stats.retry_followup_items_exhausted_total,
                "top_gap_fill_subtypes": [
                    {"legal_unit_subtype": subtype, "count": count}
                    for subtype, count in sorted(
                        gate_stats.llm_gap_fill_subtype_counts.items(),
                        key=lambda item: (item[1], item[0]),
                        reverse=True,
                    )[:8]
                ],
                "top_gap_fill_families": [
                    {"family": family, "count": count}
                    for family, count in sorted(
                        gate_stats.llm_gap_fill_family_counts.items(),
                        key=lambda item: (item[1], item[0]),
                        reverse=True,
                    )[:5]
                ],
                "top_timeout_gap_fill_families": [
                    {"family": family, "count": count}
                    for family, count in sorted(
                        gate_stats.llm_gap_fill_timeout_family_counts.items(),
                        key=lambda item: (item[1], item[0]),
                        reverse=True,
                    )[:5]
                ],
                "gap_fill_trigger_counts": dict(
                    sorted(
                        gate_stats.llm_gap_fill_trigger_counts.items(),
                        key=lambda item: (item[1], item[0]),
                        reverse=True,
                    )
                ),
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
                        "llm_gap_fill_mode": config.llm_gap_fill_mode,
                        "llm_gap_fill_enabled": config.llm_gap_fill_enabled,
                        "llm_gap_fill_max_share": config.llm_gap_fill_max_share,
                        "metrics": stats.llm_gate_metrics,
                },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )

        if doc_metadata:
            _write_doc_metadata_manifest(output_dir=config.output_dir, doc_metadata=doc_metadata)

        if stats.total_docs == 0:
            logger.warning("No documents found. Pipeline complete.")
            stats.elapsed_seconds = time.monotonic() - t0
            return stats

    # Fast-path: load doc_metadata from manifest when extraction stages were skipped.
    if needs_doc_metadata and not doc_metadata:
        doc_metadata = _load_doc_metadata_manifest(config.output_dir)
        if doc_metadata:
            logger.info("Loaded {} documents from doc_metadata manifest (skipped XML parse).", len(doc_metadata))
            if config.doc_id_filter:
                filtered = {did: m for did, m in doc_metadata.items() if did in config.doc_id_filter}
                stats.total_docs = len(filtered)
            else:
                stats.total_docs = len(doc_metadata)
        elif not needs_extraction_stream:
            logger.warning(
                "doc_metadata manifest not found at {}. "
                "Reference resolution and graph enrichment will have limited doc metadata.",
                config.output_dir / "manifests" / "doc_metadata.json",
            )

    if "ground_quotes" in config.stages:
        st = time.monotonic()
        logger.info("=== Ground quotes ===")
        from polisyos.lex.batch.postprocess import ground_spo_quotes

        grounded_stats = ground_spo_quotes(
            spo_results_dir=config.spo_results_dir,
            provisions_dir=config.provisions_dir,
            output_dir=config.grounded_spo_dir,
        )
        stats.grounded_statements = grounded_stats["statements_grounded"]
        stats.normative_statements = grounded_stats["statements_normative"]
        stats.stage_times["ground_quotes"] = time.monotonic() - st

    if "resolve_refs" in config.stages:
        st = time.monotonic()
        logger.info("=== Resolve references ===")
        from polisyos.lex.batch.postprocess import resolve_references

        resolved_stats = resolve_references(
            references_dir=config.references_dir,
            output_dir=config.resolved_references_dir,
            doc_metadata=doc_metadata,
        )
        stats.reference_edges = max(stats.reference_edges, resolved_stats["rows_resolved"])
        stats.stage_times["resolve_refs"] = time.monotonic() - st

    if "graph" in config.stages:
        st = time.monotonic()
        logger.info("=== Stage 4: Build graph ===")
        from polisyos.lex.batch.graph_builder import build_graph

        graph_stats = build_graph(
            spo_results_dir=Path(_active_spo_results_dir(config)),
            provisions_dir=config.provisions_dir,
            references_dir=(
                Path(_active_references_dir(config))
                if config.extract_references_enabled
                else None
            ),
            domains_dir=config.domains_dir if config.extract_domains_enabled else None,
            doc_metadata=doc_metadata,
            db_path=config.db_path,
            resolution_cards_path=config.cards_path,
            feedback_queue_path=config.pattern_feedback_queue_path if config.pattern_feedback_enabled else None,
            insert_batch_size=config.graph_insert_batch,
        )
        stats.entities = graph_stats.entities
        stats.facts = graph_stats.facts
        stats.candidate_facts = graph_stats.candidate_facts
        stats.grounded_facts = graph_stats.grounded_facts
        stats.normative_facts = graph_stats.normative_facts
        stats.reference_edges = graph_stats.reference_edges
        # Backfill counters that are otherwise only set during structure/spo stages.
        stats.total_provisions = max(stats.total_provisions, graph_stats.provisions)
        stats.total_spo = max(stats.total_spo, graph_stats.facts)
        stats.llm_gate_metrics["high_confidence_norms_total"] = graph_stats.high_confidence_norms
        stats.llm_gate_metrics["amendments_total"] = graph_stats.amendments
        stats.llm_gate_metrics["amendments_with_target_total"] = graph_stats.amendments_with_target
        stats.llm_gate_metrics["amendment_docs_total"] = graph_stats.amendment_docs_total
        stats.llm_gate_metrics["amendment_docs_with_target_total"] = graph_stats.amendment_docs_with_target
        stats.llm_gate_metrics["reference_resolution_audit_total"] = graph_stats.reference_resolution_audit
        stats.llm_gate_metrics["reference_resolution_resolved_total"] = graph_stats.reference_resolution_resolved
        stats.llm_gate_metrics["reference_resolution_partial_total"] = graph_stats.reference_resolution_partial
        stats.llm_gate_metrics["pattern_feedback_queue_total"] = graph_stats.pattern_feedback_queue
        from polisyos.lex.batch.consistency_checker import detect_consistency_issues

        with duckdb.connect(str(config.db_path)) as con:
            consistency_issues = detect_consistency_issues(con, jurisdiction=config.jurisdiction)
        stats.llm_gate_metrics["consistency_issues_total"] = consistency_issues
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
            spo_results_dir=Path(_active_spo_results_dir(config)),
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
            min_reference_resolution_coverage_pct=config.quality_min_reference_resolution_coverage_pct,
            min_llm_saved_pct=config.quality_min_llm_saved_pct,
            min_audit_samples_for_rate=config.quality_min_audit_samples_for_rate,
            min_provision_docs_for_doc_rate=config.quality_min_provision_docs_for_doc_rate,
            min_spo_rows_for_row_rate=config.quality_min_spo_rows_for_row_rate,
            min_statements_for_statement_rate=config.quality_min_statements_for_statement_rate,
            min_reference_rows_for_rate=config.quality_min_reference_rows_for_rate,
        )
        gate = evaluate_quality_gates(report=report, thresholds=thresholds)
        stats.quality_gate_passed = gate.passed
        stats.quality_passed = gate.passed
        stats.quality_gate_failed_checks = list(gate.failed_checks)
        stats.quality_failed_checks = list(gate.failed_checks)
        stats.quality_hotspot_failed_checks = list(gate.hotspot_failed_checks)
        stats.quality_warning_failed_checks = list(gate.warning_failed_checks)
        stats.quality_skipped_checks = list(gate.skipped_checks)
        stats.quality_report = {
            key: float(value) if isinstance(value, (int, float)) else 0.0
            for key, value in gate.report.items()
            if isinstance(value, (int, float))
        }
        stats.stage_times["quality"] = time.monotonic() - st

        logger.info(
            "Quality report: full_only={:.2f}% empty_rows={:.2f}% oov_action={:.2f}% missing_quote={:.2f}% dup_anchor={:.3f}%",
            float(report.get("full_only_docs_pct", 0.0)),
            float(report.get("empty_statement_rows_pct", 0.0)),
            float(report.get("oov_action_rate_pct", 0.0)),
            float(report.get("missing_quote_rate_pct", 0.0)),
            float(report.get("duplicate_anchor_rate_pct", 0.0)),
        )
        if gate.skipped_checks:
            logger.info("Quality checks skipped due to low sample size: {}", ", ".join(gate.skipped_checks))
        if gate.warning_failed_checks:
            logger.warning("Quality warning checks failed: {}", ", ".join(gate.warning_failed_checks))
        if gate.hotspot_failed_checks:
            logger.warning(
                "Quality hotspot checks failed (triage-only): {}",
                ", ".join(gate.hotspot_failed_checks),
            )
        if (not gate.passed) and (not config.quality_fail_on_critical):
            logger.warning(
                "Quality gates failed (warn-only): {}",
                ", ".join(gate.failed_checks),
            )
        if (not gate.passed) and config.quality_fail_on_critical:
            raise RuntimeError(
                f"Quality gates failed: {', '.join(gate.failed_checks)}. "
                f"Report: {gate.report}"
            )

    if "export_claims" in config.stages:
        st = time.monotonic()
        logger.info("=== Export claims ===")
        from polisyos.lex.batch.postprocess import export_normative_claims

        export_stats = export_normative_claims(
            db_path=config.db_path,
            output_dir=config.claim_exports_dir,
        )
        stats.exported_claims = export_stats["claims_total"]
        if config.export_claims_to_cas:
            from polisyos.lex.batch.claim_bridge import export_normative_claim_sets

            bridge_result = export_normative_claim_sets(
                db_path=config.db_path,
                cas_root=config.cas_root or (config.output_dir / ".polisyos"),
                fact_log_root=config.fact_log_root or (config.output_dir / "fact_log"),
                output_dir=config.claim_exports_dir,
            )
            stats.exported_claim_sets = len(bridge_result.normalized_claim_set_artifact_ids)
        stats.stage_times["export_claims"] = time.monotonic() - st

    if "benchmark" in config.stages:
        st = time.monotonic()
        logger.info("=== Benchmark ===")
        from polisyos.lex.batch.benchmark import run_benchmark

        benchmark_outcome = run_benchmark(config)
        stats.benchmark_passed = benchmark_outcome.passed
        stats.benchmark_metrics = benchmark_outcome.metrics
        stats.benchmark_failed_checks = benchmark_outcome.failed_checks
        stats.stage_times["benchmark"] = time.monotonic() - st

    if "qc" in config.stages:
        st = time.monotonic()
        logger.info("=== QC ===")
        from polisyos.lex.batch.qc import run_qc

        qc_report = run_qc(
            config,
            fail_fast=config.quality_fail_on_critical,
        )
        stats.stage_times["qc"] = time.monotonic() - st
        qc_metrics = qc_report.metrics if isinstance(qc_report.metrics, dict) else {}
        if stats.quality_gate_passed is None:
            gate_passed = qc_metrics.get("quality_gate_passed")
            stats.quality_gate_passed = bool(gate_passed) if gate_passed is not None else None
        if stats.quality_passed is None:
            stats.quality_passed = stats.quality_gate_passed
        if not stats.quality_gate_failed_checks and isinstance(qc_metrics.get("quality_gate_failed_checks"), list):
            stats.quality_gate_failed_checks = list(qc_metrics.get("quality_gate_failed_checks", []))
            stats.quality_failed_checks = list(stats.quality_gate_failed_checks)
        if not stats.quality_hotspot_failed_checks and isinstance(qc_metrics.get("quality_hotspot_failed_checks"), list):
            stats.quality_hotspot_failed_checks = list(qc_metrics.get("quality_hotspot_failed_checks", []))
        if not stats.quality_warning_failed_checks and isinstance(qc_metrics.get("quality_gate_warning_failed_checks"), list):
            stats.quality_warning_failed_checks = list(qc_metrics.get("quality_gate_warning_failed_checks", []))
        if not stats.quality_skipped_checks and isinstance(qc_metrics.get("quality_gate_skipped_checks"), list):
            stats.quality_skipped_checks = list(qc_metrics.get("quality_gate_skipped_checks", []))
        stats.qc_passed = bool(qc_metrics.get("qc_passed", qc_report.passed))
        stats.qc_failed_checks = list(qc_metrics.get("qc_failed_checks", []))
        release_passed = qc_metrics.get("release_passed")
        stats.release_passed = bool(release_passed) if release_passed is not None else None
        stats.release_failed_checks = list(qc_metrics.get("release_failed_checks", []))

    if "publish_bundle" in config.stages:
        st = time.monotonic()
        logger.info("=== Publish bundle ===")
        from polisyos.lex.batch.publish import run_publish

        run_publish(
            config.output_dir,
            require_embeddings=config.publish_require_embeddings,
        )
        stats.published_bundle = True
        stats.stage_times["publish_bundle"] = time.monotonic() - st

    stats.elapsed_seconds = time.monotonic() - t0
    telemetry_payload = {
        "stage_times": stats.stage_times,
        "total_duration_s": round(stats.elapsed_seconds, 3),
        "docs_processed": stats.total_docs,
        "provisions_extracted": stats.total_provisions,
        "facts_total": stats.facts,
        "facts_grounded": stats.grounded_facts,
        "facts_normative": stats.normative_facts,
        "reference_edges": stats.reference_edges,
        "llm_gate_metrics": stats.llm_gate_metrics,
        "llm_request_log_path": str(config.llm_request_log_path) if config.spo_request_log_enabled else "",
        "quality_gate_passed": stats.quality_gate_passed,
        "quality_passed": stats.quality_passed,
        "quality_gate_failed_checks": stats.quality_gate_failed_checks,
        "quality_failed_checks": stats.quality_failed_checks,
        "quality_hotspot_failed_checks": stats.quality_hotspot_failed_checks,
        "quality_warning_failed_checks": stats.quality_warning_failed_checks,
        "quality_skipped_checks": stats.quality_skipped_checks,
        "qc_passed": stats.qc_passed,
        "qc_failed_checks": stats.qc_failed_checks,
        "benchmark_passed": stats.benchmark_passed,
        "benchmark_failed_checks": stats.benchmark_failed_checks,
        "release_passed": stats.release_passed,
        "release_failed_checks": stats.release_failed_checks,
    }
    with open(config.telemetry_path, "w", encoding="utf-8") as fh:
        json.dump(telemetry_payload, fh, ensure_ascii=False, indent=2)
    logger.info(
        "Pipeline complete in {:.1f}s: {} docs, {} entities, {} facts",
        stats.elapsed_seconds,
        stats.total_docs,
        stats.entities,
        stats.facts,
    )
    return stats
