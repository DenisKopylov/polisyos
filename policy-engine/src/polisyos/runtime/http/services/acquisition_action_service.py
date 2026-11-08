"""Run-bound acquisition route projection and deferred action composition."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core import artifacts
from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.contracts import RunCandidateSimulationN5ResultBody
from polisyos.pdc import OperationClass, OperationContract, OperationInvocationRecord
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
    AcquisitionRouteClosureError,
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
    AcquisitionRouteRecoveryRequired,
    AcquisitionSelectedEvaluation,
    CandidateExperimentTerminalHistory,
    VerifiedAcquisitionRouteClosure,
    VerifiedCandidateExperimentOrigin,
    persist_world_commit_and_reenter,
    resume_world_committed_reentry,
)
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    CANDIDATE_EXPERIMENT_ACTION_KIND,
    AgentActionAuthorityGateway,
    AgentActionAuthorityRefused,
    AgentActionIntent,
    AuthenticatedAgentActionDecisionHistory,
    agent_action_authority_scope,
    agent_action_content_hash,
    produce_agent_action_authority_decision,
    reserve_agent_external_action,
)

from .control import ControlPlaneService
from .human_decisions import HumanDecisionService

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.quality.acquisition_movement import AcquisitionMovementService
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthConfig,
        AcquisitionWorldGrowthReceipt,
    )
    from polisyos.runtime.quality.epoch_deployment import EpochDeployment

    from .control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlJobExecutionScope,
        ControlJobRecord,
    )

_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_IMPLEMENTATION_REF = "polisyos.runtime.acquisition_route_loop.owner_port.v1"


class AcquisitionActionServiceError(ValueError):
    """Typed fail-closed error from the acquisition service boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _candidate_experiment_n5_result_read_error_code(exc: Exception) -> str | None:
    """Classify a selected result read without inferring from exception text."""
    try:
        artifacts.raise_artifact_read_access_error(exc)
    except artifacts.ArtifactOwnershipError:
        return "candidate_experiment_n5_result_scope_refused"
    except PermissionError:
        return "candidate_experiment_n5_result_storage_unavailable"

    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    validation_refusal = False
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, artifacts.ArtifactUnavailableError):
            return "candidate_experiment_n5_result_storage_unavailable"
        if isinstance(current, artifacts.ArtifactOwnershipError):
            return "candidate_experiment_n5_result_scope_refused"
        if isinstance(current, OSError):
            return "candidate_experiment_n5_result_storage_unavailable"
        if isinstance(current, (TypeError, ValueError)):
            validation_refusal = True
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    if validation_refusal:
        return "candidate_experiment_n5_result_selected_view_not_established"
    return None


class AcquisitionRouteReplayPins(BaseModel):
    """Server-projected pins callers may only echo for optimistic concurrency."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_job_id: str = Field(min_length=1)
    compiled_ref: str = Field(pattern=_SHA256_PATTERN)
    compiled_content_hash: str = Field(pattern=_SHA256_PATTERN)
    terminal_event_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=_SHA256_PATTERN)
    cost_basis_hash: str = Field(pattern=_SHA256_PATTERN)


class AcquisitionRouteMutationRequest(BaseModel):
    """Strict caller fields; route facts, status, authority, and epochs are forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    route_projection_hash: str = Field(pattern=_SHA256_PATTERN)
    planner_report_hash: str = Field(pattern=_SHA256_PATTERN)
    replay_pins: AcquisitionRouteReplayPins
    idempotency_key: str = Field(min_length=1, max_length=200)
    human_decision_record_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)


class CandidateExperimentRouteReplayPins(BaseModel):
    """Exact selected source and policy views for an unknown-cost experiment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_job_id: str = Field(min_length=1)
    source_payload_ref: str = Field(pattern=_SHA256_PATTERN)
    request_content_hash: str = Field(pattern=_SHA256_PATTERN)
    compiled_ref: artifacts.ArtifactRef
    planner_report_ref: artifacts.ArtifactRef
    compiler_report_ref: artifacts.ArtifactRef
    configured_port_source_ref: artifacts.ArtifactRef
    policy_ref: artifacts.ArtifactRef
    candidate_digest: str = Field(pattern=_SHA256_PATTERN)
    predecessor_terminal_ref: artifacts.ArtifactRef | None = None

    @model_serializer(mode="wrap")
    def _preserve_predecessor_presence(  # type: ignore[no-untyped-def]  # noqa: ANN202
        self, handler: SerializerFunctionWrapHandler
    ):
        """Keep legacy absence and explicit null distinct in request-bound selectors.

        The private hook intentionally leaves its return unannotated so
        Pydantic retains this model's typed serialization schema.
        """
        payload = handler(self)
        if "predecessor_terminal_ref" not in self.model_fields_set:
            payload.pop("predecessor_terminal_ref", None)
        return payload

    @model_validator(mode="after")
    def _selected_views_required(self) -> CandidateExperimentRouteReplayPins:
        selected = (
            (self.compiled_ref, "runtime.compiled_recursive_generation_cycle"),
            (self.planner_report_ref, "runtime.acquisition_planner_report"),
            (self.compiler_report_ref, "runtime.data_requirement_compilation_report"),
            (
                self.configured_port_source_ref,
                "runtime.quality.n7_configured_candidate_port_source",
            ),
            (self.policy_ref, "runtime_quality.candidate_unpriced_acquisition_policy"),
        )
        if self.predecessor_terminal_ref is not None:
            selected += (
                (self.predecessor_terminal_ref, "runtime_quality.acquisition_route_loop_receipt"),
            )
        for ref, kind in selected:
            if (
                set(type(ref).model_fields) != set(artifacts.ArtifactRef.model_fields)
                or ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("candidate_experiment_selected_profile_required")
        return self


class CandidateExperimentRouteMutationRequest(BaseModel):
    """Optimistic pins only; permission and live action owners remain separate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    route_id: str = Field(pattern=_SHA256_PATTERN)
    replay_pins: CandidateExperimentRouteReplayPins
    idempotency_key: str = Field(min_length=1, max_length=200)
    human_decision_record_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)


class CandidateExperimentRouteExecutionRequest(BaseModel):
    """Exact persisted decision selected for one candidate-experiment execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: CandidateExperimentRouteMutationRequest
    decision_ref: str = Field(pattern=_SHA256_PATTERN)


class CandidateExperimentN5ResultProjection(BaseModel):
    """Fresh candidate-only result bound to its selected reentry terminal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    terminal_receipt_ref: artifacts.ArtifactRef
    reentry_receipt_ref: artifacts.ArtifactRef
    result_body: RunCandidateSimulationN5ResultBody
    reason_codes: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    configuration_use: Literal["not_established"] = "not_established"
    implementation_currentness: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"
    publication_authority: Literal[False] = False
    authoritative_for: tuple[Literal["api_display"], ...] = ("api_display",)
    may_not_use_for: tuple[
        Literal[
            "n5_evaluation_retention",
            "claim_authority",
            "publication_authority",
        ],
        ...,
    ] = (
        "n5_evaluation_retention",
        "claim_authority",
        "publication_authority",
    )

    @model_validator(mode="after")
    def _selected_candidate_result(self) -> CandidateExperimentN5ResultProjection:
        if any(
            ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref, kind in (
                (
                    self.terminal_receipt_ref,
                    "runtime_quality.acquisition_route_loop_receipt",
                ),
                (
                    self.reentry_receipt_ref,
                    "runtime_quality.candidate_source_reentry_receipt",
                ),
            )
        ):
            raise ValueError("candidate_experiment_n5_result_selected_ref_invalid")
        if (
            self.result_body.authority_purpose != "candidate_scenario_n5_only"
            or self.result_body.candidate_status != "candidate_unverified"
            or self.result_body.currentness_status != "not_established"
            or self.result_body.publication_authority
            or self.configuration_use != "not_established"
            or self.implementation_currentness != "not_established"
            or self.authoritative_for != ("api_display",)
            or self.may_not_use_for
            != (
                "n5_evaluation_retention",
                "claim_authority",
                "publication_authority",
            )
            or not all(code.strip() for code in (*self.reason_codes, *self.limitations))
            or len(self.reason_codes) != len(set(self.reason_codes))
            or len(self.limitations) != len(set(self.limitations))
        ):
            raise ValueError("candidate_experiment_n5_result_scope_invalid")
        return self


