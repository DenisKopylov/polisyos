"""Empirical-parameter extraction schema hint."""

from __future__ import annotations

EMPIRICAL_PARAMETERS_SCHEMA_HINT = """
"empirical_parameters": [{
  "name": "canonical-like name",
  "display_name": "optional human-readable label",
  "parameter_type": "quantitative|qualitative|ordinal|distributional",
  "value": <number|null>,
  "value_range": [<number>, <number>] | null,
  "value_qualitative": "string|null",
  "confidence_interval": [<number>, <number>] | null,
  "std_error": <number|null>,
  "unit": "explicit unit (never null)",
  "evidence_strength": "rct|quasi_natural|meta_analysis|observational|theoretical|unknown",
  "geographic_scope": "optional geography",
  "time_period": "optional period",
  "aggregation_level": "optional aggregation (country|region|firm|household|individual)",
  "transferability": "optional transportability note",
  "transfer_conditions": ["optional condition"],
  "heterogeneity_note": "optional note on effect heterogeneity",
  "subgroup_estimates": {"group_name": <number>}
}]

Rules:
- Every item in "empirical_parameters" must be an object, never a bare string.
- Use "name", not "parameter" or "variable".
- If no numeric estimate is available, set "value" to null and put the textual statement in "value_qualitative".
- Only extract causal effect estimates or directly usable quantitative parameters.
- Never use p-values, significance stars, test statistics, sample sizes, or confidence levels as "value".
- If the estimate is unitless, still set "unit" explicitly. Prefer one of:
  "unitless", "elasticity", "semi_elasticity", "odds_ratio", "risk_ratio",
  "hazard_ratio", "correlation_coefficient", "standardized_effect",
  "index_points", "percentage_points".
- If the paper reports a coefficient/effect size but the scale is unclear, prefer
  a conservative explicit unit like "unitless" over null only when the paper
  clearly presents it as an effect estimate rather than a significance metric.
- "sample_size" must be an integer or null.
- "extraction_confidence" must be a numeric value in [0,1], never words like high/medium/low.
- When a paper reports "95% CI [0.12, 0.45]", extract confidence_interval as [0.12, 0.45] (the bounds, NOT the confidence level 0.95).
- When subgroup results are given (e.g. "effect is 0.15 for men, 0.08 for women"), extract subgroup_estimates: {"men": 0.15, "women": 0.08}.

GOOD example (RCT with full uncertainty):
{
  "name": "fiscal_multiplier",
  "display_name": "Government spending multiplier",
  "parameter_type": "quantitative",
  "value": 1.5,
  "confidence_interval": [1.1, 1.9],
  "std_error": 0.2,
  "unit": "unitless",
  "evidence_strength": "quasi_natural",
  "geographic_scope": "United States",
  "time_period": "2009-2012",
  "aggregation_level": "country",
  "subgroup_estimates": {"recession": 2.1, "expansion": 0.8}
}

GOOD example (elasticity):
{
  "name": "trade_openness_elasticity_gdp",
  "display_name": "Trade openness elasticity of GDP growth",
  "parameter_type": "quantitative",
  "value": 0.12,
  "confidence_interval": [0.05, 0.19],
  "std_error": 0.035,
  "unit": "elasticity",
  "evidence_strength": "quasi_natural",
  "geographic_scope": "Sub-Saharan Africa",
  "time_period": "1990-2018"
}

BAD example (extracts p-value as value):
{
  "name": "tax_effect",
  "value": 0.001,
  "unit": null
}
This is BAD because: 0.001 looks like a p-value not an effect size, unit is null instead of explicit.
""".strip()

__all__ = ["EMPIRICAL_PARAMETERS_SCHEMA_HINT"]
