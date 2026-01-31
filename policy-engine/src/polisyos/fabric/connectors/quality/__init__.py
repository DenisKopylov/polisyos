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
]
