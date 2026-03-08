"""Causal-claims extraction schema hint."""

from __future__ import annotations

CAUSAL_CLAIMS_SCHEMA_HINT = """
"causal_claims": [{
  "claim_id": "optional stable id",
  "claim_text": "short sentence-level statement from the paper",
  "cause_variable": "canonical-like name",
  "effect_variable": "canonical-like name",
  "direction": "positive|negative|null|mixed|ambiguous|non_linear",
  "claim_explicitness": "explicit|implicit|unclear",
  "design_family_hint": "rct|iv|did|rdd|synthetic_control|panel_fe|ols|meta_analysis|review|theoretical|unclear",
  "effect_size": <number|null>,
  "evidence_strength": "rct|quasi_natural|meta_analysis|observational|theoretical|unknown",
  "supporting_spans": [{
    "section": "abstract|methods|results|discussion|conclusion|claims",
    "text": "verbatim supporting sentence",
    "sentence_index": <integer|null>,
    "score": <number 0..1>
  }],
  "method_spans": [{
    "section": "methods|results|discussion",
    "text": "verbatim method/design sentence",
    "sentence_index": <integer|null>,
    "score": <number 0..1>
  }],
  "source_basis": "fulltext|abstract_only",
  "claim_extraction_confidence": <number|null>,
  "scope_conditions": ["..."],
  "counterevidence_notes": "...",
  "extraction_warnings": ["optional warning"]
}]
""".strip()

__all__ = ["CAUSAL_CLAIMS_SCHEMA_HINT"]
