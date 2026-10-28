"""Behavioral ownership checks for exact selected CAS fixture views."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.security.tenant_context import tenant_scope


def assert_selected_cas_view_owned(
    cas_root: Path,
    reference: ArtifactRef,
    *,
    tenant_id: str,
    cell_id: str,
) -> None:
    """Reopen an exact view as its owner and refuse foreign tenant/cell readers.

    Optional producer manifest context is not a local ownership claim. The
    actual CAS read boundary must admit the selected owner and reject both
    foreign scopes, including when a producer supplied a matching context.
    """
    assert reference.manifest_profile_sha256 is not None
    reader = FileSystemCAS(cas_root).for_tenant(tenant_id, cell_id)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        manifest = reader.get_manifest(reference)
        payload = reader.get_bytes(reference)
        assert manifest.artifact_id == reference.artifact_id
        assert artifact_manifest_profile_sha256(manifest) == reference.manifest_profile_sha256
        assert hashlib.sha256(payload).hexdigest() == reference.artifact_id.hex

    for foreign_tenant, foreign_cell in (
        (tenant_id + "-foreign", cell_id),
        (tenant_id, cell_id + "-foreign"),
    ):
        foreign = FileSystemCAS(cas_root).for_tenant(foreign_tenant, foreign_cell)
        with tenant_scope(None, tenant_id=foreign_tenant, cell_id=foreign_cell):
            with pytest.raises(ArtifactOwnershipError):
                foreign.get_manifest(reference)
            with pytest.raises(ArtifactOwnershipError):
                foreign.get_bytes(reference)
