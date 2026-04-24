"""Administrative missingness taxonomy and readiness contracts.

This module formalizes Stage 12.2 of the research roadmap:
registration-based, compliance-based, and system-change-based missingness
patterns become typed metadata that can travel with an M-graph and power
readiness/risk assessments.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.mgraph import MissingnessKind, build_mgraph
from polisyos.ir.analytics.recoverability import mgraph_fingerprint

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.ir.analytics.causal_graph import CausalGraphModel


class AdministrativeMissingnessScenarioFamily(str, Enum):
    """High-level family of administrative missingness mechanisms."""

    REGISTRATION_BASED = "registration_based"
    COMPLIANCE_BASED = "compliance_based"
    SYSTEM_CHANGE_BASED = "system_change_based"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class AdministrativeMissingnessClass(str, Enum):
    """Operational administrative-missingness class used by survey governance."""

    NONE = "none"
    REGISTRATION_NOT_APPLIED = "registration_not_applied"
    REGISTRATION_NOT_REGISTERED = "registration_not_registered"
    COMPLIANCE_NOT_COMPLETED = "compliance_not_completed"
    SERVICE_UNAVAILABLE_OFFICE_CLOSED = "service_unavailable_office_closed"
    SYSTEM_CHANGE_OR_SCHEMA_BREAK = "system_change_or_schema_break"
    RETENTION_EXPIRED = "retention_expired"
    LEGAL_RESTRICTION_OR_REDACTION = "legal_restriction_or_redaction"
    PROCESSING_BACKLOG_OR_REPORTING_LAG = "processing_backlog_or_reporting_lag"
    LINKAGE_FAILURE = "linkage_failure"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class AdministrativeMissingnessDirection(str, Enum):
    """How an administrative value became unobservable."""

    NOT_GENERATED = "not_generated"
    NOT_CAPTURED = "not_captured"
    DELAYED = "delayed"
    WITHHELD = "withheld"
    DELETED = "deleted"
    NOT_LINKED = "not_linked"
    UNKNOWN = "unknown"


class AdministrativeMissingnessUnitScope(str, Enum):
    """Granularity at which the administrative missingness mechanism operates."""

    FIELD = "field"
    RECORD = "record"
    LINK = "link"
    EPISODE = "episode"
    EXTRACT = "extract"
    TIME_WINDOW = "time_window"
    UNKNOWN = "unknown"


class MissingnessAssessmentStatus(str, Enum):
    """Readiness status for a typed administrative missingness mechanism."""

    RECOVERABLE = "recoverable"
    NOT_RECOVERABLE = "not_recoverable"
    PARTIALLY_RECOVERABLE = "partially_recoverable"
    UNKNOWN = "unknown"


class AdministrativeMissingnessMetadata(BaseModel):
    """Administrative-process metadata required to certify missingness recovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    scenario_family: AdministrativeMissingnessScenarioFamily
    scenario_class: AdministrativeMissingnessClass | None = None
    missingness_direction: AdministrativeMissingnessDirection | None = None
    missingness_unit_scope: AdministrativeMissingnessUnitScope | None = None
    target_variables: tuple[str, ...] = ()
    registration_indicator: str | None = None
    eligibility_covariates: tuple[str, ...] = ()
    population_frame_observed: bool | None = None
    compliance_indicator: str | None = None
    compliance_driver_covariates: tuple[str, ...] = ()
    system_version_variable: str | None = None
    time_variable: str | None = None
    rollout_covariates: tuple[str, ...] = ()
    office_availability_covariates: tuple[str, ...] = ()
    identifier_quality_covariates: tuple[str, ...] = ()
    processing_lag_covariates: tuple[str, ...] = ()
    legal_restriction_covariates: tuple[str, ...] = ()
    bridge_window_observed: bool | None = None
    retention_window_observed: bool | None = None
    legal_rule_observed: bool | None = None
    matured_cohorts_observed: bool | None = None
    validation_subset_available: bool | None = None
    evidence_refs: tuple[str, ...] = ()
    source_system: str | None = None
    extract_ts: str | None = None
    policy_version: str | None = None
    linkage_run_id: str | None = None
    retention_schedule_id: str | None = None
    notes: str = ""

    @property
    def administrative_covariates(self) -> tuple[str, ...]:
        items = [
            *(self.target_variables or ()),
            self.registration_indicator,
            *(self.eligibility_covariates or ()),
            self.compliance_indicator,
            *(self.compliance_driver_covariates or ()),
            self.system_version_variable,
            self.time_variable,
            *(self.rollout_covariates or ()),
            *(self.office_availability_covariates or ()),
            *(self.identifier_quality_covariates or ()),
            *(self.processing_lag_covariates or ()),
            *(self.legal_restriction_covariates or ()),
        ]
        return tuple(_stable_strings(items))


