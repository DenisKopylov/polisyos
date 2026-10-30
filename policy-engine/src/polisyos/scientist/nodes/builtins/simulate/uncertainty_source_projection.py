"""Science-owned uncertainty source validation and fixed IR entrypoints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from polisyos.core.artifacts._profiled_ref import profile_bound_ref
from polisyos.core.artifacts.canonical_profile import (
    read_core_manifest_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import (
    CalibrationReportRef,
    IdentifiabilityDiagnosticRef,
    SimulationResult,
    SimulationResultRef,
    UncertaintyEnvelopeRef,
)
from polisyos.foundry.calibration.identifiability import ExecuteResponseSourceIdentity
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir.analytics.uncertainty import (
    PersistedUncertaintyAdmission,
    PersistedUncertaintySubjectProjection,
    load_simulation_result_subject_uncertainty_projection,
    load_simulation_result_uncertainty_admission,
)
from polisyos.ir.registry import ArtifactRefModel

_SHA256_PATTERN = r"^(?:sha256:)?[0-9a-f]{64}$"


@dataclass(frozen=True, slots=True)
class _ValidatedUncertaintySourceRead:
    # Produced and consumed inside this fixed Science bridge; never accepted as input.
    simulation_result_ref: ArtifactRefModel
    simulation_result: SimulationResult
    propagation_report_ref: ArtifactRefModel
    propagation_report: PropagationReportV11 | PropagationReportV12


class _ReportMetricDiagnostic(BaseModel):
    """Match one diagnostic row emitted by the current propagation producer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    metric_id: StrictStr = Field(min_length=1)
    method: Literal["delta_method", "monte_carlo", "analytical", "none"]
    diagnostics: dict[StrictStr, Any]


class _ReportResponseBasisCandidate(BaseModel):
    """Match the full candidate response-basis projection persisted by Science."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"]
    evidence_grade: Literal["candidate"]
    gate_eligible: Literal[False]
    mapping_status: Literal["candidate_only", "partial"]
    mapping_basis_status: Literal["candidate_only"]
    state_slot_to_moment: dict[StrictStr, StrictStr]
    source_inputs: dict[StrictStr, ExecuteResponseSourceIdentity]
    selected_simulation_result_ref: SimulationResultRef
    source_simulation_result_ref: SimulationResultRef
    diagnostic_ref: IdentifiabilityDiagnosticRef
    sensitivity_matrix_ref: ArtifactRef
    calibration_report_ref: CalibrationReportRef
    calibration_execution_input_basis_ref: ArtifactRef
    propagation_config_ref: ArtifactRef
    limitation_codes: list[StrictStr]
    missing_parameter_envelopes: list[StrictStr]


class _ReportInputEnvelopeSource(BaseModel):
    """Match the complete calibration-envelope source projection in the report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_form: Literal["embedded_in_selected_report"]
    calibration_report_ref: CalibrationReportRef
    calibration_execution_input_basis_ref: ArtifactRef
    content_sha256: StrictStr = Field(pattern=_SHA256_PATTERN)
    standalone_envelope_ref: UncertaintyEnvelopeRef | None = None


class _ReportStateSlotOutput(BaseModel):
    """Match one state-slot output row emitted by the propagation producer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    subject_kind: Literal["state_slot"]
    subject_id: StrictStr = Field(min_length=1)
    state_path: StrictStr = Field(min_length=1)
    unit_id: StrictStr = Field(min_length=1)
    response_moment: StrictStr = Field(min_length=1)
    envelope_ref: UncertaintyEnvelopeRef | None
    evidence_grade: Literal["candidate"]
    gate_eligible: Literal[False]
    input_envelope_sources: dict[StrictStr, _ReportInputEnvelopeSource]


class _ReportSamplingRecipe(BaseModel):
    """Match the full shared sampling recipe persisted by Monte Carlo."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    config: PropagationConfig
    input_param_names: list[StrictStr]
    input_envelope_sha256: dict[StrictStr, StrictStr | None]
    sample_axis: StrictStr = Field(min_length=1)
    joint_sample_id: StrictStr | None


