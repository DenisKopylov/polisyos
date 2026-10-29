from __future__ import annotations

import json
from collections import UserDict
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTransferBundle,
    LessonTrustLevel,
    load_lesson_card,
    persist_lesson_card,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferPolicy,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferSourceScope,
    TransferTenantScopeStatus,
    anonymize_tenant_id,
    build_transfer_hop,
    resolve_transfer_context,
    tenant_partition,
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


def test_lesson_writer_uses_context_not_card_tenant_self_label(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="fiscal", run_id="writer-run", tenant_hash="producer-tenant"
    )
    self_labeled = _card().model_copy(update={"origin_tenant_hash": "forged-tenant"})
    ref = registry.record_local(self_labeled, context=source)
    stored = load_lesson_card(registry._store, ref)
    assert stored.origin_tenant_hash == "producer-tenant"
    snapshot = registry.index_snapshot(context=source)
    assert snapshot.source_scope is not None
    assert snapshot.source_scope.tenant_hash == "producer-tenant"
    assert all(entry.origin_tenant_hash == "producer-tenant" for entry in snapshot.entries)
    snapshot_ref = registry.snapshot_ref()
    assert snapshot_ref is not None
    reloaded = LessonRegistry.load_snapshot(registry._store, snapshot_ref)
    assert reloaded.source_scope == snapshot.source_scope
    assert all(entry.origin_tenant_hash == "producer-tenant" for entry in reloaded.entries)


def test_versioned_lesson_scope_distinguishes_none_global_and_foreign(tmp_path) -> None:
    registry = _registry(tmp_path)
    sources = [
        TransferContext(task_family="policy", domain="fiscal", run_id=f"run-{i}", tenant_hash=value)
        for i, value in enumerate((None, "global", "tenant-b", "x" * 300))
    ]
    for source in sources:
        registry.record_local(_card(), context=source)
    registry.record_local(
        _card(),
        context=TransferContext(
            task_family="policy", domain="energy", run_id="same-tenant-energy", tenant_hash=None
        ),
    )
    fresh = _registry(tmp_path)
    for index, source in enumerate(sources):
        isolated = _registry(tmp_path / f"isolated-{index}")
        isolated.record_local(_card(), context=source)
        result = isolated.find_transfer_candidates(
            LessonQuery(task_family="policy", limit=10),
            target_context=TransferContext(
                task_family="policy",
                domain="labor",
                run_id="target",
                tenant_hash=source.tenant_hash,
            ),
        )
        assert isinstance(result, LessonTransferBundle)
        assert not result.scope_refusals
        assert result.candidates
        assert {card.origin_tenant_hash for card in result.candidates} == {source.tenant_hash}
    foreign = fresh.find_transfer_candidates(
        LessonQuery(task_family="policy", limit=10),
        target_context=TransferContext(
            task_family="policy", domain="labor", run_id="target", tenant_hash=None
        ),
    )
    assert foreign.candidates
    assert {card.origin_tenant_hash for card in foreign.candidates} == {None}
    assert any(
        item.reason is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
        for item in foreign.scope_refusals
    )
    combined = fresh.query_with_transfer(
        LessonQuery(task_family="policy", limit=10),
        target_context=TransferContext(
            task_family="policy", domain="labor", run_id="target", tenant_hash=None
        ),
    )
    assert combined
    assert {card.origin_tenant_hash for card in combined} == {None}


def test_lesson_reader_refuses_path_body_mismatch_and_ambiguous_legacy(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="fiscal", run_id="source", tenant_hash="global"
    )
    registry.record_local(_card(), context=source)
    path = registry._index_path_for_context(source)
    payload = json.loads(path.read_text())
    payload["source_scope"]["tenant_kind"] = "unscoped"
    payload["source_scope"]["tenant_hash"] = None
    payload["source_scope"]["tenant_scope_status"] = "declared_unscoped"
    path.write_text(json.dumps(payload))
    fresh = _registry(tmp_path)
    result = fresh.find_transfer_candidates(
        LessonQuery(task_family="policy", limit=10),
        target_context=TransferContext(
            task_family="policy", domain="labor", run_id="target", tenant_hash="global"
        ),
    )
    assert result.candidates == []
    assert result.scope_refusals[0].reason is TransferScopeRefusalReason.PATH_BODY_MISMATCH

    legacy = _registry(tmp_path / "legacy")
    legacy_path = legacy._root / "global" / "policy" / "fiscal" / "index.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        json.dumps(
            {"schema_version": "1.0", "task_family": "policy", "domain": "fiscal", "entries": []}
        )
    )
    malformed_path = legacy._root / "v3" / "not-a-digest" / "index.json"
    malformed_path.parent.mkdir(parents=True)
    malformed_path.write_text("{}")
    result = legacy.find_transfer_candidates(
        LessonQuery(task_family="policy", limit=10),
        target_context=TransferContext(
            task_family="policy", domain="labor", run_id="target", tenant_hash=None
        ),
    )
    assert result.candidates == []
    assert any(
        item.reason is TransferScopeRefusalReason.LEGACY_PATH_UNBOUND
        for item in result.scope_refusals
    )
    assert any(
        item.reason is TransferScopeRefusalReason.MALFORMED_PATH for item in result.scope_refusals
    )


def test_resolve_transfer_context_preserves_explicit_none_and_rejects_empty_hash() -> None:
    base = TransferContext(
        task_family="policy", domain="fiscal", run_id="base", tenant_hash="tenant-a"
    )
    inherited = resolve_transfer_context(context={"transfer_context": base})
    assert inherited.tenant_hash == "tenant-a"
    with pytest.raises(TransferScopeRefusedError) as explicit_none_conflict:
        resolve_transfer_context(
            context={"transfer_context": base}, tenant_hash=None, tenant_hash_is_explicit=True
        )
    assert (
        explicit_none_conflict.value.refusals[0].reason
        is TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )
    with pytest.raises(TransferScopeRefusedError) as resolver_refusal:
        resolve_transfer_context(tenant_hash="", tenant_hash_is_explicit=True)
    assert (
        resolver_refusal.value.refusals[0].reason
        is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )
    with pytest.raises(ValueError, match="tenant hash must be a non-empty identity"):
        TransferContext(tenant_hash="")
    with pytest.raises(ValueError, match="tenant hash must be a non-empty identity"):
        tenant_partition("  ")
    assert tenant_partition(None) == "n"
    assert tenant_partition("global") != tenant_partition(None)
    with pytest.raises(ValueError, match="tenant source scope requires a non-empty identity"):
        TransferSourceScope(
            task_family="policy",
            domain="fiscal",
            tenant_kind="tenant",
            tenant_hash="",
            tenant_scope_status=TransferTenantScopeStatus.UNKNOWN,
        )


