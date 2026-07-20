from __future__ import annotations

from collections.abc import Callable

from polisyos.core.contracts.runtime import ScenarioCreateRequest
from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.permissions import permissions_for_roles
from tests.unit.runtime.http.test_runtime_api_authz import (
    _build_secure_client,
    _CaptureOPA,
    _claims,
    _fixture_bearer,
    _scenario_create_body,
)


class _LineageInterleavingOPA(_CaptureOPA):
    def __init__(self) -> None:
        super().__init__()
        self.callback: Callable[[], None] | None = None

    async def check(self, authz_input):
        self.inputs.append(authz_input)
        callback = self.callback
        if callback is not None and str(authz_input.resource_kind).startswith(
            "runtime.lineage.batch"
        ):
            self.callback = None
            callback()
        return AuthzResult(
            decision=AuthzDecision.ALLOW,
            policy="polisyos/authz/decision",
        )


def _secure_viewer_client(runtime_api_env, *, opa_client, suffix: str):
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
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    return client, headers


def test_server_emitted_run_telemetry_lineage_is_owned_before_opa(
    runtime_api_env,
) -> None:
    opa = _CaptureOPA()
    client, headers = _secure_viewer_client(
        runtime_api_env,
        opa_client=opa,
        suffix="run-telemetry-lineage",
    )
    lineage_id = f"run:{runtime_api_env['core_run_id']}:telemetry"

    with client:
        response = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={"lineage_ids": [lineage_id]},
        )

    assert response.status_code == 200, response.json()
    assert [item["id"] for item in response.json()["lineages"]] == [lineage_id]
    assert len(opa.inputs) == 1
    assert opa.inputs[0].resource_tenant_id == runtime_api_env["tenant_a"]
    assert opa.inputs[0].resource_kind == "runtime.lineage.batch.ownership_verified"


def test_scenario_lineage_head_change_after_opa_binding_fails_before_projection(
    runtime_api_env,
) -> None:
    opa = _LineageInterleavingOPA()
    client, headers = _secure_viewer_client(
        runtime_api_env,
        opa_client=opa,
        suffix="scenario-lineage-race",
    )
    scenario_id = "scn_ds20_lineage_race"
    quantity_response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/quantities"
    )
    assert quantity_response.status_code == 200
    quantity = next(
        item
        for item in quantity_response.json()["quantities"]
        if item["metric_id"] == "policy_cost"
    )
    scenario_request = ScenarioCreateRequest.model_validate(
        _scenario_create_body(scenario_id=scenario_id, quantity=quantity)
    )

    with client:
        ctx = client.app.state.runtime_container.runtime_api_context
        run = ctx.run_index.get_run(runtime_api_env["core_run_id"])
        first = ctx.scenarios.create_for_run(
            run=run,
            request=scenario_request,
            temporal_scope=None,
        )
        assert first.revision == 1
        stable = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={"lineage_ids": [f"scenario:{scenario_id}:model"]},
        )
        assert stable.status_code == 200, stable.json()
        assert stable.json()["lineages"][0]["metadata"]["manifest_hash"] == (
            first.manifest_hash
        )
        opa.callback = lambda: ctx.scenarios.create_for_run(
            run=run,
            request=scenario_request,
            temporal_scope=None,
        )

        response = client.post(
            "/api/v1/lineage/batch",
            headers=headers,
            json={"lineage_ids": [f"scenario:{scenario_id}:model"]},
        )

    assert response.status_code == 409, response.json()
    assert response.json()["code"] == "scenario_authorization_binding_changed"
    assert opa.callback is None
    assert len(opa.inputs) == 2


def test_auth_me_openapi_permission_example_equals_canonical_analyst_grants() -> None:
    openapi = create_runtime_api_app().openapi()
    example = openapi["paths"]["/api/v1/auth/me"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["examples"]["default"]["value"]

    assert example["permissions"] == [
        permission.value for permission in permissions_for_roles([PolicyOSRole.ANALYST])
    ]
