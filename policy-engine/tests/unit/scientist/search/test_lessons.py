from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

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
    load_lesson_card,
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


@pytest.mark.parametrize(
    "query_fields",
    [
        pytest.param({"domain": "general", "tenant_hash": None}, id="scoped-local"),
        pytest.param({}, id="aggregated-local"),
    ],
)
def test_lesson_queries_write_daily_access_hints_without_index_cas(
    tmp_path, monkeypatch, query_fields
) -> None:
    store, registry = _make_registry(tmp_path)
    source_context = TransferContext(
        task_family="policy",
        domain="general",
        run_id="source-run",
        tenant_hash=None,
    )
    cards = [
        LessonCard(
            kind=LessonKind.FAILURE,
            summary=f"Lesson {index} for the access hint test.",
            failure_type="access_hint",
            stage_name="test",
            fidelity_level=1,
            candidate_hash=f"candidate-{index}",
            source_run_id=f"run-{index}",
            tags=["access-hint-test"],
        )
        for index in range(2)
    ]
    for card in cards:
        registry.record_local(card, context=source_context)

    index_path = registry._index_path_for_context(source_context)
    initial_snapshot_ref = registry.snapshot_ref()
    assert initial_snapshot_ref is not None
    original_index_bytes = index_path.read_bytes()

    access_writes: list[Path] = []
    write_bytes = LessonRegistry._write_bytes

    def count_access_writes(payload: bytes, *, path: Path) -> None:
        if path.parent.name == "access":
            access_writes.append(path)
        write_bytes(payload, path=path)

    monkeypatch.setattr(LessonRegistry, "_write_bytes", staticmethod(count_access_writes))

    cas_writes: list[None] = []
    put_json = store.put_json

    def count_cas_writes(*args, **kwargs):
        cas_writes.append(None)
        return put_json(*args, **kwargs)

    monkeypatch.setattr(store, "put_json", count_cas_writes)

    query = LessonQuery(tags=["access-hint-test"], limit=10, **query_fields)
    first_results = registry.query(query)
    assert {card.lesson_id for card in first_results} == {card.lesson_id for card in cards}
    expected_hint_names = {
        f"{sha256(card.lesson_id.encode('utf-8')).hexdigest()}.txt" for card in cards
    }
    assert len(access_writes) == len(cards)
    assert {path.name for path in access_writes} == expected_hint_names
    assert cas_writes == []
    assert index_path.read_bytes() == original_index_bytes

    second_results = registry.query(query)
    assert {card.lesson_id for card in second_results} == {card.lesson_id for card in cards}
    assert len(access_writes) == len(cards)
    assert cas_writes == []
    assert index_path.read_bytes() == original_index_bytes
    assert registry.snapshot_ref() == initial_snapshot_ref

    restarted = LessonRegistry(root=registry._root, store=store)
    reopened = restarted._load_index_file(index_path)
    assert all(entry.last_accessed_at is not None for entry in reopened.entries)

    restart_results = restarted.query(query)
    assert {card.lesson_id for card in restart_results} == {card.lesson_id for card in cards}
    assert len(access_writes) == len(cards)
    assert cas_writes == []
    assert index_path.read_bytes() == original_index_bytes

    stale_entry = reopened.entries[0]
    stale_hint = restarted._access_path(index_path, stale_entry.lesson_id)
    stale_hint.write_text(
        (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        encoding="utf-8",
    )
    restarted.query(query)
    assert len(access_writes) == len(cards) + 1
    assert access_writes[-1] == stale_hint
    assert cas_writes == []
    assert index_path.read_bytes() == original_index_bytes


def test_gc_uses_evidence_age_for_trust_after_recent_access_and_restart(tmp_path) -> None:
    store, registry = _make_registry(tmp_path)
    context = TransferContext(
        task_family="policy",
        domain="general",
        run_id="source-run",
        tenant_hash=None,
    )
    source_card = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Recent use cannot renew old evidence trust.",
        failure_type="stale_evidence",
        stage_name="test",
        fidelity_level=1,
        candidate_hash="old-evidence",
        source_run_id="source-run",
        created_at=datetime.now(UTC) - timedelta(days=200),
        confidence=0.9,
        tags=["gc-evidence-clock"],
    )
    card_ref = registry.record_local(source_card, context=context)
    index_path = registry._index_path_for_context(context)
    stored_before = load_lesson_card(store, card_ref)
    query = LessonQuery(
        task_family="policy",
        domain="general",
        tenant_hash=None,
        tags=["gc-evidence-clock"],
        limit=1,
    )

    cold = registry.query(query)
    assert len(cold) == 1
    assert cold[0].trust_level == LessonTrustLevel.LOW_CONFIDENCE
    assert cold[0].confidence == 0.5
    access_hint = registry._access_path(index_path, source_card.lesson_id)
    assert access_hint.is_file()
    assert registry.top_patterns(limit=1, context=context)[0].trust_level == LessonTrustLevel.LOCAL

    removed = registry.garbage_collect(ttl_days=90)
    assert removed == 0

    after_gc = registry.index_snapshot(context=context).entries[0]
    assert after_gc.last_accessed_at is not None
    assert after_gc.last_seen == source_card.created_at
    assert after_gc.artifact_ref == card_ref
    assert after_gc.trust_level == LessonTrustLevel.LOW_CONFIDENCE
    pattern = registry.top_patterns(limit=1, context=context)[0]
    assert pattern.trust_level == LessonTrustLevel.LOW_CONFIDENCE
    assert pattern.last_seen == source_card.created_at

    restarted = LessonRegistry(root=registry._root, store=store)
    restarted_pattern = restarted.top_patterns(limit=1, context=context)[0]
    assert restarted_pattern.trust_level == LessonTrustLevel.LOW_CONFIDENCE
    assert restarted_pattern.last_seen == source_card.created_at
    warm = restarted.query(query)
    assert len(warm) == 1
    assert warm[0].trust_level == LessonTrustLevel.LOW_CONFIDENCE
    assert warm[0].confidence == 0.5
    stored_after = load_lesson_card(store, card_ref)
    assert stored_after.model_dump(mode="json") == stored_before.model_dump(mode="json")