def test_transfer_context_reconciles_live_access_scope_and_unknown_state() -> None:
    access = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id=None,
        spiffe_id="spiffe://test/search",
    )
    token = set_current_access_scope(access)
    try:
        expected = anonymize_tenant_id("tenant-a")
        bound = resolve_transfer_context(transfer_context=TransferContext(tenant_hash=expected))
        assert bound.tenant_hash == expected
        assert bound.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        with pytest.raises(TransferScopeRefusedError) as mismatch:
            resolve_transfer_context(
                transfer_context=TransferContext(tenant_hash=anonymize_tenant_id("tenant-b"))
            )
        assert (
            mismatch.value.refusals[0].reason
            is TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH
        )
        with pytest.raises(TransferScopeRefusedError):
            resolve_transfer_context(
                transfer_context=TransferContext(
                    tenant_scope_status=TransferTenantScopeStatus.DECLARED_UNSCOPED
                )
            )
    finally:
        reset_current_access_scope(token)

    unknown = resolve_transfer_context(run_id="no-auth")
    declared = resolve_transfer_context(
        transfer_context=TransferContext(
            tenant_scope_status=TransferTenantScopeStatus.DECLARED_UNSCOPED
        )
    )
    assert unknown.tenant_hash is None
    assert unknown.tenant_scope_status is TransferTenantScopeStatus.UNKNOWN
    assert declared.tenant_hash is None
    assert declared.tenant_scope_status is TransferTenantScopeStatus.DECLARED_UNSCOPED
    hop = build_transfer_hop(
        unknown,
        TransferContext(
            task_family="policy",
            domain="labor",
            run_id="target",
            tenant_scope_status=TransferTenantScopeStatus.UNKNOWN,
        ),
        provenance_weight=0.65,
    )
    assert hop.source_tenant_scope_status is TransferTenantScopeStatus.UNKNOWN
    assert hop.target_tenant_scope_status is TransferTenantScopeStatus.UNKNOWN
    assert hop.provenance_weight == 0.65
    with pytest.raises(TransferScopeRefusedError) as malformed_status:
        resolve_transfer_context(context={"tenant_scope_status": "future_status"})
    assert (
        malformed_status.value.refusals[0].reason
        is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )
    with pytest.raises(TransferScopeRefusedError) as malformed_context:
        resolve_transfer_context(
            context={
                "transfer_context": {
                    "tenant_scope_status": "declared_unscoped",
                    "tenant_hash": "unexpected",
                }
            }
        )
    assert (
        malformed_context.value.refusals[0].reason
        is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )


def test_lesson_record_and_fresh_reader_reconcile_access_scope(tmp_path) -> None:
    registry = _registry(tmp_path)
    expected = anonymize_tenant_id("tenant-a")
    access = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id=None,
        spiffe_id="spiffe://test/search",
    )
    token = set_current_access_scope(access)
    try:
        source = resolve_transfer_context(
            transfer_context=TransferContext(
                task_family="policy",
                domain="fiscal",
                run_id="authenticated-source",
                tenant_hash=expected,
            )
        )
        registry.record_local(_card(), context=source)
        snapshot = registry.index_snapshot(context=source)
        assert snapshot.source_scope is not None
        assert snapshot.source_scope.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        assert (
            snapshot.entries[0].origin_tenant_scope_status
            is TransferTenantScopeStatus.AUTHENTICATED
        )
        bundle = registry.find_transfer_candidates(
            LessonQuery(task_family="policy", limit=10),
            target_context=TransferContext(
                task_family="policy",
                domain="labor",
                run_id="authenticated-reader",
                tenant_hash=expected,
            ),
        )
        assert bundle.candidates
        assert all(
            card.origin_tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
            for card in bundle.candidates
        )
        materialized = registry.query_with_transfer(
            LessonQuery(task_family="policy", limit=10),
            target_context=TransferContext(
                task_family="policy",
                domain="labor",
                run_id="authenticated-materializer",
                tenant_hash=expected,
            ),
        )
        assert materialized
        assert all(
            card.origin_tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
            for card in materialized
        )
    finally:
        reset_current_access_scope(token)

    wrong_access = AccessScope.for_service(
        tenant_id="tenant-b",
        cell_id=None,
        spiffe_id="spiffe://test/search",
    )
    wrong_token = set_current_access_scope(wrong_access)
    try:
        with pytest.raises(TransferScopeRefusedError) as mismatch:
            registry.find_transfer_candidates(
                LessonQuery(task_family="policy", limit=10),
                target_context=TransferContext(
                    task_family="policy",
                    domain="labor",
                    run_id="foreign-reader",
                    tenant_hash=expected,
                ),
            )
        assert (
            mismatch.value.refusals[0].reason
            is TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH
        )
    finally:
        reset_current_access_scope(wrong_token)


