"""Stable governance facade for runtime validation, calibration review, and replay reports.

This package exposes orchestration-level contracts consumed by Scientist nodes
and calibration jobs without eagerly importing the entire governance and
forecasting stack at package import time.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "REQUIRED_SIGNOFF_FAMILIES",
    "BacktestKind",
    "BacktestKindResult",
    "BacktestMatrixResult",
    "BacktestMatrixRunner",
    "CalibrationAdversarialResult",
    "CalibrationAdversarialSuiteRegistry",
    "CalibrationCandidateScore",
    "CalibrationGovernanceEvidenceRunner",
    "CalibrationGovernanceInput",
    "CalibrationGovernanceReport",
    "CalibrationGovernanceRunner",
    "CalibrationLeaderboard",
    "CalibrationLeaderboardEntry",
    "CalibrationLeaderboardMetrics",
    "CalibrationRunManifest",
    "CalibrationRunRunner",
    "CalibrationValidationBundle",
    "CalibrationValidationRunner",
    "CalibrationValidationRunnerInput",
    "CalibrationValidationRunnerResult",
    "FamilyEligibilityEntry",
    "FamilyEligibilityRegistry",
    "FamilyTier",
    "GovernanceAccountabilityArtifact",
    "GovernanceAccountabilityInput",
    "GovernanceReport",
    "GovernanceReportLinks",
    "GovernanceThresholdEntry",
    "HoldoutScoresManifest",
    "LossBreakdownManifest",
    "SpecificationCurveRunner",
    "SpecificationCurveSummaryManifest",
    "StrategicResponseMetricsManifest",
    "StrategicResponseRunner",
    "StressScenarioComparison",
    "StressScenarioKind",
    "StressScenarioResult",
    "StressScenarioRunner",
    "TransportabilityRunner",
    "TransportabilitySummaryManifest",
    "ValidationProfile",
    "build_downstream_utility_report",
    "build_family_eligibility_registry",
    "build_governance_accountability_artifact",
    "build_interference_evidence",
    "build_required_backtest_bundles",
    "load_calibration_validation_bundle",
    "load_governance_accountability_artifact",
    "persist_calibration_validation_bundle",
    "persist_governance_accountability_artifact",
    "postflight_checks",
    "preflight_checks",
    "resolve_governance_threshold",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ValidationProfile": ("polisyos.core.governance.profiles", "ValidationProfile"),
    "BacktestKind": ("polisyos.scientist.governance.backtest_matrix", "BacktestKind"),
    "BacktestKindResult": ("polisyos.scientist.governance.backtest_matrix", "BacktestKindResult"),
    "BacktestMatrixResult": (
        "polisyos.scientist.governance.backtest_matrix",
        "BacktestMatrixResult",
    ),
    "BacktestMatrixRunner": (
        "polisyos.scientist.governance.backtest_matrix",
        "BacktestMatrixRunner",
    ),
    "GovernanceAccountabilityArtifact": (
        "polisyos.scientist.governance.accountability",
        "GovernanceAccountabilityArtifact",
    ),
    "GovernanceAccountabilityInput": (
        "polisyos.scientist.governance.accountability",
        "GovernanceAccountabilityInput",
    ),
    "GovernanceThresholdEntry": (
        "polisyos.scientist.governance.accountability",
        "GovernanceThresholdEntry",
    ),
    "build_governance_accountability_artifact": (
        "polisyos.scientist.governance.accountability",
        "build_governance_accountability_artifact",
    ),
    "persist_governance_accountability_artifact": (
        "polisyos.scientist.governance.accountability",
        "persist_governance_accountability_artifact",
    ),
    "load_governance_accountability_artifact": (
        "polisyos.scientist.governance.accountability",
        "load_governance_accountability_artifact",
    ),
    "resolve_governance_threshold": (
        "polisyos.scientist.governance.accountability",
        "resolve_governance_threshold",
    ),
    "CalibrationAdversarialResult": (
        "polisyos.scientist.governance.calibration",
        "CalibrationAdversarialResult",
    ),
    "CalibrationAdversarialSuiteRegistry": (
        "polisyos.scientist.governance.calibration",
        "CalibrationAdversarialSuiteRegistry",
    ),
    "CalibrationGovernanceInput": (
        "polisyos.scientist.governance.calibration",
        "CalibrationGovernanceInput",
    ),
    "CalibrationGovernanceReport": (
        "polisyos.scientist.governance.calibration",
        "CalibrationGovernanceReport",
    ),
    "CalibrationGovernanceRunner": (
        "polisyos.scientist.governance.calibration",
        "CalibrationGovernanceRunner",
    ),
    "CalibrationLeaderboard": (
        "polisyos.scientist.governance.calibration_leaderboard",
        "CalibrationLeaderboard",
    ),
    "CalibrationLeaderboardEntry": (
        "polisyos.scientist.governance.calibration_leaderboard",
        "CalibrationLeaderboardEntry",
    ),
    "CalibrationLeaderboardMetrics": (
        "polisyos.scientist.governance.calibration_leaderboard",
        "CalibrationLeaderboardMetrics",
    ),
    "CalibrationValidationBundle": (
        "polisyos.scientist.governance.calibration_validation",
        "CalibrationValidationBundle",
    ),
    "CalibrationValidationRunner": (
        "polisyos.scientist.governance.calibration_validation",
        "CalibrationValidationRunner",
    ),
    "CalibrationValidationRunnerInput": (
        "polisyos.scientist.governance.calibration_validation",
        "CalibrationValidationRunnerInput",
    ),
    "CalibrationValidationRunnerResult": (
        "polisyos.scientist.governance.calibration_validation",
        "CalibrationValidationRunnerResult",
    ),
    "persist_calibration_validation_bundle": (
        "polisyos.scientist.governance.calibration_validation",
        "persist_calibration_validation_bundle",
    ),
    "load_calibration_validation_bundle": (
        "polisyos.scientist.governance.calibration_validation",
        "load_calibration_validation_bundle",
    ),
    "CalibrationCandidateScore": (
        "polisyos.scientist.governance.blueprint_release",
        "CalibrationCandidateScore",
    ),
    "CalibrationGovernanceEvidenceRunner": (
        "polisyos.scientist.governance.blueprint_release",
        "CalibrationGovernanceEvidenceRunner",
    ),
    "CalibrationRunManifest": (
        "polisyos.scientist.governance.blueprint_release",
        "CalibrationRunManifest",
    ),
    "CalibrationRunRunner": (
        "polisyos.scientist.governance.blueprint_release",
        "CalibrationRunRunner",
    ),
    "FamilyEligibilityEntry": (
        "polisyos.scientist.governance.blueprint_release",
        "FamilyEligibilityEntry",
    ),
    "FamilyEligibilityRegistry": (
        "polisyos.scientist.governance.blueprint_release",
        "FamilyEligibilityRegistry",
    ),
    "FamilyTier": ("polisyos.scientist.governance.blueprint_release", "FamilyTier"),
    "HoldoutScoresManifest": (
        "polisyos.scientist.governance.blueprint_release",
        "HoldoutScoresManifest",
    ),
    "LossBreakdownManifest": (
        "polisyos.scientist.governance.blueprint_release",
        "LossBreakdownManifest",
    ),
    "REQUIRED_SIGNOFF_FAMILIES": (
        "polisyos.scientist.governance.blueprint_release",
        "REQUIRED_SIGNOFF_FAMILIES",
    ),
    "SpecificationCurveRunner": (
        "polisyos.scientist.governance.blueprint_release",
        "SpecificationCurveRunner",
    ),
    "SpecificationCurveSummaryManifest": (
        "polisyos.scientist.governance.blueprint_release",
        "SpecificationCurveSummaryManifest",
    ),
    "StrategicResponseMetricsManifest": (
        "polisyos.scientist.governance.blueprint_release",
        "StrategicResponseMetricsManifest",
    ),
    "StrategicResponseRunner": (
        "polisyos.scientist.governance.blueprint_release",
        "StrategicResponseRunner",
    ),
    "TransportabilityRunner": (
        "polisyos.scientist.governance.blueprint_release",
        "TransportabilityRunner",
    ),
    "TransportabilitySummaryManifest": (
        "polisyos.scientist.governance.blueprint_release",
        "TransportabilitySummaryManifest",
    ),
    "build_downstream_utility_report": (
        "polisyos.scientist.governance.blueprint_release",
        "build_downstream_utility_report",
    ),
    "build_family_eligibility_registry": (
        "polisyos.scientist.governance.blueprint_release",
        "build_family_eligibility_registry",
    ),
    "build_interference_evidence": (
        "polisyos.scientist.governance.blueprint_release",
        "build_interference_evidence",
    ),
    "build_required_backtest_bundles": (
        "polisyos.scientist.governance.blueprint_release",
        "build_required_backtest_bundles",
    ),
    "postflight_checks": ("polisyos.scientist.governance.postflight", "postflight_checks"),
    "preflight_checks": ("polisyos.scientist.governance.preflight", "preflight_checks"),
    "GovernanceReport": ("polisyos.scientist.governance.report", "GovernanceReport"),
    "GovernanceReportLinks": ("polisyos.scientist.governance.report", "GovernanceReportLinks"),
    "StressScenarioComparison": (
        "polisyos.scientist.governance.stress_scenarios",
        "StressScenarioComparison",
    ),
    "StressScenarioKind": (
        "polisyos.scientist.governance.stress_scenarios",
        "StressScenarioKind",
    ),
    "StressScenarioResult": (
        "polisyos.scientist.governance.stress_scenarios",
        "StressScenarioResult",
    ),
    "StressScenarioRunner": (
        "polisyos.scientist.governance.stress_scenarios",
        "StressScenarioRunner",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
