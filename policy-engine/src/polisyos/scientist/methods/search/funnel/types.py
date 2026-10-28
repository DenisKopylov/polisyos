"""Core types for the multi-fidelity evaluation funnel."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from math import isfinite
from typing import TYPE_CHECKING, Any, Literal, NoReturn

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir import TypedFailureCard as TypedFailureCard
from polisyos.ir import UncertaintyType as UncertaintyType
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAdmission,
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    _policy_runtime_invocation_binding,
    _validate_objective_score_state,
)
from polisyos.scientist.methods.search.stage_contracts import SearchStage, StageResult
from polisyos.scientist.methods.search.uncertainty import (
    SearchUncertaintyCurrentRead as SearchUncertaintyCurrentRead,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope as UncertaintyEnvelope,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEstimate,
)

if TYPE_CHECKING:
    from polisyos.scientist.methods.search.contracts import CandidateProposal
    from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision

FunnelEvaluationStatus = Literal["not_evaluated", "partial", "evaluated"]
FunnelCostOrigin = Literal["reported", "estimated", "unknown"]
FunnelWorkPacketStatus = Literal["available", "unavailable", "rejected"]
RoutingAction = Literal[
    "advance",
    "defer",
    "reject",
    "retry_cheaper",
    "complete",
    "defer_to_human",
]
DegradationMode = Literal[
    "normal",
    "conservative_routing",
    "no_promotion",
    "reduced_judge",
    "freeze_frontier",
    "prior_free",
    "auto_cap",
]


def _validate_funnel_cost(amount: float | None, origin: FunnelCostOrigin) -> None:
    """Reject amounts that disagree with their source-evidence status."""
    if origin not in {"reported", "estimated", "unknown"}:
        raise ValueError("unsupported funnel cost origin")
    if amount is None:
        if origin != "unknown":
            raise ValueError("known funnel cost origin requires a cost amount")
        return
    if isinstance(amount, bool) or not isfinite(amount) or amount < 0.0:
        raise ValueError("funnel cost amount must be finite and non-negative")
    if origin == "unknown":
        raise ValueError("unknown funnel cost cannot carry an amount")


class FunnelExecutedWorkPacket(ArtifactMinimalityMixin):
    """Source-bound record of one completed native policy-runtime invocation.

    The current policy runtime does not execute a scientific draw loop. The
    invocation counter is therefore reported separately from requested draw
    configuration, while actual draw counters remain uninstrumented.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.1"
    authority_purpose: Literal["engineering_execution_observation"] = (
        "engineering_execution_observation"
    )
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(ArtifactFunction.REPLAY_AUDIT)
    )
    run_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    candidate_hash: str = Field(min_length=1)
    candidate_ref: ArtifactRef
    stage_level: Literal[3, 4]
    stage_name: Literal["funnel_L3_medium", "funnel_L4_full"]
    fidelity: Literal["medium", "full"]
    evaluation_attempt_id: str = Field(min_length=1)
    observed_at: AwareDatetime
    backend_kind: str = Field(min_length=1)
    work_unit: Literal["policy_runtime_evaluator_invocation"] = (
        "policy_runtime_evaluator_invocation"
    )
    attempted_invocation_count: Literal[1] = 1
    completed_invocation_count: Literal[1] = 1
    failed_invocation_count: Literal[0] = 0
    source_result_ref: ArtifactRef
    requested_draw_count: int | None = Field(default=None, ge=0, strict=True)
    requested_draw_source: Literal[
        "fidelity_default", "effective_estimation_config", "unavailable"
    ] = "unavailable"
    effective_estimation_config_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    draw_execution_status: Literal["not_instrumented"] = "not_instrumented"
    attempted_draw_count: None = None
    successful_draw_count: None = None
    failed_draw_count: None = None
    unattempted_draw_count: None = None
    input_signature: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _preserve_legacy_draw_source(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        if payload.get("schema_version") == "1.0" and "requested_draw_source" not in payload:
            payload["requested_draw_source"] = "fidelity_default"
        return payload

    @model_validator(mode="after")
    def _validate_runtime_binding(self) -> FunnelExecutedWorkPacket:
        if self.candidate_ref.kind != "scientist.policy_design.candidate":
            raise ValueError("work packet candidate_ref must identify a policy candidate")
        if self.source_result_ref.kind != "scientist.policy_evaluation_vector":
            raise ValueError("work packet source_result_ref must identify a policy evaluation")
        expected = {
            3: ("funnel_L3_medium", "medium"),
            4: ("funnel_L4_full", "full"),
        }[self.stage_level]
        if (self.stage_name, self.fidelity) != expected:
            raise ValueError("work packet stage and fidelity do not match")
        if self.schema_version == "1.0":
            if (
                self.requested_draw_source != "fidelity_default"
                or self.effective_estimation_config_sha256 is not None
            ):
                raise ValueError("legacy work packet draw source is invalid")
        elif self.requested_draw_source == "fidelity_default":
            raise ValueError("new work packets require a source-bound draw request")
        elif (
            _policy_runtime_invocation_binding(
                {
                    "evaluation_attempt_id": self.evaluation_attempt_id,
                    "requested_draw_count": self.requested_draw_count,
                    "requested_draw_source": self.requested_draw_source,
                    "effective_estimation_config_sha256": (self.effective_estimation_config_sha256),
                }
            )
            is None
        ):
            raise ValueError("new work packet runtime invocation tuple is invalid")
        return self


def parse_funnel_work_packet_feedback(
    feedback: Mapping[str, Any],
) -> tuple[ArtifactRef | None, FunnelWorkPacketStatus]:
    """Read the producer's typed packet reference claim for consumer admission."""
    raw_ref = feedback.get("policy_runtime_work_packet_ref")
    raw_status = feedback.get("policy_runtime_work_packet_status")
    if raw_ref is None:
        return None, "unavailable" if raw_status in {
            None,
            "unavailable",
        } else "rejected"
    try:
        ref = raw_ref if isinstance(raw_ref, ArtifactRef) else ArtifactRef.model_validate(raw_ref)
    except (TypeError, ValueError):
        return None, "rejected"
    if raw_status != "available":
        return None, "rejected"
    return ref, "available"


def statistical_uncertainty_from_ci_width(
    simulation_results: dict[str, Any],
    *,
    source: str,
    quantification_method: str,
    recommended_action: str | None = None,
) -> UncertaintyEstimate:
    """Build a statistical estimate without laundering missing CI data.

    A missing, malformed, non-finite, or negative confidence-interval width is
    unassessed uncertainty.  A finite zero width remains a measured zero-width
    interval, including when the effect itself is zero.
    """

    bootstrap = simulation_results.get("bootstrap")
    if not isinstance(bootstrap, Mapping) or "ci_width" not in bootstrap:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width missing",
            quantification_method="ci_width_missing",
            is_reducible=True,
            recommended_action=recommended_action,
        )

    raw_width = bootstrap.get("ci_width")
    if raw_width is None:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width missing",
            quantification_method="ci_width_missing",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    if isinstance(raw_width, bool):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width invalid",
            quantification_method="ci_width_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    try:
        ci_width = float(raw_width)
    except (TypeError, ValueError, OverflowError):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width invalid",
            quantification_method="ci_width_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    if not isfinite(ci_width) or ci_width < 0.0:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width invalid",
            quantification_method="ci_width_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )

    if "ate" not in simulation_results:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    raw_effect = simulation_results["ate"]
    if raw_effect is None or isinstance(raw_effect, bool):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    try:
        effect = abs(float(raw_effect))
    except (TypeError, ValueError, OverflowError):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    if not isfinite(effect):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )

    if effect == 0.0:
        level = 0.0 if ci_width == 0.0 else 1.0
    else:
        level = min(1.0, ci_width / (2.0 * effect))
    return UncertaintyEstimate(
        level=level,
        source=source,
        quantification_method=quantification_method,
        is_reducible=True,
        recommended_action=recommended_action,
    )


