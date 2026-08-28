from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir import TypedFailureCard
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    lesson_from_failure_card,
)


def _make_registry(tmp_path):
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = LessonRegistry(root=tmp_path / "search_registry" / "lessons", store=store)
    return store, registry


def test_lesson_registry_dedupes_and_tracks_occurrences(tmp_path) -> None:
    _, registry = _make_registry(tmp_path)
    card = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Budget envelope violated.",
        failure_type="budget_violation",
        stage_name="funnel_L1_heuristic",
        fidelity_level=1,
        candidate_hash="abc123",
        source_run_id="run-1",
        tags=["budget", "tax_reform"],
    )

    registry.record(card)
    registry.record(card.model_copy(update={"lesson_id": "second"}))

    snapshot = registry.index_snapshot()
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].occurrence_count == 2
    assert registry.snapshot_ref() is not None

    results = registry.query(LessonQuery(tags=["budget"], limit=5))
    assert len(results) == 1
    assert results[0].failure_type == "budget_violation"


def test_lesson_registry_invalidate_and_gc(tmp_path) -> None:
    _, registry = _make_registry(tmp_path)
    old_card = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Ancient lesson",
        failure_type="historic_failure",
        stage_name="funnel_L1_heuristic",
        fidelity_level=1,
        candidate_hash="old",
        source_run_id="run-old",
        created_at=datetime.now(UTC) - timedelta(days=200),
        tags=["legacy"],
    )
    registry.record(old_card)
    removed = registry.garbage_collect(ttl_days=90)
    assert removed == 1

    fresh_card = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Fresh lesson",
        failure_type="transport_failure",
        stage_name="funnel_L2_causal",
        fidelity_level=2,
        candidate_hash="fresh",
        source_run_id="run-fresh",
        tags=["transport"],
    )
    registry.record(fresh_card)
    assert registry.invalidate(fresh_card.lesson_id, "contradicted") is True
    assert registry.query(LessonQuery(tags=["transport"], limit=5)) == []


def test_lesson_from_failure_card_preserves_failure_metadata() -> None:
    failure_card = TypedFailureCard(
        judge_name="L2",
        failure_type="non_identifiable",
        severity="blocker",
        description="Effect is not identifiable under the supplied graph.",
        remediation_hint="Add instruments or relax the estimand.",
    )

    lesson = lesson_from_failure_card(
        failure_card,
        candidate_hash="cand-1",
        stage_name="funnel_L2_causal",
        fidelity_level=2,
        source_run_id="run-1",
        tags=["instrumental_variable"],
    )

    assert lesson.kind == LessonKind.FAILURE
    assert lesson.failure_type == "non_identifiable"
    assert lesson.remediation_hint == "Add instruments or relax the estimand."
    assert "instrumental_variable" in lesson.tags
