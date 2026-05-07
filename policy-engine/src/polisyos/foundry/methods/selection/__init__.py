"""Lazy facade for method selection and advisor APIs."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "COST_PER_MS",
    "ActiveSetSummary",
    "AdvisorOptimizationResult",
    "AdvisorValuePolicy",
    "BudgetCertificate",
    "CalibratedRegretCertificate",
    "CandidateScore",
    "ConfidenceSequence",
    "CrossMethodConsensus",
    "DataCharacteristics",
    "MethodAdvisorQuery",
    "MethodAdvisorResult",
    "MethodLossProfile",
    "MethodScoreTraceEntry",
    "MethodSelectionCriteria",
    "advise_methods",
    "advise_methods_for_analyst",
    "attach_advisor_execution_context",
    "authoring_catalog_payload",
    "build_advisor_execution_context",
    "compute_voi",
    "method_selection_payload",
    "pareto_advise_methods",
    "rank_method_catalog_entries",
    "suggest_adapter_methods",
    "suggest_alternative_methods",
    "suggest_plan_node_alternatives",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("polisyos.foundry.methods.selection.advisor"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
