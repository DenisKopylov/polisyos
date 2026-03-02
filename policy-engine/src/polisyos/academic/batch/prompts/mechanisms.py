"""Mechanism extraction schema hint."""

from __future__ import annotations

MECHANISMS_SCHEMA_HINT = """
"mechanisms": [{
  "description": "short mechanism text",
  "mediating_variables": ["canonical-like variable"],
  "evidence_type": "laboratory|natural_experiment|survey|mixed",
  "theoretical_framework": "optional"
}]
""".strip()

__all__ = ["MECHANISMS_SCHEMA_HINT"]