def test_authenticated_cross_tenant_transfer_keeps_both_source_scopes(tmp_path) -> None:
    registry = LessonRegistry(
        root=tmp_path / "registry" / "lessons",
        store=FileSystemCAS(tmp_path / ".polisyos"),
        transfer_policy=TransferPolicy(allow_cross_tenant=True, ttl_days=90),
    )
    source_hash = anonymize_tenant_id("tenant-a")
    source_token = set_current_access_scope(
        AccessScope.for_service(
            tenant_id="tenant-a",
            cell_id=None,
            spiffe_id="spiffe://test/search",
        )
    )
    try:
        source = resolve_transfer_context(
            transfer_context=TransferContext(
                task_family="policy",
                domain="fiscal",
                run_id="authenticated-source",
                tenant_hash=source_hash,
            )
        )
        registry.record_local(_card(), context=source)
    finally:
        reset_current_access_scope(source_token)

    target_hash = anonymize_tenant_id("tenant-b")
    target_token = set_current_access_scope(
        AccessScope.for_service(
            tenant_id="tenant-b",
            cell_id=None,
            spiffe_id="spiffe://test/search",
        )
    )
    try:
        target = resolve_transfer_context(
            transfer_context=TransferContext(
                task_family="policy",
                domain="labor",
                run_id="authenticated-target",
                tenant_hash=target_hash,
                cross_tenant_opt_in=True,
            )
        )
        denied = registry.find_transfer_candidates(
            LessonQuery(task_family="policy", limit=10),
            target_context=target.model_copy(update={"cross_tenant_opt_in": False}),
        )
        assert denied.candidates == []
        assert any(
            refusal.reason is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
            for refusal in denied.scope_refusals
        )
        bundle = registry.find_transfer_candidates(
            LessonQuery(task_family="policy", limit=10), target_context=target
        )
        assert bundle.candidates
        source_card = bundle.candidates[0]
        assert source_card.origin_tenant_hash == source_hash
        assert source_card.origin_tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        materialized = registry.materialize_transfer(source_card, target_context=target)
        assert materialized is not None
        assert materialized.origin_tenant_hash == target_hash
        assert materialized.origin_tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        assert materialized.provenance_weight == 0.35
        hop = materialized.transfer_chain[-1]
        assert hop.source_tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        assert hop.target_tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
        fresh = _registry(tmp_path)
        target_snapshot = fresh.index_snapshot(context=target)
        assert target_snapshot.source_scope is not None
        assert target_snapshot.source_scope.tenant_hash == target_hash
        assert all(
            entry.origin_tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED
            for entry in target_snapshot.entries
        )
    finally:
        reset_current_access_scope(target_token)


def test_unknown_lesson_candidate_keeps_unknown_status(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = resolve_transfer_context(
        transfer_context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="unknown-source",
            tenant_hash="caller-claim",
        )
    )
    registry.record_local(_card(), context=source)
    bundle = registry.find_transfer_candidates(
        LessonQuery(task_family="policy", limit=10),
        target_context=TransferContext(
            task_family="policy",
            domain="labor",
            run_id="unknown-reader",
            tenant_hash="caller-claim",
        ),
    )
    assert bundle.candidates
    assert bundle.target_tenant_scope_status is TransferTenantScopeStatus.UNKNOWN
    assert all(
        card.origin_tenant_scope_status is TransferTenantScopeStatus.UNKNOWN
        for card in bundle.candidates
    )


def test_local_lesson_query_refuses_cas_scope_drift(tmp_path) -> None:
    registry = _registry(tmp_path)
    context = resolve_transfer_context(
        transfer_context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="unknown-source",
            tenant_hash="caller-claim",
        )
    )
    registry.record_local(_card(), context=context)
    snapshot = registry.index_snapshot(context=context)
    entry = snapshot.entries[0]
    stored = load_lesson_card(registry._store, entry.artifact_ref)
    forged = stored.model_copy(
        update={"origin_tenant_scope_status": TransferTenantScopeStatus.AUTHENTICATED}
    )
    entry.artifact_ref = persist_lesson_card(registry._store, forged)
    registry._persist_index(snapshot, context=context)

    with pytest.raises(TransferScopeRefusedError) as mismatch:
        registry.query(
            LessonQuery(
                task_family="policy",
                domain="fiscal",
                tenant_hash="caller-claim",
                limit=10,
            )
        )
    assert mismatch.value.refusals[0].reason is TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH


def test_local_aggregate_distinguishes_unknown_from_declared_unscoped(tmp_path) -> None:
    registry = _registry(tmp_path)
    unknown = TransferContext(task_family="policy", domain="fiscal", run_id="unknown")
    declared = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="declared",
        tenant_scope_status=TransferTenantScopeStatus.DECLARED_UNSCOPED,
    )
    registry.record_local(_card(), context=unknown)
    registry.record_local(_card(), context=declared)

    fresh = _registry(tmp_path)
    results = fresh.query(LessonQuery(task_family="policy", limit=10))

    assert results
    assert all(
        card.origin_tenant_scope_status is TransferTenantScopeStatus.UNKNOWN for card in results
    )
    declared_result = fresh.find_transfer_candidates(
        LessonQuery(task_family="policy", limit=10), target_context=declared
    )
    assert declared_result.candidates
    assert all(
        card.origin_tenant_scope_status is TransferTenantScopeStatus.DECLARED_UNSCOPED
        for card in declared_result.candidates
    )


def test_materialize_transfer_refuses_card_self_asserted_authenticated_scope(tmp_path) -> None:
    registry = _registry(tmp_path)
    authenticated_hash = anonymize_tenant_id("tenant-a")
    access = AccessScope.for_service(
        tenant_id="tenant-a",
        cell_id=None,
        spiffe_id="spiffe://test/search",
    )
    token = set_current_access_scope(access)
    try:
        forged = _card().model_copy(
            update={
                "origin_tenant_hash": authenticated_hash,
                "origin_tenant_scope_status": TransferTenantScopeStatus.AUTHENTICATED,
            }
        )
        with pytest.raises(TransferScopeRefusedError) as refusal:
            registry.materialize_transfer(
                forged,
                target_context=TransferContext(
                    task_family="policy",
                    domain="labor",
                    run_id="target",
                    tenant_hash=authenticated_hash,
                ),
            )
        assert refusal.value.refusals[0].reason is TransferScopeRefusalReason.SOURCE_BINDING_MISSING
    finally:
        reset_current_access_scope(token)


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

    with pytest.raises(TransferScopeRefusedError) as explicit_scope_conflict:
        resolve_transfer_context(
            context={"transfer_context": base},
            task_family="policy",
            domain="health",
        )
    assert (
        explicit_scope_conflict.value.refusals[0].reason
        is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    )


