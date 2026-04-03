"""Public legal evaluation backends package API."""
from __future__ import annotations

from .simple_v1 import RuleFinding, evaluate_rule_simple_v1

__all__ = [
    "RuleFinding",
    "evaluate_rule_simple_v1",
]
