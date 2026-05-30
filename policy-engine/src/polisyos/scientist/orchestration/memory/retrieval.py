"""Deterministic reflexive-memory retrieval with contamination and scope checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.scientist.orchestration.memory.applicability import (
    MemoryApplicabilityContext,
    evaluate_lesson_applicability,
)
from polisyos.scientist.orchestration.memory.balanced import (
    BalancedMemoryApplicability,
    BalancedMemoryBiasPolicy,
    BalancedMemoryDecayPolicy,
    BalancedMemoryKind,
    BalancedMemoryRecord,
    MemoryInfluenceMode,
    assert_balanced_memory_can_influence,
    balanced_memory_from_lesson_card,
    calculate_conservative_bias_metrics,
    evaluate_balanced_memory_applicability,
)
from polisyos.scientist.orchestration.memory.consolidation import assert_lesson_can_influence
from polisyos.scientist.orchestration.memory.contamination import (
    MemoryContaminationPolicy,
    detect_memory_contamination,
    lesson_payload_for_contamination,
)
from polisyos.scientist.orchestration.memory.contracts import (
    LessonApplicability,
    ReflexiveMemoryEvent,
    build_reflexive_memory_event,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from polisyos.scientist.methods.search.lessons import LessonCard, LessonQuery, LessonRegistry


class MemoryRetrievedLesson(BaseModel):
    """Warning-only lesson surfaced to a future run."""

    model_config = ConfigDict(extra="forbid")

    lesson_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    anti_patterns: list[str] = Field(default_factory=list)
    remediation_hint: str | None = None
    applicability: LessonApplicability
    influence_mode: Literal["warning_anti_pattern"] = "warning_anti_pattern"
    source_run_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_warning_only(self) -> MemoryRetrievedLesson:
        if not self.applicability.applies:
            raise ValueError("retrieved lessons must be applicable")
        if not self.applicability.reasons:
            raise ValueError("retrieved lessons must include applicability reasons")
        return self


class MemoryRetrievalResult(BaseModel):
    """Complete result of a governed memory lookup."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    retrieved_lessons: list[MemoryRetrievedLesson] = Field(default_factory=list)
    rejected_lessons: list[LessonApplicability] = Field(default_factory=list)
    events: list[ReflexiveMemoryEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_event_coverage(self) -> MemoryRetrievalResult:
        retrieved_ids = {lesson.lesson_id for lesson in self.retrieved_lessons}
        event_ids = {
            event.lesson_id for event in self.events if event.action in {"retrieved", "applied"}
        }
        if not retrieved_ids.issubset(event_ids):
            raise ValueError("retrieved lessons must have memory events")
        return self


class BalancedMemoryRetrievedRecord(BaseModel):
    """Future-only balanced memory surfaced to search, review, or acquisition."""

    model_config = ConfigDict(extra="forbid")

    memory: BalancedMemoryRecord
    applicability: BalancedMemoryApplicability
    influence_modes: tuple[MemoryInfluenceMode, ...] = Field(default=())
    source_run_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_future_influence_only(self) -> BalancedMemoryRetrievedRecord:
        if not self.applicability.applies:
            raise ValueError("retrieved balanced memory must be applicable")
        if not self.applicability.reasons:
            raise ValueError("retrieved balanced memory must include applicability reasons")
        if tuple(self.influence_modes) != tuple(self.applicability.influence_modes):
            raise ValueError("retrieved balanced memory influence modes must match applicability")
        return self


class BalancedMemoryRetrievalResult(BaseModel):
    """Complete result of W5.D balanced-memory retrieval."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    retrieved_memories: list[BalancedMemoryRetrievedRecord] = Field(default_factory=list)
    rejected_memories: list[BalancedMemoryApplicability] = Field(default_factory=list)
    events: list[ReflexiveMemoryEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_event_coverage(self) -> BalancedMemoryRetrievalResult:
        retrieved_ids = {item.memory.memory_id for item in self.retrieved_memories}
        event_ids = {
            event.lesson_id for event in self.events if event.action in {"retrieved", "applied"}
        }
        if not retrieved_ids.issubset(event_ids):
            raise ValueError("retrieved balanced memories must have memory events")
        return self


def retrieve_reflexive_lessons_from_registry(
    registry: LessonRegistry,
    query: LessonQuery,
    *,
    context: MemoryApplicabilityContext,
    contamination_policy: MemoryContaminationPolicy | None = None,
    decay_policy: BalancedMemoryDecayPolicy | dict[str, Any] | None = None,
    revoked_lesson_ids: Iterable[str] = (),
    limit: int = 10,
) -> MemoryRetrievalResult:
    """Query the existing lesson registry and apply Phase 2.4 memory controls."""

    active_query = query.model_copy(update={"limit": min(max(1, limit), query.limit)})
    return retrieve_reflexive_lessons(
        registry.query(active_query),
        context=context,
        contamination_policy=contamination_policy,
        decay_policy=decay_policy,
        revoked_lesson_ids=revoked_lesson_ids,
        limit=limit,
    )


def retrieve_balanced_memories_from_registry(
    registry: LessonRegistry,
    query: LessonQuery,
    *,
    context: MemoryApplicabilityContext,
    contamination_policy: MemoryContaminationPolicy | None = None,
    decay_policy: BalancedMemoryDecayPolicy | dict[str, Any] | None = None,
    bias_policy: BalancedMemoryBiasPolicy | dict[str, Any] | None = None,
    revoked_memory_ids: Iterable[str] = (),
    limit: int = 10,
) -> BalancedMemoryRetrievalResult:
    """Query the lesson registry for balanced success/failure/opportunity memory."""

    active_limit = max(1, limit)
    candidate_limit = min(100, max(query.limit, active_limit * len(BalancedMemoryKind)))
    active_query = query.model_copy(update={"limit": candidate_limit})
    return retrieve_balanced_memories(
        registry.query(active_query),
        context=context,
        contamination_policy=contamination_policy,
        decay_policy=decay_policy,
        bias_policy=bias_policy,
        revoked_memory_ids=revoked_memory_ids,
        limit=active_limit,
    )


def retrieve_balanced_memories(
    lessons: Sequence[LessonCard],
    *,
    context: MemoryApplicabilityContext,
    contamination_policy: MemoryContaminationPolicy | None = None,
    decay_policy: BalancedMemoryDecayPolicy | dict[str, Any] | None = None,
    bias_policy: BalancedMemoryBiasPolicy | dict[str, Any] | None = None,
    revoked_memory_ids: Iterable[str] = (),
    limit: int = 10,
) -> BalancedMemoryRetrievalResult:
    """Return balanced memory as future influence while preserving rejection reasons."""

    active_decay_policy = _coerce_decay_policy(decay_policy)
    active_bias_policy = _coerce_bias_policy(bias_policy)
    candidates: list[BalancedMemoryRetrievedRecord] = []
    rejected: list[BalancedMemoryApplicability] = []
    rejected_events: list[ReflexiveMemoryEvent] = []
    active_revoked = set(revoked_memory_ids)

    for lesson in lessons:
        try:
            memory_kind = BalancedMemoryKind(lesson.kind.value)
        except ValueError:
            continue
        contamination = detect_memory_contamination(
            lesson_payload_for_contamination(lesson),
            policy=contamination_policy,
        )
        if contamination:
            applicability = BalancedMemoryApplicability(
                memory_id=lesson.lesson_id,
                memory_kind=memory_kind,
                applies=False,
                reasons=(
                    "contaminated_hidden_eval",
                    *(f"{finding.token_kind}:{finding.token}" for finding in contamination),
                ),
                scope={},
                influence_weight=0.0,
                decay_status="blocked",
            )
            rejected.append(applicability)
            rejected_events.append(
                _balanced_memory_event(
                    run_id=context.run_id,
                    memory=None,
                    applicability=applicability,
                    action="rejected",
                    metadata={
                        "contamination_findings": [
                            finding.model_dump(mode="json") for finding in contamination
                        ]
                    },
                )
            )
            continue

        memory = balanced_memory_from_lesson_card(lesson)
        applicability = evaluate_balanced_memory_applicability(
            memory,
            context,
            revoked_memory_ids=active_revoked,
            decay_policy=active_decay_policy,
        )
        if not applicability.applies:
            rejected.append(applicability)
            rejected_events.append(
                _balanced_memory_event(
                    run_id=context.run_id,
                    memory=memory,
                    applicability=applicability,
                    action="rejected",
                )
            )
            continue
        candidates.append(
            BalancedMemoryRetrievedRecord(
                memory=memory,
                applicability=applicability,
                influence_modes=applicability.influence_modes,
                source_run_id=memory.source_run_id,
            )
        )

    retrieved = _select_balanced_memory_records(candidates, limit=max(1, limit))
    bias_metrics = calculate_conservative_bias_metrics(
        retrieved_memories=[item.memory for item in retrieved],
        rejected_memories=rejected,
        bias_policy=active_bias_policy,
    )
    retrieved_events = [
        _balanced_memory_event(
            run_id=context.run_id,
            memory=item.memory,
            applicability=item.applicability,
            action="retrieved",
        )
        for item in retrieved
    ]
    return BalancedMemoryRetrievalResult(
        run_id=context.run_id,
        retrieved_memories=retrieved,
        rejected_memories=rejected,
        events=[*retrieved_events, *rejected_events],
        metadata={
            "candidate_count": len(lessons),
            "applicable_count": len(candidates),
            "retrieved_count": len(retrieved),
            "rejected_count": len(rejected),
            "candidate_kind_counts": _balanced_kind_counts(
                [candidate.memory.kind for candidate in candidates]
            ),
            "retrieved_kind_counts": _balanced_kind_counts(
                [item.memory.kind for item in retrieved]
            ),
            "rejected_kind_counts": _balanced_kind_counts(
                [item.memory_kind for item in rejected]
            ),
            "balance_status": _balance_status(retrieved),
            "authority_boundary": "future_influence_only_not_claim_evidence",
            "decay_summary": _decay_summary(retrieved, rejected),
            "decay_policy": active_decay_policy.model_dump(mode="json"),
            "conservative_bias_metrics": bias_metrics.model_dump(mode="json"),
            "bias_policy": active_bias_policy.model_dump(mode="json"),
        },
    )


def retrieve_reflexive_lessons(
    lessons: Sequence[LessonCard],
    *,
    context: MemoryApplicabilityContext,
    contamination_policy: MemoryContaminationPolicy | None = None,
    decay_policy: BalancedMemoryDecayPolicy | dict[str, Any] | None = None,
    revoked_lesson_ids: Iterable[str] = (),
    limit: int = 10,
) -> MemoryRetrievalResult:
    """Return applicable failure lessons as warnings and rejected lessons with reasons."""

    active_decay_policy = _coerce_decay_policy(decay_policy)
    retrieved: list[MemoryRetrievedLesson] = []
    rejected: list[LessonApplicability] = []
    events: list[ReflexiveMemoryEvent] = []
    active_revoked = set(revoked_lesson_ids)

    for lesson in lessons:
        contamination = detect_memory_contamination(
            lesson_payload_for_contamination(lesson),
            policy=contamination_policy,
        )
        if contamination:
            applicability = LessonApplicability(
                lesson_id=lesson.lesson_id,
                applies=False,
                reasons=[
                    "contaminated_hidden_eval",
                    *[f"{finding.token_kind}:{finding.token}" for finding in contamination],
                ],
                scope={},
                influence_weight=0.0,
                decay_status="blocked",
            )
            rejected.append(applicability)
            events.append(
                build_reflexive_memory_event(
                    run_id=context.run_id,
                    lesson_id=lesson.lesson_id,
                    action="rejected",
                    applicability=applicability,
                    metadata={
                        "contamination_findings": [f.model_dump(mode="json") for f in contamination]
                    },
                )
            )
            continue

        applicability = evaluate_lesson_applicability(
            lesson,
            context,
            revoked_lesson_ids=active_revoked,
        )
        applicability = _apply_lesson_decay(
            lesson,
            applicability,
            context=context,
            decay_policy=active_decay_policy,
        )
        if not applicability.applies:
            rejected.append(applicability)
            events.append(
                build_reflexive_memory_event(
                    run_id=context.run_id,
                    lesson_id=lesson.lesson_id,
                    action="rejected",
                    applicability=applicability,
                    metadata={
                        "influence_weight": applicability.influence_weight,
                        "decay_status": applicability.decay_status,
                    },
                )
            )
            continue

        retrieved_lesson = MemoryRetrievedLesson(
            lesson_id=lesson.lesson_id,
            summary=lesson.summary,
            anti_patterns=list(lesson.anti_patterns),
            remediation_hint=lesson.remediation_hint,
            applicability=applicability,
            source_run_id=lesson.source_run_id,
        )
        retrieved.append(retrieved_lesson)
        events.append(
            build_reflexive_memory_event(
                run_id=context.run_id,
                lesson_id=lesson.lesson_id,
                action="retrieved",
                applicability=applicability,
                metadata={
                    "influence_mode": "warning_anti_pattern",
                    "influence_weight": applicability.influence_weight,
                    "decay_status": applicability.decay_status,
                },
            )
        )
        if len(retrieved) >= limit:
            break

    return MemoryRetrievalResult(
        run_id=context.run_id,
        retrieved_lessons=retrieved,
        rejected_lessons=rejected,
        events=events,
        metadata={
            "candidate_count": len(lessons),
            "retrieved_count": len(retrieved),
            "rejected_count": len(rejected),
            "influence_mode": "warning_anti_pattern",
            "decay_summary": _lesson_decay_summary(retrieved, rejected),
            "decay_policy": active_decay_policy.model_dump(mode="json"),
        },
    )


def format_balanced_memory_context(
    result: BalancedMemoryRetrievalResult,
    *,
    max_memories: int = 10,
) -> str:
    """Render W5.D balanced memory for prompts as future influence, never evidence."""

    lines = ["[Balanced memory influence - not claim evidence]"]
    for item in result.retrieved_memories[:max_memories]:
        assert_balanced_memory_can_influence(item.applicability)
        reasons = ", ".join(item.applicability.reasons)
        modes = ", ".join(f"mode={mode.value}" for mode in item.influence_modes)
        guidance = item.memory.guidance or item.memory.summary
        lines.append(
            f"- memory_id={item.memory.memory_id}; kind={item.memory.kind.value}; "
            f"{modes}; weight={item.applicability.influence_weight:.3f}; "
            f"reasons={reasons}; guidance={guidance}"
        )
    return "\n".join(lines)


def format_warning_only_memory_context(
    result: MemoryRetrievalResult,
    *,
    max_lessons: int = 10,
) -> str:
    """Render applicable memory as warning-only prompt/context text."""

    lines = ["[Reflexive memory warnings - not claim evidence]"]
    for lesson in result.retrieved_lessons[:max_lessons]:
        assert_lesson_can_influence(lesson.applicability)
        reasons = ", ".join(lesson.applicability.reasons)
        anti_patterns = ", ".join(lesson.anti_patterns) or "unspecified"
        remediation = lesson.remediation_hint or "Review the prior failure mode before proceeding."
        lines.append(
            f"- lesson_id={lesson.lesson_id}; mode=warning_anti_pattern; "
            f"weight={lesson.applicability.influence_weight:.3f}; "
            f"reasons={reasons}; anti_patterns={anti_patterns}; remediation={remediation}"
        )
    return "\n".join(lines)


def _select_balanced_memory_records(
    candidates: list[BalancedMemoryRetrievedRecord],
    *,
    limit: int,
) -> list[BalancedMemoryRetrievedRecord]:
    selected: list[BalancedMemoryRetrievedRecord] = []
    selected_ids: set[str] = set()
    for kind in BalancedMemoryKind:
        match = next(
            (candidate for candidate in candidates if candidate.memory.kind is kind),
            None,
        )
        if match is None:
            continue
        selected.append(match)
        selected_ids.add(match.memory.memory_id)
        if len(selected) >= limit:
            return selected
    for candidate in candidates:
        if candidate.memory.memory_id in selected_ids:
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def _balanced_memory_event(
    *,
    run_id: str,
    memory: BalancedMemoryRecord | None,
    applicability: BalancedMemoryApplicability,
    action: Literal["retrieved", "applied", "rejected", "revoked"],
    metadata: dict[str, Any] | None = None,
) -> ReflexiveMemoryEvent:
    event_metadata = {
        "balanced_memory": True,
        "memory_kind": applicability.memory_kind.value,
        "influence_modes": [mode.value for mode in applicability.influence_modes],
        "influence_mode": "balanced_future_influence",
        "influence_weight": applicability.influence_weight,
        "decay_status": applicability.decay_status,
        "evidence_slot_admission": "forbidden",
    }
    if memory is not None:
        event_metadata.update(
            {
                "source_run_id": memory.source_run_id,
                "authority_boundary": memory.authority_boundary.model_dump(mode="json"),
            }
        )
    event_metadata.update(metadata or {})
    return build_reflexive_memory_event(
        run_id=run_id,
        lesson_id=applicability.memory_id,
        action=action,
        applicability=LessonApplicability(
            lesson_id=applicability.memory_id,
            applies=applicability.applies,
            reasons=list(applicability.reasons),
            scope=dict(applicability.scope),
            expires_at=applicability.expires_at,
        ),
        metadata=event_metadata,
    )


def _balanced_kind_counts(kinds: Iterable[BalancedMemoryKind]) -> dict[str, int]:
    counts = {kind.value: 0 for kind in BalancedMemoryKind}
    for kind in kinds:
        counts[kind.value] += 1
    return {kind: count for kind, count in counts.items() if count}


def _apply_lesson_decay(
    lesson: LessonCard,
    applicability: LessonApplicability,
    *,
    context: MemoryApplicabilityContext,
    decay_policy: BalancedMemoryDecayPolicy,
) -> LessonApplicability:
    now = context.now.astimezone(UTC)
    explicit_expiry = applicability.expires_at
    ttl_expiry = lesson.created_at + timedelta(days=decay_policy.default_ttl_days)
    effective_expiry = _earliest_datetime(explicit_expiry, ttl_expiry)
    influence_weight = _lesson_influence_weight(lesson, now=now, decay_policy=decay_policy)
    reasons = list(applicability.reasons)
    applies = applicability.applies
    decay_status = applicability.decay_status

    if "revoked" in reasons:
        decay_status = "revoked"
    if explicit_expiry is not None and now > explicit_expiry:
        decay_status = "expired_scope"
    elif now > ttl_expiry:
        applies = False
        decay_status = "expired_ttl"
        if "expired_ttl" not in reasons:
            reasons.append("expired_ttl")
    elif influence_weight < decay_policy.minimum_influence_weight:
        applies = False
        decay_status = "decayed"
        if "decayed_below_threshold" not in reasons:
            reasons.append("decayed_below_threshold")

    return applicability.model_copy(
        update={
            "applies": applies,
            "reasons": reasons,
            "expires_at": effective_expiry,
            "influence_weight": influence_weight,
            "decay_status": decay_status,
        }
    )


def _lesson_influence_weight(
    lesson: LessonCard,
    *,
    now: datetime,
    decay_policy: BalancedMemoryDecayPolicy,
) -> float:
    age = max(timedelta(), now.astimezone(UTC) - lesson.created_at)
    age_days = age.total_seconds() / 86_400
    half_life_factor = 0.5 ** (age_days / decay_policy.half_life_days)
    return round(max(0.0, min(1.0, float(lesson.confidence) * half_life_factor)), 12)


def _earliest_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _lesson_decay_summary(
    retrieved: Iterable[MemoryRetrievedLesson],
    rejected: Iterable[LessonApplicability],
) -> dict[str, Any]:
    retrieved_weights = [item.applicability.influence_weight for item in retrieved]
    rejected_list = list(rejected)
    return {
        "expired_count": sum(
            1
            for item in rejected_list
            if item.decay_status in {"expired_scope", "expired_ttl"}
            or "expired" in item.reasons
            or "expired_ttl" in item.reasons
        ),
        "decayed_count": sum(
            1
            for item in rejected_list
            if item.decay_status == "decayed" or "decayed_below_threshold" in item.reasons
        ),
        "retrieved_min_influence_weight": min(retrieved_weights) if retrieved_weights else None,
        "retrieved_max_influence_weight": max(retrieved_weights) if retrieved_weights else None,
    }


def _decay_summary(
    candidates: Iterable[BalancedMemoryRetrievedRecord],
    rejected: Iterable[BalancedMemoryApplicability],
) -> dict[str, Any]:
    retrieved_weights = [item.applicability.influence_weight for item in candidates]
    rejected_list = list(rejected)
    return {
        "expired_count": sum(
            1
            for item in rejected_list
            if item.decay_status in {"expired_scope", "expired_ttl"}
            or "expired" in item.reasons
            or "expired_ttl" in item.reasons
        ),
        "decayed_count": sum(
            1
            for item in rejected_list
            if item.decay_status == "decayed" or "decayed_below_threshold" in item.reasons
        ),
        "retrieved_min_influence_weight": min(retrieved_weights) if retrieved_weights else None,
        "retrieved_max_influence_weight": max(retrieved_weights) if retrieved_weights else None,
    }


def _coerce_decay_policy(
    policy: BalancedMemoryDecayPolicy | dict[str, Any] | None,
) -> BalancedMemoryDecayPolicy:
    if policy is None:
        return BalancedMemoryDecayPolicy()
    if isinstance(policy, BalancedMemoryDecayPolicy):
        return policy
    return BalancedMemoryDecayPolicy.model_validate(policy)


def _coerce_bias_policy(
    policy: BalancedMemoryBiasPolicy | dict[str, Any] | None,
) -> BalancedMemoryBiasPolicy:
    if policy is None:
        return BalancedMemoryBiasPolicy()
    if isinstance(policy, BalancedMemoryBiasPolicy):
        return policy
    return BalancedMemoryBiasPolicy.model_validate(policy)


def _balance_status(retrieved: list[BalancedMemoryRetrievedRecord]) -> str:
    kinds = {item.memory.kind for item in retrieved}
    if not kinds:
        return "empty"
    if kinds == set(BalancedMemoryKind):
        return "balanced"
    if kinds == {BalancedMemoryKind.FAILURE}:
        return "failure_only"
    return "partial"


__all__ = [
    "BalancedMemoryRetrievalResult",
    "BalancedMemoryRetrievedRecord",
    "MemoryRetrievalResult",
    "MemoryRetrievedLesson",
    "format_balanced_memory_context",
    "format_warning_only_memory_context",
    "retrieve_balanced_memories",
    "retrieve_balanced_memories_from_registry",
    "retrieve_reflexive_lessons",
    "retrieve_reflexive_lessons_from_registry",
]