class _GaussianValidationTolerances(BaseModel):
    """Record the numerical thresholds used when validating the declared law."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    diagonal_rtol: StrictFloat = Field(ge=0)
    diagonal_atol: StrictFloat = Field(ge=0)
    symmetry_rtol: StrictFloat = Field(ge=0)
    symmetry_atol: StrictFloat = Field(ge=0)
    negative_eigenvalue_scale_rtol: StrictFloat = Field(ge=0)


class _GaussianDrawBatch(BaseModel):
    """Record the actual transform types and seed context of one draw batch."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    first_draw: StrictInt = Field(ge=0)
    draw_count: StrictInt = Field(gt=0)
    source_dtype: StrictStr = Field(min_length=1)
    factor_dtype: StrictStr = Field(min_length=1)
    mean_dtype: StrictStr = Field(min_length=1)
    joint_dtype: StrictStr = Field(min_length=1)
    device: StrictStr = Field(min_length=1)
    prng_implementation: StrictStr | None
    replicate_index: StrictInt | None = Field(ge=0)
    replicate_seed: StrictInt | None


class _GaussianNumericProfile(BaseModel):
    """Record actual numeric execution details, without asserting source authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    backend: Literal["jax_random", "scipy_qmc"]
    jax_version: StrictStr = Field(min_length=1)
    jaxlib_version: StrictStr = Field(min_length=1)
    numpy_version: StrictStr = Field(min_length=1)
    scipy_version: StrictStr | None
    covariance_validation_dtype: StrictStr = Field(min_length=1)
    covariance_storage_dtype: StrictStr = Field(min_length=1)
    factor_dtype: StrictStr = Field(min_length=1)
    means: list[StrictFloat] = Field(min_length=1)
    factor_rows: list[list[StrictFloat]] = Field(min_length=1)
    draw_batches: list[_GaussianDrawBatch] = Field(min_length=1)
    summary_dtypes: list[StrictStr] = Field(min_length=1)
    validation_tolerances: _GaussianValidationTolerances
    qmc_uniform_clip: list[StrictFloat] | None


class _ReportSamplingRecipeV12(_ReportSamplingRecipe):
    """Bind the axis and assumption of an executed Gaussian joint sampler."""

    gaussian_joint_names: list[StrictStr] = Field(min_length=1)
    gaussian_joint_assumption: Literal["multivariate_normal_with_declared_covariance"]
    gaussian_numeric_profile: _GaussianNumericProfile

    @model_validator(mode="after")
    def validate_gaussian_joint_declaration(self) -> _ReportSamplingRecipeV12:
        """Require the declared Gaussian axes to match the emitted input order."""
        if (
            self.gaussian_joint_names != self.input_param_names
            or self.gaussian_joint_names != sorted(set(self.gaussian_joint_names))
            or set(self.gaussian_joint_names) != set(self.input_envelope_sha256)
            or self.sample_axis != "draw"
            or self.joint_sample_id is not None
        ):
            raise ValueError("Gaussian joint declaration does not match the input axes")
        profile = self.gaussian_numeric_profile
        dimension = len(self.gaussian_joint_names)
        if (
            len(profile.means) != dimension
            or len(profile.factor_rows) != dimension
            or any(len(row) != dimension for row in profile.factor_rows)
        ):
            raise ValueError("Gaussian transform dimensions do not match the input axes")
        qmc = self.config.mc_sampling_method != "random"
        if qmc:
            clip = profile.qmc_uniform_clip
            if (
                profile.backend != "scipy_qmc"
                or not profile.scipy_version
                or clip is None
                or len(clip) != 2
                or not 0.0 <= clip[0] < clip[1] <= 1.0
            ):
                raise ValueError("QMC Gaussian execution profile is incomplete")
        elif (
            profile.backend != "jax_random"
            or profile.scipy_version is not None
            or profile.qmc_uniform_clip is not None
        ):
            raise ValueError("random Gaussian execution profile is inconsistent")
        next_draw = 0
        for batch in profile.draw_batches:
            if batch.first_draw != next_draw:
                raise ValueError("Gaussian draw batches must be contiguous")
            next_draw += batch.draw_count
            if qmc:
                if (
                    batch.prng_implementation is not None
                    or batch.replicate_index is None
                    or batch.replicate_seed != self.config.mc_seed + batch.replicate_index
                ):
                    raise ValueError("QMC Gaussian batch seed context is inconsistent")
            elif (
                not batch.prng_implementation
                or batch.replicate_index is not None
                or batch.replicate_seed is not None
            ):
                raise ValueError("random Gaussian batch seed context is inconsistent")
        return self


class _ReportDrawOutputOutcome(BaseModel):
    """Match one persisted output failure classification."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    output_metric_id: StrictStr = Field(min_length=1)
    outcome_code: Literal[
        "simulation_exception",
        "invalid_response",
        "missing_output",
        "non_numeric_output",
        "non_finite_output",
    ]
    error_type: StrictStr | None = None


