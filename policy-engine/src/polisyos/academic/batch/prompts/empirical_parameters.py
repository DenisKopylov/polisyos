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
- "sample_size" must be an integer or null.
- "extraction_confidence" must be a numeric value in [0,1], never words like high/medium/low.
""".strip()

__all__ = ["EMPIRICAL_PARAMETERS_SCHEMA_HINT"]
