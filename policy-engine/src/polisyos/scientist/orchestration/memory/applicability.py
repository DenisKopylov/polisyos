"""Applicability checks for reflexive lesson reuse."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.orchestration.memory.contracts import (
    LessonApplicability,
    MemoryVisibility,
)
from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind


class MemoryApplicabilityContext(BaseModel):
    """Target-run context used to decide whether a lesson may influence a run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    tenant_hash: str | None = None
    domain: str = Field(default="general", min_length=1)
    workflow_id: str | None = None
    method_family: str | None = None
    task_family: str = Field(default="policy", min_length=1)
    now: datetime = Field(default_factory=lambda: datetime.now(UTC))


def lesson_scope_from_card(lesson: LessonCard) -> dict[str, str]:
    """Return the reflexive-memory scope stored on a lesson card."""

    raw_scope = lesson.metadata.get("memory_scope")
    if isinstance(raw_scope, dict):
        return {str(key): str(value) for key, value in raw_scope.items() if value is not None}
    return {
        "visibility": str(lesson.metadata.get("memory_visibility", MemoryVisibility.DOMAIN.value)),
        "domain": lesson.domain,
        **({"tenant_hash": lesson.origin_tenant_hash} if lesson.origin_tenant_hash else {}),
    }


def evaluate_lesson_applicability(
    lesson: LessonCard,
    context: MemoryApplicabilityContext,
    *,
    revoked_lesson_ids: Iterable[str] = (),
) -> LessonApplicability:
    """Evaluate scope, expiry and lesson kind before a lesson can be reused."""

    scope = lesson_scope_from_card(lesson)
    reasons: list[str] = []
    blocked: list[str] = []
    revoked = set(revoked_lesson_ids)
    visibility = _visibility(scope.get("visibility"))
    expires_at = _parse_expiry(scope.get("expires_at"))

    if lesson.lesson_id in revoked:
        blocked.append("revoked")
    if lesson.kind is not LessonKind.FAILURE:
        blocked.append("not_failure_lesson")
    else:
        reasons.append("failure_lesson")
    if expires_at is not None and context.now.astimezone(UTC) > expires_at:
        blocked.append("expired")
    else:
        reasons.append("not_expired")
    if lesson.task_family and lesson.task_family != context.task_family:
        blocked.append("task_family_mismatch")
    else:
        reasons.append("task_family_match")

    _check_visibility(
        visibility=visibility,
        scope=scope,
        lesson=lesson,
        context=context,
        reasons=reasons,
        blocked=blocked,
    )
    _check_optional_scope(
        scope=scope,
        key="workflow_id",
        context_value=context.workflow_id,
        reasons=reasons,
        blocked=blocked,
    )
    _check_optional_scope(
        scope=scope,
        key="method_family",
        context_value=context.method_family,
        reasons=reasons,
        blocked=blocked,
    )
    if lesson.metadata.get("reusable_memory") is not True:
        reasons.append("legacy_lesson_warning_only")
    else:
        reasons.append("reusable_memory")

    applies = not blocked
    return LessonApplicability(
        lesson_id=lesson.lesson_id,
        applies=applies,
        reasons=_dedupe([*reasons, *blocked]),
        scope=scope,
        expires_at=expires_at,
    )


def _visibility(value: str | None) -> MemoryVisibility:
    try:
        return MemoryVisibility(value or MemoryVisibility.DOMAIN.value)
    except ValueError:
        return MemoryVisibility.DOMAIN


def _parse_expiry(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _check_visibility(
    *,
    visibility: MemoryVisibility,
    scope: dict[str, str],
    lesson: LessonCard,
    context: MemoryApplicabilityContext,
    reasons: list[str],
    blocked: list[str],
) -> None:
    scoped_tenant = scope.get("tenant_hash") or lesson.origin_tenant_hash
    scoped_domain = scope.get("domain") or lesson.domain
    if visibility is MemoryVisibility.LOCAL_RUN:
        if lesson.source_run_id != context.run_id:
            blocked.append("run_scope_mismatch")
        else:
            reasons.append("run_scope_match")
        return
    if visibility is MemoryVisibility.TENANT:
        if not scoped_tenant or scoped_tenant != context.tenant_hash:
            blocked.append("tenant_scope_mismatch")
        else:
            reasons.append("tenant_scope_match")
        return
    if visibility is MemoryVisibility.DOMAIN:
        if scoped_domain != context.domain:
            blocked.append("domain_scope_mismatch")
        else:
            reasons.append("domain_scope_match")
        return
    reasons.append("global_public_scope")


def _check_optional_scope(
    *,
    scope: dict[str, str],
    key: str,
    context_value: str | None,
    reasons: list[str],
    blocked: list[str],
) -> None:
    expected = scope.get(key)
    if expected is None:
        return
    if context_value != expected:
        blocked.append(f"{key}_mismatch")
        return
    reasons.append(f"{key}_match")


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "MemoryApplicabilityContext",
    "evaluate_lesson_applicability",
    "lesson_scope_from_card",
]
