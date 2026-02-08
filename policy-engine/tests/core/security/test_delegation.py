from __future__ import annotations

import pytest

pytest.importorskip("jwt")

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.delegation import DelegationTokenManager
from polisyos.core.security.exceptions import DelegationVerificationError
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole


def _user_scope() -> AccessScope:
    return AccessScope(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
        principal_type="user",
        user_sub="user-1",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
        jwt_jti="jwt-1",
    )


def test_issue_and_verify_delegation_token() -> None:
    manager = DelegationTokenManager(signing_key="test-secret", ttl_seconds=60)
    scope = _user_scope()
    issuer = "spiffe://polisyos.io/cell/cell-a/svc/scientist"
    audience = "spiffe://polisyos.io/cell/cell-a/svc/fabric"

    token = manager.issue_token(scope=scope, issuer=issuer, audience=audience, trace_id="trace-1")
    claims = manager.verify_token(
        token,
        expected_audience=audience,
        trusted_issuers=frozenset({issuer}),
    )

    restored = claims.to_access_scope()
    assert restored.tenant_id == scope.tenant_id
    assert restored.user_sub == scope.user_sub
    assert restored.roles == scope.roles


def test_untrusted_issuer_is_rejected() -> None:
    manager = DelegationTokenManager(signing_key="test-secret", ttl_seconds=60)
    scope = _user_scope()
    issuer = "spiffe://polisyos.io/cell/cell-a/svc/scientist"
    audience = "spiffe://polisyos.io/cell/cell-a/svc/fabric"

    token = manager.issue_token(scope=scope, issuer=issuer, audience=audience)

    with pytest.raises(DelegationVerificationError):
        manager.verify_token(
            token,
            expected_audience=audience,
            trusted_issuers=frozenset({"spiffe://polisyos.io/cell/cell-a/svc/runtime"}),
        )
