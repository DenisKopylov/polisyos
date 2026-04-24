"""missing_data — Foundry methods for M-graph missing data analysis.

Three registered methods in the ``causal.missing_data`` namespace:

  RecoverabilityTest  — test whether P(S) is recoverable from P*(V)
  OrderedRecovery     — build the recovery EstimandAST via ordered fixing operator
  FullLawIdentify     — two-stage pipeline: recover P(V) then identify P(Y|do(X))

All three are thin Foundry wrappers around pure algorithm functions in
``recoverability_engine.py``.

References
----------
Mohan, K. & Pearl, J. (2021). "Graphical Models for Processing Missing Data."
    Journal of the American Statistical Association.
Mohan, K., Pearl, J. & Tian, J. (2013). "Missing Data as a Causal and
    Probabilistic Problem." UAI 2013.
Nabi, R., Bhattacharya, R. & Shpitser, I. (2020). "Full law identification in
    graphical models of missing data."
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

_logger = logging.getLogger(__name__)

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.ir.analytics.administrative_missingness import (
    AdministrativeMissingnessClass,
    AdministrativeMissingnessDirection,
    AdministrativeMissingnessMetadata,
    AdministrativeMissingnessScenarioFamily,
    AdministrativeMissingnessUnitScope,
    MissingnessAssessmentProvenance,
    MissingnessAssessmentReport,
    MissingnessAssessmentStatus,
    MissingnessEstimandRisk,
    MissingnessEvidenceItem,
    MissingnessImplicationFailure,
    MissingnessProofStep,
    MissingnessRecoverabilitySummary,
    MissingnessTestabilityAudit,
    extract_administrative_missingness_metadata,
)


def _json_slot(name: str) -> SlotSpec:
    return SlotSpec(name, SlotType.SCALAR, Unit(name, "json"))


class ConditionalIndependence(BaseModel):
    """Testable implication X ⊥ Y | Z extracted from an M-graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: str
    y: str
    z: tuple[str, ...] = ()