@pytest.mark.parametrize(
    "malformed_context",
    [
        False,
        0,
        "scope",
        [],
        {"transfer_context": False},
        {"transfer_context": ["policy", "fiscal"]},
        {"transfer_context": {}},
        {"transfer_context": {"task_family": "policy"}},
        {
            "transfer_context": {
                "task_family": "policy",
                "domain": "fiscal",
                "run_id": "run",
                "unexpected": "value",
            }
        },
        {1: "non-string-key"},
        {"policy_search_context": {"task_family": []}},
        {"transfer_context": {"tenant_hash": []}},
        {"transfer_context": {"timestamp": "not-a-time"}},
        {"tenant_scope_status": None},
        {"tenant_hash": ""},
        {"transfer_context": {"cross_tenant_opt_in": "false"}},
        {"transfer_context": {"tenant_scope_status": True}},
        {"cross_tenant_opt_in": "false"},
        {"tenant_hash": []},
        {"policy_search_context": "fiscal"},
    ],
)
def test_resolve_transfer_context_refuses_present_malformed_scope(malformed_context: Any) -> None:
    with pytest.raises(TransferScopeRefusedError) as captured:
        resolve_transfer_context(context=malformed_context)

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE


def test_resolve_transfer_context_preserves_absence_and_valid_mapping_inputs() -> None:
    absent = resolve_transfer_context(context={"transfer_context": None})
    explicit_candidate = resolve_transfer_context(
        context={"transfer_context": None, "tenant_hash": "unattested"}
    )
    mapping_context = resolve_transfer_context(
        context=UserDict(
            {
                "task_family": "policy",
                "domain": "fiscal",
                "run_id": "run-1",
                "user_request": "extra non-scope context stays available",
            }
        )
    )

    assert absent.tenant_hash is None
    assert absent.tenant_scope_status.value == "unknown"
    assert explicit_candidate.tenant_hash == "unattested"
    assert explicit_candidate.tenant_scope_status.value == "unknown"
    assert (mapping_context.task_family, mapping_context.domain, mapping_context.run_id) == (
        "policy",
        "fiscal",
        "run-1",
    )


def test_resolver_refuses_explicit_null_hash_conflicting_with_context() -> None:
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="run-a",
        tenant_hash="tenant-a",
    )

    with pytest.raises(TransferScopeRefusedError) as captured:
        resolve_transfer_context(
            context={"transfer_context": source},
            tenant_hash=None,
            tenant_hash_is_explicit=True,
        )

    assert (
        captured.value.refusals[0].reason
        is TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )


def test_resolver_refuses_conflicting_supplied_tenant_hashes() -> None:
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="run-a",
        tenant_hash="tenant-a",
    )

    with pytest.raises(TransferScopeRefusedError) as captured:
        resolve_transfer_context(context={"transfer_context": source, "tenant_hash": "tenant-b"})

    assert (
        captured.value.refusals[0].reason
        is TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )


def test_resolver_reconciles_present_null_and_typed_hash_field_presence() -> None:
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash="tenant-a",
    )
    with pytest.raises(TransferScopeRefusedError) as outer_null:
        resolve_transfer_context(context={"transfer_context": source, "tenant_hash": None})
    assert (
        outer_null.value.refusals[0].reason
        is TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )

    nested_null = {
        "task_family": "policy",
        "domain": "fiscal",
        "run_id": "source-run",
        "tenant_hash": None,
    }
    with pytest.raises(TransferScopeRefusedError) as nested_null_conflict:
        resolve_transfer_context(
            context={"transfer_context": nested_null, "tenant_hash": "tenant-a"}
        )
    assert (
        nested_null_conflict.value.refusals[0].reason
        is TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )

    defaulted = TransferContext(task_family="policy", domain="fiscal", run_id="source-run")
    assert "tenant_hash" not in defaulted.model_fields_set
    resolved = resolve_transfer_context(
        context={"transfer_context": defaulted, "tenant_hash": "tenant-a"}
    )
    assert resolved.tenant_hash == "tenant-a"
    assert resolved.tenant_scope_status is TransferTenantScopeStatus.UNKNOWN

    explicit_null = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash=None,
    )
    assert "tenant_hash" in explicit_null.model_fields_set
    with pytest.raises(TransferScopeRefusedError) as typed_null_conflict:
        resolve_transfer_context(
            context={"transfer_context": explicit_null, "tenant_hash": "tenant-a"}
        )
    assert (
        typed_null_conflict.value.refusals[0].reason
        is TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )


def test_resolver_reconciles_explicit_transfer_context_and_keyword_hash() -> None:
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash="tenant-a",
    )
    other_source = source.model_copy(update={"tenant_hash": "tenant-b"})
    with pytest.raises(TransferScopeRefusedError) as explicit_context_conflict:
        resolve_transfer_context(
            context={"transfer_context": source}, transfer_context=other_source
        )
    assert (
        explicit_context_conflict.value.refusals[0].reason
        is TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH
    )

    accepted = resolve_transfer_context(
        context={"transfer_context": source, "tenant_hash": "tenant-a"},
        transfer_context=source,
        tenant_hash="tenant-a",
    )
    assert accepted.tenant_hash == "tenant-a"
    assert accepted.tenant_scope_status is TransferTenantScopeStatus.UNKNOWN


def test_resolver_refuses_present_null_conflict_under_live_access_scope() -> None:
    expected_hash = anonymize_tenant_id("tenant-a")
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash=expected_hash,
    )
    token = set_current_access_scope(
        AccessScope.for_service(
            tenant_id="tenant-a", cell_id=None, spiffe_id="spiffe://test/search"
        )
    )
    try:
        with pytest.raises(TransferScopeRefusedError) as captured:
            resolve_transfer_context(context={"transfer_context": source, "tenant_hash": None})
        assert (
            captured.value.refusals[0].reason
            is TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH
        )
    finally:
        reset_current_access_scope(token)


