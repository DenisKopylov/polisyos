"""Lazy facade for method selection and advisor APIs."""

from __future__ import annotations

from importlib import import_module

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
    "MethodSelectionAlternative",
    "MethodSelectionReceipt",
    "MethodSelectionCriteria",
    "_score_entry",
    "_score_entry_v2",
    "advise_methods",
    "advise_methods_for_analyst",
    "attach_advisor_execution_context",
    "authoring_catalog_payload",
    "build_advisor_execution_context",
    "compute_voi",
    "method_selection_payload",
    "pareto_advise_methods",
    "rank_method_catalog_entries",
    "reachable_value_method_fqns",
    "select_method_candidates_for_requirements",
    "select_value_method_for_problem",
    "suggest_adapter_methods",
    "suggest_alternative_methods",
    "suggest_plan_node_alternatives",
]

_REQUIREMENT_IMPORTS = {
    "select_method_candidates_for_requirements",
}


def __getattr__(name: str) -> object:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name = (
        "polisyos.foundry.methods.selection.requirements"
        if name in _REQUIREMENT_IMPORTS
        else "polisyos.foundry.methods.selection.advisor"
    )
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
