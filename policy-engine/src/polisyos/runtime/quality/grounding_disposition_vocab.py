"""Canonical grounding-disposition vocabulary shared by N4/N6 quality paths."""

from __future__ import annotations

from typing import Literal

GroundingDispositionKind = Literal[
    "shadow_bound",
    "veto_false_analog",
    "novel_cg3",
    "non_binding_abstain",
    "unknown_blocked",
]

__all__ = ["GroundingDispositionKind"]
