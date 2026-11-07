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
        AcquisitionCandidateRouteLoopReceipt,
        AcquisitionRouteLoopReceiptV2,
        VerifiedAcquisitionRouteClosure,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
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
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationResult
    from polisyos.scientist.orchestration.engine.budget_ledger import (
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
    encoded = exact_n5_content_bytes(values)
    payload = {
        "schema_version": "CandidateAcquisitionEvaluationBasis@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": "candidate_source_complete_native_values_v1",
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
    return CandidateAcquisitionEvaluationBasis.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )


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
    payload = {
        "schema_version": "CandidateAcquisitionEvaluationDecision@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_rule": "candidate-source-complete-native-values.v1",
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
    return CandidateAcquisitionEvaluationDecision.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )


@dataclass(frozen=True)
class ResolvedAcquisitionEvaluation:
    """Actual source/context/input/result objects reopened by their owners."""

    selected: AcquisitionSelectedEvaluation
    source: N4CandidateScenarioSourceRecordV3
    input_record: CandidateSimulationN5InputV5
    execution: CandidateSimulationExecutionV5
    result: JointSimulationResult
    handoff: CandidateSimulationContextHandoff


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
    before any further effect.
    """

    head: AcquisitionActionHeadRecord
    terminal_ref: ArtifactRef
    terminal: AcquisitionCandidateExperimentTerminalReceipt
    origin: VerifiedCandidateExperimentOrigin
    phase_chain: tuple[VerifiedAcquisitionActionPhase, ...]
    action: CandidateAcquisitionActionReceipt
    source: CandidateAcquisitionSource
    budget_window: BudgetLedgerReentryBudgetWindow
    decision: CandidateAcquisitionEvaluationDecision | None
    current_basis: CandidateAcquisitionEvaluationBasis | None
    selected_basis: CandidateAcquisitionEvaluationBasis | None
    evaluation: ResolvedAcquisitionEvaluation | None
    reentry: CandidateSourceReentryReceipt | None
    continuation: CandidateAcquisitionRetainedContinuation | None
    frontier_before: AcquisitionEvaluationFrontierRecord | None
    frontier_after: AcquisitionEvaluationFrontierRecord | None
    reentry_evaluation: ResolvedAcquisitionEvaluation | None = None


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
    source, execution, input_record = repository._resolve_selected_candidate_simulation_v5_pair(
        source_ref=source_ref,
        execution_ref=execution_ref,
        input_ref=input_ref,
        expected_run_id=run_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
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
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    result = load_joint_simulation_result(
        result_ref,
        store=artifact_store,
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

    if type(record) is CandidateAcquisitionEvaluationDecision:
        role = "decision"
    elif type(record) is CandidateAcquisitionEvaluationBasis:
        role = "prospective_basis" if record.basis_role == "prospective" else "outcome_basis"
    elif type(record) is CandidateAcquisitionRetainedContinuation:
        role = "retained_continuation"
    elif type(record) is CandidateRetainedPortCapture:
        role = "retained_port_capture"
    else:
        raise TypeError("candidate_evaluation_record_untyped")
    return _candidate_evaluation_role_event_id(record.candidate_action_ref, role)


def _candidate_evaluation_role_event_id(
    action_ref: ArtifactRef,
    role: Literal[
        "decision",
        "prospective_basis",
        "outcome_basis",
        "retained_continuation",
        "retained_port_capture",
    ],
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
    identity = hashlib.sha256(exact_n5_content_bytes(action_ref)).hexdigest()
    return f"evt_candidate_evaluation_{role}_{identity}"


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
    | AcquisitionRetainedContinuation,
) -> ArtifactRef:
    """Persist and reopen one strict basis/decision with its real producer event."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )

    if type(record) not in {
        AcquisitionEvaluationBasis,
        AcquisitionEvaluationDecision,
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
        AcquisitionRetainedContinuation,
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
            schema=artifacts.SchemaInfo(name=record.ARTIFACT_SCHEMA_NAME, version="1.0"),
            producer=artifacts.ProducerInfo(component=PRODUCER, version="1.0"),
            inputs=[input_ref_from_artifact_ref(ref, role=path) for path, ref in typed_refs],
        ),
        evidence_id=identity,
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner="team-runtime-quality",
        reader_contract=record.ARTIFACT_KIND + ".reader",
        reader_contract_version="1.0",
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
        if isinstance(record, (AcquisitionEvaluationBasis, CandidateAcquisitionEvaluationBasis))
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
            _candidate_evaluation_event_id(record)
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
    | type[AcquisitionRetainedContinuation],
) -> (
    AcquisitionEvaluationBasis
    | AcquisitionEvaluationDecision
    | CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture
    | AcquisitionRetainedContinuation
):
    """Resolve exact selected bytes, schema, producer and durable event scope."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )

    if record_type not in {
        AcquisitionEvaluationBasis,
        AcquisitionEvaluationDecision,
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
        AcquisitionRetainedContinuation,
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
        or manifest.artifact_schema.version != "1.0"
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
        ),
    ):
        expected_event_id = _candidate_evaluation_event_id(record)
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


def basis_exact_values_equal(
    left: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
    right: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
) -> bool:
    """Compare the complete admitted native quantity, without hash-only equality."""
    if (
        isinstance(left, CandidateAcquisitionEvaluationBasis)
        or isinstance(right, CandidateAcquisitionEvaluationBasis)
    ) and (
        type(left) is not CandidateAcquisitionEvaluationBasis
        or type(right) is not CandidateAcquisitionEvaluationBasis
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
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Recompute supported candidate values without asserting source authority.

    The caller must independently establish the selected action and predecessor
    chain. Historical mode reads a prior witness only; live retention additionally
    requires current implementation reconciliation and a native/SQL fence.
    """
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
    if type(basis) is not CandidateAcquisitionEvaluationBasis:
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
    values, reasons = recompute_candidate_acquisition_basis_values(
        artifact_store=artifact_store,
        problem=problem,
        preparation_inputs=basis.preparation_inputs,
        predecessors=predecessors,
        prior=selected_evaluation,
        prepared_n5_configuration=basis.prepared_n5_configuration,
        fresh_limit_usd=fresh_limit_usd,
        global_limit_usd=global_limit_usd,
        selected_data_snapshot_ref=basis.selected_data_snapshot_ref,
        selected_world_model_ref=basis.selected_world_model_ref,
        historical_read_only=True,
    )
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