class ImplicationTestResult(BaseModel):
    """Single CI test result with BH-adjusted significance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    implication: ConditionalIndependence
    statistic: float
    p_value: float
    adjusted_p_value: float
    passed: bool
    test_name: str = "adaptive_mgraph_ci"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestReport(BaseModel):
    """Aggregated M-graph implication test report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    implications_tested: int
    implications_passed: int
    implications_failed: list[tuple[ConditionalIndependence, float]] = Field(default_factory=list)
    overall_valid: bool
    alpha: float = 0.05
    correction_method: str = "benjamini_hochberg"
    test_method: str = "adaptive_mgraph_ci"
    results: list[ImplicationTestResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


_REGISTRATION_KEYWORDS = (
    "register",
    "registration",
    "apply",
    "application",
    "enroll",
    "enrol",
    "eligib",
)
_COMPLIANCE_KEYWORDS = (
    "compliance",
    "report",
    "filing",
    "submit",
    "submission",
    "deadline",
    "sanction",
    "document",
    "attest",
)
_SYSTEM_CHANGE_KEYWORDS = (
    "system",
    "version",
    "release",
    "regime",
    "rollout",
    "migration",
    "office",
    "downtime",
    "period",
    "date",
    "time",
)

_BOOLEAN_REQUIREMENT_FIELDS = {
    "population_frame_observed": "population_frame_observed",
    "bridge_window_observed": "bridge_window_observed",
    "retention_window_observed": "retention_window_observed",
    "legal_rule_observed": "legal_rule_observed",
    "matured_cohorts_observed": "matured_cohorts_observed",
    "validation_subset_available": "validation_subset_available",
}

_CLASS_DEFAULT_DIRECTIONS = {
    AdministrativeMissingnessClass.NONE: AdministrativeMissingnessDirection.UNKNOWN,
    AdministrativeMissingnessClass.REGISTRATION_NOT_APPLIED: (
        AdministrativeMissingnessDirection.NOT_GENERATED
    ),
    AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED: (
        AdministrativeMissingnessDirection.NOT_GENERATED
    ),
    AdministrativeMissingnessClass.COMPLIANCE_NOT_COMPLETED: (
        AdministrativeMissingnessDirection.NOT_CAPTURED
    ),
    AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED: (
        AdministrativeMissingnessDirection.NOT_CAPTURED
    ),
    AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK: (
        AdministrativeMissingnessDirection.NOT_CAPTURED
    ),
    AdministrativeMissingnessClass.RETENTION_EXPIRED: (AdministrativeMissingnessDirection.DELETED),
    AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION: (
        AdministrativeMissingnessDirection.WITHHELD
    ),
    AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG: (
        AdministrativeMissingnessDirection.DELAYED
    ),
    AdministrativeMissingnessClass.LINKAGE_FAILURE: AdministrativeMissingnessDirection.NOT_LINKED,
    AdministrativeMissingnessClass.MIXED: AdministrativeMissingnessDirection.UNKNOWN,
    AdministrativeMissingnessClass.UNKNOWN: AdministrativeMissingnessDirection.UNKNOWN,
}

_CLASS_DEFAULT_SCOPES = {
    AdministrativeMissingnessClass.NONE: AdministrativeMissingnessUnitScope.UNKNOWN,
    AdministrativeMissingnessClass.REGISTRATION_NOT_APPLIED: (
        AdministrativeMissingnessUnitScope.RECORD
    ),
    AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED: (
        AdministrativeMissingnessUnitScope.RECORD
    ),
    AdministrativeMissingnessClass.COMPLIANCE_NOT_COMPLETED: (
        AdministrativeMissingnessUnitScope.EPISODE
    ),
    AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED: (
        AdministrativeMissingnessUnitScope.TIME_WINDOW
    ),
    AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK: (
        AdministrativeMissingnessUnitScope.EXTRACT
    ),
    AdministrativeMissingnessClass.RETENTION_EXPIRED: (
        AdministrativeMissingnessUnitScope.TIME_WINDOW
    ),
    AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION: (
        AdministrativeMissingnessUnitScope.FIELD
    ),
    AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG: (
        AdministrativeMissingnessUnitScope.EXTRACT
    ),
    AdministrativeMissingnessClass.LINKAGE_FAILURE: AdministrativeMissingnessUnitScope.LINK,
    AdministrativeMissingnessClass.MIXED: AdministrativeMissingnessUnitScope.UNKNOWN,
    AdministrativeMissingnessClass.UNKNOWN: AdministrativeMissingnessUnitScope.UNKNOWN,
}

_CLASS_ESTIMAND_SCOPE = {
    AdministrativeMissingnessClass.REGISTRATION_NOT_APPLIED: "eligible_population",
    AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED: "eligible_population",
    AdministrativeMissingnessClass.COMPLIANCE_NOT_COMPLETED: "started_population",
    AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED: "service_window",
    AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK: "harmonised_window",
    AdministrativeMissingnessClass.RETENTION_EXPIRED: "retention_window",
    AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION: "restricted_domain",
    AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG: "current_extract",
    AdministrativeMissingnessClass.LINKAGE_FAILURE: "linked_population",
}


def _merge_requirement_specs(
    *specs: tuple[tuple[str, ...], dict[str, tuple[str, ...]]],
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    names: list[str] = []
    variables: dict[str, tuple[str, ...]] = {}
    for requirement_names, requirement_vars in specs:
        for name in requirement_names:
            if name not in names:
                names.append(name)
        for key, value in requirement_vars.items():
            current = list(variables.get(key, ()))
            for item in value:
                text = str(item).strip()
                if text and text not in current:
                    current.append(text)
            variables[key] = tuple(current)
    return tuple(names), variables


def _infer_operational_missingness(
    *,
    metadata: AdministrativeMissingnessMetadata | None,
    scenario_family: AdministrativeMissingnessScenarioFamily,
) -> tuple[
    AdministrativeMissingnessClass,
    AdministrativeMissingnessDirection,
    AdministrativeMissingnessUnitScope,
]:
    if metadata is not None and metadata.scenario_class is not None:
        scenario_class = metadata.scenario_class
    elif scenario_family is AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED:
        label = str(metadata.registration_indicator or "").lower() if metadata else ""
        if "apply" in label or "application" in label or "claim" in label:
            scenario_class = AdministrativeMissingnessClass.REGISTRATION_NOT_APPLIED
        else:
            scenario_class = AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED
    elif scenario_family is AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED:
        scenario_class = AdministrativeMissingnessClass.COMPLIANCE_NOT_COMPLETED
    elif scenario_family is AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED:
        if metadata is not None and metadata.office_availability_covariates:
            scenario_class = AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED
        else:
            scenario_class = AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK
    elif scenario_family is AdministrativeMissingnessScenarioFamily.HYBRID:
        scenario_class = AdministrativeMissingnessClass.MIXED
    else:
        scenario_class = AdministrativeMissingnessClass.UNKNOWN

    if metadata is not None and metadata.missingness_direction is not None:
        direction = metadata.missingness_direction
    else:
        direction = _CLASS_DEFAULT_DIRECTIONS[scenario_class]

    if metadata is not None and metadata.missingness_unit_scope is not None:
        scope = metadata.missingness_unit_scope
    else:
        scope = _CLASS_DEFAULT_SCOPES[scenario_class]

    return scenario_class, direction, scope


def _scenario_requirements(
    metadata: AdministrativeMissingnessMetadata | None,
    scenario_family: AdministrativeMissingnessScenarioFamily,
    scenario_class: AdministrativeMissingnessClass,
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    if scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        return _merge_requirement_specs(
            (
                ("identifier_quality_covariates", "validation_subset_available"),
                {
                    "identifier_quality_covariates": (
                        tuple(metadata.identifier_quality_covariates) if metadata else ()
                    ),
                },
            ),
        )

    if scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        return _merge_requirement_specs(
            (
                (
                    "time_variable",
                    "processing_lag_covariates",
                    "matured_cohorts_observed",
                ),
                {
                    "time_variable": (metadata.time_variable,)
                    if metadata and metadata.time_variable
                    else (),
                    "processing_lag_covariates": (
                        tuple(metadata.processing_lag_covariates) if metadata else ()
                    ),
                },
            ),
        )

    if scenario_class is AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION:
        return _merge_requirement_specs(
            (
                ("legal_restriction_covariates", "legal_rule_observed"),
                {
                    "legal_restriction_covariates": (
                        tuple(metadata.legal_restriction_covariates) if metadata else ()
                    ),
                },
            ),
        )

    if scenario_class is AdministrativeMissingnessClass.RETENTION_EXPIRED:
        return _merge_requirement_specs(
            (
                ("time_variable", "retention_window_observed"),
                {
                    "time_variable": (metadata.time_variable,)
                    if metadata and metadata.time_variable
                    else (),
                },
            ),
        )

    if scenario_class is AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED:
        return _merge_requirement_specs(
            (
                ("office_availability_covariates",),
                {
                    "office_availability_covariates": (
                        tuple(metadata.office_availability_covariates) if metadata else ()
                    ),
                },
            ),
        )

    if scenario_class is AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK:
        requirement_names = ["system_version_or_time", "rollout_covariates"]
        if metadata is not None and metadata.bridge_window_observed is not None:
            requirement_names.append("bridge_window_observed")
        return _merge_requirement_specs(
            (
                tuple(requirement_names),
                {
                    "system_version_or_time": (
                        tuple(
                            item
                            for item in (
                                metadata.system_version_variable,
                                metadata.time_variable,
                            )
                            if item
                        )
                        if metadata
                        else ()
                    ),
                    "rollout_covariates": tuple(metadata.rollout_covariates) if metadata else (),
                },
            ),
        )

    if scenario_family is AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED:
        requirement_names = (
            "registration_indicator",
            "population_frame_observed",
            "eligibility_covariates",
        )
        requirement_vars = {
            "registration_indicator": (metadata.registration_indicator,)
            if metadata and metadata.registration_indicator
            else (),
            "eligibility_covariates": (tuple(metadata.eligibility_covariates) if metadata else ()),
        }
        return requirement_names, requirement_vars

    if scenario_family is AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED:
        requirement_names = (
            "compliance_indicator",
            "compliance_driver_covariates",
        )
        requirement_vars = {
            "compliance_indicator": (metadata.compliance_indicator,)
            if metadata and metadata.compliance_indicator
            else (),
            "compliance_driver_covariates": (
                tuple(metadata.compliance_driver_covariates) if metadata else ()
            ),
        }
        return requirement_names, requirement_vars

    if scenario_family is AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED:
        requirement_names = (
            "system_version_or_time",
            "rollout_covariates",
        )
        system_vars: tuple[str, ...] = ()
        if metadata is not None:
            system_vars = tuple(
                item for item in (metadata.system_version_variable, metadata.time_variable) if item
            )
        requirement_vars = {
            "system_version_or_time": system_vars,
            "rollout_covariates": tuple(metadata.rollout_covariates) if metadata else (),
        }
        return requirement_names, requirement_vars

    if scenario_family is AdministrativeMissingnessScenarioFamily.HYBRID:
        names: list[str] = []
        variables: dict[str, tuple[str, ...]] = {}
        for component in (
            AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED,
            AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED,
            AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED,
        ):
            component_names, component_vars = _scenario_requirements(
                metadata,
                component,
                AdministrativeMissingnessClass.UNKNOWN,
            )
            for name in component_names:
                if name not in names:
                    names.append(name)
            variables.update(component_vars)
        return tuple(names), variables

    return (), {}


def _infer_scenario_family(
    *,
    graph: Any,
    metadata: AdministrativeMissingnessMetadata | None,
) -> tuple[AdministrativeMissingnessScenarioFamily, float, tuple[str, ...]]:
    if metadata is not None:
        return metadata.scenario_family, 1.0, metadata.administrative_covariates

    nodes = tuple(str(node) for node in getattr(graph, "nodes", ()))
    lowered = {node: node.lower() for node in nodes}
    registration_hits = tuple(
        node
        for node, label in lowered.items()
        if any(token in label for token in _REGISTRATION_KEYWORDS)
    )
    compliance_hits = tuple(
        node
        for node, label in lowered.items()
        if any(token in label for token in _COMPLIANCE_KEYWORDS)
    )
    system_hits = tuple(
        node
        for node, label in lowered.items()
        if any(token in label for token in _SYSTEM_CHANGE_KEYWORDS)
    )
    scores = {
        AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED: len(registration_hits),
        AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED: len(compliance_hits),
        AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED: len(system_hits),
    }
    non_zero = {family: score for family, score in scores.items() if score > 0}
    if not non_zero:
        return AdministrativeMissingnessScenarioFamily.UNKNOWN, 0.0, ()
    sorted_scores = sorted(non_zero.items(), key=lambda item: item[1], reverse=True)
    top_family, top_score = sorted_scores[0]
    if len(sorted_scores) > 1 and sorted_scores[1][1] == top_score:
        all_hits = tuple(_stable_names([*registration_hits, *compliance_hits, *system_hits]))
        confidence = min(0.75, 0.35 + 0.1 * float(top_score))
        return AdministrativeMissingnessScenarioFamily.HYBRID, confidence, all_hits
    hits_map = {
        AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED: registration_hits,
        AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED: compliance_hits,
        AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED: system_hits,
    }
    confidence = min(0.85, 0.35 + 0.15 * float(top_score))
    return top_family, confidence, tuple(_stable_names(hits_map[top_family]))


def _operational_status_override(
    *,
    scenario_class: AdministrativeMissingnessClass,
    metadata: AdministrativeMissingnessMetadata | None,
    current_status: MissingnessAssessmentStatus,
    missing_requirement_names: tuple[str, ...],
) -> MissingnessAssessmentStatus:
    if current_status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
        return current_status

    if scenario_class is AdministrativeMissingnessClass.RETENTION_EXPIRED:
        if metadata is None or metadata.retention_window_observed is not True:
            return MissingnessAssessmentStatus.NOT_RECOVERABLE
        return MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE

    if scenario_class is AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION:
        if "legal_rule_observed" in missing_requirement_names:
            return MissingnessAssessmentStatus.UNKNOWN
        return MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE

    if scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        if "matured_cohorts_observed" in missing_requirement_names:
            return MissingnessAssessmentStatus.UNKNOWN
        return MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE

    if scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        if "validation_subset_available" in missing_requirement_names:
            return MissingnessAssessmentStatus.UNKNOWN
        return MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE

    if scenario_class is AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED:
        return MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE

    if scenario_class is AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK:
        if metadata is not None and metadata.bridge_window_observed is False:
            return MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE

    return current_status


def _risk_level_for_status(status: MissingnessAssessmentStatus) -> str:
    if status is MissingnessAssessmentStatus.RECOVERABLE:
        return "low"
    if status is MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE:
        return "medium"
    if status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
        return "high"
    return "unknown"


def _identifiable_for_status(status: MissingnessAssessmentStatus) -> bool | None:
    if status is MissingnessAssessmentStatus.RECOVERABLE:
        return True
    if status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
        return False
    return None


def _estimands_at_risk(
    *,
    metadata: AdministrativeMissingnessMetadata | None,
    scenario_class: AdministrativeMissingnessClass,
    status: MissingnessAssessmentStatus,
    query_variables: frozenset[str],
) -> tuple[MissingnessEstimandRisk, ...]:
    target_variables = (
        tuple(metadata.target_variables)
        if metadata is not None and metadata.target_variables
        else tuple(sorted(query_variables))
    )
    scope = _CLASS_ESTIMAND_SCOPE.get(scenario_class, "analysis_population")
    return tuple(
        MissingnessEstimandRisk(
            name=f"E[{variable}]",
            scope=scope,
            identifiable=_identifiable_for_status(status),
            risk_level=_risk_level_for_status(status),
        )
        for variable in target_variables
    )


def _identification_assumptions_for_assessment(
    *,
    metadata: AdministrativeMissingnessMetadata | None,
    scenario_family: AdministrativeMissingnessScenarioFamily,
    scenario_class: AdministrativeMissingnessClass,
    target_variables: tuple[str, ...],
) -> tuple[str, ...]:
    assumptions: list[str] = []
    if scenario_family is AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED:
        indicator = metadata.registration_indicator if metadata else "registration_indicator"
        drivers = (
            ", ".join(metadata.eligibility_covariates) if metadata else "eligibility_covariates"
        )
        for target in target_variables:
            assumptions.append(f"{target} ⟂ {indicator} | {drivers}")
        assumptions.append(f"0 < P({indicator}=1 | {drivers}) < 1")
    elif scenario_family is AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED:
        indicator = metadata.compliance_indicator if metadata else "compliance_indicator"
        drivers = (
            ", ".join(metadata.compliance_driver_covariates)
            if metadata
            else "compliance_driver_covariates"
        )
        for target in target_variables:
            assumptions.append(f"{target} ⟂ {indicator} | {drivers}")
        assumptions.append(f"0 < P({indicator}=1 | {drivers}) < 1")
    elif scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        drivers = (
            ", ".join(metadata.identifier_quality_covariates)
            if metadata and metadata.identifier_quality_covariates
            else "identifier_quality_covariates"
        )
        for target in target_variables:
            assumptions.append(f"{target} ⟂ link_success | {drivers}")
        assumptions.append("0 < P(link_success=1 | identifier_quality_covariates) < 1")
    elif scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        drivers = (
            ", ".join(_stable_names([metadata.time_variable, *metadata.processing_lag_covariates]))
            if metadata
            else "time, backlog_covariates"
        )
        for target in target_variables:
            assumptions.append(f"{target} ⟂ R_{target} | {drivers}")
    elif scenario_class in {
        AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED,
        AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK,
    }:
        drivers = (
            ", ".join(
                _stable_names(
                    [
                        metadata.system_version_variable,
                        metadata.time_variable,
                        *metadata.rollout_covariates,
                        *metadata.office_availability_covariates,
                    ]
                )
            )
            if metadata
            else "system_or_service_covariates"
        )
        for target in target_variables:
            assumptions.append(f"{target} ⟂ R_{target} | {drivers}")
    return tuple(_stable_names(assumptions))


def _testable_implications_for_assessment(
    *,
    metadata: AdministrativeMissingnessMetadata | None,
    scenario_class: AdministrativeMissingnessClass,
    scenario_family: AdministrativeMissingnessScenarioFamily,
) -> tuple[str, ...]:
    implications: list[str] = []
    if scenario_family is AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED:
        implications.extend(
            ("registration_indicator_observed", "population_frame_coverage_audited")
        )
    if scenario_family is AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED:
        implications.extend(("process_log_sequence_complete", "compliance_indicator_observed"))
    if scenario_class is AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED:
        implications.extend(("office_availability_logged", "outage_windows_declared"))
    if scenario_class is AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK:
        implications.extend(("bridge_window_or_dual_run_available", "pre_post_consistency_checked"))
    if scenario_class is AdministrativeMissingnessClass.RETENTION_EXPIRED:
        implications.extend(("retention_boundary_declared", "disappearingness_monotone"))
    if scenario_class is AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION:
        implications.extend(("access_rule_deterministic", "redaction_rule_matches_payload"))
    if scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        implications.extend(("revision_curve_monotone", "matured_cohorts_tracked"))
    if scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        implications.extend(("linkage_precision_estimated", "validation_subset_available"))
    if metadata is not None and metadata.bridge_window_observed is True:
        implications.append("bridge_window_observed")
    if metadata is not None and metadata.validation_subset_available is True:
        implications.append("validation_subset_available")
    return tuple(_stable_names(implications))


def _evidence_for_assessment(
    metadata: AdministrativeMissingnessMetadata | None,
) -> tuple[MissingnessEvidenceItem, ...]:
    if metadata is None:
        return ()
    return tuple(
        MissingnessEvidenceItem(type="artifact", ref=ref, quality="medium")
        for ref in metadata.evidence_refs
    )


def _provenance_for_assessment(
    *,
    graph: Any,
    metadata: AdministrativeMissingnessMetadata | None,
) -> MissingnessAssessmentProvenance:
    graph_metadata = getattr(graph, "metadata", {}) or {}
    return MissingnessAssessmentProvenance(
        source_system=metadata.source_system if metadata else None,
        extract_ts=metadata.extract_ts if metadata else None,
        policy_version=metadata.policy_version if metadata else None,
        linkage_run_id=metadata.linkage_run_id if metadata else None,
        retention_schedule_id=metadata.retention_schedule_id if metadata else None,
        assessment_method="assess_administrative_missingness",
        code_commit=str(graph_metadata.get("code_commit") or "") or None,
        mgraph_fingerprint=str(graph_metadata.get("mgraph_fingerprint") or "") or None,
    )


def _recommended_method_stack_for_assessment(
    *,
    scenario_class: AdministrativeMissingnessClass,
    scenario_family: AdministrativeMissingnessScenarioFamily,
    status: MissingnessAssessmentStatus,
) -> tuple[str, ...]:
    methods: list[str]
    if scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        methods = [
            "probabilistic_linkage_with_uncertainty",
            "ipw_on_link_success",
            "sensitivity_bounds",
        ]
    elif scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        methods = ["lag_adjusted_ipw", "nowcasting", "revision_aware_bounds"]
    elif scenario_class is AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION:
        methods = ["restricted_domain_weighting", "partial_identification_bounds"]
    elif scenario_class is AdministrativeMissingnessClass.RETENTION_EXPIRED:
        methods = ["restricted_estimand", "monotone_bounds"]
    elif scenario_class in {
        AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED,
        AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK,
    }:
        methods = ["bridge_reweighting", "harmonisation", "bounds"]
    elif scenario_family is AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED:
        methods = ["ipw", "doubly_robust", "pattern_mixture", "sensitivity_analysis"]
    else:
        methods = ["ipw", "aipw", "selection_model", "bounds"]

    if status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
        return tuple(method for method in methods if "bounds" in method or "restricted" in method)
    if status is MissingnessAssessmentStatus.UNKNOWN:
        methods.append("collect_more_process_metadata")
    return tuple(_stable_names(methods))


def _sensitivity_plan_for_assessment(
    *,
    scenario_class: AdministrativeMissingnessClass,
    status: MissingnessAssessmentStatus,
) -> tuple[str, ...]:
    if status is MissingnessAssessmentStatus.RECOVERABLE:
        return ()
    if scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        return ("Run linkage-rule perturbations and report bounded estimates.",)
    if scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        return ("Publish revision-aware intervals until matured cohorts close the lag.",)
    if scenario_class is AdministrativeMissingnessClass.RETENTION_EXPIRED:
        return ("Restrict the estimand to the retention window or report monotone bounds.",)
    return ("Escalate to bounds or sensitivity analysis if point identification fails.",)


def _target_population_after_restriction(
    *,
    scenario_class: AdministrativeMissingnessClass,
    metadata: AdministrativeMissingnessMetadata | None,
) -> str | None:
    if scenario_class is AdministrativeMissingnessClass.RETENTION_EXPIRED:
        return "Units whose event times fall inside the observed retention window."
    if scenario_class is AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION:
        return "Units permitted by the declared access and redaction rule."
    if scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        return "Units linkable under the declared identifier-quality regime."
    if scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        return "Units observed by the current extract date after accounting for reporting lag."
    if metadata is not None and metadata.population_frame_observed is False:
        return "Registered or observed-frame units only; non-registered eligible units remain external."
    return None


def _recommendations_for_assessment(
    *,
    metadata: AdministrativeMissingnessMetadata | None,
    scenario_family: AdministrativeMissingnessScenarioFamily,
    scenario_class: AdministrativeMissingnessClass,
    missing_requirement_names: tuple[str, ...],
    recoverability_status: str,
    selection_only_registration: bool,
    testability_invalid: bool,
) -> tuple[str, ...]:
    recommendations: list[str] = []
    if scenario_class in {
        AdministrativeMissingnessClass.REGISTRATION_NOT_APPLIED,
        AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED,
    }:
        if "registration_indicator" in missing_requirement_names:
            recommendations.append(
                "Add a fully observed registration/apply flag and declare registration_flag -> R_X."
            )
        if "population_frame_observed" in missing_requirement_names or selection_only_registration:
            recommendations.append(
                "Log registration status for non-registered units to distinguish missing objects from missing attributes."
            )
        if "eligibility_covariates" in missing_requirement_names:
            recommendations.append(
                "Record eligibility or queue covariates that drive registration before treating the pattern as recoverable."
            )
    elif scenario_class is AdministrativeMissingnessClass.COMPLIANCE_NOT_COMPLETED:
        if "compliance_indicator" in missing_requirement_names:
            recommendations.append(
                "Model compliance status C explicitly and declare C -> R_X for affected fields."
            )
        if "compliance_driver_covariates" in missing_requirement_names:
            recommendations.append(
                "Add deadlines, sanctions, or service-access covariates that explain compliance."
            )
    elif scenario_class is AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED:
        if "office_availability_covariates" in missing_requirement_names:
            recommendations.append(
                "Record outage windows, office availability, and service-channel metadata before certifying recoverability."
            )
    elif scenario_class is AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK:
        if "system_version_or_time" in missing_requirement_names:
            recommendations.append(
                "Add a system_version or time variable and declare it as a parent of the affected R-nodes."
            )
        if "rollout_covariates" in missing_requirement_names:
            recommendations.append(
                "Record rollout covariates such as region or office type to separate migration effects from latent selection."
            )
        if "bridge_window_observed" in missing_requirement_names:
            recommendations.append(
                "Persist dual-run or overlap-window evidence before treating schema changes as harmonised."
            )
    elif scenario_class is AdministrativeMissingnessClass.RETENTION_EXPIRED:
        recommendations.append(
            "Restrict the estimand to the retention window unless an external archive or snapshot history is available."
        )
    elif scenario_class is AdministrativeMissingnessClass.LEGAL_RESTRICTION_OR_REDACTION:
        if "legal_rule_observed" in missing_requirement_names:
            recommendations.append(
                "Persist the legal or access-control rule that drives redaction before claiming partial recoverability."
            )
    elif scenario_class is AdministrativeMissingnessClass.PROCESSING_BACKLOG_OR_REPORTING_LAG:
        if "processing_lag_covariates" in missing_requirement_names:
            recommendations.append(
                "Store batch, workload, and extract-timing covariates so lagged observations can be modelled."
            )
        if "matured_cohorts_observed" in missing_requirement_names:
            recommendations.append(
                "Retain matured cohorts or revision histories to calibrate nowcasts for delayed administrative updates."
            )
    elif scenario_class is AdministrativeMissingnessClass.LINKAGE_FAILURE:
        if "identifier_quality_covariates" in missing_requirement_names:
            recommendations.append(
                "Capture identifier-quality covariates and linkage diagnostics before treating link success as ignorable."
            )
        if "validation_subset_available" in missing_requirement_names:
            recommendations.append(
                "Create a validation subset or clerical-review sample; otherwise fall back to bounds for linkage bias."
            )
    elif scenario_family is AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED:
        if "system_version_or_time" in missing_requirement_names:
            recommendations.append(
                "Add a system_version or time variable and declare it as a parent of the affected R-nodes."
            )
    elif scenario_family is AdministrativeMissingnessScenarioFamily.UNKNOWN:
        recommendations.append(
            "Annotate the M-graph with administrative missingness metadata to classify registration, compliance, or system-change processes."
        )
    elif scenario_family is AdministrativeMissingnessScenarioFamily.HYBRID:
        recommendations.append(
            "Decompose the hybrid missingness process into explicit registration/compliance/system-change components in graph metadata."
        )

    if recoverability_status == "not_recoverable":
        recommendations.append(
            "Remove or justify self-censoring paths X -> ... -> R_X, or collect administrative drivers that block those paths."
        )
    if metadata is not None and metadata.notes:
        recommendations.append(f"Documented administrative note: {metadata.notes}")
    if testability_invalid:
        recommendations.append(
            "Revisit the administrative M-graph: one or more testable missingness implications failed on observed data."
        )

    return tuple(_stable_names(recommendations))


def _stable_names(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _normalize_var_set(payload: Any) -> frozenset[str]:
    if payload in (None, "", ()):
        return frozenset()
    if isinstance(payload, (list, tuple, set, frozenset)):
        return frozenset(str(item) for item in payload if str(item).strip())
    text = str(payload).strip()
    if not text:
        return frozenset()
    return frozenset({text})


def assess_administrative_missingness(
    *,
    graph: Any,
    data: Mapping[str, Any] | np.ndarray | None = None,
    mgraph_meta: Any | None = None,
    query_variables: frozenset[str] | None = None,
    treatment: Any | None = None,
    outcome: Any | None = None,
    max_conditioning_set_size: int = 2,
    dp_context: Mapping[str, Any] | None = None,
    judge_threshold_registry_root: str | None = None,
    readiness_target: str = "diagnostic",
) -> MissingnessAssessmentReport:
    """Assess recoverability/testability for common administrative missingness patterns."""
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        full_law_identify,
        test_recoverability,
    )
    from polisyos.ir.analytics.causal_graph import CausalGraphModel
    from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

    parsed_graph = CausalGraphModel.model_validate(graph) if isinstance(graph, dict) else graph
    meta = mgraph_meta or extract_mgraph_metadata(parsed_graph)
    administrative_meta = extract_administrative_missingness_metadata(parsed_graph)
    scenario_family, scenario_confidence, inferred_covariates = _infer_scenario_family(
        graph=parsed_graph,
        metadata=administrative_meta,
    )
    scenario_class, missingness_direction, missingness_unit_scope = _infer_operational_missingness(
        metadata=administrative_meta,
        scenario_family=scenario_family,
    )
    requirement_names, requirement_vars = _scenario_requirements(
        administrative_meta,
        scenario_family,
        scenario_class,
    )
    available_nodes = set(parsed_graph.nodes)
    if isinstance(data, Mapping):
        available_nodes.update(str(key) for key in data.keys())

    present_covariates: list[str] = []
    missing_covariates: list[str] = []
    missing_requirement_names: list[str] = []
    for requirement in requirement_names:
        if requirement in _BOOLEAN_REQUIREMENT_FIELDS:
            field_name = _BOOLEAN_REQUIREMENT_FIELDS[requirement]
            if administrative_meta is None or getattr(administrative_meta, field_name) is not True:
                missing_requirement_names.append(requirement)
            continue
        required_vars = tuple(requirement_vars.get(requirement, ()))
        if not required_vars:
            missing_requirement_names.append(requirement)
            continue
        present = [var for var in required_vars if var in available_nodes]
        absent = [var for var in required_vars if var not in available_nodes]
        if not present and required_vars:
            missing_requirement_names.append(requirement)
        present_covariates.extend(present)
        missing_covariates.extend(absent)

    if not present_covariates:
        present_covariates.extend(str(item) for item in inferred_covariates if item)

    resolved_query_vars = (
        frozenset(query_variables)
        if query_variables is not None
        else frozenset(meta.substantive_vars)
    )
    resolved_target_variables = (
        tuple(administrative_meta.target_variables)
        if administrative_meta is not None and administrative_meta.target_variables
        else tuple(sorted(resolved_query_vars))
    )
    recoverability_result = test_recoverability(
        query_vars=resolved_query_vars,
        graph=parsed_graph,
        mgraph_meta=meta,
    )
    recoverability_summary = MissingnessRecoverabilitySummary(
        status=recoverability_result.status.value,
        query_variables=tuple(sorted(recoverability_result.query_variables)),
        blocking_r_nodes=tuple(sorted(recoverability_result.blocking_r_nodes)),
        proof_steps=tuple(
            MissingnessProofStep(
                rule_name=str(step.rule_name),
                antecedent_vars=tuple(str(item) for item in getattr(step, "antecedent_vars", ())),
                consequent_vars=tuple(str(item) for item in getattr(step, "consequent_vars", ())),
                applied_to_graph_state=str(getattr(step, "applied_to_graph_state", "")),
                depth=int(getattr(step, "depth", 0)),
            )
            for step in recoverability_result.proof_steps
        ),
        algorithm_version=str(recoverability_result.algorithm_version),
    )

    testability_audit: MissingnessTestabilityAudit | None = None
    testability_invalid = False
    if data is not None:
        try:
            test_report = test_mgraph_implications(
                graph=parsed_graph,
                mgraph_meta=meta,
                data=data,
                max_conditioning_set_size=max_conditioning_set_size,
                dp_context=dp_context,
                judge_threshold_registry_root=judge_threshold_registry_root,
                readiness_target=readiness_target,
            )
            testability_invalid = not bool(test_report.overall_valid)
            testability_audit = MissingnessTestabilityAudit(
                overall_valid=bool(test_report.overall_valid),
                implications_tested=int(test_report.implications_tested),
                implications_failed=tuple(
                    MissingnessImplicationFailure(
                        x=item.x,
                        y=item.y,
                        z=item.z,
                        adjusted_p_value=float(adj_p),
                    )
                    for item, adj_p in test_report.implications_failed
                ),
                warnings=tuple(str(item) for item in test_report.warnings),
            )
        except Exception as exc:
            testability_audit = MissingnessTestabilityAudit(
                overall_valid=False,
                implications_tested=0,
                implications_failed=(),
                warnings=(f"implication_test_failed:{exc}",),
            )
            testability_invalid = True

    treatment_set = _normalize_var_set(treatment)
    outcome_set = _normalize_var_set(outcome)
    if treatment_set and outcome_set:
        try:
            full_law_result = full_law_identify(
                treatment=treatment_set,
                outcome=outcome_set,
                graph=parsed_graph,
                mgraph_meta=meta,
            )
            metadata_payload_full_law = {
                "status": str(
                    getattr(
                        getattr(full_law_result, "status", None),
                        "value",
                        getattr(full_law_result, "status", ""),
                    )
                ),
                "treatment": sorted(treatment_set),
                "outcome": sorted(outcome_set),
                "algorithm_version": str(getattr(full_law_result, "algorithm_version", "") or ""),
                "trace": list(getattr(full_law_result, "trace", []) or []),
                "proof_steps": [
                    {
                        "rule_name": str(getattr(step, "rule_name", "")),
                        "depth": int(getattr(step, "depth", 0)),
                    }
                    for step in list(getattr(full_law_result, "proof_steps", []) or [])
                ],
                "identified": (
                    str(
                        getattr(
                            getattr(full_law_result, "status", None),
                            "value",
                            getattr(full_law_result, "status", ""),
                        )
                    )
                    .strip()
                    .lower()
                    == "identified"
                ),
            }
        except Exception as exc:
            metadata_payload_full_law = {
                "status": "assessment_failed",
                "treatment": sorted(treatment_set),
                "outcome": sorted(outcome_set),
                "identified": False,
                "error": str(exc),
            }
    else:
        metadata_payload_full_law = None

    selection_only_registration = (
        scenario_family is AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED
        and administrative_meta is not None
        and administrative_meta.population_frame_observed is False
    )

    if recoverability_result.status.value == "not_recoverable":
        status = MissingnessAssessmentStatus.NOT_RECOVERABLE
    elif scenario_family is AdministrativeMissingnessScenarioFamily.UNKNOWN:
        status = MissingnessAssessmentStatus.UNKNOWN
    elif selection_only_registration:
        status = MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE
    elif missing_requirement_names:
        status = MissingnessAssessmentStatus.UNKNOWN
    else:
        status = MissingnessAssessmentStatus.RECOVERABLE

    status = _operational_status_override(
        scenario_class=scenario_class,
        metadata=administrative_meta,
        current_status=status,
        missing_requirement_names=tuple(_stable_names(missing_requirement_names)),
    )

    recommendations = _recommendations_for_assessment(
        metadata=administrative_meta,
        scenario_family=scenario_family,
        scenario_class=scenario_class,
        missing_requirement_names=tuple(_stable_names(missing_requirement_names)),
        recoverability_status=recoverability_result.status.value,
        selection_only_registration=selection_only_registration,
        testability_invalid=testability_invalid,
    )

    estimands_at_risk = _estimands_at_risk(
        metadata=administrative_meta,
        scenario_class=scenario_class,
        status=status,
        query_variables=resolved_query_vars,
    )
    identification_assumptions = _identification_assumptions_for_assessment(
        metadata=administrative_meta,
        scenario_family=scenario_family,
        scenario_class=scenario_class,
        target_variables=resolved_target_variables,
    )
    testable_implications_declared = _testable_implications_for_assessment(
        metadata=administrative_meta,
        scenario_class=scenario_class,
        scenario_family=scenario_family,
    )
    evidence = _evidence_for_assessment(administrative_meta)
    provenance = _provenance_for_assessment(
        graph=parsed_graph,
        metadata=administrative_meta,
    )
    recommended_method_stack = _recommended_method_stack_for_assessment(
        scenario_class=scenario_class,
        scenario_family=scenario_family,
        status=status,
    )
    sensitivity_plan = _sensitivity_plan_for_assessment(
        scenario_class=scenario_class,
        status=status,
    )
    target_population_after_restriction = _target_population_after_restriction(
        scenario_class=scenario_class,
        metadata=administrative_meta,
    )

    metadata_payload: dict[str, Any] = {
        "mgraph_fingerprint": parsed_graph.metadata.get("mgraph_fingerprint"),
        "selection_only_registration": selection_only_registration,
    }
    if metadata_payload_full_law is not None:
        metadata_payload["full_law_identification"] = metadata_payload_full_law
    if administrative_meta is not None:
        metadata_payload["administrative_missingness"] = administrative_meta.model_dump(mode="json")

    return MissingnessAssessmentReport(
        status=status,
        scenario_family=scenario_family,
        scenario_class=scenario_class,
        missingness_direction=missingness_direction,
        missingness_unit_scope=missingness_unit_scope,
        scenario_confidence=scenario_confidence,
        administrative_covariates_present=tuple(_stable_names(present_covariates)),
        administrative_covariates_missing=tuple(_stable_names(missing_covariates)),
        key_variables=tuple(sorted(resolved_query_vars)),
        proof_kernel_requirements=tuple(requirement_names),
        mgraph_ref=str(
            parsed_graph.metadata.get("mgraph_fingerprint")
            or parsed_graph.metadata.get("graph_ref")
            or ""
        )
        or None,
        recoverability=recoverability_summary,
        testability_audit=testability_audit,
        estimands_at_risk=estimands_at_risk,
        identification_assumptions=identification_assumptions,
        testable_implications_declared=testable_implications_declared,
        evidence=evidence,
        provenance=provenance,
        recommended_method_stack=recommended_method_stack,
        sensitivity_plan=sensitivity_plan,
        target_population_after_restriction=target_population_after_restriction,
        recommendations=recommendations,
        metadata=metadata_payload,
    )


# ---------------------------------------------------------------------------
# AdministrativeMissingnessAssessment
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "administrative-missingness", "m-graph", "structural"},
)
class AdministrativeMissingnessAssessment:
    """Assess administrative missingness patterns and recoverability for an M-graph."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="administrative_missingness_assessment",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({_json_slot("mgraph_data")}),
        output_slots=frozenset({_json_slot("assessment_report")}),
        parameters=(
            ParameterSpec(name="query_variables", default=[]),
            ParameterSpec(name="treatment", default=[]),
            ParameterSpec(name="outcome", default=[]),
            ParameterSpec(name="max_conditioning_set_size", default=2),
            ParameterSpec(name="dp_context", default=None),
            ParameterSpec(name="judge_threshold_registry_root", default=None),
            ParameterSpec(name="readiness_target", default="diagnostic"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Classify registration/compliance/system-change missingness patterns, "
            "run M-graph recoverability, and optionally audit testable implications."
        ),
        tags=frozenset(
            {
                "causal",
                "missing-data",
                "administrative-missingness",
                "recoverability",
                "m-graph",
                "readiness",
                "structural",
            }
        ),
        citations=(
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing Missing Data.",
            "Nabi, R., Bhattacharya, R. & Shpitser, I. (2020). Full law identification in graphical models of missing data.",
        ),
        equations={
            "recoverability": "P(S) recoverable iff R_{V_i} ∉ desc(V_i) for all V_i in S",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "When administrative data missingness needs a typed scenario assessment "
            "before causal execution or governance gating."
        ),
        when_not_to_use="When the graph is not an M-graph or no missingness modeling is intended.",
        output_interpretation=(
            "assessment_report summarizes the scenario family, proof-kernel requirements, "
            "recoverability status, and optional testability/full-law diagnostics."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = CausalGraphModel.model_validate(raw) if isinstance(raw, dict) else raw
        data = state.get("data")
        meta = extract_mgraph_metadata(graph)
        report = assess_administrative_missingness(
            graph=graph,
            data=data,
            mgraph_meta=meta,
            query_variables=(
                frozenset(params.get("query_variables", ()))
                if params.get("query_variables")
                else None
            ),
            treatment=params.get("treatment"),
            outcome=params.get("outcome"),
            max_conditioning_set_size=int(params.get("max_conditioning_set_size", 2)),
            dp_context=params.get("dp_context"),
            judge_threshold_registry_root=params.get("judge_threshold_registry_root"),
            readiness_target=str(params.get("readiness_target", "diagnostic")),
        )
        return {"assessment_report": report.model_dump(mode="json")}


def _observed_nodes(graph: Any, mgraph_meta: Any) -> list[str]:
    """Return nodes that are observable in the M-graph."""
    observed: set[str] = set(mgraph_meta.fully_observed_vars)
    observed.update(pn.proxy_name for pn in mgraph_meta.proxy_nodes)
    observed.update(f"R_{rn.target_variable}" for rn in mgraph_meta.r_nodes)
    return sorted(node for node in observed if node in set(graph.nodes))


def _bh_adjust(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg p-value adjustment."""
    if not p_values:
        return []
    n = len(p_values)
    order = np.argsort(np.asarray(p_values, dtype=float))
    adjusted = np.empty(n, dtype=float)
    running = 1.0
    for rank in range(n - 1, -1, -1):
        idx = int(order[rank])
        raw = float(p_values[idx])
        candidate = min(1.0, raw * n / float(rank + 1))
        running = min(running, candidate)
        adjusted[idx] = running
    return [float(v) for v in adjusted]


def _coerce_series(values: Any) -> np.ndarray:
    """Convert a dataset column to a 1D numeric vector."""
    arr = np.asarray(values)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    if arr.dtype.kind in {"O", "U", "S"}:
        _, inverse = np.unique(arr.astype(str), return_inverse=True)
        return inverse.astype(float)
    return arr.astype(float)


def _raw_series(values: Any) -> np.ndarray:
    """Return a 1D raw series without coercing categorical values."""
    arr = np.asarray(values)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    return arr


def _is_missing_scalar(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)):
        return bool(np.isnan(value))
    return False


