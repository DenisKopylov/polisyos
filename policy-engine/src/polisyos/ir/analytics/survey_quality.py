"""Survey-quality contracts for design-aware missing-data estimation."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from polisyos.ir.analytics.administrative_missingness import (
    AdministrativeMissingnessClass,
    AdministrativeMissingnessDirection,
    AdministrativeMissingnessScenarioFamily,
    AdministrativeMissingnessUnitScope,
    MissingnessAssessmentReport,
    MissingnessAssessmentStatus,
)
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.ir.artifacts.contracts import ArtifactStore
    from polisyos.ir.artifacts.refs import InputRef
    from polisyos.ir.references import SurveyQualityCertificateRef

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class SurveyAssumptionLayer(str, Enum):
    """High-level layer audited by the survey quality certificate."""

    DESIGN = "design"
    IMPUTATION = "imputation"
    IDENTIFICATION = "identification"
    POSITIVITY = "positivity"
    VARIANCE = "variance"
    MISSINGNESS = "missingness"


class SurveyAssumptionStatus(str, Enum):
    """Pass/fail state for one assumption component."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    UNTESTED = "untested"


class SurveyRequestedRegime(str, Enum):
    """Requested identification regime for the estimator run."""

    POPULATION_MAR = "population_mar"
    MNAR_SHADOW = "mnar_shadow"


class SurveyValidatedRegime(str, Enum):
    """Validated regime returned by the diagnostic router."""

    BOTH_VALID = "both_valid"
    DESIGN_VALID_ONLY = "design_valid_only"
    IMPUTATION_VALID_ONLY = "imputation_valid_only"
    MNAR_SHADOW_IDENTIFIED = "mnar_shadow_identified"
    NEITHER_VALID = "neither_valid"
    MNAR_UNIDENTIFIED = "mnar_unidentified"


class SurveyVarianceMode(str, Enum):
    """Variance path used by the estimator."""

    REPLICATE = "replicate"
    SANDWICH = "sandwich"
    BOOTSTRAP = "bootstrap"


