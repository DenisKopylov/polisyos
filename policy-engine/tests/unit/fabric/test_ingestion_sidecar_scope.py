from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.fabric.storage.tenant_cas import TenantSidecarScope

_TENANT_A = "00000000-0000-0000-0000-00000000000a"
_TENANT_B = "00000000-0000-0000-0000-00000000000b"
_PATH_TENANT = "00000000-0000-0000-0000-0000000000ff"


def test_explicit_sidecar_scope_uses_authenticated_tenant_not_root_components(
    tmp_path: Path,
) -> None:
    base_root = tmp_path / "policy" / "tenants" / _PATH_TENANT / "cas"

    with tenant_scope(None, tenant_id=_TENANT_A, cell_id="cell-a"):
        scope = TenantSidecarScope.from_current_context(base_root)

    assert scope.base_root == base_root
    assert scope.tenant_id == _TENANT_A
    assert scope.cursor_index_root == base_root / "tenants" / _TENANT_A
    assert scope.cache_namespace("connector_cache") == f"tenants/{_TENANT_A}/connector_cache"


def test_explicit_sidecar_scope_preserves_unscoped_candidate_root(tmp_path: Path) -> None:
    base_root = tmp_path / "candidate" / "cas"

    scope = TenantSidecarScope.from_current_context(base_root)

    assert scope.base_root == base_root
    assert scope.tenant_id is None
    assert scope.cursor_index_root == base_root
    assert scope.cache_namespace("connector_cache") == "connector_cache"


def test_explicit_pre_scoped_store_root_does_not_add_a_second_tenant_segment(
    tmp_path: Path,
) -> None:
    store_root = tmp_path / "policy" / "tenants" / _TENANT_A / "cas"

    scope = TenantSidecarScope.for_pre_scoped_store_root(store_root, _TENANT_A)

    assert scope.sidecar_root == store_root
    assert scope.cursor_index_root == store_root
    assert scope.cache_namespace("connector_cache") == "connector_cache"


def test_sidecar_root_cannot_be_supplied_as_an_unbound_path(tmp_path: Path) -> None:
    base_root = tmp_path / "policy" / "cas"

    with pytest.raises((TypeError, ValueError)):
        TenantSidecarScope(
            base_root=base_root,
            tenant_id=_TENANT_A,
            sidecar_root=base_root / "unbound",
        )


@pytest.mark.parametrize(
    "namespace",
    ["/absolute", "../escape", f"tenants/{_TENANT_B}/custom"],
)
def test_explicit_sidecar_scope_rejects_untrusted_or_already_qualified_namespace(
    tmp_path: Path,
    namespace: str,
) -> None:
    with tenant_scope(None, tenant_id=_TENANT_A, cell_id="cell-a"):
        scope = TenantSidecarScope.from_current_context(tmp_path / "cas")

    with pytest.raises(ValueError):
        scope.cache_namespace(namespace)