def test_resolver_reconciles_status_from_nested_and_explicit_contexts() -> None:
    declared_unscoped = TransferContext(
        tenant_scope_status=TransferTenantScopeStatus.DECLARED_UNSCOPED
    )
    explicit_unknown = TransferContext(tenant_scope_status=TransferTenantScopeStatus.UNKNOWN)
    with pytest.raises(TransferScopeRefusedError) as captured:
        resolve_transfer_context(
            context={"transfer_context": declared_unscoped},
            transfer_context=explicit_unknown,
        )
    assert (
        captured.value.refusals[0].reason is TransferScopeRefusalReason.TENANT_SCOPE_STATUS_MISMATCH
    )

    # Defaulted fields on a typed context are fallback values, not declarations.
    defaults_only = TransferContext()
    resolved = resolve_transfer_context(
        context={"transfer_context": defaults_only},
        transfer_context=TransferContext(
            task_family="discovery", domain="labor", run_id="explicit"
        ),
    )
    assert (resolved.task_family, resolved.domain, resolved.run_id) == (
        "discovery",
        "labor",
        "explicit",
    )


@pytest.mark.parametrize(
    ("field_name", "replacement", "expected_reason"),
    [
        ("task_family", "discovery", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE),
        ("domain", "labor", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE),
        ("run_id", "other-run", TransferScopeRefusalReason.INVALID_REQUEST_SCOPE),
        ("tenant_hash", "tenant-b", TransferScopeRefusalReason.REQUEST_TENANT_CONTEXT_MISMATCH),
        ("cross_tenant_opt_in", True, TransferScopeRefusalReason.INVALID_REQUEST_SCOPE),
        (
            "timestamp",
            datetime(2030, 1, 2, tzinfo=UTC),
            TransferScopeRefusalReason.INVALID_REQUEST_SCOPE,
        ),
    ],
)
def test_resolver_reconciles_every_present_typed_scope_field(
    field_name: str,
    replacement: Any,
    expected_reason: TransferScopeRefusalReason,
) -> None:
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash="tenant-a",
        cross_tenant_opt_in=False,
        timestamp=datetime(2030, 1, 1, tzinfo=UTC),
    )
    conflicting = source.model_copy(update={field_name: replacement})
    with pytest.raises(TransferScopeRefusedError) as captured:
        resolve_transfer_context(context={"transfer_context": source}, transfer_context=conflicting)
    assert captured.value.refusals[0].reason is expected_reason


@pytest.mark.parametrize(
    ("context", "expected_reason"),
    [
        (
            {"domain": "fiscal", "policy_request_domain": "labor"},
            TransferScopeRefusalReason.INVALID_REQUEST_SCOPE,
        ),
        (
            {"run_id": "run-a", "source_run_id": "run-b"},
            TransferScopeRefusalReason.INVALID_REQUEST_SCOPE,
        ),
        (
            {
                "tenant_scope_status": "declared_unscoped",
                "tenant_hash": "tenant-a",
            },
            TransferScopeRefusalReason.UNSCOPED_SCOPE_MISMATCH,
        ),
        (
            {
                "transfer_context": TransferContext(
                    tenant_scope_status=TransferTenantScopeStatus.UNKNOWN
                ),
                "tenant_scope_status": "declared_unscoped",
            },
            TransferScopeRefusalReason.TENANT_SCOPE_STATUS_MISMATCH,
        ),
        (
            {
                "transfer_context": TransferContext(
                    task_family="policy", domain="fiscal", run_id="source-run"
                ),
                "policy_search_context": {"task_family": "discovery"},
            },
            TransferScopeRefusalReason.INVALID_REQUEST_SCOPE,
        ),
    ],
)
def test_resolver_refuses_conflicting_aliases_and_cross_wrapper_scope(
    context: dict[str, Any], expected_reason: TransferScopeRefusalReason
) -> None:
    with pytest.raises(TransferScopeRefusedError) as captured:
        resolve_transfer_context(context=context)
    assert captured.value.refusals[0].reason is expected_reason


def test_resolver_accepts_redundant_equal_complete_scope_declarations() -> None:
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash="tenant-a",
        cross_tenant_opt_in=True,
        timestamp=datetime(2030, 1, 1, tzinfo=UTC),
    )
    resolved = resolve_transfer_context(
        context={
            "transfer_context": source,
            "task_family": "policy",
            "policy_request_domain": "fiscal",
            "source_run_id": "source-run",
            "tenant_hash": "tenant-a",
            "tenant_scope_status": "unknown",
            "cross_tenant_opt_in": True,
            "timestamp": "2030-01-01T00:00:00Z",
        },
        transfer_context=source,
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        cross_tenant_opt_in=True,
        tenant_hash="tenant-a",
    )
    assert resolved == source


def test_lesson_writer_refuses_malformed_context_before_persist(tmp_path) -> None:
    registry = _registry(tmp_path)

    with pytest.raises(TransferScopeRefusedError) as captured:
        registry.record_local(_card(), context={"tenant_hash": []})  # type: ignore[arg-type]

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    assert list((tmp_path / "registry" / "lessons").rglob("index.json")) == []
    assert list((tmp_path / ".polisyos").rglob("*.json")) == []


def test_transfer_query_refuses_malformed_target_before_local_lookup(tmp_path) -> None:
    registry = _registry(tmp_path)
    registry.record_local(
        _card(),
        context=TransferContext(
            task_family="policy", domain="fiscal", run_id="run-1", tenant_hash="tenant-a"
        ),
    )

    with pytest.raises(TransferScopeRefusedError) as captured:
        registry.query_with_transfer(
            LessonQuery(limit=20),
            target_context={"tenant_hash": []},  # type: ignore[arg-type]
        )

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE


def test_transfer_consumer_refuses_malformed_target_before_index_scan(tmp_path) -> None:
    registry = _registry(tmp_path)

    with pytest.raises(TransferScopeRefusedError) as captured:
        registry.find_transfer_candidates(
            LessonQuery(),
            target_context={"tenant_hash": "tenant-a"},  # type: ignore[arg-type]
        )

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE
    assert list((tmp_path / "registry" / "lessons").rglob("index.json")) == []