def _complete_case_mask(columns: list[np.ndarray]) -> np.ndarray:
    """Mask rows that are present across every supplied raw series."""
    if not columns:
        raise ValueError("At least one column is required")
    n = len(columns[0])
    mask = np.ones(n, dtype=bool)
    for column in columns:
        arr = np.asarray(column)
        if len(arr) != n:
            raise ValueError("Implication test columns must have matching length")
        if arr.dtype.kind in {"f"}:
            mask &= np.isfinite(arr)
        elif arr.dtype.kind in {"i", "u", "b"}:
            mask &= True
        else:
            mask &= np.array([not _is_missing_scalar(value) for value in arr], dtype=bool)
    return mask


def _series_kind(raw: np.ndarray) -> str:
    """Infer whether a series should be treated as continuous or categorical."""
    arr = np.asarray(raw)
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    if arr.size == 0:
        return "categorical"
    if arr.dtype.kind in {"O", "U", "S", "b"}:
        return "categorical"

    finite = arr[np.isfinite(arr)] if arr.dtype.kind == "f" else arr
    if finite.size == 0:
        return "categorical"
    unique = np.unique(finite)
    if unique.size <= 12 and np.allclose(unique, np.round(unique)):
        return "categorical"
    return "continuous"


def _encode_for_kernel(raw: np.ndarray) -> np.ndarray:
    """Encode a series as a numeric design matrix for kernel-based tests."""
    arr = np.asarray(raw)
    if arr.ndim != 1:
        raise ValueError("Each data column must be one-dimensional")
    if _series_kind(arr) == "categorical":
        labels = arr.astype(str)
        _, inverse = np.unique(labels, return_inverse=True)
        return np.eye(int(np.max(inverse)) + 1, dtype=float)[inverse]
    return arr.astype(float).reshape(-1, 1)


