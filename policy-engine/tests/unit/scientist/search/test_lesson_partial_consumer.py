"""Partial lesson answers retain query admission and persisted evidence identity."""

from datetime import UTC, datetime, timedelta

import pytest

from polisyos.core import artifacts
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
    load_lesson_card,
)
from polisyos.scientist.methods.search.transfer_context import TransferContext

AS_OF = datetime(2026, 9, 1, tzinfo=UTC)


def _context(domain):
    return TransferContext(
        task_family="policy",
        domain=domain,
        run_id="reader-run",
        tenant_hash="tenant-a",
        timestamp=AS_OF,
    )


def _registry(tmp_path):
    return LessonRegistry(
        root=tmp_path / "lessons", store=artifacts.FileSystemCAS(tmp_path / "cas")
    )


def _card(name, *, source_run_id="allowed-source", created_at=AS_OF):
    return LessonCard(
        lesson_id=name,
        kind=LessonKind.FAILURE,
        summary=name,
        failure_type="partial_answer",
        stage_name="L1",
        fidelity_level=1,
        candidate_hash="candidate",
        source_run_id=source_run_id,
        created_at=created_at,
        confidence=0.9,
        tags=["partial"],
    )


def _query(**updates):
    return LessonQuery(
        task_family="policy",
        domain="target",
        tenant_hash="tenant-a",
        source_run_id="allowed-source",
        trust_levels=[LessonTrustLevel.LOCAL, LessonTrustLevel.TRANSFERRED],
        min_confidence=0.8,
        tags=["partial"],
        limit=2,
        as_of=AS_OF,
    ).model_copy(update=updates)


def _evidence(entry):
    return (
        entry.artifact_ref,
        entry.card_refs,
        entry.occurrence_count,
        entry.first_seen,
        entry.last_seen,
        entry.transfer_chain,
    )


def test_partial_local_answer_is_filled_by_one_admitted_transfer(tmp_path):
    registry = _registry(tmp_path)
    local_ref = registry.record_local(_card("local-valid"), context=_context("target"))
    source_ref = registry.record_local(_card("transfer-valid"), context=_context("source"))
    source_before = registry.index_snapshot(context=_context("source")).entries[0]

    assert [card.summary for card in registry.query(_query())] == ["local-valid"]
    result = registry.query_with_transfer(_query(), target_context=_context("target"))

    assert [card.summary for card in result] == ["local-valid", "transfer-valid"]
    assert [card.trust_level for card in result] == [
        LessonTrustLevel.LOCAL,
        LessonTrustLevel.TRANSFERRED,
    ]
    assert all(card.source_run_id == "allowed-source" and card.confidence == 0.9 for card in result)
    assert result[1].created_at == load_lesson_card(registry._store, source_ref).created_at
    assert result[1].origin_domain == "source" and len(result[1].transfer_chain) == 1
    assert load_lesson_card(registry._store, local_ref).summary == "local-valid"
    assert _evidence(registry.index_snapshot(context=_context("source")).entries[0]) == (
        _evidence(source_before)
    )
    # A fresh namespace reader observes the actual materialized CAS card.
    assert {card.summary for card in _registry(tmp_path).query(_query())} == {
        "local-valid",
        "transfer-valid",
    }


def test_source_run_filter_excludes_other_sources_before_partial_fill(tmp_path):
    registry = _registry(tmp_path)
    for domain, name in (("target", "local"), ("source", "transfer")):
        registry.record_local(
            _card(f"{name}-wrong-source", source_run_id="other-source"), context=_context(domain)
        )
        registry.record_local(_card(f"{name}-valid"), context=_context(domain))

    assert [card.summary for card in registry.query(_query())] == ["local-valid"]
    result = registry.query_with_transfer(_query(), target_context=_context("target"))
    assert {card.summary for card in result} == {"local-valid", "transfer-valid"}
    target = registry.index_snapshot(context=_context("target"))
    assert {entry.summary for entry in target.entries} == {
        "local-wrong-source",
        "local-valid",
        "transfer-valid",
    }
    assert all(card.source_run_id == "allowed-source" for card in result)


