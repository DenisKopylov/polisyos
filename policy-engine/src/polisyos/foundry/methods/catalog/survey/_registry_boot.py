"""Public survey registry boot module API."""
from __future__ import annotations

from typing import Sequence

from .design import ComplexSurveyDesignEstimator
from .estimation import CalibrationGREGEstimator, FayHerriotEstimator
from .imputation import MICEEstimator, NonresponseAdjustmentEstimator
from .weighting import (
    HorvitzThompsonEstimator,
    PropensityWeightingEstimator,
    RakingEstimator,
)


def register_survey_methods() -> Sequence[type]:
    """Register survey methods."""
    return (
        HorvitzThompsonEstimator,
        RakingEstimator,
        PropensityWeightingEstimator,
        FayHerriotEstimator,
        CalibrationGREGEstimator,
        MICEEstimator,
        NonresponseAdjustmentEstimator,
        ComplexSurveyDesignEstimator,
    )


__all__ = ["register_survey_methods"]
