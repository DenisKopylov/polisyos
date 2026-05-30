"""W9.A continuous-governance drift detector implementations."""

from __future__ import annotations

from .calibration_drift import detect_calibration_drift
from .common import (
    DEFAULT_SPARSE_HISTORY_POLICY,
    DETECTOR_FEATURE_FLAGS,
    DetectorConfig,
    DriftDetectionResult,
    SparseHistoryBand,
    SparseHistoryPolicy,
)
from .fairness import FairnessDriftSignal, detect_fairness_drift
from .policy_context import PolicyContextSignal, detect_policy_context_drift
from .source_invalidation import detect_source_invalidation

__all__ = [
    "DEFAULT_SPARSE_HISTORY_POLICY",
    "DETECTOR_FEATURE_FLAGS",
    "DetectorConfig",
    "DriftDetectionResult",
    "FairnessDriftSignal",
    "PolicyContextSignal",
    "SparseHistoryBand",
    "SparseHistoryPolicy",
    "detect_calibration_drift",
    "detect_fairness_drift",
    "detect_policy_context_drift",
    "detect_source_invalidation",
]
