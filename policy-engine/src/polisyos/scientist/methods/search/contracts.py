"""Canonical ask/tell and funnel contracts for search runtimes.

This module intentionally contains only DTOs and protocols. The concrete
bridges for the legacy controller and funnel live in :mod:`adapters` and are
resolved lazily for the historical imports that remain part of the supported
surface. The lifecycle config protocol describes the existing facade object
structurally, so the owner does not import that facade back.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAdmission,
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    ObjectiveValue,
    _validate_objective_score_state,
)

if TYPE_CHECKING:
    from polisyos.scientist.methods.search.funnel.types import (
        FunnelOutcome,
        FunnelTicket,
    )

    # Runtime aliases resolve through __getattr__; avoid importing concrete adapters.
    LegacySearchServiceAdapter: type[Any]
    OrchestratorFunnelService: type[Any]


class CandidateStrategyContext(BaseModel):
    """Bind a strategy producer's subject to the payload sent to evaluators.

    Only the five fields produced by StrategyAdapter are transport fields.
    Other producer data belongs in ``subject`` and is never dropped by name.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    producer: Literal["strategy_adapter", "policy_design"] = "strategy_adapter"
    subject: dict[str, Any]
    strategy_fields: dict[
        Literal["candidate_id", "acquisition_value", "predicted_mean", "predicted_std", "source"],
        Any,
    ] = Field(default_factory=dict)
    policy_schema: bool = False
    policy_transport: bool = False


class CandidateProposal(BaseModel):
    """Carry the exact evaluated payload with an optional typed strategy binding.

    Unknown semantic inputs belong in ``payload``. Metadata other than the
    explicitly bound service iteration is refused at the evaluation boundary.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    strategy_context: CandidateStrategyContext | None = None
    service_iteration: int | None = Field(default=None, ge=0)


class EvaluationBundle(BaseModel):
    """Capture evaluator feedback returned by Stage A/B and promotion scoring."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    objective_value: float | None
    is_promising: bool
    score_status: ObjectiveScoreStatus = ObjectiveScoreStatus.NOT_ESTABLISHED
    score_assessment: ObjectiveScoreAssessment | None = None
    score_admission: ObjectiveScoreAdmission | None = None
    stage_a_passed: bool = True
    stage_b_result: dict[str, Any] | None = None
    duration_seconds: float = 0.0
    objective_details: list[Any] = Field(default_factory=list)
    policy_evaluation: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_score_state(self) -> EvaluationBundle:
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
        return self


