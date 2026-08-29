from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi import Depends, Request
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    require_action_permission,
)
from polisyos.runtime.http.authz_middleware import AuthzMiddleware
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _DenyOPA,
    _fixture_bearer,
    _SlowOPA,
)
from tests.unit.runtime.http.test_runtime_rego_authorization_parity import _opa_eval
from tests.unit.runtime.http.test_runtime_step_up_authz import (
    _production_approval_body,
    _production_approval_test_context,
)


class _AcquisitionRegoMutationOPA:
    def __init__(self, resource_class: str) -> None:
        self.resource_class = resource_class
        self.payloads: list[dict[str, Any]] = []

    async def check(self, authz_input):
        payload = deepcopy(authz_input.to_opa_input())
        authority = str(payload["resource"]["binding_authority"])
        payload["resource"]["class"] = self.resource_class
        payload["resource"]["kind"] = f"{self.resource_class}.{authority}"
        self.payloads.append(payload)
        allowed = bool(
            _opa_eval(
                "data.polisyos.authz.decision.allow",
                input_value=payload,
            )
        )
        return AuthzResult(
            decision=AuthzDecision.ALLOW if allowed else AuthzDecision.DENY,
            policy="polisyos/authz/decision",
            reasons=("ACTION_REQUEST_PATH_RESOURCE_MISMATCH",) if not allowed else (),
        )


def _hold_exposure_audit_file_lock(path: str, locked, release) -> None:
    import fcntl

    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        locked.send(True)
        release.recv()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _reserve_exposure_in_process(
    path: str,
    unsigned_payload: dict[str, object],
    receipt_ref: str,
    result,
) -> None:
    from polisyos.runtime.http.access_audit import (
        HumanDecisionExposureAuditEvent,
        PreparedHumanDecisionExposureEvent,
        RuntimeDataAccessAuditTrail,
    )

    unsigned = HumanDecisionExposureAuditEvent.model_validate(unsigned_payload)
    prepared = PreparedHumanDecisionExposureEvent(
        unsigned_event=unsigned,
        completed_event=unsigned.model_copy(update={"event_receipt_ref": receipt_ref}),
        receipt_ref=receipt_ref,
    )
    RuntimeDataAccessAuditTrail(path=Path(path))._reserve_exposure_delivery(prepared)
    result.send("reserved")


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


@pytest.mark.parametrize(
    "proxy_resource_class",
    [
        "runtime.case_inspection",
        "runtime.run_paper",
        "runtime.governed_projection.depth_n_cycle_board",
    ],
)
def test_acquisition_get_rego_denies_same_permission_proxy_before_projection(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    proxy_resource_class: str,
) -> None:
    opa = _AcquisitionRegoMutationOPA(proxy_resource_class)
    bearer = _fixture_bearer(f"acquisition-proxy-{proxy_resource_class}")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-acquisition-proxy-{proxy_resource_class}",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    projection_calls: list[str] = []

    def _must_not_project(_service, **kwargs):
        projection_calls.append(str(kwargs.get("run_id")))
        raise AssertionError("acquisition projection executed after proxy authorization")

    monkeypatch.setattr(AcquisitionActionService, "list_routes", _must_not_project)
    audit = _CaptureAudit()
    with client:
        _install_audit(client, audit)
        response = client.get(
            "/api/v1/runs/run-ds15/acquisition-routes",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )

    assert response.status_code == 403, response.text
    assert projection_calls == []
    assert len(opa.payloads) == 1
    payload = opa.payloads[0]
    assert payload["action"] == {"permission": "runs.review"}
    assert "runs.review" in payload["identity"]["permissions"]
    assert payload["resource"]["class"] == proxy_resource_class
    assert audit.entries[-1]["outcome"] == "deny"


def test_invalid_delegation_denial_emits_one_terminal_audit(
    runtime_api_env,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="invalid-delegation-audit",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="invalid-delegation-audit")

    response = client.post(
        "/api/v1/ds20/audit/invalid-delegation-audit",
        headers={
            **_headers(runtime_api_env, bearer),
            "X-PolicyOS-Context": "unverified-delegation",
            "l5d-client-id": "spiffe://polisyos.test/delegator",
        },
        json={},
    )

    assert response.status_code == 403, response.json()
    assert response.json()["code"] == "delegation_not_configured"
    assert executed == []
    assert len(audit.entries) == 1
    assert audit.entries[0]["outcome"] == "deny"
    assert audit.entries[0]["denial_reason"] == "delegation_not_configured"


