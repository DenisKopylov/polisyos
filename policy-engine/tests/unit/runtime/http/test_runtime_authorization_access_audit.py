from __future__ import annotations

import json
import time
from dataclasses import replace
from typing import Any

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi import Depends
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.permissions import RuntimePermission
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _DenyOPA,
    _fixture_bearer,
    _SlowOPA,
)
from tests.unit.runtime.http.test_runtime_step_up_authz import (
    _production_approval_test_context,
)


class _CaptureAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)


class _FailingAudit:
    def append(self, entry: dict[str, Any]) -> None:
        del entry
        raise OSError("audit storage unavailable")


def _install_audit(client, audit: object) -> None:
    client.app.state.runtime_container.runtime_access_audit = audit
    client.app.state.runtime_access_audit = audit


def _add_low_stakes_probe(client, executed: list[bool], *, suffix: str) -> None:
    action = require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind=f"runtime.ds20.audit.{suffix}",
        ),
    )

    @client.app.post(
        f"/api/v1/ds20/audit/{suffix}",
        dependencies=[Depends(action)],
    )
    def _probe() -> dict[str, bool]:
        executed.append(True)
        return {"mutated": True}


def _secure_probe_client(runtime_api_env, *, opa_client, suffix: str, roles=None):
    bearer = _fixture_bearer(suffix)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa_client,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-{suffix}",
            roles=(frozenset({PolicyOSRole.ADMIN}) if roles is None else roles),
        ),
    )
    return client, bearer


def _headers(runtime_api_env, bearer: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }


