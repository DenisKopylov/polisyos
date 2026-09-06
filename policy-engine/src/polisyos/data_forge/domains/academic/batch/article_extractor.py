"""Phase 0a article extraction pipeline (screening + full extraction)."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.core.canon.hashing import content_hash
from polisyos.data_forge.domains.academic.batch.claim_ids import stable_claim_id
from polisyos.data_forge.domains.academic.batch.context_classifier import infer_context_from_article
from polisyos.data_forge.domains.academic.batch.fulltext_resolver import (
    fetch_full_text_for_work,
    reconstruct_abstract,
)
from polisyos.data_forge.domains.academic.batch.prompts import (
    BOUNDARY_CONDITIONS_SCHEMA_HINT,
    CAUSAL_CLAIMS_SCHEMA_HINT,
    EMPIRICAL_PARAMETERS_SCHEMA_HINT,
    MECHANISMS_SCHEMA_HINT,
    SCREENING_PROMPT,
)
from polisyos.data_forge.domains.academic.knowledge.types import (
    ClaimOccurrenceVocabularyTransport,
    EstimateCandidate,
    SourceTopicRef,
    WorkRecord,
)
from polisyos.data_forge.domains.academic.openalex.priority_filter import should_process
from polisyos.data_forge.domains.academic.trust import compute_trust_score
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    BoundaryCondition,
    CausalClaim,
    ClaimExplicitness,
    ClaimType,
    ClaimVocabularyAxisStatus,
    ContextAttribute,
    DesignFamily,
    EvidenceParameter,
    EvidenceSpan,
    EvidenceStrength,
    HeterogeneityResult,
    IdentificationStrategy,
    Mechanism,
    ModerationEdge,
    ParameterType,
    SourceBasis,
    TextQuality,
    VersionedClaimVocabularyEnvelope,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
    from polisyos.data_forge.domains.academic.knowledge.variable_canonizer import VariableCanonizer

logger = get_logger(__name__)


def _parse_json_object(raw_content: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_content)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start != -1 and end > start:
        candidate = raw_content[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


# Minimum required keys for each extraction response type.  Responses missing
# ALL of these keys are treated as structurally invalid (likely hallucinated or
# truncated JSON) and logged as warnings so the data loss becomes visible.
_EXTRACTION_REQUIRED_KEYS = frozenset({"causal_claims", "empirical_parameters"})
_ADJUDICATION_REQUIRED_KEYS = frozenset({"claim_validity_score", "causal_credibility"})
_SCREENING_REQUIRED_KEYS = frozenset({"relevant"})


def _validate_extraction_response(
    parsed: dict[str, Any] | None, *, context: str = "extraction"
) -> dict[str, Any] | None:
    """Validate that a parsed LLM response has the expected structure.

    Returns the parsed dict if valid, or None if structurally invalid.
    Logs a warning for invalid responses to make data loss visible.
    """
    if parsed is None:
        return None
    if context == "extraction":
        required = _EXTRACTION_REQUIRED_KEYS
    elif context == "adjudication":
        required = _ADJUDICATION_REQUIRED_KEYS
    elif context == "screening":
        required = _SCREENING_REQUIRED_KEYS
    else:
        return parsed  # unknown context → no validation

    present = required & set(parsed.keys())
    if not present:
        logger.warning(
            "LLM {} response missing ALL required keys {}; got keys: {}",
            context,
            sorted(required),
            sorted(parsed.keys())[:10],
        )
        return None
    return parsed


_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_QUALITATIVE_SCORE_MAP = {
    "very_low": 0.15,
    "low": 0.3,
    "medium": 0.55,
    "moderate": 0.6,
    "high": 0.85,
    "very_high": 0.95,
}
_EVIDENCE_STRENGTH_ALIASES = {
    "rct": EvidenceStrength.RCT.value,
    "randomized": EvidenceStrength.RCT.value,
    "randomised": EvidenceStrength.RCT.value,
    "quasi": EvidenceStrength.QUASI_NATURAL.value,
    "quasi_natural": EvidenceStrength.QUASI_NATURAL.value,
    "quasi-natural": EvidenceStrength.QUASI_NATURAL.value,
    "quasi_experimental": EvidenceStrength.QUASI_NATURAL.value,
    "quasi-experimental": EvidenceStrength.QUASI_NATURAL.value,
    "natural_experiment": EvidenceStrength.QUASI_NATURAL.value,
    "natural-experiment": EvidenceStrength.QUASI_NATURAL.value,
    "event_study": EvidenceStrength.QUASI_NATURAL_EVENT.value,
    "event-study": EvidenceStrength.QUASI_NATURAL_EVENT.value,
    "meta_analysis": EvidenceStrength.META_ANALYSIS.value,
    "meta-analysis": EvidenceStrength.META_ANALYSIS.value,
    "panel_fe": EvidenceStrength.PANEL_FE.value,
    "system_gmm": EvidenceStrength.PANEL_FE.value,
    "gmm": EvidenceStrength.PANEL_FE.value,
    "structural_model": EvidenceStrength.STRUCTURAL.value,
    "time_series_cointegration": EvidenceStrength.STRUCTURAL.value,
    "observational": EvidenceStrength.OBSERVATIONAL.value,
    "cross_sectional": EvidenceStrength.CROSS_SECTIONAL.value,
    "ols_cross_sectional": EvidenceStrength.CROSS_SECTIONAL.value,
    "theoretical": EvidenceStrength.THEORETICAL.value,
    "unknown": EvidenceStrength.UNKNOWN.value,
    # Canonical names always alias to themselves, including future enum members.
    **{strength.value: strength.value for strength in EvidenceStrength},
}
_PARAMETER_TYPE_ALIASES = {
    "quantitative": ParameterType.QUANTITATIVE.value,
    "qualitative": ParameterType.QUALITATIVE.value,
    "ordinal": ParameterType.ORDINAL.value,
    "distributional": ParameterType.DISTRIBUTIONAL.value,
    "categorical": ParameterType.QUALITATIVE.value,
}
_PARAMETER_UNIT_ALIASES = {
    "pp": "percentage_points",
    "percentage_point": "percentage_points",
    "percentage_points": "percentage_points",
    "pct_point": "percentage_points",
    "pct_points": "percentage_points",
    "basis_point": "basis_points",
    "basis_points": "basis_points",
    "odds_ratio": "odds_ratio",
    "risk_ratio": "risk_ratio",
    "relative_risk": "risk_ratio",
    "hazard_ratio": "hazard_ratio",
    "elasticity": "elasticity",
    "semi_elasticity": "semi_elasticity",
    "correlation_coefficient": "correlation_coefficient",
    "correlation": "correlation_coefficient",
    "standardized_effect": "standardized_effect",
    "standardised_effect": "standardized_effect",
    "index_point": "index_points",
    "index_points": "index_points",
    "score_point": "index_points",
    "score_points": "index_points",
    "unitless": "unitless",
}
_DIRECTION_ALIASES = {
    "positive": "positive",
    "increase": "positive",
    "increases": "positive",
    "negative": "negative",
    "decrease": "negative",
    "decreases": "negative",
    "null": "null",
    "no_effect": "null",
    "no effect": "null",
    "mixed": "mixed",
    "ambiguous": "ambiguous",
    "non_linear": "non_linear",
    "non-linear": "non_linear",
}
_CLAIM_EXPLICITNESS_ALIASES = {
    "explicit": ClaimExplicitness.EXPLICIT.value,
    "implicit": ClaimExplicitness.IMPLICIT.value,
    "unclear": ClaimExplicitness.UNCLEAR.value,
}
_CLAIM_TYPE_ALIASES = {
    "causal_claim": ClaimType.CAUSAL_CLAIM.value,
    "causal_assertion": ClaimType.CAUSAL_CLAIM.value,
    "association": ClaimType.ASSOCIATION.value,
    "associative": ClaimType.ASSOCIATIVE.value,
    "mechanism": ClaimType.MECHANISM.value,
    "descriptive": ClaimType.DESCRIPTIVE.value,
    "normative": ClaimType.NORMATIVE.value,
    "review_summary": ClaimType.REVIEW_SUMMARY.value,
    "unclear": ClaimType.UNCLEAR.value,
    "not_applicable": ClaimType.NOT_APPLICABLE.value,
}
_DESIGN_FAMILY_ALIASES = {
    "rct": DesignFamily.RCT.value,
    "randomized": DesignFamily.RCT.value,
    "randomised": DesignFamily.RCT.value,
    "iv": DesignFamily.IV.value,
    "instrumental_variables": DesignFamily.IV.value,
    "instrumental_variable": DesignFamily.IV.value,
    "did": DesignFamily.DID.value,
    "difference_in_differences": DesignFamily.DID.value,
    "rdd": DesignFamily.RDD.value,
    "synthetic_control": DesignFamily.SYNTHETIC_CONTROL.value,
    "event_study": DesignFamily.EVENT_STUDY.value,
    "event-study": DesignFamily.EVENT_STUDY.value,
    "quasi_experimental_other": DesignFamily.QUASI_EXPERIMENTAL_OTHER.value,
    "quasi-experimental-other": DesignFamily.QUASI_EXPERIMENTAL_OTHER.value,
    "quasi_experimental_did": DesignFamily.QUASI_EXPERIMENTAL_DID.value,
    "quasi_experimental_rdd": DesignFamily.QUASI_EXPERIMENTAL_RDD.value,
    "panel_fe": DesignFamily.PANEL_FE.value,
    "fixed_effects": DesignFamily.PANEL_FE.value,
    "fe": DesignFamily.PANEL_FE.value,
    "ols": DesignFamily.OLS.value,
    "ols_cross_sectional": DesignFamily.OLS_CROSS_SECTIONAL.value,
    "meta_analysis": DesignFamily.META_ANALYSIS.value,
    "review": DesignFamily.REVIEW.value,
    "review_narrative": DesignFamily.REVIEW_NARRATIVE.value,
    "review_meta_analysis": DesignFamily.REVIEW_META_ANALYSIS.value,
    "theoretical": DesignFamily.THEORETICAL.value,
    "structural_model": DesignFamily.STRUCTURAL_MODEL.value,
    "time_series_cointegration": DesignFamily.TIME_SERIES_COINTEGRATION.value,
    "unclear": DesignFamily.UNCLEAR.value,
}
_METHOD_SENTENCE_RE = re.compile(
    r"\b(randomi[sz]ed|random assignment|random lottery|field experiment|audit study|correspondence study|"
    r"survey experiment|lab(?:oratory)? experiment|encouragement design|instrumental variable|2sls|tsls|"
    r"difference.?in.?differences?|did\b|regression discontinuity|rdd\b|synthetic control|event study|"
    r"natural experiment|quasi[- ]experimental|staggered adoption|staggered rollout|fixed effects?|panel data|"
    r"administrative data|registry data|register data|microdata|matched employer[- ]employee|ols\b|"
    r"ordinary least squares|regression)\b",
    re.IGNORECASE,
)
_RESULT_SENTENCE_RE = re.compile(
    r"\b(we find|find that|results show|our results|our findings|we show|we document|we provide evidence|"
    r"evidence from|evidence on|estimate|estimated|increases?|decreases?|reduces?|raises?|affect(?:s|ed|ing)?|"
    r"effects? on|impact on|coefficient|beta\b|odds ratio|risk ratio|hazard ratio|leads to|causes?|"
    r"has no effect|no effect on)\b",
    re.IGNORECASE,
)
_CLAIM_SENTENCE_RE = re.compile(
    r"\b(causes?|effect of|impact of|leads to|results in|increases?|decreases?|reduces?|raises?|"
    r"affect(?:s|ed|ing)?|find that|show that|document that|evidence that|associated with|no effect on)\b",
    re.IGNORECASE,
)
_NUMERIC_RESULT_SNIPPET_RE = re.compile(
    r"\b((?:95%|90%)\s*C[Ii]|(?:SE|s\.e\.|std\.?\s*err(?:or)?)\s*=|"
    r"\bOR\b\s*=|\bRR\b\s*=|\bHR\b\s*=|β\s*=|\bbeta\b\s*=|\bcoefficient\b|\bcoef\.?\b|"
    r"percentage\s*points?|basis\s*points?)\b",
    re.IGNORECASE,
)
_NUMERIC_RESULT_BLOCK_RE = re.compile(
    r"\b("
    r"table\s+\d+|panel\s+[a-z]|\bcol(?:umn)?\s*\(?\d+\)?|regression results?|main results?|"
    r"coefficient|coef\.?\b|beta\b|odds ratio|risk ratio|hazard ratio|"
    r"95%\s*ci|90%\s*ci|confidence interval|std\.?\s*err(?:or)?|se\s*[=:]|"
    r"fixed effects?|instrumental variable|2sls|tsls|difference[- ]?in[- ]?differences?|"
    r"first stage|second stage"
    r")\b",
    re.IGNORECASE,
)


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _extract_first_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("value", "count", "n", "sample_size", "observations", "respondents"):
            parsed = _extract_first_number(value.get(key))
            if parsed is not None:
                return parsed
        return None
    text = _normalized_text(value).replace("−", "-")
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    token = match.group(0)
    if token.count(",") == 1 and "." not in token:
        token = token.replace(",", ".")
    else:
        token = token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def _coerce_float(value: Any) -> float | None:
    return _extract_first_number(value)


def _coerce_int(value: Any) -> int | None:
    parsed = _extract_first_number(value)
    if parsed is None:
        return None
    try:
        return int(parsed)
    except (TypeError, ValueError):
        return None


def _coerce_score(value: Any, *, default: float) -> float:
    parsed = _coerce_float(value)
    if parsed is not None:
        return max(0.0, min(1.0, parsed))
    normalized = _normalized_text(value).lower().replace("-", "_").replace(" ", "_")
    if normalized in _QUALITATIVE_SCORE_MAP:
        return _QUALITATIVE_SCORE_MAP[normalized]
    return default


def _coerce_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _normalized_text(item)
        if text:
            out.append(text)
    return out


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _coerce_number_pair(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    left = _coerce_float(value[0])
    right = _coerce_float(value[1])
    if left is None or right is None:
        return None
    lo, hi = sorted((left, right))
    return (lo, hi)


def _coerce_subgroup_estimates(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        parsed = _coerce_float(raw)
        name = _normalized_text(key)
        if name and parsed is not None:
            out[name] = parsed
    return out


def _normalize_evidence_strength(value: Any) -> str:
    """Accept canonical names and explicit aliases; unrecognized input stays unknown."""
    normalized = _normalized_text(value).lower().replace(" ", "_")
    if not normalized:
        return EvidenceStrength.UNKNOWN.value
    return _EVIDENCE_STRENGTH_ALIASES.get(normalized, EvidenceStrength.UNKNOWN.value)


def _normalize_parameter_type(value: Any, *, fallback: str) -> str:
    normalized = _normalized_text(value).lower().replace(" ", "_")
    if not normalized:
        return fallback
    return _PARAMETER_TYPE_ALIASES.get(normalized, fallback)


def _normalize_parameter_unit(value: Any) -> str | None:
    normalized = _normalized_text(value).lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    return _PARAMETER_UNIT_ALIASES.get(normalized, normalized)


def _normalize_direction(value: Any) -> str:
    normalized = _normalized_text(value).lower().replace(" ", "_")
    if not normalized:
        return "mixed"
    return _DIRECTION_ALIASES.get(normalized, "mixed")


def _normalize_claim_explicitness(value: Any) -> str:
    normalized = _normalized_text(value).lower().replace(" ", "_")
    if not normalized:
        return ClaimExplicitness.UNCLEAR.value
    return _CLAIM_EXPLICITNESS_ALIASES.get(normalized, ClaimExplicitness.UNCLEAR.value)


def _normalize_claim_type(value: Any) -> str:
    normalized = _normalized_text(value).lower().replace(" ", "_")
    if not normalized:
        return ClaimType.UNCLEAR.value
    return _CLAIM_TYPE_ALIASES.get(normalized, ClaimType.UNCLEAR.value)


def _normalize_design_family(value: Any) -> str:
    normalized = _normalized_text(value).lower().replace(" ", "_")
    if not normalized:
        return DesignFamily.UNCLEAR.value
    for key, mapped in _DESIGN_FAMILY_ALIASES.items():
        if key in normalized:
            return mapped
    return _DESIGN_FAMILY_ALIASES.get(normalized, DesignFamily.UNCLEAR.value)


def _normalize_source_basis(value: Any) -> str:
    normalized = _normalized_text(value).lower().replace(" ", "_")
    if normalized == SourceBasis.ABSTRACT_ONLY.value:
        return SourceBasis.ABSTRACT_ONLY.value
    return SourceBasis.FULLTEXT.value


def _normalize_text_quality(value: Any, *, fallback: str) -> str:
    normalized = _normalized_text(value).lower().replace(" ", "_")
    allowed = {
        TextQuality.STRUCTURED_FULLTEXT.value,
        TextQuality.EXTRACTED_FULLTEXT.value,
        TextQuality.ABSTRACT_ONLY.value,
        TextQuality.DEGRADED.value,
    }
    if normalized in allowed:
        return normalized
    return fallback


def _split_sentences(text: str) -> list[str]:
    cleaned = _normalized_text(text)
    if not cleaned:
        return []
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned)
    return [piece.strip() for piece in pieces if piece.strip()]


def _select_top_sentences(
    sentences: list[str], pattern: re.Pattern[str], *, limit: int
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, sentence in enumerate(sentences):
        if not pattern.search(sentence):
            continue
        score = min(1.0, 0.45 + 0.1 * len(pattern.findall(sentence)))
        out.append(
            {
                "section": "methods"
                if pattern is _METHOD_SENTENCE_RE
                else "results"
                if pattern is _RESULT_SENTENCE_RE
                else "claims",
                "text": sentence,
                "sentence_index": index,
                "score": round(score, 3),
            }
        )
        if len(out) >= limit:
            break
    return out


def _select_numeric_result_snippets(text: str, *, limit: int) -> list[dict[str, Any]]:
    normalized = _normalized_text(text)
    if not normalized:
        return []
    snippets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, match in enumerate(_NUMERIC_RESULT_SNIPPET_RE.finditer(normalized), start=1):
        start = max(0, match.start() - 140)
        end = min(len(normalized), match.end() + 180)
        snippet = normalized[start:end].strip(" ;,")
        if len(snippet) < 24 or snippet in seen:
            continue
        seen.add(snippet)
        score = 0.65
        if re.search(r"(?:95%|90%)\s*C[Ii]", snippet, re.IGNORECASE):
            score += 0.15
        if re.search(r"(?:SE|s\.e\.|std\.?\s*err(?:or)?)\s*=", snippet, re.IGNORECASE):
            score += 0.1
        snippets.append(
            {
                "section": "results",
                "text": snippet,
                "sentence_index": None,
                "score": round(min(1.0, score), 3),
                "span_id": f"n_{index:02d}",
            }
        )
        if len(snippets) >= limit:
            break
    return snippets


def _select_numeric_result_blocks(text: str, *, limit: int) -> list[dict[str, Any]]:
    raw_text = str(text or "")
    if not raw_text.strip():
        return []
    snippets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, match in enumerate(_NUMERIC_RESULT_BLOCK_RE.finditer(raw_text), start=1):
        start = max(0, match.start() - 260)
        end = min(len(raw_text), match.end() + 520)
        snippet = _normalized_text(raw_text[start:end]).strip(" ;,")
        if len(snippet) < 80 or snippet in seen:
            continue
        if len(re.findall(r"[-+]?\d+(?:\.\d+)?", snippet)) < 2:
            continue
        seen.add(snippet)
        score = 0.7
        lower = snippet.lower()
        if "table " in lower or "panel " in lower:
            score += 0.05
        if re.search(r"(?:95%|90%)\s*c[i]", lower):
            score += 0.15
        if re.search(r"(?:se|std\.?\s*err(?:or)?)\s*[=:]", lower):
            score += 0.1
        if re.search(r"\b(coef(?:ficient)?|beta|odds ratio|risk ratio|hazard ratio)\b", lower):
            score += 0.1
        snippets.append(
            {
                "section": "results",
                "text": snippet,
                "sentence_index": None,
                "score": round(min(1.0, score), 3),
                "span_id": f"nb_{index:02d}",
            }
        )
        if len(snippets) >= limit:
            break
    return snippets


_PRE_EXTRACTION_CONTAMINATION_RE = re.compile(
    r"(?i)"
    r"(cookie policy|cookie settings|cookie preferences|cookie consent|accept cookies|manage cookies|we use cookies|"
    r"all rights reserved|copyright \d{4}|download pdf|view pdf|view abstract|"
    r"sign in to access|institutional login|explore all metrics|accesses|citations|altmetric|"
    r"doi:\s*\S+|doi\.org/\S+|https?://\S{20,}|"
    r"export citation|download citation|cite this article|"
    r"@article\{[^}]+\}|@inproceedings\{[^}]+\}|"
    r"prev\s+next|skip to main content|toggle navigation|"
    r"published by \w[\w\s]{2,30}press|elsevier|springer|wiley|taylor & francis|sage publications|"
    r"supplementary (?:materials?|data|information|files?)|"
    r"orcid\.org/\S+|"
    r"funding[:\s]+this (?:work|research|study) was (?:supported|funded)[\s\S]{0,200}?\.)"
)


def _build_evidence_bundle(
    *, title: str, abstract: str, text: str, source_kind: str
) -> dict[str, Any]:
    text = _PRE_EXTRACTION_CONTAMINATION_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    sentences = _split_sentences(text)
    abstract_sentences = _split_sentences(abstract)
    method_sentences = _select_top_sentences(
        sentences or abstract_sentences, _METHOD_SENTENCE_RE, limit=6
    )
    result_sentences = _select_top_sentences(
        sentences or abstract_sentences, _RESULT_SENTENCE_RE, limit=8
    )
    claim_sentences = _select_top_sentences(
        sentences or abstract_sentences, _CLAIM_SENTENCE_RE, limit=8
    )
    numeric_result_snippets = _select_numeric_result_snippets(text, limit=8)
    numeric_result_blocks = _select_numeric_result_blocks(text, limit=6)
    if not claim_sentences and abstract_sentences:
        claim_sentences = _select_top_sentences(abstract_sentences, _RESULT_SENTENCE_RE, limit=5)
    source_basis = (
        SourceBasis.ABSTRACT_ONLY.value
        if source_kind == "abstract_fallback"
        else SourceBasis.FULLTEXT.value
    )
    text_quality = (
        TextQuality.ABSTRACT_ONLY.value
        if source_kind == "abstract_fallback"
        else TextQuality.DEGRADED.value
        if len(text) < 800
        else TextQuality.EXTRACTED_FULLTEXT.value
    )
    abstract_rows = [
        {
            "span_id": f"a_{index + 1:02d}",
            "section": "abstract",
            "text": sentence,
            "sentence_index": index,
            "score": 0.5,
        }
        for index, sentence in enumerate(abstract_sentences[:8])
    ]
    for prefix, rows in (("m", method_sentences), ("r", result_sentences), ("c", claim_sentences)):
        for index, row in enumerate(rows, start=1):
            row["span_id"] = f"{prefix}_{index:02d}"
    return {
        "title": title,
        "abstract": abstract,
        "source_kind": source_kind,
        "source_basis": source_basis,
        "text_quality": text_quality,
        "abstract_sentences": abstract_rows,
        "method_sentences": method_sentences,
        "result_sentences": result_sentences,
        "claim_sentences": claim_sentences,
        "numeric_result_snippets": numeric_result_snippets,
        "numeric_result_blocks": numeric_result_blocks,
    }


def _normalize_evidence_span(payload: Any, *, default_section: str = "") -> EvidenceSpan | None:
    if isinstance(payload, str):
        text = _normalized_text(payload)
        if not text:
            return None
        return EvidenceSpan(text=text, section=default_section, sentence_index=None, score=0.5)
    if not isinstance(payload, dict):
        return None
    text = _normalized_text(payload.get("text") or payload.get("sentence") or payload.get("span"))
    if not text:
        return None
    return EvidenceSpan(
        span_id=_normalized_text(payload.get("span_id") or payload.get("id")),
        section=_normalized_text(payload.get("section")) or default_section,
        text=text,
        sentence_index=_coerce_int(payload.get("sentence_index")),
        score=_coerce_score(payload.get("score"), default=0.5),
    )


def _span_lookup(evidence_bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for bucket in (
        "abstract_sentences",
        "method_sentences",
        "result_sentences",
        "claim_sentences",
        "numeric_result_snippets",
        "numeric_result_blocks",
    ):
        for item in evidence_bundle.get(bucket, []):
            if not isinstance(item, dict):
                continue
            span_id = _normalized_text(item.get("span_id"))
            if span_id:
                out[span_id] = item
    return out


def _resolve_span_ids(
    raw_ids: Any,
    *,
    evidence_bundle: dict[str, Any],
    default_section: str,
) -> list[EvidenceSpan]:
    if not isinstance(raw_ids, list):
        return []
    lookup = _span_lookup(evidence_bundle)
    out: list[EvidenceSpan] = []
    for raw_id in raw_ids:
        span_id = _normalized_text(raw_id)
        if not span_id:
            continue
        item = lookup.get(span_id)
        if not item:
            continue
        span = _normalize_evidence_span(
            {**item, "span_id": span_id}, default_section=default_section
        )
        if span is not None:
            out.append(span)
    return out


def _find_supporting_spans(
    *,
    cause: str,
    effect: str,
    claim_text: str,
    evidence_bundle: dict[str, Any],
    limit: int = 3,
) -> list[EvidenceSpan]:
    query_tokens = {
        token
        for token in re.findall(r"[a-z0-9_]{3,}", " ".join([cause, effect, claim_text]).lower())
        if token not in {"the", "and", "for", "with"}
    }
    rows = []
    for bucket in ("claim_sentences", "result_sentences", "abstract_sentences"):
        for item in evidence_bundle.get(bucket, []):
            if not isinstance(item, dict):
                continue
            text = _normalized_text(item.get("text"))
            if not text:
                continue
            lower = text.lower()
            overlap = sum(1 for token in query_tokens if token in lower)
            if overlap <= 0:
                continue
            rows.append(
                (
                    overlap + float(item.get("score") or 0.0),
                    EvidenceSpan(
                        span_id=_normalized_text(item.get("span_id")),
                        section=_normalized_text(item.get("section")),
                        text=text,
                        sentence_index=_coerce_int(item.get("sentence_index")),
                        score=_coerce_score(item.get("score"), default=0.5),
                    ),
                )
            )
    rows.sort(key=lambda pair: pair[0], reverse=True)
    deduped: list[EvidenceSpan] = []
    seen: set[str] = set()
    for _, span in rows:
        if span.text in seen:
            continue
        seen.add(span.text)
        deduped.append(span)
        if len(deduped) >= limit:
            break
    if deduped:
        return deduped

    for bucket in ("claim_sentences", "result_sentences", "abstract_sentences"):
        fallback_items = evidence_bundle.get(bucket, [])
        for item in fallback_items[:limit]:
            if not isinstance(item, dict) or not item.get("text"):
                continue
            deduped.append(
                EvidenceSpan(
                    span_id=_normalized_text(item.get("span_id")),
                    section=_normalized_text(item.get("section")),
                    text=_normalized_text(item.get("text")),
                    sentence_index=_coerce_int(item.get("sentence_index")),
                    score=_coerce_score(item.get("score"), default=0.4),
                )
            )
        if deduped:
            break
    return deduped


def _normalize_empirical_parameter(
    payload: Any,
    *,
    diagnostics: list[str] | None = None,
) -> EvidenceParameter | None:
    if not isinstance(payload, dict):
        if diagnostics is not None:
            diagnostics.append("dropped:non_object")
        return None

    name_source = ""
    name = ""
    for candidate_key in ("name", "parameter", "variable", "variable_hint"):
        name = _normalized_text(payload.get(candidate_key))
        if name:
            name_source = candidate_key
            break
    if not name:
        if diagnostics is not None:
            diagnostics.append("dropped:missing_name")
        return None
    if name in {"sample_size", "study.sample_size", "n", "n_observations"}:
        if diagnostics is not None:
            diagnostics.append(f"dropped:sample_size_parameter:{name}")
        return None
    if diagnostics is not None and name_source and name_source != "name":
        diagnostics.append(f"mapped:{name_source}->name")

    value = _coerce_float(payload.get("value"))
    value_range = _coerce_number_pair(payload.get("value_range"))
    value_qualitative = _normalized_text(payload.get("value_qualitative"))
    if value is None and value_range is None and not value_qualitative:
        fallback_text = _normalized_text(payload.get("value"))
        if fallback_text:
            value_qualitative = fallback_text

    fallback_type = (
        ParameterType.QUANTITATIVE.value
        if (value is not None or value_range is not None)
        else ParameterType.QUALITATIVE.value
    )
    confidence_interval = _coerce_number_pair(payload.get("confidence_interval"))
    if confidence_interval is None:
        confidence_interval = _coerce_number_pair([payload.get("ci_low"), payload.get("ci_high")])
        if confidence_interval is not None and diagnostics is not None:
            diagnostics.append("mapped:ci_low/ci_high->confidence_interval")

    transfer_conditions = _coerce_text_list(payload.get("transfer_conditions"))
    pattern_name = _normalized_text(
        payload.get("pattern_name") or payload.get("extraction_pattern")
    )
    if pattern_name:
        transfer_conditions.append(f"extraction_pattern:{pattern_name}")
        if diagnostics is not None:
            diagnostics.append("retained:pattern_name->transfer_conditions")
    confidence = _coerce_float(payload.get("confidence"))
    if confidence is not None:
        transfer_conditions.append(f"extraction_confidence:{confidence:g}")
        if diagnostics is not None:
            diagnostics.append("retained:confidence->transfer_conditions")

    heterogeneity_note = (
        _normalized_text(
            payload.get("heterogeneity_note")
            or payload.get("context")
            or payload.get("context_snippet")
            or payload.get("source")
        )
        or None
    )
    if (
        diagnostics is not None
        and heterogeneity_note
        and not _normalized_text(payload.get("heterogeneity_note"))
    ):
        if _normalized_text(payload.get("context_snippet")):
            diagnostics.append("mapped:context_snippet->heterogeneity_note")
        elif _normalized_text(payload.get("context")):
            diagnostics.append("mapped:context->heterogeneity_note")
        elif _normalized_text(payload.get("source")):
            diagnostics.append("mapped:source->heterogeneity_note")

    candidate = {
        "name": name,
        "display_name": _normalized_text(payload.get("display_name")) or name,
        "parameter_type": _normalize_parameter_type(
            payload.get("parameter_type"), fallback=fallback_type
        ),
        "value": value,
        "value_range": value_range,
        "value_qualitative": value_qualitative or None,
        "confidence_interval": confidence_interval,
        "std_error": _coerce_float(payload.get("std_error")),
        "unit": _normalize_parameter_unit(payload.get("unit")),
        "evidence_strength": _normalize_evidence_strength(payload.get("evidence_strength")),
        "geographic_scope": _normalized_text(payload.get("geographic_scope")),
        "time_period": _normalized_text(payload.get("time_period")),
        "aggregation_level": _normalized_text(payload.get("aggregation_level")),
        "transferability": _normalized_text(payload.get("transferability")) or "unknown",
        "transfer_conditions": transfer_conditions,
        "heterogeneity_note": heterogeneity_note,
        "subgroup_estimates": _coerce_subgroup_estimates(payload.get("subgroup_estimates")),
    }
    try:
        return EvidenceParameter.model_validate(candidate)
    except (TypeError, ValueError) as exc:
        logger.debug("EvidenceParameter validation failed: {}", exc)
        if diagnostics is not None:
            diagnostics.append(f"dropped:validation_failed:{type(exc).__name__}")
        return None


def _normalize_causal_claim(
    payload: Any,
    *,
    work_id: str,
    evidence_bundle: dict[str, Any],
    default_source_basis: str,
) -> CausalClaim | None:
    if not isinstance(payload, dict):
        return None

    effect_size = _coerce_float(payload.get("effect_size"))
    magnitude_qualitative = _normalized_text(payload.get("magnitude_qualitative"))
    if effect_size is None and not magnitude_qualitative:
        magnitude_qualitative = _normalized_text(payload.get("effect_size")) or None

    cause_variable = _normalized_text(payload.get("cause_variable") or payload.get("cause"))
    effect_variable = _normalized_text(payload.get("effect_variable") or payload.get("effect"))
    claim_text = _normalized_text(payload.get("claim_text"))
    supporting_spans = _resolve_span_ids(
        payload.get("supporting_span_ids"),
        evidence_bundle=evidence_bundle,
        default_section="claims",
    )
    if not supporting_spans:
        supporting_spans = [
            item
            for item in (
                _normalize_evidence_span(raw, default_section="claims")
                for raw in _as_list(payload.get("supporting_spans"))
            )
            if item is not None
        ]
    if not supporting_spans:
        supporting_spans = _find_supporting_spans(
            cause=cause_variable,
            effect=effect_variable,
            claim_text=claim_text,
            evidence_bundle=evidence_bundle,
        )
    method_spans = _resolve_span_ids(
        payload.get("method_span_ids"),
        evidence_bundle=evidence_bundle,
        default_section="methods",
    )
    if not method_spans:
        method_spans = [
            item
            for item in (
                _normalize_evidence_span(raw, default_section="methods")
                for raw in _as_list(payload.get("method_spans"))
            )
            if item is not None
        ]
    if not method_spans:
        method_spans = [
            EvidenceSpan.model_validate(item)
            for item in evidence_bundle.get("method_sentences", [])[:3]
            if isinstance(item, dict) and item.get("text")
        ]

    candidate = {
        "claim_id": stable_claim_id(
            work_id=work_id,
            cause=cause_variable,
            effect=effect_variable,
            claim_text=claim_text,
            direction=_normalize_direction(payload.get("direction")),
            supporting_span_ids=tuple(
                span.span_id for span in supporting_spans if getattr(span, "span_id", "")
            ),
        ),
        "claim_text": claim_text,
        "claim_type": _normalize_claim_type(payload.get("claim_type")),
        "cause_variable": cause_variable,
        "effect_variable": effect_variable,
        "direction": _normalize_direction(payload.get("direction")),
        "claim_explicitness": _normalize_claim_explicitness(payload.get("claim_explicitness")),
        "design_family_hint": _normalize_design_family(payload.get("design_family_hint")),
        "magnitude_qualitative": magnitude_qualitative,
        "effect_size": effect_size,
        "evidence_strength": _normalize_evidence_strength(payload.get("evidence_strength")),
        "scope_conditions": _coerce_text_list(payload.get("scope_conditions")),
        "counterevidence_notes": _normalized_text(
            payload.get("counterevidence_notes") or payload.get("mechanism")
        ),
        "supporting_spans": supporting_spans,
        "method_spans": method_spans,
        "supporting_span_ids": [span.span_id for span in supporting_spans if span.span_id],
        "method_span_ids": [span.span_id for span in method_spans if span.span_id],
        "source_basis": _normalize_source_basis(
            payload.get("source_basis") or default_source_basis
        ),
        "claim_extraction_confidence": _coerce_float(payload.get("claim_extraction_confidence")),
        "extraction_warnings": _coerce_text_list(payload.get("extraction_warnings")),
        "identification_strategy": _normalize_identification_strategy(
            payload.get("identification_strategy")
        ),
    }
    if not candidate["cause_variable"] or not candidate["effect_variable"]:
        return None
    if not candidate["supporting_spans"]:
        return None
    try:
        return CausalClaim.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _normalize_mechanism(payload: Any) -> Mechanism | None:
    if not isinstance(payload, dict):
        return None
    candidate = {
        "description": _normalized_text(payload.get("description") or payload.get("mechanism")),
        "mediating_variables": _coerce_text_list(payload.get("mediating_variables")),
        "evidence_type": _normalized_text(payload.get("evidence_type")),
        "theoretical_framework": _normalized_text(payload.get("theoretical_framework")) or None,
    }
    if not candidate["description"]:
        return None
    try:
        return Mechanism.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _normalize_boundary_condition(payload: Any) -> BoundaryCondition | None:
    if not isinstance(payload, dict):
        return None
    candidate = {
        "variable": _normalized_text(payload.get("variable")),
        "condition_type": _normalized_text(payload.get("condition_type")),
        "required_value": payload.get("required_value"),
        "violated_by": _coerce_text_list(payload.get("violated_by")),
        "consequence_if_violated": _normalized_text(payload.get("consequence_if_violated")),
        "operator": _normalized_text(payload.get("operator")),
        "threshold_value": _normalized_text(payload.get("threshold_value")),
        "scope_text": _normalized_text(payload.get("scope_text")),
        "confidence": _coerce_score(payload.get("confidence"), default=0.0),
    }
    try:
        return BoundaryCondition.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _normalize_identification_strategy(payload: Any) -> IdentificationStrategy | None:
    if not isinstance(payload, dict):
        return None
    candidate = {
        "identification_method": _normalized_text(payload.get("identification_method")),
        "instrument": _normalized_text(payload.get("instrument")),
        "exclusion_restrictions": _coerce_text_list(payload.get("exclusion_restrictions")),
        "design_assumptions": _coerce_text_list(payload.get("design_assumptions")),
        "identification_confidence": _coerce_float(payload.get("identification_confidence")),
    }
    if not candidate["identification_method"]:
        return None
    try:
        return IdentificationStrategy.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _normalize_heterogeneity_result(payload: Any) -> HeterogeneityResult | None:
    if not isinstance(payload, dict):
        return None
    moderator = _normalized_text(payload.get("moderator"))
    if not moderator:
        return None
    subgroup_raw = payload.get("subgroup_effects")
    subgroup_effects: dict[str, float] = {}
    if isinstance(subgroup_raw, dict):
        for k, v in subgroup_raw.items():
            coerced = _coerce_float(v)
            if coerced is not None:
                subgroup_effects[str(k)] = coerced
    candidate = {
        "moderator": moderator,
        "dimension": _normalized_text(payload.get("dimension")),
        "finding": _normalized_text(payload.get("finding")),
        "interaction_coefficient": _coerce_float(payload.get("interaction_coefficient")),
        "interaction_pvalue": _coerce_float(payload.get("interaction_pvalue")),
        "subgroup_effects": subgroup_effects,
        "confidence": _coerce_float(payload.get("confidence")),
    }
    try:
        return HeterogeneityResult.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _normalize_context_attribute(payload: Any) -> ContextAttribute | None:
    if not isinstance(payload, dict):
        return None
    attribute_name = _normalized_text(payload.get("attribute_name"))
    if not attribute_name:
        return None
    candidate = {
        "attribute_name": attribute_name,
        "canonical_name": _normalized_text(payload.get("canonical_name")),
        "value": _coerce_float(payload.get("value")),
        "value_qualitative": _normalized_text(payload.get("value_qualitative")) or None,
        "unit": _normalized_text(payload.get("unit")) or None,
        "country_codes": _coerce_text_list(payload.get("country_codes")),
        "time_period": _normalized_text(payload.get("time_period")),
        "measurement_method": _normalized_text(payload.get("measurement_method")),
        "confidence": _coerce_score(payload.get("confidence"), default=0.5),
    }
    try:
        return ContextAttribute.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _normalize_moderation_edge(payload: Any) -> ModerationEdge | None:
    if not isinstance(payload, dict):
        return None
    base_cause = _normalized_text(payload.get("base_cause"))
    base_effect = _normalized_text(payload.get("base_effect"))
    moderator = _normalized_text(payload.get("moderator"))
    if not base_cause or not base_effect or not moderator:
        return None
    candidate = {
        "base_cause": base_cause,
        "base_effect": base_effect,
        "moderator": moderator,
        "base_claim_id": _normalized_text(payload.get("base_claim_id")) or None,
        "direction_of_moderation": _normalized_text(payload.get("direction_of_moderation")),
        "quantitative_interaction": _coerce_float(payload.get("quantitative_interaction")),
        "interaction_pvalue": _coerce_float(payload.get("interaction_pvalue")),
        "confidence": _coerce_score(payload.get("confidence"), default=0.5),
        "match_quality": _normalized_text(payload.get("match_quality")),
        "alignment_source": _normalized_text(payload.get("alignment_source")),
        "evidence_text": _normalized_text(payload.get("evidence_text")),
    }
    try:
        return ModerationEdge.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _normalize_extraction_payload(
    work: dict[str, Any],
    parsed: dict[str, Any],
    model: str,
    usage: dict[str, Any],
    *,
    evidence_bundle: dict[str, Any],
    source_kind: str,
) -> dict[str, Any]:
    normalization_warnings: list[str] = []
    empirical_parameters: list[EvidenceParameter] = []
    for index, raw_parameter in enumerate(_as_list(parsed.get("empirical_parameters"))):
        diagnostics: list[str] = []
        parameter = _normalize_empirical_parameter(raw_parameter, diagnostics=diagnostics)
        if parameter is not None:
            empirical_parameters.append(parameter)
        normalization_warnings.extend(
            f"empirical_parameters[{index}]:{diagnostic}" for diagnostic in diagnostics
        )
    causal_claims = [
        item
        for item in (
            _normalize_causal_claim(
                raw,
                work_id=str(work.get("id") or ""),
                evidence_bundle=evidence_bundle,
                default_source_basis=evidence_bundle.get(
                    "source_basis", SourceBasis.FULLTEXT.value
                ),
            )
            for raw in _as_list(parsed.get("causal_claims"))
        )
        if item is not None
    ]
    mechanisms = [
        item
        for item in (_normalize_mechanism(raw) for raw in _as_list(parsed.get("mechanisms")))
        if item is not None
    ]
    boundary_conditions = [
        item
        for item in (
            _normalize_boundary_condition(raw)
            for raw in _as_list(parsed.get("boundary_conditions"))
        )
        if item is not None
    ]
    heterogeneity_results = [
        item
        for item in (
            _normalize_heterogeneity_result(raw)
            for raw in _as_list(parsed.get("heterogeneity_results"))
        )
        if item is not None
    ]

    method_spans = [
        item
        for item in (
            _normalize_evidence_span(raw, default_section="methods")
            for raw in _as_list(parsed.get("method_spans"))
        )
        if item is not None
    ]
    if not method_spans:
        method_spans = [
            EvidenceSpan.model_validate(item)
            for item in evidence_bundle.get("method_sentences", [])[:5]
            if isinstance(item, dict) and item.get("text")
        ]

    supporting_spans: list[EvidenceSpan] = []
    seen_spans: set[str] = set()
    for claim in causal_claims:
        for span in claim.supporting_spans:
            if span.text in seen_spans:
                continue
            seen_spans.add(span.text)
            supporting_spans.append(span)
    if not supporting_spans:
        supporting_spans = [
            EvidenceSpan.model_validate(item)
            for item in evidence_bundle.get("claim_sentences", [])[:5]
            if isinstance(item, dict) and item.get("text")
        ]

    return {
        "openalex_id": str(work.get("id") or ""),
        "doi": str(work.get("doi") or ""),
        "title": str(work.get("title") or ""),
        "year": int(work.get("publication_year") or 0) or None,
        "cited_by_count": int(work.get("cited_by_count") or 0),
        "source_basis": _normalize_source_basis(
            parsed.get("source_basis") or evidence_bundle.get("source_basis")
        ),
        "text_quality": _normalize_text_quality(
            parsed.get("text_quality"),
            fallback=evidence_bundle.get("text_quality", TextQuality.EXTRACTED_FULLTEXT.value),
        ),
        "supporting_spans": supporting_spans,
        "method_spans": method_spans,
        "extraction_warnings": [
            *_coerce_text_list(parsed.get("extraction_warnings")),
            *normalization_warnings,
        ],
        "empirical_parameters": empirical_parameters,
        "causal_claims": causal_claims,
        "mechanisms": mechanisms,
        "boundary_conditions": boundary_conditions,
        "methodology": _normalized_text(parsed.get("methodology")),
        "methodology_enum": _normalize_evidence_strength(
            parsed.get("methodology_enum") or parsed.get("evidence_strength")
        ),
        "sample_size": _coerce_int(parsed.get("sample_size")),
        "citation_summary": _normalized_text(parsed.get("citation_summary")),
        "extraction_model": model,
        "extraction_timestamp": datetime.now(UTC).isoformat(),
        "extraction_confidence": _coerce_score(parsed.get("extraction_confidence"), default=0.7),
        "heterogeneity_results": heterogeneity_results,
        "external_validity_assessment": _normalized_text(
            parsed.get("external_validity_assessment")
        ),
        "screening_cost_usd": 0.0,
        "extraction_cost_usd": float(usage.get("total_cost_usd") or 0.0),
        "token_count_prompt": int(usage.get("prompt_tokens") or 0),
        "token_count_completion": int(usage.get("completion_tokens") or 0),
    }


class _SlidingWindowLimiter:
    def __init__(self, max_requests: int, window: float = 1.0) -> None:
        self._max = max(1, int(max_requests))
        self._window = float(window)
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and self._timestamps[0] <= now - self._window:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                wait = self._timestamps[0] + self._window - now
            await asyncio.sleep(max(0.01, wait))


class GonkaChatClient:
    """OpenAI-compatible client using Gonka API pattern from lex batch."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        max_concurrent: int,
        rate_limit_rps: float,
        max_retries: int,
        disable_json_mode: bool = False,
        timeout_seconds: int = 120,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._session: aiohttp.ClientSession | None = None
        self._sem = asyncio.Semaphore(max(1, int(max_concurrent)))
        self._limiter = _SlidingWindowLimiter(max(1, int(rate_limit_rps)), window=1.0)
        self._max_retries = max(1, int(max_retries))
        self._disable_json_mode = disable_json_mode
        self._timeout = aiohttp.ClientTimeout(total=max(10, int(timeout_seconds)))

    async def __aenter__(self) -> GonkaChatClient:
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def chat(
        self,
        *,
        model: str,
        temperature: float,
        prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert self._session is not None, "Use async context manager"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if not self._disable_json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        not_found_retries = 0
        for attempt in range(1, self._max_retries + 1):
            async with self._sem:
                await self._limiter.acquire()
                try:
                    async with self._session.post(self._url, json=payload) as resp:
                        body = await resp.text()
                        if resp.status == 200:
                            data = json.loads(body)
                            if not isinstance(data, dict):
                                data = {}
                            content = ""
                            choices = data.get("choices")
                            if isinstance(choices, list) and choices:
                                first = choices[0]
                                if isinstance(first, dict):
                                    msg = first.get("message")
                                    if isinstance(msg, dict):
                                        content = str(msg.get("content") or "")
                            parsed = _parse_json_object(content) or {}
                            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                            return parsed, usage

                        if resp.status == 404:
                            not_found_retries += 1
                            if not_found_retries > 2:
                                raise RuntimeError(
                                    f"Gonka HTTP 404 (model not found) after {not_found_retries} attempts: {body[:300]}"
                                )
                            await asyncio.sleep(1.0)
                            continue
                        if resp.status in {429, 500, 502, 503, 504}:
                            await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 20.0))
                            continue

                        # Retry once without JSON mode for compatibility.
                        if resp.status == 400 and "response_format" in payload:
                            payload.pop("response_format", None)
                            await asyncio.sleep(0.05)
                            continue

                        raise RuntimeError(f"Gonka HTTP {resp.status}: {body[:300]}")
                except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as exc:
                    last_error = exc
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 20.0))

        raise RuntimeError("Gonka request failed after retries") from last_error