def _build_contingency_table(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, int, int]:
    x_labels, x_codes = np.unique(x.astype(str), return_inverse=True)
    y_labels, y_codes = np.unique(y.astype(str), return_inverse=True)
    table = np.zeros((len(x_labels), len(y_labels)), dtype=int)
    np.add.at(table, (x_codes, y_codes), 1)
    return table, len(x_labels), len(y_labels)


def _g_test_from_table(table: np.ndarray) -> tuple[float, float, dict[str, Any]]:
    from scipy.stats import chi2, chi2_contingency

    if table.ndim != 2:
        raise ValueError("Contingency table must be 2D")
    if table.shape[0] < 2 or table.shape[1] < 2 or int(table.sum()) == 0:
        return 0.0, 1.0, {"degrees_of_freedom": 0, "degenerate": True}

    try:
        statistic, _, dof, _ = chi2_contingency(table, correction=False, lambda_="log-likelihood")
    except ValueError:
        return 0.0, 1.0, {"degrees_of_freedom": 0, "degenerate": True}

    if dof <= 0:
        return 0.0, 1.0, {"degrees_of_freedom": int(dof), "degenerate": True}
    p_value = float(chi2.sf(float(statistic), int(dof)))
    return float(statistic), p_value, {"degrees_of_freedom": int(dof), "degenerate": False}


