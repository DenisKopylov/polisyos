from __future__ import annotations

import pytest

from polisyos.core.contracts.runtime import AuthMeResponse as CoreAuthMeResponse
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.permissions import (
    ROLE_PERMISSION_GRANTS,
    RuntimePermission,
    permissions_for_roles,
)
from polisyos.runtime.http.routes.auth import AuthMeResponse as HttpAuthMeResponse

_EXPECTED_RUNTIME_PERMISSION_VALUES = (
    "analysis.execute",
    "artifacts.batch.read",
    "artifacts.render",
    "dashboard.view",
    "decisions.validity.publish",
    "evidence.acquire",
    "evidence.discover",
    "evidence.preview",
    "evidence.promotions.approve",
    "evidence.promotions.reject",
    "evidence.resolve",
    "evidence.review",
    "evidence.sae.analyze",
    "evidence.view",
    "fabric.impact.analyze",
    "fabric.quality.read",
    "fabric.trust.read",
    "knowledge.search",
    "knowledge.trigger",
    "knowledge.view",
    "lineage.batch.read",
    "mobility.analyze",
    "mode.analyst",
    "platform.admin",
    "platform.view",
    "runs.batch.read",
    "runs.feedback.evaluate",
    "runs.human_decisions.create",
    "runs.launch",
    "runs.production_approval.create",
    "runs.reissue",
    "runs.review",
    "runs.view",
    "scenarios.create",
)

_ALL_RUNTIME_PERMISSION_VALUES: frozenset[str] = frozenset(_EXPECTED_RUNTIME_PERMISSION_VALUES)
_ADMIN_ONLY_PERMISSION_VALUES: frozenset[str] = frozenset(
    {
        "decisions.validity.publish",
        "runs.production_approval.create",
        "runs.reissue",
    }
)
_HUMAN_DECISION_PERMISSION_VALUE = "runs.human_decisions.create"
_EXPECTED_ROLE_PERMISSION_VALUES: dict[PolicyOSRole, frozenset[str]] = {
    PolicyOSRole.ADMIN: _ALL_RUNTIME_PERMISSION_VALUES,
    PolicyOSRole.ANALYST: _ALL_RUNTIME_PERMISSION_VALUES
    - _ADMIN_ONLY_PERMISSION_VALUES
    - {"platform.admin"},
    PolicyOSRole.VIEWER: frozenset(
        {
            "artifacts.batch.read",
            "dashboard.view",
            "evidence.view",
            "fabric.quality.read",
            "fabric.trust.read",
            "knowledge.search",
            "knowledge.view",
            "lineage.batch.read",
            "platform.view",
            "runs.batch.read",
            "runs.view",
        }
    ),
    PolicyOSRole.SERVICE: _ALL_RUNTIME_PERMISSION_VALUES
    - _ADMIN_ONLY_PERMISSION_VALUES
    - {"evidence.acquire", "scenarios.create", _HUMAN_DECISION_PERMISSION_VALUE},
    PolicyOSRole.SYSTEM: _ALL_RUNTIME_PERMISSION_VALUES
    - _ADMIN_ONLY_PERMISSION_VALUES
    - {"evidence.acquire", "scenarios.create", _HUMAN_DECISION_PERMISSION_VALUE},
}


def test_runtime_permission_values_are_unique_and_stable() -> None:
    values = tuple(permission.value for permission in RuntimePermission)

    assert values == _EXPECTED_RUNTIME_PERMISSION_VALUES
    assert len(values) == len(set(values))
    assert len(RuntimePermission.__members__) == len(values)


def test_role_grants_only_contain_runtime_permission_members() -> None:
    assert set(ROLE_PERMISSION_GRANTS) == set(PolicyOSRole)
    assert all(
        isinstance(permission, RuntimePermission)
        for grants in ROLE_PERMISSION_GRANTS.values()
        for permission in grants
    )
    assert ROLE_PERMISSION_GRANTS[PolicyOSRole.ADMIN] == frozenset(RuntimePermission)


@pytest.mark.parametrize("role", list(PolicyOSRole))
def test_role_grants_match_exact_normative_matrix(role: PolicyOSRole) -> None:
    actual_values = frozenset(permission.value for permission in ROLE_PERMISSION_GRANTS[role])

    assert actual_values == _EXPECTED_ROLE_PERMISSION_VALUES[role]
    assert permissions_for_roles([role]) == sorted(
        ROLE_PERMISSION_GRANTS[role],
        key=lambda permission: permission.value,
    )


def test_role_permission_union_is_stable_and_empty_roles_deny_all() -> None:
    assert permissions_for_roles([]) == []

    roles = [PolicyOSRole.VIEWER, PolicyOSRole.ANALYST]
    expected = sorted(
        ROLE_PERMISSION_GRANTS[PolicyOSRole.VIEWER] | ROLE_PERMISSION_GRANTS[PolicyOSRole.ANALYST],
        key=lambda permission: permission.value,
    )
    assert permissions_for_roles(roles) == expected


def test_non_admin_roles_never_gain_admin_only_authority() -> None:
    admin_only_permissions = {RuntimePermission(value) for value in _ADMIN_ONLY_PERMISSION_VALUES}

    for role in PolicyOSRole:
        if role is not PolicyOSRole.ADMIN:
            assert ROLE_PERMISSION_GRANTS[role].isdisjoint(admin_only_permissions)


def test_human_decision_create_is_only_granted_to_accountable_human_roles() -> None:
    permission = RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE

    assert permission in ROLE_PERMISSION_GRANTS[PolicyOSRole.ADMIN]
    assert permission in ROLE_PERMISSION_GRANTS[PolicyOSRole.ANALYST]
    assert all(
        permission not in ROLE_PERMISSION_GRANTS[role]
        for role in (PolicyOSRole.VIEWER, PolicyOSRole.SERVICE, PolicyOSRole.SYSTEM)
    )


def test_http_auth_me_response_preserves_core_shape_except_permission_type() -> None:
    assert HttpAuthMeResponse.model_fields.keys() == CoreAuthMeResponse.model_fields.keys()
    for field_name, http_field in HttpAuthMeResponse.model_fields.items():
        if field_name == "permissions":
            continue
        core_field = CoreAuthMeResponse.model_fields[field_name]
        assert http_field.annotation == core_field.annotation
        assert http_field.is_required() == core_field.is_required()
        assert http_field.default == core_field.default
        assert http_field.default_factory == core_field.default_factory


def test_openapi_projects_runtime_permission_enum() -> None:
    openapi = create_runtime_api_app().openapi()
    auth_me_response = openapi["paths"]["/api/v1/auth/me"]["get"]["responses"]["200"]
    response_schema = auth_me_response["content"]["application/json"]["schema"]
    schemas = openapi["components"]["schemas"]

    assert response_schema == {"$ref": "#/components/schemas/AuthMeResponse"}
    assert schemas["AuthMeResponse"]["properties"]["permissions"]["items"] == {
        "$ref": "#/components/schemas/RuntimePermission"
    }
    assert tuple(schemas["RuntimePermission"]["enum"]) == _EXPECTED_RUNTIME_PERMISSION_VALUES
