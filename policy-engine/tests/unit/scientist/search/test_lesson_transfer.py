from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
)
from polisyos.scientist.methods.search.transfer_context import TransferContext, TransferPolicy


def _registry(tmp_path) -> LessonRegistry:
    store = FileSystemCAS(tmp_path / ".polisyos")
    return LessonRegistry(
        root=tmp_path / "registry" / "lessons",
        store=store,
        transfer_policy=TransferPolicy(ttl_days=90),
    )


def _card(*, created_at: datetime | None = None) -> LessonCard:
    return LessonCard(
        kind=LessonKind.FAILURE,
        summary="Tax reform pattern underperforms for GDP objective.",
        failure_type="transport_failure",
        stage_name="funnel_L1_heuristic",
        fidelity_level=1,
        candidate_hash="pattern",
        source_run_id="run-source",
        created_at=created_at or datetime.now(UTC),
        tags=["tax_reform", "gdp_growth"],
    )


def test_query_with_transfer_materializes_cross_domain_same_tenant(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
    )
    registry.record_local(_card(), context=source)

    results = registry.query_with_transfer(
        LessonQuery(
            stage_name="funnel_L1_heuristic",
            task_family="policy",
            tags=["tax_reform", "gdp_growth"],
            limit=3,
        ),
        target_context=target,
    )

    assert results
    assert results[0].trust_level == LessonTrustLevel.TRANSFERRED
    assert 0.0 < results[0].provenance_weight < 1.0

    local_results = registry.query(
        LessonQuery(
            stage_name="funnel_L1_heuristic",
            task_family="policy",
            domain="labor",
            tenant_hash="tenant-a",
            tags=["tax_reform"],
            limit=3,
        )
    )
    assert local_results
    assert local_results[0].transfer_chain


def test_same_domain_same_tenant_reuse_stays_local(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    registry.record_local(_card(), context=source)

    results = registry.query(
        LessonQuery(
            stage_name="funnel_L1_heuristic",
            task_family="policy",
            domain="fiscal",
            tenant_hash="tenant-a",
            tags=["tax_reform"],
            limit=3,
        )
    )

    assert results
    assert results[0].trust_level == LessonTrustLevel.LOCAL
    assert results[0].provenance_weight == 1.0


def test_cross_tenant_transfer_denied_by_default(tmp_path) -> None:
    registry = _registry(tmp_path)
    registry.record_local(
        _card(),
        context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="loop-source",
            tenant_hash="tenant-a",
        ),
    )

    results = registry.query_with_transfer(
        LessonQuery(
            stage_name="funnel_L1_heuristic",
            task_family="policy",
            tags=["tax_reform"],
            limit=3,
        ),
        target_context=TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-target",
            tenant_hash="tenant-b",
        ),
    )

    assert results == []


def test_ttl_demotes_old_lessons_before_archive(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    registry.record_local(
        _card(created_at=datetime.now(UTC) - timedelta(days=100)),
        context=source,
    )

    results = registry.query(
        LessonQuery(
            stage_name="funnel_L1_heuristic",
            task_family="policy",
            domain="fiscal",
            tenant_hash="tenant-a",
            tags=["tax_reform"],
            limit=3,
        )
    )

    assert results
    assert results[0].trust_level == LessonTrustLevel.LOW_CONFIDENCE


def test_invalidation_beats_transfer_materialization(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    lesson = _card()
    registry.record_local(lesson, context=source)
    assert registry.invalidate(lesson.lesson_id, "contradicted_by_new_run") is True

    results = registry.query_with_transfer(
        LessonQuery(
            stage_name="funnel_L1_heuristic",
            task_family="policy",
            tags=["tax_reform"],
            limit=3,
        ),
        target_context=TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-target",
            tenant_hash="tenant-a",
        ),
    )

    assert results == []
