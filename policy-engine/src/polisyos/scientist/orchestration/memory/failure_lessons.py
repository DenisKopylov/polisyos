"""Governed reflexive-memory facade over failure cards and lesson cards."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.scientist.methods.search.failure_cards import TypedFailureCard
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonQuery,
    LessonRegistry,
    lesson_from_failure_card,
)


class MemoryVisibility(str, Enum):
    """Visibility scopes for reusable reflexive lessons."""

    LOCAL_RUN = "local_run"
    TENANT = "tenant"
    DOMAIN = "domain"
    GLOBAL_PUBLIC = "global_public"


class LessonApplicability(BaseModel):
    """Reasoned applicability decision for a lesson in a target run."""

    model_config = ConfigDict(extra="forbid")

    lesson_id: str = Field(min_length=1)
    applies: bool
    reasons: list[str] = Field(default_factory=list)
    scope: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _require_reasons(self) -> LessonApplicability:
        if not self.reasons:
            raise ValueError("LessonApplicability must include reasons")
        return self


class ReflexiveMemoryEvent(BaseModel):
    """Auditable memory retrieval/application/revocation event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    run_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    action: Literal["retrieved", "applied", "rejected", "revoked"]
    applicability: LessonApplicability
    research_dag_node_id: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_event(self) -> ReflexiveMemoryEvent:
        if self.applicability.lesson_id != self.lesson_id:
            raise ValueError("ReflexiveMemoryEvent lesson_id must match applicability")
        if self.action in {"retrieved", "applied"} and not self.applicability.applies:
            raise ValueError("retrieved/applied memory events require applicable lessons")
        return self


