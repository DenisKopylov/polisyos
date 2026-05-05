from __future__ import annotations

import pytest
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.exceptions import TenantContextNotSetError
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id,
    get_current_tenant_id_or_none,
    require_tenant_context,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)

TENANT = "11111111-1111-1111-1111-111111111111"
CELL = "22222222-2222-7222-8222-222222222222"


def test_tenant_scope_sets_context() -> None:
    assert get_current_tenant_id_or_none() is None
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert get_current_tenant_id() == TENANT
        assert get_current_cell_id() == CELL
    assert get_current_tenant_id_or_none() is None


def test_get_current_tenant_requires_scope() -> None:
    with pytest.raises(TenantContextNotSetError):
        _ = get_current_tenant_id()


def test_require_tenant_context_decorator() -> None:
    @require_tenant_context
    def guarded() -> str:
        return "ok"

    with pytest.raises(TenantContextNotSetError):
        guarded()

    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert guarded() == "ok"


def test_access_scope_context_helpers() -> None:
    scope = AccessScope(
        tenant_id=TENANT,
        cell_id=CELL,
        principal_type="user",
        user_sub="user-1",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
    )
    assert get_current_access_scope_or_none() is None
    token = set_current_access_scope(scope)
    try:
        assert get_current_access_scope_or_none() == scope
    finally:
        reset_current_access_scope(token)
    assert get_current_access_scope_or_none() is None
