"""Local CAS ownership is independent from producer manifest context markers."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.security.tenant_context import tenant_scope
from tests._helpers.selected_cas_ownership import assert_selected_cas_view_owned


@pytest.mark.parametrize("bound_context", [False, True])
def test_selected_fixture_owner_reopens_without_inventing_producer_context(
    tmp_path: Path, bound_context: bool
) -> None:
    """Real local claims admit exact views with either absent or explicit context."""
    context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    store = FileSystemCAS(tmp_path).with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        reference = store.put_bytes(
            b"selected fixture payload",
            PutOptions(
                kind="research.ownership_fixture",
                media_type="application/octet-stream",
                tenant_context=context if bound_context else None,
            ),
            return_selected_profile=True,
        )
        before = store.get_manifest(reference)
    assert before.tenant_context == (context if bound_context else None)
    assert_selected_cas_view_owned(tmp_path, reference, tenant_id="tenant-a", cell_id="cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert store.get_manifest(reference) == before


@pytest.mark.parametrize("bound_context", [False, True])
def test_producer_context_marker_without_local_owner_claim_is_rejected(
    tmp_path: Path, bound_context: bool
) -> None:
    """Keeping a matching producer marker cannot replace the actual local claim."""
    context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    unowned = FileSystemCAS(tmp_path)
    reference = unowned.put_bytes(
        b"unclaimed fixture payload",
        PutOptions(
            kind="research.ownership_fixture",
            media_type="application/octet-stream",
            tenant_context=context if bound_context else None,
        ),
        return_selected_profile=True,
    )
    assert unowned.get_manifest(reference).tenant_context == (context if bound_context else None)
    with pytest.raises(ArtifactOwnershipError):
        assert_selected_cas_view_owned(tmp_path, reference, tenant_id="tenant-a", cell_id="cell-a")