def _conditional_g_test(
    x: np.ndarray, y: np.ndarray, z: np.ndarray
) -> tuple[float, float, dict[str, Any]]:
    if z.ndim == 1:
        z = z[:, None]
    strata: dict[tuple[str, ...], list[int]] = {}
    for idx, row in enumerate(z):
        strata.setdefault(tuple(row.astype(str).tolist()), []).append(idx)

    total_statistic = 0.0
    total_dof = 0
    valid_strata = 0
    skipped_strata = 0
    for indices in strata.values():
        x_slice = x[indices]
        y_slice = y[indices]
        table, _, _ = _build_contingency_table(x_slice, y_slice)
        statistic, _, meta = _g_test_from_table(table)
        if meta.get("degenerate"):
            skipped_strata += 1
            continue
        valid_strata += 1
        total_statistic += statistic
        total_dof += int(meta["degrees_of_freedom"])

    if total_dof <= 0 or valid_strata == 0:
        return (
            0.0,
            1.0,
            {
                "degrees_of_freedom": 0,
                "valid_strata": valid_strata,
                "skipped_strata": skipped_strata,
                "degenerate": True,
            },
        )

    from scipy.stats import chi2

    p_value = float(chi2.sf(float(total_statistic), total_dof))
    return (
        float(total_statistic),
        p_value,
        {
            "degrees_of_freedom": int(total_dof),
            "valid_strata": valid_strata,
            "skipped_strata": skipped_strata,
            "degenerate": False,
        },
    )