class MissingnessProofStep(BaseModel):
    """Compact proof step exposed through missingness assessments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_name: str
    antecedent_vars: tuple[str, ...] = ()
    consequent_vars: tuple[str, ...] = ()
    applied_to_graph_state: str = ""
    depth: int = 0


class MissingnessRecoverabilitySummary(BaseModel):
    """Recoverability trace for the missingness mechanism itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    query_variables: tuple[str, ...] = ()
    blocking_r_nodes: tuple[str, ...] = ()
    proof_steps: tuple[MissingnessProofStep, ...] = ()
    algorithm_version: str = ""


class MissingnessImplicationFailure(BaseModel):
    """Single failed testable implication from an M-graph audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: str
    y: str
    z: tuple[str, ...] = ()
    adjusted_p_value: float = Field(ge=0.0, le=1.0)


class MissingnessTestabilityAudit(BaseModel):
    """Summary of statistical checks for testable M-graph implications."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_valid: bool
    implications_tested: int = Field(ge=0)
    implications_failed: tuple[MissingnessImplicationFailure, ...] = ()
    warnings: tuple[str, ...] = ()


class MissingnessEstimandRisk(BaseModel):
    """Machine-readable summary of which estimands are threatened by a mechanism."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    scope: str = ""
    identifiable: bool | None = None
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"


class MissingnessEvidenceItem(BaseModel):
    """Evidence artifact supporting a missingness assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    ref: str
    quality: Literal["low", "medium", "high", "unknown"] = "unknown"


class MissingnessAssessmentProvenance(BaseModel):
    """Provenance block for decision-grade missingness assessments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_system: str | None = None
    extract_ts: str | None = None
    policy_version: str | None = None
    linkage_run_id: str | None = None
    retention_schedule_id: str | None = None
    assessment_method: str = ""
    assessor: str | None = None
    code_commit: str | None = None
    mgraph_fingerprint: str | None = None


class MissingnessAssessmentReport(BaseModel):
    """Readiness-facing report for administrative missingness modeling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    status: MissingnessAssessmentStatus
    scenario_family: AdministrativeMissingnessScenarioFamily
    scenario_class: AdministrativeMissingnessClass = AdministrativeMissingnessClass.UNKNOWN
    missingness_direction: AdministrativeMissingnessDirection = (
        AdministrativeMissingnessDirection.UNKNOWN
    )
    missingness_unit_scope: AdministrativeMissingnessUnitScope = (
        AdministrativeMissingnessUnitScope.UNKNOWN
    )
    scenario_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    administrative_covariates_present: tuple[str, ...] = ()
    administrative_covariates_missing: tuple[str, ...] = ()
    key_variables: tuple[str, ...] = ()
    proof_kernel_requirements: tuple[str, ...] = ()
    mgraph_ref: str | None = None
    recoverability: MissingnessRecoverabilitySummary | None = None
    testability_audit: MissingnessTestabilityAudit | None = None
    estimands_at_risk: tuple[MissingnessEstimandRisk, ...] = ()
    identification_assumptions: tuple[str, ...] = ()
    testable_implications_declared: tuple[str, ...] = ()
    evidence: tuple[MissingnessEvidenceItem, ...] = ()
    provenance: MissingnessAssessmentProvenance | None = None
    recommended_method_stack: tuple[str, ...] = ()
    sensitivity_plan: tuple[str, ...] = ()
    target_population_after_restriction: str | None = None
    recommendations: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


def extract_administrative_missingness_metadata(
    graph: CausalGraphModel,
) -> AdministrativeMissingnessMetadata | None:
    """Return typed administrative-missingness metadata from graph.metadata."""
    raw = graph.metadata.get("administrative_missingness")
    if raw is None:
        return None
    if isinstance(raw, AdministrativeMissingnessMetadata):
        return raw
    return AdministrativeMissingnessMetadata.model_validate(raw)


def attach_administrative_missingness_metadata(
    graph: CausalGraphModel,
    metadata: AdministrativeMissingnessMetadata,
) -> CausalGraphModel:
    """Attach typed administrative metadata to an M-graph."""
    updated_metadata = dict(graph.metadata)
    updated_metadata["administrative_missingness"] = metadata.model_dump(mode="json")
    updated_metadata.setdefault("mgraph_fingerprint", mgraph_fingerprint(graph))
    return graph.model_copy(update={"metadata": updated_metadata})


