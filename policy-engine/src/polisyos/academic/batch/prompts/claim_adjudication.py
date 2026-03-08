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
  "publishable_edge": true,
  "adjudication_notes": "short rationale"
}
""".strip()


CLAIM_ADJUDICATION_PROMPT_VARIANTS = (
    "Be conservative. Do not upgrade observational language to credible causal evidence without explicit design support.",
    "Focus on identification strategy and whether the cited evidence justifies a causal edge in a production graph.",
    "Prefer abstention or weak credibility when the text lacks explicit causal identification or only reports associations.",
)


__all__ = ["CLAIM_ADJUDICATION_SCHEMA_HINT", "CLAIM_ADJUDICATION_PROMPT_VARIANTS"]