def test_authorization_allow_is_appended_to_existing_access_audit_trail(
    runtime_api_env,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="allow",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="allow")

    response = client.post(
        "/api/v1/ds20/audit/allow",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 200, response.json()
    assert executed == [True]
    assert len(audit.entries) == 1
    event = audit.entries[0]
    assert event["schema_version"] == "polisyos.runtime.authorization_audit.v1"
    assert event["event_type"] == "runtime.authorization.decision"
    assert event["outcome"] == "allow"
    assert event["permission"] == "runs.launch"
    assert event["resource_digest"].startswith("sha256:")
    assert event["step_up_outcome"] == "not_required"
    assert event["subject"] == "user-1"


def test_authorization_deny_is_appended_to_existing_access_audit_trail(
    runtime_api_env,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="permission-deny",
        roles=frozenset(),
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="permission-deny")

    response = client.post(
        "/api/v1/ds20/audit/permission-deny",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 403, response.json()
    assert executed == []
    assert len(audit.entries) == 1
    event = audit.entries[0]
    assert event["outcome"] == "deny"
    assert event["denial_reason"] == "action_permission_denied"
    assert event["permission"] == "runs.launch"
    assert event["resource_digest"] == ""


def test_missing_identity_denial_is_appended_without_unbound_authority_claims(
    runtime_api_env,
) -> None:
    client, _cell, _provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)

    response = client.post("/api/v1/control/runs", json={})

    assert response.status_code == 401, response.json()
    assert len(audit.entries) == 1
    event = audit.entries[0]
    assert event["outcome"] == "deny"
    assert event["denial_reason"] == "missing_bearer_token"
    assert event["subject"] == "anonymous"
    assert event["resource_digest"] == ""
    assert event["binding_authority"] == ""


def test_opa_denial_is_appended_once(runtime_api_env) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_DenyOPA(),
        suffix="opa-deny",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="opa-deny")

    response = client.post(
        "/api/v1/ds20/audit/opa-deny",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 403, response.json()
    assert executed == []
    assert len(audit.entries) == 1
    event = audit.entries[0]
    assert event["denial_reason"] == "authorization_denied"
    assert event["opa_policy"] == "polisyos/authz/decision"
    assert event["opa_reasons"] == ["DENY_TEST"]


def test_opa_timeout_is_appended_once(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_OPA_TIMEOUT_SECONDS", "0.1")
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_SlowOPA(),
        suffix="opa-timeout",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="opa-timeout")

    response = client.post(
        "/api/v1/ds20/audit/opa-timeout",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 504, response.json()
    assert executed == []
    assert len(audit.entries) == 1
    assert audit.entries[0]["denial_reason"] == "authz_dependency_timeout"


def test_resource_binding_denial_is_appended_before_opa(runtime_api_env) -> None:
    opa = _CaptureOPA()
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=opa,
        suffix="binding-deny",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)

    response = client.post(
        "/api/v1/control/data/ingest",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 400, response.json()
    assert response.json()["code"] == (
        "authorization_binding_selector_alternative_required"
    )
    assert opa.inputs == []
    assert len(audit.entries) == 1
    event = audit.entries[0]
    assert event["outcome"] == "deny"
    assert event["denial_reason"] == response.json()["code"]
    assert event["permission"] == "evidence.acquire"
    assert event["resource_digest"] == ""


def test_step_up_denial_is_appended_without_token_material(runtime_api_env) -> None:
    context = _production_approval_test_context(
        runtime_api_env,
        suffix="audit-step-up-deny",
    )
    audit = _CaptureAudit()
    _install_audit(context["client"], audit)
    assertion = "this-secret-step-up-value-must-not-be-audited"
    confidential_body_value = "this-confidential-body-value-must-not-be-audited"
    secret_bearer = context["bearer"]

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            **_headers(runtime_api_env, context["bearer"]),
            "X-PolicyOS-Step-Up": assertion,
        },
        json={
            "quality_scorecard_ref": context["scorecard_ref"],
            "override": {
                "reviewer_identity": "user-1",
                "reason": confidential_body_value,
                "scope": f"run:{runtime_api_env['core_run_id']}",
                "expires_at": "2099-01-01T00:00:00Z",
                "evidence_refs": [context["scorecard_ref"]],
            },
        },
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "step_up_verifier_unavailable"
    assert len(audit.entries) == 1
    event = audit.entries[0]
    assert event["outcome"] == "deny"
    assert event["step_up_class"] == "production_approval"
    assert event["step_up_outcome"] == "denied"
    serialized = json.dumps(event)
    assert assertion not in serialized
    assert secret_bearer not in serialized
    assert confidential_body_value not in serialized
    assert set(event) == {
        "schema_version",
        "event_type",
        "timestamp",
        "request_id",
        "outcome",
        "denial_reason",
        "method",
        "route_path",
        "permission",
        "resource_id",
        "resource_digest",
        "resource_kind",
        "binding_authority",
        "step_up_class",
        "step_up_outcome",
        "subject",
        "tenant_id",
        "principal_type",
        "opa_policy",
        "opa_reasons",
    }


def test_denied_mutation_remains_denied_when_access_audit_append_fails(
    runtime_api_env,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="denial-audit-append-failure",
        roles=frozenset(),
    )
    _install_audit(client, _FailingAudit())
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="denial-audit-append-failure")

    response = client.post(
        "/api/v1/ds20/audit/denial-audit-append-failure",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "action_permission_denied"
    assert executed == []


def test_opa_unavailable_is_appended_once(runtime_api_env) -> None:
    from polisyos.core.security.authz import AuthzDecision, AuthzResult

    class _UnavailableOPA:
        async def check(self, authz_input):
            del authz_input
            return AuthzResult(
                decision=AuthzDecision.DENY,
                policy="polisyos/authz/decision",
                reasons=("OPA_UNREACHABLE",),
            )

    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_UnavailableOPA(),
        suffix="opa-unavailable",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="opa-unavailable")

    response = client.post(
        "/api/v1/ds20/audit/opa-unavailable",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "authz_dependency_unavailable"
    assert executed == []
    assert len(audit.entries) == 1
    assert audit.entries[0]["denial_reason"] == "authz_dependency_unavailable"
    assert audit.entries[0]["opa_reasons"] == ["OPA_UNREACHABLE"]


def test_lower_stakes_action_denies_when_access_audit_append_fails(
    runtime_api_env,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="append-failure",
    )
    _install_audit(client, _FailingAudit())
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="append-failure")

    response = client.post(
        "/api/v1/ds20/audit/append-failure",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "authorization_audit_unavailable"
    assert executed == []


def test_high_stakes_action_denies_when_access_audit_append_fails(
    runtime_api_env,
) -> None:
    from polisyos.runtime.http.security import RuntimeSecurityConfig
    from polisyos.runtime.http.step_up import (
        StepUpAssertionVerification,
        StepUpClass,
        require_step_up,
    )

    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="step-up-audit-append-failure",
    )
    _install_audit(client, _FailingAudit())
    action = require_action_permission(
        RuntimePermission.EVIDENCE_ACQUIRE,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.audit.step_up_failure",
        ),
    )
    step_up = require_step_up(StepUpClass.ACQUISITION_APPROVAL)
    executed: list[bool] = []
    now = int(time.time())

    class _Verifier:
        def verify(self, encoded_assertion: str, verification_context):
            assert encoded_assertion == "external-step-up"
            return StepUpAssertionVerification(
                context=verification_context,
                assertion_id="audit-failure-step-up-jti",
                issuer="https://step-up.example",
                audience="polisyos-runtime-step-up",
                issued_at=now - 1,
                expires_at=now + 60,
                assurance="fresh_mfa",
            )

    class _ReplayStore:
        def consume_step_up_assertion(self, *, assertion_id: str, expires_at: int) -> bool:
            assert assertion_id == "audit-failure-step-up-jti"
            assert expires_at == now + 60
            return True

    security = client.app.state.runtime_security
    assert isinstance(security, RuntimeSecurityConfig)
    client.app.state.runtime_security = replace(
        security,
        step_up_verifier=_Verifier(),
        step_up_replay_store=_ReplayStore(),
    )

    @client.app.post(
        "/api/v1/ds20/audit/step-up-append-failure",
        dependencies=[Depends(action), Depends(step_up)],
    )
    def _probe() -> dict[str, bool]:
        executed.append(True)
        return {"mutated": True}

    response = client.post(
        "/api/v1/ds20/audit/step-up-append-failure",
        headers={
            **_headers(runtime_api_env, bearer),
            "X-PolicyOS-Step-Up": "external-step-up",
        },
        json={},
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "authorization_audit_unavailable"
    assert executed == []