# ---------------------------------------------------------------------------
# §8.5 — CheapSignalVector
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CheapSignalVector:
    """Multi-dimensional cheap signal produced by Level 1 (blueprint §8.5).

    All scores are in [0, 1] unless documented otherwise.
    """

    structural_validity: float = 0.5
    causal_identifiability: float = 0.5
    positivity_risk: float = 0.5
    transportability_risk: float = 0.5
    uncertainty_prior: float = 0.5
    policy_conflict: float = 0.0
    feasibility: float = 0.5
    expected_value_proxy: float = 0.0
    expected_harm_proxy: float = 0.5
    expected_information_gain: float = 0.5

    def routing_decision(self) -> Literal["reject", "defer", "advance", "fast_track"]:
        """Deterministic routing based on vector thresholds (blueprint §8.5)."""
        if self.structural_validity < 0.5 or self.causal_identifiability < 0.2:
            return "reject"
        if self.positivity_risk > 0.8 or self.policy_conflict > 0.8:
            return "reject"
        if (
            self.expected_value_proxy > 0.9
            and self.feasibility > 0.8
            and self.expected_harm_proxy < 0.1
            and self.positivity_risk < 0.2
            and self.uncertainty_prior < 0.3
        ):
            return "fast_track"
        return "advance"


# ---------------------------------------------------------------------------
# §8.6 — FunnelStageResult and FunnelStage
# ---------------------------------------------------------------------------