def test_duplicate_evidence_across_routes_does_not_consume_partial_quota_or_refresh(tmp_path):
    registry = _registry(tmp_path)
    source_ref = registry.record_local(_card("duplicate"), context=_context("source"))
    source = load_lesson_card(registry._store, source_ref)
    materialized = registry.materialize_transfer(
        source, target_context=_context("target"), query=_query()
    )
    assert materialized is not None
    before = registry.index_snapshot(context=_context("target")).entries[0]
    # Real copies of the same original evidence occupy several discovery routes.
    for domain in ("copy-a", "copy-b", "copy-c"):
        registry.record_local(source, context=_context(domain))
    registry.record_local(
        _card("distinct", created_at=AS_OF - timedelta(days=1)), context=_context("source")
    )

    result = registry.query_with_transfer(_query(), target_context=_context("target"))
    assert [card.summary for card in result] == ["duplicate", "distinct"]
    assert result[0].lesson_id == materialized.lesson_id
    after = next(
        entry
        for entry in registry.index_snapshot(context=_context("target")).entries
        if entry.summary == "duplicate"
    )
    assert _evidence(after) == _evidence(before)
    assert load_lesson_card(registry._store, after.artifact_ref).created_at == AS_OF
    assert len(_registry(tmp_path).query(_query())) == 2


def test_distinct_newer_evidence_is_not_suppressed_as_route_metadata(tmp_path):
    registry = _registry(tmp_path)
    old_ref = registry.record_local(
        _card("same-pattern", created_at=AS_OF - timedelta(days=1)), context=_context("source")
    )
    old = load_lesson_card(registry._store, old_ref)
    assert registry.materialize_transfer(old, target_context=_context("target"), query=_query())
    before = registry.index_snapshot(context=_context("target")).entries[0]
    new_ref = registry.record_local(_card("same-pattern"), context=_context("source"))

    candidates = registry.find_transfer_candidates(
        _query(), target_context=_context("target"), exclude_cards=registry.query(_query())
    )
    assert len(candidates) == 1
    assert (
        candidates[0].created_at == load_lesson_card(registry._store, new_ref).created_at == AS_OF
    )
    assert candidates[0].created_at != old.created_at
    assert registry.materialize_transfer(
        candidates[0], target_context=_context("target"), query=_query()
    )
    after = registry.index_snapshot(context=_context("target")).entries[0]
    assert after.last_seen == AS_OF and after.occurrence_count == before.occurrence_count + 1


@pytest.mark.parametrize("invalid_time", ["future", "stale"])
def test_partial_fill_uses_the_same_as_of_and_freshness_on_both_routes(tmp_path, invalid_time):
    registry = _registry(tmp_path)
    invalid_at = (
        AS_OF + timedelta(days=1) if invalid_time == "future" else AS_OF - timedelta(days=100)
    )
    for domain, name in (("target", "local"), ("source", "transfer")):
        registry.record_local(
            _card(f"{name}-invalid", created_at=invalid_at), context=_context(domain)
        )
        registry.record_local(_card(f"{name}-valid"), context=_context(domain))

    source_before = registry.index_snapshot(context=_context("source"))
    assert [card.summary for card in registry.query(_query())] == ["local-valid"]
    result = registry.query_with_transfer(_query(), target_context=_context("target"))
    assert {card.summary for card in result} == {"local-valid", "transfer-valid"}
    assert all(card.created_at == AS_OF and card.confidence == 0.9 for card in result)
    assert all(card.trust_level is not LessonTrustLevel.LOW_CONFIDENCE for card in result)
    assert "transfer-invalid" not in {
        entry.summary for entry in registry.index_snapshot(context=_context("target")).entries
    }
    assert [
        _evidence(entry) for entry in registry.index_snapshot(context=_context("source")).entries
    ] == [_evidence(entry) for entry in source_before.entries]
    # Reading at an actual later wall time affects retention, never historical evidence.
    assert all(card.last_accessed_at >= AS_OF for card in _registry(tmp_path).query(_query()))
