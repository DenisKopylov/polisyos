"""Deterministic frontier helpers for legacy search controller flows."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Any

from polisyos.common.serialization import stable_json_dumps
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    CandidateStrategyContext,
    EvaluationBundle,
)
from polisyos.scientist.methods.search.objective import ObjectiveValue


@dataclass(frozen=True)
class FrontierPoint:
    """Internal representation of one Pareto-frontier candidate."""

    candidate: dict[str, Any]
    objectives: list[dict[str, Any]]
    normalized_values: tuple[float, ...]
    candidate_hash: str
    proposal: CandidateProposal | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "candidate": dict(self.candidate),
            "candidate_hash": self.candidate_hash,
            "objectives": [dict(item) for item in self.objectives],
        }


def _validate_json_subject(value: Any, *, _seen: set[int] | None = None, _depth: int = 0) -> None:
    """Admit only values that the evaluator and persisted JSON both represent identically."""
    if _depth > 128:
        raise ValueError("candidate_subject_depth_exceeded")
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int:
        if abs(value) > 9_007_199_254_740_991:
            raise ValueError("candidate_subject_integer_outside_safe_json_range")
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("candidate_subject_non_finite")
        return
    if type(value) not in (dict, list):
        raise TypeError("candidate_subject_not_json_native")
    seen = set() if _seen is None else _seen
    if id(value) in seen:
        raise ValueError("candidate_subject_cycle")
    seen.add(id(value))
    try:
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                raise TypeError("candidate_subject_non_string_key")
            values = value.values()
        else:
            values = value
        for item in values:
            _validate_json_subject(item, _seen=seen, _depth=_depth + 1)
    finally:
        seen.remove(id(value))


def candidate_payloads_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Compare the exact JSON-native payloads submitted and persisted."""
    _validate_json_subject(left)
    _validate_json_subject(right)
    return stable_json_dumps(left) == stable_json_dumps(right)


def _strategy_subject_hash(context: CandidateStrategyContext) -> str:
    subject = context.subject
    _validate_json_subject(subject)
    if context.policy_schema:
        from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

        typed = PolicyCandidateSchema.model_validate(subject)
        if not candidate_payloads_equal(subject, typed.model_dump(mode="json", exclude_none=True)):
            raise ValueError("candidate_policy_subject_not_canonical")
        return typed.candidate_hash()
    return "sha256:" + hashlib.sha256(stable_json_dumps(subject).encode("utf-8")).hexdigest()


def strategy_candidate_payload(context: CandidateStrategyContext) -> dict[str, Any]:
    """Build the one evaluator payload from the explicit producer context."""
    from copy import deepcopy

    subject = deepcopy(context.subject)
    _validate_json_subject(subject)
    fields = deepcopy(context.strategy_fields)
    _validate_json_subject(fields)
    if context.producer == "policy_design" and (
        fields or not context.policy_schema or not context.policy_transport
    ):
        raise ValueError("candidate_policy_context_invalid")
    # Producer-only strategy fields never enter the evaluator payload. Any
    # caller semantic field, including _strategy_metadata, stays in subject.
    if context.policy_schema and not context.policy_transport:
        raise ValueError("candidate_policy_context_invalid")
    if context.policy_transport:
        if "candidate_hash" in subject:
            raise ValueError("candidate_policy_subject_conflict")
        subject["candidate_hash"] = _strategy_subject_hash(context)
    _validate_json_subject(subject)
    return subject


def materialize_candidate_proposal(proposal: CandidateProposal) -> dict[str, Any]:
    """Validate and return the same payload that ask, tell and evaluators see."""
    from copy import deepcopy

    _validate_json_subject(proposal.payload)
    if proposal.metadata:
        if proposal.service_iteration is None or proposal.metadata != {
            "iteration": proposal.service_iteration
        }:
            raise ValueError("candidate_proposal_metadata_not_evaluated")
    elif proposal.service_iteration is not None:
        raise ValueError("candidate_service_context_mismatch")
    if proposal.strategy_context is not None:
        reconstructed = strategy_candidate_payload(proposal.strategy_context)
        if not candidate_payloads_equal(reconstructed, proposal.payload):
            raise ValueError("candidate_proposal_payload_mismatch")
    return deepcopy(proposal.payload)


def invoke_candidate_evaluator(
    evaluator: Callable[..., Any],
    candidate: dict[str, Any],
    context: dict[str, Any],
    proposal: CandidateProposal | None,
    *,
    prior_ticket_id: str | None = None,
) -> Any:
    """Deliver producer context only to the concrete funnel owner, never a stage."""
    from polisyos.scientist.methods.search.funnel.orchestrator import _BoundFunnelStageCallable

    if proposal is not None and not candidate_payloads_equal(
        materialize_candidate_proposal(proposal), candidate
    ):
        raise ValueError("candidate_evaluation_payload_mismatch")
    if type(evaluator) is _BoundFunnelStageCallable:
        return evaluator.with_proposal(candidate, context, proposal, prior_ticket_id)
    return evaluator(candidate, context)