def _mixed_kernel_test(
    *,
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray | None,
    alpha: float,
    dp_context: Mapping[str, Any] | None = None,
    judge_threshold_registry_root: str | None = None,
    readiness_target: str = "diagnostic",
) -> dict[str, Any]:
    """Approximate mixed-data CI via kernel tests on encoded columns."""
    from polisyos.foundry.methods.catalog.causal.independence_tests import (
        HSICIndependenceTest,
        KCIConditionalTest,
    )

    x_enc = _encode_for_kernel(x)
    y_enc = _encode_for_kernel(y)

    if z is None or z.size == 0:
        raw = HSICIndependenceTest.pure_step(
            {"X": x_enc, "Y": y_enc},
            {
                "alpha": alpha,
                "n_bootstrap": 99,
                "dp_context": dp_context,
                "judge_threshold_registry_root": judge_threshold_registry_root,
                "readiness_target": readiness_target,
            },
        )["result"]
        return {
            "test_name": "hsic_mixed",
            "statistic": float(raw["statistic"]),
            "p_value": float(raw["p_value"]),
            "passed": bool(raw["passed"]),
            "critical_value": float(raw["critical_value"]),
            "alpha": float(raw.get("alpha", alpha)),
            "critical_statistic_value": float(
                raw.get("critical_statistic_value", raw["critical_value"])
            ),
            "calibration_mode": raw.get("calibration_mode"),
            "dp_context_summary": raw.get("dp_context_summary"),
            "naive_fpr_inflation_bound": raw.get("naive_fpr_inflation_bound"),
            "metadata": {
                **dict(raw.get("metadata", {})),
                **{
                    key: raw[key]
                    for key in (
                        "alpha",
                        "critical_value",
                        "critical_statistic_value",
                        "calibration_mode",
                        "dp_context_summary",
                        "naive_fpr_inflation_bound",
                    )
                    if raw.get(key) is not None
                },
                "route": "hsic_mixed",
                "approximation": "kernel_mixed_marginal",
            },
        }

    z_enc = np.column_stack([_encode_for_kernel(z[:, idx]) for idx in range(z.shape[1])])
    raw = KCIConditionalTest.pure_step(
        {"X": x_enc, "Y": y_enc, "Z": z_enc},
        {
            "alpha": alpha,
            "n_bootstrap": 99,
            "ridge": 1e-2,
            "dp_context": dp_context,
            "judge_threshold_registry_root": judge_threshold_registry_root,
            "readiness_target": readiness_target,
        },
    )["result"]
    return {
        "test_name": "kci_mixed",
        "statistic": float(raw["statistic"]),
        "p_value": float(raw["p_value"]),
        "passed": bool(raw["passed"]),
        "critical_value": float(raw["critical_value"]),
        "alpha": float(raw.get("alpha", alpha)),
        "critical_statistic_value": float(
            raw.get("critical_statistic_value", raw["critical_value"])
        ),
        "calibration_mode": raw.get("calibration_mode"),
        "dp_context_summary": raw.get("dp_context_summary"),
        "naive_fpr_inflation_bound": raw.get("naive_fpr_inflation_bound"),
        "metadata": {
            **dict(raw.get("metadata", {})),
            **{
                key: raw[key]
                for key in (
                    "alpha",
                    "critical_value",
                    "critical_statistic_value",
                    "calibration_mode",
                    "dp_context_summary",
                    "naive_fpr_inflation_bound",
                )
                if raw.get(key) is not None
            },
            "route": "kci_mixed",
            "approximation": "kernel_conditional_independence",
        },
    }


def _get_column(
    data: Mapping[str, Any] | np.ndarray,
    variable: str,
    variable_order: tuple[str, ...] | None = None,
) -> np.ndarray:
    if isinstance(data, Mapping):
        if variable not in data:
            raise KeyError(f"Missing data column for variable {variable!r}")
        return _coerce_series(data[variable])
    if variable_order is None:
        raise ValueError("variable_order is required when data is provided as an ndarray")
    try:
        idx = variable_order.index(variable)
    except ValueError as exc:
        raise KeyError(f"Variable {variable!r} not present in variable_order") from exc
    return _coerce_series(data[:, idx])


def _raw_column(
    data: Mapping[str, Any] | np.ndarray,
    variable: str,
    variable_order: tuple[str, ...] | None = None,
) -> np.ndarray:
    """Return a raw 1D column while preserving categorical dtype information."""
    if isinstance(data, Mapping):
        if variable not in data:
            raise KeyError(f"Missing data column for variable {variable!r}")
        return _raw_series(data[variable])
    if variable_order is None:
        raise ValueError("variable_order is required when data is provided as an ndarray")
    try:
        idx = variable_order.index(variable)
    except ValueError as exc:
        raise KeyError(f"Variable {variable!r} not present in variable_order") from exc
    return _raw_series(data[:, idx])


def _minimal_separating_sets(
    *,
    graph: Any,
    observed_nodes: list[str],
    max_conditioning_set_size: int,
) -> list[ConditionalIndependence]:
    from polisyos.foundry.methods.catalog.causal.admg_ops import m_separation

    implications: list[ConditionalIndependence] = []
    for x, y in itertools.combinations(observed_nodes, 2):
        candidates = [node for node in observed_nodes if node not in {x, y}]
        found = False
        for size in range(0, min(max_conditioning_set_size, len(candidates)) + 1):
            for z in itertools.combinations(candidates, size):
                if m_separation(
                    graph,
                    x_set=frozenset({x}),
                    y_set=frozenset({y}),
                    z_set=frozenset(z),
                ):
                    implications.append(ConditionalIndependence(x=x, y=y, z=tuple(sorted(z))))
                    found = True
                    break
            if found:
                break
    # Deduplicate while preserving order
    seen: set[ConditionalIndependence] = set()
    deduped: list[ConditionalIndependence] = []
    for implication in implications:
        if implication in seen:
            continue
        seen.add(implication)
        deduped.append(implication)
    return deduped


def testable_implications(
    graph: Any,
    mgraph_meta: Any,
    *,
    max_conditioning_set_size: int = 2,
) -> list[ConditionalIndependence]:
    """Derive testable conditional independences from an M-graph."""
    observed = _observed_nodes(graph, mgraph_meta)
    return _minimal_separating_sets(
        graph=graph,
        observed_nodes=observed,
        max_conditioning_set_size=max_conditioning_set_size,
    )


