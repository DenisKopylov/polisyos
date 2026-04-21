"""Proximal causal identification certificate IR.

The objects in this module are intentionally estimator-agnostic. They record
the machine-checked graph obligations, the bridge equations that must be solved
by an estimator, and the non-graphical assumptions that make the proximal
identification argument sound.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import BridgePlausibilityReportRef, ProximalIdentificationCertificateRef


class ProxyAnnotation(BaseModel):
    """User/developer supplied proximal proxy annotation.

    ``treatment_inducing`` corresponds to Z-proxies and ``outcome_inducing`` to
    W-proxies in the proximal causal inference literature.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    treatment_inducing: tuple[str, ...] = Field(default_factory=tuple)
    outcome_inducing: tuple[str, ...] = Field(default_factory=tuple)
    covariates: tuple[str, ...] = Field(default_factory=tuple)
    estimand: Literal["ATE", "ATT", "MEAN_EFFECT"] = "ATE"
    include_treatment_bridge: bool = True
    accept_oracle_assumptions: bool = False

    @model_validator(mode="after")
    def _normalize_sets(self) -> ProxyAnnotation:
        for field_name in ("treatment_inducing", "outcome_inducing", "covariates"):
            values = tuple(str(item).strip() for item in getattr(self, field_name))
            if any(not item for item in values):
                raise ValueError(f"{field_name} must not contain empty variable names")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicate variables")
            object.__setattr__(self, field_name, tuple(sorted(values)))
        return self


class ProximalQuerySpec(BaseModel):
    """Machine-readable target query for a proximal certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    estimand: Literal["ATE", "ATT", "MEAN_EFFECT"] = "ATE"
    treatment: tuple[str, ...]
    outcome: tuple[str, ...]
    covariates: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_query_scope(self) -> ProximalQuerySpec:
        if len(self.treatment) != 1:
            raise ValueError("proximal v1 supports exactly one treatment")
        if len(self.outcome) != 1:
            raise ValueError("proximal v1 supports exactly one outcome")
        for field_name in ("treatment", "outcome", "covariates"):
            values = tuple(str(item).strip() for item in getattr(self, field_name))
            if any(not item for item in values):
                raise ValueError(f"{field_name} must not contain empty variable names")
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicate variables")
            object.__setattr__(self, field_name, tuple(sorted(values)))
        return self


class ProximalGraphClass(BaseModel):
    """Declared graph class covered by a proximal certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "PCI-Core"
    graph_type_required: tuple[Literal["admg", "dag"], ...] = ("admg", "dag")
    notes: str = (
        "v1: single treatment, single outcome; conservative sufficient "
        "graphical checks for proximal bridge identification."
    )


class ProximalGraphCheck(BaseModel):
    """One machine-checkable graph obligation and optional witness data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check: str
    status: Literal["pass", "fail"]
    source: str | None = None
    target: str | None = None
    source_set: tuple[str, ...] = Field(default_factory=tuple)
    target_set: tuple[str, ...] = Field(default_factory=tuple)
    requirements: tuple[str, ...] = Field(default_factory=tuple)
    witness: dict[str, Any] = Field(default_factory=dict)
    detail: str = ""


class ProximalAssumption(BaseModel):
    """Explicit graphical or non-graphical assumption in the certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    statement: str
    source: str = "proximal_causal_inference"
    machine_checkable: bool = False