def funnel_prior_ticket_id(
    stage_a: Callable[..., Any], stage_b: Callable[..., Any], result: Any
) -> str | None:
    """Retain prior work only from the same concrete owner that performed Stage A."""
    from polisyos.scientist.methods.search.funnel.orchestrator import _BoundFunnelStageCallable

    if not (
        type(stage_a) is _BoundFunnelStageCallable
        and type(stage_b) is _BoundFunnelStageCallable
        and stage_a._owner is stage_b._owner
        and stage_a._stage == "stage_a"
        and stage_b._stage == "stage_b"
        and isinstance(result, EvaluationBundle)
    ):
        return None
    ticket_id = result.metadata.get("funnel_ticket_id")
    if ticket_id is not None and (not isinstance(ticket_id, str) or not ticket_id):
        raise ValueError("funnel_stage_a_ticket_invalid")
    return ticket_id


def policy_candidate_hash(
    candidate: dict[str, Any] | CandidateProposal,
    *,
    metadata_hash: str | None = None,
    explicit_hash: str | None = None,
) -> str:
    """Recompute candidate identity from the validated executed subject."""
    if isinstance(candidate, CandidateProposal):
        materialize_candidate_proposal(candidate)
        if candidate.strategy_context is not None:
            actual = _strategy_subject_hash(candidate.strategy_context)
        else:
            actual = policy_candidate_hash(candidate.payload)
    else:
        _validate_json_subject(candidate)
        actual = (
            "sha256:" + hashlib.sha256(stable_json_dumps(candidate).encode("utf-8")).hexdigest()
        )
    for supplied in (metadata_hash, explicit_hash):
        if supplied not in (None, "") and (
            not isinstance(supplied, str) or supplied.strip() != actual
        ):
            raise ValueError("candidate_identity_supplied_hash_mismatch")
    return actual


def update_legacy_pareto_front(
    frontier: Iterable[FrontierPoint],
    *,
    candidate: dict[str, Any],
    objectives: list[ObjectiveValue],
    cap: int = 100,
    proposal: CandidateProposal | None = None,
) -> list[FrontierPoint]:
    """Insert one candidate into the legacy Pareto frontier payload."""

    if proposal is not None and not candidate_payloads_equal(
        materialize_candidate_proposal(proposal), candidate
    ):
        raise ValueError("candidate_proposal_payload_mismatch")
    new_point = FrontierPoint(
        candidate=dict(candidate),
        objectives=[
            {
                "name": item.name,
                "raw_value": item.raw_value,
                "direction": item.direction.value,
            }
            for item in objectives
        ],
        normalized_values=tuple(item.normalized_value for item in objectives),
        candidate_hash=policy_candidate_hash(proposal or candidate),
        proposal=proposal,
    )

    existing_points: list[FrontierPoint] = []
    for existing in frontier:
        if existing.proposal is not None and not candidate_payloads_equal(
            materialize_candidate_proposal(existing.proposal), existing.candidate
        ):
            raise ValueError("candidate_proposal_payload_mismatch")
        existing_points.append(
            replace(
                existing,
                candidate_hash=policy_candidate_hash(existing.proposal or existing.candidate),
            )
        )
    if proposal is not None and proposal.strategy_context is not None:
        if any(
            point.proposal is None and "_strategy_metadata" in point.candidate
            for point in existing_points
        ):
            raise ValueError("legacy_frontier_producer_envelope_unestablished")
    surviving: list[FrontierPoint] = []
    for existing in existing_points:
        if existing.candidate_hash == new_point.candidate_hash:
            if dominates(existing.normalized_values, new_point.normalized_values):
                return existing_points
            continue
        if not dominates(new_point.normalized_values, existing.normalized_values):
            surviving.append(existing)

    is_dominated = any(
        dominates(existing.normalized_values, new_point.normalized_values) for existing in surviving
    )
    if is_dominated:
        return surviving[:cap]

    surviving.append(new_point)
    surviving.sort(
        key=lambda item: (
            tuple(-value for value in item.normalized_values),
            item.candidate_hash,
        )
    )
    return surviving[:cap]


def dominates(a: Iterable[float], b: Iterable[float]) -> bool:
    """Return True if *a* dominates *b* (all <= and at least one <)."""

    left = tuple(a)
    right = tuple(b)
    if len(left) != len(right):
        return False
    at_least_one_better = False
    for left_value, right_value in zip(left, right, strict=False):
        if left_value > right_value:
            return False
        if left_value < right_value:
            at_least_one_better = True
    return at_least_one_better


__all__ = [
    "FrontierPoint",
    "funnel_prior_ticket_id",
    "invoke_candidate_evaluator",
    "candidate_payloads_equal",
    "dominates",
    "materialize_candidate_proposal",
    "policy_candidate_hash",
    "strategy_candidate_payload",
    "update_legacy_pareto_front",
]