@dataclass
class FunnelStageResult(StageResult):
    """Extended stage result carrying funnel-specific metadata."""

    uncertainty_envelope: UncertaintyEnvelope = field(
        default_factory=UncertaintyEnvelope.unknown,
    )
    cheap_signal: CheapSignalVector | None = None
    failure_cards: list[TypedFailureCard] = field(default_factory=list)
    compute_cost_usd: float | None = None
    compute_cost_origin: FunnelCostOrigin = "unknown"
    executed_work_packet_ref: ArtifactRef | None = None
    executed_work_packet_status: FunnelWorkPacketStatus = "unavailable"
    fidelity_level: int = 0
    audit_refs: list[ArtifactRef] = field(default_factory=list)
    uncertainty_observation_ref: ArtifactRef | None = None
    actionable_side_information_ref: ArtifactRef | None = None
    terminal_action: (
        Literal[
            "advance",
            "defer",
            "reject",
            "retry_cheaper",
            "complete",
            "defer_to_human",
        ]
        | None
    ) = None

    def __post_init__(self) -> None:
        """Keep score, cost, and work-packet states aligned."""
        super().__post_init__()
        _validate_funnel_cost(self.compute_cost_usd, self.compute_cost_origin)
        _validate_funnel_work_packet(
            self.executed_work_packet_ref,
            self.executed_work_packet_status,
        )

    @property
    def has_blockers(self) -> bool:
        return any(fc.is_blocker for fc in self.failure_cards)


def _validate_funnel_work_packet(
    ref: ArtifactRef | None,
    status: FunnelWorkPacketStatus,
) -> None:
    if status == "available" and ref is None:
        raise ValueError("available executed-work status requires a packet reference")
    if status == "unavailable" and ref is not None:
        raise ValueError("unavailable executed-work status cannot carry a packet reference")


@dataclass(slots=True)
class FunnelTraceStep:
    """Trace record for one stage execution."""

    fidelity_level: int
    stage_name: str
    objective_value: float | None
    is_promising: bool
    duration_seconds: float
    compute_cost_usd: float | None
    compute_cost_origin: FunnelCostOrigin
    score_status: ObjectiveScoreStatus = ObjectiveScoreStatus.NOT_ESTABLISHED
    score_assessment: ObjectiveScoreAssessment | None = None
    score_admission: ObjectiveScoreAdmission | None = None
    executed_work_packet_ref: ArtifactRef | None = None
    executed_work_packet_status: FunnelWorkPacketStatus = "unavailable"
    routing_decision: str | None = None
    voi_action: str | None = None
    voi_priority: float | None = None
    failure_count: int = 0
    blocker_count: int = 0

    def __post_init__(self) -> None:
        if self.score_admission is not None:
            self.score_status = self.score_admission.status
            if self.score_status is not ObjectiveScoreStatus.AVAILABLE:
                self.objective_value = None
            elif self.score_admission.reported_assessment != self.score_assessment:
                self.score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
                self.objective_value = None
            elif self.score_assessment is not None:
                self.objective_value = self.score_assessment.value
        elif self.score_assessment is None:
            if self.score_status is ObjectiveScoreStatus.AVAILABLE:
                self.score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
        else:
            self.score_status = self.score_assessment.status
            if self.score_status is ObjectiveScoreStatus.AVAILABLE:
                self.objective_value = self.score_assessment.value
        _validate_objective_score_state(self.objective_value, self.score_status)
        _validate_funnel_cost(self.compute_cost_usd, self.compute_cost_origin)
        _validate_funnel_work_packet(
            self.executed_work_packet_ref,
            self.executed_work_packet_status,
        )


class _FunnelTicketMethodMetricCapabilitySlot:
    """Hold a short-lived owner basis outside the ticket's dataclass fields."""

    __slots__ = ("_method_metric_projection_basis",)