def test_corrupt_access_hint_does_not_change_evidence_age_or_trust(tmp_path) -> None:
    store, registry = _make_registry(tmp_path)
    context = TransferContext(
        task_family="policy",
        domain="general",
        run_id="source-run",
        tenant_hash=None,
    )
    source_card = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Old evidence remains old after access.",
        failure_type="stale_evidence",
        stage_name="test",
        fidelity_level=1,
        candidate_hash="stale-candidate",
        source_run_id="source-run",
        created_at=datetime.now(UTC) - timedelta(days=100),
        confidence=0.9,
        tags=["stale-access"],
    )
    card_ref = registry.record_local(source_card, context=context)
    index_path = registry._index_path_for_context(context)
    original_snapshot = registry._load_index_file(index_path)
    original_entry = original_snapshot.entries[0]
    stored_before = load_lesson_card(store, card_ref)

    hint_path = registry._access_path(index_path, source_card.lesson_id)
    hint_path.parent.mkdir(parents=True, exist_ok=True)
    hint_path.write_text("not-a-timestamp", encoding="utf-8")

    restarted = LessonRegistry(root=registry._root, store=store)
    loaded_before_query = restarted.index_snapshot(context=context)
    loaded_entry = loaded_before_query.entries[0]
    assert loaded_entry.last_accessed_at is None
    assert loaded_entry.artifact_ref == original_entry.artifact_ref
    assert loaded_entry.last_seen == original_entry.last_seen

    result = restarted.query(
        LessonQuery(
            task_family="policy",
            domain="general",
            tenant_hash=None,
            tags=["stale-access"],
            limit=1,
        )
    )
    assert len(result) == 1
    assert result[0].lesson_id == source_card.lesson_id
    assert result[0].created_at == source_card.created_at
    assert result[0].source_run_id == source_card.source_run_id
    assert result[0].trust_level == LessonTrustLevel.LOW_CONFIDENCE
    assert result[0].confidence == 0.5

    loaded_after_query = restarted.index_snapshot(context=context)
    queried_entry = loaded_after_query.entries[0]
    assert queried_entry.last_accessed_at is not None
    assert queried_entry.artifact_ref == original_entry.artifact_ref
    assert queried_entry.last_seen == original_entry.last_seen
    assert queried_entry.origin_run_id == original_entry.origin_run_id
    assert queried_entry.origin_domain == original_entry.origin_domain
    stored_after = load_lesson_card(store, card_ref)
    assert stored_after.model_dump(mode="json") == stored_before.model_dump(mode="json")

    strict_warm_query = restarted.query(
        LessonQuery(
            task_family="policy",
            domain="general",
            tenant_hash=None,
            tags=["stale-access"],
            trust_levels=[LessonTrustLevel.LOCAL],
            min_confidence=0.8,
            limit=1,
        )
    )
    assert strict_warm_query == []


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
