"""Owned effective-basis comparison for an admitted acquisition occurrence.

Source admission, evaluation meaning and execution occurrence are separate. A
selected schema/profile or matching hash never grants retention: the bridge
replays all supported owner values and the actual selected execution. Unknown
facets conservatively request re-entry. The SQL/native terminal fence is the
linearization point, not publication of these immutable candidate records.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.runtime.quality.agent_action_authority import write_runtime_authority_artifact
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationScenarioProfile,
    CandidateSimulationSyntheticModelDeclarationV1,
    _require_n5_field_role_census,
)
from polisyos.runtime.quality.candidate_source_basis import CandidateSourceBasisInputs
from polisyos.runtime.quality.data_state_substrate import ControlledAcquisitionSlotBinding
from polisyos.runtime.quality.joint_simulation_horizon import PreparedJointSimulationConfiguration
from polisyos.runtime.quality.n5_execution_basis import (
    _exact_native_content,
    exact_n5_content_bytes,
    exact_n5_content_hash,
    exact_n5_model_field_names,
    read_n5_execution_implementation_witness,
    reconcile_live_n5_implementation,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.core.contracts import FoundryInputBindingRule
    from polisyos.core.registry import RegistryBundleContent
    from polisyos.runtime.http.services.control.run_lifecycle import VerifiedAcquisitionActionPhase
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierRecord,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
        AcquisitionCandidateRouteLoopReceipt,
        AcquisitionRouteLoopReceiptV2,
        VerifiedAcquisitionRouteClosure,
        VerifiedCandidateExperimentOrigin,
        VerifiedModelInputRoutingOrigin,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
    from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
        CandidateExperimentReuseOccurrence,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.candidate_source_basis import CandidateSourceBasisPredecessor
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSourceReentryReceipt,
        GenerationCycleRecord,
        GenerationCycleRun,
    )
    from polisyos.runtime.quality.generation_source import N4CandidateScenarioSourceRecordV3
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericN5SemanticSuccessorRequest,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        JointSimulationRequest,
        JointSimulationResult,
    )
    from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight
    from polisyos.runtime.quality.n5_candidate_content import (
        GenericProgramGraphContentObservationV2,
    )
    from polisyos.runtime.quality.n5_execution_basis import N5ProductionImage
    from polisyos.runtime.quality.n5_execution_profile import N5NativeExecutionProfile
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerReentryBudgetWindow,
    )

_HASH = r"^sha256:[0-9a-f]{64}$"
BASIS_KIND = "runtime_quality.acquisition_evaluation_basis"
DECISION_KIND = "runtime_quality.acquisition_evaluation_decision"
PRODUCER = "polisyos.runtime.acquisition_evaluation"


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _candidate_ref_same(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    """Compare full artifact views, independent of a reference subclass."""
    if left is None or right is None:
        return left is right
    if not isinstance(left, ArtifactRef) or not isinstance(right, ArtifactRef):
        return False
    # A future reference subtype with additional fields is not silently
    # reduced to today's four-field identity. Its owner must reconcile it.
    if any(
        set(type(ref).model_fields) != set(ArtifactRef.model_fields)
        or set(vars(ref)) != set(ArtifactRef.model_fields)
        or ref.__pydantic_extra__
        for ref in (left, right)
    ):
        return False
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)


def _candidate_model_values_same(left: object, right: object) -> bool:
    """Compare candidate-owned typed values while normalizing only artifact refs.

    This comparison does not establish ownership of referenced bytes. Callers
    must independently reopen the selected owners and replay their inputs.
    """
    if left is None or right is None:
        return left is right
    if type(left) is not type(right) or not (
        isinstance(left, BaseModel) or (is_dataclass(left) and not isinstance(left, type))
    ):
        return False

    def same_values(a: object, b: object) -> bool:
        if isinstance(a, ArtifactRef) or isinstance(b, ArtifactRef):
            return (
                isinstance(a, ArtifactRef)
                and isinstance(b, ArtifactRef)
                and _candidate_ref_same(a, b)
            )
        if type(a) is not type(b):
            return False
        if isinstance(a, BaseModel):
            try:
                names = exact_n5_model_field_names(a)
                other_names = exact_n5_model_field_names(b)
            except (AttributeError, TypeError, ValueError):
                return False
            if names != other_names:
                return False
            return all(same_values(getattr(a, name), getattr(b, name)) for name in names)
        if is_dataclass(a) and not isinstance(a, type):
            return all(
                same_values(getattr(a, item.name), getattr(b, item.name)) for item in fields(a)
            )
        if isinstance(a, dict):
            left_rows = {exact_n5_content_bytes(key): value for key, value in a.items()}
            right_rows = {exact_n5_content_bytes(key): value for key, value in b.items()}
            return (
                len(left_rows) == len(a)
                and len(right_rows) == len(b)
                and left_rows.keys() == right_rows.keys()
                and all(same_values(value, right_rows[key]) for key, value in left_rows.items())
            )
        if isinstance(a, (tuple, list)):
            return len(a) == len(b) and all(same_values(x, y) for x, y in zip(a, b, strict=True))
        return exact_n5_content_bytes(a) == exact_n5_content_bytes(b)

    try:
        return same_values(left, right)
    except (AttributeError, TypeError, ValueError):
        return False


class AcquisitionSelectedEvaluation(_Record):
    """Exact evaluation occurrence selected by the verified route accumulator."""

    candidate_id: str = Field(min_length=1)
    candidate_content_hash: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    world_model_record_hash: str = Field(pattern=_HASH)
    evaluation_job_id: str = Field(min_length=1)
    evaluation_run_id: str = Field(min_length=1)
    generation_run_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=0)
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    n5_input_ref: ArtifactRef
    n5_execution_ref: ArtifactRef
    n5_result_ref: ArtifactRef
    basis_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _selected_refs(self) -> AcquisitionSelectedEvaluation:
        for name, kind in (
            ("n4_source_ref", "runtime.quality.n4_candidate_scenario_source"),
            ("context_job_ref", "runtime.quality.cycle_substrate_context_job"),
            ("n5_input_ref", "runtime.quality.candidate_simulation_n5_input"),
            ("n5_execution_ref", "runtime.quality.candidate_simulation_execution"),
            ("n5_result_ref", "polisyos.runtime.joint_simulation_result"),
            ("basis_ref", BASIS_KIND),
        ):
            ref = getattr(self, name)
            if ref is None and name == "basis_ref":
                continue
            if (
                not isinstance(ref, ArtifactRef)
                or ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("acquisition_evaluation_selected_view_not_established:" + name)
        return self


class AcquisitionBasisPreparationInputs(_Record):
    """Exact compact selectors/configuration used by the shared pure owners.

    Configuration is a declared candidate input, never source permission. Raw
    source bytes, activation, selected row and all derived values are reopened
    through their real owners on historical replay.
    """

    configured_profile: CandidateSimulationScenarioProfile
    original_model_declaration: CandidateSimulationSyntheticModelDeclarationV1
    base_data_snapshot_ref: ArtifactRef
    receipt_ref: ArtifactRef
    passport_ref: ArtifactRef
    boundary_candidate_ref: ArtifactRef
    source_ref: ArtifactRef
    observation_id: str
    slot_binding: ControlledAcquisitionSlotBinding
    transaction_time: str
    preparation_job_id: str
    n5_execution_configuration: PreparedJointSimulationConfiguration | None
    n5_configuration_reason_codes: tuple[str, ...] = ()


class AcquisitionEvaluationBasis(_Record):
    """Complete exact native values of the supported controlled NCM profile.

    ``effective_native_values_hex`` stores the actual complete typed quantity;
    its hash is an index. Deciding equality compares the bytes themselves. Every
    source occurrence and selected execution stays in the separate envelope.
    """

    ARTIFACT_KIND: ClassVar[str] = BASIS_KIND
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.AcquisitionEvaluationBasis"
    schema_version: Literal["AcquisitionEvaluationBasis@1.0"] = "AcquisitionEvaluationBasis@1.0"
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_profile: Literal["controlled_acquired_observation_ncm_v1"] = (
        "controlled_acquired_observation_ncm_v1"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=_HASH)
    candidate_id: str = Field(min_length=1)
    growth_receipt_ref: ArtifactRef
    admitted_source_ref: ArtifactRef
    evaluation: AcquisitionSelectedEvaluation | None = None
    preparation_inputs: AcquisitionBasisPreparationInputs
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    effective_native_values_hex: str
    effective_values_sha256: str = Field(pattern=_HASH)
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _content(self) -> AcquisitionEvaluationBasis:
        try:
            values = bytes.fromhex(self.effective_native_values_hex)
        except ValueError as exc:
            raise ValueError("acquisition_evaluation_basis_native_codec_invalid") from exc
        if "sha256:" + hashlib.sha256(values).hexdigest() != self.effective_values_sha256:
            raise ValueError("acquisition_evaluation_basis_values_hash_mismatch")
        if (self.predicate_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("acquisition_evaluation_basis_predicate_mismatch")
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("acquisition_evaluation_basis_content_mismatch")
        return self


class AcquisitionEvaluationBasisV2(AcquisitionEvaluationBasis):
    """Declared numerical acquired-observation basis with candidate-only scope."""

    schema_version: Literal["AcquisitionEvaluationBasis@2.0"] = "AcquisitionEvaluationBasis@2.0"
    comparison_profile: Literal["controlled_acquired_observation_numerical_v2"] = (
        "controlled_acquired_observation_numerical_v2"
    )
    closure_residuals: tuple[str, ...] = (
        "arbitrary_code_read_set_completeness_not_established",
        "same_process_transient_slot_cell_registry_mutations_not_established",
        "opaque_seam_values_not_established",
        "generated_code_provenance_not_established",
        "loaded_code_to_file_bytes_association_not_independently_reconciled",
        "cross_machine_bitwise_reproducibility_not_established",
        "interpreter_os_integrity_not_established",
        "protected_reuse_not_established",
    )
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False

    @model_validator(mode="after")
    def _fixed_residuals(self) -> AcquisitionEvaluationBasisV2:
        if self.closure_residuals != type(self).model_fields["closure_residuals"].default:
            raise ValueError("acquisition_evaluation_v2_closure_residuals_mismatch")
        return self


def _candidate_selected_ref(ref: ArtifactRef | None, kind: str) -> bool:
    return bool(
        isinstance(ref, ArtifactRef)
        and _candidate_ref_same(ref, ref)
        and ref.kind == kind
        and ref.media_type == "application/json"
        and ref.manifest_profile_sha256 is not None
    )


class CandidateAcquisitionEvaluationBasis(_Record):
    """Replayable candidate-source input basis, distinct from observed admission.

    The encoded values are a comparison quantity, not source authority. The
    owner must independently replay the complete selected source, predecessor
    world, execution configuration, and actual prior N5 before using them.
    """

    ARTIFACT_KIND: ClassVar[str] = BASIS_KIND
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.CandidateAcquisitionEvaluationBasis"
    schema_version: Literal["CandidateAcquisitionEvaluationBasis@1.0"] = (
        "CandidateAcquisitionEvaluationBasis@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_profile: Literal["candidate_source_complete_native_values_v1"] = (
        "candidate_source_complete_native_values_v1"
    )
    basis_role: Literal["prospective", "evaluated", "blocked"]
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    action_generation: int = Field(ge=1)
    route_id: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    candidate_id: str = Field(min_length=1)
    source_candidate_content_hash: str = Field(pattern=_HASH)
    candidate_action_ref: ArtifactRef
    reuse_occurrence_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    candidate_world_intent_ref: ArtifactRef
    candidate_source_ref: ArtifactRef
    preparation_inputs: CandidateSourceBasisInputs
    prepared_n5_configuration: PreparedJointSimulationConfiguration | None
    selected_data_snapshot_ref: ArtifactRef | None = None
    selected_world_model_ref: ArtifactRef | None = None
    evaluation: AcquisitionSelectedEvaluation | None = None
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False
    effective_native_values_hex: str
    effective_values_sha256: str = Field(pattern=_HASH)
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _bind_candidate_basis(self) -> CandidateAcquisitionEvaluationBasis:
        refs = (
            (self.candidate_action_ref, "runtime_quality.acquisition_candidate_action_receipt"),
            (self.candidate_world_intent_ref, "runtime_quality.acquisition_candidate_world_intent"),
            (self.candidate_source_ref, "runtime.quality.candidate_acquisition_source"),
        )
        if any(not _candidate_selected_ref(ref, kind) for ref, kind in refs):
            raise ValueError("candidate_evaluation_basis_selected_ref_invalid")
        if self.reuse_occurrence_ref is not None and not _candidate_selected_ref(
            self.reuse_occurrence_ref, "runtime_quality.candidate_experiment_reuse_occurrence"
        ):
            raise ValueError("candidate_evaluation_basis_reuse_occurrence_invalid")
        if not _candidate_ref_same(
            self.preparation_inputs.candidate_source_ref, self.candidate_source_ref
        ):
            raise ValueError("candidate_evaluation_basis_source_mismatch")
        actual_refs = (self.selected_data_snapshot_ref, self.selected_world_model_ref)
        if self.basis_role == "prospective":
            if any(ref is not None for ref in actual_refs) or self.evaluation is not None:
                raise ValueError("candidate_evaluation_prospective_has_outcome")
        elif (
            not _candidate_selected_ref(self.selected_data_snapshot_ref, "fabric.data_snapshot")
            or not _candidate_selected_ref(
                self.selected_world_model_ref, "runtime.quality.world_model_record"
            )
            or (self.basis_role == "evaluated") != (self.evaluation is not None)
        ):
            raise ValueError("candidate_evaluation_actual_outcome_incomplete")
        if self.evaluation is not None and (
            not _candidate_model_values_same(self.evaluation, self.evaluation)
            or self.evaluation.basis_ref is not None
            or self.evaluation.candidate_id != self.candidate_id
            or self.evaluation.design_problem_ref != self.design_problem_basis_ref
        ):
            raise ValueError("candidate_evaluation_basis_subject_mismatch")
        if self.basis_role == "blocked" and self.predicate_provenance != "not_established":
            raise ValueError("candidate_evaluation_blocked_basis_claim_invalid")
        if self.predicate_provenance == "recomputed" and self.prepared_n5_configuration is None:
            raise ValueError("candidate_evaluation_configuration_not_established")
        if (self.predicate_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("candidate_evaluation_basis_predicate_mismatch")
        if not all(isinstance(item, str) and item.strip() for item in self.limitations) or len(
            self.limitations
        ) != len(set(self.limitations)):
            raise ValueError("candidate_evaluation_basis_limitations_invalid")
        try:
            values = bytes.fromhex(self.effective_native_values_hex)
        except ValueError as exc:
            raise ValueError("candidate_evaluation_basis_native_codec_invalid") from exc
        if "sha256:" + hashlib.sha256(values).hexdigest() != self.effective_values_sha256:
            raise ValueError("candidate_evaluation_basis_values_hash_mismatch")
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("candidate_evaluation_basis_content_mismatch")
        return self


CANDIDATE_N5_CLOSURE_RESIDUALS_V2 = (
    "arbitrary_code_read_set_completeness_not_established",
    "same_process_transient_slot_cell_registry_mutations_not_established",
    "opaque_seam_values_not_established",
    "generated_code_provenance_not_established",
    "loaded_code_to_file_bytes_association_not_independently_reconciled",
    "cross_machine_bitwise_reproducibility_not_established",
    "interpreter_os_integrity_not_established",
    "protected_reuse_not_established",
)


class CandidateAcquisitionEvaluationBasisV2(CandidateAcquisitionEvaluationBasis):
    """Candidate equality of a declared numerical basis, never protected authority."""

    schema_version: Literal["CandidateAcquisitionEvaluationBasis@2.0"] = (
        "CandidateAcquisitionEvaluationBasis@2.0"
    )
    comparison_profile: Literal["candidate_source_declared_numerical_basis_v2"] = (
        "candidate_source_declared_numerical_basis_v2"
    )
    closure_residuals: tuple[str, ...] = CANDIDATE_N5_CLOSURE_RESIDUALS_V2

    @model_validator(mode="after")
    def _fixed_closure_residuals(self) -> CandidateAcquisitionEvaluationBasisV2:
        if self.closure_residuals != CANDIDATE_N5_CLOSURE_RESIDUALS_V2:
            raise ValueError("candidate_evaluation_v2_closure_residuals_mismatch")
        return self


class GenericModelInputSelectedEvaluation(_Record):
    """The original producer's selected Generic N5 input, execution and result."""

    input_ref: ArtifactRef
    execution_ref: ArtifactRef
    result_ref: ArtifactRef
    semantic_successor_ref: ArtifactRef
    action_job_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _selected_refs(self) -> GenericModelInputSelectedEvaluation:
        refs = (
            (self.input_ref, "runtime.quality.generic_cycle_simulation_n5_input"),
            (self.execution_ref, "runtime.quality.generic_cycle_simulation_n5_execution"),
            (self.result_ref, "polisyos.runtime.joint_simulation_result"),
            (self.semantic_successor_ref, "runtime.quality.model_input_successor_selection"),
        )
        if any(not _candidate_selected_ref(ref, kind) for ref, kind in refs):
            raise ValueError("generic_model_input_evaluation_selected_ref_invalid")
        return self