class ParetoBasisScope(BaseModel):
    """Describe whether a view's required objective basis is actually declared."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    scope: Literal["declared", "observed_axis_union", "not_established"]
    coordinate_ids: list[str] = Field(default_factory=list)
    basis_ref: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_basis_scope(self) -> ParetoBasisScope:
        """Keep declared, observed, and unknown bases structurally distinct."""
        if any(not coordinate_id for coordinate_id in self.coordinate_ids):
            raise ValueError("Pareto basis contains an empty coordinate id")
        if len(set(self.coordinate_ids)) != len(self.coordinate_ids):
            raise ValueError("Pareto basis repeats a coordinate id")
        if self.scope == "declared" and (not self.coordinate_ids or not self.basis_ref):
            raise ValueError("declared Pareto basis requires coordinates and a basis ref")
        if self.scope == "observed_axis_union" and (
            not self.coordinate_ids or self.basis_ref is not None
        ):
            raise ValueError("observed Pareto basis requires observed coordinates only")
        if self.scope == "not_established" and (self.coordinate_ids or self.basis_ref):
            raise ValueError("unestablished Pareto basis cannot carry coordinates or a ref")
        return self


class ParetoViewAssessment(BaseModel):
    """Persist which eligible entries could be compared in one Pareto view."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[
        "complete",
        "partial",
        "no_usable_inputs",
        "basis_limited",
        "denominator_limited",
        "legacy_limited",
    ]
    coverage_status: Literal["complete", "partial", "no_usable_inputs"] | None = None
    basis_scope: ParetoBasisScope = Field(
        default_factory=lambda: ParetoBasisScope(scope="not_established")
    )
    input_count: int = Field(ge=0)
    assessed_count: int = Field(ge=0)
    unassessed_candidate_hashes: list[str] = Field(default_factory=list)
    missing_coordinate_ids_by_candidate_hash: dict[str, list[str]] = Field(default_factory=dict)
    non_finite_coordinate_ids_by_candidate_hash: dict[str, list[str]] = Field(default_factory=dict)
    unresolved_axis_contract_candidate_hashes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_coverage(self) -> ParetoViewAssessment:
        """Bind the coverage count to explicit unassessed candidate identities."""
        if self.coverage_status is None:
            object.__setattr__(
                self,
                "coverage_status",
                self.status
                if self.status in {"complete", "partial", "no_usable_inputs"}
                else "no_usable_inputs",
            )
        if self.basis_scope.scope != "declared" and self.status in {
            "complete",
            "partial",
            "no_usable_inputs",
        }:
            # Older assessments are conservative on read: measured coverage does
            # not establish that the policy objective basis itself is complete.
            object.__setattr__(self, "status", "basis_limited")
        if self.assessed_count + len(self.unassessed_candidate_hashes) != self.input_count:
            raise ValueError("Pareto view assessment does not cover every eligible entry")
        if len(set(self.unassessed_candidate_hashes)) != len(self.unassessed_candidate_hashes):
            raise ValueError("Pareto view assessment repeats an unassessed candidate")
        unassessed = set(self.unassessed_candidate_hashes)
        if not set(self.missing_coordinate_ids_by_candidate_hash) <= unassessed:
            raise ValueError("missing-coordinate assessment names an assessed candidate")
        if not set(self.non_finite_coordinate_ids_by_candidate_hash) <= unassessed:
            raise ValueError("non-finite assessment names an assessed candidate")
        if not set(self.unresolved_axis_contract_candidate_hashes) <= unassessed:
            raise ValueError("unresolved-axis assessment names an assessed candidate")
        if self.coverage_status == "complete" and (not self.input_count or unassessed):
            raise ValueError("complete coverage requires nonempty assessed inputs")
        if self.coverage_status == "partial" and (not self.assessed_count or not unassessed):
            raise ValueError("partial view assessment requires both assessed and omitted inputs")
        if self.coverage_status == "no_usable_inputs" and self.assessed_count:
            raise ValueError("no_usable_inputs cannot contain assessed entries")
        if self.status == "complete" and (
            self.basis_scope.scope != "declared" or self.coverage_status != "complete"
        ):
            raise ValueError(
                "complete view assessment requires complete coverage on a declared basis"
            )
        if self.status == "partial" and (
            self.basis_scope.scope != "declared" or self.coverage_status != "partial"
        ):
            raise ValueError(
                "partial view assessment requires partial coverage on a declared basis"
            )
        if self.status == "no_usable_inputs" and (
            self.basis_scope.scope != "declared" or self.coverage_status != "no_usable_inputs"
        ):
            raise ValueError("no_usable_inputs requires an established basis with no usable rows")
        if self.status == "basis_limited" and self.basis_scope.scope == "declared":
            raise ValueError("basis_limited requires an unestablished or observed-only basis")
        return self


class ParetoViewProjection(BaseModel):
    """Carry one view's assessed status alongside candidate and ranked members."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    view: str = Field(min_length=1)
    assessment: ParetoViewAssessment
    eligible_candidate_hashes: tuple[str, ...]
    candidate_frontier_hashes: tuple[str, ...] = ()
    ranked_frontier_hashes: tuple[str, ...] = ()
    unassessed_candidate_hashes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_projection(self) -> ParetoViewProjection:
        """Bind status-specific identity lists to one eligible denominator."""
        for name, values in (
            ("eligible candidates", self.eligible_candidate_hashes),
            ("candidate frontier", self.candidate_frontier_hashes),
            ("ranked frontier", self.ranked_frontier_hashes),
            ("unassessed candidates", self.unassessed_candidate_hashes),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"Pareto projection repeats a {name} member")
            if any(not value for value in values):
                raise ValueError(f"Pareto projection contains an empty {name} identity")
        if not set(self.ranked_frontier_hashes) <= set(self.candidate_frontier_hashes):
            raise ValueError("ranked Pareto members must belong to the candidate frontier")
        if self.assessment.status != "complete" and self.ranked_frontier_hashes:
            raise ValueError("limited Pareto projection cannot expose ranked members")
        eligible = set(self.eligible_candidate_hashes)
        if len(self.eligible_candidate_hashes) != self.assessment.input_count:
            raise ValueError(
                "Pareto projection eligible identities do not match the assessment denominator"
            )
        if not set(self.candidate_frontier_hashes) <= eligible:
            raise ValueError("Pareto candidate frontier contains an ineligible identity")
        if not set(self.assessment.unassessed_candidate_hashes) <= eligible:
            raise ValueError("Pareto assessment names an ineligible unassessed candidate identity")

        status = self.assessment.status
        if status in {"partial", "no_usable_inputs"}:
            expected_unassessed = set(self.assessment.unassessed_candidate_hashes)
        elif status == "complete":
            expected_unassessed = set()
        else:
            expected_unassessed = eligible
        if set(self.unassessed_candidate_hashes) != expected_unassessed:
            raise ValueError(
                "Pareto projection unassessed candidate identities do not match its status and assessment"
            )
        return self


class TellResult(BaseModel):
    """Return registry/frontier deltas and current-best feedback after `tell()`."""

    model_config = ConfigDict(extra="forbid")

    best_candidate: dict[str, Any] | None = None
    best_objective: float | None = None
    history_length: int = 0
    registry_update: dict[str, Any] = Field(default_factory=dict)
    lesson_cards: list[dict[str, Any]] = Field(default_factory=list)
    frontier_delta: list[dict[str, Any]] = Field(default_factory=list)
    pareto_projection: ParetoViewProjection | None = None


class SearchService(Protocol):
    """Expose candidate generation (`ask`) and evaluator feedback ingestion (`tell`)."""

    def ask(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]: ...

    def tell(
        self,
        candidate_id: str,
        evaluation: EvaluationBundle,
    ) -> TellResult: ...


class FunnelService(Protocol):
    """Submit candidates to a multi-fidelity funnel and fetch routed outcomes."""

    def submit(
        self,
        candidate: CandidateProposal,
        *,
        context: dict[str, Any] | None = None,
    ) -> FunnelTicket: ...

    def get_result(self, ticket: FunnelTicket | str) -> FunnelOutcome: ...


class SearchStatus(str, Enum):
    """Track the lifecycle state of a legacy search loop run."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    CONVERGED = "converged"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class SearchIteration:
    """Record one ask/evaluate step and the evaluator feedback for later proposals."""

    iteration: int
    candidate: dict[str, Any]
    objective_value: float | None
    objective_details: list[ObjectiveValue]
    is_promising: bool
    stage_a_passed: bool
    stage_b_result: dict[str, Any] | None
    duration_seconds: float
    policy_evaluation: Any | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    policy_evaluation_status: str = "missing"
    policy_evaluation_error: str | None = None
    score_status: ObjectiveScoreStatus = ObjectiveScoreStatus.NOT_ESTABLISHED
    score_assessment: ObjectiveScoreAssessment | None = None
    score_admission: ObjectiveScoreAdmission | None = None
    candidate_proposal: CandidateProposal | None = None
    candidate_ref: ArtifactRef | None = None
    evaluation_ref: ArtifactRef | None = None
    current_policy_reevaluation: bool = False

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