def _put_card_with_manifest_schema(
    store: FileSystemCAS,
    card: LessonCard,
    schema_version: str,
    *,
    kind: str = "scientist.search.lesson_card",
    media_type: str = "application/json",
    schema_name: str = "polisyos.scientist.search.LessonCard",
) -> ArtifactRef:
    canon_spec = CanonSpec(forbid_floats=False)
    return store.put_bytes(
        to_canonical_bytes(card, canon_spec),
        PutOptions(
            kind=kind,
            media_type=media_type,
            schema=SchemaInfo(name=schema_name, version=schema_version),
            canon=CanonInfo.from_spec(canon_spec),
        ),
    )


def test_lesson_card_writer_and_fresh_reader_bind_schema_versions(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    current_ref = persist_lesson_card(store, _card())
    current_manifest = store.get_manifest(current_ref)

    assert current_manifest.kind == "scientist.search.lesson_card"
    assert current_manifest.media_type == "application/json"
    assert current_manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.search.LessonCard", version="2.0"
    )
    assert load_lesson_card(store, current_ref).schema_version == "2.0"

    legacy = _card().model_copy(update={"schema_version": "1.0"})
    legacy_ref = _put_card_with_manifest_schema(store, legacy, "1.0")
    assert load_lesson_card(store, legacy_ref).schema_version == "1.0"

    rewritten_ref = persist_lesson_card(store, load_lesson_card(store, legacy_ref))
    assert store.get_manifest(rewritten_ref).artifact_schema.version == "2.0"
    assert load_lesson_card(store, rewritten_ref).schema_version == "2.0"

    mismatched_ref = _put_card_with_manifest_schema(store, legacy, "2.0")
    with pytest.raises(TransferScopeRefusedError) as mismatched:
        load_lesson_card(store, mismatched_ref)
    assert mismatched.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY

    unknown_ref = _put_card_with_manifest_schema(store, _card(), "9.0")
    with pytest.raises(TransferScopeRefusedError) as unknown:
        load_lesson_card(store, unknown_ref)
    assert unknown.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY


def test_resolver_refuses_conflicting_scope_statuses() -> None:
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="run-a",
        tenant_hash="tenant-a",
        tenant_scope_status=TransferTenantScopeStatus.UNKNOWN,
    )

    with pytest.raises(TransferScopeRefusedError) as captured:
        resolve_transfer_context(
            context={
                "transfer_context": source,
                "tenant_scope_status": TransferTenantScopeStatus.DECLARED_UNSCOPED.value,
            }
        )

    assert (
        captured.value.refusals[0].reason is TransferScopeRefusalReason.TENANT_SCOPE_STATUS_MISMATCH
    )


