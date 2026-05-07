"""Public validation helpers for Scientist formal metric diagnostics."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "CausalFairnessSpec",
    "CorrectionMethod",
    "CounterfactualFairnessEstimator",
    "DecisionValidityService",
    "DecisionValidityStateStore",
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
    "LegalCandidatePack",
    "LegalSourcePack",
    "MetricId",
    "MetricValidationTypeIBenchResult",
    "ParityGapTestEstimator",
    "PathSpecificFairnessEstimator",
    "Phase5ArtifactPreflightInput",
    "Phase5PublicationResult",
    "Phase5ValidationBlocked",
    "PolicyEvidenceLink",
    "PolicyOption",
    "PolicyOptionSet",
    "PolicyRequestFrame",
    "ProtectedAttributeConfig",
    "SourceCoverageGap",
    "SourceVerificationReport",
    "StatisticalTestsConfig",
    "TestConfig",
    "TestId",
    "TypeITestSummary",
    "VerifiedLegalClaim",
    "VerifiedPolicyReport",
    "adjust_family",
    "assemble_legal_candidate_pack",
    "build_phase5_validation_report",
    "build_policy_request_frame",
    "build_verified_policy_report",
    "collect_phase5_evidence",
    "compare_metric_family",
    "compare_metric_pairwise",
    "describe_test_id",
    "draft_policy_option_set",
    "enforce_phase5_publication",
    "enforce_phase5_validation_report",
    "evaluate_ic_implementation_conformance",
    "evaluate_incentive_compatibility",
    "expand_legal_source_pack",
    "fairness_gate_response",
    "fairness_refusal_decision",
    "formalize_policy_option_set",
    "load_ic_certificate",
    "load_ic_conformance_report",
    "load_ic_negative_certificate",
    "load_ic_report",
    "load_legal_candidate_pack",
    "load_legal_source_pack",
    "load_metric_observation_bundle",
    "load_policy_option_set",
    "load_policy_request_frame",
    "load_source_verification_report",
    "load_verified_policy_report",
    "persist_ic_certificate",
    "persist_ic_conformance_report",
    "persist_ic_negative_certificate",
    "persist_ic_report",
    "persist_legal_candidate_pack",
    "persist_legal_source_pack",
    "persist_metric_observation_bundle",
    "persist_policy_option_set",
    "persist_policy_request_frame",
    "persist_source_verification_report",
    "persist_verified_policy_report",
    "predict_with_fairness_gate",
    "promote_ic_certificate_to_runtime",
    "recommend_test",
    "recover_source_gaps",
    "review_source_gaps",
    "run_metric_validation_type_i_bench",
    "run_phase5_artifact_preflight",
    "verify_ic_implementation_conformance",
    "verify_incentive_compatibility",
    "verify_source_pack",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DecisionValidityService": (
        "polisyos.scientist.validation.decision_validity",
        "DecisionValidityService",
    ),
    "DecisionValidityStateStore": (
        "polisyos.scientist.validation.decision_validity",
        "DecisionValidityStateStore",
    ),
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
    "LegalCandidatePack": (
        "polisyos.scientist.validation.policy_verified.models",
        "LegalCandidatePack",
    ),
    "LegalSourcePack": (
        "polisyos.scientist.validation.policy_verified.models",
        "LegalSourcePack",
    ),
    "PolicyEvidenceLink": (
        "polisyos.scientist.validation.policy_verified.models",
        "PolicyEvidenceLink",
    ),
    "PolicyOption": ("polisyos.scientist.validation.policy_verified.models", "PolicyOption"),
    "PolicyOptionSet": (
        "polisyos.scientist.validation.policy_verified.models",
        "PolicyOptionSet",
    ),
    "PolicyRequestFrame": (
        "polisyos.scientist.validation.policy_verified.models",
        "PolicyRequestFrame",
    ),
    "SourceCoverageGap": (
        "polisyos.scientist.validation.policy_verified.models",
        "SourceCoverageGap",
    ),
    "SourceVerificationReport": (
        "polisyos.scientist.validation.policy_verified.models",
        "SourceVerificationReport",
    ),
    "VerifiedLegalClaim": (
        "polisyos.scientist.validation.policy_verified.models",
        "VerifiedLegalClaim",
    ),
    "VerifiedPolicyReport": (
        "polisyos.scientist.validation.policy_verified.models",
        "VerifiedPolicyReport",
    ),
    "load_legal_candidate_pack": (
        "polisyos.scientist.validation.policy_verified.models",
        "load_legal_candidate_pack",
    ),
    "load_legal_source_pack": (
        "polisyos.scientist.validation.policy_verified.models",
        "load_legal_source_pack",
    ),
    "load_policy_option_set": (
        "polisyos.scientist.validation.policy_verified.models",
        "load_policy_option_set",
    ),
    "load_policy_request_frame": (
        "polisyos.scientist.validation.policy_verified.models",
        "load_policy_request_frame",
    ),
    "load_source_verification_report": (
        "polisyos.scientist.validation.policy_verified.models",
        "load_source_verification_report",
    ),
    "load_verified_policy_report": (
        "polisyos.scientist.validation.policy_verified.models",
        "load_verified_policy_report",
    ),
    "persist_legal_candidate_pack": (
        "polisyos.scientist.validation.policy_verified.models",
        "persist_legal_candidate_pack",
    ),
    "persist_legal_source_pack": (
        "polisyos.scientist.validation.policy_verified.models",
        "persist_legal_source_pack",
    ),
    "persist_policy_option_set": (
        "polisyos.scientist.validation.policy_verified.models",
        "persist_policy_option_set",
    ),
    "persist_policy_request_frame": (
        "polisyos.scientist.validation.policy_verified.models",
        "persist_policy_request_frame",
    ),
    "persist_source_verification_report": (
        "polisyos.scientist.validation.policy_verified.models",
        "persist_source_verification_report",
    ),
    "persist_verified_policy_report": (
        "polisyos.scientist.validation.policy_verified.models",
        "persist_verified_policy_report",
    ),
    "assemble_legal_candidate_pack": (
        "polisyos.scientist.validation.policy_verified.service",
        "assemble_legal_candidate_pack",
    ),
    "build_policy_request_frame": (
        "polisyos.scientist.validation.policy_verified.service",
        "build_policy_request_frame",
    ),
    "build_verified_policy_report": (
        "polisyos.scientist.validation.policy_verified.service",
        "build_verified_policy_report",
    ),
    "draft_policy_option_set": (
        "polisyos.scientist.validation.policy_verified.service",
        "draft_policy_option_set",
    ),
    "expand_legal_source_pack": (
        "polisyos.scientist.validation.policy_verified.service",
        "expand_legal_source_pack",
    ),
    "formalize_policy_option_set": (
        "polisyos.scientist.validation.policy_verified.service",
        "formalize_policy_option_set",
    ),
    "recover_source_gaps": (
        "polisyos.scientist.validation.policy_verified.service",
        "recover_source_gaps",
    ),
    "review_source_gaps": (
        "polisyos.scientist.validation.policy_verified.service",
        "review_source_gaps",
    ),
    "verify_source_pack": (
        "polisyos.scientist.validation.policy_verified.service",
        "verify_source_pack",
    ),
    "evaluate_ic_implementation_conformance": (
        "polisyos.scientist.validation.verification.ic.conformance",
        "evaluate_ic_implementation_conformance",
    ),
    "load_ic_conformance_report": (
        "polisyos.scientist.validation.verification.ic.conformance",
        "load_ic_conformance_report",
    ),
    "persist_ic_conformance_report": (
        "polisyos.scientist.validation.verification.ic.conformance",
        "persist_ic_conformance_report",
    ),
    "promote_ic_certificate_to_runtime": (
        "polisyos.scientist.validation.verification.ic.conformance",
        "promote_ic_certificate_to_runtime",
    ),
    "verify_ic_implementation_conformance": (
        "polisyos.scientist.validation.verification.ic.conformance",
        "verify_ic_implementation_conformance",
    ),
    "evaluate_incentive_compatibility": (
        "polisyos.scientist.validation.verification.ic.service",
        "evaluate_incentive_compatibility",
    ),
    "load_ic_certificate": (
        "polisyos.scientist.validation.verification.ic.service",
        "load_ic_certificate",
    ),
    "load_ic_negative_certificate": (
        "polisyos.scientist.validation.verification.ic.service",
        "load_ic_negative_certificate",
    ),
    "load_ic_report": (
        "polisyos.scientist.validation.verification.ic.service",
        "load_ic_report",
    ),
    "persist_ic_certificate": (
        "polisyos.scientist.validation.verification.ic.service",
        "persist_ic_certificate",
    ),
    "persist_ic_negative_certificate": (
        "polisyos.scientist.validation.verification.ic.service",
        "persist_ic_negative_certificate",
    ),
    "persist_ic_report": (
        "polisyos.scientist.validation.verification.ic.service",
        "persist_ic_report",
    ),
    "verify_incentive_compatibility": (
        "polisyos.scientist.validation.verification.ic.service",
        "verify_incentive_compatibility",
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
