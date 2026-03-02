"""Boundary-condition extraction schema hint."""

from __future__ import annotations

BOUNDARY_CONDITIONS_SCHEMA_HINT = """
"boundary_conditions": [{
  "variable": "context variable",
  "condition_type": "threshold|categorical|ordinal",
  "required_value": "string or number",
  "consequence_if_violated": "short consequence",
  "scope_text": "optional raw evidence"
}]
""".strip()

__all__ = ["BOUNDARY_CONDITIONS_SCHEMA_HINT"]
