"""Typed mobility report contract with Phase 2 attrition-aware extensions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    BoundsBundleRef,
)

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactStore, InputRef
    from polisyos.ir.registry.refs import MobilityReportRef


def _default_artifact_name(schema_version: str) -> str:
    return (
        "mobility_report_v1.json"
        if str(schema_version).startswith("1.")
        else "mobility_report_v2.json"
    )


class MobilityModelSpec(KernelModel):
    """Lightweight estimator/model specification used inside mobility reports."""

    family: str
    features: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MobilityPopulation(KernelModel):
    """Target-population and class-construction metadata."""

    target_population: str | None = None
    weights_design: str | None = None
    panel_length: int | None = Field(default=None, ge=1)
    waves_used: list[int] = Field(default_factory=list)
    class_definition: dict[str, Any] = Field(default_factory=dict)


class MobilityAttrition(KernelModel):
    """Attrition assumptions and nuisance-model metadata."""

    pattern: str | None = None
    monotone: bool | None = None
    mechanism_assumed: str | None = None
    refreshment_sample: bool | None = None
    positivity_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_model: MobilityModelSpec | None = None
    outcome_model: MobilityModelSpec | None = None


class MobilityPointEstimate(KernelModel):
    """Point-identified mobility outputs."""

    joint_matrix: list[list[float]] = Field(default_factory=list)
    transition_matrix: list[list[float]] = Field(default_factory=list)
    row_marginals: list[float] = Field(default_factory=list)
    col_marginals: list[float] = Field(default_factory=list)
    mobility_stats: dict[str, Any] = Field(default_factory=dict)


class MobilityUncertainty(KernelModel):
    """Uncertainty summary for a mobility report."""

    method: str | None = None
    standard_errors: dict[str, Any] = Field(default_factory=dict)
    confidence_intervals: dict[str, Any] = Field(default_factory=dict)
    bootstrap: dict[str, Any] = Field(default_factory=dict)
    covariance_ref: str | None = None


class MobilityBounds(KernelModel):
    """Compact embedded summary of partial-identification outputs."""

    bundle_ref: BoundsBundleRef | None = None
    cell_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
    summary_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
    sharpness_status: str | None = None
    method: str | None = None


class MobilityBalanceDiagnostics(KernelModel):
    """Covariate-balance diagnostics before and after attrition adjustment."""

    max_abs_smd_before: float | None = None
    max_abs_smd_after: float | None = None


class MobilityDiagnostics(KernelModel):
    """Operational diagnostics for weighting and support checks."""

    effective_sample_size: float | None = None
    max_weight: float | None = None
    p99_weight: float | None = None
    min_retention_probability: float | None = None
    max_retention_probability: float | None = None
    observed_retention_rate: float | None = None
    observed_full_cases: int | None = Field(default=None, ge=0)
    balance: MobilityBalanceDiagnostics | None = None
    placebo_checks: dict[str, Any] = Field(default_factory=dict)
    sensitivity_grid: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class MobilityReport(KernelModel):
    """Backwards-compatible mobility report with Phase 2 typed extensions."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    # Keep the stable contract id for existing Phase 1 method signatures while
    # using ``schema_version`` to differentiate richer payloads.
    contract_id: ClassVar[str] = "ir.mobility_report.v1"

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
    artifact_name: Literal["mobility_report_v1.json", "mobility_report_v2.json"] = (
        "mobility_report_v2.json"
    )
    analysis_type: str
    estimand_id: str | None = None
    status: Literal["ok", "warn", "block"]
    population: MobilityPopulation = Field(default_factory=MobilityPopulation)
    attrition: MobilityAttrition = Field(default_factory=MobilityAttrition)
    point_estimate: MobilityPointEstimate = Field(default_factory=MobilityPointEstimate)
    uncertainty: MobilityUncertainty = Field(default_factory=MobilityUncertainty)
    bounds: MobilityBounds = Field(default_factory=MobilityBounds)
    diagnostics: MobilityDiagnostics = Field(default_factory=MobilityDiagnostics)
    assumptions: list[str] = Field(default_factory=list)
    summary_metrics: dict[str, Any] = Field(default_factory=dict)
    sensitivity_envelope: dict[str, Any] = Field(default_factory=dict)
    upstream_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_payload(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value

        payload = dict(value)
        has_v2_fields = any(
            key in payload
            for key in (
                "estimand_id",
                "population",
                "attrition",
                "point_estimate",
                "uncertainty",
                "bounds",
                "diagnostics",
                "assumptions",
            )
        )
        if "schema_version" in payload:
            raw_schema_version = payload["schema_version"]
            if not isinstance(raw_schema_version, str) or not raw_schema_version:
                raise ValueError(
                    "MobilityReport schema_version must be a non-empty string when present"
                )
            schema_version = raw_schema_version
        else:
            schema_version = "2.0" if has_v2_fields else "1.0"
            payload["schema_version"] = schema_version
        payload.setdefault("artifact_name", _default_artifact_name(schema_version))

        summary_metrics = payload.get("summary_metrics")
        if isinstance(summary_metrics, Mapping) and "point_estimate" not in payload:
            stats: dict[str, Any] = {}
            if "upward_mobility_rate" in summary_metrics:
                stats["upward_rate"] = summary_metrics["upward_mobility_rate"]
            if "downward_mobility_rate" in summary_metrics:
                stats["downward_rate"] = summary_metrics["downward_mobility_rate"]
            if "immobility_rate" in summary_metrics:
                stats["immobility_rate"] = summary_metrics["immobility_rate"]
            point_estimate = {
                "transition_matrix": summary_metrics.get("transition_matrix", []),
                "mobility_stats": stats,
            }
            if point_estimate["transition_matrix"] or point_estimate["mobility_stats"]:
                payload["point_estimate"] = point_estimate

        metadata = payload.get("metadata")
        if isinstance(metadata, Mapping) and "diagnostics" not in payload:
            diagnostics: dict[str, Any] = {}
            valid_observations = metadata.get("valid_observations")
            if valid_observations is not None:
                diagnostics["observed_full_cases"] = int(valid_observations)
            if diagnostics:
                payload["diagnostics"] = diagnostics

        sensitivity = payload.get("sensitivity_envelope")
        if isinstance(sensitivity, Mapping) and "bounds" not in payload:
            bounds: dict[str, Any] = {}
            if "summary_bounds" in sensitivity:
                bounds["summary_bounds"] = sensitivity["summary_bounds"]
            if "bounds_method" in sensitivity:
                bounds["method"] = sensitivity["bounds_method"]
            if bounds:
                payload["bounds"] = bounds
        return payload

    @model_validator(mode="after")
    def _fill_compatibility_views(self) -> MobilityReport:
        summary_metrics = dict(self.summary_metrics)
        if self.point_estimate.transition_matrix and "transition_matrix" not in summary_metrics:
            summary_metrics["transition_matrix"] = self.point_estimate.transition_matrix
        if (
            "upward_mobility_rate" not in summary_metrics
            and "upward_rate" in self.point_estimate.mobility_stats
        ):
            summary_metrics["upward_mobility_rate"] = self.point_estimate.mobility_stats[
                "upward_rate"
            ]
        if (
            "downward_mobility_rate" not in summary_metrics
            and "downward_rate" in self.point_estimate.mobility_stats
        ):
            summary_metrics["downward_mobility_rate"] = self.point_estimate.mobility_stats[
                "downward_rate"
            ]
        if (
            "immobility_rate" not in summary_metrics
            and "immobility_rate" in self.point_estimate.mobility_stats
        ):
            summary_metrics["immobility_rate"] = self.point_estimate.mobility_stats[
                "immobility_rate"
            ]
        if "n_classes" not in summary_metrics:
            n_classes = 0
            if self.point_estimate.transition_matrix:
                n_classes = len(self.point_estimate.transition_matrix)
            elif self.point_estimate.row_marginals:
                n_classes = len(self.point_estimate.row_marginals)
            if n_classes > 0:
                summary_metrics["n_classes"] = n_classes
        if "n_obs" not in summary_metrics and self.diagnostics.observed_full_cases is not None:
            summary_metrics["n_obs"] = int(self.diagnostics.observed_full_cases)
        object.__setattr__(self, "summary_metrics", summary_metrics)

        sensitivity = dict(self.sensitivity_envelope)
        if self.bounds.summary_bounds and "summary_bounds" not in sensitivity:
            sensitivity["summary_bounds"] = self.bounds.summary_bounds
        if self.bounds.method is not None and "bounds_method" not in sensitivity:
            sensitivity["bounds_method"] = self.bounds.method
        if self.uncertainty.confidence_intervals and "confidence_intervals" not in sensitivity:
            sensitivity["confidence_intervals"] = self.uncertainty.confidence_intervals
        object.__setattr__(self, "sensitivity_envelope", sensitivity)
        return self


_OWNER_SCHEMA_NAME = "ir.mobility_report"
_OWNER_SCHEMA_VERSION = "2.0"
_OWNER_WIRE_POLICY = ("ir.owner.mobilityreport.wire", "1")


def _owner_payload_version(payload: object) -> str:
    """Require an embedded source version; a DTO default is not historical evidence."""
    if not isinstance(payload, dict):
        raise TypeError("Owned MobilityReport payload must be a JSON object")
    version = payload.get("schema_version")
    if type(version) is not str or not version.strip():
        raise ValueError("Owned MobilityReport payload requires an explicit schema_version")
    return version


def _validate_owner_source(payload: object, admission: ResolvedSchemaAdmission) -> MobilityReport:
    """Validate bytes only under this owner exact registered source representation."""
    registration = admission.source_registration
    if registration.schema_name != _OWNER_SCHEMA_NAME:
        raise ValueError("Owned MobilityReport source has the wrong schema name")
    if registration.payload_version != _owner_payload_version(payload):
        raise ValueError("Owned MobilityReport payload version disagrees with its representation")
    return MobilityReport.model_validate(payload)


def _project_owner_source(
    source: MobilityReport,
    admission: ResolvedSchemaAdmission,
) -> MobilityReport:
    """Preserve the validated source value when no semantic projection is declared."""
    if not isinstance(source, MobilityReport):
        raise TypeError("Owned MobilityReport source was not validated by its owner")
    if admission.source_registration.payload_version != source.schema_version:
        raise ValueError("Owned MobilityReport projection would change the source version")
    return source


def _validate_owner_profile(
    profile: CanonInfo,
    registration: IRRepresentationRegistration,
) -> bool:
    """Accept only the canonical profile used by this family real writer."""
    expected = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    return registration.profile_ref is None and profile == expected


_mobilityreport_owner = ArtifactOwnerDeclaration(
    contract_id="ir.mobility_report.v1",
    dto_fqn="polisyos.ir.analytics.mobility.MobilityReport",
    abi_key="ir.mobility_report",
    registry_key="ir.mobility_report",
    kind="ir.mobility_report",
    media_type="application/json",
    purpose="ir.mobility_report.typed_consumer",
    policy_revision="ir.mobility_report.v1.owner-admission.v1",
    accepted_wire_policies=(_OWNER_WIRE_POLICY,),
    payload_version_of=_owner_payload_version,
    validate_source=_validate_owner_source,
    project_for_consumer=_project_owner_source,
    validate_profile=_validate_owner_profile,
)


register_schema_version(
    _OWNER_SCHEMA_NAME,
    _OWNER_SCHEMA_VERSION,
    compatibility=CompatibilityMode.NONE,
    notes=(
        "MobilityReport current owner-admitted representation; historical predecessors are not registered.",
    ),
)
register_ir_representation(
    registry_key=_mobilityreport_owner.registry_key,
    owner_ref=_mobilityreport_owner.contract_id,
    dto_abi=_mobilityreport_owner.dto_fqn,
    wire_policy_ref=_OWNER_WIRE_POLICY[0],
    wire_policy_revision=_OWNER_WIRE_POLICY[1],
    schema_name=_OWNER_SCHEMA_NAME,
    schema_version=_OWNER_SCHEMA_VERSION,
    payload_version=_OWNER_SCHEMA_VERSION,
    profile_ref=None,
    readable=True,
    writable=True,
    current=True,
    default_write=True,
)


def persist_mobility_report(
    store: ArtifactStore,
    report: MobilityReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.mobility_report",
    schema_version: str | None = None,
) -> MobilityReportRef:
    """Persist a source-validated MobilityReport under its exact owned representation."""
    selected = _put_owned_json_artifact(
        store,
        report.model_dump(mode="json"),
        owner=_mobilityreport_owner,
        schema_name=schema_name,
        schema_version=report.schema_version if schema_version is None else schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    from polisyos.ir.registry.refs import MobilityReportRef

    return MobilityReportRef.model_validate(selected)


def load_mobility_report(store: ArtifactStore, ref: MobilityReportRef) -> MobilityReport:
    """Read MobilityReport only after its trusted owner admits the stored representation."""
    return _get_owned_json_artifact(store, ref, owner=_mobilityreport_owner)


__all__ = [
    "MobilityAttrition",
    "MobilityBalanceDiagnostics",
    "MobilityBounds",
    "MobilityDiagnostics",
    "MobilityModelSpec",
    "MobilityPointEstimate",
    "MobilityPopulation",
    "MobilityReport",
    "MobilityUncertainty",
    "load_mobility_report",
    "persist_mobility_report",
]
