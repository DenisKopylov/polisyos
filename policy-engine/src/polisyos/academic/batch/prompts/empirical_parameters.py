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
  "unit": "optional unit",
  "evidence_strength": "rct|quasi_natural|meta_analysis|observational|theoretical|unknown",
  "geographic_scope": "optional geography",
  "time_period": "optional period",
  "aggregation_level": "optional aggregation",
  "transferability": "optional transportability note",
  "transfer_conditions": ["optional condition"],
  "heterogeneity_note": "optional note",
  "subgroup_estimates": {"group": <number>}
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
""".strip()

__all__ = ["EMPIRICAL_PARAMETERS_SCHEMA_HINT"]
