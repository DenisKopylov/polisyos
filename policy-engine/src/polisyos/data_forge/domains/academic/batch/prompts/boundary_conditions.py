"""Boundary-condition extraction schema hint."""

from __future__ import annotations

BOUNDARY_CONDITIONS_SCHEMA_HINT = """
"boundary_conditions": [{
  "variable": "context variable that must hold a specific value for the causal claim to apply",
  "condition_type": "threshold|categorical|ordinal",
  "required_value": "string or number describing the required condition",
  "consequence_if_violated": "what happens to the causal effect when this condition is NOT met",
  "scope_text": "verbatim evidence from the paper"
}]

Rules:
- Boundary conditions are PREREQUISITES for the causal effect to hold, NOT moderators.
- A moderator CHANGES the size of the effect; a boundary condition ENABLES or DISABLES it entirely.
- "threshold" = effect only exists above/below a numeric cutoff (e.g. "effect disappears below GDP $5000")
- "categorical" = effect only applies in specific categories (e.g. "only in democratic countries")
- "ordinal" = effect depends on being above/below a rank (e.g. "only in middle-income or higher")
- Always include scope_text with verbatim evidence when available.

Example:
Paper says: "The fiscal stimulus effect is only significant when the output gap is negative (recession), and disappears entirely during expansion periods. This holds specifically for countries with flexible exchange rate regimes."
[
  {"variable": "output_gap", "condition_type": "threshold", "required_value": "negative (recession)", "consequence_if_violated": "Fiscal multiplier becomes statistically insignificant during expansions", "scope_text": "The fiscal stimulus effect is only significant when the output gap is negative"},
  {"variable": "exchange_rate_regime", "condition_type": "categorical", "required_value": "flexible", "consequence_if_violated": "Effect not demonstrated for fixed exchange rate regimes", "scope_text": "This holds specifically for countries with flexible exchange rate regimes"}
]
""".strip()

__all__ = ["BOUNDARY_CONDITIONS_SCHEMA_HINT"]
