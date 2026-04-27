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
from .evidence import (
    FabricQualityGovernanceEvidence,
    build_fabric_quality_governance_evidence,
)
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
    "DEFAULT_POLICIES",
    "AnomalyFinding",
    "AnomalyReport",
    "ColumnProfile",
    "CompletenessAnalyzer",
    "CompletenessResult",
    "ConsistencyChecker",
    "ConsistencyResult",
    "DataQualityReport",
    "DataQualityValidator",
    "DatasetProfile",
    "DateGap",
    "DriftFinding",
    "DriftReport",
    "FabricQualityGovernanceEvidence",
    "FreshnessChecker",
    "FreshnessLevel",
    "FreshnessPolicy",
    "FreshnessStatus",
    "HistogramBin",
    "QualityContract",
    "QualityContractFailure",
    "QualityContractResult",
    "QualityContractRule",
    "QualityScorer",
    "QualityTrendPoint",
    "QualityTrendReport",
    "RuleViolation",
    "SamplingConfig",
    "SamplingStrategy",
    "TopValue",
    "build_fabric_quality_governance_evidence",
    "build_quality_series_key",
    "build_quality_trend_report",
    "detect_anomalies",
    "detect_drift",
    "evaluate_quality_contract",
    "load_quality_contract",
    "profile_dataframe",
]