class GenericModelInputEvaluationBasisV1(_Record):
    """Owner-replayable candidate basis for one semantic ProgramGraph input.

    The numerical intent excludes the selected state snapshot's values. The
    comparator must reopen both snapshots through Foundry and compare every
    codec leaf's exact bytes. This record alone grants neither reuse nor an
    assertion that its supplied intent has been independently recomputed.
    """

    ARTIFACT_KIND: ClassVar[str] = BASIS_KIND
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.GenericModelInputEvaluationBasis"
    schema_version: Literal["GenericModelInputEvaluationBasis@1.0"] = (
        "GenericModelInputEvaluationBasis@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_profile: Literal[
        "generic_program_graph_declared_numerical_v1",
        "generic_program_graph_declared_numerical_v2",
    ] = "generic_program_graph_declared_numerical_v1"
    basis_role: Literal["prospective", "evaluated", "blocked"]
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    candidate_id: str = Field(min_length=1)
    input_ref: ArtifactRef
    semantic_successor_ref: ArtifactRef
    bound_state_snapshot_ref: ArtifactRef
    evaluation: GenericModelInputSelectedEvaluation | None = None
    prospective_basis_ref: ArtifactRef | None = None
    comparison_decision_ref: ArtifactRef | None = None
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)
    closure_residuals: tuple[str, ...] = CANDIDATE_N5_CLOSURE_RESIDUALS_V2
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False
    numerical_intent_hex: str = Field(max_length=2 * 1024 * 1024)
    numerical_intent_sha256: str = Field(pattern=_HASH)
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _bind_basis(self) -> GenericModelInputEvaluationBasisV1:
        refs = (
            (self.input_ref, "runtime.quality.generic_cycle_simulation_n5_input"),
            (self.semantic_successor_ref, "runtime.quality.model_input_successor_selection"),
            (self.bound_state_snapshot_ref, "foundry.state_snapshot"),
        )
        if self.source_job_id == self.action_job_id or any(
            not _candidate_selected_ref(ref, kind) for ref, kind in refs
        ):
            raise ValueError("generic_model_input_basis_selected_ref_invalid")
        if (self.basis_role == "evaluated") != (self.evaluation is not None):
            raise ValueError("generic_model_input_basis_evaluation_mismatch")
        if (self.prospective_basis_ref is None) != (self.comparison_decision_ref is None) or (
            self.prospective_basis_ref is not None
            and (
                self.basis_role != "evaluated"
                or not _candidate_selected_ref(self.prospective_basis_ref, BASIS_KIND)
                or not _candidate_selected_ref(self.comparison_decision_ref, DECISION_KIND)
            )
        ):
            raise ValueError("generic_model_input_basis_comparison_link_invalid")
        if self.evaluation is not None and (
            self.evaluation.action_job_id != self.action_job_id
            or not _candidate_ref_same(self.evaluation.input_ref, self.input_ref)
            or not _candidate_ref_same(
                self.evaluation.semantic_successor_ref, self.semantic_successor_ref
            )
        ):
            raise ValueError("generic_model_input_basis_evaluation_mismatch")
        if self.basis_role == "blocked" and self.predicate_provenance != "not_established":
            raise ValueError("generic_model_input_blocked_basis_claim_invalid")
        if (self.predicate_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("generic_model_input_basis_predicate_mismatch")
        if (
            not all(type(item) is str and item.strip() for item in self.limitations)
            or len(set(self.limitations)) != len(self.limitations)
            or self.closure_residuals != CANDIDATE_N5_CLOSURE_RESIDUALS_V2
        ):
            raise ValueError("generic_model_input_basis_limitations_invalid")
        try:
            encoded = bytes.fromhex(self.numerical_intent_hex)
        except ValueError as exc:
            raise ValueError("generic_model_input_basis_intent_invalid") from exc
        if (
            encoded.hex() != self.numerical_intent_hex
            or "sha256:" + hashlib.sha256(encoded).hexdigest() != self.numerical_intent_sha256
        ):
            raise ValueError("generic_model_input_basis_intent_mismatch")
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("generic_model_input_basis_content_mismatch")
        return self


class GenericModelInputEvaluationDecisionV1(_Record):
    """One current candidate-use decision about an original Generic N5 result."""

    ARTIFACT_KIND: ClassVar[str] = DECISION_KIND
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.GenericModelInputEvaluationDecision"
    schema_version: Literal["GenericModelInputEvaluationDecision@1.0"] = (
        "GenericModelInputEvaluationDecision@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_rule: Literal[
        "generic-program-graph-declared-numerical-basis.v1",
        "generic-program-graph-declared-numerical-basis.v2",
    ] = "generic-program-graph-declared-numerical-basis.v1"
    decision_kind: Literal["initial", "comparison"]
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    candidate_id: str = Field(min_length=1)
    action_phase_ref: ArtifactRef
    semantic_successor_ref: ArtifactRef
    routing_use_decision_ref: ArtifactRef
    authority_decision_ref: ArtifactRef
    activation_receipt_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    prior_basis_ref: ArtifactRef | None = None
    prior_evaluation: GenericModelInputSelectedEvaluation | None = None
    comparison_result: Literal["equivalent", "different", "not_established"] | None
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    expected_frontier_revision: int = Field(ge=0)
    expected_frontier_ref: str | None = Field(default=None, pattern=_HASH)
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False
    generated_at: str = Field(min_length=1)
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _bind_decision(self) -> GenericModelInputEvaluationDecisionV1:
        refs = (
            (self.action_phase_ref, "runtime.quality.model_input_use_action_phase"),
            (self.semantic_successor_ref, "runtime.quality.model_input_successor_selection"),
            (self.routing_use_decision_ref, "runtime.quality.model_input_routing_use_decision"),
            (self.authority_decision_ref, "runtime_quality.agent_action_authority_decision"),
            (self.current_basis_ref, BASIS_KIND),
        )
        activation = self.activation_receipt_ref
        if (
            self.source_job_id == self.action_job_id
            or any(not _candidate_selected_ref(ref, kind) for ref, kind in refs)
            or activation.kind != "epoch.activated_overlay_admission_receipt"
            or activation.media_type != "application/vnd.polisyos.epoch+json"
            or activation.manifest_profile_sha256 is None
            or (
                self.prior_basis_ref is not None
                and not _candidate_selected_ref(self.prior_basis_ref, BASIS_KIND)
            )
        ):
            raise ValueError("generic_model_input_decision_selected_ref_invalid")
        if (self.expected_frontier_revision == 0) != (self.expected_frontier_ref is None):
            raise ValueError("generic_model_input_decision_frontier_mismatch")
        if self.decision_kind == "initial":
            if (
                self.comparison_result is not None
                or self.prior_basis_ref is not None
                or self.prior_evaluation is not None
                or self.expected_frontier_revision != 0
                or self.expected_frontier_ref is not None
                or self.predicate_provenance != "recomputed"
                or self.reason_codes
            ):
                raise ValueError("generic_model_input_initial_decision_invalid")
        else:
            if (
                self.comparison_result is None
                or (self.comparison_result == "not_established")
                != (self.predicate_provenance == "not_established")
                or (self.predicate_provenance == "recomputed") == bool(self.reason_codes)
            ):
                raise ValueError("generic_model_input_decision_predicate_mismatch")
            if self.comparison_result != "not_established" and (
                self.prior_basis_ref is None
                or self.prior_evaluation is None
                or self.expected_frontier_revision < 1
            ):
                raise ValueError("generic_model_input_decision_prior_missing")
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("generic_model_input_decision_content_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class PreparedGenericModelInputNumericalBasis:
    """Ephemeral owner-replayed intent and its actual current provider profile."""

    successor: GenericN5SemanticSuccessorRequest
    bound_state_snapshot_ref: ArtifactRef
    numerical_intent: bytes
    prepared_calls: tuple[tuple[int, str, int, bytes], ...]
    execution_profile: N5NativeExecutionProfile
    source_image: N5ProductionImage


@dataclass(frozen=True, slots=True)
class _GenericModelInputNumericalQuantity:
    bound_state_snapshot_ref: ArtifactRef
    numerical_intent: bytes
    prepared_calls: tuple[tuple[int, str, int, bytes], ...]
    execution_profile: N5NativeExecutionProfile
    source_image: N5ProductionImage


@dataclass(frozen=True, slots=True)
class _GenericModelInputNumericalIntake:
    """Immutable owner inputs before selecting current or recorded call content."""

    bound_state_snapshot_ref: ArtifactRef
    program_graph_ref: ArtifactRef
    exec_plan_ref: ArtifactRef
    state: object
    registry: RegistryBundleContent
    numerical_values: dict[str, object]


GENERIC_NUMERICAL_INTENT_PROFILE = "generic_program_graph_declared_numerical_v2"
_GENERIC_FIELD_ROLES = frozenset(
    {"numerical", "operational", "output_label", "resolved", "not_consumed"}
)
_GENERIC_REQUEST_FIELD_ROLES = (
    ("world_model_record_ref", "output_label"),
    ("world_model_record", "numerical"),
    ("intervention_atoms", "numerical"),
    ("selected_outcomes", "numerical"),
    ("horizon", "numerical"),
    ("engine_plan", "resolved"),
    ("baseline_state", "numerical"),
    ("evidence_state", "numerical"),
    ("comparator_refs", "output_label"),
    ("comparator_profile", "numerical"),
    ("coupling_graph", "numerical"),
    ("budget_ref", "operational"),
    ("seed", "numerical"),
    ("replications", "numerical"),
    ("world_credal_state_before", "numerical"),
    ("candidate_intent", "numerical"),
    ("member_basis", "numerical"),
    ("source_candidate_relationship", "numerical"),
    ("composition_status", "numerical"),
    ("composition_limitation_code", "numerical"),
    ("child_to_parent_refinement_status", "numerical"),
    ("child_to_parent_refinement_limitation_code", "numerical"),
)
_GENERIC_PLAN_FIELD_ROLES = (
    ("engine_kind", "numerical"),
    ("objective_ref", "numerical"),
    ("declared_equilibrium_semantics", "numerical"),
    ("eligibility_conditions", "numerical"),
    ("ncm_spec", "numerical"),
    ("variable_map", "numerical"),
    ("outcome_aggregations", "numerical"),
    ("coupled_state", "numerical"),
    ("coupled_params", "numerical"),
    ("system_dynamics_state", "numerical"),
    ("system_dynamics_params", "numerical"),
    ("system_dynamics_state_overrides_by_atom", "numerical"),
    ("program_compilation_ref", "resolved"),
    ("program_semantic_input_bindings_ref", "resolved"),
    ("program_graph_ref", "resolved"),
    ("exec_plan_ref", "resolved"),
    ("program_store", "resolved"),
    ("program_base_state", "resolved"),
    ("program_base_ref", "resolved"),
    ("mechanism_registry", "resolved"),
    ("slot_registry", "resolved"),
    ("merge_registry", "resolved"),
    ("selector_field_registry", "resolved"),
    ("constraint_registry", "resolved"),
    ("program_graph_acyclic", "numerical"),
    ("program_parameter_overrides_by_atom", "numerical"),
    ("method_fqn", "numerical"),
)
_GENERIC_GRAPH_FIELD_ROLES = (
    ("schema_version", "numerical"),
    ("ir_ref", "resolved"),
    ("lowered_ir_ref", "resolved"),
    ("nodes", "resolved"),
    ("edges", "resolved"),
    ("entrypoints", "not_consumed"),
    ("notes", "output_label"),
)
_GENERIC_NODE_FIELD_ROLES = (
    ("node_id", "numerical"),
    ("node_kind", "numerical"),
    ("mechanism_type", "numerical"),
    ("method_fqn", "numerical"),
    ("method_version", "numerical"),
    ("method_params", "numerical"),
    ("input_ports", "numerical"),
    ("params_ref", "resolved"),
    ("op", "resolved"),
    ("inputs", "numerical"),
    ("outputs", "numerical"),
)
_GENERIC_OP_FIELD_ROLES = (
    ("op_kind", "numerical"),
    ("params", "numerical"),
    ("notes", "output_label"),
)
_GENERIC_EDGE_FIELD_ROLES = (
    ("src", "numerical"),
    ("dst", "numerical"),
    ("relation", "output_label"),
)
_GENERIC_EXEC_PLAN_FIELD_ROLES = (
    ("program_ref", "resolved"),
    ("order", "numerical"),
    ("environment_ref", "resolved"),
    ("environment_fingerprint", "resolved"),
    ("determinism_tier", "numerical"),
    ("random_seed", "numerical"),
    ("nan_guard_enabled", "numerical"),
    ("policy_fidelity_level", "numerical"),
    ("constraint_mode", "numerical"),
    ("mode", "numerical"),
    ("jit", "numerical"),
    ("max_steps", "numerical"),
    ("notes", "resolved"),
)
_GENERIC_LOWERED_IR_FIELD_ROLES = (
    ("schema_version", "numerical"),
    ("ir_ref", "resolved"),
    ("mechanisms", "not_consumed"),
    ("constraints", "numerical"),
    ("composite_constraints", "not_consumed"),
    ("parameter_specs", "not_consumed"),
    ("time_semantics", "not_consumed"),
    ("environment_config", "not_consumed"),
    ("policy_fidelity_level", "not_consumed"),
    ("constraint_mode", "numerical"),
    ("notes", "not_consumed"),
)


def _generic_numerical_fields(
    value: BaseModel, roles: tuple[tuple[str, str], ...], *, scope: str
) -> dict[str, object]:
    """Project an exact owner type after its entire field-role census succeeds."""
    census = _require_n5_field_role_census(
        exact_n5_model_field_names(value),
        roles,
        allowed_roles=_GENERIC_FIELD_ROLES,
        error_prefix=f"generic_model_input_{scope}_field_role",
    )
    return {name: getattr(value, name) for name in sorted(census) if census[name] == "numerical"}


def _generic_program_graph_numerical_values(
    graph: object,
    exec_plan: object,
    lowered_ir: object,
    parameter_payloads: dict[str, object],
) -> dict[str, object]:
    """Join complete owner-resolved plan content without source-view labels."""
    from polisyos.core.contracts import (
        ExecPlan,
        LoweredIR,
        ProgramEdge,
        ProgramGraph,
        ProgramNode,
        ProgramOp,
    )

    if type(graph) is not ProgramGraph or type(exec_plan) is not ExecPlan:
        raise ValueError("generic_model_input_program_types_not_established")
    if type(lowered_ir) is not LoweredIR or type(parameter_payloads) is not dict:
        raise ValueError("generic_model_input_lowered_ir_not_established")
    if type(graph.nodes) is not list or any(type(node) is not ProgramNode for node in graph.nodes):
        raise ValueError("generic_model_input_node_type_not_established")
    if type(graph.edges) is not list or any(type(edge) is not ProgramEdge for edge in graph.edges):
        raise ValueError("generic_model_input_edge_type_not_established")
    if type(exec_plan.notes) is not list or any(type(note) is not str for note in exec_plan.notes):
        raise ValueError("generic_model_input_plan_notes_not_established")
    if len({node.node_id for node in graph.nodes}) != len(graph.nodes):
        raise ValueError("generic_model_input_node_census_not_established")
    expected_parameters = {node.node_id for node in graph.nodes if node.params_ref is not None}
    if set(parameter_payloads) != expected_parameters or any(
        type(payload) is not dict for payload in parameter_payloads.values()
    ):
        raise ValueError("generic_model_input_parameter_census_not_established")
    graph_values = _generic_numerical_fields(graph, _GENERIC_GRAPH_FIELD_ROLES, scope="graph")
    graph_values["edges"] = [
        _generic_numerical_fields(edge, _GENERIC_EDGE_FIELD_ROLES, scope="edge")
        for edge in graph.edges
    ]
    nodes = []
    for node in graph.nodes:
        node_values = _generic_numerical_fields(node, _GENERIC_NODE_FIELD_ROLES, scope="node")
        if graph.schema_version == "0.2":
            # The optional 0.3 field did not exist in recorded 0.2 numerical
            # intent; preserve that exact wire rather than adding null bytes.
            if node.input_ports is not None:
                raise ValueError("generic_model_input_legacy_input_mapping_invalid")
            node_values.pop("input_ports")
        if node.op is not None and type(node.op) is not ProgramOp:
            raise ValueError("generic_model_input_op_type_not_established")
        node_values["op"] = (
            None
            if node.op is None
            else _generic_numerical_fields(node.op, _GENERIC_OP_FIELD_ROLES, scope="op")
        )
        node_values["resolved_parameters"] = parameter_payloads.get(node.node_id)
        nodes.append(node_values)
    graph_values["nodes"] = nodes
    exec_values = _generic_numerical_fields(
        exec_plan, _GENERIC_EXEC_PLAN_FIELD_ROLES, scope="exec_plan"
    )
    exec_values["randomization_notes"] = tuple(
        note for note in exec_plan.notes if note.startswith("randomization:")
    )
    return {
        "graph": graph_values,
        "exec_plan": exec_values,
        "lowered_ir": _generic_numerical_fields(
            lowered_ir, _GENERIC_LOWERED_IR_FIELD_ROLES, scope="lowered_ir"
        ),
    }


def prepare_generic_model_input_numerical_basis(
    *,
    store: CoreJSONArtifactStore,
    input_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
    expected_blocked_execution_ref: ArtifactRef,
    controller: JointSimulationHorizonController,
) -> PreparedGenericModelInputNumericalBasis:
    """Replay a current semantic selection and prepare its declared N5 inputs.

    The native successor owner, Foundry input owner and ordinary mechanism
    factory supply the values. This performs no N5 execution or protected-use
    admission. The selected state bytes stay in Foundry CAS and are reopened
    during comparison, while the bounded intent retains the exact remaining
    supported values. Unsupported fields and provider identities refuse.

    Args:
        store: Existing selected-profile artifact owner.
        input_ref: Original blocked Generic N5 input.
        semantic_successor_ref: Current selected candidate input occurrence.
        expected_blocked_execution_ref: The independently selected blocked origin.
        controller: The actual current N5 controller with its prepared policy.

    Returns:
        An ephemeral preparation carrying no authority or frontier selection.

    Raises:
        TypeError: If the concrete controller is not the native owner.
        ValueError: If source replay, exact content or the bounded profile refuses.
    """
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )

    successor = GenericCycleSimulationAdmissionOwner(
        profiles=(), store=store
    ).prepare_semantic_successor_request(
        semantic_successor_ref=semantic_successor_ref,
        expected_blocked_execution_ref=expected_blocked_execution_ref,
        expected_input_ref=input_ref,
    )
    quantity = _prepare_generic_model_input_numerical_quantity(
        store=store,
        request=successor.request,
        preflight=successor.preflight,
        controller=controller,
    )
    return PreparedGenericModelInputNumericalBasis(
        successor=successor,
        bound_state_snapshot_ref=quantity.bound_state_snapshot_ref,
        numerical_intent=quantity.numerical_intent,
        prepared_calls=quantity.prepared_calls,
        execution_profile=quantity.execution_profile,
        source_image=quantity.source_image,
    )


_SELECTED_METHOD_BINDINGS_FIELD_ROLES = (
    ("schema_version", "resolved"),
    ("data_snapshot_ref", "resolved"),
    ("registry_bundle_ref", "resolved"),
    ("rules", "resolved"),
    ("bound_state_snapshot_ref", "resolved"),
    ("quality_report_ref", "resolved"),
    ("notes", "resolved"),
    ("registered_sql_admission_ref", "resolved"),
    ("resolved_binding_manifest_ref", "resolved"),
    ("selected_method_inputs", "resolved"),
)
_SELECTED_METHOD_INPUT_FIELD_ROLES = (
    ("model_input_obligation_ref", "resolved"),
    ("binding_id", "resolved"),
    ("port_id", "resolved"),
    ("slot_id", "numerical"),
    ("canonical_value", "resolved"),
    ("dtype", "numerical"),
    ("shape", "numerical"),
    ("npy_value_ref", "resolved"),
    ("value_sha256", "resolved"),
)


def _selected_method_input_numerical_values(resolution: object) -> tuple[object, ...]:
    """Encode already reconciled physical method values, without lineage labels.

    The Foundry owner separately resolves every source, selection and NPY edge.
    This projection is a numerical value only; it supplies no admission proof.
    Consuming ABI-local mappings, defaults and callables belong to the executor's
    separate actual-call preparation, never inferred from binding identifiers.
    """
    import numpy as np

    from polisyos.core.contracts.foundry import FoundrySelectedMethodInput
    from polisyos.foundry.data_plane.bindings import SelectedMethodInputResolution
    from polisyos.foundry.data_plane.selected_tensors import selected_tensor_value_sha256

    if type(resolution) is not SelectedMethodInputResolution:
        raise TypeError("generic_method_input_resolution_not_established")
    if resolution.bindings.schema_version != "1.4":
        raise ValueError("generic_method_input_profile_not_established")
    _require_n5_field_role_census(
        exact_n5_model_field_names(resolution.bindings),
        _SELECTED_METHOD_BINDINGS_FIELD_ROLES,
        allowed_roles=frozenset({"resolved"}),
        error_prefix="generic_method_bindings_field_role",
    )
    records = resolution.records
    if not records or len({record.slot_id for record in records}) != len(records):
        raise ValueError("generic_method_input_census_not_established")
    if set(resolution.values) != {record.slot_id for record in records}:
        raise ValueError("generic_method_input_census_not_established")
    values = []
    for record in sorted(records, key=lambda item: item.slot_id):
        if not isinstance(record, FoundrySelectedMethodInput):
            raise ValueError("generic_method_input_record_not_established")
        _require_n5_field_role_census(
            exact_n5_model_field_names(record),
            _SELECTED_METHOD_INPUT_FIELD_ROLES,
            allowed_roles=frozenset({"numerical", "resolved"}),
            error_prefix="generic_method_input_field_role",
        )
        value = resolution.values[record.slot_id]
        if (
            type(value) is not np.ndarray
            or value.dtype.kind != "f"
            or value.dtype.metadata is not None
            or value.dtype.name != record.dtype
            or tuple(value.shape) != record.shape
            or not np.isfinite(value).all()
            or value.nbytes > 1024 * 1024
        ):
            raise ValueError("generic_method_input_physical_value_not_established")
        raw = value.tobytes(order="C")
        if (
            selected_tensor_value_sha256(value.dtype, tuple(value.shape), raw)
            != record.value_sha256
        ):
            raise ValueError("generic_method_input_physical_value_mismatch")
        values.append((record.slot_id, value.dtype.str, tuple(value.shape), raw))
    return tuple(values)


def _prepare_generic_model_input_numerical_intake(
    *,
    store: CoreJSONArtifactStore,
    request: JointSimulationRequest,
    preflight: ProgramGraphInputPreflight,
    controller: JointSimulationHorizonController,
) -> _GenericModelInputNumericalIntake:
    """Reopen the complete immutable request, graph, state and registry inputs."""
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts import ExecPlan, LoweredIR, ProgramGraph
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.data_plane import load_input_bindings
    from polisyos.foundry.execute import (
        load_model,
        load_payload,
        load_state_snapshot,
        state_snapshot_value_projection,
    )
    from polisyos.foundry.methods import MethodRegistry
    from polisyos.runtime.quality.joint_simulation_horizon import (
        EnginePlan,
        JointSimulationHorizonController,
        JointSimulationRequest,
        _require_program_graph_input_preflight,
    )

    if type(controller) is not JointSimulationHorizonController:
        raise TypeError("generic_model_input_controller_not_established")
    if controller._registry is not MethodRegistry.get_instance():
        raise ValueError("generic_model_input_controller_registry_not_established")
    if type(request) is not JointSimulationRequest or len(request.engine_plan) != 1:
        raise ValueError("generic_model_input_request_census_not_established")
    controller._validate_world_model_record(request)
    (plan,) = request.engine_plan
    if type(plan) is not EnginePlan:
        raise ValueError("generic_model_input_plan_census_not_established")
    request_values = _generic_numerical_fields(
        request, _GENERIC_REQUEST_FIELD_ROLES, scope="request"
    )
    plan_values = _generic_numerical_fields(plan, _GENERIC_PLAN_FIELD_ROLES, scope="plan")
    selected = controller._select_engine(request)
    if (
        selected.plan is not plan
        or selected.decision.decision != "selected"
        or selected.decision.engine_kind != "program_graph"
        or plan.program_store is not store
    ):
        raise ValueError("generic_model_input_engine_not_established")
    semantic = _require_program_graph_input_preflight(
        request, plan, selected.decision, lambda *_args: preflight
    )
    if semantic is None or plan.program_semantic_input_bindings_ref is None:
        raise ValueError("generic_model_input_semantic_intake_not_established")
    bindings = load_input_bindings(store, plan.program_semantic_input_bindings_ref)
    state_ref = bindings.bound_state_snapshot_ref
    if not _candidate_selected_ref(state_ref, "foundry.state_snapshot"):
        raise ValueError("generic_model_input_state_not_selected")
    state = load_state_snapshot(store, snapshot_ref=state_ref)
    # Establish the complete state-codec denominator now; the bytes are compared
    # by reopening the selected snapshots, not duplicated in the small intent.
    state_snapshot_value_projection(state)
    registry_ref = preflight.invocation.registry_bundle_ref
    registry = load_registry_bundle_content(store, registry_ref)
    for name in (
        "mechanism_registry",
        "slot_registry",
        "merge_registry",
        "selector_field_registry",
        "constraint_registry",
    ):
        if exact_n5_content_bytes(getattr(plan, name)) != exact_n5_content_bytes(
            getattr(registry, name)
        ):
            raise ValueError("generic_model_input_registry_binding_mismatch")
    if (
        plan.program_graph_ref is None
        or plan.exec_plan_ref is None
        or plan.program_base_ref is None
    ):
        raise ValueError("generic_model_input_program_source_not_established")
    graph = validate_core_model_json_artifact(ProgramGraph, store, plan.program_graph_ref)
    exec_plan = validate_core_model_json_artifact(ExecPlan, store, plan.exec_plan_ref)
    if not _candidate_ref_same(exec_plan.program_ref, plan.program_graph_ref):
        raise ValueError("generic_model_input_program_source_mismatch")
    if graph.lowered_ir_ref is None:
        raise ValueError("generic_model_input_lowered_ir_not_established")
    lowered_ir = load_model(store, graph.lowered_ir_ref, LoweredIR)
    parameter_payloads = {}
    for node in graph.nodes:
        if node.params_ref is not None:
            manifest = store.get_manifest(node.params_ref)
            selected_ref = artifact_ref_for_manifest(manifest)
            if not store.verify(selected_ref).ok:
                raise ValueError("generic_model_input_parameter_source_not_established")
            parameter_payloads[node.node_id] = load_payload(store, node.params_ref)
    graph_values = _generic_program_graph_numerical_values(
        graph, exec_plan, lowered_ir, parameter_payloads
    )
    return _GenericModelInputNumericalIntake(
        bound_state_snapshot_ref=state_ref,
        program_graph_ref=plan.program_graph_ref,
        exec_plan_ref=plan.exec_plan_ref,
        state=state,
        registry=registry,
        numerical_values={
            "profile": GENERIC_NUMERICAL_INTENT_PROFILE,
            "request": request_values,
            "plan": plan_values,
            "decision": selected.decision,
            **graph_values,
            "registry": {
                name: getattr(registry, name)
                for name in (
                    "mechanism_registry",
                    "slot_registry",
                    "merge_registry",
                    "selector_field_registry",
                    "constraint_registry",
                )
            },
        },
    )


def _generic_model_input_numerical_intent(
    intake: _GenericModelInputNumericalIntake,
    *,
    prepared_calls: tuple[tuple[int, str, int, bytes], ...],
    configuration: PreparedJointSimulationConfiguration,
) -> bytes:
    """Encode the same immutable numerical facets for live and recorded replay."""
    intent = exact_n5_content_bytes(
        {
            **intake.numerical_values,
            "prepared_calls": prepared_calls,
            "configuration": configuration,
        }
    )
    if len(intent) > 1024 * 1024:
        raise ValueError("generic_model_input_intent_limit_exceeded")
    return intent


def _prepare_generic_model_input_numerical_quantity(
    *,
    store: CoreJSONArtifactStore,
    request: JointSimulationRequest,
    preflight: ProgramGraphInputPreflight,
    controller: JointSimulationHorizonController,
) -> _GenericModelInputNumericalQuantity:
    """Prepare immutable inputs and the actual current callable/provider bytes."""
    from polisyos.foundry.execute import (
        execute_semantic_horizon_step,
        prepare_program_graph_mechanism_calls,
    )
    from polisyos.foundry.methods import MethodRegistry
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        prepare_joint_simulation_configuration,
        read_joint_simulation_configuration,
        require_prepared_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        _native_profile,
        _prepared_image_descriptor,
        _product_root,
    )
    from polisyos.runtime.quality.n5_execution_basis import (
        capture_n5_production_image,
        snapshot_foundry_mechanism_call,
    )

    if type(controller) is not JointSimulationHorizonController:
        raise TypeError("generic_model_input_controller_not_established")
    if controller._registry is not MethodRegistry.get_instance():
        raise ValueError("generic_model_input_controller_registry_not_established")
    configuration = read_joint_simulation_configuration(controller)
    require_prepared_joint_simulation_configuration(
        controller, prepare_joint_simulation_configuration()
    )
    intake = _prepare_generic_model_input_numerical_intake(
        store=store, request=request, preflight=preflight, controller=controller
    )
    prepared_calls = tuple(
        (index, node_id, step, snapshot_foundry_mechanism_call(call))
        for index, node_id, step, call in prepare_program_graph_mechanism_calls(
            store,
            program_ref=intake.program_graph_ref,
            exec_plan_ref=intake.exec_plan_ref,
            base_state=intake.state,
            mechanism_registry=intake.registry.mechanism_registry,
            steps=request.horizon.steps(),
        )
    )
    intent = _generic_model_input_numerical_intent(
        intake, prepared_calls=prepared_calls, configuration=configuration
    )
    profile = _native_profile(configuration, numerical_callable=execute_semantic_horizon_step)
    image = capture_n5_production_image(
        root=_product_root(), admitted_profile=_prepared_image_descriptor(configuration)
    )
    if profile.profile_identity_predicate != "recomputed" or image.provenance != "recomputed":
        raise ValueError("generic_model_input_provider_not_established")
    return _GenericModelInputNumericalQuantity(
        bound_state_snapshot_ref=intake.bound_state_snapshot_ref,
        numerical_intent=intent,
        prepared_calls=prepared_calls,
        execution_profile=profile,
        source_image=image,
    )