class CandidateExperimentPriorN5ResultProjection(BaseModel):
    """Keep a verified earlier candidate result distinct from the current action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prior_action_ref: artifacts.ArtifactRef
    prior_action_generation: int = Field(ge=1)
    n5_result: CandidateExperimentN5ResultProjection

    @model_validator(mode="after")
    def _selected_prior_action(self) -> CandidateExperimentPriorN5ResultProjection:
        if (
            self.prior_action_ref.kind != "runtime_quality.acquisition_candidate_action_receipt"
            or self.prior_action_ref.media_type != "application/json"
            or self.prior_action_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("candidate_experiment_prior_n5_result_action_ref_invalid")
        if (
            self.n5_result.result_body.artifact_ref.kind
            != "polisyos.runtime.joint_simulation_result"
            or self.n5_result.result_body.artifact_ref.manifest_profile_sha256 is None
            or self.n5_result.result_body.selected_manifest_profile_sha256
            != self.n5_result.result_body.artifact_ref.manifest_profile_sha256
        ):
            raise ValueError("candidate_experiment_prior_n5_result_selected_view_invalid")
        return self


class CandidateExperimentCurrentActionProjection(BaseModel):
    """Read-only status of the current verified candidate-experiment action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["unknown", "in_progress", "completed", "blocked"] = "unknown"
    action_generation: int | None = Field(default=None, ge=1)
    job_id: str | None = Field(default=None, min_length=1)
    job_state: Literal["pending", "running", "completed", "failed", "cancelled"] | None = None
    coarse_phase: (
        Literal["requested", "executing", "candidate_input_prepared", "terminal"] | None
    ) = None
    receipt_phase: (
        Literal[
            "requested",
            "executing",
            "outcome_selected",
            "candidate_input_reentry_pending",
            "terminal",
        ]
        | None
    ) = None
    recovery_state: Literal["none", "reentry_recovery_required", "complete"] | None = None
    selected_receipt_ref: artifacts.ArtifactRef | None = None
    terminal_outcome: (
        Literal["candidate_reentry_completed", "candidate_evaluation_retained", "candidate_blocked"]
        | None
    ) = None
    evaluation_disposition: Literal["unknown", "new", "retained", "blocked"] = "unknown"
    selected_evaluation: AcquisitionSelectedEvaluation | None = None
    candidate_n5_result: CandidateExperimentN5ResultProjection | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    prior_candidate_n5_result: CandidateExperimentPriorN5ResultProjection | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    blocker_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _projection_matches_verified_terminal(self) -> CandidateExperimentCurrentActionProjection:
        if self.action_generation is None:
            if (
                any(
                    value is not None
                    for value in (
                        self.job_id,
                        self.job_state,
                        self.coarse_phase,
                        self.receipt_phase,
                        self.recovery_state,
                        self.selected_receipt_ref,
                        self.terminal_outcome,
                        self.selected_evaluation,
                        self.candidate_n5_result,
                        self.prior_candidate_n5_result,
                        self.blocker_reason,
                    )
                )
                or self.status != "unknown"
                or self.evaluation_disposition != "unknown"
            ):
                raise ValueError("candidate_experiment_unknown_projection_has_action_fields")
            return self
        if (
            self.job_id is None
            or self.coarse_phase is None
            or self.receipt_phase is None
            or self.recovery_state is None
            or self.selected_receipt_ref is None
            or self.selected_receipt_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("candidate_experiment_current_projection_identity_missing")
        if self.status in {"unknown", "in_progress"}:
            if (
                self.terminal_outcome is not None
                or self.evaluation_disposition != "unknown"
                or self.selected_evaluation is not None
                or self.candidate_n5_result is not None
                or self.prior_candidate_n5_result is not None
                or self.blocker_reason is not None
            ):
                raise ValueError("candidate_experiment_nonterminal_projection_has_outcome")
            return self
        if self.status == "blocked":
            if (
                self.terminal_outcome != "candidate_blocked"
                or self.evaluation_disposition != "blocked"
                or self.selected_evaluation is not None
                or self.candidate_n5_result is not None
                or self.blocker_reason is None
                or self.receipt_phase != "terminal"
            ):
                raise ValueError("candidate_experiment_blocked_projection_mismatch")
            if self.prior_candidate_n5_result is not None and (
                self.blocker_reason != "candidate_experiment_input_change_not_established"
                or self.prior_candidate_n5_result.prior_action_generation >= self.action_generation
                or self.prior_candidate_n5_result.n5_result.terminal_receipt_ref
                == self.selected_receipt_ref
            ):
                raise ValueError("candidate_experiment_prior_n5_result_current_projection_mismatch")
            return self
        if (
            self.terminal_outcome
            not in {
                "candidate_reentry_completed",
                "candidate_evaluation_retained",
            }
            or self.receipt_phase != "terminal"
        ):
            raise ValueError("candidate_experiment_completed_projection_missing_terminal")
        if self.evaluation_disposition == "blocked":
            if (
                self.terminal_outcome != "candidate_reentry_completed"
                or self.selected_evaluation is not None
                or self.blocker_reason is None
            ):
                raise ValueError("candidate_experiment_completed_blocked_projection_mismatch")
            if self.candidate_n5_result is not None and (
                self.receipt_phase != "terminal"
                or self.candidate_n5_result.terminal_receipt_ref != self.selected_receipt_ref
            ):
                raise ValueError("candidate_experiment_completed_n5_result_mismatch")
            if self.prior_candidate_n5_result is not None:
                raise ValueError(
                    "candidate_experiment_prior_n5_result_completed_projection_mismatch"
                )
            return self
        if self.evaluation_disposition not in {"new", "retained"}:
            raise ValueError("candidate_experiment_completed_projection_missing_evaluation")
        if self.evaluation_disposition == "new" and (
            self.terminal_outcome != "candidate_reentry_completed"
            or self.selected_evaluation is None
        ):
            raise ValueError("candidate_experiment_new_evaluation_projection_mismatch")
        if self.evaluation_disposition == "retained" and (
            self.terminal_outcome != "candidate_evaluation_retained"
            or self.selected_evaluation is None
        ):
            raise ValueError("candidate_experiment_retained_evaluation_projection_mismatch")
        if self.candidate_n5_result is not None:
            raise ValueError("candidate_experiment_evaluated_projection_has_fresh_result")
        if self.prior_candidate_n5_result is not None:
            raise ValueError("candidate_experiment_prior_n5_result_completed_projection_mismatch")
        if self.blocker_reason is not None:
            raise ValueError("candidate_experiment_completed_projection_has_blocker")
        return self


class CandidateExperimentRouteProjection(BaseModel):
    """Read-only experiment proposal with unknown cost and no action authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["CandidateExperimentRouteProjection@1.0"] = (
        "CandidateExperimentRouteProjection@1.0"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA256_PATTERN)
    replay_pins: CandidateExperimentRouteReplayPins
    scheduler_action: str = Field(min_length=1)
    scheduler_reason: str = Field(min_length=1)
    current_action: CandidateExperimentCurrentActionProjection = Field(
        default_factory=CandidateExperimentCurrentActionProjection
    )
    monetary_cost: Literal["not_established"] = "not_established"
    information_value: Literal["not_established"] = "not_established"
    action_authority: Literal["not_established"] = "not_established"
    publication_authority: Literal[False] = False


class AcquisitionRouteProjection(BaseModel):
    """Read-only current route with independent execution and authority postures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["AcquisitionRouteProjection@1.1"] = "AcquisitionRouteProjection@1.1"
    tenant_id: str
    cell_id: str
    run_id: str
    route_id: str = Field(pattern=_SHA256_PATTERN)
    route_projection_hash: str = Field(pattern=_SHA256_PATTERN)
    planner_report_hash: str = Field(pattern=_SHA256_PATTERN)
    planner_record_id: str
    recommended_strategy: str
    cost_basis: dict[str, object]
    replay_pins: AcquisitionRouteReplayPins
    route_status: Literal["costed_actionable"] = "costed_actionable"
    authority_capability: Literal["ready", "producer_missing"]
    execution_capability: Literal["ready", "producer_missing"]
    qualification_status: Literal["pending_epoch_activation", "activated"] = (
        "pending_epoch_activation"
    )
    qualification_predicate: Literal["not_established", "independently_reconciled"] = (
        "not_established"
    )
    qualification_reason: Literal["policy_admission_missing", "native_owner_readback"] = (
        "policy_admission_missing"
    )
    world_growth: Literal["not_established", "no_growth", "admitted_delta"] = "not_established"
    admitted_observation_delta: int | None = Field(default=None, ge=0)
    authority_badge: Literal["behavioral_fixture_not_production", "native_owner_verified"] = (
        "behavioral_fixture_not_production"
    )
    external_nonclosures: tuple[str, ...] = (
        "fresh_positive_production_route:absent/unallocated",
        "current_mandate_owner:producer_missing",
        "deterministic_admission_bundle:producer_missing",
        "non_fixture_n13b_owner_port:bridge_missing",
    )

    @model_validator(mode="after")
    def _growth_outcome_matches_evidence(self) -> AcquisitionRouteProjection:
        pending = (
            self.qualification_status == "pending_epoch_activation"
            and self.qualification_predicate == "not_established"
            and self.qualification_reason == "policy_admission_missing"
        )
        admitted = (
            self.qualification_status == "activated"
            and self.qualification_predicate == "independently_reconciled"
            and self.qualification_reason == "native_owner_readback"
            and self.authority_badge == "native_owner_verified"
        )
        if self.world_growth == "not_established":
            if not pending or self.admitted_observation_delta is not None:
                raise ValueError("acquisition_world_growth_status_delta_mismatch")
        elif self.world_growth == "no_growth":
            if not admitted or self.admitted_observation_delta != 0:
                raise ValueError("acquisition_world_growth_status_delta_mismatch")
        elif (
            not admitted
            or self.admitted_observation_delta is None
            or self.admitted_observation_delta <= 0
        ):
            raise ValueError("acquisition_world_growth_status_delta_mismatch")
        return self


class AcquisitionRouteListResponse(BaseModel):
    """Run-bound list response; the current closure admits at most one route."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    routes: tuple[AcquisitionRouteProjection, ...]


class AcquisitionDecisionRequestResponse(BaseModel):
    """Persisted authority result without an external effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    route_id: str = Field(pattern=_SHA256_PATTERN)
    authority_decision_ref: str = Field(pattern=_SHA256_PATTERN)
    outcome: Literal["decision_required", "decision_available"]
    human_decision_request: dict[str, object] | None = None
    world_growth: Literal["not_established"] = "not_established"


class AcquisitionExecutionResponse(BaseModel):
    """Durable deferred-job acceptance response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    route_id: str = Field(pattern=_SHA256_PATTERN)
    job_id: str
    authority_decision_ref: str = Field(pattern=_SHA256_PATTERN)
    status: Literal["accepted", "completed"] = "accepted"
    receipt_phase: Literal["requested", "terminal"] = "requested"
    world_growth: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _status_matches_receipt_phase(self) -> AcquisitionExecutionResponse:
        if (self.status == "completed") != (self.receipt_phase == "terminal"):
            raise ValueError("acquisition_execution_status_phase_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class _ValidatedAcquisitionMutation:
    """One route closure bound to the server-derived action identity."""

    closure: VerifiedAcquisitionRouteClosure
    job_id: str


class AcquisitionOwnerExecutionResult(BaseModel):
    """Strict owner-port result; refs denote artifacts the external owner already persisted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "AcquisitionOwnerExecutionResult@1.0", "AcquisitionOwnerExecutionResult@1.1"
    ] = "AcquisitionOwnerExecutionResult@1.0"
    disposition: Literal["quarantined_no_growth", "world_committed", "candidate_input_prepared"]
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)
    admitted_observation_delta: int = Field(ge=0)
    overlay_admission_receipt_ref: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    post_epoch_event_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    authority_badge: Literal[
        "behavioral_fixture_not_production", "native_owner_verified", "candidate_input_only"
    ] = "behavioral_fixture_not_production"
    action_phase_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    candidate_action_ref: artifacts.ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _world_commit_requires_active_owner_evidence(
        self,
    ) -> AcquisitionOwnerExecutionResult:
        if self.disposition == "candidate_input_prepared":
            if (
                self.schema_version != "AcquisitionOwnerExecutionResult@1.1"
                or self.authority_badge != "candidate_input_only"
                or self.candidate_action_ref is None
                or self.candidate_action_ref.kind
                != "runtime_quality.acquisition_candidate_action_receipt"
                or self.candidate_action_ref.media_type != "application/json"
                or self.candidate_action_ref.manifest_profile_sha256 is None
                or str(self.candidate_action_ref.artifact_id) not in self.owner_receipt_refs
                or self.action_phase_ref is None
                or self.admitted_observation_delta != 0
                or self.overlay_admission_receipt_ref is not None
                or self.post_epoch_event_ref is not None
            ):
                raise ValueError("candidate_input_owner_evidence_incomplete")
        elif self.schema_version != "AcquisitionOwnerExecutionResult@1.0" or (
            self.candidate_action_ref is not None or self.authority_badge == "candidate_input_only"
        ):
            raise ValueError("candidate_input_owner_schema_mismatch")
        elif self.disposition == "world_committed":
            if (
                self.admitted_observation_delta <= 0
                or self.overlay_admission_receipt_ref is None
                or self.post_epoch_event_ref is None
            ):
                raise ValueError("world_commit_owner_evidence_incomplete")
        elif (
            self.admitted_observation_delta != 0
            or self.overlay_admission_receipt_ref is not None
            or self.post_epoch_event_ref is not None
        ):
            raise ValueError("quarantine_cannot_claim_world_growth")
        if any(not ref.startswith("sha256:") for ref in self.owner_receipt_refs):
            raise ValueError("owner_receipt_ref_invalid")
        if (
            self.action_phase_ref is not None
            and self.action_phase_ref not in self.owner_receipt_refs
        ):
            raise ValueError("owner_action_phase_ref_missing")
        return self