class _ReportDrawFailure(BaseModel):
    """Match one draw-level failure row persisted by Monte Carlo."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    draw_index: StrictInt = Field(ge=0)
    sampled_input_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    output_outcomes: list[_ReportDrawOutputOutcome] = Field(min_length=1)


class _ReportDrawOutcomeFields(BaseModel):
    """Shared count and failure fields of the versioned Monte Carlo ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    requested_draw_count: StrictInt = Field(ge=0)
    attempted_draw_count: StrictInt = Field(ge=0)
    simulation_attempt_count: StrictInt = Field(ge=0)
    retry_attempt_count: StrictInt = Field(ge=0)
    successful_draw_count: StrictInt = Field(ge=0)
    unattempted_draw_count: StrictInt = Field(ge=0)
    outcome_denominator_complete: StrictBool
    input_identity_status: Literal["content_hashed", "not_established"]
    implementation_identity_status: Literal["not_established"]
    draw_identity_basis: Literal["sampling_recipe+draw_index+sampled_input_sha256"]
    failure_records: list[_ReportDrawFailure]


class _ReportDrawOutcomeProvenance(_ReportDrawOutcomeFields):
    """Match the historical schema-1.0 Monte Carlo ledger."""

    schema_version: Literal["1.0"]
    sampling_recipe: _ReportSamplingRecipe


class _ReportDrawOutcomeProvenanceV12(_ReportDrawOutcomeFields):
    """Match schema-1.1 of the Gaussian-joint Monte Carlo ledger."""

    schema_version: Literal["1.1"]
    sampling_recipe: _ReportSamplingRecipeV12

    @model_validator(mode="after")
    def validate_batch_denominator(self) -> _ReportDrawOutcomeProvenanceV12:
        """Require the batch trace to cover exactly the attempted draw ledger."""
        if (
            sum(
                batch.draw_count
                for batch in self.sampling_recipe.gaussian_numeric_profile.draw_batches
            )
            != self.attempted_draw_count
        ):
            raise ValueError("Gaussian batch trace does not cover attempted draws")
        return self