class BridgeFunctionSpec(BaseModel):
    """A confounding bridge equation emitted by the proximal identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    role: Literal["outcome_bridge", "treatment_bridge"]
    domain: tuple[str, ...]
    equation_type: Literal["conditional_expectation", "integral_equation"]
    equation: str
    assumptions: tuple[ProximalAssumption, ...] = Field(default_factory=tuple)
    optional: bool = False


class ProximalMediationQuerySpec(BaseModel):
    """Machine-readable target query for the single-mediator proximal template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["path_specific"] = "path_specific"
    estimand: Literal["E[Y{a, M(a_ref)}]"] = "E[Y{a, M(a_ref)}]"
    treatment: str
    mediator: str
    outcome: str
    active_treatment_value: float = 1.0
    reference_treatment_value: float = 0.0
    target_effect: Literal["psi", "nde", "nie"] = "psi"

    @model_validator(mode="after")
    def _validate_query(self) -> ProximalMediationQuerySpec:
        labels = {
            "treatment": str(self.treatment).strip(),
            "mediator": str(self.mediator).strip(),
            "outcome": str(self.outcome).strip(),
        }
        if any(not value for value in labels.values()):
            raise ValueError("treatment, mediator, and outcome must be non-empty")
        if len(set(labels.values())) != 3:
            raise ValueError("treatment, mediator, and outcome must be distinct")
        for field_name, value in labels.items():
            object.__setattr__(self, field_name, value)
        return self


class ProximalMediationBridgeEquation(BaseModel):
    """Nested bridge equation used by the proximal mediation theorem."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    equation_type: Literal["fredholm_first_kind"] = "fredholm_first_kind"
    target: str
    unknown_function: str
    operator: str


class ProximalMediationCompletenessCondition(BaseModel):
    """Explicit completeness condition required by proximal mediation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    statement: str
    oracle_needed: bool = True


class ProximalMediationTopology(BaseModel):
    """Topological envelope covered by the v1 proximal mediation theorem."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "single_mediator_proximal_v1"
    allowed_edges_summary: tuple[str, ...] = (
        "A -> M -> Y",
        "A -> Y (optional)",
        "X -> {A,M,Y} (optional common causes)",
        "Z -> A (optional); W -> Y (optional)",
    )
    forbidden_edges_summary: tuple[str, ...] = (
        "Z -> M",
        "Z -> Y",
        "A -> W",
        "M -> W",
    )


class ProximalMediationCertificate(BaseModel):
    """Oracle-backed certificate for path-specific proximal mediation v1.

    The v1 template is intentionally proof-kernel focused: structural checks are
    machine-verifiable, while completeness and cross-world assumptions remain
    explicit oracle-level obligations recorded in the payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query: ProximalMediationQuerySpec
    variable_roles: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    topology: ProximalMediationTopology = Field(default_factory=ProximalMediationTopology)
    theorem: dict[str, Any] = Field(default_factory=dict)
    graph_checks: tuple[ProximalGraphCheck, ...] = Field(default_factory=tuple)
    bridge_equations: tuple[ProximalMediationBridgeEquation, ...] = Field(default_factory=tuple)
    completeness_conditions: tuple[ProximalMediationCompletenessCondition, ...] = Field(
        default_factory=tuple
    )
    identified_functional: str
    assumptions: dict[str, Any] = Field(default_factory=dict)
    diagnostics_and_gates: dict[str, Any] = Field(default_factory=dict)
    proof_trace: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_certificate(self) -> ProximalMediationCertificate:
        if not self.bridge_equations:
            raise ValueError("proximal mediation certificate must declare bridge equations")
        if not self.completeness_conditions:
            raise ValueError(
                "proximal mediation certificate must declare completeness conditions"
            )
        failed_checks = [item.check for item in self.graph_checks if item.status == "fail"]
        if failed_checks:
            raise ValueError(
                f"proximal mediation certificate cannot include failed checks: {failed_checks}"
            )
        return self


