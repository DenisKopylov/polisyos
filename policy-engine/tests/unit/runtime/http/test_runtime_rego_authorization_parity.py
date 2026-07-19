"""Behavioral parity guards for the runtime action/Rego authorization bridge."""

from __future__ import annotations

import json
import shutil
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from fastapi.routing import APIRoute

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.authz import AuthzInput
from polisyos.core.security.identity import PIIAccessLevel
from polisyos.runtime.http.authorization import (
    ActionPermissionVerification,
    ResourceBindingSource,
    ResourceBindingSpec,
    RouteAuthorizationRequirement,
    get_route_action_permission_dependency,
    get_route_authorization_requirement,
)
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.opa_input import (
    CANONICAL_ROLE_AUTHORIZATION_SOURCE,
    DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    RuntimeActionAuthzInput,
    RuntimePrincipalAuthzInput,
)
from polisyos.runtime.http.permissions import RuntimePermission, permissions_for_roles
from polisyos.runtime.http.resource_binding import (
    BindingAuthority,
    BoundAuthorizationResource,
    bind_authorization_resource,
)
from polisyos.runtime.http.security import PolicyOSRole
from tests.unit.runtime.http.test_runtime_api_authz import (
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _fixture_bearer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


_REPO_ROOT = Path(__file__).resolve().parents[4]
_POLICY_DIR = _REPO_ROOT / "ops" / "policy" / "policies"
_OPA_REPRODUCTION_COMMAND = (
    "opa check --strict ops/policy/policies && opa test --fail-on-empty -v ops/policy/policies"
)
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _opa_eval(query: str, *, input_value: Mapping[str, object] | None = None) -> Any:
    opa = shutil.which("opa")
    if opa is None:
        pytest.fail(
            "OPA is required for runtime authorization parity; run: " + _OPA_REPRODUCTION_COMMAND
        )
    completed = subprocess.run(
        [
            opa,
            "eval",
            "--format=json",
            "--strict-builtin-errors",
            "--data",
            str(_POLICY_DIR),
            "--stdin-input",
            query,
        ],
        input=json.dumps(dict(input_value or {})),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    results = document.get("result", [])
    assert len(results) == 1, document
    expressions = results[0].get("expressions", [])
    assert len(expressions) == 1, document
    return expressions[0]["value"]


def _authorities_for_binding(spec: ResourceBindingSpec) -> frozenset[BindingAuthority]:
    if spec.source in {
        ResourceBindingSource.OWNED_EXISTING_PATH,
        ResourceBindingSource.OWNED_EXISTING_BATCH,
        ResourceBindingSource.RESOLVED_SELECTOR_BATCH,
    }:
        return frozenset({BindingAuthority.OWNERSHIP_VERIFIED})
    if spec.source is ResourceBindingSource.RESOLVED_SELECTOR:
        return frozenset({BindingAuthority.CONTENT_RESOLVED_UNSCOPED})
    if spec.source is ResourceBindingSource.REQUEST_COMPOSITE:
        return frozenset({BindingAuthority.REQUEST_BOUND})
    if spec.source is ResourceBindingSource.TENANT_COLLECTION:
        return frozenset({BindingAuthority.TENANT_COLLECTION})
    if spec.source is ResourceBindingSource.OWNED_PARENT_OR_REQUEST_COMPOSITE:
        if spec.parent_required:
            return frozenset({BindingAuthority.OWNERSHIP_VERIFIED})
        return frozenset(
            {
                BindingAuthority.OWNERSHIP_VERIFIED,
                BindingAuthority.REQUEST_BOUND,
            }
        )
    if spec.source is ResourceBindingSource.CANDIDATE_TARGET_SLOT:
        authorities = {BindingAuthority.CANDIDATE}
        if spec.path_parameter is not None:
            authorities.add(BindingAuthority.OWNERSHIP_VERIFIED)
        return frozenset(authorities)
    raise AssertionError(f"unsupported binding source: {spec.source.value}")


def _live_action_contracts(app: object) -> dict[str, dict[str, set[str]]]:
    contracts: dict[str, dict[str, set[str]]] = {}
    for candidate in cast("Any", app).routes:
        if not isinstance(candidate, APIRoute):
            continue
        if not (set(candidate.methods) & _UNSAFE_METHODS):
            continue
        requirement = get_route_authorization_requirement(cast("Any", candidate))
        resource_class = requirement.resource_binding.resource_kind
        authorities = {
            authority.value for authority in _authorities_for_binding(requirement.resource_binding)
        }
        by_resource = contracts.setdefault(requirement.permission.value, {})
        by_resource.setdefault(resource_class, set()).update(authorities)
    return contracts


def test_rego_permission_vocabulary_matches_canonical_server_enum() -> None:
    rego_permissions = set(_opa_eval("data.polisyos.authz.action_permission.permission_vocabulary"))
    server_permissions = {permission.value for permission in RuntimePermission}

    assert len(server_permissions) == 33
    assert rego_permissions == server_permissions
    service_read_contracts = _opa_eval(
        "data.polisyos.authz.action_permission.service_read_contracts"
    )
    assert set(service_read_contracts) == {RuntimePermission.RUNS_VIEW.value}


def test_rego_action_resource_contracts_match_live_mutating_router(
    runtime_api_env,
) -> None:
    raw_contracts = _opa_eval("data.polisyos.authz.action_permission.action_contracts")
    rego_contracts = {
        permission: {
            resource_class: set(authorities) for resource_class, authorities in resources.items()
        }
        for permission, resources in raw_contracts.items()
    }

    assert rego_contracts == _live_action_contracts(runtime_api_env["app"])
    assert set(_opa_eval("data.polisyos.authz.action_permission.binding_authority_vocabulary")) == {
        authority.value for authority in BindingAuthority
    }


def test_runtime_opa_input_projects_exact_sealed_action_contract() -> None:
    requirement = RouteAuthorizationRequirement(
        permission=RuntimePermission.RUNS_LAUNCH,
        resource_binding=ResourceBindingSpec(
            source=ResourceBindingSource.TENANT_COLLECTION,
            resource_kind="runtime.run_collection",
        ),
    )
    verification = ActionPermissionVerification(
        requirement=requirement,
        subject="service:canary",
        tenant_id="tenant-a",
        jwt_id="service-token-1",
        roles=frozenset({PolicyOSRole.SERVICE}),
        authorization_source=DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
        granted_permissions=(RuntimePermission.RUNS_LAUNCH,),
    )
    digest = "sha256:" + "0" * 64
    bound_resource = BoundAuthorizationResource(
        requirement=requirement,
        tenant_id="tenant-a",
        resource_kind="runtime.run_collection.tenant_collection",
        resource_id=f"urn:polisyos:runtime-authorization-resource:v1:{digest}",
        resource_digest=digest,
        authority=BindingAuthority.TENANT_COLLECTION,
        body_sha256="sha256:" + "1" * 64,
        query_sha256="sha256:" + "2" * 64,
        canonical_selectors=(("tenant_id", '"tenant-a"'),),
    )
    scope = AccessScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        principal_type="service",
        user_sub="",
        roles=frozenset({PolicyOSRole.SERVICE}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=False,
        spiffe_id="spiffe://polisyos.test/canary",
    )
    base_input = AuthzInput.for_http_request(
        request_method="POST",
        request_path="/api/v1/control/runs",
        request_headers={},
        scope=scope,
        resource_tenant_id="tenant-a",
        resource_kind=bound_resource.resource_kind,
        resource_artifact_id=bound_resource.resource_id,
    )

    runtime_input = RuntimeActionAuthzInput.from_bound_action(
        base_input=base_input,
        verification=verification,
        bound_resource=bound_resource,
        principal_permissions=(RuntimePermission.RUNS_LAUNCH,),
        authorization_source=DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    )

    payload = runtime_input.to_opa_input()
    assert payload["action"] == {"permission": "runs.launch"}
    assert payload["identity"]["permissions"] == ["runs.launch"]
    assert payload["identity"]["authorization_source"] == "deployment_service_principal"
    assert payload["resource"]["class"] == "runtime.run_collection"
    assert payload["resource"]["binding_authority"] == "tenant_collection"

    with pytest.raises(ValueError, match="sealed action verification"):
        RuntimeActionAuthzInput.from_bound_action(
            base_input=base_input,
            verification=verification,
            bound_resource=bound_resource,
            principal_permissions=(RuntimePermission.EVIDENCE_ACQUIRE,),
            authorization_source=DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
        )
    with pytest.raises(ValueError, match="sealed action verification"):
        RuntimeActionAuthzInput.from_bound_action(
            base_input=base_input,
            verification=verification,
            bound_resource=bound_resource,
            principal_permissions=(RuntimePermission.RUNS_LAUNCH,),
            authorization_source=CANONICAL_ROLE_AUTHORIZATION_SOURCE,
        )


def test_runtime_middleware_sends_sealed_action_contract_to_opa(
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    bearer = _fixture_bearer("rego-action-input")
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
            jti="jwt-rego-action-input",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    with client:
        response = client.post(
            "/api/v1/control/runs",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            json={},
        )

    assert response.status_code == 422
    assert len(opa.inputs) == 1
    runtime_input = opa.inputs[0]
    assert type(runtime_input) is RuntimeActionAuthzInput
    payload = runtime_input.to_opa_input()
    assert payload["action"] == {"permission": "runs.launch"}
    assert payload["resource"]["class"] == "runtime.run_collection"
    assert payload["resource"]["binding_authority"] == "tenant_collection"
    assert payload["identity"]["authorization_source"] == (CANONICAL_ROLE_AUTHORIZATION_SOURCE)
    assert set(payload["identity"]["permissions"]) == {
        permission.value for permission in permissions_for_roles(frozenset({PolicyOSRole.ADMIN}))
    }


@pytest.mark.parametrize(
    ("path", "grants", "expected"),
    [
        ("/api/v1/control/jobs/job-1", (RuntimePermission.RUNS_VIEW,), True),
        ("/api/v1/runs/run-1", (RuntimePermission.RUNS_VIEW,), True),
        (
            "/api/v1/runs/run-1/timeline",
            (RuntimePermission.RUNS_LAUNCH, RuntimePermission.RUNS_VIEW),
            True,
        ),
        ("/api/v1/control/jobs/job-1", (RuntimePermission.RUNS_LAUNCH,), False),
        ("/api/v1/control/data/secret", (RuntimePermission.RUNS_VIEW,), False),
    ],
)
def test_server_service_read_expectation_matches_rego(
    path: str,
    grants: tuple[RuntimePermission, ...],
    expected: bool,
) -> None:
    scope = AccessScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        principal_type="user",
        user_sub="runtime-canary",
        roles=frozenset({PolicyOSRole.ADMIN}),
        max_pii_tier=PIIAccessLevel.CRITICAL,
        mfa_verified=False,
        spiffe_id="",
    )
    base_input = AuthzInput.for_http_request(
        request_method="GET",
        request_path=path,
        request_headers={},
        scope=scope,
        resource_tenant_id="tenant-a",
        resource_kind="http_resource",
    )
    projected = RuntimePrincipalAuthzInput.from_verified_principal(
        base_input=base_input,
        principal_permissions=grants,
        authorization_source=DEPLOYMENT_SERVICE_AUTHORIZATION_SOURCE,
    )

    rego_allowed = _opa_eval(
        "data.polisyos.authz.decision.allow",
        input_value=projected.to_opa_input(),
    )
    server_expected = RuntimePermission.RUNS_VIEW in grants and path in {
        "/api/v1/control/jobs/job-1",
        "/api/v1/runs/run-1",
        "/api/v1/runs/run-1/timeline",
    }
    assert server_expected is expected
    assert rego_allowed is server_expected


class _DecisionInputMutation(StrEnum):
    NONE = "none"
    UNKNOWN_ACTION = "unknown_action"
    MALFORMED_ACTION = "malformed_action"
    KNOWN_ACTION_WRONG_RESOURCE = "known_action_wrong_resource"
    UNKNOWN_RESOURCE = "unknown_resource"
    UNKNOWN_AUTHORITY = "unknown_authority"
    CROSS_TENANT = "cross_tenant"
    FABRICATED_TENANT = "fabricated_tenant"


@dataclass(frozen=True, slots=True)
class _DecisionParityCase:
    name: str
    route_path: str
    role: PolicyOSRole
    body: bytes
    mutation: _DecisionInputMutation = _DecisionInputMutation.NONE


_DECISION_PARITY_CASES = (
    _DecisionParityCase(
        "analyst_launch",
        "/api/v1/control/runs",
        PolicyOSRole.ANALYST,
        b"{}",
    ),
    _DecisionParityCase(
        "viewer_launch",
        "/api/v1/control/runs",
        PolicyOSRole.VIEWER,
        b"{}",
    ),
    _DecisionParityCase(
        "admin_ingestion",
        "/api/v1/control/data/ingest",
        PolicyOSRole.ADMIN,
        b'{"datasets":[{"dataset_id":"dataset-a"}]}',
    ),
    _DecisionParityCase(
        "admin_unscoped_resolution",
        "/api/v1/control/data/resolve",
        PolicyOSRole.ADMIN,
        b'{"data_needs":[{"need_id":"need-a"}]}',
    ),
    _DecisionParityCase(
        "request_bound_resource_with_fabricated_tenant",
        "/api/v1/control/data/resolve",
        PolicyOSRole.ADMIN,
        b'{"data_needs":[{"need_id":"need-a"}]}',
        _DecisionInputMutation.FABRICATED_TENANT,
    ),
    _DecisionParityCase(
        "cross_tenant_launch",
        "/api/v1/control/runs",
        PolicyOSRole.ADMIN,
        b"{}",
        _DecisionInputMutation.CROSS_TENANT,
    ),
    _DecisionParityCase(
        "unknown_action",
        "/api/v1/control/runs",
        PolicyOSRole.ADMIN,
        b"{}",
        _DecisionInputMutation.UNKNOWN_ACTION,
    ),
    _DecisionParityCase(
        "malformed_action",
        "/api/v1/control/runs",
        PolicyOSRole.ADMIN,
        b"{}",
        _DecisionInputMutation.MALFORMED_ACTION,
    ),
    _DecisionParityCase(
        "known_action_wrong_resource",
        "/api/v1/control/runs",
        PolicyOSRole.ADMIN,
        b"{}",
        _DecisionInputMutation.KNOWN_ACTION_WRONG_RESOURCE,
    ),
    _DecisionParityCase(
        "unknown_resource",
        "/api/v1/control/runs",
        PolicyOSRole.ADMIN,
        b"{}",
        _DecisionInputMutation.UNKNOWN_RESOURCE,
    ),
    _DecisionParityCase(
        "unknown_authority",
        "/api/v1/control/runs",
        PolicyOSRole.ADMIN,
        b"{}",
        _DecisionInputMutation.UNKNOWN_AUTHORITY,
    ),
)


def _live_route(app: object, *, method: str, path: str) -> APIRoute:
    matches = [
        candidate
        for candidate in cast("Any", app).routes
        if isinstance(candidate, APIRoute)
        and candidate.path == path
        and method in candidate.methods
    ]
    assert len(matches) == 1, (method, path, matches)
    return matches[0]


def _project_live_server_action(
    app: object,
    *,
    route_path: str,
    role: PolicyOSRole,
    body: bytes,
) -> tuple[bool, dict[str, Any]]:
    route = _live_route(app, method="POST", path=route_path)
    dependency = get_route_action_permission_dependency(cast("Any", route))
    claims = _claims(
        tenant_id="tenant-a",
        cell_id="cell-a",
        jti=f"parity-{role.value}",
        roles=frozenset({role}),
    )
    scope = AccessScope.from_user_claims(claims)
    request = SimpleNamespace(
        method="POST",
        path_params={},
        scope={"query_string": b""},
        state=SimpleNamespace(
            user_claims=claims,
            access_scope=scope,
            authz_effective_scope=scope,
        ),
        app=app,
    )
    try:
        verification = dependency._authorize(cast("Any", request))
    except RuntimeHTTPError:
        fallback_allowed, fallback_payload = _project_live_server_action(
            app,
            route_path=route_path,
            role=PolicyOSRole.ADMIN,
            body=body,
        )
        assert fallback_allowed
        fallback_payload["identity"]["roles"] = [role.value]
        fallback_payload["identity"]["permissions"] = [
            permission.value
            for permission in sorted(
                permissions_for_roles(frozenset({role})),
                key=lambda permission: permission.value,
            )
        ]
        return False, fallback_payload

    assert type(verification) is ActionPermissionVerification
    bound_resource = bind_authorization_resource(
        cast("Any", request),
        dependency.requirement,
        body,
    )
    base_input = AuthzInput.for_http_request(
        request_method="POST",
        request_path=route_path,
        request_headers={},
        scope=scope,
        resource_tenant_id=bound_resource.tenant_id or "",
        resource_kind=bound_resource.resource_kind,
        resource_artifact_id=bound_resource.resource_id,
    )
    projected = RuntimeActionAuthzInput.from_bound_action(
        base_input=base_input,
        verification=verification,
        bound_resource=bound_resource,
    )
    return True, projected.to_opa_input()


def _mutate_live_server_input(
    payload: dict[str, Any],
    mutation: _DecisionInputMutation,
) -> dict[str, Any]:
    candidate = deepcopy(payload)
    if mutation is _DecisionInputMutation.NONE:
        return candidate
    if mutation is _DecisionInputMutation.UNKNOWN_ACTION:
        candidate["action"]["permission"] = "runs.launch.synonym"
    elif mutation is _DecisionInputMutation.MALFORMED_ACTION:
        candidate["action"] = "runs.launch"
    elif mutation is _DecisionInputMutation.KNOWN_ACTION_WRONG_RESOURCE:
        candidate["action"]["permission"] = "evidence.acquire"
    elif mutation is _DecisionInputMutation.UNKNOWN_RESOURCE:
        candidate["resource"]["class"] = "runtime.run_collection.synonym"
        candidate["resource"]["kind"] = "runtime.run_collection.synonym.tenant_collection"
    elif mutation is _DecisionInputMutation.UNKNOWN_AUTHORITY:
        candidate["resource"]["binding_authority"] = "self_asserted"
        candidate["resource"]["kind"] = "runtime.run_collection.self_asserted"
    elif mutation is _DecisionInputMutation.CROSS_TENANT:
        candidate["resource"]["tenant_id"] = "tenant-b"
    elif mutation is _DecisionInputMutation.FABRICATED_TENANT:
        candidate["resource"]["tenant_id"] = "tenant-a"
    else:  # pragma: no cover - closed enum exhaustiveness guard
        raise AssertionError(f"unsupported mutation: {mutation.value}")
    return candidate


@pytest.mark.parametrize("case", _DECISION_PARITY_CASES, ids=lambda case: case.name)
def test_server_and_rego_decisions_match_for_principal_operation_resource_matrix(
    case: _DecisionParityCase,
    runtime_api_env,
) -> None:
    server_route_allowed, server_input = _project_live_server_action(
        runtime_api_env["app"],
        route_path=case.route_path,
        role=case.role,
        body=case.body,
    )
    input_value = _mutate_live_server_input(server_input, case.mutation)
    server_allowed = server_route_allowed and input_value == server_input

    rego_allowed = _opa_eval(
        "data.polisyos.authz.decision.allow",
        input_value=input_value,
    )
    assert rego_allowed is server_allowed
