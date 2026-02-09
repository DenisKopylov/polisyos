from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "ChangeProposalRef",
    "LegalDocSource",
    "LegalEvaluationRequest",
    "LegalReportRef",
    "LexError",
    "LexIndexError",
    "LexIngestError",
    "LexIngestOptions",
    "LexIngestResult",
    "LexNotReadyError",
    "LexStructureError",
    "LexStructureOptions",
    "LexStructureResult",
    "LexValidationError",
    "LexVersionIndexOptions",
    "LexVersionIndexResult",
    "LexVersioningError",
    "NormPackBuildRequest",
    "NormPackBuildResult",
    "NormPackBudgets",
    "MutationIntent",
    "NormPackMutator",
    "NormChangeType",
    "NormChange",
    "NormDiff",
    "NormImpactAnalyzer",
    "NormImpactReport",
    "ComplianceTransition",
    "ComplianceDelta",
    "AffectedKPI",
    "diff_norm_packs",
    "WorldEventRefLike",
    "assemble_norm_pack",
    "build_legal_structure",
    "build_version_index",
    "evaluate_legality",
    "ingest_legal_doc_bytes",
    "propose_changes",
    "resolve_active_version",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # contracts
    "ChangeProposalRef": ("polisyos.core.contracts.lex", "ChangeProposalRef"),
    "LegalEvaluationRequest": ("polisyos.core.contracts.lex", "LegalEvaluationRequest"),
    "LegalReportRef": ("polisyos.core.contracts.lex", "LegalReportRef"),
    # api
    "assemble_norm_pack": ("polisyos.lex.api", "assemble_norm_pack"),
    "build_legal_structure": ("polisyos.lex.api", "build_legal_structure"),
    "build_version_index": ("polisyos.lex.api", "build_version_index"),
    "evaluate_legality": ("polisyos.lex.api", "evaluate_legality"),
    "ingest_legal_doc_bytes": ("polisyos.lex.api", "ingest_legal_doc_bytes"),
    "propose_changes": ("polisyos.lex.api", "propose_changes"),
    "resolve_active_version": ("polisyos.lex.api", "resolve_active_version"),
    # errors
    "LexError": ("polisyos.lex.errors", "LexError"),
    "LexIndexError": ("polisyos.lex.errors", "LexIndexError"),
    "LexIngestError": ("polisyos.lex.errors", "LexIngestError"),
    "LexNotReadyError": ("polisyos.lex.errors", "LexNotReadyError"),
    "LexStructureError": ("polisyos.lex.errors", "LexStructureError"),
    "LexValidationError": ("polisyos.lex.errors", "LexValidationError"),
    "LexVersioningError": ("polisyos.lex.errors", "LexVersioningError"),
    # types
    "ActiveVersionResult": ("polisyos.lex.types", "ActiveVersionResult"),
    "ActiveVersionStrategy": ("polisyos.lex.types", "ActiveVersionStrategy"),
    "LegalDocSource": ("polisyos.lex.types", "LegalDocSource"),
    "LexIngestOptions": ("polisyos.lex.types", "LexIngestOptions"),
    "LexIngestResult": ("polisyos.lex.types", "LexIngestResult"),
    "LexStructureOptions": ("polisyos.lex.types", "LexStructureOptions"),
    "LexStructureResult": ("polisyos.lex.types", "LexStructureResult"),
    "LexVersionIndexOptions": ("polisyos.lex.types", "LexVersionIndexOptions"),
    "LexVersionIndexResult": ("polisyos.lex.types", "LexVersionIndexResult"),
    "NormPackBudgets": ("polisyos.lex.types", "NormPackBudgets"),
    "NormPackBuildRequest": ("polisyos.lex.types", "NormPackBuildRequest"),
    "NormPackBuildResult": ("polisyos.lex.types", "NormPackBuildResult"),
    "WorldEventRefLike": ("polisyos.lex.types", "WorldEventRefLike"),
    # simulator
    "AffectedKPI": ("polisyos.lex.simulator", "AffectedKPI"),
    "ComplianceDelta": ("polisyos.lex.simulator", "ComplianceDelta"),
    "ComplianceTransition": ("polisyos.lex.simulator", "ComplianceTransition"),
    "MutationIntent": ("polisyos.lex.simulator", "MutationIntent"),
    "NormChange": ("polisyos.lex.simulator", "NormChange"),
    "NormChangeType": ("polisyos.lex.simulator", "NormChangeType"),
    "NormDiff": ("polisyos.lex.simulator", "NormDiff"),
    "NormImpactAnalyzer": ("polisyos.lex.simulator", "NormImpactAnalyzer"),
    "NormImpactReport": ("polisyos.lex.simulator", "NormImpactReport"),
    "NormPackMutator": ("polisyos.lex.simulator", "NormPackMutator"),
    "diff_norm_packs": ("polisyos.lex.simulator", "diff_norm_packs"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.lex' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
