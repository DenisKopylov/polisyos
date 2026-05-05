"""Confidence fusion helpers for Lex SPO facts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FusedConfidence:
    """Fused confidence public type."""

    extraction_confidence: float
    grounding_confidence: float
    structural_confidence: float
    verification_confidence: float
    fused_score: float
    confidence_breakdown: dict[str, float]

    def breakdown_json(self) -> str:
        return json.dumps(self.confidence_breakdown, ensure_ascii=False, sort_keys=True)


GROUNDING_SCORES = {
    "exact_quote": 1.0,
    "quote_without_offsets": 0.7,
    "offsets_without_quote": 0.5,
    "missing_quote": 0.2,
}
STRUCTURE_SCORES = {
    "full": 1.0,
    "full_only": 0.8,
    "structured_legal_unit": 0.95,
    "article": 0.95,
    "part": 0.9,
    "point": 0.88,
    "fallback_chunk": 0.5,
    "fallback_search_only": 0.3,
    "raw_text": 0.3,
}
SOURCE_MODIFIER = {
    "rule_auto": 1.05,
    "llm": 1.0,
    "audit_llm": 0.97,
    "llm_gap_fill": 0.9,
    "deferred": 0.7,
    "llm_timeout_fallback": 0.7,
    "llm_gap_fill_timeout_fallback": 0.68,
    "audit_llm_timeout_fallback": 0.68,
    "dedup_clone": 0.98,
}


def compute_fused_confidence(
    *,
    extraction_conf: float,
    grounding_status: str,
    structural_quality: str,
    verification_conf: float | None,
    extraction_source: str,
) -> FusedConfidence:
    """Compute fused confidence helper."""
    grounding_conf = GROUNDING_SCORES.get(grounding_status, 0.1)
    structural_conf = STRUCTURE_SCORES.get(
        structural_quality, STRUCTURE_SCORES["structured_legal_unit"]
    )
    verify_conf = (
        extraction_conf if verification_conf is None else max(0.0, min(1.0, verification_conf))
    )
    source_mod = SOURCE_MODIFIER.get(extraction_source, 1.0)
    components = [
        max(0.01, min(1.0, extraction_conf)),
        max(0.01, min(1.0, grounding_conf)),
        max(0.01, min(1.0, structural_conf)),
        max(0.01, min(1.0, verify_conf)),
    ]
    geometric_mean = math.prod(components) ** (1.0 / len(components))
    fused = min(1.0, max(0.0, geometric_mean * source_mod))
    return FusedConfidence(
        extraction_confidence=round(extraction_conf, 4),
        grounding_confidence=round(grounding_conf, 4),
        structural_confidence=round(structural_conf, 4),
        verification_confidence=round(verify_conf, 4),
        fused_score=round(fused, 4),
        confidence_breakdown={
            "extraction": round(extraction_conf, 4),
            "grounding": round(grounding_conf, 4),
            "structural": round(structural_conf, 4),
            "verification": round(verify_conf, 4),
            "source_modifier": round(source_mod, 4),
        },
    )


def quality_band_for_score(score: float) -> str:
    """Quality band for score helper."""
    if score >= 0.85:
        return "high_confidence_norm"
    if score >= 0.65:
        return "normative_ready"
    if score >= 0.45:
        return "grounded_ready"
    return "low_confidence"