class AcquisitionExecutionPort(Protocol):
    """External owner port; no raw path, CAS, journal, passport, or epoch inputs."""

    def execute(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        *,
        action_phase_ref: str | None = None,
    ) -> AcquisitionOwnerExecutionResult: ...

    def recover_owned_result(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        *,
        action_phase_ref: str | None = None,
    ) -> AcquisitionOwnerExecutionResult: ...

    def project_world_growth_outcome(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> tuple[
        Literal["not_established", "no_growth", "admitted_delta"],
        AcquisitionWorldGrowthReceipt | None,
    ]: ...

    def reenter(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        result: AcquisitionOwnerExecutionResult,
    ) -> str: ...

    def resume_reentry(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        owner_receipt_refs: tuple[str, ...],
    ) -> str: ...


class AcquisitionAuthorityGatewayProvider(Protocol):
    """External signed authority inputs resolved by the deployment composition root."""

    def for_request(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
        job_id: str,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway: ...

    def for_candidate_experiment_request(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
        job_id: str,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway: ...

    def load_candidate_experiment_decision_history(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
        job_id: str,
        decision_ref: str,
    ) -> AuthenticatedAgentActionDecisionHistory: ...

    def for_job(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
        job_id: str,
        decision_ref: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway: ...


class AcquisitionActionService:
    """Compose current route, PA2/DS9 authority, worker, owner port, and recovery."""

    def __init__(
        self,
        *,
        control_service: ControlPlaneService,
        human_decision_service: HumanDecisionService,
        authority_provider: AcquisitionAuthorityGatewayProvider | None = None,
        execution_port: AcquisitionExecutionPort | None = None,
        world_growth_config: AcquisitionWorldGrowthConfig | None = None,
        epoch_deployment: EpochDeployment | None = None,
        movement_service: AcquisitionMovementService | None = None,
    ) -> None:
        if type(control_service) is not ControlPlaneService:
            raise TypeError("acquisition service requires the exact control service")
        if type(human_decision_service) is not HumanDecisionService:
            raise TypeError("acquisition service requires the exact DS9 service")
        production_execution_port: AcquisitionExecutionPort | None = None
        if execution_port is None:
            from .acquisition_surface_execution import (
                build_production_world_bank_wdi_execution_port,
            )

            execution_port = build_production_world_bank_wdi_execution_port(
                control_service=control_service,
                world_growth_config=world_growth_config,
                epoch_deployment=epoch_deployment,
            )
            production_execution_port = execution_port
        if authority_provider is not None and any(
            not callable(getattr(authority_provider, name, None))
            for name in ("for_request", "for_job")
        ):
            raise TypeError("acquisition authority provider contract invalid")
        if execution_port is not None and any(
            not callable(getattr(execution_port, name, None))
            for name in ("execute", "reenter", "resume_reentry")
        ):
            raise TypeError("acquisition execution port contract invalid")
        self._movement_service = movement_service
        self.control_service = control_service
        self.human_decision_service = human_decision_service
        self._authority_provider = authority_provider
        self._execution_port = execution_port
        self._production_execution_port = production_execution_port
        if movement_service is not None:
            movement_service.bind_completed_control_job_core_source_resolver(
                control_service.resolve_completed_control_job_core_run_source
            )
        control_service.bind_acquisition_job_handler(self.handle_job)

    def list_routes(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
    ) -> AcquisitionRouteListResponse:
        """Return the exact current costed route or a typed closure error."""

        closure = self._resolve(tenant_id=tenant_id, cell_id=cell_id, run_id=run_id)
        return AcquisitionRouteListResponse(
            run_id=run_id,
            routes=(self._projection(closure),),
        )

    def get_route(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
    ) -> AcquisitionRouteProjection:
        """Return one exact current route; stale route ids never revive."""

        closure = self._resolve(tenant_id=tenant_id, cell_id=cell_id, run_id=run_id)
        if closure.route_id != route_id:
            raise AcquisitionActionServiceError("acquisition_route_not_current")
        return self._projection(closure)

    def request_decision(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: AcquisitionRouteMutationRequest,
        bound_permission: BoundActionPermissionVerification,
    ) -> AcquisitionDecisionRequestResponse:
        """Persist the PA2 decision/request without consuming or invoking the effect."""

        admission = self._validated_mutation(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=request,
        )
        closure = admission.closure
        provider = self._require_authority_provider()
        operation, invocation, intent = self._action_tuple(closure, request)
        job_id = admission.job_id

        def _no_effect(_invocation: OperationInvocationRecord) -> object:
            raise RuntimeError("decision request cannot invoke an acquisition effect")

        gateway = provider.for_request(
            closure=closure,
            request=request,
            job_id=job_id,
            bound_permission=bound_permission,
            effect_handler=_no_effect,
        )
        with agent_action_authority_scope(gateway):
            decision = produce_agent_action_authority_decision(
                bound_permission=bound_permission,
                operation=operation,
                invocation=invocation,
                intent=intent,
            )
            persisted = gateway.persist_decision(decision)
        return AcquisitionDecisionRequestResponse(
            run_id=run_id,
            route_id=route_id,
            authority_decision_ref=str(persisted.write_result.cas_ref.artifact_id),
            outcome=(
                "decision_required" if decision.outcome == "refused" else "decision_available"
            ),
            human_decision_request=(
                decision.human_decision_request.model_dump(mode="json")
                if decision.human_decision_request is not None
                else None
            ),
        )

    def execute(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: AcquisitionRouteMutationRequest,
        bound_permission: BoundActionPermissionVerification,
        request_id: str | None,
        principal: RuntimePrincipal | None,
    ) -> AcquisitionExecutionResponse:
        """Reserve a durable allow, persist requested phase, and enqueue without effect."""

        admission = self._validated_mutation(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=request,
        )
        closure = admission.closure
        provider = self._require_authority_provider()
        self._require_production_execution_bridge(closure)
        self._require_execution_port()
        operation, invocation, intent = self._action_tuple(closure, request)
        job_id = admission.job_id
        action_generation = self._action_generation(closure, job_id)

        def _no_http_effect(_invocation: OperationInvocationRecord) -> object:
            raise RuntimeError("HTTP acquisition reservation cannot invoke an effect")

        gateway = provider.for_request(
            closure=closure,
            request=request,
            job_id=job_id,
            bound_permission=bound_permission,
            effect_handler=_no_http_effect,
        )
        try:
            with agent_action_authority_scope(gateway):
                persisted = reserve_agent_external_action(
                    bound_permission=bound_permission,
                    operation=operation,
                    invocation=invocation,
                    intent=intent,
                )
        except AgentActionAuthorityRefused as exc:
            raise AcquisitionActionServiceError("human_decision_required") from exc
        decision_ref = str(persisted.write_result.cas_ref.artifact_id)
        requested = self._phase_receipt(
            action_generation=action_generation,
            closure=closure,
            job_id=job_id,
            decision_ref=decision_ref,
            receipt_phase="requested",
            predecessor_receipt_ref=None,
            owner_receipt_refs=(),
        )
        head = self.control_service.acquisition_route_sink.get_head(requested)
        if head is None:
            self.control_service.acquisition_route_sink.persist_phase(requested)
        elif head.job_id != job_id or head.receipt_phase not in {
            "requested",
            "executing",
            "outcome_selected",
            "world_committed_reentry_pending",
            "terminal",
        }:
            raise AcquisitionActionServiceError("acquisition_action_head_conflict")
        self.control_service.enqueue_acquisition_job(
            job_id=job_id,
            run_id=run_id,
            payload={
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": route_id,
                "decision_ref": decision_ref,
                "request": request.model_dump(mode="json"),
                "operation": operation.model_dump(mode="json"),
                "invocation": invocation.model_dump(mode="json"),
                "intent": intent.model_dump(mode="json"),
            },
            request_id=request_id,
            principal=principal,
        )
        return AcquisitionExecutionResponse(
            run_id=run_id,
            route_id=route_id,
            job_id=job_id,
            authority_decision_ref=decision_ref,
        )

    def handle_job(
        self,
        job: ControlJobRecord,
        payload: dict[str, Any],
        execution_scope: ControlJobExecutionScope,
    ) -> dict[str, Any]:
        """Run only with the tenant/cell admission attached to the live job lease."""

        if payload.get("action_kind") == CANDIDATE_EXPERIMENT_ACTION_KIND:
            return self._handle_candidate_experiment_job(job, payload, execution_scope)

        if job.kind != "acquisition" or job.run_id is None:
            raise AcquisitionActionServiceError("acquisition_job_kind_mismatch")
        if (
            execution_scope.status != "established"
            or not execution_scope.tenant_id
            or not execution_scope.cell_id
        ):
            raise AcquisitionActionServiceError("acquisition_job_owner_scope_not_established")
        if (
            payload.get("tenant_id") != execution_scope.tenant_id
            or payload.get("cell_id") != execution_scope.cell_id
        ):
            raise AcquisitionActionServiceError("acquisition_job_payload_owner_scope_mismatch")
        request = AcquisitionRouteMutationRequest.model_validate(payload.get("request"))
        admission = self._validated_mutation(
            tenant_id=execution_scope.tenant_id,
            cell_id=execution_scope.cell_id,
            run_id=job.run_id,
            route_id=str(payload.get("route_id") or ""),
            request=request,
        )
        if job.job_id != admission.job_id:
            raise AcquisitionActionServiceError("acquisition_job_identity_mismatch")
        closure = admission.closure
        operation = OperationContract.model_validate(payload.get("operation"))
        invocation = OperationInvocationRecord.model_validate(payload.get("invocation"))
        intent = AgentActionIntent.model_validate(payload.get("intent"))
        expected_tuple = self._action_tuple(closure, request)
        if (operation, invocation, intent) != expected_tuple:
            raise AcquisitionActionServiceError("acquisition_job_action_binding_mismatch")
        decision_ref = str(payload.get("decision_ref") or "")
        action_generation = self._action_generation(closure, job.job_id)
        seed = self._phase_receipt(
            action_generation=action_generation,
            closure=closure,
            job_id=job.job_id,
            decision_ref=decision_ref,
            receipt_phase="requested",
            predecessor_receipt_ref=None,
            owner_receipt_refs=(),
        )
        sink = self.control_service.acquisition_route_sink
        head = sink.get_head(seed)
        if head is None:
            raise AcquisitionActionServiceError("acquisition_requested_head_missing")
        port = self._require_execution_port()
        if head.receipt_phase == "terminal":
            self._consume_movement(head.receipt_ref)
            return {
                "state": "completed",
                "phase": "acquisition",
                "receipt_phase": "terminal",
                "terminal_receipt_ref": head.receipt_ref,
            }
        if head.receipt_phase == "candidate_input_reentry_pending":
            completed = self._complete_production_candidate_input(closure)
            if completed is None:
                raise AcquisitionRouteRecoveryRequired("candidate_reentry_recovery_required")
            self._consume_movement(completed.receipt_ref)
            return self._terminal_progress(completed)
        if head.receipt_phase == "world_committed_reentry_pending":
            if self._production_execution_bridge_installed():
                completed = self._complete_production_positive_admission(closure)
                if completed is not None:
                    self._consume_movement(completed.receipt_ref)
                    return self._terminal_progress(completed)
            pending = self._read_phase_receipt(head.receipt_ref)
            terminal = resume_world_committed_reentry(
                sink=sink,
                pending_receipt=pending,
                reentry=lambda: port.resume_reentry(closure, pending.owner_receipt_refs),
            )
            self._consume_movement(terminal.receipt_ref)
            return self._terminal_progress(terminal)
        if (
            head.receipt_phase in {"executing", "outcome_selected"}
            and self._production_execution_bridge_installed()
        ):
            # Recovery reads the already-owned outcome. It never replays the provider effect.
            action_phase_ref = (
                head.receipt_ref
                if head.receipt_phase == "executing"
                else head.predecessor_receipt_ref
            )
            if action_phase_ref is None:
                raise AcquisitionActionServiceError("acquisition_executing_head_missing")
            current = sink.current_action_outcome(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                route_id=closure.route_id,
            )
            if (
                current is None
                or current.head != head
                or current.executing_phase_ref != action_phase_ref
                or current.executing_phase is None
            ):
                raise AcquisitionActionServiceError("acquisition_executing_head_changed")
            current_phase = current.executing_phase
            if (
                current_phase.receipt_phase != "executing"
                or current_phase.action_generation != action_generation
                or current_phase.job_id != job.job_id
                or current_phase.tenant_id != closure.tenant_id
                or current_phase.cell_id != closure.cell_id
                or current_phase.run_id != closure.run_id
                or current_phase.source_job_id != closure.source_job_id
                or current_phase.route_id != closure.route_id
                or current_phase.compiled_ref != closure.compiled_ref
                or current_phase.planner_report_hash
                != agent_action_content_hash(closure.planner_report)
                or current_phase.cost_basis_hash != closure.cost_basis_hash
            ):
                raise AcquisitionActionServiceError("acquisition_executing_head_unverified")
            result = self._production_execution_port.recover_owned_result(
                closure, action_phase_ref=action_phase_ref
            )
            if (
                result.action_phase_ref != action_phase_ref
                or action_phase_ref not in result.owner_receipt_refs
            ):
                raise AcquisitionActionServiceError("acquisition_owner_recovery_scope_mismatch")
            still_current = sink.current_action_outcome(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                route_id=closure.route_id,
            )
            if still_current is None or still_current.head != current.head:
                raise AcquisitionActionServiceError("acquisition_executing_head_changed")
            selected_head = sink.persist_action_outcome_selection(
                action_phase_ref,
                result.owner_receipt_refs,
                **(
                    {"candidate_receipt_ref": result.candidate_action_ref}
                    if result.candidate_action_ref
                    else {}
                ),
            )
            if (
                selected_head.receipt_phase != "outcome_selected"
                or selected_head.predecessor_receipt_ref != action_phase_ref
            ):
                raise AcquisitionActionServiceError("acquisition_action_selection_missing")
            if result.disposition == "candidate_input_prepared":
                return self._persist_candidate_pending_and_reenter(
                    closure=closure,
                    job_id=job.job_id,
                    decision_ref=decision_ref,
                    action_generation=action_generation,
                    predecessor_receipt_ref=selected_head.receipt_ref,
                    owner_receipt_refs=result.owner_receipt_refs,
                    candidate_receipt_ref=result.candidate_action_ref,
                )
            if result.disposition == "quarantined_no_growth":
                terminal = self._terminal_receipt(
                    action_generation=action_generation,
                    closure=closure,
                    job_id=job.job_id,
                    decision_ref=decision_ref,
                    predecessor_receipt_ref=selected_head.receipt_ref,
                    owner_receipt_refs=result.owner_receipt_refs,
                )
                terminal_head = sink.persist_terminal(terminal)
                self._consume_movement(terminal_head.receipt_ref)
                return self._terminal_progress(terminal_head)
            if self._production_execution_bridge_installed():
                completed = self._complete_production_positive_admission(closure)
                if completed is not None:
                    self._consume_movement(completed.receipt_ref)
                    return self._terminal_progress(completed)
            pending = self._phase_receipt(
                action_generation=action_generation,
                closure=closure,
                job_id=job.job_id,
                decision_ref=decision_ref,
                receipt_phase="world_committed_reentry_pending",
                predecessor_receipt_ref=selected_head.receipt_ref,
                owner_receipt_refs=result.owner_receipt_refs,
            )
            terminal = persist_world_commit_and_reenter(
                sink=sink,
                pending_receipt=pending,
                reentry=lambda: port.reenter(closure, result),
            )
            self._consume_movement(terminal.receipt_ref)
            return self._terminal_progress(terminal)
        if head.receipt_phase != "requested":
            raise AcquisitionActionServiceError("acquisition_action_head_not_recoverable")
        executing = self._phase_receipt(
            action_generation=action_generation,
            closure=closure,
            job_id=job.job_id,
            decision_ref=decision_ref,
            receipt_phase="executing",
            predecessor_receipt_ref=head.receipt_ref,
            owner_receipt_refs=(),
        )
        executing_head = sink.persist_phase(executing)
        result_holder: list[AcquisitionOwnerExecutionResult] = []

        def _effect(_invocation: OperationInvocationRecord) -> object:
            if self._production_execution_bridge_installed():
                result = AcquisitionOwnerExecutionResult.model_validate(
                    port.execute(closure, action_phase_ref=executing_head.receipt_ref)
                )
                if (
                    result.action_phase_ref != executing_head.receipt_ref
                    or executing_head.receipt_ref not in result.owner_receipt_refs
                ):
                    raise AcquisitionActionServiceError(
                        "acquisition_owner_execution_scope_mismatch"
                    )
            else:
                result = AcquisitionOwnerExecutionResult.model_validate(port.execute(closure))
            result_holder.append(result)
            return result

        gateway = self._require_authority_provider().for_job(
            closure=closure,
            request=request,
            job_id=job.job_id,
            effect_handler=_effect,
            decision_ref=decision_ref,
        )
        persisted = gateway.load_persisted_decision(decision_ref)
        gateway.execute_bound_effect(
            operation=operation,
            invocation=invocation,
            intent=intent,
            persisted=persisted,
        )
        if len(result_holder) != 1:
            raise AcquisitionActionServiceError("acquisition_owner_result_missing")
        result = result_holder[0]
        outcome_predecessor_ref = executing_head.receipt_ref
        if self._production_execution_bridge_installed():
            if (
                result.action_phase_ref != executing_head.receipt_ref
                or executing_head.receipt_ref not in result.owner_receipt_refs
            ):
                raise AcquisitionActionServiceError("acquisition_owner_execution_scope_mismatch")
            selected_head = sink.persist_action_outcome_selection(
                executing_head.receipt_ref,
                result.owner_receipt_refs,
                **(
                    {"candidate_receipt_ref": result.candidate_action_ref}
                    if result.candidate_action_ref
                    else {}
                ),
            )
            if (
                selected_head.receipt_phase != "outcome_selected"
                or selected_head.predecessor_receipt_ref != executing_head.receipt_ref
            ):
                raise AcquisitionActionServiceError("acquisition_action_selection_missing")
            outcome_predecessor_ref = selected_head.receipt_ref
        if result.disposition == "candidate_input_prepared":
            return self._persist_candidate_pending_and_reenter(
                closure=closure,
                job_id=job.job_id,
                decision_ref=decision_ref,
                action_generation=action_generation,
                predecessor_receipt_ref=outcome_predecessor_ref,
                owner_receipt_refs=result.owner_receipt_refs,
                candidate_receipt_ref=result.candidate_action_ref,
            )
        if result.disposition == "quarantined_no_growth":
            terminal = self._terminal_receipt(
                action_generation=action_generation,
                closure=closure,
                job_id=job.job_id,
                decision_ref=decision_ref,
                predecessor_receipt_ref=outcome_predecessor_ref,
                owner_receipt_refs=result.owner_receipt_refs,
            )
            terminal_head = sink.persist_terminal(terminal)
            self._consume_movement(terminal_head.receipt_ref)
            return self._terminal_progress(terminal_head)
        if self._production_execution_bridge_installed():
            completed = self._complete_production_positive_admission(closure)
            if completed is not None:
                self._consume_movement(completed.receipt_ref)
                return self._terminal_progress(completed)
        pending = self._phase_receipt(
            action_generation=action_generation,
            closure=closure,
            job_id=job.job_id,
            decision_ref=decision_ref,
            receipt_phase="world_committed_reentry_pending",
            predecessor_receipt_ref=outcome_predecessor_ref,
            owner_receipt_refs=result.owner_receipt_refs,
        )
        terminal = persist_world_commit_and_reenter(
            sink=sink,
            pending_receipt=pending,
            reentry=lambda: port.reenter(closure, result),
        )
        self._consume_movement(terminal.receipt_ref)
        return self._terminal_progress(terminal)

    def _persist_candidate_pending_and_reenter(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        job_id: str,
        decision_ref: str,
        action_generation: int,
        predecessor_receipt_ref: str,
        owner_receipt_refs: tuple[str, ...],
        candidate_receipt_ref: artifacts.ArtifactRef | None,
    ) -> dict[str, Any]:
        """Record candidate input before re-entry, without asserting observation admission."""
        if not self._production_execution_bridge_installed():
            raise AcquisitionActionServiceError("candidate_input_owner_not_installed")
        pending = self._phase_receipt(
            action_generation=action_generation,
            closure=closure,
            job_id=job_id,
            decision_ref=decision_ref,
            receipt_phase="candidate_input_reentry_pending",
            predecessor_receipt_ref=predecessor_receipt_ref,
            owner_receipt_refs=owner_receipt_refs,
            candidate_receipt_ref=candidate_receipt_ref,
        )
        head = self.control_service.acquisition_route_sink.persist_phase(pending)
        if head.receipt_phase != "candidate_input_reentry_pending":
            raise AcquisitionActionServiceError("candidate_input_pending_head_missing")
        completed = self._complete_production_candidate_input(closure)
        if completed is None:
            raise AcquisitionRouteRecoveryRequired("candidate_reentry_recovery_required")
        self._consume_movement(completed.receipt_ref)
        return self._terminal_progress(completed)

    def _complete_production_candidate_input(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> AcquisitionActionHeadRecord | None:
        """Re-enter only through the installed candidate-aware production owner."""
        from .acquisition_surface_execution import WorldBankWDIAcquisitionExecutionPort

        port = self._production_execution_port
        if (
            type(port) is not WorldBankWDIAcquisitionExecutionPort
            or self._execution_port is not port
        ):
            return None
        return port.complete_candidate_reentry(closure)

    def _complete_production_positive_admission(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> AcquisitionActionHeadRecord | None:
        """Use only the actual installed production source/evaluation owner."""
        from .acquisition_surface_execution import WorldBankWDIAcquisitionExecutionPort

        port = self._production_execution_port
        if (
            type(port) is not WorldBankWDIAcquisitionExecutionPort
            or self._execution_port is not port
        ):
            return None
        return port.complete_positive_admission(closure)

    def _consume_movement(self, receipt_ref: str) -> None:
        if getattr(self, "_movement_service", None) is not None:
            self._movement_service.consume_terminal(supplier_receipt_ref=receipt_ref)

    def get_candidate_experiment_route(
        self, *, tenant_id: str, cell_id: str, run_id: str
    ) -> CandidateExperimentRouteProjection:
        """Reopen the candidate source and verified current action without granting authority."""
        if not tenant_id or not cell_id or not run_id:
            raise AcquisitionActionServiceError("acquisition_actor_scope_missing")
        loop = self._candidate_experiment_loop(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        )
        try:
            origin = loop.resolve_current_candidate_experiment(run_id=run_id)
        except AcquisitionRouteClosureError as exc:
            raise AcquisitionActionServiceError(exc.code) from exc
        projection = self._candidate_experiment_projection(origin)
        current_action = self._candidate_experiment_current_action_projection(origin)
        return projection.model_copy(update={"current_action": current_action})

    @staticmethod
    def _candidate_experiment_projection(
        origin: VerifiedCandidateExperimentOrigin,
    ) -> CandidateExperimentRouteProjection:
        """Project only the currently reopened source and policy identity."""
        scope = origin.policy_scope
        return CandidateExperimentRouteProjection(
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            route_id=origin.route_id,
            replay_pins=CandidateExperimentRouteReplayPins(
                source_job_id=origin.source_job_id,
                source_payload_ref=origin.source_payload_ref,
                request_content_hash=origin.request_content_hash,
                compiled_ref=scope.compiled_ref,
                planner_report_ref=scope.planner_report_ref,
                compiler_report_ref=scope.compiler_report_ref,
                configured_port_source_ref=scope.configured_port_source_ref,
                policy_ref=origin.policy_ref,
                candidate_digest=scope.candidate_digest,
                **(
                    {
                        "predecessor_terminal_ref": (
                            origin.candidate_terminal_history_chain[-1].terminal_ref
                        )
                    }
                    if origin.candidate_terminal_history_chain
                    else {}
                ),
            ),
            scheduler_action=origin.source_cycle.voi_decision.scheduler_action,
            scheduler_reason=origin.source_cycle.voi_decision.scheduler_reason,
        )

    def _candidate_experiment_current_action_projection(
        self, origin: VerifiedCandidateExperimentOrigin
    ) -> CandidateExperimentCurrentActionProjection:
        """Project the exact current head; a prior terminal never fills a newer phase."""
        from polisyos.runtime.http.services.control_plane_store import (
            AcquisitionActionHeadRecord,
            ControlJobRecord,
        )

        head = origin.current_action_head
        if head is None:
            return CandidateExperimentCurrentActionProjection()
        if (
            type(head) is not AcquisitionActionHeadRecord
            or (head.tenant_id, head.cell_id, head.run_id, head.source_job_id, head.route_id)
            != (
                origin.tenant_id,
                origin.cell_id,
                origin.run_id,
                origin.source_job_id,
                origin.route_id,
            )
            or head.receipt_ref != head.receipt_sha256
        ):
            raise AcquisitionActionServiceError(
                "candidate_experiment_current_action_identity_not_established"
            )

        job = self.control_service._control_store.get_job(head.job_id)
        job_state: Literal["pending", "running", "completed", "failed", "cancelled"] | None = None
        if job is not None:
            if (
                type(job) is not ControlJobRecord
                or job.job_id != head.job_id
                or job.kind != "acquisition"
                or job.run_id != origin.run_id
            ):
                raise AcquisitionActionServiceError(
                    "candidate_experiment_current_job_identity_not_established"
                )
            job_state = job.state

        terminal_history = origin.current_terminal_history
        if (
            terminal_history is not None
            and type(terminal_history) is not CandidateExperimentTerminalHistory
        ):
            raise AcquisitionActionServiceError("candidate_experiment_terminal_history_not_typed")
        current_terminal = (
            terminal_history
            if terminal_history is not None and terminal_history.head == head
            else None
        )

        receipt_kind = (
            "runtime_quality.acquisition_route_loop_receipt"
            if head.receipt_phase == "terminal"
            else "runtime_quality.acquisition_candidate_experiment_phase_receipt"
        )
        if head.receipt_manifest_profile_sha256 is None:
            raise AcquisitionActionServiceError(
                "candidate_experiment_current_receipt_profile_not_established"
            )
        try:
            selected_receipt_ref = artifacts.profile_bound_ref(
                self.control_service._artifact_store,
                artifacts.ArtifactRef(
                    artifact_id=artifacts.ArtifactID.model_validate(head.receipt_ref),
                    kind=receipt_kind,
                    media_type="application/json",
                    manifest_profile_sha256=head.receipt_manifest_profile_sha256,
                ),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise AcquisitionActionServiceError(
                "candidate_experiment_current_receipt_profile_not_established"
            ) from exc

        if current_terminal is not None and (
            type(current_terminal.terminal) is not AcquisitionCandidateExperimentTerminalReceipt
            or current_terminal.terminal_ref != selected_receipt_ref
        ):
            raise AcquisitionActionServiceError(
                "candidate_experiment_terminal_receipt_profile_mismatch"
            )
        terminal = current_terminal.terminal if current_terminal is not None else None
        blocker_reason = None if terminal is None else terminal.blocker_reason
        if (
            current_terminal is not None
            and terminal is not None
            and terminal.terminal_outcome == "candidate_reentry_completed"
            and terminal.selected_evaluation is None
        ):
            # Physical reentry may finish without establishing an evaluation.
            # Preserve that outcome and expose the exact verified basis reasons.
            basis = current_terminal.selected_basis
            if (
                basis is None
                or basis.basis_role != "blocked"
                or basis.predicate_provenance != "not_established"
                or not basis.reason_codes
            ):
                raise AcquisitionActionServiceError(
                    "candidate_experiment_blocked_evaluation_basis_not_established"
                )
            blocker_reason = "; ".join(basis.reason_codes)
        candidate_n5_result = (
            self._candidate_experiment_n5_result_projection(current_terminal)
            if current_terminal is not None
            and terminal is not None
            and terminal.terminal_outcome == "candidate_reentry_completed"
            and terminal.selected_evaluation is None
            else None
        )
        prior_candidate_n5_result = (
            self._candidate_experiment_prior_n5_result_projection(current_terminal)
            if current_terminal is not None
            and terminal is not None
            and terminal.terminal_outcome == "candidate_blocked"
            and terminal.blocker_reason == "candidate_experiment_input_change_not_established"
            else None
        )
        return self._format_candidate_experiment_current_action(
            head=head,
            job_state=job_state,
            selected_receipt_ref=selected_receipt_ref,
            current_terminal_head=None if current_terminal is None else current_terminal.head,
            terminal_outcome=None if terminal is None else terminal.terminal_outcome,
            selected_evaluation=None if terminal is None else terminal.selected_evaluation,
            candidate_n5_result=candidate_n5_result,
            prior_candidate_n5_result=prior_candidate_n5_result,
            blocker_reason=blocker_reason,
        )

    def _candidate_experiment_prior_n5_result_projection(
        self,
        current_history: CandidateExperimentTerminalHistory,
    ) -> CandidateExperimentPriorN5ResultProjection:
        """Expose the last verified N5 body only as a prior candidate observation."""
        terminal = current_history.terminal
        decision = current_history.decision
        if (
            terminal.terminal_outcome != "candidate_blocked"
            or terminal.blocker_reason != "candidate_experiment_input_change_not_established"
            or decision is None
            or decision.comparison_result != "not_established"
            or decision.predicate_provenance != "not_established"
            or "candidate_experiment_input_change_not_established" not in decision.reason_codes
        ):
            raise AcquisitionActionServiceError(
                "candidate_experiment_prior_n5_result_current_blocker_not_established"
            )

        from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
            _candidate_experiment_unselected_prior,
        )

        try:
            prior_history = _candidate_experiment_unselected_prior(current_history.origin)
        except ValueError as exc:
            raise AcquisitionActionServiceError(
                "candidate_experiment_prior_n5_result_history_not_established"
            ) from exc

        history_chain = current_history.origin.candidate_terminal_history_chain
        current_scope = (
            current_history.head.tenant_id,
            current_history.head.cell_id,
            current_history.head.run_id,
            current_history.head.source_job_id,
            current_history.head.route_id,
        )
        if (
            prior_history is None
            or not any(item is prior_history for item in history_chain)
            or any(
                type(item) is not CandidateExperimentTerminalHistory
                or item.head.action_generation != generation
                or item.terminal.action_generation != generation
                or (
                    item.head.tenant_id,
                    item.head.cell_id,
                    item.head.run_id,
                    item.head.source_job_id,
                    item.head.route_id,
                )
                != current_scope
                for generation, item in enumerate(history_chain, start=1)
            )
            or tuple(item.head.action_generation for item in history_chain)
            != tuple(range(1, current_history.head.action_generation))
            or prior_history.head.action_generation >= current_history.head.action_generation
            or prior_history.terminal.candidate_action_ref is None
            or prior_history.terminal.action_generation != prior_history.head.action_generation
        ):
            raise AcquisitionActionServiceError(
                "candidate_experiment_prior_n5_result_history_not_established"
            )

        n5_result = self._candidate_experiment_n5_result_projection(
            prior_history,
            expected_latest_head=current_history.head,
        )
        if n5_result is None:
            raise AcquisitionActionServiceError(
                "candidate_experiment_prior_n5_result_not_established"
            )
        return CandidateExperimentPriorN5ResultProjection(
            prior_action_ref=prior_history.terminal.candidate_action_ref,
            prior_action_generation=prior_history.head.action_generation,
            n5_result=n5_result,
        )

    def _candidate_experiment_n5_result_projection(
        self,
        history: CandidateExperimentTerminalHistory,
        *,
        expected_latest_head: AcquisitionActionHeadRecord | None = None,
    ) -> CandidateExperimentN5ResultProjection | None:
        """Project candidate N5 numbers without establishing full configuration use."""
        latest_head = expected_latest_head or history.head
        if (
            (
                latest_head.tenant_id,
                latest_head.cell_id,
                latest_head.run_id,
                latest_head.source_job_id,
                latest_head.route_id,
            )
            != (
                history.head.tenant_id,
                history.head.cell_id,
                history.head.run_id,
                history.head.source_job_id,
                history.head.route_id,
            )
            or latest_head.action_generation < history.head.action_generation
            or latest_head.receipt_phase != "terminal"
        ):
            raise AcquisitionActionServiceError(
                "candidate_experiment_n5_result_expected_head_mismatch"
            )
        terminal = history.terminal
        reentry = history.reentry
        evaluation = history.reentry_evaluation
        basis = history.selected_basis
        if (
            terminal.terminal_outcome != "candidate_reentry_completed"
            or terminal.selected_evaluation is not None
            or terminal.candidate_reentry_ref is None
            or reentry is None
            or basis is None
            or basis.basis_role != "blocked"
            or not basis.reason_codes
            or reentry.new_cycle.simulation.status != "joint_simulated"
        ):
            return None
        if evaluation is None:
            raise AcquisitionActionServiceError(
                "candidate_experiment_n5_result_history_not_established"
            )

        selected = evaluation.selected
        execution = evaluation.execution
        if (
            selected.design_problem_ref != reentry.design_problem_basis_ref
            or reentry.design_problem_basis_ref
            != (reentry.new_cycle.design_problem_basis_ref or reentry.new_cycle.design_problem_ref)
            or selected.evaluation_job_id != reentry.action_job_id
            or selected.evaluation_run_id != reentry.run_id
            or selected.generation_run_id != reentry.continued_generation_run.run_id
            or selected.cycle_index != reentry.new_cycle.cycle_index
            or execution.job_id != reentry.action_job_id
            or execution.run_id != reentry.run_id
            or reentry.n5_result_ref is None
            or any(
                artifacts.artifact_ref_identity_key(ref)
                != artifacts.artifact_ref_identity_key(reentry.n5_result_ref)
                for ref in (selected.n5_result_ref, execution.n5_result_ref)
            )
        ):
            raise AcquisitionActionServiceError(
                "candidate_experiment_n5_result_reentry_binding_mismatch"
            )

        prepared = basis.prepared_n5_configuration
        if prepared is None:
            return None
        from polisyos.runtime.quality.n5_execution_basis import (
            _candidate_n5_experiment_observation_supported,
            read_n5_execution_implementation_witness,
        )

        try:
            witness = read_n5_execution_implementation_witness(
                evaluation.result,
                input_ref=selected.n5_input_ref,
            )
        except ValueError:
            return None
        if not _candidate_n5_experiment_observation_supported(witness, prepared):
            return None

        try:
            physical_work = evaluation.result.physical_work_observations
        except ValueError:
            return None
        if (
            evaluation.result.diagnostics.get("physical_work_capture_status") != "observed"
            or not physical_work
        ):
            return None

        from polisyos.runtime.http.services.acquisition_n5_projection import (
            build_candidate_n5_result_body,
        )

        try:
            result_body = build_candidate_n5_result_body(
                store=self.control_service._artifact_store,
                ref=selected.n5_result_ref,
                result=evaluation.result,
                source=evaluation.source,
                tenant_id=history.origin.tenant_id,
                cell_id=history.origin.cell_id,
                authority_purpose="candidate_scenario_n5_only",
            )
        except Exception as exc:
            code = _candidate_experiment_n5_result_read_error_code(exc)
            if code is None:
                raise
            raise AcquisitionActionServiceError(code) from exc
        if artifacts.artifact_ref_identity_key(
            result_body.artifact_ref
        ) != artifacts.artifact_ref_identity_key(selected.n5_result_ref):
            raise AcquisitionActionServiceError(
                "candidate_experiment_n5_result_reentry_binding_mismatch"
            )

        try:
            source_heads = (
                self.control_service._control_store.list_acquisition_action_heads_for_source(
                    tenant_id=history.head.tenant_id,
                    cell_id=history.head.cell_id,
                    run_id=history.head.run_id,
                    source_job_id=history.head.source_job_id,
                )
            )
        except (OSError, RuntimeError) as exc:
            raise AcquisitionActionServiceError(
                "candidate_experiment_current_action_head_not_established"
            ) from exc
        if any(head.route_id != history.head.route_id for head in source_heads) or tuple(
            head.action_generation for head in source_heads
        ) != tuple(range(1, len(source_heads) + 1)):
            raise AcquisitionActionServiceError("candidate_experiment_action_history_conflict")
        latest_source_head = source_heads[-1] if source_heads else None
        if latest_source_head != latest_head:
            raise AcquisitionActionServiceError("candidate_experiment_current_action_head_changed")
        return CandidateExperimentN5ResultProjection(
            terminal_receipt_ref=history.terminal_ref,
            reentry_receipt_ref=terminal.candidate_reentry_ref,
            result_body=result_body,
            reason_codes=basis.reason_codes,
            limitations=tuple(
                dict.fromkeys(
                    (
                        *basis.limitations,
                        *reentry.limitations,
                        "controller_wide_configuration_use_not_established",
                    )
                )
            ),
        )

    @staticmethod
    def _format_candidate_experiment_current_action(
        *,
        head: AcquisitionActionHeadRecord | None,
        job_state: Literal["pending", "running", "completed", "failed", "cancelled"] | None,
        selected_receipt_ref: artifacts.ArtifactRef | None,
        current_terminal_head: AcquisitionActionHeadRecord | None,
        terminal_outcome: Literal[
            "candidate_reentry_completed", "candidate_evaluation_retained", "candidate_blocked"
        ]
        | None = None,
        selected_evaluation: AcquisitionSelectedEvaluation | None = None,
        candidate_n5_result: CandidateExperimentN5ResultProjection | None = None,
        prior_candidate_n5_result: CandidateExperimentPriorN5ResultProjection | None = None,
        blocker_reason: str | None = None,
    ) -> CandidateExperimentCurrentActionProjection:
        """Format an owner-adapted snapshot; this helper does not verify its inputs."""
        if head is None:
            return CandidateExperimentCurrentActionProjection()

        terminal_is_current = current_terminal_head == head
        status: Literal["unknown", "in_progress", "completed", "blocked"] = "unknown"
        evaluation_disposition: Literal["unknown", "new", "retained", "blocked"] = "unknown"
        if terminal_is_current:
            if terminal_outcome == "candidate_blocked":
                status = "blocked"
                evaluation_disposition = "blocked"
                selected_evaluation = None
            elif terminal_outcome in {
                "candidate_reentry_completed",
                "candidate_evaluation_retained",
            }:
                status = "completed"
                if terminal_outcome == "candidate_evaluation_retained":
                    evaluation_disposition = "retained"
                elif selected_evaluation is not None:
                    evaluation_disposition = "new"
                elif blocker_reason is not None:
                    evaluation_disposition = "blocked"
            else:
                raise AcquisitionActionServiceError(
                    "candidate_experiment_current_terminal_outcome_not_established"
                )
        elif job_state in {"pending", "running"} and head.receipt_phase != "terminal":
            status = "in_progress"

        if not terminal_is_current:
            terminal_outcome = None
            selected_evaluation = None
            candidate_n5_result = None
            prior_candidate_n5_result = None
            blocker_reason = None
        return CandidateExperimentCurrentActionProjection(
            status=status,
            action_generation=head.action_generation,
            job_id=head.job_id,
            job_state=job_state,
            coarse_phase=head.coarse_phase,
            receipt_phase=head.receipt_phase,
            recovery_state=head.recovery_state,
            selected_receipt_ref=selected_receipt_ref,
            terminal_outcome=terminal_outcome,
            evaluation_disposition=evaluation_disposition,
            selected_evaluation=selected_evaluation,
            candidate_n5_result=candidate_n5_result,
            prior_candidate_n5_result=prior_candidate_n5_result,
            blocker_reason=blocker_reason,
        )

    def _resolve_candidate_experiment_origin(
        self, *, tenant_id: str, cell_id: str, run_id: str
    ) -> VerifiedCandidateExperimentOrigin:
        """Reopen the candidate source and policy through the canonical route owner."""
        loop = self._candidate_experiment_loop(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        )
        try:
            return loop.resolve_current_candidate_experiment(run_id=run_id)
        except AcquisitionRouteClosureError as exc:
            raise AcquisitionActionServiceError(exc.code) from exc

    def _candidate_experiment_origin_for_request(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        request: CandidateExperimentRouteMutationRequest,
        require_current: bool,
    ) -> VerifiedCandidateExperimentOrigin:
        """Bind immutable request pins to their verified prefix and optional live head."""
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

        loop = self._candidate_experiment_loop(tenant_id=tenant_id, cell_id=cell_id, run_id=run_id)
        try:
            root = loop._resolve_candidate_experiment_source(run_id=run_id)
            job_id = self._candidate_experiment_job_id(root, request)
            selected_heads = (
                self.control_service._control_store.list_acquisition_action_heads_for_source(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=run_id,
                    source_job_id=root.source_job_id,
                )
            )
            own_heads = tuple(head for head in selected_heads if head.job_id == job_id)
            if len(own_heads) > 1:
                raise AcquisitionActionServiceError("candidate_experiment_job_identity_mismatch")
            origin = loop.resolve_candidate_experiment_predecessor_origin(
                run_id=run_id,
                predecessor_terminal_ref=request.replay_pins.predecessor_terminal_ref,
                expected_action_generation=(own_heads[0].action_generation if own_heads else None),
            )
        except AcquisitionRouteClosureError as exc:
            raise AcquisitionActionServiceError(exc.code) from exc
        if request.route_id != origin.route_id or not _candidate_model_values_same(
            request.replay_pins, self._candidate_experiment_projection(origin).replay_pins
        ):
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        heads = self.control_service._control_store.list_acquisition_action_heads_for_source(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            source_job_id=origin.source_job_id,
        )
        if any(head.route_id != origin.route_id for head in heads) or tuple(
            head.action_generation for head in heads
        ) != tuple(range(1, len(heads) + 1)):
            raise AcquisitionActionServiceError("candidate_experiment_action_history_conflict")
        generation = len(origin.candidate_terminal_history_chain) + 1
        job_id = self._candidate_experiment_job_id(origin, request)
        same_job = tuple(head for head in heads if head.job_id == job_id)
        if len(same_job) > 1 or (same_job and same_job[0].action_generation != generation):
            raise AcquisitionActionServiceError("candidate_experiment_job_identity_mismatch")
        if require_current:
            latest = heads[-1] if heads else None
            previous = (
                origin.candidate_terminal_history_chain[-1].head
                if origin.candidate_terminal_history_chain
                else None
            )
            new_action = latest == previous
            pending_retry = (
                latest is not None
                and latest.action_generation == generation
                and latest.job_id == job_id
                and latest.receipt_phase != "terminal"
            )
            if not (new_action or pending_retry):
                raise AcquisitionActionServiceError("candidate_experiment_predecessor_not_current")
            if pending_retry:
                origin = replace(origin, current_action_head=latest)
        return origin

    def _candidate_experiment_loop(
        self, *, tenant_id: str, cell_id: str, run_id: str
    ) -> AcquisitionRouteLoop:
        """Compose the candidate source reader from the existing run-bound owners."""
        if not tenant_id or not cell_id or not run_id:
            raise AcquisitionActionServiceError("acquisition_actor_scope_missing")
        return AcquisitionRouteLoop(
            control_store=self.control_service._control_store,
            artifact_store=self.control_service._artifact_store,
            event_log=self.control_service._diagnostic_event_log,
            core_source_resolver=self.control_service.resolve_completed_control_job_core_run_source,
            tenant_id=tenant_id,
            cell_id=cell_id,
            action_outcome_reader=self.control_service.acquisition_route_sink,
        )

    def _validate_candidate_experiment_request(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        request: CandidateExperimentRouteMutationRequest,
    ) -> CandidateExperimentRouteProjection:
        """Reopen optimistic pins only; this does not reserve or authorize work."""
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

        if type(request) is not CandidateExperimentRouteMutationRequest:
            raise AcquisitionActionServiceError("candidate_experiment_request_untyped")
        projection = self.get_candidate_experiment_route(
            tenant_id=tenant_id, cell_id=cell_id, run_id=run_id
        )
        if request.route_id != projection.route_id or not _candidate_model_values_same(
            request.replay_pins, projection.replay_pins
        ):
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        return projection

    def replay_candidate_experiment_authority(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: CandidateExperimentRouteMutationRequest,
        job_id: str,
        decision_ref: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Reopen candidate source and persisted PA2/DS9 evidence for a checked worker."""
        if type(request) is not CandidateExperimentRouteMutationRequest:
            raise AcquisitionActionServiceError("candidate_experiment_request_untyped")
        origin = self._candidate_experiment_origin_for_request(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=request,
            require_current=True,
        )
        if route_id != origin.route_id:
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        expected_job_id = self._candidate_experiment_job_id(origin, request)
        if job_id != expected_job_id:
            raise AcquisitionActionServiceError("candidate_experiment_job_identity_mismatch")
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

        projection = self._candidate_experiment_projection(origin)
        if not _candidate_model_values_same(request.replay_pins, projection.replay_pins):
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        provider = self._require_candidate_experiment_authority_provider()
        return provider.for_candidate_experiment_job(
            origin=origin,
            request=request,
            job_id=job_id,
            decision_ref=decision_ref,
            effect_handler=effect_handler,
        )

    def load_candidate_experiment_decision_history(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: CandidateExperimentRouteMutationRequest,
        job_id: str,
        decision_ref: str,
    ) -> AuthenticatedAgentActionDecisionHistory:
        """Load immutable candidate PA2 history after rebuilding the exact tuple.

        The returned record proves what PA2 recorded at the original write context;
        it deliberately does not authorize current execution.
        """
        if type(request) is not CandidateExperimentRouteMutationRequest:
            raise AcquisitionActionServiceError("candidate_experiment_request_untyped")
        origin = self._candidate_experiment_origin_for_request(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=request,
            require_current=False,
        )
        if origin.route_id != route_id:
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

        if not _candidate_model_values_same(
            request.replay_pins, self._candidate_experiment_projection(origin).replay_pins
        ):
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        expected_job_id = self._candidate_experiment_job_id(origin, request)
        if job_id != expected_job_id:
            raise AcquisitionActionServiceError("candidate_experiment_job_identity_mismatch")
        provider = self._require_candidate_experiment_authority_provider()
        return provider.load_candidate_experiment_decision_history(
            origin=origin,
            request=request,
            job_id=job_id,
            decision_ref=decision_ref,
        )

    def request_candidate_experiment_decision(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: CandidateExperimentRouteMutationRequest,
        bound_permission: BoundActionPermissionVerification,
    ) -> AcquisitionDecisionRequestResponse:
        """Persist the exact candidate-experiment PA2 decision without executing it."""
        projection = self._validate_candidate_experiment_request(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=request,
        )
        if route_id != projection.route_id:
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        origin = self._candidate_experiment_origin_for_request(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=request,
            require_current=True,
        )
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

        if origin.route_id != projection.route_id or not _candidate_model_values_same(
            self._candidate_experiment_projection(origin).replay_pins,
            projection.replay_pins,
        ):
            raise AcquisitionActionServiceError("candidate_experiment_source_changed")
        job_id = self._candidate_experiment_job_id(origin, request)
        operation, invocation, intent = self._candidate_experiment_action_tuple(origin, request)
        provider = self._require_candidate_experiment_authority_provider()

        def _no_effect(_invocation: OperationInvocationRecord) -> object:
            raise RuntimeError("candidate-experiment decision request cannot invoke an effect")

        gateway = provider.for_candidate_experiment_request(
            origin=origin,
            request=request,
            job_id=job_id,
            bound_permission=bound_permission,
            effect_handler=_no_effect,
        )
        with agent_action_authority_scope(gateway):
            decision = produce_agent_action_authority_decision(
                bound_permission=bound_permission,
                operation=operation,
                invocation=invocation,
                intent=intent,
            )
            persisted = gateway.persist_decision(decision)
        return AcquisitionDecisionRequestResponse(
            run_id=run_id,
            route_id=route_id,
            authority_decision_ref=str(persisted.write_result.cas_ref.artifact_id),
            outcome=(
                "decision_required" if decision.outcome == "refused" else "decision_available"
            ),
            human_decision_request=(
                decision.human_decision_request.model_dump(mode="json")
                if decision.human_decision_request is not None
                else None
            ),
        )

    def execute_candidate_experiment(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: CandidateExperimentRouteMutationRequest,
        decision_ref: str,
        request_id: str | None,
        principal: RuntimePrincipal | None,
    ) -> AcquisitionExecutionResponse:
        """Queue one candidate experiment without exposing an effect at the HTTP layer."""
        if type(request) is not CandidateExperimentRouteMutationRequest:
            raise AcquisitionActionServiceError("candidate_experiment_request_untyped")
        origin = self._candidate_experiment_origin_for_request(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=request,
            require_current=False,
        )
        projection = self._candidate_experiment_projection(origin)
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

        if (
            route_id != projection.route_id
            or request.route_id != projection.route_id
            or not _candidate_model_values_same(request.replay_pins, projection.replay_pins)
        ):
            raise AcquisitionActionServiceError("candidate_experiment_route_revalidation_required")
        job_id = self._candidate_experiment_job_id(origin, request)

        phase_owner = self.control_service.acquisition_route_sink
        existing_heads = (
            self.control_service._control_store.list_acquisition_action_heads_for_source(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                source_job_id=origin.source_job_id,
            )
        )
        existing_requested = None
        same_job_heads = tuple(head for head in existing_heads if head.job_id == job_id)
        if len(same_job_heads) > 1:
            raise AcquisitionActionServiceError("candidate_experiment_action_history_conflict")
        if same_job_heads:
            try:
                outcome = phase_owner.verify_action_head(same_job_heads[0])
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise AcquisitionActionServiceError(
                    "candidate_experiment_requested_phase_recovery_not_established"
                ) from exc
            if (
                outcome.head.job_id != job_id
                or outcome.head.action_generation
                != len(origin.candidate_terminal_history_chain) + 1
                or not outcome.phase_chain
                or type(outcome.phase_chain[0].receipt)
                is not AcquisitionCandidateExperimentPhaseReceipt
            ):
                raise AcquisitionActionServiceError("candidate_experiment_action_history_conflict")
            existing_requested = outcome.phase_chain[0]
            requested_phase = existing_requested.receipt
            if (
                requested_phase.receipt_phase != "requested"
                or requested_phase.job_id != job_id
                or str(requested_phase.authority_decision_ref.artifact_id) != decision_ref
            ):
                raise AcquisitionActionServiceError("candidate_experiment_action_history_conflict")
            existing_job = self.control_service._control_store.get_job(job_id)
            if existing_job is not None and existing_job.state == "completed":
                expected_payload = {
                    "action_kind": CANDIDATE_EXPERIMENT_ACTION_KIND,
                    "tenant_id": tenant_id,
                    "cell_id": cell_id,
                    "run_id": run_id,
                    "route_id": route_id,
                    "request": request.model_dump(mode="json"),
                    "decision_ref": decision_ref,
                }
                if (
                    existing_job.kind != "acquisition"
                    or existing_job.run_id != run_id
                    or existing_job.submitted_by is None
                    or principal is None
                    or not principal.authenticated
                    or principal.subject != existing_job.submitted_by
                    or principal.tenant_id != tenant_id
                    or principal.cell_id != cell_id
                    or existing_job.payload_ref is None
                ):
                    raise AcquisitionActionServiceError(
                        "candidate_experiment_completed_retry_scope_conflict"
                    )
                stored_payload = read_core_json_artifact(
                    self.control_service._artifact_store, existing_job.payload_ref
                ).value
                if not isinstance(stored_payload, dict) or any(
                    stored_payload.get(name) != value for name, value in expected_payload.items()
                ):
                    raise AcquisitionActionServiceError(
                        "candidate_experiment_completed_retry_payload_conflict"
                    )
                from polisyos.runtime.quality.acquisition_evaluation import (
                    CandidateExperimentTerminalHistory,
                )
                from polisyos.runtime.quality.acquisition_route_loop import (
                    AcquisitionCandidateExperimentTerminalReceipt,
                )

                terminal_history = outcome.candidate_experiment_terminal_history
                if (
                    outcome.head.receipt_phase != "terminal"
                    or outcome.head.job_id != job_id
                    or type(outcome.latest_receipt)
                    is not AcquisitionCandidateExperimentTerminalReceipt
                    or type(terminal_history) is not CandidateExperimentTerminalHistory
                    or terminal_history.head != outcome.head
                    or terminal_history.terminal != outcome.latest_receipt
                    or str(terminal_history.terminal_ref.artifact_id) != outcome.head.receipt_ref
                ):
                    raise AcquisitionActionServiceError(
                        "candidate_experiment_completed_terminal_history_not_established"
                    )
                try:
                    history = self.load_candidate_experiment_decision_history(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        run_id=run_id,
                        route_id=route_id,
                        request=request,
                        job_id=job_id,
                        decision_ref=decision_ref,
                    )
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise AcquisitionActionServiceError(
                        "candidate_experiment_completed_decision_history_not_established"
                    ) from exc
                permission = history.decision.permission_snapshot
                if (
                    history.current_authority != "not_revalidated"
                    or history.decision_ref != decision_ref
                    or decision_ref != f"sha256:{history.payload_sha256}"
                    or history.decision.outcome != "allowed"
                    or permission is None
                    or permission.subject != principal.subject
                    or permission.tenant_id != tenant_id
                ):
                    raise AcquisitionActionServiceError(
                        "candidate_experiment_completed_retry_authority_conflict"
                    )
                return AcquisitionExecutionResponse(
                    run_id=run_id,
                    route_id=route_id,
                    job_id=job_id,
                    authority_decision_ref=decision_ref,
                    status="completed",
                    receipt_phase="terminal",
                )
        current_origin = self._candidate_experiment_origin_for_request(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            request=request,
            require_current=True,
        )
        port = self._require_candidate_experiment_execution_port()
        bridge = getattr(port, "_world_growth_bridge", None)
        preflight = getattr(port, "preflight_candidate_experiment", None)
        continuation_preflight = getattr(bridge, "preflight_candidate_experiment_evaluation", None)
        if bridge is None or not callable(preflight) or not callable(continuation_preflight):
            raise AcquisitionActionServiceError(
                "candidate_experiment_full_continuation_preflight_not_established"
            )
        try:
            selection = preflight(origin=current_origin)
            continuation = continuation_preflight(origin=current_origin, selection=selection)
            from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
                CandidateExperimentEvaluationPreflight,
            )

            if (
                type(continuation) is not CandidateExperimentEvaluationPreflight
                or continuation.origin != current_origin
                or continuation.selection != selection
                or continuation.policy_ref != current_origin.policy_ref
                or continuation.continuation_kind != "candidate_source_reentry_n5"
            ):
                raise ValueError("candidate_experiment_full_continuation_preflight_mismatch")
            history = self.load_candidate_experiment_decision_history(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                route_id=route_id,
                request=request,
                job_id=job_id,
                decision_ref=decision_ref,
            )
            if (
                type(history) is not AuthenticatedAgentActionDecisionHistory
                or history.current_authority != "not_revalidated"
                or history.decision_ref != decision_ref
                or decision_ref != f"sha256:{history.payload_sha256}"
                or history.decision.outcome != "allowed"
            ):
                raise ValueError("candidate_experiment_pa2_decision_not_allowed")
            permission = history.decision.permission_snapshot
            if (
                principal is None
                or not principal.authenticated
                or permission is None
                or principal.subject != permission.subject
                or principal.tenant_id != tenant_id
                or principal.cell_id != cell_id
                or permission.subject != principal.subject
                or permission.tenant_id != tenant_id
                or origin.tenant_id != tenant_id
                or origin.cell_id != cell_id
            ):
                raise ValueError("candidate_experiment_decision_subject_scope_mismatch")

            def _no_effect(_invocation: OperationInvocationRecord) -> object:
                raise RuntimeError("candidate experiment enqueue cannot execute an effect")

            gateway = self.replay_candidate_experiment_authority(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                route_id=route_id,
                request=request,
                job_id=job_id,
                decision_ref=decision_ref,
                effect_handler=_no_effect,
            )
            persisted = gateway.load_persisted_decision(decision_ref)
            if persisted.decision != history.decision:
                raise ValueError("candidate_experiment_current_pa2_changed")
            if existing_requested is not None:
                phase = existing_requested.receipt
                requested_head = (
                    self.control_service._control_store.get_acquisition_action_head_by_receipt(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        run_id=run_id,
                        source_job_id=origin.source_job_id,
                        route_id=origin.route_id,
                        action_generation=phase.action_generation,
                        receipt_ref=existing_requested.receipt_ref,
                    )
                )
                if requested_head is None or requested_head.receipt_manifest_profile_sha256 is None:
                    raise ValueError("candidate_experiment_requested_profile_not_established")
                prepared = phase_owner._prepared_experiment_phase_publication(
                    phase,
                    request,
                    receipt_ref=existing_requested.receipt_ref,
                    receipt_manifest_profile_sha256=(
                        requested_head.receipt_manifest_profile_sha256
                    ),
                    durable_event_id=existing_requested.durable_event_id,
                )
            else:
                phase = AcquisitionCandidateExperimentPhaseReceipt(
                    receipt_id=f"{job_id}.candidate-experiment.requested",
                    tenant_id=origin.tenant_id,
                    cell_id=origin.cell_id,
                    run_id=origin.run_id,
                    source_job_id=origin.source_job_id,
                    route_id=origin.route_id,
                    action_generation=len(origin.candidate_terminal_history_chain) + 1,
                    job_id=job_id,
                    source_payload_ref=origin.source_payload_ref,
                    capability_manifest_ref=origin.capability_manifest_ref,
                    request_content_hash=origin.request_content_hash,
                    policy_scope=origin.policy_scope,
                    policy_ref=origin.policy_ref,
                    authority_decision_ref=artifacts.profile_bound_ref(
                        self.control_service._artifact_store,
                        artifacts.ArtifactRef(
                            artifact_id=artifacts.ArtifactID.model_validate(decision_ref),
                            kind="runtime_quality.agent_action_authority_decision",
                            media_type="application/json",
                        ),
                    ),
                    voi_decision=origin.source_cycle.voi_decision,
                    coarse_phase="requested",
                    receipt_phase="requested",
                    recovery_state="none",
                    predecessor_receipt_ref=None,
                    owner_receipt_refs=(),
                    generated_at=datetime.now(UTC),
                )
                prepared = phase_owner.prepare_experiment_phase_publication(phase, request)
            payload = {
                "action_kind": CANDIDATE_EXPERIMENT_ACTION_KIND,
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": route_id,
                "request": request.model_dump(mode="json"),
                "decision_ref": decision_ref,
            }
            self.control_service.enqueue_acquisition_job(
                job_id=job_id,
                run_id=run_id,
                payload=payload,
                request_id=request_id,
                principal=principal,
                prepared_acquisition_action_head=prepared,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            code = str(getattr(exc, "code", "") or exc)
            raise AcquisitionActionServiceError(
                code
                if code.startswith("candidate_experiment_")
                else "candidate_experiment_enqueue_not_established"
            ) from exc
        return AcquisitionExecutionResponse(
            run_id=run_id,
            route_id=route_id,
            job_id=job_id,
            authority_decision_ref=decision_ref,
        )

    def _handle_candidate_experiment_job(
        self,
        job: ControlJobRecord,
        payload: dict[str, Any],
        execution_scope: ControlJobExecutionScope,
    ) -> dict[str, Any]:
        """Execute or recover one candidate source under the exact running job lease."""
        from polisyos.runtime.http.services.acquisition_surface_execution import (
            WorldBankWDIAcquisitionExecutionPort,
        )
        from polisyos.runtime.quality.acquisition_route_loop import (
            AcquisitionCandidateExperimentTerminalReceipt,
        )
        from polisyos.runtime.quality.acquisition_world_growth import (
            AcquisitionWorldGrowthBridge,
        )

        if (
            job.kind != "acquisition"
            or job.run_id is None
            or job.state != "running"
            or execution_scope.status != "established"
            or not execution_scope.actor_authenticated
            or not execution_scope.tenant_id
            or not execution_scope.cell_id
        ):
            raise AcquisitionActionServiceError(
                "candidate_experiment_running_lease_not_established"
            )
        tenant_id = execution_scope.tenant_id
        cell_id = execution_scope.cell_id
        run_id = job.run_id
        from polisyos.runtime.http.services.control.job_attempt_publication import (
            _EXECUTION_INTENT_BINDING_KEY,
        )

        try:
            payload = ControlPlaneService._job_payload_without_telemetry(payload)
        except (TypeError, ValueError) as exc:
            raise AcquisitionActionServiceError(
                "candidate_experiment_job_payload_telemetry_invalid"
            ) from exc
        allowed_payload_keys = {
            "action_kind",
            "job_id",
            "tenant_id",
            "cell_id",
            "run_id",
            "route_id",
            "request",
            "decision_ref",
            _EXECUTION_INTENT_BINDING_KEY,
        }
        if set(payload) - allowed_payload_keys:
            raise AcquisitionActionServiceError("candidate_experiment_job_payload_fields_invalid")
        request = CandidateExperimentRouteMutationRequest.model_validate(payload.get("request"))
        route_id = str(payload.get("route_id") or "")
        decision_ref = str(payload.get("decision_ref") or "")
        if (
            payload.get("tenant_id") != tenant_id
            or payload.get("cell_id") != cell_id
            or payload.get("run_id") != run_id
            or payload.get("job_id") != job.job_id
            or payload.get("action_kind") != CANDIDATE_EXPERIMENT_ACTION_KIND
            or not decision_ref.startswith("sha256:")
            or route_id != request.route_id
        ):
            raise AcquisitionActionServiceError("candidate_experiment_job_payload_scope_mismatch")
        admission = self.control_service._control_store.current_execution_job_admission()
        if (
            not admission.matches_job_record(job)
            or admission.job.state != "running"
            or admission.scope != execution_scope
        ):
            raise AcquisitionActionServiceError("candidate_experiment_running_lease_changed")
        loop = self._candidate_experiment_loop(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        )
        try:
            origin = loop.resolve_current_candidate_experiment(
                run_id=run_id,
                action_job_id=job.job_id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise AcquisitionRouteRecoveryRequired(
                "candidate_experiment_action_history_not_current"
            ) from exc
        if route_id != origin.route_id or job.job_id != self._candidate_experiment_job_id(
            origin, request
        ):
            raise AcquisitionActionServiceError("candidate_experiment_job_identity_mismatch")
        sink = self.control_service.acquisition_route_sink
        outcomes = sink.experiment_action_outcomes(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            source_job_id=origin.source_job_id,
            route_id=origin.route_id,
        )
        if not outcomes or outcomes[-1].head.job_id != job.job_id:
            raise AcquisitionRouteRecoveryRequired("candidate_experiment_action_head_missing")
        outcome = outcomes[-1]
        head = outcome.head
        if head.job_id != job.job_id:
            raise AcquisitionActionServiceError("candidate_experiment_action_head_job_mismatch")
        if type(outcome.latest_receipt) is AcquisitionCandidateExperimentTerminalReceipt:
            return self._candidate_experiment_terminal_progress(outcome)
        phase_chain = outcome.phase_chain
        if not phase_chain:
            raise AcquisitionRouteRecoveryRequired("candidate_experiment_phase_history_missing")
        latest = phase_chain[-1]
        phase = latest.receipt
        if type(phase) is not AcquisitionCandidateExperimentPhaseReceipt:
            raise AcquisitionRouteRecoveryRequired("candidate_experiment_phase_history_untyped")
        port = self._require_candidate_experiment_execution_port()
        if (
            type(port) is not WorldBankWDIAcquisitionExecutionPort
            or type(port._world_growth_bridge) is not AcquisitionWorldGrowthBridge
        ):
            raise AcquisitionActionServiceError("candidate_experiment_execution_owner_missing")
        if phase.receipt_phase == "requested":
            try:
                decision_history = self.load_candidate_experiment_decision_history(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=run_id,
                    route_id=route_id,
                    request=request,
                    job_id=job.job_id,
                    decision_ref=decision_ref,
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise AcquisitionActionServiceError(
                    "candidate_experiment_worker_decision_history_not_established"
                ) from exc
            permission = decision_history.decision.permission_snapshot
            if (
                decision_history.current_authority != "not_revalidated"
                or decision_history.decision_ref != decision_ref
                or decision_ref != f"sha256:{decision_history.payload_sha256}"
                or decision_history.decision.outcome != "allowed"
                or permission is None
                or permission.subject != job.submitted_by
                or permission.subject != execution_scope.actor_subject
                or permission.tenant_id != tenant_id
                or phase.authority_decision_ref.artifact_id
                != artifacts.ArtifactID.model_validate(decision_ref)
            ):
                raise AcquisitionActionServiceError(
                    "candidate_experiment_worker_decision_scope_mismatch"
                )
            operation, invocation, intent = self._candidate_experiment_action_tuple(origin, request)

            def _no_effect(_invocation: OperationInvocationRecord) -> object:
                raise RuntimeError("candidate-experiment readiness replay cannot invoke an effect")

            readiness_gateway = self.replay_candidate_experiment_authority(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                route_id=route_id,
                request=request,
                job_id=job.job_id,
                decision_ref=decision_ref,
                effect_handler=_no_effect,
            )
            readiness_decision = readiness_gateway.load_persisted_decision(decision_ref)
            if readiness_decision.decision != decision_history.decision:
                raise AcquisitionActionServiceError("candidate_experiment_current_pa2_changed")
            executing = phase.model_copy(
                update={
                    "receipt_id": f"{job.job_id}.candidate-experiment.executing",
                    "coarse_phase": "executing",
                    "receipt_phase": "executing",
                    "recovery_state": "none",
                    "predecessor_receipt_ref": latest.receipt_ref,
                    "generated_at": datetime.now(UTC),
                }
            )
            executing_head = sink.persist_experiment_phase(executing)
            if executing_head.receipt_phase != "executing":
                raise AcquisitionRouteRecoveryRequired(
                    "candidate_experiment_executing_head_not_established"
                )
            action_phase_ref = executing_head.receipt_ref

            def _effect(_invocation: OperationInvocationRecord) -> object:
                return port.execute_candidate_experiment(
                    origin=origin,
                    action_phase_ref=action_phase_ref,
                )

            gateway = self.replay_candidate_experiment_authority(
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=run_id,
                route_id=route_id,
                request=request,
                job_id=job.job_id,
                decision_ref=decision_ref,
                effect_handler=_effect,
            )
            persisted = gateway.load_persisted_decision(decision_ref)
            if persisted.decision.outcome != "allowed":
                raise AcquisitionActionServiceError("candidate_experiment_pa2_decision_not_allowed")
            result = gateway.execute_bound_effect(
                operation=operation,
                invocation=invocation,
                intent=intent,
                persisted=persisted,
            )
            selected_ref = getattr(result, "candidate_action_ref", None)
            if (
                type(result) is not AcquisitionOwnerExecutionResult
                or result.disposition != "candidate_input_prepared"
                or result.action_phase_ref != action_phase_ref
                or selected_ref is None
            ):
                raise AcquisitionRouteRecoveryRequired(
                    "candidate_experiment_source_action_not_selected"
                )
            phase = executing
            phase_ref = action_phase_ref
        elif phase.receipt_phase == "executing":
            bridge = port._world_growth_bridge
            recovered = bridge.recover_candidate_experiment_action(
                origin=origin,
                action_phase_ref=latest.receipt_ref,
            )
            if recovered is None:
                raise AcquisitionRouteRecoveryRequired(
                    "candidate_experiment_effect_outcome_unresolved"
                )
            selected_ref, _action = recovered
            phase = phase_chain[-1].receipt
            phase_ref = latest.receipt_ref
        elif phase.receipt_phase in {"outcome_selected", "candidate_input_reentry_pending"}:
            phase_ref = latest.receipt_ref
            selected_ref = phase.candidate_receipt_ref
        else:
            raise AcquisitionRouteRecoveryRequired("candidate_experiment_phase_not_recoverable")
        if phase.receipt_phase in {"executing", "outcome_selected"}:
            predecessor_ref = (
                phase_ref if phase.receipt_phase == "executing" else latest.receipt_ref
            )
            selected = phase.model_copy(
                update={
                    "receipt_id": (
                        f"{job.job_id}.candidate-experiment.outcome-selected"
                        if phase.receipt_phase == "executing"
                        else phase.receipt_id
                    ),
                    "receipt_phase": "outcome_selected",
                    "candidate_receipt_ref": selected_ref,
                    "owner_receipt_refs": (str(selected_ref.artifact_id),),
                    "predecessor_receipt_ref": predecessor_ref,
                    "generated_at": (
                        datetime.now(UTC)
                        if phase.receipt_phase == "executing"
                        else phase.generated_at
                    ),
                }
            )
            selected_head = (
                sink.persist_experiment_phase(selected)
                if phase.receipt_phase == "executing"
                else head
            )
            if selected_head.receipt_phase != "outcome_selected":
                raise AcquisitionRouteRecoveryRequired(
                    "candidate_experiment_outcome_head_not_established"
                )
            pending = selected.model_copy(
                update={
                    "receipt_id": f"{job.job_id}.candidate-experiment.reentry-pending",
                    "coarse_phase": "candidate_input_prepared",
                    "receipt_phase": "candidate_input_reentry_pending",
                    "recovery_state": "reentry_recovery_required",
                    "predecessor_receipt_ref": selected_head.receipt_ref,
                    "generated_at": datetime.now(UTC),
                }
            )
            pending_head = sink.persist_experiment_phase(pending)
            if pending_head.receipt_phase != "candidate_input_reentry_pending":
                raise AcquisitionRouteRecoveryRequired(
                    "candidate_experiment_reentry_head_not_established"
                )
            phase = pending
        if phase.receipt_phase != "candidate_input_reentry_pending" or selected_ref is None:
            raise AcquisitionRouteRecoveryRequired("candidate_experiment_reentry_pending_missing")
        admission = self.control_service._control_store.current_execution_job_admission()
        if not admission.matches_job_record(job) or admission.scope != execution_scope:
            raise AcquisitionActionServiceError("candidate_experiment_running_lease_changed")
        try:
            from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
                dispatch_candidate_experiment_evaluation,
            )
            from polisyos.runtime.quality.substrate_registry import (
                run_catalog_source_call,
            )

            catalog_source = self.control_service.catalog_serving_source

            def _dispatch_and_verify() -> object:
                terminal_head = dispatch_candidate_experiment_evaluation(
                    bridge=port._world_growth_bridge,
                    origin=origin,
                )
                return sink.verify_action_head(terminal_head)

            final = run_catalog_source_call(catalog_source, _dispatch_and_verify)
        except AcquisitionRouteRecoveryRequired:
            raise
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise AcquisitionRouteRecoveryRequired(
                "candidate_experiment_evaluation_recovery_required"
            ) from exc
        return self._candidate_experiment_terminal_progress(final)

    @staticmethod
    def _candidate_experiment_terminal_progress(
        outcome: object,
    ) -> dict[str, Any]:
        """Project only a verified experiment terminal to generic job completion."""
        from polisyos.runtime.http.services.control.run_lifecycle import (
            VerifiedAcquisitionActionOutcome,
        )
        from polisyos.runtime.quality.acquisition_evaluation import (
            CandidateExperimentTerminalHistory,
        )
        from polisyos.runtime.quality.acquisition_route_loop import (
            AcquisitionCandidateExperimentTerminalReceipt,
        )

        if (
            type(outcome) is not VerifiedAcquisitionActionOutcome
            or type(outcome.latest_receipt) is not AcquisitionCandidateExperimentTerminalReceipt
            or type(outcome.candidate_experiment_terminal_history)
            is not CandidateExperimentTerminalHistory
            or outcome.candidate_experiment_terminal_history.head != outcome.head
        ):
            raise AcquisitionRouteRecoveryRequired("candidate_experiment_terminal_not_verified")
        return {
            "state": "completed",
            "phase": "candidate_experiment",
            "receipt_phase": "terminal",
            "terminal_outcome": outcome.latest_receipt.terminal_outcome,
            "terminal_receipt_ref": outcome.head.receipt_ref,
        }

    @staticmethod
    def _candidate_experiment_action_tuple(
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
    ) -> tuple[OperationContract, OperationInvocationRecord, AgentActionIntent]:
        """Bind the candidate policy, source, replay pins, and request into PA2."""
        binding = agent_action_content_hash(
            {
                "tenant_id": origin.tenant_id,
                "cell_id": origin.cell_id,
                "run_id": origin.run_id,
                "source_job_id": origin.source_job_id,
                "source_payload_ref": origin.source_payload_ref,
                "request_content_hash": origin.request_content_hash,
                "route_id": origin.route_id,
                "policy_ref": origin.policy_ref.model_dump(mode="json"),
                "policy_scope": origin.policy_scope.model_dump(mode="json"),
                "replay_pins": request.replay_pins.model_dump(mode="json"),
                "idempotency_key": request.idempotency_key,
                "human_decision_record_ref": request.human_decision_record_ref,
                "action_job_id": AcquisitionActionService._candidate_experiment_job_id(
                    origin, request
                ),
            }
        )
        operation = OperationContract(
            operation_id=CANDIDATE_EXPERIMENT_ACTION_KIND,
            operation_version="v1",
            operation_class=OperationClass.ACQUIRE,
            consumes=[],
            produces=[],
            formal_preconditions=[],
            allowed_internal_execution=["tool_call"],
            implementation_refs=[
                {
                    "module": "polisyos.runtime.http.services.acquisition_action_service",
                    "symbol": "AcquisitionActionService.request_candidate_experiment_decision",
                }
            ],
            cost_model={"monetary_cost": "not_established"},
            authority_transform={"kind": "preserves"},
            failure_modes=["authority_refused", "candidate_source_changed"],
            repair_options=[OperationClass.ESCALATE],
        )
        invocation = OperationInvocationRecord(
            invocation_id=f"candidate-experiment.execute.{binding.removeprefix('sha256:')}",
            operation_id=operation.operation_id,
            operation_version=operation.operation_version,
            workspace_id=origin.run_id,
            cycle_index=origin.effective_source_cycle.cycle_index,
            selected_by={"producer": "runtime.acquisition_route_loop"},
            selection_rationale_ref=origin.route_id,
            input_artifacts=[],
            parameters={
                "route_id": origin.route_id,
                "source_job_id": origin.source_job_id,
                "source_payload_ref": origin.source_payload_ref,
                "request_content_hash": origin.request_content_hash,
                "policy_ref": request.replay_pins.policy_ref.model_dump(mode="json"),
                "candidate_digest": request.replay_pins.candidate_digest,
                "replay_pins": request.replay_pins.model_dump(mode="json"),
                "idempotency_key": request.idempotency_key,
                "human_decision_record_ref": request.human_decision_record_ref,
                "action_job_id": AcquisitionActionService._candidate_experiment_job_id(
                    origin, request
                ),
            },
            internal_trace={"phase": "candidate_experiment_decision_only"},
            tool_calls=[],
            human_requests=[],
            output_artifacts=[],
            applicability_result="applicable",
            budget_delta={"candidate_experiment_actions": 1},
            status="started",
        )
        return (
            operation,
            invocation,
            AgentActionIntent(action_kind=CANDIDATE_EXPERIMENT_ACTION_KIND),
        )

    @staticmethod
    def _candidate_experiment_job_id(
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
    ) -> str:
        """Derive one stable decision identity without introducing a phase receipt."""
        binding = agent_action_content_hash(
            {
                "tenant_id": origin.tenant_id,
                "cell_id": origin.cell_id,
                "run_id": origin.run_id,
                "source_job_id": origin.source_job_id,
                "route_id": origin.route_id,
                "request_content_hash": origin.request_content_hash,
                "replay_pins": request.replay_pins.model_dump(mode="json"),
                "idempotency_key": request.idempotency_key,
                "human_decision_record_ref": request.human_decision_record_ref,
            }
        )
        return f"candidate-experiment-{binding.removeprefix('sha256:')}"

    def _require_candidate_experiment_authority_provider(
        self,
    ) -> AcquisitionAuthorityGatewayProvider:
        provider = self._require_authority_provider()
        if not callable(getattr(provider, "for_candidate_experiment_request", None)):
            raise AcquisitionActionServiceError("candidate_experiment_authority_producer_missing")
        return provider

    def _resolve(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        action_job_id: str | None = None,
    ) -> VerifiedAcquisitionRouteClosure:
        if not tenant_id or not cell_id or not run_id:
            raise AcquisitionActionServiceError("acquisition_actor_scope_missing")
        loop = AcquisitionRouteLoop(
            control_store=self.control_service._control_store,
            artifact_store=self.control_service._artifact_store,
            event_log=self.control_service._diagnostic_event_log,
            core_source_resolver=(
                self.control_service.resolve_completed_control_job_core_run_source
            ),
            tenant_id=tenant_id,
            cell_id=cell_id,
            action_outcome_reader=self.control_service.acquisition_route_sink,
        )
        try:
            return loop.resolve_current_route(run_id=run_id, action_job_id=action_job_id)
        except AcquisitionRouteClosureError as exc:
            raise AcquisitionActionServiceError(exc.code) from exc

    def _projection(self, closure: VerifiedAcquisitionRouteClosure) -> AcquisitionRouteProjection:
        from polisyos.runtime.quality.acquisition_executor import (
            SemanticEpochAdmissionResolutionError,
        )

        execution_bridge_installed = self._production_execution_bridge_installed()
        growth_status: Literal["not_established", "no_growth", "admitted_delta"] = "not_established"
        growth = None
        try:
            execution_ready = self._production_execution_bridge_ready(closure)
            if execution_bridge_installed:
                growth_status, growth = (
                    self._production_execution_port.project_world_growth_outcome(closure)
                )
        except (SemanticEpochAdmissionResolutionError, ValueError, OSError) as exc:
            raise AcquisitionActionServiceError("acquisition_native_admission_unverified") from exc
        authority_nonclosures = getattr(
            self._authority_provider,
            "external_nonclosures",
            (
                "current_mandate_owner:producer_missing",
                "deterministic_admission_bundle:producer_missing",
            ),
        )
        return AcquisitionRouteProjection(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            route_id=closure.route_id,
            route_projection_hash=closure.route_id,
            planner_report_hash=agent_action_content_hash(closure.planner_report),
            planner_record_id=closure.planner_record.acquisition_id,
            recommended_strategy=closure.planner_record.recommended_strategy.value,
            cost_basis=closure.cost_basis_record.model_dump(mode="json"),
            replay_pins=self._pins(closure),
            authority_capability=(
                "ready"
                if execution_ready
                and getattr(self._authority_provider, "authority_available", False)
                else "producer_missing"
            ),
            execution_capability=("ready" if execution_ready else "producer_missing"),
            qualification_status="activated" if growth is not None else "pending_epoch_activation",
            qualification_predicate="independently_reconciled"
            if growth is not None
            else "not_established",
            qualification_reason="native_owner_readback"
            if growth is not None
            else "policy_admission_missing",
            world_growth=growth_status,
            admitted_observation_delta=(
                None
                if growth_status == "not_established"
                else (0 if growth_status == "no_growth" else growth.admitted_observation_delta)
            ),
            authority_badge="native_owner_verified"
            if growth is not None
            else "behavioral_fixture_not_production",
            external_nonclosures=(
                *(("fresh_positive_production_route:artifact_missing",) if growth is None else ()),
                *authority_nonclosures,
                "connector_families_except_worldbank.wdi:surface_out_of_scope",
                *(
                    ("non_fixture_n13b_owner_port:bridge_missing",)
                    if not execution_bridge_installed
                    else (
                        ("worldbank.wdi_route_binding:producer_missing",)
                        if not execution_ready
                        else ()
                    )
                ),
            ),
        )

    def _validated_mutation(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: AcquisitionRouteMutationRequest,
    ) -> _ValidatedAcquisitionMutation:
        """Bind the deterministic action identity before folding route history."""
        job_id = self._job_id_for_request(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            route_id=route_id,
            request=request,
        )
        closure = self._resolve(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            action_job_id=job_id,
        )
        if (
            closure.route_id != route_id
            or request.route_projection_hash != closure.route_id
            or request.planner_report_hash != agent_action_content_hash(closure.planner_report)
            or request.replay_pins != self._pins(closure)
        ):
            raise AcquisitionActionServiceError("acquisition_route_revalidation_required")
        return _ValidatedAcquisitionMutation(closure=closure, job_id=job_id)

    @staticmethod
    def _pins(closure: VerifiedAcquisitionRouteClosure) -> AcquisitionRouteReplayPins:
        return AcquisitionRouteReplayPins(
            source_job_id=closure.source_job_id,
            compiled_ref=closure.compiled_ref,
            compiled_content_hash=closure.compiled_content_hash,
            terminal_event_id=closure.terminal_event_id,
            design_problem_ref=closure.design_problem_ref,
            cost_basis_hash=closure.cost_basis_hash,
        )

    @staticmethod
    def _action_tuple(
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
    ) -> tuple[OperationContract, OperationInvocationRecord, AgentActionIntent]:
        operation = OperationContract(
            operation_id=ACQUISITION_ACTION_KIND,
            operation_version="v1",
            operation_class=OperationClass.ACQUIRE,
            consumes=[],
            produces=[],
            formal_preconditions=[],
            allowed_internal_execution=["tool_call"],
            implementation_refs=[
                {
                    "module": "polisyos.runtime.http.services.acquisition_action_service",
                    "symbol": "AcquisitionExecutionPort.execute",
                }
            ],
            cost_model={"cost_basis_hash": closure.cost_basis_hash},
            authority_transform={"kind": "preserves"},
            failure_modes=[
                "authority_refused",
                "owner_port_failed",
                "reentry_recovery_required",
            ],
            repair_options=[OperationClass.ESCALATE],
        )
        binding = agent_action_content_hash(
            {
                "tenant_id": closure.tenant_id,
                "cell_id": closure.cell_id,
                "run_id": closure.run_id,
                "route_id": closure.route_id,
                "planner_report_hash": request.planner_report_hash,
                "replay_pins": request.replay_pins.model_dump(mode="json"),
                "idempotency_key": request.idempotency_key,
            }
        )
        invocation = OperationInvocationRecord(
            invocation_id=f"acquisition.execute.{binding.removeprefix('sha256:')}",
            operation_id=operation.operation_id,
            operation_version=operation.operation_version,
            workspace_id=closure.run_id,
            cycle_index=closure.source_cycle.cycle_index,
            selected_by={"producer": "runtime.acquisition_route_loop"},
            selection_rationale_ref=closure.route_id,
            input_artifacts=[],
            parameters={
                "route_id": closure.route_id,
                "planner_report_hash": request.planner_report_hash,
                "cost_basis_hash": closure.cost_basis_hash,
                "compiled_ref": closure.compiled_ref,
            },
            internal_trace={"phase": "deferred_acquisition_reservation"},
            tool_calls=[],
            human_requests=[],
            output_artifacts=[],
            applicability_result="applicable",
            budget_delta={"acquisition_actions": 1},
            status="started",
        )
        return (
            operation,
            invocation,
            AgentActionIntent(action_kind=ACQUISITION_ACTION_KIND),
        )

    @staticmethod
    def _job_id(
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
    ) -> str:
        return AcquisitionActionService._job_id_for_request(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            route_id=closure.route_id,
            request=request,
        )

    @staticmethod
    def _job_id_for_request(
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        route_id: str,
        request: AcquisitionRouteMutationRequest,
    ) -> str:
        payload = (
            f"{tenant_id}\0{cell_id}\0{run_id}\0{route_id}\0"
            f"{request.planner_report_hash}\0{request.idempotency_key}\0"
            f"{request.human_decision_record_ref or ''}"
        ).encode()
        return f"acquisition-{hashlib.sha256(payload).hexdigest()}"

    def _action_generation(self, closure: VerifiedAcquisitionRouteClosure, job_id: str) -> int:
        try:
            return self.control_service.acquisition_route_sink.resolve_action_generation(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                route_id=closure.route_id,
                job_id=job_id,
            )
        except (ValueError, RuntimeError, OSError) as exc:
            raise AcquisitionActionServiceError("acquisition_action_generation_unverified") from exc

    @staticmethod
    def _phase_receipt(
        *,
        closure: VerifiedAcquisitionRouteClosure,
        job_id: str,
        decision_ref: str,
        receipt_phase: Literal[
            "requested",
            "executing",
            "world_committed_reentry_pending",
            "candidate_input_reentry_pending",
        ],
        predecessor_receipt_ref: str | None,
        owner_receipt_refs: tuple[str, ...],
        action_generation: int = 1,
        candidate_receipt_ref: artifacts.ArtifactRef | None = None,
    ) -> AcquisitionRoutePhaseReceipt:
        coarse, recovery = {
            "requested": ("requested", "none"),
            "executing": ("executing", "none"),
            "world_committed_reentry_pending": (
                "world_committed",
                "reentry_recovery_required",
            ),
            "candidate_input_reentry_pending": (
                "candidate_input_prepared",
                "reentry_recovery_required",
            ),
        }[receipt_phase]
        return AcquisitionRoutePhaseReceipt(
            schema_version=(
                "AcquisitionRoutePhaseReceipt@1.2"
                if receipt_phase == "candidate_input_reentry_pending"
                else "AcquisitionRoutePhaseReceipt@1.0"
            ),
            receipt_id=f"{job_id}.{receipt_phase}",
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
            action_generation=action_generation,
            job_id=job_id,
            compiled_ref=closure.compiled_ref,
            planner_report_hash=agent_action_content_hash(closure.planner_report),
            cost_basis_hash=closure.cost_basis_hash,
            decision_ref=decision_ref,
            coarse_phase=coarse,
            receipt_phase=receipt_phase,
            recovery_state=recovery,
            predecessor_receipt_ref=predecessor_receipt_ref,
            owner_receipt_refs=owner_receipt_refs,
            candidate_receipt_ref=candidate_receipt_ref,
            generated_at=datetime.now(UTC),
        )

    @staticmethod
    def _terminal_receipt(
        *,
        closure: VerifiedAcquisitionRouteClosure,
        job_id: str,
        decision_ref: str,
        predecessor_receipt_ref: str,
        owner_receipt_refs: tuple[str, ...],
        action_generation: int = 1,
    ) -> AcquisitionRouteLoopReceipt:
        return AcquisitionRouteLoopReceipt(
            receipt_id=f"{job_id}.terminal",
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
            action_generation=action_generation,
            job_id=job_id,
            compiled_ref=closure.compiled_ref,
            planner_report_hash=agent_action_content_hash(closure.planner_report),
            cost_basis_hash=closure.cost_basis_hash,
            decision_ref=decision_ref,
            terminal_outcome="quarantined_no_growth",
            predecessor_receipt_ref=predecessor_receipt_ref,
            owner_receipt_refs=owner_receipt_refs,
            reentry_receipt_ref=None,
            generated_at=datetime.now(UTC),
        )

    def _read_phase_receipt(self, ref: str) -> AcquisitionRoutePhaseReceipt:
        try:
            return AcquisitionRoutePhaseReceipt.model_validate(
                require_declared_profile(
                    read_core_json_artifact(self.control_service._artifact_store, ref)
                )
            )
        except Exception as exc:
            raise AcquisitionActionServiceError("acquisition_phase_readback_failed") from exc

    @staticmethod
    def _terminal_progress(head: AcquisitionActionHeadRecord) -> dict[str, Any]:
        if head.receipt_phase != "terminal":
            raise AcquisitionActionServiceError("acquisition_terminal_head_missing")
        return {
            "state": "completed",
            "phase": "acquisition",
            "receipt_phase": "terminal",
            "terminal_receipt_ref": head.receipt_ref,
        }

    def _require_authority_provider(self) -> AcquisitionAuthorityGatewayProvider:
        if self._authority_provider is None:
            raise AcquisitionActionServiceError("acquisition_authority_producer_missing")
        return self._authority_provider

    def _production_execution_bridge_installed(self) -> bool:
        from .acquisition_surface_execution import WorldBankWDIAcquisitionExecutionPort

        production_port = getattr(self, "_production_execution_port", None)
        return (
            type(production_port) is WorldBankWDIAcquisitionExecutionPort
            and self._execution_port is production_port
        )

    def _production_execution_bridge_ready(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> bool:
        from polisyos.runtime.quality.acquisition_executor import (
            LiveAcquisitionExecutionError,
        )

        production_port = getattr(self, "_production_execution_port", None)
        if not self._production_execution_bridge_installed():
            return False
        try:
            production_port.require_route_ready(closure)
        except (LiveAcquisitionExecutionError, AcquisitionActionServiceError):
            return False
        return True

    def _require_production_execution_bridge(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> None:
        """Refuse public reservation unless the exact route binding is executable."""

        from polisyos.runtime.quality.acquisition_executor import (
            LiveAcquisitionExecutionError,
            SemanticEpochAdmissionResolutionError,
        )

        production_port = getattr(self, "_production_execution_port", None)
        if not self._production_execution_bridge_installed():
            raise AcquisitionActionServiceError("acquisition_execution_bridge_missing")
        try:
            production_port.prepare_route_execution(closure)
        except AcquisitionActionServiceError:
            raise
        except LiveAcquisitionExecutionError as exc:
            raise AcquisitionActionServiceError(exc.code) from exc
        except (SemanticEpochAdmissionResolutionError, ValueError, OSError) as exc:
            raise AcquisitionActionServiceError("acquisition_native_admission_unverified") from exc

    def _require_execution_port(self) -> AcquisitionExecutionPort:
        if self._execution_port is None:
            raise AcquisitionActionServiceError("acquisition_execution_bridge_missing")
        return self._execution_port

    def _require_candidate_experiment_execution_port(
        self,
    ) -> WorldBankWDIAcquisitionExecutionPort:
        """Return the installed production owner for candidate-experiment effects."""
        from .acquisition_surface_execution import WorldBankWDIAcquisitionExecutionPort

        port = getattr(self, "_production_execution_port", None)
        if (
            type(port) is not WorldBankWDIAcquisitionExecutionPort
            or self._execution_port is not port
        ):
            raise AcquisitionActionServiceError("candidate_experiment_execution_owner_missing")
        if not callable(getattr(port, "execute_candidate_experiment", None)):
            raise AcquisitionActionServiceError("candidate_experiment_execution_owner_missing")
        return port


__all__ = [
    "AcquisitionActionService",
    "AcquisitionActionServiceError",
    "AcquisitionAuthorityGatewayProvider",
    "AcquisitionDecisionRequestResponse",
    "AcquisitionExecutionPort",
    "AcquisitionExecutionResponse",
    "AcquisitionOwnerExecutionResult",
    "AcquisitionRouteListResponse",
    "AcquisitionRouteMutationRequest",
    "AcquisitionRouteProjection",
    "AcquisitionRouteReplayPins",
    "CandidateExperimentCurrentActionProjection",
    "CandidateExperimentRouteExecutionRequest",
    "CandidateExperimentRouteMutationRequest",
    "CandidateExperimentRouteProjection",
    "CandidateExperimentRouteReplayPins",
]