def _verify_generic_model_input_origin(
    *,
    origin: VerifiedModelInputRoutingOrigin,
    input_ref: ArtifactRef,
    successor: GenericN5SemanticSuccessorRequest,
) -> None:
    """Join an independently replayed route origin to this selected request."""
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedModelInputRoutingOrigin

    if type(origin) is not VerifiedModelInputRoutingOrigin:
        raise TypeError("generic_model_input_origin_not_established")
    source, selection = successor.input_record, successor.selection
    active_problem = (
        origin.source_cycle.design_problem_basis_ref or origin.source_cycle.design_problem_ref
    )
    if (
        (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id)
        != (source.tenant_id, source.cell_id, source.run_id, source.job_id)
        or origin.source_cycle.selected_candidate_ref != source.candidate_id
        or active_problem != source.design_problem_ref
        or origin.n5_expectation.design_problem_ref != source.design_problem_ref
        or not _candidate_ref_same(origin.n5_expectation.input_ref, input_ref)
        or not _candidate_ref_same(origin.n5_execution_ref, selection.blocked_execution_ref)
        or not _candidate_ref_same(origin.routing_report_ref, selection.routing_report_ref)
        or not _candidate_ref_same(origin.compiled_ref, selection.compiled_ref)
    ):
        raise ValueError("generic_model_input_origin_scope_mismatch")


def _read_generic_model_input_original_evaluation(
    *,
    store: CoreJSONArtifactStore,
    input_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
    evaluation: GenericModelInputSelectedEvaluation,
    successor: GenericN5SemanticSuccessorRequest,
) -> GenericProgramGraphContentObservationV2:
    """Verify the immutable V5, original observation and selected Foundry chains."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5ExecutionV5,
        GenericN5ExecutionJoinExpectation,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        read_generic_program_graph_n5_content_observation,
    )

    source = successor.input_record
    if (
        type(evaluation) is not GenericModelInputSelectedEvaluation
        or not _candidate_ref_same(evaluation.input_ref, input_ref)
        or not _candidate_ref_same(evaluation.semantic_successor_ref, semantic_successor_ref)
        or evaluation.action_job_id != successor.selection.action_job_id
    ):
        raise ValueError("generic_model_input_original_evaluation_mismatch")
    expected = GenericN5ExecutionJoinExpectation(
        input_ref=input_ref,
        result_ref=evaluation.result_ref,
        status="joint_simulated",
        model_input_obligation_set_ref=None,
        semantic_successor_ref=semantic_successor_ref,
        n4_source_ref=source.n4_source_ref,
        context_job_ref=source.context_job_ref,
        profile_ref=source.profile_ref,
        child_family_ref=source.n4_child_profile_family_ref,
        child_set_ref=source.n4_child_profile_set_ref,
        profile_selection_ref=source.profile.profile_selection_ref,
        profile=source.profile,
        child_selection=source.child_selection,
        design_problem_ref=source.design_problem_ref,
        outcome_variable=source.outcome_variable,
        cycle_index=source.cycle_index,
        candidate_id=source.candidate_id,
        candidate_atom_hash=source.candidate_atom_hash,
        world_model_record_content_hash=source.profile.context_inputs.world_model_record.content_hash,
        job_id=source.job_id,
        run_id=source.run_id,
        source_run_id=source.source_run_id,
        tenant_id=source.tenant_id,
        cell_id=source.cell_id,
    )
    outcome, resolved = GenericCycleSimulationAdmissionOwner(
        profiles=(), store=store
    ).resolve_n5_execution_join_with_result(evaluation.execution_ref, expected=expected)
    if (
        outcome.status != "resolved"
        or type(outcome.execution) is not GenericCycleSimulationN5ExecutionV5
        or outcome.execution.action_job_id != evaluation.action_job_id
        or resolved is None
    ):
        raise ValueError("generic_model_input_original_execution_not_established")
    observation = read_generic_program_graph_n5_content_observation(
        resolved.result,
        input_ref=input_ref,
        semantic_successor_ref=semantic_successor_ref,
        expected_request=resolved.request,
        store=store,
    )
    return observation


def _verify_generic_model_input_original_evaluation(
    *,
    store: CoreJSONArtifactStore,
    input_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
    evaluation: GenericModelInputSelectedEvaluation,
    prepared: PreparedGenericModelInputNumericalBasis,
) -> GenericProgramGraphContentObservationV2:
    """Require original integrity and exact current call/provider bytes for reuse."""
    from polisyos.runtime.quality.n5_execution_profile import (
        reconcile_recorded_n5_profile_current_bytes,
    )

    observation = _read_generic_model_input_original_evaluation(
        store=store,
        input_ref=input_ref,
        semantic_successor_ref=semantic_successor_ref,
        evaluation=evaluation,
        successor=prepared.successor,
    )
    if observation.numerical_intent_sha256 != (
        "sha256:" + hashlib.sha256(prepared.numerical_intent).hexdigest()
    ):
        raise ValueError("generic_model_input_original_intent_mismatch")
    for step in observation.steps:
        expected_calls = tuple(
            (index, node_id, content.hex())
            for index, node_id, prepared_step, content in prepared.prepared_calls
            if prepared_step == step.step
        )
        actual_calls = tuple(
            (call.plan_index, call.node_id, call.callable_receiver_hex) for call in step.calls
        )
        if actual_calls != expected_calls:
            raise ValueError("generic_model_input_original_call_binding_mismatch")
    comparison = reconcile_recorded_n5_profile_current_bytes(
        observation.execution_profile,
        prepared.execution_profile,
        recorded_source_image=observation.source_image,
        current_source_image=prepared.source_image,
    )
    if comparison.status != "recomputed":
        raise ValueError("generic_model_input_original_provider_not_established")
    return observation


def issue_generic_model_input_evaluation_basis(
    *,
    store: CoreJSONArtifactStore,
    origin: VerifiedModelInputRoutingOrigin,
    input_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
    controller: JointSimulationHorizonController,
    basis_role: Literal["prospective", "evaluated"],
    evaluation: GenericModelInputSelectedEvaluation | None = None,
    event_log: RuntimeDiagnosticEventLog | None = None,
    prospective_basis_ref: ArtifactRef | None = None,
    comparison_decision_ref: ArtifactRef | None = None,
    prior_origin: VerifiedModelInputRoutingOrigin | None = None,
) -> GenericModelInputEvaluationBasisV1:
    """Issue a candidate basis after actual successor and numerical preparation.

    An evaluated basis additionally reopens the original selected V5 and its
    complete producer observation. The caller separately establishes the live
    action, authority, currentness and frontier before using this record.
    """
    prepared = prepare_generic_model_input_numerical_basis(
        store=store,
        input_ref=input_ref,
        semantic_successor_ref=semantic_successor_ref,
        expected_blocked_execution_ref=origin.n5_execution_ref,
        controller=controller,
    )
    _verify_generic_model_input_origin(
        origin=origin, input_ref=input_ref, successor=prepared.successor
    )
    if (basis_role == "evaluated") != (evaluation is not None):
        raise ValueError("generic_model_input_evaluation_role_mismatch")
    if evaluation is not None:
        _verify_generic_model_input_original_evaluation(
            store=store,
            input_ref=input_ref,
            semantic_successor_ref=semantic_successor_ref,
            evaluation=evaluation,
            prepared=prepared,
        )
    if (prospective_basis_ref is None) != (comparison_decision_ref is None):
        raise ValueError("generic_model_input_basis_comparison_link_invalid")
    if prospective_basis_ref is None and prior_origin is not None:
        raise ValueError("generic_model_input_basis_comparison_link_invalid")
    replacement_decision: GenericModelInputEvaluationDecisionV1 | None = None
    if prospective_basis_ref is not None:
        if basis_role != "evaluated" or event_log is None or comparison_decision_ref is None:
            raise ValueError("generic_model_input_basis_comparison_link_invalid")
        replacement_decision = _verify_generic_model_input_replacement(
            store=store,
            event_log=event_log,
            origin=origin,
            prior_origin=prior_origin,
            controller=controller,
            input_ref=input_ref,
            semantic_successor_ref=semantic_successor_ref,
            prospective_basis_ref=prospective_basis_ref,
            comparison_decision_ref=comparison_decision_ref,
            prepared=prepared,
        )
    source, selection = prepared.successor.input_record, prepared.successor.selection
    payload = {
        "schema_version": "GenericModelInputEvaluationBasis@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": GENERIC_NUMERICAL_INTENT_PROFILE,
        "basis_role": basis_role,
        "tenant_id": source.tenant_id,
        "cell_id": source.cell_id,
        "run_id": source.run_id,
        "source_job_id": source.job_id,
        "action_job_id": selection.action_job_id,
        "route_id": selection.route_id,
        "design_problem_ref": origin.source_cycle.design_problem_ref,
        "design_problem_basis_ref": source.design_problem_ref,
        "candidate_id": origin.source_cycle.selected_candidate_ref,
        "input_ref": input_ref.model_dump(mode="json"),
        "semantic_successor_ref": semantic_successor_ref.model_dump(mode="json"),
        "bound_state_snapshot_ref": prepared.bound_state_snapshot_ref.model_dump(mode="json"),
        "evaluation": evaluation.model_dump(mode="json") if evaluation is not None else None,
        "prospective_basis_ref": prospective_basis_ref.model_dump(mode="json")
        if prospective_basis_ref is not None
        else None,
        "comparison_decision_ref": comparison_decision_ref.model_dump(mode="json")
        if comparison_decision_ref is not None
        else None,
        "predicate_provenance": "recomputed",
        "reason_codes": [],
        "limitations": [
            "candidate_simulation_input_only",
            "producer_observed_intermediate_state_not_independently_recomputed",
            *(
                ["prior_numerical_comparison_not_established"]
                if replacement_decision is not None
                and replacement_decision.comparison_result == "not_established"
                else []
            ),
        ],
        "closure_residuals": list(CANDIDATE_N5_CLOSURE_RESIDUALS_V2),
        "observed_admission": False,
        "publication_authority": False,
        "numerical_intent_hex": prepared.numerical_intent.hex(),
        "numerical_intent_sha256": "sha256:"
        + hashlib.sha256(prepared.numerical_intent).hexdigest(),
    }
    return GenericModelInputEvaluationBasisV1.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )


def compare_generic_model_input_evaluation_bases(
    *,
    store: CoreJSONArtifactStore,
    prior: GenericModelInputEvaluationBasisV1,
    current: GenericModelInputEvaluationBasisV1,
    prior_origin: VerifiedModelInputRoutingOrigin,
    current_origin: VerifiedModelInputRoutingOrigin,
    controller: JointSimulationHorizonController,
) -> tuple[Literal["equivalent", "different", "not_established"], tuple[str, ...]]:
    """Reopen both source owners and compare full supported state and intent.

    This is candidate numerical equivalence only. The caller must read both
    basis records by their selected profiles and independently revalidate the
    current action and frontier before retaining an original result.
    """
    from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection

    try:
        if type(prior) is not GenericModelInputEvaluationBasisV1 or type(current) is not type(
            prior
        ):
            raise TypeError("generic_model_input_basis_untyped")
        prior = type(prior).model_validate_json(prior.model_dump_json())
        current = type(current).model_validate_json(current.model_dump_json())
        if (
            prior.basis_role != "evaluated"
            or current.basis_role != "prospective"
            or prior.comparison_profile != GENERIC_NUMERICAL_INTENT_PROFILE
            or current.comparison_profile != GENERIC_NUMERICAL_INTENT_PROFILE
            or prior.evaluation is None
            or prior.predicate_provenance != "recomputed"
            or current.predicate_provenance != "recomputed"
            or (
                prior.tenant_id,
                prior.cell_id,
                prior.run_id,
                prior.source_job_id,
                prior.candidate_id,
                prior.design_problem_ref,
            )
            != (
                current.tenant_id,
                current.cell_id,
                current.run_id,
                current.source_job_id,
                current.candidate_id,
                current.design_problem_ref,
            )
        ):
            raise ValueError("generic_model_input_basis_subject_mismatch")
        prepared = []
        for basis, origin in ((prior, prior_origin), (current, current_origin)):
            item = prepare_generic_model_input_numerical_basis(
                store=store,
                input_ref=basis.input_ref,
                semantic_successor_ref=basis.semantic_successor_ref,
                expected_blocked_execution_ref=origin.n5_execution_ref,
                controller=controller,
            )
            _verify_generic_model_input_origin(
                origin=origin, input_ref=basis.input_ref, successor=item.successor
            )
            selection = item.successor.selection
            if (
                basis.action_job_id != selection.action_job_id
                or basis.route_id != selection.route_id
                or basis.design_problem_ref != origin.source_cycle.design_problem_ref
                or basis.design_problem_basis_ref != item.successor.input_record.design_problem_ref
                or basis.candidate_id != origin.source_cycle.selected_candidate_ref
                or not _candidate_ref_same(
                    basis.bound_state_snapshot_ref, item.bound_state_snapshot_ref
                )
                or bytes.fromhex(basis.numerical_intent_hex) != item.numerical_intent
            ):
                raise ValueError("generic_model_input_basis_owner_replay_mismatch")
            prepared.append(item)
        observation = _verify_generic_model_input_original_evaluation(
            store=store,
            input_ref=prior.input_ref,
            semantic_successor_ref=prior.semantic_successor_ref,
            evaluation=prior.evaluation,
            prepared=prepared[0],
        )
        from polisyos.runtime.quality.n5_execution_profile import (
            reconcile_recorded_n5_profile_current_bytes,
        )

        if (
            reconcile_recorded_n5_profile_current_bytes(
                observation.execution_profile,
                prepared[1].execution_profile,
                recorded_source_image=observation.source_image,
                current_source_image=prepared[1].source_image,
            ).status
            != "recomputed"
        ):
            raise ValueError("generic_model_input_current_provider_not_established")
        states = tuple(
            state_snapshot_value_projection(
                load_state_snapshot(store, snapshot_ref=item.bound_state_snapshot_ref)
            )
            for item in prepared
        )
        if prepared[0].numerical_intent != prepared[1].numerical_intent or states[0] != states[1]:
            return "different", ()
        return "equivalent", ()
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        return "not_established", (str(getattr(exc, "code", None) or exc),)


def issue_generic_model_input_evaluation_decision(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    origin: VerifiedModelInputRoutingOrigin,
    prior_origin: VerifiedModelInputRoutingOrigin | None,
    controller: JointSimulationHorizonController,
    semantic_successor_ref: ArtifactRef,
    current_basis_ref: ArtifactRef,
    prior_basis_ref: ArtifactRef | None,
    prior_evaluation: GenericModelInputSelectedEvaluation | None,
    decision_kind: Literal["initial", "comparison"],
    comparison_result: Literal["equivalent", "different", "not_established"] | None,
    reason_codes: tuple[str, ...],
    expected_frontier_revision: int,
    expected_frontier_ref: str | None,
    generated_at: str,
) -> GenericModelInputEvaluationDecisionV1:
    """Recompute a candidate initial or comparison decision for this action.

    Initial selection requires the current action's already completed V5 and
    its evaluated basis. A comparison reopens both basis owners. The caller
    independently revalidates the live authority and fenced frontier; this
    record itself grants no retention, publication, or source authority.
    """
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedModelInputRoutingOrigin
    from polisyos.runtime.quality.model_input_successor_selection import (
        read_model_input_successor_selection,
    )

    if type(origin) is not VerifiedModelInputRoutingOrigin:
        raise TypeError("generic_model_input_origin_not_established")
    _require_candidate_issuance_reasons(reason_codes)
    selection = read_model_input_successor_selection(store, semantic_successor_ref)
    if (
        (selection.tenant_id, selection.cell_id, selection.run_id, selection.source_job_id)
        != (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id)
        or not _candidate_ref_same(selection.blocked_execution_ref, origin.n5_execution_ref)
        or not _candidate_ref_same(selection.routing_report_ref, origin.routing_report_ref)
        or not _candidate_ref_same(selection.compiled_ref, origin.compiled_ref)
        or selection.routing_use_decision_ref is None
    ):
        raise ValueError("generic_model_input_decision_origin_mismatch")
    current_basis = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=current_basis_ref,
        record_type=GenericModelInputEvaluationBasisV1,
    )
    if type(current_basis) is not GenericModelInputEvaluationBasisV1 or (
        current_basis.comparison_profile != GENERIC_NUMERICAL_INTENT_PROFILE
        or current_basis.action_job_id != selection.action_job_id
        or current_basis.route_id != selection.route_id
        or current_basis.design_problem_ref != origin.source_cycle.design_problem_ref
        or current_basis.design_problem_basis_ref != origin.n5_expectation.design_problem_ref
        or current_basis.candidate_id != origin.source_cycle.selected_candidate_ref
        or not _candidate_ref_same(current_basis.input_ref, origin.n5_expectation.input_ref)
        or not _candidate_ref_same(current_basis.semantic_successor_ref, semantic_successor_ref)
    ):
        raise ValueError("generic_model_input_decision_current_basis_mismatch")
    if decision_kind == "initial":
        if (
            comparison_result is not None
            or reason_codes
            or prior_origin is not None
            or prior_basis_ref is not None
            or prior_evaluation is not None
            or expected_frontier_revision != 0
            or expected_frontier_ref is not None
            or current_basis.basis_role != "evaluated"
            or current_basis.predicate_provenance != "recomputed"
            or current_basis.evaluation is None
            or current_basis.evaluation.action_job_id != selection.action_job_id
            or current_basis.prospective_basis_ref is not None
            or current_basis.comparison_decision_ref is not None
        ):
            raise ValueError("generic_model_input_initial_decision_invalid")
        replayed = issue_generic_model_input_evaluation_basis(
            store=store,
            origin=origin,
            input_ref=origin.n5_expectation.input_ref,
            semantic_successor_ref=semantic_successor_ref,
            controller=controller,
            basis_role="evaluated",
            evaluation=current_basis.evaluation,
        )
        if replayed != current_basis:
            raise ValueError("generic_model_input_initial_basis_replay_mismatch")
    elif decision_kind == "comparison":
        if current_basis.basis_role != "prospective":
            raise ValueError("generic_model_input_comparison_basis_invalid")
        replayed = issue_generic_model_input_evaluation_basis(
            store=store,
            origin=origin,
            input_ref=origin.n5_expectation.input_ref,
            semantic_successor_ref=semantic_successor_ref,
            controller=controller,
            basis_role="prospective",
        )
        if replayed != current_basis:
            raise ValueError("generic_model_input_current_basis_replay_mismatch")
        if prior_basis_ref is None:
            actual_result = "not_established"
            actual_reasons = ("generic_model_input_prior_basis_missing",)
            if prior_origin is not None or prior_evaluation is not None:
                raise ValueError("generic_model_input_decision_prior_mismatch")
        else:
            try:
                prior_basis = read_acquisition_evaluation_artifact(
                    store=store,
                    event_log=event_log,
                    ref=prior_basis_ref,
                    record_type=GenericModelInputEvaluationBasisV1,
                )
            except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError):
                prior_basis = None
            if prior_basis is None:
                if prior_evaluation is not None:
                    raise ValueError("generic_model_input_decision_prior_mismatch")
                actual_result = "not_established"
                actual_reasons = ("generic_model_input_prior_basis_not_established",)
            elif type(
                prior_basis
            ) is not GenericModelInputEvaluationBasisV1 or not _candidate_model_values_same(
                prior_basis.evaluation, prior_evaluation
            ):
                raise ValueError("generic_model_input_decision_prior_mismatch")
            elif prior_origin is None:
                actual_result = "not_established"
                actual_reasons = ("generic_model_input_prior_origin_not_established",)
            elif type(prior_origin) is not VerifiedModelInputRoutingOrigin:
                raise TypeError("generic_model_input_prior_origin_not_established")
            else:
                actual_result, actual_reasons = compare_generic_model_input_evaluation_bases(
                    store=store,
                    prior=prior_basis,
                    current=current_basis,
                    prior_origin=prior_origin,
                    current_origin=origin,
                    controller=controller,
                )
        if (comparison_result, reason_codes) != (actual_result, actual_reasons):
            raise ValueError("generic_model_input_decision_comparison_mismatch")
    else:
        raise ValueError("generic_model_input_decision_kind_unsupported")
    payload = {
        "schema_version": "GenericModelInputEvaluationDecision@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_rule": "generic-program-graph-declared-numerical-basis.v2",
        "decision_kind": decision_kind,
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "source_job_id": origin.source_job_id,
        "action_job_id": selection.action_job_id,
        "route_id": selection.route_id,
        "design_problem_ref": origin.source_cycle.design_problem_ref,
        "design_problem_basis_ref": origin.n5_expectation.design_problem_ref,
        "candidate_id": origin.source_cycle.selected_candidate_ref,
        "action_phase_ref": selection.action_phase_ref.model_dump(mode="json"),
        "semantic_successor_ref": semantic_successor_ref.model_dump(mode="json"),
        "routing_use_decision_ref": selection.routing_use_decision_ref.model_dump(mode="json"),
        "authority_decision_ref": selection.authority_decision_ref.model_dump(mode="json"),
        "activation_receipt_ref": selection.activation_receipt_ref.model_dump(mode="json"),
        "current_basis_ref": current_basis_ref.model_dump(mode="json"),
        "prior_basis_ref": prior_basis_ref.model_dump(mode="json") if prior_basis_ref else None,
        "prior_evaluation": prior_evaluation.model_dump(mode="json") if prior_evaluation else None,
        "comparison_result": comparison_result,
        "predicate_provenance": "not_established"
        if comparison_result == "not_established"
        else "recomputed",
        "reason_codes": list(reason_codes),
        "expected_frontier_revision": expected_frontier_revision,
        "expected_frontier_ref": expected_frontier_ref,
        "observed_admission": False,
        "publication_authority": False,
        "generated_at": generated_at,
    }
    return GenericModelInputEvaluationDecisionV1.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )


def _verify_generic_model_input_replacement(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    origin: VerifiedModelInputRoutingOrigin,
    prior_origin: VerifiedModelInputRoutingOrigin | None,
    controller: JointSimulationHorizonController,
    input_ref: ArtifactRef,
    semantic_successor_ref: ArtifactRef,
    prospective_basis_ref: ArtifactRef,
    comparison_decision_ref: ArtifactRef,
    prepared: PreparedGenericModelInputNumericalBasis,
) -> GenericModelInputEvaluationDecisionV1:
    """Replay the prior decision and the same current action's prospective basis."""
    from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection

    decision = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=comparison_decision_ref,
        record_type=GenericModelInputEvaluationDecisionV1,
    )
    prospective = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=prospective_basis_ref,
        record_type=GenericModelInputEvaluationBasisV1,
    )
    if (
        type(decision) is not GenericModelInputEvaluationDecisionV1
        or type(prospective) is not GenericModelInputEvaluationBasisV1
        or decision.comparison_rule != "generic-program-graph-declared-numerical-basis.v2"
        or prospective.comparison_profile != GENERIC_NUMERICAL_INTENT_PROFILE
        or decision.decision_kind != "comparison"
        or decision.comparison_result not in ("different", "not_established")
        or not _candidate_ref_same(decision.current_basis_ref, prospective_basis_ref)
        or not _candidate_ref_same(decision.semantic_successor_ref, semantic_successor_ref)
        or not _candidate_ref_same(prospective.semantic_successor_ref, semantic_successor_ref)
        or not _candidate_ref_same(prospective.input_ref, input_ref)
        or prospective.basis_role != "prospective"
        or prospective.predicate_provenance != "recomputed"
        or prospective.action_job_id != prepared.successor.selection.action_job_id
        or not _candidate_ref_same(
            prospective.bound_state_snapshot_ref, prepared.bound_state_snapshot_ref
        )
        or bytes.fromhex(prospective.numerical_intent_hex) != prepared.numerical_intent
    ):
        raise ValueError("generic_model_input_replacement_scope_mismatch")
    replayed_decision = issue_generic_model_input_evaluation_decision(
        store=store,
        event_log=event_log,
        origin=origin,
        prior_origin=prior_origin,
        controller=controller,
        semantic_successor_ref=semantic_successor_ref,
        current_basis_ref=prospective_basis_ref,
        prior_basis_ref=decision.prior_basis_ref,
        prior_evaluation=decision.prior_evaluation,
        decision_kind="comparison",
        comparison_result=decision.comparison_result,
        reason_codes=decision.reason_codes,
        expected_frontier_revision=decision.expected_frontier_revision,
        expected_frontier_ref=decision.expected_frontier_ref,
        generated_at=decision.generated_at,
    )
    if replayed_decision != decision:
        raise ValueError("generic_model_input_replacement_decision_mismatch")
    # Read both complete selected state quantities even though the same
    # action's exact selected snapshot ref is required above.
    prospective_state = load_state_snapshot(
        store, snapshot_ref=prospective.bound_state_snapshot_ref
    )
    evaluated_state = load_state_snapshot(store, snapshot_ref=prepared.bound_state_snapshot_ref)
    if state_snapshot_value_projection(prospective_state) != state_snapshot_value_projection(
        evaluated_state
    ):
        raise ValueError("generic_model_input_replacement_state_mismatch")
    return decision


