"""Facade for assembling jurisdiction- and date-scoped norm packs from corpus artifacts."""

from __future__ import annotations

from polisyos.lex.normpack.assemble_pack import assemble_norm_pack
from polisyos.lex.normpack.conflict_check import (
    build_policy_conflict_check_report,
    normalize_policy_conflict_check_report,
)
from polisyos.lex.normpack.legal_authority import (
    build_legal_authority_report,
    build_legal_authority_requirement_artifact,
)
from polisyos.lex.types import NormPackBudgets, NormPackBuildRequest, NormPackBuildResult

__all__ = [
    "NormPackBudgets",
    "NormPackBuildRequest",
    "NormPackBuildResult",
    "assemble_norm_pack",
    "build_legal_authority_report",
    "build_legal_authority_requirement_artifact",
    "build_policy_conflict_check_report",
    "normalize_policy_conflict_check_report",
]
