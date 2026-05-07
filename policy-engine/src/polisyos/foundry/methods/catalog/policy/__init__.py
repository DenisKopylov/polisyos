"""Expose policy-evaluation methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

from ._registry_boot import register_policy_methods
from .evaluation import (
    BudgetImpactEstimator,
    ExAnteSimulationEstimator,
    PolicyScorecardEstimator,
)
from .frontier import (
    FiscalMultiplierEstimator,
    FoundationModelPolicyAnalysisEstimator,
    KrusellSmithLiteEstimator,
    MeanFieldEquilibriumEstimator,
    OptimalLinearTaxEstimator,
    SufficientStatisticsWelfareEstimator,
)
from .mcda import (
    AHPEstimator,
    ELECTREEstimator,
    RankStabilityEstimator,
    RobustAHPEstimator,
    RobustELECTREEstimator,
    RobustTOPSISEstimator,
    TOPSISEstimator,
)
from .welfare import (
    AtkinsonSWFEstimator,
    CostBenefitAnalysisEstimator,
    CostEffectivenessEstimator,
    RawlsianSWFEstimator,
    SenCapabilityEstimator,
    SocialWeightManifest,
    StateDependentInverseSocialWeightsEstimator,
    UtilitarianSWFEstimator,
    WelfareBundle,
    build_social_weight_ref,
    clear_social_weight_manifest_registry,
    register_social_weight_manifest,
    resolve_social_weight_manifest,
    resolve_social_weight_schedule,
)


def ensure_policy_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with policy methods for scoring, MCDA, and welfare analysis."""
    bootstrap_builtin_foundry_method_family("policy", registry)


__all__ = [
    "AHPEstimator",
    "AtkinsonSWFEstimator",
    "BudgetImpactEstimator",
    "CostBenefitAnalysisEstimator",
    "CostEffectivenessEstimator",
    "ELECTREEstimator",
    "ExAnteSimulationEstimator",
    "FiscalMultiplierEstimator",
    "FoundationModelPolicyAnalysisEstimator",
    "KrusellSmithLiteEstimator",
    "MeanFieldEquilibriumEstimator",
    "OptimalLinearTaxEstimator",
    "PolicyScorecardEstimator",
    "RankStabilityEstimator",
    "RawlsianSWFEstimator",
    "RobustAHPEstimator",
    "RobustELECTREEstimator",
    "RobustTOPSISEstimator",
    "SenCapabilityEstimator",
    "SocialWeightManifest",
    "StateDependentInverseSocialWeightsEstimator",
    "SufficientStatisticsWelfareEstimator",
    "TOPSISEstimator",
    "UtilitarianSWFEstimator",
    "WelfareBundle",
    "build_social_weight_ref",
    "clear_social_weight_manifest_registry",
    "ensure_policy_methods_registered",
    "register_policy_methods",
    "register_social_weight_manifest",
    "resolve_social_weight_manifest",
    "resolve_social_weight_schedule",
]
