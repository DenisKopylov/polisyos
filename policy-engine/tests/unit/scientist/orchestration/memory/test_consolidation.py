from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.reflexion_evaluator import ReflexionReplayEvaluation
from polisyos.scientist.orchestration.memory import (
    LessonApplicability,
    assert_lesson_can_influence,
    build_reflexion_memory_recovery_eval_report,
    build_reflexion_recovery_eval_report,
    consolidate_lessons,
    revoke_lesson,
)
from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind, LessonQuery, LessonRegistry


def _lesson(lesson_id: str, **updates) -> LessonCard:
    base = LessonCard(
        lesson_id=lesson_id,
        kind=LessonKind.FAILURE,
        summary="Do not trust unsupported source snippets.",
        failure_type="unsupported_claim",
        stage_name="evidence_gate",
        fidelity_level=2,
        candidate_hash="candidate_a",
        source_run_id="source_run",
        task_family="policy",
        domain="tax",
        anti_patterns=["unsupported_claim"],
    )
    return base.model_copy(update=updates)


def test_consolidation_preserves_source_lesson_ids() -> None:
    consolidated = consolidate_lessons([_lesson("lesson_a"), _lesson("lesson_b")])

    assert len(consolidated.lessons) == 1
    assert consolidated.merged_lesson_ids == ["lesson_b"]
    assert "lesson_a" in consolidated.lessons[0].metadata["consolidated_source_lesson_ids"]
    assert "lesson_b" in consolidated.lessons[0].metadata["consolidated_source_lesson_ids"]


def test_revoked_lesson_cannot_influence_and_registry_hides_it(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    lesson = _lesson("lesson_a")
    registry.record_local(lesson)

    event = revoke_lesson(
        registry,
        lesson_id="lesson_a",
        reason="source_withdrawn",
        run_id="run_target",
    )

    assert event.action == "revoked"
    assert event.metadata["registry_invalidated"] is True
    assert registry.query(LessonQuery(domain="tax", task_family="policy")) == []
    with pytest.raises(ValueError, match="lesson cannot influence"):
        assert_lesson_can_influence(event.applicability)


def test_recovery_eval_report_requires_improvement_consistency() -> None:
    report = build_reflexion_recovery_eval_report(
        run_id="run_memory_eval",
        held_out_scenario_count=20,
        baseline_recovery_rate=0.4,
        memory_recovery_rate=0.55,
    )

    assert report.improved is True
    assert report.recovery_delta == pytest.approx(0.15)
    with pytest.raises(ValueError):
        LessonApplicability(lesson_id="lesson_a", applies=False, reasons=[])


def test_memory_recovery_report_accepts_existing_reflexion_replay_evaluations() -> None:
    baseline = ReflexionReplayEvaluation(sample_count=4, pass_rate=0.25)
    memory = ReflexionReplayEvaluation(sample_count=4, pass_rate=0.75)

    report = build_reflexion_memory_recovery_eval_report(
        run_id="run_memory_eval",
        baseline_evaluation=baseline,
        memory_evaluation=memory,
    )

    assert report.held_out_scenario_count == 4
    assert report.baseline_recovery_rate == 0.25
    assert report.memory_recovery_rate == 0.75
    assert report.improved is True
