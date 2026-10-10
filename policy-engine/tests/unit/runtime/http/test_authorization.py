from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.permissions import RuntimePermission

_VIEWER_BEARER = "viewer-bearer-1"


class _IdentityProvider:
    def __init__(self, claims: UserIdentityClaims) -> None:
        self._claims = claims

    def extract_user_claims(
        self,
        jwt_token: str,
        *,
        expected_cell_id: str | None = None,
    ) -> UserIdentityClaims:
        if jwt_token != _VIEWER_BEARER or (
            expected_cell_id is not None and expected_cell_id != self._claims.cell_id
        ):
            raise ValueError("test identity does not match the requested cell")
        return self._claims


class _AllowOPA:
    async def check(self, authz_input: Any):
        del authz_input
        from polisyos.core.security.authz import AuthzDecision, AuthzResult

        return AuthzResult(decision=AuthzDecision.ALLOW, policy="test/allow")


class _CaptureAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)


def test_disallowed_production_approval_is_denied_and_audited_with_principal_identity(
    runtime_api_env,
) -> None:
    tenant_id = str(runtime_api_env["tenant_a"])
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=10)
    registry.register_cell(cell)
    for candidate_tenant in (tenant_id, str(runtime_api_env["tenant_b"])):
        registry.register_tenant(
            TenantSpec(
                tenant_id=candidate_tenant,
                name=f"tenant-{candidate_tenant[:8]}",
                region="us-gov-west-1",
            ),
            cell.cell_id,
        )

    claims = UserIdentityClaims(
        sub="viewer-reviewer",
        tenant_id=tenant_id,
        cell_id=cell.cell_id,
        roles=frozenset({PolicyOSRole.VIEWER}),
        mfa_verified=True,
        iss="https://idp.example",
        aud="polisyos-runtime",
        exp=4_102_444_800,
        iat=1,
        jti="jwt-viewer-reviewer",
    )
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        enable_security_middlewares=True,
        identity_provider=_IdentityProvider(claims),
        cell_registry=registry,
        opa_client=_AllowOPA(),
    )
    audit = _CaptureAudit()
    app.state.runtime_access_audit = audit
    app.state.runtime_container.runtime_access_audit = audit

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
            headers={
                "Authorization": f"Bearer {_VIEWER_BEARER}",
                "X-Tenant-ID": tenant_id,
            },
            json={},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "action_permission_denied"
    assert RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE.value in response.json()["detail"]
    assert len(audit.entries) == 1
    event = audit.entries[0]
    assert event["outcome"] == "deny"
    assert event["denial_reason"] == "action_permission_denied"
    assert event["permission"] == RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE.value
    assert event["subject"] == claims.sub
    assert event["tenant_id"] == tenant_id
    assert event["route_path"] == "/api/v1/runs/{run_id}/production-approval"


def test_cross_tenant_run_denial_is_persisted_under_request_principal(
    runtime_api_env,
    monkeypatch,
) -> None:
    from pathlib import Path

    from polisyos.runtime.http.access_audit import RuntimeDataAccessAuditTrail
    from polisyos.runtime.http.compliance import RuntimeAuditQuery, query_runtime_audit

    tenant_a = str(runtime_api_env["tenant_a"])
    tenant_b = str(runtime_api_env["tenant_b"])
    run_id = str(runtime_api_env["cross_tenant_run_id"])
    request_id = "tenant-a-run-b-denial-001"
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=10)
    registry.register_cell(cell)
    for candidate_tenant in (tenant_a, tenant_b):
        registry.register_tenant(
            TenantSpec(
                tenant_id=candidate_tenant,
                name=f"tenant-{candidate_tenant[:8]}",
                region="us-gov-west-1",
            ),
            cell.cell_id,
        )

    claims = UserIdentityClaims(
        sub="tenant-a-requester",
        tenant_id=tenant_a,
        cell_id=cell.cell_id,
        roles=frozenset({PolicyOSRole.ANALYST}),
        mfa_verified=True,
        iss="https://idp.example",
        aud="polisyos-runtime",
        exp=4_102_444_800,
        iat=1,
        jti="jwt-tenant-a-requester",
    )
    app = create_runtime_api_app(
        cas_root=runtime_api_env["cas_root"],
        core_runs_root=runtime_api_env["cas_root"] / "runs",
        enable_security_middlewares=True,
        identity_provider=_IdentityProvider(claims),
        cell_registry=registry,
        opa_client=_AllowOPA(),
    )
    audit_path = Path(runtime_api_env["cas_root"]) / "runtime" / "audit" / "access.jsonl"
    projection_calls: list[str] = []

    with TestClient(app, raise_server_exceptions=False) as client:
        temporal = client.app.state.runtime_api_ctx.temporal
        monkeypatch.setattr(
            temporal,
            "project_run_details",
            lambda run_details, temporal_scope: projection_calls.append(str(run_details.run_id)),
        )
        response = client.get(
            f"/api/v1/runs/{run_id}",
            headers={
                "Authorization": f"Bearer {_VIEWER_BEARER}",
                "X-Tenant-ID": tenant_a,
                "X-Request-ID": request_id,
            },
        )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "run_tenant_mismatch"
    assert tenant_b not in response.text
    assert projection_calls == []

    scan = RuntimeDataAccessAuditTrail(path=audit_path).scan_read_only()
    assert scan.audit_read_error_count == 0
    events = [entry for entry in scan.entries if entry.get("request_id") == request_id]
    assert len(events) == 1
    event = events[0]
    assert event["timestamp"] > 0
    assert event["request_id"] == request_id
    assert event["tenant_id"] == tenant_a
    assert event["actor"] == claims.sub
    assert event["method"] == "GET"
    assert event["endpoint"] == f"/api/v1/runs/{run_id}"
    assert event["operation"] == "READ runtime.run"
    assert event["resource_kind"] == "runtime.run"
    assert event["resource_id"] == run_id
    assert event["outcome"] == "deny"
    assert event["metadata"] == {"denial_reason": "run_tenant_mismatch"}
    assert event["tenant_id"] != tenant_b

    visible_to_compliance_reader = query_runtime_audit(
        runtime_api_env["cas_root"],
        RuntimeAuditQuery(
            stream="access",
            tenant_id=tenant_a,
            actor=claims.sub,
            resource_id=run_id,
            endpoint=f"/api/v1/runs/{run_id}",
            operation="READ runtime.run",
            outcome="deny",
        ),
    )
    assert [entry["request_id"] for entry in visible_to_compliance_reader] == [request_id]