def reconcile_generic_model_input_evaluation_completion(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    origin: VerifiedModelInputRoutingOrigin,
    prior_origin: VerifiedModelInputRoutingOrigin | None,
    controller: JointSimulationHorizonController,
    comparison_decision_ref: ArtifactRef,
    evaluated_basis_ref: ArtifactRef,
) -> GenericModelInputEvaluationBasisV1:
    """Reopen a fresh V5 basis and its exact prior comparison before selection.

    This does not advance a frontier or authorize a protected action. The
    caller must perform its current lease and transaction checks separately.
    """
    evaluated = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=evaluated_basis_ref,
        record_type=GenericModelInputEvaluationBasisV1,
    )
    if (
        type(evaluated) is not GenericModelInputEvaluationBasisV1
        or evaluated.basis_role != "evaluated"
        or evaluated.predicate_provenance != "recomputed"
        or evaluated.evaluation is None
        or evaluated.prospective_basis_ref is None
        or not _candidate_ref_same(evaluated.comparison_decision_ref, comparison_decision_ref)
    ):
        raise ValueError("generic_model_input_completion_not_established")
    replayed = issue_generic_model_input_evaluation_basis(
        store=store,
        event_log=event_log,
        origin=origin,
        prior_origin=prior_origin,
        input_ref=evaluated.input_ref,
        semantic_successor_ref=evaluated.semantic_successor_ref,
        controller=controller,
        basis_role="evaluated",
        evaluation=evaluated.evaluation,
        prospective_basis_ref=evaluated.prospective_basis_ref,
        comparison_decision_ref=comparison_decision_ref,
    )
    if replayed != evaluated:
        raise ValueError("generic_model_input_completion_replay_mismatch")
    return evaluated


def _recorded_generic_model_input_calls(
    observation: GenericProgramGraphContentObservationV2,
) -> tuple[tuple[int, str, int, bytes], ...]:
    """Read the original complete call census, without loading old or present code."""
    from polisyos.runtime.quality.n5_execution_basis import _require_v2_wire

    by_step: dict[int, tuple[tuple[int, str, bytes], ...]] = {}
    for step in observation.steps:
        calls = []
        for call in step.calls:
            encoded = call.callable_receiver_hex
            if encoded is None:
                raise ValueError("generic_model_input_history_call_not_established")
            content = bytes.fromhex(encoded)
            if not content or content.hex() != encoded:
                raise ValueError("generic_model_input_history_call_not_established")
            _require_v2_wire(content.decode("utf-8"))
            calls.append((call.plan_index, call.node_id, content))
        selected = tuple(calls)
        if step.step in by_step and by_step[step.step] != selected:
            raise ValueError("generic_model_input_history_call_census_mismatch")
        by_step[step.step] = selected
    return tuple(
        (index, node_id, step, content)
        for step, calls in sorted(by_step.items())
        for index, node_id, content in calls
    )


def _replay_generic_model_input_basis_values_for_history(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    origin: VerifiedModelInputRoutingOrigin,
    basis_ref: ArtifactRef,
    evaluation_context: GenericModelInputSelectedEvaluation,
) -> GenericModelInputEvaluationBasisV1:
    """Reconstruct immutable basis values from their original numerical observation.

    A retained prospective use has no separate observation of its past provider
    environment. Its numerical facets can be reconciled with the selected old
    observation; its issued decision remains a record of the predicate at that
    time. This path establishes no current provider or reuse permission.
    """
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from polisyos.runtime.quality.n5_candidate_content import _prepared_image_descriptor
    from polisyos.runtime.quality.n5_execution_basis import _v2_native_wire

    basis = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=basis_ref,
        record_type=GenericModelInputEvaluationBasisV1,
    )
    if (
        type(basis) is not GenericModelInputEvaluationBasisV1
        or basis.comparison_profile != GENERIC_NUMERICAL_INTENT_PROFILE
        or basis.basis_role not in ("prospective", "evaluated")
        or basis.predicate_provenance != "recomputed"
        or basis.reason_codes
        or type(evaluation_context) is not GenericModelInputSelectedEvaluation
    ):
        raise ValueError("generic_model_input_history_basis_not_established")
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    successor = owner.prepare_semantic_successor_request(
        semantic_successor_ref=basis.semantic_successor_ref,
        expected_blocked_execution_ref=origin.n5_execution_ref,
        expected_input_ref=basis.input_ref,
    )
    _verify_generic_model_input_origin(
        origin=origin, input_ref=basis.input_ref, successor=successor
    )
    source, selection = successor.input_record, successor.selection
    if (
        (basis.tenant_id, basis.cell_id, basis.run_id, basis.source_job_id)
        != (source.tenant_id, source.cell_id, source.run_id, source.job_id)
        or basis.action_job_id != selection.action_job_id
        or basis.route_id != selection.route_id
        or basis.design_problem_ref != origin.source_cycle.design_problem_ref
        or basis.design_problem_basis_ref != source.design_problem_ref
        or basis.candidate_id != origin.source_cycle.selected_candidate_ref
        or (
            basis.evaluation is not None
            and not _candidate_model_values_same(basis.evaluation, evaluation_context)
        )
    ):
        raise ValueError("generic_model_input_history_basis_subject_mismatch")
    original = owner.prepare_semantic_successor_request(
        semantic_successor_ref=evaluation_context.semantic_successor_ref,
        expected_blocked_execution_ref=origin.n5_execution_ref,
        expected_input_ref=evaluation_context.input_ref,
    )
    _verify_generic_model_input_origin(
        origin=origin, input_ref=evaluation_context.input_ref, successor=original
    )
    observation = _read_generic_model_input_original_evaluation(
        store=store,
        input_ref=evaluation_context.input_ref,
        semantic_successor_ref=evaluation_context.semantic_successor_ref,
        evaluation=evaluation_context,
        successor=original,
    )
    configuration = PreparedJointSimulationConfiguration.model_validate(
        observation.consumed_configuration
    )
    if tuple(
        (item.name, item.value) for item in observation.execution_profile.declared_settings
    ) != (
        (
            "prepared_configuration_hash",
            exact_n5_content_hash(configuration.model_dump(mode="python")),
        ),
    ) or observation.source_image.selected_profile_content != _v2_native_wire(
        _prepared_image_descriptor(configuration)
    ):
        raise ValueError("generic_model_input_history_recorded_profile_binding_mismatch")
    controller = JointSimulationHorizonController(_prepared_configuration=configuration)
    intake = _prepare_generic_model_input_numerical_intake(
        store=store,
        request=successor.request,
        preflight=successor.preflight,
        controller=controller,
    )
    intent = _generic_model_input_numerical_intent(
        intake,
        prepared_calls=_recorded_generic_model_input_calls(observation),
        configuration=configuration,
    )
    if (
        not _candidate_ref_same(basis.bound_state_snapshot_ref, intake.bound_state_snapshot_ref)
        or bytes.fromhex(basis.numerical_intent_hex) != intent
        or (
            basis.action_job_id == evaluation_context.action_job_id
            and basis.numerical_intent_sha256 != observation.numerical_intent_sha256
        )
    ):
        raise ValueError("generic_model_input_history_basis_owner_replay_mismatch")
    return basis


