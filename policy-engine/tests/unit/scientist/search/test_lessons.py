from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir import TypedFailureCard
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
    lesson_from_failure_card,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
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


def test_repeated_reads_do_not_restore_confidence_without_new_evidence(tmp_path) -> None:
    _, registry = _make_registry(tmp_path)
    registry.record(
        LessonCard(
            kind=LessonKind.FAILURE,
            summary="Stale evidence must remain bounded.",
            failure_type="stale_evidence",
            stage_name="funnel_L1_heuristic",
            fidelity_level=1,
            candidate_hash="stale-candidate",
            source_run_id="run-stale",
            created_at=datetime.now(UTC) - timedelta(days=100),
            confidence=0.9,
            tags=["stale"],
        )
    )

    cold = registry.query(LessonQuery(tags=["stale"], limit=1))
    assert len(cold) == 1
    assert cold[0].trust_level == LessonTrustLevel.LOW_CONFIDENCE
    assert cold[0].confidence == 0.5

    warm_strict = registry.query(
        LessonQuery(
            tags=["stale"],
            trust_levels=[LessonTrustLevel.LOCAL],
            min_confidence=0.8,
            limit=1,
        )
    )
    assert warm_strict == []


def test_lesson_index_local_json_round_trips_required_nullable_source_scope(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    root = tmp_path / "search_registry" / "lessons"
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash=None,
    )
    registry = LessonRegistry(root=root, store=store)
    registry.record_local(
        LessonCard(
            kind=LessonKind.FAILURE,
            summary="Unscoped source scope remains explicit.",
            failure_type="scope_round_trip",
            stage_name="test",
            fidelity_level=1,
            candidate_hash="round-trip",
            source_run_id="source-run",
        ),
        context=source,
    )

    index_path = registry._index_path_for_context(source)
    persisted_scope = json.loads(index_path.read_text(encoding="utf-8"))["source_scope"]
    assert persisted_scope["tenant_kind"] == "unscoped"
    assert "tenant_hash" in persisted_scope
    assert persisted_scope["tenant_hash"] is None

    fresh_registry = LessonRegistry(root=root, store=store)
    reopened = fresh_registry.index_snapshot(context=source)
    assert reopened.source_scope is not None
    assert reopened.source_scope.tenant_hash is None
    assert [entry.failure_type for entry in reopened.entries] == ["scope_round_trip"]


def test_lesson_index_local_json_keeps_scoped_source_scope(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    root = tmp_path / "search_registry" / "lessons"
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash="tenant-a",
    )
    registry = LessonRegistry(root=root, store=store)
    registry.record_local(
        LessonCard(
            kind=LessonKind.FAILURE,
            summary="Scoped source scope remains bound.",
            failure_type="scope_round_trip",
            stage_name="test",
            fidelity_level=1,
            candidate_hash="round-trip",
            source_run_id="source-run",
        ),
        context=source,
    )

    fresh_registry = LessonRegistry(root=root, store=store)
    reopened = fresh_registry.index_snapshot(context=source)
    assert reopened.source_scope is not None
    assert reopened.source_scope.tenant_kind == "tenant"
    assert reopened.source_scope.tenant_hash == "tenant-a"


def test_lesson_index_local_json_rejects_restored_null_omission(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    root = tmp_path / "search_registry" / "lessons"
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash=None,
    )
    registry = LessonRegistry(root=root, store=store)

    def write_without_required_null(snapshot, *, path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            snapshot.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        LessonRegistry,
        "_write_index_file",
        staticmethod(write_without_required_null),
    )
    registry.record_local(
        LessonCard(
            kind=LessonKind.FAILURE,
            summary="Restoring null omission loses required scope binding.",
            failure_type="scope_round_trip",
            stage_name="test",
            fidelity_level=1,
            candidate_hash="round-trip",
            source_run_id="source-run",
        ),
        context=source,
    )

    fresh_registry = LessonRegistry(root=root, store=store)
    with pytest.raises(TransferScopeRefusedError) as captured:
        fresh_registry.index_snapshot(context=source)
    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY
