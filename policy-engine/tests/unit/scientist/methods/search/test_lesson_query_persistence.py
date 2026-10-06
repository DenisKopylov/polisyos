"""Effective lesson filters and retention clocks through actual CAS consumers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.controller import SearchController
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
    load_lesson_card,
)
from polisyos.scientist.methods.search.transfer_context import TransferContext, TransferPolicy


def registry_card(tmp_path, *, days=0):
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(tmp_path / "registry", store=store)
    source = TransferContext(
        task_family="discovery", domain="source", run_id="source-run", tenant_hash="tenant-a"
    )
    card = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Producer observation",
        failure_type="counterexample",
        stage_name="stage-a",
        fidelity_level=2,
        candidate_hash="candidate-one",
        source_run_id="source-run",
        task_family="discovery",
        domain="source",
        created_at=datetime.now(UTC) - timedelta(days=days),
        confidence=0.9,
        tags=["measured"],
    )
    return store, registry, source, card


@pytest.mark.parametrize("serialized", [False, True])
def test_real_controller_keeps_typed_nested_context_in_lesson_consumer(tmp_path, serialized):
    _, registry, source, card = registry_card(tmp_path)
    registry.record_local(card, context=source)
    payload = source.model_dump(mode="json") if serialized else source
    controller = object.__new__(SearchController)
    hints = controller._build_lesson_hints(
        {"lesson_registry": registry, "transfer_context": payload}
    )
    assert len(hints) == 1
    assert hints[0]["task_family"] == "discovery" and hints[0]["domain"] == "source"


def test_destination_projection_uses_all_effective_query_filters(tmp_path):
    _, registry, source, card = registry_card(tmp_path)
    registry.record_local(card, context=source)
    target = source.model_copy(update={"domain": "destination", "run_id": "target-run"})
    query = LessonQuery(
        task_family="discovery",
        domain="destination",
        source_run_id="source-run",
        stage_name="stage-a",
        fidelity_level=2,
        tags=["measured"],
        candidate_hash="candidate-one",
        trust_levels=[LessonTrustLevel.TRANSFERRED],
        min_confidence=0.8,
    )
    rows = registry.query_with_transfer(query, target_context=target)
    assert len(rows) == 1 and rows[0].domain == "destination"
    assert rows[0].trust_level == LessonTrustLevel.TRANSFERRED and rows[0].confidence == 0.9
    assert len(registry.query(query.model_copy(update={"tenant_hash": "tenant-a"}))) == 1
    for field, value in [
        ("source_run_id", "different"),
        ("trust_levels", [LessonTrustLevel.LOCAL]),
        ("candidate_hash", "different"),
        ("fidelity_level", 3),
        ("stage_name", "different"),
        ("tags", ["absent"]),
        ("min_confidence", 1.0),
    ]:
        assert (
            registry.query_with_transfer(
                query.model_copy(update={field: value}), target_context=target
            )
            == []
        ), field


def test_active_policy_demotes_local_and_transferred_confidence_equally(tmp_path):
    _, registry, source, card = registry_card(tmp_path, days=45)
    registry.record_local(card, context=source)
    policy = TransferPolicy(ttl_days=30)
    target = source.model_copy(update={"domain": "destination", "run_id": "target-run"})
    strict = LessonQuery(task_family="discovery", tags=["measured"], min_confidence=0.8)
    assert registry.query_with_transfer(strict, target_context=source, policy=policy) == []
    assert registry.query_with_transfer(strict, target_context=target, policy=policy) == []
    permissive = strict.model_copy(update={"min_confidence": 0.0})
    local = registry.query_with_transfer(permissive, target_context=source, policy=policy)[0]
    transferred = registry.query_with_transfer(permissive, target_context=target, policy=policy)[0]
    assert (local.confidence, transferred.confidence) == (0.5, 0.5)
    assert local.trust_level == transferred.trust_level == LessonTrustLevel.LOW_CONFIDENCE


def test_access_writes_no_cas_snapshot_and_repeated_reads_cannot_refresh_evidence(tmp_path):
    store, registry, source, card = registry_card(tmp_path, days=100)
    ref = registry.record_local(card, context=source)
    snapshot_ref = registry.snapshot_ref()
    index_path = registry._index_path_for_context(source)
    before = index_path.read_bytes()
    query = LessonQuery(
        task_family="discovery", domain="source", tenant_hash="tenant-a", tags=["measured"]
    )
    assert registry.query(query)[0].confidence == 0.5
    access_files = list(index_path.parent.glob("access/*.txt"))
    assert len(access_files) == 1
    stamp = access_files[0].stat().st_mtime_ns
    assert registry.query(query)[0].confidence == 0.5
    assert access_files[0].stat().st_mtime_ns == stamp
    assert index_path.read_bytes() == before and registry.snapshot_ref() == snapshot_ref
    restarted = LessonRegistry(tmp_path / "registry", store=store)
    entry = restarted.index_snapshot(context=source).entries[0]
    assert entry.last_accessed_at > entry.last_seen
    assert restarted.garbage_collect(ttl_days=30) == 0
    assert restarted.query(query.model_copy(update={"min_confidence": 0.8})) == []
    original = load_lesson_card(store, ref)
    assert original.confidence == 0.9 and original.created_at == card.created_at


def test_older_arrival_cannot_replace_newest_actual_evidence_ref(tmp_path):
    store, registry, source, card = registry_card(tmp_path)
    newest = registry.record_local(card, context=source)
    older = card.model_copy(
        update={
            "lesson_id": "older-arrival",
            "created_at": card.created_at - timedelta(days=100),
            "confidence": 0.4,
            "candidate_hash": "old-candidate",
        }
    )
    registry.record_local(older, context=source)
    entry = registry.index_snapshot(context=source).entries[0]
    assert entry.artifact_ref == newest and entry.last_seen == card.created_at
    assert entry.occurrence_count == 2
    assert load_lesson_card(store, entry.artifact_ref).candidate_hash == "candidate-one"
    rows = registry.query(
        LessonQuery(
            task_family="discovery", domain="source", tenant_hash="tenant-a", min_confidence=0.8
        )
    )
    assert len(rows) == 1 and rows[0].candidate_hash == "candidate-one"