def replay_generic_model_input_decision_for_history(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    origin: VerifiedModelInputRoutingOrigin,
    decision_ref: ArtifactRef,
    evaluation_context: GenericModelInputSelectedEvaluation,
) -> GenericModelInputEvaluationDecisionV1:
    """Reconcile a recorded decision's parents without issuing a present decision.

    Args:
        store: Selected-profile artifact reader for the immutable history.
        event_log: Durable producer-event owner for the selected records.
        origin: Independently replayed blocked source and subject scope.
        decision_ref: Exact original decision selected by the completed action.
        evaluation_context: Original numerical observation selected for this use.

    Returns:
        The original decision, including its unchanged issuance-time provenance.

    Raises:
        ValueError: If any selected parent, subject, or recorded comparison conflicts.
    """
    from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
    from polisyos.runtime.quality.model_input_successor_selection import (
        read_model_input_successor_selection,
    )

    decision = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=decision_ref,
        record_type=GenericModelInputEvaluationDecisionV1,
    )
    if (
        type(decision) is not GenericModelInputEvaluationDecisionV1
        or decision.comparison_rule != "generic-program-graph-declared-numerical-basis.v2"
    ):
        raise ValueError("generic_model_input_history_decision_not_established")
    selection = read_model_input_successor_selection(store, decision.semantic_successor_ref)
    if (
        (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
        != (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id)
        or decision.action_job_id != selection.action_job_id
        or decision.route_id != selection.route_id
        or decision.design_problem_ref != origin.source_cycle.design_problem_ref
        or decision.design_problem_basis_ref != origin.n5_expectation.design_problem_ref
        or decision.candidate_id != origin.source_cycle.selected_candidate_ref
        or not _candidate_ref_same(decision.action_phase_ref, selection.action_phase_ref)
        or not _candidate_ref_same(
            decision.routing_use_decision_ref, selection.routing_use_decision_ref
        )
        or not _candidate_ref_same(
            decision.authority_decision_ref, selection.authority_decision_ref
        )
        or not _candidate_ref_same(
            decision.activation_receipt_ref, selection.activation_receipt_ref
        )
        or not _candidate_ref_same(selection.blocked_execution_ref, origin.n5_execution_ref)
        or not _candidate_ref_same(selection.routing_report_ref, origin.routing_report_ref)
        or not _candidate_ref_same(selection.compiled_ref, origin.compiled_ref)
    ):
        raise ValueError("generic_model_input_history_decision_subject_mismatch")
    current = _replay_generic_model_input_basis_values_for_history(
        store=store,
        event_log=event_log,
        origin=origin,
        basis_ref=decision.current_basis_ref,
        evaluation_context=evaluation_context,
    )
    if (
        current.action_job_id != decision.action_job_id
        or current.route_id != decision.route_id
        or not _candidate_ref_same(current.semantic_successor_ref, decision.semantic_successor_ref)
    ):
        raise ValueError("generic_model_input_history_decision_current_basis_mismatch")
    if decision.decision_kind == "initial":
        if (
            current.basis_role != "evaluated"
            or current.evaluation is None
            or current.prospective_basis_ref is not None
            or current.comparison_decision_ref is not None
        ):
            raise ValueError("generic_model_input_history_initial_basis_mismatch")
    else:
        if current.basis_role != "prospective":
            raise ValueError("generic_model_input_history_comparison_basis_mismatch")
        prior = None
        if decision.prior_basis_ref is not None:
            recorded_prior = read_acquisition_evaluation_artifact(
                store=store,
                event_log=event_log,
                ref=decision.prior_basis_ref,
                record_type=GenericModelInputEvaluationBasisV1,
            )
            if (
                type(recorded_prior) is not GenericModelInputEvaluationBasisV1
                or recorded_prior.evaluation is None
                or not _candidate_model_values_same(
                    recorded_prior.evaluation, decision.prior_evaluation
                )
            ):
                raise ValueError("generic_model_input_history_prior_evaluation_mismatch")
            prior = _replay_generic_model_input_basis_values_for_history(
                store=store,
                event_log=event_log,
                origin=origin,
                basis_ref=decision.prior_basis_ref,
                evaluation_context=recorded_prior.evaluation,
            )
        if decision.comparison_result != "not_established":
            if prior is None:
                raise ValueError("generic_model_input_history_prior_basis_missing")
            prior_state = state_snapshot_value_projection(
                load_state_snapshot(store, snapshot_ref=prior.bound_state_snapshot_ref)
            )
            current_state = state_snapshot_value_projection(
                load_state_snapshot(store, snapshot_ref=current.bound_state_snapshot_ref)
            )
            same = (
                bytes.fromhex(prior.numerical_intent_hex)
                == bytes.fromhex(current.numerical_intent_hex)
                and prior_state == current_state
            )
            if (decision.comparison_result == "equivalent") != same:
                raise ValueError("generic_model_input_history_comparison_mismatch")
        # A recorded refusal cannot reconstruct a past loaded provider world.
        # Its original reason/provenance remain recorded, and it grants no reuse.
    return decision


def replay_generic_model_input_basis_for_history(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    origin: VerifiedModelInputRoutingOrigin,
    basis_ref: ArtifactRef,
    evaluation_context: GenericModelInputSelectedEvaluation,
) -> GenericModelInputEvaluationBasisV1:
    """Replay an original basis and replacement parents without current admission.

    Args:
        store: Selected-profile artifact reader for the immutable history.
        event_log: Durable producer-event owner for the selected records.
        origin: Independently replayed blocked source and subject scope.
        basis_ref: Exact original prospective or evaluated basis.
        evaluation_context: Original numerical occurrence selector, reopened by this reader.

    Returns:
        The unchanged original basis after its immutable parents are reconciled.

    Raises:
        ValueError: If original values, numerical sources, or replacement parents conflict.
    """
    basis = _replay_generic_model_input_basis_values_for_history(
        store=store,
        event_log=event_log,
        origin=origin,
        basis_ref=basis_ref,
        evaluation_context=evaluation_context,
    )
    if basis.prospective_basis_ref is not None:
        if basis.comparison_decision_ref is None:
            raise ValueError("generic_model_input_history_replacement_parent_missing")
        decision = replay_generic_model_input_decision_for_history(
            store=store,
            event_log=event_log,
            origin=origin,
            decision_ref=basis.comparison_decision_ref,
            evaluation_context=evaluation_context,
        )
        prospective = _replay_generic_model_input_basis_values_for_history(
            store=store,
            event_log=event_log,
            origin=origin,
            basis_ref=basis.prospective_basis_ref,
            evaluation_context=evaluation_context,
        )
        if (
            decision.decision_kind != "comparison"
            or decision.comparison_result not in ("different", "not_established")
            or not _candidate_ref_same(decision.current_basis_ref, basis.prospective_basis_ref)
            or not _candidate_ref_same(
                decision.semantic_successor_ref, basis.semantic_successor_ref
            )
            or prospective.action_job_id != basis.action_job_id
            or prospective.basis_role != "prospective"
            or not _candidate_ref_same(
                prospective.bound_state_snapshot_ref, basis.bound_state_snapshot_ref
            )
            or bytes.fromhex(prospective.numerical_intent_hex)
            != bytes.fromhex(basis.numerical_intent_hex)
        ):
            raise ValueError("generic_model_input_history_replacement_parent_mismatch")
    return basis


class AcquisitionEvaluationDecision(_Record):
    """A recomputed comparison, bound to a particular action and frontier.

    Equivalence is necessary but never sufficient for a retained terminal. The
    actual current cheap continuation and native/frontier/lease commit remain
    mandatory owner operations. A decision artifact alone selects nothing.
    """

    ARTIFACT_KIND: ClassVar[str] = DECISION_KIND
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.AcquisitionEvaluationDecision"
    schema_version: Literal["AcquisitionEvaluationDecision@1.0"] = (
        "AcquisitionEvaluationDecision@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_rule: Literal["AD-E02-B09-01/owned-complete-native-values/v1"] = (
        "AD-E02-B09-01/owned-complete-native-values/v1"
    )
    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    action_job_id: str
    action_generation: int = Field(ge=1)
    route_id: str = Field(pattern=_HASH)
    compiled_ref: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    candidate_id: str
    selected_action_receipt_ref: ArtifactRef
    growth_receipt_ref: ArtifactRef
    admitted_source_ref: ArtifactRef
    prior_basis_ref: ArtifactRef | None
    current_basis_ref: ArtifactRef
    prior_evaluation: AcquisitionSelectedEvaluation | None
    comparison_result: Literal["equivalent", "different", "not_established"]
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    expected_frontier_revision: int = Field(ge=0)
    expected_frontier_ref: str | None = Field(default=None, pattern=_HASH)
    generated_at: str
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _content(self) -> AcquisitionEvaluationDecision:
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("acquisition_evaluation_decision_content_mismatch")
        if self.comparison_result == "equivalent" and (
            self.predicate_provenance != "recomputed"
            or self.reason_codes
            or self.prior_evaluation is None
            or self.prior_evaluation.basis_ref is None
            or self.prior_basis_ref is None
            or self.expected_frontier_revision < 1
            or self.expected_frontier_ref is None
        ):
            raise ValueError("acquisition_equivalent_decision_incomplete")
        if (self.comparison_result == "not_established") != (
            self.predicate_provenance == "not_established"
        ):
            raise ValueError("acquisition_evaluation_decision_predicate_mismatch")
        return self


class AcquisitionEvaluationDecisionV2(AcquisitionEvaluationDecision):
    """Candidate-only decision over the acquired numerical V2 basis."""

    schema_version: Literal["AcquisitionEvaluationDecision@2.0"] = (
        "AcquisitionEvaluationDecision@2.0"
    )
    comparison_rule: Literal["AD-E02-B09-01/declared-numerical-basis/v2"] = (
        "AD-E02-B09-01/declared-numerical-basis/v2"
    )


class CandidateAcquisitionEvaluationDecision(_Record):
    """One candidate-only comparison against the owner-selected frontier."""

    ARTIFACT_KIND: ClassVar[str] = DECISION_KIND
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.runtime.CandidateAcquisitionEvaluationDecision"
    schema_version: Literal["CandidateAcquisitionEvaluationDecision@1.0"] = (
        "CandidateAcquisitionEvaluationDecision@1.0"
    )
    authority_purpose: Literal["candidate_evaluation_retention_only"] = (
        "candidate_evaluation_retention_only"
    )
    comparison_rule: Literal["candidate-source-complete-native-values.v1"] = (
        "candidate-source-complete-native-values.v1"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    action_generation: int = Field(ge=1)
    route_id: str = Field(pattern=_HASH)
    compiled_ref: str = Field(pattern=_HASH)
    design_problem_ref: str = Field(pattern=_HASH)
    design_problem_basis_ref: str = Field(pattern=_HASH)
    candidate_id: str = Field(min_length=1)
    source_candidate_content_hash: str = Field(pattern=_HASH)
    candidate_action_ref: ArtifactRef
    reuse_occurrence_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    candidate_world_intent_ref: ArtifactRef
    candidate_source_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    prior_basis_ref: ArtifactRef | None = None
    prior_evaluation: AcquisitionSelectedEvaluation | None = None
    comparison_result: Literal["equivalent", "different", "not_established"]
    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...] = ()
    expected_frontier_revision: int = Field(ge=0)
    expected_frontier_ref: str | None = Field(default=None, pattern=_HASH)
    observed_admission: Literal[False] = False
    publication_authority: Literal[False] = False
    generated_at: str = Field(min_length=1)
    content_hash: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def _bind_candidate_decision(self) -> CandidateAcquisitionEvaluationDecision:
        refs = (
            (self.candidate_action_ref, "runtime_quality.acquisition_candidate_action_receipt"),
            (self.candidate_world_intent_ref, "runtime_quality.acquisition_candidate_world_intent"),
            (self.candidate_source_ref, "runtime.quality.candidate_acquisition_source"),
            (self.current_basis_ref, BASIS_KIND),
        )
        if any(not _candidate_selected_ref(ref, kind) for ref, kind in refs) or (
            self.prior_basis_ref is not None
            and not _candidate_selected_ref(self.prior_basis_ref, BASIS_KIND)
        ):
            raise ValueError("candidate_evaluation_decision_selected_ref_invalid")
        if self.reuse_occurrence_ref is not None and not _candidate_selected_ref(
            self.reuse_occurrence_ref, "runtime_quality.candidate_experiment_reuse_occurrence"
        ):
            raise ValueError("candidate_evaluation_decision_reuse_occurrence_invalid")
        if (self.expected_frontier_revision == 0) != (self.expected_frontier_ref is None):
            raise ValueError("candidate_evaluation_decision_frontier_mismatch")
        if (self.comparison_result == "not_established") != (
            self.predicate_provenance == "not_established"
        ) or (self.predicate_provenance == "recomputed") == bool(self.reason_codes):
            raise ValueError("candidate_evaluation_decision_predicate_mismatch")
        if self.comparison_result != "not_established" and (
            self.prior_basis_ref is None
            or self.prior_evaluation is None
            or not _candidate_ref_same(self.prior_evaluation.basis_ref, self.prior_basis_ref)
            or self.expected_frontier_revision < 1
        ):
            raise ValueError("candidate_evaluation_decision_prior_missing")
        if self.prior_evaluation is not None and (
            not _candidate_model_values_same(self.prior_evaluation, self.prior_evaluation)
            or self.prior_evaluation.candidate_id != self.candidate_id
            or self.prior_evaluation.candidate_content_hash != self.source_candidate_content_hash
            or self.prior_evaluation.design_problem_ref != self.design_problem_basis_ref
        ):
            raise ValueError("candidate_evaluation_decision_subject_mismatch")
        if self.content_hash != exact_n5_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("candidate_evaluation_decision_content_mismatch")
        return self


class CandidateAcquisitionEvaluationDecisionV2(CandidateAcquisitionEvaluationDecision):
    """Candidate decision comparing the declared numerical v2 basis only."""

    schema_version: Literal["CandidateAcquisitionEvaluationDecision@2.0"] = (
        "CandidateAcquisitionEvaluationDecision@2.0"
    )
    comparison_rule: Literal["candidate-source-declared-numerical-basis.v2"] = (
        "candidate-source-declared-numerical-basis.v2"
    )


def _candidate_issuance_ref(ref: ArtifactRef | None) -> dict[str, object] | None:
    """Serialize a complete reference without reducing a subtype's meaning."""
    if ref is None:
        return None
    if not _candidate_ref_same(ref, ref):
        raise ValueError("candidate_evaluation_issuance_ref_untyped")
    return ref.model_dump(mode="json")


def _require_candidate_issuance_reasons(reason_codes: tuple[str, ...]) -> None:
    """Keep actual caller reasons; never manufacture a replacement diagnostic."""
    if type(reason_codes) is not tuple or any(
        not isinstance(reason, str) or not reason.strip() for reason in reason_codes
    ):
        raise ValueError("candidate_evaluation_issuance_reasons_invalid")


def issue_candidate_acquisition_evaluation_basis(
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
    action_job_id: str,
    action_generation: int,
    route_id: str,
    design_problem_ref: str,
    design_problem_basis_ref: str,
    candidate_id: str,
    source_candidate_content_hash: str,
    candidate_action_ref: ArtifactRef,
    candidate_world_intent_ref: ArtifactRef,
    candidate_source_ref: ArtifactRef,
    preparation_inputs: CandidateSourceBasisInputs,
    prepared_n5_configuration: PreparedJointSimulationConfiguration | None,
    basis_role: Literal["prospective", "evaluated", "blocked"],
    values: dict[str, object],
    predicate_provenance: Literal["recomputed", "not_established"],
    reason_codes: tuple[str, ...],
    limitations: tuple[str, ...],
    selected_data_snapshot_ref: ArtifactRef | None = None,
    selected_world_model_ref: ArtifactRef | None = None,
    evaluation: AcquisitionSelectedEvaluation | None = None,
    reuse_occurrence_ref: ArtifactRef | None = None,
    basis_version: Literal["1.0", "2.0"] = "1.0",
) -> CandidateAcquisitionEvaluationBasis:
    """Construct a candidate basis from caller-replayed inputs and values.

    The caller must independently bind the selected action, source, preparation,
    configuration, limitations and any complete N5 evaluation. This constructor
    computes canonical hashes and validates the record; it performs no owner
    replay, persistence, currentness check or authorization. A fresh N5 does not
    upgrade an explicitly ``not_established`` basis. An evaluated selection must
    retain its original ``basis_ref=None`` until the terminal binds this basis.

    Raises:
        TypeError: If preparation, configuration, evaluation or values are untyped.
        ValueError: If the supplied record violates the candidate contract.
    """
    if type(preparation_inputs) is not CandidateSourceBasisInputs or not (
        _candidate_model_values_same(preparation_inputs, preparation_inputs)
    ):
        raise TypeError("candidate_evaluation_issuance_preparation_untyped")
    preparation = CandidateSourceBasisInputs.model_validate(
        preparation_inputs.model_dump(mode="python")
    )
    if prepared_n5_configuration is not None and (
        type(prepared_n5_configuration) is not PreparedJointSimulationConfiguration
        or not _candidate_model_values_same(prepared_n5_configuration, prepared_n5_configuration)
    ):
        raise TypeError("candidate_evaluation_issuance_configuration_untyped")
    if evaluation is not None and (
        type(evaluation) is not AcquisitionSelectedEvaluation
        or not _candidate_model_values_same(evaluation, evaluation)
    ):
        raise TypeError("candidate_evaluation_issuance_evaluation_untyped")
    if type(values) is not dict or any(not isinstance(name, str) for name in values):
        raise TypeError("candidate_evaluation_issuance_values_untyped")
    _require_candidate_issuance_reasons(reason_codes)
    if basis_version not in ("1.0", "2.0"):
        raise ValueError("candidate_evaluation_basis_version_unsupported")
    encoded = exact_n5_content_bytes(values)
    payload = {
        "schema_version": "CandidateAcquisitionEvaluationBasis@" + basis_version,
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": (
            "candidate_source_complete_native_values_v1"
            if basis_version == "1.0"
            else "candidate_source_declared_numerical_basis_v2"
        ),
        "basis_role": basis_role,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "run_id": run_id,
        "source_job_id": source_job_id,
        "action_job_id": action_job_id,
        "action_generation": action_generation,
        "route_id": route_id,
        "design_problem_ref": design_problem_ref,
        "design_problem_basis_ref": design_problem_basis_ref,
        "candidate_id": candidate_id,
        "source_candidate_content_hash": source_candidate_content_hash,
        "candidate_action_ref": _candidate_issuance_ref(candidate_action_ref),
        "candidate_world_intent_ref": _candidate_issuance_ref(candidate_world_intent_ref),
        "candidate_source_ref": _candidate_issuance_ref(candidate_source_ref),
        "preparation_inputs": preparation.model_dump(mode="json"),
        "prepared_n5_configuration": prepared_n5_configuration.model_dump(mode="json")
        if prepared_n5_configuration is not None
        else None,
        "selected_data_snapshot_ref": _candidate_issuance_ref(selected_data_snapshot_ref),
        "selected_world_model_ref": _candidate_issuance_ref(selected_world_model_ref),
        "evaluation": evaluation.model_dump(mode="json") if evaluation is not None else None,
        "predicate_provenance": predicate_provenance,
        "reason_codes": list(reason_codes),
        "limitations": list(limitations),
        "observed_admission": False,
        "publication_authority": False,
        "effective_native_values_hex": encoded.hex(),
        "effective_values_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
    }
    if reuse_occurrence_ref is not None:
        payload["reuse_occurrence_ref"] = _candidate_issuance_ref(reuse_occurrence_ref)
    record_type = CandidateAcquisitionEvaluationBasis
    if basis_version == "2.0":
        payload["closure_residuals"] = list(CANDIDATE_N5_CLOSURE_RESIDUALS_V2)
        record_type = CandidateAcquisitionEvaluationBasisV2
    return record_type.model_validate({**payload, "content_hash": exact_n5_content_hash(payload)})


def issue_candidate_acquisition_evaluation_decision(
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
    action_job_id: str,
    action_generation: int,
    route_id: str,
    compiled_ref: str,
    design_problem_ref: str,
    design_problem_basis_ref: str,
    candidate_id: str,
    source_candidate_content_hash: str,
    candidate_action_ref: ArtifactRef,
    candidate_world_intent_ref: ArtifactRef,
    candidate_source_ref: ArtifactRef,
    current_basis_ref: ArtifactRef,
    prior_basis_ref: ArtifactRef | None,
    prior_evaluation: AcquisitionSelectedEvaluation | None,
    comparison_result: Literal["equivalent", "different", "not_established"],
    predicate_provenance: Literal["recomputed", "not_established"],
    reason_codes: tuple[str, ...],
    expected_frontier_revision: int,
    expected_frontier_ref: str | None,
    generated_at: str,
    reuse_occurrence_ref: ArtifactRef | None = None,
    decision_version: Literal["1.0", "2.0"] = "1.0",
) -> CandidateAcquisitionEvaluationDecision:
    """Construct the caller's candidate comparison without granting retention.

    The caller must replay the selected bases, prior evaluation and exact
    frontier before supplying this comparison and its unchanged reasons. The
    explicit timestamp belongs to that caller's transaction, so retries can
    reproduce the same content. This constructor performs no comparison,
    persistence, currentness check, source admission or authorization.

    Raises:
        TypeError: If the supplied prior evaluation is untyped.
        ValueError: If the supplied record violates the candidate contract.
    """
    if prior_evaluation is not None and (
        type(prior_evaluation) is not AcquisitionSelectedEvaluation
        or not _candidate_model_values_same(prior_evaluation, prior_evaluation)
    ):
        raise TypeError("candidate_evaluation_issuance_evaluation_untyped")
    _require_candidate_issuance_reasons(reason_codes)
    if decision_version not in ("1.0", "2.0"):
        raise ValueError("candidate_evaluation_decision_version_unsupported")
    payload = {
        "schema_version": "CandidateAcquisitionEvaluationDecision@" + decision_version,
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_rule": (
            "candidate-source-complete-native-values.v1"
            if decision_version == "1.0"
            else "candidate-source-declared-numerical-basis.v2"
        ),
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "run_id": run_id,
        "source_job_id": source_job_id,
        "action_job_id": action_job_id,
        "action_generation": action_generation,
        "route_id": route_id,
        "compiled_ref": compiled_ref,
        "design_problem_ref": design_problem_ref,
        "design_problem_basis_ref": design_problem_basis_ref,
        "candidate_id": candidate_id,
        "source_candidate_content_hash": source_candidate_content_hash,
        "candidate_action_ref": _candidate_issuance_ref(candidate_action_ref),
        "candidate_world_intent_ref": _candidate_issuance_ref(candidate_world_intent_ref),
        "candidate_source_ref": _candidate_issuance_ref(candidate_source_ref),
        "current_basis_ref": _candidate_issuance_ref(current_basis_ref),
        "prior_basis_ref": _candidate_issuance_ref(prior_basis_ref),
        "prior_evaluation": prior_evaluation.model_dump(mode="json")
        if prior_evaluation is not None
        else None,
        "comparison_result": comparison_result,
        "predicate_provenance": predicate_provenance,
        "reason_codes": list(reason_codes),
        "expected_frontier_revision": expected_frontier_revision,
        "expected_frontier_ref": expected_frontier_ref,
        "observed_admission": False,
        "publication_authority": False,
        "generated_at": generated_at,
    }
    if reuse_occurrence_ref is not None:
        payload["reuse_occurrence_ref"] = _candidate_issuance_ref(reuse_occurrence_ref)
    record_type = (
        CandidateAcquisitionEvaluationDecision
        if decision_version == "1.0"
        else CandidateAcquisitionEvaluationDecisionV2
    )
    return record_type.model_validate({**payload, "content_hash": exact_n5_content_hash(payload)})


@dataclass(frozen=True)
class ResolvedAcquisitionEvaluation:
    """Actual source/context/input/result objects reopened by their owners."""

    selected: AcquisitionSelectedEvaluation
    source: N4CandidateScenarioSourceRecordV3
    input_record: CandidateSimulationN5InputV5
    execution: CandidateSimulationExecutionV5
    result: JointSimulationResult
    handoff: CandidateSimulationContextHandoff


