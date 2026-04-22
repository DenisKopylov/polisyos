"""Public survey registry boot module API."""
from __future__ import annotations

from .causal_frontier import CausalFrontierFayHerriotEstimator
from .demographic_consistency import CCEBEstimator, DemographicConsistencyEstimator
from .design import ComplexSurveyDesignEstimator
from .estimation import (
    CalibrationGREGEstimator,
    FayHerriotDependenceAwareEstimator,
    FayHerriotEstimator,
)
from .imputation import MICEEstimator, NonresponseAdjustmentEstimator
from .semiparametric import (
    SurveySemiparametricATEEstimator,
    SurveySemiparametricATTEstimator,
    SurveySemiparametricSubgroupMeanEstimator,
)
from .weighting import (
    HorvitzThompsonEstimator,
    PropensityWeightingEstimator,
    RakingEstimator,
    RakingIPFEstimator,
)

try:  # pragma: no cover - optional dependency path
    from .adaptive import AdaptiveAugmentedEstimator, AdaptiveCalibratedIPWEstimator
except ModuleNotFoundError:  # pragma: no cover - keep survey core available
    AdaptiveAugmentedEstimator = None
    AdaptiveCalibratedIPWEstimator = None

try:  # pragma: no cover - optional dependency path
    from .dr import DesignMissingnessDREstimator
except ModuleNotFoundError:  # pragma: no cover - keep survey core available
    DesignMissingnessDREstimator = None


def register_survey_methods() -> tuple[type, ...]:
    """Register survey methods."""
    methods: list[type] = [
        HorvitzThompsonEstimator,
        RakingEstimator,
        RakingIPFEstimator,
        PropensityWeightingEstimator,
        DemographicConsistencyEstimator,
        CCEBEstimator,
        FayHerriotEstimator,
        FayHerriotDependenceAwareEstimator,
        CausalFrontierFayHerriotEstimator,
        CalibrationGREGEstimator,
        MICEEstimator,
        NonresponseAdjustmentEstimator,
        ComplexSurveyDesignEstimator,
        SurveySemiparametricATEEstimator,
        SurveySemiparametricATTEstimator,
        SurveySemiparametricSubgroupMeanEstimator,
    ]
    if AdaptiveCalibratedIPWEstimator is not None:
        methods.append(AdaptiveCalibratedIPWEstimator)
    if AdaptiveAugmentedEstimator is not None:
        methods.append(AdaptiveAugmentedEstimator)
    if DesignMissingnessDREstimator is not None:
        methods.append(DesignMissingnessDREstimator)
    return tuple(methods)


__all__ = ["register_survey_methods"]
