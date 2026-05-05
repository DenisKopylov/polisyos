"""Public validation helpers for Scientist formal metric diagnostics."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "CausalFairnessSpec",
    "CorrectionMethod",
    "CounterfactualFairnessEstimator",
    "FairnessAuditConfig",
    "FairnessAuditEstimator",
    "FairnessAuditEstimatorFamily",
    "FairnessAuditInput",
    "FairnessAuditResult",
    "FairnessAuditRunner",
    "FairnessThreshold",
    "FamilyErrorSummary",
    "FamilyScope",
    "GroupMetricBreakdownEstimator",
    "IntersectionalConfig",
    "MetricId",
    "MetricValidationTypeIBenchResult",
    "ParityGapTestEstimator",
    "PathSpecificFairnessEstimator",
    "Phase5ArtifactPreflightInput",
    "Phase5PublicationResult",
    "Phase5ValidationBlocked",
    "ProtectedAttributeConfig",
    "StatisticalTestsConfig",
    "TestConfig",
    "TestId",
    "TypeITestSummary",
    "adjust_family",
    "build_phase5_validation_report",
    "collect_phase5_evidence",
    "compare_metric_family",
    "compare_metric_pairwise",
    "describe_test_id",
    "enforce_phase5_publication",
    "enforce_phase5_validation_report",
    "fairness_gate_response",
    "fairness_refusal_decision",
    "load_metric_observation_bundle",
    "persist_metric_observation_bundle",
    "predict_with_fairness_gate",
    "recommend_test",
    "run_metric_validation_type_i_bench",
    "run_phase5_artifact_preflight",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "FamilyErrorSummary": ("polisyos.scientist.validation.benchmarks", "FamilyErrorSummary"),
    "MetricValidationTypeIBenchResult": (
        "polisyos.scientist.validation.benchmarks",
        "MetricValidationTypeIBenchResult",
    ),
    "TypeITestSummary": ("polisyos.scientist.validation.benchmarks", "TypeITestSummary"),
    "run_metric_validation_type_i_bench": (
        "polisyos.scientist.validation.benchmarks",
        "run_metric_validation_type_i_bench",
    ),
    "CausalFairnessSpec": ("polisyos.scientist.validation.fairness_audit", "CausalFairnessSpec"),
    "CounterfactualFairnessEstimator": (
        "polisyos.scientist.validation.fairness_audit",
        "CounterfactualFairnessEstimator",
    ),
    "FairnessAuditConfig": (
        "polisyos.scientist.validation.fairness_audit",
        "FairnessAuditConfig",
    ),
    "FairnessAuditEstimator": (
        "polisyos.scientist.validation.fairness_audit",
        "FairnessAuditEstimator",
    ),
    "FairnessAuditEstimatorFamily": (
        "polisyos.scientist.validation.fairness_audit",
        "FairnessAuditEstimatorFamily",
    ),
    "FairnessAuditInput": ("polisyos.scientist.validation.fairness_audit", "FairnessAuditInput"),
    "FairnessAuditResult": (
        "polisyos.scientist.validation.fairness_audit",
        "FairnessAuditResult",
    ),
    "FairnessAuditRunner": (
        "polisyos.scientist.validation.fairness_audit",
        "FairnessAuditRunner",
    ),
    "FairnessThreshold": ("polisyos.scientist.validation.fairness_audit", "FairnessThreshold"),
    "GroupMetricBreakdownEstimator": (
        "polisyos.scientist.validation.fairness_audit",
        "GroupMetricBreakdownEstimator",
    ),
    "IntersectionalConfig": (
        "polisyos.scientist.validation.fairness_audit",
        "IntersectionalConfig",
    ),
    "ParityGapTestEstimator": (
        "polisyos.scientist.validation.fairness_audit",
        "ParityGapTestEstimator",
    ),
    "PathSpecificFairnessEstimator": (
        "polisyos.scientist.validation.fairness_audit",
        "PathSpecificFairnessEstimator",
    ),
    "ProtectedAttributeConfig": (
        "polisyos.scientist.validation.fairness_audit",
        "ProtectedAttributeConfig",
    ),
    "StatisticalTestsConfig": (
        "polisyos.scientist.validation.fairness_audit",
        "StatisticalTestsConfig",
    ),
    "fairness_gate_response": (
        "polisyos.scientist.validation.fairness_audit",
        "fairness_gate_response",
    ),
    "fairness_refusal_decision": (
        "polisyos.scientist.validation.fairness_audit",
        "fairness_refusal_decision",
    ),
    "predict_with_fairness_gate": (
        "polisyos.scientist.validation.fairness_audit",
        "predict_with_fairness_gate",
    ),
    "CorrectionMethod": ("polisyos.scientist.validation.metrics", "CorrectionMethod"),
    "FamilyScope": ("polisyos.scientist.validation.metrics", "FamilyScope"),
    "MetricId": ("polisyos.scientist.validation.metrics", "MetricId"),
    "TestConfig": ("polisyos.scientist.validation.metrics", "TestConfig"),
    "TestId": ("polisyos.scientist.validation.metrics", "TestId"),
    "adjust_family": ("polisyos.scientist.validation.metrics", "adjust_family"),
    "compare_metric_family": ("polisyos.scientist.validation.metrics", "compare_metric_family"),
    "compare_metric_pairwise": (
        "polisyos.scientist.validation.metrics",
        "compare_metric_pairwise",
    ),
    "describe_test_id": ("polisyos.scientist.validation.metrics", "describe_test_id"),
    "load_metric_observation_bundle": (
        "polisyos.scientist.validation.metrics",
        "load_metric_observation_bundle",
    ),
    "persist_metric_observation_bundle": (
        "polisyos.scientist.validation.metrics",
        "persist_metric_observation_bundle",
    ),
    "recommend_test": ("polisyos.scientist.validation.metrics", "recommend_test"),
    "Phase5ArtifactPreflightInput": (
        "polisyos.scientist.validation.phase5_preflight",
        "Phase5ArtifactPreflightInput",
    ),
    "Phase5PublicationResult": (
        "polisyos.scientist.validation.phase5_preflight",
        "Phase5PublicationResult",
    ),
    "Phase5ValidationBlocked": (
        "polisyos.scientist.validation.phase5_preflight",
        "Phase5ValidationBlocked",
    ),
    "build_phase5_validation_report": (
        "polisyos.scientist.validation.phase5_preflight",
        "build_phase5_validation_report",
    ),
    "collect_phase5_evidence": (
        "polisyos.scientist.validation.phase5_preflight",
        "collect_phase5_evidence",
    ),
    "enforce_phase5_validation_report": (
        "polisyos.scientist.validation.phase5_preflight",
        "enforce_phase5_validation_report",
    ),
    "enforce_phase5_publication": (
        "polisyos.scientist.validation.phase5_preflight",
        "enforce_phase5_publication",
    ),
    "run_phase5_artifact_preflight": (
        "polisyos.scientist.validation.phase5_preflight",
        "run_phase5_artifact_preflight",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.validation' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