def rebuild_selected_candidate_n5_request(
    *,
    store: CoreJSONArtifactStore,
    input_ref: ArtifactRef,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str,
) -> JointSimulationRequest:
    """Reopen the selected V5 source and rebuild its producer-owned request.

    This historical reconstruction grants neither current use nor authority.
    The caller independently binds the selected input to its own route and result.
    """
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_cycle import (
        _value_outcome_variable,
        build_candidate_n5_request_from_resolved_values,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )

    expected = {
        "expected_run_id": run_id,
        "expected_job_id": job_id,
        "expected_tenant_id": tenant_id,
        "expected_cell_id": cell_id,
    }
    repository = GenerationSourceRepository(store)
    record = repository.resolve_candidate_simulation_v5(ref=input_ref, **expected)
    if type(record) is not CandidateSimulationN5InputV5:
        raise ValueError("candidate_n5_source_request_input_not_established")
    source = repository.load_candidate_scenario_source_for_n5(record.n4_source_ref, **expected)
    if type(source) is not N4CandidateScenarioSourceRecordV3:
        raise ValueError("candidate_n5_source_request_source_not_established")
    context = (
        CycleSubstrateContextArtifactOwner(store=store)
        .resolve_historical_job_artifact(record.context_job_ref, problem=source.problem, **expected)
        .context
    )
    _, ncm = repository.load_candidate_declared_ncm(
        declaration_ref=record.model_declaration_ref,
        ncm_ref=record.ncm_ref,
        expected_profile=record.profile,
        **expected,
    )
    outcome = _value_outcome_variable(source.candidate, source.problem)
    if (
        outcome != record.outcome_variable
        or source.candidate.candidate_id != record.original_candidate_id
        or source.candidate.atom.content_hash != record.original_candidate_hash
        or context.content_hash != record.materialization.context_hash
        or context.world_model_record.content_hash != record.materialization.world_model_record_hash
        or str(record.ncm_ref.artifact_id)
        not in context.world_model_record.simulation_model_ref.ncm_refs
        or exact_n5_content_bytes(source.profile) != exact_n5_content_bytes(record.profile)
    ):
        raise ValueError("candidate_n5_source_request_binding_mismatch")
    return build_candidate_n5_request_from_resolved_values(
        world_record=context.world_model_record,
        derived_atom=record.materialization.derived_n5_atom,
        outcome=outcome,
        ncm_spec=ncm,
        n5_config=record.n5,
    )


@dataclass(frozen=True, slots=True)
class CandidateEvaluationTerminalHistory:
    """Owner-replayed candidate terminal, not a current authorization token.

    Route folding receives this only from the historical verifier after it has
    checked the selected event, action, basis, continuation and SQL frontier.
    Mutation consumers must resolve the live route and lease again.
    """

    head: AcquisitionActionHeadRecord
    terminal_ref: ArtifactRef
    terminal: AcquisitionCandidateRouteLoopReceipt
    action: CandidateAcquisitionActionReceipt
    decision: CandidateAcquisitionEvaluationDecision
    current_basis: CandidateAcquisitionEvaluationBasis
    selected_basis: CandidateAcquisitionEvaluationBasis
    evaluation: ResolvedAcquisitionEvaluation | None
    reentry: CandidateSourceReentryReceipt | None
    continuation: CandidateAcquisitionRetainedContinuation | None
    frontier: AcquisitionEvaluationFrontierRecord


@dataclass(frozen=True, slots=True)
class CandidateExperimentTerminalHistory:
    """Replayed candidate-experiment terminal, never a current permission.

    This view binds a terminal to its original candidate source, signed PA2
    history, action receipt, source re-entry or retained continuation, and the
    exact SQL evaluation frontier. ``phase_chain`` ends with the selected
    terminal. Consumers must obtain live permission and lease independently
    before any further effect. ``recorded_live_refusal`` means that a V2
    blocked comparison preserved the producer's recorded failure to establish
    a live implementation. That historical predicate is consumer-asserted;
    this reader does not claim to reconstruct a past loaded implementation.
    """

    head: AcquisitionActionHeadRecord
    terminal_ref: ArtifactRef
    terminal: (
        AcquisitionCandidateExperimentTerminalReceipt
        | AcquisitionCandidateExperimentTerminalReceiptV2
    )
    origin: VerifiedCandidateExperimentOrigin
    phase_chain: tuple[VerifiedAcquisitionActionPhase, ...]
    action: CandidateAcquisitionActionReceipt
    source: CandidateAcquisitionSource
    budget_window: BudgetLedgerReentryBudgetWindow | None
    decision: CandidateAcquisitionEvaluationDecision | None
    current_basis: CandidateAcquisitionEvaluationBasis | None
    selected_basis: CandidateAcquisitionEvaluationBasis | None
    evaluation: ResolvedAcquisitionEvaluation | None
    reentry: CandidateSourceReentryReceipt | None
    continuation: CandidateAcquisitionRetainedContinuation | None
    frontier_before: AcquisitionEvaluationFrontierRecord | None
    frontier_after: AcquisitionEvaluationFrontierRecord | None
    reentry_evaluation: ResolvedAcquisitionEvaluation | None = None
    reuse_occurrence: CandidateExperimentReuseOccurrence | None = None
    reuse_occurrence_ref: ArtifactRef | None = None
    provenance_budget_window: BudgetLedgerReentryBudgetWindow | None = None
    recorded_live_refusal: bool = False


def resolve_selected_acquisition_evaluation(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
) -> ResolvedAcquisitionEvaluation:
    """Reopen the current route's selected evaluation without relaxing old job scope."""
    return resolve_selected_acquisition_evaluation_parts(
        artifact_store=bridge.artifact_store,
        control_store=bridge.control_store,
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        generation_run=closure.generation_run,
        source_cycle=closure.source_cycle,
        design_problem_ref=closure.design_problem_ref,
    )


def resolve_selected_acquisition_evaluation_parts(
    *,
    artifact_store: CoreJSONArtifactStore,
    control_store: ControlPlaneStore,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    generation_run: GenerationCycleRun,
    source_cycle: GenerationCycleRecord,
    design_problem_ref: str,
) -> ResolvedAcquisitionEvaluation:
    """Read one verified accumulator cycle through its actual source owners.

    This is shared by current mutation and historical fold. It does not grant
    present source eligibility, permission or a job lease.
    """
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_cycle import _cycle_basis_ref
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    cycle = source_cycle
    simulation = cycle.simulation
    if simulation.status != "joint_simulated":
        raise ValueError("acquisition_prior_actual_n5_not_established")
    source_ref = simulation.candidate_simulation_n4_source_ref
    context_ref = simulation.candidate_simulation_context_job_ref
    input_ref = simulation.candidate_simulation_n5_input_ref
    result_ref = simulation.simulation_result_ref
    execution_ref = ArtifactRef.model_validate(
        simulation.diagnostics.get("candidate_simulation_execution_selected_ref")
    )
    if any(ref is None for ref in (source_ref, context_ref, input_ref, result_ref)):
        raise ValueError("acquisition_prior_selected_evaluation_refs_missing")
    repository = GenerationSourceRepository(artifact_store)
    source, execution, input_record, result = (
        repository._resolve_selected_candidate_simulation_v5_pair(
            source_ref=source_ref,
            execution_ref=execution_ref,
            input_ref=input_ref,
            expected_run_id=run_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
    )
    if (
        type(execution) is not CandidateSimulationExecutionV5
        or type(input_record) is not CandidateSimulationN5InputV5
        or execution.original_candidate_id != cycle.selected_candidate_ref
        or execution.original_candidate_hash != cycle.selected_candidate_content_hash
        or execution.world_model_record_hash != simulation.k_world_ref_before
        or execution.world_model_record_hash != simulation.k_world_ref_after
        or source.candidate.candidate_id != cycle.selected_candidate_ref
        or source.candidate.atom.content_hash != cycle.selected_candidate_content_hash
        or source.stable_subject_ref != design_problem_ref
        or generation_run.design_problem_ref != design_problem_ref
        or _cycle_basis_ref(source_cycle) != source.cycle_problem_ref
    ):
        raise ValueError("acquisition_prior_evaluation_accumulator_mismatch")
    for left, right in (
        (execution.n5_input_ref, input_ref),
        (execution.n4_source_ref, source_ref),
        (execution.context_job_ref, context_ref),
        (execution.n5_result_ref, result_ref),
        (input_record.n4_source_ref, source_ref),
        (input_record.context_job_ref, context_ref),
    ):
        if artifact_ref_identity_key(left) != artifact_ref_identity_key(right):
            raise ValueError("acquisition_prior_evaluation_selected_join_mismatch")
    context_job = CycleSubstrateContextArtifactOwner(
        store=artifact_store,
        control_store=control_store,
    ).resolve_historical_job_artifact(
        context_ref,
        problem=source.problem,
        expected_job_id=source.job_id,
        expected_run_id=run_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    if context_job.context.world_model_record_content_hash != execution.world_model_record_hash:
        raise ValueError("acquisition_prior_context_world_mismatch")
    declaration, _ = repository.load_candidate_declared_ncm(
        declaration_ref=input_record.model_declaration_ref,
        ncm_ref=input_record.ncm_ref,
        expected_profile=input_record.profile,
        expected_job_id=source.job_id,
        expected_run_id=run_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _validate_loaded_joint_simulation_result,
    )

    _validate_loaded_joint_simulation_result(
        result,
        expected_world_model_record_content_hash=execution.world_model_record_hash,
        expected_atom_ids=(input_record.materialization.derived_n5_atom.intervention_id,),
        expected_selected_outcomes=(input_record.outcome_variable,),
    )
    selected = AcquisitionSelectedEvaluation(
        candidate_id=cycle.selected_candidate_ref,
        candidate_content_hash=cycle.selected_candidate_content_hash,
        design_problem_ref=source.cycle_problem_ref,
        world_model_record_hash=execution.world_model_record_hash,
        evaluation_job_id=source.job_id,
        evaluation_run_id=run_id,
        generation_run_id=generation_run.run_id,
        cycle_index=cycle.cycle_index,
        n4_source_ref=source_ref,
        context_job_ref=context_ref,
        n5_input_ref=input_ref,
        n5_execution_ref=execution_ref,
        n5_result_ref=result_ref,
    )
    return ResolvedAcquisitionEvaluation(
        selected=selected,
        source=source,
        input_record=input_record,
        execution=execution,
        result=result,
        handoff=CandidateSimulationContextHandoff(
            context=context_job.context,
            context_job_ref=context_ref,
            profile=input_record.profile,
            profile_config_ref=input_record.profile_config_ref,
            job_id=source.job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            model_declaration=declaration,
            model_declaration_ref=input_record.model_declaration_ref,
            ncm_ref=input_record.ncm_ref,
        ),
    )


def selected_artifact_ref(store: CoreJSONArtifactStore, locator: str) -> ArtifactRef:
    """Read the real manifest selector; never construct a profile from a label."""
    manifest = store.get_manifest(locator)
    ref = artifact_ref_for_manifest(manifest)
    if not store.verify(ref).ok:
        raise ValueError("acquisition_evaluation_selected_artifact_unverified")
    return ref


def _typed_record_input_refs(record: BaseModel) -> tuple[tuple[str, ArtifactRef], ...]:
    """Walk the complete typed record for selector-preserving input lineage."""
    rows: list[tuple[str, ArtifactRef]] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, ArtifactRef):
            rows.append((path, value))
        elif isinstance(value, BaseModel):
            for name in type(value).model_fields:
                visit(getattr(value, name), path + "." + name)
        elif isinstance(value, dict):
            for name, item in sorted(value.items(), key=lambda row: str(row[0])):
                visit(item, path + "." + str(name))
        elif isinstance(value, (tuple, list)):
            for index, item in enumerate(value):
                visit(item, path + "." + str(index))

    visit(record, "input")
    return tuple(sorted(rows, key=lambda row: row[0]))


def _candidate_evaluation_event_id(
    record: CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture,
) -> str:
    """Name one immutable decision or basis role per exact selected action."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )

    if type(record) in (
        CandidateAcquisitionEvaluationDecision,
        CandidateAcquisitionEvaluationDecisionV2,
    ):
        role = "decision"
    elif type(record) in (
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationBasisV2,
    ):
        role = "prospective_basis" if record.basis_role == "prospective" else "outcome_basis"
    elif type(record) is CandidateAcquisitionRetainedContinuation:
        role = "retained_continuation"
    elif type(record) is CandidateRetainedPortCapture:
        role = "retained_port_capture"
    else:
        raise TypeError("candidate_evaluation_record_untyped")
    return _candidate_evaluation_role_event_id(
        record.candidate_action_ref,
        role,
        reuse_occurrence_ref=getattr(record, "reuse_occurrence_ref", None),
    )


def _candidate_evaluation_role_event_id(
    action_ref: ArtifactRef,
    role: Literal[
        "decision",
        "prospective_basis",
        "outcome_basis",
        "retained_continuation",
        "retained_port_capture",
    ],
    *,
    reuse_occurrence_ref: ArtifactRef | None = None,
) -> str:
    """Name the single action-scoped event used for crash-window recovery."""
    if (
        type(action_ref) is not ArtifactRef
        or action_ref.kind != "runtime_quality.acquisition_candidate_action_receipt"
        or action_ref.media_type != "application/json"
        or action_ref.manifest_profile_sha256 is None
        or role
        not in {
            "decision",
            "prospective_basis",
            "outcome_basis",
            "retained_continuation",
            "retained_port_capture",
        }
    ):
        raise ValueError("candidate_evaluation_event_scope_untyped")
    if reuse_occurrence_ref is not None and not _candidate_selected_ref(
        reuse_occurrence_ref, "runtime_quality.candidate_experiment_reuse_occurrence"
    ):
        raise ValueError("candidate_evaluation_event_scope_untyped")
    identity = hashlib.sha256(
        exact_n5_content_bytes(reuse_occurrence_ref or action_ref)
    ).hexdigest()
    return f"evt_candidate_evaluation_{role}_{identity}"


def _generic_model_input_evaluation_event_id(
    record: GenericModelInputEvaluationBasisV1 | GenericModelInputEvaluationDecisionV1,
) -> str:
    """Name one candidate record role on its exact current semantic selection."""
    if type(record) is GenericModelInputEvaluationBasisV1:
        role = {
            "prospective": "prospective_basis",
            "evaluated": "evaluated_basis",
            "blocked": "blocked_basis",
        }[record.basis_role]
    elif type(record) is GenericModelInputEvaluationDecisionV1:
        role = "decision"
    else:
        raise TypeError("generic_model_input_evaluation_record_untyped")
    identity = hashlib.sha256(exact_n5_content_bytes(record.semantic_successor_ref)).hexdigest()
    return f"evt_generic_model_input_{role}_{identity}"


def persist_acquisition_evaluation_artifact(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    record: AcquisitionEvaluationBasis
    | AcquisitionEvaluationDecision
    | CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture
    | AcquisitionRetainedContinuation
    | GenericModelInputEvaluationBasisV1
    | GenericModelInputEvaluationDecisionV1,
) -> ArtifactRef:
    """Persist and reopen one strict basis/decision with its real producer event."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )

    if type(record) not in {
        AcquisitionEvaluationBasis,
        AcquisitionEvaluationBasisV2,
        AcquisitionEvaluationDecision,
        AcquisitionEvaluationDecisionV2,
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationBasisV2,
        CandidateAcquisitionEvaluationDecision,
        CandidateAcquisitionEvaluationDecisionV2,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
        AcquisitionRetainedContinuation,
        GenericModelInputEvaluationBasisV1,
        GenericModelInputEvaluationDecisionV1,
    }:
        raise TypeError("acquisition_evaluation_artifact_untyped")
    if type(record) is CandidateRetainedPortCapture:
        from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
            _require_candidate_retained_port_scope,
        )

        _require_candidate_retained_port_scope(record=record, store=store, event_log=event_log)
    payload = record.model_dump(mode="json")
    identity = record.content_hash.removeprefix("sha256:")
    generated_at = datetime.now(UTC).isoformat()
    typed_refs = _typed_record_input_refs(record)
    refs = tuple(sorted({str(ref.artifact_id) for _, ref in typed_refs}))
    result = write_runtime_authority_artifact(
        store,
        event_log,
        payload,
        artifacts.ArtifactWriteOptions(
            kind=record.ARTIFACT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=record.ARTIFACT_SCHEMA_NAME,
                version=(
                    "2.0"
                    if type(record)
                    in (
                        CandidateAcquisitionEvaluationBasisV2,
                        CandidateAcquisitionEvaluationDecisionV2,
                        AcquisitionEvaluationBasisV2,
                        AcquisitionEvaluationDecisionV2,
                    )
                    else "1.0"
                ),
            ),
            producer=artifacts.ProducerInfo(component=PRODUCER, version="1.0"),
            inputs=[input_ref_from_artifact_ref(ref, role=path) for path, ref in typed_refs],
        ),
        evidence_id=identity,
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner="team-runtime-quality",
        reader_contract=record.ARTIFACT_KIND + ".reader",
        reader_contract_version=(
            "2.0"
            if type(record)
            in (
                CandidateAcquisitionEvaluationBasisV2,
                CandidateAcquisitionEvaluationDecisionV2,
                AcquisitionEvaluationBasisV2,
                AcquisitionEvaluationDecisionV2,
            )
            else "1.0"
        ),
        tenant_id=record.tenant_id,
        cell_id=record.cell_id,
        run_id=record.run_id,
        job_id=record.source_job_id,
        trace_id="trace-" + record.source_job_id,
        span_id="span-evaluation-basis",
        parent_span_id=None,
        requested_execution_profile="governed",
        effective_execution_profile="governed",
        phase="acquisition_evaluation",
        generated_at=generated_at,
        as_of_time=generated_at,
        same_input_closure={
            "closure_id": "acquisition-evaluation:" + record.content_hash,
            "status": "closed",
            "run_id": record.run_id,
            "job_id": record.source_job_id,
            "tenant_id": record.tenant_id,
            "cell_id": record.cell_id,
            "evidence_input_refs": refs,
            "closure_sha256": record.design_problem_ref,
        },
        input_refs=refs,
        effective_mode_ref=record.comparison_profile
        if isinstance(
            record,
            (
                AcquisitionEvaluationBasis,
                CandidateAcquisitionEvaluationBasis,
                GenericModelInputEvaluationBasisV1,
            ),
        )
        else record.comparison_rule,
        degradation_ledger_ref=None,
        semantic_binding_ref=record.content_hash,
        validation_status="pass",
        blocking_status="non_blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary=PRODUCER,
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="pa2_ds9_decision_required",
        ),
        event_id=(
            _generic_model_input_evaluation_event_id(record)
            if type(record)
            in (GenericModelInputEvaluationBasisV1, GenericModelInputEvaluationDecisionV1)
            else _candidate_evaluation_event_id(record)
            if isinstance(
                record,
                (
                    CandidateAcquisitionEvaluationBasis,
                    CandidateAcquisitionEvaluationDecision,
                    CandidateAcquisitionRetainedContinuation,
                    CandidateRetainedPortCapture,
                ),
            )
            else "evt_acquisition_evaluation_" + identity
        ),
        event_source=PRODUCER,
        event_type="polisyos.runtime.acquisition.evaluation.v1",
        event_subject="run/" + record.run_id + "/candidate/" + record.candidate_id,
        state_before=None,
        state_after=record.predicate_provenance,
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    loaded = read_acquisition_evaluation_artifact(
        store=store,
        event_log=event_log,
        ref=result.cas_ref,
        record_type=type(record),
    )
    if loaded != record:
        raise RuntimeError("acquisition_evaluation_artifact_readback_mismatch")
    return result.cas_ref


