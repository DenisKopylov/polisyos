"""Causal-claims extraction schema hint."""

from __future__ import annotations

CAUSAL_CLAIMS_SCHEMA_HINT = """
"causal_claims": [{
  "cause_variable": "canonical-like name",
  "effect_variable": "canonical-like name",
  "direction": "positive|negative|null|mixed|ambiguous|non_linear",
  "effect_size": <number|null>,
  "evidence_strength": "rct|quasi_natural|meta_analysis|observational|theoretical|unknown",
  "scope_conditions": ["..."],
  "counterevidence_notes": "..."
}]
""".strip()

__all__ = ["CAUSAL_CLAIMS_SCHEMA_HINT"]
