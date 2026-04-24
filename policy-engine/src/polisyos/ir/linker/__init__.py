"""Public linker facade for Trinity binding results, reports, and norm-applicability validation."""

from __future__ import annotations

from .link_trinity import (
    LinkedIntervention,
    LinkedTrinityBundle,
    TrinityBindings,
    link_trinity,
)
from .reports import LinkIssue, LinkIssueCode, LinkReport, LinkSeverity
from .types import validate_norm_applicability_refs

__all__ = [
    "LinkIssue",
    "LinkIssueCode",
    "LinkReport",
    "LinkSeverity",
    "LinkedIntervention",
    "LinkedTrinityBundle",
    "TrinityBindings",
    "link_trinity",
    "validate_norm_applicability_refs",
]
