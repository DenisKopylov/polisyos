"""Prompt fragments for claim-level causal adjudication."""

from __future__ import annotations

CLAIM_ADJUDICATION_SCHEMA_HINT = """
{
  "paper_asserts_causality_score": <number 0..1>,
  "claim_type": "causal_assertion|association|mechanism|descriptive|normative|review_summary",
  "design_family": "rct|iv|did|rdd|synthetic_control|panel_fe|ols|meta_analysis|review|theoretical|unclear",
  "causal_credibility": "strong|moderate|weak|not_causal|unclear",
  "risk_of_bias": "low|moderate|serious|critical|unclear",
  "support_status": "supported|mixed|counterevidence|insufficient",
  "claim_validity_score": <number 0..1>,
  "adjudication_confidence": <number 0..1>,
  "publishable_edge": true|false,
  "adjudication_notes": "short rationale"
}

Calibration guide for claim_validity_score:
- 0.85-1.0: Strong identification (RCT/IV/RDD), precise estimate, clear causal language, low risk of bias
- 0.65-0.85: Good quasi-experimental design (DiD, event study), reasonable identification assumptions
- 0.45-0.65: Panel FE or careful observational study with some causal ambiguity
- 0.25-0.45: OLS or cross-sectional with "suggestive" causal language; weak identification
- 0.00-0.25: Purely correlational, descriptive, or theoretical claims presented as causal

Adjudication examples:

Example 1 — STRONG (publish):
Claim: "The minimum wage increase reduced teen employment by 1.4 percentage points"
Design: did, Method span mentions "parallel trends test", Supporting span has "Table 3, column 4"
Result: {"paper_asserts_causality_score": 0.95, "claim_type": "causal_assertion", "design_family": "did", "causal_credibility": "strong", "risk_of_bias": "low", "support_status": "supported", "claim_validity_score": 0.88, "adjudication_confidence": 0.90, "publishable_edge": true, "adjudication_notes": "DiD with parallel trends verification, precise estimate with SE"}

Example 2 — WEAK (do not publish):
Claim: "Countries with higher trade openness tend to grow faster"
Design: ols, Method span: "OLS regression with country fixed effects"
Result: {"paper_asserts_causality_score": 0.3, "claim_type": "association", "design_family": "ols", "causal_credibility": "weak", "risk_of_bias": "serious", "support_status": "supported", "claim_validity_score": 0.30, "adjudication_confidence": 0.75, "publishable_edge": false, "adjudication_notes": "Associational language only, OLS without causal identification strategy"}

Example 3 — MODERATE (publish with caveats):
Claim: "The cash transfer program increased school enrollment by 8%"
Design: rct, source_basis: abstract_only
Result: {"paper_asserts_causality_score": 0.9, "claim_type": "causal_assertion", "design_family": "rct", "causal_credibility": "moderate", "risk_of_bias": "moderate", "support_status": "supported", "claim_validity_score": 0.72, "adjudication_confidence": 0.65, "publishable_edge": true, "adjudication_notes": "RCT with clear effect but abstract-only limits verification of implementation details"}
""".strip()


CLAIM_ADJUDICATION_PROMPT_VARIANTS = (
    "Be conservative. Do not upgrade observational language to credible causal evidence without explicit design support.",
    "Focus on identification strategy and whether the cited evidence justifies a causal edge in a production graph.",
    "Prefer abstention or weak credibility when the text lacks explicit causal identification or only reports associations.",
)


__all__ = ["CLAIM_ADJUDICATION_SCHEMA_HINT", "CLAIM_ADJUDICATION_PROMPT_VARIANTS"]
