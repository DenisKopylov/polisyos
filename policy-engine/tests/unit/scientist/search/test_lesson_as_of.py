"""Real CAS lesson admission uses evidence time, independently of retention."""

from datetime import UTC, datetime, timedelta

import pytest

from polisyos.core import artifacts
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
)
from polisyos.scientist.methods.search.transfer_context import TransferContext

AS_OF = datetime(2020, 1, 1, tzinfo=UTC)


def _card(created_at=AS_OF):
    return LessonCard(
        kind=LessonKind.FAILURE,
        summary="Persisted evidence has an explicit occurrence time.",
        failure_type="temporal_evidence",
        stage_name="L1",
        fidelity_level=1,
        candidate_hash="candidate",
        source_run_id="source",
        created_at=created_at,
        confidence=0.9,
        task_family="policy",
        domain="source",
        origin_tenant_hash="tenant-a",
    )


def _registry(tmp_path):
    return LessonRegistry(
        root=tmp_path / "lessons", store=artifacts.FileSystemCAS(tmp_path / "cas")
    )


def _context(domain, *, timestamp=AS_OF):
    return TransferContext(
        domain=domain, run_id="reader", timestamp=timestamp, tenant_hash="tenant-a"
    )


@pytest.mark.parametrize("route", ["local", "transfer", "materialize", "aggregate"])
def test_future_cas_evidence_is_not_available_at_past_as_of(tmp_path, route):
    registry = _registry(tmp_path)
    future = _card(AS_OF + timedelta(days=1))
    registry.record_local(future, context=_context("source"))
    snapshot = registry.snapshot_ref()
    # Reopen the actual index and CAS; retained metadata is not admission.
    registry = _registry(tmp_path)
    if route == "local":
        result = registry.query_with_transfer(
            LessonQuery(domain="source", tenant_hash="tenant-a"),
            target_context=_context("source"),
        )
    elif route == "transfer":
        result = registry.query_with_transfer(LessonQuery(), target_context=_context("target"))
    elif route == "materialize":
        result = registry.materialize_transfer(future, target_context=_context("target"))
    else:
        result = registry.query(LessonQuery(as_of=AS_OF))
    assert result is None if route == "materialize" else result == []
    assert registry.index_snapshot(context=_context("target")).entries == []
    assert LessonRegistry.load_snapshot(registry._store, snapshot).entries[0].last_seen == (
        future.created_at
    )


@pytest.mark.parametrize("route", ["local", "transfer", "materialize", "aggregate"])
def test_evidence_exactly_at_as_of_remains_available(tmp_path, route):
    registry = _registry(tmp_path)
    card = _card()
    registry.record_local(card, context=_context("source"))
    if route == "local":
        result = registry.query(LessonQuery(domain="source", tenant_hash="tenant-a", as_of=AS_OF))
    elif route == "transfer":
        result = registry.query_with_transfer(LessonQuery(), target_context=_context("target"))
    elif route == "materialize":
        result = registry.materialize_transfer(card, target_context=_context("target"))
    else:
        result = registry.query(LessonQuery(as_of=AS_OF))
    assert result
    effective = result if route == "materialize" else result[0]
    assert effective.created_at == AS_OF
    assert effective.confidence == 0.9


def test_retention_reads_and_restart_never_refresh_evidence(tmp_path):
    registry = _registry(tmp_path)
    registry.record_local(_card(), context=_context("source"))
    later = AS_OF + timedelta(days=100)
    broad = LessonQuery(domain="source", tenant_hash="tenant-a", as_of=later)
    before_read = datetime.now(UTC)
    first = registry.query(broad)
    assert first[0].confidence == 0.5
    assert first[0].trust_level is LessonTrustLevel.LOW_CONFIDENCE
    assert before_read <= first[0].last_accessed_at <= datetime.now(UTC)
    strict = broad.model_copy(
        update={"min_confidence": 0.8, "trust_levels": [LessonTrustLevel.LOCAL]}
    )
    assert registry.query(strict) == []
    assert _registry(tmp_path).query(strict) == []
    # The same access sidecar cannot make evidence from the next day exist early.
    assert (
        _registry(tmp_path).query(
            LessonQuery(domain="source", tenant_hash="tenant-a", as_of=AS_OF - timedelta(seconds=1))
        )
        == []
    )


def test_conflicting_as_of_is_refused_before_materialization(tmp_path):
    registry = _registry(tmp_path)
    registry.record_local(_card(), context=_context("source"))
    with pytest.raises(ValueError, match="as.of"):
        registry.query_with_transfer(
            LessonQuery(as_of=AS_OF + timedelta(days=1)),
            target_context=_context("target"),
        )
    with pytest.raises(ValueError, match="as.of"):
        registry.materialize_transfer(
            _card(),
            target_context=_context("target"),
            query=LessonQuery(as_of=AS_OF + timedelta(days=1)),
        )
    assert registry.index_snapshot(context=_context("target")).entries == []


def test_query_as_of_round_trip_preserves_explicit_time():
    query = LessonQuery(as_of=AS_OF)
    assert LessonQuery.model_validate_json(query.model_dump_json()).as_of == AS_OF
    assert LessonQuery().as_of is None


def test_newer_persisted_version_is_not_reinterpreted_as_older_evidence(tmp_path):
    registry = _registry(tmp_path)
    registry.record_local(_card(), context=_context("source"))
    later_card = _card(AS_OF + timedelta(days=1))
    registry.record_local(later_card, context=_context("source"))
    snapshot = registry.index_snapshot(context=_context("source"))
    assert snapshot.entries[0].occurrence_count == 2
    assert len(snapshot.entries[0].card_refs) == 2
    assert (
        _registry(tmp_path).query(LessonQuery(domain="source", tenant_hash="tenant-a", as_of=AS_OF))
        == []
    )
    assert (
        _registry(tmp_path)
        .query(LessonQuery(domain="source", tenant_hash="tenant-a", as_of=later_card.created_at))[0]
        .created_at
        == later_card.created_at
    )


def test_aggregate_transfer_lookup_keeps_the_explicit_target_time(tmp_path):
    registry = _registry(tmp_path)
    registry.record_local(_card(AS_OF + timedelta(days=1)), context=_context("source"))
    assert (
        registry.query_with_transfer(
            LessonQuery(),
            target_context=TransferContext(domain="isolated::reader", timestamp=AS_OF),
        )
        == []
    )


def test_naive_query_time_is_refused(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        _registry(tmp_path).query(LessonQuery(as_of=AS_OF.replace(tzinfo=None)))


@pytest.mark.parametrize("aggregate", [False, True])
def test_historical_read_retains_evidence_at_actual_access_time(tmp_path, aggregate):
    registry = _registry(tmp_path)
    registry.record_local(_card(), context=_context("source"))
    query = LessonQuery(as_of=AS_OF)
    if not aggregate:
        query = query.model_copy(update={"domain": "source", "tenant_hash": "tenant-a"})
    before_read = datetime.now(UTC)
    card = registry.query(query)[0]
    assert card.created_at == AS_OF
    assert before_read <= card.last_accessed_at <= datetime.now(UTC)
    fresh = _registry(tmp_path)
    entry = fresh.index_snapshot(context=_context("source")).entries[0]
    assert entry.last_seen == AS_OF
    assert before_read <= entry.last_accessed_at <= datetime.now(UTC)
    assert fresh.garbage_collect(ttl_days=90) == 0
    assert fresh.query(query)[0].confidence == 0.9
    # Retention did not change present-day evidence sufficiency.
    assert fresh.query(query.model_copy(update={"as_of": datetime.now(UTC)}))[0].confidence == 0.5