@pytest.mark.parametrize(
    "manifest_fields",
    [
        {"kind": "scientist.search.other"},
        {"media_type": "application/vnd.polisyos.other+json"},
        {"schema_name": "polisyos.scientist.search.Other"},
    ],
)
def test_lesson_card_reader_refuses_nonconforming_manifest_fields(
    tmp_path, manifest_fields
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _put_card_with_manifest_schema(store, _card(), "2.0", **manifest_fields)

    with pytest.raises(TransferScopeRefusedError) as captured:
        load_lesson_card(store, ref)

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY


def test_lesson_index_cas_writer_and_fresh_reader_bind_schema_versions(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy", domain="fiscal", run_id="loop-source", tenant_hash="tenant-a"
    )
    registry.record_local(_card(), context=source)
    snapshot_ref = registry.snapshot_ref()
    assert snapshot_ref is not None
    manifest = registry._store.get_manifest(snapshot_ref)

    assert manifest.kind == "scientist.search.lesson_index"
    assert manifest.media_type == "application/json"
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.search.LessonIndexSnapshot", version="3.0"
    )
    snapshot = LessonRegistry.load_snapshot(registry._store, snapshot_ref)
    assert snapshot.schema_version == "3.0"
    assert snapshot.source_scope is not None

    legacy_payload = snapshot.model_dump(mode="python")
    legacy_payload.pop("source_scope")
    legacy_payload["schema_version"] = "1.0"
    legacy_ref = registry._store.put_json(
        legacy_payload,
        PutOptions(
            kind="scientist.search.lesson_index",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.search.LessonIndexSnapshot", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    with pytest.raises(TransferScopeRefusedError) as legacy_unbound:
        LessonRegistry.load_snapshot(registry._store, legacy_ref)
    assert (
        legacy_unbound.value.refusals[0].reason is TransferScopeRefusalReason.SOURCE_BINDING_MISSING
    )

    mismatched_ref = registry._store.put_json(
        snapshot,
        PutOptions(
            kind="scientist.search.lesson_index",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.search.LessonIndexSnapshot", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    with pytest.raises(TransferScopeRefusedError) as captured:
        LessonRegistry.load_snapshot(registry._store, mismatched_ref)
    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY


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


def test_transfer_limit_applies_after_effective_trust_eligibility(tmp_path) -> None:
    registry = _registry(tmp_path)
    now = datetime.now(UTC)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
        timestamp=now,
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
        timestamp=now,
    )
    fresh = _card(created_at=now).model_copy(update={"summary": "fresh projected transfer"})
    old = _card(created_at=now - timedelta(days=100)).model_copy(
        update={"summary": "older eligible low-confidence transfer"}
    )
    registry.record_local(fresh, context=source)
    registry.record_local(old, context=source)

    query = LessonQuery(
        task_family="policy",
        domain="fiscal",
        source_run_id="run-source",
        trust_levels=[LessonTrustLevel.LOW_CONFIDENCE],
        min_confidence=0.0,
        limit=1,
    )
    raw = registry.find_transfer_candidates(query, target_context=target)
    assert len(raw.candidates) == 1
    assert raw.candidates[0].summary == fresh.summary

    # The first raw source candidate becomes TRANSFERRED and is ineligible.
    # The second candidate age-derived weight produces LOW_CONFIDENCE, which
    # satisfies the query and must consume the single final result slot.
    results = registry.query_with_transfer(query, target_context=target)
    assert len(results) == 1
    assert results[0].lesson_id != fresh.lesson_id
    assert results[0].summary == old.summary
    assert results[0].trust_level is LessonTrustLevel.LOW_CONFIDENCE
    assert results[0].provenance_weight == pytest.approx(0.325)
    assert results[0].domain == "labor"
    assert results[0].origin_domain == "fiscal"

    fresh_reader = _registry(tmp_path)
    persisted = fresh_reader.query(
        LessonQuery(
            task_family="policy",
            domain="labor",
            source_run_id="run-source",
            trust_levels=[LessonTrustLevel.LOW_CONFIDENCE],
            min_confidence=0.0,
            tenant_hash="tenant-a",
            limit=1,
        )
    )
    assert len(persisted) == 1
    assert persisted[0].lesson_id == results[0].lesson_id
    assert persisted[0].origin_domain == "fiscal"


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


def test_evidence_age_survives_reads_restart_and_transfer_materialization(tmp_path) -> None:
    """Usage and transfer clocks cannot renew the producer-owned evidence clock."""
    now = datetime.now(UTC)
    evidence_at = now - timedelta(days=100)
    store = FileSystemCAS(tmp_path / ".polisyos")
    root = tmp_path / "registry" / "lessons"
    policy = TransferPolicy(ttl_days=90)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="age-source",
        tenant_hash="tenant-a",
        timestamp=now,
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="age-target",
        tenant_hash="tenant-a",
        timestamp=now,
    )
    registry = LessonRegistry(root=root, store=store, transfer_policy=policy)
    stale = _card(created_at=evidence_at).model_copy(
        update={"confidence": 0.9, "tags": ["age-anchor"]}
    )
    source_ref = registry.record_local(stale, context=source)

    broad = LessonQuery(
        task_family="policy",
        domain="fiscal",
        tenant_hash="tenant-a",
        tags=["age-anchor"],
        limit=1,
    )
    cold = registry.query(broad)
    warm = registry.query(broad)
    assert [(card.trust_level, card.confidence) for card in (cold + warm)] == [
        (LessonTrustLevel.LOW_CONFIDENCE, 0.5),
        (LessonTrustLevel.LOW_CONFIDENCE, 0.5),
    ]
    assert (
        registry.query(
            broad.model_copy(
                update={
                    "trust_levels": [LessonTrustLevel.LOCAL],
                    "min_confidence": 0.8,
                }
            )
        )
        == []
    )

    reopened = LessonRegistry(root=root, store=store, transfer_policy=policy)
    after_restart = reopened.query(broad)
    assert len(after_restart) == 1
    assert (after_restart[0].trust_level, after_restart[0].confidence) == (
        LessonTrustLevel.LOW_CONFIDENCE,
        0.5,
    )
    source_entry = reopened.index_snapshot(context=source).entries[0]
    assert source_entry.artifact_ref == source_ref
    assert source_entry.last_seen == evidence_at
    assert source_entry.last_accessed_at is not None

    transferred = reopened.query_with_transfer(
        LessonQuery(task_family="policy", tags=["age-anchor"], limit=1),
        target_context=target,
    )
    assert len(transferred) == 1
    assert transferred[0].trust_level is LessonTrustLevel.LOW_CONFIDENCE
    assert transferred[0].confidence == after_restart[0].confidence == 0.5
    assert transferred[0].provenance_weight == pytest.approx(0.325)
    assert transferred[0].created_at == evidence_at

    target_entry = reopened.index_snapshot(context=target).entries[0]
    target_ref = target_entry.artifact_ref
    assert target_entry.last_seen == evidence_at
    assert load_lesson_card(store, target_ref).created_at == evidence_at

    fresh = LessonRegistry(root=root, store=store, transfer_policy=policy)
    target_query = LessonQuery(
        task_family="policy",
        domain="labor",
        tenant_hash="tenant-a",
        tags=["age-anchor"],
        limit=1,
    )
    repeated_target = fresh.query(target_query)
    assert len(repeated_target) == 1
    assert (repeated_target[0].trust_level, repeated_target[0].confidence) == (
        LessonTrustLevel.LOW_CONFIDENCE,
        0.5,
    )
    assert fresh.index_snapshot(context=target).entries[0].artifact_ref == target_ref

    fresh_card = _card(created_at=now).model_copy(update={"tags": ["fresh-control"]})
    fresh.record_local(fresh_card, context=source)
    fresh_transfer = fresh.query_with_transfer(
        LessonQuery(task_family="policy", tags=["fresh-control"], limit=1),
        target_context=target,
    )
    assert len(fresh_transfer) == 1
    assert fresh_transfer[0].trust_level is LessonTrustLevel.TRANSFERRED
    assert fresh_transfer[0].provenance_weight == pytest.approx(0.65)


def test_stale_transfer_confidence_filter_uses_effective_age(tmp_path) -> None:
    """A stale source cannot pass a strict target filter on raw confidence."""
    now = datetime.now(UTC)
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="age-source",
        tenant_hash="tenant-a",
        timestamp=now,
    )
    target = TransferContext(
        task_family="policy",
        domain="labor-strict",
        run_id="age-target",
        tenant_hash="tenant-a",
        timestamp=now,
    )
    registry.record_local(
        _card(created_at=now - timedelta(days=100)).model_copy(
            update={"confidence": 0.9, "tags": ["age-strict"]}
        ),
        context=source,
    )
    local = registry.query(
        LessonQuery(
            task_family="policy",
            domain="fiscal",
            tenant_hash="tenant-a",
            tags=["age-strict"],
            limit=1,
        )
    )
    assert len(local) == 1
    assert (local[0].trust_level, local[0].confidence) == (
        LessonTrustLevel.LOW_CONFIDENCE,
        0.5,
    )
    strict = LessonQuery(
        task_family="policy",
        tags=["age-strict"],
        min_confidence=0.8,
        limit=1,
    )
    assert registry.query_with_transfer(strict, target_context=target) == []
    assert registry.index_snapshot(context=target).entries == []


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


def test_fallback_run_id_never_overrides_or_masks_a_declaration() -> None:
    declared = TransferContext(task_family="policy", domain="fiscal", run_id="declared-run")

    resolved = resolve_transfer_context(
        transfer_context=declared, fallback_run_id="ticket-generated-run"
    )
    assert resolved.run_id == "declared-run"
    assert resolve_transfer_context(fallback_run_id="ticket-generated-run").run_id == (
        "ticket-generated-run"
    )

    with pytest.raises(TransferScopeRefusedError):
        resolve_transfer_context(
            context={"transfer_context": declared, "run_id": None},
            fallback_run_id="ticket-generated-run",
        )
    with pytest.raises(TransferScopeRefusedError):
        resolve_transfer_context(
            transfer_context=declared,
            run_id="conflicting-run",
            fallback_run_id="ticket-generated-run",
        )
    with pytest.raises(TransferScopeRefusedError):
        resolve_transfer_context(fallback_run_id="")


def test_transfer_query_keeps_source_run_filter_separate_from_target(tmp_path) -> None:
    registry = _registry(tmp_path)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="run-source",
        tenant_hash="tenant-a",
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="run-target",
        tenant_hash="tenant-a",
    )
    # The card's task/domain defaults were not supplied as declarations. Its source
    # run remains provenance while target_context chooses the destination scope.
    registry.record_local(_card(), context=source)

    results = registry.query_with_transfer(
        LessonQuery(
            failure_type="transport_failure",
            stage_name="funnel_L1_heuristic",
            fidelity_level=1,
            candidate_hash="pattern",
            task_family="policy",
            domain="fiscal",
            source_run_id="run-source",
            tags=["tax_reform"],
            min_tag_overlap=1,
            tenant_hash="tenant-a",
            limit=3,
        ),
        target_context=target,
    )

    assert len(results) == 1
    assert results[0].source_run_id == "run-source"
    assert results[0].origin_run_id == "run-source"
    assert results[0].domain == "labor"
    assert results[0].origin_domain == "fiscal"
    assert results[0].task_family == "policy"
    assert results[0].failure_type == "transport_failure"
    assert results[0].stage_name == "funnel_L1_heuristic"
    assert results[0].fidelity_level == 1
    assert results[0].candidate_hash == "pattern"
    assert "tax_reform" in results[0].tags
    assert results[0].trust_level == LessonTrustLevel.TRANSFERRED

    # A fresh registry reads the persisted target namespace and still reports the
    # original source run, rather than treating it as the target run declaration.
    fresh = _registry(tmp_path)
    snapshot = fresh.index_snapshot(context=target)
    assert len(snapshot.entries) == 1
    persisted = load_lesson_card(fresh._store, snapshot.entries[0].artifact_ref)
    assert persisted.source_run_id == persisted.origin_run_id == "run-source"
    assert persisted.domain == "labor"
    assert persisted.origin_domain == "fiscal"
    # A fresh local reader evaluates domain in the persisted target namespace;
    # it must not substitute the source-origin domain into this ordinary query.
    readback = fresh.query(
        LessonQuery(
            task_family="policy",
            domain="labor",
            source_run_id="run-source",
            tags=["tax_reform"],
            tenant_hash="tenant-a",
            limit=3,
        )
    )
    assert len(readback) == 1
    assert readback[0].lesson_id == results[0].lesson_id
    assert readback[0].source_run_id == "run-source"
    assert readback[0].domain == "labor"
    assert readback[0].origin_domain == "fiscal"

    # Isolate the wrong-source negative from the persisted labor positive above.
    # This fresh registry contains exactly one source namespace (fiscal); labor is
    # a known destination in the fixture, but no labor card is stored as a source.
    source_only = _registry(tmp_path / "source-only")
    source_only.record_local(_card(), context=source)
    source_entries = source_only.index_snapshot(context=source).entries
    assert len(source_entries) == 1
    assert [entry.domain for entry in source_entries] == ["fiscal"]
    assert source_only.index_snapshot(context=target).entries == []

    wrong_source_domain = source_only.query_with_transfer(
        LessonQuery(
            task_family="policy",
            domain="labor",
            source_run_id="run-source",
            tags=["tax_reform"],
            limit=3,
        ),
        target_context=TransferContext(
            task_family="policy",
            domain="energy",
            run_id="wrong-target",
            tenant_hash="tenant-a",
        ),
    )
    assert wrong_source_domain == []

    with pytest.raises(TransferScopeRefusedError):
        fresh.query_with_transfer(
            LessonQuery(tenant_hash="tenant-b"),
            target_context=target,
        )

    absent_source = fresh.query_with_transfer(
        LessonQuery(
            task_family="policy",
            source_run_id="different-source",
            tags=["tax_reform"],
            limit=3,
        ),
        target_context=target,
    )
    assert absent_source == []

    # An explicitly conflicting card-domain declaration remains a refusal.
    conflicting_card = _card().model_copy(update={"domain": "fiscal"})
    with pytest.raises(TransferScopeRefusedError):
        fresh.record_local(conflicting_card, context=target)


def test_nested_policy_search_scope_reconciles_all_present_scope_fields() -> None:
    emitted = {
        "policy_search_context": {
            "structure_id": "structure-a",
            "policy_family": "policy",
            "task_family": "policy",
            "domain": "fiscal",
        }
    }
    resolved = resolve_transfer_context(context=emitted)
    assert resolved.task_family == "policy"
    assert resolved.domain == "fiscal"

    for field_name, conflicting_value in (("task_family", "discovery"), ("domain", "labor")):
        with pytest.raises(TransferScopeRefusedError):
            resolve_transfer_context(context={**emitted, field_name: conflicting_value})
    for field_name in ("task_family", "domain"):
        for malformed_value in (None, "", "  ", 7, []):
            malformed = {
                "policy_search_context": {
                    "task_family": "policy",
                    "domain": "fiscal",
                    field_name: malformed_value,
                }
            }
            with pytest.raises(TransferScopeRefusedError):
                resolve_transfer_context(context=malformed)
    for malformed_wrapper in (None, "not-a-mapping", [], 7):
        with pytest.raises(TransferScopeRefusedError):
            resolve_transfer_context(context={"policy_search_context": malformed_wrapper})