class _PropagationReportFields(BaseModel):
    """Shared fields of Science-owned propagation reports."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.foundry.PropagationReport"
    ARTIFACT_KIND: ClassVar[Literal["foundry.propagation_report"]] = "foundry.propagation_report"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    input_envelope_count: StrictInt = Field(ge=0)
    output_metric_count: StrictInt = Field(ge=0)
    mapped_param_count: StrictInt = Field(ge=0)
    mapped_params: list[StrictStr]
    mapping_status: Literal[
        "candidate_only", "consumer_asserted", "partial", "resolved", "unresolved"
    ]
    mapping_source: Literal["execute_response_matrix", "caller_parameters", "not_established"]
    mapping_basis_status: Literal["candidate_only", "consumer_asserted", "not_established"]
    unmapped_metric_ids: list[StrictStr]
    missing_output_metric_ids: list[StrictStr]
    methods: list[Literal["delta_method", "monte_carlo", "analytical", "none"]]
    diagnostics: list[_ReportMetricDiagnostic]
    incomplete_output_metric_ids: list[StrictStr]
    response_basis_candidate: _ReportResponseBasisCandidate | None = None
    state_slot_outputs: dict[StrictStr, _ReportStateSlotOutput] | None = None


class PropagationReportV11(_PropagationReportFields):
    """Science-owned strict DTO for the historical PropagationReport 1.1 grammar."""

    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.1"
    schema_version: Literal["1.1"]
    draw_outcome_provenance: _ReportDrawOutcomeProvenance | None = None


class PropagationReportV12(_PropagationReportFields):
    """Science-owned strict DTO for Gaussian-joint PropagationReport 1.2."""

    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.2"
    schema_version: Literal["1.2"]
    draw_outcome_provenance: _ReportDrawOutcomeProvenanceV12


def _simulation_result_ref(selector: object) -> SimulationResultRef:
    """Normalize a caller selector to the Core-owned typed SimulationResult ref."""
    if isinstance(selector, (str, ArtifactID)):
        return SimulationResultRef(artifact_id=ArtifactID.model_validate(selector))
    if isinstance(selector, BaseModel):
        payload: object = selector.model_dump(mode="python")
    else:
        payload = selector
    if not isinstance(payload, Mapping):
        raise TypeError("simulation_result_selector_malformed")
    return SimulationResultRef.model_validate(dict(payload))


def _neutral_ref(ref: BaseModel) -> ArtifactRefModel:
    """Project an owner ref into the neutral IR carrier without changing its selection."""
    return ArtifactRefModel.model_validate(ref.model_dump(mode="python"))


def _load_validated_uncertainty_source_read(
    store: object,
    selector: object,
) -> _ValidatedUncertaintySourceRead:
    """Read Core and Science uncertainty source DTOs from exact selected CAS profiles.

    The result is a typed transport projection, not an admissibility decision.
    Core validates SimulationResult with its selected-profile reader. Science
    validates PropagationReport against its selected version's strict DTO.
    """
    simulation_ref = profile_bound_ref(store, _simulation_result_ref(selector))
    simulation_result = validate_core_model_json_artifact(
        SimulationResult,
        store,
        simulation_ref,
        manifest_profile_sha256=simulation_ref.manifest_profile_sha256,
    )
    if simulation_result.propagation_report_ref is None:
        raise ValueError("uncertainty_source_propagation_report_ref_missing")

    report_ref = ArtifactRef.model_validate(
        simulation_result.propagation_report_ref.model_dump(mode="python")
    )
    selected_report_ref = profile_bound_ref(store, report_ref)
    report_manifest, _ = read_core_manifest_profile(
        store,
        selected_report_ref,
        manifest_profile_sha256=selected_report_ref.manifest_profile_sha256,
    )
    report_version = (
        None if report_manifest.artifact_schema is None else report_manifest.artifact_schema.version
    )
    report: PropagationReportV11 | PropagationReportV12
    if report_version == "1.1":
        report = validate_core_model_json_artifact(
            PropagationReportV11,
            store,
            selected_report_ref,
            manifest_profile_sha256=selected_report_ref.manifest_profile_sha256,
        )
    elif report_version == "1.2":
        report = validate_core_model_json_artifact(
            PropagationReportV12,
            store,
            selected_report_ref,
            manifest_profile_sha256=selected_report_ref.manifest_profile_sha256,
        )
    else:
        raise ValueError("uncertainty_source_propagation_report_version_unsupported")
    return _ValidatedUncertaintySourceRead(
        simulation_result_ref=_neutral_ref(simulation_ref),
        simulation_result=simulation_result,
        propagation_report_ref=_neutral_ref(selected_report_ref),
        propagation_report=report,
    )


_SOURCE_OWNER_READ_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


def _reconcile_source_owner_validation(
    limitation_codes: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        code for code in limitation_codes if code != "source_owner_validation_not_performed"
    )


def load_science_simulation_result_uncertainty_admission(
    store: object,
    selector: object,
    metric_id: str,
) -> PersistedUncertaintyAdmission:
    # Only the store, selected SimulationResult ref, and metric subject are caller supplied.
    # Core SimulationResult and Science PropagationReport validators are hardwired here.
    try:
        projection = _load_validated_uncertainty_source_read(store, selector)
    except _SOURCE_OWNER_READ_ERRORS:
        return PersistedUncertaintyAdmission(None, ("source_owner_validation_refused",))

    admission = load_simulation_result_uncertainty_admission(
        ensure_ir_artifact_store(store),
        projection.simulation_result_ref,
        metric_id,
    )
    return replace(
        admission,
        limitation_codes=_reconcile_source_owner_validation(admission.limitation_codes),
    )


def load_science_simulation_result_subject_uncertainty_projection(
    store: object,
    selector: object,
    *,
    subject_kind: Literal["metric", "state_slot"],
    subject_id: str,
) -> PersistedUncertaintySubjectProjection:
    # Projection remains candidate-only. This records only that both owner validators ran.
    try:
        projection = _load_validated_uncertainty_source_read(store, selector)
    except _SOURCE_OWNER_READ_ERRORS:
        return PersistedUncertaintySubjectProjection(
            subject_kind=subject_kind,
            subject_id=str(subject_id),
            envelope=None,
            envelope_ref=None,
            limitation_codes=("source_owner_validation_refused",),
        )

    result = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        projection.simulation_result_ref,
        subject_kind=subject_kind,
        subject_id=subject_id,
    )
    return replace(
        result,
        limitation_codes=_reconcile_source_owner_validation(result.limitation_codes),
    )


__all__ = [
    "PropagationReportV11",
    "PropagationReportV12",
    "load_science_simulation_result_subject_uncertainty_projection",
    "load_science_simulation_result_uncertainty_admission",
]
