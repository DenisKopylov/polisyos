"""Canonical ask/tell and funnel contracts for search runtimes.

This module intentionally contains only DTOs and protocols.  The concrete
bridges for the legacy controller and funnel live in :mod:`adapters` and are
resolved lazily for the historical imports that remain part of the supported
surface.  Keeping the bridge out of this module makes contract-only imports
safe for planners and import-boundary checks.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from polisyos.scientist.methods.search.adapters import (
        LegacySearchServiceAdapter,
        OrchestratorFunnelService,
    )
    from polisyos.scientist.methods.search.funnel.orchestrator import (
        FunnelOutcome,
        FunnelTicket,
    )


class CandidateProposal(BaseModel):
    """Carry one candidate proposal and metadata across service boundaries."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationBundle(BaseModel):
    """Capture evaluator feedback returned by Stage A/B and promotion scoring."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    objective_value: float
    is_promising: bool
    stage_a_passed: bool = True
    stage_b_result: dict[str, Any] | None = None
    duration_seconds: float = 0.0
    objective_details: list[Any] = Field(default_factory=list)
    policy_evaluation: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchServiceCheckpoint(BaseModel):
    """Immutable native-service replay envelope; readers accept this version only.

    The controller validates the decoded run ledger before admission. Arbitrary
    callbacks and external owner handles are supplied again by the caller.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["search-service.v2"] = "search-service.v2"
    configuration: dict[str, Any]
    run_state: dict[str, Any]
    generator_state: dict[str, Any] | None
    stopping_state: dict[str, Any]
    pending_candidates: dict[str, dict[str, Any]]
    pending_candidate_ids: list[str]
    initial_candidate_ids: list[str]
    completed_candidate_ids: list[str]
    ask_iteration: int = Field(ge=0)
    initial_candidate: dict[str, Any] | None
    started_at: str | None
    stopping_reason: str | None
    failure: str | None

    @model_validator(mode="after")
    def _validate_candidate_ownership(self) -> SearchServiceCheckpoint:
        ids = self.completed_candidate_ids
        if any(not value for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("invalid completed candidate ids")
        if any(not value for value in self.pending_candidates):
            raise ValueError("invalid pending candidate ids")
        if set(ids).intersection(self.pending_candidates):
            raise ValueError("candidate cannot be pending and completed")
        if len(set(self.pending_candidate_ids)) != len(self.pending_candidate_ids) or set(
            self.pending_candidate_ids
        ) != set(self.pending_candidates):
            raise ValueError("pending candidate order does not match its payloads")
        if len(set(self.initial_candidate_ids)) != len(self.initial_candidate_ids) or not set(
            self.initial_candidate_ids
        ).issubset(self.pending_candidates):
            raise ValueError("initial candidates must be pending")
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
    "EvaluationBundle",
    "FunnelService",
    "LegacySearchServiceAdapter",
    "OrchestratorFunnelService",
    "ParetoBasisScope",
    "ParetoViewAssessment",
    "ParetoViewProjection",
    "SearchService",
    "SearchServiceCheckpoint",
    "TellResult",
]
