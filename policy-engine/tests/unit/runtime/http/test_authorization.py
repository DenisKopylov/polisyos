from __future__ import annotations

import os
import threading
import time
from typing import Any

import pytest
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


class _FailSecondAppendAudit(_CaptureAudit):
    def __init__(self) -> None:
        super().__init__()
        self.append_calls = 0

    def append(self, entry: dict[str, Any]) -> None:
        self.append_calls += 1
        if self.append_calls == 2:
            raise OSError("authorization audit storage unavailable")
        super().append(entry)


def test_authorization_state_restoration_handles_absent_and_present_none() -> None:
    from starlette.datastructures import State

    from polisyos.runtime.http.authz_middleware import (
        _MISSING_AUTHORIZATION_STATE,
        _restore_authorization_state_value,
    )

    state = State({"present_none": None, "present_value": "before"})
    _restore_authorization_state_value(state, "temporary", _MISSING_AUTHORIZATION_STATE)
    _restore_authorization_state_value(state, "present_none", None)
    _restore_authorization_state_value(state, "present_value", "before")

    assert not hasattr(state, "temporary")
    assert state.present_none is None
    assert state.present_value == "before"


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


@pytest.mark.parametrize(
    "fail_authorization_audit",
    [False, True],
    ids=["decision-persisted", "decision-audit-fails-closed"],
)
def test_cross_tenant_run_denial_is_persisted_under_request_principal(
    runtime_api_env,
    monkeypatch,
    fail_authorization_audit: bool,
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
    failing_audit = _FailSecondAppendAudit() if fail_authorization_audit else None
    if failing_audit is not None:
        app.state.runtime_access_audit = failing_audit
        app.state.runtime_container.runtime_access_audit = failing_audit
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

    if failing_audit is not None:
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "authorization_audit_unavailable"
        assert tenant_b not in response.text
        assert projection_calls == []
        assert failing_audit.append_calls == 2
        assert len(failing_audit.entries) == 1
        data_access_event = failing_audit.entries[0]
        assert data_access_event["tenant_id"] == tenant_a
        assert data_access_event["actor"] == claims.sub
        assert data_access_event["outcome"] == "deny"
        assert data_access_event["metadata"] == {"denial_reason": "run_tenant_mismatch"}
        assert "runtime.authorization.decision" not in str(data_access_event)
        assert tenant_b not in str(data_access_event)
        return

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "run_tenant_mismatch"
    assert tenant_b not in response.text
    assert projection_calls == []

    scan = RuntimeDataAccessAuditTrail(path=audit_path).scan_read_only()
    assert scan.audit_read_error_count == 0
    events = [entry for entry in scan.entries if entry.get("request_id") == request_id]
    authorization_events = [
        entry for entry in events if entry.get("event_type") == "runtime.authorization.decision"
    ]
    data_access_events = [
        entry for entry in events if entry.get("event_type") != "runtime.authorization.decision"
    ]
    assert len(authorization_events) == 1
    assert authorization_events[0]["outcome"] == "deny"
    assert authorization_events[0]["permission"] == RuntimePermission.RUNS_REVIEW.value
    assert authorization_events[0]["denial_reason"] == ("authorization_binding_run_tenant_mismatch")
    assert authorization_events[0]["subject"] == claims.sub
    assert authorization_events[0]["tenant_id"] == tenant_a
    assert len(data_access_events) == 1
    event = data_access_events[0]
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


@pytest.mark.parametrize(
    "failure",
    [
        "none",
        "before",
        "during_next",
        "after_result",
        "scope",
        "unavailable",
        "wrong_type",
        "expired",
    ],
)
def test_cas_batch_authorizer_uses_current_exact_configured_grants(
    tmp_path, monkeypatch, failure: str
) -> None:
    """Local configured grants reach real CAS admission, never signal-as-permission."""
    from polisyos.core.artifacts import FileSystemCAS, PutOptions
    from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
    from polisyos.runtime.http.authorization import (
        DeploymentPrincipalGrantResolver,
        verify_cas_batch_for_request,
    )

    identity = ("https://local-native.invalid", "cas03-local", "worker", "tenant-a", "cell-a")
    claims = UserIdentityClaims(
        iss=identity[0],
        aud=identity[1],
        sub=identity[2],
        tenant_id=identity[3],
        cell_id=identity[4],
        exp=int(time.time()) + (-60 if failure == "expired" else 300),
        iat=int(time.time()) - 120,
    )
    active = DeploymentPrincipalGrantResolver(
        [(identity, [RuntimePermission.ARTIFACTS_BATCH_READ])]
    )
    withdrawn = DeploymentPrincipalGrantResolver([])
    current = [withdrawn if failure == "before" else active]

    def configured_resolver():
        if failure == "unavailable":
            raise OSError("configured grant source unavailable")
        if failure == "wrong_type":
            return None
        return current[0]

    store = FileSystemCAS(
        tmp_path / "cas",
        tenant_id="tenant-b" if failure == "scope" else "tenant-a",
        cell_id="cell-a",
    )
    key = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key.public_key, key_id=key.key_id)
    refs = [
        store.put_bytes(
            f"grant-item-{i}".encode(), PutOptions(kind="cas03.grant", media_type="text/plain")
        )
        for i in range(3)
    ]
    for ref in refs:
        store.sign_artifact(ref, signer)
    consumed = []

    def source():
        for index, ref in enumerate(refs):
            consumed.append(ref)
            if failure == "during_next" and index == 1:
                current[0] = withdrawn
            yield ref.artifact_id

    if os.environ.get("E02_CAS03_REMOVAL") == "request-authorizer":
        verify_batch = store.verify_all_signatures

        def remove_authorizer(*args, **kwargs):
            kwargs.pop("request_authorizer", None)
            return verify_batch(*args, **kwargs)

        monkeypatch.setattr(store, "verify_all_signatures", remove_authorizer)

    verify_one = store.verify_signature

    def verify_and_withdraw(*args, **kwargs):
        result = verify_one(*args, **kwargs)
        if failure == "after_result":
            current[0] = withdrawn
        return result

    monkeypatch.setattr(store, "verify_signature", verify_and_withdraw)
    report = verify_cas_batch_for_request(
        store,
        verifier,
        artifact_ids=source(),
        claims=claims,
        current_resolver=configured_resolver,
        max_workers=1,
        pending_window=1,
    )
    expected = 3 if failure == "none" else (1 if failure in {"during_next", "after_result"} else 0)
    assert report.valid == report.admitted == report.finished == expected
    if failure == "none":
        assert report.state == "complete" and report.inventory_exhausted is True
        assert report.abort_reason is None
    else:
        assert report.state == "aborted" and report.inventory_exhausted is False
        assert report.abort_reason == (
            "inventory_failed" if failure in {"unavailable", "wrong_type"} else "authorization_lost"
        )
        assert report.errors == 1
        assert len(consumed) == (2 if failure == "during_next" else expected)
    for row in report.details[:expected]:
        assert row.status.value == "valid"


