"""Real CAS lesson admission uses evidence time, independently of retention."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from polisyos.core import artifacts
from polisyos.core.artifacts import PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
    load_lesson_card,
    persist_lesson_card,
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
    )


def _registry(tmp_path):
    return LessonRegistry(
        root=tmp_path / "lessons", store=artifacts.FileSystemCAS(tmp_path / "cas")
    )


def _context(domain, *, timestamp=AS_OF):
    return TransferContext(domain=domain, run_id="reader", timestamp=timestamp, tenant_hash=None)


@pytest.mark.parametrize("route", ["local", "transfer", "materialize", "aggregate"])
def test_future_cas_evidence_is_not_available_at_past_as_of(tmp_path, route):
    registry = _registry(tmp_path)
    future = _card(AS_OF + timedelta(days=1))
    source_ref = registry.record_local(future, context=_context("source"))
    future = load_lesson_card(registry._store, source_ref)
    snapshot = registry.snapshot_ref()
    # Reopen the actual index and CAS; retained metadata is not admission.
    registry = _registry(tmp_path)
    if route == "local":
        result = registry.query_with_transfer(
            LessonQuery(domain="source", tenant_hash=None),
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
    source_ref = registry.record_local(card, context=_context("source"))
    card = load_lesson_card(registry._store, source_ref)
    if route == "local":
        result = registry.query(LessonQuery(domain="source", tenant_hash=None, as_of=AS_OF))
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
    broad = LessonQuery(domain="source", tenant_hash=None, as_of=later)
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
            LessonQuery(domain="source", tenant_hash=None, as_of=AS_OF - timedelta(seconds=1))
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


def test_new_lesson_clocks_require_offsets_before_persistence(tmp_path):
    registry = _registry(tmp_path)
    with pytest.raises(ValueError, match="timezone"):
        registry.record_local(_card(AS_OF.replace(tzinfo=None)), context=_context("source"))
    with pytest.raises(ValueError, match="timezone"):
        persist_lesson_card(
            registry._store,
            _card().model_copy(update={"last_accessed_at": AS_OF.replace(tzinfo=None)}),
        )
    assert registry.snapshot_ref() is None
    assert list((tmp_path / "lessons").rglob("index.json")) == []
    assert list((tmp_path / "cas").rglob("*.blob")) == []

    offset = timezone(timedelta(hours=3))
    card = _card(AS_OF.astimezone(offset))
    ref = registry.record_local(card, context=_context("source"))
    loaded = load_lesson_card(_registry(tmp_path)._store, ref)
    assert loaded.created_at.isoformat() == AS_OF.isoformat()
    as_of = LessonQuery.model_validate({"as_of": "2020-01-01T03:00:00+03:00"}).as_of
    assert as_of == AS_OF
    assert as_of.tzinfo is UTC


def test_unknown_historical_lesson_clock_is_inspectable_without_aging(tmp_path):
    registry = _registry(tmp_path)
    context = _context("source")
    old = _card()
    registry.record_local(old, context=context)
    payload = old.model_dump(mode="json")
    naive = "2020-01-01T00:00:00"
    payload.update(schema_version="1.0", created_at=naive)
    legacy_ref = registry._store.put_json(
        payload,
        PutOptions(
            kind="scientist.search.lesson_card",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.search.LessonCard", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    index_path = registry._index_path_for_context(context)
    body = json.loads(index_path.read_text())
    body["entries"][0].update(
        artifact_ref=legacy_ref.model_dump(mode="json"),
        card_refs=[legacy_ref.model_dump(mode="json")],
        first_seen=naive,
        last_seen=naive,
    )
    index_path.write_text(json.dumps(body))
    original_index = index_path.read_bytes()
    original = registry._store.get_bytes(legacy_ref)

    fresh = _registry(tmp_path)
    assert load_lesson_card(fresh._store, legacy_ref).created_at.tzinfo is None
    assert fresh.query(LessonQuery(domain="source", tenant_hash=None, as_of=AS_OF)) == []
    assert (
        fresh.find_transfer_candidates(
            LessonQuery(as_of=AS_OF), target_context=_context("target")
        ).candidates
        == []
    )
    assert fresh.garbage_collect() == 0
    assert fresh._store.get_bytes(legacy_ref) == original
    assert index_path.read_bytes() == original_index
    assert fresh.index_snapshot(context=context).entries[0].last_seen.tzinfo is None

    selected = fresh.record_local(_card(), context=context)
    current = _registry(tmp_path)
    found = current.query(LessonQuery(domain="source", tenant_hash=None, as_of=AS_OF))
    assert [card.lesson_id for card in found] == [
        load_lesson_card(current._store, selected).lesson_id
    ]
    assert current._store.get_bytes(legacy_ref) == original


def test_newer_persisted_version_is_not_reinterpreted_as_older_evidence(tmp_path):
    registry = _registry(tmp_path)
    registry.record_local(_card(), context=_context("source"))
    later_card = _card(AS_OF + timedelta(days=1))
    registry.record_local(later_card, context=_context("source"))
    snapshot = registry.index_snapshot(context=_context("source"))
    assert snapshot.entries[0].occurrence_count == 2
    assert len(snapshot.entries[0].card_refs) == 2
    assert (
        _registry(tmp_path).query(LessonQuery(domain="source", tenant_hash=None, as_of=AS_OF)) == []
    )
    assert (
        _registry(tmp_path)
        .query(LessonQuery(domain="source", tenant_hash=None, as_of=later_card.created_at))[0]
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
        query = query.model_copy(update={"domain": "source", "tenant_hash": None})
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


def test_unscoped_snapshot_keeps_required_null_scope_on_fresh_cas_read(tmp_path):
    registry = _registry(tmp_path)
    registry.record_local(_card(), context=_context("source"))
    ref = registry.snapshot_ref()
    assert ref is not None
    fresh_store = artifacts.FileSystemCAS(tmp_path / "cas")
    snapshot = LessonRegistry.load_snapshot(fresh_store, ref)
    assert snapshot.source_scope is not None
    assert snapshot.source_scope.tenant_hash is None
    assert "tenant_hash" in snapshot.source_scope.model_fields_set
    assert snapshot.entries[0].last_seen == AS_OF


@pytest.mark.parametrize("route", ["transfer", "candidates", "materialize"])
def test_explicit_query_time_overrides_omitted_target_clock_without_mutation(tmp_path, route):
    registry = _registry(tmp_path)
    ref = registry.record_local(_card(), context=_context("source"))
    card = load_lesson_card(registry._store, ref)
    target = TransferContext(domain="target", run_id="reader", tenant_hash=None)
    query = LessonQuery(as_of=AS_OF)
    target_before = target.model_dump(mode="python")
    target_fields = set(target.model_fields_set)
    query_before = query.model_dump(mode="python")
    assert "timestamp" not in target_fields
    if route == "transfer":
        result = registry.query_with_transfer(query, target_context=target)
    elif route == "candidates":
        result = registry.find_transfer_candidates(query, target_context=target).candidates
    else:
        result = registry.materialize_transfer(card, target_context=target, query=query)
    assert result
    assert target.model_dump(mode="python") == target_before
    assert target.model_fields_set == target_fields
    assert query.model_dump(mode="python") == query_before


@pytest.mark.parametrize("route", ["transfer", "candidates", "materialize"])
def test_omitted_target_clock_uses_actual_query_time_for_fresh_evidence(tmp_path, route):
    registry = _registry(tmp_path)
    target = TransferContext(domain="target", run_id="reader", tenant_hash=None)
    assert "timestamp" not in target.model_fields_set
    # Evidence occurs after this context's constructor default but before the
    # actual query. Only an explicitly declared target timestamp freezes time.
    card = _card(target.timestamp + timedelta(microseconds=1))
    source = TransferContext(domain="source", run_id="writer", tenant_hash=None)
    ref = registry.record_local(card, context=source)
    card = load_lesson_card(registry._store, ref)
    assert target.timestamp < card.created_at <= datetime.now(UTC)
    query = LessonQuery()
    if route == "transfer":
        result = registry.query_with_transfer(query, target_context=target)
    elif route == "candidates":
        result = registry.find_transfer_candidates(query, target_context=target).candidates
    else:
        result = registry.materialize_transfer(card, target_context=target, query=query)
    assert result
