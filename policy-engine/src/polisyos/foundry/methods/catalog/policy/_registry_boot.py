"""Public policy registry boot module API."""
from __future__ import annotations

from typing import Sequence

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
    TOPSISEstimator,
)
from .welfare import (
    AtkinsonSWFEstimator,
    CostBenefitAnalysisEstimator,
    CostEffectivenessEstimator,
    RawlsianSWFEstimator,
    SenCapabilityEstimator,
    UtilitarianSWFEstimator,
)


def register_policy_methods() -> Sequence[type]:
    """Register policy methods."""
    return (
        CostBenefitAnalysisEstimator,
        CostEffectivenessEstimator,
        SufficientStatisticsWelfareEstimator,
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
    )


__all__ = ["register_policy_methods"]