def test_dependency_override_denial_emits_one_terminal_audit(
    runtime_api_env,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="override-audit",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    action = require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.ds20.audit.override",
        ),
    )
    executed: list[bool] = []

    @client.app.post(
        "/api/v1/ds20/audit/override",
        dependencies=[Depends(action)],
    )
    def _probe() -> dict[str, bool]:
        executed.append(True)
        return {"mutated": True}

    client.app.dependency_overrides[action] = lambda: None
    response = client.post(
        "/api/v1/ds20/audit/override",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "authorization_dependency_overridden"
    assert executed == []
    assert len(audit.entries) == 1
    assert audit.entries[0]["outcome"] == "deny"
    assert audit.entries[0]["denial_reason"] == "authorization_dependency_overridden"


def test_unbound_resource_denial_emits_one_terminal_audit(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="unbound-resource-audit",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="unbound-resource-audit")
    monkeypatch.setattr(AuthzMiddleware, "_opa_resource", lambda *args, **kwargs: None)

    response = client.post(
        "/api/v1/ds20/audit/unbound-resource-audit",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code == 503, response.json()
    assert response.json()["code"] == "authorization_resource_unbound"
    assert executed == []
    assert len(audit.entries) == 1
    assert audit.entries[0]["outcome"] == "deny"
    assert audit.entries[0]["denial_reason"] == "authorization_resource_unbound"


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
    assert response.json()["code"] == ("authorization_binding_selector_alternative_required")
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
        json=_production_approval_body(
            context,
            override={
                "reviewer_identity": "user-1",
                "reason": confidential_body_value,
                "scope": f"run:{runtime_api_env['core_run_id']}",
                "expires_at": "2099-01-01T00:00:00Z",
                "evidence_refs": [context["scorecard_ref"]],
            },
        ),
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


@pytest.mark.parametrize(
    "mutation_kind",
    [
        pytest.param("replace_binding", id="replace-binding"),
        pytest.param("mutate_resource", id="mutate-resource"),
        pytest.param("base_dict_mutator", id="base-dict-mutator"),
        pytest.param("base_state_dict_mutator", id="base-state-dict-mutator"),
        pytest.param("clear_state", id="clear-state"),
    ],
)
def test_handler_cannot_mutate_sealed_authorization_state(
    runtime_api_env,
    mutation_kind: str,
) -> None:
    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix=f"sealed-{mutation_kind}",
    )
    audit = _CaptureAudit()
    _install_audit(client, audit)
    action = require_action_permission(
        RuntimePermission.RUNS_LAUNCH,
        ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind=f"runtime.ds20.audit.sealed.{mutation_kind}",
        ),
    )
    executed: list[bool] = []

    @client.app.post(
        f"/api/v1/ds20/audit/sealed-{mutation_kind}",
        dependencies=[Depends(action)],
    )
    def _probe(request: Request) -> dict[str, bool]:
        if mutation_kind == "replace_binding":
            request.state.authz_bound_resource = object()
        elif mutation_kind == "mutate_resource":
            request.state.authz_resource["kind"] = "attacker-controlled"
        elif mutation_kind == "base_dict_mutator":
            dict.__setitem__(
                request.state.authz_resource,
                "kind",
                "attacker-controlled",
            )
        elif mutation_kind == "base_state_dict_mutator":
            dict.__setitem__(
                request.scope["state"],
                "authz_bound_resource",
                object(),
            )
        else:
            request.scope["state"].clear()
        executed.append(True)
        return {"mutated": True}

    response = client.post(
        f"/api/v1/ds20/audit/sealed-{mutation_kind}",
        headers=_headers(runtime_api_env, bearer),
        json={},
    )

    assert response.status_code >= 500
    if mutation_kind not in {"base_dict_mutator", "base_state_dict_mutator"}:
        assert response.json()["code"] == "authorization_binding_integrity_violation"
    assert executed == []
    assert len(audit.entries) == 1
    # The one durable event is the truthful admission decision. The attempted
    # handler-side state change is rejected before it can alter that decision.
    assert audit.entries[0]["outcome"] == "allow"


