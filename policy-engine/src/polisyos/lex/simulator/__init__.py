"""Norm-pack diff and impact-simulation tools used after legal-evaluation outputs are available."""

from .diff import FieldDelta, NormChange, NormChangeType, NormDiff, diff_norm_packs
from .engine import NormImpactAnalyzer
from .mutator import MutationIntent, NormPackMutator
from .report import (
    AffectedKPI,
    ComplianceDelta,
    ComplianceTransition,
    NormImpactReport,
)

__all__ = [
    "AffectedKPI",
    "ComplianceDelta",
    "ComplianceTransition",
    "FieldDelta",
    "MutationIntent",
    "NormChange",
    "NormChangeType",
    "NormDiff",
    "NormImpactAnalyzer",
    "NormImpactReport",
    "NormPackMutator",
    "diff_norm_packs",
]
