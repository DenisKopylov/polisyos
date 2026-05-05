"""Mechanism extraction schema hint."""

from __future__ import annotations

MECHANISMS_SCHEMA_HINT = """
"mechanisms": [{
  "description": "concise description of HOW the cause produces the effect (the causal pathway)",
  "mediating_variables": ["canonical-like variable names for intermediate steps in the causal chain"],
  "evidence_type": "laboratory|natural_experiment|survey|mixed",
  "theoretical_framework": "named economic/social theory if mentioned (e.g. Keynesian multiplier, human capital theory)"
}]

Rules:
- Extract the causal PATHWAY, not just the cause and effect (those are in causal_claims).
- mediating_variables are the INTERMEDIATE steps: if X causes Y through Z, then Z is the mediator.
- Do NOT confuse mediators (intermediate steps) with moderators (conditions that change the effect size).
- Evidence_type refers to how the mechanism was identified, not the main study design.
- If the paper only speculates about mechanisms without evidence, still extract but set evidence_type to the weakest applicable category.

Example:
Paper says: "The tax cut increased consumer spending, which in turn boosted employment through increased labor demand. This is consistent with standard Keynesian demand-side theory."
{
  "description": "Tax cuts increase disposable income, raising consumer spending, which increases firm revenue and labor demand, leading to higher employment",
  "mediating_variables": ["consumer_spending", "labor_demand"],
  "evidence_type": "natural_experiment",
  "theoretical_framework": "Keynesian demand-side multiplier"
}
""".strip()

__all__ = ["MECHANISMS_SCHEMA_HINT"]