def build_registration_based_mgraph(
    *,
    substantive_vars: list[str],
    directed_edges: list[tuple[str, str]] | None = None,
    target_variables: list[str],
    registration_indicator: str = "registration_flag",
    eligibility_covariates: list[str] | None = None,
    population_frame_observed: bool = True,
    missingness_kind: MissingnessKind = MissingnessKind.MAR,
    discovery_method: str = "administrative_registration",
    scenario_class: AdministrativeMissingnessClass | None = None,
    missingness_direction: AdministrativeMissingnessDirection | None = None,
    missingness_unit_scope: AdministrativeMissingnessUnitScope | None = None,
    evidence_refs: list[str] | None = None,
    notes: str = "",
) -> CausalGraphModel:
    """Construct a registration-based administrative M-graph template."""
    eligibility_covariates = list(eligibility_covariates or [])
    indicator_label = registration_indicator.lower()
    resolved_class = scenario_class
    if resolved_class is None:
        if any(token in indicator_label for token in ("apply", "application", "claim")):
            resolved_class = AdministrativeMissingnessClass.REGISTRATION_NOT_APPLIED
        else:
            resolved_class = AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED
    resolved_direction = missingness_direction or AdministrativeMissingnessDirection.NOT_GENERATED
    resolved_scope = missingness_unit_scope or AdministrativeMissingnessUnitScope.RECORD
    all_substantive = _stable_strings(
        [
            *substantive_vars,
            registration_indicator,
            *eligibility_covariates,
        ]
    )
    merged_directed = _dedupe_edges(
        [
            *(directed_edges or []),
            *((cov, registration_indicator) for cov in eligibility_covariates),
        ]
    )
    graph = build_mgraph(
        substantive_vars=all_substantive,
        directed_edges=merged_directed,
        missingness_map=dict.fromkeys(target_variables, missingness_kind),
        missingness_edges=[(registration_indicator, f"R_{var}") for var in target_variables],
        discovery_method=discovery_method,
    )
    return attach_administrative_missingness_metadata(
        graph,
        AdministrativeMissingnessMetadata(
            scenario_family=AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED,
            scenario_class=resolved_class,
            missingness_direction=resolved_direction,
            missingness_unit_scope=resolved_scope,
            target_variables=tuple(_stable_strings(target_variables)),
            registration_indicator=registration_indicator,
            eligibility_covariates=tuple(_stable_strings(eligibility_covariates)),
            population_frame_observed=population_frame_observed,
            evidence_refs=tuple(_stable_strings(evidence_refs or [])),
            notes=notes,
        ),
    )


def build_compliance_based_mgraph(
    *,
    substantive_vars: list[str],
    directed_edges: list[tuple[str, str]] | None = None,
    target_variables: list[str],
    compliance_indicator: str = "compliance_status",
    compliance_driver_covariates: list[str] | None = None,
    self_censoring_variables: list[str] | None = None,
    missingness_kind: MissingnessKind = MissingnessKind.MAR,
    discovery_method: str = "administrative_compliance",
    scenario_class: AdministrativeMissingnessClass | None = None,
    missingness_direction: AdministrativeMissingnessDirection | None = None,
    missingness_unit_scope: AdministrativeMissingnessUnitScope | None = None,
    evidence_refs: list[str] | None = None,
    notes: str = "",
) -> CausalGraphModel:
    """Construct a compliance-based administrative M-graph template."""
    compliance_driver_covariates = list(compliance_driver_covariates or [])
    self_censoring_variables = list(self_censoring_variables or [])
    resolved_class = scenario_class or AdministrativeMissingnessClass.COMPLIANCE_NOT_COMPLETED
    resolved_direction = missingness_direction or AdministrativeMissingnessDirection.NOT_CAPTURED
    resolved_scope = missingness_unit_scope or AdministrativeMissingnessUnitScope.EPISODE
    all_substantive = _stable_strings(
        [
            *substantive_vars,
            compliance_indicator,
            *compliance_driver_covariates,
        ]
    )
    merged_directed = _dedupe_edges(
        [
            *(directed_edges or []),
            *((cov, compliance_indicator) for cov in compliance_driver_covariates),
            *((var, compliance_indicator) for var in self_censoring_variables),
        ]
    )
    graph = build_mgraph(
        substantive_vars=all_substantive,
        directed_edges=merged_directed,
        missingness_map=dict.fromkeys(target_variables, missingness_kind),
        missingness_edges=[(compliance_indicator, f"R_{var}") for var in target_variables],
        discovery_method=discovery_method,
    )
    return attach_administrative_missingness_metadata(
        graph,
        AdministrativeMissingnessMetadata(
            scenario_family=AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED,
            scenario_class=resolved_class,
            missingness_direction=resolved_direction,
            missingness_unit_scope=resolved_scope,
            target_variables=tuple(_stable_strings(target_variables)),
            compliance_indicator=compliance_indicator,
            compliance_driver_covariates=tuple(_stable_strings(compliance_driver_covariates)),
            evidence_refs=tuple(_stable_strings(evidence_refs or [])),
            notes=notes,
        ),
    )


