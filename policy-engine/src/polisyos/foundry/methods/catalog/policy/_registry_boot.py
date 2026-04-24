"""Public policy registry boot module API."""

from __future__ import annotations

from collections.abc import Sequence

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
    StateDependentInverseSocialWeightsEstimator,
    UtilitarianSWFEstimator,
)


def register_policy_methods() -> Sequence[type]:
    """Register policy methods."""
    return (
        CostBenefitAnalysisEstimator,
        CostEffectivenessEstimator,
        SufficientStatisticsWelfareEstimator,
        StateDependentInverseSocialWeightsEstimator,
        UtilitarianSWFEstimator,
        RawlsianSWFEstimator,
        AtkinsonSWFEstimator,
        SenCapabilityEstimator,
        BudgetImpactEstimator,
        PolicyScorecardEstimator,
        ExAnteSimulationEstimator,
        FoundationModelPolicyAnalysisEstimator,
        FiscalMultiplierEstimator,
        KrusellSmithLiteEstimator,
        OptimalLinearTaxEstimator,
        MeanFieldEquilibriumEstimator,
        TOPSISEstimator,
        AHPEstimator,
        ELECTREEstimator,
        RankStabilityEstimator,
        RobustTOPSISEstimator,
        RobustAHPEstimator,
        RobustELECTREEstimator,
    )


__all__ = ["register_policy_methods"]
