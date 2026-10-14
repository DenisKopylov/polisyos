from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferScopeRefusedError,
    TransferTenantScopeStatus,
    anonymize_tenant_id,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_state import (
    load_predictive_voi_scheduler,
    persist_predictive_voi_scheduler,
    predictive_voi_snapshot_path,
)


def _ctx(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(store=SimpleNamespace(root=tmp_path))


def _scope(
    run_id: str,
    status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN,
    tenant_hash: str | None = None,
) -> dict[str, object]:
    return {
        "task_family": "policy",
        "domain": "fiscal",
        "run_id": run_id,
        "tenant_hash": tenant_hash,
        "tenant_scope_status": status.value,
        "cross_tenant_opt_in": False,
        "timestamp": "2026-10-14T00:00:00Z",
    }


def test_candidate_cache_is_partitioned_by_status_and_runtime_run(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    unknown = predictive_voi_snapshot_path(ctx, transfer_context=_scope("runtime-a"))
    same_run = predictive_voi_snapshot_path(ctx, transfer_context=_scope("runtime-a"))
    another_run = predictive_voi_snapshot_path(ctx, transfer_context=_scope("runtime-b"))
    declared = predictive_voi_snapshot_path(
        ctx,
        transfer_context=_scope("runtime-a", TransferTenantScopeStatus.DECLARED_UNSCOPED),
    )

    assert unknown == same_run
    assert unknown != another_run
    assert unknown != declared
    assert unknown is not None and "global" not in unknown.name


def test_candidate_declared_hash_never_selects_tenant_authority_cache(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    supplied_hash = anonymize_tenant_id("candidate-asserted-tenant")
    path = predictive_voi_snapshot_path(
        ctx, transfer_context=_scope("runtime-a", tenant_hash=supplied_hash)
    )

    assert path is not None
    assert supplied_hash not in path.name
    assert "candidate-unknown-" in path.name


def test_serialized_authenticated_label_without_live_scope_is_candidate_only(
    tmp_path: Path,
) -> None:
    tenant_hash = anonymize_tenant_id("candidate-asserted-tenant")
    path = predictive_voi_snapshot_path(
        _ctx(tmp_path),
        transfer_context=_scope("runtime-a", TransferTenantScopeStatus.AUTHENTICATED, tenant_hash),
    )

    assert path is not None
    assert "candidate-unknown-" in path.name
    assert tenant_hash not in path.name


def test_authenticated_runtime_scope_keeps_existing_tenant_cache_location(
    tmp_path: Path,
) -> None:
    access = AccessScope.for_service(
        tenant_id="runtime-tenant-a",
        cell_id=None,
        spiffe_id="spiffe://test/policy-runtime",
    )
    token = set_current_access_scope(access)
    try:
        tenant_hash = anonymize_tenant_id("runtime-tenant-a")
        path = predictive_voi_snapshot_path(
            _ctx(tmp_path),
            transfer_context=_scope(
                "runtime-a", TransferTenantScopeStatus.AUTHENTICATED, tenant_hash
            ),
        )
    finally:
        reset_current_access_scope(token)

    expected = tmp_path / "search_registry" / "voi" / f"policy__fiscal__{tenant_hash}.json"
    assert path == expected


def test_unknown_scope_never_reads_or_overwrites_legacy_global_snapshot(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    legacy_global = tmp_path / "search_registry" / "voi" / "policy__fiscal__global.json"
    legacy_global.parent.mkdir(parents=True)
    legacy_global.write_text("legacy-global-sentinel", encoding="utf-8")
    transfer_context = _scope("runtime-a")

    scheduler = load_predictive_voi_scheduler(ctx, transfer_context=transfer_context)
    persist_predictive_voi_scheduler(ctx, transfer_context=transfer_context, scheduler=scheduler)
    run_local_path = predictive_voi_snapshot_path(ctx, transfer_context=transfer_context)

    assert legacy_global.read_text(encoding="utf-8") == "legacy-global-sentinel"
    assert run_local_path is not None and run_local_path.exists()
    assert run_local_path != legacy_global


def test_missing_runtime_run_uses_fresh_scheduler_without_persisting(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    legacy_global = tmp_path / "search_registry" / "voi" / "policy__fiscal__global.json"
    legacy_global.parent.mkdir(parents=True)
    legacy_global.write_text("legacy-global-sentinel", encoding="utf-8")
    transfer_context = _scope("unknown")

    scheduler = load_predictive_voi_scheduler(ctx, transfer_context=transfer_context)
    persist_predictive_voi_scheduler(ctx, transfer_context=transfer_context, scheduler=scheduler)

    assert predictive_voi_snapshot_path(ctx, transfer_context=transfer_context) is None
    assert legacy_global.read_text(encoding="utf-8") == "legacy-global-sentinel"
    files = list((tmp_path / "search_registry" / "voi").glob("*.json"))
    assert files == [legacy_global]


def test_cache_scope_rejects_malformed_supplied_hash(tmp_path: Path) -> None:
    malformed = _scope("runtime-a")
    malformed["tenant_hash"] = " "

    with pytest.raises(TransferScopeRefusedError):
        predictive_voi_snapshot_path(_ctx(tmp_path), transfer_context=malformed)