class ReflexionRecoveryEvalReport(BaseModel):
    """Held-out recovery measurement for memory-assisted Reflexion."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    held_out_scenario_count: int = Field(gt=0)
    baseline_recovery_rate: float = Field(ge=0.0, le=1.0)
    memory_recovery_rate: float = Field(ge=0.0, le=1.0)
    recovery_delta: float
    improved: bool
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_delta(self) -> ReflexionRecoveryEvalReport:
        expected = round(self.memory_recovery_rate - self.baseline_recovery_rate, 12)
        if round(float(self.recovery_delta), 12) != expected:
            raise ValueError("recovery_delta must equal memory_recovery_rate - baseline")
        if self.improved != (self.recovery_delta > 0.0):
            raise ValueError("improved must reflect positive recovery_delta")
        return self


def build_reflexive_lesson_scope(
    *,
    visibility: MemoryVisibility = MemoryVisibility.DOMAIN,
    tenant_hash: str | None = None,
    domain: str | None = None,
    workflow_id: str | None = None,
    method_family: str | None = None,
    expires_at: datetime | None = None,
) -> dict[str, str]:
    """Build a compact scope dictionary stored on reusable lesson metadata."""

    scope = {"visibility": visibility.value}
    if tenant_hash:
        scope["tenant_hash"] = tenant_hash
    if domain:
        scope["domain"] = domain
    if workflow_id:
        scope["workflow_id"] = workflow_id
    if method_family:
        scope["method_family"] = method_family
    if expires_at is not None:
        scope["expires_at"] = expires_at.astimezone(UTC).isoformat()
    return scope


def apply_reflexive_scope(
    lesson: LessonCard,
    *,
    visibility: MemoryVisibility = MemoryVisibility.DOMAIN,
    tenant_hash: str | None = None,
    domain: str | None = None,
    workflow_id: str | None = None,
    method_family: str | None = None,
    expires_at: datetime | None = None,
) -> LessonCard:
    """Return a lesson card annotated with governed reflexive-memory scope."""

    scope = build_reflexive_lesson_scope(
        visibility=visibility,
        tenant_hash=tenant_hash or lesson.origin_tenant_hash,
        domain=domain or lesson.domain,
        workflow_id=workflow_id,
        method_family=method_family,
        expires_at=expires_at,
    )
    return lesson.model_copy(
        update={
            "domain": domain or lesson.domain,
            "metadata": {
                **lesson.metadata,
                "memory_scope": scope,
                "memory_visibility": visibility.value,
                "reusable_memory": True,
            },
        }
    )


def failure_card_to_reflexive_lesson(
    failure_card: TypedFailureCard,
    *,
    candidate_hash: str,
    stage_name: str,
    fidelity_level: int,
    source_run_id: str,
    visibility: MemoryVisibility = MemoryVisibility.DOMAIN,
    tenant_hash: str | None = None,
    domain: str | None = None,
    workflow_id: str | None = None,
    method_family: str | None = None,
    expires_at: datetime | None = None,
    tags: Iterable[str] | None = None,
    trace_refs: Iterable[str] | None = None,
) -> LessonCard:
    """Translate an existing failure card into a scoped reflexive lesson."""

    lesson = lesson_from_failure_card(
        failure_card,
        candidate_hash=candidate_hash,
        stage_name=stage_name,
        fidelity_level=fidelity_level,
        source_run_id=source_run_id,
        tags=tags,
        trace_refs=trace_refs,
    )
    return apply_reflexive_scope(
        lesson,
        visibility=visibility,
        tenant_hash=tenant_hash,
        domain=domain,
        workflow_id=workflow_id,
        method_family=method_family,
        expires_at=expires_at,
    )


def build_reflexive_memory_event(
    *,
    run_id: str,
    lesson_id: str,
    action: Literal["retrieved", "applied", "rejected", "revoked"],
    applicability: LessonApplicability,
    research_dag_node_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReflexiveMemoryEvent:
    """Build a validated memory event with a stable public shape."""

    return ReflexiveMemoryEvent(
        run_id=run_id,
        lesson_id=lesson_id,
        action=action,
        applicability=applicability,
        research_dag_node_id=research_dag_node_id,
        metadata=metadata or {},
    )


def build_reflexion_recovery_eval_report(
    *,
    run_id: str,
    held_out_scenario_count: int,
    baseline_recovery_rate: float,
    memory_recovery_rate: float,
    metadata: dict[str, Any] | None = None,
) -> ReflexionRecoveryEvalReport:
    """Create a deterministic held-out recovery report for Phase 2.4 gates."""

    delta = memory_recovery_rate - baseline_recovery_rate
    return ReflexionRecoveryEvalReport(
        run_id=run_id,
        held_out_scenario_count=held_out_scenario_count,
        baseline_recovery_rate=baseline_recovery_rate,
        memory_recovery_rate=memory_recovery_rate,
        recovery_delta=delta,
        improved=delta > 0.0,
        metadata=metadata or {},
    )


def build_reflexion_memory_recovery_eval_report(
    *,
    run_id: str,
    baseline_evaluation: Any,
    memory_evaluation: Any,
    metadata: dict[str, Any] | None = None,
) -> ReflexionRecoveryEvalReport:
    """Build a recovery report from existing Reflexion replay/eval outputs."""

    baseline_rate = _extract_recovery_rate(baseline_evaluation)
    memory_rate = _extract_recovery_rate(memory_evaluation)
    scenario_count = max(
        _extract_sample_count(baseline_evaluation),
        _extract_sample_count(memory_evaluation),
    )
    return build_reflexion_recovery_eval_report(
        run_id=run_id,
        held_out_scenario_count=scenario_count,
        baseline_recovery_rate=baseline_rate,
        memory_recovery_rate=memory_rate,
        metadata={
            "baseline_source": type(baseline_evaluation).__name__,
            "memory_source": type(memory_evaluation).__name__,
            **(metadata or {}),
        },
    )


class ReflexiveMemoryFacade:
    """Thin governed facade around the existing CAS-backed lesson registry."""

    def __init__(self, registry: LessonRegistry) -> None:
        self.registry = registry

    def record_lesson(
        self,
        lesson: LessonCard,
        *,
        hidden_ref_ids: set[str] | None = None,
        hidden_suite_ids: set[str] | None = None,
        canary_tokens: set[str] | None = None,
    ) -> Any:
        """Record a reusable lesson only after contamination checks pass."""

        from polisyos.scientist.orchestration.memory.contamination import (
            MemoryContaminationPolicy,
            assert_reusable_memory_clean,
            lesson_payload_for_contamination,
        )

        policy = MemoryContaminationPolicy(
            hidden_ref_ids=hidden_ref_ids or set(),
            hidden_suite_ids=hidden_suite_ids or set(),
            canary_tokens=canary_tokens or set(),
        )
        assert_reusable_memory_clean(lesson_payload_for_contamination(lesson), policy=policy)
        return self.registry.record_local(lesson)

    def record_failure_card(
        self,
        failure_card: TypedFailureCard,
        *,
        candidate_hash: str,
        stage_name: str,
        fidelity_level: int,
        source_run_id: str,
        visibility: MemoryVisibility = MemoryVisibility.DOMAIN,
        tenant_hash: str | None = None,
        domain: str | None = None,
        workflow_id: str | None = None,
        method_family: str | None = None,
        expires_at: datetime | None = None,
        hidden_ref_ids: set[str] | None = None,
        hidden_suite_ids: set[str] | None = None,
        canary_tokens: set[str] | None = None,
    ) -> Any:
        """Create, scope and record a failure lesson."""

        lesson = failure_card_to_reflexive_lesson(
            failure_card,
            candidate_hash=candidate_hash,
            stage_name=stage_name,
            fidelity_level=fidelity_level,
            source_run_id=source_run_id,
            visibility=visibility,
            tenant_hash=tenant_hash,
            domain=domain,
            workflow_id=workflow_id,
            method_family=method_family,
            expires_at=expires_at,
        )
        return self.record_lesson(
            lesson,
            hidden_ref_ids=hidden_ref_ids,
            hidden_suite_ids=hidden_suite_ids,
            canary_tokens=canary_tokens,
        )

    def retrieve(
        self,
        query: LessonQuery,
        *,
        context: Any,
        limit: int = 10,
        revoked_lesson_ids: Iterable[str] = (),
        hidden_ref_ids: set[str] | None = None,
        hidden_suite_ids: set[str] | None = None,
        canary_tokens: set[str] | None = None,
    ) -> Any:
        """Retrieve governed warning-only lessons from the existing registry."""

        from polisyos.scientist.orchestration.memory.applicability import MemoryApplicabilityContext
        from polisyos.scientist.orchestration.memory.contamination import MemoryContaminationPolicy
        from polisyos.scientist.orchestration.memory.retrieval import retrieve_reflexive_lessons_from_registry

        active_context = (
            context
            if isinstance(context, MemoryApplicabilityContext)
            else MemoryApplicabilityContext.model_validate(context)
        )
        policy = MemoryContaminationPolicy(
            hidden_ref_ids=hidden_ref_ids or set(),
            hidden_suite_ids=hidden_suite_ids or set(),
            canary_tokens=canary_tokens or set(),
        )
        return retrieve_reflexive_lessons_from_registry(
            self.registry,
            query,
            context=active_context,
            contamination_policy=policy,
            limit=limit,
            revoked_lesson_ids=set(revoked_lesson_ids),
        )

    def revoke(self, lesson_id: str, *, reason: str, run_id: str) -> ReflexiveMemoryEvent:
        """Invalidate a lesson in the underlying registry and return an audit event."""

        from polisyos.scientist.orchestration.memory.consolidation import revoke_lesson

        return revoke_lesson(self.registry, lesson_id=lesson_id, reason=reason, run_id=run_id)


def _extract_recovery_rate(evaluation: Any) -> float:
    if isinstance(evaluation, dict):
        if "reflexion_recovery_rate" in evaluation:
            return float(evaluation["reflexion_recovery_rate"])
        if "pass_rate" in evaluation:
            return float(evaluation["pass_rate"])
        metrics = evaluation.get("holdout_metrics")
        if isinstance(metrics, dict) and "reflexion_recovery_rate" in metrics:
            return float(metrics["reflexion_recovery_rate"])
        if isinstance(metrics, dict) and "retry_success_rate" in metrics:
            return float(metrics["retry_success_rate"])
    for attr in ("reflexion_recovery_rate", "pass_rate", "retry_success_rate"):
        if hasattr(evaluation, attr):
            return float(getattr(evaluation, attr))
    metrics = getattr(evaluation, "holdout_metrics", None)
    if isinstance(metrics, dict):
        if "reflexion_recovery_rate" in metrics:
            return float(metrics["reflexion_recovery_rate"])
        if "retry_success_rate" in metrics:
            return float(metrics["retry_success_rate"])
    raise ValueError("could not extract Reflexion recovery rate")


def _extract_sample_count(evaluation: Any) -> int:
    if isinstance(evaluation, dict):
        if "sample_count" in evaluation:
            return max(1, int(evaluation["sample_count"]))
        counts = evaluation.get("sample_counts")
        if isinstance(counts, dict):
            return max(1, max((int(value) for value in counts.values()), default=1))
    if hasattr(evaluation, "sample_count"):
        return max(1, int(evaluation.sample_count))
    counts = getattr(evaluation, "sample_counts", None)
    if isinstance(counts, dict):
        return max(1, max((int(value) for value in counts.values()), default=1))
    return 1


__all__ = [
    "LessonApplicability",
    "MemoryVisibility",
    "ReflexionRecoveryEvalReport",
    "ReflexiveMemoryEvent",
    "ReflexiveMemoryFacade",
    "apply_reflexive_scope",
    "build_reflexion_memory_recovery_eval_report",
    "build_reflexion_recovery_eval_report",
    "build_reflexive_lesson_scope",
    "build_reflexive_memory_event",
    "failure_card_to_reflexive_lesson",
]