def recompute_acquisition_basis_values(
    *,
    bridge: _BasisContext,
    closure: _BasisScope,
    prepared: object,
    prior: ResolvedAcquisitionEvaluation | None,
    actual_evaluation: bool,
    _historical_read_only: bool = False,
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
            "actual_live_implementation": witness.implementation,
            "n5_execution_configuration": consumed_configuration
            if actual_evaluation
            else prepared_configuration,
            "skipped_execution_scope": "configured_single_candidate_n4_and_ncm_n5_only",
            "current_continuation_policy": "actual_grounding_value_voi_requirement_rerun",
        }
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
) -> AcquisitionEvaluationBasis:
    """Issue only after actual owner recomputation; unsupported facets stay typed."""
    values, reasons = recompute_acquisition_basis_values(
        bridge=bridge,
        closure=closure,
        prepared=prepared,
        prior=prior,
        actual_evaluation=actual_evaluation,
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
        "schema_version": "AcquisitionEvaluationBasis@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": "controlled_acquired_observation_ncm_v1",
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
    return AcquisitionEvaluationBasis.model_validate(
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
    )
    encoded = exact_n5_content_bytes(values)
    if reasons or encoded != bytes.fromhex(basis.effective_native_values_hex):
        raise ValueError("acquisition_historical_basis_owner_replay_mismatch:" + ",".join(reasons))
    return basis
