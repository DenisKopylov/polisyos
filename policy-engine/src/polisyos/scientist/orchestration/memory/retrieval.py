"""Deterministic reflexive-memory retrieval with contamination and scope checks."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.scientist.orchestration.memory.applicability import (
    MemoryApplicabilityContext,
    evaluate_lesson_applicability,
)
from polisyos.scientist.orchestration.memory.consolidation import assert_lesson_can_influence
from polisyos.scientist.orchestration.memory.contamination import (
    MemoryContaminationPolicy,
    detect_memory_contamination,
    lesson_payload_for_contamination,
)
from polisyos.scientist.orchestration.memory.failure_lessons import (
    LessonApplicability,
    ReflexiveMemoryEvent,
    build_reflexive_memory_event,
)
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
            event.lesson_id
            for event in self.events
            if event.action in {"retrieved", "applied"}
        }
        if not retrieved_ids.issubset(event_ids):
            raise ValueError("retrieved lessons must have memory events")
        return self


def retrieve_reflexive_lessons_from_registry(
    registry: LessonRegistry,
    query: LessonQuery,
    *,
    context: MemoryApplicabilityContext,
    contamination_policy: MemoryContaminationPolicy | None = None,
    revoked_lesson_ids: Iterable[str] = (),
    limit: int = 10,
) -> MemoryRetrievalResult:
    """Query the existing lesson registry and apply Phase 2.4 memory controls."""

    active_query = query.model_copy(update={"limit": min(max(1, limit), query.limit)})
    return retrieve_reflexive_lessons(
        registry.query(active_query),
        context=context,
        contamination_policy=contamination_policy,
        revoked_lesson_ids=revoked_lesson_ids,
        limit=limit,
    )


def retrieve_reflexive_lessons(
    lessons: Sequence[LessonCard],
    *,
    context: MemoryApplicabilityContext,
    contamination_policy: MemoryContaminationPolicy | None = None,
    revoked_lesson_ids: Iterable[str] = (),
    limit: int = 10,
) -> MemoryRetrievalResult:
    """Return applicable failure lessons as warnings and rejected lessons with reasons."""

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
                    *[
                        f"{finding.token_kind}:{finding.token}"
                        for finding in contamination
                    ],
                ],
                scope={},
            )
            rejected.append(applicability)
            events.append(
                build_reflexive_memory_event(
                    run_id=context.run_id,
                    lesson_id=lesson.lesson_id,
                    action="rejected",
                    applicability=applicability,
                    metadata={"contamination_findings": [f.model_dump(mode="json") for f in contamination]},
                )
            )
            continue

        applicability = evaluate_lesson_applicability(
            lesson,
            context,
            revoked_lesson_ids=active_revoked,
        )
        if not applicability.applies:
            rejected.append(applicability)
            events.append(
                build_reflexive_memory_event(
                    run_id=context.run_id,
                    lesson_id=lesson.lesson_id,
                    action="rejected",
                    applicability=applicability,
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
                metadata={"influence_mode": "warning_anti_pattern"},
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
        },
    )


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
            f"reasons={reasons}; anti_patterns={anti_patterns}; remediation={remediation}"
        )
    return "\n".join(lines)


__all__ = [
    "format_warning_only_memory_context",
    "MemoryRetrievalResult",
    "MemoryRetrievedLesson",
    "retrieve_reflexive_lessons",
    "retrieve_reflexive_lessons_from_registry",
]