@dataclass(slots=True)
class FunnelTicket(_FunnelTicketMethodMetricCapabilitySlot):
    """Stateful handle for one candidate moving through the funnel."""

    ticket_id: str
    candidate_hash: str
    candidate: dict[str, Any]
    context: dict[str, Any]
    submitted_via_cache: bool = False
    stage_results: dict[int, FunnelStageResult] = field(default_factory=dict)
    trace: list[FunnelTraceStep] = field(default_factory=list)
    current_level: int | None = None
    next_level: int | None = None
    final_action: RoutingAction = "advance"
    degradation_mode: DegradationMode = "normal"
    is_terminal: bool = False
    last_scheduling_decision: SchedulingDecision | None = None
    lesson_refs: list[ArtifactRef] = field(default_factory=list)
    correlation_recorded: bool = False
    lessons_finalized: bool = False
    cache_key: str = ""
    parent_ticket_id: str | None = None
    lineage: tuple[str, ...] = ()
    continuation_reason: str | None = None
    terminal_basis: str | None = None
    search_uncertainty_ticket_id: str | None = None
    search_uncertainty_generation: int | None = None
    search_uncertainty_task_binding_ref: ArtifactRef | None = None
    # The retained result history owner; the parent may itself be a reuse request.
    result_reuse_source_ticket_id: str | None = None
    candidate_proposal: CandidateProposal | None = None
    prior_attempt_ticket_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "_method_metric_projection_basis", None)

    def _set_method_metric_projection_basis(self, basis: object | None) -> None:
        """Replace the in-process-only source basis after a fresh owner lookup."""
        object.__setattr__(self, "_method_metric_projection_basis", basis)

    def __copy__(self) -> FunnelTicket:
        """Copy public state while dropping the ephemeral admission capability."""
        return replace(
            self,
            candidate=deepcopy(self.candidate),
            context=dict(self.context),
            candidate_proposal=deepcopy(self.candidate_proposal),
            stage_results=deepcopy(self.stage_results),
            trace=deepcopy(self.trace),
            lesson_refs=list(self.lesson_refs),
            lineage=tuple(self.lineage),
        )

    def __deepcopy__(self, memo: dict[int, Any]) -> FunnelTicket:
        """Deep-copy persisted ticket state without carrying the source capability."""
        duplicate = self.__copy__()
        memo[id(self)] = duplicate
        return duplicate

    def __reduce_ex__(self, protocol: int) -> NoReturn:
        """Refuse generic pickle snapshots of tickets containing live runtime context."""
        del protocol
        raise TypeError("FunnelTicket requires its explicit bounded work-packet serializer")

    @property
    def last_result(self) -> FunnelStageResult | None:
        if not self.stage_results:
            return None
        return self.stage_results[max(self.stage_results)]


@dataclass(slots=True)
class FunnelAttemptHistory:
    """Actual trace retained under the organizational attempt that ran it."""

    ticket_id: str
    trace: list[FunnelTraceStep] = field(default_factory=list)


@dataclass(slots=True)
class FunnelOutcome:
    """Aggregated view of one ticket's funnel execution state."""

    ticket_id: str
    candidate_hash: str
    trace: list[FunnelTraceStep]
    stage_results: dict[int, FunnelStageResult]
    final_result: FunnelStageResult | None
    failure_cards: list[TypedFailureCard]
    uncertainty_envelope: UncertaintyEnvelope
    compute_cost_usd: float | None
    compute_cost_origin: FunnelCostOrigin
    degradation_mode: DegradationMode
    final_action: RoutingAction
    completed: bool
    last_scheduling_decision: SchedulingDecision | None = None
    lesson_refs: list[ArtifactRef] = field(default_factory=list)
    audit_refs: list[ArtifactRef] = field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = field(default_factory=list)
    parent_ticket_id: str | None = None
    lineage: tuple[str, ...] = ()
    continuation_reason: str | None = None
    evaluation_status: FunnelEvaluationStatus = "evaluated"
    current_uncertainty_envelope: UncertaintyEnvelope | None = None
    uncertainty_observation_refs: list[ArtifactRef] = field(default_factory=list)
    uncertainty_intake_failures: list[str] = field(default_factory=list)
    search_uncertainty_current_read: SearchUncertaintyCurrentRead | None = None
    result_reuse_source_ticket_id: str | None = None
    prior_attempt_ticket_id: str | None = None
    prior_attempt_trace: list[FunnelTraceStep] = field(default_factory=list)
    prior_attempt_history: list[FunnelAttemptHistory] = field(default_factory=list)
    prior_attempt_history_status: Literal["complete", "verification_missing"] = "complete"

    def __post_init__(self) -> None:
        _validate_funnel_cost(self.compute_cost_usd, self.compute_cost_origin)


# Keep import, repr, and pickle resolution at the historical owner module.
_HISTORICAL_FUNNEL_MODULE = "polisyos.scientist.methods.search.funnel.orchestrator"
FunnelTraceStep.__module__ = _HISTORICAL_FUNNEL_MODULE
FunnelAttemptHistory.__module__ = _HISTORICAL_FUNNEL_MODULE
FunnelTicket.__module__ = _HISTORICAL_FUNNEL_MODULE
FunnelOutcome.__module__ = _HISTORICAL_FUNNEL_MODULE


class FunnelStage(SearchStage):
    """Abstract base for a stage within the multi-fidelity funnel.

    Extends ``SearchStage`` with fidelity metadata and richer result type.
    """

    @property
    @abstractmethod
    def fidelity_level(self) -> int:
        """Numeric fidelity level (0 = cheapest, higher = more expensive)."""
        ...

    @property
    @abstractmethod
    def estimated_cost_usd(self) -> float:
        """Estimated per-candidate cost in USD."""
        ...

    @abstractmethod
    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        """Evaluate a candidate and return a funnel-aware result."""
        ...
