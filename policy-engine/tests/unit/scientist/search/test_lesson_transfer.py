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
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferPolicy,
    resolve_transfer_context,
)


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


def test_resolve_transfer_context_preserves_typed_base_until_explicit_override() -> None:
    base = TransferContext(
        task_family="discovery",
        domain="education",
        run_id="run-base",
        tenant_hash="tenant-a",
        cross_tenant_opt_in=True,
        timestamp=datetime(2026, 9, 1, tzinfo=UTC),
    )

    for payload in (base, base.model_dump(mode="json")):
        resolved = resolve_transfer_context(context={"transfer_context": payload})

        assert (resolved.task_family, resolved.domain, resolved.run_id) == (
            "discovery",
            "education",
            "run-base",
        )
        assert resolved.cross_tenant_opt_in is True

    overridden = resolve_transfer_context(
        context={"transfer_context": base},
        task_family="policy",
        domain="health",
    )

    assert (overridden.task_family, overridden.domain, overridden.run_id) == (
        "policy",
        "health",
        "run-base",
    )


def test_query_with_transfer_reapplies_source_trust_and_confidence_filters(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    weak = _card().model_copy(update={"confidence": 0.2, "tags": ["weak"]})
    strong = _card().model_copy(update={"confidence": 0.9, "tags": ["strong"]})
    registry.record_local(weak, context=source)
    registry.record_local(strong, context=source)

    assert (
        registry.query(
            LessonQuery(
                task_family="policy",
                domain="fiscal",
                tenant_hash="tenant-a",
                source_run_id="run-source",
                tags=["weak"],
                trust_levels=[LessonTrustLevel.LOCAL],
                min_confidence=0.8,
                limit=3,
            )
        )
        == []
    )
    local_strong = registry.query(
        LessonQuery(
            task_family="policy",
            domain="fiscal",
            tenant_hash="tenant-a",
            source_run_id="run-source",
            tags=["strong"],
            trust_levels=[LessonTrustLevel.LOCAL],
            min_confidence=0.8,
            limit=3,
        )
    )
    assert len(local_strong) == 1
    assert (
        registry.query(
            LessonQuery(
                task_family="policy",
                domain="fiscal",
                tenant_hash="tenant-a",
                source_run_id="run-other",
                tags=["strong"],
                min_confidence=0.8,
                limit=3,
            )
        )
        == []
    )

    transfer_cases = (
        (
            LessonQuery(
                task_family="policy",
                source_run_id="run-source",
                tags=["weak"],
                trust_levels=[LessonTrustLevel.TRANSFERRED],
                min_confidence=0.8,
                limit=3,
            ),
            "labor-weak",
        ),
        (
            LessonQuery(
                task_family="policy",
                source_run_id="run-source",
                tags=["strong"],
                trust_levels=[LessonTrustLevel.LOCAL],
                min_confidence=0.8,
                limit=3,
            ),
            "labor-trust",
        ),
        (
            LessonQuery(
                task_family="policy",
                source_run_id="run-other",
                tags=["strong"],
                min_confidence=0.8,
                limit=3,
            ),
            "labor-source",
        ),
    )

    for query, domain in transfer_cases:
        assert (
            registry.query_with_transfer(
                query,
                target_context=TransferContext(
                    task_family="policy",
                    domain=domain,
                    run_id="loop-target",
                    tenant_hash="tenant-a",
                ),
            )
            == []
        )


def test_query_with_transfer_materializes_cross_domain_same_tenant(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    registry.record_local(_card(), context=source)
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
    )
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