class SurveyAssumptionComponent(KernelModel):
    """One auditable assumption component in the survey certificate."""

    component_id: str = Field(..., pattern=ID_PATTERN)
    layer: SurveyAssumptionLayer
    statement: str = Field(..., min_length=1, max_length=500)
    status: SurveyAssumptionStatus
    metric_name: str | None = Field(None, min_length=1, max_length=120)
    metric_value: float | None = None
    threshold_value: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SurveyQualityCertificate(KernelModel):
    """Operational certificate for survey DR estimation under design + missingness."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    artifact_name: Literal["survey_quality_certificate_v1.json"] = (
        "survey_quality_certificate_v1.json"
    )

    target_estimand: str = Field(..., min_length=1, max_length=255)
    estimator_id: str = Field(..., min_length=1, max_length=255)
    dataset_id: str | None = Field(default=None, min_length=1, max_length=255)
    data_origin: str | None = Field(default=None, min_length=1, max_length=255)
    regime_requested: SurveyRequestedRegime
    regime_validated: SurveyValidatedRegime
    missingness_class: AdministrativeMissingnessClass = AdministrativeMissingnessClass.NONE
    missingness_family: AdministrativeMissingnessScenarioFamily = (
        AdministrativeMissingnessScenarioFamily.UNKNOWN
    )
    missingness_direction: AdministrativeMissingnessDirection = (
        AdministrativeMissingnessDirection.UNKNOWN
    )
    missingness_unit_scope: AdministrativeMissingnessUnitScope = (
        AdministrativeMissingnessUnitScope.UNKNOWN
    )
    missingness_status: MissingnessAssessmentStatus | None = None
    missingness_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    target_variables: list[str] = Field(default_factory=list)

    estimate: float
    standard_error: float = Field(ge=0.0)
    variance_mode: SurveyVarianceMode
    estimated_efficiency_bound: float | None = Field(default=None, ge=0.0)

    design_assumptions: list[SurveyAssumptionComponent] = Field(default_factory=list)
    imputation_assumptions: list[SurveyAssumptionComponent] = Field(default_factory=list)
    identification_assumptions: list[SurveyAssumptionComponent] = Field(default_factory=list)
    missingness_assumptions: list[SurveyAssumptionComponent] = Field(default_factory=list)

    overlap_score: float | None = Field(default=None, ge=0.0, le=1.0)
    effective_sample_size: float | None = Field(default=None, ge=0.0)
    max_weight: float | None = Field(default=None, ge=0.0)
    weight_cv: float | None = Field(default=None, ge=0.0)

    orthogonality_score_design: float | None = Field(default=None, ge=0.0)
    orthogonality_score_imputation: float | None = Field(default=None, ge=0.0)
    sensitivity_radius: float | None = Field(default=None, ge=0.0)

    overall_pass: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_certificate(self) -> SurveyQualityCertificate:
        allowed_when_passing = {
            SurveyValidatedRegime.BOTH_VALID,
            SurveyValidatedRegime.DESIGN_VALID_ONLY,
            SurveyValidatedRegime.IMPUTATION_VALID_ONLY,
            SurveyValidatedRegime.MNAR_SHADOW_IDENTIFIED,
        }
        if self.overall_pass and self.regime_validated not in allowed_when_passing:
            raise ValueError("overall_pass=True requires a validated passing regime")
        if (
            self.regime_validated is SurveyValidatedRegime.MNAR_SHADOW_IDENTIFIED
            and self.sensitivity_radius is None
        ):
            raise ValueError("mnar_shadow_identified requires a sensitivity_radius")
        return self

    def as_evidence_payload(self) -> dict[str, Any]:
        """Return a compact evidence payload suitable for sibling quality layers."""

        return {
            "artifact_name": self.artifact_name,
            "schema_version": self.schema_version,
            "target_estimand": self.target_estimand,
            "estimator_id": self.estimator_id,
            "dataset_id": self.dataset_id,
            "data_origin": self.data_origin,
            "regime_requested": self.regime_requested.value,
            "regime_validated": self.regime_validated.value,
            "missingness_class": self.missingness_class.value,
            "missingness_family": self.missingness_family.value,
            "missingness_direction": self.missingness_direction.value,
            "missingness_unit_scope": self.missingness_unit_scope.value,
            "missingness_status": (
                self.missingness_status.value if self.missingness_status is not None else None
            ),
            "missingness_confidence": self.missingness_confidence,
            "target_variables": list(self.target_variables),
            "estimate": self.estimate,
            "standard_error": self.standard_error,
            "variance_mode": self.variance_mode.value,
            "overall_pass": self.overall_pass,
            "blocking_reasons": list(self.blocking_reasons),
            "evidence_refs": list(self.evidence_refs),
            "overlap_score": self.overlap_score,
            "effective_sample_size": self.effective_sample_size,
            "max_weight": self.max_weight,
            "weight_cv": self.weight_cv,
        }


def build_survey_quality_certificate(
    *,
    target_estimand: str,
    estimator_id: str = "survey_quality",
    dataset_id: str | None = None,
    data_origin: str | None = None,
    regime_requested: SurveyRequestedRegime = SurveyRequestedRegime.POPULATION_MAR,
    regime_validated: SurveyValidatedRegime = SurveyValidatedRegime.BOTH_VALID,
    estimate: float = 0.0,
    standard_error: float = 0.0,
    variance_mode: SurveyVarianceMode = SurveyVarianceMode.SANDWICH,
    design_assumptions: Iterable[SurveyAssumptionComponent] = (),
    imputation_assumptions: Iterable[SurveyAssumptionComponent] = (),
    identification_assumptions: Iterable[SurveyAssumptionComponent] = (),
    missingness_assumptions: Iterable[SurveyAssumptionComponent] = (),
    missingness_assessment: MissingnessAssessmentReport | dict[str, Any] | None = None,
    overlap_score: float | None = None,
    effective_sample_size: float | None = None,
    max_weight: float | None = None,
    weight_cv: float | None = None,
    orthogonality_score_design: float | None = None,
    orthogonality_score_imputation: float | None = None,
    sensitivity_radius: float | None = None,
    overall_pass: bool | None = None,
    blocking_reasons: Iterable[str] = (),
    evidence_refs: Iterable[str] = (),
    evidence_payload: dict[str, Any] | None = None,
    estimated_efficiency_bound: float | None = None,
) -> SurveyQualityCertificate:
    """Convenience constructor mirroring the common estimator payload shape."""

    assessment = _normalize_missingness_assessment(missingness_assessment)
    resolved_design_assumptions = list(design_assumptions)
    resolved_imputation_assumptions = list(imputation_assumptions)
    resolved_identification_assumptions = list(identification_assumptions)
    resolved_missingness_assumptions = list(missingness_assumptions)
    resolved_blocking_reasons = [
        str(item).strip() for item in blocking_reasons if str(item).strip()
    ]
    resolved_evidence_refs = [str(item).strip() for item in evidence_refs if str(item).strip()]
    payload = dict(evidence_payload or {})

    missingness_class = AdministrativeMissingnessClass.NONE
    missingness_family = AdministrativeMissingnessScenarioFamily.UNKNOWN
    missingness_direction = AdministrativeMissingnessDirection.UNKNOWN
    missingness_unit_scope = AdministrativeMissingnessUnitScope.UNKNOWN
    missingness_status: MissingnessAssessmentStatus | None = None
    missingness_confidence = 0.0
    target_variables: list[str] = []

    if assessment is not None:
        missingness_class = assessment.scenario_class
        missingness_family = assessment.scenario_family
        missingness_direction = assessment.missingness_direction
        missingness_unit_scope = assessment.missingness_unit_scope
        missingness_status = assessment.status
        missingness_confidence = assessment.scenario_confidence
        target_variables = _target_variables_from_assessment(assessment)
        resolved_missingness_assumptions.append(_missingness_component_from_assessment(assessment))
        resolved_evidence_refs.extend(item.ref for item in assessment.evidence)
        payload.setdefault("missingness_assessment", assessment.model_dump(mode="json"))
        if assessment.status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
            resolved_blocking_reasons.append("missingness_not_recoverable")

    resolved_blocking_reasons = _stable_strings(resolved_blocking_reasons)
    resolved_evidence_refs = _stable_strings(resolved_evidence_refs)

    if overall_pass is None:
        overall_pass = len(resolved_blocking_reasons) == 0

    return SurveyQualityCertificate(
        target_estimand=target_estimand,
        estimator_id=estimator_id,
        dataset_id=dataset_id,
        data_origin=data_origin,
        regime_requested=regime_requested,
        regime_validated=regime_validated,
        missingness_class=missingness_class,
        missingness_family=missingness_family,
        missingness_direction=missingness_direction,
        missingness_unit_scope=missingness_unit_scope,
        missingness_status=missingness_status,
        missingness_confidence=missingness_confidence,
        target_variables=target_variables,
        estimate=estimate,
        standard_error=standard_error,
        variance_mode=variance_mode,
        estimated_efficiency_bound=estimated_efficiency_bound,
        design_assumptions=resolved_design_assumptions,
        imputation_assumptions=resolved_imputation_assumptions,
        identification_assumptions=resolved_identification_assumptions,
        missingness_assumptions=resolved_missingness_assumptions,
        overlap_score=overlap_score,
        effective_sample_size=effective_sample_size,
        max_weight=max_weight,
        weight_cv=weight_cv,
        orthogonality_score_design=orthogonality_score_design,
        orthogonality_score_imputation=orthogonality_score_imputation,
        sensitivity_radius=sensitivity_radius,
        overall_pass=overall_pass,
        blocking_reasons=resolved_blocking_reasons,
        evidence_refs=_stable_strings(resolved_evidence_refs),
        evidence_payload=payload,
    )


def _normalize_missingness_assessment(
    payload: MissingnessAssessmentReport | dict[str, Any] | None,
) -> MissingnessAssessmentReport | None:
    if payload is None:
        return None
    if isinstance(payload, MissingnessAssessmentReport):
        return payload
    return MissingnessAssessmentReport.model_validate(payload)


def _missingness_component_from_assessment(
    assessment: MissingnessAssessmentReport,
) -> SurveyAssumptionComponent:
    if assessment.status is MissingnessAssessmentStatus.RECOVERABLE:
        status = SurveyAssumptionStatus.PASS
    elif assessment.status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
        status = SurveyAssumptionStatus.FAIL
    else:
        status = SurveyAssumptionStatus.WARN
    return SurveyAssumptionComponent(
        component_id="administrative_missingness",
        layer=SurveyAssumptionLayer.MISSINGNESS,
        statement=f"{assessment.scenario_class.value}:{assessment.status.value}",
        status=status,
        evidence_refs=[item.ref for item in assessment.evidence],
        notes=list(assessment.recommended_method_stack[:2]),
    )


def _target_variables_from_assessment(
    assessment: MissingnessAssessmentReport,
) -> list[str]:
    raw = assessment.metadata.get("administrative_missingness")
    if isinstance(raw, dict):
        target_variables = raw.get("target_variables")
        if isinstance(target_variables, list):
            return _stable_strings(target_variables)
    return _stable_strings(assessment.key_variables)


def _stable_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def persist_survey_quality_certificate(
    store: ArtifactStore,
    certificate: SurveyQualityCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.survey_quality_certificate",
    schema_version: str = "1.0",
) -> SurveyQualityCertificateRef:
    """Persist a survey-quality certificate and return its typed artifact ref."""

    from polisyos.ir.artifacts.io import put_json_artifact
    from polisyos.ir.canon import CanonSpec
    from polisyos.ir.references import SurveyQualityCertificateRef

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.survey_quality_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SurveyQualityCertificateRef.model_validate(ref)


def load_survey_quality_certificate(
    store: ArtifactStore,
    ref: SurveyQualityCertificateRef,
) -> SurveyQualityCertificate:
    """Load a persisted survey-quality certificate."""

    from polisyos.ir.artifacts.io import get_json_artifact

    payload = get_json_artifact(store, ref.artifact_id)
    return SurveyQualityCertificate.model_validate(payload)


__all__ = [
    "SurveyAssumptionComponent",
    "SurveyAssumptionLayer",
    "SurveyAssumptionStatus",
    "SurveyQualityCertificate",
    "SurveyRequestedRegime",
    "SurveyValidatedRegime",
    "SurveyVarianceMode",
    "build_survey_quality_certificate",
    "load_survey_quality_certificate",
    "persist_survey_quality_certificate",
]
