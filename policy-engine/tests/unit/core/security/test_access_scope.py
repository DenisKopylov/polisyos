from __future__ import annotations

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims


def test_access_scope_from_user_claims_roundtrip() -> None:
    claims = UserIdentityClaims(
        sub="user-1",
        email="user@example.com",
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
        roles=frozenset({PolicyOSRole.ANALYST}),
        mfa_verified=True,
        iss="https://idp.example/realms/polisyos",
        aud="polisyos-web",
        exp=9_999_999_999,
        iat=1,
        jti="jwt-1",
    )

    scope = AccessScope.from_user_claims(claims)
    payload = scope.to_dict()
    restored = AccessScope.from_dict(payload)

    assert restored.tenant_id == claims.tenant_id
    assert restored.cell_id == claims.cell_id
    assert restored.user_sub == claims.sub
    assert restored.max_pii_tier.value == "high"
    assert restored.roles == frozenset({PolicyOSRole.ANALYST})


def test_access_scope_for_service_defaults() -> None:
    scope = AccessScope.for_service(
        tenant_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        cell_id="cell-b",
        spiffe_id="spiffe://polisyos.io/cell/cell-b/svc/runtime",
    )

    assert scope.principal_type == "service"
    assert scope.roles == frozenset({PolicyOSRole.SERVICE})
    assert scope.max_pii_tier.value == "high"
    assert scope.mfa_verified is False
