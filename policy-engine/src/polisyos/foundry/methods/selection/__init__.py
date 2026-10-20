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
    "MethodRouteConstraint",
    "InputContractMethodCandidate",
    "InputContractMethodSelection",
    "select_method_for_input_contract",
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
    "method_selection_context_hash",
    "method_accepts_input_contract",
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

# Keep runtime lookup and source-bound closure on the same finite owner map.
_EXPORT_MODULES = {
    "COST_PER_MS": "polisyos.foundry.methods.selection.advisor",
    "ActiveSetSummary": "polisyos.foundry.methods.selection.advisor",
    "AdvisorOptimizationResult": "polisyos.foundry.methods.selection.advisor",
    "AdvisorValuePolicy": "polisyos.foundry.methods.selection.advisor",
    "BudgetCertificate": "polisyos.foundry.methods.selection.advisor",
    "CalibratedRegretCertificate": "polisyos.foundry.methods.selection.advisor",
    "CandidateScore": "polisyos.foundry.methods.selection.advisor",
    "ConfidenceSequence": "polisyos.foundry.methods.selection.advisor",
    "CrossMethodConsensus": "polisyos.foundry.methods.selection.advisor",
    "DataCharacteristics": "polisyos.foundry.methods.selection.advisor",
    "MethodAdvisorQuery": "polisyos.foundry.methods.selection.advisor",
    "MethodAdvisorResult": "polisyos.foundry.methods.selection.advisor",
    "MethodLossProfile": "polisyos.foundry.methods.selection.advisor",
    "MethodScoreTraceEntry": "polisyos.foundry.methods.selection.advisor",
    "MethodSelectionAlternative": "polisyos.foundry.methods.selection.receipt",
    "MethodRouteConstraint": "polisyos.foundry.methods.selection.advisor",
    "InputContractMethodCandidate": "polisyos.foundry.methods.selection.advisor",
    "InputContractMethodSelection": "polisyos.foundry.methods.selection.advisor",
    "select_method_for_input_contract": "polisyos.foundry.methods.selection.advisor",
    "MethodSelectionReceipt": "polisyos.foundry.methods.selection.receipt",
    "MethodSelectionCriteria": "polisyos.foundry.methods.selection.advisor",
    "_score_entry": "polisyos.foundry.methods.selection.advisor",
    "_score_entry_v2": "polisyos.foundry.methods.selection.advisor",
    "advise_methods": "polisyos.foundry.methods.selection.advisor",
    "advise_methods_for_analyst": "polisyos.foundry.methods.selection.advisor",
    "attach_advisor_execution_context": "polisyos.foundry.methods.selection.advisor",
    "authoring_catalog_payload": "polisyos.foundry.methods.selection.advisor",
    "build_advisor_execution_context": "polisyos.foundry.methods.selection.advisor",
    "compute_voi": "polisyos.foundry.methods.selection.advisor",
    "method_selection_context_hash": "polisyos.foundry.methods.selection.advisor",
    "method_accepts_input_contract": "polisyos.foundry.methods.selection.advisor",
    "method_selection_payload": "polisyos.foundry.methods.selection.advisor",
    "pareto_advise_methods": "polisyos.foundry.methods.selection.advisor",
    "rank_method_catalog_entries": "polisyos.foundry.methods.selection.advisor",
    "reachable_value_method_fqns": "polisyos.foundry.methods.selection.advisor",
    "select_method_candidates_for_requirements": "polisyos.foundry.methods.selection.requirements",
    "select_value_method_for_problem": "polisyos.foundry.methods.selection.advisor",
    "suggest_adapter_methods": "polisyos.foundry.methods.selection.advisor",
    "suggest_alternative_methods": "polisyos.foundry.methods.selection.advisor",
    "suggest_plan_node_alternatives": "polisyos.foundry.methods.selection.advisor",
}


def __getattr__(name: str) -> object:
    if name not in __all__ or name not in _EXPORT_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name = _EXPORT_MODULES[name]
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
