from __future__ import annotations

import pytest
from polisyos.scientist.orchestration.memory import (
    LessonApplicability,
    MemoryApplicabilityContext,
    MemoryContaminationPolicy,
    MemoryRetrievalResult,
    MemoryRetrievedLesson,
    MemoryVisibility,
    apply_reflexive_scope,
    build_reflexive_memory_event,
    format_warning_only_memory_context,
    retrieve_reflexive_lessons,
)
from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind


def _lesson(lesson_id: str = "lesson_a", **updates) -> LessonCard:
    base = LessonCard(
        lesson_id=lesson_id,
        kind=LessonKind.FAILURE,
        summary="Avoid promotion before source verification.",
        failure_type="unsupported_claim",
        stage_name="evidence_gate",
        fidelity_level=2,
        candidate_hash="candidate_a",
        source_run_id="source_run",
        task_family="policy",
        domain="tax",
        origin_tenant_hash="tenant_a",
        anti_patterns=["unsupported_claim"],
        remediation_hint="Verify snippet spans before claiming readiness.",
    )
    return base.model_copy(update=updates)


def test_retrieval_returns_lesson_ids_reasons_and_warning_only_mode() -> None:
    lesson = apply_reflexive_scope(
        _lesson(),
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        workflow_id="scientist_policy_design",
    )
    context = MemoryApplicabilityContext(
        run_id="run_target",
        domain="tax",
        workflow_id="scientist_policy_design",
    )

    result = retrieve_reflexive_lessons([lesson], context=context)

    assert result.retrieved_lessons[0].lesson_id == "lesson_a"
    assert result.retrieved_lessons[0].influence_mode == "warning_anti_pattern"
    assert result.retrieved_lessons[0].applicability.reasons
    assert result.events[0].action == "retrieved"
    assert result.events[0].metadata["influence_mode"] == "warning_anti_pattern"


def test_contaminated_lesson_is_rejected_not_retrieved() -> None:
    lesson = apply_reflexive_scope(
        _lesson(metadata={"hidden_suite_id": "hidden-suite"}),
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
    )
    context = MemoryApplicabilityContext(run_id="run_target", domain="tax")
    policy = MemoryContaminationPolicy(hidden_suite_ids={"hidden-suite"})

    result = retrieve_reflexive_lessons(
        [lesson],
        context=context,
        contamination_policy=policy,
    )

    assert result.retrieved_lessons == []
    assert result.rejected_lessons[0].applies is False
    assert "contaminated_hidden_eval" in result.rejected_lessons[0].reasons
    assert result.events[0].action == "rejected"


def test_warning_only_memory_context_rejects_revoked_influence() -> None:
    applicability = LessonApplicability(
        lesson_id="lesson_revoked",
        applies=True,
        reasons=["revoked"],
    )
    result = MemoryRetrievalResult(
        run_id="run_target",
        retrieved_lessons=[
            MemoryRetrievedLesson(
                lesson_id="lesson_revoked",
                summary="Do not reuse revoked lesson.",
                anti_patterns=["revoked_pattern"],
                applicability=applicability,
                source_run_id="source_run",
            )
        ],
        events=[
            build_reflexive_memory_event(
                run_id="run_target",
                lesson_id="lesson_revoked",
                action="retrieved",
                applicability=applicability,
            )
        ],
    )

    with pytest.raises(ValueError, match="lesson cannot influence"):
        format_warning_only_memory_context(result)


def test_warning_only_memory_context_is_not_claim_evidence() -> None:
    lesson = apply_reflexive_scope(_lesson(), visibility=MemoryVisibility.DOMAIN, domain="tax")
    context = MemoryApplicabilityContext(run_id="run_target", domain="tax")
    result = retrieve_reflexive_lessons([lesson], context=context)

    rendered = format_warning_only_memory_context(result)

    assert "not claim evidence" in rendered
    assert "mode=warning_anti_pattern" in rendered
    assert "lesson_id=lesson_a" in rendered
