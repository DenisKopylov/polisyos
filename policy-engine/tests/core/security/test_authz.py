from __future__ import annotations

import asyncio

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.authz import AuthzDecision, AuthzInput, OPAClient
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole


class _MetricsStub:
    def __init__(self) -> None:
        self.cache_hits: list[str] = []
        self.errors: list[tuple[str, str]] = []
        self.latencies: list[tuple[str, float]] = []
        self.decisions: list[tuple[str, str, bool]] = []

    def record_authz_cache_hit(self, *, policy: str) -> None:
        self.cache_hits.append(policy)

    def record_authz_error(self, *, policy: str, reason: str) -> None:
        self.errors.append((policy, reason))

    def record_authz_latency(self, policy: str, duration_seconds: float) -> None:
        self.latencies.append((policy, duration_seconds))

    def record_authz_decision(self, *, policy: str, decision: str, cached: bool) -> None:
        self.decisions.append((policy, decision, cached))


def _scope() -> AccessScope:
    return AccessScope(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
        principal_type="user",
        user_sub="user-1",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
    )


def test_opa_client_uses_cache(monkeypatch) -> None:
    client = OPAClient(cache_ttl_seconds=30.0)
    scope = _scope()
    authz_input = AuthzInput.for_http_request(
        request_method="GET",
        request_path="/api/v1/runs/1",
        request_headers={},
        scope=scope,
        resource_tenant_id=scope.tenant_id,
        resource_kind="run",
    )

    calls = {"count": 0}

    async def _fake_query(payload_input):
        del payload_input
        calls["count"] += 1
        return {"allow": True, "deny_reasons": [], "audit_entry": {"policy": "decision"}}

    monkeypatch.setattr(client, "_query_opa", _fake_query)

    first = asyncio.run(client.check(authz_input))
    second = asyncio.run(client.check(authz_input))

    assert first.decision == AuthzDecision.ALLOW
    assert second.cached is True
    assert calls["count"] == 1


def test_opa_client_denies_on_error(monkeypatch) -> None:
    client = OPAClient(cache_ttl_seconds=0.0)
    scope = _scope()
    authz_input = AuthzInput.for_http_request(
        request_method="GET",
        request_path="/api/v1/runs/1",
        request_headers={},
        scope=scope,
    )

    async def _broken_query(payload_input):
        del payload_input
        raise RuntimeError("OPA down")

    monkeypatch.setattr(client, "_query_opa", _broken_query)

    result = asyncio.run(client.check(authz_input))
    assert result.decision == AuthzDecision.DENY
    assert "OPA_UNREACHABLE" in result.reasons


def test_opa_client_includes_allowed_columns_in_audit_entry(monkeypatch) -> None:
    client = OPAClient(cache_ttl_seconds=0.0)
    scope = _scope()
    authz_input = AuthzInput.for_http_request(
        request_method="GET",
        request_path="/api/v1/data/claims",
        request_headers={},
        scope=scope,
    )

    async def _fake_query(payload_input):
        del payload_input
        return {
            "allow": True,
            "deny_reasons": [],
            "allowed_columns": ["claim_id", "confidence"],
            "audit_entry": {"policy": "decision"},
        }

    monkeypatch.setattr(client, "_query_opa", _fake_query)

    result = asyncio.run(client.check(authz_input))
    assert result.decision == AuthzDecision.ALLOW
    assert result.audit_entry["allowed_columns"] == ["claim_id", "confidence"]


def test_opa_client_uses_injected_metrics(monkeypatch) -> None:
    metrics = _MetricsStub()
    client = OPAClient(cache_ttl_seconds=30.0, metrics=metrics)
    scope = _scope()
    authz_input = AuthzInput.for_http_request(
        request_method="GET",
        request_path="/api/v1/runs/1",
        request_headers={},
        scope=scope,
        resource_tenant_id=scope.tenant_id,
        resource_kind="run",
    )
    calls = {"count": 0}

    monkeypatch.setattr(
        "polisyos.core.security.authz.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    async def _fake_query(payload_input):
        del payload_input
        calls["count"] += 1
        return {"allow": True, "deny_reasons": [], "audit_entry": {"policy": "decision"}}

    monkeypatch.setattr(client, "_query_opa", _fake_query)

    first = asyncio.run(client.check(authz_input))
    second = asyncio.run(client.check(authz_input))

    assert first.decision == AuthzDecision.ALLOW
    assert second.cached is True
    assert calls["count"] == 1
    assert metrics.cache_hits == ["polisyos/authz/decision"]
    assert metrics.decisions == [("polisyos/authz/decision", "allow", False)]
    assert len(metrics.latencies) == 1
