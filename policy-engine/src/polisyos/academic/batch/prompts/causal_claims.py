"""Causal-claims extraction schema hint."""

from __future__ import annotations

CAUSAL_CLAIMS_SCHEMA_HINT = """
"causal_claims": [{
  "claim_id": "optional stable id",
  "claim_text": "short sentence-level statement from the paper",
  "cause_variable": "canonical-like name using underscores (e.g. minimum_wage, tax_rate, trade_openness)",
  "effect_variable": "canonical-like name using underscores (e.g. employment_rate, gdp_growth, inflation)",
  "direction": "positive|negative|null|mixed|ambiguous|non_linear",
  "claim_explicitness": "explicit|implicit|unclear",
  "design_family_hint": "rct|iv|did|rdd|synthetic_control|panel_fe|ols|meta_analysis|review|theoretical|unclear",
  "effect_size": <number|null>,
  "evidence_strength": "rct|quasi_natural|meta_analysis|observational|theoretical|unknown",
  "supporting_spans": [{
    "section": "abstract|methods|results|discussion|conclusion|claims",
    "text": "verbatim supporting sentence copied EXACTLY from source text",
    "sentence_index": <integer|null>,
    "score": <number 0..1>
  }],
  "method_spans": [{
    "section": "methods|results|discussion",
    "text": "verbatim method/design sentence copied EXACTLY from source text",
    "sentence_index": <integer|null>,
    "score": <number 0..1>
  }],
  "source_basis": "fulltext|abstract_only",
  "claim_extraction_confidence": <number|null>,
  "scope_conditions": ["population or geographic or temporal restriction on the claim"],
  "counterevidence_notes": "any caveats or contradictory findings mentioned by the paper",
  "extraction_warnings": ["optional warning"]
}]

Calibration guide for claim_extraction_confidence:
- 0.85-1.0: Clear explicit causal claim with strong design, verbatim spans found, numeric effect size
- 0.65-0.85: Causal claim with decent identification but some ambiguity in wording or missing numeric details
- 0.45-0.65: Implicit causal claim or weak design; claim is plausible but not strongly stated
- 0.20-0.45: Very uncertain extraction; claim may be over-interpreted from correlational language

GOOD extraction example (from a DiD paper):
{
  "claim_text": "The reform reduced informal employment by 4.2 percentage points",
  "cause_variable": "labor_market_reform",
  "effect_variable": "informal_employment_share",
  "direction": "negative",
  "claim_explicitness": "explicit",
  "design_family_hint": "did",
  "effect_size": -4.2,
  "evidence_strength": "quasi_natural",
  "supporting_spans": [{"section": "results", "text": "Column 3 of Table 2 shows that the reform reduced informal employment by 4.2 percentage points (SE = 1.1, p < 0.01) relative to the control group.", "sentence_index": 45, "score": 0.95}],
  "method_spans": [{"section": "methods", "text": "We employ a difference-in-differences strategy exploiting the staggered rollout of the reform across Mexican states between 2012 and 2016.", "sentence_index": 22, "score": 0.9}],
  "source_basis": "fulltext",
  "claim_extraction_confidence": 0.92,
  "scope_conditions": ["Mexico", "2012-2016", "formal sector workers"],
  "counterevidence_notes": "Authors note the effect is not significant for workers over 55."
}

BAD extraction (over-interprets correlational language):
{
  "claim_text": "Higher education spending is associated with better test scores",
  "cause_variable": "education_spending",
  "effect_variable": "test_scores",
  "direction": "positive",
  "design_family_hint": "ols",
  "effect_size": null,
  "evidence_strength": "observational",
  "claim_extraction_confidence": 0.35
}
This is BAD because: no effect size extracted, "associated" language → claim_explicitness should be "implicit" not omitted, design is OLS but confidence is too high for correlational finding.
""".strip()

__all__ = ["CAUSAL_CLAIMS_SCHEMA_HINT"]