def test_mgraph_implications(
    *,
    graph: Any,
    mgraph_meta: Any,
    data: Mapping[str, Any] | np.ndarray,
    implications: list[ConditionalIndependence] | None = None,
    alpha: float = 0.05,
    max_conditioning_set_size: int = 2,
    variable_order: tuple[str, ...] | None = None,
    dp_context: Mapping[str, Any] | None = None,
    judge_threshold_registry_root: str | None = None,
    readiness_target: str = "diagnostic",
) -> TestReport:
    """Run CI tests for all supplied or graph-derived M-graph implications."""
    from polisyos.foundry.methods.catalog.causal.independence_tests import (
        CategoricalConditionalIndependenceTest,
        PartialCorrelationTest,
    )

    if implications is None:
        implications = testable_implications(
            graph,
            mgraph_meta,
            max_conditioning_set_size=max_conditioning_set_size,
        )

    results: list[ImplicationTestResult] = []
    p_values: list[float] = []
    warnings: list[str] = []
    for implication in implications:
        raw_x = _raw_column(data, implication.x, variable_order)
        raw_y = _raw_column(data, implication.y, variable_order)
        raw_z_cols = [_raw_column(data, name, variable_order) for name in implication.z]
        all_columns = [raw_x, raw_y, *raw_z_cols]
        mask = _complete_case_mask(all_columns)
        if not np.any(mask):
            raise ValueError("Implication test has no complete cases")

        raw_x_obs = raw_x[mask]
        raw_y_obs = raw_y[mask]
        z_raw = np.column_stack([col[mask] for col in raw_z_cols]) if raw_z_cols else None
        x = _get_column(data, implication.x, variable_order)[mask]
        y = _get_column(data, implication.y, variable_order)[mask]
        z_numeric = (
            np.column_stack(
                [_get_column(data, name, variable_order)[mask] for name in implication.z]
            )
            if implication.z
            else None
        )
        x_kind = _series_kind(raw_x[mask])
        y_kind = _series_kind(raw_y[mask])
        z_kinds = tuple(_series_kind(col[mask]) for col in raw_z_cols)
        all_kinds = (x_kind, y_kind, *z_kinds)
        all_continuous = all(kind == "continuous" for kind in all_kinds)
        all_categorical = all(kind == "categorical" for kind in all_kinds)

        state: dict[str, Any]
        route: str
        if not implication.z:
            if all_categorical:
                categorical = CategoricalConditionalIndependenceTest.pure_step(
                    {"X": raw_x_obs, "Y": raw_y_obs},
                    {
                        "alpha": alpha,
                        "statistic_family": "g2",
                        "dp_context": dp_context,
                        "judge_threshold_registry_root": judge_threshold_registry_root,
                        "readiness_target": readiness_target,
                    },
                )["result"]
                raw = {
                    "test_name": "g_test",
                    "statistic": float(categorical["statistic"]),
                    "p_value": float(categorical["p_value"]),
                    "passed": bool(categorical["passed"]),
                    "critical_value": float(categorical["critical_value"]),
                    "metadata": {
                        **dict(categorical.get("metadata", {})),
                        **{
                            key: categorical[key]
                            for key in (
                                "alpha",
                                "critical_value",
                                "critical_statistic_value",
                                "calibration_mode",
                                "dp_context_summary",
                                "naive_fpr_inflation_bound",
                            )
                            if categorical.get(key) is not None
                        },
                        "route": "g_test",
                        "ci_test_impl": str(categorical["test_name"]),
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": (),
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "g_test"
            elif all_continuous:
                state = {"X": x, "Y": y}
                raw = PartialCorrelationTest.pure_step(
                    state,
                    {"alpha": alpha, "dp_context": dp_context},
                )["result"]
                raw = {
                    **raw,
                    "metadata": {
                        **dict(raw.get("metadata", {})),
                        "route": "partial_correlation",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": (),
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "partial_correlation"
            else:
                raw = _mixed_kernel_test(
                    x=x,
                    y=y,
                    z=None,
                    alpha=alpha,
                    dp_context=dp_context,
                    judge_threshold_registry_root=judge_threshold_registry_root,
                    readiness_target=readiness_target,
                )
                raw["metadata"] = {
                    **dict(raw.get("metadata", {})),
                    "x_kind": x_kind,
                    "y_kind": y_kind,
                    "conditioning_kinds": (),
                    "n_complete_cases": int(mask.sum()),
                }
                route = raw["test_name"]
        else:
            if all_categorical:
                categorical = CategoricalConditionalIndependenceTest.pure_step(
                    {"X": raw_x_obs, "Y": raw_y_obs, "Z": z_raw},
                    {
                        "alpha": alpha,
                        "statistic_family": "g2",
                        "dp_context": dp_context,
                        "judge_threshold_registry_root": judge_threshold_registry_root,
                        "readiness_target": readiness_target,
                    },
                )["result"]
                raw = {
                    "test_name": "conditional_g_test",
                    "statistic": float(categorical["statistic"]),
                    "p_value": float(categorical["p_value"]),
                    "passed": bool(categorical["passed"]),
                    "critical_value": float(categorical["critical_value"]),
                    "metadata": {
                        **dict(categorical.get("metadata", {})),
                        **{
                            key: categorical[key]
                            for key in (
                                "alpha",
                                "critical_value",
                                "critical_statistic_value",
                                "calibration_mode",
                                "dp_context_summary",
                                "naive_fpr_inflation_bound",
                            )
                            if categorical.get(key) is not None
                        },
                        "route": "conditional_g_test",
                        "ci_test_impl": str(categorical["test_name"]),
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": z_kinds,
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "conditional_g_test"
            elif all_continuous:
                state = {"X": x, "Y": y, "Z": z_numeric}
                raw = PartialCorrelationTest.pure_step(
                    state,
                    {"alpha": alpha, "dp_context": dp_context},
                )["result"]
                raw = {
                    **raw,
                    "metadata": {
                        **dict(raw.get("metadata", {})),
                        "route": "partial_correlation",
                        "x_kind": x_kind,
                        "y_kind": y_kind,
                        "conditioning_kinds": z_kinds,
                        "n_complete_cases": int(mask.sum()),
                    },
                }
                route = "partial_correlation"
            else:
                raw = _mixed_kernel_test(
                    x=x,
                    y=y,
                    z=z_numeric,
                    alpha=alpha,
                    dp_context=dp_context,
                    judge_threshold_registry_root=judge_threshold_registry_root,
                    readiness_target=readiness_target,
                )
                raw["metadata"] = {
                    **dict(raw.get("metadata", {})),
                    "x_kind": x_kind,
                    "y_kind": y_kind,
                    "conditioning_kinds": z_kinds,
                    "n_complete_cases": int(mask.sum()),
                }
                route = raw["test_name"]

        if route in {"hsic_mixed", "kci_mixed"}:
            warnings.append(
                f"{implication.x} ⟂ {implication.y} | {list(implication.z)} used {route} approximation"
            )

        p_values.append(float(raw["p_value"]))
        results.append(
            ImplicationTestResult(
                implication=implication,
                statistic=float(raw["statistic"]),
                p_value=float(raw["p_value"]),
                adjusted_p_value=float(raw["p_value"]),
                passed=bool(raw["passed"]),
                test_name=str(raw["test_name"]),
                metadata=dict(raw.get("metadata", {})),
            )
        )

    adjusted = _bh_adjust(p_values)
    adjusted_results: list[ImplicationTestResult] = []
    failed: list[tuple[ConditionalIndependence, float]] = []
    passed_count = 0
    for result, adj_p in zip(results, adjusted, strict=False):
        passed = bool(adj_p >= alpha)
        if passed:
            passed_count += 1
        else:
            failed.append((result.implication, float(adj_p)))
        adjusted_results.append(
            result.model_copy(
                update={
                    "adjusted_p_value": float(adj_p),
                    "passed": passed,
                }
            )
        )

    return TestReport(
        implications_tested=len(adjusted_results),
        implications_passed=passed_count,
        implications_failed=failed,
        overall_valid=(passed_count == len(adjusted_results)),
        alpha=alpha,
        test_method="adaptive_mgraph_ci",
        results=adjusted_results,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# RecoverabilityTest
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "recoverability", "m-graph", "structural"},
)
class RecoverabilityTest:
    """Test whether a query P(S) is recoverable from incomplete data.

    Implements the Mohan & Pearl (2021) graphical recoverability criterion
    (Theorem 1): P(S) is recoverable iff no R_V ∈ desc(V) in G' = G[V∪R \\ proxies].

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph" and
        ``metadata["mgraph"]`` containing the serialised MGraphMetadata.

    Output
    ------
    recoverability_result : dict
        status, query_variables, blocking_r_nodes, proof_steps, algorithm_version.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="recoverability_test",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({_json_slot("mgraph_data")}),
        output_slots=frozenset({_json_slot("recoverability_result")}),
        parameters=(
            ParameterSpec(name="query_variables", default=[]),
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Test recoverability of a query P(S) from incomplete data using "
            "the Mohan & Pearl (2021) M-graph graphical criterion."
        ),
        tags=frozenset(
            {
                "causal",
                "missing-data",
                "recoverability",
                "m-graph",
                "mcar",
                "mar",
                "mnar",
                "structural",
            }
        ),
        citations=(
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing "
            "Missing Data. Journal of the American Statistical Association.",
            "Mohan, K., Pearl, J. & Tian, J. (2013). Missing Data as a Causal "
            "and Probabilistic Problem. UAI 2013.",
        ),
        equations={
            "criterion": (
                "P(S) recoverable iff ∀V_i∈S: R_{V_i} ∉ desc(V_i) in G[V∪R \\ proxy_nodes]"
            ),
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "Before causal analysis when the dataset has systematic missing values; "
            "to determine whether identification is feasible."
        ),
        when_not_to_use="Data is fully observed (no missing values).",
        output_interpretation=(
            "status='recoverable' → safe to proceed with full law identification. "
            "status='not_recoverable' → blocking_r_nodes identifies MNAR variables "
            "that prevent recovery."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            test_recoverability,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = CausalGraphModel.model_validate(raw) if isinstance(raw, dict) else raw
        meta = extract_mgraph_metadata(graph)

        qvars_raw = params.get("query_variables", [])
        query_vars = frozenset(qvars_raw) if qvars_raw else frozenset(meta.substantive_vars)

        result = test_recoverability(
            query_vars=query_vars,
            graph=graph,
            mgraph_meta=meta,
        )

        return {
            "recoverability_result": {
                "status": result.status.value,
                "query_variables": sorted(result.query_variables),
                "blocking_r_nodes": sorted(result.blocking_r_nodes),
                "proof_steps": [
                    {
                        "rule_name": s.rule_name,
                        "antecedent_vars": list(s.antecedent_vars),
                        "consequent_vars": list(s.consequent_vars),
                        "applied_to_graph_state": s.applied_to_graph_state,
                        "depth": s.depth,
                    }
                    for s in result.proof_steps
                ],
                "trace": result.trace,
                "algorithm_version": result.algorithm_version,
            }
        }


# ---------------------------------------------------------------------------
# OrderedRecovery
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "ordered-recovery", "m-graph", "structural"},
)
class OrderedRecovery:
    """Recover full-data joint P(V) from incomplete data via topological ordering.

    Implements the Mohan, Pearl & Tian (2013) ordered fixing operator:
        P(V) = Π_i P(V_i | V_{<i})
    Each factor is recovered as P*(V_i | V_{<i}, R_{V_i}=1) for MCAR/MAR variables.

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph".

    Output
    ------
    recovery_estimand : dict
        Serialised EstimandAST with ProductNode of RecoveredDistNode factors.
    ordered_recovery_steps : list[dict]
        Proof steps for the topological recovery sequence.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ordered_recovery",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({_json_slot("mgraph_data")}),
        output_slots=frozenset(
            {
                _json_slot("recovery_estimand"),
                _json_slot("ordered_recovery_steps"),
            }
        ),
        parameters=(ParameterSpec(name="dataset_ref", default=None),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Recover full-data joint P(V) from incomplete data using the "
            "ordered fixing operator (Mohan, Pearl & Tian 2013)."
        ),
        tags=frozenset(
            {
                "causal",
                "missing-data",
                "ordered-recovery",
                "m-graph",
                "estimand",
                "fixing-operator",
                "structural",
            }
        ),
        citations=(
            "Mohan, K., Pearl, J. & Tian, J. (2013). Missing Data as a Causal "
            "and Probabilistic Problem. UAI 2013.",
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing "
            "Missing Data. Journal of the American Statistical Association.",
        ),
        equations={
            "recovery": "P(V) = Π_i P(V_i | V_{<i})",
            "mcar_mar_factor": "P(V_i | V_{<i}) = P*(V_i | V_{<i}, R_{V_i}=1)",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "After RecoverabilityTest confirms P(V) is recoverable; "
            "to obtain the explicit recovery formula."
        ),
        when_not_to_use=(
            "RecoverabilityTest returned NOT_RECOVERABLE — ordered recovery "
            "will not produce a valid result."
        ),
        output_interpretation=(
            "recovery_estimand is an EstimandAST with a ProductNode of "
            "RecoveredDistNode factors.  Each factor specifies the data query "
            "(variable, conditioning, missingness_indicator, proxy_variable) "
            "needed to estimate that factor from the incomplete dataset."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            ordered_recovery,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = CausalGraphModel.model_validate(raw) if isinstance(raw, dict) else raw
        meta = extract_mgraph_metadata(graph)
        dataset_ref = params.get("dataset_ref")

        estimand = ordered_recovery(
            graph=graph,
            mgraph_meta=meta,
            dataset_ref=dataset_ref,
        )

        # Extract proof steps from the estimand's root factors
        steps = []
        from polisyos.ir.analytics.estimand import ProductNode, RecoveredDistNode

        if isinstance(estimand.root, ProductNode):
            for i, factor in enumerate(estimand.root.factors):
                if isinstance(factor, RecoveredDistNode):
                    steps.append(
                        {
                            "rule_name": "ORDERED_RECOVERY_STEP",
                            "variable": factor.variable,
                            "conditioning": list(factor.conditioning),
                            "missingness_kind": factor.missingness_kind,
                            "missingness_indicator": factor.missingness_indicator,
                            "proxy_variable": factor.proxy_variable,
                            "depth": i,
                        }
                    )

        return {
            "recovery_estimand": estimand.model_dump(mode="json"),
            "ordered_recovery_steps": steps,
        }


# ---------------------------------------------------------------------------
# FullLawIdentify
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "full-law", "identification", "m-graph"},
)
class FullLawIdentify:
    """Identify P(Y|do(X)) from incomplete data using the full law pipeline.

    Two-stage pipeline (Nabi, Bhattacharya & Shpitser 2020):
      Stage 1: RecoverabilityTest — check if P(V) is recoverable from P*(V).
      Stage 2: ID algorithm — identify P(Y|do(X)) from recovered P(V).

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph".

    Output
    ------
    identification_result : dict
        status, estimand_ast, proof_steps, algorithm_version, trace.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="full_law_identify",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                _json_slot("mgraph_data"),
                _json_slot("treatment"),
                _json_slot("outcome"),
            }
        ),
        output_slots=frozenset({_json_slot("identification_result")}),
        parameters=(
            ParameterSpec(name="oracle", default="none"),
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Identify causal effects from incomplete data via the full law pipeline "
            "(Nabi, Bhattacharya & Shpitser 2020): recover P(V) then identify P(Y|do(X))."
        ),
        tags=frozenset(
            {
                "causal",
                "missing-data",
                "full-law",
                "identification",
                "m-graph",
                "id-algorithm",
            }
        ),
        citations=(
            "Nabi, R., Bhattacharya, R. & Shpitser, I. (2020). Full law identification "
            "in graphical models of missing data.",
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing Missing Data. "
            "Journal of the American Statistical Association.",
        ),
        equations={
            "pipeline": "P(Y|do(X)) identified from incomplete data via two-stage pipeline",
            "stage1": "Recover P(V) = Π_i P*(V_i|V_{<i}, R_{V_i}=1)",
            "stage2": "Identify P(Y|do(X)) from P(V) via ID algorithm",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "Causal identification when input data has systematic missingness "
            "(MCAR/MAR/MNAR patterns confirmed via m-graph analysis)."
        ),
        when_not_to_use="Data is fully observed; use standard ID algorithm instead.",
        output_interpretation=(
            "status='identified' → both stages succeeded; estimand_ast contains "
            "the full identification formula. "
            "status='not_recoverable' → Stage 1 failed; identification is impossible "
            "without additional assumptions. "
            "status='hedge_found' / 'oracle_needed' → Stage 2 failed; the causal query "
            "is non-identifiable even with complete data."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            full_law_identify,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = CausalGraphModel.model_validate(raw) if isinstance(raw, dict) else raw
        meta = extract_mgraph_metadata(graph)

        treatment_raw = state["treatment"]
        outcome_raw = state["outcome"]
        treatment = (
            frozenset(treatment_raw)
            if isinstance(treatment_raw, (list, tuple, frozenset, set))
            else frozenset({str(treatment_raw)})
        )
        outcome = (
            frozenset(outcome_raw)
            if isinstance(outcome_raw, (list, tuple, frozenset, set))
            else frozenset({str(outcome_raw)})
        )

        oracle = str(params.get("oracle", "none"))
        dataset_ref = params.get("dataset_ref")

        result = full_law_identify(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            mgraph_meta=meta,
            dataset_ref=dataset_ref,
            oracle=oracle,
        )

        estimand_dict = (
            result.estimand_ast.model_dump(mode="json") if result.estimand_ast is not None else None
        )

        return {
            "identification_result": {
                "status": result.status.value,
                "estimand_ast": estimand_dict,
                "algorithm_version": result.algorithm_version,
                "trace": result.trace,
                "proof_steps": [
                    {
                        "rule_name": s.rule_name,
                        "antecedent_vars": list(s.antecedent_vars),
                        "consequent_vars": list(s.consequent_vars),
                        "applied_to_graph_state": s.applied_to_graph_state,
                        "depth": s.depth,
                    }
                    for s in result.proof_steps
                ],
            }
        }


# ---------------------------------------------------------------------------
# MGraphImplicationTester
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "implication-test", "m-graph"},
)
class MGraphImplicationTester:
    """Statistical audit of testable M-graph implications."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mgraph_implication_test",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                _json_slot("mgraph_data"),
                _json_slot("data"),
            }
        ),
        output_slots=frozenset({_json_slot("test_report")}),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="max_conditioning_set_size", default=2),
            ParameterSpec(name="implications", default=[]),
            ParameterSpec(name="variable_order", default=[]),
            ParameterSpec(name="dp_context", default=None),
            ParameterSpec(name="judge_threshold_registry_root", default=None),
            ParameterSpec(name="readiness_target", default="diagnostic"),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Generate testable M-graph implications via m-separation and run a "
            "BH-corrected conditional-independence test suite."
        ),
        tags=frozenset(
            {
                "causal",
                "missing-data",
                "m-graph",
                "implication-test",
                "conditional-independence",
                "falsification",
            }
        ),
        citations=(
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing Missing Data.",
            "Fisher, R.A. (1924). The distribution of the partial correlation coefficient.",
        ),
        equations={
            "bh": "q_(i) = min_{j>=i} p_(j)·m/j",
            "ci": "X ⊥ Y | Z",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "After constructing an M-graph, to falsify missingness assumptions "
            "against observed data."
        ),
        when_not_to_use="When no observed dataset is available.",
        output_interpretation=(
            "overall_valid=True means no graph-derived implication was rejected "
            "after multiple-testing correction."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw_graph = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw_graph) if isinstance(raw_graph, dict) else raw_graph
        )
        meta = extract_mgraph_metadata(graph)

        raw_data = state.get("data", state.get("dataset"))
        if raw_data is None:
            raise KeyError("MGraphImplicationTester requires 'data' in state")

        raw_implications = params.get("implications")
        implications: list[ConditionalIndependence] | None = None
        if raw_implications:
            implications = [
                (
                    item
                    if isinstance(item, ConditionalIndependence)
                    else ConditionalIndependence.model_validate(item)
                )
                for item in raw_implications
            ]

        report = test_mgraph_implications(
            graph=graph,
            mgraph_meta=meta,
            data=raw_data,
            implications=implications,
            alpha=float(params.get("alpha", 0.05)),
            max_conditioning_set_size=int(params.get("max_conditioning_set_size", 2)),
            variable_order=tuple(params.get("variable_order", ())) or None,
            dp_context=params.get("dp_context"),
            judge_threshold_registry_root=params.get("judge_threshold_registry_root"),
            readiness_target=str(params.get("readiness_target", "diagnostic")),
        )
        return {"test_report": report.model_dump(mode="json")}


__all__ = [
    "AdministrativeMissingnessAssessment",
    "ConditionalIndependence",
    "FullLawIdentify",
    "ImplicationTestResult",
    "MGraphImplicationTester",
    "OrderedRecovery",
    "RecoverabilityTest",
    "TestReport",
    "assess_administrative_missingness",
    "test_mgraph_implications",
    "testable_implications",
]
