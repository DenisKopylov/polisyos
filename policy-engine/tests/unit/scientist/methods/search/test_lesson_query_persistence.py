"""CAS and consumer witnesses for transfer-query scope and evidence freshness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
    load_lesson_card,
)
from polisyos.scientist.methods.search.objective import CompositeObjective
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferPolicy,
    resolve_transfer_context,
)


def _registry(path: Path) -> tuple[FileSystemCAS, LessonRegistry]:
    store = FileSystemCAS(path / "cas")
    return store, LessonRegistry(path / "lessons", store=store)


def _card(context: TransferContext, *, age_days: int = 0, confidence: float = 0.9) -> LessonCard:
    return LessonCard(
        lesson_id="lesson-source",
        kind=LessonKind.FAILURE,
        summary="Keep the source evidence boundary.",
        failure_type="source-boundary",
        stage_name="stage-source",
        fidelity_level=1,
        candidate_hash="candidate-source",
        source_run_id="run-source",
        task_family=context.task_family,
        domain=context.domain,
        origin_tenant_hash=context.tenant_hash,
        created_at=datetime.now(UTC) - timedelta(days=age_days),
        confidence=confidence,
        trace_refs=["fixture/source/evidence-v1"],
    )


def _files(path: Path) -> dict[str, bytes]:
    """Enumerate every regular file under the isolated fixture CAS denominator."""
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


class _CapturingGenerator:
    def __init__(self) -> None:
        self.contexts: list[dict[str, Any]] = []

    def generate(self, history: Any, current_best: Any, context: dict[str, Any]) -> dict[str, Any]:
        del history, current_best
        self.contexts.append(context)
        return {"semantic": {"interventions": []}}


def test_nested_context_and_explicit_override_reach_real_lesson_consumer(tmp_path: Path) -> None:
    _, registry = _registry(tmp_path)
    base = TransferContext(task_family="discovery", domain="education", run_id="run-source")
    registry.record_local(_card(base), context=base)
    for payload in (base, base.model_dump(mode="json")):
        resolved = resolve_transfer_context(context={"transfer_context": payload})
        assert (resolved.task_family, resolved.domain) == ("discovery", "education")
        generator = _CapturingGenerator()
        controller = SearchController(
            SearchConfig(stopping=MaxIterations(1), objective=CompositeObjective()),
            generator,
            lambda candidate, context: (0.0, True),
            lambda candidate, context: {"simulation_results": {}},
        )
        controller.run(initial_context={"transfer_context": payload, "lesson_registry": registry})
        hints = generator.contexts[0]["lesson_hints"]
        assert len(hints) == 1
        assert (hints[0]["task_family"], hints[0]["domain"]) == ("discovery", "education")
    explicit = resolve_transfer_context(
        context={"transfer_context": base}, task_family="policy", domain="health"
    )
    assert (explicit.task_family, explicit.domain) == ("policy", "health")
    unknown = resolve_transfer_context(run_id="run-unknown")
    assert unknown.domain == "isolated::run-unknown"


def test_transfer_query_filters_before_materialization_and_after_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="source", run_id="run-source", tenant_hash="fixture-tenant"
    )
    target = TransferContext(
        task_family="policy", domain="target", run_id="run-target", tenant_hash="fixture-tenant"
    )
    registry.record_local(_card(source), context=source)
    calls = []
    original = registry.materialize_transfer

    def observe(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(registry, "materialize_transfer", observe)
    for updates in (
        {"trust_levels": [LessonTrustLevel.LOCAL]},
        {"source_run_id": "run-other"},
        {"min_confidence": 0.95},
        {"stage_name": "unrelated-stage"},
    ):
        query = LessonQuery(**updates)
        assert registry.query_with_transfer(query, target_context=target) == []
        assert calls == [], "Rejected projected cards must not enter materialization"
        assert registry.index_snapshot(context=target).entries == []
    permit = LessonQuery(
        source_run_id="run-source", trust_levels=[LessonTrustLevel.TRANSFERRED], min_confidence=0.8
    )
    result = registry.query_with_transfer(permit, target_context=target)
    assert len(result) == len(calls) == 1
    assert result[0].trust_level is LessonTrustLevel.TRANSFERRED
    _, reopened = _registry(tmp_path)
    local = reopened.query(
        permit.model_copy(update={"domain": "target", "tenant_hash": "fixture-tenant"})
    )
    assert len(local) == 1
    assert local[0].source_run_id == "run-source"
    assert (
        reopened.query(
            permit.model_copy(
                update={"domain": "target", "tenant_hash": "fixture-tenant", "min_confidence": 0.95}
            )
        )
        == []
    )


def test_old_reads_survive_restart_without_confidence_rejuvenation_or_full_snapshot_writes(
    tmp_path: Path,
) -> None:
    store, registry = _registry(tmp_path)
    context = TransferContext(task_family="policy", domain="source", run_id="run-source")
    original = _card(context, age_days=100)
    ref = registry.record_local(original, context=context)
    index_path = registry._index_path_for_context(context)
    before_index = index_path.read_bytes()
    before_cas = _files(tmp_path / "cas")
    broad = LessonQuery(task_family="policy", domain="source")
    strict = broad.model_copy(
        update={"trust_levels": [LessonTrustLevel.LOCAL], "min_confidence": 0.8}
    )
    for _ in range(3):
        _, registry = _registry(tmp_path)
        result = registry.query(broad)
        assert len(result) == 1
        assert (result[0].confidence, result[0].trust_level) == (
            0.5,
            LessonTrustLevel.LOW_CONFIDENCE,
        )
        assert registry.query(strict) == []
    assert load_lesson_card(store, ref).created_at == original.created_at
    assert index_path.read_bytes() == before_index, (
        "Access accounting must not rewrite evidence index"
    )
    assert _files(tmp_path / "cas") == before_cas, "Reads must not publish full evidence snapshots"
    assert registry.index_snapshot(context=context).entries[0].last_accessed_at is not None


def test_stale_transfer_preserves_evidence_age_before_and_after_materialization(
    tmp_path: Path,
) -> None:
    _, registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="source", run_id="run-source", tenant_hash="fixture-tenant"
    )
    target = TransferContext(
        task_family="policy", domain="target", run_id="run-target", tenant_hash="fixture-tenant"
    )
    registry.record_local(_card(source, age_days=100), context=source)
    strict = LessonQuery(min_confidence=0.8, source_run_id="run-source")
    assert registry.query_with_transfer(strict, target_context=target) == []
    assert registry.index_snapshot(context=target).entries == []
    broad = strict.model_copy(update={"min_confidence": 0.0})
    result = registry.query_with_transfer(broad, target_context=target)
    assert len(result) == 1
    assert (result[0].confidence, result[0].trust_level) == (0.5, LessonTrustLevel.LOW_CONFIDENCE)
    _, reopened = _registry(tmp_path)
    assert (
        reopened.query(
            strict.model_copy(update={"domain": "target", "tenant_hash": "fixture-tenant"})
        )
        == []
    )
    repeated = reopened.query(
        broad.model_copy(update={"domain": "target", "tenant_hash": "fixture-tenant"})
    )
    assert len(repeated) == 1 and repeated[0].confidence == 0.5


def test_new_producer_evidence_version_has_its_own_refs_and_clock(tmp_path: Path) -> None:
    store, registry = _registry(tmp_path)
    context = TransferContext(task_family="policy", domain="source", run_id="run-source")
    old = _card(context, age_days=100)
    old_ref = registry.record_local(old, context=context)
    new = old.model_copy(
        update={
            "lesson_id": "evidence-v2",
            "created_at": datetime.now(UTC),
            "trace_refs": ["fixture/source/evidence-v2"],
            "candidate_hash": "candidate-v2",
        }
    )
    new_ref = registry.record_local(new, context=context)
    assert new_ref != old_ref
    assert load_lesson_card(store, old_ref).trace_refs == ["fixture/source/evidence-v1"]
    assert load_lesson_card(store, new_ref).trace_refs == ["fixture/source/evidence-v2"]
    _, reopened = _registry(tmp_path)
    cards = reopened.query(
        LessonQuery(domain="source", min_confidence=0.8, trust_levels=[LessonTrustLevel.LOCAL])
    )
    assert len(cards) == 1 and cards[0].created_at == new.created_at


def test_out_of_order_old_producer_replay_preserves_newest_evidence_across_transfer(
    tmp_path: Path,
) -> None:
    store, registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="source", run_id="run-source", tenant_hash="fixture-tenant"
    )
    target = TransferContext(
        task_family="policy", domain="target", run_id="run-target", tenant_hash="fixture-tenant"
    )
    old = _card(source, age_days=100)
    old_ref = registry.record_local(old, context=source)
    new = old.model_copy(
        update={
            "lesson_id": "evidence-v2",
            "created_at": datetime.now(UTC),
            "trace_refs": ["fixture/source/evidence-v2"],
            "candidate_hash": "candidate-v2",
        }
    )
    new_ref = registry.record_local(new, context=source)
    registry.record_local(old, context=source)
    for _ in range(2):
        _, registry = _registry(tmp_path)
        entry = registry.index_snapshot(context=source).entries[0]
        assert entry.artifact_ref == new_ref
        assert old_ref in entry.card_refs and new_ref in entry.card_refs
        assert entry.occurrence_count == 3 and entry.last_seen == new.created_at
        local = registry.query(
            LessonQuery(
                domain="source",
                tenant_hash="fixture-tenant",
                min_confidence=0.8,
                candidate_hash=new.candidate_hash,
            )
        )
        assert len(local) == 1 and local[0].trace_refs == new.trace_refs
        result = registry.query_with_transfer(
            LessonQuery(source_run_id="run-source", min_confidence=0.8, limit=1),
            target_context=target,
        )
        assert len(result) == 1
        assert result[0].created_at == new.created_at and result[0].trace_refs == new.trace_refs
        assert result[0].trust_level is LessonTrustLevel.TRANSFERRED
    assert load_lesson_card(store, old_ref).created_at == old.created_at


@pytest.mark.parametrize("ttl_days,age_days,confidence", [(5, 10, 0.5), (180, 100, 0.9)])
def test_explicit_active_policy_applies_to_local_and_transferred_evidence(
    tmp_path: Path, ttl_days: int, age_days: int, confidence: float
) -> None:
    _, registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="source", run_id="run-source", tenant_hash="fixture-tenant"
    )
    target = TransferContext(
        task_family="policy", domain="target", run_id="run-target", tenant_hash="fixture-tenant"
    )
    registry.record_local(_card(source, age_days=age_days), context=source)
    policy = TransferPolicy(ttl_days=ttl_days)
    query = LessonQuery(source_run_id="run-source", limit=1)
    local = registry.query_with_transfer(query, target_context=source, policy=policy)
    assert len(local) == 1 and local[0].confidence == confidence
    transferred = registry.query_with_transfer(query, target_context=target, policy=policy)
    # Past twice the explicit TTL the transfer policy rejects the source entirely.
    if age_days > ttl_days * 2:
        assert transferred == []
        return
    assert len(transferred) == 1 and transferred[0].confidence == confidence
    _, reopened = _registry(tmp_path)
    restored = reopened.query_with_transfer(query, target_context=target, policy=policy)
    assert len(restored) == 1 and restored[0].confidence == confidence


def test_access_writes_are_throttled_and_corrupt_retention_hint_cannot_change_evidence(
    tmp_path: Path,
) -> None:
    _, registry = _registry(tmp_path)
    context = TransferContext(task_family="policy", domain="source", run_id="run-source")
    card = _card(context, age_days=100)
    registry.record_local(card, context=context)
    query = LessonQuery(domain="source")
    registry.query(query)
    access = registry._access_path(registry._index_path_for_context(context), card.lesson_id)
    before = (access.read_bytes(), access.stat().st_mtime_ns)
    _, reopened = _registry(tmp_path)
    for _ in range(3):
        assert reopened.query(query)[0].confidence == 0.5
    assert (access.read_bytes(), access.stat().st_mtime_ns) == before
    access.write_text("not-a-retention-timestamp", encoding="utf-8")
    _, reopened = _registry(tmp_path)
    assert reopened.query(query)[0].confidence == 0.5


def test_removing_evidence_clock_keeps_markers_but_oracle_detects_rejuvenation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, registry = _registry(tmp_path)
    context = TransferContext(task_family="policy", domain="source", run_id="run-source")
    card = _card(context, age_days=100)
    ref = registry.record_local(card, context=context)
    assert registry.query(LessonQuery(domain="source"))[0].confidence == 0.5
    _, reopened = _registry(tmp_path)
    monkeypatch.setattr(
        reopened,
        "_evidence_anchor",
        lambda entry, lesson: entry.last_accessed_at or entry.last_seen,
    )
    strict = LessonQuery(domain="source", trust_levels=[LessonTrustLevel.LOCAL], min_confidence=0.8)
    assert load_lesson_card(store, ref).created_at == card.created_at
    with pytest.raises(AssertionError):
        assert reopened.query(strict) == []


def test_post_projection_filter_rejects_before_cas_and_removal_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="source", run_id="run-source", tenant_hash="fixture-tenant"
    )
    target = TransferContext(
        task_family="policy", domain="target", run_id="run-target", tenant_hash="fixture-tenant"
    )
    card = _card(source)
    registry.record_local(card, context=source)
    before = _files(tmp_path / "cas")
    local_only = LessonQuery(
        source_run_id="run-source", trust_levels=[LessonTrustLevel.LOCAL], min_confidence=0.8
    )
    assert registry.materialize_transfer(card, target_context=target, query=local_only) is None
    assert _files(tmp_path / "cas") == before
    monkeypatch.setattr(registry, "_matches_query", lambda *args, **kwargs: True)
    with pytest.raises(AssertionError):
        assert registry.materialize_transfer(card, target_context=target, query=local_only) is None
