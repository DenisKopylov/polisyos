from __future__ import annotations

from dataclasses import dataclass
from string import ascii_lowercase, digits
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
from polisyos.runtime.http.dependencies import (
    enforce_artifact_tenant_access,
    enforce_run_tenant_access,
)
from polisyos.runtime.http.errors import RuntimeHTTPError

_TENANT_IDS = st.text(alphabet=ascii_lowercase + digits, min_size=1, max_size=24)
_ARTIFACT_ID = ArtifactID.model_validate("sha256:" + "a" * 64)


def _request_for_tenant(tenant_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(
            access_scope=AccessScope(
                tenant_id=tenant_id,
                cell_id="cell-a",
                principal_type="user",
                user_sub="property-user",
                roles=frozenset({PolicyOSRole.VIEWER}),
                max_pii_tier=PIIAccessLevel.LOW,
                mfa_verified=True,
            )
        )
    )


@dataclass(frozen=True)
class _RunDetails:
    tenant_id: str | None


@dataclass(frozen=True)
class _RunRecord:
    details: _RunDetails


@pytest.mark.property
@given(
    scope_tenant=_TENANT_IDS,
    artifact_tenant=st.one_of(_TENANT_IDS, st.none()),
    allow_unscoped=st.booleans(),
)
def test_enforce_artifact_tenant_access_respects_tenant_invariants(
    scope_tenant: str,
    artifact_tenant: str | None,
    allow_unscoped: bool,
) -> None:
    request = _request_for_tenant(scope_tenant)
    ctx = SimpleNamespace(
        allow_unscoped_artifacts=allow_unscoped,
        run_index=SimpleNamespace(get_artifact_tenant=lambda _artifact_id: artifact_tenant),
    )

    if artifact_tenant is None and allow_unscoped:
        assert enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=_ARTIFACT_ID) is None
        return

    if artifact_tenant == scope_tenant:
        assert (
            enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=_ARTIFACT_ID)
            == artifact_tenant
        )
        return

    with pytest.raises(RuntimeHTTPError) as exc_info:
        enforce_artifact_tenant_access(request, ctx=ctx, artifact_id=_ARTIFACT_ID)

    assert exc_info.value.status_code == 403


@pytest.mark.property
@given(scope_tenant=_TENANT_IDS, run_tenant=st.one_of(_TENANT_IDS, st.none()))
def test_enforce_run_tenant_access_is_fail_closed_when_scope_or_tenant_mismatch(
    scope_tenant: str,
    run_tenant: str | None,
) -> None:
    request = _request_for_tenant(scope_tenant)
    run = _RunRecord(details=_RunDetails(tenant_id=run_tenant))

    if run_tenant == scope_tenant:
        enforce_run_tenant_access(request, ctx=SimpleNamespace(), run=run)
        return

    with pytest.raises(RuntimeHTTPError) as exc_info:
        enforce_run_tenant_access(request, ctx=SimpleNamespace(), run=run)

    assert exc_info.value.status_code == 403