def build_system_change_based_mgraph(
    *,
    substantive_vars: list[str],
    directed_edges: list[tuple[str, str]] | None = None,
    target_variables: list[str],
    system_version_variable: str | None = "system_version",
    time_variable: str | None = None,
    rollout_covariates: list[str] | None = None,
    office_availability_covariates: list[str] | None = None,
    affected_outcomes: list[str] | None = None,
    missingness_kind: MissingnessKind = MissingnessKind.MAR,
    discovery_method: str = "administrative_system_change",
    scenario_class: AdministrativeMissingnessClass | None = None,
    missingness_direction: AdministrativeMissingnessDirection | None = None,
    missingness_unit_scope: AdministrativeMissingnessUnitScope | None = None,
    bridge_window_observed: bool | None = None,
    evidence_refs: list[str] | None = None,
    notes: str = "",
) -> CausalGraphModel:
    """Construct a system-change-based administrative M-graph template."""
    rollout_covariates = list(rollout_covariates or [])
    office_availability_covariates = list(office_availability_covariates or [])
    affected_outcomes = list(affected_outcomes or [])
    resolved_class = scenario_class
    if resolved_class is None:
        if office_availability_covariates:
            resolved_class = AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED
        else:
            resolved_class = AdministrativeMissingnessClass.SYSTEM_CHANGE_OR_SCHEMA_BREAK
    resolved_direction = missingness_direction or AdministrativeMissingnessDirection.NOT_CAPTURED
    if missingness_unit_scope is not None:
        resolved_scope = missingness_unit_scope
    elif resolved_class is AdministrativeMissingnessClass.SERVICE_UNAVAILABLE_OFFICE_CLOSED:
        resolved_scope = AdministrativeMissingnessUnitScope.TIME_WINDOW
    else:
        resolved_scope = AdministrativeMissingnessUnitScope.EXTRACT
    mechanism_var = system_version_variable or time_variable
    if mechanism_var is None:
        raise ValueError(
            "build_system_change_based_mgraph requires system_version_variable or time_variable"
        )
    all_substantive = _stable_strings(
        [
            *substantive_vars,
            mechanism_var,
            *([time_variable] if time_variable and time_variable != mechanism_var else []),
            *rollout_covariates,
            *office_availability_covariates,
        ]
    )
    extra_directed: list[tuple[str, str]] = [
        *((cov, mechanism_var) for cov in rollout_covariates),
        *((cov, mechanism_var) for cov in office_availability_covariates),
        *((mechanism_var, outcome) for outcome in affected_outcomes),
    ]
    if time_variable is not None and time_variable != mechanism_var:
        extra_directed.append((time_variable, mechanism_var))
    merged_directed = _dedupe_edges([*(directed_edges or []), *extra_directed])
    graph = build_mgraph(
        substantive_vars=all_substantive,
        directed_edges=merged_directed,
        missingness_map=dict.fromkeys(target_variables, missingness_kind),
        missingness_edges=[(mechanism_var, f"R_{var}") for var in target_variables],
        discovery_method=discovery_method,
    )
    return attach_administrative_missingness_metadata(
        graph,
        AdministrativeMissingnessMetadata(
            scenario_family=AdministrativeMissingnessScenarioFamily.SYSTEM_CHANGE_BASED,
            scenario_class=resolved_class,
            missingness_direction=resolved_direction,
            missingness_unit_scope=resolved_scope,
            target_variables=tuple(_stable_strings(target_variables)),
            system_version_variable=system_version_variable,
            time_variable=time_variable,
            rollout_covariates=tuple(_stable_strings(rollout_covariates)),
            office_availability_covariates=tuple(_stable_strings(office_availability_covariates)),
            bridge_window_observed=bridge_window_observed,
            evidence_refs=tuple(_stable_strings(evidence_refs or [])),
            notes=notes,
        ),
    )


def _stable_strings(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value is None:
            continue
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _dedupe_edges(edges: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for src, dst in edges:
        key = (str(src), str(dst))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


__all__ = [
    "AdministrativeMissingnessClass",
    "AdministrativeMissingnessDirection",
    "AdministrativeMissingnessMetadata",
    "AdministrativeMissingnessScenarioFamily",
    "AdministrativeMissingnessUnitScope",
    "MissingnessAssessmentProvenance",
    "MissingnessAssessmentReport",
    "MissingnessAssessmentStatus",
    "MissingnessEstimandRisk",
    "MissingnessEvidenceItem",
    "MissingnessImplicationFailure",
    "MissingnessProofStep",
    "MissingnessRecoverabilitySummary",
    "MissingnessTestabilityAudit",
    "attach_administrative_missingness_metadata",
    "build_compliance_based_mgraph",
    "build_registration_based_mgraph",
    "build_system_change_based_mgraph",
    "extract_administrative_missingness_metadata",
]
