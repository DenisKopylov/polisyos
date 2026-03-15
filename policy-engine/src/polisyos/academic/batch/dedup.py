"""Stage: merge parsed files and deduplicate by OpenAlex work id."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from typing import Any

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.knowledge.types import SourceTopicRef, WorkRecord
from polisyos.batch_common.manifest import write_stage_manifest


class MergeStats(dict):
    """Dict-like merge stats."""


def _iter_input_files(config: AcademicBatchConfig) -> list:
    parsed = sorted(config.parsed_dir.glob("*.jsonl"))
    extracted = sorted(config.extracted_dir.glob("*.jsonl"))
    if config.resolve_extract_final_works_path.exists():
        extracted = [
            path
            for path in extracted
            if path.name != "resolve_extract.jsonl"
        ]
    return parsed + extracted


def _payload_key(value: Any) -> str:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _union_items(left: list[Any], right: list[Any]) -> list[Any]:
    seen: set[str] = set()
    merged: list[Any] = []
    for item in [*left, *right]:
        key = _payload_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _merge_metadata(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {**base, **incoming}
    list_keys = {
        "supporting_spans",
        "method_spans",
        "extraction_warnings",
        "heterogeneity_results",
        "context_attributes",
        "moderation_edges",
        "attempt_error_classes",
    }
    for key in list_keys:
        left = base.get(key) if isinstance(base.get(key), list) else []
        right = incoming.get(key) if isinstance(incoming.get(key), list) else []
        if left or right:
            merged[key] = _union_items(left, right)
    dict_keys = {"reconciliation_diagnostics"}
    for key in dict_keys:
        if isinstance(base.get(key), dict) or isinstance(incoming.get(key), dict):
            merged[key] = {
                **(base.get(key) if isinstance(base.get(key), dict) else {}),
                **(incoming.get(key) if isinstance(incoming.get(key), dict) else {}),
            }
    return merged


def _prefer_scalar(preferred_value: Any, fallback_value: Any) -> Any:
    if preferred_value not in (None, "", [], {}):
        return preferred_value
    return fallback_value


def _merge_records(base: WorkRecord, incoming: WorkRecord) -> WorkRecord:
    """Merge duplicate records preserving topic links and stronger extraction."""
    # Topic refs union by topic_id
    by_topic: dict[str, SourceTopicRef] = {t.topic_id: t for t in base.source_topics}
    for t in incoming.source_topics:
        existing = by_topic.get(t.topic_id)
        if existing is None or t.selection_score > existing.selection_score:
            by_topic[t.topic_id] = t

    # Explicit precedence: resolve_extract > article_extract > llm_enriched > deterministic(parse).
    mode_priority = {
        "deterministic": 1,
        "llm_enriched": 2,
        "article_extract": 3,
        "resolve_extract": 4,
    }
    base_priority = mode_priority.get(base.extraction_mode, 0)
    incoming_priority = mode_priority.get(incoming.extraction_mode, 0)

    if incoming_priority > base_priority:
        chosen_estimates = incoming.estimates
        chosen_claims = incoming.causal_claims
        chosen_bounds = incoming.boundary_conditions
        extraction_mode = incoming.extraction_mode
        chosen_metadata = incoming.metadata
    elif incoming_priority < base_priority:
        extraction_mode = base.extraction_mode
    else:
        extraction_mode = (
            incoming.extraction_mode
            if incoming.extraction_confidence > base.extraction_confidence
            else base.extraction_mode
        )

    preferred = incoming if incoming_priority > base_priority else base
    fallback = base if preferred is incoming else incoming

    merged = base.model_copy(
        update={
            "source_topics": sorted(by_topic.values(), key=lambda x: x.topic_id),
            "title": _prefer_scalar(preferred.title, fallback.title),
            "doi": _prefer_scalar(preferred.doi, fallback.doi),
            "abstract": _prefer_scalar(preferred.abstract, fallback.abstract),
            "year": preferred.year or fallback.year,
            "publication_date": _prefer_scalar(preferred.publication_date, fallback.publication_date),
            "language": _prefer_scalar(preferred.language, fallback.language),
            "work_type": _prefer_scalar(preferred.work_type, fallback.work_type),
            "is_retracted": bool(base.is_retracted or incoming.is_retracted),
            "cited_by_count": max(base.cited_by_count, incoming.cited_by_count),
            "fwci": preferred.fwci if preferred.fwci is not None else fallback.fwci,
            "citation_normalized_percentile": (
                preferred.citation_normalized_percentile
                if preferred.citation_normalized_percentile is not None
                else fallback.citation_normalized_percentile
            ),
            "citation_is_top_1_percent": bool(base.citation_is_top_1_percent or incoming.citation_is_top_1_percent),
            "citation_is_top_10_percent": bool(base.citation_is_top_10_percent or incoming.citation_is_top_10_percent),
            "journal": _prefer_scalar(preferred.journal, fallback.journal),
            "source_id": _prefer_scalar(preferred.source_id, fallback.source_id),
            "is_oa": bool(base.is_oa or incoming.is_oa),
            "has_fulltext": bool(base.has_fulltext or incoming.has_fulltext),
            "full_text_url": _prefer_scalar(preferred.full_text_url, fallback.full_text_url),
            "concepts": _union_items(base.concepts, incoming.concepts),
            "study_design": _prefer_scalar(preferred.study_design, fallback.study_design),
            "trust_score": max(base.trust_score, incoming.trust_score),
            "extraction_confidence": max(base.extraction_confidence, incoming.extraction_confidence),
            "extraction_mode": extraction_mode,
            "estimates": _union_items(base.estimates, incoming.estimates),
            "causal_claims": _union_items(base.causal_claims, incoming.causal_claims),
            "boundary_conditions": _union_items(base.boundary_conditions, incoming.boundary_conditions),
            "context_profile": {
                **(base.context_profile if isinstance(base.context_profile, dict) else {}),
                **(incoming.context_profile if isinstance(incoming.context_profile, dict) else {}),
            },
            "method_signal_score": max(base.method_signal_score, incoming.method_signal_score),
            "llm_gate_route": _prefer_scalar(preferred.llm_gate_route, fallback.llm_gate_route),
            "llm_gate_score": max(base.llm_gate_score, incoming.llm_gate_score),
            "llm_gate_reasons": _union_items(base.llm_gate_reasons, incoming.llm_gate_reasons),
            "token_count_prompt": max(base.token_count_prompt, incoming.token_count_prompt),
            "token_count_completion": max(base.token_count_completion, incoming.token_count_completion),
            "screening_cost_usd": max(base.screening_cost_usd, incoming.screening_cost_usd),
            "extraction_cost_usd": max(base.extraction_cost_usd, incoming.extraction_cost_usd),
            "metadata": _merge_metadata(base.metadata, incoming.metadata),
        }
    )
    return merged


def merge_and_dedup(config: AcademicBatchConfig) -> MergeStats:
    started_at = datetime.now(UTC).isoformat()
    merged: list[WorkRecord] = []
    seen: dict[str, WorkRecord] = {}
    duplicates: list[tuple[str, str]] = []

    parsed_files = _iter_input_files(config)
    for file_path in parsed_files:
        with open(file_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = WorkRecord.model_validate_json(line)
                key = rec.id
                if key in seen:
                    duplicates.append((key, file_path.name))
                    seen[key] = _merge_records(seen[key], rec)
                    continue
                seen[key] = rec

    merged = list(seen.values())

    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        for rec in merged:
            fh.write(rec.model_dump_json() + "\n")

    with open(config.topic_links_path, "w", encoding="utf-8") as fh:
        for rec in merged:
            for t in rec.source_topics:
                fh.write(
                    json.dumps(
                        {
                            "run_id": rec.metadata.get("run_id", config.run_id),
                            "pass_name": rec.metadata.get("pass_name", config.pass_name),
                            "work_id": rec.id,
                            "topic_id": t.topic_id,
                            "topic_display_name": t.topic_display_name,
                            "policy_block": t.policy_block,
                            "policy_subblock": t.policy_subblock,
                            "rank": t.rank,
                            "selection_score": t.selection_score,
                            "batch_origin": t.batch_origin,
                            "selected_at": t.selected_at,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    with open(config.duplicates_report_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["work_id", "source_file"])
        writer.writerows(duplicates)

    topic_links = sum(len(r.source_topics) for r in merged)

    stats = MergeStats(
        parsed_files=len(parsed_files),
        merged_records=len(merged),
        duplicates=len(duplicates),
        topic_links=topic_links,
    )

    write_stage_manifest(
        manifest_path=config.manifests_dir / "merge_dedup.json",
        stage="merge_dedup",
        status="ok",
        metrics=dict(stats),
        artifacts=[config.merged_records_path, config.topic_links_path, config.duplicates_report_path],
        started_at=started_at,
    )
    return stats
