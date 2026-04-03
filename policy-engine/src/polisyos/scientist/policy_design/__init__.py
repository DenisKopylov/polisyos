"""Policy design typed schema and objective stack.

This package intentionally uses lazy re-exports to avoid import cycles between
``policy_design.output`` and downstream consumers such as ``judge_stack``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_SYMBOL_TO_MODULE = {
    "AdversarialScenarioBundle": "polisyos.scientist.policy_design.adversary",
    "AdversarialScenarioProposal": "polisyos.scientist.policy_design.adversary",
    "AdversaryExecutionResult": "polisyos.scientist.policy_design.adversary",
    "BudgetAllocationEntry": "polisyos.scientist.policy_design.schema",
    "ChampionPolicyDossier": "polisyos.scientist.policy_design.output",
    "ConstraintStatus": "polisyos.scientist.policy_design.objectives",
    "ConstraintCritic": "polisyos.scientist.policy_design.critic",
    "ConstraintCriticInput": "polisyos.scientist.policy_design.critic",
    "ConstraintCritique": "polisyos.scientist.policy_design.critic",
    "ConstraintFinding": "polisyos.scientist.policy_design.critic",
    "ConstraintSatisfactionReport": "polisyos.scientist.policy_design.output",
    "ConstraintTrace": "polisyos.scientist.policy_design.critic",
    "DeterministicPolicyTranslator": "polisyos.scientist.policy_design.translator",
    "FallbackVariant": "polisyos.scientist.policy_design.schema",
    "GovernanceGatePacket": "polisyos.scientist.policy_design.output",
    "HarmEnvelope": "polisyos.scientist.policy_design.schema",
    "HierarchicalSearchConfig": "polisyos.scientist.policy_design.search",
    "HierarchicalSearchCoordinator": "polisyos.scientist.policy_design.search",
    "HierarchicalSearchResult": "polisyos.scientist.policy_design.search",
    "HierarchicalSearchState": "polisyos.scientist.policy_design.search",
    "ImplementationPlan": "polisyos.scientist.policy_design.output",
    "MonitoringSignalSpec": "polisyos.scientist.policy_design.schema",
    "NarrativeVariant": "polisyos.scientist.policy_design.search",
    "ObjectiveChannelValue": "polisyos.scientist.policy_design.objectives",
    "ObjectiveDirection": "polisyos.scientist.policy_design.objectives",
    "ObjectiveKind": "polisyos.scientist.policy_design.objectives",
    "ObjectiveStack": "polisyos.scientist.policy_design.objectives",
    "ParameterScheduleEntry": "polisyos.scientist.policy_design.schema",
    "ParameterSearchSpec": "polisyos.scientist.policy_design.search",
    "PolicyAssumptionSpec": "polisyos.scientist.policy_design.schema",
    "PolicyArtifactBuildInput": "polisyos.scientist.policy_design.output",
    "PolicyArtifactBuilder": "polisyos.scientist.policy_design.output",
    "PolicyArtifactBundle": "polisyos.scientist.policy_design.output",
    "PolicyCandidateSchema": "polisyos.scientist.policy_design.schema",
    "PolicyEvaluationBundle": "polisyos.scientist.policy_design.objectives",
    "PolicyEvaluationVector": "polisyos.scientist.policy_design.objectives",
    "PolicyBrief": "polisyos.scientist.policy_design.output",
    "PolicyFrontierReport": "polisyos.scientist.policy_design.output",
    "PolicyParameterCodec": "polisyos.scientist.policy_design.search",
    "PolicyRiskNote": "polisyos.scientist.policy_design.translator",
    "PolicySearchLevel": "polisyos.scientist.policy_design.search",
    "PolicyTranslatorConfig": "polisyos.scientist.policy_design.translator",
    "PolicyTranslatorWorker": "polisyos.scientist.policy_design.translator",
    "RecommendedAction": "polisyos.scientist.policy_design.translator",
    "RejectedAlternativesSummary": "polisyos.scientist.policy_design.output",
    "ReplayableAuditBundle": "polisyos.scientist.policy_design.output",
    "RolloutStep": "polisyos.scientist.policy_design.schema",
    "ScenarioAdversaryConfig": "polisyos.scientist.policy_design.adversary",
    "ScenarioAdversaryWorker": "polisyos.scientist.policy_design.adversary",
    "ScenarioAttackSurface": "polisyos.scientist.policy_design.adversary",
    "StructureCandidate": "polisyos.scientist.policy_design.search",
    "SubgroupImpactReport": "polisyos.scientist.policy_design.output",
    "TargetPopulationSpec": "polisyos.scientist.policy_design.schema",
    "TradeoffRow": "polisyos.scientist.policy_design.output",
    "TransportAssumptionSpec": "polisyos.scientist.policy_design.schema",
    "TransportabilityReport": "polisyos.scientist.policy_design.output",
    "TranslatorComplianceFinding": "polisyos.scientist.policy_design.translator",
    "TranslatorCompliancePass": "polisyos.scientist.policy_design.translator",
    "TranslatorComplianceResult": "polisyos.scientist.policy_design.translator",
    "TranslatorInputBundle": "polisyos.scientist.policy_design.translator",
    "UncertaintyReport": "polisyos.scientist.policy_design.output",
    "critique_to_failure_cards": "polisyos.scientist.policy_design.critic",
    "critique_to_lesson_cards": "polisyos.scientist.policy_design.critic",
    "load_adversarial_scenario_bundle": "polisyos.scientist.policy_design.adversary",
    "load_policy_artifact_bundle": "polisyos.scientist.policy_design.output",
    "load_policy_brief": "polisyos.scientist.policy_design.output",
    "load_policy_candidate_schema": "polisyos.scientist.policy_design.schema",
    "persist_adversarial_scenario_bundle": "polisyos.scientist.policy_design.adversary",
    "persist_policy_artifact_bundle": "polisyos.scientist.policy_design.output",
    "persist_policy_brief": "polisyos.scientist.policy_design.output",
    "persist_policy_candidate_schema": "polisyos.scientist.policy_design.schema",
    "trace_to_mutation_hints": "polisyos.scientist.policy_design.critic",
}

__all__ = sorted(_SYMBOL_TO_MODULE)


def __getattr__(name: str) -> Any:
    """Resolve public exports lazily to keep package import cycle-free."""
    module_name = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