class BridgePlausibilitySeverity(str, Enum):
    """Traffic-light severity for bridge existence/completeness diagnostics."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class BridgeFailureMode(str, Enum):
    """Main failure mode diagnosed for a proximal bridge equation."""

    NONE = "none"
    INFEASIBLE_EQUATION = "infeasible_equation"
    WEAK_COMPLETENESS = "weak_completeness"
    ILL_POSED = "ill_posed"
    NONUNIQUE_SOLUTION = "nonunique_solution"
    UNKNOWN = "unknown"


class BridgeFallbackDisposition(str, Enum):
    """What the B-layer should do with a diagnosed bridge equation."""

    PROCEED_POINT_ESTIMATE = "proceed_point_estimate"
    PROCEED_WITH_WARNING = "proceed_with_warning"
    REQUIRE_BOUNDS = "require_bounds"
    BLOCK_POINT_ESTIMATE = "block_point_estimate"


class BridgePlausibilityReport(BaseModel):
    """Typed diagnostic artifact for proximal bridge existence/completeness.

    This contract is intentionally estimator-facing rather than proof-kernel
    facing: it records whether the bridge equation appears compatible with the
    data, how ill-posed the inverse problem looks, and what fallback the system
    should take when point identification is not trustworthy.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    equation_type: Literal["outcome_bridge", "treatment_bridge", "both"]
    residual_r: float | None = Field(default=None, ge=0.0)
    residual_interval: tuple[float, float] | None = None
    effective_rank: float | None = Field(default=None, ge=0.0)
    sigma_min: float | None = Field(default=None, ge=0.0)
    ill_posedness_index: float | None = Field(default=None, ge=0.0)
    proxy_association_score: float | None = None
    bridge_existence_supported: bool | None = None
    completeness_plausible: bool | None = None
    functional_invariant_to_nonuniqueness: bool | None = None
    suspected_failure_mode: BridgeFailureMode = BridgeFailureMode.UNKNOWN
    severity: BridgePlausibilitySeverity = BridgePlausibilitySeverity.YELLOW
    fallback_disposition: BridgeFallbackDisposition | None = None
    reasons: tuple[str, ...] = ()
    recommended_bounds_methods: tuple[str, ...] = ()
    recommended_rescue_actions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_report(self) -> BridgePlausibilityReport:
        if self.residual_interval is not None:
            lower, upper = self.residual_interval
            if lower < 0.0 or upper < 0.0:
                raise ValueError("residual_interval must be non-negative")
            if lower > upper:
                raise ValueError("residual_interval must satisfy lower <= upper")
        if self.fallback_disposition is None:
            object.__setattr__(
                self,
                "fallback_disposition",
                _default_fallback_disposition(self),
            )
        return self

    def to_summary_dict(self) -> dict[str, Any]:
        """Return the compact JSON shape embedded in bounds/negative artifacts."""

        return {
            "schema_version": self.schema_version,
            "equation_type": self.equation_type,
            "residual_r": self.residual_r,
            "residual_interval": list(self.residual_interval) if self.residual_interval else None,
            "effective_rank": self.effective_rank,
            "sigma_min": self.sigma_min,
            "ill_posedness_index": self.ill_posedness_index,
            "proxy_association_score": self.proxy_association_score,
            "bridge_existence_supported": self.bridge_existence_supported,
            "completeness_plausible": self.completeness_plausible,
            "functional_invariant_to_nonuniqueness": self.functional_invariant_to_nonuniqueness,
            "suspected_failure_mode": self.suspected_failure_mode.value,
            "severity": self.severity.value,
            "fallback_disposition": (
                self.fallback_disposition.value if self.fallback_disposition is not None else None
            ),
            "reasons": list(self.reasons),
            "recommended_bounds_methods": list(self.recommended_bounds_methods),
            "recommended_rescue_actions": list(self.recommended_rescue_actions),
        }


class IdentifiedFunctional(BaseModel):
    """Final identified functional certified by the proximal proof."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: Literal["ATE", "ATT", "MEAN_EFFECT"]
    expression: str
    preferred: bool = False
    bridge_role: Literal["outcome_bridge", "treatment_bridge", "doubly_robust"] | None = None


class ProximalIdentificationCertificate(BaseModel):
    """Constructive proximal identification proof artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query: ProximalQuerySpec
    proxies: ProxyAnnotation
    graph_class: ProximalGraphClass = Field(default_factory=ProximalGraphClass)
    graph_checks: tuple[ProximalGraphCheck, ...] = Field(default_factory=tuple)
    bridge_functions: tuple[BridgeFunctionSpec, ...] = Field(default_factory=tuple)
    identified_functionals: tuple[IdentifiedFunctional, ...] = Field(default_factory=tuple)
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    proof_trace: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_certificate(self) -> ProximalIdentificationCertificate:
        if not self.bridge_functions:
            raise ValueError("a proximal certificate must declare at least one bridge function")
        if not self.identified_functionals:
            raise ValueError("a proximal certificate must declare an identified functional")
        failed_checks = [item.check for item in self.graph_checks if item.status == "fail"]
        if failed_checks:
            raise ValueError(f"proximal certificate cannot include failed checks: {failed_checks}")
        return self


