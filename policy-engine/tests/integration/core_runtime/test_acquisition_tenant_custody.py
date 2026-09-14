"""Actual acquisition keeps producer custody through the tenant-scoped CAS."""

from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.resilience import guard_runtime_cas
from tests.integration.core_runtime.test_acquisition_world_growth_chain import (
    test_actual_wdi_admits_delta_and_reenters_same_case as run_actual_chain,
)
from tests.unit.runtime.http import test_control_service_di as control_fixture


@pytest.mark.asyncio
async def test_actual_acquisition_producers_preserve_tenant_custody_through_reentry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Reconstructing any producer's store loses ownership and breaks this chain."""
    stores = []

    def build_owned_store(path: Path):
        store = guard_runtime_cas(
            artifacts.FileSystemCAS(path).with_ambient_ownership_enforcement()
        )
        stores.append(store)
        request.addfinalizer(store.close)
        return store

    monkeypatch.setattr(control_fixture, "FileSystemCAS", build_owned_store)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        await run_actual_chain(tmp_path, monkeypatch, request, guarded_cas=False)
        assert len(stores) == 1
        store = stores[0]
        snapshots = [
            ref
            for ref in store.iter_artifact_ids()
            if store.get_manifest(ref).kind == "fabric.data_snapshot"
        ]
        assert snapshots
        original = {str(ref): store.get_bytes(ref) for ref in snapshots}
        assert all(store.verify(ref).ok for ref in snapshots)

    for tenant_id, cell_id in (("tenant-b", "cell-a"), ("tenant-a", "cell-b")):
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            for ref in snapshots:
                with pytest.raises(ArtifactOwnershipError):
                    store.get_bytes(ref)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert {str(ref): store.get_bytes(ref) for ref in snapshots} == original