def read_acquisition_evaluation_artifact(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
    record_type: type[AcquisitionEvaluationBasis]
    | type[AcquisitionEvaluationDecision]
    | type[CandidateAcquisitionEvaluationBasis]
    | type[CandidateAcquisitionEvaluationDecision]
    | type[CandidateAcquisitionRetainedContinuation]
    | type[CandidateRetainedPortCapture]
    | type[AcquisitionRetainedContinuation]
    | type[GenericModelInputEvaluationBasisV1]
    | type[GenericModelInputEvaluationDecisionV1],
) -> (
    AcquisitionEvaluationBasis
    | AcquisitionEvaluationDecision
    | CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture
    | AcquisitionRetainedContinuation
    | GenericModelInputEvaluationBasisV1
    | GenericModelInputEvaluationDecisionV1
):
    """Resolve exact selected bytes, schema, producer and durable event scope."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )

    if record_type not in {
        AcquisitionEvaluationBasis,
        AcquisitionEvaluationBasisV2,
        AcquisitionEvaluationDecision,
        AcquisitionEvaluationDecisionV2,
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationBasisV2,
        CandidateAcquisitionEvaluationDecision,
        CandidateAcquisitionEvaluationDecisionV2,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
        AcquisitionRetainedContinuation,
        GenericModelInputEvaluationBasisV1,
        GenericModelInputEvaluationDecisionV1,
    }:
        raise TypeError("acquisition_evaluation_artifact_reader_untyped")
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ValueError("acquisition_evaluation_artifact_profile_missing")
    manifest = store.get_manifest(ref)
    if (
        artifact_ref_identity_key(artifact_ref_for_manifest(manifest))
        != artifact_ref_identity_key(ref)
        or not store.verify(ref).ok
        or manifest.kind != record_type.ARTIFACT_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != record_type.ARTIFACT_SCHEMA_NAME
        or manifest.artifact_schema.version
        != (
            "2.0"
            if record_type
            in (
                CandidateAcquisitionEvaluationBasisV2,
                CandidateAcquisitionEvaluationDecisionV2,
                AcquisitionEvaluationBasisV2,
                AcquisitionEvaluationDecisionV2,
            )
            else "1.0"
        )
        or manifest.producer is None
        or manifest.producer.component != PRODUCER
        or manifest.producer.version != "1.0"
    ):
        raise ValueError("acquisition_evaluation_artifact_owner_mismatch")
    record = record_type.model_validate(load_core_json_artifact(store, ref))
    expected_inputs = tuple(
        sorted(
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for path, input_ref in _typed_record_input_refs(record)
            for item in (input_ref_from_artifact_ref(input_ref, role=path),)
        )
    )
    actual_inputs = tuple(
        sorted(
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in manifest.inputs
        )
    )
    if actual_inputs != expected_inputs:
        raise ValueError("acquisition_evaluation_artifact_input_lineage_mismatch")
    report = reconcile_authority_ref(
        artifact_store=store,
        event_log=event_log,
        cas_ref=(
            ref
            if isinstance(
                record,
                (
                    CandidateAcquisitionEvaluationBasis,
                    CandidateAcquisitionEvaluationDecision,
                    CandidateAcquisitionRetainedContinuation,
                    CandidateRetainedPortCapture,
                    GenericModelInputEvaluationBasisV1,
                    GenericModelInputEvaluationDecisionV1,
                ),
            )
            else str(ref.artifact_id)
        ),
        expected_tenant_id=record.tenant_id,
        expected_cell_id=record.cell_id,
        expected_run_id=record.run_id,
        expected_job_id=record.source_job_id,
    )
    if report.durable_event_id is None:
        raise ValueError("acquisition_evaluation_artifact_event_unavailable")
    if isinstance(
        record,
        (
            CandidateAcquisitionEvaluationBasis,
            CandidateAcquisitionEvaluationDecision,
            CandidateAcquisitionRetainedContinuation,
            CandidateRetainedPortCapture,
            GenericModelInputEvaluationBasisV1,
            GenericModelInputEvaluationDecisionV1,
        ),
    ):
        expected_event_id = (
            _generic_model_input_evaluation_event_id(record)
            if type(record)
            in (GenericModelInputEvaluationBasisV1, GenericModelInputEvaluationDecisionV1)
            else _candidate_evaluation_event_id(record)
        )
        rows = event_log.list_events(event_id=expected_event_id, limit=2)
        if report.durable_event_id != expected_event_id or len(rows) != 1:
            raise ValueError("candidate_evaluation_artifact_event_unavailable")
        event = rows[0].event
        if (
            event.event_source != PRODUCER
            or event.event_type != "polisyos.runtime.acquisition.evaluation.v1"
            or event.tenant_id != record.tenant_id
            or event.cell_id != record.cell_id
            or event.run_id != record.run_id
            or event.job_id != record.source_job_id
            or str(ref.artifact_id) not in event.artifact_refs
        ):
            raise ValueError("candidate_evaluation_artifact_event_mismatch")
    return record


def read_acquisition_basis_or_decision_artifact(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
    kind: Literal["basis", "decision"],
) -> AcquisitionEvaluationBasis | AcquisitionEvaluationDecision:
    """Dispatch ordinary acquired-observation records by their persisted version."""
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ValueError("acquisition_evaluation_artifact_profile_missing")
    schema = store.get_manifest(ref).artifact_schema
    classes = {
        ("basis", "1.0"): AcquisitionEvaluationBasis,
        ("basis", "2.0"): AcquisitionEvaluationBasisV2,
        ("decision", "1.0"): AcquisitionEvaluationDecision,
        ("decision", "2.0"): AcquisitionEvaluationDecisionV2,
    }
    record_type = classes.get((kind, schema.version)) if schema is not None else None
    if record_type is None or schema.name != record_type.ARTIFACT_SCHEMA_NAME:
        raise ValueError("acquisition_evaluation_artifact_version_not_established")
    record = read_acquisition_evaluation_artifact(
        store=store, event_log=event_log, ref=ref, record_type=record_type
    )
    if not isinstance(record, (AcquisitionEvaluationBasis, AcquisitionEvaluationDecision)):
        raise TypeError("acquisition_evaluation_artifact_reader_untyped")
    return record


def read_candidate_acquisition_evaluation_basis_artifact(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
) -> CandidateAcquisitionEvaluationBasis:
    """Dispatch the selected candidate basis by its persisted manifest version.

    The ordinary reader verifies the full selected profile, producer and event
    after this dispatch. Unknown versions are not comparable.
    """
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ValueError("acquisition_evaluation_artifact_profile_missing")
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if schema is None or schema.name != CandidateAcquisitionEvaluationBasis.ARTIFACT_SCHEMA_NAME:
        raise ValueError("candidate_evaluation_basis_schema_not_established")
    if schema.version == "1.0":
        record_type = CandidateAcquisitionEvaluationBasis
    elif schema.version == "2.0":
        record_type = CandidateAcquisitionEvaluationBasisV2
    else:
        raise ValueError("candidate_evaluation_basis_version_unsupported")
    record = read_acquisition_evaluation_artifact(
        store=store, event_log=event_log, ref=ref, record_type=record_type
    )
    if not isinstance(record, CandidateAcquisitionEvaluationBasis):
        raise TypeError("candidate_evaluation_basis_reader_untyped")
    return record


def read_candidate_acquisition_evaluation_decision_artifact(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
) -> CandidateAcquisitionEvaluationDecision:
    """Read the selected candidate decision under its declared version."""
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ValueError("acquisition_evaluation_artifact_profile_missing")
    schema = store.get_manifest(ref).artifact_schema
    if schema is None or schema.name != CandidateAcquisitionEvaluationDecision.ARTIFACT_SCHEMA_NAME:
        raise ValueError("candidate_evaluation_decision_schema_not_established")
    if schema.version == "1.0":
        record_type = CandidateAcquisitionEvaluationDecision
    elif schema.version == "2.0":
        record_type = CandidateAcquisitionEvaluationDecisionV2
    else:
        raise ValueError("candidate_evaluation_decision_version_unsupported")
    record = read_acquisition_evaluation_artifact(
        store=store, event_log=event_log, ref=ref, record_type=record_type
    )
    if not isinstance(record, CandidateAcquisitionEvaluationDecision):
        raise TypeError("candidate_evaluation_decision_reader_untyped")
    return record


def basis_exact_values_equal(
    left: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
    right: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
) -> bool:
    """Compare the complete admitted native quantity, without hash-only equality."""
    if type(left) is not type(right) or left.comparison_profile != right.comparison_profile:
        return False
    if (
        isinstance(left, CandidateAcquisitionEvaluationBasis)
        or isinstance(right, CandidateAcquisitionEvaluationBasis)
    ) and (
        type(left) is not type(right)
        or type(left)
        not in (CandidateAcquisitionEvaluationBasis, CandidateAcquisitionEvaluationBasisV2)
        or left.comparison_profile != right.comparison_profile
    ):
        return False
    return (
        left.predicate_provenance == right.predicate_provenance == "recomputed"
        and bytes.fromhex(left.effective_native_values_hex)
        == bytes.fromhex(right.effective_native_values_hex)
    )


def recompute_candidate_acquisition_basis_values(
    *,
    artifact_store: CoreJSONArtifactStore,
    problem: DesignProblem,
    preparation_inputs: CandidateSourceBasisInputs,
    predecessors: tuple[CandidateSourceBasisPredecessor, ...],
    prior: ResolvedAcquisitionEvaluation | None,
    prepared_n5_configuration: PreparedJointSimulationConfiguration | None,
    fresh_limit_usd: Decimal,
    global_limit_usd: Decimal,
    selected_data_snapshot_ref: ArtifactRef | None = None,
    selected_world_model_ref: ArtifactRef | None = None,
    historical_read_only: bool = False,
    basis_version: Literal["1.0", "2.0"] = "1.0",
    current_n5_controller: JointSimulationHorizonController | None = None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Recompute supported candidate values without asserting source authority.

    The caller must independently establish the selected action and predecessor
    chain. Historical mode reads a prior witness only; live retention additionally
    requires current implementation reconciliation and a native/SQL fence.
    """
    if basis_version == "2.0":
        return recompute_candidate_acquisition_basis_values_v2(
            artifact_store=artifact_store,
            problem=problem,
            preparation_inputs=preparation_inputs,
            predecessors=predecessors,
            prior=prior,
            prepared_n5_configuration=prepared_n5_configuration,
            selected_data_snapshot_ref=selected_data_snapshot_ref,
            selected_world_model_ref=selected_world_model_ref,
            historical_read_only=historical_read_only,
            current_n5_controller=current_n5_controller,
        )
    if basis_version != "1.0":
        return {}, ("candidate_evaluation_basis_version_unsupported",)
    from polisyos.runtime.quality.candidate_source_basis import (
        prepare_candidate_source_basis_values,
    )
    from polisyos.runtime.quality.generation_source import candidate_scenario_semantic_values

    values: dict[str, object] = {}
    try:
        if (
            type(prepared_n5_configuration) is not PreparedJointSimulationConfiguration
            or not isinstance(fresh_limit_usd, Decimal)
            or not isinstance(global_limit_usd, Decimal)
            or not fresh_limit_usd.is_finite()
            or not global_limit_usd.is_finite()
            or fresh_limit_usd < 0
            or global_limit_usd < 0
        ):
            raise ValueError("candidate_evaluation_configuration_not_established")
        if type(prior) is not ResolvedAcquisitionEvaluation:
            raise ValueError("candidate_evaluation_prior_execution_not_established")
        prepared = prepare_candidate_source_basis_values(
            store=artifact_store,
            problem=problem,
            inputs=preparation_inputs,
            data_snapshot_ref=selected_data_snapshot_ref,
            world_model_ref=selected_world_model_ref,
            predecessors=predecessors,
        )
        if prepared.predicate_provenance != "recomputed" or prepared.reason_codes:
            raise ValueError(
                prepared.reason_codes[0]
                if prepared.reason_codes
                else "candidate_evaluation_preparation_not_established"
            )
        actual = selected_data_snapshot_ref is not None or selected_world_model_ref is not None
        witness = (
            read_n5_execution_implementation_witness(
                prior.result, input_ref=prior.selected.n5_input_ref
            )
            if historical_read_only
            else reconcile_live_n5_implementation(
                prior.result, input_ref=prior.selected.n5_input_ref
            )
        )
        if witness.predicate_provenance != "recomputed":
            reason = (
                "n5_prior_live_implementation_not_established"
                if historical_read_only
                else "candidate_evaluation_implementation_not_established"
            )
            raise ValueError(reason)
        configuration = _exact_native_content(prepared_n5_configuration)
        if actual and exact_n5_content_bytes(witness.consumed_configuration_values) != (
            exact_n5_content_bytes(configuration)
        ):
            raise ValueError("candidate_evaluation_configuration_not_consumed")
        profile = prior.input_record.profile if actual else preparation_inputs.configured_profile
        values = {
            "design_problem": problem,
            "stable_proposal": candidate_scenario_semantic_values(
                stable_subject_ref=prior.source.stable_subject_ref,
                proposal=prior.source.proposal,
                candidate=prior.source.candidate,
                profile=profile,
            ),
            **prepared.effective_values,
            "actual_live_implementation": witness.implementation,
            "n5_execution_configuration": configuration,
            # The separately verified action/window caps govern whether new
            # work may run. They are not numerical inputs consumed by this
            # N5, and changed cheap scheduling must not change its result.
            "skipped_execution_scope": "configured_single_candidate_n4_and_ncm_n5_only",
            "current_continuation_policy": "actual_grounding_value_voi_requirement_rerun",
        }
        exact_n5_content_bytes(values)
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        return values, (str(getattr(exc, "code", None) or exc),)
    return values, ()


