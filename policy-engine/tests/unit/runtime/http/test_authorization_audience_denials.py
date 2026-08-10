"""Server-side audience-denial proxies over the DS20 permission floor.

DS5 owns the final PUBLIC/REVIEWER/EXPERT/MACHINE mapping.  Until that bridge
exists, a PUBLIC-class HTTP principal is represented by a genuine authenticated
identity with no granted action permissions.  These tests prove that direct
requests cannot obtain reviewer or expert authority merely because a client
surface exposed or hid an action.
"""

from __future__ import annotations

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.permissions import RuntimePermission
from tests.unit.runtime.http.test_runtime_api_authz import (
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _fixture_bearer,
)


def _authenticated_client(
    runtime_api_env,
    *,
    suffix: str,
    roles: frozenset[PolicyOSRole],
):
    opa = _CaptureOPA()
    bearer = _fixture_bearer(suffix)
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
            jti=f"jwt-{suffix}",
            roles=roles,
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    return client, opa, headers


def _assert_permission_denied(response, *, permission: RuntimePermission) -> None:
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "action_permission_denied"
    assert permission.value in response.json()["detail"]


def test_public_principal_is_denied_reviewer_operation_server_side(
    runtime_api_env,
) -> None:
    client, opa, headers = _authenticated_client(
        runtime_api_env,
        suffix="public-reviewer-operation",
        roles=frozenset(),
    )

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers=headers,
        json={},
    )

    _assert_permission_denied(
        response,
        permission=RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
    )
    assert opa.inputs == []


def test_public_principal_is_denied_expert_operation_server_side(
    runtime_api_env,
) -> None:
    client, opa, headers = _authenticated_client(
        runtime_api_env,
        suffix="public-expert-operation",
        roles=frozenset(),
    )

    response = client.post(
        "/api/v1/control/analytics/sae/causal-frontier",
        headers=headers,
        json={},
    )

    _assert_permission_denied(
        response,
        permission=RuntimePermission.EVIDENCE_SAE_ANALYZE,
    )
    assert opa.inputs == []


def test_hidden_client_action_remains_denied_when_called_directly(
    runtime_api_env,
) -> None:
    client, opa, headers = _authenticated_client(
        runtime_api_env,
        suffix="hidden-action-direct-call",
        roles=frozenset({PolicyOSRole.VIEWER}),
    )

    response = client.post(
        "/api/v1/control/data/promotion/promotion-hidden-client-action/approve",
        headers=headers,
        json={"reason": "a hidden client control is not authorization"},
    )

    _assert_permission_denied(
        response,
        permission=RuntimePermission.EVIDENCE_PROMOTIONS_APPROVE,
    )
    assert opa.inputs == []


def test_role_name_without_exact_permission_is_denied(runtime_api_env) -> None:
    client, opa, headers = _authenticated_client(
        runtime_api_env,
        suffix="role-name-without-permission",
        roles=frozenset({PolicyOSRole.VIEWER}),
    )

    response = client.post(
        "/api/v1/analysis/attractors",
        headers=headers,
        json={},
    )

    _assert_permission_denied(
        response,
        permission=RuntimePermission.ANALYSIS_EXECUTE,
    )
    assert opa.inputs == []


def test_unverified_permission_header_is_ignored(runtime_api_env) -> None:
    client, opa, headers = _authenticated_client(
        runtime_api_env,
        suffix="unverified-permission-header",
        roles=frozenset(),
    )
    headers["X-PolicyOS-Permissions"] = RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE.value

    response = client.post(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/production-approval",
        headers=headers,
        json={},
    )

    _assert_permission_denied(
        response,
        permission=RuntimePermission.RUNS_PRODUCTION_APPROVAL_CREATE,
    )
    assert opa.inputs == []


def test_coarse_opa_allow_without_exact_permission_is_denied(runtime_api_env) -> None:
    client, opa, headers = _authenticated_client(
        runtime_api_env,
        suffix="coarse-opa-without-permission",
        roles=frozenset(),
    )

    response = client.post(
        "/api/v1/control/runs",
        headers=headers,
        json={"data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]}},
    )

    _assert_permission_denied(response, permission=RuntimePermission.RUNS_LAUNCH)
    assert opa.inputs == []


def test_permissionless_or_wrong_role_cannot_fetch_governed_projection(runtime_api_env) -> None:
    """A direct projection URL remains server-denied without its exact grant."""
    client, opa, headers = _authenticated_client(
        runtime_api_env,
        suffix="governed-projection-wrong-grant",
        roles=frozenset({PolicyOSRole.VIEWER}),
    )

    response = client.get(
        "/api/v1/exports/governed-projections/engine-census",
        headers={**headers, "X-PolicyOS-Permissions": "mode.analyst"},
    )

    _assert_permission_denied(response, permission=RuntimePermission.MODE_ANALYST)
    assert len(opa.inputs) == 1