@dataclass
class ExtractorStats:
    """Extractor stats public type."""

    total_seen: int = 0
    skipped: int = 0
    screening_rejected: int = 0
    no_fulltext: int = 0
    extracted: int = 0
    extraction_errors: int = 0
    cached_skipped: int = 0
    total_screening_cost_usd: float = 0.0
    total_extraction_cost_usd: float = 0.0
    total_tokens_prompt: int = 0
    total_tokens_completion: int = 0
    new_canonical_names: int = 0
    elapsed_seconds: float = 0.0


class PolicyArticleExtractor:
    """Policy article extractor public type."""

    def __init__(
        self,
        *,
        screening_model: str,
        extraction_model: str,
        max_concurrent: int,
        canonizer: VariableCanonizer,
        gonka_client: GonkaChatClient,
        fulltext_timeout_seconds: int,
        cache_path: Path,
        resolved_texts: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.screening_model = screening_model
        self.extraction_model = extraction_model
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self._canonizer = canonizer
        self._gonka = gonka_client
        self._fulltext_timeout_seconds = max(3, int(fulltext_timeout_seconds))
        self._cache_path = cache_path
        self._processed_cache = self._load_processed_cache(cache_path)
        self._resolved_texts = resolved_texts or {}

    @staticmethod
    def _load_processed_cache(cache_path: Path) -> set[str]:
        if not cache_path.exists():
            return set()
        cache: set[str] = set()
        with open(cache_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = row.get("cache_key")
                if isinstance(key, str) and key:
                    cache.add(key)
        return cache

    def _append_cache_key(self, cache_key: str, openalex_id: str) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "cache_key": cache_key,
                        "openalex_id": openalex_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        self._processed_cache.add(cache_key)

    @staticmethod
    def _cache_key_for_work(work: dict[str, Any]) -> str:
        openalex_id = str(work.get("id") or "")
        doi = str(work.get("doi") or "")
        payload = f"{doi.strip().lower()}|{openalex_id.strip().lower()}"
        if payload == "|":
            payload = json.dumps(work, sort_keys=True, ensure_ascii=False)
        return content_hash(payload, prefix=True)

    @staticmethod
    def _reconstruct_abstract(work: dict[str, Any]) -> str:
        return reconstruct_abstract(work)

    async def _screen(self, abstract: str, stats: ExtractorStats) -> bool:
        prompt = SCREENING_PROMPT.format(abstract=abstract[:6000])
        parsed, usage = await self._gonka.chat(
            model=self.screening_model,
            temperature=0.0,
            prompt=prompt,
        )
        stats.total_tokens_prompt += int(usage.get("prompt_tokens") or 0)
        stats.total_tokens_completion += int(usage.get("completion_tokens") or 0)
        stats.total_screening_cost_usd += float(usage.get("total_cost_usd") or 0.0)
        return bool(parsed.get("relevant", False))

    async def _fetch_full_text(self, work: dict[str, Any]) -> tuple[str, str]:
        """Return (text, source_kind). source_kind in {fulltext_html, fulltext_pdf, abstract_fallback}.

        Retries up to 2 times with exponential backoff for transient HTTP
        failures (429 rate limit, 5xx server errors, timeouts).  Falls back
        to abstract if all retries fail.
        """
        import asyncio as _asyncio

        max_retries = 2
        base_delay = 2.0  # seconds

        for attempt in range(max_retries + 1):
            try:
                text, source_kind, _source_url = await fetch_full_text_for_work(
                    work,
                    timeout_seconds=self._fulltext_timeout_seconds,
                )
                # If we got actual fulltext, return immediately
                if source_kind != "abstract_fallback" and text.strip():
                    return text, source_kind
                # Abstract fallback on first attempt — still retry if we can
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    await _asyncio.sleep(delay)
                    continue
                return text, source_kind
            except Exception:
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    await _asyncio.sleep(delay)
                    continue
                # Final attempt failed — fall through to abstract
                break

        # All retries exhausted — return abstract fallback
        abstract = self._reconstruct_abstract(work)
        return abstract or "", "abstract_fallback"

    async def _extract(
        self,
        work: dict[str, Any],
        text: str,
        source_kind: str,
        stats: ExtractorStats,
    ) -> ArticleExtractionResult | None:
        abstract = self._reconstruct_abstract(work)
        evidence_bundle = _build_evidence_bundle(
            title=str(work.get("title") or ""),
            abstract=abstract,
            text=text,
            source_kind=source_kind,
        )
        extraction_prompt = f"""
Extract policy-relevant empirical evidence from the evidence bundle.
Return strict JSON with keys:
- empirical_parameters
- causal_claims
- mechanisms
- boundary_conditions
- methodology
- methodology_enum
- sample_size
- citation_summary
- extraction_confidence
- extraction_warnings

{EMPIRICAL_PARAMETERS_SCHEMA_HINT}
{CAUSAL_CLAIMS_SCHEMA_HINT}
{MECHANISMS_SCHEMA_HINT}
{BOUNDARY_CONDITIONS_SCHEMA_HINT}

Rules:
- Return JSON only.
- Use null for unavailable numeric values.
- Never place words like high, medium, low in numeric fields.
- If a value is qualitative, put it in value_qualitative instead of value.
- For empirical_parameters, extract coefficients/effect sizes only; never use p-values,
  significance stars, sample sizes, or test statistics as the main numeric value.
- If a quantitative estimate is dimensionless, set unit explicitly to a conservative
  label like unitless, elasticity, odds_ratio, risk_ratio, correlation_coefficient,
  standardized_effect, index_points, or percentage_points.
- sample_size must be an integer or null.
- Every causal claim must include at least one supporting span.
- Be conservative about design_family_hint.
- If the evidence bundle only contains abstract sentences, do not imply strong causal validity.

Evidence bundle:
{json.dumps(evidence_bundle, ensure_ascii=False)}
""".strip()

        parsed, usage = await self._gonka.chat(
            model=self.extraction_model,
            temperature=0.0,
            prompt=extraction_prompt,
        )

        stats.total_tokens_prompt += int(usage.get("prompt_tokens") or 0)
        stats.total_tokens_completion += int(usage.get("completion_tokens") or 0)
        stats.total_extraction_cost_usd += float(usage.get("total_cost_usd") or 0.0)

        try:
            result = ArticleExtractionResult.model_validate(
                _normalize_extraction_payload(
                    work,
                    parsed,
                    self.extraction_model,
                    usage,
                    evidence_bundle=evidence_bundle,
                    source_kind=evidence_bundle["source_kind"],
                )
            )
            return result
        except Exception as exc:
            logger.warning("article extraction parse failed for {}: {}", work.get("id"), exc)
            stats.extraction_errors += 1
            return None

    async def _self_verify(
        self,
        result: ArticleExtractionResult,
        evidence_bundle: dict[str, Any],
        stats: ExtractorStats,
    ) -> ArticleExtractionResult:
        """Quick LLM verification pass: check that extracted claims are grounded.

        Uses a cheap model call to verify the top claims actually match the
        source text.  Adjusts claim_extraction_confidence downward for claims
        flagged as unsupported.  Adds extraction_warnings when issues found.
        """
        if not result.causal_claims:
            return result

        # Only verify top 5 claims to keep cost low
        claims_to_verify = result.causal_claims[:5]
        claim_summaries = []
        for i, claim in enumerate(claims_to_verify):
            claim_summaries.append(
                f"Claim {i + 1}: {claim.cause_variable} -> {claim.effect_variable} "
                f"(direction={claim.direction.value}, "
                f"effect_size={claim.effect_size}, "
                f"design={claim.design_family_hint.value})"
            )
        claims_block = "\n".join(claim_summaries)

        verification_prompt = f"""
You are verifying extracted causal claims against source text.
For each claim, check:
1. Does the source text actually support this cause-effect relationship?
2. Is the direction (positive/negative) correct given the source?
3. Is the effect_size plausible (not a p-value or sample size)?
4. Is the design_family_hint consistent with the methodology described?

Return strict JSON: {{"verifications": [
  {{"claim_index": 1, "supported": true|false, "confidence_adjustment": <number -0.3..0>, "issue": "short description or null"}}
]}}

Rules:
- confidence_adjustment should be 0 for correctly extracted claims.
- For minor issues (slightly wrong direction, imprecise effect size): -0.1
- For major issues (claim not in text, wrong variables, p-value as effect): -0.2 to -0.3
- JSON only.

Extracted claims:
{claims_block}

Source title: {evidence_bundle.get("title", "")}
Source text (first 3000 chars):
{str(evidence_bundle.get("text", ""))[:3000]}
""".strip()

        try:
            parsed, usage = await self._gonka.chat(
                model=self.screening_model,  # use cheap model
                temperature=0.0,
                prompt=verification_prompt,
            )
            stats.total_tokens_prompt += int(usage.get("prompt_tokens") or 0)
            stats.total_tokens_completion += int(usage.get("completion_tokens") or 0)
        except Exception:
            return result  # verification failure is non-fatal

        verifications = parsed.get("verifications") if isinstance(parsed, dict) else None
        if not isinstance(verifications, list):
            return result

        updated_claims = list(result.causal_claims)
        for v in verifications:
            if not isinstance(v, dict):
                continue
            idx = int(v.get("claim_index", 0)) - 1  # 1-indexed → 0-indexed
            if 0 <= idx < len(updated_claims):
                adjustment = max(-0.3, min(0.0, float(v.get("confidence_adjustment", 0))))
                issue = v.get("issue")
                claim = updated_claims[idx]
                _cc = claim.claim_extraction_confidence
                _rc = result.extraction_confidence
                old_conf = float(_cc if _cc is not None else (_rc if _rc is not None else 0.5))
                new_conf = max(0.05, old_conf + adjustment)
                warnings = list(claim.extraction_warnings)
                if issue and not v.get("supported", True):
                    warnings.append(f"verification_issue: {str(issue)[:100]}")
                updated_claims[idx] = claim.model_copy(
                    update={
                        "claim_extraction_confidence": round(new_conf, 4),
                        "extraction_warnings": sorted(set(warnings)),
                    }
                )

        return result.model_copy(update={"causal_claims": updated_claims})

    def _canonize_variables(
        self, result: ArticleExtractionResult, stats: ExtractorStats
    ) -> ArticleExtractionResult:
        canonized_claims = []
        for claim in result.causal_claims:
            cause, cause_new = self._canonizer.canonize(claim.cause_variable)
            effect, effect_new = self._canonizer.canonize(claim.effect_variable)
            stats.new_canonical_names += int(cause_new) + int(effect_new)
            canonized_claims.append(
                claim.model_copy(
                    update={
                        "claim_id": stable_claim_id(
                            work_id=result.openalex_id,
                            cause=cause,
                            effect=effect,
                            claim_text=claim.claim_text,
                            direction=claim.direction.value,
                            supporting_span_ids=tuple(claim.supporting_span_ids),
                        ),
                        "cause_variable": cause,
                        "effect_variable": effect,
                    }
                )
            )

        canonized_params = []
        for parameter in result.empirical_parameters:
            name, is_new = self._canonizer.canonize(parameter.name)
            stats.new_canonical_names += int(is_new)
            canonized_params.append(parameter.model_copy(update={"name": name}))

        canonized_mechanisms = []
        for mechanism in result.mechanisms:
            mediators: list[str] = []
            for mediator in mechanism.mediating_variables:
                canonical_mediator, is_new = self._canonizer.canonize(mediator)
                stats.new_canonical_names += int(is_new)
                mediators.append(canonical_mediator)
            canonized_mechanisms.append(
                mechanism.model_copy(update={"mediating_variables": mediators})
            )

        canonized_boundaries = []
        for boundary in result.boundary_conditions:
            if boundary.variable:
                canonical_var, is_new = self._canonizer.canonize(boundary.variable)
                stats.new_canonical_names += int(is_new)
                canonized_boundaries.append(boundary.model_copy(update={"variable": canonical_var}))
            else:
                canonized_boundaries.append(boundary)

        return result.model_copy(
            update={
                "causal_claims": canonized_claims,
                "empirical_parameters": canonized_params,
                "mechanisms": canonized_mechanisms,
                "boundary_conditions": canonized_boundaries,
            }
        )

    async def _process_one(
        self, work: dict[str, Any], stats: ExtractorStats
    ) -> ArticleExtractionResult | None:
        async with self._semaphore:
            cache_key = self._cache_key_for_work(work)
            if cache_key in self._processed_cache:
                stats.cached_skipped += 1
                return None

            abstract = self._reconstruct_abstract(work)
            if abstract:
                relevant = await self._screen(abstract, stats)
                if not relevant:
                    stats.screening_rejected += 1
                    return None

            resolved = self._resolved_texts.get(str(work.get("id") or ""))
            if resolved:
                full_text = _normalized_text(resolved.get("text"))
                source_kind = str(resolved.get("source_kind") or "abstract_fallback")
            else:
                full_text, source_kind = await self._fetch_full_text(work)
            if not full_text.strip():
                stats.no_fulltext += 1
                return None

            result = await self._extract(work, full_text, source_kind, stats)
            if result is None:
                return None

            # Self-verification: cheap LLM pass to check claims match source
            if result.causal_claims:
                evidence_bundle = _build_evidence_bundle(
                    title=str(work.get("title") or ""),
                    abstract=self._reconstruct_abstract(work),
                    text=full_text,
                    source_kind=source_kind,
                )
                result = await self._self_verify(result, evidence_bundle, stats)

            if source_kind == "abstract_fallback":
                _STRONG_ABSTRACT_DESIGNS = frozenset(
                    {
                        DesignFamily.RCT,
                        DesignFamily.IV,
                        DesignFamily.DID,
                        DesignFamily.RDD,
                        DesignFamily.SYNTHETIC_CONTROL,
                    }
                )
                has_strong_design = any(
                    c.design_family_hint in _STRONG_ABSTRACT_DESIGNS for c in result.causal_claims
                )
                confidence_multiplier = 1.0 if has_strong_design else 0.8
                downgraded_claims = [
                    claim.model_copy(
                        update={
                            "source_basis": SourceBasis.ABSTRACT_ONLY,
                            "extraction_warnings": sorted(
                                {*claim.extraction_warnings, "abstract_only_fallback"}
                            ),
                        }
                    )
                    for claim in result.causal_claims
                ]
                result = result.model_copy(
                    update={
                        "extraction_confidence": max(
                            0.1, result.extraction_confidence * confidence_multiplier
                        ),
                        "source_basis": SourceBasis.ABSTRACT_ONLY,
                        "text_quality": TextQuality.ABSTRACT_ONLY,
                        "causal_claims": downgraded_claims,
                        "extraction_warnings": sorted(
                            {*result.extraction_warnings, "abstract_only_fallback"}
                        ),
                        "citation_summary": (
                            (result.citation_summary + " ").strip() + "[fallback:abstract_only]"
                        ).strip(),
                    }
                )

            result = self._canonize_variables(result, stats)
            result = result.model_copy(
                update={"source_context": infer_context_from_article(work, result)}
            )
            self._append_cache_key(cache_key, result.openalex_id)

            stats.extracted += 1
            return result

    async def process_batch(
        self,
        works: list[dict[str, Any]],
        *,
        domain_filter: list[str] | None = None,
        min_citations: int = 10,
    ) -> tuple[list[ArticleExtractionResult], ExtractorStats]:
        started = time.monotonic()
        stats = ExtractorStats()
        accepted: list[tuple[int, dict[str, Any]]] = []

        for index, work in enumerate(works):
            stats.total_seen += 1
            keep, _ = should_process(work, domain_filter=domain_filter, min_citations=min_citations)
            if not keep:
                stats.skipped += 1
                continue
            accepted.append((index, work))

        async def _run_one(
            index: int, work: dict[str, Any]
        ) -> tuple[int, ArticleExtractionResult | None]:
            return index, await self._process_one(work, stats)

        indexed_results: list[tuple[int, ArticleExtractionResult]] = []
        tasks = [asyncio.create_task(_run_one(index, work)) for index, work in accepted]
        for task in asyncio.as_completed(tasks):
            index, result = await task
            if result is not None:
                indexed_results.append((index, result))

        indexed_results.sort(key=lambda item: item[0])
        results = [result for _, result in indexed_results]

        stats.elapsed_seconds = time.monotonic() - started
        return results, stats


def _safe_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def serialize_rich_claim_occurrence_vocabulary(
    claim: CausalClaim,
    *,
    record_extraction_mode: str | None,
    record_extraction_confidence: float | None = None,
) -> ClaimOccurrenceVocabularyTransport:
    """Build the lossless v2 composite emitted for one rich extracted claim.

    The record confidence is deliberately accepted only to make its exclusion
    explicit: missing claim confidence remains absent rather than borrowing a
    paper-level observation.
    """

    del record_extraction_confidence
    fields_set = claim.model_fields_set

    def _candidate_axis(field_name: str, value: Any) -> tuple[Any | None, ClaimVocabularyAxisStatus]:
        if field_name not in fields_set:
            return None, ClaimVocabularyAxisStatus.NOT_ESTABLISHED
        return value, ClaimVocabularyAxisStatus.CANDIDATE

    design_family_hint, design_family_hint_status = _candidate_axis(
        "design_family_hint", claim.design_family_hint
    )
    evidence_strength, evidence_strength_status = _candidate_axis(
        "evidence_strength", claim.evidence_strength
    )
    source_basis, source_basis_status = _candidate_axis("source_basis", claim.source_basis)
    retained = claim.model_dump(mode="json")
    retained.pop("cause_variable")
    retained.pop("effect_variable")
    retained.pop("design_family_hint")
    retained.pop("evidence_strength")
    retained.pop("claim_extraction_confidence")
    retained.pop("source_basis")
    retained["cause"] = claim.cause_variable
    retained["effect"] = claim.effect_variable
    retained["direction"] = claim.direction.value
    retained["mechanism"] = claim.counterevidence_notes
    return ClaimOccurrenceVocabularyTransport(
        occurrence=retained,
        vocabulary=VersionedClaimVocabularyEnvelope(
            cause=claim.cause_variable,
            effect=claim.effect_variable,
            direction=claim.direction.value,
            mechanism=claim.counterevidence_notes,
            design_family_hint=design_family_hint,
            design_family_hint_status=design_family_hint_status,
            evidence_strength=evidence_strength,
            evidence_strength_status=evidence_strength_status,
            claim_extraction_confidence=claim.claim_extraction_confidence,
            claim_extraction_confidence_status=(
                ClaimVocabularyAxisStatus.CANDIDATE
                if claim.claim_extraction_confidence is not None
                else ClaimVocabularyAxisStatus.NOT_ESTABLISHED
            ),
            source_basis=source_basis,
            source_basis_status=source_basis_status,
            record_extraction_mode=record_extraction_mode,
        ),
    )


def _to_work_record(
    *,
    result: ArticleExtractionResult,
    raw_work: dict[str, Any],
    topic_ids: list[str],
    topic_display_names: list[str],
    run_id: str,
    pass_name: str,
) -> WorkRecord:
    paper_trust_score = compute_trust_score(
        study_design=str(result.methodology or ""),
        cited_by_count=int(result.cited_by_count or 0),
        publication_year=int(result.year or 2000),
        sample_size=result.sample_size,
    )
    estimates: list[EstimateCandidate] = []
    for parameter in result.empirical_parameters:
        value = parameter.value
        if value is None and parameter.value_range is not None:
            lo, hi = parameter.value_range
            value = (float(lo) + float(hi)) / 2.0
        if value is None:
            continue
        estimates.append(
            EstimateCandidate(
                value=float(value),
                ci_low=(
                    _safe_float(parameter.confidence_interval[0])
                    if parameter.confidence_interval is not None
                    else None
                ),
                ci_high=(
                    _safe_float(parameter.confidence_interval[1])
                    if parameter.confidence_interval is not None
                    else None
                ),
                std_error=_safe_float(parameter.std_error),
                unit=str(parameter.unit or ""),
                context_snippet=str(parameter.heterogeneity_note or ""),
                pattern_name="resolve_extract",
                confidence=float(result.extraction_confidence),
                variable_hint=parameter.name,
            )
        )

    causal_claims = [
        serialize_rich_claim_occurrence_vocabulary(
            claim,
            record_extraction_mode="resolve_extract",
            record_extraction_confidence=result.extraction_confidence,
        )
        for claim in result.causal_claims
    ]

    boundary_conditions = [
        {
            "variable": boundary.variable,
            "operator": boundary.operator,
            "threshold_value": str(boundary.required_value or boundary.threshold_value or ""),
            "scope_text": boundary.scope_text,
            "confidence": boundary.confidence,
            "condition_type": boundary.condition_type,
            "consequence_if_violated": boundary.consequence_if_violated,
        }
        for boundary in result.boundary_conditions
    ]

    topic_refs: list[SourceTopicRef] = []
    for index, topic_id in enumerate(topic_ids):
        topic_refs.append(
            SourceTopicRef(
                topic_id=str(topic_id),
                topic_display_name=(
                    topic_display_names[index]
                    if index < len(topic_display_names)
                    else str(topic_id)
                ),
                rank=0,
                selection_score=0.0,
                batch_origin="resolve_extract",
                selected_at=datetime.now(UTC).isoformat(),
            )
        )

    abstract = str(raw_work.get("abstract") or "").strip()
    if not abstract:
        abstract = PolicyArticleExtractor._reconstruct_abstract(raw_work)

    return WorkRecord(
        id=result.openalex_id,
        title=result.title,
        doi=result.doi,
        abstract=abstract,
        year=result.year,
        publication_date=str(raw_work.get("publication_date") or ""),
        language=str(raw_work.get("language") or ""),
        work_type=str(raw_work.get("type") or ""),
        is_retracted=bool(raw_work.get("is_retracted") or False),
        cited_by_count=result.cited_by_count,
        fwci=float(raw_work.get("fwci"))
        if isinstance(raw_work.get("fwci"), (int, float))
        else None,
        citation_normalized_percentile=None,
        citation_is_top_1_percent=False,
        citation_is_top_10_percent=False,
        journal="",
        source_id="",
        is_oa=bool(
            (raw_work.get("open_access") or {}).get("is_oa")
            if isinstance(raw_work.get("open_access"), dict)
            else False
        ),
        has_fulltext=bool(raw_work.get("has_fulltext") or False),
        full_text_url=str(
            (
                (raw_work.get("open_access") or {}).get("oa_url")
                if isinstance(raw_work.get("open_access"), dict)
                else ""
            )
            or ""
        ),
        concepts=list(raw_work.get("topics") or []),
        source_topics=topic_refs,
        study_design=str(result.methodology or ""),
        trust_score=float(paper_trust_score),
        estimates=estimates,
        causal_claims=causal_claims,
        boundary_conditions=boundary_conditions,
        context_profile=result.source_context.model_dump(mode="json")
        if result.source_context
        else {},
        extraction_mode="resolve_extract",
        extraction_confidence=float(result.extraction_confidence),
        method_signal_score=float(result.extraction_confidence),
        token_count_prompt=int(result.token_count_prompt),
        token_count_completion=int(result.token_count_completion),
        screening_cost_usd=float(result.screening_cost_usd),
        extraction_cost_usd=float(result.extraction_cost_usd),
        metadata={
            "sample_size": result.sample_size,
            "run_id": run_id,
            "pass_name": pass_name,
            "resolve_extract": True,
            "paper_trust_score": paper_trust_score,
            "claim_extraction_confidence": float(result.extraction_confidence),
            "source_basis": result.source_basis.value,
            "text_quality": result.text_quality.value,
            "supporting_spans": [span.model_dump(mode="json") for span in result.supporting_spans],
            "method_spans": [span.model_dump(mode="json") for span in result.method_spans],
            "extraction_warnings": list(result.extraction_warnings),
            "paper_relevance": bool(result.paper_relevance),
            "paper_relevance_reason": result.paper_relevance_reason,
            "paper_kind": result.paper_kind.value,
            "heterogeneity_results": [
                item.model_dump(mode="json") for item in result.heterogeneity_results
            ],
            "external_validity_assessment": result.external_validity_assessment,
            "provider_finish_reason": result.provider_finish_reason,
            "provider_latency_ms": result.provider_latency_ms,
            "truncated_output": bool(result.truncated_output),
            "llm_error_class": result.llm_error_class,
            "context_attributes": [
                attr.model_dump(mode="json") for attr in result.context_attributes
            ],
            "moderation_edges": [edge.model_dump(mode="json") for edge in result.moderation_edges],
            "reconciliation_diagnostics": dict(result.reconciliation_diagnostics),
        },
    )


def _load_selected_works(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _load_resolved_texts(path: Path) -> dict[str, dict[str, Any]]:
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
            work_id = str(row.get("work_id") or "")
            if work_id:
                rows[work_id] = row
    return rows


async def run_article_extract(config: AcademicBatchConfig) -> dict[str, float | int]:
    """Compatibility wrapper for the clean-cut resolve_extract stage."""
    from polisyos.data_forge.domains.academic.batch.resolve_extract import run_resolve_extract

    return await run_resolve_extract(config)


__all__ = ["ExtractorStats", "PolicyArticleExtractor", "run_article_extract"]