def _candidate_v5_numerical_request_facets(
    *, prior: ResolvedAcquisitionEvaluation, problem: DesignProblem, rule: object
) -> dict[str, object]:
    """Rebuild the canonical V5 builder's non-config request facets."""
    from polisyos.runtime.quality.generation_cycle import (
        JointSimulationPort,
        _value_outcome_variable,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest

    # This exact V5 builder supplies the first group and leaves the second
    # group at constructor defaults. Fail closed on any new request field.
    supplied = {
        "world_model_record_ref",
        "world_model_record",
        "intervention_atoms",
        "selected_outcomes",
        "horizon",
        "engine_plan",
        "baseline_state",
        "comparator_refs",
        "budget_ref",
        "seed",
        "replications",
    }
    defaulted = {
        "evidence_state",
        "comparator_profile",
        "coupling_graph",
        "world_credal_state_before",
        "candidate_intent",
        "member_basis",
        "source_candidate_relationship",
        "composition_status",
        "composition_limitation_code",
        "child_to_parent_refinement_status",
        "child_to_parent_refinement_limitation_code",
    }
    if supplied & defaulted or supplied | defaulted != set(JointSimulationRequest.model_fields):
        raise ValueError("candidate_evaluation_v5_request_census_not_established")
    atom = prior.input_record.materialization.derived_n5_atom
    outcome = _value_outcome_variable(prior.source.candidate, problem)
    if not outcome:
        raise ValueError("candidate_evaluation_numerical_outcome_not_established")
    variable_map = JointSimulationPort._joint_simulation_variable_map(
        atoms=(atom,), outcome=outcome, raw_hint=None
    )
    return {
        "numerical_atom": {
            "operator_kind": atom.operator_kind,
            "target_world_slots": atom.target_world_slots,
            "causal_do_expr": atom.causal_do_expr,
            "outcome_variable": outcome,
            "variable_map": variable_map,
            "current_rule": rule,
        },
        "n5_request_defaults": {
            name: JointSimulationRequest.model_fields[name].get_default(call_default_factory=True)
            for name in sorted(defaulted)
        },
    }


def recompute_candidate_acquisition_basis_values_v2(
    *,
    artifact_store: CoreJSONArtifactStore,
    problem: DesignProblem,
    preparation_inputs: CandidateSourceBasisInputs,
    predecessors: tuple[CandidateSourceBasisPredecessor, ...],
    prior: ResolvedAcquisitionEvaluation | None,
    prepared_n5_configuration: PreparedJointSimulationConfiguration | None,
    selected_data_snapshot_ref: ArtifactRef | None = None,
    selected_world_model_ref: ArtifactRef | None = None,
    historical_read_only: bool = False,
    current_n5_controller: JointSimulationHorizonController | None = None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Recompute candidate numerical identity with a current, completed N5 seam.

    A successful comparison establishes only equality of this declared basis.
    The caller separately verifies current use, semantic and evidence bindings,
    and must never treat this candidate observation as protected authority.
    """
    from polisyos.runtime.quality.candidate_source_basis import (
        prepare_candidate_source_numerical_basis_values_v2,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        read_candidate_n5_declared_implementation,
        reconcile_candidate_n5_declared_implementation,
    )

    try:
        if type(prior) is not ResolvedAcquisitionEvaluation:
            raise ValueError("candidate_evaluation_prior_execution_not_established")
        if type(prepared_n5_configuration) is not PreparedJointSimulationConfiguration:
            raise ValueError("candidate_evaluation_configuration_not_established")
        prepared = prepare_candidate_source_numerical_basis_values_v2(
            store=artifact_store,
            problem=problem,
            inputs=preparation_inputs,
            predecessors=predecessors,
            data_snapshot_ref=selected_data_snapshot_ref,
            world_model_ref=selected_world_model_ref,
        )
        if prepared.predicate_provenance != "recomputed" or prepared.reason_codes:
            raise ValueError(
                prepared.reason_codes[0]
                if prepared.reason_codes
                else "candidate_evaluation_preparation_not_established"
            )
        implementation_reader = (
            read_candidate_n5_declared_implementation
            if historical_read_only
            else reconcile_candidate_n5_declared_implementation
        )
        expected_request = rebuild_selected_candidate_n5_request(
            store=artifact_store,
            input_ref=prior.selected.n5_input_ref,
            run_id=prior.selected.evaluation_run_id,
            job_id=prior.selected.evaluation_job_id,
            tenant_id=prior.input_record.tenant_id,
            cell_id=prior.input_record.cell_id,
        )
        reader_args = {
            "input_ref": prior.selected.n5_input_ref,
            "prepared_configuration": prepared_n5_configuration,
            "expected_request": expected_request,
        }
        if historical_read_only:
            identity = implementation_reader(prior.result, **reader_args)
        else:
            identity = reconcile_candidate_n5_declared_implementation(
                prior.result, **reader_args, current_n5_controller=current_n5_controller
            )
        if (
            type(identity) is not dict
            or set(identity) != {"content_image", "execution_profile", "callable_identity"}
            or any(value is None for value in identity.values())
        ):
            raise ValueError("candidate_evaluation_identity_not_established")
        numerical_request = _candidate_v5_numerical_request_facets(
            prior=prior, problem=problem, rule=preparation_inputs.configured_profile.rule
        )
        values = {
            **prepared.effective_values,
            **numerical_request,
            "n5_execution_configuration": _exact_native_content(prepared_n5_configuration),
            "n5_declared_implementation": identity,
        }
        exact_n5_content_bytes(values)
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        return {}, (str(getattr(exc, "code", None) or exc),)
    return values, ()


def replay_candidate_acquisition_basis_for_history(
    *,
    artifact_store: CoreJSONArtifactStore,
    problem: DesignProblem,
    basis: CandidateAcquisitionEvaluationBasis,
    predecessors: tuple[CandidateSourceBasisPredecessor, ...],
    selected_evaluation: ResolvedAcquisitionEvaluation | None,
    fresh_limit_usd: Decimal,
    global_limit_usd: Decimal,
) -> CandidateAcquisitionEvaluationBasis:
    """Replay an owner-selected candidate basis without claiming current authority.

    The caller must first independently resolve the bounded route, action,
    ledger and predecessor chain. Historical N5 provenance is reopened through
    its own selected witness; this does not admit another execution or establish
    the present catalog, lease or loaded implementation. A blocked basis may
    replay against an actual historical N5 result while retaining no selected
    evaluation claim on the basis itself.
    """
    if type(basis) not in (
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationBasisV2,
    ):
        raise TypeError("candidate_evaluation_history_basis_untyped")
    if basis.basis_role == "evaluated":
        if type(
            selected_evaluation
        ) is not ResolvedAcquisitionEvaluation or not _candidate_model_values_same(
            basis.evaluation, selected_evaluation.selected
        ):
            raise ValueError("candidate_evaluation_history_selected_n5_mismatch")
    elif basis.basis_role == "blocked" and basis.evaluation is not None:
        raise ValueError("candidate_evaluation_history_blocked_has_selected_n5")
    common = {
        "artifact_store": artifact_store,
        "problem": problem,
        "preparation_inputs": basis.preparation_inputs,
        "predecessors": predecessors,
        "prior": selected_evaluation,
        "prepared_n5_configuration": basis.prepared_n5_configuration,
        "selected_data_snapshot_ref": basis.selected_data_snapshot_ref,
        "selected_world_model_ref": basis.selected_world_model_ref,
        "historical_read_only": True,
    }
    if type(basis) is CandidateAcquisitionEvaluationBasisV2:
        values, reasons = recompute_candidate_acquisition_basis_values_v2(**common)
    else:
        values, reasons = recompute_candidate_acquisition_basis_values(
            **common, fresh_limit_usd=fresh_limit_usd, global_limit_usd=global_limit_usd
        )
    if (
        type(basis) is CandidateAcquisitionEvaluationBasisV2
        and basis.predicate_provenance == "not_established"
        and basis.reason_codes
        and bytes.fromhex(basis.effective_native_values_hex) == exact_n5_content_bytes({})
        and not reasons
    ):
        # A historical read can establish the selected old observation, not
        # reconstruct why the then-current implementation was incomparable.
        # Preserve only the recorded refusal; this branch grants no equality.
        return basis
    if (
        basis.predicate_provenance != ("not_established" if reasons else "recomputed")
        or basis.reason_codes != reasons
        or exact_n5_content_bytes(values) != bytes.fromhex(basis.effective_native_values_hex)
    ):
        raise ValueError("candidate_evaluation_history_basis_owner_replay_mismatch")
    return basis


def _declaration_meaning(declaration: BaseModel, profile: BaseModel) -> dict[str, object]:
    """Separate the exact verified profile envelope from full declaration meaning."""
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )

    if (
        type(declaration) is not CandidateSimulationSyntheticModelDeclarationV1
        or type(profile) is not CandidateSimulationScenarioProfile
        or declaration.profile_config_ref != candidate_simulation_profile_ref(profile)
        or declaration.profile_content_hash != profile.content_hash
        or declaration.profile_selection_ref != profile.profile_selection_ref
    ):
        raise ValueError("acquisition_declared_model_profile_relation_not_established")
    # These three fields are independently reconciled occurrence bindings above
    # and by the normal selected declaration/NCM reader. Every other present or
    # future declaration field remains part of the exact effective quantity.
    envelope = {"profile_config_ref", "profile_content_hash", "content_hash"}
    return {
        name: getattr(declaration, name)
        for name in type(declaration).model_fields
        if name not in envelope
    }


def _context_input_meaning(inputs: BaseModel) -> dict[str, object]:
    """Keep every context input; its world is replaced only by owned world values."""
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextInputs

    if type(inputs) is not CandidateSimulationContextInputs:
        raise TypeError("acquisition_context_inputs_untyped")
    return {
        name: getattr(inputs, name)
        for name in type(inputs).model_fields
        if name != "world_model_record"
    }


class _BasisContext(Protocol):
    artifact_store: CoreJSONArtifactStore


class _BasisScope(Protocol):
    tenant_id: str
    cell_id: str
    run_id: str
    design_problem_basis: DesignProblem


def _foundry_binding_numerical_values(rule: object) -> dict[str, object]:
    """Project the complete Foundry rule census onto its numerical roles."""
    from polisyos.core.contracts import FoundryInputBindingRule

    expected = {
        "binding_id",
        "source_path",
        "target_slot_id",
        "required",
        "default_value",
        "transforms",
        "notes",
    }
    if (
        set(FoundryInputBindingRule.model_fields) != expected
        or not isinstance(rule, dict)
        or set(rule) != expected
    ):
        raise ValueError("acquisition_numerical_rule_census_not_established")
    notes = rule["notes"]
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise ValueError("acquisition_numerical_rule_notes_not_established")
    return {name: rule[name] for name in expected - {"notes"}}


def _ordinary_numerical_binding_rules(
    rules: list[FoundryInputBindingRule], *, owned_target_slot: str
) -> tuple[dict[str, object], ...]:
    """Preserve the ordinary owner's acquired and retained rule distinctions."""
    return tuple(
        {
            "acquired_owner_values"
            if rule.target_slot_id == owned_target_slot
            else "retained_rule": _foundry_binding_numerical_values(rule.model_dump(mode="json"))
        }
        for rule in rules
    )


def recompute_acquisition_basis_values(
    *,
    bridge: _BasisContext,
    closure: _BasisScope,
    prepared: object,
    prior: ResolvedAcquisitionEvaluation | None,
    actual_evaluation: bool,
    _historical_read_only: bool = False,
    basis_version: Literal["1.0", "2.0"] = "1.0",
    current_n5_controller: JointSimulationHorizonController | None = None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Resolve every supported consumed facet through its actual producer owner.

    ``actual_evaluation`` chooses the read side of those same owners. The bridge
    invokes it only for its freshly verified selected/re-entry result. No caller
    completeness, method label, marker, source hash or supplied mapping is an
    admission. Unsupported profiles return exact reasons and cannot retain.
    """
    from polisyos.foundry.data_plane import load_input_bindings
    from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
    from polisyos.ir import prepare_ncm_spec_selected_values
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionCandidatePreparation
    from polisyos.runtime.quality.candidate_simulation import prepare_candidate_n5_request_values
    from polisyos.runtime.quality.data_state_substrate import (
        acquired_observation_binding_rule_values,
        prepare_acquired_observation_semantic_values,
        prepare_acquired_observation_world_semantic_values,
        read_acquired_observation_binding_rule,
        read_acquired_observation_semantic_values,
        read_acquired_observation_world_semantic_values,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        candidate_scenario_semantic_values,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    if type(prepared) is not AcquisitionCandidatePreparation:
        raise TypeError("acquisition_evaluation_preparation_not_owner_typed")
    reasons: list[str] = []
    values: dict[str, object] = {}
    try:
        # Keep known intent bound even if another facet is NE. Unsupported
        # values are handled inside this typed-NE boundary, never before it.
        values["n5_execution_configuration"] = _exact_native_content(
            prepared.n5_execution_configuration
        )
        if prepared.n5_execution_configuration is None:
            reasons.extend(prepared.n5_configuration_reason_codes)
            raise ValueError("n5_configuration_preparation_not_established")
        if prior is None:
            raise ValueError("acquisition_prior_execution_not_observed")
        source = prior.source
        profile = prior.input_record.profile if actual_evaluation else prepared.configured_profile
        if actual_evaluation:
            producer_world = profile.context_inputs.world_model_record
            views = world_model_artifact_views(producer_world)
            state = load_state_snapshot(
                bridge.artifact_store, snapshot_ref=views.bound_state_snapshot_ref
            )
            bindings = load_input_bindings(bridge.artifact_store, views.input_bindings_ref)
            owned_rule = read_acquired_observation_binding_rule(
                bridge.artifact_store,
                views.data_snapshot_ref,
            )
            observation = read_acquired_observation_semantic_values(
                bridge.artifact_store,
                views.data_snapshot_ref,
            )
            world = read_acquired_observation_world_semantic_values(
                store=bridge.artifact_store,
                world_model_record=producer_world,
                registry_bundle_ref=views.registry_bundle_ref,
            )
            declaration, ncm = GenerationSourceRepository(
                bridge.artifact_store
            ).load_candidate_declared_ncm(
                declaration_ref=prior.input_record.model_declaration_ref,
                ncm_ref=prior.input_record.ncm_ref,
                expected_profile=profile,
                expected_run_id=closure.run_id,
                expected_job_id=source.job_id,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
            )
            n5 = prior.input_record.n5
            rules = list(bindings.rules)
            effective_rule = observation["binding_rule"]
        else:
            state = prepared.prospective_values.materialized_state
            rules = list(prepared.prospective_values.effective_rules)
            owned_rule = prepared.preparation.foundry_binding_rule
            observation = prepare_acquired_observation_semantic_values(prepared.preparation)
            world = prepare_acquired_observation_world_semantic_values(
                store=bridge.artifact_store,
                base_world_model_record=prepared.base_world,
                data_preparation=prepared.preparation,
                prepared_state_values=prepared.prospective_values,
                registry_bundle_ref=world_model_artifact_views(
                    prepared.base_world
                ).registry_bundle_ref,
                substrate_registry=prepared.configured_profile.context_inputs.substrate_registry,
            )
            model_values = prepared.prospective_model
            ncm = model_values.ncm_spec
            n5 = model_values.n5_config
            # Same exact constructor as the actual acquired-context producer.
            # It needs a real world for late-bound profile refs only. The
            # declaration meaning below retains original owner meaning while
            # replacing only its actual refreshed numerical inputs.
            declaration = model_values.original_declaration
            effective_rule = acquired_observation_binding_rule_values(prepared.preparation)
        if world["predicate_provenance"] != "recomputed":
            reasons.extend(str(reason) for reason in world["reason_codes"])
        # Verify the exact owner rule before replacing its generated report
        # occurrence with the owner's effective projection. Retained rules are
        # never stripped or interpreted in Runtime.
        target_rules = tuple(
            rule for rule in rules if rule.target_slot_id == owned_rule.target_slot_id
        )
        if target_rules != (owned_rule,):
            raise ValueError("acquisition_evaluation_owned_rule_relation_mismatch")
        rule_values = tuple(
            {"acquired_owner_values": effective_rule}
            if rule.target_slot_id == owned_rule.target_slot_id
            else {"retained_rule": rule}
            for rule in rules
        )
        prepared_configuration = _exact_native_content(prepared.n5_execution_configuration)
        if basis_version == "2.0":
            from polisyos.runtime.quality.n5_candidate_content import (
                read_candidate_n5_declared_implementation,
                reconcile_candidate_n5_declared_implementation,
            )

            reader = (
                read_candidate_n5_declared_implementation
                if _historical_read_only
                else reconcile_candidate_n5_declared_implementation
            )
            expected_request = rebuild_selected_candidate_n5_request(
                store=bridge.artifact_store,
                input_ref=prior.selected.n5_input_ref,
                run_id=prior.selected.evaluation_run_id,
                job_id=prior.selected.evaluation_job_id,
                tenant_id=prior.input_record.tenant_id,
                cell_id=prior.input_record.cell_id,
            )
            reader_args = {
                "input_ref": prior.selected.n5_input_ref,
                "prepared_configuration": prepared.n5_execution_configuration,
                "expected_request": expected_request,
            }
            if _historical_read_only:
                implementation = reader(prior.result, **reader_args)
            else:
                implementation = reconcile_candidate_n5_declared_implementation(
                    prior.result, **reader_args, current_n5_controller=current_n5_controller
                )
            consumed_configuration = prepared_configuration
        else:
            witness = (
                read_n5_execution_implementation_witness(
                    prior.result,
                    input_ref=prior.selected.n5_input_ref,
                )
                if _historical_read_only
                else reconcile_live_n5_implementation(
                    prior.result,
                    input_ref=prior.selected.n5_input_ref,
                )
            )
            if witness.predicate_provenance != "recomputed":
                raise ValueError("acquisition_prior_implementation_was_not_established")
            consumed_configuration = witness.consumed_configuration_values
            prepared_configuration = _exact_native_content(prepared.n5_execution_configuration)
            if actual_evaluation and exact_n5_content_bytes(
                consumed_configuration
            ) != exact_n5_content_bytes(prepared_configuration):
                raise ValueError("acquisition_evaluation_configuration_not_consumed")
            implementation = witness.implementation
        declaration_meaning = _declaration_meaning(declaration, profile)
        if not actual_evaluation:
            from dataclasses import fields

            declaration_meaning.update(
                {
                    field.name: getattr(
                        prepared.prospective_model.declared_model_values, field.name
                    )
                    for field in fields(prepared.prospective_model.declared_model_values)
                }
            )
        values = {
            "design_problem": closure.design_problem_basis,
            "stable_proposal": candidate_scenario_semantic_values(
                stable_subject_ref=source.stable_subject_ref,
                proposal=source.proposal,
                candidate=source.candidate,
                profile=profile,
            ),
            "controlled_observation": observation,
            "world": world["effective_values"],
            "foundry_state": state_snapshot_value_projection(state),
            "applied_rules": rule_values,
            "selected_native_ncm": prepare_ncm_spec_selected_values(ncm).value_bytes,
            "n5_request_values": prepare_candidate_n5_request_values(n5),
            "declared_model": declaration_meaning,
            "context_inputs": _context_input_meaning(profile.context_inputs),
            "profile_schema": profile.schema_version,
            "profile_purpose": profile.purpose,
            "profile_limitations": profile.limitations,
            "actual_live_implementation": implementation,
            "n5_execution_configuration": consumed_configuration
            if actual_evaluation
            else prepared_configuration,
            "skipped_execution_scope": "configured_single_candidate_n4_and_ncm_n5_only",
            "current_continuation_policy": "actual_grounding_value_voi_requirement_rerun",
        }
        if basis_version == "2.0":
            from polisyos.runtime.quality.candidate_simulation import (
                prepare_candidate_n5_request_projection_v2,
            )

            values = {
                "foundry_state": values["foundry_state"],
                "applied_rules": _ordinary_numerical_binding_rules(
                    rules, owned_target_slot=owned_rule.target_slot_id
                ),
                "selected_native_ncm": values["selected_native_ncm"],
                "declared_model": values["declared_model"],
                "n5_request_values": prepare_candidate_n5_request_projection_v2(n5).numerical,
                **_candidate_v5_numerical_request_facets(
                    prior=prior, problem=closure.design_problem_basis, rule=profile.rule
                ),
                "n5_execution_configuration": prepared_configuration,
                "n5_declared_implementation": implementation,
            }
        elif basis_version != "1.0":
            raise ValueError("acquisition_evaluation_basis_version_unsupported")
        # Walk the full native quantity now. Unknown Any/native fields are not
        # encoded with repr(), omitted, or accepted through a caller marker.
        exact_n5_content_bytes(values)
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        reasons.append(str(getattr(exc, "code", None) or exc))
    return values, tuple(dict.fromkeys(reasons))


def issue_acquisition_evaluation_basis(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    growth_receipt_ref: ArtifactRef,
    admitted_source_ref: ArtifactRef,
    prepared: object,
    prior: ResolvedAcquisitionEvaluation | None,
    actual_evaluation: bool,
    basis_version: Literal["1.0", "2.0"] = "1.0",
    current_n5_controller: JointSimulationHorizonController | None = None,
) -> AcquisitionEvaluationBasis:
    """Issue only after actual owner recomputation; unsupported facets stay typed."""
    values, reasons = recompute_acquisition_basis_values(
        bridge=bridge,
        closure=closure,
        prepared=prepared,
        prior=prior,
        actual_evaluation=actual_evaluation,
        basis_version=basis_version,
        current_n5_controller=current_n5_controller,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionCandidatePreparation

    if type(prepared) is not AcquisitionCandidatePreparation:
        raise TypeError("acquisition_evaluation_preparation_not_owner_typed")
    encoded = exact_n5_content_bytes(values)
    selectors = AcquisitionBasisPreparationInputs(
        configured_profile=prepared.configured_profile,
        original_model_declaration=prepared.prospective_model.original_declaration,
        base_data_snapshot_ref=prepared.preparation.base_data_snapshot_ref,
        receipt_ref=prepared.preparation.receipt_ref,
        passport_ref=prepared.preparation.observation_projection.passport_ref,
        boundary_candidate_ref=prepared.passport.semantic_boundary_candidate_ref,
        source_ref=admitted_source_ref,
        observation_id=prepared.preparation.selected_observation_id,
        slot_binding=prepared.preparation.selected_profile,
        transaction_time=prepared.transaction_time.isoformat(),
        preparation_job_id=prepared.current_job.job_id,
        n5_execution_configuration=prepared.n5_execution_configuration,
        n5_configuration_reason_codes=prepared.n5_configuration_reason_codes,
    )
    payload = {
        "schema_version": "AcquisitionEvaluationBasis@" + basis_version,
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": (
            "controlled_acquired_observation_ncm_v1"
            if basis_version == "1.0"
            else "controlled_acquired_observation_numerical_v2"
        ),
        "tenant_id": closure.tenant_id,
        "cell_id": closure.cell_id,
        "run_id": closure.run_id,
        "source_job_id": closure.source_job_id,
        "design_problem_ref": closure.design_problem_basis_ref,
        "candidate_id": closure.source_cycle.selected_candidate_ref,
        "growth_receipt_ref": growth_receipt_ref.model_dump(mode="json"),
        "admitted_source_ref": admitted_source_ref.model_dump(mode="json"),
        "evaluation": prior.selected.model_dump(mode="json")
        if actual_evaluation and prior
        else None,
        "preparation_inputs": selectors.model_dump(mode="json"),
        "predicate_provenance": "not_established" if reasons else "recomputed",
        "reason_codes": list(reasons),
        "effective_native_values_hex": encoded.hex(),
        "effective_values_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
    }
    record_type = AcquisitionEvaluationBasis
    if basis_version == "2.0":
        payload["closure_residuals"] = list(CANDIDATE_N5_CLOSURE_RESIDUALS_V2)
        payload["observed_admission"] = False
        payload["publication_authority"] = False
        record_type = AcquisitionEvaluationBasisV2
    return record_type.model_validate(
        {
            **payload,
            "content_hash": exact_n5_content_hash(payload),
        }
    )


def read_acquisition_retained_continuation(
    *,
    store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    ref: ArtifactRef,
    decision: AcquisitionEvaluationDecision,
    terminal: AcquisitionRouteLoopReceiptV2,
) -> AcquisitionRetainedContinuation:
    """Load the strict actual current-consequence owner without an import cycle."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        read_acquisition_retained_continuation as read_owned,
    )

    return read_owned(
        store=store, event_log=event_log, ref=ref, decision=decision, terminal=terminal
    )


@dataclass(frozen=True)
class _HistoricalBasisContext:
    artifact_store: CoreJSONArtifactStore
    control_store: ControlPlaneStore


@dataclass(frozen=True)
class _HistoricalBasisScope:
    tenant_id: str
    cell_id: str
    run_id: str
    design_problem_basis: DesignProblem


def replay_acquisition_basis_for_history(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    basis: AcquisitionEvaluationBasis,
    prior_evaluation: ResolvedAcquisitionEvaluation,
    control_service: object | None = None,
) -> AcquisitionEvaluationBasis:
    """Recompute a historical basis from actual bytes without granting current reuse.

    This path never emits a terminal or a new comparison permission. Historical
    implementation observations are resolved from their actual selected N5
    source, while the current mutation path still requires the live producer
    observation and exact present loaded bindings. Native currentness is not
    inferred from the immutable admission chain.
    """
    from pathlib import Path

    from polisyos.core import contracts
    from polisyos.foundry.data_plane import load_input_bindings, prepare_json_input_binding_values
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        read_historical_acquisition_growth,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionCandidatePreparation
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
    )
    from polisyos.runtime.quality.data_state_substrate import (
        replay_acquired_observation_snapshot_preparation,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    del control_service  # No present lease/configuration is used as a historical permit.
    selected = prior_evaluation.selected
    if (
        selected.candidate_id != basis.candidate_id
        or selected.design_problem_ref != basis.design_problem_ref
        or prior_evaluation.source.run_id != basis.run_id
        or prior_evaluation.source.tenant_id != basis.tenant_id
        or prior_evaluation.source.cell_id != basis.cell_id
    ):
        raise ValueError("acquisition_historical_basis_evaluation_scope_mismatch")
    if basis.evaluation is not None and basis.evaluation.model_dump(exclude={"basis_ref"}) != (
        selected.model_dump(exclude={"basis_ref"})
    ):
        raise ValueError("acquisition_historical_basis_occurrence_mismatch")
    growth = read_historical_acquisition_growth(
        artifact_store=artifact_store,
        event_log=event_log,
        ref=basis.growth_receipt_ref,
        tenant_id=basis.tenant_id,
        cell_id=basis.cell_id,
        run_id=basis.run_id,
        source_job_id=basis.source_job_id,
    )
    inputs = basis.preparation_inputs
    if inputs.source_ref != basis.admitted_source_ref or (
        growth.activation.overlay_admission_receipt_ref != inputs.receipt_ref
        or growth.activation.passport_ref != inputs.passport_ref
    ):
        raise ValueError("acquisition_historical_basis_admission_selector_mismatch")
    preparation = replay_acquired_observation_snapshot_preparation(
        artifact_store,
        base_data_snapshot_ref=inputs.base_data_snapshot_ref,
        receipt_ref=inputs.receipt_ref,
        passport_ref=inputs.passport_ref,
        boundary_candidate_ref=inputs.boundary_candidate_ref,
        source_ref=inputs.source_ref,
        observation_id=inputs.observation_id,
        slot_binding=inputs.slot_binding,
        transaction_time=datetime.fromisoformat(inputs.transaction_time),
        activation=growth.activation,
    )
    configured = inputs.configured_profile
    views = world_model_artifact_views(configured.context_inputs.world_model_record)
    if views.data_snapshot_ref != inputs.base_data_snapshot_ref:
        raise ValueError("acquisition_historical_basis_configured_base_mismatch")
    base_bindings = load_input_bindings(artifact_store, views.input_bindings_ref)
    rules = [
        rule
        for rule in base_bindings.rules
        if rule.target_slot_id != preparation.foundry_binding_rule.target_slot_id
    ]
    rules.append(preparation.foundry_binding_rule)
    prepared_values = prepare_json_input_binding_values(
        artifact_store,
        payload_json=preparation.payload_json,
        registry_bundle_ref=views.registry_bundle_ref,
        rules=rules,
    )
    owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(configured,),
        model_declarations=(inputs.original_model_declaration,),
        store=artifact_store,
    )
    model_values = owner.prepare_model_values_for_acquired_state(
        problem=prior_evaluation.source.problem,
        profile_selection_ref=configured.profile_selection_ref,
        source_world_model=configured.context_inputs.world_model_record,
        state=prepared_values.materialized_state,
    )
    job = control_store.get_job(inputs.preparation_job_id)
    if job is None or job.run_id != basis.run_id:
        raise ValueError("acquisition_historical_basis_preparation_job_missing")
    prepared = AcquisitionCandidatePreparation(
        n5_execution_configuration=inputs.n5_execution_configuration,
        n5_configuration_reason_codes=inputs.n5_configuration_reason_codes,
        configured_profile=configured,
        base_world=configured.context_inputs.world_model_record,
        passport=AdmissionPassport.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=artifact_store,
                ref=inputs.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        ),
        current_job=job,
        preparation=preparation,
        prospective_values=prepared_values,
        prospective_model=model_values,
        # This readonly path does not use scratch or emit data/world/context.
        workspace_dir=Path(
            configured.context_inputs.world_model_record.fabric_world_ref.snapshot_root
        ),
        transaction_time=datetime.fromisoformat(inputs.transaction_time),
        substrate_registry_ref=views.substrate_registry_ref,
    )
    values, reasons = recompute_acquisition_basis_values(
        bridge=_HistoricalBasisContext(artifact_store, control_store),
        closure=_HistoricalBasisScope(
            basis.tenant_id, basis.cell_id, basis.run_id, prior_evaluation.source.problem
        ),
        prepared=prepared,
        prior=prior_evaluation,
        actual_evaluation=basis.evaluation is not None,
        _historical_read_only=True,
        basis_version="2.0" if type(basis) is AcquisitionEvaluationBasisV2 else "1.0",
    )
    encoded = exact_n5_content_bytes(values)
    if reasons or encoded != bytes.fromhex(basis.effective_native_values_hex):
        raise ValueError("acquisition_historical_basis_owner_replay_mismatch:" + ",".join(reasons))
    return basis