def test_configured_cas_grant_loss_drains_real_inflight_callbacks(tmp_path, monkeypatch) -> None:
    """Observed native grant denial preserves both already-admitted crypto rows."""
    from polisyos.core.artifacts import FileSystemCAS, PutOptions
    from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
    from polisyos.runtime.http.authorization import (
        DeploymentPrincipalGrantResolver,
        verify_cas_batch_for_request,
    )

    identity = (
        "https://local-native.invalid",
        "cas03-local",
        "inflight-worker",
        "tenant-a",
        "cell-a",
    )
    claims = UserIdentityClaims(
        iss=identity[0],
        aud=identity[1],
        sub=identity[2],
        tenant_id=identity[3],
        cell_id=identity[4],
        exp=int(time.time()) + 300,
        iat=int(time.time()) - 60,
    )
    active = DeploymentPrincipalGrantResolver(
        [(identity, [RuntimePermission.ARTIFACTS_BATCH_READ])]
    )
    withdrawn = DeploymentPrincipalGrantResolver([])
    current = [active]
    loss_observed = threading.Event()
    second_verified = threading.Event()
    second_finished_after_loss = threading.Event()

    def configured_resolver():
        resolver = current[0]
        if resolver is withdrawn:
            loss_observed.set()
        return resolver

    store = FileSystemCAS(tmp_path / "cas", tenant_id="tenant-a", cell_id="cell-a")
    key = KeyPair.generate()
    signer = Ed25519Signer.from_pem(key.private_pem())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key.public_key, key_id=key.key_id)
    refs = [
        store.put_bytes(
            f"inflight-{i}".encode(), PutOptions(kind="cas03.inflight", media_type="text/plain")
        )
        for i in range(3)
    ]
    for ref in refs:
        store.sign_artifact(ref, signer)
    consumed = []

    def source():
        for ref in refs:
            consumed.append(ref)
            yield ref.artifact_id

    verify_one = store.verify_signature

    def verify_then_wait(artifact_id, selected_verifier, **kwargs):
        result = verify_one(artifact_id, selected_verifier, **kwargs)
        assert result.status.value == "valid"
        if artifact_id == refs[0].artifact_id:
            assert second_verified.wait(5), "second real callback was not admitted"
            current[0] = withdrawn
        else:
            assert artifact_id == refs[1].artifact_id, "post-loss artifact was admitted"
            second_verified.set()
            assert loss_observed.wait(5), "configured grant denial was not observed"
            second_finished_after_loss.set()
        return result

    monkeypatch.setattr(store, "verify_signature", verify_then_wait)
    report = verify_cas_batch_for_request(
        store,
        verifier,
        claims=claims,
        current_resolver=configured_resolver,
        artifact_ids=source(),
        max_workers=2,
        pending_window=2,
    )
    assert second_finished_after_loss.is_set()
    assert consumed == refs[:2]
    assert report.state == "aborted"
    assert report.abort_reason == "authorization_lost"
    assert report.inventory_exhausted is False
    assert report.admitted == report.finished == report.valid == 2
    assert report.errors == 1
    assert {row.artifact_id for row in report.details if row.status.value == "valid"} == {
        str(ref.artifact_id) for ref in refs[:2]
    }