def test_blocking_authorization_resolver_does_not_stall_event_loop(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http import authz_middleware as authz_middleware_module

    client, bearer = _secure_probe_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        suffix="resolver-offload",
    )
    _install_audit(client, _CaptureAudit())
    executed: list[bool] = []
    _add_low_stakes_probe(client, executed, suffix="resolver-offload")
    original_bind = authz_middleware_module.bind_authorization_resource

    def _blocking_bind(*args, **kwargs):
        time.sleep(0.35)
        return original_bind(*args, **kwargs)

    monkeypatch.setattr(
        authz_middleware_module,
        "bind_authorization_resource",
        _blocking_bind,
    )

    async def _exercise() -> tuple[httpx.Response, httpx.Response, float]:
        transport = httpx.ASGITransport(app=client.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as async_client:
            started = time.monotonic()
            mutation_task = asyncio.create_task(
                async_client.post(
                    "/api/v1/ds20/audit/resolver-offload",
                    headers=_headers(runtime_api_env, bearer),
                    json={},
                )
            )
            await asyncio.sleep(0.02)
            health = await async_client.get("/health")
            health_elapsed = time.monotonic() - started
            mutation = await mutation_task
        return health, mutation, health_elapsed

    health, mutation, health_elapsed = asyncio.run(_exercise())

    assert health.status_code == 200, health.text
    assert health_elapsed < 0.20
    assert mutation.status_code == 200, mutation.text
    assert executed == [True]


def test_human_decision_exposure_is_a_top_level_completed_event(tmp_path) -> None:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.signing import (
        Ed25519Signer,
        Ed25519Verifier,
        KeyPair,
        SignatureVerificationStatus,
    )
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.runtime.http.access_audit import (
        HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
        HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
        HumanDecisionExposureAuditEvent,
        RuntimeDataAccessAuditTrail,
        complete_human_decision_exposure_event,
        prepare_human_decision_exposure_event,
        reserve_human_decision_exposure_event,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )
    custody_identity = "service://runtime/human-decision-custody"
    custody_pair = KeyPair.generate()
    custody_signer = Ed25519Signer(custody_pair.private_key)
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(
        custody_pair.public_key,
        identity=custody_identity,
    )
    delivered_body = b'{"opened":"exact evidence bytes"}'
    delivered_ref = artifact_store.put_bytes(
        delivered_body,
        ArtifactWriteOptions(
            kind="test.human_decision.exposed_content",
            media_type="application/json",
        ),
    )
    delivered_id = str(delivered_ref.artifact_id)
    unsigned_core = HumanDecisionExposureAuditEvent(
        timestamp=1.0,
        event_id="exposure-1",
        event_ref="runtime://human-decision/exposure-events/exposure-1",
        event_receipt_ref=None,
        tenant_id="tenant-a",
        actor_ref="principal-a",
        run_id="run-a",
        request_ref="sha256:" + "a" * 64,
        request_digest="sha256:" + "b" * 64,
        basis_digest="sha256:" + "c" * 64,
        session_ref="sha256:" + "d" * 64,
        artifact_id=delivered_id,
        content_digest=delivered_id,
        delivered_bytes=len(delivered_body),
        allowed_multiplicity=1,
        verifier_epoch="ds9-test-epoch",
    )
    path = tmp_path / "access.jsonl"
    trail = RuntimeDataAccessAuditTrail(path=path)
    prepared = prepare_human_decision_exposure_event(
        event=unsigned_core,
        artifact_store=artifact_store,
        event_log=event_log,
    )
    reserved = reserve_human_decision_exposure_event(
        trail=trail,
        prepared=prepared,
        artifact_store=artifact_store,
        signer=custody_signer,
        signer_identity=custody_identity,
        verifier=verifier,
    )
    completed = complete_human_decision_exposure_event(
        trail=trail,
        reserved=reserved,
        artifact_store=artifact_store,
        signer=custody_signer,
        signer_identity=custody_identity,
        verifier=verifier,
    )
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert [row["event_type"] for row in rows] == [
        "runtime.human_decision.exposure_delivery_reserved",
        "runtime.human_decision.exposure",
    ]
    persisted = HumanDecisionExposureAuditEvent.model_validate(rows[1])
    assert persisted == completed
    assert persisted.event_type == "runtime.human_decision.exposure"
    assert "outcome" not in persisted.model_dump(mode="json")
    assert persisted.event_receipt_ref is not None

    receipt_id = ArtifactID.model_validate(persisted.event_receipt_ref)
    manifest = artifact_store.get_manifest(receipt_id)
    assert manifest.kind == HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "polisyos.runtime.HumanDecisionExposureAuditEvent"
    assert manifest.artifact_schema.version == HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION
    assert manifest.authority is not None

    signed_core = HumanDecisionExposureAuditEvent.model_validate(
        from_canonical_bytes(artifact_store.get_bytes(receipt_id))
    )
    assert signed_core == unsigned_core
    assert persisted.model_copy(update={"event_receipt_ref": None}) == signed_core

    signature = artifact_store.get_signature(receipt_id)
    assert signature is not None
    assert signature.artifact_id == str(receipt_id)
    assert signature.signer_identity == custody_identity
    verification = artifact_store.verify_signature(
        receipt_id,
        verifier,
        strict_identity=True,
    )
    assert verification.status == SignatureVerificationStatus.VALID
    assert verification.signer_identity == custody_identity

    diagnostic_ref = manifest.authority.diagnostic_event_ref
    diagnostic = DiagnosticEvent.model_validate(
        from_canonical_bytes(artifact_store.get_bytes(diagnostic_ref))
    )
    durable = control_store.list_diagnostic_events(event_id=diagnostic.event_id)
    assert len(durable) == 1
    assert durable[0].event == diagnostic


def test_exposure_signature_failure_leaves_no_completed_row(tmp_path) -> None:
    from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.http.access_audit import (
        HumanDecisionExposureAuditEvent,
        RuntimeAuthorizationAuditError,
        RuntimeDataAccessAuditTrail,
        prepare_human_decision_exposure_event,
        reserve_human_decision_exposure_event,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(
        store=ControlPlaneStore(
            backend="sqlite",
            sqlite_path=tmp_path / "control.sqlite3",
        ),
        artifact_store=artifact_store,
    )
    signer = Ed25519Signer(KeyPair.generate().private_key)
    untrusted_verifier = Ed25519Verifier(strict_identity=True)
    event = HumanDecisionExposureAuditEvent(
        timestamp=1.0,
        event_id="exposure-signature-failure",
        event_ref="runtime://human-decision/exposure-events/signature-failure",
        event_receipt_ref=None,
        tenant_id="tenant-a",
        actor_ref="principal-a",
        run_id="run-a",
        request_ref="sha256:" + "a" * 64,
        request_digest="sha256:" + "b" * 64,
        basis_digest="sha256:" + "c" * 64,
        session_ref="sha256:" + "d" * 64,
        artifact_id="sha256:" + "e" * 64,
        content_digest="sha256:" + "e" * 64,
        delivered_bytes=12,
        allowed_multiplicity=1,
        verifier_epoch="ds9-test-epoch",
    )
    trail = RuntimeDataAccessAuditTrail(path=tmp_path / "access.jsonl")
    prepared = prepare_human_decision_exposure_event(
        event=event,
        artifact_store=artifact_store,
        event_log=event_log,
    )
    with pytest.raises(RuntimeAuthorizationAuditError, match="did not verify"):
        reserve_human_decision_exposure_event(
            trail=trail,
            prepared=prepared,
            artifact_store=artifact_store,
            signer=signer,
            signer_identity="service://runtime/human-decision-custody",
            verifier=untrusted_verifier,
        )

    assert not (tmp_path / "access.jsonl").exists()


def test_exposure_replay_race_has_one_durable_completed_winner(tmp_path) -> None:
    from hashlib import sha256

    from polisyos.core import canon
    from polisyos.runtime.http.access_audit import (
        HumanDecisionExposureAuditEvent,
        PreparedHumanDecisionExposureEvent,
        RuntimeAuthorizationAuditError,
        RuntimeDataAccessAuditTrail,
    )

    unsigned = HumanDecisionExposureAuditEvent(
        timestamp=1.0,
        event_id="exposure-race",
        event_ref="runtime://human-decision/exposure-events/exposure-race",
        event_receipt_ref=None,
        tenant_id="tenant-a",
        actor_ref="principal-a",
        run_id="run-a",
        request_ref="sha256:" + "a" * 64,
        request_digest="sha256:" + "b" * 64,
        basis_digest="sha256:" + "c" * 64,
        session_ref="sha256:" + "d" * 64,
        artifact_id="sha256:" + "e" * 64,
        content_digest="sha256:" + "e" * 64,
        delivered_bytes=12,
        allowed_multiplicity=1,
        verifier_epoch="ds9-test-epoch",
    )
    receipt_ref = (
        "sha256:"
        + sha256(
            canon.to_canonical_bytes(
                unsigned.model_dump(mode="json"),
                canon.CanonSpec(forbid_floats=False),
            )
        ).hexdigest()
    )
    prepared = PreparedHumanDecisionExposureEvent(
        unsigned_event=unsigned,
        completed_event=unsigned.model_copy(update={"event_receipt_ref": receipt_ref}),
        receipt_ref=receipt_ref,
    )
    path = tmp_path / "access.jsonl"

    def _attempt(index: int) -> str:
        trail = RuntimeDataAccessAuditTrail(path=path)
        try:
            trail._reserve_exposure_delivery(prepared)
        except RuntimeAuthorizationAuditError:
            return f"blocked-{index}"
        return f"winner-{index}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(_attempt, range(2)))

    assert sum(outcome.startswith("winner-") for outcome in outcomes) == 1
    assert sum(outcome.startswith("blocked-") for outcome in outcomes) == 1
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.skipif(os.name != "posix", reason="host-level audit locking requires POSIX")
def test_exposure_reservation_waits_for_the_cross_process_file_lock(tmp_path) -> None:
    from hashlib import sha256

    from polisyos.core import canon
    from polisyos.runtime.http.access_audit import HumanDecisionExposureAuditEvent

    unsigned = HumanDecisionExposureAuditEvent(
        timestamp=1.0,
        event_id="exposure-process-lock",
        event_ref="runtime://human-decision/exposure-events/process-lock",
        event_receipt_ref=None,
        tenant_id="tenant-a",
        actor_ref="principal-a",
        run_id="run-a",
        request_ref="sha256:" + "a" * 64,
        request_digest="sha256:" + "b" * 64,
        basis_digest="sha256:" + "c" * 64,
        session_ref="sha256:" + "d" * 64,
        artifact_id="sha256:" + "e" * 64,
        content_digest="sha256:" + "e" * 64,
        delivered_bytes=12,
        allowed_multiplicity=1,
        verifier_epoch="ds9-test-epoch",
    )
    receipt_ref = (
        "sha256:"
        + sha256(
            canon.to_canonical_bytes(
                unsigned.model_dump(mode="json"),
                canon.CanonSpec(forbid_floats=False),
            )
        ).hexdigest()
    )
    path = tmp_path / "access.jsonl"
    ctx = multiprocessing.get_context("fork")
    locked_parent, locked_child = ctx.Pipe(duplex=False)
    release_child, release_parent = ctx.Pipe(duplex=False)
    result_parent, result_child = ctx.Pipe(duplex=False)
    holder = ctx.Process(
        target=_hold_exposure_audit_file_lock,
        args=(str(path), locked_child, release_child),
    )
    reserver = ctx.Process(
        target=_reserve_exposure_in_process,
        args=(str(path), unsigned.model_dump(mode="json"), receipt_ref, result_child),
    )

    holder.start()
    assert locked_parent.poll(5.0)
    assert locked_parent.recv() is True
    reserver.start()
    returned_before_release = result_parent.poll(0.2)
    bytes_before_release = path.read_text(encoding="utf-8")

    release_parent.send(True)
    assert result_parent.poll(5.0)
    assert result_parent.recv() == "reserved"
    holder.join(5.0)
    reserver.join(5.0)
    assert holder.exitcode == 0
    assert reserver.exitcode == 0
    assert returned_before_release is False
    assert bytes_before_release == ""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["event_type"] for row in rows] == [
        "runtime.human_decision.exposure_delivery_reserved"
    ]


def test_exposure_reservation_can_complete_only_once_when_quota_exceeds_one(
    tmp_path,
) -> None:
    from hashlib import sha256

    from polisyos.core import canon
    from polisyos.runtime.http.access_audit import (
        HumanDecisionExposureAuditEvent,
        HumanDecisionExposureReplayError,
        PreparedHumanDecisionExposureEvent,
        RuntimeDataAccessAuditTrail,
    )

    unsigned = HumanDecisionExposureAuditEvent(
        timestamp=1.0,
        event_id="exposure-single-consumption",
        event_ref="runtime://human-decision/exposure-events/single-consumption",
        event_receipt_ref=None,
        tenant_id="tenant-a",
        actor_ref="principal-a",
        run_id="run-a",
        request_ref="sha256:" + "a" * 64,
        request_digest="sha256:" + "b" * 64,
        basis_digest="sha256:" + "c" * 64,
        session_ref="sha256:" + "d" * 64,
        artifact_id="sha256:" + "e" * 64,
        content_digest="sha256:" + "e" * 64,
        delivered_bytes=12,
        allowed_multiplicity=2,
        verifier_epoch="ds9-test-epoch",
    )
    receipt_ref = (
        "sha256:"
        + sha256(
            canon.to_canonical_bytes(
                unsigned.model_dump(mode="json"),
                canon.CanonSpec(forbid_floats=False),
            )
        ).hexdigest()
    )
    prepared = PreparedHumanDecisionExposureEvent(
        unsigned_event=unsigned,
        completed_event=unsigned.model_copy(update={"event_receipt_ref": receipt_ref}),
        receipt_ref=receipt_ref,
    )
    trail = RuntimeDataAccessAuditTrail(path=tmp_path / "access.jsonl")
    reserved = trail._reserve_exposure_delivery(prepared)

    trail._append_reserved_exposure(reserved)
    with pytest.raises(HumanDecisionExposureReplayError, match="already completed"):
        trail._append_reserved_exposure(reserved)

    rows = [
        json.loads(line)
        for line in (tmp_path / "access.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event_type"] for row in rows] == [
        "runtime.human_decision.exposure_delivery_reserved",
        "runtime.human_decision.exposure",
    ]


def test_exposure_reservation_fails_closed_on_truncated_audit_row(tmp_path) -> None:
    from hashlib import sha256

    from polisyos.core import canon
    from polisyos.runtime.http.access_audit import (
        HumanDecisionExposureAuditEvent,
        PreparedHumanDecisionExposureEvent,
        RuntimeAuthorizationAuditError,
        RuntimeDataAccessAuditTrail,
    )

    unsigned = HumanDecisionExposureAuditEvent(
        timestamp=1.0,
        event_id="exposure-after-truncated-row",
        event_ref="runtime://human-decision/exposure-events/after-truncated-row",
        event_receipt_ref=None,
        tenant_id="tenant-a",
        actor_ref="principal-a",
        run_id="run-a",
        request_ref="sha256:" + "a" * 64,
        request_digest="sha256:" + "b" * 64,
        basis_digest="sha256:" + "c" * 64,
        session_ref="sha256:" + "d" * 64,
        artifact_id="sha256:" + "e" * 64,
        content_digest="sha256:" + "e" * 64,
        delivered_bytes=12,
        allowed_multiplicity=1,
        verifier_epoch="ds9-test-epoch",
    )
    receipt_ref = (
        "sha256:"
        + sha256(
            canon.to_canonical_bytes(
                unsigned.model_dump(mode="json"),
                canon.CanonSpec(forbid_floats=False),
            )
        ).hexdigest()
    )
    prepared = PreparedHumanDecisionExposureEvent(
        unsigned_event=unsigned,
        completed_event=unsigned.model_copy(update={"event_receipt_ref": receipt_ref}),
        receipt_ref=receipt_ref,
    )
    path = tmp_path / "access.jsonl"
    truncated = '{"event_type":"runtime.human_decision.exposure_delivery_reserved"'
    path.write_text(truncated, encoding="utf-8")

    with pytest.raises(RuntimeAuthorizationAuditError, match="state unknowable"):
        RuntimeDataAccessAuditTrail(path=path)._reserve_exposure_delivery(prepared)

    assert path.read_text(encoding="utf-8") == truncated


def test_exposure_raw_completed_append_rejects_forged_receipt(tmp_path) -> None:
    from polisyos.runtime.http.access_audit import (
        HumanDecisionExposureAuditEvent,
        RuntimeAuthorizationAuditError,
        RuntimeDataAccessAuditTrail,
    )

    forged = HumanDecisionExposureAuditEvent(
        timestamp=1.0,
        event_id="exposure-forged",
        event_ref="runtime://human-decision/exposure-events/exposure-forged",
        event_receipt_ref="sha256:" + "f" * 64,
        tenant_id="tenant-a",
        actor_ref="principal-a",
        run_id="run-a",
        request_ref="sha256:" + "a" * 64,
        request_digest="sha256:" + "b" * 64,
        basis_digest="sha256:" + "c" * 64,
        session_ref="sha256:" + "d" * 64,
        artifact_id="sha256:" + "e" * 64,
        content_digest="sha256:" + "e" * 64,
        delivered_bytes=12,
        allowed_multiplicity=1,
        verifier_epoch="ds9-test-epoch",
    )
    trail = RuntimeDataAccessAuditTrail(path=tmp_path / "access.jsonl")

    with pytest.raises(RuntimeAuthorizationAuditError, match="verified delivery"):
        trail.append_completed_exposure(forged)


def test_exposure_partial_or_cancelled_send_never_emits_completed_receipt() -> None:
    from polisyos.runtime.http.routes.human_decisions import _ExactExposureResponse

    class _Service:
        def __init__(self) -> None:
            self.completed: list[object] = []

        def prepare_exposure_audit_event(self, delivery):
            del delivery
            return object()

        def complete_exposure_audit_event(self, reserved) -> None:
            self.completed.append(reserved)

    service = _Service()
    response = _ExactExposureResponse(
        cast(
            "Any",
            SimpleNamespace(
                content=b"exact evidence bytes",
                media_type="application/octet-stream",
                artifact_ref="sha256:" + "a" * 64,
                session_ref="sha256:" + "b" * 64,
                allowed_multiplicity=1,
            ),
        ),
        service=cast("Any", service),
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-encoding"] == "identity"
    assert response.headers["etag"] == f'"sha256:{"a" * 64}"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-policyos-exposure-session"] == "sha256:" + "b" * 64

    async def _receive() -> dict[str, object]:
        return {"type": "http.disconnect"}

    async def _send(message: dict[str, object]) -> None:
        if message.get("type") == "http.response.body":
            raise ConnectionError("client disconnected during evidence body")

    with pytest.raises(ConnectionError, match="client disconnected"):
        asyncio.run(
            response(
                {"type": "http", "method": "GET", "path": "/evidence"},
                _receive,
                _send,
            )
        )

    assert service.completed == []


def test_exposure_altered_final_frame_never_emits_completed_receipt() -> None:
    from polisyos.runtime.http.routes.human_decisions import _ExactExposureResponse

    class _Service:
        def __init__(self) -> None:
            self.completed: list[object] = []

        def prepare_exposure_audit_event(self, delivery):
            del delivery
            return object()

        def complete_exposure_audit_event(self, reserved) -> None:
            self.completed.append(reserved)

    service = _Service()
    response = _ExactExposureResponse(
        cast(
            "Any",
            SimpleNamespace(
                content=b"exact evidence bytes",
                media_type="application/octet-stream",
                artifact_ref="sha256:" + "a" * 64,
                session_ref="sha256:" + "b" * 64,
                allowed_multiplicity=1,
            ),
        ),
        service=cast("Any", service),
    )
    response.body = b"altered evidence bytes"

    async def _receive() -> dict[str, object]:
        return {"type": "http.request"}

    async def _send(message: dict[str, object]) -> None:
        del message

    with pytest.raises(RuntimeError, match="one exact terminal body frame"):
        asyncio.run(
            response(
                {"type": "http", "method": "GET", "path": "/evidence"},
                _receive,
                _send,
            )
        )

    assert service.completed == []
