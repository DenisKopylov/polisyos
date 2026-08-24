"""Named DS1 N009-N013 server-side regression probes for Atlas DS20."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.execution_policy import RuntimeBootstrapError
from tests.unit.runtime.http.test_runtime_api_authz import (
    _EXPECTED_MUTATING_OPERATIONS,
    _EXPECTED_MUTATING_PERMISSIONS,
    _HIGH_STAKES_MUTATING_OPERATIONS,
    _action_permission_dependencies,
    _authorized_mutation_request,
    _build_permissionless_client,
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
    _live_mutating_operations,
    _live_mutating_routes,
    _operation_path,
)


def test_ds9_human_decision_mutation_is_structurally_authorized(
    runtime_api_env,
) -> None:
    route = next(
        route
        for route in _live_mutating_routes(runtime_api_env["app"])
        if route.path == "/api/v1/runs/{run_id}/human-decisions"
    )

    assert _action_permission_dependencies(route)


def test_ds1_n009_generic_action_authorization_is_structural_and_fail_closed(
    runtime_api_env,
) -> None:
    from polisyos.runtime.http.authorization import (
        assert_mutating_route_authorization_contract,
    )

    client, bearer = _build_permissionless_client(runtime_api_env)
    assert _live_mutating_operations(client.app) == _EXPECTED_MUTATING_OPERATIONS
    assert all(
        len(_action_permission_dependencies(route)) == 1
        for route in _live_mutating_routes(client.app)
    )

    for method, route_path in _EXPECTED_MUTATING_OPERATIONS:
        response = client.request(
            method,
            _operation_path(route_path, runtime_api_env),
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json={},
        )
        assert response.status_code == 403, (method, route_path, response.text)
        assert response.json()["code"] == "action_permission_denied"

    @client.app.post("/api/v1/ds20/n009-unguarded-sibling")
    def _unguarded_sibling() -> dict[str, bool]:
        return {"mutated": True}

    with pytest.raises(RuntimeError, match="requires one direct"):
        assert_mutating_route_authorization_contract(client.app)


def test_ds1_n010_ui_fallback_identity_cannot_authorize_any_mutation(
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    client, _cell, _provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    spoofed_ui_fallback_headers = {
        "X-Tenant-ID": runtime_api_env["tenant_a"],
        "X-PolicyOS-User": "fallback-analyst",
        "X-PolicyOS-Roles": "analyst",
        "X-PolicyOS-MFA": "true",
        "X-PolicyOS-Permissions": ",".join(
            permission.value
            for permission in sorted(
                set(_EXPECTED_MUTATING_PERMISSIONS.values()),
                key=lambda permission: permission.value,
            )
        ),
    }

    for method, route_path in _EXPECTED_MUTATING_OPERATIONS:
        response = client.request(
            method,
            _operation_path(route_path, runtime_api_env),
            headers=spoofed_ui_fallback_headers,
            json={},
        )
        assert response.status_code == 401, (method, route_path, response.text)
        assert response.json()["code"] == "missing_bearer_token"

    assert opa.inputs == []


def test_ds1_n011_production_fixture_identity_configuration_is_impossible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "production")

    with pytest.raises(RuntimeBootstrapError, match="fixture identity"):
        create_runtime_api_app(
            cas_root=tmp_path / ".polisyos",
            allow_fixture_identity=True,
        )


def _production_approval_packet_ids(store) -> set[str]:
    return {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "runtime.production_approval_packet"
    }


@pytest.mark.parametrize(
    ("reviewer_identity", "signature", "expected_code"),
    [
        pytest.param(
            "self-asserted-reviewer",
            None,
            "production_approval_override_identity_mismatch",
            id="other-reviewer",
        ),
        pytest.param(
            "user-1",
            "client-authored-signature",
            "production_approval_client_signature_forbidden",
            id="client-signature",
        ),
    ],
)
def test_ds1_n012_production_approval_rejects_self_asserted_authority(
    reviewer_identity: str,
    signature: str | None,
    expected_code: str,
    runtime_api_env,
) -> None:
    from tests.unit.runtime.http.test_runtime_step_up_authz import (
        _production_approval_test_context,
    )

    context = _production_approval_test_context(
        runtime_api_env,
        suffix=f"n012-{expected_code}",
    )
    store = context["store"]
    before = _production_approval_packet_ids(store)
    assertion = _install_bound_test_step_up(context["client"])
    override: dict[str, Any] = {
        "reviewer_identity": reviewer_identity,
        "reason": "DS1 N012 authority-boundary probe",
        "scope": f"run:{runtime_api_env['core_run_id']}",
        "expires_at": "2099-01-01T00:00:00Z",
        "evidence_refs": [context["scorecard_ref"]],
    }
    if signature is not None:
        override["signature"] = signature

    response = context["client"].post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers={
            "Authorization": f"Bearer {context['bearer']}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": assertion,
        },
        json={
            "quality_scorecard_ref": context["scorecard_ref"],
            "override": override,
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == expected_code
    assert _production_approval_packet_ids(store) == before


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param(operation, id=operation[1].rsplit("/", 1)[-1])
        for operation in _HIGH_STAKES_MUTATING_OPERATIONS
    ],
)
def test_ds1_n013_unverified_mfa_cannot_reach_high_stakes_handler(
    operation: tuple[str, str],
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    opa = _CaptureOPA()
    bearer = _fixture_bearer("n013-unverified-mfa-" + operation[1])
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    claims = _claims(
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        jti="jwt-n013-" + operation[1],
        roles=frozenset({PolicyOSRole.ADMIN}),
    )
    provider.put_claim(bearer, claims.model_copy(update={"mfa_verified": False}))

    with client:
        request_path, body = _authorized_mutation_request(
            operation,
            runtime_api_env,
            cell_id=cell.cell_id,
            client=client,
            monkeypatch=monkeypatch,
        )
        assertion = _install_bound_test_step_up(client)
        request_options = {} if body is None else {"json": body}
        request_headers = {
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_a"],
            "X-PolicyOS-Step-Up": assertion,
        }
        if operation[1] == "/api/v1/runs/{run_id}/human-decisions":
            request_headers["X-PolicyOS-Human-Decision-Exposure"] = "test-only-exposure-session"
        response = client.request(
            operation[0],
            request_path,
            headers=request_headers,
            **request_options,
        )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "step_up_base_mfa_required"
    assert len(opa.inputs) == 1
