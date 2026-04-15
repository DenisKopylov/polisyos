"""
Data Quality and Freshness System for connectors.

Provides validation utilities and report structures.
"""

from .completeness import (
    CompletenessAnalyzer,
    CompletenessResult,
    DateGap,
    SamplingConfig,
    SamplingStrategy,
)
from .consistency import ConsistencyChecker, ConsistencyResult
from .freshness import (
    DEFAULT_POLICIES,
    FreshnessChecker,
    FreshnessPolicy,
)
from .report import (
    DataQualityReport,
    FreshnessLevel,
    FreshnessStatus,
    RuleViolation,
)
from .statistics import (
    AnomalyFinding,
    AnomalyReport,
    ColumnProfile,
    DatasetProfile,
    DriftFinding,
    DriftReport,
    HistogramBin,
    QualityContract,
    QualityContractFailure,
    QualityContractResult,
    QualityContractRule,
    QualityTrendPoint,
    QualityTrendReport,
    TopValue,
    build_quality_series_key,
    build_quality_trend_report,
    detect_anomalies,
    detect_drift,
    evaluate_quality_contract,
    load_quality_contract,
    profile_dataframe,
)
from .validator import DataQualityValidator, QualityScorer

__all__ = [
    "DataQualityValidator",
    "QualityScorer",
    "FreshnessChecker",
    "FreshnessPolicy",
    "FreshnessStatus",
    "FreshnessLevel",
    "DEFAULT_POLICIES",
    "CompletenessAnalyzer",
    "CompletenessResult",
    "DateGap",
    "SamplingStrategy",
    "SamplingConfig",
    "ConsistencyChecker",
    "ConsistencyResult",
    "DataQualityReport",
    "RuleViolation",
    "TopValue",
    "HistogramBin",
    "ColumnProfile",
    "DatasetProfile",
    "AnomalyFinding",
    "AnomalyReport",
    "DriftFinding",
    "DriftReport",
    "QualityContractRule",
    "QualityContract",
    "QualityContractFailure",
    "QualityContractResult",
    "QualityTrendPoint",
    "QualityTrendReport",
    "build_quality_series_key",
    "build_quality_trend_report",
    "profile_dataframe",
    "detect_anomalies",
    "detect_drift",
    "load_quality_contract",
    "evaluate_quality_contract",
]
