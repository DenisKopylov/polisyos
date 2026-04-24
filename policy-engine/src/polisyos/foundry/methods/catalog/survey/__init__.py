"""Expose survey-design methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_survey_methods
from .causal_frontier import CausalFrontierFayHerriotEstimator
from .demographic_consistency import (
    CCEBEstimator,
    DemographicConsistencyEstimator,
    DemographicConsistencyResult,
)
from .design import ComplexSurveyDesignEstimator
from .estimation import (
    CalibrationGREGEstimator,
    FayHerriotDependenceAwareEstimator,
    FayHerriotEstimator,
)
from .imputation import MICEEstimator, NonresponseAdjustmentEstimator
from .protocols import AuxiliaryTotalUncertainty, CalibrationWeights
from .semiparametric import (
    LinearizedSurveyVariance,
    PSUStratifiedCrossFitSchedule,
    ReplicateSurveyVariance,
    SamplingModelSpec,
    SurveyAdjustedSignalResult,
    SurveyDesignSpec,
    SurveySemiparametricATEEstimator,
    SurveySemiparametricATTEstimator,
    SurveySemiparametricSubgroupMeanEstimator,
    SurveyVarianceBackend,
    WeightRegimeDiagnostic,
    build_psu_stratified_cross_fit_schedule,
    build_survey_adjusted_signal,
    combine_weights_for_estimand,
    compute_binder_linearized_variance,
    compute_replicate_weight_variance,
    diagnose_weight_regime,
    resolve_inverse_inclusion_weights,
)
from .weighting import (
    HorvitzThompsonEstimator,
    PropensityWeightingEstimator,
    RakingEstimator,
    RakingIPFEstimator,
)

try:  # pragma: no cover - optional dependency path
    from .adaptive import (
        AdaptiveAugmentedEstimator,
        AdaptiveCalibratedIPWEstimator,
        AdaptiveResponsiveSurveyEstimator,
    )
except ModuleNotFoundError:  # pragma: no cover - keep survey core available
    AdaptiveAugmentedEstimator = None
    AdaptiveCalibratedIPWEstimator = None
    AdaptiveResponsiveSurveyEstimator = None

try:  # pragma: no cover - optional dependency path
    from .adaptive_benchmark import (
        AdaptiveBenchmarkCaseResult,
        AdaptiveBenchmarkConfig,
        AdaptiveBenchmarkScenarioKind,
        AdaptiveBenchmarkSuiteResult,
        default_adaptive_benchmark_config,
        run_adaptive_benchmark_suite,
    )
except ModuleNotFoundError:  # pragma: no cover - keep survey core available
    AdaptiveBenchmarkCaseResult = None
    AdaptiveBenchmarkConfig = None
    AdaptiveBenchmarkScenarioKind = None
    AdaptiveBenchmarkSuiteResult = None
    default_adaptive_benchmark_config = None
    run_adaptive_benchmark_suite = None

try:  # pragma: no cover - optional dependency path
    from .dr import DesignMissingnessDREstimator
except ModuleNotFoundError:  # pragma: no cover - keep survey core available
    DesignMissingnessDREstimator = None


def ensure_survey_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with survey methods for design, estimation, and reweighting flows."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_survey_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AuxiliaryTotalUncertainty",
    "CCEBEstimator",
    "CalibrationGREGEstimator",
    "CalibrationWeights",
    "CausalFrontierFayHerriotEstimator",
    "ComplexSurveyDesignEstimator",
    "DemographicConsistencyEstimator",
    "DemographicConsistencyResult",
    "FayHerriotDependenceAwareEstimator",
    "FayHerriotEstimator",
    "HorvitzThompsonEstimator",
    "LinearizedSurveyVariance",
    "MICEEstimator",
    "NonresponseAdjustmentEstimator",
    "PSUStratifiedCrossFitSchedule",
    "PropensityWeightingEstimator",
    "RakingEstimator",
    "RakingIPFEstimator",
    "ReplicateSurveyVariance",
    "SamplingModelSpec",
    "SurveyAdjustedSignalResult",
    "SurveyDesignSpec",
    "SurveySemiparametricATEEstimator",
    "SurveySemiparametricATTEstimator",
    "SurveySemiparametricSubgroupMeanEstimator",
    "SurveyVarianceBackend",
    "WeightRegimeDiagnostic",
    "build_psu_stratified_cross_fit_schedule",
    "build_survey_adjusted_signal",
    "combine_weights_for_estimand",
    "compute_binder_linearized_variance",
    "compute_replicate_weight_variance",
    "diagnose_weight_regime",
    "ensure_survey_methods_registered",
    "register_survey_methods",
    "resolve_inverse_inclusion_weights",
]

if AdaptiveCalibratedIPWEstimator is not None:
    __all__.append("AdaptiveCalibratedIPWEstimator")
if AdaptiveAugmentedEstimator is not None:
    __all__.append("AdaptiveAugmentedEstimator")
if AdaptiveResponsiveSurveyEstimator is not None:
    __all__.append("AdaptiveResponsiveSurveyEstimator")
if AdaptiveBenchmarkCaseResult is not None:
    __all__.append("AdaptiveBenchmarkCaseResult")
if AdaptiveBenchmarkConfig is not None:
    __all__.append("AdaptiveBenchmarkConfig")
if AdaptiveBenchmarkScenarioKind is not None:
    __all__.append("AdaptiveBenchmarkScenarioKind")
if AdaptiveBenchmarkSuiteResult is not None:
    __all__.append("AdaptiveBenchmarkSuiteResult")
if default_adaptive_benchmark_config is not None:
    __all__.append("default_adaptive_benchmark_config")
if run_adaptive_benchmark_suite is not None:
    __all__.append("run_adaptive_benchmark_suite")
if DesignMissingnessDREstimator is not None:
    __all__.append("DesignMissingnessDREstimator")
