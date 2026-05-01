"""Consolidation and revocation helpers for reflexive memory."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.memory.failure_lessons import (
    LessonApplicability,
    ReflexiveMemoryEvent,
    build_reflexive_memory_event,
)
from polisyos.scientist.search.lessons import LessonCard, LessonRegistry


class ConsolidatedLessonSet(BaseModel):
    """Deduped lesson set plus audit metadata."""

    model_config = ConfigDict(extra="forbid")

    lessons: list[LessonCard] = Field(default_factory=list)
    merged_lesson_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def consolidate_lessons(lessons: Iterable[LessonCard]) -> ConsolidatedLessonSet:
    """Merge duplicate lesson cards without deleting source lesson ids."""

    by_signature: dict[str, LessonCard] = {}
    merged: list[str] = []
    total = 0
    for lesson in lessons:
        total += 1
        signature = _lesson_signature(lesson)
        existing = by_signature.get(signature)
        if existing is None:
            by_signature[signature] = lesson
            continue
        merged.append(lesson.lesson_id)
        by_signature[signature] = existing.model_copy(
            update={
                "tags": sorted(set(existing.tags) | set(lesson.tags)),
                "anti_patterns": sorted(set(existing.anti_patterns) | set(lesson.anti_patterns)),
                "mutation_hints": sorted(set(existing.mutation_hints) | set(lesson.mutation_hints)),
                "trace_refs": sorted(set(existing.trace_refs) | set(lesson.trace_refs)),
                "metadata": {
                    **existing.metadata,
                    "consolidated_source_lesson_ids": sorted(
                        set(existing.metadata.get("consolidated_source_lesson_ids", []))
                        | {existing.lesson_id, lesson.lesson_id}
                    ),
                },
            }
        )
    return ConsolidatedLessonSet(
        lessons=list(by_signature.values()),
        merged_lesson_ids=merged,
        metadata={"input_count": total, "output_count": len(by_signature)},
    )


def revoke_lesson(
    registry: LessonRegistry,
    *,
    lesson_id: str,
    reason: str,
    run_id: str,
) -> ReflexiveMemoryEvent:
    """Invalidate a lesson in the registry while preserving a revocation event."""

    invalidated = registry.invalidate(lesson_id, reason)
    applicability = LessonApplicability(
        lesson_id=lesson_id,
        applies=False,
        reasons=["revoked", reason, "registry_invalidated" if invalidated else "lesson_not_found"],
        scope={},
    )
    return build_reflexive_memory_event(
        run_id=run_id,
        lesson_id=lesson_id,
        action="revoked",
        applicability=applicability,
        metadata={"reason": reason, "registry_invalidated": invalidated},
    )


def assert_lesson_can_influence(applicability: LessonApplicability) -> None:
    """Raise when a lesson is revoked/out-of-scope and therefore cannot influence a run."""

    if not applicability.applies or "revoked" in set(applicability.reasons):
        raise ValueError("lesson cannot influence run: " + ",".join(applicability.reasons))


def _lesson_signature(lesson: LessonCard) -> str:
    return "|".join(
        [
            str(lesson.kind.value),
            lesson.failure_type.strip().lower(),
            lesson.stage_name.strip().lower(),
            lesson.task_family.strip().lower(),
            lesson.domain.strip().lower(),
            " ".join(lesson.summary.split()).lower(),
        ]
    )


__all__ = [
    "ConsolidatedLessonSet",
    "assert_lesson_can_influence",
    "consolidate_lessons",
    "revoke_lesson",
]
