"""Finalize resolve_extract attempts into one canonical work result per work id."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.academic.batch.article_extractor import _to_work_record
from polisyos.academic.batch.claim_ids import stable_claim_id
from polisyos.academic.batch.resolve_extract import _to_claim_row
from polisyos.academic.knowledge.skg_store import hash_edge_id
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    BoundaryCondition,
    CausalClaim,
    ContextAttribute,
    DesignFamily,
    EvidenceParameter,
    EvidenceSpan,
    EvidenceStrength,
    ModerationEdge,
    ParameterType,
    SourceBasis,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.academic.batch.config import AcademicBatchConfig

_TRANSIENT_ERROR_CLASSES = {"provider_http_429", "provider_http_5xx", "timeout", "empty_response"}
_PERMANENT_ERROR_PREFIXES = ("provider_http_4", "json_parse", "normalization_error")
_UNIT_HINT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(percentage points?|pct points?|pp)\b", re.IGNORECASE), "percentage_points"),
    (re.compile(r"\bbasis points?\b", re.IGNORECASE), "basis_points"),
    (re.compile(r"\bodds ratio\b", re.IGNORECASE), "odds_ratio"),
    (re.compile(r"\brisk ratio\b|\brelative risk\b", re.IGNORECASE), "risk_ratio"),
    (re.compile(r"\bhazard ratio\b", re.IGNORECASE), "hazard_ratio"),
    (re.compile(r"\bsemi[- ]?elasticit(y|ies)\b", re.IGNORECASE), "semi_elasticity"),
    (re.compile(r"\belasticit(y|ies)\b", re.IGNORECASE), "elasticity"),
    (re.compile(r"\bcorrelation\b|\bcorr\b", re.IGNORECASE), "correlation_coefficient"),
    (
        re.compile(
            r"\bstandardi[sz]ed effect\b|\bstandardi[sz]ed coefficient\b|\bbeta\b", re.IGNORECASE
        ),
        "standardized_effect",
    ),
    (re.compile(r"\bindex points?\b|\bscore points?\b", re.IGNORECASE), "index_points"),
    (re.compile(r"\blog odds\b", re.IGNORECASE), "log_odds"),
)
_GENERIC_UNITLESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\btreatment effect\b", re.IGNORECASE),
    re.compile(r"\beffect on\b", re.IGNORECASE),
    re.compile(r"\bimpact on\b", re.IGNORECASE),
    re.compile(r"\bcoefficient\b", re.IGNORECASE),
    re.compile(r"\bestimate\b", re.IGNORECASE),
)
_EFFECT_ESTIMATE_HINT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(treatment effect|effect size|effect estimate|estimated effect|causal effect|impact|"
        r"coefficient|marginal effect|odds ratio|risk ratio|hazard ratio|elasticit(?:y|ies)|"
        r"semi[- ]?elasticit(?:y|ies)|beta)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(change|difference|gain|improvement|increase|decrease|reduction|decline|rise|drop)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(posttest minus pretest|after minus before|before[- ]after|pretest[- ]posttest)\b",
        re.IGNORECASE,
    ),
)
_SCORE_UNIT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bscores?\b", re.IGNORECASE),
    re.compile(r"\bindex\b", re.IGNORECASE),
    re.compile(r"\bscale\b", re.IGNORECASE),
)
_NON_EFFECT_STAT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsample[_ ]?size\b", re.IGNORECASE),
    re.compile(r"\bn[_ ]?observations?\b", re.IGNORECASE),
    re.compile(r"\bp[-_ ]?value\b", re.IGNORECASE),
    re.compile(r"\bsignificance\b", re.IGNORECASE),
    re.compile(r"\bt[-_ ]?stat(istic)?\b", re.IGNORECASE),
    re.compile(r"\bz[-_ ]?stat(istic)?\b", re.IGNORECASE),
)
_STRENGTH_PRIORITY: dict[str, int] = {
    EvidenceStrength.RCT.value: 7,
    EvidenceStrength.QUASI_NATURAL.value: 6,
    EvidenceStrength.QUASI_NATURAL_EVENT.value: 6,
    EvidenceStrength.META_ANALYSIS.value: 5,
    EvidenceStrength.PANEL_FE.value: 4,
    EvidenceStrength.STRUCTURAL.value: 3,
    EvidenceStrength.OBSERVATIONAL.value: 2,
    EvidenceStrength.CROSS_SECTIONAL.value: 1,
    EvidenceStrength.THEORETICAL.value: 0,
    EvidenceStrength.UNKNOWN.value: -1,
}


def _jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_selected_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            work_id = str(row.get("work_id") or "").strip()
            if work_id:
                rows[work_id] = row
    return rows


def _load_attempts(path: Path) -> dict[str, list[ArticleExtractionResult]]:
    grouped: dict[str, list[ArticleExtractionResult]] = defaultdict(list)
    if not path.exists():
        return grouped
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            result = ArticleExtractionResult.model_validate_json(line)
            grouped[result.openalex_id].append(result)
    return grouped


def _evidence_span_key(span: EvidenceSpan) -> tuple[str, str, int | None]:
    return (str(span.section or ""), str(span.text or "").strip(), span.sentence_index)


def _union_spans(*span_lists: list[EvidenceSpan]) -> list[EvidenceSpan]:
    seen: set[tuple[str, str, int | None]] = set()
    merged: list[EvidenceSpan] = []
    for spans in span_lists:
        for span in spans:
            key = _evidence_span_key(span)
            if key in seen:
                continue
            seen.add(key)
            merged.append(span)
    return merged


def _claim_key(result: ArticleExtractionResult, claim: CausalClaim) -> str:
    return claim.claim_id or stable_claim_id(
        work_id=result.openalex_id,
        cause=claim.cause_variable,
        effect=claim.effect_variable,
        claim_text=claim.claim_text,
        direction=claim.direction.value,
        supporting_span_ids=tuple(claim.supporting_span_ids),
    )


def _merge_claims(rows: list[ArticleExtractionResult]) -> list[CausalClaim]:
    merged: dict[str, CausalClaim] = {}
    for result in rows:
        for claim in result.causal_claims:
            key = _claim_key(result, claim)
            existing = merged.get(key)
            if existing is None:
                merged[key] = claim.model_copy(update={"claim_id": key})
                continue
            supporting_spans = _union_spans(existing.supporting_spans, claim.supporting_spans)
            method_spans = _union_spans(existing.method_spans, claim.method_spans)
            publish_blockers = sorted({*existing.publish_blockers, *claim.publish_blockers})
            existing_tier = existing.design_quality_tier or 99
            candidate_tier = claim.design_quality_tier or 99
            merged[key] = existing.model_copy(
                update={
                    "claim_text": existing.claim_text or claim.claim_text,
                    "direction": existing.direction
                    if existing.direction.value != "mixed"
                    else claim.direction,
                    "claim_type": existing.claim_type
                    if existing.claim_type.value != "unclear"
                    else claim.claim_type,
                    "design_family_hint": (
                        existing.design_family_hint
                        if existing.design_family_hint != DesignFamily.UNCLEAR
                        else claim.design_family_hint
                    ),
                    "effect_size": existing.effect_size
                    if existing.effect_size is not None
                    else claim.effect_size,
                    "supporting_spans": supporting_spans,
                    "supporting_span_ids": [
                        span.span_id for span in supporting_spans if span.span_id
                    ],
                    "method_spans": method_spans,
                    "method_span_ids": [span.span_id for span in method_spans if span.span_id],
                    "source_basis": (
                        SourceBasis.FULLTEXT
                        if existing.source_basis == SourceBasis.FULLTEXT
                        or claim.source_basis == SourceBasis.FULLTEXT
                        else SourceBasis.ABSTRACT_ONLY
                    ),
                    "claim_extraction_confidence": max(
                        float(existing.claim_extraction_confidence or 0.0),
                        float(claim.claim_extraction_confidence or 0.0),
                    ),
                    "extraction_warnings": sorted(
                        {*existing.extraction_warnings, *claim.extraction_warnings}
                    ),
                    "strong_design_evidence": bool(
                        existing.strong_design_evidence or claim.strong_design_evidence
                    ),
                    "publish_to_graph": bool(existing.publish_to_graph or claim.publish_to_graph),
                    "publish_blockers": publish_blockers,
                    "design_quality_tier": min(existing_tier, candidate_tier)
                    if min(existing_tier, candidate_tier) < 99
                    else None,
                    "span_contamination_detected": bool(
                        existing.span_contamination_detected or claim.span_contamination_detected
                    ),
                    "scope_conditions": sorted(
                        {*existing.scope_conditions, *claim.scope_conditions}
                    ),
                }
            )
    return list(merged.values())


def _merge_parameters(rows: list[ArticleExtractionResult]) -> list[EvidenceParameter]:
    merged: dict[tuple[Any, ...], EvidenceParameter] = {}
    for result in rows:
        for parameter in result.empirical_parameters:
            key = (
                parameter.name,
                parameter.value,
                parameter.value_range,
                parameter.unit,
                parameter.parameter_type.value,
            )
            existing = merged.get(key)
            if existing is None:
                merged[key] = parameter
                continue
            transfer_conditions = sorted(
                {*existing.transfer_conditions, *parameter.transfer_conditions}
            )
            subgroup_estimates = dict(existing.subgroup_estimates)
            subgroup_estimates.update(parameter.subgroup_estimates)
            merged[key] = existing.model_copy(
                update={
                    "display_name": existing.display_name or parameter.display_name,
                    "confidence_interval": existing.confidence_interval
                    or parameter.confidence_interval,
                    "std_error": existing.std_error
                    if existing.std_error is not None
                    else parameter.std_error,
                    "evidence_strength": (
                        existing.evidence_strength
                        if existing.evidence_strength.value != "unknown"
                        else parameter.evidence_strength
                    ),
                    "geographic_scope": existing.geographic_scope or parameter.geographic_scope,
                    "time_period": existing.time_period or parameter.time_period,
                    "aggregation_level": existing.aggregation_level or parameter.aggregation_level,
                    "transferability": existing.transferability
                    if existing.transferability != "unknown"
                    else parameter.transferability,
                    "transfer_conditions": transfer_conditions,
                    "heterogeneity_note": existing.heterogeneity_note
                    or parameter.heterogeneity_note,
                    "subgroup_estimates": subgroup_estimates,
                }
            )
    return list(merged.values())


def _merge_context_attributes(rows: list[ArticleExtractionResult]) -> list[ContextAttribute]:
    merged: dict[tuple[Any, ...], ContextAttribute] = {}
    for result in rows:
        for attribute in result.context_attributes:
            key = (
                attribute.canonical_name or attribute.attribute_name,
                tuple(sorted(attribute.country_codes)),
                attribute.time_period,
                attribute.value,
                attribute.value_qualitative,
                attribute.unit,
            )
            existing = merged.get(key)
            if existing is None:
                merged[key] = attribute
                continue
            evidence_spans = _union_spans(existing.evidence_spans, attribute.evidence_spans)
            merged[key] = existing.model_copy(
                update={
                    "confidence": max(float(existing.confidence), float(attribute.confidence)),
                    "measurement_method": existing.measurement_method
                    or attribute.measurement_method,
                    "evidence_spans": evidence_spans,
                }
            )
    return list(merged.values())


def _merge_moderation_edges(rows: list[ArticleExtractionResult]) -> list[ModerationEdge]:
    merged: dict[tuple[Any, ...], ModerationEdge] = {}
    for result in rows:
        for edge in result.moderation_edges:
            key = (
                edge.base_claim_id or "",
                edge.base_cause,
                edge.base_effect,
                edge.moderator,
            )
            existing = merged.get(key)
            if existing is None:
                merged[key] = edge.model_copy(
                    update={
                        "source_openalex_ids": sorted(
                            {*edge.source_openalex_ids, result.openalex_id}
                        ),
                    }
                )
                continue
            merged[key] = existing.model_copy(
                update={
                    "direction_of_moderation": existing.direction_of_moderation
                    or edge.direction_of_moderation,
                    "quantitative_interaction": (
                        existing.quantitative_interaction
                        if existing.quantitative_interaction is not None
                        else edge.quantitative_interaction
                    ),
                    "interaction_pvalue": existing.interaction_pvalue
                    if existing.interaction_pvalue is not None
                    else edge.interaction_pvalue,
                    "evidence_count": max(int(existing.evidence_count), int(edge.evidence_count)),
                    "confidence": max(float(existing.confidence), float(edge.confidence)),
                    "match_quality": existing.match_quality or edge.match_quality,
                    "alignment_source": existing.alignment_source or edge.alignment_source,
                    "source_openalex_ids": sorted(
                        {
                            *existing.source_openalex_ids,
                            *edge.source_openalex_ids,
                            result.openalex_id,
                        }
                    ),
                    "evidence_text": existing.evidence_text or edge.evidence_text,
                }
            )
    return list(merged.values())


def _merge_boundaries(rows: list[ArticleExtractionResult]) -> list[BoundaryCondition]:
    merged: dict[tuple[Any, ...], BoundaryCondition] = {}
    for result in rows:
        for boundary in result.boundary_conditions:
            key = (
                boundary.variable,
                boundary.condition_type,
                str(boundary.required_value or boundary.threshold_value or ""),
            )
            existing = merged.get(key)
            if existing is None:
                merged[key] = boundary
                continue
            merged[key] = existing.model_copy(
                update={
                    "scope_text": existing.scope_text or boundary.scope_text,
                    "operator": existing.operator or boundary.operator,
                    "violated_by": sorted({*existing.violated_by, *boundary.violated_by}),
                    "confidence": max(float(existing.confidence), float(boundary.confidence)),
                }
            )
    return list(merged.values())


def _attempt_rank(result: ArticleExtractionResult) -> tuple[Any, ...]:
    published_count = sum(1 for claim in result.causal_claims if claim.publish_to_graph)
    supporting_count = sum(len(claim.supporting_spans) for claim in result.causal_claims)
    method_count = sum(len(claim.method_spans) for claim in result.causal_claims)
    nonempty = int(
        bool(
            result.causal_claims
            or result.empirical_parameters
            or result.context_attributes
            or result.moderation_edges
            or result.boundary_conditions
        )
    )
    no_error = int(str(result.llm_error_class or "") == "")
    fulltext = int(result.source_basis == SourceBasis.FULLTEXT)
    return (
        nonempty,
        fulltext,
        published_count,
        len(result.causal_claims),
        len(result.empirical_parameters),
        len(result.context_attributes),
        len(result.moderation_edges),
        supporting_count,
        method_count,
        no_error,
        float(result.extraction_confidence),
        int(result.token_count_prompt + result.token_count_completion),
    )


def _status_for_attempts(rows: list[ArticleExtractionResult]) -> str:
    if not rows:
        return "permanent_failed"
    any_nonempty = any(
        result.causal_claims
        or result.empirical_parameters
        or result.context_attributes
        or result.moderation_edges
        or result.boundary_conditions
        for result in rows
    )
    if any_nonempty:
        return "succeeded_nonempty"
    error_classes = {
        str(result.llm_error_class or "").strip()
        for result in rows
        if str(result.llm_error_class or "").strip()
    }
    if any(error in _TRANSIENT_ERROR_CLASSES for error in error_classes):
        return "retryable_failed"
    if any(error.startswith(_PERMANENT_ERROR_PREFIXES) for error in error_classes):
        return "permanent_failed"
    return "succeeded_empty"


def _merge_attempts(rows: list[ArticleExtractionResult]) -> ArticleExtractionResult:
    ordered = sorted(rows, key=_attempt_rank, reverse=True)
    primary = ordered[0].model_copy(deep=True)
    merged_claims = _merge_claims(ordered)
    merged_parameters = _merge_parameters(ordered)
    merged_context_attributes = _merge_context_attributes(ordered)
    merged_moderation_edges = _merge_moderation_edges(ordered)
    merged_boundaries = _merge_boundaries(ordered)
    supporting_spans = _union_spans(*[result.supporting_spans for result in ordered])
    method_spans = _union_spans(*[result.method_spans for result in ordered])
    error_classes = sorted(
        {
            str(result.llm_error_class or "").strip()
            for result in ordered
            if str(result.llm_error_class or "").strip()
        }
    )
    extraction_warnings = sorted(
        {
            warning
            for result in ordered
            for warning in result.extraction_warnings
            if str(warning or "").strip()
        }
    )
    source_basis = (
        SourceBasis.FULLTEXT
        if any(result.source_basis == SourceBasis.FULLTEXT for result in ordered)
        else SourceBasis.ABSTRACT_ONLY
    )
    return primary.model_copy(
        update={
            "source_basis": source_basis,
            "supporting_spans": supporting_spans,
            "method_spans": method_spans,
            "empirical_parameters": merged_parameters,
            "causal_claims": merged_claims,
            "boundary_conditions": merged_boundaries,
            "extraction_confidence": max(float(result.extraction_confidence) for result in ordered),
            "llm_error_class": ""
            if any(row for row in ordered if _attempt_rank(row)[0])
            else "|".join(error_classes),
            "extraction_warnings": extraction_warnings,
            "context_attributes": merged_context_attributes,
            "moderation_edges": merged_moderation_edges,
        }
    )


def _link_parameter_to_claims(parameter: EvidenceParameter, claims: list[CausalClaim]) -> list[str]:
    linked: list[str] = []
    candidates = [
        str(parameter.name or "").strip(),
        str(parameter.display_name or "").strip(),
        str(parameter.heterogeneity_note or "").strip(),
    ]
    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        return linked
    for claim in claims:
        claim_text = str(claim.claim_text or "").lower()
        for candidate in candidates:
            candidate_lower = candidate.lower()
            if candidate in {claim.cause_variable, claim.effect_variable}:
                linked.append(claim.claim_id)
                break
            if candidate_lower and candidate_lower in claim_text:
                linked.append(claim.claim_id)
                break
            if _token_overlap_score(candidate, claim.cause_variable) >= 0.34:
                linked.append(claim.claim_id)
                break
            if _token_overlap_score(candidate, claim.effect_variable) >= 0.34:
                linked.append(claim.claim_id)
                break
    return sorted({claim_id for claim_id in linked if claim_id})


def _claims_by_id(claims: list[CausalClaim]) -> dict[str, CausalClaim]:
    return {claim.claim_id: claim for claim in claims if claim.claim_id}


def _tokenize_variable_name(value: str) -> set[str]:
    text = str(value or "").strip().lower()
    if not text:
        return set()
    parts = re.split(r"[^a-z0-9]+", text.replace(".", "_"))
    return {part for part in parts if part and len(part) >= 3}


def _token_overlap_score(left: str, right: str) -> float:
    left_tokens = _tokenize_variable_name(left)
    right_tokens = _tokenize_variable_name(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _best_strength(values: list[str]) -> str:
    cleaned = [str(value or "").strip() for value in values if str(value or "").strip()]
    if not cleaned:
        return EvidenceStrength.UNKNOWN.value
    return max(cleaned, key=lambda value: _STRENGTH_PRIORITY.get(value, -1))


def _parameter_context_text(parameter: EvidenceParameter) -> str:
    parts = [
        str(parameter.display_name or ""),
        str(parameter.name or ""),
        str(parameter.heterogeneity_note or ""),
    ]
    return " | ".join(part for part in parts if part).strip()


def _has_effect_estimate_hint(text: str) -> bool:
    return any(pattern.search(text) for pattern in _EFFECT_ESTIMATE_HINT_PATTERNS)


def _parameter_is_non_effect_statistic(parameter: EvidenceParameter) -> bool:
    text = _parameter_context_text(parameter)
    return any(pattern.search(text) for pattern in _NON_EFFECT_STAT_PATTERNS)


def _ambiguous_small_number_parameter_names(parameters: list[EvidenceParameter]) -> set[str]:
    grouped: dict[str, list[EvidenceParameter]] = defaultdict(list)
    for parameter in parameters:
        if parameter.parameter_type != ParameterType.QUANTITATIVE:
            continue
        if parameter.value is None:
            continue
        if not (0.0 <= abs(float(parameter.value)) <= 1.0):
            continue
        if str(parameter.unit or "").strip():
            continue
        if parameter.confidence_interval is not None or parameter.std_error is not None:
            continue
        if parameter.evidence_strength.value not in {
            EvidenceStrength.UNKNOWN.value,
            EvidenceStrength.THEORETICAL.value,
        }:
            continue
        grouped[str(parameter.name or "").strip()].append(parameter)
    return {name for name, rows in grouped.items() if name and len(rows) >= 2}


def _effective_parameter_strength(
    parameter: EvidenceParameter,
    *,
    result: ArticleExtractionResult,
    linked_claims: list[CausalClaim],
) -> str:
    if parameter.evidence_strength.value not in {
        EvidenceStrength.UNKNOWN.value,
        EvidenceStrength.THEORETICAL.value,
    }:
        return parameter.evidence_strength.value
    claim_strength = _best_strength([claim.evidence_strength.value for claim in linked_claims])
    if claim_strength != EvidenceStrength.UNKNOWN.value:
        return claim_strength
    if result.methodology_enum.value != EvidenceStrength.UNKNOWN.value:
        return result.methodology_enum.value
    return parameter.evidence_strength.value


def _effective_parameter_unit(
    parameter: EvidenceParameter,
    *,
    linked_claims: list[CausalClaim],
) -> str | None:
    explicit_unit = str(parameter.unit or "").strip()
    if explicit_unit:
        return explicit_unit
    text = _parameter_context_text(parameter)
    has_effect_hint = _has_effect_estimate_hint(text)
    for pattern, canonical_unit in _UNIT_HINT_PATTERNS:
        if pattern.search(text):
            return canonical_unit
    if linked_claims and parameter.value is not None and abs(float(parameter.value)) >= 0.1:
        if has_effect_hint and any(pattern.search(text) for pattern in _SCORE_UNIT_PATTERNS):
            return "index_points"
    if linked_claims and parameter.value is not None and abs(float(parameter.value)) >= 0.1:
        if any(pattern.search(text) for pattern in _GENERIC_UNITLESS_PATTERNS):
            return "unitless"
    return None


def _parameter_point_value(parameter: EvidenceParameter, *, mode: str) -> tuple[float | None, str]:
    if parameter.value is not None:
        return float(parameter.value), "explicit_value"
    if parameter.value_range is not None and mode != "high_precision":
        lo, hi = parameter.value_range
        return (float(lo) + float(hi)) / 2.0, "midpoint_from_range"
    return None, ""


def _linked_edge_ids(result: ArticleExtractionResult, linked_claim_ids: list[str]) -> list[str]:
    claim_lookup = _claims_by_id(result.causal_claims)
    edge_ids: set[str] = set()
    for claim_id in linked_claim_ids:
        claim = claim_lookup.get(claim_id)
        if claim is None:
            continue
        edge_ids.add(
            hash_edge_id(
                claim.cause_variable,
                claim.effect_variable,
                claim.direction.value,
            )
        )
    return sorted(edge_ids)


def _curated_numeric_rows(
    result: ArticleExtractionResult,
    *,
    mode: str,
    source_context: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    claim_lookup = _claims_by_id(result.causal_claims)
    ambiguous_names = _ambiguous_small_number_parameter_names(result.empirical_parameters)
    for parameter in result.empirical_parameters:
        if parameter.parameter_type != ParameterType.QUANTITATIVE:
            continue
        if _parameter_is_non_effect_statistic(parameter):
            continue
        if parameter.name in ambiguous_names and not str(parameter.unit or "").strip():
            continue
        if mode == "off":
            continue
        point_estimate, estimate_source = _parameter_point_value(parameter, mode=mode)
        if point_estimate is None:
            continue
        linked_claim_ids = _link_parameter_to_claims(parameter, result.causal_claims)
        linked_claims = [
            claim_lookup[claim_id] for claim_id in linked_claim_ids if claim_id in claim_lookup
        ]
        effective_unit = _effective_parameter_unit(parameter, linked_claims=linked_claims)
        effective_strength = _effective_parameter_strength(
            parameter,
            result=result,
            linked_claims=linked_claims,
        )
        uncertainty_source = (
            "confidence_interval"
            if parameter.confidence_interval is not None
            else "std_error"
            if parameter.std_error is not None
            else ""
        )
        quality_flags: list[str] = []
        if not effective_unit:
            quality_flags.append("unit_missing")
        if effective_strength in {
            EvidenceStrength.UNKNOWN.value,
            EvidenceStrength.THEORETICAL.value,
        }:
            quality_flags.append("weak_evidence_strength")
        if not linked_claim_ids:
            quality_flags.append("claim_link_missing")
        if not uncertainty_source:
            quality_flags.append("uncertainty_missing")
        rows.append(
            {
                "numeric_id": hashlib.sha256(
                    f"curated|{result.openalex_id}|{parameter.name}|{point_estimate}|{effective_unit or ''}".encode()
                ).hexdigest()[:24],
                "openalex_id": result.openalex_id,
                "canonical_name": parameter.name,
                "parameter_name": parameter.name,
                "display_name": parameter.display_name or parameter.name,
                "estimate_type": estimate_source,
                "point_estimate": float(point_estimate),
                "estimate_sign": "positive"
                if point_estimate > 0
                else "negative"
                if point_estimate < 0
                else "null",
                "confidence_interval": list(parameter.confidence_interval)
                if parameter.confidence_interval
                else None,
                "std_error": parameter.std_error,
                "unit": effective_unit,
                "evidence_strength": effective_strength,
                "source_basis": result.source_basis.value,
                "geographic_scope": parameter.geographic_scope,
                "time_period": parameter.time_period,
                "linked_claim_ids": linked_claim_ids,
                "linked_edge_ids": _linked_edge_ids(result, linked_claim_ids),
                "linked_edge_pairs": [
                    {"src": claim.cause_variable, "dst": claim.effect_variable}
                    for claim in result.causal_claims
                    if claim.claim_id in linked_claim_ids
                ],
                "source_context": source_context or None,
                "source_layer": "curated_numeric",
                "uncertainty_source": uncertainty_source,
                "quality_flags": quality_flags,
            }
        )
    return rows


def _strict_simulation_ready_rows(curated_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _STRONG_EVIDENCE_TYPES = {
        EvidenceStrength.RCT.value,
        EvidenceStrength.META_ANALYSIS.value,
    }
    rows: list[dict[str, Any]] = []
    for row in curated_rows:
        if row.get("point_estimate") is None:
            continue
        if not str(row.get("unit") or "").strip():
            continue
        if str(row.get("evidence_strength") or "") in {
            EvidenceStrength.UNKNOWN.value,
            EvidenceStrength.THEORETICAL.value,
            "",
        }:
            continue
        if not row.get("linked_claim_ids") and not row.get("linked_edge_ids"):
            continue
        is_strong = str(row.get("evidence_strength") or "") in _STRONG_EVIDENCE_TYPES
        # Relax uncertainty gate for strong evidence (RCT/META_ANALYSIS)
        if not is_strong:
            if row.get("confidence_interval") in (None, []) and row.get("std_error") is None:
                continue
        # Relax source_context gate for strong evidence (flag quality issue)
        if not isinstance(row.get("source_context"), dict) or not row["source_context"]:
            if not is_strong:
                continue
            existing_flags = (
                json.loads(row.get("quality_flags_json") or "[]")
                if row.get("quality_flags_json")
                else []
            )
            row = {
                **row,
                "quality_flags_json": json.dumps([*existing_flags, "missing_source_context"]),
            }
        rows.append(
            {
                **row,
                "source_layer": "simulation_ready",
            }
        )
    return rows


def _simulation_ready_parameters(
    result: ArticleExtractionResult,
    *,
    mode: str,
    source_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if result.source_basis != SourceBasis.FULLTEXT:
        # Allow abstract-only for RCT/META_ANALYSIS evidence
        has_strong = any(
            c.evidence_strength in {EvidenceStrength.RCT, EvidenceStrength.META_ANALYSIS}
            for c in result.causal_claims
        )
        if not has_strong:
            return rows
    curated_rows = _curated_numeric_rows(
        result,
        mode=mode,
        source_context=source_context or {},
    )
    strict_rows = _strict_simulation_ready_rows(curated_rows)
    if strict_rows or mode == "high_precision":
        return strict_rows

    claim_lookup = _claims_by_id(result.causal_claims)
    ambiguous_names = _ambiguous_small_number_parameter_names(result.empirical_parameters)
    for parameter in result.empirical_parameters:
        if parameter.parameter_type != ParameterType.QUANTITATIVE:
            continue
        if _parameter_is_non_effect_statistic(parameter):
            continue
        if parameter.name in ambiguous_names and not str(parameter.unit or "").strip():
            continue
        if mode == "off":
            continue
        point_estimate, estimate_source = _parameter_point_value(parameter, mode=mode)
        if point_estimate is None:
            continue
        linked_claim_ids = _link_parameter_to_claims(parameter, result.causal_claims)
        linked_claims = [
            claim_lookup[claim_id] for claim_id in linked_claim_ids if claim_id in claim_lookup
        ]
        effective_unit = _effective_parameter_unit(parameter, linked_claims=linked_claims)
        effective_strength = _effective_parameter_strength(
            parameter,
            result=result,
            linked_claims=linked_claims,
        )
        uncertainty_source = (
            "confidence_interval"
            if parameter.confidence_interval is not None
            else "std_error"
            if parameter.std_error is not None
            else ""
        )
        quality_flags: list[str] = []
        if not effective_unit:
            quality_flags.append("unit_missing")
        if effective_strength in {
            EvidenceStrength.UNKNOWN.value,
            EvidenceStrength.THEORETICAL.value,
        }:
            quality_flags.append("weak_evidence_strength")
        if not linked_claim_ids:
            quality_flags.append("claim_link_missing")
        if not uncertainty_source:
            quality_flags.append("uncertainty_missing")
        rows.append(
            {
                "numeric_id": hashlib.sha256(
                    f"{result.openalex_id}|{parameter.name}|{point_estimate}|{effective_unit or ''}".encode()
                ).hexdigest()[:24],
                "openalex_id": result.openalex_id,
                "canonical_name": parameter.name,
                "parameter_name": parameter.name,
                "display_name": parameter.display_name or parameter.name,
                "estimate_type": estimate_source,
                "point_estimate": point_estimate,
                "estimate_sign": "positive"
                if point_estimate > 0
                else "negative"
                if point_estimate < 0
                else "null",
                "confidence_interval": list(parameter.confidence_interval)
                if parameter.confidence_interval
                else None,
                "std_error": parameter.std_error,
                "unit": effective_unit,
                "evidence_strength": effective_strength,
                "source_basis": result.source_basis.value,
                "geographic_scope": parameter.geographic_scope,
                "time_period": parameter.time_period,
                "linked_claim_ids": linked_claim_ids,
                "linked_edge_ids": _linked_edge_ids(result, linked_claim_ids),
                "linked_edge_pairs": [
                    {"src": claim.cause_variable, "dst": claim.effect_variable}
                    for claim in result.causal_claims
                    if claim.claim_id in linked_claim_ids
                ],
                "source_context": source_context or None,
                "source_layer": "simulation_ready",
                "uncertainty_source": uncertainty_source,
                "quality_flags": quality_flags,
            }
        )
    return rows


def run_resolve_finalize(config: AcademicBatchConfig) -> dict[str, int]:
    """Run resolve finalize."""
    started_at = datetime.now(UTC).isoformat()
    attempts_by_work = _load_attempts(config.resolve_extract_attempts_path)
    if not attempts_by_work:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "resolve_finalize.json",
            stage="resolve_finalize",
            status="ok",
            metrics={"attempts": 0, "finalized": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"attempts": 0, "finalized": 0}

    selected_rows = _load_selected_rows(config.selected_global_works_path)
    final_results: list[dict[str, Any]] = []
    final_work_rows: list[dict[str, Any]] = []
    raw_claim_rows: list[dict[str, Any]] = []
    published_claim_rows: list[dict[str, Any]] = []
    clean_context_rows: list[dict[str, Any]] = []
    clean_moderation_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for work_id, attempts in sorted(attempts_by_work.items()):
        merged = _merge_attempts(attempts)
        resolution_status = _status_for_attempts(attempts)
        status_counts[resolution_status] += 1
        final_results.append(merged.model_dump(mode="json"))

        selected_row = selected_rows.get(work_id, {})
        raw_work = selected_row.get("work") if isinstance(selected_row.get("work"), dict) else {}
        record = _to_work_record(
            result=merged,
            raw_work=raw_work if isinstance(raw_work, dict) else {},
            topic_ids=[
                str(item) for item in selected_row.get("topic_ids", []) if str(item).strip()
            ],
            topic_display_names=[
                str(item)
                for item in selected_row.get("topic_display_names", [])
                if str(item).strip()
            ],
            run_id=config.run_id,
            pass_name=config.pass_name,
        )
        simulation_ready = _simulation_ready_parameters(
            merged,
            mode=config.numeric_precision_mode,
            source_context=record.context_profile,
        )
        record = record.model_copy(
            update={
                "metadata": {
                    **record.metadata,
                    "resolve_finalize": True,
                    "resolution_status": resolution_status,
                    "attempt_count": len(attempts),
                    "attempt_error_classes": sorted(
                        {
                            str(result.llm_error_class or "").strip()
                            for result in attempts
                            if str(result.llm_error_class or "").strip()
                        }
                    ),
                    "simulation_ready_numeric_estimates": simulation_ready,
                }
            }
        )
        final_work_rows.append(record.model_dump(mode="json"))

        for claim in merged.causal_claims:
            row = _to_claim_row(
                merged,
                claim,
                topic_ids=[
                    str(item) for item in selected_row.get("topic_ids", []) if str(item).strip()
                ],
                topic_display_names=[
                    str(item)
                    for item in selected_row.get("topic_display_names", [])
                    if str(item).strip()
                ],
            )
            raw_claim_rows.append(row)
            if claim.publish_to_graph:
                published_claim_rows.append(row)

        for attribute in merged.context_attributes:
            if not attribute.evidence_spans:
                continue
            clean_context_rows.append(
                {
                    "openalex_id": merged.openalex_id,
                    **attribute.model_dump(mode="json"),
                    "evidence_span_count": len(attribute.evidence_spans),
                }
            )
        for edge in merged.moderation_edges:
            clean_moderation_rows.append(
                {
                    "openalex_id": merged.openalex_id,
                    **edge.model_dump(mode="json"),
                }
            )
        numeric_rows.extend(simulation_ready)

    for path in (
        config.resolve_extract_final_results_path,
        config.resolve_extract_final_works_path,
        config.raw_claim_candidates_final_path,
        config.published_claims_final_path,
        config.context_attributes_clean_path,
        config.moderation_edges_clean_path,
        config.simulation_ready_numeric_path,
    ):
        if path.exists():
            path.unlink()

    _jsonl_write(config.resolve_extract_final_results_path, final_results)
    _jsonl_write(config.resolve_extract_final_works_path, final_work_rows)
    _jsonl_write(config.raw_claim_candidates_final_path, raw_claim_rows)
    _jsonl_write(config.published_claims_final_path, published_claim_rows)
    _jsonl_write(config.context_attributes_clean_path, clean_context_rows)
    _jsonl_write(config.moderation_edges_clean_path, clean_moderation_rows)
    _jsonl_write(config.simulation_ready_numeric_path, numeric_rows)

    metrics = {
        "attempts": sum(len(rows) for rows in attempts_by_work.values()),
        "works_seen": len(attempts_by_work),
        "finalized": len(final_results),
        "succeeded_nonempty": int(status_counts.get("succeeded_nonempty", 0)),
        "succeeded_empty": int(status_counts.get("succeeded_empty", 0)),
        "retryable_failed": int(status_counts.get("retryable_failed", 0)),
        "permanent_failed": int(status_counts.get("permanent_failed", 0)),
        "raw_claims_final": len(raw_claim_rows),
        "published_claims_final": len(published_claim_rows),
        "clean_context_attributes": len(clean_context_rows),
        "clean_moderation_edges": len(clean_moderation_rows),
        "simulation_ready_numeric": len(numeric_rows),
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "resolve_finalize.json",
        stage="resolve_finalize",
        status="ok",
        metrics=metrics,
        artifacts=[
            config.resolve_extract_final_results_path,
            config.resolve_extract_final_works_path,
            config.raw_claim_candidates_final_path,
            config.published_claims_final_path,
            config.context_attributes_clean_path,
            config.moderation_edges_clean_path,
            config.simulation_ready_numeric_path,
        ],
        started_at=started_at,
    )
    return metrics


__all__ = ["run_resolve_finalize"]