CandidatePayload = dict[str, Any]
SearchContext = dict[str, Any]
StageAEvaluator = Callable[
    [CandidatePayload, SearchContext], tuple[float | None, bool] | EvaluationBundle
]
StageBEvaluator = Callable[[CandidatePayload, SearchContext], dict[str, Any]]


class _SearchCandidateGenerator(Protocol):
    """Generate the next candidate proposal from search history and context."""

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Propose one JSON-compatible candidate for Stage A/B evaluation."""


class _SearchEvaluatorPorts(Protocol):
    """Describe the evaluator bundle consumed by the private lifecycle owner."""

    stage_a: StageAEvaluator
    stage_b: StageBEvaluator


class _SearchLifecycleConfig(Protocol):
    """Describe existing SearchConfig fields consumed by the lifecycle owner."""

    stopping: Any
    objective: Any
    max_iterations_hard_limit: int
    enable_stage_a: bool
    batch_size: int
    resource_arbiter: Any | None
    transfer_manager: Any | None
    transfer_fingerprint: Any | None
    initial_evaluations: list[dict[str, Any]]
    policy_objective_stack: Any | None
    pareto_registry: Any | None
    policy_source_store: Any | None
    pareto_objective_basis_by_view: dict[str, ParetoBasisScope]
    max_empty_generation_attempts: int
    producer_settlement_store: Any | None
    producer_run_binding: Any | None


@dataclass
class SearchResult:
    """Return the final champion candidate, history, and evaluation counters."""

    search_id: str
    status: SearchStatus
    best_candidate: dict[str, Any] | None
    best_objective: float
    iterations_completed: int
    history: list[SearchIteration]
    stopping_reason: str | None
    total_duration_seconds: float
    stage_a_evaluations: int
    stage_b_evaluations: int
    pareto_front: list[dict[str, Any]] = field(default_factory=list)
    telemetry: dict[str, Any] = field(default_factory=dict)
    pareto_projection: ParetoViewProjection | None = None


class GenerationTransition(str, Enum):
    """Typed transitions emitted by the candidate-generation boundary."""

    TRANSIENT_EMPTY = "transient_empty"
    EXHAUSTED = "exhausted"


class _EvaluationDisposition(str, Enum):
    """Classify one evaluated candidate at the run-state boundary."""

    ORDINARY = "ordinary"
    SENTINEL = "sentinel"


@dataclass(frozen=True)
class _EvaluationTransition:
    """Carry one candidate disposition and its detached history record."""

    disposition: _EvaluationDisposition
    record: SearchIteration


class _NativeSearchRunStatePort(Protocol):
    """Expose only the run-state fields used by the native driver."""

    evaluation_iterations: int
    generation_attempts: int
    empty_generation_attempts: int
    generation_transition: GenerationTransition | None

    def apply_evaluation_transition(self, transition: _EvaluationTransition) -> None: ...


class _StoppingCheckView(Protocol):
    """Expose the stop decision fields consumed by the native search driver."""

    @property
    def should_stop(self) -> bool: ...

    @property
    def reason(self) -> str | None: ...


class _StoppingCriterionPort(Protocol):
    """Describe the configured stop check without importing its implementation."""

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> _StoppingCheckView: ...


class _NativeSearchConfigPort(Protocol):
    """Expose only configuration consumed by the native search service."""

    @property
    def max_iterations_hard_limit(self) -> int: ...

    @property
    def max_empty_generation_attempts(self) -> int: ...

    @property
    def stopping(self) -> _StoppingCriterionPort: ...


class _NonReentrantLockPort(Protocol):
    """Expose the nonblocking acquisition and release used for one run."""

    def acquire(self, blocking: bool = True) -> bool: ...

    def release(self) -> None: ...


class _NativeSearchControllerPort(Protocol):
    """Describe controller-owned operations consumed by the native service driver."""

    @property
    def _config(self) -> _NativeSearchConfigPort: ...

    @property
    def _history(self) -> Sequence[SearchIteration]: ...

    @property
    def _run_lock(self) -> _NonReentrantLockPort: ...

    @property
    def _run_state(self) -> _NativeSearchRunStatePort: ...

    _status: SearchStatus

    def _prepare_service_run(self) -> None: ...

    def _generate_candidates(
        self,
        *,
        iteration: int,
        initial_candidate: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[dict[str, Any] | CandidateProposal]: ...

    def _accept_tell(
        self,
        *,
        candidate: dict[str, Any],
        objective_value: float | None,
        score_status: ObjectiveScoreStatus,
        objective_details: list[Any],
        is_promising: bool,
        stage_a_passed: bool,
        stage_b_result: dict[str, Any],
        duration_seconds: float,
        candidate_proposal: CandidateProposal | None = None,
    ) -> SearchIteration: ...

    def _service_tell_snapshot(self) -> dict[str, Any]: ...

    def _begin_native_run(self, initial_context: dict[str, Any]) -> datetime: ...

    def _finish_native_run(
        self,
        *,
        start_time: datetime,
        stopping_reason: str | None,
    ) -> SearchResult: ...

    def _refresh_budget_snapshot(self, context: dict[str, Any]) -> None: ...

    def _stopping_state(self) -> dict[str, Any]: ...

    def _to_history_dict(self, iteration: SearchIteration) -> dict[str, Any]: ...

    def _evaluate_candidate(
        self,
        candidate: dict[str, Any] | CandidateProposal,
        iteration: int,
        context: dict[str, Any],
    ) -> _EvaluationTransition: ...


# Resolve annotations in their defining module before preserving the historic pickle paths.
# Pydantic later reflects these dataclasses through the compatibility modules in ``__module__``;
# retain actual owner-bound types in both annotations and dataclass field metadata so resolution
# does not depend on whichever names happen to be imported by the legacy facade.
def _bind_legacy_search_record_annotations(record_type: type[Any]) -> None:
    resolved = get_type_hints(record_type, globalns=globals(), localns=globals())
    record_type.__annotations__ = resolved
    for record_field in fields(record_type):
        record_field.type = resolved[record_field.name]


for _legacy_search_record in (SearchIteration, SearchResult, _EvaluationTransition):
    _bind_legacy_search_record_annotations(_legacy_search_record)
del _legacy_search_record
del _bind_legacy_search_record_annotations

# Preserve the historic lookup paths for serialized search records.
SearchStatus.__module__ = "polisyos.scientist.methods.search.controller"
SearchIteration.__module__ = "polisyos.scientist.methods.search.controller"
SearchResult.__module__ = "polisyos.scientist.methods.search.controller"
GenerationTransition.__module__ = "polisyos.scientist.methods.search.run_state"
_EvaluationDisposition.__module__ = "polisyos.scientist.methods.search.run_state"
_EvaluationTransition.__module__ = "polisyos.scientist.methods.search.run_state"

_LAZY_ADAPTER_EXPORTS = frozenset(
    {
        "LegacySearchServiceAdapter",
        "OrchestratorFunnelService",
    }
)


def __getattr__(name: str) -> Any:
    """Resolve legacy bridge names without importing runtime implementations eagerly."""
    if name in _LAZY_ADAPTER_EXPORTS:
        module = importlib.import_module("polisyos.scientist.methods.search.adapters")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CandidateProposal",
    "CandidateStrategyContext",
    "EvaluationBundle",
    "FunnelService",
    "LegacySearchServiceAdapter",
    "OrchestratorFunnelService",
    "ParetoBasisScope",
    "ParetoViewAssessment",
    "ParetoViewProjection",
    "SearchService",
    "TellResult",
]
