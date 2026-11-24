"""Science-owned uncertainty source validation and fixed IR entrypoints."""

from __future__ import annotations

import json
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

from polisyos.core.artifacts import profile_bound_ref
from polisyos.core.artifacts.canonical_profile import (
    read_core_manifest_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
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
    propagation_report: PropagationReportV11 | PropagationReportV12 | PropagationReportV13


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifiedStateSlotDrawProjection(PersistedUncertaintySubjectProjection):
    """Expose recomputed local draw arithmetic with the original candidate scope."""

    draw_ledger_ref: ArtifactRefModel
    draw_basis_verification: Literal["recomputed"] = "recomputed"


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


class _ReportDrawFailureFields(BaseModel):
    """Match the common identity of one persisted draw-level failure."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    draw_index: StrictInt = Field(ge=0)
    sampled_input_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class _ReportDrawFailure(_ReportDrawFailureFields):
    """Match a historical draw failure with the historical outcome grammar."""

    output_outcomes: list[_ReportDrawOutputOutcome] = Field(min_length=1)


class _ReportNumericResolutionOutcome(BaseModel):
    """Match loss of nonzero support in the admitted float32 output profile."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    output_metric_id: StrictStr = Field(min_length=1)
    outcome_code: Literal["numeric_resolution_lost"]
    error_type: Literal["float32_projection_underflow"]


class _ReportDrawFailureV13(_ReportDrawFailureFields):
    """Match one numeric-profile-aware draw failure."""

    output_outcomes: list[_ReportDrawOutputOutcome | _ReportNumericResolutionOutcome] = Field(
        min_length=1
    )


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


class _ReportDrawOutcomeProvenance(_ReportDrawOutcomeFields):
    """Match the historical schema-1.0 Monte Carlo ledger."""

    schema_version: Literal["1.0"]
    sampling_recipe: _ReportSamplingRecipe
    failure_records: list[_ReportDrawFailure]


class _ReportDrawOutcomeProvenanceV12(_ReportDrawOutcomeFields):
    """Match schema-1.1 of the Gaussian-joint Monte Carlo ledger."""

    schema_version: Literal["1.1"]
    sampling_recipe: _ReportSamplingRecipeV12
    failure_records: list[_ReportDrawFailure]

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


class _ReportDrawOutcomeProvenanceV13(_ReportDrawOutcomeFields):
    """Match a float32-resolution-aware ledger without changing old grammars."""

    schema_version: Literal["1.2"]
    sampling_recipe: _ReportSamplingRecipeV12 | _ReportSamplingRecipe
    failure_records: list[_ReportDrawFailureV13]
    output_numeric_profile: Literal["float32_finite_support_v1"]

    @model_validator(mode="after")
    def validate_numeric_profile(self) -> _ReportDrawOutcomeProvenanceV13:
        """Require an actual resolution loss and any Gaussian batch denominator."""
        if not any(
            outcome.outcome_code == "numeric_resolution_lost"
            or (
                outcome.outcome_code == "non_finite_output"
                and outcome.error_type == "float32_projection_overflow"
            )
            for record in self.failure_records
            for outcome in record.output_outcomes
        ):
            raise ValueError("float32 numeric profile requires an output resolution loss")
        if (
            isinstance(self.sampling_recipe, _ReportSamplingRecipeV12)
            and sum(
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


class PropagationReportV13(_PropagationReportFields):
    """Science-owned DTO for output-resolution-aware propagation reports."""

    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.3"
    schema_version: Literal["1.3"]
    draw_outcome_provenance: _ReportDrawOutcomeProvenanceV13


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
    report: PropagationReportV11 | PropagationReportV12 | PropagationReportV13
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
    elif report_version == "1.3":
        report = validate_core_model_json_artifact(
            PropagationReportV13,
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


def _verify_state_slot_draws(
    store: FileSystemCAS,
    projection: _ValidatedUncertaintySourceRead,
    result: PersistedUncertaintySubjectProjection,
) -> tuple[ArtifactRef, tuple[str, ...]] | None:
    """Reopen the exact source and replay local draws without physical executions."""
    from polisyos.foundry.calibration.identifiability import load_execute_response_basis_candidate
    from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
    from polisyos.foundry.uncertainty.monte_carlo import MonteCarloDrawOutcomeLedger
    from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
        _DRAW_LEDGER_PRODUCER,
        _DRAW_LEDGER_ROLE,
        _build_execute_response_state_projection_fn,
        _input_ref,
        _load_calibration_response_source,
        _mark_sensitivity_mapping,
        _mark_state_slot_projection,
        _response_lineage_inputs,
        _selected_manifest,
        _supports_response_draw_replay,
    )

    report_ref = ArtifactRef.model_validate(
        projection.propagation_report_ref.model_dump(mode="python")
    )
    report_manifest = store.get_manifest(report_ref)
    edges = [edge for edge in report_manifest.inputs if edge.role == _DRAW_LEDGER_ROLE]
    if not edges:
        return None
    if len(edges) != 1 or edges[0].manifest_profile_sha256 is None:
        raise ValueError("draw outcome ledger must have one selected report edge")
    edge = edges[0]
    ledger_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=MonteCarloDrawOutcomeLedger.ARTIFACT_KIND,
        media_type=MonteCarloDrawOutcomeLedger.ARTIFACT_MEDIA_TYPE,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    report = projection.propagation_report
    claim = report.response_basis_candidate
    state_slot = result.subject_id
    output = (report.state_slot_outputs or {}).get(state_slot)
    if (
        result.envelope is None
        or result.envelope_ref is None
        or claim is None
        or output is None
        or report.mapping_source != "execute_response_matrix"
        or report.methods != ["monte_carlo"]
        or report.output_metric_count != 1
        or set(report.state_slot_outputs or {}) != {state_slot}
    ):
        raise ValueError("draw outcome ledger lacks the bounded response projection")

    config_ref = claim.propagation_config_ref
    _selected_manifest(
        store,
        config_ref,
        expected_kind="foundry.propagation_config",
        model=PropagationConfig,
        expected_schema="polisyos.foundry.PropagationConfig",
        expected_version="1.0",
    )
    config = validate_core_model_json_artifact(
        PropagationConfig,
        store,
        config_ref,
        manifest_profile_sha256=config_ref.manifest_profile_sha256,
    )
    if not _supports_response_draw_replay(config, inputs=report.input_envelope_count, outputs=1):
        raise ValueError("draw outcome ledger is outside the bounded replay profile")

    candidate = load_execute_response_basis_candidate(store, claim.selected_simulation_result_ref)
    source = _load_calibration_response_source(store, claim.calibration_report_ref, candidate)
    if (
        len(source.input_envelopes) != 1
        or candidate.source_simulation_result_ref != claim.source_simulation_result_ref
        or candidate.diagnostic_ref != claim.diagnostic_ref
        or candidate.sensitivity_matrix_ref != claim.sensitivity_matrix_ref
        or candidate.source_inputs != claim.source_inputs
        or source.basis_ref != claim.calibration_execution_input_basis_ref
        or tuple(claim.limitation_codes) != source.limitation_codes
        or {
            name: entry.model_dump(mode="json", exclude_unset=True)
            for name, entry in output.input_envelope_sources.items()
        }
        != source.input_envelope_sources
    ):
        raise ValueError("draw outcome ledger does not bind the recomputed response source")
    ledger_manifest = store.get_manifest(ledger_ref)
    expected_inputs = [
        *_response_lineage_inputs(candidate, source, config_ref=config_ref),
        _input_ref(result.envelope_ref, role=f"state_slot_envelope.{state_slot}"),
    ]
    if (
        ledger_manifest.producer != _DRAW_LEDGER_PRODUCER
        or sorted(ledger_manifest.inputs, key=lambda item: item.role)
        != sorted(expected_inputs, key=lambda item: item.role)
        or sorted(
            (item for item in report_manifest.inputs if item.role != _DRAW_LEDGER_ROLE),
            key=lambda item: item.role,
        )
        != sorted(expected_inputs, key=lambda item: item.role)
    ):
        raise ValueError("draw outcome ledger selected lineage mismatch")
    ledger = validate_core_model_json_artifact(
        MonteCarloDrawOutcomeLedger,
        store,
        ledger_ref,
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    if ledger.requested_draw_count != config.mc_n_samples:
        raise ValueError("draw outcome ledger differs from the selected requested denominator")

    fn, _mapped, statuses, missing = _build_execute_response_state_projection_fn(
        candidate,
        selected_state_slot_ids=[state_slot],
        input_envelopes=source.input_envelopes,
        response_source=source,
    )
    moment = output.response_moment
    if (
        candidate.response_slots.get(moment) != state_slot
        or output.state_path != candidate.state_paths[moment]
        or output.unit_id != candidate.moment_unit_ids[moment]
        or claim.state_slot_to_moment != {state_slot: moment}
        or sorted(claim.missing_parameter_envelopes) != sorted(missing)
    ):
        raise ValueError("draw outcome ledger subject differs from the selected state slot")
    replay = PropagationDispatcher(config, capture_draw_outcome_ledger=True).propagate(
        simulation_fn=fn,
        nominal_params={name: env.point_estimate for name, env in source.input_envelopes.items()},
        input_envelopes=source.input_envelopes,
        output_metric_ids=[state_slot],
    )
    if len(replay) != 1:
        raise ValueError("selected response replay did not return one state slot")
    emitted = replay[0]
    if ledger != MonteCarloDrawOutcomeLedger.model_validate_json(
        json.dumps(emitted.diagnostics[_DRAW_LEDGER_ROLE], allow_nan=False)
    ):
        raise ValueError("draw outcome ledger differs from local replay")
    replay_envelope = _mark_state_slot_projection(
        _mark_sensitivity_mapping(
            emitted,
            mapping_source="execute_response_matrix",
            mapping_status=statuses[state_slot],
        ),
        candidate=candidate,
        response_source=source,
        moment_name=moment,
    )
    if (
        replay_envelope != result.envelope
        or report.draw_outcome_provenance is None
        or report.draw_outcome_provenance.model_dump(mode="json")
        != emitted.diagnostics["draw_outcome_provenance"]
    ):
        raise ValueError("selected envelope or draw provenance differs from local replay")
    return ledger_ref, source.limitation_codes


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
    """Resolve the selected candidate and, when supported, verify its exact draws."""
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
    result = replace(
        result,
        limitation_codes=_reconcile_source_owner_validation(result.limitation_codes),
    )
    if (
        subject_kind != "state_slot"
        or result.envelope is None
        or not isinstance(store, FileSystemCAS)
        or _simulation_result_ref(selector).manifest_profile_sha256 is None
    ):
        return result
    try:
        verified = _verify_state_slot_draws(store, projection, result)
    except _SOURCE_OWNER_READ_ERRORS:
        return replace(
            result, limitation_codes=(*result.limitation_codes, "draw_basis_revalidation_refused")
        )
    if verified is None:
        return result
    ledger_ref, source_limitations = verified
    generic_gaps = {
        "draw_success_ledger_missing",
        "draw_basis_verifier_missing",
        "execute_response_basis_revalidation_not_performed_by_ir",
    }
    applicable_limitations = [code for code in result.limitation_codes if code not in generic_gaps]
    return VerifiedStateSlotDrawProjection(
        subject_kind=result.subject_kind,
        subject_id=result.subject_id,
        envelope=result.envelope,
        envelope_ref=result.envelope_ref,
        limitation_codes=tuple(dict.fromkeys([*applicable_limitations, *source_limitations])),
        draw_ledger_ref=_neutral_ref(ledger_ref),
    )


__all__ = [
    "PropagationReportV11",
    "PropagationReportV12",
    "PropagationReportV13",
    "VerifiedStateSlotDrawProjection",
    "load_science_simulation_result_subject_uncertainty_projection",
    "load_science_simulation_result_uncertainty_admission",
]
