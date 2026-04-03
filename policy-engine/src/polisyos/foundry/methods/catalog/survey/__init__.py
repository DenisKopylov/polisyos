"""Expose survey-design methods and register them into the Foundry catalog."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_survey_methods
from .design import ComplexSurveyDesignEstimator
from .estimation import CalibrationGREGEstimator, FayHerriotEstimator
from .imputation import MICEEstimator, NonresponseAdjustmentEstimator
from .weighting import (
    HorvitzThompsonEstimator,
    PropensityWeightingEstimator,
    RakingEstimator,
)


def ensure_survey_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with survey methods for design, estimation, and reweighting flows."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_survey_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "CalibrationGREGEstimator",
    "ComplexSurveyDesignEstimator",
    "FayHerriotEstimator",
    "HorvitzThompsonEstimator",
    "MICEEstimator",
    "NonresponseAdjustmentEstimator",
    "PropensityWeightingEstimator",
    "RakingEstimator",
    "ensure_survey_methods_registered",
    "register_survey_methods",
]