def persist_proximal_identification_certificate(
    store: ArtifactStore,
    certificate: ProximalIdentificationCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.proximal_identification_certificate",
    schema_version: str = "1.0",
) -> ProximalIdentificationCertificateRef:
    """Persist a proximal identification certificate and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.proximal_identification_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ProximalIdentificationCertificateRef.model_validate(ref)


def load_proximal_identification_certificate(
    store: ArtifactStore,
    ref: ProximalIdentificationCertificateRef,
) -> ProximalIdentificationCertificate:
    """Load a persisted proximal identification certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ProximalIdentificationCertificate.model_validate(payload)


def persist_bridge_plausibility_report(
    store: ArtifactStore,
    report: BridgePlausibilityReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.bridge_plausibility_report",
    schema_version: str = "1.0",
) -> BridgePlausibilityReportRef:
    """Persist a proximal bridge plausibility report and return its typed ref."""

    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.bridge_plausibility_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return BridgePlausibilityReportRef.model_validate(ref)


def load_bridge_plausibility_report(
    store: ArtifactStore,
    ref: BridgePlausibilityReportRef,
) -> BridgePlausibilityReport:
    """Load a persisted proximal bridge plausibility report."""

    payload = get_json_artifact(store, ref.artifact_id)
    return BridgePlausibilityReport.model_validate(payload)


def _default_fallback_disposition(
    report: BridgePlausibilityReport,
) -> BridgeFallbackDisposition:
    if report.severity is BridgePlausibilitySeverity.GREEN:
        return BridgeFallbackDisposition.PROCEED_POINT_ESTIMATE
    if (
        report.suspected_failure_mode is BridgeFailureMode.INFEASIBLE_EQUATION
        or report.bridge_existence_supported is False
    ):
        return (
            BridgeFallbackDisposition.BLOCK_POINT_ESTIMATE
            if report.severity is BridgePlausibilitySeverity.RED
            else BridgeFallbackDisposition.REQUIRE_BOUNDS
        )
    if report.suspected_failure_mode in {
        BridgeFailureMode.WEAK_COMPLETENESS,
        BridgeFailureMode.NONUNIQUE_SOLUTION,
    } and report.functional_invariant_to_nonuniqueness is not True:
        return BridgeFallbackDisposition.REQUIRE_BOUNDS
    if report.severity is BridgePlausibilitySeverity.RED:
        return BridgeFallbackDisposition.REQUIRE_BOUNDS
    return BridgeFallbackDisposition.PROCEED_WITH_WARNING


__all__ = [
    "BridgeFailureMode",
    "BridgeFallbackDisposition",
    "BridgeFunctionSpec",
    "ProximalMediationBridgeEquation",
    "ProximalMediationCertificate",
    "ProximalMediationCompletenessCondition",
    "ProximalMediationQuerySpec",
    "ProximalMediationTopology",
    "BridgePlausibilityReport",
    "BridgePlausibilitySeverity",
    "IdentifiedFunctional",
    "load_bridge_plausibility_report",
    "load_proximal_identification_certificate",
    "persist_bridge_plausibility_report",
    "ProximalAssumption",
    "ProximalGraphCheck",
    "ProximalGraphClass",
    "ProximalIdentificationCertificate",
    "ProximalQuerySpec",
    "ProxyAnnotation",
    "persist_proximal_identification_certificate",
]
